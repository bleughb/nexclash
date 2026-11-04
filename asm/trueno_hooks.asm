; El Capitan Trueno (Dinamic, 1990, 48K) - figures as hardware sprites, foreground in Layer 2.
; The game plots every figure into a window back buffer (0xF2E0, 30 x 112) and its attribute buffer
; (0xF13C, 30 x 14); the ISR task 0x8865 copies both to the screen when a render is ready, then
; restores the scenery under the figures. The plotter already has a "behind the foreground" mode: for
; a cell set in the foreground map it saves the scenery under the figure (restore list as usual) but
; draws no pixel and paints no attribute. A data patch (0x87BE) points the plotter at a map of all
; 0xFF bytes in the ROM (0x3B00, the 48K ROM's unused block, the same in the alt ROM), so no figure
; reaches the buffer or the attributes: the ULA shows the scenery only (host's idea, 2026-10-13), and
; every other byte of game memory is as the original. Each figure is shown as sprites instead.
; Foreground cells of the real map 0xEF60 are copied into Layer 2 with the palette priority bit, so
; bushes and grass stay in front of the sprites as in the original.
; Entry/exit stubs live in alt ROM image 1 at 0x386E; hook bodies, state and tables live in Next RAM
; page PAGE_S, mapped at MMU slot 0 while a hook runs (the game's IM2 handler never touches slot 0;
; the ISR hooks save and restore the slot 0 page they find).
;
; Patch sites (original bytes verified by trueno.py):
;   0x82DF  DD CB 03 46  BIT 0,(IX+3)   -> JP e_fig  (figure entry: record frame, x, y, flags)
;   0x88A2  21 08 E6     LD HL,0xE608   -> JP e_cm   (ISR, screen copy done: show the sprites)
;   0x8865  3A 08 E6     LD A,(0xE608)  -> JP e_tk   (ISR task, every interrupt: pending clear)
;   0x887D  3F 1F 32     CCF / RRA / LD (0xE608),A -> JP e_shk (ISR: the shaken copy, 8 lines lower,
;                                                    e.g. Goliath landing: flag it for the commit)
;   0x6410  21 60 EF     LD HL,0xEF60   -> JP e_scr  (foreground map rebuilt: new screen)
;   0xA207  21 00 58     LD HL,0x5800   -> JP e_cls  (screen clear: menu, game over)
;   0xA375  C3 01 A5     JP 0xA501      -> JP e_mnu  (in-game pause menu: Layer 2 and sprites off
;                                                    while its window is up, 2026-10-13)
;   0x5DCD  CD 0E 5E     CALL 0x5E0E    -> JP e_end  (screen 60, the end of part 1: the access code
;                                                    screen: sprites off, Layer 2 only on the panel (the
;                                                    host's portraits, 2026-10-31); the next game's
;                                                    first screen turns them on, 2026-10-13)
;   0x5FCA  CD FD 5F     CALL 0x5FFD    -> JP e_men  (title menu printed: CPU 7 MHz, host 2026-10-17)
;   0x607F  CD 1F 98     CALL 0x981F    -> JP e_go   (the game starts from the menu: CPU 3.5 MHz)
;   0xA43D  4F 87 87     LD C,A / ADD A,A / ADD A,A -> JP e_sfx (a sound effect: always at 3.5 MHz)
;   0x889B  21 3C F1     LD HL,0xF13C   -> JP e_att  (ISR copy, attribute source: 0xEF98, the scenery
;                                                    without figures; screen 34 (the dragon, clear mode):
;                                                    0xF13C as the original, for its energy bar drawn
;                                                    via 0x82E4 past the figure hook, 2026-10-13)
;   0xA2C2  26 00 6F     LD H,0 / LD L,A -> JP e_glyph (make_nex --ru / --multi: Cyrillic glyphs)
; make_nex --multi (assembled -DMULTI=1; title menu items 5 COLOR and 6 language, 2026-10-31):
;   0x5FFD  CD F0 5F     CALL 0x5FF0    -> JP e_mprt (print the menu: also the state of item 5)
;   0x5FF1  05 -> 06     LD B,6: six menu items (the count for drawing and for the keys)
;   0x604C  98 5F -> 8D 61 LD DE,0x5F98 at 0x604B: the dispatch table with items 5 and 6, written by
;                          make_nex over the old colour handler 0x618D (unused now; 12 bytes)
;   0x5ED1  the old menu list (unused now): the state words of item 5, written by make_nex
;   0x87BE  60 EF -> C8 3C   the plotter's all-0xFF map at the alt ROM's top 0x3CC8 (not 0x3B00)
;   0xA621  CD 1F E9     CALL 0xE91F    -> JP e_swd  (pause window, item 4: the sword as a sprite in
;                                                    colour instead of its glyphs, host 2026-10-31)
; NextReg 0x7F (user register) carries the requests: bit 0 = rebuild Layer 2 at the next commit,
; bit 6 = this copy is shaken (8 lines lower), bit 7 = clear Layer 2 and the sprites at the next
; interrupt. The main-code stubs only write it
; with NEXTREG (no register, flag or memory change); only the ISR reads it.

        DEVICE ZXSPECTRUMNEXT

PAGE_S  EQU 26                  ; hook page (bank 13, first half)
PAT0    EQU 28                  ; first pattern data page (bank 14 on)
L2BANK  EQU 27                  ; Layer 2: banks 27-29 = pages 54-59 (patterns use banks 14-26)
L2PAGE  EQU 54
MAXF    EQU 64                  ; figures per render
NSPR    EQU 128                 ; sprites / 4-bit patterns
TRANSP  EQU 0xE3                ; Layer 2 transparent colour (NextReg 0x14 default)
BWPAGE  EQU 60                  ; bush and fix cells made on the PC (build/bush_walls.py), pages 60 on:
                                ; page 60 = page per screen (64 bytes, 0 = none), then its offset in
                                ; that page (64 words at 0x40); a screen's block: count, then per cell
                                ; row, column, 64 Layer 2 bytes. Blocks are packed (2026-10-14); a
                                ; block may run on into the next page (read via slots 2 and 3)
L2COL   EQU 16                  ; Layer 2 palette index 16 + colour (0-7, +8 bright), priority set
                                ; RUFONT: Cyrillic glyphs in the alt ROM, set after MULTI below
PORTPG  EQU 76                 ; the host's portraits (build/portraits.bin): bank 38, first half
L2NP    EQU 32                 ; the same colours without priority (wall ropes, under the sprites)
L2GREY  EQU 48                  ; grey 36 and grey 73 (the hidden portraits, host 2026-11-01)

G_FLAGS EQU 0xE608              ; bit 0 = render ready (the ISR copies it)
G_MODE  EQU 0xE60B              ; 34 = clear mode (blank buffer)
G_MAP   EQU 0xEF60              ; foreground cell map: 4 bytes per cell row, 14 rows, bit 7 = column 0
G_ATTR  EQU 0xEF98              ; window attributes without figures, 30 x 14
G_BUF   EQU 0xF2E0              ; window pixels, 30 bytes x 112 lines (screen x 8, y 16)

; ---- hook page layout ----
V_SP    EQU 0x0000              ; game SP in the figure hook
V_SP2   EQU 0x0002              ; game SP in the ISR hooks
V_SLOT0 EQU 0x0004              ; slot 0 page found by an ISR hook
V_N     EQU 0x0005              ; figures recorded this render
V_PREV  EQU 0x0006              ; sprites shown now
V_NEXT  EQU 0x0007              ; next free 4-bit pattern
V_S     EQU 0x0008              ; next sprite (commit)
V_OVF   EQU 0x0009              ; pattern memory full in this pass
V_PAT   EQU 0x000A              ; figure: first pattern
V_FX    EQU 0x000B              ; figure: descriptor x, y, flags
V_FY    EQU 0x000C
V_FF    EQU 0x000D
V_COLS  EQU 0x000E
V_ROWS  EQU 0x000F
V_DX    EQU 0x0010
V_DY    EQU 0x0011
V_PADS  EQU 0x0012
V_MX    EQU 0x0013
V_MY    EQU 0x0014
V_ATTR2 EQU 0x0015
V_X0    EQU 0x0016              ; 2: box x in sprite coordinates
V_Y0    EQU 0x0018
V_R     EQU 0x0019
V_C     EQU 0x001A
V_RSRC  EQU 0x001C              ; 2: Layer 2 pass: buffer row of this cell row
V_RATT  EQU 0x001E              ; 2: attribute row
V_NEW   EQU 0x0020              ; 2: the map to show
V_LDST  EQU 0x0022              ; 2: Layer 2 address of the cell
V_INK   EQU 0x0024              ; Layer 2 colours of the cell
V_PAP   EQU 0x0025
V_LY    EQU 0x0028              ; Layer 2 pass: first screen line of the cell row
V_LN    EQU 0x0029              ; line in the cell row (0-7)
V_C0    EQU 0x002A              ; run of foreground cells: first, last column
V_C1    EQU 0x002B
V_XL    EQU 0x002C              ; leftmost / rightmost ink pixel of the run, current x
V_XR    EQU 0x002D
V_X     EQU 0x002E
V_REQ   EQU 0x002F              ; NextReg 0x7F as read by the commit
V_SHK   EQU 0x0030              ; 8 when this copy is shaken, else 0
V_LI    EQU 0x0031              ; rope cell: left neighbour ink, paper (Layer 2 indices)
V_LP    EQU 0x0032
V_RI    EQU 0x0033              ; right neighbour ink, paper
V_RP    EQU 0x0034
V_RT    EQU 0x0035              ; 2: rope mask table, current row
V_FAC   EQU 0x0026              ; figure: stored facing (bit 7)
V_BLK   EQU 0x0027              ; renders shown (bit 0: blink phase)
V_BW    EQU 0x0036              ; 1 = this screen's bush cells came from the table (no pass 2b)
STK1    EQU 0x0100              ; figure hook stack (0x0040-0x00FF; the ISR may push 34 bytes on it)
RESF    EQU 0x0F00              ; per frame: first pattern + 1 of its hit-flash shape
FIGS    EQU 0x1000              ; MAXF x (frame, x, y, flags)
RES     EQU 0x1100              ; per frame: first pattern + 1 (0 = not in pattern memory)
SDIR    EQU 0x1200              ; per frame (220 x 8): page, first | facing << 7, cols, rows, dx, dy, pads, mdx
OLDMAP  EQU 0x1900              ; the foreground map Layer 2 shows now (56 bytes)
ZMAP    EQU 0x1940              ; 56 zero bytes (the empty map)
OLDROPE EQU 0x1980              ; the rope cells Layer 2 shows now (56 bytes, map layout)
FDIR    EQU 0x1A00              ; per frame (220 x 2): page, first of its hit-flash silhouette shape
BLINK   EQU 0x1C00              ; per frame: 1 = the hit flash blinks (normal / silhouette)
STK2    EQU 0x2000              ; ISR hook stack (0x1D00-0x1FFF)
V_MHZ   EQU 0x0037              ; CPU speed (NextReg 0x07) of the main code, found by an ISR hook
        IFNDEF TITLE_MHZ        ; CPU speed after the title: 1 = 7 MHz (the menu); -DTITLE_MHZ=0 for a test
                                ; build from a snapshot in the game (make_nex.py --snap)
TITLE_MHZ EQU 1
        ENDIF
        IFNDEF GAME_MHZ         ; the game's CPU speed (e_go): 0 = 3.5 MHz; -DGAME_MHZ=3 = the fast game
GAME_MHZ EQU 0                  ; experiment (28 MHz, frame limiter e_lim, delays e_dly; make_nex --fast)
        ENDIF
        IFNDEF LIM
LIM     EQU 4                   ; fast game: at least this many frames per render (the original's usual)
        ENDIF
V_FRM   EQU 0x0038              ; fast game: interrupts counted by e_tk
V_LAST  EQU 0x0039              ; fast game: V_FRM at the last render
        IFNDEF MULTI            ; -DMULTI=1: all three languages and both sprite colourings, chosen in
MULTI   EQU 0                   ; the title menu (items 5 and 6; make_nex.py --multi, host 2026-10-31)
        ENDIF
        IF MULTI                ; Cyrillic glyphs (make_nex): multi: room for 24 below the all-0xFF map,
RUFONT  EQU 0x3C08              ; which moves to the alt ROM's top 0x3CC8-0x3CFF (the menus need one
        ELSE                    ; free run after the stubs, also in the fast game)
RUFONT  EQU 0x3C00              ; texts_ru.RUFONT (make_nex --ru)
        ENDIF
V_LANG  EQU 0x003A              ; multi: language 0 Espanol, 1 English, 2 Russian
V_COL   EQU 0x003B              ; multi: 1 = COLOR ON (the host's "- Copy" sheets), 0 = OFF
V_STW   EQU 0x003C              ; multi, 2: the item with the state word of item 5 (alt ROM)
V_SWD   EQU 0x003E              ; multi: 1 = the pause's sword sprite is up (palette, clip changed)
SW_X    EQU 148                 ; multi: the sword's 16x16 box on the screen (build/pause_sword.py)
SW_Y    EQU 92
PLIST   EQU 0xE8B2              ; multi: the pause window's draw list, its first PLEN bytes (s_pwin)
PLEN    EQU 24
STOREPG EQU 77                  ; multi: both colourings and the texts (make_nex), at slot 1 when used:
ST_COL  EQU 0x0900              ;   COLOR OFF block at 0, ON block here: SDIR copy, FDIR copy at +0x700,
                                ;   16 palette bytes at +0x8C0
ST_STW  EQU 0x1200              ;   6 words: state word item for language * 2 + V_COL
ST_LANG EQU 0x1210              ;   3 words: the language's records at slot 1 (word address, byte length,
                                ;   bytes; address 0 ends)

; ---- alt ROM stubs ----
        ORG 0x386E
e_fig:  nextreg 0x50,PAGE_S
        jp s_fig
x_fig:  nextreg 0x50,0xFF
        bit 0,(ix+3)
        jp 0x82E3
e_cm:   ld bc,0x243B            ; AF BC DE HL are dead here (all set before use by 0x88A5 on)
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        nextreg 0x50,PAGE_S
        ld (V_SLOT0),a
        jp s_cm
x_cm:   nextreg 0x50,a
        ld hl,G_FLAGS
        jp 0x88A5
e_tk:
        IF GAME_MHZ
        ld bc,0x243B            ; fast game: count the interrupts (V_FRM, for the frame limiter e_lim)
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        nextreg 0x50,PAGE_S
        ld hl,V_FRM
        inc (hl)
        nextreg 0x50,a
        ENDIF
        ld bc,0x243B            ; AF BC DE HL are dead here (task entry: LD A,(nn) / RRA / RET NC ...)
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        rla
        jr c,e_tkc
x_tk:   ld a,(G_FLAGS)
        jp 0x8868
e_tkc:  dec b
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        nextreg 0x50,PAGE_S
        ld (V_SLOT0),a
        jp s_tk
x_tk2:  nextreg 0x50,a
        jr x_tk
e_shk:  ccf                     ; the original three instructions
        rra
        ld (G_FLAGS),a
        ld bc,0x243B            ; BC A F are dead here (LD BC / LD DE / XOR A follow): flag bit 6
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        or 0x40
        out (c),a
        jp 0x8882
e_scr:  nextreg 0x7F,1          ; new screen: rebuild Layer 2 at the next commit (drops a pending clear:
                                ; the rebuild clears every cell that is not foreground any more)
        nextreg 0x69,0x80       ; Layer 2 on (off if the pause menu was left without its RET)
        nextreg 0x50,PAGE_S     ; forget the figures recorded so far in this render: they belong to
        ld hl,V_N               ; the old screen (the original overwrites them in the buffer; here
        ld (hl),0               ; they showed as sprites on the new screen's first copy). HL is set next
        nextreg 0x50,0xFF
        nextreg 0x15,0x00       ; sprites off until the next commit: the copy takes most of a frame,
                                ; the old sprites flashed over the new screen meanwhile
        ld hl,G_MAP
        jp 0x6413
e_cls:  nextreg 0x7F,0x81       ; clear Layer 2 and the sprites, then rebuild at the next commit
        ld hl,0x5800
        jp 0xA20A
e_end:  nextreg 0x50,PAGE_S     ; the access code screen (s_end)
        jp s_end
x_end:  nextreg 0x50,0xFF
        jp 0x5DD0
e_fade: call cnoop             ; 0x984D: the screen fades out (death, end of part 1; 0x5E33 fades the
        nextreg 0x15,0x00       ; ULA attributes only): sprites and Layer 2 off first, they stayed bright
        nextreg 0x69,0x00       ; over it until the menu (host, 2026-10-18). On again by the game: the
        call 0x5E33             ; commit (sprites), a new screen (e_scr: Layer 2)
        jp 0x9850
e_glyph:                        ; 0xA2C2 (make_nex --ru): the glyph of code A: 0x5C65 + 8 * A as the
        ld h,0                  ; original, or a Cyrillic glyph (code 0x2D on, texts_ru.py) at RUFONT +
        cp 0x2D                 ; 8 * (A - 0x2D) in this alt ROM. DE is set again after 0xA2CC
        jr nc,.ru
        ld l,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x5C65
        add hl,de
        jp 0xA2CC
.ru:    sub 0x2D
        ld l,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,RUFONT
        add hl,de
        jp 0xA2CC
cnoop:  nextreg 0x61,2         ; copper: no shake or pause instructions (clist, NOOP = 0x0000), they
        nextreg 0x62,0xC0       ; would turn Layer 2 on again. NEXTREG keeps every register
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x61,6
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x61,14
        nextreg 0x63,0
        nextreg 0x63,0
        ret
e_att:  push af                 ; the copy's attribute source (HL', set before CALL 0x8915)
        ld hl,0xEF98
        ld a,(0xE60B)
        cp 34
        jr nz,.a
        ld hl,0xF13C
.a:     pop af
        jp 0x889E
e_mnu:  nextreg 0x15,0x00       ; pause menu (0xA36C tail-jumps to it; it returns with RET NC/C):
        nextreg 0x61,2          ; its window is drawn in the ULA, so hide the sprites, and the copper
        nextreg 0x62,0xC0       ; turns Layer 2 off for lines 16-135 only (clist): the top frame line
        nextreg 0x63,0x69       ; (y 14) and the host's portraits stay (2026-10-18). NEXTREG keeps
        nextreg 0x63,0x00       ; every register and flag. A pause left without its RET: the clear
        nextreg 0x61,6          ; (s_tk) or the next commit (cshake) sets the copper back
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x61,14
        nextreg 0x63,0x69
        nextreg 0x63,0x80
        IF MULTI
        call e_pwin             ; the window's own draw list (the dragon's record may lie over it)
        ENDIF
        call 0xA501
        IF MULTI
        call e_swx              ; the sword sprite away, the clip, the palette and the record back
        ENDIF
        call cnoop
        nextreg 0x69,0x80       ; the copper may have left it off (mid-frame)
        nextreg 0x15,0x01
        ret
e_por:  ld a,(0x96FA)            ; the panel's three portraits (0x95C3; table 0x96E9/F1/F9, +1 bit 0 =
        ld h,a                  ; hidden): the game swaps their attributes in and out; when one was
        ld a,(0x96F2)           ; swapped, the host's cells are set at once, not at the next commit
        ld l,a                  ; (host: the old hero's cells stayed for a moment). The callers
        push hl                 ; (0x89FF, 0x983F) set every register again afterwards
        ld a,(0x96EA)
        push af
        ld ix,0x96E9
        call 0x97E1
        ld ix,0x96F1
        call 0x97E1
        ld ix,0x96F9
        call 0x97E1
        pop af
        ld hl,0x96EA
        xor (hl)
        ld b,a
        pop hl
        ld a,(0x96F2)
        xor l
        or b
        ld b,a
        ld a,(0x96FA)
        xor h
        or b
        and 1
        ret z
        nextreg 0x50,PAGE_S
        jp s_por
x_por:  nextreg 0x50,0xFF
        ret
e_men:  call 0x5FFD            ; title menu printed: 7 MHz while it waits for a key (host; the
        nextreg 0x07,1         ; game itself is timed by the CPU and stays at 3.5 MHz)
        jp 0x5FCD
e_go:   nextreg 0x07,GAME_MHZ   ; the game starts from the menu: 3.5 MHz (fast game: 28)
        call 0x981F
        jp 0x6082
        IF GAME_MHZ
e_lim:  push af                 ; fast game, 0x89FA (render ready next): at least LIM frames since the
        ld a,i                  ; last render, so the game keeps the original's pace. P/V = IFF2: no
        jp po,.go               ; waiting with interrupts off. Slot 0 = page S while waiting (the ISR
        nextreg 0x50,PAGE_S     ; hooks keep the page they find)
.w:     ld a,(V_FRM)
        ld hl,V_LAST
        sub (hl)
        cp LIM
        jr c,.w
        ld a,(V_FRM)
        ld (V_LAST),a
        nextreg 0x50,0xFF
.go:    pop af
        ld hl,0xE608
        jp 0x89FD
e_dly:  push bc                 ; fast game, 0xA18F: a delay loop timed by the CPU (the pause menu, the
        ld a,i                  ; access code screen, ...): at 3.5 MHz when the game runs at 28, then
        push af                 ; the speed again; the menu's 7 MHz stays (the host liked its pace).
        di                      ; NextReg 0x07 is read with interrupts off: the ISR hooks select other
        ld bc,0x243B            ; registers on 0x243B (a read of 0x7F set the menu to 3.5 MHz,
        ld a,0x07               ; 2026-10-31); P/V of LD A,I = IFF2
        out (c),a
        inc b
        in a,(c)
        and 3
        ld c,a
        pop af
        jp po,.k
        ei
.k:     ld a,c
        cp 3
        jr nz,.l
        nextreg 0x07,0
.l:     dec de                  ; the original loop
        ld a,d
        or e
        jr nz,.l
        ld a,c
        nextreg 0x07,a
        xor a                   ; A = 0 and Z as the original leaves them
        pop bc
        ret
        ENDIF
e_sfx:  ld e,a                  ; a sound effect (0xA43D, A = effect; all of them come here and leave
        ld a,i                  ; by the RET at 0xA472; the only beeper code, its pitch and gaps are
        push af                 ; timed by the CPU): the whole effect at 3.5 MHz, then the speed found
        di                      ; here again (host: per note switching was heard as noise).
        ld bc,0x243B            ; BC, DE, HL are set by the effect before use. NextReg 0x07 is read
        ld a,0x07               ; with interrupts off (the ISR hooks select other registers on
        out (c),a               ; 0x243B; see e_dly)
        inc b
        in a,(c)
        and 3
        ld l,a
        pop af
        jp po,.k
        ei
.k:     push hl
        nextreg 0x07,0
        ld a,e
        ld c,a                  ; the original LD C,A / ADD A,A / ADD A,A
        add a,a
        add a,a
        call 0xA440
        ex (sp),hl              ; L = the speed found; the effect's registers and flags go back as
        push af                 ; it left them
        ld a,l
        nextreg 0x07,a
        pop af
        pop hl
        ret
        IF MULTI                ; title menu (s_mprt, s_col, s_lang run from page S; the dispatch table
e_mprt: nextreg 0x50,PAGE_S     ; is in the game's RAM, make_nex): 0x5FFD, the menu
        jp s_mprt
x_mprt: nextreg 0x50,0xFF
        ret
e_col:  nextreg 0x50,PAGE_S     ; menu item 5: COLOR ON <-> OFF, the sprite colouring
        jp s_col
e_lang: nextreg 0x50,PAGE_S     ; menu item 6: the next language
        jp s_lang
e_swd:  nextreg 0x50,PAGE_S     ; pause window, item 4 (0xA621): the sword as a sprite
        jp s_swd
e_swx:  nextreg 0x50,PAGE_S     ; the pause is over: the sword sprite away
        jp s_swx
e_pwin: nextreg 0x50,PAGE_S     ; the pause begins: its window's draw list
        jp s_pwin
        ENDIF
rom_end:

; ---- hook page code ----
        ORG 0x0100
; figure entry 0x82DF, IX = descriptor: record it when visible. Keeps every register and flag.
s_fig:  ld (V_SP),sp
        ld sp,STK1
        push af
        push hl
        bit 0,(ix+3)
        jr z,.out
        ld a,(V_N)
        cp MAXF
        jr nc,.out
        inc a
        ld (V_N),a
        dec a
        add a,a
        add a,a
        ld l,a
        ld h,high FIGS
        ld a,(ix+0)
        ld (hl),a
        inc l
        ld a,(ix+1)
        ld (hl),a
        inc l
        ld a,(ix+2)
        ld (hl),a
        inc l
        ld a,(ix+3)
        ld (hl),a
.out:   pop hl
        pop af
        ld sp,(V_SP)
        jp x_fig

; ISR, after the screen copy (0x88A2): Layer 2 if a new screen, patterns, sprites, hide the rest.
s_cm:   ld (V_SP2),sp
        ld sp,STK2
        call mhz
        ld hl,V_BLK
        inc (hl)
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        ld (V_REQ),a
        and 0x40                ; shaken copy: Layer 2 and the sprites 8 lines lower too
        rrca
        rrca
        rrca
        ld (V_SHK),a            ; 8 or 0
        neg
        jr z,.ns
        add a,192               ; Layer 2 y offset 192 - 8
.ns:    call cshake             ; the scroll is the copper's (clist)
        nextreg 0x1C,1         ; Layer 2 clip: the whole screen (the pause menu clips it to the panel)
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        IF MULTI
        ld a,(V_SWD)            ; the pause was left without its RET while the sword was up
        or a
        call nz,swoff
        ENDIF
        ld a,(V_REQ)
        and 0x81                ; bit 6 consumed
        ld (V_REQ),a
        rra
        jr nc,.req
        ld a,(V_REQ)
        and 0x80
        ld (V_REQ),a
        ld hl,G_MAP
        ld a,(G_MODE)           ; screen 34 (the dragon, clear mode: the buffer is blank): Layer 2
        cp 34                   ; cleared (the old screen's foreground stayed there, 2026-10-13)
        jr nz,.map
        ld hl,ZMAP
.map:   call l2map
.req:   ld a,(V_REQ)
        nextreg 0x7F,a
.figs:  call pats
        ld a,(V_OVF)
        or a
        jr z,.emit
        call flush              ; pattern memory full: start again with this render's shapes
        call pats
.emit:  call emit
        call hide
        call ports              ; the host's portraits over the panel
        nextreg 0x15,0x01       ; sprites on (off since a new screen was built), order S L U
        xor a
        ld (V_N),a
        jp isrx

; ISR task entry (0x8865) with a clear request: Layer 2 and sprites off.
s_tk:   ld (V_SP2),sp
        ld sp,STK2
        call mhz
        nextreg 0x7F,1          ; done; rebuild at the next commit
        ld hl,ZMAP
        call l2map
        xor a
        ld (V_S),a
        call hide
        call portsoff
        xor a                   ; no shake (the copper would turn Layer 2 on at line 24)
        call cshake
        ld a,(V_MHZ)
        nextreg 0x07,a
        ld a,(V_SLOT0)
        nextreg 0x51,0xFF
        ld sp,(V_SP2)
        jp x_tk2

; ---- the panel's portraits: Layer 2 cells over it (cell rows 17-23); host 2026-10-17 redrawn,
; 2026-11-01 all three at once, the hidden ones grey (the face lighter) ----
; portraits.bin (build/portraits_l2.py) in page PORTPG, mapped at slot 3 here: count, then per cell:
; +0 state, +1 flags (bit 0: 64 colour pixels at +29), +2 cell row, +3 column, +4 the original 8 pixel
; bytes, +12 its attribute, +13 16 bytes of grey pixels (2 bits each, the leftmost first: 0 transparent,
; 1 grey 36, 2 grey 73). The game hides a portrait by attributes 0 and keeps its pixels, so the screen
; tells the state: pixels and attribute as the original = the hero in play (state 1: the host's colour
; pixels, or transparent where the ULA's own cell stays), the pixels with attribute 0 = hidden (state 2:
; grey), anything else = another picture there (state 0: transparent). Only cells whose state changed
; are drawn. Slot 3 goes back to page 11; slot 1 is set again by the ISR exit.
ports:  push ix
        nextreg 0x53,PORTPG
        ld ix,0x6001
        ld a,(0x6000)
        ld b,a
.cell:  push bc
        call pstate
        cp (ix+0)
        call nz,pcell
        call pnext
        pop bc
        djnz .cell
        nextreg 0x53,11
        pop ix
        ret

; A = the state the screen asks for cell IX (see ports)
pstate: ld a,(ix+2)             ; HL = its top pixel line: 0x4000 + (row & 0x18) * 256 + (row & 7) * 32
        ld c,a                  ; + column
        and 0x18
        or 0x40
        ld h,a
        ld a,c
        and 7
        rrca
        rrca
        rrca
        or (ix+3)
        ld l,a
        push ix
        pop de
        ld a,e                  ; DE = IX + 4: the original pixels
        add a,4
        ld e,a
        adc a,d
        sub e
        ld d,a
        ld b,8
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc h
        djnz .cmp
        ld a,c                  ; HL = its attribute: 0x5800 + (row >> 3) * 256 + (row & 7) * 32 + column
        and 0x18
        rrca
        rrca
        rrca
        add a,0x58
        ld h,a
        ld a,c
        and 7
        rrca
        rrca
        rrca
        or (ix+3)
        ld l,a
        ld a,(de)
        cp (hl)
        ld a,1
        ret z                   ; in play
        ld a,(hl)
        or a
        ld a,2
        ret z                   ; hidden
.no:    xor a
        ret

; IX = the next cell
pnext:  ld de,29
        bit 0,(ix+1)
        jr z,.n
        ld e,29+64
.n:     add ix,de
        ret

; main code (e_por, a portrait swapped): the cells at once, interrupts off meanwhile (slot 3 is borrowed)
s_por:  ld (V_SP),sp
        ld sp,STK1
        ld a,i                  ; P/V = IFF2
        di
        push af
        call ports
        nextreg 0x51,0xFF
        pop af
        ld sp,(V_SP)
        jp po,x_por
        ei
        jp x_por

; all portrait cells transparent (the Layer 2 clear: menu, game over)
portsoff:
        push ix
        nextreg 0x53,PORTPG
        ld ix,0x6001
        ld a,(0x6000)
        ld b,a
.c:     push bc
        xor a
        cp (ix+0)
        call nz,pcell
        call pnext
        pop bc
        djnz .c
        nextreg 0x53,11
        pop ix
        ret

; cell IX into Layer 2 in state A (0 transparent, 1 in play, 2 grey); +0 = A
pcell:  ld (ix+0),a
        ld c,a
        ld a,(ix+2)             ; y = row * 8: page L2PAGE + y / 32 at slot 1, DE = 0x2000 + (y & 31) * 256
        add a,a                 ; + column * 8
        add a,a
        add a,a
        ld b,a
        rlca
        rlca
        rlca
        and 7
        add a,L2PAGE
        nextreg 0x51,a
        ld a,b
        and 31
        add a,0x20
        ld d,a
        ld a,(ix+3)
        add a,a
        add a,a
        add a,a
        ld e,a
        ld a,c
        dec a
        jr z,.col
        dec a
        jr z,.grey
        jr .tr
.col:   bit 0,(ix+1)
        jr z,.tr                ; no colour pixels: the ULA's own cell shows
        push ix
        pop hl
        ld bc,29
        add hl,bc               ; HL = its colour pixels
        ld a,8
.ln:    push af
        ld bc,8
        ldir
        ld a,e
        sub 8
        ld e,a
        inc d
        pop af
        dec a
        jr nz,.ln
        ret
.grey:  push ix
        pop hl
        ld bc,13
        add hl,bc               ; HL = its grey pixels, 2 bytes a line
        ld c,8
.gl:    ld a,(hl)
        inc hl
        call grey4
        ld a,(hl)
        inc hl
        call grey4
        ld a,e
        sub 8
        ld e,a
        inc d
        dec c
        jr nz,.gl
        ret
.tr:    ld c,8
.tl:    ld b,8
        ld a,TRANSP
.tp:    ld (de),a
        inc e
        djnz .tp
        ld a,e
        sub 8
        ld e,a
        inc d
        dec c
        jr nz,.tl
        ret

; 4 grey pixels from A (2 bits each, the leftmost first) to DE, E advanced; keeps C and HL
grey4:  ld b,4
.g:     rlca
        rlca
        push af
        and 3
        jr z,.t
        add a,L2GREY-1          ; 1: grey 36, 2: grey 73
        jr .w
.t:     ld a,TRANSP
.w:     ld (de),a
        inc e
        pop af
        djnz .g
        ret

; the copper's shake instructions (clist bytes 2, 6, 8; byte 14, the pause's, NOOP): A = Layer 2 Y
; scroll, 184 shaken or 0. NextReg 0x63 writes each instruction whole (the copper never reads half)
cshake: nextreg 0x61,14
        nextreg 0x62,0xC0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x61,2
        nextreg 0x62,0xC0       ; the same start control: the copper goes on
        or a
        jr z,.off
        nextreg 0x63,0x69       ; MOVE 0x69,0x00
        nextreg 0x63,0x00
        nextreg 0x61,6
        nextreg 0x63,0x69       ; MOVE 0x69,0x80
        nextreg 0x63,0x80
        nextreg 0x63,0x17       ; MOVE 0x17,A
        nextreg 0x63,a
        ret
.off:   nextreg 0x63,0          ; NOOP
        nextreg 0x63,0
        nextreg 0x61,6
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        nextreg 0x63,0
        ret

mhz:    ld bc,0x243B            ; remember the main code's CPU speed, then 28 MHz for the hook
        ld a,0x07
        out (c),a
        inc b
        in a,(c)
        and 3                   ; bits 1-0: the programmed speed
        ld (V_MHZ),a
        nextreg 0x07,3
        ret

isrx:   ld a,(V_MHZ)            ; back to the main code's speed (menu 7 MHz, game 3.5 MHz)
        nextreg 0x07,a
        nextreg 0x51,0xFF
        ld a,(V_SLOT0)
        ld sp,(V_SP2)
        jp x_cm

; hide sprites V_S .. V_PREV-1, V_PREV = V_S
hide:   ld a,(V_PREV)
        ld e,a
        ld a,(V_S)
        ld (V_PREV),a
.h:     cp e
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .h

; HL = SDIR + E * 8
sdir:   ld l,e
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,high SDIR
        ld h,a
        ret

flush:  ld hl,RES                ; forget every resident shape (normal and hit flash)
        ld b,0
.z:     ld (hl),0
        inc hl
        djnz .z
        ld hl,RESF
.zf:    ld (hl),0
        inc hl
        djnz .zf
        xor a
        ld (V_NEXT),a
        ret

; make every recorded figure's shape resident in pattern memory (V_OVF = 1 when it does not fit)
pats:   xor a
        ld (V_OVF),a
        ld a,(V_N)
        or a
        ret z
        ld b,a
        ld hl,FIGS
.f:     push bc
        push hl
        call resd
        call ensure
        pop hl
        pop bc
        ld a,(V_OVF)
        or a
        ret nz
        inc l
        inc l
        inc l
        inc l
        djnz .f
        ret

; HL = figure record -> E = frame, D = high RES, or high RESF for a hit flash (flags bit 1)
resd:   ld e,(hl)
        ld d,high RES
        push hl
        inc l
        inc l
        inc l
        ld a,(hl)
        pop hl
        and 2
        ret z                   ; no hit flash
        ld d,high BLINK         ; a blinking figure shows its normal shape on odd renders
        ld a,(de)
        ld d,high RES
        or a
        jr z,.f
        ld a,(V_BLK)
        rra
        ret c
.f:     ld d,high RESF
        ret

; DE = residency entry (resd): upload the shape's patterns unless resident (or no shape)
ensure: ld a,(de)
        or a
        ret nz
        call sdir
        ld a,(hl)
        cp 0xFF
        ret z
        ld c,a                  ; page and first of the normal shape
        inc hl
        ld a,(hl)
        and 0x3F
        ld b,a
        inc hl
        ld a,d
        cp high RESF
        jr nz,.pg
        push hl                 ; the silhouette shape: page and first from FDIR
        ld l,e
        ld h,0
        add hl,hl
        ld a,h
        add a,high FDIR
        ld h,a
        ld c,(hl)
        inc hl
        ld b,(hl)
        pop hl
.pg:    ld a,b
        ld (V_PAT),a            ; first pattern in the page
        ld a,c
        add a,PAT0
        nextreg 0x51,a          ; its page at 0x2000
        ld c,(hl)               ; cols
        inc hl
        ld b,(hl)               ; rows
        xor a
.m:     add a,c
        djnz .m
        ld c,a                  ; C = patterns
        ld a,(V_NEXT)
        add a,c
        cp NSPR+1
        jr nc,.ovf
        ld b,a                  ; new V_NEXT
        ld a,(V_NEXT)
        inc a
        ld (de),a               ; RES = first + 1
        dec a
        srl a                   ; 4-bit pattern N -> slot N/2, bit 7 = N&1
        jr nc,.e
        or 0x80
.e:     push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld a,b
        ld (V_NEXT),a
        ld a,(V_PAT)
        ld h,a
        ld l,0
        srl h
        rr l                    ; HL = first * 128
        ld a,h
        add a,0x20
        ld h,a
        ld b,c
.u:     push bc
        ld bc,0x805B            ; 128 bytes to the pattern port
        otir
        pop bc
        djnz .u
        ret
.ovf:   ld a,1
        ld (V_OVF),a
        ret

; sprites for every recorded figure whose shape is resident, in plot order (later = in front)
emit:   xor a
        ld (V_S),a
        ld a,(V_N)
        or a
        ret z
        ld b,a
        ld hl,FIGS
.f:     push bc
        push hl
        call fig1
        pop hl
        pop bc
        inc l
        inc l
        inc l
        inc l
        djnz .f
        ret

; HL = figure record
fig1:   call resd
        ld a,(de)
        or a
        ret z                   ; no shape: the figure stays on the ULA
        dec a
        ld (V_PAT),a
        inc l
        ld a,(hl)
        ld (V_FX),a
        inc l
        ld a,(hl)
        ld (V_FY),a
        inc l
        ld a,(hl)
        ld (V_FF),a
        ld c,0                  ; palette offset (none: the hit flash has its own shape)
        call sdir
        inc hl
        ld a,(hl)
        and 0x80
        ld (V_FAC),a            ; facing of the stored graphic (bit 7)
        inc hl
        ld a,(hl)
        ld (V_COLS),a
        inc hl
        ld a,(hl)
        ld (V_ROWS),a
        inc hl
        ld a,(hl)
        ld (V_DX),a
        inc hl
        ld a,(hl)
        ld (V_DY),a
        inc hl
        ld a,(hl)
        ld (V_PADS),a
        inc hl                  ; HL -> mdx
        ld a,(V_FAC)
        ld b,a
        ld a,(V_FF)
        xor b
        rlca
        and 1                   ; mirror x = descriptor bit 7 xor stored facing
        jr z,.fm
        ld a,(hl)               ; mirrored: the box x the game uses then
        ld (V_DX),a
        ld a,1
.fm:    ld (V_MX),a
        add a,a
        add a,a
        add a,a
        or c
        ld c,a
        ld a,(V_FF)
        rlca
        rlca
        and 1
        ld (V_MY),a             ; mirror y = descriptor bit 6
        add a,a
        add a,a
        or c
        ld (V_ATTR2),a
        ; box x = 4 * x - 88 + dx - (mirror x ? pad x : 0)   (screen = buffer + 8, sprite = screen + 32)
        ld a,(V_FX)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,-88
        add hl,de
        ld a,(V_DX)
        ld e,a
        ld d,0
        bit 7,a
        jr z,.dx
        dec d
.dx:    add hl,de
        ld a,(V_MX)
        or a
        jr z,.nx
        ld a,(V_PADS)
        and 15
        ld e,a
        ld d,0
        or a
        sbc hl,de
.nx:    ld (V_X0),hl
        ; box y = y - 20 + dy - (mirror y ? pad y : 0)   (screen = buffer + 16)
        ld a,(V_DY)
        ld b,a
        ld a,(V_FY)
        sub 20
        add a,b
        ld b,a
        ld a,(V_MY)
        or a
        jr z,.ny
        ld a,(V_PADS)
        rrca
        rrca
        rrca
        rrca
        and 15
        ld c,a
        ld a,b
        sub c
        ld b,a
.ny:    ld a,(V_SHK)
        add a,b
        ld (V_Y0),a
        xor a
        ld (V_R),a
.row:   xor a
        ld (V_C),a
.col:   ld a,(V_S)
        cp NSPR
        ret nc
        nextreg 0x34,a
        inc a
        ld (V_S),a
        ; x = X0 + 16 * (mirror x ? cols - 1 - c : c)
        ld a,(V_MX)
        or a
        ld a,(V_C)
        jr z,.cx
        ld b,a
        ld a,(V_COLS)
        dec a
        sub b
.cx:    ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_X0)
        add hl,de
        ld a,l
        nextreg 0x35,a
        ; y = Y0 + 16 * (mirror y ? rows - 1 - r : r)
        ld a,(V_MY)
        or a
        ld a,(V_R)
        jr z,.cy
        ld b,a
        ld a,(V_ROWS)
        dec a
        sub b
.cy:    add a,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_Y0)
        add a,b
        nextreg 0x36,a
        ld a,h
        and 1
        ld b,a
        ld a,(V_ATTR2)
        or b
        nextreg 0x37,a
        ; pattern N = first + r * cols + c
        ld a,(V_COLS)
        ld b,a
        ld a,(V_R)
        ld c,a
        ld a,(V_PAT)
        inc c
        jr .rm
.rl:    add a,b
.rm:    dec c
        jr nz,.rl
        ld b,a
        ld a,(V_C)
        add a,b
        ld b,a
        srl a
        or 0xC0                 ; visible, 5th attribute byte
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca                    ; N bit 0 -> bit 6
        or 0x80                 ; 4-bit pattern
        nextreg 0x39,a
        ld a,(V_COLS)
        ld b,a
        ld a,(V_C)
        inc a
        ld (V_C),a
        cp b
        jp c,.col
        ld a,(V_ROWS)
        ld b,a
        ld a,(V_R)
        inc a
        ld (V_R),a
        cp b
        jp c,.row
        ret

; Layer 2 = the map at HL (G_MAP for a new screen, ZMAP to clear). (1) every cell in the old or the
; new map becomes transparent; (2a) every foreground cell that is not a bush is drawn whole, as the
; original hides figures (pillars, masonry, grass); (2b) bushes (bright green ink, attribute & 0x47 =
; 0x44): per pixel line, every run of bush cells is drawn from its leftmost to its rightmost ink pixel,
; the rest stays transparent: solid silhouettes whose edges follow the leaves, not the cells. Ink in
; the cell's ink colour, paper in its paper colour, all with the priority bit (host's rules,
; 2026-10-13); (3) the window's top frame line (y 14, x 6-249) is drawn whole in bright blue except
; where a panel icon has a pixel (ZMAP: cleared). Then OLDMAP = the map.
l2map:  ld (V_NEW),hl
        xor a                   ; (1) clear old and new cells
        ld (V_R),a
