; The Great Escape: native buffer companion. Game memory and drawing are retained.
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
V_MMU3          EQU 0x3E06
V_IFF           EQU 0x3E08
HLIB_V_R        EQU 0x3E0A
V_RETSP         EQU 0x3E10
V_RETURN        EQU 0x3E12
V_TARGET        EQU 0x3E14
V_RDELTA        EQU 0x3E16
V_NATIVE        EQU 0x3E17
V_BALL          EQU 0x3E1A          ; cooler ball step (page 24, starts 0)
BALL_STEPS      EQU 20
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
        MACRO ENTRY number
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        ld a,number
        jp hook_enter
        ENDM
        ORG 0x1800
library_start:
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
library_end:
        ASSERT library_end <= 0x1C00
        SAVEBIN "ge_library.bin",library_start,library_end-library_start

        ORG 0x3A80
resident_start:
h_tile_out:      ENTRY 0
h_tile_in:       ENTRY 1
h_tile_dirty:    ENTRY 2
h_scroll_r:      ENTRY 3
h_scroll_l:      ENTRY 4
h_scroll_dr:     ENTRY 5
h_scroll_d:      ENTRY 6
h_scroll_u:      ENTRY 7
h_scroll_ul:     ENTRY 8
h_figure16:      ENTRY 9
h_figure24:      ENTRY 10
h_item:          ENTRY 11
h_publish:       ENTRY 12
h_frame_end:     ENTRY 13
h_searchlight:   ENTRY 14
h_dialog:       ENTRY 15
hook_enter:
        ld (V_KIND),a
        HLIB_R_IN
        ; Original AF is already saved by ENTRY; only BC needs preserving here.
        push bc
        HLIB_SPEED_IN_ABC V_CLOCK
        pop bc
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
        dec b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (V_MMU3),a
        nextreg 0x50,26
        jp dispatch
native_exit:
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        HLIB_R_IN
        SAVE_REGS
        nextreg 0x50,26
        jp after_native
finish_resident:
        ld a,(V_MMU3)
        nextreg 0x53,a
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
launch_resident:
        ld a,(V_MMU3)
        nextreg 0x53,a
        ld a,(V_MMU2)
        nextreg 0x52,a
        ld a,(V_MMU0)
        nextreg 0x50,a
        RESTORE_REGS
        HLIB_R_OUT
        ld sp,(V_SP)
launch_jump:
        jp 0
native_block:
        ldir
        jp native_exit
; The cooler ball's sprite positions (X, Y; the screen's top left is 32,32): thrown from McQueen's hand at the
; cell's right wall and caught, 20 steps, the last four in the glove. nexclash/great_escape.py BALL_PATH matches.
ball_path:
        db 162,109, 166,106, 169,103, 172,101, 175,100, 178,100, 182,100, 185,101
        db 182,101, 178,102, 175,103, 172,104, 169,106, 166,108, 162,110, 159,113
        db 159,113, 159,113, 159,113, 159,113
resident_end:
        ASSERT resident_end <= 0x3D00
        SAVEBIN "ge_resident.bin",resident_start,resident_end-resident_start

        ORG 0x0000
code_start:
dispatch:
        ld a,(V_KIND)
        cp 3
        jp c,tile_hook
        cp 9
        jp c,scroll_hook
        cp 12
        jp c,figure_hook
        jp z,publish_hook
        cp 13
        jp z,frame_end_hook
        cp 14
        jp z,searchlight_hook
        jp dialog_hook
set_finish:
        ld (finish_jump+1),hl
        ld a,(V_RDELTA)
        call hlib_r_set
        jp finish_resident
set_launch:
        ld (launch_jump+1),hl
        ld a,(V_RDELTA)
        call hlib_r_set
        jp launch_resident
; Native subroutines keep their own exact stack. Only their top return word is
; temporarily redirected, then restored before rejoining the caller.
redirect_return:
        ld hl,(V_SP)
        ld (V_RETSP),hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_RETURN),de
        ld de,native_exit
        ld (hl),d
        dec hl
        ld (hl),e
        ret

tile_hook:
        call hlib_debt_open
        ld a,(V_KIND)
        cp 2
        jp z,dirty_prefix
.ready:
        call draw_tile
        ld a,(V_KIND)
        or a
        jr nz,.inside
        RESTORE_REGS
        ld bc,24
        ld a,8
.out_loop:
        ex af,af'
        ld a,(de)
        ld (hl),a
        add hl,bc
        inc e
        ex af,af'
        dec a
        jp nz,.out_loop
        jr .saved
.inside:
        RESTORE_REGS
        ld bc,0x0818
.in_loop:
        ld a,(hl)
        ld (de),a
        ld a,c
        add a,e
        jr nc,.no_carry
        inc d
.no_carry:
        ld e,a
        inc l
        djnz .in_loop
.saved: push af
        SAVE_REGS
        ; Native eight-row copy ran unchanged at 28 MHz. Its original time is
        ; credited against the extra work, including the slow entry and exit.
        ld a,(V_KIND)
        ld hl,tile_overhead_in
        or a
        jr nz,.dirty_cost
        ld hl,tile_overhead_out
        jr .cost
.dirty_cost:
        cp 2
        jr nz,.cost
        ld hl,tile_overhead_dirty
.cost:  ld a,(V_CLOCK)
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        call hlib_debt_close
        call dirty_credit
        ld a,(V_KIND)
        add a,a
        ld e,a
        ld d,0
        ld hl,tile_returns
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld a,(V_KIND)
        or a
        ld a,50
        jr z,.r
        ld a,(tile_native_dest)
        cp 64
        ld a,49
        jr c,.r
        inc a
.r:     ld (V_RDELTA),a
        push hl
        call dirty_r
        pop hl
        jp set_finish
tile_returns: dw 0xA9DF,0x6B68,0xBC7F
tile_overhead_out: db 10,14,16,17
tile_overhead_in: db 9,14,16,17
tile_overhead_dirty: db 11,16,19,20

scroll_hook:
        call hlib_pace_open
        ld a,(V_KIND)
        sub 3
        add a,a
        ld e,a
        ld d,0
        ld hl,scroll_targets
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_TARGET),de
        call scroll_canvas
        ld a,(V_KIND)
        sub 3
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,scroll_table
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (R_BC),de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_RETURN),hl
        ld a,(V_KIND)
        cp 4
        jr z,.back
        cp 7
        jr nc,.back
        ld a,0xB0
        jr .op
.back: ld a,0xB8
.op:   ld (native_block+1),a
        ; Original LD BC precedes the native block. Variable M1s execute unchanged.
        ld a,0xF2
        ld (V_RDELTA),a
        ld a,1
        ld (V_NATIVE),a
        ld hl,native_block
        jp set_launch
