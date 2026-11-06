; Three Weeks in Paradise (Mikro-Gen 1986, 128K release) - every figure of the five plotters becomes
; hardware sprites (4-bit) with a fixed colour; scenery, panel and text stay on the ULA.
; Facts: games/three_weeks.md.
;
; Render order (0x8DD4): 0xA90D attributes := clean, figures plotted into the back buffer 0x5B00-0x6AFF
; with save-under to a list at 0x7800, 0xA8ED blit (pixels by line table, attributes 0x7600 -> 0x5800),
; 0xB7D7 restores the save-under list. The game runs with DI from its start at 0x6C00, never in ROM.
; Banks at 0xC000: 0 figures, 3 Wally, 1 and 6 tiles, 4 text, 7 the picture; the commit pages what it reads.
; Method: the game's own code runs unchanged. The plotters only log; the blit first restores the
; save-under list without changing it (0xE17E then writes the same bytes again), and takes the
; attributes from the clean copy 0xF700. So nothing differs from the original but the screen.
;
; Page H = Next page 26 at slot 0 while a hook runs (ROM otherwise): variables, code, cache, hook stack.
; Stubs in the alt ROM's free area 0x386E-.

        DEVICE ZXSPECTRUMNEXT

HPG     EQU 26
GP3     EQU 11                  ; the game's page at slot 3
STORE   EQU 28                  ; colour store: pages 28-67, 8 bytes per address 0x6000-0xFFFF
MAXLOG  EQU 24
NSM     EQU 14                  ; small cache entries (four patterns each: 0-55)
NLG     EQU 12                  ; large entries (six patterns each: 56-127)
ESZ     EQU 12
CBLACK  EQU 8                   ; palette: 0 transparent, 1-7 inks, 8 black, 9-15 bright inks

; game variables
ROOM    EQU 27864
ROOMAT  EQU 42298
WX      EQU 27830
WY      EQU 27831
WFR     EQU 27841
BX      EQU 27839
BY      EQU 27840
SX      EQU 27906
SY      EQU 27907
SY2     EQU 27908
BASE    EQU 47723
WCOL    EQU 27866               ; 0 = Wally's own colour on (key 3)
WCOL2   EQU 27876               ; non-zero: the game does not paint him
UCNT    EQU 27858               ; save-under count
UPTR    EQU 35663               ; save-under list pointer
ITEMRET EQU 0xBB53              ; 0xE3FD's return address when an item is plotted
ITEMT   EQU 32832               ; item paint table, 4 bytes per frame
WALLY   EQU 49158
WEND    EQU WALLY+3456
NATDX   EQU 35669               ; the spear carrier's direction
SINK    EQU 27887               ; non-zero while 0x8F0E sinks him, frame 0 moving in bank 3
ORIENT  EQU 35634               ; Wally's facing: E0FE mirrors 18 frames in place
REVT    EQU 107                 ; the game's bit-reverse table, page
FILLMIN EQU MINOUT
OWHITE  EQU 15
MINOUT  EQU 24                  ; opaque pixels: fewer, no outline

; ---- page H ----
V_N     EQU 0x0000              ; plots logged
V_PREV  EQU 0x0001              ; sprites shown
V_SP    EQU 0x0002              ; (2)
V_FX    EQU 0x0004              ; non-zero: the attribute effect ran, the blit shows 0xF900
V_COL   EQU 0x0005              ; 1 = the colour store has entries (Python / recolour)
V_STAMP EQU 0x0006
V_RS    EQU 0x0007              ; round robin, small
V_RL    EQU 0x0008              ; round robin, large
V_DROP  EQU 0x0009              ; figures dropped (diagnostic)
V_NS    EQU 0x000A              ; sprites this commit
V_HL    EQU 0x000B              ; (2)
V_LP    EQU 0x000D              ; (2) log pointer
V_LI    EQU 0x000F
V_TCNT  EQU 0x0010
V_ROWS  EQU 0x0011
V_P     EQU 0x0012              ; pattern
V_X     EQU 0x0013
V_Y     EQU 0x0014
V_KEY   EQU 0x0015              ; 9 bytes: K, gfx (2), sum (2), inks (4)
V_K     EQU V_KEY
V_G     EQU V_KEY+1
V_SUM   EQU V_KEY+3
V_INK   EQU V_KEY+5
V_S     EQU 0x001E              ; bytes per row of the frame
V_CL    EQU 0x001F              ; columns of the frame (2, 3)
V_TOP   EQU 0x0020              ; (2) row pointer of the current tile
V_R     EQU 0x0022              ; row counter of the tile
V_C     EQU 0x0023              ; column in tile
V_RI    EQU 0x0025              ; rows done in the tile
V_PN    EQU 0x0026              ; 4 bytes: painted nibbles of the byte
V_CLR   EQU 0x002A              ; painted transparent mask of the byte
V_BM    EQU 0x002B              ; mask byte
V_BG    EQU 0x002C              ; graphics byte
V_BI    EQU 0x002D              ; ink nibble of the byte
V_PIX   EQU 0x002E              ; pixel counter
V_ACC   EQU 0x002F              ; pattern byte being built
V_BA    EQU 0x0030              ; (2) address of the graphics byte
V_E     EQU 0x0032              ; (2) cache entry
V_MIR   EQU 0x0140
V_ORI0  EQU 0x0141              ; (ORIENT) the colour map's facing, written by Python
V_M6    EQU 0x0142              ; the game's page at slot 6 at a commit
V_WAL   EQU 0x0143              ; 1: the figure is Wally, bank 3
V_BF    EQU 0x0144              ; fill byte
V_X1    EQU 0x0146              ; box column
V_PI    EQU 0x0147              ; pixel in the graphics byte
V_IP    EQU 0x0148              ; (2) image pointer
V_TP    EQU 0x014A              ; pattern
V_TY    EQU 0x014B
V_PK    EQU 0x014C              ; the left pixel of the pattern byte being made
V_NAT0  EQU 0x0145              ; (NATDX) of the colour map's facing, written by Python
V_FR    EQU 0x0034
V_KND   EQU 0x0035
V_FRONT EQU 0x0036              ; 1 while the room's front routine (table 59034) prints over the figures
V_FCP   EQU 0x0037              ; (2) front cell list pointer
V_GBD   EQU 0x003D              ; 1 once this room's go-behind cells are on Layer 2 (0 after h_l2clr)
GBT     EQU 0x1A00              ; go-behind: room * 2 -> item list (the lists at 0x1140-0x13FF) (0 = none); an item is runs col, row, rows, then 0xFE; 0xFF ends. Written by Python
NGBR    EQU 37                  ; rooms
V_GBN   EQU 0x014D              ; go-behind items drawn so far in this room (table order)
MEMO    EQU 0x1B80              ; h_ink's memo: 32 x 4 (gfx, ink, line)
ITF     EQU 0x1B00              ; MAXLOG: 1 if the plot is an item (a collectable): items go first, under every figure
V_PASS  EQU 0x0150              ; commit pass: 0 items, 1 the rest
V_L0    EQU 0x0160              ; (2) video line at the blit's start (the pace: the original blit's time is kept)
V_DEBT  EQU 0x0162              ; (2) hook time outside the blit since the last one, 1/16 lines (estimated per call)
V_NL    EQU 0x0164              ; (2) lines a video frame, learned at a wrap (0 = 311 until then)
V_LLN   EQU 0x0166              ; (2) the last line read
V_EL    EQU 0x0168              ; (2) lines since the blit's start, counted at each x_tick
V_PADON EQU 0x016A              ; 1: the blit started the pace window
TGT16   EQU 8592                ; x 16: the original blit, 0xA8ED to its RET, 538.6 lines (JNext, 128K timing, mean of 768), less the fixed
                                ; 3.5 MHz hook time outside it (0xA1E9, 0xA204, 0xB7D7: about 1.5 lines) and the window's lead-in
