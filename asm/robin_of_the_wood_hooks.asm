; IRQ remains enabled: its verified footprint never touches slots 1, 3 or 4.
; It writes AY registers, not a timed beeper loop; AY oscillators keep real time.
; Robin of the Wood 128K. All figure families; replay and JNext evidence in the owned pilot.
        DEVICE ZXSPECTRUMNEXT
        ORG 0x386E
e_gfx:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call capture
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xC67E
e_commit:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call commit
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xC955
e_room:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call clear
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        ld hl,0x7C02
        ret
e_menu:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call clear
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xCE73
e_start:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call clear
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xCE67
e_arrow_erase:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call arrow_erase
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xBBEC
e_arrow_draw:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call arrow_draw
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        jp 0xBBEC
e_item:
        nextreg 7,3
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        nextreg 0x53,26
        call item
        nextreg 0x54,4
        nextreg 0x53,11
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        nextreg 7,0
        ld (0xD8C2),a
        ret
e_hud: push af
        ld a,0x77
        ld (0xD7AD),a
        pop af
        xor a
        ld (0xD81D),a
        ret
rom_end:
        ORG 0x6000
capture:
        ld (gfxptr),hl
        ld (coords),bc
        ld (object),ix
        and 0x80
        ld (facing),a
        ld hl,18
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (caller),de
        ld iy,descriptors
        ld hl,objects
        ld b,13
.slot:  ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        ld hl,(object)
        or a
        sbc hl,de
        pop hl
        jr z,.found
        ld de,16
        add iy,de
        djnz .slot
        ld a,1
        ld (error),a
        ret
.found: ld (iy+0),0
        ld hl,(caller)
        ld de,0xCA52
        or a
        sbc hl,de
        ret nz
        ld hl,table
        ld b,(hl)
        inc hl
.find:  ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        ld hl,(gfxptr)
        or a
        sbc hl,de
        pop hl
        jr z,.image
        ld de,49
        add hl,de
        djnz .find
        ld a,2
        ld (error),a
        ret
.image: ld a,(hl)
        ld (kind),a
        inc hl
        ld a,(coords+1)
        and 7
        ld e,a
        ld a,(facing)
        rlca
        rlca
        rlca
        rlca
        and 8
        or e
        ld e,a
        add a,a
        add a,e
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        ld (iy+6),a
        inc hl
        ld a,(hl)
        ld (iy+7),a
        inc hl
        ld a,(hl)
        ld (iy+8),a
        ld (iy+0),1
        ld (iy+5),3
        ld (iy+4),2
        ld a,(kind)
        and 1
        jr nz,.tiled
        ld a,(coords)
        ld l,a
        ld h,0
        add hl,hl
        ld de,15
        add hl,de
        ld (iy+1),l
        ld a,(kind)
        and 0xF0
        or h
        ld (iy+2),a
        ld a,(coords+1)
        add a,31
        ld (iy+3),a
        ret
.tiled: ld (iy+4),4
        ld a,(coords)
        srl a
        srl a
        sub 3
        ld e,a
        ld a,(facing)
        or a
        ld a,e
        jr z,.unmirrored
        dec a
.unmirrored:
        and 31
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,31
        add hl,de
        ld (iy+1),l
        ld a,(kind)
        and 0xF0
        or h
        ld (iy+2),a
        ld a,(coords+1)
        and 0xF8
        add a,23
        ld (iy+3),a
        ret

arrow_slot:
        ld a,e
        sub 0x3F
        srl a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,descriptors+13*16
        add hl,de
        push hl
        pop iy
        ret
arrow_erase:
        call arrow_slot
        ld (iy+0),0
        ret
arrow_draw:
        call arrow_slot
        ld (iy+0),1
        ld (iy+4),1
        ld (iy+5),1
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,31
        add hl,de
        ld (iy+1),l
        ld (iy+2),h
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,31
        ld (iy+3),a
        ld a,(arrow_pattern)
        ld (iy+6),a
        ld hl,(arrow_pattern+1)
        ld (iy+7),l
        ld (iy+8),h
        ret

