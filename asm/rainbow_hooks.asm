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
; Music (bank 1, 2026-10-19):
;   0xD4DE  21 59 5C  LD HL,0x5C59 (AY player entry: a tick starts)  -> JP e_ps
;   0xD6D4  01 FD FF  LD BC,0xFFFD (AY register write: A = reg, D = value; then OUT, OUT, RET) -> JP e_ay
; Objects (2026-10-11, tilemap build): per-cell object map (page 27) kept by three cell-drawer hooks:
;   60853  87 6F 26 00  ADD A,A / LD L,A / LD H,0  (base tile, A = tile)      -> JP e_bt
;   60839  3D 6F 26 00  DEC A / LD L,A / LD H,0    (opaque object tile A)     -> JP e_ov
;   60965  3D 87 87 87  DEC A / ADD A,A x3         (masked object, A = 1-14)  -> JP e_it
;   59547  2A 82 E8     LD HL,(59522) (walker end of a band)                  -> JP e_bend
; Every object (rainbow pieces = codes 1-14, fruit / flowers / collectables = opaque codes >= 15) is
; shown on the tilemap layer (bank 7, in front of the ULA, behind the sprites): one tile per object
; cell, composed from the game's graphics with a 1-pixel black border, rainbow-group objects behind
; the others. The ULA cell shows the cell's map tile (the background) and its colour.
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
; --- objects on the tilemap (page 27 per-cell arrays, slot 1; cell i at base + i)
TILES   EQU 0x2800          ; map tile (the cell's background)
OBJO    EQU 0x2B00          ; opaque object code (60839; 0 none, FF = unsupported: cell left as drawn)
OBJM1   EQU 0x2E00          ; masked objects (60965, codes 1-14) in draw order: nibbles m1 m2
OBJM2   EQU 0x3100          ; m3 m4
FLAGS   EQU 0x3400          ; bit 7 = background known, bits 0-3 = remembered item ink index
CTILE   EQU 0x3700          ; tile assigned this render (0 none) - the band fix needs it
KEYS    EQU 0x3A00          ; tile cache: 4-byte key (O, M1, M2, item ink << 4 | rainbow ink) per tile
STAMP   EQU 0x3D00          ; tile cache: render stamp per tile (bit 7 set; 0 = free)
RCNT    EQU 0x3DC0          ; occupied cells per cell row k (22)
OCCM    EQU 0x27A0          ; occupied cells per cell row k as a 32-bit mask (4 bytes, bit 7 = column 0)
BITS    EQU 0x1F08          ; page 26: 0x80 >> n (8 bytes)
MCLASS  EQU 0x3DE0          ; class of masked object code 0-15 (profile)
OCLASS  EQU 0x3E00          ; class of opaque object code 0-255 (profile): bit 0 rainbow group (behind,
                            ; cell ink), bit 1 left on the ULA, bit 2 no border, bits 4-7 ink override
BGOVR   EQU 0x3F00          ; map tile -> tile shown under objects (profile; identity by default)
NTILE   EQU 176             ; tile definitions 0-175 (0 = transparent)
PAGE_TM EQU 14              ; bank 7 first 8K: tilemap 0x0000 (40x32 x 2 bytes), tiles 0x0A00
TDEF    EQU 0x0A00
PAGE_SH EQU 28              ; shadow map (row kk at kk*64, 2 bytes per column) + LASTT, slot 2
LASTT   EQU 0x4600          ; page 28 at slot 2: tile number of each cell last render (704)
X2      EQU 0x1F00          ; page 26: 2 bits -> 2 nibbles (00 0F F0 FF)
PBUF    EQU 0x0EE6          ; 8 rows of the object being drawn at PBUF+1..+8; PBUF+0 / +9 stay 0
FBUF    EQU PBUF+10         ; its inside pixels (enclosed paper; collectables), 8 rows
PAGE_F  EQU 25              ; bank 12 upper (in the .nex): FILLM 0x2000 (8 bytes per opaque code
FILLM   EQU 0x2000          ; 15-190: the enclosed paper of the object, from profile `fills`),
FILLC   EQU 0x2600          ; FILLC per code: inside colour as a pixel byte (0 = automatic)
V_HASF  EQU 0x008C          ; the object being drawn has inside pixels (ofill; odraw clears it)
V_FPIX  EQU 0x008D          ; their pixel byte (both nibbles)
X8T     EQU 0x4C00          ; page 28 at slot 2 (render start): nibble-expansion tables, 4 x 256
V_CLRF  EQU 0x0089          ; diagnostic: the frame-start clear of $C8 bit 0 did not take (read back 1)
V_BCOL  EQU 0x008A
V_DCNT  EQU 0x008B          ; diagnostic: poll counter          ; diagnostic: the border colour of this frame (restored after a deferred commit)
V_X8    EQU 0x0088          ; 1 = X8T built (page 28 is not in the .nex: built at the first render)
V_IA    EQU 0x0038          ; cell hooks: A at entry
V_IBC   EQU 0x0039
V_TOK   EQU 0x003B          ; tilemap built this render (scroll a multiple of 8)
V_BACK  EQU 0x003C          ; map being built: 0x00 or 0x05 (page-14 high byte)
V_SP3   EQU 0x003D          ; render end: game SP
V_MSB   EQU 0x003F          ; scroll the shadow map / the map on screen was built with (FF none)
V_MSD   EQU 0x0040
V_KK    EQU 0x0041          ; screen char row - 2
V_K     EQU 0x0042          ; cell row
V_COL   EQU 0x0043
V_CUR   EQU 0x0044          ; stamp of this render / the previous one
V_PRV   EQU 0x0045
V_INKR  EQU 0x0046          ; ink index: rainbow-class objects / item-class objects
V_INKI  EQU 0x0047
V_OL    EQU 0x0048          ; key: O, M1, M2, inks
V_HAS   EQU 0x004C
V_VICT  EQU 0x004D
V_ICY   EQU 0x004E          ; s_ov: carry at entry
V_IHL2  EQU 0x004F          ; s_it: HL at entry
V_FMAX  EQU 0x0051          ; figure sprites allowed (128)
V_OCC   EQU 0x0052
V_PROBE EQU 0x0053
V_NROWS EQU 0x0054
V_CINK  EQU 0x0055
V_SP4   EQU 0x0056          ; game SP in hooks with an own stack
V_CMD   EQU 0x0058
V_CQ    EQU 0x0059          ; 2 bytes
V_PASS  EQU 0x005B
V_CLS   EQU 0x005C
V_FLG   EQU 0x005D
V_TT    EQU 0x005E
V_MAPHI EQU 0x005F
V_OHL   EQU 0x0060
V_CTP   EQU 0x0062
V_ROWA  EQU 0x0064
V_TDP   EQU 0x0066
V_S8    EQU 0x0068
V_SPC   EQU 0x0069          ; obuild: SP while clearing (word)
V_LTP   EQU 0x006B          ; LASTT pointer (word)
V_TATR  EQU 0x006D          ; map attribute (palette offset << 4)
V_RB    EQU 0x006E          ; TILES + 32k (word)
V_OMP   EQU 0x0070          ; OCCM pointer low byte
V_OMB   EQU 0x0071          ; mask bits left
V_DIAG  EQU 0x0072          ; 1 = diagnostic build (border colours)
V_FRUN  EQU 0x0073          ; diagnostic: a game frame is running
V_DBC   EQU 0x0074          ; diagnostic: BC (word)
RS_LINE EQU 240             ; render end at or past this line: commit at once (if it fits before line 16)
V_PEND  EQU 0x0080          ; 1 = this render's commit is still to do (deferred to the next interrupt)
V_N58   EQU 0x0081          ; (58850) at the render end (play-area rows; the deferred commit clips with it)
; music (2026-10-19): the game's AY player runs up to 3 times per game frame; at 28 MHz those ticks came
; within a few ms. Its register writes (the one AY routine 0xD6D4 in bank 1) are queued per tick
; (a tick starts at the player entry 0xD4DE) and sent to the chip one tick per interrupt.
V_AYR   EQU 0x0082          ; oldest queued tick (slot 0-3)
V_AYN   EQU 0x0083          ; ticks queued (0-4)
V_AYO   EQU 0x0084          ; 1 = the newest queued tick is open for writes
V_AYW   EQU 0x0085          ; slot being written
V_AYSP  EQU 0x0086          ; game SP in the AY hooks (word)
AYQ     EQU 0x1FC0          ; page 26: 4 slots x 16 bytes: R0-R13 values, mask regs 0-7, mask regs 8-13
                            ; (bit 7 = the lowest register)
CODE2   EQU 0x1F10          ; fourth code block (page 26, up to 0x1FFF)
CODE4   EQU 0x0D60          ; third code block (page 26, up to 0x0DFF)
CODE3   EQU 0x0E60          ; second code block (page 26, up to 0x0EFF: the tail of WBM's page)

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
        jp s_limp
e_ay:   nextreg 0x50,PAGE_S         ; site 0xD6D4 (bank 1, interrupts off): queue the AY write
        jp s_ay
e_ps:   nextreg 0x50,PAGE_S         ; site 0xD4DE (bank 1): the AY player starts a tick
        jp s_ps
x_ay:   nextreg 0x50,0xFF
        ld bc,0xBFFD                ; BC as the original routine leaves it
        ret
x_ps:   nextreg 0x50,0xFF
        ld hl,0x5C59                ; the replaced LD HL,0x5C59
        jp 0xD4E1
x_lrun: nextreg 0x50,0xFF
        ld a,(48768)
        jp 65175
x_lskip:
        nextreg 0x50,0xFF
        jp 65274
e_off1: nextreg 0x15,0              ; site 65076 CALL 23643 (play state ended: death, continue,
        nextreg 0x6B,0              ; round end, game over): sprites + tilemap off until the next
        nextreg 0x7F,1              ; commit; tile cache flushed at the next render (graphics may
        jp 23643                    ; change before play resumes)
e_off2: nextreg 0x15,0              ; site 65029 CALL 23698 (main loop (re)start)
        nextreg 0x6B,0
        nextreg 0x7F,1
        jp 23698
e_hx:   nextreg 0x07,0              ; site 65274 (POP AF / EI / RET): back to 3.5 MHz for the
        nextreg 0x50,PAGE_S         ; main loop (its timing stays the original's). A is free here.
        jp dfend                    ; diagnostic build: frame end (then x_hx; no stack use)
x_hx:   nextreg 0x50,0xFF
        pop af
        ei
        ret
e_bt:   nextreg 0x50,PAGE_S         ; site 60853: base tile into a back-buffer cell
        jp s_bt
e_ov:   nextreg 0x50,PAGE_S         ; site 60839: opaque object tile
        jp s_ov
e_it:   nextreg 0x50,PAGE_S         ; site 60965: masked object
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
; --- render-end / deferred commit control (2026-10-19): read-only code in the alt ROM (slot 1);
; slot 0 = page 26 here. commit (page 26) maps store pages at slot 1 but leaves it as $FF before
; returning, so it can be called from here.
; render end: commit now if the beam is below the play area with room for the whole commit, else
; at the next interrupt (s_lim, line 248: bottom border) - never wait for the beam (2026-10-19: the
; raster wait cost 3.4 ms per game frame on average, up to 10 ms).
s_re:   ld (V_HL3),hl               ; HL and BC are live here; A and F are not (SUB 160 follows)
        ld (V_BC3),bc
        ld (V_DE3),de
        ld (V_SP3),sp               ; own stack (page 26)
        ld sp,STK
        ld a,(58850)
        ld (V_N58),a
        ld a,1
        ld (V_PEND),a
        call rsafe
.rs:    call c,commit               ; (unit-test control: CALL = commit at once wherever the beam is)
        ld sp,(V_SP3)
        ld hl,(V_HL3)
        ld bc,(V_BC3)
        ld de,(V_DE3)
        ld a,(58850)
        jp x_re

; s_int: every interrupt (site 65172, AF already pushed): own stack, the interrupted code's BC DE HL
; kept. A commit deferred from the render end runs now (line 248, bottom border) at 28 MHz; then one
; queued AY tick goes to the chip (two when 3+ are queued: catching up after a frame overran).
s_int:  ld (V_SP4),sp
        ld sp,STK
        push bc
        push de
        push hl
        ld a,(V_PEND)
        or a
        jr z,.nc
        nextreg 0x07,3
        call dcom
        nextreg 0x07,0
.nc:    call aytick
        pop hl
        pop de
        pop bc
        ld sp,(V_SP4)
        jp s_lim

; AY write hook (A = register, D = value; interrupts off): every register kept; BC = 0xBFFD on return.
s_ay:   ld (V_AYSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        call aywr
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_AYSP)
        jp x_ay
; player entry: a new tick (slot) opens
s_ps:   ld (V_AYSP),sp
        ld sp,STK
        push af
        push bc
        push de
        call ayopen
        pop de
        pop bc
        pop af
        ld sp,(V_AYSP)
        jp x_ps

aywr:   cp 14
        jr c,.q
        ld bc,0xFFFD                ; not a sound register: to the chip at once, as the original
        out (c),a
        ld b,0xBF
        out (c),d
        ret
.q:     ld e,a
        ld a,(V_AYO)
        or a
        call z,ayopen               ; a write outside a tick (e.g. the silence routine): its own slot
        ld a,(V_AYW)
        call ayslot
        ld a,l
        add a,e
        ld l,a
        ld (hl),d
        ld a,l                      ; mask byte: slot + 14 (+1 for registers 8-13)
        sub e
        add a,14
        ld l,a
        ld a,e
        cp 8
        jr c,.m
        inc l
        sub 8
.m:     add a,low BITS
        ld c,a
        ld b,high BITS
        ld a,(bc)
        or (hl)
        ld (hl),a
        ret

ayopen: ld a,(V_AYN)
        cp 4
.fl:    call z,ayplay               ; queue full: the oldest tick to the chip now
        ld a,(V_AYR)
        ld hl,V_AYN
        add a,(hl)
        and 3
        ld (V_AYW),a
        inc (hl)
        call ayslot
        ld a,l
        add a,14
        ld l,a
        xor a
        ld (hl),a
        inc l
        ld (hl),a
        inc a
        ld (V_AYO),a
        ret

aytick: ld a,(V_AYN)
        or a
        ret z
        call ayplay
        ld a,(V_AYN)
        cp 3
        call nc,ayplay
        ld a,(V_AYN)
        or a
        ret nz
        ld (V_AYO),a                ; queue empty: nothing open
        ret

; the oldest queued tick to the chip: its written registers in order 0-13
ayplay: ld a,(V_AYR)
        call ayslot
        ld a,l
        add a,14
        ld l,a
        ld d,(hl)
        inc l
        ld e,(hl)
        ld a,l
        sub 15
        ld l,a
        xor a
.lp:    sla e
        rl d
        jr nc,.n
        ld bc,0xFFFD
        out (c),a
        ld b,0xBF
        ld c,(hl)
        push af
        ld a,c
        ld c,0xFD
.o:     out (c),a                   ; (unit-test control: NOPs = nothing reaches the chip)
        pop af
.n:     inc l
        inc a
        cp 14
        jr c,.lp
        ld a,(V_AYR)
        inc a
        and 3
        ld (V_AYR),a
        ld hl,V_AYN
        dec (hl)
        ret

ayslot: add a,a                     ; A = slot -> HL = AYQ + 16 * slot
        add a,a
        add a,a
        add a,a
        add a,low AYQ
        ld l,a
        ld h,high AYQ
        ret

; dcom: the deferred commit (from s_lim). Dropped when a non-play screen came since the render (the
; sprites-off stubs set NextReg $7F; render start clears it): its sprites must not come back on.
dcom:   ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        or a
        jr z,.c
        xor a
        ld (V_PEND),a
        ret
.c:     ld a,1                      ; diagnostic build: blue border during a deferred commit
        call dcol
        call commit
        ld a,(V_BCOL)               ; back to this frame's colour (yellow / magenta stay until the next frame)
        jp dcol

; rsafe: carry set = commit now: the beam (active video line, NextReg $1E/$1F; 0 = first pixel row)
; is at or past line RS_LINE - this frame will miss the interrupt at line 248 (interrupts are off
; until the frame ends; RS_LINE leaves 8 lines for the rest of the frame), or the render ended in the
; first ~4 ms after it - and the lines left before line 16 of the next frame (311 + 16 - L, 128K
; timing) exceed what the commit needs (under one line per sprite + 17 for the map copy: V_S + 20). Otherwise NC: the commit runs at the next interrupt (line 248, bottom
; border) - the same displayed frame as a commit below the play area, but outside the game frame.
rsafe:  ld bc,0x243B
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        and 1
        ld h,a
        ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        ld l,a
        ld de,RS_LINE
        or a
        sbc hl,de
        jr c,.no                    ; L < RS_LINE: the interrupt comes first
        ex de,hl
        ld hl,327-20-RS_LINE        ; 128K timing: 311 lines a frame
        or a
        sbc hl,de
        jr c,.no
        ld a,(V_S)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        jr c,.no
        scf
        ret
.no:    or a
        ret

; X8T (page 28, mapped at slot 2 here): X8T + 256k + v = nibbles of bits 7-2k (high) / 6-2k (low)
; of v, 0xF per set bit. Built once at the first render start (page 28 is not in the .nex).
x8bld:  nextreg 0x52,PAGE_SH
        ld hl,X8T
.v:     ld c,l                      ; v = L
        ld b,4
.kk:    xor a
        sla c
        jr nc,.h
        or 0xF0
.h:     sla c
        jr nc,.l
        or 0x0F
.l:     ld (hl),a
        inc h
        djnz .kk
        ld h,high X8T
        inc l
        jr nz,.v
        nextreg 0x52,10
        ld a,1
        ld (V_X8),a
        ret
; --- diagnostic build, frame start / end (alt ROM; jumped to from s_lim / e_hx, no stack use).
; Frame start: wait (up to 255 polls) until the INT signal ($22 bit 7) has dropped, then clear the
; ULA interrupt flag ($C8 bit 0) and read it back: still 1 = the clear did not take (V_CLRF).
; Frame end: $C8 bit 0 set = an interrupt came during the frame = overrun -> YELLOW, or MAGENTA when
; the frame-start clear had not taken (the flag then proves nothing). Black otherwise. The colour
; stays until the next frame start (a deferred commit shows blue, then restores it).
dfst:   ld a,(V_DIAG)
        or a
        jp z,x_lrun
        ld (V_FRUN),a
        ld (V_DBC),bc
        ld bc,0x243B
        ld a,0x22
        out (c),a
        inc b
        ld a,255
        ld (V_DCNT),a
.w:     in a,(c)                    ; (A and F are dead here: x_lrun reloads A, CP 3 follows)
        rla
        jr nc,.lo
        ld a,(V_DCNT)
        dec a
        ld (V_DCNT),a
        jr nz,.w
.lo:    nextreg 0xC8,1
        dec b
        ld a,0xC8
        out (c),a
        inc b
        in a,(c)
        and 1
        ld (V_CLRF),a
        ld bc,(V_DBC)
        xor a
        ld (V_BCOL),a
        out (0xFE),a
        jp x_lrun
dfend:  ld a,(V_FRUN)
        or a
        jp z,x_hx
        xor a
        ld (V_FRUN),a
        ld (V_DBC),bc
        ld bc,0x243B
        ld a,0xC8
        out (c),a
        inc b
        in a,(c)
        ld bc,(V_DBC)
        and 1
        jp z,x_hx
        ld a,(V_CLRF)
        or a
        ld a,6                      ; yellow: overran
        jr z,.y
        ld a,3                      ; magenta: flag unreliable this frame
.y:     ld (V_BCOL),a
        out (0xFE),a
        jp x_hx
; (tcommit only maps slots 2 / 3: it runs from the alt ROM, called by commit with slot 1 = $FF)
; tcommit: show the map built this render (or switch the layer off), clip it to the play area
tcommit:
        ld a,(V_TOK)
        or a
        jr z,.off
        nextreg 0x52,PAGE_SH        ; shadow rows -> map rows 6-25, columns 4-35 (2 bytes each)
        nextreg 0x53,PAGE_TM
        ld hl,0x4000
        ld de,0x6000+(6*40+4)*2
        ld a,20
.cr:    ld bc,64
        ldir
        ex de,hl
        ld bc,16                    ; to column 4 of the next map row
        add hl,bc
        ex de,hl
        dec a
        jr nz,.cr
        nextreg 0x52,10
        nextreg 0x53,11
        ld a,(V_MSB)
        ld (V_MSD),a
        nextreg 0x6E,0x80           ; map at 0x0000 in bank 7
        nextreg 0x6F,0x80+high TDEF
        nextreg 0x1C,8              ; tilemap clip: x 16-143 (2-pixel units), y 48 .. 47 + N
        nextreg 0x1B,16
        nextreg 0x1B,143
        nextreg 0x1B,48
        ld a,(V_N58)
        add a,47
        nextreg 0x1B,a
        nextreg 0x6B,0x81           ; tilemap on: 40x32, 2-byte entries (palette offset per tile),
                                    ; tilemap over the ULA (bit 0; the per-tile bit is 0 as well)
        ret
.off:   nextreg 0x6B,0
        ld a,0xFF
        ld (V_MSD),a
        ret
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
        ld a,(V_X8)
        or a
        call z,x8bld
        call obuild
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP4)
        ld iy,27964
        jp x_rs

s_limp: jp s_int                     ; every interrupt: deferred commit, one AY tick (alt ROM code)
s_lim:  ld a,(V_TICK)
        inc a
        cp LIMIT
        jr c,.skip
        xor a
        ld (V_TICK),a
        nextreg 0x07,3              ; 28 MHz for the game frame
        jp dfst                     ; diagnostic build: frame start (then x_lrun; no stack use)
.skip:  ld (V_TICK),a
        jp x_lskip

; commit: the tilemap, then every staged piece's patterns + attributes in one burst (sprite by
; sprite: pattern, then its attributes; pieces top to bottom, so a commit that the beam catches up
; with has done the rows the beam reaches first), then hide the sprites of the previous render
commit: xor a
        ld (V_PEND),a
        call tcommit
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
        ld c,0x5B                   ; 64 bytes (top half; the bottom stays zero) by OUTI: ports 0x5B
        ld a,8                      ; and 0x57 decode the low byte only, so B is free (16 T a byte
.pt:    outi                        ; instead of OTIR's 21; 2026-10-19)
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        dec a
        jr nz,.pt
        ld a,(V_CS)                 ; 0x303B bits 6:0 = the sprite for port 0x57 (the same write moves
        ld bc,0x303B                ; the pattern pointer: its upload is done)
        out (c),a
        ld c,0x57                   ; its 5 attribute bytes ($35-$39 order) from ATTRB
        ex de,hl
        outi
        outi
        outi
        outi
.a5:    outi                        ; (unit-test control: NOPs = attribute 4 not written)
        ex de,hl
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
        ld a,(V_S)
        ld (V_PREV),a
.hide:  cp h
        jr nc,.done
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .hide
.done:  ret

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
        ld a,(V_SP+1)               ; class without outline (CLASSTAB bit 0, e.g. the thrown rainbow):
        ld l,a                      ; part of the store key (bit 1), so a stream drawn from another
        ld h,high CLASSTAB          ; class never shares its patterns
        ld a,(hl)
        and 1
        add a,a
        ld hl,V_KEY
        or (hl)
        ld (hl),a
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
        call nooutl                 ; classes without outline: outline pixels (2) -> transparent (0)
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
        and 0xF0                    ; bit 0 = no-outline flag, not attr2's X8
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

; --- objects (rainbow pieces, fruit, flowers, any object the game puts in a back-buffer cell) on the
; tilemap layer. Cell hooks keep per cell: the map tile (background), the opaque object (60839) and up
; to four masked objects (60965) in draw order. Render start builds the back tilemap (page 14,
; slot 3): one tile per visible object cell, composed from the game's own graphics with a 1-pixel
; black border (cached by content). Band end: the cell's map tile rows + its colour on the ULA, so
; the objects never leave a square. Render end: the built map is shown (NextReg $6E), raster-synced.
; Cell hooks: own stack (SP at these sites may be a data pointer). DE = back-buffer cell
; 0x9F00 + 256*k + col; D outside 0x9F-0xB4 or E >= 32 = not a cell (ignored).

; HL = TILES + cell; V_OCC = OBJO | OBJM1 before the change. RCNT follows the cell's occupancy;
; a tile assigned this render (CTILE) is dropped and the cell's entry cleared in both tilemaps.
oafter: ld (V_OHL),hl
        ld a,h
        add a,high (OBJO-TILES)
        ld h,a
        ld a,(hl)
        inc h
        inc h
        inc h
        or (hl)
        ld c,a                      ; occupied now
        ld hl,(V_OHL)
        push bc
        call ocrow
        pop bc
        add a,low RCNT
        ld e,a
        ld d,high RCNT
        ld a,(V_OCC)
        or a
        jr nz,.was
        or c
        jr z,.ct
        ld a,(de)
        inc a
        ld (de),a
        call .tog
        jr .ct
.was:   ld a,c
        or a
        jr nz,.ct
        ld a,(de)
        dec a
        ld (de),a
        call .tog
        jr .ct
.tog:   ld hl,(V_OHL)               ; occupancy changed: flip the cell's bit in OCCM
        call ocrow
        add a,a
        add a,a
        ld e,a
        ld a,l
        and 31
        ld c,a
        rrca
        rrca
        rrca
        and 3
        add a,e
        add a,low OCCM
        ld e,a
        ld d,high OCCM
        ld a,c
        and 7
        add a,low BITS
        ld l,a
        ld h,high BITS
        ld a,(de)
.tg:    xor (hl)                    ; (unit-test control: NOP = mask not kept)
        ld (de),a
        ret
.ct:    ld hl,(V_OHL)
        ld a,h
        add a,high (CTILE-TILES)
        ld h,a
        ld a,(hl)
        or a
        ret z
        ld (hl),0                   ; stale this render: the cell is shown as drawn
        ld hl,(V_OHL)
        call ocrow
        ld e,a                      ; E = k
        ld a,l
        and 31
        ld d,a                      ; D = col
        nextreg 0x52,PAGE_SH        ; shadow map being built (page 28 at slot 2, row kk at kk*64)
        ld a,(V_MSB)
        ld b,0
        call .clr
        nextreg 0x52,10
        nextreg 0x53,PAGE_TM        ; map on screen (page 14 at slot 3, entry ((kk+6)*40+col+4)*2)
        ld a,(V_MSD)
        ld b,1
        call .clr
        nextreg 0x53,11
        ret
.clr:   cp 0xFF                     ; A = scroll that map was built with (FF: none); E = k, D = col
        ret z
        rrca
        rrca
        rrca
        and 31
        ld c,a
        ld a,e
        sub c
        jr nc,.c1
        add a,22
.c1:    cp 20
        ret nc                      ; off screen in that map
        dec b
        jr z,.dm
        ld l,a                      ; shadow: 0x4000 + kk*64 + col*2
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,d
        add a,a
        add a,l
        ld l,a
        ld a,h
        add a,0x40
        ld h,a
        jr .cz
.dm:    add a,6
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc                   ; *40
        ld a,d
        add a,4
        ld c,a
        ld b,0
        add hl,bc
        add hl,hl                   ; 2 bytes per entry
        ld a,h
        add a,0x60
        ld h,a
.cz:    ld (hl),0
        inc hl
        ld (hl),0
        ret

s_bt:   ld (V_IA),a                 ; 60853: base tile A -> TILES = A, known, no objects
        ld (V_SP4),sp
        ld sp,STK
        push bc
        push de
        push hl
        call ocell
        jr nc,.out
        nextreg 0x51,PAGE_T
        ld a,(V_IA)
        ld (hl),a
        call ocpre
        ld (hl),0                   ; OBJO
        inc h
        inc h
        inc h
        ld (hl),0                   ; OBJM1
        inc h
        inc h
        inc h
        ld (hl),0                   ; OBJM2
        inc h
        inc h
        inc h
        ld (hl),0x80                ; FLAGS: tile known, item ink unknown
        call ocpost
        nextreg 0x51,0xFF
.out:   pop hl
        pop de
        pop bc
        ld sp,(V_SP4)
        ld a,(V_IA)
        add a,a                     ; the replaced ADD A,A / LD L,A / LD H,0 (carry: JP C follows)
        ld l,a
        ld h,0
        jp x_bt

; ocpre: HL = TILES + cell -> V_OCC = OBJO | OBJM1 (before), HL = OBJO + cell, (V_OHL) = TILES + cell
ocpre:  ld (V_OHL),hl
        ld a,h
        add a,high (OBJO-TILES)
        ld h,a
        ld a,(hl)
        inc h
        inc h
        inc h
        or (hl)
        dec h
        dec h
        dec h
        ld (V_OCC),a
        ret
ocpost: ld hl,(V_OHL)
        jp oafter

s_ov:   ld (V_IA),a                 ; 60839: opaque tile A (0xF700 + 8*(A-1)) over a blank cell:
        sbc a,a                     ; TILES = the map byte at BC', the object = A alone. Carry at
        ld (V_ICY),a                ; entry kept for the replaced DEC A.
        ld (V_SP4),sp
        ld sp,STK
        push bc
        push de
        push hl
        call ocell
        jr nc,.out
        exx                         ; map tile = the byte at BC' (all three callers)
        ld a,(bc)
        exx
        nextreg 0x51,PAGE_T
        ld (hl),a                   ; TILES
        call ocpre
        ld a,(V_IA)
        or a
        jr z,.uns
        cp 0xFF
        jr z,.uns
        push hl
        ld l,a
        ld h,high OCLASS
        ld a,(hl)
        pop hl
        call ocls
        jr c,.uns                   ; class: leave the cell as drawn
        or 0x80
        ld (V_FLG),a
        ld a,(V_IA)
        jr .wr
.uns:   ld a,0x80                   ; code 0 / 255 or class ULA -> FF (cell left as drawn)
        ld (V_FLG),a
        ld a,0xFF
.wr:    ld (hl),a                   ; OBJO (unit-test control: NOP = the object is not recorded)
        inc h
        inc h
        inc h
        ld (hl),0
        inc h
        inc h
        inc h
        ld (hl),0
        inc h
        inc h
        inc h
        ld a,(V_FLG)
        ld (hl),a                   ; FLAGS: known + the object's group bits
        call ocpost
        nextreg 0x51,0xFF
.out:   pop hl
        pop de
        pop bc
        ld sp,(V_SP4)
        ld a,(V_ICY)
.rla:   rla                         ; carry back (unit-test control: removed)
        ld a,(V_IA)
        dec a                       ; the replaced DEC A / LD L,A / LD H,0
        ld l,a
        ld h,0
        jp x_ov

s_it:   ld (V_IA),a                 ; 60965: masked object A (codes 1-14: 0xF600 + 16*(A-1)) drawn
        ld (V_IHL2),hl              ; over the cell: appended to the cell's masked list (4 max; a
        ld (V_SP4),sp               ; fifth, or another code -> FF: the cell is left as drawn)
        ld sp,STK
        push bc
        push de
        call ocell
        jr nc,.out
        nextreg 0x51,PAGE_T
        call ocpre
        ld a,(hl)
        inc a
        jp z,.done                  ; already FF
        ld a,(V_IA)
        dec a
        cp 14
        jr nc,.ff
        inc a
        ld c,a                      ; C = code (1-14)
        push hl
        add a,low MCLASS
        ld l,a
        ld h,high MCLASS
        ld a,(hl)
        pop hl
        push bc
        call ocls
        pop bc
        jr c,.ff                    ; class: leave the cell as drawn
        ld (V_FLG),a
        inc h
        inc h
        inc h                       ; OBJM1
        ld a,(hl)
        and 0xF0
        jr nz,.m1l
        ld a,c
        rlca
        rlca
        rlca
        rlca
        ld (hl),a
        jr .ok
.m1l:   ld a,(hl)
        and 0x0F
        jr nz,.m2
        ld a,(hl)
        or c
        ld (hl),a
        jr .ok
.m2:    inc h
        inc h
        inc h                       ; OBJM2
        ld a,(hl)
        and 0xF0
        jr nz,.m2l
        ld a,c
        rlca
        rlca
        rlca
        rlca
        ld (hl),a
        jr .ok
.m2l:   ld a,(hl)
        and 0x0F
        jr nz,.ff6
        ld a,(hl)
        or c
        ld (hl),a
        jr .ok
.ff6:   dec h
        dec h
        dec h
.ff:    ld hl,(V_OHL)               ; FF in OBJO
        ld a,h
        add a,high (OBJO-TILES)
        ld h,a
        ld (hl),0xFF
        jr .done
.ok:    ld hl,(V_OHL)               ; appended: the cell's FLAGS get the object's group bits
        ld a,h
        add a,high (FLAGS-TILES)
        ld h,a
        ld a,(V_FLG)
        or (hl)
        ld (hl),a
.done:  call ocpost
        nextreg 0x51,0xFF
.out:   pop de
        pop bc
        ld sp,(V_SP4)
        ld hl,(V_IHL2)
        ld a,(V_IA)
        dec a                       ; the replaced DEC A / ADD A,A x3 (60969 = the 4th ADD A,A)
        add a,a
        add a,a
        add a,a
        jp x_it

; --- render start: build the back tilemap. Own stack; IY free (LD IY,27964 follows); IX saved.
obuild: push ix
        ld bc,0x243B                ; cache flush requested (sprites-off hooks set NextReg $7F)?
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        or a
.fj:    jr z,.nf                    ; (unit-test control: JR = flush ignored)
        nextreg 0x7F,0
        nextreg 0x51,PAGE_T
        ld hl,STAMP
        ld b,NTILE
.fl:    ld (hl),0
        inc hl
        djnz .fl
.nf:    xor a
        ld (V_TOK),a
        ld a,(48782)
        and 7
        jp nz,.end                  ; scroll not a multiple of 8 (never seen): tilemap off
        inc a
        ld (V_TOK),a
        ld a,(V_FRM)                ; stamps: this render / the previous one (bit 7 set: 0 = free)
        or 0x80
        ld (V_CUR),a
        dec a
        or 0x80
        ld (V_PRV),a
        nextreg 0x51,PAGE_T
        nextreg 0x52,PAGE_SH
        nextreg 0x53,PAGE_TM
        ld (V_SPC),sp               ; clear the shadow map: 20 rows x 64 bytes at 0x4000
        ld sp,0x4000+20*64
        ld hl,0
        ld b,160
.cb:    push hl                     ; (unit-test control: NOPs = map not cleared)
        push hl
        push hl
        push hl
        djnz .cb
        ld sp,(V_SPC)
        ld a,(48782)
        ld (V_MSB),a
        rrca
        rrca
        rrca
        and 31
        ld (V_S8),a
        xor a
        ld (V_KK),a
.row:   ld a,(V_KK)                 ; screen char row R = kk + 2, visible while 8*kk < N
        add a,a
        add a,a
        add a,a
        ld hl,58850
        cp (hl)
        jp nc,.tail
        ld a,(V_S8)                 ; k = (s/8 + kk) mod 22
        ld hl,V_KK
        add a,(hl)
        cp 22
        jr c,.k1
        sub 22
.k1:    ld (V_K),a
        add a,low RCNT
        ld l,a
        ld h,high RCNT
        ld a,(hl)
        or a
        jp z,.nrow
        ld a,(V_K)                  ; row base TILES + 32k; visit the occupied cells only (OCCM)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,TILES
        add hl,de
        ld (V_RB),hl
        ld a,(V_K)
        add a,a
        add a,a
        add a,low OCCM
        ld (V_OMP),a
        xor a
        ld (V_COL),a
.q:     ld a,(V_OMP)
        ld l,a
        ld h,high OCCM
        ld a,(hl)
        or a
        jr z,.qn
.b:     add a,a
        ld (V_OMB),a
        call c,.cell
        ld a,(V_COL)
        inc a
        ld (V_COL),a
        and 7
        ld a,(V_OMB)
        jr nz,.b
        jr .qx
.qn:    ld a,(V_COL)
        add a,8
        ld (V_COL),a
.qx:    ld hl,V_OMP
        inc (hl)
        ld a,(V_COL)
        cp 32
        jr c,.q
        jp .nrow
.cell:  ld hl,(V_RB)
        ld a,(V_COL)
        add a,l
        ld l,a
        ld (V_OHL),hl
        ld a,h
        add a,high (OBJO-TILES)
        ld h,a
        ld a,(hl)
        ld (V_OL),a                 ; O
        inc h
        inc h
        inc h
        ld c,(hl)                   ; M1
        inc h
        inc h
        inc h
        ld b,(hl)                   ; M2
        inc h
        inc h
        inc h
        ld e,(hl)                   ; FLAGS
        inc h
        inc h
        inc h
        ld (hl),0                   ; CTILE = 0 unless a tile is assigned below
        ld (V_CTP),hl
        or c
        ret z                  ; no object
        ld a,(V_OL)
        inc a
        ret z                  ; FF: left as drawn
        bit 7,e
        ret z                  ; background unknown (cell drawn before the hooks saw it)
        ld (V_OL+1),bc              ; M1, M2
        ld a,e
        ld (V_FLG),a
        ld a,(V_FLG)                ; V_HAS from the FLAGS group bits (kept by the cell hooks):
        rrca                        ; bit 0 rainbow group, 1 item group, 3 fixed ink
        rrca
        rrca
        rrca
        and 3
        ld c,a
        ld a,(V_FLG)
        and 0x40
        rrca
        rrca
        rrca
        or c
        ld (V_HAS),a
        ld a,(V_HAS)
        bit 2,a
        ret nz
        ld hl,(V_OHL)               ; ink pixel index from the attribute buffer (0xB500 + cell)
        ld a,h
        sub high TILES
        add a,0xB5
        ld h,a
        ld a,(hl)
        call oinkx
        ld (V_INKR),a
        ld c,a
        ld a,(V_HAS)
        and 3
        cp 2
        jr nz,.r
        ld a,c                      ; items only: their ink, remembered for when a rainbow joins
        ld (V_INKI),a
        ld hl,(V_CTP)
        ld a,h
        sub high (CTILE-FLAGS)
        ld h,a
        ld a,(hl)
        and 0xF0
        or c
        ld (hl),a
        jr .k
.r:     cp 3
        ld a,c
        jr nz,.ri
        ld a,(V_FLG)                ; rainbow + item: the item's remembered ink, else the cell's
        and 15
        jr nz,.ri
        ld a,c
.ri:    ld (V_INKI),a
.k:     ld a,(V_HAS)                ; one ink for the whole tile (one group, no fixed ink): the
        and 3                       ; tile holds the ink as pixel 2 and the map entry's palette
        cp 3                        ; offset selects the colour (bank n: pixel 2 = ink index n)
        jr z,.fix
        ld a,(V_HAS)
        bit 3,a
        jr nz,.fix
        ld a,(V_INKR)
        rlca
        rlca
        rlca
        rlca
        ld (V_TATR),a
.vi:    ld a,2                      ; (unit-test control: NOPs = the ink stays in the pixels)
        ld (V_INKR),a
        ld (V_INKI),a
        xor a
        jr .k2
.fix:   xor a                       ; several inks: in the pixels, palette offset 0
        ld (V_TATR),a
        ld a,(V_INKI)
        rlca
        rlca
        rlca
        rlca
        ld hl,V_INKR
        or (hl)
.k2:    ld (V_OL+3),a               ; key = O, M1, M2, (0 | item ink << 4 | rainbow ink)
        ld hl,(V_OHL)               ; the cell's tile last time still holds this key?
        ld de,LASTT-TILES
        add hl,de
        ld (V_LTP),hl
        ld a,(hl)
        or a
        jr z,.slow
        ld (V_PROBE),a
        ld l,a
        ld h,high STAMP
        ld a,(hl)
        or a
        jr z,.slow
        ld a,(V_PROBE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,KEYS
        add hl,de
        ld de,V_OL
        ld b,4
.fc:    ld a,(de)
        cp (hl)
        jr nz,.slow
        inc de
        inc hl
        djnz .fc
        ld a,(V_PROBE)
        ld l,a
        ld h,high STAMP
        ld a,(V_CUR)
        ld (hl),a
        ld a,l
        jr .got
.slow:  call olook                  ; A = tile number (0: no free entry)
        ld hl,(V_LTP)
        ld (hl),a
.got:   ld hl,(V_CTP)
        ld (hl),a
        or a
        ret z
        ld c,a
        ld a,(V_KK)                 ; shadow entry 0x4000 + kk*64 + col*2: tile, attribute
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_COL)
        add a,a
        add a,l
        ld l,a
        ld a,h
        add a,0x40
        ld h,a
        ld (hl),c
        inc hl
        ld a,(V_TATR)
        ld (hl),a
        ret
.nrow:  ld a,(V_KK)
        inc a
        ld (V_KK),a
        cp 20
        jp c,.row
.tail:  ld a,(V_KK)                 ; cell rows not on screen this render (kk 20-21, below the play
        cp 22                       ; area): no tile assigned (unit-test control: JR = left stale)
.tj:    jr nc,.end
        ld a,(V_S8)
        ld hl,V_KK
        add a,(hl)
        cp 22
        jr c,.t1
        sub 22
.t1:    ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CTILE
        add hl,de
        ld b,32
.t2:    ld (hl),0
        inc hl
        djnz .t2
        ld hl,V_KK
        inc (hl)
        jr .tail
.end:   nextreg 0x51,0xFF
        nextreg 0x52,10
        nextreg 0x53,11
        pop ix
        ret

; tile cache: key V_OL (4 bytes) -> A = tile number 1..NTILE-1 (0: none free). 16 probes from
; 1 + (hash & 127). Hit: stamp = this render. Miss: the first probed entry not used this render or
; the previous one (that one is on screen until the commit) is rebuilt.
olook:  ld a,(V_OL)
        ld hl,V_OL+1
        ld b,(hl)
        add a,b
        add a,b
        add a,b
        inc hl
        ld b,(hl)
        add a,b
        add a,b
        rlca
        inc hl
        add a,(hl)
        add a,(hl)
        add a,(hl)
        and 127
        inc a
        ld (V_PROBE),a
        xor a
        ld (V_VICT),a
        ld b,16
.p:     push bc
        ld a,(V_PROBE)
        ld l,a
        ld h,high STAMP
        ld a,(hl)
        or a
        jr z,.free
        ld c,a
        ld a,(V_PROBE)              ; key at KEYS + 4*e
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,KEYS
        add hl,de
        ld de,V_OL
        ld b,4
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.ne
        inc de
        inc hl
        djnz .cmp
        pop bc                      ; hit
        ld a,(V_PROBE)
        ld l,a
        ld h,high STAMP
        ld a,(V_CUR)
        ld (hl),a
        ld a,l
        ret
.ne:    ld a,c
        ld hl,V_CUR
        cp (hl)
        jr z,.nx
        inc hl
        cp (hl)
.np:    jr z,.nx                    ; used last render = on screen (unit-test control: NOPs)
.free:  ld a,(V_VICT)
        or a
        jr nz,.nx
        ld a,(V_PROBE)
        ld (V_VICT),a
.nx:    pop bc
        ld a,(V_PROBE)
        inc a
        cp NTILE
        jr c,.p2
        ld a,1
.p2:    ld (V_PROBE),a
        djnz .p
        ld a,(V_VICT)
        or a
.vic:   ret z                       ; none free: the cell is left as drawn
        ld l,a
        ld h,high STAMP
        ld a,(V_CUR)
        ld (hl),a
        ld a,l
        ld (V_PROBE),a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,KEYS
        add hl,de
        ex de,hl
        ld hl,V_OL
        ld bc,4
        ldir
        call ocompd
        ld a,(V_PROBE)
        ret

; compose tile V_PROBE (page 14 at slot 3: 0x6000 + TDEF + 32*e) from V_OL: rainbow-class objects
; first (opaque object, then the masked ones in draw order), item-class objects on top. Each object:
; border pixels (8-neighbours of its pixels inside the cell) -> 1 (black), its pixels -> its ink.
ocomp:  ld a,(V_PROBE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x6000+TDEF
        add hl,de
        ld (V_TDP),hl
        ld b,32
.z:     ld (hl),0
        inc hl
        djnz .z
        xor a
        ld (V_PASS),a               ; pass 0: rainbow class, pass 1: item class
.pass:  ld a,(V_OL)
        or a
        jr z,.pm
        ld l,a
        ld h,high OCLASS
        ld a,(hl)
        call .sel
        jr nz,.pm
        ld a,(V_OL)                 ; opaque object rows: 0xF700 + 8*(A-1)
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xF700
        add hl,de
        ld de,PBUF+1
        ld bc,8
        ldir
        call ofill                  ; collectables: their inside pixels (FBUF, V_HASF, V_FPIX)
        call odraw
.pm:    ld a,(V_OL+1)
        rrca
        rrca
        rrca
        rrca
        call .mo
        ld a,(V_OL+1)
        call .mo
        ld a,(V_OL+2)
        rrca
        rrca
        rrca
        rrca
        call .mo
        ld a,(V_OL+2)
        call .mo
        ld a,(V_PASS)
        inc a
        ld (V_PASS),a
        cp 2
        jr c,.pass
        ret
.mo:    and 15
        ret z
        ld c,a
        add a,low MCLASS
        ld l,a
        ld h,high MCLASS
        ld a,(hl)
        call .sel
        ret nz
        ld a,c                      ; masked object gfx rows: odd bytes of 0xF600 + 16*(code-1)
        dec a
        rlca
        rlca
        rlca
        rlca
        inc a
        ld l,a
        ld h,0xF6
        ld de,PBUF+1
        ld b,8
.mg:    ld a,(hl)
        ld (de),a
        inc l
        inc l
        inc de
        djnz .mg
        jp odraw
; class byte A: Z if the object belongs to this pass; sets V_CLS = class byte
.sel:   ld (V_CLS),a
        and 1                       ; rainbow group -> pass 0
.selx:  xor 1                       ; (unit-test control: XOR 0 = order reversed)
        ld b,a
        ld a,(V_PASS)
        cp b
        ret

; --- band hook (59547): the visible object cells on the band just blitted (screen char row R from
; (59522)) get their map tile's rows (only rows inside the play area) and, while the screen still
; shows the attribute-buffer value, the tile's colour. Then the replaced LD HL,(59522).
s_bend: ld (V_SP4),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,(V_TOK)
        or a
        jp z,.q
        ld hl,(59522)
        ld (V_ROWA),hl
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld l,a
        ld a,h
        and 0x18
        or l                        ; A = R
        sub 2
        cp 20
        jp nc,.q
        ld (V_KK),a
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(58850)
        sub c
        jp c,.q
        jp z,.q
        cp 8
        jr c,.n1
        ld a,8
.n1:    ld (V_NROWS),a
        ld a,(48782)
        rrca
        rrca
        rrca
        and 31
        ld hl,V_KK
        add a,(hl)
        cp 22
        jr c,.k1
        sub 22
.k1:    ld (V_K),a
        nextreg 0x51,PAGE_T
        add a,low RCNT
        ld l,a
        ld h,high RCNT
        ld a,(hl)
        or a
        jp z,.qm
        ld a,(V_K)                  ; occupied cells of the row (OCCM) with a tile this render
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,TILES
        add hl,de
        ld (V_RB),hl
        ld a,(V_K)
        add a,a
        add a,a
        add a,low OCCM
        ld (V_OMP),a
        xor a
        ld (V_COL),a
.oq:    ld a,(V_OMP)
        ld l,a
        ld h,high OCCM
        ld a,(hl)
        or a
        jr z,.oqn
.ob:    add a,a
        ld (V_OMB),a
        call c,.cell
        ld a,(V_COL)
        inc a
        ld (V_COL),a
        and 7
        ld a,(V_OMB)
        jr nz,.ob
        jr .oqx
.oqn:   ld a,(V_COL)
        add a,8
        ld (V_COL),a
.oqx:   ld hl,V_OMP
        inc (hl)
        ld a,(V_COL)
        cp 32
        jr c,.oq
        jp .qm
.cell:  ld hl,(V_RB)
        ld a,(V_COL)
        add a,l
        ld l,a
        ld (V_OHL),hl
        ld hl,(V_OHL)
        ld a,h
        add a,high (CTILE-TILES)
        ld h,a
        ld a,(hl)
        or a
        ret z
        ld hl,(V_OHL)               ; tile -> background override -> source rows
        ld l,(hl)
        ld h,high BGOVR
        ld a,(hl)
        ld (V_TT),a
        and 127
        ld l,a
        ld h,0x10
        add hl,hl
        add hl,hl
        add hl,hl                   ; 0x8000 + 8*(t & 127)
        ex de,hl
        ld hl,(V_ROWA)
        ld a,(V_COL)
        or l
        ld l,a
        ld a,(V_NROWS)
        ld b,a
        ld a,(V_TT)
        rla
        jr c,.fm
.fr:    ld a,(de)
.wt:    ld (hl),a                   ; (unit-test control: NOP = background not drawn)
        inc e
        inc h
        djnz .fr
        jr .fa
.fm:    ld a,(de)                   ; mirrored (as 60853: bit-reversal table page 0xF5)
        push hl
        ld h,0xF5
        ld l,a
        ld a,(hl)
        pop hl
        ld (hl),a
        inc e
        inc h
        djnz .fm
.fa:
        ld a,(V_KK)                 ; attribute 0x5800 + 32R + col
        add a,2
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_COL)
        or l
        ld l,a
        ld a,h
        add a,0x58
        ld h,a
        ex de,hl
        ld hl,(V_OHL)               ; attribute buffer 0xB500 + cell
        ld a,h
        sub high TILES
        add a,0xB5
        ld h,a
        ld a,(de)
        cp (hl)
        ret nz                   ; a star set its own ink: keep it
        ld a,(V_TT)
        or 128
        ld l,a
        ld h,0xF2
        ld a,(hl)
        and 127
        ld (de),a
        ret
.qm:    nextreg 0x51,0xFF
.q:     pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP4)
        ld hl,(59522)
        jp x_bend
