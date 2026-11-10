; Highway Encounter: restore the temporary loader tail before original B0E0.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_CSRC EQU 0x3E60
V_CDST EQU 0x3E62
V_VARIANT EQU 0x3E68
V_ROWS EQU 0x3E69
V_MASK EQU 0x3E6A
V_DPAGE EQU 0x3E6D
V_C_SPEED EQU 0x3E70
V_ARGBC EQU 0x3E72
V_ARGDE EQU 0x3E74
V_ARGHL EQU 0x3E76
V_ARGIX EQU 0x3E78
V_ARGA EQU 0x3E7A
V_KIND EQU 0x3E7B
V_EXIT EQU 0x3E7C
V_SHOW EQU 0x3E80
V_NEWA EQU 0x3E81
V_FAST EQU 0x3E82
V_BULK EQU 0x3E85
V_LEFT EQU 0x3E86
V_COPY_SRC EQU 0x3E88
V_COPY_DST EQU 0x3E8A
V_CHUNK EQU 0x3E8C
V_EXIT_A EQU 0x3E8E
V_TABLE EQU 0x3E90
V_FLAGS EQU 0x3E92
V_COLUMNS EQU 0x3E94
V_ERASE_SPEED EQU 0x3E96
V_ERASE_SRC_PAGE EQU 0x3E98
V_ERASE_DST_PAGE EQU 0x3E99
V_ROW_FLAGS EQU 0x3EA0
V_ROW_SRC EQU 0x3EBC
V_ROW_DST EQU 0x3EBE
V_DMA_READY EQU 0x3EC0
V_POST_SPEED EQU 0x3EC1
V_FIXED_WINDOW EQU 0x3EC2
        ORG 0x2200
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
        DEFINE HLIB_PC_OTIR
        INCLUDE "lib/hlib_dma.asm"
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
        MACRO RESTORE delta
        ld a,delta
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ENDM
h_open:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ; Whole-window calibration includes the two wrappers and raster
        ; quantisation. Repay their fixed cost without changing game delays.
        ld hl,176
        call hlib_debt_add
        call hlib_pace_open
        RESTORE -11
        ld ix,(0x8F01)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x985E
h_close:
        ENTER
        ld a,(V_SPEED)
        ld c,a
pace_k:
        ld a,104
        call hlib_pace_waitk
        HLIB_SPEED_OUT V_SPEED
        RESTORE -12
        ld a,(0x8F0B)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9ADB
h_erase_open:
        ENTER
        HLIB_SPEED_IN V_ERASE_SPEED
        ld hl,176
        call hlib_debt_add
        call hlib_pace_open
        RESTORE -12
        ld hl,0x8D52
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9825
h_erase_test:
        ; Both original branches select982A when NZ and9859 when Z.
        ; Finish only at the actual RET, including the empty erase list.
        ENTER
        jr nz,.more
        ld a,(V_ERASE_SPEED)
        ld c,a
        ld a,104
        call hlib_pace_waitk
        HLIB_SPEED_OUT V_ERASE_SPEED
        RESTORE -12
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9859
.more:
        RESTORE -12
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x982A
h_scene_open:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,1
        ld (V_FIXED_WINDOW),a
        ld hl,176
        call hlib_debt_add
        call hlib_pace_open
        RESTORE -12
        ld hl,0xFD00
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x95F2
h_scene_close:
        ENTER
        ld a,(V_SPEED)
        ld c,a
scene_pace_k:
        ; Original95EF..9765:375864 T, independent of tile contents.
        ; Count all colour work inside this fixed drawing window.
        ld hl,26848
        call hlib_pace_wait
        xor a
        ld (V_FIXED_WINDOW),a
        HLIB_SPEED_OUT V_SPEED
        RESTORE -12
        ld a,(0x8F1C)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9768
; A8D6 is outside both windows: it may dispatch the ship/ending sound.
; After it returns, 976D..981F contains only the original room publication,
; backing-store and dirty-table copies. Time the whole sequence once.
h_post_open:
        ENTER
        HLIB_SPEED_IN V_POST_SPEED
        ld a,1
        ld (V_FIXED_WINDOW),a
        ld hl,176
        call hlib_debt_add
        call hlib_pace_open
        RESTORE -12
        ld hl,0xD905
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x9770
h_post_close:
        ENTER
        ld a,(V_POST_SPEED)
        ; Original976D..981F:247097 T before display-memory contention.
        ld hl,17650
        call hlib_pace_wait
        xor a
        ld (V_FIXED_WINDOW),a
        HLIB_SPEED_OUT V_POST_SPEED
        RESTORE -12
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA546
boot_resume:
        nextreg 0x51,HOOK_PAGE
        ld sp,0x3F00
        push af
        push bc
        push de
        push hl
        ld hl,0x2000
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
        MACRO COLOUR_ENTRY id
        nextreg 0x51,24
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        ld a,id
        jp colour_enter
        ENDM
c_9933:
        COLOUR_ENTRY 0
x_9933:
        RESTORE -18
        HLIB_R_OUT
        ld l,c
        ld h,b
        ld a,24
        nextreg 0x51,255
        jp 0x9937
c_99d1:
        COLOUR_ENTRY 1
x_99d1:
        RESTORE -18
        HLIB_R_OUT
        ld h,b
        ld l,c
        ld a,24
        nextreg 0x51,255
        jp 0x99D5
c_9a26:
        COLOUR_ENTRY 2
