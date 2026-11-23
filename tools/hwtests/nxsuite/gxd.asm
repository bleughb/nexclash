; nxsuite/gxd.asm - XD DIVMMC, opt-in (spec section 3 X-D). GPL-3.0-or-later.
; Slot-7 overlay after G1 on page 60. Never in RUN ALL: only by the menu key D, each test after its hazard
; screen (Y). Rebuilt after board runs 8 / 9 (9b79e63: each of XD1, XD2, XD3 stopped the machine; run 8's
; screen showed the ROM font replaced by DivMMC memory). Rules now:
; - no NextZXOS code runs while a test has changed anything: DivMMC is mapped on purpose by an RST 8 whose
;   entry is delayed (spec 1.1, sd_esx: the opcode at $0008 comes from what slot 0 holds) with a one-byte
;   RET at $0008 of the alt ROM; registers are set as a harmless F_OPEN (read, no such file) in case the
;   entry is not delayed on this board and NextZXOS takes the call after all;
; - interrupts off the whole time DivMMC can be mapped; only our code (slot 7) and stack (bank 2) run; no
;   print and no file call until the ROM is back (xd_chk: $0000-$0007 and the font at $3D00-$3D7F equal the
;   copies taken at start, page 62);
; - DivMMC is unmapped by a RET at $1FF8-$1FFF (the exit range, NEXT_REGISTERS.md:35): a $C9 found in the
;   DivMMC ROM there, with $C9 planted at all eight addresses of the alt ROM, so the same RET runs whether
;   the exit acts before or after that fetch; then NextZXOS's own exit (one F_OPEN) as a fallback;
; - every planted alt ROM byte is written only while DivMMC is off (book N18: DivMMC beats the ROM and the
;   alt ROM, a write would land in DivMMC RAM) and put back; $BB, $0A, $8C, MMU 0 / 1, IM 1, I back;
; - if DivMMC still cannot be unmapped the machine stops on a message drawn with the RAM font (no file call:
;   it would run in DivMMC memory). Never writes the SD card and never writes port $E3.
; XDNEG = 1 (negative-control build): xd_end does not unmap, to show the check and the stop screen.

; -> Z = the ROM is back: $0000-$0007 and $3D00-$3D7F (MMU 0 / 1 and $8C as at launch) equal the copies
; taken at start (page 62 in slot 3 while comparing)
xd_chk: ld a,(NRSNAP+$8C) : nextreg $8C,a
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a
        nextreg $53,STRPAGE
        ld hl,0 : ld de,ROM8C : ld b,8 : call .c
        jr nz,.x
        ld hl,$3D00 : ld de,FONTC : ld b,128 : call .c
.x:     push af : nextreg $53,$0B : pop af : ret
.c:     ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : djnz .c
        ret

; C = 0: the alt ROM bytes of xd_pt saved and ours planted; C = 1: the saved bytes put back. Only while
; DivMMC is off. $8C, MMU 0 / 1 back to their launch values after (through xd_chk).
xd_alt: nextreg $50,$FF : nextreg $51,$FF
        ld ix,xd_pt : ld hl,xd_sv : ld b,XDPN
.l:     ld e,(ix+0) : ld d,(ix+1)
        ld a,c : or a : jr nz,.r
        nextreg $8C,$80 : ld a,(de) : ld (hl),a         ; alt ROM read: save
        ld a,(ix+2)
        jr .w
.r:     ld a,(hl)
.w:     nextreg $8C,$C0 : ld (de),a                     ; write mode
        inc hl : inc ix : inc ix : inc ix : djnz .l
        jp xd_chk
; address, byte: RET at the RST 8 and RST $38 entries; SCF : RET at $3D00 (XD2); RET in the exit range
xd_pt:  dw $0008 : db $C9
        dw $0038 : db $C9
        dw $3D00 : db $37
        dw $3D01 : db $C9
        dw $1FF8 : db $C9
        dw $1FF9 : db $C9
        dw $1FFA : db $C9
        dw $1FFB : db $C9
        dw $1FFC : db $C9
        dw $1FFD : db $C9
        dw $1FFE : db $C9
        dw $1FFF : db $C9
