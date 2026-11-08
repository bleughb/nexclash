; Lunar Jetman (Ultimate, 1983, 48K) - every object the two XOR plotters draw becomes hardware
; sprites; the plotters' screen stores and the object colour painters are NOPs (lunar_jetman.py).
; Hooks in alt ROM image 1 at 0x386E (read-only). Interrupts stay on: the ROM IM 1 handler uses
; slots 0 and 2 only, so slot 4 may hold a Next page while a hook runs (restored to page 4 before
; any return). Hooks never touch IX, IY, I, IFF or the alternate registers (the plotter keeps the
; old image in them).
;
; Sites (original bytes checked by lunar_jetman.py):
;   34558  0E 00 C9  LD C,0 / RET  end of the figure plotter's new-image setup     -> JP h_new
;   34431  AF DD 77 09  XOR A / LD (IX+9),A  object outside the window: state clear  -> JP h_clr
;                    (every update for every such object: only an object with something drawn, IX+10 > 0,
;                    can have sprites showing; the rest pass at 3.5 MHz in 43 T more than the original)
;   34368  AF 32 59 5E  XOR A / LD (24153),A  erase-only entry                       -> JP h_eo
;   34383  AF 32 59 5E  XOR A / LD (24153),A  truck erase-only entry                 -> JP h_teo
;   34958  0E 00 C9  LD C,0 / RET  end of the truck plotter's setup                -> JP h_tnew
;   35749  21 BF 57  LD HL,22463 (entry of the play-area clear 35749: the missile warning,
;                    new screens; callers 41670, 45992, 46424, 46476)               -> JP h_msg
;   34011  CD AD 84  CALL 33965 (pixel clear of the whole screen, routine 34008)     -> CALL h_cls
; Sprites / patterns: trucks 0x6090 -> 0-9, 0x6180 -> 10-19 (5 x 2 tiles); object n (IX =
; 0x6078 + 24n, n 0-26) -> 20 + 4n .. 23 + 4n (2 x 2 tiles). Truck lowest, so figures go in front.

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 0x6078
NOBJ    EQU 27
STATE   EQU 26
IDXP    EQU 27
TP0     EQU 28
FP0     EQU 36
SCROLL  EQU 24698
GLOOK   EQU 34175               ; the game's own graphic lookup (IX+0 -> DE), reads only
FLIST   EQU 0x8040
TLIST   EQU 0x8400

        ORG 0x386E
; ---- figure: new image set up (IX+9..15 = what is drawn) ----
h_new:  push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed (NR 7 bits 1:0, card patch.restore-speed), kept on the
        ld a,7                  ; stack: these hooks live in the alt ROM (no RAM for a latch)
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        push de                 ; DE / HL saved at 28 MHz
        push hl
        call objn               ; A = n, carry = not an object
        jp c,.out
        ld c,a                  ; C = n
        add a,a
        add a,a
        add a,20
        ld b,a                  ; B = first sprite
        ld a,(ix+10)
        or a
        jr z,.hid
        dec de                  ; DE = graphic (height byte)
        call ffind              ; A = id, carry = none; slot 4 = state page
        jr c,.unm
        ld e,a                  ; E = id
        ld h,0x80
        ld l,c                  ; HL = cache[n]
        inc a
        cp (hl)
        jr z,.cached
        ld (hl),a
        ld a,b
        call patsel
        ld a,e
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,FP0
        nextreg 0x54,a
        ld a,e
        and 15
        add a,a
        add a,0x80
        ld h,a
        ld l,0                  ; HL = 0x8000 + (id & 15) * 512
        ld bc,0x005B
        call up256              ; 512 bytes
        call up256
.cached:
        nextreg 0x54,4
        call objn
        add a,a
        add a,a
        add a,20
        ld b,a
        ; y = (IX+4) - (IX+10) + 32, x = (IX+1) + 31
        ld a,(ix+4)
        sub (ix+10)
        add a,32
        ld e,a                  ; E = Y
        ld a,(ix+7)
        call paloff             ; A = palette offset << 4
        ld c,a
        ld l,(ix+1)
        ld h,0
        ld a,l
        add a,31
        ld l,a
        jr nc,.n9
        inc h
.n9:    ; HL = X, B = sprite, C = palette, E = Y; four tiles
        ld d,b                  ; D = pattern (= sprite)
        call place
        push hl
        call add16
        call place
        pop hl
        ld a,e
        add a,16
        ld e,a
        call place
        call add16
        call place
        jr .out
.unm:   nextreg 0x54,4
.hid:   ld a,b
        ld b,4
        call hide
.out:   pop hl
        pop de
        pop af
        nextreg 0x07,a          ; the caller's speed back (never a fixed 3.5 MHz)
        pop bc
        pop af
        ld c,0
        ret

