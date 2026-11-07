; Knight Tyme (Mastertronic Added Dimension 1986, 128K edition) - every figure in play becomes 4-bit
; hardware sprites; scenery, text, windows and icons stay on the ULA. Facts: games/knight_tyme.md.
;
; Drawing in the original:
;   Knight   0xAD18 / 0xACE5: compose a 3 x 32 box: clean bytes from the room copy in bank 7, masked graphics
;            from 0xF3F4 / 0xF6F4 (4 shifts x 2 facings), blit the old clean box, 0xAD54 CALL 0xACBB blit the new.
;   Others   room build: objects 0x941E CALL 0xB30A (2 x 2 cells), characters 0x706C CALL 0xB30F (2 x 4 cells),
;            both masked on the screen BEFORE the screen is copied to bank 7 as the room's clean copy.
; Method - the game's own code runs, the same instructions in the same order:
;   0xAD54  CALL e_kn: the blit runs from the clean box 0x5D65 (data patch 0xACBC), DE and A put back, sprites set.
;   0x706C / 0x941E  CALL e_ch / e_ob: cells saved, the game's plotter runs, cells restored, sprites built.
;   0x6D7E  JP e_rm : room build starts: all figure sprites go.
;   0x8FB8  CALL e_wn: a window opens: sprite tiles it touches are hidden; the next Knight commit shows them.
;   0x9218  JP e_wp : full screen wipe: all figure sprites go.
; Hook code: small stubs in alt ROM image 1 (0x386E-, free in the 48K ROM), the rest in page H at slot 4 with
; interrupts off (the ISR touches every slot). The plotter and blit themselves run with interrupts on.
;
; Patch sites (original bytes verified by knight_tyme.py):
;   0xAD54 CD BB AC  CALL 0xACBB   -> CALL e_kn
;   0xACBC 05 (LD DE,23813)        -> 65 (LD DE,23909): the blit reads the clean box
;   0x706C CD 0F B3  CALL 0xB30F   -> CALL e_ch
;   0x941E CD 0A B3  CALL 0xB30A   -> CALL e_ob
;   0x6D7E 3A BC 61  LD A,(25020)  -> JP e_rm
;   0x8FB8 CD 03 90  CALL 0x9003   -> CALL e_wn
;   0x9218 21 00 00  LD HL,0       -> JP e_wp
;   0x6F0A CD CC 93  CALL 0x93CC   -> CALL e_ov: room build, scenery done: the Bridge's seated crew, drawn in the room
;                                     graphics, get sprite tiles over their ULA ink (own colours per pixel, page 27)
;   0x6892 01 (LD A,1: PLAYER ATTRIBUTE UPDATE) -> 00: figures have their own colours in either option

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"    ; macros only: HLIB_SPEED_IN

HPG     EQU 26                  ; hook page, MMU slot 4 while a hook runs
GP4     EQU 4                   ; the game's page at slot 4
GP5     EQU 5                   ; the game's page at slot 5
STORE   EQU 28                  ; colour store: pages 28-43: 8 bytes per address 0xC000-0xFFFF
CBLACK  EQU 8                   ; sprite palette index of black
CWHITE  EQU 15
KPAT    EQU 6                   ; Knight: tiles per image, images at pattern 0, 6, .. 42
RFIRST  EQU 48                  ; first pattern of the room figures
KSLOT   EQU 122                 ; Knight's sprites: 122-127 (on top)
MAXROOM EQU 122                 ; room figure sprites 0-121

