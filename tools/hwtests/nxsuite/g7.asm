; nxsuite/g7.asm - G7 BENCH: the nextbench v3 table (spec section 3 G7). GPL-3.0-or-later.
; Slot-7 overlay on page 61. The rows are nextbench_gen.py's (suite layout: build/nb_cases.inc), so each
; row is the same routine as nextbench v3. Per row and speed (3.5 / 28 MHz): set-up, R chosen by a probe
; so a measurement fills ~140 lines (as nextbench), then 5 runs of [the row R times - the empty routine
; R times] on the core's `measure` (4 passes from frame start, quarter-line delays), each converted to
; microseconds per call with the start-up calibration `cal` (2048 x LD A,(IX+0) at 3.5 MHz = 38,912 T =
; 11,117.7 us); tear-down; the copy / fill check. Differences from nextbench v3: the 5 runs of a row follow
; each other (v3 repeats the whole table 5 times), and the calibration is the one at start-up.
; One line per row and speed: T id=nb.<name>.<size>.<35|28>, v = mean us per call (min / max over the 5
; runs, n = 5), R = calls per measurement. Copper function rows (kind 1): v = the number (a line or a count
; of wrong palette entries), mean of 5. Status: FAIL only when a copy / fill check fails ("!" in
; nextbench); PASS when it is right; INFO for rows with no check. A row whose one call does not fit a
; frame: v=long. No expectation from 3.02 (the 28 MHz read wait) is applied: these are numbers.
; Memory during a row: slot 6 = page 38 (SRC $C000 2 KB pattern, DST $C800 2 KB, the stack-copy block at
; $D000), COPZ = $6200 (512 zero bytes in bank 5, the z80ntest window), blocks / table / rows here. The
; two $7FFD rows page bank 0 into slots 6 / 7: their code is in bank 2 (nb_far.inc) and they are measured
; through g7far (bank 2), which puts pages 38 / 61 back before it returns. Interrupts off throughout.
; N01's own line (INFO): v = rows run, fails = rows whose check failed, cal = the calibration used,
; dma35 = PASS / FAIL for the DMA copy / fill rows at 3.5 MHz (claim dma-correct-3m5). About 4 min.

G7P6    equ 38
        MODULE nb
SRC     equ $C000
DST     equ $C800
stkblk  equ $D000
COPZ    equ $6200

@t_n01: di
        call prep
        xor a : ld (nfail),a : ld (nrow),a : ld (ndma),a
        ld iy,tests
.row:   ld a,(iy+0) : or (iy+1) : jr z,.done
        xor a : call one : call emit
        ld a,1 : call one : call emit
        ld hl,nrow : inc (hl)
        ld de,TLEN : add iy,de
        jr .row
.done:  ld a,(spd0) : nextreg $07,a
        xor a : ld (mshift),a
        ld a,(nrow) : ld l,a : ld h,0 : call res_int
        ld hl,u_count : call res_unit
        ld a,(nfail) : ld e,a : ld d,0 : ld hl,k_fails : call ex_kd
        ld de,(cal) : ld hl,k_cal : call ex_kd
        ld hl,k_dma : call ex_k
        ld hl,w_pass : ld a,(ndma) : or a : jr z,.dw
        ld hl,w_fail
.dw:    jp wstr
TLEN    equ 20

; slot 6 = page 38: the source pattern, the stack-copy block; COPZ zeroed; slot 6 home again
prep:   nextreg $56,G7P6
        ld hl,SRC : ld bc,2048 : ld e,0
.s:     ld a,e : add a,a : add a,a : add a,a : sub e : add a,3 : and $7F : ld (hl),a
        inc hl : inc e : dec bc : ld a,b : or c : jr nz,.s
        ; 256 chunks, descending: LD SP,SRC+I*8 : POP AF/BC/DE/HL : LD SP,DST+I*8+8 : PUSH HL/DE/BC/AF
        ld hl,stkblk : ld bc,255 * 8
.k:     ld (hl),$31 : inc hl
        push hl : ld hl,SRC : add hl,bc : ex de,hl : pop hl
        ld (hl),e : inc hl : ld (hl),d : inc hl
        ld (hl),$F1 : inc hl : ld (hl),$C1 : inc hl : ld (hl),$D1 : inc hl : ld (hl),$E1 : inc hl
        ld (hl),$31 : inc hl
        push hl : ld hl,DST+8 : add hl,bc : ex de,hl : pop hl
        ld (hl),e : inc hl : ld (hl),d : inc hl
        ld (hl),$E5 : inc hl : ld (hl),$D5 : inc hl : ld (hl),$C5 : inc hl : ld (hl),$F5 : inc hl
        ld a,b : or c : jr z,.ke
        push hl : ld h,b : ld l,c : ld bc,8 : or a : sbc hl,bc : ld b,h : ld c,l : pop hl
        jr .k
.ke:    ld (hl),$ED : inc hl : ld (hl),$7B : inc hl : ld de,spsave : ld (hl),e : inc hl : ld (hl),d : inc hl
        ld (hl),$C9
        ld hl,COPZ : ld de,COPZ+1 : ld bc,511 : ld (hl),0 : ldir
        nextreg $56,HOMEP6
        ret

