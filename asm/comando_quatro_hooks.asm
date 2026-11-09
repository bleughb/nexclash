; Comando Quatro (Zigurat / GameSoft, 1989, 48K): clash removal by a Layer 2 figure overlay.
;
; The game composes each pass in a back buffer (pixels F0B0, attributes FCF0, 28 columns x 14 rows):
; each figure is masked and ORed in, its box painted with the figure's ink and bright (B7CF), the whole
; window copied to the screen (EB0A), then everything restored from a save list (B830). Painting is the
; clash: the scenery in a figure's box takes the figure's ink.
;
; Here every game byte stays the original's. The ULA bitmap is the original's. The attributes shown
; come from a private copy taken before the pass's first plot: for the length of the game's own copy the
; clean attributes stand in its buffer, so a painted cell never reaches the screen. Each
; figure's ink goes on a double-buffered Layer 2, in plot order, in the colour the game would have
; painted; a figure's opaque mask punches earlier ink out. Published with the copy, off the play rows.
;
; The original plot, copy and restore run whole at 28 MHz in K windows (hlib_pace), which pays for the
; overlay. Interrupts are off throughout play in this game; beeper sound is outside the hooks.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_A EQU 0x3E34
V_R0 EQU 0x3E35
V_BACK EQU 0x3E36              ; L2 16K bank of the back buffer
V_FRESH EQU 0x3E37             ; 1: back buffer not cleared for this pass
V_INK EQU 0x3E38
V_OPAQUE EQU 0x3E39
V_RECT EQU 0x3E3A              ; word: end of the back buffer's rectangle list
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_COLS EQU 0x3E3F
P_SKIP EQU 0x3E40
P_W EQU 0x3E41
P_S EQU 0x3E42
P_CNT EQU 0x3E43
P_G EQU 0x3E44                 ; word: this row's graphic
P_M EQU 0x3E46                 ; word: this row's mask
V_POLL EQU 0x3E48              ; word
R_BUF EQU 0x3E80               ; [0, gfx.., 0] at +0, [FF, mask.., FF] at +16
RECTS_A EQU 0x3A00             ; 4 bytes a rectangle, 64 rectangles
RECTS_B EQU 0x3B00
RECT_MAX EQU 60
SHADOW EQU 0x2000              ; 392 clean attributes, as FCF0
TEMP EQU 0x2200                ; 392: the work attributes while the clean ones stand in
ATTRS EQU 0xFCF0
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 152                ; below the play rows (40..151)
BEAM_HI EQU 285                ; a copy started here ends before line 40 of the next frame
K_PLOT EQU 100
K_COPY EQU 112
K_REST EQU 100
ROW0 EQU 40                    ; the window's first screen row, first screen column 2
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
; Leave: R as the original's, registers restored, page restored.
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

; The original body runs with its entry registers; R afterwards is the entry
; R + the M1s the body really took (V_R0).
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
        MACRO WAIT_K k
        ld a,(V_SPEED)
        ld c,a
        ld a,k
        call hlib_pace_waitk
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM

; ---- a figure: its ink on the overlay, then the original's plot B663 -------
h_plot:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call l2_plot
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        COPY_BODY 0xB663
        WAIT_K K_PLOT
        LEAVE_R
        ret

; ---- the restore B830, whole ------------------------------------------------
h_rest:
        ENTER
        ld a,(0xB9BF)           ; the Z of the original's CALL NZ
        or a
        jr z,.skip
        HLIB_SPEED_IN V_SPEED
        call hlib_pace_open
        COPY_BODY 0xB830
        WAIT_K K_REST
        LEAVE_R
        ret
.skip:  ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- the pass's copy: wait for the beam below the play rows, copy, publish --
h_copy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call l2_ready
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
.go:    call attrs_in
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        COPY_BODY 0xEB0A
        call l2_publish
        WAIT_K K_COPY
        call hlib_debt_open
        call attrs_out
        ld a,8
        call hlib_debt_close
        LEAVE_R
        ret

; ---- a copy during the screen wipe (C761): the clean attributes, no new overlay
h_wcopy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call attrs_in
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        COPY_BODY 0xEB0A
        WAIT_K K_COPY
        call hlib_debt_open
        call attrs_out
        ld a,8
        call hlib_debt_close
        LEAVE_R
        ret

; ---- the copy of the cleared window (DD1C): nothing left to overlay ---------
h_dcopy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_pace_open
        COPY_BODY 0xEB0A
        nextreg 0x69,0
        WAIT_K K_COPY
        LEAVE_R
        ret

