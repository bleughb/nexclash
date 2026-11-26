; nxsuite/g6.asm - G6 DMA: D01-D14 (spec section 3 G6). GPL-3.0-or-later.
; Slot-7 overlay. Scratch: DMA pages 38 / 39 in slots 0 / 1 ($0000-$3FFF, interrupts off; MMU 0 / 1 back
; from the launch snapshot after each test). Programs as nextbench (port $6B, $C3 first; the harness ends
; with $83, $C3 and a $6B read). Times: CTC3 /16 (a tick = 16 clocks of 28 MHz) read in the polling loop,
; wraps counted, so a long transfer is timed too (a continuous one: see g6_run). D10-D14 the blitter
; (core 3.03 on; JNext has none, CSpect 4.5.9 has one). Left out (reasons in nxsuite_claims.json, printed
; by the intake): D15 and D16. Pages 40-43 hold overlay code, so the scratch is 36-39, not 36-43.
; D02 writes sprite pattern memory (pattern 63 onwards; it cannot be read back; nothing shows it).

G6P     equ $F700               ; the program being built (64 bytes)
G6B     equ $F740               ; 7 read-back bytes (D06)

; ---------------------------------------------------------------- helpers
; also starts CTC3 (/16, 256) and CTC0 (/256, 256) once: g6_run only reads them (a counter just loaded
; may read 0 first)
g6_map: nextreg $50,38 : nextreg $51,39 : di
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld bc,$183B : ld a,$27 : out (c),a : xor a : out (c),a
        ld b,0
.w:     djnz .w
        ret
g6_unmap:
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a : ret
; HL = address, BC = length, A = value
g6_fill:
        ld (hl),a : dec bc : ld a,b : or c : ret z
        ld d,h : ld e,l : inc de : ldir : ret
; HL = address, BC = length: the nextbench pattern (i x 7 + 3) & $7F
g6_pat: ld e,3
.l:     ld a,e : and $7F : ld (hl),a : ld a,e : add a,7 : ld e,a
        inc hl : dec bc : ld a,b : or c : jr nz,.l
        ret
; HL = a, DE = b, BC = length -> HL = bytes that differ
g6_cmp: push hl : pop ix : ld hl,0
.l:     ld a,(de) : cp (ix+0) : jr z,.s
        inc hl
.s:     inc ix : inc de : dec bc : ld a,b : or c : jr nz,.l
        ret
; HL = address, BC = length, A = value -> HL = bytes that are not that value
g6_cnt: ld e,a : push hl : pop ix : ld hl,0
.l:     ld a,(ix+0) : cp e : jr z,.s
        inc hl
.s:     inc ix : dec bc : ld a,b : or c : jr nz,.l
        ret

; the program from the g6 variables -> G6P, (g6pl) = its length. Layout: $83, WR0 $7D A-lo A-hi len-lo
; len-hi, WR1 (r1 | $40 + timing byte when g6t <> 0), WR2 (r2 | $40 + timing byte (+ $20 and the
; prescaler when g6pre <> 0) when g6t <> 0), WR4 r4 B-lo B-hi, $82, $CF.
g6_mk:  ld de,G6P
        ld a,$83 : ld (de),a : inc de
        ld a,$7D : ld (de),a : inc de
        ld hl,(g6s) : ld a,l : ld (de),a : inc de : ld a,h : ld (de),a : inc de
        ld hl,(g6n) : ld a,l : ld (de),a : inc de : ld a,h : ld (de),a : inc de
        ld a,(g6t) : or a : ld a,(g6r1) : jr z,.n1
        or $40 : ld (de),a : inc de : ld a,(g6t)
.n1:    ld (de),a : inc de
        ld a,(g6t) : or a : ld a,(g6r2) : jr z,.n2
        or $40 : ld (de),a : inc de
        ld a,(g6pre+1) : or a : ld a,(g6t) : jr z,.n2
        or $20 : ld (de),a : inc de : ld a,(g6pre)
.n2:    ld (de),a : inc de
        ld a,(g6r4) : ld (de),a : inc de
        ld hl,(g6d) : ld a,l : ld (de),a : inc de : ld a,h : ld (de),a : inc de
        ld a,$82 : ld (de),a : inc de
        ld a,$CF : ld (de),a : inc de
        ex de,hl : ld de,G6P : or a : sbc hl,de : ld a,l : ld (g6pl),a
        ret
; the defaults: mem $0000 -> mem $2000, continuous, timing byte 2 (nextbench), no prescaler
g6_def: ld hl,0 : ld (g6s),hl : ld (g6pre),hl : ld hl,$2000 : ld (g6d),hl
        ld a,$14 : ld (g6r1),a : ld a,$10 : ld (g6r2),a : ld a,2 : ld (g6t),a
        ld a,$AD : ld (g6r4),a : ld a,$6B : ld (g6port),a
        ret
g6s:    dw 0
g6n:    dw 0
g6d:    dw 0
g6r1:   db 0
g6r2:   db 0
g6t:    db 0
g6pre:  dw 0                    ; low = prescaler, high = 1 if used
g6r4:   db 0
g6pl:   db 0
g6port: db $6B
; send: $C3, then the program, to (g6port)
g6_send:
        ld a,(g6port) : ld c,a : ld a,$C3 : out (c),a
        ld hl,G6P : ld a,(g6pl) : ld b,a : otir
        ret
; start ($87 to (g6port)) and time: HL = address polled for the end (0 = none: the CPU only runs again
; when a continuous transfer is over), E = the value it must reach, (g6lim) = wraps before giving up,
; (g6go) = 0: no $87 (the loop alone: a baseline); 512K polls also give up. -> DEHL = ticks, (g6it) = 32-bit loop count, carry =
; gave up. With HL = 0 the CPU is frozen for the whole transfer (book ch 5: continuous mode keeps the bus),
; so no wrap of CTC3 is seen: the time is rebuilt from three clocks read before and after - the raster
; line (x ticks per line from the preamble, +-2 lines), CTC0 /256 (wraps every 4096 ticks) and CTC3 /16 -
; each one picking the wrap count of the next (good up to one frame).
g6_run: ld (.pa+1),hl : ld a,h : or l : ld (.np),a
        ld a,e : ld (.ev),a
        ld hl,0 : ld (g6it),hl : ld (g6it+2),hl
        ld ix,0
        call line : ld (.l0),hl
        ld bc,$183B : in a,(c) : ld (.a0),a
        ld bc,$1B3B : in a,(c) : ld (.c0),a : ld h,a
        ld de,0
        ld a,(g6go) : or a : jr z,.l
        ld a,(g6port) : ld c,a : ld a,$87 : out (c),a : ld c,$3B
.l:     in a,(c) : cp h : ld h,a : jr c,.n : jr z,.n
        inc de                                      ; a wrap
        push hl : ld hl,(g6lim) : or a : sbc hl,de : pop hl : jr z,.to
.n:     inc ix : ld a,ixh : or ixl : jr nz,.i
        push hl : ld hl,(g6it+2) : inc hl : ld (g6it+2),hl : ld a,l : pop hl
        cp 8 : jr z,.to                             ; 512K polls: a stopped CTC or a DMA that never ends
.i:     ld a,(.np) : or a : jr z,.e
.pa:    ld a,($0000) : push hl : ld hl,.ev : cp (hl) : pop hl : jr nz,.l
.e:     ld (g6it),ix
        call .t : or a : ret
