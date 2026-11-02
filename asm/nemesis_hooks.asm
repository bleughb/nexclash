; Nemesis the Warlock (Martech 1987, 48K) - every figure as hardware sprites.
; Hooks + state in RAM page PAGE mapped at 0x2000-0x3FFF (MMU slot 1) for the whole game (the
; game reads no ROM there: scan 2026-11-02). Interrupts are off all game (isr: 0 accepted).
;
; Method (games/nemesis_the_warlock.md "Build plan"): the game's masked plotters run UNCHANGED,
; so all game memory stays identical. Each plot is logged (buffer address HL, save-under IY,
; graphic DE, width, direction). After the buffer -> screen copy (0x7D9A) the hook writes each
; logged figure's save-under onto the SCREEN only (reverse order = the background), and shows
; each figure as 2x2 4-bit sprites: pixel 1 = ink, 2 = paper (solid), 0 = transparent; ink and
; paper from the room attribute (51800); patterns cached by (graphic, width).
;
; Sites (original bytes checked by nemesis.py):
;   31213 06 08 DD     LD B,8 / LD IX,8 (8x8 plot)       -> JP e_p8
;   31268 3A DA CA     LD A,(51930) (32-line plot right)  -> JP e_pr
;   31362 3A DA CA     LD A,(51930) (32-line plot left)   -> JP e_pl
;   32154 21 F8 5D     LD HL,24056 (buffer -> screen)     -> JP e_cp
;   37865 21 00 40     LD HL,16384 (full-screen draw)     -> JP e_cls

        DEVICE ZXSPECTRUMNEXT

NENT    EQU 16          ; figures per frame (4 sprites each)
NSLOT   EQU 32          ; cached images (4 patterns each)
BUFBASE EQU 23798       ; back buffer: line L, column c at BUFBASE + 32L + c = screen (c*8, L)
ROOMATT EQU 51800

        ORG 0x2000
; ---- plot entries ----
e_pr:   push af
        push bc
        ld c,0
        call plog
        pop bc
        pop af
        ld a,(51930)
        jp 31271
e_pl:   push af
        push bc
        ld c,1
        call plog
        pop bc
        pop af
        ld a,(51930)
        jp 31365
plog:   ld a,(51930)
        ld b,4
        cp 4
        jr z,.w3
        cp 5
        jr nz,logent
.w3:    ld b,3
        jr logent
e_p8:   push af
        push bc
        ld bc,0x0100            ; w 1, right
        call logent
        pop bc
        pop af
        ld b,8
        ld ix,8
        jp 31219

; B = width (1, 3, 4), C = direction (0 right, 1 left); HL, DE, IY = plotter inputs
logent: ld a,b
        dec a
        jr z,.ok                ; 8x8: its own save area
        ld a,iyh
        cp 0x40
        ret c                   ; save-under in ROM (IY = 0 at 0x7162): a permanent stamp = scenery
.ok:    ld a,(cnt)
        cp NENT
        ret nc                  ; full: not shown (the verifier counts it)
        push hl
        push de
        ld (t_hl),hl
        ld (t_de),de
        ld (t_iy),iy
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,tab
        add hl,de
        ld de,(t_hl)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(t_iy)
        ld a,b
        dec a
        jr nz,.iy
        ld de,32388             ; the 8x8 plotter's own save area
.iy:    ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(t_de)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),b
        inc hl
        ld (hl),c
        ld hl,cnt
        inc (hl)
        pop de
        pop hl
        ret

; ---- full-screen draw: sprites off, log cleared ----
e_cls:  push af
        push bc
        call hideall
        pop bc
        pop af
        ld hl,16384
        jp 37868

hideall:
        xor a
        ld (cnt),a
        ld (old),a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NENT*4
        jr nz,.h
        ret

; ---- buffer -> screen copy: run it, then come back to post ----
e_cp:   ld hl,post
        push hl
        ld hl,24056
        jp 32157

post:   push af
        push bc
        push de
        push hl
        push ix
        nextreg 0x07,3
        ld hl,frame
        inc (hl)
        ; palette: index 1 = room ink, 2 = room paper
        ld a,(ROOMATT)
        ld c,a
        and 7
        bit 6,c
        jr z,.i
        or 8
.i:     call rgb
        nextreg 0x43,0x20
        nextreg 0x40,1
        nextreg 0x41,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        bit 6,c
        jr z,.p
        or 8
.p:     call rgb
        nextreg 0x41,a
        ; background back onto the screen, last figure first
        ld a,(cnt)
        or a
        jr z,.spr
        ld b,a
