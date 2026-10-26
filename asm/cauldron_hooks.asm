; Cauldron (Palace Software, 1985, 48K) - hardware sprites over the figures (games/cauldron.md
; "Build design"). Overlay: the game's XOR plotter (0x6357) and every other screen writer still
; write the ULA exactly as the original; every LIVE image (one XOR plot drew it, its key's next
; plot erases it) gets 2 x 2 4-bit sprites on its pixels, in front. A key is (graphic, x, y, rows,
; width). Another writer that touches a live image's rectangle drops its sprite at that moment and
; taints the key (no sprite again until a clear holds the whole key: the residue the original
; leaves stays ULA-only, Dean 2026-10-26 Q6); a clear that holds the whole key forgets it.
;
; Patch sites (original bytes checked by the engine):
;   RAM 0x6357  5E 23 56  LD E,(HL) / INC HL / LD D,(HL) (plotter entry, HL = descriptor) -> JP e_plot
;   RAM 0xB2A0  21 00 48  LD HL,0x4800 (clear rows 64-191)                      -> JP e_clr
;   RAM 0xB366  6F 26 00  LD L,A / LD H,0 (8 x 8 tile at (45972))                -> JP e_tile
;   RAM 0xDED2  21 00 50  LD HL,0x5000 (bottom third: one byte left)            -> JP e_scl
;   RAM 0xDEEA  21 FF 57  LD HL,0x57FF (bottom third: one byte right)           -> JP e_scr
;   ROM 0x0B9B  3A 91 5C  LD A,(P-FLAG) in PR-ALL (HL = the cell)               -> JP e_char
;   ROM 0x0E44  C5 CD 9B  PUSH BC / CALL CL-ADDR (CL-LINE: B lines from bottom)  -> JP e_cll
;   ROM 0x0E00  CD 9B 0E  CALL CL-ADDR (CL-SCROLL; PO-SCR calls 0x0E00 too)      -> JP e_csc
; The ROM sites are bytes of the alt ROM image (patch.altrom0); the code is in alt ROM image 1 at
; 0x386E- (free FF in the 48K ROM), + the start-up register block, below 0x3D00.
; Tables and the code that uses them (0xC700-): Next page 26 mapped at slot 6 (0xC000) only while
; they are used; no game data is read then (the descriptor is copied through the stack first; graphics are read with MMU6 = page 0).
; Interrupts are left as the game has them: the ROM IM 1 handler touches slots 0 and 2 only and
; needs IY, which no hook changes. 28 MHz inside the hooks, 3.5 MHz while the original body runs.
; Sprites: slot s (0-27) = sprites 4s..4s+3 and 4-bit patterns 4s..4s+3 (top-left, top-right,
; bottom-left, bottom-right 16 x 16 of the unshifted image at pixel x); higher number on top.

        DEVICE ZXSPECTRUMNEXT

BODY    EQU 0x635A              ; the plotter after the replaced instructions; RET 0x63DA
PG      EQU 26                  ; table page (bank 13), at slot 6 inside a hook
NSLOT   EQU 28
NTAB    EQU 128
ATTR_T  EQU 23695
MASK_T  EQU 23696
P_FLAG  EQU 23697
TILEAT  EQU 45972               ; the tile writer's screen address (word)

V_N     EQU 0xC000              ; entries in use
V_OVF   EQU 0xC001              ; 1: overflow (new keys not recorded, no sprites) until a full clear
V_NFREE EQU 0xC002              ; free sprite slots
FREE    EQU 0xC003              ; 28 bytes: free slot stack (top = FREE + V_NFREE - 1)
DESC    EQU 0xC020              ; 8: graphic lo, hi, x, y, rows, width, attr type, attr value
RECT    EQU 0xC028              ; 4: y0, y1 (pixel rows), c0, c1 (byte columns)
KIND    EQU 0xC02C              ; touch: 0 taint, 1 clear
WRAP    EQU 0xC02D              ; 1: the plot reaches past column 31 (whole-screen rectangle), 2: too big; no sprite
USLOT   EQU 0xC02E              ; slot to upload + show
UINK    EQU 0xC02F              ; ink pair (ink * 0x11)
TAB     EQU 0xC100              ; NTAB x 12: key (6), state, y0, y1, c0, c1, 0
; state: 0-27 live with that sprite slot, 0xFE live with no sprite, 0xFF tainted

        ORG 0x386E