XDPN    equ ($-xd_pt)/3
xd_sv:  ds XDPN

; A = 8 or $38: that RST with esx's call state (core.asm: IM 1, I as at launch, IY = $5C3A, MMU 0 / 1 = ROM,
; alternate set kept) and the alt ROM on ($8C = $80) so its planted RET is fetched. RST 8 has the registers
; of an F_OPEN (read) of NXNOFILE.XXX. -> back with interrupts off, $8C and MMU 0 / 1 as at launch
xd_rst: ld (.k),a
        nextreg $50,$FF : nextreg $51,$FF : nextreg $8C,$80
        ld a,(launch_i) : ld i,a : im 1
        push iy : ld iy,$5C3A
        exx : push bc : push de : push hl : exx : ex af,af' : push af : ex af,af'
        ld ix,xd_name : ld b,$01 : ld a,(.k) : cp 8 : ld a,'*' : jr nz,.r38
        rst 8
        db $9A                                          ; F_OPEN for NextZXOS; SBC A,D after the RET
        jr .b
.r38:   or a : rst $38
.b:     di
        ex af,af' : pop af : ex af,af' : exx : pop hl : pop de : pop bc : exx
        pop iy
        push af
        ld a,(NRSNAP+$8C) : nextreg $8C,a
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a
        pop af : ret
.k:     db 0
xd_name: db "NXNOFILE.XXX",0

; DivMMC mapped: the first RET found in its ROM at $1FF8-$1FFF is called (alt ROM on: its eight RETs). -> Z =
; the ROM is back. (xd_ra) = the address's low byte, 0 = no RET there (then NZ)
xd_off: ld hl,$1FF8 : ld b,8
.f:     ld a,(hl) : cp $C9 : jr z,.c
        inc hl : djnz .f
        xor a : ld (xd_ra),a : or 1 : ret
.c:     ld a,l : ld (xd_ra),a
        nextreg $50,$FF : nextreg $51,$FF : nextreg $8C,$80
        call .j
        di
        jp xd_chk
.j:     jp (hl)
xd_ra:  db 0
; DivMMC mapped: its ROM's bytes at $1FF8-$1FFF -> key "dv=" (16 hex digits)
xd_dv:  ld hl,xk_dv : call ex_k
        ld hl,$1FF8 : ld b,8
.l:     ld a,(hl) : push hl : push bc : call whex2 : pop bc : pop hl : inc hl : djnz .l
        ret

; at a test's start: DivMMC must be off (else unmapped first); the alt ROM bytes planted
xd_pre: call xd_chk : call nz,xd_un
        call xd_chk : jr nz,xd_stop
        ld c,0 : jp xd_alt
