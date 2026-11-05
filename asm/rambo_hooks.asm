; Rambo (Ocean, 1985, 48K) - figures (display-list type >= 0x40) as hardware sprites.
; Stubs in game RAM 0x5D80- (zero and untouched in every recording; only the end-of-game fade reads it).
; Everything else in Next page H_PAGE, mapped at slot 1 only while a hook runs (the game reads the
; ROM as its random numbers and as fade masks, so the alt ROM route would change the game).
; Interrupts are off at every plot and blit site (verify counts it); the hide sites use NEXTREG only.
;
; Patch sites (original bytes checked by rambo.py):
;   0x8052 DD 7E 09  LD A,(IX+9)     -> JP s_p1   plot (cell or rotated), whole figure
;   0x8670 78 32 98  LD A,B / LD (,  -> JP s_p2   plot, clipped
;   0x813E 21 00 C0  LD HL,0xC000    -> CALL s_bl blit: sprites commit with it
;   0x8093 3A 4F FF  LD A,(0xFF4F)   -> JP s_pt   attribute painter: an empty list is now possible
;   0x6C8F 11 01 40, 0x7600 0E 13 3E, 0x74B3 0E 1F 3E -> JP s_h3 / s_h1 / s_h2: sprites and Layer 2 off
;   0x8EB4 DD 21 AE    LD IX,0x79AE    -> JP s_tn: the start of a life: portraits on during its tune
        DEVICE ZXSPECTRUMNEXT

H_PAGE  EQU 26
FIGTYPE EQU 0x40
DIR     EQU 0x3000          ; 8-byte entries: desc, page, tile data, tile count, tile list
LOG     EQU 0x3A00          ; 5 attribute bytes per tile, written at the commit
MAXP    EQU 60              ; two pattern sets of 60; patterns 60-63 are the portrait
IMG_PAGE EQU 28             ; the first tile page: the portrait's 4 tiles first
L2_BANK EQU 20

        ORG 0x5D80
s_p1:   ld a,(iy+1)
        cp FIGTYPE
        jr nc,s_f1
s_o1:   ld a,(ix+9)
        jp 0x8055
s_f1:   ld a,(ix+9)         ; what the skipped plot leaves in memory
        ld (0x8080),a
        ld a,b
        ld (0x8078),a
        ld (0xFF2A),sp
        nextreg 0x51,H_PAGE
        nextreg 0x07,3
        xor a
        jp h_fig
s_p2:   ld a,(iy+1)
        cp FIGTYPE
        jr nc,s_f2
s_o2:   ld a,b
        ld (0x8698),a
        jp 0x8674
s_f2:   ld a,b
        ld (0x8698),a
        ld (0xFF2A),sp
        nextreg 0x51,H_PAGE
        nextreg 0x07,3
        ld a,1
        jp h_fig
s_ret:  nextreg 0x07,0
        nextreg 0x51,0xFF
        ret
s_fb0:  nextreg 0x07,0
        nextreg 0x51,0xFF
        jp s_o1
s_fb1:  nextreg 0x07,0
        nextreg 0x51,0xFF
        jp s_o2
s_bl:   nextreg 0x51,H_PAGE
        nextreg 0x07,3
        push bc             ; C = 0 from the wait loop: the blit's counter
s_blc:  call h_commit
        pop bc
        nextreg 0x07,0
        nextreg 0x51,0xFF
        ld hl,0xC000
        ret
s_pt:   ld a,(0xFF4F)
        or a
        jp nz,0x8096
        jp 0x80DA
s_tn:   push af
        push bc
        push de
        push hl
        nextreg 0x51,H_PAGE
        nextreg 0x07,3
        call h_commit
        nextreg 0x69,0      ; the play area is black ink on black during the tune: no dirt behind it yet
        nextreg 0x07,0
        nextreg 0x51,0xFF
        pop hl
        pop de
        pop bc
        pop af
        ld ix,0x79AE
        jp 0x8EB8
s_h1:   nextreg 0x15,0
        nextreg 0x69,0
        ld c,0x13
        ld a,0x17
        jp 0x7604
s_h2:   nextreg 0x15,0
        nextreg 0x69,0
        ld c,0x1F
        ld a,0x17
        jp 0x74B7
s_h3:   nextreg 0x15,0
        nextreg 0x69,0
        ld de,0x4001
        jp 0x6C92
ram_end:

        ORG 0x2000
; A = 0 from s_p1, 1 from s_p2. BC, IX, IY stay; A, DE, HL, F are dead after the plot.
; Stack here: return of the plot's CALL, then the attribute list pointer the caller pushed.
h_fig:  ld (vvar),a
        push bc
        ld hl,DIR
        ld a,(ndir)
        ld b,a
.find:  ld a,(hl)
        cp ixl
        jr nz,.nx
        inc hl
        ld a,(hl)
        dec hl
        cp ixh
        jr z,.got
.nx:    ld a,8
        add hl,a
        djnz .find
.fb:    pop bc              ; not in the table, or no pattern left: the original plot
        ld a,(vvar)
        or a
        jp z,s_fb0
        jp s_fb1
.got:   inc hl
        inc hl
        ld a,(hl)
        ld (vpage),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)           ; DE = tile data at slot 0
        inc hl
        ld a,(hl)
        ld (vn),a
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)           ; BC = tile list
        ld hl,pcount
        add a,(hl)
        cp MAXP+1
        jr nc,.fb
