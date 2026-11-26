; Yie Ar Kung-Fu (Imagine 1985, 128K edition) - fighters, thrown objects, chain and hit spark become 4-bit
; hardware sprites; scenery, HUD and text stay on the ULA. Facts: games/yie_ar_kung_fu.md.
;
; Drawing in the original: two screens (bank 5, bank 7), one shown, 7FFD bit 3 flips at 0xB3FC once a tick.
;   Fighters  0xB423: LDIR restores old rectangles from the clean copy (0x5B00-), then 0xB4EC / 0xB528 CALL 0xB5D8
;             plot each object on the hidden screen: W, H, then (mask, graphics) pairs; byte aligned, or shifted by a nibble.
;   Stars     0xF563 CALL 0xF56C: OR plot of 8 lines on the SHOWN screen after the flip, wiped before the next flip by 0xF57A.
;   Chain     0xEF36 / 0xEF73: XOR plot of 5 lines, C columns, right or left, on the shown screen; 0xEFAB wipes it.
;   Spark     0xB8FC: 8 x 8 on the shown screen with one attribute cell, held 10 HALTs, restored by 0xF490.
; Method: the game's own code runs, the same instructions in the same order. Only the stores change: each store to a
; screen is a NOP, so both screens stay clean and the game's restores copy clean bytes over clean bytes.
;
; Patch sites (original bytes verified by yie_ar_kung_fu.py):
;   0xB4EC, 0xB528  CD D8 B5  CALL 0xB5D8 -> CALL e_plot: note the object, then the plot's own bookkeeping runs
;   0xB632 0xB6AC 0xB6C4 0xB73A 0xB7BA 0xB7D7  12 LD (DE),A -> 00   fighter stores
;   0xB3F9          01 FD 7F  LD BC,32765 -> CALL e_flip: commit this tick's sprites, then the flip
;   0xF563          CD 6C F5  CALL 0xF56C -> CALL e_star;   0xF571  12 LD (DE),A -> 00
;   0xEF25          22 E3 BD  LD (48611),HL -> CALL e_chain;  0xEF39, 0xEF76  77 LD (HL),A -> 00
;   0xEFAB          2A E3 BD  LD HL,(48611) -> JP e_cwipe (keeps the interrupt state: 0xADDD calls it with DI)
;   0xB908          3A C8 B9  LD A,(47560) -> CALL e_spark;  0xB90B 0xB914 0xB91B 0xB948  77/12 attribute stores -> 00
;   0xB92D          12 LD (DE),A -> 00 spark store
;   0xB91C          CD 90 F4  CALL 0xF490 -> CALL e_spoff
;   0xAAAF          21 FF 5A  LD HL,23295 -> JP e_wa;  0xAAE9  3A CF BD  LD A,(48591) -> JP e_wb: the two wipes, all sprites off
; Hook code: stubs in alt ROM image 1 (0x386E-, free in the 48K ROM), the rest in page H at slot 7, interrupts off.

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"     ; macros only

HPG     EQU 26                  ; hook page, MMU slot 0 while a hook runs

