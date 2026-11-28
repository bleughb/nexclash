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
FCELL     EQU 0x2D50        ; each figure's cell colours as the game held them at its blit (20 a figure: 5 rows x 4 columns)
V_CAP     EQU 0x21F6        ; capture: the figure's FCELL block (2)
V_OVR     EQU 0x21F8        ; Enhanced: 1 = the painted colours are on (the build sets it)
REMAP     EQU 0x2780        ; a pixel value (bank 0's Spectrum colour) -> the one the sprite shows: identity, or Enhanced's
                            ; nearest colour in the painting palette (bank 1); 16-aligned (16)
OVR_BASE  EQU 0x8E00        ; the painted colours: 4 bytes (8 nibbles, pixel 0 first; 0 = the default) per graphics
OVR_SPAN  EQU 0x6000        ; byte from OVR_BASE, OVR_SPAN bytes, in Next pages OVR_PAGE0.. (2048 bytes of game a page),
OVR_PAGE0 EQU 40            ; mapped at slot 0 only inside ovr (the game takes no interrupt: none in the recordings)
MAXFIG    EQU 24
FIGSZ     EQU 10            ; +0 gfx, +2 colour, +3 -, +4 rows, +5 width bytes, +6 x, +7 top, +8 mirror, +9 bank
SPR0      EQU 0
PROBE     EQU 8
MUT0      EQU 48            ; slots 48-63 for figures in several colours (cached by signature, else rebuilt)

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
PTAB      EQU 0x2680        ; build: a one-colour figure's 16 pixel pairs (16-aligned, after ATTRTAB)
T_LEFT    EQU 0x21F0        ; cls: pixels left in the current cell (0: look the next one up)
C_NREST   EQU 0x21F3        ; cells: distinct slots given back this update
C_NTGT    EQU 0x21F4        ; cells: the slots the game gave out (counter - 3)
SEEN      EQU 0x2700        ; cells: the update each slot was given back in (128)
SLOTCTR   EQU 0xBDF1        ; the game's next free slot (from 3 each update)
F_SP      EQU 0x21F1        ; fcolour: the next signature byte (2)
SIGT      EQU 0x2690        ; fcolour: a figure's colour signature (11: alignment, up to 9 cell colours, box size)
SLOTCLR   EQU 0x26C0        ; the colour each one-colour slot was built in (64)
MSIG      EQU 0x2800        ; the signature each mutable slot was built for (16 x 11)
T_INK     EQU 0x21E6        ; tile: the ink and paper pixel values (colour + 1)
T_PAP     EQU 0x21E7
TILEBUF   EQU 0x2200
HSTACK    EQU 0x2400
ATTRTAB   EQU 0x2400
NSPRMAX   EQU 128           ; sprites ATTRTAB holds (640 bytes, then PTAB)

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
                                ; on into capture (DE = the entry + 9)

; capture: the figure just recorded (DE = its entry + 9) -> the colours of the cells it covers, from the game's colour
; list as it is now, at this figure's own blit (0xBAF9 / 0xBA8A wrote them just before it): FCELL + 2 x (entry - FIGS),
; 5 rows x 4 columns from the box's top left cell; 0xFF no slot; all 0xFE when the box is off the map (fbox), and the
; lookups (fcell) then read the list at the copy. A later figure that shares a cell gives the list its colour, so
; reading the list at the copy (as the first build did) gave both figures the later one's: the clash between figures.
capture:
        push ix
        ld hl,-9
        add hl,de
        push hl
        pop ix                  ; IX = the entry
        ld de,-FIGS
        add hl,de
        add hl,hl
        ld de,FCELL
        add hl,de
        ld (V_CAP),hl
        call fbox
        ld a,0xFF
        jr nc,.fill
        ld a,0xFE               ; off the map
.fill:  ld hl,(V_CAP)
        ld b,20
.f:     ld (hl),a
        inc hl
        djnz .f
        cp 0xFE
        jr z,.done
        ld a,(F_CY0)
.row:   ld b,a                  ; B = cell row
        ld a,(F_CX0)
.col:   ld c,a                  ; C = cell column
        ld hl,F_CY0
        ld a,b
        sub (hl)
        cp 5
        jr nc,.next
        add a,a
        add a,a
        ld e,a
        ld hl,F_CX0
        ld a,c
        sub (hl)
        cp 4
        jr nc,.next
        add a,e
        ld e,a
        ld d,0
        push de                 ; the cell's index in the block
        ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld e,c
        add hl,de
        ld de,DIRTY
        add hl,de
        ld a,(hl)               ; the cell's slot
        pop de
        cp 3
        jr c,.next              ; no slot: 0xFF stays
        push de
        ld e,a
        ld d,0
        ld hl,SLOTCOL
        add hl,de
        ld a,(hl)
        pop de
        ld hl,(V_CAP)
        add hl,de
.n_cap: ld (hl),a               ; (negative control: NOP = nothing captured, every cell 'no slot')
.next:  ld a,(F_CX1)
        cp c
        jr z,.nr
        ld a,c
        inc a
        jr .col
.nr:    ld a,(F_CY1)
        cp b
        jr z,.done
        ld a,b
        inc a
        jr .row
.done:  pop ix
        ret

; fcell: A = cell row, E = cell column, IX = a figure -> A = that cell's colour as the game held it at the figure's blit
; (capture), 0xFF no slot. A cell outside the captured block, or a figure captured off the map: the list at the copy.
; Keeps BC, DE, HL.
fcell:  push hl
        push de
        push bc
        ld c,a                  ; C = row
        ld b,e                  ; B = column
        ld a,(ix+7)
        rrca
        rrca
        rrca
        and 31
        ld d,a
        ld a,c
        sub d
        jr c,.live
        cp 5
        jr nc,.live
        add a,a
        add a,a
        ld l,a
        ld a,(ix+6)
        rrca
        rrca
        rrca
        and 31
        ld d,a
        ld a,b
        sub d
        jr c,.live
        cp 4
        jr nc,.live
        add a,l
        ld e,a
        ld d,0
        push ix
        pop hl
        push de
        ld de,-FIGS
        add hl,de
        add hl,hl
        ld de,FCELL
        add hl,de
        pop de
        add hl,de
        ld a,(hl)
        cp 0xFE
        jr nz,.out
.live:  ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld e,b
        ld d,0
        add hl,de
        ld de,DIRTY
        add hl,de
        ld a,(hl)
        cp 3
        jr c,.none
        ld e,a
        ld d,0
        ld hl,SLOTCOL
        add hl,de
        ld a,(hl)
        jr .out
.none:  ld a,0xFF
.out:   pop bc
        pop de
        pop hl
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

; cells: every cell holding a slot (3 and up) gets the scenery's colour in that slot's colour list entry:
; TILEATTR[TILEMAP[cell]], as the copier's background path (0xBD4B) colours a cell with no figure. First the recorded
; figures' boxes; the slots are distinct and below the game's counter, so when those give back counter - 3 slots there
; is no other; else (an object drawn another way, as a rope) every cell of the map.
cells:  xor a
        ld (C_NREST),a
        ld a,(V_NFIG)
        or a
        jr z,.chk
        ld b,a
        ld ix,FIGS
.f:     push bc
        call fbox
        jr c,.nf                ; nothing of it on the map
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
        add hl,de               ; the cell's index
        ld de,DIRTY
        add hl,de
        ld a,(hl)
        cp 3
        call nc,rest
        pop bc
        ld a,(F_CX1)
        cp c
        jr z,.nr
        ld a,c
        inc a
        jr .col
.nr:    ld a,(F_CY1)
        cp b
        jr z,.nf
        ld a,b
        inc a
        jr .row
.nf:    pop bc
        ld de,FIGSZ
        add ix,de
        djnz .f
.chk:   ld a,(SLOTCTR)
        sub 3
        ret c
        ld (C_NTGT),a
        ld b,a
        ld a,(C_NREST)
        cp b
        ret nc                  ; every slot given back
        ld hl,DIRTY             ; a slot outside the figures: the map, until every slot is given back
        ld bc,640
.c:     ld a,(hl)
        cp 3
        jr c,.cn
        call rest
        ld a,(C_NTGT)
        ld e,a
        ld a,(C_NREST)
        cp e
        ret nc
.cn:    inc hl
        dec bc
        ld a,b
        or c
        jr nz,.c
        ret

; rest: A = a slot, HL = its dirty map entry -> the slot's colour list entry = the cell's scenery colour; counted in
; C_NREST once an update. Keeps BC, HL.
rest:   push hl
        push bc
        ld c,a                  ; the slot
        ld de,TILEMAP-DIRTY
        add hl,de
        ld a,(hl)               ; the cell's tile
        ld l,a
        ld h,high TILEATTR
        ld a,(hl)               ; its colour
.n_col: ld hl,SLOTCOL           ; (negative control: a colour list not put back)
        ld b,0
        add hl,bc
        ld (hl),a
        ld hl,SEEN
        add hl,bc
        ld a,(V_UPD)
        cp (hl)
        jr z,.d                 ; counted already (an overlapping box)
        ld (hl),a
        ld a,(C_NREST)
        inc a
        ld (C_NREST),a
.d:     pop bc
        pop hl
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
        ld a,(ix+3)             ; a figure in several colours (an item's own table, 0xBA8A): its signature
        or a
        jr nz,.uni
        ld a,(SIGT)
        inc a
        jr z,.k0                ; more than 9 cells: built every time
        ld a,d
        or e
        jr nz,.mk
        inc e
.mk:    ld c,MUT0               ; a mutable slot built for this image and this signature?
.ms:    ld l,c
        ld h,high HLIB_PCACHE
        ld a,(hl)
        cp e
        jr nz,.mn
        set 6,l
        ld a,(hl)
        cp d
        jr nz,.mn
        call sigeq
        jr nz,.mn
        ld a,c                  ; hit: no upload
        jp .use
.mn:    inc c
        ld a,c
        cp 64
        jr c,.ms
        push de                 ; a miss: the least recently used mutable slot not serving this update
        ld a,MUT0
        ld b,64-MUT0
        ld c,0
        ld d,64
.ml:    ld e,a
        add a,low SLOTUSE
        ld l,a
        ld h,high SLOTUSE
        ld a,(hl)
        or a
        ld a,255
        jr z,.mage
        ld a,(V_UPD)
        sub (hl)
.mage:  cp c
        jr c,.mln
        jr z,.mln
        ld c,a
        ld d,e
.mln:   ld a,e
        inc a
        djnz .ml
        ld a,d
        pop de
        ld c,a
        cp 64
        jr nc,.k0               ; all serving this update
        call sigsave            ; MSIG[slot] = SIGT
        ld a,c
        call hlib_pc_inval      ; its old image gone: the upload below always happens
        jp .free
.k0:    ld de,0                 ; key 0 = mutable: always uploaded
        jp .mut
.uni:   ld a,d                  ; one colour: key = graphics + pair, the colour compared from SLOTCLR on a hit
        or e
        jr nz,.k1
        inc e                   ; 0 is the mutable key
.k1:    ld a,e
        xor d
        xor (ix+2)
        and 63
        cp MUT0
        jr c,.h
        sub 64-MUT0             ; one-colour keys hash into 0 .. MUT0-1, clear of the mutable slots
.h:     ld (V_HASH),a
        ld b,PROBE              ; a slot already holding the key in this colour?
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
        ld a,c
        add a,low SLOTCLR
        ld l,a
        ld h,high SLOTCLR
        ld a,(hl)
        cp (ix+2)
        jr nz,.n
        ld a,c                  ; hit: no upload
        jp .use
.n:     ld a,c
        inc a
        cp MUT0
        jr c,.n2
        xor a                   ; the window wraps within 0 .. MUT0-1
.n2:    djnz .p
        push de                 ; a miss: the least recently used slot of the window (an animation's frames stay)
        ld a,(V_HASH)
        ld b,PROBE
        ld c,0                  ; the oldest age so far (0 = serving this update: never taken)
        ld d,MUT0               ; its slot (MUT0: none)
.l:     ld e,a
        add a,low SLOTUSE
        ld l,a
        ld h,high SLOTUSE
        ld a,(hl)
        or a
        ld a,255                ; never used: the oldest
        jr z,.age
        ld a,(V_UPD)
        sub (hl)                ; updates since its last use
.age:   cp c
        jr c,.ln
        jr z,.ln
        ld c,a
        ld d,e
.ln:    ld a,e
        inc a
        cp MUT0
        jr c,.l2
        xor a
.l2:    djnz .l
        ld a,d
        pop de
        ld c,a
        cp MUT0
        jr c,.ufree
        ld a,(V_HASH)           ; every one in the window serving this update: any of 0 .. MUT0-1 not serving it
        ld b,MUT0
.qu:    ld c,a
        add a,low SLOTUSE
        ld l,a
        ld h,high SLOTUSE
        ld a,(V_UPD)
        cp (hl)
        jr nz,.ufree
        ld a,c
        inc a
        cp MUT0
        jr c,.qu2
        xor a
.qu2:   djnz .qu
                                ; all serving this update: reuse the last
.ufree: ld a,c                  ; C = the slot: its colour, its old key gone (the upload always happens)
        add a,low SLOTCLR
        ld l,a
        ld h,high SLOTCLR
        ld a,(ix+2)
        ld (hl),a
        ld a,c
        call hlib_pc_inval
        jp .free
.mut:   ld a,MUT0               ; several colours: from the mutable slots (MUT0 ..), so cached figures stay
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
        ld a,(ix+3)
        or a
        call nz,ptab            ; and its 16 pixel pairs
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
        jp nc,.out
        push af
        add a,a
        add a,a
        add a,a
        ld (T_PX),a             ; the byte's first image column
        pop af
        xor a
        ld (T_LEFT),a           ; its first pixel looks its cell up
        ld a,(de)
        ld d,a                  ; D = graphics
        ld a,(bc)
        ld e,a                  ; E = mask
        ld a,(ix+3)
        or a
        jr z,.multi
        ld b,high PTAB          ; one colour: two pixels a look-up (graphics bits, then mask bits)
        DUP 4
        xor a
        sla d
        rla
        sla d
        rla
        sla e
        rla
        sla e
        rla
        or low PTAB
        ld c,a
        ld a,(bc)
        ld (hl),a
        inc hl
        EDUP
        pop bc
        pop de
        jp ovr                  ; the painted pixels over these 4 bytes (DE = the graphics byte)
.multi: ld b,4
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
        jp ovr
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
        jr nz,.go               ; one colour: T_INK / T_PAP set once (build)
        ld a,(T_LEFT)
        or a
        call z,pixcol           ; a new cell: its colour, and how many pixels stay in it
        ld a,(T_LEFT)
        dec a
        ld (T_LEFT),a
.go:    ld a,(T_PX)
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

; ptab: PTAB[g1 g2 m1 m2] = the two pixels (high nibble first) for those graphics and mask bits: ink where the
; graphics bit is set, else paper where the mask bit is clear, else 0 (see-through).
ptab:   ld hl,PTAB
        xor a
.e:     push af
        ld c,a
        bit 3,c
        ld a,(T_INK)
        jr nz,.p1
        bit 1,c
        ld a,0
        jr nz,.p1
        ld a,(T_PAP)
.p1:    rlca
        rlca
        rlca
        rlca
        ld b,a
        bit 2,c
        ld a,(T_INK)
        jr nz,.p2
        bit 0,c
        ld a,0
        jr nz,.p2
        ld a,(T_PAP)
.p2:    or b
        ld (hl),a
        inc l
        pop af
        inc a
        cp 16
        jr nz,.e
        ret

; codes: A = an attribute -> T_INK, T_PAP = its ink and paper as pixel values (1-8 normal, 9-15 bright, bright black 1).
codes:  push bc
        ld b,a
        and 7
        call code
        call remap
        ld (T_INK),a
        ld a,b
        rrca
        rrca
        rrca
        and 7
        call code
        call remap
        ld (T_PAP),a
        pop bc
        ret
; remap: A = a pixel value 0-15 -> REMAP's (identity but in Enhanced). Keeps BC, DE, HL.
remap:  push hl
        ld hl,REMAP
        add a,l
        ld l,a
.n_rmp: ld a,(hl)               ; (negative control: NOP NOP = the Spectrum colour kept in the painting palette's bank)
        pop hl
        ret

; ovr: DE = a graphics byte just turned into the 4 pattern bytes before HL -> its painted pixels over them, on the
; pixels that draw (ink or paper; a see-through pixel stays see-through). Off unless V_OVR. Keeps BC, DE, HL.
ovr:    ld a,(V_OVR)
        or a
        ret z
        push bc
        push de
        push hl
        ex de,hl                ; HL = the graphics byte's address, DE = past the 4 pattern bytes
        ld bc,-OVR_BASE
        add hl,bc
        jr nc,.none             ; below the table
        ld a,h
        cp high OVR_SPAN
        jr nc,.none             ; past it
        rrca
        rrca
        rrca
        and 31
        add a,OVR_PAGE0
        nextreg 0x50,a          ; this byte's page at slot 0
        ld a,h
        and 7
        ld h,a
        add hl,hl
        add hl,hl               ; HL = its entry
        ex de,hl                ; DE = the entry, HL = past the pattern bytes
        ld bc,-4
        add hl,bc
        ld b,4
.b:     ld a,(de)
        or a
        jr z,.n
        ld c,a                  ; two painted nibbles (0: that pixel's default)
        and 0xF0
        jr z,.l
        ld a,(hl)
        and 0xF0
        jr z,.l                 ; the pixel draws nothing
        ld a,(hl)
        xor c
        and 0xF0
        xor (hl)
.n_ovr: ld (hl),a               ; (negative control: NOP = the painted colours left out)
.l:     ld a,c
        and 0x0F
        jr z,.n
        ld a,(hl)
        and 0x0F
        jr z,.n
        ld a,(hl)
        xor c
        and 0x0F
        xor (hl)
        ld (hl),a
.n:     inc de
        inc hl
        djnz .b
        nextreg 0x50,0xFF       ; the ROM back at slot 0
.none:  pop hl
        pop de
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
; colour list (read before cells puts the scenery's back) -> T_INK, T_PAP, and T_LEFT = the pixels of this row that stay
; in that cell. Keeps BC, DE, HL.
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
        ld a,l
        and 7
        bit 0,(ix+8)
        jr nz,.ml
        neg
        add a,8                 ; 8 - (column & 7) pixels to the cell's right edge
        jr .lf
.ml:    inc a                   ; mirrored: (column & 7) + 1 to its left edge
.lf:    ld (T_LEFT),a
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
        call fcell              ; A = cell row, E = column -> the cell's colour at this figure's blit
        cp 0xFF
        jr z,.none
        call codes
.none:  pop bc
        pop de
        pop hl
        ret

; sigput: A -> the next signature byte; past 9 cells the signature is spoilt (SIGT = 0xFF: built every time).
; Keeps BC, DE, HL.
sigput: push hl
        push af
        ld hl,(F_SP)
        ld a,l
        cp low (SIGT+10)
        jr c,.ok
        pop af
        ld a,0xFF
        ld (SIGT),a
        pop hl
        ret
.ok:    pop af
        ld (hl),a
        inc hl
        ld (F_SP),hl
        pop hl
        ret

; sigeq: C = a mutable slot -> Z when MSIG for it equals SIGT (11 bytes). Keeps BC, DE, HL.
sigeq:  push bc
        push de
        push hl
        call sigat
        ld de,SIGT
        ld b,11
.q:     ld a,(de)
        cp (hl)
.n_sig: jr nz,.x                ; (negative control: NOPped = the colours ignored, a stale image served)
        inc e
        inc l
        djnz .q
        xor a                   ; Z: equal
.x:     pop hl
        pop de
        pop bc
        ret

; sigsave: C = a mutable slot -> MSIG for it = SIGT. Keeps BC, DE, HL.
sigsave: push bc
        push de
        push hl
        call sigat
        ex de,hl
        ld hl,SIGT
        ld b,11
.c:     ld a,(hl)
        ld (de),a
        inc l
        inc e
        djnz .c
        pop hl
        pop de
        pop bc
        ret

; sigat: C = a mutable slot -> HL = its MSIG entry (11 x (slot - MUT0)).
sigat:  ld a,c
        sub MUT0
        ld l,a
        add a,a
        add a,a
        add a,l
        add a,a
        add a,l                 ; 11 x (slot - MUT0)
        add a,low MSIG
        ld l,a
        ld h,high MSIG
        ret

; fbox: the figure at IX -> F_CX0..F_CX1, F_CY0..F_CY1 = the cells it covers inside the 32 x 20 map: columns x >> 3 ..
; (x + width x 8 - 1) >> 3, rows top >> 3 .. (top + rows - 1) >> 3. Carry: none (it lies below the map).
fbox:   ld a,(ix+6)
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
        cp 160
        ccf
        ret c                   ; top below the map
        rrca
        rrca
        rrca
        and 31
        ld (F_CY0),a
        ld a,(ix+7)
        add a,(ix+4)
        dec a
        jr c,.r19               ; past row 255
        rrca
        rrca
        rrca
        and 31
        cp 20
        jr c,.r1
.r19:   ld a,19
.r1:    ld (F_CY1),a
        or a                    ; no carry
        ret

; fcolour: the figure at IX -> (IX+3) = 1 when every cell it covers holds one colour in the game's colour list (then
; (IX+2) = it), else 0 (an item with a colour per cell). Cells: columns x >> 3 .. (x + width x 8 - 1) >> 3, rows
; top >> 3 .. (top + rows - 1) >> 3, inside the 32 x 20 map.
fcolour:
        ld a,0xFF
        ld (SIGT),a             ; no signature yet (0xFF: not cacheable)
        call fbox
        ld (ix+3),1
        ret c                   ; nothing on the map: one colour, the object's
        ld hl,SIGT+1            ; the signature: alignment, then each cell's colour (0xFF: no slot)
        ld b,9
        ld a,0xFE
.sc:    ld (hl),a
        inc l
        djnz .sc
        ld hl,SIGT+1
        ld (F_SP),hl
        ld a,(ix+8)
        and 1
        rrca
        rrca
        ld b,a                  ; mirror -> bit 6
        ld a,(ix+7)
        and 7
        add a,a
        add a,a
        add a,a
        or b
        ld b,a
        ld a,(ix+6)
        and 7
        or b
        ld (SIGT),a             ; x & 7 | (top & 7) << 3 | mirror << 6
        ld a,(F_CY0)
        ld b,a
        ld a,(F_CY1)
        sub b
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,(F_CX0)
        ld c,a
        ld a,(F_CX1)
        sub c
        or b
        ld (SIGT+10),a          ; the clipped box's columns - 1 | rows - 1 << 4 (the same cells, another shape)
        ld a,0xFF
        ld (F_COL),a
        ld a,(F_CY0)
.row:   ld b,a                  ; B = cell row
        ld a,(F_CX0)
.col:   ld c,a                  ; C = cell column
        push bc
        ld a,b
        ld e,c
        call fcell              ; the cell's colour at this figure's blit
        cp 0xFF
        jr z,.noslot            ; no slot here
        ld e,a
        call sigput
        ld a,(F_COL)
        cp 0xFF
        jr nz,.cmp
        ld a,e
        ld (F_COL),a
        jr .skip
.cmp:   cp e
        jr z,.skip
.n_multi: ld (ix+3),0           ; a second colour (negative control: LD (IX+3),1 = one colour for every figure)
        jr .skip
.noslot: ld a,0xFF
        call sigput
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
attrs:  ld a,(V_NSPR)
        cp NSPRMAX
        ret nc                  ; the table full: this tile not shown
        ld hl,(C_ATP)
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
        ld c,0                  ; C = Y bit 8
        add a,(ix+7)            ; top + 16 x row
        jr nc,.y1
        inc c
.y1:    add a,32
        jr nc,.y2
        inc c
.y2:    ld (hl),a               ; attribute 1: Y bits 0-7. A figure above the room (top 224-255, the game's off-screen
        inc hl                  ; rows) gets Y 256 or more, below the screen, as the game leaves it unseen
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
        or c                    ; Y bit 8
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
        ASSERT (SLOTUSE & 255) + 64 <= 256
        ASSERT (SIGT & 255) + 11 <= 256 && SIGT >= PTAB + 16 && SLOTCLR >= SIGT + 11 && SEEN >= SLOTCLR + 64 && (SEEN & 255) + 128 <= 256
        ASSERT MSIG >= SEEN + 128 && (MSIG & 255) + 176 <= 256 && MSIG + 176 <= 0x2900 && ATTRTAB + 5 * NSPRMAX <= PTAB
        ASSERT (PTAB & 15) == 0 && PTAB >= ATTRTAB + 640 && PTAB + 16 <= 0x2900

        SAVEBIN "jtn2_page.bin", code_start, code_end - code_start

; ---- the stub's set-up (stub_extra at 0xD000, CALLed once before the game starts) ----
        ORG 0xD000
setup_start:
; setup: bank 0 = 0 clear, 1-8 the Spectrum's normal colours (black .. white), 9-15 the bright ones; sprite 127 on
; top (later objects over earlier, as the game draws); sprites visible.
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,setpal
        ld b,32                 ; bank 0 (the Spectrum colours), bank 1 (Enhanced's painting palette)
.p:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .p
        nextreg 0x4B,0
        nextreg 0x15,0x01       ; sprites visible (SLU order); bit 6 clear = sprite 127 on top: later objects over earlier
        ret
setpal: db 0x00, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6        ; 0 clear, 1-8 normal black .. white
        db 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF                    ; 9-15 bright blue .. white
setpal1: ds 16                  ; bank 1: Enhanced's painting palette (the build writes it; 0 entries otherwise)
setup_end:
        SAVEBIN "jtn2_setup.bin", setup_start, setup_end - setup_start
