; Quazatron (Hewson, 1986, 48K) - colour v1.0, session 1: the scenery canvas on Layer 2. Facts: games/quazatron.md.
;
; Design (primary, built for smooth scrolling): the game's linear background (0x8300, 256 x 152, 1 bit) has a colour
; twin on a wrap-around Layer 2 canvas, 320 x 256 x 8 bits (banks L2BANK.., column-major: byte = x * 256 + y). The
; game's view sits at canvas origin (OX, OY); its in-place scroll moves become an origin change; only the strip the
; game pastes (C1A5) is written. A pixel's colour is the ROLE of the drawing list that last cleared it to paper
; (scenery lists: masks draw the surfaces), kept in a tag strip (TAGS, column-major, 152 bytes a column) that mirrors
; the game's 32-pixel column strip (0x8080). Ink pixels hold 0..15, the ZX ink of the screen cell they show in
; (black on the deck, the void's colour below it), set at the commit (C05A, after the game's attributes).
; Layer 2 covers the play area (clip) above the ULA, so the ULA play area is hidden; the panel below is the ULA's.
; Droids become hardware sprites placed from the same origin (session 2); smooth mode moves the shown offset.
;
; Sites (original bytes checked by quazatron.py):
;   BE2E CD 7D B0  CALL B07D (scenery list into the strip)  -> CALL t_list   (tags after the game's own draw)
;   BE82 CD 44 C0  CALL C044 (strip clear)                  -> CALL t_clr
;   BFEC, BFFB CD A5 C1  CALL C1A5 (strip paste)            -> CALL t_paste  (tags -> canvas at the origin)
;   E10E 21 FF 94 / E11D 21 00 84 / E12C 21 02 83 / E146 21 FD 95  the scroll moves -> JP t_sd / t_su / t_sl / t_sr
;   C05A 11 00 83  background to screen + attributes        -> JP t_c05a     (commit: offset, inks, Layer 2 on)
;   B2C9 21 00 40  screen clear                             -> JP t_cls      (Layer 2 off)
;   B1FB ED 53 63 B2  the printer                           -> JP t_prn      (Layer 2 off when it prints in the play area)
; Memory: trampolines in alt ROM image 1 (0x386E-); code and state in Next page HPAGE, mapped at slot 2 (0x4000) only
; inside a hook (the ISR at E6E6 / BD2D never touches 0x4000-0x5FFF); canvas pages at slot 6 (0xC000) only inside a
; hook's work (the ISR never touches 0xC000-0xDFFF). The game's stack is at 0x61xx (slot 3): never remapped.
; R: the game reads R (B5B1, in the ISR); every trampoline brackets its extra M1s with HLIB_R_IN / HLIB_R_OUT.
; Speed: the work runs at 28 MHz, the caller's speed restored (hlib_speed).
; Pace (session 2, target ORIGINAL): every hook's added time goes to a debt (its 28 MHz work measured on the video line,
; its entry and exit at the caller's clock as a constant) that the game's own delay (DD80) repays: t_dly starts the
; loop shorter, R kept exact. Fast scroll off: each scroll move runs at 28 MHz in a pace window that lasts the
; original LDDR's exact time less the debt. Sprite patterns: an image-keyed slot cache (21 slots of 3 patterns).
; DD8A 67 2E 00  LD H,A / LD L,0 (the delay loop's start)  -> JP t_dly

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"

HPAGE   EQU 26                  ; bank 13 lower half
ULAPAGE EQU 10
L2BANK  EQU 18                  ; Layer 2 canvas: banks 18-22 = pages 36-45
L2PAGE  EQU 36
TS      EQU 152                 ; tag strip column stride
R_FLOOR EQU 16                  ; palette: 0-15 ZX inks, 16 floor, 17 wall, 18 ramp, 19 fringe, 20 face (the ink inside a
R_WALL  EQU 17                  ; wall part), 21 arrow, 22 object, 23 pad, 24 console screen (its OR ink), 25 bezel
R_FACE  EQU 20
R_SCREEN EQU 24
R_CONSOLE EQU 25

TCOL    EQU 0x4C00              ; 32 words: TAGS + px * TS
PALINIT EQU 0xD080              ; 32 Layer 2 palette entries (2 bytes each) in the setup block, from quazatron.py
ROWBUF  EQU 0x4C40              ; 32 attributes
DECKPAL EQU 0xD100              ; in page S0 at slot 6: 8 papers x 5 entries (16-20) x 2 bytes, from quazatron.py
SPOS    EQU 0xD000              ; in page S0 at slot 6: per sprite group, base X (2), base Y (2) at the game origin
ROLETAB EQU 0xD800              ; in page S0 at slot 6: (list - 0x9600) >> 3 -> role, from quazatron.py sprite_store
VSPD    EQU 0x4BC0
HLIB_V_R EQU 0x4BC1             ; 3
OX      EQU 0x4BC4              ; 2: canvas x of the view's left edge (0-319)
OY      EQU 0x4BC6              ; canvas y of the view's top line
L2ON    EQU 0x4BC7
DECKP   EQU 0x4BC8              ; deck attribute last programmed (0xFF: none)
SLOT6   EQU 0x4BC9
LST     EQU 0x4BCA              ; 2
ROLE    EQU 0x4BCC
OPF     EQU 0x4BCD              ; the part's flags
P0      EQU 0x4BCE              ; 2: TAGS + (x + jstart) * TS
JST     EQU 0x4BD0              ; first visible bit of the part
JN      EQU 0x4BD1              ; visible bits
TROW    EQU 0x4BD2              ; tag row of the part's first drawn row
NROWS   EQU 0x4BD3
CX      EQU 0x4BD4              ; 2
CY      EQU 0x4BD6
PW      EQU 0x4BD7
CR      EQU 0x4BD8              ; commit: view cell row
CC      EQU 0x4BD9              ; commit: view cell column
TINK    EQU 0x4BDA
SPX     EQU 0x4BDB              ; 2: the record's x (signed)
SPY     EQU 0x4BDD              ; the record's y
GRP     EQU 0x4BDE              ; sprite groups (3 sprites, 3 patterns each) used this update
GPREV   EQU 0x4BDF              ; ... last update
TYP     EQU 0x4BE0              ; the record's A000 type (plate index)
REC     EQU 0x4BE1              ; 2
DRV     EQU 0x4BE3              ; 2: the player's drive list
NREC    EQU 0x4BE5
VSPD2   EQU 0x4BE6              ; the caller's speed at an outer fast-section hook
GSPD    EQU 0x4BE7              ; the game's speed (the last outer latch): the ISR body runs at it
VFASTT  EQU 0x4BE8              ; 3: scroll steps at 28 MHz (fast-scroll option), 0: off (from quazatron.py; the toggle)
VFAST   EQU 0x4CE1              ; in use: VFASTT from the first commit on, 0 in monochrome (session 3)
VCENTRE EQU 0x4CE2              ; session 4: 1 = Centred view (the toggle: with E0DC / E1B3 patched to c_pre); it implies
                                ; fast scroll and the smooth display (p_pre sets VFASTT / VSMOOTH at each commit)
CWD     EQU 0x4CE3              ; 2: the debt when a Centred step's window opened (mv_in); cw_close sets DEBT from it
GXI     EQU 0x4CE5              ; glide (page 27): x: frames between the last two x commits (6-32)
GXA     EQU 0x4CE6              ;   frames since the last x commit
GXF     EQU 0x4CE7              ;   x fraction (1/256 px)
GYI     EQU 0x4CE8              ;   y: the same
GYA     EQU 0x4CE9
GYF     EQU 0x4CEA
LTX     EQU 0x4CEB              ; 2: TX the glide last saw
LTY     EQU 0x4CED              ;   TY
GPAGE   EQU 27                  ; page 27 (bank 13 upper half): the glide, mapped at slot 6 only inside isr_step
VMONO   EQU 0x4CE0              ; 1: monochrome (the base of the .nxc: Layer 2 and the sprites never on, the ULA shows the
                                ; game's own picture; the hooks and the limiter run as in colour), 0: colour (the set)
VSMOOTH EQU 0x4BE9              ; 1: smooth display (the shown origin glides to the game's), 0: off
DX      EQU 0x4BEA              ; 2: the shown origin
DY      EQU 0x4BEC
SDX     EQU 0x4BED              ; 2: OX - DX, signed (-160..159)
SDY     EQU 0x4BEF              ; 2: OY - DY, signed
XHB     EQU 0x4BF1              ; put3: X bit 8
ISRSPD  EQU 0x4BF2              ; t_isr: the interrupted code's speed
TX      EQU 0x4BF3              ; 2: the origin at the last commit (the shown origin's target; sprites are placed
TY      EQU 0x4BF5              ;    from the view the game last drew, which is this one)
DEBT    EQU 0x4BF6              ; 2: the pace limiter's debt, 1/16 video lines (14 T at 3.5 MHz) of hook time not yet repaid
DST     EQU 0x4BF8              ; 2: the video line at the open debt window's start
ISRL    EQU 0x4BFA              ; 2: the video line at an ISR's start inside the hook page
DH0     EQU 0x4BFC              ; t_dly: the delay's outer count
GIMG    EQU 0x4BFD              ; group: the image number
MVE     EQU 0x4C80              ; 2: a move's pace window: lines elapsed (ISR bodies left out)
MVT     EQU 0x4C82              ; 2: its target (1/16 lines)
MVP     EQU 0x4C84              ; polls left with the line counter still (no counter: give up)
MVL     EQU 0x4C85              ; 2: the last line read in the wait
DEBTCAP EQU 312 * 16 * 4        ; four frames: crowds (6+ blocks, no delay) repaid by the next updates with a delay
O_MOVEV EQU (30 + 21 * 0x1200 - 5) / 14       ; a scroll move's original time at 3.5 MHz (LD HL / DE / BC, LDDR or
O_MOVEH EQU (30 + 21 * 0x12FE - 5) / 14       ; LDIR; 0x8300-0x95FF and the code are uncontended), 1/16 lines
SKEY    EQU 0x4C60              ; 21: the image (+1) each pattern slot (3 patterns) holds, 0: none. The images are
                                ; immutable (built into the sprite store): a group whose image is in a slot uses it
SUSE    EQU 0x4C90              ; 21: the update (STAMP) a slot was last used in: never replaced in the same update
GPAT    EQU 0x4CB0              ; 21: each group's first pattern (3 x its slot), for the smooth step's put3
SCLK    EQU 0x4CC8              ; the next slot to try for a new image (clock)
STAMP   EQU 0x4CC9              ; this update's number (p_spr)
PPAT    EQU 0x4CCA              ; put3: the first sprite's pattern
HLIB_PACE_NL EQU 312            ; 48K timing (z80tonex: NR 3 = 48K)
; session 3: game-routine pace windows (fw_*). The game's own E656 (block blits, every update), and with fast scroll off
; a scroll step's BE38 (strip render) and its C05A copy (from DD9A), run at 28 MHz; their time there (WP, ISR bodies and
; nested hook work left out) x K/16 is the original's time (WO); the saving repays DEBT, and what DEBT does not take is
; waited out on the video line. K per routine: JNext's ratio of the original's time at 3.5 MHz (48K contention) to the
; routine's at 28 MHz, measured in session 3 (work/s3/kcal.py), rounded down (never faster than the original).
WOPEN   EQU 0x4CD0              ; 0: no window, 1: the game routine runs (nested hooks: WNEST), 2: the hook's own work
WK      EQU 0x4CD1              ; K (x 16)
WNEST   EQU 0x4CD6              ; 2: nested / own hook time inside the window (1/16 lines)
WO      EQU 0x4CD8              ; 2: the original's time (1/16 lines)
WP      EQU 0x4CDA              ; 2: the routine's time at 28 MHz
WT      EQU 0x4CDC              ; 2: fw_wait's target
        IFNDEF KSPR
KSPR    EQU 104                 ; E656 (JNext: 98.8 off, 102.1 on over 1,051 calls)
KBS     EQU 98                  ; BE38: not used (its ratio varies 5 to 6 with the strip: it runs at the caller's speed)
KCPY    EQU 141                 ; C05A (JNext: the copy from DD9A, about 170k T without its interrupts, against WP 1,360)
        ENDIF
C_FW    EQU 34                  ; a window hook's entry and exit at the caller's clock (about 480 T)
; the hooks' unmeasured parts (1/16 lines): their entry and exit at the caller's clock, counted in the simulator
; (session 2: work/s2/calib.py; median extra T at 3.5 MHz / 14, rounded down, plus the 28 MHz part outside a window)
        IFNDEF C_LIST
C_LIST  EQU 34                  ; t_list 484 T
C_TW    EQU 33                  ; t_clr, t_paste, t_spr 463 T
C_C05A  EQU 68                  ; t_c05a 953 T
C_MOVE  EQU 15                  ; the moves outside their pace window (about 300 T; the window has the rest)
C_BS    EQU 0                   ; t_bs: its own part is small (its nested hooks count their own)
C_ISR   EQU 37                  ; t_isr from game code 521 T (every frame)
C_CLS   EQU 44                  ; t_prn 630-711 T (t_cls clears the debt)
KDLY    EQU 40                  ; t_dly 652 T, in delay steps (16 T)
        ENDIF
S0      EQU 46                  ; sprite store: page 46 = (list - 0x9C00) >> 1 -> 0-3 enemy frame / image / 255,
                                ; pages 47.. = images (16 x 48 x 8 bits, 10 a page), from quazatron.py sprite_store
MAXG    EQU 21
FLAGS   EQU 0xD200              ; in page S0 at slot 6: 40 x 32 canvas cells, the ink their ink bytes hold (0xFF: unknown)
TAGS    EQU 0x4D00              ; 32 columns x 152 rows

; game variables
G_AF0E  EQU 0xAF0E
G_AF10  EQU 0xAF10
G_AF14  EQU 0xAF14
G_AF15  EQU 0xAF15
G_AF16  EQU 0xAF16
G_AF17  EQU 0xAF17
G_AF2D  EQU 0xAF2D
G_DECK  EQU 0xB044

; ============================================================================================================
        ORG 0x4000
        INCLUDE "lib/hlib_r.asm"        ; HLIB_R_IN / OUT, hlib_r_set

; p_tags: HL = the list just drawn into the strip. Repeat its geometry (B07F) into the tag strip: mask bits -> the
; list's role, OR bits -> 0 (ink), overwrite bits -> ink / role. A part of height 0 ends the list, as in B0EC.
p_tags: ld (LST),hl
        ld de,-0x9600
        add hl,de
        jr nc,.floor
        ld a,h
        cp 6
        jr nc,.floor
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ld h,high ROLETAB
        nextreg 0x56,S0         ; (t_list runs inside BE38: slot 6 is the game's page 0)
        ld a,(hl)
        nextreg 0x56,0
        jr .rok
.floor: ld a,R_FLOOR
.rok:   ld (ROLE),a
        ld hl,(LST)
        ld b,(hl)
        inc hl
.part:  push bc
        ld a,(hl)               ; x offset (signed)
        ld e,a
        rla
        sbc a,a
        ld d,a
        push hl
        ld hl,(G_AF0E)
        add hl,de               ; HL = x
        ld b,h
        ld c,l
        ld de,7
        add hl,de
        ld a,h
        or a
        jr nz,.xskip
        ld a,l
        cp 39
        jr nc,.xskip
        ; visible bits: jstart = max(0, -x), jend = min(8, 32 - x)
        xor a
        bit 7,b
        jr z,.js
        ld a,c
        neg                     ; -x (1..7)
.js:    ld (JST),a
        ld e,a                  ; E = jstart
        ld a,32
        sub c                   ; 32 - x (x in -7..31 -> 1..39)
        cp 8
        jr c,.je
        ld a,8
.je:    sub e
        ld (JN),a
        ld a,c
        add a,e                 ; x + jstart (0..31)
        add a,a
        add a,low TCOL
        ld l,a
        ld h,high TCOL
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a
        ld (P0),hl
        pop hl
        inc hl
        ld a,(G_AF10)
        add a,(hl)
        ld d,a                  ; D = row
        inc hl
        ld a,(hl)
        inc hl                  ; HL = glyph
        ld (OPF),a
        and 63
        jr z,.endl              ; RET Z in the original
        ld e,a                  ; E = height
        push hl
        ld c,e
        ld b,0
        add hl,bc
        ex (sp),hl              ; (SP) = next part, HL = glyph
        ld a,(G_AF16)
        cp d
        jr nc,.noclip
        ld a,d
        add a,e
        jr nc,.vskip
        jr z,.vskip
        ld e,a                  ; rows left
        ld a,d
        neg
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a                  ; glyph += -D
        ld d,0
.noclip:
        ld a,(G_AF17)
        sub d
        cp e
        jr nc,.rows
        ld e,a
.rows:  ld a,d
        ld (TROW),a
        ld a,e
        ld (NROWS),a
        or a
        jr z,.vskip
        call rowloop
.vskip: pop hl                  ; next part
        pop bc
        dec b
        jp nz,.part
        ret
.xskip: pop hl                  ; the x byte: skip y, read the height, as B178
        inc hl
        inc hl
        ld a,(hl)
        and 63
        inc hl
        ld e,a
        ld d,0
        add hl,de
        pop bc
        dec b
        jp nz,.part
        ret
.endl:  pop bc
        ret

; rowloop: HL = the first drawn glyph row; TROW, NROWS, P0, JST, JN, OPF, ROLE set.
rowloop:
        ld a,(NROWS)
        ld b,a
.row:   push bc
        ld c,(hl)               ; glyph byte
        inc hl
        push hl
        ld a,(JST)
        or a
        jr z,.sh0
        ld b,a
.shl:   sla c
        djnz .shl
.sh0:   ld hl,(P0)
        ld a,(TROW)
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld de,TS
        ld a,(JN)
        ld b,a
        ld a,(OPF)
        bit 7,a
        jr nz,.mask
        bit 6,a
        jr nz,.set
.or:    ld a,(ROLE)
        cp R_CONSOLE
        ld a,0
        jr nz,.or0
        ld a,R_SCREEN           ; a console's OR ink is its screen
.or0:   sla c
        jr nc,.or1
        ld (hl),a
.or1:   add hl,de
        djnz .or0
        jr .next
.mask:  ld a,(ROLE)
        cp R_WALL
        jr z,.mw
.mk:    sla c
        jr nc,.mk1
        ld (hl),a
.mk1:   add hl,de
        djnz .mk
        jr .next
.mw:    sla c                   ; a wall part: its 0 bits over ink become the face tone
        jr c,.mw1
        inc (hl)
        dec (hl)
        jr nz,.mw2
        ld (hl),R_FACE
        jr .mw2
.mw1:   ld (hl),a
.mw2:   add hl,de
        djnz .mw
        jr .next
.set:   ld a,(ROLE)
.st:    sla c
        jr nc,.st1
        ld (hl),0
        jr .st2
.st1:   ld (hl),a
.st2:   add hl,de
        djnz .st
.next:  ld hl,TROW
        inc (hl)
        pop hl
        pop bc
        djnz .row
        ret

; p_clr: the strip was cleared to ink (C044): tag rows 0 .. AF17-1 of all 32 columns = 0.
p_clr:  ld a,(G_AF17)
        or a
        ret z
        ld hl,TCOL
        ld b,32
.c:     push bc
        ld e,(hl)
        inc l
        ld d,(hl)
        inc l
        push hl
        ex de,hl
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        ld a,(G_AF17)
        dec a
        jr z,.c1
        ld c,a
        ld b,0
        ldir
.c1:    pop hl
        pop bc
        djnz .c
        ret

; rd56: A = NR 0x56
rd56:   ld bc,0x243B
        ld a,0x56
        di
        out (c),a
        inc b
        in a,(c)
        ei
        ret

; p_paste: after C1A5: strip columns 0..W-1 (W = 16 if AF2D = 1, else 32), rows 0..AF17-1 -> canvas at
; (OX + AF14 * 8 + px, OY + AF15 + row); the canvas cells touched -> FLAGS 0xFF.
p_paste:
        call rd56
        ld (SLOT6),a
        ld a,(G_AF2D)
        cp 1
        ld a,16
        jr z,.w
        ld a,32
.w:     ld (PW),a
        ld a,(G_AF14)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(OX)
        add hl,de
        call mod320
        ld (CX),hl
        ld a,(OY)
        ld b,a
        ld a,(G_AF15)
        add a,b
        ld (CY),a
        ld a,(G_AF17)
        or a
        jp z,.done
        ld hl,TCOL
        ld a,(PW)
        ld b,a
.col:   push bc
        push hl                 ; TCOL entry
        ld hl,(CX)
        ld a,l                  ; page = L2PAGE + (cx >> 5)
        srl h
        rra
        srl h
        rra
        srl h
        rra
        srl h
        rra
        srl h
        rra
        add a,L2PAGE
        nextreg 0x56,a
        ld hl,(CX)
        ld a,l
        and 31
        add a,0xC0
        ld d,a
        ld a,(CY)
        ld e,a
        pop hl
        push hl
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a                  ; HL = tag column
        ld a,(G_AF17)           ; the column: LDIR, split where the canvas y wraps (256) inside its column
        ld c,a
        ld a,e
        neg                     ; bytes to the column's end (0: 256)
        jr z,.one
        cp c
        jr nc,.one
        ld b,a
        ld a,c
        sub b
        push af                 ; the rest, from y 0
        ld c,b
        ld b,0
        ldir
        dec d                   ; DE ran into the next column: back to this one's y 0
        pop af
        ld c,a
.one:   ld b,0
        ldir
        ld hl,(CX)              ; next canvas column
        inc hl
        call mod320
        ld (CX),hl
        pop hl
        inc l
        inc l
        pop bc
        djnz .col
        ; flags: cell columns (cx0 >> 3) .. + W/8 - 1, cell rows (CY >> 3) .. ((CY + rows - 1) >> 3), wrapping
        ld a,(PW)
        rrca
        rrca
        rrca
        and 7
        ld b,a                  ; cell columns
        ld hl,(CX)              ; CX is now cx0 + W: step back
        ld a,(PW)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        jr nc,.f0
        ld de,320
        add hl,de
.f0:    ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        ld c,a                  ; C = first cell column (0..39)
        nextreg 0x56,S0         ; FLAGS
.fc:    push bc
        ld a,(CY)
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; first cell row
        ld a,(G_AF17)
        dec a
        ld d,a
        ld a,(CY)
        and 7
        add a,d                 ; offset of the last row from the first cell's top
        rrca
        rrca
        rrca
        and 31
        inc a
        ld b,a                  ; cell rows touched
.fr:    push bc
        push de
        ld a,e
        and 31
        call cellptr            ; HL = FLAGS + row * 40 + C
        ld (hl),0xFF
        pop de
        inc e
        pop bc
        djnz .fr
        pop bc
        inc c
        ld a,c
        cp 40
        jr c,.fc1
        ld c,0
.fc1:   djnz .fc
.done:  ld a,(SLOT6)
        nextreg 0x56,a
        ret

; cellptr: A = cell row (0..31), C = cell column (0..39) -> HL = FLAGS + A * 40 + C. DE lost.
cellptr:
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; *8
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl               ; *32
        add hl,de               ; *40
        ld e,c
        ld d,0
        add hl,de
        ld de,FLAGS
        add hl,de
        ret

; mod320: HL in 0..639 -> HL mod 320
mod320: push de
        ld de,320
        or a
        sbc hl,de
        jr nc,.m
        add hl,de
.m:     pop de
        ret

; p_off: Layer 2 off (outside play)
p_off:  xor a
        ld (L2ON),a
        nextreg 0x15,0
        ld bc,0x123B
        out (c),a
        ret

; p_pre: after p_inks (C05A done): the shown origin (snap, or left to the smooth step), the deck's palette, Layer 2
; and the sprites on.
p_pre:  ld a,(VCENTRE)          ; session 4: Centred view implies fast scroll and the smooth display
        or a
        jr z,.nc
        ld hl,0x0103
        ld (VFASTT),hl
.nc:    call rd56
        ld (SLOT6),a
        ld hl,(OX)              ; the committed origin
        ld (TX),hl
        ld a,(OY)
        ld (TY),a
        call offs
        ld a,(VSMOOTH)
        or a
        jr z,.snap
        ld a,(L2ON)
        or a
        jr z,.snap
        ld hl,(SDX)             ; smooth: snap only on a jump (more than 64 px or 48 lines)
        bit 7,h
        jr z,.p1
        call neghl
.p1:    ld de,65
        or a
        sbc hl,de
        jr nc,.snap
        ld hl,(SDY)
        bit 7,h
        jr z,.p2
        call neghl
.p2:    ld de,49
        or a
        sbc hl,de
        jr c,.nos
.snap:  ld hl,(OX)
        ld (DX),hl
        ld a,(OY)
        ld (DY),a
        call wregs
        call offs
.nos:   ; deck palette (roles 16-20) when the deck's attribute changes
        ld a,(G_DECK)
        ld hl,DECKP
        cp (hl)
        jr z,.pal
        ld (hl),a
        rrca
        rrca
        rrca
        and 7                   ; paper
        ld b,a
        add a,a
        add a,a
        add a,b
        add a,a                 ; * 10 bytes
        add a,low DECKPAL
        ld l,a
        ld h,high DECKPAL
        nextreg 0x56,S0
        nextreg 0x43,0x10
        nextreg 0x40,R_FLOOR
        ld b,10
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        ld a,(SLOT6)
        nextreg 0x56,a
.pal:   ld a,(VMONO)
        or a
        ret nz                  ; monochrome: Layer 2, the sprites and fast scroll never on
        ld a,(VFASTT)
        ld (VFAST),a
        ld a,(L2ON)
        or a
        ret nz
        inc a
        ld (L2ON),a
        nextreg 0x15,0x01       ; sprites visible, S L U
        ld a,2
        ld bc,0x123B
        out (c),a
        ret

; p_inks: after C05A + C0C3 (the attributes are current): every view cell's ink bytes = its attribute's ink.
p_inks: call rd56
        ld (SLOT6),a
        ld hl,(OX)              ; the view's first canvas cell: column OX >> 3 (0-39), row (OY >> 3) & 31
        ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        ld (CC),a
        ld a,(OY)
        rrca
        rrca
        rrca
        and 31
        ld (TINK),a             ; (TINK: the canvas row of view row CR)
        xor a
        ld (CR),a
.crow:  ; this row's 32 attributes -> ROWBUF (the ULA page at slot 6), then FLAGS (S0) mapped for the row's walk
        nextreg 0x56,ULAPAGE
        ld a,(CR)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xD800
        add hl,de
        ld de,ROWBUF
        ld bc,32
        ldir
        nextreg 0x56,S0
        ld a,(CC)
        ld c,a                  ; C = canvas column
        ld a,(TINK)
        call cellptr            ; HL = FLAGS + row * 40 + C
        ld de,ROWBUF
        ld b,32
.ccol:  ld a,(de)               ; the attribute's ink, 0-15
        and 0x47
        cp 0x40
        jr c,.nb
        sub 0x38
.nb:    cp (hl)
        jr z,.same
        ld (hl),a
        push bc
        push de
        push hl
        ld b,a
        ld a,(TINK)
        ld d,a
        ld a,b
        call recell             ; C = cell column, D = cell row, A = ink
        nextreg 0x56,S0
        pop hl
        pop de
        pop bc
.same:  inc e                   ; ROWBUF (0x4C40-0x4C5F: E never wraps)
        inc hl
        inc c
        ld a,c
        cp 40
        jr c,.c1
        ld c,0
        push de
        ld de,-40
        add hl,de
        pop de
.c1:    djnz .ccol
        ld a,(TINK)
        inc a
        and 31
        ld (TINK),a
        ld hl,CR
        inc (hl)
        ld a,(hl)
        cp 19
        jp c,.crow
        ld a,(SLOT6)
        nextreg 0x56,a
        ret

; recell: canvas cell (C column, D row): every ink byte (< 16) of its 8 x 8 -> A. Maps its page at slot 6.
recell: ld e,a
        ld a,c
        rrca
        rrca
        and 0x3F
        add a,L2PAGE
        nextreg 0x56,a
        ld a,c
        and 3
        add a,a
        add a,a
        add a,a
        add a,0xC0
        ld h,a                  ; column (C & 3) * 8 -> 0xC000 + that * 256
        ld a,d
        add a,a
        add a,a
        add a,a
        ld l,a                  ; row * 8
        ld b,8
.k:     push bc
        push hl
        ld b,8
.j:     ld a,(hl)
        cp 16
        jr c,.j0
        cp R_FACE               ; a wall face's ink: the void's ink in a void cell, kept on the deck (black ink,
        jr nz,.j1               ; bright or not)
        ld a,e
        and 7
        jr z,.j1
.j0:    ld (hl),e
.j1:    inc l
        djnz .j
        pop hl
        inc h
        pop bc
        djnz .k
        ret

;p_spr: after E656 (the blocks are on the screen): every draw record (A320, AF09 of them) as sprites, the last
; record (drawn last, in front) first, so it takes the lowest sprite numbers (sprite 0 on top). Enemies: one group
; (image 4 (type - 1) + frame); the player: a group per part (second weapon, dome + AFA4, weapon, drive, chassis);
; others: the record's list. Groups not used since the last update are hidden.
p_spr:  ld a,(L2ON)
        or a
        ret z
        call offs
        ld hl,(0xDDAE)          ; the drive list (DDAE is in slot 6: read before any mapping)
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (DRV),hl
        call rd56
        ld (SLOT6),a
        ld hl,STAMP
        inc (hl)
        xor a
        ld (GRP),a
        ld a,(0xAF09)
        cp 8
        jr c,.n
        ld a,7
.n:     or a
        jp z,.hide
        ld (NREC),a
        dec a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld de,0xA320
        add hl,de
.rec:   ld (REC),hl
        inc hl
        ld c,(hl)               ; flags
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (SPX),de
        inc hl
        ld a,(hl)
        ld (SPY),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the record's list
        inc hl
        ld a,(hl)
        ld (TYP),a
        bit 7,c
        jr nz,.pl
        ld b,0
        call group
        jr .nx
.pl:    xor a
        ld (TYP),a
        ld hl,(0xAF9C)
        call grp_ind
        ld de,(0xAF9E)
        ld a,(0xAFA4)
        ld b,a
        call group
        ld hl,(0xAF9A)
        call grp_ind
        ld de,(DRV)
        ld b,0
        call group
        ld hl,(0xAFA0)
        call grp_ind
.nx:    ld hl,(REC)
        ld de,-8
        add hl,de
        ld a,(NREC)
        dec a
        ld (NREC),a
        jr nz,.rec
.hide:  ld a,(GPREV)
        ld hl,GRP
        sub (hl)
        jr c,.hd
        jr z,.hd
        ld e,a                  ; groups to hide
        ld a,(hl)
        ld d,a
        add a,a
        add a,d                 ; first sprite
        ld bc,0x303B
        out (c),a
        ld a,e
        add a,a
        add a,e
        ld e,a                  ; sprites to hide
        ld c,0x57
.h1:    xor a
        out (c),a
        out (c),a
        out (c),a
        out (c),a               ; attr 3 = 0: invisible, 4-byte form
        dec e
        jr nz,.h1
.hd:    ld a,(GRP)
        ld (GPREV),a
        ld a,(SLOT6)
        nextreg 0x56,a
        ret

grp_ind:                        ; HL -> a word = the list; B = 0
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld b,0
; group: DE = list, B = rows down (the dome's AFA4), TYP. One image -> 3 patterns, 3 sprites.
group:  ld a,(GRP)
        cp MAXG
        ret nc
        ld hl,-0x9C00
        add hl,de
        ret nc
        ld a,h
        cp 0x14
        ret nc
        srl h
        rr l
        ld a,h
        add a,0xC0
        ld h,a
        nextreg 0x56,S0
        ld a,(hl)
        cp 255
        ret z
        cp 4
        jr nc,.img
        ld c,a
        ld a,(TYP)
        dec a
        cp 32
        ret nc
        add a,a
        add a,a
        add a,c
.img:   ld (GIMG),a
        ld c,0
.d10:   cp 10
        jr c,.dd
        sub 10
        inc c
        jr .d10
.dd:    ld e,a
        add a,a
        add a,e
        add a,0xC0
        ld h,a
        ld l,0                  ; HL = 0xC000 + (n % 10) * 768
        ld a,c
        add a,S0 + 1
        nextreg 0x56,a
        ld a,(GRP)
        ld e,a
        add a,a
        add a,e
        ld e,a                  ; E = first pattern / sprite
        push bc
        push hl
        call slot_of            ; A = 3 x the slot holding the image, Z = it is there already
        pop hl
        push af
        ld (PPAT),a
        ld a,(GRP)
        add a,low GPAT
        ld e,a
        ld d,high GPAT
        ld a,(PPAT)
        ld (de),a
        pop af
        jr z,.hit               ; the slot holds this image: no upload
        ld bc,0x303B
        out (c),a
        ld c,0x5B               ; only the low byte is decoded: B may count down
        ld d,24
.u:     DUP 32
        outi                    ; 16 T a byte (OTIR 21)
        EDUP
        dec d
        jr nz,.u
.hit:   pop bc                  ; B = rows down
        ; base Y = y (signed: >= 200 is above the top) - 8 + B; base X = x + 24 (at the game's origin)
        ld a,(SPY)
        ld l,a
        ld h,0
        cp 200
        jr c,.y
        dec h
.y:     ld a,b
        sub 8
        ld c,a
        sbc a,a
        ld b,a
        add hl,bc
        push hl
        ld hl,(SPX)
        ld bc,24
        add hl,bc
        ex de,hl                ; DE = base X
        pop bc                  ; BC = base Y
        nextreg 0x56,S0         ; SPOS[GRP] = base X, base Y (the smooth display's frame step moves them)
        ld a,(GRP)
        add a,a
        add a,a
        ld l,a
        ld h,high SPOS
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld (hl),c
        inc l
        ld (hl),b
        ld hl,(SDX)
        add hl,de
        ex de,hl
        ld hl,(SDY)
        add hl,bc
        ld a,(GRP)
        ld b,a
        add a,a
        add a,b
        call put3
        ld hl,GRP
        inc (hl)
        ret

; offs: SDX = OX - DX normalised to -160..159, SDY = OY - DY (signed 8 -> 16). AF, DE, HL lost.
offs:   ld hl,(TX)
        ld de,(DX)
        or a
        sbc hl,de               ; -319..319
        ld de,160
        bit 7,h
        jr nz,.neg
        push hl
        or a
        sbc hl,de
        pop hl
        jr c,.x
        ld de,-320
        add hl,de
        jr .x
.neg:   add hl,de               ; HL + 160 < 0 -> HL + 320
        bit 7,h
        ld de,-160
        add hl,de
        jr z,.x
        ld de,320
        add hl,de
.x:     ld (SDX),hl
        ld a,(DY)
        ld e,a
        ld a,(TY)
        sub e
        ld l,a
        rla
        sbc a,a
        ld h,a
        ld (SDY),hl
        ret

neghl:  xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
        ret

; spd_fast: latch the caller's speed (VSPD2, GSPD), then NR 7 = it | VFAST. The port read is DI-protected (the ISR
; hook never touches the ports, but this keeps the read atomic). AF, BC lost.
spd_fast:
        call spd_latch
        ld b,a
        ld a,(VFAST)
        or b
        nextreg 0x07,a
        ret

; spd_latch: VSPD2 = GSPD = A = the caller's speed (NR 7 bits 1:0); the speed is not changed. AF, BC lost.
spd_latch:
        ld bc,0x243B
        ld a,7
        di
        out (c),a
        inc b
        in a,(c)
        ei
        and 3
        ld (VSPD2),a
        ld (GSPD),a
        ret

; spd_back: NR 7 = VSPD2. Keeps every register and flag.
spd_back:
        push af
        ld a,(VSPD2)
        nextreg 0x07,a
        pop af
        ret

; wregs: the Layer 2 scroll registers from the shown origin: X = DX - 32 (mod 320), Y = DY - 32. AF, DE, HL lost.
wregs:  ld hl,(DX)
        ld de,32
        or a
        sbc hl,de
        jr nc,.x
        ld de,320
        add hl,de
.x:     ld a,l
        nextreg 0x16,a
        ld a,h
        and 1
        nextreg 0x71,a
        ld a,(DY)
        sub 32
        nextreg 0x17,a
        ret

; isr_step: from the ISR hook, in game code (page mapped at slot 2 by t_isr): the smooth display's frame step at
; 28 MHz, then NR 7 = the game's speed for the ISR body. Keeps IX, IY, the alternate set; AF, BC, DE, HL lost.
isr_step:
        nextreg 0x07,3
        ld a,(WOPEN)            ; a game routine's pace window: its time so far counted, the ISR's left out (wskipc)
        or a
        call nz,mvtick
        call dbg_open
        ld a,(VSMOOTH)
        or a
        jp z,.done
        ld a,(L2ON)
        or a
        jp z,.done
        call offs
        nextreg 0x56,GPAGE      ; session 4: the glide (v1.0's, or Centred view's) runs from page 27 at slot 6
        call glide
        nextreg 0x56,0
.w:     call wregs
        call offs
        ld a,(GPREV)
        or a
        jr z,.done
        nextreg 0x56,S0
        ld b,a
        ld hl,SPOS
        xor a
.g:     push bc
        push af                 ; A = group
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        ld hl,(SDX)
        add hl,de
        ex de,hl                ; DE = X
        pop hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        push hl
        ld hl,(SDY)
        add hl,bc               ; HL = Y
        pop bc                  ; BC = SPOS pointer
        pop af
        push af
        push bc
        push hl
        push af
        add a,low GPAT
        ld l,a
        ld h,high GPAT
        ld a,(hl)
        ld (PPAT),a
        pop af
        pop hl
        ld b,a
        add a,a
        add a,b                 ; first sprite = 3 g
        call put3
        pop hl
        pop af
        inc a
        pop bc
        djnz .g
        nextreg 0x56,0
.done:  ld a,C_ISR               ; (the same at any interrupted clock: the hook's state never depends on it)
        call dbg_close_r
        ld a,(GSPD)
        nextreg 0x07,a
        ret

; put3: A = first sprite (= its first pattern), DE = X, HL = Y of the top one: 3 sprites, 5-byte attributes,
; 8-bit patterns, stacked 16 lines apart. AF, BC, HL lost.
put3:   push de
        push af
        ld a,d
        and 1
        ld (XHB),a
        pop af
        ld bc,0x303B
        out (c),a
        ld a,(PPAT)             ; the first sprite's pattern (the image's slot)
        ld d,a
        ld b,3
        ld c,0x57
.k:     out (c),e
        out (c),l
        ld a,(XHB)
        out (c),a
        ld a,d
        or 0xC0
        out (c),a
        inc d
        ld a,h
        and 1
        out (c),a
        push de
        ld de,16
        add hl,de
        pop de
        djnz .k
        pop de
        ret

; ---- the pace limiter (card patch.pace-limiter; target ORIGINAL). Every hook's added time goes to DEBT: its work at
; 28 MHz measured on the video line (dbg_open .. dbg_close; an ISR inside the window is left out: isr_in / isr_out),
; its entry and exit at the caller's clock as a constant per hook (C_*). The game's own delay at DD80 repays it (t_dly:
; the loop starts shorter). With 6 or more blocks the game has no delay: the debt waits for the next update's.

; qline: HL = the video line (0-311), the reads with interrupts held off (then put back as they were: inside the ISR
; they stay off); NR 7 is selected again after (HLIB_SPEED_IN reads it). AF, BC lost.
qline:  ld a,i
        di
        push af
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
        ld a,7
        out (c),a
        pop af
        ret po
        ei
        ret

; dbg_open: a debt window starts (at 28 MHz). AF, BC, HL lost.
dbg_open:
        call qline
        ld (DST),hl
        ret

; dbg_close: A = the hook's unmeasured part (1/16 lines). DEBT += 16 x lines since dbg_open + A. Inside a game routine's
; pace window (WOPEN 1: a nested hook, its entry and exit at 28 MHz: A / 8) or after it (WOPEN 2: the window hook's own
; work; A is its 3.5 MHz part, outside the window) the measured time also goes to WNEST. AF, BC, DE, HL lost.
dbg_close:
        push af
        call dlines
        ld a,(WOPEN)
        or a
        jr z,.plain
        dec a
        jr nz,.post
        pop af
        rrca
        rrca
        rrca
        and 0x1F
        ld e,a
        ld d,0
        add hl,de
        call .nest
        xor a
        call dadd.add
        jp mvtick               ; the window's count goes on here too: never a frame between two counts (an
                                ; interrupt in a ROM trampoline is not counted), so no wrap is lost
.post:  call .nest
.plain: pop af
        jr dadd.add
.nest:  push hl
        ld de,(WNEST)
        add hl,de
        ld (WNEST),hl
        pop hl
        ret

; dbg_close_r: as dbg_close, never WNEST (isr_step: the ISR is left out of a window by mvtick / wskipc).
dbg_close_r:
        push af
        call dlines
        pop af
        jr dadd.add

; dlines: HL = 16 x lines since dbg_open. AF, BC, DE lost.
dlines: call qline
        ld de,(DST)
        or a
        sbc hl,de
        jr nc,.p
        ld de,HLIB_PACE_NL
        add hl,de
.p:     add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ret

; dadd: DEBT += A (1/16 lines), capped at 0xBFFF (about 10 frames). AF, DE, HL lost.
dadd:   ld hl,0
.add:   ld e,a
        ld d,0
        add hl,de
        ld de,(DEBT)
        add hl,de
        jr c,.cap
        push hl
        ld de,DEBTCAP
        or a
        sbc hl,de
        pop hl
        jr c,.w
.cap:   ld hl,DEBTCAP
.w:     ld (DEBT),hl
        ret

; dconst: DEBT += A; keeps BC, DE, HL. AF lost.
dconst: push hl
        push de
        call dadd
        pop de
        pop hl
        ret

; isr_in / isr_out: t_isr in the hook page (interrupts off): the ISR body's time is left out of an open debt window
; (DST moves on by it). AF, BC, DE, HL lost.
isr_in: call qline
        ld (ISRL),hl
        ld a,(WOPEN)            ; a pace window: its time counted up to here
        or a
        ret z
        jp mvtick
isr_out:
        call qline
        ld a,(WOPEN)            ; a pace window: the ISR body left out (it goes on from here)
        or a
        jr z,.nw
        ld (MVL),hl
.nw:    ld de,(ISRL)
        or a
        sbc hl,de
        jr nc,.p
        ld de,HLIB_PACE_NL
        add hl,de
.p:     ld de,(DST)
        add hl,de
        ld de,HLIB_PACE_NL
        or a
        sbc hl,de
        jr nc,.w
        add hl,de
.w:     ld (DST),hl
        ret

; p_dly: from t_dly, at the game's clock. A = h0 = 8 (6 - AF09): the original's loop is N0 = 256 h0 steps of
; DEC L / JR NZ (16 T each) and h0 of DEC H / JR NZ. It now starts k = DEBT x 7/8 + KDLY steps short (KDLY: this
; hook's own time), at most N0 - 1; what is not repaid stays in DEBT. -> H, L the loop's start (N' = N0 - k steps:
; h' = ceil(N' / 256), l' = N' mod 256), A = t_dly's R delta: the original runs 2 + 2 N0 + 2 h0 M1s from DD8A to DD93,
; the hook E = 6 and N = 4, the loop 2 N' + 2 h': delta = 2 (h0 - h' - (l' & 63)) - 8 (mod 128; 2 N0 = 0).
; BC, DE lost.
p_dly:  ld (DH0),a
        ld hl,(DEBT)
        ld d,h
        ld e,l
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e
        or a
        sbc hl,de               ; debt - debt / 8 (14 T a unit, 16 T a step)
        ld de,KDLY
        add hl,de
        ex de,hl                ; DE = k
        ld a,(DH0)
        ld h,a
        ld l,0
        or a
        sbc hl,de               ; N' = N0 - k
        jr z,.cap
        jr c,.cap
        ld de,0
        ld (DEBT),de            ; all repaid
        jr .go
.cap:   ld a,(DH0)              ; k = N0 - 1: N0 - 1 - KDLY steps from the debt, x 8 / 7 in units
        ld h,a
        ld l,0
        ld de,-(KDLY + 1)
        add hl,de
        ld d,h
        ld e,l
        ld b,3
.s1:    srl d
        rr e
        djnz .s1
        add hl,de               ; + s / 8
        ld b,3
.s2:    srl d
        rr e
        djnz .s2
        add hl,de               ; + s / 64
        ld b,3
.s3:    srl d
        rr e
        djnz .s3
        add hl,de               ; + s / 512 (x 1.1426, under 8 / 7: the rest is never under-counted)
        ex de,hl
        ld hl,(DEBT)
        or a
        sbc hl,de
        jr nc,.d
        ld hl,0
.d:     ld (DEBT),hl
        ld hl,1                 ; N' = 1
.go:    ld a,l
        or a
        jr z,.h
        inc h                   ; h' = ceil(N' / 256)
.h:     and 63
        ld b,a
        ld a,(DH0)
        sub h
        sub b
        add a,a
        sub 8
        and 0x7F
        ret

; mv_in: a scroll move starts: the caller's speed latched (VSPD2, GSPD), then 28 MHz in both modes; with fast scroll
; off, its pace window opens. AF, BC lost.
mv_in:  call spd_fast
        nextreg 0x07,3
        ld a,(VFAST)
        or a
        jr z,.win
        ld a,(VCENTRE)          ; session 4: Centred view (fast): the step's window opens here and closes after its
        or a                    ; copy (cw_close): the step costs no game time, its time goes to the debt
        ret z
        push hl
        ld hl,(DEBT)
        ld (CWD),hl
        pop hl
.win:   push hl
        call qline
        ld (MVL),hl
        ld hl,0
        ld (MVE),hl
        ld a,3                  ; session 3: an ISR inside the move (now run here, in the page) is left out of the
        ld (WOPEN),a            ; window (isr_in / isr_out), and its body runs at the game's speed, as in the original
        pop hl
        ret

; mv_lddr / mv_ldir: the game's own block move, run in the page (an interrupt in it takes t_isr's hook-page path).
mv_lddr:
        lddr
        ret
mv_ldir:
        ldir
        ret

; mv_out: HL = the move's original time (1/16 lines). Fast scroll off: wait until the window has lasted that, less
; the debt (an ISR body inside it is left out, as it lengthened the original's move too); a debt over it is cut by
; what the move saved. Then the caller's speed. Keeps BC, DE; AF, HL lost.
mv_out: ld a,(VFAST)
        or a
        jr nz,.back             ; fast scroll: the burst's saving is its own (never in the debt)
        push bc
        push de
        ld (MVT),hl             ; O
        ex de,hl
        ld hl,(DEBT)
        ex de,hl                ; HL = O, DE = debt
        or a
        sbc hl,de
        jr c,.paid
        ld (MVT),hl             ; wait until the window has lasted O - debt
        ld hl,0
        ld (DEBT),hl
        ld a,0
        ld (MVP),a
.w:     call mvtick
        ld hl,(MVE)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(MVT)
        or a
        sbc hl,de
        jr c,.w
        jr .done
.paid:  call mvtick             ; the debt is more than the move: no wait; debt -= O - W
        ld hl,(MVE)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(DEBT)
        add hl,de               ; W + debt
        ld de,(MVT)
        or a
        sbc hl,de               ; - O
        jr nc,.st
        ld hl,0
.st:    ld (DEBT),hl
.done:  xor a
        ld (WOPEN),a
        pop de
        pop bc
.back:  ld a,(VSPD2)
        nextreg 0x07,a
        ret

; mvtick: MVE += lines since MVL (one wrap allowed), MVL = now; interrupts held off throughout, so an ISR's isr_out
; (which moves DST) cannot fall between. The line counter still for 256 polls: MVE is forced past any target (an
; emulator without one). AF, DE, HL lost.
mvtick: ld a,i
        di
        push af
        push bc
        call qline
        ld de,(MVL)
        ld (MVL),hl
        or a
        sbc hl,de
        jr nz,.m
        ld a,(MVP)
        dec a
        ld (MVP),a
        jr nz,.z
        ld hl,0x0FFF            ; no line counter: give up (x 16 is past any target)
        ld (MVE),hl
        jr .z
.m:     push af
        xor a
        ld (MVP),a
        pop af
        jr nc,.m2
        ld de,HLIB_PACE_NL
        add hl,de
.m2:    ld de,(MVE)
        add hl,de
        ld (MVE),hl
.z:     pop bc
        pop af
        ret po
        ei
        ret

; slot_of: the pattern slot for image GIMG: -> A = its first pattern (3 x slot), Z when the slot holds it already
; (no upload), NZ for a slot given to it now (the caller uploads), never one used earlier in this update (at most
; MAXG = 21 groups an update: one is always free). BC, DE, HL lost.
slot_of:
        ld a,(GIMG)
        inc a
        ld hl,SKEY
        ld bc,21
        cpir
        jr nz,.miss
        ld a,20
        sub c                   ; the slot
        call .use
        cp a                    ; Z
        ret
.miss:  ld a,(SCLK)
        ld b,21
.f:     cp 21
        jr c,.f1
        xor a
.f1:    ld e,a
        ld d,high SUSE
        add a,low SUSE
        ld l,a
        ld h,d
        ld a,(STAMP)
        cp (hl)
        ld a,e
        jr nz,.got
        inc a
        djnz .f
.got:   ld e,a                  ; E = the slot
        inc a
        ld (SCLK),a
        ld a,e
        add a,low SKEY
        ld l,a
        ld h,high SKEY
        ld a,(GIMG)
        inc a
        ld (hl),a
        ld a,e
        call .use
        or 1                    ; NZ
        ld a,c
        ret
.use:   ld e,a                  ; SUSE[slot] = STAMP; A = C = 3 x slot
        add a,low SUSE
        ld l,a
        ld h,high SUSE
        ld a,(STAMP)
        ld (hl),a
        ld a,e
        add a,a
        add a,e
        ld c,a
        ret

; ---- session 3: game-routine pace windows (see WOPEN). With 6 or more blocks the game has no delay, so the hooks'
; time is repaid inside the update: the game's own routine runs at 28 MHz and the window lasts the original's time
; less the debt.

; The window's time: MVE (lines) and MVL as the scroll moves' windows (never at the same time), counted by mvtick; an
; ISR body is left out (isr_in / isr_step: mvtick, isr_out / wskipc: MVL = now).

; wskipc: from t_isr (game code) after the ISR body: a window goes on from now. Keeps BC, DE, HL; AF lost.
wskipc: ld a,(WOPEN)
        or a
        ret z
        push bc
        push hl
        call qline
        ld (MVL),hl
        pop hl
        pop bc
        ret

; fw_open: A = K: the window opens, at 28 MHz. AF, BC, DE, HL lost.
fw_open:
        ld (WK),a
        nextreg 0x07,3
        ld hl,0
        ld (MVE),hl
        ld (WNEST),hl
        xor a
        ld (MVP),a
        call qline
        ld (MVL),hl
        ld a,1
        ld (WOPEN),a
        ret

; wown: HL = 16 MVE - WNEST (the routine and the wait so far), C when negative. AF, DE lost.
wown:   call mvtick
        ld hl,(MVE)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(WNEST)
        or a
        sbc hl,de
        ret

; fw_mark: the game routine has returned: WP = its time, WO = WP x K / 16, WOPEN = 2. AF, BC, DE, HL lost.
fw_mark:
        call wown
        jr nc,.p
        ld hl,0
.p:     ld (WP),hl
        ex de,hl                ; C:HL = DE x K
        ld hl,0
        ld c,0
        ld a,(WK)
        ld b,8
.m:     add hl,hl
        rl c
        rla
        jr nc,.n
        add hl,de
        jr nc,.n
        inc c
.n:     djnz .m
        ld a,c
        ld b,4
.s:     srl a
        rr h
        rr l
        djnz .s
        or a
        jr z,.o
        ld hl,0xFFFF
.o:     ld (WO),hl
        ld a,2
        ld (WOPEN),a
        ret

; fw_wait: the routine's saving (WO - WP) repays DEBT; what DEBT does not take is waited out: until 16 MVE - WNEST (the
; routine and the wait) reaches WO - DEBT (no line counter: mvtick gives up). WOPEN = 0. AF, BC, DE, HL lost.
fw_wait:
        ld hl,(WO)
        ld de,(WP)
        or a
        sbc hl,de
        jr c,.done
        ex de,hl                ; DE = the saving
        ld hl,(DEBT)
        or a
        sbc hl,de
        jr c,.wait
        ld (DEBT),hl            ; the saving all taken by the debt
        jr .done
.wait:  ld hl,(WO)
        ld de,(DEBT)
        or a
        sbc hl,de
        ld (WT),hl
        ld hl,0
        ld (DEBT),hl
.w:     call wown
        jr c,.w
        ld de,(WT)
        or a
        sbc hl,de
        jr c,.w
.done:  xor a
        ld (WOPEN),a
        ret

; fw_step: E = K. Fast scroll: 28 MHz (spd_fast), the saving its own; off: a window. AF, BC lost.
fw_step:
        ld a,(VFAST)
        or a
        jp nz,spd_fast
        call spd_latch
        ld a,e
        jp fw_open

; the window hooks' page parts (called from their ROM trampolines inside an R bracket; every register kept).
; fw_spr_in: before E656: always a window.
fw_spr_in:
        push af
        push bc
        push de
        push hl
        call spd_latch
        ld a,KSPR
        call fw_open
        ld a,-9 & 0x7F
fw_in_x:
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ret
; fw_spr_out: after E656: the sprites (p_spr), then the wait.
fw_spr_out:
        push af
        push bc
        push de
        push hl
        call fw_mark
fw_spr_m:
        call dbg_open
        call p_spr
        ld a,C_FW
        call dbg_close
        call fw_wait
        ld a,-9 & 0x7F
fw_out_x:
        call hlib_r_set
        call spd_back
        pop hl
        pop de
        pop bc
        pop af
        ret

; fw_bs_in: before BE38 (a scroll step's strip): fast scroll: 28 MHz, its saving its own; off: the caller's speed.
fw_bs_in:
        push af
        push bc
        push de
        push hl
        ld a,(VFAST)            ; off: the caller's speed (the original's time exactly; its nested hooks' time goes to
        or a                    ; the debt, repaid by the copy's window, the move's and the delay)
        call nz,spd_fast
        call z,spd_latch
        ld a,-9 & 0x7F
        jp fw_in_x
fw_bs_out:
        push af
        push bc
        push de
        push hl
        ld a,(WOPEN)
        cp 1                    ; (session 4: not a Centred step's window, 3)
        jr nz,fw_bs_x
        call fw_mark
fw_bs_m:
        ld a,C_FW
        call dconst
        call fw_wait
fw_bs_x:
        ld a,-9 & 0x7F
        jp fw_out_x

; fw_cpy_in: before C05A's copy (C05D). From DD9A (a scroll step's copy): fast scroll: 28 MHz, its saving its own;
; off: a window. Otherwise (E0CE: a view's first copy) the caller's speed, and earlier debt (the menu's) dropped.
fw_cpy_in:
        push af
        push bc
        push de
        push hl
        ld hl,10
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = the copy's return address
        ld de,0xDD9D
        or a
        sbc hl,de
        jr z,.step
        ld de,c_ret - 0xDD9D    ; session 4: from c_pre (Centred view: the step's copy before the update)
        or a
        sbc hl,de
        jr nz,.first
.step:  ld e,KCPY
        call fw_step
        jr .x
.first: ld hl,0
        ld (DEBT),hl
        xor a
        ld (WOPEN),a
        call spd_latch
.x:     ld a,-10 & 0x7F
        jp fw_in_x
; fw_cpy_out: after the copy: the inks and the origin (p_inks, p_pre: the picture changes once, complete), then the
; wait.
fw_cpy_out:
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld a,(WOPEN)
        cp 1
        call z,fw_mark
fw_cpy_m:
        call dbg_open
        call p_inks
        call p_pre
        ld a,C_C05A
        call dbg_close
        ld a,(WOPEN)
        cp 2
        call z,fw_wait
        cp 3
        call z,cw_close
        ld a,-9 & 0x7F
        jp fw_out_x

; cw_close: a Centred step's window ends (after its copy, inks and origin): DEBT = the debt at its start + the window's
; time (ISR bodies left out); what nested hooks added inside it is replaced. WOPEN = 0. AF, DE, HL lost.
cw_close:
        call mvtick
        ld hl,(CWD)
        ld (DEBT),hl
        ld hl,(MVE)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        xor a
        ld (WOPEN),a
        jp dadd.add

TCODE_END:
        DISPLAY "TCODE_END ",/H,TCODE_END
        ASSERT TCODE_END <= VSPD
        ORG TCOL
        DUP 32, n
        DW TAGS + n * TS
        EDUP
PAGE_END:
        SAVEBIN "quazatron_page.bin",0x4000,PAGE_END-0x4000

; ============================================================================================================
        ORG 0x386E

; CALL B07D at BE2E (a scenery list into the strip)
t_list: push hl
        call 0xB07D
        nextreg 0x52,HPAGE
        HLIB_R_IN
        ex (sp),hl
        push af
        push bc
        push de
        HLIB_SPEED_IN VSPD
        push hl
        call dbg_open
        pop hl
        call p_tags
        ld a,C_LIST
        call dbg_close
        ld a,-11 & 0x7F
        call hlib_r_set
        HLIB_SPEED_OUT VSPD
        pop de
        pop bc
        pop af
        pop hl
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; CALL C044 at BE82 (the strip cleared to ink)
t_clr:  call 0xC044
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call dbg_open
        call p_clr
        jr tw_exit

; CALL C1A5 at BFEC, BFFB (the strip pasted into the background)
t_paste:
        call 0xC1A5
        nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN VSPD
        call dbg_open
        call p_paste
tw_exit:
        ld a,C_TW
        call dbg_close
        ld a,-10 & 0x7F
        call hlib_r_set
        HLIB_SPEED_OUT VSPD
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; CALL E656 at E0DF (the blocks blitted to the screen): E656 itself in a pace window (fw_spr_in / fw_spr_out: 28 MHz,
; the original's time less the debt), then the sprites follow. Bracket 1 makes R exact at E656's entry (O = 1 (CALL),
; E = 1 + 2 + 3, N = 1 + 2 + 1: -9); bracket 2 from its RET (O = 0, E = 2 + 3, N = 1 + 2 + 1 (RET): -9).
t_spr:  nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_spr_in
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        call 0xE656
        nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_spr_out
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; JP at C05A (background to screen, then the attributes). The commit runs after the game's copy, so the shown canvas
; changes once, complete (during the copy the original shows its new bitmap under the old attributes; we keep showing
; the last complete picture; at the first view Layer 2 is still off and the ULA shows exactly the original). Two
; brackets, so that R is the original's exactly while the game's own copy runs (the ISR reads R); the first does no
; work but the speed and the window (fw_cpy_in): (1) O = 1 (LD DE) to the copy's entry, E = 1 + 2 + 3, N = 1 + 2 + 1
; (LD DE) + 1 (CALL): delta 1 - 6 - 5 = -10; (2) from the copy's RET: E = 2 + 3, N = 1 + 2 + 1 (RET): delta -9.
t_c05a: nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_cpy_in
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld de,0x8300
        call 0xC05D
        nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_cpy_out
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; the scroll moves, run here (both options): the origin follows (content down 8 = view up: OY - 8, ...), then the
; game's own LD HL / LD DE / LD BC / LDDR or LDIR at the caller's speed, or at 28 MHz with the fast-scroll option.
; R: O = 3 + 2 n (the block move refetches ED B0 / B8 per byte) to the instruction after it; E = 1 (JP) + 2 + 3;
; N = 1 + 2 + 1 (JP). n = 4608 (vertical): O = 3 (mod 128), delta -7; n = 4862: O = 127, delta 117.
t_sd:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld a,(OY)
        sub 8
        ld (OY),a
        ld a,C_MOVE
        call dadd
        ld a,-7 & 0x7F
        call hlib_r_set
        call mv_in
        pop af
        ld hl,0x94FF
        ld de,0x95FF
        ld bc,0x1200
        call mv_lddr
        push af
        push hl
        ld hl,O_MOVEV
        call mv_out
        pop hl
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xE119
t_su:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld a,(OY)
        add a,8
        ld (OY),a
        ld a,C_MOVE
        call dadd
        ld a,-7 & 0x7F
        call hlib_r_set
        call mv_in
        pop af
        ld hl,0x8400
        ld de,0x8300
        ld bc,0x1200
        call mv_ldir
        push af
        push hl
        ld hl,O_MOVEV
        call mv_out
        pop hl
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xE128
t_sl:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld de,16
        call s_x
        call mv_in
        pop af
        ld hl,0x8302
        ld de,0x8300
        ld bc,0x12FE
        call mv_ldir
        push af
        push hl
        ld hl,O_MOVEH
        call mv_out
        pop hl
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xE137
t_sr:   nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        ld de,320-16
        call s_x
        call mv_in
        pop af
        ld hl,0x95FD
        ld de,0x95FF
        ld bc,0x12FE
        call mv_lddr
        push af
        push hl
        ld hl,O_MOVEH
        call mv_out
        pop hl
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xE151
s_x:    ld hl,(OX)
        add hl,de
        call mod320
        ld (OX),hl
        ld a,C_MOVE
        call dadd
        ld a,117
        jp hlib_r_set

; CALL BE38 at E1A9 (a scroll step's new strip): at 28 MHz; with fast scroll off in a pace window (fw_bs_in / out).
; Bracket 1 makes R exact at BE38's entry (O = 1, E = 6, N = 1 + 2 + 1: -9); bracket 2 from its RET (E = 2 + 3, N = 4: -9).
t_bs:   nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_bs_in
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        call 0xBE38
        nextreg 0x52,HPAGE
        HLIB_R_IN
        call fw_bs_out
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ret

; JP at E6E6 (the ISR's JP BD2D). The interrupted PC decides: in the ROM trampolines, nothing; in the hook page, only
; NR 7 = the game's speed for the ISR body; in game code, the smooth display's frame step (isr_step). No port is
; read or selected here. R exact at BD2D: E = 1 (JP) + 1 + 2, N = 2 (POP AF, JP): R = R read - 5, bit 7 kept.
t_isr:  push af
        ld a,r
        push hl
        ld l,a
        and 0x80
        ld h,a
        ld a,l
        sub 5
        and 0x7F
        or h
        ld l,a
        push hl
        push bc
        push de
        call rd7                ; A = the interrupted speed, then the hook's own parts at 28 MHz
        nextreg 0x07,3
        ld c,a
        ld hl,10
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        cp 0x40
        jr c,.rom
        cp 0x60
        jr nc,.game
        ; in the hook page (inside a hook's R bracket, the page mapped): the ISR body at the game's speed, then the
        ; hook's own speed back (the port is safe: the page's own reads are DI-protected)
        ld a,c
        ld (ISRSPD),a
        call isr_in             ; the ISR body's time is left out of an open debt window
        ld a,(GSPD)
        nextreg 0x07,a
        pop de
        pop bc
        pop hl
        pop hl
        pop af
        call 0xBD2D
        push af
        ld a,(ISRSPD)
        nextreg 0x07,a
        push bc
        push de
        push hl
        call isr_out
        pop hl
        pop de
        pop bc
        pop af
        ret
.rom:   ld a,c                  ; a ROM trampoline: nothing (the interrupted speed back)
        nextreg 0x07,a
        pop de
        pop bc
        pop hl
        ld a,l
        pop hl
        ld r,a
        pop af
        jp 0xBD2D
.game:  nextreg 0x52,HPAGE      ; game code: the frame step, the ISR body, then the interrupted speed and R
        ld a,c
        ld (ISRSPD),a
        call isr_step           ; NR 7 = the game's speed at its end
        nextreg 0x52,ULAPAGE
        pop de
        pop bc
        pop hl
        ld a,l
        pop hl
        ld r,a
        pop af
        call 0xBD2D             ; (CALL, 1 M1, as the JP: R exact at BD2D)
        nextreg 0x07,3
        push af
        ld a,r                  ; R read = R at the ISR's return + 2 + 3; set = that - 2 (POP AF, RET follow)
        push hl
        ld l,a
        and 0x80
        ld h,a
        ld a,l
        sub 7
        and 0x7F
        or h
        ld l,a
        nextreg 0x52,HPAGE
        call wskipc             ; a game routine's pace window goes on from here (the ISR left out)
        ld a,(ISRSPD)
        nextreg 0x07,a
        nextreg 0x52,ULAPAGE
        ld a,l
        pop hl
        ld r,a
        pop af
        ret

; rd7: A = NR 7 bits 1:0 (the programmed speed). BC lost. Only from t_isr (interrupts off).
rd7:    ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ret

; JP at B2C9 (screen clear): Layer 2 off. O = 1, E = 6, N = 5: delta -10.
t_cls:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        call p_off
        push hl
        ld hl,0
        ld (DEBT),hl            ; the screen clear (a new deck, the menu): the debt so far is never repaid
        pop hl
        ld a,-10 & 0x7F
        call hlib_r_set
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0x4000
        jp 0xB2CC

; JP at B1FB (the printer, LD (B263),DE): Layer 2 off when DE is in the play area (rows 0-151).
; O = 2 (ED 53), E = 6, N = 1 + 2 + 2 + 1: delta -10.
t_prn:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        ld a,d
        cp 0x50
        jr c,.off
        cp 0x58
        jr nc,.no
        ld a,e
        cp 0x60
        jr nc,.no
.off:   call p_off
.no:    ld a,C_CLS
        call dconst
        ld a,-10 & 0x7F
        call hlib_r_set
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld (0xB263),de
        jp 0xB1FF
; JP at DD8A (LD H,A / LD L,0: the game's delay, H x 256 steps of DEC L / JR NZ at DD8D). The pace limiter: the
; loop starts shorter by the debt (p_dly), at the game's clock; R is the original's again at DD93 (delta from p_dly).
t_dly:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        call p_dly
        call hlib_r_set
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xDD8D
ROM_END:
        ASSERT ROM_END + 20 <= 0x3CAC  ; session 4: c_pre at 0x3CAC
        SAVEBIN "quazatron_rom.bin",0x386E,ROM_END-0x386E

; ============================================================================================================
; Page 27 (GPAGE, bank 13 upper half), mapped at slot 6 only inside isr_step (interrupts off; the hook page at slot 2).
        ORG 0xC000
; glide: the shown origin (DX, DY) one frame toward the committed one (TX, TY); SDX / SDY current (offs). Smooth
; scrolling alone: v1.0's rule, moved here unchanged (2 px a frame, 4 when more than 16 behind; 1 line, 2 when more
; than 8). Centred view: glide_c. AF, BC, DE, HL lost.
glide:  ld a,(VCENTRE)
        or a
        jp nz,glide_c
        ld hl,(SDX)             ; x: 2 px a frame, 4 when more than 16 behind
        ld a,h
        or l
        jr z,.y
        bit 7,h
        push af
        jr z,.xp
        call neghl
.xp:    ld de,17
        or a
        sbc hl,de
        add hl,de
        ld de,2
        jr c,.xs
        ld de,4
.xs:    or a
        sbc hl,de               ; |d| - step
        jr nc,.xf
        add hl,de
        ex de,hl                ; step = |d|
.xf:    pop af
        ld hl,(DX)
        jr nz,.xm
        add hl,de
        call mod320
        jr .xw
.xm:    or a
        sbc hl,de
        jr nc,.xw
        ld de,320
        add hl,de
.xw:    ld (DX),hl
.y:     ld a,(SDY)              ; y: 1 line a frame, 2 when more than 8 behind
        or a
        ret z
        ld b,1
        bit 7,a
        jr z,.yp
        neg
        ld b,-1
.yp:    cp 9
        jr c,.ys
        sla b
.ys:    ld a,(DY)
        add a,b
        ld (DY),a
        ret

; glide_c (session 4, Centred view): per axis the shown origin moves at the speed that reaches the committed one just as
; the next step is due: |d| / max(4, I + 3 - A) a frame (8.8 fixed point, the fraction kept), I = the frames between the
; last two commits on that axis (6-32), A = the frames since the last one. A steady walk gives a steady camera; when the
; player stops, it eases out over at least 4 frames; never past the target.
glide_c:
        ld hl,(TX)
        ld de,(LTX)
        or a
        sbc hl,de
        jr z,.x1
        add hl,de
        ld (LTX),hl
        ld hl,GXA
        call g_new
.x1:    ld hl,GXA
        call g_inc
        ld hl,(SDX)
        ld a,h
        or l
        jr z,.x0
        bit 7,h
        push af
        jr z,.xp
        call neghl
.xp:    ld a,(GXI)
        ld b,a
        ld a,(GXA)
        ld c,a
        ld a,(GXF)
        ld d,a
        call g_step
        ld (GXF),a
        pop af
        ld hl,(DX)
        jr nz,.xm
        add hl,de
        call mod320
        jr .xw
.xm:    or a
        sbc hl,de
        jr nc,.xw
        ld de,320
        add hl,de
.xw:    ld (DX),hl
        jr .y
.x0:    ld (GXF),a
.y:     ld a,(TY)
        ld hl,LTY
        cp (hl)
        jr z,.y1
        ld (hl),a
        ld hl,GYA
        call g_new
.y1:    ld hl,GYA
        call g_inc
        ld hl,(SDY)
        ld a,h
        or l
        jr z,.y0
        bit 7,h
        push af
        jr z,.yp
        call neghl
.yp:    ld a,(GYI)
        ld b,a
        ld a,(GYA)
        ld c,a
        ld a,(GYF)
        ld d,a
        call g_step
        ld (GYF),a
        pop af
        ld a,(DY)
        jr nz,.ym
        add a,e
        jr .yw
.ym:    sub e
.yw:    ld (DY),a
        ret
.y0:    ld (GYF),a
        ret

; g_step: HL = |d| (1-319), B = I, C = A, D = the fraction -> DE = the pixels to move now (never over |d|), A = the
; new fraction. v = min(|d|, 255) x 256 / max(4, I + 3 - A); acc = v + fraction. BC lost.
g_step: ld a,b
        add a,3                 ; aim 3 frames past the predicted step: the camera keeps moving (no stop before a step
        sub c                   ; that comes a little late); the leftover is taken up in the next interval
        jr c,.r4
        cp 4
        jr nc,.r
.r4:    ld a,4
.r:     ld c,a
        push hl
        ld a,h
        or a
        jr z,.lo
        ld l,255
.lo:    ld h,l
        ld l,0
        xor a
        ld b,16
.dv:    add hl,hl
        rla
        jr c,.sb
        cp c
        jr c,.nx
.sb:    sub c
        inc l
.nx:    djnz .dv
        ld e,d
        ld d,0
        add hl,de
        ld a,l
        ld e,h
        ld d,0
        pop hl
        push hl
        or a                    ; (A kept: OR A only clears the carry)
        sbc hl,de
        pop hl
        ret nc
        ex de,hl
        xor a
        ret

; g_new: HL = an axis's age (its I the byte below): I = the age held to 6-32, the age = 0. AF lost.
g_new:  ld a,(hl)
        cp 6
        jr nc,.a
        ld a,6
.a:     cp 33
        jr c,.b
        ld a,32
.b:     ld (hl),0
        dec hl
        ld (hl),a
        ret

; g_inc: (HL) + 1, held at 255.
g_inc:  inc (hl)
        ret nz
        dec (hl)
        ret
GPAGE_END:
        ASSERT GPAGE_END <= 0xE000
        SAVEBIN "quazatron_page2.bin",0xC000,GPAGE_END-0xC000

; ============================================================================================================
; c_pre (session 4, Centred view): CALL at E0DC (was CALL D5BB) and JP E1EC at E1B3 (the edge bursts never start), in the
; Centred builds only. Pure Z80 at the game's speed, the same bytes in the reference game the proofs replay: before
; each update, when the player is more than one step off the play area's centre (128, 88), ONE scroll step that way
; (the game's own step: E0FB .. E1AC, which returns here); after it, the game's copy to the screen and AF2B = 0, so the
; update that follows is a normal one (droids move). AF2B 1-6 (the transfer and lift modes): no step.
        ORG 0x3CAC
c_pre:  ld a,(0xAF2C)
        and a
        jr nz,c_step
        ld a,(0xAF2B)
        and a
        jr z,c_chk
        cp 7
        jp c,0xD5BB
        call 0xC05A
c_ret:  xor a
        ld (0xAF2B),a
        jp 0xD5BB
c_chk:  ld a,(0xAF94)
        ld e,0x14
        cp 112
        jr c,c_go
        ld e,0x0A
        cp 145
        jr nc,c_go
        ld a,(0xAF95)
        ld e,0x28
        cp 80
        jr c,c_go
        ld e,0x1E
        cp 97
        jp c,0xD5BB
c_go:   ld a,e
        ld (0xAF2B),a
        ld d,0
        ld hl,0xAF36
        add hl,de
        ld de,0xAF2C
        ld bc,10
        ldir
        ld a,1
c_step: pop hl
        jp 0xE0FB
C_END:
        ASSERT C_END <= 0x3D00
        SAVEBIN "quazatron_centre.bin",0x3CAC,C_END-0x3CAC

; ============================================================================================================
; setup: called by the stub (DI, 3.5 MHz, slot 2 = the screen page) before the tail. Layer 2 320 x 256 on banks
; L2BANK.., its palette (PALINIT in the hook page), the canvas cleared, the clip = the 256 x 152 play area,
; layers S L U, sprites off for now, Layer 2 off until the first commit.
        ORG 0xD000
setup:  nextreg 0x07,3
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,PALINIT
        ld b,64
.p:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .p
        ld a,L2PAGE
.cl:    nextreg 0x52,a
        ld hl,0x4000
        ld de,0x4001
        ld bc,0x1FFF
        ld (hl),0
        ldir
        inc a
        cp L2PAGE + 10
        jr c,.cl
        nextreg 0x52,ULAPAGE
        nextreg 0x70,0x10
        nextreg 0x12,L2BANK
        nextreg 0x1C,1
        nextreg 0x18,16
        nextreg 0x18,143
        nextreg 0x18,32
        nextreg 0x18,183
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x15,0
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,151
        nextreg 0x07,0
        ret
SETUP_END:
        ASSERT SETUP_END <= PALINIT
        SAVEBIN "quazatron_setup.bin",0xD000,SETUP_END-0xD000
