; nxsuite/gxt.asm - XT TIMING, opt-in (spec section 3 X-T, step 5). GPL-3.0-or-later.
; Slot-7 overlay after G7 on page 61. Never in RUN ALL: only by the menu key T, each test after its hazard
; screen (Y). NextReg $03 (machine timing) survives a soft reset, so before a test writes it the start
; value goes into the progress record (PRG_T03) with PRG_FLAGS bit 1 set and the record is written; the
; test puts the timing back and clears the bit. A hang leaves the bit set: the next start puts $03 back
; from the record before anything is measured (prg_read2, xtb2.asm) and the test is marked HANG-GUARD.
; $03 is written as the z80tonex tail does (proven on boards): bit 7 (allow the change) + timing in bits
; 6:4 (1 48K, 2 128K, 3 +3, 4 Pentagon) + bits 2:0 = 011 (never 111: config mode). The ULA interrupt
; line is read from NextReg $C8 bit 0 (set by the ULA interrupt even with interrupts off, book ch 4;
; board I07 pdi=$01), polled at 28 MHz: no interrupt is taken. XT4 / XT5 page memory: their code is in
; bank 2 (xtb2.asm), since OUT $7FFD also moves slots 6 / 7.

; ---------------------------------------------------------------- helpers
; A = timing 1-4 -> NextReg $03 written, 3 frames waited (the change is taken at a frame end)
xt_set: rlca : rlca : rlca : rlca : or $83 : nextreg $03,a
xt_w3:  ld b,3
.f:     push bc : call frame_sync : pop bc : djnz .f
        ret
; the start timing back (NRSNAP+$03, put right by prg_read2 after a hang)
xt_back:
        ld a,(NRSNAP+$03) : and $70 : or $83 : nextreg $03,a
        jr xt_w3
; the start value into the progress record, PRG_FLAGS bit 1 set, record written (before $03 is touched)
xt_arm: ld a,(NRSNAP+$03) : ld (PRGB+PRG_T03),a
        ld hl,PRGB+PRG_FLAGS : set 1,(hl)
        jp prg_write
; bit 1 cleared (the harness writes the record after the test)
xt_dis: ld hl,PRGB+PRG_FLAGS : res 1,(hl) : ret
; A = timing 1-4 -> HL = the 50 Hz frame length the claims give (VGA: 312 / 311 / 311 / 320). No HDMI case:
; nothing the program can read says which frame the board sends (board run 7: HDMI cable, $11 = $00, VGA
; lengths measured); the header geom= and the V19 cable answer say which frame a run measured.
xt_exp: ld hl,312 : cp 1 : ret z
        ld hl,320 : cp 4 : ret z
        ld hl,311 : ret
; -> HL = lines per frame (largest line over 4 frames + 1; 0 = no wrap seen)
xt_len: ld a,4 : call flines_n
        ld a,h : or l : ret z
        inc hl : ret
; -> HL = the raster line at which NextReg $C8 bit 0 (ULA interrupt status) was first seen set after
; line 0 ($FFFF = not within ~5 frames). 28 MHz; the ULA interrupt enabled ($C4 bit 0, restored after).
xt_ula: nextreg $07,3
        ld a,(NRSNAP+$C4) : or 1 : nextreg $C4,a
        call frame_sync
        nextreg $C8,$FF
        ld bc,$243B : ld a,$C8 : out (c),a : inc b
        ld de,0
.w:     in a,(c) : rra : jr c,.s
        dec de : ld a,d : or e : jr nz,.w
        ld hl,$FFFF : jr .e
.s:     call line
.e:     push hl : nextreg $C8,$FF : ld a,(spd0) : nextreg $07,a : pop hl
        ret
; -> HL = the largest line until the line number falls (0 = no fall within the guard), (xt_jl) = the
; line read just after the fall
xt_jl:  dw 0
xt_wmax:
        call line : ld (.p),hl : ld (.m),hl
        ld de,0
.l:     push de : call line : pop de
        ld bc,(.p) : ld (.p),hl : or a : sbc hl,bc : jr c,.w
        add hl,bc
        ld bc,(.m) : push hl : or a : sbc hl,bc : pop hl : jr c,.n
        ld (.m),hl
.n:     dec de : ld a,d : or e : jr nz,.l
        ld hl,0 : ret
.w:     add hl,bc : ld (xt_jl),hl : ld hl,(.m) : ret
.p:     dw 0
.m:     dw 0

