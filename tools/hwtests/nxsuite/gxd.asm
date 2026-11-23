; nxsuite/gxd.asm - XD DIVMMC, opt-in (spec section 3 X-D, step 5). GPL-3.0-or-later.
; Slot-7 overlay after G1 on page 60. Never in RUN ALL: only by the menu key D, each test after its hazard
; screen (Y). Never writes the SD card (the only esxDOS call is F_OPEN, read mode, of a file that does not
; exist) and never writes port $E3. NextReg $BB bit 6 (XD1) and $0A bit 4 are written read-modify-write
; and put back; the alt ROM image (page 55) gets a few marker bytes, saved first and written back the same
; way as M03 does ($8C = $C0 write mode, $80 read). A test that does not come back is HANG-GUARD on the
; next start; the hazard screen says what to do (reset, start again).

; HL = 8-byte buffer -> $0000-$0007 as slots 0 / 1 show them with MMU 0 / 1 = $FF (ROM, or DivMMC when it
; is mapped over it); MMU 0 / 1 back from the snapshot
xd_rd8: nextreg $50,$FF : nextreg $51,$FF
        ex de,hl : ld hl,0 : ld bc,8 : ldir
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a
        ret
; DE = 8-byte buffer -> Z if it equals xd_b0 (the bytes before the test)
xd_same:
        ld hl,xd_b0 : ld b,8
.l:     ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : djnz .l
        ret
; F_OPEN (read) of a name that does not exist; a handle (it did exist after all) is closed again.
; -> (xd_e) = 0 error as expected, 1 opened
xd_nf:  ld hl,xd_name : ld b,$01 : call f_open
        ld a,0 : jr c,.e
        call f_close : ld a,1
.e:     ld (xd_e),a : ret
xd_name: db "NXNOFILE.XXX",0
xd_e:   db 0
xd_b0:  ds 8
xd_b1:  ds 8
xd_b2:  ds 8
xk_bb:   db "nrbb",0
xk_m1:   db "mapped1",0
xk_m2:   db "mapped2",0
xk_op:   db "opened",0

; ---------------------------------------------------------------- XD1 NextReg $BB bit 6: the automap exit
; $0000-$0007 read (MMU 0 / 1 = $FF); $BB bit 6 flipped; one F_OPEN (read) of NXNOFILE.XXX (an error, no
; write); $0000-$0007 again: other bytes = DivMMC still mapped after the call = the flipped value stops the
; exit at $1FF8-$1FFF. $BB put back, one more F_OPEN (NextZXOS leaves through its own exit) and the bytes
; again (mapped2: 0 = the ROM is back). v = "set-enables" (bit 6 = 1 lets the exit run: book, varmfskii),
; "set-disables" (nextreg.txt), or "no-change" (mapped either way the same). INFO (a choice).
t_xd1:  ld hl,xd_b0 : call xd_rd8
        ld a,$BB : call rdreg : ld (.bb),a : ld hl,xk_bb : call ex_kh
        ld a,(.bb) : xor $40 : nextreg $BB,a
        call xd_nf : ld a,(xd_e) : ld (.o1),a
        ld hl,xd_b1 : call xd_rd8
        ld a,$BB : call rdreg : and $BF : ld b,a : ld a,(.bb) : and $40 : or b : nextreg $BB,a
        call xd_nf
        ld hl,xd_b2 : call xd_rd8
        ld de,xd_b1 : call xd_same : ld a,0 : jr z,.u1
        inc a
.u1:    ld (.m1),a : ld hl,xk_m1 : call ex_kh
        ld de,xd_b2 : call xd_same : ld a,0 : jr z,.u2
        inc a
.u2:    ld hl,xk_m2 : call ex_kh
        ld a,(.o1) : ld hl,xk_op : call ex_kh
        ld hl,w_noch : ld a,(.m1) : or a : jr z,.w      ; the exit ran with the flipped bit
        ld a,(.bb) : and $40 : ld hl,w_sen : jr nz,.w   ; launch 1 (exit runs), flipped 0 stopped it
        ld hl,w_sdis                                    ; launch 0, flipped 1 stopped it
.w:     jp res_word
.bb:    db 0
.o1:    db 0
.m1:    db 0
w_sen:  db "set-enables",0
w_sdis: db "set-disables",0
w_noch: db "no-change",0

