; nxsuite/g4.asm - G4 FRAME: geometry and raster (spec section 3 G4). GPL-3.0-or-later.
; Nothing here assumes a line count: frames are found by the line number falling (wrap), with a guard.

; (frame_lines / flines_n / ctc_line live in core.asm: the preamble uses them too)

; -> HL = the largest line read until the line number falls (the next wrap); 0 = no wrap within the guard
fwrapmax:
        call line : ld (.prev),hl : ld (.max),hl
        ld de,0
.l:     push de : call line : pop de
        push hl : ld bc,(.prev) : or a : sbc hl,bc : pop hl : jr c,.w
        ld (.prev),hl
        push hl : ld bc,(.max) : or a : sbc hl,bc : pop hl : jr c,.n
        ld (.max),hl
.n:     dec de : ld a,d : or e : jr nz,.l
        ld hl,0 : ret
.w:     ld hl,(.max) : ret
.prev:  dw 0
.max:   dw 0

; HL = key, DE = a largest line -> " key=<DE + 1>" (a frame length; 0 stays 0 = no wrap seen)
ex_klen:
        push de : call ex_k : pop hl
        ld a,h : or l : jr z,.z
        inc hl
.z:     jp wdec

; the expected frame length for the timing in use: HDMI 312; VGA by $03 bits 6:4 (1 48K 312, 2 128K 311,
; 3 +3 311, 4 Pentagon 320) -> HL (0 = no reference for this timing)
f_expect:
        ld a,(NRSNAP+$11) : and 7 : cp 7 : ld hl,312 : ret z
        ld a,$03 : call rdreg : rrca : rrca : rrca : rrca : and 7
        ld hl,312 : cp 1 : ret z
        ld hl,311 : cp 2 : ret z : cp 3 : ret z
        ld hl,320 : cp 4 : ret z
        ld hl,0 : ret

; ---------------------------------------------------------------- F01 lines per frame
t_f01:  ld a,10 : call flines_n
        ld a,h : or l : jr z,.none
        inc hl
.none:  ld (.n),hl
        call res_int
        ld hl,u_lines : call res_unit
        call f_expect : ld (.e),hl
        ex de,hl : ld hl,k_exp : call ex_kd
        ld a,$03 : call rdreg : ld hl,k_nr03 : call ex_kh
        ld hl,(.e) : ld a,h : or l : ret z
        ld de,(.n) : or a : sbc hl,de : ret nz
        ld a,ST_PASS : ld (R_st),a
        ret
.n:     dw 0
.e:     dw 0
k_exp:  db "exp",0
k_nr03: db "nr03",0

; ---------------------------------------------------------------- F02 line length
; CTC3 at prescaler 16 (one tick = 2 T of 3.5 MHz) over 256 line changes, at 28 MHz
t_f02:  nextreg $07,3
        call ctc_line
        ld a,(spd0) : nextreg $07,a
        add hl,hl : rl e : rl d                     ; ticks x 2 = T (3.5 MHz) per line, x 100
        call res_num
        ld hl,u_t : call res_unit
        ld de,(ctc_ticks) : ld hl,k_t256 : jp ex_kd
k_t256: db "ticks256",0

; ---------------------------------------------------------------- F03 the other refresh rate
; $05 bit 2 flipped (read-modify-write) at line 100: the frame in which it happened and the next one, then
; lines per frame and the line length at the new rate; bit 2 put back the same way and two frames waited.
; The monitor may lose the picture for a moment (both switches).
t_f03:  ld a,$05 : call rdreg : ld (.r5),a
        call frame_sync : ld a,100 : call sync_lsb
        ld a,(.r5) : xor 4 : nextreg $05,a
        call fwrapmax : ld (.f1),hl
        call fwrapmax : ld (.f2),hl
        ld a,$05 : call rdreg : ld (.n5),a
        ld a,10 : call flines_n
        ld a,h : or l : jr z,.z
        inc hl
