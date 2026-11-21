; R-Type prototype (2026-11-15): scenery on a hardware-scrolled Layer 2.
; The original game runs unchanged and visible on the ULA (figures, stars, HUD);
; only the scenery pixels move to Layer 2. No pace machinery: the main loop runs
; at 28MHz and the native three-interrupt wait paces it. The native ISR (all
; beeper effects) runs at 3.5MHz with ROM in slot 0. Not an engine or deliverable.
;
; Native scenery: 8842 shifts every background span of the ULA one pixel per call
; (7A8E = 0), fed from the staged column the controller copies to hidden ULA
; column 31 (89C3, every eighth call). Here the staged column is drawn on Layer 2
; instead and its staging pixels are zeroed, so the ULA keeps no scenery and the
; native shift moves blank cells. Owner/attribute/dirty maps are untouched.
        DEVICE ZXSPECTRUMNEXT
L2A_BANK EQU 48                 ; Layer 2 640x256x4: screen A, 16K banks 48-52 (pages 96-105)
L2A_PAGE EQU L2A_BANK*2
L2B_BANK EQU 53                 ; screen B (half a pixel to the right), banks 53-57 (pages 106-115)
L2B_PAGE EQU L2B_BANK*2
TRANSP  EQU 0xE3
        IFDEF L2_SPR_FRONT
LORDER  EQU 0x40                ; NR 0x15: sprites over Layer 2 over ULA, sprite 0 on top
        ELSE
LORDER  EQU 0x44                ; NR 0x15: Layer 2 (scenery) over sprites over ULA, as the original;
                                ; scenery black open to the sky is see-through (scenery_masks.py)
        ENDIF
MASK_PAGE0 EQU 32               ; scenery masks: level n in 16K bank 15+n (pages 30+2n keys, 31+2n masks)
        ; Outside play (titles, high scores, name entry, continue) the game runs at
        ; its own 3.5MHz: those screens time themselves with busy loops.
        MACRO L2_OFF
        IFDEF L2_SHIP
        call ship_stop          ; battleship tilemap off, bank 7 data back (ship.asm)
        ENDIF
        nextreg 0x69,0
        xor a
        ld (run_fast),a
        nextreg 7,0
        IFDEF L2_SPRITES
        nextreg 0x15,LORDER     ; sprites hidden
        xor a
        ld (spr_on),a
        ENDIF
        ENDM
        ORG 0x2000
hook_setup:
        ; The game reads Kempston only on port 1F. NextZXOS may leave either
        ; connector in another mode, so make both Kempston 1; keep 50/60Hz and
        ; the scandoubler bit. (l2_off_title clears the game's "no Kempston"
        ; flag 7A8B at every title.)
        push af
        push bc
        ld bc,0x243B
        ld a,5
        out (c),a
        inc b
        in a,(c)
        and 0x05
        or 0x50                 ; mode 001 (Kempston 1) on both connectors
        nextreg 5,a
        pop bc
        pop af
        IFDEF L2_NOTAPE
        call spec_hold
        ENDIF
        nextreg 0x12,L2A_BANK
        nextreg 0x14,TRANSP
        nextreg 0x70,0x20       ; 640x256, 4bpp, palette offset 0
        nextreg 0x69,0          ; Layer 2 off until a level is drawn
        nextreg 0x16,0
        nextreg 0x71,0
        nextreg 0x17,0
        nextreg 0x1C,1          ; reset Layer 2 clip index
        nextreg 0x18,20         ; play columns 1..30 (x 40..279 of 320, clip x in pairs), rows 0..19
        nextreg 0x18,139
        nextreg 0x18,32
        nextreg 0x18,191
        nextreg 0x43,0x10       ; Layer 2 first palette, auto-increment
        nextreg 0x40,0
        push hl
        push bc
        ld hl,l2_pal
        ld b,16
.pal:   ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pal
        pop bc
        pop hl
        IFDEF L2_SPRITES
        call spr_setup
        ENDIF
        ret

