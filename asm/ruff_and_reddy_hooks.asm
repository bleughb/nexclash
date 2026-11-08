; Ruff and Reddy (Hi-Tec, 128K): clash removal by a Layer 2 figure overlay.
;
; The game composes each update in a 26 x 160 back buffer at 8C90: it saves the
; cells under each figure, plots them with their masks, then copies the buffer to
; the screen (A506..A5E6, about a frame at 3.5 MHz). The attributes are the room's
; and never change in play, so a figure takes the ink of the cells it crosses.
; This engine keeps the ULA as the original's, byte for byte, and draws each
; figure's ink on Layer 2 in white, the colour a figure has in the open, in the
; game's plot order; a figure's mask punches out what it covers. Double buffered,
; published with the copy, which runs whole below the play area at 28 MHz.
;
; The original bodies run whole at 28 MHz inside K windows (hlib_pace), which pays
; for the overlay. Interrupts are off at every hook but the three that only hide.
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
V_RECT EQU 0x3E3A              ; word: end of the back buffer's rectangle list
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_N EQU 0x3E3F                 ; bytes a row of the source
V_Q EQU 0x3E42                 ; word: end of the pass's figure list
V_QBUF EQU 0x3E80              ; 4 bytes a figure: kind, x, y, number; 6 at most
P_R EQU 0x3E40                 ; screen row (0..159)
P_SRC EQU 0x3E44               ; word
V_POLL EQU 0x3E48              ; word
RECTS_A EQU 0x3A00             ; 4 bytes a rectangle
RECTS_B EQU 0x3B00
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 160                ; below the play rows
BEAM_HI EQU 262
K_RENDER EQU 100
K_COPY EQU 118
ROW_FIRST EQU 32               ; the game's y of the buffer's first row (9CD0)
X_LEFT EQU 24                  ; the buffer's first column on the screen
WHITE EQU 15
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

;    The whole render pass before the frame wait is one K window at 28 MHz: entered at A31E, closed at A4F7.
h_render:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_pace_open
        ld a,R_RENDER
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA31E
h_render_end:
        ENTER
        call hlib_nest_open
        call draw_queue
        ld a,8
        call hlib_nest_close
        ld a,(V_SPEED)
        ld c,a
        ld a,K_RENDER
        call hlib_pace_waitk
        ld a,R_WAIT
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ei
h_halt: halt
        di
        jp 0xA4FA

; ---- plot: note the figure and go on to the original's body. The overlay is drawn
; at the end of the pass, so the window's reading stays the game's own time.
        MACRO PLOT_HOOK kind, xa, ya, sa, target
        ENTER
        ld hl,(V_Q)
        ld (hl),kind
        inc hl
        ld a,(xa)
        ld (hl),a
        inc hl
        ld a,(ya)
        ld (hl),a
        inc hl
        ld a,(sa)
        ld (hl),a
        inc hl
        ld (V_Q),hl
        ld a,R_PLOT
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

h_big:
        PLOT_HOOK 1,0xA671,0xA69B,0xA68F,0xA66C
h_small:
        PLOT_HOOK 0,0xA86C,0xA896,0xA88A,0xA867

; the pass's figures, in the game's plot order, on the back buffer
draw_queue:
        call l2_ready
        ld hl,V_QBUF
.lp:    ld de,(V_Q)
        or a
        push hl
        sbc hl,de
        pop hl
        jr z,.done
        ld a,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld e,(hl)
        inc hl
        push hl
        ld hl,P_X
        ld (hl),c
        ld hl,P_Y
        ld (hl),b
        or a
        ld a,e
        jr z,.small
        call l2_big
        jr .next
.small: call l2_small
.next:  pop hl
        jr .lp
.done:  ld hl,V_QBUF
        ld (V_Q),hl
        ret

; ---- copy: entered from A506 in place of LD SP,9EA4. Wait for the beam below the
; play rows; the game's own copy runs at 28 MHz and comes back at h_copy_end.
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
.go:    ld a,8
        call hlib_debt_close
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        ld sp,0x9EA4
        jp 0xA509
; ---- from A5E6, in place of LD SP,5DBF: the copy is done; publish and pace.
h_copy_end:
        ld sp,0x4000
        push af
        push bc
        push de
        push hl
        call l2_publish
        ld a,(V_SPEED)
        ld c,a
        ld a,K_COPY
        call hlib_pace_waitk
        ld a,R_COPY
        call hlib_r_set
        ld hl,0x5DBF
        ld (V_SP),hl
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA5E9

; ---- a new room or a full-screen picture: the overlay goes off until the next copy
        MACRO HIDE_HOOK target, delta
        ENTER
        nextreg 0x69,0
        ld a,delta
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
h_room:
        HIDE_HOOK 0xAADD,R_HIDE
