; Cyclone (Vortex Software, 1985, 48K) - hardware sprites for the helicopter, its shadow, the
; aircraft and the aircraft's shadow (design: games/cyclone.md "Phase B design").
;
; The game's compositing runs unchanged; the hooks only take snapshots of the 33 dynamic tiles
; (the strip the helicopter and its shadow are composited into) and, around the game's renderer,
; build the sprites and show the strip's scenery instead of the composited tiles.
;
; ROM stubs in alt ROM image 1 at 0x386E (must end below 0x3AFF: the IM 2 vector is read from ROM
; 0x3AFF/0x3B00 = FF FF). Code, data and a private stack in Next page PG, mapped at slot 6
; (0xC000-0xDFFF) only while a hook runs (the ISR never touches slot 6); MMU6 = page 0 again
; before any game code runs. Never touches IX/IY (except the replayed LD IX of the renderer),
; I, IFF or the alternate registers. Turbo (NEXTREG 7 = 3) only around hook work.
;
; Patch sites (original bytes checked by cyclone.py):
;   0x7F72  3A 05 75  LD A,(29957)          -> JP e_s0   (S0: scenery of the strip)
;   0x7F7A  00 00 00  NOP x3                -> CALL e_s1 (S1: after the shadow)
;   0x5B4E, 0x9281  CD AF 86  CALL 0x86AF   -> CALL e_h  (helicopter buffer + altitude)
;   0x762C  1E 00 DD  LD E,0 / LD IX,..     -> JP e_r    (render)
;   0x84D6  21 00 40  LD HL,16384           -> JP e_c1   (whole screen clear: hide)
;   0x8D0E  21 00 58  LD HL,22528           -> JP e_c2   (play area clear: hide)
; Sprites (4-bit, pattern = slot): 0-3 aircraft shadow, 4-24 strip canvas (3 x 7 of 16 px at
; x 72, y 32), 25-28 aircraft. Palette offset 0: index 1 = ink, index 2 = mask.

        DEVICE ZXSPECTRUMNEXT

PG      EQU 26
NSPR    EQU 29
TILES   EQU 0xFCF8              ; dynamic tiles 0x5F-0x7F (33 x 8)
TATTR   EQU 0xFE5F              ; their attributes (33)
AGFX    EQU 0xFB98              ; tiles 0x33-0x44 graphics (18 x 8): aircraft shadow + aircraft
TGFX    EQU 0xFA00              ; tile graphics base
MAP     EQU 0xF74E              ; tile map 23 x 22
HBUF    EQU 0x6950              ; helicopter (3 columns of 24 bytes)
ALTV    EQU 0x750D              ; helicopter altitude: top line in the strip = 62 - A
T_SH    EQU 0x33                ; aircraft shadow tiles 0x33-0x3B, aircraft 0x3C-0x44
T_AIR   EQU 0x3C

; ---- page data ----
AP      EQU 0xCB00              ; padded byte plane: aircraft 34 x 34 (1156) / helicopter 28 x 28 (784)
W       EQU AP
PH      EQU 0xDE40              ; helicopter ink, packed like CI, window rows (6 x 26 = 156)
S0T     EQU 0xD000              ; 264
S0A     EQU 0xD108              ; 33
S1T     EQU 0xD130              ; 264
FT      EQU 0xD240              ; 264 (final tiles, saved around the render)
FA      EQU 0xD348              ; 33
AG      EQU 0xD370              ; 144
HB      EQU 0xD400              ; 72
VA      EQU 0xD448              ; altitude at the helicopter draw
FLG     EQU 0xD449              ; bit 0 S0, bit 1 S1, bit 2 helicopter, bit 3 tiles swapped
SVSP    EQU 0xD44A
P_I     EQU 0xD44C
P_W     EQU 0xD44E
WB      EQU 0xD450              ; window base row (canvas)
CNT     EQU 0xD451
CNT2    EQU 0xD452
CHG     EQU 0xD453
PWID    EQU 0xD454              ; plane width (= height): 26 or 32
PWIDW   EQU 0xD456              ; the same, 16 bit
PL      EQU 0xD458              ; plane base
PLEND   EQU 0xD45A              ; plane base + N*N - 1
AX0     EQU 0xD45C              ; aircraft window origin x, y (16-bit signed)
AY0     EQU 0xD45E
SX0     EQU 0xD460              ; aircraft shadow window origin x, y
SY0     EQU 0xD462
AFND    EQU 0xD464              ; bit 0 aircraft found, bit 1 shadow found
ACOL    EQU 0xD465              ; anchor column, row (signed)
AROW    EQU 0xD466
TBASE   EQU 0xD467              ; tile base being built
MAPR    EQU 0xD468
MAPC    EQU 0xD469
CROW    EQU 0xD46A              ; canvas emission row
SPN     EQU 0xD46B
GPTR    EQU 0xD46C
KC      EQU 0xD46E
KR      EQU 0xD46F
TV      EQU 0xD470              ; 8 temp bytes
PF      EQU 0xD478              ; canvas pass: tile / S0 / S1 / map pointers
P0      EQU 0xD47A
P1      EQU 0xD47C
PMP     EQU 0xD47E
ET      EQU 0xD480              ; expected dynamic tile
CC      EQU 0xD481
CR      EQU 0xD482
CHGC    EQU 0xD483
LYV      EQU 0xD484
CRR     EQU 0xD485              ; cache round robin
CVAL    EQU 0xD486              ; cache entries valid (bits 0-3)
ZERO    EQU 0xD4A0              ; 8 zero bytes
CI      EQU 0xD500              ; canvas ink 6 x 112 = 672 -> 0xD7A0
ASH     EQU 0xD7A0              ; aircraft shadow ink, packed 4 x 32 = 128
AIW     EQU 0xD820              ; aircraft ink, packed
AWW     EQU 0xD8A0              ; aircraft white, packed
CACHE   EQU 0xD920              ; 3 x (key 156 + mask 156) -> 0xDCC8
NCACHE  EQU 3
WCW     EQU 0xDD10              ; canvas white, window rows only (6 x 26 = 156)
VIS     EQU 0xDE00              ; 29 bytes: sprite has pixels
ROWOCC  EQU 0xDEE0              ; 112 bytes: canvas row has pixels, bit k = sprite column k
ERW     EQU 0xDE27              ; emission: canvas row
NEF     EQU 0xDE26              ; emspr: nonzero = upload
ST      EQU 0xDE20              ; emission stride (ink, white)
PHP     EQU 0xDE28
GA      EQU 0xDE22
GB      EQU 0xDE24
TBL     EQU 0xDD00              ; nibble table (page aligned)
STK     EQU 0xDFF0

