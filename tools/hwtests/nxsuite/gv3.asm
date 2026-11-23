; nxsuite/gv3.asm - V VISUAL on page 40 at $F200 (OVLX_1; Z04 uses $F000-$F1FF, F05 $FD00-$FF01): the
; tilemap and layer tests V11, V12, V13, V14, V04, and V07 (from gv2.asm). GPL-3.0-or-later. The tilemap
; lives in bank 7 page 14 ($6E / $6F bit 7, first 8K only: NEXT_REGISTERS.md:46; C03 / C04 build their code
; there at run time): map at offset $0800 (40 x 32, two bytes an entry), definitions at $1400. Palette
; entries through pal_set / pal_back; $6B $6C $6E $6F $68 $15 $4A by the harness; sprites by spr_off; the
; copper stopped. VNEG = 1: the decisive setting changed.

TMAP    equ $6800                   ; page 14 in slot 3
TDEF    equ $7400
; page 14 into slot 3 (tm_end: the harness page back)
tm_pg:  nextreg $53,14 : ret
tm_end: nextreg $53,$0B : ret
; E = attribute -> every map entry tile 0 with it
tm_clr: ld hl,TMAP : ld bc,1280
.l:     ld (hl),0 : inc hl : ld (hl),e : inc hl : dec bc : ld a,b : or c : jr nz,.l
        ret
; A = tile, E = byte, B = bytes -> definition at TDEF + A * (32, or 8 if B = 8) filled with E
tm_def: ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl : ld a,b : cp 8 : jr z,.s
        add hl,hl : add hl,hl
.s:     push bc : ld bc,TDEF : add hl,bc : pop bc
.l:     ld (hl),e : inc hl : djnz .l
        ret
; B = tile row, C = first column, A = count, D = tile, E = attribute -> map entries
tm_run: push af : push de : ld a,c : ld h,0 : ld l,b : add hl,hl : add hl,hl : add hl,hl
        ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,de : add hl,a : add hl,hl   ; (row * 40 + col) * 2
        ld de,TMAP : add hl,de : pop de : pop bc
.l:     ld (hl),d : inc hl : ld (hl),e : inc hl : djnz .l
        ret
; A = $6B value -> map / definition bases, scroll 0, clip window and $4B / $4C at their reset values, the
; tilemap on (the harness puts $6B $6C $6E $6F $2F-$31 $4B $4C back; the clip window is left at its reset value)
tm_on:  nextreg $6E,$88 : nextreg $6F,$94 : nextreg $6C,0
        nextreg $2F,0 : nextreg $30,0 : nextreg $31,0 : nextreg $4B,$E3 : nextreg $4C,$0F
        nextreg $1C,8 : nextreg $1B,0 : nextreg $1B,159 : nextreg $1B,0 : nextreg $1B,255
        nextreg $6B,a : ret
; B = y, D = x0, E = width, C = colour -> one row of a 256 x 192 Layer 2
g3_run: ld a,b : rlca : rlca : rlca : and 7 : add a,44 : nextreg $53,a
        ld a,b : and 31 : add a,$60 : ld h,a : ld l,d
.x:     ld (hl),c : inc l : dec e : jr nz,.x
        nextreg $53,$0B : ret
