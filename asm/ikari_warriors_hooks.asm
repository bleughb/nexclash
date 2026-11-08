; Ikari Warriors (Elite 1988, 48K) - every figure plotted into the back buffer becomes 4-bit hardware
; sprites; scenery, HUD and text stay on the ULA. Facts: games/ikari_warriors.md.
;
; The game composes each game frame in an 8K circular buffer, exactly MMU slot 6 (0xC000-0xDFFF, 32 bytes
; a line, origin (0xE460)) and blits a 22 x 168 window to the screen. Main loop: logic, scenery tiles,
; draw figures (0xEBAA..0xEBC2), blit (0xEBC5), erase figures LIFO (0xEBC8..0xEBDD). Interrupts are off in play.
; Method - the game's own code runs unchanged and every game byte stays as in the original:
;   0xEBAA  before the first figure of the frame: copy the blit's window to page C (the clean scenery)
;   0xEBC5  the blit runs with slot 6 = page C, so the ULA never shows a figure
;   0xEBC8  slot 6 back; commit: sprites from the log
;   the 7 plotters: log the figure; a new image is captured into a pattern (cache of 32 images)
; K1, the rotating masked plotter, is captured by running the game's own body twice on page S
; (backgrounds FF and 00); the others read their graphics stream directly.
;
; Hook code: alt ROM image 1, 0x2400 up, nothing at 0x3D00-. Page H = Next page 26 at slot 4 while a hook runs.

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"    ; macros only: HLIB_SPEED_IN
HLIB_V_PACE EQU 0x8040          ; 26 bytes of page H (0x8040-0x8059), zero at start (asm/lib/hlib_pace.asm)
HLIB_PACE_NL EQU 312            ; 48K timing, 50 Hz: lines a frame
T_BLIT  EQU 6130                ; the blit on the original: 25.9 ms, 1/16 lines (no interrupts in play)
K_LG    EQU 128                 ; e_lg's window: the original's time per unit of 28 MHz time, x 16
D_LG    EQU 512                 ; e_lg: least debt to act on, 1/16 lines
K_DR    EQU 128                 ; the figure phase's window, the same
A_HOOK  EQU 13                  ; a hook's 3.5 MHz entry and exit, 1/16 lines

HPG     EQU 26                  ; hook page, slot 4 while a hook runs
CPG     EQU 27                  ; clean scenery, slot 6 during the blit
SPG     EQU 28                  ; scratch, slot 6 during a K1 capture
STORE   EQU 29                  ; colour store, pages 29-31, slot 6 during an upload
GP4     EQU 4
GP6     EQU 0

ORIGIN  EQU 0xE460              ; buffer origin (game variable)
ASP     EQU 0xE4B0              ; the plotters' saved SP (game variable)
BLIT    EQU 0x62B2

MAXLOG  EQU 100

; ---- page H at 0x8000 ----
V_N     EQU 0x8000              ; figures logged this frame
V_PREV  EQU 0x8001              ; sprites shown by the last commit
V_SP    EQU 0x8002              ; game SP while a hook runs
V_PHASE EQU 0x8004              ; 1 = between the frame's first draw and the blit
V_RR    EQU 0x8005              ; cache round robin
V_COL   EQU 0x8006              ; 1 = the colour store has entries (Python / recolour)
V_STAMP EQU 0x8007              ; frame stamp
V_STOLEN EQU 0x8008             ; cache entries taken while on show (counted, verify)
V_E     EQU 0x8009              ; entry index
V_S     EQU 0x800A              ; next sprite slot
V_PAL   EQU 0x800B
V_Y     EQU 0x800C
V_DEST  EQU 0x800E
V_KEY   EQU 0x8010              ; 8 bytes; +7 = kind, never 0 in use
V_CB    EQU 0x8018              ; colour route: graphics base
V_CS    EQU 0x801A              ; pixels of rotation
V_CW    EQU 0x801B              ; graphics bytes per line
V_CK    EQU 0x801C              ; 0 = this image has no colour keys
V_TM    EQU 0x801D
V_O     EQU 0x801E
V_SP2   EQU 0x8020
V_X     EQU 0x8022
V_LN    EQU 0x8023
V_NIB   EQU 0x8024
V_XB    EQU 0x8025
V_TMP   EQU 0x8026
V_INK   EQU 0x8027              ; default ink index of the image being uploaded
V_FO    EQU 0x8028              ; K1: 0 = no fill or outline (ripples)
V_ATT   EQU 0x8029              ; word: the blit's attribute origin, in the clean copy
V_BIT   EQU 0x802B
V_FILL  EQU 0x802C              ; fill index: 14 paper, 13 black
V_OFS   EQU 0x802D
V_CELL  EQU 0x802E
V_HL    EQU 0x8030              ; e_ab
V_SPD   EQU 0x8036              ; the caller's CPU speed (lib/hlib_speed.asm latch; e_bl's carries to e_post)
V_A     EQU 0x8037              ; A while LEAVE restores the speed
V_DET   EQU 0x8034              ; K1: palette index of a cleared pixel: the paper, or I_DET in foliage
I_DET   EQU 8                   ; yellow, the body colour on sand: a foliage figure's detail on its black fill
V_RET   EQU 0x8032
V_CP    EQU 0x805A              ; (2) the next byte of the new image's patterns in CAPT
V_DRW   EQU 0x805E              ; 1 = the figure phase is in a K window
V_SPW   EQU 0x805D              ; the caller's speed through e_lg's window
V_L2N   EQU 0x805C              ; images in the store
CAPT    EQU 0x8C00              ; a new image's 4 tile patterns, 512 bytes, written out in one go
L2DIR   EQU 0x9600              ; the store's directory: 255 x 10: key 8, tile mask, (spare)
L2P0    EQU 32                  ; the store: Next pages 32-47, 16 images a page
LINES   EQU 0x9400              ; the blit's 168 screen line addresses, a private copy (Python fills it)
LINEOP  EQU 0x62C3              ; operand of the blit's LD SP,0x5B00
I_XOR   EQU 12                  ; XOR figures: by bank, black; bank 0 yellow over blue ink; bank 1 white in foliage
ENT     EQU 0x8100              ; 32 x 16: key 8, +8 tile mask, +9 stamp
LOG     EQU 0x8300              ; MAXLOG x 3: entry, dest
INK     EQU 0x8500              ; canvas 24 lines x 4 bytes
HOLE    EQU 0x8560
RSTK    EQU 0x8700              ; K1: the registers at entry, pushed below this
RETCELL EQU 0x8700
HSTK    EQU 0x9000
ATTC    EQU 0x9000              ; clean attribute buffer, 1K: bit 2 of H clear, so the blit's wrap still works
N0      EQU 0x8820              ; K1 image as palette indexes, 32 a line, one blank line above and below
ROWL    EQU 0x8B00              ; opaque spans: +y, or +x for the column tables
ROWR    EQU 0x8B20
COLT    EQU 0x8B40
COLB    EQU 0x8B60
I_FBLK  EQU 13                  ; palette: fill black
I_FPAP  EQU 14                  ; fill in the paper under the figure
I_OUT   EQU 15                  ; outline

        MACRO ENTER                     ; the caller's speed latched (on the hook stack), then 28 MHz
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPD
        ENDM

        MACRO ENTERB                    ; e_post, entered at the blit's speed: V_SPD stays e_bl's latch
        nextreg 0x54,HPG
        nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        ENDM

        MACRO LEAVE                     ; the caller's speed back (never a fixed 3.5 MHz); A and the flags kept
        ld sp,(V_SP)
        ld (V_A),a
        ld a,(V_SPD)
        nextreg 0x07,a
        ld a,(V_A)
        nextreg 0x54,GP4
        ENDM

        MACRO PUSHALL
        push af
        push bc
        push de
        push hl
        ENDM

        MACRO POPALL
        pop hl
        pop de
        pop bc
        pop af
        ENDM

        ORG 0x2400

