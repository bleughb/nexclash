; Gunrunner Enhanced (Spec256 colours by Jao Paulo): the play window on a double-buffered Layer 2.
;
; The game composes a back buffer (6A00, 34 bytes a row) and copies 125 rows of it to the ULA. The hooks mirror
; every write to that buffer on a colour canvas: one byte of RAM = 8 pixels = 8 bytes of canvas, so any address A
; has its colours at page CBASE + A/1024, offset (A & 1023) * 8. Graphics in the canvas are the set's own planes.
; A hook runs BEFORE the instruction it replaces, on the same state, then the game goes on: registers, R and RAM
; are the original's. The filler, the scroll and the copy run at 28 MHz in pace windows, which pay for the mirror.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_BACK EQU 0x3E34              ; L2 bank of the back buffer
V_DMA EQU 0x3E35               ; 1: ordinary DMA
V_ATTR EQU 0x3E36              ; attribute the palette was last set for
V_D EQU 0x3E38                 ; word: destination (RAM address)
V_S EQU 0x3E3A                 ; word: source
V_R EQU 0x3E3C                 ; rows
V_W EQU 0x3E3D                 ; bytes a row
V_SP6 EQU 0x3E3E               ; source page in slot 6
V_POLL EQU 0x3E40              ; word
V_X EQU 0x3E42
V_PEND EQU 0x3E46
V_R0 EQU 0x3E47
; The bodies' original time, in quarter 1/16 lines (T / 14 * 4): per byte, per row, once. A short body at 28 MHz lasts only
; a few lines, too coarse to scale by K, so its time comes from its rows and bytes.
K0_STAR EQU 857
V_ST EQU 0x3E48                ; 10 counters, 6 bytes of the star table
KB_TILE EQU 13
KR_TILE EQU 20
K0_TILE EQU 143
KB_FIG EQU 26
KR_FIG EQU 49
K0_FIG EQU 172
KB_BOX EQU 12
KR_BOX EQU 24
K0_BOX EQU 28
V_Y EQU 0x3E44
CBASE EQU 14                   ; canvas page of address 0 (only 0x6800 up exist): page = CBASE + A / 1024
PAL_PAGE EQU 26
L2_BANK_A EQU 14
L2_BANK_B EQU 17
ROW EQU 34
; The original's time, measured in JNext against the .z80 (ms x 250 = 1/16 lines, less the hook's own way in)
T_FILL EQU 7350
T_SCROLL EQU 5450
T_COPY EQU 4400
WIN_Y EQU 49
WIN_ROWS EQU 125
WIN_X EQU 24
SRC0 EQU 0x6A04
        ORG 0x2000
rom_start:
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; Entry and exit veneers (end of this file) exist in the hidden ROM and in the page at one address, in Sinclair's
; unused 0x386E-0x3CFF: this game's BASIC still runs on the ROM, so nothing else of the ROM may change.
        MACRO ENTER
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        HLIB_SPEED_IN_ABC V_SPEED
        ENDM
; Leave: slots back, R as the original's, registers restored, page restored. The bytes after the last NEXTREG run
; from the hidden ROM.
        MACRO LEAVE delta
        ld a,127&(delta-2)
        call hlib_r_set
        call slots
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        ENDM
        MACRO DEBT_IN
        call hlib_debt_open
        ENDM
        MACRO DEBT_OUT
        ld a,(V_PEND)
        or a
        call nz,try_flip
        ld a,23
        call hlib_debt_close
        ENDM

; The original's body run here at 28 MHz with the site's registers; V_R0 = the M1s it took, the wrapper's included.
        MACRO BODY fn, kb, kr, k0
        call slots
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call fn
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld b,kb
        ld c,kr
        ld de,k0
        call target
        ld a,(V_SPEED)
        call hlib_pace_wait
        ENDM
        MACRO LEAVE_B delta
        ld a,127&(delta-2)
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        call slots
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        ENDM

