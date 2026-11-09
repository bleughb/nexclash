; That Sinking Feeling (Sunteam, 2017, 48K-128K), an Arcade Game Designer game: clash removal, and Enhanced colours as a menu option.
;
; The game XORs its figures and objects straight onto the ULA and never writes an attribute for one, so a figure takes the ink of
; the cell it is in. Here the ULA stays the original's, every byte. Each figure and object is a hardware sprite over it, in the
; position the game plots it: the ink they have in open water in the default look, the Spec256 set's colours in Enhanced. Figure plots run at 28 MHz, which
; pays for the hook; the game's own frame wait keeps the pace in play.
;
; Enhanced adds a Layer 2 under the sprites: the set's backdrop for the room, chosen by the set's own rules on the room number, with
; every block and character the game prints drawn on it from a table of the set's pixels. A value FF pixel goes transparent (the ULA
; shows through). A room is drawn at 28 MHz, between h_room and h_ra / h_rb, as Layer 2 costs more than the original's cell. Dots
; (AGD's particles) toggle a pixel on Layer 2.
;
; Slots inside a hook: 1 this page; 4 and 5 are mapped only around Layer 2's work and never around the game's code. The hooks stay on
; the game's stack. The ISR pages bank 4 at C000 by port 7FFD, which puts the ROM back in slot 1 and sets slots 6 and 7, and calls the
; ROM's IM 1 handler; it never touches 4 or 5. So its entry keeps slot 1's page in NextREG 7F and its second OUT's next instruction puts
; it back: an interrupt can land in any hook.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 311
V_SPEED EQU 0x3E30
ISR_AT EQU 0x6060
ISR_TAIL EQU 0x2C                ; POP AF after the second OUT
ISR_KW EQU -21
ISR_KX EQU -6
V_R0 EQU 0x3E35
V_ENH EQU 0x3E3C                ; 1 in Enhanced
V_BG EQU 0x3E3D                 ; the backdrop's first page
V_BATCH EQU 0x3E3E              ; a room is being drawn: Layer 2 holds the bare backdrop
V_ROOMSP EQU 0x3E3F             ; the game's clock while a room runs at 28 MHz
V_INK EQU 0x3E40
V_TMP EQU 0x3E41
V_WAIT EQU 0x3E43
W_EMPTY EQU 32
W_ROOM EQU 6800
V_OBJ EQU 0x3E48                ; ten objects: 1 while shown
V_PT EQU 0x3E60                 ; fifty dots: flag, the pixel it covers
V_SH EQU 0x3EC4                 ; twelve figures: pattern or FF, y, x, spare
L2_PAGE EQU 32
BG_PAGE EQU 38                  ; 7 backdrops of 6 pages
FONT_T EQU 80                   ; 64 bytes a glyph
BLOCK_T EQU 81
BLOCK_EMPTY EQU 0x1F00          ; offset in BLOCK_T: 1 when a block's 64 pixels are all 0
SP_PAGE EQU 82
N_FIGS EQU 12
FIGS EQU 0x8F2E
FIRST_OBJ_SP EQU 12
FIRST_OBJ_PAT EQU 24
FIRST_ALT_PAT EQU 34
OBJ_STEP EQU 38
FONT_BASE EQU 0x7900
BLOCK_BASE EQU 0x9C62
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; fig_new: the figure at IX, its new place (IX+6 sprite, +7 frame, +8 y, +9 x). AF, BC, DE, HL lost.
fig_new:
        ld a,(ix+6)
        call 0x8E38
        ld a,(hl)
        add a,(ix+7)
        cp FIRST_OBJ_PAT
        ld c,a
        jr nc,fig_off
        call fig_slot
        ld a,(ix+9)
        and 0xFE
        ld e,a
        ld a,(ix+8)
        ld d,a
        ld a,c
        cp 11                   ; the jellyfish: the set paints its tentacles another colour at odd shifts
        jp c,sp_show
        cp 13
        jp nc,sp_show
        bit 1,e
        jp z,sp_show
        add a,FIRST_ALT_PAT-11
        jp sp_show
fig_off:
        call fig_slot
        jp sp_hide
; sh_set: B the sprite, C the pattern or FF for none, D y, E x: the figures' sprites in V_SH, for the swap. HL kept, AF lost.
sh_set: ld a,b
        cp N_FIGS
        ret nc
        push hl
        add a,a
        add a,a
        ld hl,V_SH
        add a,l
        ld l,a
        ld (hl),c
        inc l
        ld (hl),d
        inc l
        ld (hl),e
        pop hl
        ret
; fig_swap: the game has swapped the records at IX and IX+15 (8B23, it keeps them in y order): their sprites follow. Run before the swap.
fig_swap:
        call fig_slot
        ld a,b
        add a,a
        add a,a
        ld hl,V_SH
        add a,l
        ld l,a                  ; HL this sprite's shadow, B its number
        push bc
        ld a,l
        add a,4
        ld e,a
        ld d,h                  ; DE the next one's
        ld b,3
.x:     ld a,(de)
        ld c,(hl)
        ld (hl),a
        ld a,c
        ld (de),a
        inc l
        inc e
        djnz .x
        ld a,l
        sub 3
        ld l,a
        pop bc
        call .one
        inc b
        ; and the next
        inc l
.one:   ld a,(hl)
        cp 0xFF
        jr nz,.on
        push hl
        push bc
        call sp_hide_q
        pop bc
        pop hl
        inc l
        inc l
        inc l
        ret
.on:    ld c,a
        inc l
        ld d,(hl)
        inc l
        ld e,(hl)
        inc l
        push hl
        push bc
        ld a,c
        call sp_show_q
        pop bc
        pop hl
        ret
; fig_slot: B = the sprite of the figure at IX.
fig_slot:
        push ix
        pop hl
        ld de,FIGS
        or a
        sbc hl,de
        ld b,0
        ld a,l
.d:     cp 15
        ret c
        sub 15
        inc b
        jr .d

; sp_show: B the sprite, A the pattern, D y, E x. sp_hide: B the sprite. AF, BC lost, DE kept.
sp_show:
        ld c,a
        call sh_set
        ld a,c
sp_show_q:
        ld c,a
        ld a,b
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld a,e
        add a,32
        out (0x57),a            ; X low
        ld a,d
        add a,32
        out (0x57),a            ; Y low
        ld a,e
        add a,32
        ld a,0
        adc a,a
        out (0x57),a            ; palette 0, X high
        ld a,c
        or 0x80
        out (0x57),a            ; visible, 8-bit pattern
        ret
sp_hide:
        ld c,0xFF
        call sh_set
sp_hide_q:
        ld a,b
        ld bc,0x303B
        out (c),a
        xor a
        out (0x57),a
        out (0x57),a
        out (0x57),a
        out (0x57),a
        ret

; room_wait: the room's drawing at 28 MHz is quicker than the original's 685,000 T by 833 T an empty block less 177,000 T (roomt.py,
; roomn.py): that, in steps of 26 T at the game's clock, so an interrupt takes its share as it did. AF, HL, DE lost.
room_wait:
        ld a,(V_ROOMSP)
        nextreg 0x07,a
        ld hl,(V_WAIT)
        ld de,W_ROOM
        or a
        sbc hl,de
        jr c,.n
        jr z,.n
.s:     dec hl
        ld a,h
        or l
        jr nz,.s
.n:     ld hl,0
        ld (V_WAIT),hl
        ret

; all_off: every sprite hidden, objects and dots forgotten. AF, BC, DE, HL lost.
all_off:
        ld b,22
.l:     dec b
        push bc
        call sp_hide
        pop bc
        inc b
        djnz .l
        ld hl,V_OBJ
        ld de,V_OBJ + 1
        ld bc,123
        ld (hl),0
        ldir
        ret

; pick_bg: the set's rules on the room number: a rule picks a backdrop, no rule keeps the one there is. AF, HL lost.
pick_bg:
        ld a,(0x7D1B)
        ld hl,.t
.l:     cp (hl)
        inc hl
        jr z,.f
        inc hl
        bit 7,(hl)
        jr z,.l
        ret
.f:     ld a,(hl)
        ld (V_BG),a
        ret
.t:     defb 0x19,BG_PAGE + 0 * 6,0x00,BG_PAGE + 6 * 6,0x04,BG_PAGE + 1 * 6,0x08,BG_PAGE + 2 * 6
        defb 0x0C,BG_PAGE + 3 * 6,0x10,BG_PAGE + 4 * 6,0x15,BG_PAGE + 5 * 6,0x17,BG_PAGE + 0 * 6,0x80

; l2_lines: B character rows from the top: Layer 2 from the backdrop. AF, BC, DE, HL lost.
l2_lines:
        ld c,0
.r:     push bc
        ld a,c
        rrca
        rrca
        and 7
        ld b,a
        ld a,(V_BG)
        add a,b
        nextreg 0x54,a
        ld a,b
        add a,L2_PAGE
        nextreg 0x55,a
        ld a,c
        and 3
        add a,a
        add a,a
        add a,a
        ld d,a
        or 0x80
        ld h,a
        ld l,0
        ld a,d
        or 0xA0
        ld d,a
        ld e,0
        ld bc,0x0800
        ldir
        pop bc
        inc c
        djnz .r
        nextreg 0x54,4
        nextreg 0x55,5
        ret

obj_body:
        ld de,(0x7D4D)
        or a
        sbc hl,de
        ld b,0
.d:     ld a,h
        or a
        jr nz,.s
        ld a,l
        cp OBJ_STEP
        jr c,.g
.s:     ld de,OBJ_STEP
        or a
        sbc hl,de
        inc b
        jr .d
.g:     ld a,b
        cp 10
        ret nc
        ld hl,V_OBJ
        ld e,b
        ld d,0
        add hl,de
        ld a,(hl)
        xor 1
        ld (hl),a
        jr z,.off
        ld a,(0x7D32)
        and 0xFE
        ld e,a
        ld a,(0x7D31)
        ld d,a
        ld a,b
        add a,FIRST_OBJ_PAT
        push af
        ld a,b
        add a,FIRST_OBJ_SP
        ld b,a
        pop af
        call sp_show
        ret
.off:   ld a,b
        add a,FIRST_OBJ_SP
        ld b,a
        call sp_hide
        ret

cell_body:
        ld a,(0x7D31)
        ld d,a                  ; the character row
        ld a,(0x7D32)
        ld e,a                  ; the column
        ld a,h
        cp 0x90
        jr nc,.block
        ld bc,FONT_BASE
        or a
        sbc hl,bc
        ld a,(0x5C8D)
        jr .go
.block: ld bc,BLOCK_BASE
        or a
        sbc hl,bc
        ; the block's own attribute is on the screen by now (8755)
        push hl
        ld l,d
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,e
        and 31
        add a,l
        ld l,a
        ld a,h
        add a,0x58
        ld h,a
        ld a,(hl)
        pop hl
.go:    and 7
        ld (V_INK),a
        add hl,hl
        add hl,hl
        add hl,hl               ; 64 x the glyph
        ld a,(V_BATCH)
        or a
        jr z,.back
        ; a room: Layer 2 is bare backdrop, and an empty block needs nothing
        ld a,b
        cp BLOCK_BASE >> 8
        jp nz,.front
        push hl
        add hl,hl
        add hl,hl               ; H = the glyph
        ld a,h
        add a,BLOCK_EMPTY & 255
        ld l,a
        ld h,0x80 + (BLOCK_EMPTY >> 8)
        nextreg 0x54,BLOCK_T
        ld a,(hl)
        pop hl
        or a
        jp nz,.front
        ld hl,(V_WAIT)          ; a room's wait, below: what an empty block no longer costs
        ld de,W_EMPTY
        add hl,de
        ld (V_WAIT),hl
        jp .done
.back:  ; the backdrop under this cell
        push hl
        push bc
        push de
        ld a,d
        rrca
        rrca
        and 7
        ld b,a
        ld a,(V_BG)
        add a,b
        nextreg 0x54,a
        ld a,b
        add a,L2_PAGE
        nextreg 0x55,a
        ld a,e
        add a,a
        add a,a
        add a,a
        ld b,a                  ; x
        ld c,255                ; LDI leaves B alone: fewer than 256 of them
        ld a,d
        and 3
        add a,a
        add a,a
        add a,a
        or 0x80                 ; the row's high byte in slot 4
        REPT 8
        ld h,a
        ld l,b
        ld e,b
        add a,0x20
        ld d,a
        sub 0x20
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        inc a
        ENDR
        pop de
        pop bc
        pop hl
.front: ; slot 4 the glyph's table, slot 5 Layer 2
        ld a,b
        cp BLOCK_BASE >> 8
        ld a,BLOCK_T
        jr z,.t0
        ld a,FONT_T
.t0:    nextreg 0x54,a
        ld a,d
        rrca
        rrca
        and 7
        add a,L2_PAGE
        nextreg 0x55,a
        ld a,h
        and 0x1F
        or 0x80
        ld h,a
        ld a,d
        and 3
        add a,a
        add a,a
        add a,a
        or 0xA0
        ld d,a
        ld (V_TMP),a
        ld a,e
        add a,a
        add a,a
        add a,a
        ld e,a
        ld (V_TMP + 1),a
        ld c,8
.row:   ld b,8
.px:    ld a,(hl)
        inc hl
        or a
        jr z,.nx
        inc a
        jr nz,.put
        ; FF: the attribute's, unless the ink is not white and there is backdrop here
        ld a,(V_INK)
        cp 7
        jr z,.ff
        ld a,(de)
        or a
        jr nz,.nx
.ff:    ld a,0xFF
        ld (de),a
        jr .nx
.put:   dec a
        ld (de),a
.nx:    inc de
        djnz .px
        ld a,(V_TMP + 1)
        ld e,a
        ld a,(V_TMP)
        inc a
        ld (V_TMP),a
        ld d,a
        dec c
        jr nz,.row
.done:  nextreg 0x54,4
        nextreg 0x55,5
        ret

dot_body:
        ld a,(ix+3)
        cp 0xC0
        ret nc
        ld a,(ix+0)
        or a
        ret z                   ; AGD's laser: this game has none
        ; which dot
        push ix
        pop hl
        ld de,(0x7D53)
        or a
        sbc hl,de
        ld de,6
        ld b,0
.d:     ld a,h
        or a
        jr nz,.s
        ld a,l
        cp 6
        jr c,.w
.s:     sbc hl,de
        inc b
        jr .d
.w:     ld l,b
        ld h,0
        add hl,hl
        ld de,V_PT
        add hl,de
        ex de,hl                ; DE the dot's two bytes
        ; the pixel, y (IX+3), x (IX+5)
        ld a,(ix+3)
        ld l,a
        rlca
        rlca
        rlca
        and 7
        add a,L2_PAGE
        nextreg 0x55,a
        ld a,l
        and 31
        or 0xA0
        ld h,a
        ld a,(ix+5)
        ld l,a
        ld a,(de)
        xor 1
        ld (de),a
        inc de
        jr z,.back
        ld a,(hl)
        ld (de),a
        ld (hl),0xFF
        jr .e
.back:  ld a,(de)
        ld (hl),a
.e:     nextreg 0x55,5
        ret

rom_end:
        ASSERT $ < 0x3880
        SAVEBIN "tsf_rom.bin",rom_start,$-rom_start

; ---- the entries and exits: in the hidden ROM's free space and this page at one address (the game's ROM calls run the calculator at 2Dxx) --
        ORG 0x3880