DPLOT   EQU 2                   ; a plot's 3.5 MHz part (NEXTREG 7 and the JP), not measured, 1/16 lines
V_HS    EQU 0x016C              ; (2) the line at the start of a hook outside the blit
DTILE   EQU 5                   ; a tile print's
V_NB    EQU 0x0151              ; parts of one figure abutting this plot: 1 right, 2 left, 4 below, 8 above (no outline there)
V_SOL   EQU 0x014F              ; 0x80: the go-behind cell being drawn is solid
V_NOGB  EQU 0x014E              ; 1 during the commit after a wipe: no go-behind work there (room change no slower)
GBCAP   EQU 16                  ; go-behind: a commit starts no new item once it has drawn this many cells (whole items always)
V_FI    EQU 0x0039              ; (2)
V_BRO   EQU 0x003B
V_LN    EQU 0x003C              ; palette line of the figure, shifted to bits 4-7
V_BO    EQU 0x003E              ; outline byte
V_OC    EQU 0x003F              ; outline colour, 0 = none
INK     EQU 0x0130              ; 16 RGB332 Spectrum colours, written by Python
BPG     EQU 27                  ; the build's page, the other half of bank 13, at slot 2 during a build only: the ULA reads page 10 whatever slot 2 holds
VIS     EQU 0x4000              ; 34 x 4 bytes, box coordinates: the figure's opaque pixels
OUTL    EQU 0x4100              ; its outline
FILLT   EQU 0x4200              ; clear pixels closed in by opaque ones: black
IMG     EQU 0x4300              ; 48 rows x 16 bytes: the box as 4-bit pixels
PAL     EQU 0x1C00              ; 16 x 16 RGB332: sprite palette lines, loaded at set-up
INKT    EQU 0x1D00              ; figure colours: the first is Wally's; lo (2), hi (2), ink nibble (0 = none), palette line << 4; lo = 0 ends
LOG     EQU 0x0040              ; MAXLOG x 10: K, gfx (2), x, y, inks (4), palette line << 4 + 1 if Wally
SHD     EQU 0x1400              ; 32 x 16 x 2: what Layer 2 shows per front cell (0 = nothing)
FCL     EQU 0x1800              ; front cells this game frame: col, row; 256 at most
L2PG    EQU 68                  ; Layer 2: banks 34-36
FCEND   EQU FCL+512
CACHE   EQU 0x1000              ; (NSM + NLG) x 12: K (0xFF = free), gfx (2), sum (2), inks (4), stamp, pattern, 0
HSTK    EQU 0x1F00

; ---- stubs: alt ROM, free area of the 48K ROM ----
        ORG 0x386E

        MACRO PLOTSTUB kind, back
        nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld b,kind
        call x_plot
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        nextreg 0x07,0
        push iy
        exx
        jp back
        ENDM

e_or16: PLOTSTUB 0, 0xB82F
e_m24:  PLOTSTUB 1, 0xB8B7
e_wal:  PLOTSTUB 2, 0xB8C5
e_or24: PLOTSTUB 3, 0xB9B3
e_m16:  PLOTSTUB 4, 0xBA62

; 0xB7D7: the save-under list is about to be consumed: plots not shown yet never will be
e_und:  nextreg 0x50,HPG
        ld (V_HL),hl
        ld hl,V_N
        ld (hl),0
        ld hl,FCL
        ld (V_FCP),hl
        ld hl,(V_HL)
        nextreg 0x50,0xFF
        ld a,(UCNT)
        jp 0xB7DA

; 0xA8ED: the blit. The registers it reads are none; it sets all it uses
; The pace: from here to the end of the attributes (e_at) the machine stays at 28 MHz, the game's own blit included,
; and e_at waits until the original's blit time has passed (less the hook time spent since the last blit): the game
; updates at the original's rate. Game memory and registers are as before; only time differs.
e_bl:   nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        call x_line
        ld (V_LLN),hl
        ld hl,0
        ld (V_EL),hl
        ld a,1
        ld (V_PADON),a
        call h_rest
        call h_com
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        ld (43267),sp
        jp 0xA8F1

; 0xA905: the blit's attributes: the clean copy, or the effect's 0x7600. Ends as the original's LDI chain does.
; The copy runs at 28 MHz (it replaces the game's 512 LDIs, which took about 2.3 ms at 3.5 MHz)
e_at:   nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        ld a,(V_FX)
        or a
        ld hl,0x7400
        jr z,.c
        ld h,0x76
.c:     xor a
        ld (V_FX),a
        pop af
        ld de,0x5800
        ld bc,512
        ldir
        push af
        push bc
        push de
        call x_pad
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        ld hl,0x7800
        nextreg 0x07,0
        ret

; hl = the video line (NR 0x1E/0x1F, read until the high bit holds still); a, f, bc used
x_line: ld bc,0x243B
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

; V_EL += the lines since the last reading. Callers are under a frame apart (a build ticks once a row), so at most one
; wrap is unseen: it counts V_NL lines (311 until a wait has seen one). Page H mapped; a, f, bc, hl used
x_tick: call x_line
        push de
        ld de,(V_LLN)
        ld (V_LLN),hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,(V_NL)
        ld a,d
        or e
        jr nz,.n
        ld de,311
.n:     add hl,de
.p:     ld de,(V_EL)
        add hl,de
        ld (V_EL),hl
        pop de
        ret

; a plot: its hook time measured by the video line (short hooks: 0 or 1 line, right on average) into V_DEBT
x_plot: push af
        push bc
        call x_line
        ld (V_HS),hl
        pop bc
        pop af
        call h_plot
        ld c,DPLOT
; V_DEBT += 16 x (lines since V_HS) + c
x_dbt:  push bc
        call x_line
        ld de,(V_HS)
        or a
        sbc hl,de
        jr nc,.p
        ld de,(V_NL)
        ld a,d
        or e
        jr nz,.n
        ld de,311
.n:     add hl,de
.p:     add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        pop bc
        ld b,0
        add hl,bc
        ld de,(V_DEBT)
        add hl,de
        ld (V_DEBT),hl
        ret

; V_DEBT += 16 x V_EL, after a last tick
x_eld:  call x_tick
        ld hl,(V_EL)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_DEBT)
        add hl,de
        ld (V_DEBT),hl
        ret

; wait until the window e_bl opened has lasted TGT16 - V_DEBT sixteenths of a line; what is left over (a long build,
; a room change) carries in V_DEBT to the next windows, at most 0xBFFF (3072 lines, 196 ms). Page H mapped
x_pad:  ld a,(V_PADON)
        or a
        ret z
        xor a
        ld (V_PADON),a
        call x_tick
        ld hl,TGT16
        ld de,(V_DEBT)
        or a
        sbc hl,de               ; target, sixteenths
        jr c,.neg
        push hl
        ld b,4
.q:     srl h
        rr l
        djnz .q
        ex de,hl                ; de = lines to reach
        ld hl,(V_EL)
.lp:    push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.ok
        push hl
        call x_line
        ld bc,(V_LLN)
        ld (V_LLN),hl
        or a
        sbc hl,bc               ; lines since the last poll
        jr nc,.d
        inc bc                  ; a wrap: the last poll saw the frame's last line
        ld (V_NL),bc
        add hl,bc               ; = the new line + 1
.d:     pop bc
        add hl,bc
        jr .lp
.ok:    ld (V_EL),hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        pop de
        or a
        sbc hl,de               ; past the target (under a line), sixteenths
        jr nc,.st
        ld hl,0
        jr .st
.neg:   ld hl,(V_DEBT)          ; no wait: the debt beyond this window, and all of the window's time
        ld de,TGT16
        or a
        sbc hl,de
        ex de,hl
        ld hl,(V_EL)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
.st:    ld a,h
        cp 0xC0
        jr c,.w
        ld hl,0xBFFF
.w:     ld (V_DEBT),hl
        ret