x_9a26:
        RESTORE -18
        HLIB_R_OUT
        ld h,b
        ld l,c
        ld a,24
        nextreg 0x51,255
        jp 0x9A2A
c_9a70:
        COLOUR_ENTRY 3
x_9a70:
        RESTORE -18
        HLIB_R_OUT
        ld h,b
        ld l,c
        ld b,24
        nextreg 0x51,255
        jp 0x9A74
; Logical byte -> eight colour pixels. 4000..57FF is the Spectrum bitmap,
; mapped directly into Layer 2 pages12..17. 5800..FFFF uses
; pages 50..91. Banks46/47 remain reserved for full hidden-ROM sources.
colour_address:
        ld a,h
        cp 0x58
        jr c,.screen
        rrca
        rrca
        and 0x3F
        add a,28
        ld b,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld a,b
        ret
.screen:
        ld a,h
        and 7
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
        ld b,a
        ld a,h
        and 0x18
        rlca
        rlca
        rlca
        or b
        ld h,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,h
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        add a,12
        ld b,a
        ld a,h
        and 31
        or 0xC0
        ld h,a
        ld a,b
        ret
; Mirror one original byte-copy without changing original game memory.
; The game is 48K, and the enclosing wrapper checks/restores its fixed
; slots 6/7. This helper is called only with original code suspended.
colour_copy_byte:
        ; A3DE's clear deliberately finishes with a discarded ROM write.
        ld a,d
        cp 0x40
        ret c
        push bc
        push de
        push hl
        push de
        call colour_address
        nextreg 0x56,a
        ex de,hl
        pop hl
        push de
        call colour_address
        nextreg 0x57,a
        set 5,h
        ex de,hl
        pop hl
        ld bc,8
        ldir
        nextreg 0x56,0
        nextreg 0x57,1
        pop hl
        pop de
        pop bc
colour_finish_byte:
        ret
; Cached original mask + supplied colours, all four exact shift variants.
; DE=original figure address, BC=original buffer position, A=variant 0..3.
; No original game RAM is written. The original plot still runs afterwards.
colour_plot:
        ld (V_VARIANT),a
        ld (V_CDST),bc
        ld hl,-0xB8F0
        add hl,de
        DUP 4
        srl h
        rr l
        EDUP
        ld de,9
        xor a
.divide:
        or a
        sbc hl,de
        jr c,.index
        inc a
        jr .divide
.index:
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_VARIANT)
        add a,a
        add a,a
        ld e,a
        ld d,0
        add hl,de
        nextreg 0x56,45
        ld de,colour_cache_table
        add hl,de
        ld a,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld a,c
        ld (V_FAST),a
        ld (V_CSRC),de
        ld a,24
        ld (V_ROWS),a
.row:
        ld hl,(V_CDST)
        call colour_address
        nextreg 0x55,a
        ld (V_DPAGE),a
        ld a,h
        and 31
        or 0xA0
        ld h,a
        ld de,(V_CSRC)
        ld a,(de)
        ld (V_MASK),a
        inc de
        ld a,(de)
        ld (V_MASK+1),a
        inc de
        ld a,(de)
        ld (V_MASK+2),a
        inc de
        ld a,(de)
        ld (V_FAST),a
        inc de
        ld a,(de)
        ld (V_FAST+1),a
        inc de
        ld a,(de)
        ld (V_FAST+2),a
        inc de
        MACRO COLOUR_OCTET offset
        ld a,(V_MASK+offset)
        ld c,a
        DUP 8
        rlc c
        sbc a,a
        and (hl)
        ld b,a
        ld a,(de)
        or b
        ld (hl),a
        inc de
        inc hl
        EDUP
        ENDM
        MACRO COLOUR_FAST_OCTET
        ex de,hl
        ld a,227
        DUP 8
        ldix
        EDUP
        ex de,hl
        ENDM
        ld a,(V_FAST+0)
        or a
        jr z,.slow0
        COLOUR_FAST_OCTET
        jp .next0
.slow0:
        COLOUR_OCTET 0
.next0:
        call colour_next_dest
        ld a,(V_FAST+1)
        or a
        jr z,.slow1
        COLOUR_FAST_OCTET
        jp .next1
.slow1:
        COLOUR_OCTET 1
.next1:
        call colour_next_dest
        ld a,(V_VARIANT)
        cp 1
        jp z,.short
        ld a,(V_FAST+2)
        or a
        jr z,.slow2
        COLOUR_FAST_OCTET
        jp .next2
.slow2:
        COLOUR_OCTET 2
.next2:
        jr .done
.short:
        ex de,hl
        ld bc,8
        add hl,bc
        ex de,hl
.done:
        ld (V_CSRC),de
        ld hl,(V_CDST)
        ld bc,-32
        add hl,bc
        ld (V_CDST),hl
        ld a,(V_ROWS)
        dec a
        ld (V_ROWS),a
        jp nz,.row
        nextreg 0x55,5
        nextreg 0x56,0
        nextreg 0x57,1
        ret
colour_next_dest:
        ld a,h
        cp 0xC0
        ret nz
        ld a,(V_DPAGE)
        inc a
        ld (V_DPAGE),a
        nextreg 0x55,a
        ld hl,0xA000
        ret
        MACRO COLOUR_EXIT
        RESTORE -18
        HLIB_R_OUT
        ENDM