; ---- figure outside the window (the state clear 34431) / erase only: hide its sprites ----
h_clr:  ld a,(ix+10)            ; the drawn image's height: 0 = nothing drawn, its sprites already hidden
        or a                    ; (h_new hides them whenever it sees IX+10 = 0)
        call nz,hidefig
        xor a                   ; the original's XOR A / LD (IX+9),A (its flags)
        ld (ix+9),a
        jp 34435
h_eo:   call hidefig
        xor a
        ld (24153),a
        jp 34372
h_teo:  call hidetruck
        xor a
        ld (24153),a
        jp 34387

hidefig:
        push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed, kept on the stack, then 28 MHz (as h_new)
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        call objn
        jr c,.x
        add a,a
        add a,a
        add a,20
        ld b,4
        call hide
.x:     pop af
        nextreg 0x07,a          ; the caller's speed back
        pop bc
        pop af
        ret

hidetruck:
        push af
        push bc
        call trk
        jr c,.x
        ld b,10
        call hide
.x:     pop bc
        pop af
        ret

; ---- truck: new image set up ----
h_tnew: push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed (NR 7 bits 1:0, card patch.restore-speed), kept on the
        ld a,7                  ; stack: these hooks live in the alt ROM (no RAM for a latch)
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        push de                 ; DE / HL saved at 28 MHz
        push hl
        call trk                ; A = first sprite (0 / 10), carry = not a truck
        jp c,.out
        ld b,a
        ld a,(ix+10)
        or a
        jp z,.hid
        push bc
        call GLOOK              ; DE = graphic [W, H, data]
        pop bc
        nextreg 0x54,STATE
        ld hl,TLIST
        call find
        jp c,.unm
        ld e,a                  ; E = id
        ld a,b
        or a
        ld hl,0x8020
        jr z,.c0
        inc hl
.c0:    ld a,e
        inc a
        cp (hl)
        jr z,.cached
        ld (hl),a
        ld a,b
        call patsel
        ; page TP0 + id / 6, offset (id % 6) * 1280
        ld a,e
        ld d,TP0
.dv:    cp 6
        jr c,.dd
        sub 6
        inc d
        jr .dv
.dd:    push af
        ld a,d
        nextreg 0x54,a
        pop af
        ld d,a
        add a,a
        add a,a
        add a,d                 ; 5 * (id % 6)
        add a,0x80
        ld h,a
        ld l,0                  ; 0x8000 + (id % 6) * 1280
        ld a,b
        ld bc,0x005B
        call up256              ; 1280 bytes
        call up256
        call up256
        call up256
        call up256
        ld b,a
.cached:
        nextreg 0x54,4
        push bc
        call GLOOK
        pop bc
        ; x: (IX+1) & 0xF8, or -8 * (W - (IX+11)) when cut on the left ((IX+1) = 0)
        ld a,(de)               ; W
        sub (ix+11)
        ld c,a                  ; C = columns cut
        ld a,(ix+1)
        or a
        jr nz,.right
        ld a,c
        or a
        jr z,.right
        ld a,c
        add a,a
        add a,a
        add a,a
        neg
        ld l,a
        ld h,0xFF               ; HL = -8k
        jr .xx
.right: ld a,(ix+1)
        and 0xF8
        ld l,a
        ld h,0
.xx:    ld a,l
        add a,31
        ld l,a
        ld a,h
        adc a,0
        ld h,a                  ; HL = X (signed)
        inc de
        ld a,(de)               ; H
        ld c,a
        ld a,(ix+4)
        sub c
        add a,32
        ld e,a                  ; E = Y
        ld c,0                  ; palette 0
        ld d,b                  ; D = pattern
        push hl
        call row5
        pop hl
        ld a,e
        add a,16
        ld e,a
        call row5
        jr .out
.unm:   nextreg 0x54,4
.hid:   ld a,b
        ld b,10
        call hide
.out:   pop hl
        pop de
        pop af
        nextreg 0x07,a          ; the caller's speed back (never a fixed 3.5 MHz)
        pop bc
        pop af
        ld c,0
        ret

row5:   ld a,5
.r:     push af
        call place
        call add16
        pop af
        dec a
        jr nz,.r
        ret

; ---- the play-area clear (missile warning, new screens): every sprite off (objects are reset after it) ----
h_msg:  call allhide
        ld hl,22463
        jp 35752

; ---- whole-screen clear (new game, new life): every sprite off, caches empty ----
h_cls:  call allhide
        jp 33965

allhide:
        push af
        push hl
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x54,STATE
        ld hl,0x8000
.c:     ld (hl),0
        inc l
        ld a,l
        cp 0x22
        jr nz,.c
        nextreg 0x54,4
        pop hl
        pop af
        ret

