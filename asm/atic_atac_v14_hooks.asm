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
; pattern store (pages STPG.., built by atic_atac_v14.py from the snapshot's graphics: ink = index 1,
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
; Patch sites (original bytes verified by atic_atac_v14.py):
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
;   0x80B4 21 00 40  LD HL,16384       -> JP h_cls      whole-screen clear (menus, via 0x80AA)
;   figure painter LD (HL),D at 0xA07D 0xA093 0xA0A6 0xA0BA 0xA0D8 0xA113 -> NOP (colour on the sprite)
;   figure painter LD (HL),E at 0xA091 0xA0AA 0xA0CD 0xA0D6 0xA0E8 0xA0F5 0xA108 0xA117 0xA132 -> NOP:
;        it reset the cells a figure left to the room colour (24090); with the D writes gone those cells
;        never took the figure's colour, so the reset only turned door / furniture cells red until the
;        furniture painter 0x9D37 repainted them (v1.2). The figure painter now writes no attribute.

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
CACHEPG EQU 0x7F00              ; last static source page in each of 64 pattern pairs (0 = invalid)
CACHERW EQU 0x7F40              ; matching 256-byte row within that page
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
V_SPEED EQU 0x5BA7              ; incoming speed, latched per figure/character setup and shared by its byte loop
V_NENT  EQU 0x5BA8              ; high-water entry count since the last clear (0..NENT)
; v1.4 pace limiter (see "pace limiter" below): 1 unit = 1/64 of a video line = 28 master cycles = 3.5 T at 3.5 MHz
V_DEBT  EQU 0x5BA9              ; 2 bytes, signed: the original's time not yet spent (> 0: the build is ahead, wait)
V_L0    EQU 0x5BAB              ; 2 bytes: video line at the start of the measured setup window
V_FR    EQU 0x5BAD              ; FRAMES (23672) low byte at the last setup: interrupts since
V_PG    EQU 0x5BAE              ; 2 bytes: polls left in a wait
; v1.6 room window (see "room window" below)
V_RW    EQU 0x5BB0              ; 1 while the room change runs at 28 MHz
V_RS    EQU 0x5BB1              ; the caller's speed, given back at h_room
V_RL    EQU 0x5BB2              ; 2 bytes: video line at the window's last reading
V_RN    EQU 0x5BB4              ; 2 bytes: lines the window has lasted
V_RC    EQU 0x5BB6              ; pixel hooks since the last reading
V_BOOST EQU 0x5BB7              ; v1.6 catch-up: 1 while the game's code runs at 28 MHz to repay the account
V_BL    EQU 0x5BB8              ; 2 bytes: video line when a setup hook left, in catch-up
HSTK    EQU 0x5C00              ; hook stack top (grows down; variables end at 0x5BBA)

        MACRO restore_speed
        push af
        ld a,(V_SPEED)
        nextreg 0x07,a
        pop af
        ENDM

        ORG 0x2000

; ---- row hooks (the blitters' CALL sites): same register / stack effect as the original ------------
h_rowa: nextreg 0x07,3
        ld a,h
        cp 0x40
        jp c,rowa_original             ; rows above line 0 (ROM addresses, discarded): the original
        ld a,l
        and 31
        cp 24
        jp nc,rowa_original            ; panel (pocket icons): the original, on the ULA
        ld a,(40677)
        jr row
h_rowb: nextreg 0x07,3
        ld a,h
        cp 0x40
        jp c,rowb_original
        ld a,l
        and 31
        cp 24
        jp nc,rowb_original
        ld a,(40746)
row:                            ; all hook work, including bounds/shift selection, at 28 MHz
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
        restore_speed
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
        restore_speed
        pop de
        jp 0x9F03

; The pocket icons / offscreen paths still run the original blitter at incoming speed.
rowa_original:
        restore_speed
        jp 0x9EDC
rowb_original:
        restore_speed
        jp 0x9F21

; ---- room-line pixel 0x9C75: A = A OR old; (HL) = A; POP HL; RET ------------------------------------
h_line:
        ld (V_SP),sp
        ld sp,HSTK
        call save_speed
        call pace_debit         ; v1.4: 39 units over the original's OR / LD / POP / RET
        db 39
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
        restore_speed
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

obj:    call save_speed
        call pace_debit         ; v1.4: 87 units over the original's op / LD (HL),A / INC L
        db 87
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
        restore_speed
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
        restore_speed
        ret

; ---- text printer 0xA1E6: LD (HL),A / INC DE / INC H -------------------------------------------
h_char: ld (V_SP),sp
        ld sp,HSTK
        call save_speed
        call pace_debit         ; v1.4: 60 units over the original's LD L,A / LD H,0
        db 60
        restore_speed
        ld sp,(V_SP)
        ld l,a                  ; displaced LD L,A / LD H,0
        ld h,0
        jp 0xA1D9

h_txt:  nextreg 0x07,3

        ld (V_SP),sp
        ld sp,HSTK
        call pace_debit         ; v1.4: 23 units over the original's LD (HL),A / INC DE / INC H
        db 23
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
        restore_speed
        inc de
        inc h
        jp 0xA1E9

; ---- play-area clear 0x8093: shadow emptied, every sprite hidden, tables reset -------------------
h_clear: ld (V_SP),sp
        ld sp,HSTK
        call save_speed
        push af
        push bc
        push de
        push hl

        ld a,(V_BOOST)
        or a
        call nz,boost_off
        ld hl,(V_SP)            ; called from the room change (return 0x9150)? v1.6: open the room window
        ld a,(hl)
        cp 0x50
        jr nz,.nw
        inc hl
        ld a,(hl)
        cp 0x91
        jr nz,.nw
        ld a,(V_SPEED)
        ld (V_RS),a
        ld a,3
        ld (V_SPEED),a          ; every hook in the window keeps 28 MHz
        ld (V_RW),a
        call pace_line
        ld (V_RL),hl
        ld hl,0
        ld (V_RN),hl
.nw:    xor a
        ld (V_NENT),a
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
        restore_speed
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
        call save_speed
        push af
        call pace_open          ; v1.4: pay what the build saved (interrupts on), start the window
        ld a,(24085)
        ld (V_ID),a
        ld a,(24086)
        ld (V_X),a
        ld a,(24087)
        ld (V_Y),a
        call fig
        push bc
        ld a,(V_X)
        ld b,a
        ld a,(V_Y)
        ld c,a
        ld a,(40677)            ; set A's shift (the JR offset the game wrote for this plot)
        call pace_close_a
        pop bc
        restore_speed
        pop af
        ld sp,(V_SP)
        ld a,(de)
        ld (24088),a
        jp 0x9F9B
h_seta: ld (V_SP),sp
        ld sp,HSTK
        call save_speed
        push af
        call pace_open          ; v1.4: pay what the build saved (interrupts on), start the window
        ld a,(ix+0)
        ld (V_ID),a
        ld a,(ix+3)
        ld (V_X),a
        ld a,(ix+4)
        ld (V_Y),a
        call fig
        push bc
        ld a,(V_X)
        ld b,a
        ld a,(V_Y)
        ld c,a
        ld a,(40746)            ; set B's shift
        call pace_close_b
        pop bc
        restore_speed
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

; allm: A = H -> complete row mask (both callers clear V_TM before this call).
; A 75-byte table replaces the repeated per-bit shifts on every erase/draw and show.
allm:   cp 25
        jr c,.m
        ld a,1
        ld (V_TM),a
        ret
.m:     ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld de,fullmasks
        add hl,de
        ld de,V_TM
        ld bc,3
        ldir
        ret
fullmasks:
        db 0,0,0
        db 1,0,0
        db 3,0,0
        db 7,0,0
        db 15,0,0
        db 31,0,0
        db 63,0,0
        db 127,0,0
        db 255,0,0
        db 255,1,0
        db 255,3,0
        db 255,7,0
        db 255,15,0
        db 255,31,0
        db 255,63,0
        db 255,127,0
        db 255,255,0
        db 255,255,1
        db 255,255,3
        db 255,255,7
        db 255,255,15
        db 255,255,31
        db 255,255,63
        db 255,255,127
        db 255,255,255

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
find:   ld a,(V_NENT)
        or a
        jr z,.missing
        ld b,a
        ld hl,ENT
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
.missing: or 1                  ; NZ
        ret

; flush: hide + free every pending entry whose owner is not V_OWN
flush:  ld a,(V_NENT)
        or a
        ret z
        ld b,a
        ld hl,ENT
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
pend:   ld a,(V_NENT)
        or a
        jr z,.unused
        ld b,a
        ld hl,ENT
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
.unused: ld hl,ENT
        ld b,NENT
.g:     ld a,(hl)
        or a
        jr z,.free
        ld de,ESZ
        add hl,de
        djnz .g
        scf
        ret
.free:  ld a,NENT
        sub b
        inc a                   ; one past this newly allocated entry
        ld c,a
        ld a,(V_NENT)
        cp c
        jr nc,.bounded
        ld a,c
        ld (V_NENT),a
.bounded: or 1                  ; NZ, NC
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
        call upload
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

; upload: A = destination pair. Immutable stored rows are uploaded only when this pair
; does not already contain that exact page + row. Free/hide/clear leave pattern RAM intact.
; The slice work buffer is mutable: invalidate its pair before every upload, including
; transitions back to an immutable stored image. Cache metadata starts zero in page 26.
upload: ld d,a
        ld l,a
        ld h,high CACHEPG
        ld a,(V_DIR + 1)
        ld c,a
        ld a,(V_R)
        add a,c
        ld e,a
        ld a,(V_DIR)
        cp WPG
        jp z,.volatile
        cp (hl)
        jr nz,.miss
        set 6,l
        ld a,e
        cp (hl)
        ret z
        res 6,l
.miss:  ld a,(V_DIR)
        ld (hl),a
        set 6,l
        ld (hl),e
.go:    ld a,d
        ld bc,0x303B
        out (c),a
        ld a,e
        add a,0xE0
        ld h,a
        ld l,0
        ld bc,0x005B
        DUP 256
        outi
        EDUP
        ret
.volatile:
        xor a
        ld (hl),a
        jp .go


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
        ld b,a                  ; image rows r = H .. 1; a row not in the mask stays outside: what the flood would make it
.r:     ld a,(V_DIR + 3)
        sub b                   ; k = H - r
        call mbit
        jr z,.rn
        push bc
        ld c,1
        call celladr            ; column 1 of the row (DE used)
        ex de,hl
        ld a,(V_SB)
        call nibadr             ; HL = its stored byte: c = 1 is the low nibble, then 7 bytes high + low, c = 16 the high nibble at + 128
        ld a,3
        ld (V_VAL),a            ; the cell for paper: 3 (outside) until the row's first ink, then 0 (not yet reached)
        ld a,(hl)
        and 15
        call inkc
        inc de
        ld b,7
.by:    inc l
        ld a,(hl)
        ld c,a
        rrca
        rrca
        rrca
        rrca
        and 15
        call inkc
        inc de
        ld a,c
        and 15
        call inkc
        inc de
        djnz .by
        ld a,l
        sub 7
        or 128
        ld l,a
        ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        and 15
        call inkc
        ex de,hl
        ld b,16                 ; back from column 16: paper after the row's last ink is outside too
.tr:    ld a,(hl)
        dec a
        jr z,.trd               ; ink
        ld (hl),3
        dec hl
        djnz .tr
.trd:
        pop bc
.rn:    djnz .r
        nextreg 0x56,GP6
.fl:    xor a                   ; spread "outside" through 4-neighbours until nothing changes
        ld (V_CH),a
        ld a,(V_DIR + 3)
        add a,2
        call mul20              ; BC = cells of image rows 0 .. H + 1
        ld hl,GB + 20
.ff:    xor a
        cpir                    ; to the next cell not yet reached
        jr nz,.fbk
        dec hl
        dec hl
        ld a,(hl)
        inc hl
        cp 3
        jr z,.fs
        ld de,-20
        add hl,de
        ld a,(hl)
        ld de,20
        add hl,de
        cp 3
        jr nz,.fn
.fs:    ld (hl),3
        ld a,1
        ld (V_CH),a
.fn:    inc hl
        ld a,b
        or c
        jr nz,.ff
.fbk:   dec hl
        ld a,(V_DIR + 3)
        add a,2
        call mul20
        xor a
        cpdr
        jr nz,.fdone            ; none left at all: done
        jr .fb1
.fb:    xor a
        cpdr
        jr nz,.fe
.fb1:
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        cp 3
        jr z,.bs
        ld de,20
        add hl,de
        ld a,(hl)
        ld de,-20
        add hl,de
        cp 3
        jr nz,.bn
.bs:    ld (hl),3
        ld a,1
        ld (V_CH),a
.bn:    dec hl
        ld a,b
        or c
        jr nz,.fb
.fe:    ld a,(V_CH)
        or a
        jr nz,.fl
.fdone: ld hl,OB                ; the patterns
        ld de,OB + 1
        ld bc,511
        ld (hl),0
        ldir
        ld a,(V_DIR + 3)
        add a,2
        ld b,a
.o:     dec b                   ; image rows r = H + 1 .. 0
        call rowlive
        jr z,.oz
        ld c,0
        call celladr
.oc:    ld a,(hl)
        cp 3
        jr nz,.oi
        ld de,-21               ; outside: black next to ink / enclosed paper (HL ends on the next cell)
        add hl,de
        ld a,(hl)
        inc hl
        and (hl)
        inc hl
        and (hl)
        ld de,18
        add hl,de
        and (hl)
        inc hl
        inc hl
        and (hl)
        add hl,de
        and (hl)
        inc hl
        and (hl)
        inc hl
        and (hl)
        ld de,-20
        add hl,de
        cp 3
        jr z,.on
        ld a,2
        jr .ow
.oi:    inc hl
        or a                    ; ink 1, enclosed paper 2
        ld a,2
        jr z,.ow
        ld a,1
.ow:    push hl
        call putnib
        pop hl
.on:    inc c
        ld a,c
        cp 18
        jr nz,.oc
.oz:    ld a,b
        or a
        jr nz,.o
        ret

; inkc: A = a stored nibble: the cell at DE: 1 for ink (Enhanced's edit: a painted nibble counts as ink) and paper from now
; on is 0, else the paper cell (V_VAL). HL, BC, DE kept.
inkc:   cp 1
        jr nz,.n
        ld a,1
        ld (de),a
        dec a
        ld (V_VAL),a
        ret
.n:     ld a,(V_VAL)
        ld (de),a
        ret

; rowlive: B = image row r -> NZ if r - 1, r or r + 1 is an image row (1 .. H) in the mask: no other row can put a pixel here. B kept.
rowlive:
        ld a,(V_DIR + 3)
        ld c,a                  ; H
        ld a,b
        cp c
        jr nc,.m0
        ld a,c                  ; r + 1: k = H - r - 1
        sub b
        dec a
        call mbit
        ret nz
.m0:    ld a,b                  ; r: k = H - r
        or a
        jr z,.m1
        cp c
        jr z,.k
        jr nc,.m1
.k:     ld a,c
        sub b
        call mbit
        ret nz
.m1:    ld a,b                  ; r - 1: k = H - r + 1
        cp 2
        jr c,.no
        ld a,c
        sub b
        inc a
        jp mbit
.no:    xor a
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
; Read the requested speed at each figure/character setup and other non-loop hook.
; Pixel rows inherit the latch from their mandatory setup. Text bytes inherit it
; from h_char at 0xA1D6 (the eight-byte loop is 0xA1E5-0xA1E9). Figure rows inherit it from
; their mandatory figure setup; the game and its ROM ISR never write NextReg 7.
; Entering at any of the four clocks is supported. No DI/EI, alternate registers or IY.
save_speed:
        push af
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld (V_SPEED),a
        pop bc
        pop af
        ret
; ---- whole-screen clear 0x80B4 (pixels 0x4000-0x57FF; from 0x80AA, the menus 0x7C29 / 0x7DA8): ----
; every figure pixel goes with it, so the same bookkeeping as h_clear, then the displaced LD HL,16384
h_cls:  ld (V_SP),sp
        ld sp,HSTK
        call save_speed
        push af
        push bc
        push de
        push hl

        ld a,(V_BOOST)
        or a
        call nz,boost_off
        xor a
        ld (V_NENT),a
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
        restore_speed
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld hl,16384
        jp 0x80B7

; ---- v1.4 pace limiter (owner, 2026-11-06: "original pace, never faster") ------------------------------
; The game has no frame lock: its pace is the time its code takes. The hooks draw faster than the original:
; a row hook saves 13-52 units against the original blitter (ULA contention included), while a setup hook
; costs more than the two instructions it displaces. Each figure setup (h_setm / h_seta) is the account:
;   + the rows this plot will draw through the row hooks x the saving of a row at this shift (CRA / CRB:
;     original minus v1.3 hook, JNext 1.2.0 means over quiet, busy and sound play, both sets)
;   + SETK: the displaced LD A,(DE) / LD (2408x),A and the figure painter's NOPs, less this hook's entry and
;     exit outside the measured window
;   + KISR for each interrupt since the last setup (the ROM ISR runs at 28 MHz when it lands in a hook)
;   - the setup window itself, measured on the video line (NR 0x1E / 0x1F)
; Hooks slower than the code they displace (text, scenery drawers, room line, character setup) take their extra time
; off it (pace_debit). V_DEBT carries the sum (> 0: the build is ahead). At the end of the setup the hook waits on the video line, at the
; caller's clock, until that time has passed: each plot then takes the original's time, in the same interrupt state
; (the game's pace depends on its masked stretches: an interrupt the original misses there delays its clock and its
; frame waits). Time the build loses (a slow setup) is carried down to UMIN, about 1.4 frames (v1.6: catch-up repays it); time it is ahead is
; carried up to UMAX. Units: 1/64 line = 28 master cycles = 3.5 T.
PNL     EQU 312                 ; lines a frame, 48K timing
UMIN    EQU -28672              ; at most 448 lines behind carried (v1.6; the catch-up repays it)
UMAX    EQU 20000               ; at most 312 lines ahead carried
WMAX    EQU 300                 ; most lines waited at one setup
KISR    EQU 44                  ; units an interrupt: 17-19% of them land at 28 MHz in v1.4 (6840 -> 1047 cycles busy, 9944 -> 1517 quiet), JNext 1.2.0
SETK    EQU -84                 ; per setup: + 6 original + 6 painter NOPs - 106 entry / exit outside the measured interval, + 18 margin (a larger SETK waits longer)

; pace_line: HL = the video line 0..PNL-1 (NR 0x1E bit 0 : NR 0x1F), read until the MSB holds. A, BC, F lost.
pace_line:
        ld bc,0x243B
.r:     ld a,0x1E
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        xor h
        and 1
        jr nz,.r
        ld a,h
        and 1
        ld h,a
        ret

; pace_store: V_DEBT = HL clamped to UMIN..UMAX (signed). A, DE, F lost.
pace_store:
        bit 7,h
        jr nz,.neg
        push hl
        ld de,UMAX + 1
        or a
        sbc hl,de
        pop hl
        jr c,.st
        ld hl,UMAX
        jr .st
.neg:   push hl
        ld de,UMIN & 0xFFFF
        or a
        sbc hl,de
        pop hl
        jr nc,.st
        ld hl,UMIN & 0xFFFF
.st:    ld (V_DEBT),hl
        ret

; pace_debit: CALL pace_debit / DB units: a hook slower than the code it displaces (text, scenery, room line, character
; setup; JNext 1.2.0 means, original against v1.3) takes its extra time off V_DEBT, so later plots wait less. Keeps
; every register.
pace_debit:
        ex (sp),hl              ; HL -> the units byte; the caller's HL on the stack
        push af
        push de
        ld e,(hl)
        inc hl
        push hl                 ; the return address, past the byte
        ld a,(V_RW)
        or a
        jr z,.acc
        ld a,(V_RC)             ; in the room window: no account, the window's clock kept
        inc a
        ld (V_RC),a
        and 15
        jr nz,.nt
        push bc
        call room_tick
        pop bc
.nt:    pop hl
        pop de
        pop af
        ex (sp),hl
        ret
.acc:   ld d,0
        ld hl,(V_DEBT)
        or a
        sbc hl,de
        call pace_store
        pop hl
        pop de
        pop af
        ex (sp),hl
        ret

; pace_open: at a setup hook's entry (28 MHz, after save_speed): interrupts since the last setup are credited (the
; game itself takes 50 off FRAMES each second: its clock), then the measured window starts (V_L0). Keeps every register.
pace_open:
        push af
        push bc
        push de
        push hl
        ld a,(V_RW)
        or a
        jr nz,.win              ; in the room window: no account
        ld a,(V_BOOST)
        or a
        call nz,boost_credit    ; the game's code since the last setup ran at 28 MHz
        ld hl,V_FR
        ld a,(23672)            ; FRAMES low byte (the ROM ISR counts every interrupt it takes)
        ld c,(hl)
        ld (hl),a
        sub c
        jr z,.go
        cp 128
        jr c,.f
        add a,50                ; the game's clock took 50 off since
.f:     cp 5
        jr c,.k
        ld a,4                  ; a long gap (menu, room build, the first setup): at most 4 counted
.k:     or a
        jr z,.go
        ld b,a
        ld hl,(V_DEBT)
        ld de,KISR
.ka:    add hl,de
        djnz .ka
        call pace_store
.go:    call pace_line
        ld (V_L0),hl
        ld a,(V_BOOST)
        or a
        jr z,.win
        ld a,(V_DEBT + 1)
        bit 7,a
        call z,boost_off        ; repaid
.win:   pop hl
        pop de
        pop bc
        pop af
        ret

; pace_close_a / _b: at a setup hook's exit (28 MHz). A = the shift's JR offset (0..12 or 232 aligned), B = x, C = y,
; (DE) = h. T = V_DEBT + the rows this plot draws through the row hooks (none for x >= 192, the pocket icons, or h = 0;
; else min(h, y + 1): rows above line 0 run the original blitter) x the set's saving at this shift + SETK. If the
; setup has taken less than T since V_L0, wait on the video line until it has (at most WMAX lines); then
; V_DEBT = T - 64 x the lines it took, clamped. Keeps DE, HL; A, BC, F lost.
pace_close_a:
        push de
        push hl
        ld hl,CRA
        jr pace_close
pace_close_b:
        push de
        push hl
        ld hl,CRB
pace_close:
        push af
        ld a,(V_RW)
        or a
        jr z,.acc
        pop af
        pop hl                  ; in the room window: no account, no wait
        pop de
        ret
.acc:   pop af
        cp 232
        jr nz,.i
        ld a,14
.i:     and 14
        rrca                    ; index 0..7 (7 = aligned)
        add a,l
        ld l,a
        jr nc,.nc
        inc h
.nc:    ld a,(hl)               ; units a row of this plot saves
        push af
        ld a,b
        cp 192
        jr nc,.none
        ld a,(de)               ; h
        or a
        jr z,.none
        ld b,a
        ld a,c
        inc a                   ; y + 1 rows on screen at most
        jr z,.none
        cp b
        jr nc,.hn
        ld b,a
.hn:    pop af
        ld e,a
        ld d,0
        ld hl,0
.cr:    add hl,de
        djnz .cr                ; HL = rows x saving
        jr .t
.none:  pop af
        ld hl,0
.t:     ld de,SETK & 0xFFFF
        add hl,de
        ld de,(V_DEBT)
        add hl,de
        ld (V_DEBT),hl          ; T: the time this setup and its rows may take, from V_L0 (signed units)
        call pace_since         ; HL = lines since V_L0
        ex de,hl
        ld hl,(V_DEBT)
        bit 7,h
        jr nz,.done             ; nothing to wait for
        ld b,6
.sh:    srl h
        rr l
        djnz .sh                ; whole lines of T
        ld bc,WMAX
        push hl
        or a
        sbc hl,bc
        pop hl
        jr c,.wok
        ld h,b
        ld l,c                  ; at most WMAX lines from V_L0 (the rest stays owed)
.wok:   push hl
        or a
        sbc hl,de
        pop hl
        jr c,.done              ; already as long as the original's
        ld b,h
        ld c,l
        push bc                 ; the line count to reach
        ld hl,2048
        ld (V_PG),hl            ; poll guard: an emulator without the line registers gives up
        ld a,(V_SPEED)
        nextreg 0x07,a          ; wait at the caller's clock: an interrupt meanwhile runs as in the original
.w:     call pace_since
        pop bc
        push bc
        push hl
        or a
        sbc hl,bc
        pop hl
        jr nc,.paid
        ld hl,(V_PG)
        dec hl
        ld (V_PG),hl
        ld a,h
        or l
        jr nz,.w
        call pace_since
.paid:  nextreg 0x07,3
        pop bc
        ex de,hl                ; DE = lines since V_L0
.done:  ex de,hl
        ld a,h
        or a
        jr nz,.huge             ; 256 lines or more: past what the account holds
        ld b,6
.m:     add hl,hl
        djnz .m                 ; 64 x lines this setup took, its wait included
        ex de,hl
        ld hl,(V_DEBT)
        or a
        sbc hl,de
        jp po,.st
.huge:  ld hl,UMIN & 0xFFFF
.st:    call pace_store
        ld a,(V_BOOST)          ; behind: the game's code at 28 MHz until the next setup (catch-up)
        or a
        jr nz,.bl
        ld de,BTHR
        ld hl,(V_DEBT)
        add hl,de
        bit 7,h
        jr z,.nb
        call boost_on
.bl:    call pace_line
        ld (V_BL),hl
.nb:    pop hl
        pop de
        ret

; pace_since: HL = lines since V_L0 (one unseen wrap allowed). A, BC, F lost; DE kept.
pace_since:
        call pace_line
        ld bc,(V_L0)
        or a
        sbc hl,bc
        ret nc
        ld bc,PNL
        add hl,bc
        ret

; ---- v1.6 catch-up: time the account is behind (a hook slower than what it displaced: an image built for the appear effect,
; scenery, text) is won back by running the game's own code at 7 MHz from one setup to the next, and crediting that gap x
; (KB - 1) at the next setup, until the account is level. Nothing else changes: no plot, no wait. A gap can win more than was owed: that
; is carried as ahead and the next setups wait it out. The beeper keeps its clock: while catch-up is on, the first bytes of the
; two sound routines (0xA3AA tone, 0xA46E noise) are JPs to h_beep / h_noise, which end catch-up, give the speed back and run the
; routine; off, they are the game's own bytes, so sound never pays a cycle for this. A one-call tone (C = 1, a sweep's step: the
; code between its tones is part of the sound) stays at the caller's clock; after any other sound catch-up goes on.
; KBOOST = (KB - 1) x 4 (a line at 7 MHz stands for 2 at 3.5, JNext). BTHR: catch-up starts 64 lines behind.
KBOOST  EQU 4
BCLK    EQU 1                   ; the clock in catch-up
BTHR    EQU 4096                ; 64 lines behind

; boost_credit: V_DEBT += lines since V_BL x KBOOST x 16. AF, BC, DE, HL lost.
boost_credit:
        call pace_line
        ld bc,(V_BL)
        or a
        sbc hl,bc
        jr nc,.p
        ld bc,PNL
        add hl,bc
.p:     ld a,h
        or a
        jr z,.m
        ld l,255                ; a gap past 255 lines counts as 255
.m:     ld d,l
        ld e,KBOOST
        mul d,e
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_DEBT)
        or a
        adc hl,de
        jp po,pace_store        ; a gap can win more than was owed: carried as ahead, the next setups wait it out
        ld hl,UMAX
        jp pace_store

