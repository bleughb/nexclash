; Mad Mix 2 (Topo Soft, 1990, 128K), Enhanced: the Spec256 colours for stage group 1 on a double-buffered Layer 2.
;
; The game rebuilds its whole play window every update in a 1-bit back buffer (bank 0, DB00), tiles, then stars, then
; figures, and the interrupt handler copies that to the screen. All of it still runs, byte for byte, at 28 MHz inside K
; windows; the ULA picture is the original's underneath. After each piece of the back buffer the same piece goes on the
; Layer 2 back buffer in the set's colours. The flip is where the handler's copy starts: the beam is below the window. The copy itself ends
; with the beam in the window's upper rows, and the opaque picture hides the copy, so the new picture is simply a frame early.
;
; Colours are read from slot 0, Layer 2 is written through port 0x123B's write map, so both are at hand with interrupts on and no
; game memory paged out. While the write map is on nothing in the hook writes memory below 0x4000 and SP stays in the game's stack.
; The handler is wrapped: it runs at the game's clock, left out of the pace windows, the write map off; and it writes 0x7FFD, so its
; exit puts slots 0 and 1 back as they were.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 311
V_SPEED EQU 0x3E30
V_INH EQU 0x3E31               ; bit 0 a main-line hook is running, bit 1 at 28 MHz
V_S0 EQU 0x3E32                ; slot 0's page in the hook
V_WM EQU 0x3E33                ; the write map's bits of 0x123B, 0 = off
V_PORT EQU 0x3E34              ; bit 1: Layer 2 showing
V_R0 EQU 0x3E35
V_FRONT EQU 0x3E36
V_BACK EQU 0x3E37
V_ON EQU 0x3E38                ; this stage has colours
V_DRAWN EQU 0x3E39
V_ATTR EQU 0x3E3A
V_IR EQU 0x3E3B
V_IB EQU 0x3E3C
V_IRF EQU 0x3E3D
V_SHOW EQU 0x3E3E
V_GP EQU 0x3E3F                ; the page of the font and the lives (the build stores it)
V_FA EQU 0x3E40
V_FDE EQU 0x3E42
V_TGT EQU 0x3E60               ; word: this figure's time
V_TB EQU 0x3E44                ; word
V_TC EQU 0x3E46                ; word
P_MAP EQU 0x3E48               ; word: the row's first map cell
P_CELL EQU 0x3E4A              ; word
P_OFF EQU 0x3E4C
P_XS EQU 0x3E4D
P_Y EQU 0x3E4E
P_LEFT EQU 0x3E4F
P_N EQU 0x3E50
P_T EQU 0x3E51
P_X EQU 0x3E52
P_CL EQU 0x3E53
P_W EQU 0x3E54
P_ROWS EQU 0x3E55
P_MIR EQU 0x3E56
P_SRC EQU 0x3E58               ; word
P_STEP EQU 0x3E5A              ; word
P_SN EQU 0x3E5C
P_SA EQU 0x3E5E                ; word: list end
LIVES_ON EQU 0x1000
LIVES_OFF EQU 0x1240
STAR_LIST EQU 0x3900           ; 3 bytes a star, 60 stars
TBL EQU 0x3A00                 ; 105 figures: page, offset word, rows
regblock EQU 0x3C00
L2_A EQU 16
L2_B EQU 19
TILE_PAGE EQU 44
INK_I EQU 253
PAPER_I EQU 254
; the original's time for each piece, T states at 3.5 MHz from the replays, as 1/16 lines of 228 T; OV: the hook's own entry and exit at the game's clock
OV EQU 16
T_TILE00 EQU 109625*16/228-OV
T_TILE01 EQU 114515*16/228-OV
T_TILE10 EQU 146375*16/228-OV
T_TILE11 EQU 152540*16/228-OV
T_STAR EQU 23020*16/228-OV
R_TILE EQU -19
R_FIG EQU -19
R_STAR EQU -19
R_FIGZ EQU -10
R_FLIP EQU -10
R_HIDE EQU -10
R_TEXT EQU -19
R_LIVES EQU -10
R_ISR EQU -20
G_STAGE EQU 0x8E76
G_ATTR EQU 0x8E7B
G_CAMX EQU 0x8F80
G_CAMY EQU 0x8F82
G_MAP EQU 0xCD00
G_TIDX EQU 0x5C00
G_FIGS EQU 0xB36A
G_BUF EQU 0xDB00
G_STARS EQU 0x92BF
G_SMASK EQU 0xB068

        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ENDM
        MACRO LEAVE_R
        ld hl,V_INH
        ld (hl),0
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
        MACRO FAST
        HLIB_SPEED_IN V_SPEED
        ld a,3
        ld (V_INH),a
        ENDM

