; Commando (Elite, 128K) - hardware sprites for the player, enemy soldiers and the POW group.
; One plotter (39120 -> 39202) draws every figure: a differential "clear old frame bits, OR new
; frame" routine, IX = object descriptor (+0/+4 old/new column, +1/+5 old/new y in 2-line units,
; +2/+6 old/new frame, +3/+7 old/new graphics page, +10 row pairs, +11 flags). Figures have no
; mask, so dropping only the OR of the new frame leaves every other screen byte as the original.
; Main path (both columns < 30, inside the window): the new frame is read only through H/L of the
; active set (INC L only), so pointing H at a 256-byte zero page turns the call into erase-only.
; The main-path loops assume a column step of -1/0/+1 and a row step |dy| < row pairs: other steps
; stay on the ULA. Rows below line 191 are cut by the sprite clip window.
;
; Interrupt safety: interrupts are ENABLED at every hook site and the game's IM2 handler (64764 ->
; 25173 -> 29527) restores every register it saves and then uses IY+7 as the game's flag byte. So
; no hook ever changes IY or IX (a build check rejects any IY/IX write), the hook stack has room
; for the handler's return address, and nothing is paged. Hooks and tables live in alt ROM image 1
; (page 0x2000-0x3FFF: the game never executes ROM and reads only page 0x00), state in bank-5 RAM
; 0x5C00-0x605F (never read or written by the game once it runs).
;
; No flicker: the entry hook only notes the object's current sprite entry (V_FREED). A converted
; plot updates that entry IN PLACE at its exit (patterns double-buffered, attributes rewritten);
; every other way out of the plotter (edge 39777, top clip 40733, skips 40926 / 40930, main-path
; passthrough at 39529 / 40955) hides it there - so a figure is never invisible between frames.
;
; Solid figures: the sprite pattern is built per plot from the frame: ink (index 1, the figure's
; colour) and a yellow body fill (index 2: pixels with ink left and right on their line and above
; and below in their column), minus the pixels of scenery the figure is behind (depth).
; Depth (Dean's rule, the game's own walk boxes): behind an object when the game's walk-test point
; y + 6 is at or above the middle of the object's walk boxes; then the object's solid shape (from
; the game's own draw mask, holes filled - shapes at 0x2000) hides the figure's pixels.
; Scenery restore: the plotter's erase cuts the old frame's bits out of the scenery (the old image
; was a sprite, never on the ULA): svsave keeps those bytes at entry, svrest ORs them back.
;
; Patch sites (original bytes verified by commando.py):
;   39120  C3 22 99      JP 39202                    -> JP e_ent   (every plot: note the entry)
;   39366  7A 93 EB E1   LD A,D/SUB E/EX DE,HL/POP HL -> JP e_main  (main path: zero page)
;   39529  ED 7B 82 FD C9  LD SP,(64898) / RET        -> JP e_x     (main exit: update / hide)
;   40955  ED 7B 82 FD C9  LD SP,(64898) / RET        -> JP e_x     (main exit, bottom clip)
;   39777  D5 E5 B7      PUSH DE/PUSH HL/OR A        -> JP e_p1    (edge path: hide)
;   40733  E5 ED 73 82 FD  PUSH HL/LD (64898),SP      -> JP e_p2    (top-clip path: hide)
;   40926  DD CB 0B AE   RES 5,(IX+11)               -> JP e_p3    (skip path: hide)
;   40930  DD 7E 06      LD A,(IX+6)                 -> JP e_p4    (skip path 2: hide)
;   27468  CB 21 CB 21   SLA C / SLA C               -> JP e_rect  (rectangle clear)
;   30597  21 00 40      LD HL,16384                 -> JP e_cls   (full screen clear)
;   25630  C3 D2 69      JP 27090                    -> JP e_init  (game entry: init)
; The .nex starts in a front end (0x5D00) that redoes the BASIC loader's key wait and "INFY
; LIVES(Y/N)?" (128K BASIC pages ROM 0, absent on the Next), then enters the game at 25089.

        DEVICE ZXSPECTRUMNEXT

NENT    EQU 12                  ; sprite entries (4 sprites, 2 x 4 patterns each)
NTYPES  EQU 41
ZPH     EQU 0x5D                ; zero page 0x5D00-0x5DFF
V_SP    EQU 0x5C00              ; game SP while a hook runs
V_HL    EQU 0x5C02              ; HL after the plotter's POP HL (new frame pointer)
V_ON    EQU 0x5C04              ; 1 = this plot is converted (set at 39366, cleared at exit)
V_FREED EQU 0x5C05              ; this object's current sprite entry (0xFF none): updated or hidden
V_CNT   EQU 0x5C06              ; entries in use
V_ROW   EQU 0x5C07              ; rows (lines) of the image
V_PG    EQU 0x5C08              ; graphics page (H)
V_L0    EQU 0x5C09              ; frame offset (L)
V_R0    EQU 0x5C0A              ; rect clear: first line
V_R1    EQU 0x5C0B              ; rect clear: line after
V_C0    EQU 0x5C0C              ; rect clear: first byte column
V_C1    EQU 0x5C0D              ; rect clear: column after
V_CLK   EQU 0x5C0E              ; last pattern slot allocated (round robin)
ENT     EQU 0x5C10              ; NENT x 8: used, ix lo, ix hi, col, y, pattern slot (0xFF none),
                                ; lines, spare
STK     EQU 0x5D00              ; hook stack top (0x5C70-0x5CFF)
MASK    EQU 0x5E20              ; 32 rows x 3 bytes: scenery pixels in front of the figure
D_F64   EQU 0x5E80              ; depth temps: walk-test point y + 6 (2-line units) + 64
D_FL0   EQU 0x5E81              ; figure first line
D_FL1   EQU 0x5E82              ; figure last line (<= 191)
D_FC    EQU 0x5E83              ; figure first column
D_OBJ   EQU 0x5E84              ; object list entry (2 bytes)
D_N     EQU 0x5E86              ; list walk limit
V_SVN   EQU 0x5E87              ; scenery save: lines saved (0 = nothing to restore)
V_SVL   EQU 0x5E88              ; scenery save: first line
V_SVC   EQU 0x5E89              ; scenery save: first column
D_LN    EQU 0x5E8A              ; current line (save / restore / shape loops)
D_SC    EQU 0x5E8B              ; shape first column + 128
D_W     EQU 0x5E8C              ; shape width (bytes)
D_H     EQU 0x5E8D              ; shape height (lines)
D_RECT  EQU 0x5E8E              ; shape flags (bit 0 rectangle, bit 1 absolute column)
D_DATA  EQU 0x5E8F              ; shape bitmap (2)
D_SL    EQU 0x5E91              ; shape first line (16-bit signed)
D_CLO   EQU 0x5E93              ; overlap first column + 128
D_CHI   EQU 0x5E94              ; overlap last column + 128
D_LLO   EQU 0x5E95              ; overlap first line
D_LHI   EQU 0x5E96              ; overlap last line
D_DPTR  EQU 0x5E97              ; shape bitmap pointer for the current line (2)
D_B0    EQU 0x5E99              ; fill: the row's ink bytes
D_B1    EQU 0x5E9A
D_B2    EQU 0x5E9B
D_MNZ   EQU 0x5E9C              ; occl: 1 = an object overlaps the figure (MASK may be non-empty)
SAVE    EQU 0x5EA0              ; scenery save: up to 32 lines x 3 bytes
INKB    EQU 0x5F20              ; 32 rows x 3 bytes: the frame's ink
FILB    EQU 0x6020              ; 32 rows x 3 bytes: the body fill (MASK, INKB, FILB share the low
                                ; byte: one index, the high byte picks the buffer)
SLOTK   EQU 0x6080              ; NSLOT x 4: key of the image in pattern slot n (patterns 4n..4n+3):
                                ; graphics page, frame offset, lines, 0 - page 0xFF = no reusable
                                ; image (empty, or built with scenery in front)
NSLOT   EQU 32
DT      EQU 0x3400              ; depth table (41 x 8; Python): +0 bit 0 walk box, +5 box middle + 64,
                                ; +6/+7 variant table (8 x: shape pointer, first line offset)
SR_T    EQU 0x3200              ; smear right / left (fill)
SL_T    EQU 0x3300
PT0     EQU 0x3600              ; (ink nibble << 4 | fill nibble) -> 2 bytes of 4-bit pixels
PT1     EQU 0x3700

        ORG 0x3800
; ---- 39120: every plot. Note the object's current sprite entry; save the scenery it will cut ----
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
        ld (V_FREED),a              ; updated in place (converted) or hidden (any other exit)
        nextreg 0x07,3
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
        ld a,(V_FREED)              ; the object's own sprite entry: reused in place
        cp NENT
        jr c,.room
        ld a,(V_CNT)
        cp NENT
        jr nc,.no                   ; table full: this plot stays on the ULA
.room:
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

; ---- 39529 / 40955: main-path exit. Converted: restore H, update the sprite; else hide it ----
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
        jr .out
.pass:  push bc
        push hl
        call hidep                  ; drawn on the ULA this time: the old sprite goes now
        pop hl
        pop bc
.out:   pop af
        ld sp,(V_SP)
        ret

; ---- the plotter's other ways out: the figure is drawn on the ULA (or not at all) -> hide ----
; PHIDE: hide the pending sprite on the hook stack; every register and flag kept, nothing written
; to the game stack.
        MACRO PHIDE
        ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push hl
        call hidep
        pop hl
        pop bc
        pop af
        ld sp,(V_SP)
        ENDM
e_p1:   PHIDE                       ; 39777 edge path (column >= 30)
        push de
        push hl
        or a
        jp 39780
e_p2:   PHIDE                       ; 40733 top-clip path
        push hl
        ld (64898),sp
        jp 40738
e_p3:   PHIDE                       ; 40926 skip (both frames outside the window)
        res 5,(ix+11)
        jr e_p4r
e_p4:   PHIDE                       ; 40930 skip 2
e_p4r:  ld a,(ix+6)
        jp 40933

; hidep: hide the entry in V_FREED (if any), V_FREED = none
hidep:  ld a,(V_FREED)
        cp NENT
        ret nc
        ld b,a
        add a,a
        add a,a
        add a,a
        add a,low ENT
        ld l,a
        ld h,high ENT
        ld a,0xFF
        ld (V_FREED),a
        ld a,(hl)
        or a
        ret z
        jp hide

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
        ld hl,SLOTK                 ; pattern slots: nothing reusable
        ld b,4*NSLOT
.z3:    ld (hl),a
        inc l
        djnz .z3
        ld hl,ZPH*256               ; zero page = 0
        xor a
.z2:    ld (hl),a
        inc l
        jr nz,.z2
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
; in the object's own entry if it has one (in place: no hide, no flicker), else in a free one
show:   ld a,(ix+1)                 ; frame starts below line 191 (walked off the bottom): nothing
        cp 96                       ; to show and no entry kept (the game may reuse the descriptor
        jp nc,hidep                 ; without plotting it again: the entry would never be freed)
        ld a,(V_FREED)
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
        jr nz,.own
.first: ld b,0
        ld hl,ENT
.f:     ld a,(hl)
        or a
        jr z,.new
        ld a,l
        add a,8
        ld l,a
        inc b
        ld a,b
        cp NENT
        jr c,.f
        ret                         ; cannot happen: e_main checked for room
.new:   ld a,(V_CNT)
        inc a
        ld (V_CNT),a
        ld a,l
        add a,5
        ld e,a
        ld d,h
        ld a,0xFF
        ld (de),a                   ; fresh entry: no pattern slot
.own:   ld a,0xFF
        ld (V_FREED),a
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
        inc l
        ld a,(ix+10)
        add a,a
        ld (V_ROW),a
        ld (hl),a
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
        push bc
        call occl                   ; MASK: scenery in front of this figure
        ld a,(D_MNZ)
        or a
        jr nz,.miss
        ld hl,SLOTK                 ; unmasked: is this image in a pattern slot already?
        ld c,0
.lk:    ld a,(V_PG)
        cp (hl)
        jr nz,.l0
        inc l
        ld a,(V_L0)
        cp (hl)
        jr nz,.l1
        inc l
        ld a,(V_ROW)
        cp (hl)
        jr z,.hit
        dec l
.l1:    dec l
.l0:    ld a,l
        add a,4
        ld l,a
        inc c
        ld a,c
        cp NSLOT
        jr c,.lk
.miss:  call alloc                  ; C = a slot no shown sprite uses (this entry's own shown image
        ld a,c                      ; stays until the attributes switch)
        add a,a
        add a,a
        add a,low SLOTK
        ld l,a
        ld h,high SLOTK
        ld a,(D_MNZ)                ; key: reusable only without scenery in front
        or a
        ld a,0xFF
        jr nz,.k1
        ld a,(V_PG)
.k1:    ld (hl),a
        inc l
        ld a,(V_L0)
        ld (hl),a
        inc l
        ld a,(V_ROW)
        ld (hl),a
        push bc
        ld a,(D_MNZ)
        or a
        call z,mclr                 ; no object overlaps: MASK = 0
        call build                  ; INKB / FILB: ink, body fill, minus MASK
        pop bc
        ld a,c                      ; first pattern = 4 * slot
        add a,a
        add a,a
        rra                         ; select: pattern >> 1 | (pattern & 1) << 7 (pattern even)
        and 0x7F
        push bc
        ld bc,0x303B
        out (c),a
        ld d,0                      ; top-left: rows 0-15, bytes 0/1
        ld c,0
        call pat
        ld c,2                      ; top-right: rows 0-15, byte 2
        call pat
        ld d,16
        ld c,0
        call pat
        ld c,2
        call pat
        pop bc
.hit:   ld a,c                      ; C = slot
        pop bc
        ld c,a
        ld a,b                      ; entry +5 = slot
        add a,a
        add a,a
        add a,a
        add a,low ENT+5
        ld l,a
        ld h,high ENT
        ld (hl),c
        ld a,c                      ; E = first pattern = 4 * slot
        add a,a
        add a,a
        ld e,a
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

; mclr: MASK = 0 (B, C, D, E kept)
mclr:   ld hl,MASK
        xor a
.l:     ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld a,l
        cp low MASK+96
        ld a,0
        jr c,.l
        ret

; alloc: C = the next pattern slot (round robin) that no entry in use shows. At most NENT of
; NSLOT are in use, so one is always found.
alloc:  ld a,(V_CLK)
.try:   inc a
        and NSLOT-1
        ld c,a
        ld hl,ENT+5
        ld b,NENT
.chk:   ld a,(hl)
        cp c
        jr nz,.nx
        ld a,l
        sub 5
        ld e,a
        ld d,h
        ld a,(de)
        or a
        jr nz,.busy
.nx:    ld a,l
        add a,8
        ld l,a
        djnz .chk
        ld a,c
        ld (V_CLK),a
        ret
.busy:  ld a,c
        jr .try

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

; upload 16 rows (D = first row) of byte group C (0: bytes 0,1; 2: byte 2 + 8 clear pixels)
pat:    push de
        push bc
        ld a,d
        ld e,a
        add a,a
        add a,e
        add a,c
        add a,low INKB
        ld e,a                      ; E = buffer index of (row D, byte C)
        ld b,16
.row:   ld a,(V_ROW)
        dec a
        cp d
        jr c,.blank                 ; row >= rows: transparent
        call pix
        ld a,c
        or a
        jr nz,.half
        inc e
        call pix
        dec e
        jr .next
.half:  xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        jr .next
.blank: xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
.next:  ld a,e
        add a,3
        ld e,a
        inc d
        djnz .row
        pop bc
        pop de
        ret

; pix: buffer index E -> 8 pixels as 4 bytes of 4-bit pixels (ink 1, fill 2, else 0)
pix:    push bc
        ld h,high INKB
        ld l,e
        ld b,(hl)                   ; ink
        inc h
        ld c,(hl)                   ; fill (FILB = INKB + 0x100)
        ld a,b                      ; high nibbles
        and 0xF0
        ld l,a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        or l
        ld l,a
        ld h,high PT0
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        ld a,b                      ; low nibbles
        add a,a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,c
        and 0x0F
        or l
        ld l,a
        ld h,high PT0
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        pop bc
        ret

; occl: MASK = for every list object with a walk box that the figure is behind (walk-test point
; y + 6 at or above the box middle), its solid shape where it overlaps the figure's box.
occl:   xor a                       ; MASK is cleared when the first object overlaps (D_MNZ)
        ld (D_MNZ),a
        ld a,(64904)                ; last list entry (0: empty list)
        or a
        ret z
        ld a,(ix+1)
        add a,70                    ; walk-test point y + 6, + 64
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
        cp NTYPES
        jp nc,.next
        inc l
        ld c,(hl)                   ; C = x byte
        inc l
        ld b,(hl)                   ; B = y
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,DT
        add hl,de                   ; HL = depth table entry
        bit 0,(hl)
        jp z,.next
        push hl
        ld de,5
        add hl,de
        ld a,(hl)                   ; box middle + 64
        add a,b
        jr c,.beh                   ; y + middle + 64 >= 256 > test point + 64
        ld e,a
        ld a,(D_F64)
        cp e
        jr c,.beh
        jr z,.beh
        pop hl
        jp .next
.beh:   pop hl
        ld de,6
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = variant table
        ld a,c
        rlca
        rlca
        rlca
        and 7                       ; variant = x >> 5
        ld l,a
        add a,a
        add a,l
        ld l,a
        ld h,0
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = shape
        inc hl
        ld a,d
        or e
        jp z,.next
        ld a,(hl)                   ; first line offset (signed)
        push de
        ld l,b
        ld h,0
        add hl,hl                   ; 2y
        ld e,a
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld (D_SL),hl                ; shape first line (16-bit signed)
        pop de
        ld a,(de)
        ld (D_RECT),a
        inc de
        ld a,(de)                   ; c0
        ld l,a
        ld a,(D_RECT)
        and 2
        ld a,l
        jr nz,.abs
        ld a,c
        and 31
        add a,l
.abs:   add a,128
        ld (D_SC),a
        inc de
        ld a,(de)
        ld (D_W),a
        inc de
        ld a,(de)
        ld (D_H),a
        inc de
        ld (D_DATA),de
        ld a,(D_FC)                 ; columns: lo = max(SC, FC), hi = min(SC + W - 1, FC + 2)
        add a,128
        ld e,a
        ld a,(D_SC)
        cp e
        jr nc,.c1
        ld a,e
.c1:    ld (D_CLO),a
        ld a,(D_SC)
        ld l,a
        ld a,(D_W)
        dec a
        add a,l
        ld l,a
        ld a,e
        add a,2
        cp l
        jr c,.c2
        ld a,l
.c2:    ld (D_CHI),a
        ld l,a
        ld a,(D_CLO)
        cp l
        jr z,.c3
        jp nc,.next
.c3:    ld hl,(D_SL)                ; lines: none if SL > FL1 or SL + H - 1 < FL0
        ld a,(D_FL1)
        ld e,a
        ld d,0
        push hl
        or a
        sbc hl,de
        pop hl
        jr z,.s1
        jp p,.next
.s1:    ld a,(D_H)
        ld e,a
        ld d,0
        add hl,de
        dec hl                      ; HL = SL + H - 1
        ld a,(D_FL0)
        ld e,a
        push hl
        or a
        sbc hl,de
        pop hl
        jp m,.next
        ld a,(D_FL1)                ; hi = min(SL + H - 1, FL1)
        ld e,a
        push hl
        or a
        sbc hl,de
        pop hl
        jr c,.h1
        ld l,e
.h1:    ld a,l
        ld (D_LHI),a
        ld hl,(D_SL)                ; lo = max(SL, FL0)
        ld a,(D_FL0)
        ld e,a
        push hl
        or a
        sbc hl,de
        pop hl
        jp p,.l2
        ld l,e
.l2:    ld a,l
        ld (D_LLO),a
        ld (D_LN),a
        ld a,(D_MNZ)                ; the first overlap clears MASK
        or a
        call z,mclr
        ld a,1
        ld (D_MNZ),a
        ld a,(D_RECT)               ; bitmap pointer of the first line / column
        and 1
        jr nz,.ln
        ld l,a                      ; HL = LLO - SL (0..255)
        ld a,(D_LLO)
        ld l,a
        ld h,0
        ld de,(D_SL)
        or a
        sbc hl,de
        ld b,l
        ld hl,(D_DATA)
        ld a,(D_W)
        ld e,a
        ld d,0
        ld a,b
        or a
        jr z,.m2
.m1:    add hl,de
        djnz .m1
.m2:    ld a,(D_SC)
        ld e,a
        ld a,(D_CLO)
        sub e
        ld e,a
        ld d,0
        add hl,de
        ld (D_DPTR),hl
.ln:    ld a,(D_FL0)                ; DE = MASK + 3 * (line - FL0) + (CLO - FC)
        ld e,a
        ld a,(D_LN)
        sub e
        ld e,a
        add a,a
        add a,e
        ld e,a
        ld a,(D_FC)
        add a,128
        ld d,a
        ld a,(D_CLO)
        sub d
        add a,e
        add a,low MASK
        ld e,a
        ld d,high MASK
        ld a,(D_CHI)
        ld c,a
        ld a,(D_CLO)
        ld b,a
        ld hl,(D_DPTR)
.col:   ld a,(D_RECT)
        and 1
        ld a,0xFF
        jr nz,.cv
        ld a,(hl)
.cv:    ex de,hl
        or (hl)
        ld (hl),a
        ex de,hl
        inc hl
        inc de
        ld a,b
        cp c
        jr z,.ce
        inc b
        jr .col
.ce:    ld hl,(D_DPTR)
        ld a,(D_W)
        ld e,a
        ld d,0
        add hl,de
        ld (D_DPTR),hl
        ld a,(D_LHI)
        ld e,a
        ld a,(D_LN)
        cp e
        jr z,.next
        inc a
        ld (D_LN),a
        jr .ln
.next:  ld hl,(D_OBJ)
        ld a,(64904)
        cp l
        ret z
        ld a,(D_N)
        dec a
        ld (D_N),a
        ret z
        ld l,(hl)
        jp .obj

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

rom_end:
        ASSERT rom_end <= 0x3FEC        ; + 20-byte register block

; --- body fill (alt ROM 0x3080, after the shapes) -------------------------------------------
        ORG 0x3080
; build: INKB = the frame's rows (zig-zag stream: even row c0 c1 c2, odd row c2 c1 c0), FILB =
; body fill (ink left and right on the line, above and below in the column) & ~ink, both & ~MASK
build:  ld a,(V_PG)
        ld h,a
        ld a,(V_L0)
        ld l,a
        ld de,INKB
        ld a,(V_ROW)
        ld b,a
.r:     ld a,(hl)                   ; even row
        ld (de),a
        inc l
        inc e
        ld a,(hl)
        ld (de),a
        inc l
        inc e
        ld a,(hl)
        ld (de),a
        inc l
        inc e
        dec b
        jr z,.ab0
        inc e                       ; odd row: c2 c1 c0
        inc e
        ld a,(hl)
        ld (de),a
        inc l
        dec e
        ld a,(hl)
        ld (de),a
        inc l
        dec e
        ld a,(hl)
        ld (de),a
        inc l
        inc e
        inc e
        inc e
        djnz .r
.ab0:   ld hl,INKB                  ; FILB = OR of the ink rows above (C D E = accumulators)
        ld a,(V_ROW)
        ld b,a
        ld c,0
        ld d,c
        ld e,c
.ab:    ld a,(hl)
        inc h
        ld (hl),c
        dec h
        or c
        ld c,a
        inc l
        ld a,(hl)
        inc h
        ld (hl),d
        dec h
        or d
        ld d,a
        inc l
        ld a,(hl)
        inc h
        ld (hl),e
        dec h
        or e
        ld e,a
        inc l
        djnz .ab
        ld a,(V_ROW)                ; ... AND the OR of the ink rows below (bottom-up)
        ld b,a
        add a,a
        add a,b
        dec a
        add a,low INKB
        ld l,a
        ld h,high INKB
        ld c,0
        ld d,c
        ld e,c
.bl:    inc h                       ; byte 2
        ld a,(hl)
        and c
        ld (hl),a
        dec h
        ld a,(hl)
        or c
        ld c,a
        dec l
        inc h                       ; byte 1
        ld a,(hl)
        and d
        ld (hl),a
        dec h
        ld a,(hl)
        or d
        ld d,a
        dec l
        inc h                       ; byte 0
        ld a,(hl)
        and e
        ld (hl),a
        dec h
        ld a,(hl)
        or e
        ld e,a
        dec l
        djnz .bl
        ld de,INKB                  ; per row: AND the line span and ~ink, then both & ~MASK
        ld a,(V_ROW)
        ld b,a
.sp:    ld a,(de)
        ld (D_B0),a
        inc e
        ld a,(de)
        ld (D_B1),a
        inc e
        ld a,(de)
        ld (D_B2),a                 ; E at byte 2
        ld h,high SR_T              ; byte 2: s2 = (b0|b1) ? FF : SR[b2]; t2 = SL[b2]
        ld a,(D_B0)
        ld c,a
        ld a,(D_B1)
        or c
        ld a,0xFF
        jr nz,.s2
        ld a,(D_B2)
        ld l,a
        ld a,(hl)
.s2:    ld c,a
        ld h,high SL_T
        ld a,(D_B2)
        ld l,a
        ld a,(hl)
        and c
        ld c,a
        ld a,(D_B2)
        cpl
        and c
        ld c,a
        call fm
        dec e
        ld h,high SR_T              ; byte 1: s1 = b0 ? FF : SR[b1]; t1 = b2 ? FF : SL[b1]
        ld a,(D_B0)
        or a
        ld a,0xFF
        jr nz,.s1
        ld a,(D_B1)
        ld l,a
        ld a,(hl)
.s1:    ld c,a
        ld h,high SL_T
        ld a,(D_B2)
        or a
        ld a,0xFF
        jr nz,.t1
        ld a,(D_B1)
        ld l,a
        ld a,(hl)
.t1:    and c
        ld c,a
        ld a,(D_B1)
        cpl
        and c
        ld c,a
        call fm
        dec e
        ld h,high SR_T              ; byte 0: s0 = SR[b0]; t0 = (b1|b2) ? FF : SL[b0]
        ld a,(D_B0)
        ld l,a
        ld a,(hl)
        ld c,a
        ld h,high SL_T
        ld a,(D_B1)
        ld l,a
        ld a,(D_B2)
        or l
        ld a,0xFF
        jr nz,.t0
        ld a,(D_B0)
        ld l,a
        ld a,(hl)
.t0:    and c
        ld c,a
        ld a,(D_B0)
        cpl
        and c
        ld c,a
        call fm
        inc e
        inc e
        inc e
        dec b
        jp nz,.sp
        ret

; fm: buffer index E (D = high INKB on entry and exit), C = span & ~ink of this byte:
; fill &= C & ~mask, ink &= ~mask
fm:     ld d,high MASK
        ld a,(de)
        cpl
        ld l,a                      ; L = ~mask
        ld d,high FILB
        ld a,(de)
        and c
        and l
        ld (de),a
        ld d,high INKB
        ld a,(de)
        and l
        ld (de),a
        ret

fill_end:
        ASSERT fill_end <= 0x3200


; --- scenery save / restore (alt ROM 0x3550) -----------------------------------------------
; svsave (entry hook, the old image is a sprite): the 3 x lines bytes under the old frame;
; svrest (converted exit): OR them back - the erase only cleared old-frame bits.
        ORG 0x3550
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
        ld b,a                      ; B = lines
        ld a,(ix+1)
        add a,a
        ld (V_SVL),a
        ld e,a
        ld a,191                    ; lines on the screen: min(B, 192 - first line)
        sub e
        ret c
        inc a
        cp b
        jr nc,.n
        ld b,a
.n:     ld a,b
        ld (V_SVN),a
        ld a,e
        call scr
        ld de,SAVE
.lp:    ld a,(hl)
        ld (de),a
        inc l
        inc e
        ld a,(hl)
        ld (de),a
        inc l
        inc e
        ld a,(hl)
        ld (de),a
        inc e
        dec l
        dec l
        call down
        djnz .lp
        ret

svrest: ld a,(V_SVN)
        or a
        ret z
        ld b,a
        ld a,(V_SVC)
        ld c,a
        ld a,(V_SVL)
        call scr
        ld de,SAVE
.lp:    ld a,(de)
        or (hl)
        ld (hl),a
        inc l
        inc e
        ld a,(de)
        or (hl)
        ld (hl),a
        inc l
        inc e
        ld a,(de)
        or (hl)
        ld (hl),a
        inc e
        dec l
        dec l
        call down
        djnz .lp
        xor a
        ld (V_SVN),a
        ret

; down: HL = the screen address one line below (within the screen)
down:   inc h
        ld a,h
        and 7
        ret nz
        ld a,l
        add a,32
        ld l,a
        ret c
        ld a,h
        sub 8
        ld h,a
        ret
svr_end:
        ASSERT svr_end <= 0x3600

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
        SAVEBIN "commando_fill.bin",0x3080,fill_end-0x3080
        SAVEBIN "commando_svr.bin",0x3550,svr_end-0x3550
        SAVEBIN "commando_rom.bin",0x3800,rom_end-0x3800
        SAVEBIN "commando_setup.bin",0xD000,pal-0xD000
