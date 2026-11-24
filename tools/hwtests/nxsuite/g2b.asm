; nxsuite/g2b.asm - G2 extras Z02-Z05 (slot 7 overlay page OVL_G2). GPL-3.0-or-later.
; One instruction at a time from a table: registers loaded (F A C B E D L H), the instruction copied to
; B5CODE followed by JP zx_back, registers stored after it. Interrupts are off throughout.

; IX = case (len, dw bytes, F A C B E D L H) -> zx_out = F A C B E D L H after
zx_case:
        ld e,(ix+1) : ld d,(ix+2) : ex de,hl          ; HL = bytes
        push ix : pop de : inc de : inc de : inc de
        push hl : ex de,hl : ld de,zx_in : ld bc,8 : ldir : pop hl
        ld c,(ix+0) : ld b,0 : ld de,B5CODE : ldir
        ex de,hl : ld (hl),$C3 : inc hl : ld de,zx_back : ld (hl),e : inc hl : ld (hl),d
        ld (zxsp),sp
        ld sp,zx_in : pop af : pop bc : pop de : pop hl
        ld sp,(zxsp)
        jp B5CODE
zx_back:
        ld (zxsp),sp
        ld sp,zx_out+8 : push hl : push de : push bc : push af
        ld sp,(zxsp)
        ret
zxsp:   dw 0
zx_in:  ds 8
zx_out: ds 8
; IX = first case, B = count -> " f1=$hh f2=$hh ... f9 fA fB" ; zxf = the F values in order
zx_all: xor a : ld (.i),a
.l:     push bc : push ix
        call zx_case
        pop ix
        ld a,(.i) : ld e,a : ld d,0 : ld hl,zxf : add hl,de : ld a,(zx_out) : ld (hl),a
        ld a,(.i) : add a,'1' : cp '9'+1 : jr c,.d
        add a,7                                     ; 10 -> 'A'
.d:     ld (zxk+1),a
        ld hl,zxk : ld a,(zx_out) : call ex_kh
        ld hl,.i : inc (hl)
        ld de,11 : add ix,de
        pop bc : djnz .l
        ret
.i:     db 0
zxk:    db "f1",0
zxf:    ds 16

; ---------------------------------------------------------------- Z02 ADD rr,A / ADD HL,nn carry
; ADD HL,A no wrap and wrap, ADD DE,A and ADD BC,A wrapping, ADD HL,$1234 wrapping, each from F = 0 / $FF.
; choice over the eight ADD rr,A cases: clears-CF (carry 0 after all), keeps-CF (carry = the carry
; before), other. PASS if clears-CF. v = ADD rr,A cases with carry set after; f1..fA = F after each case.
z_31:   db $ED,$31
z_32:   db $ED,$32
z_33:   db $ED,$33
z_34:   db $ED,$34,$34,$12
z02c:   db 2 : dw z_31 : db $00,$20, 0,0, 0,0, $00,$10
        db 2 : dw z_31 : db $FF,$20, 0,0, 0,0, $00,$10
        db 2 : dw z_31 : db $00,$20, 0,0, 0,0, $F0,$FF
        db 2 : dw z_31 : db $FF,$20, 0,0, 0,0, $F0,$FF
        db 2 : dw z_32 : db $00,$20, 0,0, $F0,$FF, 0,0
        db 2 : dw z_32 : db $FF,$20, 0,0, $F0,$FF, 0,0
        db 2 : dw z_33 : db $00,$20, $F0,$FF, 0,0, 0,0
        db 2 : dw z_33 : db $FF,$20, $F0,$FF, 0,0, 0,0
        db 4 : dw z_34 : db $00,$00, 0,0, 0,0, $00,$F0
        db 4 : dw z_34 : db $FF,$00, 0,0, 0,0, $00,$F0
t_z02:  ld ix,z02c : ld b,10 : call zx_all
        ld hl,zxf : ld b,8 : ld c,0 : ld d,0 : ld e,0 ; C = carry set, D = carry kept, E = carry before