; ---- page H at 0xE000 (slot 7: nothing a hook reads lives there; the game's stars are below 0xE000) ----
HB      EQU 0xE000
V_SP    EQU HB+0x0000
V_NP    EQU HB+0x0002              ; plots this tick
V_SHOWN EQU HB+0x0003              ; figure blocks shown
V_RING  EQU HB+0x0004              ; 1 = outline
V_W     EQU HB+0x0005              ; canvas columns in bytes
V_LN    EQU HB+0x0006              ; canvas lines
V_TF    EQU HB+0x0007              ; (2) tile flags of the last convert: bit = row*4+col
V_PAT   EQU HB+0x0009              ; first pattern of the last convert
V_COLS  EQU HB+0x000A              ; tile columns
V_ROWS  EQU HB+0x000B              ; tile rows
V_X     EQU HB+0x000C              ; (2) sprite X
V_Y     EQU HB+0x000E              ; (2) sprite Y
V_A2    EQU HB+0x0010              ; attribute 2 base: palette offset, mirror
V_SL    EQU HB+0x0011              ; next slot
V_CHN   EQU HB+0x0012              ; chain sprites shown
V_CHB   EQU HB+0x0013              ; (5) chain bytes the patterns hold
V_SPK   EQU HB+0x0018              ; spark shown
V_STS   EQU HB+0x0019              ; stars shown: bits
V_DROP  EQU HB+0x001A              ; (2) nothing drawn though asked (diagnostic)
V_K     EQU HB+0x001C              ; temporaries
V_L     EQU HB+0x001D
V_TMP   EQU HB+0x001E
V_I0    EQU HB+0x0020
V_I1    EQU HB+0x0021
V_B1    EQU HB+0x0022
V_CA    EQU HB+0x0024       ; (2) this object's record
V_DST   EQU HB+0x0026       ; (2) tiles in memory
V_ENT   EQU HB+0x0028       ; (2) table entry
V_IDX   EQU HB+0x002A
V_PG    EQU HB+0x002B
V_LIN   EQU HB+0x002C
V_LF    EQU HB+0x002D
V_R     EQU HB+0x002E
V_T     EQU HB+0x002F
V_TFW   EQU HB+0x0030       ; (2)
V_N     EQU HB+0x0032
V_SOL   EQU HB+0x0033       ; 0x0F: small8s fills the silhouette (the spark's cell is opaque), 0: ink only
V_SPD   EQU HB+0x0034       ; hlib_speed latch: the caller's CPU speed, given back on every exit
V_CAVE  EQU HB+0x0035       ; 1 = the Feedle caves are on Layer 2
V_CX    EQU HB+0x0036       ; cave being drawn: left x
V_CY    EQU HB+0x0037       ;   line
V_CN    EQU HB+0x0038       ;   lines left
V_CF    EQU HB+0x0039       ;   0xFF on the solid fill lines
V_CAVEP EQU HB+0x003A       ; 1 = the game drew the caves on the hidden screen this tick (0xB547)
V_GBODY EQU HB+0x003B       ; 1 = default colours: figure bodies take the ground's paper (Python sets it)
V_GROUND EQU HB+0x003C      ; the body colour last written to the sprite palette
GROUND  EQU 0x5800+22*32+2  ; a ground cell's attribute (lawn, courtyard; the caves are pixels only)
L2BANK  EQU 30              ; Layer 2 (16K banks 30-32, 8K pages 60-65): the Feedle caves over the sprites, else transparent
L2PG    EQU 60
CAVEF   EQU 48575           ; non-zero: the game draws the two caves each tick (0xB547)
CAVEL   EQU 41500           ; their rows (5 bytes drawn, 6 apart: 0xB5C3), OR plotted from line 144 at x 0 and x 216
CAVER   EQU 41741
BITS    EQU HB+0x00F0       ; 1, 2, 4, 8, written by Python
PLOTS   EQU HB+0x0100              ; 4 x 8: object, ptr (2), x, y, mirror, -, -
CACHE   EQU HB+0x0140              ; 4 x 8: ptr (2), tile flags (2), W, H, -, -
CODE0   EQU HB+0x0600
CTAB    EQU HB+0x0200       ; 128 x 8: frame (2), flags (2), canvas bytes, lines; empty when frame = 0
TAB     EQU HB+0x1800              ; 4 pages: byte -> nibbles 0/1, one page per output byte; written by Python
PM      EQU HB+0x1200          ; silhouette plane: 8 x 64
PI      EQU PM + 0x0200         ; ink plane
PR      EQU PM + 0x0400         ; ring plane
HSTK    EQU HB+0x1F00
SCR     EQU HB+0x1C00       ; scratch tile
STORE   EQU 28              ; store pages 28-59: 4 x 2048 per page

MAXPL   EQU 4
BLOCK   EQU 16                  ; sprites per plot
SCHAIN  EQU 80                  ; chain: slots 80-111, on top of the figures
NCHAIN  EQU 32
SSTAR   EQU 120                 ; stars: slots 120-122
SSPARK  EQU 127
PSTAR   EQU 64                  ; patterns 64-66 stars, 67 spark, 68 chain whole, 69 chain half
PSPARK  EQU 67
PCH     EQU 68

OBJI    EQU 48570               ; (2) current object
FPTR    EQU 47088               ; (2) frame being plotted
FLIP    EQU 48526               ; object's mirror flag
POS     EQU 48553               ; object's x, y
STARI   EQU 47565
CHDIR   EQU 48607
CHBYTES EQU 48540
SPKINK  EQU 47560

        MACRO ENTER
        di
        nextreg 0x57,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        push ix
        HLIB_SPEED_IN_ABC V_SPD     ; A, F, B, C are on the hook stack
        ENDM

        MACRO LEAVEDI
        HLIB_SPEED_OUT_A V_SPD      ; the caller's speed; A comes back from the stack
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x57,15
        ENDM

        MACRO LEAVE
        LEAVEDI
        ei
        ENDM

; ---- alt ROM stubs ----
        ORG 0x386E

e_plot: ENTER
        call c_plot
        LEAVE
        jp 0xB5D8

e_flip: ENTER
        call c_flip
        LEAVE
        ld bc,32765
        ret

e_star: ENTER
        call c_star
        LEAVE
        jp 0xF56C

e_chain: ENTER
        call c_chain
        LEAVE
        ld (48611),hl
        ret

e_cwipe: push af
        ld a,i
        di
        push af                     ; P/V = IFF
        nextreg 0x57,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push bc
        push de
        push hl
        push ix
        HLIB_SPEED_IN_ABC V_SPD     ; A, F on the game's stack, B, C on the hook stack
        call c_cwipe
        HLIB_SPEED_OUT_A V_SPD      ; A comes back from the game's stack
        pop ix
        pop hl
        pop de
        pop bc
        ld sp,(V_SP)
        nextreg 0x57,15
        pop af
        jp po,.di
        pop af
        ei
        ld hl,(48611)
        jp 0xEFAE
.di:    pop af
        ld hl,(48611)
        jp 0xEFAE

e_spark: ENTER
        call c_spark
        LEAVE
        ld a,(SPKINK)
        ret

e_spoff: ENTER
        call c_spoff
        LEAVE
        jp 0xF490

e_wa:   ENTER
        call c_wipe
        LEAVE
        ld hl,23295
        jp 0xAAB2

e_wb:   ENTER
        call c_wipe
        LEAVE
        ld a,(48591)
        jp 0xAAEC

e_cave: ENTER
        call c_cave
        LEAVE
        ld a,(CAVEF)
        ret
rom_end:

; ---- page H ----
        ORG CODE0

; the plot's own state is read here: which object, which frame, where, which way
c_plot: ld a,(V_NP)
        cp MAXPL
        jr nc,.full
        ld l,a
        inc a
        ld (V_NP),a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,PLOTS
        add hl,de
        ld a,(OBJI)
        ld (hl),a
        inc hl
        ld de,(FPTR)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld e,a
        ld d,0
        ex de,hl
        add hl,hl
        ld bc,POS
        add hl,bc
        ld a,(hl)
        ld (de),a
        inc de
        inc hl
        ld a,(hl)
        ld (de),a
        inc de
        ld a,(OBJI)
        ld l,a
        ld h,0
        ld bc,FLIP
        add hl,bc
        ld a,(hl)
        ld (de),a
        ret
.full:  ld hl,(V_DROP)
        inc hl
        ld (V_DROP),hl
        ret

; before the flip: the stars come off (the game has just wiped them) and this tick's figures go up
c_flip: call cave_flip
        call ground_body
        ld a,(V_STS)
        or a
        call nz,hide_stars
        xor a
        ld (V_K),a
.lp:    ld a,(V_K)
        ld hl,V_NP
        cp (hl)
        jr nc,.rest
        call fig
        ld hl,V_K
        inc (hl)
        jr .lp
.rest:  ld a,(V_K)              ; blocks shown last tick and not this one
        ld hl,V_SHOWN
        cp (hl)
        jr nc,.done
        call hide_block
        ld hl,V_K
        inc (hl)
        jr .rest
.done:  ld a,(V_NP)
        ld (V_SHOWN),a
        xor a
        ld (V_NP),a
        ret

hide_block:                     ; A = block
        add a,a
        add a,a
        add a,a
        add a,a
        ld b,BLOCK
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        ret

hide_stars:
        ld a,SSTAR
        ld b,3
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        xor a
        ld (V_STS),a
        ret

; one figure: V_K = plot number
fig:    ld a,(V_K)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,PLOTS
        add hl,de
        push hl
        pop ix                  ; IX = plot: object, ptr, x, y, mirror
        ld a,(ix+0)
        and 3
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CACHE
        add hl,de               ; HL = what this object's patterns hold
        ld (V_CA),hl
        ld e,(ix+1)
        ld d,(ix+2)
        ld a,(hl)
        cp e
        jr nz,.conv
        inc hl
        ld a,(hl)
        cp d
        jr z,.same
.conv:  push ix
        call find               ; -> HL = entry in the table, store page mapped, V_DST = its tiles; converted if new
        pop ix
        ; entry: ptr, flags (2), canvas bytes, lines -> the object's record
        ld de,(V_CA)
        ld bc,6
        ldir
        ld a,(ix+0)
        and 3
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_PAT),a
        ld hl,(V_CA)
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_TF),de
        call upload
        nextreg 0x56,14
