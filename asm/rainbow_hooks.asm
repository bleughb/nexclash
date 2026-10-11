; Rainbow Islands (128K) - hardware sprites for every figure drawn by the list walker 59504.
; Entry/exit stubs live in alt ROM image 1 at 0x386E (read-only). The hook bodies, state, tables
; and canvases live in Next RAM page PAGE_S, mapped at MMU slot 0 only while a hook runs (the
; walker runs with interrupts disabled); only ROM code maps/unmaps slot 0.
; No stack use anywhere (SP points into graphics data inside the walker).
;
; Patch sites (bank 0):
;   58851  FD 21 3C 6D  LD IY,27964  (render start)  -> JP e_rs
;   59539  26 F5 DD E9  LD H,245 / JP (IX)        -> JP e_pc
;   59543  A7 C2 79 E8  AND A / JP NZ,59513       -> JP e_af
;   59087  3A E2 E5     LD A,(58850) (render end) -> JP e_re
; Collectables (2026-10-11): item cell shadow map (page 27) kept by three cell-drawer hooks:
;   60853  87 6F 26 00  ADD A,A / LD L,A / LD H,0  (base tile, A = tile)  -> JP e_bt
;   60839  3D 6F 26 00  DEC A / LD L,A / LD H,0    (full overlay >= 15)   -> JP e_ov
;   60965  3D 87 87 87  DEC A / ADD A,A x3         (masked item, A = code) -> JP e_it
;   59547  2A 82 E8     LD HL,(59522) (walker end of a band) -> JP e_bend
; DE = back-buffer cell 0x9F00 + 256*k + col (k = cell row 0-21). Render start: the visible item
; cells -> item list (page 27) + one 4-bit pattern each (page 28: item gfx + mask, ink = the cell's
; attribute-buffer ink, black outline, palette offset ITEM_PAL). After each band's blit (walker
; end 59547): that band's item pixels are cleared on the screen (screen AND mask AND NOT gfx) and
; the cell's screen attribute set to its base colour, so the square never shows. Render end: the
; same fix for every item (no-op unless a band was missed), then the item sprites are committed
; with the LOWEST sprite numbers, the figures after them (always in front).
; The walker is called once per 8-line band from inside the blit (up to 14 times a frame), so the
; piece counter is per render (58851 .. 59087), not per walker call.
;
; Each piece (one char-row band, up to 6 bytes wide) is drawn by the game's own plotter twice, at
; its real screen address but with a canvas page mapped over the screen (MMU slot 2): run 1 into
; PAGE_C1 with the window cleared (-> graphic G), run 2 into PAGE_C2 with the window = FF
; (-> mask|graphic MG). All registers end exactly as after the original plot (only AF' differs).
; Pixel: G=1 ink, MG=1&G=0 transparent, MG=0 outline. NIBTAB (built by Python) maps
; (G nibble, MG nibble) -> 2 bytes of 4-bit pixels; CLASSTAB maps gfx address high byte ->
; palette offset << 4. A piece covers columns E-2..E+5 of its start address (plotters run left or
; right, up to 6 bytes wide): 4 sprites 4n..4n+3, 4-bit patterns 4n..4n+3 (slots 2n, 2n+1).

        DEVICE ZXSPECTRUMNEXT
PAGE_S  EQU 26              ; hook code, state, tables (slot 0 during a hook)
PAGE_T  EQU 27              ; plotter layout tables (slot 1 while converting)
PAGE_C2 EQU 29              ; canvas mapped over the screen (slot 2) for the register run
STORE_PG EQU 32             ; pattern store: pages 32-63 (256K), slot 1 while looking up
NSPR_MAX EQU 128            ; sprites (= 4-bit patterns) per render
WBG     EQU 0x0D00          ; conversion buffer G (ink) by row*6+col (96 bytes)
WBM     EQU 0x0E00          ; conversion buffer MG (mask|ink)
MIRTAB  EQU 0x0F00          ; bit reversal (the plotters' table page 245)
NIBTAB  EQU 0x1000          ; (G nibble, MG nibble) -> 2 bytes of 4-bit pixels (0x1000 / 0x1100)
CLASSTAB EQU 0x1200         ; gfx address high byte -> palette offset << 4
PI      EQU 0x1300          ; plotter info by IXl, 8 pages: +0 IXh (0 = unknown), +1 off|nspr<<4,
                            ; +2 len carry 0, +3 len carry 1, +4/+5 layout ptr c0, +6/+7 layout ptr c1

V_S     EQU 0x0000          ; sprites (and patterns) used this render (0x0001 stays 0)
V_PREV  EQU 0x001E          ; V_S of the previous render
V_RUN   EQU 0x0002          ; 3 = passthrough to the ULA screen, 4 = register run on the canvas
V_TMP   EQU 0x0003          ; A after the plotter (next list code)
V_SP    EQU 0x0004          ; gfx pointer (SP at dispatch)
V_DE    EQU 0x0006          ; screen address of the piece
V_IX    EQU 0x0008
V_SP2   EQU 0x000C          ; registers after the register run
V_BC2   EQU 0x000E
V_HL2   EQU 0x0010
V_DF    EQU 0x0012
V_IY    EQU 0x0014
V_HL3   EQU 0x0016
V_VIS   EQU 0x0018          ; 3 bytes: sprite k of this piece has pixels
V_BC3   EQU 0x001C
V_OFF   EQU 0x0020          ; window start = E - off
V_NS    EQU 0x0021          ; sprites of this piece (1-3)
V_KEY   EQU 0x0022          ; AF' carry
V_LEN   EQU 0x0023          ; graphics stream length
V_FRM   EQU 0x0024          ; render counter (word)
V_ENT   EQU 0x0026          ; entry address in slot 1 (word, low byte 0)
V_EPG   EQU 0x0028          ; store page of the entry
V_HITS  EQU 0x002A          ; store hits (word, statistics only)
V_LT    EQU 0x002C          ; layout table pointer (slot 1, PAGE_T)
V_NP    EQU 0x0001          ; pieces staged this render (cleared with V_S at render start)
V_DE3   EQU 0x0030          ; render end: DE saved
V_CL    EQU 0x0032          ; commit: piece list pointer
V_CS    EQU 0x0034          ; commit: sprite number
V_TMP2  EQU 0x0035          ; commit: sprites left in this piece
CLIST   EQU 0x1B00          ; staged pieces: 3 bytes each (store page, entry high byte, nspr)
ATTRB   EQU 0x1C80          ; staged sprite attributes: 5 bytes per sprite (attr 0-4)
V_OVF   EQU 0x0036          ; overflow entries used this render (word cleared at render start)
PAGE_OVF EQU 30             ; overflow entries (never looked up): all 4 ways already in use
V_TICK  EQU 0x002E          ; interrupts since the last game frame (limiter)
LIMIT   EQU 3               ; game frame every 3rd interrupt = the original's normal pace
STK     EQU 0x0100          ; hook stack top (grows down into 0x00F0-0x00FF)
; --- collectables (item sprites)
CODES   EQU 0x3000          ; page 27 (slot 1): item code per back-buffer cell (704; 0 none, FF = ULA)
CODES_END EQU CODES+704
BATTR   EQU 0x3300          ; page 27: base tile colour per cell (bit 7 = known)
EXP     EQU 0x1F00          ; page 26: nibble -> 2 bytes of 4-bit pixels, F where the bit is set
ILIST   EQU 0x3600          ; page 27: item list, 16 bytes per item: +0 col, +1 Y0, +2 visible rows,
                            ; +3 gfx low, +4 attr char row (FF none), +5 base colour, +6/+7 attribute-
                            ; buffer address, +8/+9 first/last char row of its visible rows, +10 ink,
                            ; +11 pattern entry, +12/+13 screen address of the first visible row,
                            ; +14 first visible row j0, +15 visible rows n (rows j0..j0+n-1)
PKEYS   EQU 0x3E00          ; page 27: pattern cache keys, 128 x (gfx low, ink, visible rows, stamp);
                            ; the pattern of entry e is in page 28 at 0x2000 + 64*e
IMAX    EQU 80              ; items per render (more: left on the ULA as drawn)
RCNT    EQU 0x3D00          ; page 27: occupied cells (item or FF) per cell row k (22 bytes)
GCOPY   EQU 0x3C00          ; page 27: copy of the item graphics 0xF600-0xF6DF (224 bytes); when
                            ; they change, every pattern cache entry is invalidated
IPAGE   EQU 28              ; item pattern cache, 64 bytes each at 0x2000 + 64*e (slot 1)
ITEM_PAL EQU 0xF0           ; palette offset 15 << 4: Spectrum ink colours (Python: Config.palette)
V_IA    EQU 0x0038          ; cell hooks: A at entry
V_IBC   EQU 0x0039          ; cell hooks: BC
V_NI    EQU 0x003B          ; render end: item sprites this render (sprites 0..NI-1)
V_IP    EQU 0x003C          ; render end: next free pattern (figures use 0..V_S-1)
V_SP3   EQU 0x003D          ; render end: game SP
V_IS    EQU 0x003F          ; (48782) = back-buffer row at the top of the play area
V_IN    EQU 0x0040          ; (58850) = play-area rows drawn
V_IYU   EQU 0x0041          ; item: (8k - s) mod 176
V_IK    EQU 0x0042          ; item: cell row k
V_IC    EQU 0x0043          ; item: column
V_IG    EQU 0x0044          ; item: gfx+mask pointer (word)
V_IINK  EQU 0x0046          ; item: ink pixel index
V_IHL   EQU 0x0047          ; item: CODES pointer (word)
V_IVIS  EQU 0x0049          ; item: visible rows (bit 7 = row 0)
V_ICODE EQU 0x004A          ; item: code
V_IYS   EQU 0x004B          ; item: sprite row offset (y, or y-176 when wrapped to the top)
V_IROW  EQU 0x004C          ; item: row counter
V_ISC   EQU 0x004D          ; item: screen row of the current pattern row
V_ICY   EQU 0x004E          ; s_ov: carry at entry (DEC A keeps it)
V_IHL2  EQU 0x004F          ; s_it: HL at entry (live until 60970)
V_FMAX  EQU 0x0051          ; figure sprites allowed this render = 128 - items (Python sets 128)
V_BR    EQU 0x0052          ; ifix: char row to fix (FF = all)
V_IREC  EQU 0x0053          ; item record pointer (word)
V_ICNT  EQU 0x0055          ; items left
V_SP4   EQU 0x0056          ; render start / band hook: game SP (word)
V_IA2   EQU 0x0058          ; ifix: Y of the current row
V_IAB   EQU 0x0059          ; ibrec: attribute-buffer address (word)
V_IROWS EQU 0x005B          ; ibrec: first / last char row of the visible rows (2 bytes)
V_IAR   EQU 0x005D          ; ibrec: attribute char row
V_IBAS  EQU 0x005E          ; ibrec: base colour
RFIRST  EQU 0x0060          ; 24 bytes: first item touching screen char row R this render (FF none)
RLAST   EQU 0x0078          ; 24 bytes: last item touching it (items are in cell-row order)
V_IE    EQU 0x0090          ; ibrec: pattern entry
V_IJ0   EQU 0x0091          ; ibrec: first visible row, V_IJ0+1 = visible rows
V_PH    EQU 0x0093          ; pattern cache: hash
V_IKEY  EQU 0x0094          ; pattern cache: key (gfx low, ink, vis) 3 bytes
V_IDIRTY EQU 0x0097         ; a cell hook changed an occupied cell since the last item list
V_LS    EQU 0x0098          ; (48782) and (58850) of the last item list
V_LN    EQU 0x0099
EPAT    EQU 0x0D60          ; commit: pattern number of cache entry e this render (128 bytes)
ESTAMP  EQU 0x0E60          ; commit: 1 = EPAT[e] uploaded this render (cleared per commit, 128 bytes)
CODE2   EQU 0x1F20          ; second code block (page 26, up to 0x1FFF)

        ORG 0x386E
e_rs:   nextreg 0x50,PAGE_S
        jp s_rs
e_re:   nextreg 0x50,PAGE_S
        jp s_re
e_pc:   nextreg 0x50,PAGE_S
        jp s_pc
e_af:   jp s_af                     ; slot 0 is still mapped (plotter run started by the hook)
x_rs:   nextreg 0x50,0xFF
        jp 58855
x_re:   nextreg 0x50,0xFF
        jp 59090
x_cont: nextreg 0x50,0xFF
        and a
        jp nz,59513
        jp 59547
; frame limiter + turbo. The whole game frame runs inside the IM2 handler (65171: PUSH AF /
; LD A,(48768) ...; exit 65274: POP AF / EI / RET). Original: one frame per 3 interrupts (4 when
; busy: the frame overran). Here: the frame runs at 28 MHz, once every LIMIT interrupts.
e_lim:  nextreg 0x50,PAGE_S         ; site 65172 (LD A,(48768)): AF is already pushed
        jp s_lim
x_lrun: nextreg 0x50,0xFF
        ld a,(48768)
        jp 65175
x_lskip:
        nextreg 0x50,0xFF
        jp 65274
e_off1: nextreg 0x15,0              ; site 65076 CALL 23643 (play state ended: death, continue,
        jp 23643                    ; round end, game over): sprites off until the next commit
e_off2: nextreg 0x15,0              ; site 65029 CALL 23698 (main loop (re)start)
        jp 23698
e_hx:   nextreg 0x07,0              ; site 65274 (POP AF / EI / RET): back to 3.5 MHz for the
        pop af                      ; main loop (its timing stays the original's)
        ei
        ret
e_bt:   nextreg 0x50,PAGE_S         ; site 60853: base tile into a back-buffer cell
        jp s_bt
e_ov:   nextreg 0x50,PAGE_S         ; site 60839: full overlay tile (code >= 15)
        jp s_ov
e_it:   nextreg 0x50,PAGE_S         ; site 60965: masked item overlay (code < 15)
        jp s_it
x_bt:   nextreg 0x50,0xFF
        jp 60857
x_ov:   nextreg 0x50,0xFF
        jp 60843
x_it:   nextreg 0x50,0xFF
        jp 60969
e_bend: nextreg 0x50,PAGE_S         ; site 59547: the walker finished a band
        jp s_bend
x_bend: nextreg 0x50,0xFF
        jp 59550
rom_end:

        ORG 0x0100
s_rs:   ld iy,0                     ; clears V_S (and spare 0x0001) without touching A or F
        ld (V_S),iy
        ld (V_OVF),iy
        ld iy,(V_FRM)               ; next render (INC IY leaves F alone)
        inc iy
        ld (V_FRM),iy
        ld (V_SP4),sp               ; collectables: item list + patterns for this render
        ld sp,STK                   ; (own stack; every register kept)
        push af
        push bc
        push de
        push hl
        call ibuild
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP4)
        ld iy,27964
        jp x_rs

s_lim:  ld a,(V_TICK)
        inc a
        cp LIMIT
        jr c,.skip
        xor a
        ld (V_TICK),a
        nextreg 0x07,3              ; 28 MHz for the game frame
        jp x_lrun
.skip:  ld (V_TICK),a
        jp x_lskip

s_re:   ld (V_HL3),hl               ; HL and BC are live here; A and F are not (SUB 160 follows)
        ld (V_BC3),bc
        ld (V_DE3),de
        ld (V_SP3),sp               ; collectables: own stack (page 26) for the item routine
        ld sp,STK
        call items
        ld sp,(V_SP3)
; commit: every staged piece's patterns + attributes in one burst (sprite by sprite: pattern, then
; its attributes), so the screen never shows a half-updated figure or old sprites with new images
        ld a,(V_NP)
        or a
        jp z,.nop
        ld de,ATTRB
        xor a
        ld (V_CS),a
        ld hl,CLIST
        ld (V_CL),hl
.pc:    ld hl,(V_CL)
        ld a,(hl)
        nextreg 0x51,a
        inc hl
        ld a,(hl)
        ld (V_ENT+1),a
        inc hl
        ld a,(hl)
        ld (V_TMP2),a
        inc hl
        ld (V_CL),hl
        ld b,a
        xor a
.pb:    sub 64
        djnz .pb
        ld l,a
        ld a,(V_ENT+1)
        ld h,a
.ps:    ld a,(V_CS)                 ; pattern slot: p/2, +128 bytes if p odd
        ld c,a
        rrca
        and 0x80
        ld b,a
        ld a,c
        srl a
        or b
        ld bc,0x303B
        out (c),a
        ld bc,0x405B                ; 64 bytes (top half; the bottom stays zero)
        otir
        ld a,(V_NI)                 ; figure sprite = item sprites + pattern number
        ld c,a
        ld a,(V_CS)
.fo:    add a,c                     ; (unit-test control: figures over the item sprites)
        nextreg 0x34,a
        ld a,(de)
        nextreg 0x35,a
        inc de
        ld a,(de)
        nextreg 0x36,a
        inc de
        ld a,(de)
        nextreg 0x37,a
        inc de
        ld a,(de)
        nextreg 0x38,a
        inc de
        ld a,(de)
        nextreg 0x39,a
        inc de
        ld a,(V_CS)
        inc a
        ld (V_CS),a
        ld a,(V_TMP2)
        dec a
        ld (V_TMP2),a
        jr nz,.ps
        ld a,(V_NP)
        dec a
        ld (V_NP),a
        jp nz,.pc
        nextreg 0x51,0xFF
.nop:   nextreg 0x15,1              ; sprites on (a non-play screen switched them off)
        ld a,(V_PREV)               ; hide sprites total .. prev-1 (drawn last render, not this one)
        ld h,a
        ld a,(V_NI)                 ; total = item sprites + figure sprites
        ld b,a
        ld a,(V_S)
        add a,b
        ld (V_PREV),a
.hide:  cp h
        jr nc,.done
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .hide
.done:  ld hl,(V_HL3)
        ld bc,(V_BC3)
        ld de,(V_DE3)
        ld a,(58850)
        jp x_re

s_pc:
        ld (V_IY),iy                ; IY = the walker's list pointer
        ld (V_SP),sp
        ld sp,STK                   ; small stack in PAGE_S (SP held the graphics pointer)
        ex af,af'                   ; AF' carries the plotter's row control (EX AF,AF'/JP NC)
        push af                     ; F' at STK-2 (bit 0 = carry)
        ex af,af'
        ld (V_DE),de
        ld (V_IX),ix
        ld a,ixh                    ; star plotters 60176/60180 overwrite a cell and set its
        cp high 60176               ; attribute: they stay on the ULA screen (cell-aligned)
        jr nz,.nostar
        ld a,ixl
        cp low 60176
        jp z,passthru
        cp low 60180
        jp z,passthru