; ---- ISR wrapper: BE26 replaces PUSH IX / PUSH IY / PUSH HL -------------------
irq_in: push ix
        push iy
        push hl
        nextreg 0x50,0xFF       ; the noise effect reads ROM bytes
        nextreg 7,0
        jp 0xBE2B
; BE52 replaces POP AF / EX AF,AF' / POP HL.
irq_out:
        call l2_half
        IFDEF L2_GLIDE
        ld hl,hk_fr
        inc (hl)
        jr nz,.fr
        dec (hl)
.fr:
        ENDIF
        IFDEF L2_GLIDE
        call glide_irq
        ENDIF
        ld a,(cur_mmu0)
        nextreg 0x50,a
        ld a,(run_fast)
        nextreg 7,a
        pop af
        ex af,af'
        pop hl
        jp 0xBE55

; ---- 8F40 replaces DI / LD BC,7FFD: a level's data is unpacked with interrupts off (several
; seconds at 3.5MHz, hidden on tape by the loading screen's logo). Run it at 28MHz; the first
; interrupt after it (EI at 5C4C) puts the speed back (irq_out: run_fast).
unpack_fast:
        nextreg 7,3
        IFDEF L2_SHIP
        call ship_stop          ; bank 7 holds packed data: put it back first
        ENDIF
        di
        ld bc,0x7FFD
        jp 0x8F44

; ---- 863D replaces CALL 73D8: life/level restart, Layer 2 off -----------------
l2_off: L2_OFF
        jp 0x73D8
; 8BE8 replaces LD HL,5800: continue screen. FE03 replaces CALL 73C2: title
; and between-level screens. Both clear the ULA; Layer 2 must not stay over them.
l2_off_continue:
        L2_OFF
        IFDEF L2_SPRITES
        call spr_start          ; the continue screen's logo as sprites, as on the title
        ENDIF
        ld hl,0x5800
        jp 0x8BEB
l2_off_title:
        L2_OFF
        IFDEF L2_SPRITES
        call spr_start          ; title figures (logo, TM) as sprites too; Layer 2 stays off
        ENDIF
        xor a                   ; 7A8B: the game's start-up Kempston test (73EC),
        ld (0x7A8B),a           ; "absent" in the snapshot. Port 1F is real here.
        ; L2_NOTAPE builds patch the prompts out of FE03 itself (l2scroll.py
        ; NOTAPE): its level load pages 7FFD, which maps ROM over this hook page,
        ; so the load must return into the game's own code.
        call 0x73C2
        jp 0xFE06

; 92E8 replaces LD DE,71C9: game over, high-score check and name entry.
l2_off_scores:
        L2_OFF
        ld de,0x71C9
        jp 0x92EB

        IFDEF L2_NOTAPE
; Full build start: keep the R-TYPE technical specification (the snapshot's
; screen) up for five seconds or until a key or fire, then let it go.
spec_hold:
        push af
        push bc
        push de
        ld e,250
.f:     call .frame
        IFDEF L2_GLIDE
        ld a,e                  ; after 2 seconds: the upscaled screen (showpiece.py)
        cp 150
        jr nz,.nr
        ld a,9
        call g_call
.nr:
        ENDIF
        xor a
        in a,(0xFE)
        cpl
        and 0x1F
        jr nz,.key
        in a,(0x1F)
        inc a
        jr z,.n                 ; FF: no Kempston interface answering
        dec a
        and 0x1F
        jr nz,.key
.n:     dec e
        jr nz,.f
        jr .out
.key:   call .frame             ; wait for release so the game does not see it
        xor a
        in a,(0xFE)
        cpl
        and 0x1F
        jr nz,.key
        in a,(0x1F)
        inc a
        jr z,.out
        dec a
        and 0x1F
        jr nz,.key
.out:
        IFDEF L2_GLIDE
        ld a,12
        call g_call
        ENDIF
        pop de
        pop bc
        pop af
        ret
.frame: ld bc,0x243B            ; one frame: wait for line 192, then for line 0
.w1:    ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        dec b
        cp 192
        jr nz,.w1
.w2:    ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        dec b
        cp 1
        jr nz,.w2
        ret
        ENDIF

