; Scooby Doo Enhanced (Spec256 colours by Armando Quaranta): the play window on a double-buffered Layer 2.
;
; The game composes a buffer (9FCC, 32 bytes a row, 128 rows) and copies it to the ULA after each HALT. Colour
; canvas: one byte of RAM = 8 pixels = 8 bytes, so any address A has its colours at page CBASE + A/1024, offset
; (A & 1023) * 8. Graphics in the canvas are the set's own planes. The game mirrors sprites in place, flagged in bit 7
; of the sprite's table entry; the canvas holds each sprite both ways, the mirrored way MOFF pages up.
; The game takes its figures off the buffer at the start of each update and puts them back at the end. The canvas holds
; the scenery only: the picture is the scenery copied to the back buffer with this update's figures plotted on it. That
; is the buffer's own picture as long as the game draws no permanent block over a figure; the replay checks it.
;
; The game's interrupt plays its sound through the ROM's beeper, on its own time, so nothing may run at 28 MHz or with
; the slots changed while an interrupt can come. So the write hooks only note what is about to happen: they run at the
; game's clock with the slots as they are but slot 1, and put a record in a queue. All the colour work is done in one
; place: the copy at 8464, just after the HALT, which at 28 MHz takes a fraction of its 3.5 MHz time. There, with
; interrupts off, the game's own copy runs, then the queue, the picture, the flip; when the interrupt's line comes near
; it stops, opens interrupts at the game's clock with the slots as the game's, and goes on after it.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_BACK EQU 0x3E34              ; L2 bank of the back buffer
V_DMA EQU 0x3E35               ; 1: ordinary DMA
V_QT EQU 0x3E36                ; word: queue tail
V_K EQU 0x3E38                 ; the record: kind
V_A EQU 0x3E39                 ; rows
V_B EQU 0x3E3A                 ; bytes a row
V_C EQU 0x3E3B                 ; source step
V_S EQU 0x3E3C                 ; word: source
V_D EQU 0x3E3E                 ; word: destination
V_X EQU 0x3E40                 ; word: mask, destination step or length
REC EQU 10
V_QH EQU 0x3E42                ; word: queue head
V_R0 EQU 0x3E44
V_IFF EQU 0x3E45               ; 1: interrupts were on
V_SP6 EQU 0x3E46
V_N EQU 0x3E48                 ; word: slice
V_CP EQU 0x3E4A                ; publish: canvas page
V_LP EQU 0x3E4B                ; publish: Layer 2 page
V_CO EQU 0x3E4C                ; word: canvas offset
V_LO EQU 0x3E4E                ; word: Layer 2 offset
V_REM EQU 0x3E50               ; word: bytes left
V_PG EQU 0x3E52                ; word: the player's graphic, as the copy reads it
V_PM EQU 0x3E54                ; word: the player's mask
V_PT EQU 0x3E56                ; cells above the player's band
V_PN EQU 0x3E57                ; cells in it
V_SPX EQU 0x3E58
V_PF EQU 0x3E5A                ; the player's graphic mirrored: 0x80
V_PFM EQU 0x3E5B               ; and its mask
V_W EQU 0x3E5C                 ; word: where the queue's kept records end
V_PEND EQU 0x3E5E              ; a picture waits for its flip
V_DP EQU 0x3E60                ; word: figure rows: destination pointer
V_GP EQU 0x3E62                ; word: graphic pointer
V_MP EQU 0x3E64                ; word: mask pointer
V_ST EQU 0x3E66                ; word: their step
V_LPG EQU 0x3E68               ; destination's page in slot 4
V_U EQU 0x3E69                 ; units of 4 pixels a row
V_NR EQU 0x3E6A                ; rows left in this chunk
V_NC EQU 0x3E6B                ; rows in this chunk
V_SPG EQU 0x3E6C               ; source's page in slot 6
V_DPG EQU 0x3E6D               ; destination's page in slot 4
V_E1 EQU 0x3E6E                ; word: table entry of the player's graphic, last time
V_E2 EQU 0x3E70                ; word: and of its mask
CHUNK EQU 8                    ; rows between looks at the beam
K_BLOCK EQU 0
K_PLOT EQU 1
K_FILL EQU 3
K_PAT EQU 4
K_FWD EQU 5
K_BACK EQU 6
K_NIB EQU 7                    ; 7-10: + 8F99's two clip bits
MOFF EQU 24                    ; pages up to a sprite's mirrored image
CBASE EQU 3                    ; canvas page of address 0 (only 0x9400 up exist): page = CBASE + A / 1024
PAL_PAGE EQU 26
L2_BANK_A EQU 14
L2_BANK_B EQU 17
BUF EQU 0x9FCC
WIN_ROWS EQU 128
PX EQU 112                     ; the player's band, column 14
INT_LINE EQU 248               ; the frame interrupt, in lines from the first ULA row
MARGIN EQU 26                  ; lines: longer than any one step of the work
        ORG 0x2000
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_pace.asm"

        MACRO C_IN
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ENDM
        MACRO C_END delta, ven
        ld a,(V_PEND)
        or a
        call nz,try_flip
        ld a,127&(delta-2)
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        jp ven
        ENDM
        MACRO C_OUT delta, ven
        call qpush
        C_END delta, ven
        ENDM
        ; the scroll: the record, then the game's own chain at 28 MHz, past the interrupt's lines
        MACRO SCR chain, ven
        call qpush
        call clear_int
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call chain
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,127&(R_S-2)
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        ld a,(V_IFF)
        or a
        jr z,1F
        ei
