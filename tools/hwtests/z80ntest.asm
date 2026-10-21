; z80ntest.asm - every Z80N instruction on a real Next against nexclash/z80n.py (GPL-3.0-or-later).
; Build: python tools/hwtests/build.py z80ntest   (build.py first runs z80ntest_gen.py, which writes
; z80ntest_cases.inc: the cases and their expected results from the shared module's handlers).
;
; Page 1 (FUNC): 46 cases. Each loads A F BC DE HL from a table, runs ONE Z80N instruction with
;   SP = $6200 and a 1 KB window at $6000 set up, then compares A..L + SP + a Fletcher checksum of
;   the window with z80n.py's result. Instructions that touch flags run twice, from F = 0 and from
;   F = $FF (the name's last character is 0 / F); the rest from F = $A5. NEXTREG / OUTINB write NextReg $7F
;   (user register) and the case reads it back into the window. JP (C) reads NextReg $7F = 5
;   through port $253B and must land on the slot at $C140 (a stub there loads A = 5); "JPC edge"
;   runs from $BFFE, so A = $FF means the base came from the instruction's own address ($8140).
;   Entry: name, actual F, expected F, code: ' ' all match (green), F only F differs (yellow),
;   R a register / SP differs (red), M memory differs (red).
; Page 2 (TIME): T-states at 3.5 MHz from the raster line counter. Each instruction runs 2048 times
;   (8 x 256 copies, or one LDIR-style instruction with BC = 2048) from the start of a frame to a
;   line read; each measurement is made 4 times, started 0 / 52 / 104 / 156 T later (a quarter line
;   apart), and the 4 line counts are added. T = 19 * (lines - lines of the same block without it)
;   / (lines of 2048 x LD A,(IX+0) - lines of nothing). ~10 s with a blue border. NEG / LDI / LDIR are Z80 controls (8 / 16 / 21): if they are off, the method
;   is, not the Z80N rows. Entry: name, measured T (one decimal), expected T; green = within 0.5.
;   All timing code and data are in uncontended RAM ($8000-$BFFF, $D000-$E7FF).
; Any key flips the page. Border: green all pass, yellow only flag differences, red a failure.
;
; Results table at RESULTS ($7E00): "NXHT", version, test count, then per test 2 bytes: status
;   (0 not run, 1 pass, 2 fail, 4 flags only) and a detail byte (FUNC: actual F; TIME: T * 10),
;   then the calibration line count (word). Per FUNC case at DUMPS + 16 * (n-1): F A C B E D L H,
;   SP, checksum. MAME headless: read them once the border is green, yellow or red.

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

RESULTS     equ $7E00
REC         equ $7C00           ; per test 4 bytes: status, actual F / T*10, expected F / T, code
DUMPS       equ $7000
MSTACK      equ $7DE0
WIN         equ $6000           ; FUNC window, 1 KB
WINLEN      equ $400
CSTACK      equ $6200           ; SP while a FUNC instruction runs
TBUF        equ $B000           ; TIME block (up to 256 x 4 bytes + SP save / restore + RET)
PSTACK      equ $F000           ; SP inside a TIME block (PUSH nn: 256 x 2 bytes below it)
TSTACK      equ $BFE0
JPC_AT      equ $C020           ; JP (C) inside slot 0 of the $C000 slot table
JPC_EDGE    equ $BFFE           ; JP (C) whose next instruction is $C000

        org $8000
start:  jp main

        org $8140
wrongpc: ld a,$FF : jp (ix)     ; JP (C) took its base from its own address

main:   di
        ld sp,MSTACK
        nextreg $07,0           ; 3.5 MHz: TIME counts 3.5 MHz T-states
        ld hl,RESULTS
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'H' : inc hl : ld (hl),'T' : inc hl
        ld (hl),1 : inc hl      ; version
        ld (hl),NTESTS : inc hl
        ld b,NTESTS*2+2
.clr:   ld (hl),0 : inc hl : djnz .clr
        ld hl,REC : ld de,REC+1 : ld bc,NTESTS*4-1 : ld (hl),0 : ldir
        call cls
        ld a,1 : out ($FE),a    ; blue border while running
        call run_cases
        call timing
        call build_slots
        call run_jpc
        call border
.pages: ld a,1 : ld b,NFUNC : ld c,0 : call page
        call key
        ld a,NFUNC+1 : ld b,NTIME : ld c,1 : call page
        call key
        jr .pages

; ---------------------------------------------------------------- FUNC
; HL = list of (address word, byte), ended by address 0: clear the window, then poke them
setup:  push hl
        ld hl,WIN : ld de,WIN+1 : ld bc,WINLEN-1 : ld (hl),0 : ldir
        pop hl
.l:     ld e,(hl) : inc hl : ld d,(hl) : inc hl
        ld a,d : or e : ret z
        ld a,(hl) : inc hl : ld (de),a
        jr .l

; Fletcher-8 pair of the window: D = sum, E = sum of sums (both mod 256)
winsum: ld hl,WIN : ld bc,WINLEN : ld de,0
.l:     ld a,(hl) : add a,d : ld d,a : add a,e : ld e,a
        inc hl : dec bc : ld a,b : or c : jr nz,.l
        ret

; A = test number, HL = expected F A C B E D L H, SP, checksum; GOT holds the actual ones
check:  ld (tno),a
        ld (eptr),hl
        call winsum
        ld (gchk),de
        ld hl,GOT+1 : ld de,(eptr) : inc de : ld b,9 : ld c,' '
.r:     ld a,(de) : cp (hl) : jr z,.r1
        ld c,'R'
.r1:    inc hl : inc de : djnz .r
        ld b,2
.m:     ld a,(de) : cp (hl) : jr z,.m1
        ld a,c : cp ' ' : jr nz,.m1
        ld c,'M'
.m1:    inc hl : inc de : djnz .m
        ld hl,(eptr) : ld a,(GOT) : cp (hl) : jr z,.f1
        ld a,c : cp ' ' : jr nz,.f1
        ld c,'F'
.f1:    ld a,c
        ld b,1 : cp ' ' : jr z,.st
        ld b,4 : cp 'F' : jr z,.st
        ld b,2
.st:    ld a,(tno) : call recaddr
        ld (hl),b : inc hl
        ld a,(GOT) : ld (hl),a : inc hl
        push hl : ld hl,(eptr) : ld a,(hl) : pop hl : ld (hl),a : inc hl
        ld (hl),c
        ld a,(GOT) : ld e,a : ld a,(tno) : ld c,a : ld a,b : call result
        ld a,(tno) : dec a : ld l,a : ld h,0
        add hl,hl : add hl,hl : add hl,hl : add hl,hl
        ld de,DUMPS : add hl,de : ex de,hl
        ld hl,GOT : ld bc,12 : ldir
        ret

GOT:    ds 8                    ; F A C B E D L H (pushed by the case)
gsp:    dw 0
gchk:   dw 0
msp:    dw 0
eptr:   dw 0
tno:    db 0

; slot table for JP (C): every 64 bytes from $C000 "LD A,slot : JP (IX)"; JP (C) at JPC_AT, JPC_EDGE
build_slots:
        ld hl,$C000 : ld c,0
.l:     ld (hl),$3E : inc hl : ld (hl),c : inc hl : ld (hl),$DD : inc hl : ld (hl),$E9
        ld de,61 : add hl,de
        inc c : jr nz,.l
        ld hl,$98ED
        ld (JPC_AT),hl
        ld (JPC_EDGE),hl
        ret

; ---------------------------------------------------------------- TIME
timing: ld (tsave),sp
        ld sp,TSTACK
        ld hl,$D000 : ld de,$D001 : ld bc,$17FF : ld (hl),0 : ldir   ; read / write area, all 0
        ld ix,$D000
        ld hl,refini : ld (tini),hl
        xor a : ld hl,refx : ld c,3 : call measure          ; 4 x 2048 x LD A,(IX+0)
        push hl
        xor a : ld c,0 : call measure                       ; the same with nothing in the block
        pop de : ex de,hl : or a : sbc hl,de
        ld (dref),hl
        ld (RESULTS+6+NTESTS*2),hl
        ld iy,ttab
        ld a,NFUNC+1 : ld (tno),a
.next:  ld a,(iy+0) : cp $FF : jp z,.done
        ld l,(iy+3) : ld h,(iy+4) : ld (tini),hl
        ld a,(iy+0) : ld l,(iy+6) : ld h,(iy+7) : ld c,(iy+5) : call measure
        push hl
        ld a,(iy+0) : ld l,(iy+9) : ld h,(iy+10) : ld c,(iy+8) : call measure
        pop de : ex de,hl : or a : sbc hl,de                ; lines with - lines without
        jr nc,.pos
        ld hl,0
.pos:   ld b,h : ld c,l : ld hl,0 : ld a,19
.mul:   add hl,bc : dec a : jr nz,.mul                      ; 19 * d (< 16000)
        ld de,(dref) : call div16                           ; HL = whole T, BC = remainder
        ld a,l : add a,a : ld l,a : add a,a : add a,a : add a,l : ld (twhole),a   ; whole * 10
        ld h,b : ld l,c : add hl,hl : ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de
        ld de,(dref) : srl d : rr e : add hl,de             ; remainder * 10 + dref / 2
        ld de,(dref) : call div16                           ; tenths, rounded (10 = carry)
        ld a,(twhole) : add a,l : ld l,a : ld h,0           ; HL = T * 10
        ld b,(iy+2) : inc b
        jr .adj1
.adj:   ld de,10 : add hl,de
.adj1:  djnz .adj                                           ; + adjust * 10
        ld a,h : or a : jr z,.t8
        ld hl,255
.t8:    ld c,l                                              ; C = T * 10 (255 = off scale)
        ld a,(iy+1) : ld b,a
        add a,a : ld e,a : add a,a : add a,a : add a,e      ; expected * 10
        ld e,a : ld a,c : sub e : jr nc,.ab
        neg
.ab:    ld e,1 : cp 6 : jr c,.st                            ; within 0.5 T
        ld e,2
.st:    ld a,(tno) : call recaddr
        ld (hl),e : inc hl : ld (hl),c : inc hl : ld (hl),b : inc hl : ld (hl),' '
        ld a,(tno) : ld d,c : ld c,a : ld a,e : ld e,d : call result
        ld de,11 : add iy,de
        ld a,(tno) : inc a : ld (tno),a
        jp .next
.done:  ld sp,(tsave)
        ret

; A = mode (0: 256 copies run 8 times, 1: one copy run once), HL = body, C = its length.
; Builds TBUF (SP saved and set to PSTACK, the copies, SP restored, RET), then 4 times: wait for
; the start of a frame, wait 0 / 52 / 104 / 156 T, run it (registers from (tini) each time), read
; the raster line. Returns HL = the 4 lines added.
measure:
        ld (tmode),a
        push hl : push bc
        ld hl,tpre : ld de,TBUF : ld bc,tpre_len : ldir
        pop bc : pop hl
        ld b,0 : ld a,(tmode) : or a : jr z,.cp
        ld b,1
.cp:    push bc : push hl
        ld a,c : or a : jr z,.e
        ld b,0 : ldir
.e:     pop hl : pop bc
        djnz .cp
        ld hl,tsuf : ld bc,tsuf_len : ldir
        ld hl,0 : ld (tsum),hl
        xor a : ld (tpass),a
.pass:  ld a,(tmode) : or a : ld a,8 : jr z,.k
        ld a,1
.k:     ld (tk),a
        call frame_sync
        ld a,(tpass) : add a,a : add a,a : inc a : ld b,a  ; 1, 5, 9, 13 x 13 T
.dl:    djnz .dl
.l:     ld (tsp),sp
        ld sp,(tini) : pop af : pop bc : pop de : pop hl
        ld sp,(tsp)
        call TBUF
        ld a,(tk) : dec a : ld (tk),a : jr nz,.l
        call line
        ld de,(tsum) : add hl,de : ld (tsum),hl
        ld a,(tpass) : inc a : ld (tpass),a : cp 4 : jr nz,.pass
        ret

tpre:   ld (tsp2),sp : ld sp,PSTACK
tpre_len equ $-tpre
tsuf:   ld sp,(tsp2) : ret
tsuf_len equ $-tsuf

; HL / DE -> HL quotient, BC remainder (DE < 32768)
div16:  ld a,h : ld c,l : ld hl,0 : ld b,16
.d:     sla c : rla
        adc hl,hl
        sbc hl,de : jr nc,.ok
        add hl,de : jr .n
.ok:    inc c
.n:     djnz .d
        push hl
        ld h,a : ld l,c
        pop bc
        ret

refx:   ld a,(ix+0)
refini: db 0,0,0,0,0,0,0,0
tsave:  dw 0
tsp:    dw 0
tsp2:   dw 0
tsum:   dw 0
tpass:  db 0
twhole: db 0
tini:   dw 0
dref:   dw 0
tmode:  db 0
tk:     db 0

; ---------------------------------------------------------------- raster (as im2hold)
; the 9-bit line into HL, read until two reads agree ($1E / $1F are two reads)
line:   push bc
.again: call line1 : ld d,h : ld e,l
        call line1
        ld a,h : cp d : jr nz,.again
        ld a,l : cp e : jr nz,.again
        pop bc : ret
line1:  ld bc,$243B : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c) : ld l,a
        ret
; return within 28 T of line 0 starting: wait for line >= 256, then past 257, then low byte 0.
; (`line` takes ~300 T, longer than a 224 T line: polling it can miss line 0 every frame)
frame_sync:
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.a:     in a,(c) : and 1 : jr z,.a
        dec b : ld a,$1F : out (c),a : inc b
.b:     in a,(c) : cp 2 : jr c,.b
.c:     in a,(c) : or a : jr nz,.c
        ret

; ---------------------------------------------------------------- results + screen
; A = status, C = test number, E = detail
result: ld b,a
        ld a,c : dec a : ld l,a : ld h,0 : add hl,hl
        push de : ld de,RESULTS+6 : add hl,de : pop de
        ld (hl),b : inc hl : ld (hl),e
        ret

; A = test number -> HL = its REC entry
recaddr:
        dec a : ld l,a : ld h,0 : add hl,hl : add hl,hl
        push de : ld de,REC : add hl,de : pop de
        ret

border: ld hl,REC : ld b,NTESTS : ld c,4    ; green
.l:     ld a,(hl)
        cp 2 : jr nz,.y
        ld c,2 : jr .o                      ; red wins
.y:     cp 4 : jr nz,.n
        ld c,6
.n:     inc hl : inc hl : inc hl : inc hl
        djnz .l
.o:     ld a,c : ld (bcol),a : out ($FE),a
        ret
bcol:   db 0

cls:    ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),$38 : ldir
        ret

