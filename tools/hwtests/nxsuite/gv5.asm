; nxsuite/gv5.asm - V VISUAL on page 60 after G1 / X-D (OVLX_3): V03, V06 (sprite transforms, the Layer 2
; priority bit). GPL-3.0-or-later. Palette entries written go back through pal_back; sprites through spr_off.
; VNEG = 1: the decisive setting changed (V03: Y scale and Y mirror; V06: no priority bit).

; B = y, D = x0, E = width, C = colour -> one row of a 256 x 192 Layer 2
l2_run: ld a,b : rlca : rlca : rlca : and 7 : add a,44 : nextreg $53,a
        ld a,b : and 31 : add a,$60 : ld h,a : ld l,d
.x:     ld (hl),c : inc l : dec e : jr nz,.x
        nextreg $53,$0B : ret
; B = y0, D = x0, C = colour -> a 30 x 16 block
v_box:  ld a,16
.r:     push af : push bc : push de : ld e,30 : call l2_run : pop de : pop bc : pop af
        inc b : dec a : jr nz,.r
        ret
v_ret:  ret

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
.blk:   dw q_v03s, q_v03o, k_s, k_o, v_ret
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

; ---------------------------------------------------------------- V06 the Layer 2 priority bit
; Book ch 17 (N5), TECHNIQUES.md:363: a Layer 2 colour whose second $44 byte has bit 7 draws above every layer,
; sprites too, also in blend modes, and only where the dot is not transparent. Blue blocks at x 60 / 110 / 160
; (rows 112 and 144): left index $10 plain, middle $11 with the priority bit, right $12 with the priority bit
; and $14's colour (transparent). Red bars (sprites, X scale 8) cross them; order SLU above line 136, blend
; mode 110 for lines 136-167 (blended: the lower blocks look lighter). Claim: red over the left block, blue
; over the middle one, red where the right one is.
@t_v06: ld a,(NRSNAP+$14) : call l2w_fill
        ld b,112 : call .row : ld b,144 : call .row
        nextreg $43,$10
        ld a,$10 : ld e,$03 : call pal_set
        ld a,$11 : ld e,$03 : call pal_set
        ld a,$12 : ld e,$03 : call pal_set
        nextreg $40,$11 : nextreg $44,$03
        IF VNEG = 0
        nextreg $44,$81
        ELSE
        nextreg $44,$01
        ENDIF
        nextreg $40,$12 : ld a,(NRSNAP+$14) : nextreg $44,a : nextreg $44,$81
        xor a : ld e,$E0 : call spr_pat
        xor a : ld de,$3074 : ld bc,$00C0 : call spr_set : nextreg $39,%00011000   ; X scale 8
        ld a,1 : ld de,$3094 : ld bc,$00C0 : call spr_set : nextreg $39,%00011000
        call l2s_on : nextreg $15,$01
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,q_v06 : call ask
        nextreg $62,0 : call spr_off : call pal_back : jp l2w_off
.row:   ld d,60 : ld c,$10 : push bc : call v_box : pop bc
        ld d,110 : ld c,$11 : push bc : call v_box : pop bc
        ld d,160 : ld c,$12 : jp v_box
.cop:   db $15,$01, $80,136, $15,$19, $80,168, $15,$01, $FF,$FF
.cope:
q_v06:  db 1
        db "V06 RED BARS, BLUE BLOCKS",0
        db " ",0
        db "In both rows, where the red bar",0
        db "crosses the blocks:",0
        db "1 = red over the LEFT block,",0
        db "    blue over the MIDDLE one,",0
        db "    no RIGHT block (red there)",0
        db "2 = red over every block",0
        db "3 = something else",0,0
        db "claim",0,"no-prio",0,"other",0