1:      pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        jp ven
        ENDM
        MACRO BLK rows, w, ss, ds
        ld hl,K_BLOCK+(rows)*256
        ld (V_K),hl
        ld hl,(w)+(ss)*256
        ld (V_B),hl
        ld hl,ds
        ld (V_X),hl
        ENDM

; qpush: the record goes on the queue; a full queue is done at once.
qpush:  ld hl,(V_K)
        ld (qp1+1),hl
        ld de,(V_QT)
        ld hl,(V_B)
        ex de,hl
qp1:    ld bc,0
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_S)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_D)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_X)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (V_QT),hl
        ex de,hl
        ld hl,QLIMIT
        or a
        sbc hl,de
        ret nc
        HLIB_IFF_DI
        ld a,0
        jp po,.off
        inc a
.off:   ld (V_IFF),a
        HLIB_SPEED_IN_ABC V_SPEED
        call flush
        call slots
        HLIB_SPEED_OUT_A V_SPEED
        ld a,(V_IFF)
        or a
        ret z
        ei
        ret

; clear_int: past the interrupt's lines if they are near (the scroll takes about 4 ms), then interrupts off, 28 MHz.
clear_int:
        HLIB_IFF_DI
        ld a,0
        jp po,.off
        inc a
.off:   ld (V_IFF),a
        or a
        jr z,.go
        ei
.w:     call hlib_line
        ld de,INT_LINE-80
        or a
        sbc hl,de
        jr c,.d
        ld de,83
        or a
        sbc hl,de
        jr c,.w
.d:     di
.go:    HLIB_SPEED_IN_ABC V_SPEED
        ret

; ---- the write hooks -------------------------------------------------------
c_s1:   C_IN                    ; 8D67: 40 rows of a tile's column, every second byte
        ld (V_S),hl
        ld (V_D),de
        BLK 40,1,2,1
        C_OUT -13, x_s1
c_s2:   C_IN                    ; 8D6F: 16 bytes from FFC0
        ld (V_D),de
        ld hl,0xFFC0
        ld (V_S),hl
        BLK 1,16,0,0
        C_OUT -13, x_s2
c_s3:   C_IN                    ; 8D85: 8 rows, every fourth byte
        ld (V_S),hl
        ld (V_D),de
        BLK 8,1,4,1
        C_OUT -13, x_s3
c_s4:   C_IN                    ; 8A7A: an object's column
        ld (V_S),hl
        ld (V_D),de
        ld a,c
        ld hl,K_BLOCK+1*256     ; rows set below
        ld (V_K),hl
        ld (V_C),a
        ld a,1
        ld (V_B),a
        ld hl,1
        ld (V_X),hl
        ld a,(0x61D9)
        ld (V_A),a
        call obj_flag
        ld (V_K),a
        C_OUT -13, x_s4
c_s5:   C_IN                    ; 8E0C: the finished column to the buffer (its 128 rows; the rest are attributes)
        ld (V_D),hl
        ld (V_S),de
        BLK 128,1,1,32
        C_OUT -13, x_s5
c_sl:   C_IN                    ; 8550: the buffer a byte left
        ld hl,K_FWD
        ld (V_K),hl
        ld hl,BUF+1
        ld (V_S),hl
        ld hl,BUF
        ld (V_D),hl
        ld hl,0x0FFF
        ld (V_X),hl
        SCR 0x848E, x_sl
c_sr:   C_IN                    ; 8532: a byte right
        ld hl,K_BACK
        ld (V_K),hl
        ld hl,0xAFCA
        ld (V_S),hl
        ld hl,0xAFCB
        ld (V_D),hl
        ld hl,0x0FFF
        ld (V_X),hl
        SCR 0x84D3, x_sr
c_su:   C_IN                    ; 8571: a cell up
        ld hl,K_FWD
        ld (V_K),hl
        ld hl,0xA0CC
        ld (V_S),hl
        ld hl,BUF
        ld (V_D),hl
        ld hl,0x0F00
        ld (V_X),hl
        SCR 0x848E, x_su
c_sd:   C_IN                    ; 8598: a cell down
        ld hl,K_BACK
        ld (V_K),hl
        ld hl,0xAECB
        ld (V_S),hl
        ld hl,0xAFCB
        ld (V_D),hl
        ld hl,0x0F00
        ld (V_X),hl
        SCR 0x84D3, x_sd
c_r1:   C_IN                    ; 8E71: a row's source, 4 bytes twice, 8 rows
        ld (V_S),hl
        ld hl,0x969F
        ld (V_D),hl
        BLK 8,4,4,8
        call qpush
        pop hl
        push hl
        ld (V_S),hl
        ld hl,0x96A3
        ld (V_D),hl
        BLK 8,4,4,8
        C_OUT -13, x_r1
