; Everyone's a Wally, updated (engine wally2; Mikro-Gen, 48K code in a 128K snapshot).
; Every figure (plotters A 45286 gang member 16x32, B 43168 masked 16x16, C 43069 OR-only 16x16)
; is drawn on a double-buffered Layer 2 instead of the back buffer, in plot order (later in front),
; each from a precomputed CANVAS: 18 x (rows + 2) bytes, the graphic with a one-pixel ring, the
; colour map and the black outline (left / right / up / down neighbours of the ink only; Dean
; 2026-10-14) baked in by wally2.py. Canvas byte: 0 = transparent; else bits 6-5 = code (01 ink,
; 10 outline, 00 painted clear pixel), bit 4 = use the figure's run-time colour, bits 3-0 = palette
; index. Canvases live in Next pages the game never reads (recolour rewrites only those).
; The game rebuilds the back buffer (0x6B00, attrs 0xFC00) every render and copies it to the screen
; (47611); the commit hook (47637, after the pixel copy) draws the render's figures into the Layer 2
; buffer not on show and shows it. Interrupts are never enabled (isr: 0 accepted in the RZX).
; Entry/exit stubs in alt ROM image 1 at 0x386E; bodies, state and tables in Next RAM page PAGE_S
; (MMU slot 0 while a hook runs); the graphic tables in page TPAGE (slot 1 during a plot hook);
; canvas pages at slot 1 and Layer 2 pages at slot 2 only during the commit.
;
; Patch sites (original bytes verified by wally2.py):
;   45286  D9 FD 5E   EXX / LD E,(IY+35)        -> JP e_a   (plotter A)
;   43168  D9 F5 ED   EXX / PUSH AF / LD (nn),SP -> JP e_b   (plotter B)
;   43069  F3 D9 F5   DI / EXX / PUSH AF         -> JP e_c   (plotter C)
;   61329  F5 D9 3A   PUSH AF / EXX / LD A,(nn)  -> JP e_p   (attribute painter after B/C)
;   47637  01 00 02   LD BC,512                  -> JP e_cm  (commit, after the pixel copy)
;   61090  11 00 6B   LD DE,27392                -> JP e_rs  (buffer restore: drop pending plots)
;   47362  E5 C5 D5   PUSH HL / PUSH BC / PUSH DE -> JP e_cl (play-area clear: room change, hide L2)
; A converted plot leaves every register, the game stack and all RAM exactly as the original,
; except the back buffer / attribute buffer cells it would have drawn (never read by game logic).
; A plot is converted only when its graphics bytes match a canvas (16-bit check of the bytes as
; stored or as mirrored in place by 33251); anything else runs the original plotter.

        DEVICE ZXSPECTRUMNEXT

PAGE_S  EQU 26
TPAGE   EQU 27
MAXP    EQU 24                  ; plots per render
L2BANK0 EQU 16                  ; Layer 2 buffers: 16K banks 16-18 (pages 32-37) and 19-21 (38-43)
L2BANK1 EQU 19
V_N     EQU 0x0000              ; plots this render
V_LAST  EQU 0x0001              ; 1 + index of a converted B/C plot awaiting 61329 (0 = none)
V_BACK  EQU 0x0002              ; Layer 2 buffer drawn next (0 / 1; the other one is on show)
V_SP    EQU 0x0004
V_X     EQU 0x0008
V_Y     EQU 0x0009
V_GFX   EQU 0x000A
V_ENT   EQU 0x000C
V_ORI   EQU 0x000E
V_COL   EQU 0x000F
V_KIND  EQU 0x0010              ; 0 A, 1 B, 2 C
V_H     EQU 0x0011
V_PG    EQU 0x0012
V_OFF   EQU 0x0013
V_CALL  EQU 0x0015
V_L2P   EQU 0x0017
V_RB    EQU 0x0018              ; canvas row base
V_ROW   EQU 0x001A
V_CS    EQU 0x001B              ; first canvas column drawn
V_CNT   EQU 0x001C              ; columns drawn
V_BOX   EQU 0x001E
STK     EQU 0x0100              ; hook stack top (grows down into 0x00C0-0x00FF)
INKTAB  EQU 0x1800              ; attribute -> palette index of its ink (black = 8)
PL      EQU 0x1900              ; plot list: 16 bytes per plot
BOX0    EQU 0x1B00              ; per Layer 2 buffer: count, then x0, y0, x1, y1 per drawn box
BOX1    EQU 0x1C80
TA      EQU 0x2000              ; graphic tables (page TPAGE at slot 1): 8 bytes per graphic:
TB      EQU 0x2200              ;   canvas page, canvas offset (2), check as stored (2), check
TC      EQU 0x2700              ;   mirrored (2), 0
NA      EQU 40                  ; A graphics: 37944 + 128*i
NB      EQU 133                 ; B frames 0-132: 33656 + 32*f, 64 bytes
NC      EQU 134                 ; C frames 0-133: 33656 + 32*f, 32 bytes
; plot entry: +0 canvas page, +1/2 offset, +3 x, +4 y, +5 canvas rows, +6 colour, +7 flags
;             (bit 0 mirrored, bit 1 joined to the plot before), +8 kind, +9/10 caller

        ORG 0x386E
