; Game Over (Dinamic/Imagine, 128K): clash removal by a Layer 2 figure overlay.
;
; The game composes each pass in a work buffer (restore from the clean buffer,
; mask + OR the figures, paint the figures' cells in the work attributes), then
; copies bitmap and attributes to the ULA. This engine keeps every bitmap byte:
; the ULA bitmap is the original's. The attributes shown come from the clean
; buffer (a one-operand change at the copy), so scenery keeps its own colours.
; Each figure's ink is drawn on Layer 2, in plot order, in the figure's own
; colour; a figure's opaque mask and plots with cell painting off (pillars in
; front) punch earlier ink out. So the picture equals the original bitmap with
; per-pixel colour. Double buffered, published with the copy, off screen.
;
; Original game RAM is read only here. The original plot and copy bodies run
; whole at 28 MHz inside K windows (hlib_pace), which pays for the overlay.
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
V_FRESH EQU 0x3E37             ; 1: back buffer not cleared for this pass
V_INK EQU 0x3E38
V_OPAQUE EQU 0x3E39
V_RECT EQU 0x3E3A              ; word: end of the back buffer's rectangle list
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_COLS EQU 0x3E3F
P_K EQU 0x3E40
P_N EQU 0x3E41
P_C EQU 0x3E42
P_SHIFT EQU 0x3E43
P_SRC EQU 0x3E44               ; word
P_W EQU 0x3E46
V_FR EQU 0x3E4C             ; word: FRAMES at the window's start
V_EX EQU 0x3E4E             ; word
ISR_LINES EQU 7
P_CNT EQU 0x3E47
V_POLL EQU 0x3E48             ; word
R_BUF EQU 0x3E80               ; gfx + mask row, up to 64 bytes
RECTS_A EQU 0x2700             ; 4 bytes a rectangle
RECTS_B EQU 0x3C00
RECT_MAX EQU 60
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 124                ; below the play area, shake included
BEAM_HI EQU 240
V_K1 EQU 0x3E76                ; world 1's restore and copy K: the mode's own (1/16)
V_K2 EQU 0x3E75                ; world 2's restore and copy K: the mode's own (1/16)
RC_W1 EQU 26                   ; a plot's time, quarters of 1/16 line a byte of width: JNext, the original's contention
RC_W2 EQU 24
PL_OVER EQU 76                 ; what the hook costs outside the window, less the plot's fixed 20
V_TGT EQU 0x3E4A               ; word
ATTR_P EQU 0x5C8F
V_ENH EQU 0x3E50               ; Enhanced
V_BDT EQU 0x3E51               ; the Backdrop line
V_SCENE EQU 0x3E52             ; a scene is being built: plots go to C
V_PLAY EQU 0x3E53              ; C is the picture: the play area is not printed on Layer 2
V_FULLN EQU 0x3E57
V_TAB EQU 0x3E5A               ; word
V_BDP EQU 0x3E5C
V_BDP1 EQU 0x3E5D
V_BDP2 EQU 0x3E5E
V_FP1 EQU 0x3E5F
T_PAGE EQU 0x3E60
T_OFF EQU 0x3E61               ; word
T_NB EQU 0x3E63
T_SKIP EQU 0x3E64
T_STR EQU 0x3E65
T_CNT EQU 0x3E66
T_DX EQU 0x3E67
T_SRC EQU 0x3E68               ; word
T_Y EQU 0x3E6A
T_H EQU 0x3E6B
T_XP EQU 0x3E6C
T_WP EQU 0x3E6D
T_CH EQU 0x3E6E
T_HOLE EQU 0x3E73
V_PART EQU 0x3E74
RB EQU 0x3D00                  ; a row, 256 bytes
TAB1 EQU 0x2000                ; world 1's graphics: record, page, offset, gfx bytes a row
TAB2 EQU 0x2300
ZXTAB EQU 0x2600               ; the 16 Spectrum colours as palette indices
C_PAGE EQU 44
FONT1 EQU 0xAAEF
FONT2 EQU 0xA977
V_FONTP1 EQU 60
V_FONTP2 EQU 61
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
        call isr_extra
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM

; ---- plot: the original's body B4EF / B517, whole, K-windowed --------------
        MACRO PLOT_HOOK flag, body, rc
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld a,(flag)
        call l2_plot
        ld a,rc
        call plot_target
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld hl,(0x5C78)
        ld (V_FR),hl
        COPY_BODY body
        ld a,(V_SPEED)
        ld hl,(V_TGT)
        call hlib_pace_wait
        call isr_extra
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret
        ENDM

