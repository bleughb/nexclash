; nxsuite/g9.asm - G9 MEM: paging, alt ROM, DivMMC automap off (spec section 3 G9). GPL-3.0-or-later.
; In bank 2 (slot 4): the tests remap slots 0-3 and 6-7, so code, stack and data stay in slots 4/5. DI
; throughout. Every test ends with g9_rest: OUT 1FFD = $04, OUT 7FFD = $10, NextReg $08 bit 7 = 1 (unlock),
; MMU 0-7 = the launch values (copied out of the snapshot first, since bank 5 may be paged out), then
; the harness may be called again. Deviations: M01 maps slots 0-3 and 6-7 to pages 40-43 / 46-47 (slots 4/5
; hold the code); M05 restores the byte it wrote and looks for an alias in all suite pages 32-63; M03 writes only its six
; marker bytes into the alt ROM (saved first and written back) instead of copying page 55; M06 uses DMA scratch pages 36 / 37 (40-42 hold code).

; copy the launch MMU values out of the snapshot (bank 5) into bank 2
g9_save:
        di
        ld hl,NRSNAP+$50 : ld de,g9m : ld bc,8 : ldir : ret
g9_rest:
        ld a,$08 : call rdreg : or $80 : nextreg $08,a
        ld bc,$1FFD : ld a,$04 : out (c),a
        ld bc,$7FFD : ld a,$10 : out (c),a
        ld hl,g9m : ld b,8 : ld e,$50
.l:     ld a,(hl) : push bc : ld bc,$243B : out (c),e : inc b : out (c),a : pop bc
        inc hl : inc e : djnz .l
        ret
g9m:    ds 8
; B = count, E = first MMU register -> g9r (B bytes)
g9_mmu: ld hl,g9r
.l:     ld a,e : call rdreg : ld (hl),a : inc hl : inc e : djnz .l
        ret
g9r:    ds 8
g9_fail: ld a,ST_FAIL : ld (R_st),a : ret
; HL = key, A = MMU slot -> " key=$hh" (from g9r)
g9_k:   push hl : ld hl,g9r : add hl,a : ld a,(hl) : pop hl : jp ex_kh
; HL = byte list -> compare 8 bytes with g9r; Z if equal ($FF in the list = do not care)
g9_cmp: ld de,g9r : ld b,8
.l:     ld a,(hl) : cp $FF : jr z,.n
        ld a,(de) : cp (hl) : ret nz
.n:     inc hl : inc de : djnz .l
        xor a : ret

; ---------------------------------------------------------------- M01 7FFD unlocked remap
; MMU 0-3 / 6-7 = 40-43 / 46-47; OUT 7FFD = $13 (bank 3, ROM bit 4 = 1); read MMU 0-7; then NEXTREG $57,47;
; read MMU 7. PASS if 0/1 = $FF, 6/7 = 6/7, 2-5 unchanged, and MMU 7 = 47 after the NEXTREG.
t_m01:  call g9_save
        nextreg $50,40 : nextreg $51,41 : nextreg $52,42 : nextreg $53,43
        nextreg $56,46 : nextreg $57,47
        ld bc,$7FFD : ld a,$13 : out (c),a
        ld b,8 : ld e,$50 : call g9_mmu
        nextreg $57,47
        ld a,$57 : call rdreg : ld (.l7),a
        call g9_rest
        ld a,(g9m+4) : ld (.e+4),a : ld a,(g9m+5) : ld (.e+5),a
        ld hl,.e : call g9_cmp : push af
        ld hl,.k : call g9_keys
        ld a,(.l7) : ld hl,k_m7 : call ex_kh
        ld a,(g9r+6) : call res_hex
        pop af : jp nz,g9_fail
        ld a,(.l7) : cp 47 : jp nz,g9_fail
        ld a,ST_PASS : ld (R_st),a : ret
.e:     db $FF,$FF,42,43,0,0,6,7
.l7:    db 0
.k:     db "m0",0,"m1",0,"m2",0,"m3",0,"m4",0,"m5",0,"m6",0,"m7",0
k_m7:   db "after57",0
; HL = 8 zero-ended keys -> " key=$hh" for g9r[0..7]
g9_keys:
        xor a
.l:     push af : push hl : call g9_k : pop hl
.s:     ld a,(hl) : inc hl : or a : jr nz,.s
        pop af : inc a : cp 8 : jr c,.l
        ret

