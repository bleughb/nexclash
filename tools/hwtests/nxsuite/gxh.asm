; nxsuite/gxh.asm - XH DMA-HAZARD, opt-in (spec section 3 X-H, step 5). GPL-3.0-or-later.
; Slot-7 overlay after G6 on page 63 (G6's helpers and scratch pages 38 / 39 in slots 0 / 1). Never in
; RUN ALL: only by the menu key H, each test after its hazard screen (Y). XH1 can freeze the machine if
; the interrupt escape fails (then: reset, start again: HANG-GUARD). XH2 leaves the DMA deaf on purpose;
; the screen then says to finish, soft-reset and start again: the next start tries one DMA byte (prg_read2)
; and the next XH2 reports what the reset did. Hardware IM2 table at $FC00-$FCFF of this page (G6 uses
; $F700-$F747 only).

XHT     equ $FC00

; ---------------------------------------------------------------- XH1 auto-restart in continuous mode
; Hardware IM2 (I = $FC, every vector -> xh_h), ULA interrupt only, NextReg $CC bit 0 = 1 (the ULA
; interrupt may break into a DMA transfer: book ch 4, hardware IM2 only), EI. Program: 256 bytes $0000 ->
; $2000 (pages 38 / 39), continuous, WR5 $A2 (auto restart), $87. The main loop counts while the DMA runs;
; the handler counts interrupts and at the second sends $83 then $C3. Then DI, pulse mode, a dummy RETI.
; v = main-loop passes before the stop (cpu=); irq = handler runs; bad = bytes of $2000-$20FF unlike $0000.
; PASS if the handler stopped it and the main loop made at most 50 passes (the CPU did not get the bus
; back between interrupts); FAIL if it ran on (the bus was given back). A machine that never comes back
; is HANG-GUARD on the next start: the escape did not work.
t_xh1:  call g6_map
        ld hl,0 : ld bc,256 : call g6_pat
        ld hl,$2000 : ld bc,256 : xor a : call g6_fill
        ld hl,XHT : ld de,xh_h : ld b,128
.t:     ld (hl),e : inc hl : ld (hl),d : inc hl : djnz .t
        xor a : ld (xh_n),a : ld (xh_st),a
        ld hl,0 : ld (xh_ml),hl
        call g6_def : ld hl,256 : ld (g6n),hl
        call g6_mk
        ld a,(g6pl) : sub 2 : ld e,a : ld d,0 : ld hl,G6P : add hl,de : ld (hl),$A2   ; WR5: auto restart
        call g6_send
        nextreg $C4,0 : nextreg $C5,0 : nextreg $C6,0
        ld a,(NRSNAP+$C0) : and $08 : or 1 : nextreg $C0,a
        nextreg $C8,$FF : nextreg $C9,$FF : nextreg $CA,$FF
        nextreg $C4,1
        nextreg $CC,1
        ld a,XHT >> 8 : ld i,a : im 2
        ei
        ld a,$87 : out ($6B),a
        ld hl,0
.m:     inc hl
        ld a,(xh_st) : or a : jr nz,.d
        ld a,h : cp $F0 : jr c,.m                       ; ~61000 passes: give up (bus given back for good)
        di : ld a,$83 : out ($6B),a : ld a,$C3 : out ($6B),a
.d:     di
        ld (xh_ml),hl
        nextreg $CC,0
        ld a,(NRSNAP+$C0) : and $08 : nextreg $C0,a
        nextreg $C8,$FF : nextreg $C9,$FF : nextreg $CA,$FF
        call .reti
        ld hl,0 : ld de,$2000 : ld bc,256 : call g6_cmp : ld (.bad),hl
        call g6_unmap
        ld hl,(xh_ml) : call res_int
        ld hl,u_count : call res_unit
        ld a,(xh_n) : ld l,a : ld h,0 : ex de,hl : ld hl,xk_irq : call ex_kd
        ld de,(.bad) : ld hl,xk_bad : call ex_kd
        ld a,(xh_st) : or a : jr z,.f
        ld hl,(xh_ml) : ld de,51 : or a : sbc hl,de : jr nc,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
.reti:  reti
.bad:   dw 0
; the handler: counts; at the second run DMA off ($83) and reset ($C3)
xh_h:   push af
        ld a,(xh_n) : inc a : ld (xh_n),a
        cp 2 : jr c,.r
        ld a,$83 : out ($6B),a : ld a,$C3 : out ($6B),a
        ld a,1 : ld (xh_st),a
.r:     pop af : ei : reti
xh_n:   db 0
xh_st:  db 0
xh_ml:  dw 0
xk_irq:  db "irq",0
xk_bad:  db "bad",0

; ---------------------------------------------------------------- XH2 WR4 with bit 4: a deaf DMA
; First pass (no answer pending): PRG_FLAGS bit 0 set and the record written; one DMA byte (dma_sane:
; before=1 copied); the WR4 byte $91 (bit 4: an interrupt control byte follows); then dma_sane again ($C3,
; a 1-byte copy): after=1 copied. v = "deaf" (after = 0) or "copied"; PASS if deaf (the claim's first
; half), FAIL if copied. The screen then says: let the group finish, soft-reset, start nxsuite.nex again, press H.
; Second pass (PRG_XH2 set by the start after that reset): v = "reset-frees" (the start's DMA byte arrived)
; or "still-locked"; INFO (the book: a reset frees it; the repo lesson: only power-off); PRG_XH2 cleared.
t_xh2:  ld a,(PRGB+PRG_XH2) : or a : jr z,.one
        ld hl,w_rfree : cp 1 : jr z,.w2
        ld hl,w_lock
.w2:    call res_word
        xor a : ld (PRGB+PRG_XH2),a
        ret
.one:   ld hl,PRGB+PRG_FLAGS : set 0,(hl) : call prg_write
        call dma_sane : sbc a,a : inc a : ld (.b),a
        ld a,$91 : out ($6B),a
        call dma_sane : sbc a,a : inc a : ld (.a),a
        ld a,(.b) : ld hl,xk_bef : call ex_kh
        ld a,(.a) : ld hl,xk_aft : call ex_kh
        ld hl,w_cop : ld a,(.a) : or a : ld a,ST_FAIL : jr nz,.w
        ld hl,w_deaf : ld a,ST_PASS
.w:     ld (R_st),a : call res_word
        call cls
        ld hl,m_xh2 : ld a,2 : call plines
        call keys_up
.k:     call getkey : or a : jr z,.k
        call keys_up
        jp gscreen
.b:     db 0
.a:     db 0
xk_bef:  db "before",0
xk_aft:  db "after",0
w_deaf: db "deaf",0
w_cop:  db "copied",0
w_rfree: db "reset-frees",0
w_lock: db "still-locked",0
m_xh2:  db "XH2 DONE. The DMA may now be",0
        db "deaf until a reset. NEXT:",0
        db " ",0
        db "1 press a key, let the group",0
        db "  finish (DONE on the screen)",0
        db "2 soft-reset the machine",0
        db "3 start nxsuite.nex again from",0
        db "  the same folder, press H:",0
        db "  XH2 then says what the reset",0
        db "  did (answer N to XH1).",0
        db " ",0
        db "Press a key.",0,0
