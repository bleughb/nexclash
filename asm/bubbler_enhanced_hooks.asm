; Bubbler: exact indexed-colour masked operations, original shapes and painter order.
        DEVICE ZXSPECTRUMNEXT
C_SRC EQU 0x3E40
C_CSRC EQU 0x3E42
C_DST EQU 0x3E44
C_ROWS EQU 0x3E46
C_WIDTH EQU 0x3E47
C_SHIFT EQU 0x3E48
C_FLIP EQU 0x3E49
C_CUT EQU 0x3E4A
C_ROT EQU 0x3E4B
C_POS EQU 0x3E4C
C_ROWPOS EQU 0x3E4E
C_ROW_SRC EQU 0x3E50
C_ROW_CSRC EQU 0x3E52
C_LEFT EQU 0x3E54
C_LINE EQU 0x3E55
C_MAP EQU 0x3E56
        ORG 0xA000
colour_draw:
        ld a,(C_ROWS)
        and a
        ret z
        ld (C_LINE),a
        ld hl,(C_DST)
        ld de,0x1A45         ; -E5BB modulo 65536
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(C_SHIFT)
        add a,8
        ld e,a
        ld d,0
        add hl,de
        ld (C_ROWPOS),hl
        ld a,(C_SHIFT)
        and a
        ld a,0xB5           ; OR IYL
        jr z,.operation
        ld a,0xAD           ; XOR IYL
.operation:
        ld (.pixel_mix+1),a
        inc a
        ld (.quick_mix0),a
        ld (.quick_mix1),a
        ld (.quick_mix2),a
        ld (.quick_mix3),a
        ld (.quick_mix4),a
        ld (.quick_mix5),a
        ld (.quick_mix6),a
        ld (.quick_mix7),a
.row:
        ld hl,(C_SRC)
        ld (C_ROW_SRC),hl
        ld hl,(C_CSRC)
        ld (C_ROW_CSRC),hl
        ld hl,(C_ROWPOS)
        ld (C_POS),hl
        ld a,(C_WIDTH)
        ld (C_LEFT),a
.byte:
        ld hl,(C_SRC)
        ld a,(hl)
        inc hl
        or (hl)
        jp z,.skip          ; no original support, and painting cannot add an edge
        ld hl,(C_POS)
        bit 7,h
        jp nz,.skip
        ld a,h
        cp 0x60
        jr c,.inside
        jp nz,.skip
        ld a,l
        cp 8
        jp nc,.skip
.inside:
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,28
        ld (C_MAP),a
        nextreg 0x56,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ex de,hl
        ld hl,(C_CSRC)
        ld a,h
        rrca
        rrca
        and 0x3F
        add a,16            ; logical source 6000..8FFF -> asset pages 40..51
        ld c,a
        ld a,(C_FLIP)
        add a,c
        nextreg 0x52,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        push hl
        ld hl,(C_SRC)
        ld b,(hl)
        pop hl
        ld a,(C_CUT)
        ld c,a
        ld a,b
        and c
        inc a
        jr nz,.masked_pixels
        ld a,e
        cp 0xF9
        jr c,.opaque
        ld a,d
        cp 0xDF
        jr z,.masked_pixels
.opaque:
        DUP 8
        ldi
        EDUP
        jp .skip
.masked_pixels:
        ld a,e
        cp 0xF9
        jr c,.quick_pixels
        ld a,d
        cp 0xDF
        jp z,.slow_pixels
.quick_pixels:
        push hl
        push bc
        ld bc,-8
        add hl,bc
        ld a,(hl)
        pop bc
        pop hl
        cp 0xA7
        jp nz,.mix_pixels
        push hl
        ld hl,(C_SRC)
        ld a,(hl)
        cpl
        inc hl
        and (hl)
        pop hl
        jp nz,.mix_pixels
        ld a,c
        inc a
        jr nz,.stipple_pixels
        ld a,254
        ld bc,8
        ldirx
        jp .skip
.stipple_pixels:
        ex de,hl
        ld a,(de)
        rlc c
        jr c,.stipple_colour0
        xor a
.stipple_colour0:
        rlc b
        jr nc,.stipple_skip0
        ld (hl),a
.stipple_skip0:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour1
        xor a
.stipple_colour1:
        rlc b
        jr nc,.stipple_skip1
        ld (hl),a
.stipple_skip1:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour2
        xor a
