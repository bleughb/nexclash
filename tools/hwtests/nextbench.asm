; nextbench.asm v2 - what Next techniques cost, at several sizes, set up / reused / torn down, and
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
; 3.02.02). Any key flips the pages. Border: green = no "!", red = one or more. ~1 minute (blue).
;
; Results at RESULTS ($7A00): "NXB2", version, count, calibration lines (word), then per row 10
; bytes: value at 3.5 MHz (dword, tenths of us or of the number), at 28 MHz (dword), R at 3.5 / 28
; MHz; then per row a flag byte: bit 0 / 1 = check failed at 3.5 / 28 MHz, bit 2 / 3 = did not fit.

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

RESULTS     equ $7A00
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
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'B' : inc hl : ld (hl),'2' : inc hl
        ld (hl),2 : inc hl : ld (hl),NTESTS
        ld hl,RESULTS+8 : ld de,RESULTS+9 : ld bc,NTESTS*(RLEN+1) : ld (hl),0 : ldir
        call cls
        ld a,1 : out ($FE),a
        xor a : ld (spd),a : ld (npass),a
        ld ix,SRC
        ld a,8 : ld hl,t_ref : call measure : push hl
        ld a,8 : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de
        ld (kref),hl : ld (RESULTS+6),hl
        ld iy,tests : ld a,1 : ld (tno),a
.t:     ld a,(iy+0) : or (iy+1) : jr z,.done
        xor a : call one
        ld a,1 : call one
        nextreg $07,0
        ld de,TLEN : add iy,de
        ld a,(tno) : inc a : ld (tno),a
        jr .t
.done:  nextreg $07,0 : nextreg $62,0
        nextreg $2F,0 : nextreg $30,0 : nextreg $16,0 : nextreg $17,0 : nextreg $43,0
        ld bc,$7FFD : ld a,$10 : out (c),a
        ld a,4 : ld (bcol),a
        ld hl,RESULTS+8+NTESTS*RLEN : ld b,NTESTS
.bf:    ld a,(hl) : and 3 : jr z,.bn
        ld a,2 : ld (bcol),a
.bn:    inc hl : djnz .bf
        xor a : ld (pg),a
.pages: call page
        call key
        ld a,(pg) : inc a : cp NPAGES : jr c,.p2
        xor a
.p2:    ld (pg),a
        jr .pages
NPAGES  equ (NTESTS+NPAGE-1)/NPAGE

; ---------------------------------------------------------------- one row at one speed
; A = 0 (3.5 MHz) / 1 (28 MHz); IY = the row's table entry
one:    ld (spd),a
        or a : jr z,.s
        nextreg $07,3
.s:     ld hl,DST : ld de,DST+1 : ld bc,4095 : ld (hl),0 : ldir
        ld a,(iy+6) : or a : jp nz,special
        ld l,(iy+2) : ld h,(iy+3) : ld a,h : or l : call nz,jphl     ; set-up
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
        xor a : ld (npass),a            ; 4 passes
        ld a,(rr) : ld hl,(trow) : call measure : push hl
        ld a,(rr) : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de : jr nc,.p
        ld hl,0
.p:     call tdown
        ld de,55589 : ld b,h : ld c,l : call mul16    ; DEHL = d * 55589
        add hl,hl : rl e : rl d                        ; * 2 = d * 111178
        ld bc,(kref) : call div32
        ld a,(rr) : ld c,a : ld b,0 : call div32       ; tenths of us per call
        call store
        call check : ret z
        ld a,(spd) : inc a : jr flag
.long:  call tdown
        ld hl,0 : ld de,0 : ld a,1 : ld (rr),a : call store
        ld a,(spd) : add a,a : add a,a : add a,a : add a,4 : jr flag   ; bit 2 / 3

; A = flag bits -> or into the row's flag byte
flag:   push af
        ld a,(tno) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        pop af : or (hl) : ld (hl),a
        ret
tdown:  push hl
        ld l,(iy+4) : ld h,(iy+5) : ld a,h : or l : call nz,jphl
        pop hl : ret

; DEHL = value (tenths) -> the row's slot for this speed (+ R)
store:  push de : push hl
        ld a,(tno) : dec a : ld l,a : ld h,0 : ld d,h : ld e,l
        add hl,hl : add hl,hl : add hl,de : add hl,hl          ; * 10
        ld de,RESULTS+8 : add hl,de
        ld a,(spd) : or a : jr z,.w
        ld de,4 : add hl,de
.w:     pop de : ld (hl),e : inc hl : ld (hl),d : inc hl
        pop de : ld (hl),e : inc hl : ld (hl),d : inc hl
        ld a,(spd) : or a : jr nz,.w2
        inc hl : inc hl : inc hl : inc hl
        jr .w3
.w2:    inc hl
.w3:    ld a,(rr) : ld (hl),a
        ret

; kind 1: the routine returns HL = a number, A = flag (0 / 1 wrong / 2 never); stored x 10
special:
        ld l,(iy+0) : ld h,(iy+1) : call jphl
        push af
        ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de : add hl,hl   ; * 10 (< 65536)
        ld de,0 : ld a,1 : ld (rr),a : call store
        pop af : or a : ret z
        cp 2 : jr z,.nf
        ld a,(spd) : inc a : jr flag
.nf:    ld a,(spd) : add a,a : add a,a : add a,a : add a,4 : jp flag

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

line:   push bc
.again: call line1 : ld d,h : ld e,l
        call line1
        ld a,h : cp d : jr nz,.again
        ld a,l : cp e : jr nz,.again
        pop bc : ret
line1:  ld bc,$243B : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c) : ld l,a
        ret
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
page:   call cls
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
        ld a,(pg) : inc a : call dec1
        ld a,'/' : call putc : ld a,NPAGES : call dec1
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
        ld ix,dbuf+7 : ld b,7
.cl:    dec ix : ld (ix+0),' ' : djnz .cl
        ld ix,dbuf+7
        ld c,10 : push ix : call div8 : pop ix : add a,'0' : dec ix : ld (ix+0),a
        dec ix : ld (ix+0),'.'
.d:     ld c,10 : push ix : call div8 : pop ix : add a,'0' : dec ix : ld (ix+0),a
        ld a,d : or e : or h : or l : jr z,.p
        push ix : pop bc : ld a,c : cp low dbuf : jr nz,.d
.p:     ld a,' ' : call putc
        ld a,(pt) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        ld a,(fbit) : add a,a : add a,a : and (hl) : jr z,.nl    ; bit 2 / 3: did not fit
        ld hl,dlong : jr .o
.nl:    ld hl,dbuf
.o:     ld b,7
.o2:    ld a,(hl) : call putc : inc hl : djnz .o2
        ld a,(pt) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*RLEN : add hl,de
        ld a,(fbit) : and (hl) : ld a,' ' : jr z,.q
        ld a,'!'
.q:     jp putc

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
rdreg:  push bc : ld bc,$243B : out (c),a : inc b : in a,(c) : pop bc : ret
key:
.r:     xor a : in a,($FE) : cpl : and $1F : jr nz,.r
.p:     xor a : in a,($FE) : cpl : and $1F : jr z,.p
        ret

title:  db "NEXTBENCH v2 core ",0
hdr:    db "us/call size  3.5MHz   28MHz",0
dlong:  db "      >"
kref:   dw 0
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
