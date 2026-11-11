; Bruce Lee: packed resident/cached figure overlay, original composer retained.
        DEVICE ZXSPECTRUMNEXT
PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SP EQU 0x3E30
V_SPEED EQU 0x3E32
V_FIG EQU 0x3E33
V_BASE EQU 0x3E34
V_IMAGE EQU 0x3E35
V_SLOT EQU 0x3E36
V_X EQU 0x3E37
V_Y EQU 0x3E39
V_PART EQU 0x3E3B
V_FULL EQU 0x3E3C
V_DRAWN EQU 0x3E4C
V_ENH EQU 0x3E50
V_PLAY EQU 0x3E51
V_DIRTY EQU 0x3E52
V_CHANGED EQU 0x3E53
V_SAVE_A EQU 0x3E54
V_IRQ_START EQU 0x3E55
V_IRQ_END EQU 0x3E56
V_IRQ_R EQU 0x3E57
V_IRQ_A EQU 0x3E58
V_COPY_ON EQU 0x3E59
V_COPY_R EQU 0x3E5A
V_COPY_TARGET EQU 0x3E5B
V_COPY_DE EQU 0x3E5D
V_I EQU 0x3E5F
V_PHASE EQU 0x3E60
V_IRQ_CLOCK EQU 0x3E61
V_ENTER_RET EQU 0x3E62
V_IRQ_SP EQU 0x3E64
V_ROOM_WINDOW EQU 0x3E66
V_GAMEOVER EQU 0x3E68
copy_original EQU 0x2300
room_original EQU 0x2380
V_CACHE EQU 0x3E40
        ORG 0x2800
rom_start:
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_speed.asm"
        MACRO ENTER allowirq, measure
        nextreg 0x51,PAGE
        IF allowirq == 0
        di
        ENDIF
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        push hl
        call enter_common
        IF allowirq
        jp po,.off
        ei
.off:
        ENDIF
        IF measure
        call hlib_debt_open
        ENDIF
        ENDM
        MACRO CLOSE_IRQ
        di
        ENDM
        MACRO R_FINISH allowirq
        di
        ld (V_SAVE_A),a
        ld a,3
        ld (V_PHASE),a
        ld a,(V_SAVE_A)
        HLIB_R_OUT
        ld sp,(V_SP)
        IF allowirq
        ei
        ENDIF
        ENDM
        MACRO LEAVE name, nameon, extra
        ld a,20
        call hlib_debt_close
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        jp pe,.on
        di
        ld a,-71-extra
        call hlib_r_set
        pop af
        R_FINISH 0
        jp name
.on:    di
        ld a,-73-extra
        call hlib_r_set
        ei
        pop af
        R_FINISH 1
        jp nameon
        ENDM
        MACRO SPEED_RETURN
        ld (V_SAVE_A),a
        HLIB_SPEED_OUT_A V_SPEED
        ld a,(V_I)
        ld i,a
        ld a,(V_SAVE_A)
        nextreg 0x51,255
        ENDM
h_commit:
        ENTER 1,1
        call background
        call figures
        xor a
        ld (V_FULL),a
        LEAVE x_commit,x_commit_on,0
x_commit:
        ld ix,0xCB1C
        SPEED_RETURN
        jp 0xC7D6
x_commit_on:
        ld ix,0xCB1C
        SPEED_RETURN
        ei
        jp 0xC7D6
h_full:
        ENTER 1,1
        call background
        ld a,1
        ld (V_FULL),a
        call figures
        LEAVE x_full,x_full_on,0
x_full:
        xor a
        ld (0xFE0B),a
        SPEED_RETURN
        jp 0xC2B0
x_full_on:
        xor a
        ld (0xFE0B),a
        SPEED_RETURN
        ei
        jp 0xC2B0
h_plot:
        ENTER 1,1
        ld de,V_DRAWN
        ld a,ixl
        cp 0x1C
        jr z,.index
        inc de
        cp 0xBE
        jr z,.index
        inc de
.index: ld a,(ix+2)
        ld (de),a
        LEAVE x_plot,x_plot_on,0
x_plot:
        push ix
        pop hl
        SPEED_RETURN
        jp 0xC3CE
x_plot_on:
        push ix
        pop hl
        SPEED_RETURN
        ei
        jp 0xC3CE
h_tile:
        ENTER 1,1
        ld a,1
        ld (V_CHANGED),a
        LEAVE x_tile,x_tile_on,0