.z:     call res_int
        ld hl,u_lines : call res_unit
        nextreg $07,3
        call ctc_line
        ld a,(spd0) : nextreg $07,a
        add hl,hl : rl e : rl d : ld (.lt),hl : ld (.lt+2),de
        ; back to the start rate
        ld a,$05 : call rdreg : and $FB : ld b,a : ld a,(.r5) : and 4 : or b : nextreg $05,a
        call fwrapmax : call fwrapmax
        ld a,(.r5) : and 4 : ld hl,w_to60 : jr z,.t
        ld hl,w_to50
.t:     push hl : ld hl,k_to : call ex_k : pop hl : call wstr
        ld a,(.n5) : ld hl,k_nr05 : call ex_kh
        ld de,(.f1) : ld hl,k_f1 : call ex_klen
        ld de,(.f2) : ld hl,k_f2 : call ex_klen
        ld hl,k_linet : call ex_k : ld hl,(.lt) : ld de,(.lt+2) : jp wfix
.r5:    db 0
.n5:    db 0
.f1:    dw 0
.f2:    dw 0
.lt:    ds 4
w_to60: db "60",0
w_to50: db "50",0
k_to:   db "to",0
k_nr05: db "nr05",0
k_f1:   db "f1",0
k_f2:   db "f2",0
k_linet: db "line_t",0

; ---------------------------------------------------------------- F04 raster read
; 100,000 LSB / MSB / LSB reads at 3.5 and at 28 MHz: a read is bad if it is above the largest line of
; the frame (preamble) or lower than the one before other than at the wrap (from within 4 of the last
; line to within 4 of 0). PASS if none.
t_f04:  xor a : call .run : ld (.b35),hl
        ld a,3 : call .run : ld (.b28),hl
        ld a,(spd0) : nextreg $07,a
        ld de,(.b35) : add hl,de : push hl
        call res_int
        ld hl,u_count : call res_unit
        ld de,(.b35) : ld hl,k_b35 : call ex_kd
        ld de,(.b28) : ld hl,k_b28 : call ex_kd
        ld de,(flines) : ld hl,k_lim : call ex_kd
        pop hl : ld a,h : or l
        ld a,ST_PASS : jr z,.s
        ld a,ST_FAIL
.s:     ld (R_st),a : ret
.run:   nextreg $07,a
        ld hl,0 : ld (.bad),hl
        call line : ld (.prev),hl
        ld a,2 : ld (.o),a
.o1:    ld de,50000
.l:     push de
        call line
        ex de,hl : ld hl,(flines) : or a : sbc hl,de : jr c,.bd   ; above the largest line
        ld hl,(.prev) : or a : sbc hl,de : jr z,.ok : jr c,.ok    ; same or later
        ; fell: a wrap if prev >= flines - 4 and the new value <= 4
        ld hl,4 : or a : sbc hl,de : jr c,.bd
        ld hl,(flines) : ld bc,-4 : add hl,bc : ld bc,(.prev) : or a : sbc hl,bc : jr z,.ok : jr c,.ok
.bd:    ld hl,(.bad) : inc hl : ld (.bad),hl
.ok:    ld (.prev),de
        pop de : dec de : ld a,d : or e : jr nz,.l
        ld a,(.o) : dec a : ld (.o),a : jr nz,.o1
        ld hl,(.bad) : ret
.bad:   dw 0
.prev:  dw 0
.o:     db 0
.b35:   dw 0
.b28:   dw 0
k_b35:  db "bad35",0
k_b28:  db "bad28",0
k_lim:  db "maxline",0

