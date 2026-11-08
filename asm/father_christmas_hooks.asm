; The Official Father Christmas Game (Enigma Variations / Alternative, 1989, 48K): clash removal on Layer 2.
;
; In level 1 the figures take the colour of the cells they cross: Santa and the elves go cyan at the table and
; yellow on the ladder. The ULA stays the original's, every byte: the game reads its attributes for walls and
; ladders. Each figure's ink goes on a double-buffered Layer 2 in bright white, its colour in the open; a later
; figure's opaque pixels punch out what it covers, as on the ULA (elves in front of Santa).
;
; The game plots straight to the screen, 25 updates a second, locked by two HALTs, interrupts off:
;   7EE7 Santa (4 bytes x 40 lines, in FA04 FA08 FA0A), 8FEE an elf (3 bytes x 24 lines, HL graphic, DE screen).
; h_santa and h_elf note what is plotted and go on to the game's own routine. h_draw, at the end of the update's
; plots, redraws the overlay and flips. Each graphic's pixels are a list made once, kept in Next pages (RAM only).
; Game RAM is read only here. The update's HALTs absorb the hook time: the pace does not change.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
GRID_LIST_ROOM EQU 3000
RECTS_A EQU 0x3900             ; what each buffer shows: 6 bytes a list, 40 of them
RECTS_B EQU 0x3A00
RECT_MAX EQU 40
DIR_PAGE EQU 47                ; 1,024 entries of 8 bytes: src, width, height, page, address
LIST_FIRST EQU 48              ; list pages (RAM only, nothing in the .nex)
LIST_LAST EQU 93
STK EQU 0x3BA0
HLIB_V_R EQU 0x3BA0
V_SPEED EQU 0x3BC0
V_SP EQU 0x3BC2
V_BACK EQU 0x3BC5              ; L2 16K bank of the back buffer
V_NE EQU 0x3BC7                ; elves plotted this update
V_R0 EQU 0x3BC8
V_RET EQU 0x3BF4               ; word
V_HL EQU 0x3BCA                ; word
V_RECT EQU 0x3BCC              ; word: end of the back buffer's list
; Santa: valid, graphic, line index, column
S_ON EQU 0x3BD0
S_SRC EQU 0x3BD1               ; word
S_Y EQU 0x3BD3
S_X EQU 0x3BD4
; elves: graphic, y, column each
E_TAB EQU 0x3BD5               ; 2 entries of 4 bytes
P_SRC EQU 0x3BE0               ; word
P_W EQU 0x3BE2
P_H EQU 0x3BE3
P_Y EQU 0x3BE4
P_COL EQU 0x3BE5
P_PAGE EQU 0x3BE6
P_C EQU 0x3BE7
P_L EQU 0x3BE8
P_PG EQU 0x3BE9
V_DIR EQU 0x3BEA               ; word
V_FREE EQU 0x3BEC              ; word
V_FREEP EQU 0x3BEE
V_LIST EQU 0x3BF0              ; word
V_KIND EQU 0x3BF2              ; 1: an elf, with a punch part
L2_BANK_A EQU 16
L2_BANK_B EQU 19
INK EQU 15
CLEAR EQU 255
TABLE EQU 0xDE5C               ; the game's screen line addresses
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"

; Enter: hook page, own stack, R noted. Leave: registers and R as the original's, then the game's own code.
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,STK
        push af
        ld a,r
        ld (HLIB_V_R),a
        ENDM
        MACRO LEAVE delta
        ld a,delta
        call hlib_r_set
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM

; The body on the game's own SP at 28 MHz, entered as the game's CALL would enter it. Its return address is borrowed for
; the way back and put back after, so RAM stays the original's, stack too. These plots send nothing to a port.
        MACRO ENTER_ALL
        ENTER
        push bc
        push de
        push hl
        HLIB_SPEED_IN V_SPEED
        ENDM
        MACRO BODY target
        ld hl,(V_SP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_RET),de
        ld de,.back
        ld (hl),d
        dec hl
        ld (hl),e
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld sp,(V_SP)
        jp target
.back:  ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld hl,(V_SP)
        ld de,(V_RET)
        ld (hl),e
        inc hl
        ld (hl),d
        ENDM
        MACRO LEAVE_ALL delta
        ld a,delta
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret
        ENDM

