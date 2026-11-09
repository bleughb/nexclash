; Army Moves (Dinamic/Imagine, 128K, parts 1 and 2): clash removal by a Layer 2 figure overlay.
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
ISR_LINES EQU 9
P_CNT EQU 0x3E47
V_POLL EQU 0x3E48             ; word
R_BUF EQU 0x3E80               ; gfx + mask row, up to 64 bytes
RECTS_A EQU 0x2700             ; 4 bytes a rectangle
RECTS_B EQU 0x3C00
RECT_MAX EQU 60
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 120                ; below the play area, shake included
BEAM_HI EQU 240
K_PLOT EQU 107
K_COPY EQU 119
K_REST EQU 119
K_TILE EQU 32                  ; a scene's tiles: their own drawing comes out of this window
V_K2 EQU 0x3E7E                ; part 2's restore and copy K: the mode's own
ATTR_P EQU 0x5C8F
V_L2ON EQU 0x3E72
V_ENH EQU 0x3E50               ; Enhanced
V_BDT EQU 0x3E51               ; the Backdrop line
V_BDON EQU 0x3E52              ; this scene has its backdrop
V_S EQU 0x3E53                 ; the ring's offset, pixels
V_SRC EQU 0x3E54               ; word
V_FLIP EQU 0x3E56
V_FULLN EQU 0x3E57
V_ZDIRTY EQU 0x3E58
V_ZN EQU 0x3E59
V_TAB EQU 0x3E5A               ; word
V_BDP EQU 0x3E5C
V_BDP1 EQU 0x3E5D
V_BDP2 EQU 0x3E5E
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
T_W EQU 0x3E6E
T_FL EQU 0x3E6F
T_CLR EQU 0x3E70
T_CLEAN EQU 0x3E71
T_HOLE EQU 0x3E73
V_CACHE EQU 0x3E74               ; word: the last record looked up
V_CPART EQU 0x3E76
V_CPAGE EQU 0x3E77
V_COFF EQU 0x3E78               ; word
V_CNB EQU 0x3E7A
V_DISP EQU 0x3E7B               ; word
V_RD EQU 0x3E7D
RB EQU 0x3D00                  ; a row, 256 bytes
TAB1 EQU 0x2000                ; part 1's graphics: record, page, offset, gfx bytes a row
TAB2 EQU 0x2300
ZXTAB EQU 0x2600               ; the 16 Spectrum colours as palette indices
C_PAGE EQU 44
S_PAGE EQU 48
ZONE_Y EQU 88
ZONE_H EQU 32
V_PART EQU 0x3E4A
V_CAP EQU 0x3E4B              ; 1: the last copy's painted cells are still on the original's screen
FIG_END_HI EQU 0xD4
CLEAN_SKY EQU 0x77C1
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
        MACRO PLOT_HOOK flag, body
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld a,(flag)
        call l2_plot
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld hl,(0x5C78)
        ld (V_FR),hl
        COPY_BODY body
        WAIT_K K_PLOT
        LEAVE_R
        ret
        ENDM

h_plot1:
        PLOT_HOOK 0xA36C,0xA3D4

; ---- restore: clean buffer to the work buffer at 28 MHz --------------------

        MACRO WAIT_KV
        ld a,(V_SPEED)
        ld c,a
        ld a,(V_K2)
        call hlib_pace_waitk
        call isr_extra
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM
        MACRO RESTORE_HOOK body, part, kw
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,part
        ld (V_PART),a
        xor a
        ld (V_CAP),a
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
        RESTORE_HOOK 0xA462,1,WAIT_K K_REST
h_rest2:
        RESTORE_HOOK 0xA462,2,WAIT_KV

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
        pop hl                  ; DE at the return: the end of the attributes the original copied
        pop de
        ld de,0x6B90
        push de
        push hl
        ld a,(shake)
        or a
        jr z,.ns
        ld a,188
.ns:    nextreg 0x17,a
        call l2_publish
        ld a,1
        ld (V_CAP),a
        kw
        LEAVE_R
        ret
        ENDM

h_copy1:
        COPY_HOOK 0xA462,V_ZERO,WAIT_K K_COPY
h_copy2:
        COPY_HOOK 0xA462,V_ZERO,WAIT_KV

; ---- the game shows or clears the screen itself: the overlay goes off --------
h_cls:
        ENTER
        nextreg 0x69,0
        xor a
        ld (V_CAP),a
        ld a,(V_ENH)
        or a
        call nz,e_slowclr
        ld a,-13
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
h_fill:                         ; BA84: PUSH HL / POP DE / INC DE, displaced
        ENTER
        ld a,h
        cp 0x5B
        jr nc,.keep
        cp 0x40
        jr c,.keep
        nextreg 0x69,0
        xor a
        ld (V_CAP),a
        ld a,(V_ENH)
        or a
        jr z,.keep
        ld a,h
        cp 0x58
        call c,e_slowclr
.keep:  ld a,(V_ENH)
        or a
        jr z,.k2
        ld a,h
        cp 0x6B
        jr nz,.k2
        ld a,l
        cp 0x90
        call z,e_slowfill
.k2:    ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        push hl
        pop de
        inc de
        jp 0xBA87