c_r2:   C_IN                    ; 8E97: the row's source cleared
        ld hl,K_FILL
        ld (V_K),hl
        ld hl,0x969F
        ld (V_D),hl
        ld hl,65
        ld (V_X),hl
        C_OUT -13, x_r2
c_r3:   C_IN                    ; 8EBE: 2 bytes four times, 8 rows
        ld (V_S),hl
        ld hl,0x969F
        ld (V_D),hl
        BLK 8,2,2,8
        call qpush
        pop hl
        push hl
        ld (V_S),hl
        ld hl,0x96A1
        ld (V_D),hl
        BLK 8,2,2,8
        call qpush
        pop hl
        push hl
        ld (V_S),hl
        ld hl,0x96A3
        ld (V_D),hl
        BLK 8,2,2,8
        call qpush
        pop hl
        push hl
        ld (V_S),hl
        ld hl,0x96A5
        ld (V_D),hl
        BLK 8,2,2,8
        C_OUT -13, x_r3
c_r4:   C_IN                    ; 8EFA: the new row: 4 bytes, then repeated along the row
        ld (V_S),hl
        ld hl,(0x8CD0)
        ld (V_D),hl
        BLK 8,4,8,32
        call qpush
        ld hl,(0x8CD0)
        ld (V_D),hl
        ld hl,K_PAT+8*256
        ld (V_K),hl
        C_OUT -13, x_r4
c_r5:   C_IN                    ; 8B99: an object in the new row
        ld hl,(0x61D7)
        ld (V_S),hl
        ld hl,(0x8CD0)
        ld (V_D),hl
        ld hl,K_BLOCK+8*256
        ld (V_K),hl
        ld a,(0x61DA)
        ld (V_B),a
        ld a,(0x8F95)
        ld (V_C),a
        ld hl,32
        ld (V_X),hl
        call obj_flag
        ld (V_K),a
        C_OUT -13, x_r5
c_plot: C_IN                    ; 9180: mask and graphic, byte aligned
        ld (V_D),hl
        call plot_args
        or K_PLOT
        ld (V_K),a
        C_OUT -13, x_plot
c_nib:  C_IN                    ; 91BA: mask and graphic, half a byte along
        ld (V_D),hl
        call plot_args
        ld b,a
        ld a,(0x8F99)
        and 3
        add a,K_NIB
        or b
        ld (V_K),a
        C_OUT -13, x_nib
c_ldir: C_IN                    ; 9237: a block, no mask
        ld (V_D),hl
        ld hl,(0x61D7)
        ld (V_S),hl
        ld a,(0x61D9)
        ld (V_A),a
        ld a,(0x61DA)
        ld (V_B),a
        ld a,(0x8F95)
        ld (V_C),a
        ld hl,32
        ld (V_X),hl
        ld a,(0x8FA0)
        call ent_bit
        ld (V_K),a              ; K_BLOCK is 0: the graphic's way round only
        C_OUT -13, x_ldir
c_hide: C_IN                    ; 6F3B: out of play
        nextreg 0x69,0
        C_END -12, x_hide

; ent_bit: A = sprite number -> A = bit 7 of its table entry's last byte: mirrored or not. HL, DE lost.
ent_bit:
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,0xB407
        add hl,de
        ld a,(hl)
        and 0x80
        ret

; obj_flag: an object in the scenery: its sprite as the game works it out at 89F5 / 8ADE -> A = 0x80 if mirrored.
obj_flag:
        ld a,(0x8CDA)
        cp 0x84
        jr nz,.n
        ld a,(0x61E8)
        cp 6
        jr c,.a
        ld a,5
.a:     add a,0x83
.n:     jr ent_bit

; plot_args: the plot's fields; A = 0x80 graphic mirrored, + 0x40 mask mirrored.
plot_args:
        ld hl,(0x61D7)
        ld (V_S),hl
        ld hl,(0xB400)
        ld (V_X),hl
        ld a,(0x61D9)
        ld (V_A),a
        ld a,(0x61DA)
        ld (V_B),a
        ld a,(0x8F95)
        ld (V_C),a
        ld a,(0x8F9F)
        call ent_bit
        rrca
        ld b,a
        ld a,(0x8FA0)
        call ent_bit
        or b
        ret

; ---- the copy: after the HALT ----------------------------------------------
c_copy: C_IN
        ld a,1
        ld (V_IFF),a
        di
        HLIB_SPEED_IN_ABC V_SPEED
        ld a,(V_PEND)
        or a
        call nz,flip
        ld hl,(0x61B1)
        ld (V_PG),hl
        ld hl,(0x61B3)
        ld (V_PM),hl
        ld a,(0x61B5)
        ld (V_PT),a
        ld a,(0x61B6)
        ld (V_PN),a
        ld de,(V_PG)
        ld bc,V_E1
        call ptr_bit
        ld (V_PF),a
        ld de,(V_PM)
        ld bc,V_E2
        call ptr_bit
        ld (V_PFM),a
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call 0x82E3
        ld a,(0x61B6)
        and a
        call nz,0x837E
        ld a,(0x61B7)
        and a
        call nz,0x82E3
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        push ix
        call flush
        call publish
        pop ix
        call slots
        ld a,127&(R_COPY-2)
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
        ei
        jp x_copy
