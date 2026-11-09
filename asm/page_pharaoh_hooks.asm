; Page and the Curse of the Pharaoh (T.D.F. micro-visions, 2015, 48K-128K): clash removal by a Layer 2 figure overlay.
;
; The game XORs each figure straight onto the ULA, two figure groups on alternate frames, locked to the
; interrupt by its own wait (7F5F, FRAMES). It never writes an attribute for a figure, so a figure in a
; cell of scenery takes that cell's ink. Here the ULA stays the original's, every byte. Each XOR plot is
; repeated on a Layer 2 in the figures' own white, by toggling: the overlay holds exactly what the game's
; plots hold, and scenery keeps its colours under it. The game's XOR body runs at 28 MHz, which pays for
; the overlay; the game's own frame wait keeps the pace in play. The one long hook, clearing the overlay
; for a new room, is repaid by the room's own drawing inside an hlib_pace K window.
;
; Layer 2 pages go in slot 7 (the game's E000 up holds nothing the hook or the ROM's IM 1 handler reads
; here, and interrupts stay on throughout); slot 1 holds this page.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
K_ROOM EQU 104
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_R0 EQU 0x3E35
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_C EQU 0x3E3F
P_B EQU 0x3E40
L2_BANK EQU 16
TOGGLE EQU 0xF8                ; transparent 255 <-> white 7
ROW_SIZE EQU 16
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; Entry veneers exist in the hidden ROM and the writable page at one address.
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ENDM
        MACRO LEAVE_R
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
; The original body with its entry registers; R afterwards = the entry R + the M1s the body really took.
        MACRO COPY_BODY body
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call body
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ENDM
        MACRO R_DONE
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        ENDM

; ---- a figure moves: its old place off and its new place on, then the original's 8C63
h_both:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BE0             ; the game's own set-up for the old place: BC masks, DE graphic, 7D2F place
        call l2_toggle
        call 0x8BCA             ; and for the new
        call l2_toggle
        COPY_BODY 0x8C63
        R_DONE
        LEAVE_R
        ret

; ---- one plot at the old place (8C4E) -----------------------------------------
h_old:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BE0
        call l2_toggle
        COPY_BODY 0x8C4E
        R_DONE
        LEAVE_R
        ret

; ---- one plot at the new place (8C5D) -----------------------------------------
h_new:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call 0x8BCA
        call l2_toggle
        COPY_BODY 0x8C5D
        R_DONE
        LEAVE_R
        ret

; ---- the room is drawn over everything (881D): the overlay starts empty, and shows ---
h_room:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        ld d,L2_BANK*2
        ld e,6
.pg:    ld a,d
        nextreg 0x57,a
        ld hl,0xE000
        ld (hl),0xFF
        push de
        ld de,0xE001
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        nextreg 0x57,1
        nextreg 0x69,0x80
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        COPY_BODY 0x881D
        ld a,(V_SPEED)
        ld c,a
        ld a,K_ROOM
        call hlib_pace_waitk
        R_DONE
        LEAVE_R
        ret

; ---- the ROM clears the screen (0DAF): the overlay goes off until the next room ----
h_cls:
        ENTER
        nextreg 0x69,0
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x0DAF

; l2_toggle: C and B the wrap masks, DE the graphic as the game set them, (7D2F) y, (7D30) x. 16 rows of three bytes.
l2_toggle:
        ld a,c
        ld (P_C),a
        ld a,b
        ld (P_B),a
        ld a,(0x7D2F)
        ld (P_Y),a
        ld a,(0x7D30)
        and 0xF8
        ld (P_X),a
        ld a,16
        ld (P_ROWS),a
.row:   ld a,(P_Y)
        ld c,a
        and 31
        or 0xE0
        ld h,a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        add a,L2_BANK*2
        nextreg 0x57,a
        ld a,(P_X)
        ld l,a
        ld a,(P_C)
        ld c,a
        ld a,(de)
        and c
        call .byte
        inc de
        ld a,(de)
        call .byte
        dec de
        ld a,(P_B)
        ld c,a
        ld a,(de)
        and c
        call .byte
        inc de
        inc de
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jr nz,.row
        nextreg 0x57,1
        ret
.byte:  or a
        jr nz,.pix
        ld a,l
        add a,8
        ld l,a
        ret
.pix:   ld b,a
        ld c,8
.lp:    rl b
        jr nc,.n
        ld a,(hl)
        xor TOGGLE
        ld (hl),a
.n:     inc l
        dec c
        jr nz,.lp
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "pp_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_BANK
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,7
        nextreg 0x41,0xFF
        nextreg 0x40,254
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x43,0
        ld d,L2_BANK*2
        ld e,6
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
        nextreg 0x50,255
        ret
setup_end:
        SAVEBIN "pp_setup.bin",setup,setup_end-setup