; ---------------------------------------------------------------- one row at one speed
; A = 0 (3.5 MHz) / 1 (28 MHz), IY = the row -> (rlong), (rr), (vsum / vmin / vmax), (rbad)
one:    ld (spd),a
        ld b,0 : or a : jr z,.s
        ld b,3
.s:     ld a,b : nextreg $07,a : ld (mshift),a
        xor a : ld (msline),a : ld (rlong),a : ld (rbad),a
        ld hl,zini : ld (mini),hl
        ld hl,0 : ld (vsum),hl : ld (vsum+2),hl : ld (vmax),hl : ld (vmax+2),hl
        dec hl : ld (vmin),hl : ld (vmin+2),hl
        nextreg $56,G7P6
        ld hl,DST : ld de,DST+1 : ld bc,2047 : ld (hl),0 : ldir
        ld a,(iy+6) : cp 1 : jp z,.fn
        ld l,(iy+2) : ld h,(iy+3) : ld a,h : or l : call nz,jphl       ; set-up
        ld l,(iy+0) : ld h,(iy+1) : ld (trow),hl
        ; probe (4 passes, R = 1): 4 x the lines of one call
        ld a,1 : call meas
        ld a,h : cp 920>>8 : jr c,.p1
        jp nz,.lg
        ld a,l : cp 920&255 : jp nc,.lg
.p1:    ld a,h : or a : jr nz,.big
        ld a,l : cp 40 : jr c,.small
.big:   ld b,h : ld c,l : ld hl,4*TARGET : call div16                  ; R = 4 x TARGET / lines of 1
        jr .r
.small: ld a,8 : call meas
        ld a,h : or a : jr nz,.m8
        ld a,l : cp 80 : jr c,.tiny
.m8:    ld b,h : ld c,l : ld hl,8*4*TARGET : call div16                ; R = 8 x 4 x TARGET / lines of 8
        jr .r
.tiny:  ld a,64 : call meas
        ld de,4 : add hl,de : ld b,h : ld c,l
        ld hl,64*4*TARGET : call div16                                  ; R = 64 x 4 x TARGET / (lines + 4)
.r:     ld a,h : or a : jr z,.r1
        ld hl,255
.r1:    ld a,l : or a : jr nz,.r2
        inc a
.r2:    ld (rr),a
        ld b,5
.run:   push bc
        ld a,(rr) : call meas : push hl
        ld hl,(trow) : push hl
        ld hl,g7ret : ld (trow),hl
        ld a,(rr) : call meas
        pop de : ld (trow),de
        ex de,hl : pop hl : or a : sbc hl,de : jr nc,.d
        ld hl,0
.d:     ; x = d x 55589 x 20 / cal / R (us x 100 per call)
        ex de,hl : ld bc,55589 : call mul16
        call x20
        ld bc,(cal) : ld a,b : or c : jr nz,.c
        inc bc
.c:     call div32
        ld a,(rr) : ld c,a : ld b,0 : call div32
        call addv
        pop bc : djnz .run
        ld l,(iy+4) : ld h,(iy+5) : ld a,h : or l : call nz,jphl       ; tear-down
        call check : jr z,.home
        ld a,1 : ld (rbad),a
.home:  nextreg $56,HOMEP6
        ret
.lg:    ld l,(iy+4) : ld h,(iy+5) : ld a,h : or l : call nz,jphl
        ld a,1 : ld (rlong),a
        jr .home
; kind 1: the routine returns HL = a number, A = 0 / 1 (wrong, "!") / 2 (never): 5 runs
.fn:    ld a,1 : ld (rr),a
        ld b,5
.f1:    push bc
        ld l,(iy+0) : ld h,(iy+1) : call jphl
        or a : jr z,.f2
        ld (rbad),a
.f2:    call x100 : call addv
        pop bc : djnz .f1
        ld a,(rbad) : cp 2 : jr nz,.f3
        ld (rlong),a
.f3:    nextreg $56,G7P6 : jr .home
; A = R -> HL = lines of (trow) R times (kind 2: through g7far in bank 2)
meas:   ld hl,(trow) : ld b,a : ld a,(iy+6) : cp 2 : ld a,b : jp z,g7far
        jp measure
; DEHL = a run's value -> vsum += , vmin / vmax
addv:   ld (vx),hl : ld (vx+2),de
        ld bc,(vsum) : add hl,bc : ld (vsum),hl
        ex de,hl : ld bc,(vsum+2) : adc hl,bc : ld (vsum+2),hl
        ld hl,vx : ld de,vmin : call cmp32 : jr nc,.n1
        ld hl,vx : ld de,vmin : ld bc,4 : ldir
.n1:    ld hl,vmax : ld de,vx : call cmp32 : ret nc
        ld hl,vx : ld de,vmax : ld bc,4 : ldir
        ret