scroll_targets: dw 4895,4896,4608,4608,4608,4607
scroll_table: dw 3263,0xAA01,3264,0xAA22,3072,0xAA44,3072,0xAA68,3072,0xAA89,3071,0xAAAB

figure_hook:
        call hlib_pace_open
        call draw_figure
        call redirect_return
        xor a
        ld (V_NATIVE),a
        ld a,(V_KIND)
        cp 11
        jr z,.item
        ld iy,(R_IY)
        ld a,(iy+24)
        and 7
        push af
        pop hl
        ld (R_AF),hl
        ld hl,0xE2A7
        ld a,(V_KIND)
        cp 10
        jr nz,.ready
        ld hl,0xE107
.ready: ld a,0xF4
        ld (V_RDELTA),a
        jp set_launch
.item:  xor a
        push af
        pop hl
        ld (R_AF),hl
        ld hl,0xE2AC
        ld a,0xF3
        ld (V_RDELTA),a
        jp set_launch

publish_hook:
        call hlib_pace_open
        ld a,(0xA7C8)
        or a
        ; Native ULA writes contend at 3.5MHz. Original-only JNext means are
        ; 57460T aligned and 202202T shifted. The aligned whole-hook budget is
        ; calibrated to 53200T across stationary AND moving player-update tests:
        ; 51086T was >2% fast stationary; the full mean was >2% slow moving.
        ld hl,3800
        jr z,.target
        ld hl,14443
.target: ld (V_TARGET),hl
        call redirect_return
        xor a
        ld (V_NATIVE),a
        ld hl,(V_SP)
        ld (0xEDD1),hl
        ld hl,0xEED7
        ld a,0xF3
        ld (V_RDELTA),a
        jp set_launch

frame_end_hook:
        call hlib_debt_open
        call cooler_ball
        call publish_canvas
        nextreg 0x69,0x80
        call overhead
        add a,7
        call hlib_debt_close
        ; Execute the original CALL A035 exactly: its original return word and SP.
        ld hl,(V_SP)
        dec hl
        ld (hl),0x9D
        dec hl
        ld (hl),0xC5
        ld (V_SP),hl
        ld a,0xF1
        ld (V_RDELTA),a
        ld hl,0xA035
        jp set_finish


after_native:
        ld a,(V_NATIVE)
        or a
        jr nz,.block
        ld hl,(V_RETSP)
        ld de,(V_RETURN)
        ld (hl),e
        inc hl
        ld (hl),d
        ld a,0xF4
        jr .delta
.block: ld a,0xF3
.delta: ld (V_RDELTA),a
        call overhead
        ld l,a
        ld h,0
        call hlib_debt_add
        ; Original time is supplied by the build's checked native timing table.
        ld hl,(V_TARGET)
        ld a,(V_CLOCK)
        call hlib_pace_wait
        ld hl,(V_RETURN)
        jp set_finish

 ; Native source cache: the external build maps only verified graphic pages.
; Contextual tiles have their own 4096-entry lookup in page86. Both paths return
; HL in slot3 and source_page. A dark copy lives exactly 22 pages later.
map_source:
        ld a,h
        srl a
        srl a
        ld e,a
        ld d,0
        push hl
        ld hl,0x1D80
        add hl,de
        ld a,(hl)
        ld (source_page),a
        nextreg 0x53,a
        pop hl
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 5,h
        set 6,h
        ret
map_world:
        ; HL = world block * 16 + subcell, never an assumed graphic address.
        add hl,hl
        set 5,h
        set 6,h
        nextreg 0x53,86
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld a,h
        add a,a
        bit 7,l
        jr z,.page
        inc a
.page:  add a,42
        ld (source_page),a
        nextreg 0x53,a
        ld a,l
        and 127
        ld l,a
        ld h,0
        DUP 6
        add hl,hl
        EDUP
        set 5,h
        set 6,h
        ret
map_canvas:
        ld a,h
        rlca
        rlca
        rlca
        and 3
        add a,34
        ld (canvas_page),a
        nextreg 0x52,a
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        ret
buffer_offset:
        ld de,0xF290
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ret

draw_tile:
        ld hl,(R_DE)
        ld a,(V_KIND)
        or a
        jr nz,.destination
        ld hl,(R_HL)
.destination:
        ld (tile_native_dest),hl
        call buffer_offset
        ld (destination),hl
        ld a,(V_KIND)
        or a
        jr nz,.indoor
        ld hl,(R_DE_ALT)
        ld a,h
        cp 0x5B
        jr c,.alternate
        cp 0x6B
        jr c,.world_pointer
.alternate:
        ld hl,(R_HL_ALT)
.world_pointer:
        ld de,0x5B00
        or a
        sbc hl,de
        call map_world
        jr .ready
.indoor:
        cp 1
        jr z,.native
        ld a,(0x68A0)
        or a
        jr nz,.native
        ld hl,(V_SP)
        ld a,(0x81BC)
        add a,(hl)
        and 3
        add a,a
        add a,a
        ld e,a
        inc hl
        ld a,(0x81BB)
        add a,(hl)
        and 3
        or e
        ld e,a
        ld d,0
        ld a,(R_AF_ALT+1)
        ld l,a
        ld h,0
        DUP 4
        add hl,hl
        EDUP
        add hl,de
        call map_world
        jr .ready
.native:
        ld hl,(R_HL)
        call map_source
.ready: ld (source),hl
        call tile_cache
        ret z
        jr nc,.marked
        ld hl,(tile_native_dest)
        ld bc,0x0801
        call mark_rectangle
.marked:
        call init_dma
        call hlib_dma_backend
        cp 2
        jp z,tile_ddma
        ld a,34
        ld (tile_base),a
        call tile_rows
        ld a,(source_page)
        add a,22
        nextreg 0x53,a
        ld a,38
        ld (tile_base),a
        ; Copy the precomputed dark pixels; no per-pixel arithmetic in this path.
        jp tile_rows
tile_rows:
        ld hl,(destination)
        call map_canvas
        ld a,(tile_base)
        cp 38
        jr nz,.mapped
        ld a,(canvas_page)
        add a,4
        ld (canvas_page),a
        nextreg 0x52,a
.mapped:
        ex de,hl
        ld hl,(source)
        ; Tiny 8-byte rows cost less as LDI than a DMA setup. The source is a
        ; contiguous cached tile. Only an actual 8K destination crossing remaps.
        DUP 8
        DUP 8
        ldi
        EDUP
        ld a,184
        add de,a
        call pixel_wrap
        EDUP
        ret
