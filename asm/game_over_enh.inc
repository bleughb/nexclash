; Game Over Enhanced: the Spec256 colours, chunky, on Layer 2. Included by game_over_hooks.asm.
; Streams: one byte a pixel, 0 skip, 254 opaque black, 255 the plot's ink, else a palette index.
; The clean picture (the game's clean buffer's twin) is C, pages C_PAGE.., rows 8-119 in place.

; e_part: which world: the copy site's own target says.
e_part: ld hl,(0x9335)
        ld de,h_copy2
        or a
        sbc hl,de
        ld a,1
        ld hl,TAB1
        ld de,(V_BDP1)
        jr nz,.s
        inc a
        ld hl,TAB2
        ld de,(V_BDP2)
        ld b,a
        ld a,(0xBE70)           ; the sets' own rule: world 2's rooms from the sixth on have no stars
        cp 5
        ld a,b
        jr c,.s
        ld e,0
.s:     ld (V_PART),a
        ld (V_TAB),hl
        ld a,e
        ld (V_BDP),a
        ret

; e_find: HL = record -> carry, T_PAGE, T_OFF, T_NB; no carry: not in the table.
e_find: ex de,hl
        ld hl,(V_TAB)
.n:     ld a,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld c,a
        or b
        ret z                   ; end of table, no carry (OR clears it)
        ld a,c
        cp e
        jr nz,.no
        ld a,b
        cp d
        jr z,.yes
.no:    inc hl
        inc hl
        inc hl
        inc hl
        jr .n
.yes:   ld a,(hl)
        ld (T_PAGE),a
        inc hl
        ld a,(hl)
        ld (T_OFF),a
        inc hl
        ld a,(hl)
        ld (T_OFF+1),a
        inc hl
        ld a,(hl)
        ld (T_NB),a
        scf
        ret

; e_plot: B = the paint flag byte. The original's plot state is read, never changed.
e_plot: ld a,(iy+1)
        or a
        ret z
        push bc
        ld a,(V_SCENE)
        or a
        call z,l2_ready
        call e_part
        pop bc
        ld a,b
        cp 0xC9
        jr z,.white
        ld a,(ATTR_P)
        jr .ink
.white: ld a,7
.ink:   ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld l,a
        ld h,ZXTAB>>8
        ld a,(hl)
        ld (V_INK),a
        ld a,(0xB734)
        neg
        add a,(iy+0)            ; rows clipped off the top
        ld (T_SKIP),a
        ld b,a
        ld c,(iy-5)
        ld hl,(0xB736)
        or a
        jr z,.pd
.pl:    ld a,l
        sub c
        ld l,a
        jr nc,.pn
        dec h
.pn:    djnz .pl
.pd:    dec hl
        dec hl
        call e_find
        ret nc                  ; every record is in the sets; nothing to draw if not
        ld a,(iy+0)
        add a,8
        ld (P_Y),a
        ld a,(iy+1)
        ld (P_ROWS),a
        ld a,(iy+2)
        inc a
        ld (P_X),a
        ld a,(iy+3)
        ld (P_COLS),a
        ld a,(V_SCENE)
        or a
        call z,rect_add
        ; source pixel and pad
        ld a,(iy+4)
        add a,a
        add a,a
        add a,a
        ld c,a                  ; k*8
        ld b,0                  ; pad
        ld a,(0xB735)
        and 1
        jr z,.ns
        ld a,c
        sub 4
        ld c,a
        jr nc,.ns
        ld c,0
        ld b,4
.ns:    ld a,(P_COLS)
        add a,a
        add a,a
        add a,a
        sub b
        ld d,a                  ; count
        ld a,(T_NB)
        add a,a
        add a,a
        add a,a
        ld (T_STR),a
        sub c                   ; what the graphic has from there
        cp d
        jr nc,.cok
        ld d,a
.cok:   ld a,d
        ld (T_CNT),a
        ld a,(P_X)
        add a,a
        add a,a
        add a,a
        add a,b
        ld (T_DX),a
        ; a scene's opaque pixels with no colour show the backdrop
        xor a
        ld (T_HOLE),a
        ld a,(V_SCENE)
        or a
        jr z,.nh
        ld a,(V_BDT)
        or a
        jr z,.nh
        ld a,(V_BDP)
        ld (T_HOLE),a
.nh:    ; source = page base + off + skip*stride + c
        ld hl,(T_OFF)
        ld d,0
        ld e,c
        add hl,de
        ld a,(T_STR)
        ld e,a
        ld a,(T_SKIP)
        or a
        jr z,.so
        ld b,a
.sm:    add hl,de
        djnz .sm
.so:    ld de,0x6000
        add hl,de
        ld (T_SRC),hl
        ld a,(T_PAGE)
        nextreg 0x53,a