; ---- the tiles: 923F and the plot whole, then the same picture in colour
h_tile:
        ENTER
        FAST
        ld a,(G_STAGE)
        cp 3
        sbc a,a
        ld (V_ON),a
        jr nz,.on
        ld a,(V_SHOW)           ; no colours here: the original's picture
        or a
        call nz,l2_hide
.on:    call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0x923F
        call 0xAC49
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        call hlib_nest_open
        ld a,(V_ON)
        or a
        jr z,.no
        push ix
        push iy
        call col_tiles
        pop iy
        pop ix
        ld a,1
        ld (V_DRAWN),a
.no:    ld a,1
        call hlib_nest_close
        ld a,(G_CAMX)
        and 4
        add a,a
        ld l,a                  ; 0, 8
        ld a,(G_CAMY)
        and 15
        jr z,.t0
        ld a,4
.t0:    add a,l                 ; 0, 4, 8, 12
        rrca
        ld l,a
        ld h,0
        ld de,tile_times
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld a,(V_SPEED)
        call hlib_pace_wait
        ld a,R_TILE
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret

; ---- the stars: which ones land is found first, on the buffer as the game will find it; then the original's loop
h_star:
        ENTER
        FAST
        call hlib_pace_open
        call hlib_nest_open
        ld a,(V_ON)
        or a
        jr z,.no
        push ix
        call col_stars
        pop ix
.no:    ld a,1
        call hlib_nest_close
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld a,0x3C
        ld ix,G_STARS
        call 0xB030
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld hl,T_STAR
        ld a,(V_SPEED)
        call hlib_pace_wait
        ld a,R_STAR
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret

; ---- a figure
h_fig:
        nextreg 0x51,HOOK_PAGE
        cp 0xFF
        jr nz,.go
        HLIB_R_IN
        push af
        ld a,R_FIGZ
        call hlib_r_set
        pop af
        HLIB_R_OUT
        nextreg 0x51,255
        ret
.go:    push af
        ld a,r
        ld (HLIB_V_R),a
        pop af
        push af
        ld (V_FDE),de
        ld (V_FA),a
        push bc
        push de
        push hl
        FAST
        call fig_time
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0xA58E
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        call hlib_nest_open
        ld a,(V_ON)
        or a
        jr z,.no
        push ix
        push iy
        call col_fig
        pop iy
        pop ix
.no:    ld a,1
        call hlib_nest_close
        ld hl,(V_TGT)
        ld a,(V_SPEED)
        call hlib_pace_wait
        ld a,R_FIG
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret

; ---- the copy's start, in the handler, the beam below the window: the new picture goes up
h_flip:
        ENTER
        FAST
        ld a,(V_DRAWN)
        or a
        jr z,.none
        xor a
        ld (V_DRAWN),a
        ld a,(V_BACK)
        ld b,a
        ld a,(V_FRONT)
        ld (V_BACK),a
        nextreg 0x13,a
        ld a,b
        ld (V_FRONT),a
        nextreg 0x12,a
        ld a,(G_ATTR)
        ld hl,V_ATTR
        cp (hl)
        call nz,set_attr
        ld a,(V_SHOW)
        or a
        jr nz,.none
        ld a,1
        ld (V_SHOW),a
        ld a,2
        ld (V_PORT),a
        nextreg 0x69,0x80