.same:  ld hl,(V_CA)
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_TF),de
        inc hl
        ld c,(hl)               ; canvas bytes W + 2
        inc hl
        ld b,(hl)               ; canvas lines H + 2
        ; X: the plot's own place: byte column, and a nibble or a byte more (the canvas has a byte of margin).
        ; Unmirrored: aligned at the column, unaligned a nibble right (0xB64E: RRD shift). Mirrored (0xB6DD) the
        ; other way round: unaligned copies whole bytes from one byte right (+8), aligned shifts a nibble (+4).
        ld a,(ix+3)
        ld e,a
        and 0xF8
        ld l,a
        ld h,0
        ld a,(ix+5)
        or a
        jr nz,.axm
        ld a,e
        and 7
        jr z,.ax
        ld de,4
        jr .ax4
.axm:   ld a,e
        and 7
        ld de,4
        jr z,.ax4
        ld e,8
.ax4:   add hl,de
.ax:    ld de,32-8
        add hl,de
        ld (V_X),hl
        ; Y: line = 190 - y - H, the margin one line above it
        ld a,190+2              ; lines = H + 2
        sub (ix+4)
        sub b
        ld l,a
        ld h,0
        ld de,32-1
        add hl,de
        ld (V_Y),hl
        ld a,(ix+0)             ; palette offset: object 0, object 1, the rest
        and 3
        cp 2
        jr c,.p
        ld a,2
