; Cybernoid (Hewson, 1988, 48K) - figures become hardware sprites.
; The game draws figures by XOR through three plotters and paints their cells afterwards (or just before).
;   32957 small: A frame (mod 16), E x, D y; 16 bytes, 4 preshifts at 60513. One image per call.
;   41469 big:   A frame, DE new position, BC old position, HL old graphic; 48 bytes, 4 preshifts at 50937. Toggles old and new.
;   42203 tile:  same arguments, 32 bytes at 54393. Called for figures from the sites patched to e_t; every other caller is
;                scenery (animated fixtures, tiles coming and going) and stays on the ULA.
;   42054, 42157 paint cells with C; 42107 with C in the left column and B in the right, all only where the room map at
;   attribute + 768 is empty.
;   31263 XORs two pixels on one line, a shot, and paints its cell bright white.
; The plot loops keep running: LD (HL),A -> NOP, and the cell writes likewise. Plots and paints run at 28 MHz, entered with a
; return through tramp, so what they save pays for the hooks: a tick the original overran now has time to spare.
; An image is a (graphic, y, x) in a table of 128 entries: a plot toggles it, as XOR does. An image taken off stays showing
; until the next tick or until a new image reuses its entry, so a figure moving by erase + draw never leaves a gap, and
; a reused entry holding the same graphic needs no upload.
; Entries 0-23 (big, tile): sprites 2i, 2i+1, pattern i, both halves. Entries 24-103 (small, shot): sprite i + 24, half
; pattern i + 24. Entries 104-127: small images past the 128 sprites, kept so the XOR count stays right, not shown. Hooks: alt ROM image 1 at 0x386E, 28 MHz; interrupts stay on and the
; ISR touches slots 0, 3, 4, 7 only: state page at slot 6, pattern pages at slot 5 only during an upload.

        DEVICE ZXSPECTRUMNEXT

STATE   EQU 22
PAT_S   EQU 26                  ; 64 images, 128 bytes each
PAT_B   EQU 27                  ; 72 images, 256 bytes each, 32 to a page
PAT_T   EQU 30                  ; 170 images, 256 bytes each, 32 to a page
PAT_P   EQU 36                  ; 4 images, 128 bytes each

EX      EQU 0xC000
EY      EQU 0xC100
GL      EQU 0xC200
GH      EQU 0xC300
ES      EQU 0xC400              ; 0 free, 1 taken off but still showing, 2 on
C1      EQU 0xC500              ; palette offset << 4, left sprite
C2      EQU 0xC600              ; right sprite
VG      EQU 0xC700
LAST    EQU 0xC702              ; 1 + entry drawn by the last plot and not painted yet
PV      EQU 0xC703              ; a paint came before its plot: valid, x, y, colours
PX      EQU 0xC704
PY      EQU 0xC705
PC1     EQU 0xC706
VN      EQU 0xC708
VD      EQU 0xC709
VP      EQU 0xC70A
VA      EQU 0xC70B
VI      EQU 0xC70D
VC      EQU 0xC70E
VF      EQU 0xC710
OVF     EQU 0xC711
OVC     EQU 0xC712
OVR     EQU 0xC713
VQ      EQU 0xC714

T0      EQU 42261               ; the tile plotter's four row writes
T1      EQU 42266
T2      EQU 42280
T3      EQU 42285