colour_enter:
        ld (V_KIND),a
        pop af
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ld (V_ARGBC),bc
        ld (V_ARGDE),de
        ld (V_ARGHL),hl
        ld (V_ARGIX),ix
        ld (V_ARGA),a
        HLIB_SPEED_IN V_C_SPEED
        xor a
        ld (V_BULK),a
        ld a,(V_KIND)
        cp 30
        jr z,.bulk
        cp 41
        jr z,.bulk
        cp 4
        jr c,.ordinary
        cp 18
        jr nc,.ordinary
        cp 11
        jr z,.ordinary
.bulk:  ld a,1
        ld (V_BULK),a
        ld a,(HLIB_V_PACE+10)
        or a
        jr nz,.ordinary
        call hlib_pace_open
        ld a,2
        ld (V_BULK),a
.ordinary:
        ld a,(V_FIXED_WINDOW)
        or a
        call z,hlib_nest_open
        ld a,(V_KIND)
        add a,a
        add a,a
        ld c,a
        ld b,0
        ld hl,colour_dispatch
        add hl,bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        ld (V_EXIT),bc
        ex de,hl
        ld de,colour_after
        push de
        jp (hl)
colour_after:
        ld a,(V_FIXED_WINDOW)
        or a
        jr z,.nested
        call hlib_pace_tick
        jr .budget
.nested:
        ; Native wrapper probe:91us outside the nested samples,27us between
        ; the window/debt samples. With K=6.5 this needs(91*6.5+27)/4=155
        ; sixteenths, not the former52. It is hook overhead, not game time.
        ; Round up one unit; the original-code window K remains unchanged.
        ld a,(HLIB_V_PACE+10)
        or a
        ld a,24
        jr z,.close
        ld a,156
.close:
        call hlib_nest_close
.budget:
        ld a,(V_BULK)
        cp 2
        call z,colour_copy_budget
        ld a,(V_BULK)
        or a
        jr nz,.copy_exit
        HLIB_SPEED_OUT V_C_SPEED
.copy_exit:
        ld hl,(V_EXIT)
        jp (hl)
colour_tick:
        ld a,(V_FIXED_WINDOW)
        or a
        jp nz,hlib_pace_tick
        jp hlib_debt_tick
colour_copy_budget:
        ; Original LDIR time, less the same LDIR about to run at 28 MHz.
        ; Units are 14 original T states (1/16 raster line). The measured
        ; colour work is already debt. No original game delay is changed.
        ld hl,(V_ARGBC)
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld d,h
        ld e,l
        DUP 4
        srl d
        rr e
        EDUP
        ld a,(V_C_SPEED)
        inc a
        ld b,a
.shift: srl h
        rr l
        djnz .shift
        or a
        sbc hl,de
        xor a
        jp hlib_pace_wait
colour_copy_up:
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        ld bc,(V_ARGBC)
        ld a,b
        or c
        jr z,.slow
        ld a,h
        cp 0x58
        jr c,.slow
        ld a,d
        cp 0x5B
        jp nc,colour_copy_linear
        ; Full32-byte ULA row:256 contiguous pixels, source within one page.
        cp 0x58
        jr nc,.slow
        ld a,e
        and 31
        jr nz,.slow
        ld a,b
        or a
        jr nz,.slow
        ld a,c
        cp 32
        jr nz,.slow
        ld a,h
        and 3
        cp 3
        jr nz,.row
        ld a,l
        cp 225
        jr nc,.slow
.row:   call colour_map_pair
        ld bc,256
        call colour_dma_copy
        nextreg 0x56,0
        nextreg 0x57,1
        ret
.slow:
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        ld bc,(V_ARGBC)
.loop:
        call colour_copy_byte
        inc hl
        inc de
        dec bc
        call colour_copy_tick
        ld a,b
        or c
        jr nz,.loop
        ret
colour_copy_linear:
        ; Contiguous expanded buffers: map once per 8K boundary, then use
        ; eight unrolled LDI instructions. Preserve forward overlap exactly.
        ld (V_COPY_SRC),hl
        ld (V_COPY_DST),de
        ld (V_LEFT),bc
.loop:  ld hl,(V_COPY_SRC)
        ld a,h
        and 3
        ld h,a
        ld de,1024
        ex de,hl
        or a
        sbc hl,de
        push hl
        ld hl,(V_COPY_DST)
        ld a,h
        and 3
        ld h,a
        ld de,1024
        ex de,hl
        or a
        sbc hl,de
        pop de
        call .minimum
        ld de,(V_LEFT)
        call .minimum
        ld (V_CHUNK),hl
        ld hl,(V_COPY_SRC)
        call colour_address
        nextreg 0x56,a
        push hl
        ld hl,(V_COPY_DST)
        call colour_address
        nextreg 0x57,a
        set 5,h
        ex de,hl
        pop hl
        push hl
        ld hl,(V_CHUNK)
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        pop hl
        call colour_dma_copy
        call colour_tick
        ld de,(V_CHUNK)
        ld hl,(V_COPY_SRC)
        add hl,de
        ld (V_COPY_SRC),hl
        ld hl,(V_COPY_DST)
        add hl,de
        ld (V_COPY_DST),hl
        ld hl,(V_LEFT)
        or a
        sbc hl,de
        ld (V_LEFT),hl
        ld a,h
        or l
        jp nz,.loop
        nextreg 0x56,0
        nextreg 0x57,1
        ret
.minimum:
        push hl
        or a
        sbc hl,de
        pop hl
        ret c
        ex de,hl
        ret
