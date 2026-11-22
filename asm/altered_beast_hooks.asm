; Altered Beast (Activision 1989, 128K) - every figure of the cell plotter becomes 4-bit hardware
; sprites; scenery, HUD and text stay on the ULA. Facts: games/altered_beast.md.
;
; The game composes each game frame in a back buffer (pixels at (23332), attributes at (23334); 32
; bytes a line, base moves one byte per scroll step). Figures are cell aligned: a record is a flag
; byte (0 = empty cell, 1 byte long) or flag + 8 graphics bytes + attribute. Main loop:
;   HALT / CALL 0x60EB blit buffer -> screen / CALL 0x6DE4 buffer := clean copy ((23954), (23956)) /
;   logic and plots into the buffer.
; Method - the game's own code runs unchanged, only the blit's source changes:
;   0xD036 / 0xCEEB  masked plot loops (stored / mirrored): log the figure; the plot runs as the original
;   0xD1D8           opaque plot (graves): log the figure; the plot runs as the original
;   0xAE40           CALL 0x60EB -> e_bl: the blit runs from the CLEAN copy, so the ULA never shows a
;                    figure; registers and pointers restored; then the commit builds sprites from the log.
; The buffer keeps the figures exactly as in the original, so no game memory differs but the screen.
; Hook code: alt ROM image 0 (the game runs with ROM 0 selected) and 1 (stub), 0x2000 up, nothing at
; 0x3D00-. Page H = Next page 26 at MMU slot 4 while a hook runs; in play slot 4 holds only the
; buffer / clean copy, which no hook reads. Interrupts stay ON in every hook.
;
; Patch sites (original bytes verified by altered_beast.py):
;   0xD036 3A 83 5D  LD A,(23939)  -> JP e_pn
;   0xCEEB 3A 83 5D  LD A,(23939)  -> JP e_pm
;   0xD1D8 CD 10 D2  CALL 0xD210   -> CALL e_op
;   0xAE40 CD EB 60  CALL 0x60EB   -> CALL e_bl
;   0xAFED 2A 26 5B  LD HL,(23334) -> JP e_fxa   end of the level: the two routines that write attributes
;   0xB046 2A 26 5B  LD HL,(23334) -> JP e_fxb   straight into the buffer (a yellow curtain, rows 0-16, columns
;                                                21-28): flag it; e_bl lets the blit show that rectangle

        DEVICE ZXSPECTRUMNEXT

HPG     EQU 26                  ; hook page, MMU slot 4 while a hook runs
GP4     EQU 4                   ; the game's page at slot 4 (bank 2 low)
GP5     EQU 5                   ; the game's page at slot 5 (bank 2 high)
STORE   EQU 28                  ; colour store: pages 28-67 (8-byte entries for 0x6000-0xFFFF)
MAXLOG  EQU 32
NCE     EQU 32                  ; cache entries
ESZ     EQU 64                  ; bytes per cache entry
MAXPAT  EQU 48                  ; patterns per entry
MAXSPR  EQU 128

BLIT    EQU 0x60EB
PIX     EQU 23332               ; buffer pixel base
ATT     EQU 23334               ; buffer attribute base
CPIX    EQU 23954               ; clean pixel base
CATT    EQU 23956               ; clean attribute base
PTR     EQU 23296               ; plot: buffer address of the first cell
W_      EQU 23940
H_      EQU 23939
YC      EQU 23938
LIM     EQU 53316               ; operand of the row limit CP (self-modified: 60, 57, 56)
FLG     EQU 23325
MASKT   EQU 0x69                ; the game's tables: byte -> mask, bit reverse
REVT    EQU 0x6A

