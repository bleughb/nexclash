; nxsuite/g3b.asm - G3 IRQ, stage 2: I04 I05 I06 I08 I10 I14 I18 I19 I20 I22 I23 I24. GPL-3.0-or-later.
; Same overlay page as g3.asm (the tables at $F800-$FFFF). Extra use of that area: I04 / I05 build their
; handler at G3V ($FEFE, over the JP; g3_tables writes the JP back), I08 captures 128 reads at $FF80.
; DMA tests (I22-I24) copy bank 5 ($4000-$7FFF) into suite pages 36 / 37 mapped at $0000-$3FFF (MMU 0 / 1,
; put back from the launch snapshot); programs as nextbench (port $6B, $C3 first, $83 $C3 + a read last).

I08B    equ $FF80
        MODULE g3x
        INCLUDE "g3com.asm"
k_line: db "line",0
k_runs: db "runs",0

; ---------------------------------------------------------------- shared helpers
; HL = line -> returns (interrupts off) when the raster reaches that line
g3_atline:
        push hl : call frame_sync : pop hl
        ld a,h : or a : jr z,.lo
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.m:     in a,(c) : rra : jr nc,.m
.lo:    ld a,l : jp sync_lsb
; HL = line, DE = lines -> HL = the line DE lines earlier (wrapping at the frame length)
g3_before:
        or a : sbc hl,de : ret nc
        ld de,(flines) : inc de : add hl,de : ret
; -> HL = the smallest line read in a pulse-mode ULA handler over 3 frames (the interrupt line)
g3_ulaline:
        ld hl,g3h_rec : call g3_tables
        call g3_zero : call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,3 : call g3_fei
        di
        ld hl,(g3lmin) : ret
; HL signed x DE -> DEHL signed; HL signed -> DEHL = x 100
g3_sx100:
        ld de,100
g3_smul:
        bit 7,h : jr z,.p
        call g3_negh : ld b,h : ld c,l : call mul16 : jp neg32
.p:     ld b,h : ld c,l : jp mul16
g3_negh:
        xor a : sub l : ld l,a : ld a,0 : sbc a,h : ld h,a : ret
; key HL, signed integer DE
ex_ksd: push de : call ex_k : pop hl : call g3_sx100 : jp wfix
; key HL, byte A as a decimal
ex_kad: ld e,a : ld d,0 : jp ex_kd

; DMA: HL = program, B = length (sent after a $C3 reset; not started)
g3_dma: ld a,$C3 : out ($6B),a
        ld c,$6B : otir : ret
g3_dmaoff:
        ld a,$83 : out ($6B),a : ld a,$C3 : out ($6B),a : in a,($6B) : ret
g3_map: nextreg $50,36 : nextreg $51,37 : ret
g3_unmap:
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a : ret
; HL = src, DE = dst, BC = length: dst = NOT src (so a copied byte always shows)
g3_ncpy:
        ld a,(hl) : cpl : ld (de),a : inc hl : inc de
        dec bc : ld a,b : or c : jr nz,g3_ncpy
        ret
; HL = dst, DE = src, BC = length -> HL = bytes that differ
g3_cmp: push hl : pop ix : ld hl,0
.l:     ld a,(de) : cp (ix+0) : jr z,.s
        inc hl
.s:     inc ix : inc de : dec bc : ld a,b : or c : jr nz,.l
        ret
; continuous 16K $4000 -> $0000; burst P = 100 2K $4000 -> $0000
i22p:   db $83, $7D, $00,$40, $00,$40, $54,2, $50,2, $AD, $00,$00, $82, $CF
i22p_e:
i23p:   db $83, $7D, $00,$40, $00,$08, $54,2, $50,$22,100, $CD, $00,$00, $82, $CF
i23p_e:

; ---------------------------------------------------------------- I04 / I05 pulse length (re-entry sweep)
; Pulse IM 2 (bus $FF -> table $FD -> G3V). The handler is built at G3V: INC IX (10 cycles, no flags), k
; cycles of padding (NOP 4, INC DE 6, LD D,0 7, NOP NOP 8, LD R,A 9; DE / R are not used by the main loop),
; EI, 4 x NOP, RET. Main loop: 5 frames from a frame start, polling $1E bit 0 (A F BC HL only). 7 or more
; runs in 5 frames = the pulse was still low after EI: re-entry. k = 0 and 4..60 cycles x 2^speed in steps of
; 2^speed; k = 1-3 and 5 cannot be built (spec asks for them by entry offset: not built, written skip=).
; Part 2: handler = 9 x IN r,(C) of NextReg $22 (12 cycles each, from the first instruction), RET: the
; largest number of leading reads with bit 7 set over 5 frames.
; A = speed -> HL = largest re-entering k (-1 none), C = how many k re-entered, A = part 2 reads
i04run: nextreg $07,a
        ld hl,1 : or a : jr z,.s0
        ld b,a
.sh:    add hl,hl : djnz .sh
.s0:    ld (.st),hl
        ld b,h : ld c,l : ld de,60 : call mul16 : ld (.end),hl
        ld hl,-1 : ld (.km),hl : xor a : ld (.nr),a
        ld hl,g3h_cnt : call g3_tables
        call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld hl,0 : ld (.k),hl