h_title:
        HIDE_HOOK 0xD332,R_HIDE
h_over:
        HIDE_HOOK 0xAC70,R_HIDE
; ---- D42B, in place of LD (D4A0),SP: the window is cleared for a message, such as LEVEL COMPLETE
h_msg:
        ENTER
        nextreg 0x69,0
        ld hl,(V_SP)
        ld (0xD4A0),hl
        ld a,R_MSG
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xD42F

; ---- Layer 2 ---------------------------------------------------------------
; A figure of 3 bytes x 32 rows: M1 M2 M3 G1 G2 G3 a row. Table A034. A = its number.
l2_big: ld hl,0xA034
        ld b,32
        ld c,3
        jr l2_plot
; A figure of 2 bytes x 16 rows: M1 M2 G1 G2 a row. Table A05E. A = its number.
l2_small:
        ld hl,0xA05E
        ld b,16
        ld c,2
l2_plot:
        ld e,a
        ld d,0
        add hl,de
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (P_SRC),de
        ld a,b
        ld (P_ROWS),a
        ld a,c
        ld (P_N),a
        call rect_add
.row:   ld a,(P_Y)
        sub ROW_FIRST
        cp 160
        jr nc,.skip
        ld (P_R),a
        call l2_row             ; H = this row in slot 0
        ld a,(P_X)
        add a,X_LEFT
        ld l,a
        ld a,(P_N)
        ld b,a                  ; bytes
        ld de,(P_SRC)           ; DE -> M1
.byte:  push de
        ld a,(de)
        ld c,a                  ; the mask
        ld a,(P_N)
        add a,e
        ld e,a
        jr nc,.nc
        inc d
.nc:    ld a,(de)               ; the graphic
        pop de
        inc de
        ; A = graphic, C = mask
        or a
        jr nz,.pixels
        ld a,c
        inc a
        jr nz,.pix0
        ld a,l                  ; nothing here: 8 pixels on
        add a,8
        ld l,a
        jr .bytedone
.pix0:  xor a
.pixels:
        push bc
        ld b,8
.pix:   rlca
        jr nc,.noink
        ld (hl),WHITE
        rl c
        jr .pn
.noink: rl c
        jr c,.pn
        ld (hl),255
.pn:    inc l
        djnz .pix
        pop bc
.bytedone:
        djnz .byte
.skip:  ld hl,(P_SRC)
        ld a,(P_N)
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld (P_SRC),hl
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jp nz,.row
        nextreg 0x50,255
        ret

; l2_row: A = screen row -> slot 0 = the back buffer's page, H = row in it. AF lost.
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

; rect_add: note the figure's box, clipped to the play rows and to 32 cells, for
; the next clear of this buffer: row, rows, cell, cells.
rect_add:
        ld a,(P_Y)
        ld b,a
        ld a,(P_ROWS)
        add a,b                 ; end y (may pass 255: no row table there either)
        jr nc,.endok
        ld a,255
.endok: cp 192
        jr c,.e2
        ld a,192
.e2:    ld c,a                  ; end y, clipped
        ld a,b
        cp 32
        jr nc,.s2
        ld a,32
.s2:    ld b,a                  ; start y, clipped
        ld a,c
        sub b
        ret c
        ret z
        ld c,a                  ; rows
        ld a,b
        sub ROW_FIRST
        ld hl,(V_RECT)
        ld (hl),a
        inc l
        ld (hl),c
        inc l
        ld a,(P_X)
        add a,X_LEFT
        jr nc,.x2
        ld a,255
.x2:    rrca
        rrca
        rrca
        and 31
        ld (hl),a
        ld b,a
        inc l
        ld a,(P_N)
        inc a                   ; a shifted figure spans one more cell
        add a,b
        cp 33
        jr c,.w2
        ld a,32
.w2:    sub b
        ld (hl),a
        inc l
        ld (V_RECT),hl
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
        ld a,(hl)               ; cells
        add a,a
        add a,a
        add a,a
        ld c,a                  ; width, pixels (32 cells: 0 means 256, not used here)
        dec l
        ld a,(hl)               ; cell
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        dec l
        ld d,(hl)               ; rows
        dec l
        ld e,(hl)               ; row
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
R_COPY EQU -25
R_RENDER EQU -12
R_PLOT EQU -12
R_WAIT EQU -12
R_HIDE EQU -12
R_MSG EQU -11

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "ruffreddy_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,X_LEFT
        nextreg 0x18,231
        nextreg 0x18,0
        nextreg 0x18,159
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
        ; both buffers transparent: 5 pages (rows 0..159) each
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
l2_pal: defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        defb 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:
        SAVEBIN "ruffreddy_setup.bin",setup,setup_end-setup
