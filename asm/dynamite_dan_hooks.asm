; Dynamite Dan (Mirrorsoft, 1985, 48K) - overlay hardware sprites for Dan (the player).
; All hooks are stateless and live in alt ROM image 1 at 0x386E (the whole image is Sinclair's ROM + these bytes,
; card patch.whole-altrom-image, so the snapshot's own BASIC starts the game). Interrupts are OFF in the game
; (DI at 0xC800, no EI reached). The ULA is left exactly as the original draws it: Dan's pixels stay
; there, under his sprites, so nothing the game reads changes. Dan never paints attributes, so his
; clash is his own pixels taking the colour of the cell; the sprites cover those pixels.
;
; Patch sites (original bytes checked by dynamite_dan.py):
;   0xD1CE  3A 80 C8        LD A,(0xC880) (Dan's plotter entry)             -> JP e_dan
;   0xE801  21 00 40        LD HL,0x4000  (full clear: menu, screens)       -> JP e_c1
;   0xE820  21 00 40        LD HL,0x4000  (play area clear: room change)    -> JP e_c2
;   0xE60B  36 80 21 B0 40  LD (HL),0x80 / LD HL,0x40B0 (end of the game)   -> JP e_end
; Sprites 0 (top 16 rows) and 1 (next 8 rows). Patterns 2f, 2f+1 = frame f (8-bit, RRRGGGBB).
; A frame is 3 x 28 bytes with ink only in rows 2-25 and at most 12 columns wide, so one 16-wide
; window at xoff[f] holds it.
; Airship (room 43, fixed): sprites 2-10 copy the hull and cables from the ULA, above Dan.

        DEVICE ZXSPECTRUMNEXT

DAN_Y     EQU 0xC872
DAN_X     EQU 0xC873
DAN_FR    EQU 0xC875
DAN_INV   EQU 0xC880
DAN_ROWS  EQU 0xDBED
ROOM      EQU 0xCFCA
AIRSHIP   EQU 0x2B          ; room 43: the airship is fixed scenery, drawn once with the room
FG_N      EQU 9             ; foreground sprites 2..10 = patterns 16..24: copies of the hull and the
FG_SPR    EQU 2             ; cables, shown over Dan (higher number on top, NEXTREG $15 bit 6 = 0)
FG_PAT    EQU 16
; R as the original's at every hook (card patch.preserve-r; the game reads R at 0xDE1F): R is read at entry and kept
; on the stack, and set before the return to entry + D_xxx (bits 6:0), measured on the verifier. No hook writes NR 7,
; so each leaves the speed it was entered at (card patch.restore-speed): e_dan runs at 28 MHz with the caller's speed
; latched on the stack and written back at its exit; the clears run at the game's clock.
D_DAN     EQU 0x7F & -6
D_CLS     EQU 0x7F & -6
D_END     EQU 0x7F & -6

; RSET delta: A = R at entry -> R = entry + delta in bits 6:0, bit 7 kept. A and flags lost.
        MACRO RSET delta
        push bc
        ld b,a
        add a,delta
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        pop bc
        ld r,a
        ENDM

        ORG 0x386E
; ---- Dan's plotter ----
e_dan:  push af
        ld a,r
        push af                 ; R at entry
        push bc
        push hl
        ld bc,0x243B            ; the caller's speed (card patch.restore-speed), kept on the stack; then 28 MHz
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        ld a,(DAN_INV)
        rrca
        jp c,.hide              ; odd: the plotter draws the saved background, not Dan
        ld a,(DAN_FR)
        cp 8
        jp nc,.hide             ; never occurs: only 8 frames
        ld c,a
        ld b,0
        ld hl,xoff
        add hl,bc
        ld b,(hl)               ; B = window column of this frame
        ld a,(DAN_X)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,b
        add a,32
        add a,l
        ld l,a
        ld a,h
        adc a,0                 ; A:L = sprite X
        and 1
        ld h,a
        nextreg 0x34,0
        ld a,l
        nextreg 0x35,a
        ld a,h
        nextreg 0x37,a
        ld a,(DAN_Y)
        add a,34                ; 32 + first ink row
        nextreg 0x36,a
        ld a,c
        add a,a
        or 0xC0                 ; visible, 5th attribute byte
        ld b,a
        nextreg 0x38,a
        nextreg 0x39,0          ; 8-bit, Y8 = 0
        nextreg 0x34,1
        ld a,l
        nextreg 0x35,a
        ld a,h
        nextreg 0x37,a
        ld a,(DAN_Y)
        add a,50
        nextreg 0x36,a
        ld a,b
        inc a
        nextreg 0x38,a
        nextreg 0x39,0
        nextreg 0x1C,2          ; the plotter draws DAN_ROWS x 2 rows (Dan sinks in water: 12..1):
        nextreg 0x19,0          ; the sprite clip window ends where the plot ends
        nextreg 0x19,255
        nextreg 0x19,0
        ld a,(DAN_ROWS)
        add a,a
        dec a
        ld b,a
        ld a,(DAN_Y)
        add a,b
        nextreg 0x19,a
.fg:    ld a,(ROOM)
        cp AIRSHIP
        jr nz,.out
        ld c,FG_SPR
        ld b,FG_N
.show:  ld a,c
        nextreg 0x34,a
        add a,0xC0+FG_PAT-FG_SPR
        nextreg 0x38,a
        inc c
        djnz .show
.out:   pop af                  ; the caller's speed back
        nextreg 0x07,a
        pop hl
        pop bc
        pop af                  ; A = R at entry
        RSET D_DAN
        pop af
        ld a,(DAN_INV)
        jp 0xD1D1
.hide:  nextreg 0x34,0              ; Dan only: the airship stays in front of nothing
        nextreg 0x38,0
        nextreg 0x34,1
        nextreg 0x38,0
        jp .fg

; ---- screen clears: Dan's sprites off until his next plot ----
e_c1:   push af
        ld a,r
        push af
        call hide
        pop af
        RSET D_CLS
        pop af
        ld hl,0x4000
        jp 0xE804
e_c2:   push af
        ld a,r
        push af
        call hide
        pop af
        RSET D_CLS
        pop af
        ld hl,0x4000
        jp 0xE823
; ---- the end of the game: the airship scene scrolls without Dan's plotter ----
e_end:  push af
        ld a,r
        push af
        call hide
        pop af
        RSET D_END
        pop af
        ld (hl),0x80
        ld hl,0x40B0
        jp 0xE610

hide:   nextreg 0x34,0
        nextreg 0x38,0
        nextreg 0x34,1
        nextreg 0x38,0
        push af
        push bc
        ld a,FG_SPR
        ld b,FG_N
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        pop bc
        pop af
        ret

xoff:   db 4,6,6,8,4,6,8,10
rom_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, sprites off then on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0xE000
        ld d,16+FG_N                ; patterns x 256 bytes
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        ld hl,0xFF00                ; foreground table, bank 11 + 0x1F00: X, Y, attr 2 per sprite
        ld c,FG_SPR
        ld b,FG_N
.f:     ld a,c
        nextreg 0x34,a
        ld a,(hl)
        inc hl
        nextreg 0x35,a
        ld a,(hl)
        inc hl
        nextreg 0x36,a
        ld a,(hl)
        inc hl
        nextreg 0x37,a
        nextreg 0x38,0
        nextreg 0x39,0
        inc c
        djnz .f
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        xor a
.p:     nextreg 0x41,a              ; identity: index = RRRGGGBB
        inc a
        jr nz,.p
        nextreg 0x4B,0xE3
        ld a,FG_SPR+FG_N
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x34,0
        nextreg 0x38,0
        nextreg 0x34,1
        nextreg 0x38,0
        nextreg 0x15,0x01
        ret
setup_end:

        SAVEBIN "dd_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "dd_setup.bin",0xD000,setup_end-0xD000