; A = first test, B = count, C = 0 FUNC / 1 TIME
page:   ld (pfirst),a : ld a,b : ld (pcount),a : ld a,c : ld (pkind),a
        call cls
        ld a,(bcol) : out ($FE),a
        xor a : ld (crow),a : ld (ccol),a
        ld hl,title : call puts
        ld a,$01 : call rdreg : push af
        rrca : rrca : rrca : rrca : and 15 : add a,'0' : call putc
        ld a,'.' : call putc
        pop af : and 15 : call dec2
        ld a,'.' : call putc
        ld a,$0E : call rdreg : call dec2
        ld hl,pfunc : ld a,(pkind) : or a : jr z,.t
        ld hl,ptime
.t:     call puts
        xor a : ld (pos),a
.e:     ld a,(pcount) : ld b,a : ld a,(pos) : cp b : ret z
        cp 23 : jr nc,.c2
        inc a : ld (crow),a : xor a : jr .c
.c2:    sub 22 : ld (crow),a : ld a,16
.c:     ld (ccol),a
        ld a,(pfirst) : ld b,a : ld a,(pos) : add a,b : ld (ptest),a
        call recaddr : ld (prec),hl
        ld a,(hl) : ld e,$07                ; not run: black paper
        cp 1 : jr nz,.s2
        ld e,$60 : jr .s                    ; green