; ---- page H at 0x8000 ----
V_N     EQU 0x8000              ; figures logged since the last commit
V_PREV  EQU 0x8001              ; sprites shown by the last commit
V_NS    EQU 0x8002              ; sprites in SPRTAB
V_COL   EQU 0x8003              ; 1 = the colour store has entries (Python / recolour)
V_SP    EQU 0x8004
V_RR    EQU 0x8006              ; cache round robin
V_NFREE EQU 0x8007              ; free patterns on the FREE stack
V_DROP  EQU 0x8008              ; figures dropped (diagnostic)
V_TEAR  EQU 0x8009              ; shown entries evicted before the attribute upload (diagnostic)
V_PTR   EQU 0x800A
V_HH    EQU 0x800C
V_KM    EQU 0x800D              ; kind (0 stored, 1 mirrored, 2 opaque) | mode << 4
V_DE    EQU 0x800E              ; stream
V_W     EQU 0x8010
V_H     EQU 0x8011
V_XL    EQU 0x8012              ; leftmost column (signed)
V_ROW0  EQU 0x8013              ; screen row of the first visible row
V_R0    EQU 0x8014              ; first visible stream row
V_NR    EQU 0x8015              ; visible rows
V_YC    EQU 0x8016
V_LM    EQU 0x8017
V_TW    EQU 0x8018
V_TH    EQU 0x8019
V_NT    EQU 0x801A
V_TX    EQU 0x801B
V_TY    EQU 0x801C
V_P     EQU 0x801D
V_OR    EQU 0x801E
V_E     EQU 0x8020              ; (2) current cache entry
V_LP    EQU 0x8022              ; (2) log pointer
V_LI    EQU 0x8024
V_SX    EQU 0x8026              ; (2)
V_CP0   EQU 0x8028              ; (2) left cell: graphics of this line (0 = none)
V_CP1   EQU 0x802A              ; (2) right cell
V_I0    EQU 0x802C              ; left cell: ink byte, paper byte, ink nibble, paper nibble
V_P0    EQU 0x802D
V_N0    EQU 0x802E
V_Q0    EQU 0x802F
V_I1    EQU 0x8030
V_P1    EQU 0x8031
V_N1    EQU 0x8032
V_Q1    EQU 0x8033
V_ST    EQU 0x8034              ; stride between a cell's lines (1, or W for the opaque kind)
V_KIND  EQU 0x8035
V_MODE  EQU 0x8036
V_INK   EQU 0x8037              ; nibbles of the byte being drawn
V_PAP   EQU 0x8038
V_G     EQU 0x8039              ; screen order graphic / mask bytes
V_M     EQU 0x803A
V_TM    EQU 0x803B
V_LN    EQU 0x803C              ; line counter
V_CK    EQU 0x803D
V_FOUND EQU 0x803E              ; (2) idle: the entry found
V_KEY   EQU 0x8040              ; 11-byte key: stream (2), km, W, H, r0, nr, 4 stream bytes
V_NIB   EQU 0x8050              ; 8 colour nibbles
V_FX    EQU 0x8060              ; (2) non-zero = an effect wrote attributes into the buffer this game frame
LOG     EQU 0x8100              ; MAXLOG x 10: km, DE (2), W, H, x, y (from the pointer), yc, limit, 0
CE      EQU 0x8300              ; NCE x 64: +0 flags (7 valid, 0 used, 1 shown), +1 key (11), +12 n,
                                ; +13 patterns (48 at most; 0xFF = empty tile)
FREE    EQU 0x8B00              ; free pattern stack (128)
SPRTAB  EQU 0x8C00              ; 128 x 5
CELLS   EQU 0x8E80              ; visible rows x W: graphics address of each stream cell (0 = empty)
HSTK    EQU 0x9F00

TI0     EQU 0x2000              ; index graphic nibble << 4 | mask nibble: first pixel pair, ink mask
TI1     EQU 0x2100              ; second pair, ink mask
TP0     EQU 0x2200              ; first pair, paper mask
TP1     EQU 0x2300              ; second pair, paper mask

; 0x2000-0x23FF: written by altered_beast.py
        ORG 0x2400

; ---- the two masked plot loops: log the figure, the displaced LD A,(23939), back ----
        MACRO PLOTLOG kind, back
        nextreg 0x07,3
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push hl
        ld hl,(PTR)
        ld (V_PTR),hl
        ld a,(H_)
        ld (V_HH),a
        ld a,kind
        call logp
        pop hl
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x54,GP4
        nextreg 0x07,0
        ld a,(H_)
        jp back
        ENDM

e_pn:   PLOTLOG 0, 0xD039
e_pm:   PLOTLOG 1, 0xCEEE

; ---- opaque plot: HL = buffer address, B = lines, DE = data ----
e_op:   nextreg 0x07,3
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push hl
        ld (V_PTR),hl
        ld a,b
        ld (V_HH),a
        ld a,2
        call logp
        pop hl
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x54,GP4
        nextreg 0x07,0
        jp 0xD210

; logp: A = kind; keeps DE, IX, IY. Mode as the plot's attribute code decides it (0xD06B / 0xCF28):
; type 6 with (IX+26) -> attribute 7; type 64 with (23325) -> attributes 4 and 5 swapped
logp:   ld c,a
        ld a,(ix+23)
        cp 6
        jr nz,.n6
        ld a,(ix+26)
        or a
        jr z,.m0
        ld a,0x10
        jr .mm
.n6:    cp 64
        jr nz,.m0
        ld a,(FLG)
        or a
        jr z,.m0
        ld a,0x20
        jr .mm