R_COPY EQU -22
R_S EQU -21

; ptr_bit: DE = a sprite's address, BC = where its table entry was last found -> A = 0x80 if the entry is mirrored. HL lost.
ptr_bit:
        ld a,(bc)
        ld l,a
        inc bc
        ld a,(bc)
        dec bc
        ld h,a
        or a
        jr z,.scan
        ld a,(hl)
        cp e
        jr nz,.scan
        inc hl
        ld a,(hl)
        cp d
        jr nz,.scan
        dec hl
        jr .got
.scan:  ld hl,0xB404
.lp:    ld a,(hl)
        cp e
        jr nz,.nx
        inc hl
        ld a,(hl)
        dec hl
        cp d
        jr nz,.nx
        inc hl                  ; an empty entry can hold the same address: it has no rows
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        add a,a
        add a,a
        add a,a
        jr nz,.got
.nx:    inc hl
        inc hl
        inc hl
        inc hl
        ld a,h
        cp 0xB7
        jr nz,.lp
        ld a,l
        cp 0xA0
        jr c,.lp
        xor a
        ret
.got:   ld a,l
        ld (bc),a
        inc bc
        ld a,h
        ld (bc),a
        inc hl
        inc hl
        inc hl
        ld a,(hl)
        and 0x80
        ret

; ---- the queue: flush does the scenery, in order, and keeps the figures' records for after the picture is copied ----
flush:  ld hl,QSTART
        ld (V_QH),hl
        ld (V_W),hl
.lp:    ld hl,(V_QH)
        ld de,(V_QT)
        or a
        sbc hl,de
        jr z,.dn
        call safe
        ld hl,(V_QH)
        ld de,V_K
        ld bc,REC
        ldir
        ld (V_QH),hl
fl_go:  ld a,(V_K)
        and 0x3F
        cp K_PLOT
        jr z,flush.keep
        cp K_NIB
        jr nc,flush.keep
        add a,a
        ld l,a
        ld h,0
        ld de,optab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        call flags
        ld de,flush.lp
        push de
        jp (hl)
flush.keep:
        ld hl,V_K
        ld de,(V_W)
        ld bc,REC
        ldir
        ld (V_W),de
        jr flush.lp
flush.dn:
        ld hl,(V_W)
        ld (V_QT),hl
        ret
optab:  dw op_block,0,0,op_fill,op_pat,op_fwd,op_back

; flags: the record's mirrored bits into the page sums of map_s and map_m. HL kept.
flags:  ld a,(V_K)
        ld b,a
        and 0x80
        jr z,.s
        ld a,MOFF
.s:     ld (map_s.add+1),a
        ld a,b
        and 0x40
        jr z,.m
        ld a,MOFF
.m:     ld (map_m.add+1),a
        ret

; figures: the kept records, on the back buffer.
figures:
        ld hl,QSTART
        ld (V_QH),hl
.lp:    ld hl,(V_QH)
        ld de,(V_QT)
        or a
        sbc hl,de
        jr z,.dn
        call safe
        ld hl,(V_QH)
        ld de,V_K
        ld bc,REC
        ldir
        ld (V_QH),hl
        call flags
        ld a,(V_K)
        and 0x3F
        cp K_PLOT
        ld de,figures.lp
        push de
        jp z,op_plot
        jp op_nib
.dn:    ld hl,QSTART
        ld (V_QT),hl
        ret

; safe: outside the interrupt's lines, return. Inside: as the game has it (slots, clock, interrupts) until it is past.
safe:   call hlib_line
        ld de,INT_LINE-MARGIN
        or a
        sbc hl,de
        ret c
        ld de,MARGIN+3
        or a
        sbc hl,de
        ret nc
        ld a,(V_IFF)
        or a
        ret z
        call slots
        HLIB_SPEED_OUT_A V_SPEED
        ei
.w:     call hlib_line
        ld de,INT_LINE-MARGIN
        or a
        sbc hl,de
        jr c,.out
        ld de,MARGIN+3
        or a
        sbc hl,de
        jr c,.w
.out:   di
        nextreg 0x07,3
        ret

slots:  nextreg 0x52,10
        nextreg 0x53,11
        nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x56,0
        nextreg 0x57,1
        ret

; map_d: HL = RAM address -> slots 4, 5 hold its canvas; HL = its canvas address there. AF lost.
map_d:  ld a,h
        srl a
        srl a
        add a,CBASE
        nextreg 0x54,a
        inc a
        nextreg 0x55,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ret

; map_s: DE = RAM address -> slots 6, 7; DE = its canvas address there. AF lost.
map_s:  ld a,d
        srl a
        srl a
        add a,CBASE