rom2_start:
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ENDM
        MACRO LEAVE_R
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
        MACRO COPY_BODY body
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call body
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ENDM
        MACRO R_DONE
        ld a,-18
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM

; ---- a figure's old place off and its new place on: the original's 8C6C ------------------------------------------------------
h_both:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call fig_new
        COPY_BODY 0x8C6C
        R_DONE
        LEAVE_R
        ret
; ---- the game swaps two figure records to keep them in y order: the original's 8B23 (8B13, 8B1E) -------------------------
h_swap:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call fig_swap
        COPY_BODY 0x8B23
        R_DONE
        LEAVE_R
        ret
; ---- one plot at the old place, 8C57 -------------------------------------------------------------------------------------------
h_old:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call fig_off
        COPY_BODY 0x8C57
        R_DONE
        LEAVE_R
        ret
; ---- one plot at the new place, 8C66 -------------------------------------------------------------------------------------------
h_new:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call fig_new
        COPY_BODY 0x8C66
        R_DONE
        LEAVE_R
        ret

; ---- an object plot (87DB, JP from 85C6 and 85E8): HL its graphic; (7D31) y, (7D32) x ----------------------------------------------
h_obj:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call obj_body
        ld a,-9
        call hlib_r_set
        LEAVE_R
        jp 0x87DB