; ---- 8842 replaces LD IX,8080: one pixel per scrolling copier call ------------
l2_scroll:
        IFNDEF L2_NOLAZY
        ld a,(l2_ready)
        or a
        call z,l2_convert       ; test builds started from a mid-level snapshot
        ENDIF
        ld a,(run_fast)         ; outside play nothing scrolls: no need to wait for the raster
        or a
        call nz,l2_sync
        ld a,(0x7A8E)
        or a
        jr nz,.no
        ld hl,(l2_s)            ; one pixel on: first half a pixel (screen B), the rest in 2 frames
        inc hl
        call wrap320
        ld (l2_s),hl
        call l2_xreg
        nextreg 0x12,L2B_BANK
        ld a,2
        ld (l2_hs),a
.no:
        IFDEF L2_SPRITES
        IFDEF L2_GLIDE
        call glide_publish
        ELSE
        call spr_publish
        ENDIF
        ENDIF
        ld ix,0x8080
        jp 0x8846

; Scroll and sprites change together while the raster is below the play area
; (video line 160 or later). A copier call normally starts just after the frame
; interrupt, so this only waits after an update that overran.
l2_sync:
        ld bc,0x243B
.w:     ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        and 1
        ret nz
        ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        dec b
        cp 160
        jr c,.w
        ret

; ---- 89C3 replaces LD HL,5E00: the new column goes to Layer 2 -----------------
; Layer 2 is 640x256 x 4bpp (one byte = one Spectrum pixel, two half pixels), column-major:
; byte column c (0..319) of a screen is page c/32, offset (c%32)*256 + row. Screen A shows the
; scenery as drawn; screen B the same shifted right by half a pixel (each byte's left half is the
; pixel to its left). The scroll register moves whole pixels; showing B right after a step and A two
; frames later gives half-pixel steps (l2_scroll, l2_half). Play row y is Layer 2 row y+32 and screen
; x is column x+32 (the layer covers the border).
l2_stage:
        ld a,0x2C               ; INC L: staging bytes are consecutive
        ld (put_cell.step),a
        ld hl,(l2_s)
        ld de,280               ; hidden screen column 31: 32 + 248
        add hl,de
        call wrap320
        ld (pc_x),hl
        ld hl,0x5E00
        ld b,0
.row:   push bc
        push hl
        ld a,l
        add a,8
        ld l,a
        ld a,(hl)               ; staged attribute; bit 7 = scenery
        pop hl
        push hl
        bit 7,a
        ld e,8                  ; scenery: black paper opaque
        jr nz,.bg
        ld hl,zero8             ; not scenery: clear the Layer 2 cell
        xor a
        ld e,0
.bg:    push af
        ld a,e
        ld (pc_blk),a
        pop af
        call put_cell
        pop hl
        pop bc
        ld de,9
        add hl,de
        inc b
        ld a,b
        cp 20
        jr nz,.row
        ld hl,0x5E00
        jp 0x89C6

; HL mod 320 (HL < 640)
wrap320:
        push de
        ld de,320
        or a
        sbc hl,de
        jr nc,.ok
        add hl,de
.ok:    pop de
        ret

; ---- 8734 replaces CALL FEEB: move the freshly drawn scenery to Layer 2 -------
l2_init:
        ld a,3                  ; 28MHz for the whole level start: the interrupt restores run_fast,
        ld (run_fast),a         ; which was still 0 here (title), so the draws ran at 3.5MHz
        nextreg 7,3
        call 0xFEEB
l2_convert:
        push af
        push bc
        push de
        push hl
        nextreg 0x69,0
        nextreg 7,3
        ld a,L2A_PAGE           ; both screens transparent (index 0)
.fill:  ld (cur_mmu0),a
        nextreg 0x50,a
        ld hl,clr_prog          ; DMA fill of the page from a fixed zero byte (LDIR took 29 frames
        ld bc,(clr_end-clr_prog)*256+0x6B ; for the 160K at 28MHz)
        otir
        inc a
        cp L2B_PAGE+10
        jr nz,.fill
        ld a,0xFF
        ld (cur_mmu0),a
        nextreg 0x50,0xFF
        ld hl,0
        ld (l2_s),hl
        call l2_xreg
        xor a
        ld (l2_hs),a
        nextreg 0x12,L2A_BANK
        ld a,0x24               ; INC H: down a ULA character cell
        ld (put_cell.step),a
        ld a,8                  ; scenery black paper is opaque black (index 8)
        ld (pc_blk),a
        ld b,0