; boost_on / boost_off: AF, HL lost. V_SPEED is what the hook gives back on leaving.
boost_on:
        ld a,(V_SPEED)
        ld (V_RS),a
        ld a,BCLK
        ld (V_SPEED),a
        ld (V_BOOST),a
        ld a,0xC3
        ld (0xA3AA),a
        ld (0xA46E),a
        ld hl,h_beep
        ld (0xA3AB),hl
        ld hl,h_noise
        ld (0xA46F),hl
        ret
boost_off:
        xor a
        ld (V_BOOST),a
        ld a,(V_RS)
        ld (V_SPEED),a
        ld a,0x3E               ; 0xA3AA: LD A,0x10 / OUT ..
        ld (0xA3AA),a
        ld hl,0xD310
        ld (0xA3AB),hl
        ld a,0x01               ; 0xA46E: LD BC,0x0830
        ld (0xA46E),a
        ld hl,0x0830
        ld (0xA46F),hl
        ret

h_beep: ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call boost_credit
        call boost_off
        ld a,(V_SPEED)
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,c                  ; (the routine sets A first)
        cp 1                    ; C = 1: a sweep (0xA3A8 from its loop): the code between its tones keeps its clock
        jp z,0xA3AA
        call 0xA3AA
        jr boost_back
h_noise:
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call boost_credit
        call boost_off
        ld a,(V_SPEED)
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        call 0xA46E
; back from a sound: catch-up goes on if the account is still behind. Keeps every register.
boost_back:
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld de,BTHR
        ld hl,(V_DEBT)
        add hl,de
        bit 7,h
        jr z,.n
        call boost_on
        nextreg 0x07,BCLK
        call pace_line
        ld (V_BL),hl
