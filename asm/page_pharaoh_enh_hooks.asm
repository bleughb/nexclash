; Page and the Curse of the Pharaoh, Enhanced: the Spec256 set's colours on a Layer 2, faithfully.
;
; Spec256 runs the game's own plots on eight parallel bit planes, so each pixel holds an 8-bit colour value.
; The game writes tiles with LD and XORs figures and items. Here the Layer 2 holds those same values, and
; the hooks repeat each write on it from tables of the set's colours: a tile overwrites, a figure or item
; XORs value by value. XOR on the value is what the planes do, so a figure comes off cleanly with no mask
; and no redraw, and where it overlaps painted scenery the colours mix exactly as they do on Spec256.
; Value FF means "the attribute's colour" on Spec256: here it is the Layer 2's transparent colour, so the
; ULA underneath shows it, ink or paper, as the renderer does. The ULA stays the original's, every byte,
; except that the game's ULA+ palette is turned back off, as Spec256 ignores those ports.
;
; Interrupts stay on: table pages go in slot 6, Layer 2 pages in slot 7, this page in slot 1. The game's
; own frame wait keeps the pace; its plots run at 28 MHz, which pays for the overlay.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
K_ROOM EQU 24
V_ROOMSPEED EQU 0x3E44
V_TC EQU 0x3E45
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_R0 EQU 0x3E35
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_S EQU 0x3E3F
P_PG EQU 0x3E40
P_L2 EQU 0x3E41
V_T EQU 0x3E42                 ; word: this row's colours in slot 6
R_BUF EQU 0x3E80               ; an item's row: 16 values
L2_BANK EQU 16
PG_FIG EQU 38                  ; 6 pages: the colours of 9050-A627, 8 values a byte
PG_FONT EQU 44                 ; 1 page: 7A00-7AFF
PG_ITEM EQU 45                 ; 3 pages: DB79-E37D
FIG_LO EQU 0x9050
FIG_HI EQU 0xA628
FONT_LO EQU 0x7A00
FONT_HI EQU 0x7B00
ITEM_LO EQU 0xDB79
ITEM_HI EQU 0xE37E
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
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
        ld sp,(V_SP)
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
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM
        MACRO EXIT_TO target
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp target
        ENDM

; ---- a figure: off its old place, on at its new, then the original's 8C63 ----
h_both:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BE0             ; the game's own set-up: DE the graphic, 7D2F / 7D30 the place
        call l2_fig
        call 0x8BCA
        call l2_fig
        COPY_BODY 0x8C63
        R_DONE
        LEAVE_R
        ret
h_old:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BE0
        call l2_fig
        COPY_BODY 0x8C4E
        R_DONE
        LEAVE_R
        ret
h_new:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BCA
        call l2_fig
        COPY_BODY 0x8C5D
        R_DONE
        LEAVE_R
        ret