; ---------------------------------------------------------------- F05 $64 line offset
; at line 100 write $64 = 32 and read the line straight after; the largest line of that frame and of the
; next; then $64 back to its start value and two frames waited. Then with $64 = 0 and = 32 (f05x): the line
; read in a line-interrupt-32 handler (li0 / li32) and the line where a copper WAIT 32 + MOVE was first seen
; (cp0 / cp32); $64 restored and two frames waited again.
t_f05:  ld a,$64 : call rdreg : ld (.r),a
        call frame_sync : ld a,100 : call sync_lsb
        nextreg $64,32
        call line : ld (.a),hl
        call fwrapmax : ld (.f1),hl
        call fwrapmax : ld (.f2),hl
        ld a,(.r) : nextreg $64,a
        call fwrapmax : call fwrapmax
        ld hl,(.a) : call res_int
        ld hl,u_lines : call res_unit
        ld de,100 : ld hl,k_before : call ex_kd
        ld de,(.f1) : ld hl,k_f1 : call ex_klen
        ld de,(.f2) : ld hl,k_f2 : call ex_klen
        xor a : call f05x : ld (.x),hl : ld (.x+2),de
        ld a,32 : call f05x : ld (.x+4),hl : ld (.x+6),de
        ld a,(.r) : nextreg $64,a
        call fwrapmax : call fwrapmax
        ld de,(.x) : ld hl,k_li0 : call ex_kd
        ld de,(.x+4) : ld hl,k_li32 : call ex_kd
        ld de,(.x+2) : ld hl,k_cp0 : call ex_kd
        ld de,(.x+6) : ld hl,k_cp32 : call ex_kd
        ld hl,k_parts : call ex_k : ld hl,w_parts : jp wstr
.x:     ds 8
.r:     db 0
.a:     dw 0
.f1:    dw 0
.f2:    dw 0
k_before: db "before",0
k_parts: db "parts",0
w_parts: db "raster,line-int,copper",0
k_li0:  db "li0",0
k_li32: db "li32",0
k_cp0:  db "cp0",0
k_cp32: db "cp32",0

; A = $64 value -> HL = the raster line read in a line-interrupt-32 handler (pulse IM 2, ULA off; $FFFF
; = never ran), DE = the line where a copper WAIT 32 + MOVE $7F,$5A was first seen by the CPU (28 MHz,
; mode 11, $7F cleared at line 200; $FFFF = never). Uses $FD00-$FF00 of this page as its IM 2 table.
F5T     equ $FD00
f05x:   di
        nextreg $64,a
        call fwrapmax
        nextreg $07,3
        ld hl,F5T : ld de,F5T+1 : ld bc,256 : ld (hl),$FE : ldir
        ld a,$C3 : ld ($FEFE),a : ld hl,f05h : ld ($FEFF),hl
        ld a,(NRSNAP+$C0) : and $08 : nextreg $C0,a
        nextreg $C5,0 : nextreg $C6,0
        nextreg $23,32
        ld a,(NRSNAP+$22) : and $F8 : or 6 : nextreg $22,a
        nextreg $C4,2
        nextreg $C8,$FF : nextreg $C9,$FF : nextreg $CA,$FF
        ld hl,$FFFF : ld (f05l),hl
        ld a,F5T>>8 : ld i,a : im 2
        ld de,0 : ld b,8
        ei
.w:     ld hl,(f05l) : inc hl : ld a,h : or l : jr nz,.g
        dec de : ld a,d : or e : jr nz,.w
        djnz .w
.g:     di
        ld a,(NRSNAP+$22) : nextreg $22,a : ld a,(NRSNAP+$23) : nextreg $23,a
        nextreg $C4,1 : nextreg $C8,$FF
        im 1 : ld a,(launch_i) : ld i,a
        ld hl,(f05l) : push hl
        ; copper: WAIT 32,0 ; MOVE $7F,$5A ; HALT
        nextreg $62,0 : nextreg $61,0
        ld hl,.cl : ld b,6
.c:     ld a,(hl) : nextreg $60,a : inc hl : djnz .c
        nextreg $61,0
        call frame_sync : ld a,200 : call sync_lsb
        nextreg $7F,0
        nextreg $62,$C0
        ld de,$FFFF : ld bc,0
.p:     ld a,$7F : call rdreg : cp $5A : jr z,.s
        dec bc : ld a,b : or c : jr nz,.p
        jr .e
.s:     call line : ex de,hl
.e:     nextreg $62,0
        ld a,(NRSNAP+$7F) : nextreg $7F,a
        pop hl
        ret
.cl:    db $80,$20, $7F,$5A, $FF,$FF
f05h:   push af : push hl
        call line : ld (f05l),hl
        pop hl : pop af : ei : reti
f05l:   dw 0