.to:    ld (g6it),ix
        call .t : scf : ret
.t:     push hl : call line : ld (.l1),hl : pop hl
        ld bc,$183B : in a,(c) : ld (.a1),a
        ld a,(.np) : or a : jr z,.fx
        push hl
        ld a,(.c0) : sub h : ld l,a : ld a,e : sbc a,0 : ld h,a : ld a,d : sbc a,0 : ld e,a : ld d,0
        ld a,e : or a : jr nz,.cn                       ; counted wraps: right when the CPU polled all along;
        push hl : ld bc,24000 : or a : sbc hl,bc : pop hl   ; below 24000 ticks (less than any frame) the
        jr nc,.cn                                       ; rebuilt time is used instead, which is right
        pop hl : jr .fx                                 ; also when the DMA held the CPU part of the time
.cn:    pop bc : ret
.fx:    ld a,(.c0) : sub h : ld (.fi),a                 ; CTC3 ticks, mod 256
        ld hl,(.l1) : ld de,(.l0) : or a : sbc hl,de : jr nc,.f1
        ld de,(flines) : inc de : add hl,de             ; across the frame end
.f1:    ld b,h : ld c,l : ld de,(ctcpl) : call mul16
        ld bc,100 : call div32                          ; HL = the line estimate in ticks
        ld de,6144 : add hl,de
        ld a,(.a1) : ld e,a : ld a,(.a0) : sub e        ; CTC0 counts down: ticks of 256 clocks, mod 256
        ld e,a : ld d,0 : ex de,hl : add hl,hl : add hl,hl : add hl,hl : add hl,hl : ex de,hl
        or a : sbc hl,de                                ; est + 6144 - CTC0 x 16
        ld a,h : and $F0 : sub $10 : ld h,a : ld l,0 : add hl,de   ; + 4096 x wraps of CTC0
        ld a,(.fi) : ld e,a : ld d,0 : or a : sbc hl,de
        ld de,384 : add hl,de
        dec h : ld a,(.fi) : ld l,a                     ; 256 x wraps of CTC3 + CTC3 ticks
        ld de,0 : ret
.l0:    dw 0
.l1:    dw 0
.a0:    db 0
.a1:    db 0
.fi:    db 0
.c0:    db 0
.np:    db 0
.ev:    db 0
g6it:   ds 4
g6lim:  dw 256
g6go:   db 1
; DEHL = ticks, BC = bytes -> DEHL = clocks x 100 per byte (ticks x 100 / bytes x 16)
g6_cpb: push bc : call g6_x100 : pop bc : call div32
        add hl,hl : rl e : rl d : add hl,hl : rl e : rl d : add hl,hl : rl e : rl d : add hl,hl : rl e : rl d
        ret
; DEHL x 100 (32 bits)
g6_x100:
        ld (.a),hl : ld (.a+2),de
        ld b,100 : ld hl,0 : ld de,0
.l:     push bc : ld bc,(.a) : add hl,bc : ld bc,(.a+2) : ex de,hl : adc hl,bc : ex de,hl : pop bc : djnz .l
        ret
.a:     ds 4
; (g6k) = key, DEHL = value x 100 -> " key=<fixed>"
g6_kfix:
        ld (.v),hl : ld (.v+2),de
        ld hl,(g6k) : call ex_k
        ld hl,(.v) : ld de,(.v+2) : jp wfix
.v:     ds 4
g6k:    dw 0
g6_fail: ld a,ST_FAIL : ld (R_st),a : ret

; ---------------------------------------------------------------- D01 copies right at 3.5 and 28 MHz
; nextbench programs (timing byte 2): 2K copy $0000 -> $2000 (dst first = NOT src) and 256-byte fill of
; the byte at $0000 (port A fixed) into $2000, at 3.5 and 28 MHz; each checked byte for byte.
; PASS if all four are right; c35 / f35 / c28 / f28 = wrong bytes.
t_d01:  call g6_map
        xor a : call .one : ld (.r),hl : ld (.r+2),de
        ld a,3 : call .one : ld (.r+4),hl : ld (.r+6),de
        call g6_unmap
        xor a : ld (.nz),a
        ld ix,.r : ld hl,.k : ld b,4
.k1:    push bc : ld e,(ix+0) : ld d,(ix+1) : ld a,d : or e : jr z,.z
        ld a,(.nz) : inc a : ld (.nz),a
.z:     push hl : call ex_kd : pop hl : inc hl : inc hl : inc hl : inc hl
        inc ix : inc ix : pop bc : djnz .k1
        ld a,(.nz) : ld l,a : ld h,0 : call res_int   ; v = how many of the four were wrong
        ld a,(.nz) : or a : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; A = speed -> HL = copy wrong, DE = fill wrong
.one:   nextreg $07,a
        ld hl,0 : ld bc,2048 : call g6_pat
        ld hl,0 : ld de,$2000 : ld bc,2048
.n:     ld a,(hl) : cpl : ld (de),a : inc hl : inc de : dec bc : ld a,b : or c : jr nz,.n
        call g6_def : ld hl,2048 : ld (g6n),hl
        call g6_mk : call g6_send
        ld hl,0 : call g6_run
        ld hl,$2000 : ld de,0 : ld bc,2048 : call g6_cmp : push hl
        ld hl,$2000 : ld bc,256 : xor a : call g6_fill
        ld a,$55 : ld ($0000),a
        call g6_def : ld hl,256 : ld (g6n),hl : ld a,$24 : ld (g6r1),a
        call g6_mk : call g6_send
        ld hl,0 : call g6_run
        ld hl,$2000 : ld bc,256 : ld a,$55 : call g6_cnt : ex de,hl
        pop hl : ret
.r:     ds 8
.nz:    db 0
.k:     db "c35",0, "f35",0, "c28",0, "f28",0

; ---------------------------------------------------------------- D02 clocks per byte, timing byte
; mem $0000 -> mem $2000 and mem $0000 -> port $5B (pattern upload from $303B = 63), continuous, timing
; byte absent / %01 / %11 / %10 (WR1 and WR2 bit 6 + that byte; the book's table: 00 4, 01 3, 10 2, 11 4
; clocks a cycle), 256 and 2048 bytes, at 3.5 and 28 MHz: 28 MHz clocks per byte = the slope (t2048 - t256)
; / 1792. Keys: m / p (memory / port), a / 3 / 4 / 2 (cycle length), 35 / 28. Builds up to 57d7b56 keyed
; the byte %11 as "3" and compared it with "absent": a test fault (board run 6: 8 against 6).
; PASS if "absent" is the 3-cycle byte %01 within 0.10 clocks at 28 MHz and 0.80 at 3.5 MHz, where every
; value is 8 times larger and one timing step is 0.16 (CSpect 4.6.0.0: pa35 47.84 against p335 48 failed a
; run at 0.10; a 3- against 4-clock cycle differs by 8 x 2 = 16 there) (dma-default-cycle-length);
; v = m a 28. A slope outside 0.5-100 clocks is a timing fault (method=fault, INFO, never FAIL). The
; transfers are continuous: the CPU is frozen, g6_run rebuilds the time (board run 5 of d99fbf8 lost
; the CTC3 wraps: 0 / 584 clocks).
t_d02:  call g6_map
        ld hl,0 : ld bc,2048 : call g6_pat
        ld hl,.tab : ld (.p),hl
        ld a,1 : ld (.ok),a : ld (.sane),a
