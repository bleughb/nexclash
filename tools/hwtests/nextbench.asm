; nextbench.asm - what Next techniques really cost, setup included (GPL-3.0-or-later, part of nexclash).
; Build: python tools/hwtests/build.py nextbench
;
; Every test is one routine (CALLed R times in a row); the time per call is measured on the raster
; line counter and printed in MICROSECONDS per call, at 3.5 MHz and at 28 MHz (the speed the converted
; games' hooks run at). "Setup" costs show as the small-size rows: e.g. DMA 1B ~ programming + start,
; (DMA 2K - DMA 1B) / 2047 = DMA cost per byte; compare with LDIR / LDI / stack rows of the same size.
;
; Method (as z80ntest, board-proven): wait for the start of a frame, wait 0 / 1 / 2 / 3 quarter lines
; (dither), run the routine R times, read the line; 4 passes added. The same with an empty routine is
; subtracted (call + loop overhead). Calibration at 3.5 MHz: 2048 x LD A,(IX+0) = 38,912 T = 11,117.7 us.
; us/call = (lines - empty lines) * 11117.7 / (calibration lines * R). R per test keeps a run inside
; a frame at 3.5 MHz; the 28 MHz run uses up to 8 R (max 255; DMA rows less, in case the DMA
; does not speed up with the CPU). Interrupts off, stack and code in
; uncontended RAM (bank 2); buffers in bank 0 ($C000 / $D000). ULA / tile rows write the screen /
; bank 5 on purpose (contended at 3.5 MHz). ~20 s with a blue border.
;
; After each memory test the result is checked: "!" after a time = the copy / fill was WRONG (e.g.
; DMA on cores before 3.02.02 at 3.5 / 7 MHz). Any key flips the two pages.
;
; Results table at RESULTS ($7E00): "NXBN", version, test count, the calibration line sum (word),
; then per test 8 bytes: tenths of us per call at 3.5 MHz (dword), at 28 MHz (dword); then per test
; one flag byte (bit 0 wrong at 3.5 MHz, bit 1 wrong at 28 MHz).

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

RESULTS     equ $7E00
STACK       equ $BFE0
FONT        equ $B800           ; RAM copy of the ROM font (a test switches ROMs through 0x7FFD)
SRC         equ $C000           ; 4K source pattern ((i*7+3) & 0x7F: never $E3, LDIRX copies all)
DST         equ $D000           ; 4K destination
PSTACK      equ $F000           ; SP inside the stack-copy / push-fill tests
DMA         equ $6B             ; zxnDMA port
NPAGE1      equ 16

        org $8000
start:  di
        ld sp,STACK
        nextreg $07,0
        ld hl,$3D00 : ld de,FONT : ld bc,768 : ldir
        ld hl,SRC : ld bc,4096 : ld e,0
.src:   ld a,e : add a,a : add a,a : add a,a : sub e : add a,3 : and $7F : ld (hl),a
        inc hl : inc e : dec bc : ld a,b : or c : jr nz,.src
        ld hl,RESULTS
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'B' : inc hl : ld (hl),'N' : inc hl
        ld (hl),1 : inc hl : ld (hl),NTESTS
        ld hl,RESULTS+8 : ld de,RESULTS+9 : ld bc,NTESTS*9 : ld (hl),0 : ldir
        call cls
        ld a,1 : out ($FE),a            ; blue: measuring
        ld ix,SRC
        ld a,8 : ld hl,t_ref : call measure : push hl
        ld a,8 : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de
        ld (kref),hl : ld (RESULTS+6),hl
        ld iy,tests : ld a,1 : ld (tno),a
.t:     ld a,(iy+0) : or (iy+1) : jr z,.done
        xor a : call one                ; 3.5 MHz
        ld a,1 : call one               ; 28 MHz
        nextreg $07,0
        ld de,TLEN : add iy,de
        ld a,(tno) : inc a : ld (tno),a
        jr .t
.done:  nextreg $07,0
        nextreg $2F,0 : nextreg $30,0 : nextreg $16,0 : nextreg $17,0 : nextreg $43,0
        ld a,4 : ld (bcol),a            ; green, or red if a check failed
        ld hl,RESULTS+8+NTESTS*8 : ld b,NTESTS
.bf:    ld a,(hl) : or a : jr z,.bn
        ld a,2 : ld (bcol),a
.bn:    inc hl : djnz .bf
.pages: ld a,0 : call page
        call key
        ld a,1 : call page
        call key
        jr .pages

; ---------------------------------------------------------------- one test at one speed
; A = 0 (3.5 MHz) / 1 (28 MHz); IY = the test's table entry
one:    ld (spd),a
        or a : jr z,.s
        nextreg $07,3
.s:     ld hl,DST : ld de,DST+1 : ld bc,4095 : ld (hl),0 : ldir
        ld a,(spd) : or a : ld a,(iy+2) : jr z,.r
        ld a,(iy+3)
.r:     ld (rr),a
        ld l,(iy+0) : ld h,(iy+1) : call measure : push hl
        ld a,(rr) : ld hl,t_none : call measure
        ex de,hl : pop hl : or a : sbc hl,de : jr nc,.p
        ld hl,0
.p:     ld de,55589 : ld b,h : ld c,l : call mul16    ; DEHL = d * 55589
        add hl,hl : rl e : rl d                        ; * 2 = d * 111178
        ld bc,(kref) : call div32                      ; / calibration lines
        ld a,(rr) : ld c,a : ld b,0 : call div32       ; / R -> tenths of us per call
        push de : push hl
        ld a,(tno) : dec a : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,RESULTS+8 : add hl,de
        ld a,(spd) : or a : jr z,.w
        ld de,4 : add hl,de
.w:     pop de : ld (hl),e : inc hl : ld (hl),d : inc hl
        pop de : ld (hl),e : inc hl : ld (hl),d
        call check                                     ; Z = OK
        ret z
        ld a,(tno) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*8 : add hl,de
        ld a,(spd) : inc a : or (hl) : ld (hl),a
        ret

; check (IY+4): 0 none, 1 DST = SRC for (IY+5) words... n bytes, 2 DST all $55 for n bytes -> Z if OK
check:  ld a,(iy+4) : or a : ret z
        ld c,(iy+5) : ld b,(iy+6)
        ld hl,DST : ld de,SRC
        cp 2 : jr z,.f
.c:     ld a,(de) : cp (hl) : ret nz
        inc hl : inc de : dec bc : ld a,b : or c : jr nz,.c
        ret
.f:     ld a,(hl) : cp $55 : ret nz
        inc hl : dec bc : ld a,b : or c : jr nz,.f
        ret

; ---------------------------------------------------------------- measuring
; HL = routine, A = R -> HL = raster lines of 4 passes (frame start + 0..3 quarter-line delays)
measure:
        ld (trout),hl : ld (tr),a
        ld hl,0 : ld (tsum),hl : xor a : ld (tpass),a
.pass:  call frame_sync
        ld a,(tpass) : add a,a : add a,a : inc a : ld b,a
        ld a,(spd) : or a : jr z,.dl
        ld a,b : add a,a : add a,a : add a,a : ld b,a  ; 28 MHz: 8x the delay loops
.dl:    djnz .dl
        ld a,(tr) : ld (tcnt),a
.l:     ld hl,(trout) : call jphl
        ld a,(tcnt) : dec a : ld (tcnt),a : jr nz,.l
        call line
        ld de,(tsum) : add hl,de : ld (tsum),hl
        ld a,(tpass) : inc a : ld (tpass),a : cp 4 : jr nz,.pass
        ld hl,(tsum)
        ret
jphl:   jp (hl)

; the 9-bit line into HL, read until two reads agree
line:   push bc
.again: call line1 : ld d,h : ld e,l
        call line1
        ld a,h : cp d : jr nz,.again
        ld a,l : cp e : jr nz,.again
        pop bc : ret
line1:  ld bc,$243B : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c) : ld l,a
        ret
