; Smash TV (Probe / Ocean 1991, 48K) - every figure of the four masked plotters becomes 4-bit
; hardware sprites (24x24 -> 2x2 sprites, 8x8 -> 1 sprite); arena, HUD and text stay on the ULA.
;
; The game rebuilds a back buffer every game frame (restore 59506: grid; pixels 0xEC00-0xFFFF,
; attrs 0xE980-0xEBFF), plots the figures into it and copies it to the screen (blit 53293).
; Interrupts are OFF at every hook site (the game runs DI in play; checked over the whole RZX).
;
; Method: the game's OWN plotter runs unchanged, but with MMU slot 7 (0xE000-0xFFFF) mapped to
; Next RAM page PG, whose 0xE980-0xFFFF is a scratch copy of the back buffer: every register,
; flag and self-modified operand comes out as the original's, the real buffer keeps the plain
; background. The restore runs twice (real buffer, then scratch), so the scratch reads what the
; original buffer holds. 0xE000-0xE97F of PG holds the hook state, tables and hook stack, and at
; 0xE872-0xE8FB a copy of the restore routine itself (it lives in slot 7: the scratch run executes
; the copy; its self-modified operand 59641 is the only byte that changes).
; Hook code lives in alt ROM image 1 at 0x2100-; 0x2000-0x20FF stays ROM (clipped plot rows read
; it), 0x386E stays 0xFF (the game's 48K ROM check at 59842), the font 0x3D00- stays ROM.
;
; Patch sites (original bytes verified by smashtv.py):
;   29704 ED 73 4E  LD (29774),SP  -> JP e_s8     8x8 masked plotter
;   29777 ED 73 9F  LD (29855),SP  -> JP e_s8m    8x8 mirrored
;   29858 ED 73 13  LD (29971),SP  -> JP e_b24    24x24 masked plotter
;   29974 ED 73 99  LD (30105),SP  -> JP e_b24m   24x24 mirrored
;   59506 ED 73 F9  LD (59641),SP  -> JP e_rs     background restore (runs twice)
;   53861 EA 3E D0  JP PE,53310    -> JP e_bl     blit loop end: commit at the fall-through
;   53868 AF 32 DC  XOR A / LD (24284),A -> JP e_end   game start / after game over: hide all

        DEVICE ZXSPECTRUMNEXT

PG      EQU 26                  ; hook page, MMU slot 7 while a hook runs
GPG     EQU 1                   ; the game's page at slot 7 (48K: bank 0 upper half)
MAXSPR  EQU 128
NGRP    EQU 32                  ; pattern cache: 32 groups of four 4-bit patterns

; ---- page PG at 0xE000 ----
V_N     EQU 0xE000              ; sprites recorded since the last commit
V_PREV  EQU 0xE001              ; sprites shown by the last commit
V_RR    EQU 0xE002              ; cache round-robin start
V_K     EQU 0xE003              ; kind: bit 1 = 8x8, bit 0 = mirrored
V_SP    EQU 0xE004              ; game SP at hook entry
V_SV    EQU 0xE006              ; the two game-stack bytes under SP (the body's CALL uses them)
V_T     EQU 0xE008
V_L     EQU 0xE00A
V_C     EQU 0xE00B
V_B     EQU 0xE00C
V_G     EQU 0xE00D
V_P     EQU 0xE00E              ; graphic pointer
V_CNV   EQU 0xE010
V_CNT   EQU 0xE011
V_E0    EQU 0xE012
V_E1    EQU 0xE013
V_X     EQU 0xE014              ; sprite X (16 bits)
V_Y     EQU 0xE016
V_PAT   EQU 0xE017
V_A2    EQU 0xE018              ; attr2 extra bits (mirror)
KEY     EQU 0xE020              ; 12 bytes: graphic pointer, size (0 = 24x24, 1 = 8x8), attribute bytes
V_CC    EQU 0xE030              ; 9 colours * 4 (pixel table bases) of the figure's cells
CACHE   EQU 0xE040              ; 32 x 16: +0 flags (bit 0 used since the commit, bit 1 on show), +1 key
SPRTAB  EQU 0xE240              ; 128 x 5 sprite attribute bytes
ATTR4   EQU 0xE500              ; attribute byte -> colour index * 4 (attr 0 = white)
PT      EQU 0xE600              ; colour*4 + pixel pair -> 4-bit pattern byte
HSTK    EQU 0xE980              ; hook stack top (grows down; must stay above 0xE8FC)
RSCODE  EQU 0xE872              ; copy of the restore routine 59506-59643 (filled by Python)

        ORG 0x2100

; ---- trampolines: the displaced instruction, then the plotter body ----
t_s8:   ld (29774),sp
        jp 29708
t_s8m:  ld (29855),sp
        jp 29781
t_b24:  ld (29971),sp
        jp 29862
t_b24m: ld (30105),sp
        jp 29978
t_rs:   ld (59641),sp
        jp 59510

; ---- one plot hook per plotter ----
        MACRO PLOTHOOK kind, tramp, oper
        nextreg 0x07,3              ; hook work at 28 MHz; the game's own bodies at 3.5 MHz
        nextreg 0x57,PG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld a,kind
        call decide                 ; L, C, B = the plotter's inputs
        ld (V_CNV),a
        ld hl,(V_SP)
        dec hl
        ld d,(hl)
        dec hl
        ld e,(hl)
        ld (V_SV),de
        pop hl
        pop de
        pop bc
        ld a,(V_CNV)
        or a
        jr z,.pass
        pop af
        ld sp,(V_SP)
        nextreg 0x07,0
        call tramp                  ; converted: into the scratch only, 3.5 MHz (original cost)
        nextreg 0x07,3
        jp .done
.pass:  pop af                      ; stays on the ULA: real buffer, then the scratch again
        push af
        push bc
        push de
        push hl
        exx
        push bc
        push de
        push hl
        exx
        ex af,af'
        push af
        ex af,af'
        ld sp,(V_SP)
        nextreg 0x57,GPG
        nextreg 0x07,0
        call tramp
        nextreg 0x07,3
        nextreg 0x57,PG
        ld sp,HSTK-16
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        call tramp
.done:  ld (oper),sp                ; the operand as the original left it
        ld (V_T),hl
        ld hl,(V_SV)                ; give the game stack its two bytes back
        push hl
        pop hl
        ld hl,(V_T)
        nextreg 0x57,GPG
        nextreg 0x07,0
        ret
        ENDM

e_s8:   PLOTHOOK 2, t_s8, 29774
e_s8m:  PLOTHOOK 3, t_s8m, 29855
e_b24:  PLOTHOOK 0, t_b24, 29971
e_b24m: PLOTHOOK 1, t_b24m, 30105

; ---- background restore: real buffer (3.5 MHz), then the scratch copy (28 MHz) ----
e_rs:   nextreg 0x07,3
        nextreg 0x57,PG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push hl
        push de
        ld hl,(V_SP)
        dec hl
        ld d,(hl)
        dec hl
        ld e,(hl)
        ld (V_SV),de
        pop de
        pop hl
        pop af
        push af
        push bc
        push de
        push hl
        exx
        push bc
        push de
        push hl
        exx
        ex af,af'
        push af
        ex af,af'
        ld sp,(V_SP)
        nextreg 0x57,GPG
        nextreg 0x07,0
        call t_rs                   ; real buffer at 3.5 MHz (original cost)
        nextreg 0x07,3
        nextreg 0x57,PG
        ld sp,HSTK-16
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        call t_rs                   ; the scratch copy (28 MHz)
        ld (V_T),hl
        ld hl,(V_SV)
        push hl
        pop hl
        ld hl,(V_T)
        nextreg 0x57,GPG
        ld (59641),sp               ; the game's own copy of the operand (slot 7 = game page)
        nextreg 0x07,0
        ret

; ---- blit loop end: JP PE as the original; at the fall-through show the recorded sprites ----
e_bl:   jp pe,53310
        nextreg 0x07,3
        nextreg 0x57,PG
        ld (V_SP),sp                ; SP = the blit's row-table pointer: never push on it
        ld sp,HSTK
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
        nextreg 0x57,GPG
        nextreg 0x07,0
        jp 53864

; ---- 53868 (game start, after game over): hide every sprite ----
e_end:  nextreg 0x07,3
        nextreg 0x57,PG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call hideall
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x57,GPG
        nextreg 0x07,0
        xor a
        ld (24284),a
        jp 53872

; =====================================================================================
; decide: A = kind, L = frame, C = column, B = line. -> A = 1 converted (sprites recorded, or
; nothing visible), 0 = the plot stays on the ULA (column >= 30, sprites or cache full).
decide: ld (V_K),a
        ld a,l
        ld (V_L),a
        ld a,c
        ld (V_C),a
        ld a,b
        ld (V_B),a
        ld a,c
        cp 30
        jr nc,.pass
        ld a,(V_K)
        and 2
        jr nz,.small
        ld a,b
        cp 25
        jr c,.inv
        cp 208
        jr nc,.inv
        ld a,(V_N)
        cp MAXSPR-3
        jr nc,.pass
        call key24
        jr .look
.small: ld a,b
        cp 41
        jr c,.inv
        cp 208
        jr nc,.inv
        ld a,(V_N)
        cp MAXSPR
        jr nc,.pass
        call key8
.look:  call lookup
        jr c,.pass
        call emit
.inv:   ld a,1
        ret
.pass:  xor a
        ret

; key24 / key8: KEY = size, pointer, attribute bytes (24x24: 9, 8x8: 1, rest 0); V_CC = colours
key24:  ld a,(V_L)
        ld l,a
        ld h,0
        add hl,hl
        ld de,0x5B00
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_P),de
        ld hl,KEY
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),0
        inc hl
        ex de,hl                    ; HL = graphic, DE = KEY+3
        ld bc,72
        add hl,bc
        ld b,9
        ld c,low V_CC