.l:     ld hl,(.p) : ld a,(hl) : cp $FF : jp z,.x
        ld (.kind),a : inc hl : ld a,(hl) : ld (.tim),a : inc hl : ld a,(hl) : ld (.spd),a : inc hl
        ld (.p),hl
        ld a,(.spd) : nextreg $07,a
        ld hl,256 : call .time : ld (.t1),hl
        ld hl,2048 : call .time
        ld de,(.t1) : or a : sbc hl,de                  ; ticks for 1792 bytes
        ld de,0 : ld bc,1792 : call g6_cpb : ld (.v),hl : ld (.v+2),de
        ld a,d : or e : jr nz,.ins                      ; a slope outside 0.5-100 clocks a byte is the
        push hl : ld bc,50 : or a : sbc hl,bc : pop hl  ; method failing, not the DMA: INFO, never FAIL
        jr c,.ins
        ld bc,10001 : or a : sbc hl,bc : jr c,.sn
.ins:   xor a : ld (.sane),a
.sn:
        ; key "<kind><tim><spd>"
        ld a,(.kind) : ld (.kb),a
        ld a,(.tim) : ld hl,.kc : add hl,a : ld a,(hl)
        ld (.kb+1),a
        ld a,(.spd) : or a : ld hl,"5"*256+"3" : jr z,.ks
        ld hl,"8"*256+"2"
.ks:    ld (.kb+2),hl
        ld hl,.kb : ld (g6k),hl : ld hl,(.v) : ld de,(.v+2) : call g6_kfix
        ; keep absent / 3 for the comparison
        ld a,(.tim) : or a : jr nz,.n3
        ld hl,(.v) : ld (.va),hl
        ld a,(.kind) : cp 'm' : jr nz,.c
        ld a,(.spd) : or a : jr z,.c
        ld hl,(.v) : ld de,(.v+2) : call res_num : ld hl,u_clocks : call res_unit
        jr .c
.n3:    cp 1 : jr nz,.c
        ld hl,(.v) : ld de,(.va) : or a : sbc hl,de : jr nc,.ab
        ex de,hl : ld hl,0 : or a : sbc hl,de
.ab:    ld de,11 : ld a,(.spd) : or a : jr nz,.tl       ; |absent - 3| <= 0.10 at 28 MHz,
        ld de,81                                        ; <= 0.80 at 3.5 MHz (one T there = 8 clocks)
.tl:    or a : sbc hl,de : jr c,.c
        xor a : ld (.ok),a
.c:     jp .l
.x:     call g6_unmap
        ld a,(.sane) : or a : jr nz,.s1
        ld hl,k_meth : call ex_k : ld hl,w_fault : jp wstr    ; INFO method=fault
.s1:    ld a,(.ok) : or a : jp z,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; HL = bytes -> HL = ticks (one transfer of that kind / timing)
.time:  ld (g6n),hl
        call g6_def
        ld a,(.tim) : ld (g6t),a
        ld a,(.kind) : cp 'p' : jr nz,.mm
        ld bc,$303B : ld a,63 : out (c),a
        ld a,$28 : ld (g6r2),a : ld hl,$5B : ld (g6d),hl
.mm:    call g6_mk : call g6_send
        ld hl,0 : call g6_run
        ret
.tab:   db 'm',0,0, 'm',1,0, 'm',3,0, 'm',2,0, 'p',0,0, 'p',1,0, 'p',3,0, 'p',2,0
        db 'm',0,3, 'm',1,3, 'm',3,3, 'm',2,3, 'p',0,3, 'p',1,3, 'p',3,3, 'p',2,3, $FF
; the key letter per timing byte: none, %01 = 3 clocks, %10 = 2, %11 = 4 (book ch 5: 00 4, 01 3, 10 2, 11 4)
.kc:    db 'a','3','2','4'
.p:     dw 0
.kind:  db 0
.tim:   db 0
.spd:   db 0
.t1:    dw 0
.v:     ds 4
.va:    dw 0
.ok:    db 0
.sane:  db 0
.kb:    db "xxxx",0

; ---------------------------------------------------------------- D03 length 0 / 1 / 16
; source $0000 = 1, 2, 3, ...; destination $2000 32 bytes of $AA; programs of length 0, 1 and 16 (timing
; byte 2, continuous) sent and started through port $6B and then through port $0B; bytes written counted.
; Every pass ends with $C3 and a read through $6B. PASS if $6B wrote 1, 1, 16; the $0B counts are INFO.
t_d03:  call g6_map
        ld hl,0 : ld b,32 : ld a,1
.s:     ld (hl),a : inc hl : inc a : djnz .s
        ld hl,.r : ld (.rp),hl : ld a,$6B : ld (.pt),a
.pp:    ld hl,.ls
.ln:    ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,d : and e : inc a : jr z,.np
        push hl
        ld (g6n),de
        ld hl,$2000 : ld bc,32 : ld a,$AA : call g6_fill
        call g6_def : ld a,(.pt) : ld (g6port),a
        call g6_mk : call g6_send
        ld hl,0 : call g6_run
        ld a,$C3 : out ($6B),a : in a,($6B)
        ld hl,$2000 : ld bc,32 : ld a,$AA : call g6_cnt
        ld a,l : ld hl,(.rp) : ld (hl),a : inc hl : ld (.rp),hl
        pop hl : jr .ln
.np:    ld a,(.pt) : cp $0B : jr z,.x
        ld a,$0B : ld (.pt),a : jr .pp
.x:     ld a,$6B : ld (g6port),a
        call g6_unmap
        ld hl,.k : ld ix,.r : ld b,6
.k1:    push bc : ld e,(ix+0) : ld d,0 : push hl : call ex_kd : pop hl
        ld bc,6 : add hl,bc : inc ix : pop bc : djnz .k1
        ld a,(.r+2) : ld l,a : ld h,0 : call res_int : ld hl,u_bytes : call res_unit
        ld a,(.r) : cp 1 : jp nz,g6_fail
        ld a,(.r+1) : cp 1 : jp nz,g6_fail
        ld a,(.r+2) : cp 16 : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
.ls:    dw 0, 1, 16, $FFFF
.pt:    db 0
.rp:    dw 0
.r:     ds 6
.k:     db "p6b0",0,0, "p6b1",0,0, "p6b16",0, "p0b0",0,0, "p0b1",0,0, "p0b16",0

; ---------------------------------------------------------------- D04 prescaler
; burst ($CD), 256 bytes $0000 -> $2000, WR2 timing byte 2 + $20 and the prescaler P = 0, 1, 12, 55, 100,
; 144, at 3.5 and 28 MHz; end seen by polling the last destination byte (dst first = NOT src). INFO v =
; clocks (28 MHz) per byte at P = 100, 28 MHz; keys pP_35 / pP_28 per P.
t_d04:  call g6_map
        ld hl,0 : ld bc,256 : call g6_pat
        ld hl,.ps : ld (.p),hl
.l:     ld hl,(.p) : ld a,(hl) : cp $FF : jp z,.x
        ld (.pv),a : inc hl : ld a,(hl) : ld (.spd),a : inc hl : ld (.p),hl
        ld a,(.spd) : nextreg $07,a
        ld hl,0 : ld de,$2000 : ld bc,256