tile_ddma:
        ld a,(source_page)
        ld b,a
        and 7
        rrca
        rrca
        rrca
        ld h,a
        ld l,0
        ld de,(source)
        res 5,d
        res 6,d
        add hl,de
        ld (tile_packet_source),hl
        ld a,b
        srl a
        srl a
        srl a
        ld (tile_packet_source_high),a
        ld hl,(destination)
        ld de,0x4000
        add hl,de
        ld (tile_packet_dest),hl
        ld a,4
        adc a,0
        ld (tile_packet_dest_high),a
        call tile_send
        ld hl,(tile_packet_source)
        ld de,0xC000
        add hl,de
        ld (tile_packet_source),hl
        ld a,(tile_packet_source_high)
        adc a,2
        ld (tile_packet_source_high),a
        ld hl,(tile_packet_dest)
        ld de,0x8000
        add hl,de
        ld (tile_packet_dest),hl
        ld a,(tile_packet_dest_high)
        adc a,0
        ld (tile_packet_dest_high),a
tile_send:
        ld hl,tile_packet
        ld bc,(tile_packet_end-tile_packet)*256+0x6B
        otir
        ret
tile_packet:
        db 0x83,0xC3,0x7D
tile_packet_source: dw 0
        dw 0
        db 0x14,0x10,0xAD
tile_packet_dest: dw 0
        db 0x82,0xD7
tile_packet_source_high: db 0
        db 0xDB
tile_packet_dest_high: db 0
        db 0xDF,3,0xE3
        dw 8
        db 0xE7
        dw 8
        db 0xEB
        dw 8
        db 0xEF
        dw 192
        db 0xCF,0x87
tile_packet_end:
source_page: db 0
tile_source: dw 0
tile_dest: dw 0
tile_base: db 0

; Physical source/destination page bases plus 16-bit offsets. Split only at 8K
; boundaries; a transfer never crosses the mappings that were selected for it.
copy_pages:
.loop:  ld hl,(copy_left)
        ld a,h
        or l
        ret z
        ld hl,(copy_source)
        ld a,h
        and 0x1F
        ld h,a
        ld de,8192
        ex de,hl
        or a
        sbc hl,de
        ld (copy_chunk),hl
        ld hl,(copy_dest)
        ld a,h
        and 0x1F
        ld h,a
        ld de,8192
        ex de,hl
        or a
        sbc hl,de
        ld de,(copy_chunk)
        push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.remain
        ld (copy_chunk),hl
.remain:
        ld hl,(copy_left)
        ld de,(copy_chunk)
        or a
        sbc hl,de
        jr nc,.map
        ld hl,(copy_left)
        ld (copy_chunk),hl
.map:   ld hl,(copy_source)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(copy_source_base)
        add a,b
        nextreg 0x53,a
        ld a,h
        and 31
        or 0x60
        ld h,a
        push hl
        ld hl,(copy_dest)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(copy_dest_base)
        add a,b
        nextreg 0x52,a
        ld a,h
        and 31
        or 0x40
        ld h,a
        ex de,hl
        pop hl
        ld bc,(copy_chunk)
        call copy_block
        ld bc,(copy_chunk)
        ld hl,(copy_source)
        add hl,bc
        ld (copy_source),hl
        ld hl,(copy_dest)
        add hl,bc
        ld (copy_dest),hl
        ld hl,(copy_left)
        or a
        sbc hl,bc
        ld (copy_left),hl
        jp .loop

copy_block:
        ld a,b
        or a
        jr nz,.dma
        ld a,c
        cp 21
        jr c,.cpu
.dma:
        ld (hlib_dma_row_src),hl
        ld (hlib_dma_row_dst),de
        ld (hlib_dma_row_len),bc
        call hlib_dma_backend
        or a
        jr z,.cpu_long
        ld hl,hlib_dma_row
        ld bc,(hlib_dma_row_end-hlib_dma_row)*256+0x6B
        otir
        ret
.cpu:   ldir
        ret
.cpu_long:
        ldir
        ; Long CPU copies can span several video frames. Account every <=8K
        ; chunk so the shared limiter never loses an unseen raster wrap.
        ld a,(HLIB_V_PACE+10)
        or a
        jp nz,hlib_pace_tick
        jp hlib_debt_tick

init_dma:
        ld a,(dma_ready)
        or a
        ret nz
        inc a
        ld (dma_ready),a
        jp hlib_dma_init

scroll_canvas:
        call clear_tile_cache
        ld a,1
        ld (dirty_full),a
        call init_dma
        ld a,(V_KIND)
        sub 3
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,scroll_table
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (scroll_count),de
        ld hl,(R_HL)
        ld a,(V_KIND)
        cp 4
        jr z,.back
        cp 7
        jr c,.forward
.back:  or a
        sbc hl,de
        inc hl
.forward:
        call buffer_offset
        ld (scroll_source),hl
        ld hl,(R_DE)
        ld a,(V_KIND)
        cp 4
        jr z,.back2
        cp 7
        jr c,.forward2
.back2: ld de,(scroll_count)
        or a
        sbc hl,de
        inc hl
.forward2:
        call buffer_offset
        ld (scroll_dest),hl
        ld hl,(scroll_count)
        add hl,hl
        add hl,hl
        add hl,hl
        ld (scroll_size),hl
        ld a,34
        ld (scroll_base),a
.pass:  ld a,(scroll_base)
        ld (copy_source_base),a
        ld a,90
        ld (copy_dest_base),a
        ld hl,(scroll_source)
        ld (copy_source),hl
        ld hl,0
        ld (copy_dest),hl
        ld hl,(scroll_size)
        ld (copy_left),hl
        call copy_pages
        ld a,90
        ld (copy_source_base),a
        ld a,(scroll_base)
        ld (copy_dest_base),a
        ld hl,0
        ld (copy_source),hl
        ld hl,(scroll_dest)
        ld (copy_dest),hl
        ld hl,(scroll_size)
        ld (copy_left),hl
        call copy_pages
        ld a,(scroll_base)
        add a,4
        ld (scroll_base),a
        cp 42
        jr nz,.pass
        ret

; The native clipping tests decide whether each destination byte is written.
; Pixel masks use the original foreground plane (low-byte wrapping), source mask
; and phase. Colour has no influence on gameplay or on coverage.
prepare_figure:
        xor a
        ld (role_base),a
        ld a,(0x3E19)
        or a
        jr z,.role_done
        ld a,(V_KIND)
        cp 11
        jr nz,.person
        ld iy,(R_IY)
        ld a,(iy+0)
        sub 9
        cp 3
        jr nc,.role_done
        add a,a
        add a,a
        add a,a
        add a,104
        jr .role_store
