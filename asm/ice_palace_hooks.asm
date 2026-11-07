        DEVICE ZXSPECTRUMNEXT
V_R EQU 0x1000
V_SPEED EQU 0x1010
V_MAP EQU 0x1011
V_N EQU 0x1012
V_PAR EQU 0x1013
V_CPSPEED EQU 0x1014
V_MASKMAP EQU 0x1015
V_S EQU 0x1016
V_OVER EQU 0x1017
V_X EQU 0x1018
V_Y EQU 0x1019
V_COL EQU 0x101A
V_Q EQU 0x101B
V_SRC EQU 0x101C
V_MASK EQU 0x101E
V_ID EQU 0x102C
V_FAM EQU 0x1021
V_HL EQU 0x1022
V_DE EQU 0x1024
V_A EQU 0x1026
V_LEFT EQU 0x1027
V_REC EQU 0x1028
V_HIGH EQU 0x102A
V_BITS EQU 0x1030
V_UNKNOWN EQU 0x1031
HLIB_V_R EQU V_R
HLIB_V_PACE EQU 0x1040
HLIB_PACE_NL EQU 311
RECS EQU 0x0200
PAT EQU 0x0400
SPR EQU 0x0500
ATTR_SAVE EQU 0x1200
LUT EQU 0x1800
MASK_FLAGS EQU 0x1600
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_V1                ; the first pace library, as this engine was verified with
        INCLUDE "lib/hlib_pace.asm"
map_state:
        ld bc,0x243B
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        nextreg 0x50,26
        ld (V_MAP),a
        ret
        MACRO ENTER
        push af
        push bc
        push de
        push hl
        ld a,r
        push af
        call map_state
        HLIB_SPEED_IN V_SPEED
        pop af
        ld (V_R),a
        ENDM
        MACRO RESTORE
        ld a,-15
        call hlib_r_set
        HLIB_R_OUT
        ld a,(V_MAP)
        nextreg 0x50,a
        pop hl
        pop de
        pop bc
        pop af
        ENDM
        MACRO AUX_IN
        push ix
        push iy
        exx
        push bc
        push de
        push hl
        exx
        ex af,af'
        push af
        ex af,af'
        ENDM
        MACRO AUX_OUT
        ex af,af'
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
        pop ix
        ENDM

; Every original body sees the original registers, SP and R. No interrupts
; are disabled by these hooks: the game's drawing phase is already DI.
        MACRO RECORD name, fam, colour, body
name:
        ENTER
        ld (V_HL),hl
        ld (V_DE),de
        ld hl,7
        add hl,sp
        ld a,(hl)
        ld (V_A),a
        ld a,fam
        ld (V_FAM),a
        ld a,colour
        ld (V_COL),a
        call hlib_debt_open
        call record_figure
        ld a,12
        call hlib_debt_close
        HLIB_SPEED_OUT V_SPEED
        RESTORE
        jp body
        ENDM
        RECORD player,0,15,0xBEE6
        RECORD enemy,0,255,0xBEE6
        RECORD projectile,1,6,0xBD9F

record_figure:
        ld a,(V_FAM)
        or a
        ld a,(V_A)
        jr nz,.bullet_id
        and 127
        cp 63
        ret z
        cp 50
        jr .known_id
.bullet_id:
        and 63
        cp 14
.known_id:
        jr c,.valid_id
        ld a,1
        ld (V_UNKNOWN),a
        ret
.valid_id:
        ld hl,(V_HL)
        ld a,(V_FAM)
        or a
        jr nz,.x
        res 0,l
.x:
        ld de,(0x6DAE)
        or a
        sbc hl,de
        ld a,h
        or a
        ret nz
        ld a,l
        cp 239
        ret nc
        and 0xF8
        ld (V_X),a
        ld a,l
        and 4
        rrca
        rrca
        ld c,a
        ld a,(V_A)
        and 0xBF
        cp 63
        ret z
        ; catalogue index: figures 0..255; projectiles 256..383
        ld l,a
        ld h,0
        bit 7,l
        jr z,.normal
        res 7,l
        ld a,(V_FAM)
        or a
        ld a,64
        jr z,.flip
        ld a,32
.flip: add a,l
        ld l,a
.normal:
        add hl,hl
        ld b,0
        add hl,bc
        ld a,(V_FAM)
        or a
        jr z,.index
        inc h
.index: ld (V_ID),hl
        ld hl,(V_DE)
        ld a,(V_FAM)
        or a
        jr nz,.y
        res 0,l
