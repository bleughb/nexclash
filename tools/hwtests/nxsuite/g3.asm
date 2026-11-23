; nxsuite/g3.asm - G3 IRQ: interrupts (spec section 3 G3). GPL-3.0-or-later.
; Interrupt area $F800-$FFFF (bank 0, slot 7; never moved during G3):
;   $F8F8 JP g3h_a       I01 / I02 handler A (the vector read from $FAFF / $FB00 = $F8 $F8: bus $FF)
;   $F9F9 JP g3h_b       I01 / I02 handler B (any other bus byte: $F9 $F9)
;   $FA00-$FB00          the I01 table (I = $FA), 257 bytes                [spec: I = $90 at $9000; $9000 is
;                        suite code here, so the same layout at a free page - recorded deviation]
;   $FC00-$FCFF          hardware IM2 table (I = $FC), 128 words
;   $FD00-$FE00          the common IM 2 table (I = $FD), 257 x $FE -> $FEFE JP (handler)
; Frames are counted by polling the raster with interrupts on; every handler sets g3int, and a raster read
; that saw it set is repeated (a handler between the register select and the read changes the selected
; NextReg). (A first version read inside DI and lost most pulse-mode interrupts in JNext: the pulse is
; shorter than the read at 28 MHz there, and nobody knows the board's pulse at 28 MHz yet - test I05.) Every test ends DI; restore_all puts back $C0, $C4-$C6, $CC-$CE, $22,
; $23, $07, CTC 0 / 3, $C8-$CA, IM 1 and I; tests that used hardware IM2 also run a dummy RETI.
; Built in stage 1: I01 I02 I03 I07 I09 I11 I12 I13 I15 I16 I17 I21 (the others are written SKIP not-built).

G3V     equ $FEFE
G3T     equ $FD00
G3BUS   equ $FA00
G3HW    equ $FC00

; ---------------------------------------------------------------- set-up
; HL = handler for the common table (also builds the I01 table and its two JPs)
g3_tables:
        ld a,$C3 : ld (G3V),a : ld (G3V+1),hl
        ld hl,G3T : ld de,G3T+1 : ld bc,256 : ld (hl),$FE : ldir
        ld hl,G3BUS : ld de,G3BUS+1 : ld bc,256 : ld (hl),$F9 : ldir
        ld a,$F8 : ld (G3BUS+$FF),a : ld (G3BUS+$100),a
        ld a,$C3 : ld ($F8F8),a : ld ($F9F9),a
        ld hl,g3h_a : ld ($F8F9),hl
        ld hl,g3h_b : ld ($F9FA),hl
        ret
; the hardware table: 128 words = HL
g3_hwtab:
        ex de,hl : ld hl,G3HW : ld b,128
.l:     ld (hl),e : inc hl : ld (hl),d : inc hl : djnz .l
        ret
g3_zero:
        ld hl,0 : ld (g3cnt),hl : ld (g3ca),hl : ld (g3cb),hl : ld (g3wr),hl
        ld (g3lmax),hl : ld (g3cmax),hl
        ld hl,$FFFF : ld (g3lmin),hl : ld (g3cmin),hl
        ret
; pulse mode, ULA interrupt only, status cleared, interrupts off
g3_pulse:
        di
        ld a,(NRSNAP+$C0) : and $08 : nextreg $C0,a
        nextreg $C4,1 : nextreg $C5,0 : nextreg $C6,0
        jr g3_ack
; hardware IM2, vector bits 7:5 = 000, ULA only (im2hold hw_mode)
g3_hw:  di
        nextreg $C4,0 : nextreg $C5,0 : nextreg $C6,0
        ld a,(NRSNAP+$C0) : and $08 : or 1 : nextreg $C0,a
        call g3_ack
        nextreg $C4,1
        ret
g3_ack: nextreg $C8,$FF : nextreg $C9,$FF : nextreg $CA,$FF
        ret
; leave hardware IM2: DI, pulse mode, status cleared, a dummy RETI with interrupts off (im2hold T7)
g3_hwoff:
        di
        ld a,(NRSNAP+$C0) : and $08 : nextreg $C0,a
        call g3_ack
g3_reti: reti

; B frames counted at line 150: g3_fdi interrupts off throughout, g3_fei on between the reads
g3_fdi: xor a : jr g3_fr
g3_fei: ld a,1
g3_fr:  ld (.ie),a
        or a : jr z,.f
        ei
.f:     push bc
.off:   call .rd : ld a,h : or a : jr nz,.on : ld a,l : cp 150 : jr z,.off
.on:    call .rd : ld a,h : or a : jr nz,.on : ld a,l : cp 150 : jr nz,.on
        pop bc : djnz .f
        ret
.rd:    ld a,(.ie) : or a : jp z,line
.r2:    xor a : ld (g3int),a
        call line
        ld a,(g3int) : or a : jr nz,.r2
        ret
.ie:    db 0
g3int:  db 0

; ---------------------------------------------------------------- handlers (EI ; RETI unless named)
; the common counting handler; a runaway (> 2047 runs) switches the interrupt sources off
g3h_cnt:
        push af : push hl
        ld a,1 : ld (g3int),a
        ld hl,(g3cnt) : inc hl : ld (g3cnt),hl
        ld a,h : cp 8 : jr c,.ok
        nextreg $C4,0 : nextreg $C5,0 : nextreg $C6,0
.ok:    pop hl : pop af : ei : reti
g3h_a:  push hl : ld hl,(g3ca) : inc hl : ld (g3ca),hl : pop hl : jr g3h_cnt
g3h_b:  push hl : ld hl,(g3cb) : inc hl : ld (g3cb),hl : pop hl : jr g3h_cnt
; counting + the raster line (LSB / MSB / LSB) and the CTC3 value at entry: min / max
g3h_rec:
        push af : push bc : push de : push hl
        call line
        ld de,(g3lmin) : call .min : ld (g3lmin),de
        ld de,(g3lmax) : call .max : ld (g3lmax),de
        ld bc,$1B3B : in l,(c) : ld h,0
        ld de,(g3cmin) : call .min : ld (g3cmin),de
        ld de,(g3cmax) : call .max : ld (g3cmax),de
        pop hl : pop de : pop bc : pop af
        jr g3h_cnt
.min:   push hl : or a : sbc hl,de : pop hl : ret nc
        ld d,h : ld e,l : ret
.max:   push hl : or a : sbc hl,de : pop hl : ret c
        ld d,h : ld e,l : ret
; im2hold handlers
g3h_right:
        push af : ld a,1 : ld (g3ca),a : ld (g3int),a : pop af : ei : reti
g3h_wrong:
        push af : ld a,1 : ld (g3int),a : pop af
        push hl : ld hl,(g3wr) : inc hl : ld (g3wr),hl : pop hl : ei : reti
g3h_noreti:                                     ; EI ; RET: never acknowledged
        push af : push hl
        ld a,1 : ld (g3int),a
        ld hl,(g3cnt) : inc hl : ld (g3cnt),hl
        ld a,l : cp 200 : jr c,.ok              ; fires again at once: stop at 200
        nextreg $C4,0
.ok:    pop hl : pop af : ei : ret
g3h_game:                                       ; game-style EI ; RET, reached through the trampoline
        push af : ld a,1 : ld (g3int),a : pop af
        push hl : ld hl,(g3cnt) : inc hl : ld (g3cnt),hl : pop hl : ei : ret
g3h_tramp:
        push hl : ld hl,g3h_game : ex (sp),hl : reti

g3cnt:  dw 0
g3ca:   dw 0
g3cb:   dw 0
g3wr:   dw 0
g3lmin: dw 0
g3lmax: dw 0
g3cmin: dw 0
g3cmax: dw 0

; HL = count -> carry if 4..6
g3_in46:
        ld a,h : or a : ret nz
        ld a,l : cp 4 : ccf : ret nc
        cp 7 : ret

; a sub-test line: HL = id string, A = status, DE = value (integer)
g3_sub: ld (subid),hl : ld (R_st),a
        ex de,hl : call res_int
        ld hl,u_count : call res_unit
        ld hl,EXB : ld (wp),hl : ld (hl),0
        call emit_t
        ld hl,0 : ld (subid),hl
        ld hl,EXB : ld (wp),hl : ld (hl),0
        ld a,ST_INFO : ld (R_st),a
        ret

; ---------------------------------------------------------------- I01 pulse IM 2: the bus byte
; v = handler A runs (bus $FF), b = handler B runs. PASS if only A ran, 4-6 times in 5 frames.
t_i01:  call i01set
        im 2
i01run: ld a,G3BUS>>8 : ld i,a
        ld b,1 : call g3_fdi
        ld b,5 : call g3_fei
        di
        ld hl,(g3ca) : call res_int
        ld hl,u_count : call res_unit
        ld de,(g3cb) : ld hl,k_b : call ex_kd
        ld hl,(g3cb) : ld a,h : or l : jr nz,.f
        ld hl,(g3ca) : call g3_in46 : jr nc,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
i01set: nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        call g3_zero
        jp g3_pulse
k_b:    db "b",0

; ---------------------------------------------------------------- I02 IM 2 entered by ED 7E
; (were ED 7E not IM 2, the CPU would stay in IM 1 / 0: the ROM 3 handler at $0038 runs, IY = system
; variables, and A never counts: FAIL)
t_i02:  call i01set
        ld iy,$5C3A
        im 1
        db $ED,$7E
        jr i01run

; ---------------------------------------------------------------- I03 im2hold T1-T7 (same order, same rules)
; im2hold's VTAB = the hardware table here (I = $FC), its UTAB = the common table (I = $FD, JP at $FEFE).
; Sub lines ih.t1 .. ih.t7 (v = im2hold's detail byte); main v = passes, FAIL if any sub test failed.
t_i03:  nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        ld hl,g3h_wrong : call g3_hwtab
        ld hl,i03r : ld b,14
.c:     ld (hl),0 : inc hl : djnz .c
        call .t1 : call .t2 : call .t3 : call .t5 : call .t6 : call .t4 : call .t7
        call g3_hwoff
        ld ix,i03r : ld hl,i03id : ld b,7 : ld c,0 : ld e,0
.s:     push bc : push de : push hl : push ix
        ld a,(ix+0) : ld e,(ix+1) : ld d,0
        cp 2 : jr nz,.np
        ld a,ST_FAIL : jr .w
.np:    cp 1 : ld a,ST_PASS : jr z,.w
        ld a,ST_INFO
.w:     call g3_sub
        pop ix : pop hl : pop de : pop bc
        ld a,(ix+0) : cp 1 : jr nz,.n1
        inc c
.n1:    cp 2 : jr nz,.n2
        inc e
.n2:    inc ix : inc ix
        push de : ld de,6 : add hl,de : pop de
        djnz .s
        push de : ld l,c : ld h,0 : call res_int : pop de
        ld hl,u_count : call res_unit
        ld a,e : or a : jr nz,.fl
        ld a,ST_PASS : ld (R_st),a : ret
.fl:    ld a,ST_FAIL : ld (R_st),a : ret
.t1:    call g3_hw : call g3_zero
        ld hl,g3h_right : ld (G3HW+$16),hl
        ld a,G3HW>>8 : ld i,a : im 2
        ei : halt : di
        ld hl,g3h_wrong : ld (G3HW+$16),hl
        ld a,(g3wr) : ld c,a : or a : jr nz,.f1
        ld a,(g3ca) : or a : jr z,.f1
        ld a,1 : ld c,a : ld b,0 : jp .res
.f1:    ld a,2 : ld b,0 : jp .res
.t2:    call g3_hw : call g3_zero
        ld hl,g3h_cnt : ld (G3HW+$16),hl
        ld a,G3HW>>8 : ld i,a : im 2
        ld b,3 : call g3_fdi
        ei : nop : nop : nop : nop : di
        ld a,(g3cnt) : ld c,a : or a : ld a,1 : jr nz,.r2
        ld a,2
.r2:    ld b,1 : jp .res
.t3:    call g3_pulse : call g3_zero
        ld a,G3T>>8 : ld i,a : im 2
        ld b,3 : call g3_fdi
        ei : nop : nop : nop : nop : di
        ld a,(g3cnt) : ld c,a : or a : ld a,1 : jr z,.r3
        ld a,2
.r3:    ld b,2 : jp .res
.t4:    call g3_hw : call g3_zero
        ld hl,g3h_noreti : ld (G3HW+$16),hl
        ld a,G3HW>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,1 : call g3_fei
        di
        ld hl,g3h_cnt : ld (G3HW+$16),hl
        call g3_ack
        ld a,(g3cnt) : ld c,a : ld a,3 : ld b,3 : jp .res
.t5:    call g3_hw : call g3_zero
        ld hl,g3h_tramp : ld (G3HW+$16),hl
        ld a,G3HW>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,5 : call g3_fei
        di
        ld b,4 : jr .r46
.t6:    call g3_hw : call g3_zero
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,5 : call g3_fei
        di
        ld b,5 : jr .r46
.t7:    call g3_hw : call g3_zero
        call g3_reti                            ; RETI as a plain return: the controller sees the ack
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,5 : call g3_fei
        di
        ld b,6
.r46:   ld hl,(g3cnt) : ld c,l : push bc : call g3_in46 : pop bc
        ld a,1 : jr c,.res
        ld a,2
; A = status 1 pass / 2 fail / 3 info, B = slot 0-6 (T1..T7), C = detail
.res:   ld l,b : ld h,0 : add hl,hl : ld de,i03r : add hl,de
        ld (hl),a : inc hl : ld (hl),c
        ret
i03r:   ds 14
i03id:  db "ih.t1",0, "ih.t2",0, "ih.t3",0, "ih.t4",0, "ih.t5",0, "ih.t6",0, "ih.t7",0

; ---------------------------------------------------------------- I07 status bits $C8
; pulse: one frame under DI, read $C8; write 0, read; write 1, read. Hardware IM2: one frame under DI,
; read; write 1, read. PASS if the pulse-mode three have bit 0 = 1 / 1 / 0 (the hardware pair recorded:
; the claim's hardware-IM2 part is about interrupts on, which this does not reach).
t_i07:  nextreg $07,3
        call g3_pulse
        ld b,1 : call g3_fdi
        ld a,$C8 : call rdreg : ld (.r),a
        nextreg $C8,0
        ld a,$C8 : call rdreg : ld (.r+1),a
        nextreg $C8,1
        ld a,$C8 : call rdreg : ld (.r+2),a
        call g3_hw
        ld b,1 : call g3_fdi
        ld a,$C8 : call rdreg : ld (.r+3),a
        nextreg $C8,1
        ld a,$C8 : call rdreg : ld (.r+4),a
        call g3_hwoff
        ld a,(.r) : call res_hex
        ld hl,.r : ld de,i07k : ld b,5
.k:     push bc : push de : push hl
        ld a,(hl) : ex de,hl : ld e,(hl) : inc hl : ld d,(hl) : ex de,hl : call ex_kh
        pop hl : pop de : pop bc
        inc hl : inc de : inc de : djnz .k
        ld a,(.r) : and 1 : jr z,.f
        ld a,(.r+1) : and 1 : jr z,.f
        ld a,(.r+2) : and 1 : jr nz,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
.r:     ds 5
i07k:   dw k_p1,k_p0w,k_p1w,k_h1,k_h1w
k_p1:   db "pdi",0
k_p0w:  db "pw0",0
k_p1w:  db "pw1",0
k_h1:   db "hdi",0
k_h1w:  db "hw1",0

; ---------------------------------------------------------------- I09 ULA interrupt line
; pulse IM 2; the handler reads the line and CTC3 (prescaler 16, constant 256, free running); 250 frames.
; v / min / max = the line read in the handler (28 MHz, a few clocks after the acknowledge), n = runs.
t_i09:  nextreg $07,3
        ld hl,g3h_rec : call g3_tables
        call g3_zero
        call g3_pulse
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,250 : call g3_fei
        di
        ld hl,(g3lmin) : call res_int
        ld hl,(g3lmin) : call x100 : ld (R_min),hl : ld (R_min+2),de
        ld hl,(g3lmax) : call x100 : ld (R_max),hl : ld (R_max+2),de
        ld hl,(g3cnt) : ld (R_n),hl
        ld hl,u_lines : call res_unit
        ld de,(g3cmin) : ld hl,k_cmin : call ex_kd
        ld de,(g3cmax) : ld hl,k_cmax : jp ex_kd
k_cmin: db "ctcmin",0
k_cmax: db "ctcmax",0

; ---------------------------------------------------------------- I11 line interrupt numbering
; pulse IM 2, ULA interrupt off, line interrupt at last+1, last+2 and 511 (last = the largest line, from the
; preamble); 5 frames each: runs and the line read in the handler. PASS if last+1 fires (4-6 runs) at line 0
; or the last line (raised on the line before, book) and the other two never fire.
t_i11:  nextreg $07,3
        ld hl,g3h_rec : call g3_tables
        ld hl,(flines) : inc hl : call .one : ld (.c1),hl : ld (.l1),de
        ld hl,(flines) : inc hl : inc hl : call .one : ld (.c2),hl : ld (.l2),de
        ld hl,511 : call .one : ld (.c3),hl : ld (.l3),de
        ld hl,(.c1) : call res_int
        ld hl,u_count : call res_unit
        ld de,(.l1) : ld hl,k_line : call ex_kd
        ld de,(.c2) : ld hl,k_p2 : call ex_kd
        ld de,(.l2) : ld hl,k_line2 : call ex_kd
        ld de,(.c3) : ld hl,k_511 : call ex_kd
        ld de,(.l3) : ld hl,k_line3 : call ex_kd
        ld de,(flines) : inc de : ld hl,k_n1 : call ex_kd
        ld hl,(.c2) : ld de,(.c3) : add hl,de : ld a,h : or l : jr nz,.f
        ld hl,(.c1) : call g3_in46 : jr nc,.f
        ld hl,(.l1) : ld a,h : or l : jr z,.p
        ld de,(flines) : or a : sbc hl,de : jr nz,.f
.p:     ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
; HL = line -> HL = runs, DE = smallest line read in the handler
.one:   push hl : call g3_zero : call g3_pulse : pop hl
        ld a,l : nextreg $23,a
        ld a,$22 : call rdreg : and $F8 : or 6 : or h : nextreg $22,a   ; ULA off, line on, MSB
        nextreg $C4,2
        call g3_ack
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld hl,0 : ld (g3cnt),hl
        ld b,5 : call g3_fei
        di
        ld a,(NRSNAP+$22) : nextreg $22,a
        ld a,(NRSNAP+$23) : nextreg $23,a
        nextreg $C4,1
        ld hl,(g3cnt) : ld de,(g3lmin)
        ret
.c1:    dw 0
.c2:    dw 0
.c3:    dw 0
.l1:    dw 0
.l2:    dw 0
.l3:    dw 0
k_line: db "line",0
k_line2: db "line2",0
k_line3: db "line3",0
k_p2:   db "last2",0
k_511:  db "l511",0
k_n1:   db "at",0

; ---------------------------------------------------------------- I12 CTC rate per CPU speed
; DI; CTC3 prescaler 256, constant 256, free running; ticks over 8 frames (line MSB 1 -> 0 to the 8th
; 1 -> 0) at $07 = 0..3. v = ticks per frame at 3.5 MHz, s7 / s14 / s28 the others; PASS if the four
; 8-frame totals are within 8 ticks (1 tick per frame).
t_i12:  ld b,0 : ld hl,.r
.s:     push bc : push hl
        ld a,b : call i12run
        pop de : ex de,hl : ld (hl),e : inc hl : ld (hl),d : inc hl
        pop bc : inc b : ld a,b : cp 4 : jr nz,.s
        ld a,(spd0) : nextreg $07,a
        ld hl,(.r) : call .pf : call res_num
        ld hl,s_ticks : call res_unit
        ld de,(.r+2) : ld hl,k_s7 : call .kx
        ld de,(.r+4) : ld hl,k_s14 : call .kx
        ld de,(.r+6) : ld hl,k_s28 : call .kx
        ; spread of the four totals
        ld hl,.r : ld de,$FFFF : ld bc,0 : ld a,4
.m:     push af
        push hl : ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        push hl : or a : sbc hl,de : pop hl : jr nc,.m1
        ld d,h : ld e,l
.m1:    push hl : or a : sbc hl,bc : pop hl : jr c,.m2
        ld b,h : ld c,l
.m2:    pop hl : inc hl : inc hl
        pop af : dec a : jr nz,.m
        ld h,b : ld l,c : or a : sbc hl,de
        ld de,9 : or a : sbc hl,de : ret nc
        ld a,ST_PASS : ld (R_st),a
        ret
.kx:    push de : call ex_k : pop hl : call .pf : jp wfix
; HL = ticks over 8 frames -> DEHL = per frame x 100
.pf:    ld b,h : ld c,l : ld de,25 : call mul16
        srl d : rr e : rr h : rr l
        ret
.r:     ds 8
k_s7:   db "s7",0
k_s14:  db "s14",0
k_s28:  db "s28",0
s_ticks: db "ticks",0
; A = speed -> HL = CTC3 ticks (prescaler 256) over 8 frames (0 = the line MSB never rose)
i12run: nextreg $07,a
        ld bc,$1B3B : ld a,$27 : out (c),a : xor a : out (c),a
        ld bc,$243B : ld a,$1E : out (c),a : inc b
        ld hl,0
.w1:    in a,(c) : rra : jr c,.w0
        dec hl : ld a,h : or l : jr nz,.w1
        ret
.w0:    in a,(c) : rra : jr c,.w0
        ld b,$1B : in a,(c) : ld (.c0),a : ld d,a
        ld hl,0 : ld (.wr),hl
        ld e,0                                    ; last MSB
        ld a,8 : ld (.fr),a
.l:     ld b,$1B : in a,(c)
        cp d : ld d,a : jr c,.nw : jr z,.nw
        ld hl,(.wr) : inc hl : ld (.wr),hl        ; the count went up: a wrap
.nw:    ld b,$25 : in a,(c) : and 1
        cp e : jr z,.l
        ld e,a : or a : jr nz,.l
        ld a,(.fr) : dec a : ld (.fr),a : jr nz,.l
        ld b,$1B : in a,(c) : ld c,a
        ld a,(.c0) : sub c : ld e,a : ld d,0 : jr nc,.p
        dec d
.p:     ld hl,(.wr) : ld h,l : ld l,0 : add hl,de
        ret
.c0:    db 0
.wr:    dw 0
.fr:    db 0

; ---------------------------------------------------------------- I13 CTC time constant, polled status
; DI, 28 MHz; CTC0 timer, prescaler 16, constant 109 / 219 / 0 (256), its interrupt off; poll $C9 bit 0
; (write 1 to clear) over 50 frames. r = count(219) x 10000 / count(0): 11690 if the period is 16 x tc
; (0 = 256), 11682 if 16 x (1 + tc) -> choice (threshold 11686; the counts are in the line for the intake). PASS (polled status works) if the count is above 0.
t_i13:  nextreg $07,3
        nextreg $C5,0
        ld a,109 : call .run : ld (.c),hl
        ld a,219 : call .run : ld (.c+2),hl
        xor a : call .run : ld (.c+4),hl
        ld hl,(.c) : call res_int
        ld hl,u_count : call res_unit
        ld de,(.c+2) : ld hl,k_219 : call ex_kd
        ld de,(.c+4) : ld hl,k_256 : call ex_kd
        ld hl,(.c+4) : ld a,h : or l : jr z,.nr
        ld hl,(.c+2) : ld b,h : ld c,l : ld de,10000 : call mul16
        ld bc,(.c+4) : call div32
        push hl : ex de,hl : ld hl,k_r : call ex_kd : pop hl
        ld de,11686 : or a : sbc hl,de
        ld hl,w_tc : jr nc,.ch
        ld hl,w_tc1
.ch:    push hl : ld hl,k_choice : call ex_k : pop hl : call wstr
.nr:    ld hl,(.c) : ld a,h : or l : ret z
        ld a,ST_PASS : ld (R_st),a
        ret
; A = time constant -> HL = $C9 bit 0 sightings over 50 frames
.run:   push af
        ld bc,$183B : ld a,$07 : out (c),a : pop af : out (c),a
        nextreg $C9,$FF
        ld hl,0 : ld d,50 : ld e,0
        ld bc,$243B
.l:     ld a,$C9 : out (c),a : inc b : in a,(c) : rra : jr nc,.n
        ld a,1 : out (c),a : inc hl
.n:     dec b : ld a,$1E : out (c),a : inc b : in a,(c) : dec b : and 1
        cp e : jr z,.l
        ld e,a : or a : jr nz,.l
        dec d : jr nz,.l
        ld bc,$183B : ld a,$03 : out (c),a
        ret
.c:     ds 6
k_219:  db "c219",0
k_256:  db "c256",0
k_r:    db "r",0
w_tc:   db "16xtc",0
w_tc1:  db "16x1+tc",0

; ---------------------------------------------------------------- I15 LD A,I P/V
; pulse IM 2 counting handler, EI; LD A,I / JP PO over 500 frames (handler count); v = P/V = 0 sightings
t_i15:  nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        call g3_zero : call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld hl,0 : ld (.bad),hl
        ld ix,0 : ld c,128                      ; guard: 128 x 65536 loops
        ei
.l:     ld a,i : jp po,.b
.c:     ld hl,(g3cnt) : ld de,500 : or a : sbc hl,de : jr nc,.d
        dec ix : ld a,ixh : or ixl : jr nz,.l
        dec c : jr nz,.l
.d:     di
        ld hl,(.bad) : call res_int
        ld hl,u_count : call res_unit
        ld de,(g3cnt) : ld hl,k_runs : jp ex_kd
.b:     ld hl,(.bad) : inc hl : ld (.bad),hl : jr .c
.bad:   dw 0
k_runs: db "runs",0

; ---------------------------------------------------------------- I16 line interrupt shares /INT
; pulse IM 2 counting handler, ULA interrupt and line interrupt 100 on, 50 frames: PASS if 99-101 runs
t_i16:  nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        call g3_zero : call g3_pulse
        nextreg $23,100
        ld a,$22 : call rdreg : and $F8 : or 2 : nextreg $22,a
        nextreg $C4,3
        call g3_ack
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld hl,0 : ld (g3cnt),hl
        ld b,50 : call g3_fei
        di
        ld hl,(g3cnt) : call res_int
        ld hl,u_count : call res_unit
        ld hl,(g3cnt) : ld de,99 : or a : sbc hl,de : jr c,.f
        ld de,3 : sbc hl,de : jr nc,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret

; ---------------------------------------------------------------- I17 ULA enable in $22 and $C4
; (a) $22 bit 2 = 1 (off) then $C4 bit 0 = 1 (on); (b) $C4 bit 0 = 1 then $22 bit 2 = 1: runs over 5 frames
; and both registers read back. PASS if the last write wins: (a) 4-6 runs, (b) none.
t_i17:  nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        call g3_zero : call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld a,$22 : call rdreg : or 4 : nextreg $22,a
        nextreg $C4,1
        call .cnt : ld (.a),hl : ld (.ra),de
        call g3_zero : call g3_pulse
        ld a,$22 : call rdreg : and $FB : nextreg $22,a
        nextreg $C4,1
        ld a,$22 : call rdreg : or 4 : nextreg $22,a
        call .cnt : ld (.b),hl : ld (.rb),de
        ld hl,(.a) : call res_int
        ld hl,u_count : call res_unit
        ld de,(.b) : ld hl,k_b : call ex_kd
        ld a,(.ra) : ld hl,k_22a : call ex_kh
        ld a,(.ra+1) : ld hl,k_c4a : call ex_kh
        ld a,(.rb) : ld hl,k_22b : call ex_kh
        ld a,(.rb+1) : ld hl,k_c4b : call ex_kh
        ld hl,(.b) : ld a,h : or l : jr nz,.f
        ld hl,(.a) : call g3_in46 : jr nc,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
; -> HL = runs over 5 frames, E = $22, D = $C4 after
.cnt:   call g3_ack
        ld b,1 : call g3_fdi
        ld hl,0 : ld (g3cnt),hl
        ld b,5 : call g3_fei
        di
        ld a,$22 : call rdreg : ld e,a
        ld a,$C4 : call rdreg : ld d,a
        ld hl,(g3cnt)
        ret
.a:     dw 0
.b:     dw 0
.ra:    dw 0
.rb:    dw 0
k_22a:  db "nr22a",0
k_c4a:  db "nrc4a",0
k_22b:  db "nr22b",0
k_c4b:  db "nrc4b",0

; ---------------------------------------------------------------- I21 NextReg $20 bit 6 (ULA request)
; at line 150, interrupts on: NEXTREG $20,$40, four NOPs, DI: handler runs and $C8, in pulse mode and in
; hardware IM2 (I = $FC, every vector -> the counter), with the ULA enable ($C4 bit 0) on and off.
; v = pulse with the enable on.
t_i21:  nextreg $07,3
        ld hl,g3h_cnt : call g3_tables
        ld hl,g3h_cnt : call g3_hwtab
        call g3_pulse : ld a,G3T>>8 : ld i,a : im 2
        ld a,1 : call .one : ld (.v),hl : ld (.c8),a
        call g3_pulse
        xor a : call .one : ld (.v+2),hl : ld (.c8+1),a
        call g3_hw : ld a,G3HW>>8 : ld i,a
        ld a,1 : call .one : ld (.v+4),hl : ld (.c8+2),a
        call g3_hw
        xor a : call .one : ld (.v+6),hl : ld (.c8+3),a
        call g3_hwoff
        ld hl,(.v) : call res_int
        ld hl,u_count : call res_unit
        ld de,(.v+2) : ld hl,k_poff : call ex_kd
        ld de,(.v+4) : ld hl,k_hon : call ex_kd
        ld de,(.v+6) : ld hl,k_hoff : call ex_kd
        ld a,(.c8) : ld hl,k_c8pon : call ex_kh
        ld a,(.c8+1) : ld hl,k_c8poff : call ex_kh
        ld a,(.c8+2) : ld hl,k_c8hon : call ex_kh
        ld a,(.c8+3) : ld hl,k_c8hoff : jp ex_kh
; A = ULA enable -> HL = runs, A = $C8 after
.one:   nextreg $C4,a
        call g3_ack
        ld b,1 : call g3_fdi                    ; at line 150, interrupts off
        ld hl,0 : ld (g3cnt),hl
        ei
        nextreg $20,$40
        nop : nop : nop : nop
        di
        ld a,$C8 : call rdreg
        ld hl,(g3cnt)
        ret
.v:     ds 8
.c8:    ds 4
k_poff: db "poff",0
k_hon:  db "hon",0
k_hoff: db "hoff",0
k_c8pon: db "c8pon",0
k_c8poff: db "c8poff",0
k_c8hon: db "c8hon",0
k_c8hoff: db "c8hoff",0
