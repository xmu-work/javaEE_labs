# Runs on compiler (python3.6). Exports 3 required Prometheus queries per test group.
import csv, json, urllib.parse, urllib.request, os
PROM = "http://172.31.13.176:9090/api/v1/query_range"
NODES = {"172.31.4.138:9100": "compiler(压测)", "172.31.8.71:9100": "course-node2(应用)",
         "172.31.6.17:9100": "course-node1(数据库)", "172.31.13.176:9100": "manager(监控)"}
QUERIES = {"活跃线程": "spring:jvm_threads_live_threads", "CPU使用率": "node:cpu_usage_percent",
           "内存使用率": "node:memory_usage_percent"}
os.chdir("/root/lab3-run")
os.makedirs("prom", exist_ok=True)
for op, threads, ramp, loops, start, end in csv.reader(open("groups.csv")):
    start, end = float(start), float(end)
    jtl = "%s-%s-%s-%s.jtl" % (op, threads, ramp, loops)
    rows = list(csv.DictReader(open(jtl, encoding="utf-8")))
    t0 = min(int(r["timeStamp"]) for r in rows) / 1000
    t1 = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows) / 1000
    out = {"测试参数": {"operation": op, "threads": int(threads), "ramp": int(ramp), "loops": int(loops),
                     "samples": len(rows), "errors": sum(r["success"] != "true" for r in rows),
                     "start": t0, "end": t1, "脚本开始": start, "脚本结束": end, "节点": NODES,
                     "step": "2s", "窗口": "首个请求前15秒至最后响应后30秒"}}
    for k, q in QUERIES.items():
        qs = urllib.parse.urlencode({"query": q, "start": t0 - 15, "end": t1 + 30, "step": 2})
        out[k] = {"query": q, "response": json.load(urllib.request.urlopen(PROM + "?" + qs, timeout=10))}
    json.dump(out, open("prom/%s-%s-%s-%s.json" % (op, threads, ramp, loops), "w"), ensure_ascii=False, indent=1)
    print(jtl, len(rows), "ok")