.crow:  call l2page
        xor a
        ld (V_C),a
.ccol:  call mapbit             ; C = bit, E = byte offset
        ld hl,(V_NEW)
        ld d,0
        add hl,de
        ld a,(hl)
        ld hl,OLDMAP
        add hl,de
        or (hl)
        ld hl,OLDROPE
        add hl,de
        or (hl)
        and c
        jr z,.cnext
        call cellxy             ; HL = Layer 2 address of the cell
        ld b,8
.cl:    push bc
        ld b,8
.cp:    ld (hl),TRANSP
        inc l
        djnz .cp
        ld a,l
        sub 8
        ld l,a
        inc h
        pop bc
        djnz .cl
.cnext: ld a,(V_C)
        inc a
        ld (V_C),a
        cp 30
        jr c,.ccol
        ld a,(V_R)
        inc a
        ld (V_R),a
        cp 14
        jr c,.crow
        ld hl,ZMAP              ; the old rope cells are cleared: forget them
        ld de,OLDROPE
        ld bc,56
        ldir
        xor a                   ; (2a) whole cells, every foreground cell but bushes; ropes
                                ; on the other cells
        ld (V_R),a
.wrow:  call l2page
        call rattr
        ld a,(V_R)              ; buffer row: G_BUF + r * 240
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        or a
        sbc hl,de               ; * 15
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; * 240
        ld de,G_BUF
        add hl,de
        ld (V_RSRC),hl
        xor a
        ld (V_C),a