; ---- 0xEB3B XOR A / LD (0xE465),A (the top of the loop) -> JP e_lg ---------------------------------
; A burst of new images ran up a debt larger than a blit can repay: this game frame's logic runs at 28 MHz in a K window,
; up to e_pre, and repays it.
e_lg:   nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push de
        push hl
        ld hl,(HLIB_V_PACE + 4)
        ld de,D_LG
        or a
        sbc hl,de
        jr c,.x
        HLIB_SPEED_IN V_SPW     ; its own latch: e_pre's ENTER latches 28 MHz
        push bc
        call hlib_pace_open
        pop bc
.x:     pop hl
        pop de
        ld sp,(V_SP)
        nextreg 0x54,GP4
        xor a
        ld (0xE465),a
        jp 0xEB3F

; ---- 0xEBAA CALL 0xF8C8 -> CALL e_pre: the clean copy --------------------------------------------
e_pre:  ENTER
        PUSHALL
        ld a,(HLIB_V_PACE + 10) ; e_lg's window open: the caller's speed and the wait for this game frame's logic
        or a
        jr z,.nw
        ld a,(V_SPW)
        ld (V_SPD),a
        ld c,a
        ld a,K_LG
        call hlib_pace_waitk
        ld hl,(HLIB_V_PACE + 4) ; still in debt: the figure phase, its plotters at 28 MHz, in a K window up to e_bl
        ld de,D_LG
        or a
        sbc hl,de
        jr c,.ok
        call hlib_pace_open
        ld a,3                  ; e_pre's LEAVE stays at 28 MHz
        ld (V_SPD),a
        nextreg 0x07,a
        ld a,1
        ld (V_DRW),a
        jr .nw
.ok:    xor a
        ld (V_DRW),a
.nw:
        call dbo
        ld hl,V_STAMP
        inc (hl)
        xor a
        ld (V_N),a
        inc a
        ld (V_PHASE),a
        ld hl,0xE000            ; the attributes before debris toggles them
        ld de,ATTC
        ld bc,1024
        ldir
        ld hl,(ORIGIN)
        ld de,0x0705            ; as the blit
        add hl,de
        res 5,h
neg_copy:
        nextreg 0x54,CPG        ; page C at 0x8000: dest = source - 0x4000. No stack here.
        ld a,h
        sub 0x40
        ld d,a
        ld e,l
        ld a,168
.line:
        REPT 22
        ldi
        ENDR
        ld bc,10
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        res 5,h
        res 5,d
        dec a
        jp nz,.line
        nextreg 0x54,HPG
        call dbc
        POPALL
        LEAVE
        jp 0xF8C8

; ---- 0xEBC5 CALL 0x62B2 -> CALL e_bl: the blit shows page C ---------------------------------------
e_bl:   ENTER
        PUSHALL
        ld a,(V_DRW)            ; the figure phase's K window: the caller's speed for the game's wait
        or a
        jr z,.nw
        xor a
        ld (V_DRW),a
        ld a,(V_SPW)
        ld (V_SPD),a
        ld c,a
        ld a,K_DR
        call hlib_pace_waitk
        nextreg 0x07,3
.nw:    call hlib_pace_open     ; the blit's window: at 28 MHz, the commit, then the wait (card patch.pace-limiter)
        ld hl,(0xE462)          ; the blit's attribute origin, moved to the clean copy: page H stays in
        ld a,h                  ; for the blit, and its LD HL,(0xE462) reads this word instead
        and 3
        or ATTC>>8
        ld h,a
        ld (V_ATT),hl
        ld hl,V_ATT
neg_att:
        ld (0x6340),hl
        ld hl,LINES             ; the game's table sits on KSTATE, so the ROM's keyboard scan damages it in attract
neg_lines:
        ld (LINEOP),hl
        POPALL
        ld sp,(V_SP)
neg_blit:
        nextreg 0x56,CPG
        jp BLIT                 ; still 28 MHz, up to e_post: it pays for the hooks' time (the game has no frame sync)

