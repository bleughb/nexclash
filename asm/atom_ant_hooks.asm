; Atom Ant (Hi-Tec, 128K form of the tape): Enhanced colours on a full Layer 2.
;
; The default build has no hooks. Enhanced keeps every game byte and the ULA as they are and
; draws the play window on a double-buffered Layer 2 with the Spec256 set's colours: the tiles the
; game draws at A1FA, then its figures in plot order, each from a colour image of the same bytes.
; A pixel the set paints 255 stays transparent: the ULA's own white ink shows through.
;
; The pass from 9E3E to 9E44 (tiles and plots) and the copy A184 run at 28 MHz in K windows
; (hlib_pace), which pays for the picture. Interrupts are off at all of them, as in the original.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 311
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_A EQU 0x3E34
V_R0 EQU 0x3E35
V_BACK EQU 0x3E36              ; L2 16K bank of the back buffer
V_SCROLL EQU 0x3E37
V_MAP EQU 0x3E38               ; word
V_Q EQU 0x3E3A                 ; word: end of the pass's figure list
P_TOP EQU 0x3E3C               ; word: this band's first row (signed)
P_BAND EQU 0x3E3E
P_COL EQU 0x3E3F
P_ROWS EQU 0x3E40
P_Y EQU 0x3E41
P_XB EQU 0x3E42                ; L2 x of the figure
P_W EQU 0x3E43                 ; pixels drawn a row
P_SKIP EQU 0x3E44              ; word: source pixels not drawn a row
P_DX EQU 0x3E46
V_POLL EQU 0x3E48              ; word
V_QBUF EQU 0x3E80              ; 4 bytes a figure: y, x, number, type; 20 at most
ART_INDEX EQU 0x3A00           ; 3 bytes an image: page, address
ART_T1 EQU 44                  ; image number of the first of type 1
ART_T2 EQU 88                  ; of type 2
TILE_PAGE EQU 44               ; 8 pages, 32 tiles each, 256 bytes a tile
SKIP EQU 0xFE                  ; a figure's pixel that leaves what is under it
SLOT2 EQU 10                   ; the page slot 2 goes back to
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 160
BEAM_HI EQU 262
K_RENDER EQU 110
K_COPY EQU 114
R_TILES EQU -12
R_PLOT EQU -13
R_END EQU -12
R_CLS EQU -13
PLAY_LEFT EQU 32
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; Entry veneers exist in the hidden ROM and the writable page at one address.
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

; ---- from the CALL A1FA at 9E3E: the window opens, the game draws its tiles at 28 MHz
h_tiles:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,(0xF876)
        ld (V_SCROLL),a
        ld hl,(0x8C2A)
        ld (V_MAP),hl
        ld hl,V_QBUF
        ld (V_Q),hl
        call hlib_pace_open
        ld a,R_TILES
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA1FA

; ---- B112, in place of LD C,(HL) / INC HL / LD B,(HL): note the figure
h_plot:
        ENTER
        ld de,(V_Q)
        ld a,e
        cp (V_QBUF + 80) & 255
        jr z,.full
        ld bc,4
        ldir
        ld (V_Q),de
.full:  ld a,R_PLOT
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld c,(hl)
        inc hl
        ld b,(hl)
        jp 0xB115

; ---- 9E44, in place of CALL AB76: the pass is done. Draw it, pace, go on to AB76 as the CALL would.
h_render_end:
        ENTER
        call hlib_nest_open
        call draw_tiles
        call draw_figures
        ld a,8
        call hlib_nest_close
        ld a,(V_SPEED)
        ld c,a
        ld a,K_RENDER
        call hlib_pace_waitk
        ld a,R_END
        call hlib_r_set
        ld hl,(V_SP)
        dec hl
        dec hl
        ld (V_SP),hl
        ld (hl),0x47
        inc hl
        ld (hl),0x9E
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xAB76

; ---- the CALL A184 at 9E6B: wait for the beam below the play rows, copy at 28 MHz, publish
h_copy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld hl,0
        ld (V_POLL),hl
