; Underwurlde (Ultimate Play The Game, 1984, 48K) - hardware sprites for the moving figures.
; Hooks in alt ROM image 1 from 0x2000 (the game runs only 0x0038-0x0363 of the ROM). Interrupts are
; ENABLED at the hook sites (ROM IM 1, the game reads FRAMES): the hooks keep IX, IY, I and IFF, use the
; game's stack, and page only slot 7, which the ROM's handler never touches.
;
; Sites (nexclash/underwurlde.py checks the original bytes):
;   38647 CD 89 96 CALL 38537 (erase old + draw new) -> CALL e_move
;   38442 CD 89 96 CALL 38537 (draw only)            -> CALL e_draw
;   38454 CD 57 96 CALL 38487 (erase only)           -> CALL e_erase
;   39015 DD 6E 01 LD L,(IX+1) (paint the figure's cells) -> JP e_attr
;   39175 CD AB 99 CALL 39339 (room: clear + paint)  -> CALL e_room
;   38269 CD C2 99 CALL 39362 (clear the screen)     -> CALL e_cls
;   the 36 LD (HL),A of the row plotters 38754-38860, 38888-38994: 77 -> 7E LD A,(HL). Same T-states, same
;   contention; the rows change nothing on the ULA. All that differs is A' after a row (never read: the
;   engine's A' test). A plot's bookkeeping keeps running exactly as the original's.
; Figures (directory rows != 0, IX in a slot) are sprites. Anything else plotted (furniture, static
; mounds and plants, menu icons, the lives figure) is XORed to the ULA here, as the row plotters did.

        DEVICE ZXSPECTRUMNEXT

GFXTAB  EQU 37682
OID     EQU 36577               ; the old image, as 39071 saved it
OX      EQU 36580
OY      EQU 36581
NIDS    EQU 150
NSLOT   EQU 24
GP7     EQU 1                   ; the game's page at slot 7
V_SLOT  EQU 0x5B80              ; per slot: id shown (0 = none), attribute byte shown, sprites shown
V_ID    EQU V_SLOT+NSLOT*3
V_PAL   EQU V_ID+1
V_W     EQU V_ID+2
V_H     EQU V_ID+3
V_CNT   EQU V_ID+4
V_AL    EQU V_ID+5
V_END   EQU V_ID+6
HLIB_V_R EQU 0x5BD0
V_SPEED EQU 0x5BD3
HLIB_V_PACE EQU 0x5BD4
HLIB_PACE_NL EQU 312
V_ACTIVE EQU 0x5BEE
V_CONT EQU 0x5BEF
IRQ_SEL EQU 0x5BF0
IRQ_SPEED EQU 0x5BF1
IRQ_FIRST_R EQU 0x5BF2
IRQ_LAST_R EQU 0x5BF3
V_FAST EQU 0x5BF4
        INCLUDE "lib/hlib_speed.asm"
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_iff.asm"
        ; Refresh state is shared with the ISR. Capture, target calculation and
        ; restore are separate short atomic windows, all at 28 MHz. The long
        ; sprite upload, original row loop and pace wait keep interrupts on.
        MACRO R_IN
        push af
        HLIB_IFF_DI
        push af
        HLIB_R_IN
        ld a,1
        ld (V_ACTIVE),a
        pop af
        HLIB_IFF_EI
        pop af
        ENDM
        MACRO R_SET delta
        push af
        HLIB_IFF_DI
        push af
        ld a,delta
        jp pe,$+4
        inc a                  ; off: one fewer exit EI, capture M1s are fixed
        call hlib_r_set
        pop af
        HLIB_IFF_EI
        pop af
        ENDM
        MACRO R_OUT
        push af
        HLIB_IFF_DI
        push af
        xor a
        ld (V_ACTIVE),a
        ld a,(HLIB_V_R+1)
        ld r,a
        pop af
        HLIB_IFF_EI
        pop af
        ENDM
        MACRO SPEED_IN
        HLIB_SPEED_IN V_SPEED
        push af
        ld a,1
        ld (V_FAST),a
        pop af
        ENDM
        MACRO SPEED_OUT
        HLIB_SPEED_OUT V_SPEED
        push af
        xor a
        ld (V_FAST),a
        pop af
        ENDM

        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
