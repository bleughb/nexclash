; Head Over Heels: eight masked monochrome planes -> indexed Layer 2 rectangle.
; Development primitives and one hook prototype; NEX integration is pending.
        DEVICE ZXSPECTRUMNEXT
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
HLIB_V_R EQU 0x3702
        ORG 0x2C80
shared_start:
        INCLUDE "lib/hlib_r.asm"
        SAVEBIN "hoh_shared.bin",shared_start,$-shared_start
PLANES EQU 0x2000
L2_PAGE EQU 76
        ORG 0x0800
planar_copy:
        ld a,(rect_w)
        or a
        ret z
        ld a,(rect_h)
        or a
        ret z
        xor a
        ld (source_offset),a
.row:
        ld a,(rect_y)
        ld e,a
        and 31
        or 0xC0
        ld d,a
        ld a,e
        srl a
        srl a
        srl a
        srl a
        srl a
        add a,L2_PAGE
        nextreg 0x56,a
        ld a,(rect_x)
        ld e,a
        ld (destination),de
        ld a,(rect_w)
        ld (bytes_left),a
.byte:
        ld a,(source_offset)
        ld l,a
        ld h,0x20
        ld b,(hl)
        inc h
        ld c,(hl)
        inc h
        ld d,(hl)
        inc h
        ld e,(hl)
        exx
        ld l,a
        ld h,0x24
        ld b,(hl)
        inc h
        ld c,(hl)
        inc h
        ld d,(hl)
        inc h
        ld e,(hl)
        exx
        ld hl,(destination)
        REPT 8
        xor a
        exx
        sla e
        rla
        sla d
        rla
        sla c
        rla
        sla b
        rla
        exx
        sla e
        rla
        sla d
        rla
        sla c
        rla
        sla b
        rla
        ld (hl),a
        inc l
        ENDR
        ld (destination),hl
        ld hl,source_offset
        inc (hl)
        ld hl,bytes_left
        dec (hl)
        jp nz,.byte
        ld a,(rect_w)
        neg
        add a,6
        ld hl,source_offset
        add a,(hl)
        ld (hl),a
        ld hl,rect_y
        inc (hl)
        ld hl,rect_h
        dec (hl)
        jp nz,.row
        ret
rect_x: db 0
rect_y: db 0
rect_w: db 0
rect_h: db 0
source_offset: db 0
bytes_left: db 0
destination: dw 0
kernel_end:
        SAVEBIN "hoh_kernel.bin",planar_copy,kernel_end-planar_copy

; Direct eight-bit masked plot. BC is the private colour buffer, HL the mask
; in MMU6, DE the bitmap in MMU7. Each original byte becomes eight pixels.
; Source pages may cross at any byte; destination wraps just like B800-B8FF.
        ORG 0x2A00
masked_pixels:
        ld a,(plot_h)
        or a
        ret z
        ld a,(plot_w)
        or a
        ret z
        ld a,(mask_page)
        nextreg 0x56,a
        ld a,(bitmap_page)
        nextreg 0x57,a
        ld hl,(mask_ptr)
        ld de,(bitmap_ptr)
        ld bc,(plot_dst)
.row:   ld a,(plot_w)
        ld (plot_left),a
.byte:
        REPT 8
        ld a,(bc)
        and (hl)
        ex de,hl
        or (hl)
        ex de,hl
        ld (bc),a
        inc bc
        inc hl
        inc de
        ENDR
        res 3,b
        call source_wrap
        ld a,(plot_left)
        dec a
        ld (plot_left),a
        jr nz,.byte
        ld a,(plot_w)
        neg
        add a,6
        add a,a
        add a,a
        add a,a
        add a,c
        ld c,a
        jr nc,.dest
        inc b
.dest:  res 3,b
        push bc
        ld a,(plot_skip)
        ld c,a
        ld b,0
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        pop bc
        call source_wrap
        call row_irq_poll
        ld a,(plot_h)
        dec a
        ld (plot_h),a
        jp nz,.row
        ret
source_wrap:
        bit 5,h
        jr z,.bitmap
        res 5,h
        ld a,(mask_page)
        inc a
        ld (mask_page),a
        nextreg 0x56,a
.bitmap:
        bit 7,d
        ret nz
        set 7,d
        set 6,d
        set 5,d
        ld a,(bitmap_page)
        inc a
        ld (bitmap_page),a
        nextreg 0x57,a
        ret
row_irq_poll:
        push af
        push bc
        HLIB_IFF_DI
        jp po,.off
        call pending_irq
        pop bc
        pop af
        ei
        ret
.off:   pop bc
        pop af
        ret
plot_w: db 0
plot_h: db 0
plot_skip: db 0
plot_left: db 0
plot_dst: dw 0
mask_ptr: dw 0
bitmap_ptr: dw 0
mask_page: db 0
bitmap_page: db 0
masked_end:
        SAVEBIN "hoh_masked.bin",masked_pixels,masked_end-masked_pixels

; Linear private colour buffer -> Layer2. Sources keep the game's six-byte
; (48-pixel) row stride; only the actual clipped rectangle is copied.
        ORG 0x2C00
expanded_copy:
        ld a,(rect_w)
        or a
        ret z
        ld a,(rect_h)
        or a
        ret z
        ld hl,PLANES
        ld (expanded_src),hl