e_a:    nextreg 0x50,PAGE_S
        jp s_a
e_b:    nextreg 0x50,PAGE_S
        jp s_b
e_c:    di
        nextreg 0x50,PAGE_S
        jp s_c
e_p:    nextreg 0x50,PAGE_S
        jp s_p
e_cm:   nextreg 0x50,PAGE_S
        jp s_cm
e_rs:   nextreg 0x50,PAGE_S
        jp s_rs
e_cl:   nextreg 0x69,0x00           ; room change: the old figures must not stay over the new room
        push hl
        push bc
        push de
        jp 47365
x_ret:  nextreg 0x50,0xFF
        ret
x_a:    nextreg 0x50,0xFF
        exx
        ld e,(iy+35)
        jp 45290
x_b:    nextreg 0x50,0xFF
        exx
        push af
        ld (43067),sp
        jp 43174
x_c:    nextreg 0x50,0xFF
        exx
        push af
        jp 43072
x_p:    nextreg 0x50,0xFF
        push af
        exx
        ld a,(62063)
        jp 61334
x_cm:   nextreg 0x50,0xFF
        ld bc,512
        jp 47640
x_rs:   nextreg 0x50,0xFF
        ld de,27392
        jp 61093
rom_end:

        ORG 0x0100
; ---- plotter A: gang member, IY = descriptor (frame +0, x +5, y +10, attr +30, gfx +35/+40) ----
s_a:    ld (V_SP),sp
        ld sp,STK
        push af
        exx                         ; the game's alternate set (all overwritten by the plotter)
        nextreg 0x07,3
        ld a,(V_N)
        cp MAXP
        jp nc,.pass
        ld a,(iy+10)
        cp 64
        jp c,.pass
        cp 161
        jp nc,.pass
        ld (V_Y),a
        ld a,(iy+5)
        cp 241
        jp nc,.pass
        ld (V_X),a
        ld l,0                      ; graphic = (IY+35/40) + frame * 128
        ld h,(iy+0)
        srl h
        rr l
        ld e,(iy+35)
        ld d,(iy+40)
        add hl,de
        ld (V_GFX),hl
        ld de,-37944
        add hl,de
        jp nc,.pass
        ld a,l
        and 127
        jp nz,.pass
        ld a,l
        rlca
        and 1
        ld c,a
        ld a,h
        add a,a
        or c
        cp NA
        jp nc,.pass
        ld de,TA
        call entry
        ld hl,(V_GFX)
        ld b,128
        call chksum
        nextreg 0x51,TPAGE
        call orient
        nextreg 0x51,0xFF
        jp c,.pass
        ld a,(V_X)                  ; the plotter's self-modified operands
        and 7
        ld (45449),a
        inc a
        ld (45353),a
        ld (45381),a
        call xcol
        ld (45435),a
        ld hl,(V_SP)
        ld (43067),hl
        ld l,(iy+30)
        ld h,high INKTAB
        ld a,(hl)
        ld (V_COL),a
        xor a
        ld (V_KIND),a
        ld a,34
        ld (V_H),a
        call stage
        ld a,(V_Y)                  ; end state of the attribute loop
        and 248
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        call xcol
        ld e,a
        ld d,0xFB
        add hl,de
        ld de,4*32-30
        ld a,(V_Y)
        and 7
        jr z,.r4
        ld de,5*32-30
