        DEVICE ZXSPECTRUMNEXT
PAGE EQU 24
dummy_effect EQU 0x3600
V_R EQU 0x3E00
V_SPEED EQU 0x3E04
V_SP EQU 0x3E06
V_FAMILY EQU 0x3E08
V_FRAME EQU 0x3E09
V_OLD EQU 0x3E0A
V_POS EQU 0x3E0C
V_OWNER EQU 0x3E0E
V_CTC_READY EQU 0x3EB0
V_CTC_START EQU 0x3EB1
V_CTC_PAINT EQU 0x3EB2
V_MASK_Y EQU 0x3EB4
V_MASK_BITS EQU 0x3EB5
HLIB_V_R EQU V_R
HLIB_V_PACE EQU 0x3E20
HLIB_PACE_NL EQU 311
        DEFINE HLIB_IFF_FIXED_R
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
        MACRO ENTER
        nextreg 0x51,PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        ENDM
        MACRO RESTORE target, delta
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,delta
        jp po,$+4
        dec a
        call hlib_r_set
        pop af
        jp po,.off
        pop af
        HLIB_R_OUT
        ld sp,(V_SP)
        nextreg 0x51,255
        ei
        jp target
.off:   pop af
        HLIB_R_OUT
        ld sp,(V_SP)
        nextreg 0x51,255
        jp target
        ENDM
        ; Effect exits keep turbo through register/IFF/R restoration. Only
        ; the final hand-back runs at the caller's clock; no original code
        ; or delay changes. The latch macro precedes R_OUT, so its fetches
        ; are removed by the same boundary correction.
        MACRO RESTORE_EFFECT target, delta
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,delta
        jp po,$+4
        dec a
        call hlib_r_set
        pop af
        jp po,.off
        HLIB_SPEED_OUT V_SPEED
        pop af
        HLIB_R_OUT
        ld sp,(V_SP)
        nextreg 0x51,255
        ei
        jp target
.off:   HLIB_SPEED_OUT V_SPEED
        pop af
        HLIB_R_OUT
        ld sp,(V_SP)
        nextreg 0x51,255
        jp target
        ENDM
        MACRO BEGIN name, family, qdisp, body
name:
        IF family = 2
        ; Enter turbo before the IFF/R work. The original stack is untouched;
        ; the shared latch uses the private stack and keeps AF/BC intact.
        nextreg 0x51,PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        HLIB_SPEED_IN V_SPEED
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        ELSE
        ENTER
        HLIB_SPEED_IN V_SPEED
        ENDIF
        ld (V_OLD),bc
        ld (V_POS),de
        ld (V_OWNER),hl
        ld hl,9
        add hl,sp
        ld a,(hl)
        ld (V_FRAME),a
        ld a,family
        ld (V_FAMILY),a
        IF family != 2
        ld a,(0x3E12)
        ld l,a
        ld h,0
        call hlib_debt_add
        ENDIF
        IF family = 2
        ld hl,(0x3E88)
        ld de,78
        add hl,de
        ld (0x3E88),hl
        call effect_clock_open
        ELSE
        call hlib_pace_open
        ENDIF
        IF family = 2
        RESTORE qdisp, -39
        ELSE
        RESTORE qdisp, -24
        ENDIF
qdisp:
        push af
        push bc
        push de
        jp body
        ENDM
        BEGIN large_in,0,large_displaced,0x76DD
        BEGIN small_in,1,small_displaced,0x795F
        BEGIN effect_in,2,effect_displaced,0x92FE
        MACRO END name, body
name:
        ENTER
        call finish_plot
        IF body = 0x9360
        RESTORE_EFFECT body,-24
        ELSE
        RESTORE body,-24
        ENDIF
        ENDM
        END large_out,0x789A
        END small_out,0x7AB3
        END effect_out,0x9360
; Exit hooks include the original displaced pops, before returning to the body.
large_exit:
        pop hl
        pop ix
        jp large_out
small_exit:
        pop hl
        pop ix
        jp small_out
effect_exit:
        pop hl
        pop de
        pop bc
        jp effect_out
        MACRO CLEAR name, qdisp, address, resume
name:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call reset_sprites
        xor a
        call hlib_debt_close
        HLIB_SPEED_OUT V_SPEED
        RESTORE qdisp,-24