.nostar:
        ld a,ixl                    ; plotter info (Python: rainbow.plotter_layouts)
        ld l,a
        ld h,high PI
        ld a,(hl)
        cp ixh
        jp nz,passthru              ; not a known plotter entry: original drawing on the ULA
        inc h
        ld a,(hl)
        ld c,a
        and 15
        ld (V_OFF),a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (V_NS),a
        ld b,a
        ld a,(V_S)
        add a,b
        ld c,a
        ld a,(V_FMAX)               ; 128 - item sprites of this render
        cp c
        jp c,passthru               ; sprites for this render used up: ULA
        ld a,(STK-2)
        and 1
        ld (V_KEY),a
        ld e,a
        inc h                       ; PI+2 / PI+3: stream length
        ld a,h
        add a,e
        ld h,a
        ld a,(hl)
        ld (V_LEN),a
        ld a,e                      ; PI+4 / PI+6: layout pointer
        add a,a
        add a,high PI+4
        ld h,a
        ld a,(hl)
        ld (V_LT),a
        inc h
        ld a,(hl)
        ld (V_LT+1),a
; --- store lookup. Key = IX + AF' carry + the WHOLE stream (compared in full). Hash of IXl,
; carry and the first <= 16 stream bytes -> set (512 sets x 2 ways, 256 bytes per entry).
        ld a,(V_LEN)
        cp 17
        jr c,.hl
        ld a,16
