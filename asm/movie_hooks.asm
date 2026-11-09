; Movie companion graphics. The private page is mapped at 0000 while drawing.
; 0000-07FF: colour counterpart of the original 9500-95FF scratch page.
; Private data and game-derived colour pages are constructed by the engine.
        DEVICE ZXSPECTRUMNEXT
        DEFINE HLIB_IFF_FIXED_R
        DEFINE HLIB_PACE_LEAN
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
V_SP            EQU 0x3E00
V_KIND          EQU 0x3E02
V_CLOCK         EQU 0x3E03
V_MMU0          EQU 0x3E04
V_MMU2          EQU 0x3E05
V_IFF           EQU 0x3E06
HLIB_V_R        EQU 0x3E08
V_TARGET        EQU 0x3E0C
V_PACE_TARGET   EQU 0x3E10
V_PLOT_SP       EQU 0x3E20
V_PLOT_CLOCK    EQU 0x3E22
V_PLOT_MMU0     EQU 0x3E23
V_PLOT_IFF      EQU 0x3E24
HLIB_V_PACE     EQU 0x1D40
HLIB_PACE_NL    EQU 312
R_HL_ALT        EQU 0x3FAC
R_DE_ALT        EQU 0x3FAE
R_BC_ALT        EQU 0x3FB0
R_AF_ALT        EQU 0x3FB2
R_IY            EQU 0x3FB4
R_IX            EQU 0x3FB6
R_HL            EQU 0x3FB8
R_DE            EQU 0x3FBA
R_BC            EQU 0x3FBC
R_AF            EQU 0x3FBE
        MACRO SAVE_REGS
        push bc
        push de
        push hl
        push ix
        push iy
        ex af,af'
        push af
        ex af,af'
        exx
        push bc
        push de
        push hl
        exx
        ENDM
        MACRO RESTORE_REGS
        ld sp,R_HL_ALT
        pop hl
        pop de
        pop bc
        exx
        pop af
        ex af,af'
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ENDM
        ORG 0x1800
library_start:
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
library_end:
        ASSERT library_end <= 0x1D00
        SAVEBIN "movie_library.bin",library_start,library_end-library_start

        MACRO ENTRY number
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        ld a,number
        jp hook_enter
        ENDM
        ORG 0x3B20
resident_start:
h_masked:       ENTRY 0
h_mirror:       ENTRY 1
h_shifted:      ENTRY 2
h_shift_mirror: ENTRY 3
h_plain_two:    ENTRY 4
h_plain_one:    ENTRY 5
h_plain_mirror: ENTRY 6
h_plain_mirror_one: ENTRY 7
h_clear:        ENTRY 8
h_commit:       ENTRY 9
h_plot:         ENTRY 10
h_plot_exit:    ENTRY 11
h_speech_write: ENTRY 12
h_clear_screen: ENTRY 13
hook_enter:
        ld (V_KIND),a
        HLIB_R_IN
        HLIB_SPEED_IN V_CLOCK
        SAVE_REGS
        HLIB_IFF_DI
        push af
        pop hl
        ld (V_IFF),hl
        ld bc,0x243B
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        ld (V_MMU0),a
        dec b
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        ld (V_MMU2),a
        nextreg 0x50,26
        jp chunk_begin

; The restore tail executes from resident RAM after MMU0 is returned to its caller.
finish_resident:
        ld a,(V_MMU2)
        nextreg 0x52,a
        ld a,(V_MMU0)
        nextreg 0x50,a
        ld a,(V_IFF)
        and 4
        jr z,.off
        ld a,0xFB
.off:   ld (finish_iff),a
        RESTORE_REGS
        HLIB_SPEED_OUT V_CLOCK
        HLIB_R_OUT
        ld sp,(V_SP)
finish_iff:
        nop
finish_jump:
        jp 0

resume_resident:
        RESTORE_REGS
        HLIB_R_OUT
        ld sp,(V_SP)
        nop