.row:   ld c,0
        push bc                 ; the row starts with nothing to its left
        ld a,b
        add a,a
        add a,a
        add a,a
        ld hl,pc_lp
        add hl,a
        ld b,8
.z:     ld (hl),0
        inc hl
        djnz .z
        pop bc
.col:   ld l,c                  ; Layer 2 column: 32 + 8 * col
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (pc_x),hl
        ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,l
        or c
        ld l,a                  ; HL = row*32+col
        push hl
        ld de,0x7E00
        add hl,de
        ld a,(hl)
        pop hl
        inc a
        jr nz,.sky              ; only owner FF is scenery
        push bc
        ld de,0x7800
        add hl,de
        ld a,(hl)
        push af
        ld a,b
        and 0x18
        or 0x40
        ld h,a
        ld a,b
        and 7
        rrca
        rrca
        rrca
        or c
        ld l,a                  ; HL = ULA cell
        pop af
        call put_cell
        pop bc
        jr .next
.sky:   ld a,c                  ; sky fast path: both screens are already clear, so only a sky cell
        or a                    ; right of scenery is drawn (its screen B first byte carries the half
        jr z,.next              ; pixel of the scenery to its left, else right edges shimmer). That
        dec hl                  ; cell also zeroes the carry, so the skipped cells after it need none.
        ld de,0x7E00            ; Level 1: 533 of 543 sky cells skipped.
        add hl,de
        ld a,(hl)
        inc a
        jr nz,.next
        push bc
        ld a,0x2C               ; INC L: zero8 is consecutive bytes
        ld (put_cell.step),a
        xor a
        ld (pc_blk),a
        ld hl,zero8
        call put_cell
        ld a,0x24
        ld (put_cell.step),a
        ld a,8
        ld (pc_blk),a
        pop bc
.next:  inc c
        ld a,c
        cp 32
        jr nz,.col
        inc b
        ld a,b
        cp 20
        jp nz,.row
        IFNDEF L2_HIDE
        nextreg 0x69,0x80
        ENDIF
        ld a,3                  ; play runs at 28MHz (the ISR stays 3.5MHz)
        ld (run_fast),a
        nextreg 7,3
        ld a,1
        ld (l2_ready),a
        IFDEF L2_SPRITES
        call spr_start
        ENDIF
        pop hl
        pop de
        pop bc
        pop af
        ret

; Layer 2 X scroll = l2_s (0..319)
l2_xreg:
        ld a,(l2_s)
        nextreg 0x16,a
        ld a,(l2_s+1)
        and 1
        nextreg 0x71,a
        ret

; From the interrupt: two frames after a step, back from the half-pixel screen to the whole one.
l2_half:
        ld a,(l2_hs)
        or a
        ret z
        dec a
        ld (l2_hs),a
        ret nz
        nextreg 0x12,L2A_BANK
        ret

; ---- one 8x8 cell: HL = source bytes (zeroed), A = attribute, B = row, pc_x = column --------
; Writes the cell to both screens. pc_lp holds, per play row, the colour index of the pixel to
; the left of the column being drawn (the previous column), for screen B's left half pixel.
put_cell:
        push hl
        ld e,a
        ld a,b
        ld (pc_row),a
        ld a,e
        and 7
        jr nz,.ik
        ld a,8                  ; black ink: opaque black
.ik:    ld d,a
        ld a,e
        and 0x40
        jr z,.ib
        ld a,d
        cp 8
        jr z,.ib
        add a,8                 ; bright
        ld d,a
.ib:    ld a,d
        ld (pc_ink),a
        ld a,e
        rrca
        rrca
        rrca
        and 7
        jr z,.blk
        ld d,a
        ld a,e
        and 0x40
        ld a,d
        jr z,.pp
        add a,8
        jr .pp
