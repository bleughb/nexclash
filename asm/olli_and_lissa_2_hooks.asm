; Olli and Lissa II: Halloween (Silverbird, 1987; 48K): the moving figures as hardware sprites.
; Facts and design: games/olli_and_lissa_2.md.
;
; The game plays with interrupts off. Each pass of its loop it draws every moving figure into a copy of the screen
; with one routine (0x92E7: HL -> the picture's address and, with A odd, its mask's; B = y, C = x, D = rows, E = bytes
; a row; it first saves what is under the figure) and then one routine (0x9453) copies each figure's rectangle to the
; screen and puts the copy back as it was. Nothing of the game changes:
;   e_fig               the JPs of the figure routine: 28 MHz; the figure's sprites (4-bit patterns: 1 where the
;                       graphic is set, 2 where the mask clears, or its painted tiles) go into the pattern set no
;                       sprite shows and the figure is staged; the game's routine; the rest of its own time waited
;                       out on the video line.
;   e_play              the CALL of the copy to the screen: the staged figures' sprites switched on, every other one
;                       off, the pattern sets change over; the copy itself runs as the original.
;   e_fade / e_scene    the CALLs of the fade to black (a new room, the title) and of the scene played on a black
;                       screen: every sprite off (the figures the game drew fade or go black with the screen).
; Code in the alt ROM from 0x2800; inside a hook the state page is at slot 0 and, while painted tiles are sent, their
; page at slot 2.
        DEVICE ZXSPECTRUMNEXT
WORK    EQU 26                  ; the state page
ADDER   EQU 0x92E7              ; the game's figure routine
PLAYER  EQU 0x9453              ; its copy to the screen
FADE    EQU 0x9AC4              ; the screen faded to black
SCENE   EQU 0x82B9              ; a scene played on a black screen
V_SPEED EQU 0x0100
HLIB_V_R EQU 0x0101             ; 3 bytes
V_SP    EQU 0x0104              ; word: the game's stack inside a hook
V_RET   EQU 0x0106              ; word: the game's return address
V_KIND  EQU 0x0108              ; the figure: 0 16 rows of 2 bytes, 1 24 rows of 3, 2 24 rows of 3 with a mask
V_A     EQU 0x0109              ; the routine's arguments
V_HL    EQU 0x010A              ; word
V_BC    EQU 0x010C
V_DE    EQU 0x010E
V_T     EQU 0x0112              ; word: the routine's own time, 1/16 lines (0 = not known: it runs as the original)
V_W     EQU 0x0114              ; bytes a row of the graphic
V_ROWS  EQU 0x0115              ; rows of the graphic
V_TX    EQU 0x0116              ; sprites across
V_TY    EQU 0x0117              ; sprites down
V_G     EQU 0x0118              ; word: graphic
V_M     EQU 0x011A              ; word: mask (0 = none)
V_BOX   EQU 0x011C              ; rows of the figure's box
V_N     EQU 0x011E              ; sprites of this figure
V_LINE  EQU 0x011F              ; its palette line
V_OX    EQU 0x0120              ; the box's x
V_I     EQU 0x0121
V_TR    EQU 0x0122
V_TC    EQU 0x0123
V_X     EQU 0x0124              ; word
V_Y     EQU 0x0126
V_FULL  EQU 0x0127              ; figures left as the game draws them: no room in the stage or the pattern set
V_ODD   EQU 0x0128              ; ... a size, a place or a kind the hooks do not hold
V_NP    EQU 0x0129              ; painted figures in PIDX (the build sets it; 0 = the plain colours)
V_PAGE  EQU 0x012B
V_SRC   EQU 0x012C              ; word
V_NS    EQU 0x0133              ; figures staged
V_PN    EQU 0x0134              ; the next pattern of the set being filled
V_SET   EQU 0x0135              ; that set's first pattern: 0 or 64
V_SHOWN EQU 0x0136              ; sprites switched on
V_PAT   EQU 0x0137              ; this figure's first pattern
V_CE    EQU 0x0138              ; word: its entry in CACHE
V_TCP   EQU 0x013A              ; the tile cache: the page being filled (the build starts it at TC0)
V_TCA   EQU 0x013C              ; word: where its next tiles go (the build starts it after the index and the scratch tiles)
V_DST   EQU 0x013E              ; word
HLIB_V_PACE EQU 0x0140          ; 26 bytes
HLIB_PACE_NL EQU 312
HSTK    EQU 0x0300              ; the hooks' stack, below this
STG     EQU 0x0300              ; NSTG staged figures of 8 bytes: x (word), y, sprites across, down, line, sprites, first pattern
NSTG    EQU 12
CACHE   EQU 0x0380              ; 128 x 5 bytes: what the patterns from this one hold: graphic (0 = nothing known), mask, line
MB      EQU 0x0600              ; 64 rows of 6 bytes: the figure's box, 1 = kept by the mask
GB      EQU 0x0800              ; the graphic, as the mask is laid out
TLO     EQU 0x0A00              ; (graphic nibble << 4 | mask nibble) -> the first two pixels
THI     EQU 0x0B00              ;                                       the last two
TT      EQU 0x0C00              ; 3 x 8 x 16 words: the routine's own time by kind, shift, class of y (the build fills it)
YC      EQU 0x0F00              ; 3 x 176: the class of y by kind (the build fills it)
YMAX    EQU 176
PIDX    EQU 0x1600              ; painted figures, 8 bytes each: graphic, rows, bytes, page, address, line
TC0     EQU 40                  ; the tile cache's first page: its index at 0x4000 (256 entries of 8 bytes: graphic, mask,
                                ; page, address), the scratch tiles, then tiles; NTC pages in all
