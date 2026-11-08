; Flying Shark (Graftgold / Firebird, 1987, 48K): a one-pixel outline on Layer 2.
;
; The play area is monochrome by design: no colour clash to fix. The ULA bitmap and
; attributes stay the original's, every byte. Figures lost against the scenery get
; the standard outline: white, one pixel, drawn on a double-buffered Layer 2 from the
; game's own plot parameters. Bullets (8-line plots) get none.
;
; The game runs from its 25 Hz interrupt handler, interrupts off throughout:
;   C772 blit: the whole play area from a cell pointer list, 84,094 T.
;   AC8D plot: every figure into cell copies, the pointers changed; drawn by the next blit.
; h_plot runs AC8D as it is, at the caller's clock (it beeps as it goes). Its threaded plot steps
; (table A000) go through capture veneers that note each plot's parameters; nothing else is added.
; h_blit, in the blit's own time: clears and draws the outlines, waits for the beam below
; the play area, flips, runs C772 whole at 28 MHz, waits out the rest of its time.
; So the bitmap arrives below the play area in one piece, and the outline with it.
;
; All game RAM is read only here. Game SP is kept for the bodies: their saved SP operands
; (C81F, ACB5) stay the original's.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
GRID EQU 0x3400                ; 8 columns x 32 lines, column 0 and line 0 kept empty
CAPS EQU 0x3500                ; 7 bytes a plot, room for 144: the game has under 40 actors, at most 2 steps each
RECTS_A EQU 0x3900             ; what each buffer shows: 6 bytes a figure, 40 of them
RECTS_B EQU 0x3A00
RECT_MAX EQU 40
DIR_PAGE EQU 47                ; 1,024 entries of 8 bytes: src, step, columns, list page, list address
LIST_FIRST EQU 48              ; list pages (RAM only, nothing in the .nex)
LIST_LAST EQU 93
LIST_ROOM EQU 1600             ; the longest list
V_YMAX EQU 0x3BEA
V_DIR EQU 0x3BEC               ; word
V_FREE EQU 0x3BEE              ; word: next list byte
V_FREEP EQU 0x3BF0             ; page of it
V_LIST EQU 0x3BF2              ; word
P_W EQU 0x3BF4
PLAY_X0 EQU 56
PLAY_X1 EQU 199
STK EQU 0x3BA0
HLIB_V_R EQU 0x3BA0
HLIB_V_PACE EQU 0x3BA4
V_SPEED EQU 0x3BC0
V_SP EQU 0x3BC2
V_R0 EQU 0x3BC4
V_BACK EQU 0x3BC5              ; L2 16K bank of the back buffer
V_PLOTTED EQU 0x3BC6           ; 1: AC8D ran since the last blit
V_N EQU 0x3BC7                 ; plots captured
V_CAP EQU 0x3BC8               ; word: next capture
V_T EQU 0x3BCA                 ; word: the step's real target
V_RECT EQU 0x3BCC              ; word: end of the back buffer's rectangle list
P_NEXT EQU 0x3BCE              ; word: next capture to draw
P_LEFT EQU 0x3BD0
P_IDX EQU 0x3BD1
P_E EQU 0x3BD2
P_D EQU 0x3BD3
P_SRC EQU 0x3BD4               ; word
P_COLS EQU 0x3BD6
P_H EQU 0x3BD7
P_Y EQU 0x3BD8
P_COL EQU 0x3BD9
P_C EQU 0x3BDA
P_L EQU 0x3BDB
P_PUNCH EQU 0x3BDC
P_RING EQU 0x3BDD
P_PAGE EQU 0x3BDE
P_GC EQU 0x3BDF
P_RC EQU 0x3BE0
P_RX EQU 0x3BE1
P_RW EQU 0x3BE2
P_RR EQU 0x3BE3
V_POLL EQU 0x3BE4              ; word
P_YMAX EQU 0x3BE6
V_RET EQU 0x3BE8               ; word
HLIB_PACE_NL EQU 312
L2_BANK_A EQU 16
L2_BANK_B EQU 19
INK EQU 15                     ; bright white
CLEAR EQU 255                  ; transparent
PLAY_COL0 EQU 7
PLAY_COL1 EQU 24
Y_OFFSET EQU 24                ; screen y = the plot's E - 24
BEAM_LO EQU 192                ; the first line below the play area
BAIL_LINES EQU 296             ; drawn so late (the blit starts about line 13): go, rather than slow
T_BLIT EQU 6314                ; C772's own time in JNext with contention, 1/16 lines (88,900 T at 224 T a line)
D_PLOT EQU 7                    ; 1/16 lines: a capture veneer
D_HOOK EQU 78                   ; 1/16 lines: h_plot's own time
REV EQU 0x9A00
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"