h_show:                         ; CALL A460: the game captures the screen into the clean buffer. A cell painted
        ENTER                   ; at the last copy shows the clean colour here, not the painted one the
        HLIB_SPEED_IN_ABC V_SPEED ; original captures: put the work buffer's colour back in those cells first.
        ld a,(V_CAP)
        or a
        jr z,.done
        ld hl,0x69F0
        ld de,0x77C0
        ld bc,0x5840
.cell:  ld a,(de)
        cp (hl)
        jr z,.same
        ld a,(hl)
        ld (bc),a
.same:  inc hl
        inc de
        inc bc
        ld a,b
        cp 0x59
        jr nz,.cell
        ld a,c
        cp 0xE0
        jr nz,.cell
.done:  ld a,(V_ENH)
        or a
        call nz,e_capture
        HLIB_SPEED_OUT_A V_SPEED
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA460

h_tile:                         ; B944: LD HL,B9B2 / the body, whole
        ENTER
        ld hl,0xB9B2
        ld a,-22
        ld b,0
        jr tile_hook
h_clr:                          ; B93F: LD HL,B9BE / the body, whole
        ENTER
        ld hl,0xB9BE
        ld a,-21
        ld b,1
tile_hook:
        ld (V_DISP),hl
        ld (V_RD),a
        ld a,b
        ld (T_CLR),a
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call e_tile
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld hl,(0x5C78)
        ld (V_FR),hl
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld hl,(V_DISP)
        call 0xB947
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,(V_SPEED)
        ld c,a
        ld a,K_TILE
        call hlib_pace_waitk
        call isr_extra
        ld a,(V_RD)
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret
h_strip:                        ; B164: LD HL,(B736) displaced; the record about to lose its mask
        ENTER
        ld hl,(0xB736)
        ld de,0xA62A
        or a
        sbc hl,de
        jr z,.fl
        ld hl,(0xB736)
        ld (V_SRC),hl
        xor a
        ld (V_FLIP),a
.fl:    ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld hl,(0xB736)
        jp 0xB167
h_flip:                         ; A5DB: CALL A607 displaced; the record about to be mirrored
        ENTER
        ld hl,(0xB736)
        ld (V_SRC),hl
        ld a,1
        ld (V_FLIP),a
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        call 0xA607
        jp 0xA5DE
h_scrl:                         ; A77F: the scrolling rows go 4 pixels left
        ENTER
        ld a,(V_S)
        add a,4
        cp 240
        jr c,.s
        xor a
.s:     ld (V_S),a
        ld a,1
        ld (V_ZDIRTY),a
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        ld a,(0xA772)
        nextreg 0x51,255
        jp 0xA782
h_scrr:                         ; A809: 4 pixels right
        ENTER
        ld a,(V_S)
        or a
        jr nz,.s
        ld a,240
.s:     sub 4
        ld (V_S),a
        ld a,1
        ld (V_ZDIRTY),a
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        ld a,(0xA772)
        nextreg 0x51,255
        jp 0xA80C

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
        jr nz,.painted
        ld a,(V_PART)
        cp 1
        jr nz,.scenery
        ld hl,(0xB736)
        ld a,h
        cp FIG_END_HI
        jr nc,.scenery
        cp 0xC0
        jr c,.scenery
        ld a,(CLEAN_SKY)        ; a figure the game leaves to the cell's ink: the sky's
        jr .ink
.painted:
        ld a,(ATTR_P)
.ink:   ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld (V_INK),a
        ld a,254
        ld (V_OPAQUE),a
        jr .colour_done
.scenery:
        ld a,255
        ld (V_INK),a
        ld (V_OPAQUE),a
.colour_done:
        push ix
        ld a,(iy+1)
        ld (P_ROWS),a
        ld a,(iy+0)
        add a,16
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
        ld (hl),16
        inc l
        ld (hl),104
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
        ld a,(V_ENH)
        or a
        jr z,.nc
        ld (V_L2ON),a
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
.nc:    ld a,b
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

; The hook-side wrappers of the slow Enhanced clears: 28 MHz, the time as debt.
e_slowclr:
        xor a
        ld (V_L2ON),a
        HLIB_SPEED_IN_ABC V_SPEED
        call hlib_debt_open
        call e_panelclr
        jr e_slowend
e_slowfill:
        HLIB_SPEED_IN_ABC V_SPEED
        call hlib_debt_open
        call e_fillc
e_slowend:
        ld a,8
        call hlib_debt_close
        HLIB_SPEED_OUT_A V_SPEED
        ret
        INCLUDE "army_moves_enh.inc"
rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3C00
        SAVEBIN "armymoves_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,16
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
        nextreg 0x43,0          ; the ULA's: the colours under the panel and on the menus
        ld hl,e_ula
        nextreg 0x40,0
        ld b,16
.lu:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .lu
        ld hl,e_ula
        nextreg 0x40,16
        ld b,16
.lv:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .lv
        ld d,L2_BANK_A*2
        ld e,6
        ld a,0xFF
        call .fill
        ld d,L2_BANK_B*2
        ld e,6
        ld a,0xFF
        call .fill
        ld d,C_PAGE
        ld e,4
        ld a,0xFF
        call .fill
        ld d,S_PAGE
        ld e,4
        xor a
        call .fill
        nextreg 0x50,255
        ret
.fill:  ld (.v+1),a
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
.v:     ld (hl),0
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        ret
e_ula:  defs 16,0
e_palette:
        defs 512,0
setup_end:
        SAVEBIN "armymoves_setup.bin",setup,setup_end-setup
