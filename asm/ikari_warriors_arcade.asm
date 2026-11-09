; Ikari Warriors, Enhanced: the scenery's colours on the tilemap, under the ULA's own ink. Facts: games/ikari_warriors_arcade.md.
; The game draws and scrolls its scenery as before. Tile routine 0x9733 draws one char of a new row per call of site 0x97E4:
; the map cell takes the tile for that map byte (IY) from the table in page TPG, else the char's default tile. The tilemap wraps
; at 256 lines like the game's buffer, row = buffer line / 8, so one register follows the scroll. Interrupts are off in play.
; Page H and the macros as asm/ikari_warriors_hooks.asm. A_ORG, A_OPEN (hlib_pace_open) are defined by the build.

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"
HPG     EQU 26
GP4     EQU 4
GP6     EQU 0
TPG     EQU 48                  ; the table: IY - 0x8000 -> tile, 0xFF = the char's default; default tiles at 0xDF00
MAPPG   EQU 14                  ; bank 7's page the tilemap can read (8K of BRAM): the map, 40 x 32, one byte a cell, then the tile graphics
ORIGIN  EQU 0xE460
V_SP    EQU 0x8002
V_SPD   EQU 0x8036
V_A     EQU 0x8037
HSTK    EQU 0x9000
HLIB_V_PACE EQU 0x8040
D_LG    EQU 192
V_TC    EQU 0x8070              ; the char; +4 to +9: a_init's registers
V_TB    EQU 0x8072              ; the strip's graphics base
V_TPAL  EQU 0x8080              ; 1 = graphics, map and palette are in

        MACRO ENTER
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPD
        ENDM

        MACRO LEAVE
        ld sp,(V_SP)
        ld (V_A),a
        ld a,(V_SPD)
        nextreg 0x07,a
        ld a,(V_A)
        nextreg 0x54,GP4
        ENDM

        MACRO SCENERY_OFF               ; registers and flags kept: the default ULA palette back, the tilemap off
        nextreg 0x6B,0
        nextreg 0x43,0
        nextreg 0x40,1
        nextreg 0x41,0x02
        nextreg 0x40,9
        nextreg 0x41,0x03
        nextreg 0x40,20
        nextreg 0x41,0x14
        nextreg 0x40,22
        nextreg 0x41,0xB4
        nextreg 0x40,28
        nextreg 0x41,0x1C
        ENDM

        ORG A_ORG
; ---- 0x97E4 LD L,(IY+0) -> JP a_tc: A H L D E and the flags are dead here, SP is not a stack (the routine uses it for data) -
a_tc:   ld a,(iy+0)
        ld hl,(0x97EF)          ; LD SP,base: the strip's graphics
        ld de,(0x97F4)          ; LD HL,dest: the cell in the buffer
        ENTER
        ld (V_TC),a
        ld (V_TB),hl
        push bc
        ld a,(V_TPAL)
        or a
        call z,a_init
        ld a,e
        and 31
        cp 5
        jr c,.out
        cp 27
        jr nc,.out
        add a,4
        ld c,a                  ; map column
        nextreg 0x56,TPG
        push iy
        pop hl
        ld a,h
        sub 0x80
        cp 0x20
        jr nc,.def
        or 0xC0
        ld h,a
        ld a,(hl)
        cp 0xFF
        jr nz,.got
.def:   ld hl,(V_TB)
        push bc
        ld bc,0x7322
        or a
        sbc hl,bc
        pop bc
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ld a,(V_TC)
        add a,l
        ld l,a
        ld h,0xDF
        ld a,(hl)
.got:   ld b,a
        ld a,d                  ; map row = buffer line / 8
        and 31
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de               ; x 40
        ld e,c
        ld d,0xC0
        add hl,de
.neg_tile:
        nextreg 0x56,MAPPG
        ld (hl),b
.out:   nextreg 0x56,GP6
        pop bc
        LEAVE
        ld l,(iy+0)
        jp 0x97E7

; once, before the first tile: the graphics from page TPG + 1 to the 8K of bank 7 the tilemap can read, a clear map, the tile palette.
; DE and BC kept for a_tc; no stack while page H is out
a_init: ld a,1
        ld (V_TPAL),a
        ld (V_TC+4),de
        ld (V_TC+6),bc
        ld (V_TC+8),hl
        nextreg 0x43,0x30       ; the tile palette, 9 bits
        nextreg 0x40,0
        ld hl,a_pal
        ld b,6*2