.m0:    xor a
.mm:    or c
        ld c,a                      ; C = km
        ld a,(V_N)
        cp MAXLOG
        jr nc,.full
        ld b,a
        inc a
        ld (V_N),a
        ld a,c
        ld (V_KM),a
        ld l,b
        ld h,0
        add hl,hl
        ld c,l
        ld b,h
        add hl,hl
        add hl,hl
        add hl,bc                   ; 10 * index
        ld bc,LOG
        add hl,bc
        ld a,(V_KM)
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(W_)
        ld (hl),a
        inc hl
        ld a,(V_HH)
        ld (hl),a
        inc hl
        push de
        ex de,hl                    ; DE = log pointer
        ld hl,(V_PTR)               ; offset from the buffer base + 128: H = row, L - 128 = column
        ld bc,(PIX)
        or a
        sbc hl,bc
        ld bc,128
        add hl,bc
        ld a,l
        sub 128
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,(YC)
        ld (de),a
        inc de
        ld a,(LIM)
        ld (de),a
        pop de
        ret
.full:  ld hl,V_DROP
        inc (hl)
        ret

; ---- CALL 0x60EB: the blit runs from the clean copy, everything put back, then the commit ----
e_bl:   call fxswap
        ld hl,(PIX)
        push hl
        ld hl,(ATT)
        push hl
        ld hl,(CPIX)
neg_pix:ld (PIX),hl
        ld hl,(CATT)
neg_att:ld (ATT),hl
        call BLIT
        push af
        push de
        push hl
        ld hl,6
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = the buffer's attribute base
        ld hl,(ATT)
        or a
        sbc hl,de                   ; HL = clean - buffer
        ld (ATT),de
        ex de,hl
        ld hl,(PTR)                 ; the blit leaves its attribute row pointer here
        or a
        sbc hl,de
        ld (PTR),hl
        pop hl
        or a
        sbc hl,de                   ; HL as the original blit leaves it
        pop de
        pop af                      ; bits 3 and 5 of F differ: the next LDI overwrites them
        inc sp
        inc sp
        ex (sp),hl
        ld (PIX),hl
        pop hl
        nextreg 0x07,3
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call effect
        call commit
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x54,GP4
        nextreg 0x07,0
        ret

; ---- the two attribute effects: only the flag; every register as it was ----
e_fxa:  nextreg 0x54,HPG
neg_fx: ld (V_FX),sp                ; SP is never 0
        nextreg 0x54,GP4
        ld hl,(ATT)
        jp 0xAFF0
e_fxb:  nextreg 0x54,HPG
        ld (V_FX),sp
        nextreg 0x54,GP4
        ld hl,(ATT)
        jp 0xB049

;   fxswap (before the blit) and effect (after it): while a level-end effect runs, the rectangle it writes is
;   exchanged between the buffer's and the clean attributes for the time of the blit, so the blit shows it
;   with no gap, and the clean copy is whole again when the game continues
fxswap: push bc
        nextreg 0x07,3
        nextreg 0x54,HPG
        ld hl,(V_FX)
        ld a,h
        or l
        call nz,swaprect
        nextreg 0x54,GP4
        nextreg 0x07,0
        pop bc
        ret

effect: ld hl,(V_FX)
        ld a,h
        or l
        ret z
        ld hl,0
        ld (V_FX),hl
swaprect:
        ld hl,(CATT)
        ld de,21
        add hl,de
        ex de,hl
        ld hl,(ATT)
        ld bc,21
        add hl,bc
        ld b,17
.r:     push bc
        ld b,8
.c:     ld a,(de)
        ld c,(hl)
        ld (hl),a
        ld a,c
        ld (de),a
        inc hl
        inc de
        djnz .c
        ld bc,24
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        pop bc
        djnz .r
        ret

; =====================================================================================
; commit: every logged figure -> sprites (SPRTAB), then the attribute upload; cache flags aged
commit: xor a
        ld (V_NS),a
        ld (V_LI),a
        ld hl,LOG
        ld (V_LP),hl
.part:  ld a,(V_LI)
        ld hl,V_N
        cp (hl)
        jr nc,.upl
        inc a
        ld (V_LI),a
        call part
        ld hl,(V_LP)
        ld de,10
        add hl,de
        ld (V_LP),hl
        jr .part
.upl:   xor a
        ld (V_N),a
        ld a,(V_NS)
        ld d,a
        ld e,0
        ld hl,SPRTAB
.c:     ld a,e
        cp d
        jr nc,.hide
        nextreg 0x34,a
        ld a,(hl)
        inc hl
        nextreg 0x35,a
        ld a,(hl)
        inc hl
        nextreg 0x36,a
        ld a,(hl)
        inc hl
        nextreg 0x37,a
        ld a,(hl)
        inc hl
        nextreg 0x38,a
        ld a,(hl)
        inc hl
        nextreg 0x39,a
        inc e
        jr .c
.hide:  ld a,(V_PREV)
        ld h,a
.h:     ld a,e
        cp h
        jr nc,.age
        nextreg 0x34,a
        nextreg 0x38,0
        inc e
        jr .h