.blk:   ld a,(pc_blk)
.pp:    ld (pc_pap),a
        ld a,e
        or 0x80
        ld (pc_key),a           ; key: the attribute as stored with the scenery bit (raw level data)
        pop hl
        ld de,pc_src            ; the 8 source bytes (zeroed in the ULA)
        ld b,8
.cp:    ld a,(hl)
        ld (de),a
        IFNDEF L2_KEEP_ULA
        ld (hl),0
        ENDIF
        inc de
.step:  inc h                   ; INC H (ULA cell) or INC L (staging): set by the caller
        djnz .cp
        call mask_find          ; a scenery cell's see-through pixels (none for a cleared cell)
        ld a,(pc_row)
        add a,a
        add a,a
        add a,a
        ld (pc_y),a             ; play row of the cell's top line
        IFDEF L2_SHIP
        ld hl,pc_paint
        ld (pc_pp),hl
        ENDIF
        ld c,0x80               ; pixel mask, leftmost first
        ld hl,(pc_x)
        ld (pc_c),hl
.colm:  ld de,pc_idx            ; this pixel column's 8 colour indices
        ld hl,pc_src
        ld b,8
        IFDEF L2_SHIP
        ld ix,(pc_pp)           ; painted scenery (r_type_scenery.py): 1-15 a colour, 80 see-through
        ENDIF
.ix:
        IFDEF L2_SHIP
        ld a,(ix+0)
        inc ix
        or a
        jr z,.dflt
        jp p,.st
        xor a
        jr .st
.dflt:
        ENDIF
        ld a,(hl)
        and c
        ld a,(pc_ink)
        jr nz,.ok
        ld a,(pc_pap)
.ok:    cp 8                    ; black: see-through where its mask bit is set
        jr nz,.st
        push hl
        ld a,l
        add a,8                 ; pc_mask follows pc_src (same 256-byte page)
        ld l,a
        ld a,(hl)
        and c
        pop hl
        ld a,8
        jr z,.st
        IFDEF L2_EDGE_DEBUG
        ld a,10                 ; debug: see-through scenery pixels in bright red
        ELSE
        xor a
        ENDIF
.st:    ld (de),a
        inc hl
        inc de
        djnz .ix
        IFDEF L2_SHIP
        ld (pc_pp),ix
        ENDIF
        ld hl,(pc_c)            ; page and offset of this column
        ld a,l
        and 31
        ld d,a
        ld a,(pc_y)
        add a,32
        ld e,a                  ; DE = offset in the page
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h                  ; column / 32
        push af
        add a,L2A_PAGE
        ld (cur_mmu0),a
        nextreg 0x50,a
        push de
        ld hl,pc_idx            ; screen A: both halves the pixel's colour
        ld b,8
.wa:    ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        or (hl)
        ld (de),a
        inc hl
        inc e
        djnz .wa
        pop de
        pop af
        add a,L2B_PAGE
        ld (cur_mmu0),a
        nextreg 0x50,a
        push bc
        ld a,(pc_y)
        ld hl,pc_lp
        add hl,a
        push hl
        pop ix                  ; IX = left neighbours for these 8 rows
        ld hl,pc_idx            ; screen B: left half = the pixel to the left
        ld b,8
.wb:    ld a,(ix+0)
        rlca
        rlca
        rlca
        rlca
        or (hl)
        ld (de),a
        ld a,(hl)
        ld (ix+0),a
        inc ix
        inc hl
        inc e
        djnz .wb
        pop bc
        ld hl,(pc_c)            ; next column (wraps at 320)
        inc hl
        call wrap320
        ld (pc_c),hl
        srl c
        jp nc,.colm
        ld a,0xFF
        ld (cur_mmu0),a
        nextreg 0x50,0xFF
        ret

; RRRGGGBB of the Layer 2 palette: 0 = transparent (TRANSP), 1-7 colours, 8 black, 9-15 bright
; pc_key (attribute | 80, then pc_src) -> pc_mask: binary search of this level's sorted keys (page
; MASK_PAGE0 + 2*(level-1): count, then 9-byte keys), masks in the next page (8 bytes each). Returns
; with Z set (found or not: the mask is zero when the cell is not listed).
        IFDEF L2_SHIP
