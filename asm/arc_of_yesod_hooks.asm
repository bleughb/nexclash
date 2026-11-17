; The Arc of Yesod (Thor / Odin, 1985, 128K release) - engine 'arc_of_yesod': every figure a hardware sprite.
; A port of asm/nodes_of_yesod_hooks.asm (the same game engine at other addresses): figures are XORed into a back buffer (0xE400, 168 lines), the changed
; rectangle is copied to the screen (LDIR at 0xD4B3) and the ink of the figure's empty cells is painted on the screen (0xD580). All figures reach that
; one copy (0xD4AF). The buffer runs unchanged, the copy and the paint no longer write, and the copy's hook sets the object's sprites from its record.
; Hooks: alt ROM image 1 at 0x386E, tables in the image's low 8K, interrupts ON throughout. The handler writes 7FFD (the AY music in bank 6), and an
; unlocked 7FFD write sets slots 0 and 1 back to the ROM, so no state may live in a page mapped there. The game leaves no free run below 0xC000 but
; 0x5B00-0x5B5A; all game code and the handler are in bank 0, at 0xC000 whenever a hook runs, so the object state sits in bank 0's 0xFBA0-0xFBFF (the
; cell map's rows 21-23, never used) and the rest at 0x5B00. A pattern page sits at slot 0 only around one OTIR, is read back afterwards, and the tile
; sent again if the handler came in between. Every such page has 0xF3 at offset 0, the byte the handler's JR reads from 0x0000.
; Object IX -> k = (IX - 0xFC00) / 32, 0-15. Sprites and half patterns k*6 .. k*6+5.
; Record: +0 bit 0 shown, bit 7 x negative; +1 x; +2 y (y + h carrying = negative); +4 h; +7,+8 graphic; +30 bit 7 mirrored.

        DEVICE ZXSPECTRUMNEXT

HELD    EQU 0xFBA0              ; per object: the graphic its pattern slots hold (16 words)
SHOWN   EQU 0xFBC0              ; per object: sprites on
V_DROP  EQU 0xFBD0              ; updates with a graphic not in the table (2 bytes): verify and JNext read it
V_K     EQU 0xFBD3
V_T     EQU 0xFBD4
V_COLS  EQU 0xFBD5
V_HP    EQU 0xFBD6
V_LINE  EQU 0xFBD7
V_X     EQU 0xFBD8              ; 2 bytes
V_MIR   EQU 0xFBDA
V_C     EQU 0xFBDB
V_RW    EQU 0xFBDC
V_Y     EQU 0xFBDD              ; 2 bytes
V_SX    EQU 0xFBE0              ; 2 bytes
T_INDEX EQU 0x0200              ; (graphic - 0x7E00) / 2 -> frame number, 0 = none (5120 bytes), in the alt ROM's low 8K, clear of the ROM's 0x1F54, which the game calls
T_FRAME EQU 0x1600              ; frame number * 8: page, tile, cols, rows, line, bytes wide (up to 159 frames, below 0x1B00)

