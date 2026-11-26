; nxsuite/g5.asm - G5 COPPER: P01-P10 (spec section 3 G5). GPL-3.0-or-later.
; Slot-7 overlay. Copper lists are written through NextReg $60 with $61 / $62 = 0 first (stopped, index 0);
; WAIT = $80 | h << 1 | v >> 8, v & 255; MOVE = register, value; HALT = $FF,$FF. The CPU sees the copper
; through NextReg $7F. Timing uses CTC3 (port $1B3B): control $07 = /16 (one tick = 16 clocks of 28 MHz),
; control $27 = /256; time constant 0 = 256; it counts down. Interrupts off throughout; the harness stops
; the copper and puts $7F, $43 back afterwards; $40 and the palette entries these tests write are put back
; here. P08 runs the LDIR+COP timing row in G7 BENCH, not here (spec: "from BENCH group").

G5PAL   equ $F600               ; 512 bytes: P08's saved sprite palette 2 (8-bit value, 9th-bit byte)

; ---------------------------------------------------------------- helpers
; HL = list, BC = bytes: copper stopped, index 0, list written, index 0 again
g5_up:  nextreg $62,0 : nextreg $61,0
.l:     ld a,(hl) : nextreg $60,a : inc hl : dec bc : ld a,b : or c : jr nz,.l
        nextreg $61,0 : ret
; HL = line -> returns when the raster reaches that line of the next frame
g5_at:  push hl : call frame_sync : pop hl
        ld a,h : or a : jr z,.lo
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.m:     in a,(c) : rra : jr nc,.m
.lo:    ld a,l : jp sync_lsb
; A = CTC3 control ($07 or $27): CTC3 started with time constant 256
g5_ctc: ld bc,$1B3B : out (c),a : xor a : out (c),a : ret
; D = start value, E = end value of $7F (CTC3 running /16) -> HL = ticks between the CPU first seeing D
; and first seeing E, $FFFF if D or E never came (guards: 65536 polls for D, 255 counter wraps for E)
g5_sw:  ld bc,$243B : ld a,$7F : out (c),a : ld c,$3B
        ld hl,0
.s:     ld b,$25 : in a,(c) : cp d : jr z,.st
        dec hl : ld a,h : or l : jr nz,.s
        jr .to
.st:    ld b,$1B : in a,(c) : ld (.c0),a : ld h,a       ; H = the last counter value
        ld l,0                                          ; L = wraps
.e:     ld b,$1B : in a,(c) : cp h : ld h,a : jr c,.n : jr z,.n
        inc l : jr z,.to                                ; the count went up: a wrap
.n:     ld b,$25 : in a,(c) : cp e : jr nz,.e
        ld a,(.c0) : sub h : ld e,a : ld d,0 : jr nc,.p
        dec d
.p:     ld h,l : ld l,0 : add hl,de : ret
.to:    ld hl,$FFFF : ret
.c0:    db 0
; (g5k) = key, DEHL = value x 100 -> " key=<fixed>"
g5_kfix:
        ld (g5v),hl : ld (g5v+2),de
        ld hl,(g5k) : call ex_k
        ld hl,(g5v) : ld de,(g5v+2) : jp wfix
g5v:    ds 4
g5k:    dw 0
; HL = key, DE = signed integer -> " key=<n>" ("-" in front when negative)
g5_ksd: bit 7,d : jp z,ex_kd
        push de : call ex_k : ld a,'-' : call wchr : pop de
        xor a : sub e : ld l,a : ld a,0 : sbc a,d : ld h,a : jp wdec
g5_fail: ld a,ST_FAIL : ld (R_st),a : ret
; HL = key, DE = value -> " key=<decimal>", $FFFF as "-" (never seen)
g5_kl:  ld a,d : and e : inc a : jp nz,ex_kd
        call ex_k : ld a,'-' : jp wchr

; the value log: P01 / P02. Polls $7F and the raster line (28 MHz) until $7F = (g5end) or 3 frames
; passed; for $7F values 1-3 the frame of the first sighting and the raster line read just before and just
; after that $7F read (g5ll / g5lh / g5lf; $FFFF / $FF = never): the change happened on one of the two
g5_log: ld hl,g5ll : ld de,g5ll+1 : ld bc,8+8+4-1 : ld (hl),$FF : ldir
        xor a : ld (.fr),a : ld (.lv),a
        ld hl,0 : ld (.pl),hl