; ---- entries first: the veneers shared with the hidden ROM page stay under 0x2C80 -----

        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,STK
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
        ret
        ENDM

; The body on the game's own SP, entered as the game's CALL would enter it. Its return address (the word the game's
; CALL of the hook pushed) is borrowed for the way back and put back after, so RAM stays the original's, stack too.
; R afterwards is the entry R + the M1s it took.
        MACRO BODY target
        ld hl,(V_SP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_RET),de
        ld de,.back
        ld (hl),d
        dec hl
        ld (hl),e
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld sp,(V_SP)
        jp target
.back:  ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld hl,(V_SP)
        ld de,(V_RET)
        ld (hl),e
        inc hl
        ld (hl),d
        ENDM

; ---- the plot pass: AC8D as it is, at the caller's clock: it beeps (port FE) as it goes ---
; Only the capture veneers are added; their time goes to the debt, repaid by the next blit's window.
h_plot:
        ENTER
        HLIB_SPEED_IN V_SPEED
        xor a
        ld (V_N),a
        ld hl,CAPS
        ld (V_CAP),hl
        HLIB_SPEED_OUT V_SPEED
        BODY 0xAC8D
        HLIB_SPEED_IN V_SPEED
        ld a,1
        ld (V_PLOTTED),a
        ; the veneers' M1s are not the game's: 35 a plot; their time: D_PLOT a plot, plus the hook's own: D_HOOK
        ld a,(V_N)
        ld c,a
        add a,a
        ld b,a
        add a,a
        add a,a
        add a,a
        add a,a
        add a,b
        add a,c
        ld b,a
        ld a,(V_R0)
        sub b
        ld (V_R0),a
        ld a,c
        ld hl,D_HOOK
        ld de,D_PLOT
        or a
        jr z,.nd
        ld b,a
.mul:   add hl,de
        djnz .mul
.nd:    call hlib_debt_add
        ld a,R_PLOT
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R

; ---- the blit; h_blank: the same for a list the game has just blanked ----------
        MACRO BLIT_HOOK blank, delta
        ENTER
        HLIB_SPEED_IN V_SPEED
        IF blank
        xor a
        ld (V_PLOTTED),a
        ENDIF
        call blit_before
        BODY 0xC772
        call blit_after
        ld a,delta
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ENDM

h_blit: BLIT_HOOK 0, R_BLIT
h_blank:
        BLIT_HOOK 1, R_BLANK

; ---- the small handler (title, menus, transitions): the outline goes off --------
; A0B0 is PUSH AF / PUSH HL / LD HL,9BA2; a JP here, and on to A0B5 with those done.
h_idle:
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,r
        ld (HLIB_V_R),a
        nextreg 0x69,0
        xor a
        ld (V_PLOTTED),a
        ld a,R_IDLE
        call hlib_r_set
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        push af
        push hl
        ld hl,0x9BA2
        jp 0xA0B5
veneers_end:
        ASSERT veneers_end < 0x2C80

        INCLUDE "lib/hlib_pace.asm"

; ---- capture veneers: the table A000 points here; only AC8D's steps pass -------
; At a step HL and AF are free: every plotter loads its own. SP is the table's.
        MACRO CAP idx, target
        ld hl,target
        ld (V_T),hl
        ld a,idx
        jp cap
        ENDM