.none:  ld hl,48
        call hlib_debt_add
        ld a,R_FLIP
        call hlib_r_set
        LEAVE_R
        di
        ld a,(G_ATTR)
        jp 0xABCC

; ---- the screen is being cleared for something else: Layer 2 goes away. The rest of the routine after the HALT.
h_hide:
        ENTER
        FAST
        ld a,(V_SHOW)
        or a
        call nz,l2_hide
        ld a,R_HIDE
        call hlib_r_set
        ld hl,V_INH
        ld (hl),0
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        HLIB_R_OUT
        nextreg 0x51,255
        ei
h_hide_halt:
        halt
        ld hl,0x5800
        jp 0xA89F

; ---- text on the screen's own bytes: the original's print, then a hole in the picture showing where it landed in the window
h_text:
        ENTER
        ld (V_TB),de
        ld (V_TC),bc
        ld a,1
        ld (V_INH),a
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0xA842
        call 0xA8FC
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,(V_SHOW)
        or a
        jr z,.no
        FAST
        ld (V_TE),de
        call hlib_debt_open
        push ix
        push iy
        call col_text
        pop iy
        pop ix
        ld a,1
        call hlib_debt_close
        jr .out
.no:    HLIB_SPEED_IN V_SPEED
.out:   ld a,R_TEXT
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret
V_TE:   defw 0

; ---- the lives on the panel: painted first, then the original's routine, which prints through h_text
h_lives:
        ENTER
        FAST
        ld a,(V_SHOW)
        or a
        jr z,.no
        call hlib_debt_open
        push ix
        push iy
        call col_lives
        pop iy
        pop ix
        ld a,1
        call hlib_debt_close
.no:    ld a,R_LIVES
        call hlib_r_set
        LEAVE_R
        ld hl,0x87B6
        jp 0x915A

; ---- the handler: at the game's clock, out of the windows, the write map off
h_isr:
        nextreg 0x51,HOOK_PAGE
        push af
        push bc
        ld bc,0x123B
        ld a,(V_PORT)
        out (c),a
        ld a,r
        ld (V_IR),a
        ld a,(V_INH)
        and 2
        jr z,.go
        push de
        push hl
        call hlib_pace_hold
        pop hl
        pop de
        ld a,(V_SPEED)
        nextreg 0x07,a
.go:    ld a,r
        ld (V_IB),a
        jp 0xA54B

h_isrx:
        nextreg 0x51,HOOK_PAGE
        push af
        push hl
        ld a,r
        ld hl,V_IB
        sub (hl)
        ld hl,V_IR
        add a,(hl)
        add a,R_ISR
        and 0x7F
        ld l,a
        ld a,(V_IR)
        and 0x80
        or l
        ld (V_IRF),a
        push bc
        push de
        ld a,(V_INH)
        and 2
        jr z,.nr
        call hlib_pace_resume
        nextreg 0x07,3
.nr:    pop de
        pop bc
        ld hl,4
        add hl,sp
        ld a,(V_INH)
        or a
        jr nz,.hook
        inc hl
        ld a,(hl)
        sub 0x20
        cp 0x20
        jr c,.hook
        pop hl
        ld a,(V_IRF)
        ld r,a
        pop af
        nextreg 0x51,255
        ei
        ret
.hook:  ld a,(V_S0)
        nextreg 0x50,a
        ld hl,4
        add hl,sp
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,draw_a-1
        or a
        sbc hl,de
        jr nc,.off              ; before the block
        ld hl,draw_b-1
        or a
        sbc hl,de
        jr c,.off               ; past it
        push bc
        ld bc,0x123B
        ld a,(V_WM)
        out (c),a
        pop bc