.wcol:  call fgk
        or a
        jr nz,.wfg
        call ropec              ; not foreground: a wall rope cell goes under the sprites
        jr .wnext
.wfg:   cp 1
        jr nz,.wnext
        ld a,(hl)               ; HL = the cell's attribute
        ld e,a
        and 7
        bit 6,e
        jr z,.wi
        or 8
.wi:    add a,L2COL
        ld (V_INK),a
        ld a,e
        rrca
        rrca
        rrca
        and 7
        bit 6,e
        jr z,.wp
        or 8
.wp:    add a,L2COL
        ld (V_PAP),a
        call cellxy
        ex de,hl                ; DE = Layer 2 address of the cell
        ld hl,(V_RSRC)
        ld a,(V_C)
        add a,l
        ld l,a
        jr nc,.ws
        inc h
.ws:    call cell8              ; HL = the cell's first source byte
.wnext: ld a,(V_C)
        inc a
        ld (V_C),a
        cp 30
        jr c,.wcol
        ld a,(V_R)
        inc a
        ld (V_R),a
        cp 14
        jp c,.wrow
        xor a                   ; (2w) bush and fix cells of a screen in the table: copied whole (the
        ld (V_BW),a             ; host's bushes with priority, see-through pixels = the wall without it;
                                ; fix cells without priority, build/fix_cells.py)
        ld hl,(V_NEW)
        ld a,l
        cp low ZMAP
        jr z,.nobw
        ld a,(G_MODE)
        cp 64
        jr nc,.nobw
        nextreg 0x52,BWPAGE     ; slot 2 (the ULA reads bank 5 directly; restored below)
        ld l,a
        ld h,0x40
        ld a,(hl)               ; the screen's page (0 = none) ...
        or a
        jr z,.nobw
        ld b,a
        ld a,l
        add a,a
        add a,0x40
        ld l,a
        ld e,(hl)               ; ... and its offset in that page (0x4040 + 2 * screen)
        inc l
        ld d,(hl)
        ld a,b
        nextreg 0x52,a
        inc a                   ; a block may run on into the next page: slot 3 (2026-10-31: the
        nextreg 0x53,a          ; windows made screens 2 and 3 longer than a page; restored below)
        ld a,1
        ld (V_BW),a
        ld hl,0x4000
        add hl,de
        ld b,(hl)
        inc hl