x_tile:
        ld hl,(0xFEA8)
        SPEED_RETURN
        jp 0xC2BB
x_tile_on:
        ld hl,(0xFEA8)
        SPEED_RETURN
        ei
        jp 0xC2BB
h_lantern:
        ENTER 1,1
        ld a,1
        ld (V_CHANGED),a
        LEAVE x_lantern,x_lantern_on,0
x_lantern:
        push hl
        ld de,0x5D00
        SPEED_RETURN
        jp 0xD63A
x_lantern_on:
        push hl
        ld de,0x5D00
        SPEED_RETURN
        ei
        jp 0xD63A
figures:
        ld a,(V_GAMEOVER)
        or a
        jp nz,hide_all
        ld ix,0xCB1C
        xor a
        ld (V_FIG),a
        ld (V_BASE),a
        call figure
        ld ix,0xCBBE
        ld a,1
        ld (V_FIG),a
        ld a,44
        ld (V_BASE),a
        call figure
        ld ix,0xCCA5
        ld a,2
        ld (V_FIG),a
        ld a,88
        ld (V_BASE),a
        call figure
        ret
h_title:
        ENTER 1,1
        call hide_all
        xor a
        ld (V_PLAY),a
        ld (V_GAMEOVER),a
        nextreg 0x69,0
        LEAVE x_title,x_title_on,0
x_title:
        ld a,7
        ld (0x600B),a
        SPEED_RETURN
        jp 0xC4C2
x_title_on:
        ld a,7
        ld (0x600B),a
        SPEED_RETURN
        ei
        jp 0xC4C2
h_room:
        ENTER 0,1
        call hide_all
        xor a
        ld (V_GAMEOVER),a
        ld a,1
        ld (V_PLAY),a
        ld (V_DIRTY),a
        nextreg 0x69,0
        ld a,20
        call hlib_debt_close
        CLOSE_IRQ
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld a,-71
        call hlib_r_set
        pop af
        R_FINISH 0
        di
        ld a,(0xFE03)
        SPEED_RETURN
        jp 0xC172
hide_all:
        xor a
        ld (V_FULL),a
        ld (V_DRAWN),a
        ld (V_DRAWN+1),a
        ld (V_DRAWN+2),a
        ld b,12
        xor a
.loop:  nextreg 0x34,a
        push af
        xor a
        nextreg 0x38,a
        pop af
        inc a
        djnz .loop
        ret
figure:
        ld a,(V_FIG)
        add a,a
        add a,a
        ld (V_SLOT),a
        ld a,(V_FIG)
        add a,low V_DRAWN
        ld l,a
        ld h,high V_DRAWN
        ld a,(hl)
        or a
        jp z,.hide
        ld a,(ix+2)
        or a
        jp z,.hide
        cp 23
        jp nc,.hide
        ld a,(V_FULL)
        or a
        jr nz,.image
        ; A new figure must wait until its original dirty rectangle reaches it.
        push ix
        pop hl
        ld a,(ix+2)
        dec a
        add a,a
        add a,a
        add a,0x16
        ld e,a
        ld d,0
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(de)
        ld b,a
        inc de
        ld a,(de)
        ld c,a
        ld a,(ix+4)
        or a
        jr z,.rows
        inc c
.rows:
        ld a,(ix+6)
        sub (ix+8)
        sub 4
        ret p
        ld a,(ix+8)
        sub (ix+6)
        sub b
        ret p
        ld a,(ix+7)
        sub (ix+9)
        sub 5
        ret p
        ld a,(ix+9)
        sub (ix+7)
        sub c
        ret p
.image:
        ld a,(ix+2)
        dec a
        add a,a
        ld b,a
        ld a,(ix+3)
        or a
        ld a,b
        jr z,.direction
        inc a
.direction:
        ld b,a
        ld a,(V_BASE)
        add a,b
        ld (V_IMAGE),a
        ; Four metadata bytes for each of four parts per image.
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x3000
        add hl,de
        push hl
        pop iy
.position:
        ld l,(ix+6)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_X),hl
        ld a,(ix+7)
        add a,a
        add a,a
        add a,a
        add a,(ix+4)
        add a,32
        ld (V_Y),a
        xor a
        ld (V_PART),a
