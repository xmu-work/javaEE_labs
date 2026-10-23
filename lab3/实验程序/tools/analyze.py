"""Stats + figures for lab3. Usage: analyze.py <pkg_dir> <fig_dir>
Reads 原始数据/*/*.jtl and 原始数据/03_Prometheus监控/*.json under pkg_dir."""
import csv, glob, json, os, sys, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

pkg, figdir = sys.argv[1], sys.argv[2]
os.makedirs(figdir, exist_ok=True)
font_manager.fontManager.addfont("/System/Library/Fonts/Hiragino Sans GB.ttc")
plt.rcParams.update({
    "font.family": "Hiragino Sans GB", "font.size": 9, "axes.unicode_minus": False,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e", "xtick.color": "#898781",
    "ytick.color": "#898781", "axes.grid": True, "grid.color": "#e1e0d9", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
    "axes.facecolor": "#fcfcfb", "legend.frameon": False, "lines.linewidth": 1.6,
})
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK2, MUTED = "#52514e", "#898781"


def pct(sorted_vals, p):  # linear interpolation, same as numpy default
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        r["t"], r["e"], r["c"] = int(r["timeStamp"]), int(r["elapsed"]), int(r.get("Connect") or 0)
    return rows


groups = []
for kind, op, sub in (("base", "读取", "01_JPA读取"), ("base", "写入", "02_JPA写入"),
                      ("sat", "读取", "04_JPA读取_吞吐上限"), ("sat", "写入", "05_JPA写入_吞吐上限")):
    for f in glob.glob(f"{pkg}/原始数据/{sub}/*.jtl"):
        name = os.path.basename(f)[:-4]
        threads = int(name.split("_")[1].replace("线程", ""))
        ramp = int(name.split("_")[2].replace("秒升压", ""))
        loops = int(name.split("_")[3].replace("次循环", ""))
        groups.append(dict(kind=kind, op=op, threads=threads, ramp=ramp, loops=loops, name=name, rows=load(f)))
groups.sort(key=lambda g: (g["kind"] != "base", g["op"] != "读取", g["threads"]))

summary = []
for g in groups:
    rows = g["rows"]
    el = sorted(r["e"] for r in rows)
    n = len(rows)
    fail = sum(r["success"] != "true" for r in rows)
    t0 = min(r["t"] for r in rows)
    t1 = max(r["t"] + r["e"] for r in rows)
    within = sum(r["success"] == "true" and r["e"] <= 40 for r in rows)
    # steady state = after ramp-up, before the last second (tail threads finishing)
    lo, hi = t0 + g["ramp"] * 1000, t1 - 1000
    steady = sum(lo <= r["t"] + r["e"] < hi for r in rows) / ((hi - lo) / 1000) if g["kind"] == "sat" else ""
    s = dict(测试项目="JPA" + g["op"] + ("(吞吐上限)" if g["kind"] == "sat" else ""), 线程数=g["threads"], 循环次数=g["loops"], 请求数=n, 失败数=fail,
             平均响应毫秒=round(sum(el) / n, 2), 中位数毫秒=round(pct(el, .5), 2), P95毫秒=round(pct(el, .95), 2),
             P99毫秒=round(pct(el, .99), 2), 最大毫秒=el[-1], 四十毫秒内成功比例=round(within / n * 100, 2),
             吞吐量每秒=round(n / ((t1 - t0) / 1000), 2),
             稳态吞吐量每秒=round(steady, 2) if steady != "" else "")
    g["s"] = s
    summary.append(s)