.n:     ld a,(hl) : cpl : ld (de),a : inc hl : inc de : dec bc : ld a,b : or c : jr nz,.n
        call g6_def : ld hl,256 : ld (g6n),hl : ld a,$CD : ld (g6r4),a
        ld a,(.pv) : ld l,a : ld h,1 : ld (g6pre),hl
        call g6_mk : call g6_send
        ld hl,$4000 : ld (g6lim),hl
        ld a,($00FF) : ld e,a : ld hl,$20FF : call g6_run
        push af : push hl : ld hl,256 : ld (g6lim),hl : pop hl : pop af   ; (board run 5: HL was lost here,
        jr nc,.ok                                                     ; so every P read 16)
        ld hl,-100 : ld de,-1 : jr .w
.ok:    ld bc,256 : call g6_cpb
.w:     ld (.v),hl : ld (.v+2),de
        ; key "p<P>_<35|28>"
        ld hl,.kb+1 : ld a,(.pv) : ld e,a : ld d,0 : ex de,hl : call .dec : ex de,hl
        ld (hl),'_' : inc hl
        ld a,(.spd) : or a : ld bc,"5"*256+"3" : jr z,.ks
        ld bc,"8"*256+"2"
.ks:    ld (hl),c : inc hl : ld (hl),b : inc hl : ld (hl),0
        ld hl,.kb : ld (g6k),hl : ld hl,(.v) : ld de,(.v+2) : call g6_kfix
        ld a,(.pv) : cp 100 : jp nz,.l
        ld a,(.spd) : or a : jp z,.l
        ld hl,(.v) : ld de,(.v+2) : call res_num : ld hl,u_clocks : call res_unit
        jp .l
.x:     call g6_unmap : ret
; HL = number < 1000, DE = text -> digits at DE (no leading zeros), DE after them
.dec:   ld bc,100 : call .d1 : ld bc,10 : call .d1
        ld a,l : add a,'0' : ld (de),a : inc de : xor a : ld (.lz),a : ret
.d1:    ld a,'0'-1
.s:     inc a : or a : sbc hl,bc : jr nc,.s
        add hl,bc
        cp '0' : jr nz,.put
        push af : ld a,(.lz) : or a : jr nz,.p0
        pop af : ret
.p0:    pop af
.put:   ld (de),a : inc de : ld a,1 : ld (.lz),a : ret
.lz:    db 0
.ps:    db 0,0, 1,0, 12,0, 55,0, 100,0, 144,0, 0,3, 1,3, 12,3, 55,3, 100,3, 144,3, $FF
.p:     dw 0
.pv:    db 0
.spd:   db 0
.v:     ds 4
.kb:    db "p144_28",0

; ---------------------------------------------------------------- D05 the CPU's share during a burst
; 28 MHz. The polling loop alone (no DMA) for as long as a burst of 2K at P = 100 lasted gives the loop
; count of a free CPU; the count during that burst, and during a continuous 2K transfer with P = 100,
; over it = the CPU's share. INFO v = % during the burst; cont = % during the continuous transfer.
t_d05:  call g6_map
        nextreg $07,3
        ld hl,0 : ld bc,2048 : call g6_pat
        ld a,$CD : call .one : ld (.b),hl : ld (.b+2),de
        ld a,$AD : call .one : ld (.c),hl : ld (.c+2),de
        call g6_unmap
        ld hl,(.b) : ld de,(.b+2) : call res_num : ld hl,u_pct : call res_unit
        ld hl,k_cont : ld (g6k),hl : ld hl,(.c) : ld de,(.c+2) : jp g6_kfix
; A = WR4 ($CD burst / $AD continuous) -> DEHL = share x 100 (%)
.one:   ld (.r4),a
        ld hl,0 : ld de,$2000 : ld bc,2048
.n:     ld a,(hl) : cpl : ld (de),a : inc hl : inc de : dec bc : ld a,b : or c : jr nz,.n
        call g6_def : ld hl,2048 : ld (g6n),hl : ld a,(.r4) : ld (g6r4),a
        ld hl,$0164 : ld (g6pre),hl
        call g6_mk : call g6_send
        ld hl,$4000 : ld (g6lim),hl
        ld a,($07FF) : ld e,a : ld hl,$27FF : call g6_run
        ld (.tk),hl : ld (.tk+2),de                         ; the ticks (board run 5: lost before use)
        ld a,$83 : out ($6B),a
        ld hl,(g6it) : ld (.ii),hl : ld hl,(g6it+2) : ld (.ii+2),hl
        call .rt : ld (.r1),hl
        ; the loop alone for as many wraps (+1)
        ld hl,(.tk) : ld de,(.tk+2)
        ld l,h : ld h,e : inc hl : ld (g6lim),hl            ; wraps = ticks / 256 + 1
        xor a : ld (g6go),a
        ld e,$FF : ld hl,.nev : call g6_run
        ld (.tk),hl : ld (.tk+2),de
        ld a,1 : ld (g6go),a : ld hl,256 : ld (g6lim),hl
        ld hl,(g6it) : ld (.ii),hl : ld hl,(g6it+2) : ld (.ii+2),hl
        call .rt
        ld a,h : or l : jr nz,.d
        inc l
.d:     push hl                                             ; share x 100 = rate1 x 10000 / rate0
        ld bc,(.r1) : ld de,10000 : call mul16
        pop bc : jp div32
