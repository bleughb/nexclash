; Ruff and Reddy (Hi-Tec, 128K): Enhanced colours on a full Layer 2.
;
; Default mode lives in ruff_and_reddy_hooks.asm and is not touched. Enhanced keeps every game byte
; and the ULA as they are. A new room is painted on a clean Layer 2 canvas from the Spec256 set's
; tiles and copied to both display buffers; each pass restores the boxes it drew last time from the
; clean canvas and draws the figures in the game's plot order from colour images of the same bytes.
; A pixel the set paints 255 stays transparent: the ULA's own ink or paper shows, as Spec256 does.
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
V_ROOM EQU 0x3E37
V_RECT EQU 0x3E3A              ; word: end of the back buffer's rectangle list
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_N EQU 0x3E3F                 ; bytes a row of the source
V_Q EQU 0x3E42                 ; word: end of the pass's figure list
V_ROW EQU 0x3EA0
V_QBUF EQU 0x3E80              ; 4 bytes a figure: kind, x, y, number; 6 at most
P_R EQU 0x3E40
P_ROWS2 EQU 0x3E41
P_W EQU 0x3E46
P_D EQU 0x3E47
P_SKIP EQU 0x3E4A             ; word
P_SRC EQU 0x3E44               ; word
V_POLL EQU 0x3E48              ; word
RECTS_A EQU 0x3900             ; 4 bytes a rectangle; each list starts on a page
RECTS_B EQU 0x3B00
L2_BANK_A EQU 16
L2_BANK_B EQU 19
BEAM_LO EQU 160                ; below the play rows
BEAM_HI EQU 262
K_RENDER EQU 100
K_COPY EQU 118
K_ROOM EQU 104
ROW_FIRST EQU 32               ; the game's y of the buffer's first row (9CD0)
X_LEFT EQU 24                  ; the buffer's first column on the screen
ART_INDEX EQU 0x3A00            ; 3 bytes an image: page, address
N_BIG EQU 21
N_SMALL EQU 45
SKIP EQU 0xFE
TILE_PAGE EQU 50               ; 8 pages, 32 tiles each
CLEAN_PAGE EQU 44               ; the clean canvas: rows 0..159 in 5 pages
SLOT2 EQU 10
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
        call l2_restore
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

; ---- copy: entered from A506 in place of LD SP,9EA4. Wait for the beam below the
; play rows; the game's own copy runs at 28 MHz and comes back at h_copy_end.
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
; ---- the CALL AADD at 818B: the overlay off; the game draws the room at 28 MHz; paint it
h_room:
        ENTER
        nextreg 0x69,0
        HLIB_SPEED_IN V_SPEED
        ld a,(0xAB04)
        ld (V_ROOM),a
        call hlib_pace_open
        call hlib_nest_open     ; before the body: the room's map as the body draws it
        call paint_room
        ld a,8
        call hlib_nest_close
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0xAADD
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld hl,(V_SP)
        ld (0xAC6D),hl
        ld a,(V_SPEED)
        ld c,a
        ld a,K_ROOM
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
h_over:
        HIDE_HOOK 0xAC70,R_HIDE
; ---- D42B, in place of LD (D4A0),SP: the window is cleared for a message
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
; ---- D332, in place of XOR A / OUT (FE),A: a full-screen picture
h_title:
        ENTER
        nextreg 0x69,0
        ld a,R_TITLE
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        xor a
        out (0xFE),a
        jp 0xD335

; ---- Layer 2 ---------------------------------------------------------------
; paint_room: the room's tiles on the clean canvas, then the canvas to both buffers; their box lists start empty.
paint_room:
        ld a,(V_ROOM)
        ld l,a
        ld h,0
        add hl,hl
        ld de,0xAA65
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (P_SRC),de           ; the room's first tile number
        xor a
        ld (P_R),a              ; screen row
