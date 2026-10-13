; Midnight Resistance (Ocean 1990, 128K) - hardware sprites for the player, the enemy soldiers /
; gun turrets and the vehicles (jeep, end-of-level tank). Engine notes: games/midnight_resistance.md.
;
; The game composes every game frame in a back buffer (pixels 0x5B00-0x6AFF, 32 bytes per line,
; attrs 0x6B00-0x6CFF), background first, figures after, then copies it to the screen (0x8730).
; Every figure plotter computes its buffer address with CALL 0x7EC1 (D = line, E = x pixel). The
; patch replaces the TARGET of five of those CALLs (same return address, same stack bytes):
;   0x97E5  97E1 masked (zig-zag rows, B bytes x 2C lines)        c_m
;   0x981E  9813 masked, mirrored (E = right byte)                 c_mf
;   0x7DC6  7DC5 overwrite (no mask)                               c_o
;   0x7E0E  7E06 overwrite, mirrored (bit-reverse table 0xFDxx)    c_om
;   0x9EF0  9E3F/9EEF 32-px masked (count 0x9EF6, op 0x9EFA)       c_p
;   0x9F45  9E3F 32-px masked, mirrored (count 0x9F4E, op 0x9F55)  c_pm
; A figure the patch converts is RECORDED (FIG table) and its plot is redirected: the hook copies
; the buffer bytes under the figure into a scratch copy of the buffer (Next RAM page PAGE_S mapped
; at 0xA000 = buffer + OFS) and returns the scratch address, so the game's own loop runs unchanged
; (same registers, same stack bytes) but draws into the scratch copy. The loop exits are patched
; (JP NZ / DJNZ kept, in ROM) to map the address back (FIX table, no flags touched), unmap the page
; and drop the CPU speed. Unconverted plots run exactly as before (the exit FIX is the identity).
; The commit (0x8950, after the screen copy) builds the sprite patterns of the recorded figures
; (into the pattern half not on show) and writes the sprite attributes; 0x8993 hides the sprites
; when the game loop ends (game over), 0x8988 when it leaves for the end of the level.
;
; Interrupt safety: interrupts are ENABLED at every hook site (IM 2, ISR pages 7FFD for the AY).
; Hooks never touch IX, IY, I or IFF; nothing is paged in slots 0/1/6/7 (an unlocked 7FFD write in
; the ISR resets them); the page is mapped at slot 5 only (the ISR never reads, writes or runs
; 0x4000-0x5FFF / 0x8000-0xBFFF; isr scan); hook stacks have room for the ISR (22 bytes).
;
; Figures whose graphics lie under the page (0xA000-0xBFFF: keys, shots, explosions at
; 0xAB88-0xB2C0) plot into a second scratch, page PAGE_U mapped at SLOT 2 (0x4000-0x5FFF = buffer -
; 0x1B00; the ISR never touches 0x4000-0x5FFF and the ULA shows bank 5 whatever slot 2 holds), with
; slot 5 back on the game's page 5 so the loop reads the graphics where they are. The buffer box is
; copied into PAGE_U through slot 4 first; the loop exits map slot 2 back (FIX also maps 0x40-0x51).
; The commit reads such graphics through slot 4 = page 5 into TMPG.
; Colour maps (docs/profiles/midnight_resistance_colours.json): Next pages of 8-byte entries, one per
; key graphics byte p (masked: the mask byte; overwrite: the graphic byte): 4 bytes of colour
; nibbles (0 = default), a check byte (mask XOR graphic rotated left), the kind (1 masked, 2
; overwrite). PT0 / PT1 (sets: 0 = all but the player, 1 = the player) give the page for p >> 10
; (0 = none); the commit maps it at slot 4 (the ISR never touches 0x8000-0x9FFF).
; Code and tables live in alt ROM image 1 (0x2000-0x3CFF; the game reads only ROM 0x0000 and the
; font 0x3D00-0x3FFF).

        DEVICE ZXSPECTRUMNEXT

PAGE_S  EQU 26
OFS     EQU 0x4500              ; scratch = buffer + OFS (0x5B00-0x6AFF -> 0xA000-0xAFFF)
MAXF    EQU 32                  ; figures per game frame
MAXT    EQU 64                  ; sprites (16x16 4-bit patterns) per game frame
CBLACK  EQU 8                   ; palette index of black
ATTR    EQU 0x6B00              ; attribute buffer (16 lines x 32)