; -> A = the ULA paper-7 colour (ULA palette entry 23, the question screen's grey)
ula_grey:
        nextreg $43,0 : nextreg $40,23 : ld a,$41 : jp rdreg

; ---------------------------------------------------------------- V11 tile definitions past 8K in bank 7
; TECHNIQUES.md:523, NEXT_REGISTERS.md:46: a bank-7 offset counts 13 bits - past 8K it wraps to page 14's start,
; never page 15. Definitions base $1F00 (tile 0 = $1F00, transparent); tile 8 = $2000: page 14 offset 0
; painted colour 1 (green), page 15 offset 0 colour 2 (red). A bar of tile 8 at rows 21-22 (display 136-151).
; Claim: green.
@t_v11: call tm_pg
        ld e,0 : call tm_clr
        ld hl,$7F00 : ld (hl),$FF : ld de,$7F01 : ld bc,31 : ldir
        ld a,$11 + $11 * VNEG : ld hl,$6000 : ld (hl),a : ld de,$6001 : ld bc,31 : ldir
        ld b,21 : ld c,4 : ld de,$0800 : ld a,32 : call tm_run
        ld b,22 : ld c,4 : ld de,$0800 : ld a,32 : call tm_run
        nextreg $53,15
        ld a,$22 - $11 * VNEG : ld hl,$6000 : ld (hl),a : ld de,$6001 : ld bc,31 : ldir
        call tm_end
        nextreg $43,$30 : ld a,1 : ld e,$1C : call pal_set : ld a,2 : ld e,$E0 : call pal_set
        ld a,$81 : call tm_on : nextreg $6F,$9F
        ld hl,q_v11 : call ask
        jp pal_back
q_v11:  db 1
        db "V11 A BAR UNDER THE TEXT",0
        db " ",0
        db "1 = a GREEN bar",0
        db "2 = a RED bar",0
        db "3 = no bar, or something else",0,0
        db "wrap",0,"page15",0,"other",0

; ---------------------------------------------------------------- V12 text-mode tiles; $6B bit 0
; Part t: text mode ($6B bit 3; book N11: a dot is transparent when its colour after the palette is $14's).
; Tile 0 (all background) attribute 0: index 0 given $14's colour. A bar of tile 1 (checks $AA / $55) with
; attribute $20: background index $20 given $14's colour, ink $21 green. Claim: green checks on the grey paper.
; Part f: 4-bit tiles, attribute bit 0 = 1 (ULA over the tile), $6B bit 0 = 0 at the frame start and = 1 from
; line 152 (copper): the bar at rows 21-22 stays under the grey paper, the one at rows 24-25 shows (claim: lower).
@t_v12: call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,0 : ld b,8 : call tm_def
        ld hl,TDEF + 8 : ld b,4
.c:     ld (hl),$AA : inc hl : ld (hl),$55 : inc hl : djnz .c
        ld b,21 : ld c,4 : ld de,$0120 : ld a,32 : call tm_run
        ld b,22 : ld c,4 : ld de,$0120 : ld a,32 : call tm_run
        call tm_end
        nextreg $43,$30
        ld a,(NRSNAP+$14) : ld e,a : xor a : call pal_set
        ld a,(NRSNAP+$14) : sub VNEG : ld e,a : ld a,$20 : call pal_set
        ld a,$21 : ld e,$1C : call pal_set
        ld a,$89 : call tm_on
        ld hl,.blk : call ask2
        nextreg $62,0 : jp pal_back
.blk:   dw q_v12t, q_v12f, k_vt, k_vf, .mid
.mid:   call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,$FF : ld b,32 : call tm_def
        ld a,1 : ld e,$11 : ld b,32 : call tm_def
        ld b,21 : ld c,4 : ld de,$0101 : ld a,32 : call tm_run
        ld b,22 : ld c,4 : ld de,$0101 : ld a,32 : call tm_run
        ld b,24 : ld c,4 : ld de,$0101 : ld a,32 : call tm_run
        ld b,25 : ld c,4 : ld de,$0101 : ld a,32 : call tm_run
        call tm_end
        nextreg $43,$30 : ld a,1 : ld e,$1C : call pal_set
        ld a,$80 : call tm_on
        ld hl,.cop : ld b,.cope-.cop : jp cop_load
.cop:   db $6B,$80, $80,152
        IF VNEG = 0
        db $6B,$81
        ENDIF
        db $FF,$FF
.cope:
k_vt:    db "t",0
k_vf:    db "f",0
q_v12t: db 1
        db "V12 GREEN CHECKS UNDER THE TEXT",0
        db " ",0
        db "The background between the",0
        db "green dots is:",0
        db "1 = the grey of the screen",0
        db "2 = PINK / magenta",0
        db "3 = something else",0,0
        db "grey",0,"pink",0,"other",0
q_v12f: db 1
        db "V12 GREEN BARS UNDER THE TEXT",0
        db " ",0
        db "1 = ONE bar, the lower one",0
        db "2 = no bar",0
        db "3 = two bars, or other",0,0
        db "lower",0,"none",0,"other",0

; ---------------------------------------------------------------- V13 sprites between the ULA and the tilemap
; TECHNIQUES.md:349 (Mike Dailly): $15 order %110 with $68 bits 6:5 = %01 gives (U|T) S (T|U): a tile with
; attribute bit 0 = 0 in front of the sprites, with bit 0 = 1 behind them. Green tile blocks at display x
; 32-79 (bit 0 = 0) and 128-175 (bit 0 = 1), rows 21-22; red sprites (X scale 8) cross both at y 140. The grey
; paper (entry 23) is given $14's colour so the ULA does not hide the sprites; fallback $4A grey.
; Claim: green over red on the left block, red over green on the right one.
@t_v13: call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,$FF : ld b,32 : call tm_def
        ld a,1 : ld e,$11 : ld b,32 : call tm_def
        ld b,21 : call .blk2 : ld b,22 : call .blk2
        call tm_end
        nextreg $43,$30 : ld a,1 : ld e,$1C : call pal_set
        call ula_grey : nextreg $4A,a
        ld a,(NRSNAP+$14) : ld e,a : ld a,23 : call pal_set
        xor a : ld e,$E0 : call spr_pat
        xor a : ld de,$108C : ld bc,$00C0 : call spr_set : nextreg $39,%00011000
        ld a,1 : ld de,$908C : ld bc,$00C0 : call spr_set : nextreg $39,%00011000
        ld a,$80 : call tm_on
        ld a,(NRSNAP+$68) : and %10011110 : or %00100000 : nextreg $68,a
        nextreg $15,$19 - $18 * VNEG
        ld hl,q_v13 : call ask
        call spr_off : jp pal_back
.blk2:  push bc : ld c,8 : ld de,$0100 : ld a,6 : call tm_run : pop bc
        ld c,20 : ld de,$0101 : ld a,6 : jp tm_run
q_v13:  db 1
        db "V13 A RED BAR, TWO GREEN BLOCKS",0
        db " ",0
        db "1 = green over red on the LEFT",0
        db "    block, red over green on",0
        db "    the RIGHT block",0
        db "2 = red over both blocks",0
        db "3 = something else",0,0
        db "claim",0,"red-top",0,"other",0

; ---------------------------------------------------------------- V14 blend modes 110 / 111 and stencil
; TECHNIQUES.md:318, book ch 17 (N9, N10): mode 110 adds Layer 2 to the ULA per channel, clamped at 7; mode
; 111 adds and takes 5 (clamped at 0); stencil ($68 bit 0) shows ULA AND tilemap. Band 1 (lines 112-127,
; mode 110) and band 2 (128-143, mode 111): a Layer 2 block ($24) at x 64-127 over the grey paper; band 3
; (144-159, stencil, order SLU): a yellow tile block. Beside each, at x 136, a sprite square in the colour the
; rule gives, computed here from the grey read back. Claim: every pair the same colour.
@t_v14: call ula_grey : ld (.u),a
        ld d,a : ld e,$24 : xor a : call v_mix : ld (.e1),a
        ld a,(.u) : ld d,a : ld e,$24 : ld a,5 : call v_mix : ld (.e2),a
        ld a,(.u) : and $FC : ld (.e3),a
        ld a,(NRSNAP+$14) : call l2w_fill
        ld b,112
.r:     push bc : ld d,64 : ld e,64 : ld c,$24 : call g3_run : pop bc : inc b : ld a,b : cp 144 : jr nz,.r
        call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,$FF : ld b,32 : call tm_def
        ld a,1 : ld e,$11 : ld b,32 : call tm_def
        ld b,22 : ld c,12 : ld de,$0100 : ld a,8 : call tm_run
        ld b,23 : ld c,12 : ld de,$0100 : ld a,8 : call tm_run
        call tm_end
        nextreg $43,$30 : ld a,1 : ld e,$FC : call pal_set
        nextreg $43,$10 : ld a,$24 : ld e,$24 : call pal_set
        nextreg $43,$20
        ld a,(.e1 + VNEG) : ld e,a : ld a,1 : call pal_set
        ld a,(.e2 - VNEG) : ld e,a : ld a,2 : call pal_set
        ld a,(.e3) : ld e,a : ld a,3 : call pal_set
        ld a,1 : ld e,1 : call spr_pat : ld a,2 : ld e,2 : call spr_pat : ld a,3 : ld e,3 : call spr_pat
        xor a : ld de,$8870 : ld bc,$0081 : call spr_set
        ld a,1 : ld de,$8880 : ld bc,$0082 : call spr_set
        ld a,2 : ld de,$8890 : ld bc,$0083 : call spr_set
        ld a,$80 : call tm_on
        call l2s_on
        ld a,(NRSNAP+$68) : and %10011110 : ld (.c0+1),a : ld (.c5+1),a : inc a : ld (.c4+1),a
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,q_v14 : call ask
        nextreg $62,0 : call spr_off : call pal_back : jp l2w_off
.cop:   db $15,$01
.c0:    db $68,0, $80,112, $15,$19, $80,128, $15,$1D, $80,144, $15,$01
.c4:    db $68,1, $80,160
.c5:    db $68,0, $FF,$FF
.cope:
.u:     db 0
.e1:    db 0
.e2:    db 0
.e3:    db 0
q_v14:  db 1
        db "V14 THREE PAIRS: A WIDE BLOCK",0
        db "AND A SMALL SQUARE RIGHT OF IT",0
        db " ",0
        db "1 = each pair is ONE colour",0
        db "2 = at least one pair differs",0
        db "3 = something else",0,0
        db "match",0,"differ",0,"other",0
; D = colour 1, E = colour 2 (8-bit RRRGGGBB), A = k (0: sum clamped at 7; 5: sum - 5 clamped at 0) -> A
v_mix:  ld (.k),a
        ld a,d : call .sp : ld (.p),hl : ld a,c : ld (.p+2),a
        ld a,e : call .sp
        ld a,(.p+1) : add a,h : call .cl : rrca : rrca : rrca : ld d,a          ; R -> bits 7-5
        ld a,(.p) : add a,l : call .cl : add a,a : add a,a : or d : ld d,a      ; G -> bits 4-2
        ld a,(.p+2) : add a,c : call .cl : rrca : and 3 : or d : ret            ; B -> bits 1-0
; A = colour -> H = R, L = G, C = B (3 bits each; blue's two bits doubled, the low bit their OR)
.sp:    ld b,a : rlca : rlca : rlca : and 7 : ld h,a
        ld a,b : rrca : rrca : and 7 : ld l,a
        ld a,b : and 3 : jr z,.z
        add a,a : inc a
.z:     ld c,a : ret
.cl:    push hl : ld hl,.k : sub (hl) : pop hl : jr nc,.q
        xor a
.q:     cp 8 : ret c
        ld a,7 : ret
.k:     db 0
.p:     ds 3

; ---------------------------------------------------------------- V04 the transparency rules
; Book p188 (N1), TECHNIQUES.md:369: ULA and Layer 2 are transparent where the colour after the palette is
; $14's; sprites and tilemap where the index before it is $4B / $4C. Order SUL; four bands of 16 lines from
; line 112: A the grey paper given $14's colour (copper) over Layer 2 stripes; B tiles of index 15 (= $4C)
; whose palette colour is red; C sprites of index $E3 (= $4B) whose palette colour is green; D the paper
; transparent again over Layer 2 index $55 given $14's colour, fallback $4A yellow. In B and C black tiles /
; sprites (index 14 / $E2) show the layer is on. Claim: stripes, grey and black twice, yellow.
@t_v04: call ula_grey : ld (.g1+1),a : ld (.g2+1),a : ld (.g3+1),a
        ld e,a : ld a,23 : call pal_set                         ; entry 23 back through pal_back
        ld a,(NRSNAP+$14) : ld (.t1+1),a : ld (.t2+1),a
        call l2w_fill
        ld b,112
.s:     push bc : ld a,b : rlca : rlca : rlca : and 7 : add a,44 : nextreg $53,a
        ld a,b : and 31 : add a,$60 : ld h,a : ld l,0
.x:     ld a,l : and 8 : ld a,$03 : jr z,.y
        ld a,$E0
.y:     ld (hl),a : inc l : jr nz,.x
        nextreg $53,$0B : pop bc : inc b : ld a,b : cp 128 : jr nz,.s
        ld b,160
.d:     push bc : ld d,0 : ld e,0 : ld c,$55 : call g3_run : pop bc : inc b : ld a,b : cp 176 : jr nz,.d
        call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,$FF : ld b,32 : call tm_def
        ld a,1 : ld e,$EE : ld b,32 : call tm_def
        ld b,20 : call .tr : ld b,21 : call .tr
        call tm_end
        nextreg $43,$30 : ld a,$1F : ld e,$E0 : call pal_set : ld a,$1E : ld e,0 : call pal_set
        nextreg $43,$20 : ld a,$E3 : ld e,$1C : call pal_set : ld a,$E2 : ld e,0 : call pal_set
        nextreg $43,$10 : ld a,(NRSNAP+$14) : sub VNEG : ld e,a : ld a,$55 : call pal_set
        xor a : ld e,$E3 : call spr_pat : ld a,1 : ld e,$E2 : call spr_pat
        xor a : ld de,$0090 : ld b,7
.p:     push bc : push af : push de : ld l,a : and 1 : or $80 : ld c,a : ld b,0 : ld a,l : call spr_set
        pop de : ld a,d : add a,32 : ld d,a : pop af : inc a : pop bc : djnz .p
        nextreg $4A,$FC
        ld a,$80 : call tm_on
        call l2s_on : nextreg $15,$09
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,q_v04 : call ask
        nextreg $62,0 : call spr_off : call pal_back : jp l2w_off
; B = tile row -> tile 0 across, tile 1 (black, the visible reference) at columns 6-7, 14-15, 22-23, 30-31
.tr:    push bc : ld c,4 : ld de,$0010 : ld a,32 : call tm_run : pop bc
        ld c,6 : call .tb : ld c,14 : call .tb : ld c,22 : call .tb : ld c,30
.tb:    push bc : ld de,$0110 : ld a,2 : call tm_run : pop bc : ret
.cop:   db $43,0, $40,23
.g1:    db $41,0, $80,112, $40,23
.t1:    db $41,0, $80,128, $40,23
.g2:    db $41,0, $80,160, $40,23
.t2:    db $41,0, $80,176, $40,23
.g3:    db $41,0, $FF,$FF
.cope:
q_v04:  db 1
        db "V04 FOUR BANDS UNDER THE TEXT",0
        db "Top to bottom:",0
        db "1 = red/blue stripes, then",0
        db "    grey with black squares",0
        db "    twice, then yellow",0
        db "2 = one or more bands differ",0
        db "3 = something else",0,0
        db "claim",0,"differ",0,"other",0

; ---------------------------------------------------------------- V07 320 x 256 Layer 2 under the reset clip window
; 320 x 256 Layer 2, transparent except a green band at rows 0-15 (the reference, inside every window) and one
; at rows 224-255 (the bottom border, below the question). Asked with the clip window at its reset value
; 0-255 / 0-191 (book p114, N15), then at 0-159 / 0-255: both bands or the top one only. Keys c0 / c1;
; means=<c0>-<c1>, the claim (the reset window hides the bottom 64 rows until 0-159 / 0-255 is written):
; top-both. v = the second answer.
@t_v07: ld a,(NRSNAP+$14) : call l2w_fill
        ld b,0
.t:     ld c,$1C : push bc : call l2w_row : pop bc : inc b : ld a,b : cp 16 : jr nz,.t
        ld b,224
.b:     ld c,$1C : push bc : call l2w_row : pop bc : inc b : jr nz,.b
        call l2w_on
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,255 : nextreg $18,0 : nextreg $18,191
        ld hl,(wp) : ld (.wp),hl
        ld hl,q_v07 : call ask : jr c,.x
        ld hl,(askp) : ld (.w0),hl
        ld hl,(.wp) : ld (wp),hl : ld hl,k_vc0 : call ex_k : ld hl,(askp) : call wstr
        ld hl,(wp) : ld (.wp),hl
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,159 : nextreg $18,0 : nextreg $18,255
        ld hl,q_v07 : call ask : jr c,.x
        ld hl,(.wp) : ld (wp),hl : ld hl,k_vc1 : call ex_k : ld hl,(askp) : call wstr
        ld hl,k_means : call ex_k : ld hl,(.w0) : call wstr
        ld a,'-' : call wchr : ld hl,(askp) : call wstr
.x:     jp l2w_off
.wp:    dw 0
.w0:    dw 0
k_vc0:   db "c0",0
k_vc1:   db "c1",0
q_v07:  db 1
        db "V07 GREEN BANDS",0
        db " ",0
        db "Look at the whole picture, top",0
        db "to bottom, border included.",0
        db " ",0
        db "1 = a green band at the TOP and",0
        db "    one at the BOTTOM",0
        db "2 = a green band at the top only",0
        db "3 = something else",0,0
        db "both",0,"top",0,"other",0