.p:     call line : ld (.pb),hl
        ld a,$7F : call rdreg : ld (.v),a
        call line : push hl
        ld de,(.pl) : or a : sbc hl,de : pop hl : ld (.pl),hl : jr nc,.nf
        ld a,(.fr) : inc a : ld (.fr),a : cp 3 : ret nc
.nf:    ld a,(.v) : ld e,a
        ld a,(.lv) : cp e : jr z,.p
        ld a,e : ld (.lv),a
        cp 4 : jr nc,.ck
        or a : jr z,.ck
        ld c,a : ld b,0 : ld ix,g5lf : add ix,bc
        ld a,(ix+0) : inc a : jr nz,.ck                 ; seen before
        ld a,(.fr) : ld (ix+0),a
        ld ix,g5ll : add ix,bc : add ix,bc
        ld hl,(.pb) : ld (ix+0),l : ld (ix+1),h
        ld hl,(.pl) : ld (ix+8),l : ld (ix+9),h
.ck:    ld a,(g5end) : cp e : jr nz,.p
        ret
.fr:    db 0
.v:     db 0
.lv:    db 0
.pl:    dw 0
.pb:    dw 0
g5ll:   ds 8                    ; line before the read that saw value 0-3 (0 unused)
g5lh:   ds 8                    ; line after it
g5lf:   ds 4                    ; frame of value 0-3
g5end:  db 0
; A = value -> DE = its line from the log
g5_ln:  ld l,a : ld h,0 : add hl,hl : ld de,g5ll : add hl,de
        ld e,(hl) : inc hl : ld d,(hl) : ret
; A = value -> DE = the line after
g5_lnh: ld l,a : ld h,0 : add hl,hl : ld de,g5lh : add hl,de
        ld e,(hl) : inc hl : ld d,(hl) : ret
; A = value, HL = line -> Z if the line before or after the sighting is that line
g5_is:  push hl : push af : call g5_ln : pop af : pop hl : push hl
        ex de,hl : or a : sbc hl,de : pop hl : ret z
        push hl : call g5_lnh : pop hl
        ex de,hl : or a : sbc hl,de : ret
; A = value -> A = its frame from the log
g5_fr:  ld l,a : ld h,0 : ld de,g5lf : add hl,de : ld a,(hl) : ret
; key table for lines 1-3
; " lN=<line before>" and, when the line after differs, " lNn=<line after>"
g5_l3:  ld a,1 : ld hl,k_l1 : call .one
        ld a,2 : ld hl,k_l2 : call .one
        ld a,3 : ld hl,k_l3
.one:   ld (.a),a : ld (.k),hl
        call g5_ln : ld (.d),de : ld hl,(.k) : call g5_kl
        ld a,(.a) : call g5_lnh : ld hl,(.d) : or a : sbc hl,de : ret z
        ld hl,(.k) : ld bc,3 : add hl,bc : jp g5_kl
.a:     db 0
.k:     dw 0
.d:     dw 0
k_l1:   db "l1",0,"l1n",0
k_l2:   db "l2",0,"l2n",0
k_l3:   db "l3",0,"l3n",0

; ---------------------------------------------------------------- P01 WAIT for a line already passed
; MOVE $7F,1; WAIT 150; MOVE $7F,2; WAIT 50; MOVE $7F,3; HALT, started (mode 01) at line 10; the CPU logs
; the line / frame each value was first seen. Choice: holds (3 at line 50 of the next frame), no-wait (3 in
; the frame of 2, within 2 lines of 150), other. (A line read before and one after each $7F read: lN / lNn.)
t_p01:  nextreg $07,3 : nextreg $7F,0
        ld hl,.cl : ld bc,.cle-.cl : call g5_up
        ld a,3 : ld (g5end),a
        ld hl,10 : call g5_at
        nextreg $62,$40
        call g5_log
        nextreg $62,0
        call g5_l3
        ld a,3 : call g5_fr : ld c,a : ld a,2 : call g5_fr : ld b,a
        ld a,c : sub b : ld e,a : ld d,0 : ld hl,k_df : push bc : call ex_kd : pop bc
        ld hl,w5_other
        ld a,b : inc a : jr z,.w                        ; 2 never seen
        ld a,c : inc a : jr z,.w
        ld a,c : cp b : jr z,.same
        ld a,3 : ld hl,50 : call g5_is : jr nz,.oth
        ld hl,w5_holds : jr .w
