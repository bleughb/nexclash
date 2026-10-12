; Commando (Elite, 128K) - hardware sprites for the player, enemy soldiers and the POW group.
; One plotter (39120 -> 39202) draws every figure: a differential "clear old frame bits, OR new
; frame" routine, IX = object descriptor (+0/+4 old/new column, +1/+5 old/new y in 2-line units,
; +2/+6 old/new frame, +3/+7 old/new graphics page, +10 row pairs, +11 flags). Figures have no
; mask, so dropping only the OR of the new frame leaves every other screen byte as the original.
; Main path (both columns < 30, inside the window): the new frame is read only through H/L of the
; active set (INC L only), so pointing H at a 256-byte zero page turns the call into erase-only.
; Edge / top-clip paths keep drawing on the ULA (the hook only hides the object's old sprite).
; The main-path loops assume a column step of -1/0/+1 (they draw at old column +-1); any other
; step stays on the ULA too, and so does a row step |dy| >= the image's row pairs (the loops wrap).
; Rows below line 191 (bottom clip) are cut by the sprite clip window.
; Interrupts are ENABLED at every hook site and the ISR writes 7FFD, so nothing is paged: stubs
; and code live in alt ROM image 1 (0x386E-), state in bank-5 RAM the game never touches once it
; runs (0x5C00-0x5E1F: never read or written after USR 25088 - boot simulation + reference RZX).
;
; Patch sites (original bytes verified by commando.py):
;   39120  C3 22 99      JP 39202                    -> JP e_ent   (every plot: hide old sprite)
;   39366  7A 93 EB E1   LD A,D/SUB E/EX DE,HL/POP HL -> JP e_main  (main path: zero page)
;   39529  ED 7B 82 FD C9  LD SP,(64898) / RET        -> JP e_x     (main exit: show new sprite)
;   40955  ED 7B 82 FD C9  LD SP,(64898) / RET        -> JP e_x     (main exit, bottom clip)
;   27468  CB 21 CB 21   SLA C / SLA C               -> JP e_rect  (rectangle clear)
;   30597  21 00 40      LD HL,16384                 -> JP e_cls   (full screen clear)
;   25630  C3 D2 69      JP 27090                    -> JP e_init  (game entry from BASIC: init)
; The snapshot is the BASIC loader (line 30): 0x5C00-0x5E1F holds the system variables and the
; program until BASIC runs USR 25088 -> JP 25630 (both loader paths pass 25630, once). The build
; leaves that RAM alone; e_init sets up the hook state there when the game takes over.
; A converted plot leaves every register, the game stack and all RAM as the original, except the
; screen bytes of the new frame (never read by game logic) and stale copies of H in dead stack.

        DEVICE ZXSPECTRUMNEXT

NENT    EQU 12                  ; sprite entries (4 sprites, 2 x 4 patterns each)
ZPH     EQU 0x5D                ; zero page 0x5D00-0x5DFF
V_SP    EQU 0x5C00              ; game SP while a hook runs
V_HL    EQU 0x5C02              ; HL after the plotter's POP HL (new frame pointer)
V_ON    EQU 0x5C04              ; 1 = this plot is converted (set at 39366, cleared at exit)
V_FREED EQU 0x5C05              ; entry index hidden by this call's entry hook (0xFF none)
V_CNT   EQU 0x5C06              ; entries in use
V_ROW   EQU 0x5C07              ; upload: rows (lines) of the image
V_PG    EQU 0x5C08              ; upload: graphics page (H)
V_L0    EQU 0x5C09              ; upload: frame offset (L)
V_R0    EQU 0x5C0A              ; rect clear: first line
V_R1    EQU 0x5C0B              ; rect clear: line after
V_C0    EQU 0x5C0C              ; rect clear: first byte column
V_C1    EQU 0x5C0D              ; rect clear: column after
ENT     EQU 0x5C10              ; NENT x 8: used, ix lo, ix hi, col, y, bank, lines, spare
STK     EQU 0x5D00              ; hook stack top (0x5C70-0x5CFF)
NIBT    EQU 0x5E00              ; 16 x 2 bytes: nibble -> two 4-bit pixel bytes (ink index 1)
MASK    EQU 0x5E20              ; 32 rows x 3 bytes: scenery pixels in front of the figure
D_F64   EQU 0x5E80              ; depth temps: walk-test point y + 6 (2-line units) + 64
D_FL0   EQU 0x5E81              ; figure first line
D_FL1   EQU 0x5E82              ; figure last line (<= 191)
D_FC    EQU 0x5E83              ; figure first column
D_OBJ   EQU 0x5E84              ; object list entry (2 bytes)
D_A0    EQU 0x5E86              ; overlap lines / columns
D_A1    EQU 0x5E87
D_B0    EQU 0x5E88
D_B1    EQU 0x5E89
D_N     EQU 0x5E8A              ; list walk limit
V_SVN   EQU 0x5E8B              ; scenery save: lines saved (0 = nothing to restore)
V_SVL   EQU 0x5E8C              ; scenery save: first line
V_SVC   EQU 0x5E8D              ; scenery save: first column
SAVE    EQU 0x5F00              ; scenery save: up to 32 lines x 3 bytes (game never touches it)
DT      EQU 0x3400              ; depth table (alt ROM): 41 x 8, derived from the game by Python

        ORG 0x386E
; ---- 39120: every plot. Converted object -> hide the sprite of the image it will erase ----
e_ent:  ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,0xFF
        ld (V_FREED),a
        xor a
        ld (V_SVN),a
        call isconv
        jr nz,.out
        ld e,(ix+0)
        ld d,(ix+1)
        call find
        jr nz,.out
        ld a,b
        ld (V_FREED),a
        call hide
        nextreg 0x07,3              ; the old image was a sprite: save the scenery its erase will cut
        call svsave
        nextreg 0x07,0
.out:   pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        jp 39202

; ---- 39366: main path. Converted -> new frame read from the zero page ----
; Runs on the game stack (the plotter's PUSH HL is still on it): no CALL/PUSH here.
e_main: ld a,ixh                    ; A/F free: LD A,D / SUB E recompute both
        cp 0x5B
        jr z,.lo
        cp 0xFD
        jr nz,.no
        ld a,ixl
        cp 0xCF
        jr nz,.no
        jr .yes
.lo:    ld a,ixl
        cp 0xDA
        jr z,.yes
        cp 0x11
        jr z,.yes
        cp 0x25
        jr z,.yes
        cp 0x39
        jr z,.yes
        cp 0x4D
        jr z,.yes
        cp 0x61
        jr nz,.no
.yes:
        ld a,(V_CNT)
        cp NENT
        jr nc,.no                   ; table full: this plot stays on the ULA
        ld a,(ix+7)
        cp 32
        jr nc,.no                   ; page outside 0xA0-0xBF: not a figure page
        ld a,d                      ; column step new - old must be -1, 0 or +1: the draw loops
        sub e                       ; put the new frame at old column +-1 whatever (IX+4) says
        inc a
        cp 3
        jr nc,.no
        ld a,(ix+5)                 ; row step |new y - old y| must be < row pairs (+10): else the
        sub (ix+1)                  ; one-image loops (40600/40671) and the overlap loop wrap and
        jr nc,.dy                   ; draw past the frame data
        neg
.dy:    cp (ix+10)
        jr nc,.no
        ld a,1
        ld (V_ON),a
        ld a,d
        sub e
        ex de,hl
        pop hl
        ld (V_HL),hl
        ld h,ZPH
        jp 39370
.no:    xor a
        ld (V_ON),a
        ld a,d
        sub e
        ex de,hl
        pop hl
        jp 39370

; ---- 39529 / 40955: main-path exit. Restore H, show the new frame as sprites ----
e_x:    ld sp,(64898)
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,(V_ON)
        or a
        jr z,.pass
        xor a
        ld (V_ON),a
        ld a,h                      ; the zero-page H is in the main or the alternate set
        cp ZPH
        jr nz,.alt
        ld a,(V_HL+1)
        ld h,a
        jr .show
.alt:   exx
        ld a,h
        cp ZPH
        jr nz,.alt2
        ld a,(V_HL+1)
        ld h,a
.alt2:  exx
.show:  push bc
        push de
        push hl
        exx
        push bc
        push de
        push hl
        nextreg 0x07,3
        call svrest                 ; scenery the erase cut back first: the ULA is as before the plot
        call show
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
.pass:  pop af
        ld sp,(V_SP)
        ret

; ---- 27468: rectangle clear (HL as passed, B bytes wide, C char rows) -> hide what it covers ----
e_rect: ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,l                      ; byte column = L & 63 (the routine's HL*4 -> L/4)
        and 63
        ld (V_C0),a
        add a,b
        ld (V_C1),a
        add hl,hl
        add hl,hl
        ld a,h                      ; first line = 2 * H(HL*4)
        add a,a
        ld (V_R0),a
        ld a,c                      ; lines = 8 * C
        add a,a
        add a,a
        add a,a
        ld e,a
        ld a,(V_R0)
        add a,e
        jr nc,.r1
        ld a,0xFF
.r1:    ld (V_R1),a
        ld b,0
        ld hl,ENT
.lp:    ld a,(hl)
        or a
        jr z,.nx
        push hl
        inc hl
        inc hl
        inc hl
        ld a,(V_C1)                 ; col < C1 and col + 3 > C0
        ld e,(hl)
        cp e
        jr z,.no
        jr c,.no
        ld a,e
        add a,3
        ld e,a
        ld a,(V_C0)
        cp e
        jr nc,.no
        inc hl
        ld a,(hl)                   ; line0 = 2y < R1 and line0 + lines > R0
        add a,a
        ld d,a
        ld a,(V_R1)
        cp d
        jr z,.no
        jr c,.no
        inc hl
        inc hl
        ld a,(hl)
        add a,d
        ld d,a
        ld a,(V_R0)
        cp d
        jr nc,.no
        pop hl
        push hl
        call hide
.no:    pop hl
.nx:    ld de,8
        add hl,de
        inc b
        ld a,b
        cp NENT
        jr c,.lp
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        sla c
        sla c
        jp 27472

; ---- 30597: full screen clear -> hide every sprite ----
e_cls:  ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push hl
        ld b,0
        ld hl,ENT
.lp:    ld a,(hl)
        or a
        call nz,hide
        ld a,l
        add a,8
        ld l,a
        inc b
        ld a,b
        cp NENT
        jr c,.lp
        pop hl
        pop bc
        pop af
        ld sp,(V_SP)
        ld hl,16384
        jp 30600

; ---- 25630: game entry (BASIC USR -> JP 25630). Hook state from scratch, all sprites hidden ----
e_init: ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld hl,V_SP+2                ; vars + entry table (0x5C02-0x5C6F) = 0
        ld b,ENT+8*NENT-V_SP-2
.z1:    ld (hl),0
        inc hl
        djnz .z1
        ld a,0xFF
        ld (V_FREED),a
        ld hl,ZPH*256               ; zero page = 0
        xor a
.z2:    ld (hl),a
        inc l
        jr nz,.z2
        ld hl,nibrom                ; nibble table
        ld de,NIBT
        ld bc,32
        ldir
        xor a                       ; sprites 0..4*NENT-1 hidden
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 4*NENT
        jr c,.h
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        jp 27090

; nibble -> two 4-bit pixel bytes (ink index 1, 0 transparent); copied to NIBT by e_init
nibrom: db 0x00,0x00, 0x00,0x01, 0x00,0x10, 0x00,0x11, 0x01,0x00, 0x01,0x01, 0x01,0x10, 0x01,0x11
        db 0x10,0x00, 0x10,0x01, 0x10,0x10, 0x10,0x11, 0x11,0x00, 0x11,0x01, 0x11,0x10, 0x11,0x11

; ---- helpers ----
; Z if IX is a converted descriptor: player 23514, enemies 23313+20n (n<5), POW group 64975
; (same list inlined in e_main)
isconv: ld a,ixh
        cp 0x5B
        jr z,.lo
        cp 0xFD
        ret nz
        ld a,ixl
        cp 0xCF
        ret
.lo:    ld a,ixl
        cp 0xDA
        ret z
        cp 0x11
        ret z
        cp 0x25
        ret z
        cp 0x39
        ret z
        cp 0x4D
        ret z
        cp 0x61
        ret

; HL = entry with (used, IX, col E, y D), B = its index; Z if found
find:   ld b,0
        ld hl,ENT
.lp:    ld a,(hl)
        or a
        jr z,.nx
        inc l
        ld a,(hl)
        cp ixl
        jr nz,.n1
        inc l
        ld a,(hl)
        cp ixh
        jr nz,.n2
        inc l
        ld a,(hl)
        cp e
        jr nz,.n3
        inc l
        ld a,(hl)
        cp d
        jr nz,.n4
        ld a,l
        and 0xF8
        ld l,a
        xor a                       ; Z
        ret
.n4:    dec l
.n3:    dec l
.n2:    dec l
.n1:    dec l
.nx:    ld a,l
        add a,8
        ld l,a
        inc b
        ld a,b
        cp NENT
        jr c,.lp
        or a                        ; NZ (B = NENT)
        ret

; hide entry HL (index B): mark free, make its 4 sprites invisible
hide:   ld (hl),0
        ld a,(V_CNT)
        dec a
        ld (V_CNT),a
        ld a,b
        add a,a
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

; show the descriptor's new frame (IX, after the plot: +0 col, +1 y, +2 frame, +3 page, +10 pairs)
show:   ld a,(ix+1)                 ; frame starts below line 191 (walked off the bottom): nothing
        cp 96                       ; to show and no entry kept (the game may reuse the descriptor
        ret nc                      ; without plotting it again: the entry would never be freed)
        ld a,(V_FREED)              ; reuse the entry this object just left, else the first free
        cp NENT
        jr nc,.first
        ld b,a
        add a,a
        add a,a
        add a,a
        add a,low ENT
        ld l,a
        ld h,high ENT
        ld a,(hl)
        or a
        jr z,.got
.first: ld b,0
        ld hl,ENT
.f:     ld a,(hl)
        or a
        jr z,.got
        ld a,l
        add a,8
        ld l,a
        inc b
        ld a,b
        cp NENT
        jr c,.f
        ret                         ; cannot happen: e_main checked V_CNT < NENT
.got:   ld a,(V_CNT)
        inc a
        ld (V_CNT),a
        ld (hl),1
        inc l
        ld a,ixl
        ld (hl),a
        inc l
        ld a,ixh
        ld (hl),a
        inc l
        ld a,(ix+0)
        ld (hl),a
        inc l
        ld a,(ix+1)
        ld (hl),a
        inc l
        ld a,(hl)                   ; pattern bank: toggle (double buffer)
        xor 1
        ld (hl),a
        ld c,a
        inc l
        ld a,(ix+10)
        add a,a
        ld (hl),a
        ld (V_ROW),a
        ld a,(ix+3)
        add a,0xA0
        ld (V_PG),a
        ld a,(ix+11)                ; frame offset: (0x98E2 + 2 * frame + bit 2 of flags)
        rrca
        rrca
        and 1
        ld e,a
        ld a,(ix+2)
        add a,a
        add a,e
        add a,0xE2
        ld l,a
        ld h,0x98
        ld a,(hl)
        ld (V_L0),a
        call occl                   ; depth: mask of scenery in front of this figure
        ld a,b                      ; first pattern = 8 * index + 4 * bank
        add a,a
        add a,c
        add a,a
        add a,a
        ld e,a
        rra                         ; select: pattern >> 1 | (pattern & 1) << 7 (pattern even)
        and 0x7F
        push bc
        ld bc,0x303B
        out (c),a
        ld d,0                      ; top-left: rows 0-15, columns 0/1
        ld c,0
        call pat
        ld c,2                      ; top-right: rows 0-15, column 2
        call pat
        ld d,16
        ld c,0
        call pat
        ld c,2
        call pat
        pop bc
        ; attributes: sprite 4b+k at (col*8 + 32 + 16(k&1), 2y + 32 + 16(k>>1)), palette = colour
        call colour
        ld c,a                      ; C = palette offset << 4
        ld a,b
        add a,a
        add a,a
        ld b,a                      ; B = first sprite
        ld d,0                      ; k
.at:    ld a,b
        add a,d
        nextreg 0x34,a
        ld a,(ix+0)                 ; X = col*8 + 32 + 16(k&1) (9 bits)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,d
        and 1
        jr z,.x0
        ld a,l
        add a,16
        ld l,a
        jr nc,.x0
        inc h
.x0:    ld a,l
        add a,32
        ld l,a
        jr nc,.x1
        inc h
.x1:    ld a,l
        nextreg 0x35,a
        ld a,(ix+1)                 ; Y = 2y + 32 + 16(k>>1) (< 256)
        add a,a
        add a,32
        bit 1,d
        jr z,.y0
        add a,16
.y0:    nextreg 0x36,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,e                      ; pattern = first + k
        add a,d
        push af
        rra
        and 0x3F
        or 0xC0                     ; visible, attribute 4 follows
        nextreg 0x38,a
        pop af
        and 1
        rrca
        rrca                        ; bit 0 -> bit 6 (N6)
        or 0x80                     ; 4-bit pattern
        nextreg 0x39,a
        inc d
        ld a,d
        cp 4
        jr c,.at
        ret

; A = palette offset << 4: player black (0), POW the ink painted under its centre if red/magenta
; (else red), enemies blue (1)
colour: ld a,ixh
        cp 0xFD
        jr z,.pow
        ld a,ixl
        cp 0xDA
        ld a,0x00
        ret z
        ld a,0x10
        ret
.pow:   ld a,(ix+1)                 ; centre line = 2y + rows/2 -> cell row = line / 8
        add a,a
        ld l,a
        ld a,(V_ROW)
        srl a
        add a,l
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl                   ; row * 32
        ld a,(ix+0)
        inc a
        add a,l
        ld l,a
        ld a,h
        adc a,0x58
        ld h,a
        ld a,(hl)
        and 7
        cp 2
        jr z,.ok
        cp 3
        jr z,.ok
        ld a,2
.ok:    rlca
        rlca
        rlca
        rlca
        ret

; upload 16 rows (D = first row) of column group C (0: columns 0,1; 2: column 2 + 8 clear pixels)
pat:    push de
        ld e,16
.row:   ld a,(V_ROW)
        dec a
        cp d
        jr c,.blank                 ; row >= rows: transparent
        ld a,c
        call fetch
        call emit
        ld a,c
        or a
        jr nz,.half
        inc a
        call fetch
        call emit
        jr .next
.half:  xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        jr .next
.blank: xor a
        ld b,8
.bl:    out (0x5B),a
        djnz .bl
.next:  inc d
        dec e
        jr nz,.row
        pop de
        ret

; A = graphics byte at row D, column A (stream: even row c0 c1 c2, odd row c2 c1 c0)
fetch:  push hl
        push bc
        ld c,a                      ; logical (screen) column 0..2
        ld a,d                      ; B = occlusion mask byte at (row D, column C)
        add a,a
        add a,d
        add a,c
        add a,low MASK
        ld l,a
        ld h,high MASK
        ld b,(hl)
        ld l,c
        bit 0,d
        jr z,.ev
        ld a,2
        sub l
        ld l,a
.ev:    ld a,d                      ; 3 * row
        add a,a
        add a,d
        add a,l
        ld l,a
        ld a,(V_L0)
        add a,l
        ld l,a
        ld a,(V_PG)
        ld h,a
        ld a,b                      ; graphics byte AND NOT mask
        cpl
        and (hl)
        pop bc
        pop hl
        ret

; A = 8 pixels -> 4 bytes of 4-bit pixels (1 = ink, 0 = transparent)
emit:   push hl
        push af
        rrca
        rrca
        rrca
        and 0x1E
        ld l,a
        ld h,high NIBT
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        pop af
        add a,a
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        pop hl
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, hide all, clip, sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr c,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
pal:                                ; 256 palette bytes appended by Python

; --- start-up front end (RAM 0x5D00, both builds): the loader's PAUSE 0 + "INFY LIVES(Y/N)?" ---
; The .nex starts here instead of in 128K BASIC (which pages ROM 0, absent on the Next). State =
; the game entry (after DI at 25088) as the real loader leaves it, with the prompt cells of row 0
; restored to the loading screen. Wait for a new key (PAUSE 0), show the prompt (pixels + FLASH
; attributes copied from the loader's own PRINT), wait for Y or N (Y: POKE 27653,182 = infinite
; lives), restore every register, JP 25089. The game never touches 0x5C00-0x5E1F after the entry;
; the sprite build's e_init clears it later.
F_PIX   EQU 0x5D80              ; 8 lines x 16 bytes of row 0 (prompt), appended by Python
F_ATT   EQU 0x5E00              ; 16 attributes of row 0 (prompt)
F_SP    EQU 0x5E10
F_STK   EQU 0x5E20
        ORG 0x5D00
front:  ld (F_SP),sp
        ld sp,F_STK
        push af
        push bc
        push de
        push hl
.rel:   xor a                       ; wait until no key is held
        in a,(0xFE)
        and 0x1F
        cp 0x1F
        jr nz,.rel
.key:   xor a                       ; PAUSE 0: any key
        in a,(0xFE)
        and 0x1F
        cp 0x1F
        jr z,.key
        ld hl,F_PIX                 ; PRINT AT 0,0; INK 7; FLASH 1; "INFY LIVES(Y/N)?"
        ld de,0x4000
        ld b,8
.pl:    push bc
        push de
        ld bc,16
        ldir
        pop de
        inc d
        pop bc
        djnz .pl
        ld hl,F_ATT
        ld de,0x5800
        ld bc,16
        ldir
.yn:    ld a,0xDF                   ; Y: row P O I U Y, bit 4
        in a,(0xFE)
        bit 4,a
        jr z,.yes
        ld a,0x7F                   ; N: row SPACE SYM M N B, bit 3
        in a,(0xFE)
        bit 3,a
        jr z,.no
        jr .yn
.yes:   ld a,182                    ; POKE 27653,182
        ld (27653),a
.no:    pop hl
        pop de
        pop bc
        pop af
        ld sp,(F_SP)
        jp ENTRY1
front_end:
ENTRY1  EQU 25089
        SAVEBIN "commando_front.bin",0x5D00,front_end-0x5D00

; --- depth (alt ROM 0x3000: ROM bytes the game never reads or executes) -----------------------
; The game's scenery is an object list (0xFF00: +0 next, +2 type, +3 x (column = bits 0-4), +4 y =
; base line / 2). Per type, the game's own walk-blocking boxes (the collision list 0xF900 it builds)
; and the object's pixel extent are in DT (Python derives them by running the game's draw and box
; routines): +0 bit 0 = has a walk box, +1/+2 first/last column, +3/+4 first/last line (signed,
; relative to column x & 31 and line 2y), +5 = middle of the boxes (2-line units, relative to y) + 64.
; Dean's rule: a figure that reaches a box from below (test point y + 6 below the box middle) is in
; front of the object; from above (test point at or above the middle) it is behind it - the game
; stops the point at the box bottom / top, so this holds for every box height: the sprite loses the pixels where
; that object's ink is on the screen inside its extent (the ULA scenery shows through).
        ORG 0x3000
occl:   push bc
        push de
        push hl
        push iy
        ld hl,MASK
        ld b,96
        xor a
.cl:    ld (hl),a
        inc l
        djnz .cl
        ld a,(64904)                ; last list entry (0: empty list)
        or a
        jp z,.done
        ld a,(ix+1)                 ; test point = y + 6 (+64): the point the game's own walk test
        add a,6                     ; (57139, from 57371) checks against the boxes - not the feet
        add a,64
        ld (D_F64),a
        ld a,(ix+1)
        add a,a
        ld (D_FL0),a
        ld e,a
        ld a,(ix+10)
        add a,a
        dec a
        add a,e
        cp 192
        jr c,.l1
        ld a,191
.l1:    ld (D_FL1),a
        ld a,(ix+0)
        ld (D_FC),a
        ld a,64
        ld (D_N),a
        ld hl,0xFF00
        ld l,(hl)
.obj:   ld (D_OBJ),hl
        inc l
        inc l
        ld a,(hl)
        and 127
        jp z,.next
        cp 41
        jp nc,.next
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,DT
        add hl,de
        push hl
        pop iy
        pop hl
        bit 0,(iy+0)
        jp z,.next
        inc l
        ld a,(hl)
        and 31
        ld c,a                      ; C = object column
        inc l
        ld b,(hl)                   ; B = object y
        ld a,b
        add a,(iy+5)
        ld e,a                      ; E = box middle + 64
        ld a,(D_F64)
        cp e
        jr z,.behind
        jp nc,.next                 ; feet below the middle: figure in front
.behind:
        ld l,b                      ; first line = 2y + l0 (16-bit signed)
        ld h,0
        add hl,hl
        push hl
        ld a,(iy+3)
        call adds
        ld a,h                      ; A0 = max(first line, figure first line)
        or a
        jp m,.a0f
        jp nz,.skip1
        ld a,(D_FL0)
        cp l
        jr nc,.a0s
        ld a,l
        jr .a0s
.a0f:   ld a,(D_FL0)
.a0s:   ld (D_A0),a
        pop hl
        ld a,(iy+4)                 ; last line = 2y + l1
        call adds
        ld a,h                      ; A1 = min(last line, figure last line)
        or a
        jp m,.next
        jr nz,.a1f
        ld a,(D_FL1)
        cp l
        jr c,.a1s
        ld a,l
        jr .a1s
.a1f:   ld a,(D_FL1)
.a1s:   ld (D_A1),a
        ld e,a
        ld a,(D_A0)
        cp e
        jr z,.cols
        jp nc,.next
.cols:  ld a,(D_FC)                 ; B0 = max(x + c0, figure column) (all + 64)
        add a,64
        ld e,a
        ld a,c
        add a,(iy+1)
        add a,64
        cp e
        jr nc,.b0
        ld a,e
.b0:    sub 64
        ld (D_B0),a
        ld a,(D_FC)                 ; B1 = min(x + c1, figure column + 2)
        add a,66
        ld e,a
        ld a,c
        add a,(iy+2)
        add a,64
        cp e
        jr c,.b1
        ld a,e
.b1:    sub 64
        ld (D_B1),a
        ld e,a
        ld a,(D_B0)
        cp e
        jr z,.rows
        jp nc,.next
.rows:  ld a,(D_A0)                 ; for each line A0..A1, column B0..B1: mask |= screen
        ld d,a
.row:   ld a,(D_B0)
        ld c,a
        ld a,d
        call scr                    ; HL = screen byte (line D, column C)
        push hl
        ld a,(D_FL0)                ; DE' = MASK + 3 * (line - FL0) + (B0 - FC)
        ld e,a
        ld a,d
        sub e
        ld e,a
        add a,a
        add a,e
        ld e,a
        ld a,(D_FC)
        ld b,a
        ld a,c
        sub b
        add a,e
        add a,low MASK
        ld e,a
        pop hl
        push de
        ld d,high MASK
        ld a,(D_B1)
        sub c
        inc a
        ld b,a
.col:   ld a,(de)
        or (hl)
        ld (de),a
        inc e
        inc l
        djnz .col
        pop de
        ld a,(D_A1)
        cp d
        jr z,.next
        inc d
        jr .row
.skip1: pop hl
.next:  ld hl,D_N
        dec (hl)
        jr z,.done
        ld hl,(D_OBJ)
        ld a,(64904)
        cp l
        jr z,.done
        ld l,(hl)
        jp .obj
.done:  pop iy
        pop hl
        pop de
        pop bc
        ret

adds:   ld e,a                      ; HL += sign-extended A (DE clobbered)
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ret

scr:    ld l,a                      ; HL = screen address of line A (0..191), column C
        and 7
        or 0x40
        ld h,a
        ld a,l
        rra
        rra
        rra
        and 0x18
        or h
        ld h,a
        ld a,l
        rla
        rla
        and 0xE0
        or c
        ld l,a
        ret
; ---- scenery save / restore: a converted plot whose old image was a sprite leaves the ULA as it
; was. The plotter's erase clears the old frame's bits (never on the ULA: it was a sprite) out of
; the scenery, and the game redraws scenery only in some frames. e_ent saves the 3 x lines bytes
; under the old frame (svsave); e_x ORs them back (svrest): the new frame was not drawn, so the
; screen equals the screen before the plot - no bitten scenery, and an exact depth mask.
svsave: xor a                       ; IX = descriptor before the plot (+0 col, +1 y, +10 pairs)
        ld (V_SVN),a
        ld a,(ix+0)
        cp 30
        ret nc
        ld c,a
        ld (V_SVC),a
        ld a,(ix+10)
        add a,a
        ret z
        ld d,a                      ; D = lines
        ld a,(ix+1)
        add a,a
        ld (V_SVL),a
        ld e,a                      ; E = line
        push iy
        ld iy,SAVE
.lp:    ld a,e
        cp 192
        jr nc,.end
        call scr
        ld a,(hl)
        ld (iy+0),a
        inc l
        ld a,(hl)
        ld (iy+1),a
        inc l
        ld a,(hl)
        ld (iy+2),a
        inc iy
        inc iy
        inc iy
        ld a,(V_SVN)
        inc a
        ld (V_SVN),a
        inc e
        dec d
        jr nz,.lp
.end:   pop iy
        ret

svrest: ld a,(V_SVN)                ; OR the saved bytes back (erase cleared only old-frame bits)
        or a
        ret z
        ld d,a
        ld a,(V_SVC)
        ld c,a
        ld a,(V_SVL)
        ld e,a
        push iy
        ld iy,SAVE
.lp:    ld a,e
        call scr
        ld a,(iy+0)
        or (hl)
        ld (hl),a
        inc l
        ld a,(iy+1)
        or (hl)
        ld (hl),a
        inc l
        ld a,(iy+2)
        or (hl)
        ld (hl),a
        inc iy
        inc iy
        inc iy
        inc e
        dec d
        jr nz,.lp
        xor a
        ld (V_SVN),a
        pop iy
        ret
depth_end:
        SAVEBIN "commando_depth.bin",0x3000,depth_end-0x3000

        SAVEBIN "commando_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "commando_setup.bin",0xD000,pal-0xD000
