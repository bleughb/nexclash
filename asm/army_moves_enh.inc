; Army Moves Enhanced: the Spec256 colours on Layer 2. Every pixel the game draws gets its colour from a
; per-graphic chunky table (1 byte a pixel: 0 skip, 254 opaque black, 255 the plot's ink, else a palette index).
; C = the composed clean picture (scene over backdrop); S = part 1's scrolling rows, raw, as a ring.
; The game's RAM is read only. Slot 0 maps Layer 2 / C; slot 3 (0x6000, never touched by the game's ISR) maps
; the source page; both are put back before any original code runs.

; e_part: V_PART, V_TAB, V_BDP from the code that is in.
e_part: ld hl,(0x9EC8)
        ld de,h_copy1
        or a
        sbc hl,de
        ld a,1
        ld hl,TAB1
        ld de,(V_BDP1)
        jr z,.s
        inc a
        ld hl,TAB2
        ld de,(V_BDP2)
        ld (V_PART),a
        ld (V_TAB),hl
        ld a,e
        ld (V_BDP),a
        ret
.s:     ld (V_PART),a
        ld (V_TAB),hl
        ld a,e
        ld (V_BDP),a
        ret

; e_find: HL = record -> carry, T_PAGE, T_OFF, T_NB; no carry: not in the table.
e_find: ld de,(V_CACHE)          ; the same record as last time: scenes repeat their tiles
        ld a,h
        cp d
        jr nz,.look
        ld a,l
        cp e
        jr nz,.look
        ld a,(V_CPART)
        ld b,a
        ld a,(V_PART)
        cp b
        jr nz,.look
        ld a,(V_CPAGE)
        or a
        ret z                   ; a miss, remembered (OR clears carry)
        ld (T_PAGE),a
        ld de,(V_COFF)
        ld (T_OFF),de
        ld a,(V_CNB)
        ld (T_NB),a
        scf
        ret
.look:  ld (V_CACHE),hl
        ld a,(V_PART)
        ld (V_CPART),a
        xor a
        ld (V_CPAGE),a          ; not found so far: the cache says miss below
        ex de,hl
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
        ld (V_CNB),a
        ld a,(T_PAGE)
        ld (V_CPAGE),a
        ld hl,(T_OFF)
        ld (V_COFF),hl
        scf
        ret

; e_plot: B = the paint flag byte. The original's plot state is read, never changed.
e_plot: ld a,(iy+1)
        or a
        ret z
        push bc
        call l2_ready
        call e_part
        pop bc
        ld a,b
        cp 0xC9
        jr nz,.pa
        ld a,(CLEAN_SKY)
        jr .ink
.pa:    ld a,(ATTR_P)
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
        jr c,.have
        xor a                   ; not in the sets: the plain figure, in its ink, black mask
        ld (V_OPAQUE),a
        jp l2_plot.colour_done
.have:  ld a,(iy+0)
        add a,16
        ld (P_Y),a
        ld a,(iy+1)
        ld (P_ROWS),a
        ld a,(iy+2)
        inc a
        ld (P_X),a
        ld a,(iy+3)
        ld (P_COLS),a
        call rect_add
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
        and 0x80
        ld (T_HOLE),a
        jr z,.nh
        ld a,(V_BDT)
        or a
        jr z,.noh
        ld a,(V_BDP)
        or a
        jr nz,.nh
.noh:   xor a
        ld (T_HOLE),a
.nh:    ld a,(T_NB)
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
        ; source = page base + off + skip*stride + c
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
        call l2_row
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
        nextreg 0x53,11
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

; e_holes: a scenery plot's opaque pixels with no colour show the backdrop: this row of it into RB, by x.
e_holes:
        ld a,(V_BDP)
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
        ld a,(V_ZDIRTY)
        or a
        call nz,e_zone
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
        jr z,.nf
        ld a,c
        cpl
        ld b,a
        ld a,(V_FULLN)
        and b
        ld (V_FULLN),a
        ld a,(V_ZN)
        and b
        ld (V_ZN),a
        ld a,16
        ld (T_Y),a
        ld a,104
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
.nf:    ld a,(V_ZN)
        and c
        jr z,.nz
        ld a,c
        cpl
        ld b,a
        ld a,(V_ZN)
        and b
        ld (V_ZN),a
        ld a,ZONE_Y
        ld (T_Y),a
        ld a,ZONE_H
        ld (T_H),a
        ld a,8
        ld (T_XP),a
        ld a,240
        ld (T_WP),a
        call e_crect
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

; e_crect: T_Y, T_H rows, T_XP, T_WP: C to the back buffer.
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