.row:
        ld a,(rect_y)
        ld e,a
        and 31
        or 0xC0
        ld d,a
        ld a,e
        srl a
        srl a
        srl a
        srl a
        srl a
        add a,L2_PAGE
        nextreg 0x56,a
        ld a,(rect_x)
        ld e,a
        ld hl,(expanded_src)
        ld a,(rect_w)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld b,0
        ldir
        ld hl,(expanded_src)
        ld bc,48
        add hl,bc
        ld (expanded_src),hl
        ld hl,rect_y
        inc (hl)
        ld hl,rect_h
        dec (hl)
        jr nz,.row
        ret
expanded_src: dw 0
expanded_end:
        SAVEBIN "hoh_expanded.bin",expanded_copy,expanded_end-expanded_copy

; Connected-hook prototype. Private IRQ forwarding is enabled for the masked
; kernel; native pulse timing and the entry/exit DI windows remain unproved.
; Original A19A is LD A,(A057), before JP (HL).
        ORG 0x2D00
h_plot:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        push af
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        exx
        push bc
        push de
        push hl
        exx
        HLIB_SPEED_IN saved_speed
        ld a,1
        ld (hook_active),a
        ld a,(0x3EEC)
        and 4
        jr z,.prepare
        ei
.prepare:
        ld (plot_target),hl
        ld de,plot_table
        ld b,12
.find:  ld a,(de)
        inc de
        cp l
        jr nz,.skip
        ld a,(de)
        cp h
        jr z,.found
.skip:  inc de
        inc de
        inc de
        djnz .find
        jp .finish
.found: inc de
        ld a,(de)
        ld (plot_w),a
        ld c,a
        inc de
        ld a,(de)
        sub c
        add a,a
        add a,a
        add a,a
        ld (plot_skip),a
        ld a,(0xA057)
        ld (plot_h),a
        di                      ; the ISR also writes the NextREG selector
        ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (saved_56),a
        dec b
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        ld (saved_57),a
        ld a,(0x3EEC)
        and 4
        jr z,.pages_ready
        ei
.pages_ready:
        exx
        ld (game_src),de
        ld (game_mask),hl
        ld a,c
        exx
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        set 5,h
        ld (plot_dst),hl
        ld hl,(game_mask)
        call address_pixel
        ld (mask_page),a
        set 7,h
        set 6,h
        ld (mask_ptr),hl
        ld hl,(game_src)
        call address_pixel
        ld (bitmap_page),a
        set 7,h
        set 6,h
        set 5,h
        ld (bitmap_ptr),hl
        di
        nextreg 0x50,26
        im 1
        ; Only private colour RAM is touched below. The forwarding bridge
        ; restores the game bank/clock/stack, so music can run even when the
        ; original plot entered DI. The saved caller IFF is restored on exit.
        call pending_irq
        ei
.masked:
        call masked_pixels
        di
        ld a,(saved_56)
        nextreg 0x56,a
        ld a,(saved_57)
        nextreg 0x57,a
.finish:
        ld a,(0x3EEC)
        and 4
        call nz,pending_irq
        ld a,(0x3EEC)
        and 4
        ld a,96                ; complete original/hook register/R comparison
        jr z,.rset
        dec a                  ; measured enabled/disabled exit refresh spans
        dec a
.rset: call hlib_r_set
        exx
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
        pop af
        jp pe,.on
        pop af
        HLIB_R_OUT
        ld sp,(saved_sp)
        ld a,0
        ld (hook_active),a
        ld a,(saved_speed)
        im 2
        nextreg 0x50,255
        nextreg 0x51,255
        nextreg 0x07,a
        ld a,(0xA057)
        jp 0xA19D
.on:   pop af
        push af
        push bc
        call pending_irq
        pop bc
        pop af
        ei
        nop
        ; Atomic shared-R latch read: an IRQ between LD A and LD R would
        ; otherwise restore an old value. EI/NOP opens after30T at28MHz.
        ld (HLIB_V_R + 2),a
        di
        ld a,(HLIB_V_R + 1)
        ld r,a
        ei
        nop
        ld a,(HLIB_V_R + 2)
        im 2
        ld a,(saved_speed)
        nextreg 0x07,a
        ld a,0
        ld (hook_active),a
        ld sp,(saved_sp)
        nextreg 0x50,255
        nextreg 0x51,255
        ld a,(0xA057)
        jp 0xA19D

; The physical ULA pulse can end during a short DI window. Both vector paths
; clearC8 on acceptance; a latched pulse here is therefore still owed. CALL0038
; has the same refresh/return-frame cost as the private IM1 acknowledgement.
pending_irq:
        ld bc,0x243B
        ld a,0xC8
        out (c),a
        inc b
        in a,(c)
        and 1
        ret z
        call 0x0038
        di
        ret

; Original address4000-FFFF -> source page28-75, offset0-1FFF.
address_pixel:
        ld a,h
        sub 0x40
        srl a
        srl a
        add a,28
        push af
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        pop af
        ret
plot_table:
        dw 0x9A25
        db 1,3
        dw 0x9A3A
        db 2,3
        dw 0x9A56
        db 3,3
        dw 0x9A79
        db 1,4
        dw 0x9A90
        db 2,4
        dw 0x9AAE
        db 3,4
        dw 0x9AD3
        db 4,4
        dw 0x9AFE
        db 1,5
        dw 0x9B17
        db 2,5
        dw 0x9B37
        db 3,5
        dw 0x9B5E
        db 4,5
        dw 0x9B8B
        db 5,5