h_rew:  ld hl,4             ; drop this figure's attribute box from the painter's list
        add hl,sp
        ld a,(hl)
        sub 5
        ld (hl),a
        jr nc,.nb
        inc hl
        dec (hl)
.nb:    ld hl,0xFF4F
        dec (hl)
        push de
        push bc
        ld a,(iy+1)         ; colour: the game's own table, ink + bright -> palette offset
        ld e,a
        ld d,0
        ld hl,0x87AF
        add hl,de
        ld a,(hl)
        ld b,a
        and 7
        ld c,a
        ld a,b
        and 0x40
        rrca
        rrca
        rrca
        or c
h_col:  swapnib
        ld (vpal),a
        ld a,(iy+2)         ; X = column * 8 + the graphic's rotation + 32
        and 0xF8
        ld l,a
        ld h,0
        bit 6,(iy+0)        ; flagged: x is signed (a small positive x can carry the flag too)
        jr z,.xp
        bit 7,a
        jr z,.xp
        dec h
.xp:    ld a,(ix+10)
h_x32:  add a,31            ; tiles start one pixel out, for the outline
        add hl,a
        ld (vx),hl
        ld a,(iy+4)         ; y counts up from the bottom of the screen
        and 0x7F
        add a,(iy+3)
        ld l,a
        ld h,0
        jr c,.yp
        bit 7,(iy+0)
        jr z,.yp
        dec h
.yp:    ex de,hl
        ld a,(ix+8)
        ld l,a
        ld h,0
        add hl,de
        ex de,hl
h_y224: ld hl,223           ; Y = 32 + 192 - y - height, one pixel up for the outline
        or a
        sbc hl,de
        ld (vy),hl
        pop bc
        pop de
        ld a,(vpage)
        nextreg 0x50,a
        ld a,(vn)
        or a
        jp z,h_done
        ld (vcnt),a
        ex de,hl
h_tile:  ld a,(bc)            ; HL = tile data, BC = tile list
        inc bc
        ld (vlist),bc
        ld d,a
        and 0xF0
        push hl
        ld hl,(vx)
        add hl,a
        ld (tx),hl
        ld a,d
        and 0x0F
        swapnib
        ld hl,(vy)
        add hl,a
        ld (ty),hl
        ld hl,(tx)          ; the panel: X 192 on is off the play area
        ld a,h
        or a
        jr nz,h_full
        ld a,l
h_clip: cp 192
        jr nc,h_skip
h_clip2: cp 177
        jr c,h_full
        ld a,192
        sub l
        ld (vlim),a
        call pattern
        pop hl
        ld d,16
