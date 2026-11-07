; Nightshade (Ultimate Play The Game, 1985, 48K) - figures as hardware sprites over the game's own picture.
; Filmation II composes the play area in a mono back buffer (0xE5C6, 24 bytes a row, rows bottom-up,
; 112 rows; 22 columns shown) and an attribute buffer (0xF046), then blits both (0xE148 / 0xE1AD).
; Every figure goes through one masked plotter (0xE3D9); figures have no colour of their own in the
; buffer, so they take the scenery's attribute (white floor, cyan walls...). Kind A clash.
;
; The game's plot is NOT skipped: every byte of game memory stays as the original's. The hook runs
; the game's own plot loop a second time into a zeroed scratch copy of the buffer (page H_PAGE at slot 1),
; which gives the figure's ink, and keeps it. At the blit, each figure's ink AND the final buffer
; (what is still visible of it after later plots) becomes 4-bit 16 x 16 sprites in the figure's colour,
; at the place the blit puts those bytes. The ULA picture is unchanged under them.
; The hero's colour box (0xC898 from 0xBEC4: 2 x 4 cells in his health colour) is not painted, so the
; scenery behind him keeps its colours; the hero's sprite carries that colour instead.
;
; Patch sites (original bytes checked by nightshade.py):
;   0xE45E ED 73 AE BB  LD (0xBBAE),SP  -> CALL s_fg / NOP   the figure plot, after its clip
;   0xE200 CD 48 E1     CALL 0xE148     -> CALL s_bl         both blits (to 0xE206): sprites switched with them
;   0xE59D CD A8 E5     CALL 0xE5A8     -> CALL s_cls        the screen clear: sprites off
;   0xBEC4 CD 98 C8     CALL 0xC898     -> CALL s_hb         the hero's colour box: registers only
        DEVICE ZXSPECTRUMNEXT

H_PAGE  EQU 26
BUF     EQU 0xE5C6          ; 58822
SAVESP  EQU 0xBBAE          ; 48046, the game's own SP save
FW      EQU 0xBBC2          ; 48066 width in bytes
FH      EQU 0xBBC3          ; 48067 rows
PLOOP   EQU 0xE4C9          ; 58569 the plot loop
HFLAG   EQU 0xBC8E          ; 48270 hero colour box on
HIDX    EQU 0xBBF3          ; 48115 hero health index
HTAB    EQU 0xC065          ; 49253 hero colours
SCR     EQU 0x2B40          ; scratch copy of the buffer, kept zero (64 bytes below it for a figure left of the window)
LIST    EQU 0x0000          ; past the scratch and what a figure at the top right spills beyond it; figure records: offset (2), w, h, colour, then w*h ink bytes
LISTEND EQU 0x2000
PAT     EQU 0x3F80          ; one 4-bit pattern being made
POFF    EQU 0x2600          ; Enhanced: figure type -> palette offset (0xFF the hero)
LPAGE   EQU 28              ; the figure records, at slot 0 (0x0000) during the hooks (interrupts are off there)
PLTPAGE EQU 29              ; Enhanced: type x orientation -> (page, address) of its two colour planes
GTAB    EQU 28318           ; the game's graphic table
NIB     EQU 0x2700          ; 4 x 256 (page-aligned): NIB_k[v] = pixels 2k, 2k+1 of byte v as nibbles (1 = ink)
MAXF    EQU 24

        ORG 0x5B4F          ; after the start-up tail (0x5B00-0x5B4E); 0x5B4F-0x5B7F unused by the game
; Every hook leaves R as the original would (the game reads R for its random numbers): the page code reads R
; on entry and sets it before the exit, counting the M1 cycles both sides.
s_fg:   nextreg 0x51,H_PAGE
        jp h_fig
s_bl:   nextreg 0x51,H_PAGE
        jp h_commit
s_hb:   nextreg 0x51,H_PAGE
        jp h_box
s_cls:  nextreg 0x51,H_PAGE
        jp h_cls
s_x:    nextreg 0x51,0xFF
        ret
s_xc:   nextreg 0x51,0xFF
        jp 0xE5A8
ram_end:

        ORG 0x2000
