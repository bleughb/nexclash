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
; reach 0xDFFF; the rest is free), PFTAB, code 0xD600-0xDDFF, tables / variables 0xDE00-
PFTAB   EQU 0xD400              ; 256 bytes: frame f has painted colour-map entries (build time)
NIBTAB  EQU 0xDE00              ; 32 bytes: nibble -> 2 pattern bytes for ink NIBINK
NIBF    EQU 0xDE20              ; f(00), f(01), f(10), f(11)
NIBINK  EQU 0xDE24              ; ink NIBTAB holds (0 = none: inks are 1-15)
FLAGS   EQU 0xDF00              ; bits 0-2 object a shown, 3-5 the buffer its own pair shows
PEND    EQU 0xDF01              ; bits 0-2 the pending pair is up, 3-5 the buffer it shows
PX      EQU 0xDF02              ; x, y (PX + 1) of the image being placed
VA      EQU 0xDF04              ; object a
VBIT    EQU 0xDF05              ; 1 << a
VFR     EQU 0xDF06              ; frame
VINK    EQU 0xDF07              ; live ink
VSEL    EQU 0xDF08              ; buffer chosen by prep (0 / 1)
CACHE   EQU 0xDF10              ; per object a: (frame, ink) of buffer 0, of buffer 1 (4a + 0..3)

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
        ld b,17
.h:     ld a,b
        dec a
        nextreg 0x34,a
        nextreg 0x38,0x40       ; sprites 0-16 invisible
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

; HL = graphic, C = ink: a painted frame's 192 pattern bytes through emit (it maps the colour-map
; pages at slot 6 per byte), then page CPAGE+4 back at slot 6 (the caller runs from it).
slow48: push de
        push hl
        ld de,-GFX0
        add hl,de
        ex de,hl                ; DE = colour-map index
        pop hl
        ld b,48
.lp:    ld a,(hl)
        call emit
        inc hl
        inc de
        djnz .lp
        nextreg 0x56,CPAGE+4
        pop de
        ret
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
; entry, A = object a: its new image -> a buffer; the pending pair shows it at (x + dx, y + dy)
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
        call prep               ; A = slot, VSEL
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
        add a,2
        ld d,a
        jp place                ; the pending pair

; exit, A = object a: its own pair takes the image (the pending one, or built now), pending hidden
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
        call slotv              ; A = slot of VSEL
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

; -> A = slot of buffer VSEL for object VA: 5 - a / 8 - a
slotv:  ld a,(VSEL)
        or a
        ld a,5
        jr z,.s
        ld a,8
.s:     ld b,a
        ld a,(VA)
        ld c,a
        ld a,b
        sub c
        ret

; A = a -> 13 - 4a (its own pair)
sprnum: add a,a
        add a,a
        cpl
        add a,14
        ret

; hide the pending pair of VA
hidep:  ld a,(VA)
        call sprnum
        add a,2
        nextreg 0x34,a
        nextreg 0x38,0x40
        inc a
        nextreg 0x34,a
        nextreg 0x38,0x40
        ret

; D = sprite, C = attribute 3: D, D+1 at (PX, PX+1) (lines 0-15 / 16-23 of the slot)
place:  ld a,d
        nextreg 0x34,a
        ld a,(PX)
        add a,32
        nextreg 0x35,a
        ld a,0
        rla
        nextreg 0x37,a          ; X8, palette offset 0
        ld a,(PX+1)
        add a,32
        nextreg 0x36,a
        nextreg 0x39,0x80       ; 4-bit, N6 = 0
        ld a,c
        nextreg 0x38,a
        ld a,d
        inc a
        nextreg 0x34,a
        ld a,(PX)
        add a,32
        nextreg 0x35,a
        ld a,0
        rla
        nextreg 0x37,a
        ld a,(PX+1)
        add a,48
        nextreg 0x36,a
        nextreg 0x39,0xC0       ; N6 = 1
        ld a,c
        nextreg 0x38,a
        ret

