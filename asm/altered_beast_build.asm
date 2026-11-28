; Assemble both editions from the same source. The unbanked binary is the published default.
        INCLUDE altered_beast_hooks.asm
        SAVEBIN "ab_rom.bin",0x2400,rom_end-0x2400
        SAVEBIN "ab_setup.bin",0xD000,pal-0xD000

        DEFINE AB_BANKED
        MODULE enhanced
        INCLUDE altered_beast_hooks.asm
        ENDMODULE
        SAVEBIN "ab_banked_rom.bin",0x2400,enhanced.rom_end-0x2400
        SAVEBIN "ab_banked_setup.bin",0xD000,enhanced.pal-0xD000

; The level-one reload branch at $75AA is long enough to page in the NEX
; entry bank without using the dying game's stack.
        ORG 0x75AA
ab_game_over:
        di
        nextreg 0x56,20
        nextreg 0x57,21
        jp ab_restore
        SAVEBIN "ab_gameover.bin",ab_game_over,$-ab_game_over

        ORG 0xD200
ab_start:
        nextreg 7,3
        ld d,0                      ; game pages -> private pages 68..84
        ld e,68
        call ab_copy
        nextreg 7,0
        call 0xD000                 ; plain build substitutes RET at D000
        jp 0xD400                   ; optional smooth setup, RET when off

ab_restore:
        ld sp,0xFFFE
        nextreg 7,3
        nextreg 0x8C,0
        ld d,68
        ld e,0
        call ab_copy
        jp 0xC000                   ; original NEX boot, including AY and registers
ab_copy:
        ld a,17                     ; all 16 game pages plus sprite cache page 26
.loop:  push af
        ld a,d
        cp 16
        jr nz,.src
        ld a,26
.src:   nextreg 0x54,a
        ld a,e
        cp 16
        jr nz,.dst
        ld a,26
.dst:   nextreg 0x55,a
        push de
        ld hl,0x8000
        ld de,0xA000
        ld bc,8192
        ldir
        pop de
        inc d
        inc e
        pop af
        dec a
        jr nz,.loop
        nextreg 0x54,4
        nextreg 0x55,5
        ret
        SAVEBIN "ab_restart.bin",ab_start,$-ab_start

TICK          EQU 0x75B6            ; unreachable tail of the level-one reload branch
V_STARTED     EQU 0x8065
V_BEAT        EQU 0x8066
V_LAST        EQU 0x8067
V_OFFSET      EQU 0x8068
PRESENT_LINE  EQU 257

; Resolve one painted pixel. Transparency and paint use the stored orientation.
; The game mask and graphic have already been mirrored into screen order.
        MACRO AB_PIXEL sourcebit, screenbit
        bit 7-sourcebit,b
        jr nz,1F
        ld a,(V_NIB+sourcebit)
        or a
        jr nz,2F
        bit 7-screenbit,c
        ld a,d
        jr nz,2F
        bit 7-screenbit,h
        ld a,e
        jr z,2F
1:      xor a
2:
        ENDM
        MACRO AB_PAIR first, second, pairpos
        AB_PIXEL first,pairpos
        swapnib
        ld l,a
        AB_PIXEL second,(pairpos+1)
        or l
        out (0x5B),a
        ld l,a
        ld a,(V_OR)
        or l
        ld (V_OR),a
        ENDM

        INCLUDE altered_beast_smooth.asm
        SAVEBIN "ab_smooth.bin",smooth_bl,smooth_end-smooth_bl
        MODULE enhanced
        INCLUDE altered_beast_smooth.asm
        ENDMODULE
        SAVEBIN "ab_banked_smooth.bin",enhanced.smooth_bl,enhanced.smooth_end-enhanced.smooth_bl

; Both tables travel together in the toggle. Select the one belonging to the
; already-installed colour edition. Each record is destination, size, bytes.
        ORG 0xD400
smooth_install:
        nextreg 0x62,0
        nextreg 0x26,0
        nextreg 0x1C,4
        nextreg 0x1A,0
        nextreg 0x1A,255
        nextreg 0x1A,0
        nextreg 0x1A,191
        ld hl,smooth_tables
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(0xAE41)
        cp low e_bl
        jr z,.install
        ex de,hl
.install:
        nextreg 0x8C,0xC0
.record:
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,d
        or e
        jr z,.done
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ldir
        jr .record
.done:  nextreg 0x8C,0
        ret
smooth_tables:
        SAVEBIN "ab_install.bin",smooth_install,$-smooth_install