resume_jump:
        jp 0
resident_end:
        ASSERT resident_end <= 0x3D00
        SAVEBIN "movie_resident.bin",resident_start,resident_end-resident_start
        ORG 0x0800
kernel_start:
; Descriptor is already clipped by the original plotter. A source bitmap byte
; has eight cached pixels. LDDX reverses the source while advancing the destination.
; Transparency FF. Source paging is done once per row, then only at 8K boundaries.
draw_chunk:
        ld a,(height)
        or a
        ret z
        ld a,(width)
        or a
        ret z
        ld a,(live)
        or a
        jr nz,draw_general
        ld a,(masked)
        or a
        jp z,fast_plain
draw_general:
.row:
        ld ix,(bitmap)
        ld iy,(mask)
        ld de,(destination)
        ld a,(width)
        ld (left),a
        push de
        push ix
        pop hl
        ld a,h
        srl a
        srl a
        add a,6
        ld c,a
        ld a,(masked)
        or a
        ld a,c
        jr nz,.masked_page
        add a,28
.masked_page:
        ld (colour_page),a
        nextreg 0x52,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        ld a,(mirrored)
        or a
        jr z,.normal_source
        ld de,7
        add hl,de
.normal_source:
        pop de
.byte:
        ld a,(live)
        cp 2
        jp z,.shared_mask
        or a
        jp nz,.live_byte
.cached_byte:
        ld a,d
        cp 7
        jr nz,.fast
        ld a,e
        cp 249
        jr nc,.edge
.fast:
        ld a,(mirrored)
        or a
        jr nz,.fast_reverse
        ld a,255
        REPT 8
        ldix
        ENDR
        res 3,d
        jp .next_byte
.fast_reverse:
        ld a,255
        REPT 8
        lddx
        ENDR
        res 3,d
        jp .next_byte
.edge:
        ld a,(mirrored)
        or a
        jr nz,.edge_reverse
        ld a,255
        REPT 8
        ldix
        res 3,d
        ENDR
        jp .next_byte
.edge_reverse:
        ld a,255
        REPT 8
        lddx
        res 3,d
        ENDR
        jp .next_byte
.shared_mask:
        ld a,ixh
        cp 0xD4
        jr nz,.shared_d3
        ld a,ixl
        cp 4
        jp c,.live_byte
        jp .cached_byte
.shared_d3:
        cp 0xD3
        jp nz,.cached_byte
        ld a,ixl
        cp 0xF4
        jp c,.cached_byte
        jp .live_byte
.live_byte:
        ld b,(ix+0)
        ld a,(masked)
        or a
        ld c,0
        jr z,.mask_ready
        ld c,(iy+0)
.mask_ready:
        ld a,(mirrored)
        or a
        jr z,.reverse_mask
        ld a,b
        mirror a
        ld b,a
        jr .pixels
.reverse_mask:
        ld a,c
        mirror a
        ld c,a
.pixels:
        call live_pixels
.next_byte:
        ld a,(mirrored)
        or a
        jr nz,.previous
        inc ix
        inc iy
        bit 5,h
        jr z,.count
        res 5,h
        ld a,(colour_page)
        inc a
        ld (colour_page),a
        nextreg 0x52,a
        jr .count
.previous:
        dec ix
        dec iy
        bit 6,h
        jr nz,.count
        set 6,h
        res 5,h
        ld a,(colour_page)
        dec a
        ld (colour_page),a
        nextreg 0x52,a
.count:
        ld a,(left)
        dec a
        ld (left),a
        jp nz,.byte
        ld hl,(bitmap)
        ld de,(source_stride)
        add hl,de
        ld (bitmap),hl
        ld hl,(mask)
        add hl,de
        ld (mask),hl
        ld hl,(destination)
        ld de,(destination_stride)
        add hl,de
        res 3,h
        ld (destination),hl
        ld a,(height)
        dec a
        ld (height),a
        jp nz,.row
        ret