item:   ld (itemid),a
        ld (coords),de
        ld a,0x77
        ld (0xD7AD),a
        ld a,(itemid)
        bit 5,a
        ret nz
        and 31
        cp 8
        ret nc
        ld (kind),a
        xor a
        ld (0xD7AD),a
        ld a,d
        and 0xFC
        ld l,a
        ld h,0
        add hl,hl
        ld de,47
        add hl,de
        ld (itemx),hl
        ld a,(coords)
        add a,31
        ld (itemy),a
        ld iy,descriptors+17*16
        ld b,9
.search:
        ld a,(iy+0)
        or a
        jr z,.next
        ld a,(itemx)
        cp (iy+1)
        jr nz,.next
        ld a,(itemx+1)
        cp (iy+2)
        jr nz,.next
        ld a,(itemy)
        cp (iy+3)
        jr z,.found
.next:  ld de,16
        add iy,de
        djnz .search
        ld a,(itemid)
        bit 7,a
        ret nz
        ld iy,descriptors+17*16
        ld b,9
.free:  ld a,(iy+0)
        or a
        jr z,.found
        ld de,16
        add iy,de
        djnz .free
        ld a,3
        ld (error),a
        ret
.found: ld (iy+0),0
        ld a,(itemid)
        bit 7,a
        ret nz
        ld (iy+0),1
        ld hl,(itemx)
        ld (iy+1),l
        ld (iy+2),h
        ld a,(itemy)
        ld (iy+3),a
        ld a,(kind)
        ld e,a
        add a,a
        add a,a
        add a,e
        ld e,a
        ld d,0
        ld hl,item_table
        add hl,de
        ld a,(hl)
        ld (iy+4),a
        inc hl
        ld a,(hl)
        ld (iy+5),a
        inc hl
        ld a,(hl)
        ld (iy+6),a
        inc hl
        ld a,(hl)
        ld (iy+7),a
        inc hl
        ld a,(hl)
        ld (iy+8),a
        ret

; Allocate only live figures. Cache by graphic and allocated slot, so an idle
; figure uploads nothing and hidden records cost no sprite port writes.
commit:
        ld ix,descriptors
        xor a
        ld (slotbase),a
        ld a,26
        ld (remaining),a
.object:
        ld a,(ix+0)
        or a
        jr nz,.live
        ld (ix+9),0
        jp .next
.live:  ld a,(slotbase)
        ld (firstslot),a
        ld d,(ix+4)
        ld e,(ix+5)
        mul d,e
        add a,e
        cp 129
        jr c,.fits
        ld a,4
        ld (error),a
        ret
.fits:  ld (end_slot),a
        ld a,(firstslot)
        cp (ix+12)
        jr nz,.upload
        ld a,(ix+6)
        cp (ix+9)
        jr nz,.upload
        ld a,(ix+7)
        cp (ix+10)
        jr nz,.upload
        ld a,(ix+8)
        cp (ix+11)
        jr nz,.upload
        ld a,(ix+1)
        cp (ix+13)
        jr nz,.attrs
        ld a,(ix+2)
        cp (ix+14)
        jr nz,.attrs
        ld a,(ix+3)
        cp (ix+15)
        jp z,.advance
        jr .attrs
.upload:
        ld a,(ix+6)
        ld (ix+9),a
        nextreg 0x54,a
        ld l,(ix+7)
        ld h,(ix+8)
        ld (ix+10),l
        ld (ix+11),h
        ld a,(firstslot)
        ld (ix+12),a
        ld e,a
        ; Next pattern-port selection uses a 256-byte pattern plus bit 7 for
        ; the upper 128-byte 4bpp half.
.tile_upload:
        ld a,e
        srl a
        bit 0,e
        jr z,.lower
        or 0x80
.lower: ld bc,0x303B
        out (c),a
        ld bc,0x805B
        otir
        inc e
        ld a,(end_slot)
        cp e
        jr nz,.tile_upload
.attrs:
        ld a,(ix+1)
        ld (ix+13),a
        ld a,(ix+2)
        ld (ix+14),a
        ld a,(ix+3)
        ld (ix+15),a
        ld (tile_y),a
        ld a,(firstslot)
        ld e,a
        ld a,(ix+5)
        ld (rows_left),a
.row:   ld l,(ix+1)
        ld a,(ix+2)
        and 1
        ld h,a
        ld d,(ix+4)