; ---- 0xEBC8 CALL 0x6711 -> CALL e_post: the commit ------------------------------------------------
e_post: nextreg 0x56,GP6
        ENTERB
        PUSHALL
        ld hl,0xE462            ; the blit's operands back
        ld (0x6340),hl
        ld hl,0x5B00
        ld (LINEOP),hl
        call commit
        xor a
        ld (V_PHASE),a
        ld hl,T_BLIT
        ld a,(V_SPD)
neg_wait:
        call hlib_pace_wait     ; until the blit's time on the original has passed, less the hooks' since the last one
        POPALL
        LEAVE
        jp 0x6711

; ---- 0xA984 0xA9B1 0xEB38 CALL 0x62B2 -> CALL e_ab: the blits outside the play loop (attract, hi-scores, start of a life) --
; Same line table fix, no stack of its own: the return address is swapped and put back, so even the dead
; bytes under SP end as the original's. Page H is in slot 4 during the blit, as for e_bl.
e_ab:   nextreg 0x54,HPG
        ld (V_HL),hl
        pop hl
        ld (V_RET),hl
        ld hl,e_abr
        push hl
        ld hl,LINES
neg_lines2:
        ld (LINEOP),hl
        ld hl,(V_HL)
        jp BLIT
e_abr:  ld (V_HL),hl
        ld hl,0x5B00
        ld (LINEOP),hl
        ld hl,(V_RET)
        push hl
        ld hl,(V_HL)
        nextreg 0x54,GP4
        ret

; ---- K1: 0x6D0E LD (ASP),SP -> JP e_k1: A = frame, IX = object ------------------------------------
e_k1:   ENTER
        ld sp,RSTK
        push af
        push bc
        push de
        push hl
        push iy
        ex af,af'
        push af
        ex af,af'
        exx
        push bc
        push de
        push hl
        exx
        ld sp,HSTK
        call dbo
        ld (V_KEY+0),a
        ld l,a                  ; colour route: 0xB700 + 36 * frame
        ld h,0
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
.c_b:   ld de,0xB700
        add hl,de
        ld (V_CB),hl
.c_key: ld a,(ix+2)
        and 0x89
        ld (V_KEY+1),a
        ld hl,(0x6D4B)          ; rotation code
        ld (V_KEY+2),hl
        ld hl,(0x6D42)          ; mask table
        ld (V_KEY+4),hl
        ld a,(0x6DAF)           ; wading: a second graphics pointer from line 6
        or a
        jr z,.nw
        ld a,(0x6DB9)
.nw:    ld (V_KEY+6),a
        ld a,1
        ld (V_KEY+7),a
        ld e,(ix+3)
        ld d,(ix+4)
        ld (V_DEST),de
        call find
        jr nc,.log
        call clearcanvas
        ld a,0xFF
        ld hl,HOLE
        call k1run
        xor a
        ld hl,INK
        call k1run
        ld hl,HOLE              ; FF background: a 0 bit is an opaque non-ink pixel
        ld b,18
.inv:   ld c,3
.inv2:  ld a,(hl)
        cpl
        ld (hl),a
        inc hl
        dec c
        jr nz,.inv2
        inc hl
        djnz .inv
        ld a,(V_KEY+1)
.c_ck:  and 1
        xor 1
        ld (V_CK),a             ; the AND-only variant keeps the default colours
.c_rot: ld a,(V_KEY+2)          ; rotation code -> pixels: 0x60 0, 0x56 2, 0x4C 4, 0x62 6
        ld b,0
        cp 0x60
        jr z,.s
        ld b,2
        cp 0x56
        jr z,.s
        ld b,4
        cp 0x4C
        jr z,.s
        ld b,6
.s:     ld a,b
        ld (V_CS),a
        ld a,2
        ld (V_CW),a
        ld (V_INK),a
        ld a,(V_KEY+0)          ; only frame 57 is a ripple; 58-62 are soldiers and must match the others
        sub 57
        jr z,.fo
        ld a,1
.fo:    ld (V_FO),a
        ld a,(V_KEY+1)          ; the AND-only variant, a figure in foliage or water, has no ink: black body
        and 1
        ld a,I_FPAP
        jr z,.fl
        ld a,I_FBLK
.fl:    ld (V_FILL),a
.c_det: ld hl,V_DET             ; its detail stands out from the foliage; ripples stay as drawn
        ld (hl),1
        cp I_FBLK
        jr nz,.fd
        ld a,(V_FO)
        or a
        jr z,.fd
        ld (hl),I_DET
.fd:
        call uploadn
.log:   call logit
        call dbc
neg_k1regs:
        ld sp,RSTK-18
        exx
        pop hl
        pop de
        pop bc
        exx
        ex af,af'
        pop af
        ex af,af'
        pop iy
        POPALL
        LEAVE
        ld (ASP),sp
        jp 0x6D12

; run the game's K1 body on page S: A = background, HL = canvas. The body ends LD SP,(ASP) / RET.
k1run:  ld (V_TMP),hl
        ld (V_SP2),sp
        nextreg 0x56,SPG
        ld de,(V_DEST)
        ld b,18
        ld c,a
.f:     ld a,c
        ld (de),a
        inc e
        ld (de),a
        inc e
        ld (de),a
        ld a,e
        add a,30
        ld e,a
        jr nc,.f2
        inc d
        res 5,d
.f2:    djnz .f
        ld hl,k1back
        ld (RETCELL),hl
        ld hl,RETCELL
        ld (ASP),hl
        ld sp,RSTK-18
        exx
        pop hl
        pop de
        pop bc
        exx
        ex af,af'
        pop af
        ex af,af'
        pop iy
        POPALL
        jp 0x6D12
k1back: ld sp,(V_SP2)
        ld hl,(V_DEST)
        ld de,(V_TMP)
        ld b,18
