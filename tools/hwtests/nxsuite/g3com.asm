; nxsuite/g3com.asm - G3 shared set-up, handlers and counters. GPL-3.0-or-later.
; Included in both G3 overlay pages (g3.asm page OVL_G3, g3b.asm page OVL2_G3 inside MODULE g3x): each
; page builds its own tables at $F800-$FFFF before use.

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

