; nxsuite/g1.asm - G1 CPU: timing per speed and memory kind, house raster method only (spec section 3 G1).
; Lives in bank 2 (slot 3 is switched to the data page or to pages $0E / $0F around a timed row).
; A row: (g1_body) bytes copied 256 times (or once for a repeating instruction), called K times per pass,
; 4 passes, 5 runs (trow); result = clocks of that speed per instruction = d x (tr_num) / cal, with K
; scaled by 2^speed so every row fills about the same number of lines at every speed.
; GPL-3.0-or-later.

; ---------------------------------------------------------------- the row runner
; set: g1_body / g1_len, g1_single (0 = 256 copies, 1 = once), g1_spd (0-3), g1_div (2048 x 2^spd >> div
; instructions are timed), g1_slot3 (0 = leave slot 3, else the page to put there), g1_at (where the block
; is built; 0 = TBUF / TBUF2, else there and +$300), (mini) the registers. -> tr_mean / tr_min / tr_max
g1row:  ld hl,(g1_body) : ld (mk_body),hl
        ld a,(g1_len) : ld (mk_bodyl),a
        ld hl,256 : ld a,(g1_single) : or a : jr z,.c
        ld hl,1
.c:     ld (mk_n),hl
        ; K and the numerator
        ld a,(g1_single) : or a : ld b,8 : jr z,.k
        ld b,1
.k:     ld a,(g1_spd) : or a : jr z,.k2
.k1:    sla b : dec a : jr nz,.k1
.k2:    ld a,(g1_div) : or a : jr z,.k4
.k3:    srl b : dec a : jr nz,.k3
.k4:    ld a,b : ld (tr_k),a
        ld hl,1900 : ld a,(g1_div) : or a : jr z,.n2
.n1:    add hl,hl : dec a : jr nz,.n1
.n2:    ld (tr_num),hl
g1row_k:                                        ; (tr_k / tr_num set by the caller)
        ld a,(g1_slot3) : or a : jr z,.s
        nextreg $53,a
.s:     ld de,(g1_at) : ld a,d : or e : jr nz,.at
        call mkrow : jr .run
.at:    push de : call mkblk : pop hl : ld (tr_blk),hl
        ld de,$300 : add hl,de : ex de,hl : ld (tr_emp),de
        ld hl,(mk_n) : push hl : ld hl,0 : ld (mk_n),hl
        call mkblk
        pop hl : ld (mk_n),hl
.run:   ld a,(g1_spd) : ld (mshift),a
        nextreg $07,a
        call trow
        ld a,(spd0) : nextreg $07,a
        nextreg $53,11
        ret
g1_body: dw 0
g1_len: db 0
g1_single: db 0
g1_spd: db 0
g1_div: db 0
g1_slot3: db 0
g1_at:  dw 0

; HL = body, A = length, B = speed: 256 copies, slot 3 = (g1p3), block in TBUF, no prologue -> tr_mean
g1plain:
        ld (g1_body),hl : ld (g1_len),a
        ld a,b : ld (g1_spd),a
        xor a : ld (g1_single),a : ld (g1_div),a : ld (mk_prol),a : ld (mk_epil),a
        ld hl,0 : ld (g1_at),hl
        ld a,(g1p3) : ld (g1_slot3),a
        jp g1row
g1p3:   db DATAPAGE

; registers before each call (F A C B E D L H)
g1i_data: db 0,0, $00,$08, $00,$68, $00,$60     ; HL = $6000, DE = $6800, BC = 2048 (LDIR 2K)
g1i_h4: db 0,0, 0,0, 0,0, $00,$40               ; HL = $4000 (bank 5)
g1i_h8: db 0,0, 0,0, 0,0, $00,$80               ; HL = $8000 (bank 2)
g1i_out: db 0,$7F, $3B,$24, 0,0, $00,$60        ; BC = $243B, A = $7F, HL = $6000
g1i_in: db 0,0, $3B,$25, 0,0, $00,$60           ; BC = $253B
g1i_fe: db 0,$FF, 0,0, 0,0, $00,$60             ; A = $FF: IN A,($FE) reads port $FFFE
g1i_l2: db 0,0, $00,$04, $00,$F0, $00,$80       ; LDIR 1K $8000 (bank 2) -> $F000 (bank 0)