; ---- plotter entry (0x6357): HL = descriptor --------------------------------------------------
e_plot: push hl                 ; placeholder: the slot to hide at the exit (low byte)
        push af
        push bc
        push de
        push hl
        push ix
        nextreg 0x07,3
        ld e,(hl)               ; the descriptor through the stack (it may sit at 0xC000-0xDFFF)
        inc hl
        ld d,(hl)
        inc hl
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        push de
        nextreg 0x56,PG
        pop de
        ld (DESC+6),de
        pop de
        ld (DESC+4),de
        pop de
        ld (DESC+2),de
        pop de
        ld (DESC),de
        call p_ent              ; A = slot to hide at the exit, C = slot to show now (0xFF: none)
        ld hl,10                ; IX, HL, DE, BC, AF pushed: + 10 = the placeholder
        add hl,sp
        ld (hl),a
        ld a,c
        cp NSLOT
        jr nc,.nou
        ld a,(RECT)
        add a,32
        ld b,a                  ; Y
        push bc                 ; B = Y, C = slot
        ld a,(DESC+2)
        ld l,a
        ld h,0
        ld de,32
        add hl,de
        push hl                 ; X
        ld hl,(DESC)            ; graphic
        ld a,(DESC+5)
        ld e,a                  ; width
        ld a,(UINK)
        ld d,a
        ld a,(DESC+4)
        ld b,a                  ; rows
        nextreg 0x56,0
        call upload
        pop hl
        pop bc
        call show
        jr .go
.nou:   nextreg 0x56,0
.go:    nextreg 0x07,0
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld e,(hl)               ; the replaced instructions
        inc hl
        ld d,(hl)
        call BODY               ; its RET 0x63DA comes back here
        ex (sp),hl              ; L = the slot to hide; the game's HL on the stack
        push af
        ld a,l
        cp NSLOT
        call c,hide_s
        pop af
        pop hl
        ret

; ---- the other screen writers: B = y0, C = y1, D = c0, E = c1, A = kind ------------------------
e_char: push af                 ; ROM PR-ALL 0x0B9B: HL = the cell (screen or printer buffer)
        ld a,h
        cp 0x40
        jr c,.x
        cp 0x58
        jr nc,.x
        push bc
        push de
        push hl
        push ix
        call cellr
        xor a
        call dotouch
        pop ix
        pop hl
        pop de
        pop bc
.x:     pop af
        ld a,(P_FLAG)
        jp 0x0B9E

e_tile: push af                 ; 0xB366: the tile writer, cell at (45972)
        push bc
        push de
        push hl
        push ix
        ld hl,(TILEAT)
        ld a,h
        cp 0x40
        jr c,.x
        cp 0x58
        jr nc,.x
        call cellr
        xor a
        call dotouch
.x:     pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld l,a
        ld h,0
        jp 0xB369

e_clr:  push af                 ; 0xB2A0: rows 64-191 cleared
        push bc
        push de
        push hl
        push ix
        ld bc,64*256+191
        ld de,31
        ld a,1
        call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x4800
        jp 0xB2A3

e_scl:  push af                 ; 0xDED2: rows 128-191, bytes 0-30 <- 1-31
        push bc
        push de
        push hl
        push ix
        ld bc,128*256+191
        ld de,30
        xor a
        call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x5000
        jp 0xDED5

e_scr:  push af                 ; 0xDEEA: rows 128-191, bytes 1-31 <- 0-30
        push bc
        push de
        push hl
        push ix
        ld bc,128*256+191
        ld de,1*256+31
        xor a
        call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x57FF
        jp 0xDEED