; ---- Santa: the game's own plot, at 28 MHz ------------------------------------------
h_santa:
        ENTER_ALL
        ld hl,(0xFA04)
        ld (S_SRC),hl
        ld hl,(0xFA08)
        srl h
        rr l
        ld a,l
        ld (S_Y),a
        ld a,(0xFA0A)
        ld (S_X),a
        ld a,1
        ld (S_ON),a
        BODY 0x7EE7
        LEAVE_ALL R_SANTA

; ---- an elf: HL = its graphic, DE = its first screen byte; the game's own plot ---------
h_elf:
        ENTER_ALL
        ld hl,STK-8+1           ; the stack as ENTER_ALL left it: HL at STK-8
        ld d,(hl)
        dec hl
        ld e,(hl)               ; DE = the caller's HL
        ld (V_HL),de
        ld hl,STK-6
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the caller's DE
        ld hl,E_TAB
        ld a,(V_NE)
        and 1
        add a,a
        add a,a
        add a,l
        ld l,a
        ld a,(V_HL)
        ld (hl),a
        inc l
        ld a,(V_HL+1)
        ld (hl),a
        inc l
        ; screen address -> y
        ld a,d
        and 7
        ld b,a
        ld a,e
        rrca
        rrca
        and 0x38
        or b
        ld b,a
        ld a,d
        rlca
        rlca
        rlca
        and 0xC0
        or b
        ld (hl),a
        inc l
        ld a,e
        and 31
        ld (hl),a
        ld hl,V_NE
        inc (hl)
        BODY 0x8FEE
        LEAVE_ALL R_ELF

; ---- the update's restores at 28 MHz: the flip comes that much sooner, ahead of the beam -----
h_rest_e:
        ENTER_ALL
        BODY 0x8E2E
        LEAVE_ALL R_REST
h_rest_s:
        ENTER_ALL
        BODY 0x8E00
        LEAVE_ALL R_REST
h_save_s:
        ENTER_ALL
        BODY 0x8DD2
        LEAVE_ALL R_REST

; ---- the end of the update's plots: redraw and flip, then the game's own 90AB --------
h_draw:
        ENTER
        push bc
        push de
        push hl
        HLIB_SPEED_IN V_SPEED
        call l2_redraw
        HLIB_SPEED_OUT V_SPEED
        pop hl
        pop de
        pop bc
        LEAVE R_DRAW
        jp 0x90AB

; ---- a room built, or a text screen: the overlay off until the next flip -------------
h_room:
        ENTER
        call l2_off
        LEAVE R_ROOM
        jp 0x7FB4

h_cls:
        ENTER
        call l2_off
        LEAVE R_CLS
        ld hl,0x5800
        jp 0x83A8
veneers_end:
        ASSERT veneers_end < 0x2C80

l2_off: nextreg 0x69,0
        xor a
        ld (S_ON),a
        ld (V_NE),a
        ret

; ---- Layer 2 -------------------------------------------------------------------------
; While drawing: slot 0 = a list page or the directory, slots 2 and 3 = two Layer 2 pages in a row.
l2_redraw:
        call l2_clear
        ld a,(S_ON)
        or a
        jr z,.noS
        ld hl,(S_SRC)
        ld (P_SRC),hl
        ld a,(S_Y)
        ld (P_Y),a
        ld a,(S_X)
        ld (P_COL),a
        ld hl,0x2804            ; H = 40 lines, L = 4 bytes; Santa's byte order: mask, data
        ld (P_W),hl
        call fig
.noS:   ld a,(V_NE)
        or a
        jr z,.pub
        ld b,a
        ld hl,E_TAB
.el:    push bc
        push hl
        ld a,(hl)
        ld (P_SRC),a
        inc l
        ld a,(hl)
        ld (P_SRC+1),a
        inc l
        ld a,(hl)
        ld (P_Y),a
        inc l
        ld a,(hl)
        ld (P_COL),a
        ld hl,0x1803            ; H = 24 lines, L = 3 bytes
        ld (P_W),hl
        call fig_elf
        pop hl
        ld a,l
        add a,4
        ld l,a
        pop bc
        djnz .el
        xor a
        ld (V_NE),a
.pub:   nextreg 0x50,255
        nextreg 0x52,10
        nextreg 0x53,11
        ; publish
        ld a,(V_BACK)
        nextreg 0x12,a
        nextreg 0x69,0x80
        cp L2_BANK_A
        ld hl,(V_RECT)
        jr z,.a
        ld (V_LIST_B),hl
        ld hl,(V_LIST_A)
        ld a,L2_BANK_A
        jr .s