.bwl:   push bc
        ld a,(hl)
        ld (V_R),a
        inc hl
        ld a,(hl)
        ld (V_C),a
        inc hl
        push hl
        call mapbit             ; mark the cell in OLDROPE: a table cell that is not foreground
        ld hl,OLDROPE           ; (fix cells, 2026-10-13) is cleared at the next rebuild too
        ld d,0
        add hl,de
        ld a,(hl)
        or c
        ld (hl),a
        call l2page
        call cellxy
        ex de,hl                ; DE = Layer 2 address of the cell
        pop hl
        ld b,8
.bwr:   push bc
        ld bc,8
        ldir
        ld a,e
        sub 8
        ld e,a
        inc d
        pop bc
        djnz .bwr
        pop bc
        djnz .bwl
.nobw:  nextreg 0x52,10
        nextreg 0x53,11
        ld a,(V_BW)
        or a
        jp nz,.frame
        xor a                   ; (2b) the bush runs, line by line (screens not in the table)
        ld (V_R),a
.row:   call l2page
        call rattr
        xor a
        ld (V_LN),a
.line:  ld a,(V_R)              ; source line = G_BUF + (r * 8 + line) * 30
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_LN)
        add a,b
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        or a
        sbc hl,de               ; * 15
        add hl,hl               ; * 30
        ld de,G_BUF
        add hl,de
        ld (V_RSRC),hl
        ld a,(V_LY)             ; Layer 2 line address: 0x2000 + (y & 31) * 256 + 8
        ld b,a
        ld a,(V_LN)
        add a,b
        and 31
        add a,0x20
        ld h,a
        ld l,8
        ld (V_LDST),hl
        xor a
        ld (V_C),a
