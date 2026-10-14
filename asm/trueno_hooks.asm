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
;                                                    screen, ULA only: Layer 2 and sprites off; the next
;                                                    game's first screen turns them on, 2026-10-13)
;   0x889B  21 3C F1     LD HL,0xF13C   -> JP e_att  (ISR copy, attribute source: 0xEF98, the scenery
;                                                    without figures; screen 34 (the dragon, clear mode):
;                                                    0xF13C as the original, for its energy bar drawn
;                                                    via 0x82E4 past the figure hook, 2026-10-13)
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
                                ; row, column, 64 Layer 2 bytes. Blocks are packed (2026-10-14)
L2COL   EQU 16                  ; Layer 2 palette index 16 + colour (0-7, +8 bright), priority set
L2NP    EQU 32                  ; the same colours without priority (wall ropes, under the sprites)

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
e_tk:   ld bc,0x243B            ; AF BC DE HL are dead here (task entry: LD A,(nn) / RRA / RET NC ...)
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
e_end:  nextreg 0x15,0x00       ; the access code screen (no screen is built: the old screen's
        nextreg 0x69,0x00       ; Layer 2 and sprites stayed over it). NEXTREG keeps every register
        call 0x5E0E
        jp 0x5DD0
e_att:  push af                 ; the copy's attribute source (HL', set before CALL 0x8915)
        ld hl,0xEF98
        ld a,(0xE60B)
        cp 34
        jr nz,.a
        ld hl,0xF13C
.a:     pop af
        jp 0x889E
e_mnu:  nextreg 0x15,0x00       ; pause menu (0xA36C tail-jumps to it; it returns with RET NC/C):
        nextreg 0x69,0x00       ; its window is drawn in the ULA, so hide Layer 2 and the sprites
        call 0xA501             ; while it is up. NEXTREG keeps every register and flag
        nextreg 0x69,0x80
        nextreg 0x15,0x01
        ret
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
        nextreg 0x07,3
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
.ns:    nextreg 0x17,a
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
        nextreg 0x15,0x01       ; sprites on (off since a new screen was built), order S L U
        xor a
        ld (V_N),a
        jp isrx

; ISR task entry (0x8865) with a clear request: Layer 2 and sprites off.
s_tk:   ld (V_SP2),sp
        ld sp,STK2
        nextreg 0x07,3
        nextreg 0x7F,1          ; done; rebuild at the next commit
        ld hl,ZMAP
        call l2map
        xor a
        ld (V_S),a
        call hide
        ld a,(V_SLOT0)
        nextreg 0x07,0
        nextreg 0x51,0xFF
        ld sp,(V_SP2)
        jp x_tk2

isrx:   nextreg 0x07,0
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
code_end:

; ---- setup (stub bank, 0xD000): palettes, transparency, sprites hidden, clip, Layer 2 on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,spal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x43,0x10       ; Layer 2 palette 0: 16 priority colours from L2COL, 16 plain from L2NP
        nextreg 0x40,L2COL
        ld hl,lpal
        ld b,64
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
        nextreg 0x12,L2BANK
        nextreg 0x7F,0
        ld bc,0x123B
        ld a,2                  ; Layer 2 visible
        out (c),a
        nextreg 0x15,0x01       ; sprites on, order S L U
        ret
spal:                           ; 256 sprite palette bytes, then 32 Layer 2 palette bytes (9-bit pairs)
lpal    EQU spal+256

        SAVEBIN "tr_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "tr_page.bin",0x0100,code_end-0x0100
        SAVEBIN "tr_setup.bin",0xD000,spal-0xD000