; (.ii) loop passes over (.tk) ticks -> HL = passes x 100 per 16 ticks (rates over different lengths
; compare; board run 5's 104 % came from a baseline about a wrap longer than the transfer)
.rt:    ld hl,(.tk) : ld de,(.tk+2)
        ld b,4
.sh:    srl d : rr e : rr h : rr l : djnz .sh
        ld a,h : or l : jr nz,.r0
        inc l
.r0:    push hl
        ld hl,(.ii) : ld de,(.ii+2) : call g6_x100
        pop bc : jp div32
.r4:    db 0
.tk:    ds 4
.ii:    ds 4
.r1:    dw 0
.b:     ds 4
.c:     ds 4
.nev:   db 0
k_cont: db "cont",0
k_meth: db "method",0
w_fault: db "fault",0
u_pct:  db "%",0

; ---------------------------------------------------------------- D06 status read
; $C3; $BF (read status); IN $6B -> s0; a 16-byte copy (continuous); $BF; IN -> s1; then read mask $7F
; ($BB, $7F), $A7 (start the read sequence) and 7 reads r0-r6. PASS if s0 = $3A and s1 = $1A.
t_d06:  call g6_map
        nextreg $07,3
        ld a,$C3 : out ($6B),a
        ld a,$BF : out ($6B),a : in a,($6B) : ld (.s),a
        call g6_def : ld hl,16 : ld (g6n),hl
        call g6_mk
        ld hl,G6P : ld a,(g6pl) : ld b,a : ld c,$6B : otir
        ld hl,0 : call g6_run
        ld a,$BF : out ($6B),a : in a,($6B) : ld (.s+1),a
        ld a,$BB : out ($6B),a : ld a,$7F : out ($6B),a : ld a,$A7 : out ($6B),a
        ld hl,G6B : ld b,7
.r:     in a,($6B) : ld (hl),a : inc hl : djnz .r
        call g6_unmap
        ld a,(.s) : call res_hex
        ld a,(.s+1) : ld hl,k_s1 : call ex_kh
        ld hl,G6B : ld de,.kr : ld b,7
.k:     push bc : push hl : push de : ld a,(hl) : ex de,hl : call ex_kh : pop de : pop hl : pop bc
        inc hl : inc de : inc de : inc de : djnz .k
        ld a,(.s) : cp $3A : jp nz,g6_fail
        ld a,(.s+1) : cp $1A : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
.s:     ds 2
.kr:    db "r0",0, "r1",0, "r2",0, "r3",0, "r4",0, "r5",0, "r6",0
k_s1:   db "s1",0

; ---------------------------------------------------------------- D07 $C3 keeps the program
; 64-byte copy $0000 -> $2000 (timing byte 2) run; destination cleared; $C3; then only $CF, $87: is the
; copy made again, and its clocks per byte (timing back to the reset default). PASS if copied again;
; v = clocks per byte of the second run (loop overhead included); first = the same for the first run.
t_d07:  call g6_map
        nextreg $07,3
        ld hl,0 : ld bc,64 : call g6_pat
        ld hl,$2000 : ld bc,64 : xor a : call g6_fill
        call g6_def : ld hl,64 : ld (g6n),hl
        call g6_mk : call g6_send
        ld hl,0 : call g6_run : ld (.t1),hl
        ld hl,$2000 : ld de,0 : ld bc,64 : call g6_cmp : ld (.b1),hl
        ld hl,$2000 : ld bc,64 : xor a : call g6_fill
        ld a,$C3 : out ($6B),a : ld a,$CF : out ($6B),a
        ld hl,0 : call g6_run : ld (.t2),hl
        ld hl,$2000 : ld de,0 : ld bc,64 : call g6_cmp : ld (.b2),hl
        call g6_unmap
        ld hl,(.t2) : ld de,0 : ld bc,64 : call g6_cpb : call res_num : ld hl,u_clocks : call res_unit
        ld hl,k6_first : ld (g6k),hl : ld hl,(.t1) : ld de,0 : ld bc,64 : call g6_cpb : call g6_kfix
        ld de,(.b1) : ld hl,k_bad1 : call ex_kd
        ld de,(.b2) : ld hl,k_bad2 : call ex_kd
        ld hl,(.b2) : ld a,h : or l : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
.t1:    dw 0
.t2:    dw 0
.b1:    dw 0
.b2:    dw 0
k6_first: db "first",0
k_bad1: db "bad1",0
k_bad2: db "bad2",0

; ---------------------------------------------------------------- D08 overlapping copy
; $0000 = $5A, $0001-$0100 = NOT pattern; 256-byte copy $0000 -> $0001 (timing byte 2, 28 MHz). PASS if
; $0001-$0100 are all $5A (byte by byte: the copy fills). v = bytes that are not $5A.
t_d08:  call g6_map
        nextreg $07,3
        ld hl,1 : ld bc,256 : call g6_pat
        ld hl,1 : ld b,0
.c:     ld a,(hl) : cpl : ld (hl),a : inc hl : djnz .c
        ld a,$5A : ld ($0000),a
        call g6_def : ld hl,256 : ld (g6n),hl : ld hl,1 : ld (g6d),hl
        call g6_mk : call g6_send
        ld hl,0 : call g6_run
        ld hl,1 : ld bc,256 : ld a,$5A : call g6_cnt
        push hl : call g6_unmap : pop hl
        push hl : call res_int : ld hl,u_bytes : call res_unit : pop hl
        ld a,h : or l : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret

; ---------------------------------------------------------------- D09 is the blitter there
; Book report N27 (zx-next-unraveling L4808-4822): $C3; the zxnDDMA bytes with every data byte below $80
; ($D7,$0B ; $DB,$0B ; $DF,$01 = physical); eight $83; then one ordinary 1-byte copy A $2000 -> B $0000.
; The blitter copies physical $0B2000 (page 57 offset 0) to $0B0000 (page 56 offset 0); an old DMA copies
; the 16-bit addresses (slot 1 = page 39 offset 0 -> slot 0 = page 38 offset 0). Bytes of 56 / 57 saved
; and written back. INFO v = blitter / none / other; FAIL if none and core >= 3.03 ($01 >= $33). The
; answer gates D10-D14 (blseen): a probe, not a version number (CSpect reports core 4.00.00).
t_d09:  call g6_map
        nextreg $07,3
        nextreg $56,56 : ld a,($C000) : ld (.sv),a : xor a : ld ($C000),a
        nextreg $56,57 : ld a,($C000) : ld (.sv+1),a : ld a,$22 : ld ($C000),a
        ld a,HOMEP6 : nextreg $56,a
        xor a : ld ($0000),a : ld a,$11 : ld ($2000),a
        ld hl,.pr : ld b,.pre-.pr : ld c,$6B : otir
        ld a,$C3 : out ($6B),a                       ; the blitter settings off again
        ld a,($0000) : ld (.r),a
        nextreg $56,56 : ld a,($C000) : ld (.r+1),a : ld a,(.sv) : ld ($C000),a
        nextreg $56,57 : ld a,(.sv+1) : ld ($C000),a
        ld a,HOMEP6 : nextreg $56,a
        call g6_unmap
        ld a,(.r+1) : sub $22 : ld a,0 : jr nz,.bs
        inc a
.bs:    ld (blseen),a                                ; 1 blitter, 0 none / other
        ld a,(.r) : ld hl,k_old : call ex_kh
        ld a,(.r+1) : ld hl,k_phys : call ex_kh
        ld hl,w_blit : ld a,(.r+1) : cp $22 : jr z,.w
        ld hl,w_none : ld a,(.r) : cp $11 : jr z,.w
        ld hl,w6_other
.w:     push hl : call res_word : pop hl
        ld de,w_none : or a : sbc hl,de : ret nz
        ld a,(NRSNAP+$01) : cp $33 : ret c
        jp g6_fail
.pr:    db $C3, $D7,$0B, $DB,$0B, $DF,$01, $83,$83,$83,$83,$83,$83,$83,$83
        db $7D, $00,$20, $01,$00, $14, $10, $AD, $00,$00, $82, $CF, $87
.pre:
.sv:    ds 2
.r:     ds 2
k_old:  db "old",0
k_phys: db "phys",0
w_blit: db "blitter",0
w_none: db "none",0
w6_other: db "other",0

; ---------------------------------------------------------------- D10-D14 the blitter (core 3.03 on)
; Book ch 5 "The zxnDDMA: the blitter": $C3 first (it clears every blitter setting), then $D7 / $DB (bits
; 23-16 of port A / B), $DF (flags: bit 0 physical, 1 2D, 2 transparent, 3 fill, 4 Layer 2 X,Y), $E3 / $E7
; / $EB / $EF (row length, rows, A stride, B stride, low byte first), $F3 (transparent colour), $F7 (fill
; value), then an ordinary program; $C3 again after. Physical address of RAM page n = $40000 + n x $2000:
; page 38 = $08C000, page 39 = $08E000 (slots 0 / 1 here). Gate: D09's probe this session (blseen 1 = run,
; 0 = SKIP why=no-blitter); D09 not run this session ($FF: a resume or hung retry): core below 3.03 = SKIP.
bl_chk: ld a,(blseen) : cp 1 : ret z
        inc a : jr z,.v