.p:     rlca
        rlca
        rlca
        rlca
        ld d,a
        ld a,(ix+5)
        or a
        ld a,d
        jr z,.nm
        or 8
.nm:    ld (V_A2),a
        ld a,(V_K)
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_SL),a             ; slots of this block
        ld a,(ix+0)
        and 3
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_PAT),a
        ld a,c
        ld (V_L),a              ; canvas bytes for mirror
        ; fall through

; set the block's sprites from V_TF, V_PAT, V_X, V_Y, V_A2, V_SL; the rest of the block hidden
attrs:  ld de,(V_TF)
        ld c,0                  ; tile number
        ld b,BLOCK
.lp:    push bc
        ld a,(V_SL)
        add a,c
        nextreg 0x34,a
        srl d
        rr e
        jr nc,.off
        push de
        ; X of this tile
        ld a,c
        and 3
        ld e,a                  ; column
        ld a,(V_A2)
        and 8
        jr nz,.mx
        ld a,e
        rlca
        rlca
        rlca
        rlca
        ld e,a
        ld d,0
        ld hl,(V_X)
        add hl,de
        jr .xk
.mx:    ld hl,(V_X)             ; mirrored: left = X + canvas width - 16 (col + 1)
        ld a,(V_L)
        add a,a
        add a,a
        add a,a
        ld d,0
        push de
        ld e,a
        add hl,de
        pop de
        ld a,e
        inc a
        rlca
        rlca
        rlca
        rlca
        ld e,a
        ld d,0
        or a
        sbc hl,de
.xk:    ld a,l
        nextreg 0x35,a
        ld a,(V_A2)
        or h
        and 0xF9
        nextreg 0x37,a
        ; Y
        ld a,c
        rrca
        rrca
        and 3
        rlca
        rlca
        rlca
        rlca
        ld e,a
        ld d,0
        ld hl,(V_Y)
        add hl,de
        ld a,l
        nextreg 0x36,a
        ld b,h
        ld a,(V_PAT)
        add a,c
        ld d,a                  ; pattern
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,d
        and 1
        rrca
        rrca
        or 0x80
        or b
        nextreg 0x39,a
        pop de
        pop bc
        inc c
        dec b
        jp nz,.lp
        ret
.off:   nextreg 0x38,0
        pop bc
        inc c
        dec b
        jp nz,.lp
        ret

; DE = frame -> table entry for it: HL = entry, store page mapped at slot 6, V_DST = its tiles; converted on a miss
find:   ld a,e
        rra
        rra
        rra
        and 0x1F
        ld l,a
        ld a,d
        xor e
        rrca
        rrca
        and 0x60
        or l                    ; 7 bits
        ld (V_IDX),a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,CTAB
        add hl,bc
        ld (V_ENT),hl
        push de
        ; page = 28 + idx / 4; tiles at 0xC000 + (idx & 3) * 2048
        ld a,(V_IDX)
        rrca
        rrca
        and 0x3F
        add a,STORE
        ld (V_PG),a
        ld a,(V_IDX)
        and 3
        rlca
        rlca
        rlca
        add a,0xC0
        ld (V_DST+1),a
        xor a
        ld (V_DST),a
        pop de
        ld a,(hl)
        cp e
        jr nz,.miss
        inc hl
        ld a,(hl)
        cp d
        jr nz,.miss
        ld a,(V_PG)
        nextreg 0x56,a
        ld hl,(V_ENT)
        ret
.miss:  ld hl,(V_ENT)
        ld (hl),e
        inc hl
        ld (hl),d
        push de
        call convert            ; planes, ring; flags in V_TF; needs the game's bank 7 no more
        ld a,(V_PG)
        nextreg 0x56,a
        call tiles
        pop de
        ld hl,(V_ENT)
        inc hl
        inc hl
        ld de,(V_TF)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_W)
        ld (hl),a
        inc hl
        ld a,(V_LN)
        ld (hl),a
        ld hl,(V_ENT)
        ret

; DE = frame: W, H, (mask, graphics) pairs -> planes and ring
convert:
        ex de,hl
        ld a,(hl)
        inc hl
        ld c,a                  ; W
        add a,2
        ld (V_W),a
        ld a,(hl)
        inc hl
        ld b,a                  ; H
        add a,2
        ld (V_LN),a
        push hl
        push bc
        call clear
        pop bc
        pop hl
        ld de,PM+8+1            ; line 1, column 1
.ln:    push bc
        push de
        ld b,c
.by:    ld a,(hl)               ; mask
        inc hl
        cpl
        or (hl)                 ; silhouette: not masked, or ink
        ld (de),a
        inc d
        inc d                   ; PI = PM + 0x200
        ld a,(hl)
        ld (de),a
        inc hl
        dec d
        dec d
        inc de
        djnz .by
        pop de
        ld a,8
        add a,e
        ld e,a
        jr nc,.nc
        inc d