; ---- the three plot entries: run the game's own setup, then the display work ----
e_move: call 38537
        SPEED_IN
        R_IN
        push af
        push bc
        push de
        push hl
        R_SET -36
        call hlib_debt_open
        ld a,(OID)
        call isfig
        jr nz,z_e_move_new
        ld a,(OX)
        ld l,a
        ld a,(OY)
        ld h,a
        ld a,(OID)
        call xorimg
z_e_move_new:   call newimg
        jp hkout

e_draw: call 38537
        SPEED_IN
        R_IN
        push af
        push bc
        push de
        push hl
        R_SET -36
        call hlib_debt_open
        call newimg
        jp hkout

e_erase: call 38487
        SPEED_IN
        R_IN
        push af
        push bc
        push de
        push hl
        R_SET -36
        call hlib_debt_open
        ld a,(OID)
        call isfig
        jr nz,z_e_erase_h
        ld a,(OX)
        ld l,a
        ld a,(OY)
        ld h,a
        ld a,(OID)
        call xorimg
        jp hkout
z_e_erase_h:
n_hide: call hide
hkout:
        ld a,12
        call hlib_debt_close
        call hlib_pace_open
        ; Run the retired row loops at 28 MHz. Their registers and working-RAM
        ; effects remain original; this window repays the added sprite work.
        ld hl,8
        add hl,sp
        ld a,(hl)
        ld (V_CONT),a
        ld (hl),low rows_out
        inc hl
        ld (hl),high rows_out
        cp low 38445
        jr z,rows_draw
        cp low 38457
        jr z,rows_erase
        pop hl
        pop de
        pop bc
n_pop:  pop af
        R_OUT
        jp 38650
rows_draw: pop hl
        pop de
        pop bc
        pop af
        R_OUT
        jp 38445
rows_erase: pop hl
        pop de
        pop bc
        pop af
        R_OUT
        jp 38457
rows_out:
        R_IN
        push af
        push bc
        push de
        push hl
        R_SET -25
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld a,96
        call hlib_mul8
        HLIB_SPEED_OUT V_SPEED
        ld a,(V_SPEED)
        call hlib_pace_wait
        nextreg 7,3
        pop hl
        pop de
        pop bc
        pop af
        R_OUT
        SPEED_OUT
        ret

; ---- screen changes: every sprite off ----
e_room:
n_room: call hideall
        jp 39339
e_cls:
n_cls:  call hideall
        jp 39362
hideall:
        SPEED_IN
        R_IN
        push af
        push bc
        push hl
        R_SET -46
        xor a
z_hideall_h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 126
        jr nz,z_hideall_h
        ld hl,V_SLOT
        ld b,NSLOT*3
z_hideall_c:     ld (hl),0
        inc hl
        djnz z_hideall_c
        pop hl
        pop bc
        pop af
        R_OUT
        SPEED_OUT
        ret

; ---- the figure's cell painter, entered in place of LD L,(IX+1) at 39015 ----
; All of A, F, B, C, D, H, L are set by the routine before use, so they are free here; E is kept.
e_attr: SPEED_IN
        R_IN
        ld a,(ix+0)
        push de
        call isfig
        pop de
        jr nz,z_e_attr_fig
        R_SET -45
        R_OUT
        SPEED_OUT
        ld l,(ix+1)
        jp 39018
z_e_attr_fig:
        R_SET -35
        R_OUT
        ld l,(ix+1)             ; 39015-39070 with CP (HL) for LD (HL),D: same T, no paint
        ld h,(ix+3)
        ld d,(ix+5)
        ld a,h
        cpl
        and 7
        ld b,a
        ld a,(36583)
        add a,8
        add a,b
        rrca
        rrca
        rrca
        and 31
        ld c,a
        ld a,(36582)
        ld b,a
        call 44512
z_e_attr_rows:  push bc
        push hl
        ld a,h
        cp 88
        jr c,z_e_attr_nop
z_e_attr_cell:
n_paint: cp (hl)
        inc l
        djnz z_e_attr_cell
z_e_attr_nop:   pop hl
        ld bc,32
        and a
        sbc hl,bc
        pop bc
        dec c
        jr nz,z_e_attr_rows
        ; the colour may change with no plot: follow it
        R_IN
        push af
        push bc
        push de
        push hl
        R_SET -24
        call slotof
        jr z,z_e_attr_out
        ld a,(hl)
        or a
        jr z,z_e_attr_out               ; not shown
        inc hl
        ld a,(hl)
        cp (ix+5)
        jr z,z_e_attr_out
        ld a,(ix+0)
        call show