plot_hook_end:
        ASSERT plot_hook_end < 0x3700
saved_sp EQU 0x3700
saved_speed EQU 0x3705
saved_56 EQU 0x3706
saved_57 EQU 0x3707
plot_target EQU 0x3708
game_src EQU 0x370A
game_mask EQU 0x370C
        SAVEBIN "hoh_plot.bin",h_plot,plot_hook_end-h_plot

; Private IM1 forwarding. The original
; AY ISR changes7FFD, which replaces MMU1 and would lose a stack at3Exx.
; Its own stack therefore uses spare page25 in MMU2, a slot the ISR does not
; read. Restore that mapping before resuming the foreground private stack.
        ORG 0x3000
irq_entry:
        push af
        ld a,r
        ld (i_start),a
        nextreg 0xC8,1
        push bc
        push de
        push hl
        push ix
        push iy
        ld (i_bc),bc
        ld (i_de),de
        ld (i_hl),hl
        ld hl,10
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (i_af),de
        ld (i_sp),sp
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        ld (i_52),a
        dec b
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (i_56),a
        dec b
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        ld (i_57),a
        nextreg 0x52,25
        ld sp,0x5FF0
        call pace_irq_hold
        ld a,(saved_56)
        nextreg 0x56,a
        ld a,(saved_57)
        nextreg 0x57,a
        ld a,(i_start)
        sub 5
        and 127
        ld b,a
        ld a,(i_start)
        and 128
        or b
        ld (i_rout),a
        ld hl,irq_return
        push hl
        ld hl,normal_original
        push hl
        ld a,(saved_speed)
        ld b,a
        ld a,(shift_active)
        or a
        ld a,b
        jr z,.music_speed
        ld a,(shift_speed)
.music_speed:
        ld b,a
        ld a,(render_active)
        or a
        ld a,b
        jr z,.music_ready
        ld a,(render_speed)
.music_ready:
        nextreg 0x07,a
        im 2
        nextreg 0x50,255
        ld hl,(i_af)
        push hl
        pop af
        ld bc,(i_bc)
        ld de,(i_de)
        ld hl,(i_hl)
        ld (i_temp),a
        ld a,(i_rout)
        ld r,a
        ld a,(i_temp)
        ret
irq_return:
        nextreg 0x51,24
        di
        push af
        ld a,r
        ld (i_end),a
        pop af
        nextreg 0x07,3
        nextreg 0x50,26
        call pace_irq_resume
        ld a,(i_56)
        nextreg 0x56,a
        ld a,(i_57)
        nextreg 0x57,a
        ld sp,(i_sp)
        ld a,(i_52)
        nextreg 0x52,a
        ld a,(i_start)
        ld c,a
        ld a,(i_end)
        sub c
        dec a
        ld c,a
        call hlib_r_add         ; a final pending call can follow hlib_r_set
        ld a,(HLIB_V_R)
        ld b,a
        add a,c
        and 127
        ld c,a
        ld a,b
        and 128
        or c
        ld (HLIB_V_R),a
        ld a,(i_end)
        sub 9
        and 127
        ld b,a
        ld a,(i_end)
        and 128
        or b
        ld (i_rout),a
        im 1
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld (i_temp),a
        ld a,(i_rout)
        ld r,a
        ld a,(i_temp)
        ei
        ret
irq_end:
i_start EQU 0x3720
i_end EQU 0x3721
i_sp EQU 0x3722
i_bc EQU 0x3724
i_de EQU 0x3726
i_hl EQU 0x3728
i_af EQU 0x372A
i_52 EQU 0x372C
i_56 EQU 0x372D
i_57 EQU 0x372E
i_rout EQU 0x372F
i_temp EQU 0x3730
hook_active EQU 0x3732
shift_active EQU 0x3734
shift_speed EQU 0x3735
        SAVEBIN "hoh_irq.bin",irq_entry,irq_end-irq_entry

; Normal-vector bridge also covers the small interval before h_plot reads IFF.
; Do not push onto the foreground stack: it may already be in MMU1, which the
; original AY handler replaces through7FFD. MMU2 is10 everywhere outside an
; interrupt in this prototype. The private page25 owns this reserved stack.
        ORG 0x3200
normal_irq:
        nextreg 0x52,25
        ld (n_sp),sp
        ld sp,0x5FF0
        push af
        ld a,r
        ld (n_start),a
        push bc
        push de
        push hl
        push ix
        push iy
        ld bc,0x243B
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        ld (n_51),a
        nextreg 0x51,24
        HLIB_SPEED_IN_ABC n_speed
        call pace_irq_hold
        ld a,(n_speed)
        ld (n_call_speed),a
        ld a,(hook_active)
        and a
        jr z,.shift_speed
        ld a,(saved_speed)
        ld (n_call_speed),a
.shift_speed:
        ld a,(shift_active)
        and a
        jr z,.speed_ready
        ld a,(shift_speed)
        ld (n_call_speed),a
.speed_ready:
        ld a,(render_active)
        and a
        jr z,.render_speed_ready
        ld a,(render_speed)
        ld (n_call_speed),a
.render_speed_ready:
        nextreg 0xC8,1
        ld a,(n_start)
        sub 12
        and 127
        ld b,a
        ld a,(n_start)
        and 128
        or b
        ld (n_rout),a
        HLIB_SPEED_OUT_A n_call_speed
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld (n_temp),a
        ld a,(n_rout)
        ld r,a
        ld a,(n_temp)
        call normal_original