.r:     ld a,(vlim)
        ld e,a
        ld b,8
.b:     ld a,(hl)
        inc hl
        inc e
        dec e
        jr z,.z
        dec e
        jr z,.o
        dec e
        jr .k
.o:     and 0xF0
        jr .k
.z:     xor a
.k:     out (0x5B),a
        djnz .b
        dec d
        jr nz,.r
        jr h_log
h_skip:  pop hl
        ld de,128
        add hl,de
        jr h_next
h_full:  call pattern
        pop hl
        ld bc,0x805B
        otir
h_log:   push hl
        ld a,(pcount)
        ld e,a
        ld a,(vbase)
        add a,e
        ld e,a
        ld hl,(vlog)
        ld a,(tx)
        ld (hl),a
        inc hl
        ld a,(ty)
        ld (hl),a
        inc hl
        ld a,(tx+1)
        and 1
        ld d,a
        ld a,(vpal)
        or d
        ld (hl),a
        inc hl
        ld a,e
        srl a
        or 0xC0
        ld (hl),a
        inc hl
        ld a,e
        and 1
        rrca
        rrca
        or 0x80
        ld d,a
        ld a,(ty+1)
        and 1
        or d
        ld (hl),a
        inc hl
        ld (vlog),hl
        ld hl,pcount
        inc (hl)
        pop hl
h_next:  ld bc,(vlist)
        ld a,(vcnt)
        dec a
        ld (vcnt),a
        jp nz,h_tile
h_done:  nextreg 0x50,0xFF
        pop bc
        jp s_ret

; select this frame's next pattern
pattern: ld a,(pcount)
        ld e,a
        ld a,(vbase)
        add a,e
        rrca
        ld bc,0x303B
        out (c),a
        ret

; the blit: the frame's attributes in one burst, the rest hidden, the other pattern set next
h_commit:
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,LOG
        ld a,(pcount)
        ld e,a
        or a
        jr z,.hide
        ld c,0x57
.w:     ld b,5
        otir
        dec e
        jr nz,.w
.hide:  ld a,(pcount)
        ld d,a
        ld a,(prevn)
        sub d
        jr z,.nh
        jr c,.nh
        ld e,a
        ld c,0x57
.h:     xor a
        out (c),a
        out (c),a
        out (c),a
        ld a,0x40
        out (c),a
        xor a
        out (c),a
        dec e
        jr nz,.h
.nh:    ld a,d
        ld (prevn),a
        xor a
        ld (pcount),a
        ld hl,LOG
        ld (vlog),hl
        ld a,(vbase)
        xor 64              ; 0-59, 64-123
        ld (vbase),a
        ld hl,0x4876        ; each portrait shows if the game's XOR plot (0x7634) has it on the screen:
h_ln:   ld a,(hl)           ; a row through its middle, 4 bytes each
        inc l
        or (hl)
        inc l
        or (hl)
        inc l
        or (hl)
        inc l
        ld d,a              ; D = first
        ld a,(hl)
        inc l
        or (hl)
        inc l
        or (hl)
        inc l
        or (hl)
        ld (vpo2),a
        ld bc,0x303B
        ld a,120
        out (c),a
        ld c,0x57
        ld hl,ptab
        ld e,8
.pl:    ld a,e
        cp 5
        ld a,d
        jr nc,.p1
        ld a,(vpo2)
.p1:    or a
        ld b,0x7F           ; hidden
        jr z,.ph
        ld b,0xFF
.ph:    ld a,(hl)
        inc hl
        out (c),a
        ld a,(hl)
        inc hl
        out (c),a
        ld a,(hl)
        inc hl
        out (c),a
        ld a,(hl)
        inc hl
        and b
        out (c),a
        ld a,(hl)
        inc hl
        out (c),a
        dec e
        jr nz,.pl
        ld a,(vnr15)
        nextreg 0x15,a
        ld a,(vnr69)
        nextreg 0x69,a
