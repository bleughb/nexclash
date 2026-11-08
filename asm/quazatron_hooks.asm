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
XPAGE   EQU 25                  ; session 9: bank 12 upper half, code at slot 1 inside hook work (see x_tags)
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
STX     EQU 0x4CE5              ; session 5 (Centred view): 2: TX when the last update's sprites were placed (p_spr)
STY     EQU 0x4CE7              ;   TY then
PSX     EQU 0x4CE8              ;   the player's AF94 then
PSY     EQU 0x4CE9              ;   AF95 (PSX, PSY adjacent)
PKX     EQU 0x4CEA              ; 2: a player group's offset: base + PKX = its screen X (PKX, PKY adjacent)
PKY     EQU 0x4CEC              ; 2
PSCX    EQU 0x4CEE              ; 2: the shown player's screen x (Pd - DX), from the last frame step
PSCY    EQU 0x4CF0              ; 2: its screen y
PG0     EQU 0x4CF2              ; the player's first sprite group this update (PG0, PG1 adjacent)
PG1     EQU 0x4CF3              ;   the group after its last
PLR     EQU 0x4CF4              ; p_spr: 1 while the player's groups are placed (Centred view)
FRESH   EQU 0x4CF5              ; 1: a view's first copy since the last frame step (the camera starts again)
SSX     EQU 0x4CF6              ; 2: the frame step's sprite offset (droids, shots): STX - DX (SSX, SSY adjacent)
SSY     EQU 0x4CF8              ; 2: STY - DY
CFX0    EQU 0x4C78              ; session 10: x_cfr's rectangle: 2: canvas x (0-319), the first column
CFY0    EQU 0x4C7A              ;   canvas line of its top (cell-aligned)
CFW     EQU 0x4C7B              ;   width in cells (32 = 256 px)
CFH     EQU 0x4C7C              ;   height in cells (32 = 256 lines)
CFV     EQU 0x4C7D              ;   the value: the deck's void ink (0-15)
CFS6    EQU 0x4C7E              ;   NR 0x56 on entry
FRSH2   EQU 0x4CFB              ; session 10: 1 = a view's first copy (fw_cpy_in): p_pre snaps the shown origin
SBUSY   EQU 0x4CFA              ; 1 while p_spr writes the sprite ports: an ISR in the hook page skips the frame step
GPAGE   EQU 27                  ; page 27 (bank 13 upper half): the frame step, mapped at slot 7 only inside isr_step
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
HLIB_V_PACE EQU 0x4B40          ; 26: the shared pace library's state (lib/hlib_pace.asm), zero at start (session 11)
DEBT    EQU HLIB_V_PACE + 4     ; 2: the pace limiter's debt, 1/16 video lines (14 T at 3.5 MHz) of hook time not yet repaid
DH0     EQU 0x4BFC              ; t_dly: the delay's outer count
GIMG    EQU 0x4BFD              ; group: the image number
        DEFINE HLIB_PACE_CAP 0x9C00     ; session 8: eight frames, 312 x 16 x 8 (was four): a Centred step pair (H + V) leaves more
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
; a scroll step's BE38 (strip render) and its C05A copy (from DD9A), run at 28 MHz; their time there (ISR bodies and
; nested hook work left out) x K/16 is the original's time (hlib_pace_waitk); the saving repays DEBT, and what DEBT does not take is
; waited out on the video line. K per routine: JNext's ratio of the original's time at 3.5 MHz (48K contention) to the
; routine's at 28 MHz, measured in session 3 (work/s3/kcal.py), rounded down (never faster than the original).
WOPEN   EQU 0x4CD0              ; 0: no window, 1: the game routine runs (nested hooks: hlib_nest_*), 2: the hook's own work,
                                ; 3: a scroll move's window (fast scroll off) or a Centred step's (cw_close)
WK      EQU 0x4CD1              ; K (x 16)
WNS     EQU 0x4CD6              ; 2: the nested hooks' entries and exits inside the routine (1/16 lines, at 28 MHz):
                                ; v1.2's WNEST left them out of the routine's time; the library's window keeps them
NESTF   EQU 0x4CD8              ; 1: inside dbg_open .. dbg_close with a nest open (an ISR there leaves the window alone)
        IFNDEF KSPR