.band:  ld a,(P_R)
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        add a,CLEAN_PAGE
        nextreg 0x50,a
        ld a,(P_R)
        and 31
        ld (P_Y),a              ; high byte of the row in slot 0
        ld a,X_LEFT
        ld (P_X),a
        ld a,13
        ld (P_N),a
        ; this row's tile numbers, read with slot 2 as the game has it: a map can lie below 0x6000
        nextreg 0x52,SLOT2
        ld hl,(P_SRC)
        ld de,V_ROW
        ld bc,13
        ldir
        ld hl,V_ROW
        ld (P_SKIP),hl
.tile:  ld hl,(P_SKIP)
        ld a,(hl)
        inc hl
        ld (P_SKIP),hl
        ld c,a
        rlca
        rlca
        rlca
        and 7
        add a,TILE_PAGE
        nextreg 0x52,a
        ld a,c
        and 31
        add a,0x40
        ld h,a
        ld l,0
        ld a,(P_Y)
        ld d,a
        ld a,(P_X)
        ld e,a
        ld bc,256
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
        jr .row
.tnext: ld a,(P_X)
        add a,16
        ld (P_X),a
        ld hl,P_N
        dec (hl)
        jr nz,.tile
        call hlib_debt_tick
        ld hl,(P_SRC)
        ld de,130
        add hl,de
        ld (P_SRC),hl
        ld a,(P_R)
        add a,16
        ld (P_R),a
        cp 160
        jp c,.band
        ; the canvas to both buffers
        ld c,0
.pg:    ld a,c
        add a,CLEAN_PAGE
        nextreg 0x52,a
        ld a,c
        add a,L2_BANK_A*2
        nextreg 0x50,a
        push bc
        call dma_page
        pop bc
        ld a,c
        add a,L2_BANK_B*2
        nextreg 0x50,a
        push bc
        call dma_page
        call hlib_debt_tick
        pop bc
        inc c
        ld a,c
        cp 5
        jr nz,.pg
        ld hl,RECTS_A
        ld (V_LIST_A),hl
        ld hl,RECTS_B
        ld (V_LIST_B),hl
        ld (V_RECT),hl
        ld a,(V_BACK)
        cp L2_BANK_A
        jr nz,.b
        ld hl,RECTS_A
        ld (V_RECT),hl
.b:     nextreg 0x50,255
        nextreg 0x52,SLOT2
        ret
dma_page:
        ld hl,dma_prog
        ld bc,(dma_end-dma_prog)*256+0x6B
        otir
        ret
dma_prog:
        db 0x83,0xC3,0x7D
        dw 0x4000,8192
        db 0x14,0x10,0xAD
        dw 0x0000
        db 0x82,0xCF,0x87
dma_end:

; l2_restore: the boxes drawn in this buffer last time, from the clean canvas.
l2_restore:
        ld hl,(V_RECT)
        ld a,l
        or a
        ret z
.next:  dec l
        ld a,(hl)               ; cells
        add a,a
        add a,a
        add a,a
        ld (P_W),a              ; pixels
        dec l
        ld a,(hl)               ; cell
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        dec l
        ld a,(hl)               ; rows
        ld (P_N),a
        dec l
        ld a,(hl)               ; row
        ld (P_R),a
        push hl
.row:   ld a,(P_R)
        call l2_row             ; H = row in slot 0, A = back page
        and 7                   ; 32 + ... : page within the buffer
        ld a,(P_R)
        rlca
        rlca
        rlca
        and 7
        add a,CLEAN_PAGE
        nextreg 0x52,a
        ld d,h                  ; DE -> the back buffer
        ld a,(P_X)
        ld e,a
        ld a,h
        add a,0x40
        ld h,a
        ld l,e                  ; HL -> the clean canvas, in slot 2
        ld a,(P_W)
        ld c,a
        ld b,0
        ldir
        ld hl,P_R
        inc (hl)
        ld hl,P_N
        dec (hl)
        jr nz,.row
        pop hl
        ld a,l
        or a
        jr nz,.next
        ld (V_RECT),hl
        nextreg 0x50,255
        nextreg 0x52,SLOT2
        ret