.l:     ld a,(hl) : and 1 : jr z,.z
        inc c
.z:     cp e : jr nz,.k
        inc d
.k:     ld a,e : xor 1 : ld e,a
        inc hl : djnz .l
        push bc : push de : ld l,c : ld h,0 : call res_int : pop de : pop bc
        ld hl,u_count : call res_unit
        ld a,c : or a : ld hl,w_clr : jr z,.ch
        ld a,d : cp 8 : ld hl,w_keep : jr z,.ch
        ld hl,w_other
.ch:    push hl : ld hl,k_choice : call ex_k : pop hl : push hl : call wstr : pop hl
        ld de,w_clr : or a : sbc hl,de : ret nz
        ld a,ST_PASS : ld (R_st),a
        ret
w_clr:  db "clears-CF",0
w_keep: db "keeps-CF",0

; ---------------------------------------------------------------- Z03 LDWS flags
; LDWS with D = $7F / $FF from F = 0 / $FF (HL = $F000 in this page; writes $7F10 / $FF10).
; ADD D,1 flags: carry after = (D was $FF); INC D flags: carry kept. Cases 2 ($7F, F=$FF) and 3 ($FF,
; F=0) decide: ADD-D-1 gives 0 / 1, INC-D 1 / 0. INFO choice; f1..f4 = F after.
z_a5:   db $ED,$A5
z03c:   db 2 : dw z_a5 : db $00,0, 0,0, $10,$7F, $00,$F0
        db 2 : dw z_a5 : db $FF,0, 0,0, $10,$7F, $00,$F0
        db 2 : dw z_a5 : db $00,0, 0,0, $10,$FF, $00,$F0
        db 2 : dw z_a5 : db $FF,0, 0,0, $10,$FF, $00,$F0
t_z03:  ld ix,z03c : ld b,4 : call zx_all
        ld a,(zxf+1) : and 1 : ld c,a
        ld a,(zxf+2) : and 1 : rla : or c             ; bit 1 = case 3 carry, bit 0 = case 2 carry
        ld hl,w_addd : cp 2 : jr z,.ch
        ld hl,w_incd : cp 1 : jr z,.ch
        ld hl,w_other
.ch:    call res_word
        push hl : ld hl,k_choice : call ex_k : pop hl : jp wstr
w_addd: db "ADD-D-1",0
w_incd: db "INC-D",0

; ---------------------------------------------------------------- Z04 ED B6 sandbox
; src $F010: 8 bytes (one $E3) between $AA guards; dst $F110: 8 x 0 between $AA guards; HL / DE / BC = src /
; dst / 8, A = $E3, alternate set 0. ED B6 once, then LDIRX (ED B4) the same way on a fresh copy.
; choice: same-as-LDIRX (HL DE BC and the 40 dst bytes equal), NOP (HL DE BC and dst unchanged), other.
; extras: hl / de / bc after ED B6 and its 8 dst bytes.
z_b6:   db $ED,$B6
z_b4:   db $ED,$B4
z04c:   db 2 : dw z_b6 : db $00,$E3, $08,$00, $10,$F1, $10,$F0
z04x:   db 2 : dw z_b4 : db $00,$E3, $08,$00, $10,$F1, $10,$F0
z04src: db $11,$22,$E3,$44,$55,$66,$77,$88
z04set: ld hl,$F000 : ld de,$F001 : ld bc,$1FF : ld (hl),$AA : ldir
        ld hl,z04src : ld de,$F010 : ld bc,8 : ldir
        ld hl,$F110 : ld b,8
.z:     ld (hl),0 : inc hl : djnz .z
        ret