h_plot1:
        PLOT_HOOK 0xB47E,0xB4EF,RC_W1
        defs 0x2CC0-$,0
h_plot2:
        PLOT_HOOK 0xB4A6,0xB517,RC_W2
        defs 0x2D80-$,0

; ---- restore: clean buffer to the work buffer at 28 MHz --------------------

        MACRO WAIT_KV vk
        ld a,(V_SPEED)
        ld c,a
        ld a,(vk)
        call hlib_pace_waitk
        call isr_extra
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM
        MACRO RESTORE_HOOK body, kw
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,1                  ; a restore wipes the work buffer: figures plotted before it never show
        ld (V_FRESH),a
        call hlib_pace_open
        ld hl,(0x5C78)
        ld (V_FR),hl
        COPY_BODY body
        kw
        LEAVE_R
        ret
        ENDM

h_rest1:
        RESTORE_HOOK 0xAF4B,WAIT_KV V_K1
        defs 0x2E40-$,0
h_rest2:
        RESTORE_HOOK 0xAF73,WAIT_KV V_K2
        defs 0x2F00-$,0

; ---- copy: wait for the beam below the play area, copy at 28 MHz, publish ---
        MACRO COPY_HOOK body, shake, kw
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
.go:    ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld hl,(0x5C78)
        ld (V_FR),hl
        COPY_BODY body
        ld a,(V_ENH)            ; Enhanced is the whole screen: its picture stays still
        or a
        ld a,0
        jr nz,.ns
        ld a,(shake)
        or a
        jr z,.ns
        ld a,188
.ns:    nextreg 0x17,a
        call l2_publish
        kw
        LEAVE_R
        ret
        ENDM

h_copy1:
        COPY_HOOK 0xAF4B,0xBF20,WAIT_KV V_K1
        defs 0x3000-$,0
h_copy2:
        COPY_HOOK 0xAF73,V_ZERO,WAIT_KV V_K2
        defs 0x3100-$,0

; ---- the barrel's own cell colours: AF06 is entered unchanged after this ----
h_cell:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld a,(V_ENH)
        or a
        call z,l2_cells
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
        jp 0xAF06

; ---- the whole screen is cleared: the overlay goes off until the next copy ---
h_cls:
        ENTER
        ld a,(V_ENH)
        or a
        jr nz,.e
        nextreg 0x69,0
.e:     ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld a,(ATTR_P)           ; the displaced instruction
        jp 0xBA66

        MACRO LEAVE_D
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        ENDM
h_print:                        ; BDC8: LD L,A / LD H,0 displaced
        ENTER
        HLIB_SPEED_IN_ABC V_SPEED
        call hlib_debt_open
        call e_char
        ld a,8
        call hlib_debt_close
        HLIB_SPEED_OUT_A V_SPEED
        LEAVE_D
        ld l,a
        ld h,0
        nextreg 0x51,255
        jp 0xBDCB
h_fill:                         ; BA84: PUSH HL / POP DE / INC DE displaced
        ENTER
        ld a,h
        cp 0x40
        jr nz,.t
        ld a,l
        or a
        jr nz,.t
        ld a,(V_ENH)
        or a
        call nz,e_slowclr
        jr .k
.t:     ld a,h
        cp 0x5D
        jr nz,.k
        ld a,l
        cp 0xC0
        jr nz,.k
        ld a,b
        cp 0x1D
        jr nz,.k
        ld a,1
        ld (V_SCENE),a
        ld a,(V_ENH)
        or a
        call nz,e_slowscene
.k:     LEAVE_D
        push hl
        pop de
        inc de
        nextreg 0x51,255
        jp 0xBA87
h_cap1:                         ; A33F: LD HL,5DC0 displaced: the scene is whole
        ENTER
        call e_captured
        LEAVE_D
        nextreg 0x51,255
        ld hl,0x5DC0
        jp 0xA342
h_cap2:                         ; A4AA
        ENTER
        call e_captured
        LEAVE_D
        nextreg 0x51,255
        ld hl,0x5DC0
        jp 0xA4AD
h_z1:                           ; 9973: LD A,0 / LD (DE),A displaced
        ENTER
        HLIB_SPEED_IN_ABC V_SPEED
        call e_zero
        HLIB_SPEED_OUT_A V_SPEED
        LEAVE_D
        ld a,0
        ld (de),a
        nextreg 0x51,255
        jp 0x9976