kernel_end:
        SAVEBIN "movie_kernel.bin",kernel_start,kernel_end-kernel_start

        ORG 0x0A00
helper_start:
chunk_begin:
        ld a,(V_KIND)
        cp 13
        jp z,clear_screen
        cp 12
        jp z,speech_changed
        cp 10
        jp z,plot_begin
        cp 11
        jp z,plot_end
        cp 8
        jp z,clear_companion
        cp 9
        jp z,commit_companion
        ld a,(V_CLOCK)
        cp 3
        call nz,hlib_pace_open
        call descriptor
        ld a,(V_CLOCK)
        cp 3
        call nz,original_target
        call draw_chunk
        ld a,(V_KIND)
        cp 4
        ld a,241               ; original JP, captured entry R, restore tail
        jr c,.r
        ld a,243               ; three displaced plain-plot instructions
.r:     call hlib_r_set
        jp resume_resident

; Original clipping/header work is drawing too. Keep it at 28 MHz between
; these boundaries; nested colour chunks restore that speed, not 3.5 MHz.
plot_begin:
        ld hl,(V_SP)
        ld (V_PLOT_SP),hl
        ld a,(V_CLOCK)
        ld (V_PLOT_CLOCK),a
        ld a,(V_MMU0)
        ld (V_PLOT_MMU0),a
        ld a,(V_IFF)
        ld (V_PLOT_IFF),a
        ld hl,0xF29F
        ld (resume_jump+1),hl
        ld a,242
        call hlib_r_set
        jp resume_resident
plot_end:
        ld hl,(V_PLOT_SP)
        ld (V_SP),hl
        ld a,(V_PLOT_CLOCK)
        ld (V_CLOCK),a
        ld a,(V_PLOT_MMU0)
        ld (V_MMU0),a
        ld a,(V_PLOT_IFF)
        ld (V_IFF),a
        ld hl,0xF526
        ld (finish_jump+1),hl
        ld a,241
        call hlib_r_set
        jp finish_resident

; The original character writer has just changed (HL-1) and (HL). Update only
; their expanded ink here; every subsequent bubble draw is an ordinary cached copy.
speech_changed:
        ld ix,(R_HL)
        dec ix
        ld a,2
        ld (left),a
.byte:
        ld c,(ix+0)
        push ix
        pop hl
        ld de,224
        add hl,de
        ld a,(hl)
        mirror a
        ld e,a
        push ix
        pop hl
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        nextreg 0x52,58
        push hl
        ld b,8
.pixel:
        rlc e
        sbc a,a
        rlc c
        jr nc,.paper
        ld a,1
.paper:
        ld (hl),a
        inc hl
        djnz .pixel
        pop hl
        nextreg 0x52,86
        ld b,8
.opaque_pixel:
        rlc c
        ld a,0
        adc a,0
        ld (hl),a
        inc hl
        djnz .opaque_pixel
        inc ix
        ld a,(left)
        dec a
        ld (left),a
        jr nz,.byte
        ld a,(R_HL)
        add a,7
        push af
        pop hl
        ld (R_AF),hl
        ld hl,0x727D
        ld (finish_jump+1),hl
        ld a,243
        call hlib_r_set
        jp finish_resident

post_chunk:
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        HLIB_R_IN
        SAVE_REGS
post_wait:
        ld a,(V_KIND)
        cp 8
        jr nc,.pace
        ld a,(V_CLOCK)
        cp 3
        jr z,.rest
.pace:
        ld hl,(V_PACE_TARGET)
        ld a,(V_CLOCK)
        call hlib_pace_wait
.rest:
        ld hl,(V_TARGET)
        ld (finish_jump+1),hl
        ld a,(V_KIND)
        cp 9
        ld a,244
        jr nz,.r
        inc a
.r:
        call hlib_r_set
        jp finish_resident