z_e_attr_out:
        pop hl
        pop de
        pop bc
        pop af
        R_OUT
        SPEED_OUT
        ret

; ---- A = id: Z = not a sprite (not in the directory, or IX has no slot). Uses A, F, B, C, D, E, H, L ----
isfig:  call dirent
        ret z
isf2:   call slotof
        ret

; A = id -> HL = directory entry (page, offset, rows, height); Z if it has no sprite
dirent: cp NIDS
        jr nc,z_dirent_no
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,DIR
        add hl,de
        inc hl
        inc hl
        ld a,(hl)               ; rows
        dec hl
        dec hl
        or a
        ret
z_dirent_no:    xor a
        ret

; IX -> HL = its state, B = first sprite, C = sprites it may use; Z if IX is not a figure record
slotof: push ix
        pop hl
        ld de,-36602
        add hl,de
        jr nc,z_slotof_no
        ld a,h
        cp 1
        jr c,z_slotof_s16               ; < 256: a 16-byte record
        jr nz,z_slotof_no
        ld a,l
        cp 48
        jr c,z_slotof_s16               ; 256-303
        cp 88
        jr nc,z_slotof_no               ; 304-343: an 8-byte record
        sub 48
        ld c,a
        and 7
        jr nz,z_slotof_no
        ld a,c
        rrca
        rrca
        rrca
n_w:    add a,19
        jr z_slotof_got
z_slotof_s16:   ld a,l
        and 15
        jr nz,z_slotof_no
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 15
        ld c,a
        ld a,h
        rrca
        rrca
        rrca
        rrca
        or c
z_slotof_got:   ld c,a
        ld b,0
        ld hl,BASES
        add hl,bc
        add hl,bc
        ld a,c
        ld d,(hl)
        inc hl
        ld e,(hl)
        ld l,a                  ; state = V_SLOT + 3 * slot
        add a,a
        add a,l
        ld l,a
        ld h,high V_SLOT
        ld a,low V_SLOT
        add a,l
        ld l,a
        ld b,d
        ld c,e
        or 1                    ; NZ
        ret
z_slotof_no:    xor a
        ret

; ---- the new image of IX ----
newimg: ld a,(ix+0)
        call isfig
        jr z,z_newimg_ula
        ld a,(ix+0)
        jp show
z_newimg_ula:   call hide
        ld l,(ix+1)
        ld h,(ix+3)
        ld a,(ix+0)
        ; falls into xorimg

; ---- A = id, L = x, H = y: XOR the image to the ULA, as the row plotters do ----
xorimg:
n_xor:  push hl
        ld l,a
        ld h,0
        add hl,hl
        ld de,GFXTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        ld a,l
        dec a
        rlca
        and 14
        or 240
        ld b,a
        ld a,(de)
        inc de
        ld (V_W),a
        ld a,(de)
        inc de
        ld (V_H),a
        or a
        ret z
        ld a,l
        and 7
        ld (V_AL),a
        ld a,l                  ; 44536 without its EX AF,AF'
        rrca
        rrca
        rrca
        and 31
        ld l,a
        ld a,h
        rlca
        rlca
        and 224
        or l
        ld l,a
        ld a,h
        and 7
        ld c,a
        ld a,h
        rrca
        rrca
        rrca
        and 24
        or 64
        or c
        ld h,a
z_xorimg_row:   push hl
        ld a,(V_AL)
        or a
        jr nz,z_xorimg_shift
        dec l                   ; aligned: the left part is 0 (table 0xFE), on the byte before
z_xorimg_shift: ld a,(V_W)
        ld (V_CNT),a
z_xorimg_byte:  ld a,(de)
        ld c,a
        ld a,(bc)
        xor (hl)
        ld (hl),a
        inc l
        inc b
        ld a,(bc)
        xor (hl)
        ld (hl),a
        dec b
        inc de
        ld a,(V_CNT)
        dec a
        ld (V_CNT),a
        jr nz,z_xorimg_byte
        pop hl
        dec h
        ld a,h
        cpl
        and 7
        jr nz,z_xorimg_next
        ld a,l
        sub 32
        ld l,a
        jr c,z_xorimg_next
        ld a,h
        add a,8
        ld h,a
z_xorimg_next:  ld a,(V_H)
        dec a
        ld (V_H),a
        jr nz,z_xorimg_row
        ret