; At 0xE45E: BC = buffer address, DE = graphic (the plot's SP), HL = shift table, A' free (the loop sets it).
; Stack: return to 0xE461 (a NOP, then the original 0xE462).
h_fig:  push af
        ld a,r              ; E = 7 M1 since the site
        ld (vR),a
        push bc             ; the incoming CPU speed (NR 0x07), restored at the exit (never a fixed 3.5 MHz)
        ld bc,0x243B
        ld a,0x07
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3      ; 28 MHz from here: the 3.5 MHz part is as short as it can be
        and 3
        ld (vspd),a
        pop bc
        ld a,115            ; 1 - 7 - 7
        call mkT
        pop af
        push bc
        push de
        push hl
        call line           ; the raster at the start of the 28 MHz part: its lines become pace debt
        ld (vfl),hl
        pop hl
        pop de
        pop bc
        ld (sv_hl),hl
        ld (sv_de),de
        ld (sv_bc),bc
        ld (sv_sp),sp
        push af
        ex af,af'
        push af
        ex af,af'
        ld a,(nfig)
        cp MAXF
        jp nc,.full
        ld a,(FW)
        ld e,a
        ld a,(FH)
        ld d,a
        mul d,e
        ld hl,(lptr)
        add hl,de
        ld de,6
        add hl,de
        ld de,LISTEND
        or a
        sbc hl,de
        jp nc,.full
        ld a,(enh_flag)     ; Enhanced: ink and two colour planes
        or a
        jr z,.n1
        ld a,(FW)
        ld e,a
        ld a,(FH)
        ld d,a
        mul d,e
        ld h,d
        ld l,e
        add hl,hl
        add hl,de           ; 3 x w x h
        ld de,(lptr)
        add hl,de
        ld de,LISTEND-6
        or a
        sbc hl,de
        jp nc,.full
.n1:
    IFDEF ENHCIM
        ld a,(enh_flag)     ; Enhanced with code images: a record, no plots (cimrec)
        or a
        jp nz,cimrec
    ENDIF
        ld hl,SCR-BUF
        add hl,bc
        ld (vscr),hl
        ld hl,(sv_de)
        ld (vsp),hl
        call splot          ; the game's own loop, into the scratch: the figure's ink
        nextreg 0x50,LPAGE
        ld de,(lptr)
        ld hl,(vscr)
        ld bc,-SCR
        add hl,bc
        ex de,hl
        ld (hl),e           ; offset in the buffer
        inc hl
        ld (hl),d
        inc hl
        ld a,(FW)
        ld (hl),a
        inc hl
        ld a,(FH)
        ld (hl),a
        inc hl
        ld a,7              ; bright white: the floor's ink, the colour every figure has on the ULA there
        ld e,a
        ld a,ixh
        cp 0xBC
        jr nz,.col
        ld a,ixl
        cp 0x8E
        jr z,.hero
        cp 0x9E
        jr nz,.col
.hero:  ld e,0xFF           ; the hero: his health colour, chosen at the blit
.col:   ld (hl),e
        inc hl
        ld a,(ix+0)         ; the figure's type, for the Enhanced colours
        ld (hl),a
        inc hl
        ld (lptr),hl
        call cpbox
        ld a,(enh_flag)
        or a
        jp z,.n2
        ld a,(ix+0)         ; G = the type's graphic; its header bits 7, 6 = the orientation it is in now
        ld l,a
        ld h,0
        add hl,hl
        ld de,GTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (vg),de
        ld a,(de)
        ld b,a
        and 15
        ld c,a              ; data width
        inc de
        ld a,(de)
        ld d,a
        ld e,c
        mul d,e
        ex de,hl
        add hl,hl
        ld (vplen),hl       ; one plane's length: 2 x width x height
        ld hl,(sv_de)       ; the plot's data pointer, from G
        ld de,(vg)
        or a
        sbc hl,de
        ld (vdoff),hl
        ld a,(ix+0)         ; PLT entry: (type * 4 + orientation) * 3
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,b
        rlca
        rlca
        and 3
        add hl,a
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        nextreg 0x50,PLTPAGE
        ld a,(hl)
        ld (vpp),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(vdoff)
        add hl,de
        ld (vsp),hl
        call plane
        ld hl,(vsp)
        ld de,(vplen)
        add hl,de
        ld (vsp),hl
        call plane
.n2:    nextreg 0x50,0xFF
        ld hl,nfig
        inc (hl)
        jr .done
.full:  ld hl,(nfull)
        inc hl
        ld (nfull),hl
.done:  ex af,af'
        pop af
        ex af,af'
        pop af
        ld sp,(sv_sp)
        ld hl,(sv_hl)
        ld de,(sv_de)
        ld bc,(sv_bc)
        ld (sv_x),hl        ; LD (0xBBAE),SP as the original: SP before the CALL
        pop hl
        ld (SAVESP),sp
        push hl
        ld hl,(sv_x)
        ld (sv_a),a
        call fig_end        ; pace debt += the lines this hook took, and its 3.5 MHz part
        ld a,(vspd)
        nextreg 0x07,a      ; the incoming speed
        ld a,(vT)
        ld r,a
        ld a,(sv_a)         ; N = 7 from here (the two NOPs stand for the NEXTREG that was here)
        nop
        nop
        jp s_x

; splot: the game's plot loop on the figure's clip and shift, with its data at (vsp), into the scratch at (vscr).
; The loop ends LD SP,(0xBBAE) / RET: SAVESP is pointed at splot's own return.
splot:  ld (SAVESP),sp
        ld bc,(vscr)
        ld hl,(sv_hl)
        ld a,(FH)
        ld sp,(vsp)
        jp PLOOP

; plane: one colour plane (page vpp, 0 = none) through the plot loop, then into the record
plane:  ld a,(vpp)
        or a
        jr z,.zero
        nextreg 0x50,a
        call splot
        nextreg 0x50,LPAGE
        jr cpbox
.zero:  nextreg 0x50,LPAGE
        ld a,(FW)
        ld e,a
        ld a,(FH)
        ld d,a
        mul d,e
        ld hl,(lptr)
.z:     ld (hl),0
        inc hl
        dec de
        ld a,d
        or e
        jr nz,.z
        ld (lptr),hl
        ret

; cpbox: the scratch box (FW x FH at vscr) to the record at lptr, the scratch left zero
cpbox:  ld de,(lptr)
        ld hl,(vscr)
        ld a,(FH)
        ld c,a
.row:   ld a,(FW)
        ld b,a
        push hl
.byte:  ld a,(hl)
        ld (de),a
        ld (hl),0
        inc hl
        inc de
        djnz .byte
        pop hl
        ld a,24
        add hl,a
        dec c
        jr nz,.row
        ld (lptr),de
        ret

; The hero's colour box (0xC898), registers as it leaves them, nothing written.
h_box:  ex af,af'
        ld a,r              ; E = 7
        ld (vR),a
        ld a,119            ; flag off: D = 5, N = 7
        call mkT
        ld a,(HFLAG)
        and a
        jr nz,.nz
        ld (sv_a),a
        push hl
        ld hl,KBOX0
        call debt_add       ; the hook's time against the original's (flag off)
        pop hl
        ld a,(vT)
        ld r,a
        ld a,(sv_a)
        nop                 ; for the NEXTREG 0x07,0 that was here: h_box runs at the caller's speed
        nop
        jp s_x
.nz:    ex af,af'
        ld e,a
        ld a,b              ; D = 11 + 7B
        add a,a
        add a,a
        add a,a
        sub b
        sub 3
        call mkT
        ld a,(0xBBFC)
        or e
        ld de,23
.l:     or 64
        inc hl
        and 63
        add hl,de
        djnz .l
        ld (sv_a),a
        push hl
        ld hl,KBOX1
        call debt_add       ; the hook's time against the original's (flag on: 4 rows)
        pop hl
        ld a,(vT)
        ld r,a
        ld a,(sv_a)
        nop
        nop
        jp s_x

; the screen clear: sprites off
h_cls:  push af
        ld a,r              ; E = 7
        ld (vR),a
        ld a,117            ; 1 - 7 - 5
        call mkT
        nextreg 0x15,0
        pop af
        ld (sv_a),a
        ld a,(vT)
        ld r,a
        ld a,(sv_a)
        jp s_xc

; vT = vR + A in R's low 7 bits, bit 7 kept
mkT:    push bc
        ld c,a
        ld a,(vR)
        ld b,a
        and 0x7F
        add a,c
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld (vT),a
        pop bc
        ret

; one 16 x 16 tile (vtx, vty) of the figure: ink AND the final buffer, columns >= 22 off.
; Speed pass (2026-11-05): column masks once a tile (a tile with both columns hidden, or below the figure, is
; skipped), row pointers stepped by the width and by 24, one call a byte (tbyte) and three page-aligned nibble
; table look-ups an output byte (out4); the same pixels as before.
tile:   ld a,(vn)
        cp 64               ; one half of the pattern memory a frame
        jr c,.ok
        ld hl,(ntrunc)
        inc hl
        ld (ntrunc),hl
        ret
.ok:
        xor a
        ld (vany),a
        ld a,(vtx)
        add a,a
        ld (vj),a
        call colmask
        ld (vm0),a
        ld a,(vj)
        inc a
        ld (vj),a
        call colmask
        ld (vm1),a
        ld b,a
        ld a,(vm0)
        or b
        ret z               ; both columns hidden: no slot
        ld a,(vty)
        add a,a
        add a,a
        add a,a
        add a,a
        ld c,a              ; the tile's first row from the figure's top
        ld a,(vh)
        dec a
        sub c               ; i = h - 1 - row
        ret c               ; the tile is below the figure: no slot
        ld (vi),a
        ld d,a
        ld a,(vw)
        ld e,a
        mul d,e
        ld hl,(vink)
        add hl,de
        ld a,(vtx)
        add a,a
        add hl,a
        ld (vpi),hl         ; the ink byte (i, j0)
        ld a,(vi)
        ld d,a
        ld e,24
        mul d,e
        ld hl,(vo)
        add hl,de
        ld de,BUF
        add hl,de
        ld a,(vtx)
        add a,a
        add hl,a
        ld (vpb),hl         ; the final buffer byte (i, j0)
    IFDEF ENHCIM
        ld a,(enh_flag)
        or a
        call nz,cimtile     ; the code image's row and column offsets, edge masks
    ENDIF
        ld ix,PAT
        ld a,16
        ld (vyy),a
    IFDEF ENHCIM
        ld a,(enh_flag)
        or a
        jp nz,cimrows       ; the rows from the code image (returns to tile.end)
    ENDIF
.r:     ld a,(vi)
        bit 7,a
        jp nz,.blank        ; past the figure's bottom: the rest of the tile blank
        ld hl,vr0           ; rows below 0 or past 111 are not shown
        add a,(hl)
        cp 112
        jp nc,.zrow
        ld a,(enh_flag)
        or a
        jp nz,.en
        ld hl,(vpb)         ; default: visible ink = ink AND the final buffer, one look-up an output byte
        ld a,(hl)
        inc hl
        ld b,(hl)           ; B = buffer byte 1
        ld hl,(vpi)
        and (hl)
        ld c,a
        ld a,(vm0)
        and c
        ld c,a              ; C = visible ink, column 0
        inc hl
        ld a,(hl)
        and b
        ld b,a
        ld a,(vm1)
        and b
        ld b,a              ; B = visible ink, column 1
        or c
        ld hl,vany
        or (hl)
        ld (hl),a
        ld h,NIB >> 8
        ld l,c
        ld a,(hl)
        ld (ix+0),a
        inc h
        ld a,(hl)
        ld (ix+1),a
        inc h
        ld a,(hl)
        ld (ix+2),a
        inc h
        ld a,(hl)
        ld (ix+3),a
        ld h,NIB >> 8
        ld l,b
        ld a,(hl)
        ld (ix+4),a
        inc h
        ld a,(hl)
        ld (ix+5),a
        inc h
        ld a,(hl)
        ld (ix+6),a
        inc h
        ld a,(hl)
        ld (ix+7),a
        ld de,8
        add ix,de
        jp .nx
.en:
        ld hl,(vpb)
        ld a,(hl)
        ld (vb0),a
        inc hl
        ld a,(hl)
        ld (vb1),a
        ld a,(vm0)
        ld (vmk),a
        ld hl,(vpi)
        ld a,(vb0)
        call tbyte
        call out4
        ld a,(vm1)
        ld (vmk),a
        ld hl,(vpi)
        inc hl
        ld a,(vb1)
        call tbyte
        call out4
        jp .nx
.zrow:  xor a
        ld b,8
.zb:    ld (ix+0),a
        inc ix
        djnz .zb
.nx:    ld hl,vi
        dec (hl)
        ld hl,(vpi)
        ld a,(vw)
        ld c,a
        ld b,0
        or a
        sbc hl,bc
        ld (vpi),hl
        ld hl,(vpb)
        ld bc,24
        or a
        sbc hl,bc
        ld (vpb),hl
        ld hl,vyy
        dec (hl)
        jp nz,.r
        jp .end
.blank: ld a,(vyy)
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.bz:    ld (ix+0),a
        inc ix
        djnz .bz
.end:
        ld a,(vany)
        or a
        ret z               ; nothing visible: no slot
        ld a,(vbase)        ; the 4-bit pattern vbase + vn, in the half no sprite shows now
        ld e,a
        ld a,(vn)
        add a,e
        ld e,a
        ld (vpat),a
        srl a
        bit 0,e
        jr z,.p0
        or 0x80
.p0:    ld bc,0x303B
        out (c),a
        ld hl,PAT
        ld bc,0x805B
        otir
        ld a,(vc0)          ; X = 88 + 8 * (c0 + 2 tx)
        ld l,a
        ld a,(vtx)
        add a,a
        add a,l
        ld l,a
        ld h,0
        bit 7,a
        jr z,.xp
        dec h
.xp:    add hl,hl
        add hl,hl
        add hl,hl
        ld a,88
        add hl,a
        ex de,hl            ; DE = X
        ld hl,(vat)         ; the attributes go to the table, sent at the switch
        ld (hl),e
        inc hl
        ld a,(vr0)          ; Y = 160 - r0 - h + 16 ty
        ld c,a
        ld a,(vh)
        add a,c
        ld c,a
        ld a,160
        sub c
        ld c,a
        ld a,(vty)
        add a,a
        add a,a
        add a,a
        add a,a
        add a,c
        ld (hl),a
        inc hl
        ld a,(vpal)
        or d                ; X8
        ld (hl),a
        inc hl
        ld a,(vpat)
        srl a
        or 0xC0             ; visible, 5th byte
        ld (hl),a
        inc hl
        ld a,(vpat)
        and 1
        ld a,0x80           ; 4-bit
        jr z,.p1
        or 0x40
.p1:    ld (hl),a
        inc hl
        ld (vat),hl
        ld hl,vn
        inc (hl)
        ret

; colmask: A = 0xFF if column (vj) is shown (j < w, and c0 + j < 22 unsigned: not the hidden margin), else 0
colmask:
        ld a,(vj)
        ld hl,vw
        cp (hl)
        jr nc,.z
        ld hl,vc0
        add a,(hl)
        cp 22
        jr nc,.z
        ld a,0xFF
        ret
.z:     xor a
        ret

; tbyte: HL = a figure ink byte, A = the final buffer's byte there, (vmk) = the column's mask ->
;   E = visible ink, C = plane 0 shown, B = plane 1 shown (Enhanced; else 0); vany |= every pixel shown
tbyte:  ld (vbf),a
        ld a,(vmk)
        and (hl)
        ld e,a              ; the figure's ink
        ld a,(enh_flag)
        or a
        jr nz,.en
        ld a,(vbf)
        and e
        ld e,a              ; visible ink: the ink AND the final buffer
        ld bc,0
        ld a,(vany)
        or e
        ld (vany),a
        ret
.en:    push hl             ; p0, p1: the same byte w*h and 2*w*h on
        ld bc,(vwh)
        add hl,bc
        ld a,(vmk)
        and (hl)
        ld d,a              ; p0
        add hl,bc
        ld a,(vmk)
        and (hl)
        ld b,a              ; p1
        pop hl
        ld a,(vbf)
        or e
        cpl                 ; hole = planes where neither the figure's ink nor anything after it drew
        ld c,a
        ld a,b
        or d
        and c
        ld c,a              ; holes shown
        ld a,(vbf)
        and e
        ld e,a              ; visible ink
        or c
        ld c,a              ; every pixel shown
        ld a,(vany)
        or c
        ld (vany),a
        ld a,c
        and b
        ld b,a              ; p1 shown
        ld a,c
        and d
        ld c,a              ; p0 shown
        ret

; out4: E, C, B -> 4 pattern bytes at IX (NIB_k[E] + 2 NIB_k[C] + 4 NIB_k[B], no carries: codes 1-7), IX += 4
out4:   ld a,b
        or c
        jr nz,.full
        ld a,e
        or a
        jr nz,.ink
        ld (ix+0),a         ; nothing shown: four zero bytes
        ld (ix+1),a
        ld (ix+2),a
        ld (ix+3),a
        jr .adv
.ink:   ld h,NIB >> 8       ; no plane shown in this byte: the ink's nibbles only
        ld l,e
        ld a,(hl)
        ld (ix+0),a
        inc h
        ld a,(hl)
        ld (ix+1),a
        inc h
        ld a,(hl)
        ld (ix+2),a
        inc h
        ld a,(hl)
        ld (ix+3),a
        jr .adv
.full:  ld h,NIB >> 8
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        add a,(hl)
        add a,a
        ld l,e
        add a,(hl)
        ld (ix+0),a
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        add a,(hl)
        add a,a
        ld l,e
        add a,(hl)
        ld (ix+1),a
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        add a,(hl)
        add a,a
        ld l,e
        add a,(hl)
        ld (ix+2),a
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        add a,(hl)
        add a,a
        ld l,e
        add a,(hl)
        ld (ix+3),a
.adv:   inc ix
        inc ix
        inc ix
        inc ix
        ret

sv_hl:  dw 0
sv_de:  dw 0
sv_bc:  dw 0
sv_sp:  dw 0
sv_x:   dw 0
lptr:   dw LIST
vscr:   dw 0
nfull:  dw 0
nfig:   db 0
vprev:  db 0
vn:     db 0
vhero:  db 7
vrec:   dw 0
vink:   dw 0
vo:     dw 0
vw:     db 0
vh:     db 0
vpal:   db 0
vc0:    db 0
vr0:    db 0
vtx:    db 0
vty:    db 0
vleft:  db 0
vyy:    db 0
vi:     db 0
vv:     db 0
va:     db 0
vb:     db 0
vwh:    dw 0
vn0:    dw 0
vn1:    dw 0
vsp:    dw 0
vg:     dw 0
vplen:  dw 0
vdoff:  dw 0
vpp:    db 0
vcol:   db 0
vtyp:   db 0
vh0:    db 0
vrt:    dw 0
vnib:   db 1
vnibh:  db 0x10
enh_flag:
        db 0
vR:     db 0
vT:     db 0
sv_a:   db 0
vj:     db 0
vany:   db 0
vrow:   db 0
vbase:  db 64               ; the half the next frame's patterns go to (0 or 64)
vpat:   db 0
vat:    dw 0
ntrunc: dw 0
vl:     dw 0
vel:    dw 0
vflen:  dw 311
vs1:    dw 278
page_end:

; ---------------------------------------------------------------------------------------------
; Second block of the hook page, past the scratch buffer and its spill (SCR + 2688 + 192 = 0x3680).
        ORG 0x3700
ATAB    EQU 0x3D00          ; the frame's sprite attributes, 5 bytes each (64 at most), sent in one go at the switch
S0      EQU 132             ; the blits and the switch start no sooner than 4 lines below the play area (rows 16-127)
WMIN    EQU 0             ; lines from the hook's start to the earliest blit: the original's 0xE200 -> 0xE206 takes
                            ; 295 lines at 3.5 MHz (JNext), the blits and switch at 28 MHz 43; 20 less for the wait
                            ; for the window, so the game's pace stays about the original's
code2:
; At 0xE200 (CALL 0xE148; the original then runs 0xE203 CALL 0xE1AD): both blits and the sprite switch together.
; 1. each figure's visible ink -> 4-bit patterns in the half of the pattern memory that no sprite shows, and
;    its attributes -> a table; 2. wait for the beam to leave the play area, at about the time the original's
;    blits would end (game speed kept); 3. the game's own two blits at 28 MHz, with the registers and SP its
;    CALLs see in the original; 4. the table -> the sprite attributes in one burst, unused slots off.
; The ULA picture and the sprites change inside one beam window below the play area, so no frame shows the
; new sprites over the old picture or the reverse (patch.display-atomic-switch).
; Returns to 0xE206 with registers, R, SAVESP and the stack word as the original leaves them.
h_commit:
        push af
        ld a,r              ; E = 7
        ld (vR),a
        push bc
        ld bc,0x243B
        ld a,0x07
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld (vspd),a
        pop bc
        ld a,38             ; 55 - 7 - 10: the original's 0xE200 -> 0xE206 is 55 M1 (mod 128)
        call mkT
        push bc
        push de
        push hl
        push ix             ; the tiles' pattern pointer (restored before the game's blits)
    IFDEF ENHCIM
        push iy             ; the code-image rows' accumulator
        exx                 ; and their alternate registers: the game's BC', DE', HL'
        push bc
        push de
        push hl
        exx
    ENDIF
        call line           ; the beam at the start
        ld (vl),hl
        ld hl,0
        ld (vel),hl
        ld (vpoll),hl
        ld hl,311           ; lines a frame and the last start line (the blits and switch take 43 lines at 28 MHz in
                            ; JNext, so they end 2 lines above the play area); 60 Hz (NR 0x05 bit 2): 264, 230
        ld de,278
        ld bc,0x243B
        ld a,0x05
        out (c),a
        inc b
        in a,(c)
        and 4
        jr z,.hz
        ld hl,264
        ld de,230