e_cll:  push af                 ; ROM CL-LINE 0x0E44: B lines from the bottom cleared
        push bc
        push de
        push hl
        push ix
        ld a,b
        or a
        jr z,.all
        cp 25
        jr nc,.all
        ld c,a
        ld a,24
        sub c
        add a,a
        add a,a
        add a,a
        ld b,a
        ld c,191
        ld de,31
        ld a,1
        jr .t
.all:   ld bc,191
        ld de,31
        xor a
.t:     call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        push bc
        call 0x0E9B
        jp 0x0E48

e_csc:  push af                 ; ROM CL-SCROLL 0x0E00: the screen moves up a line
        push bc
        push de
        push hl
        push ix
        ld bc,191
        ld de,31
        xor a
        call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        call 0x0E9B
        jp 0x0E03

; HL screen address -> B = y0, C = y1, D = E = column; not the top line of a cell: whole screen
cellr:  ld a,h
        and 7
        jr nz,.all
        ld a,l
        and 31
        ld d,a
        ld e,a
        ld a,h
        and 0x18
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or b
        ld b,a
        add a,7
        ld c,a
        ret
.all:   ld bc,191
        ld de,31
        ret

dotouch:
        nextreg 0x07,3
        nextreg 0x56,PG
        ld (KIND),a
        ld a,b
        ld (RECT),a
        ld a,c
        ld (RECT+1),a
        ld a,d
        ld (RECT+2),a
        ld a,e
        ld (RECT+3),a
        call touch
        nextreg 0x56,0
        nextreg 0x07,0
        ret

; ---- sprites ------------------------------------------------------------------------------------
hide_s: add a,a                 ; A = slot: its 4 sprites hidden (A, F changed)
        add a,a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        ret

show:   ld a,c                  ; C = slot, HL = X, B = Y
        add a,a
        add a,a
        ld c,a
        call sh1
        inc c
        push hl
        ld de,16
        add hl,de
        call sh1
        pop hl
        inc c
        ld a,b
        add a,16
        ld b,a
        call sh1
        inc c
        ld de,16
        add hl,de
sh1:    ld a,c                  ; sprite C at (HL, B), pattern C (4-bit)
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,b
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; upload: C = slot, HL = graphic, E = width, B = rows, D = ink pair. 4 patterns of 16 lines x 8
; bytes: pattern k covers graphic bytes 2 (k & 1) .. +1 of lines 16 (k >> 1) .. +15.
upload: ld a,c
        add a,a                 ; pattern 4s: index 2s, first half
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld ix,-8
        add ix,sp
        ld sp,ix                ; frame: +0 w, +1 rows, +2 ink, +3/4 graphic, +5 k, +6 nb, +7 line
        ld (ix+0),e
        ld (ix+1),b
        ld (ix+2),d
        ld (ix+3),l
        ld (ix+4),h
        ld (ix+5),0
.k:     ld a,(ix+5)             ; HL = graphic + 16 w (k >> 1) + 2 (k & 1)
        and 2
        ld l,0
        jr z,.k0
        ld a,(ix+0)
        add a,a
        add a,a
        add a,a
        add a,a
        ld l,a
.k0:    ld a,(ix+5)
        and 1
        add a,a
        ld c,a                  ; 2 (k & 1)
        add a,l
        ld e,a
        ld d,0
        ld l,(ix+3)
        ld h,(ix+4)
        add hl,de
        ld a,(ix+0)             ; nb = min(2, max(0, w - 2 (k & 1)))
        sub c
        jr nc,.n0
        xor a
.n0:    cp 3
        jr c,.n1
        ld a,2
.n1:    ld (ix+6),a
        ld a,(ix+5)
        and 2
        add a,a
        add a,a
        add a,a                 ; 16 (k >> 1)
        ld (ix+7),a
        ld b,16
        ld d,(ix+2)
.ln:    ld a,(ix+7)
        cp (ix+1)
        jr nc,.z8               ; line >= rows: 8 zeros
        push hl
        ld c,(ix+6)
        ld a,c
        or a
        jr z,.zr