.add:   add a,0
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld a,d
        and 3
        ld d,a
        sla e
        rl d
        sla e
        rl d
        sla e
        rl d
        ld a,d
        or 0xC0
        ld d,a
        ret

; map_m: HL = RAM address -> slots 2, 3; HL = its canvas address there. AF lost.
map_m:  ld a,h
        srl a
        srl a
        add a,CBASE
.add:   add a,0
        nextreg 0x52,a
        inc a
        nextreg 0x53,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 6,h
        ret

; map_l: HL = an address in the buffer -> slots 4, 5 hold it on the back buffer; HL = its address there. AF, DE lost.
map_l:  ld de,0x10000-BUF
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld d,a
        ld a,(V_BACK)
        add a,a
        add a,d
        ld (V_LPG),a
        nextreg 0x54,a
        inc a
        nextreg 0x55,a
        ld a,h
        and 0x1F
        or 0x80
        ld h,a
        ret

; blit: HL source, DE destination, BC bytes, forward; overlap with the destination behind is right.
blit:   ld a,(V_DMA)
        or a
        jr z,.cpu
        ld a,b
        or a
        jr nz,.dma
        ld a,c
        cp 40
        jr c,.cpu
.dma:   ld (d_src),hl
        ld (d_len),bc
        ld (d_dst),de
        ld hl,d_pkt
        ld bc,(d_end-d_pkt)*256+0x6B
        otir
        ret
.cpu:   ldir
        ret
; blit_down: HL source's last byte, DE destination's last byte, BC bytes, backward.
blit_down:
        ld a,(V_DMA)
        or a
        jr z,.cpu
        ld (e_src),hl
        ld (e_len),bc
        ld (e_dst),de
        ld hl,e_pkt
        ld bc,(e_end-e_pkt)*256+0x6B
        otir
        ret
.cpu:   lddr
        ret
e_pkt:  db 0x83,0xC3,0x7D
e_src:  dw 0
e_len:  dw 0
        db 0x44,0x02,0x40,0x02,0xAD
e_dst:  dw 0
        db 0x82,0xCF,0x87
e_end:
d_pkt:  db 0x83,0xC3,0x7D
d_src:  dw 0
d_len:  dw 0
        db 0x54,0x02,0x50,0x02,0xAD
d_dst:  dw 0
        db 0x82,0xCF,0x87
d_end:

; step: V_S += V_C, V_D += V_X; the rows count down, Z when none is left.
step:   ld hl,(V_S)
        ld a,(V_C)
        ld e,a
        ld d,0
        add hl,de
        ld (V_S),hl
        ld hl,(V_D)
        ld de,(V_X)
        add hl,de
        ld (V_D),hl
        ld hl,V_A
        dec (hl)
        ret

op_block:
.again: call safe
        call chunk
        ld a,(V_B)
        cp 8
        jr c,.small
        ; a wide block: DMA, a row at a time
.w:     ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ex de,hl
        ld a,(V_B)
        ld c,a
        ld b,0
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        call blit
        call step
        ret z
        ld hl,V_NR
        dec (hl)
        jr nz,.w
        jr .again
.small: ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ex de,hl                ; HL source (slots 6, 7), DE destination (slots 4, 5)
        ld a,(V_S+1)
        srl a
        srl a
        add a,CBASE
        ld (V_SPG),a
        ld a,(map_s.add+1)
        ld b,a
        ld a,(V_SPG)
        add a,b
        ld (V_SPG),a
        ld a,(V_D+1)
        srl a
        srl a
        add a,CBASE
        ld (V_DPG),a
        ld a,(V_X)
        add a,a
        add a,a
        add a,a                 ; destination step: a row of 32 is 0, and the page below takes it
        ld (.dl+1),a
        ld a,(V_X+1)
        or a
        ld a,(V_X)
        ld b,0
        cp 32
        jr nz,.ds
        inc b
.ds:    ld a,b
        ld (.dh+1),a
.rw:    ld a,(V_B)
.ldi:   ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        dec a
        jr nz,.ldi
        ; on to the next row: back to the row's start and one step on
        ld a,(V_B)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld b,0
        ex de,hl
        or a
        sbc hl,bc
.dl:    ld a,0
        add a,l
        ld l,a
        jr nc,.dh
        inc h
.dh:    ld a,0
        add a,h
        ld h,a
        cp 0xA0
        jr c,.d1
        sub 0x20
        ld h,a
        ld a,(V_DPG)
        inc a
        ld (V_DPG),a
        nextreg 0x54,a
        inc a
        nextreg 0x55,a
.d1:    ex de,hl
        or a
        sbc hl,bc
        ld bc,(V_ST)
        add hl,bc
        ld a,h
        cp 0xE0
        jr c,.s1
        sub 0x20
        ld h,a
        ld a,(V_SPG)
        inc a
        ld (V_SPG),a
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
.s1:    ld a,(V_NR)
        dec a
        ld (V_NR),a
        jr nz,.rw
        ; the record past this chunk
        ld a,(V_NC)
        ld d,a
        ld a,(V_C)
        ld e,a
        mul d,e
        ld hl,(V_S)
        add hl,de
        ld (V_S),hl
        ld a,(V_NC)
        ld d,a
        ld a,(V_X)
        ld e,a
        mul d,e
        ld hl,(V_D)
        add hl,de
        ld (V_D),hl
        ld a,(V_NC)
        ld b,a
        ld a,(V_A)
        sub b
        ld (V_A),a
        jp nz,.again
        ret