; return just after line 0 starts (line >= 256, then past 257, then low byte 0)
frame_sync:
        ld bc,$243B : ld a,$1E : out (c),a : inc b
.a:     in a,(c) : and 1 : jr z,.a
        dec b : ld a,$1F : out (c),a : inc b
.b:     in a,(c) : cp 2 : jr c,.b
.c:     in a,(c) : or a : jr nz,.c
        ret

; ---------------------------------------------------------------- arithmetic (plain Z80)
; BC * DE -> DEHL
mul16:  ld hl,0 : ld a,16
.l:     add hl,hl : rl e : rl d : jr nc,.n
        add hl,bc : jr nc,.n
        inc de
.n:     dec a : jr nz,.l
        ret
; DEHL / BC -> DEHL (remainder in rem)
div32:  ld a,32
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
; DEHL / C -> DEHL, A = remainder (C <= 128)
div8:   xor a : ld b,32
.l:     add hl,hl : rl e : rl d : rla
        cp c : jr c,.n
        sub c : inc l
.n:     djnz .l
        ret

; ---------------------------------------------------------------- the tests
; entry: routine (word), R at 3.5 MHz, R at 28 MHz, check type, check length (word), name (8)
TLEN    equ 15
        MACRO T rout, r35, r28, chk, n, nm
        dw rout : db r35, r28, chk : dw n : db nm
        ENDM
