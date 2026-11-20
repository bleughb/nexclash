; 3D Stock Car Championship (Firebird, 1988, 48K) - the four cars as hardware sprites laid over the
; game's own cars. The game reads the screen to find collisions (a car's image ANDed with the screen,
; 0xC750), so every pixel it draws stays; only the colouring of the cells under a car is removed, and
; a sprite in the car's colour covers the car's ink pixels. Stateless hooks in alt ROM image 1.
;
; Patch sites (original bytes checked by stock_car_3d.py):
;   0xC90D  3D C2 FD   DEC A / JP NZ,0xC8FD (0xC55A, draw all cars: the end of its last loop,
;                      which commits each car's move unless a collision refused it)  -> JP e_done
;   0xF9D0  26 5B 06   LD H,0x5B / LD B,.. (clear the screen; 0xF9CE falls into it)  -> JP e_cls
;   0xD27B  16 D6 D9   LD D,0xD6 / EXX (draw the track, at the start of a race)        -> JP e_track
; Screen-write patches (no hook): 0xC8AE, 0xC8B7, 0xC8BF, 0xC8CF, 0xC8D8, 0xC8E0  70 -> 00
;   (LD (HL),B: the car's colour into a cell).
; Car records: 0xD900 + 0x100 * n, n = 0..3; count at 0xF994. The car as DRAWN is at its accepted place:
; x = (IX+0x08), y = (IX+0x05), the top left pixel of its 16 x 8 image, and its image follows from its
; accepted heading (IX+0x0B), (IX+0x0A) by the game's own rule (0xC35D). The proposed values (IX+0x46),
; (IX+0x43), (IX+0x5F) are where it would go: after a collision the game draws it where it was, so a
; sprite set from those sat a pixel or two off the car in one draw in nine. (IX+0x5F) = 28 hides a car.
; Ink = (IX+0x3F).
; Sprites 0-3 = cars 0-3. A car's livery is picked by its ink (cyan, green, yellow, white = 0..3):
; pattern = 28 * livery + image (4 bits a pixel, 16 x 16, the game's 16 x 8 image in rows 4-11, so
; the sprite goes 4 lines above the image), palette offset = livery.
; Layer 2 (320 x 256, banks 16-20) is the backdrop: each circuit's own picture, unpacked when its track
; is drawn, on for the race, off at every screen clear; a circuit with no picture has none. Only black
; PAPER is see-through (ULA palette 16 and 24 = the transparent colour); black ink stays solid. The
; game's own stands, trees and flags outside the track are covered: the picture's pixels over their
; cells use palette entries with the priority bit, which draw over the ULA. Screen memory is untouched.

        DEVICE ZXSPECTRUMNEXT

CARS    EQU 0xD900
NCARS   EQU 0xF994
IMAGES  EQU 28
L2BANK  EQU 16
INDEX   EQU 42                  ; bank 21, first page: the index of backdrops

        ORG 0x386E
; ---- 0xC90D: the end of "draw all cars": every car is on the screen and its move settled. ----
; Interrupts are on; SP is the game's stack.
e_done: dec a
        jp nz,0xC8FD
        push af
        push bc
        push de
        push hl
        ld a,(NCARS)
        ld c,a                  ; C = cars in this race
        ld h,high CARS
        ld b,0                  ; B = car = sprite
.car:   ld a,b
        nextreg 0x34,a
        cp c
        jr nc,.hide
        ld l,0x5F
        ld a,(hl)
        cp IMAGES
        jr nc,.hide             ; the game's blank image: not shown
        ld l,0x0A
        ld e,(hl)
        inc l
        ld a,(hl)               ; A = heading, E = its fraction: the image, as 0xC35D works it out
        or a
        jr z,.round
        inc a
        cp 0x0C
        jr c,.image
        jr z,.round
        inc a
        cp 0x0E
        jr z,.round
        inc a
        cp 0x1A
        jr c,.image
.round: rl e
        adc a,0
.image:
        ld e,a                  ; E = image
        ld l,0x08
        ld a,(hl)
        add a,32
        nextreg 0x35,a          ; x, low 8 bits
        ld d,0
        rl d                    ; D = x bit 8
        ld l,0x05
        ld a,(hl)
        add a,28
        nextreg 0x36,a          ; y: the image is 4 rows down in its pattern
        ld l,0x3F
        ld a,(hl)
        and 7
        push hl
        ld hl,livery
        add hl,a
        ld a,(hl)               ; A = livery 0..3
        pop hl
        push af
        swapnib
        or d
        nextreg 0x37,a          ; palette offset = livery, x bit 8
        pop af
        push hl
        ld hl,first
        add hl,a
        ld a,(hl)
        pop hl
        add a,e
        ld e,a                  ; E = pattern = 28 * livery + image
        srl a
        or 0xC0
        nextreg 0x38,a          ; visible, attribute 4 used, pattern (upper bits)
        ld a,e
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a          ; 4-bit pattern, its lowest bit
        jr .next
.hide:  nextreg 0x38,0
.next:  inc h
        inc b
        ld a,b
        cp 4
        jr nz,.car
        ld a,(engines)
        or a
        call nz,sound
        pop hl
        pop de
        pop bc
        pop af
        ret                     ; the routine's own RET (0xC911)

; ---- An engine note for every car, on the Next's sound chips (the game itself only clicks the beeper,
; for car 1). Reads the cars' records, writes nothing the game can see. Cars 0-2 are channels A-C of
; chip 1, car 3 is channel A of chip 2; channel B of chip 2 is noise for a crash or a skid.
engines: db 1                   ; 0 = this option off (the build sets it)
sound:  ld bc,0x243B              ; the second chip on: the loader turns it off again after setup
        ld a,0x08
        out (c),a
        inc b
        in a,(c)
        or 0x02
        nextreg 0x08,a
        ld a,0xFF
        call chip
        ld a,7
        ld e,0x38               ; chip 1: three tones, no noise
        call ay
        ld h,high CARS
        ld d,0
.three: call note
        inc h
        inc d
        ld a,d
        cp 3
        jr nz,.three
        ld a,0xFE
        call chip
        ld a,7
        ld e,0x2E               ; chip 2: tone on A, noise on B
        call ay
        ld a,6
        ld e,0x0C
        call ay
        ld d,0
        call note
        ld h,high CARS          ; the loudest thing that is happening to any car in this race
        ld a,(NCARS)
        and 7
        ld e,0
        jr z,.none
        ld b,a
.bang:  ld l,0x10
        ld a,(hl)
        bit 6,a
        jr z,.skid
        ld e,15                 ; a crash
.skid:  rla
        jr nc,.nx
        ld l,0x01
        ld a,(hl)
        cp 0x30
        jr c,.nx
        ld a,e
        or a
        jr nz,.nx
        ld e,9                  ; tyres
.nx:    inc h
        djnz .bang
.none:  ld a,9
        jp ay                   ; chip 2, channel B: its volume

; H = the car's record, D = its channel on the chip selected: the note for its speed.
note:   ld a,h
        sub high CARS
        ld e,a
        ld a,(NCARS)
        dec a
        cp e
        ld e,0
        jr c,.vol               ; not in this race: silent
        ld l,0x01
        ld a,(hl)               ; its speed
        push af
        srl a
        srl a
        add a,a
        push hl
        ld hl,pitch
        add hl,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = tone period for that speed
        ld a,d
        add a,a
        add a,a
        add hl,a                ; each car a little apart, so four engines do not sound as one
        ex de,hl                ; E = low, D = high; H = channel
        ld a,h
        add a,a
        call ay
        ld e,d
        inc a
        call ay
        ld d,h
        pop hl
        pop af
        rlca
        rlca
        and 3
        add a,9                 ; louder as it goes faster: 9 to 12
        ld e,a
.vol:   ld a,d
        add a,8
; A = register, E = value, on the chip selected. Keeps A, D, E, H, L.
ay:     push bc
        ld bc,0xFFFD
        out (c),a
        ld b,0xBF
        out (c),e
        pop bc
        ret
; A = 0xFF chip 1, 0xFE chip 2 (both speakers).
chip:   push bc
        ld bc,0xFFFD
        out (c),a
        pop bc
        ret
quiet:  ld a,0xFF
        call .one
        ld a,0xFE
.one:   call chip
        ld e,0
        ld a,8
        call ay
        inc a
        call ay
        inc a
        jp ay
; Tone periods for speeds 0, 4, 8 ... 252: 110837 / (60 + 5.4 n) for n = 0..63, 60 Hz ticking over to 400 Hz flat out.
pitch:
        dw 1847,1695,1565,1455,1358,1274,1200,1133
        dw 1074,1021,972,928,888,851,817,786
        dw 757,730,705,682,660,639,620,602
        dw 585,568,553,539,525,512,499,487
        dw 476,465,455,445,436,427,418,410
        dw 402,394,386,379,372,366,359,353
        dw 347,341,336,330,325,320,315,310
        dw 306,301,297,293,289,285,281,277
livery: db 0,0,0,0,1,0,2,3      ; by ink: green 4, cyan 5, yellow 6, white 7
first:  db 0,IMAGES,2*IMAGES,3*IMAGES

; ---- 0xF9D0: clear the screen (A = attribute). No cars are on it afterwards. ----
; The game clears it here before drawing a track (called from 0xBEDE, so it returns to 0xBEE1), and from
; 0xF9CE for its text screens: the menu, the instructions, the final positions. A text screen gets the
; menu's picture behind it, in a build that has the pictures (the track hook is in place at 0xD27B).
; Every register is handed on as the game's own two instructions would leave it.
e_cls:  push af
        push bc
        push de
        push hl
        call quiet              ; no engines on a menu or a results screen
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 4
        jr nz,.h
        ld a,(0xD27B)
        cp 0xC3
        jr nz,.off              ; a build without pictures
        ld hl,8
        add hl,sp               ; the return address, above the four saved pairs
        ld a,(hl)
        cp 0xE1
        jr nz,.text
        inc hl
        ld a,(hl)
        cp 0xBE
        jr nz,.text
.off:   nextreg 0x69,0          ; a track is about to be drawn: Layer 2 off until its picture is ready
        jr .go
.text:  ld de,MENU
        call show
.go:    pop hl
        pop de
        pop bc
        pop af
        ld h,0x5B
        ld b,0x18
        jp 0xF9D4

; ---- 0xD27B: draw the track. A race is on the screen from here until the next clear. ----
e_track:
        push af
        push bc
        push de
        push hl
        ld de,(0xD4B9)          ; DE = this circuit's track data
        call show
        pop hl
        pop de
        pop bc
        pop af
        ld d,0xD6
        exx
        jp 0xD27E

; Show the picture listed under DE, if there is one: unpack it into Layer 2 and turn Layer 2 on.
; Bank 21's first page holds the index: 35 bytes a picture, its key (a circuit's track data address as at
; 0xD4B9, or MENU) then eleven places, each a page and an address in 0xA000-0xBFFF: the palette (512
; bytes), then ten ZX0 streams, one for each 8K of Layer 2. The last two bytes of the index's 1K hold the
; key of the picture Layer 2 holds now, so the same one is not unpacked twice.
; Keeps IX, IY and whether interrupts were on; the game's memory in slots 4 to 7 is put back.
MENU    equ 1
HELD    equ 0x83FE
show:   push ix
        push iy
        ld a,i
        jp pe,.iff              ; on
        ld a,i                  ; off, or an interrupt taken at the end of the first read (card patch.iff-safe-read)
