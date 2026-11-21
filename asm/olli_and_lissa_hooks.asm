; Olli and Lissa: The Ghost of Shilmoore Castle (Firebird, 1986; 48K code in a 128K snapshot): the moving figures as
; hardware sprites. Facts and design: games/olli_and_lissa.md.
;
; The game plays with interrupts off and draws every moving figure straight to the screen with one routine (0x89DA:
; HL = a pair of pointers, graphic and mask; B = y, C = x; D = rows, E = bytes a row): the clean room from its copy
; at 0xE000, AND the mask, OR the graphic. The mask is one pixel larger than the graphic on every side. Nothing of
; the game changes:
;   e_olli / e_caul / e_obj / e_big   the five CALLs of that routine (two are Olli's): 28 MHz; the figure's sprites (4-bit
;                       patterns: 1 where the graphic is set, 2 where the mask clears, or its painted tiles) go into
;                       free patterns, then the attributes of the figure's own sprites; the game's routine; the
;                       rest of its own time waited out on the video line.
;   e_room / e_wipe     the five CALLs of the screen wipe (a new room, a scene): every sprite off, the figures
;                       forgotten. Interrupts are on at the title's: off inside the hook, on again after it.
;   under               Olli caught: the game plays a scene over him and draws nothing else until its wipe; the
;                       figures under the scene go back to the game's own drawing.
; Code in the alt ROM from 0x2800 (the game runs no ROM code and reads one ROM byte, 0x0BEA); inside a hook the
; state page is at slot 0 and, while painted tiles are sent, their page at slot 2.
        DEVICE ZXSPECTRUMNEXT
WORK    EQU 26                  ; the state page
FIG     EQU 0x89DA              ; the game's figure routine
WIPE    EQU 0x82EB              ; its screen wipe
V_SPEED EQU 0x0100
HLIB_V_R EQU 0x0101             ; 3 bytes
V_SP    EQU 0x0104              ; word: the game's stack inside a hook
V_RET   EQU 0x0106              ; word: the game's return address
V_KIND  EQU 0x0108              ; which CALL: 0 an object (its key is IY), 1 Olli, 2 the steam, 3 Sir Humphrey
V_HL    EQU 0x010A              ; word: the routine's arguments
V_BC    EQU 0x010C
V_DE    EQU 0x010E
V_KEY   EQU 0x0110              ; word
V_T     EQU 0x0112              ; word: the routine's own time, 1/16 lines
V_NB    EQU 0x0114
V_ROWS  EQU 0x0115
V_TX    EQU 0x0116              ; sprites across
V_TY    EQU 0x0117              ; sprites down
V_G     EQU 0x0118              ; word: graphic
V_M     EQU 0x011A              ; word: mask
V_ENT   EQU 0x011C              ; word: the figure's entry
V_N     EQU 0x011E              ; sprites of this figure
V_LINE  EQU 0x011F              ; its palette line
V_SPR   EQU 0x0120              ; its first sprite
V_I     EQU 0x0121
V_TR    EQU 0x0122
V_TC    EQU 0x0123
V_X     EQU 0x0124              ; word
V_Y     EQU 0x0126
V_FULL  EQU 0x0127              ; figures left as the game draws them: no free entry or no free patterns
V_ODD   EQU 0x0128              ; ... a size the table does not hold
V_NP    EQU 0x0129              ; painted figures in PIDX (the build sets it; 0 = the plain colours)
V_NEXT  EQU 0x012A              ; where the search for a free pattern goes on
V_PAGE  EQU 0x012B
V_SRC   EQU 0x012C              ; word
V_A     EQU 0x012E
V_OLDN  EQU 0x012F
HLIB_V_PACE EQU 0x0140          ; 26 bytes
HLIB_PACE_NL EQU 311
NEW     EQU 0x0160              ; 12 bytes: the patterns taken for this figure
OLD     EQU 0x0170              ; 12 bytes: the ones it showed
HSTK    EQU 0x0300              ; the hooks' stack, below this
PMAP    EQU 0x0300              ; 128 bytes: 1 = the pattern is shown
ENTS    EQU 0x0380              ; NENT figures of 24 bytes: key, graphic, mask, rows, bytes, line, sprites, 12 patterns, x, y
NENT    EQU 10
E_SIZE  EQU 24
EVENT_HI EQU 0x90               ; an object's record below this address is a scene's, not the room's (those from 0x92D6)
MB      EQU 0x0600              ; 64 rows of 6 bytes: the mask, a row and a pixel larger than the graphic
GB      EQU 0x0800              ; the graphic, as the mask is laid out
TLO     EQU 0x0A00              ; (graphic nibble << 4 | mask nibble) -> the first two pixels
THI     EQU 0x0B00              ;                                       the last two
TT      EQU 0x0C00              ; 7 x 5 x 8 words: the routine's own time by rows / 8, bytes, shift (the build fills it)
PIDX    EQU 0x1000              ; painted figures, 8 bytes each: graphic, rows, bytes, page, address, line

        ORG 0x2800
rom_start:
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        DEFINE HLIB_PACE_LEAN
        DEFINE HLIB_PACE_CAP 0x0C00
        INCLUDE "lib/hlib_pace.asm"

; ---------------------------------------------------------------- the five CALLs of the figure routine
; A and the flags are dead at its entry (its first use of A is LD A,B).
e_obj:  ld a,0
        jp fig
e_olli: ld a,1
        jp fig
e_caul: ld a,2
        jp fig
e_big:  ld a,3
        jp fig

fig:    nextreg 0x50,WORK
        ld (V_KIND),a
        ld a,r
        ld (HLIB_V_R),a
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPEED
        ld (V_HL),hl
        ld (V_BC),bc
        ld (V_DE),de
        call hlib_pace_open
        call sprite
.n_rin: ld a,R_IN
        call hlib_r_set
        ld bc,(V_BC)
        ld de,(V_DE)
        ld sp,(V_SP)
        ld hl,fig_end
        ex (sp),hl              ; the routine returns here
        ld (V_RET),hl
        ld hl,(V_HL)
        HLIB_R_OUT
        nextreg 0x50,255
        jp FIG
fig_end:
        nextreg 0x50,WORK
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ld hl,D_FIG             ; the hook's own entry and exit, outside the window
        call hlib_debt_add
.n_t:   ld hl,(V_T)
        HLIB_SPEED_OUT V_SPEED
        ld a,(V_SPEED)
        call hlib_pace_wait
.n_rout: ld a,R_OUT
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        push hl
        ld hl,(V_RET)
        ex (sp),hl              ; the game's return address, where the game's own CALL left it
        HLIB_R_OUT
        nextreg 0x50,255
        ret
R_IN    EQU 0                   ; (the routine does not read R; R after it is set by R_OUT, from the verifier's comparison)
R_OUT   EQU 105                 ; -23
D_FIG   EQU 85                  ; calibrated so a figure takes the original's time (games/olli_and_lissa.md)

; ---------------------------------------------------------------- the five CALLs of the screen wipe
; Interrupts are on at the title's wipe: off while the state page stands where the ROM's handler is.
e_room:
e_wipe: push af
        HLIB_IFF_DI
        push af                 ; P/V = interrupts were on
        nextreg 0x50,WORK
        ld a,r
        ld (HLIB_V_R),a
        ld (V_SP),sp
        ld sp,HSTK
        push bc
        push de
        push hl
        call alloff
.n_r:   ld a,R_WIPE
        call hlib_r_set
        pop hl
        pop de
        pop bc
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x50,255
        pop af
        jp pe,.on
        nop
        jp .x
.on:    ei
        nop
.x:     pop af
        jp WIPE
R_WIPE  EQU 107                 ; -21

; Every sprite off, every figure and pattern forgotten.
alloff: xor a
.l:     nextreg 0x34,a
.n_off: nextreg 0x38,0
        inc a
        jp p,.l
        ld hl,PMAP
        ld de,PMAP + 1
        ld bc,ENTS + NENT * E_SIZE - PMAP - 1
        ld (hl),0
        ldir
        ret

; ---------------------------------------------------------------- a figure's sprites
; V_HL / V_BC / V_DE = the routine's arguments, V_KIND = the CALL. Leaves V_T = the routine's own time.
sprite: ld hl,0
        ld (V_T),hl
        ld de,(V_DE)            ; D rows, E bytes
        ld a,d
        and 7
        jp nz,.odd
        ld a,d
        rrca
        rrca
        rrca
        dec a
        cp 7
        jp nc,.odd              ; 8 to 56 rows
        ld b,a
        ld a,e
        dec a
        cp 5
        jp nc,.odd              ; 1 to 5 bytes
        ld c,a
        ld a,b
        add a,a
        add a,a
        add a,b
        add a,c
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_BC)
        and 7
        add hl,a
        add hl,hl
        add hl,TT
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_T),hl
        ld a,e
        ld (V_NB),a
        ld hl,txt
        add hl,a
        ld a,(hl)
        ld (V_TX),a
        ld b,a
        ld a,d
        ld (V_ROWS),a
        add a,17
        swapnib
        and 15
        ld (V_TY),a
        ld c,a
        xor a
