; Silkworm (Random Access / Virgin Games, 128K): the Enhanced colours on Layer 2.
;
; The game composes a back buffer each update (clear, stars, figures, ground) and copies it to
; the ULA, whose play area is white on black. This engine leaves all of that running, byte for
; byte. It composes the same picture in the set's own colours on a double-buffered Layer 2 over
; the ULA, figure by figure, from colour images of the game's graphics, and flips at the interrupt.
; A graphic with no colour image is drawn in white from the game's own bytes (the original look).
;
; Pace: the blit and the clear, under DI, run at the game's clock, as ever. The update's logic and its
; plots run at 28 MHz in K windows, which pay for Layer 2; a plot's DI lasts as long as ever, so the
; game misses the interrupts it missed. Interrupts run at the game's clock, so the AY music keeps its tempo.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 311
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_R0 EQU 0x3E35
V_X EQU 0x3E36                 ; screen x of this figure
V_Y EQU 0x3E37
V_H EQU 0x3E38                 ; rows
V_W EQU 0x3E39                 ; pixels wide
V_BACK EQU 0x3E3A              ; L2 16K bank of the back buffer
V_FLIP EQU 0x3E3B              ; 1: the back buffer waits to be shown
V_RECT EQU 0x3E3C              ; word: end of the back buffer's list
V_DOTS EQU 0x3E3E              ; word: end of the back buffer's star list
V_PHASE EQU 0x3E40             ; ground: pixels rotated
V_WHITE EQU 0x3E41             ; 1: a silhouette
V_N EQU 0x3E42
V_XE EQU 0x3E43
V_SPAN EQU 0x3E44
V_IR0 EQU 0x3E46               ; interrupt: R at entry, slot 1 found
V_I7 EQU 0x3E48
V_IR1 EQU 0x3E49
V_SRC EQU 0x3E4A               ; word
V_PG EQU 0x3E4C
V_F EQU 0x3E4D                 ; word: frame address
RECTS_A EQU 0x3800             ; 4 bytes a rectangle: y, rows, x, width
RECTS_B EQU 0x3900
RECT_MAX EQU 60
DOTS_A EQU 0x3A00              ; 2 bytes a star: y, x
DOTS_B EQU 0x3A80
L2_A EQU 16
L2_B EQU 19
PG_TABLE EQU 44                ; frame table, then the ground patterns
PG_GROUND EQU 45
PG_FRAMES EQU 48
INK_WHITE EQU 1                ; palette index of the set's FF pixel on the sky
MMU6 EQU 0
MMU5 EQU 5
K_LOGIC EQU 111
A_FIG EQU 255
A_FIG2 EQU 32
K_PLOT EQU 88
K_STARS EQU 104
V_TS EQU 0x3E4F
V_WIFF EQU 0x3E54
V_LOGIC EQU 0x3E55               ; 1: the update's logic, at 28 MHz, has not reached the ground
V_CH EQU 0x3E56
V_WSP EQU 0x3E52                 ; word: the hook's stack during a stack wipe
V_TITLE EQU 0x3E51               ; 1: the title's Layer 2 image is set up
TITLE_BANK EQU 27
V_ICONS EQU 0x3E50              ; jeep lives showing as sprites, a bit each
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
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
        MACRO BODY_IN
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ENDM
        MACRO BODY_OUT
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ENDM

; ---- the game's interrupt, 9D63, at its own clock; flip the picture here --------------
ISR_W EQU -17
h_isr:
        push af
        push bc
        ld a,r
        push hl
        ld l,a
        ld bc,0x243B
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        ld h,a
        dec b
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld c,a
        nextreg 0x51,HOOK_PAGE
        ld (V_IR0),hl
        ld a,c
        ld (V_I7),a
        call hlib_pace_hold
        ld a,(V_FLIP)
        or a
        call nz,l2_flip
        ld a,(V_SPEED)
        nextreg 0x07,a
        ld a,r
        ld (V_IR1),a
        ld a,(V_IR0+1)
        nextreg 0x51,a
        call 0x9D63
        nextreg 0x51,HOOK_PAGE
        ld a,r
        ld hl,V_IR1
        sub (hl)
        ld (V_IR1),a
        call hlib_pace_resume   ; held always, so that a line read it broke is read again (hlib_now)
        ld bc,0x243B            ; and NR 7 selected, so that a clock read it broke reads the clock
        ld a,7
        out (c),a
        ld a,(V_I7)
        nextreg 0x07,a
        ld a,(V_IR1)
        add a,ISR_W
        ld hl,V_IR0
        add a,(hl)
        and 0x7F
        ld b,a
        ld a,(hl)
        and 0x80
        or b
        ld b,a
        ld a,(V_IR0+1)
        nextreg 0x51,a
        ld a,b
        ld r,a
        pop hl
        pop bc
        pop af
        ret