; e_rb: RB = the row's base: the backdrop (or black) for A = the row. B counts down; DE, HL kept out.
e_rbbd: ld c,a
        ld a,(V_BDT)
        or a
        jr z,e_rb0.z
        ld a,(V_BDP)
        or a
        jr z,e_rb0.z
        ld b,a
        ld a,c
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
        ld l,8
        ld de,RB
        ld bc,240
        ldir
        ret
e_rb0:
.z:     ld hl,RB
        ld de,RB+1
        ld bc,239
        ld (hl),0
        ldir
        ret

; e_zone: part 1's scrolling rows composed into C from the ring.
e_zone: xor a
        ld (V_ZDIRTY),a
        ld a,3
        ld (V_ZN),a
        ld a,ZONE_Y
        ld (T_Y),a
        ld a,ZONE_H
        ld (T_H),a
.row:   ld a,(T_Y)
        call e_rbbd
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,S_PAGE
        nextreg 0x53,a
        ld a,(T_Y)
        and 31
        add a,0x60
        ld h,a
        ld a,(V_S)
        add a,8
        ld l,a
        ld de,RB
        ld a,(V_S)
        ld c,a
        ld a,240
        sub c
        ld b,a
        call .ov
        ld a,(V_S)
        or a
        jr z,.done
        ld b,a
        ld l,8
        call .ov
.done:  ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld d,a
        ld e,8
        ld hl,RB
        ld bc,240
        ldir
        ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr nz,.row
        nextreg 0x53,11
        nextreg 0x50,255
        ret
.ov:    ld a,(hl)
        inc l
        or a
        jr z,.s
        ld (de),a
.s:     inc e
        djnz .ov
        ret

; e_bdall: the backdrop goes in under the scene: C = backdrop (S stays raw).
e_bdall:
        ld a,1
        ld (V_BDON),a
        ld a,3
        ld (V_FULLN),a
        ld a,16
        ld (T_Y),a
        ld a,104
        ld (T_H),a
.row:   ld a,(T_Y)
        call e_rbbd
        ld a,(T_Y)
        call e_rbput
        ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr z,.e
        ld a,(hl)
        and 31
        call z,hlib_debt_tick
        jr .row
.e:
        nextreg 0x50,255
        ret

; e_rbput: A = row: RB to C, x = 8.
e_rbput:
        ld c,a
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ld a,c
        and 31
        ld d,a
        ld e,8
        ld hl,RB
        ld bc,240
        ldir
        ret

; e_tile: the game's tile copy (B944) or clear (B93F, T_CLR = 1).
e_tile: call e_part
        xor a
        ld (T_PAGE),a
        ld (T_FL),a
        ld a,(T_CLR)
        or a
        jr nz,.nofind
        ld hl,(0xB736)
        ld de,0xA62A
        or a
        sbc hl,de
        jr nz,.raw
        ld a,(V_FLIP)
        ld (T_FL),a
        ld hl,(V_SRC)
        jr .find
.raw:   ld hl,(0xB736)
.find:  call e_find
        jr c,.nofind
        xor a
        ld (T_PAGE),a
.nofind:
        ld hl,(0xB937)
        ld de,0xAF74
        or a
        sbc hl,de
        jr nz,.nb               ; the first tile of a scene in the clean picture: its backdrop goes in first
        ld a,(V_BDON)
        or a
        call z,e_bdall
.nb:    ld a,(0xB73E)
        cp 31
        ret nc                  ; wider than the play area: left to the ULA
        ld (T_W),a
        add a,a
        add a,a
        add a,a
        ld (T_WP),a
        ld a,(0xB73C)
        ld (T_H),a
        ld hl,(0xB937)
        ld de,0xAF74
        or a
        sbc hl,de
        ld a,0
        jr nz,.scr
        inc a
.scr:   ld (T_CLEAN),a
        or a
        jr z,.ys
        ld a,(0xB734)
        add a,16
        ld (T_Y),a
        ld a,(0xB735)
        add a,a
        add a,a
        add a,a
        add a,8
        ld (T_XP),a
        jr .go
.ys:    ld a,(0xB734)
        ld (T_Y),a
        ld a,(0xB735)
        add a,a
        add a,a
        add a,a
        ld (T_XP),a
.go:    ld hl,(T_OFF)
        ld de,0x6000
        add hl,de
        ld a,(T_FL)
        or a
        jr z,.ns
        ld a,(T_WP)
        ld e,a
        ld d,0
        add hl,de
        dec hl
.ns:    ld (T_SRC),hl
.row:   call e_trow
        ; next row of the stream
        ld hl,(T_SRC)
        ld a,(T_WP)
        ld e,a
        ld d,0
        add hl,de
        ld (T_SRC),hl
        ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr nz,.row
        ld a,(T_CLEAN)
        or a
        jr z,.done
        ld a,(V_PART)
        cp 1
        jr nz,.full
        ld a,(0xB734)
        cp ZONE_Y-16
        jr c,.full
        ld a,1
        ld (V_ZDIRTY),a
        jr .done