normal_return:
        nextreg 0x51,24
        di
        push af
        ld a,r
        ld (n_end),a
        nextreg 0x07,3
        call pace_irq_resume
        push bc
        ld a,(hook_active)
        and a
        jr z,.no_credit
        ld a,(n_start)
        ld c,a
        ld a,(n_end)
        sub c
        add a,6
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
        ld a,(n_end)
        sub 11
        and 127
        ld b,a
        ld a,(n_end)
        and 128
        or b
        ld (n_rout),a
        pop bc
        pop af
        ld (n_temp),a
        ld a,(n_51)
        nextreg 0x51,a
        ld sp,(n_sp)
        HLIB_SPEED_OUT_A n_speed
        ld a,(n_rout)
        ld r,a
        ld a,(n_temp)
        nextreg 0x52,10
        ei
        ret
normal_original:
        push af
        push bc
        push hl
        jp 0x7379
normal_irq_end:
n_sp EQU 0x5D00
n_start EQU 0x5D02
n_end EQU 0x5D03
n_51 EQU 0x5D04
n_rout EQU 0x5D05
n_temp EQU 0x5D06
n_speed EQU 0x5D07
n_call_speed EQU 0x5D08
        SAVEBIN "hoh_normal.bin",normal_irq,normal_irq_end-normal_irq

; Mutation hooks enter on a private stack, then return to their own immutable
; displaced-instruction tail. No continuation is pushed onto the game stack.
        ORG 0x3400
generic_enter:
        push af
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        exx
        push bc
        push de
        push hl
        exx
        HLIB_SPEED_IN saved_speed
        ld a,1
        ld (hook_active),a
        ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (saved_56),a
        dec b
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        ld (saved_57),a
        dec b
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        ld (mutation_kind),a
        nextreg 0x50,26
        im 1
        ; Companion work is interruptible independently of the caller's IFF.
        ; Original drawing resumes with the exact saved IFF and refresh value.
        call pending_irq
        ei
.run:
        call mutation_dispatch
        di
        ld a,(saved_56)
        nextreg 0x56,a
        ld a,(saved_57)
        nextreg 0x57,a
        ld a,(0x3EEA)
        and 4
        call nz,pending_irq
        ; The original monochrome shift is pure drawing. Run it at28MHz,
        ; keeping a separate caller-clock latch for music and the end hook.
        ld a,(mutation_kind)
        or a
        jr nz,.shift_exit
        ld a,(saved_speed)
        ld (shift_speed),a
        ld a,1
        ld (shift_active),a
        ld a,3
        ld (saved_speed),a
        jr .shift_ready
.shift_exit:
        cp 5
        jr nz,.shift_ready
        ld a,(shift_speed)
        ld (saved_speed),a
        xor a
        ld (shift_active),a
.shift_ready:
        ld a,(mutation_kind)
        cp 19
        jr nz,.render_exit
        ld a,(saved_speed)
        ld (render_speed),a
        ld a,1
        ld (render_active),a
        ld a,3
        ld (saved_speed),a
        jr .render_ready
.render_exit:
        cp 20
        jr nz,.render_ready
        ld a,(render_active)
        or a
        jr z,.render_ready
        ld a,(render_speed)
        ld (saved_speed),a
        xor a
        ld (render_active),a
.render_ready:
        ld a,(0x3EEA)
        and 4
        ld a,91
        jr z,.rset
        sub 2
.rset: call hlib_r_set
        exx
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
        pop af
        jp pe,.on
        pop af
        HLIB_R_OUT
        ld a,0
        ld (hook_active),a
        ld a,(saved_speed)
        nextreg 0x07,a
        im 2
        nextreg 0x50,255
        ld a,(HLIB_V_R + 2)
        ret
.on:   pop af
        push af
        push bc
        call pending_irq
        pop bc
        pop af
        ei
        nop
        ld (HLIB_V_R + 2),a
        di
        ld a,(HLIB_V_R + 1)
        ld r,a
        ei
        nop
        ld a,(HLIB_V_R + 2)
        im 2
        ld a,(saved_speed)
        nextreg 0x07,a
        ld a,0
        ld (hook_active),a
        nextreg 0x50,255
        ld a,(HLIB_V_R + 2)
        ret

; Additional mutation operations share this checked stack/return ABI.
mutation_dispatch:
        ld a,(mutation_kind)
        add a,a
        ld c,a
        ld b,0
        ld hl,mutation_table
        add hl,bc
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        jp (hl)
mutation_table:
        dw shift_pixels,mirror_three,mirror_four,mirror_two
        dw mutation_noop,mutation_noop,xor_pixels,clear_pixels
        dw copy_forward,copy_backward,edge_copy,crop_door
        dw clear_column_one,clear_column_two,stored_column_one,stored_column_two
        dw tiled_column_two,tiled_column_one,ui_pixels,render_begin
        dw display_copy
        dw pace_player
mutation_noop:
        ret

h_shift:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,0
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        dec a
        add a,a
        exx
        jp 0x9EF9
h_wait:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,4
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        ld a,(0x7043)
        jp 0x70F4
h_mirror_three:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,1
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        push hl
        push de
        ex de,hl
        jp 0xAED0
h_mirror_four:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,2
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        push hl
        push de
        ex de,hl
        jp 0xAF0C
h_mirror_two:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,3
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        push de
        ld d,0xB9
        jp 0x9ED1
