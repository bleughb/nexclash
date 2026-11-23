; nxsuite/core.asm - code that stays in bank 2 ($8000-$AFFF): it may map other pages into slots 3, 6 and 7
; and still runs. Timing core (house raster method of nextbench v3), arithmetic, CRC, esxDOS calls, the
; result text store, the progress record, NextReg restore, the text writer. GPL-3.0-or-later.

; ---------------------------------------------------------------- NextReg read
; A = NextReg -> A = value (BC kept)
rdreg:  push bc
        ld bc,$243B : out (c),a : inc b : in a,(c)
        pop bc
        ret

; ---------------------------------------------------------------- raster (nextbench v3, LEARNINGS 2.3)
; HL = the raster line at the first IN. The MSB only changes where the LSB wraps to 0, so a second LSB
; read not below the first proves H belongs to L; otherwise read again.
line:   push bc
.again: ld bc,$243B : ld a,$1F : out (c),a : inc b : in l,(c)
        dec b : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c)
        cp l : jr c,.again
        pop bc : ret

; return within ~28 T (3.5 MHz) of line 0 starting: wait for line >= 256, then >= 258, then LSB 0
; (house method: needs $64 = 0 and a frame of >= 258 lines - every Next timing has 261+). The first two
; waits time out (rast_bad = 1) so a broken counter cannot hang the program; the last loop is the
; board-proven one, unchanged.
frame_sync:
        push de
        ld bc,$243B : ld a,$1E : out (c),a : inc b
        ld de,0
.a:     in a,(c) : and 1 : jr nz,.a1
        dec de : ld a,d : or e : jr nz,.a
        jr .to
.a1:    dec b : ld a,$1F : out (c),a : inc b
        ld de,0
.b:     in a,(c) : cp 2 : jr nc,.c
        dec de : ld a,d : or e : jr nz,.b
        jr .to
.c:     in a,(c) : or a : jr nz,.c
        pop de
        ret
.to:    ld a,1 : ld (rast_bad),a
        pop de
        ret
rast_bad: db 0

; after frame_sync: wait for LSB = A (A < 256, line 0-255 of this frame), tight loop
sync_lsb:
        ld e,a
        ld bc,$243B : ld a,$1F : out (c),a : inc b
.w:     in a,(c) : cp e : jr nz,.w
        ret

; ---------------------------------------------------------------- measuring
; HL = block (called K times per pass; registers from (mini) before each call), A = K -> HL = the raster
; lines after the K calls, 4 passes started a quarter line apart, added. (msline) = 0: start at line 0,
; else at line (msline) of the frame. (mshift) = CPU speed 0-3 (the quarter-line delay is scaled).
measure:
        ld (.call+1),hl : ld (mk),a
        ld hl,0 : ld (msum),hl : xor a : ld (mpass),a
.pass:  call frame_sync
        ld a,(msline) : or a : call nz,sync_lsb
        ld a,(mpass) : add a,a : add a,a : inc a : ld b,a  ; 1, 5, 9, 13 x 13 T
        ld a,(mshift) : or a : jr z,.dl
.sh:    sla b : dec a : jr nz,.sh
.dl:    djnz .dl
        ld a,(mk) : ld (mcnt),a
.l:     ld (msp),sp
        ld sp,(mini) : pop af : pop bc : pop de : pop hl
        ld sp,(msp)
.call:  call 0
        ld a,(mcnt) : dec a : ld (mcnt),a : jr nz,.l
        call line
        ld de,(msum) : add hl,de : ld (msum),hl
        ld a,(mpass) : inc a : ld (mpass),a : cp 4 : jr nz,.pass
        ld hl,(msum)
        ret
mk:     db 0
mcnt:   db 0
mpass:  db 0
msum:   dw 0
msp:    dw 0
mini:   dw zini
msline: db 0
mshift: db 0
zini:   ds 8                    ; F A C B E D L H for a row that needs nothing

; Build a block at DE: (mk_pro) bytes, (mk_n) copies of (mk_body), (mk_epi) bytes, RET -> DE after it
mkblk:  ld hl,(mk_pro) : ld a,(mk_prol) : call .cp
        ld bc,(mk_n)