; target: HL = (V_R x V_W x B + V_R x C + DE) / 4
target: push de
        push bc
        ld a,(V_R)
        ld e,a
        ld a,(V_W)
        ld d,a
        mul d,e
        ex de,hl
        ld a,b
        call hlib_mul8
        pop bc
        push hl
        ld a,(V_R)
        ld l,a
        ld h,0
        ld a,c
        call hlib_mul8
        pop de
        add hl,de
        pop de
        add hl,de
        srl h
        rr l
        srl h
        rr l
        ret

slots:  nextreg 0x54,4
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

; map_s: DE = RAM address -> slots 6, 7 hold its canvas; DE = its canvas address there. AF lost.
map_s:  ld a,d
        srl a
        srl a
        add a,CBASE
        ld (V_SP6),a
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

; next_row: V_D += ROW, HL = its canvas (map_d). DE: the source's page moved on when it left slot 6. AF lost.
next_row:
        ld hl,(V_D)
        push de
        ld de,ROW
        add hl,de
        pop de
        ld (V_D),hl
        call map_d
        ld a,d
        cp 0xE0
        ret c
        sub 0x20
        ld d,a
        ld a,(V_SP6)
        inc a
        ld (V_SP6),a
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ret

; The row loops: V_D = first destination, V_S = source, V_R rows, V_W bytes a row. 8 canvas bytes a RAM byte.
        MACRO PASS op
        ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ld a,(V_R)
        ld c,a
.r:     ld a,(V_W)
        ld b,a
.c:     DUP 8
        ld a,(de)
        op
        ld (hl),a
        inc de
        inc hl
        EDUP
        djnz .c
        dec c
        ret z
        call next_row
        jr .r
        ENDM
pass_and:
        PASS <and (hl)>
pass_xor:
        PASS <xor (hl)>
pass_put:
        PASS <nop>

; The buffer's row, to or from a linear table (the save areas).
save_rows:                      ; V_D = buffer, V_S = table: table <- buffer
        ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ld a,(V_R)
.r:     push af
        ld a,(V_W)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld b,0
        jr nc,.n
        inc b
.n:     ldir
        call next_row
        pop af
        dec a
        jr nz,.r
        ret
rest_rows:                      ; V_D = buffer, V_S = table: buffer <- table
        ld de,(V_S)
        call map_s
        ld hl,(V_D)
        call map_d
        ld a,(V_R)
.r:     push af
        ld a,(V_W)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld b,0
        jr nc,.n
        inc b
.n:     ex de,hl
        ldir
        ex de,hl
        call next_row
        pop af
        dec a
        jr nz,.r
        ret

; blit: HL source, DE destination, BC bytes, forward; overlap with source below destination fills, as LDIR does.
blit:   ld a,(V_DMA)
        or a
        jr z,.cpu
        ld (d_src),hl
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
        db 0x04,0x00,0xAD
e_dst:  dw 0
        db 0x82,0xCF,0x87
e_end:
d_pkt:  db 0x83,0xC3,0x7D
d_src:  dw 0
d_len:  dw 0
        db 0x14,0x10,0xAD
d_dst:  dw 0
        db 0x82,0xCF,0x87
d_end:

; ---- D5B1: the buffer cleared -------------------------------------------------
b_clr:  ENTER
        DEBT_IN
        ld hl,0x6A00
        ld (V_D),hl
        ld hl,0x1101
        ld (V_S),hl             ; bytes left
.lp:    ld hl,(V_D)
        ld a,h
        and 3
        ld d,a
        ld e,l
        ld hl,1024
        or a
        sbc hl,de               ; room in this 1K
        ld de,(V_S)
        or a
        sbc hl,de
        jr c,.part
        ld hl,(V_S)             ; all that is left fits
        jr .go
.part:  add hl,de
.go:    ld b,h
        ld c,l                  ; bytes in this slice
        ld hl,(V_S)
        or a
        sbc hl,bc
        ld (V_S),hl
        ld hl,(V_D)
        push hl
        add hl,bc
        ld (V_D),hl
        pop hl
        call map_d
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        dec bc
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        call blit
        ld hl,(V_S)
        ld a,h
        or l
        jr nz,.lp
.d:     DEBT_OUT
        LEAVE -13
        jp x_clr

; ---- D986: one record of the scenery plotter ------------------------------------
b_tile:  ENTER
        DEBT_IN
        pop hl                  ; the record
        push hl
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        cp 0x96
        jr c,.y
        xor a