.person:
        ld hl,(0x81AC)
        ld de,0xD1EA
        or a
        sbc hl,de
        jr c,.role_done
        ld de,0x026B
        or a
        sbc hl,de
        jr nc,.role_done
        ld iy,(R_IY)
        ld a,(iy+0)
        or a
        jr nz,.prisoner
        ld a,(0x3E18)
        or a
        jr z,.role_done
        ld a,56
        jr .role_store
.prisoner:
        sub 20
        cp 6
        jr nc,.role_done
        inc a
        add a,a
        add a,a
        add a,a
.role_store:
        ld (role_base),a
.role_done:
        ld hl,(0x81AC)
        ld (bitmap),hl
        ld hl,(0x81AE)
        ld (mask),hl
        ld hl,(0x81B0)
        ld (foreground),hl
        ld hl,(0x81A2)
        call buffer_offset
        ld (destination),hl
        ld iy,(R_IY)
        ld a,(iy+24)
        and 7
        ld b,a
        ld a,(V_KIND)
        cp 11
        jr nz,.phase
        ld b,0
.phase: ld a,b
        ld (phase),a
        cp 4
        ld hl,clip16r
        ld a,(0xE2C2)
        jr c,.height16
        ld hl,clip16l
        ld a,(0xE363)
.height16:
        ld (rows_left),a
        ld a,16
        ld (width),a
        ld a,2
        ld (stride),a
        ld a,(V_KIND)
        cp 10
        jr nz,.clip
        ld a,24
        ld (width),a
        ld a,3
        ld (stride),a
        ld a,(phase)
        cp 4
        ld hl,clip24r
        ld a,(0xE121)
        jr c,.height24
        ld hl,clip24l
        ld a,(0xE1E2)
.height24:
        ld (rows_left),a
.clip:  ld de,clip_flags
        ld b,4
.c:     ld a,(hl)
        inc hl
        push hl
        ld h,(hl)
        ld l,a
        ld a,(hl)
        pop hl
        inc hl
        ld (de),a
        inc de
        djnz .c
        ld a,(stride)
        ld b,a
        ld a,(phase)
        or a
        jr z,.clip_count
        inc b
.clip_count:
        ld a,b
        ld (foreground_bytes),a
        ld hl,clip_flags
        ld a,0x77
.clip_all:
        and (hl)
        inc hl
        djnz .clip_all
        ld (foreground_fullclip),a
        ld a,(0x81B7)
        and 128
        ld (mirrored),a
        ld hl,(0x81A2)
        ld a,(rows_left)
        ld b,a
        ld a,(stride)
        ld c,a
        ld a,(phase)
        or a
        jr z,.mark_width
        inc c
.mark_width:
        call mark_rectangle
        ; The original plot's exact row/constant costs are verified independently.
        ld b,3
        ld a,(stride)
        cp 3
        jr nz,.count
        inc b
.count: ld hl,clip_flags
        ld c,0
.store: ld a,(hl)
        cp 0x77
        jr nz,.skip
        inc c
.skip:  inc hl
        djnz .store
        ld a,c
        DUP 5
        add a,a
        EDUP
        ld l,a
        ld a,(rows_left)
        dec a
        or l
        ld l,a
        ld a,(phase)
        ld h,a
        ld a,(mirrored)
        or a
        jr z,.width
        set 3,h
.width: ld a,(stride)
        cp 3
        jr nz,.table
        set 4,h
.table: add hl,hl
        ld a,h
        and 0x20
        ld a,88
        jr z,.page
        inc a
.page:  nextreg 0x53,a
        ld a,h
        and 31
        or 96
        ld h,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(V_KIND)
        cp 11
        jr nz,.target
        dec de
        dec de
.target: ld (V_TARGET),de
        ret
        MACRO SELECT_PIXELS forward_entry, reverse_entry, forward_cross_entry, reverse_cross_entry
        ld hl,forward_entry
        ld a,(mirrored)
        or a
        jr z,.kernel
        ld hl,reverse_entry
.kernel:
        ld a,d
        cp 0x5F
        jr nz,.safe
        ld a,e
        cp 0xE0
        jr c,.safe
        ld hl,forward_cross_entry
        ld a,(mirrored)
        or a
        jr z,.safe
        ld hl,reverse_cross_entry
.safe:  ld (pixels_call+1),hl
        ENDM
draw_figure:
        call prepare_figure
        ld bc,0x243B
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        ld (figure_mmu4),a
.row:   ld a,(figure_mmu4)
        nextreg 0x54,a
        call prepare_foreground
        ld ix,(bitmap)
        ld iy,(mask)
        ld a,(mirrored)
        or a
        jr z,.source
        ld a,(stride)
        dec a
        ld e,a
        ld d,0
        add ix,de
        add iy,de
.source:
        push ix
        pop hl
        call map_source
        ld a,(source_page)
        ld (figure_source_page),a
        nextreg 0x54,a
        ld a,h
        and 31
        or 128
        ld h,a
        ld a,(mirrored)
        or a
        jr z,.cache
        ld de,7
        add hl,de
.cache: ld (pixel_source),hl
        ld hl,(destination)
        ld a,(phase)
        add hl,a
        call map_canvas
        ex de,hl
        ld a,(canvas_page)
        add a,4
        nextreg 0x53,a
.select: SELECT_PIXELS pixels_forward,pixels_reverse,pixels_forward_cross,pixels_reverse_cross
.select_end:
        ld hl,(pixel_source)
        xor a
        ld (byte_index),a
.byte:  ld a,(ix+0)
        ld b,a
        ld a,(iy+0)
        cpl
        or b
        ld b,a
        ld a,(mirrored)
        or a
        ld a,b
        jr z,.coverage
        mirror a
.coverage:
        ld b,a
        push hl
        ld hl,aligned_fg
        ld a,(byte_index)
        add hl,a
        ld a,(hl)
        and b
        pop hl
        ld b,a
        ld a,(role_base)
        ld c,a
        call pixels_call
        ; Source pages are contiguous within the verified five-page actor run.
        ; A row can straddle a page; the eight-colour byte itself never does.
        ld a,h
        cp 0xA0
        jr c,.under
        ld h,0x80
        ld a,(figure_source_page)
        inc a
        jr .mapped
.under: cp 0x80
        jr nc,.pointers
        ld h,0x9F
        ld a,(figure_source_page)
        dec a
.mapped:
        ld (figure_source_page),a
        nextreg 0x54,a