.a:     ld a,(hl)
        ld (de),a
        push hl
        ld l,a
        ld h,high ATTR4
        ld a,(hl)
        ld l,c
        ld h,high V_CC
        ld (hl),a
        pop hl
        inc hl
        inc de
        inc c
        djnz .a
        ret

key8:   ld a,(V_L)
        ld l,a
        ld h,0
        add hl,hl
        ld de,0x5C00
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_P),de
        ld hl,KEY
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),1
        inc hl
        ex de,hl
        ld bc,8
        add hl,bc
        ld a,(hl)
        ld (de),a
        ld l,a
        ld h,high ATTR4
        ld a,(hl)
        ld (V_CC),a
        ex de,hl
        ld b,8
.z:     inc hl
        ld (hl),0
        djnz .z
        ret

; lookup: KEY in the cache -> A = group, carry clear (images uploaded on a miss); carry = no
; free group (every group used since the commit or on show)
lookup: ld hl,CACHE+1
        ld b,0
.e:     push hl
        ld de,KEY
        ld c,12
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.ne
        inc hl
        inc de
        dec c
        jr nz,.cmp
        pop hl
        ld a,b
        jr .use
.ne:    pop hl
        ld de,16
        add hl,de
        inc b
        ld a,b
        cp NGRP
        jr nz,.e
        ld a,(V_RR)                 ; miss: a free group (flags 0), round robin
        ld c,NGRP
