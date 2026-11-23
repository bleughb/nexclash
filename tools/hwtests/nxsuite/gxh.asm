; nxsuite/gxh.asm - XH DMA-HAZARD, opt-in (spec section 3 X-H, step 5). GPL-3.0-or-later.
; Slot-7 overlay after G6 on page 63 (G6's helpers and scratch pages 38 / 39 in slots 0 / 1). Never in
; RUN ALL: only by the menu key H, each test after its hazard screen (Y). XH1 can freeze the machine if
; the interrupt escape fails (then: reset, start again: HANG-GUARD). XH2 leaves the DMA deaf on purpose;
; the screen then says to finish, soft-reset and start again: the next start tries one DMA byte (prg_read2)
; and the next XH2 asks which reset was used and reports what it did. Hardware IM2 table at $FC00-$FCFF of
; this page (G6 uses $F700-$F747 only); the texts at $F748 (gxhtxt.asm).

XHT     equ $FC00

; ---------------------------------------------------------------- XH1 auto-restart in continuous mode
; Hardware IM2 (I = $FC, every vector -> xh_h), ULA interrupt only, NextReg $CC bit 0 = 1 (the ULA
; interrupt may break into a DMA transfer: book ch 4, hardware IM2 only), EI. Program: 256 bytes $0000 ->
; $2000 (pages 38 / 39), continuous, WR5 $A2 (auto restart), $87. The main loop counts while the DMA runs;
; the handler counts interrupts and at the second sends $83 then $C3. Then DI, pulse mode, a dummy RETI.
; v = main-loop passes before the stop (cpu=); irq = handler runs; bad = bytes of $2000-$20FF unlike $0000.
; PASS if the handler stopped it and the main loop made at most 50 passes (the CPU did not get the bus
; back between interrupts); FAIL if it ran on (the bus was given back). A machine that never comes back
; is HANG-GUARD on the next start: the escape did not work. First one DMA byte (dma_sane): a DMA that does
; not answer (still locked by an earlier XH2: board run 7 pass 2, v=15812 bad=254) gives SKIP why=dma-deaf.
t_xh1:  call dma_sane : jr nc,.go                  ; a deaf DMA (an earlier XH2 lock) cannot answer: SKIP
        ld hl,why_deaf : ld (R_why),hl : ld a,ST_SKIP : ld (R_st),a : ret
.go:    call g6_map
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

; ---------------------------------------------------------------- XH2 WR4 with bit 4: a deaf DMA
; First pass (no answer pending): one DMA byte (dma_sane). If it does not arrive the DMA is already deaf (an
; earlier XH2 in this run, or a reset that did not free it): SKIP why=dma-deaf, nothing sent, the screen says
; to power off and on. Else PRG_FLAGS bit 0 set and the record written; before=1; the WR4 byte $91 (bit 4:
; an interrupt control byte follows); dma_sane again: after=1 copied. v = "deaf" (after = 0, PASS: the
; claim's first half) or "copied" (FAIL). The screen then says: let the group finish, power off and on (or a
; hard reset), start nxsuite.nex again, press H.
; Second pass (PRG_XH2 set by the start after that reset, prg_read2): a 1 / 2 / 3 question - which reset
; (reset=soft / hard / power) - then v = "reset-frees" (the start's DMA byte arrived) or "still-locked";
; OPERATOR; PRG_XH2 cleared. S = ask later: PENDING-OPERATOR, PRG_XH2 kept.
t_xh2:  ld a,(PRGB+PRG_XH2) : or a : jr nz,.two
        call dma_sane : jr nc,.one
        ld hl,why_deaf : ld (R_why),hl : ld a,ST_SKIP : ld (R_st),a
        ld hl,m_xh2d : jr .scr
.one:   ld hl,PRGB+PRG_FLAGS : set 0,(hl) : call prg_write
        ld a,1 : ld hl,xk_bef : call ex_kh
        ld a,$91 : out ($6B),a
        call dma_sane : sbc a,a : inc a : ld (.a),a
        ld hl,xk_aft : call ex_kh
        ld hl,w_cop : ld a,(.a) : or a : ld a,ST_FAIL : jr nz,.w
        ld hl,w_deaf : ld a,ST_PASS
.w:     ld (R_st),a : call res_word
        ld hl,m_xh2
.scr:   push hl : call cls : pop hl : ld a,1 : call plines
        call keys_up
.k:     call getkey : or a : jr z,.k
        call keys_up
        jp gscreen
.two:   ld hl,q_xh2 : call ask : ret c               ; S: asked again next time
        ld hl,(askp) : push hl
        ld hl,EXB : ld (wp),hl                      ; the answer as reset= only
        ld hl,xk_rst : call ex_k : pop hl : call wstr
        ld a,(PRGB+PRG_XH2) : ld hl,w_rfree : cp 1 : jr z,.w2
        ld hl,w_lock
.w2:    call res_word
        xor a : ld (PRGB+PRG_XH2),a
        ret
.a:     db 0
