; nxsuite/gv7.asm - V VISUAL on page 40 after G4 (OVLX_1, with gv3.asm; below Z04's $F000): V08, the 640 x 256
; Layer 2 one-dot check. GPL-3.0-or-later. Uses gv3.asm's tilemap helpers (same page). VNEG = 1: the white
; blocks are drawn one dot to the right (a nibble shift), so screen 1 shows red on the left edges.

; ---------------------------------------------------------------- V08 640 x 256 Layer 2: dots against the tilemap
; Book ch 14 (report D-N3, N4): 640 x 256 is column-major like 320 x 256, one byte = two 4-bit dots (high
; nibble on the left), and X scrolls 0-319 in steps of 2 dots. Layer 2 (on top, order LSU) holds white blocks
; 16 dots wide (8 byte columns of $11) with 16-dot transparent gaps in the border strips (rows 0-31 and
; 224-255, outside the question). Under it a 40 x 32 tilemap (7 MHz dots: 2 Layer 2 dots each) has a red
; tile exactly under every block and a blue one under every gap. Exactly in line: white and blue only. One dot
; out: a one-dot red line on one side of every block. Screen 1: no scroll (do the two layers line up at all?).
; Screen 2: Layer 2 X scroll 1 and tilemap X scroll 1 (one 7 MHz dot = 2 dots): if a 640 scroll step is 2 dots
; (the claim) both move alike and nothing changes; a 1-dot step leaves red on one side. Keys s0 / s1.
@t_v08: ld a,$30 : nextreg $43,a                                  ; tilemap palette 0
        ld a,1 : ld e,$E0 : call pal_set : ld a,2 : ld e,$03 : call pal_set
        ld a,$10 : nextreg $43,a                                  ; Layer 2 palette 0
        ld a,(NRSNAP+$14) : ld e,a : xor a : call pal_set  ; nibble 0 = the transparent colour
        ld a,1 : ld e,$FF : call pal_set                          ; nibble 1 = white
        xor a : call l2w_fill
        ld d,44
.p:     ld a,d : nextreg $53,a
        ld h,$60
.c:     ld a,h : and 15 : ld c,a : ld b,0 : push hl : ld hl,v8pat : add hl,bc : ld c,(hl) : pop hl
        ld l,0 : ld b,32
.t:     ld (hl),c : inc l : djnz .t
        ld l,224 : ld b,32
.b:     ld (hl),c : inc l : djnz .b
        inc h : ld a,h : cp $80 : jr nz,.c
        inc d : ld a,d : cp 54 : jr nz,.p
        nextreg $53,$0B
        call tm_pg
        ld e,0 : call tm_clr
        xor a : ld e,$FF : ld b,32 : call tm_def                  ; tile 0: index 15 = $4C, transparent
        ld a,1 : ld e,$11 : ld b,32 : call tm_def                 ; tile 1 red
        ld a,2 : ld e,$22 : ld b,32 : call tm_def                 ; tile 2 blue
        ld hl,TMAP : call .rows
        ld hl,TMAP + 28 * 80 : call .rows
        call tm_end
        ld a,$81 : call tm_on                                     ; on, over the ULA
        call l2w_on : nextreg $70,%00100000                       ; 640 x 256, palette offset 0
        ld hl,.blk : call ask2
        call pal_back
        jp l2w_off
.blk:   dw q_v08, q_v08b, k_v8a, k_v8b, .mid
.mid:   nextreg $71,0 : nextreg $16,1 : nextreg $2F,0 : nextreg $30,1
        ret
; HL = map row start -> four rows of 40 entries: red, blue, red, ... (tile, attribute 0)
.rows:  ld b,80
.r:     ld (hl),1 : inc hl : ld (hl),0 : inc hl : ld (hl),2 : inc hl : ld (hl),0 : inc hl : djnz .r
        ret
v8pat:  db $11 - VNEG * $10, $11, $11, $11, $11, $11, $11, $11, VNEG * $10, 0, 0, 0, 0, 0, 0, 0
k_v8a:  db "s0",0
k_v8b:  db "s1",0
q_v08:  db 2
        db "V08 640-WIDE EDGES (1 of 2)",0
        db " ",0
        db "WHITE blocks on BLUE in the",0
        db "top and bottom border strips.",0
        db "1 = no red at any block edge",0
        db "2 = a thin RED line on the",0
        db "    LEFT edge of the blocks",0
        db "3 = thin RED on the RIGHT edges",0
        db "4 = something else",0,0
        db "none",0,"left",0,"right",0,"other",0
q_v08b: db 2
        db "V08 SCROLLED ONE STEP (2 of 2)",0
        db " ",0
        db "WHITE blocks on BLUE in the",0
        db "top and bottom border strips.",0
        db "1 = no red at any block edge",0
        db "2 = a thin RED line on the",0
        db "    LEFT edge of the blocks",0
        db "3 = thin RED on the RIGHT edges",0
        db "4 = something else",0,0
        db "none",0,"left",0,"right",0,"other",0
