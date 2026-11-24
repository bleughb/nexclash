; Jack the Nipper (Gremlin Graphics 1986, 48K) - figures as hardware sprites. Facts and design: games/jack_the_nipper.md.
; The sprite routine 0x8009 draws each object masked (AND mask, OR graphics) into a shadow screen at 0x6000-0x6FFF and
; marks its cells; the copier 0x86F9 copies marked cells to the display, 0x8735 restores them from the tile map.
; The draw code itself is NOT replaced: at its two returns from the address helper 0x87BB (0x80C9 for 16-wide
; figures, 0x8273 for 24-wide) the hook records the figure and moves the shadow address from 0x6000-0x6FFF to
; 0x2000-0x2FFF (RES 6,H: no flag or register but H changes), so the draw lands in a scratch shadow in this page and
; the real shadow keeps the background. The cell marks take only H bits 3 and 0-2 and L (0x8123): the same cells.
; At the copier's entry 0x86F9 (called after the figure draws from four places: 0xAC72 every update, 0xAA4A, 0xA66C,
; 0xA72C) the commit turns the figures recorded since the last copy into
; 4-bit sprites (pixel 0 clear, 1 black = the graphics, 2 body = mask-cleared; the body colour by the palette offset,
; one bank per Spectrum colour: the paper and bright of the cell under the figure's feet), uploads the tiles not
; cached (hlib_pcache), writes the attributes, hides the sprites shown last time and not now, then runs the copier.
; Memory: this file is Next page JTN_PAGE at MMU slot 1 (0x2000-0x3FFF) for the whole game (the game never reads the
; ROM there): 0x2000-0x2FFF scratch shadow, 0x3000-0x35FF state, 0x3600- code, 0x3E00 the tail restore, 0x3F00 the
; stub's register block. Interrupts are off for the whole game (no interrupt accepted in the recording).

        DEVICE ZXSPECTRUMNEXT

D16_BACK  EQU 0x80CC        ; after PUSH HL / PUSH AF / AND A at 0x80C9 (the 16-wide path)
D24_BACK  EQU 0x8276        ; the same three bytes at 0x8273 (the 24-wide path)
COPY_BACK EQU 0x86FC        ; the copier after its first instruction (LD HL,0x7CFF at 0x86F9; its loop re-enters at 0x86FC)
MAXFIG    EQU 24            ; figures recorded per game update
FIGSZ     EQU 10            ; +0 gfx, +2 mask, +4 rows, +5 width bytes (2 / 3), +6 x, +7 top, +8 mirror, +9 bank
SPR0      EQU 0             ; first sprite number
PROBE     EQU 8             ; slots tried from a key's hash

; ---- page state (zero at start: the page image is zero there) ----
FIGS      EQU 0x3000        ; MAXFIG x FIGSZ
HLIB_PCACHE EQU 0x3100      ; hlib_pcache: +slot key low, +64+slot key high
SLOTUSE   EQU 0x3180        ; 64 bytes: the update number a slot last served
V_NFIG    EQU 0x31C0        ; figures recorded this update
V_SHOWN   EQU 0x31C1        ; sprites shown after the last commit
V_UPD     EQU 0x31C2        ; update number (1-255)
V_LATCH   EQU 0x31C3        ; hlib_speed latch
V_HSP     EQU 0x31C4        ; the game's SP while a hook runs (2)
V_NSPR    EQU 0x31C6        ; sprites in ATTRTAB
R_SH      EQU 0x31C7        ; record's inputs
R_ROWS    EQU 0x31C8
R_WID     EQU 0x31C9
R_MASK    EQU 0x31CA        ; (2)
R_GFX     EQU 0x31CC        ; (2)
R_HL      EQU 0x31CE        ; (2)
R_X       EQU 0x31D0
R_Y       EQU 0x31D1
C_FIG     EQU 0x31D2        ; commit: the entry (2)
C_COLS    EQU 0x31D4        ; sprite columns (1 / 2)
C_TROWS   EQU 0x31D5        ; tile rows (1-3)
C_TR      EQU 0x31D6
C_TC      EQU 0x31D7
C_SLOT    EQU 0x31D8        ; slot of the current tile pair
C_PAIR    EQU 0x31D9        ; pair index of C_SLOT (0xFF none)
C_ATP     EQU 0x31DA        ; ATTRTAB write pointer (2)
B_ROW     EQU 0x31DC        ; build: figure row from the top
B_T       EQU 0x31DD        ; build: tile index
T_TC      EQU 0x31DE        ; tile: its column
T_N       EQU 0x31DF        ; tile: rows left
T_COL     EQU 0x31E0        ; tile: byte column of its first byte
T_G       EQU 0x31E1        ; tile: graphics byte address (2)
C_T       EQU 0x31E3        ; figure: the current tile index
V_HASH    EQU 0x31E4        ; slot: the key's hash
TILEBUF   EQU 0x3200        ; 256 bytes: the two 4-bit tiles of a slot
HSTACK    EQU 0x3400        ; hook stack top (0x3300-0x33FF)
ATTRTAB   EQU 0x3400        ; 5 bytes a sprite (attributes 0-4)

        INCLUDE "lib/hlib_speed.asm"     ; macros only

        ORG 0x3600
code_start:

; e_d16 / e_d24: JP here from 0x80C9 / 0x8273, right after CALL 0x87BB: HL = the figure's bottom-row shadow address,
; A = its pixel shift, DE = mask, DE' = graphics, IX = the object. Every register and flag is kept (the hook runs on
; its own stack); the three displaced bytes then run on the scratch address.
e_d16:  ld (V_HSP),sp
        ld sp,HSTACK
        push af
        push bc
        push de
        push hl
        ld bc,0x0218            ; width 2 bytes; 24 rows ...
        bit 0,(ix+2)
        jr z,.r
        ld c,16                 ; ... or 16 when (IX+2) bit 0 is set (0x80CF)
