; Cookie (Ultimate, 1983, 16K) - hardware sprites for every figure the move-and-redraw plotter (0x763A) draws:
; Charlie, his flour bombs, the ingredients, the nasties.
; The game's plotter has Jetpac's and Pssst's control flow (the same entries, set-ups and old / new frame walk)
; with another row routine: a graphic is 16 pixels wide, shifted at run time and XORed in. These hooks are
; asm/pssst_hooks.asm's at this game's addresses: the game goes on drawing the figures into the bitmap (nothing of
; the bitmap changes), the sprites lie on the same pixels in the object's colour, and the colour the game paints
; over a figure's cells is not painted.
; The figure code and tables live in alt ROM image 1 at 0x386E (read-only). The entries, the speed latch and R
; live in hook RAM at 0xB000 (bank 2: a 16K game never addresses it; the verifier fails on
; any game read or write above 0x7FFF). Interrupts may be on at every site (IM 1, ROM handler reads IY): the
; hooks use only pushes below SP and NEXTREG, never IX/IY/I/IFF or the alternate registers (the plotter keeps
; state in them).
;
; Patch sites (original bytes checked by cookie.py):
;   0x75A9  CD E3 76   CALL 0x76E3 (new-frame set-up: the screen address; DE = graphic, IX = object)  -> CALL e_nw
;   0x7602  CD 5A 75   CALL 0x755A (erase only, graphic in DE)                  -> CALL e_e1
;   0x7607  CD 57 75   CALL 0x7557 (erase only)                                 -> CALL e_e2
;   0x5FBA, 0x642B, 0x6D51  CD D4 74   CALL 0x74D4 (bitmap clear, every new screen) -> CALL e_cls
; Pace: no frame sync on the main loop, so a draw's hook time would be lost for good. The plot's set-up, a fixed
; stretch per draw, runs at 28 MHz and pays for it (no wait, nothing tuned to an emulator's figure); the entries
; go up to 28 MHz, the ends give the caller's speed back:
;   0x75C1  CD 5A 75   CALL 0x755A (a draw that moves in both)                  -> CALL e_p27
;   0x75CC  CD 84 75   CALL 0x7584 (a draw that moves)                          -> CALL e_p3c
;   0x75FD  CD 87 75   CALL 0x7587 (a draw only)                                -> CALL e_p3f
;   0x7617  CD 84 75   CALL 0x7584 (a draw only)                                -> CALL e_p3c
;   0x75D0  CD 57 75   CALL 0x7557 (the erase set-up after 0x75CC's draw set-up) -> CALL e_x1
;   0x75C9  D9 18 07   EXX / JR 0x75D3                                          -> JP e_x2
;   0x761A  D9 AF 32   EXX / XOR A / LD (0x5F19),A                              -> JP e_x3
; The colour paint (0x74EE: (IX+3) over the figure's cells; the game rewrites its column limit as it runs): its
; store at 0x7519, LD (HL),D, becomes LD A,(HL): the same time, the same registers, no colour. Every object has
; sprites, so no paint is left.
; Sprites: object i = (IX - 0x5F35) / 8 (0-9) owns sprites 2i, 2i+1: a graphic is 16 pixels wide and up to 32
; lines, at the pixel x of (IX+1), its bottom line at (IX+2). The game draws nothing below line 159 (it cuts a
; figure there): the sprites' window ends at that line. A figure with its bottom line above line 31 is not
; drawn at all (the cut's signed compare): its sprites go off. Any other IX: no sprite.
; Patterns (4-bit, ink = 1) and their lookup: asm/cookie_tables.asm (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 0x5F35
NOBJ    EQU 10
NSPR    EQU NOBJ*2
TOP     EQU 31                  ; a figure whose bottom line is above this one is not drawn

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
        push bc
        ld b,a
        and 7
        ld a,b
        pop bc
        jr nz,.no
        rrca
        rrca                    ; 2i, carry clear
        and a
        ret
.no:    scf
        ret

; erase-only: the object's sprites off
hideobj:
        push af
        push bc
        call objbase
        jr c,.out
        ld b,2
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
.out:   pop bc
        pop af
        ret

; DE = graphic, IX = object. Uses all but IX/IY.
draw:   call objbase
        ret c
        ld a,(ix+2)
        cp TOP                  ; (y - 159 as a signed byte: above line 31 the set-up takes the figure for one
        jr c,.none              ; far under the bottom and cuts all of it)
        ld hl,gtab
.lk:    ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jr z,.none
        ld a,c
        cp e
        jr nz,.nx
        ld a,b
        cp d
        jr z,.ent
.nx:    inc hl
        inc hl
        jr .lk
.ent:   ld c,(hl)               ; C = pattern
        inc hl
        ld b,(hl)               ; B = rows - 1
        ld a,(ix+1)
        add a,32
        ld l,a
        ld a,0
        adc a,0
        ld h,a                  ; HL = X (the display from 32)
        ld a,(ix+2)             ; the bottom line
        bit 0,b
        jr nz,.r2
        add a,17                ; Y = y - 15 + 32
        jr .ry
.r2:    inc a                   ; Y = y - 31 + 32
.ry:    ld e,a                  ; E = Y
        push bc
        ld a,(ix+3)
        ld d,a
        and 7
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,d
        and 0x40
        add a,a
        or b
        or h
        ld h,a                  ; H = palette offset (ink + 8 * bright) << 4 | the ninth bit of X
        call objbase
        ld d,a                  ; D = the object's first sprite
        pop bc
        call place              ; row 0
        bit 0,b
        jr z,.one
        ld a,e
        add a,16
        ld e,a
        inc c
        call place              ; row 1
        ret
.one:   ld a,d
        jr .off
.none:  call objbase
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
.off:   nextreg 0x34,a
        nextreg 0x38,0
        ret

; one 16x16 sprite D at X = L (ninth bit and palette in H), Y = E, pattern C; D += 1
place:  ld a,d
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,h
.n_x8:  nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
        ld a,c
        srl a
.n_vis: or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        inc d
        ret

        INCLUDE "cookie_tables.asm"
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

; ---- new frame of an object: at 28 MHz already, from its entry. O 1, E 1 + 3, N 1 + 1 ----
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
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x76E3

; ---- erase-only entries: hide the object's sprites. O 1, E 1 + 3, N 1 + 1 ----
e_e1:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x755A
e_e2:   HLIB_R_IN
        call hideobj
        R_SET 1-4-2
        HLIB_R_OUT
        jp 0x7557

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
        jp 0x74D4

; ---- the plot's set-up at 28 MHz: entries. O 1, E 1 + 15 + 3, N 1 + 1 ----
        MACRO E_PRE TARGET
        HLIB_SPEED_IN V_SPD
        HLIB_R_IN
        R_SET 1-19-2
        HLIB_R_OUT
        jp TARGET
        ENDM
e_p27:  E_PRE 0x755A
e_p3c:  E_PRE 0x7584
e_p3f:  E_PRE 0x7587

; ---- ends: R first, so that only the last few T run at the caller's speed. E 1 + 3; N 1 + 5 + replay + jump ----
e_x1:   call 0x7623             ; 0x7557's first call, still in the window. To 0x755A: O and E both count it; O 1, N 7
        HLIB_R_IN
        R_SET 1-4-7
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        jp 0x755A
e_x2:   HLIB_R_IN               ; O 2, N 8
        R_SET 2-4-8
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        jp 0x75D3
e_x3:   HLIB_R_IN               ; O 3, N 10
        R_SET 3-4-10
        HLIB_R_OUT
        HLIB_SPEED_OUT V_SPD
        exx
        xor a
        ld (0x5F19),a
        jp 0x761F

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
        nextreg 0x1C,2          ; the sprites' window: the game draws no figure below line 159
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,159
        nextreg 0x15,0x01
        ret
speccy: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
fixpal: ds 26                   ; 13 fixed colours, 2 bytes each (the build fills them in)
setup_end:

; ---- Loading screen stub (nexclash-patch build/all2/add_screen.py STUB, bank 13; ported 2026-11-04) ----
; cookie.loading_nex() makes bank 13 (pages 26, 27; entry bank, PC 0xC000): ld_head at 0xC000, zero
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
PICTURE EQU 0xC200          ; the game's own screen bytes (cookie.loading_nex)

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


        SAVEBIN "ck_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ck_ram.bin",0xB000,ram_end-0xB000
        SAVEBIN "ck_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "ck_ldhead.bin",0xC000,ldscr.head_end-0xC000
        SAVEBIN "ck_ldtail.bin",0xFFD0,0x30