; ---- page H at 0x8000 ----
V_SP    EQU 0x8000
V_SPD   EQU 0x80FF              ; the caller's CPU speed (lib/hlib_speed.asm latch)
V_K     EQU 0x8002              ; kind: 0 character, 1 object
V_A     EQU 0x8003              ; plot: graphic, row, column
V_B     EQU 0x8004
V_C     EQU 0x8005
V_NS    EQU 0x8006              ; room sprites in use
V_NP    EQU 0x8007              ; next free pattern
V_HID   EQU 0x8008              ; a window hid tiles
V_HASC  EQU 0x8009              ; 1 = the colour store has entries (Python / recolour)
V_OL    EQU 0x800A              ; 1 = outline
V_DROP  EQU 0x800B              ; tiles dropped (diagnostic)
V_G     EQU 0x800C              ; (2) graphics
V_M     EQU 0x800E              ; (2) mask
V_WB    EQU 0x8010              ; width in bytes
V_HL    EQU 0x8011              ; lines
V_INK   EQU 0x8012              ; ink index
V_OC    EQU 0x8013              ; outline index
V_OK    EQU 0x8014              ; 1 = the outline rings ink only (white figures: the game's mask is their black halo)
V_TILE  EQU 0x8015              ; tile mask of the last pack
V_X     EQU 0x8016              ; (2) sprite X of the canvas origin (+32)
V_Y     EQU 0x8018              ; (2) sprite Y
V_PB    EQU 0x801A              ; pattern of this tile
V_NC    EQU 0x801B              ; canvas tile columns
V_NR    EQU 0x801C              ; canvas tile rows
V_NB    EQU 0x801D              ; (4) colour nibbles of this byte
V_CL    EQU 0x8021              ; clear mask of this byte
V_ANY   EQU 0x8022
V_L     EQU 0x8023
V_WN    EQU 0x8024              ; window in sprite coordinates: left, right (2 each), top, bottom (2 each)
V_N     EQU 0x802C
V_CT    EQU 0x802E              ; tile counter
V_OP    EQU 0x8030              ; (2) overlay: position pointer
V_OD    EQU 0x8032              ; (2) overlay: tile data pointer
V_OC2   EQU 0x8034              ; overlay: tiles left
SPRTAB  EQU 0x8100              ; 128 x 8: X (2), Y (2), a3, a4, shown (1, 2 hidden; 0x10 left edge is ring, 0x20 top edge), size
                                ; size: (pixels wide - 1) << 4 | (lines - 1): the figure's part of this tile
CACHE   EQU 0x8500              ; Knight: 8 x 8: valid, colour, sum (2), tile mask
SAVE    EQU 0x8600              ; cells under a figure
TILEB   EQU 0x8680              ; 128 bytes: tile being packed
CANVAS  EQU 0x8700              ; 49 lines x 64: figure at (2,2), rings at 1, zeros at 0; pack reads 3 x 16 lines from line 1
HSTK    EQU 0x9440

LINES   EQU 0x6680              ; the game's line address table
KX      EQU 25694               ; Knight: column of the new box
KY      EQU 25157               ; line
KSHIFT  EQU 25159
KFACE   EQU 25697
KCOL    EQU 25162
OBJCOL  EQU 23695               ; ATTR T, set by the object loop
CHCOL   EQU 0x7086              ; self-modified LD A,n: the character's colour
GTAB    EQU 0xC544              ; graphic table: graphics, mask

        MACRO ENTER
        di
        nextreg 0x54,HPG
        ld (V_SP),sp
        ld sp,HSTK
        HLIB_SPEED_IN V_SPD             ; the caller's speed latched (hook stack), then 28 MHz
        push af
        push bc
        push de
        push hl
        push ix
        ENDM

        MACRO LEAVE
        pop ix
        pop hl
        pop de
        pop bc
        ld a,(V_SPD)                    ; the caller's speed back (never a fixed 3.5 MHz), then A
        nextreg 0x07,a
        pop af
        ld sp,(V_SP)
        nextreg 0x54,GP4
        ei
        ENDM

; ---- alt ROM stubs ----
        ORG 0x386E

e_kn:   ex (sp),hl                  ; the blit returns to e_kn2
        ld hl,e_kn2
        ex (sp),hl
        jp 0xACBB
e_kn2:  ENTER
        call c_kn
        LEAVE
        ld de,0x5D65                ; as the original's blit from 0x5D05 ends
        ld a,(0x5D64)
        jp 0xAD57

e_ch:   ENTER
        xor a
        ld (V_K),a
        call c_save
        LEAVE
        ex (sp),hl
        ld hl,e_ch2
        ex (sp),hl
        jp 0xB30F
e_ch2:  ENTER
        ld hl,0x706F
        call c_plot
        LEAVE
        jp 0x706F

e_ob:   ENTER
        ld a,1
        ld (V_K),a
        call c_save
        ld a,(V_N)
        or a
        jr z,.win                   ; the window's object picture stays on the ULA
        LEAVE
        ex (sp),hl
        ld hl,e_ob2
        ex (sp),hl
        jp 0xB30A
.win:   LEAVE
        jp 0xB30A
e_ob2:  ENTER
        ld hl,0x9421
        call c_plot
        LEAVE
        jp 0x9421

e_rm:   ENTER
        call c_all
        LEAVE
        ld a,(25020)
        jp 0x6D81

e_wn:   ENTER
        call c_win
        LEAVE
        jp 0x9003

e_ov:   ENTER
        call c_ov
        LEAVE
        jp 0x93CC

e_wp:   ENTER
        call c_all
        LEAVE
        ld hl,0
        jp 0x921B

rom_end:

; ---- page H: code ----
        ORG 0x9440

; c_save: called with the entry registers on the hook stack (ret, ix, hl, de, bc, af): saves the cells under the
; plot. V_N = 0 when the entry IX is the window picture's 25568: that plot stays on the ULA.
c_save: ld hl,2
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = entry IX
        inc hl
        inc hl
        inc hl
        inc hl
        inc hl
        ld c,(hl)                   ; C
        inc hl
        ld b,(hl)                   ; B
        inc hl
        inc hl
        ld a,(hl)                   ; A
        ld (V_A),a
        ld a,b
        ld (V_B),a
        ld a,c
        ld (V_C),a
        ld hl,25568                 ; 0x93E7's own entry: the object picture in a window
        or a
        sbc hl,de
        ld a,h
        or l
        ld (V_N),a                  ; 0 = stay on the ULA
        jr z,.done
        ld a,(V_K)
        or a
        ld e,32
        jr z,.c
        ld e,16
.c:     ld a,(V_B)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        ld bc,LINES
        add hl,bc
        ld ix,SAVE
        ld b,e
.l:     push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ex de,hl
        ld a,(V_C)
        add hl,a
        ld a,(hl)
        ld (ix+0),a
        inc hl
        ld a,(hl)
        ld (ix+1),a
        inc ix
        inc ix
        ex de,hl
        pop bc
        djnz .l
.done:  ret

; c_plot: HL = the game's return address (put back in the dead stack). Restores the cells, builds the sprites.
c_plot: ex de,hl
        ld hl,(V_SP)
        dec hl
        ld (hl),d
        dec hl
        ld (hl),e
        ld a,(V_K)
        or a
        ld e,32
        jr z,.c
        ld e,16
.c:     ld a,e
        ld (V_HL),a
        ld a,(V_B)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        ld bc,LINES
        add hl,bc
        ld ix,SAVE
        ld b,e
.l:     push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ex de,hl
        ld a,(V_C)
        add hl,a
        ld a,(ix+0)
        ld (hl),a
        inc hl
        ld a,(ix+1)
        ld (hl),a
        inc ix
        inc ix
        ex de,hl
        pop bc
        djnz .l
        ld a,2
        ld (V_WB),a
        ld a,(V_A)                  ; graphic table
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,GTAB
        add hl,bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_G),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_M),de
        ld a,(V_K)
        or a
        ld a,(CHCOL)
        jr z,.col
        ld a,(OBJCOL)