.row:   ld a,(T_HOLE)
        or a
        call nz,e_holes
        ld a,(P_Y)
        call e_row
        ld d,h
        ld a,(T_DX)
        ld e,a
        ld hl,(T_SRC)
        ld a,(T_CNT)
        ld b,a
.px:    ld a,(hl)
        inc hl
        or a
        jr z,.sk
        cp 254
        jr nc,.sp
        ld (de),a
.sk:    inc e
        djnz .px
        ld hl,(T_SRC)
        ld a,(T_STR)
        ld c,a
        ld b,0
        add hl,bc
        ld (T_SRC),hl
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jr nz,.row
.out:   nextreg 0x53,11
        nextreg 0x50,255
        ret
.sp:    jr nz,.ik
        ld a,(T_HOLE)
        or a
        jr z,.blk
        push hl
        ld h,RB>>8
        ld l,e
        ld a,(hl)
        pop hl
        ld (de),a
        jr .sk
.blk:   xor a
        ld (de),a
        jr .sk
.ik:    ld a,(V_INK)
        ld (de),a
        jr .sk

; e_row: A = y: slot 0 on the row's page, H = its high byte; a scene's plots go to C.
e_row:  ld c,a
        ld a,(V_SCENE)
        or a
        ld a,c
        jp z,l2_row
        and 31
        ld h,a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ret

; e_holes: this row of the backdrop into RB, by x.
e_holes:
        ld b,a
        ld a,(P_Y)
        ld c,a
        rlca
        rlca
        rlca
        and 7
        add a,b
        nextreg 0x53,a
        ld a,c
        and 31
        add a,0x60
        ld h,a
        ld a,(T_DX)
        ld l,a
        ld e,a
        ld d,RB>>8
        ld a,(T_CNT)
        ld c,a
        ld b,0
        ldir
        ld a,(T_PAGE)
        nextreg 0x53,a
        ret

; e_ready: the back buffer back to C where figures were, once a pass.
e_ready:
        ld a,(V_FRESH)
        or a
        ret z
        xor a
        ld (V_FRESH),a
        ld a,(V_BACK)
        cp L2_BANK_A
        ld c,1
        jr z,.ma
        ld c,2
.ma:    ld a,(V_FULLN)
        and c
        jr z,.nz
        ld a,c
        cpl
        ld b,a
        ld a,(V_FULLN)
        and b
        ld (V_FULLN),a
        ld a,8
        ld (T_Y),a
        ld a,112
        ld (T_H),a
        ld a,8
        ld (T_XP),a
        ld a,240
        ld (T_WP),a
        call e_crect
        ld hl,(V_RECT)
        ld l,0
        ld (V_RECT),hl
        jr .out
.nz:    ld hl,(V_RECT)
        ld a,l
        or a
        jr z,.out
.next:  dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld (T_WP),a
        dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld (T_XP),a
        dec l
        ld a,(hl)
        ld (T_H),a
        dec l
        ld a,(hl)
        ld (T_Y),a
        push hl
        call e_crect
        pop hl
        ld a,l
        or a
        jr nz,.next
        ld (V_RECT),hl
.out:   nextreg 0x53,11
        nextreg 0x50,255
        ret

; e_crect: T_Y, T_H, T_XP, T_WP: C to the back buffer.
e_crect:
.row:   ld a,(T_H)
        and 31
        call z,hlib_debt_tick   ; a whole picture takes over a frame
        ld a,(T_Y)
        call l2_row
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x53,a
        ld a,(T_XP)
        ld l,a
        ld d,h
        ld e,l
        ld a,h
        add a,0x60
        ld h,a
        ld a,(T_WP)
        ld c,a
        ld b,0
        ldir
        ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr nz,.row
        ret

; e_scene: the game clears its clean and work pictures for a new scene: C = the backdrop or black.
e_scene:
        ld a,1
        ld (V_SCENE),a
        xor a
        ld (V_PLAY),a
        call e_part
        ld a,8
        ld (T_Y),a
        ld a,112
        ld (T_H),a
.row:   ld a,(T_Y)
        ld c,a
        rlca
        rlca
        rlca
        and 7
        ld e,a
        add a,C_PAGE
        nextreg 0x50,a
        ld a,c
        and 31
        ld d,a
        ld a,(V_BDT)
        or a
        jr z,.black
        ld a,(V_BDP)
        or a
        jr z,.black
        add a,e
        nextreg 0x53,a
        ld a,d
        add a,0x60
        ld h,a
        ld l,8
        ld e,8
        ld bc,240
        ldir
        jr .nx
.black: ld l,8
        ld h,d
        ld e,9
        ld (hl),0
        ld bc,239
        ldir