.full:  ld a,(0xB734)
        add a,16
        ld (P_Y),a
        ld a,(0xB73C)
        ld (P_ROWS),a
        ld a,(0xB735)
        inc a
        ld (P_X),a
        ld a,(0xB73E)
        ld (P_COLS),a
        call rect_add           ; this buffer's list
        ld hl,(V_RECT)
        push hl
        ld a,(V_BACK)
        cp L2_BANK_A
        ld hl,(V_LIST_B)
        jr z,.ob
        ld hl,(V_LIST_A)
.ob:    ld (V_RECT),hl
        call rect_add           ; the other's
        ld hl,(V_RECT)
        ld a,(V_BACK)
        cp L2_BANK_A
        jr z,.ob2
        ld (V_LIST_A),hl
        jr .ob3
.ob2:   ld (V_LIST_B),hl
.ob3:   pop hl
        ld (V_RECT),hl
.done:  nextreg 0x53,11
        nextreg 0x50,255
        ret

; e_trow: one row of a tile: RB = base + stream over the tile's span, then to its place.
e_trow: ld a,(T_CLEAN)
        or a
        jr z,.hole
        ld a,(V_PART)
        cp 1
        jr nz,.bd
        ld a,(T_Y)
        cp ZONE_Y
        jr nc,.raw
.bd:    ld a,(V_BDT)
        or a
        jr z,.black
        ld a,(V_BDP)
        or a
        jr z,.black
        ld b,a
        ld a,(T_Y)
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
        ld a,(T_XP)
        ld l,a
        sub 8
        ld e,a
        ld d,RB>>8
        ld a,(T_WP)
        ld c,a
        ld b,0
        ldir
        ld a,(T_XP)
        sub 8
        jr .over
.black: ld a,(T_XP)
        sub 8
        ld l,a
        xor a
        jr .fillat
.raw:   ld l,0
        xor a
        jr .fillat
.hole:  ld l,0
        ld a,255
.fillat:
        ld h,RB>>8
        ld c,a
        ld a,(T_WP)
        ld b,a
        ld a,l
        ld (T_DX),a
.fl:    ld (hl),c
        inc l
        djnz .fl
        ld a,(T_DX)
.over:  ld e,a
        ld d,RB>>8
        ld a,(T_PAGE)
        or a
        jr z,.place
        nextreg 0x53,a
        ld hl,(T_SRC)
        ld a,(T_WP)
        ld b,a
        ld a,(T_FL)
        or a
        jr nz,.flipped
.ov:    ld a,(hl)
        inc hl
        or a
        jr z,.s
        cp 254
        jr z,.s
        jr c,.w
        ld a,(ZXTAB+7)
.w:     ld (de),a
.s:     inc e
        djnz .ov
        jr .place
.flipped:
.fv:    ld a,(hl)
        dec hl
        or a
        jr z,.fs
        cp 254
        jr z,.fs
        jr c,.fw
        ld a,(ZXTAB+7)
.fw:    ld (de),a
.fs:    inc e
        djnz .fv
.place: ld a,(T_CLEAN)
        or a
        jr z,.pscr
        ld a,(V_PART)
        cp 1
        jr nz,.pc
        ld a,(T_Y)
        cp ZONE_Y
        jr nc,.pz
.pc:    ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld d,a
        ld a,(T_XP)
        ld e,a
        sub 8
        ld l,a
        ld h,RB>>8
        ld a,(T_WP)
        ld c,a
        ld b,0
        ldir
        ret
.pz:    ; S, as a ring: x + V_S modulo 240
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,S_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld d,a
        ld a,(T_XP)
        sub 8
        ld c,a
        ld a,(V_S)
        add a,c
        jr c,.wr
        cp 240
        jr c,.nw
.wr:    sub 240
.nw:    add a,8
        ld e,a
        ld hl,RB
        ld a,(T_WP)
        ld b,a
.zb:    ld a,(hl)
        inc l
        ld (de),a
        inc e
        ld a,e
        cp 248
        jr nz,.zn
        ld e,8
.zn:    djnz .zb
        ld a,1
        ld (V_ZDIRTY),a
        ret
.pscr:  ; the screen: both buffers, and C when it is in the play rows
        ld a,(T_Y)
        cp 192
        ret nc
        ld a,L2_BANK_A*2
        call .pb
        ld a,L2_BANK_B*2
        call .pb
        ld a,(T_Y)
        cp 16
        ret c
        cp 120
        ret nc
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld d,a
        ld a,(T_XP)
        ld e,a
        ld hl,RB
        ld a,(T_WP)
        ld b,a