.col:   call setcol
        call build
        ld a,(V_C)                  ; sprite position of the canvas origin (figure at +1,+1 of tile space)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,31
        add hl,bc
        ld (V_X),hl
        ld a,(V_B)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,bc
        ld (V_Y),hl
        ld a,2
        ld (V_NC),a
        ld a,(V_K)
        or a
        ld a,3
        jr z,.r
        ld a,2
.r:     ld (V_NR),a
        jp pack_room

; setcol: A = attribute -> ink index, outline index, ring rule
setcol: ld b,a
        and 7
        ld c,a
        ld a,b
        and 0x40
        jr z,.nb
        ld a,c
        or a
        jr z,.k
        add a,8
        jr .s
.k:     ld a,CBLACK
        jr .s
.nb:    ld a,c
        or a
        jr nz,.s
        ld a,CBLACK
.s:     ld (V_INK),a
        ld b,a
        and 7
        cp 7
        ld a,CWHITE
        ld c,0
        jr nz,.o
        ld a,CBLACK
        ld c,1
.o:     ld (V_OC),a
        ld a,c
        ld (V_OK),a
        ret

; build: V_G, V_M, V_WB, V_HL, V_INK, V_OC -> the canvas
build:  ld hl,CANVAS
        ld de,CANVAS+1
        ld bc,49*64-1
        ld (hl),0
        ldir
        ld hl,CANVAS+2*64+2         ; line pointer
        ld a,(V_HL)
        ld b,a
