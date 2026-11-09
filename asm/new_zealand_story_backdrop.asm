; The New Zealand Story v1.2: "Backdrops" toggle. Layer 2 (320x256, 8 bpp, banks 42-46 = pages 84-93)
; under the tilemap; layer priority SUL; Layer 2 clipped to the play area; the ULA's play area clipped
; away while the backdrop shows, so the tilemap's transparent pixels (type-0 paper, index 0) show it.
; The Layer 2 picture is a ring: buffer (x mod 320, y mod 256) holds the backdrop's world pixel (x, y).
; Kept valid for the region [RX, RX+304) x [RY, RY+192) around the camera (24-pixel margin on every side);
; each screen copy draws only the newly needed strips. Layer 2 scroll = (view - 32) mod (320, 256):
;   default build: the camera at the copy (0x5CA2/0x5CA4), written at the copy;
;   Smooth scrolling build: the view the interrupt commit shows (SM_DX/SM_DY), written in the same
;   interrupt as the tilemap offsets ($2F/$30/$31), right after the smooth commit.
; Code in alt ROM image 1 at 0x34C0-0x3CFF (page 82 offsets 0x14C0-0x1CFF: free in every build).
; Data: pages 45, 67, 81, 83 (nexclash/new_zealand_story_backdrops.py). Sites: 0xDAC4 (copy, after the colour copy hook),
; 0xA404 (the game's interrupt routine, after the colour/smooth interrupt hook).
; GPL-3.0-or-later, as NexClash.
    DEVICE NOSLOT64K
    OPT --zxnext

    IFNDEF NEG_SCROLL
NEG_SCROLL = 0                  ; negative control: the Layer 2 scroll one pixel off
    ENDIF
    IFNDEF NEG_LEVEL
NEG_LEVEL = 0                   ; negative control: the next level's backdrop (wrong level page)
    ENDIF

DIRPG   EQU 81
L2PG    EQU 84                  ; first 8K page of the Layer 2 (16K bank 42)
MARGIN  EQU 24
RW      EQU 256+2*MARGIN
RH      EQU 144+2*MARGIN
SM_DX   EQU 0x6028              ; the smooth build's shown view (page 15)
SM_DY   EQU 0x602A
; every page mapped at slot 3 keeps 0x1F00-0x1FFF free (as the colour hooks' pages do): the stack zone
; (SP = 0x8000 inside the hooks, about 120 bytes deep at most), scratch 0x7F00-0x7F1F, state 0x7F20-0x7F2F
SC_SX   EQU 0x7F00
SC_SY   EQU 0x7F01
SC_STG  EQU 0x7F02
SC_D    EQU 0x7F03
SC_BASE EQU 0x7F04
SC_RX   EQU 0x7F06
SC_RY   EQU 0x7F08
SC_X0   EQU 0x7F0A
SC_X1   EQU 0x7F0C
SC_Y0   EQU 0x7F0E
SC_Y1   EQU 0x7F10
SC_CX   EQU 0x7F12
SC_CY   EQU 0x7F14
SC_COLX EQU 0x7F16
SC_CURY EQU 0x7F18
SC_REM  EQU 0x7F1A
SC_PG   EQU 0x7F1C
SC_C    EQU 0x7F1D
SC_TX   EQU 0x7F1E
SC_UR   EQU 0x7F1F
; state, page 81 only
ST_KEY  EQU 0x7F20              ; level (0xA402) | 0x80 for the 34-wide 4-4
ST_VALID EQU 0x7F21
ST_ON   EQU 0x7F22
ST_PAGE EQU 0x7F23
ST_HDR  EQU 0x7F24
ST_SP   EQU 0x7F26              ; the game's SP
ST_M0   EQU 0x7F28              ; MMU0, MMU3 as found
ST_M3   EQU 0x7F29
ST_SPEED EQU 0x7F2A             ; the CPU speed as found ($07 bits 1-0)
; the run cache (in the tile page's zone): one tile column's runs, reused by its 16 pixel columns
SC_CC   EQU 0x7F2B              ; the tile column cached
SC_CN   EQU 0x7F2C              ; runs cached, 0xFF: none
SC_T8   EQU 0x7F2D              ; tx * 8
SC_K    EQU 0x7F2E              ; runs left to draw
SC_KY0  EQU 0x7F30              ; the rows cached
SC_KY1  EQU 0x7F32
SC_RUNS EQU 0x7F34              ; 16 x (source of tile column 0: 2, py, length)
BD_STK  EQU 0x8000

    MACRO SCROLL                ; Layer 2 scroll for view HL, DE: ((HL - 32) mod 320, (DE - 32) mod 256); no stack
    ld bc,32
    or a
    sbc hl,bc
    jr nc,.x1
    ld bc,320
    add hl,bc
.x1 ld bc,320
.x2 or a
    sbc hl,bc
    jr nc,.x2
    add hl,bc
    IF NEG_SCROLL
    inc hl
    ENDIF
    ld a,l
    nextreg 0x16,a
    ld a,h
    and 1
    nextreg 0x71,a
    ld a,e
    sub 32
    nextreg 0x17,a
    ENDM

    MACRO RDREG reg             ; A = NextReg reg (BC destroyed)
    ld bc,0x243B
    ld a,reg
    out (c),a
    inc b
    in a,(c)
    ENDM

    ORG 0x34C0
bd_start:
    MACRO BD_ENTER              ; save on the game's stack, switch to the zone stack (page 81 at slot 3),
    push af                     ; 28 MHz; out: C = level key, HL = camera X, DE = camera Y
    push bc
    push de
    push hl
    ld a,(0x6E00)               ; the map width: slot 3 still holds the game's page
    ld l,a
    ld a,(0xA402)
    ld h,a
    call bd_rd50
    ld e,a
    RDREG 0x53
    ld d,a
    ld a,i                      ; P/V = IFF2; read twice: an interrupt taken during LD A,I reads 0
    jp pe,.ie0                  ; (Z80 erratum), and the second read is right after its EI/RETI
    ld a,i
.ie0
    di
    nextreg 0x53,DIRPG
    ld (ST_SP),sp
    ld sp,BD_STK                ; the stack zone of whichever of our pages is at slot 3
    jp po,.ei0
    ei
.ei0
    ld (ST_M0),de
    push ix
    push iy
    call bd_rd7
    and 3
    ld (ST_SPEED),a
    nextreg 7,3
    ld c,h                      ; level key
    ld a,l
    cp 34
    jr nz,.k
    set 7,c
.k  ld hl,(0x5CA2)
    ld de,(0x5CA4)
    ENDM

    MACRO BD_LEAVE
    nextreg 0x53,DIRPG
    ld a,(ST_SPEED)
    nextreg 7,a
    pop iy
    pop ix
    ld de,(ST_M0)
    ld a,e
    nextreg 0x50,a
    ld a,i                      ; the same double read (Z80 erratum)
    jp pe,.ie1
    ld a,i
.ie1
    di
    ld sp,(ST_SP)
    ld a,d
    nextreg 0x53,a
    jp po,.ei1
    ei
.ei1
    pop hl
    pop de
    pop bc
    pop af
    ENDM

; ------------------------------------------------------------------ stage start / new life (site 0xA300)
; After the game's level init (0xD933) on the READY screen: the stage's first full draw (or the redraw after
; a respawn's camera jump) happens here, at 28 MHz, while the screen shows READY, not in play.
; The interrupt leaves NR 0x53 selected: its page read between OUT and IN would be taken for this register. NR 7 has bit 6 clear, page
; 81 (slot 3 here) set; MMU0 is read until two readings agree (an interrupt comes once in a frame).
bd_rd7:
    RDREG 7
    bit 6,a
    jr nz,bd_rd7
    ret
bd_rd50:
    RDREG 0x50
    push af
    RDREG 0x50
    pop bc
    cp b
    jr nz,bd_rd50
    ret
bd_ready:
    BD_ENTER
    ld a,(ST_VALID)
    or a
    jr z,.init
    ld a,(ST_KEY)
    cp c
    jr z,.scroll
.init
    call level_init
    jr .done
.scroll
    ld iy,(ST_HDR)
    ld a,(ST_PAGE)
    nextreg 0x53,a
    ld (SC_CX),hl
    ld (SC_CY),de
    call scroll_update
.done
    BD_LEAVE
bd_rtail:
    call 0xA948                 ; the replaced instruction
    jp 0xA303

; ------------------------------------------------------------------ after the scroll, before the copy (site 0xA394)
; The game's camera for this update is final (0xD814 ran); the screen still shows the last copy, so the new
; strips (outside the region shown) are drawn here, before the line cap's wait, and the copy hook only has to
; top up and switch Layer 2 on: no frame shows the tilemap's see-through paper without the backdrop.
bd_pre:
    BD_ENTER
    ld a,(ST_VALID)
    or a
    jr z,.done
    ld a,(ST_KEY)
    cp c
    jr nz,.done                 ; a new level: the READY hook or the copy sets it up
    ld iy,(ST_HDR)
    ld a,(ST_PAGE)
    nextreg 0x53,a
    ld (SC_CX),hl
    ld (SC_CY),de
    call scroll_update
.done
    BD_LEAVE
bd_ptail:
    call 0xA75D                 ; the replaced instruction
    jp 0xA397

; ------------------------------------------------------------------ the copy (site 0xDAC4)
bd_copy:
    BD_ENTER
    ld a,(ST_VALID)
    or a
    jr z,.init
    ld a,(ST_KEY)
    cp c
    jr z,.scroll
.init
    call level_init             ; C = key, HL = camera X, DE = camera Y; Z: no backdrop here
    jr z,.off
    jr .show
.scroll
    ld iy,(ST_HDR)
    ld a,(ST_PAGE)
    nextreg 0x53,a
    ld (SC_CX),hl
    ld (SC_CY),de
    call scroll_update
    nextreg 0x53,DIRPG
.show
    call is_smooth
    jr z,.sm                    ; smooth: the interrupt writes the scroll
    ld a,(ST_PAGE)
    nextreg 0x53,a
    ld hl,(SC_CX)
    ld de,(SC_CY)
    call set_scroll
    nextreg 0x53,DIRPG
.sm call show_on
    jr .out
.off
    call show_off
.out
    BD_LEAVE
bd_ctail:
    ld hl,0xE700                ; the replaced instruction
    jp 0xDAC7

; Z set when the Smooth scrolling build's interrupt hook is installed (h_irq + K is its JP h_irq_smooth)
is_smooth:
    ld a,(0xFDFD)
    cp 0xC3
    ret nz
    push hl
    push de
    ld hl,(0xFDFE)
    ld a,h
    cp 0x40
    jr nc,.no                   ; not a hook (the game's own JP 0xA404)
    ld de,BD_SMOOTH_K
    add hl,de
    ld a,(hl)
    cp 0xC3
    pop de
    pop hl
    ret
.no pop de
    pop hl
    or 1
    ret

; ------------------------------------------------------------------ level start: palette, world, full draw
; In: page 81 at slot 3, C = level key, HL = camera X, DE = camera Y. Out: NZ = backdrop on, slot 3 = 81.
level_init:
    ld a,c
    ld (ST_KEY),a
    xor a
    ld (ST_VALID),a
    ld a,c
    and 0x7F
    IF NEG_LEVEL
    inc a
    ENDIF
    cp 21
    jr c,.ok
    xor a
    ret
.ok push hl
    push de
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld de,0x6380
    add hl,de                   ; level table entry: world, stage, base lo, hi
    ld a,(hl)
    or a
    jr nz,.w
    pop de
    pop hl
    xor a
    ret
.w  ld b,a                      ; world 1-5
    inc hl
    ld c,(hl)                   ; stage 0-3
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)                   ; base y
    push de
    push bc
    ; palette: page 81 0x6100 + ((world-1)*4 + stage) * 32
    ld a,b
    dec a
    add a,a
    add a,a
    add a,c
    ld e,a
    ld d,32
    mul d,e
    ld hl,0x6100
    add hl,de
    RDREG 0x43
    push af
    nextreg 0x43,0x10           ; Layer 2 first palette, auto-increment
    nextreg 0x40,16
    ld b,32
.p  ld a,(hl)
    inc hl
    nextreg 0x44,a
    djnz .p
    pop af
    nextreg 0x43,a
    pop bc                      ; B world, C stage
    ld a,b
    dec a
    ld e,a
    ld d,0
    ld hl,bd_wpage
    add hl,de
    ld a,(hl)
    ld (ST_PAGE),a
    ld hl,bd_whdr
    add hl,de
    add hl,de
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    ld (ST_HDR),hl
    push hl
    pop iy                      ; IY = the world header (in its page)
    pop ix                      ; base y
    pop de                      ; camera Y, X (pushed with page 81 at slot 3: popped before it goes)
    pop hl
    ld a,(ST_PAGE)
    nextreg 0x53,a              ; no stack use from here until page 81 is back, except balanced calls
    ld a,0xFF
    ld (SC_CN),a                ; the run cache: empty
    ld (SC_BASE),ix
    ld (SC_CX),hl
    ld (SC_CY),de
    ld e,c
    ld d,0
    push iy
    pop hl
    add hl,de
    ld de,8
    add hl,de
    ld a,(hl)
    ld (SC_SX),a
    ld de,4
    add hl,de
    ld a,(hl)
    ld (SC_SY),a
    add hl,de
    ld a,(hl)
    ld (SC_STG),a
    call region                 ; HL = RX, DE = RY for this camera
    ld (SC_RX),hl
    ld (SC_RY),de
    call draw_full
    nextreg 0x53,DIRPG
    ld a,1
    ld (ST_VALID),a
    or a
    ret

; HL = max(0, SC_CX - MARGIN), DE = max(0, SC_CY - MARGIN)
region:
    ld hl,(SC_CX)
    ld de,MARGIN
    or a
    sbc hl,de
    jr nc,.x
    ld hl,0
.x  push hl
    ld hl,(SC_CY)
    or a
    sbc hl,de
    jr nc,.y
    ld hl,0
.y  ex de,hl
    pop hl
    ret

draw_full:
    ld hl,(SC_RX)
    ld (SC_X0),hl
    ld de,RW
    add hl,de
    ld (SC_X1),hl
    ld hl,(SC_RY)
    ld (SC_Y0),hl
    ld de,RH
    add hl,de
    ld (SC_Y1),hl
    jp draw_rect

; ------------------------------------------------------------------ a copy in play: the new strips
; Slot 3 = the world's tile page, IY = its header, SC_CX/SC_CY = the camera.
scroll_update:
    call region                 ; HL = nx, DE = ny
    push de
    push hl
    ld bc,(SC_RX)
    or a
    sbc hl,bc                   ; dx
    call absbig_x
    jp nc,.full
    ex de,hl
    ld bc,(SC_RY)
    or a
    sbc hl,bc                   ; dy
    call absbig_y
    jp nc,.full
    ; columns: dx > 0: [ox+RW, nx+RW); dx < 0: [nx, ox); rows ny..ny+RH
    pop hl                      ; nx
    pop de                      ; ny
    push de
    push hl
    ld (SC_Y0),de
    ex de,hl
    ld bc,RH
    add hl,bc
    ld (SC_Y1),hl
    pop hl
    push hl
    ld de,(SC_RX)
    or a
    sbc hl,de
    jr z,.rows
    jr c,.left
    ld hl,(SC_RX)
    ld bc,RW
    add hl,bc
    ld (SC_X0),hl
    pop hl
    push hl
    add hl,bc
    ld (SC_X1),hl
    call draw_rect
    jr .rows
.left
    pop hl
    push hl
    ld (SC_X0),hl
    ld hl,(SC_RX)
    ld (SC_X1),hl
    call draw_rect
.rows
    ; the overlap columns [max(nx,ox), min(nx,ox)+RW)
    pop hl                      ; nx
    push hl
    ld de,(SC_RX)
    or a
    sbc hl,de
    add hl,de
    jr nc,.mx                   ; nx >= ox
    ex de,hl                    ; HL = ox, DE = nx
.mx ld (SC_X0),hl               ; max
    ex de,hl                    ; HL = min
    ld bc,RW
    add hl,bc
    ld (SC_X1),hl
    pop hl
    pop de                      ; ny
    push de
    push hl
    ex de,hl
    ld de,(SC_RY)
    or a
    sbc hl,de
    jr z,.done
    jr c,.up
    ld hl,(SC_RY)               ; dy > 0: [oy+RH, ny+RH)
    ld bc,RH
    add hl,bc
    ld (SC_Y0),hl
    pop hl
    pop de
    push de
    push hl
    ex de,hl
    add hl,bc
    ld (SC_Y1),hl
    call draw_rect
    jr .done
.up pop hl                      ; dy < 0: [ny, oy)
    pop de
    push de
    push hl
    ld (SC_Y0),de
    ld hl,(SC_RY)
    ld (SC_Y1),hl
    call draw_rect
    jr .done
.full
    pop hl
    pop de
    ld (SC_RX),hl
    ld (SC_RY),de
    jp draw_full
.done
    pop hl
    pop de
    ld (SC_RX),hl
    ld (SC_RY),de
    ret

; carry set when |HL| < RW (HL signed)
absbig_x:
    ld bc,RW
    jr absbig
absbig_y:
    ld bc,RH
absbig:
    bit 7,h
    jr z,.p
    push de
    ex de,hl
    ld hl,0
    or a
    sbc hl,de
    pop de
.p  or a
    sbc hl,bc
    ret

; ------------------------------------------------------------------ drawing
; draw_rect: columns SC_X0..SC_X1-1, rows SC_Y0..SC_Y1-1 (world pixels); slot 3 = tile page, IY = header.
draw_rect:
    ld hl,(SC_X0)
.c  ld de,(SC_X1)
    or a
    sbc hl,de
    ret nc
    add hl,de
    ld (SC_COLX),hl
    push hl
    call draw_col
    pop hl
    inc hl
    jr .c

draw_col:
    ld hl,(SC_COLX)
    ld de,320
.m  or a
    sbc hl,de
    jr nc,.m
    add hl,de                   ; buffer x
    ld a,l
    and 31
    ld (SC_D),a
    ld a,l
    rlca
    rlca
    rlca
    and 7
    ld b,a
    ld a,h
    add a,a
    add a,a
    add a,a
    or b
    add a,L2PG
    ld (SC_PG),a
    ld hl,(SC_COLX)
    ld a,l
    and 15
    ld (SC_TX),a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    ld (SC_C),a
    ld a,(SC_TX)
    add a,a
    add a,a
    add a,a
    ld (SC_T8),a
    ld a,(SC_CN)                ; the runs of this tile column for these rows, cached?
    cp 0xFF
    jr z,.build
    ld a,(SC_C)
    ld hl,SC_CC
    cp (hl)
    jr nz,.build
    ld hl,(SC_Y0)
    ld de,(SC_KY0)
    or a
    sbc hl,de
    jr nz,.build
    ld hl,(SC_Y1)
    ld de,(SC_KY1)
    or a
    sbc hl,de
    jr z,.redo
.build
    ld a,(SC_C)
    ld (SC_CC),a
    ld hl,(SC_Y1)
    ld (SC_KY1),hl
    ld hl,(SC_Y0)
    ld (SC_KY0),hl
    ld (SC_CURY),hl
    ex de,hl
    ld hl,(SC_Y1)
    or a
    sbc hl,de
    ld (SC_REM),hl
    ld ix,SC_RUNS
    xor a
    ld (SC_CN),a
.b1 call cell                   ; HL = source (tile column 0), C = py, B = run length
    ld (ix+0),l
    ld (ix+1),h
    ld (ix+2),c
    ld (ix+3),b
    inc ix
    inc ix
    inc ix
    inc ix
    ld hl,SC_CN
    inc (hl)
    ld a,(SC_REM)
    or a
    jr nz,.b1
    ld a,(SC_REM+1)
    or a
    jr nz,.b1
.redo
    ld a,(SC_PG)
    nextreg 0x50,a
    ld a,(SC_D)
    ld d,a
    ld a,(SC_Y0)
    ld e,a                      ; DE = 0x0000 + D*256 + (y & 255) in slot 0
    ld ix,SC_RUNS
    ld a,(SC_CN)
    ld (SC_K),a
.run
    ld l,(ix+0)
    ld h,(ix+1)
    ld a,(SC_T8)
    add a,l
    ld l,a
    adc a,h
    sub l
    ld h,a
    ld c,(ix+2)
    ld b,(ix+3)
    bit 0,c
    jr z,.even
    ld a,(hl)                   ; an odd first row: its low nibble
    and 15
    or 16
    ld (de),a
    inc e
    inc hl
    dec b
    jr z,.next
.even
    ld a,b
    push af                     ; its bit 0: a last high nibble
    srl b
    jr z,.last
.pair
    ld a,(hl)
    swapnib
    and 15
    or 16
    ld (de),a
    inc e
    ld a,(hl)
    and 15
    or 16
    ld (de),a
    inc e
    inc hl
    djnz .pair
.last
    pop af
    and 1
    jr z,.next
    ld a,(hl)
    swapnib
    and 15
    or 16
    ld (de),a
    inc e
.next
    inc ix
    inc ix
    inc ix
    inc ix
    ld hl,SC_K
    dec (hl)
    jr nz,.run
    RDREG 0x50                  ; an interrupt's 0x7FFD write puts the ROM back: redo the column
    ld hl,SC_PG
    cp (hl)
    jr nz,.redo
    ret

; cell: for tile column SC_C at row SC_CURY: HL = source byte of the tile's pixel column 0 (add tx*8),
; C = py (row in the tile), B = run length (min(16 - py, SC_REM)); advances SC_CURY and SC_REM by the run.
cell:
    ld a,(iy+0)
    or a
    jp nz,.hz
    ; texture: R = y >> 4, py = y & 15
    ld hl,(SC_CURY)
    ld a,l
    and 15
    push af                     ; py
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l                      ; R (< 256)
    ld e,(iy+2)                 ; cy
    ld d,0                      ; quotient
.dv cp e
    jr c,.dd
    sub e
    inc d
    jr .dv
.dd ld hl,SC_SY
    add a,(hl)
    cp e
    jr c,.u1
    sub e
.u1 ld (SC_UR),a                ; ur
    ld b,0
    ld a,(SC_STG)
    or a
    jr z,.ns
    bit 0,d
    jr z,.ns
    ld b,(iy+6)                 ; cx/2
.ns ld a,(SC_C)
    ld e,(iy+1)                 ; cx
.m1 cp e
    jr c,.m2
    sub e
    jr .m1
.m2 add a,b
    ld hl,SC_SX
    add a,(hl)
.m3 cp e
    jr c,.m4
    sub e
    jr .m3
.m4 ld b,a                      ; uc
    pop af
    ld c,a                      ; py
    jp .tile
.hz ; horizon: rel = y - base
    ld hl,(SC_CURY)
    ld de,(SC_BASE)
    or a
    sbc hl,de
    bit 7,h
    jr nz,.above
    ; ground: ur = ns + nb + ((rel >> 4) mod ng)
    ld a,l
    and 15
    ld c,a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    ld e,(iy+5)
.g1 cp e
    jr c,.g2
    sub e
    jr .g1
.g2 add a,(iy+3)
    add a,(iy+4)
    jr .hu
.above
    ld e,(iy+24)
    ld d,(iy+25)                ; nb*16
    add hl,de
    bit 7,h
    jr nz,.sky
    ld a,l                      ; band: ur = ns + (k >> 4)
    and 15
    ld c,a
    ld a,l
    rrca
    rrca
    rrca
    rrca
    and 15
    add a,(iy+3)
    jr .hu
.sky; t = -(rel + nb*16) > 0; m = t mod ns*16; k = m ? ns*16 - m : 0
    ex de,hl
    ld hl,0
    or a
    sbc hl,de
    ld e,(iy+26)
    ld d,(iy+27)                ; ns*16
.s1 or a
    sbc hl,de
    jr nc,.s1
    add hl,de                   ; m
    ld a,h
    or l
    jr z,.s2
    ex de,hl
    or a
    sbc hl,de                   ; ns*16 - m
.s2 ld a,l
    and 15
    ld c,a
    ld a,l
    rrca
    rrca
    rrca
    rrca
    and 15                      ; ur
.hu ld (SC_UR),a
    ld a,(SC_C)
    ld e,(iy+1)
.h1 cp e
    jr c,.h2
    sub e
    jr .h1
.h2 ld hl,SC_SX
    add a,(hl)
.h3 cp e
    jr c,.h4
    sub e
    jr .h3
.h4 ld b,a                      ; uc
.tile
    ; tile = umap[ur * cx + uc]
    ld a,(SC_UR)
    ld d,a
    ld e,(iy+1)
    mul d,e
    ld l,(iy+22)
    ld h,(iy+23)
    add hl,de
    ld e,b
    ld d,0
    add hl,de
    ld d,(hl)                   ; tile number
    ld e,128
    mul d,e
    ld l,(iy+20)
    ld h,(iy+21)
    add hl,de
    ld a,c
    srl a
    ld e,a
    ld d,0
    add hl,de                   ; source byte (pixel column 0)
    ; run length = min(16 - py, REM)
    ld a,16
    sub c
    ld b,a
    push hl
    ld hl,(SC_REM)
    ld a,h
    or a
    jr nz,.full
    ld a,l
    cp b
    jp nc,.full
    ld b,a
.full
    ld e,b
    ld d,0
    or a
    sbc hl,de
    ld (SC_REM),hl
    ld hl,(SC_CURY)
    add hl,de
    ld (SC_CURY),hl
    pop hl
    ret

; ------------------------------------------------------------------ Layer 2 on/off, scroll
set_scroll:                     ; HL = view X, DE = view Y (world pixels)
    SCROLL
    ret

show_on:                        ; page 81 at slot 3
    nextreg 0x70,0x10           ; 320x256, palette offset 0
    nextreg 0x12,42             ; Layer 2 at 16K bank 42
    nextreg 0x1C,0x05           ; reset the Layer 2 and ULA clip indexes
    nextreg 0x18,16
    nextreg 0x18,143
    nextreg 0x18,32
    nextreg 0x18,175            ; Layer 2: the play area
    nextreg 0x1A,0
    nextreg 0x1A,255
    nextreg 0x1A,144
    nextreg 0x1A,191            ; ULA: the score panel only
    RDREG 0x15
    and 0xE3
    or 0x08                     ; SUL
    nextreg 0x15,a
    ld a,2
    ld bc,0x123B
    out (c),a                   ; Layer 2 visible
    ld a,1
    ld (ST_ON),a
    ret

show_off:                       ; page 81 at slot 3
    xor a
    ld bc,0x123B
    out (c),a
    nextreg 0x1C,0x04
    nextreg 0x1A,0
    nextreg 0x1A,255
    nextreg 0x1A,0
    nextreg 0x1A,191
    xor a
    ld (ST_ON),a
    ret

; ------------------------------------------------------------------ the interrupt (site 0xA404)
bd_irq:
    push af
    push bc
    push de
    push hl
    push ix                     ; no stack use below while slot 3 holds another page
    RDREG 0x53
    ld ixh,a
    nextreg 0x53,DIRPG
    ld a,(ST_ON)
    or a
    jp z,.out
    RDREG 0x6B
    bit 7,a
    jr nz,.tm
    xor a                       ; the tilemap went off (READY, title, loader): so does the backdrop
    ld bc,0x123B
    out (c),a
    nextreg 0x1C,0x04
    nextreg 0x1A,0
    nextreg 0x1A,255
    nextreg 0x1A,0
    nextreg 0x1A,191
    ld (ST_ON),a
    jp .out
.tm ld a,(0xFDFD)               ; the Smooth scrolling build's hook installed?
    cp 0xC3
    jp nz,.pr
    ld hl,(0xFDFE)
    ld a,h
    cp 0x40
    jp nc,.pr
    ld de,BD_SMOOTH_K
    add hl,de
    ld a,(hl)
    cp 0xC3
    jp nz,.pr
    nextreg 0x53,15
    ld hl,(SM_DX)
    ld de,(SM_DY)
    SCROLL
.pr RDREG 0x15                  ; the smooth commit writes $15 (sprites): keep SUL
    and 0xE3
    or 0x08
    nextreg 0x15,a
.out
    ld a,ixh
    nextreg 0x53,a
    pop ix
    pop hl
    pop de
    pop bc
    pop af
bd_itail:
    push af                     ; the replaced instructions
    push bc
    push de
    jp 0xA407

    INCLUDE "bd_layout.inc"
bd_end:
    ASSERT bd_end <= 0x4000
    SAVEBIN "OUT.bin", bd_start, bd_end-bd_start
