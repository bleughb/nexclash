; Chuckie Egg (A&F, 1983, 48K) - hardware sprites for the player, the duck and the hens.
; All hooks are stateless and live in alt ROM image 1 at 0x386E (read-only, survives every
; paging write). Interrupts are ENABLED at every hook site (IM2 handler in RAM): the hooks use
; only the game stack (pushes below SP) and NEXTREG, which an interrupt cannot disturb.
;
; Patch sites (original bytes checked by chuckie.py):
;   39500  F5 C5 D5    PUSH AF/BC/DE (player + duck plotter)   -> JP e_pl
;   37635  CD 04 94    CALL 37892 (hen draw, after the gfx address is set) -> CALL e_hd
;   37727  DD 2E 02    LD IXl,2 (hen erase = tile redraw)      -> JP e_he
;   43934, 44700  21 FF 5A  LD HL,23295 (CLS)                  -> JP e_c1 / e_c2
;   42403, 42946  21 00 40  LD HL,16384 (CLS)                  -> JP e_c3 / e_c4
;   43442  01 00 18    LD BC,6144 (CLS)                        -> JP e_c5
; Screen-write patches (no hook): 39697 1A B6 -> 7E 00 (player/duck buffer = background only),
;   39827 36 06 -> 00 00 (no yellow attributes), 37646 77 -> 00 and 37653 77 -> 00 (hen OR writes),
;   37707 36 05 -> 00 00 (no cyan attributes).
; Sprites: hens 0-4 (hen table entry (DE-29527)/4), duck 5, player 6 (higher number on top).
; Patterns: 0-31 = player/duck frame A (gfx 36336+32A), 32-47 = hen block A' (gfx 36878+32A').

        DEVICE ZXSPECTRUMNEXT

SPR_DUCK  EQU 5
SPR_PLAY  EQU 6
HENTAB    EQU 29527
PAT_HEN   EQU 32

        ORG 0x386E
; ---- player / duck plotter entry: A = frame, L = x, H = y (191 - top line) ----
e_pl:   push af
        push bc
        push de
        push hl
        ld hl,8
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = return address of the plotter call
        ld b,SPR_PLAY
        ld a,e
        cp low 41238
        jr nz,.d2
        ld a,d
        cp high 41238
        jr z,.duck
.d2:    ld a,e
        cp low 41361
        jr nz,.pl
        ld a,d
        cp high 41361
        jr nz,.pl
.duck:  ld b,SPR_DUCK
.pl:    ld a,b
        nextreg 0x34,a
        ld hl,7
        add hl,sp
        ld c,(hl)               ; C = frame (A at entry)
        pop hl
        push hl
        ld a,c
        cp 32
        jr nc,.hide             ; (frames >= 32 never occur; hidden)
        ld a,l
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        nextreg 0x37,a          ; X8, palette offset 0 (yellow)
        ld a,223
        sub h                   ; Y = 191 - H + 32
        nextreg 0x36,a
        ld a,c
        call setpat
        jr .out
.hide:  nextreg 0x38,0
.out:   pop hl
        pop de
        pop bc
        pop af
        push af
        push bc
        push de
        jp 39503

; ---- hen draw: CALL 37892 with DE = gfx (36878 + 32A'), HL = position, C = 2 (1: x >= 249) ----
; stack: +0 return 37638, +2 HL, +4 AF, +6 caller DE (hen table entry), +8 caller BC
e_hd:   push af
        push bc
        push de
        push hl
        call henidx             ; A = hen index, carry set if not a hen table entry
        jr c,.out
        nextreg 0x34,a
        ld hl,4
        add hl,sp
        ld a,(hl)               ; C at entry
        cp 2
        jr nz,.hide             ; 1 byte per row: the original draws nothing
        ld hl,-36878
        add hl,de               ; DE = gfx: HL = 32 * A'
        ld a,h
        cp 2
        jr nc,.hide             ; A' outside 0-15: no pattern (never occurs)
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,h
        rlca
        rlca
        rlca
        or c
        add a,PAT_HEN
        ld c,a
        pop hl
        push hl                 ; HL = position
        ld a,l
        and 0xF8
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        or 0x10                 ; palette offset 1 (cyan)
        nextreg 0x37,a
        ld a,208
        sub h                   ; Y = 191 - H - 15 + 32
        nextreg 0x36,a
        ld a,c
        call setpat
        jr .out
.hide:  nextreg 0x38,0
.out:   pop hl
        pop de
        pop bc
        pop af
        jp 37892

; ---- hen erase (tile redraw at the hen's old position): hide its sprite ----
; stack: +0 HL, +2 AF, +4 caller DE, +6 caller BC
e_he:   push af
        push bc
        push de
        push hl
        ld hl,8+4
        add hl,sp
        call henid2
        jr c,.out
        nextreg 0x34,a
        nextreg 0x38,0
.out:   pop hl
        pop de
        pop bc
        pop af
        ld ixl,2
        jp 37730

; ---- screen clears: hide every sprite ----
e_c1:   call hideall
        ld hl,23295
        jp 43937
e_c2:   call hideall
        ld hl,23295
        jp 44703
e_c3:   call hideall
        ld hl,16384
        jp 42406
e_c4:   call hideall
        ld hl,16384
        jp 42949
e_c5:   call hideall
        ld bc,6144
        jp 43445

hideall:
        push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp SPR_PLAY+1
        jr nz,.h
        pop af
        ret

; A = pattern (sprite selected): visible 4-bit sprite with pattern A
setpat: ld b,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; e_hd: the caller's DE is at SP+2 (return of this CALL) +8 (pushes) +6
henidx: ld hl,2+8+6
        add hl,sp
; HL -> caller DE (low, high). A = (DE - HENTAB) / 4, carry set if DE outside the 5 entries
henid2: ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld bc,-HENTAB
        add hl,bc
        ld a,h
        or a
        jr nz,.no
        ld a,l
        cp 20
        jr nc,.no
        rrca
        rrca
        and 7
        or a                    ; carry clear
        ret
.no:    scf
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0xE000
        ld d,24                     ; 48 patterns x 128 bytes = 24 x 256
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,1
        nextreg 0x41,0xB4           ; offset 0 index 1: yellow (attr 6)
        nextreg 0x40,17
        nextreg 0x41,0x16           ; offset 1 index 1: cyan (attr 5)
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

        SAVEBIN "ce_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ce_setup.bin",0xD000,setup_end-0xD000