.same:  ld a,3 : call g5_ln : ld hl,-150 : add hl,de : ld a,h : or a : jr nz,.oth
        ld a,l : cp 3 : jr nc,.oth
        ld hl,w5_nowait : jr .w
.oth:   ld hl,w5_other
.w:     jp res_word
.cl:    db $7F,1, $80|(150>>8),150&255, $7F,2, $80,50, $7F,3, $FF,$FF
.cle:
w5_holds: db "holds",0
w5_nowait: db "no-wait",0
w5_other: db "other",0
k_df:   db "frames23",0

; ---------------------------------------------------------------- P02 two WAITs on one line
; WAIT (100, h 50); MOVE $7F,1; WAIT (100, h 10); MOVE $7F,2; HALT. PASS if 2 was first seen on line 100
; (the second WAIT, h already passed on the same line, did not hold for a frame); l1 = where 1 was seen
; ("-": 2 followed within the same poll, as it should).
t_p02:  nextreg $07,3 : nextreg $7F,0
        ld hl,.cl : ld bc,.cle-.cl : call g5_up
        ld a,2 : ld (g5end),a
        ld hl,10 : call g5_at
        nextreg $62,$40
        call g5_log
        nextreg $62,0
        call g5_l3
        ld a,2 : call g5_ln : ex de,hl : call res_int
        ld a,2 : ld hl,100 : call g5_is : jp nz,g5_fail
        ld a,ST_PASS : ld (R_st),a : ret
.cl:    db $80|(50<<1),100, $7F,1, $80|(10<<1),100, $7F,2, $FF,$FF
.cle:
; ---------------------------------------------------------------- P03 the largest WAIT h
; for h = 48..63: WAIT (100, h); MOVE $7F,h; HALT (mode 01); $7F read at line 101 of the next frame.
; INFO v = the largest h that ran ($FF none); hits = a 16-bit mask, bit n = h 48 + n ran.
t_p03:  nextreg $07,3
        ld hl,0 : ld (.m),hl
        ld a,$FF : ld (.mx),a
        ld a,48
.h:     ld (.cl+3),a : ld (.hh),a
        add a,a : or $80 : ld (.cl),a
        nextreg $7F,0
        ld hl,.cl : ld bc,6 : call g5_up
        ld hl,10 : call g5_at
        nextreg $62,$40
        ld hl,101 : call g5_at
        ld a,$7F : call rdreg : ld b,a
        nextreg $62,0
        ld a,(.hh) : cp b : jr nz,.n
        ld (.mx),a
        sub 48 : ld b,a : ld hl,1 : jr z,.s
.sh:    add hl,hl : djnz .sh
.s:     ld de,(.m) : ld a,l : or e : ld l,a : ld a,h : or d : ld h,a : ld (.m),hl
.n:     ld a,(.hh) : inc a : cp 64 : jr c,.h
        ld a,(.mx) : call res_hex
        ld hl,(.m) : ex de,hl : ld hl,k_hits : jp ex_kd
.cl:    db $80,100, $7F,0, $FF,$FF
.hh:    db 0
.mx:    db 0
.m:     dw 0
k_hits: db "hits",0

; ---------------------------------------------------------------- P04 copper line = raster line
; for L = 0, 120, 191, 250: WAIT (L, 0); MOVE $7F,$AA; HALT started at line 0 (28 MHz); the CPU polls the
; line LSB and $7F in one loop and keeps the CTC3 value (/16) at the first sighting of each; then the line
; read after $AA. PASS if the line equals L every time; extras lL = that line, oL = T (3.5 MHz) from
; the line change to the $7F change (ticks x 2; poll loop resolution ~4 T; negative = $7F first). Each L
; is run in 3 frames: oL = the median, sL = max - min (board run 4 gave o191 = -62 with the other three
; 0, JNext o120 = -74: one-off readings, so one frame per L was not enough).
t_p04:  nextreg $07,3
        ld a,$07 : call g5_ctc
        ld a,1 : ld (.ok),a                         ; v = 1: all four lines equal
        ld hl,.ls
.l:     ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,d : and e : inc a : jp z,.x
        push hl
        ld (.L),de
        ld a,d : or $80 : ld (.cl),a : ld a,e : ld (.cl+1),a
        ld hl,.ov : ld (.op),hl : ld b,3
