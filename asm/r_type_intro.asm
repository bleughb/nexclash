; =============================================================================
; R-Type intro for the ZX Spectrum Next: the R-9 specification screen, animated
;
; Built by nexclash/r_type_intro.py (the data: the owner's R-9 model rendered at build time, the title, logo
; and text from the player's snapshot), assembled with -DALLDIR -DGAME [-DLOADSCR] in front of the game.
; Without GAME it assembles to the stand-alone demo (specanim2.nex with ALLDIR, else specanim.nex).
;
; What it shows: the spec screen. Five seconds still, then the three ships turn
; once in seven seconds (top in pitch, side in yaw, front in roll), and again.
; The text list scrolls all the time, one line a second.
;
; Joystick (Kempston), or keys O P Q A:
;   ALLDIR build: the screen changes to the side ship alone, in the middle, and
;     the stick turns it every way: left/right round its upright axis, up/down
;     over the top and under. Fire or SPACE: back to the spec screen.
;   Other build: left/right turn the side ship in place. Fire or SPACE: back to automatic.
;
; How it works
;   - The ships are stored pictures, packed, in 8K pages from FIRST_PAGE. They
;     are drawn on the ordinary Spectrum screen (1 bit a pixel, all green): a
;     picture is built in a spare page (BUF_PAGE) and copied to the screen in
;     the bottom border. Bank 7 is NOT used as a second screen: on a real Next
;     it holds the disk system's memory, and the R-Type build reads the disk.
;   - The title, logo and text are on Layer 2, in front of the ships. The title
;     and logo are loaded with the file; the text window is redrawn from a
;     1-bit strip each time the list moves one pixel.
;   - ALLDIR: the side ship is stored for yaw -64..64 and pitch 0..128 in steps
;     of 4 (of 256 to the turn). Every other direction is one of those flipped
;     left-right and/or top-bottom, which is exact because the ship's two sides
;     are the same.
;   - Interrupts stay off. Time is kept by watching the video line number.
; =============================================================================

    opt --zxnext
    device zxspectrumnext

    include "spec_data.inc"
    ifdef GAME
    include "game.inc"
    endif

HOLD        equ 250             ; video frames still (5 s at 50Hz)
PER_STEP    equ 2               ; video frames per picture
TEXT_EVERY  equ 7               ; video frames per pixel of text scroll
LOADER_PAGE equ 222             ; R-Type build: the loader's own 8K page
BUF_PAGE    equ 220             ; where a picture is built before it is copied to the screen
HAND_EVERY  equ 3               ; video frames per step of the hand-turned ship
LOAD_HOLD   equ 150             ; R-Type build: frames the loading screen stays after the page check (4 s with it)
FADE_EVERY  equ 3               ; video frames per step of a fade (7 steps)
L2_PAGE     equ 18              ; Layer 2 = bank 9
YELLOW      equ $FC
CLEAR       equ $E3
ATTR        equ $44             ; bright green on black

    org $8000

start:
    di
    ld sp,stack_top
    nextreg $07,3               ; 28MHz
    ifdef GAME
    ld bc,$243B                 ; the classic paging (ROM, top bank) as the Next's loader left it
    ld a,$8E
    out (c),a
    inc b
    in a,(c)
    ld (entry8e),a
    endif
    ifdef GAME
    ld bc,$243B                 ; both joystick ports to Kempston, keeping 50/60Hz and the scandoubler bit
    ld a,5
    out (c),a
    inc b
    in a,(c)
    and $05
    or $50
    nextreg 5,a
    endif
    nextreg $69,0               ; Layer 2 off while we set up
    nextreg $12,9               ; Layer 2 is bank 9
    nextreg $70,0               ; 256x192, 8 bit
    nextreg $15,0               ; sprites, Layer 2, ULA: Layer 2 in front of the ships
    nextreg $14,CLEAR           ; see-through colour
    nextreg $16,0
    nextreg $17,0
    nextreg $71,0
    nextreg $43,0               ; ULA palette, first; Layer 2 palette first
    xor a
    out ($FE),a                 ; black border

    ifdef GAME
; The Next's loader showed the game's tape loading screen (in the file, SAVENEX SCREEN) as soon as the file
; started loading. Keep it up while the picture pages are checked, LOAD_HOLD frames in all, then fade it out.
    call check_pages            ; about a second
    ld b,LOAD_HOLD
.lhold:
    push bc
    call wait_frame             ; (uses BC)
    pop bc
    djnz .lhold
    call fade_out               ; both palettes black: the spec screen is drawn unseen, then faded in
    endif

    nextreg $52,10              ; the screen: wipe, green
    call wipe_all
    nextreg $52,BUF_PAGE        ; from here on the work page is at $4000
    call wipe

    call draw_text
    call draw_ships             ; first picture, into the hidden screen
    call wait_frame
    call flip
    nextreg $69,%10000000       ; Layer 2 on
    ifdef GAME
    call fade_in
    ld hl,HOLD-1                ; the ships start turning at once
    ld (cycle),hl
    endif

; ---------------------------------------------------------------- main loop
    ifdef GAME
; ---------------------------------------------------------------- main loop, R-Type build
; (owner, 2026-11-22) state 1: the ships turning, from the start.   any key -> game
;                                                                  stick -> 2 (fade), the first time only
;                                                                  stick, after that -> game
;                       state 2: the side ship alone, turned by the stick.   any key -> 1 (fade)
; "Any key" is any keyboard key or the fire button. A stick still held when state 1 starts is ignored
; until it is let go.
main:
    call wait_frame
    ld a,(pending)
    or a
    jr z,.noflip
    call flip
    ld a,(fadein)               ; the first picture after a fade-out is on the screen: fade it in
    or a
    jr z,.noflip
    xor a
    ld (fadein),a
    call fade_in
.noflip:
    call read_input             ; A: bit 0 right, 1 left, 2 down, 3 up (stick), 4 any key or fire
    ld b,a
    and $10
    ld c,a
    ld a,(keyheld)
    cpl
    and c
    ld d,a                      ; D: a key has just gone down
    ld a,c
    ld (keyheld),a
    ld a,(state)
    cp 2
    jr z,.hand
    ld a,d
    or a
    jp nz,go_game               ; state 1: a key or fire loads the game
    ld a,b
    and 15
    ld c,a
    ld a,(stickwait)
    or a
    jr z,.stickok
    ld a,c                      ; ignoring the stick until it is let go
    or a
    jp nz,.run
    xor a
    ld (stickwait),a
    jp .run
.stickok:
    ld a,c
    or a
    jp z,.run
    ld a,(handdone)             ; the hand-turned ship has been seen: the stick loads the game too
    or a
    jp nz,go_game
    push bc
    call fade_out
    pop bc
    ld a,1
    ld (fadein),a
    ld a,(auto)                 ; stick moved: the side ship alone, facing the way it is now
    ld d,a
    ld e,94                     ; picture number * 64 / STEPS
    mul d,e
    ld a,d
    and 63
    ld (gy),a
    ld a,16                     ; side on
    ld (gp),a
    ld a,1
    ld (manual),a
    ld (handclock),a
    ld a,2
    ld (state),a
    nextreg $69,0               ; Layer 2 off: the ship has the whole screen
    jr .run
.hand:
    ld a,d
    or a
    jr z,.move
    call fade_out               ; back to the ships turning, once only
    ld a,1
    ld (state),a
    ld (handdone),a
    ld (stickwait),a
    ld (fadein),a
    xor a
    ld (manual),a
    ld hl,HOLD-1                ; turning again at once
    ld (cycle),hl
    nextreg $69,%10000000
    jr .run
.move:
    ld a,b
    and 15
    jr z,.run
    ld hl,handclock
    dec (hl)
    jr nz,.run
    ld (hl),HAND_EVERY
    ld a,(gy)
    bit 0,b
    jr z,.nr
    inc a
.nr:
    bit 1,b
    jr z,.nl
    dec a
.nl:
    and 63
    ld (gy),a
    ld a,(gp)
    bit 3,b
    jr z,.nu
    inc a
.nu:
    bit 2,b
    jr z,.nd
    dec a
.nd:
    and 63
    ld (gp),a
.run:
    ld hl,0
    ld a,(state)
    dec a
    jr nz,.still                ; only state 1 runs the hold-and-turn cycle
    ld hl,(cycle)
    inc hl
    ld de,HOLD+STEPS*PER_STEP
    or a
    sbc hl,de
    jr z,.wrapped
    add hl,de
.wrapped:
    ld (cycle),hl
    ld de,HOLD
    or a
    sbc hl,de
    jr nc,.turning
    ld hl,0
.turning:
    srl h
    rr l                        ; PER_STEP = 2
    jr .auto
.still:
    ld (cycle),hl
.auto:
    ld (auto),hl
    ld (side),hl
    ld (want),hl
    ld (want+2),hl
    ld (want+4),hl
    ld a,(manual)
    or a
    jr z,.wanted
    ld hl,(gy)                  ; L = yaw, H = pitch
    ld (want),hl
    ld hl,$FFFF
    ld (want+2),hl
    ld (want+4),hl
.wanted:

    else
main:
    call wait_frame
    ld a,(pending)
    or a
    call nz,flip

    ; --- the cycle: HOLD frames still, then STEPS*PER_STEP frames turning
    ld hl,(cycle)
    inc hl
    ld de,HOLD+STEPS*PER_STEP
    or a
    sbc hl,de
    jr z,.wrapped
    add hl,de
.wrapped:
    ld (cycle),hl
    ld de,HOLD
    or a
    sbc hl,de
    jr nc,.turning
    ld hl,0
.turning:
    srl h
    rr l                        ; PER_STEP = 2
    ld (auto),hl

    ; --- controls
    call read_stick             ; A: bit 0 right, 1 left, 2 down, 3 up, 4 fire
    ld b,a
    bit 4,b
    jr z,.nofire
    xor a
    ld (manual),a
    ifdef ALLDIR
    nextreg $69,%10000000       ; the spec screen's title, logo and text again
    endif
.nofire:

    ifdef ALLDIR
; ............ the side ship alone, turned every way
    ld a,b
    and 15
    jr z,.nomove
    ld a,(manual)
    or a
    jr nz,.have
    ld a,(auto)                 ; take over facing the way the ship is now
    ld d,a
    ld e,94                     ; picture number * 64 / STEPS
    mul d,e
    ld a,d
    and 63
    ld (gy),a
    ld a,16                     ; side on
    ld (gp),a
    ld a,1
    ld (manual),a
    ld (handclock),a
    nextreg $69,0               ; Layer 2 off: the ship has the whole screen
.have:
    ld hl,handclock
    dec (hl)
    jr nz,.nomove
    ld (hl),HAND_EVERY
    ld a,(gy)
    bit 0,b
    jr z,.nr
    inc a
.nr:
    bit 1,b
    jr z,.nl
    dec a
.nl:
    and 63
    ld (gy),a
    ld a,(gp)
    bit 3,b
    jr z,.nu
    inc a
.nu:
    bit 2,b
    jr z,.nd
    dec a
.nd:
    and 63
    ld (gp),a
.nomove:
    ld hl,(auto)
    ld (side),hl
    ld (want),hl
    ld (want+2),hl
    ld (want+4),hl
    ld a,(manual)
    or a
    jr z,.wanted
    ld hl,(gy)                  ; L = yaw, H = pitch
    ld (want),hl
    ld hl,$FFFF
    ld (want+2),hl
    ld (want+4),hl
.wanted:

    else
; ............ the side ship turned left/right where it is
    ld a,b
    and 3
    jr z,.nomove
    ld a,(manual)
    or a
    jr nz,.have
    ld hl,(auto)                ; take over from where the ship is now
    ld (side),hl
    ld a,1
    ld (manual),a
.have:
    ld a,(cycle)
    and 1
    jr nz,.nomove               ; one picture every second frame
    ld hl,(side)
    bit 0,b
    jr z,.left
    inc hl
    ld de,STEPS
    or a
    sbc hl,de
    jr z,.set
    add hl,de
    jr .set
.left:
    ld a,h
    or l
    jr nz,.dec
    ld hl,STEPS
.dec:
    dec hl
.set:
    ld (side),hl
.nomove:
    ld hl,(auto)
    ld (want+2),hl
    ld (want+4),hl
    ld a,(manual)
    or a
    jr nz,.keep
    ld (side),hl
.keep:
    ld hl,(side)
    ld (want),hl
    endif

    endif

    ; --- ships: redraw when a picture changes. Text: one pixel up every TEXT_EVERY frames, but never in
    ;     the same frame as a ship redraw - it waits for the next free frame.
    ld hl,textclock
    ld a,(hl)
    or a
    jr z,.due
    dec (hl)
.due:
    ld hl,want
    ld de,drawn
    ld b,6
.cmp:
    ld a,(de)
    cp (hl)
    jr nz,.redraw
    inc hl
    inc de
    djnz .cmp
    ld a,(textclock)
    or a
    jp nz,main
    ld a,TEXT_EVERY
    ld (textclock),a
    ld hl,(scroll)
    inc hl
    ld de,LIST_ROWS
    or a
    sbc hl,de
    jr z,.t0
    add hl,de
.t0:
    ld (scroll),hl
    call draw_text
    jp main
.redraw:
    call draw_ships
    jp main

; ---------------------------------------------------------------- controls
; Returns A: bit 0 right, bit 1 left, bit 2 down, bit 3 up, bit 4 fire.
read_stick:
    in a,($1F)                  ; Kempston
    ld c,a
    and 3
    cp 3                        ; left and right together: no joystick there
    jr nz,.ok
    ld c,0
.ok:
    ld a,c
    and %00011111
    ld c,a
    ld a,$DF                    ; keys P (bit 0) and O (bit 1)
    in a,($FE)
    cpl
    and 3
    or c
    ld c,a
    ld a,$FB                    ; Q: up
    in a,($FE)
    rrca
    jr c,.noq
    set 3,c
.noq:
    ld a,$FD                    ; A: down
    in a,($FE)
    rrca
    jr c,.noa
    set 2,c
.noa:
    ld a,$7F                    ; SPACE: fire
    in a,($FE)
    rrca
    ld a,c
    ret c
    or %00010000
    ret

    ifdef GAME
; Returns A: bit 0 right, 1 left, 2 down, 3 up from the joystick only; bit 4 = any keyboard key, or fire.
read_input:
    in a,($1F)                  ; Kempston
    ld c,a
    and 3
    cp 3                        ; left and right together: no joystick there
    jr nz,.ok
    ld c,0
.ok:
    ld a,c
    and %00011111
    ld c,a
    ld a,(fakestick)            ; (for testing in an emulator: poke a stick value here)
    or c
    ld c,a
    xor a
    in a,($FE)                  ; all the keyboard rows at once
    cpl
    and $1F
    ld a,c
    ret z
    or %00010000
    ret

; Any key from the still or turning screen: wait for the key to come up, blank the screen, and load the game.
go_game:
    call wait_frame
    call read_input
    and $10
    jr nz,go_game
    nextreg $69,0
    nextreg $52,10
    call wipe                   ; black screen while the game loads
    nextreg $56,LOADER_PAGE     ; the loader is kept in its own page; it runs from $A000 (bank 2), which the
    ld hl,$C000                 ; disk system leaves alone
    ld de,loader
    ld bc,loader_end-loader
    ldir
    jp loader
    endif

    ifdef GAME
; Add up every picture page and compare with the totals worked out when the file was made. A page that
; differs did not load properly (not enough memory, or a damaged file): the border goes blue, and the page
; number is left in (badpage). Takes about a second.
check_pages:
    ld hl,page_sums
    ld b,FRAME_PAGES+GRID_PAGES
    ld c,FIRST_PAGE
.page:
    ld a,c
    nextreg $56,a
    push hl
    push bc
    ld hl,$C000
    xor a
    ld b,32
.blk:
    add a,(hl)
    inc l
    add a,(hl)
    inc l
    add a,(hl)
    inc l
    add a,(hl)
    inc l
    jr nz,.blk
    inc h
    djnz .blk
    pop bc
    pop hl
    cp (hl)
    jr z,.ok
    ld a,c
    ld (badpage),a
    ld a,1
    out ($FE),a
.ok:
    inc hl
    inc c
    djnz .page
    ret
page_sums: RT_SUMS

; Fades. Both palettes (Layer 2 first, ULA first) are rewritten from fade_tab: 8 levels, 0 black .. 7 the
; normal colours. Layer 2's see-through colour $E3 keeps its value at every level, so it stays see-through.
fade_out:
    ld a,7
.step:
    dec a
    push af
    call set_level
    call wait_fade
    pop af
    or a
    jr nz,.step
    ret

fade_in:
    xor a
.step:
    inc a
    push af
    call set_level
    call wait_fade
    pop af
    cp 7
    jr nz,.step
    ret

wait_fade:
    ld b,FADE_EVERY
.w:
    push bc
    call wait_frame
    pop bc
    djnz .w
    ret

; A = level 0-7. Uses A, B, DE, HL.
set_level:
    add a,high fade_tab
    ld h,a
    ld l,0
    nextreg $43,%00010000       ; Layer 2 first palette, index going up by itself
    nextreg $40,0
    ld b,0
.l2:
    ld a,(hl)
    nextreg $41,a
    inc l
    djnz .l2
    nextreg $43,0               ; ULA first palette
    nextreg $40,0
    ld de,ula_cols
    ld b,32
.ula:
    ld a,(de)
    ld l,a
    ld a,(hl)
    nextreg $41,a
    inc de
    djnz .ula
    ret

; The Next's standard ULA colours (inks 0-15, then papers 16-31), RRRGGGBB.
ula_cols:
    db $00,$02,$A0,$A2,$14,$16,$B4,$B6, $00,$03,$E0,$E7,$1C,$1F,$FC,$FF
    db $00,$02,$A0,$A2,$14,$16,$B4,$B6, $00,$03,$E0,$E7,$1C,$1F,$FC,$FF
    endif

; ---------------------------------------------------------------- screens
; Wait for the start of the bottom border (video line 192).
wait_frame:
    ld bc,$243B
    ld a,$1F
    out (c),a
    inc b
.leave:
    in a,(c)
    cp 192
    jr z,.leave
.arrive:
    in a,(c)
    cp 192
    jr nz,.arrive
    ret

; Copy the finished picture to the screen. Called at the start of the bottom border, it is done before
; the next picture starts. The screen's page goes in at $6000 just for the copy.
flip:
    xor a
    ld (pending),a
    nextreg $53,10
    ld hl,$4000
    ld de,$6000
    ld bc,6144
    ldir
    nextreg $53,11
    ret

; Wipe the screen at $4000 and make it all green ink.
wipe_all:
    call wipe
    ld hl,$5800
    ld de,$5801
    ld bc,767
    ld (hl),ATTR
    ldir
    ret
wipe:
    ld hl,$4000
    ld de,$4001
    ld bc,6143
    ld (hl),l
    ldir
    ret

; Draw the wanted pictures into the work page; it is copied to the screen at the next frame.
draw_ships:
    call wipe
    ld hl,want
    ld de,drawn
    ld bc,6
    ldir
    xor a
    ld (vflip),a
    ld (hflip),a
    ifdef ALLDIR
    ld a,(drawn+3)
    inc a
    jr z,hand_ship              ; $FFFF there: the hand-turned ship alone
    endif
    ld hl,(drawn)
    call picture
    ld hl,(drawn+2)
    ld de,STEPS
    add hl,de
    call picture
    ld hl,(drawn+4)
    ld de,STEPS*2
    add hl,de
    call picture
ships_done:
    ld a,1
    ld (pending),a
    ret

    ifdef ALLDIR
; The side ship from direction yaw (drawn), pitch (drawn+1), each 0-63.
hand_ship:
    ld a,(drawn)
    ld c,a                      ; C = yaw
    ld a,(drawn+1)              ; A = pitch
    cp 2*GN+1
    jr c,.upper
    neg
    add a,4*GN                  ; pitch past the top or bottom: the picture for
    ld b,a                      ; (-yaw, -pitch), flipped top-bottom
    ld a,c
    neg
    and 63
    ld c,a
    ld a,1
    ld (vflip),a
    ld a,b
.upper:
    ld b,a                      ; B = stored pitch, 0..2*GN
    ld a,c
    cp GN+1
    jr c,.front
    cp 3*GN
    jr nc,.front
    neg
    add a,2*GN                  ; facing away: the picture for (128 - yaw), flipped left-right
    and 63
    ld c,a
    ld a,1
    ld (hflip),a
.front:
    ld a,c
    add a,GN
    and 63                      ; column in the table: yaw -GN..GN -> 0..2*GN
    ld d,b
    ld e,2*GN+1
    mul d,e
    add de,a
    ld h,d
    ld l,e
    add hl,hl
    add hl,de
    ld de,gridtab
    add hl,de
    call open_picture
    jr ships_done
    endif

; HL = picture number (0 .. 3*STEPS-1). Unpacks it onto the screen at $4000, adding to what is there.
picture:
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,frametab
    add hl,de
; HL = table entry (page, address).
open_picture:
    ld a,(hl)
    nextreg $56,a               ; the picture's page and the next one at $C000-$FFFF
    inc a
    nextreg $57,a
    inc hl
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    ld a,(hl)                   ; first row
    inc hl
    ld b,(hl)                   ; rows
    inc hl
    ld c,a
    ld a,(vflip)
    or a
    ld a,c
    exx
    ld bc,0                     ; BC' = step through the row table after each row
    jr z,.down
    neg
    add a,192                   ; flipped top-bottom: start at row 192 - first, and go up
    ld bc,-4
.down:
    ld l,a
    ld h,0
    add hl,hl
    ld de,rowtab
    add hl,de                   ; HL' = row address table
    ld d,high revtab            ; DE' = bit-reverse table
    exx
    ld a,(hflip)
    or a
    jr nz,mirrored
.row:
    exx
    ld a,(hl)
    inc hl
    ex af,af'
    ld a,(hl)
    inc hl
    add hl,bc
    exx
    ld d,a
    ex af,af'
    ld e,a                      ; DE = start of this row on screen
.piece:
    ld a,(hl)
    inc hl
    or a
    jr z,.rowdone
    ld c,a
    swapnib
    and 15
    add a,e
    ld e,a                      ; skip
    ld a,c
    and 15
    jr z,.piece
    ld c,a
.byte:
    ld a,(de)
    or (hl)
    ld (de),a
    inc hl
    inc e
    dec c
    jr nz,.byte
    jr .piece
.rowdone:
    djnz .row
    ret

; The same, flipped left-right about column 128: pixel x goes to 256 - x.
; Each byte is bit-reversed and put at the mirror place, then moved one pixel right.
mirrored:
.row:
    exx
    ld a,(hl)
    inc hl
    ex af,af'
    ld a,(hl)
    inc hl
    add hl,bc
    exx
    ld d,a
    ex af,af'
    or 31
    ld e,a                      ; DE = last byte of this row on screen
.piece:
    ld a,(hl)
    inc hl
    or a
    jr z,.rowdone
    ld c,a
    swapnib
    and 15
    neg
    add a,e
    ld e,a                      ; skip, leftwards
    ld a,c
    and 15
    jr z,.piece
    ld c,a
.byte:
    ld a,(hl)
    inc hl
    exx
    ld e,a
    ld a,(de)                   ; bit-reversed
    exx
    srl a                       ; one pixel right; the pixel pushed out ...
    jr nc,.in
    inc e
    ex de,hl
    set 7,(hl)                  ; ... goes into the next byte
    ex de,hl
    dec e
.in:
    ex de,hl
    or (hl)
    ld (hl),a
    ex de,hl
    dec e
    dec c
    jr nz,.byte
    jr .piece
.rowdone:
    djnz .row
    ret

; Redraw the text window on Layer 2 from the strip, starting at row (scroll).
draw_text:
    ld hl,(scroll)
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,de
    add hl,hl                   ; * TEXTW (10)
    ld de,textbits
    add hl,de
    ex de,hl                    ; DE = strip
    ld hl,(scroll)
    ld (textrow),hl
    ld a,WIN_TOP
    ld b,WIN_ROWS
.row:
    push bc
    push af
    ld c,a
    rlca
    rlca
    rlca
    and 7
    add a,L2_PAGE
    nextreg $56,a               ; the page holding this screen row
    ld a,c
    and 31
    or $C0
    ld h,a
    ld l,0
    ld c,TEXTW
.byte:
    ld a,(de)
    inc de
    ld b,8
.bit:
    rlca
    jr c,.on
    ld (hl),CLEAR
    inc l
    djnz .bit
    jr .next
.on:
    ld (hl),YELLOW
    inc l
    djnz .bit
.next:
    dec c
    jr nz,.byte
    ld hl,(textrow)             ; the list wraps round
    inc hl
    ld bc,LIST_ROWS
    or a
    sbc hl,bc
    jr nz,.same
    ld de,textbits
    jr .store
.same:
    add hl,bc
.store:
    ld (textrow),hl
    pop af
    inc a
    pop bc
    djnz .row
    ret

; ---------------------------------------------------------------- variables
shown:      db 0                ; 0: bank 5 on screen, 1: bank 7
pending:    db 0                ; hidden screen is ready to show
manual:     db 0                ; side ship follows the stick
cycle:      dw 0                ; frame within hold + turn
auto:       dw 0                ; picture the automatic turn is on
side:       dw 0                ; picture the side ship is on
want:       dw 0,0,0            ; side, top, front (ALLDIR by hand: yaw, pitch, $FFFF, $FFFF)
drawn:      dw 0,0,0
scroll:     dw 0
textrow:    dw 0
textclock:  db TEXT_EVERY
gy:         db 0                ; hand-turned ship: yaw 0-63
gp:         db 16               ;                   pitch 0-63 (must follow gy)
handclock:  db 1
vflip:      db 0
state:      db 1                ; R-Type build: see the main loop
handdone:   db 0                ; R-Type build: the hand-turned ship has been shown (once only)
stickwait:  db 1                ; R-Type build: ignore the stick until it is let go
fadein:     db 0                ; R-Type build: fade in after the next picture reaches the screen
keyheld:    db $10              ; a key was down last frame (starts set: a key held at launch is ignored)
fakestick:  db 0
entry8e:    db 0                ; R-Type build: Next register $8E at start-up
nexhandle:  db $FF              ; R-Type build: the Next's loader leaves this file open and writes its handle here
badpage:    db 0                ; R-Type build: a picture page that failed the start-up check (0 = none)
hflip:      db 0

    ifdef GAME
    align 256
fade_tab:                       ; 8 x 256: colour RRRGGGBB at level L (0-7) = each part * L / 7
FL = 0
    dup 8
FV = 0
    dup 256
    if FV == $E3
    db $E3
    else
    db ((((FV >> 5) & 7) * FL / 7) << 5) | ((((FV >> 2) & 7) * FL / 7) << 2) | ((FV & 3) * FL / 7)
    endif
FV = FV + 1
    edup
FL = FL + 1
    edup
    endif
    align 256
    REV_TABLE
    DATA_TABLES
    ifdef ALLDIR
    GRID_TABLE
    endif

    ds 128
stack_top:

    assert $ <= $C000

; ---------------------------------------------------------------- Layer 2 picture (title and logo), bank 9-11
PG = L2_PAGE
OFS = 0
    dup 6
    mmu 6,PG
    org $C000
    incbin "spec_l2.bin",OFS,8192
PG = PG + 1
OFS = OFS + 8192
    edup

; ---------------------------------------------------------------- the stored pictures
PG = FIRST_PAGE
OFS = 0
    dup FRAME_PAGES
    mmu 6,PG
    org $C000
    incbin "spec_frames.bin",OFS,8192
PG = PG + 1
OFS = OFS + 8192
    edup

    ifdef ALLDIR
PG = FIRST_GRID
OFS = 0
    dup GRID_PAGES
    mmu 6,PG
    org $C000
    incbin "spec_grid.bin",OFS,8192
PG = PG + 1
OFS = OFS + 8192
    edup
    ifdef GAME
; ---------------------------------------------------------------- the game loader
; The file is this program followed by the game's memory banks (make_rtype_spec.py). On a real Next the
; disk calls (RST $08) are made by NextZXOS, which needs the ordinary 128K layout while it works:
;   48K BASIC ROM at the bottom (port $1FFD bit 2 and $7FFD bit 4, copied to BANK678 $5B67 and BANKM $5B5C),
;   bank 5 at $4000 with the system variables, bank 2 at $8000, bank 0 at $C000, no $DFFD paging,
;   the stack below $BFE0, IY at the system variables.
; So the loader runs from $A000 (bank 2), reads each 8K piece into $8000 and copies it to its page between
; disk calls. The game's banks 0-7 are kept in spare pages until the file is closed, then put in place.
; Border colour shows how far it got: yellow opening, cyan/green reading, white putting in place;
; red: the file did not open; red/yellow flashing: a read failed.
    mmu 6,LOADER_PAGE
    org $C000
    disp $A000
loader:
    di
    ld sp,loader_stack
    ld a,(entry8e)              ; (read these before $8000 is used as the buffer)
    ld (saved8e),a
    ld a,(nexhandle)
    ld (game_handle),a
    ld iy,$5C3A
    im 1
    nextreg $52,10
    nextreg $53,11
    nextreg $54,4
    nextreg $55,5
    ld bc,$DFFD
    xor a
    out (c),a
    ld bc,$1FFD
    ld a,%00000100              ; ROM 3 (48K BASIC) with $7FFD bit 4
    out (c),a
    ld ($5B67),a
    ld bc,$7FFD
    ld a,%00010000              ; bank 0 at the top
    out (c),a
    ld ($5B5C),a
    nextreg $56,0
    nextreg $57,1
    ld a,6
    out ($FE),a                 ; yellow: opening
    ld a,(game_handle)
    cp $FF
    jr nz,.open                 ; the file is still open from loading: its name does not matter
    ld a,'*'                    ; (no handle - in CSpect: open it by name)
    ld hl,game_file
    ld ix,game_file
    ld b,1
    rst $08
    db $9A                      ; F_OPEN
    di
    jp c,open_fail
    ld (game_handle),a
.open:
    ld a,(game_handle)
    ld bc,RT_OFS>>16
    ld de,RT_OFS&$FFFF
    ld l,0
    ld ixl,0
    rst $08
    db $9F                      ; F_SEEK to the game's banks
    di
    jp c,read_fail
    ld hl,game_pages
.next:
    ld a,(hl)
    cp $FF
    jr z,.done
    push hl
    and 1
    add a,4
    out ($FE),a                 ; cyan / green: reading
    ld a,(game_handle)
    ld hl,$8000
    ld ix,$8000
    ld bc,$2000
    rst $08
    db $9D                      ; F_READ 8K into the buffer
    di
    jp c,read_fail
    ld a,b
    cp $20
    jp nz,read_fail             ; a short read
    pop hl
    ld a,(hl)
    inc hl
    push hl
    nextreg $56,a               ; copy the buffer to its page ...
    ld hl,$8000
    ld de,$C000
    ld bc,$2000
    ldir
    nextreg $56,0               ; ... and back to the ordinary layout for the next disk call
    pop hl
    jr .next
.done:
    ld a,(game_handle)
    rst $08
    db $9B                      ; F_CLOSE: the last disk call
    di
    ld a,7
    out ($FE),a                 ; white: putting the held banks in place
    ld hl,place_list
.place:
    ld a,(hl)
    cp $FF
    jr z,.placed
    nextreg $56,a
    inc hl
    ld a,(hl)
    inc hl
    nextreg $57,a
    push hl
    ld hl,$C000
    ld de,$E000
    ld bc,$2000
    ldir
    pop hl
    jr .place
.placed:
    xor a
    out ($FE),a
    ld a,(saved8e)              ; the classic paging as the Next's loader left it
    or %00001000
    nextreg $8E,a
    nextreg $15,1               ; as the Next's own loader leaves things
    nextreg $43,$20
    nextreg $52,10
    nextreg $53,11
    jp $4000                    ; planted in the game's (blank) screen: puts bank 2 in place and starts the game
open_fail:
    ld a,2
    out ($FE),a                 ; red: the file did not open (was it renamed?)
    jr $
read_fail:
    ld a,2
    out ($FE),a
    ld b,0
.w1:
    djnz .w1
    ld a,6
    out ($FE),a
.w2:
    djnz .w2
    jr read_fail
saved8e:    db 0
game_handle: db 0
game_file:  RT_FILE_NAME
game_pages: RT_PAGES            ; one destination page per 8K piece, in file order
place_list: RT_PLACE            ; (held page, its real page) pairs
    ds 96
loader_stack:
    assert loader_stack < $BFE0
loader_end:
    ent
    savenex open "rtype_spec_intro.nex",start,stack_top
    savenex core 3,0,0
    savenex cfg 0,nexhandle,0,1 ; needs 2MB; keep the file open (the game is read from it later)
    ifdef LOADSCR
    ; the game's tape loading screen (r_type_loading.scr, beside the player's snapshot): the Next's loader
    ; shows it at once. It must be prepared in bank 5, which is then cleared again so it is not stored as a
    ; bank (bank 5 holds the system variables the disk calls need).
    mmu 6,10
    org $C000
    incbin "r_type_loading.scr"
    savenex screen scr
    mmu 6,10
    org $C000
    block 6912,0
    endif
    else
    savenex open "specanim2.nex",start,stack_top
    savenex core 3,0,0
    savenex cfg 0,0,0,1         ; needs 2MB
    endif
    else
    savenex open "specanim.nex",start,stack_top
    savenex core 3,0,0
    savenex cfg 0
    endif
    savenex auto
    savenex close