.nx:    ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr z,.end
        ld a,(hl)
        and 31
        call z,hlib_debt_tick
        jr .row
.end:   nextreg 0x53,11
        nextreg 0x50,255
        ret

; e_clear: the whole screen cleared: both buffers transparent.
e_clear:
        xor a
        ld (V_SCENE),a
        ld (V_PLAY),a
        ld (V_FULLN),a
        ld b,12
        ld c,L2_BANK_A*2
.pg:    ld a,c
        nextreg 0x50,a
        ld hl,0
        ld de,1
        ld (hl),0xFF
        push bc
        ld bc,0x1FFF
        ldir
        call hlib_debt_tick
        pop bc
        inc c
        djnz .pg
        nextreg 0x50,255
        ld hl,RECTS_A
        ld (V_LIST_A),hl
        ld hl,RECTS_B
        ld (V_LIST_B),hl
        ld a,(V_BACK)
        cp L2_BANK_A
        ld hl,RECTS_A
        jr z,.a
        ld hl,RECTS_B
.a:     ld (V_RECT),hl
        ld a,1
        ld (V_FRESH),a
        ret

; e_char: A at 0x3FFF = the character about to be printed at (B79D, B79E), unless the cell already holds it.
e_char: ld a,(0x3FFF)
        cp 128
        ret nc
        ld (T_CH),a
        ld hl,(0xB907)
        push hl
        ld de,FONT1
        or a
        sbc hl,de
        ld b,V_FONTP1
        jr z,.f
        pop hl
        push hl
        ld de,FONT2
        or a
        sbc hl,de
        ld b,V_FONTP2
        jr z,.f
        pop hl
        ret
.f:     ld a,b
        ld (T_PAGE),a
        pop de                  ; the font
        ld a,(T_CH)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de               ; the glyph
        ; the ULA cell
        ld a,(0xB79D)
        ld b,a
        cp 24
        ret nc
        and 0x18
        or 0x40
        ld d,a
        ld a,b
        and 7
        rrca
        rrca
        rrca
        ld c,a
        ld a,(0xB79E)
        cp 32
        ret nc
        or c
        ld e,a
        ld b,8
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.diff
        inc hl
        inc d
        djnz .cmp
        ret                     ; already there
.diff:  ld a,(0xB79D)           ; the play area in play belongs to the picture
        ld b,a
        ld a,(V_PLAY)
        or a
        jr z,.draw
        ld a,b
        or a
        jr z,.draw
        cp 15
        jr nc,.draw
        ld a,(0xB79E)
        or a
        jr z,.draw
        cp 31
        ret c
.draw:  ld a,(T_PAGE)
        nextreg 0x53,a
        ld a,(T_CH)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x6000
        add hl,de
        ld (T_SRC),hl
        ld a,(0xB79D)
        add a,a
        add a,a
        add a,a
        ld (T_Y),a
        ld a,(0xB79E)
        add a,a
        add a,a
        add a,a
        ld (T_XP),a
        ld a,8
        ld (T_H),a
.row:   ld hl,(T_SRC)
        ld de,R_BUF
        ld b,8
.conv:  ld a,(hl)
        inc hl
        cp 254                  ; the attribute's own ink stays on the ULA
        jr c,.put
        ld a,255
.put:   ld (de),a
        inc de
        djnz .conv
        ld (T_SRC),hl
        ld c,L2_BANK_A*2
        call e_put8
        ld c,L2_BANK_B*2
        call e_put8
        ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr nz,.row
        nextreg 0x53,11
        nextreg 0x50,255
        ret

; e_put8: C = the buffer's first page: R_BUF's 8 pixels at T_Y, T_XP.
e_put8: ld a,(T_Y)
        ld b,a
        rlca
        rlca
        rlca
        and 7
        add a,c
        nextreg 0x50,a
        ld a,b
        and 31
        ld d,a
        ld a,(T_XP)
        ld e,a
        ld hl,R_BUF
        ld bc,8
        ldir
        ret

; e_zero: the game zeroes the screen byte at the DE it came with: those 8 pixels go transparent.
e_zero: ld hl,(0x3FFA)
        ld a,h
        cp 0x58
        ret nc
        ; y = bits: 010 yy yyy / yyy xxxxx
        and 7
        ld b,a
        ld a,h
        and 0x18
        rlca
        rlca
        rlca
        or b
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
        ld (T_Y),a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld (T_XP),a
        ld hl,R_BUF
        ld b,8
.f:     ld (hl),255
        inc hl
        djnz .f
        ld c,L2_BANK_A*2
        call e_put8
        ld c,L2_BANK_B*2
        call e_put8
        nextreg 0x50,255
        ret