qdisp:
        ld c,0
        ld hl,address
        jp resume
        ENDM
        CLEAR clear_all,clear_all_disp,0x5AFF,0xB050
        CLEAR clear_play,clear_play_disp,0x5800,0xB066
reset_sprites:
        ld b,128
        xor a
.loop:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .loop
        ld hl,0x3800
        ld de,0x3801
        ld bc,127
        xor a
        ld (hl),a
        ldir
        ld hl,0x3900
        ld b,64
        xor a
.maps:  ld (hl),a
        inc hl
        inc a
        djnz .maps
        xor a
        ld (0x3E6B),a
        ld (0x3E73),a
        ld (0x3E7B),a
        call reset_effects
        ret
boot_resume:
        nextreg 0x51,PAGE
        ld sp,0x3F00
        push af
        push bc
        push de
        push hl
        nextreg 0x54,34
        ld hl,0x8000
        ld de,0x5B00
        ld bc,512
        ldir
        nextreg 0x54,4
        call effect_clock_init
        pop hl
        pop de
        pop bc
boot_r: ld a,0
        ld r,a
        pop af
boot_sp:ld sp,0
        nextreg 0x51,255
boot_jump:jp 0
rom_end:
regblock:
        ds 32
        ASSERT $<0x3000
        SAVEBIN "rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x15,0x41
        nextreg 0x4B,227
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,175
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,palette
        ld d,0
.pal:   ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec d
        jr nz,.pal
        nextreg 0x54,33
        ld hl,0x9400
        ld a,48
        ld bc,0x303B
        out (c),a
        ld d,10
.upload:
        ld bc,0x005B
        otir
        dec d
        jr nz,.upload
        nextreg 0x54,4
        ret
palette:
        SAVEBIN "setup.bin",setup,$-setup

; Development renderer. The original screen and painters are still retained here.
; Pixels are clipped with the game's original foreground cell mask.
V_SLOT EQU 0x3E60
V_PART EQU 0x3E61
V_NPART EQU 0x3E62
V_X EQU 0x3E63
V_Y EQU 0x3E64
V_ROW EQU 0x3E65
V_SRC EQU 0x3E66
V_PAGE EQU 0x3E68
V_ID EQU 0x3E69
V_ATTR_PTR EQU 0x3E8C
V_ATTR EQU 0x3E90
        ASSERT V_ATTR+24<=V_CTC_READY
        ORG 0x3000
render:
        ld a,(0x3E11)
        or a
        ret z
        ld a,(V_FAMILY)
        cp 2
        jp z,render_effect
        ld hl,(V_OWNER)
        ld de,0xB101
        or a
        sbc hl,de
        ret z
        ld a,(V_FAMILY)
        or a
        jr nz,.small
        xor a
        ld (V_SLOT),a
        ld a,4
        ld (V_NPART),a
        ld a,(V_FRAME)
        cp 24
        jr z,.fixture
        ret nc
        ld c,a
        ld a,(0x7BDA)
        or a
        ld a,c
        jp z,.asset
        add a,24
        jp .asset
.fixture:
        ld hl,(V_OWNER)
        ld de,0xB181
        or a
        sbc hl,de
        ld a,l
        and 127
        ret nz
        ld b,5
.div:   srl h
        rr l
        djnz .div
        ld a,h
        or a
        ret nz
        ld a,l
        cp 4
        ret c
        cp 20
        ret nc
        ld (V_SLOT),a
        ld a,96
        jp .asset
.small:
        ld hl,(V_OWNER)
        ld de,0xB181
        or a
        sbc hl,de
        jr nz,.ordinary
        ld c,0
        jr .found
.ordinary:
        ld de,(V_OWNER)
        ld hl,0x3800
        ld c,20
.search:
        ld a,(hl)
        inc hl
        cp e
        jr nz,.miss
        ld a,(hl)
        cp d
        jr z,.found
.miss:  ld a,(hl)
        dec hl
        or (hl)
        jr z,.free
        inc hl
        inc hl
        inc c
        ld a,c
        cp 48
        jr c,.search
        ld a,1
        ld (0x3E6A),a
        ret
.free:  ld a,(V_FRAME)
        or a
        ret z
        ld (hl),e
        inc hl
        ld (hl),d
.found: ld a,c
        ld (V_SLOT),a
        ld a,1
        ld (V_NPART),a
        ld a,(V_FRAME)
        or a
        jp z,hide_one
        cp 48
        ret nc
        add a,48