.y:     ld b,a
        inc hl
        ld c,(hl)               ; x
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; the sprite's definition
        push de
        ld e,b
        ld d,ROW
        mul d,e
        ld hl,0x6A00
        add hl,de
        ld b,0
        add hl,bc
        ld (V_D),hl
        pop de
        ld a,(de)
        add a,a
        add a,a
        add a,a
        ld (V_R),a
        inc de
        ld a,(de)
        ld (V_W),a
        inc de
        ld a,(de)
        inc de
        ld (V_S),de
        or a
        ld (V_R0+1),a           ; non-zero: AND and XOR passes
        jr z,.plain
        ld hl,(V_D)
        push hl
        call pass_and
        pop hl
        ld (V_D),hl
        ld hl,(V_S)             ; the XOR block follows the mask block
        ld a,(V_R)
        ld e,a
        ld a,(V_W)
        ld d,a
        mul d,e
        add hl,de
        ld (V_S),hl
        call pass_xor
        jr .d
.plain: call pass_put
.d:     DEBT_OUT
        call slots
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call f_tile
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,(V_R0+1)
        or a
        ld b,KB_TILE
        ld c,KR_TILE
        jr z,.one
        ld b,2*KB_TILE
        ld c,2*KR_TILE
.one:   ld de,K0_TILE
        call target
        ld a,(V_SPEED)
        call hlib_pace_wait
        LEAVE_B -24
        jp x_tile
f_tile: ld a,(hl)
        add a,a
        add a,a
        jp 0xD989
; DA0B, reached only inside f_tile: the record's end returns to the hook.
e_tile: inc hl
        ld a,(hl)
        cp 0xFF
        ret

; ---- 811D: a figure: AND with the mask, XOR with the graphic -------------------
b_fig:  ENTER
        DEBT_IN
        pop hl                  ; HL at the site: the buffer
        pop de                  ; DE at the site: the mask
        pop bc                  ; C at the site: rows
        push bc
        push de
        push hl
        ld (V_D),hl
        ld (V_S),de
        ld a,c
        ld (V_R),a
        ld a,(0x8209)
        ld (V_W),a
        ld hl,(0x8140)          ; read now: the passes map the canvas over this code
        ld (V_X),hl
        ld hl,(0x813D)
        ld (V_Y),hl
        call pass_and
        ld hl,(V_X)
        ld (V_D),hl
        ld hl,(V_Y)
        ld (V_S),hl
        call pass_xor
        DEBT_OUT
        BODY f_fig,KB_FIG,KR_FIG,K0_FIG
        LEAVE_B -23
        jp x_fig
f_fig:  ld a,(0x8209)
        jp 0x8120

; ---- D330 / D274: an entity's box saved, restored. HL buffer, DE table, width set ----
b_save:  ENTER
        DEBT_IN
        pop hl
        pop de
        push de
        push hl
        ld (V_D),hl
        ld (V_S),de
        ld a,(0xD338)
        ld (V_W),a
        ld a,(ix+0x0B)
        add a,a
        add a,a
        add a,a
        ld (V_R),a
        call save_rows
        DEBT_OUT
        BODY f_save,KB_BOX,KR_BOX,K0_BOX
        LEAVE_B -23
        jp x_save
f_save: ld a,(ix+0x0B)
        jp 0xD333
b_rest:  ENTER
        DEBT_IN
        pop hl
        pop de
        push de
        push hl
        ld (V_D),hl
        ld (V_S),de
        ld a,(0xD27C)
        ld (V_W),a
        ld a,(ix+0x0B)
        add a,a
        add a,a
        add a,a
        ld (V_R),a
        call rest_rows
        DEBT_OUT
        BODY f_rest,KB_BOX,KR_BOX,K0_BOX
        LEAVE_B -23
        jp x_rest
f_rest: ld a,(ix+0x0B)
        jp 0xD277

; ---- the same with B rows given (bullets; D337, D27B entered from outside) --------
        MACRO BOX_ARGS width
        pop hl
        pop de
        pop bc
        push bc
        push de
        push hl
        ld (V_D),hl
        ld (V_S),de
        ld a,b
        ld (V_R),a
        ld a,(width)
        ld (V_W),a
        ENDM
