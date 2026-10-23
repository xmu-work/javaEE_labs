#!/bin/bash
cd /root/lab3-run
: > groups.csv
run(){ s=$(date +%s.%3N); bash jmeter-command.sh $1 $2 10 $3 2>&1 | grep -E "summary =" | tail -1; e=$(date +%s.%3N); echo "$1,$2,10,$3,$s,$e" >> groups.csv; sleep 30; }
for t in 1000 1050 1100 1150 1200; do run ReadProduct $t 2; done
for t in 1000 1100 1200 1300; do run WriteProduct $t 1; done
echo ALL_DONE