.un:    push bc
        ld a,b
        dec a
        call entry
        call unpaint
        pop bc
        djnz .un
.spr:   ld a,(cnt)
        or a
        jr z,.hide
        ld b,a
        xor a
.mk:    push bc
        push af
        call entry
        pop af
        push af
        call mkspr
        pop af
        inc a
        pop bc
        djnz .mk
.hide:  ld a,(cnt)
        add a,a
        add a,a
        ld b,a                  ; first unused sprite
        ld a,(old)
        add a,a
        add a,a
        ld c,a                  ; end of last frame's sprites
.hl:    ld a,b
        cp c
        jr nc,.done
        nextreg 0x34,a
        nextreg 0x38,0
        inc b
        jr .hl
.done:  ld a,(cnt)
        ld (old),a
        xor a
        ld (cnt),a
        nextreg 0x07,0
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

; A = Spectrum colour 0-15 -> A = RGB332
rgb:    push hl
        ld hl,spc
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld a,(hl)
        pop hl
        ret

; A = entry index -> IX = tab + 8A
entry:  ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,tab
        add hl,de
        push hl
        pop ix
        ret

; lines of entry IX -> A (8 for the 8x8 plot, else 32)
lines:  ld a,(ix+6)
        cp 1
        ld a,8
        ret z
        ld a,32
        ret

;---- write entry IX's save-under onto the screen (copy window: lines 8-127, columns 2-29) ----
unpaint:
        ld l,(ix+0)
        ld h,(ix+1)
        ld de,BUFBASE
        or a
        sbc hl,de               ; HL = offset in the buffer (signed)
        ld a,h
        cp 0x10
        jr c,.pos
        cp 0xFC
        ret c                   ; first line >= 128 or < -32: nothing visible
.pos:   ld a,l
        and 31
        ld (t_v),a              ; c0
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,h
        add a,a
        add a,a
        add a,a
        or b
        add a,32
        ld (t_y),a              ; y0 + 32 (0-159)
        ld b,a
        ld a,40
        sub b
        jr nc,.rs
        xor a
.rs:    ld (t_r),a              ; first visible row = max(0, 8 - y0)
        call lines
        ld c,a
        ld a,160
        sub b                   ; 128 - y0
        cp c
        jr c,.re
        ld a,c
.re:    ld hl,t_r
        sub (hl)
        ret c
        ret z
        ld c,a                  ; rows to write
        ld e,(ix+2)
        ld d,(ix+3)             ; DE = save-under
        ld a,(hl)
        or a
        jr z,.d0
        ld b,a
.dl:    ld a,e
        add a,(ix+6)
        ld e,a
        jr nc,.dn
        inc d
.dn:    djnz .dl                ; skip the saved bytes of the hidden rows
.d0:    ld a,(t_y)
        add a,(hl)
        sub 32                  ; first visible line
        ld b,a
        and 7
        ld h,a
        ld a,b
        and 0xC0
        rrca
        rrca
        rrca
        or h
        or 0x40
        ld h,a
        ld a,b
        and 0x38
        add a,a
        add a,a
        ld l,a                  ; HL = screen line, column 0
        ld a,(t_v)
        cp 2
        jr c,.slow
        add a,(ix+6)
        cp 31
        jr nc,.slow             ; part of the row outside columns 2-29
        ld a,(ix+7)
        or a
        jr nz,.left
        ld a,(t_v)
        or l
        ld l,a
.fr:    push bc
        push hl
        ld c,(ix+6)
        ld b,0
        ex de,hl
        ldir                    ; right: saved in screen order
        ex de,hl
        pop hl
        call down
        pop bc
        dec c
        jr nz,.fr
        ret
.left:  ld a,(t_v)
        add a,(ix+6)
        dec a
        or l
        ld l,a
.fl:    push hl
        ld b,(ix+6)
.fb:    ld a,(de)               ; left: saved from the row's last byte
        ld (hl),a
        inc de
        dec l
        djnz .fb
        pop hl
        call down
        dec c
        jr nz,.fl
        ret
.slow:  ld a,(ix+7)
        or a
        ld a,(t_v)
        jr z,.sr
        add a,(ix+6)
        dec a
.sr:    ld (t_j),a              ; current column
        ld b,(ix+6)
.sb:    ld a,(t_j)
        cp 2
        jr c,.sn
        cp 30
        jr nc,.sn
        push hl
        or l
        ld l,a
        ld a,(de)
        ld (hl),a
        pop hl
