; Gunfright Enhanced: ordered Layer 2 renderer (v17 design, v18 hook-cost constants).
; Each original producer records one command at its entry, after the original has computed its buffer address,
; data pointer, rows, shift and mirror (BE0D/BF51 masked, C4AB scenery OR, C622 ground store, B28A duel strip).
; The original mono drawing still runs unchanged, so game RAM, registers and R stay the original's.
; At h_out (after A3F1's copy and clear) the queue is replayed into the hidden Layer 2 buffer with the
; pre-coloured pixels (v7 semantics: masked replace on cover, OR of indices, ground replace), then the
; buffers are flipped while the beam is outside the playfield rows 8..119.

L2A_BANK  EQU 16        ; Layer 2 buffer A: 16K banks 16..18 (pages 32..37)
L2B_BANK  EQU 19        ; Layer 2 buffer B: banks 19..21 (pages 38..43)
MT_PAGE   EQU 44        ; masked colours, town role: 5 pages (4 bytes per source byte from MASK_LO)
MB_PAGE   EQU 49        ; masked colours, bandit role: 5 pages
PL_PAGE   EQU 54        ; plain colours: scenery 8A3B.. (8 per byte), ground 6873.. at +0xBE60: 6 pages
DU_PAGE   EQU 60        ; duel strips (256 bytes each) + identity table at +DU_TABLE: 2 pages
DU_TABLE  EQU 0x3500
MASK_LO   EQU 0x68EC
MASK_HI   EQU 0x8A2E
SC_LO     EQU 0x8A3B
SC_HI     EQU 0xA207
GR_LO     EQU 0x6873
GR_HI     EQU 0x688D
GR_OFF    EQU 0xBE60
L2_QMAX   EQU 120
L2_TRANS  EQU 255

; Hook cost accounting (sixteenths of an original line). A hook inside the render window lengthens the
; measured window, which h_out scales by 104/16: each one takes back 104 x its own lines. A hook outside
; the window (duel logic) adds its own time 1:1, repaid from the next window's wait.
L2_WCOST  EQU 87
L2_LCOST  EQU 26

        MACRO L2_HOOK name,kind,exitname
name:
        ld (l2_sp),sp
        ld sp,0x3FF0
        push af                 ; 28 MHz first: in the duel logic the hook runs at the game's clock until here
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld (l2_speed),a
        pop bc
        pop af
        HLIB_R_IN
        ld (l2_a),a
        ld (l2_bc),bc
        ld (l2_de),de
        ld (l2_hl),hl
        push af
        push bc
        push de
        push hl
        HLIB_IFF_DI
        push af
        ld a,kind
        call l2_record
        ld a,98                 ; 113 less the 15 R of the clock switch before HLIB_R_IN
        call hlib_r_set
        pop af
        HLIB_IFF_EI
        pop hl
        pop de
        pop bc
        pop af
        ld (l2_a),a
        ld a,(l2_speed)
        nextreg 0x07,a
        ld a,(l2_a)
        ld sp,(l2_sp)
        HLIB_R_OUT
        jp exitname
        ENDM
        L2_HOOK h_l2_mask,1,exit_l2_mask
        L2_HOOK h_l2_mirror,2,exit_l2_mirror
        L2_HOOK h_l2_scenery,3,exit_l2_scenery
        L2_HOOK h_l2_ground,5,exit_l2_ground
        L2_HOOK h_l2_strip,7,exit_l2_strip

; A = kind. Appends one 8-byte command: kind (bit 7 bandit role), buffer, data (strip: id, identity), rows, shift, width.
l2_record:
        ld (l2_kind),a
        ld hl,(l2_cost)
        ld de,L2_LCOST
        ld a,(active)
        and a
        jr z,.cost
        ld de,L2_WCOST
.cost:  add hl,de
        ld (l2_cost),hl
        ld a,(l2_count)
        cp L2_QMAX
        jr c,.room
.fail:  ld a,1
        ld (l2_overflow),a
        ret
.room:  ld l,a
        ld h,0
        inc a
        ld (l2_count),a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,l2_queue
        add hl,de
        ld a,(l2_kind)
        cp 3
        jr c,.masked
        cp 7
        jp z,.strip
; scenery OR (3) / ground store (5): buffer DE, data HL, rows A', shift A250, mirror A254
        ld b,a
        ld a,(0xA254)
        and a
        jr z,.nomir
        inc b
.nomir: ld (hl),b
        inc hl
        ld de,(l2_de)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(l2_hl)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ex af,af'
        ld c,a
        ex af,af'
        ld a,c
        and a
        jp z,.fail
        ld (hl),a
        inc hl
        ld a,(0xA250)
        and 6
        ld (hl),a
        ; data range: scenery SC_LO..SC_HI-1 or ground GR_LO..GR_HI-1
        ex de,hl
        ld bc,SC_LO
        or a
        sbc hl,bc
        jr c,.lowp
        ld bc,SC_HI-SC_LO
        or a
        sbc hl,bc
        ret c
        jp .fail
.lowp:  ld hl,(l2_hl)
        ld bc,GR_LO
        or a
        sbc hl,bc
        jp c,.fail
        ld bc,GR_HI-GR_LO
        or a
        sbc hl,bc
        ret c
        jp .fail
; masked (1 normal, 2 mirror): buffer BC, data DE, rows A223, width A222 (+1 when shifted), shift A220
.masked:
        ld b,a
        ld a,(ix+0)
        cp 10
        jr z,.bandit
        cp 22
        jr nz,.town
.bandit:
        set 7,b
.town:  ld (hl),b
        inc hl
        ld de,(l2_bc)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(l2_de)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(0xA223)
        ld (hl),a
        inc hl
        ld a,(0xA220)
        and 6
        ld (hl),a
        inc hl
        ld c,a
        ld a,(0xA222)
        jr z,.unsh
        dec a
.unsh:  ld (hl),a
        ex de,hl
        ld bc,MASK_LO
        or a
        sbc hl,bc
        jp c,.fail
        ld bc,MASK_HI-MASK_LO
        or a
        sbc hl,bc
        ret c
        jp .fail
; duel strip (7): buffer HL, strip id A, identity = the original mapped bounty (B492[A262])
.strip:
        ld (hl),a
        inc hl
        ld de,(l2_hl)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(l2_a)
        cp 41
        jp nc,.fail
        ld (hl),a
        inc hl
        ld a,(0xA262)
        cp 20
        jr c,.vb
        xor a
.vb:    push hl
        ld hl,0xB492
        add hl,a
        ld a,(hl)
        pop hl
        cp 20
        jr c,.vi
        xor a
.vi:    ld (hl),a
        inc hl
        ld (hl),8
        inc hl
        ld a,(0xA220)
        and 6
        ld (hl),a
        ret

; h_in: show a pending frame if the beam is outside the playfield now.
l2_in:
        ld a,(l2_pending)
        and a
        ret z
        call l2_safe
        ret nz
        jp l2_flip

; Z if the beam is outside rows 8..119 (Layer 2 may be switched). AF, BC, HL lost.
l2_safe:
        call hlib_line
        ld a,h
        and a
        jr nz,.yes
        ld a,l
        cp 8
        jr c,.yes
        cp 120
        jr nc,.yes
        or 1
        ret
.yes:   xor a
        ret

l2_flip:
        ld a,(l2_back)
        nextreg 0x12,a
        xor L2A_BANK^L2B_BANK
        ld (l2_back),a
        ld a,(l2_flip_x0)
        neg
        nextreg 0x16,a
        nextreg 0x1C,1
        ld a,(l2_flip_x0)
        nextreg 0x18,a
        add a,175
        nextreg 0x18,a
        nextreg 0x18,8
        nextreg 0x18,119
        nextreg 0x69,0x80
        xor a
        ld (l2_pending),a
        ret

l2_hide:
        nextreg 0x69,0
        xor a
        ld (l2_pending),a
        ld (l2_count),a
        ld (l2_overflow),a
        ret

; h_out: target -= hook costs (never below zero), then render and flip.
l2_cost_apply:
        ld hl,(target)
        ld de,(l2_cost)
        or a
        sbc hl,de
        jr nc,.ok
        ld hl,0
.ok:    ld (target),hl
        ld hl,0
        ld (l2_cost),hl
        ret

l2_present:
        ld a,(l2_init)
        and a
        jr nz,.ready
        ld a,1
        call hlib_dma_init
        ld a,1
        ld (l2_init),a
.ready: ld a,(l2_overflow)
        and a
        jp nz,l2_hide
        ld a,(0xA269)
        cp 5
        jp nc,l2_hide           ; playfield must fit 256 pixels: X0 = 40 + 8*A269
        add a,a
        add a,a
        add a,a
        add a,40
        ld (l2_x0),a
        ld a,(l2_pending)
        and a
        jr z,.draw
        call l2_safe
        call z,l2_flip          ; the previous frame, now; otherwise it is never shown (no tearing)
.draw:  ; save MMU slots 2..7
        ld hl,l2_maps
        ld d,0x52
.rd:    ld bc,0x243B
        out (c),d
        inc b
        in a,(c)
        ld (hl),a
        inc hl
        inc d
        ld a,d
        cp 0x58
        jr nz,.rd
        push iy
        call l2_clear
        ld hl,l2_queue
        ld (l2_cursor),hl
        ld a,(l2_count)
        and a
        jr z,.done
        ld (l2_left),a
.cmd:   call hlib_pace_tick     ; at least once a frame: the line counter allows one unseen wrap
        ld hl,(l2_cursor)
        call l2_draw
        ld hl,(l2_cursor)
        ld de,8
        add hl,de
        ld (l2_cursor),hl
        ld hl,l2_left
        dec (hl)
        jr nz,.cmd
.done:  pop iy
        ld hl,l2_maps
        ld d,0x52
.wr:    ld bc,0x243B
        out (c),d
        inc b
        ld a,(hl)
        out (c),a
        inc hl
        inc d
        ld a,d
        cp 0x58
        jr nz,.wr
        xor a
        ld (l2_count),a
        ld a,(l2_back)
        ld (l2_drawn),a
        ld a,(l2_x0)
        ld (l2_flip_x0),a
        ld a,1
        ld (l2_pending),a
        ; flip now if safe; if not, wait for row 120 only when that ends before the pace target
        call hlib_pace_tick
        ld hl,(pace)
        ld a,h
        and a
        jp nz,l2_flip
        ld a,l
        cp 8
        jp c,l2_flip
        cp 120
        jp nc,l2_flip
        ld a,120
        sub l
        ld c,a
        ld b,0
        ld hl,(target)
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ld de,(pace+2)
        or a
        sbc hl,de
        ret c
        or a
        sbc hl,bc
        ret c
.wait:  call l2_safe
        jr nz,.wait
        jp l2_flip

; Clear rows 6..121 of the back buffer (slots 4..7 temporarily), DMA fill or CPU push fill.
l2_clear:
        ld a,(l2_back)
        add a,a
        nextreg 0x54,a
        inc a
        nextreg 0x55,a
        inc a
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld a,0xFF
        ld (l2_cur),a
        call hlib_dma_backend
        and a
        jr z,.cpu
        ld hl,l2_fill
        ld bc,(l2_fill_end-l2_fill)*256+0x6B
        otir
        ret
.cpu:   ld (l2_clear_sp),sp
        ld sp,0xF800
        ld de,0
        ld b,0
.c:     DUP 56
        push de
        EDUP
        djnz .c
        ld sp,(l2_clear_sp)
        ret

; HL = command. Draws it into the back buffer.
l2_draw:
        ld a,(hl)
        ld (l2_k),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (l2_base),de
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        ld (l2_rows),a
        inc hl
        ld a,(hl)
        ld (l2_sh),a
        inc hl
        ld a,(hl)
        ld (l2_wb),a
        ld a,(l2_k)
        and 7
        cp 3
        jr c,.mask
        cp 7
        jp z,.strip
        ; plain: W = 16, offset = (data-SC_LO)*8 or GR_OFF+(data-GR_LO)*8
        ld hl,16
        ld (l2_w),hl
        ld h,b
        ld l,c
        ld de,SC_LO
        or a
        sbc hl,de
        jr nc,.sc
        ld h,b
        ld l,c
        ld de,GR_LO
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,GR_OFF
        add hl,de
        jr .pl
.sc:    add hl,hl
        add hl,hl
        add hl,hl
.pl:    ld c,PL_PAGE
        ld a,(l2_k)
        and 7
        ld de,l2_op_or
        cp 3
        jr z,.op
        ld de,l2_op_orrev
        cp 4
        jr z,.op
        ld de,l2_op_copy
        cp 5
        jr z,.op
        ld de,l2_op_copyrev
.op:    ld (l2_opcall+1),de
        jp .geom
.mask:  ; W = 8w; offset = (data-MASK_LO)*4
        ld a,(l2_wb)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld (l2_w),hl
        ld h,b
        ld l,c
        ld de,MASK_LO
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        ld c,MT_PAGE
        ld a,(l2_k)
        bit 7,a
        jr z,.tr
        ld c,MB_PAGE
.tr:    and 7
        ld de,l2_op_mask
        cp 1
        jr z,.mop
        ld de,l2_op_maskrev
        ; mirrored: leftmost byte = buffer - (w-1) - (shift ? 1 : 0)
        push hl
        ld hl,(l2_base)
        ld a,(l2_wb)
        dec a
        ld b,a
        ld a,(l2_sh)
        and a
        jr z,.ns
        inc b
.ns:    ld a,l
        sub b
        ld l,a
        jr nc,.nb
        dec h
.nb:    ld (l2_base),hl
        pop hl
.mop:   ld (l2_opcall+1),de
        jr .geom
.strip: ; W = 32, rows 8, strip index from the identity table
        push bc
        ld a,DU_PAGE
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        pop bc
        ld a,b                  ; identity
        ld hl,0x4000+DU_TABLE
        ld de,41
        and a
        jr z,.ti
.tm:    add hl,de
        dec a
        jr nz,.tm
.ti:    ld a,c                  ; strip id
        add hl,a
        ld h,(hl)
        ld l,0                  ; strip * 256
        ld de,32
        ld (l2_w),de
        ld c,DU_PAGE
        ld de,l2_op_or
        ld (l2_opcall+1),de
.geom:  ; HL = colour offset, C = first page of the array: map 2 pages at 0x4000
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,c
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        ld (l2_src),hl
        ; R' = (base - BUF0 + 48) / 24, c = remainder; x0 = 8c + shift; y = 121 - R'
        ld hl,(l2_base)
        ld de,0xD6E6-48
        or a
        sbc hl,de
        ld b,121
        ld de,192
.d8:    or a
        sbc hl,de
        jr c,.d8u
        ld a,b
        sub 8
        ld b,a
        jr .d8
.d8u:   add hl,de
        ld a,l
.d1:    cp 24
        jr c,.d1u
        sub 24
        dec b
        jr .d1
.d1u:   add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(l2_sh)
        add a,c
        ld (l2_x),a
        ld a,b
        ld (l2_y),a
        ; n1 = min(W, 192 - x0), n2 = W - n1
        ld a,(l2_x)
        ld c,a
        ld a,192
        sub c
        ld c,a
        ld a,(l2_w)
        cp c
        jr c,.fit
        ld a,c
.fit:   ld (l2_n1),a
        ld c,a
        ld a,(l2_w)
        sub c
        ld (l2_n2),a
        ; rows
        ld a,(l2_k)
        and 7
        cp 7
        jr nz,.r
        ld a,8
        ld (l2_rows),a
.r:     ld hl,(l2_src)
        ld a,(l2_k)
        and 7
        cp 2
        jr z,.rev
        cp 4
        jr z,.rev
        cp 6
        jr z,.rev
        xor a
        ld (l2_rv),a
        jr .fastq
.rev:   ld de,(l2_w)
        add hl,de
        dec hl                  ; first row starts at its last pixel
        ld a,1
        ld (l2_rv),a
.fastq: ld a,(l2_n2)
        and a
        jr nz,.row              ; a row wraps past column 23: generic path
        push hl
        ld a,(l2_x)
        ld e,a
        ld a,(l2_y)
        call l2_dest
        pop hl
        ld a,(l2_rows)
        ld iyh,a
        ld a,(l2_w)
        ld iyl,a
        ld a,(l2_k)
        and 7
        dec a
        jp z,l2_f_mask
        dec a
        jp z,l2_f_maskrev
        dec a
        jp z,l2_f_or
        dec a
        jp z,l2_f_orrev
        dec a
        jp z,l2_f_copy
        dec a
        jp z,l2_f_copyrev
        jp l2_f_orw
.row:   ld a,(l2_x)
        ld e,a
        ld a,(l2_y)
        call l2_dest
        ld a,(l2_n1)
        ld c,a
        ld b,0
        call l2_opcall
        ld a,(l2_n2)
        and a
        jr z,.nw
        ld e,0
        ld a,(l2_y)
        dec a
        call l2_dest
        ld a,(l2_n2)
        ld c,a
        ld b,0
        call l2_opcall
.nw:    ld a,(l2_rv)
        and a
        jr z,.nx
        ld de,(l2_w)
        add hl,de
        add hl,de
.nx:    ld a,(l2_y)
        dec a
        ld (l2_y),a
        ld a,(l2_rows)
        dec a
        ld (l2_rows),a
        jr nz,.row
        ret

; A = canvas row y (0..127), E = x: DE = its address at 0xE000 (slot 7 mapped). HL kept.
l2_dest:
        ld d,a
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(l2_back)
        add a,a
        add a,b
        ld b,a
        ld a,(l2_cur)
        cp b
        jr z,.same
        ld a,b
        ld (l2_cur),a
        nextreg 0x57,a
.same:  ld a,d
        and 31
        or 0xE0
        ld d,a
        ret

; Fast row loops (no wrap): DE = first row address, HL = source, IYh = rows, IYl = W. Rows go up (D-1).
l2_cross:
        ld a,(l2_cur)
        dec a
        ld (l2_cur),a
        nextreg 0x57,a
        ld d,0xFF
        ret
        MACRO L2_UP w
        dec d
        bit 5,d
        call z,l2_cross
        ld a,e
        sub w
        ld e,a
        ENDM
l2_f_mask:
        ld b,0
        ld c,iyl
        ld a,L2_TRANS
        ldirx
        L2_UP iyl
        dec iyh
        jr nz,l2_f_mask
        ret
l2_f_maskrev:
        ld b,0
        ld c,iyl
        ld a,L2_TRANS
        lddrx
        L2_UP iyl
        ld a,iyl
        add a,a
        add hl,a
        dec iyh
        jr nz,l2_f_maskrev
        ret
l2_f_copy:
        ld a,iyh
        ld c,a
        ld b,0
        DUP 4
        sla c
        rl b
        EDUP
.l:     DUP 16
        ldi
        EDUP
        ret po
        L2_UP 16
        jp .l
l2_f_copyrev:
        ld a,iyh
        ld c,a
        ld b,0
        DUP 4
        sla c
        rl b
        EDUP
.l:     ld a,0xAA
        DUP 16
        lddx
        EDUP
        ret po
        ld a,32
        add hl,a
        L2_UP 16
        jp .l
l2_f_or:
        DUP 16
        ld a,(de)
        or (hl)
        ld (de),a
        inc hl
        inc e
        EDUP
        L2_UP 16
        dec iyh
        jp nz,l2_f_or
        ret
l2_f_orrev:
        DUP 16
        ld a,(de)
        or (hl)
        ld (de),a
        dec hl
        inc e
        EDUP
        ld a,32
        add hl,a
        L2_UP 16
        dec iyh
        jp nz,l2_f_orrev
        ret
l2_f_orw:                       ; duel strips: W = 32
        DUP 32
        ld a,(de)
        or (hl)
        ld (de),a
        inc hl
        inc e
        EDUP
        L2_UP 32
        dec iyh
        jp nz,l2_f_orw
        ret

l2_opcall:
        jp l2_op_mask
l2_op_mask:
        ld a,L2_TRANS
        ldirx
        ret
l2_op_maskrev:
        ld a,L2_TRANS
        lddrx
        ret
l2_op_copy:
        ldir
        ret
l2_op_copyrev:
        ld a,0xAA               ; never a colour: LDDRX copies every byte
        lddrx
        ret
l2_op_or:
        ld a,(de)
        or (hl)
        ld (de),a
        inc hl
        inc de
        dec c
        jr nz,l2_op_or
        ret
l2_op_orrev:
        ld a,(de)
        or (hl)
        ld (de),a
        dec hl
        inc de
        dec c
        jr nz,l2_op_orrev
        ret

l2_fill: db 0x83,0xC3,0x7D
        dw l2_zero,28672
        db 0x24,0x10,0xAD
        dw 0x8800
        db 0x82,0xCF,0x87
l2_fill_end:
l2_zero: db 0
l2_init: db 0
l2_sp: dw 0
l2_clear_sp: dw 0
l2_a: db 0
l2_bc: dw 0
l2_de: dw 0
l2_hl: dw 0
l2_speed: db 0
l2_kind: db 0
l2_cost: dw 0
l2_count: db 0
l2_overflow: db 0
l2_pending: db 0
l2_back: db L2A_BANK
l2_drawn: db 0
l2_x0: db 0
l2_flip_x0: db 72
l2_maps: ds 6,0
l2_cursor: dw 0
l2_left: db 0
l2_k: db 0
l2_base: dw 0
l2_rows: db 0
l2_sh: db 0
l2_wb: db 0
l2_w: dw 0
l2_src: dw 0
l2_x: db 0
l2_y: db 0
l2_n1: db 0
l2_n2: db 0
l2_rv: db 0
l2_cur: db 0xFF
l2_queue: ds L2_QMAX*8,0
