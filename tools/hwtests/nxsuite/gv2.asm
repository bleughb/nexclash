; nxsuite/gv2.asm - V VISUAL, second page: tests built after board run 7 (page 42 after G3's g3b.asm; flag 8
; in the test table). GPL-3.0-or-later. Each shows a picture with its reference drawn beside it and asks
; one 1 / 2 / 3 question (ask, opr.asm). What the harness does not put back is put back here: the Layer 2
; and sprite clip windows (reset values 0-255 / 0-191) and the palette entries written.

; helpers l2w_fill / l2w_row / l2w_on / l2w_off / cop_load: bank 2 (xtb2.asm), shared with gv.asm

; ---------------------------------------------------------------- V18 $64 = 33 / 32: copper line 0 and Layer 2 row 0
; 320 x 256 Layer 2, transparent ($14's index) except row 0 = index 1 and row 4 = index $FF (white, the
; reference). Index 1 is black except while the copper's line 0 runs: WAIT line 0, index 1 = white; WAIT
; line 1, index 1 = black. Row 0 shows white only if copper line 0 is Layer 2 row 0. Asked with $64 = 33,
; then 32: two lines (row 0 and the reference) or one. Keys o33 / o32 = the answers; means=<o33>-<o32>,
; the claim (TECHNIQUES.md:211): two-one. v = the second answer.
@t_v18: ld a,(NRSNAP+$14) : call l2w_fill
        ld bc,$0001 : call l2w_row
        ld bc,$04FF : call l2w_row
        nextreg $43,$10 : nextreg $40,1 : nextreg $41,0
        call l2w_on
        ld hl,.cop : ld b,.cope-.cop : call cop_load
        ld hl,(wp) : ld (.wp),hl
        nextreg $64,33
        ld hl,q_v18 : call ask : jr c,.x
        ld hl,(askp) : ld (.w0),hl
        ld hl,(.wp) : ld (wp),hl : ld hl,k_o33 : call ex_k : ld hl,(askp) : call wstr
        ld hl,(wp) : ld (.wp),hl
        nextreg $64,32
        ld hl,q_v18 : call ask : jr c,.x
        ld hl,(.wp) : ld (wp),hl : ld hl,k_o32 : call ex_k : ld hl,(askp) : call wstr
        ld hl,k_means : call ex_k : ld hl,(.w0) : call wstr
        ld a,'-' : call wchr : ld hl,(askp) : call wstr
.x:     nextreg $62,0
        nextreg $43,$10 : nextreg $40,1 : nextreg $41,1       ; index 1 back to its reset colour
        jp l2w_off
.cop:   db $80,0, $40,1, $41,$FF, $80,1, $40,1, $41,0, $FF,$FF
.cope:
.wp:    dw 0
.w0:    dw 0
k_o33:  db "o33",0
k_o32:  db "o32",0
q_v18:  db 1
        db "V18 THIN WHITE LINES AT THE TOP",0
        db " ",0
        db "Look at the very top edge of the",0
        db "picture (in the border, above",0
        db "the grey). A thin white line is",0
        db "drawn there as a reference.",0
        db " ",0
        db "1 = TWO thin white lines, one",0
        db "    just above the other",0
        db "2 = ONE thin white line",0
        db "3 = no line, or something else",0,0
        db "two",0,"one",0,"other",0

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