.r:     call record
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_HSP)
        res 6,h
        push hl
        push af
        and a
        jp D16_BACK

e_d24:  ld (V_HSP),sp
        ld sp,HSTACK
        push af
        push bc
        push de
        push hl
        ld bc,0x0328            ; width 3 bytes; 40 rows ...
        bit 2,(ix+2)
        jr z,.a
        ld c,24                 ; ... 24 (bit 2) ...
        jr .r
.a:     bit 3,(ix+2)
        jr z,.r
        ld c,32                 ; ... or 32 (bit 3), as 0x8279
.r:     call record
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_HSP)
        res 6,h
        push hl
        push af
        and a
        jp D24_BACK

; record: B = width bytes, C = rows, A = shift, HL = bottom-row shadow address, DE = mask, DE' = graphics, IX = the
; object. Adds an entry to FIGS. AF, BC, DE, HL lost; alternates and IX kept.
record: ld (R_SH),a
        ld a,c
        ld (R_ROWS),a
        ld a,b
        ld (R_WID),a
        ld (R_MASK),de
        ld (R_HL),hl
        exx
        ld (R_GFX),de
        exx
        ld a,(V_NFIG)
        cp MAXFIG
        ret nc
        ld c,a
        inc a
        ld (V_NFIG),a
        ld l,c
        ld h,0
        add hl,hl               ; 2n
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl               ; 8n
        add hl,de               ; 10n
        ld de,FIGS
        add hl,de
        ex de,hl                ; DE = the entry
        ld hl,(R_GFX)
        call st16               ; +0 graphics
        ld hl,(R_MASK)
        call st16               ; +2 mask
        ld a,(R_ROWS)
        ld (de),a               ; +4 rows
        inc de
        ld a,(R_WID)
        ld (de),a               ; +5 width bytes
        inc de
        ld hl,(R_HL)
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(R_SH)
        add a,b                 ; x = column x 8 + shift
        ld (R_X),a
        ld (de),a               ; +6 x
        inc de
        ld a,h                  ; y = (H and 0x18) << 3 | (L and 0xE0) >> 2 | H and 7: the shadow's screen layout
        and 0x18
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
        ld b,a
        ld a,h
        and 7
        or b
        ld (R_Y),a              ; the bottom row
        ld b,a
        ld a,(R_ROWS)
        ld c,a
        ld a,b
        sub c
        inc a
        ld (de),a               ; +7 top = bottom - rows + 1 (mod 256: a figure above row 0 is clipped by the sprite)
        inc de
        xor a
        bit 0,(ix+4)
        jr nz,.nm
        inc a                   ; (IX+4) bit 0 clear: the mirrored draw (0x8482 / 0x85D0)
.nm:    ld (de),a               ; +8 mirror
        inc de
        ld a,(R_Y)              ; the cell under the feet: row = bottom >> 3, column = (x + width x 4) >> 3
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl               ; row x 32
        ld a,(R_WID)
        add a,a
        add a,a
        ld b,a
        ld a,(R_X)
        add a,b
        rrca
        rrca
        rrca
        and 31
        or l
        ld l,a
        ld a,h
        add a,0x58
        ld h,a
        ld a,(hl)               ; its attribute
        ld b,a
        rrca
        rrca
        rrca
        and 7                   ; paper
        bit 6,b
        jr z,.nb
        or 8                    ; bright
.nb:    ld (de),a               ; +9 bank
        ret

st16:   ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ret