.hl:    ld b,a
        ld hl,(V_SP)
        ld a,ixl
        ld e,a
        ld a,(V_KEY)
        ld d,a
.h:     ld a,e
        add a,(hl)
        ld e,a
        ld a,d
        rlca
        xor (hl)
        ld d,a
        inc hl
        djnz .h
        ld a,d
        rrca
        xor e
        ld e,a                      ; set (256 sets x 4 ways x 256 bytes = 256K)
        rrca
        rrca
        rrca
        and 31
        add a,STORE_PG
        ld (V_EPG),a
        nextreg 0x51,a              ; store page -> slot 1
        ld a,e
        and 7
        add a,a
        add a,a
        add a,0x20
        ld h,a                      ; ways 0-3 = H:00 .. (H+3):00
        ld c,4
.way:   ld l,0
        ld a,(hl)
        cp ixl
        jr nz,.wn
        inc l
        ld a,(hl)
        cp ixh
        jr nz,.wn
        inc l
        ld a,(V_KEY)
        cp (hl)
        jr nz,.wn
        ld l,8
        ld de,(V_SP)
        ld a,(V_LEN)
        ld b,a
.cmp:   ld a,(de)
        cp (hl)
.cmpj:  jr nz,.wn                   ; (unit-test negative control patches this jump out)
        inc de
        inc l
        djnz .cmp
        jp hit
.wn:    inc h
        dec c
        jr nz,.way
        ld a,h                      ; miss: victim = the oldest way NOT used this render (its
        sub 4                       ; patterns are committed at render end)
        ld h,a
        ld c,4
        ld b,0
        ld e,0
.v:     ld l,3
        ld a,(V_FRM)
        sub (hl)
        jr z,.vn
        cp b
        jr c,.vn
        ld b,a
        ld e,h
.vn:    inc h
        dec c
        jr nz,.v
        ld a,e
        or a
        jr nz,.vok
        ld a,(V_OVF)                ; all 4 ways used this render: convert into an overflow entry
        cp 32                       ; (page 30, one per piece, not cached)
        jr c,.ov
        nextreg 0x51,0xFF           ; (32 overflows in one render: ULA - never expected)
        jp passthru
.ov:    inc a
        ld (V_OVF),a
        add a,0x1F
        ld h,a
        ld a,PAGE_OVF
        ld (V_EPG),a
        nextreg 0x51,a
        jp miss
.vok:   ld h,a
        jp miss

hit:    ld a,h
        ld (V_ENT+1),a
        ld l,3
        ld a,(V_FRM)
        ld (hl),a
        ld hl,(V_HITS)
        inc hl
        ld (V_HITS),hl
        jp upload

; --- miss: convert the stream straight into the entry (no canvas runs), store key + stream
miss:   ld a,h
        ld (V_ENT+1),a
        xor a
        ld (V_ENT),a
        ld hl,WBG                   ; G = 0, MG = FF (untouched pixels are transparent)
        ld b,96
.i0:    ld (hl),a
        inc l
        djnz .i0
        ld hl,WBM
        ld b,96
        dec a