.eb:    ld a,(hl)
        call emit4
        inc hl
        dec c
        jr nz,.eb
.zr:    ld a,2
        sub (ix+6)
        jr z,.nz
        add a,a
        add a,a
        ld c,a
        xor a
.zz:    out (0x5B),a
        dec c
        jr nz,.zz
.nz:    pop hl
        jr .nx
.z8:    xor a
        ld c,8
.z9:    out (0x5B),a
        dec c
        jr nz,.z9
.nx:    ld a,l
        add a,(ix+0)
        ld l,a
        jr nc,.nc
        inc h
.nc:    inc (ix+7)
        djnz .ln
        inc (ix+5)
        ld a,(ix+5)
        cp 4
        jp c,.k
        ld ix,8
        add ix,sp
        ld sp,ix
        ret

emit4:  push hl                 ; A = graphic byte -> 4 pattern bytes (D = ink pair)
        push af
        rrca
        rrca
        rrca
        rrca
        call emit2
        pop af
        call emit2
        pop hl
        ret
emit2:  and 15
        add a,a
        add a,low NIBT
        ld l,a
        ld h,high NIBT
        ld a,(hl)
        and d
        out (0x5B),a
        inc l
        ld a,(hl)
        and d
        out (0x5B),a
        ret

        ALIGN 32
NIBT:   ; nibble (pixels 0-3, bit 3 first) -> 2 pattern-byte masks
        DEFB 0x00,0x00, 0x00,0x0F, 0x00,0xF0, 0x00,0xFF
        DEFB 0x0F,0x00, 0x0F,0x0F, 0x0F,0xF0, 0x0F,0xFF
        DEFB 0xF0,0x00, 0xF0,0x0F, 0xF0,0xF0, 0xF0,0xFF
        DEFB 0xFF,0x00, 0xFF,0x0F, 0xFF,0xF0, 0xFF,0xFF
rom_end:
        ASSERT rom_end + 20 <= 0x3D00

; ---- page 26 code (runs at 0xC700- while page 26 is at slot 6: no game data read) --------------
        ORG 0xC700
; p_ent: the plot whose descriptor is at DESC. -> A = slot to hide at the exit, C = slot to show
; now (0xFF: none); a shown slot has USLOT, UINK, RECT set.
p_ent:  ld a,(DESC+3)           ; y
        cp 176
        jp nc,.bad
        ld b,a
        ld a,(DESC+4)           ; rows
        or a
        jp z,.bad
        ld c,a
        ld a,b
        inc a
        cp c
        jp c,.bad               ; y + 1 < rows: PIXEL-ADD fails part way
        ld a,(DESC+5)
        or a
        jp z,.bad
        ld a,175
        sub b
        ld (RECT),a             ; y0 = 175 - y
        add a,c
        dec a
        ld (RECT+1),a           ; y1
        ld a,(DESC+2)
        ld d,a
        rrca
        rrca
        rrca
        and 31
        ld (RECT+2),a           ; c0
        ld e,a
        ld a,(DESC+5)
        add a,e
        dec a
        ld e,a
        ld a,d
        and 7
        ld a,e
        jr z,.al
        inc a
.al:    ld (RECT+3),a           ; c1 = c0 + w - 1 (+ 1 shifted)
        cp 32
        jr c,.fit
        xor a
        ld (RECT),a             ; past column 31: the whole screen, no sprite
        ld (RECT+2),a
        ld a,191
        ld (RECT+1),a
        ld a,31
        ld (RECT+3),a
        ld a,1
        jr .nw
.fit:   ld a,(DESC+5)           ; wider than 32 px or taller than 32 rows: no sprite (2 x 2 only)
        cp 5
        ld a,2
        jr nc,.nw
        ld a,(DESC+4)
        cp 33
        ld a,2
        jr nc,.nw
        xor a