.age:   ld a,d
        ld (V_PREV),a
        ld hl,CE
        ld de,ESZ
        ld b,NCE
.f:     ld a,(hl)
        and 0x81                    ; valid + used -> valid + shown
        bit 0,a
        jr z,.f1
        xor 3
.f1:    ld (hl),a
        add hl,de
        djnz .f
        ret

; part: the log entry at V_LP -> geometry, cache entry (built on a miss), sprites
part:   ld hl,(V_LP)
        ld a,(hl)
        ld (V_KM),a
        ld c,a
        and 15
        ld (V_KIND),a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (V_MODE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_DE),de
        inc hl
        ld a,(hl)
        ld (V_W),a
        inc hl
        ld a,(hl)
        ld (V_H),a
        inc hl
        ld a,(hl)
        ld (V_XL),a                 ; pointer column
        inc hl
        ld a,(hl)
        ld (V_ROW0),a               ; pointer row
        inc hl
        ld a,(hl)
        ld (V_YC),a
        inc hl
        ld a,(hl)
        ld (V_LM),a
        ld a,(V_W)                  ; guards: W 1-16
        or a
        jp z,.drop
        cp 17
        jp nc,.drop
        ld a,d                      ; the stream outside page H's slot
        and 0xE0
        cp 0x80
        jp z,.drop
        ld a,(V_KIND)
        cp 2
        jr nz,.masked
        ld a,(V_H)                  ; opaque: H = lines, whole cells only
        ld c,a
        and 7
        jp nz,.drop
        ld a,c
        rrca
        rrca
        rrca
        and 31
        ld (V_NR),a
        xor a
        ld (V_R0),a
        jr .geom
.masked:
        ld a,(V_H)                  ; rows the plot draws: 40 <= row, row < limit (S flag, as CP / JP M)
        ld b,a
        ld c,0                      ; C = stream row
        ld a,(V_YC)
        ld d,a
        xor a
        ld (V_NR),a
.rw:    ld a,c
        cp b
        jr nc,.geom0
        ld a,d
        add a,c
        sub 40
        jp m,.rno
        add a,40
        ld hl,V_LM
        sub (hl)
        jp p,.rno
        ld hl,V_NR
        ld a,(hl)
        or a
        jr nz,.rin
        ld a,c
        ld (V_R0),a
.rin:   inc (hl)
        inc c
        jr .rw
.rno:   ld a,(V_NR)                 ; a gap after the visible run ends it
        or a
        jr nz,.geom0
        inc c
        jr .rw
.geom0: ld a,(V_R0)
        ld hl,V_ROW0
        add a,(hl)
        ld (hl),a
.geom:  ld a,(V_NR)
        or a
        ret z                       ; nothing visible
        cp 21
        jp nc,.drop
        ld a,(V_KIND)               ; mirrored: the pointer is the rightmost cell
        cp 1
        jr nz,.xok
        ld a,(V_W)
        dec a
        ld c,a
        ld a,(V_XL)
        sub c
        ld (V_XL),a
.xok:   ld a,(V_W)                  ; tiles
        inc a
        srl a
        ld (V_TW),a
        ld b,a
        ld a,(V_NR)
        inc a
        srl a
        ld (V_TH),a
        ld c,a
        xor a
.mu:    add a,c
        djnz .mu
        ld (V_NT),a
        cp MAXPAT+1
        jr nc,.drop
        ld a,(V_KIND)
        cp 2
        jr nz,.st1
        ld a,(V_W)
        jr .st2
.st1:   ld a,1
.st2:   ld (V_ST),a
        call key
        call lookup                 ; -> V_E, carry = dropped
        ret c
        jp emit
.drop:  ld hl,V_DROP
        inc (hl)
        ret

; key: stream (2), km, W, H, r0, nr, first 4 stream bytes
key:    ld hl,V_KEY
        ld de,(V_DE)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_KM)
        ld (hl),a
        inc hl
        ld a,(V_W)
        ld (hl),a
        inc hl
        ld a,(V_H)
        ld (hl),a
        inc hl
        ld a,(V_R0)
        ld (hl),a
        inc hl
        ld a,(V_NR)
        ld (hl),a
        inc hl
        ex de,hl
        ld bc,4
        ldir
        ret

; lookup: the entry with V_KEY (hit) or a new one built (miss) -> V_E; carry = no room (dropped)
lookup: ld hl,CE+1
        ld b,NCE
        ld de,ESZ
        ld a,(V_KEY)
.e:     cp (hl)
        jr z,.cand
.nx:    add hl,de
        djnz .e
        call cells                  ; miss; carry = the stream ran into page H's slot
        jr c,.bad
        call alloc
        ret c
        call build
        jr .use
.bad:   ld hl,V_DROP
        inc (hl)
        scf
        ret