op_pat: ld hl,(V_D)
        ld (V_S),hl
.row:   ld hl,(V_D)
        call map_d
        ld d,h
        ld e,l
        push hl
        ld hl,32
        add hl,de
        ex de,hl
        pop hl
        ld bc,224
        call blit
        ld hl,(V_D)
        ld de,32
        add hl,de
        ld (V_D),hl
        ld hl,V_A
        dec (hl)
        jr nz,.row
        ret

op_fill:
        ld hl,(V_D)
        call map_d
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        ld bc,(V_X)
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        dec bc
        jp blit

; prow: HL destination, DE graphic, BC mask, A = units of 4 pixels. The mask is read through the stack pointer: interrupts are off.
prow:   ld ixl,a
        ld (.o+1),bc
        ld (V_SPX),sp
.o:     ld sp,0
.px:    pop bc
        ld a,c
        and (hl)
        ex de,hl
        or (hl)
        ex de,hl
        ld (hl),a
        inc hl
        inc de
        ld a,b
        and (hl)
        ex de,hl
        or (hl)
        ex de,hl
        ld (hl),a
        inc hl
        inc de
        pop bc
        ld a,c
        and (hl)
        ex de,hl
        or (hl)
        ex de,hl
        ld (hl),a
        inc hl
        inc de
        ld a,b
        and (hl)
        ex de,hl
        or (hl)
        ex de,hl
        ld (hl),a
        inc hl
        inc de
        dec ixl
        jp nz,.px
        ld sp,(V_SPX)
        ret

op_plot:
.again: call safe
        call chunk
        ld hl,(V_D)
        call map_l
        ld (V_DP),hl
        ld hl,(V_X)
        call map_m
        ld (V_MP),hl
        ld de,(V_S)
        call map_s
        ld (V_GP),de
        ld a,(V_B)
        add a,a
        ld (V_U),a
        call plot_rows
        call advance
        jr nz,.again
        ret

; chunk: this many rows now; their step in canvas bytes.
chunk:  ld a,(V_B)
        cp 9
        ld b,CHUNK
        jr c,.b
        ld b,CHUNK/2            ; a wide sprite
.b:     ld a,(V_A)
        cp b
        jr c,.a
        ld a,b
.a:     ld (V_NC),a
        ld (V_NR),a
        ld a,(V_C)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld (V_ST),hl
        ret

; plot_rows: V_NR rows from the pointers. The destination's window moves on when it leaves slot 5.
plot_rows:
.row:   ld hl,(V_DP)
        ld de,(V_GP)
        ld bc,(V_MP)
        ld a,(V_U)
        or a
        call nz,prow
        ld de,(V_ST)
        ld hl,(V_GP)
        add hl,de
        ld (V_GP),hl
        ld hl,(V_MP)
        add hl,de
        ld (V_MP),hl
        ld hl,(V_DP)
        inc h
        ld a,h
        cp 0xC0
        jr c,.w
        sub 0x20
        ld h,a
        ld a,(V_LPG)
        inc a
        ld (V_LPG),a
        nextreg 0x54,a
        inc a
        nextreg 0x55,a
.w:     ld (V_DP),hl
        ld hl,V_NR
        dec (hl)
        jr nz,.row
        ret

; advance: the record past this chunk. Z when no rows are left.
advance:
        ld a,(V_NC)
        ld d,a
        ld a,(V_C)
        ld e,a
        mul d,e
        ld hl,(V_S)
        add hl,de
        ld (V_S),hl
        ld hl,(V_X)
        add hl,de
        ld (V_X),hl
        ld a,(V_NC)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(V_D)
        add hl,de
        ld (V_D),hl
        ld a,(V_NC)
        ld b,a
        ld a,(V_A)
        sub b
        ld (V_A),a
        ret

; The half-byte plot: pixel i of the graphic and mask goes to pixel 4 + i of the destination, i from 0, or from -4 with
; the left clip (8F99 bit 0), to 8w, or 8w - 4 with the right clip (bit 1). With no bytes, the left clip's 4 pixels only.
op_nib:
.again: call safe
        call chunk
        ld a,(V_K)
        and 0x3F
        sub K_NIB
        ld c,a                  ; the clip bits
        push bc
        ld hl,(V_D)
        call map_l
        pop bc
        bit 0,c
        jr nz,.d1
        inc hl
        inc hl
        inc hl
        inc hl
.d1:    ld (V_DP),hl
        ld hl,(V_X)
        bit 0,c
        jr z,.m0
        dec hl
.m0:    call map_m
        bit 0,c
        jr z,.m1
        ld de,4
        add hl,de