; ---- page PAGE_S at 0xA000 (only while a hook runs) ----
V_SP    EQU 0xB000              ; game SP while a hook runs on its own stack
V_HL    EQU 0xB002
V_NF    EQU 0xB004              ; figures recorded this frame
V_NT    EQU 0xB005              ; sprites reserved this frame
V_PREV  EQU 0xB006              ; sprites shown by the last commit
V_CPTR  EQU 0xB007              ; next cache entry to replace (0..NCACHE-1)
V_N     EQU 0xB008              ; sprites built by this commit
V_ATT   EQU 0xB009              ; attribute the colour table CT holds (cells mode)
V_LIVE  EQU 0xB00A              ; 1 = in the game loop (set by a commit, cleared at its exit)
V_KIND  EQU 0xB00B              ; variant: bit 0 mirror, bit 1 overwrite, bit 2 32-px (P)
V_W     EQU 0xB00C              ; bytes per line
V_R     EQU 0xB00D              ; lines
V_X     EQU 0xB00E              ; left column (signed)
V_Y     EQU 0xB00F              ; first line
V_COL   EQU 0xB010              ; ink index (0 = colours of the attribute cells)
V_GFX   EQU 0xB011              ; graphics pointer (2)
V_A0    EQU 0xB013              ; buffer address of line 0's first byte (2)
V_FL    EQU 0xB015              ; figure flags: bit 0 mirror, bit 1 overwrite, bit 2 no ink
V_TMP   EQU 0xB016              ; (2)
V_K     EQU 0xB018              ; conversion: byte counter
V_RR    EQU 0xB019              ; conversion: line counter
V_DST   EQU 0xB01A              ; conversion: staging pointer (2)
V_DC    EQU 0xB01C              ; conversion: display column of the current byte
V_AROW  EQU 0xB01D              ; conversion: attribute line address (2)
V_NC    EQU 0xB01F              ; tiles across
V_NR    EQU 0xB020              ; tiles down
V_TX    EQU 0xB021
V_TY    EQU 0xB022
V_PAT   EQU 0xB023              ; pattern number of the current tile
V_BC    EQU 0xB024              ; (2)
V_BACK  EQU 0xB026              ; conversion: 1 = this line runs right to left in the data
V_DCS   EQU 0xB027              ; conversion: display column step (+1 / -1)
V_SPTR  EQU 0xB028              ; pattern slot search start (0..127)
V_ENT   EQU 0xB029              ; cache entry of the figure being built (2; 0 = not cached)
V_T     EQU 0xB02B              ; tile index within the figure
SLOTST  EQU 0xB040              ; 128 pattern slots: bit 0 on show (last commit), bit 1 used by this one
SLOTENT EQU 0xB440              ; 128 pattern slots: cache entry + 1 whose image it holds (0 = none)
CACHE   EQU 0xBE00              ; NCACHE x 16: gfx (2), W, R, flags & 6, colour, valid, Y & 7 (cells), 8 slots
NCACHE  EQU 16
SIG     EQU 0xBC00              ; NCACHE x 32: cells figures: the attributes under the image (k order)
V_SIG   EQU 0xB0C0              ; this figure's attribute signature (32)
V_SL    EQU 0xB02C              ; its length (0 = cells figure too large to cache)
V_Y7    EQU 0xB02D              ; Y & 7 (cells), 0 (fixed colour)
V_UND   EQU 0xB02E              ; decide: 1 = graphics under the page (scratch at slot 2)
V_SRC   EQU 0xB031              ; (2) build: where the figure's graphics are read
V_DELTA EQU 0xB033              ; (2) build: original graphics address - V_SRC
V_CPG   EQU 0xB035              ; colour store page mapped at slot 4 (0 = page 4, the game's)
V_MAP   EQU 0xB036              ; build: 1 = apply the colour map
V_PTL   EQU 0xB037              ; build: low byte of the set's page table
V_LEN   EQU 0xB039              ; (2) decide: graphics length
V_TP    EQU 0xB03B              ; (2) conv: source address of the current entry
V_VF    EQU 0xB03D              ; decide: 0x80 = drawn vertically flipped (strides -32, D = bottom line)
FIG     EQU 0xB100              ; MAXF x 8: gfx lo, gfx hi, W, R, X, Y, flags, colour
STK     EQU 0xB300              ; hook stack top (0xB200-0xB2FF)
SPR     EQU 0xB300              ; MAXT x 5 sprite attributes (0xB300-0xB43F)
CT      EQU 0xB500              ; pixel codes (0 clear, 1 ink, 2 paper; 2 per byte) -> colours
PT0     EQU 0xB580              ; colour store page per 1K of graphics, set 0 (64; Python fills)
PT1     EQU 0xB5C0              ; set 1 (the player)
TMPG    EQU 0xBF00              ; build: copy of a figure's graphics from under the page (<= 255)
PAGE_U  EQU 27                  ; scratch for under-page figures, at slot 2 while their loop runs
OFS2    EQU 0x2500              ; buffer -> PAGE_U seen at slot 4 (0x5B00 -> 0x8000)
KEY_COL EQU 14                  ; keys: bright yellow, black outline
STG     EQU 0xB600              ; staging: 48 lines x 32 bytes (4-bit pixels) 0xB600-0xBBFF

; ---- alt ROM tables (Python fills them) ----
NIBTAB  EQU 0x2000              ; (G nibble << 4 | M nibble) -> 2 bytes of pixel codes (2 pages)
FIX     EQU 0x2200              ; high byte: scratch -> buffer (identity outside 0xA0-0xB1: a loop ends
                                ; one line below its last, up to 0x6B00+32+W)
INKI    EQU 0x2300              ; attribute -> ink palette index
PAPI    EQU 0x2400              ; attribute -> paper palette index
ROM_ORG EQU 0x2500

        ORG ROM_ORG
; ================= CALL 0x7EC1 replacements (plot start) =================
c_m:    nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,0
        jr c_go
c_mf:   nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,1
        jr c_go
c_o:    nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,2
        jr c_go
c_om:   nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,3
        jr c_go
c_p:    nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,4
        jr c_go
c_pm:   nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,5
c_go:   ld (V_KIND),a
        nextreg 0x07,3              ; 28 MHz from here to the loop exit (or the pass below)
        push bc
        push de
        push hl
        xor a
        ld (V_UND),a
        call decide                 ; NC = convert (scratch prepared, figure recorded)
        pop hl
        pop de
        pop bc
        jr c,.pass
        ld a,(V_UND)
        or a
        jr nz,.und
        pop af
        ld sp,(V_SP)
        jp m7ec1                    ; scratch address; the page stays mapped for the loop
.und:   pop af                      ; graphics under the page: slot 5 = the game's, scratch at slot 2
        ld sp,(V_SP)
        nextreg 0x55,5
        nextreg 0x52,PAGE_U
        jp m7ec2
.pass:  pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        nextreg 0x07,0
        jp 0x7EC1

; 0x7EC1 with the scratch base (flags at RET: OR A with A = 0, as the original)
m7ec2:  ld hl,0x4000                ; slot-2 scratch (buffer - 0x1B00)
        jr m7c
m7ec1:  ld hl,0x5B00+OFS
m7c:    srl e
        srl e
        srl e
        ld a,d
        ld d,0
        add hl,de
        ld e,32
.l:     or a
        ret z
        rra
        jr nc,.n
        add hl,de
.n:     ex de,hl
        add hl,hl
        ex de,hl
        jp .l

; ================= loop exits (every plot of these routines passes here) =================
        MACRO FIXDE                 ; D: scratch -> buffer; unmap; normal speed (no stack, no flags)
        nextreg 0x55,PAGE_S
        ld (V_HL),hl
        ld h,high FIX
        ld l,d
        ld d,(hl)
        ld hl,(V_HL)
        nextreg 0x55,5
        nextreg 0x52,10
        nextreg 0x07,0
        ENDM
x_m:    jp nz,0x97EA
        FIXDE
        jp 0x9812
x_mf:   jp nz,0x9828
        exx
        FIXDE
        jp 0x9865
x_o:    jp nz,0x7DCA
        ex de,hl
        FIXDE
        ex de,hl
        jp 0x7DE8
x_om:   jp nz,0x7E16
        ex de,hl
        FIXDE
        ex de,hl
        jp 0x7E3C
        MACRO FIXDEF                ; FIXDE, then the 32-px loop's last ADD HL,BC (DE - 32 + 32) again
        nextreg 0x55,PAGE_S         ; on the real address: H, N, C and flag bits 3/5 as the original
        ld (V_HL),hl                ; (S, Z, P/V are the loop's, unchanged by ADD HL)
        ld (V_BC),bc
        ld h,high FIX
        ld l,d
        ld d,(hl)
        ld hl,-32
        add hl,de
        ld bc,32
        add hl,bc
        ld bc,(V_BC)
        ld hl,(V_HL)
        nextreg 0x55,5
        nextreg 0x52,10
        nextreg 0x07,0
        ENDM
x_p:    djnz .b
        FIXDEF
        ret
.b:     jp 0x9EF7
x_pm:   djnz .b
        exx
        FIXDEF
        jp 0x9FBA
.b:     jp 0x9F4F

; ================= decide: convert this plot? =================
; In: V_KIND, game stack (V_SP): +0 return, +2 graphics pointer, +4 the plotter's caller.
; B = bytes, C = line pairs (97E1 / 9813 / 7DC5), D = line, E = x pixel.
; Out: carry = pass. NC = recorded + scratch box prepared.
decide: xor a
        ld (V_VF),a
        ld a,(V_LIVE)
        or a
        jp z,dpass
        ld a,(V_NF)
        cp MAXF
        jp nc,dpass
        ld a,d
        cp 128
        jp nc,dpass
        ld (V_Y),a
        ld hl,(V_SP)
        inc hl
        inc hl
        ld a,(hl)
        ld (V_GFX),a
        inc hl
        ld a,(hl)
        ld (V_GFX+1),a
        inc hl
        ld a,(hl)                   ; caller
        inc hl
        ld h,(hl)
        ld l,a
        ld a,(V_KIND)
        bit 2,a
        jp nz,.p
        ; ---- 97E1 / 9813 / 7DC5 / 7E06: every caller (Dean, 2026-10-13: every figure a sprite);
        ;      keys yellow, the rest in its cell colours; stride +32, OR opcodes ----
        push de
        ld de,kcall
        call inlist
        ld a,KEY_COL
        jr z,.vk
        ld de,acall
        call inlist
        ld a,12                     ; the player's add-on piece: the player's colour (and set)
        jr z,.vk
        xor a
.vk:    pop de
        ld (V_COL),a
        ld a,b
        or a
        jp z,dpass
        cp 9
        jp nc,dpass
        ld (V_W),a
        ld a,c
        or a
        jp z,dpass
        cp 25                       ; at most 48 lines (staging)
        jp nc,dpass
        add a,a
        ld (V_R),a
        ld a,(V_COL)
        cp 12
        ld a,(V_KIND)
        jr nz,.fk
        or 8                        ; colour set 1 (the player)
.fk:    and 0x0B
        ld (V_FL),a
        and 3
        cp 1
        jr z,.mf
        cp 2
        jr z,.o
        cp 3
        jr z,.om
        ld hl,(0x97F7)              ; 97E1: strides (+32, or -32 = flipped via 97A7) and OR opcodes
        ld bc,(0x9809)
        call strd
        jp nz,dpass
        ld a,(0x97EE)
        cp 0xB6
        jp nz,dpass
        ld a,(0x9800)
        cp 0xB6
        jp nz,dpass
        jp dbox
.mf:    ld hl,(0x983E)
        ld bc,(0x9859)
        call strd
        jp nz,dpass
        ld a,(0x982F)
        cp 0xB6
        jp nz,dpass
        ld a,(0x984B)
        cp 0xB6
        jp nz,dpass
        jp dbox
.o:     ld hl,(0x7DD3)
        ld bc,(0x7DE0)
        call strd
        jp nz,dpass
        jp dbox
.om:    ld hl,(0x7E23)              ; 7E06: strides (7DF2 sets them to -32 for a flipped draw)
        ld bc,(0x7E34)
        call strd
        jp nz,dpass
        jp dbox
        ; ---- 9E3F: player (green), soldiers (white), tank turret (cells) ----
.p:     push de
        ld de,pcall
        call inlist
        ld b,12
        jr z,.pc
        ld de,scall
        call inlist
        ld b,15
        jr z,.pc
        ld b,0                      ; any other caller: its cell colours
.pc:    pop de
        ld a,b
        ld (V_COL),a
        ld a,4
        ld (V_W),a
        ld a,(V_KIND)
        and 1
        ld hl,0x9EF6
        ld bc,0x9EFA
        jr z,.pn
        ld hl,0x9F4E
        ld bc,0x9F55
.pn:    ld a,(hl)                   ; line pairs
        or a
        jp z,dpass
        cp 25
        jp nc,dpass
        add a,a
        ld (V_R),a
        ld a,(V_KIND)
        and 1
        ld l,a
        ld a,(bc)                   ; OR (HL) or NOP
        or a
        jr z,.nop
        cp 0xB6
        jp nz,dpass
        ld a,l
        jr .pf
.nop:   ld a,l
        or 4
.pf:    ld l,a
        ld a,(V_COL)
        cp 12                       ; the player: colour set 1
        ld a,l
        jr nz,.pf2
        or 8
.pf2:   ld (V_FL),a
        ; ---- box: columns, buffer range, graphics range, sprite budget ----
dbox:   ld a,(V_VF)             ; flipped: D is the bottom line -> V_Y = the top line
        or a
        jr z,.nv
        ld a,(V_R)
        dec a
        ld b,a
        ld a,(V_Y)
        sub b
        jp c,dpass
        ld (V_Y),a
        ld a,(V_FL)
        or 0x80
        ld (V_FL),a
.nv:    ld a,e
        rrca
        rrca
        rrca
        and 31
        ld c,a                      ; first byte's column (mirror: the right-hand byte)
        ld a,(V_FL)
        and 1
        ld a,c
        jr z,.nx
        ld a,(V_W)
        dec a
        ld b,a
        ld a,c
        sub b                       ; left column, may be -7..31
.nx:    ld (V_X),a
        ; visible wrap guard: normal X + W - 1 <= 34, mirror X >= -3
        ld b,a
        ld a,(V_FL)
        and 1
        jr nz,.mx
        ld a,(V_W)
        add a,b
        cp 36
        jp nc,dpass
        jr .ok1
.mx:    ld a,b
        add a,3
        jp m,dpass
.ok1:   ; A0 = 0x5B00 + Y*32 + X (signed X)
        ld a,(V_Y)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_X)
        ld e,a
        rla
        sbc a,a
        ld d,a
        add hl,de
        ld de,0x5B00
        add hl,de
        ld (V_A0),hl
        or a
        sbc hl,de
        jp c,dpass                  ; starts before the buffer
        ; last byte = A0 + (R-1)*32 + W-1 <= 0x6AFF
        ld a,(V_R)
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_W)
        dec a
        ld e,a
        ld d,0
        add hl,de
        ld de,(V_A0)
        add hl,de
        ld de,0x6B00
        or a
        sbc hl,de
        jp nc,dpass
        ; graphics: [GFX, GFX + R*W*(2 or 1)) outside 0xA000-0xBFFF and below 0x10000
        ld a,(V_R)
        ld e,a
        ld d,0
        ld hl,0
        ld a,(V_W)
        ld b,a
