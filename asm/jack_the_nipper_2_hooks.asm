; Jack the Nipper II - In Coconut Capers (Gremlin Graphics 1987, 48K) - figures as hardware sprites. Facts and design:
; games/jack_the_nipper_2.md. Per object, 0xBAF9 gives each cell the figure covers a slot in a cell buffer at 0xE900
; (counter 0xBDF1; the dirty map 0xFB00-0xFD7F points at it) and copies the cell's background tile into it; one of 16
; blit paths then masks the figure into those slots through IY (AND mask, OR graphics); the copier 0xBC62 writes each
; dirty cell to the screen, its attribute from the slot's colour list 0xBD68 (the object's colour: the clash).
; The blit code itself is NOT replaced: at each blit's LD (0xBDE8),SP (HL = the graphics, IY = the buffer) the hook
; records the figure and moves IY from 0xE900-0xECFF to 0x2900-0x2CFF (high byte AND 0x3F), so the blit lands in a
; scratch buffer in this page and the cell buffer keeps the background. At the copier's entry the commit puts back
; the scenery's attribute into each slot's colour list entry (the tile colour table 0xED00, as the copier's
; background path), then turns the figures into 4-bit sprites in the object's own ink and paper (pixel = colour + 1;
; palette bank 0 normal, bank 1 bright), uploads tiles not cached, writes the attributes, hides the rest.
; Memory: this file is Next page JTN_PAGE at MMU slot 1 (0x2000-0x3FFF) for the whole game (the game never reads the
; ROM there): 0x2000-0x28FF state, 0x2900-0x2D4F scratch buffer, 0x3000- code, 0x3E00 the tail restore, 0x3F00 the
; stub's register block.

        DEVICE ZXSPECTRUMNEXT

COPY_BACK EQU 0xBC65        ; the copier after LD HL,0xFD80
X_DRAWN   EQU 0xB2D5        ; the draw's x (0xB2B3 stores it as an operand)
DIRTY     EQU 0xFB00        ; dirty map: 640 cells (32 x 20), a slot number from 3, 1 / 2 = other states
TILEMAP   EQU 0xF800        ; tile per cell
TILEATTR  EQU 0xED00        ; colour per tile
SLOTCOL   EQU 0xBD68        ; colour per slot
MAXFIG    EQU 24
FIGSZ     EQU 10            ; +0 gfx, +2 colour, +3 -, +4 rows, +5 width bytes, +6 x, +7 top, +8 mirror, +9 bank
SPR0      EQU 0
PROBE     EQU 8

FIGS      EQU 0x2000
HLIB_PCACHE EQU 0x2100
SLOTUSE   EQU 0x2180
V_NFIG    EQU 0x21C0
V_SHOWN   EQU 0x21C1
V_UPD     EQU 0x21C2
V_LATCH   EQU 0x21C3
V_HSP     EQU 0x21C4
V_NSPR    EQU 0x21C6
C_FIG     EQU 0x21D2
C_COLS    EQU 0x21D4
C_TROWS   EQU 0x21D5
C_TR      EQU 0x21D6
C_TC      EQU 0x21D7
C_SLOT    EQU 0x21D8
C_PAIR    EQU 0x21D9
C_ATP     EQU 0x21DA
B_ROW     EQU 0x21DC
B_T       EQU 0x21DD
T_TC      EQU 0x21DE
T_N       EQU 0x21DF
T_COL     EQU 0x21E0
T_G       EQU 0x21E1
C_T       EQU 0x21E3
V_HASH    EQU 0x21E4
V_LATCHD  EQU 0x21E5
V_HL      EQU 0x21E8        ; a blit stub's HL (2)
T_PX      EQU 0x21EA        ; tile: the image column of the next pixel
F_CX0     EQU 0x21EB        ; fcolour: the cells a figure covers
F_CX1     EQU 0x21EC
F_CY0     EQU 0x21ED
F_CY1     EQU 0x21EE
F_COL     EQU 0x21EF
T_INK     EQU 0x21E6        ; tile: the ink and paper pixel values (colour + 1)
T_PAP     EQU 0x21E7
TILEBUF   EQU 0x2200
HSTACK    EQU 0x2400
ATTRTAB   EQU 0x2400

        INCLUDE "lib/hlib_speed.asm"     ; macros only

        ORG 0x3000