tests:  T t_ldir256,  7, 56, 1, 256,  "LDIR 256"
        T t_ldi256,   9, 72, 1, 256,  "LDI x256"
        T t_stk256,  12, 96, 1, 256,  "STACK256"
        T t_dma1,   128,255, 1, 1,    "DMA 1B  "
        T t_dma256,  16, 32, 1, 256,  "DMA 256 "
        T t_dma2k,    2,  4, 1, 2048, "DMA 2K  "
        T t_ldir2k,   1,  8, 1, 2048, "LDIR 2K "
        T t_dmaprg, 128,255, 0, 0,    "DMA prog"
        T t_fldir,    7, 56, 2, 256,  "FILL LDR"
        T t_fpush,   28,224, 2, 256,  "FILL PSH"
        T t_fdma,    16, 32, 2, 256,  "FILL DMA"
        T t_ldirx,    7, 56, 1, 256,  "LDIRX256"
        T t_potir,    7, 56, 0, 0,    "PAT OTIR"
        T t_pouti,    9, 72, 0, 0,    "PAT OUTI"
        T t_poutb,    9, 72, 0, 0,    "PAT OTNB"
        T t_pdma,    16, 32, 0, 0,    "PAT DMA "
        T t_aout,   255,255, 0, 0,    "ATTR OUT"
        T t_anr,    255,255, 0, 0,    "ATTR NR "
        T t_nrv,    255,255, 0, 0,    "NEXTREGv"
        T t_nra,    255,255, 0, 0,    "NEXTREGa"
        T t_nrport, 255,255, 0, 0,    "REG PORT"
        T t_mmu,    255,255, 0, 0,    "MMU NR  "
        T t_7ffd,   255,255, 0, 0,    "7FFD OUT"
        T t_ulach,  128,255, 0, 0,    "ULA CHAR"
        T t_tile,   255,255, 0, 0,    "TILE ENT"
        T t_l2ch,    32,255, 0, 0,    "L2 8x8  "
        T t_tmscr,  255,255, 0, 0,    "TM SCROL"
        T t_l2scr,  255,255, 0, 0,    "L2 SCROL"
        T t_ularow,   5, 40, 0, 0,    "ULA 256B"
        T t_pal,    255,255, 0, 0,    "PAL 1   "
        T t_copnr,   14,112, 0, 0,    "COP32 NR"
        T t_copout,  14,112, 0, 0,    "COP32 IO"
        dw 0
NTESTS  equ ($-tests-2)/TLEN