.hz:    ld (vflen),hl
        ld (vs1),de
        ld a,(HFLAG)
        or a
        ld a,7
        jr z,.hc
        ld a,(HIDX)
        ld hl,HTAB
        add hl,a
        ld a,(hl)
        and 7
.hc:    ld (vhero),a
        nextreg 0x50,LPAGE
        xor a
        ld (vn),a
        ld hl,ATAB
        ld (vat),hl
        ld hl,LIST
        ld (vrec),hl
        ld a,(nfig)
        or a
        jp z,.hide
        ld (vleft),a
.fig:   ld hl,(vrec)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (vo),de
        ld a,(hl)
        ld (vw),a
        inc hl
        ld a,(hl)
        ld (vh),a
        inc hl
        ld a,(hl)
        inc hl
        ld (vcol),a
        ld a,(hl)
        inc hl
        ld (vtyp),a
        ld (vink),hl
        ld a,(vcol)
        cp 0xFF
        jr nz,.c1
        ld a,(vhero)
.c1:    ld b,a              ; B = the plain colour
        ld a,(enh_flag)
        or a
        jr z,.c2
        ld a,(vtyp)
        ld hl,POFF
        add hl,a
        ld a,(hl)
        cp 0xFF
        jr nz,.c3
        ld a,b
        add a,8             ; the hero: offset 8 + his health colour (FILL and LINE are it)