.r4:    add hl,de
        ld c,(iy+30)
        ld b,0
        ld de,30
        ld a,(V_X)
        and 7
        or a                        ; flags exactly as OR A / ADD HL,DE in the last row
        add hl,de
        exx
        nextreg 0x07,0
        ld sp,(V_SP)
        jp x_ret
.pass:  exx
        nextreg 0x07,0
        pop af
        ld sp,(V_SP)
        jp x_a

; ---- plotter B: masked 16x16, A = frame (gfx 33656 + A*32), position (43064/43065) ----
s_b:    ld (V_SP),sp
        ld sp,STK
        push af
        exx
        nextreg 0x07,3
        ld a,(V_N)
        cp MAXP
        jp nc,.pass
        ld a,(43065)
        cp 64
        jp c,.pass
        cp 169
        jp nc,.pass
        ld (V_Y),a
        ld a,(43064)
        cp 241
        jp nc,.pass
        ld (V_X),a
        pop af
        push af
        cp NB
        jp nc,.pass
        ld de,TB
        call entry
        ld b,64
        call gfxsum
        jp c,.pass
        pop af                      ; PUSH AF on the game stack, (43067) = SP after it
        push af
        ld hl,(V_SP)
        dec hl
        ld (hl),a
        dec hl
        push af
        pop bc
        ld (hl),c
        ld (43067),hl
        ld a,(V_X)
        and 7
        inc a
        ld (43232),a
        ld (43260),a
        call xcol
        ld (61359),a
        call ccol
        ld a,1
        ld (V_KIND),a
        ld a,18
        ld (V_H),a
        ld a,(V_N)
        inc a
        ld (V_LAST),a
        call stage
        call bcend
        pop af
        exx
        nextreg 0x07,0
        ld sp,(V_SP)
        jp x_ret
.pass:  xor a
        ld (V_LAST),a               ; 61329 after this plot paints the ULA (as the original)
        exx
        nextreg 0x07,0
        pop af
        ld sp,(V_SP)
        jp x_b

; ---- plotter C (after its DI): OR-only 16x16, A = frame, position (43064/43065) ----
s_c:    ld (V_SP),sp
        ld sp,STK
        push af
        exx
        nextreg 0x07,3
        ld a,(V_N)
        cp MAXP
        jp nc,.pass
        ld a,(43065)
        cp 64
        jp c,.pass
        cp 169
        jp nc,.pass
        ld (V_Y),a
        ld a,(43064)
        cp 241
        jp nc,.pass
        ld (V_X),a
        pop af
        push af
        cp NC
        jp nc,.pass
        ld de,TC
        call entry
        ld b,32
        call gfxsum
        jp c,.pass
        pop af                      ; PUSH AF on the game stack, (43067) = SP after it
        push af
        ld hl,(V_SP)
        dec hl
        ld (hl),a
        dec hl
        push af
        pop bc
        ld (hl),c
        ld (43067),hl
        ld a,(V_X)
        and 7
        inc a
        ld (43131),a
        call xcol
        ld (61359),a
        call ccol
        ld a,2
        ld (V_KIND),a
        ld a,18
        ld (V_H),a
        ld a,(V_N)
        inc a
        ld (V_LAST),a
        call stage
        call bcend
        pop af
        exx
        nextreg 0x07,0
        ld sp,(V_SP)
        jp x_ret
.pass:  xor a
        ld (V_LAST),a
        exx
        nextreg 0x07,0
        pop af
        ld sp,(V_SP)
        jp x_c

; ---- 61329: attribute painter. After a converted B/C it only sets that plot's colour ----
s_p:    ld (V_SP),sp
        ld sp,STK
        push af
        ld a,(V_LAST)
        or a
        jr z,.pass
        exx
        pop af
        push af
        ld hl,(V_SP)                ; PUSH AF on the game stack
        dec hl
        ld (hl),a
        dec hl
        push af
        pop bc
        ld (hl),c
        ld a,(V_LAST)
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,PL+6
        add hl,de
        ld a,(62063)
        ld e,a
        ld d,high INKTAB
        ld a,(de)
        ld (hl),a
        xor a
        ld (V_LAST),a
        ld a,(43065)                ; end state of the attribute loop
        and 248
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(61359)
        ld e,a
        ld d,0xFB
        add hl,de
        ld de,64
        ld a,(43065)
        and 7
        jr z,.r2
        ld de,96