; ---- CLS (CALL 0DAF, 791F): every sprite off; Layer 2 back to the backdrop. CALL here, JP there ------------------------------------
h_cls:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call all_off
        ld a,(V_ENH)
        or a
        jr z,.n
        call pick_bg
        ld b,24
        call l2_lines
.n:     ld a,-9
        call hlib_r_set
        LEAVE_R
        jp 0x0DAF

; ---- a room (CALL 884D, 7F8F and 8387): sprites off, then in Enhanced the backdrop, and the room's drawing at 28 MHz until h_ra / h_rb ---
h_room:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call all_off
        ld a,(V_ENH)
        or a
        jr z,.n
        call pick_bg
        ld b,23
        call l2_lines
        ld a,1
        ld (V_BATCH),a
        ld a,(V_SPEED)
        ld (V_ROOMSP),a
        ld a,-9
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x884D
.n:     ld a,-9
        call hlib_r_set
        LEAVE_R
        jp 0x884D
; the room's drawn: CALL 859D at 7F92 and CALL 82EE at 838A. CALL here, JP there.
        MACRO ROOM_END target
        ENTER
        xor a
        ld (V_BATCH),a
        ld a,(V_ROOMSP)
        ld (V_SPEED),a
        call room_wait
        ld a,-9
        call hlib_r_set
        LEAVE_R
        jp target
        ENDM