b_sb:  ENTER
        DEBT_IN
        BOX_ARGS 0xD338
        call save_rows
        DEBT_OUT
        LEAVE -12
        jp x_sb
b_rb:  ENTER
        DEBT_IN
        BOX_ARGS 0xD27C
        call rest_rows
        DEBT_OUT
        LEAVE -12
        jp x_rb
b_s24:  ENTER
        DEBT_IN
        ld a,4
        ld (0xD338),a
        BOX_ARGS 0xD338
        ld a,0x18
        ld (V_R),a
        call save_rows
        DEBT_OUT
        LEAVE -11
        jp x_s24
b_r24:  ENTER
        DEBT_IN
        ld a,4
        ld (0xD27C),a
        BOX_ARGS 0xD27C
        ld a,0x18
        ld (V_R),a
        call rest_rows
        DEBT_OUT
        LEAVE -11
        jp x_r24

; ---- C688: a bullet: B pairs of AND, XOR bytes, one column ------------------------
b_bul:  ENTER
        DEBT_IN
        pop hl
        pop de                  ; D = y, E = x
        pop bc
        push bc
        push de
        push hl
        ld a,d
        cp 0x96
        jr c,.y
        xor a
.y:     ld c,e
        ld e,a
        ld d,ROW
        mul d,e
        ld hl,0x6A00
        add hl,de
        ld b,0
        add hl,bc
        ld (V_D),hl
        ld de,(0xC68C)
        ld a,(0xC68F)
        ld c,a
        call map_s
        ld hl,(V_D)
        call map_d
