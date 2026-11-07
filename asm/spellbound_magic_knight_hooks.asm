; Spellbound (Mastertronic Added Dimension 1986, 128K edition) - every figure in play becomes 4-bit hardware
; sprites; scenery, text, windows and icons stay on the ULA. Facts: games/spellbound_magic_knight.md.
;
; Drawing in the original (same author's engine as Knight Tyme, addresses and details read from this game):
;   Knight   0xA5FC / 0xA5C9: compose a 3 x 32 box: clean bytes from the room copy in bank 7, masked graphics
;            from 0xF9F4 / 0xFCF4 (4 shifts x 2 facings), blit the old clean box, 0xA63B CALL 0xA59F blit the new.
;   Others   room build: objects 0x94E4 CALL 0xAD14 (2 x 2 cells), characters 0x72E9 CALL 0xAD19 (2 x 4 cells),
;            both masked on the screen BEFORE the screen is copied to bank 7 as the room's clean copy.
;   Smoke    0x732D CALL 0xAD0F (2 x 3 cells), five frames where a character or the Knight appears.
;   Balls    0xAB3B, an 8 x 8 XOR plot from three sites, in rooms 12, 19, 37, 50, 51.
;   Paint    option UPDATE (23705, on from the start here): the Knight, objects, characters paint their cells' attributes.
; Method - the game's own code runs, the same instructions in the same order:
;   0xA63B  CALL e_kn: the blit runs from the clean box 0x5D65 (data patch 0xA5A0), DE and A put back, sprites set.
;   0x72E9 / 0x94E4 / 0x732D  cells saved, the game's plotter runs, cells restored, sprites built.
;   0x733C  smoke over: its sprites go.
;   0x8E42 / 0x8E6B / 0x8F55 CALL e_ba: the ball's sprite follows each call; the XOR's two stores are NOPs.
;   Attribute stores of the paint: NOPs, so scenery keeps its colours in either option.
;   0x6FA9  JP e_rm : room build starts: all figure sprites go.
;   0x90F1  CALL e_wn: a window opens: sprite tiles it touches are hidden; the next Knight commit shows them.
;   0x934E  JP e_wp : full screen wipe: all figure sprites go.
; Hook code: small stubs in alt ROM image 1 (0x386E-, free in the 48K ROM), the rest in page H at slot 4 with
; interrupts off (the ISR touches every slot). The plotter and blit themselves run with interrupts on.

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"    ; macros only: HLIB_SPEED_IN
        INCLUDE "lib/hlib_iff.asm"      ; macros only: HLIB_IFF_DI / HLIB_IFF_EI

HPG     EQU 26                  ; hook page, MMU slot 4 while a hook runs
GP4     EQU 4                   ; the game's page at slot 4
GP5     EQU 5                   ; the game's page at slot 5
STORE   EQU 28                  ; colour store: pages 28-43: 8 bytes per address 0xC000-0xFFFF
CBLACK  EQU 8                   ; sprite palette index of black
CWHITE  EQU 15
BINK    EQU 13                  ; the balls: bright cyan, the colour they show on the room's black
KPAT    EQU 6                   ; Knight: tiles per image, images at pattern 0, 6, .. 42
RFIRST  EQU 48                  ; first pattern of the room figures
KSLOT   EQU 122                 ; Knight's sprites: 122-127 (on top)
BSLOT   EQU 118                 ; balls: 118-121
BPAT    EQU 124                 ; ball frames: patterns 124-127
PLIM    EQU 124                 ; room figures use patterns below this
MAXROOM EQU 118                 ; room figure sprites 0-117

; ---- page H at 0x8000 ----
V_SP    EQU 0x8000
V_SPD   EQU 0x80FF              ; the caller's CPU speed (lib/hlib_speed.asm latch)
V_K     EQU 0x8002              ; kind: 0 character, 1 object
V_A     EQU 0x8003              ; plot: graphic, row, column
V_B     EQU 0x8004
V_C     EQU 0x8005
V_NS    EQU 0x8006              ; room sprites in use
V_NP    EQU 0x8007              ; next free pattern
V_HID   EQU 0x8008              ; a window hid tiles
V_HASC  EQU 0x8009              ; 1 = the colour store has entries (Python / recolour)
V_OL    EQU 0x800A              ; 1 = outline
V_DROP  EQU 0x800B              ; tiles dropped (diagnostic)
V_G     EQU 0x800C              ; (2) graphics
V_M     EQU 0x800E              ; (2) mask
V_WB    EQU 0x8010              ; width in bytes
V_HL    EQU 0x8011              ; lines
V_INK   EQU 0x8012              ; ink index
V_OC    EQU 0x8013              ; outline index
V_OK    EQU 0x8014              ; 1 = the outline rings ink only (white figures: the game's mask is their black halo)
V_TILE  EQU 0x8015              ; tile mask of the last pack
V_X     EQU 0x8016              ; (2) sprite X of the canvas origin (+32)
V_Y     EQU 0x8018              ; (2) sprite Y
V_PB    EQU 0x801A              ; pattern of this tile
V_NC    EQU 0x801B              ; canvas tile columns
V_NR    EQU 0x801C              ; canvas tile rows
V_NB    EQU 0x801D              ; (4) colour nibbles of this byte
V_CL    EQU 0x8021              ; clear mask of this byte
V_ANY   EQU 0x8022
V_L     EQU 0x8023
V_WN    EQU 0x8024              ; window in sprite coordinates: left, right (2 each), top, bottom (2 each)
V_N     EQU 0x802C
V_CT    EQU 0x802E              ; tile counter
V_SMA   EQU 0x802F              ; 1 = smoke on show
V_SMS   EQU 0x8030              ; V_NS before the smoke
V_SMP   EQU 0x8031              ; V_NP before the smoke
V_BC    EQU 0x8032              ; (4) ball frames built
V_PW    EQU 0x8036              ; rectangle width in pixels: 8W + 2
V_CH    EQU 0x8037              ; fill: a pass changed a line
V_T     EQU 0x8038              ; (3) fill: sum bytes
V_MS    EQU 0x803B              ; 1 = this Knight commit converted an image (kwait)
SPRTAB  EQU 0x8100              ; 128 x 8: X (2), Y (2), a3, a4, shown (1, 2 hidden; 0x10 left edge is ring, 0x20 top edge), size
                                ; size: (pixels wide - 1) << 4 | (lines - 1): the figure's part of this tile
CACHE   EQU 0x8040              ; Knight: 8 x 8: valid, colour, sum (2), tile mask
REVT    EQU 0x8500              ; 256: each byte bit-reversed (written by Python into the page; fill)
SAVE    EQU 0x8600              ; cells under a figure
TILEB   EQU 0x8680              ; 128 bytes: tile being packed
CANVAS  EQU 0x8700              ; 49 lines x 64: figure at (2,2), rings at 1, zeros at 0; pack reads 3 x 16 lines from line 1
HSTK    EQU 0x9440
; bit rows, canvas columns 40-63 of each line of the rectangle (build)
MZ      EQU 40                  ; (4) clear pixels
MZR     EQU 44                  ; (4) MZ bit-reversed
MR      EQU 48                  ; (4) reached from outside
MN      EQU 52                  ; (4) earns a ring
MK      EQU 56                  ; (4) neither clear nor black (a white figure's ring rule; written when V_OK)
MX      EQU 60                  ; (4) scratch

LINES   EQU 0x6680              ; the game's line address table
KX      EQU 25720               ; Knight: column of the new box
KY      EQU 25355               ; line
KSHIFT  EQU 25357
KFACE   EQU 25723
KCOL    EQU 25360
OBJCOL  EQU 23695               ; ATTR T, set by the object loop
CHCOL   EQU 0x7303              ; self-modified LD A,n: the character's colour
GTAB    EQU 0xC544              ; graphic table: graphics, mask

        MACRO ENTER                     ; interrupts as the caller had them: the game's handler never touches slot 4
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPD             ; the caller's speed latched (hook stack), then 28 MHz
        push af
        push bc
        push de
        push hl
        push ix
        ENDM

        MACRO PIX                       ; one pixel: D ink bits (ink C), E clear bits, else black B
        sla d
        jr nc,1F
        ld (hl),c
        sla e
        jr 2F
1:      sla e
        jr c,2F
        ld (hl),b
2:      inc l
        ENDM

        MACRO PACK2                     ; two canvas pixels -> a pattern byte; C collects them
        ld a,(hl)
        inc l
        swapnib
        or (hl)
        inc l
        ld (de),a
        inc e
        or c
        ld c,a
        ENDM

        MACRO LEAVE
        pop ix
        pop hl
        pop de
        pop bc
        ld a,(V_SPD)                    ; the caller's speed back (never a fixed 3.5 MHz), then A
        nextreg 0x07,a
        pop af
        ld sp,(V_SP)
        nextreg 0x54,GP4
        ENDM

; ---- alt ROM stubs ----
        ORG 0x386E

e_kn:   ex (sp),hl                  ; the blit returns to e_kn2
        ld hl,e_kn2
        ex (sp),hl
        jp 0xA59F
e_kn2:  ENTER
        call c_kn
        LEAVE
        ld de,0x5D65                ; as the original's blit from 0x5D05 ends
        ld a,(0x5D64)
        jp 0xA63E

e_ch:   ENTER
        xor a
        ld (V_K),a
        call c_save
        LEAVE
        ex (sp),hl
        ld hl,e_ch2
        ex (sp),hl
        jp 0xAD19
e_ch2:  ENTER
        ld hl,0x72EC
        call c_plot
        LEAVE
        jp 0x72EC

e_ob:   ENTER
        ld a,1
        ld (V_K),a
        call c_save
        ld a,(V_N)
        or a
        jr z,.win                   ; the window's object picture stays on the ULA
        LEAVE
        ex (sp),hl
        ld hl,e_ob2
        ex (sp),hl
        jp 0xAD14
.win:   LEAVE
        jp 0xAD14
e_ob2:  ENTER
        ld hl,0x94E7
        call c_plot
        LEAVE
        jp 0x94E7

e_sm:   ENTER
        ld a,2
        ld (V_K),a
        call c_save
        LEAVE
        ex (sp),hl
        ld hl,e_sm2
        ex (sp),hl
        jp 0xAD0F
e_sm2:  ENTER
        call c_sm
        ld hl,0x7330
        call c_plot
        LEAVE
        jp 0x7330

e_sx:   ENTER
        call c_sx
        LEAVE
        jp 0x77F0

e_ba:   ENTER
        call c_ba
        LEAVE
        jp 0xAB3B

e_rm:   ENTER
        call c_all
        LEAVE
        ld a,(25282)
        jp 0x6FAC

e_wn:   ENTER
        call c_win
        LEAVE
        jp 0x913C

e_wp:   ENTER
        call c_all
        LEAVE
        ld hl,0
        jp 0x9351

; kwait (end of c_kn): after a conversion, under 90 lines before the frame interrupt (video line 248 of 311), wait for
; it. That frame is lost anyway (the game's work after the blit takes 7.3 ms or more); without the wait the game's own
; DI copy (0xA52F-0xA55B, 1.9-2.9 ms after the blit) can hold the interrupt off and lose it. Interrupts off: no wait.
kwait:  ld a,(V_MS)
        or a
        ret z
        xor a
        ld (V_MS),a
        ld bc,0x243B
.r:     ld a,0x1E                   ; the video line, read until its MSB holds still
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
        ld de,248-90
        or a
        sbc hl,de
        ret c                       ; 90 lines or more left
        ld de,90
        sbc hl,de
        ret nc                      ; past line 248: this frame's interrupt has come
        ld a,i
        jp pe,.on
        ld a,i                      ; off, or an interrupt taken at the end of the first read
        ret po
.on:    ld a,(V_SPD)                ; the handler at the caller's speed
        nextreg 0x07,a
        halt
        nextreg 0x07,3
        ret

rom_end:

; ---- page H: code ----
        ORG 0x9440

; c_save: called with the entry registers on the hook stack (ret, ix, hl, de, bc, af): saves the cells under the
; plot. V_N = 0 when the entry IX is the window picture's 25568: that plot stays on the ULA.
c_save: ld hl,2
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = entry IX
        inc hl
        inc hl
        inc hl
        inc hl
        inc hl
        ld c,(hl)                   ; C
        inc hl
        ld b,(hl)                   ; B
        inc hl
        inc hl
        ld a,(hl)                   ; A
        ld (V_A),a
        ld a,b
        ld (V_B),a
        ld a,c
        ld (V_C),a
        ld hl,25594                 ; 0x94AD's own entry: the object picture in a window
        or a
        sbc hl,de
        ld a,h
        or l
        ld (V_N),a                  ; 0 = stay on the ULA
        jr z,.done
        call klines
        ld e,a
        ld a,(V_B)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        ld bc,LINES
        add hl,bc
        ld ix,SAVE
        ld b,e
.l:     push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ex de,hl
        ld a,(V_C)
        add hl,a
        ld a,(hl)
        ld (ix+0),a
        inc hl
        ld a,(hl)
        ld (ix+1),a
        inc ix
        inc ix
        ex de,hl
        pop bc
        djnz .l
.done:  ret

; c_plot: HL = the game's return address (put back in the dead stack). Restores the cells, builds the sprites.
c_plot: ex de,hl
        ld hl,(V_SP)
        dec hl
        ld (hl),d
        dec hl
        ld (hl),e
        call klines
        ld e,a
        ld (V_HL),a
        ld a,(V_B)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        ld bc,LINES
        add hl,bc
        ld ix,SAVE
        ld b,e
.l:     push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ex de,hl
        ld a,(V_C)
        add hl,a
        ld a,(ix+0)
        ld (hl),a
        inc hl
        ld a,(ix+1)
        ld (hl),a
        inc ix
        inc ix
        ex de,hl
        pop bc
        djnz .l
        ld a,2
        ld (V_WB),a
        ld a,(V_A)                  ; graphic table
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,GTAB
        add hl,bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_G),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_M),de
        ld a,(V_K)
        or a
        ld a,(CHCOL)
        jr z,.col
        ld a,(V_K)
        cp 2
        ld a,0x47                   ; smoke: bright white, a default: the game gives it the cell's colour
        jr z,.col
        ld a,(OBJCOL)
.col:   call setcol
        call build
        ld a,(V_C)                  ; sprite position of the canvas origin (figure at +1,+1 of tile space)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,31
        add hl,bc
        ld (V_X),hl
        ld a,(V_B)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,bc
        ld (V_Y),hl
        ld a,2
        ld (V_NC),a
        ld a,(V_K)
        or a
        ld a,3
        jr z,.r
        ld a,2                      ; objects 18 lines, smoke 26: two rows of tiles
.r:     ld (V_NR),a
        jp pack_room

; klines: V_K -> lines of this kind of figure in A
klines: ld a,(V_K)
        or a
        ld a,32
        ret z
        ld a,(V_K)
        cp 2
        ld a,24
        ret z
        ld a,16
        ret

; c_sm: a new smoke frame: the last frame's tiles go, its pool entries are reused
c_sm:   ld a,(V_SMA)
        or a
        jr nz,c_smo
        ld a,1
        ld (V_SMA),a
        ld a,(V_NS)
        ld (V_SMS),a
        ld a,(V_NP)
        ld (V_SMP),a
        ret
c_smo:  ld a,(V_SMS)
        ld c,a
.l:     ld a,(V_NS)
        cp c
        jr z,.d
        dec a
        ld (V_NS),a
        push bc
        call hide
        pop bc
        jr .l
.d:     ld a,(V_SMP)
        ld (V_NP),a
        ret

; c_sx: the smoke is over
c_sx:   ld a,(V_SMA)
        or a
        ret z
        call c_smo
        xor a
        ld (V_SMA),a
        ret

; c_ba: a ball, entry A = its character, IX = its record, position (23677). Its sprite is simply where the last call said.
; Erasing calls name the same place and frame as the last call, so they change nothing.
c_ba:   ld hl,11                    ; ret, ix, hl, de, bc, f, a
        add hl,sp
        ld a,(hl)
        ld (V_A),a
        ld hl,2
        add hl,sp
        ld a,(hl)                   ; IX low: 0xE6 + 8 * ball
        sub 0xE6
        rrca
        rrca
        rrca
        and 3
        add a,BSLOT
        ld (V_CT),a
        ld a,(V_A)
        cp 116
        jr nc,.show
        ld a,(V_CT)                 ; the blank before a ball's first move
        jp hide
.show:  sub 116
        and 3
        ld (V_L),a
        ld hl,V_BC
        add hl,a
        ld a,(hl)
        or a
        jr nz,.have
        ld (hl),1
        call c_bb
.have:  ld a,(23677)
        ld l,a
        ld h,0
        ld de,31
        add hl,de
        ld (V_X),hl
        ld a,(23678)
        ld l,a
        ld h,0
        add hl,de
        ld (V_Y),hl
        ld a,1
        ld (V_NC),a
        ld (V_NR),a
        ld (V_WB),a
        ld a,8
        ld (V_HL),a
        ld a,(V_L)
        add a,BPAT
        ld b,a
        ld a,(V_CT)
        ld d,0
        ld e,0
        jp put

; c_bb: frame V_L (character V_A) -> a pattern: the ball at (1,1) in bright cyan, a white ring, no fill (it is solid:
; every clear pixel of its box counts as outside)
c_bb:   ld a,(V_A)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xBA00
        add hl,de
        ld (V_G),hl
        ld hl,fftab                 ; mask all ones: clear bits are see-through
        ld (V_M),hl
        ld a,BINK
        ld (V_INK),a
        xor a
        ld (V_OK),a
        ld a,CWHITE
        ld (V_OC),a
        ld a,1
        ld (V_WB),a
        ld a,8
        ld (V_HL),a
        call bldm
        ld ix,CANVAS+64             ; lines 1 .. 10: reached = clear
        ld b,10
.r:     ld a,(ix+MZ)
        ld (ix+MR),a
        ld a,(ix+MZ+1)
        ld (ix+MR+1),a
        ld de,64
        add ix,de
        djnz .r
        call rings
        ld de,0
        call pack
        ld a,(V_L)
        add a,BPAT
        jp upload

; setcol: A = attribute -> ink index, outline index, ring rule
setcol: ld b,a
        and 7
        ld c,a
        ld a,b
        and 0x40
        jr z,.nb
        ld a,c
        or a
        jr z,.k
        add a,8
        jr .s
.k:     ld a,CBLACK
        jr .s
.nb:    ld a,c
        or a
        jr nz,.s
        ld a,CBLACK
.s:     ld (V_INK),a
        ld b,a
        and 7
        cp 7
        ld a,CWHITE
        ld c,0
        jr nz,.o
        ld a,CBLACK
        ld c,1
.o:     ld (V_OC),a
        ld a,c
        ld (V_OK),a
        ret

; ---- figure -> canvas. Besides the pixels, each canvas line L of the rectangle (lines 1 .. H+2, pixels 1 .. PW = 8W+2)
; holds bit rows in its columns 40-63 (pack reads 1-32, figures reach 27): bit i = pixel PW - i of that line.
; build: V_G, V_M, V_WB, V_HL, V_INK, V_OC -> the canvas
build:  call bldm
        call fillh
        ld a,(V_OL)
        or a
        ret z
        jp rings

; bldm: canvas lines 0-35, columns 0-33 cleared (no figure reaches further; lines 36-48 are never written), the figure's
; pixels, and the bit rows Z (clear), ZR (Z reversed), R = 0, K (neither clear nor black; white figures)
bldm:   ld hl,CANVAS
        ld c,36
.cl:    xor a
        ld b,17
.c2:    ld (hl),a
        inc l
        ld (hl),a
        inc l
        djnz .c2
        ld a,l
        add a,30
        ld l,a
        jr nc,.c3
        inc h
.c3:    dec c
        jr nz,.cl
        ld a,(V_WB)
        add a,a
        add a,a
        add a,a
        add a,2
        ld (V_PW),a
        ld ix,CANVAS+64             ; line 1: the top margin
        call mline
        ld ix,CANVAS+128
        ld a,(V_INK)
        ld c,a                      ; C = ink
        ld a,(V_HL)
        ld b,a
.line:  push bc
        push ix
        pop hl
        inc l
        inc l                       ; pixel 2
        ld a,(V_WB)
        ld b,a
.byte:  ld a,(V_HASC)
        or a
        jr nz,.cb
        push hl
        ld hl,(V_G)
        ld d,(hl)
        inc hl
        ld (V_G),hl
        ld hl,(V_M)
        ld e,(hl)
        inc hl
        ld (V_M),hl
        pop hl
        jr .fast
.cb:    push bc
        push hl
        call colents
        ld hl,(V_G)
        ld d,(hl)                   ; D graphics
        inc hl
        ld (V_G),hl
        ld hl,(V_M)
        ld e,(hl)                   ; E mask
        inc hl
        ld (V_M),hl
        pop hl
        pop bc
        push hl
        ld hl,V_NB
        ld a,(V_CL)
        or (hl)
        inc hl
        or (hl)
        inc hl
        or (hl)
        inc hl
        or (hl)
        pop hl
        jp nz,.slow                 ; painted: pixel by pixel
.fast:  ld a,d
        cpl
        and e
        ld e,a                      ; E = clear (paper with mask 1), D = ink
        push de                     ; this byte's bits: D earns a white figure's ring, E clear
        inc a
        jr nz,.draw
        ld a,l                      ; all clear: the canvas already is
        add a,8
        ld l,a
        jr .bn
.draw:  push bc
        ld a,CBLACK                 ; the game's knocked-out paper (mask 0): black
        ld b,a
        PIX
        PIX
        PIX
        PIX
        PIX
        PIX
        PIX
        PIX
        pop bc
.bn:    dec b
        jp nz,.byte
        call masks
        ld a,(V_WB)
        add a,a
        ld l,a
        ld h,0
        add hl,sp
        ld sp,hl                    ; the byte pairs go
        ld de,64
        add ix,de
        pop bc
        dec b
        jp nz,.line
        call mline                  ; line H+2: the bottom margin
        ret

; .slow: a painted byte, D graphics, E mask, V_NB / V_CL its colours: eight pixels, then its bits from them
.slow:  push bc
        ld b,0
.bit:   ld a,b                      ; colour nibble of pixel B
        rra
        and 3
        push hl
        ld hl,V_NB
        add hl,a
        ld a,(hl)
        pop hl
        bit 0,b
        jr nz,.lo
        rra
        rra
        rra
        rra
.lo:    and 15
        ld c,a                      ; C = painted colour or 0
        ld a,(V_CL)
        rlca
        ld (V_CL),a
        jr c,.clear                 ; painted clear (a set bit: bit 7 first)
        sla d
        jr nc,.nink
        sla e                       ; ink
        ld a,c
        or a
        jr nz,.st
        ld a,(V_INK)
        jr .st
.nink:  sla e
        jr c,.tr                    ; paper with mask 1: see-through unless painted
        ld a,c                      ; mask 0: the game's knocked-out paper: black unless painted
        or a
        jr nz,.st
        ld a,CBLACK
        jr .st
.clear: sla d
        sla e
        xor a
        jr .st
.tr:    ld a,c
.st:    ld (hl),a
        inc hl
        inc b
        ld a,b
        cp 8
        jr nz,.bit
        ld a,l
        sub 8
        ld l,a
        ld de,0
        ld b,8
.zk:    ld a,(hl)
        inc l
        sla e
        sla d
        or a
        jr nz,.nz
        inc e                       ; clear
        jr .zn
.nz:    cp CBLACK
        jr z,.zn
        inc d                       ; neither clear nor black
.zn:    djnz .zk
        pop bc
        push de
        jp .bn

; mline: IX = a margin line: Z all the rectangle, K none, R none
mline:  ld a,(V_WB)
        ld b,a
        ld de,0x00FF
.p:     push de
        djnz .p
        call masks
        ld a,(V_WB)
        add a,a
        ld l,a
        ld h,0
        add hl,sp
        ld sp,hl
        ret

; masks: IX = line; under the return address W byte pairs (D, E), the last byte on top ->
; Z = (1 << 8W | E bytes) << 1 | 1 (the margins are clear), ZR = Z reversed, R = 0, K = D bytes << 1 (V_OK only)
masks:  ld hl,2
        add hl,sp                   ; the last byte's pair: E, D
        push ix
        pop de
        ld a,e
        add a,MZ
        ld e,a                      ; DE = Z
        ld a,(V_WB)
        ld b,a
        scf                         ; the right margin
.z:     ld a,(hl)
        rla
        ld (de),a
        inc hl
        inc hl
        inc e
        djnz .z
        ld a,1                      ; the left margin
        rla
.z2:    ld (de),a                   ; then zeros up to ZR
        xor a
        inc e
        bit 2,e
        jr z,.z2
        ld b,d
        ld a,e
        add a,3
        ld c,a                      ; BC = ZR + 3
        ld a,e
        sub 4
        ld e,a                      ; DE = Z
        ld h,REVT>>8
        REPT 4
        ld a,(de)
        ld l,a
        ld a,(hl)
        ld (bc),a
        inc e
        dec c
        ENDR
        ld a,e
        add a,4
        ld e,a                      ; R = 0
        xor a
        REPT 4
        ld (de),a
        inc e
        ENDR
        ld a,(V_OK)
        or a
        ret z
        ld a,e
        add a,4
        ld e,a                      ; K
        ld hl,3
        add hl,sp
        ld a,(V_WB)
        ld b,a
        or a
.k:     ld a,(hl)
        rla
        ld (de),a
        inc hl
        inc hl
        inc e
        djnz .k
        ld a,0
        rla
.k2:    ld (de),a
        xor a
        inc e
        bit 2,e
        jr z,.k2
        ret

; fillh: R = the clear pixels the outside reaches (4-connected to the top margin line), by line passes down and up
; until a pass finds nothing new; the clear pixels it cannot reach become black: no outline inside a figure.
fillh:  ld hl,CANVAS+MR             ; line 0 (outside the rectangle): R all ones, the seed of line 1
        ld a,0xFF
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        call .dn
.lp:    call .up
        ld a,(V_CH)
        or a
        jr z,.done
        call .dn
        ld a,(V_CH)
        or a
        jr nz,.lp
.done:  ld ix,CANVAS+128            ; lines 2 .. H+1: Z and not R -> black
        ld a,(V_HL)
        ld b,a
.e:     push bc
        ld a,(ix+MR)
        cpl
        and (ix+MZ)
        ld (ix+MX),a
        ld a,(ix+MR+1)
        cpl
        and (ix+MZ+1)
        ld (ix+MX+1),a
        ld a,(ix+MR+2)
        cpl
        and (ix+MZ+2)
        ld (ix+MX+2),a
        ld a,(ix+MR+3)
        cpl
        and (ix+MZ+3)
        ld (ix+MX+3),a
        ld c,CBLACK
        call wrow
        ld de,64
        add ix,de
        pop bc
        djnz .e
        ret
.dn:    xor a                       ; lines 1 .. H+2, each from the line above
        ld (V_CH),a
        ld ix,CANVAS+64
        ld a,(V_HL)
        add a,2
        ld b,a
.d1:    push bc
        push ix
        pop hl
        ld de,MR-64
        add hl,de
        call step
        ld de,64
        add ix,de
        pop bc
        djnz .d1
        ret
.up:    xor a                       ; lines H+1 .. 1, each from the line below (after .dn: IX = line H+3)
        ld (V_CH),a
        ld de,-128
        add ix,de
        ld a,(V_HL)
        inc a
        ld b,a
.u1:    push bc
        push ix
        pop hl
        ld de,MR+64
        add hl,de
        call step
        ld de,-64
        add ix,de
        pop bc
        djnz .u1
        ret

; step: IX = line, HL = R of the neighbour line. New pixels: the neighbour's R on this line's Z; then R becomes every
; run of Z they touch. Runs to the left: S | (Z + S) ^ Z & Z (the carry runs up a run); to the right the same on ZR.
step:   ld a,(ix+MR)
        cpl
        and (hl)
        and (ix+MZ)
        ld e,a
        inc l
        ld a,(ix+MR+1)
        cpl
        and (hl)
        and (ix+MZ+1)
        ld d,a
        inc l
        ld a,(ix+MR+2)
        cpl
        and (hl)
        and (ix+MZ+2)
        ld c,a
        inc l
        ld a,(ix+MR+3)
        cpl
        and (hl)
        and (ix+MZ+3)
        ld b,a
        or c
        or d
        or e
        ret z                       ; nothing new here
        ld a,1
        ld (V_CH),a
        ld a,(ix+MR)
        or e
        ld e,a
        ld a,(ix+MR+1)
        or d
        ld d,a
        ld a,(ix+MR+2)
        or c
        ld c,a
        ld a,(ix+MR+3)
        or b
        ld b,a
        push ix
        pop hl
        ld a,l
        add a,MZ
        ld l,a
        call upf                    ; leftwards
        call rev
        push ix
        pop hl
        ld a,l
        add a,MZR
        ld l,a
        call upf                    ; rightwards, in the reversed bits
        call rev
        ld (ix+MR),e
        ld (ix+MR+1),d
        ld (ix+MR+2),c
        ld (ix+MR+3),b
        ret

; upf: HL = Z (4 bytes of one line), E D C B = S within Z -> S | ~(Z + S) & Z: from each seed, its run leftwards
upf:    ld a,(hl)
        add a,e
        ld (V_T),a
        inc l
        ld a,(hl)
        adc a,d
        ld (V_T+1),a
        inc l
        ld a,(hl)
        adc a,c
        ld (V_T+2),a
        inc l
        ld a,(hl)
        adc a,b
        cpl
        and (hl)
        or b
        ld b,a
        dec l
        ld a,(V_T+2)
        cpl
        and (hl)
        or c
        ld c,a
        dec l
        ld a,(V_T+1)
        cpl
        and (hl)
        or d
        ld d,a
        dec l
        ld a,(V_T)
        cpl
        and (hl)
        or e
        ld e,a
        ret

; rev: E D C B (32 bits) -> bit-reversed
rev:    ld h,REVT>>8
        ld l,e
        ld a,(hl)
        ld l,b
        ld e,(hl)
        ld b,a
        ld l,d
        ld a,(hl)
        ld l,c
        ld d,(hl)
        ld c,a
        ret

; rings: a one-pixel ring on the reached pixels beside any that earn one (V_OK: ink only, the game's mask is a white
; figure's black halo; else every pixel not reached), in V_OC
rings:  ld ix,CANVAS+64
        ld a,(V_HL)
        add a,2
        ld b,a
.n:     ld a,(V_OK)
        or a
        jr nz,.k
        ld hl,CANVAS+64+MZ          ; line 1's Z: the rectangle
        ld a,(ix+MR)
        cpl
        and (hl)
        ld (ix+MN),a
        inc l
        ld a,(ix+MR+1)
        cpl
        and (hl)
        ld (ix+MN+1),a
        inc l
        ld a,(ix+MR+2)
        cpl
        and (hl)
        ld (ix+MN+2),a
        inc l
        ld a,(ix+MR+3)
        cpl
        and (hl)
        ld (ix+MN+3),a
        jr .nn
.k:     ld a,(ix+MK)
        ld (ix+MN),a
        ld a,(ix+MK+1)
        ld (ix+MN+1),a
        ld a,(ix+MK+2)
        ld (ix+MN+2),a
        ld a,(ix+MK+3)
        ld (ix+MN+3),a
.nn:    ld de,64
        add ix,de
        djnz .n
        xor a                       ; line H+3 earns none (line 0's N is never written: always none)
        ld (ix+MN),a
        ld (ix+MN+1),a
        ld (ix+MN+2),a
        ld (ix+MN+3),a
        ld ix,CANVAS+64
        ld a,(V_HL)
        add a,2
        ld b,a
.r:     push bc
        ld e,(ix+MN)
        ld d,(ix+MN+1)
        ld c,(ix+MN+2)
        ld b,(ix+MN+3)
        sla e
        rl d
        rl c
        rl b
        ld a,e
        or (ix+MN-64)
        or (ix+MN+64)
        ld (ix+MX),a
        ld a,d
        or (ix+MN-63)
        or (ix+MN+65)
        ld (ix+MX+1),a
        ld a,c
        or (ix+MN-62)
        or (ix+MN+66)
        ld (ix+MX+2),a
        ld a,b
        or (ix+MN-61)
        or (ix+MN+67)
        ld (ix+MX+3),a
        ld e,(ix+MN)
        ld d,(ix+MN+1)
        ld c,(ix+MN+2)
        ld b,(ix+MN+3)
        srl b
        rr c
        rr d
        rr e
        ld a,e
        or (ix+MX)
        and (ix+MR)
        ld (ix+MX),a
        ld a,d
        or (ix+MX+1)
        and (ix+MR+1)
        ld (ix+MX+1),a
        ld a,c
        or (ix+MX+2)
        and (ix+MR+2)
        ld (ix+MX+2),a
        ld a,b
        or (ix+MX+3)
        and (ix+MR+3)
        ld (ix+MX+3),a
        ld a,(V_OC)
        ld c,a
        call wrow
        ld de,64
        add ix,de
        pop bc
        dec b
        jp nz,.r
        ret

; wrow: IX = line, bits at MX -> colour C at those pixels
wrow:   ld a,(ix+MX)
        or (ix+MX+1)
        or (ix+MX+2)
        or (ix+MX+3)
        ret z
        push ix
        pop hl
        ld a,(V_PW)
        add a,l
        ld l,a                      ; pixel of bit 0
        ld a,(ix+MX)
        call wbyte
        ld a,(ix+MX+1)
        call wbyte
        ld a,(ix+MX+2)
        call wbyte
        ld a,(ix+MX+3)
; wbyte: A = 8 bits, bit 0 at HL, leftwards -> colour C; HL -> bit 0 of the next byte
wbyte:  ld d,l
        or a
        jr z,.e
.b:     srl a
        jr nc,.n
        ld (hl),c
        jr z,.e                     ; that was the last
.n:     dec l
        jr .b
.e:     ld a,d
        sub 8
        ld l,a
        ret

fftab:  db 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF

; colents: the colour store entry of the graphics byte at V_G -> V_NB, V_CL (zeros when absent or stale)
colents:
        xor a
        ld (V_CL),a
        ld hl,V_NB
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ld a,(V_HASC)
        or a
        ret z
        ld hl,(V_G)
        ld a,h
        cp 0xC0
        ret c
        sub 0xC0
        ld b,a                      ; offset 14 bits: page = offset >> 10, in page (offset & 0x3FF) * 8
        rrca
        rrca
        and 0x3F
        add a,STORE
        ld c,a
        HLIB_IFF_DI                     ; slot 5 holds the game's interrupt handler: interrupts off while it is
        push af                         ; remapped, and only then (P/V = the caller's IFF)
        ld a,c
        nextreg 0x55,a
        ld a,b
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0xA0
        ld h,a
        ld a,(hl)
        cp 1
        jr nz,.out
        inc hl
        push hl
        ld hl,(V_G)
        ld b,(hl)                   ; slot 6/7: the game's byte
        pop hl
        ld a,(hl)
        cp b
        jr nz,.out                  ; other graphics at this address: defaults
        inc hl
        ld de,V_NB
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)
        ld (V_CL),a
.out:   nextreg 0x55,GP5
        pop af
        HLIB_IFF_EI
        ret

; pack: canvas tile (D = column, E = row) -> TILEB, NZ if any pixel
pack:   ld a,e
        swapnib                     ; row * 16 lines
        ld l,a
        ld a,(V_HL)                 ; lines of this row inside the rectangle (to H+2); below it the canvas is clear
        add a,2
        sub l
        cp 16
        jr c,.k
        ld a,16
.k:     ld (V_T),a
        ld h,0
        ld b,6
.m:     add hl,hl
        djnz .m                     ; * 64
        ld a,d
        swapnib                     ; column * 16 pixels
        add a,1                     ; origin: canvas (1,1)
        add hl,a
        ld bc,CANVAS+64
        add hl,bc
        ld de,TILEB
        ld a,(V_T)
        ld b,a
        ld c,0                      ; B lines, C any pixel
.y:     PACK2
        PACK2
        PACK2
        PACK2
        PACK2
        PACK2
        PACK2
        PACK2
        ld a,l                      ; the next line, the same 16 pixels
        add a,48
        ld l,a
        jr nc,.n
        inc h
.n:     djnz .y
        ld a,(V_T)                  ; the clear lines
        sub 16
        jr z,.d
        neg
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.zl:    ld (de),a
        inc e
        djnz .zl
.d:     ld a,c
        or a
        ret

; upload: TILEB -> pattern A
upload: ld c,a
        srl a
        bit 0,c
        jr z,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ld hl,TILEB
        ld bc,0x005B                ; B = 0: 256 is too many: two halves of 128
        ld b,128
        otir
        ret

; put: A = sprite slot, B = pattern, D = column, E = row of the tile, from V_X, V_Y: writes SPRTAB and the sprite
put:    nextreg 0x34,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,SPRTAB>>8
        ld h,a
        push hl
        pop ix
        ld a,d
        swapnib
        ld hl,(V_X)
        add hl,a
        ld (ix+0),l
        ld (ix+1),h
        ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,e
        swapnib
        ld hl,(V_Y)
        add hl,a
        ld (ix+2),l
        ld (ix+3),h
        ld a,l
        nextreg 0x36,a
        ld a,b
        srl a
        or 0xC0                     ; visible, extended
        ld (ix+4),a
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca                        ; pattern bit 0 -> bit 6
        or 0x80                     ; 4-bit
        ld c,a
        ld a,h
        and 1
        or c
        ld (ix+5),a
        nextreg 0x39,a
        ; what of the tile the figure really fills: a window beside it should not hide it
        ld c,1
        ld a,d
        or a
        jr nz,.nl
        set 4,c
.nl:    ld a,e
        or a
        jr nz,.nt
        set 5,c
.nt:    ld (ix+6),c
        ld a,(V_NC)                 ; width
        dec a
        cp d
        ld c,0xF0
        jr nz,.w
        ld a,(V_WB)
        add a,a
        add a,a
        add a,a
        add a,2
        ld c,a
        ld a,d
        swapnib
        neg
        add a,c                     ; pixels in the last column
        dec a
        swapnib
        ld c,a
.w:     ld a,(V_NR)                 ; height
        dec a
        cp e
        ld a,15
        jr nz,.h
        ld a,(V_HL)
        add a,2
        ld b,a
        ld a,e
        swapnib
        neg
        add a,b
        dec a
.h:     or c
        ld (ix+7),a
        ret

; hide: A = sprite slot; forgets it
hide:   nextreg 0x34,a
        nextreg 0x38,0
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,SPRTAB>>8
        ld h,a
        ld a,l
        add a,6
        ld l,a
        ld (hl),0
        ret

; pack_room: the canvas becomes room sprites, tiles with pixels only
pack_room:
        ld d,0
.c:     ld e,0
.r:     push de
        call pack
        pop de
        jr z,.next
        ld a,(V_NP)
        cp PLIM
        jr nc,.drop
        ld a,(V_NS)
        cp MAXROOM
        jr nc,.drop
        ld a,(V_NP)
        push de
        call upload
        pop de
        ld a,(V_NP)
        ld b,a
        inc a
        ld (V_NP),a
        ld a,(V_NS)
        ld c,a
        inc a
        ld (V_NS),a
        ld a,c
        call put
.next:  inc e
        ld a,(V_NR)
        cp e
        jr nz,.r
        inc d
        ld a,(V_NC)
        cp d
        jr nz,.c
        ret
.drop:  ld hl,V_DROP
        inc (hl)
        jr .next

; c_kn: the Knight
c_kn:   ld hl,(V_SP)                ; the dead stack word holds e_kn2 here, the original's return there
        dec hl
        ld (hl),0xA6
        dec hl
        ld (hl),0x3E
        ld a,(V_HID)
        or a
        call nz,unhide
        ld a,(KSHIFT)
        and 3
        ld c,a
        ld a,(KFACE)
        or a
        jr z,.f
        ld a,4
        add a,c
        ld c,a
.f:     ld a,c                      ; C = image 0-7 (4-7: the 384 byte offset)
        ld d,96
        ld e,a
        mul d,e
        ld hl,0xF9F4
        add hl,de
        ld (V_G),hl
        ld hl,0xFCF4
        add hl,de
        ld (V_M),hl
        ld a,c
        add a,a
        add a,a
        add a,a
        ld hl,CACHE
        add hl,a
        push hl
        ld hl,(V_G)                 ; checksum of the 192 bytes
        ld de,0
        ld b,96
.s1:    ld a,(hl)
        add de,a
        inc hl
        djnz .s1
        ld hl,(V_M)
        ld b,96
.s2:    ld a,(hl)
        add de,a
        inc hl
        djnz .s2
        pop hl
        ld a,(hl)
        or a
        jr z,.miss
        inc hl
        ld a,(KCOL)
        cp (hl)
        dec hl
        jr nz,.miss
        inc hl
        inc hl
        ld a,(hl)
        cp e
        dec hl
        dec hl
        jr nz,.miss
        inc hl
        inc hl
        inc hl
        ld a,(hl)
        cp d
        dec hl
        dec hl
        dec hl
        jr z,.hit
.miss:  ld a,1
        ld (V_MS),a                 ; a conversion: kwait at the end
        push bc
        ld (hl),1
        inc hl
        ld a,(KCOL)
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        push hl
        ld a,(KCOL)
        call setcol
        ld a,3
        ld (V_WB),a
        ld a,32
        ld (V_HL),a
        call build
        pop hl
        pop bc
        push hl
        push bc
        ld a,c
        ld d,KPAT
        ld e,a
        mul d,e
        ld a,e
        ld (V_PB),a
        xor a
        ld (V_TILE),a
        ld d,0
.kc:    ld e,0
.kr:    push de
        call pack
        pop de
        jr z,.kn
        ld a,d                      ; tile number = column * 3 + row
        add a,a
        add a,d
        add a,e
        ld b,a
        add a,0
        ld c,a
        ld a,(V_PB)
        add a,c
        push de
        push bc
        call upload
        pop bc
        pop de
        ld hl,V_TILE
        ld a,b
        inc a
        ld b,a
        ld a,0x80
.sh:    rlca
        djnz .sh
        or (hl)
        ld (hl),a
.kn:    inc e
        ld a,e
        cp 3
        jr nz,.kr
        inc d
        ld a,d
        cp 2
        jr nz,.kc
        pop bc
        pop hl
        ld a,(V_TILE)
        ld (hl),a
        ld de,-4
        add hl,de
.hit:   ld de,4
        add hl,de
        ld a,(hl)
        ld (V_TILE),a
        ld a,(KX)                   ; sprite position of the canvas origin
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,31
        add hl,de
        ld (V_X),hl
        ld a,(KY)
        ld l,a
        ld h,0
        add hl,de
        ld (V_Y),hl
        ld a,c
        ld d,KPAT
        ld e,a
        mul d,e
        ld a,e
        ld (V_PB),a
        ld a,(V_TILE)
        ld (V_L),a
        ld a,3
        ld (V_WB),a
        ld (V_NR),a
        ld a,32
        ld (V_HL),a
        ld a,2
        ld (V_NC),a
        ld d,0
.ac:    ld e,0
.ar:    ld a,d
        add a,a
        add a,d
        add a,e
        ld c,a                      ; tile number
        add a,KSLOT
        ld (V_CT),a
        ld a,(V_L)
        rrca
        ld (V_L),a
        jr nc,.ah
        ld a,(V_PB)
        add a,c
        ld b,a
        ld a,(V_CT)
        push de
        call put
        pop de
        jr .an
.ah:    ld a,(V_CT)
        call hide
.an:    inc e
        ld a,e
        cp 3
        jr nz,.ar
        inc d
        ld a,d
        cp 2
        jr nz,.ac
        jp kwait

; unhide: tiles a window hid come back
unhide: xor a
        ld (V_HID),a
        ld hl,SPRTAB+6
        ld b,0
.l:     ld a,b
        cp 128
        ret z
        ld a,(hl)
        and 3
        cp 2
        jr nz,.n
        ld a,(hl)
        and 0xFC
        or 1
        ld (hl),a
        ld a,b
        nextreg 0x34,a
        push hl
        ld de,-2
        add hl,de
        ld a,(hl)
        nextreg 0x38,a
        pop hl
.n:     ld de,8
        add hl,de
        inc b
        jr .l

; c_all: every figure sprite goes; room pool empty
c_all:  ld b,128
        ld c,0
.l:     ld a,c
        call hide
        inc c
        djnz .l
        xor a
        ld (V_NS),a
        ld (V_HID),a
        ld (V_SMA),a
        ld a,RFIRST
        ld (V_NP),a
        ret

; c_win: rectangle (25714) left, (25715) top, (25716) right, (25717) bottom (cells): hide the tiles that touch it
c_win:  ld a,(25714)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_WN),hl
        ld a,(25716)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,39
        add hl,de
        ld (V_WN+2),hl
        ld a,(25715)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_WN+4),hl
        ld a,(25717)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,39
        add hl,de
        ld (V_WN+6),hl
        ld ix,SPRTAB
        ld c,0
.l:     ld a,(ix+6)
        and 3
        cp 1
        jr nz,.n
        ld e,(ix+0)                 ; left edge, past a ring column
        ld d,(ix+1)
        bit 4,(ix+6)
        jr z,.a
        inc de
.a:     ld hl,(V_WN+2)              ; window right < left edge: clear of it
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+7)                 ; right edge
        swapnib
        and 15
        ld l,(ix+0)
        ld h,(ix+1)
        add hl,a
        ld de,(V_WN)
        or a
        sbc hl,de
        jr c,.n
        ld e,(ix+2)                 ; top edge
        ld d,(ix+3)
        bit 5,(ix+6)
        jr z,.b
        inc de
.b:     ld hl,(V_WN+6)
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+7)                 ; bottom edge
        and 15
        ld l,(ix+2)
        ld h,(ix+3)
        add hl,a
        ld de,(V_WN+4)
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+6)
        and 0xFC
        or 2
        ld (ix+6),a
        ld a,1
        ld (V_HID),a
        ld a,c
        nextreg 0x34,a
        nextreg 0x38,0