h_z2:                           ; 97AE
        ENTER
        HLIB_SPEED_IN_ABC V_SPEED
        call e_zero
        HLIB_SPEED_OUT_A V_SPEED
        LEAVE_D
        ld a,0
        ld (de),a
        nextreg 0x51,255
        jp 0x97B1
e_captured:
        xor a
        ld (V_SCENE),a
        ld a,(V_ENH)
        or a
        ret z
        ld (V_PLAY),a
        ld (V_FRESH),a
        ld a,3
        ld (V_FULLN),a
        ret
e_slowclr:
        HLIB_SPEED_IN_ABC V_SPEED
        call hlib_debt_open
        call e_clear
        jr e_slowend
e_slowscene:
        HLIB_SPEED_IN_ABC V_SPEED
        call hlib_debt_open
        call e_scene
e_slowend:
        ld a,8
        call hlib_debt_close
        HLIB_SPEED_OUT_A V_SPEED
        ret

; plot_target: the original plot's time from what it will draw (1/16 line): A = its cost a byte of width.
plot_target:
        ld e,a
        ld d,0
        ld hl,72
        ld a,(iy+3)
        or a
        jr z,.nc
        ld b,a
.c:     add hl,de
        djnz .c
.nc:    ld a,(iy-5)
        ld e,a
        ld b,6
.w:     add hl,de
        djnz .w
        ld a,(0xB735)
        and 1
        jr z,.ns
        ld bc,36
        add hl,bc
        ld b,10
.sw:    add hl,de
        djnz .sw
.ns:    ex de,hl
        ld hl,0
        ld a,(iy+1)
        or a
        jr z,.z
        ld b,a
.r:     add hl,de
        djnz .r
        srl h
        rr l
        srl h
        rr l
.z:     ld de,PL_OVER         ; the hook's own time beyond the window
        or a
        sbc hl,de
        jr nc,.t
        ld hl,0
.t:     ld (V_TGT),hl
        ret

V_ZERO: defb 0
; ---- Layer 2: A = the plot's paint flag byte (C9: painting off) --------------
l2_plot:
        ld b,a
        ld a,(V_ENH)
        or a
        jp nz,e_plot
        ld a,(iy+1)
        or a
        ret z
        push bc
        call l2_ready
        pop bc
        ld a,b
        cp 0xC9
        ld a,255
        ld (V_INK),a
        ld (V_OPAQUE),a
        jr z,.colour_done
        ld a,(ATTR_P)
        ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld (V_INK),a
        ld a,254
        ld (V_OPAQUE),a
.colour_done:
        push ix
        ld a,(iy+1)
        ld (P_ROWS),a
        ld a,(iy+0)
        add a,8
        ld (P_Y),a
        ld a,(iy+2)
        inc a
        ld (P_X),a
        ld a,(iy+3)
        ld (P_COLS),a
        ld a,(iy+4)
        ld (P_K),a
        ld hl,(0xB736)
        ld (P_SRC),hl
        ld a,(iy-5)
        ld (P_W),a
        srl a
        ld (P_N),a
        ld (P_C),a
        ld a,(0xB735)
        and 1
        ld (P_SHIFT),a
        jr z,.ns
        ld hl,P_C
        inc (hl)
.ns:    ld a,(V_INK)
        cp 255
        jr z,.punch
        call rect_add
        jr .row
.punch: call rect_hit           ; nothing drawn under a punch: no work
        jr c,.row
        pop ix
        ret
.row:   ld a,(P_N)
        ld c,a
        ld b,0
        ld hl,(P_SRC)
        ld de,R_BUF
        ld a,(P_SHIFT)
        or a
        jr nz,.shifted
        ldir
        ld a,(P_N)
        ld c,a
        ldir
        ld (P_SRC),hl
        jr .out
.shifted:
        ldir
        ld a,0x0F
        ld (de),a
        inc de
        ld a,(P_N)
        ld c,a
        ldir
        ld (P_SRC),hl
        ld a,0xFF
        ld (de),a
        ld hl,R_BUF
        ld a,(P_C)
        add a,a
        ld b,a
        xor a
.rrd:   rrd
        inc hl
        djnz .rrd
.out:   ld a,(P_Y)
        call l2_row             ; H = this row in slot 0
        ld a,(P_X)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld de,(V_INK)           ; E = ink, D = opaque
        ld a,(P_C)
        ld (.mo+2),a
        ld a,(P_K)
        ld c,a
        ld b,0
        ld ix,R_BUF
        add ix,bc
        ld a,(P_COLS)
        ld (P_CNT),a