t_none: ret
t_ref:
        DUP 256
        ld a,(ix+0)
        EDUP
        ret

; memory -> memory, 256 bytes
t_ldir256:
        ld hl,SRC : ld de,DST : ld bc,256 : ldir : ret
t_ldi256:
        ld hl,SRC : ld de,DST : ld a,16
.l:
        DUP 16
        ldi
        EDUP
        dec a : jr nz,.l
        ret
t_stk256:
        ld (spsave),sp
I       = 0
        DUP 32
        ld sp,SRC+I*8 : pop af : pop bc : pop de : pop hl
        ld sp,DST+I*8+8 : push hl : push de : push bc : push af
I       = I+1
        EDUP
        ld sp,(spsave)
        ret
t_ldir2k:
        ld hl,SRC : ld de,DST : ld bc,2048 : ldir : ret
t_ldirx:
        ld hl,SRC : ld de,DST : ld bc,256 : ld a,$E3 : ldirx : ret
t_dma1: ld hl,d_c1 : ld bc,(d_c_len << 8) | DMA : otir : ret
t_dma256:
        ld hl,d_c256 : ld bc,(d_c_len << 8) | DMA : otir : ret
t_dma2k:
        ld hl,d_c2k : ld bc,(d_c_len << 8) | DMA : otir : ret
t_dmaprg:
        ld hl,d_c256 : ld bc,((d_c_len - 1) << 8) | DMA : otir : ret     ; all but ENABLE
; fills, 256 bytes of $55
t_fldir:
        ld hl,DST : ld (hl),$55 : ld de,DST+1 : ld bc,255 : ldir : ret
t_fpush:
        ld (spsave),sp : ld sp,DST+256 : ld hl,$5555
        DUP 128
        push hl
        EDUP
        ld sp,(spsave) : ret
t_fdma: ld hl,d_f256 : ld bc,(d_c_len << 8) | DMA : otir : ret
; sprite pattern upload, 256 bytes (one 8-bit 16x16 pattern) to port 0x5B, pattern slot 0
t_potir:
        ld bc,$303B : xor a : out (c),a
        ld hl,SRC : ld bc,$005B : otir : ret
t_pouti:
        ld bc,$303B : xor a : out (c),a
        ld hl,SRC : ld c,$5B : ld a,16
.l:
        DUP 16
        outi
        EDUP
        dec a : jr nz,.l
        ret
t_poutb:
        ld bc,$303B : xor a : out (c),a
        ld hl,SRC : ld bc,$005B : ld a,16
.l:
        DUP 16
        outinb
        EDUP
        dec a : jr nz,.l
        ret
t_pdma: ld bc,$303B : xor a : out (c),a
        ld hl,d_p256 : ld bc,(d_c_len << 8) | DMA : otir : ret
; one sprite's 4 attributes (sprite 0, invisible): by port 0x57, by NEXTREG $34-$38
t_aout: ld bc,$303B : xor a : out (c),a
        ld hl,attrs : ld c,$57 : outi : outi : outi : outi : ret
t_anr:  nextreg $34,0 : nextreg $35,32 : nextreg $36,32 : nextreg $37,0 : nextreg $38,0 : ret
; one register write: NEXTREG n,v / NEXTREG n,A / OUT $243B + OUT $253B (NextReg $7F, user register)
t_nrv:  nextreg $7F,$55 : ret
t_nra:  ld a,$55 : nextreg $7F,a : ret
t_nrport:
        ld bc,$243B : ld a,$7F : out (c),a : inc b : ld a,$55 : out (c),a : ret
; paging: MMU slot 6 by NEXTREG (page 0 = as now) / 128K port 0x7FFD (bank 0, 48K ROM)
t_mmu:  nextreg $56,0 : ret
t_7ffd: ld bc,$7FFD : ld a,$10 : out (c),a : ret
; an 8x8 cell: ULA (8 pixel bytes + attribute, contended) / tilemap entry (2 bytes in bank 5) /
; Layer 2 style (64 bytes, rows 256 apart)
t_ulach:
        ld hl,$4000 : ld de,SRC
        DUP 8
        ld a,(de) : ld (hl),a : inc e : inc h
        EDUP
        ld a,$38 : ld ($5800),a : ret