.cand:  dec hl
        bit 7,(hl)                  ; valid?
        inc hl
        jr z,.nx
        push hl
        push bc
        inc hl
        ld de,V_KEY+1
        ld c,10
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.ne
        inc hl
        inc de
        dec c
        jr nz,.cmp
        pop bc
        pop hl
        dec hl                      ; the entry
.use:   set 0,(hl)
        ld (V_E),hl
        or a
        ret
.ne:    pop bc
        pop hl
        ld de,ESZ
        ld a,(V_KEY)
        jr .nx

; alloc: an invalid entry (or an idle one evicted) with enough free patterns -> HL; carry = none
alloc:  ld hl,CE                    ; an invalid entry?
        ld b,NCE
        ld de,ESZ
.i:     bit 7,(hl)
        jr z,.got
        add hl,de
        djnz .i
        call idle                   ; none: evict an idle entry
        ret c
        push hl
        call evict
        pop hl
.got:   ld (V_E),hl
.pat:   ld a,(V_NFREE)              ; enough free patterns?
        ld b,a
        ld a,(V_NT)
        cp b
        jr c,.ok
        jr z,.ok
        call idle
        jr c,.fail
        call evict
        jr .pat
.ok:    ld hl,(V_E)
        ld (hl),0x80
        inc hl
        ex de,hl
        ld hl,V_KEY
        ld bc,11
        ldir
        ex de,hl
        ld a,(V_NT)
        ld (hl),a
        ld hl,(V_E)
        or a
        ret
.fail:  ld hl,V_DROP
        inc (hl)
        scf
        ret

