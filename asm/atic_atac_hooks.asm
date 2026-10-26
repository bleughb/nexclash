; Atic Atac (48K) - every figure a hardware sprite, outlined and solid (games/atic_atac.md, Build design).
;
; The game draws every figure by XOR with two row blitters (0x9EDC set A / 0x9F21 set B), one whole
; image per plot: graphic DE = height h + h rows of 2 bytes, drawn upward from line y, pixel x.
; Converted writes go into a 1-bit SHADOW screen (page SHPG at slot 3 while a hook runs, shadow
; address = screen address | 0x2000) instead of the ULA, so ULA XOR SHADOW == the original screen at
; every moment. The non-XOR writers compute the original's new byte from the virtual old one
; (ULA ^ shadow) and write new ^ shadow to the ULA. The play-area clear empties the shadow and hides
; every sprite. No logic reads figure pixels (stage 1 figdep), so nothing reads the shadow back.
;
; Display: hardware sprites. Each shown image = one entry (table ENT); one pattern PAIR (an 8-bit
; pattern slot = two 4-bit patterns) per visible tile row; sprite 2q / 2q+1 shows 4-bit pattern
; 2q / 2q+1 (left / right half, 16 px each: 18 px wide with the outline). Patterns come from the
; pattern store (pages STPG.., built by atic_atac.py from the snapshot's graphics: ink = index 1,
; outline + enclosed paper = index 2 black, 0 transparent); the palette offset is the figure's
; colour (IX+5: ink + 8 * BRIGHT). XOR parity per image key (DE, x, y): a plot of a key not shown
; draws it; a plot of a shown key erases it, which only marks it PENDING (still visible): the next
; draw by the same owner (IX) reuses its sprites (the 0x9FCA move = erase + draw in one call), a
; plot by another owner or the clear hides it.
;
; Memory: hook code in alt ROM image 1 at 0x2000- (the game reads no ROM byte in 0x2000-0x38DF:
; RZX scan); variables + hook stack in the printer buffer 0x5B80-0x5BFF (never touched by the
; game); hook tables in the shadow page above the shadow (0x7800-, slot 3 during hooks). Slot 3 is
; the game's page 11 again at every exit, slot 7 page 1. Interrupts stay ON (ROM IM 1: keeps every
; register, reads IY, touches slots 0 and 2 only): hooks never change IX, IY, I, IFF or the
; alternate registers; the row hooks use the game's stack exactly as the original blitter does,
; the others switch to the hook stack.
;
; Patch sites (original bytes verified by atic_atac.py):
;   0x9EA0 CD DC 9E  CALL 0x9EDC       -> CALL h_rowa   blitter A row (shift: JR offset at 40677)
;   0x9EA9 CD 21 9F  CALL 0x9F21       -> CALL h_rowb   blitter B row (shift: JR offset at 40746)
;   0x9F97 1A 32 18  LD A,(DE) / LD (24088),A  -> JP h_setm   set A setup: id (24085), x, y (24086/7)
;   0x9FC1 1A 32 19  LD A,(DE) / LD (24089),A  -> JP h_seta   set B setup: id IX+0, x, y IX+3 / IX+4
;   0x8093 21 00 40  LD HL,16384       -> JP h_clear    play-area clear
;   0x9C75 B6 77 E1  OR (HL) / LD (HL),A / POP HL -> JP h_line  room-line pixel
;   0x99D7 / 0x9A36 / 0x9A78 / 0x9ADD / 0x9B88  op / LD (HL),A / INC L -> JP h_o1..h_o5 (scenery
;        drawers; the op byte NOP / OR (HL) / XOR (HL) is written by the game: its writers 0x99CD /
;        0x9A0E / 0x9A54 / 0x9ACF / 0x9B61 `LD (op),A` -> `LD (V_OP1..5),A`)
;   0xA1E6 77 13 24  LD (HL),A / INC DE / INC H -> JP h_txt  text printer
;   figure painter LD (HL),D at 0xA07D 0xA093 0xA0A6 0xA0BA 0xA0D8 0xA113 -> NOP (colour on the sprite)

        DEVICE ZXSPECTRUMNEXT

SHPG    EQU 26                  ; shadow page: shadow screen 0x6000-0x77FF, tables 0x7800-
GPG     EQU 11                  ; the game's page at slot 3 (48K)
GP7     EQU 1                   ; the game's page at slot 7 (48K)
SH      EQU 0x6000
DIR     EQU 0x7800              ; 256 ids x 4: store page (0 = none), tile-row index in page, tile rows, rows above y (hc)
ENT     EQU 0x7C00              ; NENT entries x ESZ bytes
NENT    EQU 24
ESZ     EQU 26                  ; +0 flags (1 used, 2 pending), +1 G, +3 x, +4 base line, +5 owner IX, +7 npairs,
                                ; +8..+21 pairs, +22 H, +23..+25 row mask (bit k = row k drawn, odd times)