post_commit:
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        HLIB_R_IN
        SAVE_REGS
        ld hl,(V_SP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_SP),hl
        ld (R_HL),de
        ld hl,0x8200
        ld (R_BC),hl
        jp post_wait

post_clear:
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        HLIB_R_IN
        SAVE_REGS
        ld hl,0x843B
        ld (R_DE),hl
        jp post_wait

descriptor:
        ld hl,(R_HL)
        ld (R_HL_SOURCE),hl
        ld a,(V_KIND)
        add a,a
        ld e,a
        ld d,0
        ld hl,native_targets
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (resume_jump+1),de
        ld a,(V_KIND)
        cp 4
        jp nc,.plain
        ld a,1
        ld (masked),a
        ld a,(V_KIND)
        and 1
        ld (mirrored),a
        ld a,(V_KIND)
        cp 2
        jr nc,.shift
        ld a,(R_BC_ALT)
        ld (width),a
        ld a,(R_BC+1)
        ld (height),a
        ld a,(R_DE_ALT)
        ld (dest_byte),a
        xor a
        ld (phase),a
        ld hl,(R_HL_ALT)
        ld de,(R_HL)
        ld a,(mirrored)
        or a
        jr z,.unshift_pointers
        ex de,hl
.unshift_pointers:
        ld (bitmap),hl
        ld (mask),de
        ld hl,(V_SP)
        ld a,(mirrored)
        or a
        jr z,.positive_width
        ld a,(width)
        neg
        jr .unshift_stride
.positive_width:
        ld a,(width)
.unshift_stride:
        ld e,a
        ld d,0
        bit 7,e
        jr z,.unshift_add
        dec d
.unshift_add:
        add hl,de
        ld (source_stride),hl
        ld a,(R_BC)
        ld hl,width
        add a,(hl)
        ld (dest_bytes),a
        jp .coordinates
.shift:
        ld a,(R_AF+1)
        ld (height),a
        ld a,(V_SP)
        ld (dest_byte),a
        ld a,(0xF409)
        ld (phase),a
        ld hl,(R_HL_ALT)
        ld (mask),hl
        ld a,(mirrored)
        or a
        jr nz,.shift_mirror
        ld hl,(R_BC)
        ld (bitmap),hl
        ld a,(R_BC_ALT)
        ld (width),a
        ld hl,(0xF5D2)
        ld e,a
        ld d,0
        add hl,de
        ld (source_stride),hl
        ld hl,(0xF5D8)
        add a,l
        ld (dest_bytes),a
        jp .coordinates
.shift_mirror:
        ld hl,(R_HL)
        ld (bitmap),hl
        ld a,(R_BC)
        ld (width),a
        ld hl,(0xF618)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld (source_stride),hl
        ld hl,(0xF61C)
        add a,l
        ld (dest_bytes),a
        jp .coordinates
.plain:
        xor a
        ld (masked),a
        ld (phase),a
        ld hl,0
        ld (mask),hl
        ld hl,0xF523
        ld (V_TARGET),hl
        ld a,(V_KIND)
        cp 6
        ld a,0
        jr c,.plain_direction
        inc a
.plain_direction:
        ld (mirrored),a
        ld a,(V_KIND)
        and 1
        xor 1
        inc a
        ld (width),a
        ld hl,2
        ld (source_stride),hl
        ld a,(V_KIND)
        cp 6
        ld a,(R_BC+1)
        jr nz,.plain_height
        ld a,(R_BC_ALT+1)
.plain_height:
        ld (height),a
        ld a,(R_BC)
        ld hl,width
        add a,(hl)
        ld b,a
        ld a,(V_KIND)
        cp 6
        jr nz,.plain_dest_stride
        ld a,(R_BC_ALT)
        add a,2
        ld b,a
