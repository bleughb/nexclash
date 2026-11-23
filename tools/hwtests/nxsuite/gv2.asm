; nxsuite/gv2.asm - V VISUAL, second page: tests built after board run 7 (page 42 after G3's g3b.asm; flag 8
; in the test table). GPL-3.0-or-later. Each shows a picture with its reference drawn beside it and asks
; one 1 / 2 / 3 question (ask, opr.asm). What the harness does not put back is put back here: the Layer 2
; and sprite clip windows (reset values 0-255 / 0-191) and the palette entries written.

; ---------------------------------------------------------------- helpers
; A = index -> 320 x 256 Layer 2 (pages 44-53) filled with it (slot 3, harness page $0B back after)
l2w_fill:
        ld c,a : ld b,44
.p:     ld a,b : nextreg $53,a
        ld hl,$6000 : ld (hl),c : ld de,$6001 : push bc : ld bc,$1FFF : ldir : pop bc
        inc b : ld a,b : cp 54 : jr nz,.p
        nextreg $53,$0B : ret
; B = row, C = index -> that row of the 320 x 256 Layer 2 (column-major: byte x * 256 + y) set to it
l2w_row:
        ld d,44
.p:     ld a,d : nextreg $53,a
        ld h,$60 : ld l,b : ld e,32
.c:     ld (hl),c : inc h : dec e : jr nz,.c
        inc d : ld a,d : cp 54 : jr nz,.p
        nextreg $53,$0B : ret
; 320 x 256 Layer 2 on top (order LSU), pages 44-53, clip 0-159 / 0-255 (wide mode: X in 2-dot units)
l2w_on: nextreg $70,%00010000 : nextreg $12,22
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,159 : nextreg $18,0 : nextreg $18,255
        ld a,(NRSNAP+$15) : and %11100011 : or %00000100 : nextreg $15,a
        ld bc,$123B : ld a,2 : out (c),a : ret
; the Layer 2 clip window back to its reset value 0-255 / 0-191 (the harness does not restore it)
l2w_off:
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,255 : nextreg $18,0 : nextreg $18,191
        ld bc,$123B : xor a : out (c),a : ret
; HL = copper program, B = its length -> loaded at index 0, run in mode %11 (from the start every frame)
cop_load:
        nextreg $62,0 : nextreg $61,0
.l:     ld a,(hl) : nextreg $60,a : inc hl : djnz .l
        nextreg $61,0 : nextreg $62,%11000000 : ret

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