.kl:    ld de,(.k) : call i04mk : jr c,.nx
        call i04five
        push ix : pop hl : ld de,7 : or a : sbc hl,de : jr c,.nx
        ld hl,(.k) : ld (.km),hl : ld hl,.nr : inc (hl)
.nx:    ld hl,(.k) : ld de,(.st) : add hl,de : ld (.k),hl
        ex de,hl : ld hl,(.end) : or a : sbc hl,de : jr nc,.kl
        call i04p22
        ld hl,(.km) : ld bc,(.nr)
        ret
.st:    dw 0
.end:   dw 0
.km:    dw 0
.nr:    db 0,0
.k:     dw 0
; DE = k -> the handler at G3V; carry = k cannot be built
i04mk:  ld hl,G3V : ld (hl),$DD : inc hl : ld (hl),$23 : inc hl     ; INC IX
        ld a,d : or e : jr z,.tail
        ex de,hl                                    ; HL = cycles left, DE = output
.lp:    ld a,h : or a : jr nz,.n
        ld a,l : cp 10 : jr c,.fin
.n:     xor a : ld (de),a : inc de
        ld bc,-4 : add hl,bc : jr .lp
.fin:   cp 4 : ret c
        jr nz,.n5
        xor a : ld (de),a : inc de : jr .t2
.n5:    cp 5 : jr nz,.n6
        scf : ret
.n6:    cp 6 : jr nz,.n7
        ld a,$13 : ld (de),a : inc de : jr .t2      ; INC DE
.n7:    cp 7 : jr nz,.n8
        ld a,$16 : ld (de),a : inc de : xor a : ld (de),a : inc de : jr .t2   ; LD D,0
.n8:    cp 8 : jr nz,.n9
        xor a : ld (de),a : inc de : ld (de),a : inc de : jr .t2
.n9:    ld a,$ED : ld (de),a : inc de : ld a,$4F : ld (de),a : inc de        ; LD R,A
.t2:    ex de,hl
.tail:  ld (hl),$FB : inc hl
        ld b,4
.t:     ld (hl),0 : inc hl : djnz .t
        ld (hl),$C9
        or a : ret
; -> IX = handler runs over 5 frames (interrupts off after)
i04five:
        di
        call g3_ack
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.f1:    in a,(c) : rra : jr nc,.f1
.f0:    in a,(c) : rra : jr c,.f0
        ld ix,0 : ld hl,$0500
        ei
.l:     in a,(c) : and 1 : cp l : jr z,.l
        ld l,a : or a : jr nz,.l
        dec h : jr nz,.l
        di
        ret
i04p:   in d,(c) : in e,(c) : in h,(c) : in l,(c) : in a,(c)
        exx : in d,(c) : in e,(c) : in h,(c) : in l,(c) : exx
        ret
i04p_e:
; -> A = the most leading reads with $22 bit 7 set (of 9) over 5 frames
i04p22: exx : push bc : push de : push hl : exx
        ld hl,i04p : ld de,G3V : ld bc,i04p_e-i04p : ldir
        xor a : ld (.mx),a
        ld a,5 : ld (.n),a
.f:     di : call g3_ack
        ld bc,$243B : ld a,$22 : out (c),a : inc b
        exx : ld bc,$253B : exx
        ei : halt
        ld (.rb+4),a
        ld a,d : ld (.rb),a : ld a,e : ld (.rb+1),a : ld a,h : ld (.rb+2),a : ld a,l : ld (.rb+3),a
        exx
        ld a,d : ld (.rb+5),a : ld a,e : ld (.rb+6),a : ld a,h : ld (.rb+7),a : ld a,l : ld (.rb+8),a
        exx
        ld hl,.rb : ld b,9 : ld c,0
.c:     bit 7,(hl) : jr z,.e
        inc c : inc hl : djnz .c
.e:     ld a,(.mx) : cp c : jr nc,.k
        ld a,c : ld (.mx),a
.k:     ld hl,.n : dec (hl) : jr nz,.f
        di
        exx : pop hl : pop de : pop bc : exx
        ld hl,g3h_cnt : call g3_tables              ; the JP at G3V back
        ld a,(.mx) : ret
.mx:    db 0
.n:     db 0
.rb:    ds 9
; v = largest re-entering k at 3.5 MHz (T of padding after the 10 T INC IX; -1 = none)
@t_i04:  xor a : call i04run
        push af : push bc
        call g3_sx100 : call res_num
        ld hl,u_t : call res_unit
        pop bc : ld a,c : ld hl,k_nre : call ex_kad
        pop af : ld hl,k_hi22 : call ex_kad
        ld hl,k_skip : call ex_k : ld hl,w_k1235 : jp wstr
; v = largest re-entering k at 28 MHz (clocks); k7 / k14 the other speeds, h7..h28 part 2
@t_i05:  ld a,1 : call i04run : ld (.k),hl : ld (.h),a
        ld a,2 : call i04run : ld (.k+2),hl : ld (.h+1),a
        ld a,3 : call i04run : ld (.k+4),hl : ld (.h+2),a
        ld hl,(.k+4) : call g3_sx100 : call res_num
        ld hl,u_clocks : call res_unit
        ld de,(.k) : ld hl,k_k7 : call ex_ksd
        ld de,(.k+2) : ld hl,k_k14 : call ex_ksd
        ld a,(.h) : ld hl,k_h7 : call ex_kad
        ld a,(.h+1) : ld hl,k_h14 : call ex_kad
        ld a,(.h+2) : ld hl,k_h28 : jp ex_kad