.f:     and NGRP-1
        ld b,a
        call gaddr
        ld a,(hl)
        or a
        jr z,.free
        ld a,b
        inc a
        dec c
        jr nz,.f
        scf
        ret
.free:  ld a,b
        inc a
        ld (V_RR),a
        inc hl                      ; copy KEY into the entry
        ex de,hl
        ld hl,KEY
        ld bc,12
        ldir
        ld a,(V_RR)
        dec a
        and NGRP-1
        ld (V_G),a
        ld a,(KEY+2)
        or a
        jr nz,.up8
        call up24
        jr .new
.up8:   call up8
.new:   ld a,(V_G)
.use:   ld (V_G),a
        ld b,a
        call gaddr
        set 0,(hl)
        ld a,(V_G)
        or a                        ; carry clear
        ret

gaddr:  ld l,b                      ; HL = CACHE + 16*B
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CACHE
        add hl,de
        ret

; ---- pattern upload: group G = 4-bit patterns 4G..4G+3 (TL, TR, BL, BR) = 256-byte slots 2G, 2G+1
selslot:ld a,(V_G)
        add a,a
        ld bc,0x303B
        out (c),a
        ret

up24:   call selslot
        ld hl,(V_P)
        ld b,h
        ld c,l
        ld a,(V_CC+0)               ; TL: rows 0-15, bytes 0-1
        ld (V_E0),a
        ld a,(V_CC+1)
        ld (V_E1),a
        ld a,8
        call rows2
        ld a,(V_CC+3)
        ld (V_E0),a
        ld a,(V_CC+4)
        ld (V_E1),a
        ld a,8
        call rows2
        ld hl,(V_P)                 ; TR: rows 0-15, byte 2
        inc hl
        inc hl
        ld b,h
        ld c,l
        ld a,(V_CC+2)
        ld (V_E0),a
        ld a,8
        call rows1
        ld a,(V_CC+5)
        ld (V_E0),a
        ld a,8
        call rows1
        ld hl,(V_P)                 ; BL: rows 16-23, bytes 0-1, then 8 empty rows
        ld de,48
        add hl,de
        ld b,h
        ld c,l
        ld a,(V_CC+6)
        ld (V_E0),a
        ld a,(V_CC+7)
        ld (V_E1),a
        ld a,8
        call rows2
        ld a,64
        call zeros
        ld hl,(V_P)                 ; BR: rows 16-23, byte 2, then 8 empty rows
        ld de,50
        add hl,de
        ld b,h
        ld c,l
        ld a,(V_CC+8)
        ld (V_E0),a
        ld a,8
        call rows1
        ld a,64
        jp zeros