.pcs:   ld a,(hl)
        inc l
        cp 255
        jr z,.pcn
        ld (de),a
.pcn:   inc e
        djnz .pcs
        ld a,3
        ld (V_FULLN),a
        ret
.pb:    ld c,a
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,c
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld d,a
        ld a,(T_XP)
        ld e,a
        ld hl,RB
        ld a,(T_WP)
        ld c,a
        ld b,0
        ldir
        ret

; e_fillc: the game clears its clean bitmap: a new scene.
e_fillc:
        xor a
        ld (V_S),a
        ld (V_BDON),a
        ld (V_ZDIRTY),a
        ld (V_ZN),a
        ld a,3
        ld (V_FULLN),a
        ld a,16
        ld (T_Y),a
        ld a,104
        ld (T_H),a
.row:   ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,C_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld h,a
        ld l,8
        ld d,h
        ld e,9
        ld (hl),255
        ld bc,239
        ldir
        ld a,(T_Y)
        cp ZONE_Y
        jr c,.ns
        rlca
        rlca
        rlca
        and 7
        add a,S_PAGE
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld h,a
        ld l,8
        ld d,h
        ld e,9
        ld (hl),0
        ld bc,239
        ldir
.ns:    ld hl,T_Y
        inc (hl)
        ld hl,T_H
        dec (hl)
        jr nz,.row
        nextreg 0x50,255
        ret

; e_panelclr: the frame and panel of both buffers go transparent.
e_panelclr:
        ld a,L2_BANK_A*2
        call .buf
        ld a,L2_BANK_B*2
        call .buf
        nextreg 0x50,255
        ret
.buf:   ld (T_PAGE),a
        xor a
        ld (T_Y),a
.row:   ld a,(T_PAGE)
        ld c,a
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        add a,c
        nextreg 0x50,a
        ld a,(T_Y)
        and 31
        ld h,a
        ld d,h
        ld l,0
        ld e,1
        ld (hl),255
        ld a,(T_Y)
        cp 16
        jr c,.whole
        cp 120
        jr nc,.whole
        ld bc,7
        ldir
        ld l,248
        ld e,249
        ld (hl),255
        ld bc,7
        ldir
        jr .nx
.whole: ld bc,255
        ldir
.nx:    ld hl,T_Y
        inc (hl)
        ld a,(hl)
        cp 192
        jr nz,.row
        ret

; e_capture: the game captures the screen into its clean picture: the same on C, from what is showing.
e_capture:
        ld a,(V_BACK)
        cp L2_BANK_A
        ld a,L2_BANK_B*2
        jr z,.f
        ld a,L2_BANK_A*2
.f:     ld (T_PAGE),a
        ld a,3
        ld (V_FULLN),a
        xor a
        ld (V_ZDIRTY),a
        ld a,16
        ld (T_Y),a
.row:   ld a,(T_Y)
        and 31
        call z,hlib_debt_tick   ; the whole picture takes over a frame
        ld a,(T_Y)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        add a,C_PAGE
        nextreg 0x50,a
        ld a,(T_PAGE)
        add a,c
        nextreg 0x53,a
        ld a,(T_Y)
        and 31
        ld d,a
        add a,0x60
        ld h,a
        ld a,8
        ld e,a
        ld l,a
.cell:  ld c,0                  ; the ULA cell not looked up yet
        ld b,0x80
.px:    ld a,(V_L2ON)
        or a
        jr z,.u
        ld a,(hl)
        or a
        jr z,.u
        cp 254
        jr nc,.u
.put:   ld (de),a
        inc l
        inc e
        rrc b
        jr nc,.px
        ld a,e
        cp 248
        jr nz,.cell
        ld a,(T_Y)
        inc a
        ld (T_Y),a
        cp 120
        jr nz,.row
        nextreg 0x53,11
        nextreg 0x50,255
        ret
.u:     ld a,c
        or a
        call z,.look
        ld a,(T_NB)
        and b
        ld a,(T_SKIP)
        jr nz,.put
        ld a,(T_STR)
        jr .put
; the cell's ULA byte in T_NB, ink in T_SKIP, paper in T_STR
.look:  push hl
        push de
        ld a,e
        and 0xF8
        ld e,a
        ld a,(T_Y)
        ld d,a
        pixelad
        ld a,(hl)
        ld (T_NB),a
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or 0x58
        ld h,a
        ld c,(hl)
        ld a,c
        and 7
        bit 6,c
        jr z,.a
        or 8
.a:     ld l,a
        ld h,ZXTAB>>8
        ld a,(hl)
        ld (T_SKIP),a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        bit 6,c
        jr z,.b
        or 8
.b:     ld l,a
        ld a,(hl)
        ld (T_STR),a
        ld c,1
        pop de
        pop hl
        ret