; ---- helpers ----
; objn: A = (IX - OBJ0) / 24, carry if IX is not an object record start (no loop: was up to 27 x 42 T)
objn:   push hl
        push de
        push ix
        pop hl
        ld de,OBJ0
        or a
        sbc hl,de
        jr c,.no
        ld a,l
        and 7
        jr nz,.no               ; not a multiple of 8
        ld a,h
        cp 3
        jr nc,.no               ; 768 or more (27 records = 648 bytes)
        ld a,l
        srl h
        rra
        srl h
        rra
        srl h
        rra                     ; A = (IX - OBJ0) / 8 (< 96)
        ld l,a
        ld e,a
        ld d,86
        mul d,e                 ; D = A * 86 / 256 = A / 3 (exact for A < 96 when A is a multiple of 3)
        ld a,d
        add a,a
        add a,d
        cp l
        jr nz,.no               ; not a multiple of 24
        ld a,d
        cp NOBJ
        ccf
        jr .x
.no:    scf
.x:     pop de
        pop hl
        ret

; trk: A = first truck sprite (0 for 0x6090, 10 for 0x6180), carry if neither
trk:    ld a,ixh
        cp 0x60
        jr z,.a
        cp 0x61
        jr nz,.no
        ld a,ixl
        cp 0x80
        jr nz,.no
        ld a,10
        or a
        ret
.a:     ld a,ixl
        cp 0x90
        jr nz,.no
        xor a
        ret
.no:    scf
        ret

; ffind: figure graphic DE -> A = id (carry if absent), by the index page (DE & 0x1FFF -> id + 1),
; checked against the state page's list; leaves the state page in slot 4
ffind:  push bc
        push hl
        nextreg 0x54,IDXP
        ld a,d
        and 0x1F
        or 0x80
        ld h,a
        ld l,e
        ld c,(hl)
        nextreg 0x54,STATE
        ld a,c
        sub 1
        jr c,.x
        ld l,a
        ld h,0
        add hl,hl
        ld bc,FLIST
        add hl,bc
        ld c,a
        ld a,(hl)
        cp e
        jr nz,.no
        inc hl
        ld a,(hl)
        cp d
        jr nz,.no
        ld a,c
        or a
        jr .x
.no:    scf
.x:     pop hl
        pop bc
        ret

; find: HL = list of graphic addresses (0-terminated), DE = address -> A = index, carry if absent
find:   push bc
        ld b,0
.l:     ld a,(hl)
        inc hl
        ld c,(hl)
        inc hl
        cp e
        jr nz,.n
        ld a,c
        cp d
        jr z,.f
.n:     dec hl
        dec hl
        ld a,(hl)
        inc hl
        or (hl)
        inc hl
        jr z,.no
        inc b
        jr .l
.f:     ld a,b
        or a
        pop bc
        ret
.no:    scf
        pop bc
        ret

; up256: 256 bytes from HL to port C (B = 0 on entry and exit); 16.6 T a byte against OTIR's 21
up256:  outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        jp nz,up256
        ret

; hide: B sprites from A
hide:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz hide
        ret

; patsel: select 4-bit pattern A for upload
patsel: push bc
        srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        pop bc
        ret

; paloff: attribute A -> (ink + 8 * bright, 0 -> 8) << 4
paloff: push bc
        ld b,a
        and 7
        bit 6,b
        jr z,.d
        or 8
.d:     or a
        jr nz,.z
        ld a,8
.z:     rlca
        rlca
        rlca
        rlca
        pop bc
        ret

add16:  ld a,l
        add a,16
        ld l,a
        ret nc
        inc h
        ret

; place: sprite D (pattern D), X = HL (9 bits), Y = E, palette C; D += 1
place:  ld a,d
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,e
        nextreg 0x36,a
        ld a,h
        and 1
        or c
        nextreg 0x37,a
        ld a,d
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,d
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        inc d
        ret
rom_end:

; --- setup (stub bank, 0xD000): sprite palette, transparency, every sprite hidden, sprites on ---
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
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
pal:    INCLUDE "lunar_jetman_palette.asm"
setup_end:

        SAVEBIN "lj_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "lj_setup.bin",0xD000,setup_end-0xD000

; ---------------------------------------------------------------------------------------------------
; Loading screen hold (the approved .nxc's builds lunar_jetman_sprites_loading / _enhanced_loading;
; imported 2026-11-04 from the pilot's loading/work/stub.asm, unchanged but for the picture: the build
; puts bank 5's own screen at loading.picture, lunar_jetman.loading_nex). The .nex's bank 5 screen area
; holds the tape's loading screen; this is bank 34 (pages 68, 69), the entry bank, PC $C000: it shows
; the picture until a key or 5 s, waits for the key to go, puts bank 5's screen back and falls through
; to $C000, page 20 (the converter's own stub). Assembled after the hook SAVEBINs (device 0xC000-0xFFFF).
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
        SAVEBIN "lj_loading.bin",0xC000,0x0200          ; code before loading.picture
        SAVEBIN "lj_loadend.bin",0xFFD0,0x0030          ; loading.final (the rest of the bank is zero)