h_shift_done:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,5
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        pop af
        inc a
        ex af,af'
        jp 0x9F39
h_copy_forward:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,8
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        ldir
        pop hl
        jp 0x81F1
h_copy_backward:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,9
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        lddr
        nop                     ; replaces the ordinary immutable-tail JP
        ret
h_crop:
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,11
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        nop                     ; displaced JR is the continuation jump
        ld c,252
        jp 0x8224
generic_end:
mutation_kind EQU 0x3733
        ASSERT generic_end < 0x3700
        SAVEBIN "hoh_generic.bin",generic_enter,generic_end-generic_enter

; The column entries share the generic register/R/clock envelope.
        ORG 0x2800
column_stubs:
        MACRO COLUMN_ENTER kind
        nextreg 0x51,24
        ld (saved_sp),sp
        ld sp,0x3EF0
        nextreg 0x7F,kind
        call generic_enter
        ld sp,(saved_sp)
        nextreg 0x51,255
        ENDM
h_clear_column_one:
        COLUMN_ENTER 12
        exx
        ld b,a
        ex de,hl
        jp 0x9DFB
h_clear_column_two:
        COLUMN_ENTER 13
        exx
        ld b,a
        ex de,hl
        jp 0x9E0A
h_tiled_column_two:
        COLUMN_ENTER 16
        ld h,0
        ld l,a
        jp 0x9E5A
h_tiled_column_one:
        COLUMN_ENTER 17
        ld h,0
        ld l,a
        jp 0x9E94
h_ui:
        COLUMN_ENTER 18
        ld a,h
        ld hl,0xB800
        jp 0x9566
h_render_begin:
        COLUMN_ENTER 19
        ld (0xA054),de
        jp 0xA0BA
h_display_copy:
        COLUMN_ENTER 20
        ld hl,(0xA052)
        jp 0x93EB
h_player:
        COLUMN_ENTER 21
        push hl
        pop iy
        jp 0xA59D

; IRQs tick twice per frame (entry and exit), avoiding an unseen whole-line
; counter wrap. The library excludes ISR time; pace_player deducts that same
; time from its real-time floor. Both private and normal bridges preserve all
; interrupted registers and restore the prior low mapping around these calls.
pace_irq_hold:
        push af
        xor a
        jr pace_irq_common
pace_irq_resume:
        push af
        ld a,1
pace_irq_common:
        push bc
        push de
        push hl
        push af
        ld bc,0x243B
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        ld (0x5D09),a
        nextreg 0x50,26
        pop af
        or a
        jr z,.hold
        call hlib_pace_resume
        call hlib_pace_tick
        jr .done
.hold: call hlib_pace_tick
        call hlib_pace_hold
.done: ld a,(0x5D09)
        nextreg 0x50,a
        pop hl
        pop de
        pop bc
        pop af
        ret
column_stubs_end:
        ASSERT column_stubs_end <= 0x2A00
        SAVEBIN "hoh_columns.bin",column_stubs,column_stubs_end-column_stubs

; These original loops branch into the displaced entry bytes. Keep their
; complete instruction sequence here, so no back edge enters a patched JP.
        ORG 0x2F00
loop_stubs:
h_xor:
        COLUMN_ENTER 6
        ld c,6
.row:  ld b,2
.byte: ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        djnz .byte
        inc hl
        dec c
        jr nz,.row
        nop                     ; balances the ordinary continuation JP
        ret
h_clear:
        COLUMN_ENTER 7
        ld e,0
.byte: ld (hl),e
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,.byte
        nop
        ret
h_edge:
        COLUMN_ENTER 10
        ld a,4
.byte: ldi
        inc hl
        inc de
        dec a
        jr nz,.byte
        nop
        ret
h_stored_column_one:
        COLUMN_ENTER 14
        ld b,a
.row:  ld a,(hl)
        ld (de),a
        inc hl
        inc hl
        ld a,e
        add a,6
        ld e,a
        djnz .row
        exx
        nop
        ret
h_stored_column_two:
        COLUMN_ENTER 15
        ld b,a
.row:  ld a,(hl)
        ld (de),a
        inc hl
        inc e
        ld a,(hl)
        ld (de),a
        inc hl
        ld a,e
        add a,5
        ld e,a
        djnz .row
        exx
        nop
        ret
loop_stubs_end:
        ASSERT loop_stubs_end <= 0x3000
        SAVEBIN "hoh_loops.bin",loop_stubs,loop_stubs_end-loop_stubs

; Companion shifts operate on complete colour indices, including mask planes.
; A shifted monochrome byte becomes eight pixels; padding is0 for bitmap and
; 255 for mask, preserving the supplied AND/OR mask arithmetic.
        ORG 0x1000
shift_pixels:
        ld a,(0x3EED)
        add a,a
        ld (shift_amount),a
        ld a,(0xADA4)
        add a,a
        add a,a
        add a,a
        ld (shift_width),a
        ld a,(0xA057)
        ld (shift_height),a
        or a
        ret z
        xor a
        ld (shift_pad),a
        ld hl,0xBF20
        call shadow_write
        ex de,hl
        ld hl,(0x3EE4)
        call shadow_read
.half:
        ld a,(shift_height)
        ld (shift_remaining),a