.m1:    ld (V_MP),hl
        ld de,(V_S)
        bit 0,c
        jr z,.s0
        dec de
.s0:    call map_s
        bit 0,c
        jr z,.s1
        inc de
        inc de
        inc de
        inc de
.s1:    ld (V_GP),de
        ld a,(V_B)
        or a
        jr nz,.nz
        ld a,1                  ; the left clip's 4 pixels
        jr .go
.nz:    add a,a
        bit 0,c
        jr z,.l0
        inc a
.l0:    bit 1,c
        jr z,.go
        dec a
.go:    ld (V_U),a
        call plot_rows
        call advance
        jr nz,.again
        ret

; room1k: HL = bytes from address HL to the end of its 1K. DE kept.
room1k: ld a,h
        and 3
        ld b,a
        ld c,l
        ld hl,1024
        or a
        sbc hl,bc
        ret

op_fwd:
.lp:    call safe
        ld hl,(V_S)
        call room1k
        ex de,hl
        ld hl,(V_D)
        call room1k
        call less
        ex de,hl
        ld hl,(V_X)
        call less
        ld (V_N),hl
        ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ex de,hl
        ld bc,(V_N)
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        call blit
        ld de,(V_N)
        ld hl,(V_S)
        add hl,de
        ld (V_S),hl
        ld hl,(V_D)
        add hl,de
        ld (V_D),hl
        ld hl,(V_X)
        or a
        sbc hl,de
        ld (V_X),hl
        ld a,h
        or l
        jr nz,.lp
        ret

; less: HL = the lesser of HL and DE. DE kept.
less:   push hl
        or a
        sbc hl,de
        pop hl
        ret c
        ld h,d
        ld l,e
        ret

op_back:
.lp:    call safe
        ld hl,(V_S)
        ld a,h
        and 3
        ld h,a
        inc hl
        ex de,hl
        ld hl,(V_D)
        ld a,h
        and 3
        ld h,a
        inc hl
        call less
        ex de,hl
        ld hl,(V_X)
        call less
        ld (V_N),hl
        ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ex de,hl
        ld bc,7
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        ld bc,(V_N)
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        call blit_down
        ld de,(V_N)
        ld hl,(V_S)
        or a
        sbc hl,de
        ld (V_S),hl
        ld hl,(V_D)
        or a
        sbc hl,de
        ld (V_D),hl
        ld hl,(V_X)
        or a
        sbc hl,de
        ld (V_X),hl
        ld a,h
        or l
        jr nz,.lp
        ret

; ---- the picture: the canvas to the back buffer, the player on it, the flip -----
publish:
        ld a,CBASE+(BUF>>10)
        ld (V_CP),a
        ld hl,(BUF&1023)*8
        ld (V_CO),hl
        ld a,(V_BACK)
        add a,a
        ld (V_LP),a
        ld hl,0
        ld (V_LO),hl
        ld hl,WIN_ROWS*256
        ld (V_REM),hl
.lp:    call safe
        ld hl,8192
        ld de,(V_CO)
        or a
        sbc hl,de
        ex de,hl
        ld hl,8192
        ld bc,(V_LO)
        or a
        sbc hl,bc
        call less
        ex de,hl
        ld hl,(V_REM)
        call less
        ld (V_N),hl
        ld a,(V_CP)
        nextreg 0x54,a
        ld a,(V_LP)
        nextreg 0x56,a
        ld hl,(V_CO)
        set 7,h
        ld de,(V_LO)
        ld a,d
        or 0xC0
        ld d,a
        ld bc,(V_N)
        call blit
        ld de,(V_N)
        ld hl,(V_REM)
        or a
        sbc hl,de
        ld (V_REM),hl
        ld hl,(V_CO)
        add hl,de
        ld a,h
        cp 0x20
        jr c,.c1
        ld hl,0
        ld a,(V_CP)
        inc a
        ld (V_CP),a
.c1:    ld (V_CO),hl
        ld hl,(V_LO)
        add hl,de
        ld a,h
        cp 0x20
        jr c,.c2
        ld hl,0
        ld a,(V_LP)
        inc a
        ld (V_LP),a
.c2:    ld (V_LO),hl
        ld hl,(V_REM)
        ld a,h
        or l
        jp nz,.lp
        call figures
        ; the player, which the copy lays over columns 14-17 of its band
        ld a,(V_PN)
        or a
        jr z,.nop
        add a,a
        add a,a
        add a,a
        ld (V_A),a              ; rows
        ld a,(V_PT)
        ld l,a
        ld h,0
        add hl,hl               ; cells x 256 = y x 32
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,BUF+14
        add hl,de
        ld (V_D),hl
        ld hl,(V_PG)
        ld (V_S),hl
        ld hl,(V_PM)
        ld (V_X),hl
        ld a,4
        ld (V_B),a
        ld (V_C),a
        ld a,(V_PFM)
        rrca
        ld b,a
        ld a,(V_PF)
        or b
        ld (V_K),a
        call flags
        call op_plot
.nop:   ld a,1
        ld (V_PEND),a
        ; the flip waits for the beam to leave the window's rows: now, or at a later hook