code_start:
; e_b0 .. e_b15: JP here from each blit's LD (0xBDE8),SP (HL = the graphics, IY = the buffer, IX = the object). The
; stub keeps HL and hands its way back to blit; every register and flag is kept but IY, moved to the scratch buffer.
e_b0:    ld (V_HL),hl
        ld hl,0xB34F
        jp blit
e_b1:    ld (V_HL),hl
        ld hl,0xB39F
        jp blit
e_b2:    ld (V_HL),hl
        ld hl,0xB401
        jp blit
e_b3:    ld (V_HL),hl
        ld hl,0xB475
        jp blit
e_b4:    ld (V_HL),hl
        ld hl,0xB57D
        jp blit
e_b5:    ld (V_HL),hl
        ld hl,0xB5C5
        jp blit
e_b6:    ld (V_HL),hl
        ld hl,0xB61C
        jp blit
e_b7:    ld (V_HL),hl
        ld hl,0xB67D
        jp blit
e_b8:    ld (V_HL),hl
        ld hl,0xB72B
        jp blit
e_b9:    ld (V_HL),hl
        ld hl,0xB763
        jp blit
e_b10:   ld (V_HL),hl
        ld hl,0xB79D
        jp blit
e_b11:   ld (V_HL),hl
        ld hl,0xB81A
        jp blit
e_b12:   ld (V_HL),hl
        ld hl,0xB907
        jp blit
e_b13:   ld (V_HL),hl
        ld hl,0xB935
        jp blit
e_b14:   ld (V_HL),hl
        ld hl,0xB964
        jp blit
e_b15:   ld (V_HL),hl
        ld hl,0xB9B7
        jp blit

blit:   ld (j_back+1),hl        ; where this blit goes on (the page is RAM)
        ld hl,(V_HL)
        ld (V_HSP),sp
        ld sp,HSTACK
        HLIB_SPEED_IN V_LATCHD
        push af
        push bc
        push de
        push hl
        call record
        push iy
        pop hl
        ld a,h
.n_red: and 0x3F                ; 0xE9-0xEC -> 0x29-0x2C (negative control: AND 0xFF = no redirect)
        ld h,a
        push hl
        pop iy
        pop hl
        pop de
        pop bc
        pop af
        HLIB_SPEED_OUT V_LATCHD
        ld sp,(V_HSP)
        ld (0xBDE8),sp          ; the instruction the site replaced
j_back: jp 0x0000

; record: HL = the graphics (rows top first: the mask bytes, then the graphics bytes), IX = the object. Adds an entry.
record: ld a,(V_NFIG)
        cp MAXFIG
        ret nc
        ld c,a
        inc a
        ld (V_NFIG),a
        push hl
        ld l,c
        ld h,0
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de               ; 10n
        ld de,FIGS
        add hl,de
        ex de,hl                ; DE = the entry
        pop hl
        ld a,l
        ld (de),a               ; +0 graphics
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,(ix+9)
        ld (de),a               ; +2 the object's colour (ink, paper, bright)
        inc de
        inc de
        ld bc,0x0210            ; width 2, rows 16: (IX+2) bit 0
        ld a,(ix+2)
        rrca
        jr c,.dim
        ld c,24                 ; bit 1: 16 x 24
        rrca
        jr c,.dim
        ld bc,0x0318            ; bit 2: 24 x 24
        rrca
        jr c,.dim
        ld c,32                 ; bit 3: 24 x 32
        rrca
        jr c,.dim
        ld bc,0x0218            ; bit 4: 16 x 24
        rrca
        jr c,.dim
        ld bc,0x0320            ; none: 24 x 32 (the dispatch at 0xB2E9)
