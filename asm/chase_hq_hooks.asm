; Chase H.Q. (Ocean, 1989; 128K): the hidden-ROM page (alt ROM 0x2000-0x3FFF) of the speed engine and its Enhanced
; colours. nexclash/chase_hq.py places the "rom" block at 0x2000 (bank 12) and "aux" at bank 13 + 0x1100; bank code is
; asm/chase_hq_banks.asm. One source, three sets (games/chase_hq.md):
;   CHQ_SET 0  default: Speed, Enhanced off (enh_enable 0), Orig. pace targets          docs/profiles/chase_hq.json
;   CHQ_SET 1  "Speed" colour set: Enhanced on at the Speed targets                       asm/chase_hq_speed.asm
;   CHQ_SET 2  "Orig. pace" colour set: Enhanced on, the target follows the original      asm/chase_hq_orig.asm
; hlib_pace is the first library (HLIB_PACE_V1), as the published builds were verified with it.
        IFNDEF CHQ_SET
          DEFINE CHQ_SET 0
        ENDIF
; Chase H.Q. 128K: bounded acceleration of road/figure rendering.
; Hooks and setup only. Original sound, input and game logic are unmodified.
        DEVICE ZXSPECTRUMNEXT
V_R         EQU 0x1F00
V_SPEED     EQU 0x1F10
V_MAP       EQU 0x1F11
HLIB_V_R    EQU V_R
HLIB_V_PACE EQU 0x1F20
HLIB_PACE_NL EQU 311
        IF CHQ_SET == 1
PACE_TARGET_E EQU 21120
        ELSE
PACE_TARGET_E EQU 23250
        ENDIF
ATTRACT_TARGET_E EQU 20992
TUNNEL_TARGET_E EQU 21120
        IF CHQ_SET == 1
INTRO_COPY_TARGET_E EQU 1
        ELSE
INTRO_COPY_TARGET_E EQU 4065
        ENDIF
        IF CHQ_SET == 2
PACE_A EQU 159
PACE_B EQU 13
PACE_D EQU 3145
V_GEO EQU 0x1F40
V_PIX EQU 0x1F42
V_WS EQU 0x1F44
V_WAITS EQU 0x1F46
V_W0 EQU 0x1F48
V_TGT EQU 0x1F4A
        ENDIF
PACE_TARGET EQU 21120 ; 1320 raster lines ~= 85.99 ms, excluding synchronous SFX
        INCLUDE "lib/hlib_speed.asm"
; Source-keyed colour rows over the original renderer, in its original order.
; All writes go to an undisplayed Layer 2 buffer; commit follows the ULA copy.
E_SP        EQU 0x1D00
E_R         EQU 0x1D02
E_SPEED     EQU 0x1D03
E_MAP2      EQU 0x1D04
E_MAP3      EQU 0x1D05
E_DEST      EQU 0x1D06
E_WIDTH     EQU 0x1D08
E_MASKED    EQU 0x1D09
E_MIRROR    EQU 0x1D0A
E_PAGE      EQU 0x1D0B
E_SOURCE    EQU 0x1D0C
E_TICK      EQU 0x1D0E
E_PENDING   EQU 0x1D0F
E_FHEIGHT   EQU 0x1D10
E_FCOUNT    EQU 0x1D11
E_FDEST     EQU 0x1D12
E_FSPEED    EQU 0x1D14
E_PSRC      EQU 0x1D16
E_PDEST     EQU 0x1D18
E_PCOUNT    EQU 0x1D1A
E_SOLID     EQU 0x1D1B
E_LENGTH    EQU 0x1D1C
E_OEND      EQU 0x1D1E
E_GAP       EQU 0x1D20
E_START     EQU 0x1D21
E_END       EQU 0x1D22
E_BACK      EQU 0x1D80
E_INIT      EQU 0x1D81
E_Y         EQU 0x1D82
E_X         EQU 0x1D83
E_HORIZON   EQU 0x1D84
E_LEFT      EQU 0x1D85
E_RIGHT     EQU 0x1D86
E_VALUE     EQU 0x1D87
E_TYPE      EQU 0x1D88
E_LBYTE     EQU 0x1D89
E_RBYTE     EQU 0x1D8A
E_MAP4      EQU 0x1D8B
E_PREVH     EQU 0x1D8C
E_FORCE     EQU 0x1D8D
E_DLINE     EQU 0x1D8E
E_DMA       EQU 0x1D90
E_FILL      EQU 0x1DA8
        ORG 0x2000
        MACRO ROW_SAVE
        nextreg 0x50,26
        ld (E_SP),sp
        ld sp,0x1CE0
        push af
        push bc
        push de
        push hl
        push ix
        ld a,r
        ld (E_R),a
        ENDM
        MACRO ROW_RESTORE delta
        ld a,(E_R)
        ld c,a
        add a,delta
        and 127
        ld b,a
        ld a,c
        and 128
        or b
        ld r,a
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(E_SP)
        nextreg 0x50,255
        ENDM
colour_maps_in:
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        ld (E_MAP2),a
        dec b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (E_MAP3),a
        ret
colour_maps_out:
        ld a,(E_MAP2)
        nextreg 0x52,a
        ld a,(E_MAP3)
        nextreg 0x53,a
        ret
colour_row:
        ld a,(E_INIT)
        or a
        ret z
        ld a,(E_WIDTH)
        or a
        ret z
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (E_SPEED),a
        cp 3
        jr z,.fast
        nextreg 0x07,3
.fast:
        ld a,(E_TICK)
        inc a
        and 15
        ld (E_TICK),a
        IF CHQ_SET == 2
        call z,tick_row
        ELSE
        call z,tick
        ENDIF
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in e,(c)
        dec b
        inc a
        out (c),a
        inc b
        in d,(c)
        dec b
        inc a
        out (c),a
        inc b
        in a,(c)
        ld (A_MAP4),a
        ld (E_MAP2),de
        push de
        push af
        nextreg 0x52,56
        call 0x4800
        pop af
        nextreg 0x54,a
        pop de
        ld a,e
        nextreg 0x52,a
        ld a,d
        nextreg 0x53,a
        ld a,(E_SPEED)
        cp 3
        ret z
        nextreg 0x07,a
        ret