.y:     ld de,(0x6DB0)
        or a
        sbc hl,de
        ld bc,0xA020
        ld a,(V_FAM)
        or a
        jr z,.height
        ld bc,0x9010
.height:
        ld e,c
        ld d,0
        add hl,de
        ld a,h
        or a
        ret nz
        ld a,l
        cp b
        ret nc
        sub c
        ld (V_Y),a
        ld a,(V_COL)
        cp 255
        jr nz,.colour
        ld a,(ix+0)
        and 127
        cp 18
        ret nc
        ld hl,0x9F1E
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        bit 2,(ix+12)
        jr z,.attr
        ld a,(0x9A06)
        and 7
        or 64
.attr:  ld c,a
        and 7
        bit 6,c
        jr z,.colour
        or 8
.colour:
        ld (V_COL),a
        ld a,(V_N)
        cp 32
        jr nc,overflow
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,RECS
        add hl,de
        ld de,(V_ID)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_X)
        ld (hl),a
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,(V_COL)
        ld (hl),a
        ld a,(V_N)
        inc a
        ld (V_N),a
        ret
overflow:
        ld a,1
        ld (V_OVER),a
        ret

        MACRO COPY name, exitname, resume
name:
        ENTER
        ld a,(V_SPEED)
        ld (V_CPSPEED),a
        call hlib_pace_open
        AUX_IN
        call prepare
        AUX_OUT
        ld hl,8
        add hl,sp
        ld (hl),low exitname
        inc hl
        ld (hl),high exitname
        RESTORE
        jp 0x6C03
exitname:
        ENTER
        AUX_IN
        ld hl,ATTR_SAVE
        ld de,0xE100
        ld bc,0x240
        ldir
        call publish
        call hlib_pace_tick
        ld a,(V_CPSPEED)
        ld (V_SPEED),a
        HLIB_SPEED_OUT V_SPEED
        ; Native 128K contention calibration: target plus recording debt keeps
        ; complete player updates within 1% in quiet, busy and sound scenes.
        ld hl,5584
        ld a,(V_SPEED)
        call hlib_pace_wait
        AUX_OUT
        RESTORE
        jp resume
        ENDM
        COPY copy_play,copy_play_end,0x6B39
        COPY copy_death,copy_death_end,0x79D2
        COPY copy_other,copy_other_end,0x94DC

prepare:
        ld bc,0x243B
        ld a,0x55
        out (c),a
        inc b
        in a,(c)
        ld (V_MASKMAP),a
        ld a,(V_PAR)
        xor 64
        ld (V_PAR),a
        xor a
        ld (V_S),a
        ld a,(V_N)
        ld (V_LEFT),a
        ld hl,RECS
        ld (V_REC),hl
.object:
        ld a,(V_LEFT)
        or a
        jp z,.done
        dec a
        ld (V_LEFT),a
        ld hl,(V_REC)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (V_X),a
        inc hl
        ld a,(hl)
        ld (V_Y),a
        inc hl
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        ld (V_COL),a
        ld hl,(V_REC)
        ld bc,8
        add hl,bc
        ld (V_REC),hl
        ld hl,MASK_FLAGS
        add hl,de
        ld a,(hl)
        ld (V_BITS),a
        ; 16 masks per 8K page, 512 bytes per mask.
        ld a,e
        and 15
        add a,a
        add a,0xA0
        ld h,a
        ld l,0
        ld (V_MASK),hl
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,32
        nextreg 0x55,a
        ; bitmap origin, including offscreen rows hidden by the global clip.
        ld a,(V_Y)
        ld l,a
        ld h,0
        bit 7,a
        jr z,.pos
        ld h,255
.pos:   ld a,(0x6DB0)
        and 15
        ld e,a
        ld d,0
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_X)
        rrca
        rrca
        rrca
        and 31
        ld e,a
        ld d,0xE4
        add hl,de
        ld (V_SRC),hl
        xor a
        ld (V_Q),a
.quad:
        ld a,(V_BITS)
        srl a
        ld (V_BITS),a
        jr c,.nonempty
        ld hl,(V_MASK)
        ld de,128
        add hl,de
        ld (V_MASK),hl
        jr .nextquad
.nonempty:
        call quadrant
.nextquad:
        ld a,(V_Q)
        inc a
        ld (V_Q),a
        cp 4
        jr nz,.quad
        call hlib_pace_tick
        jp .object
.done:
        ld a,(V_MASKMAP)
        nextreg 0x55,a
        ld a,(V_S)
        ld c,a
        ld a,(V_HIGH)
        cp c
        jr nc,.high
        ld a,c
        ld (V_HIGH),a
