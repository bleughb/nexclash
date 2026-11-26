; nxsuite/vh2.asm - V group helpers shared by the overlay pages (bank 2, after txt2.asm). GPL-3.0-or-later.

; A = pattern number (0-63), E = colour index -> an 8-bit 16 x 16 pattern of that colour
spr_pat:
        ld bc,$303B : out (c),a
        ld bc,$005B : ld a,e
.l:     out (c),a : djnz .l
        ret
; A = sprite, D = display x (0-223), E = display y (0-191), C = attribute 3 ($80 visible + pattern),
; B = attribute 2 (mirror / rotate bits 3-1; palette offset 0); no fifth byte
spr_set:
        nextreg $34,a
        ld a,d : add a,32 : nextreg $35,a
        ld a,e : add a,32 : nextreg $36,a
        ld a,b : nextreg $37,a
        ld a,c : nextreg $38,a
        ret
; sprites 0-31 hidden, the sprite clip window back to its reset value 0-255 / 0-191
spr_off:
        xor a
.l:     nextreg $34,a : nextreg $38,0 : inc a : cp 32 : jr nz,.l
        nextreg $1C,2 : nextreg $19,0 : nextreg $19,255 : nextreg $19,0 : nextreg $19,191
        ret
; 256 x 192 Layer 2 on top (order LSU), pages 44-49, clip 0-255 / 0-191 (fill it first with l2w_fill)
l2s_on: call l2w_on : nextreg $70,0
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,255 : nextreg $18,0 : nextreg $18,191
        ret
; 256 x 192 Layer 2: B = y, C = colour -> a horizontal line, x 0-255
l2_hl:  ld a,b : rlca : rlca : rlca : and 7 : add a,44 : nextreg $53,a
        ld a,b : and 31 : add a,$60 : ld h,a : ld l,0
.x:     ld (hl),c : inc l : jr nz,.x
        nextreg $53,$0B : ret
; after a group's good write: its line count kept for the group screens (g_show) and shown now
g_saved:
        ld hl,(txtlines) : ld de,(linebase) : add hl,de : ld (savedl),hl : jp g_show
savedl: dw 0
; HL -> block: dw q1, q2, key1, key2, mid. Asks q1; calls mid (it changes the picture); asks q2. -> keys
; <key1>=<word1> <key2>=<word2> means=<word1>-<word2>, v = word2; carry: S pressed (PENDING-OPERATOR)
ask2:   ld de,.b : ld bc,10 : ldir
        ld hl,(wp) : ld (.wp),hl
        ld hl,(.b) : call ask : ret c
        ld hl,(askp) : ld (.w0),hl
        ld hl,(.wp) : ld (wp),hl : ld hl,(.b+4) : call ex_k : ld hl,(askp) : call wstr
        ld hl,(wp) : ld (.wp),hl
        ld hl,(.b+8) : call .jp
        ld hl,(.b+2) : call ask : ret c
        ld hl,(.wp) : ld (wp),hl : ld hl,(.b+6) : call ex_k : ld hl,(askp) : call wstr
        ld hl,k_means : call ex_k : ld hl,(.w0) : call wstr
        ld a,'-' : call wchr : ld hl,(askp) : jp wstr
.jp:    jp (hl)
.b:     ds 10
.wp:    dw 0
.w0:    dw 0
; the palette $43 selects: A = index, E = colour (8-bit, $41). The old colour is kept; pal_back puts all back.
PALBUF  equ $63C0                   ; bank 5, 64 bytes below the NextReg snapshot (G2's window, not used by V)
pal_set:
        push af : nextreg $40,a
        ld a,$43 : call rdreg : ld hl,(pal_p) : ld (hl),a : inc hl
        pop af : ld (hl),a : inc hl
        ld a,$41 : call rdreg : ld (hl),a : inc hl : ld (pal_p),hl
        ld a,e : nextreg $41,a : ret
pal_back:
        ld hl,(pal_p)
.l:     ld a,l : cp low PALBUF : jr z,.x
        dec hl : ld c,(hl) : dec hl : ld b,(hl) : dec hl : ld a,(hl)
        nextreg $43,a : ld a,b : nextreg $40,a : ld a,c : nextreg $41,a : jr .l
.x:     ld (pal_p),hl : ret
pal_p:  dw PALBUF