.plain_dest_stride:
        ld a,b
        ld (dest_bytes),a
        ld hl,(R_DE)
        ld a,l
        ld (dest_byte),a
        ld (R_HL),hl
        ld hl,(R_HL_SOURCE)
        ld (V_SP),hl
        inc hl
        ld (bitmap),hl
        ld a,(V_KIND)
        cp 4
        jr nz,.plain_other
        ld (V_SP),hl
        ld (R_DE),hl
        jp .coordinates
.plain_other:
        dec hl
        ld h,0
        cp 6
        jr c,.plain_de
        ld h,0x80
.plain_de:
        ld (R_DE),hl
        jp .coordinates
.coordinates:
        ld a,(dest_byte)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(phase)
        ld e,a
        ld d,0
        add hl,de
        res 3,h
        ld (destination),hl
        ld a,(dest_bytes)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld (destination_stride),hl
        xor a
        ld (live),a
        ld a,(bitmap+1)
        cp 0x9F
        jr z,.mutable_small
        cp 0xA4
        jr z,.mutable_door
        cp 0xD2
        jr z,.speech
        cp 0xD3
        jr z,.shared
        cp 0xD4
        ret nz
        ld a,(bitmap)
        cp 4
        ret nc
.shared:
        ld a,2
        ld (live),a
        ret
.speech:
        ret
.mutable_small:
        ld a,(bitmap)
        cp 0x77
        ret c
        jr .live
.mutable_door:
        ld a,(bitmap)
        cp 0x83
        ret nc
.live:  ld a,1
        ld (live),a
        ret
native_targets:
        dw 0xF567,0xF582,0xF5A0,0xF5E6,0xF39D,0xF3AD,0xF3C0,0xF3D9

original_target:
        ld a,(V_KIND)
        ld e,a
        add a,a
        add a,e
        ld e,a
        ld d,0
        ld hl,costs
        add hl,de
        ld a,(hl)
        ld (row_base),a
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (row_constant),a
        ld a,(V_KIND)
        cp 2
        jr c,.multiply
        cp 4
        jr nc,.multiply
        ld a,(phase)
        sub 3
        cp 3
        jr nc,.multiply
        ld a,d
        add a,6
        ld d,a
.multiply:
        ld a,(width)
        ld e,a
        mul d,e
        ld a,(row_base)
        ld l,a
        ld h,0
        add hl,de
        ld de,0
        ld a,(height)
        ld b,a
.rows:  ex de,hl
        add hl,de
        ex de,hl
        djnz .rows
        ex de,hl
        ld a,(row_constant)
        ld e,a
        ld d,0
        add hl,de
target_sixteenths:
        ld b,16
.divide:
        add hl,hl
        rl d
        ld a,d
        sub 14
        jr c,.next_bit
        ld d,a
        inc l
.next_bit:
        djnz .divide
        ld a,d
        cp 7
        jr c,.rounded
        inc hl
.rounded:
        ld (V_PACE_TARGET),hl
        ld hl,32
        ld a,(V_CLOCK)
        or a
        jr z,.debt
        ld b,a
.clock: srl h
        rr l
        djnz .clock
.debt:  call hlib_debt_add
        ret
costs:  db 54,80,55,54,80,43,124,181,30,116,189,42
        db 57,0,33,41,0,42,87,0,30,57,0,34

clear_companion:
        call hlib_pace_open
        ld a,(R_AF+1)
        cp 240
        ld hl,118
        jr c,.normal_cost
        ld l,88
.normal_cost:
        rrca
        rrca
        rrca
        rrca
        and 15
        inc a
        ld e,a
        ld d,101
        mul d,e
        add hl,de
        ld d,0
        call target_sixteenths
        ld a,(0xF70D)
        srl a
        inc a
        ld b,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld sp,hl
        ld hl,0xFFFF
