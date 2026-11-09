; Starquake (Bubble Bus, 1985, 48K) - the six moving figures (BLOB, enemies, effects) as hardware sprites.
; Stateless hooks in alt ROM image 1 at 0x386E. The game's own XOR plotter (0xDF70) keeps running with
; its 24 screen stores (LD (HL),A after XOR (HL)) replaced by NOP, one instruction for one, so the ULA
; keeps no figure pixels; each figure is a solid 4-bit sprite (ink, black fill, outline). The game reads
; no bitmap byte but in the plot itself, and reloads A after each loop. The attribute painter 0xD8B1 runs too,
; unchanged; e_pl saves the attributes just before it and e_un (at 0xD964, the end of its loop)
; puts them back, so figures no longer paint their ink into the scenery cells. The painter's
; stores below the attribute area (0x5B00 up, read by the collision code) stay as they were.
;
; Sites (original bytes checked by starquake.py):
;   0xD9CE  CD B1 D8  CALL 0xD8B1 (attribute paint, just after the plot)  -> CALL e_pl
;   0x6194, 0x6618, 0x672A  CD D0 5F  CALL 0x5FD0 (full screen clear)  -> CALL e_cls
;   0xA45F  CD 47 A6  CALL 0xA647 (play area clear, new room)           -> CALL e_rc
;   0xA412  C3 47 A6  JP 0xA647 (jump table entry, same routine)        -> JP e_rc
;   0xD964  21 20 5B  LD HL,0x5B20 (after the paint loop)               -> JP e_un
;   0xE06D  C2 72 DF  JP NZ,0xDF72 (the plot's next object)              -> JP e_ob
; Pace (2026-11-08): every plot follows the game's own sync (0xD9C8: the HALT or the tone that runs to the
; next interrupt), and e_pl and e_un's time pushed some updates past it. The plot takes a fixed time, 25,500 T
; whatever the figures. Its last three objects run at 28 MHz, from e_ob down to e_pl's exit: about half the
; plot, more than the hooks' median time, so no wait, no K, and the sync gives back whatever is over. A stretch
; of the plot, not all of it, because the tone runs in what is left of the frame: the original's share stays.
; Every hook ends with a JP to the original target, so the code the game runs is unchanged and a
; verifier that does not count fetches in 0x386E-rom_end stays in step with the recording.
; Object i (0-5): record 0xDD18+32i as the plot left it: +0/1 line table pointer (top line 16 + k),
; +2/3 the shifted 24x16 image drawn, +4 x byte, +9 colour (ink 0-7). The four shifted copies are
; separate animation frames, so each 48-byte image is its own pattern set. Image n: 32x32 canvas
; (2x2 tiles of 16x16, 4-bit), graphic at (4,8); store page STP + n/16, offset (n%16)*512.
; Sprite: X = 8 * x byte - 4 + 32, Y = top line - 8 + 32.
; Object i: sprites 20-4i .. 23-4i (BLOB, object 0, on top), patterns in 256-byte slots 2i, 2i+1.

        DEVICE ZXSPECTRUMNEXT

REC     EQU 0xDD18
EN0     EQU 0xA548
EN_N    EQU 144
PL0     EQU 0xE074
PL_N    EQU 52
LTAB    EQU 0xDDDE
SAVEPG  EQU 38                  ; last store page: images 192-195 below 0xE800, attributes at 0xF000
SAVEAT  EQU 0xF000
CACHE   EQU 0xF300                  ; 6 x 2 bytes, page SAVEPG, zero in the build
SPD     EQU 0xF30C                  ; the caller's speed (hlib_speed latch), page SAVEPG: e_ob to e_pl
WIN_OBJ EQU 3                       ; first object of the plot's 28 MHz stretch
STP     EQU 26

        INCLUDE "lib/hlib_speed.asm"

        ORG 0x386E
; ---- after the plot, before the (store-less) attribute paint ----
e_pl:   push af
        push bc
        push de
        push hl
        ld bc,0x243B            ; at 28 MHz already, since e_ob
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        push af                 ; MMU7 as found
        push ix
        ld ix,REC
        xor a
