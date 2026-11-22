; Manic Miner (Bug-Byte, 1983, 48K) - every moving figure, the items and the portal as hardware
; sprites. Back-buffer composer: the game plots into 0x6000 and paints 0x5C00, then LDIRs them to
; the ULA. Logic (pixel collisions, attribute reads) only reads the buffers, so they stay exactly as
; the original leaves them; only the two LDIRs' SOURCES change: pixels from the clean buffer 0x7000,
; attributes from the clean buffer 0x5E00. The LDIRs keep their length, so the game's speed (no frame
; sync, interrupts off the whole game) does not change.
;
; Patch sites (original bytes checked by manic_miner.py):
;   0x86AD CD 75 8A  CALL 0x8A75 (cavern load)  -> CALL e_cav   hide all, upload patterns + palette
;   0x8DEB CD F4 8F  horizontal guardian plot   -> CALL e_hg
;   0x8E39 CD F4 8F  Eugene plot                -> CALL e_eug
;   0x8EC9 CD F4 8F  Skylab plot                -> CALL e_sky
;   0x8F3B CD F4 8F  vertical guardian plot     -> CALL e_sky
;   0x91D7 CD F4 8F  Kong falling (solid)       -> CALL e_kfl
;   0x9206 CD F4 8F  Kong standing              -> CALL e_kst
;   0x8FAB CD D5 92  item plot (8 rows)         -> CALL e_item
;   0x8FEF 2A B2 80  LD HL,(0x80B2) (portal)    -> CALL e_port
;   0x927F 3A 68 80  LD A,(0x8068) (Willy)      -> CALL e_wil
;   0x87A2 21 00 60  LD HL,0x6000 (pixel blit)  -> CALL e_blit  hide unused slots, HL = 0x7000
;   0x87C8 21 00 5C  LD HL,0x5C00 (attr blit)   -> CALL e_attr  HL = 0x5E00 (exceptions below)
;   0x85E6 21 00 40  LD HL,0x4000 (title)       -> CALL e_hl40  hide all
;   0x8963 21 00 40  LD HL,0x4000 (game over)   -> CALL e_hl40  hide all
;   0x9040 11 60 82  LD DE,0x8260 (swordfish)   -> CALL e_de82  hide all
;
; Sprites: slots in plot order (higher slot on top = the game's own overwrite order), counter CNT in
; the printer buffer (scan: untouched). Patterns, 4-bit, rebuilt at every cavern load:
;  0-7 Willy (0x8200), 8-15 guardian frames (0x8100), 16-17 Kong falling frames solid (0x8140),
;  18 item solid (0x80B4), 19 portal solid (0x8090), 20 portal inverted (FLASH), 21 Eugene (0x80E0).
; Nibbles: 1 = ink (palette offset = the figure's ink + 8 * BRIGHT), 2 = item paper, 3 = portal paper,
;  4 = cavern background paper; the last three set in the sprite palette at each cavern load.

        DEVICE ZXSPECTRUMNEXT

CNT      EQU 0x5BFF
NSPR     EQU 16
PLOT     EQU 0x8FF4
ITEMPLOT EQU 0x92D5
CAVLOAD  EQU 0x8A75
BGATTR   EQU 0x8020
PAT_G    EQU 8
PAT_K    EQU 16
PAT_I    EQU 18
PAT_P    EQU 19
PAT_E    EQU 21

        ORG 0x386E
; ---- plot hooks: registers as the plot call expects them, all kept; each ends in the plot itself ----
e_hg:   nextreg 0x07,3
        push af
        push bc
        ld a,(iy+0)
        ld b,a
        ld a,e
        call frame
        jr plot1

e_sky:  nextreg 0x07,3
        push af
        push bc
        ld a,(BGATTR)
        and 0x40
        or (iy+0)
        ld b,a
        ld a,e
        call frame
        jr plot1

e_kst:  nextreg 0x07,3
        push af
        push bc
        ld b,0x44
        ld a,e
        call frame
        jr plot1

e_kfl:  nextreg 0x07,3
        push af
        push bc
        ld a,(BGATTR)
        and 0x40
        or 6
        ld b,a
        ld a,e
        rlca
        rlca
        rlca
        and 1                   ; E = 0x40 or 0x60
        add a,PAT_K
        ld c,a
        jr plot1

e_eug:  nextreg 0x07,3
        push af
        push bc
        ld a,(0x8074)           ; items left: white, else the game's cycling ink (0x8E50)
        or a
        ld a,7
        jr nz,.k
        ld a,(0x80BD)
        rrca
        rrca
        and 7
.k:     ld b,a
        ld a,(BGATTR)
        and 0x40
        or b
        ld b,a
        ld c,PAT_E
plot1:  push de
        push hl
        call put
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x07,0
        jp PLOT

; A = E of the plot call = frame * 32 -> C = guardian pattern
frame:  rlca
        rlca
        rlca
        and 7
        add a,PAT_G
        ld c,a
        ret

e_item: nextreg 0x07,3
        push af
        push bc
        push de
        push hl
        ld a,(iy+0)
        ld b,a
        ld c,PAT_I
        ex de,hl                ; DE = where the item is plotted
        call put
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x07,0
        jp ITEMPLOT

e_port: nextreg 0x07,3
        push af
        push bc
        push de
        ld hl,(0x80B2)
        push hl
        ld a,(0x808F)
        ld b,a
        ld c,PAT_P
        rlca
        jr nc,.n                ; no FLASH
        ld a,(0x80BD)           ; down 4 per game loop: about the ULA's flash rate
        and 0x10
        jr z,.n
        inc c
.n:     call put
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x07,0
        ret

e_wil:  nextreg 0x07,3
        push af
        push bc
        push de
        push hl
        ld a,(BGATTR)
        and 0x40
        or 7
        ld b,a
        ld a,(0x806A)
        and 1
        add a,a
        add a,a
        ld c,a
        ld a,(0x8069)
        and 3
        or c
        ld c,a                  ; pattern 0-7 = the frame the plot below selects (0x928E)
        ld a,(0x806C)
        and 31
        ld d,a
        ld a,(0x8068)
        rrca
        and 0x7F
        ld e,a
        call putxy
        pop hl
        pop de
        pop bc
        pop af
        ld a,(0x8068)
        nextreg 0x07,0
        ret

; ---- blits ----
e_blit: nextreg 0x07,3
        push af
        push bc
        ld a,(CNT)
        ld b,a
.h:     ld a,b
        cp NSPR
        jr nc,.e
        nextreg 0x34,a
        nextreg 0x38,0
        inc b
        jr .h
.e:     xor a
        ld (CNT),a
        pop bc
        pop af
        ld hl,0x7000
        nextreg 0x07,0
        ret

; HL on arrival: 0x8000 after the pixel LDIR; 0x5DFF after the extra-life fill of 0x5C00 (0x87C6).
e_attr: nextreg 0x07,3
        push af
        ld a,h
        cp 0x5D
        jr z,.fill
        ld a,(0x8407)
        cp 18
        jr z,.beam
        ld hl,0x5E00
        jr .out
.fill:  ld hl,0x5C00            ; the whole play area is the effect's colour
        jr .out
.beam:  push de                 ; Solar Power Generator: the light beam only exists in 0x5C00.
        push bc                 ; 0x5C00 is dead after this copy (rewritten at 0x8748): clean it
        ld hl,0x5C00            ; of the figures' paint, keep the beam
        ld de,0x5E00
        ld bc,0x0200
.b:     ld a,(hl)
        cp 0x77
        jr z,.k
        ld a,(de)
        ld (hl),a
.k:     inc hl
        inc de
        dec bc
        ld a,b
        or c
        jr nz,.b
        pop bc
        pop de
        ld hl,0x5C00
.out:   pop af
        nextreg 0x07,0
        ret

; ---- screens without figures ----
e_hl40: nextreg 0x07,3
        call hide
        ld hl,0x4000
        nextreg 0x07,0
        ret
e_de82: nextreg 0x07,3
        call hide
        ld de,0x8260
        nextreg 0x07,0
        ret

hide:   push af
        xor a
        ld (CNT),a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSPR
        jr nz,.h
        pop af
        ret

; ---- one sprite. HL = buffer address, B = attribute (ink + BRIGHT), C = pattern ----
put:    ld a,l
        and 31
        ld d,a                  ; column
        ld a,l
        and 0xE0
        rrca
        rrca
        ld e,a
        ld a,h
        and 7
        or e
        ld e,a
        ld a,h
        and 0x18
        rlca
        rlca
        rlca
        or e
        ld e,a                  ; pixel row
; D = column, E = pixel row, B = attribute, C = pattern
putxy:  ld a,(CNT)
        cp NSPR
        ret nc
        nextreg 0x34,a
        inc a
        ld (CNT),a
        ld a,e
        add a,32
        nextreg 0x36,a
        ld a,b
        and 0x40
        rrca
        rrca
        rrca
        ld e,a
        ld a,b
        and 7
        or e
        swapnib
        ld e,a                  ; palette offset << 4
        ld a,d
        add a,a
        add a,a
        add a,a
        add a,32
        nextreg 0x35,a
        ld a,e
        adc a,0                 ; X8
        nextreg 0x37,a
        ld a,c
        rrca
        and 0x3F
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; ---- cavern load: hide everything, build this cavern's patterns and palette, then load as before ----
e_cav:  nextreg 0x07,3
        push af
        push bc
        push de
        push hl
        call hide
        ld bc,0x303B
        xor a
        out (c),a
        ld de,0x0100            ; D = ink nibble, E = paper nibble
        ld hl,0x8200            ; Willy
        ld a,8
        call pats
        ld hl,0x8100            ; guardians
        ld a,8
        call pats
        ld e,4
        ld hl,0x8140            ; Kong falling: overwrites what is behind him
        ld a,2
        call pats
        ld e,2
        ld hl,0x80B4            ; item: 8 x 8, rest transparent
        ld b,8
.i:     push bc
        ld a,(hl)
        inc hl
        call px8
        xor a
        ld b,4
.z:     out (0x5B),a
        djnz .z
        pop bc
        djnz .i
        xor a
        ld b,64
.y:     out (0x5B),a
        djnz .y
        ld e,3
        ld hl,0x8090            ; portal
        ld a,1
        call pats
        ld de,0x0301
        ld hl,0x8090            ; portal, FLASH phase
        ld a,1
        call pats
        ld de,0x0100
        ld hl,0x80E0            ; Eugene
        ld a,1
        call pats
        ld a,(0x8075)           ; palette: item paper
        ld b,2
        call papers
        ld a,(0x808F)           ; portal paper
        ld b,3
        call papers
        ld a,(BGATTR)           ; background paper
        ld b,4
        call papers
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x07,0
        jp CAVLOAD

; A patterns from HL
pats:   push af
        ld b,32
.r:     ld a,(hl)
        inc hl
        push bc
        call px8
        pop bc
        djnz .r
        pop af
        dec a
        jr nz,pats
        ret

; A = 8 pixels -> 4 pattern bytes, D = ink nibble, E = paper nibble. Destroys A, B, C.
px8:    ld c,a
        ld b,4
.a:     sla c
        ld a,e
        jr nc,.p0
        ld a,d
.p0:    swapnib
        sla c
        jr nc,.p1
        or d
        jr .w
.p1:    or e
.w:     out (0x5B),a
        djnz .a
        ret

; A = attribute: sprite palette index (o << 4) + B = its paper colour, every offset o
papers: push hl
        ld c,a
        rrca
        rrca
        rrca
        and 7
        ld l,a
        ld a,c
        and 0x40
        rrca
        rrca
        rrca
        or l
        ld l,a
        ld h,0
        push de
        ld de,cols
        add hl,de
        pop de
        ld c,(hl)               ; colour
        ld a,b
.l:     nextreg 0x40,a
        ld h,a
        ld a,c
        nextreg 0x41,a
        ld a,h
        add a,16
        cp b
        jr nz,.l
        pop hl
        ret

cols:   db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
rom_end:

; --- setup routine (stub bank, 0xD000): palette (index o << 4 + 1 = Spectrum colour o), hide, on ---
        ORG 0xD000
setup:  nextreg 0x43,0x20           ; sprite palette 0
        ld hl,tab
        ld b,16
        ld a,1
.p:     nextreg 0x40,a
        ld c,a
        ld a,(hl)
        inc hl
        nextreg 0x41,a
        ld a,c
        add a,16
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
tab:    db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "mm_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "mm_setup.bin",0xD000,setup_end-0xD000