; ---- A = id, a figure: its sprites at IX's position, IX's colour ----
show:
n_ix:   ld (V_ID),a
        call slotof             ; HL = state, B = first sprite, C = allowance
        ret z
        push hl
        ld a,(V_ID)
        call dirent             ; HL = entry
        pop de                  ; DE = state
        ld a,(hl)               ; page
        ld (V_W),a
        inc hl
        ld a,(hl)               ; offset (256 bytes)
        ld (V_CNT),a
        inc hl
        ld a,(hl)               ; rows
        add a,a                 ; sprites
        cp c
        jr c,z_show_fits
        ld a,c
z_show_fits:  ld c,a                  ; C = sprites to show
        inc hl
        ld a,(hl)
        ld (V_H),a              ; height
        ; pattern upload, if another image is there
        ld a,(de)
        ld hl,V_ID
        cp (hl)
n_same: jr z,z_show_same
        ld a,(hl)
        ld (de),a
        push bc
        ld a,b
        srl a
        ld bc,0x303B
        out (c),a
        ld a,(V_W)
        nextreg 0x57,a
        ld a,(V_CNT)
        add a,0xE0
        ld h,a
        ld l,0
        pop bc
        push bc
        ld a,c
        srl a                   ; rows
z_show_up:    ld bc,0x005B
        otir
        dec a
        jr nz,z_show_up
        nextreg 0x57,GP7
        pop bc
z_show_same:  inc de
n_pal:  ld a,(ix+5)
        ld (de),a               ; the colour shown
        ld h,a
        and 7
        bit 6,h
        jr z,z_show_dim
        or 8