.attr:
        ld a,(iy+0)
        cp 116
        jr c,.resident
        ld b,a
        ld a,(V_SLOT)
        ld c,a
        ld a,(V_PART)
        add a,c
        add a,low V_CACHE
        ld l,a
        ld h,high V_CACHE
        ld a,b
        cp (hl)
        jr z,.resident
        ld (hl),a
        ; The source is a packed 128-byte part, not a whole image.
        ld c,a
        and 63
        srl a
        or 0x80
        ld h,a
        ld a,c
        rrca
        and 0x80
        ld l,a
        ld a,c
        rlca
        rlca
        and 3
        add a,26
        nextreg 0x54,a
        ld a,(V_SLOT)
        ld c,a
        ld a,(V_PART)
        add a,c
        add a,116
        rrca
        and 0xBF
        ld bc,0x303B
        out (c),a
        ld bc,0x805B
        otir
        nextreg 0x54,4
.resident:
        ld a,(V_PART)
        ld d,a
        ld a,(V_SLOT)
        add a,d
        nextreg 0x34,a
        ld hl,(V_X)
        bit 0,d
        jr z,.x
        ld bc,16
        add hl,bc
.x:     ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        or (iy+1)
        nextreg 0x37,a
        ld a,(V_Y)
        bit 1,d
        jr z,.y
        add a,16
.y:     nextreg 0x36,a
        ld a,(iy+2)
        nextreg 0x38,a
        ld a,(iy+3)
        nextreg 0x39,a
        inc iy
        inc iy
        inc iy
        inc iy
        ld a,(V_PART)
        inc a
        ld (V_PART),a
        cp 4
        jp nz,.attr
        ret
.hide:  ld a,(V_SLOT)
        ld b,4
.hide_loop:
        nextreg 0x34,a
        push af
        xor a
        nextreg 0x38,a
        pop af
        inc a
        djnz .hide_loop
        ret
h_copy:
        nextreg 0x51,PAGE
        jp copy_enter
x_copy_on:
        SPEED_RETURN
        ei
        ret
x_copy:
        SPEED_RETURN
        ret
; The unchanged704-tile room composer costs423151T and52100M1 (mod128=4).
; Use its saved time for Enhanced painting, then pad to the original duration.
h_roomdraw:
        ENTER 1,0
        call hlib_pace_open
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld a,0
        jp po,.iff
        inc a
.iff:  ld (V_COPY_ON),a
        pop af
        call room_original
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        ; Reproduce the last original CALL and PUSH HL on the original stack.
        ld hl,(V_SP)
        dec hl
        ld (hl),0xC2
        dec hl
        ld (hl),0x0F
        dec hl
        ld (hl),0xFA
        dec hl
        ld (hl),0xFF
        call hlib_pace_tick
        ld a,1
        ld (V_ROOM_WINDOW),a
        call background
        xor a
        ld (V_ROOM_WINDOW),a
        ; Reveal the new room only at the original full-copy commit.
        nextreg 0x69,0
        ld hl,20
        call hlib_debt_add
        ld hl,30225
        ld a,(V_SPEED)
        call hlib_pace_wait
        di
        ld a,(V_COPY_ON)
        or a
        jr z,.off
        ld a,-68
        call hlib_r_set
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        R_FINISH 1
        SPEED_RETURN
        ei
        jp 0xC216
.off:  ld a,-66
        call hlib_r_set
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        R_FINISH 0
        SPEED_RETURN
        jp 0xC216
boot_resume:
        nextreg 0x51,PAGE
        ld sp,0x3F00
        push af
        push bc
        push de
        push hl
        ld hl,0x3C00
        ld de,0x5B00
        ld bc,512
        ldir
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
h_gameover:
        nextreg 0x51,PAGE
        jp gameover_mapped
rom_end:
regblock:
        ds 32
        ASSERT $<=0x3000
        ASSERT $<0x3C00
        SAVEBIN "rom.bin",rom_start,$-rom_start
        ASSERT $<0x3000
        ORG 0xD000
setup:
        nextreg 0x12,16
        nextreg 0x69,0
        nextreg 0x14,1
        nextreg 0x15,0x41
        nextreg 0x4B,0
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        ; Preload 116 resident parts; spare slots are lazily replaced in play.
        xor a
        ld bc,0x303B
        out (c),a
        nextreg 0x54,26
        call load_page
        nextreg 0x54,27
        call load_page
        nextreg 0x54,4
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,palette
        call load_palette
        nextreg 0x43,0x10
        nextreg 0x40,0
        call load_palette
        ret
load_palette:
        ld d,0
.loop:  ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec d
        jr nz,.loop
        ret
load_page:
        ld hl,0x8000
        ld d,32