.mul:   add a,c
        djnz .mul
        ld (V_N),a              ; sprites of this figure
        ; the figure's key
        ld a,(V_KIND)
        ld e,a
        ld d,0
        or a
        jr nz,.k
        push iy
        pop de
.k:     ld (V_KEY),de
        ld hl,ENTS
        ld bc,NENT * 256
.f:     ld a,(hl)
        inc hl
        cp e
        jr nz,.n
        ld a,(hl)
        cp d
        jr z,.found
.n:     dec hl
        ld a,(hl)
        inc hl
        or (hl)
        jr z,.new
        ld a,E_SIZE - 1
        add hl,a
        inc c
        djnz .f
.full:  ld hl,V_FULL
        inc (hl)
        ret
.odd:   ld hl,V_ODD
        inc (hl)
        ret
.new:   dec hl
        ld (hl),e
        inc hl
        ld (hl),d
.found: dec hl
        ld (V_ENT),hl
        ld a,c
        add a,a
        add a,a
        ld b,a
        add a,a
        add a,b                 ; x 12
        ld (V_SPR),a
        ld a,(V_KIND)           ; a scene the game plays over the room (Olli caught: records below the room's
        or a                    ; objects) rubs out what is under it and draws nothing else until its wipe:
        jr nz,.nev              ; the figures under it go back to the game's own drawing
        ld a,(V_KEY + 1)
        cp EVENT_HI