.i1:    ld (hl),a
        inc l
        djnz .i1
        nextreg 0x51,PAGE_T         ; layout table: per stream byte: target row*6+col (bits 5-0),
        ld de,(V_SP)                ; bit 6 = mirrored (leftward row), bit 7 = mask byte
        ld hl,(V_LT)
        ld a,(V_LEN)
        ld b,a
.lp:    ld a,(de)
        inc de
        ld iyl,a
        ld a,(hl)
        inc hl
        ld c,a
        push hl
        bit 6,c
        jr z,.nm
        ld h,high MIRTAB
        ld a,iyl
        ld l,a
        ld a,(hl)
        ld iyl,a
.nm:    ld a,c
        and 0x3F
        ld l,a
        ld h,high WBG
        bit 7,c
        jr nz,.mk
        ld a,iyl                    ; ink byte: G = v, MG |= v
        ld (hl),a
        inc h
        or (hl)
        ld (hl),a
        jr .nx
.mk:    ld a,iyl                    ; mask byte: MG = m | G
        or (hl)
        inc h
        ld (hl),a
.nx:    pop hl
        djnz .lp
        ld a,(V_EPG)
        nextreg 0x51,a              ; entry page back in slot 1
        ld a,(V_NS)                 ; patterns at entry + 256 - 64*nspr (top 8 rows, 64 bytes each)
        ld b,a
        xor a
.pb:    sub 64
        djnz .pb
        ld ixl,a
        ld a,(V_ENT+1)
        ld ixh,a
        ld a,0                      ; k = 0
.spr:   ld (V_TMP),a
        ld c,0                      ; OR of all pattern bytes (visibility)
        add a,a                     ; column 2k of row 0
        ld l,a
        ld h,high WBG
        ld iyh,8
.row:   push hl
        call cbyte
        inc l
        call cbyte
        pop hl
        ld a,l
        add a,6
        ld l,a
        dec iyh
        jr nz,.row
        ld a,(V_TMP)
        add a,low V_VIS
        ld e,a
        ld d,high V_VIS
        ld a,c
        ld (de),a
        ld a,(V_TMP)
        inc a
        ld hl,V_NS
        cp (hl)
        jr c,.spr
        ld hl,(V_ENT)               ; header: IXl IXh key stamp vis0-2 nspr, stream at +8
        ld a,(V_IX)
        ld (hl),a
        inc l
        ld a,(V_IX+1)
        ld (hl),a
        inc l
        ld a,(V_KEY)
        ld (hl),a
        inc l
        ld a,(V_FRM)
        ld (hl),a
        inc l
        ex de,hl
        ld hl,V_VIS
        ld bc,3
        ldir
        ld a,(V_NS)
        ld (de),a
        inc e
        ld hl,(V_SP)
        ld a,(V_LEN)
        ld c,a
        ld b,0
        ldir

; --- stage the piece: visibility now, patterns + attributes are committed at render end
upload: ld hl,(V_ENT)
        ld l,4
        ld de,V_VIS
        ld bc,3
        ldir
        ld a,(V_NP)                 ; CLIST[np] = page, entry high byte, nspr
        ld l,a
        ld h,0
        ld e,a
        ld d,0
        add hl,hl
        add hl,de
        ld de,CLIST
        add hl,de
        ld a,(V_EPG)
        ld (hl),a
        inc hl
        ld a,(V_ENT+1)
        ld (hl),a
        inc hl
        ld a,(V_NS)
        ld (hl),a
        ld hl,V_NP
        inc (hl)
        nextreg 0x51,0xFF           ; alt ROM back in slot 1 (the plotter returns through it)
; --- register run: the original plotter once, over a canvas page, for its exact register state
        ld a,4
        ld (V_RUN),a
        nextreg 0x52,PAGE_C2
        ld ix,(V_IX)
        ld bc,(V_SP)                ; dispatch state: BC = HL = SP = stream, H = 245
        ld sp,(V_SP)
        ld de,(V_DE)
        ld h,245
        ld l,c
        jp (ix)

passthru:
        ld sp,(V_SP)
        ld a,3
        ld (V_RUN),a
        ld bc,(V_SP)
        ld de,(V_DE)
        ld h,245
        ld l,c
        jp (ix)

; one window byte pair (G at HL, MG at HL+0x100) -> 4 pattern bytes at (IX); C |= bytes
cbyte:  ld a,(hl)                   ; G
        and 0xF0
        ld b,a
        inc h                       ; MG
        ld a,(hl)
        swapnib                     ; Z80N ED 23 (simulated in rainbow._machine)
        and 0x0F
        or b
        ld e,a
        ld d,high NIBTAB
        ld a,(de)
        ld (ix+0),a
        or c
        ld c,a
        inc d
        ld a,(de)
        ld (ix+1),a
        or c
        ld c,a
        ld a,(hl)
        and 0x0F
        ld b,a
        dec h
        ld a,(hl)
        swapnib
        and 0xF0
        or b
        ld e,a
        dec d
        ld a,(de)
        ld (ix+2),a
        or c
        ld c,a
        inc d
        ld a,(de)
        ld (ix+3),a
        or c
        ld c,a
        inc ix
        inc ix
        inc ix
        inc ix
        ret

s_af:   ld (V_TMP),a
        ld a,(V_RUN)
        cp 4
        jr z,regsdone
        ld a,(V_TMP)                ; passthrough finished
        jp x_cont