t_tile: ld hl,$1234 : ld ($6000),hl : ret
t_l2ch: ld hl,SRC : ld de,DST : ld a,8
.r:
        DUP 8
        ldi
        EDUP
        ld e,0 : inc d
        dec a : jr nz,.r
        ret
; scrolling: hardware offsets (tilemap X, Layer 2 X / Y) vs one ULA pixel row band copied (256 bytes)
t_tmscr:
        nextreg $2F,0 : nextreg $30,1 : ret
t_l2scr:
        nextreg $16,1 : nextreg $17,0 : ret
t_ularow:
        ld hl,$4100 : ld de,$4000 : ld bc,256 : ldir : ret
; one palette entry (sprite palette 1, entry 0)
t_pal:  nextreg $43,$20 : nextreg $40,0 : nextreg $41,$E3 : ret
; a 32-instruction copper list (64 bytes of NOPs), copper stopped: by NEXTREG $60 / by OUT $253B
t_copnr:
        nextreg $61,0 : nextreg $62,0
        ld hl,cop : ld b,64
.l:     ld a,(hl) : nextreg $60,a : inc hl : djnz .l
        ret
t_copout:
        nextreg $61,0 : nextreg $62,0
        ld bc,$243B : ld a,$60 : out (c),a : inc b
        ld hl,cop : ld e,64
.l:     ld a,(hl) : out (c),a : inc hl : dec e : jr nz,.l
        ret

; zxnDMA programs (port $6B), continuous mode, A -> B, 2 T timing both ports
        MACRO DMAPROG src, len, r1, r2, dst
        db $83                  ; WR6 disable
        db %01111101            ; WR0 A -> B, port A address + length follow
        dw src, len
        db r1, %00000010        ; WR1 port A (+ timing byte: 2 T)
        db r2, %00000010        ; WR2 port B (+ timing byte: 2 T)
        db %10101101            ; WR4 continuous, port B address follows
        dw dst
        db %10000010            ; WR5
        db $CF                  ; WR6 load
        db $87                  ; WR6 enable
        ENDM
d_c1:   DMAPROG SRC, 1, %01010100, %01010000, DST          ; memory++ -> memory++
d_c_len equ $-d_c1
d_c256: DMAPROG SRC, 256, %01010100, %01010000, DST
d_c2k:  DMAPROG SRC, 2048, %01010100, %01010000, DST
d_f256: DMAPROG fillb, 256, %01100100, %01010000, DST      ; fixed memory -> memory++
d_p256: DMAPROG SRC, 256, %01010100, %01101000, $005B      ; memory++ -> fixed I/O port 0x5B
fillb:  db $55
attrs:  db 32, 32, 0, 0
cop:    ds 64, 0

; ---------------------------------------------------------------- screen
; A = page (0 / 1)
page:   ld (pg),a
        call cls
        ld a,(bcol) : out ($FE),a
        xor a : ld (crow),a : ld (ccol),a
        ld hl,title : call puts
        ld a,$01 : call rdreg : push af
        rrca : rrca : rrca : rrca : and 15 : add a,'0' : call putc
        ld a,'.' : call putc
        pop af : and 15 : call dec2
        ld a,'.' : call putc
        ld a,$0E : call rdreg : call dec2
        ld a,(pg) : add a,'1' : ld (ptxt+3),a
        ld hl,ptxt : call puts
        ld a,1 : ld (crow),a : xor a : ld (ccol),a
        ld hl,hdr : call puts
        ld a,(pg) : or a : ld a,1 : ld b,NPAGE1 : jr z,.f
        ld a,NPAGE1+1 : ld b,NTESTS-NPAGE1
.f:     ld (pt),a : ld a,b : ld (pn),a
        ld a,3 : ld (crow),a