.off:   pop de
        pop hl
        ld a,(V_IRF)
        ld r,a
        pop af
        ei
        ret

; ---- helpers
tile_times:
        defw T_TILE00,T_TILE01,T_TILE10,T_TILE11
; rows and time of the figure, from the same reading of A58E's clipping as col_fig: each path a base and a time a row x 4
fig_paths:
        defw 494*16/228
        defb (201*64+114)/228,0
        defw 494*16/228
        defb (431*64+114)/228,0
        defw 584*16/228
        defb (213*64+114)/228,0
        defw 524*16/228
        defb (533*64+114)/228,0
; V_TGT from V_FA, V_FDE. Everything but IX, IY lost.
fig_time:
        ld hl,0
        ld (V_TGT),hl
        ld a,(V_FA)
        ld c,a
        and 0x7F
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,G_FIGS
        add hl,de
        ld b,(hl)               ; rows
        ld de,(V_FDE)
        bit 7,c
        jr z,.nm
        ld a,e
        sub 4
        ld e,a
.nm:    ld a,e                  ; the path: 0 plain, 4 shifted, 8 mirrored, 12 both
        and 4
        bit 7,c
        jr z,.pm
        or 8
.pm:    ld hl,fig_paths
        add a,l
        ld l,a
        jr nc,.p1
        inc h
.p1:    ld c,0                  ; extras, 1/16 lines
        ld a,b
        neg
        cp d
        ret z
        jr nc,.top
        ld a,d
        neg
        ld e,a
        ld a,b
        sub e
        ret z
        ld b,a
        ld d,0
        ld c,24                 ; 343 T of skipping
.top:   ld a,d
        cp 144
        ret nc
        add a,b
        sub 144
        jr c,.nb
        jr z,.nb
        ld e,a
        ld a,b
        sub e
        ld b,a
        inc c
        inc c                   ; 32 T
.nb:    ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        ld e,(hl)
        ld d,b
        mul d,e
        srl d
        rr e
        srl d
        rr e
        pop hl
        add hl,de
        ld b,0
        add hl,bc
        ld de,OV
        or a
        sbc hl,de
        jr nc,.ok
        ld hl,0
.ok:    ld (V_TGT),hl
        ret

l2_hide:
        xor a
        ld (V_SHOW),a
        ld (V_PORT),a
        ld (V_DRAWN),a
        nextreg 0x69,0
        ret

; A = the stage's attribute: palette entries 253, 254
set_attr:
        ld (hl),a
        ld e,a
        nextreg 0x43,0x10
        nextreg 0x40,INK_I
        ld a,e
        and 7
        call .one
        ld a,e
        rrca
        rrca
        rrca
        and 7
        call .one
        nextreg 0x43,0
        ret
.one:   ld d,a                  ; G R B to r g b, 9 bits; bright 7, else 6
        ld a,e
        and 0x40
        ld a,6
        jr z,.lv
        inc a
.lv:    ld c,a                  ; level
        xor a
        bit 1,d
        jr z,.g
        ld a,c
        rrca
        rrca
        rrca
.g:     ld b,a
        xor a
        bit 2,d
        jr z,.b
        ld a,c
        add a,a
        add a,a
.b:     or b
        ld b,a
        bit 0,d
        ld a,0
        jr z,.w
        ld a,c
.w:     ld c,a
        srl a
        or b
        nextreg 0x44,a
        ld a,c
        and 1
        nextreg 0x44,a
        ret

; A = screen row -> V_WM = the port's value with the write map on the back buffer's third; AF, C lost.
wm_row: and 0xC0
        or 0x09
wm_put: ld c,a
        ld a,(V_PORT)
        or c
        ld (V_WM),a
        ret