.line:  push bc
        push hl
        ld a,(V_WB)
        ld b,a
.byte:  push bc
        push hl
        call colents
        ld hl,(V_G)
        ld d,(hl)                   ; D graphics
        inc hl
        ld (V_G),hl
        ld hl,(V_M)
        ld e,(hl)                   ; E mask
        inc hl
        ld (V_M),hl
        pop hl
        ld b,0
.bit:   ld a,b                      ; colour nibble of pixel B
        rra
        and 3
        push hl
        ld hl,V_NB
        add hl,a
        ld a,(hl)
        pop hl
        bit 0,b
        jr nz,.lo
        rra
        rra
        rra
        rra
.lo:    and 15
        ld c,a                      ; C = painted colour or 0
        ld a,(V_CL)
        rlca
        ld (V_CL),a
        jr c,.clear                 ; painted clear (a set bit: bit 7 first)
        sla d
        jr nc,.nink
        sla e                       ; ink
        ld a,c
        or a
        jr nz,.st
        ld a,(V_INK)
        jr .st
.nink:  sla e
        jr c,.tr                    ; paper with mask 1: see-through unless painted
        ld a,c                      ; mask 0: the game's knocked-out paper: black unless painted
        or a
        jr nz,.st
        ld a,CBLACK
        jr .st
.clear: sla d
        sla e
        xor a
        jr .st
.tr:    ld a,c
.st:    ld (hl),a
        inc hl
        inc b
        ld a,b
        cp 8
        jr nz,.bit
        pop bc
        djnz .byte
        pop hl
        ld bc,64
        add hl,bc
        pop bc
        djnz .line
        ld a,(V_OL)
        or a
        ret z
        ; outline: rings in 0x10, a pass then gives them the colour
        ld a,(V_HL)
        add a,2
        ld b,a                      ; lines 1 .. H+2
        ld hl,CANVAS+64+1
.ol:    push bc
        push hl
        ld a,(V_WB)
        add a,a
        add a,a
        add a,a
        add a,2
        ld b,a                      ; pixels 1 .. 8W+2
.op:    ld a,(hl)
        or a
        jr nz,.nx
        push hl
        dec hl
        ld a,(hl)
        call ringt
        jr nz,.yes
        inc hl
        inc hl
        ld a,(hl)
        call ringt
        jr nz,.yes
        ld de,-65
        add hl,de
        ld a,(hl)
        call ringt
        jr nz,.yes
        ld de,128
        add hl,de
        ld a,(hl)
        call ringt
.yes:   pop hl
        jr z,.nx
        ld (hl),0x10
.nx:    inc hl
        djnz .op
        pop hl
        ld bc,64
        add hl,bc
        pop bc
        djnz .ol
        ld a,(V_HL)
        add a,2
        ld b,a
        ld hl,CANVAS+64+1
.o2:    push bc
        push hl
        ld a,(V_WB)
        add a,a
        add a,a
        add a,a
        add a,2
        ld b,a
.o3:    ld a,(hl)
        cp 0x10
        jr nz,.o4
        ld a,(V_OC)
        ld (hl),a
.o4:    inc hl
        djnz .o3
        pop hl
        ld bc,64
        add hl,bc
        pop bc
        djnz .o2
        ret

; ringt: A = a neighbour. NZ = this neighbour earns a ring. Rings themselves (0x10) do not.
ringt:  cp 0x10
        jr z,.no
        or a
        ret z
        ld c,a
        ld a,(V_OK)
        or a
        jr z,.yes
        ld a,c                      ; ring on ink only: black paper is the game's own halo
        cp CBLACK
        jr z,.no
.yes:   or 1
        ret
.no:    xor a
        ret

; colents: the colour store entry of the graphics byte at V_G -> V_NB, V_CL (zeros when absent or stale)
colents:
        xor a
        ld (V_CL),a
        ld hl,V_NB
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ld a,(V_HASC)
        or a
        ret z
        ld hl,(V_G)
        ld a,h
        cp 0xC0
        ret c
        sub 0xC0
        ld b,a                      ; offset 14 bits: page = offset >> 10, in page (offset & 0x3FF) * 8
        rrca
        rrca
        and 0x3F
        add a,STORE
        nextreg 0x55,a
        ld a,b
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0xA0
        ld h,a
        ld a,(hl)
        cp 1
        jr nz,.out
        inc hl
        push hl
        ld hl,(V_G)
        ld b,(hl)                   ; slot 6/7: the game's byte
        pop hl
        ld a,(hl)
        cp b
        jr nz,.out                  ; other graphics at this address: defaults
        inc hl
        ld de,V_NB
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)
        ld (V_CL),a
