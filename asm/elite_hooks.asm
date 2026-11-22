; Elite (Firebird 1985, Russian 128K hack) - engine 'elite', milestone M1 (early integrated diagnostic):
; the viewport is mirrored onto a double-buffered Layer 2 in colour (per ship model, per draw category).
; Design: games/elite.md "## Build plan". All hook code lives in alt ROM image 1 (stateless; the one state byte,
; the current colour, is NextReg $7F: 0 = ship mode, colour from the ship's blueprint in IY).
;
; The game ORs every line pixel into a mono back buffer (bank 0, 0xC000-0xCFDF, screen layout, shown at 0x4020 by
; the copy 0x7FBE). Each buffer write instruction is replaced by a one-byte RST:
;   LD (HL),A  (77)    -> RST 18h  (DF)      h_plot: does the write, then sets / clears the Layer 2 pixels whose
;   LD (HL),B  (70)    -> RST 10h  (D7)      buffer bit changed (0->1: current colour, 1->0: transparent)
;   LD (HL),FF (36 FF) -> RST 20h, NOP (E7 00)
; The buffer stays exactly the original's (the ULA copy keeps running underneath: anything not mirrored shows white).
; Category hooks (CALL / JP retargeted, original bytes checked by nexclash/elite.py):
;   0x74EE CALL Z,0x7584 planet / sun   0x74F1 CALL 0x7898 stars   0x74F4 CALL 0xD03C messages
;   0x74F7 CALL 0x9C80 combat (lasers, crosshair; ships through the wrapper below)
;   0x9E44 JP 0xF8B4 (ship draw wrapper) -> ship mode    0xF8D4 JP 0x9E47 (wrapper exit) -> combat colour
;   0x8080 buffer clear (DI / LD BC,30) -> also clears the Layer 2 back buffer, colour reset to white
;   0x7FBE buffer copy (LD HL,0xC000)   -> flips Layer 2 (NR $12 <-> NR $13) first

        DEVICE ZXSPECTRUMNEXT

L2_A      EQU 16            ; Layer 2 16K banks: 16-18 and 19-21 (8K pages 32-37, 38-43)
L2_B      EQU 19
TRANS     EQU 0xE3          ; Layer 2 transparent colour (NR $14 default)
C_WHITE   EQU 0xFF
C_RED     EQU 0xE0
C_PLANET  EQU 0x4B
C_SHIPDEF EQU 0xFF
P_L2      EQU 0x0B          ; port 0x123B: write-over on (bit 0), visible (bit 1), shadow bank NR $13 (bit 3)
P_SHOW    EQU 0x02          ; visible only

; ---------------------------------------------------------------------------------------------------------------
; RST vectors (alt ROM low image, 0x0010-0x0027; Sinclair's bytes there are never read by the game: access scan).
; Not RST 08h: CSpect (with -mmc) traps it as an esxDOS call and skips the next byte as the function number
; (the star writer's LD (HL),A / RET at 0xA84B lost its RET - the M1 build froze, 2026-11-23).
; ---------------------------------------------------------------------------------------------------------------
        ORG 0x0010
rst10:  push af                         ; LD (HL),B
        ld a,b
        call h_plot
        pop af
        ret
        ds 0x0018 - $, 0
rst18:  jp h_plot                       ; LD (HL),A
        ds 0x0020 - $, 0
rst20:  push af                         ; LD (HL),0xFF
        ld a,0xFF
        call h_plot
        pop af
        ret
low_end:
        SAVEBIN "elite_low.bin", rst10, low_end - rst10

; ---------------------------------------------------------------------------------------------------------------
; Hooks (alt ROM 0x3000-0x3BFF; the game executes 0x22B0-0x22CA and reads 0x0127-0x0B26 and the font, never here)
; ---------------------------------------------------------------------------------------------------------------
        ORG 0x3000
rom_start:

; h_plot: (HL) = A, as the original LD (HL),A, and mirror the changed bits on the Layer 2 back buffer.
; Keeps every register and flag. Interrupts may be on. Stack: 10 bytes with the RST (4 pushes, no CALL) - the ship
; draw wrapper runs on a 32-byte stack at 0x4000-0x401F and reaches the writers with SP down to 0x400E (site_ctx probe):
; one byte more than 14 would push into the ROM and lose a return address (M1 first boot crashed that way).
h_plot: push af
        push bc
        ld c,a                          ; C = new byte
        ld a,(hl)
        ld (hl),c                       ; the original write
        xor c                           ; A = changed bits
        jr z,.out
        push de
        push hl
        ld e,a                          ; E = changed bits
        ld a,h                          ; the buffer is in screen layout at 0xC000: line k from HL as from a screen
        sub 0xC0                        ; address; the copy shows line k at screen y = k + 8 for k = 0-119 (it walks
        cp 0x10                         ; both pointers line by line, so there is no fixed address offset)
        jr nc,.skip                     ; not the buffer (the same writers also write game data above 0xCFE0)
        ld a,l                          ; k = (H & 7) | ((L >> 2) & 0x38) | ((H << 3) & 0xC0)
        rrca
        rrca
        and 0x38
        ld b,a
        ld a,h
        and 7
        or b
        ld b,a
        ld a,h
        rlca
        rlca
        rlca
        and 0xC0
        or b
        cp 120
        jr nc,.skip                     ; lines 120-127: never shown
        add a,8
        ld d,a                          ; D = y
        ld a,l
        and 31
        rlca
        rlca
        rlca
        ld l,a                          ; L = x of the byte's first pixel
        ld h,c                          ; H = new byte (C is needed for the ports)
        ld a,d
        and 0xC0
        or P_L2
        ld bc,0x123B
        out (c),a                       ; write-over: back buffer, third y >> 6
        ld bc,0x243B                    ; colour: NR $7F, or the ship's (IY blueprint) when it is 0
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        or a
        jr nz,.col
        ld b,high shipcol
        ld a,iyl
        ld c,a
        ld a,(bc)
.col:   ld b,a                          ; B = colour
        ld c,h                          ; C = new byte
        ld a,d
        and 63
        ld h,a                          ; HL = pixel address in the third
        ld d,8
.bit:   sla e                           ; carry = this pixel changed
        jr nc,.next
        bit 7,c
        ld (hl),b
        jr nz,.next
        ld (hl),TRANS
.next:  sla c
        inc l
        dec d
        jr nz,.bit
        ld bc,0x123B
        ld a,P_SHOW
        out (c),a                       ; write-over off
.skip:  pop hl
        pop de
.out:   pop bc
        pop af
        ret

; ---- category hooks ----
h_planet:
        nextreg 0x7F,C_PLANET
        jp 0x7584
h_stars:
        nextreg 0x7F,C_WHITE
        jp 0x7898
h_msg:  nextreg 0x7F,C_WHITE
        jp 0xD03C
h_combat:
        nextreg 0x7F,C_RED
        jp 0x9C80
h_ship: nextreg 0x7F,0
        jp 0xF8B4
h_shipend:
        nextreg 0x7F,C_RED
        jp 0x9E47

; h_clear (0x8080, replaces DI / LD BC,30): clear the back buffer's thirds 0 and 1 (rows 0-127) with the DMA,
; through slots 6 / 7 (bank 0 there again afterwards). Interrupts off from here on, as the original. No stack
; use while slots 6 / 7 are remapped (SP may be up there).
h_clear:
        di
        push af                         ; the original keeps A (callers rely on it); pushed before the remap
        nextreg 0x7F,C_WHITE
        ld bc,0x243B
        ld a,0x13
        out (c),a
        inc b
        in a,(c)                        ; A = back buffer's 16K bank
        add a,a                         ; its first 8K page
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        inc a
        ld hl,dma_fill
        ld bc,(dma_fill_len << 8) | 0x6B
        otir
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld hl,dma_fill
        ld bc,(dma_fill_len << 8) | 0x6B
        otir
        nextreg 0x56,0
        nextreg 0x57,1
        pop af
        ld bc,30
        jp 0x8084

; h_flip (0x7FBE, replaces LD HL,0xC000): show the buffer just drawn (swap NR $12 / NR $13).
h_flip: ld bc,0x243B
        ld a,0x12
        out (c),a
        inc b
        in a,(c)
        ld l,a                          ; L = front
        dec b
        ld a,0x13
        out (c),a
        inc b
        in a,(c)                        ; A = back
        nextreg 0x12,a
        ld a,l
        nextreg 0x13,a
        ld hl,0xC000
        jp 0x7FC1

; zxnDMA: fill 0xC000-0xFFFF with TRANS (port A fixed at trans_byte, port B incrementing, continuous)
dma_fill:
        db 0x83                         ; disable
        db 0x7D                         ; WR0: A -> B, port A address and length follow
        dw trans_byte
        dw 0x4000
        db 0x24                         ; WR1: port A memory, fixed
        db 0x10                         ; WR2: port B memory, increment
        db 0xAD                         ; WR4: continuous, port B address follows
        dw 0xC000
        db 0x82                         ; WR5: stop at end
        db 0xCF                         ; load
        db 0x87                         ; enable
dma_fill_len EQU $ - dma_fill
trans_byte:
        db TRANS

        ds 0x3900 - $, 0xFF
; IM 2 vector table: I = 0x39 (snapshot I and the game's LD A,0xFD at 0xFF4C changed by nexclash/elite.py), so the
; vector is 0xFEFE (the game's ISR entry) whatever byte the bus holds. The original table (I = 0xFD) has FE FE only
; at 0xFDFF / 0xFE00 and game code elsewhere: CSpect's IM 2 bus byte is not 0xFF, and the first interrupt jumped
; through 0xFD00 = 0xC903 into the buffer (plain conversion crashed in pass 2, 2026-11-23).
im2tab: ds 257, 0xFE
        ds 0x3B00 - $, 0xFF
; ship colour per blueprint (index = low byte of IY); other values white. RRRGGGBB, never TRANS. Blueprints are
; 23-byte records from 0x61E3 (0x61E3 + 23 n, n = 0-22; low bytes all distinct); IY = the record while a ship's lines
; are drawn. Model names not yet identified; the station seen in Docking is 0x63C6 (n = 21). Provisional colours,
; repaintable later (design detail 1).
shipcol:
        ds 256, C_SHIPDEF
BP      MACRO lo, col
        ORG shipcol + lo
        db col
        ENDM
        BP 0xE3, 0x1F           ; n 0   cyan
        BP 0xFA, 0xF4           ; n 1   orange-pink
        BP 0x11, 0xFC           ; n 2   yellow
        BP 0x28, 0x1C           ; n 3   green
        BP 0x3F, 0xE3 ^ 0x40    ; n 4   (0xA3) purple
        BP 0x56, 0x5F           ; n 5   sky blue
        BP 0x6D, 0xE7           ; n 6   magenta
        BP 0x84, 0xD8           ; n 7   olive-yellow
        BP 0x9B, 0x7C           ; n 8   lime
        BP 0xB2, 0xEC           ; n 9   salmon
        BP 0xC9, 0xF0           ; n 10  orange
        BP 0xE0, 0x9B           ; n 11  sea green
        BP 0xF7, 0xCF           ; n 12  pink
        BP 0x0E, 0x3B           ; n 13  teal
        BP 0x25, 0x9F           ; n 14  mint
        BP 0x3C, 0x6F           ; n 15  lavender
        BP 0x53, 0xFE           ; n 16  pale yellow
        BP 0x6A, 0x3F           ; n 17  aqua
        BP 0x81, 0xEA           ; n 18  rose
        BP 0x98, 0x93           ; n 19  steel
        BP 0xAF, 0xB7           ; n 20  lilac
        BP 0xC6, 0xDB           ; n 21  station: light grey-blue
        BP 0xDD, 0xF8           ; n 22  amber
        ORG shipcol + 256
rom_end:
        SAVEBIN "elite_rom.bin", rom_start, rom_end - rom_start

; ---------------------------------------------------------------------------------------------------------------
; Set-up (stub bank, CALLed by the stub at 0xD000 before the tail; 3.5 MHz, stub stack in slot 6): Layer 2 banks,
; both cleared to transparent through slot 7 (the stub's upper page, mapped back afterwards), Layer 2 shown.
; ---------------------------------------------------------------------------------------------------------------
        ORG 0xD000
setup:  nextreg 0x12,L2_A
        nextreg 0x13,L2_B
        nextreg 0x14,TRANS
        nextreg 0x7F,C_WHITE
        ld a,L2_A * 2
        ld e,12                         ; 6 x 2 pages
.pg:    nextreg 0x57,a
        ld hl,s_dma
        ld bc,(s_dma_len << 8) | 0x6B
        otir
        inc a
        dec e
        jr nz,.pg
        nextreg 0x57,21                 ; z80tonex.STUB_PAGE_HI
        ld bc,0x123B
        ld a,P_SHOW
        out (c),a
        ret
s_dma:  db 0x83, 0x7D
        dw s_trans
        dw 0x2000
        db 0x24, 0x10, 0xAD
        dw 0xE000
        db 0x82, 0xCF, 0x87
s_dma_len EQU $ - s_dma
s_trans:
        db TRANS
setup_end:
        SAVEBIN "elite_setup.bin", setup, setup_end - setup