.high:
        ; Preserve original attribute buffer for the original game.
        ld hl,0xE100
        ld de,ATTR_SAVE
        ld bc,0x240
        ldir
        ld hl,0xE100
        ld (hl),6
        ld de,0xE101
        ld bc,0x23F
        ldir
        call 0x6CE7
        ret

quadrant:
        ld hl,(V_MASK)
        ld de,PAT
        ld a,(V_Q)
        and 1
        add a,a
        ld c,a
        ld b,0
        push hl
        ld hl,(V_SRC)
        add hl,bc
        ld a,(V_Q)
        and 2
        add a,h
        ld h,a
        push hl
        pop ix
        pop hl
        push hl
        ld b,16
.row:
        push bc
.byte:
        ld a,(ix+0)
        inc ix
        ld h,0
        ld l,a
        add hl,hl
        add hl,hl
        ld bc,LUT
        add hl,bc
        ldi
        ldi
        ldi
        ldi
        ; Two bytes per row; DE's low bits count generated packed pixels.
        ld a,e
        and 7
        jr nz,.byte
        ld bc,30
        add ix,bc
        pop bc
        djnz .row
        pop hl
        ld de,PAT
        ld b,32
.mask:
        DUP 4
        ld a,(de)
        or (hl)
        ld (de),a
        inc de
        inc hl
        EDUP
        djnz .mask
        ld (V_MASK),hl
        ld a,(V_S)
        cp 64
        jp nc,overflow
        ld c,a
        ld a,(V_PAR)
        add a,c
        srl a
        jr nc,.even
        or 128
.even:  ld bc,0x303B
        out (c),a
        ld hl,PAT
        ld bc,0x805B
        otir
        ld a,(V_S)
        ld l,a
        ld h,0
        add a,a
        add a,a
        add a,l
        ld l,a
        jr nc,.nohigh
        inc h
.nohigh:ld bc,SPR
        add hl,bc
        ld a,(V_Q)
        and 1
        rlca
        rlca
        rlca
        rlca
        ld c,a
        ld a,(V_X)
        add a,c
.sprite_x_offset:
        add a,32
        ld (hl),a
        ld a,(V_COL)
        adc a,0
        inc hl
        push af
        ld a,(V_Q)
        and 2
        rlca
        rlca
        rlca
        ld c,a
        ld a,(V_Y)
        add a,c
        add a,96
        ld (hl),a
        inc hl
        pop af
        ld (hl),a
        inc hl
        ld a,(V_S)
        ld c,a
        ld a,(V_PAR)
        add a,c
        ld c,a
        srl a
        or 0xC0
        ld (hl),a
        inc hl
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a
        ld a,(V_S)
        inc a
        ld (V_S),a
        ret

publish:
        ld bc,0x303B
        xor a
        out (c),a
        ld a,(V_S)
        or a
        jr z,.hide
        ld e,a
        ld hl,SPR
        ld c,0x57
.spr:   ld b,5
        otir
        dec e
        jr nz,.spr
.hide:  ld a,(V_S)
.loop:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.loop
        nextreg 0x15,1
        xor a
        ld (V_N),a
        ret

reset:
        ENTER
        xor a
        ld (V_N),a
        nextreg 0x15,0
        HLIB_SPEED_OUT V_SPEED
        RESTORE
        ld b,24
        jp 0x91E8

boot_resume:
        di
        nextreg 0x50,26
        ld (0x1050),sp
        ld sp,0x1FF0
        push af
        push bc
        push de
        push hl
        ld a,r
        ld (V_R),a
        nextreg 7,3
        ld hl,printer_saved
        ld de,0x5B00
        ld bc,256
        ldir
        call setup
        nextreg 7,0
        ld a,-23
        call hlib_r_set
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(0x1050)
        nextreg 0x50,255
boot_iff:
        ei
boot_jump:
        jp 0
setup:
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,palette
        ld b,0
.pal:   ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pal
        nextreg 0x43,0
        nextreg 0x4B,15
        nextreg 0x1C,2
        nextreg 0x19,16
        nextreg 0x19,239
        nextreg 0x19,64
        nextreg 0x19,191
        nextreg 0x15,0
        xor a
.hide:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hide
        ret
palette:
        ds 256,0
printer_saved:
        ds 256,0
regblock:
        ds 20,0
rom_end:
        ASSERT rom_end < 0x4000
        SAVEBIN "ice_rom.bin",rom_start,rom_end-rom_start