h_isr_end:

; ---- FC55, 9E03: the game writes to the screen itself. In the picture's area that ends
; the picture until the next blit. These can run inside the interrupt: no RAM, no slot change.
        MACRO L2_OFF_IF_PLAY
        ld a,d
        cp 0x40
        jr nz,.a
        ld a,e
        cp 0x80
        jr c,.skip
        jr .off
.a:     cp 0x50
        jr nz,.b
        ld a,e
        cp 0x80
        jr nc,.skip
        jr .off
.b:     cp 0x58
        jr nc,.skip
.off:   nextreg 0x69,0
        nextreg 0x15,0
.skip:
        ENDM
        MACRO R_FIX delta
        ld a,b
        add a,delta
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld r,a
        ENDM
h_fc:
        push af
        push bc
        ld a,r
        ld b,a
        L2_OFF_IF_PLAY
        R_FIX -8
        pop bc
        pop af
        ldi
        dec de
        jp 0xFC58
h_fc_end:
h_fill:
        pop ix
        push af
        push bc
        ld a,r
        ld b,a
        push de
        ld e,(ix+2)
        ld d,(ix+3)
        ld a,d
        cp 0x40
        jr c,.done
        cp 0x5B
        jr nc,.done
        cp 0x58
        jr c,.bitmap
        ; attributes of the picture's rows: 5880-5A7F
        cp 0x5A
        jr z,.lo
        ld a,e
        cp 0x80
        jr nc,.off2
        ld a,d
        cp 0x58
        jr z,.done
.off2:  nextreg 0x69,0
        nextreg 0x15,0
        jr .done
.lo:    ld a,e
        cp 0x80
        jr c,.off2
        jr .done
.bitmap:
        L2_OFF_IF_PLAY
.done:  pop de
        R_FIX -8
        pop bc
        pop af
        ld c,(ix+0)
        jp 0x9E08
h_fill_end:

; ---- 9421: the update's logic, plots and all, runs at 28 MHz in K windows: the windows pay for Layer 2.
; Under the game's DI (the figure's last plot) the wait is under DI too, so it misses the interrupts it did.
h_loop:
        ENTER
        ld a,(V_LOGIC)          ; the game can leave its logic without the ground (game over, restart):
        or a                    ; the clock then is ours, not the game's, and must not be latched as the game's
        jr nz,.in
        inc a
        ld (V_LOGIC),a
        HLIB_SPEED_IN V_SPEED
        jr .go
.in:    nextreg 0x07,3
.go:    call hlib_pace_open
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9608

; ---- A2AC, AA0A, B16D: a figure's Layer 2 image; its plot runs on from here -----------------
        MACRO FIGURE lda,next,white,figure
        ENTER
        HLIB_SPEED_IN V_TS
        call hlib_nest_open
        ld a,white
        ld (V_WHITE),a
        call figure
        ld a,A_FIG
        call hlib_nest_close
        ld hl,A_FIG2
        call hlib_debt_add
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        ld a,(lda)
        HLIB_R_OUT
        nextreg 0x51,255
        jp next
        ENDM
h_p:
        FIGURE 0x9C93,0xA2AF,0,fig_p
h_w:
        FIGURE 0x9C93,0xAA0D,1,fig_p
h_s:
        FIGURE 0x9C99,0xB170,0,fig_s

; ---- A98A, A9DD: the game's DI: the logic's window closes, the plot's opens; A9BA, AA04 the reverse ----
        MACRO DI_SITE next
        ENTER
        ld a,(HLIB_V_PACE+10)
        or a
        jr z,.nowin
        ld a,(V_SPEED)
        ld c,a
        ld a,K_LOGIC
        call hlib_pace_waitk
        call hlib_pace_open
.nowin: ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        di
        ld (0x9C8D),sp
        jp next
        ENDM