; All operands are real RAM in stable MMU6/7 pages. The original 48K game
; only owns the beeper; it has no DMA user or Next interrupt sources. Jobs
; are synchronous, bounded to 8K, and run at 28MHz. Forward overlap keeps
; the original read-then-write order. Fail closed on old cores/HW-IM2.
colour_dma_copy:
        ld a,(V_DMA_READY)
        or a
        jr nz,.ready
        push hl
        push de
        push bc
        ld a,1
        call hlib_dma_init
        ld a,1
        ld (V_DMA_READY),a
        pop bc
        pop de
        pop hl
.ready:
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld (colour_dma_source),hl
        ld (colour_dma_destination),de
        ld (colour_dma_length),bc
        ld hl,colour_dma_packet
        ld bc,(colour_dma_end-colour_dma_packet)*256+0x6B
        otir
        ret
.cpu:   DUP 8
        ldi
        EDUP
        jp pe,.cpu
        ret
colour_dma_packet:
        db 0x83,0xC3,0x7D
colour_dma_source: dw 0
colour_dma_length: dw 0
        db 0x14,0x10,0xAD
colour_dma_destination: dw 0
        db 0x82,0xCF,0x87
colour_dma_end:
colour_copy_down:
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        ld bc,(V_ARGBC)
        ld a,b
        or c
        jr z,.loop
        push hl
        or a
        sbc hl,bc
        ld a,h
        pop hl
        cp 0x58
        jr c,.loop
        push hl
        ex de,hl
        or a
        sbc hl,bc
        ld a,h
        pop hl
        ld de,(V_ARGDE)
        cp 0x58
        jp nc,colour_copy_reverse_linear
.loop:
        call colour_copy_byte
        dec hl
        dec de
        dec bc
        call colour_copy_tick
        ld a,b
        or c
        jr nz,.loop
        ret
; Attribute/backing-buffer LDDR: page-bounded chunks avoid remapping both
; pages for every byte. Expanded bytes are disjoint eight-pixel groups;
; reversing within each group preserves the original backward overlap.
; CPU LDD is used here; the shared DMA model does not support decrement.
colour_copy_reverse_linear:
        ld (V_COPY_SRC),hl
        ld (V_COPY_DST),de
        ld (V_LEFT),bc
.loop:  ld hl,(V_COPY_SRC)
        ld a,h
        and 3
        ld h,a
        inc hl
        push hl
        ld hl,(V_COPY_DST)
        ld a,h
        and 3
        ld h,a
        inc hl
        pop de
        call colour_copy_linear.minimum
        ld de,(V_LEFT)
        call colour_copy_linear.minimum
        ld (V_CHUNK),hl
        ld hl,(V_COPY_SRC)
        call colour_address
        nextreg 0x56,a
        ld a,l
        or 7
        ld l,a
        push hl
        ld hl,(V_COPY_DST)
        call colour_address
        nextreg 0x57,a
        set 5,h
        ld a,l
        or 7
        ld l,a
        ex de,hl
        ld hl,(V_CHUNK)
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        pop hl
.copy:  DUP 8
        ldd
        EDUP
        jp pe,.copy
        call colour_tick
        ld de,(V_CHUNK)
        ld hl,(V_COPY_SRC)
        or a
        sbc hl,de
        ld (V_COPY_SRC),hl
        ld hl,(V_COPY_DST)
        or a
        sbc hl,de
        ld (V_COPY_DST),hl
        ld hl,(V_LEFT)
        or a
        sbc hl,de
        ld (V_LEFT),hl
        ld a,h
        or l
        jp nz,.loop
        nextreg 0x56,0
        nextreg 0x57,1
        ret
colour_copy_tick:
        ld a,c
        or a
        ret nz
        push bc
        push de
        push hl
        call colour_tick
        pop hl
        pop de
        pop bc
        ret
colour_plot_0:
        ld bc,(V_ARGBC)
        ld de,(V_ARGDE)
        ld a,0
        jp colour_plot
colour_plot_1:
        ld bc,(V_ARGBC)
        ld de,(V_ARGDE)
        ld a,1
        jp colour_plot
colour_plot_2:
        ld bc,(V_ARGBC)
        ld de,(V_ARGDE)
        ld a,2
        jp colour_plot
colour_plot_3:
        ld bc,(V_ARGBC)
        ld de,(V_ARGDE)
        ld a,3
        jp colour_plot
colour_ix8_de:
        ld hl,(V_ARGIX)
        ld bc,8
        add hl,bc
        ld de,(V_ARGDE)
        jp colour_copy_byte
colour_ix_de:
        ld hl,(V_ARGIX)
        ld de,(V_ARGDE)
        jp colour_copy_byte
colour_ix_hl:
        ld hl,(V_ARGIX)
        ld de,(V_ARGHL)
        jp colour_copy_byte
colour_ix8_hl:
        ld hl,(V_ARGIX)
        ld bc,8
        add hl,bc
        ld de,(V_ARGHL)
        jp colour_copy_byte
colour_tile8:
        ld hl,(V_ARGHL)
        ld de,(V_ARGIX)
        ; Eight aligned source bytes are64 pixels in one page. Tile rows
        ; share their destination page except at one forward boundary.
        ld a,h
        cp 0x58
        jr c,.slow
        ld a,l
        and 7
        jr nz,.slow
        ld a,d
        cp 0x58
        jr c,.slow
        cp 0xFF
        jr c,.mapped
        ld a,e
        cp 32
        jr nc,.slow
.mapped:
        call colour_map_pair
        ld (V_ERASE_DST_PAGE),a
        ld a,8