.no:    ld hl,why_nobl : ld (R_why),hl : ld a,ST_SKIP : ld (R_st),a : scf : ret
.v:     ld a,(NRSNAP+$01) : cp $33 : jr c,.no
        or a : ret
blseen: db $FF
; A = flags: g6_def, no timing byte (the reset default), extended bytes $08 / $08
bl_def: ld (blf),a : call g6_def : xor a : ld (g6t),a : ld a,$08 : ld (blxa),a : ld (blxb),a : ret
; the g6 variables (g6_mk) with physical addresses, (blxa) / (blxb), (blf), (blv) the colour / fill value,
; bl2 the 2D words (sent when flag bit 1) -> sent, started, timed (DEHL ticks, g6_run), $C3 after
bl_go:  call g6_mk
        ld a,$C3 : out ($6B),a
        ld a,$D7 : out ($6B),a : ld a,(blxa) : out ($6B),a
        ld a,$DB : out ($6B),a : ld a,(blxb) : out ($6B),a
        ld a,$DF : out ($6B),a : ld a,(blf) : out ($6B),a
        ld a,(blf) : and 2 : jr z,.n2
        ld hl,bl2 : ld e,$E3
.l2:    ld a,e : out ($6B),a : ld a,(hl) : out ($6B),a : inc hl : ld a,(hl) : out ($6B),a : inc hl
        ld a,e : add a,4 : ld e,a : cp $F3 : jr nz,.l2
.n2:    ld a,(blf) : and 4 : jr z,.n3
        ld a,$F3 : out ($6B),a : ld a,(blv) : out ($6B),a
.n3:    ld a,(blf) : and 8 : jr z,.n4
        ld a,$F7 : out ($6B),a : ld a,(blv) : out ($6B),a
.n4:    ld hl,G6P : ld a,(g6pl) : ld b,a : ld c,$6B : otir
        ld hl,0 : call g6_run
        ld a,$C3 : out ($6B),a : ret
blxa:   db 0
blxb:   db 0
blf:    db 0
blv:    db 0
bl2:    dw 0,0,0,0              ; row length, rows, A stride, B stride
; HL = a, DE = b -> HL = |a - b|
bl_abs: or a : sbc hl,de : ret nc
        ex de,hl : ld hl,0 : or a : sbc hl,de : ret

; ---------------------------------------------------------------- D10 physical addresses
; 16 bytes page 38 +$100 -> page 39 +$100 by physical address ($08C100 -> $08E100), read through the MMU
; (slots 0 / 1); 16 bytes before and 32 after the copy checked still $AA. cross: 16 bytes from $08FFF8 (the
; last 8 of page 39, then the first 8 of page 40 if the address carries into the extended byte) to page 38
; +$200, compared with page 39 / page 40 through slot 1. v = wrong bytes of the first copy (guards
; included). PASS if v and cross are 0.
t_d10:  call bl_chk : ret c
        call g6_map
        nextreg $07,3
        ld hl,$0100 : ld bc,16 : call g6_pat
        ld hl,$20F0 : ld bc,64 : ld a,$AA : call g6_fill
        ld a,1 : call bl_def
        ld hl,$C100 : ld (g6s),hl : ld hl,$E100 : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld hl,$0100 : ld de,$2100 : ld bc,16 : call g6_cmp : push hl
        ld hl,$20F0 : ld bc,16 : ld a,$AA : call g6_cnt : push hl
        ld hl,$2110 : ld bc,32 : ld a,$AA : call g6_cnt
        pop de : add hl,de : pop de : add hl,de : ld (.w),hl
        ld hl,$0200 : ld bc,16 : ld a,$AA : call g6_fill
        ld a,1 : call bl_def
        ld hl,$FFF8 : ld (g6s),hl : ld hl,$C200 : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld hl,$3FF8 : ld de,$0200 : ld bc,8 : call g6_cmp : push hl
        nextreg $51,40
        ld hl,$2000 : ld de,$0208 : ld bc,8 : call g6_cmp
        nextreg $51,39
        pop de : add hl,de : ld (.x),hl
        call g6_unmap
        ld hl,(.w) : call res_int : ld hl,u_bytes : call res_unit
        ld de,(.x) : ld hl,k_cross : call ex_kd
        ld hl,(.w) : ld de,(.x) : ld a,h : or l : or d : or e : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
.w:     dw 0
.x:     dw 0
k_cross: db "cross",0