.c:     ld a,(hl)
        ld (de),a
        inc l
        inc de
        ld a,(hl)
        ld (de),a
        inc l
        inc de
        ld a,(hl)
        ld (de),a
        inc de
        xor a
        ld (de),a
        inc de
        ld a,l
        add a,30
        ld l,a
        jr nc,.c2
        inc h
        res 5,h
.c2:    djnz .c
        nextreg 0x56,GP6
        ret

; ---- K2 bullets: 0x67C5 LD H,(IX+7) -> JP e_k2: SP = stream of (mask, graphics) --------------------
e_k2:   ENTER
        PUSHALL
        call dbo
        call clearkey
        ld hl,(V_SP)
        ld (V_KEY+0),hl
        ld a,2
        ld (V_KEY+7),a
        ld e,(ix+6)
        ld d,(ix+7)
        ld (V_DEST),de
        call find
        jr nc,.log
        call clearcanvas
        ld hl,(V_SP)
        ld de,INK
        ld b,20                 ; 10 lines x 2 bytes
        ld c,0
.l:     ld a,(hl)               ; mask
        inc hl
        push af
        ld a,(hl)               ; graphics
        inc hl
        ld (de),a
        ld (V_NIB),a
        pop af
        push hl
        ld hl,V_NIB
        or (hl)                 ; 0 bit of mask | graphics = opaque non-ink
        cpl
        ld hl,HOLE-INK
        add hl,de
        ld (hl),a
        pop hl
        inc de
        inc c
        bit 0,c
        jr nz,.n
        inc de
        inc de
.n:     djnz .l
        call upload
.log:   call logit
        call dbc
        POPALL
        LEAVE
        ld h,(ix+7)
        jp 0x67C8

; ---- K3: 0x6980 LD BC,3102 -> JP e_k3: XOR, SP = stream, HL = dest; draw and erase come through here
e_k3:   ENTER
        PUSHALL
        ld a,(V_PHASE)
        or a
        jr z,.x
        call dbo
        ld (V_DEST),hl
        call clearkey
        ld hl,(V_SP)
        ld (V_KEY+0),hl
        ld a,3
        ld (V_KEY+7),a
        ld a,I_XOR
        ld (V_INK),a
        call find
        jr nc,.log
        call clearcanvas
        ld hl,(V_SP)
        ld de,INK
        ld b,24
.l:     ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        inc de
        djnz .l
        call upload
.log:   call logit
        call dbc
.x:     POPALL
        LEAVE
        ld bc,3102
        jp 0x6983

; ---- K4 dots: 0x6B8D LD C,192 / AND A -> JP e_k4: XOR, A = rotation, HL = dest ----------------------
; The original XORs (HL), then SET 5,L: on an odd line that is the same byte and the dot cancels.
e_k4:   ENTER
        PUSHALL
        ld c,a
        ld a,(V_PHASE)
        or a
        jr z,.x
        bit 5,l
.neg:   jr nz,.x
        call dbo
        ld (V_DEST),hl
        call clearkey
        ld a,c
        ld (V_KEY+0),a
        ld a,4
        ld (V_KEY+7),a
        ld a,I_XOR
        ld (V_INK),a
        call find
        jr nc,.log
        call clearcanvas
        ld a,(V_KEY+0)
        ld b,a
        ld a,0xC0
        inc b
.r:     dec b
        jr z,.rd
        rrca
        rrca
        jr .r
.rd:    ld (INK+0),a
        ld (INK+4),a
        call upload
.log:   call logit
        call dbc
.x:     POPALL
        LEAVE
        ld c,192
        and a
        jp 0x6B90

; ---- K5 pick-ups: 0xF845 JP 0xF7ED -> JP e_k5: opaque 2 x 14, HL = graphics (slot 4), DE = dest ------
e_k5:   ENTER
        PUSHALL
        call dbo
        ld (V_DEST),de
        call clearkey
        ld (V_KEY+0),hl
        ld (V_CB),hl
        ld a,5
        ld (V_KEY+7),a
        call find
        jr nc,.log
        call clearcanvas
        ld hl,(V_CB)
        ld de,INK
        ld b,28
        ld c,0
.l:     nextreg 0x54,GP4        ; no stack use while the game's page is in
        ld a,(hl)
        nextreg 0x54,HPG
        inc hl
        ld (de),a
        cpl
        push hl
        ld hl,HOLE-INK
        add hl,de
        ld (hl),a
        pop hl
        inc de
        inc c
        bit 0,c
        jr nz,.n
        inc de
        inc de
.n:     djnz .l
.c5:    ld a,5
        ld (V_CK),a
        xor a
        ld (V_CS),a
        ld a,2
        ld (V_CW),a
        call upload
.log:   call logit
        call dbc
        POPALL
        LEAVE
        jp 0xF7ED

; ---- K6 heavy objects: 0xF76A LD D,(IX+7) -> JP e_k6: 4 x 24, edges masked, HL = graphics -----------
e_k6:   ENTER
        PUSHALL
        call dbo
        call clearkey
        ld (V_KEY+0),hl
        ld (V_CB),hl
        ld a,(0xF779)
        ld (V_KEY+2),a
        ld a,(0xF784)
        ld (V_KEY+3),a
        ld a,6
        ld (V_KEY+7),a
        ld e,(ix+6)
        ld d,(ix+7)
        ld (V_DEST),de
        call find
        jr nc,.log
        ld hl,(V_CB)
        ld de,INK
        ld b,24
.l:     ld a,(V_KEY+2)
        call k6e
        xor a
        call k6e
        xor a
        call k6e
        ld a,(V_KEY+3)
        call k6e
        djnz .l
.c6:    ld a,6
        ld (V_CK),a
        xor a
        ld (V_CS),a
        ld a,4
        ld (V_CW),a
        call upload
.log:   call logit
        call dbc
        POPALL
        LEAVE
        ld d,(ix+7)
        jp 0xF76D
; A = AND mask, (HL) = graphics: DE -> INK; 0 bit of mask | graphics = opaque non-ink
k6e:    ld c,a
        ld a,(hl)
        inc hl
        ld (de),a
        or c
        cpl
        push hl
        ld hl,HOLE-INK
        add hl,de
        ld (hl),a
        pop hl
        inc de
        ret