.dim:   ld a,c
        ld (de),a               ; +4 rows
        inc de
        ld a,b
        ld (de),a               ; +5 width bytes
        inc de
        ld a,(X_DRAWN)
        ld (de),a               ; +6 x
        inc de
        ld a,(ix+1)
        ld (de),a               ; +7 top
        inc de
        xor a
        bit 1,(ix+5)
        jr z,.nm
        inc a                   ; (IX+5) bit 1: the mirrored blit (0xB703 ...)
.nm:    ld (de),a               ; +8 mirror
        inc de
        ld a,(ix+9)
        rlca
        rlca
        and 1                   ; bright -> palette bank 1
        ld (de),a               ; +9 bank
        ret

; e_cmt: JP here from the copier's entry 0xBC62. Every register and flag is kept; then LD HL,0xFD80 and the copier.
e_cmt:  ld (V_HSP),sp
        ld sp,HSTACK
        push af
        push bc
        push de
        push hl
        push ix
        HLIB_SPEED_IN V_LATCH
        call commit
.n_spd: HLIB_SPEED_OUT V_LATCH  ; (negative control: its NEXTREG 7 NOPped = the caller's speed not given back)
.n_spd_end:
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_HSP)
        ld hl,0xFD80
        jp COPY_BACK

; cells: every dirty cell holding a slot (3 and up) gets the scenery's colour in that slot's colour list entry:
; TILEATTR[TILEMAP[cell]], as the copier's background path (0xBD4B) colours a cell with no figure.
cells:  ld hl,DIRTY
        ld de,TILEMAP
        ld bc,640
.c:     ld a,(hl)
        cp 3
        jr c,.n
        push hl
        push bc
        ld c,a                  ; the slot
        ld a,(de)               ; the cell's tile
        ld l,a
        ld h,high TILEATTR
        ld a,(hl)               ; its colour
.n_col: ld hl,SLOTCOL           ; (negative control: a colour list not put back)
        ld b,0
        add hl,bc
        ld (hl),a
        pop bc
        pop hl
.n:     inc hl
        inc de
        dec bc
        ld a,b
        or c
        jr nz,.c
        ret

; commit: pass 1 uploads the tiles not cached and fills ATTRTAB; pass 2 writes the attributes and hides the rest.
commit: ld a,(V_UPD)
        inc a
        jr nz,.u
        inc a                   ; 1-255: SLOTUSE 0 never matches
.u:     ld (V_UPD),a
        xor a
        ld (V_NSPR),a
        ld hl,ATTRTAB
        ld (C_ATP),hl
        ld ix,FIGS
        ld a,(V_NFIG)
        or a
        jr z,.p2
        ld b,a
.f:     push bc
        call figure
        ld de,FIGSZ
        add ix,de
        pop bc
        djnz .f
.p2:    call cells              ; then the cells keep the scenery's colours
        xor a
        ld (V_NFIG),a
        ld bc,0x303B
        ld a,SPR0
        out (c),a               ; the attribute index (pattern uploads moved it)
        ld hl,ATTRTAB
        ld a,(V_NSPR)
        ld d,a                  ; D = sprites now
        or a
        jr z,.hide
        ld e,a
        ld bc,0x0057
.w:     ld b,5
        otir                    ; attributes 0-4 of one sprite
        dec e
        jr nz,.w
.hide:
.n_hide: ld a,(V_SHOWN)          ; (negative control: LD A,D here = nothing hidden)
        sub d
        jr c,.done
        jr z,.done
        ld e,a                  ; sprites shown last time and not now: attribute 3 = 0 (4 bytes, no attribute 4)
        ld bc,0x0057
        xor a