; bodies
b_nop:  nop
b_lda:  ld a,($6000)
b_pop:  pop bc
b_ldix: ld (ix+5),$AA
b_ldir: ldir
b_ldha: ld a,(hl)
b_lhla: ld (hl),a
b_outc: out (c),a
b_inc:  in a,(c)
b_infe: in a,($FE)
b_ed00: db $ED,$00
b_ed63: db $ED,$63,$00,$60
b_ed6b: db $ED,$6B,$00,$60
b_dd00: db $DD,$00
pro_pop: ld (g1sp),sp : ld sp,$6000
PRO_POP_LEN equ $-pro_pop
epi_pop: ld sp,(g1sp)
EPI_POP_LEN equ $-epi_pop
g1sp:   dw 0

; the C01 rows at speed B -> g1r (5 means x 100, dwords): NOP, LD A,(nn), POP BC, LD (IX+d),n, LDIR / byte;
; g1x = the NOP row's min / max
c01rows:
        ld a,b : ld (.s),a
        ld a,DATAPAGE : ld (g1p3),a
        ld ix,$6000
        ld hl,zini : ld (mini),hl
        ld hl,b_nop : ld a,(.s) : ld b,a : ld a,1 : call g1plain
        ld de,g1r : call .st
        ld hl,tr_min : ld de,g1x : ld bc,8 : ldir
        ld hl,b_lda : ld a,(.s) : ld b,a : ld a,3 : call g1plain
        ld de,g1r+4 : call .st
        ld hl,b_pop : ld (g1_body),hl : ld a,1 : ld (g1_len),a
        ld a,(.s) : ld (g1_spd),a
        xor a : ld (g1_single),a : ld (g1_div),a
        ld hl,pro_pop : ld (mk_pro),hl : ld a,PRO_POP_LEN : ld (mk_prol),a
        ld hl,epi_pop : ld (mk_epi),hl : ld a,EPI_POP_LEN : ld (mk_epil),a
        ld hl,0 : ld (g1_at),hl : ld a,DATAPAGE : ld (g1_slot3),a
        call g1row
        ld de,g1r+8 : call .st
        ld ix,$6000
        ld hl,b_ldix : ld a,(.s) : ld b,a : ld a,4 : call g1plain
        ld de,g1r+12 : call .st
        ld hl,g1i_data : ld (mini),hl
        ld hl,b_ldir : ld (g1_body),hl : ld a,2 : ld (g1_len),a
        ld a,1 : ld (g1_single),a
        ld a,(.s) : ld (g1_spd),a
        call g1row
        ld hl,zini : ld (mini),hl
        ld de,g1r+16
.st:    ld hl,tr_mean : ld bc,4 : ldir : ret
.s:     db 0
g1r:    ds 20
g1x:    ds 8

; ---------------------------------------------------------------- C01
t_c01:  ld b,3 : call c01rows
        call res_g1nop
        ld hl,u_clocks : call res_unit
        ld hl,c01k : call g1keys
        ; decide: every row within 0.2 of the 3.5 MHz T -> PASS no-wait; NOP 5 +- 0.2 -> wait; else other
        ld hl,g1r : ld de,c01t : ld b,5 : call within20
        ld hl,w_nowait : jr nc,.o
        ld a,ST_PASS : ld (R_st),a : jr .k
.o:     ld hl,(g1r) : ld de,500-20 : or a : sbc hl,de : jr c,.x
        ld hl,(g1r) : ld de,500+21 : or a : sbc hl,de : jr nc,.x
        ld hl,w_wait : jr .k