; ---- K8 debris: 0x6879 LD BC,1055 -> JP e_k8: XOR 2 x 8 from the ROM, HL = dest ----------------------
e_k8:   ENTER
        PUSHALL
        ld a,(V_PHASE)
        or a
        jr z,.x
        call dbo
        ld (V_DEST),hl
        call clearkey
        ld a,(ix+3)
        and 2
        ld (V_KEY+0),a
        ld a,8
        ld (V_KEY+7),a
        ld a,4                  ; red: the ink the game toggles the debris's cell to
        ld (V_INK),a
        call find
        jr nc,.log
        call clearcanvas
        ld hl,300
        ld a,(V_KEY+0)
        or a
        jr z,.p
        ld hl,1020
.p:     ld de,INK
        ld b,8
.l:     ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        inc de
        inc de
        djnz .l
        call upload
.log:   call logit
        call dbc
.x:     POPALL
        LEAVE
        ld bc,1055
        jp 0x687C

; ---- sprites off where the game leaves the play loop ---------------------------------------------
        MACRO HIDEIT
        ENTER
        PUSHALL
        xor a
        ld (V_N),a
        ld (V_PHASE),a
        ld (V_S),a
        call hiderest
        POPALL
        LEAVE
        ENDM

e_h1:   HIDEIT                  ; 0xEB13 LD (61985),SP
        ld (61985),sp
        jp 0xEB17
e_h2:   HIDEIT                  ; 0xEC0C LD HL,63776: GAME OVER
        ld hl,63776
        jp 0xEC0F
e_h3:   HIDEIT                  ; 0xF214 LD HL,61990: end of a level
        ld hl,61990
        jp 0xF217
e_h4:   HIDEIT                  ; 0xAB7C LD IY,58470: back from play
        ld iy,58470
        jp 0xAB80

; ---- commit ---------------------------------------------------------------------------------------
commit: ld hl,(ORIGIN)
        ld de,0x0700
        add hl,de
        res 5,h
        ld (V_O),hl
        xor a
        ld (V_S),a
        ld a,(V_N)
        or a
        jr z,hiderest
        ld b,a
        ld hl,LOG
.n:     push bc
        ld a,(hl)
        ld (V_E),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        call emit
        pop hl
        pop bc
        djnz .n
hiderest:
        ld a,(V_S)
        ld c,a
        ld a,(V_PREV)
        ld b,a
        ld a,c
        ld (V_PREV),a
.h:     ld a,c
        cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc c
        jr .h

; DE = buffer address of the figure's top left byte
emit:   ld hl,(V_O)
        ex de,hl
        or a
        sbc hl,de
        ld a,h
        and 0x1F
        ld h,a
        ld a,l
        and 31
        ld b,a                  ; B = column
        add hl,hl
        add hl,hl
        add hl,hl               ; H = line in the window
        ld a,h
        cp 168
        jr c,.vis
        cp 232
        ret c
.vis:   add a,48                ; 32 + 16; a figure above the window wraps to 24..47
neg_pos:
        ld c,a                  ; C = sprite y
        ld (V_Y),a
        sub 23                  ; the hole colour: paper of the cell under the figure's centre
        jr nc,.r1
        xor a
.r1:    rrca
        rrca
        rrca
        and 31
        cp 2
        jr nc,.r2
        ld a,2
.r2:    cp 23
        jr c,.r3
        ld a,22
.r3:    ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,b
        inc a
        cp 5
        jr nc,.c1
        ld a,5
.c1:    cp 27
        jr c,.c2
        ld a,26
.c2:    ld e,a
        ld d,0x58
        add hl,de
        ld a,(hl)
        ld (V_CELL),a
        rrca
        rrca
        rrca
        and 15
        swapnib
        ld (V_PAL),a
        ld a,(V_E)              ; tile mask
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,ENT+8
        add hl,de
        ld a,(hl)
        ld (V_TM),a
        dec hl                  ; kind
        ld a,(hl)
        cp 3
        jr z,.xk
        cp 4
        jr nz,.nk
.xk:    ld a,(V_CELL)           ; a sprite cannot invert: the colour an inverted pixel would mostly show
        ld e,a
        and 7
        ld a,0x00
        jr nz,.xs
        ld a,e
        and 0x38
        cp 0x20
        ld a,(V_PAL)
        jr nz,.xs
        ld a,0x10
.xs:    ld (V_PAL),a
.nk:    ld a,(V_PAL)            ; green terrain: the body stays the yellow it has on sand, or it is lost in the foliage
        and 0x70
        cp 0x40
        jr nz,.ng
        ld a,0x60
        ld (V_PAL),a
.ng:    ld a,(hl)               ; K1's patterns have a margin of one pixel for the outline
        cp 1
        ld a,0
        jr nz,.o0
        inc a
        dec c
.o0:    ld (V_OFS),a
        ld l,b                  ; HL = sprite x = column * 8 + 32
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld a,(V_OFS)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld a,(V_E)
        add a,a
        add a,a
        ld d,a                  ; D = pattern
        ld e,0                  ; E = tile
.t:     ld a,(V_TM)
        rrca
        ld (V_TM),a
        jr nc,.nx
        ld a,(V_S)
        cp 128
        jr nc,.nx
        nextreg 0x34,a
        inc a
        ld (V_S),a
        push hl
        bit 0,e
        jr z,.tx
        ld a,16
        add a,l
        ld l,a
        ld a,0
        adc a,h
        ld h,a
.tx:    ld a,l
        nextreg 0x35,a
        ld a,c
        bit 1,e
        jr z,.ty
        add a,16
.ty:    nextreg 0x36,a
        ld a,(V_PAL)
        or h
        nextreg 0x37,a
        pop hl
        ld a,d
        or e
        ld (V_TMP),a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,(V_TMP)
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
.nx:    inc e
        ld a,e
        cp 4
        jr nz,.t
        ret