SHADOW_PAGE EQU 23              ; Next page: the ink the original would have painted in each play-area cell (0 = none), at slot 4 for one access;
                                ; the handler never touches slot 4 (0x8000-0x9FFF: graphics, read by the game's plotters only)
G_LOW   EQU 0x7E00
G_SPAN  EQU 0x2800

V_SPEED EQU 0xFBE2
HLIB_V_R EQU 0x5B00
        INCLUDE "lib/hlib_speed.asm"
        ORG 0x386E
        INCLUDE "lib/hlib_r.asm"
V_IFF EQU 0x5B09
V_ACTIVE EQU 0x5B0A
V_IRQ_R EQU 0x5B0B
V_LAST_FRAME EQU 0x5B0C
V_LAST_LINE EQU 0x5B0D
V_HAVE_TIME EQU 0x5B0F
V_IRQ_SERIAL EQU 0x5B10
V_SAVE_SERIAL EQU 0x5B11
V_ATTR_SPEED EQU 0x5B16
V_WT0 EQU 0x5B19                ; 2 bytes: the open window's target, 1/16 lines
V_WT  EQU 0x5B1B                ; 2 bytes: that + the carry
V_PD  EQU 0x5B1D                ; 2 bytes, signed: time carried, 1/16 lines (+ = the build is ahead, - = behind)
V_WL  EQU 0x5B1F                ; 2 bytes: lines to reach
V_WS  EQU 0x5B21                ; the window's caller's speed
ISRLINES EQU 43                 ; the game's interrupt handler, lines (9,631 T mean, plain build)
PDMIN EQU -8192                 ; 512 lines behind at most
A_PLAYER EQU 130                 ; e_player's time, 1/16 lines
; R bookkeeping remains interruptible; the ISR wrappers repair an interrupted capture or store.
ny_r_begin:
        push af
        ld a,1
        ld (V_ACTIVE),a
        pop af
        push af
        ld a,r
ny_r_in_store:
        ld (HLIB_V_R),a
        pop af
        ret
ny_r_run:
        ret
ny_r_end:
        ld (HLIB_V_R + 2),a
        ld a,(HLIB_V_R + 1)
ny_r_out_set:
        ld r,a
        ld a,(HLIB_V_R + 2)
        push af
        xor a
        ld (V_ACTIVE),a
        pop af
        ret
; Once per player update. The limiter uses its own IRQ serial byte
; plus the raster line; the wait runs at the incoming clock with IRQs enabled.
e_player:
        call ny_speed_in
        call ny_r_begin
        push af
        push bc
        push de
        push hl
        ld a,-44
        call ny_r_set
        call ny_r_run
        ld hl,(V_PD)            ; this hook's own time goes to the account
        ld de,0 - A_PLAYER
        add hl,de
        ld (V_PD),hl
        call ny_r_end
        call ny_speed_out
        pop hl
        pop de
        pop bc
        pop af
        ld ix,64992
        jp 0xBAFC

; ---- 0xD4AF (LD B,0 / EX AF,AF'), both copies join here: sprites, then the copy's register effects with nothing written ----
e_blit: push af
        push bc
        push de
        push hl
        call ny_speed_in
        call blit_tgt
        call original_m1
        ld (0x5B12),a
        pop hl
        pop de
        pop bc
        pop af
        call ny_r_begin
        push af
        push bc
        push de
        push hl
        ld a,(0x5B12)
        call ny_r_set
        call ny_r_run
        call win_open
        call update
        pop hl
        pop de
        pop bc
        pop af
        ld b,0
.row:   ex af,af'
        ld a,c
        add hl,bc               ; LDIR's effects, without the writes
        ex de,hl
        add hl,bc
        ex de,hl
        ld bc,0
        ld c,32
        add hl,bc
        ld c,a
        or a
        sbc hl,bc
        ex de,hl
        or a
        sbc hl,bc
        ex de,hl
        inc d
        ld a,d
        and 7
        jp nz,.j
        ld a,e
        add a,32
        ld e,a
        jp c,.j
        ld a,d
        sub 8
        ld d,a
.j:     ex af,af'
        dec a
        jp nz,.row
        push af
        push bc
        push de
        push hl
        ld hl,(V_WT0)
        ld a,(V_SPEED)
        call win_wait
        pop hl
        pop de
        pop bc
        pop af
        call ny_r_end
        call ny_speed_out
        jp 0xD552               ; where the copy loop's own JP goes (the paint)

; ---- 0xAAF1 room redraw, 0xA985 and 0xAA3F new game, 0xDA50 game over, 0xC112 the window refresh: no figures until they are plotted again ----
e_room: call hideall
        ld hl,23485
        jp 0xAAF4
e_new1: call hideall
        ld hl,16384
        jp 0xA988
e_new2: call hideall
        ld hl,16384
        jp 0xAA42
e_over: call hideall
        ld hl,16384
        jp 0xDA53
e_tele: call hideall
        ld hl,22528
        jp 0xC115

hideall:
        call ny_speed_in
        call ny_r_begin
        push af
        push bc
        ld a,-44
        call ny_r_set
        xor a
        ld (V_HAVE_TIME),a
        nextreg 0x54,SHADOW_PAGE ; the room is drawn again: no cell holds a figure's ink
        push de
        push hl
        ld hl,0x8000
        ld de,0x8001
        ld bc,0x2FF
        ld (hl),a
        ldir
        pop hl
        pop de
        nextreg 0x54,4
        call ny_r_run
        ld bc,SHOWN
.o:     ld a,(bc)
        or a
        call nz,hobj
        inc c
        ld a,c
        cp low (SHOWN+16)
        jr nz,.o
        call ny_r_end
        call ny_speed_out
        pop bc
        pop af
        ret
; BC -> SHOWN[k], not zero: sprites off, count cleared
hobj:   push de
        ld a,c
        sub low SHOWN
        ld e,a
        add a,a
        add a,e
        add a,a                 ; k * 6
        ld e,a
        ld a,(bc)
        ld d,a
        xor a
        ld (bc),a
        ld a,e
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        dec d
        jr nz,.h
        pop de
        ret

update: ld a,ixh
        sub 0xFC
        cp 2
        jr nc,.out              ; not an object: counted by verify, not expected
        ld l,a
        ld a,ixl
        and 31
        jr nz,.out
        ld a,ixl
        rlca
        rlca
        rlca
        and 7
        ld h,a
        ld a,l
        add a,a
        add a,a
        add a,a
        or h
        ld (V_K),a
        bit 0,(ix+0)
        jr nz,.on
        call hidek
.out:   ret
.on:    ld e,(ix+7)
        ld d,(ix+8)
        ld hl,-G_LOW
        add hl,de
        ld a,h
        cp high G_SPAN
        jr nc,.drop
        srl h
        rr l
        ld bc,T_INDEX
        add hl,bc
        ld a,(hl)
        or a
        jr z,.drop
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,T_FRAME
        add hl,bc               ; HL -> page, tile, cols, rows, line, bytes, 1 = the game rewrites this graphic
        push hl
        ld bc,6
        add hl,bc
        ld a,(hl)
        or a
        jr nz,.dyn
        ld a,(V_K)              ; held?
        add a,a
        add a,low HELD
        ld l,a
        ld h,high HELD
        ld a,(hl)
        cp e
        jr nz,.new
        inc hl
        ld a,(hl)
        cp d
        jr z,.same
        dec hl
.new:   ld (hl),e
        inc hl
        ld (hl),d
        pop hl
        push hl
        call upload
.same:  pop hl
        call show
        jr .out
.drop:  ld hl,(V_DROP)
        inc hl
        ld (V_DROP),hl
        call hidek
        jr .out
.dyn:   ld a,(V_K)              ; the appear / vanish effect's graphic: its tiles come from its bytes as they are now, and nothing is held
        add a,a
        add a,low HELD
        ld l,a
        ld h,high HELD
        ld (hl),0xFF
        inc hl
        ld (hl),0xFF
        call dynload
        jr .same

hidek:  ld a,(V_K)
        add a,low SHOWN
        ld c,a
        ld b,high SHOWN
        ld a,(bc)
        or a
        ret z
        jp hobj

; HL -> frame record. Patterns to half patterns k*6... Code here is in slot 1; the source page sits at slot 0 for the length of one tile.
upload: ld a,(V_K)
        ld e,a
        add a,a
        add a,e
        add a,a
        ld (V_HP),a             ; half pattern
        ld a,(hl)               ; page
        inc hl
        ld e,(hl)               ; tile
        inc hl
        ld d,(hl)               ; cols
        inc hl
        push af
        ld a,(hl)               ; rows
        ld b,a
        xor a
.m:     add a,d
        djnz .m
        ld d,a                  ; tiles
        pop af
        ld l,e                  ; 128 * (tile + 1): offset 0 keeps 0xF3 free
        inc l
        ld h,0
        srl l
        rr h
        ld e,a                  ; E = page
        ld a,h
        ld h,l
        ld l,a
.t:     ld a,(V_HP)
        rrca                    ; pattern select: half pattern / 2, the half in bit 7
        ld bc,0x303B
        out (c),a
        push hl
        ld a,e
        nextreg 0x50,a
        ld bc,0x805B
        otir
        ld bc,0x243B            ; still there? The handler's 7FFD writes put the ROM back at slot 0.
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        cp e
        jr z,.ok
        pop hl                  ; send this tile again
        jr .t
.ok:    pop af
        ld a,(V_HP)
        inc a
        ld (V_HP),a
        dec d
        jr nz,.t
        nextreg 0x50,0xFF
        ret

; HL -> frame record
show:   inc hl
        inc hl
        ld a,(hl)
        ld (V_COLS),a
        ld b,a
        inc hl
        ld a,(hl)
        ld (V_RW),a
        inc hl
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_LINE),a
        inc hl
        ld e,(hl)               ; bytes wide
        ld a,(ix+30)
        and 0x80
        ld (V_MIR),a
        ; X of the first tile, +32. Not mirrored: x - 1 (the margin). Mirrored: x + bytes*8 + 1 - cols*16.
        ld l,(ix+1)
        ld h,0
        bit 7,(ix+0)
        jr z,.pos
        dec h
.pos:   ld a,(V_MIR)
        or a
        jr z,.n
        ld a,e
        add a,a
        add a,a
        add a,a                 ; bytes * 8
        ld e,a
        ld d,0
        add hl,de
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,a                 ; cols * 16
        ld e,a
        ld d,0
        or a
        sbc hl,de
        inc hl
        inc hl
.n:     ld de,31
        add hl,de
        ld (V_X),hl
        ; Y of the first tile, +32: y - 1, y negative when y + h carries
        ld a,(ix+2)
        ld l,a
        ld h,0
        add a,(ix+4)
        jr nc,.yp
        dec h
.yp:    ld de,31
        add hl,de
        ld (V_Y),hl
        xor a
        ld (V_T),a
.rw:    xor a
        ld (V_C),a
        ld hl,(V_X)
        ld a,(V_MIR)
        or a
        jr z,.fx
        ld a,(V_COLS)           ; mirrored: first column is the rightmost
        dec a
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        add hl,de
.fx:    ld (V_SX),hl
.co:    ld a,(V_K)
        ld e,a
        add a,a
        add a,e
        add a,a                 ; k * 6
        ld e,a
        ld a,(V_T)
        add a,e
        ld e,a                  ; sprite and half pattern
        nextreg 0x34,a
        ld hl,(V_SX)
        ld a,l
        nextreg 0x35,a
        ld a,(V_Y)
        nextreg 0x36,a
        ld a,(V_MIR)
        or a
        jr z,.m1
        ld a,8
.m1:    ld d,a
        ld a,h
        and 1
        or d
        ld d,a
        ld a,(V_LINE)
        or d
        nextreg 0x37,a
        ld a,e
        srl a                   ; pattern = half / 2, half in bit 6 of 0x39
        or 0xC0
        nextreg 0x38,a
        ld a,e
        and 1
        rrca
        rrca
        or 0x80
        ld d,a
        ld a,(V_Y+1)
        and 1
        or d
        nextreg 0x39,a
        ld de,16
        ld a,(V_MIR)
        or a
        jr z,.nx
        ld de,-16
.nx:    add hl,de
        ld (V_SX),hl
        ld hl,V_T
        inc (hl)
        ld hl,V_C
        inc (hl)
        ld a,(V_COLS)
        cp (hl)
        jp nz,.co
        ld hl,(V_Y)
        ld de,16
        add hl,de
        ld (V_Y),hl
        ld hl,V_RW
        dec (hl)
        jp nz,.rw
        ; sprites beyond this frame's tiles off
        ld a,(V_K)
        add a,low SHOWN
        ld c,a
        ld b,high SHOWN
        ld a,(V_T)
        ld d,a                  ; new count
        ld a,(bc)
        ld e,a                  ; old count
        ld a,d
        ld (bc),a
        ld a,e
        sub d
        ret c
        ret z
        ld e,a                  ; how many
        ld a,c
        sub low SHOWN
        ld b,a
        add a,a
        add a,b
        add a,a
        add a,d                 ; first to clear
.off:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        dec e
        jr nz,.off
        ret
; Exact M1 span of original rectangle copy, including screen-row branches.
; A=height, C=width, DE=screen destination. Caller has saved all registers.
original_m1:
        ld h,a
        ld a,c
        add a,a
        add a,11
        ld b,a
        ld l,2
.row:   ld a,l
        add a,b
        ld l,a
        inc d
        ld a,d
        and 7
        jr nz,.next
        ld a,l
        add a,-3
        ld l,a
        ld a,e
        add a,32
        ld e,a
        jr c,.next
        ld a,l
        add a,-3
        ld l,a
        ld a,d
        sub 8
        ld d,a
.next:  dec h
        jr nz,.row
        ld a,l
        sub 84                  ; 59 + 25, blit_tgt's M1s before R is read
        ret
e_irq_in:
        push af
        push bc
        push de
        push af
        push bc
        ld a,r
        ld c,a
        sub 8
        ld (V_IRQ_R),a
        ld a,(V_IRQ_SERIAL)
        inc a
        ld (V_IRQ_SERIAL),a
        ld a,c
        sub 8
        and 0x7F
        bit 7,c
        jr z,.r
        or 0x80
.r:     ld r,a
        pop bc
        pop af
        jp 0xDDB6
e_irq_out:
        push af
        push bc
        ld a,r
        ld c,a
        ld a,(V_IRQ_R)
        ld b,a
        ld a,c
        sub 5
        sub b
        add a,7
        ld b,a
        ld a,(V_ACTIVE)
        or a
        jr z,.restore
        ld a,b
        call hlib_r_add
        push bc
        ld c,b
        ld a,(HLIB_V_R)
        ld b,a
        add a,c
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld (HLIB_V_R),a
        pop bc
        ld hl,12
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)              ; return PC of the interrupted instruction
        ld hl,ny_r_in_store
        or a
        sbc hl,de
        jr z,.fix_a
        ld hl,ny_r_out_set
        or a
        sbc hl,de
        jr z,.fix_a
        ld a,d
        cp high ny_set_b
        jr nz,.restore
        ld a,e
        cp low ny_set_b
        jr c,.restore
        cp low ny_set_ab
        jr c,.fix_a
        cp low ny_set_store
        jr c,.fix_c
        jr z,.fix_a
        jr .restore
