# Board vs emulators: nxsuite 4548f5f

Generated (GPL-3.0-or-later, part of nexclash) by
`python tools/hwtests/intake.py --compare docs/kb/hardware/n-go-3.03.00.json docs/kb/hardware/emulator/jnext-1.3.0-3.02.03.json docs/kb/hardware/emulator/cspect-4.5.9.0-50hz-4.00.00.json docs/kb/hardware/emulator/cspect-4.5.9.0-60hz-4.00.00.json`.
All four ran the same build (4548f5f) as RUN ALL; the CSpect 60 Hz column started with 60 Hz set, so its frame figures differ by design. A cell is the verdict and value of that record; `-` = not answered there.

| claim | board n-go 3.03.00 | JNext 1.3.0 3.02.03 | CSpect 4.5.9.0 50Hz 4.00.00 | CSpect 4.5.9.0 60Hz 4.00.00 |
|---|---|---|---|---|
| copper-instruction-time | measured 1.88 | measured 1.93 | measured 0 | measured 0 |
| copper-nextreg-collision | measured 21.75 | measured 25.87 | measured 0 | measured 0 |
| cpu-28-wait-bank5 | measured 4 | measured 4.97 | measured 4 | measured 4 |
| cpu-28-wait-page0f | measured 4 | measured 4.98 | measured 4 | measured 4 |
| cpu-28-wait-reads-only | measured 7.01 | measured 7.99 | measured 7.01 | measured 7.01 |
| cpu-28-wait-sram-fetch | confirmed 4 | measured 5 | confirmed 4 | confirmed 4 |
| cpu-contention-08b6-latch | measured 23 | measured 0 | measured 0 | measured 0 |
| cpu-contention-bank5-3m5 | measured 0.03 | measured 0 | measured 0 | measured 0 |
| cpu-ed7e-im2 | confirmed 5 | confirmed 5 | disproved 0 | disproved 0 |
| cpu-io-contention | measured 11 | measured 11 | measured 11 | measured 10.99 |
| cpu-speed-switch-cost | measured 0 | measured 0 | measured 0.17 | measured 0 |
| cpu-undoc-timings | measured 8.01 | measured 8.01 | measured 4 | measured 3.98 |
| cpu-z80n-tstates-28 | confirmed 31 | measured 0 | confirmed 31 | confirmed 31 |
| dma-blitter-detect | choice blitter | choice none | choice blitter | choice blitter |
| dma-blitter-transparent-fill | confirmed 2.88 | - | confirmed 0 | confirmed 0 |
| dma-burst-cpu-share | confirmed 99.37 | confirmed 100 | disproved 1853200 | disproved 1853200 |
| dma-burst-prescaler-int | confirmed 12 | confirmed 12 | confirmed 13 | confirmed 15 |
| dma-c3-reset-keeps | confirmed 7.68 | confirmed 4.96 | confirmed 0 | confirmed 0 |
| dma-cost-per-byte | disproved 5.92 | disproved 2.88 | - | - |
| dma-default-cycle-length | confirmed 5.92 | disproved 2.88 | - | - |
| dma-hwim2-yield | confirmed 1214 | measured 16384 | confirmed 1207 | confirmed 1205 |
| dma-prescaler-rate | measured 3195.36 | measured 3193.12 | measured 0 | measured 0 |
| dma-pulse-lost | confirmed 0 | confirmed 0 | measured 1 | measured 1 |
| dma-read-status | confirmed $3A | confirmed $3A | disproved $00 | disproved $00 |
| frame-60hz-display-start | confirmed 264 | confirmed 264 | measured 264 | measured 264 |
| frame-64-offset | measured 100 | measured 100 | measured 132 | measured 132 |
| frame-line-length | measured 228.02 | measured 228.02 | measured 0 | measured 0 |
| frame-lines-50 | confirmed 311 | confirmed 311 | measured 311 | measured 264 |
| frame-lines-60 | measured 264 | measured 264 | measured 264 | measured 311 |
| irq-22-bit7-int-low | measured 23 | measured 23 | measured 0 | measured 0 |
| irq-ack-cost | measured 33.46 | measured 33.46 | measured 0 | measured 0 |
| irq-ctc-rate-fixed | confirmed 2216.37 | confirmed 2216.25 | confirmed 0 | confirmed 0 |
| irq-ctc-status-polled | confirmed 16138 | confirmed 16113 | confirmed 8329 | confirmed 42578 |
| irq-ctc-time-constant | choice 16138 | choice 16113 | choice 8329 | choice 42578 |
| irq-hwim2-im1-fallback | choice 2 | choice 2 | choice 0 | choice 0 |
| irq-line-int-numbering | confirmed 5 | disproved 5 | disproved 0 | disproved 0 |
| irq-line-int-position | measured -150 | measured -150 | measured -24 | measured -24 |
| irq-nr20-generate | measured 1 | measured 1 | measured 0 | measured 0 |
| irq-one-outstanding | confirmed 1 | confirmed 1 | measured 0 | measured 0 |
| irq-pulse-bus-ff | confirmed 5 | confirmed 5 | disproved 0 | disproved 0 |
| irq-reti-retn-rules | confirmed 1 | confirmed 1 | measured 1 | measured 1 |
| irq-status-bit-diagnostics | confirmed $01 | confirmed $01 | disproved $FF | disproved $FF |
| irq-ula-int-line | measured 248 | measured 248 | measured 248 | measured 224 |
| lay-l2-default-banks | measured $DE | measured $DE | measured $98 | measured $98 |
| lay-l2-no-cpu-wait | confirmed 20.97 | confirmed 23.97 | confirmed 20.97 | confirmed 20.97 |
| lay-tilemap-reset-bases | measured $DE | measured $DE | measured $98 | measured $98 |
| mem-7ffd-locked | confirmed $00 | confirmed $00 | disproved $06 | disproved $06 |
| mem-high-pages | measured $C0 | measured $FF | measured $5A | measured $5A |
| spr-303b-shared-index | confirmed $01 | disproved $00 | confirmed $01 | confirmed $01 |
| spr-34-vs-303b | confirmed 3 | disproved none | disproved 9 | disproved 9 |
| spr-4bit-attr4-halves | confirmed $01 | disproved $00 | disproved $03 | disproved $03 |
| spr-4byte-records | confirmed $01 | disproved $00 | confirmed $01 | confirmed $01 |
| spr-collision-rules | confirmed $01 | disproved $00 | disproved $01 | disproved $01 |
| spr-line-limit | confirmed 106 | disproved 0 | disproved 1 | disproved 1 |
| spr-nr-postinc | confirmed $01 | disproved $00 | confirmed $01 | confirmed $01 |
| spr-port-low-byte | confirmed $01 | disproved $00 | confirmed $01 | confirmed $01 |
| spr-position-wrap | confirmed $0F | disproved $00 | disproved $1F | disproved $1F |
| spr-relative-accidental | choice relative | choice none | choice both | choice both |
| spr-transparency-before-offset | confirmed $00 | confirmed $00 | disproved $01 | disproved $01 |
| sys-60hz-switch-timing | measured 264 | measured 264 | measured 264 | measured 311 |
| sys-board-id | measured 3.03.00 | measured 3.02.03 | measured 4.00.00 | measured 4.00.00 |
| sys-core-version-regs | measured 3.03.00 | measured 3.02.03 | measured 4.00.00 | measured 4.00.00 |
| sys-launch-7ffd-unlocked | confirmed $DE | confirmed $DE | confirmed $98 | confirmed $98 |
| sys-launch-divmmc-regs | measured $DE | measured $DE | measured $98 | measured $98 |
| sys-launch-nextreg-state | measured $DE | measured $DE | measured $98 | measured $98 |
| sys-rom3-bytes-386e | measured $EEE2 | measured $E2F9 | measured $FD5E | measured $FD5E |
| z80n-add-rr-a-carry | confirmed 0 | confirmed 0 | choice 4 | choice 4 |
| z80n-ed-b6 | choice same-as-LDIRX | choice same-as-LDIRX | choice NOP | choice NOP |
| z80n-func-suite | confirmed $A4 | disproved $A4 | disproved $A5 | disproved $A5 |
| z80n-jpc-flags | confirmed $A5 | confirmed $A5 | disproved $05 | disproved $05 |
| z80n-ldix-flags | confirmed $00 | confirmed $00 | disproved $00 | disproved $00 |
| z80n-ldws-flags | choice ADD-D-1 | choice INC-D | choice INC-D | choice INC-D |

72 claims differ; 29 claims none of the others answered (operator questions not driven, opt-in or skipped tests) are left out. Emulator columns are what that emulator does, not hardware evidence.