.bm:    ld hl,(V_POLL)
        dec hl
        ld (V_POLL),hl
        ld a,h
        or l
        jr z,.go
        call hlib_line
        ld de,BEAM_LO
        or a
        sbc hl,de
        jr c,.bm
        ld de,BEAM_HI-BEAM_LO
        or a
        sbc hl,de
        jr nc,.bm
.go:    ld a,8
        call hlib_debt_close
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0xA184
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld hl,(V_SP)
        ld (0xA1F7),hl
        call l2_publish
        ld a,(V_SPEED)
        ld c,a
        ld a,K_COPY
        call hlib_pace_waitk
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- A16C, in place of LD HL,4000: the screen is cleared, the overlay goes off until the next copy
h_cls:
        ENTER
        nextreg 0x69,0
        ld a,R_CLS
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld hl,0x4000
        jp 0xA16F

; ---- the tiles: 11 rows of 12, first row at 15 - scroll, row 16 is the screen's first
draw_tiles:
        ld hl,(V_MAP)
        ld (P_SKIP),hl          ; the map pointer here
        ld a,(V_SCROLL)
        cpl                     ; -1 - scroll
        ld l,a
        ld h,0xFF
        ld (P_TOP),hl
        ld a,11
        ld (P_BAND),a
.band:  ld a,12
        ld (P_COL),a
        ld a,PLAY_LEFT
        ld (P_DX),a
.tile:  ld hl,(P_SKIP)
        ld a,(hl)
        inc hl
        ld (P_SKIP),hl
        ld c,a                  ; the tile
        rlca
        rlca
        rlca
        and 7
        add a,TILE_PAGE
        nextreg 0x52,a
        ld a,c
        and 31
        add a,0x40
        ld d,a
        ld e,0                  ; DE -> the tile, in slot 2
        ld hl,(P_TOP)
        ld b,16                 ; rows
        bit 7,h
        jr z,.below
        ; top rows off the screen: -L rows skipped
        ld a,l
        add a,16
        jr nc,.tnext            ; wholly above (carry clear when L + 16 < 256)
        jr z,.tnext
        ld b,a
        ld a,l
        neg
        rlca
        rlca
        rlca
        rlca
        ld e,a                  ; 16 bytes a row
        ld a,e
        ld l,0
        ld h,0
.below: ; HL = first screen row, B = rows; cut at row 160
        ld a,l
        cp 160
        jr nc,.tnext
        add a,b
        cp 161
        jr c,.fits
        ld a,160
        sub l
        ld b,a
.fits:  ld a,l
        call l2_row             ; H = row in slot 0
        ld a,b                  ; BC = 16 x rows, for the LDIs' P/V
        rrca
        rrca
        rrca
        rrca
        ld c,a
        and 0x0F
        ld b,a
        ld a,c
        and 0xF0
        ld c,a
        ld a,(P_DX)
        ld l,a
        ex de,hl                ; HL -> the tile, DE -> Layer 2
.row:   ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        jp po,.tnext
        ld a,e
        sub 16
        ld e,a
        inc d
        ld a,d
        cp 0x20
        jr nz,.row
        ld d,0
        call l2_next
        jr .row
.tnext: ld a,(P_DX)
        add a,16
        ld (P_DX),a
        ld hl,P_COL
        dec (hl)
        jp nz,.tile
        call hlib_debt_tick     ; the picture takes over a frame
        ld hl,(P_TOP)
        ld de,16
        add hl,de
        ld (P_TOP),hl
        ld hl,P_BAND
        dec (hl)
        jp nz,.band
        nextreg 0x50,255
        nextreg 0x52,SLOT2
        ret

; l2_row: A = screen row -> slot 0 = the back buffer's page, H = row in it. V_PAGE for l2_next. AF lost.
l2_row: push bc
        ld c,a
        and 31
        ld h,a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        ld (V_PAGE),a
        nextreg 0x50,a
        pop bc
        ret
l2_next:
        ld a,(V_PAGE)
        inc a
        ld (V_PAGE),a
        nextreg 0x50,a
        ret
V_PAGE: defb 0

