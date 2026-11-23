; nxsuite/gv4.asm - V VISUAL on page 43 after G5 / G8 (OVLX_2): V17, V01 (sprites, the sprite clip window,
; the copper). GPL-3.0-or-later. Reference lines in a transparent 256 x 192 Layer 2 on top (order LSU);
; sprites 0-31 hidden and the sprite clip window put back by spr_off; the copper stopped; $15 by the harness.
; VNEG = 1 (negative-control build): the decisive copper write is left out (V01 u: $15 bit 5 left clear;
; V17: the claimed effect written).

; 256 x 192 Layer 2: E = x, C = colour -> a vertical line, rows 0-191
l2_vl:  ld d,44
.p:     ld a,d : nextreg $53,a
        ld h,$60 : ld l,e : ld b,32
.r:     ld (hl),c : inc h : djnz .r
        inc d : ld a,d : cp 50 : jr nz,.p
        nextreg $53,$0B : ret
; D = first x, E = y, A = first sprite, B = count -> sprites of pattern 0 every 32 dots
v_row:  push bc : push af : push de
        ld bc,$0080 : call spr_set
        pop de : ld a,d : add a,32 : ld d,a
        pop af : inc a : pop bc : djnz v_row
        ret

; ---------------------------------------------------------------- V17 a copper MOVE to $15 resets the clip windows
; Red 16 x 16 sprites in two rows (y 116 and y 148, x 0-192). The copper, from line 0 every frame: the sprite
; clip window to X 96-159 (white lines at x 95 and 160), then at line 132 MOVE $15 with the value it already
; has (TECHNIQUES.md:215). Claim true: the lower row runs past the lines, the upper does not (lower).
; VNEG = 1 writes the window back to 0-255 / 0-191 there instead: the picture the claim gives.
@t_v17: ld a,(NRSNAP+$14) : call l2w_fill
        ld e,95 : ld c,$FF : call l2_vl
        ld e,160 : ld c,$FF : call l2_vl
        xor a : ld e,$E0 : call spr_pat
        xor a : ld de,116 : ld b,7 : call v_row
        ld a,7 : ld de,148 : ld b,7 : call v_row
        call l2s_on : nextreg $15,$05
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,q_v17 : call ask
        nextreg $62,0 : call spr_off : jp l2w_off
.cop:   db $1C,2, $19,96, $19,159, $19,0, $19,191, $80,132
        IF VNEG = 0
        db $15,$05
        ELSE
        db $1C,2, $19,0, $19,255, $19,0, $19,191        ; what the claim says the MOVE does
        ENDIF
        db $FF,$FF
.cope:
q_v17:  db 1
        db "V17 TWO ROWS OF RED SQUARES",0
        db " ",0
        db "1 = both rows only between the",0
        db "    two white lines",0
        db "2 = the upper row between the",0
        db "    lines, the LOWER row runs",0
        db "    past them",0
        db "3 = something else",0,0
        db "inside",0,"lower",0,"other",0

; ---------------------------------------------------------------- V01 sprite clip units; a change one line late
; Part 1 (u): clip window X 64-127, Y 0-255; three bands of red sprites (y 112, 136, 160; x 0-192). The copper
; sets $15 per band: band 1 sprites not over the border (window in display dots: 64-127, white lines at 63 /
; 128); band 2 over the border, $15 bit 5 clear (window ignored: all across); band 3 over the border with
; bit 5 (window in 2-dot units across the wide area: display 96-223, yellow lines at 95 / 224). Book p114.
; Part 2 (l): sprite 31 (red) at y 146 hidden; the copper shows it at line 157 and hides it at 158 (white
; Layer 2 rows 156 and 158 beside it): claim (a change shows one line later) -> it covers row 158 (late).
@t_v01: ld a,(NRSNAP+$14) : call l2w_fill
        ld e,63 : ld c,$FF : call l2_vl
        ld e,128 : ld c,$FF : call l2_vl
        ld e,95 : ld c,$FC : call l2_vl
        ld e,224 : ld c,$FC : call l2_vl
        xor a : ld e,$E0 : call spr_pat
        xor a : ld de,112 : ld b,7 : call v_row
        ld a,8 : ld de,136 : ld b,7 : call v_row
        ld a,16 : ld de,160 : ld b,7 : call v_row
        call l2s_on
        nextreg $1C,2 : nextreg $19,64 : nextreg $19,127 : nextreg $19,0 : nextreg $19,255
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,.blk : call ask2
        nextreg $62,0 : call spr_off : jp l2w_off
.blk:   dw q_v01u, q_v01l, k_u, k_l, .mid
; part 2: the band picture off, the line rows and sprite 31 on
.mid:   nextreg $62,0 : call spr_off
        ld a,(NRSNAP+$14) : call l2w_fill
        ld b,156 : ld c,$FF : call l2_hl
        ld b,158 : ld c,$FF : call l2_hl
        ld a,31 : ld de,$6492 : ld bc,$0000 : call spr_set   ; x 100, y 146, hidden (pattern 0)
        nextreg $15,$01                                       ; SLU: the sprite over Layer 2
        ld hl,.cp2 : ld b,.cp2e-.cp2 : jp cop_load
; the window is written again after every $15 MOVE (V17's claim: such a MOVE resets the clip windows)
.cop:   db $15,$05, $1C,2, $19,64, $19,127, $19,0, $19,255, $80,130
        db $15,$07, $1C,2, $19,64, $19,127, $19,0, $19,255, $80,154
        db $15,$27-$20*VNEG, $1C,2, $19,64, $19,127, $19,0, $19,255, $FF,$FF
.cope:
.cp2:   db $80,157, $34,31
        IF VNEG = 0
        db $38,$80
        ENDIF
        db $80,158, $34,31, $38,0, $FF,$FF
.cp2e:
k_u:    db "u",0
k_l:    db "l",0
q_v01u: db 1
        db "V01 THREE BANDS OF RED SQUARES",0
        db " ",0
        db "1 = top band between the WHITE",0
        db "    lines, middle band all",0
        db "    across, bottom band between",0
        db "    the YELLOW lines",0
        db "2 = as 1 but the bottom band is",0
        db "    between the WHITE lines",0
        db "3 = something else",0,0
        db "book",0,"one-dot",0,"other",0
q_v01l: db 1
        db "V01 A SHORT RED DASH",0
        db " ",0
        db "Look at the red dash and the",0
        db "two thin white lines.",0
        db "1 = the dash fills the gap",0
        db "    between the two lines",0
        db "2 = the dash covers the LOWER",0
        db "    line (a gap above it)",0
        db "3 = something else / no dash",0,0
        db "same-line",0,"late",0,"other",0