; The dirt is pinned to the scenery. The game moves every object by the steps in 0xFF32 (x +-8, y +-2, or +-8 in the
; helicopter), the copy of 0xFF3D it took at the top of the frame, and adds the same steps to 0xFF2F (y) and 0xFF33 (x, 1 per
; 8 pixels) at the end of that frame's logic, from the 0xFF3D the player's code has just set: they lead the objects by one
; frame. So each blit shows what the world values held at the commit before.
; A new life or a restart sets them outright: a change larger than a step takes effect at once.
        ld hl,vpy
        ld a,(0xFF2F)
        sub (hl)
        add a,8
        cp 17
        jr c,.ys
        ld a,(0xFF2F)
        ld (hl),a
.ys:    ld hl,vpx
        ld a,(0xFF33)
        sub (hl)
        inc a
        cp 3
        jr c,.xs
        ld a,(0xFF33)
        ld (hl),a
.xs:
h_scy:  ld a,(vpy)
        neg
h_scr:  and 63              ; the dirt repeats every 64 rows: 64 divides Layer 2's 192
        ld e,a
        ld a,(vpx)
h_scx:  add a,a
        add a,a
        add a,a             ; wraps at 256 as Layer 2 does, across the 256 x 64 tile
        ld d,a
; The commit runs about 60 lines into the frame, and the blit after it finishes early in the next one, ahead of the beam:
; the new picture first shows in the next frame, from its top line. The copper changes the scroll there, not now.
        nextreg 0x62,0      ; copper stopped, index 0
        nextreg 0x61,0
h_cw:   nextreg 0x60,0x80   ; WAIT line 0, the top line of the picture
        nextreg 0x60,0
        nextreg 0x60,0x16   ; MOVE NR 0x16, x
        ld a,d
        nextreg 0x60,a
        nextreg 0x60,0x17   ; MOVE NR 0x17, y
        ld a,e
        nextreg 0x60,a
        nextreg 0x60,0xFF   ; HALT
        nextreg 0x60,0xFF
        nextreg 0x62,0x40   ; run once, from index 0
        ld a,(0xFF2F)
        ld (vpy),a
        ld a,(0xFF33)
        ld (vpx),a
        ret

; x, y, palette offset 1 + x8, visible + 4-bit + pattern, 4-bit + pattern low
ptab:   db 208,104,0x10,0xC0+30,0x80
        db 224,104,0x10,0xC0+30,0xC0
        db 208,120,0x10,0xC0+31,0x80
        db 224,120,0x10,0xC0+31,0xC0
        db 240,104,0x10,0xC0+30,0x80
        db 0,104,0x11,0xC0+30,0xC0
        db 240,120,0x10,0xC0+31,0x80
        db 0,120,0x11,0xC0+31,0xC0
vnr15:  db 1                ; 9 in the Enhanced set: sprites, ULA, Layer 2
vnr69:  db 0                ; 0x80 in the Enhanced set: Layer 2 on in play
vpy:    db 0
vpx:    db 0

ndir:   db 0                ; set by the build
pcount: db 0
prevn:  db 0
vbase:  db 0
vvar:   db 0
vpage:  db 0
vn:     db 0
vcnt:   db 0
vpal:   db 0
vx:     dw 0
vy:     dw 0
tx:     dw 0
ty:     dw 0
vlist:  dw 0
vlim:   db 0
vpo2:   db 0
vlog:   dw LOG
page_end:

        ORG 0xD000
setup:  nextreg 0x43,0x20   ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal_tab
        ld b,0
.n:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .n
        nextreg 0x4B,0      ; nibble 0 is transparent
        ld a,(enh_flag)
        or a
        jr z,.ne
        nextreg 0x43,0x10   ; Enhanced: the dirt's 9-bit browns, entries 0-4 of the Layer 2 palette
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,10
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        nextreg 0x43,0      ; black paper see-through, Layer 2 shows behind it
        nextreg 0x40,16
        nextreg 0x41,0xE3
        nextreg 0x40,24
        nextreg 0x41,0xE3