; ---------------------------------------------------------------- M02 7FFD locked
; OUT 7FFD = $30 (lock, bank 0); OUT 7FFD = $13 (should be ignored); MMU 0-7
; read; NEXTREG $08 bit 7 = 0 (RMW) -> $08 read (bit 7: 0 = still locked); OUT 7FFD = $13 again, MMU 6
; read; NEXTREG $08 bit 7 = 1 -> $08 read; OUT 7FFD = $13, MMU 6 read (unlocked: 6).
; PASS if locked writes left MMU 6/7 = 0/1, the 0 write kept the lock, and the 1 write unlocked.
t_m02:  call g9_save
        ld bc,$7FFD : ld a,$30 : out (c),a
        ld a,$13 : out (c),a
        ld b,8 : ld e,$50 : call g9_mmu
        ld a,$08 : call rdreg : and $7F : nextreg $08,a
        ld a,$08 : call rdreg : ld (.r),a
        ld bc,$7FFD : ld a,$13 : out (c),a
        ld a,$56 : call rdreg : ld (.r+1),a
        ld a,$08 : call rdreg : or $80 : nextreg $08,a
        ld a,$08 : call rdreg : ld (.r+2),a
        ld bc,$7FFD : ld a,$13 : out (c),a
        ld a,$56 : call rdreg : ld (.r+3),a
        call g9_rest
        ld hl,M01k : call g9_keys
        ld a,(.r) : ld hl,.k0 : call ex_kh
        ld a,(.r+1) : ld hl,.k1 : call ex_kh
        ld a,(.r+2) : ld hl,.k2 : call ex_kh
        ld a,(.r+3) : ld hl,.k3 : call ex_kh
        ld a,(g9r+6) : call res_hex
        ld a,(g9r+6) : or a : jp nz,g9_fail
        ld a,(g9r+7) : cp 1 : jp nz,g9_fail
        ld a,(.r+1) : or a : jp nz,g9_fail             ; still locked after the 0 write
        ld a,(.r+3) : cp 6 : jp nz,g9_fail             ; unlocked after the 1 write
        ld a,ST_PASS : ld (R_st),a : ret
.r:     ds 4
.k0:    db "nr08w0",0
.k1:    db "m6w0",0
.k2:    db "nr08w1",0
.k3:    db "m6w1",0
M01k equ t_m01.k

; ---------------------------------------------------------------- M03 automap off + alt ROM
; $0A bit 4 = 0 (RMW). Alt ROM: $8C = $80 first to save the image bytes at $0038 / $3D00 (3 each), $8C =
; $C0 (write mode) to put LD A,$38 : RET at $0038 and LD A,$3D : RET at $3D00, $8C = $80 (read-only):
; CALL $3D00 and RST $38 (DI) -> A; a write to $0038 (should be ignored) and the byte read back; $0038
; read with 7FFD bit 4 = 0 (the other image). The saved bytes are written back the same way.
; PASS if both markers came back (no automap); altw = the byte after the write ($3E = ignored).
t_m03:  call g9_save
        ld a,$0A : call rdreg : and $EF : nextreg $0A,a
        nextreg $8C,$80
        ld hl,$0038 : ld de,.sv : ld bc,3 : ldir
        ld hl,$3D00 : ld bc,3 : ldir
        nextreg $8C,$C0
        ld hl,.p38 : ld de,$0038 : ld bc,3 : ldir
        ld hl,.p3d : ld de,$3D00 : ld bc,3 : ldir
        nextreg $8C,$80
        xor a : call $3D00 : ld (.r),a
        xor a : rst $38 : ld (.r+1),a
        ld a,$AA : ld ($0038),a : ld a,($0038) : ld (.r+2),a
        ld bc,$7FFD : ld a,$00 : out (c),a
        ld a,($0038) : ld (.r+3),a
        ld a,$10 : out (c),a
        nextreg $8C,$C0
        ld hl,.sv : ld de,$0038 : ld bc,3 : ldir
        ld de,$3D00 : ld bc,3 : ldir
        ld a,(NRSNAP+$8C) : nextreg $8C,a
        ld a,(NRSNAP+$0A) : nextreg $0A,a
        call g9_rest
        ld a,(.r) : call res_hex
        ld a,(.r) : ld hl,.k0 : call ex_kh
        ld a,(.r+1) : ld hl,.k1 : call ex_kh
        ld a,(.r+2) : ld hl,.k2 : call ex_kh
        ld a,(.r+3) : ld hl,.k3 : call ex_kh
        ld a,(.r) : cp $3D : jp nz,g9_fail
        ld a,(.r+1) : cp $38 : jp nz,g9_fail
        ld a,ST_PASS : ld (R_st),a : ret