; ---- the write map is on only inside draw_a .. draw_b, and only memory below 0x4000 changes there through it. The handler's exit
; puts it back on only if it interrupted this block. d_off's OUT is the last instruction of the block.
        MACRO MAP_ON
        push bc
        ld bc,0x123B
        ld a,(V_WM)
        out (c),a
        pop bc
        ENDM
draw_a:
; B rows of 32 from HL to DE; IXL = screen x
d_full: MAP_ON
.r:     push bc
        DUP 32
        ldi
        EDUP
        pop bc
        inc d
        ld e,ixl
        djnz .r
        jp d_off
; B rows of IYL from HL, IYH on to the next row
d_part: MAP_ON
.r:     push bc
        ld b,0
        ld a,iyl
        ld c,a
        ldir
        ld a,iyh
        add a,l
        ld l,a
        jr nc,.c
        inc h
.c:     pop bc
        inc d
        ld e,ixl
        djnz .r
        jp d_off
; figures: B rows of IYH, 255 leaves the picture alone
d_fig:  MAP_ON
.r:     push bc
        ld b,0
        ld a,iyh
        ld c,a
        ld a,255
        ldirx
        ld a,24
        sub iyh
        add hl,a
        pop bc
        inc d
        ld e,ixl
        djnz .r
        jp d_off
d_mir:  MAP_ON
.r:     push bc
        ld b,0
        ld a,iyh
        ld c,a
        ld a,255
        lddrx
        ld a,24
        add a,iyh
        add hl,a
        pop bc
        inc d
        ld e,ixl
        djnz .r
d_off:  ld bc,0x123B
        ld a,(V_PORT)
        out (c),a
draw_b: ret

; ---- the tiles in colour. Window x = 32 t - (camX and 0x1C); y = 16 r - (camY and 15).
col_tiles:
        ld hl,(G_CAMY)
        ld de,(G_CAMX)
        ld a,l
        and 15
        ld (P_OFF),a
        ld a,l
        and 0xF0
        ld l,a
        add hl,hl
        add hl,hl
        ld a,e
        and 0x1C
        ld (P_XS),a
        ld a,d
        and 7
        ld d,a
        ld b,5
.sh:    srl d
        rr e
        djnz .sh
        add hl,de
        ld de,G_MAP
        add hl,de
        ld (P_MAP),hl
        ld a,16
        ld (P_Y),a
        ld a,144
        ld (P_LEFT),a
.row:   call hlib_debt_tick         ; the whole picture can outlast a frame, and the line count would wrap unseen
        ; rows of this band: to the tile's end, the window's end, and the end of the Layer 2 third
        ld a,(P_OFF)
        neg
        add a,16
        ld b,a
        ld a,(P_LEFT)
        cp b
        jr nc,.r1
        ld b,a
.r1:    ld a,(P_Y)
        and 63
        neg
        add a,64
        cp b
        jr nc,.r2
        ld b,a
.r2:    ld a,b
        ld (P_N),a
        ld hl,(P_MAP)
        ld (P_CELL),hl
        ld a,(P_XS)
        neg
        ld (P_X),a              ; signed window x of the first tile
        ld a,7
        ld (P_T),a
.col:   ld a,(P_X)
        ld e,a
        xor a
        ld (P_CL),a
        ld a,(P_T)              ; only the first tile can start left of the window
        cp 7
        jr nz,.pos
        ld a,e
        or a
        jr z,.pos
        ld a,e
        neg
        ld (P_CL),a
        ld e,0
.pos:   ld a,e
        cp 192
        jp nc,.ne
        ld a,(P_CL)
        neg
        add a,32
        ld d,a                  ; width
        add a,e
        cp 193
        jr c,.fit
        ld a,192
        sub e
        ld d,a
