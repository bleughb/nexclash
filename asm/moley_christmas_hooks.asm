; Moley Christmas. Keep the original screen and back buffer. Select resident
; 4-bit patterns by frame; none of the original graphics are in this source.
        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"

; Keep the interrupted game's index and alternate registers untouched. R is
; saved on the stack: the low seven bits wrap, bit 7 belongs to the caller.
        MACRO ENTER_HOOK
        push af
        push bc
        ld a,r
        push af
        push de
        push hl
        ENDM
        MACRO LEAVE_HOOK delta
        pop hl
        pop de
        pop af
        ld b,a
        sub delta
        xor b
        and 0x7f
        xor b
        ld r,a
        pop bc
        pop af
        ENDM

        ORG 0x386e
; The plotter entry and its straight-line setup run together. Its original
; address calculator supplies BC. Compute the three shift displacements and
; source pointer at turbo to pay for the attribute writes. No gameplay
; input ports are sampled during the speed change.
figure: ld a,r
        push af
        HLIB_SPEED_IN_SP
        ld a,ixl
        sub 0x21
        rrca
        rrca
        add a,8
        nextreg 0x34,a
        ld a,(ix+2)
        ld l,a
        ld h,high frames
        ld e,(hl)
        ld d,0xf0                ; bright white, the ink in open room cells
        bit 7,(ix+3)
        jr nz,figure_pos
        set 3,d
figure_pos:
        call place
        call 0x8a11
        add a,a
        ld (0x897a),a
        ld (0x89e2),a
        ld (0x8a57),a
        ld a,(ix+2)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xc000
        add hl,de
        ex de,hl                 ; DE holds final pointer, HL saves final AF
        push af
        pop hl
        HLIB_SPEED_OUT_SP
        pop af
        bit 7,a
        jr z,.rlo
        add a,42
        or 128
        jr .setr
.rlo:   add a,42
        and 127
.setr:  ld r,a
        push hl
        pop af
        ex de,hl
        ld de,0xc000
        jp 0x8952
; D = palette and mirror, E = 4-bit pattern number, IX = x,y record.
place:  ld a,(ix+0)
        add a,32
        nextreg 0x35,a
        ld a,d
        adc a,0
        nextreg 0x37,a
        ld a,(ix+1)
        add a,32
        nextreg 0x36,a
        ld d,0x80
        jr nc,.low
        inc d
.low:   ld a,e
        srl a
        jr nc,.even
        set 6,d
.even:  or 0xc0
        nextreg 0x38,a
        ld a,d
        nextreg 0x39,a
        ret

pickup_init:
        ENTER_HOOK
        call pickup
        LEAVE_HOOK 8
        inc ix
        inc ix
        jp 0x862b
pickup_cycle:
        ld (hl),a
        ENTER_HOOK
        ld a,ixl
        sub 0xd5
        rrca
        rrca
        nextreg 0x34,a
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        ld d,a
        ld a,(ix+0)
        add a,32
        ld a,d
        adc a,0
        nextreg 0x37,a
        LEAVE_HOOK 8
        ld e,(ix+0)
        jp 0x865d
pickup: ld a,ixl
        sub 0xd5
        rrca
        rrca
        nextreg 0x34,a
        ld l,(ix+2)
        ld h,(ix+3)
        ld a,(hl)
        and 7
        rlca
        rlca
        rlca
        rlca
        ld d,a
        ld a,h
        and 3
        ld h,a
        ld bc,(0x8103)
        add hl,bc
        ld a,(hl)
        sub 236
        add a,124
        ld e,a
        jp place
collected:
        ENTER_HOOK
        ld a,ixl
        sub 0xd5
        rrca
        rrca
        nextreg 0x34,a
        nextreg 0x38,0
        LEAVE_HOOK 8
        ld (ix+2),0
        jp 0x869b

room:   ENTER_HOOK
        call hide
        LEAVE_HOOK 8
        ld (0x8107),a
        jp 0x854d
clear:  ENTER_HOOK
        call hide
        LEAVE_HOOK 8
        ld hl,0x4000
        jp 0xa2ab
gameover:
        ENTER_HOOK
        call hide
        LEAVE_HOOK 7
        jp 0x82d9
hide:   xor a
.loop:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 16
        jr nz,.loop
        ret

        ALIGN 256
frames: ds 256,0                ; engine fills frame -> pattern numbers only
rom_end:

        ORG 0xd000