.e:     xor a : ld (ccol),a
        ld a,(pt) : dec a : ld l,a : ld h,0
        ld d,h : ld e,l : add hl,hl : add hl,hl : add hl,hl : add hl,hl : or a : sbc hl,de   ; *15
        ld de,tests+7 : add hl,de
        ld b,8
.n:     ld a,(hl) : call putc : inc hl : djnz .n
        ld a,(pt) : dec a : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,RESULTS+8 : add hl,de
        push hl : ld a,1 : call pval : pop hl
        ld de,4 : add hl,de : ld a,2 : call pval
        ld a,(crow) : inc a : ld (crow),a
        ld a,(pt) : inc a : ld (pt),a
        ld a,(pn) : dec a : ld (pn),a : jr nz,.e
        ret
; HL = the dword (tenths of us), A = flag bit: "  dddd.d" + "!" if that check failed
pval:   ld (fbit),a
        ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        ex de,hl                        ; DEHL = value
        ld ix,dbuf+7 : ld b,7
.cl:    dec ix : ld (ix+0),' ' : djnz .cl
        ld ix,dbuf+7
        ld c,10 : call div8 : add a,'0' : dec ix : ld (ix+0),a
        dec ix : ld (ix+0),'.'
.d:     push bc
        ld c,10 : call div8 : add a,'0' : dec ix : ld (ix+0),a
        pop bc
        ld a,d : or e : or h : or l : jr z,.p
        push ix : pop bc : ld a,c : cp low dbuf : jr nz,.d
.p:     ld a,' ' : call putc
        ld hl,dbuf : ld b,7
.o:     ld a,(hl) : call putc : inc hl : djnz .o
        ld a,(pt) : dec a : ld e,a : ld d,0 : ld hl,RESULTS+8+NTESTS*8 : add hl,de
        ld a,(fbit) : and (hl) : ld a,' ' : jr z,.q
        ld a,'!'
.q:     jp putc

cls:    ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),$38 : ldir
        ret
putc:   push hl : push de : push bc
        sub 32 : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,FONT : add hl,de
        ld a,(crow) : and $18 : or $40 : ld d,a
        ld a,(crow) : and 7 : rrca : rrca : rrca : ld e,a
        ld a,(ccol) : or e : ld e,a
        ld b,8
.l:     ld a,(hl) : ld (de),a : inc hl : inc d : djnz .l
        ld a,(ccol) : inc a : ld (ccol),a
        pop bc : pop de : pop hl
        ret
puts:   ld a,(hl) : or a : ret z
        call putc : inc hl : jr puts
dec2:   push bc
        ld b,0
.l:     cp 10 : jr c,.d
        sub 10 : inc b : jr .l
.d:     ld c,a : ld a,b : add a,'0' : call putc : ld a,c : add a,'0' : call putc
        pop bc : ret
rdreg:  push bc : ld bc,$243B : out (c),a : inc b : in a,(c) : pop bc : ret
key:
.r:     xor a : in a,($FE) : cpl : and $1F : jr nz,.r
.p:     xor a : in a,($FE) : cpl : and $1F : jr z,.p
        ret

title:  db "NEXTBENCH v1 core ",0
ptxt:   db "  P?/2",0
hdr:    db "us/call   3.5MHz    28MHz",0
kref:   dw 0
spsave: dw 0
trout:  dw 0
tsum:   dw 0
rem:    dw 0
tr:     db 0
tcnt:   db 0
tpass:  db 0
spd:    db 0
rr:     db 0
tno:    db 0
bcol:   db 0
pg:     db 0
pt:     db 0
pn:     db 0
crow:   db 0
ccol:   db 0
fbit:   db 0
dbuf:   ds 7

        ASSERT $ <= FONT

        SAVENEX OPEN "nextbench.nex", start, STACK
        SAVENEX CORE 3,0,0
        SAVENEX CFG 0,0,0,0
        SAVENEX AUTO
        SAVENEX CLOSE