t_z04:  call z04set
        exx : push bc : push de : push hl : ld bc,0 : ld de,0 : ld hl,0 : exx
        ex af,af' : push af : xor a : ex af,af'
        ld ix,z04c : call zx_case
        ex af,af' : pop af : ex af,af'
        exx : pop hl : pop de : pop bc : exx
        ld hl,zx_out : ld de,.r : ld bc,8 : ldir
        ld hl,$F100 : ld de,.d : ld bc,40 : ldir
        call z04set
        ld ix,z04x : call zx_case
        ld hl,k_hl : call ex_k : ld hl,(.r+6) : call .h16
        ld hl,k_de : call ex_k : ld hl,(.r+4) : call .h16
        ld hl,k_bc : call ex_k : ld hl,(.r+2) : call .h16
        ld hl,k_dst : call ex_k
        ld hl,.d+16 : ld b,8
.x:     ld a,(hl) : push hl : push bc : call whex2 : pop bc : pop hl : inc hl : djnz .x
        ld hl,.r+2 : ld de,zx_out+2 : ld b,6 : call .cmp : jr nz,.nl
        ld hl,.d : ld de,$F100 : ld b,40 : call .cmp : jr nz,.nl
        ld hl,w_same : jr .ch
.nl:    ld hl,(.r+6) : ld de,$F010 : or a : sbc hl,de : jr nz,.ot
        ld hl,(.r+4) : ld de,$F110 : or a : sbc hl,de : jr nz,.ot
        ld hl,(.r+2) : ld de,8 : or a : sbc hl,de : jr nz,.ot
        ld hl,.d+16 : ld b,8
.n0:    ld a,(hl) : or a : jr nz,.ot
        inc hl : djnz .n0
        ld hl,w_nop : jr .ch
.ot:    ld hl,w_other
.ch:    call res_word
        push hl : ld hl,k_choice : call ex_k : pop hl : jp wstr
.cmp:   ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : djnz .cmp
        ret
.h16:   ld a,'$' : call wchr : jp whex4
.r:     ds 8
.d:     ds 40
k_hl:   db "hl",0
k_de:   db "de",0
k_bc:   db "bc",0
k_dst:  db "dst",0
w_same: db "same-as-LDIRX",0
w_nop:  db "NOP",0

; ---------------------------------------------------------------- Z05 PIXELDN / PIXELAD edges
; PIXELDN from $57FF and $57E0; PIXELAD with D = 192, 200, 255 and E = 0, 255: HL after each (raw).
z_93:   db $ED,$93
z_94:   db $ED,$94
z05c:   db 2 : dw z_93 : db 0,0, 0,0, 0,0, $FF,$57
        db 2 : dw z_93 : db 0,0, 0,0, 0,0, $E0,$57
        db 2 : dw z_94 : db 0,0, 0,0, 0,192, 0,0
        db 2 : dw z_94 : db 0,0, 0,0, 255,192, 0,0
        db 2 : dw z_94 : db 0,0, 0,0, 0,200, 0,0
        db 2 : dw z_94 : db 0,0, 0,0, 255,200, 0,0
        db 2 : dw z_94 : db 0,0, 0,0, 0,255, 0,0
        db 2 : dw z_94 : db 0,0, 0,0, 255,255, 0,0
z05k:   dw k_dn1,k_dn2,k_ad1,k_ad2,k_ad3,k_ad4,k_ad5,k_ad6
k_dn1:  db "dn57ff",0
k_dn2:  db "dn57e0",0
k_ad1:  db "ad192_0",0
k_ad2:  db "ad192_255",0
k_ad3:  db "ad200_0",0
k_ad4:  db "ad200_255",0
k_ad5:  db "ad255_0",0
k_ad6:  db "ad255_255",0
t_z05:  ld ix,z05c : ld iy,z05k : ld b,8
.l:     push bc : push ix : push iy
        call zx_case
        pop iy : push iy
        ld l,(iy+0) : ld h,(iy+1) : call ex_k
        ld a,'$' : call wchr : ld hl,(zx_out+6) : call whex4
        pop iy : pop ix : pop bc
        ld de,11 : add ix,de : inc iy : inc iy
        djnz .l
        ld hl,8 : call res_int
        ld hl,u_count : jp res_unit