.x:     ld hl,w_other
.k:     push hl : ld hl,k_choice : call ex_k : pop hl : jp wstr
c01t:   dw 400,1300,1000,1900,2100
c01k:   dw k_nop,k_lda,k_pop,k_ldix,k_ldir
k_nop:  db "nop",0
k_lda:  db "lda",0
k_pop:  db "pop",0
k_ldix: db "ldixn",0
k_ldir: db "ldir",0
k_choice: db "choice",0
w_nowait: db "no-wait",0
w_wait: db "wait",0
w_other: db "other",0
; v = the NOP row's mean, min, max (5 runs)
res_g1nop:
        ld hl,(g1r) : ld de,(g1r+2) : call res_num
        ld hl,g1x : ld de,R_min : ld bc,8 : ldir
        ld hl,5 : ld (R_n),hl
        ret
; HL = 5 key pointers -> " key=<g1r[i]>"
g1keys: ld b,5 : ld de,g1r
.l:     push bc : push de : push hl
        ld e,(hl) : inc hl : ld d,(hl) : ex de,hl : call ex_k
        pop hl : pop de : push de : push hl
        ex de,hl : ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        ex de,hl : call wfix
        pop hl : pop de : pop bc
        inc hl : inc hl : inc de : inc de : inc de : inc de
        djnz .l
        ret
; HL = values (dwords x 100), DE = expected (words x 100), B = count -> carry if all within 0.20
within20:
.l:     push bc : push hl : push de
        ld c,(hl) : inc hl : ld b,(hl)            ; low word of the value (values < 65536)
        ex de,hl : ld e,(hl) : inc hl : ld d,(hl) ; DE = expected
        ld h,b : ld l,c : or a : sbc hl,de        ; value - expected
        jr nc,.p
        ld a,h : cpl : ld h,a : ld a,l : cpl : ld l,a : inc hl
.p:     ld de,21 : or a : sbc hl,de
        pop de : pop hl : pop bc
        ret nc                                    ; off by > 0.20: no carry
        inc hl : inc hl : inc hl : inc hl : inc de : inc de
        djnz .l
        scf : ret

; ---------------------------------------------------------------- C06: the C01 rows at 7 and 14 MHz
t_c06:  ld b,1 : call c01rows
        call res_g1nop
        ld hl,u_clocks : call res_unit
        ld hl,c06k7 : call g1keys
        ld b,2 : call c01rows
        ld hl,c06k14 : jp g1keys
c06k7:  dw k_nop7,k_lda7,k_pop7,k_ldix7,k_ldir7
c06k14: dw k_nop14,k_lda14,k_pop14,k_ldix14,k_ldir14
k_nop7: db "nop7",0
k_lda7: db "lda7",0
k_pop7: db "pop7",0
k_ldix7: db "ldixn7",0
k_ldir7: db "ldir7",0
k_nop14: db "nop14",0
k_lda14: db "lda14",0
k_pop14: db "pop14",0
k_ldix14: db "ldixn14",0
k_ldir14: db "ldir14",0

; ---------------------------------------------------------------- C02: code in bank 5 ($6800), 28 MHz
t_c02:  ld hl,zini : ld (mini),hl
        ld hl,b_nop : ld (g1_body),hl : ld a,1 : ld (g1_len),a
        xor a : ld (g1_single),a : ld (g1_div),a : ld (g1_slot3),a : ld (mk_prol),a : ld (mk_epil),a
        ld a,3 : ld (g1_spd),a
        ld hl,B5CODE : ld (g1_at),hl
        call g1row
        call res_trow
        ld hl,u_clocks : call res_unit
        ; LD A,(HL) with HL in bank 5, code in bank 2
        ld hl,g1i_h4 : ld (mini),hl
        xor a : ld (g1p3),a
        ld hl,b_ldha : ld a,1 : ld b,3 : call g1plain
        ld a,DATAPAGE : ld (g1p3),a
        ld hl,k_ldhl : jp ex_kmean