NTC     EQU 8
SCRATCH EQU 0x4800              ; 8 tiles made each time
TFIRST  EQU 0x4C00
TPROBE  EQU 8                   ; entries looked at for a picture

        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_LEAN
        DEFINE HLIB_PACE_CAP 0x0C00
        INCLUDE "lib/hlib_pace.asm"


; ---------------------------------------------------------------- the JPs of the figure routine
e_fig:  nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_R_IN               ; (on the hooks' stack: nothing is written below the game's)
        HLIB_SPEED_IN V_SPEED
        ld (V_A),a
        ld (V_HL),hl
        ld (V_BC),bc
        ld (V_DE),de
        call size               ; V_T = the routine's own time, or 0
        ld hl,(V_T)
        ld a,h
        or l
        jp z,asis
        call hlib_pace_open
        call sprite
.n_rin: ld a,R_IN
        call hlib_r_set
        ld bc,(V_BC)
        ld de,(V_DE)
        ld sp,(V_SP)
        ld hl,fig_end
        ex (sp),hl              ; the routine returns here
        ld (V_RET),hl
        ld hl,(V_HL)
        ld a,(V_A)
        HLIB_R_OUT
        nextreg 0x50,255
        jp ADDER
fig_end:
        nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ld hl,D_FIG             ; the hook's own entry and exit, outside the window
        call hlib_debt_add
.n_t:   ld hl,(V_T)
        HLIB_SPEED_OUT V_SPEED
        ld a,(V_SPEED)
        call hlib_pace_wait
.n_rout: ld a,R_OUT
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        push hl
        ld hl,(V_RET)
        ex (sp),hl              ; the game's return address, where the game's own CALL left it
        HLIB_R_OUT
        nextreg 0x50,255
        ret
; A figure the hooks do not hold: the routine as the original runs it, the hook's time owed to the next window.
asis:   ld hl,D_ASIS
        call hlib_debt_add
        HLIB_SPEED_OUT V_SPEED
.n_r:   ld a,R_ASIS
        call hlib_r_set
        ld bc,(V_BC)
        ld de,(V_DE)
        ld hl,(V_HL)
        ld sp,(V_SP)
        ld a,(V_A)
        HLIB_R_OUT
        nextreg 0x50,255
        jp ADDER