.obj:   push af
        call one
        ld de,32
        add ix,de
        pop af
        inc a
        cp 6
        jr nz,.obj
        pop ix
        nextreg 0x57,SAVEPG     ; the attributes before the paint, put back by e_un
        ld hl,0x5800
        ld de,SAVEAT
        ld bc,768
        ldir
        ld a,(SPD)
        ld h,a                  ; the caller's speed, from e_ob; HL comes back below
        pop af
        nextreg 0x57,a
        ld a,h
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        jp 0xD8B1

; A = object i, IX = record
one:    ld b,a
        nextreg 0x57,SAVEPG
        ld l,(ix+2)
        ld h,(ix+3)             ; HL = the shifted image the plot drew
        ld a,b
        add a,a
        ld e,a
        ld d,high CACHE         ; DE = this object's cache entry: the image its patterns hold
        ld a,(de)
        cp l
        jr nz,.new
        inc e
        ld a,(de)
        cp h
        jr z,.place             ; same image as last time: patterns already uploaded
        dec e
.new:   ld a,l
        ld (de),a
        inc e
        ld a,h
        ld (de),a
        push bc
        call imgidx
        pop bc
        jp c,hide
        ld e,a
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,STP
        nextreg 0x57,a
        ld a,e
        and 15
        add a,a
        add a,0xE0
        ld h,a
        ld l,0
        push bc
        ld a,b
        add a,a
        ld bc,0x303B
        out (c),a
        ld bc,0x005B
        otir
        otir
        pop bc
.place: ld a,(ix+9)
        and 7
        swapnib
        ld c,a                  ; C = palette offset (colour) << 4
        ld l,(ix+0)
        ld h,(ix+1)
        ld de,-LTAB
        add hl,de
        srl h
        rr l                    ; L = line table index k: top line 16 + k
        ld a,l
        add a,40                ; Y = 16 + k - 8 + 32
        ld e,a
        ld a,0
        adc a,0
        ld d,a                  ; DE = Y (9 bits)
        ld l,(ix+4)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,l
        add a,28                ; X = 8 * x byte - 4 + 32
        ld l,a
        ld a,h
        adc a,0
        ld h,a                  ; HL = X (9 bits)
        ld a,5
        sub b
        add a,a
        add a,a
        push af                 ; sprite number of tile 0
        ld a,b
        add a,a
        or 0xC0
        ld b,a                  ; B = a3 of the top tiles (visible, 5 bytes, slot 2i)
        pop af
        ; tile 0: X, Y, top slot, first half
        nextreg 0x34,a
        push af
        ld a,l
        nextreg 0x35,a
        ld a,e
        nextreg 0x36,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,b
        nextreg 0x38,a
        ld a,d
        or 0x80
        nextreg 0x39,a
        pop af
        inc a
        ; tile 1: X+16, Y, top slot, second half
        nextreg 0x34,a
        push af
        ld a,l
        add a,16
        nextreg 0x35,a
        ld a,h
        adc a,0
        and 1
        or c
        nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
        ld a,b
        nextreg 0x38,a
        ld a,d
        or 0xC0
        nextreg 0x39,a
        pop af
        inc a
        inc b                   ; bottom tiles: slot 2i+1
        ; tile 2: X, Y+16
        nextreg 0x34,a
        push af
        ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,e
        add a,16
        nextreg 0x36,a
        ld a,d
        adc a,0
        and 1
        or 0x80
        nextreg 0x39,a
        ld a,b
        nextreg 0x38,a
        pop af
        inc a
        ; tile 3: X+16, Y+16
        nextreg 0x34,a
        ld a,l
        add a,16
        nextreg 0x35,a
        ld a,h
        adc a,0
        and 1
        or c
        nextreg 0x37,a
        ld a,e
        add a,16
        nextreg 0x36,a
        ld a,d
        adc a,0
        and 1
        or 0xC0
        nextreg 0x39,a
        ld a,b
        nextreg 0x38,a
        ret

; B = object i: its four sprites invisible
hide:   ld a,b
        add a,a
        ld l,a
        ld h,high CACHE
        ld (hl),0
        inc l
        ld (hl),0               ; no image held: the next known image uploads
        ld a,5
        sub b
        add a,a
        add a,a
        ld b,4
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        ret

; HL = image base -> A = image index, carry clear; carry set: not a figure image (blank or unknown)
imgidx: push hl
        ld de,EN0
        or a
        sbc hl,de
        jr c,.r2
        ld d,0
        ld b,EN_N
        call div48
        jr nc,.ok