try_flip:
        call hlib_line
        ld de,WIN_ROWS
        or a
        sbc hl,de
        ret c
flip:   xor a
        ld (V_PEND),a
        ld a,(V_BACK)
        nextreg 0x12,a
        cp L2_BANK_A
        ld a,L2_BANK_A
        jr nz,.st
        ld a,L2_BANK_B
.st:    ld (V_BACK),a
        nextreg 0x69,0x80
        ret
QSTART:
QLIMIT EQU 0x3860-REC
        ASSERT QSTART < 0x3300

; Veneers: in the hidden ROM and in the page at one address, in Sinclair's unused 0x386E-0x3BFF.
        ORG 0x3870
ven_start:
h_s1:   nextreg 0x51,HOOK_PAGE
        jp c_s1
x_s1:   nextreg 0x51,255
        ld bc,0x2828
        jp 0x8D6A
h_s2:   nextreg 0x51,HOOK_PAGE
        jp c_s2
x_s2:   nextreg 0x51,255
        ld hl,0xFFC0
        jp 0x8D72
h_s3:   nextreg 0x51,HOOK_PAGE
        jp c_s3
x_s3:   nextreg 0x51,255
        ld bc,0x0830
        jp 0x8D88
h_s4:   nextreg 0x51,HOOK_PAGE
        jp c_s4
x_s4:   nextreg 0x51,255
        ld a,(0x61D9)
        jp 0x8A7D
h_s5:   nextreg 0x51,HOOK_PAGE
        jp c_s5
x_s5:   nextreg 0x51,255
        ld ix,0xB400
        jp 0x8E10
h_sl:   nextreg 0x51,HOOK_PAGE
        jp c_sl
x_sl:   nextreg 0x51,255
        jp 0x8553
h_sr:   nextreg 0x51,HOOK_PAGE
        jp c_sr
x_sr:   nextreg 0x51,255
        jp 0x8535
h_su:   nextreg 0x51,HOOK_PAGE
        jp c_su
x_su:   nextreg 0x51,255
        jp 0x8574
h_sd:   nextreg 0x51,HOOK_PAGE
        jp c_sd
x_sd:   nextreg 0x51,255
        jp 0x859B
h_r1:   nextreg 0x51,HOOK_PAGE
        jp c_r1
x_r1:   nextreg 0x51,255
        ld de,0x969F
        jp 0x8E74
h_r2:   nextreg 0x51,HOOK_PAGE
        jp c_r2
x_r2:   nextreg 0x51,255
        ld hl,0x969F
        jp 0x8E9A
h_r3:   nextreg 0x51,HOOK_PAGE
        jp c_r3
x_r3:   nextreg 0x51,255
        ld de,0x969F
        jp 0x8EC1
h_r4:   nextreg 0x51,HOOK_PAGE
        jp c_r4
x_r4:   nextreg 0x51,255
        ld de,(0x8CD0)
        jp 0x8EFE
h_r5:   nextreg 0x51,HOOK_PAGE
        jp c_r5
x_r5:   nextreg 0x51,255
        ld de,(0x8CD0)
        jp 0x8B9D
h_plot: nextreg 0x51,HOOK_PAGE
        jp c_plot
x_plot: nextreg 0x51,255
        ld bc,(0x61D9)
        jp 0x9184
h_nib:  nextreg 0x51,HOOK_PAGE
        jp c_nib
x_nib:  nextreg 0x51,255
        ld bc,(0x61D9)
        jp 0x91BE
h_ldir: nextreg 0x51,HOOK_PAGE
        jp c_ldir
x_ldir: nextreg 0x51,255
        ld a,(0x61DA)
        jp 0x923A
h_hide: nextreg 0x51,HOOK_PAGE
        jp c_hide
x_hide: nextreg 0x51,255
        jp 0x7D5F
h_copy: nextreg 0x51,HOOK_PAGE
        jp c_copy
x_copy: nextreg 0x51,255
        jp 0x8475
ven_end:
        ASSERT $ < 0x3C00
rom_end:
regblock EQU 0x3C00
        SAVEBIN "scooby_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x70,0
        nextreg 0x12,L2_BANK_A
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,WIN_ROWS-1
        ; the Layer 2 palette
        nextreg 0x50,PAL_PAGE
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,0x0000
        ld bc,0x0000
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        nextreg 0x43,0
        ; DMA only on a core that has it and with no hardware IM2
        ld bc,0x243B
        ld a,0xC0
        out (c),a
        inc b
        in a,(c)
        ld e,0
        and 1
        jr nz,.nod
        dec b
        ld a,1
        out (c),a
        inc b
        in a,(c)
        cp 0xFF
        jr z,.nod
        cp 0x30
        jr c,.nod
        ld e,1
.nod:   nextreg 0x50,HOOK_PAGE
        ld a,e
        ld (V_DMA-0x2000),a
        ld a,L2_BANK_B
        ld (V_BACK-0x2000),a
        nextreg 0x50,255
        ret
setup_end:
        SAVEBIN "scooby_setup.bin",setup,setup_end-setup