.iff:   push af                 ; P/V = interrupts were on
        ld ix,0
        add ix,sp               ; IX = the game's stack
        di
        ld sp,0x5C00            ; a stack of our own while the game's is paged out (the printer buffer)
        ld bc,0x243B
        ld a,0x07
        out (c),a
        inc b
        in a,(c)
        and 3
        push af                 ; the speed the game runs at
        nextreg 0x07,3          ; 28 MHz for the unpacking
        nextreg 0x54,INDEX
        ld hl,(HELD)
        or a
        sbc hl,de
        jr z,.on                ; Layer 2 already holds it
        nextreg 0x69,0
        ld iy,0x8000
.find:  ld a,(iy+0)
        and (iy+1)
        inc a
        jr z,.none              ; 0xFFFF ends the index: no picture for this
        ld a,(iy+0)
        cp e
        jr nz,.no
        ld a,(iy+1)
        cp d
        jr z,.found
.no:    ld bc,35
        add iy,bc
        jr .find
.found: ld (HELD),de
        inc iy
        inc iy
        call source             ; the palette: 256 colours, two bytes each
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld b,0
.pa:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .pa
.pb:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .pb
        ld a,2*L2BANK           ; the ten pages of Layer 2
.page:  push af
        nextreg 0x57,a
        call source
        ld de,0xE000
        call dzx0
        pop af
        inc a
        cp 2*L2BANK+10
        jr nz,.page