.sn:    inc de
        ld a,(ix+7)
        or a
        ld a,(t_j)
        jr nz,.sd
        inc a
        jr .sx
.sd:    dec a
.sx:    ld (t_j),a
        djnz .sb
        call down
        dec c
        jr nz,.slow
        ret

; HL = next screen line (columns kept)
down:   inc h
        ld a,h
        and 7
        ret nz
        ld a,l
        add a,32
        ld l,a
        ret c
        ld a,h
        sub 8
        ld h,a
        ret

; ---- sprites 4A..4A+3 for entry IX ----
mkspr:  add a,a
        add a,a
        ld (t_spr),a
        call lookup             ; A = first pattern (4 x slot)
        ld (t_pat),a
        ld l,(ix+0)
        ld h,(ix+1)
        ld de,BUFBASE
        or a
        sbc hl,de
        jr nc,.pos
        ld a,h
        cp 0xFC
        jp c,.off               ; line < -32
        jr .ok
.pos:   ld a,h
        cp 0x14
        jp nc,.off              ; line >= 160: off the window
.ok:
        ld a,l
        and 31
        ld e,a                  ; c0
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld d,a
        ld a,h
        add a,a
        add a,a
        add a,a
        or d
        add a,32
        ld (t_y),a              ; Y = line + 32
        ld l,e
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de               ; X = 8 c0 + 32
        ld a,(ix+7)
        or a
        jr z,.x
        ld a,(ix+6)
        cp 3
        jr nz,.x
        ld de,-8                ; left, 24 wide: the right 8 pixels of the mirrored box are empty
        add hl,de
.x:     ld (t_x),hl
        ld b,0
.q:     ld a,(t_spr)
        add a,b
        nextreg 0x34,a
        ld hl,(t_x)
        ld a,b
        and 1
        ld c,a
        ld a,(ix+7)
        xor c                   ; left: quadrant columns swapped
        jr z,.q0
        ld de,16
        add hl,de
.q0:    ld a,l
        nextreg 0x35,a
        ld a,(t_y)
        bit 1,b
        jr z,.q1
        add a,16
.q1:    nextreg 0x36,a
        ld a,(ix+7)
        add a,a
        add a,a
        add a,a                 ; X mirror (bit 3) for left
        ld c,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,(t_pat)
        add a,b
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
        inc b
        ld a,b
        cp 4
        jr nz,.q
        ret
.off:   ld a,(t_spr)
        ld b,4
.o:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .o
        ret

; ---- pattern cache: key (graphic DE, width) -> slot; A = 4 x slot ----
lookup: ld hl,keys
        ld b,0
.f:     ld a,(ix+4)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(ix+5)
        cp (hl)
        dec hl
        jr nz,.n
        inc hl
        inc hl
        ld a,(ix+6)
        cp (hl)
        dec hl
        dec hl
        jr z,.hit
.n:     inc hl
        inc hl
        inc hl
        inc hl
        inc b
        ld a,b
        cp NSLOT
        jr nz,.f
        ; miss: next slot (round robin) not used in this frame
        ld c,NSLOT
.a:     ld a,(rr)
        ld b,a
        inc a
        and NSLOT-1
        ld (rr),a
        call keyp
        inc hl
        inc hl
        inc hl
        ld a,(frame)
        cp (hl)
        jr nz,.free
        dec c
        jr nz,.a
.free:  dec hl
        dec hl
        dec hl
        ld a,(ix+4)
        ld (hl),a
        inc hl
        ld a,(ix+5)
        ld (hl),a
        inc hl
        ld a,(ix+6)
        ld (hl),a
        dec hl
        dec hl
        push bc
        push hl
        ld a,b
        call build
        pop hl
        pop bc
.hit:   inc hl
        inc hl
        inc hl
        ld a,(frame)
        ld (hl),a
        ld a,b
        add a,a
        add a,a
        ret

; B = slot -> HL = keys + 4B
keyp:   ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        ld de,keys
        add hl,de
        ret

; ---- A = slot: patterns 4A..4A+3 from entry IX's graphic ----
build:  add a,a
        add a,a
        ld (t_pat),a
        ld l,(ix+4)
        ld h,(ix+5)
        ld (t_m),hl             ; mask
        ld a,(ix+6)
        ld de,8
        cp 1
        jr z,.o
        ld de,96
        cp 3
        jr z,.o
        ld de,128
.o:     add hl,de
        ld (t_g),hl             ; image
        call lines
        ld (t_ln),a
        xor a