h_di1:
        DI_SITE 0xA98F
h_di2:
        DI_SITE 0xA9E2
        MACRO EI_SITE
        ENTER
        ld a,(HLIB_V_PACE+10)
        or a
        jr z,.nowin
        ld a,(V_SPEED)
        ld c,a
        ld a,K_PLOT
        call hlib_pace_waitk
        call hlib_pace_open
.nowin: ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld sp,(0x9C8D)
        ei
        ret
        ENDM
h_ei1:
        EI_SITE
h_ei2:
        EI_SITE

; ---- 9474: the buffer's clear: the back buffer swapped, its old boxes wiped; the game's own clear
; runs after at its own clock. A flash: the whole sky filled as the game fills it.
h_clear:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld a,(V_FLIP)
        or a
        call nz,l2_flip
        call l2_swap
        call l2_wipe
        ld a,(0x9783)
        or a
        call nz,l2_flash
        ld a,8
        call hlib_debt_close
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9784

; ---- 9465: the logic's window closes, back to the game's clock; the ground's image. The DI sections
; of the blit and the clear run on at the game's clock, as ever.
h_ground:
        ENTER
        xor a
        ld (V_LOGIC),a
        ld a,(HLIB_V_PACE+10)
        or a
        jr z,.nowin
        ld a,(V_SPEED)
        ld c,a
        ld a,K_LOGIC
        call hlib_pace_waitk
.nowin: call hlib_debt_open
        call l2_ground
        ld a,8
        call hlib_debt_close
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x96DB

; ---- 9477: the stars, in a window; their dots after --------------------------------------
h_stars:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_pace_open
        BODY_IN
        call 0x785B
        BODY_OUT
        ld a,(V_SPEED)
        ld c,a
        ld a,K_STARS
        call hlib_pace_waitk
        call hlib_debt_open
        call l2_stars
        ld a,8
        call hlib_debt_close
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

; ---- 946B: the picture is ready: show it at the interrupt. The blit follows at its own clock ----
h_blit:
        ENTER
        ld a,1
        ld (V_FLIP),a
        call spr_icons
        ld a,-12
        call hlib_r_set
        LEAVE_R
        jp 0xA25E

; The set paints the jeep's lives in the panel orange, the ULA's cell has one colour for the row's icons
; and heli: sprites of the set's colours lie on the game's own icons, as the screen shows them.
spr_icons:
        ld hl,0x53A0+8
        ld b,5
        ld e,0
.scan:  ld a,(hl)
        cp 0x7F
        jr nz,.no
        scf
        jr .bit
.no:    or a
.bit:   rl e
        dec l
        dec l
        djnz .scan
        ld a,(V_ICONS)
        cp e
        ret z
        ld a,e
        ld (V_ICONS),a
        ld bc,0x303B
        xor a
        out (c),a
        ld d,32
        ld b,5
.spr:   ld a,d
        out (0x57),a
        ld a,200
        out (0x57),a
        xor a
        out (0x57),a
        srl e
        sbc a,a
        and 0x80
        out (0x57),a
        ld a,d
        add a,16
        ld d,a
        djnz .spr
        ret

; ---- 7B76: a new wave: the ground's table is loaded again ----------------------------------
h_wave:
        ENTER
        xor a
        ld (V_PHASE),a
        ld a,-12
        call hlib_r_set
        LEAVE_R
        jp 0x7BEA

; ---- 7DA3: the title's wait, after its HALT: the set's logo and tags as a still Layer 2 image over the ULA
; (printing a chosen control can turn Layer 2 off: it comes back the next time round).
h_title:
        ENTER
        ld a,(V_LOGIC)          ; back here from the logic: the game's clock again, its window gone
        or a
        jr z,.notl
        xor a
        ld (V_LOGIC),a
        ld (HLIB_V_PACE+10),a
        ld a,(V_SPEED)
        nextreg 0x07,a
