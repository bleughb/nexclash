; Heartland (Odin, 1986, 48K): the figures as hardware sprites. Facts and design: games/heartland.md.
;
; Every game step composes the play window in a back buffer at 0xC000 (32 bytes a line): each figure is
; saved, then (buffer AND mask) OR graphic, by one of three plotters (0xA7D4, mirrored 0xA88D, small 0xA837);
; a large figure's cells are painted bright white in the attribute copy (0xA790); the foreground pieces go on
; top (0x9FAB); the buffer and the attribute copy go to the screen (0xA56F, 0xA615); the figures are put back.
; The game takes random numbers from a byte at address R * 257, anywhere in memory (0xBBF3), so the build
; keeps every byte of the game's memory and of the screen bitmap as the original has it:
;   e_big / e_mir / e_small  at the three plotters' entries: note what is plotted (buffer address, graphic,
;                            mask), with a copy of the shift buffer when the graphic is in it;
;   e_paint                  at the paint's entry: note each cell and its colour before the paint;
;   e_commit                 at the screen copy: patterns for the noted figures (4 bit: 1 ink, 2 the mask's
;                            cleared border, 0 clear; minus the pixels the foreground pieces own), the game's
;                            own copy at 28 MHz, then every sprite attribute in one run: each sprite lies on
;                            its figure's own pixels in the bitmap;
;   e_acopy                  at the attribute copy: the painted cells get their own colours back for the
;                            game's copy, then the paint again: the screen keeps the room's colours;
;   e_cls                    the whole-screen clear (0x5E5E): every sprite off;
;   e_random                 the random byte: the original's painted colour from the two attribute cells it
;                            can read (0x5959, 0x5A5A); the stubs end below 0x3939, the first ROM byte it can.
; The entries and exits sit in the 48K ROM's unused area (alt ROM); the bodies in a RAM copy of 0x2000-0x3FFF
; mapped at slot 1 inside a hook, the state in a second page at slot 4. The game's interrupt handler (0x60F3,
; IM 2 through a table of 0xF3: sound, the hourglass) saves every register and touches neither slot; it runs
; inside the hooks as it does in the game. Interrupts stay as the game has them.
        DEVICE ZXSPECTRUMNEXT
CODEP   EQU 24                  ; RAM copy of 0x2000-0x3FFF: the ROM's bytes, the stubs, the bodies from 0x2000
WORK    EQU 26                  ; the state page (slot 4 inside a hook; page 4 back at the exit)
COV     EQU 0x8000              ; 4,608 bytes: the pixels the foreground pieces own, as the buffer is laid out
COV_END EQU 0x92                ; high byte after the last coverage byte
FGC     EQU 0x9200              ; the foreground list the coverage was made from: count, then 4 bytes a piece
FGMAX   EQU 15
V_SPEED EQU 0x9240
HLIB_V_R EQU 0x9241             ; 3 bytes
V_N     EQU 0x9244              ; figures noted since the last copy
V_PREV  EQU 0x9245              ; attribute bytes the last copy showed
V_SET   EQU 0x9246              ; pattern set of the last copy: 0 or 64 (4-bit pattern numbers)
V_KIND  EQU 0x9247
V_BUF   EQU 0x9248              ; word
V_STP   EQU 0x924A              ; word: next free stash byte
V_DEST  EQU 0x924C              ; word
V_Q     EQU 0x924E              ; next 4-bit pattern number
V_ATP   EQU 0x9250              ; word: next attribute row
V_ROWS  EQU 0x9252
V_LNS   EQU 0x9253              ; bit 0: this copy shows 144 lines
V_X     EQU 0x9255              ; word
V_Y     EQU 0x9257
Z8      EQU 0x9258              ; 8 zero bytes: the coverage of a line outside the buffer
V_RB    EQU 0x9260              ; R before the game's routine
V_SPAN  EQU 0x9261              ; M1s the game's routine ran
V_PN    EQU 0x9262              ; cells noted before the paint
V_PP    EQU 0x9263              ; word: next paint record
V_VAL   EQU 0x9265
V_VAR   EQU 0x9266              ; the attribute copy's way this step: 1 plain, 2 ink limit, 3 one colour
V_CF    EQU 0x9267              ; 2 bytes: the two readable cells had their paint lifted
SA_B    EQU 0x9269              ; 2 bytes: what the build's screen holds at 0x5959, 0x5A5A
SA_O    EQU 0x926B              ; 2 bytes: what the original's holds
V_LIM   EQU 0x926D              ; the ink limit of the game's copy this step, 0 = none
V_RADD  EQU 0x926E              ; M1s the original's copy ran more than the build's
STASH   EQU 0x9280
STASH_END EQU 0x9840
ENTS    EQU 0x9840              ; 8 figures of 8 bytes: buffer address, graphic, mask, kind
MAXE    EQU 8
ATTRS   EQU 0x9880              ; 48 sprites of 5 bytes
NSPR    EQU 48
PREC    EQU 0x9970              ; 64 cells of 3 bytes: address, colour before the paint
PMAX    EQU 64
PFL     EQU 0x9A30              ; 64 bytes: the cell's paint was lifted
HLIB_V_PACE EQU 0x9A70           ; 26 bytes
HLIB_PACE_NL EQU 312
T_112   EQU 4667                ; the game's copy of 112 lines: 65,335 T, in 1/16 lines
T_144   EQU 5998                ; 144 lines: 83,978 T
D_NOTE  EQU 54                  ; a note's own time, added to what the copy's wait gives back
D_PAINT EQU 54
D_ACOPY EQU 154
PBUF    EQU 0x9B00              ; 3 blocks of 256: a block = two patterns side by side, 16 lines
TLO     EQU 0x9E00              ; (graphic nibble << 4 | mask nibble) -> the first two pixels
THI     EQU 0x9F00              ;                                       the last two
REV     EQU 0xFE                ; the game's bit-reverse table, high byte
FGLIST  EQU 0xA10B
LINES   EQU 0xAC19              ; bit 0: 144 lines this copy, else 112
ACOPY   EQU 0xD440              ; the attribute copy
CELL0   EQU ACOPY + 0x99        ; -> 0x5959
CELL1   EQU ACOPY + 0x19A       ; -> 0x5A5A
AMODE   EQU 0xBCA5              ; not zero: the plain attribute copy
ACNT    EQU 0xAC17              ; else counts down to the one-colour flash
APHASE  EQU 0xAC18              ; and this gives the ink limit

; ---------------------------------------------------------------- entries and exits: the same bytes in the alt ROM and the page
        ORG 0x386E
rom_start:
        MACRO STUB body
        nextreg 0x51,CODEP
        nextreg 0x54,WORK
        push af
        jp body
        ENDM
e_big:  STUB note0
e_mir:  STUB note1
e_small: STUB note2
e_paint: STUB paint
e_commit: STUB commit
e_acopy: STUB acopy
e_random: STUB random
e_cls:  STUB cls
; R as the original leaves it, the pages back, then the address on the stack.
x_ret:  ld (HLIB_V_R + 2),a
        ld a,(HLIB_V_R + 1)
        ld r,a
        ld a,(HLIB_V_R + 2)
        nextreg 0x54,4
        nextreg 0x51,255
        ret
; The random byte: the answer in V_VAL, or the byte at HL read once the pages are back.
x_rndv: ld a,(HLIB_V_R + 1)
        ld r,a
        ld a,(V_VAL)
        nextreg 0x54,4
        nextreg 0x51,255
        jp 0xBBFB
x_rndp: ld a,(HLIB_V_R + 1)
        ld r,a
        nextreg 0x54,4
        nextreg 0x51,255
        ld a,(hl)
        jp 0xBBFB
ROM_END:
        ASSERT ROM_END + 20 <= 0x3939   ; the random byte can read 0x3939, 0x3A3A, 0x3B3B, 0x3C3C: they stay the ROM's 0xFF
        SAVEBIN "heartland_rom.bin",0x386E,ROM_END-0x386E

; ---------------------------------------------------------------- the bodies: only in the page
        ORG 0x2000
code_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_LEAN
        INCLUDE "lib/hlib_pace.asm"

; The three plotters, entered with HL = mask, DE = graphic, HL' = buffer address.
note0:  xor a
        jr note
note1:
.n_mir: ld a,1
        jr note
note2:  ld a,2
        jr note
note:   ld (V_KIND),a
        ld a,r
        ld (HLIB_V_R),a
        HLIB_SPEED_IN V_SPEED
        call noted
        push de
        push hl
        ld hl,D_NOTE
        call hlib_debt_add
        pop hl
        pop de
.n_r:   ld a,R_NOTE
        call hlib_r_set
        push hl
        ld a,(V_KIND)
        add a,a
        add a,exits & 255
        ld l,a
        ld h,exits >> 8
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a
        ld (V_X),hl             ; the plotter's second instruction, for the RET
        pop hl
        pop af
        push hl
        ld hl,(V_X)
        ex (sp),hl
        HLIB_SPEED_OUT V_SPEED
        ld bc,0
        jp x_ret
        ALIGN 8
exits:  DW 0xA7D7,0xA890,0xA83A
R_NOTE  EQU 111                 ; -17: the hook's own M1s (the verifier compares R)

; V_KIND = kind, HL = mask, DE = graphic, HL' = buffer address. Keeps BC, DE, HL and the alternate set.
noted:  push bc
        push de
        push hl
        exx
        ld (V_BUF),hl
        exx
        ld a,(V_N)
        cp MAXE
        jr nc,.out
        inc a
        ld (V_N),a
        dec a
        add a,a
        add a,a
        add a,a
        add a,ENTS & 255
        ld c,a
        ld b,ENTS >> 8          ; BC = the figure's entry
        ld a,d
        cp 0xD6
        jr nz,.put              ; the graphic is not the shift buffer: its bytes stay until the copy
        push bc
        ld bc,136
        ld a,(V_KIND)
        cp 2
        jr nz,.l
        ld c,48
.l:     push hl                 ; the mask
        ld hl,(V_STP)
        add hl,bc
        add hl,bc
        ld a,h
        cp STASH_END >> 8
        jr c,.fits
        jr nz,.nofit
        ld a,l
        cp (STASH_END & 255) + 1
        jr c,.fits
.nofit: pop hl
        pop bc
        jr .put
.fits:  ex de,hl                ; HL = graphic
        ld de,(V_STP)
        push de
        push bc
        ldir
        pop bc
        pop af                  ; (the copy's address)
        pop hl                  ; mask
        push af
        push de
        ldir
        ld (V_STP),de
        pop hl                  ; the mask's copy
        pop de                  ; the graphic's copy
        pop bc
.put:   ld a,(V_BUF)
        ld (bc),a
        inc c
        ld a,(V_BUF + 1)
        ld (bc),a
        inc c
        ld a,e
        ld (bc),a
        inc c
        ld a,d
        ld (bc),a
        inc c
        ld a,l
        ld (bc),a
        inc c
        ld a,h
        ld (bc),a
        inc c
        ld a,(V_KIND)
        ld (bc),a
.out:   pop hl
        pop de
        pop bc
        ret


; The paint of a large figure's cells: HL = buffer address, IX = the figure. Each cell's address and colour are
; noted, the paint itself is the game's.
paint:  ld a,r
        ld (HLIB_V_R),a
        HLIB_SPEED_IN V_SPEED
        push bc
        push de
        push hl
        ld b,3
        ld a,(ix+9)
        and 7
        jr z,.b
        inc b
.b:     ld a,l
        and 31
        ld e,a
        ld a,h
        rrca
        rrca
        rrca
        ld d,a
        and 0xE0
        or e
        ld e,a
        ld a,d
        and 3
        ld d,a
        ld hl,ACOPY + 32
        add hl,de               ; the first cell, as 0xA79C works it out
        ld c,4
        ld de,(V_PP)
.row:   push bc
.cell:  ld a,(V_PN)
        cp PMAX
        jr nc,.full
        inc a
        ld (V_PN),a
        ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,(hl)
        ld (de),a
        inc de
.full:  inc hl
        djnz .cell
        pop bc
        ld a,32
        sub b
        add a,l
        ld l,a
        jr nc,.n
        inc h
.n:     dec c
        jr nz,.row
        ld (V_PP),de
        ld hl,D_PAINT
        call hlib_debt_add
        pop hl
        pop de
        pop bc
        ld a,R_PAINT
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        push hl
        ld hl,0xA795
        ex (sp),hl
        ld b,3
        ld a,(ix+9)
        jp x_ret
R_PAINT EQU 116

; The screen copy. With figures: their patterns, the game's copy at 28 MHz, the attributes.
commit: ld a,r
        ld (HLIB_V_R),a
        HLIB_SPEED_IN V_SPEED
        push hl
        ld a,(V_N)
        ld hl,V_PREV
        or (hl)
        jr nz,.work
        pop hl                  ; nothing noted, nothing shown: the game's copy as it is
        ld a,R_C0
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        push hl
        ld hl,0xA572
        ex (sp),hl
        ld hl,LINES
        jp x_ret
.work:  push bc
        push de
        push ix
        exx
        ex af,af'
        push af
        push bc
        push de
        push hl
        ld a,(LINES)
        ld (V_LNS),a
        call hlib_pace_open
.n_cov: call cover
        call build
        pop hl
        pop de
        pop bc
        pop af
        ex af,af'
        exx
        pop ix
        pop de
        pop bc
        pop hl
        pop af
        ld a,R_CCALL
        call hlib_r_set
        ld a,(HLIB_V_R + 1)
        ld r,a
        ld hl,LINES
        call 0xA572             ; the game's copy
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        call show
        HLIB_SPEED_OUT V_SPEED
        ld hl,T_112             ; wait out the rest of the time the game's copy takes at its own speed
        ld a,(V_LNS)
        rra
        jr nc,.t
        ld hl,T_144
.t:     ld a,(V_SPEED)
.n_wait: call hlib_pace_wait
        ld a,R_C1
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        jp x_ret
R_C0    EQU 114
R_CCALL EQU 0
R_C1    EQU 109

; The attribute copy. The noted cells that still hold their paint get their colour back for the game's copy.
acopy:  ld a,r
        ld (HLIB_V_R),a
        HLIB_SPEED_IN V_SPEED
        push hl
        ld hl,0
        ld (V_CF),hl
        ld a,(V_PN)
        or a
        jr nz,.work
        ld (SA_B),hl            ; no paint: the two cells are the original's
        ld (SA_O),hl
        pop hl
        ld a,R_A0
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        push hl
        ld hl,0xA618
        ex (sp),hl
        ld a,(AMODE)
        jp x_ret
.work:  push bc
        push de
        ; which way the game's copy goes this time
        ld c,1
        ld a,(AMODE)
        or a
        jr nz,.v
        inc c
        ld a,(ACNT)
        dec a
        jr nz,.v
        inc c
.v:     ld a,c
        ld (V_VAR),a
        ; lift the paint, last noted first
        ld a,(V_PN)
        ld b,a
        ld c,a
        add a,a
        add a,c
        ld e,a
        ld d,0
        ld hl,PREC
        add hl,de               ; after the last record
        ld a,b
        add a,PFL & 255
        ld e,a
        ld d,PFL >> 8           ; after the last flag
.lift:  dec e
        xor a
        ld (de),a
        dec hl
        ld c,(hl)               ; the colour before
        dec hl
        ld a,(hl)
        dec hl
        push hl
        ld l,(hl)
        ld h,a                  ; the cell
        cp ACOPY >> 8
        jr c,.no
        jr nz,.hi
        ld a,l
        cp ACOPY & 255
        jr c,.no
        jr .in
.hi:    cp (ACOPY + 576) >> 8
        jr c,.in
        jr nz,.no
        ld a,l
        cp (ACOPY + 576) & 255
        jr nc,.no
.in:    ld a,c
        or 0x47
        cp (hl)
        jr nz,.no               ; something else wrote the cell since
.n_lift: ld (hl),c
        ld a,1
        ld (de),a
.no:    pop hl
        djnz .lift
        pop de
        pop bc
        pop hl
        pop af
        HLIB_SPEED_OUT_A V_SPEED
        ld a,R_ACALL            ; R as the original has it there: the game's copy can read it (0xA6B0)
        call hlib_r_set
        ld a,(HLIB_V_R + 1)
        ld r,a
        ld a,(AMODE)
        call 0xA618             ; the game's copy, at the game's speed
        HLIB_R_IN
        HLIB_SPEED_IN V_SPEED
        push af
        push bc
        push de
        push hl
        ; the ink limit, as 0xA6C6 works it out (its first 448 cells), when the game's copy went that way
        xor a
        ld (V_RADD),a
        ld c,a
        ld a,(V_VAR)
        cp 2
        jr nz,.nl
        ld a,(APHASE)
        bit 3,a
        jr z,.p
        cpl
.p:     and 7
        jr nz,.q
        inc a
.q:     ld c,a
.nl:    ld a,c
        ld (V_LIM),a
        ; the paint again
        ld a,(V_PN)
        ld b,a
        ld hl,PREC
        ld de,PFL
.again: ld a,(de)
        or a
        jr z,.skip
        push hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,(hl)
        or 0x47
.n_again: ld (hl),a
        ld a,h
        cp CELL0 >> 8
        jr nz,.c1
        ld a,l
        cp CELL0 & 255
        jr nz,.c1
        ld a,1
        ld (V_CF),a
.c1:    ld a,h
        cp CELL1 >> 8
        jr nz,.c2
        ld a,l
        cp CELL1 & 255
        jr nz,.c2
        ld a,1
        ld (V_CF + 1),a
.c2:    pop hl
        ; a cell whose own ink is under the limit took the short way through the game's copy; painted it takes the long one
        ld a,(V_LIM)
        or a
        jr z,.skip
        ld c,a
        inc hl
        ld a,(hl)
        dec hl
        cp (ACOPY + 448) >> 8
        jr nc,.skip
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        and 7
        cp c
        jr nc,.skip
        ld a,(V_RADD)
        add a,2
        ld (V_RADD),a
.skip:  inc hl
        inc hl
        inc hl
        inc e
        djnz .again
        xor a
        ld (V_PN),a
        ld hl,PREC
        ld (V_PP),hl
        ; the two cells the random byte can read: what the build shows, what the original shows
        ld a,(0x5959)
        ld (SA_B),a
        ld (SA_O),a
        ld c,a
        ld a,(0x5A5A)
        ld (SA_B + 1),a
        ld (SA_O + 1),a
        ld b,a
        ld a,(V_VAR)
        cp 3
        jr z,.sh                ; one colour everywhere: the same in both
        ld e,0x47               ; what the paint makes of a cell: bright white ink, or bright with the limit's ink
        ld a,(V_LIM)
        or a
        jr z,.pl
        or 0x40
        ld e,a
.pl:    ld a,(V_CF + 1)
        or a
        jr z,.s0
        ld a,b
        call .of
        ld (SA_O + 1),a
.s0:    ld a,(V_CF)
        or a
        jr z,.sh
        ld a,c
        call .of
        ld (SA_O),a
        jr .sh
.of:    and 0x78                ; the cell's paper, flash off, with the paint's ink and bright
        or e
        ret
.sh:    ld hl,D_ACOPY
        call hlib_debt_add
        ld a,R_A1
        call hlib_r_set
        ld a,(V_RADD)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        pop af
        HLIB_SPEED_OUT V_SPEED
        jp x_ret
R_A0    EQU 114
R_ACALL EQU 118                 ; -10
R_A1    EQU 119

; The whole screen cleared (0x5E5E: the game leaves the play picture): every sprite off. Hooked at its second
; instruction: the random byte can read address 0x5E5E itself.
cls:    ld a,r
        ld (HLIB_V_R),a
        push bc
        ld bc,0x303B
        xor a
        out (c),a
        ld bc,NSPR * 4 * 256 + 0x57
.l:     out (c),a
        djnz .l
        ld (V_PREV),a
        pop bc
        ld a,R_CLS
        call hlib_r_set
        pop af
        push hl
        ld hl,0x5E64
        ex (sp),hl
        ld de,0x4001
        jp x_ret
R_CLS   EQU 114

; The random byte: A = R XOR the last one, then the byte at address A * 257.
random: ld a,r
        ld l,a
        sub RND_E               ; the value the original's LD A,R reads
        xor l
        and 0x7F
        xor l
        ld h,a
        add a,RND_X             ; R to leave
        xor l
        and 0x7F
        xor l
        ld (HLIB_V_R + 1),a
        ld a,(0xBBF7)           ; the XOR's operand: the game stores the last byte there
        xor h
        ld h,a
        ld l,a
        cp 0x59
        jr z,.c0
        cp 0x5A
        jr nz,.plain
        ld a,(SA_B + 1)
        cp (hl)
        jr nz,.plain            ; written since the attribute copy: the same in both
        ld a,(SA_O + 1)
        jr .val
.c0:    ld a,(SA_B)
        cp (hl)
.n_rnd: jr nz,.plain
        ld a,(SA_O)
        jr .val
.val:   ld (V_VAL),a
        ld a,h
        or a                    ; the flags the XOR left
        inc sp
        inc sp
        jp x_rndv
.plain: ld a,h
        or a
        inc sp
        inc sp
        jp x_rndp
RND_E   EQU 7
RND_X   EQU 126

; The coverage follows the game's foreground list: made again only when the list changes.
cover:  ld hl,FGLIST
        ld a,(hl)
        cp FGMAX + 1
        jr nc,.make             ; too long to keep: every copy
        add a,a
        add a,a
        inc a
        ld b,a
        ld de,FGC
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.make
        inc hl
        inc de
        djnz .cmp
        ret
.make:  ld hl,FGLIST
        ld a,(hl)
        cp FGMAX + 1
        jr c,.keep
        ld a,0xFF
        ld (FGC),a              ; never equal: made again next time
        jr .clr
.keep:  add a,a
        add a,a
        inc a
        ld c,a
        ld b,0
        ld de,FGC
        ldir
.clr:   ld hl,COV
        ld de,COV + 1
        ld bc,COV_END * 256 - COV - 1
        ld (hl),0
        ldir
        ld ix,FGLIST
        ld a,(ix+0)
        or a
        ret z
        ld b,a
        inc ix
.piece: push bc
        ld l,(ix+0)
        ld a,(ix+1)
        sub 0x40
        ld h,a                  ; HL = coverage byte
        ld e,(ix+2)
        ld d,(ix+3)             ; the piece: +1 bytes wide, +2 lines, +3 data, +256 mask
        push de
        exx
        pop hl
        inc h                   ; HL' = mask
        exx
        inc de
        ld a,(de)
        ld b,a
        inc de
        ld a,(de)
        ld c,a
        inc de                  ; DE = data, B = width, C = lines
.line:  push bc
        ld a,h
        cp 0x80
        jr c,.skip
        cp COV_END
        jr nc,.skip
.byte:  exx
        ld a,(hl)
        inc hl
        exx
        cpl
        ex de,hl
        or (hl)
        ex de,hl
        or (hl)
        ld (hl),a
        inc l
        inc de
        djnz .byte
        jr .next
.skip:  exx
        inc hl
        exx
        inc l
        inc de
        djnz .skip
.next:  pop bc
        ld a,l
        sub b
        add a,32
        ld l,a
        jr nc,.nc
        inc h
.nc:    dec c
        jr nz,.line
        ld de,4
        add ix,de
        pop bc
        djnz .piece
        ret

; The noted figures -> patterns in the set not shown, their attributes listed.
build:
        ld a,(V_SET)
        xor 64
        ld (V_SET),a
        ld (V_Q),a
        srl a
        ld bc,0x303B
        out (c),a               ; pattern uploads start at this slot
        ld hl,ATTRS
        ld (V_ATP),hl
        ld de,ATTRS + 1
        ld bc,NSPR * 5 - 1
        ld (hl),0
        ldir
        ld a,(V_N)
        or a
        jr z,.show
        ld b,a
        ld hl,ENTS
.fig:   push bc
        push hl
        call figure
        pop hl
        ld a,l
        add a,8
        ld l,a
        pop bc
        djnz .fig
.show:  ret

; The sprite window is the lines this copy showed; then every attribute in one run.
show:   nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,48
        ld a,(V_LNS)
        rra
.n_win: ld a,48 + 111
        jr nc,.w
        ld a,48 + 143
.w:     nextreg 0x19,a
        ld bc,0x303B            ; sprite 0 for the attribute port (NextReg 0x34 does not move the port's index)
        xor a
.n_sel: out (c),a
        ld hl,ATTRS
        ld bc,(NSPR * 5) * 256 + 0x57
        otir
        ld hl,(V_ATP)
        ld de,0 - ATTRS
        add hl,de
        ld a,l
        ld (V_PREV),a           ; bytes of attributes in use: zero = none shown
        xor a
        ld (V_N),a
        ld hl,STASH
        ld (V_STP),hl
        ret

; HL = the figure's entry.
figure: ld e,(hl)
        inc l
        ld d,(hl)
        inc l
        ld (V_BUF),de
        ld c,(hl)
        inc l
        ld b,(hl)
        inc l
        push bc
        pop ix                  ; IX = graphic
        ld c,(hl)
        inc l
        ld b,(hl)
        inc l
        ld a,(hl)
        ld (V_KIND),a
        push bc                 ; the mask
        ; position: x = 32 + column * 8, y = 32 + 48 + line
        ld a,e
        and 31
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,32
        add hl,bc
        ld (V_X),hl
        ld a,d
        and 0x3F
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,e
        rlca
        rlca
        rlca
        and 7
        or b
.n_y:   add a,80
        ld (V_Y),a
        ld a,d
        sub 0x40
        ld d,a                  ; DE = coverage
        ld a,(V_KIND)
        cp 1
        jr nz,.fwd
        ld a,e
        add a,3
        ld e,a                  ; mirrored: from the fourth byte, backwards, as the plotter
.fwd:   push de
        exx
        pop de
        pop hl                  ; HL' = mask, DE' = coverage
        exx
        ld hl,PBUF
        ld (V_DEST),hl
        ld a,(V_KIND)
        cp 2
        ld a,34
        jr nz,.r
        ld a,16
.r:     ld (V_ROWS),a
.row:   exx
        push de
        ld a,d
        cp 0x80
        jr c,.off
        cp COV_END
        jr c,.on
.off:   ld de,Z8 + 3
.on:    exx
        ld de,(V_DEST)
        ld a,(V_KIND)
        or a
        jr z,.n4
        dec a
        jr z,.m4
        call cell_n
        call cell_n
        ld a,e
        add a,120
        ld e,a
        call cell_n
        ld bc,0x00FF
        call emit
        jr .end
.n4:    call cell_n
        call cell_n
        ld a,e
        add a,120
        ld e,a
        call cell_n
        call cell_n
        jr .end
.m4:    ld a,e
        add a,132
        ld e,a
        call cell_m
        ld a,e
        sub 8
        ld e,a
        call cell_m
        ld a,e
        sub 128
        ld e,a
        call cell_m
        ld a,e
        sub 8
        ld e,a
        call cell_m
.end:   exx
        pop de
        ld a,e
        add a,32
        ld e,a
        jr nc,.nc
        inc d
.nc:    exx
        ld hl,(V_DEST)
        ld a,l
        add a,8
        ld l,a
        jp p,.same
        ld l,0
        inc h
.same:  ld (V_DEST),hl
        ld hl,V_ROWS
        dec (hl)
        jr nz,.row
        ; upload and attributes
        ld a,(V_KIND)
        cp 2
        ld a,3
        jr nz,.u
        ld a,1
.u:     ld hl,PBUF
.blk:   push af
        ld bc,0x005B
        otir
        push hl
        ld hl,(V_X)
        call attr
        ld hl,(V_X)
        ld bc,16
        add hl,bc
        call attr
        ld a,(V_Y)
        add a,16
        ld (V_Y),a
        pop hl
        pop af
        dec a
        jr nz,.blk
        ret

; One sprite: HL = x (9 bits), V_Y, the next pattern number.
attr:   ex de,hl
        ld hl,(V_ATP)
        ld (hl),e
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,d
        and 1
        ld (hl),a
        inc hl
        ld a,(V_Q)
        ld e,a
        srl a
.n_q:   or 0xC0
        ld (hl),a
        inc hl
        ld a,e
        rrca
        rrca
        and 0x40
        or 0x80
        ld (hl),a
        inc hl
        ld (V_ATP),hl
        ld a,e
        inc a
        ld (V_Q),a
        ret

; One byte of the figure: graphic at IX, mask at HL', coverage at DE'; 4 pattern bytes at DE.
cell_n: ld b,(ix+0)
        inc ix
        exx
        ld a,(de)
        ld c,a
        inc e
        ld a,(hl)
        inc hl
        or c
        ex af,af'
        ld a,c
        cpl
        exx
        and b
        ld b,a
        ex af,af'
        ld c,a
        jr emit
cell_m: ld l,(ix+0)
        inc ix
        ld h,REV
        ld b,(hl)
        exx
        ld a,(de)
        ld c,a
        dec e
        ld a,(hl)
        inc hl
        exx
        ld l,a
        ld a,(hl)
        exx
        or c
        ex af,af'
        ld a,c
        cpl
        exx
        and b
        ld b,a
        ex af,af'
        ld c,a
; B = graphic, C = mask -> 4 bytes at DE (E moves on by 4).
emit:   ld a,c
        swapnib
        xor b
        and 0x0F
        xor b
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        ld (de),a
        inc e
        inc h
        ld a,(hl)
        ld (de),a
        inc e
        ld a,b
        swapnib
        xor c
        and 0xF0
        xor c
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        ld (de),a
        inc e
        inc h
        ld a,(hl)
        ld (de),a
        inc e
        ret
CODE_END:
        ASSERT CODE_END <= 0x3800
        SAVEBIN "heartland_code.bin",0x2000,CODE_END-0x2000

        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,1
        ld hl,.pal
        ld b,15
.pl:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pl
        nextreg 0x4B,0          ; index 0 clear
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,48
        nextreg 0x19,191
        nextreg 0x15,0x01       ; sprites on, S L U
        ret
; 1 ink (bright white), 2 the mask's border (black); 3-15 for a painted sheet, the Spectrum's other colours.
.pal:   DB 0xFF,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
SETUP_END:
        SAVEBIN "heartland_setup.bin",0xD000,SETUP_END-0xD000