.page:  ld bc,0x005B
        otir
        dec d
        jr nz,.page
        ret
palette:
        SAVEBIN "setup.bin",setup,$-setup

        ORG 0x2410
background:
        ld a,(V_ENH)
        or a
        ret z
        ld a,(V_PLAY)
        or a
        ret z
        ld a,(V_DIRTY)
        ld b,a
        ld a,(V_CHANGED)
        or b
        jr nz,.check
        nextreg 0x69,128
        ret
.check:
        ld hl,(0x6000)
        ld de,0x9800
        or a
        sbc hl,de
        ret nz
        ld ix,0x6040
        ld iy,0x2040
.tile:  ld a,(V_DIRTY)
        or a
        jr nz,.changed
        ld a,(ix+0)
        cp (iy+0)
        jr z,.next
.changed:
        ld a,(ix+0)
        ld (iy+0),a
        call background_tile
.next:  inc ix
        inc iy
        ; A full room lasts longer than a video frame. Carry its cost into
        ; debt a row at a time so the raster counter cannot wrap unseen.
        ld a,ixl
        and 31
        jr nz,.row_time_done
        ld a,(V_ROOM_WINDOW)
        or a
        jr z,.debt_time
        call hlib_pace_tick
        jr .row_time_done
.debt_time:
        call hlib_debt_tick
.row_time_done:
        ld a,ixh
        cp 0x63
        jr nz,.tile
        xor a
        ld (V_DIRTY),a
        ld (V_CHANGED),a
        nextreg 0x69,128
        ret
background_tile:
        ld c,a
        and 127
        ld l,a
        ld h,0
        DUP 6
        add hl,hl
        EDUP
        set 7,h
        ld a,c
        rlca
        and 1
        add a,30
        nextreg 0x54,a
        ld a,ixl
        and 31
        rlca
        rlca
        rlca
        ld e,a
        ld a,ixl
        and 0x60
        rrca
        rrca
        or 0xA0
        ld d,a
        ld a,ixh
        and 3
        add a,a
        ld b,a
        ld a,ixl
        rlca
        and 1
        add a,b
        add a,32
        nextreg 0x55,a
        ld b,8
.row:   push bc
        DUP 8
        ldi
        EDUP
        pop bc
        ld a,e
        sub 8
        ld e,a
        jr c,.next_row
        inc d
.next_row:
        djnz .row
        nextreg 0x54,4
        nextreg 0x55,5
        ret

; I=23 selects the private word at23FF while MMU1 holds page24. The original
; I is restored at the original clock before unmapping. C003 stays unchanged.
; The original ISR touches C000/FE00 and AF/BC/DE/HL, never the mapped source
; and Layer2 slots, alternate registers or Next registers. Its own EI/RET
; returns here; its refresh contribution is added to the outer saved R.
; The shared hold/resume pair excludes the ISR from debt/window time and
; makes an interrupted shared raster reading retry consistently.
h_irq:
        ; The boot backup is dead after boot_resume. Use its upper end for
        ; IRQ work, including interrupts after the foreground SP is restored.
        ld (V_IRQ_SP),sp
        ld sp,0x3DE0
        push af
        ld a,r
        ld (V_IRQ_START),a
        push bc
        push de
        push hl
        HLIB_SPEED_IN_ABC V_IRQ_CLOCK
        call hlib_pace_hold
        ld a,(V_IRQ_START)
        ld b,a
        sub 8
        and 127
        ld c,a
        ld a,b
        and 128
        or c
        ld (V_IRQ_R),a
        pop hl
        pop de
        pop bc
        pop af
        ld (V_IRQ_A),a
        HLIB_SPEED_OUT_A V_SPEED
        ld a,(V_IRQ_R)
        ld r,a
        ld a,(V_IRQ_A)
        call irq_original
irq_return:
        di
        push af
        ld a,r
        ld (V_IRQ_END),a
        nextreg 0x07,3
        push bc
        push de
        push hl
        call hlib_pace_resume
        ld a,(V_PHASE)
        cp 2
        jr nz,.no_credit
        ld a,(V_IRQ_START)
        ld c,a
        ld a,(V_IRQ_END)
        sub c
        add a,3
        ld c,a
        call hlib_r_add
        ld a,(HLIB_V_R)
        ld b,a
        add a,c
        and 127
        ld c,a
        ld a,b
        and 128
        or c
        ld (HLIB_V_R),a