.fix_c: ld hl,8                 ; saved C in the original ISR stack frame
        jr .fix
.fix_a: ld hl,11                ; saved A in the original ISR stack frame
.fix:   add hl,sp
        ld a,(hl)
        ld e,a
        add a,b
        and 0x7F
        bit 7,e
        jr z,.put
        or 0x80
.put:   ld (hl),a
.restore:
        ld a,c
        sub 8
        and 0x7F
        bit 7,c
        jr z,.r
        or 0x80
.r:     ld r,a
        pop bc
        pop af
        pop hl
        pop de
        pop bc
        jp 0xDDF1
rom_end:

; Original random reads use address R*257. Preserve their view of ROM and
; screen bytes even though those areas now hold tables or bare scenery.
        ORG 0x1E80
e_attr:
        call ny_speed_in
        call ny_r_begin
        push af
        push bc
        push af
        ld a,-42
        call ny_r_set
        pop af
        ld b,a                  ; the ink the original stores: kept in the shadow page, for the game's reads of screen colours
        nextreg 0x54,SHADOW_PAGE
        push hl
        ld a,h
        add a,0x28              ; 0x58xx -> 0x80xx
        ld h,a
        ld (hl),b
        pop hl
        nextreg 0x54,4
        call ny_r_end
        call ny_speed_out
        pop bc
        pop af
        ret