; ---- log and cache -------------------------------------------------------------------------------
logit:  ld a,(V_N)
        cp MAXLOG
        ret nc
        ld l,a
        inc a
        ld (V_N),a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,de
        ld de,LOG
        add hl,de
        ld a,(V_E)
        ld (hl),a
        inc hl
        ld de,(V_DEST)
        ld (hl),e
        inc hl
        ld (hl),d
        ret

clearkey:
        push hl
        ld hl,V_KEY
        ld b,8
.c:     ld (hl),0
        inc hl
        djnz .c
        xor a
        ld (V_CK),a
        ld a,2
        ld (V_INK),a
        pop hl
        ret

clearcanvas:
        ld hl,INK
        ld b,192
.c:     ld (hl),0
        inc hl
        djnz .c
        ret

entry:  ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,ENT
        add hl,de
        ret

; -> CY = new image (V_E chosen, key stored, stamp set); NC = found (V_E)
find:   ld c,0
.e:     ld a,c
        call entry
        ld de,V_KEY
        ld b,8
.k:     ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc hl
        djnz .k
        ld a,c
        ld (V_E),a
        inc hl                  ; +9
        ld a,(V_STAMP)
        ld (hl),a
        or a
        ret
.no:    inc c
        ld a,c
        cp 32
        jr nz,.e
        ld a,(V_RR)
        ld b,32
.a:     ld (V_E),a
        ld c,a
        call entry
        ld de,9
        add hl,de
        ld a,(V_STAMP)
        cp (hl)
        jr nz,.got
        ld a,c
        inc a
        and 31
        djnz .a
        ld hl,V_STOLEN
        inc (hl)
        ld a,(V_RR)
        ld (V_E),a
.got:   ld a,(V_E)
        inc a
        and 31
        ld (V_RR),a
        ld a,(V_E)
        call entry
        ex de,hl
        ld hl,V_KEY
        ld bc,8
        ldir
        xor a
        ld (de),a               ; tile mask
        inc de
        ld a,(V_STAMP)
        ld (de),a
        ; fall into l2get: a pattern the cache gave up may be in the store

; l2get: the store holds this key: its patterns back into V_E's 4 tiles, NC (found). Else CY = new image.
l2get:  ld a,(V_L2N)
        or a
        jr z,.new
        ld b,a
        ld hl,L2DIR
.e:     push bc
        push hl
        ld de,V_KEY
        ld b,8
.k:     ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc hl
        djnz .k
        ld a,(hl)               ; the tile mask
        pop hl
        pop bc
        push af
        ld a,(V_L2N)
        sub b                   ; the image's index
.neg_l2:
        call l2map
        ld a,(V_E)
        add a,a
        ld bc,0x303B
        out (c),a
        ld bc,0x005B
        otir
        otir
        nextreg 0x56,GP6
        ld a,(V_E)
        call entry
        ld de,8
        add hl,de
        pop af
        ld (hl),a
        or a
        ret
.no:    pop hl
        ld de,10
        add hl,de
        pop bc
        djnz .e
.new:   scf
        ret

; l2map: A = image -> slot 6 = its page of the store, HL = its 512 bytes there. AF lost.
l2map:  ld l,a
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,L2P0
        nextreg 0x56,a
        ld a,l
        and 15
        add a,a
        add a,0xC0
        ld h,a
        ld l,0
        ret

; uend: the new image's patterns out in one go, and a copy in the store (full: not kept). A = its tile mask, kept.
uend:   push af
        ld hl,CAPT
        ld bc,0x005B
        otir
        otir
        ld a,(V_L2N)
        cp 255
        jr z,.full
        ld l,a
        ld h,0
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de               ; x 10
        ld de,L2DIR
        add hl,de
        ex de,hl
        ld hl,V_KEY
        ld bc,8
        ldir
        pop af
        push af
        ld (de),a
        ld a,(V_L2N)
        call l2map
        ex de,hl
        ld hl,CAPT
        ld bc,512
        ldir
        nextreg 0x56,GP6
        ld hl,V_L2N
        inc (hl)
.full:  pop af
        ret

; cap: A = the next pattern byte of the new image. Every register kept.
cap:    push hl
        ld hl,(V_CP)
        ld (hl),a
        inc hl
        ld (V_CP),hl
        pop hl
        ret

; capi: the capture starts at the head of CAPT.
capi:   ld hl,CAPT
        ld (V_CP),hl
        ret

; dbo / dbc: this hook's time goes to the debt, the blit's window repays it (asm/lib/hlib_pace.asm). dbo keeps every
; register; dbc loses them; dtk (every register kept) reads the lines at least once a frame in a long hook.
dbo:    push af
        push bc
        push de
        push hl
        call hlib_nest_open
        pop hl
        pop de
        pop bc
        pop af
        ret
dbc:    ld a,A_HOOK
        jp hlib_nest_close
dtk:    push af
        push bc
        push de
        push hl
        call hlib_debt_tick
        pop hl
        pop de
        pop bc
        pop af
        ret

; ---- canvas -> 4 tile patterns, 32 x 32 --------------------------------------------------------
upload: call capi
        ld a,(V_E)
        add a,a
        ld bc,0x303B
        out (c),a
        xor a
        ld (V_TM),a
        ld e,0                  ; E = tile
.t:     ld d,0                  ; D = line in the tile
.ln:    ld a,e
        and 2
        add a,a
        add a,a
        add a,a
        add a,d                 ; canvas line
        ld (V_LN),a
        cp 24
        jr c,.in
        ld b,8                  ; below the canvas: clear
        xor a
.z:     call cap
        djnz .z
        jr .nl
.in:    push de
        ld a,e
        and 1
        add a,a                 ; canvas byte of this tile
        ld (V_XB),a
        call ubyte
        ld a,(V_XB)
        inc a
        ld (V_XB),a
        call ubyte
        pop de
