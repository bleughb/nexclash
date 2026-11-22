; Jet Set Willy (Software Projects, 1984, 48K) - hardware sprites for every figure in the play area.
; Back-buffer composer, interrupts never on. The game keeps composing 0x5C00 (attributes) and 0x6000
; (pixels) exactly as before, because its logic reads them; only the two final LDIRs change source, to the
; clean room buffers 0x5E00 and 0x7000. Each plot site also sets a hardware sprite.
;
; Sites (original bytes checked by jsw.py):
;   89AD CD 8B 89     CALL 898B (start of a game pass)       -> CALL e_pass
;   89F5 21 00 60     LD HL,6000 (pixel blit)                -> CALL e_blit (hides unused sprites, HL = 7000)
;   8A26 21 00 5C     LD HL,5C00 (attribute blit)            -> LD HL,5E00 (no hook)
;   8912 3A 20 84     LD A,(8420) (room load)                -> CALL e_room
;   87CB 32 CE 85     LD (85CE),A (title)                    -> CALL e_ttl
;   8C4A 21 00 40     LD HL,4000 (game over scene)           -> CALL e_ovr
;   8AE6 C4 EB 8A     CALL NZ,8AEB (pause: colour cycle)     -> CALL NZ,e_pau (sprites off)
;   8B07 21 00 9A     LD HL,9A00 (resume)                    -> CALL e_res (sprites on)
;   9660 06 10 3A D3 85  LD B,10 / LD A,(85D3) (Willy)       -> CALL e_wil, NOP, NOP
;   95BB CD 68 96     CALL 9668 (toilet)                     -> CALL e_toi
;   922E CD 56 94     CALL 9456 (guardian)                   -> CALL e_gua
;   9563 CD 56 94     CALL 9456 (Maria)                      -> CALL e_mar
;   928E DD 7E 06     LD A,(IX+6) (arrow)                    -> CALL e_arr
;   930E DD 7E 05     LD A,(IX+5) (one rope pixel)           -> CALL e_rop
;   935E 3A D6 85     LD A,(85D6) (rope finished)            -> CALL e_rfl
;   9449 21 E1 80     LD HL,80E1 (item)                      -> CALL e_itm
;
; Sprites: one per plot in plot order (higher number on top, so the game's own depth), 4-bit patterns.
; Patterns are written at every plot into the bank not on show, then the attributes switch to them
; (patch.display-atomic-switch): pattern = sprite number + BANK (0 / 64).
; Palette (static, setup; offset 0 only): index 1-7 normal blue..white, 8 black, 9-15 bright; 0 transparent. A figure's
; colour is in its pattern nibbles (S_I ink, S_B paper of a solid figure), so one figure can hold several colours.
; Colour map (patch.runtime-colour-map): Next pages 28-32 hold 4 bytes per graphics byte 0x9C00-0xBFFF, as pattern
; bytes, 0 nibble = default; page 33: E000 + room * 32 items, E800 + room item flags, F000 + n / 32 "this graphic is
; painted". Mapped at slot 7 only inside an upload (interrupts are off); the game never maps these pages. Recolour
; rewrites only those pages.
; Hook state: HS.. in the printer buffer (jsw.py and the scan prove it untouched). Hooks run at 28 MHz.

        DEVICE ZXSPECTRUMNEXT

HS      EQU 0x5B60
COUNT   EQU HS+0
HIWAT    EQU HS+1
BANK    EQU HS+2
S_X     EQU HS+3
S_Y     EQU HS+4
S_I     EQU HS+5
S_P     EQU HS+6
R_OPEN  EQU HS+7
R_X0    EQU HS+8
R_Y0    EQU HS+9
R_ROWS  EQU HS+10               ; 16 bytes: 0 = no pixel, else x - R_X0 + 1
S_B     EQU HS+26
S_R     EQU HS+27
S_SPD   EQU HS+29               ; the caller's CPU speed (NR 7 bits 1:0), given back on the way out
MAXSPR  EQU 64

        ORG 0x386E

; ---- every pass -------------------------------------------------------------------------------
e_pass: push af                 ; four instructions: at the caller's speed (a switch costs more than they do)
        xor a
        ld (COUNT),a
        ld a,(BANK)
        xor 64
        ld (BANK),a
        pop af
        jp 0x898B

e_blit: push af
        push bc
        ld a,(COUNT)
        call hidefrom
        ld a,(COUNT)
        ld (HIWAT),a
        pop bc
        pop af
neg_blit:
        ld hl,0x7000
        ret

; A = first sprite to hide, up to the larger of HIWAT and COUNT, at 28 MHz. Clobbers A, B, C.
hidefrom:
        ld c,a
        call spdin
        ld a,(HIWAT)
        ld b,a
        ld a,(COUNT)
        cp b
        jr c,.k
        ld b,a
.k:     ld a,c
.l:     cp b
        jr nc,spdout
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .l

hideall:
        push af
        push bc
        xor a
        call hidefrom
        xor a
        ld (COUNT),a
        ld (HIWAT),a
        pop bc
        pop af
        ret

e_room: call hideall
        ld a,(0x8420)
        ret

e_ttl:  call hideall
        ld (0x85CE),a
        ret

e_ovr:  call hideall
        ld hl,0x4000
        ret

e_pau:  nextreg 0x15,0
        jp 0x8AEB

e_res:  nextreg 0x15,1
        ld hl,0x9A00
        ret

; pushes everything and goes to 28 MHz; rest undoes it, flags and all
enter:  ex (sp),hl
        push de
        push bc
        push af
        push ix
        push iy
        call spdin
        push hl                 ; back to the hook, with HL as the site had it (A is not kept)
        ld hl,12
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ret

rest:   pop hl
        ld (S_R),hl
        pop iy
        pop ix
        call spdout
        pop af
        pop bc
        pop de
        pop hl
        push hl
        ld hl,(S_R)
        ex (sp),hl
        ret

; spdin: the caller's speed latched, then 28 MHz. Keeps B, C, D, E, H, L; A, F lost. Port 0x243B selects NR 7 from
; the setup on (a Spectrum game never uses it, NEXTREG never changes it), so one IN reads it. spdout: back to it; A lost.
spdin:  push bc
        ld bc,0x253B
        in a,(c)
        and 3
        ld (S_SPD),a
        nextreg 7,3
        pop bc
        ret
spdout: ld a,(S_SPD)
neg_spd:nextreg 7,a
        ret

; ---- Willy: DE = graphic, IX = row table entry -------------------------------------------------
e_wil:  call enter
        ld a,ixl
        srl a
        ld (S_Y),a
        ld a,(0x85D3)
        and 0x1F
        add a,a
        add a,a
        add a,a
        ld (S_X),a
        ld a,(0x80A0)           ; ink 7, the background's bright (961E)
        and 0x40
        or 7
        call colour
        call plot32
        call rest
        ld b,16
neg_reg:
        ld a,(0x85D3)
        ret

; ---- toilet: DE = graphic, IX = row table entry, C = column; paints 07 --------------------------
e_toi:  call enter
        ld a,ixl
        srl a
        ld (S_Y),a
        ld a,c
        add a,a
        add a,a
        add a,a
        ld (S_X),a
        ld a,7
        call colour
        call plot32
        call rest
        jp 0x9668

; ---- guardian: HL = 0x6000 address, DE = graphic, IX = entity -----------------------------------
e_gua:  call enter
        ld a,(ix+1)             ; bit 3 bright, bits 0-2 ink (91EE)
        ld c,a
        and 8
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,c
        and 7
        or b
        call colour
        call xy
        ld (S_X),a
        ld a,c
        ld (S_Y),a
        call plot32
        call rest
        jp 0x9456

; ---- Maria: HL = 0x6000 address on a cell edge; top half 45, bottom half 07 (956C, 9572) ---------
e_mar:  call enter
        call xy
        ld (S_X),a
        ld a,c
        ld (S_Y),a
        ld a,0x45
        call colour
        push de
        pop ix
        call half
        ld a,(S_Y)
        add a,8
        ld (S_Y),a
        ld a,7
        call colour
        call half
        call rest
        jp 0x9456

; one sprite from 8 rows at IX (IX moves on), the other 8 rows empty
half:   call begin
        ret nc
        ld l,16
        call upgfx
        ld b,64
        call outz
        jp fin

; ---- arrow: H,L = its top row in 0x6000 (after DEC H), IX = entity; rows (IX+6), FF, (IX+6) --------
e_arr:  call enter
        ld a,h                  ; the cell's attribute, painted ink 7 at 9289: its bright
        and 8
        rrca
        rrca
        rrca
        or 0x5C
        ld d,a
        ld e,l
        ld a,(de)
        call colour
        call paper              ; overwrites in the original, so solid: paper opaque
        call xy
        ld (S_X),a
        ld a,c
        ld (S_Y),a
        call begin
        jr nc,.x
        ld a,(S_B)
        ld e,a
        ld a,(S_I)
        ld d,a
        ld a,(ix+6)
        call out8
        ld b,4
        call outz
        ld a,0xFF
        call out8
        ld b,4
        call outz
        ld a,(ix+6)
        call out8
        ld b,108
        call outz
        call fin
.x:     call rest
        ld a,(ix+6)
        ret

; ---- one item: DE = 0x6000 address on a cell edge. Overwrites in the original, so solid: paper opaque ----
e_itm:  call enter
        ld a,d                  ; the cell's attribute, just painted at 943D
        and 8
        rrca
        rrca
        rrca
        or 0x5C
        ld h,a
        ld l,e
        ld a,(hl)
        call colour
        call paper
        ex de,hl
        call xy
        ld (S_X),a
        ld a,c
        ld (S_Y),a
        call begin
        jr nc,.x
        ld a,(0x8420)           ; the room's item graphic comes from C0E1 + room * 256: its colours
        and 0x3F
        ld l,a
        ld h,0xE8
        nextreg 0x57,33
        ld c,(hl)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        or 0xE0
        ld h,a
        push hl
        pop iy
        ld a,(S_B)
        ld e,a
        ld a,(S_I)
        ld d,a
        ld ix,0x80E1
        ld l,8
        ld a,c
        or a
        jr z,.u
.p:     ld a,(ix+0)
        call out8o
        ld b,4
        call outz
        inc ix
        dec l
        jr nz,.p
        jr .e
.u:     ld a,(ix+0)
        call out8
        ld b,4
        call outz
        inc ix
        dec l
        jr nz,.u
.e:     nextreg 0x57,1
        ld b,64
        call outz
        call fin
.x:     call rest
neg_itm:
        ld hl,0x80E1
        ret

; ---- rope: one pixel. HL = 0x6000 address, (IX+5) = mask ----------------------------------------
e_rop:  call enter
        call xy                 ; A = x of the cell, C = y
        ld b,a
        ld a,(ix+5)
.k:     rlca                    ; mask 0x80 = column 0
        jr c,.g
        inc b
        jr .k
.g:     ld a,(R_OPEN)
        or a
        jr z,.new
        ld a,(R_Y0)
        ld e,a
        ld a,c
        sub e
        cp 16
        jr nc,.fl
        ld e,a                  ; row in the slice
        ld a,(R_X0)
        ld d,a
        ld a,b
        sub d
        cp 16
        jr c,.st
.fl:    push bc
        call rflush
        pop bc
.new:   ld a,c
        ld (R_Y0),a
        ld a,b
        sub 8
        jr nc,.o
        xor a
.o:     ld (R_X0),a
        ld hl,R_ROWS
        ld d,16
        xor a
.z:     ld (hl),a
        inc hl
        dec d
        jr nz,.z
        inc a
        ld (R_OPEN),a
        ld a,(R_X0)
        ld d,a
        ld a,b
        sub d
        ld e,0
.st:    inc a
        ld d,0
        ld hl,R_ROWS
        add hl,de
        ld (hl),a
        call rest
        ld a,(ix+5)
        ret

; ---- rope finished ------------------------------------------------------------------------------
e_rfl:  call enter
        ld a,(R_OPEN)
        or a
        call nz,rflush
        call rest
        ld a,(0x85D6)
        ret

; the open slice -> one sprite in the room's background ink (the rope paints no attribute)
rflush: ld a,(0x80A0)
        call colour
        ld a,(R_X0)
        ld (S_X),a
        ld a,(R_Y0)
        ld (S_Y),a
        xor a
        ld (R_OPEN),a
        call begin
        ret nc
        ld hl,R_ROWS
        ld e,16
.r:     ld a,(hl)
        inc hl
        ld d,a                  ; 0, or offset + 1
        ld c,0                  ; byte index * 2 = pixel
.b:     xor a
        bit 7,d
        jr nz,.w                ; no pixel left on this row
        ld a,d
        or a
        jr z,.w0
        dec a                   ; pixel offset
        sub c
        jr z,.hi
        dec a
        jr nz,.w0
        ld a,(S_I)
        jr .w
.hi:    ld a,(S_I)
        swapnib
        jr .w
.w0:    xor a
.w:     out (0x5B),a
        inc c
        inc c
        ld a,c
        cp 16
        jr nz,.b
        dec e
        jr nz,.r
        jp fin

; ---- common -------------------------------------------------------------------------------------
; A = attribute -> S_I = its ink as a palette index, S_B = 0 (see-through). Keeps A.
colour: push bc
        ld c,a
        call index
        ld (S_I),a
        xor a
        ld (S_B),a
        ld a,c
        pop bc
        ret

; A = attribute -> S_B = its paper as a palette index (a solid figure). Keeps A.
paper:  push bc
        ld c,a
        rrca
        rrca
        rrca
        call index
        ld (S_B),a
        ld a,c
        pop bc
        ret

; A bits 0-2 = colour, C bit 6 = bright -> palette index 1-15, black = 8.
index:  and 7
        jr nz,.n
        ld a,8
        ret
.n:     bit 6,c
        ret z
        or 8
        ret

; HL = 0x6000 layout address -> A = x (0..248), C = y. Keeps DE, HL, IX.
xy:     ld a,h
        and 0x18
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,h
        and 7
        or c
        ld c,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or c
        ld c,a
        ld a,l
        and 0x1F
        add a,a
        add a,a
        add a,a
        ret

; DE = 32 bytes of graphic -> a sprite
plot32: push de
        pop ix
        call begin
        ret nc
        ld l,32
        call upgfx
        jp fin

; L graphics bytes at IX -> pattern bytes in the figure's colours, with the colour map if this graphic is painted
upgfx:  push hl
        call ovfind
        pop hl
        ld a,(S_B)
        ld e,a
        ld a,(S_I)
        ld d,a
        jr z,.u
.p:     ld a,(ix+0)
        call out8o
        inc ix
        dec l
        jr nz,.p
        nextreg 0x57,1
        ret
.u:     ld a,(ix+0)
        call out8
        inc ix
        dec l
        jr nz,.u
        ret

; the negative control's jump target: leaves slot 7 mapped
ovbad:  nextreg 0x57,33
        xor a
        ret

; IX = graphic -> NZ and IY = its colours (their page at slot 7), or Z with slot 7 as the game has it
ovfind: ld a,ixh
        sub 0x9C
        cp 0x24
        jr nc,.no
        ld b,a
        ld h,0
        ld l,b
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,ixl
        rlca
        rlca
        rlca
        and 7
        add a,l
        ld l,a
        ld a,h
        adc a,0xF0
        ld h,a
        nextreg 0x57,33
        ld a,(hl)
        or a
        jr z,.off
        ld a,b
        rrca
        rrca
        rrca
        and 0x1F
        add a,28
        nextreg 0x57,a
        ld a,b
        and 7
        ld h,a
        ld a,ixl
        ld l,a
        add hl,hl
        add hl,hl
        ld a,h
        or 0xE0
        ld h,a
        push hl
        pop iy
        or a
        ret
.off:   nextreg 0x57,1
.no:    xor a
        ret

; takes a sprite and points the pattern port at its pattern. NC = table full. Clobbers A, B, C.
begin:  ld a,(COUNT)
        cp MAXSPR
        ret nc
        ld c,a
        inc a
        ld (COUNT),a
        ld a,(BANK)
        add a,c
        ld (S_P),a
        srl a
        jr nc,.e
        or 0x80
.e:     ld b,0x30
        ld c,0x3B
        out (c),a
        ld a,(COUNT)
        dec a
        nextreg 0x34,a
        scf
        ret

; the attributes, last. Clobbers A, C.
fin:    ld a,(S_X)
        add a,32
        ld c,a
        ld a,0
        adc a,0
        nextreg 0x37,a
        ld a,c
        nextreg 0x35,a
        ld a,(S_Y)
neg_y:  add a,32
        nextreg 0x36,a
        ld a,(S_P)
        ld c,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; A = 8 pixels -> 4 pattern bytes: ink pixels D, others E. Clobbers A, B, C, H.
out8:   ld c,a
        ld b,4
.l:     ld a,e
        rlc c
        jr nc,.a
        ld a,d
.a:     swapnib
        ld h,a
        ld a,e
        rlc c
        jr nc,.b
        ld a,d
.b:     or h
        out (0x5B),a
        djnz .l
        ret

; out8 + the colour map at IY (IY moves on 4 bytes): a non-zero nibble replaces the default
out8o:  ld c,a
        ld b,4
.l:     ld a,e
        rlc c
        jr nc,.a
        ld a,d
.a:     swapnib
        ld h,a
        ld a,e
        rlc c
        jr nc,.b
        ld a,d
.b:     or h
        ld h,a
        ld a,(iy+0)
        inc iy
        or a
        jr z,.w
        push bc
        ld c,a
        and 0xF0
        jr nz,.hi
        ld a,h
        and 0xF0
.hi:    ld b,a
        ld a,c
        and 0x0F
        jr nz,.lo
        ld a,h
        and 0x0F
.lo:    or b
        ld h,a
        pop bc
.w:     ld a,h
        out (0x5B),a
        djnz .l
        ret

; B zero bytes (B = 0 is 256)
outz:   xor a
.l:     out (0x5B),a
        djnz .l
        ret

rom_end:

; ---- setup routine (stub bank, 0xD000): palette, hide all, sprites on ---------------------------
        ORG 0xD000
setup:  nextreg 0x43,0x20               ; sprite palette 0, auto-increment
        nextreg 0x4B,0                  ; index 0 transparent
        nextreg 0x40,0
        ld hl,cols
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ld bc,0x243B                    ; select NR 7 for the hooks' speed reads (spdin)
        ld a,7
        out (c),a
        ret
cols:   DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        DB 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "jsw_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "jsw_setup.bin",0xD000,setup_end-0xD000
