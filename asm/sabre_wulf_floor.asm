; Sabre Wulf, the "Jungle floor" toggle (display only, with the Enhanced colours): a dim floor on Layer 2 under the
; ULA. Jungle floor art: Jon Attree (assets/sabre_wulf/jungle.png, cave.png; the .rle files below are their rows).
; Profile: docs/profiles/sabre_wulf_floor.json; sabre_wulf.jungle_floor(nex) adds it to any built .nex of the engine
; (default, QAOP + Space, and their Enhanced sets), the same bytes in all four.
; The toggle's bytes: this block in the state page (page 22, slot 7 inside a hook, at 0xF200: the state tables end at
; 0xF10B) and the operand of e_clr's CALL leave (0x3908), which now calls `floor`, which ends with JP leave.
; So the floor runs at the end of every clear (47964), at 28 MHz, before leave puts the slots, R and the caller's
; clock back: R at the meeting point is leave's (VR + D_CLR), whatever runs before it.
; Registers: e_clr pushed AF, BC, DE, HL; leave pops HL and DE; C (D_CLR) is kept here. IX, IY, I, the alternate set
; and the interrupts are untouched. The floor writes no game memory: only NEXTREGs, port 0x123B, Layer 2's banks
; (through slot 6, which leave sets back to page 0) and its own bytes in the state page.
;
; Which clear: the game's return address (the caller + 3) says what comes next.
;   room shown: 45399 (a flip, 45396), 45543 (a game starts, 45540), 45582 (the players swap, 45579),
;               41550 (back to the room after the amulet display, 41547)  -> floor for room (38659)
;   anything else (title 46045, game over 43634, ending 40813, amulet display 41482)  -> Layer 2 hidden
; The room the game draws next is in 38659 at the clear (793 of 793 clears in the recordings).
; Cave: the room's own item list (type 24678 + room, list at word 24934 + 2 type: graphic, position, 0 ends), as the
; game draws it (48093), holds the cave rock 0x847C: rooms 135-137 and 151-153, the six of the cave.
; Picture: banks 18-20 hold the jungle floor, 21-23 the cave's, each the 128 x 96 tile 2 x 2, drawn once at the
; first clear of all (DRAWN): the title's, with Layer 2 hidden, so no room waits for it. A room's arrangement is Layer
; 2's scroll: X = 16 (room & 7), Y = DY(room >> 3) = 16 ((room >> 3) mod 6), so the tile's period (128, 96) leaves no
; seam; neighbours differ (X by 16, Y by 32).
; Show: Layer 2 under the ULA (NR 0x15 = 0x09: sprites, ULA, Layer 2), the ULA's black (ink and paper, bright or
; not: ULA palette 0, 8, 16, 24) the global transparent colour 0xE3, the fallback colour black, Layer 2 clipped to
; lines 16-191 (the panel's lines show black, as they did).

        DEVICE ZXSPECTRUMNEXT

LEAVE   EQU 0x395B
ROOM    EQU 38659
RTYPE   EQU 24678
RLIST   EQU 24934
ROCK    EQU 0x847C
JBANK   EQU 18
CBANK   EQU 21
DRAWN   EQU 0xF17F              ; 0 until the pictures are drawn (zero in the .nex: past the tables, before the code)
ROWBUF  EQU 0xF180              ; one decoded row, 128 bytes

        ORG 0xF200
floor:  push bc                 ; C = D_CLR for leave
        ld a,(DRAWN)            ; the first clear of all (the title's, at start): draw the pictures, set the palettes
        or a
        call z,init
        ld hl,12                ; [BC][ret to e_clr][HL][DE][BC][AF][game return]
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = the game's return address
        ld de,shown
        ld b,4
.c:     ld a,(de)
        inc de
        cp l
        ld a,(de)
        inc de
        jr nz,.n
        cp h
        jr z,.play
.n:     djnz .c
        ld bc,0x123B            ; not a room: Layer 2 off
        xor a
        out (c),a
        jr .out

.play:  ld a,(ROOM)             ; the room's type, then its list
        ld l,a
        ld h,0
        ld de,RTYPE
        add hl,de
        ld l,(hl)
        ld h,0
        add hl,hl
        ld de,RLIST
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld b,JBANK
.it:    ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        inc hl
        inc hl
        ld a,d
        or e
        jr z,.bk
        ld a,e
        cp low ROCK
        jr nz,.it
        ld a,d
        cp high ROCK
        jr nz,.it
        ld b,CBANK
.bk:    ld a,b
        nextreg 0x12,a
        ld a,(ROOM)
        and 7
        rlca
        rlca
        rlca
        rlca
        nextreg 0x16,a
        ld a,(ROOM)
        rrca
        rrca
        rrca
        and 31
        add a,low dy
        ld l,a
        ld a,0
        adc a,high dy
        ld h,a
        ld a,(hl)
        nextreg 0x17,a
        nextreg 0x15,0x09       ; sprites on, order sprites / ULA / Layer 2
        nextreg 0x1C,1          ; Layer 2 clip: x 0-255, lines 16-191
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,16
        nextreg 0x18,191
        ld bc,0x123B
        ld a,2                  ; Layer 2 shown
        out (c),a
.out:   pop bc
        jp LEAVE

; init: both pictures into Layer 2's banks, the palettes, the transparency. Once.
init:   ld hl,jungle
        ld a,JBANK*2
        call pic
        ld hl,cave
        ld a,CBANK*2
        call pic
        nextreg 0x43,0x10       ; Layer 2 palette 0, auto-increment: entries 0-5, 9-bit
        nextreg 0x40,0
        ld hl,l2pal
        ld b,12
.p:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .p
        nextreg 0x43,0x00       ; ULA palette 0: black ink and paper, bright or not, transparent
        ld a,0
        call clear
        ld a,8
        call clear
        ld a,16
        call clear
        ld a,24
        call clear
        nextreg 0x43,0x20       ; as the setup leaves it (sprite palette 0)
        nextreg 0x14,0xE3       ; the global transparent colour
        nextreg 0x4A,0x00       ; nothing anywhere: black
        ld a,1
        ld (DRAWN),a
        ret
clear:  nextreg 0x40,a
        nextreg 0x41,0xE3
        ret

; pic: HL = the tile's rows (RLE), A = Layer 2's first 8K page. Rows r and r + 96 each get the row twice (x 0, 128).
pic:    ld (PG),a
        xor a
        ld (ROWN),a
.row:   ld de,ROWBUF            ; decode one row: b < 0x80: b + 1 zeros, else (b & 0x7F) + 1 pixels
.d:     ld a,(hl)
        inc hl
        bit 7,a
        jr nz,.lit
        inc a
        ld b,a
        xor a
.z:     ld (de),a
        inc e
        djnz .z
        jr .e
.lit:   and 0x7F
        inc a
        ld c,a
        ld b,0
        ldir
.e:     ld a,e
        cp low (ROWBUF+128)     ; ROWBUF + 128 = 0xF200: E wraps to 0x00
        jr nz,.d
        push hl
        ld a,(ROWN)
        call put
        ld a,(ROWN)
        add a,96
        call put
        pop hl
        ld a,(ROWN)
        inc a
        ld (ROWN),a
        cp 96
        jr nz,.row
        ret
put:    ld c,a                  ; line A: page PG + A / 32, offset 256 (A & 31)
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,(PG)
        add a,b
        nextreg 0x56,a
        ld a,c
        and 31
        add a,0xC0
        ld d,a
        ld e,0
        ld hl,ROWBUF
        ld bc,128
        ldir
        ld hl,ROWBUF
        ld bc,128
        ldir
        ret

shown:  DW 45399,45543,45582,41550
dy:     DB 0,16,32,48,64,80,0,16,32,48,64,80,0,16,32,48,64,80,0,16,32,48,64,80,0,16,32,48,64,80,0,16
l2pal:  DB 0x00,0, 0x28,0, 0x48,0, 0x44,0, 0x24,1, 0x48,1   ; RRRGGGBB then blue's low bit: black, green, olive, brown, stone, stone light
PG:     DB 0
ROWN:   DB 0
jungle: INCBIN "../assets/sabre_wulf/jungle.rle"
cave:   INCBIN "../assets/sabre_wulf/cave.rle"
floor_end:
        ASSERT floor_end <= 0x10000
        SAVEBIN "swf_floor.bin",0xF200,floor_end-0xF200