.a:     ld (V_LIST_A),hl
        ld hl,(V_LIST_B)
        ld a,L2_BANK_B
.s:     ld (V_RECT),hl
        ld (V_BACK),a
        ret
V_LIST_A: defw RECTS_A
V_LIST_B: defw RECTS_B

; l2_clear: every list this buffer showed, again, in the transparent colour; the list emptied.
l2_clear:
        ld a,CLEAR
        ld (ink_list.colour+1),a
        ld (ink_clip.colour+1),a
        ld a,(V_BACK)
        cp L2_BANK_A
        ld de,RECTS_A
        jr z,.a
        ld de,RECTS_B
.a:     ld hl,(V_RECT)
        ld (.end+1),hl
        ld (.base+1),de
.lp:
.end:   ld hl,0
        or a
        sbc hl,de
        jr z,.out
        ld a,(de)
        ld (P_PAGE),a
        inc de
        ld a,(de)
        ld l,a
        inc de
        ld a,(de)
        ld h,a
        inc de
        ld a,(de)
        ld (P_Y),a
        inc de
        ld a,(de)
        ld (P_COL),a
        inc de
        push de
        ex de,hl
        ld a,(P_PAGE)
        nextreg 0x50,a
        call ink_list
        pop de
        jr .lp
.out:
.base:  ld hl,0
        ld (V_RECT),hl
        ld a,INK
        ld (ink_list.colour+1),a
        ld (ink_clip.colour+1),a
        ret

; ink_list: DE = the list (slot 0), P_Y, P_COL: the pixels on the back buffer.
ink_list:
        ld a,(P_Y)
        cp 192-41
        jp nc,ink_clip          ; low enough to reach the page after the last: test each pixel
        ld b,a
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        ld a,b
        and 31
        add a,0x40
        ld b,a                  ; B = the row's high byte for line 0
        ld a,(P_COL)
        add a,a
        add a,a
        add a,a
        ld c,a                  ; C = x of column 0
.lp:    ld a,(de)
        inc de
        cp 255
        ret z
        add a,b
        ld h,a
        ld a,(de)
        inc de
        add a,c
        ld l,a
.colour:
        ld (hl),INK
        jr .lp

; ink_clip: each pixel tested and paged.
ink_clip:
        ld a,255
        ld (P_PG),a
        ld a,(P_COL)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(P_Y)
        ld b,a
.lp:    ld a,(de)
        inc de
        cp 255
        ret z
        add a,b
        cp 192
        jr nc,.skip
        ld l,a
        rlca
        rlca
        rlca
        and 7
        ld h,a
        ld a,(P_PG)
        cp h
        jr z,.same
        ld a,h
        ld (P_PG),a
        push hl
        ld a,(V_BACK)
        add a,a
        add a,h
        nextreg 0x52,a
        pop hl
.same:  ld a,l
        and 31
        add a,0x40
        ld h,a
        ld a,(de)
        inc de
        add a,c
        ld l,a
.colour:
        ld (hl),INK
        jr .lp
.skip:  inc de
        jr .lp

; fig: Santa's graphic (mask, data); note it for this buffer's clear, draw its ink.
fig:    xor a
        ld (V_KIND),a
        jr fig_any
; fig_elf: an elf's (mask, data too: POP BC gives C mask, B data); its opaque paper punches what is under it.
fig_elf:
        ld a,1
        ld (V_KIND),a
fig_any:
        call list_find
        ret c
        push de
        call note
        pop de
        call ink_list
        ; DE = past the ink's terminator: the punch part. Only an elf has one.
        ld a,(V_KIND)
        or a
        ret z
        ld a,CLEAR
        ld (ink_list.colour+1),a
        ld (ink_clip.colour+1),a
        call ink_list
        ld a,INK
        ld (ink_list.colour+1),a
        ld (ink_clip.colour+1),a
        ret

; note: this list on the buffer's clear list
note:   ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*5
        ret nc
        ld a,(P_PAGE)
        ld (hl),a
        inc l
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld a,(P_Y)
        ld (hl),a
        inc l
        ld a,(P_COL)
        ld (hl),a
        inc l
        ld (V_RECT),hl
        ret