.r:     DUP 8
        ld a,(de)
        and (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
        ld a,l
        sub 8
        ld l,a
        jr nc,.nb
        dec h
.nb:    DUP 8
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
        dec c
        jr z,.d
        call next_row
        jr .r
.d:     DEBT_OUT
        LEAVE -12
        jp x_bul

; ---- C8FB / C980: the ten stars drawn, erased: the mirror of the routine, then its body ----
        MACRO STAR_READ
        ld hl,star_tab
        ld de,V_ST
        ld b,10
.rd:    ld a,(hl)
        inc hl
        push hl
        ld h,(hl)
        ld l,a
        ld a,(hl)               ; the star's counter in DD28...
        ld (de),a
        inc de
        pop hl
        inc hl
        inc hl
        inc hl
        djnz .rd
        ld hl,0xE26D
        ld de,V_ST+10
        ld bc,6
        ldir
        ENDM
star_tab:
        dw 0xDD28,0x6F54,0xDD30,0x6C26,0xDD2A,0x6E4B,0xDD2E,0x6A0E,0xDD2C,0x7090
        dw 0xDD2F,0x6B25,0xDD2D,0x70FF,0xDD2B,0x6E59,0xDD29,0x6B2C,0xDD31,0x709F
; stars: E = 0 draw (cells empty), 1 erase (cells hold the star)
stars:  ld ix,star_tab+2
        ld iy,V_ST
        ld b,10
.lp:    push bc
        push de
        ld a,(iy+0)
        ld c,0
        cp 0x0C
        jr z,.big
        cp 0x0D
        jr z,.big
        cp 0x0E
        jr nz,.sm
.big:   ld c,3
.sm:    ld l,(ix+0)
        ld h,(ix+1)
        ld (V_D),hl
        ld a,c
        add a,10
        add a,V_ST&255
        ld (V_X),a              ; low byte of the local copy of the table
        ld a,V_ST>>8
        ld (V_X+1),a
        push iy
        ld iy,(V_X)
        ld b,3
.row:   ld a,(hl)
        and 0xF0
        ld c,a
        ld a,e
        or a
        jr z,.dr
        ld a,(iy+0)
        cp c
        jr nz,.no
        jr .nx
.dr:    ld a,c
        or a
        jr nz,.no
.nx:    inc iy
        push de
        ld de,ROW
        add hl,de
        pop de
        djnz .row
        pop iy
        push iy
        ld a,(iy+0)
        ld hl,0xE26D
        cp 0x0C
        jr z,.b2
        cp 0x0D
        jr z,.b2
        cp 0x0E
        jr nz,.s2
.b2:    ld hl,0xE270
.s2:    ld (V_S),hl
        ld a,3
        ld (V_R),a
        ld a,1
        ld (V_W),a
        call pass_xor
.no:    pop iy
        pop de
        pop bc
        inc ix
        inc ix
        inc ix
        inc ix
        inc iy
        dec b
        jp nz,.lp
        call slots
        xor a
        ld (V_R),a
        ret
b_st1:  ENTER
        DEBT_IN
        push ix
        push iy
        STAR_READ
        ld e,0
        call stars
        pop iy
        pop ix
        DEBT_OUT
        BODY f_st1,0,0,K0_STAR
        LEAVE_B -23
        jp x_st1
f_st1:  ld hl,0x6F54
        jp 0xC8FE
b_st2:  ENTER
        DEBT_IN
        push ix
        push iy
        STAR_READ
        ld e,1
        call stars
        pop iy
        pop ix
        DEBT_OUT
        BODY f_st2,0,0,K0_STAR
        LEAVE_B -23
        jp x_st2
f_st2:  ld hl,0x6F54
        jp 0xC983

; ---- DC0E: a column of the buffer zeroed -----------------------------------------
b_col:  ENTER
        DEBT_IN
        ld hl,0x6E1E
        ld a,(0xE278)
        add a,l
        ld l,a
        ld (V_D),hl
        ld c,0x5F
        call map_d
.r:     ld b,32
.z:     ld (hl),0
        inc hl
        djnz .z
        dec c
        jr z,.d
        call next_row
        jr .r
.d:     DEBT_OUT
        LEAVE -13
        jp x_col

; ---- D3B4: 4 bytes of the buffer set ---------------------------------------------
b_ffs:  ENTER
        DEBT_IN
        pop hl
        push hl
        ld a,(0xE278)
        add a,l
        ld l,a
        jr nc,.n
        inc h
.n:     call map_d
        ld b,32
.z:     ld (hl),0xFF
        inc hl
        djnz .z
        DEBT_OUT
        LEAVE -13
        jp x_ffs

; ---- D3C4 from a screen that is not play, and D5A3: no overlay ---------------------
b_hide:  ENTER
        nextreg 0x69,0
        LEAVE -13
        jp x_hide
b_cls:  ENTER
        nextreg 0x69,0
        LEAVE -13
        jp x_cls

; ---- D97A: the filler, an LDIR of the buffer onto itself ---------------------------
b_fill:  ENTER
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x6E40
        ld de,0x6E40
        ld bc,0x10A7
        ldir
        push af
        push bc
        push de
        push hl
        ld a,(V_PEND)
        or a
        call nz,try_flip
        ld hl,T_FILL
        ld a,(V_SPEED)
        call hlib_pace_wait
        LEAVE 3+2*0x10A7-12
        jp x_fill

; ---- D942 / D95E: the buffer's lower part moved a byte ------------------------------
b_left:  ENTER
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x6F51
        ld de,0x6F50
        ld bc,0x0BAF
        ldir
        push af
        push bc
        push de
        push hl
        call hlib_nest_open
        ld hl,0x6F50
        ld (V_D),hl
        ld hl,0x0BAF
        ld (V_S),hl             ; bytes left
.lp:    ld hl,(V_D)
        ld a,h
        and 3
        ld d,a
        ld e,l
        ld hl,1024
        or a
        sbc hl,de               ; room in this 1K
        ld de,(V_S)
        or a
        sbc hl,de
        jr c,.part
        ld hl,(V_S)             ; all that is left fits
        jr .go
.part:  add hl,de
.go:    ld b,h
        ld c,l                  ; bytes in this slice
        ld hl,(V_S)
        or a
        sbc hl,bc
        ld (V_S),hl
        ld hl,(V_D)
        push hl
        add hl,bc
        ld (V_D),hl
        pop hl
        call map_d
        ld d,h
        ld e,l                  ; DE: destination
        ld a,c                  ; BC x 8
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        push bc
        ld bc,8
        add hl,bc               ; HL: source
        pop bc
        call blit
        ld hl,(V_S)
        ld a,h
        or l
        jr nz,.lp
        ld a,6
        call hlib_nest_close
        ld hl,T_SCROLL
        ld a,(V_SPEED)
        call hlib_pace_wait
        LEAVE 3+2*0x0BAF-1-12
        jp x_left

b_right:  ENTER
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x7AFE
        ld de,0x7AFF
        ld bc,0x0BAF
        lddr
        push af
        push bc
        push de
        push hl
        call hlib_nest_open
        ld hl,0x7AFF            ; the top byte moved
        ld (V_D),hl
        ld hl,0x0BAF
        ld (V_S),hl             ; bytes left
.lp:    ld hl,(V_D)
        ld a,h
        and 3
        ld b,a
        ld c,l
        inc bc                  ; bytes down to this 1K's start
        ld hl,(V_S)
        or a
        sbc hl,bc
        jr nc,.t
        ld bc,(V_S)             ; all that is left
        ld hl,0
.t:     ld (V_S),hl
        ld hl,(V_D)
        or a
        sbc hl,bc               ; one below the slice's first destination byte: its first source byte
        push bc
        push hl
        ld (V_D),hl
        call map_d
        pop de
        pop bc
        push hl                 ; canvas of the source's first byte
        ld h,b
        ld l,c
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l                  ; canvas bytes
        pop hl
        add hl,bc
        dec hl                  ; the source's top canvas byte
        ld d,h
        ld e,l
        push bc
        ld bc,8
        add hl,bc
        ex de,hl                ; HL source, DE destination
        pop bc
        call blit_down
        ld hl,(V_S)
        ld a,h
        or l
        jr nz,.lp
        ld a,6
        call hlib_nest_close
        ld hl,T_SCROLL
        ld a,(V_SPEED)
        call hlib_pace_wait
        LEAVE 3+2*0x0BAF-1-12
        jp x_right

; ---- BF04, D4D2: the copy in play: the original's at 28 MHz, the canvas published ----
b_copy:  ENTER
        call hlib_pace_open
        ld hl,(V_SP)
        dec hl
        dec hl
        ld de,.back
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
        ld (0xEC98),hl
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        dec sp
        dec sp
        jp 0xD3C8
.back:  ld sp,0x4000
        push af
        push bc
        push de
        push hl
        ld hl,(V_SP)
        ld (0xEC98),hl          ; as the original left it
        call hlib_nest_open
        call publish
        ld a,6
        call hlib_nest_close
        ld hl,T_COPY
        ld a,(V_SPEED)
        call hlib_pace_wait
        LEAVE 7010-12
        jp x_copy

publish:
        ld a,(V_PEND)
        or a
.pw:    jr z,.pd
        call try_flip
        ld a,(V_PEND)
        or a
        jr .pw
.pd:
        ; the level's colour, read from the window's attributes as the set's renderer does
        ld a,(0x5800+6*32+3)
        ld hl,V_ATTR
        cp (hl)
        call nz,set_ink
        ld a,(V_BACK)
        add a,a
        ld c,a                  ; first page of the back buffer
        ld hl,SRC0
        ld (V_S),hl
        ld a,WIN_Y
.row:   push af
        push bc
        ld b,a
        rlca
        rlca
        rlca
        and 7
        add a,c
        nextreg 0x56,a
        ld a,b
        and 31
        or 0xC0
        ld d,a
        ld e,WIN_X
        ld hl,(V_S)
        push de
        call map_d
        pop de
        ld bc,208
        call blit
        ld hl,(V_S)
        ld de,ROW
        add hl,de
        ld (V_S),hl
        pop bc
        pop af
        inc a
        cp WIN_Y+WIN_ROWS
        jr nz,.row
        call slots
        ld a,1
        ld (V_PEND),a
        ret

; try_flip: show the new picture if the beam is outside the window's rows; else a later hook does. No wait: it costs pace.
try_flip:
        call hlib_line
        ld de,WIN_Y-2
        or a
        sbc hl,de
        jr c,flip
        ld de,WIN_ROWS+3
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

; set_ink: A = attribute: L2 palette 192..255 as the set's renderer mixes them with this ink.
set_ink:
        ld (V_ATTR),a
        ld b,a
        and 7
        bit 6,b
        jr z,.nb
        or 8
.nb:    ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; 128 bytes a table
        ld de,0xE000
        add hl,de
        nextreg 0x57,PAL_PAGE
        nextreg 0x43,0x10
        nextreg 0x40,192
        ld b,128
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        nextreg 0x43,0
        nextreg 0x57,1
        ret


; ---- the veneers, in the hidden ROM too ----
        ASSERT $ < 0x3860
        ORG 0x3870
ven_start:
h_clr: nextreg 0x51,HOOK_PAGE
        jp b_clr
x_clr: nextreg 0x51,255
        ld de,0x6A01
        jp 0xD5B4
h_tile: nextreg 0x51,HOOK_PAGE
        jp b_tile
x_tile: nextreg 0x51,255
        jp nz,0xD986
        ret
h_fig: nextreg 0x51,HOOK_PAGE
        jp b_fig
x_fig: nextreg 0x51,255
        ret
h_save: nextreg 0x51,HOOK_PAGE
        jp b_save
x_save: nextreg 0x51,255
        ret
h_sb: nextreg 0x51,HOOK_PAGE
        jp b_sb
x_sb: nextreg 0x51,255
        jp 0xD337
h_bul: nextreg 0x51,HOOK_PAGE
        jp b_bul
x_bul: nextreg 0x51,255
        jp 0xD617
h_st1: nextreg 0x51,HOOK_PAGE
        jp b_st1
x_st1: nextreg 0x51,255
        ret
h_st2: nextreg 0x51,HOOK_PAGE
        jp b_st2
x_st2: nextreg 0x51,255
        ret
h_col: nextreg 0x51,HOOK_PAGE
        jp b_col
x_col: nextreg 0x51,255
        ld hl,0x6E1E
        jp 0xDC11
h_ffs: nextreg 0x51,HOOK_PAGE
        jp b_ffs
x_ffs: nextreg 0x51,255
        ld a,(0xE278)
        jp 0xD3B7
h_hide: nextreg 0x51,HOOK_PAGE
        jp b_hide
x_hide: nextreg 0x51,255
        ld (0xEC98),sp
        jp 0xD3C8
h_fill: nextreg 0x51,HOOK_PAGE
        jp b_fill
x_fill: nextreg 0x51,255
        ret
h_left: nextreg 0x51,HOOK_PAGE
        jp b_left
x_left: nextreg 0x51,255
        jp 0xD94D
h_right: nextreg 0x51,HOOK_PAGE
        jp b_right
x_right: nextreg 0x51,255
        jp 0xD969
h_copy: nextreg 0x51,HOOK_PAGE
        jp b_copy
x_copy: nextreg 0x51,255
        ret
h_rest: nextreg 0x51,HOOK_PAGE
        jp b_rest
x_rest: nextreg 0x51,255
        ret
h_rb: nextreg 0x51,HOOK_PAGE
        jp b_rb
x_rb: nextreg 0x51,255
        jp 0xD27B
h_s24: nextreg 0x51,HOOK_PAGE
        jp b_s24
x_s24: nextreg 0x51,255
        ld b,0x18
        ld a,4
        jp 0xD337
h_r24: nextreg 0x51,HOOK_PAGE
        jp b_r24
x_r24: nextreg 0x51,255
        ld b,0x18
        ld a,4
        jp 0xD27B
h_cls: nextreg 0x51,HOOK_PAGE
        jp b_cls
x_cls: nextreg 0x51,255
        ld de,0x4001
        jp 0xD5A6
ven_end:
        ASSERT $ < 0x3C00
rom_end:
regblock EQU 0x3C00
        SAVEBIN "gunrunner_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x70,0
        nextreg 0x12,L2_BANK_A
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1
        nextreg 0x18,WIN_X
        nextreg 0x18,WIN_X+207
        nextreg 0x18,WIN_Y
        nextreg 0x18,WIN_Y+WIN_ROWS-1
        ; the Layer 2 palette: page 26 holds it after the ink tables
        nextreg 0x50,PAL_PAGE
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,0x0800
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
        SAVEBIN "gunrunner_setup.bin",setup,setup_end-setup