.row:   DUP 8
        ldi
        EDUP
        dec a
        jr z,.done
        push af
        ex de,hl
        ld bc,248
        add hl,bc
        ex de,hl
        ld a,d
        cp 0xE0
        jr nc,.same
        add a,0xE0
        ld d,a
        ld a,(V_ERASE_DST_PAGE)
        inc a
        ld (V_ERASE_DST_PAGE),a
        nextreg 0x57,a
.same:  pop af
        jr .row
.done:  nextreg 0x56,0
        nextreg 0x57,1
        ret
.slow:
        ld hl,(V_ARGHL)
        ld de,(V_ARGIX)
        ld b,8
.loop:  call colour_copy_byte
        inc hl
        push hl
        ld hl,32
        add hl,de
        ex de,hl
        pop hl
        djnz .loop
        ret
colour_hl_ix:
        ld hl,(V_ARGHL)
        ld de,(V_ARGIX)
        jp colour_copy_byte
colour_hl_de:
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        jp colour_copy_byte
colour_restore_figure:
        ld hl,(V_ARGHL)
        ld d,h
        ld e,l
        ld bc,0xF005
        add hl,bc
        ; Most figures occupy three bytes wholly inside a32-byte row.
        ; Map that whole rectangle once and change pages only when stepping
        ; backwards through an8K boundary. Edge columns retain the byte path.
        ld a,e
        and 31
        cp 25
        jp nc,.slow
        ld a,h
        cp 0x5B
        jp c,.slow
        ld a,d
        cp 0x5B
        jp c,.slow
        push de
        call colour_address
        ld (V_ERASE_SRC_PAGE),a
        nextreg 0x56,a
        ex de,hl
        pop hl
        push de
        call colour_address
        ld (V_ERASE_DST_PAGE),a
        nextreg 0x57,a
        set 5,h
        ex de,hl
        pop hl
        ld a,24
.fastrow:
        DUP 24
        ldi
        EDUP
        dec a
        jr z,.fastdone
        ld bc,-280
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        push af
        ld a,h
        cp 0xC0
        jr nc,.source_ok
        add a,0x20
        ld h,a
        ld a,(V_ERASE_SRC_PAGE)
        dec a
        ld (V_ERASE_SRC_PAGE),a
        nextreg 0x56,a
.source_ok:
        ld a,d
        cp 0xE0
        jr nc,.dest_ok
        add a,0x20
        ld d,a
        ld a,(V_ERASE_DST_PAGE)
        dec a
        ld (V_ERASE_DST_PAGE),a
        nextreg 0x57,a
.dest_ok:
        pop af
        jr .fastrow
.fastdone:
        nextreg 0x56,0
        nextreg 0x57,1
        ret
.slow:
        ld a,24
        ld (V_ROWS),a
.row:   push hl
        push de
        ; Three logical bytes span24 pixels. At a1024-byte source/destination
        ; boundary they occupy two Next pages; do not let LDIR cross the mapped
        ; slot into unrelated pixels or wrap the destination through ROM.
        ld a,h
        and 3
        cp 3
        jr nz,.check_dest
        ld a,l
        cp 254
        jr nc,.edge
.check_dest:
        ld a,d
        and 3
        cp 3
        jr nz,.mapped
        ld a,e
        cp 254
        jr nc,.edge
.mapped:
        call colour_map_pair
        ld bc,24
        ldir
        nextreg 0x56,0
        nextreg 0x57,1
        jr .next
.edge:
        ld b,3
.byte:  call colour_copy_byte
        inc hl
        inc de
        djnz .byte
.next:
        pop de
        pop hl
        ld bc,-32
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        ld a,(V_ROWS)
        dec a
        ld (V_ROWS),a
        jr nz,.row
        ret
; Both logical starts map once. Caller owns slots 6/7 until it restores them.
colour_map_pair:
        push de
        call colour_address
        nextreg 0x56,a
        ex de,hl
        pop hl
        push de
        call colour_address
        nextreg 0x57,a
        set 5,h
        ex de,hl
        pop hl
        ret
colour_commit:
        ld hl,0x9BFC
.row:   ld a,(hl)
        or a
        ret z
        ld (V_COLUMNS),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_ARGHL),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_ARGDE),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_FLAGS),de
        ld (V_TABLE),hl
        ; Keep the at-most27 original flags before mapping their RAM slot.
        ld hl,(V_FLAGS)
        ld de,V_ROW_FLAGS
        ld a,(V_COLUMNS)
        ld b,a
.flags: ld a,(hl)
        ld (de),a
        dec l
        inc de
        djnz .flags
        ld hl,V_ROW_FLAGS
        ld (V_FLAGS),hl
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        call colour_map_pair
        ld (V_ROW_SRC),hl
        ld (V_ROW_DST),de
.column:
        ld hl,(V_FLAGS)
        ld a,(hl)
        or a
        call nz,colour_dirty_cell
        ld hl,(V_FLAGS)
        inc l
        ld (V_FLAGS),hl
        ld bc,-8
        ld hl,(V_ROW_SRC)
        add hl,bc
        ld (V_ROW_SRC),hl
        ld hl,(V_ROW_DST)
        add hl,bc
        ld (V_ROW_DST),hl
        ld hl,(V_ARGDE)
        dec l
        ld (V_ARGDE),hl
        ld a,(V_COLUMNS)
        dec a
        ld (V_COLUMNS),a
        jr nz,.column
        ; A complete table row is bounded to31 cells, well below a video
        ; frame. Poll once here instead of once per (often untouched) cell.
        nextreg 0x56,0
        nextreg 0x57,1
        call colour_tick
        ld hl,(V_TABLE)
        jp .row
