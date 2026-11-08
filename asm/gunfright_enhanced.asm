; Gunfright Enhanced: the default runtime (gunfright_hooks.asm: original renderer at 28 MHz, original-clock
; logic and sound, pace limiter) with the sprite grid replaced by the ordered Layer 2 renderer (gunfright_l2.asm):
; five producer hooks record draw commands, h_out replays them into a hidden double-buffered Layer 2 with the
; owner's painted colours and flips outside the playfield. Assembled to docs/profiles/gunfright_enhanced.json.
        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
HLIB_V_R EQU vr
        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"
h_in:
        ld (saved_sp),sp
        ld sp,0x3FF0           ; private hook stack; no dead game-stack residue
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_IFF_DI
        push af
        HLIB_SPEED_IN_ABC speed
        call l2_in
        call hlib_pace_open
        ld a,1
        ld (active),a
        ld a,114               ; original CALL 1 - entry 10 - exit 5
        call hlib_r_set
        pop af
        HLIB_IFF_EI
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(saved_sp)
        HLIB_R_OUT
        jp exit_in

h_out:
        ld (saved_sp),sp
        ld sp,0x3FF0           ; private hook stack; no dead game-stack residue
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_IFF_DI
        push af
        call hlib_pace_tick
        ld hl,(pace+2)
        ld a,104               ; original render: measured slope ~104.05
        call hlib_mul8
        ld de,448              ; fixed contended-copy allowance, below measured
        ld a,(41577)
        and a
        jr nz,.town_target
        ld de,336              ; duel: measured shorter original render window
.town_target:
        add hl,de              ; 679/16 lines, leaving hook/quantisation margin
        ld (target),hl
        call l2_cost_apply
        call l2_present
        ld hl,(target)
        ld a,(speed)
        call hlib_pace_wait
        HLIB_SPEED_OUT_A speed
        xor a
        ld (active),a
        ld a,114
        call hlib_r_set
        pop af
        HLIB_IFF_EI
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(saved_sp)
        HLIB_R_OUT
        jp exit_out

h_clear:
        ld (saved_sp),sp
        ld sp,0x3FF0           ; private hook stack; no dead game-stack residue
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_IFF_DI
        push af
        HLIB_SPEED_IN_ABC clear_speed
        nextreg 0x15,0
        call l2_hide
        xor a
        ld (grid_valid),a
        ld a,(active)
        and a
        jr z,.normal
        xor a
        ld (active),a
        ld a,(speed)
        ld (clear_speed),a
.normal:
        HLIB_SPEED_OUT_A clear_speed
        ld a,113               ; original LD HL 1 - entry 10 - exit 6
        call hlib_r_set
        pop af
        HLIB_IFF_EI
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(saved_sp)
        HLIB_R_OUT
        jp exit_clear

; Preserve every incoming map. The game stack remains in untouched slot 2.
grid:
        ld a,(upload_init)
        and a
        jr nz,.dma_ready
        ld a,1
        call hlib_dma_init
        ld a,1
        ld (upload_init),a
.dma_ready:
        exx
        push bc
        push de
        push hl
        ld hl,0x8000           ; original mono bytes for exact cache decisions
        exx
        ld a,(41577)
        ld (xoffset),a
        ld hl,0x5825           ; actual original top-left playfield attribute
        add hl,a
        ld a,(hl)
        and 7
        rlca
        rlca
        rlca
        rlca
        ld (ink_bank),a        ; original bright ink, palette bank 0..7
        ld hl,maps
        ld d,0x54
.read:  ld bc,0x243B
        out (c),d
        inc b
        in a,(c)
        ld (hl),a
        inc hl
        inc d
        ld a,d
        cp 0x58
        jr nz,.read
        nextreg 0x54,30
        nextreg 0x55,31
        nextreg 0x56,28
        nextreg 0x57,29
        ld de,0xC000
        ld a,8
        ld (gy),a
        xor a
        ld (tile_id),a
        ld (dirty_count),a
        ld (dirty_max),a
        ld a,120
        ld (dirty_min),a
.tile_row:
        ld a,(xoffset)
        add a,5
        ld (gx),a
        ld a,11
        ld (cols),a
.tile:
        xor a
        ld (changed),a
        ld b,16
        ld a,(gy)
        ld c,a
        and 7
        or 0x40
        ld h,a
        ld a,c
        and 0xC0
        rrca
        rrca
        rrca
        or h
        ld h,a
        ld a,c
        and 0x38
        rlca
        rlca
        ld l,a
        ld a,(gx)
        or l
        ld l,a
.row:
        ld a,(hl)
        inc hl
        ld c,(hl)
        exx
        cp (hl)
        ld (hl),a
        inc hl
        exx
        jr z,.first_same
        ld a,1
        ld (changed),a
.first_same:
        ld a,c
        exx
        cp (hl)
        ld (hl),a
        inc hl
        exx
        jr z,.second_same
        ld a,1
        ld (changed),a
.second_same:
        ; Step the Spectrum ULA address directly. Recomputing it from X/Y
        ; for each of 1,232 tile rows dominated the short duel renderer.
        dec l
        inc h
        ld a,h
        and 7
        jr nz,.next_line
        ld a,l
        add a,32
        ld l,a
        jr c,.next_line
        ld a,h
        sub 8
        ld h,a