.out:   nextreg 0x55,GP5
        ret

; pack: canvas tile (D = column, E = row) -> TILEB, NZ if any pixel
pack:   ld a,e
        swapnib                     ; row * 16 lines
        ld l,a
        ld h,0
        ld b,6
.m:     add hl,hl
        djnz .m                     ; * 64
        ld a,d
        swapnib                     ; column * 16 pixels
        add a,1                     ; origin: canvas (1,1)
        add hl,a
        ld bc,CANVAS+64
        add hl,bc
        ld de,TILEB
        xor a
        ld (V_ANY),a
        ld b,16
.y:     push bc
        push hl
        ld b,8
.x:     ld a,(hl)
        inc hl
        swapnib
        or (hl)
        inc hl
        ld (de),a
        inc de
        ld c,a
        ld a,(V_ANY)
        or c
        ld (V_ANY),a
        djnz .x
        pop hl
        ld bc,64
        add hl,bc
        pop bc
        djnz .y
        ld a,(V_ANY)
        or a
        ret

; upload: TILEB -> pattern A
upload: ld c,a
        srl a
        bit 0,c
        jr z,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        ld hl,TILEB
        ld bc,0x005B                ; B = 0: 256 is too many: two halves of 128
        ld b,128
        otir
        ret

; put: A = sprite slot, B = pattern, D = column, E = row of the tile, from V_X, V_Y: writes SPRTAB and the sprite
put:    nextreg 0x34,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,SPRTAB>>8
        ld h,a
        push hl
        pop ix
        ld a,d
        swapnib
        ld hl,(V_X)
        add hl,a
        ld (ix+0),l
        ld (ix+1),h
        ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        nextreg 0x37,a
        ld a,e
        swapnib
        ld hl,(V_Y)
        add hl,a
        ld (ix+2),l
        ld (ix+3),h
        ld a,l
        nextreg 0x36,a
        ld a,b
        srl a
        or 0xC0                     ; visible, extended
        ld (ix+4),a
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca                        ; pattern bit 0 -> bit 6
        or 0x80                     ; 4-bit
        ld c,a
        ld a,h
        and 1
        or c
        ld (ix+5),a
        nextreg 0x39,a
        ; what of the tile the figure really fills: a window beside it should not hide it
        ld c,1
        ld a,d
        or a
        jr nz,.nl
        set 4,c
.nl:    ld a,e
        or a
        jr nz,.nt
        set 5,c
.nt:    ld (ix+6),c
        ld a,(V_NC)                 ; width
        dec a
        cp d
        ld c,0xF0
        jr nz,.w
        ld a,(V_WB)
        add a,a
        add a,a
        add a,a
        add a,2
        ld c,a
        ld a,d
        swapnib
        neg
        add a,c                     ; pixels in the last column
        dec a
        swapnib
        ld c,a
.w:     ld a,(V_NR)                 ; height
        dec a
        cp e
        ld a,15
        jr nz,.h
        ld a,(V_HL)
        add a,2
        ld b,a
        ld a,e
        swapnib
        neg
        add a,b
        dec a
.h:     or c
        ld (ix+7),a
        ret

; hide: A = sprite slot; forgets it
hide:   nextreg 0x34,a
        nextreg 0x38,0
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,SPRTAB>>8
        ld h,a
        ld a,l
        add a,6
        ld l,a
        ld (hl),0
        ret

; pack_room: the canvas becomes room sprites, tiles with pixels only
pack_room:
        ld d,0
.c:     ld e,0
.r:     push de
        call pack
        pop de
        jr z,.next
        ld a,(V_NP)
        cp 128
        jr nc,.drop
        ld a,(V_NS)
        cp MAXROOM
        jr nc,.drop
        ld a,(V_NP)
        push de
        call upload
        pop de
        ld a,(V_NP)
        ld b,a
        inc a
        ld (V_NP),a
        ld a,(V_NS)
        ld c,a
        inc a
        ld (V_NS),a
        ld a,c
        call put