e_random:
        call ny_speed_in
        call ny_r_begin
        push bc
        push hl
        ld a,-41
        call ny_r_set
        ld a,h
        cp 0x40
        jr c,.rom
        cp 0x58
        jr c,.buffer
        cp 0x5B
        jr c,.attr
        ld a,(hl)
        jr .value
.rom:   ld l,a
        ld h,0x1E
        ld a,(hl)
        jr .value
.buffer:
        sub 0x40
        add a,a
        add a,0x40
        ld l,a
        ld h,0x1E
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,(hl)
        jr .value
.attr:  nextreg 0x54,SHADOW_PAGE
        add a,0x28              ; 0x58xx -> 0x80xx
        ld h,a
        ld a,(hl)
        nextreg 0x54,4
        or a
        jr nz,.value            ; painted since the room was drawn: the original's screen holds that ink
.bare:  pop hl
        push hl
        ld a,(hl)
.value: call ny_r_end
        call ny_speed_out
        pop hl
        pop bc
        and 15
        jp 0xC358
; win_since: HL = lines since win_open (a window is under a frame), ISRLINES less if an interrupt came: it took its
; time whichever clock it ran at, as in the original. A, BC, DE, F lost.
win_since:
        call pace_now
        ld c,a
        ld de,(V_LAST_LINE)
        or a
        sbc hl,de
        jr nc,.p
        ld de,311
        add hl,de