regsdone:
        ld (V_SP2),sp               ; every register is now exactly as after the original plot
        ld (V_BC2),bc               ; (AF' may hold a canvas byte: verify proves it dies)
        ld (V_HL2),hl
        ld (V_DF),de
        nextreg 0x52,10             ; screen back
        ld sp,STK-2
        ld a,(V_DE)                 ; X of column E-off = (E & 31) * 8 - 8*off + 32 (9 bits in HL)
        and 31
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_OFF)                ; 8 * (4 - off)
        neg
        add a,4
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld a,(V_DE)                 ; Y = cell top + (D & 7) + 32 (patterns hold rows from the
        and 0xE0                    ; piece's own start row)
        rrca
        rrca
        ld b,a
        ld a,(V_DE+1)
        and 0x18
        rlca
        rlca
        rlca
        or b
        ld b,a
        ld a,(V_DE+1)
        and 7
        add a,b
        add a,32
        ld c,a
        ld a,(V_SP+1)               ; palette offset by graphics page
        ld e,a
        ld d,high CLASSTAB
        ld a,(de)
        ld b,a
        ld a,(V_S)                  ; IY = ATTRB + 5 * V_S
        ld e,a
        ld d,0
        ld iy,ATTRB
        add iy,de
        add iy,de
        add iy,de
        add iy,de
        add iy,de
        ld ixl,0                    ; k = 0..nspr-1
.a:     ld a,(V_S)
        add a,ixl
        ld ixh,a                    ; sprite = pattern index
        ld (iy+0),l
        ld (iy+1),c
        ld a,h
        and 1
        or b
        ld (iy+2),a
        ld a,ixl
        add a,low V_VIS
        ld e,a
        ld d,high V_VIS
        ld a,(de)                   ; nonzero = this sprite has pixels
        or a
        ld a,0x40                   ; attr4 enabled, hidden
        jr z,.nv
        ld a,0xC0                   ; attr4 enabled, visible
.nv:    ld e,a
        ld a,ixh                    ; attr3 = p/2, attr4 N6 = p & 1
        srl a
        or e
        ld (iy+3),a
        ld a,ixh
        rrca
        rrca
        and 0x40
        or 0x80
        ld (iy+4),a
        ld de,5
        add iy,de
        ld de,16
        add hl,de
        inc ixl
        ld a,(V_NS)
        cp ixl
        jr nz,.a
        ld a,(V_S)
        ld hl,V_NS
        add a,(hl)
        ld (V_S),a
        ld iy,(V_IY)
        ld ix,(V_IX)
        ld de,(V_DF)
        ld bc,(V_BC2)
        ld hl,(V_HL2)
        ld sp,(V_SP2)
        ld a,(V_TMP)
        jp x_cont

; --- collectables: shadow map hooks (interrupts off at all three sites in both RZX). No stack:
; at these sites SP is the game's stack. DE = back-buffer cell; a DE that is not a cell
; (D outside 0x9F-0xB4 or E >= 32) is ignored; else HL = CODES + 32*(D-0x9F) + E.

s_bt:   ld (V_IA),a                 ; A = tile code: base colour = (0xF200 + (tile|128)) & 127
        ld (V_IBC),bc
        or 128
        ld l,a
        ld h,0xF2
        ld a,(hl)
        and 127
        or 128                      ; bit 7: colour known
        ld c,a
        ld a,d
        sub 0x9F
        cp 22
        jr nc,.out
        ld l,a
        ld a,e
        cp 32
        jr nc,.out
        ld a,l
        rrca
        rrca
        rrca
        ld h,a
        and 0xE0
        or e
        ld l,a
        ld a,h
        and 0x03
        add a,high CODES
        ld h,a
        nextreg 0x51,PAGE_T
        ld a,h
        add a,high (BATTR-CODES)
        ld h,a
        ld (hl),c
        sub high (BATTR-CODES)
        ld h,a
        ld b,0                      ; no item in the cell any more
        ld a,(hl)                   ; CODES = B; row count (RCNT) follows empty <-> occupied
        ld (hl),b
        ld c,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        sub high CODES
        add a,a
        add a,a
        add a,a
        or l
        add a,low RCNT
        ld l,a
        ld h,high RCNT
        ld a,c
        or b
        jr z,.o3                    ; empty before and after: the item list is unaffected
        ld a,1
        ld (V_IDIRTY),a
        ld a,c
        or a
        jr nz,.o1
        inc (hl)
        jr .o3
.o1:    ld a,b
        or a
        jr nz,.o3
        dec (hl)
.o3:
        nextreg 0x51,0xFF
.out:   ld bc,(V_IBC)
        ld a,(V_IA)
        add a,a                     ; the replaced ADD A,A / LD L,A / LD H,0 (carry: JP C follows)
        ld l,a
        ld h,0
        jp x_bt

s_ov:   ld (V_IA),a                 ; full 8x8 tile from 0xF700 + 8*(code-1): code 1-14 = an item
        sbc a,a                     ; drawn OPAQUE (its tile is plain: F2 bit 7 clear), code >= 15 =
        ld (V_ICY),a                ; another overlay (no item). Carry at entry kept for DEC A.
        ld a,d
        sub 0x9F
        cp 22
        jr nc,.out
        ld l,a
        ld a,e
        cp 32
        jr nc,.out
        ld a,l
        rrca
        rrca
        rrca
        ld h,a
        and 0xE0
        or e
        ld l,a
        ld a,h
        and 0x03
        add a,high CODES
        ld h,a
        ld (V_IBC),bc
        ld a,(V_IA)
        ld bc,0                     ; no item, colour unknown
        dec a
        cp 14
        jr nc,.st
        inc a
        ld b,a                      ; opaque item
        ld a,iyh                    ; cell composition (IY = 60699): colour computed later by the
        cp high 60699               ; game, ink irrelevant (the cell is blank once the item is
        jr nz,.spn                  ; removed). Spawned item (other IY): the colour before it =
        ld a,iyl                    ; the attribute buffer now
        cp low 60699
        jr z,.st
.spn:   ld a,h
        add a,high (0xB500-CODES)
        ld h,a
        ld a,(hl)
        or 128
        ld c,a
        ld a,h
        sub high (0xB500-CODES)
        ld h,a
.st:    nextreg 0x51,PAGE_T
        ld a,h
        add a,high (BATTR-CODES)
        ld h,a
        ld (hl),c
        sub high (BATTR-CODES)
        ld h,a
.wr:    ld a,(hl)                   ; (unit-test control: this read + write -> the code is kept)
        ld (hl),b
        ld c,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        sub high CODES
        add a,a
        add a,a
        add a,a
        or l
        add a,low RCNT
        ld l,a
        ld h,high RCNT
        ld a,c
        or b
        jr z,.o3                    ; empty before and after: the item list is unaffected
        ld a,1
        ld (V_IDIRTY),a
        ld a,c
        or a
        jr nz,.o1
        inc (hl)
        jr .o3
.o1:    ld a,b
        or a
        jr nz,.o3
        dec (hl)
.o3:
        nextreg 0x51,0xFF
        ld bc,(V_IBC)
.out:   ld a,(V_ICY)
.rla:   rla                         ; carry back (unit-test control: removed)
        ld a,(V_IA)
        dec a                       ; the replaced DEC A / LD L,A / LD H,0
        ld l,a
        ld h,0
        jp x_ov

s_it:   ld (V_IA),a                 ; A = item code: CODES = code if the cell is empty or holds
        ld (V_IBC),bc               ; the same code, else FF (several objects / not an item: ULA)
        ld (V_IHL2),hl
        ld a,d
        sub 0x9F
        cp 22
        jr nc,.out
        ld l,a
        ld a,e
        cp 32
        jr nc,.out
        ld a,l
        rrca
        rrca
        rrca
        ld h,a
        and 0xE0
        or e
        ld l,a
        ld a,h
        and 0x03
        add a,high CODES
        ld h,a
        nextreg 0x51,PAGE_T
        ld a,(V_IA)
        ld b,a
        dec a                       ; items are codes 1-14 (0xF600 graphics); anything else the
        cp 14                       ; masked drawer puts in a cell stays on the ULA
        jr nc,.many
        ld a,(hl)
        or a
        jr z,.new
        cp b
        jr z,.set
.many:  ld b,0xFF
        jr .set
.new:   ld a,iyh                    ; cell composition (IY = 60720): base colour from s_bt / s_ov;
        cp high 60720               ; item spawned into a drawn cell (other IY): its colour before
        jr nz,.spn                  ; the item = the attribute buffer now
        ld a,iyl
        cp low 60720
        jr z,.set
.spn:   ld a,h
        add a,high (0xB500-CODES)
        ld h,a
        ld a,(hl)
        or 128
        ld c,a
        ld a,h
        sub high (0xB500-CODES)
        add a,high (BATTR-CODES)
        ld h,a
        ld (hl),c
        sub high (BATTR-CODES)
        ld h,a
.set:
        ld a,(hl)                   ; CODES = B; row count (RCNT) follows empty <-> occupied
        ld (hl),b
        ld c,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        sub high CODES
        add a,a
        add a,a
        add a,a
        or l
        add a,low RCNT
        ld l,a
        ld h,high RCNT
        ld a,c
        or b
        jr z,.o3                    ; empty before and after: the item list is unaffected
        ld a,1
        ld (V_IDIRTY),a
        ld a,c
        or a
        jr nz,.o1
        inc (hl)
        jr .o3
.o1:    ld a,b
        or a
        jr nz,.o3
        dec (hl)
.o3:
        nextreg 0x51,0xFF
.out:   ld bc,(V_IBC)
        ld hl,(V_IHL2)
        ld a,(V_IA)
        dec a                       ; the replaced DEC A / ADD A,A x3 (60969 = the 4th ADD A,A)
        add a,a
        add a,a
        add a,a
        jp x_it

; --- collectables: render start. Scan the shadow map (rows with occupied cells); every item cell
; with rows in the play area -> record in ILIST (page 27); its pattern from the cache (page 28),
; built only for a new key. Then the per-char-row item ranges for the band hook. Own stack (STK);
; IY is free here (the replaced LD IY,27964 follows); IX is saved.
ibuild: push ix
        ld a,(V_FRM)                ; pattern cache stamp = render counter
        ld iyh,a
        nextreg 0x51,PAGE_T
        ld hl,0xF600                ; item graphics changed since the last render (other island)?
        ld de,GCOPY
        ld b,224
.gc:    ld a,(de)
        cp (hl)
        jr nz,.gchg
        inc l
        inc e
        djnz .gc
        ld a,(V_IDIRTY)             ; nothing changed since the last list (no cell hook touched an
        or a                        ; occupied cell, same scroll and play-area height): keep it
        jr nz,.new
        ld a,(48782)
        ld hl,V_LS
        cp (hl)
        jr nz,.new
        ld a,(58850)
        inc hl
        cp (hl)
        jr nz,.new
        call ikeep                  ; same list: the game may still change an item's ink (51914)
        nextreg 0x51,0xFF
        pop ix
        ret
.gchg:  ld hl,0xF600                ; yes: keep a copy and invalidate every cache entry
        ld de,GCOPY
        ld bc,224
        ldir
        ld hl,PKEYS+2
        ld de,4
        ld b,128
.iv:    ld (hl),0
        add hl,de
        djnz .iv
.new:   xor a
        ld (V_IDIRTY),a
        ld a,(48782)
        ld (V_LS),a
        ld a,(58850)
        ld (V_LN),a
        xor a
        ld (V_NI),a
        ld a,NSPR_MAX
        ld (V_FMAX),a
        ld a,(48782)
        ld (V_IS),a
        ld a,(58850)
        ld (V_IN),a
        ld hl,ILIST
        ld (V_IREC),hl
        ld hl,RFIRST                ; no band work yet
        ld b,48
        ld a,0xFF
.cw:    ld (hl),a
        inc l
        djnz .cw
        ld hl,CODES                 ; rows with occupied cells only
        ld de,RCNT
.rowk:  ld a,(de)
        or a
        jr z,.rnx
        ld b,32
.scan:  ld a,(hl)
        or a
        jr z,.nx
        inc a
        jr z,.nx                    ; FF: left on the ULA
        dec a
        ld (V_ICODE),a
        ld (V_IHL),hl
        push bc
        push de
        call ibrec
        pop de
        pop bc
        ld hl,(V_IHL)
.nx:    inc hl
        djnz .scan
        jr .rn2
.rnx:   ld bc,32
        add hl,bc
.rn2:   inc e
        ld a,e
        cp low RCNT+22
        jr c,.rowk
        ld a,(V_NI)                 ; band ranges: first / last item touching each char row
        or a
        jr z,.end
        ld b,a
        ld c,0
        ld ix,ILIST
.br:    ld a,(ix+8)
        call .mark
        ld a,(ix+9)
        call .mark
        ld a,(ix+4)
        cp 0xFF
        call nz,.mark
        ld de,16
        add ix,de
        inc c
        djnz .br
.end:   nextreg 0x51,0xFF
        ld a,(V_NI)                 ; figures may use the sprites the items leave
        ld b,a
        ld a,NSPR_MAX
        sub b
        ld (V_FMAX),a
        pop ix
        ret
.mark:  add a,low RFIRST            ; A = char row, C = item
        ld l,a
        ld h,high RFIRST
        ld a,(hl)
        inc a
        jr nz,.m1
        ld (hl),c
.m1:    ld a,l
        add a,RLAST-RFIRST
        ld l,a
        ld (hl),c
        ret

; list kept: stamp every item's cache entry (so none is evicted), then refresh each item's ink
; from the attribute buffer; a changed ink gets its pattern from the cache (new key)
ikeep:  ld a,(V_NI)
        or a
        ret z
        ld b,a
        ld ix,ILIST
.st:    ld l,(ix+11)
        ld h,0
        add hl,hl
        add hl,hl
        ld a,h
        add a,high PKEYS
        ld h,a
        inc l
        inc l
        inc l
        ld a,iyh
        ld (hl),a
        ld de,16
        add ix,de
        djnz .st
        ld a,(V_NI)
        ld b,a
        ld ix,ILIST
.ik:    ld l,(ix+6)
        ld h,(ix+7)
        ld a,(hl)                   ; ink pixel index: ink 0 -> 1 (black), else ink+1, bright +7
        ld c,a
        and 7
        ld e,1
        jr z,.i1
        inc a
        ld e,a
        bit 6,c
        jr z,.i1
        add a,7
        ld e,a
.i1:    ld a,e
        cp (ix+10)
.ref:   jr z,.in                    ; (unit-test control: JR = inks never refreshed)
        ld (V_IINK),a
        ld (ix+10),a
        ld a,(ix+3)
        ld (V_IG),a
        ld a,(ix+2)
        ld (V_IVIS),a
        push bc
        call ipat
        pop bc
        ld a,(V_IE)
        ld (ix+11),a
.in:    ld de,16
        add ix,de
        djnz .ik
        ret

ibrec:  ld a,(V_NI)
        cp IMAX
        ret nc                      ; list full: the item stays on the ULA as drawn
        ld a,l
        and 31
        ld (V_IC),a
        ld a,h                      ; k = (H - high CODES) * 8 + L / 32
        sub high CODES
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        or b
        ld (V_IK),a
        add a,a                     ; y = (8k - s) mod 176
        add a,a
        add a,a
        ld b,a
        ld a,(V_IS)
        ld c,a
        ld a,b
        sub c
        jr nc,.y1
        add a,176
.y1:    ld (V_IYU),a
        cp 168                      ; cell starts in the last 8 rows: its lower rows wrap to the
        jr c,.y2                    ; top of the play area
        sub 176
.y2:    add a,16                    ; Y0 = screen row of pattern row 0
        ld (V_IYS),a
        ld a,(V_IYU)                ; usual case: all 8 rows on screen
        cp 168
        jr nc,.slow
        add a,8
        ld hl,V_IN
        cp (hl)
        jr z,.fast
        jr nc,.slow
.fast:  ld a,0xFF
        ld (V_IVIS),a
        xor a
        ld (V_IJ0),a
        ld a,8
        ld (V_IJ0+1),a
        jr .vok
.slow:  ld e,0                      ; visible rows: row j shows at t = (y + j) mod 176, if t < N
        ld c,0                      ; (they are contiguous: j0 .. j0+n-1)
        ld d,0
        ld a,0xFF
        ld (V_IJ0),a
.vj:    ld a,(V_IYU)
        add a,c
        cp 176
        jr c,.v1
        sub 176
.v1:    ld hl,V_IN
        cp (hl)
        rl e
        bit 0,e
        jr z,.v2
        inc d
        ld a,(V_IJ0)
        inc a
        jr nz,.v2
        ld a,c
        ld (V_IJ0),a
.v2:    inc c
        ld a,c
        cp 8
        jr c,.vj
        ld a,e
        or a
        ret z                       ; nothing of it on screen
        ld (V_IVIS),a
        ld a,d
        ld (V_IJ0+1),a
.vok:   ld a,(V_IYS)                ; char rows of the first and last visible row
        ld hl,V_IJ0
        add a,(hl)
        ld b,a                      ; B = Y of the first visible row
        rrca
        rrca
        rrca
        and 31
        ld (V_IROWS),a
        inc hl
        ld a,b
        add a,(hl)
        dec a
        rrca
        rrca
        rrca
        and 31
        ld (V_IROWS+1),a
        ld a,b                      ; screen address of row B, column
        and 7
        ld h,a
        ld a,b
        and 0xC0
        rrca
        rrca
        rrca
        or h
        or 0x40
        ld h,a
        ld a,b
        and 0x38
        rlca
        rlca
        ld l,a
        ld a,(V_IC)
        or l
        ld l,a
        ld (V_IHL2),hl
        ld a,(V_IK)                 ; attribute-buffer address 0xB500 + 32k + col
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_IC)
        or l
        ld l,a
        ld a,h
        add a,0xB5
        ld h,a
        ld (V_IAB),hl
        ld a,(hl)                   ; ink pixel index: ink 0 -> 1 (black), else ink+1, bright +7
        ld b,a
        and 7
        ld c,1
        jr z,.ik
        inc a
        ld c,a
        bit 6,b
        jr z,.ik
        add a,7
        ld c,a