; idle: an entry valid, not used this commit, other than V_E -> HL (round robin); not on show first,
; then one on show (its sprites are replaced by this commit's upload); carry = none
idle:   ld d,0x83
        call .pass
        ret nc
        ld d,0x81
        call .pass
        ret c
        ld hl,V_TEAR
        inc (hl)
        ld hl,(V_FOUND)            ; the entry found (see .found)
        or a
        ret
.pass:  ld a,(V_RR)
        ld c,NCE
.l:     cp NCE
        jr c,.in
        xor a
.in:    ld b,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld de,CE
        add hl,de
        pop de
        ld a,(hl)
        and d
        cp 0x80
        jr nz,.no
        push de
        ld de,(V_E)
        or a
        sbc hl,de
        add hl,de
        pop de
        jr z,.no
        ld a,b
        inc a
        ld (V_RR),a
        ld (V_FOUND),hl
        or a
        ret
.no:    ld a,b
        inc a
        dec c
        jr nz,.l
        scf
        ret

; evict HL: its patterns back on the FREE stack, entry invalid
evict:  ld (hl),0
        ld de,12
        add hl,de
        ld b,(hl)                   ; n
        inc hl
.p:     ld a,b
        or a
        ret z
        ld a,(hl)
        inc hl
        dec b
        cp 0xFF
        jr z,.p
        push hl
        push af
        ld a,(V_NFREE)
        ld l,a
        inc a
        ld (V_NFREE),a
        ld h,high FREE
        pop af
        ld (hl),a
        pop hl
        jr .p

; cells: walk the stream -> CELLS (masked kinds); carry = the stream entered page H's slot
cells:  ld a,(V_KIND)
        cp 2
        jr nz,.w
        or a
        ret
.w:     ld hl,(V_DE)
        ld de,CELLS
        ld a,(V_R0)
        ld c,a                      ; C = rows still to skip
        ld a,(V_NR)
        add a,c
        ld (V_CK),a                 ; rows to walk
.r:     ld a,(V_W)
        ld b,a
.c:     ld a,h
        and 0xE0
        cp 0x80
        scf
        ret z
        ld a,(hl)
        or a
        jr nz,.cell
        inc hl
        ld a,c
        or a
        jr nz,.nc
        ld (de),a
        inc de
        ld (de),a
        inc de
        jr .nc
.cell:  inc hl
        ld a,c
        or a
        jr nz,.sk
        ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
.sk:    ld a,9
        add a,l
        ld l,a
        jr nc,.nc
        inc h
.nc:    djnz .c
        ld a,c
        or a
        jr z,.ns
        dec c
.ns:    ld a,(V_CK)
        dec a
        ld (V_CK),a
        jr nz,.r
        or a
        ret

; build: the patterns of entry V_E (rows of tiles, left to right)
build:  xor a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
.tx:    call tile
        ld a,(V_TX)
        inc a
        ld (V_TX),a
        ld hl,V_TW
        cp (hl)
        jr c,.tx
        ld a,(V_TY)
        inc a
        ld (V_TY),a
        ld hl,V_TH
        cp (hl)
        jr c,.ty
        ld hl,(V_E)
        ret

; tile (V_TX, V_TY): a pattern from the FREE stack, 16 rows uploaded; an empty one goes back
tile:   ld a,(V_NFREE)
        dec a
        ld (V_NFREE),a
        ld l,a
        ld h,high FREE
        ld a,(hl)
        ld (V_P),a
        ld c,a                      ; select it: 0x303B = slot (P / 2) + 128-byte half
        srl a
        bit 0,c
        jr z,.s
        or 0x80
.s:     ld bc,0x303B
        out (c),a
        xor a
        ld (V_OR),a
        ld a,(V_TY)
        add a,a
        call cellrow
        ld a,(V_TY)
        add a,a
        inc a
        call cellrow
        ld a,(V_TX)                 ; record the pattern (or 0xFF) in the entry
        ld b,a
        ld a,(V_TY)
        ld c,a
        ld a,(V_TW)
        ld e,a
        xor a
.mul:   dec c
        jp m,.md
        add a,e
        jr .mul
.md:    add a,b
        ld e,a
        ld d,0
        ld hl,(V_E)
        add hl,de
        ld de,13
        add hl,de
        ld a,(V_OR)
        or a
        ld a,(V_P)
        jr nz,.keep
        ld a,(V_NFREE)              ; empty: the pattern goes back
        inc a
        ld (V_NFREE),a
        ld a,0xFF
.keep:  ld (hl),a
        ret

; cellrow: A = visible cell row: 8 pattern lines of the tile's two cells
cellrow:ld (V_CK),a
        ld a,(V_TX)
        add a,a
        ld c,a
        ld a,(V_CK)
        ld b,a
        call cellset
        ld (V_CP0),hl
        ld a,d
        ld (V_N0),a
        ld a,e
        ld (V_Q0),a
        call bytes2
        ld (V_I0),a
        ld a,e
        ld (V_P0),a
        ld a,(V_TX)
        add a,a
        inc a
        ld c,a
        ld a,(V_CK)
        ld b,a
        call cellset
        ld (V_CP1),hl
        ld a,d
        ld (V_N1),a
        ld a,e
        ld (V_Q1),a
        call bytes2
        ld (V_I1),a
        ld a,e
        ld (V_P1),a
        ld a,8
        ld (V_LN),a
.l:     ld hl,(V_CP0)
        ld a,(V_N0)
        ld (V_INK),a
        ld a,(V_Q0)
        ld (V_PAP),a
        ld a,(V_I0)
        ld d,a
        ld a,(V_P0)
        ld e,a
        call bout
        ld (V_CP0),hl
        ld hl,(V_CP1)
        ld a,(V_N1)
        ld (V_INK),a
        ld a,(V_Q1)
        ld (V_PAP),a
        ld a,(V_I1)
        ld d,a
        ld a,(V_P1)
        ld e,a
        call bout
        ld (V_CP1),hl
        ld a,(V_LN)
        dec a
        ld (V_LN),a
        jr nz,.l
        ret

; bytes2: D = ink nibble, E = paper nibble -> A = ink byte (nibble twice), E = paper byte
bytes2: ld a,e
        add a,a
        add a,a
        add a,a
        add a,a
        or e
        ld e,a
        ld a,d
        add a,a
        add a,a
        add a,a
        add a,a
        or d
        ret

; cellset: B = visible cell row, C = screen column in the figure -> HL = its graphics (0 = none),
; D = ink nibble, E = paper nibble
cellset:ld hl,0
        ld de,0
        ld a,b
        push hl
        ld hl,V_NR
        cp (hl)
        pop hl
        ret nc
        ld a,c
        push hl
        ld hl,V_W
        cp (hl)
        pop hl
        ret nc
        ld a,(V_KIND)
        cp 1
        jr nz,.sc
        ld a,(V_W)                  ; mirrored: stream column W - 1 - screen column
        dec a
        sub c
        ld c,a
.sc:    ld a,(V_W)                  ; HL = row * W + column
        ld e,a
        ld d,0
        ld a,b
        or a
        jr z,.m1
.m0:    add hl,de
        djnz .m0
.m1:    ld e,c
        add hl,de
        ld a,(V_KIND)
        cp 2
        jr z,.opq
        add hl,hl
        ld de,CELLS
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl                    ; HL = graphics
        ld a,h
        or l
        ld de,0
        ret z
        push hl
        ld de,8
        add hl,de
        ld a,(hl)                   ; the cell's attribute
        pop hl
        jr .attr
.opq:   push hl                     ; HL = cell index: attribute at data + 144 + index
        ld de,(V_DE)
        add hl,de
        ld de,144
        add hl,de
        ld a,(hl)
        pop hl
        push af
        ld a,c                      ; graphics = data + (row * 8) * W + column
        ld hl,0
        ld a,(V_CK)
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_W)
        ld e,a
        ld d,0
        ld a,b
        or a
        jr z,.g1
.g0:    add hl,de
        djnz .g0