R_IN    EQU 0                   ; (the routine sets R itself; R after it is set by R_OUT, from the verifier's comparison)
R_OUT   EQU 116
R_ASIS  EQU 0
D_FIG   EQU 91                  ; calibrated so a figure takes the original's time (games/olli_and_lissa_2.md)
D_ASIS  EQU 40

; ---------------------------------------------------------------- the CALLs before which the sprites change
; Every register and flag passes through.
        MACRO PREHOOK target, drop
        nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_R_IN               ; (on the hooks' stack: nothing is written below the game's)
        HLIB_SPEED_IN V_SPEED
        push af
        push bc
        push de
        push hl
        IF drop
        xor a
        ld (V_NS),a             ; (figures drawn in a pass that ends before its copy to the screen)
        ENDIF
        call commit             ; -> HL = its time, 1/16 lines
        call hlib_debt_add
        HLIB_SPEED_OUT V_SPEED
        ld a,R_PLAY
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x50,255
        jp target
        ENDM
e_play: PREHOOK PLAYER, 0
e_fade: PREHOOK FADE, 1
e_scene: PREHOOK SCENE, 1
R_PLAY  EQU 116
D_PLAY  EQU 35                  ; the hook with nothing to switch
D_SPR   EQU 4                   ; ... and a sprite more

; ---------------------------------------------------------------- the sprites change
; The staged figures' sprites on, every other sprite off; the other pattern set is the one to fill.
commit: xor a
        ld (V_I),a
        ld a,(V_NS)
        or a
        jr z,.hide
        ld b,a
        ld hl,STG
.fig:   push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_X),de
        ld a,(hl)
        inc hl
        ld (V_Y),a
        ld a,(hl)
        inc hl
        ld (V_TX),a
        ld a,(hl)
        inc hl
        ld (V_TY),a
        ld a,(hl)
        inc hl
        ld (V_LINE),a
        inc hl
        ld a,(hl)
        inc hl
        ld (V_PAT),a
        push hl
        call attrs
        pop hl
        pop bc
        djnz .fig
.hide:  ld a,(V_SHOWN)
        ld c,a
        ld a,(V_I)
        ld (V_SHOWN),a
.off:   cp c
        jr nc,.done
        nextreg 0x34,a
.n_off: nextreg 0x38,0
        inc a
        jr .off
.done:  xor a
        ld (V_NS),a
        ld a,(V_SET)
        xor 64
.n_set: ld (V_SET),a
        ld (V_PN),a
        ld a,(V_SHOWN)
        ld e,a
        ld d,D_SPR
        mul d,e
        ld hl,D_PLAY
        add hl,de
        ret

; The attributes of one figure's sprites: V_X, V_Y, V_TX, V_TY, V_LINE, patterns from V_PAT, sprites from V_I.
attrs:  ld b,0                  ; the sprite's row
.tr:    ld c,0
.tc:    ld a,(V_I)
        nextreg 0x34,a
        ld a,c
        swapnib
        ld hl,(V_X)
        add hl,a
        ld a,l
        nextreg 0x35,a
        ld a,(V_LINE)
        swapnib
.n_x8:  or h
        nextreg 0x37,a
        ld a,b
        swapnib
        ld l,a
        ld a,(V_Y)
        add a,l
        nextreg 0x36,a
        ld a,(V_PAT)            ; the pattern, 0-127: N6 is its bit 0
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld a,(V_PAT)
        srl a
.n_vis: or 0xC0
        nextreg 0x38,a
        ld hl,V_PAT
        inc (hl)
        ld hl,V_I
        inc (hl)
        inc c
        ld a,(V_TX)
        cp c
        jr nz,.tc
        inc b
        ld a,(V_TY)
        cp b
        jr nz,.tr
        ret

; ---------------------------------------------------------------- what the routine is asked for
; V_A / V_BC / V_DE = its arguments. -> V_KIND, V_T = its own time (0: a size, a place or flags the hooks do not hold).
size:   ld hl,0
        ld (V_T),hl
        ld de,(V_DE)            ; D rows, E bytes
        ld a,(V_A)
        or a
        jr z,.nomask
        rra
        jr nc,.odd              ; (a mask loaded and not used)
        ld a,d
        cp 24
        jr nz,.odd
        ld a,e
        cp 3
        jr nz,.odd
        ld a,2
        jr .kind