.nc:    pop bc
        djnz .ln
        ld a,(V_RING)
        ld (V_TMP),a
        jp ring

; clear the planes for this canvas: lines rounded up to whole tiles
clear:  ld a,(V_LN)
        add a,15
        and 0xF0
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; bytes per plane
        ld c,l
        ld b,h
        push bc
        ld hl,PM
        ld de,PM+1
        ld (hl),0
        dec bc
        ldir
        pop bc
        push bc
        ld hl,PI
        ld de,PI+1
        ld (hl),0
        dec bc
        ldir
        pop bc
        ld hl,PR
        ld de,PR+1
        ld (hl),0
        dec bc
        ldir
        ret

; ring plane: a neighbour above, below, left or right is in the silhouette, and this pixel is not; V_TF = tiles used
ring:   ld hl,0
        ld (V_TF),hl
        xor a
        ld (V_LIN),a
.line:  ld a,(V_LIN)
        ld hl,V_LN
        cp (hl)
        ret nc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,PM
        add hl,bc               ; HL = silhouette line
        push hl
        pop ix
        ld bc,-8
        add ix,bc               ; IX = the line above (8 zero bytes lie before PM)
        xor a
        ld (V_LF),a
        ld a,(V_W)
        ld b,a
        ld c,0                  ; byte on the left
        ld e,0                  ; column
.byt:   ld d,(hl)               ; this
        inc hl                  ; HL = byte on the right
        ld a,(ix+0)
        or (ix+16)
        or d
        or c
        or (hl)
        jr z,.next
        ld a,(V_TMP)
        or a
        jr z,.store
        ld a,(hl)
        rlca
        and 1
        ld (V_R),a
        ld a,c
        rrca
        and 0x80
        push hl
        ld hl,V_R
        or (hl)
        ld (hl),a
        ld a,d
        srl a
        or (hl)
        ld (hl),a
        ld a,d
        add a,a
        or (hl)
        pop hl
        or (ix+0)
        or (ix+16)
        ld c,a
        ld a,d
        cpl
        and c                   ; ring byte
.store: dec hl
        inc h
        inc h
        inc h
        inc h
        ld (hl),a
        dec h
        dec h
        dec h
        dec h
        inc hl
        or d
        jr z,.next
        ld a,e                  ; this tile column has something on this line
        rrca
        and 3
        push hl
        ld hl,BITS
        add a,l
        ld l,a
        ld a,(hl)
        ld hl,V_LF
        or (hl)
        ld (hl),a
        pop hl
.next:  ld c,d
        inc ix
        inc e
        dec b
        jp nz,.byt
        ; this line's four flags into V_TF at its row
        ld a,(V_LF)
        or a
        jr z,.nl
        ld c,a
        ld a,(V_LIN)
        ld b,a
        and 0x10
        ld a,c
        jr z,.lo
        rlca
        rlca
        rlca
        rlca
.lo:    ld c,a
        ld a,b
        and 0x20
        ld hl,V_TF
        jr z,.lb
        inc hl
.lb:    ld a,(hl)
        or c
        ld (hl),a
.nl:    ld hl,V_LIN
        inc (hl)
        jp .line

; the flagged tiles into memory at V_DST: tile number * 128; 16 lines x 8 bytes; a pixel is 1 ink, 2 body, 3 ring
tiles:  ld hl,(V_TF)
        ld (V_TFW),hl
        xor a
        ld (V_T),a
.tile:  ld a,(V_TFW)
        rrca
        jp nc,.skip
        ld a,(V_T)              ; destination
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_DST)
        add hl,de
        ex de,hl
        ld a,(V_T)              ; plane address: row * 128 + column * 2
        and 12
        rlca
        rlca
        rlca
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(V_T)
        and 3
        add a,a
        add a,l
        ld l,a
        ld bc,PM
        add hl,bc
        ld a,16
.ln:    ld (V_N),a
        call pix
        inc l
        call pix
        ld bc,7
        add hl,bc
        ld a,(V_N)
        dec a
        jr nz,.ln
.skip:  ld hl,V_TFW+1
        srl (hl)
        dec hl
        rr (hl)
        ld hl,V_T
        inc (hl)
        ld a,(hl)
        cp BLOCK
        jp c,.tile
        ret

; HL = silhouette byte (the ink plane 0x200 on, the ring 0x400 on) -> four pattern bytes at DE; HL, DE moved on as said
pix:    ld b,(hl)
        inc h
        inc h
        ld c,(hl)
        inc h
        inc h
        ld a,b
        or (hl)
        jr z,.zero
        ld a,b
        xor c
        ld b,a                  ; body
        ld a,(hl)
        or c
        ld c,a                  ; ink | ring
        ld a,(hl)
        or b
        ld b,a                  ; body | ring
        push hl
        ld h,TAB/256
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        or (hl)
        ld (de),a
        inc de
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        or (hl)
        ld (de),a
        inc de
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        or (hl)
        ld (de),a
        inc de
        inc h
        ld l,b
        ld a,(hl)
        add a,a
        ld l,c
        or (hl)
        ld (de),a
        inc de
        pop hl
        jr .back