V_DEBT_MODE EQU 0xC72D
V_TARGET EQU 0xC726
V_CLASSES EQU 0xC900
V_TIMES EQU 0xCA00
V_LEAVE_R EQU 0xC725
V_SPEED EQU 0xC720
HLIB_V_R EQU 0xC721
HLIB_V_PACE EQU 0xC730
HLIB_PACE_NL EQU 311
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_iff.asm"
        MACRO CAPTURE target, debtmode
        nextreg 0x56,STATE
        HLIB_SPEED_IN V_SPEED
        HLIB_R_IN
        push af
        ld a,1
        ld (V_ACTIVE),a
        ld a,debtmode
        ld (V_DEBT_MODE),a
        pop af
        push hl
        ld hl,target
        ld (V_TARGET),hl
        pop hl
        ENDM
        ORG 0x2800
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; ---- 32957 small plotter ----
e_s:   CAPTURE 80,0
            push af
        push bc
        push de
        push hl
        call enter
        and 15
        add a,a
        add a,a
        ld c,a
        ld a,e
        and 3
        or c
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,60513
        add hl,bc
        ld b,h
        ld c,l
        call bt
        ; The retired bitmap loop has no register outputs. Its only surviving
        ; RAM effects are the two preshift operands, both (original E & 124)/4.
        ; Keep those effects and the exact R increment, without 16 discarded XORs.
        ld hl,2
        add hl,sp
        ld a,(hl)
        and 124
        rrca
        rrca
        ld (33007),a
        ld (33026),a
        ld hl,(V_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
        xor a
        ld (V_ACTIVE),a
        ld a,20                ; original 49 M1 mod 128 - entry 21 - exit 8
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_R_OUT
        HLIB_SPEED_OUT_A V_SPEED
        nextreg 0x56,0
        pop af
        ret

; ---- 31263 one line of two pixels (a shot), always painted bright white: a graphic of one byte at 31308 + (E & 3) ----
e_p:   CAPTURE 24,1
            push af
        push bc
        push de
        push hl
        call enter
        ld a,e
        ld (PX),a
        ld a,d
        ld (PY),a
        ld hl,0xF0F0            ; bright white, palette offset 15
        ld (PC1),hl
        ld a,1
        ld (PV),a
        ld a,e
        and 3
        add a,low 31308
        ld c,a
        ld b,high 31308
        call bt
        xor a
        ld (PV),a
        ld (LAST),a
        call lv2
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,tramp
        ex (sp),hl
        push af
        push bc
        push hl
        jp 31266

; ---- 41469 big plotter ----
e_b:   CAPTURE 361,0
        call big_target
            push af
        push bc
        push de
        push hl
        call enter
        call oldimg
        cp 18
        jr nc,.out
        add a,a
        add a,a
        ld c,a
        ld a,e
        and 3
        or c
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        add hl,hl
        add hl,bc
        ld bc,50937
        add hl,bc
        ld b,h
        ld c,l
        call bt
.out:   call lv2
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,tramp
        ex (sp),hl
        push af
        push bc
        push de
        jp 41472

; ---- 42203 tile plotter, figure callers only ----
e_t:   CAPTURE 275,0
            push af
        push bc
        push de
        push hl
        call enter
        call oldimg
        cp 170
        jr nc,.out
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,54393
        add hl,bc
        ld b,h
        ld c,l
        call bt
.out:   call lv2_tile
        xor a
        call tw
        pop hl
        pop de
        pop bc
        pop af
        call 42203
        push af
        ld a,0x77
        call tw
        pop af
        jp tramp
tw:     ld (T0),a
        ld (T1),a
        ld (T2),a
        ld (T3),a
        ret

; HL old graphic, C old x, B old y. Keeps A, DE.
oldimg: push af
        push de
        ld d,b
        ld e,c
        ld b,h
        ld c,l
        call bt
        pop de
        pop af
        ret

; ---- cell painters ----
e_a1:   CAPTURE 44,2
           push af
        push bc
        push de
        push hl
        ld b,c
        ld hl,0x0202            ; rows, columns
        call ea
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,tramp
        ex (sp),hl
        push af
        push bc
        push de
        jp 42160
e_a2:   CAPTURE 62,1
           push af
        push bc
        push de
        push hl
        ld b,c
        ld hl,0x0303
        call ea
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,tramp
        ex (sp),hl
        push af
        push bc
        push de
        jp 42057
e_a3:   CAPTURE 56,1
           push af
        push bc
        push de
        push hl
        ld hl,0x0302
        call ea
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,tramp
        ex (sp),hl
        push af
        push bc
        push de
        jp 42110

; ---- a tick begins: images taken off and not reused go ----
e_tick:   CAPTURE 0,0
         push af
        push bc
        push hl
        call enter
        ld hl,ES
        ld bc,128
.f:     ld a,1
        cpir
        jr nz,.d
        dec hl
        ld (hl),0
        ld a,l
        call hide
        inc hl
        ld a,b
        or c
        jr nz,.f
.d:     call leave_tick
        pop hl
        pop bc
        pop af
        xor a
        ld (28954),a
        jp 25976

; ---- the two screen clears ----
e_c1:   CAPTURE 0,0
           call clear
        ld c,0
        ld hl,23295
        jp 26287
e_c2:   CAPTURE 0,0
           call clear
        ld c,0
        ld hl,22656
        jp 26309

clear:  push af
        push bc
        push hl
        call enter
        xor a
        ld (LAST),a
        ld (PV),a
        ld hl,ES
        ld b,128
.l:     ld a,(hl)
        or a
        jr z,.n
        ld (hl),0
        ld a,l
        call hide
.n:     inc l
        djnz .l
        call leave
        pop hl
        pop bc
        pop af
        ret

tramp:
        nextreg 0x56,STATE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ld a,(V_DEBT_MODE)
        or a
        jr z,.window
        ld a,20
        call hlib_debt_close
        ld hl,(V_TARGET)
        call hlib_debt_repay
        jr .done
.window:
        ld hl,(V_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
.done:  xor a
        ld (V_ACTIVE),a
        ld a,-13
r_tramp_delta EQU $-1
        call hlib_r_set
        pop hl
        pop de
        pop bc
        HLIB_R_OUT
        HLIB_SPEED_OUT_A V_SPEED
        nextreg 0x56,0
        pop af
        ret

lv2_tile:
        push af
        push bc
        push de
        push hl
        ld a,-50
        jr lv2_common
lv2:
        push af
        push bc
        push de
        push hl
        ld a,-37
r_body_delta EQU $-1
lv2_common:
        call hlib_r_set
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x56,0
        ret

enter:
        push af
        push bc
        push de
        push hl
        ld a,(V_DEBT_MODE)
        or a
        jr z,.window
        call hlib_debt_open
        jr .done
.window:
        ld hl,20
        call hlib_debt_add
        call hlib_pace_open
.done:
        pop hl
        pop de
        pop bc
        pop af
        ret

leave_tick:
        push af
        ld a,-33
        jr leave_common
leave:
        push af
        ld a,-34
leave_common:
        ld (V_LEAVE_R),a
        pop af
        push af
        push bc
        push de
        push hl
        ld hl,0
        ld a,(V_SPEED)
        call hlib_pace_wait
        xor a
        ld (V_ACTIVE),a
        ld a,(V_LEAVE_R)
r_leave_delta EQU $-1
        call hlib_r_set
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x56,0
        ret

big_target:
        push af
        push bc
        push de
        push hl
        ld h,high V_CLASSES
        ld l,e
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        sub (hl)                 ; new-x class * 7
        ld l,c
        add a,(hl)               ; + old-x class
        add a,a
        ld l,a
        ld h,high V_TIMES
        ld a,(hl)
        ld (V_TARGET),a
        inc l
        ld a,(hl)
        ld (V_TARGET+1),a
        pop hl
        pop de
        pop bc
        pop af
        ret

; Z if the image at BC draws nothing. Graphics checked by the build (blank_images).
blankq: ld hl,-50937
        add hl,bc
        jr nc,.n
        ld hl,-51129
        add hl,bc
        jr nc,.y
        ld hl,-54393
        add hl,bc
        ld a,h
        or l
        ret z
        ld hl,-61089
        add hl,bc
        jr nc,.n
        ld a,h
        or a
        jr nz,.n
        ld a,l
        cp 64
        jr c,.y
        cp 128
        ret
.n:     or 1
        ret
.y:     xor a
        ret

; BC graphic, D y, E x: XOR this image, unless it draws nothing.
bt:     call blankq
        ret z
toggle: ld (VG),bc
        ld h,high X_HEAD
        ld l,e
        ld a,(hl)
.f:     cp 255
        jr z,.on
        ld l,a
        ld h,high EY
        ld a,(hl)
        cp d
        jr nz,.nx
        inc h
        ld a,(VG)
        cp (hl)
        jr nz,.nx
        inc h
        ld a,(VG+1)
        cp (hl)
        jr nz,.nx
        inc h
        ld a,(hl)
        cp 2
        jr nz,.nx
        ld (hl),1
        xor a
        ld (LAST),a
        ret
.nx:    ld h,high X_NEXT
        ld a,(hl)
        jr .f
.on:    ld a,255
        ld (V_CACHE_BEST),a
        ld h,high G_HEAD
        ld a,(VG)
        ld l,a
        ld a,(hl)
.p:     cp 255
        jr z,.chosen
        ld l,a
        ld h,high GH
        ld a,(VG+1)
        cp (hl)
        jr nz,.pn
        ld h,high ES
        ld a,(hl)
        cp 2
        jr nc,.pn
        ld a,(V_CACHE_BEST)
        cp l
        jr c,.pn
        ld a,l
        ld (V_CACHE_BEST),a
.pn:    ld h,high G_NEXT
        ld a,(hl)
        jr .p
.chosen:
        ld a,(V_CACHE_BEST)
        cp 255
        jr z,.fr
        ld l,a
        jp .same
.fr:    ld bc,(VG)              ; a free entry of its pool, else one taken off
        call patof
        ld hl,ES
        ld bc,24
        ld a,(VN)
        dec a
        jr nz,.po
        ld l,24
        ld c,104
.po:    push hl
        push bc
        xor a
        cpir
        pop bc
        jr z,.new0
        pop hl
        ld a,1
        cpir
        jr z,.new
        ld hl,OVF               ; full: the XOR count is lost; verify fails on this
        inc (hl)
        ret
.new0:  pop af
.new:   dec hl
        ld a,l
        ld (VI),a
        cp 104
        jr nc,.nup
        ld a,(VN)
        dec a
        jr z,.nup
        ld a,(VI)
        ld c,a                  ; pattern select
        ld a,(VN)
        dec a
        ld a,c
        jr nz,.sel
        add a,24
        srl a                   ; half in bit 7
        jr nc,.sel
        or 0x80
.sel:   ld bc,0x303B
        out (c),a
        ld a,(VP)
        nextreg 0x55,a
        ld hl,(VA)
        ld c,0x5B
        ld a,(VN)
        dec a
        ld b,128
        jr z,.up
        ld b,0
.up:    otir
        nextreg 0x55,5
.nup:   ld a,(VI)
        ld l,a
.same:  call x_link
        call g_link
        ld h,high EX
        ld (hl),e
        inc h
        ld (hl),d
        inc h
        ld a,(VG)
        ld (hl),a
        inc h
        ld a,(VG+1)
        ld (hl),a
        inc h
        ld (hl),2
        ld a,(PV)
        or a
        jr z,.nop
        ld a,(PX)
        cp e
        jr nz,.nop0
        ld a,(PY)
        cp d
        jr nz,.nop0
        inc h
        ld a,(PC1)
        ld (hl),a
        inc h
        ld a,(PC1+1)
        ld (hl),a
.nop0:  xor a
        ld (PV),a
.nop:   ld a,l
        inc a
        ld (LAST),a
        dec a
        ; fall through to show

; A = entry: its sprites from the table
show:   cp 104
        ret nc
        ld (VI),a
        ld l,a
        ld h,high GL
        ld c,(hl)
        inc h
        ld b,(hl)
        call patof
        ld a,(VI)
        ld l,a
        ld h,high EX
        ld e,(hl)
        inc h
        ld d,(hl)
        ld a,e
        cp 128
        jr c,.vis
        cp 248
        jr nc,.vis
        ld a,(VI)
        jp hide                 ; off the screen: the plotter writes nothing
.vis:   ld h,high C1
        ld c,(hl)
        inc h
        ld b,(hl)
        ld a,e
        and 0xFC
        ld l,a
        ld a,e
        rla
        sbc a,a
        ld h,a
        add hl,hl
        ld a,32
        add a,l
        ld l,a
        ld a,0
        adc a,h
        ld h,a                  ; HL = X
        ld a,d
        add a,32
        ld d,a
        ld a,0
        adc a,0
        ld e,a                  ; D = Y, E = Y8
        ld a,(VN)
        dec a
        jr nz,.big
        ld a,(VI)               ; one sprite, half pattern i + 24
        add a,24
        nextreg 0x34,a
        ; Small figures and shots have immutable resident patterns (24..57).
        push hl
        ld a,(VP)
        cp PAT_P
        ld a,24
        jr nz,.static
        ld a,56
.static:
        ld (VQ),a
        ld a,(VA+1)
        and 31
        ld l,a
        ld a,(VQ)
        add a,l
        ld (VQ),a
        pop hl
        ld a,(VA)
        rlca                    ; half-pattern in carry
        ld a,(VQ)
        push af
        or 0xC0
        ld (VQ),a
        call spr
        pop af
        ld a,0
        rla
        rrca
        rrca                    ; the half in bit 6
        or 0x80
        or e
        nextreg 0x39,a
        ret
.big:   ld a,(VI)
        or 0xC0
        ld (VQ),a
        ld a,(VI)
        add a,a
        nextreg 0x34,a
        call spr
        ld a,e
        or 0x80
        nextreg 0x39,a
        ld a,(VI)
        add a,a
        inc a
        nextreg 0x34,a
        ld a,(VD)
        add a,l
        ld l,a
        ld a,0
        adc a,h
        ld h,a
        ld c,b
        call spr
        ld a,e
        or 0xC0
        nextreg 0x39,a
        ret
spr:    ld a,l
        nextreg 0x35,a
        ld a,d
        nextreg 0x36,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,(VQ)
        nextreg 0x38,a
        ret

; A = entry: its sprites off
hide:   cp 24
        jr nc,.s
        add a,a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .o
.s:     cp 104
        ret nc
        add a,24
.o:     nextreg 0x34,a
        nextreg 0x38,0
        ret

; BC graphic -> VN sprites, VD second sprite's offset, VP pattern page, VA address at slot 5. Keeps DE.
patof:  ld hl,-60513
        add hl,bc
        jr c,.s
        ld hl,-54393
        add hl,bc
        jr c,.t
        ld hl,-50937
        add hl,bc
        jr nc,.p
        call sh4
        ld a,l
        ld c,0
.d:     cp 3
        jr c,.e
        sub 3
        inc c
        jr .d
.e:     ld a,c
        ld c,PAT_B
        ld b,16
        jr .two
.t:     call sh4
        srl h
        rr l
        ld a,l
        ld c,PAT_T
        ld b,8
.two:   ld l,a
        rlca
        rlca
        rlca
        and 7
        add a,c
        ld (VP),a
        ld a,l
        and 31
        or 0xA0
        ld (VA+1),a
        xor a
        ld (VA),a
        ld a,b
        ld (VD),a
        ld a,2
        ld (VN),a
        ret
.s:     call sh4
        ld c,PAT_S
.one:   ld a,l
        srl a
        or 0xA0
        ld (VA+1),a
        ld a,l
        rrca
        and 0x80
        ld (VA),a
        ld a,c
        ld (VP),a
        ld a,1
        ld (VN),a
        ret
.p:     ld a,c
        sub low 31308
        ld l,a
        ld c,PAT_P
        jr .one
sh4:    srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ret

; (the painters' code is in the state page, below)
ea:     call enter
        ld a,(V_DEBT_MODE)
        cp 2
        jr z,.a1
        call over
        jp attr
.a1:    call a1_cells
        jp attr

; A1's two-by-two attribute loop: only non-screen writes survive. Count its
; conditional LD (HL),C fetches for R, including the original low-byte wrap.
a1_cells:
        push bc
        push de
        ld a,41                ; 70 original fetches - 21 entry - 8 exit
        ld (V_LEAVE_R),a
        ld a,e
        cp 128
        jr c,.x
        ld hl,V_LEAVE_R
        inc (hl)
        ld e,0
.x:     call 26521
        ld b,2
.row:   push hl
        ld de,768
        add hl,de
        ex de,hl
        pop hl
        call .cell
        inc l
        inc e
        call .cell
        ld de,31
        add hl,de
        djnz .row
        pop de
        pop bc
        ret
.cell:  ld a,(de)
        or a
        ret nz
        ld a,(V_LEAVE_R)
        inc a
        ld (V_LEAVE_R),a
        ld a,h
        cp 0x5B
        ret c
        ld (hl),c
        ret

a1_finish:
        ld a,20
        call hlib_debt_close
        ld hl,(V_TARGET)
        call hlib_debt_repay
        xor a
        ld (V_ACTIVE),a
        ld a,(V_LEAVE_R)
        call hlib_r_set
        pop hl                 ; ea return (e_a1 now returns directly)
        pop hl
        pop de
        pop bc
        HLIB_R_OUT
        HLIB_SPEED_OUT_A V_SPEED
        nextreg 0x56,0
        pop af
        ret
; 128K music runs at the interrupted game's clock even inside accelerated plots.
; The game ISR never touches slot 6; its original body and AY writes are unchanged.
V_ACTIVE EQU 0xC724
IRQ_MAP EQU 0xC728
IRQ_SEL EQU 0xC729
IRQ_SPEED EQU 0xC72A
IRQ_FIRST_R EQU 0xC72B
IRQ_LAST_R EQU 0xC72C
irq_in:
        push af
        push bc
        push de
        push hl
        ld a,r
        push af
        ld bc,0x243B
        in a,(c)
        push af
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        nextreg 0x56,STATE
        ld (IRQ_MAP),a
        pop af
        ld (IRQ_SEL),a
        pop af
        ld (IRQ_FIRST_R),a
        HLIB_SPEED_IN IRQ_SPEED
        call hlib_pace_hold
        ld a,(V_ACTIVE)
        or a
        ld a,(IRQ_SPEED)
        jr z,.clock
        ld a,(V_SPEED)
.clock: nextreg 7,a
        ld a,(IRQ_FIRST_R)
        ld b,a
        add a,-12
        and 0x7F
        bit 7,b
        jr z,.r
        or 0x80
.r:     ld r,a
        pop hl
        pop de
        pop bc
        pop af
        push af
        push bc
        push de
        jp 0x70D6
irq_out:
        push af
        push bc
        push de
        push hl
        ld a,r
        ld (IRQ_LAST_R),a
        nextreg 7,3
        call hlib_pace_resume
        ld a,(V_ACTIVE)
        or a
        jr z,.noadd
        ld a,(IRQ_FIRST_R)
        ld b,a
        ld a,(IRQ_LAST_R)
        sub b
        add a,5
        ld b,a
        ld a,(HLIB_V_R)
        ld c,a
        add a,b
        and 0x7F
        bit 7,c
        jr z,.save
        or 0x80
.save:  ld (HLIB_V_R),a
.noadd: ld a,(IRQ_LAST_R)
        ld b,a
        add a,-11
        and 0x7F
        bit 7,b
        jr z,.r
        or 0x80
.r:     ld d,a
        ld bc,0x243B
        ld a,(IRQ_SEL)
        out (c),a
        HLIB_SPEED_OUT IRQ_SPEED
        ld a,(IRQ_MAP)
        nextreg 0x56,a
        ld a,d
        ld r,a
        pop hl
        pop de
        pop bc
        pop af
        ei
        reti

; Exact X buckets: every allocated slot remains linked while inactive. This
; preserves slot allocation, pattern caching and sprite priority, while painters
; and XOR lookup inspect only entries with the requested X coordinate.
X_HEAD EQU 0xCB00
X_NEXT EQU 0xCC00
X_PREV EQU 0xCD00
X_LINKED EQU 0xCE00
x_link:
        push af
        push bc
        push hl
        ld b,l                  ; entry
        ld h,high X_LINKED
        ld a,(hl)
        or a
        jr z,.insert
        ld h,high EX
        ld a,(hl)
        cp e
        jr z,.out               ; already in the right bucket
        ld c,a                  ; old bucket
        ld h,high X_NEXT
        ld a,(hl)
        push af                 ; old successor
        ld h,high X_PREV
        ld a,(hl)
        cp 255
        jr z,.head
        ld l,a
        ld h,high X_NEXT
        jr .unlink
.head:  ld l,c
        ld h,high X_HEAD
.unlink:
        pop af
        ld (hl),a
        cp 255
        jr z,.insert
        ld l,b
        ld h,high X_PREV
        ld c,(hl)
        ld l,a
        ld (hl),c
.insert:
        ld h,high X_HEAD
        ld l,e
        ld a,(hl)
        ld (hl),b
        ld l,b
        ld h,high X_NEXT
        ld (hl),a
        ld h,high X_PREV
        ld (hl),255
        inc h
        ld (hl),1               ; X_LINKED
        cp 255
        jr z,.out
        ld l,a
        ld h,high X_PREV
        ld (hl),b
.out:   pop hl
        pop bc
        pop af
        ret

V_CACHE_BEST EQU 0xC72E
G_HEAD EQU 0xD000
G_NEXT EQU 0xD100
G_PREV EQU 0xD200
G_LINKED EQU 0xD300
g_link:
        push de
        push af
        ld a,(VG)
        ld e,a
        pop af
        push af
        push bc
        push hl
        ld b,l                  ; entry
        ld h,high G_LINKED
        ld a,(hl)
        or a
        jr z,.insert
        ld h,high GL
        ld a,(hl)
        cp e
        jr z,.out               ; already in the right bucket
        ld c,a                  ; old bucket
        ld h,high G_NEXT
        ld a,(hl)
        push af                 ; old successor
        ld h,high G_PREV
        ld a,(hl)
        cp 255
        jr z,.head
        ld l,a
        ld h,high G_NEXT
        jr .unlink
.head:  ld l,c
        ld h,high G_HEAD
.unlink:
        pop af
        ld (hl),a
        cp 255
        jr z,.insert
        ld l,b
        ld h,high G_PREV
        ld c,(hl)
        ld l,a
        ld (hl),c
.insert:
        ld h,high G_HEAD
        ld l,e
        ld a,(hl)
        ld (hl),b
        ld l,b
        ld h,high G_NEXT
        ld (hl),a
        ld h,high G_PREV
        ld (hl),255
        inc h
        ld (hl),1               ; G_LINKED
        cp 255
        jr z,.out
        ld l,a
        ld h,high G_PREV
        ld (hl),b
.out:   pop hl
        pop bc
        pop af
        pop de
        ret

rom_end:

        ORG 0xC800              ; in the state page, so only with it mapped
; A paint's rows below the screen land in the room map: those writes stay. H rows, L columns, C left colour, B the rest,
; D y, E x. Keeps BC, DE. (Only from line 168 on: the third row is then 23, and column 32 of it is the map's first byte.)
over:   ld a,d
        cp 168
        ret c
        push bc
        push de
        ld a,e
        cp 128
        jr c,.x
        xor a
.x:     and 124
        rrca
        rrca
        ld e,a                  ; column
        ld a,l
        ld (OVC),a
        ld a,h                  ; rows
        ld (OVR),a
        ld a,d
        and 248
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,l
        add a,e
        ld l,a
        ld a,h
        adc a,0x58
        ld h,a                  ; HL = cell
.r:     push hl
        ld a,(OVC)
        ld e,a
        ld d,c                  ; D = this cell's colour
.c:     ld a,h
        cp 0x5B
        jr c,.n
        push hl
        inc h
        inc h
        inc h
        ld a,(hl)
        pop hl
        or a
        jr nz,.n
        ld (hl),d
.n:     ld d,b
        inc hl
        dec e
        jr nz,.c
        pop hl
        ld de,32
        add hl,de
        ld a,(OVR)
        dec a
        ld (OVR),a
        jr nz,.r
        pop de
        pop bc
        ret

; a paint: C, B = colours, D y, E x
attr:
        ld a,c
        call palb
        ld c,a
        ld a,b
        call palb
        ld b,a
        ld (VC),bc
        xor a
        ld (VF),a
        ld h,high X_HEAD
        ld l,e
        ld a,(hl)
.f:     cp 255
        jr z,.done
        ld l,a
        ld h,high EY
        ld a,(hl)
        cp d
        jr nz,.nx
        ld h,high ES
        ld a,(hl)
        cp 2
        jr nz,.nx
        ld a,l
        call setcol
        ld a,1
        ld (VF),a
.nx:    ld h,high X_NEXT
        ld a,(hl)
        jr .f
.done:  ld a,(VF)
        or a
        jr nz,.ex
        ld a,(LAST)
        or a
        jr z,.pend
        dec a
        call setcol
        jr .ex
.pend:  ld a,e
        ld (PX),a
        ld a,d
        ld (PY),a
        ld hl,(VC)
        ld (PC1),hl
        ld a,1
        ld (PV),a
.ex:    xor a
        ld (LAST),a
        ld a,(V_DEBT_MODE)
        cp 2
        jp z,a1_finish
        jp lv2

; A = entry: colours VC, show it. Keeps BC, DE, HL.
setcol:
        push hl
        ld l,a
        ld h,high C1
        ld a,(VC)
        cp (hl)
        jr nz,.changed
        inc h
        ld a,(VC+1)
        cp (hl)
        jr nz,.changed
        pop hl
        ret
.changed:
        ld a,l
        pop hl
        push bc
        push de
        push hl
        ld l,a
        ld h,high C1
        ld a,(VC)
        ld (hl),a
        inc h
        ld a,(VC+1)
        ld (hl),a
        ld a,l
        call show
        pop hl
        pop de
        pop bc
        ret

palb:   ld l,a
        and 7
        bit 6,l
        jr z,.n
        or 8
.n:     rlca
        rlca
        rlca
        rlca
        ret
st_end:

        ORG 0xD000
setup:
        ; Upload each small image once, never while a visible sprite uses it.
        ld bc,0x303B
        ld a,24
        out (c),a
        nextreg 0x55,PAT_S
        ld hl,0xA000
        ld d,32
        call .patterns
        ld bc,0x303B
        ld a,56
        out (c),a
        nextreg 0x55,PAT_P
        ld hl,0xA000
        ld d,2
        call .patterns
        nextreg 0x55,5
        jr .palette
.patterns:
        ld bc,0x005B
        otir
        dec d
        jr nz,.patterns
        ret
.palette:
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld d,0
.k:     ld e,0
.n:     ld a,e
        cp 1
        jr nz,.fx
        ld a,d
        add a,low gamecol
        ld c,a
        ld a,0
        adc a,high gamecol
        ld b,a
        ld a,(bc)
        jr .w
.fx:    ld a,e
        add a,low pal
        ld c,a
        ld a,0
        adc a,high pal
        ld b,a
        ld a,(bc)
.w:     nextreg 0x41,a
        inc e
        ld a,e
        cp 16
        jr nz,.n
        inc d
        ld a,d
        cp 16
        jr nz,.k
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2          ; sprite clip window: the play area (the plotters write nothing above line 32)
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,32
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
gamecol: DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6     ; RRRGGGBB: ink 0-7
        DB 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF      ; bright
pal:    DB 0x00,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4      ; entries 2-15: the same fixed colours in every offset, for painted pixels
        DB 0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "cy_rom.bin",0x2800,rom_end-0x2800
        SAVEBIN "cy_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "cy_st.bin",0xC800,st_end-0xC800