.on:    nextreg 0x69,0x80       ; Layer 2 on
.none:  nextreg 0x54,4          ; the game's memory back
        nextreg 0x55,5
        nextreg 0x56,0
        nextreg 0x57,1
        pop af
        nextreg 0x07,a
        ld sp,ix
        pop af
        jp po,.was
        ei
.was:   pop iy
        pop ix
        ret

; IY -> page, address: that page and the next at 0xA000 and 0xC000, HL = the address, IY past them.
source: ld a,(iy+0)
        nextreg 0x55,a
        inc a
        nextreg 0x56,a
        ld l,(iy+1)
        ld h,(iy+2)
        inc iy
        inc iy
        inc iy
        ret

; ZX0 "standard" decoder, v2 format, by Einar Saukas and Urusergi (BSD-3-Clause,
; https://github.com/einar-saukas/ZX0). HL = packed data, DE = where to unpack it.
dzx0:   ld bc,0xFFFF
        push bc
        inc bc
        ld a,0x80
.lit:   call .elias
        ldir
        add a,a
        jr c,.new
        call .elias
.copy:  ex (sp),hl
        push hl
        add hl,de
        ldir
        pop hl
        ex (sp),hl
        add a,a
        jr nc,.lit
.new:   pop bc
        ld c,0xFE
        call .loop
        inc c
        ret z
        ld b,c
        ld c,(hl)
        inc hl
        rr b
        rr c
        push bc
        ld bc,1
        call nc,.back
        inc bc
        jr .copy
.elias: inc c
.loop:  add a,a
        jr nz,.skip
        ld a,(hl)
        inc hl
        rla
.skip:  ret c
.back:  add a,a
        rl c
        rl b
        jr .loop
rom_end:

; --- setup routine (stub bank, 0xD000). Bank 11 holds the patterns (112 x 128 bytes), then at
;     0x3800 the sprite palette (64 colours, 2 bytes each).
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11, lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0xE000
        ld d,32                     ; the first 8K of patterns
        call upload
        nextreg 0x57,23             ; bank 11, upper page
        ld hl,0xE000
        ld d,24                     ; the other 6K
        call upload
        nextreg 0x43,0x20           ; sprite palette 0
        nextreg 0x40,0
        ld hl,0xF800
        ld b,128
.sp:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .sp
        nextreg 0x43,0x00           ; ULA palette 0: black paper, plain and bright, is the see-through colour
        nextreg 0x40,16
        nextreg 0x41,0xE3
        nextreg 0x40,24
        nextreg 0x41,0xE3
        nextreg 0x57,21
        nextreg 0x14,0xE3           ; the see-through colour
        nextreg 0x4A,0              ; and what shows where nothing is drawn: black
        nextreg 0x4B,0              ; sprite transparency index 0
        nextreg 0x12,L2BANK
        nextreg 0x70,0x10           ; Layer 2 320 x 256, 256 colours
        nextreg 0x1C,1              ; its clip window: all of it
        nextreg 0x18,0
        nextreg 0x18,159
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x16,0              ; no scroll
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x69,0              ; Layer 2 off until a race
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x09           ; sprites on; sprites over the ULA over Layer 2
        ld bc,0x243B                ; the sound chips in both speakers (the engine hook does the rest)
        ld a,0x09
        out (c),a
        inc b
        in a,(c)
        or 0xE0
        nextreg 0x09,a
        nextreg 0x57,23             ; the game starts on its menu, with no clear: its picture is already in
        ld a,(0xF880)               ; Layer 2 if the build has one (flag), and its palette is at 0x3900
        or a
        jr z,.done
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,0xF900
        ld b,0
.m1:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .m1
.m2:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .m2
        nextreg 0x69,0x80
.done:  nextreg 0x57,21
        ret
upload: ld bc,0x005B
        otir
        dec d
        jr nz,upload
        ret
setup_end:

        SAVEBIN "sc_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sc_setup.bin",0xD000,setup_end-0xD000