.g1:    ld e,c
        add hl,de
        ld de,(V_DE)
        add hl,de
        pop af
.attr:  ld b,a
        ld a,(V_MODE)
        cp 1
        jr nz,.a2
        ld b,7                      ; type 6 hit: attribute 7
        jr .a9
.a2:    cp 2
        jr nz,.a9
        ld a,b
        cp 4
        jr nz,.a3
        ld b,5
        jr .a9
.a3:    cp 5
        jr nz,.a9
        ld b,4
.a9:    ld a,b                      ; ink
        and 7
        call cidx
        ld d,a
        ld a,b                      ; paper
        rrca
        rrca
        rrca
        and 7
        call cidx
        ld e,a
        ret
; A = colour 0-7, bit 6 of B = bright -> palette index (black = 8)
cidx:   or a
        jr nz,.c
        ld a,8
        ret
.c:     bit 6,b
        ret z
        add a,8
        ret

; bout: HL = graphics of this line (0 = none), D / E = ink / paper bytes -> 4 pattern bytes;
; HL advanced by the stride
bout:   ld a,h
        or l
        jr nz,.y
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        ret
.y:     push hl
        ld c,(hl)                   ; C = stored graphic
        ld a,c
        ld (V_CK),a
        ld a,(V_KIND)
        cp 2
        jr nz,.msk
        ld b,0                      ; opaque: every pixel drawn
        jr .sc
.msk:   ld h,MASKT
        ld l,c
        ld b,(hl)                   ; B = mask
        cp 1
        jr nz,.sc
        ld h,REVT
        ld l,c
        ld c,(hl)
        ld l,b
        ld b,(hl)
.sc:    ld a,c
        ld (V_G),a
        ld a,b
        ld (V_M),a
        ld a,(V_COL)
        or a
        jr z,.def
        pop hl
        push hl
        call colent
        jr c,.painted
.def:   ld a,(V_G)
        and 0xF0
        ld b,a
        ld a,(V_M)
        rrca
        rrca
        rrca
        rrca
        and 15
        or b
        call nibo
        ld a,(V_G)
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld b,a
        ld a,(V_M)
        and 15
        or b
        call nibo
        jr .adv
.painted:
        call pixout
.adv:   pop hl
        ld a,(V_ST)
        add a,l
        ld l,a
        ret nc
        inc h
        ret

; nibo: A = index; D / E = ink / paper bytes -> two pattern bytes
nibo:   ld l,a
        ld h,high TI0
        ld a,(hl)
        and d
        ld b,a
        ld h,high TP0
        ld a,(hl)
        and e
        or b
        out (0x5B),a
        ld c,a
        ld h,high TI1
        ld a,(hl)
        and d
        ld b,a
        ld h,high TP1
        ld a,(hl)
        and e
        or b
        out (0x5B),a
        or c
        ld hl,V_OR
        or (hl)
        ld (hl),a
        ret

; colent: HL = graphics byte address -> carry = a valid colour entry (V_NIB, V_TM filled); keeps DE.
; The store is mapped at slot 5 only here: the graphic is already in V_G / V_M, no game memory read
colent: ld a,h
        cp 0x60
        jr c,.no
        push de
        sub 0x60
        ld h,a
        rrca
        rrca
        and 63
        add a,STORE
        nextreg 0x55,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xA000
        add hl,de
        ld a,(hl)
        or a
        jr z,.nm
        inc hl
        ld a,(V_CK)                 ; check = the stored graphic
        cp (hl)
        jr nz,.nm
        inc hl
        ld de,V_NIB
        ld b,4
.n:     ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (de),a
        inc de
        ld a,(hl)
        and 15
        ld (de),a
        inc de
        inc hl
        djnz .n
        ld a,(hl)
        ld (V_TM),a
        nextreg 0x55,GP5
        pop de
        scf
        ret
.nm:    nextreg 0x55,GP5
        pop de
.no:    or a
        ret

; pixout: the 8 pixels of V_G / V_M with the colour entry -> 4 pattern bytes
pixout: ld c,0                      ; C = screen pixel 0-7
.px:    call pixel
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        inc c
        call pixel
        or e
        out (0x5B),a
        ld hl,V_OR
        or (hl)
        ld (hl),a
        inc c
        ld a,c
        cp 8
        jr c,.px
        ret

; pixel C (0 = left on screen) -> A = colour index (0 transparent); keeps C, E
pixel:  ld a,(V_KIND)               ; stored bit: mirrored = 7 - C
        cp 1
        ld a,c
        jr nz,.sb
        ld a,7
        sub c
.sb:    ld d,a                      ; D = stored bit
        ld b,a
        inc b
        ld a,(V_TM)                 ; painted transparent?