.p:     ld a,(V_LAST_FRAME)
        cp c
        ret z
        ld de,ISRLINES
        or a
        sbc hl,de
        ret nc
        ld hl,0
        ret

; blit_tgt: A = rows, C = columns -> V_WT0 = 1.5 r c + 10 r: 21 T r c + 140 T r, in 1/16 lines. Keeps every register.
blit_tgt:
        push af
        push de
        push hl
        ld d,a
        ld e,c
        mul d,e
        ld h,d
        ld l,e
        srl d
        rr e
        add hl,de
        ld e,a
        ld d,10
        mul d,e
        add hl,de
        ld (V_WT0),hl
        pop hl
        pop de
        pop af
        ret
helpers_end:
        ASSERT helpers_end <= 0x1F50
        SAVEBIN "arc_helpers.bin",0x1E80,helpers_end-0x1E80

        ORG 0x1C50
; The ISR is not changed internally. These wrappers account its M1 cycles
; when it interrupts a sprite hook or pacing wait, so restoring R retains them.
; A=game IRQ frame counter, HL=stable video line. Read high/low/high and
; the frame byte twice so an ISR during the read starts the sample again.
pace_now:
.retry: ld a,(V_IRQ_SERIAL)
        push af
        ld bc,0x243B
        ld a,0x1E
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        xor h
        and 1
        jr nz,.retry_pop
        ld a,(V_IRQ_SERIAL)
        ld c,a
        pop af
        cp c
        jr nz,.retry
        push af
        ld de,65                ; 128K cvc origin relative to the ULA IRQ frame
        add hl,de
        ld de,311
        or a
        sbc hl,de
        jr nc,.phase
        add hl,de