.ne:    nextreg 0x4A,0      ; what shows where nothing does: black
        nextreg 0x14,0xE3
        nextreg 0x12,L2_BANK
        nextreg 0x13,L2_BANK
        nextreg 0x70,0      ; 256 x 192, no scroll, no clip left over
        nextreg 0x71,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,159    ; Layer 2 stops at the panel, whatever it scrolls
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x57,IMG_PAGE ; the portrait's patterns
        ld bc,0x303B
        ld a,30
        out (c),a
        ld hl,0xE000
        ld d,2
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        nextreg 0x57,21
        xor a
.hd:    nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.hd
        nextreg 0x1C,2      ; as far as the portraits; figures stop at the play area in the hook
        nextreg 0x19,0
        nextreg 0x19,239
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0
        ret
l2_pal: db 0x00,0, 0x44,0, 0x68,1, 0x8C,1, 0x8D,0
enh_flag:
        db 0
pal_tab:
        ds 256
setup_end:

; ---- Loading screen stub (runs/rambo/loading/stub.asm v2, 2026-11-03; ported 2026-11-04) ----
; The loading screen is on show from bank 5 in the file; this puts bank 5 back. rambo.loading_nex()
; makes bank 23 (pages 46, 47; entry bank, PC 0xC000): ld_head at 0xC000, zero to 0xC200, the game's
; own bank 5 screen bytes (6912), zero to 0xFFD0, ld_tail. On entry the loader has left: slots 2-5 =
; 10,11,4,5, slots 6-7 = 68,69, DI, SP = 0xDFFE and the start address pushed just below SP. The
; original start is page 20 at 0xC000. No byte outside this bank differs when it leaves; its last
; instruction puts page 5 back, so the next fetch is 0xC000 with no trampoline in RAM.
        MODULE ldscr
SCREEN  EQU 0x4000
SCRLEN  EQU 6912
REGS    EQU 0xFE00          ; register stack, page 47; below it the stub's call stack
SEL     EQU 0xFE02          ; port 0x243B as found
TIMEOUT EQU 250             ; frames: 5 s at 50 Hz
CAP     EQU 250             ; most frames to wait for a held key to go
CLEAR   EQU 3               ; frames with no key before leaving
LINE    EQU 192             ; first line below the picture
PICTURE EQU 0xC200          ; the game's own screen bytes (rambo.loading_nex)

        ORG 0xC000
start:  di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,0x243B
        in      a,(c)
        ld      (SEL),a
        xor     a
        out     (0xfe),a
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
        ld      hl,PICTURE
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        xor     a
        out     (0xfe),a
        ld      bc,0x243B
        ld      a,(SEL)
        out     (c),a
        nextreg 0x55,47
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
poll:   ld      bc,0x243B
        ld      a,0x1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,(0xfe)
        cpl
        and     0x1f
        or      e
        ld      e,a
        ld      a,d
        ret
head_end:
        ASSERT  head_end <= PICTURE

        ORG 0xFFD0
        DISP    0xBFD0
; Runs from page 47 at slot 5. Bank 10's top bytes get what the loader's stack left there.
final:  nextreg 0x56,20
        nextreg 0x57,21
        ld      hl,0xC000
        ld      (0xDFFC),hl
        ld      sp,REGS-0x4000-12
        pop     iy
        pop     ix
        ld      hl,(0xBFFF)     ; MEMPTR = 0xC000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,0xDFFE
        ds      0xBFFC-$
        nextreg 0x55,5          ; falls through to 0xC000, page 20
        ASSERT  $ == 0xC000
        ENT
        ENDMODULE


        SAVEBIN "ra_ram.bin",0x5D80,ram_end-0x5D80
        SAVEBIN "ra_page.bin",0x2000,page_end-0x2000
        SAVEBIN "ra_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "ra_ldhead.bin",0xC000,ldscr.head_end-0xC000
        SAVEBIN "ra_ldtail.bin",0xFFD0,0x30