.c3:    ld b,a
.c2:    ld a,b
        swapnib
        ld (vpal),a
        ld a,(vw)
        ld e,a
        ld a,(vh)
        ld d,a
        mul d,e
        ld (vwh),de
        ld de,(vo)
        ex de,hl            ; HL = offset (a figure left of the window starts below the buffer: -2)
        ld bc,48
        add hl,bc
        ld bc,24
        ld e,-2
.dv:    or a
        sbc hl,bc
        jr c,.dd
        inc e
        jr .dv
.dd:    add hl,bc
        ld a,l
        cp 22               ; in the hidden columns 22-23: the figure starts left of the window
        jr c,.dn
        sub 24
        inc e
.dn:    ld (vc0),a
        ld a,e
        ld (vr0),a
        ld hl,(vink)        ; next record
    IFDEF ENHCIM
        ld a,(enh_flag)
        or a
        jr z,.dflt
        call cimparse       ; the code image's page, row 0 address, stride, shift: HL = the next record
        jr .r1
.dflt:
    ENDIF
        ld de,(vwh)
        add hl,de
        ld a,(enh_flag)
        or a
        jr z,.r1
        add hl,de
        add hl,de
.r1:    ld (vrec),hl
        ld a,(vr0)          ; rows past the buffer's top (row 111) are not on the screen
        ld b,a
        ld a,112
        sub b
        ld hl,vh
        cp (hl)
        jr nc,.hk
        ld (hl),a