.fit:   ld a,d
        ld (P_W),a
        ld a,e
        add a,32
        ld e,a                  ; screen x
        ; the tile: its colours' page, then the first byte
        ld hl,(P_CELL)
        ld c,(hl)
        ld b,high G_TIDX
        ld a,(bc)
        ld c,a                  ; tile number
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,TILE_PAGE
        ld (V_S0),a
        nextreg 0x50,a
        ld a,c
        and 15
        add a,a
        ld h,a
        ld a,(P_OFF)
        rlca
        rlca
        rlca
        rlca
        rlca
        ld l,a
        and 0xE0
        ld l,a
        ld a,(P_OFF)
        rrca
        rrca
        rrca
        and 1
        add a,h
        ld h,a
        ld a,(P_CL)
        add a,l
        ld l,a
        ld ixl,e
        ld a,(P_Y)
        call wm_row
        ld a,(P_Y)
        and 63
        ld d,a
        ld a,(P_N)
        ld b,a
        ld a,(P_W)
        cp 32
        jr nz,.part
        call d_full
        jr .ne
.part:  ld iyl,a
        neg
        add a,32
        ld iyh,a                ; to the next row of the tile
        call d_part
.ne:    ; the next column of the map, in its row of 64
        ld a,(P_CELL)
        ld l,a
        cpl
        and 0x3F
        ld a,l
        jr nz,.ni
        and 0xC0
        jr .ns
.ni:    inc a
.ns:    ld (P_CELL),a
        ld a,(P_X)
        add a,32
        ld (P_X),a
        ld hl,P_T
        dec (hl)
        jp nz,.col
        ; next band
        ld a,(P_OFF)
        ld hl,P_N
        add a,(hl)
        cp 16
        jr c,.same
        ld hl,(P_MAP)
        ld de,0x40
        add hl,de
        ld (P_MAP),hl
        xor a
.same:  ld (P_OFF),a
        ld a,(P_N)
        ld b,a
        ld a,(P_Y)
        add a,b
        ld (P_Y),a
        ld a,(P_LEFT)
        sub b
        ld (P_LEFT),a
        jp nz,.row
        ld a,255
        ld (V_S0),a
        nextreg 0x50,255
        ret

; ---- a figure in colour: the rules of A58E's own clipping, read afresh
col_fig:
        ld a,(V_FA)
        ld c,a
        and 0x80
        ld (P_MIR),a
        ld a,c
        and 0x7F
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,TBL
        add hl,de
        ld a,(hl)
        ld (V_S0),a
        ld ixh,a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld b,(hl)               ; rows
        ld (P_SRC),de
        ld de,(V_FDE)           ; D = y, E = x
        ld a,(P_MIR)
        or a
        jr z,.nm
        ld a,e
        sub 4
        ld e,a
.nm:    ld a,b                  ; above the window?
        neg
        cp d
        ret z
        ld c,0                  ; rows to skip
        jr nc,.top
        ld a,d
        neg
        ld c,a
        ld a,b
        sub c
        ret z
        ld b,a
        ld d,0
.top:   ld a,d
        cp 144
        ret nc
        ld (P_Y),a
        add a,b
        sub 144
        jr c,.nb
        jr z,.nb
        ld l,a
        ld a,b
        sub l
        ld b,a
.nb:    ld a,b
        ld (P_ROWS),a
        ; the visible span of the 24 columns
        ld a,e
        and 0xFC
        ld l,a                  ; L = left column
        ld h,0                  ; first
        ld iyl,24               ; end
        bit 2,e
        jr z,.ns
        ld a,(P_MIR)
        or a
        jr z,.nr
        ld h,4
        jr .ns
.nr:    ld iyl,20
.ns:    ; clip to 32 .. 223 on the screen: L + i
        ld a,l
        add a,h
        ld e,a                  ; first screen column, may wrap
        jp c,.none
        cp 224
        jp nc,.none
        cp 32
        jr nc,.lf
        ld a,32
        sub l
        ld h,a                  ; first i
        cp 24
        jp nc,.none
.lf:    ld a,iyl
        add a,l
        jr c,.rc
        cp 225
        jr c,.rd