.zero:  xor a
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld (de),a
        inc de
.back:  dec h
        dec h
        dec h
        dec h
        ret

; the flagged tiles from V_DST to pattern memory from V_PAT
upload: ld hl,(V_TF)
        ld (V_TFW),hl
        xor a
        ld (V_T),a
.tile:  ld a,(V_TFW)
        rrca
        jr nc,.skip
        ld a,(V_PAT)
        ld hl,V_T
        add a,(hl)
        ld b,a
        srl a
        ld d,a
        ld a,b
        and 1
        rrca
        or d
        ld bc,0x303B
        out (c),a
        ld a,(V_T)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_DST)
        add hl,de
        ld bc,0x805B
        otir
.skip:  ld hl,V_TFW+1
        srl (hl)
        dec hl
        rr (hl)
        ld hl,V_T
        inc (hl)
        ld a,(hl)
        cp BLOCK
        jr c,.tile
        ret

; a small tile just built in the planes: to the scratch tile, then pattern memory
emit:   call ring
        ld hl,SCR
        ld (V_DST),hl
        call tiles
        jp upload

; ---- stars ----
; DE = screen address, HL = 8 bytes of graphics; star number in STARI
c_star: ld a,(STARI)
        and 3
        ld (V_K),a
        push de
        call small8
        pop de
        ld a,(V_K)
        add a,PSTAR
        ld (V_PAT),a
        ld a,(V_K)
        add a,SSTAR
        ld (V_SL),a
        ld hl,V_STS
        set 0,(hl)
        ld a,0x20               ; palette offset 2
        jr place8

; ---- spark ----
; the game has just stored the shown screen's cell in 47566; the graphic is at 47393; no outline on a spark
c_spark:
        ld hl,47393
        ld a,(V_RING)                   ; the build's outline setting, given back after the spark
        push af
        xor a
        ld (V_RING),a
        call small8s
        pop af
        ld (V_RING),a
        ld a,PSPARK
        ld (V_PAT),a
        ld a,SSPARK
        ld (V_SL),a
        ld a,1
        ld (V_SPK),a
        ld a,(SPKINK)
        and 7
        add a,a
        ld hl,SPKP
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        nextreg 0x40,0x31       ; palette entry group 3, ink
        nextreg 0x41,a
        ld a,(SPKINK)           ; body = the cell's paper
        rrca
        rrca
        rrca
        and 7
        add a,a
        ld hl,SPKP
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        nextreg 0x40,0x32       ; palette entry group 3, body
        nextreg 0x41,a
        ld de,(47566)
        ld a,0x30               ; palette offset 3
        ; fall through
place8: push af
        ; D, E = screen address -> line, column
        ld a,d
        and 7
        ld c,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or c
        ld c,a
        ld a,d
        and 0x18
        rlca
        rlca
        rlca
        or c
        ld c,a                  ; line
        ld a,e
        and 0x1F
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32-4
        add hl,de               ; X
        ld a,(V_SL)
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        pop af
        or h
        and 0xF1
        nextreg 0x37,a
        ld a,c
        add a,32-1
        nextreg 0x36,a
        ld a,(V_PAT)
        ld d,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,d
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; spark's star: uses the same canvas, pattern PSPARK
small8s:
        ld a,0x0F               ; the game copies the spark over its whole cell: zero bits are paper, not see-through
        ld (V_SOL),a
        ld a,PSPARK
        jr sm8
; 8 lines at HL onto a 16 x 16 tile, a nibble in, one line down
small8: xor a
        ld (V_SOL),a
        ld a,(V_K)
        add a,PSTAR
sm8:    ld (V_PAT),a
        push hl
        ld a,2
        ld (V_W),a
        ld a,10
        ld (V_LN),a
        call clear
        pop hl
        ld de,PM+8
        ld b,8
.l:     ld a,(hl)
        inc hl
        ld c,a
        rrca
        rrca
        rrca
        rrca
        and 15
        inc d
        inc d
        ld (de),a               ; ink plane
        dec d
        dec d
        push hl
        ld hl,V_SOL
        or (hl)
        ld (de),a               ; silhouette: the ink, or the whole cell
        inc e
        ld a,c
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        inc d
        inc d
        ld (de),a
        dec d
        dec d
        ld c,a
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        or c
        pop hl
        ld (de),a
        ld a,e
        add a,7
        ld e,a
        jr nc,.c
        inc d
.c:     djnz .l
        ld a,(V_RING)
        ld (V_TMP),a
        jp emit

; ---- chain ----
; HL = screen address of the first column, C = columns (C & 31 at the site is in 47257)
c_chain:
        push hl
        ; patterns when the bytes change
        ld hl,CHBYTES
        ld de,V_CHB
        ld b,5
        ld c,0