.stipple_colour2:
        rlc b
        jr nc,.stipple_skip2
        ld (hl),a
.stipple_skip2:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour3
        xor a
.stipple_colour3:
        rlc b
        jr nc,.stipple_skip3
        ld (hl),a
.stipple_skip3:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour4
        xor a
.stipple_colour4:
        rlc b
        jr nc,.stipple_skip4
        ld (hl),a
.stipple_skip4:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour5
        xor a
.stipple_colour5:
        rlc b
        jr nc,.stipple_skip5
        ld (hl),a
.stipple_skip5:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour6
        xor a
.stipple_colour6:
        rlc b
        jr nc,.stipple_skip6
        ld (hl),a
.stipple_skip6:
        inc hl
        inc de
        ld a,(de)
        rlc c
        jr c,.stipple_colour7
        xor a
.stipple_colour7:
        rlc b
        jr nc,.stipple_skip7
        ld (hl),a
.stipple_skip7:
        inc hl
        inc de
        jp .skip
.mix_pixels:
        ex de,hl
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour0
        xor a
.quick_colour0:
        rlc b
        jr c,.quick_store0
.quick_mix0:
        or (hl)
.quick_store0:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour1
        xor a
.quick_colour1:
        rlc b
        jr c,.quick_store1
.quick_mix1:
        or (hl)
.quick_store1:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour2
        xor a
.quick_colour2:
        rlc b
        jr c,.quick_store2
.quick_mix2:
        or (hl)
.quick_store2:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour3
        xor a
.quick_colour3:
        rlc b
        jr c,.quick_store3
.quick_mix3:
        or (hl)
.quick_store3:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour4
        xor a
.quick_colour4:
        rlc b
        jr c,.quick_store4
.quick_mix4:
        or (hl)
.quick_store4:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour5
        xor a
.quick_colour5:
        rlc b
        jr c,.quick_store5
.quick_mix5:
        or (hl)
.quick_store5:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour6
        xor a
.quick_colour6:
        rlc b
        jr c,.quick_store6
.quick_mix6:
        or (hl)
.quick_store6:
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.quick_colour7
        xor a
.quick_colour7:
        rlc b
        jr c,.quick_store7
.quick_mix7:
        or (hl)
.quick_store7:
        ld (hl),a
        inc hl
        inc de
        jp .skip
.slow_pixels:
        ld ix,8
.pixel:
        ld a,d
        cp 0xE0
        jr nz,.mapped
        ld d,0xC0
        ld a,(C_MAP)
        inc a
        ld (C_MAP),a
        nextreg 0x56,a
.mapped:
        ld a,(hl)
        cp 254
        jr nz,$+3
        xor a
        rlc c
        jr c,.colour
        xor a
.colour:
        ld iyl,a
        rlc b
        jr c,.masked
        ld a,(de)
.pixel_mix:
        or iyl
        jr .store
.masked:
        ld a,iyl
.store:
        ld (de),a
        inc hl
        inc de
        dec ixl
        jr nz,.pixel
.skip:
        ld a,(C_CUT)
        ld c,a
        ld a,(C_ROT)
        dec a
        jr z,.right
        dec a
        jr nz,.keep_cut
        rlc c
        jr .keep_cut
.right:
        rrc c
.keep_cut:
        ld a,c
        ld (C_CUT),a
        ld hl,(C_SRC)
        inc hl
        inc hl
        ld (C_SRC),hl
        ld hl,(C_CSRC)
        inc hl
        inc hl
        ld (C_CSRC),hl
        ld hl,(C_POS)
        ld de,8
        add hl,de
        ld (C_POS),hl
        ld hl,C_LEFT
        dec (hl)
        jp nz,.byte
        ld hl,(C_ROWPOS)
        ld de,-192
        add hl,de
        ld (C_ROWPOS),hl
        ld hl,C_LINE
        dec (hl)
        jp nz,.row
        ret
        INCLUDE "lib/hlib_dma.asm"
        INCLUDE "bubbler_copy.inc"
        INCLUDE "bubbler_buffer.inc"
colour_end:
        SAVEBIN "bubbler_auxiliary.bin",0xA000,colour_end-0xA000