.s2:    cp 2 : jr nz,.s4
        ld e,$50 : jr .s                    ; red
.s4:    cp 4 : jr nz,.s
        ld e,$70                            ; yellow
.s:     call paint
        ld a,(ptest) : dec a : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,names : add hl,de : ld b,7
.nm:    ld a,(hl) : call putc : inc hl : djnz .nm
        ld a,' ' : call putc
        ld hl,(prec) : inc hl
        ld a,(pkind) : or a : jr nz,.time
        ld a,(hl) : call hex2 : ld a,' ' : call putc
        inc hl : ld a,(hl) : call hex2 : ld a,' ' : call putc
        inc hl : ld a,(hl) : call putc
        jr .nx
.time:  ld a,(hl) : call div10 : push af        ; B = whole T, A = tenths
        ld a,b : cp 10 : jr nc,.t2
        ld a,' ' : call putc : ld a,b : add a,'0' : call putc : jr .t3
.t2:    ld a,b : call dec2
.t3:    ld a,'.' : call putc : pop af : add a,'0' : call putc
        ld a,' ' : call putc
        inc hl : ld a,(hl) : call dec2s
.nx:    ld a,(pos) : inc a : ld (pos),a
        jp .e

; E = attribute for 15 cells at crow, ccol
paint:  ld a,(crow) : ld l,a : ld h,0
        add hl,hl : add hl,hl : add hl,hl : add hl,hl : add hl,hl
        ld a,(ccol) : add a,l : ld l,a
        ld bc,$5800 : add hl,bc
        ld b,15
