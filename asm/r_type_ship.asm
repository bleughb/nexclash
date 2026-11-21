; R-Type sprite build (L2_SHIP): the level 3 battleship hull as a 1-bit text-mode tilemap.
;
; The hull is 46 strips of 1x13 cells (table (C4BA), indices 29..56, object IY 85D9, owner byte 9C),
; replotted every 8th update at whole-cell steps. As sprites it needs about 180 patterns, more than
; the Next has, so it came out as 8x8 ULA blocks. Here each non-empty cell becomes one text-mode tile
; (8 bytes, 333 tiles in 512-tile mode) with its original attribute as the palette offset, so it shows
; with exactly the original two colours per cell. Black paper is opaque, as on the ULA.
;
; Memory: tilemap and tiles in bank 7's lower 8K (page 14), which holds packed level data the game
; does not touch during level 3; that page is saved to page 126 on first use and put back by ship_off
; (every L2_OFF and the unpack hook). Map at offset 0 (40x32 entries of 2 bytes), tiles from 0A00,
; per-strip map columns (13 entries) from 1600.
;
; The game's plots only mark the strips seen; at publish (ship_tick) the map is rebuilt from them
; (strip i in map column i mod 40) and the scroll registers place it, so the tilemap changes at the
; same copier call as the ULA. The copier gate blanks owner-9C cells on the ULA (spr_gate).
;
; Lives in page SHIP_PG (bank 63 high half) at 0x0100, mapped into slot 0 while it runs (s_call).
; Entries: 0100 plot (HL graphic, B row, C column; A = 0 if the tilemap shows it), 0103 off, 0106 tick,
; 0109 scenery cell lookup (scn_find: this page is also the build's spare code page).

        MMU 0,SHIP_PG
        ORG 0x0100
ship_start:
        jp ship_plot
        jp ship_off
        jp ship_tick
        jp scn_find             ; 0109: scenery mask and paint of a cell (l2scroll put_cell)

NSTRIP  EQU 46
STRIP0  EQU 0x28                ; table entry of the first strip (A = 29, entry A-1)
SAVE_PG EQU 126                 ; page 14 kept here while the tilemap uses it
MAP     EQU 0x4000              ; page 14 seen in slot 2
TILES   EQU MAP+0x0A00
IMG     EQU MAP+0x1600          ; strip i: its 13 map entries at IMG + 26i
AGE_MAX EQU 12                  ; updates without a hull plot before the tilemap goes off

; ---- plot: HL graphic, B row, C column ------------------------------------------------------------
ship_plot:
        ld a,c
        dec a
        cp 30
        jr nc,.no               ; outside the play columns (before the ship is in): as before
        ld a,(built)
        or a
        jr nz,.b
        push bc
        push hl
        call build
        pop hl
        pop bc
        ld a,(built)
.b:     dec a
        jr nz,.no               ; build failed (2): sprites as before
        push bc
        ld de,ship_g
        ld bc,NSTRIP*256
.f:     ld a,(de)
        inc de
        cp l
        jr nz,.n
        ld a,(de)
        cp h
        jr z,.hit
.n:     inc de
        inc c
        djnz .f
        pop bc
.no:    ld a,1
        ret
.hit:   ld e,c                  ; E = strip
        pop bc
        ld a,c
        sub e
        ld (new_l),a            ; column of strip 0 (signed)
        ld a,b
        ld (new_b),a
        ld d,0
        ld hl,seen
        add hl,de
        ld (hl),1
        ld a,1
        ld (plotted),a
        xor a
        ret

; ---- tick: once per update, at publish -------------------------------------------------------------
ship_tick:
        ld a,(plotted)
        or a
        jr nz,.new
        ld hl,age
        inc (hl)
        ld a,(hl)
        cp AGE_MAX+1
        ret c
        jp ship_off
.new:   xor a
        ld (plotted),a
        ld (age),a
        call map_fill
        ld a,(new_l)            ; X = -(32 + 8L) mod 320
        ld l,a
        add a,a
        sbc a,a
        ld h,a                  ; HL = L, signed
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de               ; -320..272
        ex de,hl
        ld hl,0
        or a
        sbc hl,de               ; -272..320
        bit 7,h
        jr z,.p
        ld de,320
        add hl,de
.p:     ld de,320
        or a
        sbc hl,de
        jr nc,.x
        add hl,de
.x:     ld a,h
        nextreg 0x2F,a
        ld a,l
        nextreg 0x30,a
        ld a,(new_b)            ; Y = -(32 + 8B) mod 256
        add a,a
        add a,a
        add a,a
        add a,32
        neg
        nextreg 0x31,a
        ld a,(shown)
        or a
        ret nz
        inc a
        ld (shown),a
        nextreg 0x6E,0xC0       ; map: bank 7 offset 0
        nextreg 0x6F,0xCA       ; tiles: bank 7 offset 0A00
        nextreg 0x1C,8          ; reset the tilemap clip index
        nextreg 0x1B,20         ; play columns 1..30 (x 40..279, in pairs), rows 0..19
        nextreg 0x1B,139
        nextreg 0x1B,32
        nextreg 0x1B,191
        nextreg 0x6B,0x8B       ; on, 40 columns, attributes, text mode, 512 tiles, over the ULA
        ret

; Map column m: strip m or m+40 if the game plotted it this cycle, else empty. Clears seen.
map_fill:
        ld a,i
        push af
        di
        nextreg 0x52,14
        ld hl,MAP
        ld c,0                  ; C = column
.m:     ld a,c
        ld b,a
        call seen_at
        jr z,.s
        ld a,c
        add a,40
        ld b,a
        cp NSTRIP
        jr nc,.e
        call seen_at
        jr z,.s
.e:     push hl                 ; empty column
        ld de,79
        ld b,13
.z:     ld (hl),0
        inc hl
        ld (hl),0
        add hl,de
        djnz .z
        pop hl
        jr .nx
.s:     push hl                 ; strip B: its 13 entries
        push hl
        ld d,b
        ld e,26
        mul d,e
        ld hl,IMG
        add hl,de
        pop de
        ld b,13
.c:     ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        add de,79
        djnz .c
        pop hl
.nx:    inc hl
        inc hl
        inc c
        ld a,c
        cp 40
        jr c,.m
        nextreg 0x52,0x0A
        call seen_clear
        pop af
        ret po
        ei
        ret
seen_at:                        ; A = strip: Z if plotted this cycle
        push hl
        ld hl,seen
        add hl,a
        ld a,(hl)
        pop hl
        dec a
        ret
seen_clear:
        ld hl,seen
        ld de,seen+1
        ld bc,NSTRIP-1
        ld (hl),0
        ldir
        ret

; ---- first hull plot: save page 14, build tiles, map entries per strip and the palette ---------------
build:  ld a,i
        push af
        di
        push ix
        nextreg 0x52,14
        nextreg 0x53,SAVE_PG
        ld hl,0x4000
        ld de,0x6000
        ld bc,0x2000
        ldir                    ; page 14 kept in page 126
        nextreg 0x53,0x0B
        ld a,1
        ld (ship_on),a          ; from now ship_off must put it back
        ld hl,MAP
        ld de,MAP+1
        ld bc,0x0A07
        ld (hl),0
        ldir                    ; empty map, tile 0 blank
        ld hl,(0xC4BA)
        ld de,STRIP0*4
        add hl,de
        ld (b_ent),hl
        ld hl,TILES+8
        ld (b_tile),hl
        ld hl,IMG
        ld (b_img),hl
        ld hl,1
        ld (b_n),hl
        ld ix,ship_g
        ld b,NSTRIP
.s:     push bc
        ld hl,(b_ent)
        ld a,(hl)
        cp 1
        jp nz,.fail
        inc hl
        ld a,(hl)
        cp 13
        jp nz,.fail
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (b_ent),hl
        ld (ix+0),e
        ld (ix+1),d
        inc ix
        inc ix
        ex de,hl                ; HL = the strip's cell stream
        ld b,13
.c:     ld a,(hl)
        cp 0x36
        jr nz,.cell
        inc hl
        ld de,(b_img)
        xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (b_img),de
        jr .nc
.cell:  and 0x7F                ; palette offset = attribute (flash bit dropped), tile bit 8 below
        add a,a
        ld c,a
        ld de,(b_n)
        ld a,d
        or c
        ld c,a
        push hl
        ld hl,(b_img)
        ld (hl),e
        inc hl
        ld (hl),c
        inc hl
        ld (b_img),hl
        inc de
        ld (b_n),de
        pop hl
        inc hl
        ld de,(b_tile)
        ld a,d
        cp high(IMG)
        jr nc,.fail             ; more tiles than room (never for this ship)
        push bc
        ld bc,8
        ldir
        pop bc
        ld (b_tile),de
.nc:    djnz .c
        pop bc
        djnz .s
        ; tilemap palette: index 2a+p = attribute a, pixel p (ink or paper); index 0 transparent
        nextreg 0x43,0x30
        nextreg 0x40,0
        ld c,0
.pl:    ld a,c
        srl a
        ld b,a
        jr c,.ink
        rrca
        rrca
        rrca
.ink:   and 7
        bit 6,b
        jr z,.nb
        add a,8
.nb:    ld hl,col_tab
        add hl,a
        ld a,(hl)
        nextreg 0x41,a
        inc c
        jr nz,.pl
        nextreg 0x40,0
        ld a,TRANSP
        nextreg 0x41,a
        nextreg 0x43,0
        ld a,1
        jr .out
.fail:  pop bc
        call restore
        ld a,2
.out:   ld (built),a
        nextreg 0x52,0x0A
        pop ix
        pop af
        ret po
        ei
        ret

; Interrupts off: page 126 back into page 14.
restore:
        nextreg 0x52,14
        nextreg 0x53,SAVE_PG
        ld hl,0x6000
        ld de,0x4000
        ld bc,0x2000
        ldir
        nextreg 0x52,0x0A
        nextreg 0x53,0x0B
        ret

; ---- off: tilemap hidden, page 14 back ---------------------------------------------------------------
ship_off:
        nextreg 0x6B,0
        xor a
        ld (ship_on),a
        ld (shown),a
        ld (plotted),a
        ld (age),a
        ld a,(built)
        dec a
        jr nz,.z                ; 0 nothing kept, 2 already put back
        ld a,i
        push af
        di
        call restore
        pop af
        jp po,.z
        ei
.z:     xor a
        ld (built),a
        jp seen_clear

; ---- scenery cell lookup (put_cell, every level; the hook page has no room) ----------------------------
; pc_key (attribute | 80, pc_src) -> pc_mask (see-through pixels) and pc_paint (64 bytes, column by column:
; 0 = the game's colour, 1-15 a painted colour, 80 = painted see-through; r_type_scenery.py). The level's
; sorted keys (page MASK_PAGE0 + 2*(level-1): count, 9-byte keys, first paint record at 8190) and its masks
; (next page) are searched with that page in slot 2. Keeps BC, DE, HL; returns A = 0.
SCN_PG0 EQU 128                 ; paint records: banks 64-71, 40 bytes each, 204 to a page
REC_PP  EQU 204
scn_find:
        push bc
        push de
        push hl
        xor a
        ld hl,pc_mask
        ld b,8
.z1:    ld (hl),a
        inc hl
        djnz .z1
        ld hl,pc_paint
        ld b,64
.z2:    ld (hl),a
        inc hl
        djnz .z2
        ld a,(pc_blk)
        cp 8
        jp nz,.out              ; not scenery
        ld a,(0x719C)
        sub '1'
        cp 8
        jp nc,.out
        add a,a
        add a,MASK_PAGE0
        ld (sf_pg),a
        ld e,a
        ld a,i
        push af
        di
        ld a,e
        nextreg 0x52,a
        ld hl,(0x4000)
        ld (sf_n),hl
        ld hl,0
        ld (sf_lo),hl
.bs:    ld hl,(sf_n)
        ld a,h
        or l
        jp z,.done              ; not listed: no mask, no paint
        srl h
        rr l
        ld (sf_h),hl
        ld de,(sf_lo)
        add hl,de
        ld (sf_mid),hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        ld de,0x4002
        add hl,de               ; 4002 + 9 * mid
        ld de,pc_key
        ld b,9
.cmp:   ld a,(de)
        cp (hl)
        jp nz,.ne
        inc hl
        inc de
        djnz .cmp
        ld hl,(0x4000+8190)     ; found: record = the level's first + mid
        ld de,(sf_mid)
        add hl,de
        ld (sf_rec),hl
        ld a,(sf_pg)
        inc a
        nextreg 0x52,a
        ex de,hl                ; HL = mid
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x4000
        add hl,de
        ld de,pc_mask
        ld bc,8
        ldir
        ld hl,(sf_rec)
        ld c,SCN_PG0
        ld de,REC_PP
.dv:    or a
        sbc hl,de
        jr c,.dd
        inc c
        jr .dv
.dd:    add hl,de               ; L = slot in the page
        ld a,c
        nextreg 0x52,a
        ld d,l
        ld e,40
        mul d,e
        ld hl,0x4000
        add hl,de
        ld (sf_rec),hl          ; the record
        ld c,0                  ; C = line
.row:   ld hl,(sf_rec)
        ld a,c
        add a,a
        add a,a
        add hl,a                ; 4 bytes of nibbles, left pixel high
        ld de,pc_paint
        ld a,e
        add a,c
        ld e,a
        ld b,4
.nb:    ld a,(hl)
        inc hl
        push af
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (de),a
        ld a,e
        add a,8
        ld e,a
        pop af
        and 15
        ld (de),a
        ld a,e
        add a,8
        ld e,a
        djnz .nb
        ld hl,(sf_rec)
        ld a,32
        add a,c
        add hl,a
        ld de,pc_paint
        ld a,e
        add a,c
        ld e,a
        ld a,(hl)               ; see-through mask, bit 7 = leftmost
        ld b,8
.mk:    rlca
        jr nc,.mn
        push af
        ld a,0x80
        ld (de),a
        pop af
.mn:    push af
        ld a,e
        add a,8
        ld e,a
        pop af
        djnz .mk
        inc c
        ld a,c
        cp 8
        jr nz,.row
.done:  nextreg 0x52,0x0A
        pop af
        jp po,.out
        ei
.out:   pop hl
        pop de
        pop bc
        xor a
        ret
.ne:    jr c,.left              ; key below this entry
        ld hl,(sf_mid)
        inc hl
        ld (sf_lo),hl
        ld hl,(sf_n)
        ld de,(sf_h)
        or a
        sbc hl,de
        dec hl
        ld (sf_n),hl
        jp .bs
.left:  ld hl,(sf_h)
        ld (sf_n),hl
        jp .bs
sf_pg:  db 0
sf_n:   dw 0
sf_lo:  dw 0
sf_h:   dw 0
sf_mid: dw 0
sf_rec: dw 0

built:  db 0                    ; 1 tiles ready (page 14 kept in 126), 2 build failed
shown:  db 0
plotted: db 0
age:    db 0
new_l:  db 0
new_b:  db 0
b_ent:  dw 0
b_tile: dw 0
b_img:  dw 0
b_n:    dw 0
ship_g: ds NSTRIP*2
seen:   ds NSTRIP
ship_end:
