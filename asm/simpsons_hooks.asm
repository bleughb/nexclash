; The Simpsons: Bart vs. the Space Mutants (Ocean, 1991, 128K): the figures as hardware sprites.
; Facts and design: games/simpsons.md.
;
; The whole game runs in its interrupt handler, 50 times a second, on two screens it flips every frame. Each
; figure is drawn by one routine (IX = the object): a pre-shifted shape of (mask, graphic) byte pairs, saved
; and then (screen AND mask) OR graphic, 1 to 4 bytes wide, mirrored through a bit-reverse table. A figure's
; pixels take the cell's ink and paper. The build keeps every byte of the game's memory and of both screens:
;   e_all    the routine that draws every object: 28 MHz, the game's own routine, then the rest of its own time
;            waited out;
;   e_shape  where the routine takes the shape's address and size: both noted (the colour keys);
;   e_note   where the routine has clipped the figure and picks its width loop: the figure's patterns go
;            straight to the pattern port (4 bit: 1 the graphic's pixels, 2 the mask's cleared pixels, 0 clear;
;            Enhanced: the painted colours of that shape, found by three keys of its bytes), its sprites listed;
;   e_flip   the screen flip: every listed sprite's attributes in one run, the pattern sets change over.
; Code and tables sit in the alt ROM (both images) from 0x2000; the state page is at slot 0 inside a hook, a
; colour page at slot 2 while its bytes are sent. Interrupts are off wherever the game draws (its handler).
; The addresses of one level's routines are written into the fx_ operands by the build (nexclash/simpsons.py).
        DEVICE ZXSPECTRUMNEXT
WORK    EQU 26                  ; the state page (slot 0 inside a hook; the ROM back at the exit)
V_SPEED EQU 0x0100
HLIB_V_R EQU 0x0101             ; 3 bytes: e_fig and e_flip
V_RN    EQU 0x0104              ; R at e_note's entry
V_RS    EQU 0x0105              ; R at e_shape's entry
V_N     EQU 0x0106              ; sprites listed since the last flip
V_PREV  EQU 0x0107              ; sprites the last flip showed
V_SET   EQU 0x0108              ; the pattern set being filled: 0 or 64 (4-bit pattern numbers)
V_Q     EQU 0x0109              ; next 4-bit pattern number
V_ATP   EQU 0x010A              ; word: next attribute record
V_SHAPE EQU 0x010C              ; word: the shape's first byte
V_SIZE  EQU 0x010E              ; lines * 4 + width code
V_IN    EQU 0x010F              ; inside the draw pass
V_ACC   EQU 0x0110              ; word: the pass's own time so far, 1/16 lines
V_SP    EQU 0x0112              ; word: the routine's data pointer at e_note
V_FSP   EQU 0x0114              ; word: the game's stack inside e_all / e_flip
V_RET   EQU 0x0132              ; word: the draw pass's caller
V_ROWP  EQU 0x0134              ; a painted figure's rows: none past the shape's last line
V_CODE  EQU 0x0116              ; width code 0-7
V_WB    EQU 0x0117              ; bytes a row
V_ROWS  EQU 0x0118              ; rows drawn
V_Y     EQU 0x0119              ; sprite y of the first row
V_X     EQU 0x011A              ; word: sprite x of the first column
V_STEP  EQU 0x011C              ; shape bytes a row
V_OFF0  EQU 0x011D              ; offset in a row of the pair for the pattern's left byte
V_OFF1  EQU 0x011E              ; and its right byte, 0xFF = none
V_MIR   EQU 0x011F              ; the figure is mirrored
V_COLS  EQU 0x0120              ; patterns across
V_C     EQU 0x0121              ; column being sent
V_LEFT  EQU 0x0122              ; rows left from the block being sent
V_BLK   EQU 0x0123              ; word: the block's first row (shape bytes, or a strip's)
V_LINE  EQU 0x0125              ; palette line << 4
V_K     EQU 0x0126              ; 3 bytes: the shape's keys
V_SKIP  EQU 0x0129              ; rows clipped off the top
V_STR   EQU 0x012A              ; word: the strip of column 0
V_STRW  EQU 0x012C              ; word: bytes a strip (lines * 8)
V_PG    EQU 0x012E              ; the strips' page
V_YB    EQU 0x012F              ; sprite y of the block being sent
V_XC    EQU 0x0130              ; word: sprite x of the column being sent
HLIB_V_PACE EQU 0x0140          ; 26 bytes
HLIB_PACE_NL EQU 311
HSTK    EQU 0x0300              ; the hooks' stack, below this
ATTRS   EQU 0x0300              ; NSPR sprites of 5 bytes
NSPR    EQU 60
TLO     EQU 0x0500              ; (graphic nibble << 4 | mask nibble) -> the first two pixels
THI     EQU 0x0600              ;                                       the last two
REVT    EQU 0x0700              ; a byte's bits reversed
CPAGE   EQU 28                  ; the first colour page: the index (0x4000: 256 chain heads by key 0, then the entries)
SPORT   EQU 0x5B                ; pattern data port

        ORG 0x2000
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_LEAN
        DEFINE HLIB_PACE_CAP 0x0200
        INCLUDE "lib/hlib_pace.asm"

; ---------------------------------------------------------------- the routine that draws every object (LD HL,(nn))
; 28 MHz for the whole pass; its return goes through this hook, which waits out the pass's own time: the loop's,
; plus what e_shape and e_note added for each figure.
e_all:  push af
        ld a,r
        nextreg 0x50,WORK
        ld (HLIB_V_R),a
        pop af
        pop hl                  ; (HL is dead: the routine loads it first) the caller's return
        ld (V_RET),hl
        ld hl,all_end
        push hl
        ld (V_FSP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPEED
        push af
        push bc
        push de
        ld hl,(T_LOOP)
        ld (V_ACC),hl
        ld a,1
        ld (V_IN),a
        call hlib_pace_open
        ld a,R_A0
        call hlib_r_set
        pop de
        pop bc
        pop af
        ld sp,(V_FSP)
        HLIB_R_OUT
        nextreg 0x50,255
fx_ahl: ld hl,(0)               ; the replaced instruction
fx_ajp: jp 0                    ; the routine's second
all_end:
        nextreg 0x50,WORK
        ld (V_FSP),sp
        ld sp,HSTK
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        xor a
        ld (V_IN),a
        ld hl,D_PASS            ; this hook's own entry and exit, outside the window
        call hlib_debt_add
        ld hl,(V_ACC)
        HLIB_SPEED_OUT V_SPEED
        ld a,(V_SPEED)
.n_wait: call hlib_pace_wait
        ld a,R_A1
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_FSP)
        push hl
        ld hl,(V_RET)
        ex (sp),hl              ; the caller's return back where the original has it
        HLIB_R_OUT
        nextreg 0x50,255
        ret
D_PASS  EQU 118                 ; 1/16 lines: calibrated so the passes take the original's time (games/simpsons.md)
D_FLIP  EQU 24
R_A0    EQU 120                 ; -8
R_A1    EQU 116                 ; -12

; ---------------------------------------------------------------- POP HL / POP DE / LD SP,HL: the shape and its size
; No stack here (SP is the routine's data pointer). A and B are dead; C is not.
e_shape: nextreg 0x50,WORK
        ld a,r
        ld (V_RS),a
        pop hl
        pop de
        ld (V_SHAPE),hl
        ld a,e
        ld (V_SIZE),a
        ld sp,hl
        ld a,(T_OFF)            ; a draw's time when it draws nothing; e_note adds the rest
        ld b,a
        ld a,(V_ACC)
        add a,b
        ld (V_ACC),a
        ld a,(T_OFF + 1)
        ld b,a
        ld a,(V_ACC + 1)
        adc a,b
        ld (V_ACC + 1),a
        ld a,(V_RS)
        ld b,a
        add a,R_S
        xor b
        and 0x7F
        xor b
        ld r,a
        nextreg 0x50,255
fx_sret: jp 0
R_S     EQU 123                 ; -5

; ---------------------------------------------------------------- LD (nn),HL: the figure is clipped and will be drawn
; HL = the width loop, DE = the first row's entry in the row table, B = rows, C = x (low byte), SP = the shape's
; bytes from the first row drawn, IX = the object. A, AF', DE', HL' are dead; BC' is the routine's save pointer.
e_note: nextreg 0x50,WORK
        ld a,r
        ld (V_RN),a
fx_nop: ld (0),hl
        ld (V_SP),sp
        ld sp,HSTK
        push bc
        push de
        push hl
        push ix
        push iy
        exx
        push bc
        exx
        call noted
        ld a,(V_RN)
        ld c,a
.n_r:   add a,R_N
        xor c
        and 0x7F
        xor c
        ld r,a
        exx
        pop bc
        exx
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        ld sp,(V_SP)
        nextreg 0x50,255
fx_nret: jp 0
R_N     EQU 109                 ; -19

; ---------------------------------------------------------------- LD (nn),A: the screens change over
e_flip: nextreg 0x50,WORK
fx_pop: ld (0),a
        ld (V_FSP),sp
        ld sp,HSTK
        push af
        ld a,r
        ld (HLIB_V_R),a
        HLIB_SPEED_IN V_SPEED
        push bc
        push de
        push hl
        call hlib_debt_open
        call show
        ld a,D_FLIP
        call hlib_debt_close
        HLIB_SPEED_OUT V_SPEED
        ld a,R_P
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_FSP)
        HLIB_R_OUT
        nextreg 0x50,255
fx_pret: jp 0
R_P     EQU 115                 ; -13

; Every listed sprite's attributes in one run, the sprites the last flip showed beyond them off, then the
; other pattern set for the next frame's figures.
show:   ld bc,0x303B
        xor a
.n_sel: out (c),a               ; sprite 0 for the attribute port
        ld hl,ATTRS
        ld a,(V_N)
        ld e,a
        or a
        jr z,.hide
        ld d,a
        ld c,0x57
.s:     ld b,5
        otir
        dec d
        jr nz,.s
.hide:  ld a,(V_PREV)
        sub e
        jr c,.done
        jr z,.done
        ld d,a
        xor a
.h:     out (0x57),a
        out (0x57),a
        out (0x57),a
.n_off: out (0x57),a
        out (0x57),a
        dec d
        jr nz,.h
.done:  ld a,e
        ld (V_PREV),a
        xor a
        ld (V_N),a
        ld hl,ATTRS
        ld (V_ATP),hl
        ld a,(V_SET)
.n_set: xor 64
        ld (V_SET),a
        ld (V_Q),a
        srl a
        ld bc,0x303B
        out (c),a               ; pattern uploads go on from this slot
        ret

; The figure e_note was given: B = rows, C = x, DE = the row table entry, IX = the object.
noted:  ld a,b
        ld (V_ROWS),a
        ld a,(ix+0)
        and 7
        ld (V_CODE),a
.n_mir: cp 5
        ld a,0
        jr c,.nm
        inc a
.nm:    ld (V_MIR),a
        ld a,(V_CODE)
        and 3
        inc a
        ld (V_WB),a
        add a,a
        ld (V_STEP),a
        ; this draw's own time beyond a draw of nothing: by width and rows, by the object's pre-shift kind, clipped
        ld a,(V_CODE)
        ld h,a
        ld l,0
        srl h
        rr l
        ld a,b
        add a,a
        or l
        ld l,a
        push de
        ld de,TT
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(V_ACC)
        add hl,de
        ld a,(ix+1)
        and 7
        add a,KT & 255
        ld e,a
        ld d,KT >> 8
        ld a,(de)
        ld e,a
        ld d,0
        add hl,de
        push hl
        ld hl,(V_SP)            ; clipped at the top: the data pointer is past the shape's first row
        ld de,(V_SHAPE)
        or a
        sbc hl,de
        ld a,h
        or l
        pop hl
        jr z,.nt
        ld a,(T_TOP)
        ld e,a
        ld d,0
        add hl,de
        jr .tb
.nt:    ld a,(V_SIZE)           ; clipped at the bottom: fewer rows than the shape has
        srl a
        srl a
        cp b
        jr z,.tb
        ld a,(T_BOT)
        ld e,a
        ld d,0
        add hl,de
.tb:    ld (V_ACC),hl
        pop hl                  ; the row table entry
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the first row's screen address
        ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        ld h,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or h
        ld h,a
        ld a,d
        and 7
        or h
n_y:    add a,32
        ld (V_Y),a
        ld a,c
        rrca
        rrca
        rrca
        and 31
        ld l,a
        ld a,e
        and 31
        add a,l
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_X),hl
        xor a
        ld (V_LINE),a
        ld a,(V_WB)
        inc a
        srl a
        ld (V_COLS),a
        ld a,(ENH)
        or a
        jr z,plainfig
        call key
        call find
        jp nc,painted
.plain:
plainfig:
        call room
        ret c
        xor a
.col:   ld (V_C),a
        ; the pairs for this column's two bytes
        ld c,a
        add a,a
        ld b,a                  ; 2c: the left byte's number
        ld a,(V_MIR)
        or a
        jr nz,.mo
        ld a,b
        add a,a
        ld (V_OFF0),a           ; 4c
        add a,2
        ld d,a
        ld a,b
        inc a
        jr .o1
.mo:    ld a,(V_WB)
        dec a
        sub b
        add a,a
        ld (V_OFF0),a           ; 2 (wb - 1 - 2c)
        sub 2
        ld d,a
        ld a,b
        inc a
.o1:    ld hl,V_WB              ; the right byte is byte 2c + 1, when the figure is that wide
        cp (hl)
        jr c,.has
        ld d,0xFF
.has:   ld a,d
        ld (V_OFF1),a
        ld hl,(V_X)
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
        add a,l
        ld l,a
        jr nc,.x
        inc h
.x:     ld (V_XC),hl
        ld hl,(V_SP)
        ld (V_BLK),hl
        ld a,(V_ROWS)
        ld (V_LEFT),a
        ld a,(V_Y)
        ld (V_YB),a
.blk:   call attr
        ld hl,(V_BLK)
        ld a,(V_LEFT)
        ld c,a
        call pat
        ld (V_BLK),hl
        ld a,c
        ld (V_LEFT),a
        or a
        jr z,.nc
        ld a,(V_YB)
        add a,16
        ld (V_YB),a
        jr .blk
.nc:    ld a,(V_COLS)
        ld c,a
        ld a,(V_C)
        inc a
        cp c
        jr c,.col
        ret

; Carry when the figure's sprites or patterns do not fit: it is not listed.
room:   ld a,(V_ROWS)
        add a,15
        rrca
        rrca
        rrca
        rrca
        and 15                  ; blocks down
        ld e,a
        ld a,(V_COLS)
        ld d,a
        mul d,e                 ; E = sprites
        ld a,(V_N)
        add a,e
        cp NSPR + 1
        ccf
        ret c
        ld a,(V_SET)
        add a,64
        ld d,a
        ld a,(V_Q)
        add a,e
        cp d
        jr z,.ok
        ccf
        ret
.ok:    or a
        ret

; One sprite's attributes: pattern V_Q at V_XC, V_YB, palette line V_LINE. V_Q, V_N move on.
attr:   ld hl,(V_ATP)
        ld de,(V_XC)
        ld (hl),e
        inc hl
        ld a,(V_YB)
        ld (hl),a
        inc hl
        ld a,(V_LINE)
        or d
        ld (hl),a
        inc hl
        ld a,(V_Q)
        ld e,a
        srl a
        or 0xC0
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
        ld hl,V_N
        inc (hl)
        ret

; One pattern (128 bytes) to the port: HL = the shape's bytes of its first row, C = rows left from there.
; -> HL the row after the pattern's last, C the rows left.
pat:    ld b,16
.row:   ld a,c
        or a
        jr z,.zero
        dec c
        push bc
        push hl
        ld a,(V_OFF0)
        call pxpair
        pop hl
        push hl
        ld a,(V_OFF1)
        cp 0xFF
        jr z,.half
        call pxpair
        jr .nx
.half:  xor a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
.nx:    pop hl
        pop bc
        ld a,(V_STEP)
        add a,l
        ld l,a
        jr nc,.n1
        inc h
.n1:    djnz .row
        ret
.zero:  xor a
.z:     out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        out (SPORT),a
        djnz .z
        ret

; The (mask, graphic) pair at HL + A -> 4 pattern bytes.
pxpair: add a,l
        ld l,a
        jr nc,.p
        inc h
.p:     ld d,(hl)
        inc hl
        ld e,(hl)               ; D = mask, E = graphic
        ld a,(V_MIR)
        or a
        jr z,.e
        ld h,REVT >> 8
        ld l,d
        ld d,(hl)
        ld l,e
        ld e,(hl)