.q:     ld (t_q),a
        ld c,a
        ld a,(t_pat)
        add a,c
        ld c,a
        srl a
        bit 0,c
        jr z,.e
        or 0x80                 ; odd pattern: second half of the 256-byte slot
.e:     ld bc,0x303B
        out (c),a
        ld a,(t_q)
        and 1
        add a,a
        ld (t_j),a              ; first byte column = 2 qx
        ld a,(t_q)
        and 2
        rlca
        rlca
        rlca
        ld (t_r),a              ; first row = 16 qy
        ld b,(ix+6)             ; row offset = 16 qy * w + 2 qx
        ld hl,0
        ld e,a
        ld d,0
        or a
        jr z,.m0
.m:     add hl,de
        djnz .m
.m0:    ld a,(t_j)
        ld e,a
        add hl,de
        ld (t_x),hl
        ld c,16
.row:   ld a,(t_r)
        ld hl,t_ln
        cp (hl)
        jr nc,.zr               ; below the figure: 16 transparent pixels
        ld a,(t_j)
        ld b,a
        call byte
        inc b
        call byte
        ld hl,(t_x)
        ld e,(ix+6)
        ld d,0
        add hl,de
        ld (t_x),hl
        jr .nr
.zr:    xor a
        ld b,8
.z:     out (0x5B),a
        djnz .z
.nr:    ld hl,t_r
        inc (hl)
        dec c
        jr nz,.row
        ld a,(t_q)
        inc a
        cp 4
        jr nz,.q
        ret

; 8 pixels for byte column B of the row at offset (t_x) (+1 for the second column); keeps B, C
byte:   ld a,b
        cp (ix+6)
        jr nc,.z
        push bc
        ld hl,(t_x)
        ld a,b
        and 1
        ld e,a
        ld d,0
        add hl,de
        ex de,hl
        ld hl,(t_m)
        add hl,de
        ld b,(hl)               ; mask
        ld hl,(t_g)
        add hl,de
        ld c,(hl)               ; image
        ld h,high nib
        ld a,b
        and 0xF0
        ld l,a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        and 15
        or l
        add a,a
        ld l,a
        jr nc,.h1
        inc h
.h1:    ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld h,high nib
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,c
        and 15
        or l
        add a,a
        ld l,a
        jr nc,.h2
        inc h
.h2:    ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        pop bc
        ret
.z:     xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        ret

spc:    db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
; nibble table (generated): entry (mask nibble << 4 | image nibble) = 4 pixels, 2 per byte
        ALIGN 256
