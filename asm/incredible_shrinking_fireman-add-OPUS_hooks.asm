; The Incredible Shrinking Fireman (Mastertronic, 1986, 48K) - hardware sprites over the figures.
; games/incredible_shrinking_fireman-add-OPUS.md "Build". Overlay, not removal: the game's plotter
; (0xB950, XOR old ^ new) and the collectable drawing (0xECFF) still write the ULA exactly as the
; original; every figure / collectable gets sprites exactly on its pixels, in front. The figure
; attribute painting is removed (0xBCDF LD (IX+0),A -> NOP x3, no hook).
; The XOR plot takes ~1/3 of a frame while the picture is drawn (hardware 2026-10-25: the half-done
; plot showed in the cells' own colours): the ENTRY hook shows the new image on a second (pending)
; sprite pair before the plot starts; the EXIT hook switches the figure's own pair to it and hides
; the pending pair. Every pixel the half-done plot changes is under a sprite all the time.
;
; Patch sites (original bytes checked by the engine):
;   0xB950  DD E5 87   PUSH IX / ADD A,A (plotter entry, A = object)   -> JP e_ent
;   0xBC5C  DD E1 C9   POP IX / RET (plotter exit, HL = OBJ + 8a + 2)  -> JP e_plot
;   0xECFF  11 14 ED   LD DE,0xED14 (one collectable: B = bottom line, C = pixel x) -> JP e_item
;   0xC4A7  21 00 40   LD HL,0x4000 (screen clear)                     -> JP e_c1
;   0xC5B1  21 00 48   LD HL,0x4800 (clear of lines 64-191)            -> JP e_c2
;   0xB4AD  21 00 40   LD HL,0x4000 (screen clear)                     -> JP e_c3
; Code: alt ROM image 1, two blocks: 0x3A01- (+ the start-up register block, below 0x3D00) and
; 0x386E-0x39FE (0x39FF-0x3A00 stay FF FF: the game's IM 2 vector is read there); and page 30 at
; 0xD600-0xDDFF: code that only runs while page 30 is at slot 6. Hooks run with interrupts OFF (IFF
; saved with LD A,I twice, restored) at 28 MHz; Next pages 26-30 (colour map; tables, variables
; and that code in page 30) are mapped at slot 6 (0xC000) only inside a hook, MMU6 back to page 0
; (bank 0, 48K); no hook reads game data in 0xC000-0xDFFF (as Cyclone).
; Sprites (higher number on top): collectables 0-4 (4-bit patterns: slot k / 2, half k & 1); object
; a (2 = enemy 2, 1 = enemy 1, 0 = fireman) at SPR = 13 - 4a: SPR / SPR+1 its own pair (lines 0-15
; / 16-23), SPR+2 / SPR+3 the pending pair. Patterns: one 256-byte slot per image (N6 = 0 / 1),
; double-buffered: slot 5 - a (buffer 0) / 8 - a (buffer 1).

        DEVICE ZXSPECTRUMNEXT

OBJ     EQU 0xBCF7              ; object table: x, y, frame, -, dx, dy, attribute, keep-mask
NEWF    EQU 0xBCF6              ; the frame the plot shows
GBASE   EQU 0xBD42              ; graphics base (word)
GFX0    EQU 0x9C40              ; colour-map index 0 = this address
ITEMG   EQU 0xED14              ; collectable graphic, 7 bytes (byte j drawn on line B - j)
IDX_IT  EQU 4144                ; colour-map index of ITEMG
CPAGE   EQU 26                  ; colour map: page 26 + i / 1024, offset (i % 1024) * 8
; page CPAGE + 4 (30) at slot 6: colour-map entries 4096-4150 at 0xC000-0xC1B7 (4096-5119 would
; reach 0xDFFF; the rest is free), tables 0xC200-0xC7FF, code 0xD600-0xDDFF, variables 0xDE00-
NIB16   EQU 0xDE00              ; 16 bytes: pixel-pair code -> pattern byte (mktab's scratch)
TINK    EQU 0xDE20              ; per object a: the ink its tables hold (0 = none: inks are 1-15)
TABS    EQU 0xC200              ; object a: 0xC200 + 0x200 a (high pair), + 0x100 (low pair)
FLAGS   EQU 0xDF00              ; bits 0-2 object a shown, 3-5 the buffer its own pair shows
PEND    EQU 0xDF01              ; bits 0-2 the pending pair is up, 3-5 the buffer it shows
PX      EQU 0xDF02              ; x, y (PX + 1) of the image being placed
VA      EQU 0xDF04              ; object a
VBIT    EQU 0xDF05              ; 1 << a
VFR     EQU 0xDF06              ; frame
VINK    EQU 0xDF07              ; live ink
VSEL    EQU 0xDF08              ; buffer chosen by prep (0 / 1)
VS      EQU 0xDF09              ; upload: the slot base
SXL     EQU 0xDF0A              ; place: X, X8 of the left column; SXR (0xDF0C) the right; SYT, SYB
SXR     EQU 0xDF0C
SYT     EQU 0xDF0E
SYB     EQU 0xDF0F
CACHE   EQU 0xDF10              ; per object a: (frame, ink) of buffer 0, of buffer 1 (4a + 0..3)
FPAGE   EQU 32                  ; figure shapes: frame f at page FPAGE + f / 8, offset (f % 8) * 1024,
                                ; mapped at slot 7 (0xE000) during an upload only (pages 32-63)

        ORG 0x3A01
; ---- plotter entry: A = object ---------------------------------------------------------------
e_ent:  push af
        ld a,i
        jp pe,.on
        ld a,i                  ; NMOS quirk: read twice
.on:    di
        push af                 ; P/V = IFF at entry
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,9                 ; HL, DE, BC, AF(IFF) pushed; + 9 = A of the first push
        add hl,sp
        ld a,(hl)
        cp 3
        jr nc,.x
        nextreg 0x56,CPAGE+4
        call n_obj
        nextreg 0x56,0
.x:     nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp po,.off
        pop af
        ei
        push ix                 ; the replaced instructions
        add a,a
        jp 0xB953
.off:   pop af
        push ix
        add a,a
        jp 0xB953

; ---- plotter exit -------------------------------------------------------------------------
e_plot: pop ix                  ; the replaced instruction
        push af
        ld a,i
        jp pe,.on
        ld a,i                  ; NMOS quirk: read twice
.on:    di
        push af                 ; P/V = IFF at entry
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld a,l
        sub low (OBJ+2)
        rrca
        rrca
        rrca
        and 0x1F
        cp 3
        jr nc,.x
        nextreg 0x56,CPAGE+4
        call x_obj
        nextreg 0x56,0
.x:     nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp po,.off
        pop af
        ei
        ret
.off:   pop af
        ret

; ---- one collectable: stack +0 return 0xECF3, +2 HL, +4 BC (B = loop counter 5..1) ----------
e_item: push af
        ld a,i
        jp pe,.on
        ld a,i
.on:    di
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,15                ; AF x2, BC, DE, HL pushed + 5 = the loop counter B
        add hl,sp
        ld a,5
        sub (hl)
        cp 5
        call c,item             ; A = k (0-4), B = bottom line, C = pixel x
        nextreg 0x56,0
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp po,.off
        pop af
        ld de,ITEMG
        ei
        jp 0xED02
.off:   pop af
        ld de,ITEMG
        jp 0xED02

; ---- screen clears: hide every sprite, forget what is shown -------------------------------
; HL is dead at the three sites (each loads it). One push (AF) before the DI; out through JP (HL)
; to a per-site tail that does the replaced LD HL,nn: no stack in use while interrupts are on.
e_c1:   ld hl,t_c1
        jr hide
e_c2:   ld hl,t_c2
        jr hide
e_c3:   ld hl,t_c3
hide:   push af
        ld a,i
        jp pe,.on
        ld a,i                  ; NMOS quirk: read twice
.on:    di
        push af                 ; P/V = IFF at entry
        push bc
        ld b,29
.h:     ld a,b
        dec a
        nextreg 0x34,a
        nextreg 0x38,0x40       ; sprites 0-28 invisible
        djnz .h
        nextreg 0x56,CPAGE+4
        xor a
        ld (FLAGS),a
        ld (PEND),a
        nextreg 0x56,0
        pop bc
        pop af
        jp po,.off
        pop af
        ei
        jp (hl)
.off:   pop af
        jp (hl)
t_c1:   ld hl,0x4000
        jp 0xC4AA
t_c2:   ld hl,0x4800
        jp 0xC5B4
t_c3:   ld hl,0x4000
        jp 0xB4B0

rom_end:

; ---- second block: 0x386E-0x39FE (free in the 48K ROM, below the IM 2 vector bytes) ----------
        ORG 0x386E
; A = k (0-4), B = bottom line, C = pixel x (column C / 8, as 0xED1B): pattern first, then
; position and visible
item:   ld e,a
        push bc
        ld a,b
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl               ; line / 8 * 32
        ld a,c
        rrca
        rrca
        rrca
        and 0x1F
        ld c,a
        ld b,0
        add hl,bc               ; + column
        ld bc,0x5800
        add hl,bc
        ld d,(hl)               ; the cell's attribute
        ld a,d
        and 7
        jr nz,.i1
        ld a,8
        jr .i2
.i1:    bit 6,d
        jr z,.i2
        add a,8
.i2:    ld c,a                  ; C = ink
        ld a,e
        rrca                    ; bit 7 = k & 1 (+128 bytes), bits 6-0 = slot k / 2
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        push de
        ld hl,ITEMG+6           ; sprite line 0 = top line B - 6 = byte 6
        ld de,IDX_IT+6
        ld b,7
.lp:    ld a,(hl)
        call emit
        xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        dec hl
        dec de
        djnz .lp
        xor a
        ld b,72                 ; lines 7-15
.z:     out (0x5B),a
        djnz .z
        pop de                  ; E = k
        pop bc                  ; B = bottom line, C = column
        ld a,e
        nextreg 0x34,a
        ld a,c
        and 0xF8
        add a,32
        nextreg 0x35,a
        ld a,0
        rla
        nextreg 0x37,a
        ld a,b
        add a,26                ; top line B - 6, + 32
        nextreg 0x36,a
        ld a,e
        and 1
        rrca
        rrca
        or 0x80                 ; 4-bit, N6 = k & 1
        nextreg 0x39,a
        ld a,e
        srl a
        or 0xC0                 ; visible, attribute 4 on, slot k / 2
        nextreg 0x38,a
        ret


emit:   push hl
        push de
        push bc
        ld b,a
        ld hl,ZERO4
        ld a,d
        cp 0x14                 ; index >= 5120: outside pages 26-30, defaults
        jr nc,.go
        srl a
        srl a
        add a,CPAGE
        nextreg 0x56,a
        ld a,d
        and 3
        ld h,a
        ld l,e
        add hl,hl
        add hl,hl
        add hl,hl               ; (i % 1024) * 8: 4 nibble bytes, check byte at +4
        ld a,h
        or 0xC0
        ld h,a                  ; the page is at slot 6 (0xC000)
        push hl
        ld de,4
        add hl,de
        ld a,(hl)
        pop hl
        cp b
        jr z,.go
        ld hl,ZERO4
.go:    ld d,(hl)               ; painted pair (left, right)
        inc hl
        ld e,0
        sla b
        jr nc,.r                ; left pixel paper: transparent
        ld a,d
        and 0xF0
        jr nz,.l1
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
.l1:    ld e,a
.r:     sla b
        jr nc,.o
        ld a,d
        and 0x0F
        jr nz,.r1
        ld a,c
.r1:    or e
        ld e,a
.o:     ld a,e
        out (0x5B),a
        ld a,l
        and 3                   ; 4 bytes done (map entries and ZERO4 are 4-aligned)
        jr nz,.go
        pop bc
        pop de
        pop hl
        ret
        ALIGN 4
ZERO4:  defb 0,0,0,0
rom2_end:
        ASSERT rom2_end <= 0x39FF
        ASSERT rom_end <= 0x3CEC                ; + 20-byte register block, below 0x3D00

; ---- page 30 at slot 6, 0xD600-0xDDFF: code that only runs while page CPAGE+4 is mapped -------
        ORG 0xD600
; entry, A = object a: its new image -> a buffer; the pending sprites show it at (x + dx, y + dy)
n_obj:  call setv               ; VA, VBIT; HL = object
        ld a,(VBIT)
        cpl
        ld b,a
        ld a,(PEND)
        and b
        ld (PEND),a             ; pending a down (until set below)
        ld a,(NEWF)
        ld (VFR),a
        or a
        jp z,hidep              ; new frame 0: the figure disappears, nothing new to show
        ld a,(hl)
        ld de,4
        add hl,de
        add a,(hl)              ; x + dx, 8 bits (as 0xB97D)
        ld (PX),a
        ld hl,(VA)              ; L = a
        call objhl
        inc hl
        ld a,(hl)
        ld de,4
        add hl,de
        add a,(hl)              ; y + dy (as 0xB982)
        ld (PX+1),a
        ld hl,(VA)
        call objhl              ; HL = object
        call prep               ; A = slot base, VSEL
        push af
        ld a,(VBIT)
        ld b,a
        ld a,(PEND)
        or b                    ; pending a up
        call setbuf             ; PEND buffer bit a := VSEL
        ld (PEND),a
        pop af
        or 0xC0                 ; visible, attribute 4 on
        ld c,a
        ld a,(VA)
        call sprnum
        add a,4
        ld d,a
        jp place                ; the pending sprites

; exit, A = object a: its own sprites take the image (the pending one, or built now), pending hidden
x_obj:  call setv               ; VA, VBIT; HL = object
        inc hl
        inc hl
        ld a,(hl)               ; frame
        dec hl
        dec hl
        ld (VFR),a
        ld a,(VBIT)
        ld b,a
        ld a,(FLAGS)
        or b
        ld c,a
        ld a,(VFR)
        or a
        ld a,c
        jr nz,.st
        xor b                   ; frame 0: not shown
.st:    ld (FLAGS),a
        ld a,(VFR)
        or a
        jr z,.hid
        ld a,(PEND)
        and b
        jr z,.now
        ld a,b                  ; the pending image: VSEL = PEND buffer bit a
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(PEND)
        and c
        jr z,.p0
        ld a,1
.p0:    ld (VSEL),a
        jr .take
.now:   call prep               ; no entry hook ran for it: build the image now
.take:  ld a,(hl)
        ld (PX),a
        inc hl
        ld a,(hl)
        ld (PX+1),a
        ld a,(FLAGS)
        call setbuf             ; FLAGS buffer bit a := VSEL
        ld (FLAGS),a
        call slotv              ; A = slot base of VSEL
        or 0x40                 ; attribute 3 without the visible bit: vis_all sets it
        ld c,a
        ld a,(VA)
        call sprnum
        ld d,a
        call place
.hid:   ld a,(VBIT)
        cpl
        ld b,a
        ld a,(PEND)
        and b
        ld (PEND),a             ; pending a down
        call hidep
        jp vis_all

; A = object -> VA, VBIT; HL = object
setv:   ld (VA),a
        ld l,a
objhl:  ld a,l
        ld b,1
        or a
        jr z,.b
.m:     sla b
        dec a
        jr nz,.m
.b:     ld a,b
        ld (VBIT),a
        ld a,l
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,OBJ
        add hl,de
        ret

; A = flags byte -> A with its buffer bit a (8 << a) = VSEL
setbuf: ld c,a
        ld a,(VBIT)
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,c
        or b
        xor b                   ; bit clear
        ld c,a
        ld a,(VSEL)
        or a
        ld a,c
        ret z
        or b
        ret

; -> A = slot base of buffer VSEL for object VA: 11 - 4a + 2 VSEL (two 256-byte slots per image)
slotv:  ld a,(VA)
        add a,a
        add a,a
        cpl
        add a,12                ; 11 - 4a
        ld b,a
        ld a,(VSEL)
        add a,a
        add a,b
        ret

; A = a -> 21 - 8a (its own 4 sprites; the pending 4 follow)
sprnum: add a,a
        add a,a
        add a,a
        cpl
        add a,22
        ret

; hide the pending sprites of VA
hidep:  ld a,(VA)
        call sprnum
        add a,4
        ld b,4
.h:     nextreg 0x34,a
        nextreg 0x38,0x40
        inc a
        djnz .h
        ret

; D = first sprite, C = attribute 3 (slot base S): an 18 x 26 image (mask included) at (PX - 1,
; PY - 1) as 4 sprites: D (S, bytes 0-127), D+1 (S, 128-255) 16 px right, D+2 (S+1, 0-127) 16 px
; down, D+3 (S+1, 128-255)
place:  ld a,(PX)
        add a,31                ; x - 1 + 32
        ld (SXL),a
        ld a,0
        rla
        ld (SXL+1),a            ; X8
        ld a,(PX)
        add a,47                ; x + 15 + 32
        ld (SXR),a
        ld a,0
        rla
        ld (SXR+1),a
        ld a,(PX+1)
        add a,31                ; y - 1 + 32
        ld (SYT),a
        add a,16
        ld (SYB),a
        ld hl,SXL
        ld a,(SYT)
        ld e,0x80
        call .w                 ; D: left, top
        inc d
        ld hl,SXR
        ld a,(SYT)
        ld e,0xC0
        call .w                 ; D+1: right, top
        inc d
        inc c                   ; slot S + 1
        ld hl,SXL
        ld a,(SYB)
        ld e,0x80
        call .w                 ; D+2: left, bottom
        inc d
        ld hl,SXR
        ld a,(SYB)
        ld e,0xC0               ; D+3: right, bottom
; A = Y, HL -> X, X8; D = sprite; E = attribute 4 (4-bit, N6); C = attribute 3
.w:     push af
        ld a,d
        nextreg 0x34,a
        ld a,(hl)
        nextreg 0x35,a
        inc hl
        ld a,(hl)
        nextreg 0x37,a          ; X8, palette offset 0
        pop af
        nextreg 0x36,a
        ld a,e
        nextreg 0x39,a
        ld a,c
        nextreg 0x38,a
        ret

; HL = object; VA, VBIT, VFR (non-zero): the image (frame, live ink) into a buffer - the one the
; figure's own sprites show, the other one, or uploaded into the other one -> VSEL, A = slot base.
; Keeps HL.
prep:   push hl
        ld de,6
        add hl,de
        ld a,(hl)               ; attribute E
        inc hl
        ld b,(hl)               ; keep-mask D
        ld c,a
        and 7
        jr nz,.ink
        ld a,8                  ; ink 0: black
        jr .ik
.ink:   ld e,a
        ld a,c
        or b
        and 0x40
        ld a,e
        jr z,.ik
        add a,8                 ; bright (from E, or kept from the BRIGHT room cells)
.ik:    ld (VINK),a
        ld c,a                  ; C = ink
        ld a,(VFR)
        ld d,a                  ; D = frame
        ld a,(VBIT)
        add a,a
        add a,a
        add a,a
        ld b,a                  ; B = buffer bit (8 << a)
        ld a,(FLAGS)
        and b
        jr z,.s0
        ld a,1
.s0:    ld e,a                  ; E = the buffer its own sprites show
        call centry             ; HL = cache entry of buffer E
        ld a,(hl)
        cp d
        jr nz,.c1
        inc l
        ld a,(hl)
        cp c
        jr z,.hit
.c1:    ld a,e
        xor 1
        ld e,a                  ; the other buffer
        call centry
        ld a,(hl)
        cp d
        jr nz,.up
        inc l
        ld a,(hl)
        cp c
        jr z,.hit
        dec l
.up:    ld (hl),d               ; new key: frame, ink
        inc l
        ld (hl),c
        ld a,e
        ld (VSEL),a
        call slotv
        call upload
        pop hl
        jp slotv
.hit:   ld a,e
        ld (VSEL),a
        pop hl
        jp slotv

; E = buffer (0 / 1) -> HL = CACHE + 4a + 2E
centry: ld a,(VA)
        add a,a
        add a,a
        add a,e
        add a,e
        add a,low CACHE
        ld l,a
        ld h,high CACHE
        ret

; A = slot base S; VA, VFR, VINK: the frame's precomputed shape (page FPAGE + f / 8, offset (f % 8)
; * 1024, mapped at slot 7) -> pattern RAM. Block: +0 codes of the top-left 16 x 16 (64 bytes, 4 per
; row: two pixel-pair codes each - ink L 8, ink R 4, mask L 2, mask R 1), +64 the first code byte of
; each top-right row (16; columns 18-31 are always empty), +80 bottom-left rows 16-25 (40), +120 the
; first code byte of each bottom-right row (10), +256 one painted-override byte per pattern byte in
; upload order (416), +1023 the painted flag. Object a's tables at 0xC200 + 0x200 a (code byte ->
; pattern byte of its high pair, + 0x100 of its low pair) for ink TINK[a].
upload: ld (VS),a
        ld bc,0x303B
        out (c),a               ; slot S from its start
        ld a,(VA)
        add a,low TINK
        ld l,a
        ld h,high TINK
        ld a,(VINK)
        cp (hl)
        call nz,mktab           ; this object's tables for VINK
        ld a,(VA)
        add a,a
        add a,high TABS
        ld d,a                  ; D = the object's high-pair table page
        ld a,(VFR)
        ld b,a
        rrca
        rrca
        rrca
        and 0x1F
        add a,FPAGE
        nextreg 0x57,a          ; the frame's data page at slot 7
        ld a,b
        and 7
        add a,a
        add a,a
        or 0xE0
        ld h,a
        ld l,0                  ; HL = the frame's block
        or 3
        ld b,a
        ld c,0xFF
        ld a,(bc)               ; painted flag (+1023)
        or a
        jr nz,.pt
        ld b,64
        call fa                 ; top-left
        ld b,16
        call fb                 ; top-right
        ld b,40
        call fa                 ; bottom-left, rows 16-25
        ld a,(VS)
        inc a
        or 0x80
        ld bc,0x303B
        out (c),a               ; slot S + 1, bytes 128-
        ld b,10
        call fb                 ; bottom-right, rows 16-25
        nextreg 0x57,1          ; bank 0's upper page back
        ret
.pt:    push ix
        push hl
        pop ix
        inc ixh                 ; IX = the overrides (+256)
        ld b,64
        call pa
        ld b,16
        call pb
        ld b,40
        call pa
        ld a,(VS)
        inc a
        or 0x80
        ld bc,0x303B
        out (c),a
        ld b,10
        call pb
        pop ix
        nextreg 0x57,1
        ret
; B code bytes -> 2 pattern bytes each
fa:     ld e,(hl)
        inc hl
        ld a,(de)
        out (0x5B),a
        inc d
        ld a,(de)
        out (0x5B),a
        dec d
        djnz fa
        ret
; B rows: 1 code byte -> 2 pattern bytes, then 6 empty ones
fb:     ld e,(hl)
        inc hl
        ld a,(de)
        out (0x5B),a
        inc d
        ld a,(de)
        out (0x5B),a
        dec d
        xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        djnz fb
        ret
; painted frames: the same, each pattern byte through pout (IX = its override)
pa:     ld e,(hl)
        inc hl
        ld a,(de)
        call pout
        inc d
        ld a,(de)
        call pout
        dec d
        djnz pa
        ret
pb:     ld e,(hl)
        inc hl
        ld a,(de)
        call pout
        inc d
        ld a,(de)
        call pout
        dec d
        xor a
        call pout
        xor a
        call pout
        xor a
        call pout
        xor a
        call pout
        xor a
        call pout
        xor a
        call pout
        djnz pb
        ret
; A = pattern byte; (IX) = its override (non-zero nibbles replace) -> out; keeps BC, DE, HL
pout:   ld c,a
        ld a,(ix+0)
        inc ix
        or a
        jr nz,.cb
        ld a,c
        out (0x5B),a
        ret
.cb:    push de
        ld e,a
        and 0xF0
        jr nz,.h
        ld a,c
        and 0xF0
.h:     ld d,a
        ld a,e
        and 0x0F
        jr nz,.l
        ld a,c
        and 0x0F
.l:     or d
        pop de
        out (0x5B),a
        ret

; VA, VINK: the object's tables: code byte d -> pattern byte of pair d >> 4 (table) and of pair
; d & 15 (table + 0x100); a pair: ink -> VINK, mask -> 8 (black), else 0 (transparent)
mktab:  ld a,(VINK)
        ld (hl),a               ; TINK[a]
        ld c,a
        ld hl,NIB16
        ld b,0
.n:     ld a,b                  ; NIB16[n], n = ink L 8, ink R 4, mask L 2, mask R 1
        and 8
        ld a,c
        jr nz,.l1
        ld a,b
        and 2
        ld a,8
        jr nz,.l1
        xor a
.l1:    add a,a
        add a,a
        add a,a
        add a,a
        ld e,a                  ; left nibble
        ld a,b
        and 4
        ld a,c
        jr nz,.r1
        ld a,b
        and 1
        ld a,8
        jr nz,.r1
        xor a
.r1:    or e
        ld (hl),a
        inc l
        inc b
        ld a,b
        cp 16
        jr nz,.n
        ld a,(VA)
        add a,a
        add a,high TABS
        ld d,a
        ld e,0                  ; DE = the high-pair table
.t:     ld a,e
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld l,a
        ld h,high NIB16
        ld a,(hl)
        ld (de),a
        inc d
        ld a,e
        and 0x0F
        ld l,a
        ld a,(hl)
        ld (de),a               ; low-pair table
        dec d
        inc e
        jr nz,.t
        ret

; visibility of the three objects' own sprites (objects 1 and 2 on one spot with one frame: both
; hidden, as their XORs cancel)
vis_all:
        ld a,(FLAGS)
        ld c,a
        and 6
        cp 6
        jr nz,.np
        ld hl,OBJ+8
        ld de,OBJ+16
        ld b,3
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.np
        inc hl
        inc de
        djnz .cmp
        ld a,c
        and 0xF9                ; the pair cancels: both hidden (buffers kept)
        ld c,a
