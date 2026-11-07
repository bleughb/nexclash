; Cobra (Ocean, 1986, 48K) - figures as hardware sprites. Facts and design: games/cobra.md.
; The game redraws the whole play area every game loop (PUSH blits), then masks figures onto the
; screen with one plotter (39865 loop; rows come in pairs, 3 columns, boustrophedon, words = mask
; (E), gfx (D)). Pixel classes: gfx 1 = INK (dark), mask 0 + gfx 0 = PAPER (the body, which takes
; the cell's paper: that is the clash), else transparent. The plotter hook writes 4-bit patterns
; (cached per plot index) and up to 4 sprites, and no screen bytes.
;
; Sites (original bytes checked by cobra.py):
;   39865 D1 7E A3  POP DE/LD A,(HL)/AND E  -> JP e_plot   plotter loop
;   40714 73 24 72  bullet write            -> JP e_bul    (+ 40733, 40735 write -> NOP)
;   36427, 43524 CD E3 9A CALL 39651        -> CALL e_frame
;   36599 CD E3 9A CALL 39651 (death loop, no scene redraw) -> CALL e_frd: frozen figures stay, pieces above them
;   36317 21 38 8D  LD HL,36152             -> JP e_rnd    ROUND screen: hide all
;   45046, 45731 CD 69 A3 CALL 41833        -> CALL e_txt  menu, high score: hide all
; Memory: this code in alt ROM image 1 (0x386E-); state in Next page SCRPAGE, mapped at slot 2 (0x4000)
; only inside a hook. The ISR (0xFFFF, 0xFFF4, 0xA67C) touches only AF, R and its stack.
; Colour map (patch.runtime-colour-map): index in the page at OVIDX; per painted image a plane in pages 28-35,
; 15 bytes a row (3 columns of 4 nibble bytes + a transparent mask). An upload copies its plane to BUF: the
; pages are mapped at slot 6, which the ISR never touches, only for that LDIR.

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"   ; card patch.restore-speed: the caller's speed back at every exit

SCRPAGE EQU 26
ULAPAGE EQU 10
MAXP    EQU 16
GAME_SP EQU 41721
MONO    EQU 64729
FIGS    EQU 39651
TEXT    EQU 41833
PLOTEND EQU 39918
BULNEXT EQU 40717
RNDNEXT EQU 36320
T_FIX16 EQU 16          ; the plot hook's parts at the caller's clock (entry to spd_in's NEXTREG, exit after
                        ; spd_out's, the JP into it): about 215 T = 15 sixteenths of a line, not in the window
DBT_HIDE0 EQU 12        ; the same for the outside hooks (patch.pace-limiter debt), measured on the verifier's model:
DBT_FRAME EQU 32+DBT_HIDE0  ;   e_frame + its CALL FIGS, and hide_rest's quick path prepaid: it runs after the
DBT_HIDE EQU 24-DBT_HIDE0   ;   figures, so the next frame would repay it; hide_rest with sprites to hide, less that
DBT_BUL EQU 22          ;   e_bul, less the original's three instructions it replaces
PIDX    EQU 0x5800      ; the prepared-pattern store (cobra.py store_index): (address - PBASE) / 8 -> entry + 1
PENT    EQU 0x5240      ; entries: address lo, hi, row pairs, page, offset lo, hi (0xC000 + offset in that page)
PBASE   EQU 46544       ; the first image's graphics (profile colour_images)
PIDXN   EQU 1812        ; (61040 - PBASE) / 8: entries of PIDX
HLIB_V_PACE EQU 0x4060  ; 26 bytes of hook page RAM (0x4060-0x4079), zero at start (asm/lib/hlib_pace.asm)
HLIB_PACE_NL EQU 312    ; 48K timing, 50 Hz: lines a frame

nslot   EQU 0x4000
nprev   EQU 0x4001
palv    EQU 0x4002
vc      EQU 0x4003
svsp    EQU 0x4004
vscr    EQU 0x4006
vrows   EQU 0x4008
vptr    EQU 0x4009
vpat    EQU 0x400B
vleft   EQU 0x400C
vupl    EQU 0x400D
vbase   EQU 0x400E
vdeath  EQU 0x400F
tmp     EQU 0x4010      ; 8 bytes: bullet rows as mask/gfx pairs
stamps  EQU 0x4020      ; MAXP * 3
vov     EQU 0x4050
vpl     EQU 0x4051
vpb     EQU 0x4053
vkey    EQU 0x4055
vcopy   EQU 0x4057
tmpo    EQU 0x4059      ; 4 bytes
vspd    EQU 0x405E      ; the incoming speed (NR 7 bits 1:0), HLIB_SPEED_IN / OUT
HSTK    EQU 0x4100
BUF     EQU 0x4400      ; the image's plane, up to 480 bytes
KEEP    EQU 0x4600      ; v -> the nibbles of the default byte v leaves alone
CLR     EQU 0x4700      ; 2 mask bits -> AND mask, 4 bytes
OVIDX   EQU 0x5000      ; count, then (start lo, hi, row pairs, page, plane lo, hi)
CLS     EQU 0x4200      ; (from cobra.py) index gggg mmmm -> left byte at CLS, right byte at CLS+256

        ORG 0x386E
COLTAB: DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6     ; paper -> RGB332
        DB 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF     ; BRIGHT

; ---- CALL 39651 (draw all figures) ----
e_frd:  ld a,1
        jr fr0
e_frame:
        xor a
fr0:    push hl
        push af
        ld a,(MONO)
        or a
        ld l,15                 ; colour mode: bright white body
        jr z,.col
        ld a,(0x5803)           ; mono: the play area's one paper
        rrca
        rrca
        rrca
        and 15
        ld l,a
.col:   ld a,l
        add a,low COLTAB
        ld l,a
        ld h,high COLTAB
        ld l,(hl)
        nextreg 0x52,SCRPAGE
        call spd_in
        call dbt_open
        ld a,(palv)
        cp l
        jr z,.same
        ld a,l
        ld (palv),a
        nextreg 0x43,0x20
        nextreg 0x40,1
        nextreg 0x41,a
.same:  pop af
        or a
        jr nz,.dth
        ld (vbase),a
        ld (vdeath),a
        jr .go
.dth:   ld a,(vdeath)
        or a
        jr nz,.go
        inc a
        ld (vdeath),a
        ld a,(nprev)
        ld (vbase),a
.go:    ld a,(vbase)
        ld (nslot),a
        ld a,DBT_FRAME
        call dbt_close
        call spd_out
        nextreg 0x52,ULAPAGE
        pop hl
        call FIGS
e_fend: ; falls into hide_rest with every register kept
hide_rest:
        push af
        push bc
        nextreg 0x52,SCRPAGE
        ld a,(nprev)
        ld b,a
        ld a,(nslot)
        ld (nprev),a
        cp b
        jr c,.slow              ; fewer figures than last time: hide the rest (28 MHz)
        nextreg 0x52,ULAPAGE    ; else nothing to do, at the caller's clock (its time prepaid by e_frame)
        pop bc
        pop af
        ret
.slow:  call spd_in
        call dbt_open
n_hide: cp b
        jr nc,.done
        ld c,a
        add a,a
        add a,a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        ld a,c
        inc a
        jr n_hide
.done:  ld a,DBT_HIDE
        call dbt_close
        call spd_out
        nextreg 0x52,ULAPAGE
        pop bc
        pop af
        ret

hide_all:
        push af
        nextreg 0x52,SCRPAGE
        xor a
        ld (nslot),a
        ld (vbase),a
        ld (vdeath),a
        nextreg 0x52,ULAPAGE
        pop af
        jr hide_rest

e_txt:  call hide_all
        jp TEXT

e_rnd:  call hide_all
        ld hl,36152
        jp RNDNEXT

; ---- plotter: HL = screen, B = row pairs, SP = graphics ----
e_plot: nextreg 0x52,SCRPAGE
        ld (svsp),sp
        ld sp,HSTK
        call spd_in
        ld (vscr),hl
        ld a,c
        ld (vc),a
        ld a,b
        ld (vrows),a
        call hlib_pace_open     ; card patch.pace-limiter: the window is the original plot loop's time
        xor a
        ld (vupl),a
n_show: ld a,(nslot)
        cp MAXP
        jr nc,plot_exit
        ld e,a
        inc a
        ld (nslot),a
        ld a,e
        add a,a
        add a,e
        ld hl,stamps
        add hl,a
        ld a,(svsp)
        cp (hl)
n_k1:   jr nz,plot_new
        inc hl
        ld a,(svsp+1)
        cp (hl)
        dec hl
n_k2:   jr nz,plot_new
        inc hl
        inc hl
        ld a,(vrows)
        cp (hl)
        dec hl
        dec hl
n_hit:  jr z,plot_show
plot_new:
        ld a,(svsp)
        ld (hl),a
        inc hl
        ld a,(svsp+1)
        ld (hl),a
        inc hl
        ld a,(vrows)
        ld (hl),a
        ld (vupl),a             ; row count, never 0
        push de
        call upload
        pop de
plot_show:
        call attrs
plot_exit:
        call pace_plot          ; wait until the original loop's time has passed (less the debt), at 28 MHz
        ld a,(vrows)
        ld b,a
        ld d,a
        ld e,12
        mul d,e
        ld hl,(svsp)
        add hl,de
        dec hl
        ld d,(hl)
        dec hl
        ld e,(hl)
n_c:    ld a,(vc)
        ld c,a
        ld hl,(vscr)
        ld sp,(GAME_SP)
plot_nav:                       ; HL, A, F as the original loop leaves them (its screen walk, no writes)
        inc l
        inc l
        inc h
        dec l
        dec l
        inc h
        ld a,h
        and 6
        jr nz,plot_n2
        ld a,l
        add a,32
        ld l,a
        jr c,plot_n2
        ld a,h
        sub 8
        ld h,a
plot_n2:
        djnz plot_nav
        call spd_out
n_map:  nextreg 0x52,ULAPAGE
        jp PLOTEND

; patterns of plot index E: up to two bands of (2 columns, 1 column)
upload: ld hl,(svsp)
        ld (vptr),hl
        ld (vkey),hl
        ld a,(vrows)
        push de
        ld d,a
        ld e,30
        mul d,e
        ld (vcopy),de
        call ovfind
        pop de
        ld a,e
        add a,a
        add a,a
        ld (vpat),a
        ld a,(vov)
        or a
        jr nz,.slow             ; a painted image: its plane, per pixel
        call pstore             ; a known image: its prepared patterns (Z), else build them
        ret z
.slow:  ld a,(vrows)
        add a,a
        ld (vleft),a
.band:  xor a
        call vband
        ld a,(vpat)
        call setpat
        ld hl,(vptr)
        ld a,(vleft)
        ld c,a
        ld b,8
.p0:    ld a,c
        or a
        jr z,.z0
        xor a
        call em
        ld a,2
        call em
        call v5
        ld a,10
        call em
        ld a,8
        call em
        call v5
        ld de,12
        add hl,de
        dec c
        dec c
        jr .n0
.z0:    call zero8
        call zero8
.n0:    djnz .p0
        ld a,10
        call vband
        ld a,(vpat)
        inc a
        call setpat
        ld hl,(vptr)
        ld a,(vleft)
        ld c,a
        ld b,8
.p1:    ld a,c
        or a
        jr z,.z1
        ld a,4
        call em
        call zero4
        call v10
        ld a,6
        call em
        call zero4
        call v10
        ld de,12
        add hl,de
        dec c
        dec c
        jr .n1
.z1:    call zero8
        call zero8
.n1:    djnz .p1
        ld hl,(vptr)
        ld de,96
        add hl,de
        ld (vptr),hl
        ld hl,(vpb)
        ld de,240
        add hl,de
        ld (vpb),hl
        ld a,(vpat)
        add a,2
        ld (vpat),a
        ld a,(vleft)
        sub 16
        ret c
        ret z
        ld (vleft),a
        jp .band

vband:  ld hl,(vpb)              ; vpl = this band's plane + A
        add hl,a
        ld (vpl),hl
        ret
v10:    call v5
v5:     ld a,(vov)
        or a
        ret z
        push hl
        ld hl,(vpl)
        ld a,5
        add hl,a
        ld (vpl),hl
        pop hl
        ret

setpat: srl a                   ; A = 4-bit pattern number
        jr nc,.ev
        or 0x80
.ev:    push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ret

em:     ld e,a                  ; pair at HL+A -> 4 pattern bytes, by the class table in the page
        ld a,(vov)
        or a
        ld a,e
        jp nz,em_p
        push hl
        add hl,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        and 0xF0
        ld l,a
        ld a,e
        swapnib
        and 15
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        ld a,d
        swapnib
        and 0xF0
        ld l,a
        ld a,e
        and 15
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        pop hl
        ret

zero8:  call zero4
zero4:  xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        ret

; sprites 4E..4E+3 at (vscr): vrows = 0 marks a bullet (one sprite)
attrs:  ld hl,(vscr)
        ld a,h
        and 0x18
        rlca
        rlca
        rlca
        ld b,a
        ld a,h
        and 7
        or b
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
n_y:    add a,32
        ld c,a                  ; C = Y
        ld a,l
        and 31
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,l
        add a,32
        ld l,a
        ld a,h
        adc a,0
        ld h,a                  ; HL = X
        ld a,e
        add a,a
        add a,a
        ld b,a                  ; B = sprite and pattern number
        call one
        ld a,(vrows)
        or a
        jr z,.hide3
        call right
        ld a,(vrows)
        cp 9
        jr c,.hide2
        ld a,c
        add a,16
        ld c,a
        inc b
        call one
        jr right
.hide3: inc b
        call off
.hide2: inc b
        call off
        inc b
off:    ld a,b
        nextreg 0x34,a
        nextreg 0x38,0
        ret
right:  inc b
        push hl
        ld de,16
        add hl,de
        call one
        pop hl
        ret
one:    ld a,b
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,c
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,b
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; ---- bullet: E, D = rows 0 and 3, D, E again; HL = screen. Overwrites its byte: every pixel opaque ----
e_bul:  nextreg 0x52,SCRPAGE
        ld (svsp),sp
        ld sp,HSTK
        call spd_in
        call dbt_open
        ld a,c
        dec a
        ld (vptr),a             ; the bullet's graphics, low byte
        push bc
        push de
        push hl
        ld (vscr),hl
        xor a
        ld (vrows),a
        ld a,(nslot)
        cp MAXP
        jr nc,.x
        ld c,a
        inc a
        ld (nslot),a
        ld a,c
        add a,a
        add a,c
        ld hl,stamps
        add hl,a
        ld a,e
        cp (hl)
        jr nz,.new
        inc hl
        ld a,d
        cp (hl)
        dec hl
        jr nz,.new
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        cp 0xFF
        jr z,.show
.new:   ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),0xFF
        ld hl,tmp
        ld (hl),0
        inc hl
        ld (hl),e
        inc hl
        ld (hl),0
        inc hl
        ld (hl),d
        inc hl
        ld (hl),0
        inc hl
        ld (hl),d
        inc hl
        ld (hl),0
        inc hl
        ld (hl),e
        push bc
        ld a,(vptr)
        ld d,a
        ld e,12
        mul d,e
        inc d
        ld (vkey),de            ; 0x100 + 12 x low byte: its own range in the index
        ld hl,60
        ld (vcopy),hl
        call ovfind
        pop bc
        ld a,c
        add a,a
        add a,a
        call setpat
        ld hl,tmp
        ld b,4
.r:     xor a
        call em
        call zero4
        call v10
        inc hl
        inc hl
        djnz .r
        ld b,12
.z:     call zero8
        djnz .z
.show:  ld e,c
        call attrs
.x:     pop hl
        pop de
        pop bc
        ld a,DBT_BUL
        call dbt_close
        call spd_out
        ld sp,(svsp)
        nextreg 0x52,ULAPAGE
        inc h
        jp BULNEXT

; speed latch (asm/lib/hlib_speed.asm), slot 2 = the hook page: latch the caller's speed, 28 MHz / back to it
spd_in: HLIB_SPEED_IN vspd
        ret
spd_out:
        HLIB_SPEED_OUT vspd
        ret

ROM_END:
        SAVEBIN "cobra_rom.bin",0x386E,ROM_END-0x386E

; ---- in the hook page, run with it mapped ----
        ORG 0x4800
ovfind: xor a                   ; vkey inside a painted image -> its plane at BUF, vov = 1
        ld (vov),a
        ld a,(OVIDX)
        or a
        ret z
        ld b,a
        ld hl,OVIDX+1
ov_l:   ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl                  ; DE = image start, HL -> row pairs
        push hl
        ld hl,(vkey)
        or a
        sbc hl,de
        jr c,ov_n                ; before this image
        ex de,hl                ; DE = offset
        pop hl
        push hl
        ld a,(hl)
        push de
        ld d,a
        ld e,12
        mul d,e                 ; DE = the image's graphics bytes
        pop hl                  ; HL = offset
        or a
        sbc hl,de
        jr nc,ov_n               ; past it
        add hl,de               ; HL = offset, a top-clipped plot starts inside
        srl h
        rr l                    ; offset / 2: 6 per row pair
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de               ; x 5 = 30 per row pair
        pop de                  ; -> row pairs
        inc de
        ld a,(de)
        ld b,a                  ; page
        inc de
        ld a,(de)
        add a,l
        ld l,a
        inc de
        ld a,(de)
        adc a,h
        ld h,a                  ; plane, this plot's first row
        ld a,b
        nextreg 0x56,a
        ld de,BUF
        ld bc,(vcopy)
        ldir
n_slot6:
        nextreg 0x56,0
        ld a,1
        ld (vov),a
        ld hl,BUF
        ld (vpb),hl
        ld (vpl),hl
        ret
ov_n:   pop hl
        ld de,4
        add hl,de
        djnz ov_l
        ret

em_p:   push hl                 ; as em, then the plane at vpl: AND mask, keep, colour
        push bc
        add hl,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        and 0xF0
        ld l,a
        ld a,e
        swapnib
        and 15
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        ld (tmpo),a
        inc h
        ld a,(hl)
        ld (tmpo+1),a
        ld a,d
        swapnib
        and 0xF0
        ld l,a
        ld a,e
        and 15
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        ld (tmpo+2),a
        inc h
        ld a,(hl)
        ld (tmpo+3),a
        ld hl,(vpl)
        ld de,4
        add hl,de
        ld c,(hl)               ; transparent mask
        ld hl,(vpl)
        ld de,tmpo
        ld b,4
.l:     ld a,c
        rlca
        rlca
        ld c,a
        and 3
        push hl
        ld hl,CLR
        add hl,a
        ld a,(de)
        and (hl)
        ld (de),a
        pop hl
        ld a,(hl)
        inc hl
        push hl
        ld l,a
        ld h,high KEEP
        ld h,(hl)
        ld a,(de)
        and h
        or l
        out (0x5B),a
        inc de
        pop hl
        djnz .l
        inc hl
        ld (vpl),hl             ; past the mask: 5 bytes a column
        pop bc
        pop hl
        ret
; ---- the pace limiter (asm/lib/hlib_pace.asm) and the prepared-pattern store, run with the page mapped ----
        INCLUDE "lib/hlib_pace.asm"        ; the current library (consistent readings; was HLIB_PACE_V1 until 2026-11-07)

; pace_plot: the original loop's time for vrows row pairs from screen row vscr: 252 T a pair (18 sixteenths) less 5,
; and about 32 T more at each character row it enters (y0 + 2B) / 8 times; less T_FIX16. Waits at 28 MHz: interrupts
; are off at every plot but the death loop's, whose handler (0xA67C) only sets R and so keeps its clock-free result.
pace_plot:
        ld a,(vrows)
        ld e,a
        ld d,18
        mul d,e                 ; DE = 18 B
        ld b,a
        ld a,(vscr+1)
        and 7
        add a,b
        add a,b
        rrca
        rrca
        rrca
        and 31                  ; C = crossings
        ld b,a
        add a,a
        srl b
        srl b
        add a,b                 ; 2.25 C
        add a,e
        ld e,a
        adc a,d
        sub e
        ld d,a
        ld hl,-T_FIX16
        add hl,de
        jr c,.w
        ld hl,0
.w:     ld a,(vspd)
        jp hlib_pace_wait

; dbt_open / dbt_close: an outside hook's time into the debt (hlib_debt_open / _close); every register kept, A = the
; hook's unmeasured part (sixteenths) for dbt_close
dbt_open:
        push af
        push bc
        push de                 ; the current library's hlib_debt_open loses DE (its consistent reading); V1's kept it
        push hl
        call hlib_debt_open
        pop hl
        pop de
        pop bc
        pop af
        ret
dbt_close:
        push bc
        push de
        push hl
        call hlib_debt_close
        pop hl
        pop de
        pop bc
        ret

; pstore: plot (svsp, vrows) is a stored image -> its patterns from the store at slot 6 into vpat.., Z; else NZ
pstore: ld hl,(svsp)
        ld de,-PBASE
        add hl,de
        jr nc,pst_no
        ld a,l
        and 7
        jr nz,pst_no
        ld b,3
pst_sh: srl h
        rr l
        djnz pst_sh
        ld de,PIDXN
        or a
        sbc hl,de
        jr nc,pst_no
        add hl,de
        ld de,PIDX
        add hl,de
        ld a,(hl)
        or a
        jr z,pst_no
        dec a
        ld e,a
        ld d,6
        mul d,e
        ld hl,PENT
        add hl,de
        ld a,(svsp)
        cp (hl)
        jr nz,pst_no
        inc hl
        ld a,(svsp+1)
        cp (hl)
        jr nz,pst_no
        inc hl
        ld a,(vrows)
        cp (hl)
        jr nz,pst_no
        inc hl
        ld a,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        nextreg 0x56,a
        ld a,(vpat)
        call setpat
        ex de,hl
        ld bc,0x005B            ; B = 0: 256 bytes, a band's two patterns
        otir
        ld a,(vrows)
        cp 9
        jr c,pst_one
        otir
pst_one:
n_slot6b:
        nextreg 0x56,0
        xor a
        ret
pst_no: or 1
        ret
PAGE_END:
        SAVEBIN "cobra_page.bin",0x4800,PAGE_END-0x4800

; ---- setup, run once by the NEX stub ----
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,1
        ld hl,.pal
        ld b,15
.pl:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pl
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,24         ; x 24..239, y 0..143: what the game's black cells leave visible
        nextreg 0x19,239
        nextreg 0x19,0
        nextreg 0x19,143
        nextreg 0x15,0x01
        ret
; 1 body (white), 2 dark (black): the default look. 3-15: paintable, the Spectrum's other colours.
.pal:   DB 0xFF,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
SETUP_END:
        SAVEBIN "cobra_setup.bin",0xD000,SETUP_END-0xD000