nib:
        db 0x22,0x22,0x22,0x21,0x22,0x12,0x22,0x11,0x21,0x22,0x21,0x21,0x21,0x12,0x21,0x11
        db 0x12,0x22,0x12,0x21,0x12,0x12,0x12,0x11,0x11,0x22,0x11,0x21,0x11,0x12,0x11,0x11
        db 0x22,0x20,0x22,0x21,0x22,0x10,0x22,0x11,0x21,0x20,0x21,0x21,0x21,0x10,0x21,0x11
        db 0x12,0x20,0x12,0x21,0x12,0x10,0x12,0x11,0x11,0x20,0x11,0x21,0x11,0x10,0x11,0x11
        db 0x22,0x02,0x22,0x01,0x22,0x12,0x22,0x11,0x21,0x02,0x21,0x01,0x21,0x12,0x21,0x11
        db 0x12,0x02,0x12,0x01,0x12,0x12,0x12,0x11,0x11,0x02,0x11,0x01,0x11,0x12,0x11,0x11
        db 0x22,0x00,0x22,0x01,0x22,0x10,0x22,0x11,0x21,0x00,0x21,0x01,0x21,0x10,0x21,0x11
        db 0x12,0x00,0x12,0x01,0x12,0x10,0x12,0x11,0x11,0x00,0x11,0x01,0x11,0x10,0x11,0x11
        db 0x20,0x22,0x20,0x21,0x20,0x12,0x20,0x11,0x21,0x22,0x21,0x21,0x21,0x12,0x21,0x11
        db 0x10,0x22,0x10,0x21,0x10,0x12,0x10,0x11,0x11,0x22,0x11,0x21,0x11,0x12,0x11,0x11
        db 0x20,0x20,0x20,0x21,0x20,0x10,0x20,0x11,0x21,0x20,0x21,0x21,0x21,0x10,0x21,0x11
        db 0x10,0x20,0x10,0x21,0x10,0x10,0x10,0x11,0x11,0x20,0x11,0x21,0x11,0x10,0x11,0x11
        db 0x20,0x02,0x20,0x01,0x20,0x12,0x20,0x11,0x21,0x02,0x21,0x01,0x21,0x12,0x21,0x11
        db 0x10,0x02,0x10,0x01,0x10,0x12,0x10,0x11,0x11,0x02,0x11,0x01,0x11,0x12,0x11,0x11
        db 0x20,0x00,0x20,0x01,0x20,0x10,0x20,0x11,0x21,0x00,0x21,0x01,0x21,0x10,0x21,0x11
        db 0x10,0x00,0x10,0x01,0x10,0x10,0x10,0x11,0x11,0x00,0x11,0x01,0x11,0x10,0x11,0x11
        db 0x02,0x22,0x02,0x21,0x02,0x12,0x02,0x11,0x01,0x22,0x01,0x21,0x01,0x12,0x01,0x11
        db 0x12,0x22,0x12,0x21,0x12,0x12,0x12,0x11,0x11,0x22,0x11,0x21,0x11,0x12,0x11,0x11
        db 0x02,0x20,0x02,0x21,0x02,0x10,0x02,0x11,0x01,0x20,0x01,0x21,0x01,0x10,0x01,0x11
        db 0x12,0x20,0x12,0x21,0x12,0x10,0x12,0x11,0x11,0x20,0x11,0x21,0x11,0x10,0x11,0x11
        db 0x02,0x02,0x02,0x01,0x02,0x12,0x02,0x11,0x01,0x02,0x01,0x01,0x01,0x12,0x01,0x11
        db 0x12,0x02,0x12,0x01,0x12,0x12,0x12,0x11,0x11,0x02,0x11,0x01,0x11,0x12,0x11,0x11
        db 0x02,0x00,0x02,0x01,0x02,0x10,0x02,0x11,0x01,0x00,0x01,0x01,0x01,0x10,0x01,0x11
        db 0x12,0x00,0x12,0x01,0x12,0x10,0x12,0x11,0x11,0x00,0x11,0x01,0x11,0x10,0x11,0x11
        db 0x00,0x22,0x00,0x21,0x00,0x12,0x00,0x11,0x01,0x22,0x01,0x21,0x01,0x12,0x01,0x11
        db 0x10,0x22,0x10,0x21,0x10,0x12,0x10,0x11,0x11,0x22,0x11,0x21,0x11,0x12,0x11,0x11
        db 0x00,0x20,0x00,0x21,0x00,0x10,0x00,0x11,0x01,0x20,0x01,0x21,0x01,0x10,0x01,0x11
        db 0x10,0x20,0x10,0x21,0x10,0x10,0x10,0x11,0x11,0x20,0x11,0x21,0x11,0x10,0x11,0x11
        db 0x00,0x02,0x00,0x01,0x00,0x12,0x00,0x11,0x01,0x02,0x01,0x01,0x01,0x12,0x01,0x11
        db 0x10,0x02,0x10,0x01,0x10,0x12,0x10,0x11,0x11,0x02,0x11,0x01,0x11,0x12,0x11,0x11
        db 0x00,0x00,0x00,0x01,0x00,0x10,0x00,0x11,0x01,0x00,0x01,0x01,0x01,0x10,0x01,0x11
        db 0x10,0x00,0x10,0x01,0x10,0x10,0x10,0x11,0x11,0x00,0x11,0x01,0x11,0x10,0x11,0x11
code_end:

; ---- state (zero at start) ----
cnt:    db 0
old:    db 0
frame:  db 0
rr:     db 0
t_v:    db 0
t_spr:  db 0
t_pat:  db 0
t_y:    db 0
t_q:    db 0
t_r:    db 0
t_j:    db 0
t_ln:   db 0
t_x:    dw 0
t_hl:   dw 0
t_de:   dw 0
t_iy:   dw 0
t_m:    dw 0
t_g:    dw 0
rowp:   dw 0
keys:   ds NSLOT*4          ; graphic lo, hi, width (0 = empty), frame stamp
tab:    ds NENT*8           ; HL, save IY, graphic DE, width, direction
regs:   ds 20               ; register block for the start-up tail
page_end:

; --- setup routine (stub bank, 0xD000): hide all, clip to the copy window, sprites on ---
        ORG 0xD000
setup:  nextreg 0x4B,0
        nextreg 0x43,0x20
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,16
        nextreg 0x19,239
        nextreg 0x19,8
        nextreg 0x19,127
        nextreg 0x15,0x01
        ret
setup_end:

        SAVEBIN "nw_page.bin",0x2000,page_end-0x2000
        SAVEBIN "nw_setup.bin",0xD000,setup_end-0xD000