k_ldhl: db "ldhl",0

; ---------------------------------------------------------------- C03 / C04: page $0E / $0F in slot 3
; (bank 7 is in the .nex, so these pages are the suite's own)
t_c03:  ld a,$0E : jr c0304
t_c04:  ld a,$0F
c0304:  ld (g1p3),a
        ld hl,zini : ld (mini),hl
        ld hl,b_nop : ld (g1_body),hl : ld a,1 : ld (g1_len),a
        xor a : ld (g1_single),a : ld (g1_div),a : ld (mk_prol),a : ld (mk_epil),a
        ld a,3 : ld (g1_spd),a
        ld a,(g1p3) : ld (g1_slot3),a
        ld hl,$6000 : ld (g1_at),hl
        call g1row
        call res_trow
        ld hl,u_clocks : call res_unit
        ld hl,g1i_data : ld (mini),hl                ; HL = $6000 in that page, code in bank 2
        ld hl,b_ldha : ld a,1 : ld b,3 : call g1plain
        ld a,DATAPAGE : ld (g1p3),a
        ld hl,k_ldhl : jp ex_kmean

; ---------------------------------------------------------------- C05: writes and I/O at 28 MHz
t_c05:  ld hl,g1i_data : ld (mini),hl
        ld hl,b_lhla : ld a,1 : ld b,3 : call g1plain
        call res_trow
        ld hl,u_clocks : call res_unit
        ld hl,g1i_out : ld (mini),hl
        ld hl,b_outc : ld a,2 : ld b,3 : call g1plain
        ld hl,k_outc : call ex_kmean
        ld hl,g1i_in : ld (mini),hl
        ld hl,b_inc : ld a,2 : ld b,3 : call g1plain
        ld hl,k_inc : jp ex_kmean
k_outc: db "outc",0
k_inc:  db "inc",0

; ---------------------------------------------------------------- C07: speed switch cost
; 128 x (NEXTREG 7,3 ; NEXTREG 7,0) (64 copies called twice) against 128 x (NEXTREG 7,0 ; NEXTREG 7,0), from 3.5 MHz: extra time
; per pair in 3.5 MHz T
b_sw:   nextreg $07,3 : nextreg $07,0
b_same: nextreg $07,0 : nextreg $07,0
t_c07:  ld hl,zini : ld (mini),hl
        xor a : ld (mk_prol),a : ld (mk_epil),a
        ld hl,64 : ld (mk_n),hl
        ld hl,b_sw : ld (mk_body),hl : ld a,8 : ld (mk_bodyl),a
        ld de,TBUF : call mkblk
        ld hl,b_same : ld (mk_body),hl
        ld de,TBUF+$300 : call mkblk
        ASSERT TBUF+$300+64*8+1 <= TBUF_END
        ld hl,TBUF : ld (tr_blk),hl : ld hl,TBUF+$300 : ld (tr_emp),hl
        ld a,2 : ld (tr_k),a                        ; 64 pairs called twice = 128 pairs = 2048 / 16
        ld hl,1900*16 : ld (tr_num),hl
        xor a : ld (mshift),a : nextreg $07,0
        call trow
        ld a,(spd0) : nextreg $07,a
        call res_trow
        ld hl,u_t : jp res_unit

; ---------------------------------------------------------------- C08: bank 5 contention at 3.5 MHz
; LD A,(HL), HL = $4000 against HL = $8000, started at line 0 (2048 accesses end before line ~120);
; then with $08 bit 6 = 1 (contention off; read-modify-write, restored), then at 7 MHz.
; -> v = extra T per access at 3.5 MHz, off = with bit 6, c7 = at 7 MHz (in 7 MHz clocks)
t_c08:  xor a : ld (g1p3),a
        xor a : call .pair : call .ext                ; 3.5 MHz
        call res_num : ld hl,5 : ld (R_n),hl
        ld hl,u_t : call res_unit
        ld a,$08 : call rdreg : ld (.r8),a
        or $40 : and $7F : nextreg $08,a             ; bit 6 = contention off (bit 7 written 0: no effect)
        xor a : call .pair : call .ext
        push de : push hl
        ld a,(.r8) : and $7F : nextreg $08,a          ; bit 6 back (bit 7 untouched)
        ld hl,k_off : call ex_k : pop hl : pop de : call wfix
        ld a,1 : call .pair : call .ext
        push de : push hl : ld hl,k_c7 : call ex_k : pop hl : pop de : call wfix
        ld a,DATAPAGE : ld (g1p3),a
        ret
.pair:  ld (.s),a
        ld hl,g1i_h4 : ld (mini),hl
        ld hl,b_ldha : ld a,(.s) : ld b,a : ld a,1 : call g1plain
        ld hl,tr_mean : ld de,.a4 : ld bc,4 : ldir
        ld hl,g1i_h8 : ld (mini),hl
        ld hl,b_ldha : ld a,(.s) : ld b,a : ld a,1 : jp g1plain
; -> DEHL = (.a4) - tr_mean (signed)
.ext:   ld hl,(.a4) : ld bc,(tr_mean) : or a : sbc hl,bc : push hl
        ld hl,(.a4+2) : ld bc,(tr_mean+2) : sbc hl,bc : ex de,hl : pop hl
        ret
.s:     db 0
.r8:    db 0
.a4:    ds 4
k_off:  db "off",0
k_c7:   db "c7",0

; ---------------------------------------------------------------- C09: $08 bit 6 read back after a write
; DI, at the start of line 20 write $08 with bit 6 flipped, then read $08 every 23 T (unrolled) 24 times;
; v = T from the NEXTREG to the first read showing the new bit (999 = not within 24 reads)
t_c09:  nextreg $07,0
        ld a,$08 : call rdreg : ld (.r8),a
        xor $40 : and $7F : ld (.nv),a
        call frame_sync : ld a,20 : call sync_lsb
        ld a,$08 : ld bc,$243B : out (c),a : inc b
        ld hl,WORK
        ld a,(.nv) : nextreg $08,a
        DUP 24
        in a,(c) : ld (hl),a : inc l
        EDUP
        ld a,(.r8) : and $7F : nextreg $08,a
        ld a,(spd0) : nextreg $07,a
        ld hl,WORK : ld b,0 : ld a,(.nv) : and $40 : ld c,a
.f:     ld a,(hl) : and $40 : cp c : jr z,.got
        inc hl : inc b : ld a,b : cp 24 : jr nz,.f
        ld hl,999 : jr .r
.got:   ld l,b : ld h,0 : ld d,h : ld e,l
        add hl,hl : add hl,de : add hl,hl : add hl,hl : add hl,hl : or a : sbc hl,de   ; x 23
.r:     call res_int
        ld hl,u_t : jp res_unit
.r8:    db 0
.nv:    db 0

; ---------------------------------------------------------------- C10: IN A,($FE) display vs border lines
; 1024 reads at 3.5 MHz started at line 0 (display) and at line 193 (border; ends before line 243)
t_c10:  ld hl,g1i_fe : ld (mini),hl
        xor a : ld (msline),a
        call .row
        call res_trow
        ld hl,u_t : call res_unit
        ld a,193 : ld (msline),a
        call .row
        xor a : ld (msline),a
        ld hl,k_border : jp ex_kmean
.row:   ld hl,b_infe : ld (g1_body),hl : ld a,2 : ld (g1_len),a
        xor a : ld (g1_single),a : ld (g1_spd),a : ld (mk_prol),a : ld (mk_epil),a : ld (g1_slot3),a
        ld a,1 : ld (g1_div),a                        ; 1024
        ld hl,0 : ld (g1_at),hl
        jp g1row
k_border: db "border",0

; ---------------------------------------------------------------- C11: undocumented opcodes at 3.5 MHz
t_c11:  ld hl,g1i_data : ld (mini),hl
        ld hl,b_ed00 : ld a,2 : ld b,0 : call g1plain
        call res_trow
        ld hl,u_t : call res_unit
        ld hl,b_ed63 : ld a,4 : ld b,0 : call g1plain
        ld hl,k_ed63 : call ex_kmean
        ld hl,b_ed6b : ld a,4 : ld b,0 : call g1plain
        ld hl,k_ed6b : call ex_kmean
        ld hl,b_dd00 : ld a,2 : ld b,0 : call g1plain
        ld hl,k_dd00 : jp ex_kmean
k_ed63: db "ed63",0
k_ed6b: db "ed6b",0
k_dd00: db "dd00",0

; ---------------------------------------------------------------- C12: OUT (C),0 writes 0
t_c12:  nextreg $7F,$55
        ld bc,$243B : ld a,$7F : out (c),a : inc b
        db $ED,$71                                   ; OUT (C),0
        ld a,$7F : call rdreg
        call res_hex
        ld a,(R_v) : or a
        ld a,ST_PASS : jr z,.s
        ld a,ST_FAIL                                ; the claim: OUT (C),0 writes 0
.s:     ld (R_st),a
        ret

; ---------------------------------------------------------------- C13: block I/O flags on port (B,$FE)
; B in 1,$80,$81,0,$10,$11 x F in 0,$FF: OUTI, OUTD, INI, IND (12 F values each, as hex pairs in that
; order), OTIR with B = 2 from F = 0 and $FF. The source byte is 0 (black border, silent); INI / IND read
; the keyboard into the scratch area. Border back to blue.
t_c13:  ld hl,SCRATCH : ld de,SCRATCH+1 : ld bc,63 : ld (hl),0 : ldir
        ld hl,k_outi : ld de,ins_outi : call .one
        ld hl,k_outd : ld de,ins_outd : call .one
        ld hl,k_ini : ld de,ins_ini : call .one
        ld hl,k_ind : ld de,ins_ind : call .one
        ld hl,k_otir : call ex_k
        ld a,2 : ld (.b),a
        ld de,ins_otir : xor a : call .run : call whex2
        ld de,ins_otir : ld a,$FF : call .run : call whex2
        ld a,1 : out ($FE),a
        ld hl,50 : jp res_int                       ; v = number of cases
; HL = key, DE = instruction routine: 12 cases
.one:   push de : call ex_k : pop de
        ld hl,c13b : ld b,6
.c:     push bc : push hl : push de
        ld a,(hl) : ld (.b),a
        xor a : call .run : call whex2
        pop de : push de
        ld a,$FF : call .run : call whex2
        pop de : pop hl : pop bc
        inc hl : djnz .c
        ret
; DE = routine, A = F before, (.b) = B -> A = F after
.run:   ld (.f),a : ld (.jp+1),de
        ld a,(.b) : ld b,a
        ld a,(.f) : ld l,a : ld h,0 : push hl : pop af   ; F set, A = 0 (the byte sent)
        ld hl,SCRATCH+16 : ld c,$FE
.jp:    call 0
        push af : pop hl : ld a,l
        ret
.b:     db 0
.f:     db 0
ins_outi: outi : ret
ins_outd: outd : ret
ins_ini: ini : ret
ins_ind: ind : ret
ins_otir: otir : ret
c13b:   db 1,$80,$81,0,$10,$11
k_outi: db "outi",0
k_outd: db "outd",0
k_ini:  db "ini",0
k_ind:  db "ind",0
k_otir: db "otir2",0

; ---------------------------------------------------------------- C14: undocumented flag bits 5 / 3
; BIT 0,(HL) with (HL) = $28, SCF, CCF, CPI ((HL) = $28, BC = 2), IN A,(C) (NextReg $7F = A, read through
; port $253B), LD A,I (I = A, interrupts off); each from (A, F) = ($28,0) ($28,$FF) ($D7,0) ($D7,$FF):
; 4 hex pairs per instruction
t_c14:  ld a,$28 : ld (SCRATCH),a
        ld hl,k_bit : ld de,i14_bit : call .one
        ld hl,k_scf : ld de,i14_scf : call .one
        ld hl,k_ccf : ld de,i14_ccf : call .one
        ld hl,k_cpi : ld de,i14_cpi : call .one
        ld hl,k_inc : ld de,i14_in : call .one
        ld hl,k_ldai : ld de,i14_ldai : call .one
        ld a,(launch_i) : ld i,a
        ld hl,24 : jp res_int
.one:   push de : call ex_k : pop de
        ld hl,c14af : ld b,4
.c:     push bc : push hl : push de
        ld a,(hl) : ld (.a),a : inc hl : ld a,(hl) : ld (.f),a
        ld a,(.a) : nextreg $7F,a : ld i,a
        ld (.jp+1),de
        ld bc,$243B : ld a,$7F : out (c),a           ; NextReg $7F selected for IN A,(C)
        ld a,(.f) : ld l,a : ld a,(.a) : ld h,a : push hl : pop af
        ld hl,SCRATCH
.jp:    call 0
        push af : pop hl : ld a,l : call whex2
        pop de : pop hl : pop bc
        inc hl : inc hl : djnz .c
        ret
.a:     db 0
.f:     db 0
c14af:  db $28,$00, $28,$FF, $D7,$00, $D7,$FF
i14_bit: bit 0,(hl) : ret
i14_scf: scf : ret
i14_ccf: ccf : ret
i14_cpi: ld bc,2 : cpi : ret
i14_in: ld bc,$253B : in a,(c) : ret
i14_ldai: ld a,i : ret
k_bit:  db "bit",0
k_scf:  db "scf",0
k_ccf:  db "ccf",0
k_cpi:  db "cpi",0
k_ldai: db "ldai",0

; ---------------------------------------------------------------- C15: Layer 2 visible vs CPU at 28 MHz
; LDIR 1K x 8 ($8000 bank 2 -> $F000 bank 0) from line 0, Layer 2 320x256 visible (bank 22: $12 = 22,
; $70 = $10, $69 bit 7) against Layer 2 off; $12 / $70 / $69 restored. PASS if equal within 0.05.
t_c15:  ld hl,g1i_l2 : ld (mini),hl
        call .row : ld hl,tr_mean : ld de,.off : ld bc,4 : ldir
        nextreg $12,22
        nextreg $70,$10
        ld a,$69 : call rdreg : or $80 : nextreg $69,a
        call .row
        ld a,(NRSNAP+$69) : nextreg $69,a
        ld a,(NRSNAP+$70) : nextreg $70,a
        ld a,(NRSNAP+$12) : nextreg $12,a
        call res_trow
        ld hl,u_clocks : call res_unit
        ld hl,k_off : call ex_k : ld hl,(.off) : ld de,(.off+2) : call wfix
        ld hl,(tr_mean) : ld de,(.off) : or a : sbc hl,de : jr nc,.p
        ld a,h : cpl : ld h,a : ld a,l : cpl : ld l,a : inc hl
.p:     ld de,6 : or a : sbc hl,de : ret nc
        ld a,ST_PASS : ld (R_st),a
        ret
.row:   ld hl,b_ldir : ld (g1_body),hl : ld a,2 : ld (g1_len),a
        ld hl,b_ldir : ld (mk_body),hl : ld a,2 : ld (mk_bodyl),a
        ld hl,1 : ld (mk_n),hl
        ld a,3 : ld (g1_spd),a
        xor a : ld (g1_slot3),a : ld (mk_prol),a : ld (mk_epil),a
        ld hl,0 : ld (g1_at),hl
        ld a,8 : ld (tr_k),a                        ; 1K x 8 = 2048 x 8 / 2
        ld hl,1900*2 : ld (tr_num),hl
        jp g1row_k
.off:   ds 4