.seek:  ld a,(V_C)              ; next run of bush cells
        cp 30
        jp nc,.lnext
        call fgk
        cp 2
        jr z,.run
        ld hl,V_C
        inc (hl)
        jr .seek
.run:   ld a,(V_C)
        ld (V_C0),a
.rend:  ld hl,V_C
        inc (hl)
        ld a,(hl)
        cp 30
        jr nc,.rdone
        call fgk
        cp 2
        jr z,.rend
.rdone: ld a,(V_C)
        dec a
        ld (V_C1),a
        ld a,(V_C0)             ; leftmost ink pixel: first non-zero byte from C0
        ld b,a
.lf:    call srcb
        or a
        jr nz,.lfound
        inc b
        ld a,(V_C1)
        cp b
        jr nc,.lf
        jp .seek                ; no ink on this line of the run
.lfound:ld c,0
.lz:    rlca
        jr c,.lz1
        inc c
        jr .lz
.lz1:   ld a,b
        add a,a
        add a,a
        add a,a
        add a,c
        ld (V_XL),a
        ld a,(V_C1)             ; rightmost ink pixel: last non-zero byte back from C1
        ld b,a
.rf:    call srcb
        or a
        jr nz,.rfound
        dec b
        jr .rf
.rfound:ld c,7
.rz:    rrca
        jr c,.rz1
        dec c
        jr .rz