; A figure's box for the next restore of this buffer: row, rows, cell, cells, clipped to the play window.
; P_Y = game y, P_ROWS = rows, P_X = L2 x (first pixel), P_N = pixels wide.
rect_add:
        ld a,(P_Y)
        ld b,a
        ld a,(P_ROWS)
        add a,b
        jr nc,.endok
        ld a,255
.endok: cp 192
        jr c,.e2
        ld a,192
.e2:    ld c,a
        ld a,b
        cp 32
        jr nc,.s2
        ld a,32
.s2:    ld b,a
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
        rrca
        rrca
        rrca
        and 31
        ld (hl),a
        ld b,a
        inc l
        ld a,(P_N)
        rrca
        rrca
        rrca
        and 31
        inc a                   ; a shifted figure spans one more cell
        add a,b
        cp 30
        jr c,.w2
        ld a,29                 ; cell 29 = x 232, the window's end
.w2:    sub b
        ld (hl),a
        inc l
        ld (V_RECT),hl
        ret

; the pass's figures, in order. V_QBUF: kind, x, y, number
draw_queue:
        ld hl,V_QBUF
.lp:    ld de,(V_Q)
        or a
        push hl
        sbc hl,de
        pop hl
        jr z,.done
        ld a,(hl)
        inc hl
        ld c,(hl)               ; x
        inc hl
        ld b,(hl)               ; y
        inc hl
        ld e,(hl)               ; number
        inc hl
        push hl
        call draw_one
        pop hl
        jr .lp
.done:  ld hl,V_QBUF
        ld (V_Q),hl
        nextreg 0x50,255
        nextreg 0x52,SLOT2
        ret

; A = kind (1 big, 0 small), C = x, B = y, E = number
draw_one:
        or a
        jr z,.small
        ld a,e
        cp N_BIG
        ret nc
        ld a,32
        ld (P_ROWS),a
        ld a,24
        jr .go
.small: ld a,e
        cp N_SMALL
        ret nc
        add a,N_BIG
        ld e,a
        ld a,16
        ld (P_ROWS),a
        ld a,16
.go:    ld (P_N),a              ; pixels wide
        ld a,b
        ld (P_Y),a
        ld a,c
        add a,X_LEFT
        jr c,.out
        ld (P_X),a
        cp 232
        jr c,.in
.out:   ret
.in:    ld a,e                  ; image number x 3
        ld l,a
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
        push de
        call rect_add
        pop de
        ; pixels a row, cut at x = 232
        ld a,(P_X)
        ld c,a
        ld a,232
        sub c
        ld b,a                  ; room to the edge
        ld a,(P_N)
        cp b
        jr c,.w
        ld a,b
.w:     ld (P_W),a
        ld b,a
        ld a,(P_N)
        sub b
        ld (P_D),a              ; source pixels left over a row
.row:   ld a,(P_Y)
        sub ROW_FIRST
        cp 160
        jr nc,.off
        call l2_row
        ld a,(P_X)
        ld l,a
        ld a,(P_W)
        ld b,a
.px:    ld a,(de)
        inc de
        cp SKIP
        jr z,.pn
        ld (hl),a
.pn:    inc l
        djnz .px
        ld a,(P_D)
        add a,e
        ld e,a
        jr nc,.next
        inc d
        jr .next
.off:   ld a,(P_N)
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
R_COPY EQU -25
R_RENDER EQU -12
R_PLOT EQU -12
R_WAIT EQU -12
R_HIDE EQU -12
R_MSG EQU -11
R_TITLE EQU -13

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3900
        SAVEBIN "ruffenh_rom.bin",rom_start,$-rom_start
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
        ld d,CLEAN_PAGE
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
        SAVEBIN "ruffenh_setup.bin",setup,setup_end-setup