up8:    call selslot                ; TL only: rows 0-7, then 8 empty rows
        ld hl,(V_P)
        ld b,h
        ld c,l
        ld a,(V_CC)
        ld (V_E0),a
        ld a,8
        ld (V_CNT),a
.r:     ld a,(V_E0)
        ld e,a
        ld a,(bc)
        call nib
        inc bc
        ld a,4
        call zeros
        ld a,(V_CNT)
        dec a
        ld (V_CNT),a
        jr nz,.r
        ld a,64
        jp zeros

rows2:  ld (V_CNT),a                ; A rows of 2 graphic bytes (stride 3) -> 8 pattern bytes each
.r:     ld a,(V_E0)
        ld e,a
        ld a,(bc)
        call nib
        inc bc
        ld a,(V_E1)
        ld e,a
        ld a,(bc)
        call nib
        inc bc
        inc bc
        ld a,(V_CNT)
        dec a
        ld (V_CNT),a
        jr nz,.r
        ret

rows1:  ld (V_CNT),a                ; A rows of 1 graphic byte (stride 3) -> 4 bytes + 4 empty
.r:     ld a,(V_E0)
        ld e,a
        ld a,(bc)
        call nib
        inc bc
        inc bc
        inc bc
        ld a,4
        call zeros
        ld a,(V_CNT)
        dec a
        ld (V_CNT),a
        jr nz,.r
        ret

zeros:  ld d,a
        xor a
.z:     out (0x5B),a
        dec d
        jr nz,.z
        ret

nib:    ld d,a                      ; A = graphic byte, E = colour*4 -> 4 pattern bytes
        ld h,high PT
        rlca
        rlca
        and 3
        or e
        ld l,a
        ld a,(hl)
        out (0x5B),a
        ld a,d
        rrca
        rrca
        rrca
        rrca
        and 3
        or e
        ld l,a
        ld a,(hl)
        out (0x5B),a
        ld a,d
        rrca
        rrca
        and 3
        or e
        ld l,a
        ld a,(hl)
        out (0x5B),a
        ld a,d
        and 3
        or e
        ld l,a
        ld a,(hl)
        out (0x5B),a
        ret

; ---- emit: append this figure's sprites (plot order = sprite order: later figures on top) ----
emit:   ld a,(V_B)
        add a,8                     ; sprite Y = 32 + (line - 24)
        ld (V_Y),a
        ld a,(V_C)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_X),hl                 ; 32 + 8 * column
        ld a,(V_G)
        add a,a
        add a,a
        ld (V_PAT),a
        ld a,(V_K)
        and 1
        rlca
        rlca
        rlca
        ld (V_A2),a                 ; X-mirror bit
        ld a,(V_K)
        cp 2
        jr nc,.small
        rrca
        jr c,.mir
        ld de,0                     ; TL, TR, BL, BR
        call spr
        ld de,16
        call nxt
        call spr
        ld a,(V_Y)
        add a,16
        ld (V_Y),a
        ld de,0
        call nxt
        call spr
        ld de,16
        call nxt
        jp spr