.f3:    push bc
        nextreg $7F,0
        ld hl,.cl : ld bc,6 : call g5_up
        call frame_sync
        nextreg $62,$40
        call .pl
        push hl : nextreg $62,0 : pop de
        ld (.lr),de
        ld hl,(.L) : or a : sbc hl,de : jr z,.eq
        xor a : ld (.ok),a
.eq:    ld a,(.cc) : ld b,a : ld a,(.cl0) : sub b       ; line change - $7F change, counting down
        ld hl,(.op) : ld (hl),a : inc hl : ld (.op),hl
        pop bc : djnz .f3
        ld de,(.lr) : ld a,(.L) : call .kl : push hl : call g5_kl : pop hl
        call .med : push bc
        ld l,a : ld h,0 : bit 7,a : jr z,.ps
        dec h
.ps:    add hl,hl : ex de,hl
        ld a,(.L) : call .kl : ld bc,5*4 : add hl,bc : push hl : call g5_ksd : pop hl
        ld bc,5*4 : add hl,bc : pop af : add a,a : ld e,a : ld d,0 : jr nc,.sp
        ld de,999
.sp:    call ex_kd
        pop hl : jp .l
.x:     ld a,(.ok) : ld l,a : ld h,0 : call res_int
        ld a,(.ok) : or a : jp z,g5_fail
        ld a,ST_PASS : ld (R_st),a : ret
; poll: -> HL = the line read after $7F = $AA; (.cl0) / (.cc) = CTC at the first sighting of each
.pl:    xor a : ld (.fl),a
        ld ix,0
        ld bc,$243B
.q:     ld b,$1B : in e,(c)
        ld b,$24 : ld a,$1F : out (c),a : inc b : in a,(c)
        ld hl,.L : cp (hl) : jr nz,.q1
        ld a,(.fl) : bit 0,a : jr nz,.q1
        or 1 : ld (.fl),a : ld a,e : ld (.cl0),a
.q1:    ld b,$24 : ld a,$7F : out (c),a : inc b : in a,(c) : cp $AA : jr nz,.q2
        ld a,(.fl) : bit 1,a : jr nz,.q2
        or 2 : ld (.fl),a : ld a,e : ld (.cc),a
        call line : ld (.lr),hl
.q2:    ld a,(.fl) : cp 3 : jr z,.qd
        dec ix : ld a,ixh : or ixl : jr nz,.q
        ld hl,$FFFF : ret
.qd:    ld hl,(.lr) : ret
; A = L & 255 -> HL = "lN" key for this L (N = 0 / 120 / 191 / 250); +20 = "oN"
.kl:    ld hl,.k0 : or a : ret z
        ld hl,.k0+5 : cp 120 : ret z
        ld hl,.k0+10 : cp 191 : ret z
        ld hl,.k0+15 : ret
.ls:    dw 0, 120, 191, 250, $FFFF
.L:     dw 0
; the three offsets (.ov, signed ticks) -> A = the median, B = max - min (ticks)
.med:   ld hl,.ov : ld a,(hl) : xor $80 : ld c,a : inc hl
        ld a,(hl) : xor $80 : ld d,a : inc hl : ld a,(hl) : xor $80 : ld e,a
        ld a,c : cp d : jr c,.m1                    ; C = min(c, d), D = max(c, d)
        ld c,d : ld d,a
.m1:    ld a,e : cp c : jr nc,.m2                   ; E below the min: the min is the median
        ld b,c : ld c,e : jr .m4                    ; (B = median, C = min, D = max)
.m2:    cp d : jr c,.m3                             ; E above the max: the max is the median
        ld b,d : ld d,e : jr .m4
.m3:    ld b,e
.m4:    ld a,d : sub c : push af : ld a,b : xor $80 : pop bc : ret
.ov:    ds 3
.op:    dw 0
.cl:    db $80,0, $7F,$AA, $FF,$FF
.ok:    db 0
.fl:    db 0
.cl0:   db 0
.cc:    db 0
.lr:    dw 0
.k0:    db "l0",0,0,0, "l120",0, "l191",0, "l250",0
        db "o0",0,0,0, "o120",0, "o191",0, "o250",0
        db "s0",0,0,0, "s120",0, "s191",0, "s250",0