.gm:    add hl,de
        djnz .gm
        ld a,(V_FL)
        and 2
        jr nz,.g1
        add hl,hl
.g1:    ld (V_LEN),hl
        ld de,(V_GFX)
        add hl,de
        jp c,dpass                  ; wraps past 0xFFFF
        ld a,h
        cp 0xA0
        jr c,.gok                   ; ends below 0xA000 (end exclusive, may equal 0xA000)
        jr nz,.g2
        ld a,l
        or a
        jr z,.gok
.g2:    ld a,d
        cp 0xC0
        jr nc,.gok                  ; starts at or above 0xC000
        ; under the page: inside 0xA000-0xBFFF and < 256 bytes (the commit's copy area TMPG)
        ld a,d
        cp 0xA0
        jp c,dpass                  ; starts below 0xA000, ends above it
        ld a,h                      ; end <= 0xC000
        cp 0xC0
        jr c,.g3
        jp nz,dpass
        ld a,l
        or a
        jp nz,dpass
.g3:    ld hl,(V_LEN)
        ld a,h
        or a
        jp nz,dpass
        ld a,1
        ld (V_UND),a
.gok:   ; sprites: ((W+1)/2) * ((R+15)/16) <= MAXT - NT
        ld a,(V_W)
        inc a
        srl a
        ld b,a
        ld a,(V_R)
        add a,15
        rrca
        rrca
        rrca
        rrca
        and 15
        ld c,a
        xor a
.tm:    add a,c
        djnz .tm
        ld b,a
        ld a,(V_NT)
        add a,b
        cp MAXT+1
        jp nc,dpass
        ld (V_NT),a
        ; ---- record ----
        ld a,(V_NF)
        ld l,a
        inc a
        ld (V_NF),a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,FIG
        add hl,de
        ld a,(V_GFX)
        ld (hl),a
        inc hl
        ld a,(V_GFX+1)
        ld (hl),a
        inc hl
        ld a,(V_W)
        ld (hl),a
        inc hl
        ld a,(V_R)
        ld (hl),a
        inc hl
        ld a,(V_X)
        ld (hl),a
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,(V_FL)
        ld (hl),a
        inc hl
        ld a,(V_COL)
        ld (hl),a
        ld a,(V_UND)
        or a
        ld de,OFS
        jr z,.c0
        dec hl
        set 6,(hl)                  ; flags: graphics under the page
        nextreg 0x54,PAGE_U         ; the slot-2 scratch, filled through slot 4
        ld de,OFS2
.c0:    ld (V_TMP),de
        ; ---- scratch box = buffer box (the loop then reads what it would have read) ----
        ld hl,(V_A0)
        ld a,(V_R)
        ld c,a
.cp:    push hl
        push bc
        ld de,(V_TMP)
        ex de,hl
        add hl,de
        ex de,hl                    ; DE = HL + OFS
        ld a,(V_W)
        ld c,a
        ld b,0
        ldir
        pop bc
        pop hl
        ld de,32
        add hl,de
        dec c
        jr nz,.cp
        nextreg 0x54,4
        or a                        ; NC: convert
        ret
dpass:  scf
        ret

strd:   ld a,h                      ; Z if HL = BC = 32 (V_VF 0) or HL = BC = -32 (V_VF 0x80)
        or a
        jr nz,.n
        ld a,l
        cp 32
        ret nz
        ld a,b
        or a
        ret nz
        ld a,c
        cp 32
        ret
.n:     inc a
        ret nz
        ld a,l
        cp 0xE0
        ret nz
        ld a,b
        inc a
        ret nz
        ld a,c
        cp 0xE0
        ret nz
        ld a,0x80
        ld (V_VF),a
        xor a
        ret

is32:   ld a,h                      ; Z if HL = 32
        or a
        ret nz
        ld a,l
        cp 32
        ret

inlist: push hl                     ; Z if HL is in the 0-terminated word list at DE
        push bc
        ld b,h
        ld c,l
.l:     ld a,(de)
        ld l,a
        inc de
        ld a,(de)
        ld h,a
        inc de
        or l
        jr z,.no
        ld a,l
        cp c
        jr nz,.l
        ld a,h
        cp b
        jr nz,.l
        pop bc
        pop hl
        xor a                       ; Z
        ret
.no:    pop bc
        pop hl
        or 1                        ; NZ
        ret

pcall:  dw 0x9E04,0x9E0C,0         ; player (legs, body)
scall:  dw 0xA4F2,0xA504,0         ; soldiers / gun turrets
kcall:  dw 0x97A4,0                ; keys
acall:  dw 0x9DFC,0x9DEF,0         ; the player's add-on piece (97E1 / 9813)
; (any other caller: cell colours; the tank turret 0xDEB2, vehicles, shots, explosions)

; ================= commit (0x8950: after the screen copy) =================
e_cm:   nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        call commit
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        ld de,(0xDCEE)
        jp 0x8954

; ================= the shop's loop (0xB879-0xB8B3; reached by the end-of-level exit) =================
; It runs the same frame routine (0x8F48, screen copy) without the game loop's commit: commit after it
; at 0xB893, and hide everything on its two exits (0xB89F RET NZ on 0xFF70, 0xB8AA RET Z on x = 200).
e_cs:   nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        call commit
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        xor a
        ld (0x93D8),a
        jp 0xB897
; leaving the shop: hide every sprite, loop no longer live (no CALL on the game's stack: its dead
; stack must stay as the original's)
        MACRO SHIDE
        nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        call hideall
        pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        ENDM
e_s2:   ld a,(0xFF70)               ; 0xB89B: LD A,(0xFF70) / OR A / RET NZ
        or a
        jp z,0xB8A0
        SHIDE
        ret
e_sx:   ld a,(0x9DFD)               ; 0xB8A5: LD A,(0x9DFD) / CP 200 / RET Z
        cp 200
        jp nz,0xB8AB
        SHIDE
        ret

; commit body (game loop and shop): the recorded figures -> patterns + sprite attributes
commit: nextreg 0x07,3
        ld hl,SLOTST                ; slots: "used by the last commit" becomes "on show"
        ld b,128
.ag:    srl (hl)
        inc hl
        djnz .ag
        xor a
        ld (V_N),a
        ld a,(V_NF)
        or a
        jr z,.att
        ld b,a
        ld hl,FIG
.f:     push bc
        push hl
        call build
        pop hl
        ld de,8
        add hl,de
        pop bc
        djnz .f
        nextreg 0x54,4              ; colour store page off slot 4
        xor a
        ld (V_CPG),a
.att:   ld a,(V_N)
        ld d,a
        ld e,0
        ld hl,SPR
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
        jr nc,.done
        nextreg 0x34,a
        nextreg 0x38,0
        inc e
        jr .h
.done:  ld a,d
        ld (V_PREV),a
        xor a
        ld (V_NF),a
        ld (V_NT),a
        ld a,1
        ld (V_LIVE),a
        nextreg 0x07,0
        ret

; ================= 0x8993: the game loop's exit test =================
e_q:    nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,(0xFF70)
        or a
        call nz,hideall
        pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        ld a,(0xFF70)
        jp 0x8996

; ================= 0x8988: JP Z,0xB7E0 (the loop's other exit: end of level) =================
; Never reached in the RZX (it ends in level 1); without this the last commit's sprites stayed on
; show through the shop and into level 2 (Dean, 2026-10-13: "an enemy stays stuck").
e_lv:   jp nz,0x898B
        nextreg 0x55,PAGE_S
        ld (V_SP),sp
        ld sp,STK
        push af
        call hideall
        pop af
        ld sp,(V_SP)
        nextreg 0x55,5
        jp 0xB7E0

hideall: push bc
        ld a,(V_PREV)
        ld b,a
        ld c,0
.h:     ld a,c
        cp b
        jr nc,.d
        nextreg 0x34,a
        nextreg 0x38,0
        inc c
        jr .h
.d:     xor a
        ld (V_PREV),a
        ld (V_NF),a
        ld (V_NT),a
        ld (V_LIVE),a
        pop bc
        ret

; ================= build: one recorded figure -> patterns + SPR entries =================
; HL = FIG entry
build:  ld a,(hl)
        ld (V_GFX),a
        inc hl
        ld a,(hl)
        ld (V_GFX+1),a
        inc hl
        ld a,(hl)
        ld (V_W),a
        inc hl
        ld a,(hl)
        ld (V_R),a
        inc hl
        ld a,(hl)
        ld (V_X),a
        inc hl
        ld a,(hl)
        ld (V_Y),a
        inc hl
        ld a,(hl)
        ld (V_FL),a
        inc hl
        ld a,(hl)
        ld (V_COL),a
        ld hl,(V_GFX)               ; graphics source: the graphics, or a copy (under the page)
        ld a,(V_FL)
        bit 6,a
        call nz,gcopy
        ld (V_SRC),hl
        ex de,hl
        ld hl,(V_GFX)
        or a
        sbc hl,de
        ld (V_DELTA),hl
        ld a,(V_FL)                 ; colour map: not for the mask-only (flashing) image
        and 4
        xor 4
        ld (V_MAP),a
        ld a,(V_FL)
        and 8
        ld a,low PT0
        jr z,.s2
        ld a,low PT1
.s2:    ld (V_PTL),a
        ld a,(V_W)
        inc a
        srl a
        ld (V_NC),a
        ld a,(V_R)
        add a,15
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (V_NR),a
        ; ---- look the image up in the cache (cells figures: with their attribute signature) ----
        ld hl,0
        ld (V_ENT),hl
        xor a
        ld (V_SL),a
        ld (V_Y7),a
        ld a,(V_COL)
        or a
        jr nz,.lk0
        call mksig
        ld a,(V_SL)
        or a
        jp z,.new
.lk0:   ld hl,CACHE
        ld b,NCACHE
.lk:    push hl
        push bc
        ld de,V_GFX                 ; key: gfx (2), W, R, flags & 6, colour; +6 valid
        ld a,(de)
        cp (hl)
        jr nz,.lkn
        inc hl
        inc de
        ld a,(de)
        cp (hl)
        jr nz,.lkn
        inc hl
        ld a,(V_W)
        cp (hl)
        jr nz,.lkn
        inc hl
        ld a,(V_R)
        cp (hl)
        jr nz,.lkn
        inc hl
        ld a,(V_FL)
        and 6
        cp (hl)
        jr nz,.lkn
        inc hl
        ld a,(V_COL)
        cp (hl)
        jr nz,.lkn
        inc hl
        ld a,(hl)
        or a
        jr z,.lkn
        inc hl
        ld a,(V_Y7)
        cp (hl)
        jr nz,.lkn
        pop bc
        pop hl
        push hl
        push bc
        call sigeq
        jr nz,.lkn
        pop bc                      ; hit: every tile from the entry's slots
        pop hl
        ld de,8
        add hl,de
        ld (V_ENT),hl
        xor a
        ld (V_T),a
        ld (V_TY),a
.hy:    xor a
        ld (V_TX),a
.hx:    ld hl,(V_ENT)
        ld a,(V_T)
        add a,l
        ld l,a
        ld a,(hl)                   ; slot
        ld (V_PAT),a
        ld l,a
        ld h,high SLOTST
        ld a,low SLOTST
        add a,l
        ld l,a
        set 1,(hl)
        call addspr
        ld hl,V_T
        inc (hl)
        call nexttile
        jr c,.hx
        ret
.lkn:   pop bc
        pop hl
        ld de,16
        add hl,de
        djnz .lk
        ; miss: take the next cache entry; forget the slots it held
        ld a,(V_CPTR)
        ld l,a
        inc a
        and NCACHE-1
        ld (V_CPTR),a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CACHE
        add hl,de
        push hl
        call entfree
        pop hl
        ld de,V_GFX                 ; new key
        ld a,(de)
        ld (hl),a
        inc hl
        inc de
        ld a,(de)
        ld (hl),a
        inc hl
        ld a,(V_W)
        ld (hl),a
        inc hl
        ld a,(V_R)
        ld (hl),a
        inc hl
        ld a,(V_FL)
        and 6
        ld (hl),a
        inc hl
        ld a,(V_COL)
        ld (hl),a
        inc hl
        ld (hl),1                   ; valid
        inc hl
        ld a,(V_Y7)
        ld (hl),a
        inc hl
        ld (V_ENT),hl               ; slots of this entry
        ld a,(V_SL)                 ; signature
        or a
        jr z,.new
        ld c,a
        ld b,0
        ld de,-8
        add hl,de
        call sigadr
        ex de,hl
        ld hl,V_SIG
        ldir
.new:   call conv
        ; ---- tiles: every tile of the NC x NR grid: a free slot, upload, sprite ----
        xor a
        ld (V_T),a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
.tx:    call alloc                  ; A = slot (on show or used now: never)
        ld (V_PAT),a
        ld hl,(V_ENT)               ; cached image: the entry records the slot, the slot the entry
        ld a,h
        or l
        jr z,.nc
        ld a,(V_T)
        add a,l
        ld l,a
        ld a,(V_PAT)
        ld (hl),a
        ld l,a
        ld h,high SLOTENT
        ld a,low SLOTENT
        add a,l
        ld l,a
        ld a,(V_CPTR)               ; entry index + 1 = (CPTR - 1) & 31 + 1
        dec a
        and NCACHE-1
        inc a
        ld (hl),a
.nc:    ld a,(V_TY)                 ; staging tile: STG + TY*512 + TX*8
        add a,a
        add a,high STG
        ld h,a
        ld a,(V_TX)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,(V_PAT)
        srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ld de,32
        ld a,16
.u1:    ld bc,0x085B
        push hl
        otir
        pop hl
        add hl,de
        dec a
        jr nz,.u1
        call addspr
        ld hl,V_T
        inc (hl)
        call nexttile
        jr c,.tx
        ret

; next tile: TX += 1, wrap to the next row; carry = more tiles
nexttile:
        ld a,(V_TX)
        inc a
        ld (V_TX),a
        ld hl,V_NC
        cp (hl)
        ret c
        xor a
        ld (V_TX),a
        ld a,(V_TY)
        inc a
        ld (V_TY),a
        ld hl,V_NR
        cp (hl)
        ret

; a free pattern slot (not on show, not used by this commit) -> A, marked used; the cache entry
; that held an image there is forgotten
alloc:  ld a,(V_SPTR)
.l:     ld l,a
        ld h,high SLOTST
        ld a,low SLOTST
        add a,l
        ld e,l
        ld l,a
        ld a,(hl)
        or a
        jr z,.got
        ld a,e
        inc a
        and 127
        jr .l
.got:   set 1,(hl)
        ld a,e
        inc a
        and 127
        ld (V_SPTR),a
        ld l,e                      ; SLOTENT[slot]: forget that entry
        ld h,high SLOTENT
        ld a,low SLOTENT
        add a,l
        ld l,a
        ld a,(hl)
        ld (hl),0
        or a
        jr z,.ok
        dec a                       ; entry index -> its valid byte
        push de
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CACHE+6
        add hl,de
        ld (hl),0
        pop de
.ok:    ld a,e
        ret

; HL = cache entry: invalidate it and clear the back-references of its slots
entfree:
        push hl
        ld de,6
        add hl,de
        ld (hl),0
        inc hl
        inc hl
        ex de,hl                    ; DE = its 8 slots
        pop hl
        push hl
        ld bc,CACHE
        or a
        sbc hl,bc                   ; index = (HL - CACHE) / 16
        ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra
        srl h
        rra
        inc a
        ld c,a                      ; entry + 1
        ld b,8
.s:     ld a,(de)
        inc de
        push hl
        ld h,high SLOTENT
        add a,low SLOTENT
        ld l,a
        ld a,(hl)
        cp c
        jr nz,.n
        ld (hl),0
.n:     pop hl
        djnz .s
.x:     pop hl
        ret

; HL = cache entry -> HL = its signature area (SIG + index * 32)
sigadr: push af
        ld a,l
        add a,a
        ld l,a
        ld a,high SIG
        adc a,0
        ld h,a
        pop af
        ret

; HL = cache entry: Z if its signature equals V_SIG (V_SL bytes; 0 = equal)
sigeq:  ld a,(V_SL)
        or a
        ret z
        ld b,a
        call sigadr
        ld de,V_SIG
.l:     ld a,(de)
        cp (hl)
        ret nz
        inc de
        inc hl
        djnz .l
        ret

; cells figure: V_SIG = attributes under the image, cell lines down, bytes k across (display column
; X + k, mirror X + W - 1 - k); V_SL = length, 0 if more than 32; V_Y7 = Y & 7
mksig:  ld a,(V_Y)
        and 7
        ld (V_Y7),a
        ld b,a
        ld a,(V_R)
        add a,b
        add a,7
        rrca
        rrca
        rrca
        and 31
        ld c,a                      ; cell lines
        ld a,(V_W)
        ld b,a
        xor a
.m:     add a,c
        djnz .m
        cp 33
        jr c,.ok
        xor a
        ld (V_SL),a
        ret
.ok:    ld (V_SL),a
        ld a,(V_Y)
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,ATTR
        add hl,de                   ; first attribute line
        ld de,V_SIG
.cr:    push bc
        push hl
        ld a,(V_W)
        ld b,a
        ld c,0                      ; k
.k:     ld a,(V_FL)
        and 1
        ld a,c
        jr z,.n
        ld a,(V_W)
        dec a
        sub c
.n:     push hl
        push bc
        ld b,a
        ld a,(V_X)
        add a,b
        and 31
        or l
        ld l,a
        ld a,(hl)
        ld (de),a
        inc de
        pop bc
        pop hl
        inc c
        djnz .k
        pop hl
        ld bc,32
        add hl,bc
        pop bc
        dec c
        jr nz,.cr
        ret

; staging image of the figure in V_* (lines R, bytes W, flags, colour)
conv:   ld a,(V_NR)
        ; ---- clear what the conversion does not write: lines R..NR*16-1, and the last 4 bytes
        ;      of each line when W is odd ----
        add a,a
        add a,a
        add a,a
        add a,a
        ld hl,V_R
        sub (hl)
        jr z,.c2
        ld c,a                      ; lines to clear
        ld a,(V_R)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,STG
        add hl,de
.c1:    push hl
        ld a,(V_NC)
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.c1b:   ld (hl),a
        inc hl
        djnz .c1b
        pop hl
        ld de,32
        add hl,de
        dec c
        jr nz,.c1
.c2:    ld a,(V_W)
        rrca
        jr nc,.c4
        rlca
        add a,a
        add a,a
        ld l,a
        ld h,high STG
        ld a,(V_R)
        ld c,a
        ld de,32
        xor a
.c3:    ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        dec l
        dec l
        dec l
        add hl,de
        dec c
        jr nz,.c3
.c4:    ; ---- colour table: a fixed colour now; cells: per byte when the attribute changes ----
        ld a,0xFF
        ld (V_ATT),a
        ld a,(V_COL)
        or a
        jr z,.c5
        ld b,a
        ld c,CBLACK
        call setct
.c5:    xor a
        ld (V_RR),a
        ld hl,(V_SRC)
        ; ---- lines (zig-zag: even lines left to right, odd lines right to left) ----
.line:  push hl
        ld a,(V_RR)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,STG
        add hl,de
        ex de,hl                    ; DE = staging line
        ld a,(V_RR)
        and 1
        ld (V_BACK),a
        jr z,.ev
        ld a,(V_W)                  ; odd line: start at byte W-1
        dec a
        add a,a
        add a,a
        add a,e
        ld e,a
.ev:    ld a,(V_COL)
        or a
        jr nz,.nc
        ; cells: attribute line 0x6B00 + ((Y + r) & 0xF8) * 4 (flipped: Y + R - 1 - r), display
        ; column of the first byte
        ld a,(V_FL)
        bit 7,a
        jr z,.cy
        ld a,(V_R)
        dec a
        ld hl,V_RR
        sub (hl)
        ld hl,V_Y
        add a,(hl)
        jr .cy2
.cy:    ld a,(V_Y)
        ld hl,V_RR
        add a,(hl)
.cy2:   and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,ATTR
        add hl,bc
        ld (V_AROW),hl
        ; first byte k0 = 0 (even) or W-1 (odd); step +1 / -1; mirror: column X+W-1-k
        ld a,(V_W)
        dec a
        ld c,a                      ; W-1
        ld a,(V_BACK)
        ld hl,V_FL
        xor (hl)
        and 1                       ; 1: columns run right to left on screen
        ld a,(V_X)
        ld b,1
        jr z,.d1
        add a,c
        ld b,-1
.d1:    ld (V_DC),a
        ld a,b
        ld (V_DCS),a
.nc:    pop hl
        ld a,(V_W)
        ld b,a
.byte:  push bc
        ld (V_TP),hl
        ld a,(V_FL)
        bit 1,a
        jr nz,.ov
        ld c,(hl)                   ; mask
        inc hl
        ld b,(hl)                   ; graphic
        inc hl
        bit 2,a
        jr z,.go
        ld b,0                      ; OR opcode was NOP: the mask only
        jr .go
.ov:    ld c,0                      ; overwrite: every pixel opaque
        ld b,(hl)
        inc hl
.go:    push hl
        ld a,(V_COL)
        or a
        jr nz,.cv
        ld hl,(V_AROW)              ; cells: colours of the attribute under this byte
        ld a,(V_DC)
        and 31
        or l
        ld l,a
        ld a,(hl)
        ld hl,V_ATT
        cp (hl)
        jr z,.same
        ld (hl),a
        push bc
        ld l,a
        ld h,high INKI
        ld b,(hl)
        ld h,high PAPI
        ld c,(hl)
        call setct
        pop bc
.same:  ld a,(V_DCS)
        ld hl,V_DC
        add a,(hl)
        ld (hl),a
.cv:    call cbyte                  ; 4 bytes at DE, DE += 4
        call ovl                    ; colour map over them
        pop hl
        ld a,(V_BACK)
        or a
        jr z,.fw
        ld a,e                      ; odd line: back 8 (cbyte's INC DE may have crossed a page)
        sub 8
        ld e,a
        jr nc,.fw
        dec d
.fw:    pop bc
        djnz .byte
        ld a,(V_RR)
        inc a
        ld (V_RR),a
        ld de,V_R
        ex de,hl
        cp (hl)
        ex de,hl
        jp c,.line
        ret

; SPR[N] for tile (TX, TY), pattern V_PAT; N += 1
addspr: ld a,(V_N)                  ; HL = SPR + N * 5 (16 bits: N * 5 passes 255 from N = 52)
        ld l,a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl
        add hl,de
        ld de,SPR
        add hl,de
        push hl
        ; x = X*8 + TX*16 (mirror: X*8 + W*8 - 16*(TX+1)) + 32
        ld a,(V_X)
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_TX)
        ld b,a
        ld a,(V_FL)
        and 1
        jr z,.n
        ld a,(V_W)                  ; + W*8 - 16*(TX+1)
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld a,b
        inc a
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        or a
        sbc hl,de
        jr .x
.n:     ld a,b
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        add hl,de
.x:     ld de,32
        add hl,de                   ; 0..511
        ex de,hl
        pop hl
        ld (hl),e                   ; attr 0: x
        inc hl
        ld a,(V_FL)                 ; attr 1: y = Y + TY*16 + 32 (flipped: Y + R - 16*(TY+1) + 32)
        bit 7,a
        ld a,(V_TY)
        jr nz,.yf
        add a,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_Y)
        add a,b
        jr .yd
.yf:    inc a
        add a,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_R)
        ld c,a
        ld a,(V_Y)
        add a,c
        sub b
.yd:    add a,32
        ld (hl),a
        inc hl
        ld a,(V_FL)                 ; attr 2: palette 0, X mirror, Y mirror (flipped), X8
        and 1
        rlca
        rlca
        rlca
        or d
        ld c,a
        ld a,(V_FL)
        and 0x80
        rrca
        rrca
        rrca
        rrca
        rrca
        or c
        ld (hl),a
        inc hl
        ld a,(V_PAT)                ; attr 3: visible, attr 4 on, pattern >> 1
        srl a
        or 0xC0
        ld (hl),a
        inc hl
        ld a,(V_PAT)                ; attr 4: 4-bit, N6
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a
        ld hl,V_N
        inc (hl)
        ret

; CT for ink index B, paper index C (codes: 0 clear, 1 ink, 2 paper)
setct:  push hl
        push de
        ld h,high CT
        ld l,0x00
        ld (hl),0
        ld l,0x01
        ld (hl),b
        ld l,0x02
        ld (hl),c
        ld a,b
        rlca
        rlca
        rlca
        rlca
        ld d,a                      ; ink << 4
        ld a,c
        rlca
        rlca
        rlca
        rlca
        ld e,a                      ; paper << 4
        ld l,0x10
        ld (hl),d
        ld l,0x11
        ld a,d
        or b
        ld (hl),a
        ld l,0x12
        ld a,d
        or c
        ld (hl),a
        ld l,0x20
        ld (hl),e
        ld l,0x21
        ld a,e
        or b
        ld (hl),a
        ld l,0x22
        ld a,e
        or c
        ld (hl),a
        pop de
        pop hl
        ret

; graphics under the page -> TMPG (through slot 4 = page 5), HL = TMPG
gcopy:  ld a,(V_R)
        ld e,a
        ld d,0
        ld hl,0
        ld a,(V_W)
        ld b,a
.m:     add hl,de
        djnz .m
        ld a,(V_FL)
        and 2
        jr nz,.o
        add hl,hl
.o:     ld b,h
        ld c,l
        ld hl,(V_GFX)
        ld a,h
        sub 0x20
        ld h,a
        ld de,TMPG
        nextreg 0x54,5
        ldir
        nextreg 0x54,4
        xor a
        ld (V_CPG),a                ; slot 4 holds page 4 again
        ld hl,TMPG
        ret

; colour map entry of the byte just converted (C = mask, B = graphic, DE = 4 past its staging
; bytes) over the staging bytes: a non-zero nibble replaces an opaque pixel's colour
ovl:    ld a,(V_MAP)
        or a
        ret z
        push bc
        push de
        ld hl,(V_TP)
        ld de,(V_DELTA)
        add hl,de                   ; key address p
        ld a,h
        rrca
        rrca
        and 0x3F
        ld e,a
        ld a,(V_PTL)
        add a,e
        ld e,a
        ld d,high PT0
        ld a,(de)
        or a
        jr z,.x
        ld e,a
        ld a,(V_CPG)
        cp e
        jr z,.m
        ld a,e
        ld (V_CPG),a
        nextreg 0x54,a
.m:     ld a,h                      ; entry = 0x8000 + (p & 0x3FF) * 8
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ld a,b
        rlca
        xor c
        ld e,a                      ; check byte
        ld a,l
        or 4
        ld l,a
        ld a,(hl)
        cp e
        jr nz,.x
        inc l
        ld a,(V_FL)
        and 2
        ld a,1
        jr z,.k
        inc a
.k:     cp (hl)
        jr nz,.x
        ld a,l
        and 0xF8
        ld l,a                      ; colour bytes
        pop de
        push de
        dec de
        dec de
        dec de
        dec de
        ld b,4
.o:     push bc
        ld a,(de)
        ld c,a
        ld b,(hl)
        and 0xF0
        jr z,.h0
        ld a,b
        and 0xF0
        jr z,.h0
        ld a,c
        and 0x0F
        ld c,a
        ld a,b
        and 0xF0
        or c
        ld c,a
.h0:    ld a,c
        and 0x0F
        jr z,.l0
        ld a,b
        and 0x0F
        jr z,.l0
        ld a,c
        and 0xF0
        ld c,a
        ld a,b
        and 0x0F
        or c
        ld c,a
.l0:    ld a,c
        ld (de),a
        inc de
        inc hl
        pop bc
        djnz .o
.x:     pop de
        pop bc
        ret

; C = mask, B = graphic -> 4 staging bytes at DE
cbyte:  ld a,c
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld l,a
        ld a,b
        and 0xF0
        or l
        call cnib
        ld a,b
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld l,a
        ld a,c
        and 0x0F
        or l
cnib:   ld l,a                      ; A = (G nibble << 4 | M nibble) -> 2 bytes at DE
        ld h,high NIBTAB
        ld a,(hl)
        inc h
        push hl
        ld l,a
        ld h,high CT
        ld a,(hl)
        ld (de),a
        inc de
        pop hl
        ld a,(hl)
        ld l,a
        ld h,high CT
        ld a,(hl)
        ld (de),a
        inc de
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, hide all, clip, sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20           ; sprite palette 0, auto-increment
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
        nextreg 0x1C,2              ; sprite clip window: the play area (columns 3-28, lines 0-127)
        nextreg 0x19,24
        nextreg 0x19,231
        nextreg 0x19,0
        nextreg 0x19,127
        nextreg 0x15,0x01
        ret
pal:                                ; 16 palette bytes appended by Python

        SAVEBIN "mr_rom.bin",ROM_ORG,rom_end-ROM_ORG
        SAVEBIN "mr_setup.bin",0xD000,pal-0xD000