.n:     ld a,b : or c : jr z,.e
        push bc
        ld hl,(mk_body) : ld a,(mk_bodyl) : call .cp
        pop bc : dec bc : jr .n
.e:     ld hl,(mk_epi) : ld a,(mk_epil) : call .cp
        ld a,$C9 : ld (de),a : inc de
        ret
.cp:    or a : ret z
        ld c,a : ld b,0 : ldir
        ret
mk_pro:  dw 0
mk_prol: db 0
mk_body: dw 0
mk_bodyl: db 0
mk_n:    dw 0
mk_epi:  dw 0
mk_epil: db 0

; A row: body bytes (mk_body/mk_bodyl), (mk_n) copies, with the prologue / epilogue set; builds the
; block at TBUF and the same without the copies at TBUF2.
mkrow:  ld de,TBUF : call mkblk
        ld hl,(mk_n) : push hl
        ld hl,0 : ld (mk_n),hl
        ld de,TBUF2 : call mkblk
        pop hl : ld (mk_n),hl
        ld hl,TBUF : ld (tr_blk),hl
        ld hl,TBUF2 : ld (tr_emp),hl
        ret

; Five runs of (tr_blk) against (tr_emp), (tr_k) calls each, at the speed in force ((mshift) set):
; per run x100 = d * (tr_num) / (cal), d = lines(block) - lines(empty) (4 passes each).
; -> tr_mean / tr_min / tr_max (dwords, x 100), tr_d = the last run's d.
; tr_num = 1900 x M where 2048 x 2^speed / M instructions are timed (M = 1: 2048 x 2^speed).
trow:   ld hl,0 : ld (tr_sum),hl : ld (tr_sum+2),hl : ld (tr_max),hl : ld (tr_max+2),hl
        dec hl : ld (tr_min),hl : ld (tr_min+2),hl
        ld a,5 : ld (tr_run),a
.run:   ld hl,(tr_blk) : ld a,(tr_k) : call measure : push hl
        ld hl,(tr_emp) : ld a,(tr_k) : call measure
        ex de,hl : pop hl : or a : sbc hl,de : jr nc,.p
        ld hl,0
.p:     ld (tr_d),hl
        ex de,hl : ld bc,(tr_num) : call mul16          ; DEHL = d * num
        ld bc,(cal) : ld a,b : or c : jr nz,.c
        inc bc
.c:     call div32                                      ; / cal
        ld (tr_x),hl : ld (tr_x+2),de
        ; sum += x
        ld bc,(tr_sum) : add hl,bc : ld (tr_sum),hl
        ex de,hl : ld bc,(tr_sum+2) : adc hl,bc : ld (tr_sum+2),hl
        ; min / max (unsigned)
        ld hl,tr_x : ld de,tr_min : call cmp32 : jr nc,.nmin  ; x < min ?
        ld hl,tr_x : ld de,tr_min : ld bc,4 : ldir
.nmin:  ld hl,tr_max : ld de,tr_x : call cmp32 : jr nc,.nmax  ; max < x ?
        ld hl,tr_x : ld de,tr_max : ld bc,4 : ldir
.nmax:  ld a,(tr_run) : dec a : ld (tr_run),a : jp nz,.run
        ld hl,(tr_sum) : ld de,(tr_sum+2) : ld c,5 : call div8
        ld (tr_mean),hl : ld (tr_mean+2),de
        ret
; (HL) dword < (DE) dword (unsigned) -> carry (BC, A changed)
cmp32:  push hl : push de
        inc hl : inc hl : inc hl : inc de : inc de : inc de
        ld b,4
.l:     ld a,(de) : ld c,a : ld a,(hl) : cp c : jr nz,.d
        dec hl : dec de : djnz .l
        or a