; ---------------------------------------------------------------- P05 copper clocks per instruction
; WAIT (100, 0); MOVE $7F,1; 1000 x MOVE $7F,1; MOVE $7F,$AA; HALT: CTC3 (/16) ticks from the CPU's first
; sight of 1 to $AA = 1001 instructions. The same with 1000 x WAIT (100, 0) in place of the MOVEs.
; INFO v = clocks (28 MHz) per MOVE (ticks x 16 / 1001); wait = per WAIT; raw tick counts in mt / wt.
t_p05:  nextreg $07,3
        ld a,$07 : call g5_ctc
        ld hl,$7F01 : call .run : ld (.mt),hl
        ld hl,$8000|(100>>8)<<8|(100&255) : call .run : ld (.wt),hl
        ld hl,(.mt) : call .cpi : call res_num : ld hl,u_clocks : call res_unit
        ld hl,k_wait : ld (g5k),hl : ld hl,(.wt) : call .cpi : call g5_kfix
        ld de,(.mt) : ld hl,k_mt : call ex_kd
        ld de,(.wt) : ld hl,k_wt : jp ex_kd
; HL = ticks -> DEHL = clocks x 100 per instruction ($FFFF ticks -> -1)
.cpi:   ld a,h : and l : inc a : jr nz,.c
        ld hl,-100 : ld de,-1 : ret
.c:     ld b,h : ld c,l : ld de,1600 : call mul16
        ld bc,1001 : jp div32
; HL = the instruction (H = first byte, L = second) repeated 1000 times -> HL = ticks
.run:   ld (.i),hl
        nextreg $7F,0
        nextreg $62,0 : nextreg $61,0
        nextreg $60,$80|(100>>8) : nextreg $60,100&255
        nextreg $60,$7F : nextreg $60,1
        ld de,1000
.w:     ld a,(.i+1) : nextreg $60,a : ld a,(.i) : nextreg $60,a
        dec de : ld a,d : or e : jr nz,.w
        nextreg $60,$7F : nextreg $60,$AA
        nextreg $60,$FF : nextreg $60,$FF
        nextreg $61,0
        ld hl,90 : call g5_at
        nextreg $62,$40
        ld de,$01AA : call g5_sw
        nextreg $62,0
        ret
.i:     dw 0
.mt:    dw 0
.wt:    dw 0
k_wait: db "wait",0
k_mt:   db "mt",0
k_wt:   db "wt",0

; ---------------------------------------------------------------- P06 where mode 11 restarts
; mode 11: MOVE $7F,9; WAIT 200; MOVE $7F,1; HALT; the CPU writes $7F = 0 at line 210 and reads the raster
; line when 9 is seen again. INFO v = that line ($FFFF never).
t_p06:  nextreg $07,3 : nextreg $7F,0
        ld hl,.cl : ld bc,.cle-.cl : call g5_up
        nextreg $62,$C0
        ld hl,210 : call g5_at
        nextreg $7F,0
        ld de,0
.p:     ld a,$7F : call rdreg : cp 9 : jr z,.s
        dec de : ld a,d : or e : jr nz,.p
        ld hl,$FFFF : jr .e
.s:     call line
.e:     push hl : nextreg $62,0 : pop hl
        ld a,h : and l : inc a : jp nz,res_int
        ld a,$FF : jp res_hex
.cl:    db $7F,9, $80|(200>>8),200&255, $7F,1, $FF,$FF
.cle:

; ---------------------------------------------------------------- P07 two MOVEs to $44 make one entry
; Layer 2 first palette entry 200 saved; copper: MOVE $43,$10; MOVE $40,200; MOVE $44,$A5; MOVE $44,$01;
; HALT; then the CPU reads entry 200 ($40 = 200, $41; $44 for the 9th bit). PASS if $41 = $A5; b9 = $44 read.
t_p07:  nextreg $43,$10 : nextreg $40,200
        ld a,$41 : call rdreg : ld (.sv),a
        ld a,$44 : call rdreg : ld (.sv+1),a
        nextreg $62,0
        ld hl,.cl : ld bc,.cle-.cl : call g5_up
        nextreg $62,$40
        ld b,0