.n:     ld de,8
        add ix,de
        inc c
        ld a,c
        cp 128
        jp nz,.l
        ret

page_end:

; --- setup routine (stub bank, 0xD000): alt ROM image 0 = ROM 0 (the Bridge's star map reads ROM 0 at 0x0D00- from bank 1
; code, 7FFD = 1), palette, sprites hidden, layer on. Same paging steps as Target Renegade's.
        ORG 0xD000
setup:  nextreg 0x54,20             ; stub page alias at 0x8000
        jp .alias - 0x4000
.alias: ld bc,0x243B                ; unlock 7FFD paging (NextReg $08 bit 7)
        ld a,8
        out (c),a
        inc b
        in a,(c)
        or 0x80
        nextreg 0x08,a
        ld bc,0x1FFD                ; ROM 0
        xor a
        out (c),a
        ld b,0x7F
        out (c),a
        nextreg 0x8C,0xC0           ; alt ROM write mode: reads ROM, writes the image
        ld hl,0
        ld de,0
        ld bc,0x4000
        ldir
        nextreg 0x8C,0
        nextreg 0x56,20
        nextreg 0x57,21
        jp .back
.back:  nextreg 0x54,GP4
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
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
        nextreg 0x15,0x01           ; sprites on, SLU, higher number on top
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
pal:                                ; 16 palette bytes appended by Python

        SAVEBIN "sb_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sb_page.bin",0x9440,page_end-0x9440
        SAVEBIN "sb_setup.bin",0xD000,pal-0xD000