setup:  HLIB_SPEED_IN_SP
        nextreg 0x53,0          ; game bank 0 at 0x6000, stub still at 0xc000
        nextreg 0x43,0x20
        ld hl,colours
        ld d,0
.pal:   ld a,d
        rlca
        rlca
        rlca
        rlca
        inc a
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a
        nextreg 0x41,0           ; index 2 = black, index 0 transparent
        inc hl
        inc d
        ld a,d
        cp 16
        jr nz,.pal
        nextreg 0x4b,0
        nextreg 0x1c,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,143
        xor a
.hide:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hide
        ld hl,sources            ; pattern, source frame; 0xff ends the list
.each:  ld a,(hl)
        inc hl
        cp 255
        jr z,.done
        rrca
        ld bc,0x303b
        out (c),a
        ld a,(hl)
        inc hl
        push hl
        cp 192
        jr nc,.tile
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x6000
        add hl,de
        push hl
        pop ix
        ld bc,0x1010             ; 16 rows, other half at IX+16
        jr .draw
.tile:  sub 192
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,0x7800+(236-1)*8
        add hl,de
        push hl
        pop ix
        ld bc,0x0800             ; eight rows, eight ink pixels
.draw:  call encode
        pop hl
        jr .each
.done:  nextreg 0x53,11
        HLIB_SPEED_OUT_SP
enable: nextreg 0x15,1
        ret
colours:
        db 0,2,0xa0,0xa2,0x14,0x16,0xb4,0xb6
        db 0,3,0xe0,0xe3,0x1c,0x1f,0xfc,0xff

; Encode the untouched source at launch. Only zero pixels enclosed by ink
; become black. Flood from outside the 16x16 image; guard ring bounds it.
        MACRO MARK_OPEN
        ld a,(hl)
        cp 2
        jr nz,.visited
        ld (hl),0
        push hl
.visited:
        ENDM
encode: push bc
        ld hl,grid
        ld de,grid+1
        ld bc,399
        ld (hl),3
        ldir
        ld hl,grid+21
        ld b,18
.init:  ld c,18
.fill:  ld (hl),2
        inc hl
        dec c
        jr nz,.fill
        inc hl
        inc hl
        djnz .init
        pop bc
        ld hl,grid+42
.row:   push hl
        ld a,(ix+0)
        call bits
        ld a,c
        or a
        jr z,.next
        ld a,(ix+16)
        call bits
.next:  pop hl
        ld de,20
        add hl,de
        inc ix
        djnz .row

        ld hl,0
        push hl                  ; flood stack sentinel
        ld hl,grid+21
        ld (hl),0
        ld de,20
.flood: inc hl
        MARK_OPEN
        dec hl
        dec hl
        MARK_OPEN
        inc hl
        add hl,de
        MARK_OPEN
        or a
        sbc hl,de
        or a
        sbc hl,de
        MARK_OPEN
        pop hl
        ld a,h
        or l
        jr nz,.flood

        ld hl,grid+42
        ld d,16
.pack:  ld b,8
.pair:  ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        inc hl
        or (hl)
        inc hl
        out (0x5b),a
        djnz .pair
        ld bc,4
        add hl,bc
        dec d
        jr nz,.pack
        ret
bits:   ld e,8
.bit:   add a,a
        jr nc,.zero
        ld (hl),1
.zero:  inc hl
        dec e
        jr nz,.bit
        ret
grid:   ds 400
sources:
        SAVEBIN "mc_rom.bin",0x386e,rom_end-0x386e
        SAVEBIN "mc_setup.bin",0xd000,sources-0xd000

; Optional painted build only. The default builds all patterns from the
; player's game at launch. This routine replaces them from spare bank 13.
        ORG 0xdb00
painted: HLIB_SPEED_IN_SP
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,paint_palette
        ld b,0
.pal:   ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pal
        xor a
        ld bc,0x303b
        out (c),a
        ld e,26
.page:  ld a,e
        nextreg 0x53,a
        ld hl,0x6000
        ld d,32
        ld bc,0x005b
.block: otir
        dec d
        jr nz,.block
        inc e
        ld a,e
        cp 28
        jr nz,.page
        nextreg 0x53,11
        HLIB_SPEED_OUT_SP
        nextreg 0x15,1
        ret
paint_palette:
        SAVEBIN "mc_paint.bin",painted,paint_palette-painted