.d:     djnz .d
        nextreg $62,0
        nextreg $43,$10 : nextreg $40,200
        ld a,$41 : call rdreg : ld (.r),a
        ld a,$44 : call rdreg : ld (.r+1),a
        nextreg $40,200 : ld a,(.sv) : nextreg $44,a : ld a,(.sv+1) : nextreg $44,a
        ld a,(NRSNAP+$43) : nextreg $43,a : ld a,(NRSNAP+$40) : nextreg $40,a
        ld a,(.r+1) : ld hl,k_b9 : call ex_kh
        ld a,(.r) : call res_hex
        ld a,(.r) : cp $A5 : jp nz,g5_fail
        ld a,ST_PASS : ld (R_st),a : ret
.cl:    db $43,$10, $40,200, $44,$A5, $44,$01, $FF,$FF
.cle:
.sv:    ds 2
.r:     ds 2
k_b9:   db "b9",0

; ---------------------------------------------------------------- P08 CPU palette access with the copper busy
; nextbench CP APART / CP SHARE: the copper loops 1024 x MOVE $7F,$55 (APART) or MOVE $40,0 (SHARE) while
; the CPU writes sprite palette 2 (256 x $41, value i xor $5A) and reads it back; wrong entries counted, at
; 3.5 and 28 MHz. Sprite palette 2 is saved first and written back. PASS if APART = 0 at both speeds;
; v = APART wrong (28 MHz); a35 / a28 / s35 / s28.
t_p08:  call .sv
        xor a : ld (.sp),a : ld de,$7F55 : call .run : ld (.r),a
        xor a : ld (.sp),a : ld de,$4000 : call .run : ld (.r+2),a
        ld a,3 : ld (.sp),a : ld de,$7F55 : call .run : ld (.r+1),a
        ld a,3 : ld (.sp),a : ld de,$4000 : call .run : ld (.r+3),a
        call .rs
        ld a,(.r+1) : ld l,a : ld h,0 : call res_int
        ld hl,.k : ld b,4 : ld ix,.r
.k1:    push bc : ld e,(ix+0) : ld d,0 : push hl : call ex_kd : pop hl
        inc hl : inc hl : inc hl : inc hl : inc ix : pop bc : djnz .k1
        ld a,(.r) : or a : jp nz,g5_fail
        ld a,(.r+1) : or a : jp nz,g5_fail
        ld a,ST_PASS : ld (R_st),a : ret
; D = register, E = value for the copper loop; (.sp) = speed -> A = wrong entries (255 max shown)
.run:   ld a,(.sp) : nextreg $07,a
        nextreg $62,0 : nextreg $61,0 : ld bc,1024
.l:     ld a,d : nextreg $60,a : ld a,e : nextreg $60,a
        dec bc : ld a,b : or c : jr nz,.l
        nextreg $61,0 : nextreg $62,$40
        nextreg $43,%01100000 : nextreg $40,0
        ld e,0
.w:     ld a,e : xor $5A : nextreg $41,a : inc e : jr nz,.w
        ld hl,0 : ld e,0
.rd:    ld a,e : nextreg $40,a
        ld bc,$243B : ld a,$41 : out (c),a : inc b : in a,(c)
        ld d,a : ld a,e : xor $5A : cp d : jr z,.ok
        inc hl
.ok:    inc e : jr nz,.rd
        nextreg $62,0
        ld a,h : or a : ld a,l : ret z
        ld a,255 : ret
; sprite palette 2 -> G5PAL (value, 9th-bit byte) / back
.sv:    nextreg $43,%01100000 : ld hl,G5PAL : ld e,0
.s1:    ld a,e : nextreg $40,a
        ld a,$41 : call rdreg : ld (hl),a : inc hl
        ld a,$44 : call rdreg : ld (hl),a : inc hl
        inc e : jr nz,.s1
        ret
.rs:    nextreg $43,%01100000 : nextreg $40,0 : ld hl,G5PAL : ld b,0
.r1:    ld a,(hl) : nextreg $44,a : inc hl : ld a,(hl) : nextreg $44,a : inc hl : djnz .r1
        ld a,(NRSNAP+$43) : nextreg $43,a : ld a,(NRSNAP+$40) : nextreg $40,a
        ret
.sp:    db 0
.r:     ds 4
.k:     db "a35",0, "a28",0, "s35",0, "s28",0