PAIRS   EQU 0x7ED0              ; 8 bytes: bit = pair in use (64 pairs = 128 4-bit patterns)
WPG     EQU 28                  ; work page (slot 7 during fig): GADR, the build grid and its patterns
GP6     EQU 0                   ; the game's page at slot 6 (48K; the store page there during build)
GADR    EQU 0xE000              ; 256 ids x 2: the graphic address the id's stored image was built from
GB      EQU 0xE200              ; build grid, (H + 4) x 20 bytes
OB      EQU 0xE600              ; built patterns: 2 tile rows
OBH     EQU 0xE6                ; (an immediate: `ld a,(expr)` would be a memory read)
OBR     EQU 6                   ; OB as a tile-row index of the work page
MAXP    EQU 14

V_SP    EQU 0x5B80              ; game SP at hook entry
V_VAL   EQU 0x5B82              ; scratch byte
V_OPC   EQU 0x5B83              ; current drawer op
V_OP1   EQU 0x5B84              ; 5 drawer op bytes (the game writes them here; set up from the snapshot)
V_ID    EQU 0x5B89
V_X     EQU 0x5B8A
V_Y     EQU 0x5B8B
V_OWN   EQU 0x5B8C              ; 2 bytes: owner IX
V_KEY   EQU 0x5B8E              ; 2 bytes: graphic DE
V_COL   EQU 0x5B90              ; palette offset << 4
V_TOP   EQU 0x5B91              ; 2 bytes: signed top row of the image (outline row)
V_E     EQU 0x5B93              ; 2 bytes: current entry address
V_DIR   EQU 0x5B95              ; 4 bytes: the id's directory entry
V_R     EQU 0x5B99              ; tile row counter
V_N     EQU 0x5B9A              ; pairs used so far in this draw
V_H     EQU 0x5B9B              ; the graphic's height now
V_G     EQU 0x5B9C              ; 2 bytes: the group's graphic (the id's stored one)
V_YB    EQU 0x5B9E              ; the group's base line
V_TM    EQU 0x5B9F              ; 3 bytes: rows toggled by this plot
V_M     EQU 0x5BA2              ; 3 bytes: the entry's mask (build)
V_SB    EQU 0x5BA5              ; build: store tile rows' high byte at slot 6
V_CH    EQU 0x5BA6              ; build: flood changed
HSTK    EQU 0x5C00              ; hook stack top (grows down; variables end at 0x5BA7)

        ORG 0x2000

