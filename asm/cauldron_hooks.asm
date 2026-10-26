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
NSLOT   EQU 14                  ; 9 sprites / 9 patterns a slot (3 x 3 of 16 x 16: image + outline up to 34 x 34)
NTAB    EQU 128
P27     EQU 27                  ; page 27 at slot 4 (0x8000-) inside hooks: attribute shadow, canvases, code
GPG4    EQU 4                   ; the game's page at slot 4
SH      EQU 0x8000              ; 768: the attribute file the ORIGINAL holds (the ULA keeps the scenery's)
USAVE   EQU 0x8300              ; 192 pairs: (ULA, shadow) attribute at the last bottom-third save
CB      EQU 0x8490              ; 1: CL-LINE's B at the hook
UNC     EQU 0x8491              ; sprite grid columns / rows of the slot being shown
UNR     EQU 0x8492
UG      EQU 0x8493              ; upload: graphic (2), width, rows, ink, slot, pattern base, row, col,
UWW     EQU 0x8495              ;   bytes per line pair, line
URR     EQU 0x8496
UIN     EQU 0x8497
USL     EQU 0x8498
UPN     EQU 0x8499
UTR     EQU 0x849A
UTC     EQU 0x849B
UNB     EQU 0x849C
UL      EQU 0x849D
CANI    EQU 0x8500              ; 36 x 5: ink bits, canvas line L at CANI + 5 (L + 1), pixel x at bit x + 1
CANO    EQU 0x8600              ; 36 x 5: outline bits (4-neighbours of ink, not ink)
TT      EQU 0x8700              ; 16: (ink 2 bits, outline 2 bits) -> pattern byte (2 pixels)
BUF     EQU 51700               ; the game's bottom-third attribute buffer (0xC9DB / 0xC9E7)
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
UINK    EQU 0xC02F              ; ink nibble (1-15)
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
        nextreg 0x54,P27        ; the attribute shadow (ink rule, body copy), canvases, page-27 code
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
        call upload             ; page 27: canvas + patterns (UNC, UNR)
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
        call body2              ; the plotter body, attributes painted into the shadow; RET comes back here
        ex (sp),hl              ; L = the slot to hide; the game's HL on the stack
        push af
        ld a,l
        cp NSLOT
        call c,hide_s
        nextreg 0x54,GPG4
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
        nextreg 0x54,P27
        ld a,b
        ld (CB),a
        nextreg 0x54,GPG4
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
.all:   nextreg 0x54,P27        ; B 0 or > 24 (garbage): the ULA takes the shadow first
        call u_from_s
        nextreg 0x54,GPG4
        ld bc,191
        ld de,31
        xor a
.t:     call dotouch
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        call .run               ; CL-LINE runs; its RET comes back here
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        nextreg 0x54,P27
        call cll_post           ; the cleared rows into the shadow
        nextreg 0x54,GPG4
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ret
.run:   push bc
        call 0x0E9B
        jp 0x0E48

e_csc:  push af                 ; ROM CL-SCROLL 0x0E00: the screen moves up a line (never in the RZX)
        push bc
        push de
        push hl
        push ix
        ld bc,191
        ld de,31
        xor a
        call dotouch
        nextreg 0x07,3
        nextreg 0x54,P27        ; the ULA takes the shadow (the scroll moves the original's attributes)
        call u_from_s
        nextreg 0x54,GPG4
        nextreg 0x07,0
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        call .run               ; CL-SCROLL, then CL-LINE (e_cll), returns here
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        nextreg 0x54,P27
        call s_from_u
        nextreg 0x54,GPG4
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ret
.run:   call 0x0E9B
        jp 0x0E03

; ---- attribute shadow: the ULA keeps the scenery's colours (Dean 2026-10-27 Q8) ----------------
e_peek: push af                 ; 0x61D8 LD L,(HL) (runtime PEEK / ATTR): attributes from the shadow
        ld a,h
        cp 0x58
        jr c,.n
        cp 0x5B
        jr nc,.n
        nextreg 0x54,P27
        add a,0x28
        ld h,a
        ld l,(hl)
        sub 0x28
        ld h,a                  ; H as the original's (LD H,0 at 0x61D5 follows)
        nextreg 0x54,GPG4
        pop af
        jp 0x61D5
.n:     pop af
        ld l,(hl)
        jp 0x61D5

e_poa:  ld a,h                  ; ROM PO-ATTR 0x0BE4 (HL = attribute): on the ULA, then on the shadow
        cp 0x58
        jr c,poa_r
        cp 0x5B
        jr nc,poa_r
        push hl
        call poa_r              ; the ULA cell from its own old value
        pop hl
        nextreg 0x54,P27
        push hl
        ld a,h
        add a,0x28
        ld h,a
        call poa_r              ; the shadow last: A, DE, F as the original's
        pop hl
        nextreg 0x54,GPG4
        ret
poa_r:  ld de,(ATTR_T)
        jp 0x0BE8

e_tatt: ld a,h                  ; 0xB33E: a room tile's attribute, (DE) = H | 0x40, ULA and shadow
        set 6,a
        ld (de),a
        push af
        ld a,d
        cp 0x58
        jr c,.x
        cp 0x5B
        jr nc,.x
        push de
        add a,0x28
        ld d,a
        nextreg 0x54,P27
        ld a,h
        set 6,a
        ld (de),a
        nextreg 0x54,GPG4
        pop de
.x:     pop af
        jp 0xB342

e_tard: push hl                 ; 0xB361 LD A,(DE): a room cell's attribute, from the shadow
        push af
        ld a,d
        cp 0x58
        jr c,.n
        cp 0x5B
        jr nc,.n
        push de
        add a,0x28
        ld d,a
        nextreg 0x54,P27
        ld a,(de)
        nextreg 0x54,GPG4
        pop de
        jr .w
.n:     ld a,(de)
.w:     ld h,a
        pop af
        ld a,h
        pop hl
        ld (TILEAT),hl
        jp 0xB365

e_save: nextreg 0x07,3          ; 0xC9DB: bottom-third attributes -> BUF (the shadow's; ULA + shadow kept)
        nextreg 0x54,P27
        call save27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xC9E6

e_rest: nextreg 0x07,3          ; 0xC9E7: BUF -> bottom third (shadow = BUF; ULA = its saved colours)
        nextreg 0x54,P27
        call rest27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xC9F2

e_box:  nextreg 0x07,3          ; 0xCE74: 6 x 5 attribute box from 52820, on the ULA and the shadow
        nextreg 0x54,P27
        call box27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xCE8D

e_rfil: nextreg 0x07,3          ; 0xB2AC: rows 4-23 filled with (23297), on the ULA and the shadow
        nextreg 0x54,P27
        call rfil27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xB2BB

e_sal:  nextreg 0x07,3          ; 0xDF04: bottom-third attributes one cell left, ULA and shadow
        nextreg 0x54,P27
        call sal27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xDF16

e_sar:  nextreg 0x07,3          ; 0xDF17: one cell right
        nextreg 0x54,P27
        call sar27
        nextreg 0x54,GPG4
        nextreg 0x07,0
        jp 0xDF29

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
hide_s: push bc                 ; A = slot: its 9 sprites hidden (A, F changed)
        ld c,a
        add a,a
        add a,a
        add a,a
        add a,c                 ; 9 s
        ld b,9
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        pop bc
        ret

; show: C = slot, HL = X (image x + 32), B = Y (image y0 + 32); UNC x UNR sprites of the grid at
; (X - 1 + 16 col, Y - 1 + 16 row) shown, the slot's other sprites hidden. Page 27 mapped.
show:   ld a,c
        call hide_s
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,c
        ld c,a                  ; sprite / pattern 9 s
        dec hl
        dec b
        ld a,(UNR)
        ld e,a
.r:     push hl
        push bc
        ld a,(UNC)
        ld d,a
.c:     call sh1
        inc c
        push de
        ld de,16
        add hl,de
        pop de
        dec d
        jr nz,.c
        pop bc
        pop hl
        ld a,c
        add a,3
        ld c,a
        ld a,b
        add a,16
        ld b,a
        dec e
        jr nz,.r
        ret

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
        add a,high SH
        ld h,a
        ld c,(hl)               ; the cell's attribute now (the shadow = the original's, page 27 at slot 4)
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
.pr:    ld (UINK),a             ; the ink nibble
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



; ---- page 27 code (0x8A00-, runs while page 27 is at slot 4; graphics are game memory 0xA5D2-) -----
        ORG 0x8A00
; upload: C = slot, HL = graphic, E = width (bytes), B = rows, D = ink nibble. The image's ink bits
; at canvas pixel (x + 1, line + 1), the outline = the 4-neighbours of ink that are not ink, the
; slot's UNC x UNR patterns (9 s + 3 row + col) written: ink pixels the ink, outline 8 (black).
upload: ld (UG),hl
        ld a,e
        ld (UWW),a
        ld a,b
        ld (URR),a
        ld a,d
        ld (UIN),a
        ld a,c
        ld (USL),a
        ld a,e
        add a,a
        add a,a
        add a,a
        add a,17
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (UNC),a              ; (8 w + 2 + 15) / 16
        ld a,b
        add a,17
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (UNR),a              ; (rows + 2 + 15) / 16
        ld hl,CANI
        ld de,CANI+1
        ld bc,511
        ld (hl),0
        ldir
        ld hl,(UG)
        ld de,CANI+10           ; image row 0 = canvas line 1
        ld a,(URR)
        ld c,a
.row:   push de
        ld a,(UWW)
        ld b,a
        or a                    ; CF = 0: pixel x lands at bit x + 1
.byt:   ld a,(hl)
        rra
        ld (de),a
        inc hl
        inc de
        djnz .byt
        ld a,0
        rra
        ld (de),a
        pop de
        ld a,e
        add a,5
        ld e,a
        jr nc,.r1
        inc d
.r1:    dec c
        jr nz,.row
        ld a,(URR)              ; outline over canvas lines 0 .. rows + 1 (5 bytes each, flat)
        add a,2
        ld b,a
        add a,a
        add a,a
        add a,b
        ld b,a
        ld ix,CANI+5
        ld hl,CANO+5
.ol:    ld a,(ix-5)
        or (ix+5)
        ld c,a
        ld a,(ix-1)
        rrca
        and 0x80
        ld d,a
        ld a,(ix+0)
        srl a
        or d
        or c
        ld c,a
        ld a,(ix+1)
        rlca
        and 1
        ld d,a
        ld a,(ix+0)
        add a,a
        or d
        or c
        ld c,a
        ld a,(ix+0)
        cpl
        and c
        ld (hl),a
        inc ix
        inc hl
        djnz .ol
        ld hl,TT                ; (ink hi, ink lo, outline hi, outline lo) -> 2 pixels
        ld c,0
.tt:    ld a,c
        and 8
        ld a,(UIN)
        jr nz,.h
        ld a,c
        and 2
        ld a,8
        jr nz,.h
        xor a
.h:     rlca
        rlca
        rlca
        rlca
        ld d,a
        ld a,c
        and 4
        ld a,(UIN)
        jr nz,.lo
        ld a,c
        and 1
        ld a,8
        jr nz,.lo
        xor a
.lo:    or d
        ld (hl),a
        inc hl
        inc c
        ld a,c
        cp 16
        jr nz,.tt
        ld a,(USL)
        ld b,a
        add a,a
        add a,a
        add a,a
        add a,b
        ld (UPN),a              ; 9 s
        xor a
        ld (UTR),a
.tr:    xor a
        ld (UTC),a
.tc:    ld a,(UTR)
        ld b,a
        add a,a
        add a,b
        ld b,a
        ld a,(UTC)
        add a,b
        ld b,a
        ld a,(UPN)
        add a,b                 ; pattern n
        rrca                    ; 4-bit pattern n: index n >> 1, bit 7 = n & 1
        ld bc,0x303B
        out (c),a
        ld a,(UTC)
        add a,a
        ld b,a
        ld a,5
        sub b
        cp 3
        jr c,.nb
        ld a,2
.nb:    ld (UNB),a              ; canvas bytes in this column: min(2, 5 - 2 col)
        ld a,(UTR)
        add a,a
        add a,a
        add a,a
        add a,a
        ld (UL),a
        ld b,16
.ln:    push bc
        ld a,(URR)
        inc a
        ld c,a
        ld a,(UL)
        cp c
        jr z,.in
        jr nc,.zl               ; past canvas line rows + 1: empty
.in:    inc a
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de               ; 5 (L + 1)
        ld a,(UTC)
        add a,a
        add a,l
        ld l,a
        ld de,CANI
        add hl,de
        ld a,(UNB)
        ld b,a
.bp:    ld c,(hl)               ; ink byte
        inc h
        ld e,(hl)               ; outline byte (CANO = CANI + 0x100)
        dec h
        inc hl
        ld d,4
.px:    xor a
        rl c
        rla
        rl c
        rla
        rl e
        rla
        rl e
        rla
        push hl
        ld l,a
        ld h,high TT
        ld a,(hl)
        pop hl
        out (0x5B),a
        dec d
        jr nz,.px
        djnz .bp
        ld a,(UNB)
        ld b,a
        ld a,2
        sub b
        jr z,.lnx
        add a,a
        add a,a
        ld b,a
        xor a
.zp:    out (0x5B),a
        djnz .zp
        jr .lnx
.zl:    xor a
        ld b,8
.zz:    out (0x5B),a
        djnz .zz
.lnx:   ld a,(UL)
        inc a
        ld (UL),a
        pop bc
        djnz .ln
        ld a,(UTC)
        inc a
        ld (UTC),a
        ld b,a
        ld a,(UNC)
        cp b
        jp nz,.tc
        ld a,(UTR)
        inc a
        ld (UTR),a
        ld b,a
        ld a,(UNR)
        cp b
        jp nz,.tr
        ret

; body2: the plotter body (0x635A-0x63DA) with every attribute access on the shadow (OR 0x80 for
; OR 0x58; type 2 PO-ATTR through poa_r on the shadow cell). Entered as the original at 0x635A.
body2:  inc hl
        push de
        pop ix
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        inc hl
.l1:    push af
        push bc
        push hl
        call 0x22AA             ; PIXEL-ADD
        ld c,a
        ex de,hl
        pop hl
        ld b,(hl)
        ld a,c
        or a
        jr z,.s1
        inc b
.s1:    inc hl
        ex de,hl
        push hl
.l2:    push hl
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or high SH
        ld h,a
        ld a,(de)
        inc de
        cp 2
        jr nz,.t01
        push de
        call poa_r
        pop de
        jr .nx
.t01:   or a
        jr nz,.t1
        ld a,(23693)
        cp (hl)
        jr nz,.nx
        ld a,(de)
        jr .wr
.t1:    ld a,(de)
        cp (hl)
        jr nz,.nx
        ld a,(23693)
.wr:    ld (hl),a
.nx:    pop hl
        inc hl
        dec de
        djnz .l2
        dec de
        ex de,hl
        ld b,(hl)
        ex (sp),hl
        ld a,c
        or a
        jr z,.al
.sh:    ex de,hl
        ld l,(ix+0)
        ld h,0
        ld a,8
        sub c
.sl:    add hl,hl
        dec a
        jr nz,.sl
        ex de,hl
        ld a,(hl)
        xor d
        ld (hl),a
        inc hl
        ld a,(hl)
        xor e
        ld (hl),a
        inc ix
        djnz .sh
        jr .en
.al:    ld a,(ix+0)
        xor (hl)
        ld (hl),a
        inc hl
        inc ix
        djnz .al
.en:    pop hl
        pop bc
        dec b
        pop af
        dec a
        jr nz,.l1
        ret

cll_post:                       ; after CL-LINE: its rows (or, B 0 / > 24, everything) into the shadow
        ld a,(CB)
        or a
        jr z,s_from_u
        cp 25
        jr nc,s_from_u
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l                  ; 32 B
        ld hl,0x5B00
        and a
        sbc hl,bc
        push hl
        ld de,SH-0x5800
        add hl,de
        ex de,hl
        pop hl
        ldir
        ret
s_from_u:
        ld hl,0x5800
        ld de,SH
        ld bc,768
        ldir
        ret
u_from_s:
        ld hl,SH
        ld de,0x5800
        ld bc,768
        ldir
        ret

save27: push af                 ; (ULA, shadow) pairs saved; BUF = the shadow (as the original)
        push ix
        ld hl,0x5A00
        ld de,SH+0x200
        ld ix,USAVE
        ld b,192
.l:     ld a,(hl)
        ld (ix+0),a
        ld a,(de)
        ld (ix+1),a
        inc hl
        inc de
        inc ix
        inc ix
        djnz .l
        pop ix
        pop af
        ld hl,SH+0x200
        ld de,BUF
        ld bc,192
        ldir                    ; flags as the original's LDIR (same bytes, same A)
        ld hl,0x5AC0
        ret

rest27: push af                 ; ULA: the colour it had at the save where BUF still holds that save's value
        push ix
        ld hl,BUF
        ld de,0x5A00
        ld ix,USAVE
        ld b,192
.l:     ld a,(hl)
        cp (ix+1)
        jr nz,.w
        ld a,(ix+0)
.w:     ld (de),a
        inc hl
        inc de
        inc ix
        inc ix
        djnz .l
        pop ix
        pop af
        ld hl,BUF
        ld de,SH+0x200
        ld bc,192
        ldir                    ; shadow = BUF; registers and flags as the original's
        ld de,0x5AC0
        ret

box27:  ld hl,0x58E6
        call .b
        ld hl,SH+0xE6
        call .b
        ld hl,0x5986
        ret
.b:     ld de,52820
        ld c,5
.r:     ld b,6
.c:     ld a,(de)
        ld (hl),a
        inc hl
        inc de
        djnz .c
        push de
        ld de,26
        add hl,de
        pop de
        dec c
        jr nz,.r
        ret

rfil27: ld a,(23297)
        ld hl,0x5880
        ld de,0x5881
        ld (hl),a
        ld bc,639
        ldir
        ld a,(23297)
        ld hl,SH+0x80
        ld de,SH+0x81
        ld (hl),a
        ld bc,639
        ldir
        ld hl,0x5AFF
        ld de,0x5B00
        ret

sal27:  ld hl,0x5A00
        call .s
        ld hl,SH+0x200
        call .s
        ld hl,0x5B00
        ret
.s:     ld c,8
.r:     ld b,31
.m:     inc hl
        ld e,(hl)
        dec hl
        ld (hl),e
        inc hl
        djnz .m
        inc hl
        dec c
        jr nz,.r
        ret

sar27:  ld hl,0x5AFF
        call .s
        ld hl,SH+0x2FF
        call .s
        ld hl,0x59FF
        ret
.s:     ld c,8
.r:     ld b,31
.m:     dec hl
        ld e,(hl)
        inc hl
        ld (hl),e
        dec hl
        djnz .m
        dec hl
        dec c
        jr nz,.r
        ret
p27_end:
        ASSERT p27_end <= 0xA000

; ---- the ROM-site jumps (copied into the alt ROM image below 0x2000 by the stub) ----------------
        ORG 0x3000
j_char: jp e_char
j_cll:  jp e_cll
j_csc:  jp e_csc
j_poa:  jp e_poa
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
        SAVEBIN "cau_p27.bin",0x8A00,p27_end-0x8A00