.rz1:   ld a,b
        add a,a
        add a,a
        add a,a
        add a,c
        ld (V_XR),a
        ld a,(V_XL)             ; draw x = XL .. XR
        ld (V_X),a
.px:    ld a,(V_X)
        rrca
        rrca
        rrca
        and 31
        ld b,a                  ; cell column
        call srcb
        ld e,a                  ; source byte
        ld a,(V_X)
        and 7
        inc a
        ld d,a
        ld a,e
.sh:    rlca
        dec d
        jr nz,.sh               ; carry = the pixel
        push af
        ld hl,(V_RATT)          ; attribute of (r, column)
        ld e,b
        ld d,0
        add hl,de
        ld e,(hl)
        pop af
        ld a,e
        jr c,.ink
        rrca
        rrca
        rrca
.ink:   and 7
        bit 6,e
        jr z,.nb
        or 8
.nb:    add a,L2COL
        ld e,a
        ld hl,(V_LDST)
        ld a,(V_X)
        add a,l
        ld l,a
        ld (hl),e
        ld a,(V_X)
        ld hl,V_XR
        cp (hl)
        jp nc,.seek             ; run done (V_C is already past it)
        inc a
        ld (V_X),a
        jr .px
.lnext: ld a,(V_LN)
        inc a
        ld (V_LN),a
        cp 8
        jp c,.line
        ld a,(V_R)
        inc a
        ld (V_R),a
        cp 14
        jp c,.row
.frame: nextreg 0x51,L2PAGE     ; (3) frame line: y 14 = 0x2E00 in the first page
        ld hl,0x2E06
.fl:    ld a,l                  ; screen byte at (x = L, 14): 0x4620 + x / 8
        rrca
        rrca
        rrca
        and 31
        ld e,a
        ld d,0x46
        ld a,e
        add a,0x20
        ld e,a
        ld a,(de)
        ld c,a
        ld a,l
        and 7
        inc a
.fs:    rlc c
        dec a
        jr nz,.fs
        jr nc,.fw               ; no pixel: draw the line
        ld a,e                  ; a pixel: its attribute 0x5820 + x / 8
        ld e,a
        ld d,0x58
        ld a,(de)
        and 7
        cp 1                    ; blue ink: the line itself
        ld a,TRANSP
        jr nz,.fset             ; a panel icon: keep the ULA
.fw:    push hl
        ld hl,(V_NEW)
        ld a,l
        pop hl
        cp low ZMAP
        ld a,TRANSP
        jr z,.fset              ; clearing: no line
        ld a,L2COL+9            ; bright blue
.fset:  ld (hl),a
        inc l
        ld a,l
        cp 250
        jr c,.fl
        ld hl,(V_NEW)           ; Layer 2 now shows this map
        ld de,OLDMAP
        ld bc,56
        ldir
        ret

; Layer 2 page of cell row V_R at slot 1; V_LY = its first screen line (16 + r * 8)
l2page: ld a,(V_R)
        add a,a
        add a,a
        add a,a
        add a,16
        ld (V_LY),a
        rlca
        rlca
        rlca
        and 7
        add a,L2PAGE
        nextreg 0x51,a
        ret

; cell (V_R, V_C): E = map byte offset (r * 4 + c / 8), C = its bit (0x80 >> (c & 7))
mapbit: ld a,(V_R)
        add a,a
        add a,a
        ld b,a
        ld a,(V_C)
        rrca
        rrca
        rrca
        and 3
        add a,b
        ld e,a
        ld a,(V_C)
        and 7
        ld b,a
        inc b
        ld a,1
.bm:    rrca
        djnz .bm
        ld c,a
        ret

; V_RATT = attribute row of V_R: G_ATTR + r * 30
rattr:  ld a,(V_R)
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        or a
        sbc hl,de
        add hl,hl
        ld de,G_ATTR
        add hl,de
        ld (V_RATT),hl
        ret

; cell (V_R, V_C) of the map V_NEW: A = 0 not foreground, 1 foreground, 2 bush (attribute & 0x47 =
; 0x44, bright green ink); HL = its attribute (V_RATT set) when foreground
fgk:    call mapbit
        ld hl,(V_NEW)
        ld d,0
        add hl,de
        ld a,(hl)
        and c
        ret z
        ld hl,(V_RATT)
        ld a,(V_C)
        ld e,a
        add hl,de
        ld a,(hl)
        and 0x47
        cp 0x44
        ld a,1
        ret nz
        inc a
        ret

; Wall rope (host, 2026-10-13): a scenery cell holding a rope link (frame 162, x 2-5 of the cell) or
; knot (frame 161) takes one attribute, so the wall pixels beside the rope clash. Such a cell (its
; pixels under the link / knot mask equal the rope's) goes into Layer 2 without priority (under the
; sprites): rope pixels in its own colours, the other pixels in the left neighbour's colours (x 0-3)
; or the right neighbour's (x 4-7). Cell (V_R, V_C), V_RSRC = buffer row, V_RATT = attribute row.
ropec:  ld hl,(V_NEW)           ; clearing: no rope
        ld a,l
        cp low ZMAP
        ret z
        ld hl,(V_RSRC)
        ld a,(V_C)
        add a,l
        ld l,a
        jr nc,.s
        inc h
.s:     push hl                 ; the cell's first source byte
        ld de,LINKT
        call rmatch
        jr z,.yes
        pop hl
        push hl
        ld de,KNOTT
        call rmatch
.yes:   pop hl
        ret nz
        push hl
        ld hl,(V_RATT)          ; colours: its own, left, right
        ld a,(V_C)
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        call acol
        ld (V_INK),bc
        push hl
        ld a,(V_C)
        or a
        jr z,.l0
        dec hl
.l0:    ld a,(hl)
        call acol
        ld (V_LI),bc
        pop hl
        ld a,(V_C)
        cp 29
        jr z,.r0
        inc hl
.r0:    ld a,(hl)
        call acol
        ld (V_RI),bc
        call mapbit             ; remembered for the next clear
        ld hl,OLDROPE
        ld d,0
        add hl,de
        ld a,(hl)
        or c
        ld (hl),a
        call cellxy
        ex de,hl                ; DE = Layer 2 address
        pop hl                  ; HL = source
        ld b,8
.ln:    push bc
        push hl
        ld c,(hl)               ; pixels
        ld hl,(V_RT)
        ld a,(hl)               ; mask row
        inc hl
        ld (V_RT),hl
        ld h,a
        ld b,8
.px:    rl h                    ; carry = rope pixel
        jr nc,.wall
        ld a,(V_INK)
        rl c
        jr c,.put
        ld a,(V_PAP)
        jr .put
.wall:  ld a,b
        cp 5                    ; B 8..5 = x 0..3: the left neighbour
        jr c,.right
        ld a,(V_LI)
        rl c
        jr c,.put
        ld a,(V_LP)
        jr .put
.right: ld a,(V_RI)
        rl c
        jr c,.put
        ld a,(V_RP)
.put:   ld (de),a
        inc e
        djnz .px
        ld a,e
        sub 8
        ld e,a
        inc d
        pop hl
        ld bc,30
        add hl,bc
        pop bc
        djnz .ln
        ret

; Z = the 8 bytes at HL (stride 30) masked with the table at DE equal its ink rows; V_RT = DE
rmatch: ld (V_RT),de
        ld b,8
.m:     ld a,(de)
        and (hl)
        ld c,a
        ld a,e
        add a,8
        ld e,a
        ld a,(de)
        cp c
        ret nz
        ld a,e
        sub 7
        ld e,a
        push bc
        ld bc,30
        add hl,bc
        pop bc
        djnz .m
        xor a                   ; Z: all 8 rows matched
        ret

; attribute A -> C = ink, B = paper (Layer 2 indices without priority)
acol:   ld e,a
        and 7
        bit 6,e
        jr z,.i
        or 8
.i:     add a,L2NP
        ld c,a
        ld a,e
        rrca
        rrca
        rrca
        and 7
        bit 6,e
        jr z,.p
        or 8
.p:     add a,L2NP
        ld b,a
        ret

        ALIGN 16                ; mask rows, then ink rows (no 256-byte crossing)
LINKT:  db 0x3C,0x3C,0x3C,0x3C,0x3C,0x3C,0x3C,0x3C, 0x10,0x08,0x18,0x18,0x10,0x08,0x18,0x18
KNOTT:  db 0x3C,0x3C,0xFF,0xFF,0xFF,0xFF,0xFC,0xFC, 0x10,0x08,0x18,0x1E,0x2E,0x70,0x18,0x18

; one cell into Layer 2: HL = first source byte (stride 30), DE = Layer 2 address, V_INK / V_PAP
cell8:  ld b,8
.ln:    push bc
        ld c,(hl)
        ld b,8
.px:    ld a,(V_INK)
        rl c
        jr c,.set
        ld a,(V_PAP)
.set:   ld (de),a
        inc e
        djnz .px
        ld a,e
        sub 8
        ld e,a
        inc d
        ld bc,30
        add hl,bc
        pop bc
        djnz .ln
        ret

; HL = Layer 2 address of cell (V_R, V_C) (V_LY from l2page)
cellxy: ld a,(V_LY)
        and 31
        add a,0x20
        ld h,a
        ld a,(V_C)
        add a,a
        add a,a
        add a,a
        add a,8
        ld l,a
        ret

; A = source byte of column B on the current line (V_RSRC); keeps B
srcb:   ld hl,(V_RSRC)
        ld a,l
        add a,b
        ld l,a
        jr nc,.n
        inc h