mask_find:                      ; ship.asm scn_find: also the cell's paint (pc_paint)
        ld a,9
        jp s_call
        ELSE
mask_find:
        push bc
        push de
        push hl
        ld hl,pc_mask
        ld b,8
.z:     ld (hl),0
        inc hl
        djnz .z
        ld a,(pc_blk)
        cp 8
        jp nz,.out              ; not scenery
        ld a,(0x719C)
        sub '1'
        cp 8
        jp nc,.out
        add a,a
        add a,MASK_PAGE0
        ld (mf_pg),a
        ld (cur_mmu0),a
        nextreg 0x50,a
        ld hl,(0)
        ld (mf_n),hl
        ld hl,0
        ld (mf_lo),hl
.bs:    ld hl,(mf_n)
        ld a,h
        or l
        jp z,.miss
        srl h
        rr l
        ld (mf_h),hl
        ld de,(mf_lo)
        add hl,de
        ld (mf_mid),hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        inc hl
        inc hl                  ; 2 + 9 * mid
        ld de,pc_key
        ld b,9
.cmp:   ld a,(de)
        cp (hl)
        jp nz,.ne
        inc hl
        inc de
        djnz .cmp
        ld a,(mf_pg)            ; found: its mask
        inc a
        ld (cur_mmu0),a
        nextreg 0x50,a
        ld hl,(mf_mid)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,pc_mask
        ld bc,8
        ldir
        jr .miss
.ne:    jr c,.left              ; key below this entry
        ld hl,(mf_mid)
        inc hl
        ld (mf_lo),hl
        ld hl,(mf_n)
        ld de,(mf_h)
        or a
        sbc hl,de
        dec hl
        ld (mf_n),hl
        jr .bs
.left:  ld hl,(mf_h)
        ld (mf_n),hl
        jr .bs
.miss:  ld a,0xFF
        ld (cur_mmu0),a
        nextreg 0x50,0xFF
.out:   pop hl
        pop de
        pop bc
        xor a
        ret
mf_pg:  db 0
mf_n:   dw 0
mf_lo:  dw 0
mf_h:   dw 0
mf_mid: dw 0
        ENDIF
        IFDEF L2_SHIP
pc_paint EQU 0x3D80             ; 64 bytes after the flag map (ship.asm scn_find)
pc_pp:  dw 0
        ENDIF

; RRRGGGBB for the eight normal then the eight bright Spectrum colours (sprite palette).
col_tab: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
l2_pal: db TRANSP,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
l2_s:   dw 0
l2_hs:  db 0
run_fast: db 0
; Black paper of a scenery cell is opaque (8): in the original a figure never draws into a cell the
; scenery owns (8EC2), so scenery hides any figure behind it. Cleared cells are transparent (0).
pc_blk: db 0
pc_ink: db 0
pc_pap: db 0
pc_row: db 0
pc_y:   db 0
pc_x:   dw 0
pc_c:   dw 0
pc_idx: ds 8
pc_lp:  ds 160
l2_ready: db 0
cur_mmu0: db 0xFF
        ALIGN 32
pc_key: db 0                    ; attribute | 80, then the cell's 8 bytes: the mask key
pc_src: ds 8
pc_mask: ds 8                   ; see-through pixels of the cell (bit 7 = leftmost)
        ALIGN 16
zero8:  ds 8
clr_prog: db 0x83,0xC3,0x7D     ; disable, reset; WR0 A->B, A address and length follow
        dw zero8,0x2000
        db 0x24,0x10,0xAD       ; A memory fixed; B memory increment; continuous, B address follows
        dw 0
        db 0x82,0xCF,0x87       ; stop at end; load; enable
clr_end:
        IFDEF L2_SPRITES
        INCLUDE "r_type_sprites.asm"
        ENDIF
        ASSERT $ < 0x3E00
        IFNDEF L2_SPRITES
        SAVEBIN "l2scroll_code.bin",hook_setup,$-hook_setup
        ENDIF