.k:     ds 6
.h:     ds 3
k_nre:  db "reentered",0
k_hi22: db "hi22",0
k_skip: db "skip",0
w_k1235: db "k1-3,5",0
k_k7:   db "k7",0
k_k14:  db "k14",0
k_h7:   db "hi22_7",0
k_h14:  db "hi22_14",0
k_h28:  db "hi22_28",0

; ---------------------------------------------------------------- 16 indexed handlers (I06, I18)
; handler i = push af : ld a,i : jr i06c; logs the index (first 8) and the last one
i06h:
i06n = 0
        DUP 16
        push af : ld a,i06n : jr i06c
i06n = i06n + 1
        EDUP
i06c:   ld (i06last),a
        push hl : push af
        ld a,(i06cnt) : cp 8 : jr nc,.x
        ld hl,i06log : add hl,a : inc a : ld (i06cnt),a
        pop af : push af : ld (hl),a
.x:     pop af : pop hl
        ld a,1 : ld (g3int),a
        pop af : ei : reti
i06last: db 0
i06cnt: db 0
i06log: ds 8
; HL = table position: 16 words -> the 16 handlers
i06tab: ld de,i06h : ld b,16
.l:     ld (hl),e : inc hl : ld (hl),d : inc hl
        push hl : ld hl,5 : add hl,de : ex de,hl : pop hl
        djnz .l
        ret

; ---------------------------------------------------------------- I06 hardware IM2 vector layout
; $C0 = $E1 (bit 3 as found), I = $FC, 16 handlers at $FCE0-$FCFF; ULA, line 100, CTC0 (tc 255) one at a
; time over 3 frames. v = ULA offset; line / ctc0 the others ($FF = none ran). PASS if ULA = $F6.
@t_i06:  nextreg $07,3
        ld hl,g3h_wrong : call g3_hwtab
        ld hl,G3HW+$E0 : call i06tab
        ld a,G3HW>>8 : ld i,a
        xor a : call .one : ld (.r),a
        ld a,1 : call .one : ld (.r+1),a
        ld a,2 : call .one : ld (.r+2),a
        call g3_hwoff
        ld a,(.r) : call res_hex
        ld a,(.r+1) : ld hl,k_lin : call ex_kh
        ld a,(.r+2) : ld hl,k_ctc0 : call ex_kh
        ld de,(g3wr) : ld hl,k_wrong : call ex_kd
        ld a,(.r) : cp $F6 : ret nz
        ld a,ST_PASS : ld (R_st),a : ret
; A = 0 ULA / 1 line / 2 CTC0 -> A = the vector offset of the last handler run ($FF none)
.one:   push af
        di
        nextreg $C4,0 : nextreg $C5,0 : nextreg $C6,0
        ld a,(NRSNAP+$C0) : and $08 : or $E1 : nextreg $C0,a
        call g3_ack : call g3_zero
        xor a : ld (i06cnt),a : dec a : ld (i06last),a
        im 2
        pop af
        or a : jr nz,.o1
        nextreg $C4,1 : jr .go
.o1:    dec a : jr nz,.o2
        nextreg $23,100
        ld a,(NRSNAP+$22) : and $F8 : or 6 : nextreg $22,a
        nextreg $C4,2 : jr .go
.o2:    ld bc,$183B : ld a,$87 : out (c),a : ld a,255 : out (c),a
        nextreg $C5,1
.go:    ld b,1 : call g3_fdi
        ld b,3 : call g3_fei
        di
        nextreg $C4,0 : nextreg $C5,0
        ld bc,$183B : ld a,$03 : out (c),a
        ld a,(NRSNAP+$22) : nextreg $22,a : ld a,(NRSNAP+$23) : nextreg $23,a
        call g3_ack
        ld a,(i06last) : cp $FF : ret z
        add a,a : add a,$E0 : ret
.r:     ds 3
k_lin:  db "line",0
k_ctc0: db "ctc0",0
k_wrong: db "wrong",0

; ---------------------------------------------------------------- I08 $22 bit 7 (/INT) time
; DI, 28 MHz, pulse mode: wait for $22 bit 7 = 0, then = 1 (a read every ~49 clocks), then 128 unrolled
; reads (23 clocks apart) into I08B; high time = (1 + leading reads with bit 7 set) x 23 clocks. 5 pulses
; each of the ULA interrupt and the line-100 interrupt. v / min / max = ULA (clocks); line / linemin.
@t_i08:  nextreg $07,3
        call g3_pulse
        ld a,(NRSNAP+$22) : nextreg $22,a
        call .run : ld (.u),hl : ld (.u+2),de
        nextreg $23,100
        ld a,(NRSNAP+$22) : and $F8 : or 6 : nextreg $22,a
        nextreg $C4,2
        call g3_ack
        call .run : ld (.l),hl : ld (.l+2),de
        ld a,(NRSNAP+$22) : nextreg $22,a : ld a,(NRSNAP+$23) : nextreg $23,a
        nextreg $C4,1
        call g3_ack
        ld hl,(.u) : call res_int
        ld hl,(.u+2) : call x100 : ld (R_min),hl : ld (R_min+2),de
        ld hl,(.u) : call x100 : ld (R_max),hl : ld (R_max+2),de
        ld hl,5 : ld (R_n),hl
        ld hl,u_clocks : call res_unit
        ld de,(.l) : ld hl,k_line : call ex_kd
        ld de,(.l+2) : ld hl,k_lmin : jp ex_kd