.e:     ld a,d
        swapnib
        xor e
        and 0x0F
        xor e
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        out (SPORT),a
        inc h
        ld a,(hl)
        out (SPORT),a
        ld a,e
        swapnib
        xor d
.n_lo:  and 0xF0
        xor d
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        out (SPORT),a
        inc h
        ld a,(hl)
        out (SPORT),a
        ret

; ---------------------------------------------------------------- Enhanced: the shape's painted colours
; The shape's keys over all its bytes (V_SHAPE, V_SIZE): the sum, and a 16-bit hash (hash * 3 + byte + 1).
key:    ld a,(V_SIZE)
        ld e,a
        and 3
        inc a
        add a,a
        ld d,a                  ; bytes a row
        ld a,e
        srl a
        srl a
        ld e,a                  ; lines
        mul d,e                 ; DE = bytes
        ld b,d
        ld c,e
        ld hl,(V_SHAPE)
        ld d,0                  ; D = the sum
        exx
        ld hl,0                 ; HL' = the hash: hash * 3 + byte + 1
        exx
.k:     ld a,(hl)
        inc hl
        ld e,a
        add a,d
        ld d,a
        ld a,e
        exx
        ld d,h
        ld e,l
        add hl,hl
.n_h:   add hl,de
        ld e,a
        ld d,0
        add hl,de
        inc hl
        exx
        dec bc
        ld a,b
        or c
        jr nz,.k
        ld a,d
        ld (V_K),a
        exx
        ld (V_K + 1),hl
        exx
        ret

; The entry for the keys and the size -> HL = its bytes after them, no carry; carry when the shape is not painted.
; An entry: the next of its chain (a word, 0 = the last), keys 1 and 2, the size, then what `painted` reads.
; The index page stays at slot 2 until the caller takes it away.
find:   nextreg 0x52,CPAGE
        ld a,(V_K)
        ld l,a
        ld h,0
        add hl,hl
        ld de,0x4000
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
.f:     ld a,h
        or l
        jr z,.none
        ld e,(hl)
        inc hl
        ld d,(hl)               ; the next entry of the chain
        inc hl
        ld a,(V_K + 1)
        cp (hl)
        jr nz,.nx
        inc hl
        ld a,(V_K + 2)
.n_k2:  cp (hl)
        jr nz,.nx
        inc hl
        ld a,(V_SIZE)
        cp (hl)
        jr nz,.nx
        inc hl
        or a
        ret
.nx:    ex de,hl
        jr .f
.none:  nextreg 0x52,10
        scf
        ret

; A painted shape. Entry: palette line << 4, then for the figure as stored and for it mirrored: patterns across,
; x offset, the strips' page, address. A strip = the column's 8 bytes a line, for every line of the shape.
painted:
        push hl
        ; rows clipped off the top: (data pointer - shape) / bytes a row. The game's own clip steps 6 bytes a row
        ; whatever the width, so a clipped figure that is not 3 bytes wide is drawn from the middle of its rows:
        ; that one is left unpainted (the pattern from the bytes the game draws).
        ld hl,(V_SP)
        ld de,(V_SHAPE)
        or a
        sbc hl,de
        ld a,(V_STEP)
        ld e,a
        ld d,0
        ld b,0xFF
.dv:    inc b
        or a
        sbc hl,de
        jr nc,.dv
        add hl,de
        ld a,h
        or l
        ld a,b
        ld (V_SKIP),a
        pop hl
        jr z,.al
.n_al:  nextreg 0x52,10
        jp plainfig
.al:    ld a,(hl)
        ld (V_LINE),a
        inc hl
        ld a,(V_MIR)
        or a
        jr z,.o
        ld de,5
.n_m:   add hl,de
.o:     ld a,(hl)
        ld (V_COLS),a
        inc hl
        ld e,(hl)               ; x offset
        inc hl
        ld a,(hl)
        ld (V_PG),a
        inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_STR),hl
        nextreg 0x52,10
        ld hl,(V_X)
        ld d,0
        add hl,de
        ld (V_X),hl
        call room
        ret c
        ld a,(V_SIZE)
        srl a
        srl a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld (V_STRW),hl          ; bytes a strip
        ld a,(V_SIZE)           ; clipped at the top the game draws on past the shape's last line (the next shape's
        srl a                   ; bytes): those rows stay its own drawing on the screen, no sprite lies on them
        srl a
        ld hl,V_SKIP
        sub (hl)
        ret c                   ; every row is past the shape: nothing of it is painted
        ret z
        ld c,a
        ld a,(V_ROWS)
        cp c
        jr c,.rw
