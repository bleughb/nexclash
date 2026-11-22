; Pssst (Ultimate, 1983, 16K) - hardware sprites for every figure the move-and-redraw plotter (0x75D0)
; draws for an object of the main table: Robbie, his spray can, the spray, the pests, bonus items, explosions.
; The game's plotter is Jetpac's, and so are these hooks (asm/jetpac_v11_hooks.asm), with one difference: the
; game goes on drawing the figures into the bitmap (nothing of the bitmap changes) and the sprites lie on the same
; pixels; only the colour the game paints over a figure's cells is not painted, for the objects that have sprites.
; The figure code and tables live in alt ROM image 1 at 0x386E (read-only). The entries, the speed latch, R and
; the colour paint's copy live in hook RAM at 0xB000 (bank 2: a 16K game never addresses it; the verifier fails on
; any game read or write above 0x7FFF). Interrupts may be on at every site (IM 1, ROM handler reads IY): the
; hooks use only pushes below SP and NEXTREG, never IX/IY/I/IFF or the alternate registers (the plotter keeps
; state in them).
;
; Patch sites (original bytes checked by pssst.py):
;   0x74D0  1A 47 32   LD A,(DE) / LD B,A / LD (0x5E0F),A (new-frame set-up, after 0x759A: HL = screen
;                      address of the bottom line, DE -> W, IX = object)        -> JP e_nw
;   0x7521  CD A8 74   CALL 0x74A8 (erase only, graphic in DE)                  -> CALL e_e1
;   0x7526  CD A5 74   CALL 0x74A5 (erase only)                                 -> CALL e_e2
;   0x667F  C3 29 75   JP 0x7529 (erase only, at a place the handler gives)      -> JP e_e3
;   0x5F59  CD 39 74   CALL 0x7439 (bitmap clear, every new screen)             -> CALL e_cls
; Pace: no frame sync on the main loop, so a draw's hook time would be lost for good. The plot's set-up, a fixed
; stretch per draw, runs at 28 MHz and pays for it (no wait, nothing tuned to an emulator's figure); the entries
; go up to 28 MHz, the ends give the caller's speed back:
;   0x74E0  CD A8 74   CALL 0x74A8 (a draw that moves in both)                  -> CALL e_p27
;   0x74EB  CD BD 74   CALL 0x74BD (a draw that moves)                          -> CALL e_p3c
;   0x751C  CD C0 74   CALL 0x74C0 (a draw only)                                -> CALL e_p3f
;   0x7536  CD BD 74   CALL 0x74BD (a draw only)                                -> CALL e_p3c
;   0x74EF  CD A5 74   CALL 0x74A5 (the erase set-up after 0x74EB's draw set-up) -> CALL e_x1
;   0x74E8  D9 18 07   EXX / JR 0x74F2                                          -> JP e_x2
;   0x7539  D9 AF 32   EXX / XOR A / LD (0x5E10),A                              -> JP e_x3
; The colour paint (0x7450: (IX+3) over the figure's cells): its CALLs and JPs from the handlers of the main
; table's objects (0x6631, 0x6A24, 0x6C99, 0x6CC4, 0x6EE4, 0x6F34) go to p_at, the same routine with the
; store read instead of written: the same time, the same registers, no colour. The others (0x6015 the lives,
; 0x7233 the leaves, 0x6D60 the bud and the flower: figures the game leaves on the screen) are not changed.
; Sprites: object i = (IX - 0x5E6C) / 8 (0-15, but the flower's) owns sprites 6i .. 6i+5: 2 rows x (2 columns + a copy of the
; column that crosses x = 256 at x - 256, 8 lines down, as the game's plotter runs on). Any other IX: no sprite.
; Patterns (4-bit, ink = 1) and their lookup: asm/pssst_tables.asm (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 0x5E6C
NOBJ    EQU 16
FLOWER  EQU 0x5E8C              ; the bud and the flower: left to the game (its last picture is taller than 2 sprites)
NSPR    EQU NOBJ*6

        ORG 0x386E
; carry clear + A = first sprite of the object IX; carry set if IX is not an object slot
objbase:
        ld a,ixh
        cp high OBJ0
        jr nz,.no
        ld a,ixl
        sub low OBJ0
        jr c,.no
        cp NOBJ*8
        jr nc,.no
        cp FLOWER - OBJ0
        jr z,.no
        push bc
        ld b,a
        and 7
        ld a,b
        pop bc
        jr nz,.no
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

; erase-only: the object's sprites off
hideobj:
        push af
        push bc
        call objbase
        jr c,.out
        ld b,6
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
        jr z,.ent
.nx:    inc hl
        inc hl
        inc hl
        jr .lk
.ent:   ld c,(hl)               ; C = pattern
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
        ld a,(ix+3)
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
        call objbase
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
.hide:  call objbase
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
; pattern C. x_c < 256: at x_c; x_c > 240: (also) at x_c - 256, 8 lines down (as the plotter runs on).
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
        add a,8                 ; (this game's plotter does not wrap within the row: past column 31 it goes on
        nextreg 0x36,a          ; at column 0 of the next character row, 8 lines down)
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

        INCLUDE "pssst_tables.asm"
rom_end:

; ---- hook RAM, bank 2 (site bytes for the verifier: the block is zero in the snapshot) ----
HLIB_V_R EQU 0xB300             ; 3 bytes (never code: the verifier leaves it out of the memory compare)
V_SPD   EQU 0xB303              ; the caller's speed, one level: an entry and its end have no hook between

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

; ---- new frame of an object: at 28 MHz already, from its entry (the lives' icons come at the caller's speed) ----
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
        ld (0x5E0F),a
        jp 0x74D5

; ---- erase-only entries: hide the object's sprites. O 1, E 1 + 3, N 1 + 1 ----
e_e1:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x74A8
e_e2:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x74A5
e_e3:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x7529

; ---- bitmap clear: hide every sprite. O 1, E 1 + 3, N 1 + 1 ----
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
        jp 0x7439

; ---- the plot's set-up at 28 MHz: entries. O 1, E 1 + 15 + 3, N 1 + 1 ----
        MACRO E_PRE TARGET
        HLIB_SPEED_IN V_SPD
        HLIB_R_IN
        R_SET 1-19-2
        HLIB_R_OUT
        jp TARGET
        ENDM
e_p27:  E_PRE 0x74A8
e_p3c:  E_PRE 0x74BD
e_p3f:  E_PRE 0x74C0

; ---- ends: R first, so that only the last few T run at the caller's speed. E 1 + 3; N 1 + 5 + replay + jump ----
e_x1:   call 0x7542             ; 0x74A5's first call, still in the window. To 0x74A8: O and E both count it; O 1, N 7
        HLIB_R_IN
        R_SET 1-4-7
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        jp 0x74A8
e_x2:   HLIB_R_IN               ; O 2, N 8
        R_SET 2-4-8
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        jp 0x74F2
e_x3:   HLIB_R_IN               ; O 3, N 10
        R_SET 3-4-10
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        xor a
        ld (0x5E10),a
        jp 0x753E

; ---- the colour paint 0x7450 with its store read instead of written: every instruction, flag and T the game's ----
p_at:   exx
        ld hl,(0x5E1A)
        call 0x748F
        ld a,(0x5E0F)
        ld b,a
        ld a,(0x5E0E)
        rrca
        rrca
        inc a
        rrca
        and 0x1F
        inc a
        ld c,a
        ld d,(ix+3)
        ld e,b
.row:   push hl
.cell:  ld a,h
        cp 0x5B
        jr nc,.end
        cp 0x58
        jr c,.end
.n_st:  ld a,(hl)               ; (the game's LD (HL),D)
        inc l
        ld a,l
        and 0x1F
        jr nz,.nx
        ld a,l
        sub 0x20
        ld l,a
.nx:    djnz .cell
.end:   pop hl
        push bc
        and a
        ld bc,0x0020
        sbc hl,bc
        pop bc
        ld b,e
        dec c
        jr nz,.row
        ret
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
        nextreg 0x43,0x20           ; sprite palette 0
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
        nextreg 0x41,a              ; index 15 the same
        inc hl
        ld a,c
        add a,16
        ld c,a
        djnz .p
        ld c,2                      ; the fixed colours of a painted set: nibbles 2 to 14 of every offset (9 bits each;
        ld d,16                     ; the plain build's are zero and no pattern uses them)
.fo:    ld a,c
        nextreg 0x40,a
        ld hl,fixpal
        ld b,13
.fk:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .fk
        ld a,c
        add a,16
        ld c,a
        dec d
        jr nz,.fo
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
speccy: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
fixpal: ds 26                   ; 13 fixed colours, 2 bytes each (the build fills them in)
setup_end:

; ---- Loading screen stub (nexclash-patch build/all2/add_screen.py STUB, bank 13; ported 2026-11-04) ----
; pssst.loading_nex() makes bank 13 (pages 26, 27; entry bank, PC 0xC000): ld_head at 0xC000, zero
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
PICTURE EQU 0xC200          ; the game's own screen bytes (pssst.loading_nex)

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


        SAVEBIN "ps_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ps_ram.bin",0xB000,ram_end-0xB000
        SAVEBIN "ps_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "ps_ldhead.bin",0xC000,ldscr.head_end-0xC000
        SAVEBIN "ps_ldtail.bin",0xFFD0,0x30