.pointers:
        ld a,(mirrored)
        or a
        jr nz,.previous
        inc ix
        inc iy
        jr .next
.previous:
        dec ix
        dec iy
.next:  ld a,(byte_index)
        inc a
        ld (byte_index),a
        push hl
        ld hl,stride
        cp (hl)
        pop hl
        jp nz,.byte
        ld a,(stride)
        ld e,a
        ld d,0
        ld hl,(bitmap)
        add hl,de
        ld (bitmap),hl
        ld hl,(mask)
        add hl,de
        ld (mask),hl
        ld hl,(foreground)
        ld a,l
        add a,4
        ld l,a
        ld (foreground),hl
        ld hl,(destination)
        ld de,192
        add hl,de
        ld (destination),hl
        ld a,(rows_left)
        dec a
        ld (rows_left),a
        jp nz,.row
        ld a,(figure_mmu4)
        nextreg 0x54,a
        ret
figure_source_page: db 0
pixels_call:
        jp pixels_forward
pixel_wrap:
        bit 5,d
        ret z
        res 5,d
        ld a,(canvas_page)
        inc a
        ld (canvas_page),a
        nextreg 0x52,a
        ret
pixel_dual_wrap:
        bit 5,d
        ret z
        res 5,d
        ld a,(canvas_page)
        inc a
        cp 38
        jr nz,.page
        ld a,34
.page:
        ld (canvas_page),a
        nextreg 0x52,a
        add a,4
        nextreg 0x53,a
        ret
        ; The optional kernel takes advantage of OR C setting sign. Outfit/key
        ; bases and ordinary bright colours all have bit 7 clear.
        MACRO PAINT_PIXEL step,masked,check_halo
        IF masked
        rlc b
        jr nc,.advance
        ENDIF
        ld a,(hl)
        or c
        IF check_halo
        jp m,.advance
        ENDIF
        ld (de),a
        or 128
        set 5,d
        ld (de),a
        res 5,d
.advance:
        step hl
        inc de
        ENDM

        MACRO PIXEL_KERNEL step,empty_entry,full_entry,check_halo
        ld a,b
        or a
        jp z,empty_entry
        cp 255
        jp z,full_entry
@.masked:
        DUP 8
        PAINT_PIXEL step,1,check_halo
        EDUP
        ret
        ENDM
        MACRO FULL_KERNEL step,check_halo
        DUP 8
        PAINT_PIXEL step,0,check_halo
        EDUP
        ret
        ENDM
        MACRO CROSS_KERNEL step,check_halo
        IF check_halo
        ; Reuse four pixels twice on these rare wrapped rows to fit the overlay.
        call .four
.four:
        ENDIF
        DUP 8/(1+check_halo)
        call pixel_dual_wrap
        PAINT_PIXEL step,1,check_halo
        EDUP
        ret
        ENDM
pixels_forward:       PIXEL_KERNEL inc,pixels_empty_forward,pixels_full_forward,0
pixels_reverse:       PIXEL_KERNEL dec,pixels_empty_reverse,pixels_full_reverse,0
pixels_full_forward:  FULL_KERNEL inc,0
pixels_full_reverse:  FULL_KERNEL dec,0
pixels_forward_cross: CROSS_KERNEL inc,0
pixels_reverse_cross: CROSS_KERNEL dec,0
figure_mmu4: db 0
clip16r: dw 0xE319,0xE32A,0xE340,0xE340
clip16l: dw 0xE3C5,0xE3D6,0xE3EC,0xE3EC
clip24r: dw 0xE188,0xE199,0xE1AA,0xE1BF
clip24l: dw 0xE259,0xE26A,0xE27B,0xE290
bit_masks: db 128,64,32,16,8,4,2,1
 ; A tag describes a clean 8x8 canvas tile, not merely a repeated source.
; Every actor footprint invalidates covered tags. Scrolls invalidate all tags.
; Tags are in private RAM 1400..172F, initially zero; source keys are never zero.
tile_cache:
        ld hl,(source)
        ld a,l
        rlca
        rlca
        and 3
        ld e,a
        ld a,h
        and 31
        add a,a
        add a,a
        or e
        ld e,a
        ld a,(source_page)
        srl a
        ld d,a
        jr nc,.key
        set 7,e
.key:   ld (tile_key),de
        ld hl,(tile_native_dest)
        ld de,0xF290
        or a
        sbc hl,de
        call canvas_band
        ld c,a
        ld a,h
        or a
        jr nz,.uncached
        ld a,l
        cp 24
        jr nc,.uncached       ; non-aligned producer: never reuse a partial tile
        ld b,l
        ld d,c
        ld e,48
        mul d,e
        add hl,hl
        add hl,de
        ld de,0x1400
        add hl,de
        ld de,(tile_key)
        ld a,(hl)
        cp e
        jr nz,.miss
        inc hl
        ld a,(hl)
        cp d
        ret z
        dec hl
.miss:  ld (hl),e
        inc hl
        ld (hl),d
        ; This tile is aligned: its band and column already identify the damage.
        ld a,c
        add a,a
        ld l,a
        ld h,0
        ld de,0x1C00
        add hl,de
        ld a,(hl)
        cp b
        jr c,.low
        ld (hl),b
.low:   inc hl
        inc b
        ld a,(hl)
        cp b
        jr nc,.done
        ld (hl),b
.done:  or 1
        ret
.uncached:
        or 1
        scf
        ret
invalidate_tile_cells:
        ld a,(V_KIND)
        cp 9
        ret c
        push bc
        push de
        ld a,ixl
        srl a
        ld d,a
        ld a,e
        add a,a
        ld l,a
        ld h,0
        ld e,48
        mul d,e
        add hl,de
        ld de,0x1400
        add hl,de
        pop de
        push de
        ld a,d
        sub e
        ld b,a
        xor a
.clear: ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        djnz .clear
        pop de
        pop bc
        ret
clear_tile_cache:
        ld (cache_sp),sp
        ld sp,0x1730
        ld hl,0
        ld b,51
.loop:  DUP 8
        push hl
        EDUP
        djnz .loop
        ld sp,(cache_sp)
        ret
tile_key: dw 0
tile_native_dest: dw 0
cache_sp: dw 0

; floor(native-byte offset / 192), with no row-dependent subtraction loop.
; The 64-entry mathematical table stores floor(n/3), n=offset>>6.
; A=8-row band, HL=byte offset within that band.
canvas_band:
        push hl
        ld a,l
        rlca
        rlca
        and 3
        ld e,a
        ld a,h
        add a,a
        add a,a
        or e
        ld l,a
        ld h,0
        ld de,0x1DC0
        add hl,de
        ld c,(hl)
        ld d,c
        ld e,192
        mul d,e
        pop hl
        or a
        sbc hl,de
        ld a,c
        ret

