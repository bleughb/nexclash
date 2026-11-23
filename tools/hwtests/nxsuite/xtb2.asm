; nxsuite/xtb2.asm - the opt-in groups' code that must stay in bank 2 (slots 6 / 7 move under it), and
; what the start does after an opt-in test left something behind. GPL-3.0-or-later.

; ---------------------------------------------------------------- start: the progress record
; prg_read, then: PRG_FLAGS bit 1 (an X-T test stopped with NextReg $03 changed; $03 survives a soft
; reset): the start timing back from PRG_T03 (into the snapshot too), 3 frames, the preamble measured
; again (it ran at the wrong timing), bit cleared. PRG_FLAGS bit 0 (XH2 locked the DMA, then a reset):
; one 1-byte DMA copy decides PRG_XH2 = 1 (the reset freed the DMA) / 2 (still deaf), bit cleared.
; -> carry: no record (as prg_read)
prg_read2:
        call prg_read : ret c
        ld hl,PRGB+PRG_FLAGS : bit 1,(hl) : jr z,.d
        res 1,(hl)
        ld a,(PRGB+PRG_T03) : ld (NRSNAP+$03),a
        and $70 : or $83 : nextreg $03,a
        ld b,3
.f:     push bc : call frame_sync : pop bc : djnz .f
        call preamble
.d:     ld hl,PRGB+PRG_FLAGS : bit 0,(hl) : jr z,.ok
        res 0,(hl)
        call dma_sane : ld a,1 : jr nc,.fr
        inc a
.fr:    ld (PRGB+PRG_XH2),a
.ok:    or a : ret

; ---------------------------------------------------------------- one DMA byte
; $C3, then a 1-byte memory copy WORK -> WORK+1 (WR0 $7D, WR1 $14, WR2 $10, WR4 $AD continuous, WR5 $82,
; $CF, $87; book ch 5), $83 after. -> NC = the byte arrived, carry = it did not
dma_sane:
        ld a,$5A : ld (WORK),a : xor a : ld (WORK+1),a
        ld hl,.p : ld bc,((.pe-.p) << 8) | $6B : otir
        ld b,0
.w:     djnz .w
        ld a,$83 : out ($6B),a
        ld a,(WORK+1) : cp $5A : ret z
        scf : ret
.p:     db $C3, $7D, low WORK, high WORK, 1, 0, $14, $10, $AD, low (WORK+1), high (WORK+1), $82, $CF, $87
.pe:

; ---------------------------------------------------------------- XT4: $7FFD and $3FFD
; OUT $7FFD,$13 -> MMU 6 / 7 into xtpg; $7FFD = $10 and slots 6 / 7 as they were; then the same with
; $3FFD into xtpg+2 (not written - $FF $FF - when NextReg $D8 bit 0 was set at launch: the +3 disk ports
; trapped). DI throughout; the caller's slot 7 is put back before the return.
xt_pg:  ld a,$56 : call rdreg : ld (.s6),a : ld a,$57 : call rdreg : ld (.s7),a
        ld bc,$7FFD : ld a,$13 : out (c),a
        ld hl,xtpg : call .rd
        ld a,$FF : ld (xtpg+2),a : ld (xtpg+3),a
        ld a,(NRSNAP+$D8) : rra : ret c
        ld bc,$3FFD : ld a,$13 : out (c),a
        ld hl,xtpg+2
.rd:    ld a,$56 : call rdreg : ld (hl),a : inc hl
        ld a,$57 : call rdreg : ld (hl),a
        ld bc,$7FFD : ld a,$10 : out (c),a
        ld a,(.s6) : nextreg $56,a : ld a,(.s7) : nextreg $57,a
        ret
.s6:    db 0
.s7:    db 0
xtpg:   ds 4

; ---------------------------------------------------------------- XT5: ROM by $1FFD bit 2 x $7FFD bit 4
; for i = 0-3: OUT $1FFD = (i & 2) << 1, OUT $7FFD = (i & 1) << 4; CRC of $0000-$3FFF (slots 0 / 1 = ROM,
; reads only) -> xtrc + 2i. Then $1FFD = $04, $7FFD = $10, slots 0 / 1 / 6 / 7 as they were.
xt_rom: ld a,$56 : call rdreg : ld (xt_pg.s6),a : ld a,$57 : call rdreg : ld (xt_pg.s7),a
        nextreg $50,$FF : nextreg $51,$FF
        ld ix,xtrc : ld d,0