.u:     ds 4
.l:     ds 4
; -> HL = most clocks high, DE = fewest (0 / 0 = never seen high)
.run:   ld hl,0 : ld (.mx),hl : dec hl : ld (.mn),hl
        ld a,5 : ld (.n),a
.f:     ld bc,$243B : ld a,$22 : out (c),a : inc b
        ld de,0
.lo:    in a,(c) : rla : jr nc,.hi0
        dec de : ld a,d : or e : jr nz,.lo
        jp .to
.hi0:   ld de,0
.h:     in a,(c) : rla : jr c,.got
        dec de : ld a,d : or e : jr nz,.h
        jp .to
.got:   ld hl,I08B
        DUP 128
        in a,(c) : ld (hl),a : inc l
        EDUP
        ld hl,I08B : ld b,128 : ld de,1
.c:     bit 7,(hl) : jr z,.cd
        inc de : inc l : djnz .c
.cd:    ld b,d : ld c,e : ld de,23 : call mul16
        ld de,(.mx) : push hl : or a : sbc hl,de : pop hl : jr c,.m1
        ld (.mx),hl
.m1:    ld de,(.mn) : push hl : or a : sbc hl,de : pop hl : jr nc,.m2
        ld (.mn),hl
.m2:    ld hl,.n : dec (hl) : jp nz,.f
        ld hl,(.mx) : ld de,(.mn) : ret
.to:    ld hl,0 : ld de,0 : ret
.mx:    dw 0
.mn:    dw 0
.n:     db 0
k_lmin: db "linemin",0

; ---------------------------------------------------------------- I10 line interrupt position
; 3.5 MHz, hardware IM2, line interrupt n only, CTC3 free running (/16, 256: a tick = 16 clocks of 28 MHz,
; 2 T here). The handler reads CTC3 and the line LSB; the main loop (DI) then polls the line LSB until it
; is n (unrolled IN / CP / JR, 23 T apart) and reads CTC3 again. raw = T between the two CTC reads; the
; estimate of "T before line n" = raw + 61 (acknowledge 19 + handler to its read) - 35 (poll read to CTC
; read) + 11 (half the poll step) = raw + 37, +-12. 5 interrupts each at n = 0, 100, 191, last-2; a handler
; that already read line n's LSB is "late" (not in the mean). v = estimate at n = 100.
@t_i10:  nextreg $07,0
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld hl,i10h : call g3_hwtab
        xor a : ld (i10late),a
        ld hl,0 : call .one : ld (.t),hl
        ld hl,100 : call .one : ld (.t+2),hl : ld a,(i10l) : ld (.lh),a
        ld hl,191 : call .one : ld (.t+4),hl
        ld hl,(flines) : dec hl : dec hl : call .one : ld (.t+6),hl
        call g3_hwoff
        nextreg $07,3
        ld hl,(.t+2) : ld de,37 : add hl,de : call res_int
        ld hl,u_t : call res_unit
        ld hl,(.t) : ld de,37 : add hl,de : ex de,hl : ld hl,k_e0 : call ex_kd
        ld hl,(.t+4) : ld de,37 : add hl,de : ex de,hl : ld hl,k_e191 : call ex_kd
        ld hl,(.t+6) : ld de,37 : add hl,de : ex de,hl : ld hl,k_el2 : call ex_kd
        ld de,(.t+2) : ld hl,k_raw : call ex_kd
        ld a,(.lh) : ld hl,k_lh : call ex_kad
        ld a,(i10late) : ld hl,k_late : jp ex_kad
.t:     ds 8
.lh:    db 0
; HL = n -> HL = mean raw T (0 if no sample)
.one:   ld (.n),hl
        call g3_hw : nextreg $C4,2
        ld a,(.n) : nextreg $23,a
        ld a,(NRSNAP+$22) : and $F8 : or 6 : ld hl,.n+1 : or (hl) : nextreg $22,a
        ld a,G3HW>>8 : ld i,a : im 2
        ld hl,0 : ld (.sum),hl : xor a : ld (.ns),a
        ld b,5
.s:     push bc
        ld bc,$243B : ld a,$1F : out (c),a
        call g3_ack
        xor a : ld (i10f),a
        ld de,0
        ei
.w:     ld a,(i10f) : or a : jr nz,.g
        dec de : ld a,d : or e : jr nz,.w
        di : jr .nx
.g:     di
        ld a,(.n) : ld e,a : ld a,(i10l) : cp e : jr z,.lt
        ld bc,$253B
.p:     in a,(c) : cp e : jr z,.q
        in a,(c) : cp e : jr z,.q
        in a,(c) : cp e : jr z,.q
        in a,(c) : cp e : jr nz,.p
.q:     ld b,$1B : in a,(c)
        ld e,a : ld a,(i10c) : sub e
        ld l,a : ld h,0 : add hl,hl
        ld de,(.sum) : add hl,de : ld (.sum),hl
        ld hl,.ns : inc (hl)
        jr .nx