colour_dirty_cell:
        ld de,(V_ARGDE)
        call colour_is_visible
        ret z
        ; The whole table row shares its source and destination pages.
        ld hl,(V_ROW_SRC)
        ld de,(V_ROW_DST)
        ld a,8
.row:   DUP 8
        ldi
        EDUP
        ld bc,-264
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        dec a
        jr nz,.row
        ret
colour_hide_cell:
        ; DE is an attribute cell. A newly rendered room can discard pixels
        ; hidden by INK=PAPER: the next room redraws them before re-enabling.
        push bc
        push de
        push hl
        ld a,d
        sub 0x58
        add a,a
        add a,a
        add a,a
        add a,0x40
        ld d,a
        ld h,d
        ld l,e
        call colour_address
        nextreg 0x56,a
        ; A character's eight scanlines share one32-line Layer2 page.
        ; Map it once, retaining the exact transparent8x8 cell.
        ld b,8
.row:   ld a,227
        DUP 8
        ld (hl),a
        inc l
        EDUP
        ld a,l
        sub 8
        ld l,a
        inc h
        djnz .row
        nextreg 0x56,0
        pop hl
        pop de
        pop bc
        ret
colour_is_visible:
        ; DE=ULA byte. Z means hidden. Only the ordinary dirty-cell path
        ; uses this gate; room copies precede the original attribute upload.
        ld a,d
        and 0x18
        rrca
        rrca
        rrca
        or 0x58
        ld h,a
        ld l,e
        ld a,(hl)
        ld c,a
        and 7
        ld b,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        cp b
        ret
colour_zero_hl:
        ld de,(V_ARGHL)
        xor a
        jp colour_fill_mono
colour_white_hl:
        ld de,(V_ARGHL)
        ld a,255
        jp colour_fill_mono
colour_red_hl:
        nextreg 0x69,0
        ld de,(V_ARGHL)
        ld a,82
        jp colour_fill_mono
colour_value_de:
        ld de,(V_ARGDE)
        ld a,(V_ARGA)
        jp colour_fill_mono
colour_flag_loop:
        ld a,(V_ARGBC+1)
        ld (V_ROWS),a
.loop:  call colour_triple_hl
        ld hl,(V_ARGHL)
        inc hl
        inc hl
        ld de,(V_ARGDE)
        add hl,de
        ld (V_ARGHL),hl
        ld a,(V_ROWS)
        dec a
        ld (V_ROWS),a
        ret z
        and 7
        call z,colour_tick
        jr .loop
colour_triple_hl:
        ld de,(V_ARGHL)
        ld b,3
.loop:  ld a,(V_ARGA)
        call colour_fill_mono
        inc de
        djnz .loop
        ret
colour_text_de:
        ld de,(V_ARGDE)
        ld a,227
        jp colour_fill_index
colour_fill_mono:
        push bc
        push de
        push hl
        push af
        ld h,d
        ld l,e
        call colour_address
        nextreg 0x56,a
        pop af
        ld c,a
        ld b,8
.loop:  rlc c
        sbc a,a
        ld (hl),a
        inc hl
        djnz .loop
        jr colour_fill_done
colour_fill_index:
        push bc
        push de
        push hl
        push af
        ld h,d
        ld l,e
        call colour_address
        nextreg 0x56,a
        pop af
        ld b,8
.loop:  ld (hl),a
        inc hl
        djnz .loop
colour_fill_done:
        nextreg 0x56,0
        pop hl
        pop de
        pop bc
        jp colour_finish_byte
colour_border_loop:
        ld a,(V_ARGBC+1)
        ld (V_ROWS),a
.loop:  call colour_left_edge
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        add hl,de
        ld (V_ARGHL),hl
        call colour_right_edge
        ld hl,(V_ARGHL)
        inc hl
        ld (V_ARGHL),hl
        ld a,(V_ROWS)
        dec a
        ld (V_ROWS),a
        ret z
        and 7
        call z,colour_tick
        jr .loop
colour_left_edge:
        ld de,0
        jr colour_edge
colour_right_edge:
        ld de,7
colour_edge:
        ld hl,(V_ARGHL)
        call colour_address
        nextreg 0x56,a
        add hl,de
        ld (hl),255
        nextreg 0x56,0
        ret
; Copy-hook entries and displaced instructions follow.
c_9615:
        COLOUR_ENTRY 4
x_9615:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        inc ix
        nextreg 0x51,255
        jp 0x9619
c_9622:
        COLOUR_ENTRY 5
x_9622:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xDA1B
        nextreg 0x51,255
        jp 0x9627
c_9778:
        COLOUR_ENTRY 6
x_9778:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xD905
        nextreg 0x51,255
        jp 0x977D
c_9783:
        COLOUR_ENTRY 7
x_9783:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xD925
        nextreg 0x51,255
        jp 0x9788
c_97b6:
        COLOUR_ENTRY 8
x_97b6:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        pop de
        nextreg 0x51,255
        jp 0x97B9
c_97e8:
        COLOUR_ENTRY 9
x_97e8:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld c,15
        nextreg 0x51,255
        jp 0x97EC
c_97fb:
        COLOUR_ENTRY 10
x_97fb:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        pop de
        nextreg 0x51,255
        jp 0x97FE
c_983d:
        COLOUR_ENTRY 11
