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
        call isconv
        jr nz,.out
        ld e,(ix+0)
        ld d,(ix+1)
        call find
        jr nz,.out
        ld a,b
        ld (V_FREED),a
        call hide
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
        ld l,a
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
        ld a,(hl)
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

        SAVEBIN "commando_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "commando_setup.bin",0xD000,pal-0xD000