; list_find: the graphic's list: its directory entry, or made now. -> DE, page in slot 0, P_PAGE. Carry: no room.
list_find:
        nextreg 0x50,DIR_PAGE
        ld hl,(P_SRC)
        ld a,h
        srl a
        rr l
        srl a
        rr l
        srl a
        rr l
        srl a
        rr l
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        push hl
        ld a,(P_SRC)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(P_SRC+1)
        cp (hl)
        inc hl
        jr nz,.make
        ld a,(P_W)
        cp (hl)
        inc hl
        jr nz,.make
        inc hl
        ld a,(hl)
        or a
        jr z,.make
        ld (P_PAGE),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        nextreg 0x50,a
        or a
        ret
.make:  pop hl
        ld (V_DIR),hl
        ld hl,(V_FREE)
        ld de,GRID_LIST_ROOM
        add hl,de
        ld a,h
        cp 0x20
        jr c,.fits
        ld a,(V_FREEP)
        inc a
        cp LIST_LAST+1
        ccf
        ret c
        ld (V_FREEP),a
        ld hl,0
        ld (V_FREE),hl
.fits:  ld a,(V_FREEP)
        ld (P_PAGE),a
        ld hl,(V_DIR)
        ld a,(P_SRC)
        ld (hl),a
        inc hl
        ld a,(P_SRC+1)
        ld (hl),a
        inc hl
        ld a,(P_W)
        ld (hl),a
        inc hl
        inc hl
        ld a,(P_PAGE)
        ld (hl),a
        inc hl
        ld de,(V_FREE)
        ld (hl),e
        inc hl
        ld (hl),d
        push de
        nextreg 0x50,a
        call mk
        pop de
        or a
        ret

; mk: the list at V_FREE, from the graphic: lines of columns of (mask, data). Ink (y, x), 255; then, an elf's: the
; opaque pixels without ink, 255. HL walks the graphic, DE the list.
mk:     ld a,0                  ; pass 0: ink
        ld (.pass+1),a
        ld de,(V_FREE)
.again: ld hl,(P_SRC)
        xor a
        ld (P_L),a
.line:  xor a
        ld (P_C),a
.col:   ld c,(hl)               ; the mask
        inc hl
        ld b,(hl)               ; the data
        inc hl
.pass:  ld a,0
        or a
        jr z,.ink
        ld a,c
        cpl
        ld c,a                  ; opaque
        ld a,b
        cpl
        and c                   ; opaque and no ink
        ld b,a
.ink:   ld a,b
        or a
        jr z,.next
        push hl
        ld a,(P_C)
        add a,a
        add a,a
        add a,a
        ld c,a
.bit:   sla b
        jr nc,.nb
        ld a,(P_L)
        ld (de),a
        inc de
        ld a,c
        ld (de),a
        inc de
.nb:    inc c
        ld a,b
        or a
        jr nz,.bit
        pop hl
.next:  ld a,(P_C)
        inc a
        ld (P_C),a
        ld b,a
        ld a,(P_W)
        cp b
        jr nz,.col
        ld a,(P_L)
        inc a
        ld (P_L),a
        ld b,a
        ld a,(P_H)
        cp b
        jr nz,.line
        ld a,255
        ld (de),a
        inc de
        ld a,(.pass+1)
        or a
        jr nz,.done
        ld a,(V_KIND)
        or a
        jr z,.done
        ld a,1
        ld (.pass+1),a
        jr .again
.done:  ld (V_FREE),de
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3900
        SAVEBIN "fatherchristmas_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_BANK_A
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,143
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,16
.lp:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .lp
        nextreg 0x40,254
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x43,0
        ld d,L2_BANK_A*2
        call .fill
        ld d,L2_BANK_B*2
        call .fill
        ld a,DIR_PAGE
        nextreg 0x50,a
        ld hl,0
        ld (hl),l
        ld de,1
        ld bc,0x1FFF
        ldir
        nextreg 0x50,255
        ret
.fill:  ld e,6
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0xFF
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        ret
l2_pal: defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        defb 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:
        SAVEBIN "fatherchristmas_setup.bin",setup,setup_end-setup

; R deltas: M1s of the original minus the hook's own (calibrated by the replay, hooklib.r_check)
R_REST EQU -24
R_SANTA EQU -24
R_ELF EQU -24
R_DRAW EQU -12
R_ROOM EQU -12
R_CLS EQU -13
