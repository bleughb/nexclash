; Nodes of Yesod (Odin, 1985, 128K release) - engine 'nodes_of_yesod': every figure a hardware sprite.
; The game XORs each figure into a back buffer (0xE400, 168 lines) and copies the changed rectangle to the screen (LDIR at 36684), then paints
; the ink of the figure's empty cells on the screen (36889). All figures reach that one copy, once for each change (36680, after 36552 and 36592).
; So the buffer runs unchanged, the copy no longer writes, the paint no longer writes, and the copy's hook sets the object's sprites from its record.
; Hooks: alt ROM image 1 at 0x386E, tables in the image's low 8K, interrupts ON throughout. The handler writes 7FFD (three far calls), and an unlocked 7FFD write sets slots 0 and 1 back
; to the ROM, so no state may live in a page mapped there: the state is 64 bytes of game RAM nothing touches (0xB3C0), and a pattern page sits at slot 0 only around one OTIR, is read back
; afterwards, and the tile sent again if the handler came in between. Every such page has 0xF3 at offset 0, the byte the handler's JR reads from 0x0000.
; Object IX -> k = (IX - 0xFC00) / 32, 0-15. Sprites and half patterns k*6 .. k*6+5.
; Record: +0 bit 0 shown, bit 7 x negative; +1 x; +2 y (y + h carrying = negative); +4 h; +7,+8 graphic; +30 bit 7 mirrored.

        DEVICE ZXSPECTRUMNEXT

HELD    EQU 0xB3C0              ; per object: the graphic its pattern slots hold (16 words)
SHOWN   EQU 0xB3E0              ; per object: sprites on
V_DROP  EQU 0xB3F0              ; updates with a graphic not in the table (2 bytes): verify and JNext read it
V_CLIP  EQU 0xB3F2              ; the bottom line of the clip window
V_K     EQU 0xB3F3
V_T     EQU 0xB3F4
V_COLS  EQU 0xB3F5
V_HP    EQU 0xB3F6
V_LINE  EQU 0xB3F7
V_X     EQU 0xB3F8              ; 2 bytes
V_MIR   EQU 0xB3FA
V_C     EQU 0xB3FB
V_RW    EQU 0xB3FC
V_Y     EQU 0xB3FD              ; 2 bytes
V_SX    EQU 0xB3BE              ; 2 bytes
T_INDEX EQU 0x0200              ; (graphic - 0xB200) / 2 -> frame number, 0 = none (5632 bytes), in the alt ROM's low 8K, clear of the ROM's 0x1F54, which the game calls
T_FRAME EQU 0x1800              ; frame number * 8: page, tile, cols, rows, line, bytes wide

G_LOW   EQU 0xB200
G_SPAN  EQU 0x2C00
BOTTOM  EQU 36486               ; ADD A,n of the game's plot: n = 88 underground (line 167), 112 on the surface (line 143)

V_SPEED EQU 0xB3BB
HLIB_V_R EQU 0xB400
        INCLUDE "lib/hlib_speed.asm"
        ORG 0x386E
        INCLUDE "lib/hlib_r.asm"
V_IFF EQU 0xB409
V_ACTIVE EQU 0xB40A
V_IRQ_R EQU 0xB40B
V_LAST_FRAME EQU 0xB40C
V_LAST_LINE EQU 0xB40D
V_HAVE_TIME EQU 0xB40F
V_IRQ_SERIAL EQU 0xB410
V_SAVE_SERIAL EQU 0xB411
V_ATTR_SPEED EQU 0xB416
V_BACKDROP EQU 0xB417
V_HUD EQU 0xB418
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
        call backdrop_update
        call ny_speed_out
        call pace_player
        call ny_speed_in
        call ny_r_end
        call ny_speed_out
        pop hl
        pop de
        pop bc
        pop af
        ld ix,64992
        jp 40052