cap_00: CAP 0x00,0xAFC3
cap_02: CAP 0x02,0xB121
cap_04: CAP 0x04,0xB005
cap_06: CAP 0x06,0xB12B
cap_08: CAP 0x08,0xB072
cap_0a: CAP 0x0A,0xB13F
cap_0c: CAP 0x0C,0xB0B4
cap_0e: CAP 0x0E,0xB14A
cap_10: CAP 0x10,0xB3FE
cap_12: CAP 0x12,0xB1BE
cap_14: CAP 0x14,0xB452
cap_16: CAP 0x16,0xB24A
cap_18: CAP 0x18,0xB4AA
cap_1a: CAP 0x1A,0xB2DA
cap_1c: CAP 0x1C,0xB502
cap_1e: CAP 0x1E,0xB36A
cap:    nextreg 0x07,3
        ld hl,(V_CAP)
        ld (hl),a
        inc hl
        ld a,(0x9C13)
        ld (hl),a
        inc hl
        ld a,(0x9C14)
        ld (hl),a
        inc hl
        ld a,(0x9C15)
        ld (hl),a
        inc hl
        ld a,(0x9C16)
        ld (hl),a
        inc hl
        ld a,(0x9C1A)
        ld (hl),a
        inc hl
        ld a,(0x9C1B)
        ld (hl),a
        inc hl
        ld (V_CAP),hl
        ld hl,V_N
        inc (hl)
        ld a,(V_SPEED)
        nextreg 0x07,a
        ld hl,(V_T)
        jp (hl)

; ---- before the blit: outlines drawn on the back buffer, the beam, then the flip -----
; From line 192 to the frame's end no line of the play area is on show, and the blit (about 60 lines at 28 MHz, top row
; first) stays ahead of the beam; so the outline can go up just before the blit and the two still arrive together.
blit_before:
        call hlib_pace_open
        ld a,(V_PLOTTED)
        or a
        ret z
        call l2_redraw
        call hlib_pace_tick
        ld hl,0
        ld (V_POLL),hl
.bm:    ld hl,(V_POLL)
        dec hl
        ld (V_POLL),hl
        ld a,h
        or l
        jr z,.go                ; no line counter
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE + 2)
        ld de,BAIL_LINES
        or a
        sbc hl,de
        jr nc,.go               ; too late to wait
        ld hl,(HLIB_V_PACE)
        ld de,BEAM_LO
        or a
        sbc hl,de
        jr c,.bm
.go:    jp l2_publish

; ---- after the blit: off if nothing was plotted; the rest of its time ----------------
blit_after:
        ld a,(V_PLOTTED)
        or a
        jr nz,.pub
        nextreg 0x69,0
.pub:   xor a
        ld (V_PLOTTED),a
        ld hl,T_BLIT
        ld a,(V_SPEED)
        jp hlib_pace_wait

; l2_publish: the back buffer becomes the front; the other buffer's list next.
l2_publish:
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
        ret
V_LIST_A: defw RECTS_A
V_LIST_B: defw RECTS_B

; ---- Layer 2: each graphic's outline is a list of pixels, made once and kept in Next pages (RAM only) --------
; Clear what this buffer last showed, by the same lists; draw this pass's plots.
; While drawing: slot 0 = a list page or the directory, slots 2 and 3 = two Layer 2 pages in a row.
l2_redraw:
        ld a,(0x9C00)           ; the blit shows lines up to 183 + the fine scroll
        and 7
        add a,184
        ld (V_YMAX),a
        call l2_clear
        ld a,(V_N)
        or a
        jr z,.done
        ld (P_LEFT),a
        ld hl,CAPS
        ld (P_NEXT),hl
.fig:   call l2_fig
        call hlib_pace_tick     ; a long draw: never a whole frame unseen
        ld hl,P_LEFT
        dec (hl)
        jr nz,.fig
.done:  nextreg 0x50,255
        nextreg 0x52,10
        nextreg 0x53,11
        ret

; l2_clear: every figure this buffer showed, again, in the transparent colour; the list emptied.
l2_clear:
        ld a,CLEAR
        ld (ink_list.colour+1),a
        ld (ink_slow.colour+1),a
        ld a,192
        ld (ink_list.limit+1),a
        ld (ink_slow.limit+1),a
        ld a,(V_BACK)
        cp L2_BANK_A
        ld de,RECTS_A
        jr z,.a
        ld de,RECTS_B
.a:     ld hl,(V_RECT)
        ld (.end+1),hl
        ld (.base+1),de