.phase: pop af
        ret
.retry_pop:
        pop af
        jr .retry
; ---- pace (v1.6): the build skips the original's copy (LDIR, 36680) and runs its attribute walk (36851-36902) at 28 MHz. Each is now a
; window: V_LAST_* at its start, the target = the original's time for its size (plain build, JNext; interrupts left out), waited for at
; its end at the caller's clock, what is over or under carried in V_PD (1/16 line). No wait anywhere else. Interrupts stay on.
win_open:
        call pace_now
        ld (V_LAST_LINE),hl
        ld (V_LAST_FRAME),a
        ret

; win_wait: A = the caller's speed. HL = target (1/16 lines). Every register kept but HL, A, F (the callers save what they need).
win_wait:
        ld (V_WS),a
        ld de,(V_PD)
        add hl,de               ; HL: the time this window may take, signed
        ld (V_WT),hl
        bit 7,h
        jr nz,.done             ; behind already: no wait
        ld b,4
.q:     srl h
        rr l
        djnz .q
        ld a,(V_WS)
        ld b,a
        inc b
        jr .st
.sc:    srl h                   ; a caller above 3.5 MHz had the original at that clock
        rr l
.st:    djnz .sc
        ld (V_WL),hl
        ld a,(V_WS)
        nextreg 0x07,a
        ld hl,0
        ld (0x5B14),hl          ; poll guard: 65,536 polls, then give up
.poll:  call win_since
        ld de,(V_WL)
        or a
        sbc hl,de
        jr nc,.met
        ld hl,(0x5B14)
        dec hl
        ld (0x5B14),hl
        ld a,h
        or l
        jr nz,.poll