KCMP    EQU 96                  ; session 9: 6.0 (session 8: 6.31). Calibrated in lockstep against the Centred reference game (work/s9/anal9c.py: the original with Centred view's logic only, its step time left out): 101 ran +1.8% slow, 96 -0.4% quiet, +1.3% scroll (JNext measured 6.10 time-weighted in session 8)
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
C_LIBP  EQU 1                   ; refactor (v1.3): a nested hook's library work outside its two readings, counted
C_LIB   EQU 8                   ; at 28 MHz T / 8 (1/16 lines, rounded down): before nest_open's reading about 160 T
                                ; (C_LIBP; inside an open window, so WNS too), after nest_close's about 1,100 T (C_LIB:
                                ; the debt sums, the window's re-read). v1.2's qline / dlines / dadd left about 600 T
                                ; so; without these, JNext: a scroll step's strip (BE38, 3.5 MHz, many nested hooks)
                                ; ran 2% longer than v1.2's and its time never reached the debt
C_CLS   EQU 44                  ; t_prn 630-711 T (t_cls clears the debt)
KDLY    EQU 40                  ; t_dly 652 T, in delay steps (16 T)
        ENDIF
S0      EQU 46                  ; sprite store: page 46 = (list - 0x9C00) >> 1 -> 0-3 enemy frame / image / 255,
                                ; pages 47.. = images (16 x 48 x 8 bits, 10 a page), from quazatron.py sprite_store
MAXG    EQU 21
FLAGS   EQU 0xD200              ; in page S0 at slot 6: 40 x 32 canvas cells, the ink their ink bytes hold (0xFF: unknown)
TAGS    EQU 0x4D00              ; 32 columns x 152 rows
TINK8   EQU 8                   ; session 9: a tag's ink value (was 0): the deck's bright black, so a fully pasted cell
                                ; on the deck needs no recell (x_paste flags it 8)
XW      EQU 0x4C76              ; session 9: x_tags: the strip's pasted width (16 or 32)
IPV     EQU 0x4B00              ; session 9: droid and shot interpolation (Centred view), page 26 state:
IOX     EQU IPV                 ;   1: ipol's offset x (px, signed)
IOY     EQU IPV + 1             ;   1: its offset y
IKY     EQU IPV + 2             ;   the group's key
ICXV    EQU IPV + 3             ;   2: its canvas x
ICYV    EQU IPV + 5             ;   its canvas y
IBST    EQU IPV + 6             ;   the best match's distance (0xFF: none)
IBQ     EQU IPV + 7             ;   its QKEY index (low byte)
IT      EQU IPV + 8             ;   frames over which the offsets are drawn in (the last update's interval, 2-8)
IR      EQU IPV + 9             ;   frames left of that (the frame step counts it down)
FRMC    EQU IPV + 10            ;   frame steps counted (cam)
FRML    EQU IPV + 11            ;   FRMC at the last update's sprites
IRAD    EQU 24                  ; the farthest a droid or a shot is matched to its last place (|dx| + |dy| each <= it)
IKEYA   EQU 0xDA00              ; in S0 (slot 6): + g this update's keys (0xFF: none), + 0x20 / 0x40 canvas x low /
                                ; high, + 0x60 canvas y; + 0x80 .. the last update's (0xFE: taken)
DXA     EQU 0xDB00              ; in S0: per group (+ g) its offset from its last place, x (px, signed; 0: none) and
DYA     EQU 0xDC00              ; y: written by ipol (slot 6), read by the frame step (slot 0: never written there)
FCT     EQU IPV + 12            ; the frame step's share of the offset still shown: IR x 256 / IT (0-255)
XFL     EQU 0x4C77              ; session 9: x_paste: the flag of the cells it touched

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

; session 9: p_tags, rowloop and p_clr run from page 25 (XPAGE, slot 1): x_tags, x_clr
p_tags: nextreg 0x51,XPAGE
        call x_tags
        nextreg 0x51,0xFF
        ret
p_clr:  nextreg 0x51,XPAGE
        call x_clr
        nextreg 0x51,0xFF
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

; session 9: p_paste runs from page 25 (x_paste)
p_paste:
        nextreg 0x51,XPAGE
        call x_paste
        nextreg 0x51,0xFF
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
        ld a,(FRSH2)            ; session 10: a view's first copy (a new deck, a restart): the canvas holds nothing of
        or a                    ; the last view, so the shown origin snaps (it glided over stale canvas cells), and in
        jr z,.nf                ; Centred view every canvas cell outside the view takes the void's ink (x_ffill): the
        ld a,(VCENTRE)          ; camera's margins hold no other place's scenery nor black
        or a
        jr z,.snap
        nextreg 0x51,XPAGE
        call x_ffill
        nextreg 0x51,0xFF
        jr .snap
.nf:    ld a,(VSMOOTH)
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
.snap:  xor a
        ld (FRSH2),a
        ld hl,(OX)
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
        nextreg 0x15,0x41       ; sprites visible, S L U, sprite 0 on top (session 10: p_spr numbers the front
                                ; record's groups first; with bit 6 clear, sprite 127 was on top and the droids
                                ; behind the player were drawn in front of him)
        ld a,2
        ld bc,0x123B
        out (c),a
        ret

; session 9: p_inks and recell run from page 25 (x_inks, x_recell)
p_inks: nextreg 0x51,XPAGE
        call x_inks
        nextreg 0x51,0xFF
        ret

;p_spr: after E656 (the blocks are on the screen): every draw record (A320, AF09 of them) as sprites, the last
; record (drawn last, in front) first, so it takes the lowest sprite numbers (sprite 0 on top: NR 0x15 bit 6,
; set by p_pre). Enemies: one group
; (image 4 (type - 1) + frame); the player: a group per part (second weapon, dome + AFA4, weapon, drive, chassis);
; others: the record's list. Groups not used since the last update are hidden.
p_spr:  ld a,(L2ON)
        or a
        ret z
        call offs
        ld hl,(TX)              ; session 5: the view these records belong to, and the player in it
        ld (STX),hl
        ld a,(TY)
        ld (STY),a
        ld hl,(0xAF94)
        ld (PSX),hl
        ld e,l
        ld d,0
        push hl
        ld hl,(PSCX)            ; a player group's offset from the shown player (screen) and this update's AF94 / 95
        or a
        sbc hl,de
        ld (PKX),hl
        pop hl
        ld e,h
        ld hl,(PSCY)
        or a
        sbc hl,de
        ld (PKY),hl
        ld hl,0
        ld (PG0),hl
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
        call ipre               ; session 9: Centred view: this update's interpolation starts
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
        ld a,(VCENTRE)
        ld (PLR),a
        ld a,(GRP)
        ld (PG0),a
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
        ld a,(GRP)
        ld (PG1),a
        xor a
        ld (PLR),a
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
        call ipol               ; session 9: a droid's or shot's offset from its last place (Centred view)
        ld hl,SDX               ; session 5: a player group in Centred view: PKX / PKY (the shown player)
        ld a,(PLR)
        or a
        jr z,.np
        ld hl,PKX
.np:    ld a,(hl)
        inc hl
        push hl
        ld h,(hl)
        ld l,a
        add hl,de
        ex de,hl
        pop hl
        inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
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
; 28 MHz, then NR 7 = the game's speed for the ISR body. Its time goes to the debt, left out of a running game routine's
; window (hlib_nest_open / _close); the ISR body is held out of every window (hlib_pace_hold here, hlib_pace_resume in
; wskipc after it). In a Centred step's window (WOPEN 3) the frame step is held out too (cw_close: the step's own time
; only). Keeps IX, IY, the alternate set; AF, BC, DE, HL lost.
isr_step:
        nextreg 0x07,3
        ld a,(HLIB_V_PACE + 10) ; an open window counted up to here (at least once a frame, as isr_in)
        or a
        call nz,hlib_pace_tick
        ld a,(WOPEN)
        cp 3
        call z,hlib_pace_hold
        ld a,(WOPEN)
        cp 3
        call nz,hlib_nest_open
        nextreg 0x57,GPAGE      ; session 5: the whole frame step (glide or camera, the scroll registers, the
        call glide              ; sprites) runs from page 27 at slot 7 (interrupts are off; slot 6 stays free for S0)
        nextreg 0x57,1
        ld a,(WOPEN)
        cp 3
        jr z,.done
        ld a,C_ISR              ; (the same at any interrupted clock: the hook's state never depends on it)
        call hlib_nest_close
        call hlib_pace_hold
.done:  ld a,(GSPD)
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

; ---- the pace limiter (card patch.pace-limiter; target ORIGINAL), on the shared library (lib/hlib_pace.asm, below;
; session 11 of the refactor: the engine's own qline, dlines, mvtick, wown, ... replaced, the maths as before). Every
; hook's added time goes to the debt (DEBT = HLIB_V_PACE + 4): its work at 28 MHz measured on the video line (dbg_open ..
; dbg_close), its entry and exit at the caller's clock as a constant per hook (C_*). The game's own delay at DD80 repays
; it (t_dly: the loop starts shorter). With 6 or more blocks the game has no delay: a window's saving repays it, or the
; next update's delay. Interrupts: t_isr holds the library's count over the ISR (hlib_pace_hold / _resume), so an ISR is
; in no window and no debt window.

; dbg_open: a hook's own work starts: its time goes to the debt, left out of a running window (hlib_nest_open). In a
; Centred step's window (WOPEN 3) nothing: the step's whole time is the window's (cw_close). AF, BC, DE, HL lost.
dbg_open:
        ld a,(WOPEN)
        cp 3
        ret z
        ld a,1                  ; an ISR inside the hook ticks no window (isr_in / wtick, wsync): its time so far would be
        ld (NESTF),a            ; counted in the window, x K (v1.2's mvtick there was undone by WNEST)
        jp hlib_nest_open

; dbg_close: A = the hook's unmeasured part (1/16 lines). Debt += 16 x lines since dbg_open + A; inside a game routine's
; window (WOPEN 1: a nested hook, its entry and exit at 28 MHz) A / 8, that window going on without the hook's time
; (hlib_nest_close: Quazatron's WNEST, now the library's). WOPEN 3: nothing. AF, BC, DE, HL lost.
dbg_close:
        ld b,a
        ld a,(WOPEN)
        cp 3
        ret z
        dec a
        ld a,b
        jr nz,.n
        rrca
        rrca
        rrca
        and 0x1F
        add a,C_LIBP
        ld b,a                  ; WNS += A / 8 + C_LIBP (fw_wait takes it out of the routine's time, as v1.2's WNEST)
        ld hl,(WNS)
        add a,l
        ld l,a
        jr nc,.c
        inc h
.c:     ld (WNS),hl
        ld a,b
        sub C_LIBP
.n:     add a,C_LIBP + C_LIB    ; the library's own unmeasured work to the debt too
        call hlib_nest_close
        xor a                   ; (cleared after the close: an ISR before it ticks nothing, which is harmless)
        ld (NESTF),a
        jp wsync                ; a window goes on from here, after the close's own work (the library's reading is
                                ; taken before its debt sums: that tail would be counted in the window, x K; it is
                                ; in C_LIB, the hook's exit in A / 8, as v1.2's)

; dadd: DEBT += A (1/16 lines), capped (HLIB_PACE_CAP). WOPEN 3: nothing (cw_close sets the debt). AF, DE, HL lost.
dadd:   ld l,a
        ld a,(WOPEN)
        cp 3
        ret z
        ld h,0
        jp hlib_debt_add

; isr_in / isr_out: t_isr in the hook page (interrupts off): the ISR's time (frame step and body) is held out of every
; window and debt window (hlib_pace_hold / _resume). AF, BC, DE, HL lost.
isr_in: call wtick              ; an open window counted up to here: at least once a frame (a Centred step's window
        call hlib_pace_hold     ; lasts up to three; v1.2's mvtick did this), so no frame wrap is lost
        ld a,(SBUSY)            ; session 5: the frame step here too (not while p_spr writes the sprite ports), so
        or a                    ; the picture moves every frame
        ret nz
        nextreg 0x57,GPAGE
        call glide
        nextreg 0x57,1
        ret
isr_out:
        call hlib_pace_resume
; wsync: after an ISR (isr_out, wskipc) an open window goes on from now, as v1.2's MVL = now: the ISR's own work
; after its tick (isr_in / isr_step), held or not (the frame step's close, the hold), stays out of the window. The
; reading before the ISR would otherwise stand until the next interrupt's tick, a whole frame later, and the frame's
; wrap was lost (a Centred step's window lasts up to three frames). Never inside a nested hook (NESTF):
; hlib_nest_close moves the window on after it. AF, BC, DE, HL lost.
wsync:  call wopen
        ret z
        call hlib_now
        ld (HLIB_V_PACE),hl
        ld (HLIB_V_PACE + 18),de
        ret
; wtick: an open window counted up to now (isr_in: at least once a frame), never inside a nested hook. AF, BC, DE,
; HL lost.
wtick:  call wopen
        ret z
        jp hlib_pace_tick
; wopen: NZ when a window is open and no nested hook is (NESTF). AF lost.
wopen:  ld a,(NESTF)
        or a
        jr nz,.no
        ld a,(HLIB_V_PACE + 10)
        or a
        ret
.no:    xor a
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
        ld a,(WOPEN)            ; session 9: a second step before the copy (horizontal, then vertical, in one update):
        cp 3                    ; the window goes on. Restarting it here lost the first step's time from the debt (in
        ret z                   ; JNext about 68k T an update with two steps), so long scrolling ran slow
        push hl
        ld hl,(DEBT)
        ld (CWD),hl
        pop hl
.win:   push de
        push hl
        call hlib_pace_open     ; an ISR inside the move (run here, in the page) is held out of the window (isr_in /
        pop hl                  ; isr_out), and its body runs at the game's speed, as in the original
        pop de
        ld a,3
        ld (WOPEN),a
        ret

; mv_lddr / mv_ldir: the game's own block move, run in the page (an interrupt in it takes t_isr's hook-page path).
mv_lddr:
        lddr
        ret
mv_ldir:
        ldir
        ret

; mv_out: HL = the move's original time (1/16 lines). Fast scroll off: wait until the window has lasted that, less
; the debt (hlib_pace_wait; an ISR body inside it is held out, as it lengthened the original's move too; a debt over it
; is cut by what the move saved). Then the caller's speed. Keeps BC, DE; AF, HL lost.
mv_out: ld a,(VFAST)
        or a
        jr nz,.back             ; fast scroll: the burst's saving is its own (never in the debt)
        push bc
        push de
        xor a                   ; the target at 3.5 MHz, never scaled by the incoming clock (as v1.2)
        call hlib_pace_wait
        xor a
        ld (WOPEN),a
        pop de
        pop bc
.back:  ld a,(VSPD2)
        nextreg 0x07,a
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

; The window's time: the library's (hlib_pace_open .. hlib_pace_waitk); an ISR is held out (isr_in / isr_step:
; hlib_pace_hold, isr_out / wskipc: hlib_pace_resume), a nested hook's or the hook's own work's time is left out and goes
; to the debt (dbg_open / dbg_close: hlib_nest_open / _close).

; wskipc: from t_isr (game code) after the ISR body: the held time ends (hlib_pace_resume). Keeps BC, DE, HL; AF lost.
wskipc: push bc
        push de
        push hl
        call hlib_pace_resume
        call wsync
        pop hl
        pop de
        pop bc
        ret

; fw_open: A = K: the window opens, at 28 MHz. AF, BC, DE, HL lost.
fw_open:
        ld (WK),a
        nextreg 0x07,3
        call hlib_pace_open
        ld hl,0
        ld (WNS),hl
        ld a,1
        ld (WOPEN),a
        ret

; fw_mark: the game routine has returned: WOPEN = 2 (the hook's own work follows: dbg_open / dbg_close leave it out of
; the window with its full unmeasured part). AF lost.
fw_mark:
        ld a,2
        ld (WOPEN),a
        ret

; fw_wait: the window's target is the routine's time x K / 16: its saving repays the debt; what the debt does not take
; is waited out (hlib_pace_wait; no line counter: the library gives up). The routine's time is the window's lines less
; WNS (v1.2's WP = 16 MVE - WNEST); the window's count keeps WNS, so the target is lines x K - WNS x (K - 16) / 16
; (= WP x K / 16 + WNS): the same wait and the same debt as v1.2's fw_wait. WOPEN = 0, A = 0. AF, BC, DE, HL lost.
fw_wait:
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE + 2)
        ld a,(WK)
        call hlib_mul8          ; lines x K (saturating)
        push hl
        ld hl,(WNS)
        ld a,(WK)
        sub 16
        call hlib_mul8          ; WNS x (K - 16)
        ld b,4
.q:     srl h
        rr l
        djnz .q
        ex de,hl
        pop hl
        or a
        sbc hl,de
        jr nc,.t
        ld hl,0
.t:     xor a                   ; the target at 3.5 MHz, never scaled by the incoming clock (as v1.2)
        call hlib_pace_wait
        xor a
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
        ld a,1
        ld (SBUSY),a
        call p_spr
        xor a
        ld (SBUSY),a
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
fw_bs_m:                        ; (session 5: its window branch removed: BE38 never runs in a window)
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
        ld (HLIB_V_PACE + 10),a ; (a window left open, if any, is dropped with the debt)
        inc a
        ld (FRESH),a
        ld (FRSH2),a
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
; time (ISRs and frame steps held out; nested hooks add nothing in WOPEN 3, their time is the window's). WOPEN = 0.
; AF, BC, DE, HL lost.
cw_close:
        call hlib_pace_tick
        xor a
        ld (WOPEN),a
        ld (HLIB_V_PACE + 10),a ; the window closes without a wait
        ld hl,(HLIB_V_PACE + 2)
        call hlib_pace_wait.x16
        ld de,(CWD)
        add hl,de
        jp nc,hlib_debt_set
        ld hl,0xFFFF
        jp hlib_debt_set

; ---- session 9: droid and shot interpolation (Centred view). The camera glides, the player is drawn at it, and the
; droids and shots used to jump each update. Now each droid's or shot's group is matched to the nearest group of the
; same key (an enemy's type; else its image) in the last update, within IRAD px on each axis, each taken once; its
; sprites are drawn at the last place and glide to this one over IT frames (the last update's interval): the frame
; step (idec, page 27) counts the offset down. No match (a new droid, a new shot): no offset. Display only.

; ipre: from p_spr: IT = IR = the frames since the last update's sprites (2-8); this update's keys and places become
; the last update's; this update's keys = none. AF, BC, DE, HL lost; slot 6 = S0.
ipre:   ld a,(VCENTRE)
        or a
        ret z
        ld a,(FRMC)
        ld hl,FRML
        ld b,(hl)
        ld (hl),a
        sub b
        cp 2
        jr nc,.t1
        ld a,2
.t1:    cp 9
        jr c,.t2
        ld a,8
.t2:    ld (IT),a
        ld (IR),a
        nextreg 0x56,S0
        ld hl,IKEYA
        ld de,IKEYA + 0x80
        ld bc,0x80
        ldir
        ld hl,IKEYA
        ld b,MAXG
.f:     ld (hl),0xFF
        inc l
        djnz .f
        ret

; ipol: from group, S0 at slot 6, DE = base X, BC = base Y (SPOS stored): the group's offset DXA / DYA (0 for the
; player's groups and for no match); a droid's or shot's key and canvas place recorded, its match found. DE, BC += the
; offset (the update's own placing shows all of it). AF, HL lost.
ipol:   ld a,(VCENTRE)
        or a
        ret z
        ld a,(GRP)
        ld l,a
        xor a
        ld h,high DXA
        ld (hl),a
        ld h,high DYA
        ld (hl),a
        ld a,(PLR)
        or a
        ret nz
        push bc
        push de
        ld a,(GIMG)
        cp 128
        jr nc,.k
        and 0xFC                ; an enemy: its type (the image's frame dropped)
.k:     ld (IKY),a
        ld hl,(STX)             ; canvas x = STX + base X (mod 320)
        add hl,de
        bit 7,h
        jr z,.x1
        ld de,320
        add hl,de
        jr .x2
.x1:    call mod320
.x2:    ld (ICXV),hl
        ld a,(STY)
        add a,c
        ld (ICYV),a
        ld a,(GRP)
        ld l,a
        ld h,high IKEYA
        ld a,(IKY)
        ld (hl),a
        set 5,l
        ld a,(ICXV)
        ld (hl),a
        res 5,l
        set 6,l
        ld a,(ICXV + 1)
        ld (hl),a
        set 5,l
        ld a,(ICYV)
        ld (hl),a
        ld a,0xFF
        ld (IBST),a
        ld l,0x80
.q:     ld a,(IKY)
        cp (hl)
        jr nz,.qn
        push hl
        set 5,l
        ld e,(hl)
        res 5,l
        set 6,l
        ld d,(hl)               ; DE = its canvas x
        set 5,l
        ld a,(hl)
        ld hl,ICYV
        sub (hl)
        ld c,a                  ; C = dy (its - this)
        ex de,hl
        ld de,(ICXV)
        or a
        sbc hl,de
        call n320b              ; HL = dx
        ld a,h
        or a
        jr z,.p
        inc a
        jr nz,.no
        ld a,l
        neg
        jr .ab
.p:     ld a,l
.ab:    cp IRAD + 1
        jr nc,.no
        ld b,a
        ld a,c
        bit 7,a
        jr z,.p2
        neg
.p2:    cp IRAD + 1
        jr nc,.no
        add a,b                 ; |dx| + |dy|
        ld b,a
        ld a,(IBST)
        cp b
        jr c,.no
        jr z,.no                ; (a tie: the first)
        ld a,b
        ld (IBST),a
        ld a,l
        ld (IOX),a
        ld a,c
        ld (IOY),a
        pop hl
        push hl
        ld a,l
        ld (IBQ),a
.no:    pop hl
.qn:    inc l
        ld a,l
        cp 0x80 + MAXG
        jr c,.q
        pop de
        pop bc
        ld a,(IBST)
        inc a
        ret z                   ; no match
        ld a,(IBQ)
        ld l,a
        ld h,high IKEYA
        ld (hl),0xFE            ; taken
        ld a,(GRP)
        ld l,a
        ld h,high DXA
        ld a,(IOX)
        ld (hl),a
        ld h,high DYA
        ld a,(IOY)
        ld (hl),a
        ld a,(IOX)
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,de
        ex de,hl                ; DE += dx
        ld a,(IOY)
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,bc
        ld b,h
        ld c,l                  ; BC += dy
        ret

RTAB:   DB 128, 85, 64, 51, 43, 37, 32          ; 256 / T, T = 2..8 (the frame step's FCT)

; n320b: HL in -319..319 -> -160..159 (page 27's n320, here). AF, DE lost.
n320b:  ld de,160
        bit 7,h
        jr nz,.neg
        push hl
        or a
        sbc hl,de
        pop hl
        ret c
        ld de,-320
        add hl,de
        ret
.neg:   add hl,de
        bit 7,h
        ld de,-160
        add hl,de
        ret z
        ld de,320
        add hl,de
        ret

        INCLUDE "lib/hlib_pace.asm"     ; session 11 (refactor): the shared pace limiter, nested hooks included
TCODE_END:
        DISPLAY "TCODE_END ",/H,TCODE_END
        ASSERT TCODE_END <= IPV         ; (session 9: the interpolation state above it)
        ORG TCOL
        DUP 32, n
        DW TAGS + n * TS
        EDUP
PAGE_END:
        SAVEBIN "quazatron_page.bin",0x4000,PAGE_END-0x4000

; ============================================================================================================
; session 9: page 25 (XPAGE: bank 12's upper half, unused before), mapped at slot 1 (0x2000) only while a page-26 stub
; calls into it (p_tags, p_clr, p_paste, p_inks; NR 0x51 = XPAGE, then 0xFF: the alt ROM again). Page 25 also holds a
; copy of the ROM trampolines at their own addresses (quazatron.py xpage_image), so an interrupt taken here reaches
; t_isr as from the alt ROM; t_isr takes a PC below 0x3800 as hook-page code. Nothing here reads ROM bytes.
        ORG 0x2000
; x_tags: HL = the list just drawn into the strip. Repeat its geometry (B07F) into the tag strip: mask bits -> the
; list's role, OR bits -> 0 (ink), overwrite bits -> ink / role. A part of height 0 ends the list, as in B0EC.
x_tags: ld (LST),hl
        ld a,(G_AF2D)           ; session 9: W = the columns the paste takes (16 when AF2D = 1, else 32): parts wholly
        cp 1                    ; past it are skipped, the rest clipped to it (the canvas never sees columns >= W)
        ld a,16
        jr z,.w
        ld a,32
.w:     ld (XW),a
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
        ld a,(XW)
        add a,7
        sub l                   ; x + 7 < W + 7
        jr c,.xskip
        jr z,.xskip
        ; visible bits: jstart = max(0, -x), jend = min(8, 32 - x)
        xor a
        bit 7,b
        jr z,.js
        ld a,c
        neg                     ; -x (1..7)
.js:    ld (JST),a
        ld e,a                  ; E = jstart
        ld a,(XW)
        sub c                   ; W - x (x in -7..W-1 -> 1..W+7)
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
        call x_row
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

; x_row: HL = the first drawn glyph row; TROW, NROWS, P0, JST, JN, OPF, ROLE set.
x_row:
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
        ld a,TINK8
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
        bit 4,(hl)              ; session 9: ink tags are 8 (bit 4 clear), roles 16-25 (bit 4 set)
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
        ld (hl),TINK8
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

; x_clr: the strip was cleared to ink (C044): tag rows 0 .. AF17-1 of all 32 columns = 0.
x_clr:  ld a,(G_AF17)           ; session 9: the W columns the paste takes (16 when AF2D = 1, else 32), rows 0 ..
        or a                    ; AF17 - 1, = TINK8 (the ink tag); the columns are TS apart, so a full-height strip is
        ret z                   ; one block
        ld c,a
        ld a,(G_AF2D)
        cp 1
        ld b,16
        jr z,.w
        ld b,32
.w:     ld hl,TAGS
        ld a,c
        cp TS
        jr z,.all
.c:     push bc
        push hl
        ld (hl),TINK8
        dec c
        jr z,.c1
        ld d,h
        ld e,l
        inc de
        ld b,0
        ldir
.c1:    pop hl
        ld de,TS
        add hl,de
        pop bc
        djnz .c
        ret
.all:   ld (hl),TINK8           ; W x 152 bytes (2,432 or 4,864)
        ld d,h
        ld e,l
        inc de
        ld a,b
        cp 16
        ld bc,16 * TS - 1
        jr z,.a1
        ld bc,32 * TS - 1
.a1:    ldir
        ret


; x_paste: after C1A5: strip columns 0..W-1 (W = 16 if AF2D = 1, else 32), rows 0..AF17-1 -> canvas at
; (OX + AF14 * 8 + px, OY + AF15 + row); the canvas cells touched -> FLAGS XFL (session 9: TINK8 or 0xFF).
x_paste:
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
.f0:    ld a,(CY)               ; session 9: the cells' flag: TINK8 when every touched cell is wholly pasted (the strip's
        ld d,a                  ; top, height and left edge on the 8 x 8 grid: all its ink bytes are TINK8 now), else
        ld a,(G_AF17)           ; 0xFF (unknown)
        or d
        or l
        and 7
        ld a,TINK8
        jr z,.fl
        ld a,0xFF
.fl:    ld (XFL),a
        ld a,l
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
        push af
        call cellptr            ; HL = FLAGS + row * 40 + C (DE lost)
        pop de                  ; D = the cell row
        ld a,(hl)               ; session 10: a cell whose ink bytes held a known ink k (not TINK8): the bytes just
        cp 0xFF                 ; pasted take k now (ink bytes only; a wall face's tone is kept), so a cell the camera
        jr z,.fx                ; shows before the commit (a void cell, blue ink) is never drawn in the tag's black.
        cp TINK8                ; FLAGS = 0x80 + k: ink bytes k, faces not resolved, so the commit's x_inks recells it
        jr z,.fk                ; whole from the attribute (a face in a void cell, or a cell that now holds another
        and 0x0F                ; place); a second paste before the commit keeps k. TINK8: every ink byte is TINK8.
        ld b,a
        or 0x80
        ld (hl),a
        ld a,b
        call x_rcink            ; C = cell column, D = cell row, A = ink (maps a Layer 2 page at slot 6)
        nextreg 0x56,S0
        jr .fk
.fx:    ld a,(XFL)
        ld (hl),a
.fk:    pop de
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


; x_inks: after C05A + C0C3 (the attributes are current): every view cell's ink bytes = its attribute's ink.
x_inks: call rd56
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
        call x_recell             ; C = cell column, D = cell row, A = ink
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

; x_rcink (session 10): as x_recell, but only the ink bytes (< 16) -> A, whatever A is (a wall face's tone kept).
x_rcink: ld e,a
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
        ld h,a
        ld a,d
        add a,a
        add a,a
        add a,a
        ld l,a
        ld c,l
        ld b,8
        jr x_recell.blk

; x_recell: canvas cell (C column, D row): every ink byte (< 16) of its 8 x 8 -> A. Maps its page at slot 6.
x_recell: ld e,a
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
        ld c,l                  ; session 9: unrolled, one loop per ink kind (the same bytes as before)
        ld b,8
        ld a,e
        and 7
        jr z,.blk
.col:   DUP 8                   ; a coloured ink: every ink byte (< 16) and a wall face's ink (R_FACE) -> E
        ld a,(hl)
        cp 16
        jr c,$+6
        cp R_FACE
        jr nz,$+3
        ld (hl),e
        inc l
        EDUP
        ld l,c
        inc h
        djnz .col
        ret
.blk:   DUP 8                   ; black ink (0 or 8): the ink bytes -> E, a wall face's ink kept (the face tone)
        ld a,(hl)
        cp 16
        jr nc,$+3
        ld (hl),e
        inc l
        EDUP
        ld l,c
        inc h
        djnz .blk
        ret

; x_cvoid (session 10): CFV = the deck's void ink (B045's ink, bright -> 8-15). AF, B lost.
x_cvoid: ld a,(0xB045)
        ld b,a
        and 7
        bit 6,b
        jr z,.n
        or 8
.n:     ld (CFV),a
        ret

; x_ffill (session 10, p_pre at a view's first copy, Centred view): every canvas cell outside the committed view
; (OX, OY) -> the void's ink: columns OX + 256 .. + 319 at all lines, then columns OX .. + 255 at lines OY + 152 ..
; + 255. FLAGS of those cells = that ink.
x_ffill: call x_cvoid
        ld hl,(OX)
        ld de,256
        add hl,de
        call mod320
        ld (CFX0),hl
        ld a,8
        ld (CFW),a
        ld a,(OY)
        ld (CFY0),a
        ld a,32
        ld (CFH),a
        call x_cfr
        ld hl,(OX)
        ld (CFX0),hl
        ld a,32
        ld (CFW),a
        ld a,(OY)
        add a,152
        ld (CFY0),a
        ld a,13
        ld (CFH),a
        ; (falls into x_cfr)

; x_cfr (session 10): the canvas cells from (CFX0, CFY0), CFW x CFH cells (each 1-32), -> CFV, pixels and FLAGS
; (wrapping at 320 and 256). Uses slot 6 and gives back its page. AF, BC, DE, HL lost. Interrupts as on entry.
x_cfr:  ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (CFS6),a
        ld hl,(CFX0)
        ld a,(CFW)
        ld b,a
.cc:    push bc                 ; a cell column: its 8 canvas columns
        ld b,8
.col:   push bc
        push hl
        ld a,l                  ; page = L2PAGE + (x >> 5)
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
        pop hl
        push hl
        ld a,l
        and 31
        add a,0xC0
        ld h,a
        ld a,(CFY0)
        ld l,a
        ld a,(CFH)
        ld b,a
        ld a,(CFV)
.f:     DUP 8
        ld (hl),a
        inc l
        EDUP
        djnz .f
        pop hl
        inc hl
        call mod320
        pop bc
        djnz .col
        pop bc
        djnz .cc
        nextreg 0x56,S0         ; FLAGS: the cells' ink
        ld hl,(CFX0)
        ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        ld c,a                  ; first cell column (0-39)
        ld a,(CFW)
        ld b,a
.fc:    push bc
        ld a,(CFY0)
        rrca
        rrca
        rrca
        and 31
        ld e,a
        ld a,(CFH)
        ld b,a
.fr:    push bc
        push de
        ld a,e
        and 31
        call cellptr
        ld a,(CFV)
        ld (hl),a
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
        ld a,(CFS6)
        nextreg 0x56,a
        ret

XCODE_END:
        DISPLAY "XCODE_END ",/H,XCODE_END
        ASSERT XCODE_END <= 0x386E
        SAVEBIN "quazatron_xpage.bin",0x2000,XCODE_END-0x2000

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
        cp 0x38                 ; session 9: page 25's code (slot 1, below the trampolines) is hook-page code
        jr c,.hk
        cp 0x40
        jr c,.rom
        cp high TCODE_END + 1   ; session 8: only the hook page's code (c_pre in the printer buffer is game-side code)
        jr nc,.game
.hk:
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
        push hl                 ; (session 8: dconst inlined, its page bytes freed)
        push de
        call dadd
        pop de
        pop hl
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

; session 8, Centred view only (the sites are part of its toggle): a pace window over the game's figure compositing
; (DC24 .. DD79: each block gets its background (C20D) and every record's lists drawn into it (B07D)), run at 28 MHz:
; its original time is its 28 MHz time x KCMP; that saving repays the debt a scroll step leaves, the rest is waited
; out (fw_mark / fw_wait). JP at DC24 (LD HL,E700): O = 1, E = 1 + 2 + 3, N = 1 + 2 + 1 (LD HL) + 1 (JP): delta -10.
t_cmp:  nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        call spd_latch
        ld a,KCMP
        call fw_open
        ld a,-10 & 0x7F
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        ld hl,0xE700
        jp 0xDC27
; CALL at DD79 (CALL B77D, after the last block): the window's end. O = 1 (CALL) to B77D, E = 1 + 2 + 3,
; N = 1 + 2 + 1 (JP): delta -9.
t_cmpo: nextreg 0x52,HPAGE
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        call fw_mark
        call fw_wait
        ld a,-9 & 0x7F
        call hlib_r_set
        call spd_back
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        nextreg 0x52,ULAPAGE
        jp 0xB77D
ROM_END:
        ASSERT ROM_END + 20 <= 0x3D00  ; (session 8: c_pre is in RAM now)
        SAVEBIN "quazatron_rom.bin",0x386E,ROM_END-0x386E

; ============================================================================================================
; Page 27 (GPAGE, bank 13 upper half), mapped at slot 7 (0xE000) only inside isr_step (interrupts off; the hook page
; at slot 2, slot 6 free for S0). The smooth display's frame step.
        ORG 0xE000
; glide: Smooth scrolling alone: v1.0's glide (2 px a frame, 4 when more than 16 behind; 1 line, 2 when more than 8),
; the scroll registers, every sprite group at its base + (TX - DX, TY - DY): unchanged, moved here. Centred view: cam.
; SDX / SDY current (offs). AF, BC, DE, HL lost.
glide:  ld a,(VSMOOTH)
        or a
        ret z
        ld a,(L2ON)
        or a
        ret z
        call offs
        ld a,(VCENTRE)
        or a
        jp nz,cam
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
        jr z,gl_w
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
gl_w:   call wregs
        call offs
        ld hl,(SDX)
        ld (SSX),hl
        ld hl,(SDY)
        ld (SSY),hl
        jp sprites

; cam (session 5, Centred view): the camera is the player. Pd (the shown player, world position on the canvas, 8.8)
; moves at a constant speed from where it is to the player of the last update (STX + PSX, STY + PSY) over one update
; interval + 1 frame (U, measured in frames between updates): one update of latency, no stop while he walks steadily.
; The shown origin (DX, DY) = Pd - (128, 88), exactly, kept inside the area the canvas holds (LO..HI from the game's
; view, grown by each step, reset by a view's first copy); when that limit moves, it eases by half the gap a frame.
; Droids and shots: their base + (STX - DX, STY - DY): where the game put them, locked to the scenery. The player's
; groups: their base + PKX / PKY, so the player sits at (Pd - DX) on the screen.
cam:    ld a,(FRESH)
        or a
        jr z,.c1
        xor a                   ; a view's first copy: start again (the area = the view; Pd = the player now)
        ld (FRESH),a
        ld (LEFT),a
        ld hl,0
        ld (LOX),hl
        ld (LOY),hl
        ld hl,(TX)
        ld (LTX),hl
        ld a,(TY)
        ld (LTY),a
        call pnew
        call freset
        jp .fr
.c1:    ld hl,LOX               ; session 10: the area before this commit (cfill)
        ld de,OLDA
        ld bc,4
        ldir
        xor a
        ld (CFX),a
        ld (CFY),a
        ld hl,(TX)              ; a step's commit: the area grows by the new view (canvas 320 x 256: at most 64 px /
        ld de,(LTX)             ; 104 lines more than the view)
        or a
        sbc hl,de
        jr z,.cy
        call n320
        ld a,l
        ld (CFX),a
        ld hl,(TX)
        ld (LTX),hl
        ld hl,LOX
        ld c,64
        call vupd
.cy:    ld a,(LTY)
        ld b,a
        ld a,(TY)
        cp b
        jr z,.c3
        ld (LTY),a
        sub b
        ld (CFY),a
        ld hl,LOY
        ld c,104
        call vupd
.c3:    call cfill              ; session 10: the area's cells no committed view drew -> the void's ink
           ld hl,(FCW)             ; session 6: the frame count, then a new update's player into the history
        inc hl
        ld (FCW),hl
        ld a,(STAMP)
        ld hl,STAMPL
        cp (hl)
        jr z,.fr
        ld (hl),a
        call pnew
        ld hl,(PNX)             ; a jump of 65+ px or lines (a new place, not a walk): start again at the player
        ld de,(PDXI)
        or a
        sbc hl,de
        call n320
        call far
        jr nc,.rs
        ld a,(PNY)
        ld hl,PDY + 1
        sub (hl)
        ld l,a
        rla
        sbc a,a
        ld h,a
        call far
        jr nc,.rs
        call hpush
        jr .fr
.rs:    call freset
.fr:    call filt
.cam:   ld hl,(PDXI)            ; x: the target origin = Pd - 128, held inside LOX..HIX of TX
        ld de,128
        or a
        sbc hl,de
        ex de,hl
        ld hl,(TX)
        ex de,hl
        or a
        sbc hl,de
        call n320               ; HL = the offset from TX
        ld a,(LOX)
        call clo
        ld a,(HIX)
        call chi
        ld de,(TX)
        add hl,de
        call w320               ; HL = the target
        ld de,(DX)
        or a
        sbc hl,de
        call n320               ; the gap
        call ease
        ld de,(DX)
        add hl,de
        call w320
        ld (DX),hl
        ld a,(PDY + 1)          ; y: Pd - 88 in LOY..HIY of TY
        sub 88
        ld hl,TY
        sub (hl)
        ld hl,LOY
        call clo8
        ld hl,HIY
        call chi8
        ld hl,TY
        add a,(hl)
        ld hl,DY
        sub (hl)                ; the gap
        ld l,a
        rla
        sbc a,a
        ld h,a
        call ease
        ld a,(DY)
        add a,l
        ld (DY),a
        call wregs
        ld hl,(PDXI)            ; the shown player on the screen, and its groups' offsets
        ld de,(DX)
        or a
        sbc hl,de
        call n320
        ld (PSCX),hl
        ld a,(PSX)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld (PKX),hl
        ld a,(PDY + 1)
        ld hl,DY
        sub (hl)
        ld l,a
        ld h,0
        ld (PSCY),hl
        ld a,(PSY)
        ld e,a
        or a
        sbc hl,de
        ld (PKY),hl
        ld hl,(STX)             ; droids and shots: the view their records belong to
        ld de,(DX)
        or a
        sbc hl,de
        call n320
        ld (SSX),hl
        ld a,(DY)
        ld e,a
        ld a,(STY)
        sub e
        ld l,a
        rla
        sbc a,a
        ld h,a
        ld (SSY),hl
        call idec               ; session 9: the droids' and shots' offsets one frame on
        ; (falls into sprites)

; sprites: every group at its base + SSX / SSY, a player group (Centred view, PG0 <= g < PG1) at its base + PKX / PKY.
sprites:
        ld a,(GPREV)
        or a
        ret z
        nextreg 0x50,S0         ; SPOS through slot 0 (interrupts are off; the ROM is back before the ISR body)
        ld b,a
        ld hl,SPOS - 0xC000
        xor a
.g:     push bc
        push af                 ; A = group
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        ld hl,SSX
        call ispl
        jr z,.o
        ld hl,PKX
.o:     ld (SOFF),hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        add hl,de
        ex de,hl                ; DE = X
        pop hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        push hl
        ld hl,(SOFF)
        inc hl
        inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        add hl,bc               ; HL = Y
        pop bc                  ; BC = SPOS pointer
        pop af
        call iadd               ; session 9: a droid's or shot's interpolation offset (Centred view)
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
        nextreg 0x50,0xFF
        ret

; ispl: A = group -> NZ for a player group in Centred view (PG0 <= A < PG1). Keeps A, BC, DE, HL.
ispl:   push bc
        ld c,a
        ld a,(VCENTRE)
        or a
        jr z,.x
        ld a,(PG0)
        ld b,a
        ld a,c
        cp b
        jr c,.no
        ld a,(PG1)
        ld b,a
        ld a,c
        cp b
        jr nc,.no
        or 1
        jr .x
.no:    xor a
.x:     ld a,c
        pop bc
        ret

; session 6: the camera filter (work/s6/camint.py is the same arithmetic, and the verifier runs it): the shown player PC
; (PDXI.PDXF, PDY) moves at a velocity V that eases (1/8 a frame) toward the player's mean velocity over the last 8
; updates (VE = distance / frames) plus a pull (1/16 of the gap a frame) toward the newest player as he was D frames
; ago on that line, never past him. Steady walking: a constant px a frame; a stop: no overshoot past where he stopped.
FK      EQU 8
FD      EQU 8
; freset: the history = the player now; PC = him, V = 0. AF, BC, DE, HL lost.
freset: ld a,1
        ld (HN),a
        ld hl,(FCW)
        ld (HT),hl
        ld hl,(PNX)
        ld (HSX),hl
        ld a,(PNY)
        ld (HSY),a
        call psnap
        ld hl,0
        ld (VX),hl
        ld (VY),hl
        ret
; hpush: the player (PNX, PNY) at frame FCW into the history (the oldest out when 8 are held). AF, BC, DE, HL lost.
hpush:  ld a,(HN)
        cp FK
        jr c,.n
        ld hl,HT + 2
        ld de,HT
        ld bc,2 * FK - 2
        ldir
        ld hl,HSX + 2
        ld de,HSX
        ld bc,2 * FK - 2
        ldir
        ld hl,HSY + 1
        ld de,HSY
        ld bc,FK - 1
        ldir
        jr .s
.n:     inc a
        ld (HN),a
.s:     ld a,(HN)
        dec a
        ld e,a
        ld d,0
        ld hl,HSY
        add hl,de
        ld a,(PNY)
        ld (hl),a
        ex de,hl
        add hl,hl
        push hl
        ld de,HT
        add hl,de
        ld de,(FCW)
        ld (hl),e
        inc hl
        ld (hl),d
        pop hl
        ld de,HSX
        add hl,de
        ld de,(PNX)
        ld (hl),e
        inc hl
        ld (hl),d
        ret
; filt: one frame of the filter (nothing with fewer than 2 updates held). AF, BC, DE, HL lost.
filt:   ld a,(HN)
        cp 2
        ret c
        dec a
        ld l,a
        ld h,0
        ld de,HSY
        add hl,de
        ld a,(hl)
        ld (P1Y),a
        ld a,(HN)
        dec a
        ld l,a
        ld h,0
        add hl,hl
        push hl
        ld de,HSX
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (P1X),de
        pop hl
        ld de,HT
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = t1
        ld hl,(FCW)
        or a
        sbc hl,de
        push de
        ld de,-FD
        add hl,de
        ld (FN),hl              ; n = frames since the newest - D
        pop de
        ld hl,(HT)
        ex de,hl
        or a
        sbc hl,de               ; t1 - t0
        ld a,h
        or a
        jr z,.d1
        xor a                   ; over 255 frames: no velocity
        jr .d2
.d1:    ld a,l
.d2:    ld (UU),a
        ; x
        ld hl,(P1X)
        ld de,(HSX)
        or a
        sbc hl,de
        call n320
        call c127
        ld h,l
        ld l,0
        call vest
        ld (VEX),hl
        call voff               ; DE = the offset along the line
        push de
        ld hl,(P1X)
        ld de,(PDXI)
        or a
        sbc hl,de
        call n320
        ld h,l
        ld l,0
        ld a,(PDXF)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        pop de
        add hl,de               ; err
        ld de,(VEX)
        ld bc,VX
        call vnext              ; HL = V
        ld a,(PDXF)
        add a,l
        ld (PDXF),a
        ld e,h
        ld d,0
        bit 7,h
        jr z,.x2
        dec d
.x2:    ld hl,(PDXI)
        adc hl,de
        call w320
        ld (PDXI),hl
        ; y
        ld a,(P1Y)
        ld hl,HSY
        sub (hl)
        ld h,a
        ld l,0
        call vest
        ld (VEY),hl
        call voff
        push de
        ld a,(P1Y)
        ld hl,PDY + 1
        sub (hl)
        ld h,a
        ld l,0
        ld a,(PDY)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        pop de
        add hl,de
        ld de,(VEY)
        ld bc,VY
        call vnext
        ld de,(PDY)
        add hl,de
        ld (PDY),hl
        ret
; c127: HL signed -> L = HL held to -127..127. AF lost.
c127:   bit 7,h
        jr nz,.n
        ld a,h
        or a
        jr nz,.p
        bit 7,l
        ret z
.p:     ld l,127
        ret
.n:     ld a,h
        inc a
        jr nz,.m
        bit 7,l
        ret nz
.m:     ld l,-127
        ret
; vest: HL = distance x 256 (signed) -> HL = VE = it / UU (the frames; 0: VE = 0), toward zero. AF, BC, DE lost.
vest:   ld a,(UU)
        or a
        jp nz,sdiv
        ld hl,0
        ret
; voff: HL = VE -> DE = VE x n when n = FN < 0 (behind the newest on its line), else 0. AF, BC, HL lost.
voff:   ld de,0
        ld a,(FN + 1)
        bit 7,a
        ret z
        ld a,(FN)
        neg                     ; -n: 1..D
        ld b,a
.l:     ex de,hl
        or a
        sbc hl,de               ; DE - HL ... (DE - VE)
        ex de,hl
        djnz .l
        ret
; vnext: HL = err (8.8), DE = VE, BC -> V: V += ((VE + err >> 4) - V) >> 3; -> HL = the new V. AF, DE lost.
vnext:  sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        add hl,de               ; desired
        ld a,(bc)
        ld e,a
        inc bc
        ld a,(bc)
        ld d,a                  ; DE = V
        or a
        sbc hl,de               ; desired - V
        sra h
        rr l
        sra h
        rr l
        sra h
        rr l
        add hl,de               ; V + that
        ld a,h
        ld (bc),a
        dec bc
        ld a,l
        ld (bc),a
        ret

; pnew: PNX = STX + PSX (mod 320), PNY = STY + PSY: the player of the last update on the canvas. AF, DE, HL lost.
pnew:   ld hl,(STX)
        ld a,(PSX)
        ld e,a
        ld d,0
        add hl,de
        call w320
        ld (PNX),hl
        ld a,(STY)
        ld hl,PSY
        add a,(hl)
        ld (PNY),a
        ret
; psnap: Pd = the target exactly (fractions 0, no segment left). AF, HL lost.
psnap:  ld hl,(PNX)
        ld (PDXI),hl
        xor a
        ld (PDXF),a
        ld (LEFT),a
        ld (PDY),a
        ld a,(PNY)
        ld (PDY + 1),a
        ret
; far: HL signed -> C when |HL| < 65 (a walk), NC for a jump. AF lost.
far:    push hl
        bit 7,h
        jr z,.p
        call neghl
.p:     ld de,65
        or a
        sbc hl,de
        pop hl
        ret
; sdiv: HL signed (8.8) / UU -> HL (8.8 a frame), rounded toward zero. AF, BC, DE lost.
sdiv:   bit 7,h
        push af
        jr z,.p
        call neghl
.p:     ld a,(UU)
        ld c,a
        xor a
        ld b,16
.d:     add hl,hl
        rla
        jr c,.s
        cp c
        jr c,.n
.s:     sub c
        inc l
.n:     djnz .d
        pop af
        ret z
        jp neghl
; n320: HL in -319..319 -> -160..159 (mod 320). AF, DE lost.
n320:   ld de,160
        bit 7,h
        jr nz,.neg
        push hl
        or a
        sbc hl,de
        pop hl
        ret c
        ld de,-320
        add hl,de
        ret
.neg:   add hl,de
        bit 7,h
        ld de,-160
        add hl,de
        ret z
        ld de,320
        add hl,de
        ret
; w320: HL in -320..639 -> 0..319. AF, DE lost.
w320:   bit 7,h
        jr z,.p
        ld de,320
        add hl,de
        ret
.p:     jp mod320
; clo / chi: HL signed, A = a signed 8-bit limit: HL = max(HL, A) / min(HL, A). AF, DE lost.
clo:    call sx8
        push hl
        or a
        sbc hl,de
        pop hl
        ret p                   ; HL >= limit (the offsets stay well inside 16 bits)
        ex de,hl
        ret
chi:    call sx8
        push hl
        or a
        sbc hl,de
        pop hl
        ret m
        ex de,hl
        ret
sx8:    ld e,a
        rla
        sbc a,a
        ld d,a
        ret
; clo8 / chi8: A signed, (HL) a signed limit: A = max / min. F lost.
clo8:   push bc
        ld b,a
        sub (hl)
        jp po,.v
        xor 0x80
.v:     ld a,b
        pop bc
        ret p
        ld a,(hl)
        ret
chi8:   push bc
        ld b,a
        sub (hl)
        jp po,.v
        xor 0x80
.v:     ld a,b
        pop bc
        ret m
        ret z
        ld a,(hl)
        ret
; ease: HL = the gap (signed px) -> HL = the move now: the whole gap up to 8 px (a walk is followed exactly),
; else half of it (an eased catch-up, never past). AF, DE lost.
ease:   push hl
        bit 7,h
        jr z,.p
        call neghl
.p:     ld de,9
        or a
        sbc hl,de
        pop hl
        ret c
        sra h
        rr l
        ret
; vupd: A = the view's move (signed), HL -> lo, hi (signed bytes, the canvas area held around the view), C = the
; most it can exceed the view: lo = min(lo - d, 0), hi = max(hi - d, 0), then the far side trimmed. AF, B, HL lost.
vupd:   ld b,a
        ld a,(hl)
        sub b
        bit 7,a
        jr nz,.l
        xor a
.l:     ld (hl),a
        inc hl
        ld a,(hl)
        sub b
        bit 7,a
        jr z,.h
        xor a
.h:     ld (hl),a
        dec hl
        sub (hl)                ; hi - lo
        cp c
        ret c
        ret z
        ld a,b
        bit 7,a
        jr nz,.n
        inc hl                  ; moved + : lo = hi - C
        ld a,(hl)
        sub c
        dec hl
        ld (hl),a
        ret
.n:     ld a,(hl)               ; moved - : hi = lo + C
        add a,c
        inc hl
        ld (hl),a
        ret

; ---- session 9 (page 27): idec, from cam each frame: FRMC + 1; while IR: IR - 1 and FCT = IR x 256 / IT (from RTAB),
; the share of each droid's or shot's offset still shown (0 when IR reaches 0). iadd, from sprites: that share of a
; droid's or shot's offset (DXA / DYA in S0, read through slot 0) added to its place. Nothing here writes S0.
idec:   ld hl,FRMC
        inc (hl)
        ld a,(IR)
        or a
        ret z
        dec a
        ld (IR),a
        ld e,a                  ; FCT = IR x RTAB[IT - 2]
        ld hl,RTAB - 2
        ld a,(IT)
        add a,l
        ld l,a
        adc a,h
        sub l
        ld h,a
        ld d,(hl)
        xor a
        inc e
.m:     dec e
        jr z,.w
        add a,d
        jr .m
.w:     ld (FCT),a
        ret
; iadd: A = group, DE = X, HL = Y -> + round(its offset x FCT / 256) for a droid's or shot's group in Centred view.
; Keeps A, BC.
iadd:   push bc
        push af
        ld c,a
        ld a,(VCENTRE)
        or a
        jr z,.x
        ld a,c
        call ispl
        jr nz,.x
        ld a,(IR)
        or a
        jr z,.x                 ; the offsets all drawn in
        push hl
        ld l,c
        ld h,high (DXA - 0xC000)
        ld a,(hl)
        call ishr
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,de
        ex de,hl
        ld l,c
        ld h,high (DYA - 0xC000)
        ld a,(hl)
        call ishr
        pop hl
        ld c,a
        rla
        sbc a,a
        ld b,a
        add hl,bc
.x:     pop af
        pop bc
        ret
; ishr: A = an offset (px, signed) -> A = its share: sign x ((|A| x FCT + 128) >> 8). BC kept; AF lost.
ishr:   push bc
        push de
        push hl
        ld c,a
        bit 7,a
        jr z,.p
        neg
.p:     ld e,a
        ld d,0
        ld a,(FCT)
        ld hl,0
        ld b,8
.m:     add hl,hl
        rla
        jr nc,.n
        add hl,de
.n:     djnz .m
        ld a,l                  ; (HL + 128) >> 8
        add a,0x80
        ld a,h
        adc a,0
        bit 7,c
        jr z,.q
        neg
.q:     pop hl
        pop de
        pop bc
        ret

; cfill (session 10, Centred view, from cam at a step's commit): the area the camera may show (LO..HI around the
; view) is a box; the views it was grown from are not. After an x step the new strip's columns were drawn for the
; view's lines only, so in the area's y margins they hold another place (or nothing): those cells, and after a y step
; the new band's lines in the x margins, take the deck's void ink (x_cfr) before the camera can reach them. Columns
; the old area already held are left alone. AF, BC, DE, HL lost.
cfill:  ld a,(CFX)
        or a
        call nz,cf_x
        ld a,(CFY)
        or a
        ret z
        ld b,a                  ; dy
        bit 7,a
        jr nz,.n
        ld a,(OLDA + 3)         ; down: lines 152 + HIYo - dy .. 151 are new where HIYo < dy
        ld c,a
        ld a,b
        sub c
        ret c
        ret z
        ld c,a
        ld a,(TY)
        add a,152
        sub c
        jr .r
.n:     ld a,(OLDA + 2)         ; up: lines 0 .. LOYo - dy - 1 are new where LOYo - dy > 0
        sub b
        ret z
        ret m
        ld c,a
        ld a,(TY)
.r:     ld (CFY0),a
        ld a,c
        rrca
        rrca
        rrca
        and 31
        ld (CFH),a
        ld a,(LOX)              ; the x margins
        or a
        jr z,.h
        neg
        rrca
        rrca
        rrca
        and 31
        ld (CFW),a
        ld a,(LOX)
        ld l,a
        rla
        sbc a,a
        ld h,a
        ld de,(TX)
        add hl,de
        call w320
        ld (CFX0),hl
        call cfr
.h:     ld a,(HIX)
        or a
        ret z
        rrca
        rrca
        rrca
        and 31
        ld (CFW),a
        ld hl,(TX)
        ld de,256
        add hl,de
        call mod320
        ld (CFX0),hl
        jr cfr
cf_x:   ld b,a                  ; dx
        bit 7,a
        jr nz,.n
        ld a,(OLDA + 1)         ; right: columns 256 + HIXo - dx .. 255 are new where HIXo < dx
        ld c,a
        ld a,b
        sub c
        ret c
        ret z
        ld c,a
        ld hl,(TX)
        ld de,256
        add hl,de
        ld e,c
        ld d,0
        or a
        sbc hl,de
        call mod320
        jr .r
.n:     ld a,(OLDA)             ; left: columns 0 .. LOXo - dx - 1 are new where LOXo - dx > 0
        sub b
        ret z
        ret m
        ld c,a
        ld hl,(TX)
.r:     ld (CFX0),hl
        ld a,c
        rrca
        rrca
        rrca
        and 31
        ld (CFW),a
        ld a,(LOY)              ; the y margins
        or a
        jr z,.h
        neg
        rrca
        rrca
        rrca
        and 31
        ld (CFH),a
        ld a,(LOY)
        ld hl,TY
        add a,(hl)
        ld (CFY0),a
        call cfr
.h:     ld a,(HIY)
        or a
        ret z
        rrca
        rrca
        rrca
        and 31
        ld (CFH),a
        ld a,(TY)
        add a,152
        ld (CFY0),a
cfr:    call x_cvoid_g
        nextreg 0x51,XPAGE      ; (interrupts are off in the frame step)
        call x_cfr
        nextreg 0x51,0xFF
        ret
x_cvoid_g:
        nextreg 0x51,XPAGE
        call x_cvoid
        nextreg 0x51,0xFF
        ret

; page 27's own state
        ORG 0xFF00
STAMPL: DB 0
FCNT:   DB 0
UU:     DB 2
LEFT:   DB 0
PDXF:   DB 0
PDXI:   DW 0
PDY:    DW 0                    ; fraction, line
VX:     DW 0
VY:     DW 0
PNX:    DW 0
PNY:    DB 0
LOX:    DB 0
HIX:    DB 0
LOY:    DB 0
HIY:    DB 0
LTX:    DW 0
LTY:    DB 0
SOFF:   DW 0
IH:     DB 0, 0, 0, 0           ; (session 5, unused)
FCW:    DW 0                    ; session 6: frames counted by the frame step
HN:     DB 0                    ; updates held in the history (1-8)
HT:     DS 16                   ; their frame counts (oldest first)
HSX:     DS 16                   ; the player's x (canvas, 0-319)
HSY:     DS 8                    ; his y (canvas line)
P1X:    DW 0
P1Y:    DB 0
FN:     DW 0
VEX:    DW 0
VEY:    DW 0
CFX:    DB 0                    ; session 10: cfill: this commit's x move (px, signed), y move, the area before it
CFY:    DB 0
OLDA:   DS 4
GPAGE_END:
        SAVEBIN "quazatron_page2.bin",0xE000,GPAGE_END-0xE000

; ============================================================================================================
; c_pre (Centred view): CALL at E0DC (was CALL D5BB) and JP E1EC at E1B3 (the edge bursts never start), in the
; Centred builds only. Pure Z80 at the game's speed, the same bytes in the reference game the proofs replay. Before
; each update, per axis, ONE of the game's own scroll steps (E0FB .. E1AC, which returns here) when the player moves
; that way and has passed the play area's centre (x 128, y 88) - session 5: the game's view always leads a camera
; that follows the player, so the shown window never reaches undrawn canvas. Velocity: the player's map dx, dy
; (AF90, AF91): screen x moves with dx + dy, screen y with dy - dx. Not moving on an axis: no step on it. A horizontal
; step, then a vertical one in the same update if needed, then the game's copy to the screen and AF2B = 0, so the
; update that follows is a normal one (droids move). AF2B 1-6 (the transfer and lift modes): no step.
C_ORG   EQU 0x5B40                ; session 8: in RAM (the printer buffer above the start-up tail, which the game never
        ORG C_ORG                 ; reads or writes: work/s8/ramfree.py), freeing the ROM area for the pace hooks
c_pre_:
c_pre:  ld a,(0xAF2B)
        and a
        jr z,c_h
        cp 7
        jp c,0xD5BB
        cp 0x1E
        jr c,c_v                ; after a horizontal step: the vertical check
c_cp:   call 0xC05A
c_ret:  xor a
        ld (0xAF2B),a
        jp 0xD5BB
c_h:    ld hl,(0xAF90)          ; L = dx, H = dy
        ld a,(0xAF94)
        ld d,a
        ld a,l
        add a,h
        ld c,128
        ld hl,0x0A14            ; + : right (0A), - : left (14)
        call c_ax
        jr nz,c_go
        call c_vd
        jr nz,c_go
        jp 0xD5BB
c_v:    call c_vd
        jr z,c_cp
c_go:   ld a,e
        ld (0xAF2B),a
        ld d,0
        ld hl,0xAF36
        add hl,de
        ld de,0xAF2C
        ld bc,10
        ldir
        ld a,1
        pop hl
        jp 0xE0FB
c_vd:   ld hl,(0xAF90)
        ld a,(0xAF95)
        ld d,a
        ld a,h
        sub l
        ld c,88
        ld hl,0x1E28            ; + : down (1E), - : up (28)
; c_ax: A = the velocity on the axis, D = the player's position, C = the centre, H / L = the step for + / -:
; -> NZ and E = the step when moving + and past the centre (D > C) or - and before it (D < C); else Z.
c_ax:   or a
        ret z
        ld e,h
        ld a,d
        jp p,c_ap
        ld e,l
        cp c
        jr c_ar
c_ap:   ld a,c
        cp d
c_ar:   sbc a,a
        ret
C_END_:
c_END:
        ASSERT C_END_ <= 0x5BB0
        SAVEBIN "quazatron_centre.bin",C_ORG,C_END_-C_ORG

; ============================================================================================================
; kmap (session 8, the 'Cursor keys + Space' toggle): CALL at B645 (was LD BC,001F / IN A,(C), then 2 NOPs): the
; game's Kempston read with the cursor keys and SPACE folded in - 5 left, 6 down, 7 up, 8 right (the Next's cursor keys
; are CAPS + these; an emulator's arrow keys press them) and SPACE fire - as Kempston bits (0 right, 1 left, 2 down,
; 3 up, 4 fire), ORed with the joystick. Pure Z80 at the game's speed, no branches: R is put back to what the
; original's LD BC / IN A,(C) leave (R read here = site + 3; after LD R,A: POP DE, LD A, RET, NOP, NOP = 5; want +3).
; BC = 001F and A = the value at the return, as the original; DE kept (B61F's destination pointer).
        ORG 0x5BB0
kmap:   ld a,r
        ld (KR),a
        push de
        ld bc,0xEFFE            ; 0 9 8 7 6: bit 2 = 8 (right), 3 = 7 (up), 4 = 6 (down)
        in a,(c)
        cpl
        ld e,a
        and 0x08                ; up -> bit 3
        ld d,a
        ld a,e
        rrca
        rrca
        and 0x05                ; 8 -> bit 0 (right), 6 -> bit 2 (down)
        or d
        ld d,a
        ld b,0xF7               ; 1 2 3 4 5: bit 4 = 5 (left)
        in a,(c)
        cpl
        rrca
        rrca
        rrca
        and 0x02                ; -> bit 1
        or d
        ld d,a
        ld b,0x7F               ; SPACE: bit 0
        in a,(c)
        cpl
        rlca
        rlca
        rlca
        rlca
        and 0x10                ; -> bit 4 (fire)
        or d
        ld d,a
        ld bc,0x001F
        in a,(c)                ; the joystick
        or d
        ld (KJ),a
        ld a,(KR)
        ld e,a
        and 0x80
        ld d,a
        ld a,e
        sub 5
        and 0x7F
        or d
        ld r,a
        pop de
        ld a,(KJ)
        ret
KR:     DB 0
KJ:     DB 0
KMAP_END:
        ASSERT KMAP_END <= 0x5C00
        SAVEBIN "quazatron_kmap.bin",0x5BB0,KMAP_END-0x5BB0

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
