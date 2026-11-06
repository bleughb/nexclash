; Quazatron (Hewson, 1986, 48K) - colour v1.0, session 1: the scenery canvas on Layer 2. Facts: games/quazatron.md.
;
; Design (primary, built for smooth scrolling): the game's linear background (0x8300, 256 x 152, 1 bit) has a colour
; twin on a wrap-around Layer 2 canvas, 320 x 256 x 8 bits (banks L2BANK.., column-major: byte = x * 256 + y). The
; game's view sits at canvas origin (OX, OY); its in-place scroll moves become an origin change; only the strip the
; game pastes (C1A5) is written. A pixel's colour is the ROLE of the drawing list that last cleared it to paper
; (scenery lists: masks draw the surfaces), kept in a tag strip (TAGS, column-major, 152 bytes a column) that mirrors
; the game's 32-pixel column strip (0x8080). Ink pixels hold 0..15, the ZX ink of the screen cell they show in
; (black on the deck, the void's colour below it), set at the commit (C05A, after the game's attributes).
; Layer 2 covers the play area (clip) above the ULA, so the ULA play area is hidden; the panel below is the ULA's.
; Droids become hardware sprites placed from the same origin (session 2); smooth mode moves the shown offset.
;
; Sites (original bytes checked by quazatron.py):
;   BE2E CD 7D B0  CALL B07D (scenery list into the strip)  -> CALL t_list   (tags after the game's own draw)
;   BE82 CD 44 C0  CALL C044 (strip clear)                  -> CALL t_clr
;   BFEC, BFFB CD A5 C1  CALL C1A5 (strip paste)            -> CALL t_paste  (tags -> canvas at the origin)
;   E10E 21 FF 94 / E11D 21 00 84 / E12C 21 02 83 / E146 21 FD 95  the scroll moves -> JP t_sd / t_su / t_sl / t_sr
;   C05A 11 00 83  background to screen + attributes        -> JP t_c05a     (commit: offset, inks, Layer 2 on)
;   B2C9 21 00 40  screen clear                             -> JP t_cls      (Layer 2 off)
;   B1FB ED 53 63 B2  the printer                           -> JP t_prn      (Layer 2 off when it prints in the play area)
; Memory: trampolines in alt ROM image 1 (0x386E-); code and state in Next page HPAGE, mapped at slot 2 (0x4000) only
; inside a hook (the ISR at E6E6 / BD2D never touches 0x4000-0x5FFF); canvas pages at slot 6 (0xC000) only inside a
; hook's work (the ISR never touches 0xC000-0xDFFF). The game's stack is at 0x61xx (slot 3): never remapped.
; R: the game reads R (B5B1, in the ISR); every trampoline brackets its extra M1s with HLIB_R_IN / HLIB_R_OUT.
; Speed: the work runs at 28 MHz, the caller's speed restored (hlib_speed). Pace: not yet repaid (session 2).

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"

HPAGE   EQU 26                  ; bank 13 lower half
ULAPAGE EQU 10
L2BANK  EQU 18                  ; Layer 2 canvas: banks 18-22 = pages 36-45
L2PAGE  EQU 36
TS      EQU 152                 ; tag strip column stride
R_FLOOR EQU 16                  ; palette: 0-15 ZX inks, 16 floor, 17 wall, 18 ramp, 19 fringe, 20 face (the ink inside a
R_WALL  EQU 17                  ; wall part), 21 arrow, 22 object, 23 pad, 24 console screen (its OR ink), 25 bezel
R_FACE  EQU 20
R_SCREEN EQU 24
R_CONSOLE EQU 25

TCOL    EQU 0x4600              ; 32 words: TAGS + px * TS
PALINIT EQU 0x4640              ; 32 Layer 2 palette entries (2 bytes each), from quazatron.py
DECKPAL EQU 0x4680              ; 8 papers x 5 entries (16-20) x 2 bytes, from quazatron.py
ROWBUF  EQU 0x46D0              ; 32 attributes
ROLETAB EQU 0x4700              ; (list - 0x9600) >> 3 -> role, from quazatron.py
VSPD    EQU 0x47C0
HLIB_V_R EQU 0x47C1             ; 3
OX      EQU 0x47C4              ; 2: canvas x of the view's left edge (0-319)
OY      EQU 0x47C6              ; canvas y of the view's top line
L2ON    EQU 0x47C7
DECKP   EQU 0x47C8              ; deck attribute last programmed (0xFF: none)
SLOT6   EQU 0x47C9
LST     EQU 0x47CA              ; 2
ROLE    EQU 0x47CC
OPF     EQU 0x47CD              ; the part's flags
P0      EQU 0x47CE              ; 2: TAGS + (x + jstart) * TS
JST     EQU 0x47D0              ; first visible bit of the part
JN      EQU 0x47D1              ; visible bits
TROW    EQU 0x47D2              ; tag row of the part's first drawn row
NROWS   EQU 0x47D3
CX      EQU 0x47D4              ; 2
CY      EQU 0x47D6
PW      EQU 0x47D7
CR      EQU 0x47D8              ; commit: view cell row
CC      EQU 0x47D9              ; commit: view cell column
TINK    EQU 0x47DA
SPX     EQU 0x47DB              ; 2: the record's x (signed)
SPY     EQU 0x47DD              ; the record's y
GRP     EQU 0x47DE              ; sprite groups (3 sprites, 3 patterns each) used this update
GPREV   EQU 0x47DF              ; ... last update
TYP     EQU 0x47E0              ; the record's A000 type (plate index)
REC     EQU 0x47E1              ; 2
DRV     EQU 0x47E3              ; 2: the player's drive list
NREC    EQU 0x47E5
S0      EQU 46                  ; sprite store: page 46 = (list - 0x9C00) >> 1 -> 0-3 enemy frame / image / 255,
                                ; pages 47.. = images (16 x 48 x 8 bits, 10 a page), from quazatron.py sprite_store
MAXG    EQU 21
FLAGS   EQU 0x4800              ; 40 x 32 canvas cells: the ink index their ink bytes hold (0xFF: unknown)
TAGS    EQU 0x4D00              ; 32 columns x 152 rows

; game variables
G_AF0E  EQU 0xAF0E
G_AF10  EQU 0xAF10
G_AF14  EQU 0xAF14
G_AF15  EQU 0xAF15
G_AF16  EQU 0xAF16
G_AF17  EQU 0xAF17
G_AF2D  EQU 0xAF2D
G_DECK  EQU 0xB044

; ============================================================================================================
        ORG 0x4000
        INCLUDE "lib/hlib_r.asm"        ; HLIB_R_IN / OUT, hlib_r_set

; p_tags: HL = the list just drawn into the strip. Repeat its geometry (B07F) into the tag strip: mask bits -> the
; list's role, OR bits -> 0 (ink), overwrite bits -> ink / role. A part of height 0 ends the list, as in B0EC.
p_tags: ld (LST),hl
        ld de,-0x9600
        add hl,de
        jr nc,.floor
        ld a,h
        cp 6
        jr nc,.floor
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ld h,high ROLETAB
        ld a,(hl)
        jr .rok
.floor: ld a,R_FLOOR
.rok:   ld (ROLE),a
        ld hl,(LST)
        ld b,(hl)
        inc hl
.part:  push bc
        ld a,(hl)               ; x offset (signed)
        ld e,a
        rla
        sbc a,a
        ld d,a
        push hl
        ld hl,(G_AF0E)
        add hl,de               ; HL = x
        ld b,h
        ld c,l
        ld de,7
        add hl,de
        ld a,h
        or a
        jr nz,.xskip
        ld a,l
        cp 39
        jr nc,.xskip
        ; visible bits: jstart = max(0, -x), jend = min(8, 32 - x)
        xor a
        bit 7,b
        jr z,.js
        ld a,c
        neg                     ; -x (1..7)
.js:    ld (JST),a
        ld e,a                  ; E = jstart
        ld a,32
        sub c                   ; 32 - x (x in -7..31 -> 1..39)
        cp 8
        jr c,.je
        ld a,8
.je:    sub e
        ld (JN),a
        ld a,c
        add a,e                 ; x + jstart (0..31)
        add a,a
        ld l,a
        ld h,high TCOL
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a
        ld (P0),hl
        pop hl
        inc hl
        ld a,(G_AF10)
        add a,(hl)
        ld d,a                  ; D = row
        inc hl
        ld a,(hl)
        inc hl                  ; HL = glyph
        ld (OPF),a
        and 63
        jr z,.endl              ; RET Z in the original
        ld e,a                  ; E = height
        push hl
        ld c,e
        ld b,0
        add hl,bc
        ex (sp),hl              ; (SP) = next part, HL = glyph
        ld a,(G_AF16)
        cp d
        jr nc,.noclip
        ld a,d
        add a,e
        jr nc,.vskip
        jr z,.vskip
        ld e,a                  ; rows left
        ld a,d
        neg
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a                  ; glyph += -D
        ld d,0
.noclip:
        ld a,(G_AF17)
        sub d
        cp e
        jr nc,.rows
        ld e,a
.rows:  ld a,d
        ld (TROW),a
        ld a,e
        ld (NROWS),a
        or a
        jr z,.vskip
        call rowloop
.vskip: pop hl                  ; next part
        pop bc
        dec b
        jp nz,.part
        ret
.xskip: pop hl                  ; the x byte: skip y, read the height, as B178
        inc hl
        inc hl
        ld a,(hl)
        and 63
        inc hl
        ld e,a
        ld d,0
        add hl,de
        pop bc
        dec b
        jp nz,.part
        ret
.endl:  pop bc
        ret

; rowloop: HL = the first drawn glyph row; TROW, NROWS, P0, JST, JN, OPF, ROLE set.
rowloop:
        ld a,(NROWS)
        ld b,a
.row:   push bc
        ld c,(hl)               ; glyph byte
        inc hl
        push hl
        ld a,(JST)
        or a
        jr z,.sh0
        ld b,a
.shl:   sla c
        djnz .shl
.sh0:   ld hl,(P0)
        ld a,(TROW)
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld de,TS
        ld a,(JN)
        ld b,a
        ld a,(OPF)
        bit 7,a
        jr nz,.mask
        bit 6,a
        jr nz,.set
.or:    ld a,(ROLE)
        cp R_CONSOLE
        ld a,0
        jr nz,.or0
        ld a,R_SCREEN           ; a console's OR ink is its screen
.or0:   sla c
        jr nc,.or1
        ld (hl),a
.or1:   add hl,de
        djnz .or0
        jr .next
.mask:  ld a,(ROLE)
        cp R_WALL
        jr z,.mw
.mk:    sla c
        jr nc,.mk1
        ld (hl),a
.mk1:   add hl,de
        djnz .mk
        jr .next
.mw:    sla c                   ; a wall part: its 0 bits over ink become the face tone
        jr c,.mw1
        inc (hl)
        dec (hl)
        jr nz,.mw2
        ld (hl),R_FACE
        jr .mw2
.mw1:   ld (hl),a
.mw2:   add hl,de
        djnz .mw
        jr .next
.set:   ld a,(ROLE)
.st:    sla c
        jr nc,.st1
        ld (hl),0
        jr .st2
.st1:   ld (hl),a
.st2:   add hl,de
        djnz .st
.next:  ld hl,TROW
        inc (hl)
        pop hl
        pop bc
        djnz .row
        ret

; p_clr: the strip was cleared to ink (C044): tag rows 0 .. AF17-1 of all 32 columns = 0.
p_clr:  ld a,(G_AF17)
        or a
        ret z
        ld hl,TCOL
        ld b,32
.c:     push bc
        ld e,(hl)
        inc l
        ld d,(hl)
        inc l
        push hl
        ex de,hl
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        ld a,(G_AF17)
        dec a
        jr z,.c1
        ld c,a
        ld b,0
        ldir
.c1:    pop hl
        pop bc
        djnz .c
        ret

; rd56: A = NR 0x56
rd56:   ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ret

; p_paste: after C1A5: strip columns 0..W-1 (W = 16 if AF2D = 1, else 32), rows 0..AF17-1 -> canvas at
; (OX + AF14 * 8 + px, OY + AF15 + row); the canvas cells touched -> FLAGS 0xFF.
p_paste:
        call rd56
        ld (SLOT6),a
        ld a,(G_AF2D)
        cp 1
        ld a,16
        jr z,.w
        ld a,32
.w:     ld (PW),a
        ld a,(G_AF14)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(OX)
        add hl,de
        call mod320
        ld (CX),hl
        ld a,(OY)
        ld b,a
        ld a,(G_AF15)
        add a,b
        ld (CY),a
        ld a,(G_AF17)
        or a
        jp z,.done
        ld hl,TCOL
        ld a,(PW)
        ld b,a
.col:   push bc
        push hl                 ; TCOL entry
        ld hl,(CX)
        ld a,l                  ; page = L2PAGE + (cx >> 5)
        srl h
        rra
        srl h
        rra
        srl h
        rra
        srl h
        rra
        srl h
        rra
        add a,L2PAGE
        nextreg 0x56,a
        ld hl,(CX)
        ld a,l
        and 31
        add a,0xC0
        ld d,a
        ld a,(CY)
        ld e,a
        pop hl
        push hl
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                  ; HL = tag column
        ld a,(G_AF17)
        ld b,a
.cp:    ld a,(hl)
        ld (de),a
        inc hl
        inc e
        djnz .cp
        ld hl,(CX)              ; next canvas column
        inc hl
        call mod320
        ld (CX),hl
        pop hl
        inc l
        inc l
        pop bc
        djnz .col
        ; flags: cell columns (cx0 >> 3) .. + W/8 - 1, cell rows (CY >> 3) .. ((CY + rows - 1) >> 3), wrapping
        ld a,(PW)
        rrca
        rrca
        rrca
        and 7
        ld b,a                  ; cell columns
        ld hl,(CX)              ; CX is now cx0 + W: step back
        ld a,(PW)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        jr nc,.f0
        ld de,320
        add hl,de
.f0:    ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        ld c,a                  ; C = first cell column (0..39)
.fc:    push bc
        ld a,(CY)
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; first cell row
        ld a,(G_AF17)
        dec a
        ld d,a
        ld a,(CY)
        and 7
        add a,d                 ; offset of the last row from the first cell's top
        rrca
        rrca
        rrca
        and 31
        inc a
        ld b,a                  ; cell rows touched
.fr:    push bc
        push de
        ld a,e
        and 31
        call cellptr            ; HL = FLAGS + row * 40 + C
        ld (hl),0xFF
        pop de
        inc e
        pop bc
        djnz .fr
        pop bc
        inc c
        ld a,c
        cp 40
        jr c,.fc1
        ld c,0
.fc1:   djnz .fc
.done:  ld a,(SLOT6)
        nextreg 0x56,a
        ret

; cellptr: A = cell row (0..31), C = cell column (0..39) -> HL = FLAGS + A * 40 + C. DE lost.
cellptr:
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; *8
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl               ; *32
        add hl,de               ; *40
        ld e,c
        ld d,0
        add hl,de
        ld de,FLAGS
        add hl,de
        ret

; mod320: HL in 0..639 -> HL mod 320
mod320: push de
        ld de,320
        or a
        sbc hl,de
        jr nc,.m
        add hl,de
.m:     pop de
        ret

; p_off: Layer 2 off (outside play)
p_off:  xor a
        ld (L2ON),a
        nextreg 0x15,0
        ld bc,0x123B
        out (c),a
        ret

; p_pre: before the game's own copy (C05A): scroll registers from the origin, the deck's palette, Layer 2 and the
; sprites on. The original shows its new bitmap with the old attributes during its copy; so does this (p_inks after).
p_pre:
        ; scroll: X = OX - 32 (mod 320), Y = OY - 32
        ld hl,(OX)
        ld de,32
        or a
        sbc hl,de
        jr nc,.x
        ld de,320
        add hl,de
.x:     ld a,l
        nextreg 0x16,a
        ld a,h
        and 1
        nextreg 0x71,a
        ld a,(OY)
        sub 32
        nextreg 0x17,a
        ; deck palette (roles 16-19) when the deck's attribute changes
        ld a,(G_DECK)
        ld hl,DECKP
        cp (hl)
        jr z,.pal
        ld (hl),a
        rrca
        rrca
        rrca
        and 7                   ; paper
        ld b,a
        add a,a
        add a,a
        add a,b
        add a,a                 ; * 10 bytes
        add a,low DECKPAL
        ld l,a
        ld h,high DECKPAL
        nextreg 0x43,0x10
        nextreg 0x40,R_FLOOR
        ld b,10
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
.pal:   ld a,(L2ON)
        or a
        ret nz
        inc a
        ld (L2ON),a
        nextreg 0x15,0x01       ; sprites visible, S L U
        ld a,2
        ld bc,0x123B
        out (c),a
        ret

; p_inks: after C05A + C0C3 (the attributes are current): every view cell's ink bytes = its attribute's ink.
p_inks:        call rd56
        ld (SLOT6),a
        xor a
        ld (CR),a
.crow:  ; this row's 32 attributes -> ROWBUF (the ULA page at slot 6)
        nextreg 0x56,ULAPAGE
        ld a,(CR)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xD800
        add hl,de
        ld de,ROWBUF
        ld bc,32
        ldir
        xor a
        ld (CC),a
.ccol:  ld a,(CC)
        add a,low ROWBUF
        ld l,a
        ld h,high ROWBUF
        ld a,(hl)
        ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld (TINK),a
        ; canvas cell: column ((OX >> 3) + CC) mod 40, row ((OY >> 3) + CR) & 31
        ld hl,(OX)
        ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        ld b,a
        ld a,(CC)
        add a,b
        cp 40
        jr c,.c40
        sub 40
.c40:   ld c,a
        ld a,(OY)
        rrca
        rrca
        rrca
        and 31
        ld b,a
        ld a,(CR)
        add a,b
        and 31
        push af
        call cellptr
        pop de                  ; D = cell row
        ld a,(TINK)
        cp (hl)
        jr z,.same
        ld (hl),a
        call recell             ; C = cell column, D = cell row, A = ink
.same:  ld hl,CC
        inc (hl)
        ld a,(hl)
        cp 32
        jr c,.ccol
        ld hl,CR
        inc (hl)
        ld a,(hl)
        cp 19
        jr c,.crow
        ld a,(SLOT6)
        nextreg 0x56,a
        ret

; recell: canvas cell (C column, D row): every ink byte (< 16) of its 8 x 8 -> A. Maps its page at slot 6.
recell: ld e,a
        ld a,c
        rrca
        rrca
        and 0x3F
        add a,L2PAGE
        nextreg 0x56,a
        ld a,c
        and 3
        add a,a
        add a,a
        add a,a
        add a,0xC0
        ld h,a                  ; column (C & 3) * 8 -> 0xC000 + that * 256
        ld a,d
        add a,a
        add a,a
        add a,a
        ld l,a                  ; row * 8
        ld b,8
.k:     push bc
        push hl
        ld b,8
.j:     ld a,(hl)
        cp 16
        jr c,.j0
        cp R_FACE               ; a wall face's ink: the void's ink in a void cell, kept on the deck
        jr nz,.j1
        inc e
        dec e
        jr z,.j1
.j0:    ld (hl),e
.j1:    inc l
        djnz .j
        pop hl
        inc h
        pop bc
        djnz .k
        ret

;p_spr: after E656 (the blocks are on the screen): every draw record (A320, AF09 of them) as sprites, the last
; record (drawn last, in front) first, so it takes the lowest sprite numbers (sprite 0 on top). Enemies: one group
; (image 4 (type - 1) + frame); the player: a group per part (second weapon, dome + AFA4, weapon, drive, chassis);
; others: the record's list. Groups not used since the last update are hidden.
p_spr:  ld a,(L2ON)
        or a
        ret z
        ld hl,(0xDDAE)          ; the drive list (DDAE is in slot 6: read before any mapping)
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (DRV),hl
        call rd56
        ld (SLOT6),a
        xor a
        ld (GRP),a
        ld a,(0xAF09)
        cp 8
        jr c,.n
        ld a,7
.n:     or a
        jp z,.hide
        ld (NREC),a
        dec a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,0xA320
        add hl,de
.rec:   ld (REC),hl
        inc hl
        ld c,(hl)               ; flags
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (SPX),de
        inc hl
        ld a,(hl)
        ld (SPY),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the record's list
        inc hl
        ld a,(hl)
        ld (TYP),a
        bit 7,c
        jr nz,.pl
        ld b,0
        call group
        jr .nx
.pl:    xor a
        ld (TYP),a
        ld hl,(0xAF9C)
        call grp_ind
        ld de,(0xAF9E)
        ld a,(0xAFA4)
        ld b,a
        call group
        ld hl,(0xAF9A)
        call grp_ind
        ld de,(DRV)
        ld b,0
        call group
        ld hl,(0xAFA0)
        call grp_ind
.nx:    ld hl,(REC)
        ld de,-8
        add hl,de
        ld a,(NREC)
        dec a
        ld (NREC),a
        jr nz,.rec
.hide:  ld a,(GPREV)
        ld hl,GRP
        sub (hl)
        jr c,.hd
        jr z,.hd
        ld e,a                  ; groups to hide
        ld a,(hl)
        ld d,a
        add a,a
        add a,d                 ; first sprite
        ld bc,0x303B
        out (c),a
        ld a,e
        add a,a
        add a,e
        ld e,a                  ; sprites to hide
        ld c,0x57
.h1:    xor a
        out (c),a
        out (c),a
        out (c),a
        out (c),a               ; attr 3 = 0: invisible, 4-byte form
        dec e
        jr nz,.h1
.hd:    ld a,(GRP)
        ld (GPREV),a
        ld a,(SLOT6)
        nextreg 0x56,a
        ret

grp_ind:                        ; HL -> a word = the list; B = 0
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld b,0
; group: DE = list, B = rows down (the dome's AFA4), TYP. One image -> 3 patterns, 3 sprites.
group:  ld a,(GRP)
        cp MAXG
        ret nc
        ld hl,-0x9C00
        add hl,de
        ret nc
        ld a,h
        cp 0x14
        ret nc
        srl h
        rr l
        ld a,h
        add a,0xC0
        ld h,a
        nextreg 0x56,S0
        ld a,(hl)
        cp 255
        ret z
        cp 4
        jr nc,.img
        ld c,a
        ld a,(TYP)
        dec a
        cp 32
        ret nc
        add a,a
        add a,a
        add a,c
.img:   ld c,0
.d10:   cp 10
        jr c,.dd
        sub 10
        inc c
        jr .d10
.dd:    ld e,a
        add a,a
        add a,e
        add a,0xC0
        ld h,a
        ld l,0                  ; HL = 0xC000 + (n % 10) * 768
        ld a,c
        add a,S0 + 1
        nextreg 0x56,a
        ld a,(GRP)
        ld e,a
        add a,a
        add a,e
        ld e,a                  ; E = first pattern / sprite
        push bc
        ld bc,0x303B
        out (c),a
        ld bc,0x005B
        otir
        otir
        otir
        ld a,e
        ld bc,0x303B
        out (c),a
        pop bc                  ; B = rows down
        ; Y = y (signed: >= 200 is above the top) - 8 + B; X = x + 24
        ld a,(SPY)
        ld l,a
        ld h,0
        cp 200
        jr c,.y
        dec h
.y:     ld a,b
        sub 8
        ld c,a
        sbc a,a
        ld b,a
        add hl,bc               ; HL = Y of the top sprite (9 bits)
        push hl
        ld hl,(SPX)
        ld bc,24
        add hl,bc
        ex de,hl                ; DE = X, L... (E above saved in A below)
        pop hl
        ld b,3
        ld c,0x57
.k:     out (c),e               ; X low
        out (c),l               ; Y low
        ld a,d
        and 1
        out (c),a               ; X bit 8
        push hl
        ld hl,GRP
        ld a,(hl)
        add a,a
        add a,(hl)
        add a,3
        sub b                   ; pattern = 3 G + (3 - B)
        or 0xC0                 ; visible, attribute 4 follows
        out (c),a
        pop hl
        ld a,h
        and 1
        out (c),a               ; Y bit 8, 8-bit pattern
        push bc
        ld bc,16
        add hl,bc
        pop bc
        djnz .k
        ld hl,GRP
        inc (hl)
        ret

TCODE_END:
        ASSERT TCODE_END <= TCOL
        ORG TCOL
        DUP 32, n
        DW TAGS + n * TS
        EDUP
PAGE_END:
        SAVEBIN "quazatron_page.bin",0x4000,PAGE_END-0x4000

; ============================================================================================================
        ORG 0x386E

; CALL B07D at BE2E (a scenery list into the strip)
t_list: push hl
        call 0xB07D
        nextreg 0x52,HPAGE
        HLIB_R_IN
        ex (sp),hl
        push af
        push bc
        push de
        HLIB_SPEED_IN VSPD
        call p_tags
        ld a,-11 & 0x7F
        call hlib_r_set
        HLIB_SPEED_OUT VSPD
        pop de
        pop bc
        pop af
        pop hl
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; CALL C044 at BE82 (the strip cleared to ink)
t_clr:  call 0xC044
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call p_clr
        jr tw_exit

; CALL C1A5 at BFEC, BFFB (the strip pasted into the background)
t_paste:
        call 0xC1A5
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call p_paste
tw_exit:
        ld a,-10 & 0x7F
        call hlib_r_set
        HLIB_SPEED_OUT VSPD
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; CALL E656 at E0DF (the blocks blitted to the screen): the sprites follow
t_spr:  call 0xE656
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call p_spr
        jp tw_exit

; JP at C05A (background to screen, then the attributes). The commit runs after the game's copy, so the shown canvas
; changes once, complete (during the copy the original shows its new bitmap under the old attributes; we keep showing
; the last complete picture; at the first view Layer 2 is still off and the ULA shows exactly the original). Two
; brackets, so that R is the original's exactly while the game's own copy runs (the ISR reads R); the first does no
; work: (1) O = 1 (LD DE) to the copy's entry, E = 1 + 2 + 3, N = 1 + 2 + 1
; (LD DE) + 1 (CALL): delta 1 - 6 - 5 = -10; (2) from the copy's RET: E = 2 + 3, N = 1 + 2 + 1 (RET): delta -9.
t_c05a: nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld a,-10 & 0x7F
        call hlib_r_set
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld de,0x8300
        call 0xC05D
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call p_inks             ; the new inks, then the origin and Layer 2 on: the picture changes once, complete
        call p_pre
        ld a,-9 & 0x7F
        call hlib_r_set
        HLIB_SPEED_OUT VSPD
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; the scroll moves: the game's own move runs; the canvas origin follows (content down 8 = view up: OY - 8, ...).
; Each: O = 1 (LD HL,nn), E = 1 (JP) + 2 (NEXTREG) + 3, N = 1 + 2 + 1 (LD HL) + 1 (JP): delta = -10.
t_sd:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld a,(OY)
        sub 8
        call s_y
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x94FF
        jp 0xE111
t_su:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld a,(OY)
        add a,8
        call s_y
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x8400
        jp 0xE120
t_sl:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push de
        ld de,16
        call s_x
        pop de
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x8302
        jp 0xE12F
t_sr:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push de
        ld de,320-16
        call s_x
        pop de
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x95FD
        jp 0xE149
s_y:    ld (OY),a
        ld a,-10 & 0x7F
        jp hlib_r_set
s_x:    ld hl,(OX)
        add hl,de
        call mod320
        ld (OX),hl
        ld a,-10 & 0x7F
        jp hlib_r_set

; JP at B2C9 (screen clear): Layer 2 off. O = 1, E = 6, N = 5: delta -10.
t_cls:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        call p_off
        ld a,-10 & 0x7F
        call hlib_r_set
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x4000
        jp 0xB2CC

; JP at B1FB (the printer, LD (B263),DE): Layer 2 off when DE is in the play area (rows 0-151).
; O = 2 (ED 53), E = 6, N = 1 + 2 + 2 + 1: delta -10.
t_prn:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        ld a,d
        cp 0x50
        jr c,.off
        cp 0x58
        jr nc,.no
        ld a,e
        cp 0x60
        jr nc,.no
.off:   call p_off
.no:    ld a,-10 & 0x7F
        call hlib_r_set
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld (0xB263),de
        jp 0xB1FF
ROM_END:
        SAVEBIN "quazatron_rom.bin",0x386E,ROM_END-0x386E

; ============================================================================================================
; setup: called by the stub (DI, 3.5 MHz, slot 2 = the screen page) before the tail. Layer 2 320 x 256 on banks
; L2BANK.., its palette (PALINIT in the hook page), the canvas cleared, the clip = the 256 x 152 play area,
; layers S L U, sprites off for now, Layer 2 off until the first commit.
        ORG 0xD000
setup:  nextreg 0x07,3
        nextreg 0x52,HPAGE
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,PALINIT
        ld b,64
.p:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .p
        ld a,L2PAGE
.cl:    nextreg 0x52,a
        ld hl,0x4000
        ld de,0x4001
        ld bc,0x1FFF
        ld (hl),0
        ldir
        inc a
        cp L2PAGE + 10
        jr c,.cl
        nextreg 0x52,ULAPAGE
        nextreg 0x70,0x10
        nextreg 0x12,L2BANK
        nextreg 0x1C,1
        nextreg 0x18,16
        nextreg 0x18,143
        nextreg 0x18,32
        nextreg 0x18,183
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x15,0
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,151
        nextreg 0x07,0
        ret
SETUP_END:
        SAVEBIN "quazatron_setup.bin",0xD000,SETUP_END-0xD000