.met:   nextreg 0x07,3
.done:  call win_since          ; HL = lines the window lasted (its interrupts left out)
        ld b,4
.m:     add hl,hl
        djnz .m                 ; x 16
        ex de,hl
        ld hl,(V_WT)
        or a
        sbc hl,de               ; left over: carried (ahead by under a line; behind down to PDMIN)
        bit 7,h
        jr z,.w
        ld de,PDMIN & 0xFFFF
        push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.w
        ex de,hl
.w:     ld (V_PD),hl
        ret

ny_speed_in:
        HLIB_SPEED_IN V_SPEED
        ret
ny_speed_out:
        HLIB_SPEED_OUT V_SPEED
        ret
ny_r_set:
        push bc
        ld c,a
        ld a,(HLIB_V_R)
ny_set_b:
        ld b,a
        add a,c
        and 0x7F
ny_set_c:
        ld c,a
ny_set_ab:
        ld a,b
        and 0x80
ny_set_or:
        or c
ny_set_store:
        ld (HLIB_V_R + 1),a
        pop bc
        ret
        ASSERT high ny_set_b == high ny_set_store
; Accelerate the figure attribute walk as one rendering burst. Nested cell
; hooks restore 28 MHz; only the last row restores the game's incoming clock.
e_attr_enter:
        HLIB_SPEED_IN V_ATTR_SPEED
        call ny_r_begin
        push af
        push bc
        push de
        push hl
        ld c,d                  ; 11 D E + 3 D + 3: 155 T D E + 39 T D + 45 T, in 1/16 lines
        mul d,e
        ld d,e
        ld e,11
        mul d,e
        ld a,c
        add a,a
        add a,c
        add a,3
        add a,e
        ld e,a
        jr nc,.h
        inc d
.h:     ld (V_WT0),de
        call win_open
        pop hl
        pop de
        pop bc
        ld a,-31                ; exact original LD A,(IX+5) span
        call ny_r_set
        pop af
        call ny_r_end
        ld a,(ix+5)
        jp 0xD55D

e_attr_row:
        dec d
        jr nz,.again
        call ny_r_begin
        push af
        push bc
        push de
        push hl
        ld hl,(V_WT0)
        ld a,(V_ATTR_SPEED)
        call win_wait
        pop hl
        pop de
        pop bc
        ld a,-21
        call ny_r_set
        pop af
        call ny_r_end
        HLIB_SPEED_OUT V_ATTR_SPEED
        jp 0xD58D
.again: call ny_r_begin
        push af
        ld a,-16
        call ny_r_set
        pop af
        call ny_r_end
        jp 0xD562
aux_end:
        ASSERT aux_end <= 0x1E00
        SAVEBIN "arc_aux.bin",0x1C50,aux_end-0x1C50

        ORG 0x1B00              ; the low 8K between the frame table and the pace helpers
; ---- 0xC1CC (LD L,A / LD H,A / LD A,(HL)): the game's second random read, address R*257, as e_random sees it ----
e_random2:
        ld l,a
        ld h,a
        push af                 ; the original's three loads change no flag
        call ny_speed_in
        call ny_r_begin
        push bc
        push hl
        ld a,-46
        call ny_r_set
        ld a,h
        cp 0x40
        jr c,.rom
        cp 0x58
        jr c,.buffer
        cp 0x5B
        jr c,.attr
        ld a,(hl)
        jr .value
.rom:   ld l,a
        ld h,0x1E
        ld a,(hl)
        jr .value
.buffer:
        sub 0x40
        add a,a
        add a,0x40
        ld l,a
        ld h,0x1E
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,(hl)
        jr .value
.attr:  nextreg 0x54,SHADOW_PAGE
        add a,0x28              ; 0x58xx -> 0x80xx
        ld h,a
        ld a,(hl)
        nextreg 0x54,4
        or a
        jr nz,.value            ; painted since the room was drawn: the original's screen holds that ink
.bare:  pop hl
        push hl
        ld a,(hl)
