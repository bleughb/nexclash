; NZS colour build: setup, CALLed once by the z80tonex start-up stub (stub bank at 0xC000-0xDFFF).
; 1. alt ROM image 1 = ROM3 with the hooks at 0x2000-0x3FFF (z80tonex.altrom_fill);
; 2. alt ROM on for reads; 3. sprite palette, transparency, clip; tilemap off until the first copy;
; 4. stage 1's own setup: NEXTREG $57,1 (bank 0's upper page at 0xE000 for its tail copy).
    DEVICE NOSLOT64K
    OPT --zxnext
    IFNDEF BACKDROP
BACKDROP = 0                    ; the "Backdrops" toggle (v1.2): the build with it on has 1
    ENDIF
    ORG 0xD000
setup:
    INCBIN "altfill.bin"
    nextreg 0x8C,0x80           ; alt ROM on for reads
    nextreg 0x43,0x20           ; the first sprite palette, auto-increment
    nextreg 0x40,0
    ld hl,spal
    ld b,0
.l  ld a,(hl)
    inc hl
    nextreg 0x44,a
    ld a,(hl)
    inc hl
    nextreg 0x44,a
    djnz .l
    nextreg 0x43,0x00
    nextreg 0x4B,0x00           ; sprite pixel 0 transparent
    nextreg 0x1C,0x02           ; sprite clip index reset
    nextreg 0x19,0
    nextreg 0x19,255
    nextreg 0x19,0
    nextreg 0x19,143            ; the 256x144 play area
    nextreg 0x4C,0              ; tile pixel 0 transparent
    nextreg 0x6C,0
    nextreg 0x6B,0
    nextreg 0x4A,0x00
    ; every sprite hidden
    ld bc,0x303B
    xor a
    out (c),a
    ld b,128
.h  out (0x57),a
    out (0x57),a
    out (0x57),a
    out (0x57),a
    djnz .h
    IF BACKDROP
bdfill:                         ; alt ROM image 1 0x34C0-0x3FFF = page 82 0x14C0-0x1FFF (backdrop.asm)
    INCBIN "bdfill.bin"
    nextreg 0x12,42             ; Layer 2 at 16K bank 42 (pages 84-93), 320x256, hidden until a backdrop is drawn
    nextreg 0x70,0x10
    ENDIF
    nextreg 0x57,1              ; stage 1's setup (its tail goes into bank 0 at 0xFFxx)
    ret
spal:
    INCBIN "spal.bin"
    SAVEBIN "OUT.bin", 0xD000, $-0xD000