; every test ends here: $BB, $0A as at launch; DivMMC unmapped and checked (RET in the exit range, then
; NextZXOS's own exit); the alt ROM bytes back; IM 1, I. Still mapped: xd_stop.
xd_end: ld a,(NRSNAP+$BB) : nextreg $BB,a : ld a,(NRSNAP+$0A) : nextreg $0A,a
        IF XDNEG = 0
        call xd_chk : call nz,xd_un
        ENDIF
        call xd_chk : jr nz,xd_stop
        ld c,1 : call xd_alt
        ld a,(launch_i) : ld i,a : im 1
        ret
xd_un:  call xd_off : ret z
        call xd_nf : jp xd_chk
; the ROM did not come back: no file call is possible (it would run in DivMMC memory); a message drawn with
; the RAM font, the border red, the machine stops
xd_stop:
        di
        call cls
        ld hl,m_xds : xor a : call plines
        ld a,2 : out ($FE),a
.h:     halt
        jr .h
m_xds:  db "DIVMMC STILL MAPPED",0
        db "The ROM did not come back after",0
        db "this test. Nothing more can be",0
        db "saved. Photograph this screen,",0
        db "then power off and on. The",0
        db "next start marks this test",0
        db "HANG-GUARD and goes on.",0,0

; F_OPEN (read) of NXNOFILE.XXX through esx (NextZXOS's own call and exit); a handle is closed again
xd_nf:  ld hl,xd_name : ld b,$01 : call f_open
        ret c
        jp f_close

xk_bb:  db "nrbb",0
xk_dv:  db "dv",0
xk_ra:  db "ra",0
xk_m0:  db "map",0
xk_m1:  db "mapflip",0
xk_r0:  db "off",0
w_noen: db "no-entry",0
w_noex: db "no-exit",0
w_sen:  db "set-enables",0
w_sdis: db "set-disables",0
w_noch: db "no-change",0

; ---------------------------------------------------------------- XD1 NextReg $BB bit 6: the automap exit
; DivMMC mapped (RST 8, RET at the alt ROM's $0008): map=1 if it is. With $BB as at launch (NextZXOS's value:
; its own calls rely on the exit) the RET in $1FF8-$1FFF is called: off=1 if the ROM came back, ra= its
; address. Mapped again, bit 6 flipped, the same RET: mapflip=1 if DivMMC stayed mapped (the flipped value
; stops the exit). $BB back. v = set-enables (bit 6 = 1 lets the exit run: book, varmfskii), set-disables
; (nextreg.txt), no-change, no-entry (the RST 8 did not leave DivMMC mapped: nothing more is tried), no-exit
; (no RET at $1FF8-$1FFF, or it did not unmap with the launch value: the flip is not tried). INFO.
t_xd1:  call xd_pre
        ld a,(NRSNAP+$BB) : ld hl,xk_bb : call ex_kh
        ld a,8 : call xd_rst : call xd_chk
        ld a,0 : jr z,.m0
        inc a
.m0:    push af : ld hl,xk_m0 : call ex_kh : pop af
        or a : ld hl,w_noen : jr z,.w
        call xd_dv
        call xd_off : ld a,0 : jr nz,.o0
        inc a
.o0:    push af : ld hl,xk_r0 : call ex_kh
        ld a,(xd_ra) : ld hl,xk_ra : call ex_kh : pop af
        or a : ld hl,w_noex : jr z,.w
        ld a,8 : call xd_rst : call xd_chk : ld hl,w_noen : jr z,.w
        ld a,(NRSNAP+$BB) : xor $40 : nextreg $BB,a
        call xd_off : ld a,0 : jr z,.m1                 ; Z: the exit ran with the flipped bit
        inc a
.m1:    push af : ld a,(NRSNAP+$BB) : nextreg $BB,a : pop af
        push af : ld hl,xk_m1 : call ex_kh : pop af
        ld hl,w_noch : or a : jr z,.w
        ld a,(NRSNAP+$BB) : and $40 : ld hl,w_sen : jr nz,.w   ; launch 1 (exit runs), flipped 0 stopped it
        ld hl,w_sdis
.w:     call res_word
        jp xd_end

; ---------------------------------------------------------------- XD2 a fetch at $3Dxx maps DivMMC at once?
; DivMMC mapped as XD1; its RAM at $3D00-$3D01 saved and OR A : RET written there (read back: ram=0 if the
; write did not hold - then nothing more); unmapped. Alt ROM $3D00 = SCF : RET. $0A as at launch (bit 4 on),
; DI, carry clear, CALL $3D00: carry clear = DivMMC's OR A ran (the fetch at $3D00 itself came from DivMMC:
; instant), carry set = the alt ROM's SCF ran. map= DivMMC mapped after the call. The DivMMC bytes are put
; back (mapped again if needed), DivMMC unmapped. v = instant (PASS), delayed (SCF ran, mapped after:
; FAIL), none (no automap at $3D00: FAIL), no-entry / no-exit / no-ram (the set-up was not possible: INFO).
xk_ram: db "ram",0
w_inst: db "instant",0
w_del:  db "delayed",0
w_nonx: db "none",0
w_nram: db "no-ram",0
xd_d3:  ds 2
xd_p3:  or a : ret
t_xd2:  call xd_pre
        ld a,8 : call xd_rst : call xd_chk : ld hl,w_noen : jp z,.i
        ld hl,$3D00 : ld de,xd_d3 : ld bc,2 : ldir
        ld hl,xd_p3 : ld de,$3D00 : ld bc,2 : ldir
        ld hl,($3D00) : ld de,(xd_p3) : or a : sbc hl,de : ld a,0 : jr nz,.rk
        inc a
.rk:    push af : ld hl,xk_ram : call ex_kh : pop af
        ld hl,w_nram : or a : jr z,.bk                  ; the write did not hold: put back, stop
        call xd_off : ld hl,w_noex : jr nz,.bk          ; not unmapped: put back (still mapped), stop
        nextreg $50,$FF : nextreg $51,$FF : nextreg $8C,$80
        di : xor a : call $3D00                         ; carry clear before
        di : sbc a,a : ld (.cy),a
        call xd_chk : ld a,0 : jr z,.m
        inc a
.m:     ld (.mp),a : ld hl,xk_m0 : call ex_kh
        ld a,(.mp) : or a : jr nz,.mm
        ld a,8 : call xd_rst : call xd_chk : jr z,.nr   ; map again to put the bytes back
.mm:    ld hl,xd_d3 : ld de,$3D00 : ld bc,2 : ldir
.nr:    ld a,(.cy) : or a : ld hl,w_del : jr nz,.d
        ld hl,w_inst : ld a,ST_PASS : jr .s
.d:     ld a,(.mp) : or a : jr nz,.f
        ld hl,w_nonx
.f:     ld a,ST_FAIL
.s:     ld (R_st),a : call res_word
        jp xd_end
.bk:    push hl : ld hl,xd_d3 : ld de,$3D00 : ld bc,2 : ldir : pop hl
.i:     call res_word : jp xd_end
.cy:    db 0
.mp:    db 0

; ---------------------------------------------------------------- XD3 the RST $38 trap with an alt ROM
; Alt ROM $0038 = RET (one byte: the next fetch would come from DivMMC if the trap fires); $0A as at launch;
; DI; RST $38 with the esx call state (IM 1, IY = $5C3A). map= DivMMC mapped after (the delayed trap fired
; after the RET), frames= the FRAMES counter ($5C78) moved (NextZXOS's own IM 1 code ran: the trap took the
; fetch at once). v = trap (map=1, PASS), isr (frames moved, PASS), no-trap (neither, FAIL).
xk_fr:  db "frames",0
w_trap: db "trap",0
w_isr:  db "isr",0
w_notr: db "no-trap",0
t_xd3:  call xd_pre
        ld hl,($5C78) : ld (.f0),hl
        ld a,$38 : call xd_rst
        call xd_chk : ld a,0 : jr z,.m
        inc a
.m:     ld (.mp),a : ld hl,xk_m0 : call ex_kh
        ld hl,($5C78) : ld de,(.f0) : or a : sbc hl,de : ld a,0 : jr z,.fr
        inc a
.fr:    ld (.fm),a : ld hl,xk_fr : call ex_kh
        ld a,(.mp) : or a : ld hl,w_trap : jr nz,.p
        ld a,(.fm) : or a : ld hl,w_isr : jr nz,.p
        ld hl,w_notr : ld a,ST_FAIL : jr .s
.p:     ld a,ST_PASS
.s:     ld (R_st),a : call res_word
        jp xd_end
.f0:    dw 0
.mp:    db 0
.fm:    db 0