.hk:
    IFDEF ENHCIM
        ld a,(enh_flag)
        or a
        jr z,.nm
        ld a,(vpp)
        nextreg 0x50,a      ; the figure's code image at slot 0 for its tiles
.nm:
    ENDIF
        xor a
        ld (vty),a
.ty:    xor a
        ld (vtx),a
.tx:    call tile
        ld a,(vtx)
        inc a
        ld (vtx),a
        add a,a
        ld hl,vw
        cp (hl)
        jr c,.tx
        ld a,(vty)
        inc a
        ld (vty),a
        add a,a
        add a,a
        add a,a
        add a,a
        ld hl,vh
        cp (hl)
        jr c,.ty
    IFDEF ENHCIM
        nextreg 0x50,LPAGE  ; the records back
    ENDIF
        ld hl,vleft
        dec (hl)
        jp nz,.fig
.hide:  xor a
        ld (nfig),a
        ld hl,LIST
        ld (lptr),hl
        nextreg 0x50,0xFF
        call wait
    IFDEF ENHCIM
        exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
    ENDIF
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        inc sp              ; SP as at the site: the original's CALLs push their return there
        inc sp
        call 0xE148         ; the game's two blits, at 28 MHz
        call 0xE1AD
        push af
        push bc
        push de
        push hl
        call burst
        call pacewait       ; to the original's 0xE200 -> 0xE206 time, less the other hooks' extra time
        pop hl
        pop de
        pop bc
        pop af
        ld (sv_a),a
        ld a,(vspd)
        nextreg 0x07,a      ; the incoming speed
        ld a,(vT)
        ld r,a
        ld a,(sv_a)         ; N = 10 from here (the two NOPs stand for the NEXTREG that was here)
        push hl             ; the stack word the original's second CALL leaves (0xE206); s_x returns there
        ld hl,0xE206
        ex (sp),hl
        nop
        nop
        jp s_x

; burst: the table -> sprite attributes from slot 0, slots used last time and not now off, sprites on,
; and the next frame's patterns to the other half
burst:  ld bc,0x303B
        xor a
        out (c),a
        ld a,(vn)
        or a
        jr z,.nb
        ld d,a
        ld hl,ATAB
        ld c,0x57
.b:     ld b,5
        otir
        dec d
        jr nz,.b
.nb:    ld a,(vn)
        ld d,a
        ld a,(vprev)
        sub d
        jr z,.nh
        jr c,.nh
        ld e,a
        ld a,d
        ld bc,0x303B
        out (c),a
        ld c,0x57
.h:     xor a
        out (c),a
        out (c),a
        out (c),a
        out (c),a
        dec e
        jr nz,.h
.nh:    ld a,d
        ld (vprev),a
        nextreg 0x15,1
        ld a,(vbase)
        xor 64
        ld (vbase),a
        ret

; wait: at least WMIN lines since the start, then the beam on a line S0..vs1 (a bounded number of polls)
wait:
.w1:    call tick
        ld a,(vpoll+1)
        cp 117
        ret nc
        ld hl,(vel)
        ld de,WMIN
        or a
        sbc hl,de
        jr c,.w1
.w2:    call tick
        ld a,(vpoll+1)
        cp 117
        ret nc
        ld de,S0
        or a
        sbc hl,de
        jr c,.w2
        add hl,de
        ex de,hl
        ld hl,(vs1)
        or a
        sbc hl,de
        jr c,.w2
        ret