.no_credit:
        ld a,(V_IRQ_END)
        ld b,a
        sub 7
        and 127
        ld c,a
        ld a,b
        and 128
        or c
        ld (V_IRQ_R),a
        ; The unmasked outer speed latch may be between OUT 243B and IN 253B.
        ld a,(V_PHASE)
        cp 1
        jr nz,.selector_ready
        ld bc,0x243B
        ld a,7
        out (c),a
.selector_ready:
        pop hl
        pop de
        pop bc
        pop af
        ld (V_IRQ_A),a
        HLIB_SPEED_OUT_A V_IRQ_CLOCK
        ld sp,(V_IRQ_SP)
        ld a,(V_IRQ_R)
        ld r,a
        ld a,(V_IRQ_A)
        ei
        ret
irq_original:
        push af
        push bc
        push de
        jp 0xC006

enter_common:
        pop hl
        ld (V_ENTER_RET),hl
        pop hl
        ; Establish the ISR's clock before selecting its temporary vector.
        ; This read and the shared speed latch both run with the caller's IFF.
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (V_SPEED),a
        pop bc
        ld a,i
        ld (V_I),a
        ld a,1
        ld (V_PHASE),a
        ld a,0x23
        ld i,a
        HLIB_SPEED_IN V_SPEED
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        push ix
        push iy
        ld a,2
        ld (V_PHASE),a
        ld hl,(V_ENTER_RET)
        jp (hl)

; The original C2EC..C365 copier is copied from the owner's verified input
; into 2300, without changing any instruction. It only reads IX, copies the
; bitmap/attributes and returns; there are no sound or gameplay calls.
; Exact original costs: empty=64T/8M1, dirty=5076T/73M1, visible=5099T/77M1.
; A carry in its five row advances removes 2T/1M1. The shared limiter repays
; the other hooks' measured debt from this saved copy time.
copy_enter:
        ENTER 1,0
        call hlib_pace_open
        ld hl,363
        ld b,73
        ld a,(ix+10)
        or a
        jr nz,.full
        ld hl,364
        ld b,77
        ld a,(ix+2)
        or a
        jr nz,.full
        ld hl,5
        ld b,8
        jr .cost
.full: ld a,(ix+9)
        and 7
        cp 3
        jr c,.cost
        dec b
.cost: ld (V_COPY_TARGET),hl
        ld a,b
        ld (V_COPY_R),a
        ; Reproduce the original PUSH DE's two dead-stack writes as well.
        ld a,(ix+9)
        rrca
        rrca
        rrca
        ld d,a
        xor (ix+8)
        and 224
        xor (ix+8)
        ld e,a
        ld (V_COPY_DE),de
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld a,0
        jp po,.iff
        inc a
.iff:  ld (V_COPY_ON),a
        pop af
        call copy_original
        push af
        push bc
        push de
        push hl
        ld a,(V_COPY_R)
        cp 8
        jr z,.no_stack_write
        ld de,(V_COPY_DE)
        ld hl,(V_SP)
        dec hl
        ld (hl),d
        dec hl
        ld (hl),e
.no_stack_write:
        ; The copy wrapper's unmeasured entry/exit also consumes its window.
        ld hl,20
        call hlib_debt_add
        ld hl,(V_COPY_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
        CLOSE_IRQ
        ld a,(V_COPY_ON)
        or a
        jr z,.off
        ld a,(V_COPY_R)
        sub 76
        call hlib_r_set
        ei
        pop hl
        pop de
        pop bc
        pop af
        R_FINISH 1
        jp x_copy_on
.off:  ld a,(V_COPY_R)
        sub 74
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        R_FINISH 0
        jp x_copy
; Original game-over text is followed by its final screen copy. Mark the
; reset here, but hide sprites only at that copy's existing commit hook.
; The object descriptors still contain their last poses at this point.
gameover_mapped:
        ENTER 1,1
        ld a,1
        ld (V_GAMEOVER),a
        LEAVE x_gameover,x_gameover_on,3
        ASSERT $<0x2800
        SAVEBIN "background.bin",background,$-background

        ORG 0x3840
pace_start:
        INCLUDE "lib/hlib_pace.asm"
x_gameover:
        ld hl,0xFCDD
        SPEED_RETURN
        jp 0xCAC3
x_gameover_on:
        ld hl,0xFCDD
        SPEED_RETURN
        ei
        jp 0xCAC3
        ASSERT $<0x3C00
        SAVEBIN "pace.bin",pace_start,$-pace_start