z_show_dim:   rlca
        rlca
        rlca
        rlca
        ld (V_PAL),a
        inc de                  ; DE -> sprites shown
        ld a,(de)
        ld (V_W),a              ; old count
        ld a,c
        ld (de),a
        ; position: X = 31 + x + 16 col, Y = 32 + y - h + 16 row (the outline's corner)
        push bc
        ld a,(ix+1)
        ld e,a
        ld d,0
n_x:    ld hl,31
        add hl,de
        ex de,hl                ; DE = X
        ld a,(ix+3)
        ld l,a
        ld h,0
n_y:    ld bc,32
        add hl,bc
        ld a,(V_H)
        ld c,a
        ld b,0
        or a
        sbc hl,bc               ; HL = Y
        pop bc
        ld a,c
        ld (V_CNT),a            ; sprites to show
        ld c,b                  ; C = sprite number
z_show_tile:  call one
        inc c
        ld a,e
        add a,16
        ld e,a
        jr nc,z_show_nc
        inc d
z_show_nc:    call one
        inc c
        ld a,e
        sub 16
        ld e,a
        jr nc,z_show_nb
        dec d
z_show_nb:    ld a,l
        add a,16
        ld l,a
        jr nc,z_show_nd
        inc h
z_show_nd:    ld a,(V_CNT)
        sub 2
        ld (V_CNT),a
        jr nz,z_show_tile
        ; sprites this image does not need off. C = next sprite, count from the first
        ld a,(V_ID)
        call z_show_extra
        ret
z_show_extra:
n_off:  ld a,(V_W)              ; old count
        ld b,a
        call slotof_b           ; A = first sprite
        add a,b                 ; A = old end
        sub c                   ; how many past C
        ret z
        ret c
        ld b,a
        ld a,c
z_show_off:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz z_show_off
        ret

; A = first sprite of IX (B kept)
slotof_b:
        push bc
        call slotof
        ld a,b
        pop bc
        ret

; C = sprite, DE = X, HL = Y
one:    ld a,c
        nextreg 0x34,a
        ld a,e
        nextreg 0x35,a
        ld a,l
        nextreg 0x36,a
        ld a,d
        and 1
        ld b,a
        ld a,(V_PAL)
        or b
        nextreg 0x37,a
        ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld b,a
        ld a,h
        and 1
        or b
        nextreg 0x39,a
        ret

; ---- IX's sprites off, its state cleared ----
hide:   call slotof
        ret z
        ld a,b                  ; first sprite
        ld (hl),0
        inc hl
        inc hl
        ld b,(hl)
        ld (hl),0
        inc b
        dec b
        ret z
z_hide_off:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz z_hide_off
        ret

; The original 48K ROM interrupt runs at the incoming game's speed. Preserve
; its instruction contribution to R and exclude its elapsed time from the limiter.
irq_in:
        push af
        push bc
        push de
        push hl
        ld a,r
        ld (IRQ_FIRST_R),a
        ld bc,0x243B
        in a,(c)
        ld (IRQ_SEL),a
        HLIB_SPEED_IN IRQ_SPEED
        call hlib_pace_hold
        ld a,(V_FAST)
        or a
        ld a,(IRQ_SPEED)
        jr z,.clock
        ld a,(V_SPEED)
.clock: nextreg 7,a
        ld a,(IRQ_FIRST_R)
        ld b,a
        add a,-12
        and 0x7F
        bit 7,b
        jr z,.r
        or 0x80
.r:     ld r,a
        pop hl
        pop de
        pop bc
        pop af
        push af
        push hl
        ld hl,(23672)
        jp 0x003D
irq_out:
        push af
        push bc
        push de
        push hl
        ld a,r
        ld (IRQ_LAST_R),a
        nextreg 7,3
        call hlib_pace_resume
        ld a,(V_ACTIVE)
        or a
        jr z,.noadd
        ld a,(IRQ_FIRST_R)
        ld b,a
        ld a,(IRQ_LAST_R)
        sub b
        add a,5
        ld b,a
        ld a,(HLIB_V_R)
        ld c,a
        add a,b
        and 0x7F
        bit 7,c
        jr z,.save0
        or 0x80
.save0: ld (HLIB_V_R),a
        ld a,(HLIB_V_R+1)
        ld c,a
        add a,b
        and 0x7F
        bit 7,c
        jr z,.save1
        or 0x80
.save1: ld (HLIB_V_R+1),a
.noadd: ld a,(IRQ_LAST_R)
        ld b,a
        add a,-11
        and 0x7F
        bit 7,b
        jr z,.r
        or 0x80
.r:     ld d,a
        ld bc,0x243B
        ld a,(IRQ_SEL)
        out (c),a
        HLIB_SPEED_OUT IRQ_SPEED
        ld a,d
        ld r,a
        pop hl
        pop de
        pop bc
        pop af
        pop hl
        pop af
        ei
        ret

; slot -> first sprite, allowance. Later sprites are on top: Sabreman highest.
BASES:  db 20,2, 22,2                                   ; 36602, 36618 (no plot seen: one row)
        db 120,6, 114,6                                 ; 36634 Sabreman, 36650
        db 24,6, 30,6, 36,6, 42,6                       ; 36666-36714
        db 48,6, 54,6, 60,6, 66,6, 72,6, 78,6           ; 36730-36810
        db 84,6, 90,6, 96,6, 102,6, 108,6               ; 36826-36890
        db 0,4, 4,4, 8,4, 12,4, 16,4                    ; 36906-36938
DIR:    ds NIDS*4               ; page, offset, rows, height (built by nexclash/underwurlde.py)
rom_end:

; ---- setup (stub bank, 0xD000): palette, all sprites off, hook state zero, sprites on ----
        ORG 0xD000
setup:  ; Own IM1: NextZXOS leaves the delayed RST 38 DivMMC trap enabled.
        ; The shared stub's NR06 NMI switch does not disable automapping on
        ; modern cores. A three-byte JP at 0038 otherwise fetches its target
        ; from DivMMC RAM. Preserve every unrelated NR0A bit.
        ld bc,0x243B
        ld a,0x0A
        out (c),a
        inc b
        in a,(c)
        and 0xEF
        nextreg 0x0A,a
        xor a
        out (0xE3),a
        nextreg 0x43,0x20       ; sprite palette 0
        nextreg 0x40,0
        ld hl,INKS
        ld d,16                 ; palette offsets
z_setup_o:     ld a,0xE3
        nextreg 0x41,a          ; index 0, transparent
        ld a,(hl)
        inc hl
        nextreg 0x41,a          ; index 1 = this offset's Spectrum colour
        push hl
        ld hl,FIXED
        ld e,14
z_setup_f:     ld a,(hl)
        inc hl
        nextreg 0x41,a          ; indices 2-15, the same in every offset
        dec e
        jr nz,z_setup_f
        pop hl
        dec d
        jr nz,z_setup_o
        nextreg 0x4B,0
        xor a
z_setup_h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,z_setup_h
        nextreg 0x15,0x01       ; sprites on
        ret
INKS:   db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6     ; ink 0-7
        db 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF     ; bright
; 2 black (outline and enclosed paper), 3-15 the colours a painting may use
FIXED:  db 0x00, 0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "uw_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "uw_setup.bin",0xD000,setup_end-0xD000
