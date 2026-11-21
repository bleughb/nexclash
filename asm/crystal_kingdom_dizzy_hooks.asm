; Crystal Kingdom Dizzy (Codemasters, 1992, 128K) - hardware sprites OVER the game's masked figures (overlay).
; Every frame (interrupts off, 0xDDC4 CALL 0xF433) the game puts back the backgrounds it saved, then walks its
; object list (33639) and draws each object (record IX, 32 bytes, 0x7E00-0x7FFF) with a routine chosen per width,
; patched into the CALL at 0xF50C: masked with save-under, data = (mask, graphics) pairs row by row, two pixel
; lines a pass (IYl passes), plain or mirrored (bit-reverse table at 0x8000, drawn right to left); or a plain copy
; (record flag bit 5: never restored, the game paints its cells white; left to the ULA).
; Objects are monochrome on the screen and take the cells' ink: the colour clash. The build keeps every screen and
; attribute write and lays white sprites over each masked object's graphics bits:
;   0xF433 (the restore pass starts), 0xF8DD (the room drawn again), 0xFBE1 (a window): every object sprite hidden;
;   0xF508 (before the CALL that draws one object): that object's sprites (record (IX >> 5) & 15, 4 sprites of
;   16 x 16, up to 32 x 32) from the bytes the game is about to OR in; a plain copy hides them.
; Hooks in alt ROM image 1 at 0x386E, stateless (locals on the dead stack below SP, IX as frame pointer), 28 MHz.

        DEVICE ZXSPECTRUMNEXT

LISTEND EQU 33770
SAVEPTR EQU 33771
RTPTR   EQU 0xF50D          ; the CALL operand: the draw routine of this object
REVT    EQU 0x8000          ; the game's bit-reverse table
NSPR    EQU 64              ; 16 records x 4 sprites
WHITE   EQU 0xF0            ; palette offset 15 (BRIGHT white) << 4