.next_line:
        djnz .row
        ld a,(changed)
        and a
        jr z,.clean
        exx
        push hl
        ld de,-32
        add hl,de
        ex de,hl               ; expand directly from this exact cached tile
        pop hl
        exx
        ld b,32
.make:
        exx
        ld a,(de)
        inc de
        exx
        call expand
        djnz .make
        jr .made
.clean:
        ld hl,128
        add hl,de
        ex de,hl
.made:
        ld a,(tile_id)
        ld hl,dirty
        add hl,a
        ld a,(changed)
        ld (hl),a
        and a
        jr z,.not_dirty
        ld hl,dirty_count
        inc (hl)
        ld a,(dirty_max)
        and a
        jr nz,.extend_bounds
        ld a,(gy)
        ld (dirty_min),a
.extend_bounds:
        ld a,(gy)
        add a,16
        ld (dirty_max),a
.not_dirty:
        ld hl,tile_id
        inc (hl)
        ld hl,gx
        inc (hl)
        inc (hl)
        ld hl,cols
        dec (hl)
        jp nz,.tile
        push bc
        push de
        push hl
        call hlib_pace_tick
        pop hl
        pop de
        pop bc
        ld a,(gy)
        add a,16
        ld (gy),a
        cp 120
        jp nz,.tile_row
        ld a,(grid_valid)
        and a
        jr z,.full_bounds
        ld a,(xoffset)
        ld hl,last_xoffset
        cp (hl)
        jr nz,.full_bounds
        ld a,(ink_bank)
        ld hl,last_ink_bank
        cp (hl)
        jr nz,.full_bounds
        ld a,(dirty_count)
        and a
        jp z,.restore          ; identical image and positions: no video writes
        jr .need_publish
.full_bounds:
        ld a,8
        ld (dirty_min),a
        ld a,120
        ld (dirty_max),a
.need_publish:
        ; Measured: 25.43 fixed lines + 1.76 per dirty pattern at 28 MHz.
        ; Reserve 28 + 2 per pattern, at most 182 of the 196 safe lines.
        ld a,(dirty_count)
        add a,a
        add a,28
        ld e,a
        ld d,0
        ld a,(dirty_min)
        ld l,a
        ld h,0
        ld bc,312
        add hl,bc
        and a
        sbc hl,de
        ld (safe_end),hl
        ld a,(dirty_max)
        add a,4
        ld (safe_min),a
.beam:
        call hlib_pace_tick
        ld hl,(pace)
        ld a,(safe_min)
        ld e,a
        ld d,0
        and a
        sbc hl,de
        add hl,de
        jr nc,.same_frame
        ld de,312              ; early next-frame window before dirty rows
        add hl,de
.same_frame:
        ld de,(safe_end)
        and a
        sbc hl,de
        jr nc,.beam
        ld hl,0xC000
        xor a
        ld (tile_id),a
.upload:
        push hl
        ld a,(tile_id)
        ld hl,dirty
        add hl,a
        ld a,(hl)
        pop hl
        and a
        jr z,.skip
        push hl
        ld a,(tile_id)
        rrca                    ; slot index/2, odd -> pattern upper half
        ld bc,0x303B
        out (c),a
        call upload128
        pop hl
.skip:
        ; Entire bounded upload is less than one frame; the wait below takes
        ; the next pace reading. Polling every tile added 50 avoidable lines.
        ld de,128
        add hl,de
        ld a,(tile_id)
        inc a
        ld (tile_id),a
        cp 77
        jr nz,.upload
        ld a,(grid_valid)
        and a
        jr z,.attrs
        ld a,(xoffset)
        ld hl,last_xoffset
        cp (hl)
        jr nz,.attrs
        ld a,(ink_bank)
        ld hl,last_ink_bank
        cp (hl)
        jr z,.attrs_done
.attrs: call attributes
        ld a,(xoffset)
        ld (last_xoffset),a
        ld a,(ink_bank)
        ld (last_ink_bank),a
.attrs_done:
        nextreg 0x15,1
        ld a,1
        ld (grid_valid),a
.restore:
        ld hl,maps
        ld a,(hl)
        nextreg 0x54,a
        inc hl
        ld a,(hl)
        nextreg 0x55,a
        inc hl
        ld a,(hl)
        nextreg 0x56,a
        inc hl
        ld a,(hl)
        nextreg 0x57,a
        exx
        pop hl
        pop de
        pop bc
        exx
        ret

; Compare every original mono byte, retaining the changed tile's source bytes.
cache:
        exx
        cp (hl)
        ld (hl),a
        inc hl
        ld (de),a
        inc de
        exx
        jr z,.same
        ld hl,changed
        ld (hl),1
.same:
        ret

; Four page-aligned tables expand only changed mono tiles to 4bpp.
expand:
        ld l,a
        ld h,0x30
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        ret

attributes:
        xor a
        ld (tile_id),a
        ld a,40                 ; top y 8 + sprite border 32
        ld (gy),a