.row:
        ld a,(shift_amount)
        call pad_pixels
        call copy_shift_row
        ld a,(shift_amount)
        neg
        add a,8
        call pad_pixels
        ld a,(shift_remaining)
        dec a
        ld (shift_remaining),a
        jr z,.half_done
        and 3
        call z,row_irq_poll
        jr .row
.half_done:
        ; Hardware interrupts stay enabled within a row. Poll every four
        ; rows and at each half end to bound an already-latched pulse.
        call row_irq_poll
        ld a,(shift_pad)
        or a
        ret nz
        dec a
        ld (shift_pad),a
        ld hl,(0x3EE6)
        call shadow_read
        jr .half

pad_pixels:
        or a
        ret z
        ld b,a
        ld a,d
        cp 0xFF
        jr nz,.fast
        ld a,e
        add a,b
        jr c,.slow
.fast:
        ld a,(shift_pad)
.next:
        ld (de),a
        inc de
        djnz .next
        jp write_wrap
.slow:
        ld a,(shift_pad)
        ld (de),a
        inc de
        call write_wrap
        djnz .slow
        ret

copy_shift_row:
        ld a,(shift_width)
        ld c,a
        ld a,h
        cp 0xDF
        jr nz,.dest
        ld a,l
        add a,c
        jr c,.slow
.dest:
        ld a,d
        cp 0xFF
        jr nz,.fast
        ld a,e
        add a,c
        jr c,.slow
.fast:
        ld b,0
        ld a,c
        cp 24
        jr z,.copy24
        DUP 8
        ldi
        EDUP
.copy24:
        DUP 24
        ldi
        EDUP
        call read_wrap
        jp write_wrap
.slow:
        ld b,c
.pixel:
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        call read_wrap
        call write_wrap
        djnz .pixel
        ret

; These helpers retain DE, so mapping the second source keeps the output head.
shadow_read:
        call shadow_address
        ld (read_page),a
        nextreg 0x56,a
        set 7,h
        set 6,h
        ret
shadow_write:
        call shadow_address
        ld (write_page),a
        nextreg 0x57,a
        set 7,h
        set 6,h
        set 5,h
        ret
shadow_address:
        ld a,h
        cp 0xB8
        jr nz,.normal
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,24
        ret
.normal:
        ld a,h
        sub 0x40
        srl a
        srl a
        add a,28
        push af
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        pop af
        ret
read_wrap:
        bit 5,h
        ret z
        res 5,h
        ld a,(read_page)
        inc a
        ld (read_page),a
        nextreg 0x56,a
        ret
write_wrap:
        bit 7,d
        ret nz
        set 7,d
        set 6,d
        set 5,d
        ld a,(write_page)
        inc a
        ld (write_page),a
        nextreg 0x57,a
        ret

mirror_three:
        ld a,3
        ld hl,(0x3EE6)
        jr mirror_pixels
mirror_four:
        ld a,4
        ld hl,(0x3EE6)
        jr mirror_pixels
mirror_two:
        ld a,2
        ld hl,(0x3EE4)
mirror_pixels:
        ld (mirror_width),a
        ld (mirror_address),hl
        ld a,(0x3EE9)
        ld (mirror_remaining),a
.row:
        ld hl,(mirror_address)
        call shadow_read
        ld (mirror_left),hl
        ld hl,(mirror_address)
        ld a,(mirror_width)
        dec a
        ld c,a
        ld b,0
        add hl,bc
        call shadow_write
        ld a,l
        or 7
        ld l,a
        ex de,hl
        ld hl,(mirror_left)
        ld a,(mirror_width)
        add a,a
        add a,a
        ld b,a
.pair:
        ld c,(hl)
        ld a,(de)
        ld (hl),a
        ld a,c
        ld (de),a
        inc hl
        dec de
        call read_wrap
        call write_unwrap
        djnz .pair
        call row_irq_poll
        ld hl,(mirror_address)
        ld a,(mirror_width)
        ld c,a
        ld b,0
        add hl,bc
        ld (mirror_address),hl
        ld a,(mirror_remaining)
        dec a
        ld (mirror_remaining),a
        jr nz,.row
        ret
write_unwrap:
        bit 5,d
        ret nz
        set 5,d
        ld a,(write_page)
        dec a
        ld (write_page),a
        nextreg 0x57,a
        ret

; The original animation XOR covers six rows of two bytes at stride three.
xor_pixels:
        ld hl,(0x3EE4)
        call shadow_write
        ex de,hl
        ld hl,(0x3EE6)
        call shadow_read
        ld a,6
        ld (mut_rows),a
.row:   ld b,16
.pixel: ld a,(de)
        xor (hl)
        ld (de),a
        inc hl
        inc de
        call read_wrap
        call write_wrap
        djnz .pixel
        ex de,hl
        ld bc,8
        add hl,bc
        ex de,hl
        call write_wrap
        call row_irq_poll
        ld a,(mut_rows)
        dec a
        ld (mut_rows),a
        jr nz,.row
        ret

clear_pixels:
        push ix
        ld ix,(0x3EE8)
        ld hl,(0x3EE4)
        call shadow_write
        ex de,hl
.byte:  xor a
        DUP 8
        ld (de),a
        inc de
        EDUP
        call write_wrap
        dec ix
        ld a,ixl
        and 31
        call z,row_irq_poll
        ld a,ixh
        or ixl
        jr nz,.byte
        pop ix
        ld hl,(0x3EE4)
        ld de,0x4000
        and a
        sbc hl,de
        ret nz
        ld hl,(0x3EE8)
        ld de,0x1800
        and a
        sbc hl,de
        ret nz
        jp display_clear

