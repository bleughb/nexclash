; The New Zealand Story (Ocean, 1989), 128K: the world loader's tape read, served from RAM.
; Runs in an extra Next 8K page mapped at MMU0 (0x0000-0x1FFF) by a 12-byte stub that replaces
; the game's own LD-BYTES entry (SCF / INC D / EX AF,AF' / DEC D / DI / LD A,0F / OUT (FE),A /
; JP 0562) at 0x43AF, the copy the game makes of bank 1 0xD1EA. The blocks themselves are the
; tape's own bytes, placed in extra pages by the TAP1 recipe: nothing of the game is in here.
;
; In: A = flag (0xAA header, 0x81+k data), IX = destination, DE = length, SP = S (return address
; at S), interrupts already off (the world loader's DI at 0x4116).
; Out, as the ROM's LD-BYTES leaves a good load: the bytes at IX, IX += length, DE = 0, H = 0,
; L = the block's checksum byte, A = 0 and F from its final CP 1, AF' as left by LD-FLAG, B and C
; as left by the last edge, the border as the last edge set it, the ROM's two return addresses
; at S-2 (0x05CD) and S-4 (0x05E6). It returns through the stub (NEXTREG $50,$FF / RET).
; A request it cannot serve (no such block, wrong length) returns as a failed load (NC, NZ),
; and the game asks again, as it would of a wrong tape.
;
; Build: nexclash/new_zealand_story.py loader_code() (pinned sjasmplus --zxnext --raw, -DCV=0x43 -DBCV=0xB021: measured on a real-tape load)
; Engine new_zealand_story; GPL-3.0-or-later, as NexClash (Dean Woodyatt, bleughb/nexclash).

EXIT    equ $43B6           ; the stub's NEXTREG $50,$FF / RET
LEVBLK  equ $5CA0           ; the game's next-block number (0..36)
DIR     equ $0200           ; 37 x (page, length lo, length hi, source lo, source hi)
HDRS    equ $0400           ; 37 x 16 raw header blocks (flag .. checksum), from the tape

        org $0100
entry:
        di
        ld b,d
        ld c,e                  ; BC = length asked for
        push ix
        pop de                  ; DE = destination
        cp $AA
        jr z,header
        sub $81
        cp 37
        jr nc,fail
        ld l,a
        add a,a
        add a,a
        add a,l                 ; 5k
        ld l,a
        ld h,DIR>>8
        ld a,(hl)
        inc hl
        nextreg $51,a           ; the block's page at 0x2000
        ld a,(hl)
        inc hl
        cp c
        jr nz,fail
        ld a,(hl)
        inc hl
        cp b
        jr nz,fail
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = its first byte after the flag
        ex af,af'
        ld a,CV
        jr copy
header:
        ld a,c
        cp 14
        jr nz,fail
        ld a,b
        or a
        jr nz,fail
        ld a,(LEVBLK)
        cp 37
        jr nc,fail
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,HDRS>>8
        ld h,a
        inc hl                  ; HDRS + 16k + 1
        ex af,af'
        ld a,CV
copy:
        ex af,af'               ; A' = C at LD-FLAG
        add ix,bc               ; IX = destination + length
        ldir                    ; HL -> the checksum byte
        ld a,(hl)
        ld l,a
        ld h,0                  ; L = last byte read, H = parity 0
        nextreg $51,$FF
        ex af,af'
        ld c,a
        xor a                   ; Z, PV, NC: as XOR L of a matching flag
        ld a,c
        rra                     ; LD A,C / RRA in LD-FLAG
        ex af,af'               ; AF' as LD-FLAG leaves it
        ld de,$05CD
        push de
        ld de,$05E6
        push de
        pop de
        pop de                  ; the ROM's two return addresses, left below S
        ld de,0
        ld bc,BCV               ; B and C as the last edge leaves them
        ld a,c
        and 7
        or 8
        out ($FE),a             ; the border (and MIC) as the last edge set it
        xor a
        cp 1                    ; A = 0 and F as LD-BYTES's LD A,H / CP 1
        jp EXIT
fail:
        nextreg $51,$FF
        xor a
        inc a                   ; NC, NZ: a failed load
        jp EXIT