.fill:  REPT 8
        push hl
        ENDR
        djnz .fill
        ld sp,R_HL_ALT
        ld hl,0x9500
        ld (R_HL),hl
        ld hl,0xF18D
        ld (resume_jump+1),hl
        ld hl,0xF1B4
        ld (V_TARGET),hl
        ld a,241
        call hlib_r_set
        jp resume_resident
commit_companion:
        call hlib_pace_open
        call copy_target
        ld a,(bulk_ready)
        or a
        jr nz,.ready
        ld a,1
        ld (bulk_ready),a
        ld a,(bulk_policy)
        call hlib_dma_init
.ready:
        ld a,(0xF716)
        ld (copy_width),a
        ld b,a
        ld a,(0xF71A)
        cp 0x2D
        jr nz,.no_pad
        inc b
.no_pad:
        ld a,b
        ld (copy_stride),a
        ld a,(0xF713)
        ld (copy_rows),a
        dec a
        ld d,a
        ld e,b
        mul d,e
        ld a,(0xF70D)
        ld l,a
        ld h,0
        or a
        sbc hl,de
        ld a,(copy_width)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        inc hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld (copy_source),hl
        ld a,(copy_width)
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(0xF23E)
        sub b
        ld (copy_x),a
        ld a,(0xF23F)
        ld b,a
        ld a,(copy_rows)
        add a,b
        ld b,a
        ld a,192
        sub b
        ld (copy_y),a
.row:
        ld a,(copy_y)
        ld d,a
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        add a,28
        nextreg 0x52,a
        ld a,d
        and 31
        or 0x40
        ld d,a
        ld a,(copy_x)
        ld e,a
        ld hl,(copy_source)
        ld a,(copy_width)
        ld c,a
        ld b,0
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        call bulk_row
        ld a,(copy_stride)
        ld e,a
        ld d,0
        sla e
        rl d
        sla e
        rl d
        sla e
        rl d
        ld hl,(copy_source)
        add hl,de
        res 3,h
        ld (copy_source),hl
        ld a,(copy_y)
        inc a
        ld (copy_y),a
        ld a,(copy_rows)
        dec a
        ld (copy_rows),a
        jr nz,.row
        ld hl,(0xF23E)
        ld (R_BC),hl
        ld hl,0xF704
        ld (resume_jump+1),hl
        ld hl,0xF737
        ld (V_TARGET),hl
        ld a,(V_MMU2)
        nextreg 0x52,a
        ld a,242
        call hlib_r_set
        jp resume_resident

; Exact nominal cost of F700..F737: row count, width and ULA page crossings.
; Native C-simulator fixtures verify all observed rectangle geometries.
copy_target:
        ld a,(0xF716)
        ld e,a
        ld d,21
        mul d,e
        ld hl,77
        add hl,de
        ld (copy_row_cost),hl
        ld a,(0xF23E)
        dec a
        srl a
        srl a
        srl a
        ld (copy_column),a
        ld a,(0xF23F)
        ld b,a
        ld a,191
        sub b
        ld c,a
        ld a,(0xF713)
        ld b,a
        ld hl,210
.row:
        ld de,(copy_row_cost)
        add hl,de
        ld a,c
        and 0x38
        add a,a
        add a,a
        ld d,a
        ld a,(copy_column)
        add a,d
        ld e,a
        ld a,(0xF716)
        cp e
        jr c,.boundary
        jr z,.boundary
        inc hl
.boundary:
        ld a,c
        and 7
        jr nz,.next
        ld a,e
        ld de,22
        cp 32
        jr c,.add
        ld e,32
.add:   add hl,de
.next:  dec c
        djnz .row
        ld d,0
        jp target_sixteenths
helper_end:
        ASSERT helper_end <= 0x1000
        SAVEBIN "movie_helper.bin",helper_start,helper_end-helper_start
        ORG 0x1000
bulk_start:
        DEFINE HLIB_PC_OTIR
        INCLUDE "lib/hlib_dma.asm"