.p38:   ld a,$38 : ret
.p3d:   ld a,$3D : ret
.sv:    ds 6
.r:     ds 4
.k0:    db "a3d00",0
.k1:    db "arst38",0
.k2:    db "altw",0
.k3:    db "other38",0

; ---------------------------------------------------------------- M04 Layer 2 write map over the alt ROM
; alt ROM on ($8C = $80, image as found); page 44 offset $1000 = 0; $12 = 22; $123B = $01 (write map,
; segment 0); read $1000 before; LD ($1000),$5A; read $1000 after; $123B = 0; page 44 at slot 6: offset
; $1000. PASS if the read stayed the ROM byte and page 44 got $5A.
t_m04:  call g9_save
        nextreg $56,44 : xor a : ld ($D000),a
        ld a,(g9m+6) : nextreg $56,a
        nextreg $8C,$80
        nextreg $12,22
        ld a,($1000) : ld (.r),a
        ld bc,$123B : ld a,$01 : out (c),a
        ld a,$5A : ld ($1000),a
        ld a,($1000) : ld (.r+1),a
        xor a : out (c),a
        nextreg $56,44 : ld a,($D000) : ld (.r+2),a
        ld a,(NRSNAP+$8C) : nextreg $8C,a
        ld a,(NRSNAP+$12) : nextreg $12,a
        call g9_rest
        ld a,(.r+2) : call res_hex
        ld a,(.r) : ld hl,.k0 : call ex_kh
        ld a,(.r+1) : ld hl,.k1 : call ex_kh
        ld a,(.r) : ld hl,.r+1 : cp (hl) : jp nz,g9_fail
        ld a,(.r+2) : cp $5A : jp nz,g9_fail
        ld a,ST_PASS : ld (R_st),a : ret
.r:     ds 3
.k0:    db "before",0
.k1:    db "after",0

; ---------------------------------------------------------------- M05 pages above the RAM
; offset-0 bytes of suite pages 32-63 saved; page $E0 in slot 6: read $C000 (r0), write $5A, read (v); the
; suite pages compared again (alias = the first page that changed, $FF none); r0 written back through the
; same mapping. INFO v = the read after the write.
t_m05:  call g9_save
        ld de,.b0 : call .scan
        nextreg $56,$E0
        ld a,($C000) : ld (.r),a
        ld a,$5A : ld ($C000),a
        ld a,($C000) : ld (.r+1),a
        ld de,.b1 : call .scan
        nextreg $56,$E0 : ld a,(.r) : ld ($C000),a
        call g9_rest
        ld a,$FF : ld (.al),a
        ld hl,.b0 : ld de,.b1 : ld bc,32*256+32
.c:     ld a,(de) : cp (hl) : jr z,.n
        ld a,c : ld (.al),a : jr .o
.n:     inc hl : inc de : inc c : djnz .c
.o:     ld a,(.r+1) : call res_hex
        ld a,(.r) : ld hl,.k0 : call ex_kh
        ld a,(.al) : ld hl,.k1 : jp ex_kh
; DE = 32-byte buffer <- offset 0 of pages 32-63 (through slot 6)
.scan:  ld b,32 : ld c,32
.s:     ld a,c : nextreg $56,a : ld a,($C000) : ld (de),a
        inc de : inc c : djnz .s
        ret
.r:     ds 2
.al:    db 0
.b0:    ds 32
.b1:    ds 32
.k0:    db "r0",0
.k1:    db "alias",0

; ---------------------------------------------------------------- M06 a fetch across $FFFF
; slot 0 = page 36 with $0000 = $05 (the JR offset) and $0006 = LD A,$77 : RET; slot 7 = page 37 with $FFFF
; = $18 (JR); CALL $FFFF (DI). PASS if A = $77.
t_m06:  call g9_save
        nextreg $50,36 : nextreg $57,37
        ld a,$05 : ld ($0000),a
        ld hl,.p : ld de,$0006 : ld bc,3 : ldir
        ld a,$18 : ld ($FFFF),a
        xor a : call $FFFF : ld (.r),a
        call g9_rest
        ld a,(.r) : call res_hex
        ld a,(.r) : cp $77 : jp nz,g9_fail
        ld a,ST_PASS : ld (R_st),a : ret
.p:     ld a,$77 : ret
.r:     db 0