.nomask:
        ld a,e
        cp 2
        jr nz,.three
        ld a,d
        cp 16
        jr nz,.odd
        xor a
        jr .kind
.three: cp 3
        jr nz,.odd
        ld a,d
        cp 24
        jr nz,.odd
        ld a,1
.kind:  ld (V_KIND),a
        ld c,a
        ld a,(V_BC + 1)         ; y
        cp YMAX
        jr nc,.odd
        ld e,c
        ld d,YMAX
        mul d,e
        add de,a
        ld hl,YC
        add hl,de
        ld b,(hl)               ; the class of y
        ld a,c
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(V_BC)
        and 7
        or c                    ; kind x 8 + shift
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,b
        add hl,a
        add hl,hl
        add hl,TT
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_T),hl
        ret
.odd:   ld hl,V_ODD
        inc (hl)
        ret

; ---------------------------------------------------------------- a figure's sprites
sprite: ld hl,(V_HL)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_G),de
        ld de,0
        ld a,(V_KIND)
        cp 2
        jr nz,.nm
        ld e,(hl)
        inc hl
        ld d,(hl)
.nm:    ld (V_M),de
        ld bc,(V_BC)            ; B y, C x
        ld l,c
        ld h,0
        add hl,32               ; the display from 32
        ld a,(V_KIND)
        or a
        jr nz,.big
        ld a,16
        ld (V_ROWS),a
        ld (V_BOX),a
        ld a,2
        ld (V_W),a
        dec a
        ld (V_TX),a
        ld a,206                ; line 174 - y is the box's first
        jr .go
.big:   ld e,a
        ld a,24
        ld (V_ROWS),a
        ld (V_BOX),a
        ld a,3
        ld (V_W),a
        dec a
        ld (V_TX),a
        dec e
        jr z,.top
        ld a,26                 ; a masked figure's box is its mask's: the graphic a row down and a pixel right
        ld (V_BOX),a
        dec hl
.top:   ld a,206
.go:    ld (V_X),hl
        sub b
        ld (V_Y),a
        ld a,(V_BOX)
        add a,15
        swapnib
        and 15
        ld (V_TY),a
        ld c,a
        ld a,(V_TX)
        ld b,a
        xor a
.mul:   add a,c
        djnz .mul
        ld (V_N),a
        ; room in the stage and in the set
        ld a,(V_NS)
        cp NSTG
        jp nc,.full
        ld a,(V_SET)
        ld c,a
        ld a,(V_PN)
        ld (V_PAT),a
        sub c
        ld hl,V_N
        add a,(hl)
        cp 65
        jp nc,.full
        ; the same picture in these patterns already (the sets come round every second pass): nothing is sent
        ld a,(V_PAT)
        ld e,a
        ld d,5
        mul d,e
        ld hl,CACHE
        add hl,de
        ld (V_CE),hl
        ld de,(V_G)
        ld a,(hl)
        cp e
        jr nz,.send
        inc hl
        ld a,(hl)
        cp d
        jr nz,.send
        inc hl
        ld de,(V_M)
        ld a,(hl)
        cp e
        jr nz,.send
        inc hl
        ld a,(hl)
        cp d
.n_ch:  jr nz,.send
        inc hl
        ld a,(hl)
        ld (V_LINE),a
        jr .stage
.send:  call upload
        ld hl,(V_CE)
        ld de,(V_G)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_M)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_LINE)
        ld (hl),a
        inc hl
        ld a,(V_N)              ; the patterns after the first are this figure's too: nothing known starts there
        dec a
        jr z,.stage
        ld b,a
        xor a
.inv:   ld (hl),a
        inc hl
        ld (hl),a
        add hl,4
        djnz .inv