; Dirty rectangles are split at Layer 2's 8K row boundaries. A contiguous row
; needs ordinary synchronous DMA even on DDMA cores; short/wrapped rows stay CPU.
bulk_row:
        ld a,b
        or a
        jr nz,.large
        ld a,c
        cp 32
        jr c,.cpu
.large:
        call hlib_dma_backend
        or a
        jr z,.cpu
        push hl
        add hl,bc
        ld a,h
        cp 8
        jr c,.fits
        jr nz,.wrap
        ld a,l
        or a
        jr z,.fits
.wrap:
        pop hl
        jr .cpu
.fits:
        pop hl
        ld (bulk_source),hl
        ld (bulk_destination),de
        ld (bulk_length),bc
        ld hl,bulk_packet
        ld bc,(bulk_packet_end-bulk_packet)*256+0x6B
        otir
        ret
.cpu:  REPT 8
        ldi
        ENDR
        jp pe,.cpu
        ret
bulk_packet:
        db 0x83,0xC3,0x7D
bulk_source: dw 0
bulk_length: dw 0
        db 0x14,0x10,0xAD
bulk_destination: dw 0
        db 0x82,0xCF,0x87
bulk_packet_end:
bulk_ready: db 0
; Original unmasked strips use a two-byte source stride and byte-aligned output.
; Map their cache once per whole strip, avoiding per-row address/paging work.
fast_plain:
        ld a,(phase)
        or a
        jp nz,draw_general
        ld a,(source_stride)
        cp 2
        jp nz,draw_general
        ld a,(width)
        cp 3
        jp nc,draw_general
        ld a,(bitmap+1)
        and 0xFC
        ld c,a
        ld hl,(bitmap)
        ld a,(mirrored)
        or a
        jr z,.last
        ld a,(width)
        dec a
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld a,h
        and 0xFC
        cp c
        jp nz,draw_general
.last:
        ld hl,(bitmap)
        ld a,(height)
        dec a
        ld e,a
        ld d,0
        sla e
        rl d
        add hl,de
        ld a,(mirrored)
        or a
        jr nz,.last_test
        ld a,(width)
        dec a
        ld e,a
        ld d,0
        add hl,de
.last_test:
        ld a,h
        and 0xFC
        cp c
        jp nz,draw_general
        ld a,(width)
        ld e,a
        ld a,(mirrored)
        or a
        ld a,2
        jr z,.forward_delta
        add a,e
        jr .delta
.forward_delta:
        sub e
.delta:
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld (fast_source_delta),hl
        ld a,e
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,(destination_stride)
        or a
        sbc hl,de
        ld (fast_destination_delta),hl
        ld hl,.forward16
        ld a,(mirrored)
        or a
        jr z,.forward
        ld hl,.reverse16
.forward:
        ld a,(width)
        cp 2
        jr z,.copy_entry
        ld de,18
        add hl,de
.copy_entry:
        ld (.copy_jump+1),hl
        ld hl,(bitmap)
        ld a,h
        srl a
        srl a
        add a,34
        nextreg 0x52,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        ld a,(mirrored)
        or a
        jr z,.destination
        ld de,7
        add hl,de
.destination:
        ld de,(destination)
.row:
        ld a,255
.copy_jump:
        jp 0
.forward16:
        REPT 8
        ldi
        ENDR
        res 3,d
        REPT 8
        ldi
        ENDR
        res 3,d
        jr .advance
.reverse16:
        ; The one-byte entry must skip the same 18 bytes as forward mode.
        REPT 8
        lddx
        ENDR
        res 3,d
        REPT 8
        lddx
        ENDR
        res 3,d
.advance:
        push de
        ld de,(fast_source_delta)
        add hl,de
        pop de
        ex de,hl
        ld bc,(fast_destination_delta)
        add hl,bc
        res 3,h
        ex de,hl
        ld a,(height)
        dec a
        ld (height),a
        jr nz,.row
        ret