.n:     pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ret

; ---- v1.6 room window (owner's rule 2026-11-07: within 2%, never slower) ---------------------------------------
; A room change (0x914D clear, 0x9150 room drawing, 0x9153 panel, 0x9156 pocket icons) took 7 to 10 frames more than the
; original's 16 to 25: every room-line pixel and scenery byte goes through a hook slower than the code it displaces,
; and the account (UMIN) can carry at most 192 lines of that. So the whole sequence, the game's code and the hooks,
; now runs at 28 MHz: h_clear (return 0x9150) opens the window, h_room (0x9159, the CALL that queues the room's sound)
; closes it, waits at the caller's clock until the original's time has passed, less anything the account owes or plus anything
; it is ahead, and gives the speed back, then catch-up runs the first pass (its doors and furniture go through the
; slow scenery hooks). Nothing plays and no key is read in the window.
;   lines x KROOM / 16 - ROFF: fit over 107 rooms, JNext: original = 3.41 x window - 0.78 frame, largest error 0.35 frame.
KROOM   EQU 55
ROFF    EQU 280
RCAP    EQU 11232               ; most lines a room change's target can reach (36 frames; the longest measured is 25)

; room_tick: V_RN += lines since the last reading. AF, BC, HL lost.
room_tick:
        call pace_line
        ld bc,(V_RL)
        ld (V_RL),hl
        or a
        sbc hl,bc
        jr nc,.p
        ld bc,PNL
        add hl,bc
.p:     ld bc,(V_RN)
        add hl,bc
        ld (V_RN),hl
        ret

h_room: ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld a,(V_RW)
        or a
        jp z,.out
        call room_tick
        ld hl,(V_RN)
        ld d,h
        ld e,KROOM
        mul d,e
        ld b,d
        ld c,e                  ; BC = high x K
        ld d,l
        ld e,KROOM
        mul d,e                 ; DE = low x K
        ld l,e
        ld a,d
        add a,c
        ld h,a
        ld a,b
        adc a,0                 ; A:H:L = lines x K
        ld b,4
.q:     srl a
        rr h
        rr l
        djnz .q                 ; / 16
        or a
        jr nz,.cap
        ld de,RCAP
        or a
        sbc hl,de
        add hl,de
        jr c,.ok
.cap:   ld hl,RCAP
.ok:    ld de,ROFF
        or a
        sbc hl,de
        jr nc,.of
        ld hl,0
.of:    ld de,(V_DEBT)          ; the account: its sign is what the plots owe or are owed, repaid here
        ld b,6
.sd:    sra d
        rr e
        djnz .sd
        add hl,de
        bit 7,h
        jr z,.tg
        ld hl,0
.tg:    ld b,h
        ld c,l
        push bc                 ; the line count to reach
        ld hl,0
        ld (V_DEBT),hl
        ld (V_PG),hl            ; poll guard: 65,536 polls, then give up
        xor a
        ld (V_RW),a             ; closed
        ld a,(V_RS)
        ld (V_SPEED),a
        nextreg 0x07,a          ; the wait, and the sound after it, at the caller's clock
.w:     call room_tick
        pop bc
        push bc
        ld hl,(V_RN)
        or a
        sbc hl,bc
        jr nc,.paid
        ld hl,(V_PG)
        dec hl
        ld (V_PG),hl
        ld a,h
        or l
        jr nz,.w
        ld hl,0
.paid:  pop bc
        ld a,h                  ; HL = lines past the target: carried as behind
        or a
        jr nz,.far
        ld a,l
        cp 192
        jr nc,.far
        ld b,6
.m:     add hl,hl
        djnz .m
        ld de,0
        ex de,hl
        or a
        sbc hl,de
        jr .st
.far:   ld hl,UMIN & 0xFFFF
.st:    ld (V_DEBT),hl
        ld a,(23672)            ; the window's interrupts are the window's: none for the next setup to credit
        ld (V_FR),a
        call boost_on           ; the first pass draws the room's doors and furniture through the slow scenery hooks
        nextreg 0x07,BCLK
        call pace_line
        ld (V_BL),hl
.out:   pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        jp 0xA403

; a row's saving in units, by shift: JR offset 0, 2, .. 12 (7..1 pixel pairs shifted), then aligned (232)
CRA:    db 47, 43, 35, 31, 24, 19, 13, 18      ; set A (0x9EDC, the erase of a move)
CRB:    db 52, 48, 39, 35, 28, 23, 17, 19      ; set B (0x9F21, the draw)
        db 0, 0                                ; (keeps the static check's decoder aligned after the data)

        IFDEF QAOP
; ---- "QAOP + Space" toggle (asm/atic_atac_v13_qaop.asm defines QAOP; the base assembles without it) ----
; The game's keyboard read 0x93CD (reached from 0x93BE only when (24064) & 6 = 0, keyboard chosen):
; LD A,0xFB / OUT (0xFD),A / IN A,(0xFE), then 0x93D3 turns the QWERT byte into the action byte
; (bit 0 right, 1 left, 2 down, 3 up, 4 fire; Kempston's order): Q left, W right, E down, R up, T fire.
; h_qaop makes that QWERT byte from Q A O P Space instead, active low as the port gives it:
;   bit 0 (Q: left)  <- O   0xDFFE bit 1        bit 3 (R: up)   <- Q      0xFBFE bit 0
;   bit 1 (W: right) <- P   0xDFFE bit 0        bit 4 (T: fire) <- Space  0x7FFE bit 0
;   bit 2 (E: down)  <- A   0xFDFE bit 0        bits 5-7        <- 0xFBFE's own (as the original's)
; and goes on at 0x93D3 (LD C,A), so C, E, A and F end as the original's for that byte. Interrupts
; are off here (0x9489's DI); the caller's clock is kept; B is kept on the game stack (2 bytes).
h_qaop: ld a,0xFB
        out (0xFD),a            ; as the original (port 0xFBFD)
        push bc
        in a,(0xFE)             ; 0xFBFE
        ld c,a
        and 0xE0
        ld b,a                  ; bits 5-7
        ld a,c
        rlca
        rlca
        rlca
        and 0x08                ; Q -> bit 3 (up)
        or b
        ld b,a
        ld a,0xFD
        in a,(0xFE)             ; 0xFDFE
        rlca
        rlca
        and 0x04                ; A -> bit 2 (down)
        or b
        ld b,a
        ld a,0xDF
        in a,(0xFE)             ; 0xDFFE
        ld c,a
        rlca
        and 0x02                ; P -> bit 1 (right)
        or b
        ld b,a
        ld a,c
        rrca
        and 0x01                ; O -> bit 0 (left)
        or b
        ld b,a
        ld a,0x7F
        in a,(0xFE)             ; 0x7FFE
        rlca
        rlca
        rlca
        rlca
        and 0x10                ; Space -> bit 4 (fire)
        or b
        pop bc
        jp 0x93D3

; The pause check 0x9489: DI / LD A,0x7E / OUT (0xFD),A / IN A,(0xFE) / BIT 0,A / RET NZ ...: Space or
; Caps Shift (bit 0 of rows 0xFEFE and 0x7FFE together) with no other key of those rows pauses. With
; Space as fire that would pause at every shot, so with the keyboard chosen bit 0 is Caps Shift's alone
; (row 0xFEFE); bits 1-7 are the original read's. A joystick reads exactly as the original. Resuming
; (0x9497-) is the game's own: Caps Shift or Space. F is kept (BIT 0,A leaves the carry).
h_pause:
        push af
        ld a,(0x5E00)
        and 6
        jr nz,.joy
        push bc
        ld a,0x7E
        out (0xFD),a            ; as the original (port 0x7EFD)
        in a,(0xFE)             ; 0x7EFE
        and 0xFE
        ld c,a
        ld a,0xFE
        in a,(0xFE)             ; 0xFEFE: Caps Shift in bit 0
        and 0x01
        or c
        pop bc
        jr .out
.joy:   ld a,0x7E
        out (0xFD),a
        in a,(0xFE)             ; 0x7EFE, as the original
.out:   ld (V_VAL),a
        pop af
        ld a,(V_VAL)
        jp 0x9490
        ENDIF

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
ops:                            ; 5 drawer op bytes + 256 palette bytes appended by atic_atac_v14.py
pal     EQU ops + 5

; ---- Loading screen stub (nexclash-patch build/all2/add_screen.py STUB, bank 23; ported 2026-11-04 from asm/jetpac_v11_hooks.asm) ----
; atic_atac_v13.loading_nex() makes bank 23 (pages 46, 47; entry bank, PC 0xC000): ld_head at 0xC000, zero
; to 0xC200, the game's own bank 5 screen bytes (6912), zero to 0xFFD0, ld_tail. On entry .nexload has
; left slots 2-5 = 10,11,4,5, slots 6-7 = this bank, DI, SP = 0xDFFE and 0xC000 pushed just below SP.
; No byte outside this bank differs when it leaves; its last instruction puts page 5 back, so the next
; fetch is 0xC000 (bank 10) with no trampoline in RAM. The border stays as the loader set it.
        MODULE ldscr
SCREEN  EQU 0x4000
SCRLEN  EQU 6912
REGS    EQU 0xFE00          ; register stack, page 47; below it the stub's call stack
SEL     EQU 0xFE02          ; port 0x243B as found
TIMEOUT EQU 250             ; frames: 5 s at 50 Hz
CAP     EQU 250             ; most frames to wait for a held key to go
CLEAR   EQU 3               ; frames with no key before leaving
LINE    EQU 192             ; first line below the picture
PICTURE EQU 0xC200          ; the game's own screen bytes (atic_atac_v13.loading_nex)

        ORG 0xC000
start:  di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,0x243B
        in      a,(c)
        ld      (SEL),a
; A key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the game doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,PICTURE
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        ld      bc,0x243B
        ld      a,(SEL)
        out     (c),a
        nextreg 0x55,47
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,0x243B
        ld      a,0x1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,(0xfe)
        cpl
        and     0x1f
        or      e
        ld      e,a
        ld      a,d
        ret
head_end:
        ASSERT  head_end <= PICTURE

        ORG 0xFFD0
        DISP    0xBFD0
; Runs from page 47 at slot 5. The entry bank's top bytes get what the loader's stack left there.
final:  nextreg 0x56,20
        nextreg 0x57,21
        ld      hl,0xC000
        ld      (0xDFFC),hl
        ld      sp,REGS-0x4000-12
        pop     iy
        pop     ix
        ld      hl,(0xBFFF)     ; MEMPTR = 0xC000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,0xDFFE
        ds      0xBFFC-$
        nextreg 0x55,5          ; falls through to 0xC000, the entry bank
        ASSERT  $ == 0xC000
        ENT
        ENDMODULE

        SAVEBIN "aa_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "aa_setup.bin",0xD000,ops-0xD000
        SAVEBIN "aa_ldhead.bin",0xC000,ldscr.head_end-0xC000
        SAVEBIN "aa_ldtail.bin",0xFFD0,0x30
