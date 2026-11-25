# Board vs board: nxsuite

Generated (GPL-3.0-or-later, part of nexclash) by
`python tools/hwtests/intake.py --compare docs/kb/hardware/n-go-3.03.00.json docs/kb/hardware/next-ks3-3.03.03.json`.

The N-Go record is run 12 of build 754bd12; the Kickstarter 3 record is one run of build 1f10237 (the two
later build adds the display-rate questions to V19 and moves two visual tests to other pages). Only the claims whose verdict or value differs are listed; every
other claim reads the same on both boards. The V18 answer has differed between runs of the same board, so
its row is not a board difference. V10 (not a claim value here) was answered "split-clean" on the
Kickstarter 3 and a flickering split on the N-Go, and is likewise not repeatable.

```
copper-instruction-time            measured 1.88 | measured 1.96
cpu-contention-bank5-3m5           measured 0.03 | measured -0.01
cpu-io-contention                  measured 10.99 | measured 11.0
cpu-undoc-timings                  measured 8.01 | measured 8.0
dma-hwim2-yield                    confirmed 1211.0 | confirmed 1209.0
dma-prescaler-rate                 measured 3195.36 | measured 3194.72
frame-64-33-l2-top                 operator V18:part-left-part-left | operator V18:part-left-part-right
irq-line-int-position              measured -150.0 | measured -148.0
mem-1ffd-128k-timing               confirmed $DFF3 | confirmed $7463
sys-board-id                       measured 3.03.00 | measured 3.03.03
sys-core-version-regs              measured 3.03.00 | measured 3.03.03
sys-rom3-bytes-386e                measured $EEE2 | measured $FDB1
sys-video-timing-frame-rate        pending-operator  | operator 49.0
13 claims differ between n-go-3.03.00.json (board n-go 3.03.00) and next-ks3-3.03.03.json (board next-ks3 3.03.03)
```