; 0xA89C: the room wipe shows the buffer: without figures; the old room's sprites go
e_wp:   nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call x_line             ; the room change's hook time, counted by x_tick (a build can take frames)
        ld (V_LLN),hl
        ld hl,0
        ld (V_EL),hl
        call h_rest
        xor a
        ld (V_NS),a
        call h_hide
        call h_l2clr
        call x_eld              ; repaid by the next blits' windows
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        nextreg 0x07,0
        ld a,(ROOM)
        jp 0xA89F

; 0xA9B8: JP 0xB7D7 after the wipe: the new room's figures
e_aw:   nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call x_line             ; the room change's hook time, counted by x_tick (a build can take frames)
        ld (V_LLN),hl
        ld hl,0
        ld (V_EL),hl
        ld hl,V_NOGB
        ld (hl),1
        call h_com
        xor a
        ld (V_NOGB),a
        call x_eld              ; repaid by the next blits' windows
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        nextreg 0x07,0
        jp 0xB7D7

; 0x6F09: clear screen (menu, messages): no sprites. Interrupts may be on: page H is not used
e_cls:  nextreg 0x69,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        xor a
        out (254),a
        jp 0x6F0C

; 0xA3F1: room 21 dark, the effect that repaints the attribute buffer: the next blit shows it
e_fx:   nextreg 0x50,HPG
        ld hl,V_FX
        ld (hl),1
        nextreg 0x50,0xFF
        ld hl,0x7600
        jp 0xA3F4
; 0xA1E9 / 0xA204: around the room's front routine: tiles printed now cover the figures
e_fon:  nextreg 0x50,HPG
        ld (V_HL),hl
        ld hl,V_FRONT
        ld (hl),1
        ld hl,(V_HL)
        nextreg 0x50,0xFF
        ld hl,0xB787
        jp 0xA1EC
e_fof:  nextreg 0x50,HPG
        ld (V_HL),hl
        ld hl,V_FRONT
        ld (hl),0
        ld hl,(V_HL)
        nextreg 0x50,0xFF
        ld hl,0x71DF
        jp 0xA207

; 0xB78E: the tile printer into the buffer: d = row, e = column; in the front routine, note the cell
e_tile: nextreg 0x07,3
        nextreg 0x50,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push hl
        ld hl,(V_DEBT)
        ld a,l
        add a,DTILE
        ld l,a
        jr nc,$+3
        inc h
        ld (V_DEBT),hl
        ld a,(V_FRONT)
        or a
        jr z,.x
        ld hl,(V_FCP)
        ld a,h
        cp FCEND >> 8
        jr nc,.x
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (V_FCP),hl
.x:     pop hl
        pop af
        ld sp,(V_SP)
        nextreg 0x50,0xFF
        nextreg 0x07,0
        push af
        push hl
        push bc
        jp 0xB791
rom_end:

; ---- page H code ----
        ORG 0x0200
h_start:

; b = kind, a = frame
h_plot: ld c,a
        ld (V_FR),a
        ld a,b
        ld (V_KND),a
        ld a,(V_N)
        cp MAXLOG
        jr c,.ok
        ld hl,V_DROP
        inc (hl)
        ret
.ok:    ld l,a
        ld h,0
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        ld de,LOG
        add hl,de
        ex de,hl                ; de = entry
        ld a,b
        or a
        jp z,.or16
        dec a
        jp z,.m24
        dec a
        jp z,.wal
        dec a
        jp z,.or24
; masked 16 x 16: frame * 64
        ld h,c
        ld l,0
        srl h
        rr l
        srl h
        rr l
        ld a,1
        jr .s16
; OR 16 x 16: frame * 32. y is a word in this plotter
.or16:  ld a,(SY2)
        or a
        ret nz                  ; never on the screen
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        xor a
.s16:   ld bc,(BASE)
        add hl,bc
        ld c,a                  ; K
        ld a,(SX)
        ld b,a
        ld a,(SY)
        ld (V_Y),a
        ld a,b
        ld (V_X),a
        jr .put
; masked 24 x 32, frame from the caller: frame * 192
.m24:   call .x192
        ld bc,(BASE)
        add hl,bc
        ld c,3
        jr .bpos
; OR 24 x 32: frame * 96
.or24:  call .x192
        srl h
        rr l
        ld bc,(BASE)
        add hl,bc
        ld c,2
.bpos:  ld a,(BX)
        ld (V_X),a
        ld a,(BY)
        ld (V_Y),a
        jr .put
; Wally
.wal:   ld a,(WFR)
        ld c,a
        call .x192
        ld bc,WALLY
        add hl,bc
        ld c,3
        ld a,(WX)
        ld (V_X),a
        ld a,(WY)
        ld (V_Y),a
.put:   ex de,hl                ; hl = entry, de = gfx, c = K
        ld (V_E),de
        ld (hl),c
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_X)
        ld (hl),a
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ex de,hl                ; de -> inks
        ld hl,(V_E)             ; gfx, kept below
        call h_ink              ; a = the figure's ink nibble, V_LN
        ld c,a
        ld b,4
.i:     ld a,c
        ld (de),a
        inc de
        djnz .i
        ld a,(V_KND)
        cp 2
        ld a,(V_LN)
        jr nz,.nw
        inc a
.nw:    ld (de),a               ; entry +9
        dec de
        dec de
        dec de
        dec de
        ld hl,V_N
        inc (hl)
        ld a,(hl)
        dec a
        ld l,a
        ld h,ITF >> 8
        ld (hl),0               ; not an item (set below if it is)
        ld a,(V_KND)
        cp 2
        jr z,.w
        cp 4
        ret nz
        ; an item (0xE3FD called from 0xE4EE): the game's paint table, 4 cells; 255 = the room's colour
        ld hl,(V_SP)
        ld a,(hl)
        cp ITEMRET & 255
        ret nz
        inc hl
        ld a,(hl)
        cp ITEMRET >> 8
        ret nz
        ld a,(V_FR)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,ITEMT
        add hl,bc
        ld b,4
.t:     ld a,(hl)
        inc hl
        cp 255
        jr z,.ts
        call h_nib
        ld (de),a
.ts:    inc de
        djnz .t
        ld a,(V_N)
        dec a
        ld l,a
        ld h,ITF >> 8
        ld (hl),1
        ret
; Wally: his table colour; key 3 takes it away: the room's ink. (WCOL2, the door of the hut, the game stops painting him: he stays his colour)
.w:     ld a,(WCOL)
        or a
        ret z
        call h_room
        ld b,4
.wl:    ld (de),a
        inc de
        djnz .wl
        ret

; hl := c * 192 (c * 128 + c * 64)
.x192:  ld h,c
        ld l,0
        srl h
        rr l
        ld b,h
        ld a,l
        srl h
        rr l
        add a,l
        ld l,a
        ld a,b
        adc a,h
        ld h,a
        ret

; hl = graphics address -> a = the figure's fixed ink (INKT), or the room's; V_LN its palette line
h_ink:  push de
        ld a,(V_KND)
        cp 2
        jr nz,.fi
        ld a,(INKT+5)           ; Wally: the table's first entry
        ld (V_LN),a
        ld a,(INKT+4)
        pop de
        ret
.fi:    ex de,hl                ; de = graphics
; memo, 32 entries by (gfx >> 5) & 31: gfx (2), ink, line. INKT does not change while the game runs; gfx 0 never matches
        ld a,e
        and 0xE0
        ld l,a
        ld a,d
        and 3
        or l
        rlca
        rlca
        rlca
        add a,a
        add a,a
        add a,MEMO & 255
        ld l,a
        ld h,MEMO >> 8
        ld a,(hl)
        cp e
        jr nz,.miss
        inc hl
        ld a,(hl)
        cp d
        jr nz,.miss1
        inc hl
        ld b,(hl)
        inc hl
        ld c,(hl)
        jr .got