.p:     ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .p
        nextreg 0x43,0
        nextreg 0x54,MAPPG      ; the map's page at slot 4: code and stack are not in it, but page H is out, so no calls here
        nextreg 0x56,TPG+1
        ld hl,0x8000
        ld de,0x8001
        ld bc,1279
        ld (hl),0
        ldir
        ld hl,0xC000
        ld de,0x8500
        ld bc,6912
        ldir
        nextreg 0x54,HPG
        nextreg 0x56,GP6
        ld de,(V_TC+4)
        ld bc,(V_TC+6)
        ld hl,(V_TC+8)
        ret

; ---- e_bl, in place of its CALL hlib_pace_open: stack and registers free ----------------------------------------------------
a_bl:   nextreg 0x6B,0xA0       ; on, one byte a cell
        nextreg 0x6C,0x01       ; palette 0, the ULA over the tilemap
        nextreg 0x6E,0x80       ; map: bank 7 + 0
        nextreg 0x6F,0x85       ; tile graphics: bank 7 + 0x0500
        nextreg 0x1C,8
        nextreg 0x1B,36         ; the play window; x in 2 pixel units
        nextreg 0x1B,123
        nextreg 0x1B,48
        nextreg 0x1B,215
        nextreg 0x2F,0
        nextreg 0x30,0
        nextreg 0x4C,15
        nextreg 0x43,0          ; the ULA: paper and blue ink clear, the tile shows through; black ink stays (the HUD shares it)
        nextreg 0x40,1
        nextreg 0x41,0xE3
        nextreg 0x40,9
        nextreg 0x41,0xE3
        nextreg 0x40,20
        nextreg 0x41,0xE3
        nextreg 0x40,22
        nextreg 0x41,0xE3
        nextreg 0x40,28
        nextreg 0x41,0xE3
        ld a,(V_TPAL)
        or a
        call z,a_init
        call A_OPEN             ; the blit's window opens here: the wait below is inside it, the limiter's own wait gets shorter
.neg_wait:                      ; ink, tile and sprites change together: the blit (at 28 MHz about 50 lines, three times the beam's
                                ; speed) starts with the beam below the window or above its top, so it stays ahead of the beam
        ld hl,(HLIB_V_PACE+4)   ; in a burst the debt comes first: no wait, a step of shimmer on some lines for one frame at worst
        ld de,D_LG
        or a
        sbc hl,de
        jr nc,.go
.w:     ld bc,0x243B
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        and 1
        ld d,a
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        ld e,a
        ld a,d
        or a
        jr nz,.go               ; line 256 and over: below the window
        ld a,e
        cp 184
        jr nc,.go
        cp 15
        jr nc,.w
.go:
        ld hl,(ORIGIN)          ; the window's first line, as the blit's: origin + 56 lines
        ld de,0x0700
        add hl,de
        ld a,h
        and 0x1F
        rlca
        rlca
        rlca
        ld b,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        or b
.neg_scroll:
        sub 48                  ; the window's top on the tilemap's 320 x 256
        nextreg 0x31,a
        ret
; dirt, rock, wood, foliage, light foliage, water: RRRGGGBB, B0
a_pal:  DB 0x48,0, 0x6D,1, 0x8C,0, 0x48,0, 0x6D,1, 0x03,0      ; filled in by the build
a_pal_end:

; ---- 0xF019 LD (0xE4B0),SP -> JP a_st: the game stipples over a destroyed object, 8 bytes x 72 lines up from HL: its tiles go back
; to ground; foliage, water and wood keep theirs (tiles below A_RK are ground and rock only)
a_st:   ENTER
        push af
        push bc
        push de
        push hl
        nextreg 0x56,MAPPG
        ld a,l
        and 31
        ld c,a                  ; column
        ld a,h
        and 31
        ld e,a                  ; row
        ld d,10                 ; 72 lines touch up to 10 rows
.r:     ld a,e
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        pop de
        ld b,8
        ld a,c
.c:     cp 5
        jr c,.n
        cp 27
        jr nc,.n
        push hl
        push af
        add a,4
        add a,l
        ld l,a
        ld a,h
        adc a,0xC0
        ld h,a
        ld a,(hl)
        cp A_RK
        jr nc,.k
.neg_st:
        ld (hl),0
.k:     pop af
        pop hl
.n:     inc a
        djnz .c
        ld a,e
        dec a
        and 31
        ld e,a
        dec d
        jr nz,.r
        nextreg 0x56,GP6
        pop hl
        pop de
        pop bc
        pop af
        LEAVE
        ld (0xE4B0),sp
        jp 0xF01D

; ---- leaving the play loop: as the hooks' own sites, the scenery off first ---------------------------------------------------
a_h1:   SCENERY_OFF
        jp A_H1
a_h2:   SCENERY_OFF
        jp A_H2
a_h3:   SCENERY_OFF
        jp A_H3
a_h4:   SCENERY_OFF
        jp A_H4
a_end:
        SAVEBIN "ik_arcade.bin",A_ORG,a_end-A_ORG