code_end:

; --- raster wait (page 26 0x0E60-0x0EFF)
        ORG CODE3
; diagnostic build: red border while a tile is composed
ocompd: ld a,2
        call dcol
        call ocomp
        xor a
        jp dcol
; ofcol: C = the code's inside colour (FILLC; 0 = automatic) -> V_FPIX. Automatic: one-ink tile
; (palette offset = the ink): pixel 3 = that palette bank's contrast colour; inks in the pixels:
; bright white inside black / blue / red / magenta items, black inside the others.
ofcol:  ld a,c
        or a
        jr nz,.s
        ld a,(V_TATR)
        or a
        ld a,0x33
        jr nz,.s
        ld a,(V_INKI)
        cp 8
        jr c,.n
        sub 7
.n:     cp 5
        ld a,0xFF
        jr c,.s
        ld a,0x11
.s:     ld (V_FPIX),a
        ret
; nooutl: the entry's new patterns (entry + 256 - 64 * nspr .. + 255, store page at slot 1): every
; outline pixel (2) -> transparent (0) when the piece's class has no outline (V_KEY bit 1).
nooutl: ld a,(V_KEY)
        and 2
        ret z
        ld a,(V_NS)
        ld b,a
        xor a
.s:     sub 64
        djnz .s
        ld l,a
        ld a,(V_ENT+1)
        ld h,a
