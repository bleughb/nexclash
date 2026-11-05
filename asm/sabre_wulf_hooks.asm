; Sabre Wulf (Ultimate, 1984, 48K) - every figure a hardware sprite. Facts and design: games/sabre_wulf.md.
; The game draws figures by XOR (rows 47629 / 47756, shift tables 0xF000) and paints their cells (47941).
; Its plot loops keep running with the same T-states: LD (HL),A -> LD A,(HL) at every row write, and the
; paint's LD (HL),D -> CP (HL) (7 T, one access of the cell, as the write; the carry it sets is dead), so
; enemy speed, which depends on how long a round of the object loop takes (no frame cap), stays the same.
; Three entries toggle images, as XOR does:
;   47529 move: toggles the saved image (38559 frame, 38560 x, 38561 y) and the object's (IX+0, +3, +4)
;   47385 toggles the object's image        47349 toggles the saved image
; A clear (47964) ends every image. Colour = (IX+5) at each plot and each paint (47908), so a hit flash shows.
; Hooks: alt ROM image 1 at 0x386E (the whole image is Sinclair's ROM + these bytes). Interrupts stay on
; (IM 1, the ROM ISR uses the game stack and the system variables only): hooks use the game stack, keep
; IX, IY, I, IFF and the alternate set, and map Next pages only in slots 6 and 7.
; 2026-11-05 rework (refactor phase 7 import):
; - the caller's speed: NR 7 latched at entry (card patch.restore-speed), restored at every exit;
; - R as the original's (card patch.preserve-r: the game takes chance from R at 39376, 40484, 41707);
; - speed pass: a hook changes no sprite when the object's (frame, x, y, colour) is as last shown; the
;   object index from a table, not a division; patterns from a frame cache in pattern RAM (128 units of
;   128 bytes, clock replacement, a unit of a frame some object shows is never replaced), so a frame an
;   animation comes back to is not uploaded again.
; State: Next page STATE at slot 7 (only inside a hook). Patterns: Next pages from PAT0 at slot 6.
; Object i (IX = 38658 + 12i) owns sprites 4*(24-i) .. +3, so the player (i = 0) is on top.

        DEVICE ZXSPECTRUMNEXT

STATE   EQU 22                  ; bank 11, first 8K
FRTAB   EQU 0xE000              ; per frame f (8 bytes): page, unit in page, flags (n-1 cols | (n-1 rows) << 1), height,
                                ;   canonical frame (frames with the same patterns share one), units (1, 2 or 4)
UL      EQU 0xE700              ; 4 arrays of 256: unit k of canonical frame c at UL + 256 k + c, if CACHED
OBJ     EQU 0xEB00              ; per object (8 bytes): +0 frame shown (0 none), +1 x, +2 y (the XOR state);
                                ;   +3 frame on the sprites (0 none), +4 x, +5 y, +6 palette offset << 4 on them
IXT     EQU 0xEC00              ; IX - 38658 (0-299) -> 8 * object, or 0xFF: not an object
UOWN    EQU 0xEE00              ; per unit: the canonical frame it holds, 0 = none
REF     EQU 0xEF00              ; per canonical frame: objects showing it (its units are then never replaced)
CACHED  EQU 0xF000              ; per canonical frame: 1 if UL holds it
VSPD    EQU 0xF100              ; the incoming speed (NR 7 bits 1:0)
VR      EQU 0xF101              ; R at the entry
HAND    EQU 0xF102              ; the cache's clock hand, unit 0-127
SXW     EQU 0xF104
SFL     EQU 0xF106
STOP    EQU 0xF107
SCOL    EQU 0xF108
VC      EQU 0xF109              ; fetch: the canonical frame, units left, UL's page for the next unit
VN      EQU 0xF10A
VK      EQU 0xF10B
SAVED   EQU 38559
NOBJ    EQU 25

; R (card patch.preserve-r): each hook's R at the meeting point = entry R + D_xxx (bits 6:0), measured on the
; verifier (hooklib.r_check): the original's M1s from the site, less the hook's M1s up to its LD A,R and after
; its LD R,A.
D_MOV   EQU 0x7F & (1 - 20 - 12)
D_TOG   EQU D_MOV
D_OLD   EQU D_MOV
D_COL   EQU 0x7F & (2 - 20 - 13)
D_CLR   EQU 0x7F & (1 - 20 - 11)

        ORG 0x386E
; ---- 47529 move ----
e_mov:  push af
        push bc
        call enter
        jr c,.out
        call tog_sv
        call tog_ix
        call apply
.out:   ld c,D_MOV
        call leave
        pop bc
        pop af
        call 47465
        jp 47532

; ---- 47385 toggle the object's image ----
e_tog:  push af
        push bc
        call enter
        jr c,.out
        call tog_ix
        call apply
.out:   ld c,D_TOG
        call leave
        pop bc
        pop af
        call 47465
        jp 47388

; ---- 47349 toggle the saved image ----
e_old:  push af
        push bc
        call enter
        jr c,.out
        call tog_sv
        call apply
.out:   ld c,D_OLD
        call leave
        pop bc
        pop af
        call 47417
        jp 47352

; ---- 47908 paint: the object's colour may have changed (hit flash) ----
e_col:  push af
        push bc
        call enter
        jr c,.out
        call apply
.out:   ld c,D_COL
        call leave
        pop bc
        pop af
        ld l,(ix+3)
        jp 47911

; ---- 47964 clear: every image ends ----
e_clr:  push af
        push bc
        call speed_in
        push de
        push hl
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NOBJ*4
        jr nz,.h
        ld hl,OBJ
        ld b,NOBJ
.z:     ld (hl),0               ; nothing shown, nothing on the sprites
        inc hl
        inc hl
        inc hl
        ld (hl),0
        ld de,5
        add hl,de
        djnz .z
        ld hl,REF               ; no frame shown: every unit may be replaced (the cache keeps its contents)
        ld b,0
.r:     ld (hl),0
        inc l
        djnz .r
        ld c,D_CLR
        call leave
        pop bc
        pop af
        ld hl,16448
        jp 47967

; speed_in: latch the incoming speed, then 28 MHz, state page in, R at entry. AF, BC lost (pushed by the hook).
; 3.5 MHz part: the CALL, LD BC, LD A, OUT, INC B, IN, the NEXTREG: 82 T.
speed_in:
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        nextreg 0x57,STATE
        ld (VSPD),a
        ld a,r
        ld (VR),a
        ret

; enter: speed_in, DE and HL pushed (popped by leave), HL = object state, B = first sprite. Carry: IX is not an object.
enter:  call speed_in
        pop bc                  ; our return
        push de
        push hl
        push bc
        push ix
        pop hl
        ld de,-38658
        add hl,de
        jr nc,.bad              ; IX below the table
        ld a,h
        cp 2
        jr nc,.bad
        ld de,IXT
        add hl,de
        ld a,(hl)
        cp 0xFF
        jr z,.bad
        ld l,a
        ld h,high OBJ           ; OBJ is page aligned; A = 8i
        rrca                    ; 4i
        ld c,a
        ld a,24*4
        sub c
        ld b,a                  ; 4 * (24 - i)
        or a                    ; carry clear
        ret
.bad:   scf
        ret

; leave: C = the hook's R delta. HL, DE popped; slot 6 and 7 back, R set, then the caller's speed.
; After the LD R,A: LD A,(nn) 1, NEXTREG x3 6, RET 1, then the hook's own (POP BC, POP AF, its tail).
leave:  ld a,(VR)
        ld b,a
        add a,c
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        pop bc                  ; our return
        pop hl
        pop de
        push bc
        ld r,a
        ld a,(VSPD)
        nextreg 0x56,0
        nextreg 0x57,1
        nextreg 0x07,a
        ret

; toggle: C = frame, D = x, E = y, HL = object state. An empty frame draws nothing.
tog_sv: ld a,(SAVED)
        ld c,a
        ld a,(SAVED+1)
        ld d,a
        ld a,(SAVED+2)
        ld e,a
        jr toggle
tog_ix: ld c,(ix+0)
        ld d,(ix+3)
        ld e,(ix+4)
toggle: push hl
        call frptr              ; HL = table entry of frame C
        ld a,(hl)
        pop hl
        or a
        ret z                   ; empty frame
        ld a,(hl)
        or a
        jr z,.show
        cp c
        jr nz,.show             ; (never in the recordings: verify counts it)
        inc hl
        ld a,(hl)
        cp d
        jr nz,.sh2
        inc hl
        ld a,(hl)
        dec hl
        cp e
        jr nz,.sh2
        dec hl
        ld (hl),0               ; same image again: XOR takes it away
        ret
.sh2:   dec hl
.show:  ld (hl),c
        inc hl
        ld (hl),d
        inc hl
        ld (hl),e
        dec hl
        dec hl
        ret

frptr:  ld l,c                  ; HL = FRTAB + 8 * C
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        or high FRTAB
        ld h,a
        ret

; apply: show the object's state on its sprites. HL = state, B = first sprite. Nothing is written when
; the sprites already show it (frame, x, y and palette offset as last shown).
apply:  ld a,(ix+5)             ; palette offset << 4: ink + 8 if bright
        ld c,a
        and 7
        bit 6,c
        jr z,.nb
        or 8
.nb:    rlca
        rlca
        rlca
        rlca
        ld (SCOL),a
        ld a,(hl)
        or a
        jr z,.hid
        ld c,a                  ; C = frame shown
        push hl
        inc hl
        inc hl
        inc hl
        cp (hl)                 ; +3
        jr nz,.chg
        inc hl
        dec hl
        dec hl
        dec hl
        ld a,(hl)               ; +1 x
        inc hl
        inc hl
        inc hl
        cp (hl)                 ; +4
        jr nz,.chg2
        dec hl
        dec hl
        ld a,(hl)               ; +2 y
        inc hl
        inc hl
        inc hl
        cp (hl)                 ; +5
        jr nz,.chg3
        inc hl
        ld a,(SCOL)
        cp (hl)                 ; +6
        pop hl
        ret z                   ; as shown: nothing to do
        jr .draw
.chg:   pop hl
        call newframe           ; C = frame: the sprites' frame becomes it (units cached, references)
        jr .draw
.chg2:
.chg3:  pop hl
.draw:  jp show

.hid:   inc hl
        inc hl
        inc hl
        ld a,(hl)               ; +3: a frame on the sprites?
        or a
        ret z                   ; hidden already
        ld (hl),0
        ld c,a
        call unref
        ld a,b                  ; all four off
        ld c,4
.off:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        dec c
        jr nz,.off
        ret

; unref: C = a frame that was on an object's sprites: one reference less on its canonical frame. Keeps B, HL.
unref:  push hl
        call frptr
        ld de,4
        add hl,de
        ld l,(hl)               ; canonical
        ld h,high REF
        dec (hl)
        pop hl
        ret

; newframe: HL = state, C = frame shown. The old frame on the sprites loses a reference, the new one gains one
; and is made resident. Keeps B, HL.
newframe:
        push hl
        inc hl
        inc hl
        inc hl
        ld a,(hl)               ; +3 old
        ld (hl),c
        or a
        jr z,.n0
        push bc
        ld c,a
        call unref
        pop bc
.n0:    call frptr
        ld de,4
        add hl,de
        ld a,(hl)               ; canonical
        ld e,a
        ld d,high REF
        ex de,hl
        inc (hl)
        ld h,high CACHED
        ld a,(hl)
        or a
        call z,fetch            ; E = canonical, DE -> frame entry +4
        pop hl
        ret

; fetch: HL = CACHED + c (c = canonical frame), DE -> its frame entry +4 (+5 = units). Takes units by the clock
; hand, never one of a frame some object shows (REF > 0; this frame's REF is already counted), uploads the frame's
; patterns there, and records them in UL. Keeps B.
fetch:  push bc
        ld (hl),1               ; CACHED[c]
        ld a,l
        ld (VC),a
        ex de,hl
        inc hl
        ld a,(hl)               ; +5 units
        ld (VN),a
        dec hl
        dec hl
        dec hl
        dec hl
        ld c,(hl)               ; +1 unit in the source page
        dec hl
        ld a,(hl)               ; +0 the source page
        nextreg 0x56,a
        ld a,high UL
        ld (VK),a
.u:     ld a,(HAND)
        ld l,a
        inc a
        and 127
        ld (HAND),a
        ld h,high UOWN
        ld a,(hl)
        or a
        jr z,.take
        ld e,a                  ; its owner: shown by an object?
        ld d,high REF
        ld a,(de)
        or a
        jr nz,.u
        ld d,high CACHED        ; no: the owner is no longer resident
        ld (de),a
.take:  ld a,(VC)
        ld (hl),a               ; UOWN[u] = c
        ld e,l                  ; E = u
        ld l,a
        ld a,(VK)
        ld h,a
        inc a
        ld (VK),a
        ld (hl),e               ; UL_k[c] = u
        ld a,e                  ; pattern select: u / 2, half in bit 7
        rrca
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld a,c                  ; source unit -> HL = 0xC000 + 128 * unit
        ld l,0
        rra
        rr l
        or 0xC0
        ld h,a
        push bc
        ld bc,0x805B            ; 128 bytes
        otir
        pop bc
        inc c
        ld a,(VN)
        dec a
        ld (VN),a
        jr nz,.u
        pop bc
        ret

; show: HL = state (+3 frame on the sprites, already resident), B = first sprite. Writes the four sprites and
; records x, y and the palette offset as shown.
show:   push hl
        inc hl
        ld a,(hl)               ; x + 32, 9 bits
        add a,32
        ld (SXW),a
        ld a,0
        rla
        ld (SXW+1),a
        inc hl
        ld e,(hl)               ; y = bottom line
        inc hl
        ld c,(hl)               ; frame on the sprites
        inc hl
        dec hl
        dec hl
        dec hl
        ld a,(hl)               ; +1
        inc hl
        inc hl
        inc hl
        ld (hl),a               ; +4 = x
        dec hl
        dec hl
        ld a,(hl)
        inc hl
        inc hl
        inc hl
        ld (hl),a               ; +5 = y
        inc hl
        ld a,(SCOL)
        ld (hl),a               ; +6
        push de
        call frptr
        ld a,(hl)
        inc hl
        inc hl
        ld a,(hl)               ; bit 0: two columns, bit 1: two rows
        ld (SFL),a
        inc hl
        pop de
        ld a,e
        add a,33
        sub (hl)                ; top line + 32 = y - height + 1 + 32
        ld (STOP),a
        inc hl
        ld l,(hl)               ; canonical c: its units at UL + 256 k + c
        ld h,high UL
        ld e,b                  ; E = sprite number
        ld d,0                  ; D = row
.row:   ld c,0                  ; C = column
.col:   ld a,e
        nextreg 0x34,a
        push hl
        ld hl,(SXW)
        ld a,c
        or a
        jr z,.x0
        ld a,16
        add a,l
        ld l,a
        ld a,0
        adc a,h
        ld h,a
.x0:    ld a,l
        nextreg 0x35,a
        ld a,(STOP)
        bit 0,d
        jr z,.y0
        add a,16
.y0:    nextreg 0x36,a
        ld a,(SCOL)
        or h
        nextreg 0x37,a
        pop hl
        ld a,(hl)               ; this sprite's unit
        inc h
        push af
        rra                     ; pattern number = unit / 2
        and 0x3F
        or 0xC0                 ; visible, attribute 4 follows
        nextreg 0x38,a
        pop af
        and 1
        rrca
        rrca
        or 0x80                 ; 4-bit, half pattern in bit 6
        nextreg 0x39,a
        inc e
        inc c
        ld a,(SFL)
        and 1
        inc a
        cp c
        jr nz,.col
        inc d
        ld a,(SFL)
        rra
        and 1
        inc a
        cp d
        jr nz,.row
        ld a,b
        add a,4
        ld c,a
.h:     ld a,e                  ; the rest of the four off
        cp c
        jr z,.e
        nextreg 0x34,a
        nextreg 0x38,0
        inc e
        jr .h
.e:     pop hl
        ret
rom_end:

        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld d,0                  ; palette offset k
.k:     ld e,0                  ; entry n
.n:     ld a,e
        cp 1
        jr nz,.fx
        ld a,d                  ; entry 1: the game's colour k
        add a,low gamecol
        ld c,a
        ld a,0
        adc a,high gamecol
        ld b,a
        ld a,(bc)
        jr .w
.fx:    ld a,e                  ; entries 2-15: the same fixed colours in every offset, for painted pixels
        add a,low pal
        ld c,a
        ld a,0
        adc a,high pal
        ld b,a
        ld a,(bc)
.w:     nextreg 0x41,a
        inc e
        ld a,e
        cp 16
        jr nz,.n
        inc d
        ld a,d
        cp 16
        jr nz,.k
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
gamecol: DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6     ; RRRGGGBB: ink 0-7
        DB 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF      ; bright
pal:    DB 0x00,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4      ; entry 0 unused, entry 1 unused, 2-7 blue..yellow
        DB 0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF      ; white, then bright blue..white
setup_end:

        IFDEF QAOP
; ---- "QAOP + Space" toggle (asm/sabre_wulf_qaop.asm defines QAOP; the base assembles without it) ----
; At its own ORG in the ROM's 0xFF area, past the base code and its 20-byte register block, so nothing of the base
; moves: the toggle's bytes are this block and the two game bytes below, nothing else.
; The game's keyboard read 0xB0FA (reached from 0xB0A3 only when (38546) bits 2:1 = 0, keyboard chosen; the player's
; handler calls it once a round under DI, the hall of fame's name entry in its loop):
; LD A,0xFB / OUT (0xFD),A / IN A,(0xFE) / CPL / LD C,A / RET, so C = the action byte, Kempston's order:
; bit 0 Q left, 1 W right, 2 E up, 3 R down, 4 T fire (the joystick routines 0xB0D9, 0xB103, 0xB0B1 build the same).
; h_qaop (site: JP over its first 3 bytes) makes that 0xFBFE byte from Q A O P Space instead, active low:
;   bit 0 <- O (0xDFFE bit 1)   bit 2 <- Q (0xFBFE bit 0)   bit 4 <- Space (0x7FFE bit 0)
;   bit 1 <- P (0xDFFE bit 0)   bit 3 <- A (0xFDFE bit 0)   bits 5-7 <- 0xFBFE's own
; then goes on at 0xB100 (CPL / LD C,A / RET): A, C as the original's for that byte; F as the original's (pushed);
; B, DE, HL untouched. R as the original's at the RET: LD A,R gives R0 + 35 (R0 = R at 0xB0FA), 6 M1s follow the
; LD R,A, the original has 6 M1s from 0xB0FA to its RET: so R is set to R0 (bit 7 kept: the 7-bit field is shifted
; up by RLCA, 2 * 35 subtracted, shifted back). Clock: the caller's (no NEXTREG).
; The pause (0xAC28: EI / LD A,0x7E / OUT (0xFD),A / IN A,(0xFE) / BIT 0,A / RET NZ / CPL / AND 0x1E / RET NZ, then
; 0xAC36 pauses) pauses on Space or Caps Shift with no other key of rows 0x7FFE / 0xFEFE. With Space as fire it would
; pause at every shot. It runs every round, so the toggle rewrites its 13 bytes 0xAC29-0xAC35 in place (no hook):
;   LD A,0x7E / OUT (0xFD),A / OR 0x80 / IN A,(0xFE) / RRCA / RET C / NOP / NOP / NOP
; the game's own OUT (port 0x7EFD, value 0x7E), then row 0xFEFE alone: Caps Shift up returns (RET C), down pauses.
; The usual path has the original's 6 M1s (R unchanged) and 3 T more (OR 7, RRCA 4 against BIT 8). A and F at the
; return differ and are dead (each caller writes both before reading: 0x9A3C, 0x9F87, 0xBB7C). Caps Shift with
; Z X C V held pauses too (the original's other-keys test does not fit). Resuming is the game's own: Space or Caps Shift.
D_QAOP  EQU 35
        ORG 0x3C00
h_qaop: push af                 ; the entry F (S, Z, P/V, C survive the original's CPL)
        ld a,0xFB
        out (0xFD),a            ; as the original (port 0xFBFD)
        in a,(0xFE)             ; 0xFBFE: b7 b6 b5 T R E W Q
        rlca
        rlca
        rlca                    ; T R E W Q b7 b6 b5
        ld c,a
        ld a,0x7F
        in a,(0xFE)             ; 0x7FFE: Space in bit 0
        rra
        rl c                    ; R E W Q b7 b6 b5 Sp
        ld a,0xFD
        in a,(0xFE)             ; 0xFDFE: A in bit 0
        rra
        rl c                    ; E W Q b7 b6 b5 Sp A
        ld a,c
        add a,a
        add a,a
        add a,a                 ; carry = Q (bit 5)
        rl c                    ; W Q b7 b6 b5 Sp A Q
        ld a,0xDF
        in a,(0xFE)             ; 0xDFFE: P in bit 0, O in bit 1
        rra
        rl c                    ; Q b7 b6 b5 Sp A Q P
        rra
        rl c                    ; b7 b6 b5 Sp A Q P O
        ld a,r
        rlca
        sub 2*D_QAOP
        rrca
        ld r,a
        pop af
        ld a,c
        jp 0xB100
qaop_end:
        ENDIF

        SAVEBIN "sw_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sw_setup.bin",0xD000,setup_end-0xD000
