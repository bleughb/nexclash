; nxsuite/g4.asm - G4 FRAME: geometry and raster (spec section 3 G4). GPL-3.0-or-later.
; Nothing here assumes a line count: frames are found by the line number falling (wrap), with a guard.

; -> HL = the largest line seen over 3 frames (tight LSB / MSB / LSB reads, `line`); 0 = the counter
; never wrapped within the guard (~65536 reads)
frame_lines:
        ld a,3
flines_n:                                   ; A = frames
        inc a : ld (.w),a
        ld hl,0 : ld (.max),hl : ld (.prev),hl
        ld de,0                             ; guard
.l:     push de
        call line
        pop de
        push hl : ld bc,(.max) : or a : sbc hl,bc : pop hl : jr c,.nm
        ld (.max),hl
.nm:    push hl : ld bc,(.prev) : or a : sbc hl,bc : pop hl : ld (.prev),hl
        jr nc,.nw
        ld a,(.w) : dec a : ld (.w),a : jr z,.d
.nw:    dec de : ld a,d : or e : jr nz,.l
        ld hl,0 : ret
.d:     ld hl,(.max) : ret
.w:     db 0
.max:   dw 0
.prev:  dw 0

; CTC channel 3 as a free-running timer (control $07: timer, prescaler 16, time constant follows, reset;
; time constant 0 = 256; one tick = 16 clocks of 28 MHz): ticks over 256 raster lines, polled (run at
; 28 MHz: one poll is far below the 512 T of a wrap). -> DEHL = ticks per line x 100 (0 = no lines)
ctc_line:
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld bc,$243B : ld a,$1F : out (c),a
        ld bc,$253B : in a,(c) : ld e,a
        ld hl,0                             ; guard
.s:     in a,(c) : cp e : jr nz,.go
        dec hl : ld a,h : or l : jr nz,.s
        jr .none
.go:    ld e,a                              ; E = this line's LSB
        ld b,$1B : in a,(c) : ld (.c0),a : ld d,a   ; D = last CTC value
        ld hl,0 : ld (.wr),hl
        ld ix,256                           ; lines to count
        ld hl,0                             ; guard per line
.p:     ld b,$1B : in a,(c)                 ; CTC (port $1B3B)
        cp d : ld d,a : jr c,.nwr : jr z,.nwr
        push hl : ld hl,(.wr) : inc hl : ld (.wr),hl : pop hl   ; the count went up: a wrap
.nwr:   ld b,$25 : in a,(c)                 ; line LSB
        cp e : jr z,.same
        ld e,a : ld hl,0
        dec ix : ld a,ixh : or ixl : jr nz,.p
        ; ticks = 256 x wraps + c0 - c1 (< 65536: 256 lines are ~28,700 ticks)
        ld b,$1B : in a,(c) : ld c,a
        ld a,(.c0) : sub c : ld e,a : ld d,0 : jr nc,.pos
        dec d
.pos:   ld hl,(.wr) : ld h,l : ld l,0 : add hl,de
        ld (ctc_ticks),hl
        ; x 100 / 256
        ld b,h : ld c,l : ld de,100 : call mul16
        ld l,h : ld h,e : ld e,d : ld d,0
        ret
.same:  dec hl : ld a,h : or l : jr nz,.p
.none:  ld hl,0 : ld de,0 : ret
.c0:    db 0
.wr:    dw 0
ctc_ticks: dw 0