.byte:  ld c,(ix+0)
.mo:    ld b,(ix+0)             ; the mask, N or N+1 bytes on (set above)
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

; l2_cells: recolour this figure's pixels by the game's own attribute block
; (B734 row, B735 column, B736 -> height, width, attributes), both ink and paper.
l2_cells:
        call l2_ready
        ld hl,(0xB736)
        ld a,(hl)
        ld (P_ROWS),a
        inc hl
        ld a,(hl)
        ld (P_COLS),a
        inc hl
        ld (P_SRC),hl
        ld a,(0xB734)
        add a,a
        add a,a
        add a,a
        add a,8
        ld (P_Y),a
.row:   ld a,(0xB735)
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        ld a,(P_COLS)
        ld (P_N),a
.cell:  ld hl,(P_SRC)
        ld a,(hl)
        inc hl
        ld (P_SRC),hl
        ld b,a
        and 7
        bit 6,b
        jr z,.ni
        or 8
.ni:    ld e,a
        ld a,b
        rrca
        rrca
        rrca
        and 7
        bit 6,b
        jr z,.np
        or 8
.np:    ld d,a
        ld a,(P_Y)
        ld c,8
.line:  push af
        call l2_row
        ld a,(P_X)
        ld l,a
        ld b,8
.px:    ld a,(hl)
        cp 255
        jr z,.pe
        cp 254
        jr nz,.ink
        ld (hl),d
        jr .pe
.ink:   ld (hl),e
.pe:    inc l
        djnz .px
        pop af
        inc a
        dec c
        jr nz,.line
        ld a,(P_X)
        add a,8
        ld (P_X),a
        ld hl,P_N
        dec (hl)
        jr nz,.cell
        ld a,(P_Y)
        add a,8
        ld (P_Y),a
        ld hl,P_ROWS
        dec (hl)
        jr nz,.row
        nextreg 0x50,255
        ret

; isr_extra: an interrupt inside a window took little of the original's time here; the original's
; handler ran at its own clock on top of the routine. Wait that time for each one taken (FRAMES counts them).
isr_extra:
        ld hl,(0x5C78)
        ld de,(V_FR)
        or a
        sbc hl,de
        ld a,l
        or a
        ret z
        cp 8
        ret nc
        ld hl,0
        ld de,ISR_LINES
.m:     add hl,de
        dec a
        jr nz,.m
        ld (V_EX),hl
        call hlib_line
        ex de,hl
.lp:    push de
        call hlib_line
        pop de
        push hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,HLIB_PACE_NL
        add hl,de
.p:     ex de,hl
        ld hl,(V_EX)
        or a
        sbc hl,de
        ld (V_EX),hl
        pop de
        jr z,.done
        jr nc,.lp
.done:  ret

; rect_add: note the figure's box for the next clear of this buffer.
rect_add:
        ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*4
        jr nz,.room
        ld l,RECT_MAX*4-4       ; list full: the last entry becomes the whole area
        ld (hl),8
        inc l
        ld (hl),112
        inc l
        ld (hl),1
        inc l
        ld (hl),30
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
        ld a,(V_ENH)
        or a
        jp nz,e_ready
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
        ld b,a
        xor a
        ld (V_SCENE),a
        ld a,b
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
        INCLUDE "game_over_enh.inc"
rom_end2:
        ASSERT $ < 0x3C00
        SAVEBIN "gameover_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,8
        nextreg 0x18,247
        nextreg 0x18,8
        nextreg 0x18,119
setup_enh:
        ld a,0                  ; Enhanced?
        or a
        jp nz,setup_e
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
        ; both buffers transparent: 4 pages (rows 0..127) each
        ld d,L2_BANK_A*2
        call .fill
        ld d,L2_BANK_B*2
        call .fill
        nextreg 0x50,255
        ret
.fill:  ld e,4
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
setup_e:
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10       ; Layer 2's first palette
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
        nextreg 0x43,0
        ld d,L2_BANK_A*2
        ld e,6
        call .fill
        ld d,L2_BANK_B*2
        ld e,6
        call .fill
        ld d,C_PAGE
        ld e,4
        call .fill
        nextreg 0x50,255
        nextreg 0x69,0x80
        ret
.fill:  ld a,d
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
        jr nz,.fill
        ret
e_palette:
        defs 512,0
setup_end:
        SAVEBIN "gameover_setup.bin",setup,setup_end-setup
