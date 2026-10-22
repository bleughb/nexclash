; nextbench.asm v3 - what Next techniques cost, at several sizes, set up / reused / torn down, and
; what the copper does (GPL-3.0-or-later, part of nexclash). Build: python tools/hwtests/build.py
; nextbench (build.py first runs nextbench_gen.py, which writes nextbench_cases.inc: the 88 rows).
;
; A timing row = one routine CALLed R times in a row; its time per call is measured on the raster
; line counter and printed in MICROSECONDS PER CALL at 3.5 MHz and at 28 MHz (the hooks' speed).
; R is chosen per row and speed: a probe run sizes it so a measurement fills ~140 lines (R = 1 for
; anything over ~10 lines a call; a row whose single call does not fit a frame shows ">").
; Method as z80ntest / v1 (board-proven): frame start, 0..3 quarter-line delay, R calls, read the
; line; 4 passes added; the same with an empty routine and the same R subtracted; calibrated against
; 2048 x LD A,(IX+0) at 3.5 MHz (38,912 T = 11,117.7 us). Rows with a set-up routine (DMA rtg / rrun:
; a full DMA program first; LDIR+COP: the copper running a MOVE loop) run it before both
; measurements and the tear-down after.
;
; Sizes: copies / fills / uploads at 1 B .. 2 KB (column 2). DMA rows: full program each call;
; "rtg" = only addresses + length rewritten (ports kept); "rrun" = LOAD + ENABLE only (the same
; transfer again); "brst" = burst mode. Copper: COP NR / COP IO = load n instructions (stopped) by
; NEXTREG $60 / by OUT $253B; COPGO+ST = start + stop; LDIR+COP = LDIR 256 while the copper runs.
; Copper function rows (value = a number, not a time):
;   CP WAIT  - copper list WAIT line 120 / MOVE $7F,$AA / HALT started at frame start: the raster
;              line ($1E/$1F) at which the CPU first sees $7F = $AA (">" = never, ~1 s).
;   CP APART - the copper loops MOVE $7F (a register the CPU does not use) while the CPU writes 256
;              palette entries ($40 / $41, sprite palette 2) and reads them back: wrong entries
;              (expected 0; "!" otherwise).
;   CP SHARE - the same with the copper looping MOVE $40 (the palette INDEX the CPU uses): wrong
;              entries expected (TECHNIQUES 1: never drive one register pair from both) - info.
; Copies / fills are checked after each row: "!" = wrong result (e.g. DMA at 3.5 MHz on cores before
; 3.02.02).
;
; v3: the whole table runs NRUNS times (~1 minute each, blue border, "RUN n/N" on screen). R is
; chosen in run 1 and kept, so every run measures the same thing. The pages show the mean over the
; runs; "~" after a value = its runs differ by more than rounding to whole raster lines can explain
; (chi-square test on the per-run line counts, false-flag chance at most 0.1 % per value:
; nextbench_gen.py sigthr). The last page(s) list every "~" row with its smallest and largest run, and the
; calibration of each run. Copper function rows: "~" = any run differs. Any key flips the pages.
; Border: red = a "!" somewhere, else yellow = a "~" somewhere, else green.
;
; Results at RESULTS ($7A00): "NXB3", version, count, calibration lines summed over the runs (word),
; then per row 10 bytes: mean value at 3.5 MHz (dword, tenths of us or of the number), at 28 MHz
; (dword), R at 3.5 / 28 MHz; then per row a flag byte: bit 0 / 1 = check failed at 3.5 / 28 MHz (any
; run), bit 2 / 3 = did not fit, bit 4 / 5 = varies between runs. RAWRUN ($6200): NRUNS, 0, the
; calibration lines of each run (NRUNS words); RAW ($6210): per row, per speed, per run the line
; count d (word; copper function rows: the number itself).

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

RESULTS     equ $7A00
RAWRUN      equ $6200           ; bank 5 above the screen; TILE ENT writes $6000-$6001 only
RAW         equ $6210
SIGL        equ $6A00           ; varying (row, speed) pairs, 2 bytes each
RLEN        equ 10
STACK       equ $BFE0
FONT        equ $B800           ; RAM copy of the ROM font (rows switch ROMs through 0x7FFD)
SRC         equ $C000           ; 4K source pattern ((i*7+3) & 0x7F: never $E3)
DST         equ $D000           ; 4K destination
COPZ        equ $F200           ; 512 zero bytes (copper NOP lists, sprite hide records)
NPAGE       equ 21
TLEN        equ 20              ; table entry: routine, set-up, tear-down, kind, check, n, size, name(8)
TARGET      equ 140             ; lines a measurement should fill

        org $8000
start:  di
        ld sp,STACK
        nextreg $07,0
        ld hl,$3D00 : ld de,FONT : ld bc,768 : ldir
        ld hl,SRC : ld bc,4096 : ld e,0
.src:   ld a,e : add a,a : add a,a : add a,a : sub e : add a,3 : and $7F : ld (hl),a
        inc hl : inc e : dec bc : ld a,b : or c : jr nz,.src
        ld hl,COPZ : ld de,COPZ+1 : ld bc,511 : ld (hl),0 : ldir
        ld hl,RESULTS
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'B' : inc hl : ld (hl),'3' : inc hl
        ld (hl),3 : inc hl : ld (hl),NTESTS
        ld hl,RESULTS+6 : ld de,RESULTS+7 : ld bc,2+NTESTS*(RLEN+1)-1 : ld (hl),0 : ldir
        ld hl,RAWRUN : ld de,RAWRUN+1 : ld bc,RAW-RAWRUN+NTESTS*2*NRUNS*2-1 : ld (hl),0 : ldir
        ld a,NRUNS : ld (RAWRUN),a
        ld hl,0 : ld (ksum),hl
        xor a : ld (run),a
.run:   call resetregs
        call cls
        ld a,1 : out ($FE),a
        xor a : ld (crow),a : ld (ccol),a
        ld hl,trun : call puts
        ld a,(run) : inc a : call dec1 : ld a,'/' : call putc : ld a,NRUNS : call dec1
        xor a : ld (spd),a : ld (npass),a
        ld ix,SRC
        ld a,8 : ld hl,t_ref : call measure : push hl
        ld a,8 : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de
        ex de,hl
        ld a,(run) : add a,a : ld l,a : ld h,0 : ld bc,RAWRUN+2 : add hl,bc
        ld (hl),e : inc hl : ld (hl),d
        ld hl,(ksum) : add hl,de : ld (ksum),hl
        ld iy,tests : ld a,1 : ld (tno),a
.t:     ld a,(iy+0) : or (iy+1) : jr z,.rdone
        xor a : call one
        ld a,1 : call one
        nextreg $07,0
        ld de,TLEN : add iy,de
        ld a,(tno) : inc a : ld (tno),a
        jr .t
.rdone: ld a,(run) : inc a : ld (run),a : cp NRUNS : jp c,.run
        call resetregs
        ld hl,(ksum) : ld (RESULTS+6),hl
        call finish
        ld a,4 : ld (bcol),a
        ld hl,RESULTS+8+NTESTS*RLEN : ld b,NTESTS
.bf:    ld a,(hl) : and $30 : jr z,.bv
        ld a,6 : ld (bcol),a
.bv:    inc hl : djnz .bf
        ld hl,RESULTS+8+NTESTS*RLEN : ld b,NTESTS
.bf2:   ld a,(hl) : and 3 : jr z,.bn
        ld a,2 : ld (bcol),a
.bn:    inc hl : djnz .bf2
        ld hl,(nsig) : ld de,NPS-1 : add hl,de : ld c,NPS : call div16_8
        ld a,l : or a : jr nz,.np
        inc a
.np:    ld (nspg),a : add a,NPAGES : ld (npg),a
        xor a : ld (pg),a
.pages: ld a,(pg) : cp NPAGES : jr nc,.sp
        call page : jr .key
.sp:    call spage
.key:   call key
        ld a,(npg) : ld b,a
        ld a,(pg) : inc a : cp b : jr c,.p2
        xor a
.p2:    ld (pg),a
        jr .pages
NPAGES  equ (NTESTS+NPAGE-1)/NPAGE
NPS     equ 19                  ; varying rows per statistics page

resetregs:
        nextreg $07,0 : nextreg $62,0
        nextreg $2F,0 : nextreg $30,0 : nextreg $16,0 : nextreg $17,0 : nextreg $43,0
        ld bc,$7FFD : ld a,$10 : out (c),a
        ret

; ---------------------------------------------------------------- one row at one speed
; A = 0 (3.5 MHz) / 1 (28 MHz); IY = the row's table entry
one:    ld (spd),a
        or a : jr z,.s
        nextreg $07,3
.s:     ld hl,DST : ld de,DST+1 : ld bc,4095 : ld (hl),0 : ldir
        ld a,(iy+6) : or a : jp nz,special
        ld a,(run) : or a : jr z,.r0
        call flagad : ld a,(spd) : add a,a : add a,a : add a,4 : and (hl) : ret nz   ; did not fit
        call slot : ld a,(spd) : ld e,a : ld d,0 : add hl,de : ld de,8 : add hl,de
        ld a,(hl) : ld (rr),a           ; R of run 1
        ld l,(iy+2) : ld h,(iy+3) : ld a,h : or l : call nz,jphl     ; set-up
        ld l,(iy+0) : ld h,(iy+1) : ld (trow),hl
        jp .meas
.r0:    ld l,(iy+2) : ld h,(iy+3) : ld a,h : or l : call nz,jphl     ; set-up
        ld l,(iy+0) : ld h,(iy+1) : ld (trow),hl
        ld a,1 : ld (npass),a           ; probe: one pass, R = 1
        ld a,1 : call measure
        ld a,h : or a : jp nz,.long
        ld a,l : cp 230 : jp nc,.long
        cp 10 : jr c,.small              ; (the probe includes ~3 lines of fixed overhead)
        ld c,a : ld hl,TARGET : call div16_8   ; R = TARGET / lines (>= 1)
        ld a,l : or a : jr nz,.r
        inc a : jr .r
.small: ld a,8 : ld hl,(trow) : call measure   ; 8 calls (< 10 lines each: <= ~83 lines)
        ld a,h : or a : jr nz,.m8
        ld a,l : cp 20 : jr c,.tiny
.m8:    ld c,l : ld hl,8*TARGET : call div16_8   ; R = 8 * TARGET / lines of 8
        ld a,l : jr .r1
.tiny:  ld a,64 : ld hl,(trow) : call measure  ; < ~2 lines a call: 64 calls fit (<= ~140 lines)
        inc hl : ld c,l : ld a,h : or a : jr z,.s8 ; R = 64 * TARGET / (lines of 64 + 1), max 255
        ld c,255
.s8:    ld hl,64*TARGET : call div16_8
        ld a,h : or a : ld a,l : jr z,.r1
        ld a,255
.r1:    or a : jr nz,.r
        inc a
.r:     ld (rr),a
        call slot : ld a,(spd) : ld e,a : ld d,0 : add hl,de : ld de,8 : add hl,de
        ld a,(rr) : ld (hl),a
.meas:  xor a : ld (npass),a            ; 4 passes
        ld a,(rr) : ld hl,(trow) : call measure : push hl
        ld a,(rr) : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de : jr nc,.p
        ld hl,0
.p:     call tdown
        call putraw                     ; d = lines of the row - lines of the empty routine
        call check : ret z
        ld a,(spd) : inc a : jr flag
.long:  call tdown
        call slot : ld a,(spd) : ld e,a : ld d,0 : add hl,de : ld de,8 : add hl,de
        ld (hl),1
        ld a,(spd) : add a,a : add a,a : add a,a : add a,4 : jr flag   ; bit 2 / 3

; A = flag bits -> or into the row's flag byte
flag:   push af
        call flagad
        pop af : or (hl) : ld (hl),a
        ret
flagad: ld a,(tno) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        ret
; HL = the row's 10-byte result slot
slot:   ld a,(tno) : dec a : ld l,a : ld h,0 : ld d,h : ld e,l
        add hl,hl : add hl,hl : add hl,de : add hl,hl          ; * 10
        ld de,RESULTS+8 : add hl,de
        ret
; HL = RAW entry of run 0 for (tno), (spd)
rawad:  ld a,(tno) : dec a : add a,a : ld l,a : ld a,(spd) : add a,l : ld l,a : ld h,0
        ld d,h : ld e,l : ld b,NRUNS-1
.m:     add hl,de : djnz .m
        add hl,hl : ld de,RAW : add hl,de
        ret
; HL = d -> RAW entry of (tno), (spd), (run)
putraw: push hl
        call rawad : ld a,(run) : add a,a : ld e,a : ld d,0 : add hl,de
        pop de : ld (hl),e : inc hl : ld (hl),d
        ret
tdown:  push hl
        ld l,(iy+4) : ld h,(iy+5) : ld a,h : or l : call nz,jphl
        pop hl : ret

; DEHL = value (tenths) -> the row's slot for this speed
store:  push de : push hl
        ld a,(tno) : dec a : ld l,a : ld h,0 : ld d,h : ld e,l
        add hl,hl : add hl,hl : add hl,de : add hl,hl          ; * 10
        ld de,RESULTS+8 : add hl,de
        ld a,(spd) : or a : jr z,.w
        ld de,4 : add hl,de
.w:     pop de : ld (hl),e : inc hl : ld (hl),d : inc hl
        pop de : ld (hl),e : inc hl : ld (hl),d : inc hl
        ret

; kind 1: the routine returns HL = a number, A = flag (0 / 1 wrong / 2 never); the number -> RAW
special:
        ld l,(iy+0) : ld h,(iy+1) : call jphl
        push af
        call putraw
        call slot : ld a,(spd) : ld e,a : ld d,0 : add hl,de : ld de,8 : add hl,de
        ld (hl),1
        pop af : or a : ret z
        cp 2 : jr z,.nf
        ld a,(spd) : inc a : jp flag
.nf:    ld a,(spd) : add a,a : add a,a : add a,a : add a,4 : jp flag

; ---------------------------------------------------------------- after the runs
; per row and speed: the mean (-> the result slot), the variation test (-> flag bit 4 / 5, SIGL)
finish: ld hl,0 : ld (nsig),hl
        ld iy,tests : ld a,1 : ld (tno),a
.t:     xor a : call .one
        ld a,1 : call .one
        ld de,TLEN : add iy,de
        ld a,(tno) : inc a : cp NTESTS+1 : ld (tno),a : jr c,.t
        ret
.one:   ld (spd),a
        call flagad : ld a,(spd) : add a,a : add a,a : add a,4 : and (hl) : ret nz   ; did not fit
        call scan
        ld hl,(ssum) : call tenths : call store
        call sig : ret nc
        ld a,(spd) : inc a : add a,a : add a,a : add a,a : add a,a : call flag   ; bit 4 / 5
        ld hl,(nsig) : push hl : add hl,hl : ld de,SIGL : add hl,de
        ld a,(tno) : ld (hl),a : inc hl : ld a,(spd) : ld (hl),a
        pop hl : inc hl : ld (nsig),hl
        ret
; HL = lines summed over the runs (or one run's lines x NRUNS) -> DEHL = tenths per call (mean)
tenths: ld a,(iy+6) : or a : jr nz,.num
        ld de,55589 : ld b,h : ld c,l : call mul16    ; DEHL = lines * 55589
        add hl,hl : rl e : rl d                        ; * 2 = lines * 111178
        ld bc,(ksum) : call div32                      ; / calibration lines (summed alike)
        push de : push hl : call slot : ld a,(spd) : ld e,a : ld d,0 : add hl,de : ld de,8 : add hl,de
        ld c,(hl) : ld b,0 : pop hl : pop de : jp div32   ; / R
.num:   ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de : add hl,hl   ; * 10 (< 65536)
        ld de,0 : ld c,NRUNS : jp div8                 ; mean of the number, tenths
; (tno), (spd) -> ssum, ssq (dword: sum of squares), smin, smax of the runs' RAW words
scan:   ld hl,0 : ld (ssum),hl : ld (ssq),hl : ld (ssq+2),hl : ld (smax),hl
        dec hl : ld (smin),hl
        call rawad : ld b,NRUNS
.l:     ld e,(hl) : inc hl : ld d,(hl) : inc hl
        push hl : push bc
        ld hl,(ssum) : add hl,de : ld (ssum),hl
        ld hl,(smin) : or a : sbc hl,de : jr c,.n1
        ld (smin),de
.n1:    ld hl,(smax) : or a : sbc hl,de : jr nc,.n2
        ld (smax),de
.n2:    ld b,d : ld c,e : call mul16                   ; d * d
        ld bc,(ssq) : add hl,bc : ld (ssq),hl
        ex de,hl : ld bc,(ssq+2) : adc hl,bc : ld (ssq+2),hl
        pop bc : pop hl : djnz .l
        ret
; after scan -> carry set if the runs differ significantly: NRUNS * sum (d - mean)^2 =
; NRUNS * ssq - ssum^2 >= SIGTHR (copper function rows: >= 1, any difference)
sig:    ld hl,(ssq) : ld de,(ssq+2) : ld b,NRUNS-1
.m:     push bc
        ld bc,(ssq) : add hl,bc : ex de,hl : ld bc,(ssq+2) : adc hl,bc : ex de,hl
        pop bc : djnz .m
        ld (t32),hl : ld (t32+2),de                   ; NRUNS * ssq
        ld bc,(ssum) : ld de,(ssum) : call mul16       ; DEHL = ssum^2
        ld b,d : ld c,e : ex de,hl
        ld hl,(t32) : or a : sbc hl,de : ex de,hl
        ld hl,(t32+2) : sbc hl,bc                      ; HL:DE = NRUNS * sum of squared deviations
        ld a,h : or l : scf : ret nz
        ex de,hl
        ld bc,SIGTHR : ld a,(iy+6) : or a : jr z,.c
        ld bc,1
.c:     or a : sbc hl,bc : ccf
        ret

; check (IY+7): 0 none, 1 DST = SRC for n bytes, 2 DST = $55 for n bytes -> Z if OK
check:  ld a,(iy+7) : or a : ret z
        ld c,(iy+8) : ld b,(iy+9)
        ld hl,DST : ld de,SRC
        cp 2 : jr z,.f
.c:     ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : dec bc : ld a,b : or c : jr nz,.c
        ret
.f:     ld a,(hl) : cp $55 : ret nz
        inc hl : dec bc : ld a,b : or c : jr nz,.f
        ret

; ---------------------------------------------------------------- measuring
; HL = routine, A = R -> HL = raster lines added over the passes ((npass) = 1: one pass, else 4)
measure:
        ld (trout),hl : ld (tr),a
        push iy
        ld hl,0 : ld (tsum),hl : xor a : ld (tpass),a
.pass:  call frame_sync
        ld a,(tpass) : add a,a : add a,a : inc a : ld b,a
        ld a,(spd) : or a : jr z,.dl
        ld a,b : add a,a : add a,a : add a,a : ld b,a
.dl:    djnz .dl
        ld a,(tr) : ld (tcnt),a
.l:     ld hl,(trout) : call jphl
        ld a,(tcnt) : dec a : ld (tcnt),a : jr nz,.l
        call line
        ld de,(tsum) : add hl,de : ld (tsum),hl
        ld a,(npass) : or a : jr nz,.one
        ld a,(tpass) : inc a : ld (tpass),a : cp 4 : jr nz,.pass
.one:   pop iy
        ld hl,(tsum)
        ret
jphl:   jp (hl)

; HL = the raster line at the first IN (a fixed time after the call). v3: v2 read the pair until
; two reads agreed; a read takes ~150 T at 3.5 MHz (a line is 224 T), so it retried 0-3 times and
; returned a line 0-3 lines late, by phase (seen in the simulator: one row's 5 runs 417 / 421 lines).
; The MSB only changes where the LSB wraps to 0, so a second LSB read not below the first proves H
; belongs to L; otherwise (only at lines 255 -> 256 and 311 -> 0) read again.
line:   push bc
.again: ld bc,$243B : ld a,$1F : out (c),a : inc b : in l,(c)
        dec b : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c)
        cp l : jr c,.again
        pop bc : ret
frame_sync:
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.a:     in a,(c) : and 1 : jr z,.a
        dec b : ld a,$1F : out (c),a : inc b
.b:     in a,(c) : cp 2 : jr c,.b
.c:     in a,(c) : or a : jr nz,.c
        ret

; ---------------------------------------------------------------- set-up / tear-down helpers
dmaset: ld hl,dc256 : ld bc,(16 << 8) | $6B : otir : ret      ; a full DMA program (ports set)
copnops:                                                       ; copper list of NOPs, stopped
        nextreg $62,0 : nextreg $61,0
        ld hl,COPZ : ld de,512
.l:     ld a,(hl) : nextreg $60,a : inc hl : dec de : ld a,d : or e : jr nz,.l
        nextreg $61,0 : ret
copmove7f:                                                     ; copper looping MOVE $7F,$55
        ld a,$7F : ld e,$55
coploop:                                                       ; A = register, E = value: 1024 MOVEs, start
        ld d,a
        nextreg $62,0 : nextreg $61,0 : ld bc,1024
.l:     ld a,d : nextreg $60,a : ld a,e : nextreg $60,a
        dec bc : ld a,b : or c : jr nz,.l
        nextreg $61,0 : nextreg $62,%01000000
        ret
copstop:
        nextreg $62,0 : ret

; ---------------------------------------------------------------- copper function rows
; CP WAIT: -> HL = line where $7F = $AA was first seen, A = 0, or A = 2 (never)
cp_wait:
        nextreg $62,0 : nextreg $7F,0 : nextreg $61,0
        nextreg $60,$80 : nextreg $60,120           ; WAIT line 120, h 0
        nextreg $60,$7F : nextreg $60,$AA           ; MOVE $7F,$AA
        nextreg $60,$FF : nextreg $60,$FF           ; HALT
        nextreg $61,0
        call frame_sync
        nextreg $62,%01000000
        ld de,0
.p:     ld bc,$243B : ld a,$7F : out (c),a : inc b : in a,(c) : cp $AA : jr z,.got
        dec de : ld a,d : or e : jr nz,.p
        nextreg $62,0 : ld hl,0 : ld a,2 : ret
.got:   call line
        nextreg $62,0 : xor a : ret
; CP APART / SHARE: A = the register the copper loops a MOVE to, E = its value, D = 1 if wrong
; entries are expected (info row) -> HL = wrong palette entries of 256, A = 0 / 1 ("!")
cp_pal: push de
        call coploop
        nextreg $43,%01100000                        ; sprite palette 2, auto-increment
        nextreg $40,0
        ld e,0
.w:     ld a,e : xor $5A : nextreg $41,a : inc e : jr nz,.w
        ld hl,0 : ld e,0
.r:     ld a,e : nextreg $40,a
        ld bc,$243B : ld a,$41 : out (c),a : inc b : in a,(c)
        ld d,a : ld a,e : xor $5A : cp d : jr z,.ok
        inc hl
.ok:    inc e : jr nz,.r
        nextreg $62,0 : nextreg $43,0
        pop de
        ld a,d : or a : ld a,0 : ret nz               ; info row: never flagged
        ld a,h : or l : ret z
        ld a,1 : ret

; ---------------------------------------------------------------- arithmetic (plain Z80)
mul16:  ld hl,0 : ld a,16                              ; BC * DE -> DEHL
.l:     add hl,hl : rl e : rl d : jr nc,.n
        add hl,bc : jr nc,.n
        inc de
.n:     dec a : jr nz,.l
        ret
div32:  ld a,32                                        ; DEHL / BC -> DEHL
        push hl : ld hl,0 : ld (rem),hl : pop hl
.l:     add hl,hl : rl e : rl d
        push hl
        ld hl,(rem) : adc hl,hl : jr c,.big
        or a : sbc hl,bc : jr nc,.ok
        add hl,bc : ld (rem),hl : pop hl : jr .n
.big:   or a : sbc hl,bc
.ok:    ld (rem),hl : pop hl : inc l
.n:     dec a : jr nz,.l
        ret
div8:   xor a : ld b,32                                ; DEHL / C -> DEHL, A = remainder
.l:     add hl,hl : rl e : rl d : rla
        cp c : jr c,.n
        sub c : inc l
.n:     djnz .l
        ret
div16_8:                                               ; HL / C -> HL
        xor a : ld b,16
.l:     add hl,hl : rla : cp c : jr c,.n
        sub c : inc l
.n:     djnz .l
        ret

; ---------------------------------------------------------------- unrolled blocks
t_none: ret
t_ref:
        DUP 256
        ld a,(ix+0)
        EDUP
        ret
ldiblk:
        DUP 256
        ldi
        EDUP
ldiblk_end:
        ret
outiblk:
        DUP 256
        outi
        EDUP
outiblk_end:
        ret
pushblk:
        DUP 128
        push hl
        EDUP
pushblk_end:
        jp (ix)

fillb:  db $55
attr32: DUP 32
        db 32, 32, 0, 0
        EDUP

        INCLUDE "nextbench_cases.inc"

; ---------------------------------------------------------------- screen
page:   call ptitle
        ld a,1 : ld (crow),a : xor a : ld (ccol),a
        ld hl,hdr : call puts
        ld a,(pg) : ld b,a : ld a,1 : inc b
.pf:    dec b : jr z,.pe
        add a,NPAGE : jr .pf
.pe:    ld (pt),a
        ld a,3 : ld (crow),a : ld a,NPAGE : ld (pn),a
.e:     ld a,(pt) : dec a : cp NTESTS : ret nc
        xor a : ld (ccol),a
        ld a,(pt) : dec a : ld l,a : ld h,0
        add hl,hl : add hl,hl : ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de   ; * 20
        ld de,tests : add hl,de : push hl : pop ix
        push ix : pop hl : ld de,12 : add hl,de
        ld b,8
.n:     ld a,(hl) : call putc : inc hl : djnz .n
        ld l,(ix+10) : ld h,(ix+11)                    ; size
        ld a,h : or l : jr nz,.sz
        ld b,4
.sp:    ld a,' ' : call putc : djnz .sp
        jr .vals
.sz:    call pnum4
.vals:  ld a,(pt) : dec a : ld l,a : ld h,0 : ld d,h : ld e,l
        add hl,hl : add hl,hl : add hl,de : add hl,hl
        ld de,RESULTS+8 : add hl,de
        push hl : ld a,1 : call pval : pop hl
        ld de,4 : add hl,de : ld a,2 : call pval
        ld a,(crow) : inc a : ld (crow),a
        ld a,(pt) : inc a : ld (pt),a
        ld a,(pn) : dec a : ld (pn),a : jr nz,.e
        ret
ptitle: call cls
        ld a,(bcol) : out ($FE),a
        xor a : ld (crow),a : ld (ccol),a
        ld hl,title : call puts
        ld a,$01 : call rdreg : push af
        rrca : rrca : rrca : rrca : and 15 : add a,'0' : call putc
        ld a,'.' : call putc
        pop af : and 15 : call dec2
        ld a,'.' : call putc
        ld a,$0E : call rdreg : call dec2
        ld a,' ' : call putc : ld a,'P' : call putc
        ld a,(pg) : inc a : call decn
        ld a,'/' : call putc : ld a,(npg) : jp decn
; HL = a number < 10000 -> 4 characters, right-aligned
pnum4:  ld de,0
        ld ix,dbuf+4 : ld b,4
.c:     dec ix : ld (ix+0),' ' : djnz .c
        ld ix,dbuf+4
.d:     ld c,10 : push ix : call div8 : pop ix
        add a,'0' : dec ix : ld (ix+0),a
        ld a,h : or l : jr nz,.d
        ld hl,dbuf : ld b,4
.o:     ld a,(hl) : call putc : inc hl : djnz .o
        ret
; HL = the value dword (tenths), A = the check bit of this speed: " dddd.d" + "!" / ">" / " "
pval:   ld (fbit),a
        ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        ex de,hl
        call fmt7
        ld a,' ' : call putc
        ld a,(pt) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        ld a,(fbit) : add a,a : add a,a : and (hl) : jr z,.nl    ; bit 2 / 3: did not fit
        ld hl,dlong : jr .o
.nl:    ld hl,dbuf
.o:     ld b,7
.o2:    ld a,(hl) : call putc : inc hl : djnz .o2
        ld a,(pt) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        ld a,(fbit) : and (hl) : ld a,'!' : jr nz,.q
        ld a,(fbit) : add a,a : add a,a : add a,a : add a,a : and (hl) : ld a,'~' : jr nz,.q
        ld a,' '
.q:     jp putc
; DEHL = tenths -> dbuf: 7 characters " dddd.d", right-aligned
fmt7:   ld ix,dbuf+7 : ld b,7
.cl:    dec ix : ld (ix+0),' ' : djnz .cl
        ld ix,dbuf+7
        ld c,10 : push ix : call div8 : pop ix : add a,'0' : dec ix : ld (ix+0),a
        dec ix : ld (ix+0),'.'
.d:     ld c,10 : push ix : call div8 : pop ix : add a,'0' : dec ix : ld (ix+0),a
        ld a,d : or e : or h : or l : ret z
        push ix : pop bc : ld a,c : cp low dbuf : jr nz,.d
        ret
pdbuf:  ld hl,dbuf : ld b,7
.o:     ld a,(hl) : call putc : inc hl : djnz .o
        ret

; ---------------------------------------------------------------- statistics page(s)
; (pg) - NPAGES = which page: the varying rows NPS at a time, each with its smallest and largest run
spage:  call ptitle
        ld a,1 : ld (crow),a : xor a : ld (ccol),a
        ld hl,shd1 : call puts
        ld a,2 : ld (crow),a : xor a : ld (ccol),a
        ld hl,scal : call puts
        ld hl,RAWRUN+2 : ld b,NRUNS
.c:     ld e,(hl) : inc hl : ld d,(hl) : inc hl
        push hl : push bc : ex de,hl : call pnum4 : pop bc : pop hl
        djnz .c
        ld a,3 : ld (crow),a : xor a : ld (ccol),a
        ld hl,shd2 : call puts
        ld hl,(nsig) : ld a,h : or l : jr nz,.list
        ld a,5 : ld (crow),a : xor a : ld (ccol),a : ld hl,snone1 : call puts
        ld a,6 : ld (crow),a : xor a : ld (ccol),a : ld hl,snone2 : jp puts
.list:  ld a,(pg) : sub NPAGES : ld b,a : ld hl,0 : ld de,NPS : inc b
.f:     dec b : jr z,.fe
        add hl,de : jr .f
.fe:    ld (sidx),hl
        ld a,4 : ld (crow),a : ld a,NPS : ld (pn),a
.e:     ld hl,(sidx) : ld de,(nsig) : or a : sbc hl,de : ret nc
        ld hl,(sidx) : add hl,hl : ld de,SIGL : add hl,de
        ld a,(hl) : ld (tno),a : inc hl : ld a,(hl) : ld (spd),a
        ld a,(tno) : dec a : ld l,a : ld h,0
        add hl,hl : add hl,hl : ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de   ; * 20
        ld de,tests : add hl,de : push hl : pop iy
        xor a : ld (ccol),a
        push iy : pop hl : ld de,12 : add hl,de
        ld b,8
.n:     ld a,(hl) : call putc : inc hl : djnz .n
        ld l,(iy+10) : ld h,(iy+11) : ld a,h : or l : jr nz,.sz
        ld hl,s4sp : call puts : jr .mz
.sz:    call pnum4
.mz:    ld hl,s35 : ld a,(spd) : or a : jr z,.m3
        ld hl,s28
.m3:    call puts
        call scan
        ld hl,(smin) : call xn : call tenths : call fmt7 : call pdbuf
        ld hl,(smax) : call xn : call tenths : call fmt7 : call pdbuf
        ld a,(crow) : inc a : ld (crow),a
        ld hl,(sidx) : inc hl : ld (sidx),hl
        ld a,(pn) : dec a : ld (pn),a : jp nz,.e
        ret
; HL = one run's value -> HL x NRUNS (tenths then divides by the run total alike)
xn:     ld d,h : ld e,l : ld b,NRUNS-1
.l:     add hl,de : djnz .l
        ret

cls:    ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),$38 : ldir
        ret
putc:   push hl : push de : push bc
        sub 32 : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,FONT : add hl,de
        ld a,(crow) : and $18 : or $40 : ld d,a
        ld a,(crow) : and 7 : rrca : rrca : rrca : ld e,a
        ld a,(ccol) : or e : ld e,a
        ld b,8
.l:     ld a,(hl) : ld (de),a : inc hl : inc d : djnz .l
        ld a,(ccol) : inc a : ld (ccol),a
        pop bc : pop de : pop hl
        ret
puts:   ld a,(hl) : or a : ret z
        call putc : inc hl : jr puts
dec2:   push bc
        ld b,0
.l:     cp 10 : jr c,.d
        sub 10 : inc b : jr .l
.d:     ld c,a : ld a,b : add a,'0' : call putc : ld a,c : add a,'0' : call putc
        pop bc : ret
dec1:   add a,'0' : jp putc
decn:   cp 10 : jr c,dec1
        jp dec2
rdreg:  push bc : ld bc,$243B : out (c),a : inc b : in a,(c) : pop bc : ret
key:
.r:     xor a : in a,($FE) : cpl : and $1F : jr nz,.r
.p:     xor a : in a,($FE) : cpl : and $1F : jr z,.p
        ret

title:  db "NEXTBENCH v3 core ",0
hdr:    db "us/call size  3.5MHz   28MHz",0
trun:   db "NEXTBENCH v3 RUN ",0
shd1:   db "~ runs differ beyond rounding",0
scal:   db "cal",0
shd2:   db "us/call size MHz    min    max",0
snone1: db "none: every row repeated",0
snone2: db "within its rounding",0
s4sp:   db "    ",0
s35:    db " 3.5",0
s28:    db "  28",0
dlong:  db "      >"
ksum:   dw 0
nsig:   dw 0
sidx:   dw 0
ssum:   dw 0
smin:   dw 0
smax:   dw 0
ssq:    dd 0
t32:    dd 0
run:    db 0
npg:    db 0
nspg:   db 0
spsave: dw 0
trout:  dw 0
trow:   dw 0
tsum:   dw 0
rem:    dw 0
tr:     db 0
tcnt:   db 0
tpass:  db 0
npass:  db 0
spd:    db 0
rr:     db 0
tno:    db 0
bcol:   db 0
pg:     db 0
pt:     db 0
pn:     db 0
crow:   db 0
ccol:   db 0
fbit:   db 0
dbuf:   ds 7

        ASSERT $ <= FONT

; ---------------------------------------------------------------- stack copy, 2048 bytes unrolled
; (bank 0 above the buffers): 256 chunks of 8 bytes in DESCENDING order, so entering at chunk
; n/8 - 1 copies the first n bytes; ends by restoring SP (saved by the row) and returning.
        org $E000
stkblk:
I       = 255
        DUP 256
        ld sp,SRC+I*8 : pop af : pop bc : pop de : pop hl
        ld sp,DST+I*8+8 : push hl : push de : push bc : push af
I       = I-1
        EDUP
        ld sp,(spsave)
        ret
        ASSERT $ <= COPZ

        SAVENEX OPEN "nextbench.nex", start, STACK
        SAVENEX CORE 3,0,0
        SAVENEX CFG 0,0,0,0
        SAVENEX AUTO
        SAVENEX CLOSE