.asset: ld (V_ID),a
        call apply_pending
        ld a,(V_SLOT)
        add a,128
        ld l,a
        ld h,0x3A
        ld a,(V_NPART)
        ld (hl),a
        ld a,(V_ID)
        ld l,a
        ld h,0
        add hl,hl
        ld de,0x3700
        add hl,de
        ld a,(hl)
        ld (V_PAGE),a
        inc hl
        ld h,(hl)
        ld l,0
        ld (V_SRC),hl
        ld hl,V_ATTR
        ld (V_ATTR_PTR),hl
        xor a
        ld (V_PART),a
.part:  ld a,(V_POS)
        add a,a
        ld c,a
        ld a,(V_PART)
        bit 0,a
        ld a,c
        jr z,.px
        add a,16
        jp c,.skip
.px:    ld (V_X),a
        ld a,(V_POS+1)
        ld c,a
        ld a,(V_PART)
        bit 1,a
        ld a,c
        jr z,.py
        add a,16
.py:    ld (V_Y),a
        ld a,(V_SLOT)
        ld c,a
        ld a,(V_PART)
        add a,c
        ld l,a
        ld h,0x39
        ld c,(hl)
        push hl
        ld a,(0x3E6B)
        add a,58
        ld l,a
        ld a,(hl)
        ld (hl),c
        pop hl
        ld (hl),a
        ld (0x3E6C),a
        ld bc,0x303B
        out (c),a
        ld a,(0x3E6B)
        inc a
        cp 6
        jr c,.queue
        xor a
.queue:
        ld (0x3E6B),a
        ld a,(V_PAGE)
        nextreg 0x54,a
        ld hl,(V_SRC)
        xor a
        ld (V_ROW),a
        dec a
        ld (V_MASK_Y),a
.row:   push hl
        ld a,(V_Y)
        ld c,a
        ld a,(V_ROW)
        add a,c
        cp 176
        jr nc,.blank
        and 248
        ld c,a
        ld a,(V_MASK_Y)
        cp c
        jr z,.cached
        ld a,c
        ld (V_MASK_Y),a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(V_X)
        rrca
        rrca
        rrca
        and 31
        ld e,a
        ld d,0
        add hl,de
        ld de,0x5B00
        add hl,de
        ld d,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld c,(hl)
        ld a,(V_X)
        and 7
        jr z,.mask
        ld b,a
        ld a,c
.shift: sla c
        rl e
        rl d
        djnz .shift
        jr .mask
.blank: ld de,0
.mask:  ld (V_MASK_BITS),de
        jr .pixels
.cached:
        ld de,(V_MASK_BITS)
.pixels:
        pop hl
        ld bc,0x105B
.pixel: sla e
        rl d
        ld a,(hl)
        inc hl
        jr c,.ink
        ld a,227
.ink:   out (c),a
        djnz .pixel
        ld a,(V_ROW)
        inc a
        ld (V_ROW),a
        cp 16
        jr nz,.row
        nextreg 0x54,4
        ld hl,(V_ATTR_PTR)
        ld a,(V_X)
        add a,32
        ld (hl),a
        inc hl
        ld a,0
        adc a,0
        ld c,a
        ld a,(V_Y)
        add a,32
        ld (hl),a
        inc hl
        ld a,(0x3E13)
        or a
        ld a,c
        jr nz,.palready
        push hl
        ld a,(V_SLOT)
        ld l,a
        ld h,0x3A
        ld a,(hl)
        or c
        pop hl
.palready:
        ld (hl),a
        inc hl
        ld a,(0x3E6C)
        or 0xC0
        ld (hl),a
        inc hl
        ld (hl),0
        inc hl
        ld (V_ATTR_PTR),hl
        jr .next
.skip:  ld hl,(V_ATTR_PTR)
        ld b,5
        xor a
.zero:  ld (hl),a
        inc hl
        djnz .zero
        dec hl
        dec hl
        ld (hl),0x40           ; hidden, but still the five-byte form
        inc hl
        inc hl
        ld (V_ATTR_PTR),hl
.next:  ld hl,(V_SRC)
        inc h
        ld a,h
        cp 0xA0
        jr c,.save
        ld h,0x80
        ld a,(V_PAGE)
        inc a
        ld (V_PAGE),a