.mir:   ld de,8                     ; mirrored: TL at +8, TR at -8
        call spr
        ld de,0xFFF8
        call nxt
        call spr
        ld a,(V_Y)
        add a,16
        ld (V_Y),a
        ld de,8
        call nxt
        call spr
        ld de,0xFFF8
        call nxt
        jp spr
.small: rrca
        ld de,0
        jp nc,spr
        ld de,0xFFF8
        jp spr

nxt:    ld a,(V_PAT)
        inc a
        ld (V_PAT),a
        ret

spr:    ld a,(V_N)                  ; SPRTAB[N] = (V_X + DE, V_Y, pattern V_PAT, V_A2); N += 1
        ld l,a
        ld h,0
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc
        ld bc,SPRTAB
        add hl,bc
        push hl
        ld hl,(V_X)
        add hl,de
        ex de,hl
        pop hl
        ld (hl),e
        inc hl
        ld a,(V_Y)
        ld (hl),a
        inc hl
        ld a,(V_A2)
        or d
        ld (hl),a
        inc hl
        ld a,(V_PAT)
        ld c,a
        srl a
        or 0xC0
        ld (hl),a
        inc hl
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a
        ld a,(V_N)
        inc a
        ld (V_N),a
        ret

; ---- commit: show sprites 0..N-1, hide N..PREV-1; age the cache flags ----
commit: ld a,(V_N)
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
        ld hl,CACHE
        ld de,16
        ld b,NGRP
.f:     ld a,(hl)
        and 1
        add a,a
        ld (hl),a
        add hl,de
        djnz .f
        ret

hideall:xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp MAXSPR
        jr nz,.h
        xor a
        ld (V_N),a
        ld (V_PREV),a
        ld hl,CACHE
        ld de,16
        ld b,NGRP
.f:     ld (hl),a
        add hl,de
        djnz .f
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
        nextreg 0x1C,2              ; sprite clip window = the play area
        nextreg 0x19,16
        nextreg 0x19,239
        nextreg 0x19,24
        nextreg 0x19,183
        nextreg 0x15,0x01           ; sprites on, SLU, higher number on top
        ret
pal:                                ; 16 palette bytes appended by Python

; --- front end (in the start snapshot at 0x5D00; write-first game RAM 0x5C6C-0x5D6C) ----------
; The screen shows the trainer prompt "DO YOU WANT TO BE INVULNERABLE ?" in row 23 (as the BASIC
; loader prints it). Y: POKE 33465,201 (as line 50); Y or N: clear row 23 (line 80), set every
; register to the loader's state at its RANDOMIZE USR 59776, JP 59776 (whose first instruction is
; DI). Keys as INKEY$ = "y"/"Y"/"n"/"N": Y or N with or without CAPS SHIFT, not with SYMBOL SHIFT.
        ORG 0x5D00
front:  di
.k:     ld bc,0x7FFE
        in a,(c)
        bit 1,a                     ; SYMBOL SHIFT held: no y/n
        jr z,.k
        bit 3,a
        jr z,.go                    ; N
        ld b,0xDF
        in a,(c)
        bit 4,a
        jr nz,.k                    ; not Y
        ld a,201
        ld (33465),a
.go:    ld hl,0x50E0
        ld d,8
.r:     ld b,32
        ld e,l
.c:     ld (hl),0
        inc l
        djnz .c
        ld l,e
        inc h
        dec d
        jr nz,.r
        ld hl,0x5AE0
        ld b,32
.a:     ld (hl),0
        inc l
        djnz .a
        ld a,63
        ld i,a
        ld sp,f_af2
        pop af
        ex af,af'
        ld bc,5665
        ld de,13979
        ld hl,10072
        exx
        ld sp,f_af
        pop af
        ld bc,59776
        ld de,24291
        ld hl,11563
        ld ix,978
        ld iy,23610
        ld sp,24976
        jp 59776
f_af:   dw 0x8054
f_af2:  dw 0x0044
front_end:

        SAVEBIN "st_rom.bin",0x2100,rom_end-0x2100
        SAVEBIN "st_setup.bin",0xD000,pal-0xD000
        SAVEBIN "st_front.bin",0x5D00,front_end-0x5D00
