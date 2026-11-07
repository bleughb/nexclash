; Green Beret (Imagine 1986, 48K) - figures as hardware sprites. Facts and design: games/green_beret.md.
; The game blits the scenery (0xA9B9), then 0xA5FE erases and plots figures straight onto the screen.
; Three plotters: 0xA78F (4 bytes x 2N lines, gfx through SP, mask through BC), 0xA8BA (2 bytes x 8 lines,
; mask,gfx words), 0xAFA5 (2 bytes x 3 lines, OR, erases its old image first).
; Pixel classes (0xA78F, 0xA8BA): gfx 1 = dark, mask 0 + gfx 0 = body (the original shows the cell's
; paper: that is the clash), else clear.
; The plot code itself is NOT replaced: while it runs, slot 2 holds SCRPAGE, so its writes land in a scratch
; screen and the ULA keeps the scenery only. Every register it leaves and its timing stay the original's.
; Sites (original bytes checked by green_beret.py): see SITES_ORIG there.
; Memory: code in alt ROM image 1; state in Next page SCRPAGE at 0x5800-0x5FFF, which is mapped
; at slot 2 only inside a hook or a plot. Interrupts are off in 0xA5FE (DI at 0xA9B9).

        DEVICE ZXSPECTRUMNEXT

SCRPAGE EQU 26
OVPAGE  EQU 27
ULAPAGE EQU 10
SLOT6   EQU 0               ; the 48K machine's page at slot 6
DRAW    EQU 0xA5FE
AFTER   EQU 0xC21A          ; what A392 calls
GAME_SP EQU 41276
YVAR    EQU 42894

; ---- page variables ----
nattr   EQU 0x5800          ; next sprite slot
nprev   EQU 0x5801          ; slots used by the last frame
frame   EQU 0x5802          ; frame counter for the cache
indraw  EQU 0x5803          ; 1 between e_fs and e_fe
svsp    EQU 0x5804
vscr    EQU 0x5806
vgfx    EQU 0x5808
vmask   EQU 0x580A
vcnt    EQU 0x580C
vrows   EQU 0x580D
vkind   EQU 0x580E          ; 0 plot, 1 plot2, 2 small
vk0     EQU 0x5810          ; key: gfx lo, gfx hi, mask lo or kind mark, rows
vk1     EQU 0x5811
vk2     EQU 0x5812
vk3     EQU 0x5813
vcols   EQU 0x5814          ; tiles across
vent    EQU 0x5815
vx      EQU 0x5816
vy      EQU 0x5818
vp      EQU 0x5819
vspd    EQU 0x581A          ; the game's clock (NR 7 bits 1:0) at hook entry, written back at exit
HSTK    EQU 0x5900
KEYS    EQU 0x5900          ; 32 x 4
STAMPS  EQU 0x5980          ; 32
CLS     EQU 0x5C00          ; (from green_beret.py) index gggg mmmm -> left byte at CLS, right byte at CLS+256
BUF     EQU 0x5E00          ; 32 rows x 16

        ORG 0x386E
; ---- A38F: CALL 0xA5FE -> frame start, then the routine ----
e_fs:   push af
        nextreg 0x52,SCRPAGE
        ld a,(frame)
        inc a
        ld (frame),a
        xor a
        ld (nattr),a
        inc a
        ld (indraw),a
        nextreg 0x52,ULAPAGE
        pop af
        jp DRAW

; ---- A392: CALL 0xC21A -> frame end: commit (hide what was not plotted), then the routine ----
e_fe:   push af
        push bc
        nextreg 0x52,SCRPAGE
        call spd_in
        call hide_rest
        xor a
        ld (indraw),a
        call spd_out
        nextreg 0x52,ULAPAGE
        pop bc
        pop af
        jp AFTER

; ---- 0x64F4 / 0x64E6: the screen wipes (menu, stage screen, game over): hide everything ----
e_wip1: call hide_all
        ld hl,22528
        jp 0x64F7
e_wip2: call hide_all
        ld bc,6143
        jp 0x64E9
hide_all:
        push af
        push bc
        nextreg 0x52,SCRPAGE
        ld a,(nattr)
        ld b,a
        ld a,(nprev)
        cp b
        jr nc,.keep             ; a wipe in mid-frame: the frame's own sprites go too
        ld a,b
        ld (nprev),a
.keep:  xor a
        ld (nattr),a
        ld (indraw),a
        call hide_rest
        nextreg 0x52,ULAPAGE
        pop bc
        pop af
        ret