.rc:    ld a,224
        sub l
        ld iyl,a
.rd:    ld a,iyl
        sub h
        jp c,.none
        jp z,.none
        ld iyh,a                ; width
        ld a,l
        add a,h
        ld ixl,a                ; screen x
        ; source: rows skipped x 24, then the column
        ld a,c
        ld e,a
        ld d,24
        mul d,e
        ld a,(P_MIR)
        or a
        ld a,h
        jr z,.so
        ld a,23
        sub h
.so:    add de,a
        ld hl,(P_SRC)
        add hl,de
        ld (P_SRC),hl
        ld a,ixh
        nextreg 0x50,a
        ld a,(P_Y)
        add a,16
        ld (P_Y),a
.band:  ld a,(P_Y)              ; rows to the end of this Layer 2 third
        and 63
        neg
        add a,64
        ld b,a
        ld a,(P_ROWS)
        cp b
        jr nc,.b1
        ld b,a
.b1:    ld a,b
        ld (P_N),a
        ld a,(P_Y)
        call wm_row
        ld a,(P_Y)
        and 63
        ld d,a
        ld e,ixl
        ld hl,(P_SRC)
        ld a,(P_MIR)
        or a
        jr nz,.mi
        call d_fig
        jr .bn
.mi:    call d_mir
.bn:    ld (P_SRC),hl
        ld a,(P_N)
        ld b,a
        ld a,(P_Y)
        add a,b
        ld (P_Y),a
        ld a,(P_ROWS)
        sub b
        ld (P_ROWS),a
        jr nz,.band
.none:  ld a,255
        ld (V_S0),a
        nextreg 0x50,255
        ret

; ---- the stars: the same test as B030 on the back buffer; each that lands turns the Layer 2 pixel to the set's inverse
col_stars:
        ld ix,G_STARS
        ld a,0x3C
        ld (P_SN),a
        ld hl,STAR_LIST
        ld (P_SA),hl
.st:    ld c,(ix+0)
        ld a,(ix+1)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,c
        rrca
        rrca
        rrca
        and 31
        add a,l
        ld l,a
        ld a,high G_BUF
        adc a,h
        ld h,a
        ld a,c
        and 7
        add a,a
        add a,low G_SMASK
        ld e,a
        ld a,high G_SMASK
        adc a,0
        ld d,a
        ld a,(de)
        ld b,a                  ; test bits
        inc de
        ld a,(de)
        ld e,a                  ; the bit
        ld d,b
        ld a,(hl)
        ld bc,0x20
        add hl,bc
        and (hl)
        add hl,bc
        and (hl)
        or a
        sbc hl,bc               ; the middle row
        cpl
        and d
        jr nz,.nx
        ld a,(hl)
        xor e
        ld (hl),a
        push hl
        ld hl,(P_SA)
        pop bc
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (P_SA),hl
        ld a,(ix+1)
        inc a                   ; window row
        cp 144
        jr nc,.nx
        add a,16
        ld d,a
        ld a,(ix+0)
        and 0xF8                ; the byte's first pixel on the buffer
        cp 32
        jr c,.nx
        cp 224
        jr nc,.nx
        ld b,a
        ld c,8
.bit:   rlc e
        jr nc,.nb
        push bc
        push de
        ld a,d                  ; slot 0: the back buffer's page of this row
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        nextreg 0x50,a
        ld a,d
        and 31
        ld h,a
        ld l,b
        ld a,(hl)
        cp INK_I
        ld c,0
        jr z,.pt
        cpl
        ld c,a
        cp INK_I
        jr c,.pt
        ld c,PAPER_I
.pt:    ld (hl),c
        pop de
        pop bc
.nb:    inc b
        dec c
        jr nz,.bit
.nx:    inc ix
        inc ix
        ld hl,P_SN
        dec (hl)
        jp nz,.st
        nextreg 0x50,255
        ; the game's buffer back as it was; the original's loop will do this again
        ld hl,(P_SA)
        ld de,STAR_LIST