.d:     pop de : pop hl : ret
tr_blk: dw 0
tr_emp: dw 0
tr_k:   db 8
tr_num: dw 1900
tr_run: db 0
tr_d:   dw 0
tr_x:   ds 4
tr_sum: ds 4
tr_min: ds 4
tr_max: ds 4
tr_mean: ds 4
cal:    dw 0                    ; lines of 2048 x LD A,(IX+0) minus nothing, 4 passes, 3.5 MHz

; ---------------------------------------------------------------- arithmetic (plain Z80, nextbench)
mul16:  ld hl,0 : ld a,16                              ; BC * DE -> DEHL
.l:     add hl,hl : rl e : rl d : jr nc,.n
        add hl,bc : jr nc,.n
        inc de
.n:     dec a : jr nz,.l
        ret
div32:  ld a,32                                        ; DEHL / BC -> DEHL (rem in (rem))
        push hl : ld hl,0 : ld (rem),hl : pop hl
.l:     add hl,hl : rl e : rl d
        push hl
        ld hl,(rem) : adc hl,hl : jr c,.big
        or a : sbc hl,bc : jr nc,.ok
        add hl,bc : ld (rem),hl : pop hl : jr .n
.big:   or a : sbc hl,bc
.ok:    ld (rem),hl : pop hl : inc l
.n:     dec a : jr nz,.l
        ret
rem:    dw 0
div8:   push bc                                        ; DEHL / C -> DEHL, A = remainder
        xor a : ld b,32
.l:     add hl,hl : rl e : rl d : rla
        cp c : jr c,.n
        sub c : inc l
.n:     djnz .l
        pop bc
        ret
; DEHL = -DEHL
neg32:  ld a,l : cpl : ld l,a : ld a,h : cpl : ld h,a
        ld a,e : cpl : ld e,a : ld a,d : cpl : ld d,a
        inc l : ret nz
        inc h : ret nz
        inc e : ret nz
        inc d : ret
; HL (unsigned) x 100 -> DEHL
x100:   ld b,h : ld c,l : ld de,100 : jp mul16

; ---------------------------------------------------------------- CRC-16/CCITT (poly $1021, init $FFFF)
crc_init:
        ld hl,CRCTAB : ld c,0
.i:     ld d,c : ld e,0 : ld b,8
.b:     sla e : rl d : jr nc,.n
        ld a,d : xor $10 : ld d,a : ld a,e : xor $21 : ld e,a
.n:     djnz .b
        ld (hl),e : inc hl : ld (hl),d : inc hl
        inc c : jr nz,.i
        ret
; A = byte -> (crc) updated (all registers but AF kept)
crcb:   push hl : push de
        ld hl,(crc)
        xor h : ld e,l
        ld l,a : ld h,0 : add hl,hl : ld a,h : add a,CRCTAB>>8 : ld h,a
        ld a,(hl) : inc hl : ld d,(hl)
        ld l,a : ld a,d : xor e : ld h,a
        ld (crc),hl
        pop de : pop hl
        ret
crc:    dw $FFFF

; ---------------------------------------------------------------- esxDOS (spec 1.1, asm/inferno_hooks.asm sd_esx)
; L = function, A / B / BC / IX as the call -> A, BC, carry. Interrupts off, IM 1, I = launch value,
; ROM in slots 0 and 1, IY = $5C3A, alternate set kept; DI again after (the API may enable interrupts).
esx:    push af
        ld a,l : ld (.fn),a
        ld a,$50 : call rdreg : ld (.m0),a
        ld a,$51 : call rdreg : ld (.m1),a
        nextreg $50,$FF
        nextreg $51,$FF
        ld a,(launch_i) : ld i,a
        im 1
        pop af
        push iy
        ld iy,$5C3A
        exx : push bc : push de : push hl : exx
        ex af,af' : push af : ex af,af'
        rst 8
.fn:    db 0
        di
        ex af,af' : pop af : ex af,af'
        exx : pop hl : pop de : pop bc : exx
        pop iy
        push af
        ld a,(.m0) : nextreg $50,a
        ld a,(.m1) : nextreg $51,a
        pop af
        ret