; Bubbler Enhanced: paced original drawing plus the approved private colour canvas.
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_CSP EQU 0x3D80
V_CSPEED EQU 0x3D82
V_ACTIVE EQU 0x3D84
V_FLIP EQU 0x3D86
V_SHIFT EQU 0x3D87
V_VALID EQU 0x3D88
V_PREP EQU 0x3D89
V_PREP_SRC EQU 0x3D8A
V_PREP_ROWS EQU 0x3D8C
V_CCOUNT EQU 0x3D8E
V_TARGET EQU 0x3D90
V_TOTAL EQU 0x3D92
V_PHASE EQU 0x3D94
V_COPY_SPEED EQU 0x3D95
V_SUB_ACTIVE EQU 0x3D96
V_SUB_SPEED EQU 0x3D97
V_FAST_COPY EQU 0x3D98
V_FAST_SPEED EQU 0x3D99
V_SCENERY_SPEED EQU 0x3D9A
V_BUILD_SPEED EQU 0x3D9B
V_BUILD_B EQU 0x3D9C
V_EARLY_RESTORE EQU 0x3D9D
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ENDM
        MACRO EXIT delta, target
        ld a,delta
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp target
        ENDM
h_open:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld hl,0
        ld (V_CCOUNT),hl
        ld (HLIB_V_PACE+4),hl
        ld (V_TOTAL),hl
        ld (V_TARGET),hl
        ld (V_PHASE),hl
        ld (HLIB_V_PACE+14),hl
        call hlib_pace_open
        EXIT -12,0xAC40
h_close:
        ENTER
        push ix
        push iy
        call colour_hold
        ld a,(0x5CE9)
        ld hl,0xE4A6
        add a,l
        ld l,a
        jr nc,.view
        inc h
.view:
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (C_SRC),de
        ld (V_PREP_SRC),de
        ld a,112
        ld (C_ROWS),a
        ld (V_PREP_ROWS),a
        ld hl,colour_prepare
        call colour_call
        call colour_resume
        call colour_accumulate
        ld a,1
        ld (V_PREP),a
        ld (V_PHASE),a
        pop iy
        pop ix
        HLIB_SPEED_OUT V_SPEED
        EXIT -12,0xA837

        MACRO C_IN
        nextreg 0x51,HOOK_PAGE
        ld (V_CSP),sp
        ld sp,0x3FF0
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        call colour_hold
        ENDM
        MACRO C_OUT delta
        call colour_resume
        ld a,delta
        call hlib_r_set
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_CSP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
colour_hold:
        push af
        push bc
        push de
        push hl
        ld a,(HLIB_V_PACE+10)
        and a
        jr z,.done
        ld hl,(V_CCOUNT)
        inc hl
        ld (V_CCOUNT),hl
        call hlib_pace_tick
        call hlib_pace_hold
.done:
        pop hl
        pop de
        pop bc
        pop af
        ret
colour_resume:
        ld a,(HLIB_V_PACE+10)
        and a
        ret z
        jp hlib_pace_resume
colour_accumulate:
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld a,(V_PHASE)
        cp 2
        ld a,103
        jr nz,.scale
        ld a,92
.scale:
        call hlib_mul8
        push hl
        ld hl,(V_CCOUNT)
        ld a,112
        call hlib_mul8
        ex de,hl
        pop hl
        or a
        sbc hl,de
        jr nc,.target
        ld hl,0
.target:
        ld de,(V_TARGET)
        add hl,de
        ld (V_TARGET),hl
        ld hl,(HLIB_V_PACE+2)
        ld de,(HLIB_V_PACE+14)
        add hl,de
        ld de,(V_TOTAL)
        add hl,de
        ld (V_TOTAL),hl
        xor a
        ld (HLIB_V_PACE+10),a
        ret
colour_segment_open:
        ld hl,0
        ld (HLIB_V_PACE+4),hl
        ld (V_CCOUNT),hl
        ld (HLIB_V_PACE+14),hl
        jp hlib_pace_open