h_ra:   ROOM_END 0x859D
h_rb:   ROOM_END 0x82EE

; ---- 877F, a block or a character: the original's 8 rows are about to go down. HL the graphic ----------------------------------------
h_cell:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call cell_body
        ld a,-10
        call hlib_r_set
        LEAVE_R
        ld a,(hl)
        ld (de),a
        inc hl
        jp 0x8782

; ---- 81B0, a dot on or off: IX its record. LD A,(IX+3) displaced --------------------------------------------------------------------
h_dot:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call dot_body
        ld a,-10
        call hlib_r_set
        LEAVE_R
        ld a,(ix+3)
        jp 0x81B3

; ---- the ISR, both ends. Runs from either copy of this page; no RAM. ------------------------------------------------------------------
; ISR+0 (DI / PUSH AF / PUSH BC displaced). A, B, C free after them.
isr_w:  di
        push af
        push bc
        ld bc,0x243B
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        nextreg 0x7F,a
        dec b
        ld a,7
        out (c),a
        ld a,r
        ld b,a
        add a,ISR_KW
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld r,a
        pop bc
        pop af
        push af
        push bc
        jp ISR_AT + 3
; after the ISR's second OUT (POP AF / EX AF,AF' / POP IY displaced). Every register is about to be popped.
isr_x:  ld a,r
        push de
        ld d,a
        push bc
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        nextreg 0x51,a
        dec b
        ld a,7
        out (c),a
        ld a,d
        add a,ISR_KX
        and 0x7F
        ld c,a
        ld a,d
        and 0x80
        or c
        ld r,a
        pop bc
        pop de
        pop af
        ex af,af'
        pop iy
        jp ISR_AT + ISR_TAIL + 4