.n:     ld a,(hl)
        ret

; 0x5DCD (e_end): the access code screen (no screen is built: the old screen's Layer 2 and sprites
; stayed over it): sprites off, Layer 2 clipped to the panel (lines 136-191) so the host's portraits
; stay (host 2026-10-31: Layer 2 off showed the ULA's portraits, with clash); the next game's first
; commit sets the whole clip again. The picture shifted out (0x5E0E) runs from here: it leaves slot 0
; and the ROM alone (checked in the simulator)
s_end:  call cnoop
        nextreg 0x15,0x00
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,136
        nextreg 0x18,191
        IF GAME_MHZ
        nextreg 0x07,0          ; fast game: 0x5E0E (the picture shifted out, timed by the CPU) at 3.5
        ENDIF                   ; MHz: as in the original it gives time to let go of the keys before
        call 0x5E0E             ; the code text, which any key leaves at once (0x5DE3; host)
        IF GAME_MHZ
        nextreg 0x07,GAME_MHZ
        ENDIF
        jp x_end

        IF MULTI
; ---- title menu items 5 and 6 (host, 2026-10-31; make_nex.py --multi, build/texts_all.py) ----
; Page STOREPG is mapped at slot 1 with interrupts off (the ISR hooks set slot 1 back to ROM).
; 0x5FFD (e_mprt): the menu as the original prints it (B items from HL = the language's list in the
; alt ROM via 0x5FFA), then the state of item 5 as an item of its own (V_STW: "OFF" / "ON " in the
; language, in the game's RAM). The game's print routines leave slot 0 alone, so this runs from here;
; the lists and the glyphs are in the alt ROM's upper half (slot 1)
s_mprt: call 0x5FF0
.l:     push bc
        call 0x6008
        pop bc
        djnz .l
        ld hl,(V_STW)
        call 0x6008
        jp x_mprt

; item 5: COLOR ON <-> OFF: that colouring's shape directories and sprite palette, nothing resident
s_col:  ld (V_SP),sp
        ld sp,STK1
        ld a,i                  ; P/V = IFF2
        di
        push af
        nextreg 0x51,STOREPG
        ld a,(V_COL)
        xor 1
        ld (V_COL),a
        call setcol
        call setstw
        nextreg 0x51,0xFF
        pop af
        ld sp,(V_SP)
        jp po,s_mprt            ; the menu again; its RET goes back to the menu loop
        ei
        jp s_mprt

; item 6: the next language (V_LANG): its records into the game's texts (the menu pointer 0x5FFA is
; one of them)
s_lang: ld (V_SP),sp
        ld sp,STK1
        ld a,i
        di
        push af
        nextreg 0x51,STOREPG
        ld a,(V_LANG)
        inc a
        cp 3
        jr c,.l
        xor a
.l:     ld (V_LANG),a
        add a,a
        ld l,a
        ld h,0
        ld de,0x2000+ST_LANG
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
.r:     ld e,(hl)               ; DE = address, 0 = end
        inc hl
        ld d,(hl)
        inc hl
        ld a,d
        or e
        jr z,.end
        ld c,(hl)
        inc hl
        ld b,0
        ldir
        jr .r
.end:   call setstw
        nextreg 0x51,0xFF
        pop af
        ld sp,(V_SP)
        jp po,.p
        ei
.p:     ld hl,0x4000            ; the title screen holds text only: wipe its pixels (not the
        ld de,0x4001            ; attributes) and print it again in the new language
        ld bc,0x17FF
        ld (hl),l
        ldir
        call 0x5FE9             ; credits and the title line
        jp s_mprt

; the shape directories and the sprite palette of V_COL (STOREPG at slot 1); no shape resident
setcol: ld hl,0x2000
        ld a,(V_COL)
        or a
        jr z,.c
        ld hl,0x2000+ST_COL
.c:     push hl
        ld de,SDIR
        ld bc,220*8
        ldir
        pop hl
        push hl
        ld de,0x0700
        add hl,de
        ld de,FDIR
        ld bc,220*2
        ldir
        pop hl
        ld de,0x08C0
        add hl,de
        nextreg 0x43,0x20       ; sprite palette 0 from index 0, as the setup
        nextreg 0x40,0
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x43,0x00
        jp flush

; V_STW = the state word item for V_LANG and V_COL (STOREPG at slot 1)
setstw: ld a,(V_LANG)
        add a,a
        ld hl,V_COL
        add a,(hl)
        add a,a
        ld l,a
        ld h,0
        ld de,0x2000+ST_STW
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (V_STW),hl
        ret

; ---- the pause's sword (host, 2026-10-31; build/pause_sword.py, sheet gfx/pause_sword.png) ----
; 0xA621 (e_swd): the pause window's item 4 (shown when 0xE634 is not 0) printed the sword's glyphs
; 0x2A 0x2B (string 0xE926), then its price (0xE92B). Now the price only, and the sword is sprite 0 with
; pattern 127 (swpat: 16x16, black opaque) in the box SW_X, SW_Y: the sprites clipped to that box,
; sprite 0 on top (the figures' sprites stay hidden behind it), the host's grey and browns in sprite
; palette slots 2-4 (COLOR OFF too). All back at the pause's end (e_swx), or at the next commit when the
; pause was left without its RET (V_SWD); that commit's hide takes sprite 0 away (V_PREV >= 1)
s_swd:  call 0xE91F             ; C: the item is shown
        jr nc,.no
        call swon
        ld hl,0xE92B            ; the price only
        call 0xA30C
        jp x_mprt
.no:    call swoff              ; (the window drawn again without the item)
        or a                    ; NC, as the original's RET NC
        jp x_mprt

s_swx:  push af                 ; the pause's NC / C and registers for its caller
        call swoff
        push bc
        push de
        push hl
        ld hl,psave             ; the dragon's record (or the list itself) as it was
        ld de,PLIST
        ld bc,PLEN
        ldir
        pop hl
        pop de
        pop bc
        pop af
        jp x_mprt

; the pause window's draw list 0xE8B2 (0xA501 draws the frame and the background from it): the game's
; dragon (screen 34) uses 0xE8B2 as an object record (0x7A82 LD (IX+4),L with IX 0xE8B2) and leaves its
; script pointer 0x80A2 at 0xE8B6, so every later pause window drew its frame and background from the
; game's code (stripes; host 2026-10-31; an original bug, trueno1.rzx frame 48898). The window is drawn
; from the original bytes (plist, checked by make_nex against the snapshot), the record's go back after
s_pwin: push af
        push bc
        push de
        push hl
        ld hl,PLIST
        ld de,psave
        ld bc,PLEN
        ldir
        ld hl,plist
        ld de,PLIST
        ld bc,PLEN
        ldir
        pop hl
        pop de
        pop bc
        pop af
        jp x_mprt

plist:  DB 0x28,0x18,0x17,0x48,0x00,0x2A,0x1A,0xB4,0x01,0x00,0x2A,0x5D
        DB 0xB4,0x01,0x00,0x2A,0x1A,0x01,0x44,0x00,0xDD,0x1A,0x01,0x44
psave:  DS PLEN

swon:   ld a,i                  ; P/V = IFF2
        di
        push af
        ld a,1
        ld (V_SWD),a
        nextreg 0x43,0x20       ; sprite palette 0: the host's grey and two browns in slots 2-4
        nextreg 0x40,2
        nextreg 0x41,0x49
        nextreg 0x41,0x68
        nextreg 0x41,0x44
        nextreg 0x43,0x00
        call flush              ; pattern 127 is the sword's now: no shape resident
        ld bc,0x303B
        ld a,0x80+63            ; 4-bit pattern 127 = slot 63, its second half
        out (c),a
        ld hl,swpat
        ld bc,0x805B            ; 128 bytes to the pattern port
        otir
        nextreg 0x34,0
        nextreg 0x35,32+SW_X
        nextreg 0x36,32+SW_Y
        nextreg 0x37,0
        nextreg 0x38,0xC0+63    ; visible, 5th attribute byte, slot 63
        nextreg 0x39,0xC0       ; 4-bit pattern, the slot's second half
        ld a,(V_PREV)           ; the next commit hides sprite 0 unless a figure takes it
        or a
        jr nz,.c
        inc a
        ld (V_PREV),a
.c:     nextreg 0x1C,2          ; sprite clip: the sword's box only
        nextreg 0x19,SW_X
        nextreg 0x19,SW_X+15
        nextreg 0x19,SW_Y
        nextreg 0x19,SW_Y+15
        nextreg 0x15,0x41       ; sprites on, sprite 0 on top, order S L U
        pop af
        ret po
        ei
        ret

swoff:  ld a,i
        di
        push af
        xor a
        ld (V_SWD),a
        nextreg 0x34,0          ; sprite 0 hidden
        nextreg 0x38,0
        nextreg 0x15,0x00       ; sprites off (the pause; its end or the commit turns them on)
        nextreg 0x1C,2          ; sprite clip: the play window again (as the setup)
        nextreg 0x19,8
        nextreg 0x19,247
        nextreg 0x19,16
        nextreg 0x19,127
        ld a,(V_COL)            ; COLOR OFF: slots 2-4 normal blue, red, magenta again
        or a
        jr nz,.on
        nextreg 0x43,0x20
        nextreg 0x40,2
        nextreg 0x41,0x02
        nextreg 0x41,0xA0
        nextreg 0x41,0xA2
        nextreg 0x43,0x00
.on:    pop af
        ret po
        ei
        ret

swpat:  DS 128                  ; the sword's pattern (make_nex.py, from the host's sheet)
        ENDIF
code_end:

; ---- setup (stub bank, 0xD000): palettes, transparency, sprites hidden, clip, Layer 2 on ----
        ORG 0xD000
setup:  call title              ; the start-up title (host, 2026-10-17)
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,spal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x43,0x10       ; Layer 2 palette 0: 16 priority colours from L2COL, 16 plain from L2NP,
        nextreg 0x40,L2COL      ; the two greys at L2GREY
        ld hl,lpal
        ld b,68
.q:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .q
        nextreg 0x43,0x00
        nextreg 0x4B,0          ; sprite index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSPR
        jr nz,.h
        nextreg 0x1C,2          ; sprite clip = the play window (screen x 8-247, y 16-127)
        nextreg 0x19,8
        nextreg 0x19,247
        nextreg 0x19,16
        nextreg 0x19,127
        ld a,L2PAGE             ; Layer 2 transparent (not stored in the .nex: 48K of one byte)
.l2:    nextreg 0x52,a
        ld hl,0x4000
        ld (hl),TRANSP
        ld de,0x4001
        ld bc,8191
        ldir
        inc a
        cp L2PAGE+6
        jr nz,.l2
        nextreg 0x52,10
        nextreg 0x61,0          ; the copper list (clist), restarted every frame
        nextreg 0x62,0
        ld hl,clist
        ld b,CL_LEN
.cu:    ld a,(hl)
        nextreg 0x60,a
        inc hl
        djnz .cu
        nextreg 0x61,0
        nextreg 0x62,0xC0
        nextreg 0x12,L2BANK
        nextreg 0x7F,0
        ld bc,0x123B
        ld a,2                  ; Layer 2 visible
        out (c),a
        nextreg 0x15,0x01       ; sprites on, order S L U
        ret
; ---- start-up title (host, 2026-10-17): the loading screen without clash, until a key or 10 s ----
; The .nex holds the clash picture in bank 5's screen (make_nex.py), so it is on the screen as soon as
; the loader has bank 5 (the first one), not the game's menu. Bank TITLE_D (build/title.py, pages
; TITLE_D*2, +1) holds the game's menu screen, the fade table and the cells that differ in the
; no-clash picture (Layer 2 patches). The ULA picture is expanded into the title's own Layer 2 (banks
; TITLE_L2..+2, through slot 0), the patches go over it, the picture is shown with the second Layer 2
; palette (16 Spectrum colours) and faded out through that palette; then the menu screen goes back.
; Called with DI and the stack in the stub page; slots 0, 1 and 3 are borrowed and given back.
TITLE_L2 EQU 34                 ; banks 34-36 = pages 68-73 (title.py TPAGE)
TITLE_D  EQU 37                 ; page 74: menu screen at 0x6000, fade at 0x7B00; page 75: patches
title:  ld bc,0x243B            ; machine ID (NextReg 0x00): 0 only in the toolkit's boot simulation,
        xor a                   ; which has no raster or keyboard to leave the title with: no title
        out (c),a
        inc b
        in a,(c)
        or a
        ret z
        push ix
        ld bc,0x2F3B            ; MAME's nextfaststart plugin: 0 = normal speed (host); not a Next port
        xor a
        out (c),a
        ld bc,0x123B            ; Layer 2 hidden while it is built: only the ULA picture is seen (host)
        xor a
        out (c),a
        ld bc,0x243B            ; slots 0 and 1 as they are (ROM)
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        ld (T_S0),a
        dec b
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        ld (T_S1),a
        nextreg 0x07,3          ; 28 MHz for the expansion
        nextreg 0x53,TITLE_D*2
        xor a
        ld (T_Y),a