; tick: HL = the line now; vel += lines since the last look
tick:   call line
        push hl
        ld de,(vl)
        or a
        sbc hl,de
        jr nc,.p
        ld de,(vflen)
        add hl,de
.p:     ld de,(vel)
        add hl,de
        ld (vel),hl
        pop hl
        ld (vl),hl
        ld de,(vpoll)
        inc de
        ld (vpoll),de
        ret

; line: HL = the raster line (NR 0x1E, 0x1F; line 0 = the ULA's top pixel row), read until the MSB is stable
line:   ld bc,0x243B
.r:     ld a,0x1E
        out (c),a
        inc b
        in d,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in e,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        cp d
        jr nz,.r
        and 1
        ld h,a
        ld l,e
        ret

vpoll:  dw 0
vpi:    dw 0
vpb:    dw 0
vm0:    db 0
vm1:    db 0
vmk:    db 0
vbf:    db 0
vb0:    db 0
vb1:    db 0

; Pace (2026-11-05): the build keeps the original's pace. Every hook's time beyond the original's is debt (signed,
; 1/16 line); the blit hook, after its switch, waits until the original's 0xE200 -> 0xE206 time less the debt.
; The constants are the hooks' 3.5 MHz parts in T-states, measured on the model (work/pace/consts.py); TGT is the
; original's blit (295.25 lines in JNext, from 0xE200 to 0xE206) less the hook's 3.5 MHz parts, in 1/16 line.
    IFDEF ENHCIM
TGT     EQU 4703 - 64       ; Enhanced: 4 lines less, calibrated on the quiet scene (+0.71%: the hooks' stub code in
                            ; contended RAM at 3.5 MHz costs more than its T-states); never below the original's pace
    ELSE
TGT     EQU 4703            ; 16 x (295.25 - (156 + 140) / 228)
    ENDIF
KFIG    EQU 17              ; 16 x (156 + 104 - 20) / 228: the 3.5 MHz parts against the original LD (0xBBAE),SP
KBOX0   EQU 37              ; flag off: 575 - 49 T (counted)
KBOX1   EQU 43              ; flag on: 932 - 315 T (measured)

; fig_end: debt += 16 x (lines since vfl) + KFIG; all registers kept
fig_end:
        push af
        push bc
        push de
        push hl
        call line
        ld de,(vfl)
        or a
        sbc hl,de
        jr nc,.p
        ld de,(vflen)
        add hl,de
.p:     add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,KFIG
        add hl,de
        call debt_hl
        pop hl
        pop de
        pop bc
        pop af
        ret

; debt_add: debt += HL; AF, BC, DE kept (HL is the caller's to restore)
debt_add:
        push af
        push de
        call debt_hl
        pop de
        pop af
        ret

; debt_hl: debt += HL (signed), held in -2048..30000
debt_hl:
        ld de,(vdebt)
        add hl,de
        bit 7,h
        jr z,.pos
        ld de,-2048
        ld a,h
        cp 0xF8
        jr nc,.st
        ex de,hl
        jr .st
.pos:   ld de,30000
        push hl
        or a
        sbc hl,de
        pop hl
        jr c,.st
        ex de,hl
.st:    ld (vdebt),hl
        ret

; pacewait: wait until 16 x vel >= TGT - debt (vel: lines since the hook's start), then debt = 16 x vel - (TGT - debt)
pacewait:
        ld hl,TGT
        ld de,(vdebt)
        or a
        sbc hl,de           ; need (signed)
        ld (vneed),hl
.w:     ld hl,(vel)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(vneed)
        or a
        sbc hl,de           ; 16 vel - need
        jp p,.done          ; >= 0 (16 vel is below 32768: vel at most a frame or two)
        ld a,(vpoll+1)
        cp 117              ; a bounded number of polls, as the window wait
        jr nc,.done
        call tick
        jr .w
.done:  ld (vdebt),hl
        ld hl,0
        call debt_hl        ; clamp
        ret

vdebt:  dw 0
vneed:  dw 0
vfl:    dw 0
vspd:   db 0
page2_end:

    IFDEF ENHCIM
; The Enhanced build's code-image routines, in the figure scratch it never uses (0x3300-0x36FF; tables 0x2B00-0x32FF);
; saved by the generated asm/nightshade_hooks_enh.asm as ns_page3.bin
        ORG 0x3300
code3:
BPT     EQU 0x2B00          ; Enhanced: 4 pages, BP_k[buffer byte] = the T2 page for pixel pair k's two bits
T2B     EQU 0x2F00          ; Enhanced: 4 pages, T2[bits][code byte] = its shown nibbles (in the figure scratch:
                            ; the Enhanced build plots no figure, so the scratch is free)
; Enhanced with code images (2026-11-05, pace): each graphic's painted codes as a 4-bit image (4 bytes a data byte,
; rows in data order, both orientations from the game's own flip) in the planes' space. The figure hook records
; where the plot's first data byte is in the image and the 2-pixel shift; the blit builds each pattern byte as
; code AND the shown mask: an ink nibble (odd code) shows where the final buffer is set, a gap nibble (even code)
; where it is clear: out = code & ~(((code ^ NIB_k[buffer]) & 0x11) * 15). No plane plots.
cimrec: ld a,(ix+0)         ; G = the type's graphic, its header (orientation bits 7, 6; width)
        ld l,a
        ld h,0
        add hl,hl
        ld de,GTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(de)
        ld (vhd),a
        and 15
        add a,a
        add a,a
        ld (vcst),a         ; stride: 4 x width
        ld hl,(sv_de)       ; the plot's data pointer, from G (header included)
        or a
        sbc hl,de
        ld (vdoff),hl
        ld a,(ix+0)         ; PLT entry: (type * 4 + orientation) * 3
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(vhd)
        rlca
        rlca
        and 3
        add hl,a
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        nextreg 0x50,PLTPAGE
        ld a,(hl)
        ld (vpp),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)           ; the entry's address (the image's start - 2)
        ld hl,(vdoff)
        add hl,hl
        add hl,de
        dec hl
        dec hl              ; start + 2 (offset - 2): the first plotted data byte's 4 code bytes
        ld (vcptr),hl
        nextreg 0x50,LPAGE
        ld hl,(lptr)
        push hl
        ld h,b              ; offset in the buffer = BC - BUF
        ld l,c
        ld de,BUF
        or a
        sbc hl,de
        ex de,hl
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(FW)
        ld (hl),a
        inc hl
        ld a,(FH)
        ld (hl),a
        inc hl
        ld e,7              ; bright white, or the hero (records 0xBC8E, 0xBC9E): his health colour at the blit
        ld a,ixh
        cp 0xBC
        jr nz,.col
        ld a,ixl
        cp 0x8E
        jr z,.hero
        cp 0x9E
        jr nz,.col