os.makedirs(f"{pkg}/数据统计", exist_ok=True)
with open(f"{pkg}/数据统计/测试结果汇总.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0]))
    w.writeheader()
    w.writerows(summary)
json.dump(summary, open(f"{figdir}/summary.json", "w"), ensure_ascii=False, indent=1)


def fig_latency(op, out, title):
    gs = [g for g in groups if g["op"] == op and g["kind"] == "base"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"wspace": 0.28})
    xmax = 0
    for i, g in enumerate(gs):
        el = sorted(r["e"] for r in g["rows"])
        n = len(el)
        y = [(k + 1) / n * 100 for k in range(n)]
        a1.step(el, y, where="post", color=PALETTE[i], label=f"{g['threads']} 线程")
        xmax = max(xmax, pct(el, .995))
        t0 = min(r["t"] for r in g["rows"])
        buckets = {}
        for r in g["rows"]:
            buckets.setdefault((r["t"] - t0) // 1000, []).append(max(r["e"] - r["c"], 0))
        xs = sorted(buckets)
        a2.plot(xs, [sum(buckets[x]) / len(buckets[x]) for x in xs], color=PALETTE[i],
                marker="o", markersize=3, label=f"{g['threads']} 线程")
    a1.axvline(40, color=MUTED, ls="--", lw=0.9)
    a1.axhline(80, color=MUTED, ls="--", lw=0.9)
    a1.set_xlim(0, max(60, xmax * 1.05))
    a1.set_ylim(0, 101)
    a1.set_xlabel("响应时间 elapsed (ms)")
    a1.set_ylabel("请求累计百分比 (%)")
    a1.set_title("响应时间累计分布", color=INK2, fontsize=9.5)
    a2.set_xlabel("距首个请求的秒数 (s)")
    a2.set_ylabel("平均 elapsed - Connect (ms)")
    a2.set_title("每秒平均响应", color=INK2, fontsize=9.5)
    a2.set_ylim(bottom=0)
    a1.legend(loc="lower right", fontsize=8)
    fig.suptitle(title, color="#0b0b0b", fontsize=10.5, y=1.0)
    fig.savefig(f"{figdir}/{out}", dpi=200, bbox_inches="tight")
    plt.close(fig)


fig_latency("读取", "fig_read.png", "JPA 读取：10 秒升压、每线程 2 次循环")
fig_latency("写入", "fig_write.png", "JPA 写入：10 秒升压、每线程 1 次循环")

# throughput-limit groups: steady throughput and latency vs threads, read and write on one axis each
sat = [g for g in groups if g["kind"] == "sat"]
if sat:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"wspace": 0.3})
    for i, op in enumerate(("读取", "写入")):
        gs = [g for g in sat if g["op"] == op]
        xs = [g["threads"] for g in gs]
        a1.plot(xs, [g["s"]["稳态吞吐量每秒"] for g in gs], color=PALETTE[i], marker="o", markersize=4, label=op)
        a2.plot(xs, [g["s"]["平均响应毫秒"] for g in gs], color=PALETTE[i], marker="o", markersize=4, label=f"{op} 均值")
        a2.plot(xs, [g["s"]["P95毫秒"] for g in gs], color=PALETTE[i], marker="s", markersize=4, ls="--", label=f"{op} P95")
        for g in gs:
            a1.annotate(f"{g['s']['稳态吞吐量每秒']:.0f}", (g["threads"], g["s"]["稳态吞吐量每秒"]),
                        textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7.5, color=INK2)
    a1.set_xlabel("并发线程数")
    a1.set_ylabel("稳态吞吐量 (请求/秒)")
    a1.set_title("吞吐量", color=INK2, fontsize=9.5)
    a1.set_ylim(0, max(g["s"]["稳态吞吐量每秒"] for g in sat) * 1.18)
    a2.set_xlabel("并发线程数")
    a2.set_ylabel("响应时间 (ms)")
    a2.set_title("响应时间", color=INK2, fontsize=9.5)
    a2.set_ylim(bottom=0)
    a1.legend(loc="lower right", fontsize=8)
    a2.legend(loc="upper left", fontsize=7.5)
    for a in (a1, a2):
        a.set_xticks([g["threads"] for g in sat if g["op"] == "读取"])
    fig.savefig(f"{figdir}/fig_capacity.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

# monitoring: peak in-window CPU per node for every group, and a figure for the heaviest write group
peaks = []
for f in sorted(glob.glob(f"{pkg}/原始数据/03_Prometheus监控/*.json")):
    m = json.load(open(f, encoding="utf-8"))
    t = m["测试参数"]
    row = {"组": os.path.basename(f).replace("_监控.json", "")}
    for s in m["补充_CPU瞬时使用率"]["response"]["data"]["result"]:
        vals = [float(v[1]) for v in s["values"] if t["start"] <= float(v[0]) <= t["end"] + 2]
        row[t["节点"][s["metric"]["instance"]]] = round(max(vals), 1)
        mid = [float(v[1]) for v in s["values"] if t["start"] + t["ramp"] <= float(v[0]) <= t["end"] - 1]
        row[t["节点"][s["metric"]["instance"]] + "_稳态均值"] = round(sum(mid) / len(mid), 1) if mid else None
    th = m["活跃线程"]["response"]["data"]["result"][0]["values"]
    row["JVM线程"] = sorted({int(float(v[1])) for v in th if t["start"] <= float(v[0]) <= t["end"] + 2})
    peaks.append(row)
json.dump(peaks, open(f"{figdir}/cpu_peaks.json", "w"), ensure_ascii=False, indent=1)

mon = sorted(glob.glob(f"{pkg}/原始数据/03_Prometheus监控/*写入_1300*.json"))
m = json.load(open(mon[0], encoding="utf-8"))
start, end, hosts = m["测试参数"]["start"], m["测试参数"]["end"], m["测试参数"]["节点"]
order = ["compiler(压测)", "course-node2(应用)", "course-node1(数据库)", "manager(监控)"]
fig, axes = plt.subplots(4, 1, figsize=(7.2, 7.0), sharex=True, gridspec_kw={"hspace": 0.32})
panels = [("活跃线程", "JVM 活跃线程数", False), ("CPU使用率", "CPU 使用率 (%)\n记录规则 rate 5m", True),
          ("补充_CPU瞬时使用率", "CPU 使用率 (%)\nirate 10s（补充）", True), ("内存使用率", "内存使用率 (%)", True)]
for ax, (key, ylab, per_node) in zip(axes, panels):
    for s in m[key]["response"]["data"]["result"]:
        lab = hosts.get(s["metric"].get("instance"), "productdemoaop") if per_node else "productdemoaop"
        if per_node and lab not in order:
            continue
        xs = [float(v[0]) - start for v in s["values"]]
        ax.plot(xs, [float(v[1]) for v in s["values"]], color=PALETTE[order.index(lab) if per_node else 0], label=lab)
    ax.axvspan(0, end - start, color="#e1e0d9", alpha=0.45, lw=0)
    ax.set_ylabel(ylab, fontsize=8.5)
    if key == "补充_CPU瞬时使用率":
        ax.set_ylim(0, 100)
h, l = axes[1].get_legend_handles_labels()
hl = sorted(zip(h, l), key=lambda x: order.index(x[1]))
fig.legend([x[0] for x in hl], [x[1] for x in hl], loc="upper center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, 0.94))
axes[0].legend(loc="upper right", fontsize=8)
axes[-1].set_xlabel("距首个请求的秒数 (s)，灰色区间为压测进行中")
fig.savefig(f"{figdir}/fig_monitor.png", dpi=200, bbox_inches="tight")
plt.close(fig)
for r in peaks:
    print(r)

for s in summary:
    print(s)