.nw:    ld (WRAP),a
        call find
        jr nz,.new
        push hl
        ld de,6
        add hl,de
        ld a,(hl)               ; state
        pop hl
        cp 0xFF
        jp z,.none              ; tainted: stays tainted
        push af
        call remove
        pop af
        cp NSLOT
        jp nc,.none             ; live with no sprite
        call free_s
        ld c,0xFF
        ret                     ; A = the slot to hide at the exit
.new:   ld a,(V_OVF)
        or a
        jp nz,.none
        ld a,(V_N)
        cp NTAB
        jr c,.ins
        ld a,1
        ld (V_OVF),a
        jr .none
.ins:   call entry              ; HL = TAB + 12 N
        inc a
        ld (V_N),a
        ex de,hl
        ld hl,DESC
        ld bc,6
        ldir
        ex de,hl                ; HL = the state byte
        ld a,(WRAP)
        or a
        jr nz,.ns
        ld a,(V_NFREE)
        or a
        jr z,.ns
        dec a
        ld (V_NFREE),a
        push hl
        ld e,a
        ld d,0
        ld hl,FREE
        add hl,de
        ld a,(hl)
        pop hl
        jr .st
.ns:    ld a,0xFE
.st:    ld (hl),a
        inc hl
        ex de,hl
        ld hl,RECT
        ld bc,4
        ldir
        xor a
        ld (de),a
        ld a,(WRAP)             ; (RECT is the whole screen for a wrapped key)
        or a
        jr nz,.none
        call entry
        ld de,-12+6
        add hl,de               ; the new entry's state (entry gives TAB + 12 N, N already + 1)
        ld a,(hl)
        cp NSLOT
        jr nc,.none
        ld (USLOT),a
        call ink
        ld a,(USLOT)
        ld c,a
        ld a,0xFF
        ret
.bad:   call taint_all
        ld a,1
        ld (V_OVF),a
.none:  ld a,0xFF
        ld c,a
        ret

entry:  ld a,(V_N)              ; -> HL = TAB + 12 V_N, A = V_N
        push af
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld de,TAB
        add hl,de
        pop af
        ret

find:   ld a,(V_N)              ; key at DESC -> Z, HL = its entry / NZ
        or a
        jr z,.no
        ld b,a
        ld hl,TAB
.lp:    push hl
        ld de,DESC
        ld c,6
.cm:    ld a,(de)
        cp (hl)
        jr nz,.ne
        inc de
        inc hl
        dec c
        jr nz,.cm
        pop hl
        ret
.ne:    pop hl
        ld de,12
        add hl,de
        djnz .lp
.no:    or 1
        ret

remove: push hl                 ; HL = entry: the last entry moves into it
        ld a,(V_N)
        dec a
        ld (V_N),a
        call entry              ; HL = the last
        pop de
        ld a,l
        cp e
        jr nz,.cp
        ld a,h
        cp d
        ret z
.cp:    ld bc,12
        ldir
        ret

free_s: push hl                 ; A = slot -> the free stack (A kept)
        push de
        ld hl,V_NFREE
        ld e,(hl)
        inc (hl)
        ld d,0
        ld hl,FREE
        add hl,de
        ld (hl),a
        pop de
        pop hl
        ret

ink:    ld a,(RECT)             ; colour of the image's first cell after the plotter's first paint
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(RECT+2)
        add a,l
        ld l,a
        ld a,h
        add a,0x58
        ld h,a
        ld c,(hl)               ; the cell's attribute now
        ld a,(DESC+6)
        cp 2
        jr z,.t2
        or a
        jr nz,.t1
        ld a,(ATTR_T)           ; type 0: old = ATTR-T -> the value
        cp c
        jr nz,.kp
        ld a,(DESC+7)
        jr .got
.t1:    ld a,(DESC+7)           ; other types: old = the value -> ATTR-T
        cp c
        jr nz,.kp
        ld a,(ATTR_T)
        jr .got
.kp:    ld a,c
        jr .got