; Mark only native drawing damage. Source columns are 8 pixels wide and bands
; are 8 rows high. A scroll or changed camera half-byte requests a complete view.
mark_rectangle:
        ld a,b
        ld (mark_height),a
        ld a,c
        ld (mark_width),a
        ld de,0xF290
        or a
        sbc hl,de
        jr nc,.onscreen
        ; Left-clipped figures may begin at F28F, one byte before the canvas.
        ; Their surviving pixels enter row zero: invalidate conservatively.
        ld a,1
        ld (dirty_full),a
        jp clear_tile_cache
.onscreen:
        call canvas_band
        cp 17
        ret nc
        add a,a
        ld e,a
        ld d,0
        push hl
        ld hl,0x1C00
        add hl,de
        push hl
        pop ix
        pop hl
        ld de,24
        ld b,0
.row:   or a
        sbc hl,de
        jr c,.column
        inc b
        jr .row
.column:
        add hl,de
        ld e,l
        ld a,(mark_width)
        add a,e
        cp 25
        jr c,.width
        ; A clipped first byte at column23 can spill into column0 of the next
        ; native row. Both sides need invalidation, not a clamped rectangle.
        ld a,1
        ld (dirty_full),a
        jp clear_tile_cache
.width: ld d,a
        ld a,(mark_height)
        dec a
        add a,b
        srl a
        srl a
        srl a
        inc a
        ld b,a
.span:  ld a,ixl
        cp 34
        ret nc
        ld a,(ix+0)
        cp e
        jr c,.minimum
        ld (ix+0),e
.minimum:
        ld a,(ix+1)
        cp d
        jr nc,.maximum
        ld (ix+1),d
.maximum:
        call invalidate_tile_cells
        inc ix
        inc ix
        djnz .span
        ret
mark_height: db 0
mark_width: db 0

; Publish after the original searchlight/attribute update. Only damaged bands
; and cells whose lighting changed are recopied; a colour is never guessed from
; a previous room or an actor's current location.
publish_canvas:
        ld a,(0x5847)
        cp 5
        jr z,.dusk
        cp 1
        ld a,0x10
        jr nz,.palette
.dusk:  ld a,0x14
.palette:
        ld hl,palette_select
        cp (hl)
        jr z,.selected
        ld (hl),a
        nextreg 0x43,a
.selected:
        call init_dma
        ld a,(0xA146)
        or a
        jr nz,.searchlight
        ld a,(0x5847)
.uniform:
        ld hl,lighting_uniform
        cp (hl)
        jp z,.view
        ld (hl),a
        ld hl,0x1E00
        ld (hl),a
        ld de,0x1E01
        ld bc,367
        ldir
        ld a,1
        ld (dirty_full),a
        jp .view
.searchlight:
        ld a,255
        ld (lighting_uniform),a
        ld hl,0x5847
        ld de,0x1E00
        ld ix,0x1C00
        ld b,16
.attrs: push bc
        ld b,23
.cell:  ld a,(hl)
.bright:
        ld c,a
        ld a,(de)
        cp c
        jr z,.same
        ld a,c
        ld (de),a
        ld a,24
        sub b
        ld c,a
        ld a,(ix+0)
        cp c
        jr c,.low
        ld (ix+0),c
.low:   inc c
        ld a,(ix+1)
        cp c
        jr nc,.same
        ld (ix+1),c
.same:  inc de
        inc hl
        djnz .cell
        ld bc,9
        add hl,bc
        inc ix
        inc ix
        pop bc
        djnz .attrs
.view:  ld a,(0xA7C7)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(0xA7C8)
        or a
        ld de,8
        jr z,.offset
        ld e,4
.offset:
        add hl,de
        ld (view_source),hl
        ld de,(view_previous)
        ld (view_previous),hl
        or a
        sbc hl,de
        ld a,(dirty_full)
        jr nz,.all
        ld a,(0xA7C7)
        or a
        jr nz,.all
        ld a,(dirty_full)
        or a
        jr z,.start
.all:   xor a
        ld (dirty_full),a
        ld hl,0x1C00
        ld b,17
.fill:  ld (hl),0
        inc hl
        ld (hl),24
        inc hl
        djnz .fill
.start:
        ld hl,0x1E00
        ld (band_attributes),hl
        ld hl,0x1C00
        ld (span_cursor),hl
        ld hl,(view_source)
        ld (band_source),hl
        ld hl,0x1038
        ld (band_dest),hl
        ld a,16
        ld (bands_left),a
.band:  ld hl,(span_cursor)
        ld a,(hl)
        ld (hl),24
        or a
        jr z,.left
        dec a
.left:  ld c,a
        inc hl
        ld a,(hl)
        ld (hl),0
        inc hl
        ld (span_cursor),hl
        ld b,a
        ld a,(0xA7C8)
        or a
        jr nz,.right
        dec b
.right: ld a,b
        cp 24
        jr c,.limit
        ld a,23
.limit: sub c
        jp c,.next_band
        jp z,.next_band
        ld (columns_left),a
        ld a,c
        add a,a
        add a,a
        add a,a
        ld (column_offset),a
        ld e,c
        ld d,0
        ld hl,(band_attributes)
        add hl,de
        ld (attribute_cursor),hl
.run:   ld hl,(attribute_cursor)
        ld a,(hl)
        ld c,a
        and 7
        cp 2
        ld a,34
        jr nc,.shade
        ld a,38
.shade:
        ld (rect_source_base),a
        ld a,(columns_left)
        ld b,a
        ld e,0
.count: ld a,(hl)
        cp c
        jr nz,.group
        inc hl
        inc e
        djnz .count
.group: ld (attribute_cursor),hl
        ld a,b
        ld (columns_left),a
        ld a,e
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld (rect_width),hl
        ld a,(column_offset)
        ld e,a
        ld d,0
        add a,l
        ld (column_offset),a
        ld hl,(band_source)
        add hl,de
        ld (rect_source),hl
        ld hl,(band_dest)
        add hl,de
        ld (rect_dest),hl
        ld a,8
        ld (rect_height),a
        call rectangle
        ld a,(columns_left)
        or a
        jr nz,.run
.next_band:
        ld hl,(band_source)
        ld de,1536
        add hl,de
        ld (band_source),hl
        ld hl,(band_dest)
        ld de,2048
        add hl,de
        ld (band_dest),hl
        ld hl,(band_attributes)
        ld de,23
        add hl,de
        ld (band_attributes),hl
        ld a,(bands_left)
        dec a
        ld (bands_left),a
        jp nz,.band
        ret
