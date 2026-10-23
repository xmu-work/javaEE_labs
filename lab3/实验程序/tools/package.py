"""Build the submission tree. Usage: package.py <pkg_dir> <run_dir>:<set> [<run_dir>:<set> ...]
set "base" = threshold groups (01/02), "sat" = throughput-limit groups (04/05).
Each run_dir holds what was copied back from compiler (jtl, report dirs, prom/, groups.csv)."""
import csv, hashlib, os, shutil, sys

pkg = sys.argv[1]
SUBS = {("base", "ReadProduct"): ("读取", "01_JPA读取"), ("base", "WriteProduct"): ("写入", "02_JPA写入"),
        ("sat", "ReadProduct"): ("读取", "04_JPA读取_吞吐上限"), ("sat", "WriteProduct"): ("写入", "05_JPA写入_吞吐上限")}
index = []
for arg in sys.argv[2:]:
    run, kind = arg.rsplit(":", 1)
    for op, threads, ramp, loops, start, end in csv.reader(open(f"{run}/groups.csv")):
        cn, sub = SUBS[(kind, op)]
        raw = f"{op}-{threads}-{ramp}-{loops}"
        name = f"JPA{cn}_{threads}线程_{ramp}秒升压_{loops}次循环"
        jtl = f"{pkg}/原始数据/{sub}/{name}.jtl"
        mon = f"{pkg}/原始数据/03_Prometheus监控/{name}_监控.json"
        os.makedirs(os.path.dirname(jtl), exist_ok=True)
        os.makedirs(os.path.dirname(mon), exist_ok=True)
        shutil.copyfile(f"{run}/{raw}.jtl", jtl)
        if not os.path.exists(mon):  # keep JSONs already enriched with the supplementary CPU query
            shutil.copyfile(f"{run}/prom/{raw}.json", mon)
        shutil.copytree(f"{run}/{raw}", f"{pkg}/../_reports/{name}", dirs_exist_ok=True)
        rows = list(csv.DictReader(open(jtl, encoding="utf-8")))
        index.append({"测试项目": "JPA" + cn + ("(吞吐上限)" if kind == "sat" else ""), "线程数": threads,
                      "升压秒数": ramp, "循环次数": loops, "请求数": len(rows),
                      "失败数": sum(r["success"] != "true" for r in rows), "原始组名": raw,
                      "原始数据文件": os.path.relpath(jtl, pkg), "监控文件": os.path.relpath(mon, pkg),
                      "网页报告目录": name, "SHA256": hashlib.sha256(open(jtl, "rb").read()).hexdigest()})
with open(f"{pkg}/原始数据/测试组索引.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(index[0]))
    w.writeheader()
    w.writerows(index)
print(len(index), "groups,", sum(r["请求数"] for r in index), "requests,",
      sum(r["失败数"] for r in index), "failures")