.lp:
.end:   ld hl,0
        or a
        sbc hl,de
        jr z,.out
        ld a,(de)
        ld (P_PAGE),a
        inc de
        ld a,(de)
        ld l,a
        inc de
        ld a,(de)
        ld h,a
        inc de
        ld a,(de)
        ld (P_Y),a
        inc de
        ld a,(de)
        ld (P_COL),a
        inc de
        ld a,(de)
        ld (P_H),a
        inc de
        push de
        ex de,hl
        ld a,(P_PAGE)
        nextreg 0x50,a
        call ink_list
        pop de
        jr .lp
.out:
.base:  ld hl,0
        ld (V_RECT),hl
        ld a,INK
        ld (ink_list.colour+1),a
        ld (ink_slow.colour+1),a
        ld a,(V_YMAX)
        ld (ink_list.limit+1),a
        ld (ink_slow.limit+1),a
        ret

; ink_list: DE = the list (slot 0), P_Y, P_COL, P_H: the pixels on the back buffer.
ink_list:
        ld a,(P_Y)
        ld b,a
        cp 192
        jp nc,ink_slow          ; above the top: y wrapped
        ld a,(P_H)
        add a,b
.limit: cp 192
        jp nc,ink_slow
        ld a,(P_COL)
        cp PLAY_COL0
        jp c,ink_slow
        ld c,a
        ld a,(P_W)
        add a,c
        cp PLAY_COL1+2
        jp nc,ink_slow
        ; all on show: two L2 pages at 0x4000, 64 rows in a row
        ld a,b
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        ld a,b
        and 31
        add a,0x40
        ld b,a                  ; B = the row's high byte for line 0
        ld a,(P_COL)
        add a,a
        add a,a
        add a,a
        ld c,a                  ; C = x of column 0
.lp:    ld a,(de)
        inc de
        cp 255
        ret z
        add a,b
        ld h,a
        ld a,(de)
        inc de
        add a,c
        ld l,a
.colour:
        ld (hl),INK
        jr .lp

; ink_slow: the same, each pixel tested: part off the play area, or the figure across the top.
ink_slow:
        ld a,255
        ld (P_RC),a             ; no page yet
        ld a,(P_COL)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(P_Y)
        ld b,a
.lp:    ld a,(de)
        inc de
        cp 255
        ret z
        add a,b
.limit: cp 192
        jr nc,.skip
        ld l,a
        rlca
        rlca
        rlca
        and 7
        ld h,a
        ld a,(P_RC)
        cp h
        jr z,.same
        ld a,h
        ld (P_RC),a
        push hl
        ld a,(V_BACK)
        add a,a
        add a,h
        nextreg 0x52,a
        pop hl
.same:  ld a,l
        and 31
        add a,0x40
        ld h,a
        ld a,(de)
        inc de
        add a,c
        ld l,a
        cp PLAY_X0
        jr c,.lp
        cp PLAY_X1+1
        jr nc,.lp
.colour:
        ld (hl),INK
        jr .lp
.skip:  inc de
        jr .lp

; l2_fig: the next capture.
l2_fig:
        ld hl,(P_NEXT)
        ld de,P_IDX
        ld bc,7
        ldir                    ; P_IDX, P_E, P_D, P_SRC, P_COLS, P_H
        ld (P_NEXT),hl
        ld a,(P_COLS)
        or a
        ret z
        cp 5
        ret nc                  ; the game has none so wide; a guard for the grid
        ld a,(P_H)
        cp 8
        ret z                   ; 8-line plots are bullets: no outline
        or a
        ret z
        cp 17
        ret nc
        ; a first stage with a second to come is one figure: the second has the mask
        ld a,(P_IDX)
        cp 0x10
        jr nc,.one
        and 2
        jr nz,.one
        ld a,(P_LEFT)
        dec a
        jr z,.one
        ld a,(hl)               ; HL = the next capture
        cp 0x10
        jr nc,.one
        and 2
        ret nz