.r2:    add hl,de
        ld de,30
        ld b,0
        ld a,(62063)
        ld c,a
        pop af
        exx
        ld sp,(V_SP)
        jp x_ret
.pass:  pop af
        ld sp,(V_SP)
        jp x_p

; ---- 61090: the back buffer is restored - plots since the last commit never reach the screen ----
s_rs:   ld (V_SP),sp
        ld sp,STK
        push af
        xor a
        ld (V_N),a
        ld (V_LAST),a
        pop af
        ld sp,(V_SP)
        jp x_rs

; ---- 47637 (pixel copy done): draw this render's figures into the hidden buffer, show it ----
s_cm:   ld (V_SP),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x07,3
        ld a,(V_BACK)
        or a
        ld a,32
        ld hl,BOX0
        jr z,.b0
        ld a,38
        ld hl,BOX1
.b0:    ld (V_L2P),a
        ld (V_BOX),hl
        call clearbox
        ld hl,(V_BOX)
        ld (hl),0
        call drawall
        ld a,(V_BACK)
        or a
        jr nz,.s1
        nextreg 0x12,L2BANK0
        jr .s2
.s1:    nextreg 0x12,L2BANK1
.s2:    xor 1
        ld (V_BACK),a
        nextreg 0x69,0x80
        nextreg 0x51,0xFF
        nextreg 0x52,10
        xor a
        ld (V_N),a
        ld (V_LAST),a
        nextreg 0x07,0
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        jp x_cm

; ---- helpers (plot hooks) ----
xcol:   ld a,(V_X)                  ; A = x / 8
        rrca
        rrca
        rrca
        and 31
        ret

entry:  ld l,a                      ; V_ENT = DE + A * 8
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        ld (V_ENT),hl
        ret

gfxsum: pop hl                      ; B/C: frame on our stack under the return address
        pop af
        push af
        push hl
        ld l,a                      ; V_GFX = 33656 + A * 32
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,33656
        add hl,de
        ld (V_GFX),hl
        call chksum
        nextreg 0x51,TPAGE
        call orient
        nextreg 0x51,0xFF
        ret

chksum: ld de,0                     ; DE = check of B bytes at HL: s = rotl16(s) + byte
.l:     ex de,hl
        add hl,hl
        jr nc,.n
        inc l
.n:     ex de,hl
        ld a,(hl)
        add a,e
        ld e,a
        jr nc,.c
        inc d
.c:     inc hl
        djnz .l
        ret

orient: ld hl,(V_ENT)               ; table entry vs check DE -> V_PG, V_OFF, V_ORI; carry = no match
        ld a,(hl)
        ld (V_PG),a
        inc hl
        ld a,(hl)
        ld (V_OFF),a
        inc hl
        ld a,(hl)
        ld (V_OFF+1),a
        inc hl
        ld a,(hl)
        cp e
        jr nz,.m
        inc hl
        ld a,(hl)
        cp d
        jr nz,.m1
        xor a
        ld (V_ORI),a
        ret
.m:     inc hl
.m1:    inc hl
        ld a,(hl)
        cp e
        jr nz,.no
        inc hl
        ld a,(hl)
        cp d
        jr nz,.no
        ld a,1
        ld (V_ORI),a
        or a
        ret
.no:    scf
        ret

ccol:   ld a,(V_Y)                  ; V_COL = ink of the attribute-buffer cell under the centre
        add a,8
        and 248
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(V_X)
        add a,8
        rrca
        rrca
        rrca
        and 31
        ld e,a
        ld d,0xFB
        add hl,de
        ld l,(hl)
        ld h,high INKTAB
        ld a,(hl)
        ld (V_COL),a
        ret

bcend:  ld a,(V_Y)                  ; B/C end state: HL = 0x6B00+(y-64)*32+x/8+2+16*32, BC 0, DE 34
        sub 64
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call xcol
        add a,2
        ld e,a
        ld d,107+2
        add hl,de
        ld bc,0
        ld de,34
        ret