.n_ev:  call c,under
.nev:
        ld hl,(V_HL)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_G),de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_M),hl
        ; the same picture as this figure shows already: only its place changes
        ld hl,(V_ENT)
        inc hl
        inc hl
        ld a,(hl)
        cp e
        jr nz,.fresh
        inc hl
        ld a,(hl)
        cp d
        jr nz,.fresh
        inc hl
        ld de,(V_M)
        ld a,(hl)
        cp e
        jr nz,.fresh
        inc hl
        ld a,(hl)
        cp d
        jr nz,.fresh
        inc hl
        ld a,(V_ROWS)
        cp (hl)
        jr nz,.fresh
        inc hl
        ld a,(V_NB)
        cp (hl)
        jr nz,.fresh
        inc hl
        ld a,(hl)
        ld (V_LINE),a
        inc hl
        ld a,(hl)
        or a
        jr z,.fresh             ; (it has no sprites: left out for want of patterns)
        inc hl
        ld de,NEW
        ld bc,12
        ldir
        jp attrs
.fresh: ; what it shows now, to be freed once the new patterns are on
        ld hl,(V_ENT)
        ld a,9
        add hl,a
        ld a,(hl)
        ld (V_OLDN),a
        inc hl
        ld de,OLD
        ld bc,12
        ldir
        ; V_N free patterns
        ld a,(V_N)
        ld b,a
        ld de,NEW
        ld a,(V_NEXT)
        ld l,a
        ld h,PMAP >> 8
        ld c,128
.al:    ld a,(hl)
        or a
        jr nz,.used
        ld a,l
        ld (de),a
        inc de
        dec b
        jr z,.got
.used:  inc l
        res 7,l
        dec c
        jr nz,.al
        ; not enough: the figure stays as the game draws it
        call hide
        call free
        ld hl,(V_ENT)
        ld a,9
        add hl,a
        ld (hl),0
        jp sprite.full
.got:   inc l
        res 7,l
        ld a,l
        ld (V_NEXT),a
        ld a,(V_N)
        ld b,a
        ld hl,NEW
.mk:    ld e,(hl)
        ld d,PMAP >> 8
        ld a,1
        ld (de),a
        inc hl
        djnz .mk
        call upload
        ; the entry: graphic, mask, size, line, sprites, patterns
        ld hl,(V_ENT)
        inc hl
        inc hl
        ld de,(V_G)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_M)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_ROWS)
        ld (hl),a
        inc hl
        ld a,(V_NB)
        ld (hl),a
        inc hl
        ld a,(V_LINE)
        ld (hl),a
        inc hl
        ld a,(V_N)
        ld (hl),a
        inc hl
        ex de,hl
        ld hl,NEW
        ld bc,12
        ldir
        call attrs
        jp free
txt:    DB 0,1,2,2,3,3

; The patterns in OLD (V_OLDN of them) are free again.
free:   ld a,(V_OLDN)
        or a
        ret z
        ld b,a
        ld hl,OLD