.m0:    db 0
.m1:    db 0
launch_i: db $3F
ovlpage: db HOMEP7              ; the page in slot 7 while a test runs (its group's overlay, else HOMEP7)

; HL = name, B = mode ($01 read, $0E write + create / truncate) -> A = handle, carry = error
f_open: push hl : pop ix
        ld a,'*' : ld l,$9A : jp esx
f_read: ld l,$9D : jp esx                              ; A = handle, IX = buffer, BC = length -> BC read
f_write: ld l,$9E : jp esx                             ; A = handle, IX = buffer, BC = length
f_close: ld l,$9B : jp esx                             ; A = handle

; ---------------------------------------------------------------- the result text (8 pages, 64 KB)
; append BC bytes from HL (bank 2 / bank 5 / slot 7 source; never slot 6) -> txtlen, crc, txtlines
txt_append:
        ld a,b : or c : ret z
        ld a,(txtfull) : or a : ret nz
.l:     push bc
        ld a,(hl) : inc hl : push hl
        push af : call crcb : pop af
        cp 10 : jr nz,.nl
        ld de,(txtlines) : inc de : ld (txtlines),de
.nl:    push af
        ld hl,(txtlen) : call txt_map               ; HL = address in slot 6
        pop af : ld (hl),a
        ld hl,(txtlen) : inc hl : ld (txtlen),hl
        ld a,h : cp $FF : jr nz,.ok                  ; 65280 bytes: full (room for the END line)
        ld a,1 : ld (txtfull),a
.ok:    pop hl : pop bc
        dec bc : ld a,b : or c : jr nz,.l
        nextreg $56,HOMEP6
        ret
; HL = offset in the text -> the page mapped into slot 6, HL = address there
txt_map:
        push de
        ld a,h : rlca : rlca : rlca : and 7
        ld e,a : ld d,0
        push hl : ld hl,txtpg : add hl,de : ld a,(hl) : pop hl
        nextreg $56,a
        ld a,h : and $1F : or $C0 : ld h,a
        pop de
        ret
; HL = offset -> A = the byte there (slot 6 back home)
txt_peek:
        push hl : call txt_map : ld a,(hl) : pop hl
        nextreg $56,HOMEP6
        ret
txtpg:  db 32,33,34,35,58,59,60,61
txtlen: dw 0
txtlines: dw 0
txtfull: db 0

; write the text + an END line to NXSUITE.TXT (the END line is not kept in the buffer) -> carry = error
txt_flush:
        ld hl,(txtlen) : ld (.len),hl
        ld hl,(crc) : ld (.crc),hl
        ld hl,(txtlines) : ld (.lin),hl
        ld a,(txtfull) : ld (.full),a
        xor a : ld (txtfull),a
        call endline                                ; END line into LB, HL = LB, BC = length
        call txt_append
        ld hl,txtname : ld b,$0E : call f_open : jr c,.out
        ld (.h),a
        ld hl,0                                     ; offset written
.p:     ld de,(txtlen) : ex de,hl : or a : sbc hl,de : jr z,.cl   ; remaining = len - offset
        ld a,h : cp $20 : jr c,.lt
        ld hl,$2000
.lt:    ld b,h : ld c,l                              ; BC = this page's bytes
        push de : push bc
        ex de,hl : call txt_map                     ; slot 6 = the page of this offset
        push hl : pop ix
        ld a,(.h) : call f_write
        nextreg $56,HOMEP6
        pop de : pop hl                             ; DE = asked, HL = offset
        jr c,.err
        ex de,hl : or a : sbc hl,bc : ex de,hl     ; written = asked?
        jr nz,.errs
        add hl,bc : jr .p
.cl:    ld hl,(txtlen) : ld (PRGB+PRG_FLEN),hl      ; the file's length (END included), for txt_load
        ld a,(.h) : call f_close
        call prg_write
        or a
        jr .out
.errs:  scf
.err:   push af : ld a,(.h) : call f_close : pop af : scf
.out:   push af
        ld hl,(.len) : ld (txtlen),hl
        ld hl,(.crc) : ld (crc),hl
        ld hl,(.lin) : ld (txtlines),hl
        ld a,(.full) : ld (txtfull),a
        nextreg $56,HOMEP6
        pop af
        ret
.len:   dw 0
.crc:   dw 0
.lin:   dw 0
.full:  db 0
.h:     db 0
txtname: db "NXSUITE.TXT",0
prgname: db "NXSUITE.PRG",0

; "END lines=<n> crc16=$hhhh" + LF into LB -> HL = LB, BC = length
endline:
        call w_lb
        ld hl,s_end : call wstr
        ld hl,(txtlines) : call wdec
        ld hl,s_crc : call wstr
        ld a,'$' : call wchr
        ld hl,(crc) : call whex4
        ld a,10 : call wchr
        jp w_len
s_end:  db "END lines=",0
s_crc:  db " crc16=",0

; read NXSUITE.TXT into the text buffer and check it: "NXSUITE 1" first, an END line whose line count and
; CRC match. -> A = 0 no file, 1 a good file (END dropped, crc / lines / txtlen set for appending), 2 a
; file that is not right (txtlen = 0).
txt_load:
        xor a : ld (txtfull),a
        ld hl,0 : ld (txtlen),hl
        ld hl,txtname : ld b,$01 : call f_open
        jr nc,.op
        xor a : ret                                  ; no file
.op:    ld (.h),a
        ; read exactly the length the progress record holds (never past the end of the file), 256 bytes
        ; at a time into WORK (bank 5), copied to the text page
        ld hl,0
.p:     ld de,(PRGB+PRG_FLEN) : ex de,hl : or a : sbc hl,de : ex de,hl : jr z,.cl   ; DE = remaining
        jr c,.cl
        ld a,h : cp $E0 : jr nc,.cl                  ; at most 7 pages read back
        ld a,d : or a : jr z,.lt
        ld de,256
.lt:    push hl : push de
        ld ix,WORK : ld b,d : ld c,e : ld a,(.h) : call f_read
        pop de : pop hl
        jr c,.cl
        ld a,b : cp d : jr nz,.cl                    ; fewer bytes than asked: stop
        ld a,c : cp e : jr nz,.cl
        push de : push hl
        ld b,e : ld de,WORK                          ; B = count (256 = 0)
.cp:    push hl : call txt_map : ld a,(de) : ld (hl),a : pop hl
        inc hl : inc de : djnz .cp
        nextreg $56,HOMEP6
        pop hl : pop de
        add hl,de : ld (txtlen),hl
        jr .p
.cl:    ld a,(.h) : call f_close
        ; scan: CRC and lines over the text up to "END " at a line start
        ld hl,$FFFF : ld (crc),hl
        ld hl,0 : ld (txtlines),hl
        ld hl,0 : ld (.end),hl
        ld a,1 : ld (.bol),a
.s:     ld de,(txtlen) : push hl : or a : sbc hl,de : pop hl : jp nc,.bad   ; no END line
        ld a,(.bol) : or a : jr z,.nb
        call txt_peek : cp 'E' : jr nz,.nb
        inc hl : call txt_peek : dec hl : cp 'N' : jr nz,.nb
        inc hl : inc hl : call txt_peek : dec hl : dec hl : cp 'D' : jr nz,.nb
        inc hl : inc hl : inc hl : call txt_peek : dec hl : dec hl : dec hl : cp ' ' : jr z,.fe
.nb:    call txt_peek
        push af : call crcb : pop af                 ; (crcb changes A)
        ld b,0 : cp 10 : jr nz,.nl
        inc b
        ld de,(txtlines) : inc de : ld (txtlines),de
.nl:    ld a,b : ld (.bol),a
        inc hl : jr .s
.fe:    ld (.end),hl
        ; the END line as it should be, compared with the file
        push hl
        call endline                                ; LB, BC = length
        pop de                                      ; DE = offset of END in the file
        ld hl,LB
.c:     ld a,(hl) : push hl : ex de,hl : push af : call txt_peek : ld b,a : pop af : ex de,hl : pop hl
        cp b : jr nz,.bad
        inc hl : inc de : dec c : jr nz,.c
        ; the first line must be "NXSUITE 1"
        ld hl,0 : ld de,s_magic
.m:     ld a,(de) : or a : jr z,.good
        call txt_peek : ex de,hl : cp (hl) : ex de,hl : jr nz,.bad
        inc hl : inc de : jr .m
.good:  ld hl,(.end) : ld (txtlen),hl
        ld a,1 : ret
.bad:   ld hl,0 : ld (txtlen),hl : ld (txtlines),hl
        ld hl,$FFFF : ld (crc),hl
        ld a,2 : ret
.h:     db 0
.end:   dw 0
.bol:   db 0
s_magic: db "NXSUITE 1",10,0

; ---------------------------------------------------------------- progress record
prg_read:                                           ; -> carry: no record
        ld hl,prgname : ld b,$01 : call f_open : ret c
        ld (.h),a
        ld ix,PRGB : ld bc,64 : call f_read
        push af : push bc
        ld a,(.h) : call f_close
        pop bc : pop af : ret c
        ld a,c : cp 64 : scf : ret nz
        ld a,(PRGB) : cp 'N' : scf : ret nz
        ld a,(PRGB+3) : cp '1' : scf : ret nz
        or a : ret
.h:     db 0
prg_write:                                          ; -> carry = error
        ld hl,prgname : ld b,$0E : call f_open : ret c
        ld (.h),a
        ld ix,PRGB : ld bc,64 : call f_write
        push af
        ld a,(.h) : call f_close
        pop af : ret
.h:     db 0

; ---------------------------------------------------------------- string page
; HL = address in the string page -> copied (zero ended, at most 127 bytes) to DE; slot 6 home after
far_copy:
        nextreg $56,STRPAGE
        ld b,127
.l:     ld a,(hl) : ld (de),a : or a : jr z,.e
        inc hl : inc de : djnz .l
        xor a : ld (de),a
.e:     nextreg $56,HOMEP6
        ret

; ---------------------------------------------------------------- restore (spec section 4)
; per entry: NextReg, compare mask, keep mask: if (now & cmp) != (launch & cmp), write
; (launch & cmp) | (now & keep). Registers a test may have written; never $02 $03 $06 $11 $82-$89 $8E $8F $D8.
rtab:   db $07,$03,$00, $05,$04,$FB, $08,$40,$3F, $0A,$10,$EF, $64,$FF,$00, $8C,$F0,$0F
        db $C0,$E9,$00, $C4,$FF,$00, $C5,$FF,$00, $C6,$FF,$00, $CC,$FF,$00, $CD,$FF,$00, $CE,$FF,$00
        db $22,$07,$00, $23,$FF,$00, $14,$FF,$00, $15,$FF,$00, $4A,$FF,$00, $4B,$FF,$00, $4C,$FF,$00
        db $43,$FF,$00, $12,$FF,$00, $13,$FF,$00, $70,$FF,$00, $16,$FF,$00, $17,$FF,$00, $71,$FF,$00
        db $68,$FF,$00, $69,$FF,$00, $6B,$FF,$00, $6C,$FF,$00, $6E,$FF,$00, $6F,$FF,$00, $09,$FF,$00
        db $2F,$FF,$00, $30,$FF,$00, $31,$FF,$00, $7F,$FF,$00
        db $52,$FF,$00, $53,$FF,$00, $54,$FF,$00, $55,$FF,$00
        db $FF
restore_all:
        di
        ld hl,rtab
.l:     ld a,(hl) : cp $FF : jr z,.x
        ld e,a : inc hl
        ld c,(hl) : inc hl                          ; cmp
        ld b,(hl) : inc hl                          ; keep
        push hl
        ld a,e : call rdreg : ld d,a                ; now
        ld hl,NRSNAP : ld a,l : add a,e : ld l,a    ; NRSNAP is page aligned
        ld a,(hl) : and c : ld l,a                  ; launch & cmp
        ld a,d : and c : cp l : jr z,.n
        ld a,d : and b : or l                       ; value to write
        push bc : ld bc,$243B : out (c),e : inc b : out (c),a : pop bc
.n:     pop hl
        jr .l
.x:     nextreg $C8,$FF                             ; interrupt status cleared (TQ:609)
        nextreg $C9,$FF
        nextreg $CA,$FF
        ld bc,$183B : ld a,$03 : out (c),a          ; CTC channels 0 and 3 reset (control $03)
        ld bc,$1B3B : out (c),a
        ld bc,$123B : xor a : out (c),a             ; Layer 2 port 0
        nextreg $56,HOMEP6                          ; our pages in slots 6 / 7 (7: the group's overlay)
        ld a,(ovlpage) : nextreg $57,a
        im 1
        ld a,(launch_i) : ld i,a
        ret

; ---------------------------------------------------------------- the text writer
; (wsink) = 0: bytes go to (wp); 1: to the screen (putc at crow / ccol)
w_lb:   ld hl,LB : ld (wp),hl : xor a : ld (wsink),a : ret
; -> HL = LB, BC = bytes written since w_lb
w_len:  ld hl,(wp) : ld de,LB : or a : sbc hl,de : ld b,h : ld c,l : ld hl,LB : ret
wchr:   push hl
        ld hl,wsink : bit 0,(hl) : jr nz,.s
        ld hl,(wp) : ld (hl),a : inc hl : ld (wp),hl
        pop hl : ret
.s:     pop hl : jp putc
wstr:   ld a,(hl) : or a : ret z
        call wchr : inc hl : jr wstr
whex4:  ld a,h : call whex2 : ld a,l
whex2:  push af : rrca : rrca : rrca : rrca : call .h : pop af
.h:     and 15 : add a,'0' : cp '9'+1 : jr c,.d
        add a,7
.d:     jp wchr
wdhex2: push af : ld a,'$' : call wchr : pop af : jr whex2     ; "$hh"
wdec:   ld de,0                                     ; HL unsigned
wdec32: push bc : ld b,0                            ; DEHL unsigned
.d:     push bc : ld c,10 : call div8 : pop bc
        push af : inc b
        ld a,h : or l : or d : or e : jr nz,.d
.o:     pop af : add a,'0' : call wchr : djnz .o
        pop bc : ret
; DEHL = signed value x 100 -> "-12.5", "3", "0.25" (at most 2 places, no trailing 0)
wfix:   bit 7,d : jr z,.p
        call neg32 : ld a,'-' : call wchr
.p:     push bc
        ld c,100 : call div8
        push af : call wdec32 : pop af
        pop bc
        or a : ret z
        push af : ld a,'.' : call wchr : pop af
        ld b,0
.t:     cp 10 : jr c,.u
        sub 10 : inc b : jr .t
.u:     push af : ld a,b : add a,'0' : call wchr : pop af
        or a : ret z
        add a,'0' : jp wchr
wp:     dw LB
wsink:  db 0

; ---------------------------------------------------------------- CRC of memory (the text CRC kept)
; HL = start, BC = length -> HL = CRC-16/CCITT
crc_mem:
        ld de,(crc) : push de
        ld de,$FFFF : ld (crc),de
.l:     ld a,(hl) : call crcb : inc hl
        dec bc : ld a,b : or c : jr nz,.l
        ld hl,(crc)
        pop de : ld (crc),de
        ret

; ---------------------------------------------------------------- S03 method (bank 2: it maps slot 6)
; page $60 (96) read-only in slot 6, page 0, ROM 0's first 8K -> A = 0 wrap (page 96 = ROM 0), 1 alias0
; (page 96 = page 0), 2 distinct; the CRCs in s03c96 / s03c0 / s03crom
s03_ram:
        nextreg $56,$60
        ld hl,$C000 : ld bc,$2000 : call crc_mem : ld (s03c96),hl
        nextreg $56,HOMEP6
        ld hl,$C000 : ld bc,$2000 : call crc_mem : ld (s03c0),hl
        ld bc,$1FFD : xor a : out (c),a             ; ROM 0 (1FFD $00 / 7FFD $00), slot 0 = $FF
        ld bc,$7FFD : out (c),a
        ld hl,$0000 : ld bc,$2000 : call crc_mem : ld (s03crom),hl
        ld bc,$1FFD : ld a,$04 : out (c),a          ; back to ROM 3
        ld bc,$7FFD : ld a,$10 : out (c),a
        ld hl,(s03c96) : ld de,(s03crom) : or a : sbc hl,de : ld a,0 : ret z
        ld hl,(s03c96) : ld de,(s03c0) : or a : sbc hl,de : ld a,1 : ret z
        ld a,2 : ret
s03c96: dw 0
s03c0:  dw 0
s03crom: dw 0

; ---------------------------------------------------------------- frame geometry (G4 F01 / F02 methods; the
; preamble uses them, so they live here and not in the G4 overlay)
; -> HL = the largest line seen over 3 frames (tight LSB / MSB / LSB reads, `line`); 0 = the counter
; never wrapped within the guard (~65536 reads)
frame_lines:
        ld a,3
flines_n:                                   ; A = frames
        inc a : ld (.w),a
        ld hl,0 : ld (.max),hl : ld (.prev),hl
        ld de,0                             ; guard
.l:     push de
        call line
        pop de
        push hl : ld bc,(.max) : or a : sbc hl,bc : pop hl : jr c,.nm
        ld (.max),hl
.nm:    push hl : ld bc,(.prev) : or a : sbc hl,bc : pop hl : ld (.prev),hl
        jr nc,.nw
        ld a,(.w) : dec a : ld (.w),a : jr z,.d
.nw:    dec de : ld a,d : or e : jr nz,.l
        ld hl,0 : ret
.d:     ld hl,(.max) : ret
.w:     db 0
.max:   dw 0
.prev:  dw 0

; CTC channel 3 as a free-running timer (control $07: timer, prescaler 16, time constant follows, reset;
; time constant 0 = 256; one tick = 16 clocks of 28 MHz): ticks over 256 raster lines, polled (run at
; 28 MHz: one poll is far below the 512 T of a wrap). -> DEHL = ticks per line x 100 (0 = no lines)
ctc_line:
        ld bc,$1B3B : ld a,$07 : out (c),a : xor a : out (c),a
        ld bc,$243B : ld a,$1F : out (c),a
        ld bc,$253B : in a,(c) : ld e,a
        ld hl,0                             ; guard
.s:     in a,(c) : cp e : jr nz,.go
        dec hl : ld a,h : or l : jr nz,.s
        jr .none
.go:    ld e,a                              ; E = this line's LSB
        ld b,$1B : in a,(c) : ld (.c0),a : ld d,a   ; D = last CTC value
        ld hl,0 : ld (.wr),hl
        ld ix,256                           ; lines to count
        ld hl,0                             ; guard per line
.p:     ld b,$1B : in a,(c)                 ; CTC (port $1B3B)
        cp d : ld d,a : jr c,.nwr : jr z,.nwr
        push hl : ld hl,(.wr) : inc hl : ld (.wr),hl : pop hl   ; the count went up: a wrap
.nwr:   ld b,$25 : in a,(c)                 ; line LSB
        cp e : jr z,.same
        ld e,a : ld hl,0
        dec ix : ld a,ixh : or ixl : jr nz,.p
        ; ticks = 256 x wraps + c0 - c1 (< 65536: 256 lines are ~28,700 ticks)
        ld b,$1B : in a,(c) : ld c,a
        ld a,(.c0) : sub c : ld e,a : ld d,0 : jr nc,.pos
        dec d
.pos:   ld hl,(.wr) : ld h,l : ld l,0 : add hl,de
        ld (ctc_ticks),hl
        ; x 100 / 256
        ld b,h : ld c,l : ld de,100 : call mul16
        ld l,h : ld h,e : ld e,d : ld d,0
        ret
.same:  dec hl : ld a,h : or l : jr nz,.p
.none:  ld hl,0 : ld de,0 : ret
.c0:    db 0
.wr:    dw 0
ctc_ticks: dw 0