.h:     out (c),a
        out (c),a
        out (c),a
        out (c),a
        dec e
        jr nz,.h
.done:  ld a,d
        ld (V_SHOWN),a
        ret

; figure: IX = an entry. Its tiles: columns 1 (16 wide) or 2 (24), rows of 16 from the top: 1, 2, 2 or 3.
figure: call fcolour
        ld a,(ix+5)
        sub 1                   ; 2 -> 1 column, 3 -> 2
        ld (C_COLS),a
        ld a,(ix+4)
        add a,15
        rrca
        rrca
        rrca
        rrca
        and 15                  ; ceil(rows / 16)
        ld (C_TROWS),a
        ld a,0xFF
        ld (C_PAIR),a
        xor a
        ld (C_TR),a
.tr:    xor a
        ld (C_TC),a
.tc:    ld a,(C_TR)             ; tile index t = tr x cols + tc
        ld b,a
        ld a,(C_COLS)
        ld c,a
        xor a
.m:     dec b
        jp m,.md
        add a,c
        jr .m
.md:    ld b,a
        ld a,(C_TC)
        add a,b
        ld (C_T),a
        srl a                   ; the pair this tile is in
        ld b,a
        ld a,(C_PAIR)
        cp b
        jr z,.have
        ld a,b
        ld (C_PAIR),a
        call slot               ; C_SLOT = a slot holding this pair, uploaded if need be
.have:  call attrs              ; this tile's sprite into ATTRTAB
        ld a,(C_TC)
        inc a
        ld (C_TC),a
        ld b,a
        ld a,(C_COLS)
        cp b
        jr nz,.tc
        ld a,(C_TR)
        inc a
        ld (C_TR),a
        ld b,a
        ld a,(C_TROWS)
        cp b
        jr nz,.tr
        ret

