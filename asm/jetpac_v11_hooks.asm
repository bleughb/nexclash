; Jetpac (Ultimate, 1983, 16K) - hardware sprites for every figure the move-and-redraw plotter
; (30522) draws: Jetman, aliens, rocket parts, fuel, items, explosions.
; The figure code and tables live in alt ROM image 1 at 0x386E (read-only). The entries, the speed
; latch and R live in hook RAM at 0xB000 (bank 2: a 16K game never addresses it; the verifier fails on any
; game read or write above 0x7FFF). Interrupts may be on at every site (IM 1, ROM handler reads IY): the
; hooks use only pushes below SP and NEXTREG, never IX/IY/I/IFF or the alternate registers (the plotter
; keeps state in them).
;
; Patch sites (original bytes checked by jetpac_v11.py):
;   29263  1A 47 32   LD A,(DE) / LD B,A / LD (24004),A (new-frame setup, after 29448: HL = screen
;                     address of the bottom line, DE -> W, IX = object)        -> JP e_nw
;   29344  CD 27 72   CALL 29223 (erase only, graphic in DE)                    -> CALL e_e1
;   29349  CD 24 72   CALL 29220 (erase only)                                   -> CALL e_e2
;   24717  CD B8 71   CALL 29112 (screen clear, every new screen)              -> CALL e_cls
; Pace (2026-11-08): no frame sync on the main loop, so a draw's hook time was lost for good. The plot's
; set-up, a fixed stretch per draw, runs at 28 MHz and pays for it (no wait, no K, nothing tuned to an
; emulator's figure); the entries go up to 28 MHz, the ends give the caller's speed back:
;   29279  CD 27 72   CALL 29223 (a draw that moves in both)                    -> CALL e_p27
;   29290  CD 3C 72   CALL 29244 (a draw that moves)                            -> CALL e_p3c
;   29339  CD 3F 72   CALL 29247 (a draw only)                                  -> CALL e_p3f
;   29365  CD 3C 72   CALL 29244 (a draw only)                                  -> CALL e_p3c
;   29294  CD 24 72   CALL 29220 (the erase set-up after 29290's draw set-up)   -> CALL e_x1
;   29287  D9 18 07   EXX / JR 29297                                            -> JP e_x2
;   29368  D9 AF 32   EXX / XOR A / LD (24005),A                                -> JP e_x3
; Screen-write patches (no hook): 30532 77 -> 00 (erase AND), 30561 77 -> 00 (draw OR),
;   29171 72 -> 00 (object colour over its cells).
; Sprites: object i = (IX - 23808) / 8 (0-16) owns sprites 6i .. 6i+5: 2 rows x (2 columns + a copy
; of the column that crosses x = 256 at x - 256, as the ULA wraps the row).
; Object 6 (the rocket, IX = 23856) draws up to 3 sections and the take-off flames through one IX, so
; the table entry's layout bits 2-3 pick a group: 0 = its own sprites (section 0), 1 / 2 = sections 1 / 2
; at sprites 102 / 108, 3 = flames at 114. Bits ignored on other objects (a loose part on object 7 / 8).
; Its colours come from the fuel count, because the game paints cell rows after the plot: (IX+5) rows
; from the bottom magenta, the rest white, a full rocket flashing with (24012); a half-filled section
; uses palette offset 7: nibble 1 (lower 8 lines) magenta, nibble 15 (upper 8 lines) white.
; Patterns (4-bit, ink = 1, rocket sections' upper 8 lines 15) and their lookup: asm/jetpac_tables.asm
; (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 23808
NOBJ    EQU 17
LEVEL   EQU 24048
PART    EQU 23860
FUELS   EQU 23861               ; object 6 +5: fuel pods delivered
TICK    EQU 24012
ROCKET  EQU 0x30                ; low byte of object 6
RBASE   EQU 36                  ; its own first sprite
FLAMES  EQU 114                 ; first sprite of the flame group
NSPR    EQU NOBJ*6+18

        ORG 0x386E
; carry clear + A = first sprite of the object IX; carry set if IX is not an object slot
objbase:
        ld a,ixh
        cp high OBJ0
        jr nz,.no
        ld a,ixl
        cp NOBJ*8
        jr nc,.no
        and 7
        jr nz,.no
        ld a,ixl
        rrca
        rrca                    ; 2i
        push bc
        ld b,a
        add a,a
        add a,b                 ; 6i, carry clear
        pop bc
        ret
.no:    scf
        ret

; A = layout -> A = first sprite of the group it selects on this object. Keeps everything else.
sbase:  and 12
        jr z,objbase
        push bc
        ld b,a
        ld a,ixl
        cp ROCKET
        jr nz,.own
        ld a,b
        srl a
        add a,b
        add a,96                ; 4, 8, 12 -> 102, 108, 114
        pop bc
        ret
.own:   pop bc
        jr objbase

; erase-only: on the rocket these are the flames (26255-26305); the sections stay
hideobj:
        push af
        push bc
        call objbase
        jr c,.out
        cp RBASE
        jr nz,.g
        ld a,FLAMES
.g:     ld b,6
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
.out:   pop bc
        pop af
        ret

; HL = screen address (bottom line), DE -> W (graphic + 1), IX = object. Uses all but IX/IY.
draw:   call objbase
        ret c
        dec de                  ; DE = graphic
        push hl
        ld hl,gtab
.lk:    ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jp z,.none
        ld a,c
        cp e
        jr nz,.nx
        ld a,b
        cp d
        jr z,.fnd
.nx:    inc hl
        inc hl
        inc hl
        inc hl
        jr .lk
.fnd:   ld a,(hl)               ; kind
        inc hl
        or a
        jr z,.ent
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = subtable
        dec a
        jr nz,.car
        ld a,(LEVEL)
        and 7
        jr .idx
.car:   ld a,(PART)
        cp 4                    ; 3 = the fuel, pre-shifted after the last part (26044)
        jp nc,.none
        add a,a
        add a,a
        ld l,a
        ld a,(LEVEL)
        rrca
        rrca
        and 3
        add a,l
.idx:   ld l,a
        add a,a
        add a,l
        ld l,a
        ld h,0
        add hl,bc
.ent:   ld a,(hl)
        cp 255
        jp z,.none
        ld c,a                  ; C = pattern
        inc hl
        ld b,(hl)               ; B = layout
        inc hl
        ld a,(hl)               ; A = x adjust
        pop hl                  ; HL = screen address
        push bc
        ld b,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        add a,b
        ld e,a
        ld a,0
        adc a,0
        ld d,a                  ; DE = x (0-263)
        ld a,l
        rrca
        rrca
        and 0x38
        ld b,a
        ld a,h
        and 7
        or b
        ld b,a
        ld a,h
        add a,a
        add a,a
        add a,a
        and 0xC0
        or b                    ; A = bottom line y
        pop bc                  ; C = pattern, B = layout
        bit 1,b
        jr nz,.r2
        add a,17                ; Y = y - 15 + 32
        jr .ry
.r2:    inc a                   ; Y = y - 31 + 32
.ry:    push bc                 ; [pattern/layout]
        push de                 ; [x]
        ld e,a                  ; E = Y
        ld a,ixl
        cp ROCKET
        jr nz,.ink
        ld a,b                  ; rocket: from the group and the fuel, not (IX+3)
        and 12
        cp 12
        ld b,0xA0               ; flames: the game's 66
        jr z,.pal
        rrca                    ; A = 2 * section
        ld c,a
        ld a,(FUELS)
        cp 6
        jr nc,.full
        sub c
        ld b,0xF0               ; no fuel up here: white
        jr c,.pal
        jr z,.pal
        dec a
        ld b,0x70               ; half
        jr z,.pal
        ld b,0xB0               ; magenta
        jr .pal
.full:  ld a,(TICK)             ; as 26507-26514
        rrca
        rrca
        and 4
        rlca
        rlca
        rlca
        rlca
        add a,0xB0
        ld b,a
        jr .pal
.ink:   ld a,(ix+3)
        ld c,a
        and 7
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,c
        and 0x40
        add a,a
        or b
        ld b,a                  ; B = palette offset (ink + 8 * bright) << 4
.pal:   pop hl
        ex (sp),hl
        ld c,l                  ; C = pattern
        ld a,h                  ; A = layout
        ex (sp),hl              ; HL = x, stack [pattern/layout]
        push af
        call sbase
        ld d,a                  ; D = next sprite
        pop af
        push af
        push hl
        call place              ; row 0, column 0
        pop hl
        pop af
        push af
        push hl
        bit 0,a
        jr z,.n1
        inc c
        call add16
        call place              ; row 0, column 1
.n1:    pop hl
        pop af
        bit 1,a
        jr z,.done
        push af
        ld a,e
        add a,16
        ld e,a
        pop af
        inc c                   ; first pattern of row 1 (pattern + columns)
        push af
        push hl
        call place              ; row 1, column 0
        pop hl
        pop af
        bit 0,a
        jr z,.done
        inc c
        call add16
        call place              ; row 1, column 1
.done:  pop hl
        ld a,h                  ; layout
        jr .hide
.none:  pop hl
        call objbase
        ld d,a
        xor a
.hide:  call sbase
        add a,6
        ld b,a
.hd:    ld a,d
        cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc d
        jr .hd

add16:  ld a,l
        add a,16
        ld l,a
        ret nc
        inc h
        ret

; one 16x16 column at x_c = HL (0-295): sprite D (D += 1 per sprite set), Y = E, palette B,
; pattern C. x_c < 256: at x_c; x_c > 240: (also) at x_c - 256 (the ULA row wrap).
place:  ld a,h
        or a
        jr nz,.w
        ld a,d
        nextreg 0x34,a
        ld a,l
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        or b
        nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
        call setpat
        ld a,l
        cp 241
        ret c
.w:     ld a,d
        nextreg 0x34,a
        ld a,l
        sub 224
        nextreg 0x35,a
        ld a,b
        nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
setpat: ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        inc d
        ret

        INCLUDE "jetpac_v11_tables.asm"
rom_end:

; ---- hook RAM, bank 2 (site bytes for the verifier: the block is zero in the snapshot) ----
HLIB_V_R EQU 0xB200             ; 3 bytes (never code: the verifier leaves it out of the memory compare)
V_SPD   EQU 0xB203              ; the caller's speed, one level: an entry and its end have no hook between

        ORG 0xB000
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"

; R = entry R + D at the next HLIB_R_OUT; every register and flag kept
        MACRO R_SET D
        push af
        ld a,(D) & 0x7F
        call hlib_r_set
        pop af
        ENDM

; ---- new frame of an object: at 28 MHz already, from its entry ----
; delta = O - E - N (card patch.preserve-r): O 3; E 1 + 3; N 1 + 3 + 1
e_nw:   HLIB_R_IN
        push af
        push bc
        push de
        push hl
        call draw
        pop hl
        pop de
        pop bc
        pop af
        R_SET 3-4-5
        HLIB_R_OUT
        ld a,(de)
        ld b,a
        ld (24004),a
        jp 29268

; ---- erase-only entries: hide the object's sprites. O 1, E 1 + 3, N 1 + 1 ----
e_e1:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 29223
e_e2:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 29220

; ---- screen clear: hide every sprite. O 1, E 1 + 3, N 1 + 1 ----
e_cls:  HLIB_R_IN
        push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSPR
        jr nz,.h
        pop af
        R_SET 1-4-2
        HLIB_R_OUT
        jp 29112

; ---- the plot's set-up at 28 MHz: entries. O 1, E 1 + 15 + 3, N 1 + 1 ----
        MACRO E_PRE TARGET
        HLIB_SPEED_IN V_SPD
        HLIB_R_IN
        R_SET 1-19-2
        HLIB_R_OUT
        jp TARGET
        ENDM
e_p27:  E_PRE 29223
e_p3c:  E_PRE 29244
e_p3f:  E_PRE 29247

; ---- ends: R first, so that only the last few T run at the caller's speed. E 1 + 3; N 1 + 5 + replay + jump ----
e_x1:   call 29377              ; 29220's first call, still in the window. To 29223: O and E both count it; O 1, N 7
        HLIB_R_IN
        R_SET 1-4-7
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        jp 29223
e_x2:   HLIB_R_IN               ; O 2, N 8
        R_SET 2-4-8
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        jp 29297
e_x3:   HLIB_R_IN               ; O 3, N 10
        R_SET 3-4-10
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        xor a
        ld (24005),a
        jp 29373
ram_end:
        ASSERT ram_end <= HLIB_V_R

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0xE000
        ld d,NPAT256
.u:     ld bc,0x005B
        otir
        ld a,h
        or a
        jr nz,.u2               ; 8K page done (HL wrapped to 0): bank 11's second page
        nextreg 0x57,23
        ld h,0xE0
.u2:    dec d
        jr nz,.u
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment off for 0x41 writes below
        ld hl,speccy
        ld b,16
        ld c,1
.p:     ld a,c
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; offset n index 1 = Spectrum colour n (8-15 bright)
        ld a,c
        add a,14
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; index 15 the same (rocket sections' upper lines)
        inc hl
        ld a,c
        add a,16
        ld c,a
        djnz .p
        nextreg 0x40,0x7F           ; offset 7 (no object's ink) = half-filled section: 1 magenta, 15 white
        nextreg 0x41,0xFF
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
speccy: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xE7,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

; ---- Loading screen stub (nexclash-patch build/all2/add_screen.py STUB, bank 13; ported 2026-11-04) ----
; jetpac_v11.loading_nex() makes bank 13 (pages 26, 27; entry bank, PC 0xC000): ld_head at 0xC000, zero
; to 0xC200, the game's own bank 5 screen bytes (6912), zero to 0xFFD0, ld_tail. On entry .nexload has
; left slots 2-5 = 10,11,4,5, slots 6-7 = this bank, DI, SP = 0xDFFE and 0xC000 pushed just below SP.
; No byte outside this bank differs when it leaves; its last instruction puts page 5 back, so the next
; fetch is 0xC000 (bank 10) with no trampoline in RAM. The border stays as the loader set it.
        MODULE ldscr
SCREEN  EQU 0x4000
SCRLEN  EQU 6912
REGS    EQU 0xFE00          ; register stack, page 27; below it the stub's call stack
SEL     EQU 0xFE02          ; port 0x243B as found
TIMEOUT EQU 250             ; frames: 5 s at 50 Hz
CAP     EQU 250             ; most frames to wait for a held key to go
CLEAR   EQU 3               ; frames with no key before leaving
LINE    EQU 192             ; first line below the picture
PICTURE EQU 0xC200          ; the game's own screen bytes (jetpac_v11.loading_nex)

        ORG 0xC000
start:  di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,0x243B
        in      a,(c)
        ld      (SEL),a
; A key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the game doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,PICTURE
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        ld      bc,0x243B
        ld      a,(SEL)
        out     (c),a
        nextreg 0x55,27
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,0x243B
        ld      a,0x1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,(0xfe)
        cpl
        and     0x1f
        or      e
        ld      e,a
        ld      a,d
        ret
head_end:
        ASSERT  head_end <= PICTURE

        ORG 0xFFD0
        DISP    0xBFD0
; Runs from page 27 at slot 5. The entry bank's top bytes get what the loader's stack left there.
final:  nextreg 0x56,20
        nextreg 0x57,21
        ld      hl,0xC000
        ld      (0xDFFC),hl
        ld      sp,REGS-0x4000-12
        pop     iy
        pop     ix
        ld      hl,(0xBFFF)     ; MEMPTR = 0xC000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,0xDFFE
        ds      0xBFFC-$
        nextreg 0x55,5          ; falls through to 0xC000, the entry bank
        ASSERT  $ == 0xC000
        ENT
        ENDMODULE


        SAVEBIN "jp_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "jp_ram.bin",0xB000,ram_end-0xB000
        SAVEBIN "jp_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "jp_ldhead.bin",0xC000,ldscr.head_end-0xC000
        SAVEBIN "jp_ldtail.bin",0xFFD0,0x30