; =============================================================================================
        ORG 0x386E
e_s0:   nextreg 0x56,PG
        jp h_s0
r_s0:   nextreg 0x56,0
        ld a,(29957)
        jp 0x7F75
e_s1:   nextreg 0x56,PG
        jp h_s1
r_ret:  nextreg 0x56,0
        ret
e_h:    call 0x86AF
        nextreg 0x56,PG
        jp h_h
e_r:    nextreg 0x56,PG
        jp h_r1
r_r:    nextreg 0x56,0
        call r_body
        nextreg 0x56,PG
        jp h_r2
r_body: ld e,0
        ld ix,MAP
        jp 0x7632
e_c1:   call hideall
        ld hl,16384
        jp 0x84D9
e_c2:   call hideall
        ld hl,22528
        jp 0x8D11
hideall:
        push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSPR
        jr nz,.h
        pop af
        ret
rom_end:

; =============================================================================================
        ORG 0xC000
hook_page:
; ---- S0: the strip's scenery (tiles + attributes) ----
h_s0:   ld (SVSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,TILES
        ld de,S0T
        ld bc,264
        ldir
        ld hl,TATTR
        ld de,S0A
        ld bc,33
        ldir
        ld a,1
        ld (FLG),a
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(SVSP)
        jp r_s0

; ---- S1: after the shadow ----
h_s1:   ld (SVSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,TILES
        ld de,S1T
        ld bc,264
        ldir
        ld hl,FLG
        set 1,(hl)
        jp h_x

; ---- helicopter drawn: its buffer and altitude ----
h_h:    ld (SVSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,HBUF
        ld de,HB
        ld bc,72
        ldir
        ld a,(ALTV)
        ld (VA),a
        ld hl,FLG
        set 2,(hl)
h_x:     nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(SVSP)
        jp r_ret

; ---- render, before the game's renderer ----
h_r1:   ld (SVSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        call aircraft               ; (uses AP; packs into ASH / AIW / AWW)
        call canvas                 ; (uses AP for W)
        ld a,(FLG)                  ; swap the scenery in
        and 3
        cp 3
        jr nz,.ns
        ld hl,TILES
        ld de,FT
        ld bc,264
        ldir
        ld hl,S0T
        ld de,TILES
        ld bc,264
        ldir
        ld hl,TATTR
        ld de,FA
        ld bc,33
        ldir
        ld hl,S0A
        ld de,TATTR
        ld bc,33
        ldir
        ld hl,FLG
        set 3,(hl)
.ns:    ld a,(AFND)
        bit 7,a
        jr z,.na
        ld hl,AGFX
        ld de,AG
        ld bc,144
        ldir
        ld hl,AGFX
        ld (hl),0
        ld de,AGFX+1
        ld bc,143
        ldir
.na:    nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(SVSP)
        jp r_r

; ---- render, after the game's renderer: restore, sprites ----
h_r2:   ld (SVSP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,FLG
        bit 3,(hl)
        jr z,.nr
        res 3,(hl)
        ld hl,FT
        ld de,TILES
        ld bc,264
        ldir
        ld hl,FA
        ld de,TATTR
        ld bc,33
        ldir
.nr:    ld a,(AFND)
        bit 7,a
        jr z,.nb
        ld hl,AG
        ld de,AGFX
        ld bc,144
        ldir
.nb:    call upload
        call attrs
        jp h_x

; =============================================================================================
; canvas: CI (packed ink, 6 x 112, canvas x 0 = screen x 72, row 0 = screen y 32), PH / CW
; (helicopter ink / white, 26 window rows from WB, packed like CI). A strip cell counts only if the map
; shows its dynamic tile and the figures changed it (F != S1 or S1 != S0); the helicopter only in
; cells it changed (F != S1).
canvas: ld hl,ROWOCC                ; clear the CI rows the last render used (and ROWOCC)
        ld de,CI
        ld b,112
.cl:    ld a,(hl)
        or a
        jr z,.cn
        ld (hl),0
        xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        jr .cx
.cn:    ld a,6
        ex de,hl
        add hl,a                    ; Z80N
        ex de,hl
.cx:    inc hl
        djnz .cl
        ld hl,PH
        ld (hl),0
        ld de,PH+1
        ld bc,155
        ldir
        ld a,(FLG)
        and 3
        cp 3
        ret nz
        ld a,(VA)
        ld b,a
        ld a,69
        sub b
        ld (WB),a                   ; window base = canvas row of the helicopter top - 1
        ld hl,TILES
        ld (PF),hl
        ld hl,S0T
        ld (P0),hl
        ld hl,S1T
        ld (P1),hl
        ld a,0x5F
        ld (ET),a
        xor a
        ld (CC),a
.col:   ld a,(CC)
        ld hl,MAP+5*23+10
        add hl,a                    ; Z80N
        ld (PMP),hl
        xor a
        ld (CR),a
.cell:  ld hl,(PMP)
        ld a,(ET)
        cp (hl)
        jr nz,.skip
        ld hl,(PF)
        ld de,(P1)
        call cmp8
        ld (CHGC),a                 ; F != S1
        ld hl,(P0)
        ld de,(P1)
        call cmp8
        ld hl,CHGC
        or (hl)
        jr z,.skip
        xor a
        ld (LYV),a
.ln:    call cline
        ld hl,LYV
        inc (hl)
        ld a,(hl)
        cp 8
        jr nz,.ln
.skip:  ld hl,(PF)
        ld de,8
        add hl,de
        ld (PF),hl
        ld hl,(P0)
        add hl,de
        ld (P0),hl
        ld hl,(P1)
        add hl,de
        ld (P1),hl
        ld hl,(PMP)
        ld e,23
        add hl,de
        ld (PMP),hl
        ld hl,ET
        inc (hl)
        ld hl,CR
        inc (hl)
        ld a,(hl)
        cp 11
        jr nz,.cell
        ld hl,CC
        inc (hl)
        ld a,(hl)
        cp 3
        jr nz,.col
        ld hl,WCW
        ld (hl),0
        ld de,WCW+1
        ld bc,155
        ldir
        ld a,(FLG)
        bit 2,a
        ret z
        call cfind                  ; mask from the cache, or computed
        jr nz,.have
        call slowmask
.have:  ex de,hl                    ; DE = M (contains PH)
        ; merge: rows WB..: CI = PH | (CI & ~M); WCW = M ^ PH
        ld a,(WB)
        call mul6
        ld bc,CI
        add hl,bc                   ; HL = CI row WB
        ld bc,PH
        ld a,156
        ld (CNT),a
.mg:    ld a,(de)                   ; m
        or a
        jr z,.m0                    ; nothing here
        ld a,(bc)
        ld (TV+1),a                 ; ph
        ld a,(de)
        cpl
        and (hl)                    ; ci & ~m
        push hl
        ld hl,TV+1
        or (hl)
        pop hl
        ld (hl),a
        ld a,(de)
        push hl
        ld hl,TV+1
        xor (hl)                    ; m ^ ph
        ld hl,WCW-PH
        add hl,bc
        ld (hl),a
        pop hl
.m0:    inc hl
        inc de
        inc bc
        ld a,(CNT)
        dec a
        ld (CNT),a
        jr nz,.mg
        ld a,(WB)                   ; occupancy of the window rows
        ld (CNT2),a
        xor a
        ld (KR),a                   ; window row
        ld b,26
.oc:    push bc
        ld a,(CNT2)
        call mul6
        ld de,CI
        add hl,de
        ex de,hl                    ; DE = CI row
        ld a,(KR)
        call mul6
        ld bc,WCW
        add hl,bc                   ; HL = WCW row
        ld c,0
        ld b,3
.ob:    ld a,(de)
        or (hl)
        inc hl
        inc de
        push hl
        ex de,hl
        or (hl)
        ex de,hl
        pop hl
        or (hl)
        inc hl
        inc de
        or a
        jr z,.oz
        ld a,4
        sub b                       ; column 0, 1, 2 -> bit
        push bc
        ld b,a
        ld a,1
.sb:    dec b
        jr z,.sd
        add a,a
        jr .sb
.sd:    pop bc
        or c
        ld c,a
.oz:    djnz .ob
        ld a,(CNT2)
        ld hl,ROWOCC
        add hl,a                    ; Z80N
        ld a,c
        or (hl)
        ld (hl),a
        ld hl,CNT2
        inc (hl)
        ld hl,KR
        inc (hl)
        pop bc
        djnz .oc
        ret

; A = 0 if the 8 bytes at HL and DE are equal (else nonzero)
cmp8:   ld b,8
        ld c,0
.c:     ld a,(de)
        xor (hl)
        or c
        ld c,a
        inc hl
        inc de
        djnz .c
        ld a,c
        ret

; one line: y = LYV of the cell at PF / P0 / P1 (strip column CC, row CR)
cline:  ld a,(LYV)
        ld hl,(PF)
        add hl,a                    ; Z80N
        ld a,(hl)
        ld (TV),a                   ; f
        ld a,(LYV)
        ld hl,(P0)
        add hl,a                    ; Z80N
        ld a,(hl)
        ld (TV+1),a                 ; s0
        ld a,(LYV)
        ld hl,(P1)
        add hl,a                    ; Z80N
        ld a,(hl)
        ld (TV+2),a                 ; s1
        ld a,(TV+1)                 ; shadow = s1 & ~s0 & f
        cpl
        ld hl,TV+2
        and (hl)
        ld hl,TV
        and (hl)
        ld (TV+3),a
        ld a,(CR)                   ; strip line L = 8 r + y
        add a,a
        add a,a
        add a,a
        ld hl,LYV
        add a,(hl)
        ld (CNT2),a
        ld a,(FLG)                  ; in the helicopter box?  d = L - (62 - VA)
        bit 2,a
        jr z,.out
        ld a,(VA)
        ld hl,CNT2
        add a,(hl)
        sub 62
        jr c,.out
        cp 24
        jr nc,.out
        ld (TV+5),a                 ; d
        ld a,(CHGC)
        or a
        ld a,0
        jr z,.he                    ; cell not changed by the helicopter: he = 0
        ld a,(CC)                   ; hb = HB[24 c + d]
        add a,a
        add a,a
        add a,a
        ld e,a
        add a,a
        add a,e
        ld hl,TV+5
        add a,(hl)
        ld hl,HB
        add hl,a                    ; Z80N
        ld a,(TV+2)                 ; he = f & (~s1 | (s1 & hb))
        and (hl)
        ld e,a
        ld a,(TV+2)
        cpl
        or e
        ld hl,TV
        and (hl)
.he:    ld (TV+4),a
        ld a,(TV+5)                 ; PH[(d + 1) * 6 + c + 1] = he
        inc a
        call mul6
        ld a,(CC)
        inc a
        add hl,a                    ; Z80N
        ld de,PH
        add hl,de
        ld a,(TV+4)
        ld (hl),a
        ld hl,TV+3
        or (hl)
        jr .st
.out:   ld a,(TV+2)                 ; other = f & ~s1 (outside the box)
        cpl
        ld hl,TV
        and (hl)
        ld hl,TV+3
        or (hl)
.st:    ld (TV+6),a                 ; ink byte -> CI[(L + 8) * 6 + c + 1]
        ld a,(CNT2)
        add a,8
        call mul6
        ld a,(CC)
        inc a
        add hl,a                    ; Z80N
        ld de,CI
        add hl,de
        ld a,(TV+6)
        ld (hl),a
        or a
        ret z
        ld a,(CNT2)                 ; ROWOCC[L + 8] |= sprite column of byte c + 1
        add a,8
        ld hl,ROWOCC
        add hl,a                    ; Z80N
        ld a,(CC)
        or a
        ld a,1
        jr z,.o
        ld a,2
.o:     or (hl)
        ld (hl),a
        ret

; cache: NZ + HL = mask rows if PH equals a stored key
cfind:  ld b,0
.e:     ld a,(CVAL)
        ld c,b
        inc c
.sh:    rrca
        dec c
        jr nz,.sh
        jr nc,.n                    ; entry not valid
        push bc
        ld a,b
        call centry                 ; HL = entry key
        ld de,PH
        ld c,156
.k:     ld a,(de)
        cp (hl)
        jr nz,.ne
        inc hl
        inc de
        dec c
        jr nz,.k
        pop bc
        or 1                        ; HL = entry + 156 = mask
        ret
.ne:    pop bc
.n:     inc b
        ld a,b
        cp NCACHE
        jr nz,.e
        xor a
        ret
centry: ld hl,CACHE                 ; HL = CACHE + A * 312
        or a
        ret z
        ld de,312
.m:     add hl,de
        dec a
        jr nz,.m
        ret

; slow path: W (26 x 26 bytes) from PH, dilate, fill, pack into a cache entry; HL = its mask rows
slowmask:
        ld hl,W                     ; padded plane 28 x 28: ring 4 (outside), interior 0
        ld a,28
        call pinit
        ld de,PH                    ; unpack: window col j = canvas x 7 + j -> plane col j + 1
        ld hl,W+28+1                ;   (x 7 = byte 0 bit 0, x 8-31 = bytes 1-3, x 32 = byte 4 bit 7)
        ld b,26
.ur:    push bc
        push hl
        ld a,(de)                   ; byte 0: bit 0 only
        rrca
        sbc a,a
        and 1
        ld (hl),a
        inc hl
        inc de
        ld c,3
.ub:    ld a,(de)
        inc de
        push de
        ld d,a
        ld b,8
.ux:    rl d
        sbc a,a
        and 1
        ld (hl),a
        inc hl
        djnz .ux
        pop de
        dec c
        jr nz,.ub
        ld a,(de)                   ; byte 4: bit 7 only
        rlca
        sbc a,a
        and 1
        ld (hl),a
        inc de                      ; byte 5 unused
        inc de
        pop hl
        ld bc,28
        add hl,bc
        pop bc
        djnz .ur
        ld hl,W
        ld bc,28
        call dilate
        call fill
        ; entry = CRR; key = PH; mask rows = every window pixel not outside
        ld a,(CRR)
        ld b,a
        ld a,(CVAL)                 ; mark valid
        ld c,1
        inc b
.vb:    dec b
        jr z,.vs
        sla c
        jr .vb
.vs:    or c
        ld (CVAL),a
        ld a,(CRR)
        call centry
        push hl
        ex de,hl
        ld hl,PH
        ld bc,156
        ldir                        ; key
        ld h,d
        ld l,e
        ld (hl),0
        inc de
        ld bc,155
        ldir                        ; mask rows cleared
        ld a,(CRR)
        inc a
        cp NCACHE
        jr c,.rr
        xor a
.rr:    ld (CRR),a
        pop hl
        ld de,156
        add hl,de
        ld (GPTR),hl                ; mask rows: canvas bit x = plane pixel (row + 1, x - 7 + 1) not 4
        ex de,hl                    ; DE = mask rows (cleared)
        ld hl,W+28+1
        ld b,26
.pr:    push bc
        ld a,(hl)                   ; x 7 -> byte 0 bit 0
        cp 4                        ; carry = not outside
        ld a,0
        rla
        ld (de),a
        inc hl
        inc de
        ld c,3
.pb:    push bc
        ld b,8
.px:    ld a,(hl)
        cp 4
        rl c
        inc hl
        djnz .px
        ld a,c
        ld (de),a
        inc de
        pop bc
        dec c
        jr nz,.pb
        ld a,(hl)                   ; x 32 -> byte 4 bit 7
        cp 4
        ld a,0
        rra
        ld (de),a
        inc de
        inc de                      ; byte 5 stays 0
        inc hl                      ; past x 32, the ring, the next row's ring
        inc hl
        inc hl
        pop bc
        djnz .pr
        ld hl,(GPTR)
        ret

; ---- small arithmetic: HL = A * n ----
mul6:   push de                     ; HL = A * 6 (Z80N MUL; DE kept)
        ld d,a
        ld e,6
        mul d,e
        ex de,hl
        pop de
        ret
mul23:  push de                     ; HL = A * 23
        ld d,a
        ld e,23
        mul d,e
        ex de,hl
        pop de
        ret
addE:   push de                     ; HL += E
        ld d,0
        add hl,de
        pop de
        ret
bitmask:                            ; A (0-7) -> 0x80 >> A
        push bc
        ld b,a
        ld a,0x80
        inc b
.b:     dec b
        jr z,.e
        rrca
        jr .b
.e:     pop bc
        ret

; =============================================================================================
; padded byte planes (1 = ink, 2 = mask, 4 = outside; a 1-pixel ring of 4 around N x N)
; pinit: HL = plane, A = N + 2: all 4, interior 0
pinit:  ld (PWID),a
        ld e,a
        ld d,a
        mul d,e                     ; Z80N: DE = (N + 2)^2
        push hl
        ld (hl),4
        ld b,d
        ld c,e
        dec bc
        ld d,h
        ld e,l
        inc de
        ldir
        pop hl
        ld a,(PWID)
        add hl,a                    ; Z80N: row 1
        inc hl                      ; col 1
        sub 2
        ld b,a                      ; N rows
.r:     push bc
        push hl
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        ld a,(PWID)
        sub 3
        ld c,a
        ld b,0                      ; N - 1
        ldir
        pop hl
        ld a,(PWID)
        add hl,a                    ; Z80N
        pop bc
        djnz .r
        ret

; dilate: HL = plane, BC = width (N + 2) (= PWID set by pinit): 0 next to a 1 -> 2.
; CPIR finds the ink pixels; each marks its 4 neighbours.
dilate: ld (PL),hl
        ld (PWIDW),bc
        ld a,(PWID)
        ld d,a
        ld e,a
        mul d,e                     ; Z80N
        ld b,d
        ld c,e                      ; BC = count
        ld de,(PWIDW)
.l:     ld a,1
        cpir
        ret nz                      ; no more ink
        push hl
        dec hl                      ; the ink pixel
        dec hl
        ld a,(hl)
        or a
        jr nz,.a
        ld (hl),2
.a:     inc hl
        inc hl
        ld a,(hl)
        or a
        jr nz,.b
        ld (hl),2
.b:     dec hl
        add hl,de
        ld a,(hl)
        or a
        jr nz,.c
        ld (hl),2
.c:     or a
        sbc hl,de
        sbc hl,de
        ld a,(hl)
        or a
        jr nz,.d
        ld (hl),2
.d:     pop hl
        ld a,b
        or c
        jr nz,.l
        ret

; fill: 0 pixels 4-connected to the ring (4) -> 4. Rows from both ends first, then forward (CPIR)
; and backward (CPDR) sweeps over the remaining zeros until stable.
fill:   ld hl,(PL)
        ld de,(PWIDW)
        add hl,de
        inc hl                      ; row 1, col 1
        ld a,(PWID)
        sub 2
        ld b,a                      ; N rows
.rw:    push bc
        push hl
.lf:    ld a,(hl)                   ; from the left
        or a
        jr nz,.le
        ld (hl),4
        inc hl
        jr .lf
.le:    pop hl
        push hl
        ld a,(PWID)
        sub 3
        add hl,a                    ; Z80N: last column of the row
.rt:    ld a,(hl)                   ; from the right
        or a
        jr nz,.re
        ld (hl),4
        dec hl
        jr .rt
.re:    pop hl
        add hl,de
        pop bc
        djnz .rw
        ld a,(PWID)
        ld d,a
        ld e,a
        mul d,e                     ; Z80N
        ld (TV),de                  ; count
        ld de,(PWIDW)
.pass:  xor a
        ld (CHG),a
        ld hl,(PL)                  ; forward
        ld bc,(TV)
.f:     xor a
        cpir
        jr nz,.fe                   ; no zero left
        dec hl
        call one
        inc hl
        ld a,b
        or c
        jr nz,.f
.fe:    ld hl,(PL)                  ; backward
        ld bc,(TV)
        add hl,bc
        dec hl
.b:     xor a
        cpdr
        jr nz,.be
        inc hl
        call one
        dec hl
        ld a,b
        or c
        jr nz,.b
.be:    ld a,(CHG)
        or a
        jr nz,.pass
        ret
one:    dec hl                      ; (HL) = 0: a 4-neighbour is 4 -> 4
        ld a,(hl)
        inc hl
        cp 4
        jr z,.s
        inc hl
        ld a,(hl)
        dec hl
        cp 4
        jr z,.s
        add hl,de
        ld a,(hl)
        or a
        sbc hl,de
        cp 4
        jr z,.s
        or a
        sbc hl,de
        ld a,(hl)
        add hl,de
        cp 4
        ret nz
.s:     ld (hl),4
        ld a,1
        ld (CHG),a
        ret

; =============================================================================================
; aircraft and its shadow: from the map at render (visible cells), into packed planes
aircraft:
        ld a,(AFND)                 ; planes are zero unless the last render drew a figure
        and 3
        jr z,.cz
        ld hl,ASH
        ld (hl),0
        ld de,ASH+1
        ld bc,128*3-1               ; ASH, AIW, AWW
        ldir
.cz:    xor a
        ld (AFND),a
        ld hl,MAP                   ; quick scan: any tile 0x33-0x44 at all?
        ld b,253                    ; 506 cells, 2 per loop
.q:     ld a,(hl)
        sub T_SH
        cp 18
        jr c,.any
        inc hl
        ld a,(hl)
        sub T_SH
        cp 18
        jr c,.any
        inc hl
        djnz .q
        ret
.any:   ld hl,AFND
        set 7,(hl)                  ; tiles 0x33-0x44 in the map: blank their graphics for the render
        ld a,T_SH
        call build
        jr z,.ns
        ld hl,AFND
        set 1,(hl)
        call origin
        ld (SX0),hl
        ld (SY0),de
        ld hl,ASH
        ld (P_I),hl
        ld hl,0
        ld (P_W),hl                 ; no white plane
        ld hl,(SX0)
        ld de,(SY0)
        call pack
.ns:    ld a,T_AIR
        call build
        ret z
        ld hl,AFND
        set 0,(hl)
        call origin
        ld (AX0),hl
        ld (AY0),de
        ld hl,AP
        ld bc,34
        call dilate
        call fill
        ld hl,AIW
        ld (P_I),hl
        ld hl,AWW
        ld (P_W),hl
        ld hl,(AX0)
        ld de,(AY0)
        jp pack

; HL = ACOL * 8 - 4, DE = AROW * 8 - 4 (signed)
origin: ld a,(AROW)
        call s8x8m4
        ex de,hl
        ld a,(ACOL)
s8x8m4: ld l,a
        rla
        sbc a,a
        ld h,a                      ; sign extend
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld de,-4
        add hl,de
        pop de
        ret

; build AP (32 x 32 bytes) from the 9 tiles A .. A + 8 (column-major, 3 x 3) where the map shows
; them; NZ = found. Ink at window x 4 + 8 kc, y 4 + 8 kr.
build:  ld (TBASE),a
        ld hl,AP                    ; padded plane 34 x 34
        ld a,34
        call pinit
        ld hl,MAP                   ; find the first cell holding a tile of the figure
        xor a
        ld (MAPR),a
.fr:    xor a
        ld (MAPC),a
.fc:    ld a,(TBASE)
        ld b,a
        ld a,(hl)
        sub b
        jr c,.fn
        cp 9
        jr c,.found
.fn:    inc hl
        ld a,(MAPC)
        inc a
        ld (MAPC),a
        cp 23
        jr nz,.fc
        ld a,(MAPR)
        inc a
        ld (MAPR),a
        cp 22
        jr nz,.fr
        xor a                       ; Z: not found
        ret
.found: ld c,0                      ; k = A: kc = k / 3, kr = k % 3
.dv:    cp 3
        jr c,.dd
        sub 3
        inc c
        jr .dv
.dd:    ld b,a                      ; B = kr, C = kc
        ld a,(MAPR)
        sub b
        ld (AROW),a
        ld a,(MAPC)
        sub c
        ld (ACOL),a
        xor a
        ld (KC),a
.kc:    xor a
        ld (KR),a
.kr:    ld a,(AROW)                 ; cell row / column, in the map?
        ld b,a
        ld a,(KR)
        add a,b
        cp 22
        jp nc,.kn                   ; (negative wraps to >= 22 too)
        ld (MAPR),a
        ld a,(ACOL)
        ld b,a
        ld a,(KC)
        add a,b
        cp 23
        jp nc,.kn
        ld (MAPC),a
        ld a,(MAPR)
        call mul23
        ld a,(MAPC)
        add hl,a                    ; Z80N
        ld de,MAP
        add hl,de
        ld a,(KC)                   ; expected tile = base + 3 kc + kr
        ld b,a
        add a,a
        add a,b
        ld b,a
        ld a,(KR)
        add a,b
        ld b,a
        ld a,(TBASE)
        add a,b
        cp (hl)
        jp nz,.kn
        ld l,a                      ; graphics TGFX + 8 tile
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,TGFX
        add hl,de
        ld (GPTR),hl
        ; plane row 4 + 8 kr + y, column 4 + 8 kc + bit
        ld a,(KR)
        add a,a
        add a,a
        add a,a
        add a,4
        push de
        ld d,a
        ld e,34
        mul d,e                     ; Z80N
        ex de,hl
        pop de
        ld a,(KC)
        add a,a
        add a,a
        add a,a
        add a,4
        add hl,a                    ; Z80N
        ld de,AP+35
        add hl,de                   ; HL = plane pixel (row, col) for y = 0, bit 0 (past the ring)
        ld b,8
.gy:    push bc
        push hl
        ld de,(GPTR)
        ld a,(de)
        inc de
        ld (GPTR),de
        ld d,a
        ld b,8
.gb:    xor a
        rl d
        rla
        ld (hl),a
        inc hl
        djnz .gb
        pop hl
        ld de,34
        add hl,de
        pop bc
        djnz .gy
.kn:    ld a,(KR)
        inc a
        ld (KR),a
        cp 3
        jp nz,.kr
        ld a,(KC)
        inc a
        ld (KC),a
        cp 3
        jp nz,.kc
        or 1                        ; NZ: found
        ret
addA:   ld e,a
        ld d,0
        add hl,de
        ret

; pack AP into P_I (ink) / P_W (white, 0 = none), 4 bytes x 32 rows, clipped to the play area
; (x 0-183, y 0-175) with the window origin HL = x0, DE = y0
pack:   ld (TV),hl
        ld (TV+2),de
        ld hl,AP+35
        ld b,0                      ; row
.r:     ld c,0                      ; col
.c:     ld a,(hl)
        cp 4
        jp z,.n                     ; outside
        ld (TV+4),a
        cp 1
        jr z,.cl                    ; ink
        ld a,(P_W+1)                ; 0 (hole) / 2 (mask) = white; no white plane: nothing
        or a
        jp z,.n
.cl:    push hl
        push bc
        ld hl,(TV)                  ; x = x0 + col in 0..183?
        ld e,c
        ld d,0
        add hl,de
        ld a,h
        or a
        jr nz,.no
        ld a,l
        cp 184
        jr nc,.no
        ld hl,(TV+2)                ; y = y0 + row in 0..175?
        ld e,b
        ld d,0
        add hl,de
        ld a,h
        or a
        jr nz,.no
        ld a,l
        cp 176
        jr nc,.no
        pop bc
        push bc
        ld a,c
        and 7
        call bitmask
        ld d,a
        ld a,b                      ; byte = row * 4 + col / 8
        add a,a
        add a,a
        ld e,a
        ld a,c
        rrca
        rrca
        rrca
        and 3
        add a,e
        ld e,a
        ld a,(TV+4)
        cp 1
        jr nz,.wt
        ld hl,(P_I)
        jr .set
.wt:    ld hl,(P_W)
.set:   push de
        ld d,0
        add hl,de
        pop de
        ld a,(hl)
        or d
        ld (hl),a
.no:    pop bc
        pop hl
.n:     inc hl
        inc c
        ld a,c
        cp 32
        jp nz,.c
        inc hl                      ; ring
        inc hl
        inc b
        ld a,b
        cp 32
        jp nz,.r
        ret

; =============================================================================================
; upload: per sprite slot 0-28, VIS[n] = has pixels; only those are uploaded (pattern = slot)
upload: xor a
        ld (SPN),a
        ; 0-3: aircraft shadow (4-byte rows, no white)
        ld a,2
        ld (TV+7),a                 ; shadow found bit
        ld hl,ASH
        ld de,ZERO
        xor a
        call up2x2
        ; 4-24: canvas (6-byte rows), 7 rows of 3
        xor a
        ld (CROW),a
.sy:    xor a
        ld (KC),a                   ; sx
.sx:    ld a,(CROW)
        call mul6
        ld a,(KC)
        add a,a
        add hl,a                    ; Z80N
        ld de,CI
        add hl,de
        ld (P_I),hl
        ld a,(CROW)
        ld (ERW),a
        ld a,6
        ld (ST),a
        ld a,1
        ld (ST+1),a                 ; 1 = canvas: white row per canvas row (wrow)
        ld a,(KC)                   ; NEF = OR of ROWOCC rows & column bit
        ld b,a
        ld a,1
        inc b
.cb:    dec b
        jr z,.cbd
        add a,a
        jr .cb
.cbd:   ld c,a
        ld a,(CROW)
        ld hl,ROWOCC
        add hl,a                    ; Z80N
        ld b,16
        xor a
.co:    or (hl)
        inc hl
        djnz .co
        and c
        ld (NEF),a
        call emspr
        ld hl,KC
        inc (hl)
        ld a,(hl)
        cp 3
        jr nz,.sx
        ld a,(CROW)
        add a,16
        ld (CROW),a
        cp 112
        jr nz,.sy
        ; 25-28: aircraft
        ld a,1
        ld (TV+7),a                 ; aircraft found bit
        ld hl,AIW
        ld de,AWW
        ld a,4
        call up2x2
        ret

; 2 x 2 sprites from 4-byte planes: HL = ink, DE = white (ZERO: none), A = white stride (4 / 0)
up2x2:  ld (GPTR),hl
        ld (TV+4),de
        ld (TV+6),a
        xor a
        ld (KR),a                   ; quadrant
.q:     ld a,(KR)
        ld c,0
        bit 1,a
        jr z,.q1
        ld c,64                     ; 16 rows x 4
.q1:    bit 0,a
        jr z,.q2
        inc c
        inc c
.q2:    ld a,c
        ld hl,(GPTR)
        add hl,a                    ; Z80N
        ld (P_I),hl
        ld hl,(TV+4)
        ld a,(TV+6)
        or a
        jr z,.q3
        ld a,c
        add hl,a                    ; Z80N
.q3:    ld (P_W),hl
        ld a,4
        ld (ST),a
        ld a,(TV+6)
        ld (ST+1),a
        ld a,(AFND)
        ld hl,TV+7
        and (hl)
        ld (NEF),a
        call emspr
        ld hl,KR
        inc (hl)
        ld a,(hl)
        cp 4
        jr nz,.q
        ret

; one sprite (slot SPN): 16 rows of 2 bytes at P_I (stride ST) / P_W (stride ST+1)
emspr:  ld a,(NEF)
        ld c,a
        ld a,(SPN)
        ld hl,VIS
        add hl,a                    ; Z80N
        ld a,c
        ld (hl),a
        or a
        jr z,.done
        ld a,(SPN)                  ; pattern select: slot n
        ld b,a
        srl a
        bit 0,b
        jr z,.p
        or 0x80
.p:     ld bc,0x303B
        out (c),a
        ld b,16
.r:     push bc
        ld a,(ST+1)
        cp 1
        call z,wrow
        call emrow
        ld hl,(P_I)
        ld a,(ST)
        add hl,a                    ; Z80N
        ld (P_I),hl
        ld a,(ST+1)
        cp 1
        jr z,.rn
        ld hl,(P_W)
        add hl,a                    ; Z80N
        ld (P_W),hl
.rn:    ld hl,ERW
        inc (hl)
        pop bc
        djnz .r
.done:  ld hl,SPN
        inc (hl)
        ret

; canvas row ERW: P_W = its white row (window rows) or ZERO
wrow:   ld hl,ZERO
        ld (P_W),hl
        ld a,(FLG)
        bit 2,a
        ret z
        ld a,(WB)
        ld b,a
        ld a,(ERW)
        sub b
        ret c
        cp 26
        ret nc
        call mul6
        ld de,WCW
        add hl,de
        ld a,(KC)
        add a,a
        add hl,a                    ; Z80N
        ld (P_W),hl
        ret

; one pattern row: 2 ink bytes at P_I, 2 white bytes at P_W -> 8 bytes to port 0x5B
emrow:  ld hl,(P_I)                 ; fast path: nothing in this row
        ld a,(hl)
        inc hl
        or (hl)
        ld hl,(P_W)
        or (hl)
        inc hl
        or (hl)
        jr nz,.full
        ld b,8
.z:     out (0x5B),a
        djnz .z
        ret
.full:  ld hl,(P_I)
        ld b,(hl)
        ld hl,(P_W)
        ld c,(hl)
        call emb
        ld hl,(P_I)
        inc hl
        ld b,(hl)
        ld hl,(P_W)
        inc hl
        ld c,(hl)
emb:    ld e,4
.l:     xor a
        sla b
        rla
        sla b
        rla
        sla c
        rla
        sla c
        rla
        ld l,a
        ld h,high TBL
        ld a,(hl)
        out (0x5B),a
        dec e
        jr nz,.l
        ret

; =============================================================================================
; sprite attributes: 0-3 shadow (if found), 4-24 canvas, 25-28 aircraft (if found)
attrs:  ld b,0
.s:     ld a,b
        nextreg 0x34,a
        ld hl,VIS
        add hl,a                    ; Z80N
        ld a,(hl)
        or a
        ld a,b
        jp z,.hide
        cp 4
        jr c,.sh
        cp 25
        jr nc,.ai
        sub 4                       ; canvas: X = 104 + 16 sx, Y = 64 + 16 sy
        ld c,0
.d3:    cp 3
        jr c,.d3e
        sub 3
        inc c
        jr .d3
.d3e:   add a,a
        add a,a
        add a,a
        add a,a
        add a,104
        ld l,a
        ld h,0
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
        add a,64
        ld e,a
        ld d,0
        jr .set
.sh:    ld a,(AFND)
        bit 1,a
        jr z,.hide
        ld hl,(SX0)
        ld de,(SY0)
        ld a,b
        jr .q
.ai:    ld a,(AFND)
        bit 0,a
        jr z,.hide
        ld hl,(AX0)
        ld de,(AY0)
        ld a,b
        sub 25
.q:     ; quadrant A (0-3): x += 16 (A & 1), y += 16 (A >> 1); then + 32
        push af
        and 1
        jr z,.q1
        push de
        ld de,16
        add hl,de
        pop de
.q1:    pop af
        and 2
        jr z,.q2
        ex de,hl
        push de
        ld de,16
        add hl,de
        pop de
        ex de,hl
.q2:    push de
        ld de,32
        add hl,de
        pop de
        ex de,hl
        push de
        ld de,32
        add hl,de
        pop de
        ex de,hl
.set:   ld a,l
        nextreg 0x35,a
        ld a,e
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,b
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        ld c,a
        ld a,d
        and 1
        or c
        nextreg 0x39,a
        jr .nx
.hide:  nextreg 0x38,0
.nx:    inc b
        ld a,b
        cp NSPR
        jp nz,.s
        ret
code_end:
        ASSERT code_end <= AP

        ORG TBL
tbl:    DB 0x00,0x02,0x20,0x22,0x01,0x02,0x21,0x22,0x10,0x12,0x20,0x22,0x11,0x12,0x21,0x22
        ORG ZERO
        DS 8,0
page_end:

; --- setup routine (stub bank, 0xD000): palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x43,0x20           ; sprite palette 0
        nextreg 0x40,1
        nextreg 0x41,0x00           ; index 1: ink (black)
        nextreg 0x40,2
        nextreg 0x41,0xFF           ; index 2: mask (white)
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
setup_end:

        SAVEBIN "cy_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "cy_code.bin",0xC000,code_end-0xC000
        SAVEBIN "cy_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "cy_tbl.bin",TBL,16