.ik:    ld a,c
        ld (V_IINK),a
        ld a,(V_ICODE)              ; gfx: (mask, gfx) pairs at 0xF600 + 16 * (code - 1)
        dec a
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_IG),a
        ld a,0xFF                   ; attribute: screen char row 2 + kk shows attribute-buffer row
        ld (V_IAR),a                ; (s/8 + kk) mod 22, so kk = (k - s/8) mod 22; fixed only when
        xor a                       ; that char row is drawn and the base colour is known
        ld (V_IBAS),a
        ld a,(V_IS)
        rrca
        rrca
        rrca
        and 31
        ld b,a
        ld a,(V_IK)
        sub b
        jr nc,.a1
        add a,22
.a1:    ld c,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_IN)
        cp b
        jr c,.na
        jr z,.na
        ld hl,(V_IHL)
        ld a,h
        add a,high (BATTR-CODES)
        ld h,a
        ld a,(hl)
        bit 7,a
        jr z,.na
        and 127
        ld (V_IBAS),a
        ld a,c
        add a,2
        ld (V_IAR),a
.na:    call ipat                   ; pattern cache entry -> V_IE (FF: none free)
        ld a,(V_IE)
        inc a
        ret z                       ; no pattern: the item stays on the ULA as drawn
        ld hl,(V_IREC)              ; the record
        ld a,(V_IC)
        ld (hl),a
        inc l
        ld a,(V_IYS)
        ld (hl),a
        inc l
        ld a,(V_IVIS)
        ld (hl),a
        inc l
        ld a,(V_IG)
        ld (hl),a
        inc l
        ld a,(V_IAR)
        ld (hl),a
        inc l
        ld a,(V_IBAS)
        ld (hl),a
        inc l
        ld a,(V_IAB)
        ld (hl),a
        inc l
        ld a,(V_IAB+1)
        ld (hl),a
        inc l
        ld a,(V_IROWS)
        ld (hl),a
        inc l
        ld a,(V_IROWS+1)
        ld (hl),a
        inc l
        ld a,(V_IINK)
        ld (hl),a
        inc l
        ld a,(V_IE)
        ld (hl),a
        inc l
        ld a,(V_IHL2)
        ld (hl),a
        inc l
        ld a,(V_IHL2+1)
        ld (hl),a
        inc l
        ld a,(V_IJ0)
        ld (hl),a
        inc l
        ld a,(V_IJ0+1)
        ld (hl),a
        inc hl
        ld (V_IREC),hl
        ld hl,V_NI
        inc (hl)
        ret