.next:  inc e
        ld a,(V_NR)
        cp e
        jr nz,.r
        inc d
        ld a,(V_NC)
        cp d
        jr nz,.c
        ret
.drop:  ld hl,V_DROP
        inc (hl)
        jr .next

; c_kn: the Knight
c_kn:   ld hl,(V_SP)                ; the dead stack word holds e_kn2 here, the original's return there
        dec hl
        ld (hl),0xAD
        dec hl
        ld (hl),0x57
        ld a,(V_HID)
        or a
        call nz,unhide
        ld a,(KSHIFT)
        and 3
        ld c,a
        ld a,(KFACE)
        or a
        jr z,.f
        ld a,4
        add a,c
        ld c,a
.f:     ld a,c                      ; C = image 0-7 (4-7: the 384 byte offset)
        ld d,96
        ld e,a
        mul d,e
        ld hl,0xF3F4
        add hl,de
        ld (V_G),hl
        ld hl,0xF6F4
        add hl,de
        ld (V_M),hl
        ld a,c
        add a,a
        add a,a
        add a,a
        ld hl,CACHE
        add hl,a
        push hl
        ld hl,(V_G)                 ; checksum of the 192 bytes
        ld de,0
        ld b,96
.s1:    ld a,(hl)
        add de,a
        inc hl
        djnz .s1
        ld hl,(V_M)
        ld b,96
.s2:    ld a,(hl)
        add de,a
        inc hl
        djnz .s2
        pop hl
        ld a,(hl)
        or a
        jr z,.miss
        inc hl
        ld a,(KCOL)
        cp (hl)
        dec hl
        jr nz,.miss
        inc hl
        inc hl
        ld a,(hl)
        cp e
        dec hl
        dec hl
        jr nz,.miss
        inc hl
        inc hl
        inc hl
        ld a,(hl)
        cp d
        dec hl
        dec hl
        dec hl
        jr z,.hit
.miss:  push bc
        ld (hl),1
        inc hl
        ld a,(KCOL)
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        push hl
        ld a,(KCOL)
        call setcol
        ld a,3
        ld (V_WB),a
        ld a,32
        ld (V_HL),a
        call build
        pop hl
        pop bc
        push hl
        push bc
        ld a,c
        ld d,KPAT
        ld e,a
        mul d,e
        ld a,e
        ld (V_PB),a
        xor a
        ld (V_TILE),a
        ld d,0
.kc:    ld e,0
.kr:    push de
        call pack
        pop de
        jr z,.kn
        ld a,d                      ; tile number = column * 3 + row
        add a,a
        add a,d
        add a,e
        ld b,a
        add a,0
        ld c,a
        ld a,(V_PB)
        add a,c
        push de
        push bc
        call upload
        pop bc
        pop de
        ld hl,V_TILE
        ld a,b
        inc a
        ld b,a
        ld a,0x80
.sh:    rlca
        djnz .sh
        or (hl)
        ld (hl),a
.kn:    inc e
        ld a,e
        cp 3
        jr nz,.kr
        inc d
        ld a,d
        cp 2
        jr nz,.kc
        pop bc
        pop hl
        ld a,(V_TILE)
        ld (hl),a
        ld de,-4
        add hl,de
.hit:   ld de,4
        add hl,de
        ld a,(hl)
        ld (V_TILE),a
        ld a,(KX)                   ; sprite position of the canvas origin
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,31
        add hl,de
        ld (V_X),hl
        ld a,(KY)
        ld l,a
        ld h,0
        add hl,de
        ld (V_Y),hl
        ld a,c
        ld d,KPAT
        ld e,a
        mul d,e
        ld a,e
        ld (V_PB),a
        ld a,(V_TILE)
        ld (V_L),a
        ld a,3
        ld (V_WB),a
        ld (V_NR),a
        ld a,32
        ld (V_HL),a
        ld a,2
        ld (V_NC),a
        ld d,0
.ac:    ld e,0
.ar:    ld a,d
        add a,a
        add a,d
        add a,e
        ld c,a                      ; tile number
        add a,KSLOT
        ld (V_CT),a
        ld a,(V_L)
        rrca
        ld (V_L),a
        jr nc,.ah
        ld a,(V_PB)
        add a,c
        ld b,a
        ld a,(V_CT)
        push de
        call put
        pop de
        jr .an