x_983d:
        RESTORE -18
        HLIB_R_OUT
        ld bc,0xF005
        nextreg 0x51,255
        jp 0x9840
c_a3de:
        COLOUR_ENTRY 12
x_a3de:
        RESTORE -23
        HLIB_R_OUT
        lddr
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0x6020
        nextreg 0x51,255
        jp 0xA3E3
c_a5f0:
        COLOUR_ENTRY 13
x_a5f0:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld c,12
        nextreg 0x51,255
        jp 0xA5F4
c_a603:
        COLOUR_ENTRY 14
x_a603:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        pop de
        nextreg 0x51,255
        jp 0xA606
c_a9eb:
        COLOUR_ENTRY 15
x_a9eb:
        RESTORE -22
        HLIB_R_OUT
        lddr
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        nextreg 0x51,255
        ret
c_aa4c:
        COLOUR_ENTRY 16
x_aa4c:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xFD00
        nextreg 0x51,255
        jp 0xAA51
c_aa79:
        COLOUR_ENTRY 17
x_aa79:
        RESTORE -23
        HLIB_R_OUT
        ldir
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        pop de
        nextreg 0x51,255
        jp 0xAA7C
c_960b:
        COLOUR_ENTRY 18
x_960b:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        inc de
        ld a,(ix+0)
        nextreg 0x51,255
        jp 0x9610
c_9610:
        COLOUR_ENTRY 19
x_9610:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        inc de
        ld bc,30
        nextreg 0x51,255
        jp 0x9615
c_9641:
        COLOUR_ENTRY 20
x_9641:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),a
        inc ix
        nextreg 0x51,255
        jp 0x9644
c_964d:
        COLOUR_ENTRY 21
x_964d:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),a
        inc ix
        nextreg 0x51,255
        jp 0x9650
c_96b8:
        COLOUR_ENTRY 22
x_96b8:
        RESTORE -18
        HLIB_R_OUT
        ld a,8
        ld de,32
.loop:  ex af,af'
        ld a,(hl)
        ld (ix+0),a
        inc hl
        add ix,de
        ex af,af'
        dec a
        jr nz,.loop
        nextreg 0x51,255
        jp 0x96C9
c_972d:
        COLOUR_ENTRY 23
x_972d:
        RESTORE -18
        HLIB_R_OUT
        ld a,8
        ld de,32
.loop:  ex af,af'
        ld a,(hl)
        ld (ix+0),a
        inc hl
        add ix,de
        ex af,af'
        dec a
        jr nz,.loop
        nextreg 0x51,255
        jp 0x973E
c_a911:
        COLOUR_ENTRY 24
x_a911:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),a
        inc hl
        ld a,(ix+8)
        nextreg 0x51,255
        jp 0xA916
c_a916:
        COLOUR_ENTRY 25
x_a916:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),a
        add hl,de
        inc ix
        nextreg 0x51,255
        jp 0xA91A
c_9a9b:
        COLOUR_ENTRY 26
x_9a9b:
        RESTORE -18
        HLIB_R_OUT
        ld hl,0x9BFC
        nextreg 0x51,255
        jp 0x9A9E
c_9773:
        COLOUR_ENTRY 27
x_9773:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),255
        ld bc,31
        nextreg 0x51,255
        jp 0x9778
c_a3d9:
        COLOUR_ENTRY 28
x_a3d9:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),0
        ld bc,6912
        nextreg 0x51,255
        jp 0xA3DE
c_979f:
        COLOUR_ENTRY 29
x_979f:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),0
        ld bc,575
        nextreg 0x51,255
        jp 0x97A4
c_97a4:
        COLOUR_ENTRY 30
x_97a4:
        RESTORE -23
        HLIB_R_OUT
        lddr
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xD905
        nextreg 0x51,255
        jp 0x97A9
c_99a0:
        COLOUR_ENTRY 31
x_99a0:
        RESTORE -18
        HLIB_R_OUT
.loop:  ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        add hl,de
        djnz .loop
        nextreg 0x51,255
        jp 0x99A8
c_a5cd:
        COLOUR_ENTRY 32
x_a5cd:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        nextreg 0x51,255
        jp 0xA5D2
c_978d:
        COLOUR_ENTRY 33
x_978d:
        RESTORE -18
        HLIB_R_OUT
.loop:  ld a,(hl)
        or 128
        ld (hl),a
        add hl,de
        ld a,(hl)
        or 1
        ld (hl),a
        inc hl
        djnz .loop
        nextreg 0x51,255
        jp 0x9799
c_b8b6:
        COLOUR_ENTRY 35
x_b8b6:
        RESTORE -17
        HLIB_R_OUT
        ld (de),a
        inc de
        nextreg 0x51,255
        jp 0xB896
c_b8da:
        COLOUR_ENTRY 36
x_b8da:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        ld a,127
        nextreg 0x51,255
        jp 0xB8DD
c_b8de:
        COLOUR_ENTRY 37
x_b8de:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        inc d
        ld b,5
        nextreg 0x51,255
        jp 0xB8E2
c_b8e3:
        COLOUR_ENTRY 38
x_b8e3:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        inc d
        inc hl
        nextreg 0x51,255
        jp 0xB8E6
c_b8ea:
        COLOUR_ENTRY 39
x_b8ea:
        RESTORE -18
        HLIB_R_OUT
        ld (de),a
        pop de
        inc de
        nextreg 0x51,255
        jp 0xB8ED
c_a3af:
        COLOUR_ENTRY 40