.notl:
        ld a,(V_TITLE)
        or a
        jr nz,.on
        inc a
        ld (V_TITLE),a
        nextreg 0x15,0
        nextreg 0x12,TITLE_BANK
        nextreg 0x1C,0x01
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,95
.on:    nextreg 0x69,0x80
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,(0x7D00)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- 5BEF: a character into the back buffer (GAME OVER, the wave's messages): on Layer 2 too ----
h_buf:
        ENTER
        ld (V_F),bc
        ld a,l
        ld (V_CH),a
        HLIB_SPEED_IN V_TS
        call hlib_nest_open
        call buf_char
        ld a,8
        call hlib_nest_close
        ld a,-10
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        push bc
        push hl
        ld h,0
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x5BF3

buf_char:
        ld hl,(V_F)
        ld de,0x8002
        or a
        sbc hl,de
        ret c
        ld a,h
        cp 0x0E                 ; 112 rows
        ret nc
        ld a,l
        and 31
        rlca
        rlca
        rlca
        add a,8
        ld (V_X),a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,32
        ld (V_Y),a
        ld a,8
        ld (V_H),a
        ld (V_W),a
        call rect_add
        ld a,(V_CH)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x5B0D
        add hl,de
        ld a,(V_Y)
        ld c,a
        ld b,8
.row:   push bc
        push hl
        ld a,c
        call l2_row
        ld d,h
        ld a,(V_X)
        ld e,a
        pop hl
        ld c,(hl)
        inc hl
        ld b,8
.px:    xor a
        sla c
        jr nc,.z
        ld a,INK_WHITE
.z:     ld (de),a
        inc e
        djnz .px
        pop bc
        inc c
        djnz .row
        nextreg 0x55,MMU5
        ret

; ---- Layer 2 -------------------------------------------------------------------------------
; l2_flip: the back buffer becomes the picture. A = anything; AF, BC? none kept: AF lost.
l2_flip:
        xor a
        ld (V_FLIP),a
        ld a,(V_BACK)
        nextreg 0x12,a
        ld a,(V_TITLE)
        or a
        jr z,.clip
        xor a
        ld (V_TITLE),a
        nextreg 0x1C,0x01
        nextreg 0x18,8
        nextreg 0x18,231
        nextreg 0x18,32
        nextreg 0x18,159
.clip:  nextreg 0x69,0x80
        nextreg 0x15,1
        ret

; l2_swap: the buffer the next picture is drawn in.
l2_swap:
        ld a,(V_BACK)
        cp L2_A
        ld hl,(V_RECT)
        jr z,.a
        ld (V_LIST_B),hl
        ld hl,(V_DOTS)
        ld (V_DOTS_B),hl
        ld hl,(V_LIST_A)
        ld (V_RECT),hl
        ld hl,(V_DOTS_A)
        ld (V_DOTS),hl
        ld a,L2_A
        jr .s
.a:     ld (V_LIST_A),hl
        ld hl,(V_DOTS)
        ld (V_DOTS_A),hl
        ld hl,(V_LIST_B)
        ld (V_RECT),hl
        ld hl,(V_DOTS_B)
        ld (V_DOTS),hl
        ld a,L2_B
.s:     ld (V_BACK),a
        ret
V_LIST_A: defw RECTS_A
V_LIST_B: defw RECTS_B
V_DOTS_A: defw DOTS_A
V_DOTS_B: defw DOTS_B

; l2_row: A = screen y -> slot 5 = its page in the back buffer, H = its high byte there. The interrupt never
; touches slots 1, 5 or 6; it runs through slot 7 (the vector, the text routine).
l2_row: ld h,a
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,(V_BACK)
        add a,a
        add a,l
        nextreg 0x55,a
        ld a,h
        and 31
        add a,0xA0
        ld h,a
        ret

; l2_wipe: the boxes and stars last drawn in this buffer, black.
l2_wipe:
        ld hl,(V_RECT)
.next:  ld a,l
        or a
        jp z,.dots
        dec l
        ld c,(hl)               ; width
        dec l
        ld a,(hl)
        ld (V_X),a
        dec l
        ld b,(hl)               ; rows
        dec l
        ld a,(hl)               ; y
        push hl
        ld e,a
        ld a,c
        cp 24
        jr z,.fast
        cp 8
        jr z,.fast
        cp 224
        jp z,.whole
        ld a,e
.row:   push af
        push bc
        call l2_row
        ld a,(V_X)
        ld l,a
        ld d,h
        ld e,l
        inc e
        ld (hl),0
        ld a,c
        dec a
        jr z,.one
        ld c,a
        ld b,0
        ldir
.one:   pop bc
        pop af
        inc a
        djnz .row
        pop hl
        jr .next
; a whole figure's box, by the stack (5.5 T a byte, ldir 21): interrupts off for a row, then as they were,
; so that the game doesn't miss an interrupt it would have taken
.fast:  ld a,(V_X)
        add a,c
        ld d,a
        HLIB_IFF_DI
        push af
        pop hl
        ld a,l
        and 4
        ld (V_WIFF),a
        ld (V_WSP),sp
.frow:  ld a,e
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,(V_BACK)
        add a,a
        add a,l
        nextreg 0x55,a
        ld a,e
        and 31
        add a,0xA0
        ld h,a
        ld l,d
        di
        ld sp,hl
        ld hl,0
        bit 4,c
        jr z,.w8
        push hl
        push hl
        push hl
        push hl
        push hl
        push hl
        push hl
        push hl
.w8:    push hl
        push hl
        push hl
        push hl
        ld sp,(V_WSP)
        ld a,(V_WIFF)
        or a
        jr z,.fnoei
        ei
.fnoei: inc e
        djnz .frow
        pop hl
        jp .next
.whole: ld a,e                  ; the whole sky, after a flash
        ld de,0
        call l2_fill
        pop hl
        jp .next
.dots:  ld a,h
        cp RECTS_A>>8
        ld hl,(V_RECT)
        ld l,0
        ld (V_RECT),hl
        ld hl,(V_DOTS)
.d2:    ld a,l
        and 0x7F
        jr z,.end
        dec l
        ld c,(hl)               ; x
        dec l
        ld a,(hl)               ; y
        push hl
        call l2_row
        ld l,c
        ld (hl),0
        pop hl
        jr .d2
.end:   ld (V_DOTS),hl
        nextreg 0x55,MMU5
        ret

; l2_flash: the game's whole-sky fill: 0xFFFF, or the AAAA / 5555 checker.
l2_flash:
        ld a,(0x9783)
        ld e,INK_WHITE
        ld d,INK_WHITE
        cp 1
        jr nz,.go
        ld e,0                  ; the checker: rows start with 5555, then AAAA
.go:    ld a,32
        ld b,112
        call l2_fill
        nextreg 0x55,MMU5
        ; the next wipe does it all
        ld hl,(V_RECT)
        ld (hl),32
        inc l
        ld (hl),112
        inc l
        ld (hl),8
        inc l
        ld (hl),224
        inc l
        ld (V_RECT),hl
        ret

; l2_fill: A = first y, B = rows of the sky's 224 pixels, by the stack, in DE's two colours, turn about on each
; row; interrupts off for a row at a time, then as they were.
l2_fill:
        ld (V_XE),a
        ld a,b
        ld (V_N),a
        HLIB_IFF_DI
        push af
        pop hl
        ld a,l
        and 4
        ld (V_WIFF),a
        ld a,e
        ld (V_F),a
        ld a,d
        ld (V_F+1),a
        ld (V_WSP),sp
.r:     ld a,(V_XE)
        call l2_row
        ld de,(V_F)
        ld l,232
        ld b,7
        di
        ld sp,hl
.p:     push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        push de
        djnz .p
        ld sp,(V_WSP)
        ld a,(V_WIFF)
        or a
        jr z,.x
        ei
.x:     ld a,e
        ld e,d
        ld d,a
        ld (V_F),de
        ld hl,V_XE
        inc (hl)
        ld hl,V_N
        dec (hl)
        jr nz,.r
        ret

; l2_ground: 16 rows, 224 wide, from this wave's 16-pixel row, rotated by V_PHASE.
; Wave: 512 bytes, 32 a row (the pattern twice over).
l2_ground:
        nextreg 0x56,PG_GROUND
        ld a,(0x9CC0)
        and 15
        add a,a
        add a,0xC0
        ld (V_PG),a
        xor a
        ld (V_SPAN),a
        ld a,144
        ld (V_XE),a
        ld a,(0x9CCA)
        or a
        jr z,.row
        ld a,144                ; 9CCA: the game shifts the ground one row down, a black row above
        call l2_row
        ld l,8
        ld d,h
        ld e,9
        ld (hl),0
        ld bc,223
        ldir
        ld a,145
        ld (V_XE),a
.row:   ld a,(V_XE)
        cp 160
        jr nc,.end
        call l2_row
        ld d,h
        ld e,8
        ld a,(V_SPAN)
        rrca
        rrca
        rrca
        ld c,a
        and 0xE0
        ld l,a
        ld a,c
        and 0x1F
        ld b,a
        ld a,(V_PG)
        add a,b
        ld h,a
        ld a,(V_PHASE)
        and 15
        add a,l
        ld l,a
        ld bc,16
        ldir
        ld h,d
        ld l,8
        ld bc,208
        ldir
        ld hl,V_SPAN
        inc (hl)
        ld hl,V_XE
        inc (hl)
        jr .row
.end:   nextreg 0x56,MMU6
        nextreg 0x55,MMU5
        ret

; l2_stars: 20 stars, each two dots, in the set's colour for FF. Phase counts here too.
l2_stars:
        ld a,(0x9CC8)
        or a
        jr z,.np
        ld hl,V_PHASE
        inc (hl)
.np:    ld ix,0x7816
        ld b,0x14
.s:     push bc
        ld a,(ix+1)
        add a,8
        ld d,a                  ; y
        ld a,(ix+0)
        sub 8                   ; x of the first dot (its byte + bit)
        ld e,a
        call .dot
        ld a,(ix+0)
        add a,160               ; 20 bytes on, wrapping into the next row
        jr nc,.same
        inc d
.same:  sub 8
        ld e,a
        call .dot
        inc ix
        inc ix
        pop bc
        djnz .s
        nextreg 0x55,MMU5
        ret
.dot:   ld a,e
        cp 8
        ret c
        cp 232
        ret nc
        ld a,d
        cp 32
        ret c
        cp 144
        ret nc
        call l2_row
        ld l,e
        ld a,(hl)
        cp INK_WHITE
        ret z
        ld (hl),INK_WHITE
        ld hl,(V_DOTS)
        ld a,l
        and 0x7F
        cp 0x7E
        ret nc
        ld (hl),d
        inc l
        ld (hl),e
        inc l
        ld (V_DOTS),hl
        ret

; fig_p: a 24 x 24 figure at (9C93), (9C95), its address in (9C97).
fig_p:  ld a,(0x9C94)
        or a
        ret nz
        ld a,(0x9C93)
        sub 8
        ld (V_X),a
        ld a,(0x9C95)
        add a,8
        ld (V_Y),a
        ld a,24
        ld (V_H),a
        ld (V_W),a
        ld hl,(0x9C97)
        jr fig
; fig_s: an 8 x 8 figure at (9C99), (9C9B), its address in (9C9D).
fig_s:  ld a,(0x9C9A)
        or a
        ret nz
        ld a,(0x9C99)
        sub 8
        ld (V_X),a
        ld a,(0x9C9B)
        add a,8
        ld (V_Y),a
        ld a,8
        ld (V_H),a
        ld (V_W),a
        ld hl,(0x9C9D)
fig:    ld (V_F),hl
        call rect_add
        call find_frame
        jp c,fig_plain
        call rle_plot
        nextreg 0x56,MMU6
        nextreg 0x55,MMU5
        ret

; find_frame: V_F -> slot 6 and HL at its image, or carry. Table: 512 entries, 4 bytes each:
; address (0: empty), page, offset / 64.
find_frame:
        nextreg 0x56,PG_TABLE
        ld hl,(V_F)
        ld a,h
        xor l
        ld e,a
        ld a,h
        rrca
        rrca
        rrca
        xor l
        and 1
        ld d,a                  ; DE = entry 0..511
.probe: ld h,d
        ld l,e
        add hl,hl
        add hl,hl
        ld a,h
        add a,0xC0
        ld h,a
        ld a,(hl)
        inc l
        or (hl)
        jr z,.none
        dec l
        ld bc,(V_F)
        ld a,(hl)
        cp c
        jr nz,.again
        inc l
        ld a,(hl)
        cp b
        jr nz,.again
        inc l
        ld a,(hl)
        inc l
        ld l,(hl)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xC000
        add hl,de
        nextreg 0x56,a
        or a
        ret
.again: inc de
        ld a,d
        and 1
        ld d,a
        jr .probe
.none:  nextreg 0x56,MMU6
        scf
        ret

; rle_plot: HL = the image (slot 6). Rows of: span count, then each span: skip, length, colours.
rle_plot:
        ld a,(V_H)
        ld (V_N),a
        ld a,(V_WHITE)
        or a
        jr nz,.clipped
        ld a,(V_X)
        cp 8
        jr c,.clipped
        ld b,a
        ld a,(V_W)
        add a,b
        jr c,.clipped
        cp 233
        jr nc,.clipped
        ld a,(V_Y)
        cp 32
        jr c,.clipped
        ld c,a
        ld a,(V_H)
        add a,c
        cp 145
        jp c,.whole
.clipped:
        ld a,(V_Y)
        ld e,a
.row:   ld a,(hl)
        inc hl
        ld (V_SPAN),a
        ld a,e
        cp 32
        jr c,.skiprow
        cp 144
        jr nc,.skiprow
        push hl
        call l2_row
        ld d,h
        pop hl
        push de
        ld a,(V_X)
        ld e,a
        ld a,(V_SPAN)
        or a
        jr z,.done
.span:  ld a,(hl)
        inc hl
        add a,e
        ld e,a
        ld b,0
        ld c,(hl)
        inc hl
        ld a,c
        add a,e
        ld (V_XE),a
        ; a span inside 8..231?
        ld a,e
        cp 8
        jr c,.slow
        cp 232
        jr nc,.slow
        ld a,(V_XE)
        cp 233
        jr nc,.slow
        ld a,(V_WHITE)
        or a
        jr nz,.white
        ldir
        jr .sn
.white: ld b,c                  ; a silhouette: the mask's pixels white, not those only OR'd (bit 7)
.w:     bit 7,(hl)
        inc hl
        jr nz,.wn
        ld a,INK_WHITE
        ld (de),a
.wn:    inc e
        djnz .w
        jr .sn
.slow:  ld b,c
.sl:    ld a,e
        cp 8
        jr c,.ns
        cp 232
        jr nc,.ns
        ld a,(V_WHITE)
        or a
        ld a,(hl)
        jr z,.sw
        bit 7,a
        jr nz,.ns
        ld a,INK_WHITE
.sw:    ld (de),a
.ns:    inc hl
        inc e
        djnz .sl
.sn:    ld a,(V_SPAN)
        dec a
        ld (V_SPAN),a
        jr nz,.span
.done:  pop de
        jr .nextrow
.skiprow:
        ld a,(V_SPAN)
        or a
        jr z,.nextrow
.sk:    inc hl
        ld c,(hl)
        inc hl
        ld b,0
        add hl,bc
        ld a,(V_SPAN)
        dec a
        ld (V_SPAN),a
        jr nz,.sk
.nextrow:
        inc e
        ld a,(V_N)
        dec a
        ld (V_N),a
        jp nz,.row
        ret
; the whole figure in the picture, not a silhouette: no clipping to test
.whole: push ix
        ld ixh,b                ; x
        ld a,(V_Y)
        push hl
        call l2_row
        ld d,h
        pop hl
        ld a,(V_Y)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        ld (V_PG),a
.wrow:  ld a,(hl)
        inc hl
        or a
        jr z,.wnext
        ld ixl,a
        ld e,ixh
.wspan: ld a,e
        add a,(hl)
        ld e,a
        inc hl
        ld c,(hl)
        inc hl
        ld b,0
        ldir
        dec ixl
        jr nz,.wspan
.wnext: inc d
        ld a,d
        cp 0xC0
        jr nz,.wsame
        ld d,0xA0
        ld a,(V_PG)
        inc a
        ld (V_PG),a
        nextreg 0x55,a
.wsame: ld a,(V_N)
        dec a
        ld (V_N),a
        jr nz,.wrow
        pop ix
        ret

; fig_plain: a graphic with no colour image: white, by the game's own mask and bytes.
fig_plain:
        ld a,(V_H)
        ld (V_N),a
        cp 24
        ld a,3
        ld bc,72
        jr z,.g
        ld a,1
        ld bc,8
.g:     ld (V_PG),a
        ld hl,(V_F)
        add hl,bc
        ld (V_SRC),hl           ; graphic, after the mask
        ld a,(V_Y)
        ld (V_XE),a
.row:   ld a,(V_XE)
        cp 32
        jr c,.nr
        cp 144
        jr nc,.nr
        call l2_row
        ld d,h
        ld a,(V_X)
        ld e,a
        ld a,(V_PG)
        ld c,a
        ld hl,(V_F)
        ld ix,(V_SRC)
.byte:  ld a,(hl)
        inc hl
        ld (V_SPAN),a
        ld b,8
        ld a,(ix+0)
        inc ix
.bit:   rlca
        push af
        ld a,(V_SPAN)
        rlca
        ld (V_SPAN),a
        jr nc,.op
        pop af
        jr nc,.pn
        push af
        ld a,INK_WHITE
        jr .put
.op:    pop af
        push af
        ld a,0
        jr nc,.put
        ld a,INK_WHITE
.put:   push bc
        ld b,a
        ld a,e
        cp 8
        jr c,.np
        cp 232
        jr nc,.np
        ld a,b
        ld (de),a
.np:    pop bc
        pop af
.pn:    inc e
        djnz .bit
        dec c
        jr nz,.byte
.nr:    ld a,(V_PG)
        ld c,a
        ld b,0
        ld hl,(V_F)
        add hl,bc
        ld (V_F),hl
        ld hl,(V_SRC)
        add hl,bc
        ld (V_SRC),hl
        ld hl,V_XE
        inc (hl)
        ld hl,V_N
        dec (hl)
        jp nz,.row
        nextreg 0x55,MMU5
        ret

; rect_add: note the figure's box, clipped, for the next wipe of this buffer.
rect_add:
        ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*4
        jr nz,.room
        ld l,RECT_MAX*4-4       ; list full: the last entry becomes the whole sky
        ld (hl),32
        inc l
        ld (hl),112
        inc l
        ld (hl),8
        inc l
        ld (hl),224
        ret
.room:  ld a,(V_Y)
        ld c,a
        ld a,(V_H)
        ld b,a
        ld a,c                  ; rows clipped to 32..143
        cp 144
        ret nc
        cp 32
        jr nc,.y2
        add a,b
        sub 32
        ret c
        ret z
        ld b,a
        ld c,32
.y2:    ld a,c
        add a,b
        cp 145
        jr c,.y3
        ld a,144
        sub c
        ld b,a
.y3:    ld a,(V_X)
        ld e,a
        ld a,(V_W)
        ld d,a                  ; columns clipped to 8..231 (x may have wrapped: a miss)
        ld a,e
        cp 232
        jr c,.xl
        add a,d                 ; off the left: x wrapped
        ret nc
        sub 8
        ret c
        ret z
        ld d,a
        ld e,8
        jr .x3
.xl:    cp 8
        jr nc,.x2
        add a,d
        sub 8
        ret c
        ret z
        ld d,a
        ld e,8
.x2:    ld a,e
        add a,d
        cp 233
        jr c,.x3
        ld a,232
        sub e
        ld d,a
.x3:    ld (hl),c
        inc l
        ld (hl),b
        inc l
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld (V_RECT),hl
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3800
        SAVEBIN "silkworm_rom.bin",rom_start,$-rom_start

; ---- the stub's setup: palette, Layer 2 ready but off until the first blit --------------
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x14,0xE3
        nextreg 0x12,L2_A
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x70,0
        nextreg 0x1C,0x01
        nextreg 0x18,8
        nextreg 0x18,231
        nextreg 0x18,32
        nextreg 0x18,159
        ld a,0x10
        nextreg 0x43,a
        nextreg 0x40,0
        ld hl,l2_pal
        ld c,2
.pal2:  push hl
        ld b,PAL_N
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        pop hl                  ; indices 128 up: the same colours, bit 7 marking pixels only OR'd
        dec c
        jr nz,.pal2
        nextreg 0x43,0
        nextreg 0x69,0
        nextreg 0x15,0
        nextreg 0x1C,0x02
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,spr_pat
        ld b,0
.pat:   ld a,(hl)
        out (0x5B),a
        inc hl
        djnz .pat
        ld bc,0x303B
        xor a
        out (c),a
        ld b,64
.hide:  xor a
        out (0x57),a
        out (0x57),a
        out (0x57),a
        out (0x57),a
        djnz .hide
        ld hl,printer
        ld de,0x5B00
        ld bc,256
        ldir
        ret
PAL_N   EQU 128
l2_pal: defs PAL_N*2,0
spr_pat: defs 256,0xE3
setup_end:
printer:
        SAVEBIN "silkworm_setup.bin",setup,setup_end-setup