.t:     rlca
        djnz .t
        jr c,.clr
        push de
        ld e,d
        ld d,0
        ld hl,V_NIB
        add hl,de
        pop de
        ld d,(hl)                   ; D = the bit's nibble (0 = default)
        ld b,c
        inc b
        ld a,(V_G)
.g:     rlca
        djnz .g
        jr nc,.ng
        ld a,d
        or a
        ret nz
        ld a,(V_INK)
        ret
.ng:    ld b,c
        inc b
        ld a,(V_M)
.m:     rlca
        djnz .m
        ld a,d
        ret c                       ; clear pixel: its nibble (0 = transparent)
        or a
        ret nz
        ld a,(V_PAP)
        ret
.clr:   xor a
        ret

; emit: the entry's tiles -> SPRTAB (screen pixel X = 8 x + 16 TX, Y = 8 row + 16 TY); tiles outside
; the screen columns or empty get no sprite
emit:   ld a,(V_XL)
        ld l,a
        rlca
        sbc a,a
        ld h,a                      ; HL = x (signed)
        add hl,hl
        add hl,hl
        add hl,hl
        ld (V_SX),hl
        ld hl,(V_E)
        ld de,13
        add hl,de                   ; HL = pattern list
        xor a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
        push hl
.tx:    pop hl
        ld a,(hl)
        inc hl
        push hl
        cp 0xFF
        jp z,.nx
        ld (V_P),a
        ld a,(V_NS)
        cp MAXSPR
        jp nc,.nx
        ld a,(V_TX)                 ; X = SX + 16 TX; visible when -15 <= X <= 255
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,(V_SX)
        add hl,de
        ld de,15
        add hl,de                   ; X + 15 in 0..270
        ld a,h
        or a
        jr z,.vis                   ; 0..255
        dec a
        jp nz,.nx                   ; negative or >= 512
        ld a,l
        cp 15
        jp nc,.nx                   ; 256..270 only
.vis:   ld de,32 - 15
        add hl,de                   ; HL = X + 32 (sprite coordinates, 9 bits)
        ex de,hl
        ld a,(V_NS)
        ld l,a
        inc a
        ld (V_NS),a
        ld h,0
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc
        ld bc,SPRTAB
        add hl,bc
        ld (hl),e                   ; attr 0: X low
        inc hl
        ld a,(V_ROW0)               ; attr 1: Y = 32 + 8 row + 16 TY
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_TY)
        add a,a
        add a,a
        add a,a
        add a,a
        add a,b
        add a,32
        ld (hl),a
        inc hl
        ld a,d
        and 1
        ld (hl),a                   ; attr 2: X8
        inc hl
        ld a,(V_P)
        ld c,a
        srl a
        or 0xC0
        ld (hl),a                   ; attr 3: visible, attr 4 on, slot P / 2
        inc hl
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a                   ; attr 4: 4-bit, 128-byte half
.nx:    ld a,(V_TX)
        inc a
        ld (V_TX),a
        ld hl,V_TW
        cp (hl)
        jp c,.tx
        pop hl
        ld a,(V_TY)
        inc a
        ld (V_TY),a
        ld de,V_TH
        ld a,(de)
        ld b,a
        ld a,(V_TY)
        cp b
        jp c,.ty
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): alt ROM image 0 (ROM 0 + the hook bytes), palette,
; transparency, hide all, clip, sprites on. Runs before the stub's image-1 fill.
        ORG 0xD000
setup:  nextreg 0x54,20             ; stub page alias at 0x8000, hook image page at 0xA000
        nextreg 0x55,24
        jp .alias - 0x4000
.alias: ld bc,0x243B                ; unlock 7FFD paging (NextReg $08 bit 7)
        ld a,8
        out (c),a
        inc b
        in a,(c)
        or 0x80
        nextreg 0x08,a
        ld bc,0x1FFD                ; ROM 0 (the 128K ROM = alt image 0)
        xor a
        out (c),a
        ld b,0x7F
        out (c),a
        nextreg 0x8C,0xC0           ; alt ROM write mode: reads ROM, writes the image
        ld hl,0
        ld de,0
        ld bc,0x4000
        ldir
        ld hl,0xA000
        ld de,0x2000
        ld bc,rom_end + 20 - 0x2000 ; hook bytes + the register block (pre-filled by Python)
        ldir
        nextreg 0x8C,0
        nextreg 0x56,20
        nextreg 0x57,21
        jp .back
.back:  nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0              ; index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2              ; sprite clip window = the play area
        nextreg 0x19,16
        nextreg 0x19,239
        nextreg 0x19,0
        nextreg 0x19,151
        nextreg 0x15,0x01           ; sprites on, SLU, higher number on top
        ret
pal:                                ; 16 palette bytes appended by Python

        SAVEBIN "ab_rom.bin",0x2400,rom_end-0x2400
        SAVEBIN "ab_setup.bin",0xD000,pal-0xD000