.save:  ld (V_SRC),hl
        ld a,(V_PART)
        inc a
        ld (V_PART),a
        ld c,a
        ld a,(V_NPART)
        cp c
        jp nz,.part
        ; All patterns are complete before any part changes position/image.
        ; The rotating spare queue replaces hlib_commit's fixed half split.
        ld a,(V_SLOT)
        ld bc,0x303B
        out (c),a
        ld a,(V_NPART)
        ld d,a
        ld hl,V_ATTR
        ld c,0x57
.commit:ld b,5
        otir
        dec d
        jr nz,.commit
        ld a,(V_SLOT)
        or a
        ret nz
        ld a,(V_NPART)
        cp 1
        ret nz
hide_player_tail:
        ld a,1
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        ret
hide_one:
        ld a,(V_SLOT)
        nextreg 0x34,a
        nextreg 0x38,0
        or a
        jp z,hide_player_tail
        ret
render_effect:
        ld a,(V_FRAME)
        cp 6
        ret z                   ; the original's deliberate empty plot
        cp 10
        ret nc
        ld c,a
        ld de,(V_POS)
        ld a,d
        rlca
        xor e
        xor c
        ld l,a
        ld h,0x22
.scan:  ld a,(hl)
        or a
        jr z,.allocate
        ld (0x3E84),hl
        dec a
        ld (0x3E86),a
        ld l,a
        ld h,0x3C
        ld a,(hl)
        cp c
        jr nz,.next
        ld a,l
        add a,a
        ld l,a
        ld h,0x3B
        ld a,(hl)
        inc hl
        cp e
        jr nz,.next
        ld a,(hl)
        cp d
        jr z,.erase
.next:  ld a,(0x3E86)
        ld l,a
        ld h,0x23
        jr .scan
.erase: ld a,(0x3E86)
        ld e,a
        ld l,a
        ld h,0x23
        ld a,(hl)
        ld hl,(0x3E84)
        ld (hl),a
        ld l,e
        ld h,0x3D
        ld (hl),0
        ld a,(0x3E7C)
        ld l,a
        ld h,0x24
        ld (hl),e
        inc a
        ld (0x3E7C),a
        ld a,e
        add a,48
        nextreg 0x34,a
        nextreg 0x38,0
        ret
.allocate:
        ld (0x3E84),hl
        ld a,(0x3E7C)
        or a
        jr nz,.room
        ld a,1
        ld (0x3E6A),a
        ret
.room:  dec a
        ld (0x3E7C),a
        ld l,a
        ld h,0x24
        ld a,(hl)
        ld (0x3E86),a
        inc a
        ld hl,(0x3E84)
        ld (hl),a
        dec a
        ld l,a
        ld h,0x23
        ld (hl),0
        ld h,0x3D
        ld (hl),1
        ld h,0x3C
        ld (hl),c
        add a,48
        ld (V_SLOT),a
        ld a,l
        add a,a
        ld l,a
        ld h,0x3B
        ld (hl),e
        inc hl
        ld (hl),d
        call apply_pending
        ld a,(V_FRAME)
        cp 8
        jr c,.colour
        ld a,(V_SLOT)
        ld l,a
        ld h,0x3A
        ld (hl),0xF0           ; original projectile painter uses bright white
.colour:
        ld a,(V_SLOT)
        nextreg 0x34,a
        ld a,(V_POS)
        add a,a
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        ld c,a
        ld a,(0x3E13)
        or a
        ld a,c
        jr nz,.pal
        ld a,(V_SLOT)
        ld l,a
        ld h,0x3A
        ld a,(hl)
        or c
.pal:   nextreg 0x37,a
        ld a,(V_POS+1)
        add a,32
        nextreg 0x36,a
        ld a,(V_FRAME)
        add a,48
        or 0xC0
        nextreg 0x38,a
        nextreg 0x39,0
        ret
finish_plot:
        ld a,(V_FAMILY)
        cp 2
        jr z,.effect
        call hlib_nest_open
        call render
        xor a
        call hlib_nest_close
        ld a,(V_SPEED)
        ld c,a
        ld a,(V_FAMILY)
        or a
        ld a,(0x3E10)
        jr nz,.k
        ld a,(0x3E14)
.k:     call hlib_pace_waitk
        jr .done
.effect:
        call render
        call effect_clock_wait
        call effect_clock_close
        ret
