; Abu Simbel Profanation (Dinamic, 1985, 48K) - figures as hardware sprites. v1.0 (2026-11-07).
; Compiled BASIC game with one machine-code figure plotter, 0xDD78: IX block at 0x9700
; (+0 new y, +1 new x, +2 graphic pointer, +4 old y, +5 old x, +8 height, +10 width in bytes).
; It paints the figure's attribute over every non-BRIGHT cell of the box, LDIRs the shifted rows
; opaque, and LDIRs zeros over the rows and columns it left, all with interrupts off (DI ... EI).
;
; Sites (original bytes checked by abu_simbel.py):
;   AD1D  CD 78 DD        CALL plotter (player)           -> CALL e_pl
;   B465  CD 78 DD        CALL plotter (enemy 0-2)        -> CALL e_en
;   BD36  CD 75 E1        CALL attr clear (room redraw)   -> CALL e_cls
;   A361  CD 6B 0D        CALL ROM CLS (text screens)     -> CALL e_cl2
;   DE98  FB              EI (the plotter's last but one) -> NOP: the hook enables them at its end
; v1.0: the plotter runs whole and unchanged, called from the hook at 28 MHz with page 31 in slot 2
; (0x4000-0x5FFF), so every byte it writes to the screen and the attributes lands in a page that is never
; shown. Its only reads there (attributes and ATTR-T at 0xDECB-0xDED0) decide nothing but the byte it
; writes back (abu_simbel.py checks it). The game's stack is in slot 3 (0x65xx), never remapped.
; Pace (card patch.pace-limiter, asm/lib/hlib_pace.asm): the plot is a game-routine window (x K_PLOT);
; the hook's own work (the pattern) is debt, repaid from that window's wait. Interrupts stay off for the
; whole hook, as they are off for the whole original plot. Speed: HLIB_SPEED_IN / _OUT. R: HLIB_R_IN /
; _OUT, the plotter's own M1s measured by two LD A,R around it (none decide on P/V).
; Hooks in alt ROM image 1. State in page 31 above 0x1B00 (the plotter writes only 0x0000-0x1AFF of it),
; mapped at slot 7 inside the hook; colour table at slot 5 (pages 28-30); the hook reads only slots 2
; (0x5C8F, attributes), 4 (0x9700) and 6 (graphics) of the game.
; Sprites: enemies 0-2 (loop variable 0x971A), player 3 (on top, drawn last in the original too).
; Patterns: built at each plot, double buffered, 2 slots per sprite (slot = 2 * sprite + flip):
; the attributes switch only after the new image is complete.

        DEVICE ZXSPECTRUMNEXT

PLOTTER   EQU 0xDD78
GFX_LO    EQU 0xC800
GFX_LEN   EQU 0x1440        ; player graphics end at 0xDC40
MAPPAGE   EQU 28            ; colour map: pages 28-30, 4 bytes per graphics byte
STPAGE    EQU 31            ; hook state (above 0x1B00) and the plotter's screen while it runs (below)
SCRPAGE   EQU 10            ; the ULA screen's page (bank 5), the game's slot 2
GAMEPAGE7 EQU 1             ; the 48K game's pages at slots 7 and 5
GAMEPAGE5 EQU 5
N_SPR     EQU 4
SPR_PLAY  EQU 3
K_PLOT    EQU 111           ; the plotter's original time per unit of its 28 MHz time, x 16: JNext 1.1.104,
                            ; 299 player plots 110.6, 517 enemy plots 111.6 (runs/abu_simbel v10/work/plottime.py)
UNMEAS    EQU 47+59-16      ; debt the lines do not see, 1/16 lines (abu_simbel.py pace model, 2026-11-07): the
                            ; 3.5 MHz entry and exit + the gap between the debt window and the plot's (659 T), and
                            ; the plot window's own 28 MHz overhead around the plotter (128 T real), which x K
                            ; would otherwise lengthen the target; less one line, the wait's own rounding down
R_FIX     EQU 22            ; delta = (R after - R before the plotter) - R_FIX (hooklib.r_delta)
R_CLS     EQU 117           ; the hide hooks' constant delta: 1 - 7 - 5 (mod 128)

S7        EQU 0xE000        ; page 31 at slot 7
S2        EQU 0x4000        ; page 31 at slot 2 (only around the plotter)
O_ST      EQU 0x1B00
V_FLIP    EQU S7+O_ST       ; 4 bytes: pattern flip per sprite
V_S       EQU S7+O_ST+0x08
V_N       EQU S7+O_ST+0x09
V_SH      EQU S7+O_ST+0x0A
V_YS      EQU S7+O_ST+0x0B
V_SPD     EQU S7+O_ST+0x10  ; HLIB_SPEED latch
HLIB_V_R  EQU S7+O_ST+0x14  ; 3 bytes
V_R1      EQU S7+O_ST+0x18  ; R before the plotter (written through slot 2)
V_R2      EQU S7+O_ST+0x19  ; R after it
V_P2      EQU S7+O_ST+0x1A  ; the page slot 2 holds while the plotter runs
V_R1_2    EQU S2+O_ST+0x18
V_R2_2    EQU S2+O_ST+0x19
HLIB_V_PACE EQU S7+O_ST+0x20 ; 26 bytes
HLIB_PACE_NL EQU 312
V_ZERO    EQU S7+0x1C00     ; 128 zero bytes: the map of a graphic outside the table
V_MASK    EQU S7+0x1D00     ; 3 x 2 bytes: pixels hidden by the cell they fall in
O_PAT     EQU 0x1D10        ; the pattern builder's code (abu_simbel.py puts it in page 31)

        ORG 0x386E
        INCLUDE "lib/hlib_iff.asm"  ; macros only: the hooks read no IFF (DI at entry, EI at the end, as the plot)
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
e_pl:   di
        push af
        ld a,SPR_PLAY
        jr e_go
e_en:   di
        push af
        ld a,(0x971A)
        jr e_go                 ; (both entries: the same M1s to HLIB_R_IN)
e_go:   nextreg 0x57,STPAGE
        ld (V_S),a
        pop af
        HLIB_R_IN
        HLIB_SPEED_IN V_SPD     ; 28 MHz inside the hook
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        call hlib_debt_open     ; the pattern: hook time outside the window
        ld a,(V_S)
        cp N_SPR
        ld a,SCRPAGE
        jr nc,e_plot            ; guard, never seen: no sprite, the plot drawn on the screen as the original
        call e_pat              ; the pattern and the sprite (page 31, mapped at slot 7)
        ld a,STPAGE             ; the plotter's screen and attribute writes go to page 31
; ---- the plot itself: the game's plotter, whole, at 28 MHz ----
e_plot: ld (V_P2),a
        ld a,UNMEAS
        call hlib_debt_close
        call hlib_pace_open
        ld a,(V_P2)
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        nextreg 0x57,GAMEPAGE7
        nextreg 0x52,a          ; slot 2: page 31 (or the screen for the guard)
        pop af
        push af
        ld a,r
        ld (V_R1_2),a
        pop af
        call PLOTTER            ; DI ... RET, its EI at 0xDE98 a NOP
        push af
        ld a,r
        ld (V_R2_2),a
        nextreg 0x52,SCRPAGE
        nextreg 0x57,STPAGE
        push bc
        push de
        push hl
        ld a,(V_SPD)
        ld c,a
        ld a,K_PLOT
        call hlib_pace_waitk    ; interrupts off, as for the whole original plot
        ld a,(V_R2)
        ld hl,V_R1
        sub (hl)
        sub R_FIX
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_SPEED_OUT V_SPD
        HLIB_R_OUT
        nextreg 0x57,GAMEPAGE7
e_ei:   ei
        ret

; ---- screens that replace the play area: no figure stays ----
e_cls:  call hide_r
        jp 0xE175
e_cl2:  call hide_r
        jp 0x0D6B
hide_r: nextreg 0x57,STPAGE
        HLIB_R_IN
        push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp N_SPR
        jr nz,.h
        ld a,R_CLS
        call hlib_r_set
        pop af
        HLIB_R_OUT
        nextreg 0x57,GAMEPAGE7
        ret

rom_end:

; --- the pattern builder: page 31 at slot 7 (above the state; the plotter never writes there) ---
        ORG S7+O_PAT
e_pat:  ld a,(V_S)
        ld hl,V_FLIP
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        xor 1
        ld (hl),a
        ld c,a
        ld a,e
        add a,a
        add a,c                 ; pattern slot 2 * sprite + flip, not on show
        ld (V_N),a
        rrca                    ; port 0x303B: bits 5-0 = slot / 2, bit 7 = the 128-byte half
        ld bc,0x303B
        out (c),a
; The game's depth: a BRIGHT cell keeps its attribute, so a figure in a BRIGHT cell whose ink equals its
; paper (water 0x49, solid white 0x7F) cannot be seen. One 16-bit mask of those pixels per cell row touched.
        ld hl,(0x9700)          ; L = y, H = x
        ld a,h
        and 7
        ld (V_SH),a
        ld a,l
        and 7
        ld (V_YS),a
        ld a,l
        rrca
        rrca
        rrca
        and 0x1F
        ld e,a
        ld a,h
        rrca
        rrca
        rrca
        and 0x1F
        ld b,a
        ld h,0
        ld l,e
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x5800
        add hl,de
        ld e,b
        ld d,0
        add hl,de               ; HL = the first cell's attribute
        ld ix,V_MASK
        ld b,3
.crow:  push bc
        push hl
        ld c,0
        ld e,1
        ld b,3
.cc:    ld a,h
        cp 0x5B                 ; (0x5B00 and up: no copy; the plotter never reaches there, abu_simbel.py checks)
        ld a,(hl)
        jr nc,.nc
        set 7,h                 ; the same cell in page 31 (0xF800-0xFAFF), which the plotter reads as its screen:
        set 5,h                 ; it then takes the original's path (BRIGHT or not) and the original's time
        ld (hl),a
        res 7,h
        res 5,h
.nc:    inc hl
        bit 6,a
        jr z,.cn
        ld d,a
        rrca
        rrca
        rrca
        xor d
        and 7
        jr nz,.cn
        ld a,c
        or e
        ld c,a
.cn:    sla e
        djnz .cc
        ld hl,0
        ld a,c
        or a
        jr z,.store
        ld a,(V_SH)
        ld d,a
        ld b,16
.px:    ld a,d
        rrca
        rrca
        rrca
        and 3
        ld e,a
        inc e
        ld a,c
.sh:    rrca
        dec e
        jr nz,.sh               ; carry = this pixel's cell is hidden
        adc hl,hl
        inc d
        djnz .px
.store: ld (ix+0),h
        ld (ix+1),l
        inc ix
        inc ix
        pop hl
        ld de,32
        add hl,de
        pop bc
        djnz .crow
        ld a,(0x5C8F)           ; the attribute the plotter paints
        and 7
        jr nz,.ink
        ld a,8                  ; ink 0: index 8 is black, index 0 is transparent
.ink:   ld ixl,a
        ld hl,(0x9702)
        ld de,0x10000-GFX_LO
        add hl,de               ; carry: at or above GFX_LO
        jr nc,.nomap
        ld a,l
        and 0x1F
        jr nz,.nomap            ; not a whole 32-byte image
        ld a,h
        cp high GFX_LEN
        jr c,.inmap
        jr nz,.nomap
        ld a,l
        cp low GFX_LEN
        jr nc,.nomap
.inmap: add hl,hl
        add hl,hl               ; 4 map bytes per graphics byte
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,MAPPAGE
        nextreg 0x55,a
        ld a,h
        and 0x1F
        or 0xA0
        ld h,a
        jr .ready
.nomap: ld hl,V_ZERO
.ready: ex de,hl                ; DE = map
        ld hl,(0x9702)          ; HL = graphic
        ld ixh,32
.byte:  ld a,32                 ; this byte's mask: row (32 - IXH) / 2, side (32 - IXH) & 1
        sub ixh
        ld b,a
        srl a
        push hl
        ld hl,V_YS
        add a,(hl)
        rrca
        rrca
        rrca
        and 3
        add a,a
        ld c,a
        ld a,b
        and 1
        add a,c
        ld l,a
        ld h,high V_MASK
        ld a,(hl)
        ld iyl,a                ; IY is the hook's (pushed); interrupts are off here
        pop hl
        ld c,(hl)
        inc hl
.nib:   ld a,(de)               ; two pixels: hidden is clear; a painted nibble wins; else ink for a set bit
        inc de
        ld b,a
        ld a,iyl
        rlca
        ld iyl,a
        rlc c                   ; (rlc sets the carry from the graphic)
        jr nc,.lo0
        rrca                    ; put the hidden bit back in bit 0's place: A bit 7 = hidden
        jr .hi1
.lo0:   rrca
        bit 7,a
        jr z,.lo
        ld a,b
        and 0x0F
        ld b,a
        jr .lo
.hi1:   bit 7,a
        jr z,.hi2
        ld a,b
        and 0x0F
        ld b,a
        jr .lo
.hi2:   ld a,b
        and 0xF0
        jr nz,.lo
        ld a,ixl
        swapnib
        or b
        ld b,a
.lo:    ld a,iyl
        rlca
        ld iyl,a
        rlc c
        jr nc,.lo2
        rrca
        bit 7,a
        jr nz,.lc
        ld a,b
        and 0x0F
        jr nz,.out
        ld a,ixl
        or b
        ld b,a
        jr .out
.lo2:   rrca
        bit 7,a
        jr z,.out
.lc:    ld a,b
        and 0xF0
        ld b,a
.out:   ld a,b
        out (0x5B),a
        ld a,e
        and 3
        jr nz,.nib
        dec ixh
        jp nz,.byte
        nextreg 0x55,GAMEPAGE5
        ld a,(V_S)
        nextreg 0x34,a
        ld hl,(0x9700)          ; L = y, H = x
        ld a,h
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        nextreg 0x37,a
        ld a,l
        add a,32
        nextreg 0x36,a
        ld a,(V_N)
        ld b,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret
pat_end:

; --- setup routine (stub bank, 0xD000): palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x4B,0
        nextreg 0x43,0x20
        nextreg 0x40,1
        ld hl,pal
        ld b,15
.p:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .p
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
; index 1-7 Spectrum inks, 8 black, 9-15 the bright inks
pal:    db 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "as_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "as_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "as_pat.bin",S7+O_PAT,pat_end-(S7+O_PAT)