; ---------------------------------------------------------------- P09 NEXTREG while the copper writes
; 2048 x NEXTREG $7F,0 (8 per DJNZ loop) at 28 MHz timed by CTC3 /256 (one tick = 256 clocks): copper
; stopped, copper looping MOVE $7F,$55, copper looping MOVE $40,0 ($40 put back). INFO v = clocks per
; NEXTREG with the copper stopped (loop share included: + 13/8); mv = looping MOVE $7F; mp = MOVE $40;
; t0 / t1 / t2 = raw ticks (a wrap past 256 ticks would show as a small count: lines l0-l2 cross-check).
t_p09:  nextreg $07,3
        ld de,0 : call .run : ld (.t),a : ld (.ln),hl
        ld de,$7F55 : call .run : ld (.t+1),a : ld (.ln+2),hl
        ld de,$4000 : call .run : ld (.t+2),a : ld (.ln+4),hl
        ld a,(NRSNAP+$40) : nextreg $40,a
        ld a,(.t) : call .cl : call res_num : ld hl,u_clocks : call res_unit
        ld hl,k_mv : ld (g5k),hl : ld a,(.t+1) : call .cl : call g5_kfix
        ld hl,k_mp : ld (g5k),hl : ld a,(.t+2) : call .cl : call g5_kfix
        ld b,3 : ld ix,.t : ld hl,.k
.k1:    push bc : push hl : ld e,(ix+0) : ld d,0 : call ex_kd : pop hl : inc hl : inc hl : inc hl : pop bc
        inc ix : djnz .k1
        ld b,3 : ld ix,.ln
.k2:    push bc : push hl : ld e,(ix+0) : ld d,(ix+1) : call ex_kd : pop hl : inc hl : inc hl : inc hl
        pop bc : inc ix : inc ix : djnz .k2
        ret
; A = ticks -> DEHL = clocks x 100 per NEXTREG = ticks x 256 x 100 / 2048 = ticks x 25 / 2
.cl:    ld l,a : ld h,0 : ld b,h : ld c,l : ld de,25 : call mul16
        srl d : rr e : rr h : rr l : ret
; DE = copper loop register / value (D = 0: copper stopped) -> A = ticks, HL = raster lines
.run:   nextreg $62,0
        ld a,d : or a : jr z,.go
        nextreg $61,0 : ld bc,1024
.l:     ld a,d : nextreg $60,a : ld a,e : nextreg $60,a
        dec bc : ld a,b : or c : jr nz,.l
        nextreg $61,0 : nextreg $62,$40
.go:    ld a,$27 : call g5_ctc
        call line : ld (.l0),hl
        ld bc,$1B3B : in a,(c) : ld (.c0),a
        ld b,0
.n:     nextreg $7F,0 : nextreg $7F,0 : nextreg $7F,0 : nextreg $7F,0
        nextreg $7F,0 : nextreg $7F,0 : nextreg $7F,0 : nextreg $7F,0
        djnz .n
        ld bc,$1B3B : in a,(c) : ld b,a
        ld a,(.c0) : sub b : push af
        call line : ld de,(.l0) : or a : sbc hl,de : jr nc,.lp
        ld de,(flines) : inc de : add hl,de
.lp:    nextreg $62,0
        pop af : ret
.c0:    db 0
.l0:    dw 0
.t:     ds 3
.ln:    ds 6
.k:     db "t0",0, "t1",0, "t2",0, "l0",0, "l1",0, "l2",0
k_mv:   db "mv",0
k_mp:   db "mp",0

; ---------------------------------------------------------------- P10 the same mode again does not restart
; mode 11: MOVE $7F,9; WAIT 150; MOVE $7F,2; HALT; at line 100 the CPU writes $7F = 0, $61 = 0, $62 = $C0;
; $7F read at line 110 of the same frame. PASS if 0 (a restart would have written 9).
t_p10:  nextreg $07,3 : nextreg $7F,0
        ld hl,.cl : ld bc,.cle-.cl : call g5_up
        nextreg $62,$C0
        ld hl,100 : call g5_at
        nextreg $7F,0 : nextreg $61,0 : nextreg $62,$C0
        ld a,110 : call sync_lsb
        ld a,$7F : call rdreg : push af
        nextreg $62,0
        pop af : push af : call res_hex
        pop af : or a : jp nz,g5_fail
        ld a,ST_PASS : ld (R_st),a : ret
.cl:    db $7F,9, $80|(150>>8),150&255, $7F,2, $FF,$FF
.cle:
