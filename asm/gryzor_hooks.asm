; Gryzor (Ocean 1987, 48K form) - every moving figure as a hardware sprite (games/gryzor.md).
;
; Layout (2026-11-05 import, after the pilot's 2026-11-03 engine):
; - Alt ROM image 1 = Sinclair's 48K ROM (patch.whole-altrom-image), with this file's GATE bytes and the start-up
;   register block in its 0xFF area (GATE..). The game sees that image at 0x0000-0x3FFF outside the hooks.
; - Next page PAGE holds the hooks' code, state and stacks, and the same GATE bytes at the same addresses. A hook site
;   jumps to a gate entry in the ROM, whose NEXTREG $51,PAGE maps the page into slot 1 under itself: the next
;   instruction comes from the page. A gate exit's NEXTREG $51,$FF maps the ROM back; the next comes from the ROM.
;   The page keeps FF FF at 0x39FF (the game's IM 2 vector, I = 0x39) like the ROM. Game memory is never written but
;   for 46081, which the original's LD (46081),SP writes too.
; - Each tick the game blits the play area (39557), then plots figures straight on the screen. The stores of the five
;   figure loops are NOPs, so the ULA shows only scenery; each loop's LD (46081),SP jumps to a hook, which gives the
;   image, screen address and rows to sprites. Interrupts are off at every hook site (the verifier counts IFF).
; - Every hook: 28 MHz inside, the caller's speed restored at exit (patch.restore-speed), R left as the original's at
;   the return point (patch.preserve-r), the pace limiter for the ORIGINAL target (patch.pace-limiter): each plot waits
;   for the time the original's stores would have taken, the star hook for the original star routine's time, the tick
;   hook pays its time into the debt.
; - Patterns: the listed images' 4-bit patterns are prepared at build time (gryzor.store_pages) in Next pages STORE..,
;   copied with OTIR runs (optimise.pattern-cache); an unlisted image is assembled from the colour plane (pages
;   PLANE.., 4-bit pixels by graphics address: plane offset = 2 * (a - 0x6000)) as before. Cache: NC groups of 4
;   patterns, key = image address + shape, replaced in rotation, never a group shown this tick or the last.
; - Star routine 38168 (CALL at 34849) is the hook e_star: it flips the stars on the build's screen as the original
;   routine would there, and works out what the original saw - the figures drawn over each star byte, from this
;   tick's plot records - so that R, A and F at the return are the original's: the game takes random numbers from R
;   (35115, 39152), and the original's path length depends on whether a figure sits in a star's byte.

        DEVICE ZXSPECTRUMNEXT

SPSAVE  EQU 46081
ROWS    EQU 46035
GB      EQU 0x6000
PAGE    EQU 24
PLANE   EQU 26          ; first page of the colour plane (banks 13-17)
NMAX    EQU 64          ; sprites
NC      EQU 32          ; cache groups of 4 patterns
NREC    EQU 40          ; plot records a tick (the recordings' most: under 20)
STARS   EQU 38191       ; the star routine's table: 20 screen addresses
NSTARS  EQU 20
GATE    EQU 0x386E      ; Sinclair's ROM is 0xFF here up to 0x3CFF; the game's IM 2 vector 0x39FF-0x3A00 stays FF FF
HLIB_PACE_NL EQU 312    ; 48K timing

; pace constants, in 3.5 MHz T (games/gryzor.md "Pace"). ST_T = a figure store's time (LD (HL),A 7 T against NOP 4 T,
; plus the screen write's contention); FIXP / FIXS / FIXT = a hook's own time outside its window (JP or CALL to the
; gate, the gate, the entry before 28 MHz, the exit after it).
    IFNDEF ST_T
ST_T    EQU 4
    ENDIF
    IFNDEF SC_T
SC_T    EQU 1           ; contention a star's screen read or write, average
    ENDIF
FIXP    EQU 267
FIXS    EQU 237
FIXT    EQU 237

        ORG 0x2000

        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"        ; the current library (consistent readings; was HLIB_PACE_V1 until 2026-11-07)

; ---------------------------------------------------------------------------------------------------------------
; plot hooks. Entered from the gate with the game's registers; interrupts off. Each replaces its whole loop: the
; original runs LD (46081),SP, the loop's set-up, then a row of 2 lines at a time (POP DE, then LD A,(HL) / AND / OR /
; LD (HL),A per byte, INC L / DEC L across and back, INC H a line, and at the row's end the screen-address step), then
; LD SP,(46081) and RET. The hook gives the figure to sprites and leaves every register as that loop leaves it - those
; depend on the image and the geometry only, never on the screen: B = 0, DE = the last pair popped (clip: E = E' after a
; row that crosses a character row), HL stepped, A and F from the last row's step, C as at the site (clip: A') - and R
; as the loop's M1 count leaves it, then jumps to the loop's LD SP,(46081). lsim works them out row by row, with the
; loop's T-states (pace window target) and M1s. The stores are NOPs too, so nothing on the ULA could ever show a figure.
; ---------------------------------------------------------------------------------------------------------------
        MACRO PLOT_IN kindv
        ld (SPSAVE),sp
        ld sp,hstack
        push af
        push bc
        HLIB_SPEED_IN_ABC vspd
        pop bc
        push bc
        push de
        push hl
        HLIB_R_IN
        call hlib_pace_open
        ld a,kindv
        ld (pk),a
        pop hl
        pop de
        pop bc
        push bc
        push de
        push hl
        ld (s_hl),hl
        ld (s_de),de
        ld (s_bc),bc
        ENDM

        MACRO PLOT_OUT dest
        call lsim
        call pace_plot
        ld a,(pm1)
        add a,RD_P
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af                  ; the game's; now the loop's final registers
        ld hl,(faf)
        push hl
        pop af
        ld bc,(fbc)
        ld de,(fde)
        ld hl,(fhl)
        HLIB_R_OUT
        HLIB_SPEED_OUT vspd
        jp dest
        ENDM

; 4 columns, HL image, DE screen, B rows (2 lines each)
b_c4:   PLOT_IN 1
        ld a,0xF0
        ld (cmask),a
        ld a,4
        call plot
        PLOT_OUT gx_c4

; 3 columns
b_c3:   PLOT_IN 0
        ld a,0xE0
        ld (cmask),a
        ld a,3
        call plot
        PLOT_OUT gx_c3

; 5 columns
b_c5:   PLOT_IN 2
        ld a,0xF8
        ld (cmask),a
        ld a,5
        call plot
        PLOT_OUT gx_c5

; 4 columns clipped at a screen edge: C = column mask for one row's 8 pops (bits 7-4: the first line's columns 0-3).
; Bit 7 clear: the left edge, DE is c columns before the row start, c = leading zero bits. B is not the rows yet:
; the loop loads it from (46035) after the site.
b_clip: PLOT_IN 4
        ld a,c
        and 0xF0
        ld (cmask),a
        xor a
        ld b,4
.z:     rlc c
        jr c,.d
        inc a
        djnz .z
.d:     ld (skip),a
        add a,e
        ld e,a
        ld a,(ROWS)
        ld b,a
        ld a,4
        call plot
        xor a
        ld (skip),a
        PLOT_OUT gx_clip

; bullet: 2 columns, 4 lines, IX image (mask, graphics), HL screen
b_b4:   PLOT_IN 3
        ex de,hl
        push ix
        pop hl
        ld a,0xC0
        ld (cmask),a
        ld a,1
        ld (kind),a
        ld b,2
        ld a,2
        call plot
        xor a
        ld (kind),a
        PLOT_OUT gx_b4

; --- the loop's results -----------------------------------------------------------------------------------------
; kind table: prefix T (2), prefix M1, row T (2), row M1, pops a row, crossing T, crossing M1 (clip: + 17 T, + 4 M1
; per drawn byte a row; the row step's no-carry branch: + 15 T, + 3 M1); the last DJNZ is 5 T shorter
KT:     dw 30
        db 4
        dw 250
        db 40, 6, 25, 4         ; c3
        dw 30
        db 4
        dw 322
        db 52, 8, 25, 4         ; c4
        dw 30
        db 4
        dw 394
        db 64, 10, 25, 4        ; c5
        dw 37
        db 5
        dw 178
        db 28, 4, 25, 4         ; b4
        dw 47
        db 6
        dw 318
        db 47, 8, 57, 12        ; clip

lsim:   ld a,(pk)
        ld l,a
        add a,a
        add a,a
        add a,a
        sub l                   ; 9 bytes a kind... 7 x k + 2 x k
        add a,l
        add a,l
        ld e,a
        ld d,0
        ld hl,KT
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (ptT),de             ; T = prefix
        ld a,(hl)
        inc hl
        ld (pm1),a              ; M1 = prefix
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (rT),de
        ld a,(hl)
        inc hl
        ld (rM),a
        ld a,(hl)
        inc hl
        ld (rpops),a
        ld a,(hl)
        inc hl
        ld (xT),a
        ld a,(hl)
        ld (xM),a
; rows, screen start, image, drawn bytes a row
        ld a,(pk)
        cp 4
        jr z,.k
        cp 3
        jr z,.b
        ld a,(s_bc+1)           ; c kinds: B rows, HL image, DE screen
        ld (rws),a
        ld hl,(s_hl)
        ld (simg),hl
        ld hl,(s_de)
        ld a,(rpops)
        jr .g
.b:     ld a,2                  ; bullet: LD B,2; IX image, HL screen
        ld (rws),a
        ld hl,(gfx)
        ld (simg),hl
        ld hl,(s_hl)
        ld a,4
        jr .g
.k:     ld a,(ROWS)             ; clip: B = (46035); HL image, DE screen; C = the 8-bit mask
        ld (rws),a
        ld hl,(s_hl)
        ld (simg),hl
        ld a,(s_bc)
        ld b,0
.n:     or a
        jr z,.nd
        add a,a
        jr nc,.n
        inc b
        jr .n
.nd:    ld a,b                  ; drawn bytes a row
        ld (rdrawn),a
        add a,a
        add a,a                 ; + 4 M1 each
        ld hl,rM
        add a,(hl)
        ld (hl),a
        ld a,(rdrawn)
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de               ; 17 T each
        ld de,(rT)
        add hl,de
        ld (rT),hl
        ld hl,(s_de)
        ld a,(rdrawn)
.g:     ld (rdrawn),a
        ld (cur),hl             ; the loop's HL: the screen start
; rows: T += row T, M1 += row M1; the step: H + 2; (H AND 6) = 0: a character row: L + 32 (clip: carry from
; ((L + E') mod 256) + 32), no carry: H - 8, + 15 T / 3 M1
        ld a,(rws)
        or a
        jr z,.z                 ; (never: the verifier counts it)
        ld b,a
.row:   push bc
        ld hl,(ptT)
        ld de,(rT)
        add hl,de
        ld (ptT),hl
        ld a,(rM)
        ld hl,pm1
        add a,(hl)
        ld (hl),a
        ld hl,(cur)
        inc h
        inc h
        ld (prev),hl            ; the step's input: the last row's is run again for A and F
        ld a,h
        and 6
        jr nz,.nx
        ld a,(xT)
        ld e,a
        ld d,0
        ld a,(xM)
        ld c,a
        ld a,(pk)
        cp 4
        jr nz,.c
        exx
        ld a,e
        exx
        add a,l
        add a,32
        jr .cy
.c:     ld a,l
        add a,32
.cy:    push af
        ld a,l
        add a,32
        ld l,a
        pop af
        jr c,.cr
        ld a,h
        sub 8
        ld h,a
        ld a,e
        add a,15
        ld e,a
        inc c
        inc c
        inc c
.cr:    push hl
        ld hl,(ptT)
        add hl,de
        ld (ptT),hl
        ld a,(pm1)
        add a,c
        ld (pm1),a
        pop hl
.nx:    ld (cur),hl
        pop bc
        djnz .row
.z:     ld hl,(ptT)
        ld de,-5                ; the last DJNZ
        add hl,de
; contention estimate: SC_T a screen read and write of each byte drawn, and a popped byte in 0x4000-0x7FFF
        ld a,(rdrawn)
        add a,a
        ld e,a
        ld d,0
        ld a,(simg+1)
        cp 0x80
        jr nc,.ce
        ld a,(rpops)
        add a,a
        add a,e
        ld e,a
        ld a,0
        adc a,d
        ld d,a
.ce:    push hl
        ld a,(rws)
        ld b,a
        ld hl,0
        inc b
        jr .cm1
.cm:    add hl,de
.cm1:   djnz .cm
        ld d,h
        ld e,l
        pop hl
        DUP SC_T
        add hl,de
        EDUP
        ld (ptT),hl
; the last pair popped: image + 2 x (rows x pops a row - 1)
        ld a,(rws)
        ld b,a
        ld a,(rpops)
        ld e,a
        ld d,0
        ld hl,0
        inc b
        jr .p1
.p:     add hl,de
.p1:    djnz .p
        dec hl
        add hl,hl
        ld de,(simg)
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the last pair, as POP DE
        ld bc,(s_bc)            ; C as at the site (clip: replaced by A' below)
        ld b,0
; the last row's step again, the loop's own instructions, for A and F (and clip's E and C)
        ld hl,(prev)
        ld a,(pk)
        cp 4
        jr z,.kl
        ld a,h
        and 6
        jr nz,.f
        ld a,l
        add a,32
        ld l,a
        jr c,.f
        ld a,h
        sub 8
        ld h,a
        jr .f
.kl:    ld a,h
        and 6
        jr nz,.ky
        exx
        ld a,e
        exx
        ld e,a
        ld a,l
        add a,e
        add a,32
        ld l,a
        jr c,.kx
        ld a,h
        sub 8
        ld h,a
.kx:    ld a,l
        sub e
        ld l,a
.ky:    ex af,af'
        ld c,a
        ex af,af'
.f:     push af
        pop af
        ld (fbc),bc
        ld (fde),de
        ld (fhl),hl
        push af
        pop hl
        ld (faf),hl
        ret

; the plot window's end: wait until the original's loop would have ended, less this hook's time outside the window
pace_plot:
        ld hl,(ptT)
        ld de,FIXP
pace_t: or a                    ; HL = displaced T, DE = the hook's T outside its window
        sbc hl,de
        jr nc,.pos
        ld de,0                 ; the hook alone costs more: the excess to the debt, a zero target
        ex de,hl
        or a
        sbc hl,de               ; HL = excess T
        call t16
        ld de,(HLIB_V_PACE + 4)
        add hl,de
        jr c,.cap
        ld a,h
        cp 0xC0
        jr c,.st
.cap:   ld hl,0xBFFF
.st:    ld (HLIB_V_PACE + 4),hl
        ld hl,0
        jr .w
.pos:   call t16
.w:     ld a,(vspd)
        jp hlib_pace_wait

; T (3.5 MHz) -> 1/16 lines: ((T >> 4) x 73) >> 6 (224 T a line: x 16 / 224 = / 14). T < 0x8C00. AF, DE lost.
t16:    push bc
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l                    ; T / 16
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,hl               ; 8 x
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl               ; 64 x
        add hl,de
        add hl,bc               ; 73 x
        ld b,6
.s:     srl h
        rr l
        djnz .s                 ; / 64
        pop bc
        ret

; --- one plot: A = columns, B = rows, HL = image, DE = screen; skip = columns off the left; cmask, kind set -----------
plot:   ld (w),a
        ld (gfx),hl
        ld (scr),de
        ld a,b
        ld (rows),a
        call record             ; every plot, drawn or not: the star hook needs what the original drew
        ld a,(gfx+1)
        cp high GB
        ret c                   ; not a graphics address: the verifier counts a figure with no sprite
        ld a,(nsp)
        cp NMAX-5
        ret nc                  ; no sprite free: the same
        ld a,(w)
        rrca
        rrca
        rrca
        and 0xE0
        ld c,a
        ld a,(rows)
        or c
        ld (shape),a
; find the image in the cache: klo by CPIR, then khi and ksh
        ld hl,klo
        ld bc,NC
.s:     ld a,(gfx)
        cpir
        jr nz,.miss
        push hl
        ld de,NC-1
        add hl,de
        ld a,(gfx+1)
        cp (hl)
        jr nz,.no
        ld de,NC
        add hl,de
        ld a,(shape)
        cp (hl)
        jr z,.hit
.no:    pop hl
        ld a,b
        or c
        jr nz,.s
; miss: the next group in rotation not on show: not used this tick or the last, whose sprites are up until this
; tick replaces them (a group's patterns must not change under a sprite); after NC tries the group is taken anyway.
.miss:  ld a,(rr)
        ld e,a
        ld d,0
        ld b,NC
.try:   ld hl,used
        add hl,de
        ld a,(tick)
        sub (hl)
        cp 2
        jr nc,.free
        ld a,e
        inc a
        and NC-1
        ld e,a
        djnz .try
.free:  ld a,e
        inc a
        and NC-1
        ld (rr),a
        ld a,e
        ld (grp),a
        ld hl,klo
        add hl,de
.inval: ld a,(gfx)              ; the group's key: the image it now holds (the negative control drops this write)
        ld (hl),a
        ld bc,NC
        add hl,bc
        ld a,(gfx+1)
        ld (hl),a
        add hl,bc
        ld a,(shape)
        ld (hl),a
        call upload
        jr .mark
.hit:   pop de                  ; DE = klo + i + 1
        ld hl,0-klo-1
        add hl,de
        ld a,l
        ld (grp),a
.mark:  ld a,(grp)
        ld e,a
        ld d,0
        ld hl,used
        add hl,de
        ld a,(tick)
        ld (hl),a

; the sprites: 16 x 16 cells, in plot order
attrs:  ld a,(w)
        inc a
        srl a
        ld (ncols),a
        ld a,(rows)
        cp 9
        ld a,1
        jr c,.r1
        inc a
.r1:    ld (nrows),a
        ld a,(scr+1)            ; screen address -> y
        ld h,a
        and 7
        ld l,a
        ld a,h
        and 0x18
        add a,a
        add a,a
        add a,a
        or l
        ld l,a
        ld a,(scr)
        and 0xE0
        srl a
        srl a
        or l
        add a,32
        ld (ybase),a
        ld a,(scr)              ; column - skip -> x, + 32 (the border): never below 0
        and 31
        ld l,a
        ld a,(skip)
        ld h,a
        ld a,l
        sub h
        add a,4                 ; column + 4 >= 0
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; (column + 4) * 8 = x + 32
        ld (xbase),hl
        ld a,(grp)
        add a,a
        add a,a
        ld d,a                  ; first pattern
        ld a,(nrows)
        ld e,a
        ld a,(ybase)
        ld (ycur),a
        ld a,(nsp)
        ld c,a                  ; C = next sprite
.row:   ld hl,(xbase)
        ld a,(ncols)
        ld b,a
        push de
.col:   ld a,c
        nextreg 0x34,a
        inc c
        ld a,l
        nextreg 0x35,a
        ld a,(ycur)
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,d
        srl a
        or 0xC0                 ; visible, attribute 4 follows
        nextreg 0x38,a
        ld a,d
        and 1
        rrca
        rrca
        or 0x80                 ; 4-bit; bit 6 = half
        nextreg 0x39,a
        inc d
        ld a,l
        add a,16
        ld l,a
        jr nc,.nc
        inc h
.nc:    djnz .col
        pop de
        ld a,(ycur)
        add a,16
        ld (ycur),a
        inc d
        inc d
        dec e
        jr nz,.row
        ld a,c
        ld (nsp),a
        ret

; --- a plot record for the star hook: y0, c0 (signed column of the image's column 0), lines, w, cmask, kind, image --
record: ld a,(nrec)
        cp NREC
        ret nc                  ; full: the verifier counts it (never in the recordings)
        inc a
        ld (nrec),a
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; 8 bytes a record
        ld de,recs
        add hl,de
        ld a,(scr+1)
        ld b,a
        and 7
        ld c,a
        ld a,b
        and 0x18
        add a,a
        add a,a
        add a,a
        or c
        ld c,a
        ld a,(scr)
        and 0xE0
        rrca
        rrca
        or c
        ld (hl),a               ; y0
        inc hl
        ld a,(scr)
        and 31
        ld c,a
        ld a,(skip)
        ld b,a
        ld a,c
        sub b
        ld (hl),a               ; c0
        inc hl
        ld a,(rows)
        add a,a
        ld (hl),a               ; lines
        inc hl
        ld a,(w)
        ld (hl),a
        inc hl
        ld a,(cmask)
        ld (hl),a
        inc hl
        ld a,(kind)
        ld (hl),a
        inc hl
        ld de,(gfx)
        ld (hl),e
        inc hl
        ld (hl),d
        ret

; --- image -> pattern memory ------------------------------------------------------------------------------------
; A listed image: its prepared patterns (index pxlo / pxhi / pxsh / pxpg / pxol / pxoh / pxn, built by gryzor.py)
; copied from the store page at slot 3 with OTIR runs of 128 bytes. Anything else: from the colour plane.
upload: ld a,(grp)
        add a,a                 ; first pattern of the group in 256-byte slots x 2 = 128-byte units / 2
        ld bc,0x303B
        out (c),a
        ld a,(npx)
        or a
        jr z,slow
        ld c,a
        ld b,0
        ld hl,pxlo
.s:     ld a,(gfx)
        cpir
        jr nz,slow
        push hl
        push bc
        ld bc,NPX-1
        add hl,bc
        ld a,(gfx+1)
        cp (hl)
        jr nz,.no
        ld bc,NPX
        add hl,bc
        ld a,(shape)
        cp (hl)
        jr z,.hit
.no:    pop bc
        pop hl
        ld a,b
        or c
        jr nz,.s
        jr slow
.hit:   pop bc
        ld bc,NPX
        add hl,bc
        ld a,(hl)               ; page
        nextreg 0x53,a
        add hl,bc
        ld e,(hl)
        add hl,bc
        ld d,(hl)               ; offset in the page
        add hl,bc
        ld a,(hl)               ; 128-byte units
        pop hl
        ex de,hl
        ld de,0x6000
        add hl,de
        ld bc,0x805B
.o:     otir
        ld b,0x80
        dec a
        jr nz,.o
        nextreg 0x53,11
        ret

slow:   ld hl,(gfx)
        ld de,0-GB
        add hl,de
        ld a,0
        add hl,hl
        adc a,a                 ; offset 2 * (image - GB): 17 bits, A = bit 16
        call map17
        ld (pbase),hl
        ld a,(w)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld (stride),hl          ; 8 * W: one row of two lines
        ld a,(rows)
        add a,a
        ld (lines),a
        xor a
        ld (lnow),a
        ld a,(rows)
        cp 9
        ld a,1
        jr c,.r1
        inc a
.r1:    ld (nrows),a
        ld a,(w)
        inc a
        srl a
        ld (ncols),a
        ld a,(nrows)
        ld (rleft),a
.rw:    ld hl,0
        ld (cnow),hl
        ld a,(ncols)
        ld (cleft),a
.cl:    ld hl,(pbase)
        ld (pcur),hl
        ld a,(lnow)
        ld (lcur),a
        ld a,8
        ld (rcnt),a
.ln:    call line0              ; line of even number
        call line1              ; odd
        ld hl,(pcur)
        ld de,(stride)
        add hl,de
        ld (pcur),hl
        ld hl,lcur
        inc (hl)
        inc (hl)
        ld hl,rcnt
        dec (hl)
        jr nz,.ln
        ld hl,cnow
        inc (hl)
        inc (hl)
        ld hl,cleft
        dec (hl)
        jr nz,.cl
; next row of cells: 4 patterns a group, two per row (W = 5 has one row of three)
        ld a,(ncols)
        cp 2
        jr nz,.x
        ld hl,(stride)          ; 8 rows on
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(pbase)
        add hl,de
        ld (pbase),hl
        ld a,(lnow)
        add a,16
        ld (lnow),a
        ld hl,rleft
        dec (hl)
        jr nz,.rw
.x:     ; fall into unmap

unmap:  nextreg 0x52,10
        nextreg 0x53,11
        ret

; even line: column c at P + 4c. Two columns of the cell.
line0:  ld a,(cnow)
        ld c,a
        call .one
        inc c
.one:   ld a,(lcur)
        ld b,a
        ld a,(lines)
        cp b
        jr c,zero4
        jr z,zero4
        ld a,(w)
        dec a
        cp c
        jr c,zero4
        ld a,c
        add a,a
        add a,a
        ld hl,(pcur)
        add a,l
        ld l,a
        ld a,h
        adc a,0
        ld h,a
        jr out4c

; odd line: column c at P + 8W - 4(c + 1)
line1:  ld a,(cnow)
        ld c,a
        call .one
        inc c
.one:   ld a,(lcur)
        inc a
        ld b,a
        ld a,(lines)
        cp b
        jr c,zero4
        jr z,zero4
        ld a,(w)
        dec a
        cp c
        jr c,zero4
        ld hl,(pcur)
        ld de,(stride)
        add hl,de
        ld a,c
        inc a
        add a,a
        add a,a
        ld e,a
        ld d,0
        or a
        sbc hl,de
out4c:  push bc
        call out4
        pop bc
        ret

out4:   ld bc,0x045B
        otir
        ret

zero4:  xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        ret

; HL = plane offset, A = bit 16: map, -> HL = window address
map17:  ld b,a
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,b
        add a,a
        add a,a
        add a,a
        or c
        add a,PLANE
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        ret

; ---------------------------------------------------------------------------------------------------------------
; the other hooks: own stack tstack; their time outside any window goes to the pace debt (e_star has a window)
; ---------------------------------------------------------------------------------------------------------------
        MACRO T_IN
        ld (tsp),sp
        ld sp,tstack
        push af
        push bc
        HLIB_SPEED_IN_ABC vspd
        pop bc
        push bc
        push de
        push hl
        HLIB_R_IN
        ENDM

        MACRO T_OUT rdv
        ld a,rdv
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        HLIB_SPEED_OUT vspd
        ld sp,(tsp)
        ENDM

; a new tick: hide what the last tick did not draw, clear the plot records; replaces CALL 39557 (the blit)
b_tick: T_IN
        call hlib_debt_open
        ld a,(nsp)
        ld c,a
        call hide
        ld a,(tick)
        inc a
        ld (tick),a
        xor a
        ld (nrec),a
        ld a,FIXT * 16 / 224
        call hlib_debt_close
        T_OUT RD_T
        jp gx_tick

; C = sprites on show now: hide the rest of last time's
hide:   ld a,(shown)
        ld b,a
        ld a,c
        ld (shown),a
.h:     ld a,c
        cp b
        jr nc,.d
        nextreg 0x34,a
        xor a
        nextreg 0x38,a
        inc c
        jr .h
.d:     xor a
        ld (nsp),a
        ret

; screen clear 34509 (menu, game over, tape): no figures on these screens; replaces LD HL,16384
b_cls:  T_IN
        call hlib_debt_open
        call allhide
        ld a,FIXT * 16 / 224
        call hlib_debt_close
        T_OUT RD_C
        ld hl,16384
        jp gx_cls

; bitmap clear 42007 at 32869 (the level's end, before START TAPE; the game's own start): the same; replaces its CALL
b_clr:  T_IN
        call hlib_debt_open
        call allhide
        ld a,FIXT * 16 / 224
        call hlib_debt_close
        T_OUT RD_K
        jp gx_clr

allhide:
        ld a,(nsp)
        ld c,a
        ld a,(shown)
        cp c
        jr nc,.s
        ld a,c
        ld (shown),a
.s:     ld c,0
        xor a
        ld (nrec),a
        jp hide

; ---------------------------------------------------------------------------------------------------------------
; the stars: replaces CALL 38168. The original: B = 20; for each table entry DE: A = (DE); if A = 255 or A = 0,
; (DE) = A XOR 32. Its path is 2 M1 (9 T) longer for a 0 than for any other byte, and 3 T longer for a 255. In the
; original the byte holds the figures drawn over it this tick; in the build it holds the scenery only.
; Here: o = the build's byte b with this tick's plot records drawn over it in order ((o AND mask) OR graphics);
; the build's screen gets b XOR 32 where b is 0 or 255 (what the original routine does on the build's screen, the
; look of the approved build); R = the original's, from the count of o = 0; A, F = the last star's, from o; B = 0,
; DE = the last star's address, HL = the table's end, as the original leaves them. The window's target is the
; original's time: 1,787 T + 9 T per o = 0 + 3 T per o = 255, + SC_T per screen read and write.
; ---------------------------------------------------------------------------------------------------------------
b_star: T_IN
        call hlib_pace_open
        push ix
        xor a
        ld (n0),a
        ld (n255),a
        ld ix,STARS
        ld b,NSTARS
.k:     push bc
        ld e,(ix+0)
        ld d,(ix+1)
        inc ix
        inc ix
        ld (sde),de
        ld a,(de)
        ld (sb),a
        call orig               ; A = o
        ld (so),a
        or a
        jr nz,.n1
        ld hl,n0
        inc (hl)
.n1:    inc a
        jr nz,.n2
        ld hl,n255
        inc (hl)
.n2:    ld de,(sde)
        ld a,(sb)
        or a
        jr z,.f
        inc a
        jr nz,.nf
        dec a
.f:     xor 32
        ld (de),a
.nf:    pop bc
        djnz .k
        pop ix
; R: O = 3 + 20 x 10 + 2 x n0 M1 (LD B, LD HL, RET; a star 10, 12 for a 0)
        ld a,(n0)
        add a,a
        add a,RD_S
        call hlib_r_set
; pace: the original's time
        ld a,(n0)
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de               ; 9 n0
        ld a,(n255)
        ld e,a
        add hl,de
        add hl,de
        add hl,de               ; + 3 n255
        ld a,(n0)
        ld e,a
        ld a,(n255)
        add a,e
        ld e,a
        DUP SC_T
        add hl,de               ; + contention of the writes
        EDUP
        ld de,1787 + 20 * SC_T
        add hl,de
        ld de,FIXS
        call pace_t
; the original's last A and F, from the last star's o
        pop hl
        pop de
        pop bc
        pop af
        ld a,(so)
        cp 255
        jr z,.x
        or a
        jr nz,.y
.x:     xor 32
.y:     ld de,(sde)
        ld b,0
        ld hl,STARS + 2 * NSTARS
        HLIB_R_OUT
        HLIB_SPEED_OUT vspd
        ld sp,(tsp)
        jp gx_ret

; DE = a star's screen address, A = the build's byte there -> A = the original's byte: this tick's plot records drawn
; over it, in plot order. IX kept.
orig:   ld (so),a
        ld a,d                  ; DE -> y, column
        and 7
        ld c,a
        ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        or c
        ld c,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or c
        ld (sy),a
        ld a,e
        and 31
        ld (sc),a
        ld a,(nrec)
        or a
        jr z,.e
        ld b,a
        ld hl,recs
.r:     push bc
        push hl
        ld a,(sy)
        sub (hl)                ; dy = y - y0
        inc hl
        ld c,a
        inc hl
        cp (hl)                 ; < lines?
        jr nc,.nx
        dec hl
        ld a,(sc)
        sub (hl)                ; dc = column - c0 (c0 may be below 0)
        inc hl
        inc hl
        cp (hl)                 ; < w?
        jr nc,.nx
        ld e,a                  ; E = dc
        ld d,(hl)               ; D = w
        inc hl
        ld a,(hl)               ; cmask
        inc hl
        ld b,e
        inc b
.cm:    add a,a
        djnz .cm
        jr nc,.nx               ; column not drawn
        ld a,(hl)               ; kind
        ld (skd),a
        inc hl
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (simg),de
        pop de
; pair index p = (dy >> 1) x 2w + (dy even: dc; odd: 2w - 1 - dc)
        ld a,d
        add a,a
        ld d,a                  ; 2w
        ld a,c
        srl a                   ; row
        ld b,a
        xor a
        inc b
        jr .m1
.m:     add a,d
.m1:    djnz .m
        bit 0,c
        jr z,.ev
        add a,d
        dec a
        sub e
        jr .ix
.ev:    add a,e
.ix:    ld l,a
        ld h,0
        add hl,hl
        ld de,(simg)
        add hl,de               ; the pair's address
        ld a,(skd)
        or a
        ld a,(so)
        jr nz,.mg
        inc hl
        and (hl)                ; (graphics, mask)
        dec hl
        or (hl)
        jr .st
.mg:    and (hl)                ; bullets: (mask, graphics)
        inc hl
        or (hl)
.st:    ld (so),a
.nx:    pop hl
        ld de,8
        add hl,de
        pop bc
        djnz .r
.e:     ld a,(so)
        ret

code_end:
; --- state ------------------------------------------------------------------------------------------------------
vspd:   db 0
vr:     ds 3
HLIB_V_R EQU vr
vpace:  ds 26
HLIB_V_PACE EQU vpace
w:      db 0
skip:   db 0
rows:   db 0
shape:  db 0
grp:    db 0
rr:     db 0
nsp:    db 0
shown:  db 0
ncols:  db 0
nrows:  db 0
ybase:  db 0
ycur:   db 0
lines:  db 0
lnow:   db 0
lcur:   db 0
rcnt:   db 0
rleft:  db 0
cleft:  db 0
cmask:  db 0
kind:   db 0
nrec:   db 0
n0:     db 0
n255:   db 0
sb:     db 0
so:     db 0
sy:     db 0
sc:     db 0
skd:    db 0
cnow:   dw 0
pk:     db 0
pm1:    db 0
rM:     db 0
rpops:  db 0
xT:     db 0
xM:     db 0
rws:    db 0
rdrawn: db 0
ptT:    dw 0
rT:     dw 0
cur:    dw 0
prev:   dw 0
s_hl:   dw 0
s_de:   dw 0
s_bc:   dw 0
fbc:    dw 0
fde:    dw 0
fhl:    dw 0
faf:    dw 0
gfx:    dw 0
scr:    dw 0
xbase:  dw 0
pbase:  dw 0
pcur:   dw 0
stride: dw 0
tsp:    dw 0
sde:    dw 0
simg:   dw 0
tick:   db 2
npx:    db 0                ; listed images (gryzor.py writes it and the index)
klo:    ds NC
khi:    ds NC
ksh:    ds NC
used:   ds NC
recs:   ds NREC*8
        ds 48
tstack:
        ds 64
hstack:
NPX     EQU 128
pxlo:   ds NPX              ; the prepared-pattern index (gryzor.py writes it into the page)
pxhi:   ds NPX
pxsh:   ds NPX
pxpg:   ds NPX
pxol:   ds NPX
pxoh:   ds NPX
pxn:    ds NPX
hook_end:
        ASSERT hook_end <= GATE

; --- the gate: the same bytes in the alt ROM and in the page --------------------------------------------------
        ORG GATE
gate_lo:
e_c4:   nextreg 0x51,PAGE
        jp b_c4
e_c3:   nextreg 0x51,PAGE
        jp b_c3
e_c5:   nextreg 0x51,PAGE
        jp b_c5
e_clip: nextreg 0x51,PAGE
        jp b_clip
e_b4:   nextreg 0x51,PAGE
        jp b_b4
e_tick: nextreg 0x51,PAGE
        jp b_tick
e_cls:  nextreg 0x51,PAGE
        jp b_cls
e_clr:  nextreg 0x51,PAGE
        jp b_clr
e_star: nextreg 0x51,PAGE
        jp b_star
gx_c4:  nextreg 0x51,0xFF
        jp 40443                ; the loop's LD SP,(46081)
gx_c3:  nextreg 0x51,0xFF
        jp 40770                ; the loop's LD SP,(46081)
gx_c5:  nextreg 0x51,0xFF
        jp 40624                ; the loop's LD SP,(46081)
gx_clip:
        nextreg 0x51,0xFF
        jp 40308                ; the loop's LD SP,(46081)
gx_b4:  nextreg 0x51,0xFF
        jp 37713                ; the loop's LD SP,(46081)
gx_tick:
        nextreg 0x51,0xFF
        jp 39557
gx_cls: nextreg 0x51,0xFF
        jp 34512
gx_clr: nextreg 0x51,0xFF
        jp 42007
gx_ret: nextreg 0x51,0xFF
        ret
gate_hi:
regs:   ds 20               ; the start-up tail's register block (alt ROM and page)
gate_end:
        ASSERT gate_end <= 0x39FF
        ORG 0x39FF
        db 0xFF,0xFF        ; the game's IM 2 vector: I = 0x39, read at 0x39FF, 0x3A00 (the ROM's bytes)
page_end:

; R deltas (hlib_r_set): O - E - N mod 128, from games/gryzor.md "R"; the verifier compares R after every hook.
; plots: O = 2 (LD (46081),SP); tick, clear: O = 0 to the CALL's target; cls: O = 1 (LD HL,16384); star: O = 203 + 2 n0.
; measured on the simulator (hooklib.r_check against the original at every hook of the recordings)
RD_P    EQU 91
RD_T    EQU 90
RD_C    EQU RD_T - 1        ; its exit has one M1 more after the LD R,A (LD HL,16384)
RD_K    EQU RD_T
RD_S    EQU 37

; --- setup routine (stub bank, 0xD000): palette, hide all, clip, sprites on -----------------------------------
        ORG 0xD000
setup:  nextreg 0x4B,0
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.c:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .c
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,167        ; lines 168+ are ink = paper (attributes 0x6D): the water hides figures there
        nextreg 0x15,0x01
        ret
; 0 transparent, 1 black (outlines, the game's ink), 2 bright yellow (bodies: what a body shows on the figures' own
; band, paper 6, rows 8-11), then the Spectrum's others
pal:    db 0x00,0x00,0xFC,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFF
setup_end:

        SAVEBIN "gz_page.bin",0x2000,page_end-0x2000
        SAVEBIN "gz_setup.bin",0xD000,setup_end-0xD000
