; The New Zealand Story (128K) colour build: stage E (tilemap scenery from the game's own char window)
; and stage F (figures as 4-bit hardware sprites from the game's own object records).
; The code is in alt ROM image 1 at 0x2000-0x3FFF (the game never reads its ROM in play), so the
; game's 0x7FFD writes (every interrupt) cannot unmap it. Those writes do reset MMU0/MMU1 to the
; ROM, so the hooks use:
;   slot 3 (0x6000-0x7FFF, MMU3): page 15 (state) or the level's page (tables) - the interrupt
;       routine never touches 0x6000-0x7FFF (checked); every page mapped there keeps
;       0x1F00-0x1FFF free as a stack zone, so an interrupt's pushes land harmlessly.
;   MMU0 (0x0000-0x1FFF): page 14 (tilemap) or a figure/pattern page, re-checked after every row,
;       part or pattern and redone if an interrupt put the ROM back.
; GPL-3.0-or-later, as NexClash. Engine new_zealand_story (assembled at build time by nexclash/new_zealand_story.py).
    DEVICE NOSLOT64K
    OPT --zxnext

    IFNDEF STAGEF
STAGEF = 1
    ENDIF
    IFNDEF NEG_TILE
NEG_TILE = 0
    ENDIF
    IFNDEF NEG_LAG
NEG_LAG = 0
    ENDIF
    IFNDEF NEG_DE
NEG_DE = 0
    ENDIF
    IFNDEF SMOOTH
SMOOTH = 0                      ; the "Smooth scrolling" toggle: the build with it on has 1
    ENDIF
    IFNDEF NEG_SMSTEP
NEG_SMSTEP = 0                  ; negative controls of smooth scrolling: a step of 3, not 2;
    ENDIF
    IFNDEF NEG_SMFIG
NEG_SMFIG = 0                   ; figures not moved with the scenery;
    ENDIF
    IFNDEF NEG_SMCLIP
NEG_SMCLIP = 0                  ; the tilemap not clipped to the play area
    ENDIF

NEG_SOUND = 0
NEG_RESTORE = 0
NEG_CAP = 0
NEG_WIN = 0                     ; negative control: the windows' lines left out of the wait
NEG_COMMIT = 0
NEG_SMBOUND = 0
NEG_UPLOAD = 0
SM_HOLD EQU 10-2*NEG_SMBOUND
SM_QN EQU 0x603B
SM_QUEUE EQU 0x6200
S_DRAW_SPEED EQU 0x6039
S_IRQ_SPEED EQU 0x603A
S_TICK EQU 0x6032
S_LAST_TICK EQU 0x6034
S_LAST_LINE EQU 0x6036
S_CAP_VALID EQU 0x6038
S_WSP   EQU 0x603C              ; the game's SP while a drawing window's library call runs
S_ISP   EQU 0x603E              ; the interrupted SP while the handler's library call runs
S_WSUM  EQU 0x6040              ; lines the windows have run since the last wait (interrupts left out)
HLIB_V_PACE EQU 0x6042          ; 26 bytes, page 15, zero at start
HLIB_PACE_NL EQU 311
ISTK    EQU 0x6080              ; the handler's library call (0x605C-0x607F)
; The wait before the player follows the original's time: what the three windows' drawing took it, from their time at
; 28 MHz, plus what the rest of the update's drawing took it, less what those cost here.
; Least squares on JNext over 3 runs of 800 updates (games/new_zealand_story.md, Pace): residual 0.4 ms of 70.
PACE_K  EQU 90                  ; x 16: window time x K (5.6) is the original's extra time for that drawing
    IF SMOOTH
PACE_C  EQU 3400                ; 1/16 lines: Smooth's work in the interrupt lengthens the update by about 3 ms more
    ELSE
PACE_C  EQU 3990                ; 1/16 lines: 16.7 ms, the screen copy's and the rest, a constant here
    ENDIF
PACE_CAP EQU 1244               ; lines, about 81.04 ms: four 128K frames: no update waits past it

LVBASE  EQU 46                  ; level pages 46..66
PTBASE  EQU 70                  ; pattern pages
; level page at slot 3
LP_N    EQU 0x6000
LP_PAL  EQU 0x6100
LP_SLOT EQU 0x6300
LP_ATTR EQU 0x6400
LP_TILE EQU 0x6500
V_WIN   EQU 0x7E00
V_MAP   EQU 0x7E02
V_HL    EQU 0x7E04
V_DE    EQU 0x7E06
; page 15 at slot 3
S_COPY  EQU 0x6000
S_NEXT  EQU 0x6001
S_PREV  EQU 0x6002
S_FIGN  EQU 0x6003
S_SP    EQU 0x6004
S_MISS  EQU 0x6006
S_NSPR  EQU 0x6008
S_PPG   EQU 0x6009              ; program page of the figure being done
S_X     EQU 0x600A              ; 2*x4+32 of the figure
S_Y     EQU 0x600C              ; y5+32
S_PTR   EQU 0x600E              ; program pointer
S_CNT   EQU 0x6010
S_FIG   EQU 0x6011              ; figure pointer
S_PART  EQU 0x6018              ; the part being done (6 bytes)
S_FIGP  EQU 0x6013
S_UPG   EQU 0x6014
S_UOF   EQU 0x6015
FIGL    EQU 0x6100              ; 36 x 6: frame, x4, y5, mirror, set, spare
PSLOT   EQU 0x6400              ; pid -> slot, 0xFF none (2048)
SLPL    EQU 0x6C00
SLPH    EQU 0x6E00              ; page-aligned: the code indexes it as high byte + slot
STAMP   EQU 0x6D00
STK     EQU 0x8000
MAP0    EQU 0x1600+4*80+8       ; page 14 at MMU0: entry of screen char (0,0)
; smooth scrolling, page 15 at slot 3
SM_VALID EQU 0x6020             ; 0: the next copy puts the view where the game is
SM_BUSY EQU 0x6021              ; a copy hook is writing sprites or the tilemap: the interrupt waits
SM_N    EQU 0x6022              ; sprites in SATT
SM_PX   EQU 0x6024              ; the game's scroll at the last copy (pixels, 10 bits)
SM_PY   EQU 0x6026
SM_DX   EQU 0x6028              ; where the view is shown (pixels, 10 bits)
SM_DY   EQU 0x602A
SM_OX   EQU 0x602C              ; D - P, the tilemap's hardware offset, -8..8
SM_OY   EQU 0x602E
SATT    EQU 0x7000              ; each sprite as the game put it: X, Y (2 each), attribute 2's bits, slot
SM_PEND EQU 0x6030              ; rows are waiting in page 15 for the next interrupt to show them
STAGE   EQU 0x7400              ; (slot 3, page 15's 0x1400) the rows, laid out as the map at page 14's 0x1600
V_PG    EQU 0x7E08              ; (level page scratch) the page the rows go to

    MACRO NR50CHK page          ; Z if MMU0 still holds the page
    ld bc,0x243B
    ld a,0x50
    out (c),a
    inc b
    in a,(c)
    cp page
    ENDM

    MACRO ENTER
    nextreg 0x53,15
    ld (S_SP),sp
    ld sp,STK
    push af
    push bc
    push de
    push hl
    push ix
    ld bc,0x243B
    ld a,7                      ; an interrupt between OUT and IN leaves NR 0x53 selected: its pages have bit 3 set, NR 7 not
    out (c),a
    inc b
    in a,(c)
    dec b
    bit 3,a
    jr nz,$-10
    and 3
    push af
    nextreg 7,3
    ENDM

    MACRO LEAVE
    nextreg 0x53,15
    pop af
    nextreg 7,a
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ld sp,(S_SP)
    nextreg 0x50,0xFF
    nextreg 0x53,11
    ENDM

    MACRO OFF
    nextreg 0x6B,0x00           ; tilemap off
    nextreg 0x15,0x00           ; sprites off
    IF STAGEF == 0
    nextreg 0x43,0x00
    nextreg 0x40,22
    nextreg 0x41,0xB4           ; the yellow paper opaque again
    ENDIF
    ENDM

    ORG 0x2000
; =====================================================================================
; 0xDAC1 (was LD BC,$1200): screen copy start
h_copy:
    ENTER
    call lvmap                  ; level page at slot 3
    ld hl,0x9E86                ; the window as 0xD9D1 reads it (0xD3E9's arithmetic)
    IF NEG_LAG
    inc hl                      ; negative control: one scroll step behind
    ENDIF
    ld a,(0x5CAB)
    cp 1
    jr nz,.c1
    dec hl
.c1 cp 3
    jr nz,.c2
    inc hl
.c2 ld de,36
    ld a,(0x5CAC)
    cp 1
    jr nz,.c3
    or a
    sbc hl,de
.c3 cp 3
    jr nz,.c4
    add hl,de
.c4
    IF SMOOTH
    push hl
    nextreg 0x53,15
    ld a,1
    ld (SM_BUSY),a
    call sm_copy                ; the view: where it is shown, as the game moved
    call lvmap                  ; the rows go to page 15, to be shown by the next interrupt, between
    ld a,15                     ; frames, with the offset: nothing changes on screen part way down
    ld (V_PG),a
    ld de,MAP0-82-0x200
    pop hl
    push de
    ld de,37
    or a
    sbc hl,de                   ; the window at screen char (-1,-1)
    pop de
    ld ixl,20
.rows
    push ix
    call wrow34                 ; rows -1..18, columns -1..32: the margins the offset shows
    pop ix
    dec ixl
    jr nz,.rows
    ld hl,0
    ld (V_MAP),hl               ; the row hook leaves the map alone
    nextreg 0x53,15
    ld a,1
    ld (SM_PEND),a
    ELSE
    ld de,MAP0
    call wrowv                  ; row 0 changes as the copy starts row 0
    ld (V_WIN),hl
    ld (V_MAP),de
    ENDIF
    nextreg 0x6E,0x96           ; map: bank 7 + 0x1600
    nextreg 0x6F,0x80           ; definitions: bank 7 + 0
    nextreg 0x1C,0x08
    IF NEG_SMCLIP
    nextreg 0x1B,8
    nextreg 0x1B,151
    nextreg 0x1B,24
    nextreg 0x1B,183
    ELSE
    nextreg 0x1B,16
    nextreg 0x1B,143
    nextreg 0x1B,32
    nextreg 0x1B,175
    ENDIF
    IF STAGEF == 0
    nextreg 0x43,0x00
    nextreg 0x40,22
    nextreg 0x41,0xE3           ; yellow paper = the transparency colour: tiles show through
    ENDIF
    IF SMOOTH == 0
    nextreg 0x6B,0x80           ; tilemap on, 40x32, 2-byte entries, per-tile ULA priority
    ENDIF
    nextreg 0x53,15
    IF STAGEF
    call sprites
    ENDIF
    IF SMOOTH
    xor a
    ld (SM_BUSY),a
    ENDIF
    LEAVE
c_tail:
    ld bc,0x1200
    jp 0xDAC4

; =====================================================================================
; 0xDB16 (was LD A,E / ADD A,$20): after each char row of the copy
h_row:
    ENTER
    call lvmap
    ld a,(V_MAP+1)
    cp high MAP0
    jr c,.none                  ; no copy start seen for this copy (V_MAP cleared): leave the map
    ld a,b
    or c
    jr z,.last                  ; BC = 0: row 17 was the last
    ld hl,(V_WIN)
    ld de,(V_MAP)
    call wrowv
    ld (V_WIN),hl
    ld (V_MAP),de
    jr .none
.last
    ld hl,0
    ld (V_MAP),hl
.none
    LEAVE
    IF NEG_DE
    inc e
    ENDIF
r_tail:
    ld a,e
    add a,0x20
    jp 0xDB19

; =====================================================================================
; 0xD973 (was LD HL,$0140): level init, after the map, the char set and the game's map row table
; (0xFB40, built by the CALL just before) are in place
h_level:
    ENTER
    IF SMOOTH
    xor a
    ld (SM_VALID),a             ; a new level: the view starts where the game is
    ENDIF
    OFF
    call lvmap
    nextreg 0x43,0x30           ; the first tilemap palette, auto-increment
    nextreg 0x40,0
    ld hl,LP_PAL
    ld b,0
.p  ld a,(hl)
    inc hl
    nextreg 0x44,a
    ld a,(hl)
    inc hl
    nextreg 0x44,a
    djnz .p
    nextreg 0x43,0x00
    ; tiles 1..n into page 14 at 0x0020 (MMU0), one tile at a time, checked
    ld a,(LP_N)
    ld ixl,a
    ld hl,LP_TILE
    ld de,0x0020
.t  push hl
    push de
.tr nextreg 0x50,14
    ld bc,32
    ldir
    NR50CHK 14
    jr z,.tok
    pop de                      ; an interrupt put the ROM back: again
    pop hl
    push hl
    push de
    jr .tr
.tok
    pop af                      ; drop the saved pointers
    pop af
    dec ixl
    jr nz,.t
    nextreg 0x50,0xFF
    LEAVE
l_tail:
    ld hl,0x0140
    jp 0xD976

; =====================================================================================
; 0xA2E1 (was LD HL,$D1B5): the level-start screen; 0xA200 (was DI / LD SP,0): restart, title
h_ready:
    OFF
k_tail:
    ld hl,0xD1B5
    jp 0xA2E4
h_title:
    nextreg 7,0
    OFF
t_tail:
    di
    ld sp,0x0000
    jp 0xA204

    IF STAGEF
; =====================================================================================
; 0xDDCC (was EX DE,HL / PUSH DE / EXX): the plotter draws this figure (past every early return)
h_plot:
    ENTER
    ld a,(S_FIGN)
    cp 36
    jr nc,.full
    ld e,a
    inc a
    ld (S_FIGN),a
    ld a,e
    add a,a
    add a,e
    add a,a                     ; 6n
    ld (S_FIGP),a
    ; read the record with bank 5 back at slot 3 (records 27-35 live at 0x6012-0x6131), on the
    ; game's own stack meanwhile (an interrupt then pushes where the original's would)
    ld hl,(S_SP)
    nextreg 0x53,11
    ld sp,hl
    ld l,(ix+6)
    ld h,(ix+7)
    ld e,(ix+8)
    ld d,0
    add hl,de
    ld e,(hl)                   ; E = frame
    ld c,(ix+4)                 ; C = x4
    ld b,(ix+5)                 ; B = y5
    ld a,(ix+11)
    and 1
    ld d,a                      ; D = mirror
    ld sp,STK-12                ; back below the five saved registers
    nextreg 0x53,15
    ld a,(S_FIGP)
    ld l,a
    ld h,high FIGL
    ld (hl),e
    inc l
    ld (hl),c
    inc l
    ld (hl),b
    inc l
    ld (hl),d
    inc l
    ld a,(0x9B6F)               ; frame 20's height names the sprite set loaded
    ld e,a
    ld d,high SETOF
    ld a,(de)
    ld (hl),a                   ; set
.full
    LEAVE
p_tail:
    ex de,hl
    push de
    exx
    jp 0xDDCF
    ENDIF

; =====================================================================================
; level page at slot 3 (call with page 15 at slot 3 is fine: only A is used and the return
; address is read back from the same offset of the level page's stack zone - so NOT that:
; lvmap is a macro-like routine that must be JP-called) - see lvmap below
lvmap:                          ; in: nothing; out: slot 3 = the level's page. Uses A, DE.
    pop hl                      ; return address, off the current page's stack zone
    ld a,(0xA402)
    cp 15
    jr c,.ok
    cp 17
    jr nc,.ok
    ; 4-4 is two maps played with the level variable at 15: MP (32 wide) then MQ (34 wide).
    ; The map width is read from the game's row table at 0xFB40 (0x6E00 is under page 15 here).
    push hl
    ld hl,(0xFB42)
    ld de,(0xFB40)
    or a
    sbc hl,de
    ld a,l
    pop hl
    cp 34
    ld a,15
    jr nz,.ok
    inc a
.ok add a,LVBASE
    nextreg 0x53,a
    jp (hl)

; one row: 32 codes from (HL) to 32 entries at (DE) in page 14 (MMU0), checked; HL += 36, DE += 80
wrowv:
    ld (V_HL),hl
    ld (V_DE),de
.again
    nextreg 0x50,14
    ld hl,(V_HL)
    ld de,(V_DE)
    ld ixh,32
.w  ld a,(hl)
    inc hl
    ld c,a
    ld b,high LP_SLOT
    ld a,(bc)
    IF NEG_TILE
    inc a
    ENDIF
    ld (de),a
    inc de
    inc b                       ; LP_ATTR = LP_SLOT + 0x100
    ld a,(bc)
    ld (de),a
    inc de
    dec ixh
    jr nz,.w
    push de
    NR50CHK 14
    pop de
    jr nz,.again
    ld a,4
    add hl,a
    ld a,16
    add de,a
    ret

    IF STAGEF
; =====================================================================================
; sprites: the figures listed this pass, as parts, in the game's drawing order (slot 35 first,
; Tiki last = highest sprite number = on top). Page 15 at slot 3.
sprites:
    ld hl,S_COPY
    inc (hl)
    xor a
    ld (S_NSPR),a
    IF SMOOTH
    ld (SM_QN),a
    ENDIF
    ld hl,FIGL
    ld (S_FIG),hl
    ld a,(S_FIGN)
    or a
    jp z,.hide
    ld ixl,a
.fig
    ld hl,(S_FIG)
    ld a,(hl)                   ; frame
    or a
    jp z,.nextfig
    cp 0x8C
    jp nc,.nextfig
    ld e,a                      ; E = frame
    inc l
    ld c,(hl)                   ; x4
    inc l
    ld b,(hl)                   ; y5
    inc l
    ld d,(hl)                   ; mirror
    inc l
    ld a,(hl)                   ; set
    cp 5
    jp nc,.nextfig
    ; X = 2*x4 + 32, Y = y5 + 32
    push de
    ld l,c
    ld h,0
    add hl,hl
    ld de,32
    add hl,de
    ld (S_X),hl
    ld l,b
    ld h,0
    add hl,de
    ld (S_Y),hl
    pop de
    ; directory index: set 0 or frame outside 20..42: (frame-1)*2+mir, else 278+((set-1)*23+frame-20)*2+mir
    or a
    jr z,.d0
    ld c,a                      ; set
    ld a,e
    cp 20
    jr c,.d0
    cp 43
    jr nc,.d0
    sub 20
    ld l,a
    ld h,0
    ld a,c
    dec a
    ld b,a
    jr z,.d2
.d1 ld a,l
    add a,23
    ld l,a
    jr nc,.d1b
    inc h
.d1b djnz .d1
.d2 add hl,hl
    ld bc,278
    add hl,bc
    jr .d3
.d0 ld l,e
    ld h,0
    dec l
    add hl,hl
.d3 ld a,d
    or a
    jr z,.d4
    inc hl
.d4 add hl,hl
    add hl,hl                   ; 4 bytes an entry
    ld bc,DIRT
    add hl,bc
    ld a,(hl)
    ld (S_PPG),a
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(hl)
    or a
    jp z,.nextfig
    ld (S_CNT),a
    ld (S_PTR),de
.part
    ; read the part's 6 bytes from the program page (MMU0), checked
.pr ld a,(S_PPG)
    nextreg 0x50,a
    ld hl,(S_PTR)
    ld de,S_PART
    ld bc,7
    ldir
    ld a,(S_PPG)
    ld e,a
    NR50CHK e
    jr nz,.pr
    ld hl,(S_PTR)
    ld bc,7
    add hl,bc
    ld (S_PTR),hl
    ld a,(S_NSPR)
    cp 128
    jp nc,.nextfig
    ; pattern slot
    ld hl,(S_PART+3)
    call pslot
    jr c,.skip
    ld c,a                      ; C = pattern slot
    ; X = S_X + dx, Y = S_Y + dy
    ld hl,(S_X)
    ld de,(S_PART)
    add hl,de
    ex de,hl                    ; DE = X
    ; top = y5 - hy in the clipper's 8 bits, 144..255 meaning above the top; Y = top + 32 + dy
    push de
    ld a,(S_Y)                  ; y5 + 32
    sub 32
    ld hl,S_PART+6
    sub (hl)                    ; y5 - hy (8 bits)
    ld l,a
    ld h,0
    cp 144
    jr c,.yv
    dec h                       ; above the top: negative
.yv ld de,32
    add hl,de
    ld a,(S_PART+2)
    ld e,a
    rla
    sbc a,a
    ld d,a                      ; DE = dy, signed
    add hl,de                   ; HL = Y
    pop de
    IF SMOOTH
    call sm_keep                ; as the game put it, then where the view shows it
    ENDIF
    IF SMOOTH == 0 || NEG_COMMIT
    ; select the sprite and write its 5 attribute bytes
    push bc
    ld a,(S_NSPR)
    ld bc,0x303B
    out (c),a
    pop bc
    ld a,e
    out (0x57),a                ; X low
    ld a,l
    out (0x57),a                ; Y low
    ld a,(S_PART+5)             ; palette offset << 4 | X mirror << 3
    ld b,a
    ld a,d
    and 1                       ; X bit 8
    or b
    out (0x57),a
    ld a,c
    srl a
    or 0xC0                     ; visible, attribute 4 follows, N5..N0
    out (0x57),a
    ld a,c
    and 1
    rrca
    rrca                        ; N6 into bit 6
    or 0x80                     ; 4-bit pattern
    ld b,a
    ld a,h
    and 1
    or b                        ; Y bit 8
    out (0x57),a
    ENDIF
    ld hl,S_NSPR
    inc (hl)
.skip
    ld hl,S_CNT
    dec (hl)
    jp nz,.part
.nextfig
    ld hl,(S_FIG)
    ld bc,6
    add hl,bc
    ld (S_FIG),hl
    dec ixl
    jp nz,.fig
.hide
    IF SMOOTH == 0 || NEG_COMMIT
    ; hide the sprites left from the last copy
    ld a,(S_NSPR)
    ld c,a
    ld a,(S_PREV)
    sub c
    jr c,.hd
    jr z,.hd
    ld b,a
    ld a,c
    push bc
    ld bc,0x303B
    out (c),a
    pop bc
.h1 xor a
    out (0x57),a
    out (0x57),a
    out (0x57),a
    out (0x57),a                ; attribute 3 = 0: invisible, 4 bytes
    djnz .h1
.hd ld a,(S_NSPR)
    ld (S_PREV),a
    ENDIF
    IF SMOOTH
    ld a,(S_NSPR)
    ld (SM_N),a
    ENDIF
    xor a
    ld (S_FIGN),a
    nextreg 0x50,0xFF
    IF SMOOTH == 0
    nextreg 0x15,0x01           ; sprites on, SLU, clipped to the play area
    ENDIF
    ret

; HL = pid -> A = hardware pattern slot (0..127), uploaded if not resident; carry: none free.
; Page 15 at slot 3. A slot stamped this copy is never taken.
pslot:
    push hl
    ld de,PSLOT
    add hl,de                   ; HL = &PSLOT[pid]
    ld a,(hl)
    cp 0xFF
    jr z,.miss
    pop de
    ld e,a
    ld d,high STAMP
    ld a,(S_COPY)
    ld (de),a
    ld a,e
    or a
    ret
.miss
    ld a,(S_NEXT)
    ld e,a
    ld d,high STAMP
    ld b,128
.f  ld a,(S_COPY)
    ex de,hl
    cp (hl)
    ex de,hl
    jr nz,.take
    ld a,e
    inc a
    and 127
    ld e,a
    djnz .f
    pop hl
    ld hl,(S_MISS)
    inc hl
    ld (S_MISS),hl
    scf
    ret
.take                           ; E = slot, HL = &PSLOT[pid], (SP) = pid
    ld a,(S_COPY)
    ld (de),a
    ld a,e
    inc a
    and 127
    ld (S_NEXT),a
    ld (hl),e
    ld d,high SLPH
    ld a,(de)
    cp 0xFF
    jr z,.noold
    ld b,a
    ld d,high SLPL
    ld a,(de)
    ld c,a                      ; BC = the slot's old pid
    ld hl,PSLOT
    add hl,bc
    ld (hl),0xFF
.noold
    pop hl                      ; pid
    ld d,high SLPL
    ld a,l
    ld (de),a
    ld d,high SLPH
    ld a,h
    ld (de),a
    ld a,l
    and 63
    ld b,a
    ld c,0
    srl b
    rr c                        ; BC = (pid & 63) * 128
    add hl,hl
    add hl,hl                   ; H = pid / 64
    ld a,h
    add a,PTBASE
    ld (S_UPG),a
    ld (S_UOF),bc
    IF SMOOTH && NEG_UPLOAD == 0
    ; A slot can still be on screen. Delay replacing its pattern until the same IRQ commit as its attributes.
    ld a,(SM_QN)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld bc,SM_QUEUE
    add hl,bc
    ld (hl),e
    inc hl
    ld a,(S_UPG)
    ld (hl),a
    inc hl
    ld bc,(S_UOF)
    ld (hl),c
    inc hl
    ld (hl),b
    ld hl,SM_QN
    inc (hl)
    ld a,e
    or a
    ret
    ENDIF
.up ld a,(S_UPG)
    nextreg 0x50,a
    ld a,e
    srl a
    jr nc,.ev
    or 0x80                     ; odd slot: the second 128 bytes of the 256-byte pattern
.ev ld bc,0x303B
    out (c),a
    ld hl,(S_UOF)
    ld bc,0x805B                ; 128 bytes to port 0x5B
    otir
    ld a,(S_UPG)
    ld d,a
    NR50CHK d
    jr nz,.up
    ld a,e
    or a
    ret
    ENDIF

    IF SMOOTH
; =====================================================================================
; Smooth scrolling. The game scrolls in whole chars, 8 pixels at an update. The view is shown at
; D, which follows the game's scroll P at 2 pixels a TV frame (the interrupt hook below), so it
; glides into the place the game has already drawn: one update behind, never ahead. Each copy
; writes the tilemap for P with a char's margin all round and sets the tilemap's offset to D - P;
; every sprite is moved by the same offset, so figures stay on the ground. Game memory and
; registers are not touched; the interrupt hook's pushes are below the game's stack.

; The copy: P from the game; pending D kept within 10 pixels (8 after the IRQ step), or put on it after a jump
; (a new life, a new level) of more than 16. Page 15 at slot 3.
sm_copy:
    ld hl,(0x5CA2)
    ld a,h
    and 3
    ld h,a
    ld (SM_PX),hl
    ld hl,(0x5CA4)
    ld a,h
    and 3
    ld h,a
    ld (SM_PY),hl
    ld a,(SM_VALID)
    or a
    jr nz,.keep
    ld hl,(SM_PX)
    ld (SM_DX),hl
    ld hl,(SM_PY)
    ld (SM_DY),hl
    ld a,1
    ld (SM_VALID),a
.keep
    ld ix,SM_PX
    call sm_hold
    ld ix,SM_PY
    call sm_hold
    jp sm_offsets

; Pending D may be 10 from P: the IRQ moves it 2 before publishing, leaving at most 8 visible.
; This avoids a 4-pixel catch-up when a copy arrives just before the fourth glide interrupt.
sm_hold:
    call sm_delta               ; HL = P - D, signed
    ld a,h
    or a
    jp p,.pos
    ld de,16                    ; negative: -16 <= d < -8 -> D = P + 8; below -16 -> D = P
    add hl,de
    jr nc,.snap
    ld a,l
    cp 16-SM_HOLD
    ret nc                      ; -10 <= d
    ld de,SM_HOLD
    jr .set
.pos
    ld de,-17
    add hl,de
    jr c,.snap                  ; d > 16
    ld de,16-SM_HOLD                     ; HL = d - 17: d > 10 when HL >= -6
    add hl,de
    ret nc
    ld de,-SM_HOLD
.set
    ld l,(ix+0)
    ld h,(ix+1)
    add hl,de
    jr .put
.snap
    ld l,(ix+0)
    ld h,(ix+1)
.put
    ld a,h
    and 3
    ld h,a
    ld (ix+4),l
    ld (ix+5),h
    ret

; IX at P: HL = P - D within 10 bits, -512..511.
sm_delta:
    ld l,(ix+0)
    ld h,(ix+1)
    ld e,(ix+4)
    ld d,(ix+5)
    or a
    sbc hl,de
    ld a,h
    and 3
    ld h,a
    bit 1,h
    ret z
    ld a,h
    or 0xFC
    ld h,a
    ret

; SM_OX, SM_OY = D - P.
sm_offsets:
    ld ix,SM_PX
    call sm_delta
    call sm_neg
    ld (SM_OX),hl
    ld ix,SM_PY
    call sm_delta
    call sm_neg
    ld (SM_OY),hl
    ret
sm_neg:
    xor a
    sub l
    ld l,a
    sbc a,a
    sub h
    ld h,a
    ret

; In sprites: DE = X, HL = Y, C = pattern slot, (S_PART+5) attribute 2's bits. Kept in SATT as the
; game put it; out, DE and HL less the view's offset.
sm_keep:
    push hl
    push de
    ld a,(S_NSPR)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,SATT
    add hl,de
    pop de
    ld (hl),e
    inc hl
    ld (hl),d
    inc hl
    ex (sp),hl                  ; HL = Y, the entry on the stack
    ex de,hl                    ; DE = Y, HL = X
    ex (sp),hl                  ; HL = entry, X on the stack
    ld (hl),e
    inc hl
    ld (hl),d
    inc hl
    ld a,(S_PART+5)
    ld (hl),a
    inc hl
    ld (hl),c
    pop hl                      ; X
    IF NEG_SMFIG == 0
    push de
    ld de,(SM_OX)
    or a
    sbc hl,de
    pop de
    ENDIF
    ex de,hl                    ; DE = X - ox
    IF NEG_SMFIG == 0
    push de
    ld de,(SM_OY)
    or a
    sbc hl,de
    pop de
    ENDIF
    ret                         ; HL = Y - oy

; DE = X, HL = Y, C = slot, B = attribute 2's bits: the sprite's 5 bytes to port 0x57.
sm_out:
    ld a,e
    out (0x57),a
    ld a,l
    out (0x57),a
    ld a,d
    and 1
    or b
    out (0x57),a
    ld a,c
    srl a
    or 0xC0
    out (0x57),a
    ld a,c
    and 1
    rrca
    rrca
    or 0x80
    ld b,a
    ld a,h
    and 1
    or b
    out (0x57),a
    ret

; =====================================================================================
; 0xFDFD (was JP $A404): every interrupt. D a step nearer P on each axis; the tilemap's offset and
; every sprite moved with it. Nothing while a copy hook is at work, or before the first copy.
h_irq_smooth:
    push af
    push bc
    push de
    push hl
    push ix
    ld hl,0                     ; inside a hook (its stack in slot 3): nothing, as slot 3 holds that stack
    add hl,sp
    ld a,h
    and 0xE0
    cp 0x60
    jr nz,.stack_ok
    ld bc,0x243B
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    cp 15
    jp nz,.away                 ; a level-page stack cannot be remapped; the cap's page-15 stack can
.stack_ok
    ld bc,0x243B                ; the slot 3 page and the speed, as they were
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    push af
    dec b
    ld a,0x07
    out (c),a
    inc b
    in a,(c)
    push af
    nextreg 0x07,3
    nextreg 0x53,15
    ld a,(SM_BUSY)
    or a
    jp nz,.out
    ld a,(SM_VALID)
    or a
    jp z,.out
    ld ix,SM_PX
    call sm_step
    ld b,a
    ld ix,SM_PY
    call sm_step
    or b
    ld b,a
    ld a,(SM_PEND)              ; the last copy's rows, from page 15 into the map shown
    or a
    jr z,.nopend
    xor a
    ld (SM_PEND),a
    nextreg 0x50,14
    ld hl,STAGE+3*80+6
    ld de,0x1600+3*80+6
    ld a,20
.cr ld bc,68
    ldir
    ld bc,80-68
    add hl,bc
    ex de,hl
    add hl,bc
    ex de,hl
    dec a
    jr nz,.cr
    call sm_upload
    nextreg 0x50,0xFF
    ld b,1                      ; (B was the copy's count) the offset and sprites written below
.nopend
    ld a,b
    or a
    jp z,.out                   ; nothing new, and already there
    call sm_offsets
    ld hl,(SM_OX)
    bit 7,h
    jr z,.ox
    ld de,320
    add hl,de
.ox ld a,h
    nextreg 0x2F,a
    ld a,l
    nextreg 0x30,a
    ld a,(SM_OY)
    nextreg 0x31,a
    ld a,(SM_N)
    or a
    jr z,.hide_old
    ld ixl,a
    ld bc,0x303B
    xor a
    out (c),a                   ; from sprite 0, the index moving on by itself
    ld hl,SATT
.s  push hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    push de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld b,(hl)
    inc hl
    ld c,(hl)
    ex de,hl                    ; HL = Y
    IF NEG_SMFIG == 0
    ld de,(SM_OY)
    or a
    sbc hl,de
    ENDIF
    pop de                      ; DE = X
    push hl
    ex de,hl
    IF NEG_SMFIG == 0
    ld de,(SM_OX)
    or a
    sbc hl,de
    ENDIF
    ex de,hl
    pop hl
    call sm_out
    pop hl
    ld de,8
    add hl,de
    dec ixl
    jr nz,.s
.hide_old
    ld a,(SM_N)
    ld c,a
    ld a,(S_PREV)
    sub c
    jr c,.shown
    jr z,.shown
    ld b,a
    ld a,c
    push bc
    ld bc,0x303B
    out (c),a
    pop bc
.hide_one
    xor a
    out (0x57),a
    out (0x57),a
    out (0x57),a
    out (0x57),a
    djnz .hide_one
.shown
    ld a,(SM_N)
    ld (S_PREV),a
    nextreg 0x6B,0x80
    nextreg 0x15,0x01
.out
    pop af
    and 3
    nextreg 0x07,a
    pop af
    nextreg 0x53,a
.away
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    jp speed_irq_original

sm_upload:
    ld a,(SM_QN)
    or a
    ret z
    ld ixh,a
    ld hl,SM_QUEUE
.loop
    ld e,(hl)
    inc hl
    ld a,(hl)
    nextreg 0x50,a
    inc hl
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    push hl
    push bc
    ld a,e
    srl a
    jr nc,.even
    or 0x80
.even
    ld bc,0x303B
    out (c),a
    pop hl
    ld bc,0x805B
    otir
    pop hl
    dec ixh
    jr nz,.loop
    xor a
    ld (SM_QN),a
    ret

; IX at P: D a step of 2 nearer P (all the way if nearer). A: not 0 when D moved. Keeps B.
sm_step:
    ld a,(ix+0)
    cp (ix+4)
    jr nz,.go
    ld a,(ix+1)
    cp (ix+5)
    jr nz,.go
    xor a
    ret
.go call sm_delta               ; HL = P - D
    ld a,h
    or a
    IF NEG_SMSTEP
    ld de,3
    ELSE
    ld de,2
    ENDIF
    jp m,.neg
    sbc hl,de
    jr c,.all
    jr .move
.neg
    add hl,de
    jr c,.all
    ld de,-2
    IF NEG_SMSTEP
    ld de,-3
    ENDIF
.move
    ld l,(ix+4)
    ld h,(ix+5)
    add hl,de
    jr .put
.all
    ld l,(ix+0)
    ld h,(ix+1)
.put
    ld a,h
    and 3
    ld h,a
    ld (ix+4),l
    ld (ix+5),h
    ld a,1
    ret

; One row of 34 codes from (HL) to 34 entries at (DE) in page 14 (MMU0), checked; HL += 36,
; DE += 80. The level's page at slot 3.
wrow34:
    ld (V_HL),hl
    ld (V_DE),de
.again
    ld a,(V_PG)
    nextreg 0x50,a
    ld hl,(V_HL)
    ld de,(V_DE)
    ld ixh,34
.w  ld a,(hl)
    inc hl
    ld c,a
    ld b,high LP_SLOT
    ld a,(bc)
    ld (de),a
    inc de
    inc b
    ld a,(bc)
    ld (de),a
    inc de
    dec ixh
    jr nz,.w
    push de
    ld a,(V_PG)
    ld e,a
    NR50CHK e
    pop de
    jr nz,.again
    ld a,2
    add hl,a
    ld a,12
    add de,a
    ret
    ENDIF

    ALIGN 256
SETOF:
    INCBIN "setof.bin"
DIRT:
    INCBIN "dir.bin"

; Pure drawing wrappers preserve the incoming clock and every input/output register.
; Clock words live in the private state page; the game sees its exact original stack.
    MACRO SPEED_IN
    call draw_enter
    ENDM
    MACRO SPEED_OUT
    call draw_leave
    ENDM

draw_enter:
    push af
    push bc
    push de
    ld bc,0x243B
    ld a,7                      ; as ENTER: read again when an interrupt came between OUT and IN
    out (c),a
    inc b
    in a,(c)
    dec b
    bit 3,a
    jr nz,$-10
    and 3
    ld d,a
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    ld e,a
    nextreg 0x53,15
    ld a,d
    ld (S_DRAW_SPEED),a
    ld a,e
    nextreg 0x53,a
    pop de
    pop bc
    pop af
    nextreg 7,3
    ret

draw_leave:
    push af
    push bc
    push de
    ld bc,0x243B
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    ld e,a
    nextreg 0x53,15
    ld a,(S_DRAW_SPEED)
    ld d,a
    ld a,e
    nextreg 0x53,a
    ld a,d
    IF NEG_RESTORE
    ld a,3
    ENDIF
    nextreg 7,a
    pop de
    pop bc
    pop af
    ret

; As draw_enter / draw_leave, and the routine's time goes to S_WSUM. Slot 3 holds the game's page at these three sites.
; The library's calls run on page 15's stack: the game's may be in slot 3 and, as before, is not used while page 15 is mapped.
win_enter:
    call draw_enter
    push af
    push bc
    push de
    push hl
    nextreg 0x53,15
    ld (S_WSP),sp
    ld sp,STK
    call hlib_pace_open
    ld sp,(S_WSP)
    nextreg 0x53,11
    pop hl
    pop de
    pop bc
    pop af
    ret

win_leave:
    push af
    push bc
    push de
    push hl
    nextreg 0x53,15
    ld (S_WSP),sp
    ld sp,STK
    call hlib_pace_tick         ; HL = the window's lines
    IF NEG_WIN == 0
    ld de,(S_WSUM)
    add hl,de
    ld (S_WSUM),hl
    ENDIF
    ld sp,(S_WSP)
    nextreg 0x53,11
    pop hl
    pop de
    pop bc
    pop af
    jp draw_leave

h_paced_player:
    ENTER
speed_wait:
    call cap_wait
speed_wait_done:
    LEAVE
paced_player_call:
    call 0xC22E
    jp 0xA39A
h_fast_scroll:
    call win_enter
fast_scroll_call:
    call 0xD814
    call win_leave
    jp 0xA38B
h_fast_scenery:
    call win_enter
fast_scenery_call:
    call 0xD9D1
    call win_leave
    jp 0xA391
h_fast_figures:
    call win_enter
fast_figures_call:
    call 0xDB26
    call win_leave
    jp 0xA394
h_fast_copy:
    SPEED_IN
fast_copy_call:
    call 0xDAC1
    SPEED_OUT
    jp 0xA3A3

; Count video interrupts without changing the interrupted A (NZS mixes A into its RNG).
; The temporary MMU3 change has no stack access while it is in effect.
h_irq:
    push af
    push bc
    push de
    push hl
    ld bc,0x243B
    ld a,7
    out (c),a
    inc b
    in a,(c)
    and 3
    ld d,a
    dec b
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    ld e,a
    nextreg 0x53,15
    ld hl,(S_TICK)
    inc hl
    ld (S_TICK),hl
    ld a,d
    ld (S_IRQ_SPEED),a
    ld (S_ISP),sp
    ld sp,ISTK
    call hlib_pace_hold         ; the handler's time is in no window (DE kept)
    ld sp,(S_ISP)
    ld a,e
    nextreg 0x53,a
    pop hl
    pop de
    pop bc
    pop af
    IF SMOOTH
    jp h_irq_smooth
    ENDIF
speed_irq_original:
    IF NEG_SOUND == 0
    nextreg 7,0
    ENDIF
i_tail:
    jp 0xA404
h_irq_return:
    push af
    push bc
    push de
    push hl
    ld bc,0x243B
    ld a,0x53
    out (c),a
    inc b
    in a,(c)
    ld e,a
    nextreg 0x53,15
    ld a,(S_IRQ_SPEED)
    ld d,a
    ld (S_ISP),sp
    ld sp,ISTK
    call hlib_pace_resume       ; DE kept
    ld sp,(S_ISP)
    ld bc,0x243B                ; the library left another register selected; the main line reads NR 0x53 and NR 7 with this one (see ENTER)
    ld a,0x53
    out (c),a
    ld a,e
    nextreg 0x53,a
    ld a,d
    nextreg 7,a
    pop hl
    pop de
    pop bc
    pop af
irq_ei:
    ei
irq_reti:
    reti

; The wait before the player: until the original's time for this update has passed (the windows' lines x K + C, in
; hlib_pace_wait's sixteenths, interrupts left out as they lengthened the original's code too), or until PACE_CAP lines
; since the last wait, whichever comes first: the speed-up in busy scenes. A real-time deadline, as before, with an
; interrupt-clock + line reading. Waiting keeps interrupts enabled. No game delays, logic or sound routines are changed.
cap_wait:
    IF NEG_CAP
    ret
    ENDIF
    ld a,(S_CAP_VALID)
    or a
    jr z,.first
    call cap_lines              ; HL = lines since the last wait, 2048 and up when longer
    ld de,PACE_CAP
    ex de,hl
    or a
    sbc hl,de                   ; HL = lines left to the cap
    jr c,.over
    jr z,.over
    push hl
    ld hl,(S_WSUM)
    ld a,PACE_K
    call hlib_mul8
    ld de,PACE_C
    add hl,de
    pop de
    jr c,.tocap
    push hl
    ld b,4
.q  srl h
    rr l
    djnz .q
    or a
    sbc hl,de                   ; the original's lines - lines left to the cap
    pop hl
    jr nc,.tocap
    push hl
    call hlib_pace_open
    pop hl
    xor a                       ; the game at 3.5 MHz, or the target would halve: only drawing is ever faster
    call hlib_pace_wait
    jr .save
.tocap
    call cap_lines
    ld de,PACE_CAP
    or a
    sbc hl,de
    jr c,.tocap
.over
    ld hl,0                     ; past the cap: nothing carried, the speed-up is the point
    ld (HLIB_V_PACE+4),hl
    jr .save
.first
.save
    call cap_now
    ld (S_LAST_TICK),hl
    ld (S_LAST_LINE),de
    ld a,1
    ld (S_CAP_VALID),a
    ld hl,0
    ld (S_WSUM),hl
    ret
; HL = lines since the last wait, from the interrupt clock and the line, from 2048 not exact
cap_lines:
    call cap_now
    push de
    ld bc,(S_LAST_TICK)
    or a
    sbc hl,bc
    ld b,h
    ld c,l
    ld hl,0
.mul
    ld a,b
    or c
    jr z,.lines
    ld de,311
    add hl,de
    dec bc
    ld a,h
    cp 8
    jr nc,.big
    jr .mul
.lines
    pop de
    add hl,de
    ld de,(S_LAST_LINE)
    or a
    sbc hl,de
    ret nc
    ld hl,0                     ; before the line it started from: an interrupt not yet counted
    ret
.big
    pop de
    ret
cap_now:
.retry
    ld hl,(S_TICK)
    ld bc,0x243B
    ld a,0x1E
    out (c),a
    inc b
    in a,(c)
    and 1
    ld d,a
    dec b
    ld a,0x1F
    out (c),a
    inc b
    in a,(c)
    ld e,a
    dec b
    ld a,0x1E
    out (c),a
    inc b
    in a,(c)
    and 1
    cp d
    jr nz,.retry
    ld bc,(S_TICK)
    or a
    sbc hl,bc
    jr nz,.retry
    ld h,b
    ld l,c
    push hl
    ex de,hl
    ld de,63
    add hl,de
    ld de,311
    or a
    sbc hl,de
    jr nc,.raw
    add hl,de
.raw
    ex de,hl
    pop hl
    ret

    INCLUDE "lib/hlib_pace.asm"

; 0xD5C3 (was LD HL,$A404): the game's own IM 2 set-up (0xD5AE, at a new life, a new world) writes
; JP $A404 at 0xFDFD again, which would leave the view still. The same writes with the hook's address,
; then its RET; the instructions it replaces charged as they were (s_tail), the one added not.
h_setim:
s_tail:
    ld a,0xC3
    ld (0xFDFD),a
    ld hl,h_irq
    ld (0xFDFE),hl
    ld hl,0xA404
    ret

h_end:
    ASSERT h_end <= 0x3FF0
    SAVEBIN "OUT.bin", 0x2000, h_end-0x2000