; ---- a render pass starts (B549, or B54C at C748): the attributes are clean --
        MACRO REND_HOOK target
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld hl,ATTRS
        ld de,SHADOW
        ld bc,392
        ldir
        ld a,8
        call hlib_debt_close
        HLIB_SPEED_OUT V_SPEED
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
h_rend:
        REND_HOOK 0xB549
h_rend4:
        REND_HOOK 0xB54C

; ---- the wipe blanks a pixel row of the buffer: the overlay's row goes too ---
h_wrow:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        pop hl                  ; the game's HL: the row
        push hl
        ld de,0xF0B0
        or a
        sbc hl,de
        ld de,28
        ld a,ROW0-1
.d:     inc a
        or a
        sbc hl,de
        jr nc,.d
        call l2_rowfront
        ld a,8
        call hlib_debt_close
        HLIB_SPEED_OUT V_SPEED
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xB177

; ---- the whole screen is cleared (B153): the overlay goes off until the next copy
h_cls:
        ENTER
        nextreg 0x69,0
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld hl,0x5800            ; the displaced instruction
        jp 0xB156

; attrs_in: the clean attributes stand in the game's buffer, its own in TEMP. attrs_out puts them back.
attrs_in:
        ld hl,ATTRS
        ld de,TEMP
        ld bc,392
        ldir
        ld hl,SHADOW
        ld de,ATTRS
        ld bc,392
        ldir
        ret
attrs_out:
        ld hl,TEMP
        ld de,ATTRS
        ld bc,392
        ldir
        ret

; ---- Layer 2: IX = the figure, B9E0.. and the operands B673 / B681 as the game set them for B663
l2_plot:
        call l2_ready
        ld a,255
        ld (V_INK),a
        ld (V_OPAQUE),a
        ld a,(ix+5)
        bit 4,a
        jr z,.paint
        ld a,(0xB9AF)
        or a
        jr z,.colour_done       ; the game paints nothing for this plot
        ld a,(ix+5)
.paint: bit 5,a
        jr nz,.own
        bit 7,(ix+9)
        jr z,.own
        ld a,1
.own:   ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld (V_INK),a
.colour_done:
        push ix
        ld a,(ix+3)
        ld (P_W),a
        ld a,(0xB9E8)
        ld (P_ROWS),a
        ld a,(0xB9E7)
        add a,ROW0
        ld (P_Y),a
        ld a,(0xB9E5)
        sub 0x70
        ld (P_X),a
        ld a,(0xB9E6)
        ld (P_COLS),a
        ld a,(0xB9E9)
        ld (P_SKIP),a
        ld a,(0xB9E0)
        and 7
        ld (P_S),a
        ld hl,(0xB673)
        ld (P_G),hl
        ld hl,(0xB681)
        ld (P_M),hl
        ld a,(V_INK)
        cp 255
        jr z,.punch
        call rect_add
        jr .start
.punch: call rect_hit           ; nothing drawn under a punch: no work
        jr c,.start
        pop ix
        ret
.start: ld ix,R_BUF+1
        ld a,(P_SKIP)
        ld e,a
        ld d,0
        add ix,de
.row:   ld a,(P_W)
        ld c,a
        ld b,0
        ld hl,(P_G)
        ld de,R_BUF
        xor a
        ld (de),a
        inc de
        ldir
        ld (P_G),hl
        ld (de),a
        ld a,(P_W)
        ld c,a
        ld hl,(P_M)
        ld de,R_BUF+16
        ld a,0xFF
        ld (de),a
        inc de
        ldir
        ld (P_M),hl
        ld (de),a
        ld a,(P_Y)
        call l2_row             ; H = this row in slot 0
        ld a,(P_X)
        add a,a
        add a,a
        add a,a
        ld l,a
        push ix
        ld a,(P_COLS)
        ld (P_CNT),a
.byte:  ld a,(P_S)
        ld b,a
        ld d,(ix-1)
        ld e,(ix+0)
        bsrl de,b
        ld c,e                  ; ink bits
        ld d,(ix+15)
        ld e,(ix+16)
        bsrl de,b
        ld b,e                  ; mask bits
        ld a,c
        or a
        jr nz,.pixels
        ld a,b
        inc a
        jr nz,.pixels
        ld a,l
        add a,8
        ld l,a
        jr .next
.pixels:
        ld de,(V_INK)           ; E = ink, D = opaque
        ld a,8
.pix:   rl c
        jr nc,.noink
        ld (hl),e
        rl b
        jr .pn
.noink: rl b
        jr c,.pn
        ld (hl),d
.pn:    inc l
        dec a
        jr nz,.pix
.next:  inc ix
        ld a,(P_CNT)
        dec a
        ld (P_CNT),a
        jr nz,.byte
        pop ix
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jp nz,.row
        nextreg 0x50,255
        pop ix
        ret