; ---------------------------------------------------------------- XD2 a fetch at $3D00 with automap on
; Alt ROM (as M03): $3D00 = LD A,$3D : RET (bytes saved first, written back after); $0A bit 4 = 1 (automap
; on, read-modify-write); MMU 0 / 1 = $FF; DI; CALL $3D00 -> A. $3D = the ROM image's code ran (no instant
; automap); other value = DivMMC memory ran at $3D00. Then $0A / $8C / MMU 0-1 back, one F_OPEN (read, no
; such file) so a still-mapped DivMMC leaves by NextZXOS's own exit, and $0000-$0007 compared with before
; (mapped=). v = A. PASS if A <> $3D (the claim: DivMMC memory ran at once); FAIL if A = $3D (the ROM
; image's code ran: no instant automap at $3D00).
t_xd2:  ld hl,xd_b0 : call xd_rd8
        ld a,$3D : ld (xd_v),a : ld hl,$3D00 : call xd_alt
        ld a,(xd_r) : call res_hex
        ld a,(xd_r) : ld hl,xk_a : call ex_kh
        call xd_tail
        ld a,(xd_r) : cp $3D : ld a,ST_FAIL : jr z,.s
        ld a,ST_PASS
.s:     ld (R_st),a : ret
xk_a:    db "a",0
xk_map:  db "mapped",0
; after XD2 / XD3: one F_OPEN, then " mapped=0|1" ($0000-$0007 against the start)
xd_tail:
        call xd_nf
        ld hl,xd_b1 : call xd_rd8
        ld de,xd_b1 : call xd_same : ld a,0 : jr z,.u
        inc a
.u:     ld hl,xk_map : jp ex_kh
; HL = $0038 or $3D00, (xd_v) = marker -> the image there = SCF : LD A,<v> : RET for $0038 (RST $38)
; or LD A,<v> : RET : NOP for $3D00 (CALL); $0A bit 4 = 1; IY = $5C3A; DI; A = 0 -> (xd_r) = A,
; (xd_c) = carry; image bytes, $0A, $8C, MMU 0 / 1 back
xd_alt: ld (.ad),hl
        nextreg $50,$FF : nextreg $51,$FF
        nextreg $8C,$80                                   ; alt ROM on, read: save 4 bytes
        ld de,.sv : ld bc,4 : ldir
        ld hl,.p3d : ld a,(xd_v) : ld (.p3d+1),a : ld (.p38+2),a
        ld a,(.ad+1) : or a : jr nz,.w
        ld hl,.p38
.w:     nextreg $8C,$C0                                   ; write mode
        ld de,(.ad) : ld bc,4 : ldir
        nextreg $8C,$80
        ld a,$0A : call rdreg : or $10 : nextreg $0A,a
        push iy : ld iy,$5C3A
        di
        ld a,(.ad+1) : or a : jr z,.r38
        xor a : call $3D00 : jr .ret
.r38:   xor a : rst $38
.ret:   di
        pop iy
        ld (xd_r),a : sbc a,a : ld (xd_c),a
        ld a,(NRSNAP+$0A) : nextreg $0A,a
        nextreg $8C,$C0
        ld hl,.sv : ld de,(.ad) : ld bc,4 : ldir
        ld a,(NRSNAP+$8C) : nextreg $8C,a
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a
        ret
.ad:    dw 0
.sv:    ds 4
.p3d:   ld a,$3D : ret : nop
.p38:   scf : ld a,$5A : ret
xd_v:   db 0
xd_r:   db 0
xd_c:   db 0

; ---------------------------------------------------------------- XD3 the RST $38 trap with an alt ROM
; Alt ROM: $0038 = SCF, $0039 = LD A,$5A : RET (bytes saved, written back); automap on ($0A bit 4 = 1);
; IY = $5C3A; DI; RST $38 -> A, carry.
; A = $5A = the image's code ran (no trap); other = the DivMMC trap took $0039 on (NextZXOS's own IM 1
; path). Then as XD2 (one F_OPEN, mapped=). v = A; key cy = carry. PASS if A <> $5A (the claim: the
; trap still fires with the alt ROM in place), FAIL if A = $5A.
t_xd3:  ld hl,xd_b0 : call xd_rd8
        ld a,$5A : ld (xd_v),a : ld hl,$0038 : call xd_alt
        ld a,(xd_r) : call res_hex
        ld a,(xd_c) : ld hl,xk_cy : call ex_kh
        call xd_tail
        ld a,(xd_r) : cp $5A : ld a,ST_FAIL : jr z,.s
        ld a,ST_PASS
.s:     ld (R_st),a : ret
xk_cy:   db "cy",0