; ---- the figures, in the game's plot order
draw_figures:
        ld hl,V_QBUF
.lp:    ld de,(V_Q)
        ld a,e
        cp l
        jr z,.done
        push hl
        call draw_one
        pop hl
        ld de,4
        add hl,de
        jr .lp
.done:  nextreg 0x50,255
        nextreg 0x52,SLOT2
        ret

; HL -> y, x, number, type
draw_one:
        ld c,(hl)               ; y
        inc hl
        ld b,(hl)               ; x
        inc hl
        ld e,(hl)               ; number
        inc hl
        ld a,(hl)               ; type
        or a
        jr z,.t0
        cp 2
        jr z,.t2
        ; type 1: 4 bytes x 24 rows, 4 images a figure
        ld a,e
        cp 11
        ret nc
        add a,a
        add a,a
        add a,ART_T1
        ld e,a
        ld a,b
        and 6
        rrca
        add a,e
        ld e,a
        ld a,32
        ld d,24
        jr .art
.t0:    ld a,e
        cp 11
        ret nc
        add a,a
        add a,a
        ld e,a
        ld a,b
        and 6
        rrca
        add a,e
        ld e,a
        ld a,24
        ld d,24
        jr .art
.t2:    ld a,e
        cp 6
        ret nc
        add a,ART_T2
        ld e,a
        ld a,24
        ld d,16
.art:   ; E = image, A = pixels wide, D = rows, B = x, C = y
        ld (P_W),a
        ld a,d
        ld (P_ROWS),a
        ld a,c
        ld (P_Y),a
        ld a,b
        and 0xF8
        ld (P_XB),a             ; the column, in pixels from the buffer's left
        ld l,e
        ld h,0
        ld d,h
        add hl,hl
        add hl,de
        ld de,ART_INDEX
        add hl,de
        ld a,(hl)
        nextreg 0x52,a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE -> the image
        ; pixels drawn a row: clip at the buffer's right edge
        ld a,(P_XB)
        ld c,a                  ; column in pixels
        ld a,(P_W)
        ld b,a
        add a,c
        jr c,.cut
        cp 192
        jr c,.nocut
        jr z,.nocut
.cut:   ld a,192
        sub c
        jr nc,.w
        xor a
.w:     ld b,a
.nocut: ld a,(P_W)
        sub b
        ld (P_SKIP),a           ; pixels of each source row left over
        ld a,b
        ld (P_DX),a             ; pixels drawn a row
        or a
        ret z
        ld a,c
        add a,PLAY_LEFT
        ld (P_XB),a
.row:   ld a,(P_Y)
        sub 24                  ; game y 24 is the screen's first row
        cp 160
        jr nc,.off
        call l2_row
        ld a,(P_XB)
        ld l,a
        ld a,(P_DX)
        ld b,a
.px:    ld a,(de)
        inc de
        cp SKIP
        jr z,.pn
        ld (hl),a
.pn:    inc l
        djnz .px
        ld a,(P_SKIP)
        or a
        jr z,.next
        add a,e
        ld e,a
        jr nc,.next
        inc d
        jr .next
.off:   ld a,(P_W)
        add a,e
        ld e,a
        jr nc,.next
        inc d
.next:  ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jr nz,.row
        ret

; l2_publish: the back buffer becomes the front
l2_publish:
        ld a,(V_BACK)
        nextreg 0x12,a
        nextreg 0x69,0x80
        cp L2_BANK_A
        ld a,L2_BANK_B
        jr z,.s
        ld a,L2_BANK_A
.s:     ld (V_BACK),a
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "atomant_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_BANK_A
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,pal_data
        ld bc,512
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,.lp
        nextreg 0x43,0
        ; both buffers transparent in the play rows: 5 pages each; the panel is in the sixth
        ld d,L2_BANK_A*2
        call .fill
        ld d,L2_BANK_B*2
        call .fill
        nextreg 0x50,255
        ret
.fill:  ld e,5
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0xFF
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        ret
setup_end:
pal_data:
        SAVEBIN "atomant_setup.bin",setup,setup_end-setup