.r2:    pop hl
        push hl
        ld de,PL0
        or a
        sbc hl,de
        jr c,.no
        ld d,EN_N
        ld b,PL_N
        call div48
        jr nc,.ok
.no:    pop hl
        scf
        ret
.ok:    pop hl
        ret

; HL = offset into a region, D = its first index, B = images in it -> A = index (NC) or C
div48:  ld a,h
        cp 3
        jr c,.sm                ; under 768 = 16 images
        ld a,b
        sub 16
        jr c,.bad
        jr z,.bad
        ld b,a
        dec h
        dec h
        dec h
        ld a,d
        add a,16
        ld d,a
        jr div48
.sm:    ld a,h
        or l
        jr z,.ex
        dec b
        jr z,.bad
        ld a,l
        sub 48
        ld l,a
        ld a,h
        sbc a,0
        ld h,a
        jr c,.bad
        inc d
        jr .sm
.ex:    ld a,d
        or a
        ret
.bad:   scf
        ret

; ---- 0xD964, after the paint loop: the attributes as they were before it, then the room's list ----
e_un:   push af
        push bc
        push de
        push hl
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        dec b
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x57,SAVEPG
        ld hl,SAVEAT
        ld de,0x5800
        ld bc,768
        ldir
        pop af
        nextreg 0x57,a
        pop af
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0x5B20
        jp 0xD967

; ---- the plot's next object (JP NZ,0xDF72 replayed: Z = all six drawn; A = the next object) ----
e_ob:   jp z,0xE070
        push af
        cp WIN_OBJ
        jr z,.win
        pop af
        jp 0xDF72
.win:   push bc
        ld bc,0x243B            ; MMU7 as found, the latch's page in, the speed latched, 28 MHz, MMU7 back
        ld a,0x57
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x57,SAVEPG
        HLIB_SPEED_IN SPD
        pop af
        nextreg 0x57,a
        pop bc
        pop af
        jp 0xDF72

; ---- screen clears: every figure sprite hidden, then the original routine ----
e_cls:  call hideall
        jp 0x5FD0
e_rc:   call hideall
        jp 0xA647

hideall: push af
        push bc
        ld a,0
        ld b,24
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        pop bc
        pop af
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): palette, transparency, all sprites hidden, sprites on ---
; sprite palette 0, block c (0-7) = colour c: 0 transparent, 1 ink (bright c), 2 black fill,
; 3 outline (white; black for a white figure), 4-15 fixed colours for the colour map (PALX).
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,PALTAB
        ld b,128
.p:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
BRIGHT  EQU 0
PALTAB:
        DEFB 0x00,0x00,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0x03,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0xE0,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0xE7,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0x1C,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0x1F,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0xFC,0x00,0xFF, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
        DEFB 0x00,0xFF,0x00,0x00, 0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6, 0x03,0xE0,0xE7,0x1C,0x1F
setup_end:

        SAVEBIN "sq_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sq_setup.bin",0xD000,setup_end-0xD000

; ---------------------------------------------------------------------------------------------------
; Loading screen hold (the approved .nxc's build starquake_sprites_loading.nex; imported 2026-11-04 from
; the pilot's loading/work/stub.asm, unchanged but for the picture: the build puts bank 5's own screen at
; loading.picture, starquake.loading_nex). The .nex's bank 5 screen area holds the tape's loading screen;
; this is bank 22, the entry bank, PC $C000: it shows the picture until a key or 5 s, waits for the key
; to go, puts bank 5's screen back and falls through to $C000, page 20 (the converter's own stub).
; Assembled after the hook SAVEBINs: it reuses device memory 0xC000-0xFFFF.
        MODULE loading
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 45; below it the stub's call stack
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

        ds      $C200-$
picture:
        ds      6912            ; bank 5's own screen, put in by the build (the file has the loading screen there)
        assert  $ <= $DF00      ; $DFxx: the loader's stack
        ds      $FFD0-$         ; REGS is written at run time; zero in the file
        disp    $-$4000
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
        SAVEBIN "sq_loading.bin",0xC000,0x0200          ; code before loading.picture
        SAVEBIN "sq_loadend.bin",0xFFD0,0x0030          ; loading.final (the rest of the bank is zero)