colour_final_wait:
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld de,(V_TOTAL)
        add hl,de
        ld (HLIB_V_PACE+2),hl
        ld hl,(V_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
        xor a
        ld (V_PHASE),a
        ret
colour_sub_start:
        push af
        push bc
        push de
        push hl
        ld a,(HLIB_V_PACE+10)
        and a
        jr nz,.done
        ld a,1
        ld (V_SUB_ACTIVE),a
        HLIB_SPEED_IN V_SUB_SPEED
        call colour_segment_open
        call hlib_pace_hold
.done:
        pop hl
        pop de
        pop bc
        pop af
        ret
colour_sub_finish:
        ld a,(V_SUB_ACTIVE)
        and a
        ret z
        call colour_resume
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld a,101
        call hlib_mul8
        push hl
        ld hl,(V_CCOUNT)
        ld a,112
        call hlib_mul8
        ex de,hl
        pop hl
        or a
        sbc hl,de
        jr nc,.target
        ld hl,0
.target:
        push hl
        ld hl,(HLIB_V_PACE+2)
        ld de,(HLIB_V_PACE+14)
        add hl,de
        ld (HLIB_V_PACE+2),hl
        pop hl
        ld a,(V_SUB_SPEED)
        call hlib_pace_wait
        HLIB_SPEED_OUT V_SUB_SPEED
        xor a
        ld (V_SUB_ACTIVE),a
        ret
; HL=auxiliary target. Incoming MMU2/5/6/7, clock and IFF are restored.
colour_call:
        ld (.call+1),hl
        HLIB_IFF_DI
        push af
        HLIB_SPEED_IN V_CSPEED
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x55
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x55,25
.call: call 0
        pop af
        nextreg 0x57,a
        pop af
        nextreg 0x56,a
        pop af
        nextreg 0x55,a
        pop af
        nextreg 0x52,a
        HLIB_SPEED_OUT V_CSPEED
        pop af
        HLIB_IFF_EI
        ret
; Current original scenery header, after its in-place mirror. All known
; canonical headers are zero except image80A8, whose canonical bit7 is one.
scenery_flip:
        ld a,(hl)
        ld e,a
        ld a,h
        cp 0x80
        jr nz,.normal
        ld a,l
        cp 0xA8
        jr nz,.normal
        ld a,e
        xor 0x80
        ld e,a
.normal:
        ld a,e
        and 0x80
        jr z,.store
        ld a,12
.store:
        ld (V_FLIP),a
        ret

h_scenery_open:
        ENTER
        HLIB_SPEED_IN V_SCENERY_SPEED
        call colour_segment_open
        EXIT -12,0xCC71
h_scenery_close:
        ENTER
        call colour_hold
        ld a,(V_SCENERY_SPEED)
        ld (V_SUB_SPEED),a
        ld a,1
        ld (V_SUB_ACTIVE),a
        call colour_sub_finish
        EXIT -12,0xCEE2
h_actor_source:
        C_IN
        ld (V_ACTIVE),de
        xor a
        ld (V_FLIP),a
        C_OUT -13
        ld a,(ix+0x16)
        jp 0xB442
h_static_source_c5f8:
        C_IN
        ld (V_ACTIVE),hl
        call scenery_flip
        C_OUT -13
        ld a,l
        add a,c
        ld l,a
        jp 50683
h_static_source_c747:
        C_IN
        ld (V_ACTIVE),hl
        call scenery_flip
        C_OUT -13
        ld a,l
        add a,c
        ld l,a
        jp 51018
h_actor_draw:
        C_IN
        ld (C_DST),de
        ld a,b
        ld (C_ROWS),a
        ld a,c
        ld (C_SHIFT),a
        ld (V_SHIFT),a
        ld a,(0xB4A7)
        ld (C_WIDTH),a
        xor a
        ld (C_FLIP),a
        ld (C_ROT),a
        ld a,255
        ld (C_CUT),a
        ld hl,(V_CSP)
        ld a,h
        cp 0x60
        jr nc,.source
        ld de,-0x5B72
        add hl,de
        push hl
        ld de,(V_ACTIVE)
        inc de
        inc de
        add hl,de
        ld (C_SRC),hl
        pop hl
        srl h
        rr l
        ld a,l
        and 7
        ld b,a
        ld a,(ix+0x16)
        and 0xF0
        rrca
        rrca
        sub 4
        ld c,a
        ld a,(0xA2DD)
        and 3
        add a,c
        ld e,a
        ld d,0
        ld hl,0xB416
        add hl,de
        ld c,(hl)
        ld a,(0xA2DD)
        and 1
        jr z,.left
        ld a,1
        ld (C_ROT),a
        inc b
        jr .rcheck
.right:
        rrc c
.rcheck:
        djnz .right
        jr .cut
.left:
        ld a,2
        ld (C_ROT),a
        inc b
        jr .lcheck
.lrotate:
        rlc c
.lcheck:
        djnz .lrotate
.cut:
        ld a,c
        ld (C_CUT),a
        ld hl,(C_SRC)
.source:
        ld (C_SRC),hl
        inc hl
        ld (C_CSRC),hl
        ld a,1
        ld (V_VALID),a
        ld hl,colour_draw
        call colour_call

        C_OUT -13
        ld a,c
        and a
        jr z,.zero
        jp 0xB4B5
.zero:  jp 0xB4BC
h_static_full:
        C_IN
        ld de,(0x5CBB)
        add hl,de
        ld (C_DST),hl
        ld a,b
        ld (C_ROWS),a
        xor a
        ld (C_SHIFT),a
        ld hl,(V_CSP)
        ld (C_SRC),hl
        inc hl
        ld (C_CSRC),hl
        ld a,2
        ld (C_WIDTH),a
        xor a
        ld (C_ROT),a
        ld a,255
        ld (C_CUT),a
        ld a,(V_FLIP)
        ld (C_FLIP),a
        ld a,1
        ld (V_VALID),a
        ld hl,colour_draw
        call colour_call

        C_OUT -13
        ld de,(0x5CBB)
        jp 0xC610
h_static_partial:
        C_IN
        ld (C_DST),hl
        ld a,(0xC794)
        ld (C_ROWS),a
        ld a,(0x5CF0)
        and 6
        ld (C_SHIFT),a
        ld hl,(V_CSP)
        ld (C_SRC),hl
        inc hl
        ld (C_CSRC),hl
        ld a,2
        ld (C_WIDTH),a
        xor a
        ld (C_ROT),a
        ld a,255
        ld (C_CUT),a
        ld a,(V_FLIP)
        ld (C_FLIP),a
        ld a,1
        ld (V_VALID),a
        ld hl,colour_draw
        call colour_call

        C_OUT -13
        ld a,(0x5CF0)
        jp 0xC791
h_save:
        C_IN
        ld (C_SRC),de
        ld (C_DST),hl
        ld a,b
        dec a
        ld (C_ROWS),a
        ld a,c
        srl a
        ld (C_WIDTH),a
        ld hl,colour_save
        call colour_call

        C_OUT -12
        ex de,hl
        jp 0xAD9A
h_restore:
        C_IN
        ld a,(V_PHASE)
        cp 3
        jr nz,.ordinary
        call colour_segment_open
        ld a,(V_EARLY_RESTORE)
        and a
        jr nz,.restored
        ld hl,colour_restore
        call colour_call
.restored:
        xor a
        ld (V_EARLY_RESTORE),a
        call colour_final_wait
        jr .done
.ordinary:
        ld hl,colour_restore
        call colour_call
.done:

        C_OUT -13
        ld a,(0xF500)
        jp 0xADA1
h_shift_left4:
        C_IN
        call colour_sub_start
        ld a,4
        ld (B_SHIFT),a
        ld a,0
        ld (B_SIDE),a
        ld hl,colour_shift
        call colour_call

        C_OUT -13
        jp clone_left4
h_shift_left2:
        C_IN
        call colour_sub_start
        ld a,2
        ld (B_SHIFT),a
        ld a,0
        ld (B_SIDE),a
        ld hl,colour_shift
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xCA6D
h_shift_right4:
        C_IN
        call colour_sub_start
        ld a,4
        ld (B_SHIFT),a
        ld a,1
        ld (B_SIDE),a
        ld hl,colour_shift
        call colour_call

        C_OUT -13
        jp clone_right4
h_shift_right2:
        C_IN
        call colour_sub_start
        ld a,2
        ld (B_SHIFT),a
        ld a,1
        ld (B_SIDE),a
        ld hl,colour_shift
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xCBC6
h_clear:
        C_IN
        call colour_sub_start
        ld hl,0
        ld (M_SRC),hl
        ld hl,8
        ld (M_DST),hl
        ld hl,24576
        ld (M_LEN),hl
        ld a,0
        ld (M_BACK),a
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        xor a
        ld (V_VALID),a
        ld (M_VALUE),a
        ld hl,colour_fill
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xE583
h_column:
        C_IN
        ld (C_DST),hl
        ld (C_CUT),a
        ld a,b
        ld (C_ROWS),a
        ld hl,colour_column
        call colour_call

        C_OUT -13
.original:
        ld (hl),a
        inc hl
        ld (hl),a
        add hl,de
        djnz .original
        jp 0xAAA4
h_column_shift:
        C_IN
        call colour_sub_start
        ld hl,24
        ld (M_SRC),hl
        ld hl,8
        ld (M_DST),hl
        ld hl,24560
        ld (M_LEN),hl
        ld a,0
        ld (M_BACK),a
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        ld hl,colour_move
        call colour_call

        C_OUT -13
        ld de,0xE5BB
        jp 0xAAB4
h_byte_shift_0:
        C_IN
        call colour_sub_start
        ld a,(61883)
        ld (C_CUT),a
        ld a,0
        ld (B_SIDE),a
        ld hl,colour_shiftbyte
        call colour_call

        C_OUT -13
        ld hl,0xE5BC
        jp 0xC9CC
h_byte_shift_1:
        C_IN
        call colour_sub_start
        ld a,(58810)
        ld (C_CUT),a
        ld a,1
        ld (B_SIDE),a
        ld hl,colour_shiftbyte
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xCB27
h_up8:
        C_IN
        call colour_sub_start
        ld hl,1544
        ld (M_SRC),hl
        ld hl,8
        ld (M_DST),hl
        ld hl,23040
        ld (M_LEN),hl
        ld a,0
        ld (M_BACK),a
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        ld hl,colour_move
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xC8DD
h_down8:
        C_IN
        call colour_sub_start
        ld de,-0xE5BB
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,15
        add hl,de
        ld (M_SRC),hl
        ld hl,24583
        ld (M_DST),hl
        ld h,0
        ld l,b
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld (M_LEN),hl
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        ld a,1
        ld (M_BACK),a
        ld hl,colour_move
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xC85B
h_clear8:
        C_IN
        call colour_sub_start
        ld de,-0xE5BB-192
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,8
        add hl,de
        ld (M_DST),hl
        ld hl,1536
        ld (M_LEN),hl
        ld a,28
        ld (M_DBASE),a
        xor a
        ld (M_BACK),a
        ld (M_VALUE),a
        ld hl,colour_fill
        call colour_call

        C_OUT -13
        ld (0x5CDA),sp
        jp 0xC865
h_memclear:
        C_IN
        ld de,-0xE5BB
        add hl,de
        jr nc,.skip
        ld a,h
        cp 12
        jr nc,.skip
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,8
        add hl,de
        ld (M_DST),hl
        ld l,b
        ld h,0
        ld a,b
        and a
        jr nz,.length
        inc h
.length:
        add hl,hl
        add hl,hl
        add hl,hl
        ld (M_LEN),hl
        ld a,28
        ld (M_DBASE),a
        xor a
        ld (M_BACK),a
        ld (M_VALUE),a
        ld hl,colour_fill
        call colour_call
.skip:

        C_OUT -12
.original:
        ld (hl),0
        inc hl
        djnz .original
        ret
h_prepare:
        C_IN
        ld a,(V_PREP)
        and a
        jr z,.make
        xor a
        ld (V_PREP),a
        ld hl,(V_CSP)
        ld de,(V_PREP_SRC)
        or a
        sbc hl,de
        jr nz,.make
        ld a,(V_PREP_ROWS)
        cp b
        jr z,.prepared
.make:
        ld hl,(V_CSP)
        ld (C_SRC),hl
        ld a,b
        ld (C_ROWS),a
        ld a,(V_PHASE)
        cp 1
        call z,colour_segment_open
        ld hl,colour_prepare
        call colour_call
        ld a,(V_PHASE)
        cp 1
        call z,colour_final_wait
        HLIB_SPEED_IN V_FAST_SPEED
        ld a,1
        ld (V_FAST_COPY),a
        jr .done
.prepared:
        ld a,(V_PHASE)
        cp 1
        jr nz,.done
        call colour_segment_open
        HLIB_SPEED_IN V_COPY_SPEED
        ld a,2
        ld (V_PHASE),a
        ; C_OUT will resume; seed a zero-length held interval now.
        call hlib_pace_hold
.done:

        C_OUT -13
        ld hl,0x4026
        jp 0xE52E
h_publish:
        C_IN
        ld a,(V_VALID)
        and a
        jr z,.safe
        ld de,0
.beam:
        dec de
        ld a,d
        or e
        jr z,.safe
        call hlib_line
        ld a,h
        and a
        jr nz,.safe
        ld a,l
        cp 6
        jr c,.safe
        cp 120
        jr nc,.safe
        ld a,(V_PHASE)
        cp 2
        jr nz,.beam
        ld a,(0xB540)
        and a
        jr z,.beam
        ld a,(0xB542)
        and a
        jr z,.beam
        ld a,(V_EARLY_RESTORE)
        and a
        jr nz,.beam
        push de
        ld hl,colour_restore
        call colour_call
        pop de
        ld a,1
        ld (V_EARLY_RESTORE),a
        jr .beam
.safe:
        ld a,(P_NEXT)
        ld (P_FRONT),a
        srl a
        nextreg 0x12,a
        ld a,(V_VALID)
        and a
        ld a,0
        jr z,.visibility
        ld a,0x80
.visibility:
        nextreg 0x69,a
        ld a,(V_PHASE)
        cp 2
        jr nz,.done
        call colour_resume
        call colour_accumulate
        HLIB_SPEED_OUT V_COPY_SPEED
        ld a,3
        ld (V_PHASE),a
.done:
        ld a,(V_FAST_COPY)
        and a
        jr z,.end
        HLIB_SPEED_OUT V_FAST_SPEED
        xor a
        ld (V_FAST_COPY),a
.end:

        C_OUT -13
        ld sp,(0x5CDA)
        jp 0xE57E
clone_left4:
        db 6,128,33,186,241,175,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,237,111,43,175,16,181
        jp finish_left4
finish_left4:
        C_IN
        call colour_sub_finish
        C_OUT -13
        jp 51816
clone_right4:
        db 6,128,33,187,229,175,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,237,103,35,16,181
        jp finish_right4
finish_right4:
        C_IN
        call colour_sub_finish
        C_OUT -13
        jp 52161
h_sub_end_ca12:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 51734
h_sub_end_cb1e:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 52002
h_sub_end_cb6c:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 52080
h_sub_end_cc6c:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 52336
h_sub_end_c86e:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 51314
h_sub_end_e599:
        C_IN
        call colour_sub_finish
        C_OUT -13
        ld sp,(0x5CDA)
        jp 58781
h_build_open:
        C_IN
        HLIB_SPEED_IN V_BUILD_SPEED
        call colour_segment_open
        call hlib_pace_hold
        C_OUT -13
        push bc
        ld hl,0xE5D1
        jp 0xAA92

h_build_close:
        C_IN
        ld a,b
        ld (V_BUILD_B),a
        ld a,(V_BUILD_SPEED)
        ld (V_SUB_SPEED),a
        ld a,1
        ld (V_SUB_ACTIVE),a
        call colour_sub_finish
        ld a,(V_BUILD_B)
        cp 1
        jr z,.last
        C_OUT -13
        dec b
        ret z
        exx
        jp 0xAAAE
.last:
        C_OUT -12
        dec b
        ret z
h_column_shift_end:
        C_IN
        call colour_sub_finish
        C_OUT -12
        exx
        jp 0xAA8E
boot_resume:
        nextreg 0x51,HOOK_PAGE
        ld sp,0x3F00
        push af
        push bc
        push de
        push hl
        ld hl,0x3C00
        ld de,0x5B00
        ld bc,256
        ldir
        jp 0xF000
boot_decode_done:
        ld hl,0x5E00
        ld (0xF010),hl
        pop hl
        pop de
        pop bc
boot_r:
        ld a,0
        ld r,a
        pop af
boot_sp:
        ld sp,0
        nextreg 0x51,255
boot_jump:
        jp 0

rom_end:
regblock: defs 32,0
        ASSERT $ < 0x3C00
        SAVEBIN "bubbler_colour_hooks.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x51,24
        ld a,64
        ld (P_FRONT),a
        ld a,70
        ld (P_NEXT),a
        xor a
        ld (V_VALID),a
        nextreg 0x55,25
        ld a,1
        call hlib_dma_init
        nextreg 0x55,5
        nextreg 0x51,255
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,palette
        ld b,0
.pal:
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pal
        nextreg 0x14,0xE3
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x64,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x12,32
        nextreg 0x13,35
        nextreg 0x15,0
        nextreg 0x69,0
        ; Let video-mode changes settle before timing the original game.
        ; The generic bootstrap restores all registers/R after setup returns.
        nextreg 0x51,24
        call hlib_pace_open
        ld hl,9984
        xor a
        call hlib_pace_wait
        ld hl,HLIB_V_PACE
        ld de,HLIB_V_PACE+1
        ld bc,25
        ld (hl),0
        ldir
        nextreg 0x51,255
        ret
palette:
        SAVEBIN "bubbler_setup.bin",setup,palette-setup