.cmp:   ld a,(de)
        cp (hl)
        jr z,.s
        inc c
        ld (de),a
        ld a,(hl)
        ld (de),a
.s:     inc hl
        inc de
        djnz .cmp
        ld a,c
        or a
        call nz,ch_pat
        pop de                  ; DE = screen address
        ; line, column as place8
        ld a,d
        and 7
        ld c,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or c
        ld c,a
        ld a,d
        and 0x18
        rlca
        rlca
        rlca
        or c
        add a,32-1
        ld (V_Y),a
        ld a,e
        and 0x1F
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_X),hl             ; X of column 0
        ld a,(47257)
        ld (V_K),a              ; columns left
        ld a,(CHDIR)
        ld (V_L),a
        ld a,SCHAIN
        ld (V_SL),a
        ld a,(V_CHN)
        push af
        xor a
        ld (V_CHN),a
.lp:    ld a,(V_K)
        or a
        jr z,.tail
        ld b,PCH
        cp 2
        jr nc,.w
        inc b                   ; half tile for a last single column
.w:     ld a,b
        ld (V_PAT),a
        ld hl,(V_X)
        ld a,(V_L)
        or a
        jr z,.fw
        ld a,(V_K)              ; going left: the tile's left edge is one column back, unless a half
        cp 2
        jr c,.fw
        ld de,-8
        add hl,de
.fw:    ld a,(V_SL)
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        or 0x20
        nextreg 0x37,a
        ld a,(V_Y)
        nextreg 0x36,a
        ld a,(V_PAT)
        ld d,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,d
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ; next tile
        ld hl,V_SL
        inc (hl)
        ld hl,V_CHN
        inc (hl)
        ld a,(V_K)
        sub 2
        jr nc,.m
        xor a
.m:     ld (V_K),a
        ld hl,(V_X)
        ld de,16
        ld a,(V_L)
        or a
        jr z,.ad
        ld de,-16
.ad:    add hl,de
        ld (V_X),hl
        ld a,(V_CHN)
        cp NCHAIN
        jr c,.lp
.tail:  pop af                  ; hide what was shown beyond this
        ld hl,V_CHN
        sub (hl)
        ret c
        ret z
        ld b,a
        ld a,(V_SL)
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        ret

; chain patterns: two tiles from the five bytes
ch_pat: ld a,2
        ld (V_W),a
        ld a,7
        ld (V_LN),a
        call clear
        ld hl,CHBYTES
        ld de,PM+8
        ld b,5
.l:     ld a,(hl)
        inc hl
        ld (de),a
        inc d
        inc d
        ld (de),a
        dec d
        dec d
        inc e
        ld (de),a
        inc d
        inc d
        ld (de),a
        dec d
        dec d
        ld a,e
        add a,7
        ld e,a
        jr nc,.c
        inc d
.c:     djnz .l
        ld a,PCH
        ld (V_PAT),a
        ld a,(V_RING)
        ld (V_TMP),a
        call emit
        ; half: drop the second column
        ld a,2
        ld (V_W),a
        ld a,7
        ld (V_LN),a
        call clear
        ld hl,CHBYTES
        ld de,PM+8
        ld b,5
.l2:    ld a,(hl)
        inc hl
        ld (de),a
        inc d
        inc d
        ld (de),a
        dec d
        dec d
        ld a,e
        add a,8
        ld e,a
        jr nc,.c2
        inc d
.c2:    djnz .l2
        ld a,PCH+1
        ld (V_PAT),a
        jp emit

c_cwipe:
        ld a,(V_CHN)
        or a
        ret z
        ld b,a
        ld a,SCHAIN
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        xor a
        ld (V_CHN),a
        ret

c_spoff:
        xor a
        ld (V_SPK),a
        nextreg 0x34,SSPARK
        nextreg 0x38,0
        ret

; a wipe: every sprite off, and the frames may change under the same addresses
c_wipe: xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        xor a
        ld (V_NP),a
        ld (V_SHOWN),a
        ld (V_CHN),a
        ld (V_SPK),a
        ld (V_STS),a
        ld hl,CACHE
        ld de,CACHE+1
        ld (hl),0
        ld bc,31
        ldir
        ld hl,CTAB
        ld de,CTAB+1
        ld (hl),0
        ld bc,1023
        ldir
        ld a,(V_CAVE)
        or a
        call nz,cave_clear
        ret

; ---- Feedle's caves: the game ORs them over everything each tick (0xB560, 0xB588, 0xB5AA), so a clone inside is
; hidden in the black. Their ink pixels go on Layer 2, over the sprites (LSU); the rest of Layer 2 is transparent.
; 0xB547 notes that the game drew them on the hidden screen; the flip (c_flip) shows them on Layer 2 with that screen.
c_cave: ld a,(CAVEF)
        or a
        ret z
        ld a,1
        ld (V_CAVEP),a
        ret