.ah:    ld a,(V_CT)
        call hide
.an:    inc e
        ld a,e
        cp 3
        jr nz,.ar
        inc d
        ld a,d
        cp 2
        jr nz,.ac
        ret

; unhide: tiles a window hid come back
unhide: xor a
        ld (V_HID),a
        ld hl,SPRTAB+6
        ld b,0
.l:     ld a,b
        cp 128
        ret z
        ld a,(hl)
        and 3
        cp 2
        jr nz,.n
        ld a,(hl)
        and 0xFC
        or 1
        ld (hl),a
        ld a,b
        nextreg 0x34,a
        push hl
        ld de,-2
        add hl,de
        ld a,(hl)
        nextreg 0x38,a
        pop hl
.n:     ld de,8
        add hl,de
        inc b
        jr .l

; c_all: every figure sprite goes; room pool empty
c_all:  ld b,128
        ld c,0
.l:     ld a,c
        call hide
        inc c
        djnz .l
        xor a
        ld (V_NS),a
        ld (V_HID),a
        ld a,RFIRST
        ld (V_NP),a
        ret

; c_ov: the crew. Page 27 at slot 5: 0xA000 tiles, sum (2): of the cells the crew sit in, or no overlay (a changed room);
; 0xA010 X (2), Y (2) per tile; 0xA100 128 bytes per tile
OVPG    EQU 27
c_ov:   ld a,(23701)
        cp 1
        ret nz
        nextreg 0x55,OVPG
        ld ix,LINES+288             ; line 144
        ld de,0
        ld b,24
.l:     push bc
        ld l,(ix+0)
        ld h,(ix+1)
        inc ix
        inc ix
        ld a,9
        add hl,a
        ld b,15
.c:     ld a,(hl)
        add de,a
        inc hl
        djnz .c
        pop bc
        djnz .l
        ld hl,(0xA001)
        or a
        sbc hl,de
        jr nz,.out
        ld a,(0xA000)
        ld (V_OC2),a
        ld hl,0xA010
        ld (V_OP),hl
        ld hl,0xA100
        ld (V_OD),hl
.t:     ld hl,(V_OD)
        ld de,TILEB
        ld bc,128
        ldir
        ld (V_OD),hl
        ld hl,(V_OP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_X),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_Y),de
        ld (V_OP),hl
        ld a,(V_NP)
        call upload
        ld a,(V_NP)
        ld b,a
        inc a
        ld (V_NP),a
        ld a,(V_NS)
        ld c,a
        inc a
        ld (V_NS),a
        ld a,c
        ld de,0
        call put
        ld (ix+6),1                 ; every line of the tile is real: no ring edges
        ld (ix+7),0xFF
        ld hl,V_OC2
        dec (hl)
        jr nz,.t
.out:   nextreg 0x55,GP5
        ret

; c_win: rectangle (25765) left, (25766) top, (25767) right, (25768) bottom (cells): hide the tiles that touch it
c_win:  ld a,(25765)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_WN),hl
        ld a,(25767)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,39
        add hl,de
        ld (V_WN+2),hl
        ld a,(25766)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_WN+4),hl
        ld a,(25768)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,39
        add hl,de
        ld (V_WN+6),hl
        ld ix,SPRTAB
        ld c,0
.l:     ld a,(ix+6)
        and 3
        cp 1
        jr nz,.n
        ld e,(ix+0)                 ; left edge, past a ring column
        ld d,(ix+1)
        bit 4,(ix+6)
        jr z,.a
        inc de
.a:     ld hl,(V_WN+2)              ; window right < left edge: clear of it
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+7)                 ; right edge
        swapnib
        and 15
        ld l,(ix+0)
        ld h,(ix+1)
        add hl,a
        ld de,(V_WN)
        or a
        sbc hl,de
        jr c,.n
        ld e,(ix+2)                 ; top edge
        ld d,(ix+3)
        bit 5,(ix+6)
        jr z,.b
        inc de
.b:     ld hl,(V_WN+6)
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+7)                 ; bottom edge
        and 15
        ld l,(ix+2)
        ld h,(ix+3)
        add hl,a
        ld de,(V_WN+4)
        or a
        sbc hl,de
        jr c,.n
        ld a,(ix+6)
        and 0xFC
        or 2
        ld (ix+6),a
        ld a,1
        ld (V_HID),a
        ld a,c
        nextreg 0x34,a
        nextreg 0x38,0