.stage:
        ; staged
        ld a,(V_NS)
        add a,a
        add a,a
        add a,a
        ld hl,STG
        add hl,a
        ld de,(V_X)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,(V_TX)
        ld (hl),a
        inc hl
        ld a,(V_TY)
        ld (hl),a
        inc hl
        ld a,(V_LINE)
        ld (hl),a
        inc hl
        ld a,(V_N)
        ld (hl),a
        inc hl
        ld a,(V_PAT)
        ld (hl),a
        ld hl,V_N
        add a,(hl)
        ld (V_PN),a
        ld hl,V_NS
.n_st:  inc (hl)
        ret
.full:  ld hl,V_FULL
        inc (hl)
        ret

; The figure's pictures into the patterns from V_PAT: its painted tiles, or 1 where the graphic is set and 2 where
; the mask clears. The plain tiles are made once a picture and kept in the tile cache (pages from TC0: an index of
; 256 entries by graphic and mask, then the tiles); with the cache full they are made each time.
upload: xor a
        ld (V_LINE),a
        ld a,(V_NP)
        or a
        jr z,.cache
        ld b,a
        ld de,(V_G)
        ld hl,PIDX
.s:     ld a,(hl)
        cp e
        jr nz,.sn
        inc hl
        ld a,(hl)
        dec hl
        cp d
        jr z,.hit
.sn:    ld a,8
        add hl,a
        djnz .s
        jr .cache