; l2_row: A = screen y -> slot 0 = the back buffer's page, H = row in it. AF lost.
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
        nextreg 0x50,a
        pop bc
        ret

; l2_rowfront: A = screen y: that row of the buffer on show goes transparent.
l2_rowfront:
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
        xor L2_BANK_A^L2_BANK_B
        add a,a
        add a,c
        nextreg 0x50,a
        ld l,16
        ld d,h
        ld e,17
        ld (hl),255
        ld bc,223
        ldir
        nextreg 0x50,255
        ret

; rect_add: note the figure's box for the next clear of this buffer.
rect_add:
        ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*4
        jr nz,.room
        ld l,RECT_MAX*4-4       ; list full: the last entry becomes the whole window
        ld (hl),ROW0
        inc l
        ld (hl),112
        inc l
        ld (hl),2
        inc l
        ld (hl),28
        ret
.room:  ld a,(P_Y)
        ld (hl),a
        inc l
        ld a,(P_ROWS)
        ld (hl),a
        inc l
        ld a,(P_X)
        ld (hl),a
        inc l
        ld a,(P_COLS)
        ld (hl),a
        inc l
        ld (V_RECT),hl
        ret

; rect_hit: carry set when this plot's box meets a box already drawn in this buffer.
rect_hit:
        ld hl,(V_RECT)
        ld a,l
        or a
        ret z                   ; empty list: no carry
.next:  dec l
        dec l
        ld a,(P_X)              ; x: box [P_X, P_X+P_COLS) against [rx, rx+rw)
        ld b,a
        ld a,(hl)               ; rx
        ld c,a
        inc l
        add a,(hl)              ; rx + rw
        dec l
        cp b
        jr z,.miss
        jr c,.miss              ; rect ends at or before the box
        ld a,(P_COLS)
        add a,b
        cp c
        jr z,.miss
        jr c,.miss              ; box ends at or before the rect
        dec l
        dec l
        ld a,(P_Y)
        ld b,a
        ld a,(hl)               ; ry
        ld c,a
        inc l
        add a,(hl)              ; ry + rh
        dec l
        cp b
        jr z,.miss2
        jr c,.miss2
        ld a,(P_ROWS)
        add a,b
        cp c
        jr z,.miss2
        jr c,.miss2
        scf
        ret
.miss:  dec l
        dec l
.miss2: ld a,l
        or a
        jr nz,.next
        or a
        ret

; l2_ready: clear the back buffer once per pass, by the boxes drawn in it.
l2_ready:
        ld a,(V_FRESH)
        or a
        ret z
        xor a
        ld (V_FRESH),a
        ld hl,(V_RECT)
        ld a,l
        or a
        ret z
.next:  dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld c,a                  ; width, pixels
        dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        dec l
        ld d,(hl)               ; rows
        dec l
        ld e,(hl)               ; y
        push hl
.row:   push de
        ld a,e
        call l2_row
        ld a,(P_X)
        ld l,a
        ld d,h
        ld e,l
        inc e
        ld (hl),255
        ld a,c
        dec a
        jr z,.onepix
        push bc
        ld c,a
        ld b,0
        ldir
        pop bc
.onepix:
        pop de
        inc e
        dec d
        jr nz,.row
        pop hl
        ld a,l
        or a
        jr nz,.next
        ld (V_RECT),hl
        nextreg 0x50,255
        ret

; l2_publish: the back buffer becomes the front; the other buffer's list next.
l2_publish:
        call l2_ready
        ld a,(V_BACK)
        nextreg 0x12,a
        nextreg 0x69,0x80
        cp L2_BANK_A
        ld hl,(V_RECT)
        jr z,.a
        ld (V_LIST_B),hl
        ld hl,(V_LIST_A)
        ld a,L2_BANK_A
        jr .s
.a:     ld (V_LIST_A),hl
        ld hl,(V_LIST_B)
        ld a,L2_BANK_B
.s:     ld (V_RECT),hl
        ld (V_BACK),a
        ld a,1
        ld (V_FRESH),a
        ret
V_LIST_A: defw RECTS_A
V_LIST_B: defw RECTS_B

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "cq_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,16
        nextreg 0x18,239
        nextreg 0x18,40
        nextreg 0x18,151
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,16
.lp:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .lp
        nextreg 0x40,254
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x43,0
        ; both buffers transparent: 6 pages each
        ld d,L2_BANK_A*2
        call .fill
        ld d,L2_BANK_B*2
        call .fill
        nextreg 0x50,255
        ret
.fill:  ld e,6
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
l2_pal: defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        defb 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:
        SAVEBIN "cq_setup.bin",setup,setup_end-setup