isr_end:
rom2_end:
regblock EQU 0x3CE0
        ASSERT $ <= regblock
        SAVEBIN "tsf_rom2.bin",rom2_start,$-rom2_start
        ORG 0xD000
setup:
        ld hl,pb_copy           ; NEXLOAD uses the printer buffer, and the game reads 5B5C (its copy of 7FFD)
        ld de,0x5B00
        ld bc,256
        ldir
        nextreg 0x70,0
        nextreg 0x14,0xE3
        nextreg 0x4B,0
        nextreg 0x15,1          ; sprites on; sprites, Layer 2, ULA
        nextreg 0x1C,3
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x12,L2_PAGE / 2
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
sp_load:
        nextreg 0x50,SP_PAGE    ; 36 patterns: more than one 8K page holds
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0
        ld d,32
        ld bc,0x005B
.o:     otir
        dec d
        jr nz,.o
        nextreg 0x50,SP_PAGE+1
        ld hl,0
        ld d,4
.p:     otir
        dec d
        jr nz,.p
        nextreg 0x50,255
setup_enh:
        ld a,0
        or a
        ret z
        ld b,0x10
        call .pal
        ld b,0x20
        call .pal
        nextreg 0x43,0
        nextreg 0x69,0x80
        ret
.pal:   ld a,b
        nextreg 0x43,a
        nextreg 0x40,0
        ld hl,e_palette
        ld b,0
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        ret
e_palette:
        defs 512,0
pb_copy:
        defs 256,0
setup_end:
        SAVEBIN "tsf_setup.bin",setup,setup_end-setup