.p:     ld a,(hl)
        ld c,a
        and 0xF0
        cp 0x20
        jr nz,.h
        ld a,c
        and 0x0F
        ld c,a
.h:     ld a,c
        and 0x0F
        cp 0x02
        jr nz,.w
        ld a,c
        and 0xF0
        ld c,a
.w:     ld (hl),c                   ; (unit-test control: NOP = outline kept)
        inc l
        jr nz,.p
        ret
code3_end:

; --- third code block (page 26 0x0D60-0x0DFF: the tail of WBG's page)
        ORG CODE4
; A = attribute -> ink pixel index (1 black, ink+1, bright +7)
oinkx:  ld c,a
        and 7
        ld a,1
        ret z
        ld a,c
        and 7
        inc a
        bit 6,c
        ret z
        add a,7
        ret

; ocls: A = class byte -> A = FLAGS group bits (0x10 rainbow group / 0x20 item group, + 0x40 fixed
; ink); carry set = leave the cell as drawn (class bit 1). Uses C.
ocls:   ld c,a
        bit 1,a
        scf
        ret nz
        and 0xF0
        ld a,0x20
        jr z,.n
        ld a,0x60
.n:     bit 0,c
        jr z,.i
        xor 0x30
.i:     or a
        ret

; HL = TILES + cell for DE (Z clear and NC if not a cell -> carry set = ok). Uses A.
ocell:  ld a,d
        sub 0x9F
        cp 22
        ret nc
        ld l,a
        ld a,e
        cp 32
        ret nc
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
        add a,high TILES
        ld h,a
        scf
        ret

; cell HL (TILES-relative): A = row count index k = (H - high TILES)*8 + L/32
ocrow:  ld a,l
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,h
        sub high TILES
        add a,a
        add a,a
        add a,a
        or c
        ret

; --- diagnostic build (V_DIAG = 1, set by Python for rainbow_sprites_diag.nex): border colour =
; blue while the commit waits for the beam, red while a tile is composed, yellow from the end of a
; game frame that overran (an interrupt came during it) to the next frame start; else black.
; OUT (0xFE) with EAR/MIC 0. Normal build: V_DIAG = 0, no port writes.
dcol:   push af                     ; A = border colour (kept)
        ld a,(V_DIAG)
        or a
        jr z,.x
        pop af
.o:     out (0xFE),a                ; (unit-test control: NOPs = no colour shown)
        ret
.x:     pop af
        ret
; ofill: the opaque object V_OL (codes 15-190): FBUF = its inside pixels (FILLM, page 25 at slot 1
; for the copy, page 27 back), V_HASF = any; V_FPIX = their colour (ofcol). Uses A, BC, DE, HL.
ofill:  xor a
        ld (V_HASF),a
        ld a,(V_OL)
        sub 15
        ret c
        cp 176
        ret nc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,FILLM
        add hl,de
        nextreg 0x51,PAGE_F
        ld de,FBUF
        ld bc,8
        ldir
        ld a,(V_OL)
        ld l,a
        ld h,high FILLC
        ld c,(hl)
        nextreg 0x51,PAGE_T
        ld hl,FBUF
        ld b,8
        xor a
.o:     or (hl)
        inc hl
        djnz .o
        ld (V_HASF),a
        or a
        ret z
        jp ofcol
code4_end:

; --- fourth code block (page 26 0x1F10-0x1FFF)
        ORG CODE2
; draw PBUF (8 rows) into the tile at V_TDP: ink = class override (bits 4-7) or the pass's ink;
; border unless class bit 2. 2026-10-19: table version (X8 in page 28 at slot 2: 4 tables of 256,
; X8 + 256k + v = the nibbles of bits 7-2k / 6-2k of v, 0xF per set bit): per tile byte
; out = old AND NOT (m OR b) OR (b AND 0x11) OR (ink AND m), m = pixel nibbles, b = border
; nibbles; rows without pixels or border skipped. 2.6x faster than the bit loop.
odraw:  ld a,(V_CLS)
        and 0xF0
        rrca
        rrca
        rrca
        rrca
        jr nz,.ik
        ld a,(V_PASS)
        or a
        ld a,(V_INKR)
        jr z,.ik
        ld a,(V_INKI)
.ik:    ld c,a                      ; ink index -> both nibbles
        rlca
        rlca
        rlca
        rlca
        or c
        ld iyh,a
        ld a,(V_CLS)
        and 4
        ld iyl,a                    ; 4 = no border
        ld hl,(V_TDP)
        ld ix,PBUF+1
.r:     ld a,iyl
        or a
        ld a,0
        jr nz,.nb
        ld a,(ix-1)                 ; v = P[j-1] | P[j] | P[j+1] (PBUF[0] and PBUF[9] stay 0)
        or (ix+0)
        or (ix+1)
        ld c,a                      ; dilate: v | v<<1 | v>>1, minus the object's own pixels
        add a,a
        or c
        ld b,a
        ld a,c
        srl a
        or b
        ld b,a
        ld a,(ix+0)
        cpl
        and b
.nb:    ld c,a                      ; C = border bits, E = pixel bits
        ld e,(ix+0)
        or e
        jr z,.skip                  ; nothing in this row
        ld b,high X8T
        ld d,b
.k:     ex de,hl                    ; old AND NOT (m OR b)
        ld a,(bc)
        or (hl)
        ex de,hl
        cpl
        and (hl)
        ld (hl),a
        ld a,(bc)                   ; OR border (index 1)
.bk:    and 0x11                    ; (unit-test control: 0 = no border)
        or (hl)
        ld (hl),a
        ld a,(de)                   ; OR ink AND m
        and iyh
        or (hl)
        ld (hl),a
        inc hl
        inc b
        inc d
        ld a,d
        cp high X8T+4
        jr c,.k
        jr .nx
.skip:  inc hl
        inc hl
        inc hl
        inc hl
.nx:    ld a,(V_HASF)               ; inside pixels of a collectable (not its own pixels): V_FPIX
        or a
        jr z,.nf
        ld a,(ix+0)
        cpl
        and (ix+9)                  ; FBUF row = PBUF+10+j = IX+9
        jr z,.nf
        ld e,a
        dec hl
        dec hl
        dec hl
        dec hl
        ld d,high X8T
        ld a,(V_FPIX)
        ld c,a
.fk:    ld a,(de)
        cpl
        and (hl)
        ld (hl),a
        ld a,(de)
.fc:    and c                       ; (unit-test control: AND 0 = inside pixels not drawn)
        or (hl)
        ld (hl),a
        inc hl
        inc d
        ld a,d
        cp high X8T+4
        jr c,.fk
.nf:    inc ix
        ld a,ixl
        cp low (PBUF+9)
        jr c,.r
        xor a
        ld (V_HASF),a
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
        nextreg 0x43,0x30           ; tilemap palette (256 bytes after the sprite palette, built by
        nextreg 0x40,0              ; Python: bank 0 = 0 transparent, 1 black, 2-8 inks, 9-15 bright;
        ld hl,pal+256               ; bank n = bank 0 but pixel 2 = ink index n and pixel 3 = its
        ld b,0                      ; contrast colour for collectables' insides)
.tp:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .tp
        nextreg 0x4C,0              ; tilemap transparent index 0
        nextreg 0x6C,0              ; attributes: palette offset 0, tilemap over the ULA
        nextreg 0x6B,0              ; off until the first commit
        nextreg 0x2F,0
        nextreg 0x30,0
        nextreg 0x31,0
        nextreg 0x7F,0
        nextreg 0x15,0x01
        ret
tpal:   db 0x00,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
pal:                                ; 256 palette bytes appended by Python

        SAVEBIN "rb_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "rb_page.bin",0x0100,code_end-0x0100
        SAVEBIN "rb_page3.bin",CODE3,code3_end-CODE3
        SAVEBIN "rb_page4.bin",CODE4,code4_end-CODE4
        SAVEBIN "rb_page2.bin",CODE2,code2_end-CODE2
        SAVEBIN "rb_setup.bin",0xD000,pal-0xD000