.hero:  ld e,0xFF
.col:   ld (hl),e
        inc hl
        ld a,(ix+0)
        ld (hl),a
        inc hl
        ld a,(vpp)
        ld (hl),a
        inc hl
        ld de,(vcptr)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(vcst)
        ld (hl),a
        inc hl
        ld a,(ix+14)        ; the 2-pixel shift: x AND 6, in code bytes
        and 6
        rrca
        ld (hl),a
        inc hl
        ld (lptr),hl
        jp h_fig.n2

; cimparse: HL = the record's fields after its header -> vpp, vcptr, vcst, vshb; HL = the next record
cimparse:
        ld a,(hl)
        ld (vpp),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (vcptr),de
        ld a,(hl)
        ld (vcst),a
        inc hl
        ld a,(hl)
        ld (vshb),a
        inc hl
        ret

; cimtile: the tile's code-image row (vcrow = vcptr + i * stride) and column offsets (4 j - shift); for each column
; its case, patched into cimrows' two CALLs: hidden (czero), inside the figure (cfast), or at its edge (cedge0 /
; cedge1, the masks patched in: the column's where 0 <= 4 j + k - shift < stride, else 0)
cimtile:
        ld a,(vi)
        ld d,a
        ld a,(vcst)
        ld e,a
        mul d,e
        ld hl,(vcptr)
        add hl,de
        ld (vcrow),hl
        ld a,(vtx)
        add a,a
        add a,a
        add a,a             ; 4 j0
        ld l,a
        ld h,0
        ld a,(vshb)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld (vco0),hl
        ld de,4
        add hl,de
        ld (vco1),hl
        ld a,(vco0)         ; q = 4 j - shift (8-bit, signed)
        ld c,a
        ld a,(vm0)
        ld b,a
        ld ix,vkm0
        call .case
        ld a,h
        or l
        jr nz,.s0
        ld a,(vkm0)         ; an edge: its masks into cedge0's AND immediates
        ld (cedge0.m0 + 1),a
        ld a,(vkm0 + 1)
        ld (cedge0.m1 + 1),a
        ld a,(vkm0 + 2)
        ld (cedge0.m2 + 1),a
        ld a,(vkm0 + 3)
        ld (cedge0.m3 + 1),a
        ld hl,cedge0
.s0:    ld (cimrows.c0 + 1),hl
        ld a,(vco0)
        add a,4
        ld c,a
        ld a,(vm1)
        ld b,a
        ld ix,vkm1
        call .case
        ld a,h
        or l
        jr nz,.s1
        ld a,(vkm1)
        ld (cedge1.m0 + 1),a
        ld a,(vkm1 + 1)
        ld (cedge1.m1 + 1),a
        ld a,(vkm1 + 2)
        ld (cedge1.m2 + 1),a
        ld a,(vkm1 + 3)
        ld (cedge1.m3 + 1),a
        ld hl,cedge1
.s1:    ld (cimrows.c1 + 1),hl
        ret
; .case: B = the column's mask, C = its q; four masks at IX (B where 0 <= q + k < stride, else 0);
; HL = czero (hidden), cfast (all four 0xFF) or 0 (an edge)
.case:  ld a,b
        or a
        ld hl,czero
        ret z
        ld d,4
        ld e,0xFF           ; AND of the four masks
.k:     ld a,c
        bit 7,a
        jr nz,.no
        ld h,a
        ld a,(vcst)
        cp h
        jr c,.no
        jr z,.no
        ld a,b
        jr .st
.no:    xor a
.st:    ld (ix+0),a
        inc ix
        and e
        ld e,a
        inc c
        dec d
        jr nz,.k
        ld a,e
        inc a
        ld hl,cfast
        ret z
        ld hl,0
        ret

; cimrows: the tile's 16 rows from the code image, then tile.end. The alternate registers hold the final buffer's row
; (HL'), the code image's row at column 0 (DE') and the stride (BC'); a row: the buffer's two bytes, column 0 through
; its routine (patched by cimtile; DE += 3), column 1 from DE + 1; rows past the figure's bottom blank, rows off the
; play area zero; one row up the figure: the buffer 24 bytes back, the code image one stride back. IYL gathers every
; pixel shown (vany). The game's BC', DE', HL' are saved by h_commit.
cimrows:
        ld iyl,0
        ld hl,(vcrow)
        ld de,(vco0)
        add hl,de
        ex de,hl
        ld hl,(vpb)
        ld a,(vcst)
        ld c,a
        ld b,0
        exx
.r:     ld a,(vi)
        bit 7,a
        jp nz,.blank
        ld hl,vr0
        add a,(hl)
        cp 112
        jp nc,.zrow
        exx
        ld a,(hl)
        ld (vb0),a
        inc hl
        ld a,(hl)
        ld (vb1),a
        dec hl
        push de
        exx
        pop de
        ld a,(vb0)
        ld c,a
.c0:    call cfast          ; patched: czero, cfast or cedge0
        inc de              ; column 1's code bytes
        ld bc,4
        add ix,bc
        ld a,(vb1)
        ld c,a
.c1:    call cfast          ; patched: czero, cfast or cedge1
        ld bc,4
        add ix,bc
        jr .nx
.zrow:  xor a
        ld (ix+0),a
        ld (ix+1),a
        ld (ix+2),a
        ld (ix+3),a
        ld (ix+4),a
        ld (ix+5),a
        ld (ix+6),a
        ld (ix+7),a
        ld de,8
        add ix,de
.nx:    exx
        ld a,l              ; the buffer: 24 bytes back
        sub 24
        ld l,a
        jr nc,.nc
        dec h
.nc:    ex de,hl            ; the code image: one stride back
        or a
        sbc hl,bc
        ex de,hl
        exx
        ld hl,vi
        dec (hl)
        ld hl,vyy
        dec (hl)
        jp nz,.r
        jr .end
.blank: ld a,(vyy)
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.bz:    ld (ix+0),a
        inc ix
        djnz .bz
.end:   ld a,iyl
        ld (vany),a
        jp tile.end

; The column routines: DE = 4 code bytes, C = the final buffer's byte -> 4 pattern bytes at IX; IYL |= them.
; Pattern byte k = T2[pair k of the buffer][code byte]: BP_k gives the page for the two buffer bits, the page maps a
; code byte to its shown nibbles (an odd code where the bit is set, an even one where it is clear).
czero:  xor a
        ld (ix+0),a
        ld (ix+1),a
        ld (ix+2),a
        ld (ix+3),a
        inc de              ; as the other routines: DE += 3
        inc de
        inc de
        ret
cfast:
        ld a,(de)
        inc de
        or a
        ld (ix+0),a
        jr z,.z0
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 0
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+0),a
        or iyl
        ld iyl,a
