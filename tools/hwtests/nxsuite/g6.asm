; nxsuite/g6.asm - G6 DMA: D01-D09 (spec section 3 G6). GPL-3.0-or-later.
; Slot-7 overlay. Scratch: DMA pages 38 / 39 in slots 0 / 1 ($0000-$3FFF, interrupts off; MMU 0 / 1 back
; from the launch snapshot after each test). Programs as nextbench (port $6B, $C3 first; the harness ends
; with $83, $C3 and a $6B read). Times: CTC3 /16 (a tick = 16 clocks of 28 MHz) read in the polling loop,
; wraps counted, so a long transfer is timed too. Not built yet (SKIP not-built): D10-D15 (the blitter's
; copies: no platform here checks them before the board - CSpect 4.5.9 has a zxDDMA, to be used for that)
; and D16 (its rows are in G7 BENCH). Pages 40-43 hold overlay code, so the scratch is 36-39, not 36-43.
; D02 writes sprite pattern memory (pattern 63 onwards; it cannot be read back; nothing shows it).

G6P     equ $F700               ; the program being built (64 bytes)
G6B     equ $F740               ; 7 read-back bytes (D06)

; ---------------------------------------------------------------- helpers
; also starts CTC3 (/16, 256) once: g6_run only reads it (a counter just loaded may read 0 first)
g6_map: nextreg $50,38 : nextreg $51,39 : di
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
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
; gave up
g6_run: ld (.pa+1),hl : ld a,h : or l : ld (.np),a
        ld a,e : ld (.ev),a
        ld hl,0 : ld (g6it),hl : ld (g6it+2),hl
        ld ix,0
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
.t:     ld a,(.c0) : sub h : ld l,a : ld a,e : sbc a,0 : ld h,a : ld a,d : sbc a,0 : ld e,a : ld d,0
        ret
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
; byte absent / 3 / 2 (WR1 and WR2 bit 6 + that byte), 256 and 2048 bytes, at 3.5 and 28 MHz: clocks
; per byte = the slope (t2048 - t256) / 1792. Keys: m / p (memory / port), a / 3 / 2, 35 / 28.
; PASS if "absent" is the 3-cycle setting within 0.10 clocks everywhere (dma-default-cycle-length);
; v = m a 28.
t_d02:  call g6_map
        ld hl,0 : ld bc,2048 : call g6_pat
        ld hl,.tab : ld (.p),hl
        ld a,1 : ld (.ok),a
.l:     ld hl,(.p) : ld a,(hl) : cp $FF : jp z,.x
        ld (.kind),a : inc hl : ld a,(hl) : ld (.tim),a : inc hl : ld a,(hl) : ld (.spd),a : inc hl
        ld (.p),hl
        ld a,(.spd) : nextreg $07,a
        ld hl,256 : call .time : ld (.t1),hl
        ld hl,2048 : call .time
        ld de,(.t1) : or a : sbc hl,de                  ; ticks for 1792 bytes
        ld de,0 : ld bc,1792 : call g6_cpb : ld (.v),hl : ld (.v+2),de
        ; key "<kind><tim><spd>"
        ld a,(.kind) : ld (.kb),a
        ld a,(.tim) : or a : ld a,'a' : jr z,.ka
        ld a,(.tim) : add a,'0'
.ka:    ld (.kb+1),a
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
.n3:    cp 3 : jr nz,.c
        ld hl,(.v) : ld de,(.va) : or a : sbc hl,de : jr nc,.ab
        ex de,hl : ld hl,0 : or a : sbc hl,de
.ab:    ld de,11 : or a : sbc hl,de : jr c,.c           ; |absent - 3| <= 0.10
        xor a : ld (.ok),a
.c:     jp .l
.x:     call g6_unmap
        ld a,(.ok) : or a : jp z,g6_fail
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
.tab:   db 'm',0,0, 'm',3,0, 'm',2,0, 'p',0,0, 'p',3,0, 'p',2,0
        db 'm',0,3, 'm',3,3, 'm',2,3, 'p',0,3, 'p',3,3, 'p',2,3, $FF
.p:     dw 0
.kind:  db 0
.tim:   db 0
.spd:   db 0
.t1:    dw 0
.v:     ds 4
.va:    dw 0
.ok:    db 0
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
        push af : ld hl,256 : ld (g6lim),hl : pop af
        jr nc,.ok
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
        ld a,$83 : out ($6B),a
        ld hl,(g6it) : ld (.i1),hl : ld hl,(g6it+2) : ld (.i1+2),hl
        ; the loop alone for as many wraps (+1)
        ld l,h : ld h,e : inc hl : ld (g6lim),hl            ; wraps = ticks / 256 + 1
        xor a : ld (g6go),a
        ld e,$FF : ld hl,.nev : call g6_run
        ld a,1 : ld (g6go),a : ld hl,256 : ld (g6lim),hl
        ; share x 100 = I1 x 100 / (I0 / 100)
        ld hl,(g6it) : ld de,(g6it+2) : ld bc,100 : call div32
        ld a,h : or l : or d : or e : jr nz,.d
        inc l
.d:     ld b,h : ld c,l
        push bc
        ld hl,(.i1) : ld de,(.i1+2) : call g6_x100
        pop bc : jp div32
.r4:    db 0
.i1:    ds 4
.b:     ds 4
.c:     ds 4
.nev:   db 0
k_cont: db "cont",0
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
; and written back. INFO v = blitter / none / other; FAIL if none and core >= 3.03 ($01 >= $33).
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