.lt:    ld hl,i10late : inc (hl)
.nx:    pop bc : djnz .s
        ld a,(NRSNAP+$22) : nextreg $22,a : ld a,(NRSNAP+$23) : nextreg $23,a
        ld hl,0 : ld a,(.ns) : or a : ret z
        ld c,a : ld hl,(.sum) : ld de,0 : call div8
        ret
.n:     dw 0
.sum:   dw 0
.ns:    db 0
i10h:   push af : push bc
        ld bc,$1B3B : in a,(c) : ld (i10c),a
        ld b,$25 : in a,(c) : ld (i10l),a
        ld a,1 : ld (i10f),a : ld (g3int),a
        pop bc : pop af : ei : reti
i10c:   db 0
i10l:   db 0
i10f:   db 0
i10late: db 0
k_e0:   db "e0",0
k_e191: db "e191",0
k_el2:  db "elast2",0
k_raw:  db "raw100",0
k_lh:   db "lh100",0
k_late: db "late",0

; ---------------------------------------------------------------- I14 interrupt acknowledge cost
; hardware IM2, ULA enable on, every vector -> RETI. At line 150, 64 times: status cleared; [NEXTREG
; $20,$40]; CTC3 read; EI; NOP; (handler); CTC3 read; DI. The same without the $20 write; the difference
; per repeat is the acknowledge + RETI (+ nothing else). v = T at 3.5 MHz; c28 = clocks at 28 MHz.
; IM 1 is not measured (it needs the ROM handler): im1=skipped.
@t_i14:  xor a : call .sp : ld (.v),hl : ld (.v+2),de
        ld a,3 : call .sp : ld (.w),hl : ld (.w+2),de
        call g3_hwoff
        ld hl,(.v) : ld de,(.v+2) : call res_num
        ld hl,u_t : call res_unit
        ld hl,k_c28 : call ex_k : ld hl,(.w) : ld de,(.w+2) : call wfix
        ld hl,k_s1 : ld de,(.s1) : call ex_kd
        ld hl,k_s0 : ld de,(.s0) : call ex_kd
        ld hl,k_im1 : call ex_k : ld hl,w_skipped : jp wstr
.v:     ds 4
.w:     ds 4
.s1:    dw 0
.s0:    dw 0
; A = speed -> DEHL = x 100 (T at 3.5 MHz, clocks at 28)
.sp:    ld (.s),a : nextreg $07,a
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld hl,g3_reti : call g3_hwtab
        call g3_hw
        ld a,G3HW>>8 : ld i,a : im 2
        ld a,1 : call .lp : ld (.s1),hl : push hl
        xor a : call .lp : ld (.s0),hl : ex de,hl : pop hl
        or a : sbc hl,de
        ld de,25 : call g3_smul
        ld a,(.s) : or a : ret nz
        ld b,3
.sh:    sra d : rr e : rr h : rr l : djnz .sh
        ret
.s:     db 0
; A = 1: with the $20 write -> HL = sum of the 64 CTC3 differences (ticks)
.lp:    ld (.f),a
        call frame_sync : ld a,150 : call sync_lsb
        ld hl,0 : ld a,64 : ld (.k),a
.r:     call g3_ack
        ld a,(.f) : or a : jr z,.n
        nextreg $20,$40
.n:     ld bc,$1B3B
        in e,(c) : ei : nop : in a,(c) : di
        ld d,a : ld a,e : sub d
        ld e,a : ld d,0 : add hl,de
        ld a,(.k) : dec a : ld (.k),a : jr nz,.r
        ret
.f:     db 0
.k:     db 0
k_c28:  db "c28",0
k_s1:   db "s1",0
k_s0:   db "s0",0
k_im1:  db "im1",0
w_skipped: db "skipped-needs-rom",0

; ---------------------------------------------------------------- I18 hardware IM2 priority
; $C0 bit 0 = 1, CPU IM 1 + DI, line ($C4 bit 1) and CTC0 ($C5 bit 0) enabled, CTC0 not counting; at line
; 150 NEXTREG $20,$81 (line + CTC0); then IM 2 (I = $FC, 16 handlers at $FC00), EI, ~64 loops, DI.
; v = handler runs; o1 o2 o3 = vector offsets in the order they ran ($FF = none); c8 / c9 status after.
@t_i18:  nextreg $07,3
        ld hl,g3h_wrong : call g3_hwtab
        ld hl,G3HW : call i06tab
        di
        nextreg $C4,0 : nextreg $C5,0 : nextreg $C6,0
        ld a,(NRSNAP+$C0) : and $08 : or 1 : nextreg $C0,a
        im 1
        ld bc,$183B : ld a,$03 : out (c),a
        call g3_ack : call g3_zero
        xor a : ld (i06cnt),a
        ld hl,i06log : ld b,8
.z:     ld (hl),$FF : inc hl : djnz .z
        call frame_sync : ld a,150 : call sync_lsb
        nextreg $C4,2 : nextreg $C5,1
        nextreg $20,$81
        ld a,G3HW>>8 : ld i,a : im 2
        ei
        ld b,64
.w:     djnz .w
        di
        ld a,$C8 : call rdreg : ld (.c),a
        ld a,$C9 : call rdreg : ld (.c+1),a
        nextreg $C4,0 : nextreg $C5,0
        call g3_hwoff
        ld a,(i06cnt) : ld l,a : ld h,0 : call res_int
        ld hl,u_count : call res_unit
        ld hl,i06log : ld de,.k : ld b,3