.nl:    inc d
        ld a,d
        cp 16
        jr nz,.ln
        inc e
        ld a,e
        cp 4
        jr nz,.t
        nextreg 0x56,GP6
        ld a,(V_E)
        call entry
        ld de,8
        add hl,de
        ld a,(V_TM)
        ld b,a
        ld a,(V_COL)
        or a
        jr z,.nc
        ld a,(V_CK)
        or a
        jr z,.nc
        ld b,15
.nc:    ld (hl),b
        ld a,b
        jp uend

; one canvas byte (V_LN, V_XB) -> 8 pixels, 4 pattern bytes. Tile E is on the stack's DE.
ubyte:  ld a,(V_LN)
        add a,a
        add a,a
        ld l,a
        ld a,(V_XB)
        add a,l
        ld l,a
        ld h,INK>>8
        ld d,(hl)               ; D = ink
        ld a,HOLE&255
        add a,l
        ld l,a
        ld e,(hl)               ; E = hole
        ld a,d
        or e
        jr z,.empty
        pop hl                  ; the return address; below it the caller's DE = tile
        pop bc
        push bc
        push hl
        ld hl,V_TM
        ld a,c
        and 3
        inc a
        ld b,a
        xor a
        scf
.m:     rla
        djnz .m
        or (hl)
        ld (hl),a
.empty: ld a,(V_XB)
        add a,a
        add a,a
        add a,a
        ld (V_X),a
        ld b,4
.p:     push bc
        call pix
        swapnib
        ld (V_NIB),a
        call pix
        ld hl,V_NIB
        or (hl)
        call cap
        pop bc
        djnz .p
        ret

; next pixel of D (ink), E (hole), at V_X, V_LN -> A = palette index, V_X + 1
pix:    sla d
        jr c,.ink
        sla e
        ld a,0
        jr nc,.got
        ld a,1
        jr .got
.ink:   sla e
        ld a,(V_INK)
.got:   ld c,a
        ld a,(V_COL)
        or a
        jr z,.d
        ld a,(V_CK)
        or a
        jr z,.d
        push de
        call colour
        pop de
        or a
        jr z,.d
        ld c,a
.d:     ld hl,V_X
        inc (hl)
        ld a,c
        ret

; ---- K1: canvas -> indexes, fill, outline, 4 tile patterns ----------------------------------------
uploadn:
        ld hl,N0-32
        ld de,N0-31
        ld bc,22*32-1
        ld (hl),0
        ldir
        xor a
        ld (V_LN),a
.y:     call dtk
        xor a
        ld (V_XB),a
.xb:    ld a,(V_LN)
        add a,a
        add a,a
        ld l,a
        ld a,(V_XB)
        add a,l
        ld l,a
        ld h,INK>>8
        ld d,(hl)
        ld a,HOLE&255
        add a,l
        ld l,a
        ld e,(hl)
        ld a,(V_XB)
        add a,a
        add a,a
        add a,a
        ld (V_X),a
        ld a,8
        ld (V_BIT),a
.px:    call pix
        cp 1
        jr nz,.pd
        ld a,(V_DET)
.pd:    ld (V_NIB),a            ; V_X has moved on by one: the margin
        push de
        ld a,(V_LN)
        inc a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_X)
        ld e,a
        ld d,0
        add hl,de
        ld de,N0
        add hl,de
        ld a,(V_NIB)
        ld (hl),a
        pop de
        ld hl,V_BIT
        dec (hl)
        jr nz,.px
        ld a,(V_XB)
        inc a
        ld (V_XB),a
        cp 3
        jr nz,.xb
        ld a,(V_LN)
        inc a
        ld (V_LN),a
        cp 18
        jr nz,.y
        ld a,(V_FO)
        or a
        jp z,.out
        ld hl,ROWL              ; the spans
        ld b,0x20
.i1:    ld (hl),255
        inc hl
        djnz .i1
        ld b,0x20
.i2:    ld (hl),0
        inc hl
        djnz .i2
        ld b,0x20
.i3:    ld (hl),255
        inc hl
        djnz .i3
        ld b,0x20
.i4:    ld (hl),0
        inc hl
        djnz .i4
        ld hl,N0
        ld d,0                  ; D = y
.s1:    ld e,0                  ; E = x
.s2:    ld a,(hl)
        or a
        jr z,.s3
        push hl
        ld h,ROWL>>8
        ld l,d
        ld a,(hl)               ; first opaque x in the line: the lowest
        cp e
        jr c,.a1
        ld (hl),e
.a1:    ld a,d
        add a,0x20
        ld l,a
        ld a,e                  ; last
        cp (hl)
        jr c,.a2
        ld (hl),a
.a2:    ld a,e
        add a,0x40
        ld l,a
        ld a,(hl)               ; first opaque y in the column
        cp d
        jr c,.a3
        ld (hl),d
.a3:    ld a,e
        add a,0x60
        ld l,a
        ld a,d                  ; last
        cp (hl)
        jr c,.s4
        ld (hl),a
.s4:    pop hl
.s3:    inc hl
        inc e
        ld a,e
        cp 32
        jr nz,.s2
        inc d
        ld a,d
        cp 20
        jr nz,.s1
        ld hl,N0                ; fill: clear, opaque on both sides in its line and in its column
        ld d,0
.f1:    ld e,0
.f2:    ld a,(hl)
        or a
        jr nz,.f3
        ld b,ROWL>>8
        ld c,d
        ld a,(bc)               ; first < x
        cp e
        jr nc,.f3
        ld a,d
        add a,0x20
        ld c,a
        ld a,(bc)               ; last > x
        cp e
        jr c,.f3
        jr z,.f3
        ld a,e
        add a,0x40
        ld c,a
        ld a,(bc)               ; first < y
        cp d
        jr nc,.f3
        ld a,e
        add a,0x60
        ld c,a
        ld a,(bc)               ; last > y
        cp d
        jr c,.f3
        jr z,.f3
        ld a,(V_FILL)
        ld (hl),a