cave_flip:
        ld a,(CAVEF)
        or a
        jp z,cave_off
        ld a,(V_CAVEP)
        or a
        ret z
        xor a
        ld (V_CAVEP),a
        ld a,(V_CAVE)
        or a
        ret nz
        inc a
        ld (V_CAVE),a
        ld hl,CAVEL
        xor a
        call cave_draw
        ld hl,CAVER
        ld a,216
cave_draw:                          ; HL = 40 rows of 5 bytes, A = left x: lines 144-181 from the rows, 182-187 solid
        ld (V_CX),a
        ld a,144
        ld (V_CY),a
        ld a,44
        ld (V_CN),a
.ln:    ld a,(V_CN)
        cp 7
        sbc a,a
        ld (V_CF),a
        call l2_line
        ld b,5
.by:    ld a,(V_CF)
        or a
        ld a,0xFF
        jr nz,.fill
        ld a,(hl)
        inc hl
.fill:  ld c,8
.bt:    rla
        push af
        ld a,0xE3
        jr nc,.w
        xor a
.w:     ld (de),a
        inc e
        pop af
        dec c
        jr nz,.bt
        djnz .by
        inc hl                              ; the row's sixth byte is not drawn
        ld a,(V_CY)
        inc a
        ld (V_CY),a
        ld a,(V_CN)
        dec a
        ld (V_CN),a
        jr nz,.ln
        nextreg 0x56,14
        ret

l2_line:                            ; DE = Layer 2 address of (V_CX, V_CY), its page at slot 6
        ld a,(V_CY)
        ld c,a
        and 0xE0
        rlca
        rlca
        rlca
        add a,L2PG
        nextreg 0x56,a
        ld a,c
        and 0x1F
        or 0xC0
        ld d,a
        ld a,(V_CX)
        ld e,a
        ret

cave_off:
        ld a,(V_CAVE)
        or a
        ret z
cave_clear:                         ; both caves transparent again (also on a wipe)
        xor a
        ld (V_CAVE),a
        ld (V_CAVEP),a
        ld a,144
        ld (V_CY),a
.cl:    xor a
        ld (V_CX),a
        call l2_line
        ld a,0xE3
        ld b,40
.c1:    ld (de),a
        inc e
        djnz .c1
        ld e,216
        ld b,40
.c2:    ld (de),a
        inc e
        djnz .c2
        ld a,(V_CY)
        inc a
        ld (V_CY),a
        cp 188
        jr nz,.cl
        nextreg 0x56,14
        ret

; The original shows a figure's body (its mask, no ink) in the paper of the cells under it: the lawn's cyan, the
; courtyard's yellow. Default colours give every body the ground's paper, set at each flip when it changes.
ground_body:
        ld a,(V_GBODY)
        or a
        ret z
        ld a,(GROUND)
        ld c,a
        rrca
        rrca
        rrca
        and 7
        bit 6,c
        jr z,.nb
        or 8
.nb:    ld e,a
        ld d,0
        ld hl,GTAB
        add hl,de
        ld a,(hl)
        ld hl,V_GROUND
        cp (hl)
        ret z
        ld (hl),a
        ld e,a
        nextreg 0x43,0x20               ; sprite palette 0
        ld b,4
        ld a,2                          ; index 2 (body) of the four groups
.g:     nextreg 0x40,a
        ld c,a
        ld a,e
        nextreg 0x41,a
        ld a,c
        add a,16
        djnz .g
        ret

; Spectrum paper -> the Next's ULA colours (normal, then BRIGHT)
GTAB:   db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF

; spark ink colours, 8-bit, per ink value
SPKP:   db 0x00,0,0x03,0,0xE0,0,0xE3,0,0x1C,0,0x1F,0,0xFC,0,0xFF,0
page_end:
        ASSERT page_end <= PM - 8

; ---- setup routine (stub bank, 0xD000): palette, sprites hidden, layer on
        ORG 0xD000
setup:  nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,64
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
        nextreg 0x12,L2BANK         ; Layer 2: the Feedle caves only, transparent elsewhere (pages prefilled 0xE3)
        nextreg 0x14,0xE3
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x70,0
        nextreg 0x43,0x10           ; Layer 2 palette 0: 0 black, 0xE3 transparent
        nextreg 0x40,0
        nextreg 0x41,0
        nextreg 0x40,0xE3
        nextreg 0x41,0xE3
        nextreg 0x43,0x20           ; back to sprite palette 0: the spark and body hooks write it without selecting it
        ld bc,0x123B
        ld a,2                      ; Layer 2 shown, no write paging; NR 0x69 is left alone (its bit 6 = 7FFD bit 3)
        out (c),a
        nextreg 0x15,0x05           ; sprites on, LSU: Layer 2 over the sprites, higher sprite number on top
        ret
pal:                                ; 64 palette bytes appended by Python

        SAVEBIN "yie_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "yie_page.bin",CODE0,page_end-CODE0
        SAVEBIN "yie_setup.bin",0xD000,pal-0xD000