stage:  ld a,(V_N)                  ; PL[N] = this plot; N += 1
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,PL
        add hl,de
        ld a,(V_PG)
        ld (hl),a
        inc hl
        ld a,(V_OFF)
        ld (hl),a
        inc hl
        ld a,(V_OFF+1)
        ld (hl),a
        inc hl
        ld a,(V_X)
        ld (hl),a
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,(V_H)
        ld (hl),a
        inc hl
        ld a,(V_COL)
        ld (hl),a
        inc hl
        push hl
        ld hl,(V_SP)                ; the plotter's caller
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_CALL),de
        call joined
        pop hl
        ld b,a
        ld a,(V_ORI)
        or b
        ld (hl),a
        inc hl
        ld a,(V_KIND)
        ld (hl),a
        inc hl
        ld de,(V_CALL)
        ld (hl),e
        inc hl
        ld (hl),d
        ld a,(V_N)
        inc a
        ld (V_N),a
        ret

joined: push ix                     ; A = 2 if this plot joins the one before (same kind B or C,
        call .t                     ; another caller, 16x16 boxes at most 1 pixel apart), else 0
        pop ix                      ; (IX is the game's: kept)
        ret
.t:     ld a,(V_KIND)
        or a
        jr z,.no
        ld a,(V_N)
        or a
        jr z,.no
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,PL+3
        add hl,de
        push hl
        pop ix
        ld a,(V_KIND)
        cp (ix+5)
        jr nz,.no
        ld a,(V_CALL)
        cp (ix+6)
        jr nz,.d
        ld a,(V_CALL+1)
        cp (ix+7)
        jr z,.no
.d:     ld a,(V_X)
        sub (ix+0)
        jr nc,.dx
        neg
.dx:    cp 18
        jr nc,.no
        ld a,(V_Y)
        sub (ix+1)
        jr nc,.dy
        neg
.dy:    cp 18
        jr nc,.no
        ld a,2
        ret
.no:    xor a
        ret

; ---- helpers (commit) ----
clearbox:
        ld hl,(V_BOX)               ; fill every box drawn into this buffer last time with 0
        ld a,(hl)
        or a
        ret z
        ld b,a
        inc hl
.bx:    push bc
        ld c,(hl)                   ; x0
        inc hl
        ld e,(hl)                   ; y0
        inc hl
        ld a,(hl)                   ; x1
        sub c
        inc a
        ld (V_CNT),a
        inc hl
        ld d,(hl)                   ; y1
        inc hl
        push hl
.row:   ld a,e
        call l2row                  ; HL = Layer 2 address of (0, E), page mapped at slot 2
        ld l,c
        ld a,(V_CNT)
        ld b,a
        xor a
.f:     ld (hl),a
        inc l
        djnz .f
        ld a,e
        cp d
        jr z,.nb
        inc e
        jr .row
.nb:    pop hl
        pop bc
        djnz .bx
        ret

l2row:  push af                     ; A = line -> page V_L2P + A/32 at slot 2, HL = 0x4000 + (A & 31)*256
        rlca
        rlca
        rlca
        and 7
        ld h,a
        ld a,(V_L2P)
        add a,h
        nextreg 0x52,a
        pop af
        and 31
        or 0x40
        ld h,a
        ld l,0
        ret

drawall:
        ld ix,PL
        ld a,(V_N)
        or a
        ret z
        ld c,a                      ; C = plots left
.g:     push ix                     ; group: this plot and the joined ones after it
        pop iy
        ld b,1
.j:     ld a,b
        cp c
        jr z,.ge
        ld de,16
        add iy,de
        bit 1,(iy+7)
        jr z,.ge
        inc b
        jr .j
.ge:    push bc
        ld a,b
        dec a
        jr nz,.two
        ld iyl,3                    ; one plot: every pixel in one pass
        call draw
        ld de,16
        add ix,de
        jr .nx
.two:   push ix                     ; joined: outlines of the whole group first, then the inks
        ld iyl,1
.p1:    push bc
        call draw
        ld de,16
        add ix,de
        pop bc
        djnz .p1
        pop ix
        pop bc
        push bc
        ld iyl,2
.p2:    push bc
        call draw
        ld de,16
        add ix,de
        pop bc
        djnz .p2
.nx:    pop bc
        ld a,c
        sub b
        ld c,a
        jr nz,.g
        ret

; draw the plot at IX into the Layer 2 buffer (pages V_L2P..), pass mask IYL (1 non-ink, 2 ink),
; and record its box; canvas (IX+0 page, IX+1/2 offset), 18 columns x (IX+5) rows from (x-1, y-1)
draw:   ld a,(ix+0)
        nextreg 0x51,a
        ld l,(ix+1)
        ld h,(ix+2)
        ld de,0x2000
        add hl,de
        ld (V_RB),hl
        xor a                       ; columns: from 1 if x = 0, up to screen column 255
        ld (V_CS),a
        ld b,18
        ld a,(ix+3)
        or a
        jr nz,.c0
        ld a,1
        ld (V_CS),a
        dec b
.c0:    ld a,(ix+3)
        cp 240
        jr c,.c1
        neg                         ; x >= 240: 257 - x columns left of the edge
        add a,1
        ld e,a                      ; (256 - x) + 1
        ld a,18
        sub e
        ld e,a
        ld a,b
        sub e
        ld b,a
.c1:    ld a,b
        ld (V_CNT),a
        ld a,0x23                   ; inc hl / dec hl: canvas direction
        bit 0,(ix+7)
        jr z,.dr
        ld a,0x2B
.dr:    ld (.dir),a
        ld a,(ix+4)                 ; first line y - 1
        dec a
        ld (V_ROW),a
        ld a,(ix+5)
        ld b,a
.r:     push bc
        ld a,(V_ROW)
        cp 64
        jr c,.skip
        cp 192
        jr nc,.skip
        call l2row
        ld a,(ix+3)
        dec a
        ld e,a
        ld a,(V_CS)
        add a,e
        ld l,a
        ex de,hl                    ; DE = Layer 2 address
        ld hl,(V_RB)
        ld a,(V_CS)
        bit 0,(ix+7)
        jr z,.fw
        neg
        add a,17
.fw:    add a,l
        ld l,a
        jr nc,.fw2
        inc h
.fw2:   ld a,(V_CNT)
        ld b,a
        ld c,(ix+6)
.px:    ld a,(hl)
        or a
        jr z,.sk
        bit 5,a
        jr z,.ni
        ld a,iyl
        and 2
        jr z,.sk
        jr .put
.ni:    ld a,iyl
        and 1
        jr z,.sk
.put:   ld a,(hl)
        bit 4,a
        jr z,.fix
        ld a,c
        jr .w
.fix:   and 0x0F
.w:     ld (de),a
.sk:    inc e
.dir:   inc hl
        djnz .px
.skip:  ld hl,(V_RB)
        ld de,18
        add hl,de
        ld (V_RB),hl
        ld hl,V_ROW
        inc (hl)
        pop bc
        djnz .r
        ld a,iyl                    ; the box once per plot (joined groups draw twice)
        and 2
        ret z
        ; box: x0 = max(0, x-1), y0 = max(64, y-1), x1 = min(255, x+16), y1 = min(191, y + rows - 2)
        ld hl,(V_BOX)
        ld a,(hl)
        inc (hl)
        add a,a
        add a,a
        inc a
        ld e,a
        ld d,0
        add hl,de
        ld a,(ix+3)
        or a
        jr z,.x0
        dec a
.x0:    ld (hl),a
        inc hl
        ld a,(ix+4)
        dec a
        cp 64
        jr nc,.y0
        ld a,64
.y0:    ld (hl),a
        inc hl
        ld a,(ix+3)
        cp 240
        ld a,255
        jr nc,.x1
        ld a,(ix+3)
        add a,16
.x1:    ld (hl),a
        inc hl
        ld a,(ix+4)
        add a,(ix+5)
        jr c,.y1c
        sub 2
        cp 192
        jr c,.y1
.y1c:   ld a,191
.y1:    ld (hl),a
        ret
code_end:

; --- setup routine (stub bank, 0xD000): Layer 2 palette and buffers, sprites off ----
        ORG 0xD000
setup:  nextreg 0x43,0x10           ; Layer 2 first palette, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x14,0xE3           ; index 0 = 0xE3 = transparent
        nextreg 0x70,0              ; 256x192
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1              ; Layer 2 clip window: full
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x12,L2BANK0
        nextreg 0x13,L2BANK1
        nextreg 0x15,0x00           ; sprites off; sprites, Layer 2, ULA order
        nextreg 0x69,0x80           ; Layer 2 on (both buffers empty)
        ret
pal:                                ; 16 palette bytes appended by Python

        SAVEBIN "w2_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "w2_page.bin",0x0100,code_end-0x0100
        SAVEBIN "w2_setup.bin",0xD000,pal-0xD000