; ---------------------------------------------------------------- XT1 frame length and ULA interrupt per timing
; For timings 1-4 (48K, 128K, +3, Pentagon): $03 written, 3 frames, lines per frame (4 frames) and the line
; of the ULA interrupt ($C8 polled); $03 read back. Keys l<t> / i<t> / r<t> (t = 1-4). v = how many of the
; four frame lengths are the claims' (VGA 312 / 311 / 311 / 320); PASS if all four.
t_xt1:  call xt_arm
        ld a,1 : ld (.t),a : xor a : ld (.ok),a
.l:     ld a,(.t) : call xt_set
        ld a,$03 : call rdreg : ld (.r),a
        call xt_len : ld (.n),hl
        call xt_ula : ld (.i),hl
        ld a,(.t) : call xt_exp : ld de,(.n) : or a : sbc hl,de : jr nz,.k
        ld hl,.ok : inc (hl)
.k:     ld a,'l' : call .key : ld de,(.n) : call wdec1
        ld a,'i' : call .key : ld de,(.i) : call wdec1
        ld a,'r' : call .key : ld a,(.r) : call wdhex2
        ld a,(.t) : inc a : ld (.t),a : cp 5 : jr c,.l
        call xt_back : call xt_dis
        ld a,(.ok) : ld l,a : ld h,0 : call res_int
        ld hl,u_count : call res_unit
        ld a,(.ok) : cp 4 : ld a,ST_PASS : jr z,.s
        ld a,ST_FAIL
.s:     ld (R_st),a : ret
; A = key letter -> " <letter><t>="
.key:   push af : ld a,' ' : call wchr : pop af : call wchr
        ld a,(.t) : add a,'0' : call wchr : ld a,'=' : jp wchr
.t:     db 0
.ok:    db 0
.r:     db 0
.n:     dw 0
.i:     dw 0
; DE = number -> written
wdec1:  ex de,hl : jp wdec

; ---------------------------------------------------------------- XT2 a timing change waits for the frame end
; From the start timing s to Pentagon (or to 48K when s is Pentagon): $03 written at line 100, then the
; lengths of that frame (v = f1, from line 100 to its wrap; j1 = the line read just after that fall), and
; of the next two (f2, f3); timing put back.
; PASS if f1 = the start length and f2 = the new one. Board run 7 (N-Go board, an Issue 2-compatible
; clone, core 3.03.00, 311 -> 320): f1 = 320, j1 = 0, f2 = 7, f3 = 320 - the frame being drawn ran on to the new length at once, then a 7-line frame:
; not held to the frame end (FAIL).
t_xt2:  call xt_arm
        ld a,(NRSNAP+$03) : rrca : rrca : rrca : rrca : and 7 : ld (.s),a
        ld b,4 : cp 4 : jr nz,.g
        ld b,1
.g:     ld a,b : ld (.d),a
        ld a,(.s) : call xt_exp : ld (.e0),hl
        ld a,(.d) : call xt_exp : ld (.e1),hl
        call frame_sync : ld a,100 : call sync_lsb
        ld a,(.d) : rlca : rlca : rlca : rlca : or $83 : nextreg $03,a
        call xt_wmax : ld (.f1),hl
        ld hl,(xt_jl) : ld (.j1),hl
        call xt_wmax : ld (.f2),hl
        call xt_wmax : ld (.f3),hl
        call xt_back : call xt_dis
        ld hl,(.f1) : inc hl : ld (.f1),hl : call res_int
        ld hl,u_lines : call res_unit
        ld hl,(.f2) : inc hl : ld (.f2),hl : ex de,hl : ld hl,xk_f2 : call ex_kd
        ld hl,(.f3) : inc hl : ex de,hl : ld hl,xk_f3 : call ex_kd
        ld de,(.j1) : ld hl,xk_j1 : call ex_kd
        ld de,(.e0) : ld hl,xk_e0 : call ex_kd
        ld de,(.e1) : ld hl,xk_e1 : call ex_kd
        ld a,(.d) : ld l,a : ld h,0 : ex de,hl : ld hl,xk_to : call ex_kd
        ld hl,(.f1) : ld de,(.e0) : or a : sbc hl,de : jr nz,.f
        ld hl,(.f2) : ld de,(.e1) : or a : sbc hl,de : jr nz,.f
        ld a,ST_PASS : ld (R_st),a : ret
.f:     ld a,ST_FAIL : ld (R_st),a : ret
.s:     db 0
.d:     db 0
.e0:    dw 0
.e1:    dw 0
.f1:    dw 0
.f2:    dw 0
.f3:    dw 0
.j1:    dw 0
xk_j1:  db "j1",0
xk_f2:   db "f2",0
xk_f3:   db "f3",0
xk_e0:   db "exp0",0
xk_e1:   db "exp1",0
xk_to:   db "to",0

