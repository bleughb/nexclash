; Renegade (Imagine, 1987, 128K release) - every figure a hardware sprite. Engine 'renegade128', from 'renegade1' with the addresses of this release, an outline, and interrupts off in hooks.
; The game composes a dirty rectangle at 0xFD00: tiles, then every part that overlaps it (39141, masked AND/OR at 38673 and
; 38812), then copies the rectangle to the screen. LD (DE),A -> LD A,(DE) at those two stores (same T-states, same registers)
; keeps every figure out of the buffer, so the copy writes bare scenery. Everything else runs as it did.
; Sprites follow the part records once per game tick (32834, and after a level's first draw 32800): list 41974 in order,
; each object (0xBF00 + id): part +15, part +23, extra (word at +3, records at 0xFF01 + 8n), later = in front, as the game.
; Part record: +0 x column (signed), +1 top line, +5 flags (shown when bits 7, 6, 1 are all set, as 39141 tests; bit 0 mirrored),
; +6 graphic. Graphic: W, R, then W columns of R (mask, data) pairs.
; Graphics change at level loads, so a graphic is found by address AND checksum in a hash table built from every level's data.
; Hooks: alt ROM images 0 and 1 at 0x386E. Hooks keep IX, IY, alternates; state page at slot 2, pattern pages at slot 6 only while uploading.

        DEVICE ZXSPECTRUMNEXT

STATE   EQU 22                  ; bank 11, first 8K
SLOT2   EQU 10                  ; the page that belongs at slot 2
HASH    EQU 0x4000              ; 512 entries of 6: graphic lo, hi, sum lo, hi, pattern page (0 = empty), index in page
HASHEND EQU 0x4C00
HELD    EQU 0x4C00              ; per part slot: the graphic its pattern slots hold (24 words)
V_KEY   EQU 0x4D00              ; level + wave: a change means graphics at the same address may differ
V_N     EQU 0x4D01              ; next sprite
V_LAST  EQU 0x4D02              ; sprites on after the last pass
V_ID    EQU 0x4D03
V_PI    EQU 0x4D04              ; part slot: 0-15 object parts, 16-23 extras
V_REC   EQU 0x4D05
V_FL    EQU 0x4D07
V_G     EQU 0x4D08
V_W     EQU 0x4D0A
V_R     EQU 0x4D0B
V_COLS  EQU 0x4D0C
V_ROWS  EQU 0x4D0D
V_TILES EQU 0x4D0E
V_PAT   EQU 0x4D0F
V_SUM   EQU 0x4D10
V_X     EQU 0x4D12
V_Y     EQU 0x4D14
V_C     EQU 0x4D15
V_RW    EQU 0x4D16
V_TP    EQU 0x4D17
V_DROP  EQU 0x4D18              ; parts that could not be shown (2 bytes): verify and JNext read it
V_LV    EQU 0x4D1C
V_IE    EQU 0x4D1D
V_FB    EQU 0x4D1A              ; graphics found by address alone (2 bytes)
MAXSPR  EQU 124

        ORG 0x386E
; ---- 32834 game tick ----
e_tick: push af
        push bc
        push de
        push hl
        call commit
        pop hl
        pop de
        pop bc
        pop af
        ld hl,49126
        jp 32837

; ---- 32800 CALL 42314: a life or level has just been drawn; the tune plays with the figures up ----
e_start:
        push af
        push bc
        push de
        push hl
        call commit
        pop hl
        pop de
        pop bc
        pop af
        jp 42314

; ---- 39940 screen clear: no figures ----
e_clear:
        push af
        push bc
        push de
        push hl
        call hideall
        pop hl
        pop de
        pop bc
        pop af
        ld hl,16384
        jp 39943

; ---- 38833 redraw of the whole play area: the figures come back at the next tick ----
e_redraw:
        push af
        push bc
        push de
        push hl
        call hideall
        pop hl
        pop de
        pop bc
        pop af
        ld ix,(42230)
        jp 38837

; The handler touches slots 3 to 7 (work/isrslots.py) and pages bank 1 at slots 6-7: the state page goes at slot 2, which it never touches,
; and interrupts stay on, except while a pattern page is at slot 6. A's flags: NZ when they were on (LD A,I twice: the NMOS quirk).
dioff:  ld a,i
        jp pe,.on
        ex (sp),hl              ; past the 32 T when LD A,I can read 0 with interrupts on
        ex (sp),hl
        ld a,i
        jp pe,.on
        di
        xor a
        ret
.on:    di
        or 1
        ret
eion:   ei
        ret

; ---- the start: the loading screen is up. A key, or about 5 seconds, then the game's own next instruction. No game memory touched.
e_front:
        push af
        push bc
        push de
        ld d,5
.o:     ld bc,0
.i:     xor a
        in a,(254)
        cpl
        and 31
        jr nz,.go
        dec bc
        ld a,b
        or c
        jr nz,.i
        dec d
        jr nz,.o
.go:    pop de
        pop bc
        pop af
        jp 31814

hideall:
        nextreg 0x07,3
        nextreg 0x52,STATE
        xor a
        ld (V_N),a
        call hide
        jr leave

commit: ld a,(28840)
        ld e,a
        ld a,(28872)
        and 3
        ld c,a                  ; level
        ld b,a
        nextreg 0x07,3
        nextreg 0x52,STATE
        ld (V_LV),a
        ld a,e
        add a,a
        add a,a
        or b
        ld hl,V_KEY
        cp (hl)
        jr z,.same
        ld (hl),a
        ld hl,HELD
        ld b,48
.z:     ld (hl),0
        inc hl
        djnz .z
        call floor              ; C = level
.same:  xor a
        ld (V_N),a
        ld hl,41974
        ld b,12                 ; the list holds 8 objects and an end mark: this only bounds it
.loop:  ld a,(hl)
        cp 255
        jr z,.done
        inc hl
        push bc
        push hl
        ld (V_ID),a
        call obj
        pop hl
        pop bc
        djnz .loop
.done:  call hide
leave:  nextreg 0x52,SLOT2
        nextreg 0x07,0
        ret

; hide sprites V_N .. V_LAST-1, V_LAST = V_N
hide:   ld a,(V_LAST)
        ld b,a
        ld a,(V_N)
        ld (V_LAST),a
.h:     cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .h

; sprite palette entry 2 = the body: the paper of this level's floor, as the figure's body shows on the floor in the original
floor:  ld a,c
        add a,a
        add a,a
        add a,a
        add a,low floors
        ld l,a
        ld a,0
        adc a,high floors
        ld h,a
        nextreg 0x43,0x20
        nextreg 0x40,2
        ld b,2
.a:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .a
        nextreg 0x40,10
        ld b,6
.b:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .b
        ret
; per level: body (the floor's paper), outline (white, black where the body is white), six palette entries for this level's painted figures
floors: DB 0xFC,0xFF,0x03,0xE0,0xE7,0x1C,0x1F,0x02
        DB 0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0x02
        DB 0x16,0xFF,0x03,0xE0,0xE7,0x1C,0x1F,0x02
        DB 0x1C,0xFF,0x03,0xE0,0xE7,0x1C,0x1F,0x02

obj:    ld a,(V_ID)
        ld b,0
.d:     cp 31
        jr c,.r
        sub 31
        inc b
        jr .d
.r:     or a
        ret nz
        ld a,b
        cp 8
        ret nc
        add a,a
        ld (V_PI),a
        ld a,(V_ID)
        add a,15
        ld l,a
        ld h,0xBF
        call part
        ld hl,V_PI
        inc (hl)
        ld a,(V_ID)
        add a,23
        ld l,a
        ld h,0xBF
        call part
        ld a,(V_ID)             ; the extra
        add a,3
        ld l,a
        ld h,0xBF
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a
        ld a,h
        cp 0xFF
        ret nz                  ; (a stale word points into the ROM: its rectangle never overlaps; verify counts plots)
        ld a,l
        dec a
        ld b,a
        and 7
        ret nz
        ld a,b
        rrca
        rrca
        rrca
        cp 8
        ret nc
        add a,16
        ld (V_PI),a
        ; fall through

; HL = part record
part:   ld (V_REC),hl
        ld de,5
        add hl,de
        ld a,(hl)
        ld (V_FL),a
        or 0x3D
        inc a
        ret nz                  ; not shown
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_G),de
        ld a,d
        cp 0x80
        jp c,drop
        ld a,(de)
        dec a
        cp 6
        jr nc,drop              ; W 1-6
        inc a
        ld (V_W),a
        add a,a
        add a,a
        add a,a
        add a,17                ; W * 8 + the outline's 2, rounded up
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (V_COLS),a           ; 16 pixel columns
        ld b,a
        inc de
        ld a,(de)
        dec a
        cp 64
        jr nc,drop              ; R 1-64
        inc a
        ld (V_R),a
        add a,17
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (V_ROWS),a
        ld c,a
        xor a
.m:     add a,c
        djnz .m
        ld (V_TILES),a
        ld c,a
        ld a,(V_PI)
        cp 16
        jr nc,.ex
        ld b,a
        add a,a
        add a,b
        add a,a                 ; 6 pattern slots a part
        ld (V_PAT),a
        ld a,6
        jr .cap
.ex:    sub 16
        add a,a
        add a,a
        add a,96                ; 4 pattern slots an extra
        ld (V_PAT),a
        ld a,4
.cap:   cp c
        jr c,drop               ; too big for its slots
        ld a,(V_PI)
        add a,a
        ld l,a
        ld h,high HELD
        ld de,(V_G)
        ld a,(hl)
        cp e
        jr nz,.up
        inc l
        ld a,(hl)
        dec l
        cp d
        jr z,show
.up:    ld (hl),0               ; not held until the upload is done
        inc l
        ld (hl),0
        dec l
        push hl
        call upload
        pop hl
        jr c,drop
        ld de,(V_G)
        ld (hl),e
        inc l
        ld (hl),d
        jr show

drop:   ld hl,(V_DROP)
        inc hl
        ld (V_DROP),hl
        ret

show:   ld hl,(V_REC)
        ld a,(hl)
        ld e,a
        rla
        sbc a,a
        ld d,a                  ; DE = x column, signed
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,31
        add hl,bc
        ld (V_X),hl             ; one left of the graphic: the outline's margin
        ex de,hl
        inc hl
        ld a,(hl)
        add a,31
        ld (V_Y),a
        ld a,(V_PAT)
        ld (V_TP),a
        ld a,(V_ROWS)
        ld (V_RW),a
.row:   xor a
        ld (V_C),a
.col:   ld a,(V_N)
        cp MAXSPR
        jr nc,drop
        inc a
        ld (V_N),a
        dec a
        nextreg 0x34,a
        ld hl,(V_X)
        ld a,(V_FL)
        rra
        jr nc,.plain
        ld a,(V_W)              ; mirrored: this tile column ends W * 8 - 16 * C from the left edge
        add a,a
        add a,a
        add a,a
        add a,l
        ld l,a
        ld a,0
        adc a,h
        ld h,a
        inc hl                  ; the tiles are mirrored with the margin: 2 right of the plain origin
        inc hl
        ld de,-16
        add hl,de
        ld a,(V_C)
        or a
        jr z,.x
        ld b,a
.xm:    add hl,de
        djnz .xm
        jr .x
.plain: ld a,(V_C)
        or a
        jr z,.x
        ld b,a
        ld de,16
.xp:    add hl,de
        djnz .xp
.x:     ld a,l
        nextreg 0x35,a
        ld a,(V_Y)
        nextreg 0x36,a
        ld a,h
        and 1
        ld b,a
        ld a,(V_FL)
        and 1
        add a,a
        add a,a
        add a,a
        or b
        nextreg 0x37,a
        ld a,(V_TP)
        ld c,a
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        inc c
        ld a,c
        ld (V_TP),a
        ld hl,V_C
        inc (hl)
        ld a,(V_COLS)
        cp (hl)
        jp nz,.col
        ld a,(V_Y)
        add a,16
        ld (V_Y),a
        ld hl,V_RW
        dec (hl)
        jp nz,.row
        ret

; find (V_G, checksum) and send its patterns to V_PAT. Carry: not in the table.
upload: ld hl,0
        ld a,(V_R)
        ld e,a
        ld d,0
        ld a,(V_W)
        ld b,a
.mu:    add hl,de
        djnz .mu
        add hl,hl
        inc hl
        inc hl
        ld b,h
        ld c,l                  ; BC = 2 + 2WR
        ld hl,(V_G)
        ld de,0
.s:     ld a,(hl)
        add a,e
        ld e,a
        jr nc,.nc
        inc d
.nc:    inc hl
        dec bc
        ld a,b
        or c
        jr nz,.s
        ld (V_SUM),de
        ld hl,(V_G)             ; slot = (lo + 2 hi + sum lo + 8 sum hi) & 511
        ld c,h
        ld b,0
        sla c
        rl b
        ld h,0
        add hl,bc
        ld c,e
        ld b,0
        add hl,bc
        ld c,d
        ld b,0
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        add hl,bc
        ld a,h
        and 1
        ld h,a
        ld b,h
        ld c,l
        add hl,hl
        add hl,bc
        add hl,hl
        ld bc,HASH
        add hl,bc
.probe: push hl
        ld de,4
        add hl,de
        ld a,(hl)
        pop hl
        or a
        jp z,byaddr             ; empty: not this address and checksum
        push hl
        ld de,(V_G)
        ld a,(hl)
        cp e
        jr nz,.next
        inc hl
        ld a,(hl)
        cp d
        jr nz,.next
        inc hl
        ld de,(V_SUM)
        ld a,(hl)
        cp e
        jr nz,.next
        inc hl
        ld a,(hl)
        cp d
        jr z,.found
.next:  pop hl
        ld de,6
        add hl,de
        ld a,h
        cp high HASHEND
        jr c,.probe
        ld hl,HASH
        jr .probe
.found: pop de                  ; the entry's start
send:   call dioff
        ld (V_IE),a
        inc hl
        ld a,(hl)
        nextreg 0x56,a          ; pattern page at slot 6
        inc hl
        ld a,(hl)
        and 0x3F                ; (the top bits are the level)
        ld l,0
        rra
        rr l
        or 0xC0
        ld h,a                  ; HL = 0xC000 + 128 * index
        ld a,(V_PAT)
        rrca                    ; pattern select: number / 2, half in bit 7
        ld bc,0x303B
        out (c),a
        ld a,(V_TILES)
        ld c,0x5B
.t:     ld b,128
        otir
        dec a
        jr nz,.t
        nextreg 0x56,0
        ld a,(V_IE)
        or a
        call nz,eion
        or a
        ret

; The game can poke a graphic in place (the last level: a stray object at 0xC017 sets bits at 0xC01C-0xC01E), and then the checksum
; finds nothing. A figure must not vanish for that: take this address's patterns, this level's if there are any. Counted in V_FB.
byaddr: ld a,(V_LV)
        ld c,a
        ld b,0
.pass:  ld hl,HASH
.f:     ld de,(V_G)
        ld a,(hl)
        cp e
        jr nz,.n
        inc hl
        ld a,(hl)
        dec hl
        cp d
        jr nz,.n
        ld a,b
        or a
        jr nz,.hit              ; second pass: any level
        push hl
        ld de,5
        add hl,de
        ld a,(hl)
        pop hl
        rlca
        rlca
        and 3
        cp c
        jr z,.hit
.n:     ld de,6
        add hl,de
        ld a,h
        cp high HASHEND
        jr c,.f
        inc b
        ld a,b
        cp 2
        jr c,.pass
        scf
        ret
.hit:   ld de,(V_FB)
        inc de
        ld (V_FB),de
        inc hl
        inc hl
        inc hl
        jp send
rom_end:

        ORG 0xD000
setup:  nextreg 0x54,20         ; alt ROM image 0, as target_renegade: the game starts with ROM 0 selected
        nextreg 0x55,24
        jp .alias - 0x4000
.alias: ld bc,0x243B            ; unlock 7FFD paging (NextReg $08 bit 7)
        ld a,8
        out (c),a
        inc b
        in a,(c)
        or 0x80
        nextreg 0x08,a
        ld bc,0x1FFD
        xor a
        out (c),a
        ld b,0x7F
        out (c),a
        nextreg 0x8C,0xC0       ; write mode: reads ROM, writes the image
        ld hl,0
        ld de,0
        ld bc,0x4000
        ldir
        ld hl,0xA000+0x186E
        ld de,0x386E
        ld bc,rom_end+20-0x386E
        ldir
        nextreg 0x8C,0
        nextreg 0x56,20
        nextreg 0x57,21
        jp .back
.back:  nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
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
        nextreg 0x1C,2          ; sprite clip window: the play area, as the game clips to line 135
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,135
        nextreg 0x15,0x01
        ret
pal:    DB 0x00,0x00,0xFC,0xFF,0xA0,0xA2,0x14,0x16      ; 0 clear, 1 black, 2 the body, 3 the outline (both per level), 4-15 fixed colours for painted pixels
        DB 0xB4,0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0x02
setup_end:

        SAVEBIN "r8_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "r8_setup.bin",0xD000,setup_end-0xD000
