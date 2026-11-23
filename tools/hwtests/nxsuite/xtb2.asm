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