.miss1: dec hl
.miss:  push hl
        call .scan
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),b
        inc hl
        ld (hl),c
.got:   ld a,c
        ld (V_LN),a
        ld a,b
        pop de
        or a
        ret nz
        jr h_room
; the table: b = ink nibble (0 = none), c = palette line << 4; both 0 when no entry holds gfx
.scan:  ld hl,INKT+6
.l:     ld a,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,a
        or c
        jr z,.nf
        ld a,e                  ; g - lo
        sub b
        ld a,d
        sbc a,c
        jr c,.nx
        ld a,e                  ; g - hi
        cp (hl)
        inc hl
        ld a,d
        sbc a,(hl)
        inc hl
        jr nc,.nx2
        ld b,(hl)               ; in range
        inc hl
        ld c,(hl)
        ret
.nx:    inc hl
        inc hl
.nx2:   inc hl
        inc hl
        jr .l
.nf:    ld bc,0
        ret
h_room: push hl
        push de
        ld a,(ROOM)
        ld e,a
        ld d,0
        ld hl,ROOMAT
        add hl,de
        ld a,(hl)
        pop de
        pop hl
; attribute -> ink nibble
h_nib:  ld c,a
        and 7
        jr nz,.n
        ld a,CBLACK
        ret
.n:     bit 6,c
        ret z
        add a,8
        ret

; ---- the save-under list written back, the list left as it is ----
h_rest: ld a,(UCNT)
        or a
        ret z
        push ix
        ld b,a
        ld hl,(UPTR)
        dec hl
.l:     ld a,(hl)
        dec hl
        ld d,(hl)
        dec hl
        ld e,(hl)
        dec hl
        push bc
        ex de,hl                ; hl = buffer, de = saved bytes
        or a
        jr z,.nar
        ld ixh,32               ; the rows, as 0xB7D7 walks them: 4 bytes a row
        ld bc,65500
.w:     DUP 4
        ld a,(de)
        ld (hl),a
        dec de
        inc hl
        EDUP
        add hl,bc
        dec ixh
        jr nz,.w
        jr .e
.nar:   ld ixh,16               ; 3 bytes a row
        ld bc,65501
.n:     DUP 3
        ld a,(de)
        ld (hl),a
        dec de
        inc hl
        EDUP
        add hl,bc
        dec ixh
        jr nz,.n
.e:     ex de,hl
        pop bc
        djnz .l
        pop ix
        ret

; ---- Layer 2 over the sprites: the cells of the room's front routine ----
h_front:
        nextreg 0x69,0x80
        ld a,(V_GBD)
        ld hl,V_NOGB
        or (hl)
        call z,h_gb
        ld hl,FCL
        ld (V_FI),hl
.l:     ld hl,(V_FI)
        ld de,(V_FCP)
        or a
        sbc hl,de
        jp nc,.end
        add hl,de
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld (V_FI),hl
        ld a,b
        cp 16
        jr nc,.l
        ld a,c
        cp 32
        jr nc,.l
        ; hash: 8 pixel lines, the attribute
        ld a,b
        add a,0x5B
        ld e,c
        ld d,a                  ; buffer of the cell (row * 256 + column)
        ld hl,0
        DUP 8                   ; the same hash as h_find's, 8 pixel lines 32 bytes apart
        add hl,hl
        ld a,(de)
        adc a,l
        ld l,a
        jr nc,$+3
        inc h
        ld a,e
        add a,32
        ld e,a
        EDUP
        ex de,hl
        push bc
        call .att               ; a = attribute
        pop bc
        add a,e
        ld e,a
        jr nc,.h2
        inc d
.h2:    set 0,e                 ; never 0
        ; shadow
        push de
        ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld e,c
        ld d,0
        add hl,de
        add hl,hl
        ld de,SHD
        add hl,de
        pop de
        ld a,(hl)
        cp e
        jr nz,.w
        inc hl
        ld a,(hl)
        cp d
        jp z,.l
        dec hl
.w:     ld (hl),e
        inc hl
        ld (hl),d
        call h_cell
        jp .l
.end:   ld hl,FCL
        ld (V_FCP),hl
        ret
.att:   ld l,b                  ; attribute of the cell, clean copy
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,0
        add hl,bc
        ld bc,0x7400
        add hl,bc
        ld a,(hl)
        ret

; b = row, c = column: the cell's pixels to Layer 2
h_cell: push bc
        ld a,b
        rrca
        rrca
        and 0x3F
        add a,L2PG
        nextreg 0x54,a
        ld a,b
        and 3
        add a,a
        add a,a
        add a,a
        add a,0x80
        ld d,a                  ; Layer 2 line
        ld a,c
        add a,a
        add a,a
        add a,a
        ld e,a                  ; x
        push de
        call h_front.att
        pop de
        pop bc
        push bc
        push de
        ld e,a
        and 7
        bit 6,e
        jr z,.nb
        add a,8
.nb:    ld hl,INK
        ld d,0
        push de
        ld e,a
        add hl,de
        pop de
        ld a,(hl)
        or a
        jr nz,$+4
        ld a,0xE3               ; black: transparent, the figures show through
        ld (V_ACC),a            ; ink
        ld a,e
        rrca
        rrca
        rrca
        and 7
        bit 6,e
        jr z,.nb2
        add a,8
.nb2:   ld hl,INK
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        or a
        jr nz,$+4
        ld a,0xE3               ; black paper: transparent
        ld (V_BI),a             ; paper
        pop de
        pop bc
        ld a,b
        add a,0x5B
        ld h,a
        ld l,c                  ; buffer
        ld a,8
        ld (V_BRO),a
.ln:    ld a,(hl)
        ld c,a
        ld b,8
        push de
.px:    sla c
        ld a,(V_BI)
        jr nc,.pp
        ld a,(V_ACC)
.pp:    ld (de),a
        inc e
        djnz .px
        pop de
        inc d
        ld a,l
        add a,32
        ld l,a
        ld a,(V_BRO)
        dec a
        ld (V_BRO),a
        jr nz,.ln
        nextreg 0x54,4
        ret

; ---- go-behind scenery: the room's chosen cells on Layer 2, scenery pixels only, once per room ----
h_gb:   ld a,1
        ld (V_GBD),a            ; set again below if items remain
        ld a,(ROOM)
        cp NGBR
        ret nc
        add a,a
        ld l,a
        ld h,GBT >> 8
        ld a,l
        add a,GBT & 255
        ld l,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        or h
        ret z
        ld a,(V_GBN)
        ld e,a                  ; items to skip (drawn by earlier commits)
        ld d,GBCAP              ; cells this commit: a new item starts only while some are left
.obj:   ld a,(hl)
        cp 0xFF
        ret z
        ld a,e
        or a
        jr z,.dob
        dec e
.sk:    ld a,(hl)
        cp 0xFE
        jr z,.sk2
        inc hl
        inc hl
        inc hl
        jr .sk
.sk2:   inc hl
        jr .obj
.dob:   ld a,d
        or a
        jr z,.more
.run:   ld a,(hl)               ; col, row, rows; 0xFE ends the item
        cp 0xFE
        jr z,.oend
        ld c,a
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        inc hl
        push hl
.cell:  push af
        push de
        push bc
        call h_gcell
        pop bc
        pop de
        ld a,d
        or a
        jr z,.c1
        dec d
.c1:    pop af
        inc b
        dec a
        jr nz,.cell
        pop hl
        jr .run
.oend:  inc hl
        push hl
        ld hl,V_GBN
        inc (hl)
        pop hl
        jr .obj
.more:  xor a                   ; the budget is spent with items left: next commit
        ld (V_GBD),a
        ret