.tile:  ld a,e
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,(ix+2)
        and 0xF0
        or h
        nextreg 0x37,a
        ld a,(tile_y)
        nextreg 0x36,a
        ld a,e
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,e
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld bc,16
        add hl,bc
        inc e
        dec d
        jr nz,.tile
        ld a,(tile_y)
        add a,16
        ld (tile_y),a
        ld a,(rows_left)
        dec a
        ld (rows_left),a
        jr nz,.row
.advance:
        ld a,(end_slot)
        ld (slotbase),a
.next:  ld de,16
        add ix,de
        ld a,(remaining)
        dec a
        ld (remaining),a
        jp nz,.object
        ld a,(last_used)
        ld b,a
        ld a,(slotbase)
        ld (last_used),a
.hide:  cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .hide
clear:  ld hl,descriptors
        ld de,descriptors+1
        ld bc,26*16-1
        xor a
        ld (hl),a
        ldir
        ld (error),a
        ld (last_used),a
.hide:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hide
        ret

gfxptr: dw 0
coords: dw 0
object: dw 0
caller: dw 0
facing: db 0
kind: db 0
itemid: db 0
itemx: dw 0
itemy: db 0
slotbase: db 0
firstslot: db 0
end_slot: db 0
remaining: db 0
rows_left: db 0
tile_y: db 0
last_used: db 0
error: db 0
objects: dw 0xAAB8,0xAAC3,0xAACE,0xAAD9,0xAAE4,0xDDE5,0xDDF0,0xDDFB,0xDE06,0xCD77,0xB7BD,0xBA4F,0xBB1B
descriptors: ds 26*16,0
item_table: ds 40,0
arrow_pattern: ds 3,0
        ALIGN 256
table: db 0
page_end:
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,palette
        ld b,48
.pal:   ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pal
        nextreg 0x4B,0
        xor a
.hide:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hide
        nextreg 0x1C,2
        nextreg 0x19,16
        nextreg 0x19,239
        nextreg 0x19,0
        nextreg 0x19,143
        nextreg 0x15,1
        ret
palette:db 0,0,109,1,97,1,162,1,12,0,22,1,180,0,182,1,0,0,96,0,224,0,227,1,28,0,31,1,252,0,255,1,0,0,109,1,97,1,162,1,108,0,22,1,180,0,182,1,0,0,96,0,224,0,227,1,28,0,31,1,252,0,255,1,0,0,109,1,97,1,162,1,13,1,22,1,180,0,182,1,0,0,96,0,224,0,227,1,28,0,31,1,252,0,255,1
setup_end:
        SAVEBIN "row_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "row_page.bin",0x6000,page_end-0x6000
        SAVEBIN "row_setup.bin",0xD000,setup_end-0xD000

; ---------------------------------------------------------------------------------------------------
; Loading screen hold (the .nxc e0c97d69's builds, default and Enhanced; imported 2026-11-04 from the
; pilot's loading/work/stub.asm, unchanged but for the picture: the build puts bank 5's own screen at
; loading.picture, robin_of_the_wood.loading_nex). The .nex's bank 5 screen area holds the tape's
; loading screen (block 4); this is bank 34 (pages 68, 69), the entry bank, PC $C000: it shows the
; picture until a key or 5 s, waits for the key to go, puts bank 5's screen back and falls through to
; $C000, page 20 (the converter's own stub). Assembled after the hook SAVEBINs (device 0xC000-0xFFFF).
        MODULE loading
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 69; below it the stub's call stack
SEL     equ     $FE02           ; port $243B as found
TIMEOUT equ     250             ; frames: 5 s at 50 Hz
CAP     equ     250             ; most frames to wait for a held key to go
CLEAR   equ     3               ; frames with no key before leaving
LINE    equ     192             ; first line below the picture

        org     $C000
start:  di
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
        nextreg $55,69
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

        ds      $C200-$
picture:
        ds      6912            ; bank 5's own screen, put in by the build (the file has the loading screen there)
        assert  $ <= $DF00      ; $DFxx: the loader's stack
        ds      $FFD0-$         ; REGS is written at run time; zero in the file
        disp    $-$4000
; Runs from page 69 at slot 5. Bank 10's top bytes get what the loader's stack left there.
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
        SAVEBIN "row_loading.bin",0xC000,0x0200         ; code before loading.picture
        SAVEBIN "row_loadend.bin",0xFFD0,0x0030         ; loading.final (the rest of the bank is zero)