fast_source_delta: dw 0
fast_destination_delta: dw 0
; Mutable doors and shared masks need their current bitmap. The direction is
; constant for this byte: choose it once, and unroll the eight original pixels.
        MACRO LIVE_PIXEL backwards
        rlc b
        jr nc,.paper
        rlc c
        ld a,(hl)
        cp 255
        jr nz,.known
        ld a,1
.known:
        or a
        jr nz,.ink
        inc a
.ink:
        ld (de),a
        jr .advance
.paper:
        rlc c
        jr c,.advance
        xor a
        ld (de),a
.advance:
        IF backwards
        dec hl
        ELSE
        inc hl
        ENDIF
        inc de
        res 3,d
        ENDM
live_pixels:
        ld a,(mirrored)
        or a
        jp nz,.backwards
        REPT 8
        LIVE_PIXEL 0
        ENDR
        ret
.backwards:
        REPT 8
        LIVE_PIXEL 1
        ENDR
        ret
clear_screen:
        call hlib_pace_open
        ld a,(bulk_policy)
        call hlib_dma_init
        ld d,28
.page:
        ld a,d
        nextreg 0x52,a
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld hl,clear_packet
        ld bc,(clear_packet_end-clear_packet)*256+0x6B
        otir
        jr .next
.cpu:
        ld sp,0x6000
        ld hl,0xFFFF
        ld b,0
.fill:
        REPT 16
        push hl
        ENDR
        djnz .fill
        ld sp,R_HL_ALT
.next:
        inc d
        ld a,d
        cp 34
        jr nz,.page
        ld a,(V_MMU2)
        nextreg 0x52,a
; Execute the original screen erase on a private return stack. No game-stack
; bytes are introduced, and its LDDR supplies the original flags and registers.
        ld hl,(R_HL)
        dec hl
        ld (R_HL),hl
        ld hl,(R_DE)
        dec hl
        ld (R_DE),hl
        ld a,0x18
        ld (R_BC+1),a
        RESTORE_REGS
        ld sp,0x3FA0
        call 0xFFAA
        ld sp,0x3FC0
        push af
        SAVE_REGS
        ld hl,32
        call hlib_debt_add
        ld hl,9218              ; 129045 original T, rounded to 1/16 raster lines
        ld a,(V_CLOCK)
        call hlib_pace_wait
        ld hl,0xFFAD
        ld (finish_jump+1),hl
        ld a,244
        call hlib_r_set
        jp finish_resident
clear_packet:
        db 0x83,0xC3,0x7D
        dw clear_white,8192
        db 0x24,0x10,0xAD
        dw 0x4000
        db 0x82,0xCF,0x87
clear_packet_end:
clear_white: db 255
bulk_policy: db 1
bulk_end:
        ASSERT bulk_end <= 0x1800
        SAVEBIN "movie_bulk.bin",bulk_start,bulk_end-bulk_start
bitmap                  EQU 0x1D00
mask                    EQU 0x1D02
destination             EQU 0x1D04
source_stride           EQU 0x1D06
destination_stride      EQU 0x1D08
width                   EQU 0x1D0A
height                  EQU 0x1D0B
mirrored                EQU 0x1D0C
masked                  EQU 0x1D0D
live                    EQU 0x1D0E
left                    EQU 0x1D0F
colour_page             EQU 0x1D10
phase                   EQU 0x1D11
dest_byte               EQU 0x1D12
dest_bytes              EQU 0x1D13
row_base                EQU 0x1D14
row_constant            EQU 0x1D15
R_HL_SOURCE             EQU 0x1D16
copy_source             EQU 0x1D18
copy_width              EQU 0x1D1A
copy_stride             EQU 0x1D1B
copy_rows               EQU 0x1D1C
copy_x                  EQU 0x1D1D
copy_y                  EQU 0x1D1E
copy_row_cost           EQU 0x1D20
copy_column             EQU 0x1D22
