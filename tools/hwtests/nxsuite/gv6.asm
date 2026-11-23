; nxsuite/gv6.asm - V VISUAL on page 63 at $FD02 (OVLX_4; above XH1's IM2 table $FC00-$FCFF and the vector
; read at $FD00-$FD01): V09, V03. GPL-3.0-or-later. VNEG = 1: V09 Y scroll 64 instead (the stripes miss the
; square); V03 Y scale and Y mirror.

; 256 x 192 Layer 2 (as l2_vl on page 43): E = x, C = colour -> a vertical line, rows 0-191
l6_vl:  ld d,44
.p:     ld a,d : nextreg $53,a
        ld h,$60 : ld l,e : ld b,32
.r:     ld (hl),c : inc h : djnz .r
        inc d : ld a,d : cp 50 : jr nz,.p
        nextreg $53,$0B : ret

; ---------------------------------------------------------------- V09 Layer 2 scroll wrap points
; TECHNIQUES.md:174, book ch 14: 256 x 192 wraps X at 256, Y at 192; 320 x 256 wraps X at 320 ($71 bit 0 =
; X bit 8), Y at 256. A red stripe at picture x 0-7 and a green one at y 0-7, Layer 2 on top of a white 32 x 32
; sprite at display x 112-143, y 80-111. 256 x 192 scrolled X 128, Y 96: the stripes cross at display (128,
; 96), on the square. 320 x 256 scrolled X 160, Y 128: wide (160, 128) = display (128, 96) again.
VYS     equ 96 - 32 * VNEG
@t_v09: ld a,(NRSNAP+$14) : call l2w_fill
        ld b,0
.h:     push bc : ld c,$1C : call l2_hl : pop bc : inc b : ld a,b : cp 8 : jr nz,.h
        ld e,0
.v:     push de : ld c,$E0 : call l6_vl : pop de : inc e : ld a,e : cp 8 : jr nz,.v
        xor a : ld e,$FF : call spr_pat
        xor a : ld de,$7050 : ld bc,$00C0 : call spr_set : nextreg $39,%00001010   ; scale 2 x 2
        call l2s_on : nextreg $15,$05
        nextreg $16,128 : nextreg $17,VYS
        ld hl,.blk : call ask2
        call spr_off : jp l2w_off
.blk:   dw q_v09, q_v09, k_a, k_w, .mid
; 320 x 256: red columns x 0-7 = the first 2 KB of page 44 (byte x * 256 + y), green rows y 0-7
.mid:   ld a,(NRSNAP+$14) : call l2w_fill
        nextreg $53,44 : ld hl,$6000 : ld (hl),$E0 : ld de,$6001 : ld bc,$07FF : ldir : nextreg $53,$0B
        ld b,0
.r:     push bc : ld c,$1C : call l2w_row : pop bc : inc b : ld a,b : cp 8 : jr nz,.r
        call l2w_on : nextreg $15,$05
        nextreg $71,0 : nextreg $16,160 : nextreg $17,VYS + 32
        ret
k_a:    db "a",0
k_w:    db "w",0
q_v09:  db 1
        db "V09 A RED AND A GREEN STRIPE",0
        db " ",0
        db "1 = they cross ON the white",0
        db "    square",0
        db "2 = they miss it",0
        db "3 = something else",0,0
        db "on",0,"off",0,"other",0

; ---------------------------------------------------------------- V03 scale after rotation; rotate, then mirror
; Book ch 16 (S7, N10): scale belongs to the screen (a 4 x 1 sprite stays wide when rotated); rotate 90
; clockwise first, then mirror. Sprite 0: solid green, rotated, X scale 4 -> 64 wide x 16 (between white rows
; 114 / 133: s = wide). Sprite 1: green with a red top-left quarter, rotated + X mirror -> rotate sends the
; corner top-left -> top-right, the mirror back to top-left (o = tl); mirror first would give bottom-right.
@t_v03: ld a,(NRSNAP+$14) : call l2w_fill
        ld b,114 : ld c,$FF : call l2_hl
        ld b,133 : ld c,$FF : call l2_hl
        ld a,1 : ld e,$1C : call spr_pat
        ld a,2 : ld bc,$303B : out (c),a : ld bc,$005B : ld d,0
.q:     ld a,d : and $88 : ld a,$1C : jr nz,.g
        ld a,$E0
.g:     out (c),a : inc d : jr nz,.q
        xor a : ld de,$3074 : ld bc,$02C1 : call spr_set          ; x 48, y 116, rotate, 5th byte, pattern 1
        IF VNEG = 0
        nextreg $39,%00010000                                       ; X scale 4
        ELSE
        nextreg $39,%00000100                                       ; Y scale 4
        ENDIF
        ld a,1 : ld de,$9674
        IF VNEG = 0
        ld bc,$0A82                                                 ; rotate + X mirror, pattern 2
        ELSE
        ld bc,$0682                                                 ; rotate + Y mirror
        ENDIF
        call spr_set
        call l2s_on : nextreg $15,$05
        ld hl,.blk : call ask2
        call spr_off : jp l2w_off
.blk:   dw q_v03s, q_v03o, k_s, k_o, .r                ; the callback on this page (v_ret is on page 61)
.r:     ret
k_s:    db "s",0
k_o:    db "o",0
q_v03s: db 1
        db "V03 THE GREEN BAR (left)",0
        db " ",0
        db "1 = WIDE: it lies between the",0
        db "    two white lines",0
        db "2 = TALL: it crosses the lines",0
        db "3 = something else",0,0
        db "wide",0,"tall",0,"other",0
q_v03o: db 1
        db "V03 THE GREEN SQUARE (right)",0
        db " ",0
        db "Where is its red corner?",0
        db "1 = top left",0
        db "2 = bottom right",0
        db "3 = somewhere else",0,0
        db "tl",0,"br",0,"other",0