copy_setup:
        ld hl,(0x3EE6)
        call shadow_write
        ex de,hl
        ld hl,(0x3EE4)
        jp shadow_read
copy_forward:
        push ix
        ld ix,(0x3EE8)
        call copy_setup
.byte:  ld bc,8
        DUP 8
        ldi
        EDUP
        call read_wrap
        call write_wrap
        dec ix
        ld a,ixl
        and 31
        call z,row_irq_poll
        ld a,ixh
        or ixl
        jr nz,.byte
        pop ix
        ret
copy_backward:
        push ix
        ld ix,(0x3EE8)
        call copy_setup
        ld a,l
        or 7
        ld l,a
        ld a,e
        or 7
        ld e,a
.byte:  ld bc,8
        DUP 8
        ldd
        EDUP
        call read_unwrap
        call write_unwrap
        dec ix
        ld a,ixl
        and 31
        call z,row_irq_poll
        ld a,ixh
        or ixl
        jr nz,.byte
        pop ix
        ret
read_unwrap:
        bit 6,h
        ret nz
        set 6,h
        res 5,h
        ld a,(read_page)
        dec a
        ld (read_page),a
        nextreg 0x56,a
        ret

edge_copy:
        call copy_setup
        ld a,4
        ld (mut_rows),a
.row:   ld bc,8
        DUP 8
        ldi
        EDUP
        call read_wrap
        call write_wrap
        ld bc,8
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        call read_wrap
        call write_wrap
        call row_irq_poll
        ld a,(mut_rows)
        dec a
        ld (mut_rows),a
        jr nz,.row
        ret

crop_door:
        ld a,(0x3EE9)
        dec a                   ; the original entry jumps to DJNZ first
        ret z
        ld (mut_rows),a
        ld a,252
        ld (mut_mask),a
        ld hl,(0x3EE6)
        call shadow_read
        push hl
        ld hl,(0x3EE4)
        call shadow_write
        ex de,hl
        pop hl
.row:   ld a,(mut_mask)
        ld c,a
        ld b,8
.pixel: rlc c
        jr c,.keep
        ld (hl),0
        ld a,255
        ld (de),a
.keep:  inc hl
        inc de
        call read_wrap
        call write_wrap
        djnz .pixel
        ld bc,16
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        call read_wrap
        call write_wrap
        call row_irq_poll
        ld a,(mut_mask)
        add a,a
        add a,a
        ld (mut_mask),a
        ld a,(mut_rows)
        dec a
        ld (mut_rows),a
        jr nz,.row
        ret

; All columns address the original B800-B8FF ring. Its expanded counterpart
; is the 2048-byte private buffer at2000, so wrap at2800, not an MMU boundary.
clear_column_one:
        ld a,1
        jr clear_column_start
clear_column_two:
        ld a,2
clear_column_start:
        ld (col_width),a
        xor a
        ld (col_mode),a
        ld hl,(0x3EE0)          ; original alternate DE
        call column_dest
        ld a,(0x3EED)
        jp column_run
stored_column_one:
        ld a,1
        jr stored_column_start
stored_column_two:
        ld a,2
stored_column_start:
        ld (col_width),a
        ld a,1
        ld (col_mode),a
        ld hl,(0x3EE4)
        ld (col_source),hl
        ld hl,(0x3EE6)
        call column_dest
        ld a,(0x3EED)
        jr column_run
tiled_column_one:
        ld a,1
        jr tiled_column_start
tiled_column_two:
        ld a,2
tiled_column_start:
        ld (col_width),a
        ld a,2
        ld (col_mode),a
        ld hl,(0x3EE8)
        ld (col_base),hl
        ld a,(0x3EED)
        ld (col_offset),a
        ld hl,(0x3EE6)
        call column_dest
        ld a,(0x3EE3)           ; original alternate B
        jr column_run
ui_pixels:
        ld a,(0x3EE8)
        ld (col_width),a
        ld a,3
        ld (col_mode),a
        ld hl,(0x3EE6)
        ld (col_source),hl
        xor a
        ld (render_text),a
        ld a,(0x3EE5)           ; UI's one-byte, eight-row tiles are text
        cp 8
        jr nz,.source
        ld a,(col_width)
        cp 1
        jr z,.text
.source:
        ld a,h
        cp 0xB6
        jr nz,.static
        ld a,l
        sub 0x6D
        cp 16
        jr nc,.static
.text:
        ld a,1
        ld (render_text),a
.static:
        ld hl,0x2000
        ld (col_dest),hl
        ld a,(0x3EE5)           ; original H is the UI height
column_run:
        ld (col_rows),a
.row:  ld a,(col_mode)
        or a
        jr z,.clear
        cp 2
        jr nz,.stored
        ld hl,(col_base)
        ld a,(col_offset)
        ld c,a
        ld b,0
        add hl,bc
        jr .source
.stored:
        ld hl,(col_source)
.source:
        call shadow_read
        ld de,(col_dest)
        ld a,(col_width)
        ld (col_left),a
.byte: ld bc,8
        DUP 8
        ldi
        EDUP
        res 3,d
        call read_wrap
        ld a,(col_left)
        dec a
        ld (col_left),a
        jr nz,.byte
        jr .next
.clear:
        ld hl,(col_dest)
        ld a,(col_width)
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.zero: ld (hl),a
        inc hl
        res 3,h
        djnz .zero