; slot: the pair C_PAIR of the figure at IX -> C_SLOT, the image uploaded when that slot did not hold it.
; Key = graphics address + pair, plus the colours << 11 (never 0; the game never rewrites its graphics).
slot:   ld e,(ix+0)
        ld d,(ix+1)
        ld a,(C_PAIR)
        add a,e
        ld e,a
        adc a,d
        sub e
        ld d,a                  ; graphics address + pair
        ld a,(ix+3)             ; a figure in several colours (an item's own table, 0xBA8A): built every time
        or a
        jr nz,.uni
        ld de,0                 ; key 0 = mutable: always uploaded
        jr .k
.uni:   ld a,(ix+2)             ; one colour: + the colour baked in: the key names the image AND its colour
        add a,a
        add a,a
        add a,a
        add a,d
        ld d,a                  ; DE = key
        or e
        jr nz,.k
        inc e                   ; 0 is the mutable key
.k:     ld a,d
        or e
        jr z,.mut               ; mutable: any slot not serving this update
        ld a,e
        xor d
        and 63
        ld (V_HASH),a
        ld b,PROBE              ; a slot already holding the key?
.p:     ld l,a
        ld h,high HLIB_PCACHE
        ld c,a
        ld a,(hl)
        cp e
        jr nz,.n
        set 6,l
        ld a,(hl)
        cp d
        jr nz,.n
        ld a,c                  ; hit: no upload
        jr .use
.n:     ld a,c
        inc a
        and 63
        djnz .p
        ld a,(V_HASH)           ; a slot not serving this update
        jr .q0
.mut:   ld a,(ix+0)
        and 63
        ld (V_HASH),a
.q0:    ld b,64
.q:     ld c,a
        add a,low SLOTUSE
        ld l,a
        ld h,high SLOTUSE
        ld a,(V_UPD)
        cp (hl)
        jr nz,.free
        ld a,c
        inc a
        and 63
        djnz .q
        ld a,c                  ; all 64 serve this update (more figures than pattern memory): reuse the last
.free:  ld a,c
        push af
        push de
        call build              ; TILEBUF = the pair's two tiles
        pop de
        pop af
        push af
        ld hl,TILEBUF
        call hlib_pc_upload     ; A = slot, DE = key, HL = source
        pop af
.use:   ld (C_SLOT),a
        add a,low SLOTUSE
        ld l,a
        ld h,high SLOTUSE
        ld a,(V_UPD)
        ld (hl),a
        ret

; build: TILEBUF = tiles 2 x C_PAIR and 2 x C_PAIR + 1 of the figure at IX, 128 bytes each (16 rows of 8 bytes, the
; left pixel in the high nibble): ink + 1 where the graphics bit is set, else paper + 1 where the mask bit is clear,
; else 0 (the palette bank gives the bright ones).
build:  ld a,(ix+2)             ; one colour: its two pixel values once (cls looks up each pixel's cell otherwise)
        call codes
        ld hl,TILEBUF
        ld a,(C_PAIR)
        add a,a
        ld (B_T),a
        call tile
        ld a,(B_T)
        inc a
        ld (B_T),a
tile:   ld a,(C_COLS)
        ld c,a
        ld a,(B_T)
        ld b,0
.dv:    cp c
        jr c,.dd
        sub c
        inc b
        jr .dv
.dd:    ld (T_TC),a
        add a,a
        ld (T_COL),a
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,a
        ld (B_ROW),a
        ld a,16
        ld (T_N),a
.row:   ld a,(B_ROW)            ; figure row from the top = memory row (top first)
        cp (ix+4)
        jr nc,.clr              ; below the figure
        ld e,a
        ld d,0
        ld b,(ix+5)
        sla b                   ; 2 x width bytes a row (masks, then graphics)
        push hl
        ld hl,0
.mw:    add hl,de
        djnz .mw
        ld a,(T_COL)
        ld e,a
        add hl,de               ; + the first byte column
        ex de,hl
        ld l,(ix+0)
        ld h,(ix+1)
        add hl,de
        ld b,h
        ld c,l                  ; BC = the mask byte
        ld e,(ix+5)
        ld d,0
        add hl,de
        ex de,hl                ; DE = the graphics byte (a width further on)
        pop hl
        ld a,(T_COL)
        call byte2
        inc de
        inc bc
        ld a,(T_COL)
        inc a
        call byte2
        jr .nx
.clr:   xor a
        ld b,8
.cl:    ld (hl),a
        inc hl
        djnz .cl
.nx:    ld a,(B_ROW)
        inc a
        ld (B_ROW),a
        ld a,(T_N)
        dec a
        ld (T_N),a
        jr nz,.row
        ret

byte2:  push de
        push bc
        cp (ix+5)
        jr nc,.out
        push af
        add a,a
        add a,a
        add a,a
        ld (T_PX),a             ; the byte's first image column
        pop af
        ld a,(de)
        ld d,a                  ; D = graphics
        ld a,(bc)
        ld e,a                  ; E = mask
        ld b,4
.px:    call cls
        rlca
        rlca
        rlca
        rlca
        ld c,a
        call cls
        or c
        ld (hl),a
        inc hl
        djnz .px
        pop bc
        pop de
        ret
.out:   xor a
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        pop bc
        pop de
        ret

cls:    ld a,(ix+3)
        or a
        call z,pixcol           ; several colours: this pixel's cell
        ld a,(T_PX)
        inc a
        ld (T_PX),a
        sla d
        jr c,.ink
        sla e
        ld a,0
        ret c
        ld a,(T_PAP)
        ret
.ink:   sla e
        ld a,(T_INK)
        ret

; codes: A = an attribute -> T_INK, T_PAP = its ink and paper as pixel values (1-8 normal, 9-15 bright, bright black 1).
codes:  push bc
        ld b,a
        and 7
        call code
        ld (T_INK),a
        ld a,b
        rrca
        rrca
        rrca
        and 7
        call code
        ld (T_PAP),a
        pop bc
        ret
code:   bit 6,b
        jr z,.n
        or a
        jr z,.n                 ; bright black = black
        add a,8
        ret
.n:     inc a
        ret

; pixcol: the colour of the cell the next pixel (image column T_PX, figure row B_ROW) shows on, from the game's own
; colour list (read before cells puts the scenery's back) -> T_INK, T_PAP. Keeps BC, DE, HL.
pixcol: push hl
        push de
        push bc
        ld a,(ix+5)             ; screen column: x + c, or x + width x 8 - 1 - c mirrored
        add a,a
        add a,a
        add a,a
        dec a
        ld c,a                  ; width x 8 - 1
        ld a,(T_PX)
        bit 0,(ix+8)
        jr z,.nm
        neg
        add a,c                 ; w8 - 1 - c
.nm:    ld l,a
        ld h,0
        ld e,(ix+6)
        ld d,0
        add hl,de               ; 9-bit screen column
        srl h
        rr l
        srl l
        srl l                   ; cell column (0-34)
        ld a,l
        cp 32
        jr nc,.none
        ld e,a
        ld a,(B_ROW)
        add a,(ix+7)            ; screen row
        rrca
        rrca
        rrca
        and 31                  ; cell row
        cp 20
        jr nc,.none
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; row x 32
        ld d,0
        add hl,de
        ld de,DIRTY
        add hl,de
        ld a,(hl)               ; the cell's slot
        cp 3
        jr c,.none
        ld e,a
        ld d,0
        ld hl,SLOTCOL
        add hl,de
        ld a,(hl)
        call codes
.none:  pop bc
        pop de
        pop hl
        ret

; fcolour: the figure at IX -> (IX+3) = 1 when every cell it covers holds one colour in the game's colour list (then
; (IX+2) = it), else 0 (an item with a colour per cell). Cells: columns x >> 3 .. (x + width x 8 - 1) >> 3, rows
; top >> 3 .. (top + rows - 1) >> 3, inside the 32 x 20 map.
fcolour:
        ld a,(ix+6)
        rrca
        rrca
        rrca
        and 31
        ld (F_CX0),a
        ld a,(ix+5)
        add a,a
        add a,a
        add a,a
        dec a
        ld l,a
        ld h,0
        ld e,(ix+6)
        ld d,0
        add hl,de
        srl h
        rr l
        srl l
        srl l
        ld a,l
        cp 32
        jr c,.c1
        ld a,31
.c1:    ld (F_CX1),a
        ld a,(ix+7)
        rrca
        rrca
        rrca
        and 31
        ld (F_CY0),a
        ld a,(ix+7)
        add a,(ix+4)
        dec a
        rrca
        rrca
        rrca
        and 31
        cp 20
        jr c,.r1
        ld a,19
.r1:    ld (F_CY1),a
        ld a,0xFF
        ld (F_COL),a
        ld (ix+3),1
        ld a,(F_CY0)
.row:   ld b,a                  ; B = cell row
        ld a,(F_CX0)
.col:   ld c,a                  ; C = cell column
        push bc
        ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld e,c
        ld d,0
        add hl,de
        ld de,DIRTY
        add hl,de
        ld a,(hl)
        cp 3
        jr c,.skip              ; no slot here
        ld e,a
        ld d,0
        ld hl,SLOTCOL
        add hl,de
        ld a,(hl)
        ld e,a
        ld a,(F_COL)
        cp 0xFF
        jr nz,.cmp
        ld a,e
        ld (F_COL),a
        jr .skip
.cmp:   cp e
        jr z,.skip
        ld (ix+3),0             ; a second colour
.skip:  pop bc
        ld a,(F_CX1)
        cp c
        jr z,.nr                ; the row's last column done
        ld a,c
        inc a
        jr .col
.nr:    ld a,(F_CY1)
        cp b
        jr z,.done              ; the last row done
        ld a,b
        inc a
        jr .row
.done:  ld a,(F_COL)
        cp 0xFF
        jr nz,.st
        ld a,(ix+2)             ; no slot found (should not happen): the object's colour
.st:    ld (ix+2),a
        ret

; attrs: the tile (C_TR, C_TC) of the figure at IX in C_SLOT -> 5 bytes at C_ATP. X = x + 32 + 16 x column (mirrored:
; the columns run right to left, and a 24-wide figure's box starts 8 pixels left), Y = top + 32 + 16 x row; attribute 2 = bank << 4 | mirror << 3 | X bit 8;
; attribute 3 = visible, attribute 4 on, pattern slot; attribute 4 = 4-bit, N6 = the tile's half, Y bit 8.
attrs:  ld hl,(C_ATP)
        ld a,(C_TC)
        ld b,a
        ld a,(ix+8)
        or a
        jr z,.nm
        ld a,(C_COLS)
        dec a
        sub b
        ld b,a                  ; mirrored: column = cols - 1 - tc
.nm:    ld a,b
        add a,a
        add a,a
        add a,a
        add a,a                 ; 16 x column
        ld e,a
        ld d,0
        ld a,(ix+6)
        add a,e
        ld e,a
        adc a,d
        sub e
        ld d,a                  ; DE = x + 16 x column
        ex de,hl
        ld bc,32
        add hl,bc               ; + 32
        ld a,(ix+8)
        or a
        jr z,.nx8
        ld a,(ix+5)
        cp 3
        jr nz,.nx8
        ld bc,-8                ; a mirrored 24-wide figure: its 32-pixel box's 8 empty columns are on the left now
        add hl,bc
.nx8:   ex de,hl
        ld (hl),e               ; attribute 0
        inc hl
        ld a,(C_TR)
        add a,a
        add a,a
        add a,a
        add a,a
        add a,(ix+7)            ; top + 16 x row (mod 256)
        add a,32
        ld (hl),a               ; attribute 1 (rows above the screen wrap far below it: off screen)
        inc hl
.n_bank: ld a,0                   ; one bank holds normal and bright (negative control: LD A,1 = the wrong bank)
        nop
        add a,a
        add a,a
        add a,a
        add a,a                 ; bank << 4
        bit 0,(ix+8)
        jr z,.n2
.n_mir:  or 8                    ; X mirror (negative control: OR 0 = never mirrored)
.n2:    or d                    ; X bit 8
        ld (hl),a               ; attribute 2
        inc hl
        ld a,(C_SLOT)
        or 0xC0                 ; visible, attribute 4 follows
        ld (hl),a               ; attribute 3
        inc hl
        ld a,(C_T)
        and 1
        rrca
        rrca                    ; N6 = the tile's half (bit 6)
        or 0x80                 ; 4-bit pattern
        ld (hl),a               ; attribute 4
        inc hl
        ld (C_ATP),hl
        ld a,(V_NSPR)
        inc a
        ld (V_NSPR),a
        ret

        DEFINE HLIB_CPU_ONLY
        INCLUDE "lib/hlib_pcache.asm"

code_end:
        ASSERT code_end <= 0x3E00

        SAVEBIN "jtn2_page.bin", code_start, code_end - code_start

; ---- the stub's set-up (stub_extra at 0xD000, CALLed once before the game starts) ----
        ORG 0xD000
setup_start:
; setup: bank 0 = 0 clear, 1-8 the Spectrum's normal colours (black .. white), 9-15 the bright ones; sprite 127 on
; top (later objects over earlier, as the game draws); sprites visible.
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,setpal
        ld b,16
.p:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .p
        nextreg 0x4B,0
        nextreg 0x15,0x41
        ret
setpal: db 0x00, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6        ; 0 clear, 1-8 normal black .. white
        db 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF                    ; 9-15 bright blue .. white
setup_end:
        SAVEBIN "jtn2_setup.bin", setup_start, setup_end - setup_start