.o:     push bc : push de : push hl
        ld a,(hl) : cp $FF : jr z,.o1
        add a,a
.o1:    ex de,hl : ld e,(hl) : inc hl : ld d,(hl) : ex de,hl : call ex_kh
        pop hl : pop de : pop bc
        inc hl : inc de : inc de : djnz .o
        ld a,(.c) : ld hl,k_c8 : call ex_kh
        ld a,(.c+1) : ld hl,k_c9 : jp ex_kh
.c:     ds 2
.k:     dw k_o1,k_o2,k_o3
k_o1:   db "o1",0
k_o2:   db "o2",0
k_o3:   db "o3",0
k_c8:   db "c8",0
k_c9:   db "c9",0

; ---------------------------------------------------------------- I19 RETN in hardware IM2
; hardware IM2, ULA; the handler ends EI ; RETN: runs over 5 frames (expect 1: never acknowledged); $C0
; read in IM 1 and in IM 2 (bits 2:1 = mode); recovered with the dummy RETI. PASS if 1 run and the mode
; bits read 01 / 10.
@t_i19:  nextreg $07,3
        ld hl,i19h : call g3_hwtab
        call g3_hw : call g3_zero
        ld a,G3HW>>8 : ld i,a : im 2
        ld b,1 : call g3_fdi
        ld b,5 : call g3_fei
        di
        im 1 : ld a,$C0 : call rdreg : ld (.c),a
        im 2 : ld a,$C0 : call rdreg : ld (.c+1),a
        call g3_hwoff
        ld hl,(g3cnt) : call res_int
        ld hl,u_count : call res_unit
        ld a,(.c) : ld hl,k_im1 : call ex_kh
        ld a,(.c+1) : ld hl,k_im2 : call ex_kh
        ld hl,(g3cnt) : dec hl : ld a,h : or l : ret nz
        ld a,(.c) : and 6 : cp 2 : ret nz
        ld a,(.c+1) : and 6 : cp 4 : ret nz
        ld a,ST_PASS : ld (R_st),a : ret
.c:     ds 2
k_im2:  db "im2",0
i19h:   push af : push hl
        ld a,1 : ld (g3int),a
        ld hl,(g3cnt) : inc hl : ld (g3cnt),hl
        pop hl : pop af : ei : retn

; ---------------------------------------------------------------- I20 one outstanding CTC interrupt
; CTC0 timer /16, tc 175 (~10 kHz at 28 MHz). Periods over one frame: $C9 bit 0 polled (interrupt off).
; Runs over one frame: hardware IM2, CTC0 only; the handler stays busy for 3 CTC0 wraps and itself counts the
; frame (line MSB falls), switching CTC0's interrupt off after one whole frame. v = runs / periods
; (1/3 if extra requests fold into one, more if they queue).
@t_i20:  nextreg $07,3
        di : nextreg $C5,0
        ld bc,$183B : ld a,$07 : out (c),a : ld a,175 : out (c),a
        call .per : ld (.p),hl
        ld hl,i20h : call g3_hwtab
        call g3_hw : nextreg $C4,0
        ld bc,$183B : ld a,$87 : out (c),a : ld a,175 : out (c),a
        call g3_ack
        nextreg $C5,1
        call g3_zero
        ld a,G3HW>>8 : ld i,a : im 2
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.a:     in a,(c) : rra : jr nc,.a
.b:     in a,(c) : rra : jr c,.b
        ld hl,0 : ld (g3cnt),hl
        xor a : ld (i20m),a : ld (i20fall),a : ld (i20done),a
        ld e,0                                  ; frame starts the main loop saw (if the handler never runs)
        ei
.c:     ld a,(i20done) : or a : jr nz,.e        ; the handler ends the frame itself: after its RETI a
        in a,(c) : rra : jr nc,.c               ; request that came meanwhile is taken at once, so this
.d:     ld a,(i20done) : or a : jr nz,.e        ; loop may never run again while CTC0 is on
        in a,(c) : rra : jr c,.d
        inc e : ld a,e : cp 3 : jr c,.c
.e:     di
        nextreg $C5,0
        ld bc,$183B : ld a,$03 : out (c),a
        call g3_hwoff
        ld hl,(.p) : ld a,h : or l : jr z,.z
        ld bc,(g3cnt) : ld de,100 : call mul16
        ld bc,(.p) : call div32
        jr .r
.z:     ld de,0
.r:     call res_num
        ld hl,u_ratio : call res_unit
        ld de,(g3cnt) : ld hl,k_runs : call ex_kd
        ld de,(.p) : ld hl,k_per : jp ex_kd
.p:     dw 0
; -> HL = $C9 bit 0 sightings over one frame (from a frame start)
.per:   nextreg $C9,$FF
        ld hl,0 : ld e,0
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.pa:    in a,(c) : rra : jr nc,.pa
.pb:    in a,(c) : rra : jr c,.pb
        dec b
.l:     ld a,$C9 : out (c),a : inc b : in a,(c) : rra : jr nc,.n
        ld a,1 : out (c),a : inc hl
.n:     dec b : ld a,$1E : out (c),a : inc b : in a,(c) : dec b : and 1
        jr z,.zz
        ld e,1 : jr .l
.zz:    bit 0,e : jr z,.l
        ret