span_cursor: dw 0
band_attributes: dw 0
view_previous: dw 0xFFFF
dirty_full: db 1

rectangle:
        call hlib_dma_backend
        cp 2
        jr nz,.fallback
        ld a,(rect_source_base)
        ld b,a
        and 7
        rrca
        rrca
        rrca
        ld h,a
        ld l,0
        ld de,(rect_source)
        add hl,de
        ld (rect_packet_source),hl
        ld a,0
        adc a,0
        ld c,a
        ld a,b
        srl a
        srl a
        srl a
        add a,c
        ld (rect_packet_source_high),a
        ld hl,(rect_dest)
        ld de,0x8000
        add hl,de
        ld (rect_packet_dest),hl
        ld a,3
        adc a,0
        ld (rect_packet_dest_high),a
        ld hl,(rect_width)
        ld (rect_packet_width),hl
        ld a,(rect_height)
        ld l,a
        ld h,0
        ld (rect_packet_height),hl
        ld hl,rect_packet
        ld bc,(rect_packet_end-rect_packet)*256+0x6B
        otir
        ret
.fallback:
        ld a,(rect_height)
        ld (rect_left),a
        ; Eight-row display bands never cross a destination page. The common
        ; source rectangle stays in one page too: map once for the whole band.
        ld hl,(rect_source)
        ld a,h
        and 31
        ld h,a
        ld de,1344
        add hl,de
        ld de,(rect_width)
        add hl,de
        bit 5,h
        jr nz,.row
        ld hl,(rect_source)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(rect_source_base)
        add a,b
        nextreg 0x53,a
        ld a,h
        and 31
        or 96
        ld h,a
        push hl
        ld hl,(rect_dest)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,28
        nextreg 0x52,a
        ld a,h
        and 31
        or 64
        ld h,a
        ex de,hl
        pop hl
.fast:  push hl
        push de
        ld bc,(rect_width)
        call copy_block
        pop de
        pop hl
        ld a,192
        add hl,a
        inc d
        ld a,(rect_left)
        dec a
        ld (rect_left),a
        jr nz,.fast
        ret
.row:
        ld hl,(rect_source)
        ld a,h
        and 31
        ld h,a
        ld de,(rect_width)
        add hl,de
        bit 5,h
        jr nz,.crossing
        ld hl,(rect_source)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(rect_source_base)
        add a,b
        nextreg 0x53,a
        ld a,h
        and 31
        or 96
        ld h,a
        push hl
        ld hl,(rect_dest)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,28
        nextreg 0x52,a
        ld a,h
        and 31
        or 64
        ld h,a
        ex de,hl
        pop hl
        ld bc,(rect_width)
        call copy_block
        jr .next
.crossing:
        ld hl,(rect_source)
        ld (copy_source),hl
        ld hl,(rect_dest)
        ld (copy_dest),hl
        ld a,(rect_source_base)
        ld (copy_source_base),a
        ld a,28
        ld (copy_dest_base),a
        ld hl,(rect_width)
        ld (copy_left),hl
        call copy_pages
.next:  ld hl,(rect_source)
        ld de,192
        add hl,de
        ld (rect_source),hl
        ld hl,(rect_dest)
        inc h
        ld (rect_dest),hl
        ld a,(rect_left)
        dec a
        ld (rect_left),a
        jp nz,.row
        ret
rect_packet:
        db 0x83,0xC3,0x7D
rect_packet_source: dw 0
        dw 0
        db 0x14,0x10,0xAD
rect_packet_dest: dw 0
        db 0x82,0xD7
rect_packet_source_high: db 0
        db 0xDB
rect_packet_dest_high: db 0
        db 0xDF,3,0xE3
rect_packet_width: dw 0
        db 0xE7
rect_packet_height: dw 0
        db 0xEB
        dw 192
        db 0xEF
        dw 256
        db 0xCF,0x87
rect_packet_end:
rect_source_base: db 0
rect_source: dw 0
rect_dest: dw 0
rect_width: dw 0
rect_height: db 0
rect_left: db 0
view_source: dw 0
attribute_cursor: dw 0
band_source: dw 0
band_dest: dw 0
bands_left: db 0
columns_left: db 0
column_offset: db 0

        INCLUDE "lib/hlib_dma.asm"
overhead:
        ld a,(V_CLOCK)
        ld e,a
        ld d,0
        ld hl,overhead_table
        add hl,de
        ld a,(hl)
        ret
overhead_table: db 32,20,14,11
lighting_uniform: db 255
palette_select: db 0x10
role_base: db 0
dma_ready: db 0
source: dw 0
destination: dw 0
canvas_page: db 0
rows_left: db 0
copy_source: dw 0
copy_dest: dw 0
copy_left: dw 0
copy_chunk: dw 0
copy_source_base: db 0
copy_dest_base: db 0
scroll_source: dw 0
scroll_dest: dw 0
scroll_count: dw 0
scroll_size: dw 0
scroll_base: db 0
bitmap: dw 0
mask: dw 0
foreground: dw 0
phase: db 0
width: db 0
stride: db 0
mirrored: db 0
source_x: db 0
colour_x: db 0
source_bit: db 0
ink: db 0
dest_x: db 0
clip_flags: ds 4,0
aligned_fg: ds 4,0
pixel_dest: dw 0
pixel_bitmap: dw 0
pixel_mask: dw 0
pixel_source: dw 0
pixel_mapped: dw 0
byte_index: db 0
coverage: db 0
code_end:
        ASSERT code_end <= 0x1400
        SAVEBIN "ge_code.bin",code_start,code_end-code_start

        ORG 0x1A00
extra_start:
; Only the original searchlight mask painter is accelerated. Beam movement,
; prisoner detection, morale and sound remain in their original callers.
searchlight_hook:
        call hlib_pace_open
        ld hl,(R_DE)
        ld de,0x5600
        or a
        sbc hl,de
        ld a,(0xAE75)
        or a
        jr z,.table
        set 3,h
.table: add hl,hl
        set 5,h
        set 6,h
        nextreg 0x53,87
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_TARGET),de
        call redirect_return
        RESTORE_REGS
        exx
        ld de,0xAF3E
        push af
        SAVE_REGS
        xor a
        ld (V_NATIVE),a
        ld a,0xF3
        ld (V_RDELTA),a
        ld hl,0xAEBC
        jp set_launch