.done:  HLIB_SPEED_OUT V_SPEED
        ret
        ASSERT $<0x3400
        SAVEBIN "render.bin",render,$-render

        ORG 0x3400
paint_exit:
        pop hl
        pop de
        pop bc
        nextreg 0x51,PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        HLIB_SPEED_IN V_SPEED
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        call paint_clock_open
        pop hl
        pop de
        pop bc
        push bc
        push de
        push hl
        call paint_sprite
        call paint_clock_close
        RESTORE_EFFECT 0x7CEA,-38
paint_sprite:
        ld a,(0x3E13)
        or a
        ret nz
        ld a,c
        and 7
        bit 6,c
        jr z,.dim
        or 8
.dim:   rlca
        rlca
        rlca
        rlca
        ld c,a
        ld (0x3E72),a
        ld (0x3E74),de
        ld a,1
        ld (0x3E73),a
        ; Player paints before its plot; many small figures paint afterwards.
        ld a,(0x3E7B)
        or a
        ret z
        ld hl,(0x3E78)
        or a
        sbc hl,de
        ret nz
        ld a,(0x3E7A)
        ld l,a
        ld h,0x3A
        ld (hl),c
        ld (0x3E6D),a
        add a,128
        ld l,a
        ld a,(hl)
        ld (0x3E6E),a
        xor a
        ld (0x3E6F),a
.colour:
        ld a,(0x3E6D)
        ld b,a
        ld a,(0x3E6F)
        add a,b
        nextreg 0x34,a
        ld a,(0x3E6F)
        and 1
        rlca
        rlca
        rlca
        add a,e
        cp 112
        ld a,c
        jr c,.nohi
        or 1
.nohi:  nextreg 0x37,a
        ld a,(0x3E6F)
        inc a
        ld (0x3E6F),a
        ld b,a
        ld a,(0x3E6E)
        cp b
        jr nz,.colour
        ret
apply_pending:
        ld hl,(V_POS)
        ld (0x3E78),hl
        ld a,(V_SLOT)
        ld (0x3E7A),a
        ld a,1
        ld (0x3E7B),a
        ld a,(0x3E73)
        or a
        ret z
        ld de,(0x3E74)
        or a
        sbc hl,de
        ret nz
        xor a
        ld (0x3E73),a
        ld a,(V_SLOT)
        ld l,a
        ld h,0x3A
        ld a,(0x3E72)
        ld (hl),a
        ret
reset_effects:
        ld hl,0x2200
        ld de,0x2201
        ld bc,511
        xor a
        ld (hl),a
        ldir
        ld hl,0x2400
        ld b,80
        xor a
.free:  ld (hl),a
        inc hl
        inc a
        djnz .free
        ld (0x3E7C),a
        ld hl,0x3D00
        ld de,0x3D01
        ld bc,79
        xor a
        ld (hl),a
        ldir
        ret
        ASSERT $<0x3600
        SAVEBIN "extras.bin",paint_exit,$-paint_exit

; One pace window for the game's empty-plot padding, not one hook per blank plot.
        ORG 0x2000
padding_in:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,(0x9E98)
        cp 16
        jr c,.count
        ld a,16
.count: neg
        add a,16
        ld (0x3E7D),a
        add a,a
        ld l,a
        ld h,0
        ld de,padding_targets
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(0x3E88)
        add hl,de
        ld (0x3E7E),hl
        ld hl,0
        ld (0x3E88),hl
        ld hl,40
        call hlib_debt_add
        call hlib_pace_open
        RESTORE padding_disp,-24
padding_disp:
        ld a,(0x9E98)
        jp 0x9E88
padding_branch:
        jp c,.nonzero
        jp padding_finish
.nonzero:
        ld b,a
        ld a,16
        sub b
        jp 0x9E8F
padding_next:
        djnz .repeat
        jp padding_finish
.repeat:
        jp 0x9E92
padding_finish:
        ENTER
        ld a,(0x3E7D)
        add a,a
        neg
        add a,-24
        ld b,a
        ld a,(0x3E7D)
        or a
        ld a,b
        jr nz,.hasplots
        dec a
.hasplots:
        ld (0x3E80),a
        ld hl,(0x3E7E)
        ld a,(V_SPEED)
        call hlib_pace_wait
        HLIB_SPEED_OUT V_SPEED
        RESTORE padding_ret,(0x3E80)
padding_ret:
        ret
