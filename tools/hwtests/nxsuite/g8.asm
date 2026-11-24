; nxsuite/g8.asm - G8 SPRITES: collision oracle, SP01-SP11 (spec section 3 G8). GPL-3.0-or-later.
; Slot-7 overlay (shares page 43 with G5). Sprites are shown on display lines 80-120 during the tests
; (Y = 32 + line, X 32 = the display's left edge). Patterns by $303B / $5B, attributes by NEXTREG $34-$39
; unless a test says $57. All 128 sprites hidden at start and end ($34 = n, $38 = 0); $15 / $09 / $4B are
; put back by the harness; the sprite clip window ($19, write-only sequence) is set back to the full
; window 0-255 / 0-191 here (the launch value cannot be read). Pattern memory is left written.
; spr_hit: $303B read at line 0 (clears the flags), $303B read again at line 200: bit 0 = collision,
; bit 1 = more sprites on a line than the hardware shows.

G8Y     equ 112                 ; display line 80
; patterns (8-bit slots): 0 = 16x16 all $01, 1 = one dot (0,0), 3 = row 0 only, 5 = SP02, 2 = 4-bit SP06,
; 6 = 4-bit all 0 (SP07)

; ---------------------------------------------------------------- helpers
; A = pattern slot, E = value: all 256 bytes
g8_pfill:
        ld bc,$303B : out (c),a
        ld bc,$005B
.l:     out (c),e : djnz .l
        ret
; A = slot, E = value for the first D bytes, the rest $E3
g8_pfirst:
        ld bc,$303B : out (c),a
        ld bc,$005B
.l:     out (c),e : dec b : dec d : jr nz,.l
        ld a,$E3
.r:     out (c),a : djnz .r
        ret
; all 128 sprites hidden; patterns 0, 1, 3 made
g8_init:
        di
        call g8_hide
        xor a : ld e,$01 : call g8_pfill
        ld a,1 : ld e,$01 : ld d,1 : call g8_pfirst
        ld a,3 : ld e,$01 : ld d,16 : call g8_pfirst
        ld a,(NRSNAP+$15) : and %00011100 : or 1 : nextreg $15,a
        ld a,$E3 : nextreg $4B,a
        ret
g8_hide:
        xor a
.l:     nextreg $34,a : nextreg $38,0 : inc a : cp 128 : jr nz,.l
        ret
; the end of every test: hidden, clip back to the full window
g8_end: call g8_hide
        nextreg $1C,%00000010
        nextreg $19,0 : nextreg $19,255 : nextreg $19,0 : nextreg $19,191
        ret
; A = sprite, HL = X (9 bits), C = pattern, B = attr4 (5-byte record; attr4 0 = a plain 8-bit sprite)
; -> shown at Y = G8Y
g8_put: ld (.y),a
        nextreg $34,a
        ld a,l : nextreg $35,a
        ld a,G8Y : nextreg $36,a
        ld a,h : and 1 : nextreg $37,a
        ld a,c : or $C0 : nextreg $38,a
        ld a,b : nextreg $39,a
        ret
.y:     db 0
; -> A = $303B bits after a frame (bit 0 collision, bit 1 line overflow)
spr_hit:
        call frame_sync
        ld bc,$303B : in a,(c)
        ld a,200 : call sync_lsb
        ld bc,$303B : in a,(c) : and 3
        ret
; A = flags -> the collision bit as 0 / 1
g8_c:   and 1 : ret
g8_fail: ld a,ST_FAIL : ld (R_st),a : ret
; HL = key, A = byte -> " key=<0/1/..>" (decimal)
g8_kd:  ld e,a : ld d,0 : jp ex_kd

; ---------------------------------------------------------------- SP01 collision rules
; one-dot sprites 10 and 11: side by side (X 100 / 101), on the same dot (100 / 100), the same dot with the
; clip window X 200-255, the same dot with $15 bit 0 = 0, and a second $303B read right after a hit.
; alone = sprite 10 by itself first (the control: a flag with one sprite means the other answers say nothing).
; PASS if alone = 0, side = 0, same = 1, second read = 0; clip / off = INFO. (CSpect 4.5.9 sets the flag
; with one sprite alone, JNext 1.3.0 never sets it: neither emulator can check G8.)
t_sp01: call g8_init
        ld a,10 : ld hl,100 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : call g8_c : ld (.r+5),a              ; the control: one sprite alone
        ld a,11 : ld hl,101 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : call g8_c : ld (.r),a
        ld a,11 : ld hl,100 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : call g8_c : ld (.r+1),a
        ld bc,$303B : in a,(c) : and 1 : ld (.r+4),a      ; the second read
        nextreg $1C,%00000010
        nextreg $19,200 : nextreg $19,255 : nextreg $19,0 : nextreg $19,191
        call spr_hit : call g8_c : ld (.r+2),a
        nextreg $1C,%00000010
        nextreg $19,0 : nextreg $19,255 : nextreg $19,0 : nextreg $19,191
        ld a,(NRSNAP+$15) : and %11111110 : nextreg $15,a
        call spr_hit : call g8_c : ld (.r+3),a
        call g8_end
        ld hl,.k : ld ix,.r : ld b,6
.k1:    push bc : push hl : ld a,(ix+0) : call g8_kd : pop hl : ld bc,7 : add hl,bc : inc ix : pop bc
        djnz .k1
        ld a,(.r+1) : call res_hex
        ld a,(.r) : or a : jp nz,g8_fail
        ld a,(.r+1) : cp 1 : jp nz,g8_fail
        ld a,(.r+4) : or a : jp nz,g8_fail
        ld a,(.r+5) : or a : jp nz,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.r:     ds 6
.k:     db "side",0,0,0, "same",0,0,0, "clip",0,0,0, "off",0,0,0,0, "second",0, "alone",0,0

; ---------------------------------------------------------------- SP02 $303B selects pattern and sprite
; pattern 5 all $E3; $303B = 5 and 64 bytes of $01 to $5B (rows 0-3 of pattern 5); $303B = 7 and 5 bytes
; to $57: sprite 7, X 100, Y G8Y, pattern 5 visible; probe sprite 64 (pattern 0) at X 100. PASS if hit.
t_sp02: call g8_init
        ld a,5 : ld e,$01 : ld d,64 : call g8_pfirst
        ld bc,$303B : ld a,7 : out (c),a
        ld hl,.at : ld bc,$0557 : otir
        ld a,64 : ld hl,100 : ld c,0 : ld b,0 : call g8_put
        call spr_hit : push af
        call g8_end
        pop af : and 1 : push af : call res_hex
        pop af : or a : jp z,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.at:    db 100, G8Y, 0, $80|5, 0

; ---------------------------------------------------------------- SP03 NEXTREG $34 and $303B
; $303B = 3; NEXTREG $34,9; 5 bytes to $57 (X 100, visible, pattern 0) + probe 64 at X 100: hit h1; then
; sprite 3 hidden through NEXTREG: hit h2. Choice: 3 (h1, not h2), 9 (h2), none. Then again with $09 bit 4
; = 1 (RMW; the harness puts $09 back). PASS if 3 then 9.
t_sp03: call g8_init
        call .one : ld (.c),a
        ld a,$09 : call rdreg : or $10 : nextreg $09,a
        call g8_hide
        call .one : ld (.c+1),a
        call g8_end
        ld a,(.c) : call .w : push hl : call res_word : pop hl
        ld a,(.c+1) : call .w : push hl : ld hl,k_b4 : call ex_k : pop hl : call wstr
        ld a,(.c) : cp 3 : jp nz,g8_fail
        ld a,(.c+1) : cp 9 : jp nz,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
; -> A = 3 / 9 / 0
.one:   ld bc,$303B : ld a,3 : out (c),a
        nextreg $34,9
        ld hl,.at : ld bc,$0557 : otir
        ld a,64 : ld hl,100 : ld c,0 : ld b,0 : call g8_put
        call spr_hit : and 1 : ld (.h),a
        nextreg $34,3 : nextreg $38,0
        call spr_hit : and 1 : jr z,.n9
        ld a,9 : ret
.n9:    ld a,(.h) : or a : ret z
        ld a,3 : ret
.w:     ld hl,w_s3 : cp 3 : ret z
        ld hl,w_s9 : cp 9 : ret z
        ld hl,w8_none : ret
.at:    db 100, G8Y, 0, $80, 0
.h:     db 0
.c:     ds 2
w_s3:   db "3",0
w_s9:   db "9",0
w8_none: db "none",0
k_b4:   db "bit4",0

; ---------------------------------------------------------------- SP04 4- and 5-byte records on $57
; $303B = 126; to $57: sprite 126 four bytes (X 40, byte 3 bit 6 = 0), 127 five bytes (X 60), 0 five bytes
; (X 80), all one-dot (pattern 1); a one-dot probe (sprite 64) at 40, 60, 80 in turn. PASS if all three hit.
t_sp04: call g8_init
        ld bc,$303B : ld a,126 : out (c),a
        ld hl,.st : ld bc,$0E57 : otir
        ld a,40 : call .pr : ld (.r),a
        ld a,60 : call .pr : ld (.r+1),a
        ld a,80 : call .pr : ld (.r+2),a
        call g8_end
        ld a,(.r) : ld hl,k_x40 : call g8_kd
        ld a,(.r+1) : ld hl,k_x60 : call g8_kd
        ld a,(.r+2) : ld hl,k_x80 : call g8_kd
        ld a,(.r) : ld hl,.r+1 : and (hl) : ld hl,.r+2 : and (hl) : push af : call res_hex
        pop af : or a : jp z,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.pr:    ld l,a : ld h,0 : ld a,64 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : and 1 : ret
.st:    db 40, G8Y, 0, $80|1
        db 60, G8Y, 0, $C0|1, 0
        db 80, G8Y, 0, $C0|1, 0
.r:     ds 3
k_x40:  db "x40",0
k_x60:  db "x60",0
k_x80:  db "x80",0

; ---------------------------------------------------------------- SP05 $75 increments the sprite
; sprites 10 and 11 shown (one dot) at X 0; NEXTREG $34,10; $75,100; $75,150; one-dot probe at 100, then 150.
; PASS if both hit.
t_sp05: call g8_init
        ld a,10 : ld hl,0 : ld c,1 : ld b,0 : call g8_put
        ld a,11 : ld hl,0 : ld c,1 : ld b,0 : call g8_put
        nextreg $34,10 : nextreg $75,100 : nextreg $75,150
        ld hl,100 : call .pr : ld (.r),a
        ld hl,150 : call .pr : ld (.r+1),a
        call g8_end
        ld a,(.r) : ld hl,k_x100 : call g8_kd
        ld a,(.r+1) : ld hl,k_x150 : call g8_kd
        ld a,(.r) : ld hl,.r+1 : and (hl) : push af : call res_hex
        pop af : or a : jp z,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.pr:    ld a,64 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : and 1 : ret
.r:     ds 2
k_x100: db "x100",0
k_x150: db "x150",0

; ---------------------------------------------------------------- SP06 4-bit pattern halves
; 8-bit slot 2 as two 4-bit patterns: bytes 0-127 transparent ($33, $4B = $E3) but row 0 ($11), bytes
; 128-255 transparent but row 15. A 4-bit sprite 10 (pattern 2) with attr4 $80 then $C0, against a one-row
; probe (pattern 3) at row 0 (Y G8Y) and row 15 (Y G8Y + 15). PASS if $80 = first half (row 0 hit, row 15
; not) and $C0 = second half.
t_sp06: call g8_init
        ld bc,$303B : ld a,2 : out (c),a
        ld bc,$085B : ld a,$11 : call .w : ld bc,$785B : ld a,$33 : call .w
        ld bc,$785B : ld a,$33 : call .w : ld bc,$085B : ld a,$11 : call .w
        ld b,$80 : call .one : ld (.r),a
        ld b,$C0 : call .one : ld (.r+1),a
        call g8_end
        ld a,(.r) : ld hl,k_a80 : call ex_kh
        ld a,(.r+1) : ld hl,k_ac0 : call ex_kh
        ld a,(.r) : call res_hex
        ld a,(.r) : cp 1 : jp nz,g8_fail
        ld a,(.r+1) : cp 2 : jp nz,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.w:     out (c),a : djnz .w : ret
; B = attr4 -> A = bit 0 row-0 hit, bit 1 row-15 hit
.one:   ld a,10 : ld hl,100 : ld c,2 : call g8_put
        ld a,64 : ld hl,100 : ld c,3 : ld b,0 : call g8_put
        call spr_hit : and 1 : ld (.h),a
        nextreg $34,64 : nextreg $36,G8Y+15
        call spr_hit : and 1 : add a,a : ld hl,.h : or (hl)
        ret
.h:     db 0
.r:     ds 2
k_a80:  db "a80",0
k_ac0:  db "ac0",0

; ---------------------------------------------------------------- SP07 transparency before the offset
; 8-bit slot 6 all $00 = a 4-bit sprite of index 0; sprite 10 (attr4 $80, pattern 6, palette offset 3) on
; the full probe; $4B = 0. PASS if no collision (index 0 is transparent before the offset is added).
t_sp07: call g8_init
        ld a,6 : ld e,0 : call g8_pfill
        nextreg $4B,0
        ld a,10 : ld hl,100 : ld c,6 : ld b,$80 : call g8_put
        nextreg $34,10 : nextreg $37,$30
        ld a,64 : ld hl,100 : ld c,0 : ld b,0 : call g8_put
        call spr_hit : and 1 : push af
        call g8_end
        pop af : push af : call res_hex
        pop af : or a : jp nz,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret

; ---------------------------------------------------------------- SP08 a relative sprite
; sprites over the border ($15 bit 1); anchor 10: 8-bit, one dot, X 150, attr4 0 (5-byte); sprite 11:
; byte 0 = 10, byte 1 = 0, attr4 $40 (relative), one dot. One-dot probe at 160 (relative) and at 10
; (absolute). INFO choice relative / absolute / both / none.
t_sp08: call g8_init
        ld a,(NRSNAP+$15) : and %00011100 : or 3 : nextreg $15,a
        ld a,10 : ld hl,150 : ld c,1 : ld b,0 : call g8_put
        nextreg $34,11 : nextreg $35,10 : nextreg $36,0 : nextreg $37,0 : nextreg $38,$C1 : nextreg $39,$40
        ld hl,160 : call .pr : ld (.r),a
        ld hl,10 : call .pr : ld (.r+1),a
        call g8_end
        ld a,(.r) : ld hl,k_x160 : call g8_kd
        ld a,(.r+1) : ld hl,k_x10 : call g8_kd
        ld a,(.r+1) : add a,a : ld hl,.r : or (hl)
        ld hl,w8_none : or a : jr z,.w
        ld hl,w_rel : cp 1 : jr z,.w
        ld hl,w_abs : cp 2 : jr z,.w
        ld hl,w_both
.w:     jp res_word
.pr:    ld a,64 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : and 1 : ret
.r:     ds 2
k_x160: db "x160",0
k_x10:  db "x10",0
w_rel:  db "relative",0
w_abs:  db "absolute",0
w_both: db "both",0

; ---------------------------------------------------------------- SP09 X wraps at 512
; over the border; sprite 10 full (pattern 0) at X 500 (X8 set); one-dot probe at X 0, 1, 2, 3, 4.
; PASS if 0-3 hit and 4 does not; v = the five results as bits (expect $0F).
t_sp09: call g8_init
        ld a,(NRSNAP+$15) : and %00011100 : or 3 : nextreg $15,a
        ld a,10 : ld hl,500 : ld c,0 : ld b,0 : call g8_put
        ld e,0 : ld d,0
.l:     push de : ld l,e : ld h,0 : ld a,64 : ld c,1 : ld b,0 : call g8_put
        call spr_hit : pop de : and 1 : jr z,.n
        ld a,1 : ld b,e : inc b
.s:     dec b : jr z,.o
        add a,a : jr .s
.o:     or d : ld d,a
.n:     inc e : ld a,e : cp 5 : jr c,.l
        ld a,d : push af
        call g8_end
        pop af : push af : call res_hex
        pop af : cp $0F : jp nz,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret

; ---------------------------------------------------------------- SP10 sprites per line
; k full sprites (pattern 0) on the same line (X = 2 x i), k = 1..128, X scale 1x / 2x / 4x / 8x (attr4
; bits 4:3); $303B bit 1 after a frame. Then 128 shown, sprites 0..k-1 moved off the line (Y + 40): the
; smallest k for which bit 1 is clear. INFO v = smallest k with the flag at 1x (0 = never); s2 / s4 / s8;
; moved. About 15 s.
t_sp10: call g8_init
        ld b,0 : call .scan : ld (.r),a
        ld b,%00001000 : call .scan : ld (.r+1),a
        ld b,%00010000 : call .scan : ld (.r+2),a
        ld b,%00011000 : call .scan : ld (.r+3),a
        call .mv : ld (.r+4),a
        call g8_end
        ld a,(.r) : ld l,a : ld h,0 : call res_int : ld hl,u_count : call res_unit
        ld a,(.r+1) : ld hl,k_s2 : call g8_kd
        ld a,(.r+2) : ld hl,k_s4 : call g8_kd
        ld a,(.r+3) : ld hl,k_s8 : call g8_kd
        ld a,(.r+4) : ld hl,k8_mv : jp g8_kd
; B = attr4 (scale) -> A = the smallest k (1..128) with bit 1 set, 0 none (board run 5 swept from 60:
; s2 / s4 / s8 = 60 only said "below 60")
.scan:  ld a,b : ld (.a4),a
        ld a,1 : ld (.k),a
.k1:    call g8_hide
        ld a,(.k) : ld e,a : xor a
.p:     push af : push de
        ld l,a : ld h,0 : add hl,hl
        ld c,0 : push af : ld a,(.a4) : ld b,a : pop af       ; attr4: the X scale
        call g8_put
        pop de : pop af : inc a : cp e : jr nz,.p
        call spr_hit : and 2 : jr z,.nx
        ld a,(.k) : ret
.nx:    ld a,(.k) : inc a : ld (.k),a : cp 129 : jr c,.k1
        xor a : ret
; -> A = the smallest k (0..128) for which, with 128 shown and 0..k-1 moved off the line, bit 1 is clear
.mv:    xor a : ld (.k),a
.m1:    call g8_hide
        xor a
.q:     push af
        ld l,a : ld h,0 : add hl,hl
        ld c,0 : ld b,0 : call g8_put
        pop af : push af : ld hl,.k : cp (hl) : jr nc,.on    ; sprites 0..k-1 off the line
        nextreg $34,a : nextreg $36,G8Y+40
.on:    pop af : inc a : cp 128 : jr nz,.q
        call spr_hit : and 2 : jr nz,.mn
        ld a,(.k) : ret
.mn:    ld a,(.k) : inc a : ld (.k),a : cp 129 : jr c,.m1
        ld a,$FF : ret
.a4:    db 0
.k:     db 0
.r:     ds 5
k_s2:   db "s2",0
k_s4:   db "s4",0
k_s8:   db "s8",0
k8_mv:   db "moved",0

; ---------------------------------------------------------------- SP11 ports by their low byte
; pattern 7 by OUTI with B = $13 (port $125B: OUTI decrements B first), 256 bytes of $01 (pattern 7 =
; full); attributes of sprite 12 by OUTI with B = $35 (port $3457) after $303B = 12; full probe at X 100.
; PASS if hit.
t_sp11: call g8_init
        ld bc,$303B : ld a,7 : out (c),a
        ld a,$E3 : ld hl,G8B : ld (hl),$01
        ld hl,G8B : ld c,$5B : ld d,0
.p:     ld b,$13 : ld (hl),$01 : outi : dec hl : dec d : jr nz,.p
        ld bc,$303B : ld a,12 : out (c),a
        ld hl,.at : ld c,$57 : ld d,4
.a:     ld b,$35 : outi : dec d : jr nz,.a
        ld a,64 : ld hl,100 : ld c,0 : ld b,0 : call g8_put
        call spr_hit : and 1 : push af
        call g8_end
        pop af : push af : call res_hex
        pop af : or a : jp z,g8_fail
        ld a,ST_PASS : ld (R_st),a : ret
.at:    db 100, G8Y, 0, $80|7
G8B:    db 0