.f3:    inc hl
        inc e
        ld a,e
        cp 32
        jr nz,.f2
        inc d
        ld a,d
        cp 20
        jr nz,.f1
.o0:    ld hl,N0                ; outline: clear, next to an opaque pixel (the builds with no outline jump over it)
        ld b,20
.o1:    ld c,32
.o2:    ld a,(hl)
        or a
        jr nz,.o4
        ld de,1
        call .nb
        jr nz,.o3
        ld de,-1
        call .nb
        jr nz,.o3
        ld de,32
        call .nb
        jr nz,.o3
        ld de,-32
        call .nb
        jr z,.o4
.o3:    ld (hl),I_OUT
.o4:    inc hl
        dec c
        jr nz,.o2
        djnz .o1
        jr .out
; NZ = the pixel at HL + DE is opaque and no outline
.nb:    push hl
        add hl,de
        ld a,(hl)
        pop hl
        or a
        ret z
        cp I_OUT
        jr z,.nb0
        or a
        ret
.nb0:   xor a
        ret
.out:   call dtk
        call capi
        ld a,(V_E)              ; 4 tiles, 32 x 32
        add a,a
        ld bc,0x303B
        out (c),a
        xor a
        ld (V_TM),a
        ld e,0                  ; E = tile
.ot:    ld d,0                  ; D = line in the tile
.ol:    ld a,e
        and 2
        add a,a
        add a,a
        add a,a
        add a,d                 ; image line
        cp 20
        jr c,.oi
        ld b,8
        xor a
.oz:    call cap
        djnz .oz
        jr .on
.oi:    ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld a,e
        and 1
        jr z,.ox
        ld de,16
        add hl,de
.ox:    ld de,N0
        add hl,de
        pop de
        ld b,8
.oy:    ld a,(hl)
        inc hl
        swapnib
        ld c,a
        ld a,(hl)
        inc hl
        or c
        jr z,.ow
        push af
        push hl
        ld a,e
        and 3
        inc a
        ld h,a
        xor a
        scf
.om:    rla
        dec h
        jr nz,.om
        ld hl,V_TM
        or (hl)
        ld (hl),a
        pop hl
        pop af
.ow:    call cap
        djnz .oy
.on:    inc d
        ld a,d
        cp 16
        jr nz,.ol
        inc e
        ld a,e
        cp 4
        jr nz,.ot
        nextreg 0x56,GP6
        ld a,(V_E)
        call entry
        ld de,8
        add hl,de
        ld a,(V_TM)
        ld (hl),a
        jp uend

        INCLUDE "lib/hlib_pace.asm"

; the colour store, keyed by the graphics byte a pixel comes from -> A = nibble, 0 = the default. Keeps C.
colour: ld a,(V_X)
        ld hl,V_CS
        sub (hl)
        jp c,.none
        ld b,a                  ; B = pixel in the graphics line
        ld a,(V_CW)
        add a,a
        add a,a
        add a,a
        dec a
        cp b
        jp c,.none
        ld a,(V_CW)             ; address = base + line * W + B / 8
        ld e,a
        ld d,0
        ld a,(V_LN)
        ld hl,0
        or a
        jr z,.h1
.h0:    add hl,de
        dec a
        jr nz,.h0
.h1:    ld a,b
        rrca
        rrca
        rrca
        and 31
        ld e,a
        add hl,de
        ld de,(V_CB)
        add hl,de               ; HL = graphics address
        ld de,0xB700            ; region -> offset
        push hl
        or a
        sbc hl,de
        jr c,.r2
        ld a,h
        cp 0x09
        jr nc,.r2x
        ld de,0
        jr .off
.r2x:   pop hl
        jp .none
.r2:    pop hl
        push hl
        ld de,0xAD00
        or a
        sbc hl,de
        jr c,.r3
        ld de,9216
        jr .off
.r3:    pop hl
        push hl
        ld de,0x9500
        or a
        sbc hl,de
        jr c,.r2x
        ld a,h
        cp 0x04
        jr nc,.r2x
        ld de,19456
.off:   add hl,hl
        add hl,hl
        add hl,de               ; HL = offset of the byte's 4 nibble bytes
        pop de                  ; drop the address
        ld a,b
        and 7
        ld (V_TMP),a
        rrca
        and 3
        ld e,a
        ld d,0
        add hl,de
        ld a,h                  ; page
        rlca
        rlca
        rlca
        and 7
        add a,STORE
        nextreg 0x56,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld a,(V_TMP)
        and 1
        ld a,(hl)
        jr nz,.lo
        swapnib
.lo:    and 15
        ret
.none:  xor a
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, hide all, clip, sprites on
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,cols
        ld c,16
.b:     xor a
        nextreg 0x41,a          ; index 0 is transparent
        ld a,(hl)
        inc hl
        nextreg 0x41,a          ; index 1: this bank's paper colour
        push hl
        ld hl,fix
        ld b,10
.f:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .f
        ld a,c                  ; 12: XOR figures. C counts down from 16
        ld b,0xB4
        cp 16
        jr z,.x
        ld b,0xFF
        cp 15
        jr z,.x
        ld b,0
.x:     ld a,b
        nextreg 0x41,a
        pop hl
        xor a
        nextreg 0x41,a          ; 13: fill, black
        dec hl
        ld a,(hl)
        inc hl
        nextreg 0x41,a          ; 14: fill, this bank's paper
        ld a,0xFF
        nextreg 0x41,a          ; 15: outline, bright white
        dec c
        jr nz,.b
        nextreg 0x4B,0          ; index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2          ; sprite clip window = the play window
        nextreg 0x19,40
        nextreg 0x19,215
        nextreg 0x19,16
        nextreg 0x19,183
        nextreg 0x15,0x01       ; sprites on, SLU, higher number on top
        ret
cols:   DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
fix:    DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0
setup_end:

        SAVEBIN "ik_rom.bin",0x2400,rom_end-0x2400
        SAVEBIN "ik_setup.bin",0xD000,setup_end-0xD000
