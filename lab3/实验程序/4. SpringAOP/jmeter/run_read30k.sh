#!/bin/bash
# Read throughput-limit rerun: 30000 requests per group so the post-ramp steady phase lasts ~15 s.
cd /root/lab3-run/sat
run(){ s=$(date +%s.%3N); bash jmeter-command.sh $1 $2 5 $3 2>&1 | grep -E "summary =" | tail -1; e=$(date +%s.%3N); echo "$1,$2,5,$3,$s,$e" >> groups.csv; sleep 30; }
for t in 20 50 100 200; do run ReadProduct $t $((30000 / t)); done
echo ALL_DONE