; --- pattern cache: key (gfx low, ink, visible rows); hash -> up to 8 probes for the key, else the
; first entry not used this render (stamp IYH) from the hash on is rebuilt. Slot 1 = page 27.
ipat:   ld a,(V_IG)
        ld (V_IKEY),a
        rrca
        rrca
        rrca
        rrca
        ld b,a
        ld a,(V_IINK)
        ld (V_IKEY+1),a
        ld c,a
        add a,a
        add a,a
        add a,a
        add a,c
        add a,b
        ld b,a
        ld a,(V_IVIS)
        ld (V_IKEY+2),a
        add a,b
        and 127
        ld (V_PH),a
        ld c,a
        ld b,8
.p1:    call .ent                   ; HL = key of entry C
        ld a,(V_IKEY)
        cp (hl)
        jr nz,.p2
        inc l
        ld a,(V_IKEY+1)
        cp (hl)
        jr nz,.p2
        inc l
        ld a,(V_IKEY+2)
        cp (hl)
        jr nz,.p2
        inc l
        ld a,iyh                    ; hit: stamp it
        ld (hl),a
        ld a,c
        ld (V_IE),a
        ret
.p2:    inc c
        res 7,c
        djnz .p1
        ld a,(V_PH)                 ; miss: first entry not used this render
        ld c,a
        ld b,128
.p3:    call .ent
        inc l
        inc l
        inc l
        ld a,iyh
        cp (hl)
        jr nz,.new
        inc c
        res 7,c
        djnz .p3
        ld a,0xFF                   ; every entry used this render
        ld (V_IE),a
        ret
.new:   ld (hl),a                   ; stamp + key
        dec l
        ld a,(V_IKEY+2)
        ld (hl),a
        dec l
        ld a,(V_IKEY+1)
        ld (hl),a
        dec l
        ld a,(V_IKEY)
        ld (hl),a
        ld a,c
        ld (V_IE),a
.nb:    call ipbuild                ; (unit-test control: never built)
        ret
.ent:   ld l,c                      ; HL = PKEYS + 4*C
        ld h,0
        add hl,hl
        add hl,hl
        ld a,h
        add a,high PKEYS
        ld h,a
        ret