; ---- 36680 (LD B,0 / EX AF,AF'), both copies join here: sprites, then the copy's register effects with nothing written ----
e_blit: push af
        push bc
        push de
        push hl
        call ny_speed_in
        call original_m1
        ld (0xB412),a
        pop hl
        pop de
        pop bc
        pop af
        call ny_r_begin
        push af
        push bc
        push de
        push hl
        ld a,(0xB412)
        call ny_r_set
        call ny_r_run
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
        call ny_r_end
        call ny_speed_out
        jp 36843

; ---- 34268 room redraw, 33766 and 33946 new game, 38127 game over, 41596 teleport: no figures until they are plotted again ----
e_room: call hideall
        ld hl,23315
        jp 34271
e_new1: call hideall
        ld hl,16384
        jp 33769
e_new2: call hideall
        ld hl,16384
        jp 33949
e_over: call hideall
        ld hl,16384
        jp 38130
e_tele: call hideall
        ld hl,22528
        jp 41599

hideall:
        call ny_speed_in
        call ny_r_begin
        push af
        push bc
        ld a,-44
        call ny_r_set
        xor a
        ld (0xB404),a
        ld (0xB406),a
        ld (0xB408),a
        ld (V_HAVE_TIME),a
        call ny_r_run
        ld bc,0x123B
        xor a
        out (c),a               ; hide the sky before any room/menu/reset redraw
        nextreg 0x6B,0          ; the painted portrait follows the original play HUD
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

update: ld a,(BOTTOM)           ; the game's bottom line for this room
        neg
        dec a
        ld hl,V_CLIP
        cp (hl)
        jr z,.cl
        ld (hl),a
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,a
.cl:    ld a,ixh
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
.on:    ld a,(ix+15)            ; the game's plotter for this clip: 0x90C1 or 0x90C2 is a bare RET, so at this clip the original shows nothing
        cp 0x90
        jr nz,.pl
        ld a,(ix+14)
        cp 0xC1
        jr z,.np
        cp 0xC2
        jr nz,.pl
.np:    call hidek
        jr .out
.pl:    ld e,(ix+7)
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
        add hl,bc               ; HL -> page, tile, cols, rows, line, bytes
        push hl                 ; held?
        ld a,(V_K)
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
        sub 59
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
        jp 39086
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
        jp 39128
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
        ld b,a
        ld a,h
        cp l
        jr nz,.done
        cp 0x58
        jr c,.done
        cp 0x5B
        jr nc,.done
        push hl
        sub 0x58
        add a,a
        add a,0x03
        ld l,a
        ld h,0xB4
        ld (hl),b
        inc hl
        ld (hl),1
        pop hl
.done:  call ny_r_end
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
.attr:  sub 0x58
        add a,a
        add a,0x03
        ld l,a
        ld h,0xB4
        inc hl
        ld a,(hl)
        or a
        jr z,.bare
        dec hl
        ld a,(hl)
        jr .value
.bare:  pop hl
        push hl
        ld a,(hl)
.value: call ny_r_end
        call ny_speed_out
        pop hl
        pop bc
        and 15
        jp 31999
helpers_end:
        ASSERT helpers_end <= 0x1F50
        SAVEBIN "ny_helpers.bin",0x1E80,helpers_end-0x1E80

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
pace_player:
        ld bc,0
        ld (0xB414),bc
.poll:
        call pace_now
        ld c,a
        ld de,(0xB414)
        dec de
        ld (0xB414),de
        ld a,d
        or e
        jr z,pace_player.save
        ld a,(V_HAVE_TIME)
        or a
        jr z,.save
        ld a,c
        ld b,a
        ld a,(V_LAST_FRAME)
        ld e,a
        ld a,b
        sub e
        cp 8
        jr nc,.save             ; menu or a pause: start a new window
        push hl
        push bc
        ld e,a
        ld d,0
        ld hl,0
        ld bc,311
.frames:
        ld a,e
        or a
        jr z,.elapsed
        add hl,bc
        dec e
        jr .frames
.elapsed:
        ex de,hl
        pop bc
        pop hl
        push hl
        add hl,de
        ld de,(V_LAST_LINE)
        or a
        sbc hl,de
        ld de,332              ; calibrated against the original player update
        ld a,(V_SPEED)
        ld b,a
        inc b
        jr .scale_test
.scale: srl d
        rr e
.scale_test:
        djnz .scale
        or a
        sbc hl,de
        pop hl
        jr c,pace_player.poll
.save:  ld (V_LAST_LINE),hl
        ld a,c
        ld (V_LAST_FRAME),a
        ld a,1
        ld (V_HAVE_TIME),a
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
        ld a,-31                ; exact original LD A,(IX+5) span
        call ny_r_set
        pop af
        call ny_r_end
        ld a,(ix+5)
        jp 36854

e_attr_row:
        dec d
        jr nz,.again
        call ny_r_begin
        push af
        ld a,-21
        call ny_r_set
        pop af
        call ny_r_end
        HLIB_SPEED_OUT V_ATTR_SPEED
        jp 36902
.again: call ny_r_begin
        push af
        ld a,-16
        call ny_r_set
        pop af
        call ny_r_end
        jp 36859
; Static Layer 2 backdrops. No frame copying or animation. This runs inside the
; player's existing R-preserved, 28 MHz span and before its pace limiter.
; BOTTOM=112 is the original renderer's surface flag; caves use 88.
backdrop_update:
        ld a,(BOTTOM)
        xor 112
        sub 1
        sbc a,a                 ; FF exactly when BOTTOM == 112
        ld d,a
        and 18
        ld e,a
        ld a,d
        cpl
        and 21
        or e                    ; surface bank 18, underground bank 21
        nextreg 0x12,a
        ld a,(BOTTOM)
        xor 88
        sub 1
        sbc a,a                 ; FF exactly when BOTTOM == 88
        or d                    ; only the two original play modes may show it
        ld e,a
        and 2
        ld c,a
        ld a,(V_BACKDROP)
        neg                     ; flag 0/1 -> 00/FF, same cost on and off
        and c
        ld bc,0x123B
        out (c),a
        ld a,(V_HUD)
        neg
        and e
        and 0x81
        nextreg 0x6B,a          ; tilemap above ULA, clipped to the portrait only
        ret
aux_end:
        ASSERT aux_end <= 0x1E00
        SAVEBIN "ny_aux.bin",0x1C50,aux_end-0x1C50

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
        nextreg 0x1C,2          ; sprite clip window: the game clips to line 167 underground, 143 on the surface
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,167
        nextreg 0x15,0x01       ; sprites on, S L U
        ; Keep ULA ink opaque; only black PAPER reveals a separate backdrop.
        ; E2 is absent from the original ULA colours, unlike bright magenta E3.
        nextreg 0x12,18
        nextreg 0x13,18
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,167         ; HUD excluded; sky plane is black below row 47
        nextreg 0x14,0xE2
        nextreg 0x4A,0
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,backdrop_pal
        ld b,64
.bgpal: ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .bgpal
        nextreg 0x43,0
        nextreg 0x40,16
        nextreg 0x41,0xE2
        nextreg 0x40,24
        nextreg 0x41,0xE2
        nextreg 0x43,0x20
        nextreg 0x15,0x09       ; sprites, ULA, Layer 2
        nextreg 0x43,0x30
        nextreg 0x40,0
        ld hl,hud_pal
        ld b,32
.hudpal: ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .hudpal
        nextreg 0x4C,0
        nextreg 0x6C,0
        nextreg 0x6E,0x97       ; map at bank 7 + 0x1700; only twelve clipped cells are used
        nextreg 0x6F,0x9B       ; definitions at bank 7 + 0x1B00
        nextreg 0x2F,0
        nextreg 0x30,0
        nextreg 0x31,0
        nextreg 0x1C,8
        nextreg 0x1B,16
        nextreg 0x1B,31
        nextreg 0x1B,200
        nextreg 0x1B,223
        nextreg 0x6B,0
        nextreg 0x43,0x20
        ld a,(hud_enabled)
        ld (V_HUD),a
        ld a,(backdrop_enabled)
        ld (V_BACKDROP),a
        ld bc,0x123B
        xor a
        out (c),a               ; menu/startup: backdrops hidden until player update
        ld hl,printer_saved
        ld de,0x5B00
        ld bc,256
        ldir                    ; NEXLOAD overwrites live game state in this buffer
        ret
pal:    BLOCK 256,0             ; written by the build: 16 lines of 16 entries
backdrop_enabled: db 0          ; independent NXC toggle, off by default
backdrop_pal: BLOCK 64,0         ; 32 RGB333 colours, encoded as paired NR44 writes
hud_enabled: db 0               ; Enhanced owns the portrait; default is the original HUD
hud_pal: BLOCK 32,0
printer_saved: BLOCK 256,0
setup_end:

        SAVEBIN "ny_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ny_setup.bin",0xD000,setup_end-0xD000
