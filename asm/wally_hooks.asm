; Everyone's a Wally (Mikro-Gen, 48K code in a 128K snapshot) - hardware sprites for the five gang
; members (plotter A 45286, 16x32 masked) and the masked 16x16 objects/enemies (plotter B 43168).
; Plotter C 43069 (OR-only 16x16 objects) stays on the ULA; its hook only clears the "last B" flag.
; The game rebuilds a back buffer (0x6B00, attrs 0xFC00) every render, plots the figures into it
; and copies it to the screen (47611); the commit hook sits after the pixel copy (47637).
; Entry/exit stubs live in alt ROM image 1 at 0x386E; hook bodies, state and tables live in Next
; RAM page PAGE_S, mapped at MMU slot 0 only while a hook runs. Interrupts are disabled at every
; hook site (verified in the RZX; plotter C executes its own DI first).
;
; Patch sites (original bytes verified by wally.py):
;   45286  D9 FD 5E   EXX / LD E,(IY+35)        -> JP e_a   (plotter A)
;   43168  D9 F5 ED   EXX / PUSH AF / LD (nn),SP -> JP e_b   (plotter B)
;   43069  F3 D9 F5   DI / EXX / PUSH AF         -> JP e_c   (plotter C)
;   61329  F5 D9 3A   PUSH AF / EXX / LD A,(nn)  -> JP e_p   (attribute painter after B/C)
;   47637  01 00 02   LD BC,512                  -> JP e_cm  (commit, after the pixel copy)
; A converted plot leaves every register, the game stack and all RAM exactly as the original,
; except the back buffer / attribute buffer cells it would have drawn (never read by game logic).

        DEVICE ZXSPECTRUMNEXT

PAGE_S  EQU 26
MAXS    EQU 32                  ; sprites per render (patterns PAR+0..31, PAR = 0 or 32)
V_N     EQU 0x0000              ; sprites this render
V_PREV  EQU 0x0001              ; sprites shown by the last commit
V_PAR   EQU 0x0002              ; pattern bank for this render (0 / 32)
V_LAST  EQU 0x0003              ; 1 + sprite index of a converted B plot awaiting 61329 (0 = none); 0x0004 spare
V_SP    EQU 0x0006
V_X     EQU 0x0008
V_Y     EQU 0x0009
STK     EQU 0x0100              ; hook stack top (grows down into 0x00C0-0x00FF)
SPRTAB  EQU 0x1800              ; 5 attribute bytes per sprite
NIBTAB  EQU 0x1A00              ; (G nibble << 4 | M nibble) -> 2 bytes of 4-bit pixels
PALMAP  EQU 0x1C00              ; attribute byte -> palette offset << 4

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
rom_end:

        ORG 0x0100
; ---- plotter A: gang member, IY = descriptor (frame +0, x +5, y +10, attr +30, gfx +35/+40) ----
s_a:    ld (V_SP),sp
        ld sp,STK
        push af
        exx                         ; the game's alternate set (all overwritten by the plotter)
        ld a,(V_N)
        cp MAXS-1
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
        and 7                       ; the plotter's self-modified operands
        ld (45449),a
        inc a
        ld (45353),a
        ld (45381),a
        call xcol
        ld (45435),a
        ld hl,(V_SP)
        ld (43067),hl
        xor a
        ld (V_LAST),a
        nextreg 0x07,3
        call setpat
        ld l,0
        ld h,(iy+0)
        srl h
        rr l
        ld e,(iy+35)
        ld d,(iy+40)
        add hl,de
        ld b,32
        call conv
        nextreg 0x07,0
        ld l,(iy+30)
        ld h,high PALMAP
        ld c,(hl)
        ld a,(V_Y)
        ld e,a
        call addspr
        ld a,(V_Y)
        add a,16
        ld e,a
        call addspr
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
        ld sp,(V_SP)
        jp x_ret
.pass:  exx
        pop af
        ld sp,(V_SP)
        jp x_a