; pattern of the key into page 28 at 0x2000 + 64*V_IE: gfx -> ink, mask 0 -> 1 (outline), else 0;
; rows not visible transparent. Page 27 back in slot 1 at the end.
ipbuild:
        ld a,(V_IE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x2000
        add hl,de
        ex de,hl                    ; DE = pattern
        ld a,(V_IINK)               ; IYL = ink in both nibbles
        ld b,a
.inkx:  rlca                        ; (unit-test control: ink 1 = outline colour)
        rlca
        rlca
        rlca
        or b
        ld iyl,a
        ld a,(V_IG)
        ld (V_IKEY),a               ; (reused: gfx pointer low byte)
        ld a,(V_IVIS)
        ld (V_IKEY+2),a             ; (reused: rows left to rotate)
        nextreg 0x51,IPAGE
        ld a,8
        ld (V_IROW),a
.row:   ld a,(V_IKEY)
        ld l,a
        ld h,0xF6
        ld c,(hl)                   ; mask
        inc l
        ld b,(hl)                   ; gfx
        inc l
        ld a,l
        ld (V_IKEY),a
        ld a,(V_IKEY+2)
        rlca
        ld (V_IKEY+2),a
        jr nc,.blank
        ld a,c                      ; C = outline bits (mask 0 and gfx 0)
        or b
        cpl
        ld c,a
        ld h,high EXP
        ld a,b                      ; high nibbles -> 2 bytes
        and 0xF0
        rrca
        rrca
        rrca
        call .two
        ld a,b                      ; low nibbles -> 2 bytes
        and 0x0F
        add a,a
        rlc c                       ; (C rotated 4 left: its low nibble now in the high nibble)
        rlc c
        rlc c
        rlc c
        call .two
        jr .rz
.blank: xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
.rz:    xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld a,(V_IROW)
        dec a
        ld (V_IROW),a
        jr nz,.row
        nextreg 0x51,PAGE_T
        ret
; A = 2 * gfx nibble, C high nibble = outline nibble: 2 bytes (ink where gfx, 1 where outline)
.two:   push bc
        ld l,a
        ld b,(hl)                   ; gfx expanded
        inc l
        ld a,c
        and 0xF0
        rrca
        rrca
        rrca
        ld c,l
        ld l,a
        ld a,(hl)                   ; outline expanded
        and 0x11
        ld iyh,a
        ld a,b
        and iyl
        or iyh
        ld (de),a
        inc de
        inc l
        ld a,(hl)
        and 0x11
        ld iyh,a
        ld l,c
        ld a,(hl)
        and iyl
        or iyh
        ld (de),a
        inc de
        pop bc
        ld a,(V_FRM)                ; IYH = the cache stamp again
        ld iyh,a
        ret

; --- band hook (59547): the items touching the band just blitted (screen char row R from the
; walker's band address (59522)): their rows on R -> screen AND mask AND NOT gfx; their attribute
; on R -> base colour while the screen shows the attribute-buffer value. Then the replaced
; LD HL,(59522). Own stack; every register kept.
s_bend: ld (V_SP4),sp
        ld sp,STK
        push af
        push hl
        ld hl,(59522)
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        and 0x18
        or l                        ; A = R
        add a,low RFIRST
        ld l,a
        ld h,high RFIRST
        ld a,(hl)
        inc a
        jr z,.q                     ; no item on this char row
        push bc
        push de
        push ix
        call ifix
        pop ix
        pop de
        pop bc
.q:     pop hl
        pop af
        ld sp,(V_SP4)
        ld hl,(59522)
        jp x_bend

; ifix: HL = RFIRST + R. Items RFIRST[R] .. RLAST[R] (page 27 records).
ifix:   ld a,l
        sub low RFIRST
        ld ixh,a                    ; IXH = R
        ld c,(hl)                   ; first
        ld a,l
        add a,RLAST-RFIRST
        ld l,a
        ld a,(hl)
        sub c
        inc a
        ld (V_ICNT),a               ; items in the range
        ld l,c                      ; record pointer = ILIST + 16 * first
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,ILIST
        add hl,de
        nextreg 0x51,PAGE_T
.it:    ld (V_IREC),hl
        ld a,l
        add a,8
        ld l,a
        ld a,(hl)                   ; rows of this item on R?
        cp ixh
        jr z,.rows
        inc l
        ld a,(hl)
        cp ixh
        jr nz,.attr
.rows:  ld hl,(V_IREC)
        ld a,l
        add a,14
        ld l,a
        ld c,(hl)                   ; j0
        inc l
        ld b,(hl)                   ; n
        ld hl,(V_IREC)
        inc l
        ld a,(hl)                   ; Y of row j0 = Y0 + j0
        add a,c
        ld (V_IA2),a
        inc l
        inc l
        ld a,(hl)                   ; gfx row j0: 0xF600 + g + 2*j0
        add a,c
        add a,c
        ld e,a
        ld d,0xF6
        ld a,l
        add a,9
        ld l,a
        ld a,(hl)                   ; screen address of row j0
        inc l
        ld h,(hl)
        ld l,a
        ld a,(V_IA2)
        ld c,a                      ; C = Y
.fr:    ld a,c
        rrca
        rrca
        rrca
        and 31
        cp ixh
.rsel:  jr nz,.skip                 ; (unit-test control: NOPs = rows of other bands fixed too)
        ld a,(de)                   ; mask
        ld ixl,a
        inc e
        ld a,(de)                   ; gfx
        dec e
        cpl
.mand:  and ixl                     ; (unit-test control patches this AND out)
        and (hl)
        ld (hl),a
.skip:  inc e
        inc e
        inc c
        inc h                       ; next screen row
        ld a,h
        and 7
        jr nz,.nl
        ld a,l
        add a,32
        ld l,a
        jr c,.nl
        ld a,h
        sub 8
        ld h,a
.nl:    djnz .fr
.attr:  ld hl,(V_IREC)
        ld a,l
        add a,4
        ld l,a
        ld a,(hl)                   ; attribute char row (FF: none)
        cp ixh
        jr nz,.an
        ld c,a
        inc l
        ld b,(hl)                   ; base colour
        inc l
        ld e,(hl)
        inc l
        ld d,(hl)                   ; DE = attribute-buffer byte
        ld l,c                      ; HL = 0x5800 + 32*row + col
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        push hl
        ld hl,(V_IREC)
        ld a,(hl)
        pop hl
        or l
        ld l,a
        ld a,h
        add a,0x58
        ld h,a
        ld a,(de)                   ; only while the screen shows the attribute-buffer value
        cp (hl)                     ; (a star may have set its own ink there)
        jr nz,.an
        ld (hl),b
.an:    ld hl,(V_IREC)
        ld de,16
        add hl,de
        ld a,(V_ICNT)
        dec a
        ld (V_ICNT),a
        jp nz,.it
        nextreg 0x51,0xFF
        ret

code_end:

; --- render end (called from s_re): the item sprites. Sprite j (0..NI-1); each cache entry used
; this render is uploaded once, to the next pattern after the figures' (V_S, V_S+1, ...), and
; items with the same entry share it. (The screen was fixed band by band.)
        ORG CODE2
items:  ld a,(V_NI)
        or a
        ret z
        ld (V_ICNT),a
        ld hl,ESTAMP                ; no entry uploaded yet this render
        ld (hl),0
        ld de,ESTAMP+1
        ld bc,127
        ldir
        ld a,(V_S)
        ld (V_IP),a
        xor a
        ld (V_TMP2),a               ; sprite j
        ld hl,ILIST
        ld (V_IREC),hl
.u:     nextreg 0x51,PAGE_T
        ld hl,(V_IREC)
        ld a,(hl)
        ld (V_IC),a
        inc l
        ld a,(hl)
        ld (V_IA2),a
        ld a,l
        add a,10
        ld l,a
        ld a,(hl)                   ; entry e -> L = e + low ESTAMP (= low EPAT)
        add a,low ESTAMP
        ld l,a
        ld h,high ESTAMP
        ld a,(hl)
        or a
        ld h,high EPAT
        jr nz,.have                 ; uploaded this render: its pattern number
        ld h,high ESTAMP
        ld (hl),1
        ld h,high EPAT
        ld a,(V_IP)
        ld (hl),a
        inc a
        ld (V_IP),a
        dec a
        ld c,a                      ; pattern slot p/2, +128 bytes if p odd
        rrca
        and 0x80
        ld b,a
        ld a,c
        srl a
        or b
        ld bc,0x303B
        out (c),a
        push hl
        ld a,l                      ; source 0x2000 + 64*e
        sub low ESTAMP
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0x20
        ld h,a
        nextreg 0x51,IPAGE
        ld bc,0x405B
        otir
        pop hl
.have:  ld c,(hl)                   ; C = pattern number
        ld a,(V_TMP2)
        nextreg 0x34,a
        inc a
        ld (V_TMP2),a
        ld a,(V_IC)                 ; X = col*8 + 32 (bit 8 -> attr 2 bit 0)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,0
        adc a,0
        ld h,a
        ld a,l
        add a,32
        nextreg 0x35,a
        ld a,h
        adc a,0
        or ITEM_PAL
        nextreg 0x37,a
        ld a,(V_IA2)                ; Y = Y0 + 32
        add a,32
        nextreg 0x36,a
        ld a,c
        srl a
        or 0xC0                     ; visible, attribute 4 used
        nextreg 0x38,a
        ld a,c
        rrca
        rrca
        and 0x40
        or 0x80                     ; 4-bit pattern, N6 = p & 1
        nextreg 0x39,a
        ld hl,(V_IREC)
        ld de,16
        add hl,de
        ld (V_IREC),hl
        ld a,(V_ICNT)
        dec a
        ld (V_ICNT),a
        jp nz,.u
        nextreg 0x51,0xFF
        ret
code2_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, hide all, clip, sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20           ; edit sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0
        ld bc,0x303B                ; zero all 16K of pattern RAM: the piece hook writes only
        xor a                       ; the top half (64 bytes) of each 4-bit pattern
        out (c),a
        ld d,64
.zp:    ld b,0
.zb:    out (0x5B),a
        djnz .zb
        dec d
        jr nz,.zp
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,16
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
pal:                                ; 256 palette bytes appended by Python

        SAVEBIN "rb_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "rb_page.bin",0x0100,code_end-0x0100
        SAVEBIN "rb_page2.bin",CODE2,code2_end-CODE2
        SAVEBIN "rb_setup.bin",0xD000,pal-0xD000