.l:     ld a,d : and 2 : add a,a : ld bc,$1FFD : out (c),a
        ld a,d : and 1 : rrca : rrca : rrca : rrca : ld bc,$7FFD : out (c),a
        push de : push ix
        ld hl,0 : ld bc,$4000 : call crc_mem
        pop ix : pop de
        ld (ix+0),l : ld (ix+1),h : inc ix : inc ix
        inc d : ld a,d : cp 4 : jr c,.l
        ld bc,$1FFD : ld a,$04 : out (c),a
        ld bc,$7FFD : ld a,$10 : out (c),a
        ld a,(NRSNAP+$50) : nextreg $50,a : ld a,(NRSNAP+$51) : nextreg $51,a
        ld a,(xt_pg.s6) : nextreg $56,a : ld a,(xt_pg.s7) : nextreg $57,a
        ret
xtrc:   ds 8

; ---------------------------------------------------------------- a session header stays in one part
; before a session's H lines: when the text is within 1 KB of ROTAT the part is written now, so the whole
; header goes into the continuation (board run 7: the first H line ended the earlier part)
txt_rot_hdr:
        ld hl,(txtlen) : ld de,1024 : add hl,de : ld a,h : cp ROTAT>>8 : ret c
        ld hl,WORK+256 : ld bc,1 : jp txt_rot.f

; ---------------------------------------------------------------- writing the result file through bank 5
; f_write, or with (bounce) <> 0 the same bytes copied 512 at a time to BOUNCE (bank 5, G2's window, free
; outside G2) and written from there. -> BC written, carry = error (as f_write)
BOUNCE  equ $6000
bounce: db 0
s_bounce: db "# a write of NXSUITE.TXT from slot 6 failed; written through bank 5 from here on",10,0
f_write_b:
        push af : ld a,(bounce) : or a : jr nz,.b
        pop af : jp f_write
.b:     pop af : ld (.h),a : ld (.left),bc : ld (.src),ix
        ld hl,0 : ld (.done),hl
.l:     ld bc,(.left) : ld a,b : or c : jr z,.e
        ld a,b : cp 2 : jr c,.c
        ld bc,512
.c:     ld (.n),bc
        ld hl,(.src) : ld de,BOUNCE : ldir
        ld ix,BOUNCE : ld bc,(.n) : ld a,(.h) : call f_write : ret c
        ld hl,(.done) : add hl,bc : ld (.done),hl
        ld hl,(.n) : or a : sbc hl,bc : scf : ret nz
        ld hl,(.src) : add hl,bc : ld (.src),hl
        ld hl,(.left) : or a : sbc hl,bc : ld (.left),hl
        jr .l
.e:     ld bc,(.done) : or a : ret
.h:     db 0
.left:  dw 0
.src:   dw 0
.done:  dw 0
.n:     dw 0

; ---------------------------------------------------------------- V group: 320 x 256 Layer 2 and copper helpers
; A = index -> 320 x 256 Layer 2 (pages 44-53) filled with it (slot 3, harness page $0B back after)
l2w_fill:
        ld c,a : ld b,44
.p:     ld a,b : nextreg $53,a
        ld hl,$6000 : ld (hl),c : ld de,$6001 : push bc : ld bc,$1FFF : ldir : pop bc
        inc b : ld a,b : cp 54 : jr nz,.p
        nextreg $53,$0B : ret
; B = row, C = index -> that row of the 320 x 256 Layer 2 (column-major: byte x * 256 + y) set to it
l2w_row:
        ld d,44
.p:     ld a,d : nextreg $53,a
        ld h,$60 : ld l,b : ld e,32
.c:     ld (hl),c : inc h : dec e : jr nz,.c
        inc d : ld a,d : cp 54 : jr nz,.p
        nextreg $53,$0B : ret
; 320 x 256 Layer 2 on top (order LSU), pages 44-53, clip 0-159 / 0-255 (wide mode: X in 2-dot units)
l2w_on: nextreg $70,%00010000 : nextreg $12,22
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,159 : nextreg $18,0 : nextreg $18,255
        ld a,(NRSNAP+$15) : and %11100011 : or %00000100 : nextreg $15,a
        ld bc,$123B : ld a,2 : out (c),a : ret
; the Layer 2 clip window back to its reset value 0-255 / 0-191 (the harness does not restore it)
l2w_off:
        nextreg $1C,1 : nextreg $18,0 : nextreg $18,255 : nextreg $18,0 : nextreg $18,191
        ld bc,$123B : xor a : out (c),a : ret
; HL = copper program, B = its length -> loaded at index 0, run in mode %11 (from the start every frame)
cop_load:
        nextreg $62,0 : nextreg $61,0
.l:     ld a,(hl) : nextreg $60,a : inc hl : djnz .l
        nextreg $61,0 : nextreg $62,%11000000 : ret