.one:   ld a,(P_E)
        sub Y_OFFSET+1
        ld (P_Y),a
        ld a,(P_D)
        sub 0x88-PLAY_COL0+1    ; the column before the plot's first
        ld (P_COL),a
        ld a,(P_COLS)
        add a,2
        ld (P_W),a
        ld a,(P_H)
        add a,2
        ld (P_RX),a
        call list_find          ; -> DE = the list, its page in slot 0 and P_PAGE; carry: none and no room
        ret c
        ; note it for this buffer's next clear
        ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*6
        jr nc,.nr
        ld a,(P_PAGE)
        ld (hl),a
        inc l
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld a,(P_Y)
        ld (hl),a
        inc l
        ld a,(P_COL)
        ld (hl),a
        inc l
        ld a,(P_RX)
        ld (hl),a
        inc l
        ld (V_RECT),hl
.nr:    ld a,(P_RX)
        ld (P_H),a
        jp ink_list

; list_find: the graphic's list: directory entry (src, step, columns) or made now.
list_find:
        nextreg 0x50,DIR_PAGE
        ld hl,(P_SRC)
        ld a,h
        srl a
        rr l
        srl a
        rr l
        srl a
        rr l
        srl a
        rr l                    ; (src >> 4), L low
        and 3
        ld h,a
        ld a,(P_IDX)
        add a,a
        add a,a
        xor h
        and 3
        ld h,a
        ld a,(P_IDX)
        add a,a
        add a,a
        add a,a
        xor l
        ld l,a
        add hl,hl
        add hl,hl
        add hl,hl               ; x 8, under 0x2000
        push hl
        ld a,(P_SRC)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(P_SRC+1)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(P_IDX)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(P_COLS)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(hl)
        or a
        jr z,.make              ; page 0: empty
        ld (P_PAGE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        nextreg 0x50,a
        or a
        ret
.make:  pop hl
        ld (V_DIR),hl
        ; room for the longest list in this page, or the next
        ld hl,(V_FREE)
        ld de,LIST_ROOM
        add hl,de
        ld a,h
        cp 0x20
        jr c,.fits
        ld a,(V_FREEP)
        inc a
        cp LIST_LAST+1
        ccf
        ret c                   ; no room: this figure goes without
        ld (V_FREEP),a
        ld hl,0
        ld (V_FREE),hl
.fits:  ld a,(V_FREEP)
        ld (P_PAGE),a
        ld hl,(V_DIR)
        ld a,(P_SRC)
        ld (hl),a
        inc hl
        ld a,(P_SRC+1)
        ld (hl),a
        inc hl
        ld a,(P_IDX)
        ld (hl),a
        inc hl
        ld a,(P_COLS)
        ld (hl),a
        inc hl
        ld a,(P_PAGE)
        ld (hl),a
        inc hl
        ld de,(V_FREE)
        ld (hl),e
        inc hl
        ld (hl),d
        push de
        nextreg 0x50,a
        call grid_zero
        call grid_fill
        ; one pass: column by column, from the one before the plot's first
        ld a,(P_W)
        ld (P_GC),a
        xor a
        ld (grid_col.x0+1),a
        ld hl,(V_FREE)
        ld (V_LIST),hl
        ld hl,GRID+32           ; grid column 1 = the plot's column -1
.col:   push hl
        call grid_col
        pop hl
        ld a,l
        add a,32
        ld l,a
        ld a,(grid_col.x0+1)
        add a,8
        ld (grid_col.x0+1),a
        ld a,(P_GC)
        dec a
        ld (P_GC),a
        jr nz,.col
        ld hl,(V_LIST)
        ld (hl),255
        inc hl
        ld (V_FREE),hl
        pop de
        or a
        ret

; grid_zero: the columns before and after the plot's, all P_H + 4 lines; the plot's own, the lines round it.
grid_zero:
        ld a,(P_H)
        add a,4
        ld c,a
        ld h,GRID>>8
        ld de,0x0020            ; E = 32
        xor a
        ld l,a
        call .col
        ld l,e
        call .col
        ld a,(P_COLS)
        add a,2
        rrca
        rrca
        rrca
        ld l,a
        call .col
        ld a,l
        and 0xE0
        add a,e
        ld l,a
        call .col
        ; the plot's own columns: lines 0, 1, H + 2, H + 3
        ld a,(P_COLS)
        ld b,a
        ld a,(P_H)
        add a,2
        ld c,a
        ld l,0x40
.own:   ld a,l
        and 0xE0
        ld l,a
        ld (hl),d               ; D = 0
        inc l
        ld (hl),d
        ld a,l
        add a,c
        dec a
        ld l,a
        ld (hl),d
        inc l
        ld (hl),d
        ld a,l
        and 0xE0
        add a,e
        ld l,a
        djnz .own
        ret
.col:   ld b,c
.z:     ld (hl),d
        inc l
        djnz .z
        ret

; grid_fill: the plot's bytes as its step lays them, as opaque bits. Grid column 2 = the plot's first,
; line 2 = its first.
grid_fill:
        ld hl,(P_SRC)
        xor a
        ld (P_C),a
.c2:    ld a,(P_IDX)
        and 4
        ld a,(P_C)
        jr z,.cn
        ld b,a
        ld a,(P_COLS)
        dec a
        sub b
.cn:    add a,2
        rrca
        rrca
        rrca
        ld e,a
        ld d,GRID>>8
        ld a,(P_IDX)
        and 8
        ld a,2
        jr z,.ys
        ld a,(P_H)
        inc a
.ys:    or e
        ld e,a
        ld a,(P_H)
        ld (P_L),a
.l2:    ld c,(hl)               ; the data
        inc hl
        ld b,(hl)               ; the mask index
        inc hl
        push hl
        ld h,REV>>8
        ld a,(P_IDX)
        and 4
        jr nz,.xf
        ld l,b
        ld b,(hl)               ; B = the mask, C = the data
        jr .kind
.xf:    ld l,c
        ld c,(hl)               ; x flip: the mask as it is, the data reversed
.kind:  ld a,(P_IDX)
        cp 0x10
        jr nc,.masked
        and 2
        jr nz,.masked
        ld a,c                  ; a first stage: data only
        jr .put
.masked:
        ld a,b
        cpl
        or c
.put:   ld (de),a
        pop hl
        ld a,(P_IDX)
        and 8
        jr nz,.up
        inc e
        jr .ln2
.up:    dec e
.ln2:   ld a,(P_L)
        dec a
        ld (P_L),a
        jr nz,.l2
        ld a,(P_C)
        inc a
        ld (P_C),a
        ld b,a
        ld a,(P_COLS)
        cp b
        jr nz,.c2
        ret

; grid_col: HL = this grid column (GRID + 32 x n), n >= 1: its ring pixels on the list at V_LIST.
grid_col:
        inc l                   ; line 1: the row above the plot
        ld a,(P_H)
        add a,2
        ld c,a
        ld b,0                  ; the line in the list
.ln:    ld a,(hl)
        ld e,a                  ; O
        add a,a
        ld d,a
        ld a,e
        srl a
        or d
        dec l
        or (hl)
        inc l
        inc l
        or (hl)
        dec l
        ld d,a
        ld a,l
        add a,32
        ld l,a
        bit 7,(hl)
        jr z,.n1
        set 0,d
.n1:    sub 64
        ld l,a
        bit 0,(hl)
        jr z,.n2
        set 7,d
.n2:    add a,32
        ld l,a
        ld a,e
        cpl
        and d                   ; R = neighbours, not opaque
        jr z,.next
        push hl
        push bc
        ld d,a
.x0:    ld c,0
        ld hl,(V_LIST)
.bit:   sla d
        jr nc,.nb
        ld (hl),b
        inc hl
        ld (hl),c
        inc hl
.nb:    inc c
        ld a,d
        or a
        jr nz,.bit
        ld (V_LIST),hl
        pop bc
        pop hl
.next:  inc l
        inc b
        dec c
        jr nz,.ln
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < GRID
        SAVEBIN "flyingshark_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,56
        nextreg 0x18,199
        nextreg 0x18,0
        nextreg 0x18,191
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
        ld a,DIR_PAGE
        nextreg 0x50,a
        ld hl,0
        ld (hl),l
        ld de,1
        ld bc,0x1FFF
        ldir
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
        SAVEBIN "flyingshark_setup.bin",setup,setup_end-setup

; R deltas: M1s of the original minus the hook's own around the body (calibrated by the replay, hooklib.r_check)
R_PLOT EQU -24
R_BLIT EQU -24
R_BLANK EQU -24
R_IDLE EQU -13