.t2:    ld de,(ATTR_T)          ; type 2: ROM PO-ATTR (0x0BE4)
        ld a,c
        xor e
        and d
        xor e
        ld hl,P_FLAG
        bit 6,(hl)
        jr z,.p4
        and 0xC7
        bit 2,a
        jr nz,.p4
        xor 0x38
.p4:    bit 4,(hl)
        jr z,.got
        and 0xF8
        bit 5,a
        jr nz,.got
        xor 7
.got:   ld c,a
        and 7
        jr z,.bk
        bit 6,c
        jr z,.pr
        or 8
        jr .pr
.bk:    ld a,8                  ; black (bright or not): palette 8 (0 is transparent)
.pr:    ld c,a
        rlca
        rlca
        rlca
        rlca
        or c
        ld (UINK),a
        ret

; touch: RECT, KIND. Every entry whose rectangle meets RECT: its sprite hidden and freed; a clear
; holding it whole forgets it (the last entry moves in), otherwise it is tainted. A clear of the
; whole screen ends the overflow.
touch:  ld ix,TAB
        ld a,(V_N)
        ld b,a
.lp:    ld a,b
        or a
        jr z,.done
        ld hl,RECT
        ld a,(ix+8)
        cp (hl)
        jr c,.next              ; e.y1 < y0
        inc hl
        ld a,(hl)
        cp (ix+7)
        jr c,.next              ; y1 < e.y0
        inc hl
        ld a,(ix+10)
        cp (hl)
        jr c,.next              ; e.c1 < c0
        inc hl
        ld a,(hl)
        cp (ix+9)
        jr c,.next              ; c1 < e.c0
        ld a,(ix+6)
        cp NSLOT
        jr nc,.ns
        call hide_s
        ld a,(ix+6)
        call free_s
.ns:    ld a,(KIND)
        or a
        jr z,.tn
        ld hl,RECT
        ld a,(ix+7)
        cp (hl)
        jr c,.tn                ; e.y0 < y0
        inc hl
        ld a,(hl)
        cp (ix+8)
        jr c,.tn                ; y1 < e.y1
        inc hl
        ld a,(ix+9)
        cp (hl)
        jr c,.tn                ; e.c0 < c0
        inc hl
        ld a,(hl)
        cp (ix+10)
        jr c,.tn                ; c1 < e.c1
        push bc
        push ix
        pop hl
        call remove
        pop bc
        dec b
        jr .lp
.tn:    ld (ix+6),0xFF
.next:  ld de,12
        add ix,de
        dec b
        jr .lp
.done:  ld a,(KIND)
        or a
        ret z
        ld hl,RECT
        ld a,(hl)
        or a
        ret nz
        inc hl
        ld a,(hl)
        cp 191
        ret nz
        inc hl
        ld a,(hl)
        or a
        ret nz
        inc hl
        ld a,(hl)
        cp 31
        ret nz
        xor a
        ld (V_OVF),a
        ret

taint_all:
        ld ix,TAB
        ld a,(V_N)
        ld b,a
.lp:    ld a,b
        or a
        ret z
        ld a,(ix+6)
        cp NSLOT
        jr nc,.t
        call hide_s
        ld a,(ix+6)
        call free_s
.t:     ld (ix+6),0xFF
        ld de,12
        add ix,de
        dec b
        jr .lp
p26_end:
        ASSERT p26_end <= 0xE000


; ---- the ROM-site jumps (copied into the alt ROM image below 0x2000 by the stub) ----------------
        ORG 0x3000
j_char: jp e_char
j_cll:  jp e_cll
j_csc:  jp e_csc
j_end:

; ---- setup (stub bank, 0xD000): sprite palette, sprites hidden (4-bit attr 4 set), sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0          ; nibble 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        ld c,a
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld a,c
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
pal:    defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "cau_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "cau_jmp.bin",0x3000,j_end-0x3000
        SAVEBIN "cau_p26.bin",0xC700,p26_end-0xC700
        SAVEBIN "cau_setup.bin",0xD000,setup_end-0xD000