; e_cmt: JP here from the copier's entry 0x86F9: the figures drawn since the last copy show from now, as the original's
; copy puts them on the screen (a figure not drawn again is gone at the next copy: its cells were restored). Every
; register and flag is kept; then the copier's first instruction and the rest of it.
e_cmt:  ld (V_HSP),sp
        ld sp,HSTACK
        push af
        push bc
        push de
        push hl
        push ix
        HLIB_SPEED_IN V_LATCH
        call commit
        HLIB_SPEED_OUT V_LATCH
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_HSP)
        ld hl,0x7CFF
        jp COPY_BACK

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
.p2:    xor a
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
.hide:  ld a,(V_SHOWN)
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
figure: ld a,(ix+5)
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
; Key = graphics address + pair (never 0; an image's graphics address names its bytes: the game never rewrites them).
slot:   ld e,(ix+0)
        ld d,(ix+1)
        ld a,(C_PAIR)
        add a,e
        ld e,a
        adc a,d
        sub e
        ld d,a                  ; DE = key
        or e
        jr nz,.k
        inc e                   ; 0 is the mutable key
.k:     ld a,e
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
        ld b,64
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
; left pixel in the high nibble): 1 where the graphics bit is set, else 2 where the mask bit is clear, else 0.
build:  ld hl,TILEBUF
        ld a,(C_PAIR)
        add a,a
        ld (B_T),a
        call tile
        ld a,(B_T)
        inc a
        ld (B_T),a
        ; HL continues at TILEBUF + 128
tile:   ld a,(C_COLS)           ; tile t -> its row tr = t / cols and column tc = t mod cols
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
        ld (T_COL),a            ; its first byte column = tc x 2
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,a
        ld (B_ROW),a            ; its first figure row from the top = tr x 16
        ld a,16
        ld (T_N),a
.row:   ld a,(B_ROW)
        ld c,a
        ld a,(ix+4)
        dec a
        sub c                   ; memory row = rows - 1 - row (the bottom row first)
        jr c,.clr               ; below the figure
        ld e,a
        ld d,0
        ld b,(ix+5)
        push hl
        ld hl,0
.mw:    add hl,de
        djnz .mw                ; memory row x width
        ld a,(T_COL)
        ld e,a
        add hl,de               ; + the first byte column
        ex de,hl
        ld l,(ix+0)
        ld h,(ix+1)
        add hl,de
        ld (T_G),hl             ; the graphics byte
        ld l,(ix+2)
        ld h,(ix+3)
        add hl,de
        ld b,h
        ld c,l                  ; BC = the mask byte
        ld de,(T_G)             ; DE = the graphics byte
        pop hl
        ld a,(T_COL)
        call byte2              ; pixels 0-7
        inc de
        inc bc
        ld a,(T_COL)
        inc a
        call byte2              ; pixels 8-15
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

; byte2: A = byte column, DE = graphics byte, BC = mask byte, HL = 4 output bytes (8 pixels). Outside the figure's
; width (column >= (IX+5)): clear. DE, BC kept; HL += 4.
byte2:  push de
        push bc
        cp (ix+5)
        jr nc,.out
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

; cls: the top pixel of D (graphics) and E (mask) -> A = 1 ink, 2 body (mask clear), 0 clear; D, E shifted left.
cls:    sla d
        jr c,.ink
        sla e
        ld a,0
        ret c
        ld a,2
        ret
.ink:   sla e
        ld a,1
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
        ld a,(ix+9)
        add a,a
        add a,a
        add a,a
        add a,a                 ; bank << 4
        bit 0,(ix+8)
        jr z,.n2
        or 8                    ; X mirror
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

        SAVEBIN "jtn_page.bin", code_start, code_end - code_start

; ---- the stub's set-up (stub_extra at 0xD000, CALLed once before the game starts) ----
        ORG 0xD000
setup_start:
; setup: run once by the stub. The sprite palette (first sprite palette): bank b (0-15) = black at 1 and the Spectrum
; colour b (0-7 normal, 8-15 bright) at 2; index 0 clear (NR 0x4B = 0); sprites on, over the border off.
setup:  nextreg 0x43,0x20       ; edit the first sprite palette, auto-increment
        nextreg 0x40,0
        ld hl,setpal
        ld b,16
.b:     xor a
        nextreg 0x41,a          ; 0: clear (the transparent index)
        nextreg 0x41,a          ; 1: black
        ld a,(hl)
        inc hl
        nextreg 0x41,a          ; 2: the bank's colour
        ld c,13
        xor a
.z:     nextreg 0x41,a
        dec c
        jr nz,.z
        djnz .b
        nextreg 0x4B,0          ; sprite transparency index
        nextreg 0x15,0x41       ; sprites visible (SLU order), sprite 127 on top: later objects over earlier, as the game draws
        ret
setpal: db 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6    ; RGB332: black, blue, red, magenta, green, cyan, yellow, white
         db 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF    ; bright

setup_end:
        SAVEBIN "jtn_setup.bin", setup_start, setup_end - setup_start