x_a3af:
        RESTORE -18
        HLIB_R_OUT
        ld (hl),82
        inc hl
        nextreg 0x51,255
        jp 0xA3B2
c_97dd:
        COLOUR_ENTRY 41
x_97dd:
        RESTORE -23
        HLIB_R_OUT
        lddr
        ld (V_EXIT_A),a
        HLIB_SPEED_OUT_A V_C_SPEED
        ld a,(V_EXIT_A)
        ld hl,0xDB05
        nextreg 0x51,255
        jp 0x97E2
c_b3a4:
        COLOUR_ENTRY 42
x_b3a4:
        RESTORE -18
        HLIB_R_OUT
        ld bc,768
        nextreg 0x51,255
        jp 0xB3A7
colour_room_attributes:
        ; FD00..FF3F is the original attribute buffer, not painted graphics.
        ; Read its original byte values, then reveal the completed room.
        ld hl,(V_ARGHL)
        ld de,0xFF3F
        or a
        sbc hl,de
        jr nz,.general
        ld hl,(V_ARGDE)
        ld de,0x5A3F
        or a
        sbc hl,de
        jr nz,.general
        ld hl,(V_ARGBC)
        ld de,576
        or a
        sbc hl,de
        jr nz,.general
        jp colour_room_attributes_fast
.general:
        ld hl,(V_ARGHL)
        ld de,(V_ARGDE)
        ld bc,(V_ARGBC)
.loop:  ld a,(hl)
        call colour_fill_mono
        push bc
        ld a,(hl)
        ld c,a
        and 7
        ld b,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        cp b
        call z,colour_hide_cell
        pop bc
        dec hl
        dec de
        dec bc
        call colour_copy_tick
        ld a,b
        or c
        jr nz,.loop
        nextreg 0x69,128
        ret
colour_room_attributes_fast:
        ; The complete attribute mirror fits page50. Expand through a
        ; generated byte-to-bits lookup, mapping both pages only once.
        ; Retain the original backward cell order and hidden-cell gate.
        nextreg 0x55,45
        nextreg 0x56,50
        ld hl,0xFF3F
        ld de,0xD1FF
        ld bc,576
.loop:  ld a,(hl)
        push hl
        push bc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0xA807
        add hl,bc
        DUP 8
        ldd
        EDUP
        ld c,a
        and 7
        ld b,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        cp b
        call z,.hidden
        pop bc
        pop hl
        dec hl
        dec bc
        call colour_copy_tick
        ld a,b
        or c
        jr nz,.loop
        nextreg 0x55,5
        nextreg 0x56,0
        nextreg 0x69,128
        ret
.hidden:
        push de
        ld h,d
        ld l,e
        inc hl
        DUP 3
        srl h
        rr l
        EDUP
        set 6,h
        ex de,hl
        call colour_hide_cell
        nextreg 0x56,50
        pop de
        ret
colour_title:
        ; The title colours cycle through the original ULA attributes.
        nextreg 0x69,0
        ret
colour_dispatch:
        dw colour_plot_0,x_9933
        dw colour_plot_1,x_99d1
        dw colour_plot_2,x_9a26
        dw colour_plot_3,x_9a70
        dw colour_copy_up,x_9615
        dw colour_copy_up,x_9622
        dw colour_copy_up,x_9778
        dw colour_copy_up,x_9783
        dw colour_copy_up,x_97b6
        dw colour_copy_up,x_97e8
        dw colour_copy_up,x_97fb
        dw colour_restore_figure,x_983d
        dw colour_copy_down,x_a3de
        dw colour_copy_up,x_a5f0
        dw colour_copy_up,x_a603
        dw colour_copy_down,x_a9eb
        dw colour_copy_up,x_aa4c
        dw colour_copy_up,x_aa79
        dw colour_ix8_de,x_960b
        dw colour_ix_de,x_9610
        dw colour_ix_hl,x_9641
        dw colour_ix_hl,x_964d
        dw colour_tile8,x_96b8
        dw colour_tile8,x_972d
        dw colour_ix_hl,x_a911
        dw colour_ix8_hl,x_a916
        dw colour_commit,x_9a9b
        dw colour_white_hl,x_9773
        dw colour_zero_hl,x_a3d9
        dw colour_zero_hl,x_979f
        dw colour_copy_down,x_97a4
        dw colour_flag_loop,x_99a0
        dw colour_triple_hl,x_a5cd
        dw colour_border_loop,x_978d
        dw 0,0 ; retired per-row right-edge hook
        dw colour_value_de,x_b8b6
        dw colour_text_de,x_b8da
        dw colour_text_de,x_b8de
        dw colour_text_de,x_b8e3
        dw colour_text_de,x_b8ea
        dw colour_red_hl,x_a3af
        dw colour_room_attributes,x_97dd
        dw colour_title,x_b3a4
; The final cache page has 7872 unused bytes after the last shifted figure.
colour_cache_table EQU 0xC200
rom_end:
regblock:
        defs 32,0
        ASSERT $ < 0x3E00
        SAVEBIN "highway_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        ret
        SAVEBIN "highway_setup.bin",setup,$-setup
        ORG 0xD100
colour_setup:
        nextreg 0x64,0
        nextreg 0x12,6
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x15,0
        nextreg 0x14,0xE3
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,143
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,colour_palette
        ld b,0
.palette:
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .palette
        nextreg 0x43,0
        ld bc,0x123B
        xor a
        out (c),a
        ret
colour_palette:
        SAVEBIN "highway_colour_setup.bin",colour_setup,$-colour_setup