; ---------------------------------------------------------------- D11 block RAM pages
; Pages $0A (bank 5: the ULA screen's first 8K), $0E and $0F at physical $054000 / $05C000 / $05E000: 16
; bytes there saved by a physical copy to page 38 +$300 and through the MMU (slot 1) to +$320; the pattern
; (+$340) copied there physically; read through the MMU and by a physical copy to +$360; then the saved
; bytes put back the same two ways. Word per page: shows (the MMU sees the pattern), twin (the MMU does not,
; the physical read does), other. v = page $0A; keys p0e / p0f. PASS if $0A twin, $0E twin, $0F shows.
t_d11:  call bl_chk : ret c
        call g6_map
        nextreg $07,3
        ld hl,$0340 : ld bc,16 : call g6_pat
        ld a,$0A : ld hl,$4000 : call .one : ld (.r),hl
        ld a,$0E : ld hl,$C000 : call .one : ld (.r+2),hl
        ld a,$0F : ld hl,$E000 : call .one : ld (.r+4),hl
        call g6_unmap
        ld hl,(.r) : call res_word
        ld hl,k_p0e : call ex_k : ld hl,(.r+2) : call wstr
        ld hl,k_p0f : call ex_k : ld hl,(.r+4) : call wstr
        ld hl,(.r) : ld de,w_twin : or a : sbc hl,de : jp nz,g6_fail
        ld hl,(.r+2) : ld de,w_twin : or a : sbc hl,de : jp nz,g6_fail
        ld hl,(.r+4) : ld de,w_shows : or a : sbc hl,de : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; A = page, HL = its 16-bit physical address (extended byte $05) -> HL = its word
.one:   ld (.pg),a : ld (.ad),hl
        ld a,1 : call bl_def : ld a,$05 : ld (blxa),a              ; save it physically
        ld hl,(.ad) : ld (g6s),hl : ld hl,$C300 : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld a,(.pg) : nextreg $51,a                                 ; and through the MMU
        ld hl,$2000 : ld de,$0320 : ld bc,16 : ldir
        nextreg $51,39
        ld a,1 : call bl_def : ld a,$05 : ld (blxb),a              ; the pattern there
        ld hl,$C340 : ld (g6s),hl : ld hl,(.ad) : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld a,(.pg) : nextreg $51,a
        ld hl,$2000 : ld de,$0340 : ld bc,16 : call g6_cmp : ld (.wm),hl
        nextreg $51,39
        ld hl,$0360 : ld bc,16 : ld a,$AA : call g6_fill          ; read back physically
        ld a,1 : call bl_def : ld a,$05 : ld (blxa),a
        ld hl,(.ad) : ld (g6s),hl : ld hl,$C360 : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld hl,$0360 : ld de,$0340 : ld bc,16 : call g6_cmp : ld (.wp),hl
        ld a,1 : call bl_def : ld a,$05 : ld (blxb),a              ; put back physically
        ld hl,$C300 : ld (g6s),hl : ld hl,(.ad) : ld (g6d),hl : ld hl,16 : ld (g6n),hl
        call bl_go
        ld a,(.pg) : nextreg $51,a                                 ; and through the MMU
        ld hl,$0320 : ld de,$2000 : ld bc,16 : ldir
        nextreg $51,39
        ld hl,(.wm) : ld a,h : or l : ld hl,w_shows : ret z
        ld hl,(.wp) : ld a,h : or l : ld hl,w_twin : ret z
        ld hl,w6_other : ret
.pg:    db 0
.ad:    dw 0
.wm:    dw 0
.wp:    dw 0
.r:     ds 6
k_p0e:  db "p0e",0
k_p0f:  db "p0f",0
w_twin: db "twin",0
w_shows: db "shows",0

; ---------------------------------------------------------------- D12 2D
; Page 38 as a sheet 256 bytes wide (byte = row x 13 + column), page 39 filled with $AA before each case.
; a: 32 x 32 from column 16 into a buffer 80 wide at +4 (strides 256 / 80); b: the Rainbow case, 64 x 20,
; strides 64 / 80, to +488; z0l: row length 0, 1 row; z0r: row length 1, 0 rows (strides 1, to +$100).
; Physical mode. a / b: every byte checked against the sheet and every other byte of page 39 still $AA
; (wrong bytes); z0l / z0r: bytes of page 39 written. v = a + b. PASS if a = b = 0 and z0l = z0r = 1
; (DDMA.md and the book: 0 still moves one byte). Marked risky: were 0 to mean 65536 the copy would run on
; into pages 40-47.
t_d12:  call bl_chk : ret c
        call g6_map
        nextreg $07,3
        ld hl,0
.p:     ld a,h : add a,a : add a,a : add a,a : add a,h : add a,h : add a,h : add a,h : add a,h
        add a,l : ld (hl),a : inc hl : ld a,h : cp $20 : jr nz,.p
        ld hl,.cs : ld de,.r
.l:     push de : push hl
        ld de,.cur : ld bc,12 : ldir
        ld hl,$2000 : ld bc,$2000 : ld a,$AA : call g6_fill
        ld a,3 : call bl_def
        ld hl,(.cur) : ld de,$C000 : add hl,de : ld (g6s),hl
        ld hl,(.cur+4) : ld de,$C000 : add hl,de : ld (g6d),hl
        ld hl,(.cur+8) : ld (bl2),hl : ld hl,(.cur+10) : ld (bl2+2),hl
        ld hl,(.cur+2) : ld (bl2+4),hl : ld hl,(.cur+6) : ld (bl2+6),hl
        ld hl,1 : ld (g6n),hl
        call bl_go
        ld hl,(.cur+8) : ld a,h : or l : jr z,.z
        ld hl,(.cur+10) : ld a,h : or l : jr z,.z
        call .chk : jr .k
.z:     ld hl,$2000 : ld bc,$2000 : ld a,$AA : call g6_cnt
.k:     ld (.w),hl
        pop hl : ld bc,12 : add hl,bc : pop de
        ld a,(.w) : ld (de),a : inc de : ld a,(.w+1) : ld (de),a : inc de
        ld a,(hl) : inc a : jp nz,.l
        call g6_unmap
        ld hl,(.r) : ld de,(.r+2) : add hl,de : call res_int : ld hl,u_bytes : call res_unit
        ld hl,.kn : ld ix,.r : ld b,4
.kk:    push bc : ld e,(ix+0) : ld d,(ix+1) : push hl : call ex_kd : pop hl
        ld bc,4 : add hl,bc : inc ix : inc ix : pop bc : djnz .kk
        ld hl,(.r) : ld de,(.r+2) : ld a,h : or l : or d : or e : jp nz,g6_fail
        ld hl,(.r+4) : dec hl : ld a,h : or l : jp nz,g6_fail
        ld hl,(.r+6) : dec hl : ld a,h : or l : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; the copy of .cur checked -> HL = wrong bytes (copied bytes that differ, each set back to $AA, + bytes of
; page 39 not $AA)
.chk:   ld hl,0 : ld (.w),hl
        ld a,(.cur+10) : ld b,a
        ld hl,(.cur) : ld de,(.cur+4)
.r1:    push bc : push hl : push de
        ld a,(.cur+8) : ld b,a
.r2:    ld a,(de) : cp (hl) : jr z,.r3
        push hl : ld hl,(.w) : inc hl : ld (.w),hl : pop hl
.r3:    ld a,$AA : ld (de),a : inc hl : inc de : djnz .r2
        pop hl : ld bc,(.cur+6) : add hl,bc : ex de,hl
        pop hl : ld bc,(.cur+2) : add hl,bc
        pop bc : djnz .r1
        ld hl,$2000 : ld bc,$2000 : ld a,$AA : call g6_cnt
        ld de,(.w) : add hl,de : ret
; source (slot 0), A stride, destination (slot 1), B stride, row length, rows
.cs:    dw 16, 256, $2004, 80, 32, 32
        dw 0, 64, $2000+488, 80, 64, 20
        dw 0, 1, $2100, 1, 0, 1
        dw 0, 1, $2100, 1, 1, 0
        db $FF
.cur:   ds 12
.w:     dw 0
.r:     ds 8
.kn:    db "a",0,0,0, "b",0,0,0, "z0l",0, "z0r",0

; ---------------------------------------------------------------- D13 transparent and fill
; 28 MHz, physical, page 38 -> page 39, no timing byte (the reset default); clocks per byte = (t2048 -
; t256) / 1792 as D02. op: an opaque copy of a source whose even bytes are $E3; tr: the same with $E3 the
; transparent colour (bit 2); fi: fill $5A (bit 3); fx: a copy from one fixed source byte $5A (WR1 $24).
; The 2048-byte runs are checked (op: a copy; tr: even bytes still $AA, odd ones copied; fi / fx: all $5A):
; bad = wrong bytes. v = fi. PASS if bad = 0, |tr - op| <= 0.10 (the write cycle is still spent) and
; |2 fi - fx| <= 0.20 (fill takes half the time of a fixed-source copy).
t_d13:  call bl_chk : ret c
        call g6_map
        nextreg $07,3
        ld hl,0 : ld bc,2048 : call g6_pat
        ld hl,0 : ld bc,1024
.e:     ld (hl),$E3 : inc hl : inc hl : dec bc : ld a,b : or c : jr nz,.e
        ld a,$5A : ld ($1000),a
        ld hl,.cs : ld (.p),hl : ld hl,.v : ld (.vp),hl
        ld hl,0 : ld (.bad),hl
.l:     ld hl,(.p) : ld a,(hl) : or a : jr z,.x
        ld (.f),a : inc hl : ld a,(hl) : ld (.bv),a : inc hl : ld a,(hl) : ld (.r1),a : inc hl
        ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld (.s),de : ld (.p),hl
        ld hl,256 : call .time : ld (.t1),hl
        ld hl,$2000 : ld bc,2048 : ld a,$AA : call g6_fill
        ld hl,2048 : call .time
        ld de,(.t1) : or a : sbc hl,de : ld de,0 : ld bc,1792 : call g6_cpb
        ex de,hl : ld hl,(.vp) : ld (hl),e : inc hl : ld (hl),d : inc hl : ld (.vp),hl
        call .chk : ld de,(.bad) : add hl,de : ld (.bad),hl
        jr .l
.x:     call g6_unmap
        ld hl,(.v+4) : ld de,0 : call res_num : ld hl,u_clocks : call res_unit
        ld hl,.kn : ld ix,.v : ld b,4
.kk:    push bc : push hl : ld (g6k),hl : ld l,(ix+0) : ld h,(ix+1) : ld de,0 : call g6_kfix
        pop hl : inc hl : inc hl : inc hl : inc ix : inc ix : pop bc : djnz .kk
        ld de,(.bad) : ld hl,k_bad : call ex_kd
        ld hl,(.bad) : ld a,h : or l : jp nz,g6_fail
        ld hl,(.v+2) : ld de,(.v) : call bl_abs : ld de,11 : or a : sbc hl,de : jp nc,g6_fail
        ld hl,(.v+4) : add hl,hl : ld de,(.v+6) : call bl_abs : ld de,21 : or a : sbc hl,de : jp nc,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; HL = bytes -> HL = ticks of one transfer of this case
.time:  ld (.n),hl
        ld a,(.f) : call bl_def
        ld a,(.bv) : ld (blv),a : ld a,(.r1) : ld (g6r1),a
        ld hl,(.s) : ld (g6s),hl : ld hl,$E000 : ld (g6d),hl : ld hl,(.n) : ld (g6n),hl
        jp bl_go
; -> HL = wrong bytes of the 2048-byte run
.chk:   ld a,(.r1) : cp $24 : jr z,.c5
        ld a,(.f) : cp 9 : jr z,.c5
        cp 5 : jr z,.ct
        ld hl,0 : ld de,$2000 : ld bc,2048 : jp g6_cmp
.c5:    ld hl,$2000 : ld bc,2048 : ld a,$5A : jp g6_cnt
.ct:    ld hl,0 : ld (.w),hl : ld de,$2000 : ld b,0 : ld c,4
.t1l:   ld a,(de) : cp $AA : call nz,.inc
        inc hl : inc de : ld a,(de) : cp (hl) : call nz,.inc
        inc hl : inc de : djnz .t1l
        dec c : jr nz,.t1l
        ld hl,(.w) : ret
.inc:   push hl : ld hl,(.w) : inc hl : ld (.w),hl : pop hl : ret
; flags, colour / fill value, WR1, source (16-bit physical, extended byte $08)
.cs:    db 1,0,$14 : dw $C000
        db 5,$E3,$14 : dw $C000
        db 9,$5A,$14 : dw $C000
        db 1,0,$24 : dw $D000
        db 0
.p:     dw 0
.vp:    dw 0
.v:     ds 8
.f:     db 0
.bv:    db 0
.r1:    db 0
.s:     dw 0
.n:     dw 0
.t1:    dw 0
.w:     dw 0
.bad:   dw 0
.kn:    db "op",0, "tr",0, "fi",0, "fx",0
k_bad:  db "bad",0

; ---------------------------------------------------------------- D14 Layer 2 X,Y
; NextReg $12 = 22 (Layer 2 from page 44: the suite's Layer 2 pages 44-53; Layer 2 stays off), a source
; 1..16 at page 38 +$400; a 4 x 4 2D copy (A stride 4; B stride forced to 256) placed by $DF $13 (physical,
; 2D, X,Y), X low, X high, Y, sent after WR4: r256 = 256 x 192 ($70 = 0) at (10,10): page 44 +$0A0A on;
; x266 = 256 x 192 at (266,11): only X's low byte counts, page 44 +$0B0A; c320 = 320 x 256 ($70 = $10) at
; (300,10): bank start + 300 x 256 + 10 = page 53 +$0C0A. A transfer row lands 256 on from the one before
; either way (a screen row in 256 x 192, a column in 320 x 256). Per case: the page cleared, the copy, the
; 16 places checked and every other byte of the page still 0 (wrong bytes). v = the three together; PASS
; if 0. $12 / $70 back from the launch snapshot (restore_all).
t_d14:  call bl_chk : ret c
        call g6_map
        nextreg $07,3
        nextreg $12,22
        ld hl,$0400 : ld b,16 : ld a,1
.s:     ld (hl),a : inc hl : inc a : djnz .s
        ld hl,.cs : ld de,.r
.l:     push de
        ld a,(hl) : inc hl : nextreg $70,a
        ld a,(hl) : ld (.x),a : inc hl : ld a,(hl) : ld (.x+1),a : inc hl : ld a,(hl) : ld (.y),a : inc hl
        ld a,(hl) : ld (.pg),a : inc hl : ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld (.of),de
        push hl
        ld a,(.pg) : nextreg $51,a
        ld hl,$2000 : ld bc,$2000 : xor a : call g6_fill
        ld hl,.pr : ld b,.pre-.pr : ld c,$6B : otir
        ld a,$C3 : out ($6B),a
        call .chk : ld (.w),hl
        nextreg $51,39
        pop hl : pop de
        ld a,(.w) : ld (de),a : inc de : ld a,(.w+1) : ld (de),a : inc de
        ld a,(hl) : inc a : jr nz,.l
        call g6_unmap
        ld hl,(.r) : ld de,(.r+2) : add hl,de : ld de,(.r+4) : add hl,de : ld (.w),hl
        call res_int : ld hl,u_bytes : call res_unit
        ld hl,.kn : ld ix,.r : ld b,3
.kk:    push bc : ld e,(ix+0) : ld d,(ix+1) : push hl : call ex_kd : pop hl
        ld bc,5 : add hl,bc : inc ix : inc ix : pop bc : djnz .kk
        ld hl,(.w) : ld a,h : or l : jp nz,g6_fail
        ld a,ST_PASS : ld (R_st),a : ret
; -> HL = wrong bytes (the 16 places checked and cleared, then the page's other bytes)
.chk:   ld hl,0 : ld (.w),hl
        ld hl,(.of) : ld de,$2000 : add hl,de
        ld c,1 : ld b,4
.c1:    push bc : push hl : ld b,4
.c2:    ld a,(hl) : cp c : jr z,.c3
        push hl : ld hl,(.w) : inc hl : ld (.w),hl : pop hl
.c3:    ld (hl),0 : inc hl : inc c : djnz .c2
        ld a,c : pop hl : inc h : pop bc : ld c,a : djnz .c1
        ld hl,$2000 : ld bc,$2000 : xor a : call g6_cnt
        ld de,(.w) : add hl,de : ret
.pr:    db $C3, $D7,$08, $E3,4,0, $E7,4,0, $EB,4,0
        db $7D, $00,$C4, $10,$00, $14, $10, $AD, $00,$00
        db $DF, $13
.x:     db 0,0
.y:     db 0
        db $82, $CF, $87
.pre:
; $70, X low, X high, Y, page, offset in the page
.cs:    db 0, 10,0, 10, 44 : dw $0A0A
        db 0, 10,1, 11, 44 : dw $0B0A
        db $10, $2C,1, 10, 53 : dw $0C0A
        db $FF
.pg:    db 0
.of:    dw 0
.w:     dw 0
.r:     ds 6
.kn:    db "r256",0, "x266",0, "c320",0