.next: call row_irq_poll
        ld hl,(col_dest)
        ld bc,48
        add hl,bc
        res 3,h
        ld (col_dest),hl
        ld a,(col_mode)
        cp 2
        jr z,.tile
        cp 3
        ld a,2
        jr nz,.step
        ld a,(col_width)
.step: ld c,a
        ld b,0
        ld hl,(col_source)
        add hl,bc
        ld (col_source),hl
        jr .count
.tile: ld a,(col_offset)
        add a,2
        and 31
        ld (col_offset),a
.count:
        ld a,(col_rows)
        dec a
        ld (col_rows),a
        jp nz,.row
        ret
column_dest:
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        set 5,h
        ld (col_dest),hl
        ret
render_begin:
        xor a
        ld (render_text),a
        ret
; Index71 and63 are identical yellow in the supplied palette. Index71 is
; reserved for transparent original text; painted71 is remapped to63 only
; during presentation, after all source mask arithmetic is complete.
display_copy:
        ld hl,(0xA052)
        ld a,h
        sub 64
        add a,a
        ld (display_x),a
        ld a,l
        sub h
        srl a
        srl a
        and 7
        ret z
        add a,a
        add a,a
        add a,a
        ld (display_width),a
        ld hl,(0xA054)
        ld a,l
        sub h
        ret z
        ld (display_rows),a
        ld a,(0x940B)            ; 0 for UI,72 for room coordinates
        ld b,a
        ld a,h
        sub b
        ld (display_y),a
        ld hl,0x2000
        ld (display_source),hl
.row:  ld a,(display_y)
        ld d,a
        and 31
        or 0xC0
        ld e,a
        ld a,d
        srl a
        srl a
        srl a
        srl a
        srl a
        add a,L2_PAGE
        nextreg 0x56,a
        ld d,e
        ld a,(display_x)
        ld e,a
        ld hl,(display_source)
        ld a,(display_width)
        ld b,a
        ld a,(render_text)
        or a
        jr nz,.text
.pixel:
        ld a,(hl)
        inc hl
        res 3,h
        cp 71
        jr nz,.put
        ld a,63
.put:  ld (de),a
        inc e
        djnz .pixel
        jr .next
.text: ld a,71
.fill: ld (de),a
        inc e
        djnz .fill
.next: call row_irq_poll
        ld hl,(display_source)
        ld bc,48
        add hl,bc
        res 3,h
        ld (display_source),hl
        ld hl,display_y
        inc (hl)
        ld hl,display_rows
        dec (hl)
        jp nz,.row
        ret
display_clear:
        ld a,L2_PAGE
.page: ld (display_y),a
        nextreg 0x56,a
        ld hl,0xC000
        ld de,0xC001
        ld bc,8191
        ld (hl),71
        ldir
        call row_irq_poll
        ld a,(display_y)
        inc a
        cp L2_PAGE+6
        jr nz,.page
        ret
mutation_end:
        ASSERT mutation_end < 0x1E00
shift_amount EQU 0x1F00
shift_width EQU 0x1F01
shift_height EQU 0x1F02
shift_remaining EQU 0x1F03
shift_pad EQU 0x1F04
read_page EQU 0x1F05
write_page EQU 0x1F06
mirror_width EQU 0x1F07
mirror_address EQU 0x1F08
mirror_left EQU 0x1F0A
mirror_remaining EQU 0x1F0C
mut_rows EQU 0x1F16
mut_mask EQU 0x1F1A
col_width EQU 0x1F20
col_mode EQU 0x1F21
col_rows EQU 0x1F22
col_source EQU 0x1F23
col_dest EQU 0x1F25
col_base EQU 0x1F27
col_offset EQU 0x1F29
col_left EQU 0x1F2A
render_text EQU 0x3738
render_active EQU 0x3736
render_speed EQU 0x3737
display_x EQU 0x1F30
display_y EQU 0x1F31
display_width EQU 0x1F32
display_rows EQU 0x1F33
display_source EQU 0x1F34
        SAVEBIN "hoh_mutation.bin",shift_pixels,mutation_end-shift_pixels

; Keep the game's four-IRQ limiter. This shared-library floor protects the
; measured quiet pace without adding a second four-frame wait:1220 lines is
; 79.48ms at128K timing, below the original81.04ms update but within2% of it.
; Busy rendering may take longer; it never earns debt against the next update.
HLIB_V_PACE EQU 0x3740
HLIB_PACE_NL EQU 311
pace_start_held EQU 0x375A
        ORG 0x1600
pace_library:
        INCLUDE "lib/hlib_pace.asm"
pace_player:
        ld a,(HLIB_V_PACE+10)
        or a
        jr z,.open
        ld hl,0
        ld (HLIB_V_PACE+4),hl
        ld hl,(HLIB_V_PACE+14)
        ld de,(pace_start_held)
        and a
        sbc hl,de
        ex de,hl
        ld hl,1220
        and a
        sbc hl,de
        jr nc,.target
        ld hl,0
.target:
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        xor a                   ; frame cap is real-time at every caller clock
        call hlib_pace_wait
.open: call hlib_pace_open
        ld hl,(HLIB_V_PACE+14)
        ld (pace_start_held),hl
        ret
pace_library_end:
        ASSERT pace_library_end < 0x1E00
        SAVEBIN "hoh_pace.bin",pace_library,pace_library_end-pace_library