padding_targets:
        DW 2,84,164,244,323,403,483,563,643,723,803,882,962,1042,1122,1202,1282
        ASSERT $<0x2800
        SAVEBIN "padding.bin",padding_in,$-padding_in

; Tiny XOR projectiles retain their original draw/attribute code and clock.
; Only their exit adds a colour-stable hardware overlay; time goes into the
; next original padding window's debt. Both use the shared effect pool.
        ORG 0x2500
projectiles:
bullet_exit:
        pop de
        pop hl
        pop bc
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,8
        call projectile_overlay
        HLIB_SPEED_OUT V_SPEED
        RESTORE 0x8336,-23
cannon_exit:
        pop hl
        pop de
        pop bc
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,9
        call projectile_overlay
        HLIB_SPEED_OUT V_SPEED
        RESTORE 0x906F,-23
projectile_overlay:
        ld (V_FRAME),a
        ld (V_POS),de
        call hlib_debt_open
        call render_effect
        ld a,35
        call hlib_debt_close
        ret
; Owned CTC channel3, interrupt disabled, 28MHz/256: one tick is32
; original3.5MHz T states. The original game has no CTC user.
; Only the normal3.5MHz effect path waits; other incoming clocks keep
; the existing shared speed/pace contract. A missing clock fails open.
effect_clock_init:
        ld bc,0x1B3B
        ld a,0x27
        out (c),a
        xor a
        out (c),a
        in e,(c)
        ld a,100
.spin:  dec a
        jr nz,.spin
        in a,(c)
        cp e
        ld a,0
        jr z,.save
        inc a
.save:  ld (V_CTC_READY),a
        ret
effect_clock_open:
        ld a,(V_CTC_READY)
        or a
        jr nz,.clocked
        ld a,(0x3E15)
        ld l,a
        ld h,0
        call hlib_debt_add
        jp hlib_debt_open
.clocked:
        ld a,0x1B
        in a,(0x3B)
        ld (V_CTC_START),a
        ret
effect_clock_wait:
        ld a,(V_CTC_READY)
        or a
        ret z
        ld a,(V_SPEED)
        or a
        ret nz
        ld e,21
        ; Explosion updates have two effect plots followed by one palette
        ; hook. In default mode its measured133us fits in the two saved
        ; drawing gaps (8+7 ticks). Enhanced has no palette exit hook.
        ; Other callers retain the original plot-duration target.
        ld a,(0x3E13)
        or a
        jr nz,.target
        ld hl,(V_SP)
        inc hl
        inc hl
        ld a,(hl)
        inc hl
        ld d,(hl)
        ld h,a
        ld a,d
        cp 0x95
        jr nz,.target
        ld a,h
        cp 0x79
        jr nz,.second
        ld e,13
        jr .target
.second:
        cp 0x94
        jr nz,.target
.noise: ld e,14
.target:
        ld hl,2048
.wait:  ld a,0x1B
        in a,(0x3B)
        ld d,a
        ld a,(V_CTC_START)
        sub d
        cp e
        ret nc
        dec hl
        ld a,h
        or l
        jr nz,.wait
        ret
effect_clock_close:
        ld a,(V_CTC_READY)
        or a
        jr nz,.clocked
        xor a
        jp hlib_debt_close
.clocked:
        ld a,0x1B
        in a,(0x3B)
        ld e,a
        ld a,(V_CTC_START)
        sub e
        ld b,30
        jr clock_debt
paint_clock_open:
        ld a,(V_CTC_READY)
        or a
        jp z,hlib_debt_open
        ld a,0x1B
        in a,(0x3B)
        ld (V_CTC_PAINT),a
        ret
paint_clock_close:
        ld a,(V_CTC_READY)
        or a
        jr nz,.clocked
        ld a,35
        jp hlib_debt_close
.clocked:
        ld a,0x1B
        in a,(0x3B)
        ld e,a
        ld a,(V_CTC_PAINT)
        sub e
        ld b,30
clock_debt:
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        srl h
        rr l
        srl h
        rr l
        ; CTC ticks32T /14.25T per sixteenth-line =2.246;9/4 is
        ; the conservative integer conversion. Fixed entry/exit is measured
        ; independently, including this add and the final speed hand-back.
        ld d,0
        ld e,b
        add hl,de
        jp hlib_debt_add
        ASSERT $<0x2800
        SAVEBIN "projectiles.bin",projectiles,$-projectiles