.n:     ld de,8
        add ix,de
        inc c
        ld a,c
        cp 128
        jp nz,.l
        ret
page_end:

; --- setup routine (stub bank, 0xD000): alt ROM image 0 = ROM 0 (the Bridge's star map reads ROM 0 at 0x0D00- from bank 1
; code, 7FFD = 1), palette, sprites hidden, layer on. Same paging steps as Target Renegade's.
        ORG 0xD000
setup:  nextreg 0x54,20             ; stub page alias at 0x8000
        jp .alias - 0x4000
.alias: ld bc,0x243B                ; unlock 7FFD paging (NextReg $08 bit 7)
        ld a,8
        out (c),a
        inc b
        in a,(c)
        or 0x80
        nextreg 0x08,a
        ld bc,0x1FFD                ; ROM 0
        xor a
        out (c),a
        ld b,0x7F
        out (c),a
        nextreg 0x8C,0xC0           ; alt ROM write mode: reads ROM, writes the image
        ld hl,0
        ld de,0
        ld bc,0x4000
        ldir
        nextreg 0x8C,0
        nextreg 0x56,20
        nextreg 0x57,21
        jp .back
.back:  nextreg 0x54,GP4
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
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
        nextreg 0x15,0x01           ; sprites on, SLU, higher number on top
        ret
pal:                                ; 16 palette bytes appended by Python

        SAVEBIN "kt_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "kt_page.bin",0x9440,page_end-0x9440
        SAVEBIN "kt_setup.bin",0xD000,pal-0xD000

; ---------------------------------------------------------------------------------------------
; Loading screen (knight_tyme.add_loading; from runs/knight_tyme/loading/work/stub.asm, the Rambo stub, 2026-11-04).
; The .nex carries the tape's loading screen in bank 5's screen area; bank 22 (pages 44, 45) is the entry
; bank, PC 0xC000: this code at 0xC000, bank 5's own screen bytes at 0xC200 (filled by the engine from the
; build), the exit at 0xFFD0. On entry the loader has left: slots 2-5 = 10,11,4,5, slots 6-7 = 68,69, DI,
; SP = 0xDFFE and the start address pushed just below SP, in the entry bank. The original start is page 20
; at 0xC000. No byte outside this bank differs when it leaves; its last instruction puts page 5 back at
; slot 5 and the next fetch is 0xC000 of page 20 (no trampoline in RAM). 250 frames or a key.
        MODULE ldscr
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 45; below it the stub's call stack
SEL     equ     $FE02           ; port $243B as found
TIMEOUT equ     250             ; frames: 5 s at 50 Hz
CAP     equ     250             ; most frames to wait for a held key to go
CLEAR   equ     3               ; frames with no key before leaving
LINE    equ     192             ; first line below the picture
picture equ     $C200           ; bank 5's own screen bytes (6912), written by knight_tyme.add_loading

        org     $C000
start:
        di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,$243B
        in      a,(c)
        ld      (SEL),a
        xor     a
        out     ($fe),a
; Show: a key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the menu doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,picture
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        xor     a
        out     ($fe),a
        ld      bc,$243B
        ld      a,(SEL)
        out     (c),a
        nextreg $55,45
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,$243B
        ld      a,$1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,($fe)
        cpl
        and     $1f
        or      e
        ld      e,a
        ld      a,d
        ret
code_end:
        org     $FFD0
        disp    $BFD0
; Runs from page 45 at slot 5. Bank 10's top bytes get what the loader's stack left there.
final:  nextreg $56,20
        nextreg $57,21
        ld      hl,$C000
        ld      ($DFFC),hl
        ld      sp,REGS-$4000-12
        pop     iy
        pop     ix
        ld      hl,($BFFF)      ; MEMPTR = $C000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,$DFFE
        ds      $BFFC-$
        nextreg $55,5           ; falls through to $C000, page 20
        assert  $ == $C000
        ent
        ENDMODULE
        SAVEBIN "kt_lstub.bin",0xC000,ldscr.code_end-0xC000
        SAVEBIN "kt_lfinal.bin",0xFFD0,0x30