.r:
        ld a,(xoffset)
        add a,9                 ; (5+offset)*8 + 32
        rlca
        rlca
        rlca
        ld l,a
        ld h,0
        ld (sx),hl
        ld a,11
        ld (cols),a
.c:
        ld a,(tile_id)
        nextreg 0x34,a
        ld hl,(sx)
        ld a,l
        nextreg 0x35,a
        ld a,(gy)
        nextreg 0x36,a
        ld a,(ink_bank)
        or h
        nextreg 0x37,a
        ld a,(tile_id)
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,(tile_id)
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld hl,(sx)
        ld de,16
        add hl,de
        ld (sx),hl
        ld hl,tile_id
        inc (hl)
        ld hl,cols
        dec (hl)
        jr nz,.c
        ld a,(gy)
        add a,16
        ld (gy),a
        cp 152
        jr nz,.r
        ret

pairs: db 0x11,0x12,0x21,0x22
saved_sp: dw 0
last_xoffset: db 0
last_ink_bank: db 0
ink_bank: db 0
speed: db 0
clear_speed: db 0
active: db 0
grid_valid: db 0
target: dw 0
vr: ds 3,0
maps: ds 4,0
xoffset: db 0
dst: dw 0
gx: db 0
gy: db 0
sx: dw 0
yy: db 0
cols: db 0
lines: db 0
changed: db 0
tile_id: db 0
dirty_count: db 0
dirty_min: db 0
dirty_max: db 0
safe_min: db 0
safe_end: dw 0
dirty: ds 77,0
pace: ds 26,0
HLIB_V_PACE EQU pace
HLIB_PACE_NL EQU 312
        INCLUDE "lib/hlib_pace.asm"

; Original 48K game has no DMA users. Synchronous job, mapped immutable source,
; 28 MHz only; shared core/IM2 capability gate fails closed to the CPU.
        DEFINE HLIB_NO_BLITTER
        INCLUDE "lib/hlib_dma.asm"
upload_init: db 0
upload128:
        call hlib_dma_backend
        and a
        jr z,.cpu
        ld (packet_src),hl
        ld hl,packet
        ld bc,(packet_end-packet)*256+0x6B
        otir
        ret
.cpu:  ld bc,0x805B
        DUP 128
        outi
        EDUP
        ret
packet: db 0x83,0xC3,0x7D
packet_src: dw 0
        dw 128
        db 0x14,0x28,0xAD
        dw 0x005B
        db 0x82,0xCF,0x87
packet_end:

        INCLUDE "gunfright_l2.asm"
code_end:
        ASSERT code_end < 0x3900

        ORG 0x3B00
s_in: nextreg 0x51,26
      jp h_in
s_out: nextreg 0x51,26
       jp h_out
s_clear: nextreg 0x51,26
         jp h_clear
exit_in: nextreg 0x51,0xFF
         jp 0xC0BB
exit_out: nextreg 0x51,0xFF
          jp 0xAEA7
exit_clear: nextreg 0x51,0xFF
            ld hl,0x4000
            ret
s_l2_mask: nextreg 0x51,26
 jp h_l2_mask
exit_l2_mask: nextreg 0x51,0xFF
 ld (0xA21D),sp
 jp 0xBE11
s_l2_mirror: nextreg 0x51,26
 jp h_l2_mirror
exit_l2_mirror: nextreg 0x51,0xFF
 ld (0xA21D),sp
 jp 0xBF55
s_l2_scenery: nextreg 0x51,26
 jp h_l2_scenery
exit_l2_scenery: nextreg 0x51,0xFF
 ld (0xA21D),sp
 jp 0xC4AF
s_l2_ground: nextreg 0x51,26
 jp h_l2_ground
exit_l2_ground: nextreg 0x51,0xFF
 ld (0xA21D),sp
 jp 0xC626
s_l2_strip: nextreg 0x51,26
 jp h_l2_strip
exit_l2_strip: nextreg 0x51,0xFF
 ex de,hl
 ld bc,0x6AC6
 jp 0xB28E
tramp_end:
        ORG 0x3DF0
regblock: ds 20,0
        ORG 0x3E80
mono_tile: ds 32,0
        SAVEBIN "gunfright_page.bin",0x2000,0x2000

        ORG 0xD000
setup: nextreg 0x15,0
       nextreg 0x69,0
       nextreg 0x70,0
       nextreg 0x12,16
       nextreg 0x13,19
       nextreg 0x16,0
       nextreg 0x17,0
       nextreg 0x14,0xE3
       nextreg 0x43,0x10
       nextreg 0x40,0
       ld hl,palette
       ld b,32
.pal:  ld a,(hl)
       nextreg 0x44,a
       inc hl
       djnz .pal
       xor a
.hide: nextreg 0x34,a
       nextreg 0x38,0
       inc a
       cp 128
       jr nz,.hide
       ret
palette: db 0,0,0,0,68,0,246,0,196,1,43,0,136,1,248,1,84,1,44,1,236,0,134,1,55,0,146,0,250,0,255,1
setup_end:
        SAVEBIN "gunfright_setup.bin",setup,setup_end-setup