; ---- plotter B: masked 16x16, A = frame (gfx 33656 + A*32), position (43064/43065) ----
s_b:    ld (V_SP),sp
        ld sp,STK
        push af
        exx
        ld a,(V_N)
        cp MAXS
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
        nextreg 0x07,3
        call setpat
        pop af
        push af
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,33656
        add hl,de
        ld b,16
        call conv
        nextreg 0x07,0
        ld a,(V_Y)                  ; colour: attribute buffer cell under the centre
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
        ld h,high PALMAP
        ld c,(hl)
        ld a,(V_N)
        inc a
        ld (V_LAST),a
        ld a,(V_Y)
        ld e,a
        call addspr
        ld a,(V_Y)                  ; end state: HL = 0x6B00+(y-64)*32+x/8+2+16*32
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
        pop af
        exx
        ld sp,(V_SP)
        jp x_ret
.pass:  exx
        pop af
        ld sp,(V_SP)
        jp x_b

; ---- plotter C (after its DI): stays on the ULA; forget a pending B ----
s_c:    exx                         ; HL' is overwritten by the plotter (LD L,A / LD H,0)
        ld hl,0
        ld (V_LAST),hl
        jp x_c                      ; (the original EXX is done; x_c does PUSH AF)

; ---- 61329: attribute painter. After a converted B it only colours that sprite ----
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
        add a,a
        add a,a
        add a,l
        add a,2
        ld l,a
        ld h,high SPRTAB
        ld a,(62063)
        ld e,a
        ld d,high PALMAP
        ld a,(de)
        ld e,a
        ld a,(hl)
        and 0x0F
        or e
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

; ---- 47637 (pixel copy done): show this render's sprites, hide the rest ----
s_cm:   ld (V_SP),sp
        ld sp,STK
        push af
        push hl
        push de
        ld a,(V_N)
        ld d,a
        ld e,0
        ld hl,SPRTAB
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
        ld (V_N),a
        ld (V_LAST),a
        ld a,(V_PAR)
        xor 32
        ld (V_PAR),a
        pop de
        pop hl
        pop af
        ld sp,(V_SP)
        jp x_cm

; ---- helpers ----
xcol:   ld a,(V_X)                  ; A = x / 8
        rrca
        rrca
        rrca
        and 31
        ret

setpat: ld a,(V_PAR)                ; pattern upload index = PAR + N (4-bit pattern)
        ld b,a
        ld a,(V_N)
        add a,b
        srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ret

addspr: ld a,(V_N)                  ; SPRTAB[N] = sprite at (V_X, E), palette C; N += 1
        ld l,a
        add a,a
        add a,a
        add a,l
        ld l,a
        ld h,high SPRTAB
        ld a,(V_X)
        add a,32
        ld (hl),a
        inc hl
        ld a,e
        add a,32
        ld (hl),a
        inc hl
        ld a,(V_X)
        cp 224
        ld a,c
        jr c,.n8
        or 1
.n8:    ld (hl),a
        inc hl
        ld a,(V_PAR)
        ld b,a
        ld a,(V_N)
        add a,b
        ld b,a
        srl a
        or 0xC0
        ld (hl),a
        inc hl
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a
        ld a,(V_N)
        inc a
        ld (V_N),a
        ret

conv:   ld e,(hl)                   ; HL = rows of (mask L, mask R, gfx L, gfx R), B rows
        inc hl
        ld c,(hl)
        inc hl
        ld a,(hl)
        inc hl
        call nibp
        ld a,(hl)
        inc hl
        ld e,c
        call nibp
        djnz conv
        ret

nibp:   push hl                     ; A = gfx byte, E = mask byte -> 4 bytes of 4-bit pixels
        ld d,a
        ld a,e
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld l,a
        ld a,d
        and 0xF0
        or l
        ld l,a
        ld h,high NIBTAB
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        ld a,d
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld l,a
        ld a,e
        and 0x0F
        or l
        ld l,a
        ld h,high NIBTAB
        ld a,(hl)
        out (0x5B),a
        inc h
        ld a,(hl)
        out (0x5B),a
        pop hl
        ret
code_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, hide all, clip, sprites on ----
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,64
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
pal:                                ; 256 palette bytes appended by Python

        SAVEBIN "wa_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "wa_page.bin",0x0100,code_end-0x0100
        SAVEBIN "wa_setup.bin",0xD000,pal-0xD000