.line:  ld a,(T_Y)
        ld e,a
        and 31
        jr nz,.same
        ld a,e                  ; a new Layer 2 page every 32 lines
        rlca
        rlca
        rlca
        and 7
        add a,TITLE_L2*2
        nextreg 0x50,a
.same:  ld a,e                  ; HL = bitmap line: 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2
        and 0x38
        rlca
        rlca
        ld l,a
        ld a,e
        and 0xC0
        rrca
        rrca
        rrca
        ld h,a
        ld a,e
        and 7
        or h
        or 0x40
        ld h,a
        ld a,e                  ; IX = attribute row: 0x7C40 + (y >> 3) * 32 (title.py; bank 5's are black)
        rrca
        rrca
        rrca
        and 31
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0x7C40
        add hl,bc
        push hl
        pop ix
        pop hl
        ld a,e                  ; DE = the Layer 2 line in slot 0
        and 31
        ld d,a
        ld e,0
.col:   ld a,(ix+0)             ; colour indices 0-7, +8 when BRIGHT
        and 0x40
        rrca
        rrca
        rrca
        ld b,a
        ld a,(ix+0)
        and 7
        or b
        ld (T_INK),a
        ld a,(ix+0)
        rrca
        rrca
        rrca
        and 7
        or b
        ld (T_PAP),a
        ld c,(hl)
        ld b,8
.px:    sla c
        ld a,(T_PAP)
        jr nc,.w
        ld a,(T_INK)
.w:     ld (de),a
        inc e
        djnz .px
        inc hl
        inc ix
        ld a,e
        or a
        jr nz,.col              ; 32 cells x 8 pixels: E wraps at the end of the line
        ld a,(T_Y)
        inc a
        ld (T_Y),a
        cp 192
        jp nz,.line
        nextreg 0x53,TITLE_D*2+1 ; the patches: count, then per line: page, address, 8 pixels
        ld hl,0x6000
        ld a,(hl)
        inc hl
        or a
        jr z,.show
        ld b,a
.pc:    push bc
        ld b,8
.pl:    ld a,(hl)
        inc hl
        nextreg 0x50,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push bc
        ld bc,8
        ldir
        pop bc
        djnz .pl
        pop bc
        djnz .pc
.show:  nextreg 0x07,0
        nextreg 0x53,TITLE_D*2
        xor a
        out (0xFE),a            ; black border while the title is up (host)
        ld hl,0x7B00            ; full colours
        call tpal
        nextreg 0x12,TITLE_L2
        nextreg 0x70,0          ; 256x192, no scroll, the whole clip window
        nextreg 0x16,0
        nextreg 0x71,0
        nextreg 0x17,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        call vsync              ; switch below the picture: the whole frame changes at once
        ld bc,0x123B
        ld a,2
        out (c),a               ; Layer 2 on (opaque over the ULA)
        ld de,500               ; 10 s at 50 Hz, the quiet wait below included
.rel:   ld b,10                 ; the key that started the .nex: 10 quiet frames in a row first
.r1:    call ttick
        jr z,.go
        call keyq
        jr nz,.rel
        djnz .r1
.wait:  ld b,3                  ; then a press counts only when held 3 frames in a row
.w1:    call ttick
        jr z,.go
        call keyq
        jr z,.wait
        djnz .w1
.go:    ld hl,0x7B00            ; fade: 9 steps (full .. black), 3 frames each
        ld b,9
.f:     push bc
        call tpal
        ld b,3
.fw:    call vsync
        djnz .fw
        pop bc
        djnz .f
        ld hl,0x6000            ; the game's menu screen back into bank 5 (Layer 2 still covers it)
        ld de,0x4000
        ld bc,6912
        ldir
        ld bc,0x123B
        xor a
        out (c),a               ; Layer 2 off; the setup puts the game's Layer 2 and palette 1 back
.rel2:  call keyq               ; the key must not reach the game's menu
        jr nz,.rel2
        ld a,(T_S0)
        nextreg 0x50,a
        ld a,(T_S1)
        nextreg 0x51,a
        nextreg 0x53,11
        nextreg 0x07,TITLE_MHZ  ; 7 MHz: the game goes on in its menu, now on the screen (host)
        pop ix
        ret

tpal:   nextreg 0x43,0x54       ; Layer 2 second palette: write it and show it
        nextreg 0x40,0
        ld b,32
.t:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .t
        ret

ttick:  call vsync              ; one title frame: Z when the time (DE frames) is out
        dec de
        ld a,d
        or e
        ret

keyq:   push bc                 ; NZ if a key or the Kempston joystick is down
        ld bc,0x00FE
        in a,(c)
        cpl
        and 0x1F
        jr nz,.k
        ld bc,0x001F
        in a,(c)
        cp 0xFF                 ; 0xFF: no Kempston port here
        jr z,.n
        and 0x1F
        jr .k
.n:     xor a
.k:     pop bc
        ret

vsync:  push bc                 ; wait for raster line 192 (NextReg 0x1F = line LSB)
        ld bc,0x243B
        ld a,0x1F
        out (c),a
        inc b
.v1:    in a,(c)
        cp 192
        jr nz,.v1
.v2:    in a,(c)
        cp 192
        jr z,.v2
        pop bc
        ret

T_Y:    db 0
T_INK:  db 0
T_PAP:  db 0
T_S0:   db 0
T_S1:   db 0

; copper (host 2026-10-17): a shaken copy moves only the window, so Layer 2 is scrolled 8 lines only
; for lines 24-135 (the window's place then): the top frame line (y 14), the top panel and the
; portraits stay; the scroll would also wrap the portrait cells (lines 184-191) to the top of the
; screen. The commit sets the three shake instructions (cshake)
clist:  db 0xC2,0x0F            ; WAIT 33,15
        db 0,0                  ; shaken: MOVE 0x69,0x00 (Layer 2 off for lines 16-23: the window
                                ; went 8 lines down, the frame line y 14 stays), else NOOP
        db 0xC2,0x17            ; WAIT 33,23
        db 0,0                  ; shaken: MOVE 0x69,0x80 (Layer 2 on), else NOOP
        db 0,0                  ; shaken: MOVE 0x17,184 (8 lines lower), else NOOP
        db 0xC2,0x87, 0x17,0    ; WAIT 33,135 / MOVE 0x17,0: the panel not scrolled
        db 0,0                  ; the pause menu: MOVE 0x69,0x80 (Layer 2 on again for the panel; it
                                ; was turned off at line 16 for the pause window), else NOOP
        db 0xFF,0xFF            ; WAIT 63,511: stop until the next frame
CL_LEN  EQU $-clist

spal:                           ; 256 sprite palette bytes, then 34 Layer 2 palette entries (9-bit pairs)
lpal    EQU spal+256

        SAVEBIN "tr_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "tr_page.bin",0x0100,code_end-0x0100
        SAVEBIN "tr_setup.bin",0xD000,spal-0xD000