.l:     ld e,(hl)
        ld d,PMAP >> 8
        xor a
.n_fr:  ld (de),a
        inc hl
        djnz .l
        ret

; Every other figure whose box this one's touches: its sprites off, its patterns free, no picture held.
under:  ld hl,ENTS
        ld bc,NENT * 256
.l:     push bc
        push hl
        ld de,(V_ENT)
        ld a,l
        cp e
        jr nz,.o
        ld a,h
        cp d
        jr z,.next
.o:     ld a,9
        add hl,a
        ld a,(hl)
        or a
        jr z,.next              ; (it shows nothing)
        pop hl
        push hl
        ld a,7
        add hl,a
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        add a,16
        ld e,a                  ; its width, with the byte the shift takes and one to spare
        ld a,15
        add hl,a                ; its x
        ld a,(V_NB)
        add a,a
        add a,a
        add a,a
        add a,16
        ld d,a
        ld a,(V_BC)
        sub (hl)
        jr nc,.xp
        neg
        cp d
        jr nc,.next
        jr .y
.xp:    cp e
        jr nc,.next
.y:     inc hl
        ld d,(hl)               ; its y (up the screen)
        pop hl
        push hl
        ld a,6
        add hl,a
        ld a,(hl)
        add a,4                 ; (the routine copies a few rows of clean room above and below)
        ld e,a
        ld a,(V_BC + 1)
        sub d
        jr nc,.yp
        neg
        cp e
        jr nc,.next
        jr .hit
.yp:    ld e,a
        ld a,(V_ROWS)
        add a,4
        ld d,a
        ld a,e
        cp d
        jr nc,.next
.hit:   pop hl
        pop bc
        push bc
        push hl
        ld a,c
        add a,a
        add a,a
        ld e,a
        add a,a
        add a,e                 ; x 12
        ld e,12
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        dec e
        jr nz,.h
        ld a,9
        add hl,a
        ld b,(hl)
        ld (hl),0
        inc hl
.fr:    ld e,(hl)
        ld d,PMAP >> 8
        xor a
        ld (de),a
        inc hl
        djnz .fr
.next:  pop hl
        pop bc
        ld a,E_SIZE
        add hl,a
        inc c
        dec b
        jp nz,.l
        ret

; The figure's 12 sprites off.
hide:   ld a,(V_SPR)
        ld b,12
.l:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .l
        ret

; The attributes of the figure's sprites: its patterns in NEW, V_N of them, V_TX across.
attrs:  ld hl,(V_ENT)           ; where it is, for a scene drawn over it
        ld a,22
        add hl,a
        ld a,(V_BC)
        ld (hl),a
        inc hl
        ld a,(V_BC + 1)
        ld (hl),a
        ld a,(V_BC)
        ld l,a
        ld h,0
        add hl,31               ; a pixel left of the graphic, the display from 32
        ld (V_X),hl
        ld a,(V_BC + 1)
        ld c,a
        cp 169                  ; line 175 - y is the graphic's first, the mask's a line above it, the display from 32;
        ld a,207                ; from y = 169 the routine starts at the screen's first line and draws a line lower
        jr nc,.n_y
        dec a
.n_y:   sub c
        ld (V_Y),a
        ld a,(V_SPR)
        ld (V_I),a
        ld de,NEW
        ld b,0                  ; the sprite's row
.tr:    ld c,0
.tc:    ld a,(V_I)
        nextreg 0x34,a
        ld a,c
        swapnib
        ld hl,(V_X)
        add hl,a
        ld a,l
        nextreg 0x35,a
        ld a,(V_LINE)
        swapnib
.n_x8:  or h
        nextreg 0x37,a
        ld a,b
        swapnib
        ld l,a
        ld a,(V_Y)
        add a,l
        nextreg 0x36,a
        ld a,(de)               ; the pattern, 0-127: N6 is its bit 0
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld a,(de)
        srl a
.n_vis: or 0xC0
        nextreg 0x38,a
        inc de
        ld hl,V_I
        inc (hl)
        inc c
        ld a,(V_TX)
        cp c
        jr nz,.tc
        inc b
        ld a,(V_TY)
        cp b
        jr nz,.tr
        ; the figure's other sprites off
        ld a,(V_SPR)
        add a,12
        ld c,a
        ld a,(V_I)
.off:   cp c
        ret z
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .off

; The figure's pictures into the patterns in NEW: its painted tiles, or 1 where the graphic is set and 2 where the
; mask clears.
upload: xor a
        ld (V_LINE),a
        ld a,(V_NP)
        or a
        jr z,plain
        ld b,a
        ld de,(V_G)
        ld hl,PIDX