; ---- a tile or letter (8743): A = its code, 7D2F row, 7D30 column ------------
h_tile:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,(HLIB_V_PACE+10)   ; inside the room's window: its line count must not wrap unseen, so a tick
        or a                    ; every 32 tiles (a tick costs about ten tiles' drawing)
        jr z,.nt
        ld hl,V_TC
        inc (hl)
        ld a,(hl)
        and 31
        call z,hlib_pace_tick
.nt:
        call l2_tile
        COPY_BODY 0x8743
        R_DONE
        LEAVE_R
        ret

; ---- an item (87AB, reached by JP): HL = its 32 bytes, 7D2F y, 7D30 x --------
h_item:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call l2_item
        COPY_BODY 0x87AB
        R_DONE
        LEAVE_R
        ret

; ---- the game turns ULA+ on (7F9B): Spec256 has no ULA+, so it goes off again
h_ula:
        ENTER
        COPY_BODY 0x7F9B
        ld bc,0xBF3B
        ld a,0x40
        out (c),a
        ld b,0xFF
        xor a
        out (c),a
        R_DONE
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- the room is drawn over everything (881D): the overlay shows. The room's tile hooks are 700 entries
; and exits at the game's clock, so the whole draw runs at 28 MHz in a K window, opened here and closed at the
; game's next CALL (h_after). Tile hooks inside latch 28 MHz as their incoming clock and keep it.
h_room:
        ENTER
        HLIB_SPEED_IN_ABC V_ROOMSPEED
        nextreg 0x69,0x80
        call hlib_pace_open
        EXIT_TO 0x881D

; ---- the draw has returned: the K window's wait, and the game's clock back ---
        MACRO AFTER_HOOK target
        ENTER
        ld a,(V_ROOMSPEED)
        ld c,a
        ld a,K_ROOM
        call hlib_pace_waitk
        ld a,(V_ROOMSPEED)
        nextreg 0x07,a
        EXIT_TO target
        ENDM
h_after1:
        AFTER_HOOK 0x8092
h_after2:
        AFTER_HOOK 0x8572

; ---- the ROM clears the screen (0DAF): overlay off and empty. The game over and winning screens stay plain ULA, as the
; set has no colour on them. The menu's text and icons all go through the tile hook, and the set paints its icons, so
; the menu shows the overlay.
h_cls:
        ENTER
        HLIB_SPEED_IN V_SPEED
        nextreg 0x69,0
        call cls_fill
        HLIB_SPEED_OUT V_SPEED
        EXIT_TO 0x0DAF
h_cls_menu:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call cls_fill
        nextreg 0x69,0x80
        HLIB_SPEED_OUT V_SPEED
        EXIT_TO 0x0DAF
cls_fill:
        ld d,L2_BANK*2
        ld e,6
.pg:    ld a,d
        nextreg 0x57,a
        ld hl,0xE000
        ld (hl),0
        push de
        ld de,0xE001
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        nextreg 0x57,1
        ret

; l2_rowpage: A = y -> slot 7 = its Layer 2 page, H = the row in it. AF, C lost.
l2_rowpage:
        ld c,a
        and 31
        or 0xE0
        ld h,a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        add a,L2_BANK*2
        nextreg 0x57,a
        ret

; t_map: HL = byte offset into a table of 8 values a byte, A = its first page ->
; HL = address in slot 6 and slot 6 mapped. BC lost. P_PG = the page.
t_map:  ld b,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,b
        ld (P_PG),a
        nextreg 0x56,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ret

; x_n: A = pixels (0-16): value at (DE) XORs into (HL), both counting on in their low byte.
x_n:    or a
        ret z
        neg
        add a,16
        ld b,a
        add a,a
        add a,a
        add a,b                 ; 5 bytes a pixel
        ld c,a
        ld b,0
        push hl
        ld hl,x_all
        add hl,bc
        ex (sp),hl
        ret
x_all:
        REPT 16
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc e
        inc l
        ENDR
        ret

; l2_fig: DE = the graphic, 7D2F y, 7D30 x: 16 rows of 16 values, XORed. The table holds each figure row's values
; already in screen order (the graphic's two bytes hold the left and right parts in the first byte, the middle in
; the second, so they run s..7, 8..15, 0..s-1), so one straight run does a row.
l2_fig: ex de,hl
        ld de,FIG_LO
        or a
        sbc hl,de
        ld a,PG_FIG
        call t_map
        ex de,hl                ; DE = the values, 16-byte aligned
        ld a,(0x7D2F)
        call l2_rowpage
        ld a,c                  ; y (l2_rowpage leaves it in C)
        rlca
        rlca
        rlca
        and 7
        add a,L2_BANK*2
        ld (P_L2),a
        ld a,(0x7D30)
        and 0xFE
        ld c,a                  ; the first pixel: x & FE
        ld b,16
.row:   ld l,c
        REPT 16
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc e
        inc l
        ENDR
        ld a,e
        or a
        jr nz,.t
        inc d
        ld a,d
        cp 0xE0
        jr nz,.t
        ld d,0xC0
        ld a,(P_PG)
        inc a
        ld (P_PG),a
        nextreg 0x56,a
.t:     inc h
        jr nz,.y
        ld h,0xE0
        ld a,(P_L2)
        inc a
        ld (P_L2),a
        nextreg 0x57,a
.y:     dec b
        jp nz,.row
map_back:
        nextreg 0x56,0
        nextreg 0x57,1
        ret

; l2_tile: 8 rows of 8 values, overwriting. A coloured source through its table, any other: FF for a set bit, else 0.
l2_tile:
        ld hl,7
        add hl,sp
        inc hl
        inc hl                  ; past this call's return address
        ld a,(hl)               ; the game's A
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(0x869B)
        add hl,de               ; the source
        ld a,(0x7D2F)
        add a,a
        add a,a
        add a,a
        ld (P_Y),a
        ld a,(0x7D30)
        and 31
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        ld a,8
        ld (P_ROWS),a
        ld de,FIG_LO
        or a
        sbc hl,de
        jr c,.notfig
        ld de,FIG_HI-FIG_LO
        or a
        sbc hl,de
        add hl,de
        jr nc,.mono2
        ld a,PG_FIG
        jr .tab
.notfig:
        add hl,de               ; back to the source
        ld de,FONT_LO
        or a
        sbc hl,de
        jr c,.mono1
        ld de,FONT_HI-FONT_LO
        or a
        sbc hl,de
        add hl,de
        jr nc,.mono3
        ld a,PG_FONT
.tab:   call t_map           ; HL = the values
        ld a,(P_Y)
        push hl
        call l2_rowpage         ; a tile's 8 rows share a page
        ld d,h
        ld a,(P_X)
        ld e,a
        pop hl
.trow:  ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ld a,e
        or a
        jr nz,.nw
        dec d                   ; column 31: LDI carried into D
.nw:    sub 8
        ld e,a
        inc d
        ld a,d
        and 7                   ; y starts on a multiple of 8
        jr nz,.trow
        jp map_back
.mono1: add hl,de               ; below the font: back to the source
        jr .mono
.mono2: ld de,FIG_LO               ; past the figures: FIG_LO was taken off
        add hl,de
        jr .mono
.mono3: ld de,FONT_LO
        add hl,de
.mono:  ld (V_T),hl
.mrow:  ld a,(P_Y)
        call l2_rowpage
        ld a,(P_X)
        ld l,a
        ld de,(V_T)
        ld a,(de)
        inc de
        ld (V_T),de
        ld c,a
        ld b,8
.mp:    rl c
        sbc a,a                 ; FF for a set bit, 0 for clear
        ld (hl),a
        inc l
        djnz .mp
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jr nz,.mrow
        jp map_back

; l2_item: 16 rows of 16 values XORed at the exact x. Coloured through its table, any other: FF for a set bit.
l2_item:
        ld hl,2
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; the game's HL
        ld (V_T),hl
        ld a,(0x7D2F)
        ld (P_Y),a
        ld a,(0x7D30)
        ld (P_X),a
        ld a,16
        ld (P_ROWS),a
        ld de,ITEM_LO
        or a
        sbc hl,de
        jr c,.mono
        ld de,ITEM_HI-ITEM_LO
        or a
        sbc hl,de
        add hl,de
        jr nc,.mono
        ld a,PG_ITEM
        call t_map
        ld (V_T),hl
.crow:  ld de,R_BUF
        ld hl,(V_T)
        ld b,16
.cp:    ld a,(hl)
        ld (de),a
        inc de
        inc hl
        ld a,h
        cp 0xE0
        jr nz,.cn
        ld h,0xC0
        ld a,(P_PG)
        inc a
        ld (P_PG),a
        nextreg 0x56,a
.cn:    djnz .cp
        ld (V_T),hl
        call .plot
        jr nz,.crow
        jp map_back
.mono:  ld de,R_BUF
        ld hl,(V_T)
        ld a,2
.mb:    push af
        ld c,(hl)
        inc hl
        ld b,8
.mp:    rl c
        sbc a,a
        ld (de),a
        inc de
        djnz .mp
        pop af
        dec a
        jr nz,.mb
        ld (V_T),hl
        call .plot
        jr nz,.mono
        jp map_back
; one row from R_BUF; NZ while rows remain
.plot:  ld a,(P_Y)
        call l2_rowpage
        ld a,(P_X)
        ld l,a
        ld de,R_BUF
        ld a,16
        call x_n
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "ppe_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_BANK
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,0
.lp:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .lp
        nextreg 0x43,0
        ld d,L2_BANK*2
        ld e,6
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        nextreg 0x50,255
        ret
l2_pal:                         ; 512 bytes: the set's palette, appended by the engine
setup_end:
        SAVEBIN "ppe_setup.bin",setup,setup_end-setup
