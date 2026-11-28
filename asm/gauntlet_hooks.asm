; Gauntlet (US Gold, 1986; 48K, the 128K's AY): every cell of the play window as a painted tile of the Next's
; tile layer. Facts and design: games/gauntlet.md.
;
; The game draws blocks and projectiles into a hidden copy of the screen (0xC000-0xDAFF) and
; sends it to the screen with three stack copies, interrupts off (0x9CDC: top third, attributes, the rest of the
; 20-row window). Nothing of the game changes:
;   e_c1 / e_c2 / e_c3  the three CALLs of the copies: 28 MHz, the game's own copy, then the rest of its own time
;                       waited out. Before the first copy, the tile pass: each of the window's 640 cells is
;                       looked up by its 8 bytes and its attribute; a painted one gets a tile definition (205
;                       at a time, the least recently shown replaced) and its map entry, any other the clear
;                       tile: the game's own cell shows there.
;   e_cl                the CALL of the hidden copy's clear after the copies: 28 MHz; the time it saves is waited
;                       out at the next first copy (it pays for the tile pass on a screen full of walls).
;   e_pre               the CALL after the game's HALT / DI. "Steady speed" (V_STEADY, set by the build): the game
;                       runs at 28 MHz and every update is shown a fixed number of frames after the last.
; Code in the alt ROM from 0x2800; inside a hook the state page is at slot 0, the tile layer's page
; (bank 7's first half) at slot 2, the cell table at slots 3-5, a definitions page at slot 2 for one copy.
; Interrupts are off around the copies (the game's own DI).
        DEVICE ZXSPECTRUMNEXT
WORK    EQU 26                  ; the state page
TPAGE   EQU 14                  ; bank 7's first 8K: the tile map (40 x 32 x 2 bytes) and the definitions, both from 0
EPAGE   EQU 28                  ; 3 pages at 0x6000: the cell table (15 bytes a cell)
EPAGE4  EQU 57                  ; its fourth page, at 0xE000
DPAGE   EQU 31                  ; from here: the painted definitions, 256 a page
V_SPEED EQU 0x0100
HLIB_V_R EQU 0x0101             ; 3 bytes
V_SP    EQU 0x0104              ; word: the game's stack inside a hook
V_STAMP EQU 0x0106              ; this pass's number, 1-255
V_NEXT  EQU 0x0107              ; the slot the last search stopped at
V_CELL  EQU 0x0108              ; word: the cell in the hidden copy
V_AT    EQU 0x010A              ; its attribute
V_FULL  EQU 0x010B              ; cells left unpainted in this pass for want of a free definition
V_LAST  EQU 0x010C              ; steady speed: the game's frame counter when the last update was shown
V_STEADY EQU 0x010D             ; frames an update, 0 = the original's pace (the build sets it)
V_INIT  EQU 0x010E              ; the tile layer's page has been cleared
V_RP    EQU 0x010F              ; R at e_pre
COPYB   EQU 0x9D3B              ; the game's bitmap copy
COPYA   EQU 0x9DA3              ; its attribute copy
SPSAVE  EQU 0x8489              ; where both keep the stack pointer
CLEAR   EQU 0xB4FF              ; the game's clear of the hidden copy
LDLOOP  EQU 0x9221              ; the level loader's DI, before its load loop
MAIN    EQU 0x8400              ; the main game's entry
NBLK    EQU 31                  ; level blocks on the tape
V_BLKN  EQU 0x0114              ; the block the last load gave
FRAMES  EQU 0x8497              ; its frame counter (the interrupt handler's INC (IY+24))
SHOTPAGE EQU 58                 ; scratch, mapped only with interrupts off
SHOTMASK EQU 0x1B00             ; 18 records of 32 packed bitmap bytes
SHOTFLAGS EQU 0x1D40            ; one flag per playfield cell
DIRTY   EQU 0x0600              ; up to 72 saved bitmap addresses
SHOTATTR EQU 0x06A0             ; 18 four-byte Next sprite descriptors
V_SHOTS EQU 0x0115
V_DIRTY EQU 0x0116
V_HALF  EQU 0x0117
V_SHOWN EQU 0x0118
V_SMALL EQU 0x0119
V_DEST  EQU 0x011B
TBUF    EQU 0x0120              ; 32 bytes: a definition on its way between pages
PBUF    EQU 0x0800              ; 8 x 256: the panel's rows as the screen has them (bytes 0x80-0xFF of each line)
PPREV   EQU 0x1800              ; the same, as the last pass saw them
TBUF2   EQU 0x0700              ; 64 bytes: a panel cell's pixels on their way to Layer 2
V_PCELL EQU 0x0110              ; word: the panel cell being drawn
V_ENT   EQU 0x0112              ; word: the entry find stopped at (its slot byte)
L2PAGE  EQU 18                  ; Layer 2: bank 9, pages 18-23
HLIB_V_PACE EQU 0x0140          ; 26 bytes
HLIB_PACE_NL EQU 311
HSTK    EQU 0x0300              ; the hooks' stack, below this
STAMPS  EQU 0x0300              ; 256 bytes: the pass that last showed each definition slot
OWNER   EQU 0x0400              ; 256 words: the cell entry (its slot byte) that owns each slot, 0 = none
BKT     EQU 0x1000              ; 1024 words: the first entry of each chain, 0 = none
MAP0    EQU 0x4000 + (4 * 40 + 4) * 2   ; the map entry of the window's first cell
E_SLOT  EQU 11                  ; a cell entry: next (word), 8 bytes, attribute, slot, palette << 4, page, number in it

        ORG 0x2800              ; (the 48K ROM below this is left as it is: the game loads its levels through it)
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_LEAN
        DEFINE HLIB_PACE_CAP 0x0C00
        INCLUDE "lib/hlib_pace.asm"

; A copy's wrapper. tiles: 1 = the tile pass first. t: the label of the copy's own time (1/16 lines).
        MACRO WRAP tiles, t, rin, rout
        push af
        ld a,r
        nextreg 0x50,WORK
        ld (HLIB_V_R),a
        pop af
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPEED
        push af
        push bc
        push de
        push hl
        call hlib_pace_open
        IF tiles
        call tilepass
        ENDIF
        ld a,rin
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x50,255
        ENDM
        MACRO WRAPEND t, rout
        nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ld hl,D_COPY            ; this hook's own entry and exit, outside the window
        call hlib_debt_add
        ld hl,(t)
        ld a,(V_STEADY)
        or a
        jr z,.w
        ld hl,0                 ; steady speed: no wait here, the update's frames are counted at e_halt
.w:     HLIB_SPEED_OUT V_SPEED
        ld a,(V_SPEED)
        call hlib_pace_wait
        ld a,rout
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x50,255
        ret
        ENDM

; ---------------------------------------------------------------- CALL bitmap copy, top third (A = 0x40, HL = 0xC000)
e_c1:   WRAP 1, T_C1, R_IN, R_OUT
        call COPYB
        ld (SPSAVE),sp          ; what the copy's own entry stores in the original
c1_end: WRAPEND T_C1, R_OUT
; ---------------------------------------------------------------- CALL attribute copy
e_c2:   WRAP 0, T_C2, R_IN, R_OUT
        call COPYA
        ld (SPSAVE),sp
c2_end: WRAPEND T_C2, R_OUT
; ---------------------------------------------------------------- CALL bitmap copy, the rest
e_c3:   WRAP 0, T_C3, R_IN, R_OUT
        call COPYB
        ld (SPSAVE),sp
c3_end: WRAPEND T_C3, R_OUT
R_IN    EQU 0                   ; set from the verifier's R comparison (games/gauntlet.md)
R_OUT   EQU 107                 ; -21
D_COPY  EQU 98                  ; calibrated so an update takes the original's time (games/gauntlet.md)

; ---------------------------------------------------------------- CALL 0xB4FF: the hidden copy cleared for the next update
; Interrupts are on here and the game's handler reads the ROM, so nothing is mapped and nothing waits: the clear
; runs at 28 MHz and the time it saves is waited out at the next update's first copy (its target includes it).
; The original's pace only: the steady-speed build leaves this CALL as it is.
e_cl:   push af                 ; the caller's A goes through the clear unchanged: kept (the clear sets F, B, C)
        ld bc,0x243B            ; the caller's speed (NR 7 bits 1:0) ...
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld b,a
        pop af                  ; ... A back ...
        push bc                 ; ... and the speed on the stack (in its high byte: 4 bytes below SP at most here)
        nextreg 0x07,3
        call CLEAR              ; the 28 MHz clear's saved time pays for the tile pass (games/gauntlet.md)
        ex (sp),hl              ; H = the saved speed, the caller's HL in its slot (6 bytes below SP at most:
        push af                 ; STACK, with this hook's own return address); the clear's AF kept
        ld a,h
.n_spd: nextreg 0x07,a          ; the caller's speed back (it was a fixed 3.5 MHz: F8 lost)
        pop af
        ex (sp),hl              ; HL back
        inc sp                  ; the speed word dropped, no flag touched
        inc sp
        ld (SPSAVE),sp          ; what the clear's own entry stores in the original
        push af
        push bc
        ld a,r
        ld b,a
.n_r:   add a,R_CL
        xor b
        and 0x7F
        xor b
        ld r,a
        pop bc
        pop af
        ret
R_CL    EQU 95                  ; -33 (the speed kept and given back: 19 more R steps)

; ---------------------------------------------------------------- the level blocks from memory (a build with the tape)
; The tape's second side is 31 headerless blocks of levels. The game asks for flag 0x80 at the start of a game (the
; first block) and for flag 0xC0 after that: whichever such block comes next on the tape, round and round.
; e_ld0 (CALL 0xB4FF at the loader's start, 0x9203): the clear, then straight to the load: the "start the tape"
;       messages and the wait for a key are left out.
; e_load (CALL 0x056B, the ROM's loader, 0x9247; interrupts off): the block's bytes, as the loader stores them (its
;       data and its checksum byte), copied to 0xC000 from the pages they sit in. The game checks the block's end
;       mark itself and runs the block's own code.
e_ld0:  call CLEAR
        jp LDLOOP
e_load: nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        ex af,af'               ; the flag asked for
        cp 0x80
        ld a,0
        jr z,.first
        ld a,(V_BLKN)
        inc a
.n_wrap: cp NBLK
        jr c,.first
        ld a,1                  ; after the last block the tape is rewound: the first 0xC0 block again
.first: ld (V_BLKN),a
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        ld de,BLKT
        add hl,de
        ld a,(hl)
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        ex de,hl
        ld de,0xC000
.n_cp:  ldir
        nextreg 0x52,10
        nextreg 0x53,11
        push de
        pop ix                  ; where the loader stops
        ex af,af'
        ld sp,(V_SP)
        nextreg 0x50,255
        ret

; ---------------------------------------------------------------- the main game from memory (a build from the title)
; The tape's loader (0xFF00) runs the front end (title, characters, controls), then loads two more blocks of side
; A: flag 0x81 to 0x73DA and flag 0x82, the main game, to 0x8400, and jumps to 0x8400. e_main (the loader's
; LD HL,0 after the front end returns, 0xFF12): both blocks copied from their pages, piece by piece through
; slot 2, and the jump. The main game's bytes in the pages already carry this build's own CALLs.
; The loader's stack is in slot 2 (0x5Bxx), so nothing here uses the stack; interrupts off while slot 2 is away.
e_main: di
        ld ix,MAINT
.l:     ld a,(ix+0)
        or a
        jr z,.done
        nextreg 0x52,a
        ld l,(ix+1)
        ld h,(ix+2)
        ld e,(ix+3)
        ld d,(ix+4)
        ld c,(ix+5)
        ld b,(ix+6)
.n_cp:  ldir
        ld de,7
        add ix,de
        jr .l
.done:  nextreg 0x52,10
        jp MAIN

; ---------------------------------------------------------------- CALL 0xB8FB, after the game's HALT / DI
; The original's pace: nothing. Steady speed (V_STEADY frames an update, the game at 28 MHz): wait, with the
; game's own interrupt handler running, until its frame counter (0x8497) is that far past the last update's.
e_pre:  nextreg 0x50,WORK
        push af
        push hl
        ld a,r
        ld (V_RP),a
        ld a,(V_STEADY)
        or a
        jr z,.orig
.wait:  ld a,(FRAMES)
        ld hl,V_LAST
        sub (hl)
        ld hl,V_STEADY
        cp (hl)
        jr nc,.go
        pop hl
        pop af
        nextreg 0x50,255
        ei
        halt
        di
        nextreg 0x50,WORK
        push af
        push hl
        jr .wait
.go:    ld a,(FRAMES)
        ld (V_LAST),a
.orig:  ld a,(V_RP)
        ld l,a
.n_r:   add a,R_PRE
        xor l
        and 0x7F
        xor l
        ld r,a
        pop hl
        pop af
        nextreg 0x50,255
        jp 0xB8FB
R_PRE   EQU 117                 ; -11

; ---------------------------------------------------------------- the tile pass
tilepass:
        ; The status panel (screen rows 20-23) is drawn straight on the screen, which slot 2 is about to hide:
        ; its 4 rows of 8 lines go to the state page first, laid out as the screen has them.
        ld hl,0x5080
        ld de,PBUF + 0x80
        ld a,8
.pc:    push hl
        push de
        ld bc,128
        ldir
        pop de
        pop hl
        inc h
        inc d
        dec a
        jr nz,.pc
        ld hl,0x5A80            ; a cell whose ink is its paper is hidden by the game (a number kept dark): it
        ld de,PBUF + 0x80       ; counts as blank
        ld b,128
.vis:   bit 4,e                 ; (columns 16-31 hold the logo: the game blinks it this way; it is shown steady)
        jr nz,.vn
        ld a,(hl)
        ld c,a
        rrca
        rrca
        rrca
        xor c
.n_vis: and 7
        jr nz,.vn
        push de
        ld c,8
        xor a
.vz:    ld (de),a
        inc d
        dec c
        jr nz,.vz
        pop de
.vn:    inc hl
        inc e
        djnz .vis
        nextreg 0x53,EPAGE
        nextreg 0x54,EPAGE + 1
        nextreg 0x55,EPAGE + 2
        nextreg 0x57,EPAGE4     ; (the game's stack is up there: a hook has its own, interrupts are off)
        push iy
        ld a,(V_INIT)
        or a
        jr nz,.ready
        inc a
        ld (V_INIT),a
        ld a,L2PAGE             ; Layer 2's six pages: clear (its colour 0 is the transparent one)
.cl2:   nextreg 0x52,a
        call .wipe
        inc a
        cp L2PAGE + 6
        jr nz,.cl2
        nextreg 0x52,TPAGE      ; the tile layer's page: bank 7 holds what the 128K left there
        call .wipe
        nextreg 0x6B,0x81       ; both layers shown from here: tiles on, 40 x 32, 2-byte entries, over the ULA
        push bc
        ld bc,0x123B
        ld a,2
        out (c),a               ; Layer 2 shown
        pop bc
.ready: call panel
        nextreg 0x52,TPAGE
        xor a
        ld (V_FULL),a
        ld hl,V_STAMP
        inc (hl)
        jr nz,.s
        inc (hl)
.s:     ld iy,MAP0
        ld hl,0xC000
        ld de,0xD800
        ld b,20
.row:   push bc
        ld b,32
.cell:  push bc
        push hl
        push de
        call onecell
        pop de
        pop hl
        pop bc
        inc iy
        inc iy
        inc de
        inc l
        djnz .cell
        ld a,l                  ; 32 cells on: the next character row, and the next third when L wraps
        and 0xE0
        jr nz,.nr
        ld a,h
        add a,8
        ld h,a
.nr:    ld bc,16
        add iy,bc
        push hl
        push de
.n_tick: call hlib_pace_tick    ; (the pass can last more than a frame: the window's time is read every row)
        pop de
        pop hl
        pop bc
        djnz .row
        call shotpass
        pop iy
        nextreg 0x52,10
        nextreg 0x53,11
        nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x57,1
        ret
.wipe:  push af
        ld hl,0x4000
        ld de,0x4001
        ld bc,0x1FFF
        ld (hl),0
        ldir
        pop af
        ret

; The panel on Layer 2: each of its 128 cells that changed since the last pass is looked up by its bytes alone
; (the game cycles the logo's colours) and its 64 painted pixels, or 64 clear ones, go to Layer 2's last page.
panel:  ld hl,PBUF + 0x80
        ld c,4
.prow:  ld b,32
.pcell: push bc
        push hl
        ld d,h                  ; the same cell as the last pass saw it
        ld e,l
        ld a,d
        add a,(PPREV - PBUF) >> 8
        ld d,a
        ld b,8
        ld c,0
.pd:    ld a,(de)
        cp (hl)
        jr z,.pe
        ld a,(hl)
        ld (de),a
        inc c
.pe:    inc h
        inc d
        djnz .pd
        ld a,c
        or a
        jr z,.pn                ; unchanged
        pop hl
        push hl
        ld (V_PCELL),hl
        ld de,anyat
        call find
        ld hl,TBUF2             ; 64 clear pixels, or the painted ones
        jr c,.blank
        ld hl,(V_ENT)           ; the entry's slot byte: its page and its number are two on
        inc hl
        inc hl
        ld a,(hl)
        inc hl
        ld l,(hl)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        nextreg 0x52,a
        ld de,TBUF2
        ld bc,64
        ldir
        jr .draw
.blank: ld d,h
        ld e,l
        inc de
        ld (hl),0
        ld bc,63
        ldir
.draw:  nextreg 0x52,L2PAGE + 5 ; Layer 2's lines 160-191
        ld hl,(V_PCELL)         ; the cell: line PBUF + 0x80 + row * 32 + col -> Layer 2 (row * 8, col * 8)
        ld a,l
        sub 0x80
        ld c,a
        and 0x1F
        add a,a
        add a,a
        add a,a
        ld e,a                  ; x
        ld a,c
        rlca
        rlca
        rlca
        and 3                   ; row
        add a,a
        add a,a
        add a,a
        add a,0x40
        ld d,a                  ; DE = the cell's first pixel
        ld hl,TBUF2
        ld a,8
.dl:    push de
        ld bc,8
        ldir
        pop de
        inc d
        dec a
        jr nz,.dl
.pn:    pop hl
        pop bc
        inc l
        dec b
        jp nz,.pcell
        dec c
        jp nz,.prow
        ret

; HL = the cell's first byte in the hidden copy, DE = its attribute, IY = its map entry.
onecell: call find
        jr c,.clear
        ld a,(hl)
        or a
        jr nz,.have
        call alloc
        or a
        jr z,.full
.have:  ld (iy+0),a
        ld e,a
        ld d,STAMPS >> 8
        ld a,(V_STAMP)
.n_st:  ld (de),a
        inc hl
        ld a,(hl)
.n_pal: ld (iy+1),a
        ret
.full:  ld hl,V_FULL
        inc (hl)
.clear: ld (iy+0),0
        ld (iy+1),0
        ret

; HL = a cell's first byte (its 8 lines 256 apart), DE = its attribute -> HL = its entry's slot byte (V_ENT too),
; no carry; carry when no entry has these bytes and this attribute (a blank cell is never looked for).
find:   ld (V_CELL),hl
        ld a,(de)
        ld (V_AT),a
        ld bc,0
        REPT 8
        ld a,(hl)
        inc h
        ld d,a
        xor b
        rlca
        ld b,a
        ld a,d
        add a,c
        ld c,a
        ENDR
        ld a,b
        or c
        jr z,.none
        ld a,(V_AT)
        xor b
        ld l,a
        ld a,c
.n_bk:  and 3
        ld h,a
        add hl,hl
        ld de,BKT
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
.chain: ld a,h
        or l
        jr z,.none
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de                 ; the next of the chain
        ld de,(V_CELL)
        ld b,8
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.no
        inc d
        inc hl
        djnz .cmp
        ld a,(V_AT)
.n_at:  cp (hl)
        jr nz,.no
        pop de
        inc hl                  ; the entry's slot
        ld (V_ENT),hl
        or a
        ret
.no:    pop hl
        jr .chain
.none:  scf
        ret

; A definition slot for the entry whose slot byte HL points at: the next one no cell of this pass shows; its
; owner loses it; the entry's 32 bytes go into it. -> A = the slot, 0 = none free. HL kept.
alloc:  push hl
        ld a,(V_NEXT)
        ld e,a
        ld b,205
.find:  inc e
        jr nz,.a
        inc e
.a:     ld a,e
        cp 10                   ; slots 10-59 are the map's own bytes for the window's rows
        jr nz,.b
        ld e,60
.b:     ld d,STAMPS >> 8
        ld a,(de)
        ld c,a
        ld a,(V_STAMP)
        cp c
        jr nz,.got
        djnz .find
        pop hl
        xor a
        ret
.got:   ld a,e
        ld (V_NEXT),a
        ld l,e
        ld h,0
        add hl,hl
        ld bc,OWNER
        add hl,bc
        ld c,(hl)
        inc hl
        ld b,(hl)               ; the old owner's slot byte
        ld a,b
        or c
        jr z,.n1
        xor a
.n_ev:  ld (bc),a
.n1:    pop bc                  ; the new owner's
        push bc
        ld (hl),b
        dec hl
        ld (hl),c
        ld a,e
        ld (bc),a
        ld h,b
        ld l,c
        inc hl
        inc hl
        ld a,(hl)               ; the definitions' page
        inc hl
        ld l,(hl)               ; the definition's number in it
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        nextreg 0x52,a
        push de
        ld de,TBUF
        ld bc,32
        ldir
        nextreg 0x52,TPAGE
        pop de
        ld l,e
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        ex de,hl
        ld hl,TBUF
        ld bc,32
        ldir
        ld a,(V_NEXT)
        pop hl
        ret

; Keep the shooter's kind before either impact path clears bit 6 of (IX+3).
; The readable sprite selector holds it until the draw. The game and its
; interrupt handler use no Next registers. Selecting a slot changes no image.
e_kind: push af
        push bc
        ld a,r
        ld b,a
        ld a,(ix+3)
        nextreg 0x34,a
        ld a,b
        add a,120
        xor b
        and 127
        xor b
        ld r,a
        pop bc
        pop af
        bit 6,(ix+3)
        jp 0x8CBA

; Both original plotters execute DI / LD SP,HL / LD A,D. HL is the live
; drawing, DE its screen address. Resume with the original bitmap stack.
        MACRO CAPTURE small, resume
        di
        nextreg 0x50,WORK
        ld sp,HSTK
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ld a,small
        ld (V_SMALL),a
        HLIB_SPEED_IN_ABC V_SPEED
        nextreg 0x52,SHOTPAGE
        call save_shot
        ; Reclaim the two extra hooks' measured cost from the copy waits.
        ; 1/16 scanline is 14.25 T at the original speed.
        IF small
        ld hl,62
        ELSE
        ld hl,74
        ENDIF
        call hlib_debt_add
        nextreg 0x52,10
        HLIB_SPEED_OUT_A V_SPEED
        ld a,117
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x50,255
        ld sp,hl
        ld a,d
        jp resume
        ENDM
e_wide: CAPTURE 0,0x8DFE
e_rock: CAPTURE 1,0x8EC2

; Save a two-byte source row exactly as POP takes it. The compact rock
; plotter uses only the first byte of each word. Pad both to 16 x 16.
save_shot:
        ld (V_DEST),de
        ld a,(V_SHOTS)
        cp 18                   ; two player records plus the game's 16 mobile records
        ret nc
        inc a
        ld (V_SHOTS),a
        dec a
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,SHOTATTR
        add hl,bc
        ld a,e                  ; x in Next coordinates, including bit 8
        rlca
        rlca
        rlca
        and 0xF8
        add a,32
        ld (hl),a
        inc hl
        ld a,0
        rla
        ld b,a
        ld a,e
        and 0xE0
        rrca
        rrca
        ld c,a
        ld a,d
        and 0x18
        rlca
        rlca
        rlca
        or c
        add a,32
        ld (hl),a
        inc hl
        ld a,ixh
        cp 0x84
        jr nz,.monster
        ld a,ixl
        cp 0x30
        ld a,(0xFFFF)
        jr z,.colour
        ld a,(0xFFFE)
        jr .colour
.monster:
        push bc
        ld bc,0x243B
        ld a,0x34
        out (c),a
        inc b
        in a,(c)
        pop bc
        and 0x40
        rlca
        rlca
        add a,4
.colour:
        and 7
        rlca
        rlca
        rlca
        rlca
        or b
        ld (hl),a
        inc hl
        ld a,(V_SHOTS)
        dec a
        ld c,a
        ld a,(V_HALF)
        or c
        or 0x80
        ld (hl),a
        ld a,c
        ld h,0
        ld l,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x4000+SHOTMASK
        add hl,de
        ex de,hl
        pop hl
        ld a,(V_SMALL)
        or a
        jr nz,.small
        xor a
        call .four              ; wide plot starts two lines down
        ld bc,16                ; six upper rows, then the first two lower rows
        ldir
        dec de                  ; the game uses INC C at 8E8C and 8E9E, so row pairs share Y
        dec de
        call .merge
        ldi
        ldi
        dec de
        dec de
        call .merge
        ldi
        ldi
        xor a
        call .four
        call .four
        jr .background
.small: ld b,8
        xor a
.row:   ldi
        inc bc                  ; LDI decrements BC, keep the loop counter
        inc hl
        ld (de),a
        inc de
        djnz .row
        ld b,16
.pad:   ld (de),a
        inc de
        djnz .pad
.background:
        ld hl,(V_DEST)
        call keep_cell
        ld a,(V_SMALL)
        or a
        ret nz
        inc l
        call keep_cell
        dec l
        ld de,32
        add hl,de
        ld a,l                  ; advancing L past FF moves to the next screen third
        and 0xE0
        jr nz,.bottom
        ld a,h
        add a,7
        ld h,a
.bottom:call keep_cell
        inc l
        jp keep_cell
.merge: REPT 2
        ld a,(de)
        or (hl)
        inc hl
        ld (de),a
        inc de
        ENDR
        ret
.four:  ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ret

; Save the first scenery under each cell once, even when shots overlap.
; The shadow page uses the hidden screen's layout. Its tail holds the flags.
keep_cell:
        push hl
        ld a,h
        rrca
        rrca
        rrca
        and 3
        ld h,a
        ld de,0x4000+SHOTFLAGS
        add hl,de
        ld a,(hl)
        or a
        jr nz,.done
        inc (hl)
        ld de,0xD800-(0x4000+SHOTFLAGS)
        add hl,de
        ld a,(hl)
        res 7,h
        ld (hl),a
        pop hl
        push hl
        ld a,(V_DIRTY)
        ld e,a
        inc a
        inc a
        ld (V_DIRTY),a
        ld d,DIRTY >> 8
        ld a,l
        ld (de),a
        inc e
        ld a,h
        ld (de),a
        ld d,h
        res 7,d
        ld e,l
        REPT 8
        ld a,(hl)
        ld (de),a
        inc h
        inc d
        ENDR
.done:  pop hl
        ret

; After the normal pass, look up the saved clean cells using the same tile
; allocator. The game still copies its own, fully drawn screen to the ULA.
shotpass:
        ld a,(V_SHOTS)
        or a
        jp z,.commit
        nextreg 0x56,SHOTPAGE
        ld a,(V_DIRTY)
        ld e,a
        ld d,DIRTY >> 8
.repair:dec e
        ld a,(de)
        ld h,a
        dec e
        ld a,(de)
        ld l,a
        push de
        push hl
        ld a,h
        rrca
        rrca
        rrca
        and 3
        ld h,a
        ld de,0xC000+SHOTFLAGS
        add hl,de
        ld (hl),0
        ld de,0xD800-(0xC000+SHOTFLAGS)
        add hl,de
        push hl                 ; attribute
        ld a,l
        and 31
        ld c,a
        ld b,0
        ld de,0xD800
        or a
        sbc hl,de
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l                    ; cell row
        ld d,l
        ld e,80
        mul d,e
        ld hl,MAP0
        add hl,de
        add hl,bc
        add hl,bc
        push hl
        pop iy
        pop de
        pop hl
        call onecell
        pop de
        ld a,e
        or a
        jr nz,.repair
        ; Upload to the half that was hidden throughout the previous update.
        ld a,(V_HALF)
        ld bc,0x303B
        out (c),a
        ld hl,0xC000+SHOTMASK
        ld a,(V_SHOTS)
.pattern:
        push af
        ld b,32
.byte:  ld d,(hl)
        inc hl
        ld c,0x5B
        REPT 8
        rlc d
        sbc a,a
        and 1
        out (c),a
        ENDR
        djnz .byte
        pop af
        dec a
        jr nz,.pattern
        nextreg 0x56,0
.commit:
        ld a,(V_SHOTS)
        ld b,a
        ld a,(V_SHOWN)
        sub b
        ld e,a
        ld a,b
        ld (V_SHOWN),a
        ; Write the four attributes of each shot, then hide expired slots.
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,SHOTATTR
        ld a,(V_SHOTS)
        or a
        jr z,.hide
        ld b,a
        ld c,0x57
.show:  REPT 3
        ld a,(hl)
        out (c),a
        inc hl
        ENDR
.visible:ld a,(hl)
        out (c),a
        inc hl
        djnz .show
.hide:  ld a,e
        or a
        jr z,.done
        jp m,.done
        ld b,a
        ld c,0x57
        xor a
.erase: REPT 4
        out (c),a
        ENDR
        djnz .erase
.done:  xor a
        ld (V_DIRTY),a
        ld (V_SHOTS),a
        ld a,(V_HALF)
        xor 32
        ld (V_HALF),a
        ret

anyat:  DB 0xFF
        ALIGN 16
BLKT:   DS NBLK * 5             ; a block: its page, its address there (0x4000 up), its bytes (the build fills it)
MAINT:  DS 8 * 7 + 1            ; the main game's pieces: page (0 ends), from, to, bytes
; ---------------------------------------------------------------- the copies' own times, 1/16 lines (the build fills them)
        ALIGN 16
T_C1:   DW 0
T_C2:   DW 0
T_C3:   DW 0
CODE_END:
ROM_END:
        SAVEBIN "gauntlet_rom.bin",0x2800,ROM_END-0x2800

        ORG 0xD000
; The stub's setup: the tile layer's palette and window (its page is cleared by the first tile pass).
setup:  ld hl,pbuf              ; the printer buffer as the snapshot has it (the title's stack is there): NEXLOAD wrote over it
        ld de,0x5B00
        ld bc,256
        ldir
        nextreg 0x43,0x30       ; tile layer palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal9
        ld b,0
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        nextreg 0x43,0x00
        nextreg 0x4C,0          ; index 0 clear
        nextreg 0x6C,0
        nextreg 0x6E,0x80       ; the map: bank 7, from its first byte
        nextreg 0x6F,0x80       ; the definitions: the same (slots 10-59 are the window's map bytes)
        nextreg 0x2F,0
        nextreg 0x30,0
        nextreg 0x31,0
        nextreg 0x1C,8
        nextreg 0x1B,16         ; the window: the play window's 32 x 20 cells
        nextreg 0x1B,143
        nextreg 0x1B,32
        nextreg 0x1B,191
        nextreg 0x6B,0x00       ; off until the first tile pass has cleared its page
        nextreg 0x43,0x10       ; Layer 2's palette: the painted colours, 0 the transparent one
        nextreg 0x40,0
        ld hl,pal2
        ld b,0
.p2:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .p2
        nextreg 0x43,0x00
        nextreg 0x12,9          ; Layer 2 in bank 9
        nextreg 0x14,0xE3       ; the transparent colour
        nextreg 0x43,0x20       ; sprite palette 0, opaque index 1 on each line
        ld hl,shotpal
        ld b,6
        ld c,1
.spal:  ld a,c
        nextreg 0x40,a
        ld a,(hl)
        inc hl
        nextreg 0x44,a
        ld a,(hl)
        inc hl
        nextreg 0x44,a
        ld a,c
        add a,16
        ld c,a
        djnz .spal
        nextreg 0x43,0
        nextreg 0x4B,0          ; transparent sprite index
        ld b,128                ; do not inherit visible slots from the loader
        xor a
.hide:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .hide
        nextreg 0x15,0x01       ; S L U: Layer 2 over the ULA and the tile layer (shown by the first tile pass)
speed:  nextreg 0x07,0        ; speed: start-up (once, before the game) - (the steady-speed build: 3 = 28 MHz)
        ret
shotpal: DS 12
pal9:   DS 512
pal2:   DS 512
pbuf:   DS 256                  ; the snapshot's 0x5B00-0x5BFF (the build fills it in)
SETUP_END:
        SAVEBIN "gauntlet_setup.bin",0xD000,SETUP_END-0xD000