; DEHL x 20
x20:    add hl,hl : rl e : rl d : add hl,hl : rl e : rl d     ; x 4
        push de : push hl
        add hl,hl : rl e : rl d : add hl,hl : rl e : rl d     ; x 16
        pop bc : add hl,bc : ex de,hl : pop bc : adc hl,bc : ex de,hl
        ret
; HL / BC -> HL (16 bits)
div16:  ld de,0 : call div32 : ret
jphl:   jp (hl)

; check (IY+7): 0 none, 1 DST = SRC for n bytes, 2 DST = $55 for n bytes -> Z if right
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

; ---------------------------------------------------------------- the line for one row and speed
emit:   ld a,ST_INFO : ld (R_st),a
        ld a,(iy+7) : or a : jr z,.st
        ld a,ST_PASS : ld (R_st),a
        ld a,(rbad) : or a : jr z,.st
        ld a,ST_FAIL : ld (R_st),a
        ld hl,nfail : inc (hl)
        ld a,(spd) : or a : jr nz,.st                   ; dma35: the DMA rows at 3.5 MHz
        ld a,(iy+12) : cp 'D' : jr z,.dm
        ld a,(iy+17) : cp 'D' : jr nz,.st               ; "FILL DMA"
.dm:    ld hl,ndma : inc (hl)
.st:    ld a,(iy+6) : cp 1 : jr nz,.nb
        ld a,(rbad) : cp 1 : jr nz,.nb                  ; a function row's "!": a key, not FAIL
        ld a,ST_INFO : ld (R_st),a
.nb:    ld a,(rlong) : or a : jr z,.val
        ld hl,w_long : call res_word
        jr .id
.val:   ld hl,(vsum) : ld de,(vsum+2) : ld c,5 : call div8
        call res_num
        ld hl,vmin : ld de,R_min : ld bc,4 : ldir
        ld hl,vmax : ld de,R_max : ld bc,4 : ldir
        ld hl,5 : ld (R_n),hl
        ld hl,u_us : ld a,(iy+6) : cp 1 : jr nz,.u
        ld hl,u_count
.u:     call res_unit
        ld a,(rr) : ld e,a : ld d,0 : ld hl,k_r : call ex_kd
        ld a,(iy+6) : cp 1 : jr nz,.id
        ld a,(rbad) : ld e,a : ld d,0 : ld hl,k_flag : call ex_kd
.id:    ; "nb." + the name without trailing spaces (inner ones -> "_") + "." + size + "." + 35 / 28
        ld de,idb : ld hl,s_nb : ld bc,3 : ldir
        push iy : pop hl : ld bc,12 : add hl,bc
        ld b,8 : ld c,0                                 ; C = pending spaces
.c:     ld a,(hl) : inc hl : cp ' ' : jr nz,.c1
        inc c : jr .c2
.c1:    push af
.c3:    ld a,c : or a : jr z,.c4
        ld a,'_' : ld (de),a : inc de : dec c : jr .c3
.c4:    pop af : ld (de),a : inc de
.c2:    djnz .c
        ld a,'.' : ld (de),a : inc de
        ld l,(iy+10) : ld h,(iy+11) : call dec5
        ld a,'.' : ld (de),a : inc de
        ld hl,s_35 : ld a,(spd) : or a : jr z,.sp
        ld hl,s_28
.sp:    ld bc,3 : ldir
        ld hl,idb : jp sub_emit
; HL -> decimal at DE (no leading zeros), DE after it
dec5:   ld bc,10000 : call .d : ld bc,1000 : call .d : ld bc,100 : call .d : ld bc,10 : call .d
        ld a,l : add a,'0' : ld (de),a : inc de
        xor a : ld (.z),a
        ret
.d:     xor a
.l:     or a : sbc hl,bc : jr c,.e
        inc a : jr .l
.e:     add hl,bc
        ld c,a : ld a,(.z) : or c : ret z
        ld (.z),a : ld a,c : add a,'0' : ld (de),a : inc de
        ret
.z:     db 0

; ---------------------------------------------------------------- set-up / tear-down (nextbench v3)
dmaset: ld hl,dc256 : ld bc,(16 << 8) | $6B : otir : ret      ; a full DMA program (ports set)
dmacset: ld hl,dcf1 : ld bc,(16 << 8) | $6B : otir : ret     ; 1 byte, both ports fixed (DMA cont)
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

; ---------------------------------------------------------------- unrolled blocks (nextbench v3)
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

        INCLUDE "nb_cases.inc"

TARGET  equ 140
spd:    db 0
rr:     db 0
rlong:  db 0
rbad:   db 0
nfail:  db 0
ndma:   db 0
nrow:   db 0
trow:   dw 0
spsave: dw 0
vx:     ds 4
vsum:   ds 4
vmin:   ds 4
vmax:   ds 4
idb:    ds 24
s_nb:   db "nb."
s_35:   db "35",0
s_28:   db "28",0
w_long: db "long",0
u_us:   db "us",0
k_r:    db "R",0
k_flag: db "flag",0
k_fails: db "fails",0
k_cal:  db "cal",0
k_dma:  db "dma35",0
w_pass: db "PASS",0
w_fail: db "FAIL",0
        ENDMODULE