; ---------------------------------------------------------------- XT3 which banks are contended, per timing
; $08 bit 6 = 0 (contention not switched off; read-modify-write, put back by the harness). Per timing 1-4:
; 1024 x LD A,(HL) from $C000 with slot 6 = the bank's first page (banks 0 1 3 4 5 7 = pages 0 2 6 8 10 14;
; read only), at 3.5 MHz from line 8 (inside the picture, where contention acts); raster lines taken.
; Extra lines against bank 0 for banks 1 3 4 5 7 -> key c<t>=a,b,c,d,e (one line = 228 T, so one line
; over 1024 reads is ~0.22 T a read). A bank counts as contended at 3 or more lines (~0.7 T a read).
; v = "book" if 128K = 1 3 5 7, +3 = 4 5 7, Pentagon = none (of the banks tried); else "other". 48K: shown,
; not compared (the book gives no list). INFO (a choice).
t_xt3:  call xt_arm
        ld a,$08 : call rdreg : ld hl,xk_r08 : call ex_kh
        ld a,$08 : call rdreg : and $3F : nextreg $08,a       ; bit 6 = 0, bit 7 written 0 (no effect)
        ld a,1 : ld (.t),a : ld a,1 : ld (.bk),a
.l:     ld a,(.t) : call xt_set
        ld a,' ' : call wchr : ld a,'c' : call wchr : ld a,(.t) : add a,'0' : call wchr : ld a,'=' : call wchr
        xor a : call .one : ld (.r0),hl
        ld ix,.pg : ld c,0                                  ; C = the mask of contended banks (bit per entry)
        ld b,5
.b:     push bc
        ld a,(ix+0) : push ix : call .one : pop ix
        ld de,(.r0) : or a : sbc hl,de : jr nc,.p
        ld hl,0
.p:     push hl : call wdec : pop hl
        pop bc
        ld a,h : or a : jr nz,.c : ld a,l : cp 3 : jr c,.nc
.c:     ld a,c : or (ix+1) : ld c,a
.nc:    inc ix : inc ix
        ld a,b : cp 1 : jr z,.nk
        push bc : ld a,',' : call wchr : pop bc
.nk:    djnz .b
        ld a,(.t) : cp 1 : jr z,.nx                        ; 48K: not compared
        ld hl,.exp-4 : add a,a : add hl,a
        ld a,c : cp (hl) : jr z,.nx
        xor a : ld (.bk),a
.nx:    ld a,(.t) : inc a : ld (.t),a : cp 5 : jp c,.l
        call xt_back : call xt_dis
        ld a,(.bk) : or a : ld hl,w_book : jr nz,.w
        ld hl,w_other2
.w:     call res_word
        ld hl,xk_lim : call ex_k : ld a,'3' : jp wchr
; A = page -> HL = lines for 1024 reads of $C000 (slot 6 = that page) at 3.5 MHz from line 8
.one:   nextreg $56,a
        nextreg $07,0
        call frame_sync : ld a,8 : call sync_lsb
        ld hl,$C000 : ld b,0
.r:     ld a,(hl) : ld a,(hl) : ld a,(hl) : ld a,(hl) : djnz .r
        call line : ld de,8 : or a : sbc hl,de
        push hl : nextreg $56,HOMEP6 : pop hl
        ret
; bank pages and their bits: 1 3 4 5 7
.pg:    db 2,1, 6,2, 8,4, 10,8, 14,16
; the book's sets as masks (timing t = 2 3 4 at .exp + 2t - 4): 128K 1 3 5 7, +3 4 5 7, Pentagon none
.exp:   db %11011,0, %11100,0, 0,0
.t:     db 0
.bk:    db 0
.r0:    dw 0
xk_r08:  db "nr08",0
xk_lim:  db "lim",0
w_book: db "book",0
w_other2: db "other",0