.un:    or a
        sbc hl,de
        ret z
        add hl,de
        ex de,hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(bc)
        xor (hl)
        ld (bc),a
        inc hl
        ex de,hl
        jr .un

; ---- text in the set's colours: the font's plain pixels are transparent, so the attributes the game just wrote show through them.
; In the window only the shown picture, the next flip takes it away; on the panel both buffers, as the screen keeps it.
col_text:
        ld hl,(V_TE)
        ld de,(V_TB)
        or a
        sbc hl,de
        dec hl
        ld a,l
        ld (P_SN),a             ; characters
        inc de
        ld (P_CELL),de          ; the string
        ld hl,(V_TC)            ; H = y, L = x
        ld (P_SRC),hl
        ld a,(V_GP)
        ld (V_S0),a
        nextreg 0x50,a
.ch:    ld a,(P_SN)
        or a
        jp z,.end
        ld hl,(P_CELL)
        ld a,(hl)
        inc hl
        ld (P_CELL),hl
        and 0x7F
        sub 0x20
        cp 0x40
        jr nc,.nc
        ld l,a                  ; x 64
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld (P_STEP),hl
        ld hl,(P_SRC)
        ld a,h
        cp 16
        jr c,.band
        cp 160
        jr nc,.band
        ld a,l                  ; a row of the window: only the window's own cells
        cp 32
        jr c,.nc
        cp 224
        jr nc,.nc
        ld a,0x01
        call .cell
        jr .nc
.band:  ld a,0x09
        call .cell
        ld a,0x01
        call .cell
.nc:    ld hl,P_SRC
        ld a,(hl)
        add a,8
        ld (hl),a
        ld hl,P_SN
        dec (hl)
        jr .ch
.end:   ld a,255
        ld (V_S0),a
        nextreg 0x50,255
        ret
; A = the map's low bits
.cell:  ld b,a
        ld a,(P_SRC+1)
        and 0xC0
        or b
        call wm_put
        ld a,(P_SRC+1)
        and 63
        ld d,a
        ld a,(P_SRC)
        ld e,a
        ld ixl,a
        ld hl,(P_STEP)
        ld b,8
        ld iyl,8
        ld iyh,0
        jp d_part

; ---- the four places for lives, in both buffers
col_lives:
        ld a,(V_GP)
        ld (V_S0),a
        nextreg 0x50,a
        ld a,(0x8E64)
        cp 5
        jr c,.n
        ld a,4
.n:     ld (P_T),a
        ld a,0x68
        ld (P_X),a
.pl:    ld a,(P_T)
        or a
        ld hl,LIVES_ON
        jr nz,.on
        ld hl,LIVES_OFF
.on:    ld (P_STEP),hl
        ld a,0x89
        call .box
        ld a,0x81
        call .box
        ld a,(P_T)
        or a
        jr z,.z
        dec a
        ld (P_T),a
.z:     ld a,(P_X)
        add a,0x20
        ld (P_X),a
        cp 0xE8
        jr nz,.pl
        ld a,255
        ld (V_S0),a
        nextreg 0x50,255
        ret
.box:   call wm_put
        ld a,(P_X)
        ld e,a
        ld ixl,a
        ld d,0xA8-128
        ld hl,(P_STEP)
        ld b,24
        ld iyl,24
        ld iyh,0
        jp d_part
rom_end:
        ASSERT $ < STAR_LIST
        SAVEBIN "mm2e_rom.bin",rom_start,$-rom_start

        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x70,0
        nextreg 0x12,L2_A
        nextreg 0x13,L2_B
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal256
        ld b,0
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        nextreg 0x43,0
        ret
l2_pal256:
        defs 512,0
setup_end:
        SAVEBIN "mm2e_setup.bin",setup,setup_end-setup