.hit:   inc hl
        inc hl
        ld a,(V_ROWS)
        cp (hl)
        jr nz,.cache
        inc hl
        ld a,(V_W)
        cp (hl)
        jr nz,.cache
        inc hl
        ld a,(hl)
        ld (V_PAGE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (V_LINE),a
        jp .out
.cache: nextreg 0x52,TC0
        ld hl,(V_G)
        ld a,l
        xor h
        ld hl,(V_M)
        xor l
        ld c,a                  ; the first entry to look at
        ld b,TPROBE
.pr:    ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        ld (V_SRC),hl
        inc hl
        ld a,(hl)
        dec hl
        or a
        jr z,.miss              ; (no graphic is in page 0: an empty entry)
        ld de,(V_G)
        ld a,(hl)
        cp e
        jr nz,.pn
        inc hl
        ld a,(hl)
        cp d
        jr nz,.pn
        inc hl
        ld de,(V_M)
        ld a,(hl)
        cp e
        jr nz,.pn
        inc hl
        ld a,(hl)
        cp d
        jr nz,.pn
        inc hl
        ld a,(hl)
        ld (V_PAGE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        jp .out
.pn:    inc c
        djnz .pr
        jr .scr                 ; (no entry free near it: made each time)
.miss:  ld a,(V_N)              ; room for V_N tiles of 128 bytes
        ld d,a
        ld e,0
        srl d
        rr e
        ld hl,(V_TCA)
        add hl,de
        ld a,h
        cp 0x60
        jr c,.fits
        jr nz,.next
        ld a,l
        or a
        jr z,.fits
.next:  ld a,(V_TCP)
        inc a
        cp TC0 + NTC
.n_fl:  jr nc,.scr
        ld (V_TCP),a
        ld hl,0x4000
        ld (V_TCA),hl
        add hl,de
.fits:  ld de,(V_TCA)
        ld (V_TCA),hl
        ld hl,(V_SRC)
        ld bc,(V_G)
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld bc,(V_M)
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld a,(V_TCP)
        ld (hl),a
        ld (V_PAGE),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        jr .make
.scr:   ld a,TC0
        ld (V_PAGE),a
        ld de,SCRATCH
.make:  ld a,(V_PAGE)
        nextreg 0x52,a
        push de
        ld (V_DST),de
        call plain
        pop de
.out:   ld a,(V_PAGE)
        nextreg 0x52,a
        ex de,hl                ; HL = the tiles, one after another
        ld a,(V_PAT)
        ld e,a
        ld a,(V_N)
.pt:    push af
        ld a,e
        inc e
        call selpat
        ld bc,0x805B
.n_ot:  otir
        pop af
        dec a
        jr nz,.pt
        nextreg 0x52,10
        ret

; The figure's tiles, 128 bytes each, to V_DST on.
plain:  ld a,(V_TY)             ; the rows the sprites take: kept by the mask, no graphic
        ld e,a
        ld d,96
        mul d,e
        dec de
        push de
        ld b,d
        ld c,e
        ld hl,MB
        ld de,MB + 1
        ld (hl),0xFF
        ldir
        pop bc
        ld hl,GB
        ld de,GB + 1
        ld (hl),0
        ldir
        ld hl,(V_M)
        ld a,h
        or l
        jr z,.nomask
        ; the mask: 5 bytes a row, the box's rows; the box starts at its bit 7 (a pixel left of the graphic)
        ld de,MB
        ld a,(V_BOX)
        ld b,a
.mr:    push bc
        push de
        ld a,(hl)
        inc hl
        rra                     ; (its last bit is the box's first)
        ld b,4
.mb:    ld a,(hl)
        inc hl
        rra
        ld (de),a
        inc de
        djnz .mb
        pop de
        ld a,6
        add de,a
        pop bc
        djnz .mr
        ld hl,(V_G)             ; the graphic: a row down and a pixel right
        ld de,GB + 6
        ld a,(V_ROWS)
        ld b,a
.gr:    push bc
        push de
        or a
        ld b,3
.gb:    ld a,(hl)
        inc hl
        rra
        ld (de),a
        inc de
        djnz .gb
        ld a,0
        rra
        ld (de),a
        pop de
        ld a,6
        add de,a
        pop bc
        djnz .gr
        jr .pats
.nomask:
        ld hl,(V_G)
        ld de,GB
        ld a,(V_ROWS)
        ld b,a
.g:     push bc
        push de
        ld a,(V_W)
        ld c,a
        ld b,0
        ldir
        pop de
        ld a,6
        add de,a
        pop bc
        djnz .g
.pats:  xor a
        ld (V_TR),a
.tr:    xor a
        ld (V_TC),a
.tc:    ld a,(V_TR)
        ld e,a
        ld d,96
        mul d,e
        ld a,(V_TC)
        add a,a
        add de,a
        ld hl,MB
        add hl,de
        ld de,(V_DST)
        ld b,16
.row:   push bc
        push hl
        call one
        inc hl
        call one
        pop hl
        ld a,6
        add hl,a
        pop bc
        djnz .row
        ld (V_DST),de
        ld a,(V_TC)
        inc a
        ld (V_TC),a
        ld hl,V_TX
        cp (hl)
        jr c,.tc
        ld a,(V_TR)
        inc a
        ld (V_TR),a
        ld hl,V_TY
        cp (hl)
        jr c,.tr
        ret

; HL -> a mask byte (its graphic byte 0x200 above): its eight pixels, 4 bytes, to DE on.
one:    ld c,(hl)
        inc h
        inc h
        ld b,(hl)
        dec h
        dec h
        push hl
        ld a,c
        swapnib
        and 0x0F
        ld l,a
        ld a,b
        and 0xF0
        or l
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        ld a,b
        swapnib
        and 0xF0
        ld l,a
        ld a,c
        and 0x0F
        or l
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
.n_o:   ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        pop hl
        ret

; A = a 4-bit pattern, 0-127: the pattern port at its first byte. Keeps DE, HL.
selpat: srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ret
CODE_END:
ROM_END:
        SAVEBIN "olli2_rom.bin",0x2800,ROM_END-0x2800

        ORG 0xD000
; The stub's setup: the sprites' palette, every sprite off, the printer buffer as the snapshot has it.
setup:  ld hl,pbuf
        ld de,0x5B00
        ld bc,256
        ldir
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal9
        ld b,0
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        nextreg 0x43,0x00
        nextreg 0x4B,0          ; a pattern's 0 is clear
        xor a
.so:    nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jp p,.so
        nextreg 0x1C,2          ; the sprites' window: the whole display
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0x01       ; sprites on, over the ULA, inside the display; a later sprite is in front
        nextreg 0x07,0
        ret
pal9:   DS 512
pbuf:   DS 256                  ; the snapshot's 0x5B00-0x5BFF (the build fills it in)
SETUP_END:
        SAVEBIN "olli2_setup.bin",0xD000,SETUP_END-0xD000
