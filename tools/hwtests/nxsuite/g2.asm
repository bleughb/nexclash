; nxsuite/g2.asm - G2 Z80N: z80ntest's cases (spec section 3 G2). GPL-3.0-or-later.
; The FUNC / TIME cases are z80ntest_gen.py's own output (z80ntest_cases.inc, the same expected values from
; nexclash/z80n.py), assembled inside MODULE z80n with the few helpers they call, copied from z80ntest.asm
; (setup, winsum, the JP (C) slot table; check writes our records instead of z80ntest's screen).
; Lives in bank 2. While the cases run, slots 6 / 7 hold the sandbox pages SBX6 / SBX7 (JP (C) slot table
; $C000-$FFFF, TIME read area $D000, write area $E000, PUSH stack below $F000), so nothing here may call
; the harness (bank 0) until g2_home; results go to G2REC (bank 5) and are written afterwards.
;   G2REC + 4 x (case - 1): status (1 pass, 2 registers / memory differ, 4 F only), F, expected F, code
;   G2T35 / G2T28: per TIME case 12 bytes: mean, min, max (x 100, dwords)
; Built in stage 1: Z01, Z06, Z07 (Z02-Z05 are written SKIP not-built).

G2T35   equ G2REC+$100
G2T28   equ G2REC+$300

        MODULE z80n
WIN         equ $6000
WINLEN      equ $400
CSTACK      equ $6200
JPC_AT      equ $C020
JPC_EDGE    equ $BFFE
        INCLUDE "z80ntest_cases.inc"

; HL = list of (address word, byte), ended by address 0: clear the window, then poke them (z80ntest)
setup:  push hl
        ld hl,WIN : ld de,WIN+1 : ld bc,WINLEN-1 : ld (hl),0 : ldir
        pop hl
.l:     ld e,(hl) : inc hl : ld d,(hl) : inc hl
        ld a,d : or e : ret z
        ld a,(hl) : inc hl : ld (de),a
        jr .l
; Fletcher-8 pair of the window: D = sum, E = sum of sums (z80ntest)
winsum: ld hl,WIN : ld bc,WINLEN : ld de,0
.l:     ld a,(hl) : add a,d : ld d,a : add a,e : ld e,a
        inc hl : dec bc : ld a,b : or c : jr nz,.l
        ret
; A = case number, HL = expected F A C B E D L H, SP, checksum; GOT holds the actual ones (z80ntest's rules)
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
.st:    ld a,(tno) : dec a : ld l,a : ld h,0 : add hl,hl : add hl,hl : ld de,G2REC : add hl,de
        ld (hl),b : inc hl
        ld a,(GOT) : ld (hl),a : inc hl
        push hl : ld hl,(eptr) : ld a,(hl) : pop hl : ld (hl),a : inc hl
        ld (hl),c
        ret
GOT:    ds 8
gsp:    dw 0
gchk:   dw 0
msp:    dw 0
eptr:   dw 0
tno:    db 0
; JP (C) slot table: every 64 bytes from $C000 "LD A,slot : JP (IX)"; JP (C) at JPC_AT and JPC_EDGE
build_slots:
        ld hl,$C000 : ld c,0
.l:     ld (hl),$3E : inc hl : ld (hl),c : inc hl : ld (hl),$DD : inc hl : ld (hl),$E9
        ld de,61 : add hl,de
        inc c : jr nz,.l
        ld hl,$98ED
        ld (JPC_AT),hl
        ld (JPC_EDGE),hl
        ret
        ENDMODULE

g2_sbx: di
        nextreg $56,SBX6 : nextreg $57,SBX7
        ret
g2_home:
        nextreg $56,HOMEP6 : ld a,(ovlpage) : nextreg $57,a
        ret

; ---------------------------------------------------------------- Z01 FUNC cases
; one `T id=zf.<case>` line each (f = actual F, fexp = expected, code R / M / F as z80ntest); main v = passes
t_z01:  ld hl,G2REC : ld de,G2REC+1 : ld bc,4*z80n.NFUNC-1 : ld (hl),0 : ldir
        nextreg $07,0
        call g2_sbx
        call z80n.build_slots
        call z80n.run_cases
        call z80n.run_jpc
        call g2_home
        ld a,(spd0) : nextreg $07,a
        ld hl,g2zf : ld (g2pfx),hl
        ld b,z80n.NFUNC : ld ix,G2REC : ld hl,z80n.names : ld c,0
.l:     push bc : push hl : push ix
        call g2_id                              ; "zf." + name -> g2idb
        ld a,(ix+0) : cp 1 : ld a,ST_PASS : jr z,.s
        ld a,ST_FAIL
.s:     ld (R_st),a
        ld a,(ix+1) : call res_hex
        ld a,(ix+1) : ld hl,k_f : call ex_kh
        ld a,(ix+2) : ld hl,k_fexp : call ex_kh
        ld a,(ix+0) : cp 1 : jr z,.ok
        ld hl,k_code : call ex_k : ld a,(ix+3) : call wchr
.ok:    ld hl,g2idb : call sub_emit
        pop ix : pop hl : pop bc
        ld a,(ix+0) : cp 1 : jr nz,.n
        inc c
.n:     ld de,8 : add hl,de
        inc ix : inc ix : inc ix : inc ix
        djnz .l
        ld l,c : ld h,0 : push hl : call res_int
        ld hl,u_count : call res_unit
        pop hl : ld a,l : cp z80n.NFUNC
        ld a,ST_FAIL : jr nz,.r
        ld a,ST_PASS
.r:     ld (R_st),a
        ret
; HL = 8-character name (space padded) -> g2idb = (g2pfx) + the name without spaces
g2_id:  push hl
        ld de,g2idb : ld hl,(g2pfx) : ld bc,3 : ldir
        pop hl : ld b,8
.c:     ld a,(hl) : inc hl : cp ' ' : jr z,.n
        ld (de),a : inc de
.n:     djnz .c
        xor a : ld (de),a
        ret
g2pfx:  dw g2zf
g2zf:   db "zf."
g2zt:   db "zt."
g2zu:   db "zu."
g2idb:  ds 12
k_f:    db "f",0
k_fexp: db "fexp",0
k_code: db "code",0

; ---------------------------------------------------------------- Z06 / Z07 TIME cases
; each case: its block (8 x 256 copies, or one repeating instruction with BC = 2048, SP saved and set to
; $F000 around it) against its base block, core `trow` (4 passes, 5 runs, LD A,(IX+0) calibration); the
; result in clocks of the speed per instruction x 100 (K scaled by 2^speed as in G1). Z06 at 3.5 MHz: sub
; line PASS if within 0.5 T of z80n.OPCODES; the Z80 controls NEG / LDI / LDIR (the first three) must pass
; or the main line says method=fail. Z07 at 28 MHz ($07 = 3): PASS if within 0.5 clock of the same table
; (the 3.03 expectation), else INFO (a number, not a verdict).
t_z06:  xor a : ld hl,G2T35 : ld de,g2zt : jr g2time
t_z07:  ld a,3 : ld hl,G2T28 : ld de,g2zu
g2time: ld (g2spd),a : ld (g2out),hl : ld (g2pfx),de
        call g2_sbx
        ld iy,z80n.ttab : ld hl,(g2out) : ld (g2o),hl
.c:     ld a,(iy+0) : cp $FF : jr z,.d
        push iy : call g2row : pop iy
        ld hl,tr_mean : ld de,(g2o) : ld bc,4 : ldir
        ld hl,tr_min : ld bc,8 : ldir                       ; tr_max follows tr_min in core
        ld (g2o),de
        ld de,11 : add iy,de
        jr .c
.d:     call g2_home
        ld a,(spd0) : nextreg $07,a
        ld iy,z80n.ttab : ld ix,(g2out) : ld hl,z80n.names+8*z80n.NFUNC
        ld bc,0 : ld (g2np),bc : ld (g2ctl),bc
.w:     ld a,(iy+0) : cp $FF : jp z,.m
        push hl
        call g2_id
        push ix : pop hl : ld de,R_v : ld bc,4 : ldir
        push ix : pop hl : ld bc,4 : add hl,bc : ld de,R_min : ld bc,8 : ldir
        ld hl,5 : ld (R_n),hl : ld a,VK_NUM : ld (R_vk),a
        ld hl,u_clocks : call res_unit
        ld a,(iy+1) : ld e,a : ld d,0 : push de : ld hl,k_exp : call ex_kd : pop hl
        call x100                                       ; DEHL = expected x 100
        ld c,(ix+0) : ld b,(ix+1) : or a : sbc hl,bc    ; expected - mean (low words; values < 655 T)
        jr nc,.p
        ld a,h : cpl : ld h,a : ld a,l : cpl : ld l,a : inc hl
.p:     ld de,51 : or a : sbc hl,de : jr c,.ok
        ld a,(g2spd) : or a : ld a,ST_FAIL : jr z,.s
        ld a,ST_INFO : jr .s                            ; Z07: INFO unless it matches (spec)
.ok:    ld hl,(g2np) : inc hl : ld (g2np),hl
        ld a,ST_PASS
.s:     ld (R_st),a
        cp ST_FAIL : jr nz,.k                           ; a control (the first three cases) failed?
        push iy : pop hl : ld de,z80n.ttab+33 : or a : sbc hl,de : jr nc,.k
        ld a,1 : ld (g2ctl),a
.k:     push ix : push iy
        ld hl,g2idb : call sub_emit             ; (the writer uses IX)
        pop iy : pop ix
        pop hl : ld de,8 : add hl,de
        ld de,12 : add ix,de
        ld de,11 : add iy,de
        jp .w
.m:     ld hl,(g2np) : push hl : call res_int
        ld hl,u_count : call res_unit
        ld a,(g2ctl) : or a : jr z,.mo
        ld hl,k_method : call ex_k : ld hl,w_mfail : call wstr
        pop hl : ld a,ST_FAIL : ld (R_st),a : ret
.mo:    pop hl : ld a,(g2spd) : or a : ld a,ST_INFO : jr nz,.r1
        ld a,ST_FAIL
.r1:    ld b,a : ld a,l : cp z80n.NTIME : ld a,b : jr nz,.r
        ld a,ST_PASS
.r:     ld (R_st),a
        ret
k_method: db "method",0
w_mfail: db "fail",0
g2spd:  db 0
g2out:  dw 0
g2o:    dw 0
g2np:   dw 0
g2ctl:  dw 0
; IY = TIME entry (mode, exp, adj, tini, len, body, lenb, base) -> tr_mean / tr_min / tr_max
g2row:  ld l,(iy+3) : ld h,(iy+4) : ld (mini),hl
        ld hl,g2pro : ld (mk_pro),hl : ld a,G2PRO_LEN : ld (mk_prol),a
        ld hl,g2epi : ld (mk_epi),hl : ld a,G2EPI_LEN : ld (mk_epil),a
        ld hl,256 : ld b,8 : ld a,(iy+0) : or a : jr z,.m
        ld hl,1 : ld b,1
.m:     ld (mk_n),hl
        ld a,(g2spd) : or a : jr z,.k
.k1:    sla b : dec a : jr nz,.k1
.k:     ld a,b : ld (tr_k),a
        ld hl,1900 : ld (tr_num),hl
        ld l,(iy+6) : ld h,(iy+7) : ld (mk_body),hl : ld a,(iy+5) : ld (mk_bodyl),a
        ld de,TBUF : call mkblk
        ld l,(iy+9) : ld h,(iy+10) : ld (mk_body),hl : ld a,(iy+8) : ld (mk_bodyl),a
        or a : jr nz,.b
        ld hl,0 : ld (mk_n),hl                          ; no base body: the frame only
.b:     ld de,TBUF2 : call mkblk
        ld hl,TBUF : ld (tr_blk),hl : ld hl,TBUF2 : ld (tr_emp),hl
        ld a,(g2spd) : ld (mshift),a : nextreg $07,a
        call trow
        ld a,(spd0) : nextreg $07,a
        xor a : ld (mk_prol),a : ld (mk_epil),a
        ld hl,zini : ld (mini),hl
        ret
g2pro:  ld (g2sp),sp : ld sp,$F000
G2PRO_LEN equ $-g2pro
g2epi:  ld sp,(g2sp)
G2EPI_LEN equ $-g2epi
g2sp:   dw 0