.s:     ld a,(hl)
        cp e
        jr nz,.sn
        inc hl
        ld a,(hl)
        dec hl
        cp d
        jr z,.hit
.sn:    ld a,8
        add hl,a
        djnz .s
        jr plain
.hit:   inc hl
        inc hl
        ld a,(V_ROWS)
        cp (hl)
        jr nz,plain
        inc hl
        ld a,(V_NB)
        cp (hl)
        jr nz,plain
        inc hl
        ld a,(hl)
        ld (V_PAGE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (V_LINE),a
        ld a,(V_PAGE)
        nextreg 0x52,a
        ex de,hl                ; HL = the tiles, one after another
        ld de,NEW
        ld a,(V_N)
.pt:    push af
        ld a,(de)
        inc de
        call selpat
        ld bc,0x805B
.n_ot:  otir
        pop af
        dec a
        jr nz,.pt
        nextreg 0x52,10
        ret

plain:  ld hl,MB
        ld de,MB + 1
        ld bc,383
        ld (hl),0xFF
        ldir
        ld hl,GB
        ld de,GB + 1
        ld bc,383
        ld (hl),0
        ldir
        ld hl,(V_M)
        ld de,MB
        ld a,(V_ROWS)
        add a,2
        ld b,a
.mr:    push bc
        push de
        ld a,(V_NB)
        inc a
        ld c,a
        ld b,0
        ldir
        pop de
        ld a,6
        add de,a
        pop bc
        djnz .mr
        ld hl,(V_G)
        ld de,GB + 6
        ld a,(V_ROWS)
        ld b,a
.gr:    push bc
        push de
        ld a,(V_NB)
        ld b,a
        or a
.gb:    ld a,(hl)
        rra
        ld (de),a
        inc hl
        inc de
        djnz .gb
        ld a,0
        rra
        ld (de),a
        pop de
        ld a,6
        add de,a
        pop bc
        djnz .gr
        ; the patterns
        ld hl,NEW
        ld (V_SRC),hl
        xor a
        ld (V_TR),a
.tr:    xor a
        ld (V_TC),a
.tc:    ld hl,(V_SRC)
        ld a,(hl)
        inc hl
        ld (V_SRC),hl
        call selpat
        ld a,(V_TR)
        ld e,a
        ld d,96
        mul d,e
        ld a,(V_TC)
        add a,a
        add de,a
        ld hl,MB
        add hl,de
        ld b,16
.row:   push bc
        push hl
        call one
        inc hl
        call one
        pop hl
        ld a,6
        add hl,a
        pop bc
        djnz .row
        ld a,(V_TC)
        inc a
        ld (V_TC),a
        ld hl,V_TX
        cp (hl)
        jr c,.tc
        ld a,(V_TR)
        inc a
        ld (V_TR),a
        ld hl,V_TY
        cp (hl)
        jr c,.tr
        ret

; HL -> a mask byte (its graphic byte 0x200 above): its eight pixels to the pattern port.
one:    ld c,(hl)
        inc h
        inc h
        ld b,(hl)
        dec h
        dec h
        push hl
        ld a,c
        swapnib
        and 0x0F
        ld l,a
        ld a,b
        and 0xF0
        or l
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        ld a,b
        swapnib
        and 0xF0
        ld l,a
        ld a,c
        and 0x0F
        or l
        ld l,a
        ld h,TLO >> 8
        ld a,(hl)
.n_o:   out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        pop hl
        ret

; A = a 4-bit pattern, 0-127: the pattern port at its first byte. Keeps DE, HL.
selpat: srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ret
CODE_END:
ROM_END:
        SAVEBIN "olli_rom.bin",0x2800,ROM_END-0x2800

        ORG 0xD000
; The stub's setup: the sprites' palette, every sprite off, the printer buffer as the snapshot has it.
setup:  ld hl,pbuf
        ld de,0x5B00
        ld bc,256
        ldir
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
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
        nextreg 0x4B,0          ; a pattern's 0 is clear
        xor a
.so:    nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jp p,.so
        nextreg 0x1C,2          ; the sprites' window: the play area, above the panel
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,175
        nextreg 0x15,0x01       ; sprites on, over the ULA, inside the display
        nextreg 0x07,0
        ret
pal9:   DS 512
pbuf:   DS 256                  ; the snapshot's 0x5B00-0x5BFF (the build fills it in)
SETUP_END:
        SAVEBIN "olli_setup.bin",0xD000,SETUP_END-0xD000