.value: call ny_r_end
        call ny_speed_out
        pop hl
        pop bc
        ex (sp),hl              ; the value into the saved AF's A
        ld h,a
        ex (sp),hl
        pop af
        jp 0xC1CF

; ---- 0xCF07 (LD A,(HL) / AND 7): the beam reads a play-area colour and leaves a cell alone unless its ink is black ----
e_beam: call ny_speed_in
        call ny_r_begin
        push hl
        ld a,-39
        call ny_r_set
        nextreg 0x54,SHADOW_PAGE
        ld a,h
        add a,0x28              ; 0x58xx -> 0x80xx
        ld h,a
        ld a,(hl)
        nextreg 0x54,4
        pop hl
        or a
        jr nz,.value            ; painted since the room was drawn: the original's screen holds that ink
        ld a,(hl)
.value: call ny_r_end
        call ny_speed_out
        and 7
        jp 0xCF0A

; DE -> the rows of a graphic 3 bytes wide (its height at DE - 2). Its 6 tiles (2 x 3; ink only, the graphic one pixel in from the left and the top, as
; the build's patterns) are made in the shadow page above the colours and sent to the object's half patterns. A, BC, DE, HL lost.
DYN_BUF EQU 0x8400
dynload:
        dec de
        dec de
        ld a,(de)
        inc de
        inc de
        push af                 ; rows
        nextreg 0x54,SHADOW_PAGE
        push de
        ld hl,DYN_BUF
        ld de,DYN_BUF+1
        ld bc,767
        ld (hl),0
        ldir
        pop de
        pop bc                  ; B = rows
        ld c,1                  ; canvas line
        ld hl,DYN_BUF+8
.line:  push bc
        nextreg 0x54,4          ; the graphic itself is in slot 4's own page
        ld a,(de)
        inc de
        ld b,a
        ld a,(de)
        inc de
        ld c,a
        ld a,(de)
        inc de
        nextreg 0x54,SHADOW_PAGE
        push de
        srl b                   ; B, C, E, D = the canvas line's 32 pixels
        rr c
        rra
        ld e,a
        ld a,0
        rra
        ld d,a
        ld a,b
        call dynexp
        ld a,c
        call dynexp
        push hl
        ld bc,120
        add hl,bc               ; the same line of the tile to the right
        ld a,e
        call dynexp
        ld a,d
        call dynexp
        pop hl
        pop de
        pop bc
        inc c
        ld a,c
        and 15
        jr nz,.next
        ld a,l                  ; the next row of tiles: past this row's right tile
        add a,128
        ld l,a
        jr nc,.next
        inc h
.next:  djnz .line
        ld a,(V_K)
        ld e,a
        add a,a
        add a,e
        add a,a
        ld e,a                  ; first half pattern
        ld hl,DYN_BUF
        ld d,6
.t:     ld a,e
        rrca
        ld bc,0x303B
        out (c),a
        ld bc,0x805B
        otir
        inc e
        dec d
        jr nz,.t
        nextreg 0x54,4
        ret
; A = 8 pixels -> 4 pattern bytes at HL (nibble 1 = ink). HL advances; BC, DE kept.
dynexp: push bc
        ld c,a
        ld b,4
.l:     xor a
        rl c
        jr nc,.a
        or 0x10
.a:     rl c
        jr nc,.b
        or 0x01
.b:     ld (hl),a
        inc hl
        djnz .l
        pop bc
        ret
aux2_end:
        ASSERT aux2_end <= 0x1C50
        SAVEBIN "arc_aux2.bin",0x1B00,aux2_end-0x1B00

        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0          ; index 0 clear
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2          ; sprite clip window: the play area's 168 lines, never changed
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,167
        nextreg 0x15,0x01       ; sprites on, S L U
        ld hl,printer_saved
        ld de,0x5B00
        ld bc,0xBC
        ldir                    ; NEXLOAD overwrites live game state in this buffer; 0x5BBC on is the start-up tail's
        ret
pal:    BLOCK 256,0             ; written by the build: 16 lines of 16 entries
printer_saved: BLOCK 0xBC,0
setup_end:

        SAVEBIN "arc_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "arc_setup.bin",0xD000,setup_end-0xD000