.z0:
        ld a,(de)
        inc de
        or a
        ld (ix+1),a
        jr z,.z1
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 1
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+1),a
        or iyl
        ld iyl,a
.z1:
        ld a,(de)
        inc de
        or a
        ld (ix+2),a
        jr z,.z2
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 2
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+2),a
        or iyl
        ld iyl,a
.z2:
        ld a,(de)
        or a
        ld (ix+3),a
        jr z,.z3
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 3
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+3),a
        or iyl
        ld iyl,a
.z3:
        ret
cedge0:
        ld a,(de)
        inc de
.m0:    and 0xFF            ; patched: this column's mask for code byte 0
        ld (ix+0),a
        jr z,.z0
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 0
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+0),a
        or iyl
        ld iyl,a
.z0:
        ld a,(de)
        inc de
.m1:    and 0xFF            ; patched: this column's mask for code byte 1
        ld (ix+1),a
        jr z,.z1
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 1
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+1),a
        or iyl
        ld iyl,a
.z1:
        ld a,(de)
        inc de
.m2:    and 0xFF            ; patched: this column's mask for code byte 2
        ld (ix+2),a
        jr z,.z2
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 2
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+2),a
        or iyl
        ld iyl,a
.z2:
        ld a,(de)
.m3:    and 0xFF            ; patched: this column's mask for code byte 3
        ld (ix+3),a
        jr z,.z3
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 3
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+3),a
        or iyl
        ld iyl,a
.z3:
        ret
cedge1:
        ld a,(de)
        inc de
.m0:    and 0xFF            ; patched: this column's mask for code byte 0
        ld (ix+0),a
        jr z,.z0
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 0
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+0),a
        or iyl
        ld iyl,a
.z0:
        ld a,(de)
        inc de
.m1:    and 0xFF            ; patched: this column's mask for code byte 1
        ld (ix+1),a
        jr z,.z1
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 1
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+1),a
        or iyl
        ld iyl,a
.z1:
        ld a,(de)
        inc de
.m2:    and 0xFF            ; patched: this column's mask for code byte 2
        ld (ix+2),a
        jr z,.z2
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 2
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+2),a
        or iyl
        ld iyl,a
.z2:
        ld a,(de)
.m3:    and 0xFF            ; patched: this column's mask for code byte 3
        ld (ix+3),a
        jr z,.z3
        ld b,a
        ld l,c
        ld h,(BPT >> 8) + 3
        ld h,(hl)
        ld l,b
        ld a,(hl)
        ld (ix+3),a
        or iyl
        ld iyl,a
.z3:
        ret

vhd:    db 0
vcst:   db 0
vshb:   db 0
vcptr:  dw 0
vcrow:  dw 0
vco0:   dw 0
vco1:   dw 0
vkm0:   ds 4
vkm1:   ds 4
page3_end:
        ASSERT page3_end <= 0x3700
    ENDIF

        ORG 0xD000
setup:  nextreg 0x43,0x20   ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal_tab
        ld b,0
.n:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .n
        nextreg 0x4B,0      ; nibble 0 is transparent
        xor a
.hd:    nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hd
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0
        ret
pal_tab:
        ds 256
setup_end:

        SAVEBIN "ns_ram.bin",0x5B4F,ram_end-0x5B4F
        SAVEBIN "ns_page.bin",0x2000,page_end-0x2000
        SAVEBIN "ns_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "ns_page2.bin",0x3700,page2_end-0x3700
        ASSERT page_end <= POFF
        ASSERT page2_end <= ATAB

; ---------------------------------------------------------------------------------------------
; Loading screen (nightshade.add_loading; from runs/nightshade/loading/stub.asm, the Rambo stub, 2026-11-04).
; The .nex carries the tape's loading screen in bank 5's screen area; bank 23 (pages 46, 47) is the entry
; bank, PC 0xC000: this code at 0xC000, bank 5's own screen bytes at 0xC200 (filled by the engine from the
; build), the exit at 0xFFD0. On entry the loader has left: slots 2-5 = 10,11,4,5, slots 6-7 = 68,69, DI,
; SP = 0xDFFE and the start address pushed just below SP, in the entry bank. The original start is page 20
; at 0xC000. No byte outside this bank differs when it leaves; its last instruction puts page 5 back at
; slot 5 and the next fetch is 0xC000 of page 20 (no trampoline in RAM). 250 frames or a key.
        MODULE ldscr
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 47; below it the stub's call stack
SEL     equ     $FE02           ; port $243B as found
TIMEOUT equ     250             ; frames: 5 s at 50 Hz
CAP     equ     250             ; most frames to wait for a held key to go
CLEAR   equ     3               ; frames with no key before leaving
LINE    equ     192             ; first line below the picture
picture equ     $C200           ; bank 5's own screen bytes (6912), written by nightshade.add_loading

        org     $C000
start:
        di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,$243B
        in      a,(c)
        ld      (SEL),a
        xor     a
        out     ($fe),a
; Show: a key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the menu doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,picture
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        xor     a
        out     ($fe),a
        ld      bc,$243B
        ld      a,(SEL)
        out     (c),a
        nextreg $55,47
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,$243B
        ld      a,$1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,($fe)
        cpl
        and     $1f
        or      e
        ld      e,a
        ld      a,d
        ret
code_end:
        org     $FFD0
        disp    $BFD0
; Runs from page 47 at slot 5. Bank 10's top bytes get what the loader's stack left there.
final:  nextreg $56,20
        nextreg $57,21
        ld      hl,$C000
        ld      ($DFFC),hl
        ld      sp,REGS-$4000-12
        pop     iy
        pop     ix
        ld      hl,($BFFF)      ; MEMPTR = $C000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,$DFFE
        ds      $BFFC-$
        nextreg $55,5           ; falls through to $C000, page 20
        assert  $ == $C000
        ent
        ENDMODULE
        SAVEBIN "ns_lstub.bin",0xC000,ldscr.code_end-0xC000
        SAVEBIN "ns_lfinal.bin",0xFFD0,0x30