k_per:  db "periods",0
u_ratio: db "ratio",0
i20h:   push af : push bc : push de : push hl
        ld bc,$183B : in d,(c) : ld e,3 : ld hl,2048   ; guard: 3 periods are ~150 reads; a CTC that
.l:     dec hl : ld a,h : or l : jr z,.x                ; never counts (CSpect 4.5.9) must not hold the frame
        in a,(c) : cp d : ld d,a : jr c,.l : jr z,.l
        dec e : jr nz,.l
.x:     ld a,1 : ld (g3int),a
        ld a,(i20fall) : cp 1 : jr nz,.nc               ; count the runs between the 1st and 2nd frame start
        ld hl,(g3cnt) : inc hl : ld (g3cnt),hl
.nc:    ld b,$25 : in a,(c) : and 1                     ; $1E (the main loop's select): line MSB
        ld hl,i20m : cp (hl) : ld (hl),a : jr z,.k
        or a : jr nz,.k
        ld hl,i20fall : inc (hl) : ld a,(hl) : cp 2 : jr c,.k
        nextreg $C5,0 : ld a,1 : ld (i20done),a         ; one whole frame counted: CTC0 interrupt off
.k:     pop hl : pop de : pop bc : pop af : ei : reti
i20m:   db 0
i20fall: db 0
i20done: db 0

; ---------------------------------------------------------------- I22 continuous DMA and the pulse
; pulse IM 2 counting handler, EI; continuous 16K $4000 -> $0000 (pages 36 / 37) started 20 lines before
; the ULA interrupt line at 3.5 MHz and 5 lines before at 28 MHz; runs counted from the start to the end
; of the transfer, $C8 read after. v = runs at 3.5 MHz; r28 at 28; bad = copy bytes wrong. PASS if no run
; at either speed (the pulse was lost).
@t_i22:  call g3_map
        xor a : ld de,20 : call .one : ld (.r),hl : ld (.c),a : ld hl,(.bad) : ld (.b),hl
        ld a,3 : ld de,5 : call .one : ld (.r+2),hl : ld (.c+1),a : ld hl,(.bad) : ld (.b+2),hl
        call g3_unmap
        ld hl,(.r) : call res_int
        ld hl,u_count : call res_unit
        ld de,(.r+2) : ld hl,k_r28 : call ex_kd
        ld a,(.c) : ld hl,k_c8a : call ex_kh
        ld a,(.c+1) : ld hl,k_c8b : call ex_kh
        ld de,(.b) : ld hl,k_bad : call ex_kd
        ld de,(.b+2) : ld hl,k_bad28 : call ex_kd
        ld hl,(.r) : ld de,(.r+2) : ld a,h : or l : or d : or e : ret nz
        ld a,ST_PASS : ld (R_st),a : ret
.r:     ds 4
.c:     ds 2
.b:     ds 4
.bad:   dw 0
; A = speed, DE = lines before -> HL = runs, A = $C8
.one:   push de : push af
        nextreg $07,3
        ld hl,$4000 : ld de,0 : ld bc,$4000 : call g3_ncpy
        pop af : nextreg $07,a
        call g3_ulaline : pop de : call g3_before : push hl
        ld hl,g3h_cnt : call g3_tables : call g3_zero : call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld hl,i22p : ld b,i22p_e-i22p : call g3_dma
        pop hl : call g3_atline
        call g3_ack
        ld hl,0 : ld (g3cnt),hl
        ei
        ld a,$87 : out ($6B),a
        di
        ld hl,(g3cnt) : push hl
        ld a,$C8 : call rdreg : push af
        call g3_dmaoff
        nextreg $07,3
        ld hl,0 : ld de,$4000 : ld bc,$4000 : call g3_cmp : ld (.bad),hl
        pop af : pop hl : ret
k_r28:  db "r28",0
k_c8a:  db "c8",0
k_c8b:  db "c8_28",0
k_bad:  db "bad",0
k_bad28: db "bad28",0

; ---------------------------------------------------------------- I23 burst DMA (prescaler) and the interrupt
; 28 MHz, pulse IM 2 counting handler, EI; burst 2K $4000 -> $0000, prescaler 100, from line 150; wait (up
; to 40 frames) until the last byte is copied. v = runs meanwhile; frames, bad. PASS if a run happened and
; the transfer finished.
@t_i23:  call g3_map
        nextreg $07,3
        ld hl,$4000 : ld de,0 : ld bc,$800 : call g3_ncpy
        ld hl,g3h_cnt : call g3_tables : call g3_zero : call g3_pulse
        ld a,G3T>>8 : ld i,a : im 2
        ld hl,i23p : ld b,i23p_e-i23p : call g3_dma
        ld hl,150 : call g3_atline
        call g3_ack
        ld hl,0 : ld (g3cnt),hl
        ei
        ld a,$87 : out ($6B),a
        ld b,0
.w:     ld a,($47FF) : ld c,a : ld a,($07FF) : cp c : jr z,.d
        push bc : ld b,1 : call g3_fei : pop bc
        inc b : ld a,b : cp 40 : jr c,.w
.d:     di
        ld a,b : ld (.fr),a
        call g3_dmaoff
        ld hl,0 : ld de,$4000 : ld bc,$800 : call g3_cmp : ld (.bad),hl
        call g3_unmap
        ld hl,(g3cnt) : call res_int
        ld hl,u_count : call res_unit
        ld a,(.fr) : ld hl,k_fr : call ex_kad
        ld de,(.bad) : ld hl,k_bad : call ex_kd
        ld hl,(g3cnt) : ld a,h : or l : ret z
        ld a,(.fr) : cp 40 : ret nc
        ld a,ST_PASS : ld (R_st),a : ret
.fr:    db 0
.bad:   dw 0
k_fr:   db "frames",0

; ---------------------------------------------------------------- I24 DMA yields to hardware IM2
; 28 MHz, hardware IM2, ULA, $CC = $01, EI; continuous 16K $4000 -> $0000 (dst first = NOT src) from 5
; lines before the ULA line. The handler records the line and how far the copy had got (binary search for
; the first byte not yet copied: the read-back of the DMA's progress through memory). Then the DI variant
; (same transfer, interrupts off): it either completes (dbad) or the machine stops (HANG-GUARD next run).
; Both wait 3 frames before the DMA is stopped: on the board (3.03.00, build 3803884) the CPU ran on at
; once and the immediate stop cut both copies (bad=15138, dbad=16384) - so the DMA does yield the bus to
; the CPU here, and the test now measures the copy after it had time to finish. JNext 1.3.0 gives the same
; numbers as that board run (handler at the start line, 0 bytes copied by then; with interrupts off the
; copy does not run at all): line= next to start= says whether a request was already waiting.
; v = bytes copied when the handler ran; ran / line / bad / dbad. PASS if the handler ran mid-transfer and
; the copy is right.
@t_i24:  call g3_map
        nextreg $07,3
        call g3_ulaline : ld de,5 : call g3_before : ld (.st),hl
        ld hl,i24h : call g3_hwtab
        ld hl,$4000 : ld de,0 : ld bc,$4000 : call g3_ncpy
        xor a : ld (i24f),a : ld hl,$FFFF : ld (i24p),hl : ld (i24l),hl
        call g3_hw
        nextreg $CC,$01
        ld a,G3HW>>8 : ld i,a : im 2
        ld hl,i22p : ld b,i22p_e-i22p : call g3_dma
        ld hl,(.st) : call g3_atline
        call g3_ack
        ei
        ld a,$87 : out ($6B),a
        call .w3                                    ; a yielding DMA lets the CPU run: wait for the end
        di
        call g3_dmaoff
        ld hl,0 : ld de,$4000 : ld bc,$4000 : call g3_cmp : ld (.bad),hl
        ld hl,$4000 : ld de,0 : ld bc,$4000 : call g3_ncpy
        ld hl,i22p : ld b,i22p_e-i22p : call g3_dma
        ld hl,(.st) : call g3_atline
        call g3_ack
        ld a,$87 : out ($6B),a
        call .w3
        call g3_dmaoff
        ld hl,0 : ld de,$4000 : ld bc,$4000 : call g3_cmp : ld (.dbad),hl
        ld a,(NRSNAP+$CC) : nextreg $CC,a
        call g3_hwoff
        call g3_unmap
        ld hl,(i24p) : call res_int
        ld hl,u_bytes : call res_unit
        ld a,(i24f) : ld hl,k_ran : call ex_kad
        ld de,(i24l) : ld hl,k_line : call ex_kd
        ld de,(.bad) : ld hl,k_bad : call ex_kd
        ld de,(.dbad) : ld hl,k_dbad : call ex_kd
        ld de,(.st) : ld hl,k_start : call ex_kd
        ld hl,(.dbad) : ld a,h : or l : ld hl,w_compl : jr z,.dw
        ld hl,w_nocopy
.dw:    push hl : ld hl,k_di : call ex_k : pop hl : call wstr
        ld a,(i24f) : or a : ret z
        ld hl,(.bad) : ld a,h : or l : ret nz
        ld hl,(i24p) : ld a,h : or l : ret z
        ld de,$4000 : or a : sbc hl,de : ret nc
        ld a,ST_PASS : ld (R_st),a : ret
; three frames (a 16K copy at 28 MHz takes well under one; the CPU only gets here early if the DMA
; yielded the bus)
.w3:    ld b,3
.w:     push bc : call frame_sync : pop bc : djnz .w
        ret
.st:    dw 0
.bad:   dw 0
.dbad:  dw 0
k_ran:  db "ran",0
k_dbad: db "dbad",0
k_di:   db "di",0
w_compl: db "completes",0
w_nocopy: db "returned-not-copied",0
k_start: db "start",0
i24h:   push af : push bc : push de : push hl
        ld a,(i24f) : or a : jr nz,.x               ; the first interrupt of the copy only
        call line : ld (i24l),hl
        ld hl,0 : ld de,$4000
.b:     push hl : or a : sbc hl,de : pop hl : jr nc,.d
        push hl : add hl,de : srl h : rr l
        ld a,(hl) : set 6,h : cp (hl) : res 6,h
        jr nz,.ne
        pop bc : inc hl : jr .b
.ne:    ex de,hl : pop hl : jr .b
.d:     ld (i24p),hl
        ld a,1 : ld (i24f),a : ld (g3int),a
.x:     pop hl : pop de : pop bc : pop af : ei : reti
i24f:   db 0
i24p:   dw 0
i24l:   dw 0
        ENDMODULE