; ---------------------------------------------------------------- XT4 48K timing: $7FFD and $3FFD page
; 48K timing; OUT $7FFD,$13 -> MMU 6 / 7 read; back; OUT $3FFD,$13 (bit 14 = 0: decoded too in 48K / 128K
; timing, book ch 3) -> MMU 6 / 7 read; back (xt_pg in bank 2). $3FFD is not written when NextReg $D8 bit 0
; was set at launch (the +3 disk ports are then trapped: a Multiface NMI, book ch 4): keys b6/b7 = $FF and
; p3ffd=skipped (board run 7: nrd8=$01, so the $3FFD half is not answered).
; v = MMU 6 after $7FFD; PASS if both writes gave 6 / 7.
t_xt4:  call xt_arm
        ld a,1 : call xt_set
        call xt_pg
        call xt_back : call xt_dis
        ld a,(xtpg) : call res_hex
        ld a,(xtpg) : ld hl,.k0 : call ex_kh
        ld a,(xtpg+1) : ld hl,.k1 : call ex_kh
        ld a,(xtpg+2) : ld hl,.k2 : call ex_kh
        ld a,(xtpg+3) : ld hl,.k3 : call ex_kh
        ld a,(NRSNAP+$D8) : ld hl,xk_d8 : call ex_kh
        ld a,(NRSNAP+$D8) : rra : jr nc,.w3
        ld hl,xk_3f : call ex_k : ld hl,w_skip : call wstr  ; " p3ffd=skipped": not written, b6 / b7 not read
.w3:
        ld hl,xtpg : ld de,.e : ld b,4
.c:     ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : djnz .c
        ld a,ST_PASS : ld (R_st),a : ret
.e:     db 6,7,6,7
.k0:    db "a6",0
.k1:    db "a7",0
.k2:    db "b6",0
.k3:    db "b7",0
xk_d8:   db "nrd8",0

; ---------------------------------------------------------------- XT5 128K timing: $1FFD bit 2 x $7FFD bit 4 -> ROM
; 128K timing; for ($1FFD bit 2, $7FFD bit 4) = 00 01 10 11: CRC of $0000-$3FFF (16K, slots 0 / 1 = ROM)
; (xt_rom in bank 2, 28 MHz); $1FFD = $04, $7FFD = $10 again. Keys r0-r3; s04 = S04's CRC of ROM 3 at the
; start. PASS if r3 = s04 and the four differ (the pair selects four ROMs). v = r0.
t_xt5:  call xt_arm
        ld a,2 : call xt_set
        nextreg $07,3
        call xt_rom
        ld a,(spd0) : nextreg $07,a
        call xt_back : call xt_dis
        ld hl,(xtrc) : call res_hex16
        ld ix,xtrc : ld b,4 : ld c,'0'
.k:     push bc : ld a,' ' : call wchr : ld a,'r' : call wchr : pop bc : push bc : ld a,c : call wchr
        ld a,'=' : call wchr : ld a,'$' : call wchr
        ld l,(ix+0) : ld h,(ix+1) : call whex4
        inc ix : inc ix : pop bc : inc c : djnz .k
        ld hl,xk_s04 : call ex_k : ld a,'$' : call wchr : ld hl,(s04c) : call whex4
        ld hl,(xtrc+6) : ld de,(s04c) : or a : sbc hl,de : ret nz
        ld ix,xtrc : ld b,3                                ; all four different
.o:     push bc : ld l,(ix+0) : ld h,(ix+1) : push ix
.i:     inc ix : inc ix : ld e,(ix+0) : ld d,(ix+1)
        push hl : or a : sbc hl,de : pop hl : jr z,.no
        djnz .i
        pop ix : inc ix : inc ix : pop bc : djnz .o
        ld a,ST_PASS : ld (R_st),a : ret
.no:    pop ix : pop bc : ret
xk_s04:  db "s04",0

; ---------------------------------------------------------------- XT6 the start timing is back
; $03 written with the start timing (again), 3 frames; lines per frame against the preamble's; $03 bits 6:4
; read back against the start value; PRG_FLAGS bit 1 cleared. PASS if both agree. v = lines per frame.
t_xt6:  call xt_back : call xt_dis
        call xt_len : ld (.n),hl : call res_int
        ld hl,u_lines : call res_unit
        ld de,(flines) : inc de : ld hl,xk_exp6 : call ex_kd
        ld a,$03 : call rdreg : ld (.r),a : ld hl,xk_nr03x : call ex_kh
        ld a,(NRSNAP+$03) : ld hl,xk_st03 : call ex_kh
        ld hl,(flines) : inc hl : ld de,(.n) : or a : sbc hl,de : ret nz
        ld a,(.r) : ld b,a : ld a,(NRSNAP+$03) : xor b : and $70 : ret nz
        ld a,ST_PASS : ld (R_st),a : ret
.n:     dw 0
.r:     db 0
xk_exp6: db "exp",0
xk_nr03x: db "nr03",0
xk_st03: db "start03",0
xk_3f:   db "p3ffd",0
w_skip:  db "skipped",0