; b = row, c = column: the cell's scenery pixels to Layer 2 in its ink, the rest transparent; shadow marked (0, 1)
h_gcell:
        ld a,c                  ; bit 7 of the column: a solid cell (the item's colour is the paper too), else ink only
        and 0x80
        ld (V_SOL),a
        res 7,c
        ld l,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld e,c
        ld d,0
        add hl,de
        add hl,hl
        ld de,SHD
        add hl,de
        ld (hl),0               ; a front hash always has bit 0 set: never equal
        inc hl
        ld (hl),1
        push bc
        call h_front.att
        ld c,a                  ; attribute
        ld a,0xE3               ; clear pixels: transparent, or the paper on a solid cell
        ld (V_BI),a
        ld a,(V_SOL)
        or a
        jr z,.ink
        ld a,c
        rrca
        rrca
        rrca
        and 7
        bit 6,c
        jr z,.pb
        add a,8
.pb:    add a,INK & 255
        ld l,a
        ld h,INK >> 8
        ld a,(hl)
        or a
        jr nz,.pk
        ld a,0xE3               ; black paper: transparent
.pk:    ld (V_BI),a
.ink:   ld a,c
        and 7
        bit 6,c
        jr z,.nb
        add a,8
.nb:    add a,INK & 255
        ld l,a
        ld h,INK >> 8
        ld a,(hl)
        or a
        jr nz,.ik
        ld a,0xE3               ; black ink: transparent (the figure shows through every black pixel)
.ik:    ld l,a
        ld a,(V_BI)
        xor l
        ld (V_ACC),a            ; ink ^ clear colour
        pop bc
        ld a,b
        rrca
        rrca
        and 0x3F
        add a,L2PG
        nextreg 0x54,a
        ld a,b
        and 3
        add a,a
        add a,a
        add a,a
        add a,0x80
        ld d,a                  ; Layer 2 line
        ld a,c
        add a,a
        add a,a
        add a,a
        ld e,a                  ; x
        ld a,b
        add a,0x5B
        ld h,a
        ld l,c                  ; buffer
        push ix
        ld a,(V_BI)
        ld ixl,a
        ld a,(V_ACC)
        ld b,a
        ld a,8
        ld (V_BRO),a
.ln:    ld c,(hl)
        DUP 8
        sla c
        sbc a,a
        and b
        xor ixl
        ld (de),a
        inc e
        EDUP
        ld a,e
        sub 8
        ld e,a
        inc d
        ld a,l
        add a,32
        ld l,a
        ld a,(V_BRO)
        dec a
        ld (V_BRO),a
        jr nz,.ln
        pop ix
        nextreg 0x54,4
        ret

; nothing on Layer 2: every cell that shows something back to transparent
h_l2clr:
        nextreg 0x69,0
        xor a
        ld (V_GBD),a
        ld (V_GBN),a
        ld hl,SHD
        ld bc,0                 ; b = row, c = column
.l:     ld a,(hl)
        ld (hl),0
        inc hl
        or (hl)
        ld (hl),0
        inc hl
        jr z,.n
        push hl
        push bc
        ld a,b
        rrca
        rrca
        and 0x3F
        add a,L2PG
        nextreg 0x54,a
        ld a,b
        and 3
        add a,a
        add a,a
        add a,a
        add a,0x80
        ld h,a
        ld a,c
        add a,a
        add a,a
        add a,a
        ld l,a
        ld bc,0x08E3            ; 8 lines; c = transparent
.r:     DUP 7
        ld (hl),c
        inc l
        EDUP
        ld (hl),c
        ld a,l
        sub 7
        ld l,a
        inc h
        djnz .r
        nextreg 0x54,4
        pop bc
        pop hl
.n:     inc c
        ld a,c
        cp 32
        jr nz,.l
        ld c,0
        inc b
        ld a,b
        cp 16
        jr nz,.l
        ret

; ---- commit: sprites from the log, in plot order ----
h_com:  ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (V_M6),a
        ld hl,V_STAMP
        inc (hl)
        xor a
        ld (V_NS),a
        ld (V_PASS),a
.pass:  xor a
        ld (V_LI),a
        ld hl,LOG
        ld (V_LP),hl
.next:  ld a,(V_N)
        ld b,a
        ld a,(V_LI)
        cp b
        jr nc,.pend
        ld l,a                  ; items in pass 0, the rest in pass 1: collectables never cover a figure
        ld h,ITF >> 8
        ld a,(V_PASS)
        xor (hl)
        jr z,.skip
        ld hl,(V_LP)
        ld de,V_KEY
        ld a,(hl)
        ld (de),a               ; K
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a               ; gfx
        inc hl
        ld a,(hl)
        ld (V_X),a
        inc hl
        ld a,(hl)
        ld (V_Y),a
        inc hl
        ld de,V_INK
        ld bc,4
        ldir
        ld a,(hl)
        ld c,a
        and 0xF0
        ld (V_LN),a
        ld a,c
        and 1
        ld (V_WAL),a
        ld a,(V_Y)
        cp 128
        jr nc,.skip             ; off the buffer: nothing shown
        ld a,(V_WAL)            ; the figure's bank at 0xC000
        or a
        jr z,.b0
        nextreg 0x56,6
        nextreg 0x57,7
        jr .b1
.b0:    nextreg 0x56,0
        nextreg 0x57,1
.b1:    call h_nb
        call h_find
        jr nc,.skip
        call h_emit
.skip:  call x_tick
        ld hl,(V_LP)
        ld de,10
        add hl,de
        ld (V_LP),hl
        ld hl,V_LI
        inc (hl)
        jr .next
.pend:  ld a,(V_PASS)
        or a
        jr nz,.done
        inc a
        ld (V_PASS),a
        jp .pass
.done:  ld a,(V_M6)
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        xor a
        ld (V_N),a
        call h_front
; hide what the last commit showed beyond this one
h_hide: ld a,(V_NS)
        ld b,a
        ld a,(V_PREV)
        ld c,a
        ld a,b
        ld (V_PREV),a
.h:     ld a,b
        cp c
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc b
        jr .h

; sprites of the current figure: V_P pattern(s), V_X, V_Y
h_emit: ld a,(V_K)              ; 2 x 2 tiles, or 2 x 3: the box starts a pixel left of and above the graphic
        and 2
        ld a,2
        jr z,.n
        ld a,3
.n:     ld (V_TCNT),a
        ld a,(V_P)
        ld b,a
        ld a,(V_Y)
        ld e,a
.r:     ld a,(V_X)
        ld d,a
        ld c,0
        call h_spr
        inc b
        ld a,d
        add a,16
        ld d,a
        rl c
        call h_spr
        inc b
        ld a,e
        add a,16
        ld e,a
        ld hl,V_TCNT
        dec (hl)
        jr nz,.r
        ret

; b = pattern, d = x low, c = x high (0, 1), e = y
h_spr:  ld a,(V_NS)
        cp 128
        jr c,.ok
        ld hl,V_DROP
        inc (hl)
        ret
.ok:    nextreg 0x34,a
        inc a
        ld (V_NS),a
        ld a,d
        add a,31
        nextreg 0x35,a
        ld a,c
        adc a,0
        and 1
        ld hl,V_LN
        or (hl)
        nextreg 0x37,a
        ld a,e
        add a,31
        nextreg 0x36,a
        ld a,b
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; key = K, gfx, sum, inks. Out: V_P, carry = found or built; no carry = no free entry
h_find: ld a,(V_K)
        add a,.cnt & 255
        ld l,a
        ld a,.cnt >> 8
        adc a,0
        ld h,a
        ld b,(hl)               ; frame length / 8
        ld de,(V_G)
        ld hl,0
; rotate left, then add: order and bit position count (a turned frame can have the same byte sum).
; The same sum as before (DE rotated left a bit, the byte added to the low half, its carry to the high), 8 bytes a pass:
; ADD HL,HL puts bit 15 in carry, ADC A,L brings it in at bit 0 with the byte (bit 0 is clear, so no carry from it)
.s:     DUP 8
        add hl,hl
        ld a,(de)
        adc a,l
        ld l,a
        jr nc,$+3
        inc h
        inc de
        EDUP
        djnz .s
        ex de,hl
        ld a,(V_NB)             ; a part of a two-part figure has its own pattern (outline cut where they meet)
        rrca
        rrca
        rrca
        xor d
        ld d,a
        ld (V_SUM),de
        ld a,(V_K)
        and 2
        ld hl,CACHE
        ld b,NSM
        jr z,.f
        ld hl,CACHE+NSM*ESZ
        ld b,NLG
.f:     push hl
        push bc
        ld de,V_KEY
        ld b,9
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc hl
        djnz .cmp
        ; found
        ld a,(V_STAMP)
        ld (hl),a
        inc hl
        ld a,(hl)
        ld (V_P),a
        pop bc
        pop hl
        scf
        ret
.no:    pop bc
        pop hl
        ld de,ESZ
        add hl,de
        djnz .f
; a miss: the next entry not on show this commit
        ld a,(V_K)
        and 2
        jr nz,.el
        ld hl,CACHE
        ld de,V_RS
        ld c,NSM
        jr .ev
.el:    ld hl,CACHE+NSM*ESZ
        ld de,V_RL
        ld c,NLG
.ev:    ld (V_E),hl
        ld b,c                  ; tries
.try:   ld a,(de)
        inc a
        cp c
        jr c,.tr1
        xor a
.tr1:   ld (de),a
        push de
        push bc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de               ; * 12
        ld de,(V_E)
        add hl,de
        pop bc
        pop de
        push hl
        push de
        ld de,9
        add hl,de
        ld a,(V_STAMP)
        cp (hl)
        pop de
        pop hl
        jr nz,.got
        djnz .try
        ld hl,V_DROP
        inc (hl)
        or a
        ret
.got:   ex de,hl                ; de = entry
        ld hl,V_KEY
        ld bc,9
        ldir                    ; key
        ex de,hl
        ld a,(V_STAMP)
        ld (hl),a
        inc hl
        ld a,(hl)
        ld (V_P),a
        call h_build
        scf
        ret
.cnt:   DB 4, 8, 12, 24

; ---- patterns of the current figure from the game's bytes ----
h_build:
        nextreg 0x52,BPG
        call x_tick
        ld a,(V_K)
        ld c,2                  ; columns
        ld b,2                  ; bytes per row
        cp 0
        jr z,.g
        ld b,4
        cp 1
        jr z,.g
        ld c,3
        ld b,3
        cp 2
        jr z,.g
        ld b,6
.g:     ld a,c
        ld (V_CL),a
        ld a,b
        ld (V_S),a
        ld hl,(V_G)
        ld (V_TOP),hl
        call h_outl
        call x_tick
        call h_img
        call x_tick
        call h_upl
        nextreg 0x52,10
        ret

; VIS, OUTL, FILLT of the current figure in box coordinates, a margin of one pixel on all four sides;
; V_OC: white, black on a white figure, none on a small one
h_outl: ld hl,VIS
        ld de,VIS+1
        ld bc,0x5FF
        ld (hl),0
        ldir
        ld a,(V_K)
        and 2
        ld a,16
        jr z,.r0
        ld a,32
.r0:    ld (V_RI),a             ; rows to read
        add a,2
        ld (V_ROWS),a
        ld hl,(V_G)
        ld (V_BA),hl
        ld hl,VIS+4
        ld (V_FI),hl
        xor a
        ld (V_BRO),a            ; opaque pixels, saturates at 255
.row:   ld a,(V_CL)
        ld b,a
        ld hl,(V_BA)
        ld de,(V_FI)
        xor a
        ld (V_ACC),a            ; the byte before
.col:   ld a,(V_K)
        rra
        jr c,.m
        ld a,(hl)
        jr .st
.m:     push de
        push hl
        ld a,(V_CL)
        ld e,a
        ld d,0
        add hl,de               ; the graphics byte
        ld c,(hl)
        pop hl
        pop de
        ld a,(hl)
        cpl
        or c
.st:    ld c,a                  ; opaque, one pixel right: the bit from the byte before comes in
        ld a,(V_ACC)
        rra
        ld a,c
        rra
        ld (de),a
        ld a,c
        ld (V_ACC),a
.cn:    ld a,c
        or a
        jr z,.cd
        dec a
        and c
        ld c,a
        ld a,(V_BRO)
        inc a
        jr z,.cn
        ld (V_BRO),a
        jr .cn
.cd:    inc hl
        inc de
        djnz .col
        ld a,(V_ACC)            ; the last byte's last pixel
        rra
        ld a,0
        rra
        ld (de),a
        ld hl,(V_BA)
        ld a,(V_S)
        ld e,a
        ld d,0
        add hl,de
        ld (V_BA),hl
        ld hl,(V_FI)
        ld de,4
        add hl,de
        ld (V_FI),hl
        ld hl,V_RI
        dec (hl)
        jr nz,.row
; the colour
        xor a
        ld (V_OC),a
        ld a,(V_BRO)
        cp MINOUT
        ret c
        call h_fill
        ld a,(V_INK)
        and 7
        cp 7
        ld a,OWHITE
        jr nz,.oc
        ld a,CBLACK
.oc:    ld (V_OC),a
; the ring: a clear pixel 4-next to an opaque one
        ld hl,VIS
        ld de,OUTL
        ld a,(V_ROWS)
        ld (V_RI),a
.rr:    xor a
        ld (V_ACC),a            ; bit 0 of the column to the left, as bit 7
        ld a,4
        ld (V_PIX),a
.cc:    ld b,(hl)
        ld a,b
        srl a
        ld c,a
        ld a,(V_ACC)
        or c
        ld c,a
        ld a,b
        add a,a
        or c
        ld c,a
        ld a,(V_PIX)
        cp 1
        jr z,.nn
        inc hl
        ld a,(hl)
        dec hl
        rlca
        and 1
        or c
        ld c,a
.nn:    ld a,(V_ROWS)
        push hl
        ld hl,V_RI
        cp (hl)
        pop hl
        jr z,.nu                ; first row
        push de
        ld de,-4
        add hl,de
        ld a,(hl)
        or c
        ld c,a
        ld de,4
        add hl,de
        pop de
.nu:    ld a,(V_RI)
        cp 1
        jr z,.nd                ; last row
        push de
        ld de,4
        add hl,de
        ld a,(hl)
        or c
        ld c,a
        ld de,-4
        add hl,de
        pop de
.nd:    ld a,b
        cpl
        and c
        ld (de),a
        ld a,b
        rrca
        and 0x80
        ld (V_ACC),a
        inc hl
        inc de
        ld a,(V_PIX)
        dec a
        ld (V_PIX),a
        jr nz,.cc
        ld a,(V_RI)
        dec a
        ld (V_RI),a
        jp nz,.rr
; a two-part figure (a bat is two 16 x 16 halves, frames one after the other, side by side): no outline where they meet
h_nbcut:
        ld a,(V_NB)
        or a
        ret z
        ld b,a
        ld hl,OUTL
        bit 0,b                 ; a part to the right: no ring in the column right of the graphic
        jr z,.n1
        push hl
        ld c,18
.r1:    inc hl
        inc hl
        res 6,(hl)
        inc hl
        inc hl
        dec c
        jr nz,.r1
        pop hl
.n1:    bit 1,b                 ; to the left
        jr z,.n2
        push hl
        ld c,18
.r2:    res 7,(hl)
        inc hl
        inc hl
        inc hl
        inc hl
        dec c
        jr nz,.r2
        pop hl
.n2:    bit 2,b                 ; below
        jr z,.n3
        push hl
        ld de,17*4
        add hl,de
        xor a
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        pop hl
.n3:    bit 3,b                 ; above
        ret z
        xor a
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ret

; parts of one figure: 16 x 16 plots of the same kind, frames one after the other, abutting exactly -> V_NB
h_nb:   xor a
        ld (V_NB),a
        ld a,(V_K)
        cp 2
        ret nc
        ld hl,LOG
        ld a,(V_N)
        or a
        ret z
        ld b,a
.l:     push bc
        push hl
        ld a,(V_K)
        cp (hl)
        jr nz,.n
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; this entry's graphics
        inc hl
        push hl
        ld hl,(V_G)
        ex de,hl
        or a
        sbc hl,de               ; its graphics - ours
        ld a,(V_K)
        or a
        ld c,32
        jr z,.k0
        ld c,64
.k0:    ld a,h
        or a
        jr nz,.neg
        ld a,l
        cp c
        jr nz,.nx
        jr .ok
.neg:   inc a
        jr nz,.nx
        ld a,l
        neg
        cp c
        jr nz,.nx
.ok:    pop hl
        ld a,(V_X)
        ld e,a
        ld a,(hl)
        sub e
        ld d,a                  ; dx
        inc hl
        ld a,(V_Y)
        ld e,a
        ld a,(hl)
        sub e                   ; dy
        or a
        jr nz,.vt
        ld a,d
        cp 16
        ld c,1
        jr z,.set
        cp 240
        ld c,2
        jr z,.set
        jr .n
.vt:    ld e,a
        ld a,d
        or a
        jr nz,.n
        ld a,e
        cp 16
        ld c,4
        jr z,.set
        cp 240
        ld c,8
        jr nz,.n
.set:   ld hl,V_NB
        ld a,(hl)
        or c
        ld (hl),a
        jr .n
.nx:    pop hl
.n:     pop hl
        ld de,10
        add hl,de
        pop bc
        djnz .l
        ret

; FILLT: clear pixels with an opaque one on all four sides, in line; VIS then counts them as opaque
h_fill: push ix
        push iy
        ld hl,VIS               ; above: the OR of the rows before
        ld de,FILLT
        ld bc,0                 ; c, b, and the two on the stack: running columns
        push bc
        push bc
        pop ix
        pop iy
        ld a,(V_ROWS)
.a:     push af
        ld a,c
        ld (de),a
        or (hl)
        ld c,a
        inc hl
        inc de
        ld a,b
        ld (de),a
        or (hl)
        ld b,a
        inc hl
        inc de
        ld a,ixl
        ld (de),a
        or (hl)
        ld ixl,a
        inc hl
        inc de
        ld a,iyl
        ld (de),a
        or (hl)
        ld iyl,a
        inc hl
        inc de
        pop af
        dec a
        jr nz,.a
        ld a,(V_ROWS)           ; below: AND with the OR of the rows after, from the last row back
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        dec hl                  ; last byte of the last row, as an offset
        ld de,VIS
        add hl,de
        ex de,hl                ; de -> VIS
        ld hl,FILLT-VIS
        add hl,de               ; hl -> FILLT
        ld bc,0
        ld ix,0
        ld iy,0
        ld a,(V_ROWS)
.b:     push af
        ld a,iyl
        and (hl)
        ld (hl),a
        ld a,(de)
        or iyl
        ld iyl,a
        dec hl
        dec de
        ld a,ixl
        and (hl)
        ld (hl),a
        ld a,(de)
        or ixl
        ld ixl,a
        dec hl
        dec de
        ld a,b
        and (hl)
        ld (hl),a
        ld a,(de)
        or b
        ld b,a
        dec hl
        dec de
        ld a,c
        and (hl)
        ld (hl),a
        ld a,(de)
        or c
        ld c,a
        dec hl
        dec de
        pop af
        dec a
        jr nz,.b
; along each row: an opaque pixel to the left, and to the right
        ld de,VIS
        ld hl,FILLT
        ld a,(V_ROWS)
.r:     push af
        ld c,0                  ; 0xFF once an opaque pixel has been seen
        ld b,4
.l:     ld a,(de)
        call .sr                ; a: the pixels at or right of an opaque pixel in the byte
        or c
        and (hl)
        ld (hl),a
        ld a,(de)
        or a
        jr z,.l1
        ld c,0xFF
.l1:    inc de
        inc hl
        djnz .l
        dec de
        dec hl
        ld c,0
        ld b,4
.m:     ld a,(de)
        call .sl
        or c
        and (hl)
        ld (hl),a
        ld a,(de)
        cpl
        and (hl)                ; not the opaque pixels themselves
        ld (hl),a
        ld a,(de)
        or a
        jr z,.m1
        ld c,0xFF
.m1:    dec de
        dec hl
        djnz .m
        inc de
        inc de
        inc de
        inc de
        inc de
        ld bc,5
        add hl,bc
        pop af
        dec a
        jr nz,.r
; VIS |= FILLT
        ld de,VIS
        ld hl,FILLT
        ld b,136
.o:     ld a,(de)
        or (hl)
        ld (de),a
        inc de
        inc hl
        djnz .o
        pop iy
        pop ix
        ret
.sr:    push bc
        ld b,a
        srl a
        or b
        ld b,a
        srl a
        srl a
        or b
        ld b,a
        swapnib
        and 0x0F
        or b
        pop bc
        ret
.sl:    push bc
        ld b,a
        add a,a
        or b
        ld b,a
        add a,a
        add a,a
        or b
        ld b,a
        swapnib
        and 0xF0
        or b
        pop bc
        ret

; IMG: every pixel of the box. Box column x, box row r show graphic pixel x - 1, r - 1
h_img:  ld hl,IMG
        ld (V_IP),hl
        xor a
        ld (V_R),a
.row:   ld a,(V_R)
        dec a
        ld (V_RI),a             ; the graphic's row, 255 above it
        call .blank
        xor a
        ld (V_X1),a
        ld (V_C),a
        ld (V_PI),a
.px:    ld a,(V_X1)
        ld b,a
        and 7
        jr nz,.nt
        ld a,(V_R)              ; a byte of the tables
        add a,a
        add a,a
        ld c,a
        ld a,b
        rrca
        rrca
        rrca
        and 3
        add a,c
        ld l,a
        ld h,OUTL >> 8
        ld a,(hl)
        ld (V_BO),a
        inc h
        ld a,(hl)
        ld (V_BF),a
.nt:    ld a,(V_X1)
        dec a
        and 7
        call z,.load            ; x = 1, 9, 17, 25: the next graphics byte
        ld a,(V_PI)
        ld c,a
        srl a
        add a,V_PN
        ld l,a
        ld h,0
        ld a,(hl)
        bit 0,c
        jr nz,.lo
        swapnib
.lo:    and 15
        call h_px
        ld c,a
        ld a,(V_X1)
        rra
        jr c,.odd
        ld a,c
        swapnib
        ld (V_PK),a
        jr .nx
.odd:   ld a,(V_PK)
        or c
        ld hl,(V_IP)
        ld (hl),a
        inc hl
        ld (V_IP),hl
.nx:    ld hl,V_PI
        inc (hl)
        ld hl,V_X1
        inc (hl)
        ld a,(hl)
        cp 32
        jr nz,.px
        ld a,(V_RI)
        cp 255
        jr z,.nr
        ld hl,(V_TOP)           ; the next row of the frame
        ld a,(V_S)
        ld e,a
        ld d,0
        add hl,de
        ld (V_TOP),hl
.nr:    call x_tick             ; the pace window counts lines through a build
        ld hl,V_R
        inc (hl)
        ld a,(V_ROWS)
        cp (hl)
        jp nz,.row
        ret
.blank: xor a
        ld (V_BG),a
        ld (V_BI),a
        ld hl,V_PN
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a               ; V_CLR
        dec a
        ld (V_BM),a
        ret
; the next graphics byte of this row, or nothing: above, below, or right of the graphic
.load:  xor a
        ld (V_PI),a
        call .blank
        ld a,(V_ROWS)
        sub 2
        ld b,a
        ld a,(V_RI)
        cp b
        ret nc
        ld a,(V_CL)
        ld b,a
        ld a,(V_C)
        cp b
        ret nc
        ld e,a
        ld d,0
        ld hl,(V_TOP)
        add hl,de
        ld a,(V_K)
        rra
        jr nc,.gb
        ld a,(hl)
        ld (V_BM),a
        ld a,(V_CL)
        ld e,a
        add hl,de
.gb:    ld a,(hl)
        ld (V_BG),a
        ld (V_BA),hl
; ink of the cell: items have four, one per quadrant of the 16 x 16
        ld a,(V_K)
        and 2
        ld hl,V_INK
        jr nz,.i
        ld a,(V_RI)
        cp 8
        ld a,0
        jr c,.q
        ld a,2
.q:     ld e,a
        ld a,(V_C)
        add a,e
        ld e,a
        ld d,0
        add hl,de
.i:     ld a,(hl)
        ld (V_BI),a
        ld a,(V_COL)
        or a
        call nz,h_store
        ld hl,V_C
        inc (hl)
        ret

; IMG to pattern memory: 2 x 2 tiles, or 2 x 3
h_upl:  ld a,(V_K)
        and 2
        ld a,2
        jr z,.n
        ld a,3
.n:     ld (V_TY),a
        ld a,(V_P)
        ld (V_TP),a
        ld h,IMG >> 8
.ty:    ld l,0
        call .tile
        ld l,8
        call .tile
        inc h
        ld a,(V_TY)
        dec a
        ld (V_TY),a
        jr nz,.ty
        ret
.tile:  push hl
        ld a,(V_TP)
        ld c,a
        inc a
        ld (V_TP),a
        ld a,c
        srl a
        bit 0,c
        jr z,.s
        or 0x80
.s:     ld bc,0x303B
        out (c),a
        ld e,16
.t:     ld bc,0x085B
        otir
        ld a,l
        add a,8
        ld l,a
        dec e
        jr nz,.t
        pop hl
        ret

; a = painted nibble of the next pixel (bit 7 of V_BG, V_BM, V_CLR) -> a = the pixel's nibble; shifts them
h_px:   push hl
        ld c,a
        ld a,(V_BG)
        ld d,a
        add a,a
        ld (V_BG),a
        ld a,(V_BM)
        ld e,a
        add a,a
        ld (V_BM),a
        ld a,(V_CLR)
        ld b,a
        add a,a
        ld (V_CLR),a
        ld a,(V_BO)
        ld h,a
        add a,a
        ld (V_BO),a
        ld a,(V_BF)
        ld l,a
        add a,a
        ld (V_BF),a
        ld a,c
        or a
        jr nz,.xit              ; painted
        bit 7,b
        jr nz,.xit              ; painted transparent (a = 0)
        bit 7,d
        jr z,.pp
        ld a,(V_BI)
        jr .xit
.pp:    bit 7,e
        jr nz,.oo
        ld a,CBLACK
        jr .xit
.oo:    bit 7,l                 ; clear: the fill, the outline, if any
        ld a,CBLACK
        jr nz,.xit
        bit 7,h
        ld a,0
        jr z,.xit
        ld a,(V_OC)
.xit:   pop hl
        ret

; the colour store's entry of the graphics byte at V_BA: 8 bytes [1, check, 4 nibble bytes, clear, 0]
; Wally's frames are mirrored in place on a turn: the map holds the snapshot's facing
h_store:
        ld a,(V_BG)
        ld (V_ACC),a            ; the check, as the map holds it
        xor a
        ld (V_MIR),a
        ld hl,(V_BA)
        ld a,(V_WAL)
        or a
        jr z,.ns
        ld a,(SINK)             ; his frame 0 is being shifted down a line at a time: no map fits, he stays whole in his ink
        or a
        ret nz
        ld a,(ORIENT)
        ld b,a
        ld a,(V_ORI0)
        cp b
        jr z,.sb
        jr .mr
.ns:    ld a,(V_K)              ; the spear carrier, 0xD680-0xD7FF: 0xB52E mirrors him in place when his direction turns
        cp 3
        jr nz,.sb
        ld a,h
        cp 0xD6
        jr c,.sb
        cp 0xD8
        jr nc,.sb
        ld a,(NATDX)
        ld b,a
        ld a,(V_NAT0)
        xor b
        and 0x80
        jr z,.sb
.mr:
        ; mirrored: the same pixel lies in column 2 - c of the triple, bits reversed
        ld a,1
        ld (V_MIR),a
        ld a,(V_C)
        add a,a
        ld c,a
        ld b,0
        ld hl,(V_BA)
        inc hl
        inc hl
        or a
        sbc hl,bc
        ld a,(V_BG)
        ld c,a
        ld b,REVT
        ld a,(bc)
        ld (V_ACC),a
        jr .sb
.sb:    ld a,(V_WAL)            ; Wally is in bank 3, his keys below the figures': address - 0x6000
        or a
        jr z,.sc
        ld a,h
        sub 0x60
        ld h,a
.sc:    ld a,h
        sub 0x60
        ret c
        ld d,a
        ld e,l
        ld a,d
        srl a
        srl a
        add a,STORE
        nextreg 0x53,a
        ld a,d
        and 3
        ld h,a
        ld l,e
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x6000
        add hl,de
        ld a,(hl)
        or a
        jr z,.x
        inc hl
        ld a,(V_ACC)
        cp (hl)
        jr nz,.x
        inc hl
        ld de,V_PN
        ld bc,5
        ldir
.x:     nextreg 0x53,GP3
        ld a,(V_MIR)
        or a
        ret z
        ; reverse: 4 nibble bytes end to end, each swapped; the clear mask by the game's table
        ld a,(V_PN)
        swapnib
        ld b,a
        ld a,(V_PN+3)
        swapnib
        ld (V_PN),a
        ld a,b
        ld (V_PN+3),a
        ld a,(V_PN+1)
        swapnib
        ld b,a
        ld a,(V_PN+2)
        swapnib
        ld (V_PN+1),a
        ld a,b
        ld (V_PN+2),a
        ld a,(V_CLR)
        ld c,a
        ld b,REVT
        ld a,(bc)
        ld (V_CLR),a
        ret
h_end:

; ---- set-up: stub bank at 0xD000 ----
        ORG 0xD000
setup:  nextreg 0x50,HPG
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,PAL
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x50,0xFF
        nextreg 0x4B,0              ; index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2              ; clip window = the play area
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,127
        nextreg 0x12,34             ; Layer 2 banks 34-36 (all transparent)
        nextreg 0x69,0
        nextreg 0x15,0x05           ; sprites on, L over S over U, higher number on top
; the loading picture is on show from bank 5: hold it until a key, or 250 frames
        xor a
        out (0xFE),a
        ld hl,250
        ld d,0                      ; 1 once the keyboard has been seen clear
.s:     call .fr
        or a
        jr nz,.k
        ld d,1
        jr .t
.k:     bit 0,d
        jr nz,.lv
.t:     dec hl
        ld a,h
        or l
        jr nz,.s
.lv:    ld hl,250                   ; leave when the key has gone, so the menu does not see it
        ld d,0
.w:     call .fr
        or a
        jr z,.c
        ld d,0
        jr .u
.c:     inc d
        ld a,d
        cp 3
        ret nc
.u:     dec hl
        ld a,h
        or l
        jr nz,.w
        ret
; one frame; a = the keyboard bits seen in it
.fr:    ld e,0
.f1:    call .po
        cp 192
        jr nz,.f1
.f2:    call .po
        cp 192
        jr z,.f2
        ld a,e
        ret
.po:    ld bc,0x243B
        ld a,0x1F
        out (c),a
        inc b
        in c,(c)
        xor a
        in a,(0xFE)
        cpl
        and 0x1F
        or e
        ld e,a
        ld a,c
        ret
        SAVEBIN "tw_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "tw_hook.bin",0x0200,h_end-0x0200
        SAVEBIN "tw_setup.bin",0xD000,$-0xD000