.n_rw:  ld a,c
.rw:    ld (V_ROWP),a
        ld a,(V_PG)
        nextreg 0x52,a
        xor a
.col:   ld (V_C),a
        ld c,a
        ld hl,(V_X)
        add a,a
        add a,a
        add a,a
        add a,a
        add a,l
        ld l,a
        jr nc,.x
        inc h
.x:     ld (V_XC),hl
        ld hl,(V_STR)
        ld a,c
        or a
        jr z,.s0
        ld de,(V_STRW)
.sm:    add hl,de
        dec a
        jr nz,.sm
.s0:    ld a,(V_SKIP)
        ld e,a
        ld d,8
        mul d,e
        add hl,de
        ld (V_BLK),hl
        ld a,(V_ROWP)
        ld (V_LEFT),a
        ld a,(V_Y)
        ld (V_YB),a
.blk:   call attr
        ld hl,(V_BLK)
        ld a,(V_LEFT)
        cp 16
        jr c,.part
        sub 16
        ld (V_LEFT),a
        ld bc,128 * 256 + SPORT
        otir
        jr .next
.part:  ld e,a                  ; rows in this last block
        add a,a
        add a,a
        add a,a
        ld b,a
        ld c,SPORT
        otir
        ld a,16
        sub e
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
        ld (V_LEFT),a
.pz:    out (SPORT),a
        djnz .pz
.next:  ld (V_BLK),hl
        ld a,(V_LEFT)
        or a
        jr z,.nc
        ld a,(V_YB)
        add a,16
        ld (V_YB),a
        jr .blk
.nc:    ld a,(V_COLS)
        ld c,a
        ld a,(V_C)
        inc a
        cp c
        jp c,.col
        nextreg 0x52,10
        ret

CODE_END:
        ASSERT CODE_END <= 0x2C00
; ---------------------------------------------------------------- tables the build fills in
        ORG 0x2C00
ENH:    DB 0                    ; 1: the painted build
        DB 0
T_OFF:  DW 0                    ; the draw routine's time when it draws nothing, 1/16 lines
T_LOOP: DW 0                    ; the pass's own time around the draws
T_TOP:  DB 0                    ; more when the figure is clipped at the top
T_BOT:  DB 0                    ; at the bottom
        ALIGN 8
KT:     DS 8                    ; more by the object's pre-shift kind
        ORG 0x2D00
TT:     DS 1024                 ; a draw's time by width code (128 bytes each) and rows (a word), 1/16 lines
ROM_END:
        SAVEBIN "simpsons_rom.bin",0x2000,ROM_END-0x2000

        ORG 0xD000
setup:  ld hl,pbuf              ; the game keeps data from 0x5B00: NEXLOAD wrote over the printer buffer
        ld de,0x5B00
        ld bc,256
        ldir
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal9
        ld b,0
.pl:    ld a,(hl)
        nextreg 0x44,a          ; 9 bits a colour: RRRGGGBB, then the last blue bit
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        nextreg 0x4B,0          ; index 0 clear
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        ld bc,0x303B
        xor a
        out (c),a               ; pattern uploads start at slot 0
        nextreg 0x15,0x01       ; sprites on, S L U
        ret
; 16 lines of 16: line 0 = 1 the graphic's pixels (black), 2 the mask's cleared pixels (white); the build fills
; in the painted lines.
pal9:   DS 512
pbuf:   DS 256                  ; the snapshot's 0x5B00-0x5BFF (the build fills it in)
SETUP_END:
        SAVEBIN "simpsons_setup.bin",0xD000,SETUP_END-0xD000

; The plain build's setup: only the printer buffer.
        ORG 0xD000
psetup: ld hl,ppbuf
        ld de,0x5B00
        ld bc,256
        ldir
        ret
ppbuf:  DS 256
PSETUP_END:
        SAVEBIN "simpsons_plain.bin",0xD000,PSETUP_END-0xD000