; HL = object; VA, VBIT, VFR (non-zero): the image (frame, live ink) into a buffer - the one the
; figure's own pair shows, the other one, or uploaded into the other one -> VSEL, A = slot.
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
.s0:    ld e,a                  ; E = the buffer its own pair shows
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
        ld bc,0x303B
        out (c),a               ; upload from the slot's start (lines 0-23; 24-31 stay 0)
        ld a,(VFR)
        ld d,a
        add a,a
        add a,d                 ; 3 * frame, 8 bits (as the plotter)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(GBASE)
        add hl,de               ; HL = graphic
        ld a,(VINK)
        ld c,a
        ld a,(VFR)
        ld e,a
        ld d,high PFTAB
        ld a,(de)               ; painted frame?
        or a
        jr nz,.sl
        call fast48
        jr .dn
.sl:    call slow48             ; (ROM: maps the colour-map pages, then page 30 back)
.dn:    pop hl
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

; visibility of the three objects' own pairs (objects 1 and 2 on one spot with one frame: both
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
.np:    ld e,13                 ; own pair of object 0; then 9, 5
        ld d,5                  ; slot 5 - a (buffer 0)
        ld b,3
.v:     ld a,c
        and 8                   ; buffer bit of this object
        ld a,d
        jr z,.s
        add a,3                 ; buffer 1: slot 8 - a
.s:     or 0x40                 ; attribute 4 on
        bit 0,c
        jr z,.h
        or 0x80                 ; visible
.h:     ld h,a
        ld a,e
        nextreg 0x34,a
        ld a,h
        nextreg 0x38,a
        ld a,e
        inc a
        nextreg 0x34,a
        ld a,h
        nextreg 0x38,a
        srl c
        dec d
        ld a,e
        sub 4
        ld e,a
        djnz .v
        ret

; HL = graphic (48 bytes), C = ink, page CPAGE+4 at slot 6: an unpainted frame's 192 pattern
; bytes from the 32-byte nibble table (2 output bytes per graphics nibble), rebuilt when the ink
; changes. Clobbers A, BC, DE, HL.
fast48: ld a,(NIBINK)
        cp c
        call nz,mknib
        ld d,high NIBTAB
        ld b,48
.f:     ld a,(hl)
        inc hl
        ld c,a
        and 0xF0
        rrca
        rrca
        rrca
        ld e,a                  ; 2 * high nibble
        ld a,(de)
        out (0x5B),a
        inc e
        ld a,(de)
        out (0x5B),a
        ld a,c
        and 0x0F
        add a,a
        ld e,a                  ; 2 * low nibble
        ld a,(de)
        out (0x5B),a
        inc e
        ld a,(de)
        out (0x5B),a
        djnz .f
        ret

; C = ink: NIBTAB[2n], [2n + 1] = the two pattern bytes of graphics nibble n (pixel pairs
; f(n >> 2), f(n & 3); f(00) = 0, f(01) = ink, f(10) = ink << 4, f(11) = ink * 0x11)
mknib:  push hl
        push de
        push bc
        ld a,c
        ld (NIBINK),a
        ld hl,NIBF
        ld (hl),0
        inc l
        ld (hl),c
        inc l
        add a,a
        add a,a
        add a,a
        add a,a
        ld (hl),a
        inc l
        or c
        ld (hl),a
        ld de,NIBTAB
        ld b,0
.i:     ld c,0
.j:     ld a,b
        or low NIBF
        ld l,a
        ld a,(hl)
        ld (de),a
        inc e
        ld a,c
        or low NIBF
        ld l,a
        ld a,(hl)
        ld (de),a
        inc e
        inc c
        ld a,c
        cp 4
        jr nz,.j
        inc b
        ld a,b
        cp 4
        jr nz,.i
        pop bc
        pop de
        pop hl
        ret

; A = graphics byte, DE = colour-map index, C = live ink: 8 pixels -> 4 bytes to port 0x5B.
; Ink pixel = the entry's nibble when non-zero and its check byte equals the graphics byte, else
; the live ink; paper pixel = transparent (an overlay: painting never covers the scenery).
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