colour_font_enter:
        ROW_SAVE
        ld hl,(E_SP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(de)
        ld (E_FHEIGHT),a
        inc de
        ld (hl),d
        dec hl
        ld (hl),e
        ROW_RESTORE -27
        ret
colour_font_copy:
        ROW_SAVE
        ld hl,(E_SP)
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        cp 0xF0
        jr c,.done
        ld a,(E_INIT)
        or a
        jr z,.done
        ld (E_FDEST),de
        HLIB_SPEED_IN E_FSPEED
        ld a,(E_FHEIGHT)
        ld (E_FCOUNT),a
.row:
        ld hl,(E_FDEST)
        ld (E_DEST),hl
        ld a,(hl)
        ld l,a
        ld h,0
        ld a,(0x1C93)
        or a
        jr z,.normal_paper
        ld h,1              ; black ink on the original cyan label colour
.normal_paper:
        ld (E_SOURCE),hl
        ld a,1
        ld (E_WIDTH),a
        ld a,2
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ld hl,(E_FDEST)
        inc h
        ld (E_FDEST),hl
        ld a,(E_FCOUNT)
        dec a
        ld (E_FCOUNT),a
        jr nz,.row
        HLIB_SPEED_OUT E_FSPEED
.done:
        ROW_RESTORE -27
        ret
colour_portrait:
        ROW_SAVE
        ld (E_PSRC),hl
        ld (E_PDEST),de
        ld a,4
        ld (E_PCOUNT),a
        HLIB_SPEED_IN E_FSPEED
.byte:
        ld hl,(E_PDEST)
        ld (E_DEST),hl
        ld hl,(E_PSRC)
        ld (E_SOURCE),hl
        ld a,1
        ld (E_WIDTH),a
        ld a,3
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ld hl,(E_PSRC)
        dec hl
        ld (E_PSRC),hl
        ld hl,(E_PDEST)
        dec hl
        ld (E_PDEST),hl
        ld a,(E_PCOUNT)
        dec a
        ld (E_PCOUNT),a
        jr nz,.byte
        HLIB_SPEED_OUT E_FSPEED
        ROW_RESTORE -25
        ld a,e
        ldd
        jp 0x8EC0
colour_occlude:
        ROW_SAVE
        call colour_occlude_body
        ROW_RESTORE -25
        ld sp,hl
        push de
        push de
        jp 0xC2C4
colour_occlude_pattern:
        ROW_SAVE
        call colour_occlude_body
        ROW_RESTORE -25
        ld sp,hl
        push de
        push de
        jp 0xC28A
colour_occlude_body:
        ld a,d
        ld (E_SOLID),a
        ld a,l
        sub 30
        ld l,a
        ld bc,240
        HLIB_SPEED_IN E_FSPEED
        call colour_span
        HLIB_SPEED_OUT E_FSPEED
        ret
colour_occlude_sides:
        ROW_SAVE
        ld a,d
        ld (E_SOLID),a
        ld (E_OEND),hl
        ld a,c
        ld (E_GAP),a
        ld a,(E_INIT)
        or a
        jr z,.done
        HLIB_SPEED_IN E_FSPEED
        ld a,(0xC222)
        neg
        add a,16
        add a,a
        ld c,a
        ld b,0
        ld a,(E_GAP)
        add a,l
        ld l,a
        or a
        sbc hl,bc
        call colour_black_span
        ld hl,(E_OEND)
        ld a,(0xC237)
        neg
        add a,16
        add a,a
        ld c,a
        ld b,0
        or a
        sbc hl,bc
        call colour_black_span
        HLIB_SPEED_OUT E_FSPEED
.done:
        ROW_RESTORE -25
        add a,c
        ld l,a
        ld a,h
        jp 0xC24B
colour_black_span:
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
colour_span:
        ld a,(E_INIT)
        or a
        ret z
        ld a,b
        or c
        ret z
        ld a,h
        cp 0xF0
        ret c
        ld (E_DEST),hl
        ld (E_LENGTH),bc
        call colour_maps_in
        ld hl,(E_DEST)
        ld a,h
        and 15
        ld d,a
        ld a,l
        and 224
        rrca
        or d
        ld (E_Y),a
        and 96
        rlca
        rlca
        rlca
        ld e,a
        ld a,(E_BACK)
        add a,2
        add a,e
        nextreg 0x53,a
        ld a,(E_Y)
        and 31
        or 0x60
        ld d,a
        ld a,l
        and 31
        rlca
        rlca
        rlca
        ld e,a
        ld (E_START),a
        ld (E_DLINE),de
        ld bc,(E_LENGTH)
        add a,c
        dec a
        ld (E_END),a
        ld a,(E_SOLID)
        cp 255
        ld a,1
        jr z,.whole
        ld a,(E_HORIZON)
        ld b,a
        ld a,(E_Y)
        cp b
        ld a,247
        jr c,.whole
        ld a,248
.whole: ld (E_FILL),a
        ld bc,(E_LENGTH)
        call colour_base.fill
        ld a,(E_FILL)
        cp 248
        jr nz,.ink
        ld a,(E_Y)
        add a,a
        ld l,a
        ld h,0xE8
        call colour_base.clamp
        ld b,a
        ld a,(E_START)
        cp b
        jr nc,.left
        ld a,b
.left:  ld (E_LEFT),a
        ld h,0xEC
        call colour_base.clamp
        ld b,a
        ld a,(E_END)
        cp b
        jr c,.right
        ld a,b
.right: ld b,a
        ld a,(E_LEFT)
        cp b
        jr nc,.ink
        ld de,(E_DLINE)
        ld e,a
        ld a,b
        sub e
        inc a
        ld c,a
        ld b,0
        ld a,246
        ld (E_FILL),a
        call colour_base.fill
.ink:
        ld a,(E_SOLID)
        or a
        jr z,.unmap
        cp 255
        jr z,.unmap
        ld l,a
        rlca
        rlca
        rlca
        and 7
        add a,48
        nextreg 0x52,a
        ld a,l
        and 31
        or 0x40
        ld h,a
        ld l,0
        ld de,(E_DLINE)
        ld bc,(E_LENGTH)
        xor a
        ldirx
.unmap:
        call tick
        call colour_maps_out
        ret
colour_row_b726:
        ROW_SAVE
        
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_b726
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,1
        ld (E_MASKED),a
        ld a,0
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld c,l
        jp (ix)

colour_row_b798:
        ROW_SAVE
        ex de,hl
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_b798
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,1
        ld (E_MASKED),a
        ld a,1
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld a,e
        ex af,af'
        jp (ix)

colour_row_94c5:
        ROW_SAVE
        
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_94c5
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,0
        ld (E_MASKED),a
        ld a,0
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld a,l
        jp (ix)

colour_row_9517:
        ROW_SAVE
        
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_9517
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,0
        ld (E_MASKED),a
        ld a,0
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld a,l
        jp (ix)

colour_row_9571:
        ROW_SAVE
        
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_9571
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,0
        ld (E_MASKED),a
        ld a,1
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld a,l
        ex af,af'
        jp (ix)

colour_row_95da:
        ROW_SAVE
        
        ld (E_DEST),hl
        push ix
        pop hl
        ld h,high count_95da
        ld a,(hl)
        ld (E_WIDTH),a
        ld a,0
        ld (E_MASKED),a
        ld a,1
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -24
        ld a,l
        ex af,af'
        jp (ix)

colour_row_9e4e:
        ROW_SAVE
        ld (E_DEST),hl
        ld a,2
        ld (E_WIDTH),a
        ld a,1
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -25
        pop de
        ld a,(hl)
        and e
        jp 0x9E51

colour_static_8f13:
        ROW_SAVE
        ld (E_DEST),hl
        ld hl,129
        ld (E_SOURCE),hl
        ld a,1
        ld (E_WIDTH),a
        ld a,2
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -25
        ld (hl),129
        ld a,h
        jp 36630

colour_static_8f28:
        ROW_SAVE
        ld (E_DEST),hl
        ld hl,129
        ld (E_SOURCE),hl
        ld a,1
        ld (E_WIDTH),a
        ld a,2
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -25
        ld (hl),129
        ld a,h
        jp 36651

colour_static_8f47:
        ROW_SAVE
        ld (E_DEST),hl
        ld hl,255
        ld (E_SOURCE),hl
        ld a,1
        ld (E_WIDTH),a
        ld a,2
        ld (E_MASKED),a
        xor a
        ld (E_MIRROR),a
        call colour_row
        ROW_RESTORE -25
        ld (hl),255
        ld a,h
        jp 36682

colour_font_a004:
        call colour_font_enter
        db 14
        push de
        ld b,4
        jp 40967

colour_font_a023:
        call colour_font_enter
        db 14
        push de
        ld b,7
        jp 40998

colour_font_a031:
        call colour_font_enter
        db 7
        push de
        ld b,7
        jp 41012

colour_font_a03d:
        call colour_font_enter
        db 16
        push de
        xor a
        ld (de),a
        jp 41024

colour_font_a083:
        call colour_font_enter
        db 9
        push de
        xor a
        ld (de),a
        jp 41094

colour_font_exit_a074:
        call colour_font_copy
        pop de
        inc e
        exx
        jp 41079

colour_font_exit_a0a4:
        call colour_font_copy
        pop de
        inc e
        exx
        jp 41127

 ALIGN 256
count_b726:
count_b798:
        db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,8,0,0,0,0,0,7,0,0,0,0,0,6,0,0,0,0,0,5,0,0,0,0
        db 0,4,0,0,0,0,0,3,0,0,0,0,0,2,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,8,0,0,0,0,0,0,0,7,0,0,0,0,0,0,0,6,0,0,0,0,0,0,0,5,0,0,0,0,0,0,0,4,0,0,0
        db 0,0,0,0,3,0,0,0,0,0,0,0,2,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0

count_94c5:
count_9517:
count_9571:
count_95da:
        db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,7,0,0,0,0,5,0,0,0,0,3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,8,0,0,0,0,0,0,0,0,6,0
        db 0,0,0,0,0,0,0,4,0,0,0,0,0,0,0,0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        db 0,0,0,0,0,0,0,0,8,0,0,0,0,6,0,0,0,0,4,0,0,0,0,2,0,0,0,0,0,0,7,0,0,0,0,0,0,0,0,5,0,0,0,0,0,0,0,0,3,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0


        ASSERT $ <= 0x2A00
        ORG 0x2A00
rom_start:

        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_V1
        INCLUDE "lib/hlib_pace.asm"

; Hook RAM is mapped only inside hooks. The original road renderer uses SP as
; a drawing pointer and deliberately writes into ROM for clipped road rows.
; Those writes MUST still be discarded: restore MMU0 before every original body.
map_state:
        ld bc,0x243B
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        nextreg 0x50,26
        ld (V_MAP),a
        ret
tick:
        IF CHQ_SET == 2
        jp tick2
        ds 5
        ELSE
        ld a,(HLIB_V_PACE+10)
        or a
        ret z
        jp hlib_pace_tick
        ENDIF

        MACRO ENTER mode
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
        IF mode == 1
          call hlib_pace_open
          ld hl,0
          ld (HLIB_V_PACE+4),hl ; no catch-up following a slow/sound frame
        ELSE
          call tick
        ENDIF
        IF mode == 5
          call review_end
        ENDIF
        IF mode == 4
          call colour_disable
        ENDIF
        IF mode == 3
          call pace_final
        ENDIF
        IF mode != 0
          HLIB_SPEED_OUT V_SPEED
        ENDIF
        ENDM
        MACRO RESTORE_ENTRY
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
        MACRO EXIT_FULL variant
        push af
        push bc
        push de
        push hl
        ld a,r
        push af
        call map_state
        nextreg 7,3
        IF variant == 1
        IF CHQ_SET == 2
          call win_pix
        ELSE
          call colour_base
        ENDIF
          call motion_display
        ENDIF
        IF variant == 4
        IF CHQ_SET == 2
          call win_geo
        ELSE
          call motion_step
        ENDIF
        ENDIF
        IF variant == 5
          call motion_history
        ENDIF
        IF variant == 7
          call colour_commit
          call motion_finish
          call pace_attract
        ENDIF
        IF variant == 6
          call colour_commit
          call motion_finish
          HLIB_SPEED_OUT V_SPEED
          ld hl,18374 ; 74.808 ms: native original 877B..879C minimum 74.805 ms
          ld a,(V_SPEED)
          call hlib_pace_wait
        ENDIF
        IF variant == 8
          ld hl,INTRO_COPY_TARGET_E
          call pace_wait_e
        ENDIF
        IF variant == 2
          call colour_commit
          call motion_finish
        ENDIF
        IF variant == 3
          call colour_late_base
        ENDIF
        call tick
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld (V_R),a
        IF variant == 0
          ld a,-17
        ELSE
          ld a,-15
        ENDIF
        call hlib_r_set
        HLIB_R_OUT
        ld a,(V_MAP)
        nextreg 0x50,a
        pop hl
        pop de
        pop bc
        pop af
        ENDM
        MACRO EXIT variant
        IF variant == 0
          call shared_exit
        ELSE
          EXIT_FULL variant
        ENDIF
        ENDM

; Replace a CALL target, keeping the original body's SP exactly unchanged.
; The original RET lands at the corresponding exit; its dead return word is
; the only original stack byte intentionally changed by the trampoline.
        MACRO TRANSPARENT name, exitname, body, resume, mode
name:
        ENTER mode
        ld hl,8
        add hl,sp
        ld (hl),low exitname
        inc hl
        ld (hl),high exitname
        IF body == 0xC452
          xor a
          ld (0x1C90),a
        ENDIF
        RESTORE_ENTRY
        jp body
exitname:
        IF body == 0xA0D6
          EXIT 5
        ELSE
        IF body == 0xB9F4
          EXIT 4
        ELSE
        IF body == 0xC452
          EXIT 1
        ELSE
          IF body == 0xBC3E
            IF resume == 0x8282
              EXIT 7
            ELSE
            IF resume == 0x879C
              EXIT 6
            ELSE
              EXIT 2
            ENDIF
            ENDIF
          ELSE
            IF body == 0xC0E1
              EXIT 3
            ELSE
              EXIT 0
            ENDIF
          ENDIF
        ENDIF
        ENDIF
        ENDIF
        jp resume
        ENDM

        TRANSPARENT player_draw,player_draw_exit,0xB318,0x84A4,0
        TRANSPARENT road_effect,road_effect_exit,0xC0E1,0x847D,0
        TRANSPARENT hud_draw,hud_draw_exit,0x9D62,0x84AA,0
        TRANSPARENT damage_draw,damage_draw_exit,0x8EE7,0x84B6,0
        TRANSPARENT colour_stage,colour_stage_exit,0x8014,0x8404,4
        TRANSPARENT colour_end,colour_end_exit,0x83BB,0x873F,5
        TRANSPARENT road_geometry,road_geometry_exit,0xB9F4,0x846E,0
        TRANSPARENT road_pixels,road_pixels_exit,0xC452,0x8474,0
        TRANSPARENT scenery,scenery_exit,0x8F5F,0x849E,0
        TRANSPARENT screen_copy,screen_copy_exit,0xBC3E,0x84BF,0
        TRANSPARENT open_frame,open_frame_exit,0xA0D6,0x844A,1
        TRANSPARENT wait_frame,wait_frame_exit,0xBB69,0x84C2,3

; The short sound-maintenance call has no SP operands. The original still
; executes at the incoming speed. All ten inter-draw calls share this hook.
sound_tick:
        ENTER 0
        ld a,(enh_enable)
        or a
        jr z,.base
        call iff_off            ; 1.3: read twice (iff_off); was LD A,I / JP PO,.fast, same length
        jr c,.fast
        HLIB_SPEED_OUT V_SPEED
.fast:
        ld a,(E_PENDING)
        cp 1
        call nz,sound_cadence
        HLIB_SPEED_OUT V_SPEED
        RESTORE_ENTRY
        jp 0x83B8
.base:
        HLIB_SPEED_OUT V_SPEED
        call sound_cadence
        RESTORE_ENTRY
        call 0x83B8
        EXIT 0
        ret

; Do not bunch the ten siren updates at the beginning of an accelerated draw.
; Preserve their positions within the original best quiet render window.
; Targets are sixteenths of 128K raster lines, measured at each call in the
; original native trial (update 176, 84.751 ms render window). The final cap is
; deliberately a little slower. No debt/catch-up is carried between checkpoints.
sound_cadence:
        ld a,(HLIB_V_PACE+10)
        or a
        ret z
        ld hl,10               ; helper CALL + four saved register pairs
        add hl,sp
        ld a,(hl)              ; low byte of the original return address
        ld hl,cadence_table
.find:  cp (hl)
        jr z,.found
        inc hl
        inc hl
        inc hl
        jr .find
.found: inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld a,(V_SPEED)
        IF CHQ_SET == 2
        call wait_counted
        ELSE
        call hlib_pace_wait
        ENDIF
        ld hl,0
        ld (HLIB_V_PACE+4),hl
        ld a,1
        ld (HLIB_V_PACE+10),a
        ret
cadence_table:
        db 0x62
        dw 714
        db 0x6B
        dw 1275
        db 0x71
        dw 5174
        db 0x77
        dw 11399
        db 0x89
        dw 11751
        db 0x92
        dw 11943
        db 0x9B
        dw 11988
        db 0xA1
        dw 14641
        db 0xB0
        dw 16565
        db 0xBC
        dw 16737

; The renderer can READ the printer buffer too. After the RAM startup tail has
; restored the snapshot registers, finish here in ROM and restore all 256 bytes,
; including the tail itself. No permanent game-RAM allocation is required.
boot_resume:
        di
        nextreg 0x50,26
        ld (0x1F14),sp
        ld sp,0x1EF0
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
        nextreg 7,0
        ld a,-23
        call hlib_r_set
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(0x1F14)
        nextreg 0x50,255
boot_iff:
        ei
boot_jump:
        jp 0
printer_saved:
        ds 256,0
regblock:
        ds 20,0
S_SP        EQU 0x1D30
S_R         EQU 0x1D32
S_MAP2      EQU 0x1D33
S_MAP3      EQU 0x1D34
S_MAP4      EQU 0x1D35
S_ACTIVE    EQU 0x1D36
S_ANGLE     EQU 0x1D37
S_TARGET    EQU 0x1D38
S_VALID     EQU 0x1D39
S_REQ       EQU 0x1D3A
S_BOUNCE    EQU 0x1D3B
S_PAGE      EQU 0x1D3C
S_COUNT     EQU 0x1D3D
S_INIT      EQU 0x1D3E
S_FRAME     EQU 0x1D40
S_BACKUP    EQU 0x1800
S_STACK     EQU 0x1BE0

; Independent private stack/state: this hook nests inside player_draw and the
; original B58E body in turn enters the existing row hooks.
        MACRO STEER_SAVE
        nextreg 0x50,26
        ld (S_SP),sp
        ld sp,S_STACK
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        ld a,r
        ld (S_R),a
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        ld (S_MAP2),a
        dec b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (S_MAP3),a
        dec b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        ld (S_MAP4),a
        nextreg 0x52,56
        ENDM
        MACRO STEER_RESTORE
        ld a,(S_MAP4)
        nextreg 0x54,a
        ld a,(S_MAP3)
        nextreg 0x53,a
        ld a,(S_MAP2)
        nextreg 0x52,a
        ld a,(S_R)
        ld c,a
        add a,-28
        and 127
        ld b,a
        ld a,c
        and 128
        or b
        ld r,a
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(S_SP)
        nextreg 0x50,255
        ENDM
steering_enter:
        STEER_SAVE
        call 0x4000
        ld hl,(S_SP)
        ld (hl),low steering_exit
        inc hl
        ld (hl),high steering_exit
        STEER_RESTORE
        jp 0xB58E
steering_exit:
        STEER_SAVE
        call 0x4003
        STEER_RESTORE
        jp 0xB421

A_MAP4      EQU 0x1D50
A_STAGE     EQU 0x1D51
A_SOURCE    EQU 0x1D52
A_DEST      EQU 0x1D54
A_FLAG      EQU 0x1D56
A_LOOKUP    EQU 0x1D57
A_CPAGE     EQU 0x1D58
A_CPTR      EQU 0x1D59
A_CACHED    EQU 0x1D5B
A_MAP5      EQU 0x1D5C
A_CMAP3     EQU 0x1D5D
A_COPYINDEX EQU 0x1D5E
A_LPTR      EQU 0x1D60
A_COUNT     EQU 0x1D62

polish_sky_source:
        ROW_SAVE
        ld a,1
        ld (0x1C90),a
        ld a,d
        and 15
        ld b,a
        ld a,e
        and 224
        rrca
        or b
        ld (0x1C91),a
        ROW_RESTORE -25
        add hl,bc
        exx
        add a,a
        jp 0xC7F5

motion_history:
        ld hl,24579
        jr motion_call
motion_display:
        ld hl,24989
        jr motion_call
motion_step:
        ld hl,24672
        jr motion_call
motion_finish:
        ld hl,24576
motion_call:
        ld a,(E_INIT)
        or a
        ret z
        push ix
        push iy
        push hl
        call colour_maps_in
        nextreg 0x52,56
        nextreg 0x53,57
        pop hl
        ld de,motion_return
        push de
        jp (hl)
motion_return:
        call colour_maps_out
        pop iy
        pop ix
        ret

review_over_geometry:
        ; Only open the window: the original geometry keeps its own speed and
        ; return address. No intermediate road pose is needed during game over.
        ENTER 1
        RESTORE_ENTRY
        jp 0xB9F4
        TRANSPARENT review_over_pixels,review_over_pixels_exit,0xC452,0x8781,0
        TRANSPARENT review_over_effect,review_over_effect_exit,0xC0E1,0x8787,0
        TRANSPARENT review_over_scenery,review_over_scenery_exit,0x8F5F,0x8790,0
        TRANSPARENT review_over_hud,review_over_hud_exit,0x9D62,0x8793,0
        TRANSPARENT review_over_message,review_over_message_exit,0x8D8F,0x8799,0
        TRANSPARENT review_over_copy,review_over_copy_exit,0xBC3E,0x879C,0
review_normal:
        ld a,(0x1C93)
        or a
        ld a,63
        jr nz,review_clip
        ld a,63
        jr review_clip
review_end:
        ld a,1
        ld (0x1C93),a
        xor a
        ld (0x1CA3),a
        ld (0x1CAB),a
        ; The original message occupies HUD rows 50..63. Reveal it.
        ld a,63
review_clip:
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,a
        ret
review_menu:
        ROW_SAVE
        HLIB_SPEED_IN E_SPEED
        call colour_disable
        HLIB_SPEED_OUT E_SPEED
        ROW_RESTORE -25
        ld hl,0xC000
        jp 0x8212
attract_open:
        ENTER 1
        ld a,1
        ld (0x1C95),a
        RESTORE_ENTRY
        jp 0x852A
        TRANSPARENT attract_geometry,attract_geometry_exit,0xB9F4,0x856B,0
        TRANSPARENT attract_pixels,attract_pixels_exit,0xC452,0x856E,0
        TRANSPARENT attract_effect,attract_effect_exit,0xC0E1,0x8574,0
        TRANSPARENT attract_scenery,attract_scenery_exit,0x8F5F,0x8589,0
        TRANSPARENT attract_player,attract_player_exit,0xB318,0x822B,0
        TRANSPARENT attract_message,attract_message_exit,0x8D8F,0x827F,0
        TRANSPARENT attract_copy,attract_copy_exit,0xBC3E,0x8282,0
        TRANSPARENT attract_menu,attract_menu_exit,0x81AA,0x8215,4
shared_exit:
        EXIT_FULL 0
        ret
hud_menu:
        ROW_SAVE
        HLIB_SPEED_IN E_FSPEED
        xor a
        ld (0x1C6E),a
        call colour_disable
        HLIB_SPEED_OUT E_FSPEED
        ROW_RESTORE -25
        ld (0x81C6),hl
        jp 0x81AD
hud_intro:
        ROW_SAVE
        ld a,(enh_enable)
        or a
        jp z,.off
        HLIB_SPEED_IN E_FSPEED
        xor a
        ld (0x1C6E),a
        ld a,1
        ld (0x1C96),a
        call colour_maps_in
        ld a,(0x8007)
        ld (A_STAGE),a
        call colour_init
        call colour_maps_out
        ld a,1
        ld (0x1C96),a
        ld a,63
        call hud_clip
        nextreg 0x12,16
        nextreg 0x69,128
        nextreg 0x62,0
        nextreg 0x43,0
        nextreg 0x26,0
        nextreg 0x27,0
        nextreg 0x16,0
        nextreg 0x17,0
        HLIB_SPEED_OUT E_FSPEED
.off:
        ROW_RESTORE -25
        ld a,0xF8
        ld (0xA220),a
        jp 0x8597
hud_full_clip:
        ld a,(0x1C96)
        or a
        ret z
        xor a
        ld (0x1C96),a
        call hud_rows_call
        ld a,191
hud_clip:
        nextreg 0x1C,1
        nextreg 0x18,8
        nextreg 0x18,247
        nextreg 0x18,0
        nextreg 0x18,a
        ret
hud_intro_copy:
        ENTER 0
        ld a,(enh_enable)
        or a
        jr z,.base
        call hlib_pace_open
        call hud_message_call
        ld hl,8
        add hl,sp
        ld (hl),low hud_intro_copy_exit
        inc hl
        ld (hl),high hud_intro_copy_exit
        RESTORE_ENTRY
        jp 0xBC3E
.base:
        call hud_message_call
        HLIB_SPEED_OUT V_SPEED
        RESTORE_ENTRY
        jp 0xBC3E
hud_intro_copy_exit:
        EXIT 8
        jp 0x85BA
hud_portrait:
        ROW_SAVE
        ld (0x1C60),hl
        ld a,(E_INIT)
        or a
        jr z,.done
        ld a,d
        cp 0x40
        jr nz,.done
        ld a,e
        cp 0x36
        jr nz,.done
        HLIB_SPEED_IN E_FSPEED
        ld hl,0x4003
        call hud_call
        HLIB_SPEED_OUT E_FSPEED
.done:
        ROW_RESTORE -25
        ld bc,160
        jp 0x9AAE
hud_static:
        ROW_SAVE
        ld a,(E_INIT)
        or a
        jr z,.done
        HLIB_SPEED_IN E_FSPEED
        ld hl,0x4006
        call hud_call
        HLIB_SPEED_OUT E_FSPEED
.done:
        ROW_RESTORE -25
        ld de,0x4036
        jp 0x9A6E
hud_init_call:
        ld hl,0x4000
        jr hud_call
hud_message_call:
        ld hl,0x4009
        jr hud_call
hud_rows_call:
        ld hl,0x400C
hud_call:
        push ix
        ld bc,0x243B
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x52,16
        ld de,hud_return
        push de
        jp (hl)
hud_return:
        pop af
        nextreg 0x54,a
        pop af
        nextreg 0x53,a
        pop af
        nextreg 0x52,a
        pop ix
        ret

; Pace waits. Default set: the game's clock and the Speed targets, as before.
pace_final:
        ld hl,PACE_TARGET
        ld a,(enh_enable)
        or a
        jr z,pace_wait_e
        IF CHQ_SET == 2
        call pace_follow
        ELSE
        ld hl,PACE_TARGET_E
        ENDIF
        ld a,(E_PENDING)
        cp 0x80
        jr nz,pace_wait_e
        xor a
        ld (E_PENDING),a
        IF CHQ_SET == 2
        ld hl,(V_TGT)
        ELSE
        ld hl,TUNNEL_TARGET_E
        ENDIF
        jr pace_wait_e
pace_attract:
        ld hl,20992 ; original 8228..8282 quiet window: 85.465 ms
        ld a,(enh_enable)
        or a
        jr z,pace_wait_e
        ld hl,ATTRACT_TARGET_E
pace_wait_e:
        ld a,(enh_enable)
        or a
        jr z,.game_clock
        call iff_off            ; 1.3: read twice (iff_off); was LD A,I / JP PO,.go, same length
        jr c,.go
.game_clock:
        HLIB_SPEED_OUT V_SPEED
.go:
        ld a,(V_SPEED)
        jp hlib_pace_wait
enh_enable:
        IF CHQ_SET == 0
        db 0
        ELSE
        db 1
        ENDIF
        IF CHQ_SET == 2
; Chase H.Q. 1.2, Orig. pace: the final target follows the original's time for this update (games/chase_hq.md "Pace")
tick2:
        ld a,(HLIB_V_PACE+10)
        or a
        ret z
        call hlib_pace_tick
        ld (V_WS),hl
        ret
tick_row:
        ld a,(HLIB_V_PACE+10)
        or a
        ret z
        jp hlib_pace_tick
win_geo:
        call win_read
        ld (V_GEO),hl
        jp motion_step
win_pix:
        call win_read
        ld (V_PIX),hl
        jp colour_base
win_read:
        ld de,(V_WS)
        push de
        call tick_row
        pop de
        ld hl,(HLIB_V_PACE+2)
        or a
        sbc hl,de
        ret
wait_counted:
        ld de,(HLIB_V_PACE+2)
        ld (V_W0),de
        call hlib_pace_wait
        ld hl,(HLIB_V_PACE+2)
        ld de,(V_W0)
        or a
        sbc hl,de
        ld de,(V_WAITS)
        add hl,de
        ld (V_WAITS),hl
        ret
; HL = this update's target: 11 x the window's lines without limiter waits + A x geometry + B x pixels + D
pace_follow:
        ld hl,(HLIB_V_PACE+2)
        ld de,(V_WAITS)
        or a
        sbc hl,de
        ld de,0
        ld (V_WAITS),de
        ld b,h
        ld c,l
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        add hl,bc
        ld a,(V_GEO)
        ld d,a
        ld e,PACE_A
        mul d,e
        add hl,de
        ld a,(V_PIX)
        ld d,a
        ld e,PACE_B
        mul d,e
        add hl,de
        ld de,PACE_D
        add hl,de
        ld (V_TGT),hl
        ret
        ENDIF
; 1.3: Carry set when interrupts are off. LD A,I reads IFF2 into P/V, but an interrupt accepted during the read
; leaves P/V clear: a single read can say "off" with interrupts on. "On" is always true, so a second read follows
; only an "off". At the end of the page so that no earlier label moves (the menu .nex keeps a set's differences
; from the default in its spare banks). A and F only; the callers reload A.
iff_off:
        ld a,i
        jp pe,.on
        ld a,i
        jp pe,.on
        scf
        ret
.on:
        or a
        ret
rom_end:
        ASSERT rom_end <= 0x4000
        IFNDEF CHQ_WRAPPED            ; a set's own source saves the blocks (asm/chase_hq_speed.asm)
        SAVEBIN "chase_rom.bin",0x2000,rom_end-0x2000
        ENDIF

        ORG 0x1100
hud_aux:
colour_base:
        ld a,(enh_enable)
        or a
        ret z
        ld a,(0x8007)
        or a
        jp z,colour_disable
        cp 6
        jp nc,colour_disable
        ld (A_STAGE),a
        ld a,(0x1C93)
        ld b,a
        ld a,(0x1C95)
        or b
        jr nz,.end_allowed
        ld a,(0xA231)
        cp 4
        jp nc,colour_disable
.end_allowed:
        call hud_full_clip

        ld a,(0xC161)
        ld b,a
        ld a,(0xC890)
        or b
        jr z,.draw
        ld a,1
        ld (E_PENDING),a
        ret
.draw:
        push ix
        call colour_maps_in
        ld a,(E_INIT)
        or a
        call z,colour_init
        nextreg 0x52,28
        ld a,0x64             ; DMA source fixed, memory, explicit 2-cycle timing
        ld (E_DMA+6),a
        ld hl,E_FILL
        ld (E_DMA+2),hl
        xor a
        ld (E_Y),a
        ld a,(0xE314)
        add a,32
        ld (E_HORIZON),a
.background:
        ld a,(E_Y)
        ld c,a
        and 96
        rlca
        rlca
        rlca
        ld b,a
        ld a,(E_BACK)
        add a,2
        add a,b
        nextreg 0x53,a
        ld a,c
        and 31
        or 0x60
        ld d,a
        ld e,0
        ld a,c
        and 31
        ld b,a
        ld a,32
        sub b
        ld b,a              ; rows left in this mapped page
        ld a,(E_HORIZON)
        sub c
        jr c,.green
        jr z,.green
        cp b
        jr nc,.skyspan
        ld b,a
.skyspan:
        ld a,247
        jr .span
.green:
        ld a,248
.span:  ld (E_FILL),a
        ld a,c
        add a,b
        ld (E_Y),a
        ld c,0              ; byte count = rows * 256
        call .fill
        call tick
        ld a,(E_Y)
        cp 128
        jr c,.background
        ld a,(E_HORIZON)
        ld (E_Y),a
.row:
        ld a,(E_Y)
        and 96
        rlca
        rlca
        rlca
        ld b,a
        ld a,(E_BACK)
        add a,2
        add a,b
        nextreg 0x53,a
        ld a,(E_Y)
        and 31
        or 0x60
        ld d,a
        ld e,0
        ld (E_DLINE),de
        ld a,(E_Y)
        add a,a
        ld l,a
        ld h,0xE8
        call .clamp
        ld (E_LEFT),a
        ld h,0xEC
        call .clamp
        ld (E_RIGHT),a
        ld b,a
        ld a,(E_LEFT)
        cp b
        jp nc,.rowdone
        ld de,(E_DLINE)
        ld e,a
        ld a,b
        sub e
        ld c,a
        ld b,0
        inc bc
        ld a,246
        ld (E_FILL),a
        call .fill
        ld a,(E_LEFT)
        and 0xF8
        ld e,a
        rrca
        rrca
        rrca
        ld (E_LBYTE),a
        ld (E_X),a
        ld c,a
        ld a,(E_Y)
        and 15
        or 0xF0
        ld h,a
        ld a,(E_Y)
        and 112
        add a,a
        add a,c
        ld l,a
        push hl
        pop ix
        ld a,(E_RIGHT)
        rrca
        rrca
        rrca
        and 31
        ld (E_RBYTE),a
        ld c,a
        ld a,(E_LBYTE)
        ld b,a
        ld a,c
        sub b
        ld b,a              ; last byte index minus first byte index
        ld a,(ix+0)
        ld c,a
        ld a,(E_LEFT)
        and 7
        ld l,a
        ld h,high edge_masks
        ld a,(hl)
        and c
        ld c,a
        ld a,b
        or a
        jr z,.lastmask
        call .expand
        inc ix
        dec b
        jr z,.last
        push ix
        pop hl
.middle:
        ld a,(hl)
        inc hl
        or a
        jr nz,.drawmid
        ld a,e
        add a,8
        ld e,a
        djnz .middle
        jr .last_hl
.drawmid:
        push hl
        ld c,a
        call .expand
        pop hl
        djnz .middle
.last_hl:
        push hl
        pop ix
.last:  ld c,(ix+0)
.lastmask:
        ld a,(E_RIGHT)
        and 7
        add a,8
        ld l,a
        ld h,high edge_masks
        ld a,(hl)
        and c
        ld c,a
        call .expand
.rowdone:
        ld a,(E_Y)
        and 7
        call z,tick
        ld a,(E_Y)
        inc a
        ld (E_Y),a
        cp 128
        jp nz,.row
        nextreg 0x52,56
        call 0x5800
        call colour_maps_out
        pop ix
        ret
.expand:
        push bc
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        or 0x58
        ld h,a
        xor a
        DUP 8
          ldix
        EDUP
        pop bc
        ret
.fill:  ld (E_DMA+4),bc
        ld (E_DMA+11),de
        ld hl,E_DMA
        ld bc,(dma_end-dma_template)*256+0x6B
        otir
        ret
.clamp:
        inc l
        ld a,(hl)
        dec l
        bit 7,a
        jr nz,.zero
        or a
        jr nz,.max
        ld a,(hl)
        ret
.zero:  xor a
        ret
.max:   ld a,255
        ret
        ALIGN 256
edge_masks:
        db 255,127,63,31,15,7,3,1
        db 128,192,224,240,248,252,254,255

colour_late_base:
        ld a,(E_PENDING)
        cp 1
        ret nz
        ld a,0x80
        ld (E_PENDING),a
        jp colour_base.draw

colour_disable:
        xor a
        ld (0x1C95),a
        ld (0x1C96),a
        xor a
        ld (0x1C93),a
        xor a
        ld (0x1ca3),a
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x26,0
        nextreg 0x27,0
        nextreg 0x15,8
        xor a
        ld (S_VALID),a
        ld (S_ACTIVE),a
        ld (E_PENDING),a
        ld a,(E_INIT)
        or a
        ret z
        xor a
        ld (E_INIT),a
        nextreg 0x69,0
        nextreg 0x62,0
        nextreg 0x43,0
        ret
colour_init:
        ld a,(enh_enable)
        or a
        ret z
        call colour_init_body
        jp hud_init_call
colour_init_body:
        call review_normal
        xor a
        ld (0x1ca3),a
        nextreg 0x52,56
        call 0x5000
        call 0x5400
        xor a
        ld (S_VALID),a
        ld (S_ACTIVE),a
        call hud_rows_call
        ld a,32
        ld (E_BACK),a
        ld a,1
        ld (E_INIT),a
        nextreg 0x43,0x10
        nextreg 0x40,0
        nextreg 0x41,0xE3     ; transparent palette entry 0
        nextreg 0x41,0        ; opaque black entry 1
        nextreg 0x40,1
        ld e,1
.pal:   ld a,e
        cp 1
        jr nz,.notblack
        xor a
.notblack:
        nextreg 0x44,a
        and 3
        jr z,.blow
        ld a,1
.blow:  or 0x80
        nextreg 0x44,a
        inc e
        jr nz,.pal
        nextreg 0x40,73
        nextreg 0x44,73
        nextreg 0x44,0x80    ; true neutral charcoal (2,2,2), no blue tint
        nextreg 0x40,2
        nextreg 0x44,248
        nextreg 0x44,128
        nextreg 0x40,3
        nextreg 0x44,249
        nextreg 0x44,128
        nextreg 0x40,4
        nextreg 0x44,246
        nextreg 0x44,128
        nextreg 0x40,5
        nextreg 0x44,173
        nextreg 0x44,128
        nextreg 0x40,6
        nextreg 0x44,104
        nextreg 0x44,129
        nextreg 0x40,7
        nextreg 0x44,244
        nextreg 0x44,128
        nextreg 0x40,8
        nextreg 0x44,248
        nextreg 0x44,129
        nextreg 0x40,9
        nextreg 0x44,36
        nextreg 0x44,129
        nextreg 0x40,10
        nextreg 0x44,151
        nextreg 0x44,128
        nextreg 0x40,11
        nextreg 0x44,78
        nextreg 0x44,128
        nextreg 0x40,13
        nextreg 0x44,218
        nextreg 0x44,128
        nextreg 0x40,14
        nextreg 0x44,209
        nextreg 0x44,128
        nextreg 0x40,15
        nextreg 0x44,213
        nextreg 0x44,128
        nextreg 0x40,16
        nextreg 0x44,136
        nextreg 0x44,129
        nextreg 0x40,17
        nextreg 0x44,37
        nextreg 0x44,128
        nextreg 0x40,244
        nextreg 0x44,109
        nextreg 0x44,129
        nextreg 0x40,245
        nextreg 0x44,83
        nextreg 0x44,129
        nextreg 0x40,249
        nextreg 0x44,56
        nextreg 0x44,128
        nextreg 0x40,246
        nextreg 0x41,109
        nextreg 0x41,83
        nextreg 0x41,56
        ; Clone the original ULA palette, changing its paper only below HUD.
        ld e,0
.ula:   nextreg 0x43,0
        ld a,e
        nextreg 0x40,a
        ld bc,0x243B
        ld a,0x41
        out (c),a
        inc b
        in d,(c)
        nextreg 0x43,0x40
        ld a,e
        nextreg 0x40,a
        ld a,d
        nextreg 0x41,a
        inc e
        ld a,e
        cp 32
        jr nz,.ula
        nextreg 0x40,16
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x14,0xE3
        nextreg 0x15,9       ; sprites, ULA, Layer 2; painted L2 pixels promoted
        nextreg 0x1C,1
        nextreg 0x18,8
        nextreg 0x18,247
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x52,56
        nextreg 0x53,57
        call 24632
        ld hl,dma_template
        ld de,E_DMA
        ld bc,dma_end-dma_template
        ldir
        ld bc,0x243B
        ld a,0x82
        out (c),a
        inc b
        in a,(c)
        or 0x20
        nextreg 0x82,a
        ret
dma_template:
        db 0x83,0x7D
        dw 0x4000,8192
        db 0x54,2,0x50,2,0xAD
        dw 0x6000
        db 0x82,0xCF,0x87
dma_end:
colour_commit:
        ld a,(E_INIT)
        or a
        ret z
        call hud_message_call
        ld a,(E_INIT)
        or a
        ret z
        ld a,(E_BACK)
        srl a
        nextreg 0x12,a
        nextreg 0x69,0x80
        ld a,(E_BACK)
        xor 6                ; 32 <-> 38
        ld (E_BACK),a
        ret

hud_aux_end:
        ASSERT $ <= 0x1800
        IFNDEF CHQ_WRAPPED            ; a set's own source saves the blocks (asm/chase_hq_speed.asm)
        SAVEBIN "hud_aux.bin",hud_aux,hud_aux_end-hud_aux
        ENDIF