; ---- A7DF: LD A,(YVAR), SP = graphics, BC = mask, HL = screen, A' = line pairs ----
e_plot: nextreg 0x52,SCRPAGE
        ld (svsp),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ex af,af'
        ld (vcnt),a
        ex af,af'
        ld (vscr),hl
        ld (vmask),bc
        ld hl,(svsp)
        ld (vgfx),hl
        xor a
        ld (vkind),a
        call spd_in             ; after the entry's reads of A, BC (it uses both)
n_plot: call show
        call spd_out
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(svsp)
        ld a,(YVAR)
        jp 0xA7E2

; ---- A8E8: LD (GAME_SP),SP, HL = graphics (mask,gfx words), DE = screen ----
e_plt2: nextreg 0x52,SCRPAGE
        ld (GAME_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld (vscr),de
        ld (vgfx),hl
        ld a,1
        ld (vkind),a
        call spd_in             ; after the entry's reads of A, BC (it uses both)
n_plt2: call show
        call spd_out
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(GAME_SP)
        jp 0xA8EC

; ---- AFD8: LD (GAME_SP),SP; new screen in DE', new graphics in HL' ----
e_smal: nextreg 0x52,SCRPAGE
        ld (GAME_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        exx
        ld (vscr),de
        ld (vgfx),hl
        exx
        ld a,2
        ld (vkind),a
        call spd_in             ; after the entry's reads of A, BC (it uses both)
n_smal: call show
        call spd_out
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(GAME_SP)
        jp 0xAFDC

; ---- AE5D: LD (GAME_SP),SP; mines: HL = graphics, mask address in the LD BC at AE6F, C = x, screen line 160 ----
e_mine: nextreg 0x52,SCRPAGE
        ld (GAME_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld (vgfx),hl
        ld hl,(0xAE70)
        ld (vmask),hl
        ld a,c
        rrca
        rrca
        rrca
        and 31
        ld l,a
        ld h,0x52
        ld de,0x80
        add hl,de
        ld (vscr),hl
        ld a,3
        ld (vkind),a
        call spd_in             ; after the entry's reads of A, BC (it uses both)
n_mine: call show
        call spd_out
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(GAME_SP)
        jp 0xAE61
; ---- AE9E: LD SP,(GAME_SP), then EXX, RET ----
e_end3: ld sp,(GAME_SP)
        nextreg 0x52,ULAPAGE
        jp 0xAEA2

; ---- A82F, A86D, A919: LD SP,(GAME_SP), then RET ----
e_end:  ld sp,(GAME_SP)
n_end:  nextreg 0x52,ULAPAGE
        ret
; ---- B03A: LD SP,(GAME_SP), then POP HL, RET ----
e_end2: ld sp,(GAME_SP)
n_end2: nextreg 0x52,ULAPAGE
        jp 0xB03E

; ---- common code ----
; the game's clock: latched at entry (NR 7 bits 1:0 through the register ports; A, BC saved by the caller),
; 28 MHz inside the hook, written back at exit (card patch.restore-speed). Slot 2 holds SCRPAGE for both.
spd_in: ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (vspd),a
        nextreg 0x07,3
        ret
spd_out:
        push af
        ld a,(vspd)
        nextreg 0x07,a
        pop af
        ret

hide_rest:
        ld a,(nprev)
        ld b,a
        ld a,(nattr)
        ld c,a
        ld (nprev),a
hr_lp:    ld a,c
        cp b
        ret nc
n_hide: nextreg 0x34,a
        nextreg 0x38,0
        inc c
        jr hr_lp

; one figure: find or make its patterns, write its sprites
show:   ld a,(indraw)
        or a
        ret z                   ; 0xAFA5 from 0xBDBB, outside the draw pass
        ld hl,(vgfx)
        ld (vk0),hl
        ld a,(vkind)
        or a
        jr z,.k0a
        cp 3
        jr nz,.k1
        ld a,(vmask)
        ld (vk2),a
        ld a,6
        ld (vk3),a
        ld (vrows),a
        ld a,2
        jr .k9
.k0a:   ld a,(vmask)
        ld (vk2),a
        ld a,(vcnt)
        add a,a
        cp 33
        jr c,.k0
        ld a,32                 ; never seen; figures are at most 24 lines
.k0:    ld (vk3),a
        ld (vrows),a
        ld a,2
        jr .k9
.k1:    dec a
        jr nz,.k2
        ld a,0xFE
        ld (vk2),a
        ld a,8
        jr .k3
.k2:    ld a,0xFF
        ld (vk2),a
        ld a,3
.k3:    ld (vk3),a
        ld (vrows),a
        ld a,1
.k9:    ld (vcols),a
; the cache
        ld hl,KEYS
        ld e,0
f_lp:     ld a,(vk0)
        cp (hl)
n_k0:   jr nz,f_nx
        inc l
        ld a,(vk1)
        cp (hl)
        dec hl
n_k1:   jr nz,f_nx
        inc l
        inc l
        ld a,(vk2)
        cp (hl)
        dec hl
        dec hl
        jr nz,f_nx
        inc l
        inc l
        inc l
        ld a,(vk3)
        cp (hl)
        dec hl
        dec hl
        dec hl
n_hit:  jr z,f_hit
f_nx:    ld a,l
        add a,4
        ld l,a
        inc e
        bit 5,e
        jr z,f_lp
; a miss: the entry unused for longest, never one on show
        ld hl,STAMPS
        ld bc,0
        ld e,0
v_lp:     ld a,(frame)
        sub (hl)
        cp b
        jr c,v_nx
        ld b,a
        ld c,e
v_nx:    inc hl
        inc e
        bit 5,e
        jr z,v_lp
        ld a,b
        cp 2
        ret c                   ; no idle entry: figure dropped (never seen: at most 12 figures a frame)
        ld e,c
        ld d,4
        mul d,e
        ld hl,KEYS
        add hl,de
        ld a,(vk0)
        ld (hl),a
        inc l
        ld a,(vk1)
        ld (hl),a
        inc l
        ld a,(vk2)
        ld (hl),a
        inc l
        ld a,(vk3)
        ld (hl),a
        ld e,c
        ld a,e
        ld (vent),a
        call upload
        ld a,(vent)
        ld e,a
f_hit:   ld a,e
        ld (vent),a
        ld hl,STAMPS
        add hl,a
        ld a,(frame)
        ld (hl),a
; the sprites: 2 x 2 tiles at most, from the screen address
attrs:  ld hl,(vscr)
        ld a,h
        and 0x18
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
        ld b,a
        ld a,h
        and 7
        or b
n_y:    add a,32
        ld (vy),a
        ld a,l
        and 31
        ld e,a
        ld d,8
        mul d,e
        ex de,hl
        ld de,32
        add hl,de
        ld (vx),hl
        ld a,(vent)
        add a,a
        add a,a
        ld (vp),a
        ld a,(vrows)
        ld d,1
        cp 17
        jr c,.r1
        inc d
.r1:    ld e,0                  ; d tile rows, e row
.row:   ld a,(vcols)
        ld b,a
        ld hl,(vx)
        ld a,(vp)
        ld c,a
.col:   ld a,(nattr)
        cp 128
        ret nc
        nextreg 0x34,a
        inc a
        ld (nattr),a
        ld a,l
        nextreg 0x35,a
        ld a,(vy)
        push bc
        ld b,a
        ld a,e
        swapnib
        add a,b
        pop bc
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        rrca
        rrca
        and 0x40
        or 0x80
        nextreg 0x39,a
        inc c
        push de
        ld de,16
        add hl,de
        pop de
        djnz .col
        ld a,(vp)
        add a,2
        ld (vp),a
        inc e
        ld a,e
        cp d
        jr nz,.row
        ret

ROM_END:
        SAVEBIN "gb_rom.bin",0x386E,ROM_END-0x386E

; ---- code in the hook page, mapped with it ----
        ORG 0x59A0
; ---- patterns of entry (vent): expand into BUF, colours, then send ----
upload: ld a,(vkind)
        or a
        jp z,x_plot
        dec a
        jr z,x_plt2
        dec a
        jr nz,x_mine
; 3 lines of 2 bytes: columns 0 1, 1 0, 0 1; OR only, so no body pixels
x_smal: ld hl,(vgfx)
        ld de,BUF
        call x_s2
        ld de,BUF+16+4
        call x_s1
        ld de,BUF+16
        call x_s1
        ld de,BUF+32
        call x_s2
        jp send
x_s2:   call x_s1
x_s1:   ld b,(hl)
        ld c,0xFF
        inc hl
        jp conv
; 6 lines of 3 bytes: columns 0 1 2, then 2 1 0; column 3 empty
x_mine: ld hl,(vgfx)
        ld bc,(vmask)
        ld de,BUF
        ld a,3
.l:     push af
        call x_b
        call x_b
        call x_b
        call x_z
        ld a,8
        add de,a
        call x_b
        call x_z
        ld a,12
        call desub
        call x_b
        ld a,8
        call desub
        call x_b
        ld a,12
        add de,a
        pop af
        dec a
        jr nz,.l
        jp send
x_z:    xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ret
desub:  neg
        add a,e
        ld e,a
        ld a,d
        adc a,0xFF
        ld d,a
        ret
; 8 lines of 2 mask,gfx words: columns 0 1, then 1 0
x_plt2: ld hl,(vgfx)
        ld de,BUF
        ld a,4
.l:     push af
        call x_w
        call x_w
        ld a,12
        add de,a
        call x_w
        ld a,e
        sub 8
        ld e,a
        ld a,d
        sbc a,0
        ld d,a
        call x_w
        ld a,12
        add de,a
        pop af
        dec a
        jr nz,.l
        jp send
x_w:    ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        jp conv
; 2N lines of 4 bytes: columns 0 1 2 3, then 3 2 1 0
x_plot: ld hl,(vgfx)
        ld bc,(vmask)
        ld de,BUF
        ld a,(vrows)
        srl a
.l:     push af
        ld a,4
.a:     push af
        call x_b
        pop af
        dec a
        jr nz,.a
        ; DE = this row + 16: the next row's last column
        ld a,12
        add de,a
        ld a,4
.b:     push af
        call x_b
        ex de,hl
        push bc
        ld bc,-8
        add hl,bc
        pop bc
        ex de,hl
        pop af
        dec a
        jr nz,.b
        ; DE = the row's first column - 4: on to the next row
        ld a,4+16
        add de,a
        pop af
        dec a
        jr nz,.l
        jp send
x_b:    push bc
        ld a,(bc)
        ld c,a
        ld b,(hl)
        inc hl
        call conv
        pop bc
        inc bc
        ret

; B = gfx, C = mask -> 4 bytes at DE. Keeps HL, BC.
conv:   push hl
        ld a,b
        and 0xF0
        ld l,a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        ld a,b
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld l,a
        ld a,c
        and 0x0F
        or l
        ld l,a
        ld h,high CLS
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        pop hl
        ret

send:   call ovapply
        ld a,(vent)
        add a,a
        add a,a
        ld e,a                  ; pattern number (half patterns)
        ld a,(vrows)
        ld d,a                  ; lines left
        ld hl,BUF
.row:   push de
        push hl
        call .tile
        pop hl
        pop de
        ld a,(vcols)
        cp 2
        jr nz,.nx
        push de
        push hl
        inc e
        ld bc,8
        add hl,bc
        call .tile
        pop hl
        pop de
.nx:    ld a,d
        sub 16
        ret c
        ret z
        ld d,a
        ld bc,16*16
        add hl,bc
        inc e
        inc e
        jr .row
; pattern E, D lines to send, HL = its first line
.tile:  ld a,e
        srl a
        ld b,a
        ld a,e
        rrca
        and 0x80
        or b
        ld bc,0x303B
        out (c),a
        ld e,16
.t:     ld a,d
        or a
        jr z,.z
        dec d
        ld bc,0x085B
        otir
        ld bc,8
        add hl,bc
        dec e
        jr nz,.t
        ret
.z:     ld bc,0x085B
.zz:    out (c),a
        djnz .zz
        dec e
        jr nz,.z
        ret

; painted colours: index in OVPAGE at slot 6 (count word, then gfx lo, gfx hi, page, plane lo, plane hi)
; plane: for each line 16 colour bytes then 16 keep masks. Interrupts are off here and the graphics are read.
ovapply:
        nextreg 0x56,OVPAGE
        ld hl,0xC000
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jr z,.out
.s:     ld a,(vk0)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(vk1)
        cp (hl)
        dec hl
        jr z,.got
.n:     ld de,5
        add hl,de
        dec bc
        ld a,b
        or c
        jr nz,.s
        jr .out
.got:   inc hl
        inc hl
        ld a,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl                ; plane
        nextreg 0x56,a
        ld de,BUF
        ld a,(vrows)
        ld b,a
.line:  push bc
        ld b,16
.px:    push bc
        ld bc,16
        push hl
        add hl,bc
        ld a,(de)
        and (hl)
        pop hl
        or (hl)
        ld (de),a
        inc hl
        inc de
        pop bc
        djnz .px
        ld bc,16
        add hl,bc
        pop bc
        djnz .line
.out:   nextreg 0x56,SLOT6
        ret
PAGE_END:
        SAVEBIN "gb_page.bin",0x59A0,PAGE_END-0x59A0

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
        nextreg 0x19,16         ; x 16..239: the game's black margin columns; y whole screen
        nextreg 0x19,239
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
; 1 body (white), 2 dark (black): the default look. 3-15: paintable, the Spectrum's other colours.
.pal:   DB 0xFF,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
SETUP_END:
        SAVEBIN "gb_setup.bin",0xD000,SETUP_END-0xD000