.np:    xor a
.v:     ld (VA),a
        call sprnum
        ld e,a                  ; E = its first sprite
        ld a,(VA)
        ld b,a
        ld a,c                  ; flags shifted: bit 0 shown, bit 3 buffer of this object
        and 8
        jr z,.b0
        ld a,1
.b0:    ld (VSEL),a
        push bc
        call slotv
        pop bc
        or 0x40
        bit 0,c
        jr z,.h
        or 0x80                 ; visible
.h:     ld d,a                  ; D = attribute 3 for the top two (slot S)
        ld a,e
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        inc e
        ld a,e
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        inc e
        inc d                   ; slot S + 1 for the bottom two
        ld a,e
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        inc e
        ld a,e
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        srl c
        ld a,(VA)
        inc a
        cp 3
        jr nz,.v
        ret

p30_end:
        ASSERT p30_end <= 0xDE00

; ---- setup (stub bank, 0xD000): sprite palette, pattern RAM 0, all sprites hidden, sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0          ; nibble 0 transparent
        ld bc,0x303B
        xor a
        out (c),a               ; pattern memory all 0 (figures upload lines 0-23 only)
        ld bc,64
.z:     ld b,0                  ; 64 x 256 bytes
.zz:    out (0x5B),a
        djnz .zz
        dec c
        jr nz,.z
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
pal:    defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "isf_rom.bin",0x3A01,rom_end-0x3A01
        SAVEBIN "isf_rom2.bin",0x386E,rom2_end-0x386E
        SAVEBIN "isf_p30.bin",0xD600,p30_end-0xD600
        SAVEBIN "isf_setup.bin",0xD000,setup_end-0xD000