; Move the dirty tile hook before its original address lookup. The game's own
; lookup and stack operations execute unchanged at 28 MHz, then colour drawing
; sees exactly the same registers as it previously did at BC71.
dirty_prefix:
        RESTORE_REGS
        ld sp,(V_SP)
        push hl
        ld a,(de)
        exx
        pop de
        push hl
        call 0xBCAA
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,bc
        ld (V_SP),sp
        ld sp,0x3FC0
        push af
        SAVE_REGS
        ; Restore the original CALL's return word left below the native SP.
        ld hl,(V_SP)
        dec hl
        ld (hl),0xBC
        dec hl
        ld (hl),0x6A
        ld hl,dirty_costs
        ld a,(0x68A0)
        or a
        jr nz,.cost
        inc hl
        inc hl
        ld a,(R_AF_ALT+1)
        cp 45
        jr c,.cost
        inc hl
        inc hl
        cp 139
        jr c,.cost
        inc hl
        inc hl
        cp 204
        jr c,.cost
        inc hl
        inc hl
.cost:  ld a,(hl)
        ld (dirty_target),a
        inc hl
        ld a,(hl)
        ld (dirty_m1),a
        jp tile_hook.ready
dirty_costs: db 12,19,23,44,25,47,26,50,26,49
dirty_target: db 0
dirty_m1: db 0
dirty_credit:
        ld a,(V_KIND)
        cp 2
        ret nz
        ld a,(dirty_target)
        ld e,a
        ld d,0
        ld a,(V_CLOCK)
        or a
        jr z,.credit
.shift: srl e
        dec a
        jr nz,.shift
.credit:
        ld hl,(HLIB_V_PACE+4)
        or a
        sbc hl,de
        jr nc,.save
        ld hl,0
.save:  jp hlib_debt_set
dirty_r:
        ld a,(V_KIND)
        cp 2
        ret nz
        ld a,(dirty_m1)
        ld hl,V_RDELTA
        add a,(hl)
        ld (hl),a
        ret
pixels_empty_forward:
        ld a,8
        add hl,a
        add de,a
        ret
pixels_empty_reverse:
        ld a,8
        add de,a
        ld bc,8
        or a
        sbc hl,bc
        ret
foreground_fullclip: db 0
foreground_bytes: db 0
prepare_foreground:
        ld a,(foreground_fullclip)
        or a
        jr z,.masked
        ld a,(foreground_bytes)
        ld b,a
        ld hl,(foreground)
        ld a,255
.all:   and (hl)
        inc l
        djnz .all
        cp 255
        jr nz,.masked
        ld hl,aligned_fg
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ret
.masked:
        ld hl,(foreground)
        ld ix,clip_flags
        ld de,aligned_fg
        ld b,4
.fg:    ld c,(hl)
        ld a,(ix+0)
        cp 0x77
        jr z,.visible
        ld c,0
.visible:
        ld a,c
        ld (de),a
        inc l
        inc de
        inc ix
        djnz .fg
        ld a,(aligned_fg)
        ld b,a
        ld a,(aligned_fg+1)
        ld c,a
        ld a,(aligned_fg+2)
        ld d,a
        ld a,(aligned_fg+3)
        ld e,a
        ld a,(phase)
        or a
        jr z,.aligned
.shift: sla e
        rl d
        rl c
        rl b
        dec a
        jr nz,.shift
.aligned:
        ld a,b
        ld (aligned_fg),a
        ld a,c
        ld (aligned_fg+1),a
        ld a,d
        ld (aligned_fg+2),a
        ret
; A50B clears the play area for the original confirmation/result text. The ULA
; owns that dialog; reveal it before its first clear. Resume only after a fully
; composed play frame, above. Reproduce CALL 6A27, including its return word.
dialog_hook:
        nextreg 0x69,0
        nextreg 0x15,0
        ld hl,(V_SP)
        dec hl
        ld (hl),0xA5
        dec hl
        ld (hl),0x0E
        ld (V_SP),hl
        ld a,0xF1
        ld (V_RDELTA),a
        ld hl,0x6A27
        jp set_finish

; McQueen in the cooler: with the outfit on and the hero waiting in solitary (in_solitary A13A = FF, room_index
; 68A0 = 24, standing on solitary_pos: map X 3A, Y 2A, low bytes) sprite 0 is a baseball thrown at the wall and caught.
; Otherwise sprites are off. Game RAM is only read (slots 3-5 hold it here); the step lives in page 24.
cooler_ball:
        ld a,(0x3E18)
        or a
        jr z,.hide
        ld a,(0xA13A)
        inc a
        jr nz,.hide
        ld a,(0x68A0)
        cp 24
        jr nz,.hide
        ld a,(0x800F)           ; room positions are one byte
        cp 0x3A
        jr nz,.hide
        ld a,(0x8011)
        cp 0x2A
.y_check:
        jr nz,.hide
        ld a,(V_BALL)
        inc a
        cp BALL_STEPS
        jr c,.step
        xor a
.step:  ld (V_BALL),a
        add a,a
        ld e,a
        ld d,0
        ld hl,ball_path
        add hl,de
        ld bc,0x303B
        xor a
        out (c),a               ; sprite 0
        ld bc,0x0057
        ld a,(hl)
        out (c),a               ; X
        inc hl
        ld a,(hl)
        out (c),a               ; Y
        out (c),d               ; no palette offset, mirror or X bit 8
        ld a,0x80
        out (c),a               ; visible, pattern 0
        nextreg 0x15,1          ; sprites on, over Layer 2
        ret
.hide:  nextreg 0x15,0
        ret

extra_end:
        ASSERT extra_end <= 0x1C00
        SAVEBIN "ge_extra.bin",extra_start,extra_end-extra_start

; Build-time overlays for colour maps with erased halo pixels. Both replace
; only code in page 26. All other addresses and the no-marker build stay fixed.
        ORG pixels_forward
halo_forward:       PIXEL_KERNEL inc,pixels_empty_forward,halo_full_forward,1
halo_reverse:       PIXEL_KERNEL dec,pixels_empty_reverse,halo_full_reverse,1
halo_full_forward:  FULL_KERNEL inc,1
halo_full_reverse:  FULL_KERNEL dec,1
halo_forward_cross: CROSS_KERNEL inc,1
halo_reverse_cross: CROSS_KERNEL dec,1
        ASSERT halo_forward.masked == pixels_forward.masked
        ASSERT $ <= figure_mmu4
        SAVEBIN "ge_halo_pixels.bin",halo_forward,$-halo_forward
        ORG draw_figure.select
halo_select: SELECT_PIXELS halo_forward,halo_reverse,halo_forward_cross,halo_reverse_cross
        ASSERT $ == draw_figure.select_end
        SAVEBIN "ge_halo_select.bin",halo_select,$-halo_select