.l:     ld (hl),e : inc hl : djnz .l
        ret

; A = character at crow, ccol (ROM font at $3D00); ccol + 1
putc:   push hl : push de : push bc
        sub 32 : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,$3D00 : add hl,de
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

hex2:   push af : rrca : rrca : rrca : rrca : call hex1 : pop af
hex1:   and 15 : add a,'0' : cp '9'+1 : jr c,.d
        add a,7
.d:     jp putc

; A -> B = A / 10, A = A mod 10
div10:  ld b,0
.l:     cp 10 : ret c
        sub 10 : inc b : jr .l

; A (0..99) as two digits
dec2:   push bc
        call div10 : ld c,a
        ld a,b : add a,'0' : call putc
        ld a,c : add a,'0' : call putc
        pop bc
        ret

; A (0..99), a space instead of a leading 0
dec2s:  cp 10 : jr nc,dec2
        push af : ld a,' ' : call putc : pop af
        add a,'0' : jp putc

; A = NextReg number -> A = its value
rdreg:  push bc
        ld bc,$243B : out (c),a : inc b : in a,(c)
        pop bc
        ret

; wait for every key up, then any key down
key:
.r:     xor a : in a,($FE) : cpl : and $1F : jr nz,.r
.p:     xor a : in a,($FE) : cpl : and $1F : jr z,.p
        ret

title:  db "Z80N v1 core ",0
pfunc:  db "  FUNC 1/2",0
ptime:  db "  TIME 2/2",0
crow:   db 0
ccol:   db 0
pos:    db 0
pfirst: db 0
pcount: db 0
pkind:  db 0
ptest:  db 0
prec:   dw 0

        INCLUDE "z80ntest_cases.inc"

        ASSERT $ <= TBUF

        SAVENEX OPEN "z80ntest.nex", start, MSTACK
        SAVENEX CORE 3,0,0
        SAVENEX CFG 0,0,0,0
        SAVENEX AUTO
        SAVENEX CLOSE