; ---- row hooks (the blitters' CALL sites): same register / stack effect as the original ------------
h_rowa: ld a,h
        cp 0x40
        jp c,0x9EDC             ; rows above line 0 (ROM addresses, discarded): the original
        ld a,l
        and 31
        cp 24
        jp nc,0x9EDC            ; panel (pocket icons): the original, on the ULA
        ld a,(40677)
        jr row
h_rowb: ld a,h
        cp 0x40
        jp c,0x9F21
        ld a,l
        and 31
        cp 24
        jp nc,0x9F21
        ld a,(40746)
row:    nextreg 0x07,3          ; 28 MHz for the hook's own work (every hook below too)
        push hl                 ; HL = screen, DE = graphics (as the original after EX DE,HL / PUSH DE)
        ex de,hl
        ld d,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ex (sp),hl              ; HL = screen, (SP) = graphics + 2 (the original's dead slot too)
        cp 232
        jr z,.al                ; aligned: 2 bytes
        cp 2
        jr c,.d1
        cp 4
        jr c,.d2
        cp 6
        jr c,.d3
        cp 8
        jr c,.d4
        cp 10
        jr c,.d5
        cp 12
        jr c,.d6
        xor a
        jr .l7
.d1:    xor a
        jr .l1
.d2:    xor a
        jr .l2
.d3:    xor a
        jr .l3
.d4:    xor a
        jr .l4
.d5:    xor a
        jr .l5
.d6:    xor a
        jr .l6
.l7:    srl d
        rr e
        rra
.l6:    srl d
        rr e
        rra
.l5:    srl d
        rr e
        rra
.l4:    srl d
        rr e
        rra
.l3:    srl d
        rr e
        rra
.l2:    srl d
        rr e
        rra
.l1:    srl d
        rr e
        rra                     ; D:E:A = the row shifted right by x & 7
        nextreg 0x53,SHPG
        set 5,h
        inc l
        inc l
        xor (hl)
        ld (hl),a
        dec l
        ld a,e
        xor (hl)
        ld (hl),a
        dec l
        ld a,d
        xor (hl)
        ld (hl),a
        res 5,h
        nextreg 0x53,GPG
        nextreg 0x07,0
        pop de                  ; DE = graphics + 2
        jp 0x9F03               ; the shared row advance (A, F come from it)
.al:    nextreg 0x53,SHPG
        set 5,h
        ld a,d
        xor (hl)
        ld (hl),a
        inc l
        ld a,e
        xor (hl)
        ld (hl),a
        dec l
        res 5,h
        nextreg 0x53,GPG
        nextreg 0x07,0
        pop de
        jp 0x9F03

; ---- room-line pixel 0x9C75: A = A OR old; (HL) = A; POP HL; RET ------------------------------------
h_line: nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push bc
        ld b,a                  ; the pixel bit
        nextreg 0x53,SHPG
        set 5,h
        ld c,(hl)               ; C = shadow
        res 5,h
        ld a,(hl)
        xor c                   ; the original's old byte
        or b
        ld b,a                  ; the original's new byte
        xor c
        ld (hl),a               ; ULA = new ^ shadow
        nextreg 0x53,GPG
        ld a,b
        or a                    ; OR's flags depend on the result only
        pop bc
        ld sp,(V_SP)
        nextreg 0x07,0
        pop hl
        ret

; ---- scenery drawers: [op] / LD (HL),A / INC L at 5 sites (op from V_OPk) -----------------------
h_o1:   ld (V_VAL),a
        ld a,(V_OP1)
        ld (V_OPC),a
        ld (V_SP),sp
        ld sp,HSTK
        call obj
        ld sp,(V_SP)
        inc l
        jp 0x99DA
h_o2:   ld (V_VAL),a
        ld a,(V_OP1 + 1)
        ld (V_OPC),a
        ld (V_SP),sp
        ld sp,HSTK
        call obj
        ld sp,(V_SP)
        inc l
        jp 0x9A39
h_o3:   ld (V_VAL),a
        ld a,(V_OP1 + 2)
        ld (V_OPC),a
        ld (V_SP),sp
        ld sp,HSTK
        call obj
        ld sp,(V_SP)
        inc l
        jp 0x9A7B
h_o4:   ld (V_VAL),a
        ld a,(V_OP1 + 3)
        ld (V_OPC),a
        ld (V_SP),sp
        ld sp,HSTK
        call obj
        ld sp,(V_SP)
        inc l
        jp 0x9AE0
h_o5:   ld (V_VAL),a
        ld a,(V_OP1 + 4)
        ld (V_OPC),a
        ld (V_SP),sp
        ld sp,HSTK
        call obj
        ld sp,(V_SP)
        inc l
        jp 0x9B8B

obj:    nextreg 0x07,3
        push af                 ; F = the flags before the op (kept by a NOP op)
        push bc
        push de
        nextreg 0x53,SHPG
        set 5,h
        ld d,(hl)               ; D = shadow
        res 5,h
        ld a,(hl)
        xor d
        ld e,a                  ; E = the original's old byte
        ld a,(V_OPC)
        cp 0xB6
        jr z,.or
        cp 0xAE
        jr z,.xor
        ld a,(V_VAL)            ; NOP: new = A
        xor d
        ld (hl),a
        nextreg 0x53,GPG
        pop de
        pop bc
        pop af                  ; F = before
        ld a,(V_VAL)            ; A = new (the value)
        nextreg 0x07,0
        ret
.or:    ld a,(V_VAL)
        or e
        jr .w
.xor:   ld a,(V_VAL)
        xor e
.w:     ld (V_VAL),a            ; new
        xor d
        ld (hl),a
        nextreg 0x53,GPG
        pop de
        pop bc
        pop af
        ld a,(V_VAL)
        or a                    ; OR / XOR flags depend on the result only
        nextreg 0x07,0
        ret

; ---- text printer 0xA1E6: LD (HL),A / INC DE / INC H -------------------------------------------
h_txt:  nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        ld b,a
        ld a,h
        cp 0x40
        jr c,.u
        cp 0x58
        jr nc,.u
        nextreg 0x53,SHPG
        set 5,h
        ld a,(hl)
        res 5,h
        nextreg 0x53,GPG
        xor b
        ld b,a
.u:     ld (hl),b               ; ULA = A ^ shadow
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x07,0
        inc de
        inc h
        jp 0xA1E9

; ---- play-area clear 0x8093: shadow emptied, every sprite hidden, tables reset -------------------
h_clear: ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        nextreg 0x53,SHPG
        ld hl,SH
        ld de,SH + 1
        ld bc,0x17FF
        ld (hl),0
        ldir
        ld hl,ENT
        ld de,ENT + 1
        ld bc,PAIRS + 8 - ENT - 1      ; the entries and the pair bitmap
        ld (hl),0
        ldir
        call hideall
        nextreg 0x53,GPG
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld hl,16384
        jp 0x8096

hideall: xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        ret

; ---- figure setups: the sprite bookkeeping, then the displaced LD A,(DE) / LD (2408x),A ---------
h_setm: ld (V_SP),sp
        ld sp,HSTK
        push af
        ld a,(24085)
        ld (V_ID),a
        ld a,(24086)
        ld (V_X),a
        ld a,(24087)
        ld (V_Y),a
        call fig
        pop af
        ld sp,(V_SP)
        ld a,(de)
        ld (24088),a
        jp 0x9F9B
h_seta: ld (V_SP),sp
        ld sp,HSTK
        push af
        ld a,(ix+0)
        ld (V_ID),a
        ld a,(ix+3)
        ld (V_X),a
        ld a,(ix+4)
        ld (V_Y),a
        call fig
        pop af
        ld sp,(V_SP)
        ld a,(de)
        ld (24089),a
        jp 0x9FC5

; fig: V_ID, V_X, V_Y, DE = graphic now, IX = owner. Keeps every register but F (callers save AF).
; The image of a plot is its GROUP: (the id's stored graphic G, x, base line). A plot of G itself
; toggles every row of the group, a one-row slice (the appear / death effect 0x8CD8: table entry ->
; G + 2k, height poked to 1, drawn at base - k) toggles row k: the group's row mask = the XOR of what
; the original drew there. All rows: the stored image; none: pending (still shown, as an erase); some:
; the image of those rows built now (build).
fig:    ld a,(V_X)
        cp 192
        ret nc                  ; panel (pocket icons): stays on the ULA
        ld a,(de)
        or a
        ret z                   ; height 0 draws nothing
        ld (V_H),a
        push bc
        ld a,(ix+5)             ; colour: ink + 8 * BRIGHT -> palette offset (read BEFORE slot 7 is
        ld b,a                  ; remapped: the object records 0xEA90.. are in slot 7)
        and 7
        bit 6,b
        jr z,.c
        or 8
.c:     rlca
        rlca
        rlca
        rlca
        ld (V_COL),a
        push de
        push hl
        nextreg 0x07,3
        nextreg 0x53,SHPG
        nextreg 0x57,WPG        ; from here on no game RAM at 0xE000- is read
        ld (V_KEY),de
        ld (V_OWN),ix
        call group              ; C: no image for this plot
        jr c,.out
        call flush              ; hide pending entries of other owners
        call find               ; HL = the group's entry, Z = found
        jr nz,.new
        call tog
        call show
        jr .out
.new:   call pend               ; HL = this owner's pending entry (Z) or a free one (NZ); C = none
        jr c,.out
        ld (V_E),hl
        ld (hl),1
        inc hl
        ld de,(V_G)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_X)
        ld (hl),a
        inc hl
        ld a,(V_YB)
        ld (hl),a
        inc hl
        ld de,(V_OWN)
        ld (hl),e
        inc hl
        ld (hl),d
        ld hl,(V_E)
        ld de,22
        add hl,de
        ld a,(V_DIR + 3)
        ld (hl),a               ; +22 H
        inc hl
        xor a
        ld (hl),a               ; +23..+25 mask: none yet
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ld hl,(V_E)
        call tog
        call show
.out:   nextreg 0x57,GP7
        nextreg 0x53,GPG
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        ret

; group: NC: V_DIR = the id's directory entry, V_G = its stored graphic, V_YB = the group's base line,
; V_TM = the rows this plot toggles. C: no image (no store entry, another height: not a game case).
group:  ld a,(V_ID)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,DIR
        add hl,de
        ld de,V_DIR
        ld bc,4
        ldir
        ld a,(V_DIR)
        or a
        scf
        ret z
        ld a,(V_ID)             ; V_G = GADR[id] (work page at slot 7)
        ld l,a
        ld h,0
        add hl,hl
        ld de,GADR
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_G),de
        xor a
        ld (V_TM),a
        ld (V_TM + 1),a
        ld (V_TM + 2),a
        ld hl,(V_KEY)
        or a
        sbc hl,de               ; HL = DE now - G
        jr nz,.sl
        ld a,(V_DIR + 3)        ; G itself: its height must be the store's
        ld b,a
        ld a,(V_H)
        cp b
        jr z,.full
        cp 1
        jr z,.sl                ; height 1 at G: the slice of row 0 (HL = 0)
        cp 192                  ; taller than 192: the store keeps the bottom 192 rows
        ret c
        ld a,b
        cp 192
        jr z,.full
        scf
        ret
.full:  ld a,(V_Y)
        ld (V_YB),a
        ld a,b
        call allm
        or a
        ret
.sl:    ld a,(V_H)              ; a slice: height 1, DE = G + 2k, k < H <= 24
        cp 1
        scf
        ret nz
        bit 7,h
        scf
        ret nz
        bit 0,l
        scf
        ret nz
        ld a,h
        or a
        scf
        ret nz
        ld a,(V_DIR + 3)
        cp 25
        ccf
        ret c
        ld b,a
        ld a,l
        rrca
        and 0x7F
        cp b
        ccf
        ret c
        ld c,a                  ; k
        ld a,(V_Y)
        add a,c
        ret c
        ld (V_YB),a             ; base = y + k
        ld a,c
        call setb
        or a
        ret

; allm: A = H -> V_TM |= every row (H > 24: one bit, no slices)
allm:   cp 25
        jr c,.m
        ld a,1
        ld (V_TM),a
        ret
.m:     or a
        ret z
        ld c,a
.l:     dec c
        ld a,c
        call setb
        ld a,c
        or a
        jr nz,.l
        ret

; setb: A = k (0-23) -> bit k of V_TM set (B, HL used)
setb:   ld b,a
        rrca
        rrca
        rrca
        and 3
        add a,low V_TM
        ld l,a
        ld h,high V_TM
        ld a,b
        and 7
        ld b,a
        ld a,1
        jr z,.d
.s:     add a,a
        djnz .s
.d:     or (hl)
        ld (hl),a
        ret

; mbit: A = k -> NZ if bit k of V_M is set (HL used)
mbit:   push bc
        ld b,a
        rrca
        rrca
        rrca
        and 3
        add a,low V_M
        ld l,a
        ld h,high V_M
        ld a,b
        and 7
        ld b,a
        ld a,1
        jr z,.d
.s:     add a,a
        djnz .s
.d:     and (hl)
        pop bc
        ret

; tog: HL = entry -> mask ^= V_TM; flags 3 (pending) if the mask is now empty, else 1 (HL kept)
tog:    push hl
        ld de,23
        add hl,de
        ld de,V_TM
        ld b,3
        ld c,0
.t:     ld a,(de)
        xor (hl)
        ld (hl),a
        or c
        ld c,a
        inc hl
        inc de
        djnz .t
        pop hl
        ld a,c
        or a
        ld a,3
        jr z,.p
        ld a,1
.p:     ld (hl),a
        ret

; find: HL = the used entry of group (V_G, V_X, V_YB); Z = found (DE used)
find:   ld hl,ENT
        ld b,NENT
.f:     ld a,(hl)
        and 1
        jr z,.n
        push hl
        inc hl
        ld a,(V_G)
        cp (hl)
        jr nz,.p
        inc hl
        ld a,(V_G + 1)
        cp (hl)
        jr nz,.p
        inc hl
        ld a,(V_X)
        cp (hl)
        jr nz,.p
        inc hl
        ld a,(V_YB)
        cp (hl)
.p:     pop hl
        ret z
.n:     ld de,ESZ
        add hl,de
        djnz .f
        or 1                    ; NZ
        ret

; flush: hide + free every pending entry whose owner is not V_OWN
flush:  ld hl,ENT
        ld b,NENT
.f:     ld a,(hl)
        cp 3                    ; used + pending
        jr nz,.n
        push hl
        ld de,5
        add hl,de
        ld a,(V_OWN)
        cp (hl)
        jr nz,.o
        inc hl
        ld a,(V_OWN + 1)
        cp (hl)
.o:     pop hl
        jr z,.n
        push bc
        call kill
        pop bc
.n:     ld de,ESZ
        add hl,de
        djnz .f
        ret

; pend: HL = a pending entry of V_OWN (Z), else a free entry (NZ, NC), else C (table full)
pend:   ld hl,ENT
        ld b,NENT
.f:     ld a,(hl)
        cp 3
        jr nz,.n
        push hl
        ld de,5
        add hl,de
        ld a,(V_OWN)
        cp (hl)
        jr nz,.o
        inc hl
        ld a,(V_OWN + 1)
        cp (hl)
.o:     pop hl
        ret z
.n:     ld de,ESZ
        add hl,de
        djnz .f
        ld hl,ENT
        ld b,NENT
.g:     ld a,(hl)
        or a
        jr z,.free
        ld de,ESZ
        add hl,de
        djnz .g
        scf
        ret
.free:  or 1                    ; NZ, NC
        ret

; kill: HL = entry -> its sprites hidden, its pairs freed, the entry emptied (HL kept)
kill:   push hl
        ld (hl),0
        ld de,7
        add hl,de
        ld b,(hl)               ; npairs
        ld (hl),0
        inc hl
        ld a,b
        or a
        jr z,.e
.k:     ld a,(hl)
        call hidep
        call freep
        inc hl
        djnz .k
.e:     pop hl
        ret

; hidep: A = pair q -> sprites 2q, 2q+1 hidden (A kept)
hidep:  push af
        add a,a
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        pop af
        ret

; freep: A = pair -> its bit cleared (A, HL kept)
freep:  push hl
        push bc
        call pbit
        cpl
        and (hl)
        ld (hl),a
        pop bc
        pop hl
        ret

; pbit: A = pair -> HL = its bitmap byte, A = its bit mask (B used)
pbit:   ld b,a
        rrca
        rrca
        rrca
        and 7
        add a,low PAIRS
        ld l,a
        ld h,high PAIRS
        ld a,b
        and 7
        ld b,a
        ld a,1
        jr z,.d
.s:     add a,a
        djnz .s
.d:     ret

; allocp: A = a free pair (marked used), C = none
allocp: push hl
        push bc
        ld hl,PAIRS
        ld c,0                  ; pair number of bit 0 of (HL)
.b:     ld a,(hl)
        cp 0xFF
        jr nz,.f
        inc hl
        ld a,c
        add a,8
        ld c,a
        cp 64
        jr c,.b
        pop bc
        pop hl
        scf
        ret
.f:     ld b,1
.t:     ld a,(hl)
        and b
        jr z,.g
        sla b
        inc c
        jr .t
.g:     ld a,(hl)
        or b
        ld (hl),a
        ld a,c
        pop bc
        pop hl
        or a                    ; NC
        ret

; show: HL = entry (just toggled) -> its sprites: pending = unchanged; all rows = the stored image;
; some rows = the image built from them
show:   ld a,(hl)
        and 2
        ret nz
        ld (V_E),hl
        xor a
        ld (V_TM),a
        ld (V_TM + 1),a
        ld (V_TM + 2),a
        ld a,(V_DIR + 3)
        call allm
        ld hl,(V_E)
        ld de,23
        add hl,de
        ld de,V_TM
        ld b,3
.m:     ld a,(de)
        cp (hl)
        jr nz,.part
        inc hl
        inc de
        djnz .m
        jr draw
.part:  call build
        ld a,WPG
        ld (V_DIR),a
        ld a,OBR
        ld (V_DIR + 1),a        ; tile rows 6-7 of the work page (V_DIR + 2 / + 3 stay the id's)

; draw: entry V_E, image V_DIR (page, tile-row index, tile rows, H) at V_X, base V_YB -> its sprites
draw:   ld a,(V_YB)             ; top = base - H (the outline row), signed 16 bits
        ld l,a
        ld h,0
        ld a,(V_DIR + 3)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld (V_TOP),hl
        xor a
        ld (V_R),a
        ld (V_N),a
        ld a,(V_DIR)
        or a
        jp z,.trim              ; no image (no store entry)
        nextreg 0x57,a          ; image page at slot 7
.row:   ld a,(V_R)
        ld b,a
        ld a,(V_DIR + 2)
        cp b
        jp z,.trim              ; every tile row done
        ld a,b                  ; tile top = top + 16r: visible if > -16 and < 192
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_TOP)
        add hl,de               ; HL = tile top (signed)
        bit 7,h
        jr z,.pos
        ld a,l                  ; negative: visible if >= -15
        cp 0xF1
        jr c,.next
        ld a,h
        cp 0xFF
        jr nz,.next
        jr .vis
.pos:   ld a,h
        or a
        jr nz,.next
        ld a,l
        cp 192
        jr nc,.next
.vis:   ld a,l
        add a,32
        ld (V_VAL),a            ; sprite Y (17..223)
        call slot               ; A = pair for the next tile, C = none left
        jr c,.trim
        push af
        ld bc,0x303B            ; upload: pattern slot q = 4-bit patterns 2q, 2q+1
        out (c),a
        ld a,(V_DIR + 1)        ; HL = 0xE000 + 256 * (tile-row index + r)
        ld b,a
        ld a,(V_R)
        add a,b
        add a,0xE0
        ld h,a
        ld l,0
        ld bc,0x005B
        otir
        pop af
        call sattr
.next:  ld a,(V_R)
        inc a
        ld (V_R),a
        jp .row
.trim:  nextreg 0x57,WPG        ; free the old pairs past V_N
        ld hl,(V_E)
        ld de,7
        add hl,de
        ld a,(V_N)
        ld c,(hl)               ; old npairs
        ld (hl),a
        cp c
        ret nc
        ld b,a                  ; HL -> pairs[V_N]
        ld e,a
        ld d,0
        inc hl
        add hl,de
        ld a,c
        sub b
        ld b,a
.t:     ld a,(hl)
        call hidep
        call freep
        inc hl
        djnz .t
        ret

; build: the image of the rows in V_E's mask, outlined and filled by the store's rule (ink 1; the paper
; the ink encloses and the 8-neighbours of ink / enclosed paper 2; else 0) -> 2 tile rows at OB (work
; page, slot 7). Ink from the stored image (store page at slot 6). Grid at GB: (H + 4) x 20 cells
; (image + a margin ring): 1 ink, 0 not yet reached, 3 outside (4-connected to the margin).
build:  ld hl,(V_E)
        ld de,23
        add hl,de
        ld de,V_M
        ld bc,3
        ldir
        ld a,(V_DIR)
        nextreg 0x56,a
        ld a,(V_DIR + 1)
        add a,0xC0
        ld (V_SB),a
        ld a,(V_DIR + 3)
        add a,4
        call mul20
        dec bc
        ld hl,GB
        ld (hl),3
        ld d,h
        ld e,l
        inc de
        ldir                    ; every cell outside
        ld a,(V_DIR + 3)
        ld b,a                  ; image rows r = H .. 1
.r:     ld c,1
        call celladr
        ld d,h
        ld e,l
        inc de
        ld (hl),0
        push bc
        ld bc,15
        ldir                    ; columns 1-16 not reached
        pop bc
        ld a,(V_DIR + 3)
        sub b                   ; k = H - r
        call mbit
        jr z,.rn
.cl:    call getnib             ; the stored image's pixel (r, c)
        cp 1
        jr nz,.cn
        call celladr
        ld (hl),1
.cn:    inc c
        ld a,c
        cp 17
        jr nz,.cl
.rn:    djnz .r
        nextreg 0x56,GP6
.fl:    xor a                   ; spread "outside" through 4-neighbours until nothing changes
        ld (V_CH),a
        ld a,(V_DIR + 3)
        add a,2
        call mul20              ; BC = cells of image rows 0 .. H + 1
        ld hl,GB + 20
.ff:    ld a,(hl)
        or a
        jr nz,.fn
        dec hl
        ld a,(hl)
        inc hl
        cp 3
        jr z,.fs
        push hl
        ld de,-20
        add hl,de
        ld a,(hl)
        pop hl
        cp 3
        jr nz,.fn
.fs:    ld (hl),3
        ld a,1
        ld (V_CH),a
.fn:    inc hl
        dec bc
        ld a,b
        or c
        jr nz,.ff
        dec hl
        ld a,(V_DIR + 3)
        add a,2
        call mul20
.fb:    ld a,(hl)
        or a
        jr nz,.bn
        inc hl
        ld a,(hl)
        dec hl
        cp 3
        jr z,.bs
        push hl
        ld de,20
        add hl,de
        ld a,(hl)
        pop hl
        cp 3
        jr nz,.bn
.bs:    ld (hl),3
        ld a,1
        ld (V_CH),a
.bn:    dec hl
        dec bc
        ld a,b
        or c
        jr nz,.fb
        ld a,(V_CH)
        or a
        jr nz,.fl
        ld hl,OB                ; the patterns
        ld de,OB + 1
        ld bc,511
        ld (hl),0
        ldir
        ld a,(V_DIR + 3)
        add a,2
        ld b,a
.o:     dec b                   ; image rows r = H + 1 .. 0
        ld c,0
.oc:    call celladr
        ld a,(hl)
        cp 1
        jr z,.o1
        or a
        jr z,.o2                ; enclosed paper
        push bc                 ; outside: black next to ink / enclosed paper
        ld de,-21
        add hl,de
        call nb3
        jr nz,.ob
        ld de,20
        add hl,de
        ld a,(hl)
        cp 3
        jr nz,.ob
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        cp 3
        jr nz,.ob
        add hl,de
        call nb3
        jr nz,.ob
        pop bc
        jr .on
.ob:    pop bc
.o2:    ld a,2
        jr .ow
.o1:    ld a,1
.ow:    call putnib
.on:    inc c
        ld a,c
        cp 18
        jr nz,.oc
        ld a,b
        or a
        jr nz,.o
        ret

; nb3: Z if (HL), (HL + 1), (HL + 2) are all 3 (HL kept)
nb3:    ld a,(hl)
        cp 3
        ret nz
        inc hl
        ld a,(hl)
        dec hl
        cp 3
        ret nz
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        cp 3
        ret

; mul20: A -> BC = 20 * A (HL kept)
mul20:  push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc
        ld b,h
        ld c,l
        pop hl
        ret

; celladr: B = image row r, C = column c -> HL = GB + 20 * (r + 1) + c + 1 (DE used)
celladr: ld a,b
        inc a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        ld a,c
        inc a
        add a,l
        ld l,a
        jr nc,.n
        inc h
.n:     ld de,GB
        add hl,de
        ret

; nibadr: A = base page high byte, B = image row r, C = column c -> HL = the pattern byte of pixel
; (r, c): base + 256 * (r >> 4) + 128 * (c >> 4) + 8 * (r & 15) + (c & 15) / 2 (A used)
nibadr: push de
        ld d,a
        ld a,b
        and 15
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,c
        and 15
        srl a
        add a,l
        ld l,a
        bit 4,c
        jr z,.l
        set 7,l
.l:     ld a,b
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,d
        ld h,a
        pop de
        ret

; getnib: B = r, C = c -> A = the stored image's value there (store tile rows at V_SB, slot 6)
getnib: ld a,(V_SB)
        call nibadr
        ld a,(hl)
        bit 0,c
        jr nz,.lo
        rrca
        rrca
        rrca
        rrca
.lo:    and 15
        ret

; putnib: A = value, B = r, C = c -> ORed into the built patterns at OB (DE kept)
putnib: push de
        ld d,a
        bit 0,c
        jr nz,.p
        rlca
        rlca
        rlca
        rlca
        ld d,a
.p:     ld a,OBH
        call nibadr
        ld a,(hl)
        or d
        ld (hl),a
        pop de
        ret

; slot: A = the pair for tile V_N of entry V_E (its old pair, or a new one); V_N + 1. C = none
slot:   ld hl,(V_E)
        ld de,8
        add hl,de
        ld a,(V_N)
        ld e,a
        ld d,0
        add hl,de               ; HL = &pairs[V_N]
        push hl
        ld hl,(V_E)
        ld de,7
        add hl,de
        cp (hl)                 ; below the old npairs: reuse its pair
        pop hl
        jr nc,.new
        ld a,(hl)
        jr .ok
.new:   cp MAXP
        ccf
        ret c
        call allocp
        ret c
        ld (hl),a
.ok:    push af
        ld a,(V_N)
        inc a
        ld (V_N),a
        pop af
        or a
        ret

; sattr: A = pair q, V_VAL = Y, V_X, V_COL -> sprites 2q (left) and 2q+1 (right) shown
sattr:  ld c,a
        add a,a
        nextreg 0x34,a
        ld a,(V_X)
        add a,31
        nextreg 0x35,a          ; X low (X8 = 0: x < 192)
        ld a,(V_VAL)
        nextreg 0x36,a          ; Y low
        ld a,(V_COL)
        nextreg 0x37,a          ; palette offset, no mirror, X8 0
        ld a,c
        or 0xC0
        nextreg 0x38,a          ; visible, attr 4 on, N = q
        nextreg 0x39,0x80       ; 4-bit, N6 0, Y8 0
        ld a,c
        add a,a
        inc a
        nextreg 0x34,a
        ld a,(V_X)
        add a,47
        nextreg 0x35,a
        ld a,(V_VAL)
        nextreg 0x36,a
        ld a,(V_COL)
        nextreg 0x37,a
        ld a,c
        or 0xC0
        nextreg 0x38,a
        nextreg 0x39,0xC0       ; 4-bit, N6 1
        ret
rom_end:

; ---- setup (stub bank, 0xD000): sprite palette, transparency, sprites hidden, drawer ops --------
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0          ; sprite transparency index 0
        xor a
.h:     nextreg 0x34,a          ; every sprite hidden
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        ld hl,ops
        ld de,V_OP1
        ld bc,5
        ldir
        nextreg 0x15,0x01       ; sprites on (not over the border), order SLU
        ret
ops:                            ; 5 drawer op bytes + 256 palette bytes appended by atic_atac.py
pal     EQU ops + 5

        SAVEBIN "aa_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "aa_setup.bin",0xD000,ops-0xD000