; frame (IX+n): first sprite, width bytes, mirrored, rows, x, y, data low, data high
F_SPR   EQU 0
F_W     EQU 1
F_MIR   EQU 2
F_ROWS  EQU 3
F_X     EQU 4
F_Y     EQU 5
F_DATA  EQU 6
F_NEW   EQU 8               ; 1: the patterns must be sent (the object's graphics, routine or height changed)
F_SUM   EQU 9               ; signature of the data: sum, xor (2 bytes)
F_K     EQU 11              ; per tile: data offsets (2 x column, bit 6 = mirrored, 0xFF blank) of the tile's two
                            ; columns on even rows, then on odd rows (4 bytes)
FRAME   EQU 16
SHOWN   EQU 0x0800          ; in the cache page: 16-bit mask of the records whose sprites are shown
STPAGE  EQU 26              ; 8K page of the pattern cache (bank 13), at 0x0000 inside the hook only
EXPT    EQU 0x1000          ; in that page: 256 x 4 pattern bytes, one byte's 8 pixels as 4-bit values 1

        ORG 0x386E
; ---- 0xF433 LD A,(33770) -> JP e_rs --------------------------------------------------------------------
e_rs:   push af
        push bc
        push hl
        nextreg 0x07,3
        nextreg 0x50,STPAGE     ; hide the records the mask says are shown, then clear it
        ld hl,(SHOWN)
        ld a,l
        or h
        jr z,rs_done
        xor a                   ; A = first sprite of record 0
rs_l:   srl h
        rr l
neg_rs:
        call c,hide4r
        add a,4
        cp NSPR
        jr nz,rs_l
        ld hl,0
        ld (SHOWN),hl
rs_done:
        nextreg 0x50,0xFF
        nextreg 0x07,0
        pop hl
        pop bc
        pop af
        ld a,(LISTEND)
        jp 0xF436

; ---- 0xF8DD LD A,(65336) -> JP e_rd: the room is drawn again, every object sprite hidden -----------------
e_rd:   push af
        push bc
        nextreg 0x07,3
neg_rd:
        call hidall
        nextreg 0x07,0
        pop bc
        pop af
        ld a,(65336)
        jp 0xF8E0

; ---- 0xFBE1 LD A,(HL) / LD IXl,A -> JP e_wn: a window (dialogue, inventory) over the play area --------------
e_wn:   push af
        push bc
        nextreg 0x07,3
neg_wn:
        call hidall
        nextreg 0x07,0
        pop bc
        pop af
        ld a,(hl)
        ld ixl,a
        jp 0xFBE4

; ---- 0xF508 LD BC,(33771) -> JP e_ob -------------------------------------------------------------------
e_ob:   push af
        push bc
        push de
        push hl
        push iy
        nextreg 0x07,3
        ld a,ixh                ; a record of the table at 0x7E00-0x7FFF, else nothing to show
        and 0xFE
        cp 0x7E
        jp nz,ob_ret
        ld a,ixl                ; first sprite = ((IX >> 5) & 15) x 4
        rlca
        rlca
        rlca
        and 7
        ld b,a
        ld a,ixh
        and 1
        rlca
        rlca
        rlca
        or b
        add a,a
        add a,a
        ld c,a                  ; C = first sprite
        push hl                 ; the routine -> width, flags (bit 0 mirrored, bit 1 zigzag)
        push de
        ld hl,(RTPTR)
        ld de,rtab
ob_find:
        ld a,(de)
        or a
        jr z,ob_none
        cp l
        jr nz,ob_next
        inc de
        ld a,(de)
        cp h
        jr z,ob_hit
        dec de
ob_next:
        inc de
        inc de
        inc de
        inc de
        jr ob_find
ob_none:
        pop de
        pop hl
        ld a,c                  ; a plain copy (or a routine not in the table): left to the ULA
        call hide4
        jp ob_ret
ob_hit: inc de
        ld a,(de)
        ld b,a                  ; B = width
        inc de
        ld a,(de)               ; A = flags
        pop de                  ; DE = screen
        pop hl                  ; HL = data
        push ix                 ; frame on the dead stack, IX on it
        ld ix,-FRAME
        add ix,sp
        ld sp,ix
        ld (ix+F_MIR),a
        ld (ix+F_SPR),c
        ld (ix+F_W),b
        ld (ix+F_DATA),l
        ld (ix+F_DATA+1),h
        ld a,iyl
        add a,a
        ld (ix+F_ROWS),a
        ld a,e                  ; x = column x 8
        and 31
        add a,a
        add a,a
        add a,a
        ld (ix+F_X),a
        ld a,d                  ; y from the screen address DE
        and 0x18
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or l
        ld l,a
        ld a,d
        and 7
        or l
        ld (ix+F_Y),a
        call dsum               ; the data's signature (graphics built in a buffer change under one pointer)
        nextreg 0x50,STPAGE     ; the cache: 8 bytes a record (data, routine low byte, rows, sum, xor) at slot x 8
        ld a,(ix+F_SPR)
        add a,a
        ld l,a
        ld h,0
        ld e,l
        ld a,(ix+F_DATA)
        cp (hl)
        jr nz,ob_new
        inc l
        ld a,(ix+F_DATA+1)
        cp (hl)
        jr nz,ob_new
        inc l
        ld a,(RTPTR)
        cp (hl)
        jr nz,ob_new
        inc l
        ld a,(ix+F_ROWS)
        cp (hl)
        jr nz,ob_new
        inc l
        ld a,(ix+F_SUM)
        cp (hl)
        jr nz,ob_new
        inc l
        ld a,(ix+F_SUM+1)
        cp (hl)
        jr nz,ob_new
        xor a
        jr ob_same
ob_new: ld l,e
        ld a,(ix+F_DATA)
        ld (hl),a
        inc l
        ld a,(ix+F_DATA+1)
        ld (hl),a
        inc l
        ld a,(RTPTR)
        ld (hl),a
        inc l
        ld a,(ix+F_ROWS)
        ld (hl),a
        inc l
        ld a,(ix+F_SUM)
        ld (hl),a
        inc l
        ld a,(ix+F_SUM+1)
        ld (hl),a
neg_new:
        ld a,1
ob_same:
        ld (ix+F_NEW),a         ; the page stays at 0x0000 for the expansion table (interrupts are off)
        ld a,(ix+F_SPR)         ; this record shown: its bit in the mask
        rrca
        rrca
        and 15
        ld b,a
        inc b
        ld hl,0
        scf
sh_l:   adc hl,hl
        djnz sh_l
        ld a,(SHOWN)
        or l
        ld (SHOWN),a
        ld a,(SHOWN+1)
        or h
        ld (SHOWN+1),a
        ld c,0                  ; tile: bit 0 = tx, bit 1 = ty
ob_tile:
        call tile
        inc c
        ld a,c
        cp 4
        jr nz,ob_tile
        ld hl,FRAME             ; drop the frame
        add hl,sp
        ld sp,hl
        pop ix
ob_ret: nextreg 0x50,0xFF
        nextreg 0x07,0
        pop iy
        pop hl
        pop de
        pop bc
        pop af
        ld bc,(SAVEPTR)
        jp 0xF50C

; C = tile (tx = bit 0, ty = bit 1): sprite F_SPR + C, 16 x 16 from rows ty x 16 and bytes tx x 2, tx x 2 + 1
tile:   ld a,c
        and 1
        add a,a
        cp (ix+F_W)
        jp nc,tl_hide           ; no byte of the object in this column of tiles
        ld a,c
        and 2
        rlca
        rlca
        rlca                    ; ty x 16
        cp (ix+F_ROWS)
        jp nc,tl_hide
        ld a,(ix+F_NEW)
        or a
        jp z,tl_attr            ; the patterns are already the object's
        ld a,(ix+F_SPR)
        add a,c
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld a,c                  ; the tile's column offsets for even and odd rows
        and 1
        add a,a
        ld e,a                  ; E = 2 x tx = first column
        ld d,0
        call kmap
        ld (ix+F_K),a
        inc e
        call kmap
        ld (ix+F_K+1),a
        dec e
        inc d
        call kmap
        ld (ix+F_K+2),a
        inc e
        call kmap
        ld (ix+F_K+3),a
        ld a,c
        and 2
        rlca
        rlca
        rlca
        ld d,a                  ; D = the tile's first row
        call rowb               ; HL = its first graphics byte
        ld b,16                 ; rows in the tile
tl_row: ld a,d
        cp (ix+F_ROWS)
        jr nc,tl_zero
        bit 0,d
        jr nz,tl_odd
        ld a,(ix+F_K)
        call fetch
        push hl
        call tx4
        pop hl
        ld a,(ix+F_K+1)
        jr tl_2nd
tl_odd: ld a,(ix+F_K+2)
        call fetch
        push hl
        call tx4
        pop hl
        ld a,(ix+F_K+3)
tl_2nd: call fetch
        push hl
        call tx4
        pop hl
        ld a,(ix+F_W)           ; next row: + 2 x width
        add a,a
        add a,l
        ld l,a
        jr nc,tl_nxt
        inc h
        jr tl_nxt
tl_zero:
        xor a
        ld e,8
tl_z:   out (0x5B),a
        dec e
        jr nz,tl_z
tl_nxt: inc d
        djnz tl_row
tl_attr:
        ld a,(ix+F_SPR)         ; attributes
        add a,c
        nextreg 0x34,a
        ld e,a
        ld a,c
        and 1
        rrca
        rrca
        rrca
        rrca                    ; tx x 16
        add a,(ix+F_X)
        ld h,0
        jr nc,tl_x
        inc h
tl_x:   add a,32
        jr nc,tl_x2
        inc h
tl_x2:  nextreg 0x35,a
        ld a,h
        or WHITE
        nextreg 0x37,a
        ld a,c
        and 2
        rlca
        rlca
        rlca
        add a,(ix+F_Y)
neg_y:  add a,32
        nextreg 0x36,a
        ld a,e
        and 63
        or 0xC0
        nextreg 0x38,a
        ld a,0x80
        nextreg 0x39,a
        ret
tl_hide:
        ld a,(ix+F_SPR)
        add a,c
        jp hide

; D = row -> HL = data + 2 x row x width + 1 (the row's first graphics byte). Keeps BC, DE
rowb:   push bc
        push de
        ld e,d
        ld d,0
        ld hl,0
        ld b,(ix+F_W)
rb_m:   add hl,de
        djnz rb_m
        add hl,hl
        inc hl
        ld e,(ix+F_DATA)
        ld d,(ix+F_DATA+1)
        add hl,de
        pop de
        pop bc
        ret

; E = column as drawn, D = row parity (bit 0) -> A = 2 x data column (+ 0x40 when mirrored), 0xFF past the width
; (mirrored: from the other end; zigzag storage: odd lines stored right to left). Keeps BC, DE, HL
kmap:   ld a,e
        cp (ix+F_W)
        jr c,km_in
        ld a,0xFF
        ret
km_in:  push bc
        ld c,e
        bit 0,(ix+F_MIR)
        jr z,km_m
        ld a,(ix+F_W)
        dec a
        sub c
        ld c,a
km_m:   bit 1,(ix+F_MIR)
        jr z,km_c
        bit 0,d
        jr z,km_c
        ld a,(ix+F_W)
        dec a
        sub c
        ld c,a
km_c:   ld a,c
        add a,a
        bit 0,(ix+F_MIR)
        jr z,km_out
        or 0x40
km_out: pop bc
        ret

; A = offset from kmap, HL = the row's first graphics byte -> A = the byte as it lands on the screen. Keeps BC, D, HL
fetch:  cp 0xFF
        jr nz,fe_in
        xor a
        ret
fe_in:  push hl
        ld e,a
        and 0x3F
        add a,l
        ld l,a
        jr nc,fe_g
        inc h
fe_g:   ld a,(hl)
        bit 6,e
        jr z,fe_out
        ld h,REVT >> 8
        ld l,a
        ld a,(hl)
fe_out: pop hl
        ret

; the data's signature: (ix+F_SUM) = sum, (ix+F_SUM+1) = xor of its 2 x rows x width bytes. Keeps BC, DE, HL
dsum:   push hl
        push bc
        push de
        ld l,(ix+F_DATA)
        ld h,(ix+F_DATA+1)
        ld a,(ix+F_W)           ; count = 2 x width x rows (<= 256: 0 means 256)
        ld b,a
        xor a
ds_m:   add a,(ix+F_ROWS)
        djnz ds_m
        add a,a
        ld b,a
        ld de,0
ds_l:   ld a,(hl)
        add a,d
        ld d,a
        ld a,(hl)
        xor e
        ld e,a
        inc hl
        djnz ds_l
        ld (ix+F_SUM),d
        ld (ix+F_SUM+1),e
        pop de
        pop bc
        pop hl
        ret

; A = first sprite: hide 4, A kept
hide4r: push af
        call hide4
        pop af
        ret

; A = first sprite: hide 4
hide4:  call hide
        inc a
        call hide
        inc a
        call hide
        inc a
        jp hide

hidall: xor a
        ld b,NSPR
ha_l:   call hide
        inc a
        djnz ha_l
        ret

hide:   nextreg 0x34,a
        push af
        xor a
        nextreg 0x38,a
        pop af
        ret

; A = 8 pixels -> 4 pattern bytes (value 1 = ink) from the table at 0x1000 of the cache page. Keeps BC
tx4:    rlca
        rlca
        ld l,a
        and 3
        or EXPT >> 8
        ld h,a
        ld a,l
        and 0xFC
        ld l,a
neg_pix:
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ret

; draw routine -> width, mirrored (masked ones only)
rtab:   dw 0xF52D
        db 1,0
        dw 0xF5EE
        db 3,2
        dw 0xF63E
        db 4,0
        dw 0xF6A4
        db 3,3
        dw 0xF718
        db 4,1
        db 0
rom_end:

; ---- start-up, called once by the stub --------------------------------------------------------------
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0xF1       ; offset 15, index 1: BRIGHT white
        nextreg 0x41,0xFF
        nextreg 0x4B,0
        xor a
st_h:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,st_h
        nextreg 0x15,0x01
        ret
setup_end:

        SAVEBIN "ck_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ck_setup.bin",0xD000,setup_end-0xD000
