; CPC section 1 lives in bank 21 at its original $4000 addresses during setup.
; All patterns are permanent. Drawing costs attribute writes only.
        ORG $D800
cpc_gate:
        nextreg $53,25
        call cpc_draw
        nextreg $53,11
        ret
cpc_gate_end:

        ORG $3b00
cpc_tick:
        call hide
        nextreg $53,25
        call cpc_objects
        nextreg $53,11
        ret
cpc_tick_end:

        ORG $6000
cpc_draw:
        push ix
        ld hl,(gfx)
        ld a,(w)
        rrca
        rrca
        rrca
        ld b,a
        ld a,(rows)
        or b
        ld c,a                  ; packed Spectrum width/row count
        ; The game reuses left-facing image addresses for several actions.
        ; Resolve its paired player draws from the action, facing and leg phase.
        ld a,h
        cp $c0
        jp c,.lookup
        cp $dd
        jp nc,.lookup
        ld a,($b405)
        cp 3
        jr z,.tumble
        cp 1
        jr z,.paired
        cp 5
        jp nz,.lookup
.paired:
        ld a,($b406)
        and 7
        ld l,a
        ld a,($b400)
        bit 0,a
        jr nz,.phase
        set 3,l
.phase: ld h,1                  ; legs
        ld a,(w)
        cp 4
        jr nz,.upper
        ld a,($b3f5)
        or a
        jr nz,.key
        ld a,($b400)
        cp 3
        jr c,.key
        set 4,l                 ; diagonal hip and shoulder share the shift
        cp 5
        jr c,.key
        set 5,l
        jr .key
.upper: inc h                   ; relaxed upper
        ld a,($b3f5)
        or a
        jr nz,.key
        ld a,($b400)
        inc a
        srl a                   ; 1 level, 2 diagonal up, 3 diagonal down
        add a,h
        ld h,a
.key:   ld c,1
        jr .lookup
.tumble:
        ld a,h
        ld h,6
        cp $d8
        jr c,.turn
        cp $da
        jr nc,.turn
        ld a,l
        cp $90
        ld l,0
        jr c,.tindex
        inc l
.tindex: ld a,(gfx+1)
        cp $d9
        jr nz,.turn2
        ld a,(gfx)
        cp $b0
        ld l,2
        jr c,.turn2
        inc l
        jr .turn2
.turn:  ld l,0
.turn2: ld a,($b3e1)
        or a
        jr z,.facing
        ld a,l
        cp 3
        jr nz,.facing
        ld l,4                  ; fallen commando
.facing:
        ld a,($b42f+1)
        cp $cb
        jr nz,.key
        set 3,l
        jr .key
.lookup: ld a,h
        ld e,a
        ld d,0
        ld ix,cpc_index
        add ix,de
        add ix,de
        ld e,(ix+0)
        ld d,(ix+1)
        ex de,hl                ; HL = rows for this graphics high byte, E = low byte
.find:  ld a,(hl)
        inc hl
        or a
        jr z,.done              ; end marker (shape cannot be zero)
        cp c
        jr nz,.skip
        ld a,(hl)
        cp e
        jr z,.found
.skip:  push de
        ld de,7
        add hl,de
        pop de
        jr .find
.done:  pop ix
        ret
.found: inc hl
        push hl
        pop ix                  ; pattern, columns, tile rows, x, y, flags
        ld a,d
        cp 7
        jr z,.base_ready
        ld a,(scr)
        and 31
        ld l,a
        ld a,(skip)
        ld b,a
        ld a,l
        sub b
        add a,4
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld (xbase),hl
        ld a,(scr+1)
        ld b,a
        and $18
        rlca
        rlca
        rlca
        ld c,a
        ld a,b
        and 7
        or c
        ld c,a
        ld a,(scr)
        and $e0
        rrca
        rrca
        or c
        add a,32
        ld (ybase),a
.base_ready:
        ld hl,(xbase)
        ld e,(ix+3)
        ld a,e
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld (xbase),hl
        ld a,(ybase)
        add a,(ix+4)
        ld c,a                  ; y
        ld d,(ix+0)             ; pattern in 128-byte units
        ld e,(ix+2)
.row:   ld hl,(xbase)
        ld b,(ix+1)
.col:   ld a,(nsp)
        cp NMAX
        jr nc,.done
        nextreg $34,a
        inc a
        ld (nsp),a
        ld a,l
        nextreg $35,a
        ld a,c
        nextreg $36,a
        ld a,h
        and 1
        or (ix+5)
        nextreg $37,a
        ld a,d
        srl a
        or $c0
        nextreg $38,a
        ld a,d
        and 1
        rrca
        rrca
        or $88                  ; four-bit, 2x horizontal, 1x vertical
        nextreg $39,a
        inc d
        push de
        ld de,32
        bit 3,(ix+5)
        jr z,.right
        ld de,-32
.right: add hl,de
        pop de
        djnz .col
        ld a,c
        add a,16
        ld c,a
        dec e
        jr nz,.row
        jp .done
; Wall objects are drawn before figures. The game still updates the ULA
; rock and reads its eye masks. Use its object records and opening phase.
cpc_objects:
        push ix
        push iy
        ld ix,$b6f7
        ld iy,$b411
        ld b,4
.loop:  push bc
        ld a,(ix+1)
        cp $80
        jr c,.visible
        cp $f0
        jr c,.next
.visible:
        ld l,a
        add a,a
        sbc a,a
        ld h,a
        add hl,hl
        ld de,32
        add hl,de
        ld (xbase),hl
        ld a,(ix+0)
        add a,32
        ld (ybase),a
        ld a,(ix+3)
        cp $df
        jr nz,.gun
        ld a,(ix+2)
        cp $c0
        jr nz,.next
        ld l,10                 ; closed store, consumed when the game marks it collected
        jr .draw
.gun:   cp $e1
        jr nz,.next
        ld a,(ix+2)
        cp $40
        jr nz,.next
        ld a,(iy+1)
        cp 10
        jr nc,.next
        ld l,a
.draw:  ld h,7
        ld c,1
        call .emit
.next:  ld de,8
        add ix,de
        inc iy
        inc iy
        pop bc
        djnz .loop
        pop iy
        pop ix
        ret
.emit:  push ix
        jp cpc_draw.lookup
cpc_index:

; Setup runs on the boot bank stack. Scratch is private to this bank.
cpc_exposed EQU $f000
canvas  EQU $E800               ; 32 bytes/row, logical (0,0) at (16,32)
        ORG $D000
cpc_boot:
        nextreg 7,3
        nextreg $52,42
        nextreg $53,43
        nextreg $4b,0
        nextreg $43,$20
        nextreg $40,0
        ld hl,cpc_inks
        ld b,32
.ink:   ld a,(hl)
        inc hl
        nextreg $44,a
        djnz .ink
        xor a
.hide:  nextreg $34,a
        nextreg $38,0
        inc a
        cp 128
        jr nz,.hide
        xor a
        ld bc,$303b
        out (c),a
        ld ix,cpc_templates
.next:  ld l,(ix+0)
        ld h,(ix+1)
        ld a,h
        or a
        jr z,.finish
        push hl
        ld hl,canvas
        ld de,canvas+1
        ld bc,32*64-1
        ld (hl),0
        ldir
        pop hl
        call cpc_compose
        ld l,(ix+2)
        ld h,(ix+3)
        ld a,h
        or a
        call nz,cpc_compose
        ; start of the requested rectangle in the composed canvas
        ld a,(ix+5)
        add a,32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,canvas+16
        add hl,de
        ld e,(ix+4)
        ld a,e
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld e,(ix+7)             ; remaining visible lines
.tiles: push hl
        ld d,(ix+6)
.tile:  push hl
        ld b,16
        ld a,e
.line:  push bc
        ld bc,$085b
        or a
        jr z,.pad
        dec a
        otir
        jr .step
.pad:   push af
        xor a
.zero:  out (c),a
        djnz .zero
        pop af
        ld bc,8
        add hl,bc
.step:  ld bc,24
        add hl,bc
        pop bc
        djnz .line
        pop hl
        ld bc,8
        add hl,bc
        dec d
        jr nz,.tile
        pop hl
        ld bc,512
        add hl,bc
        ld a,e
        sub 16
        ld e,a
        jr z,.advance
        jr nc,.tiles
.advance:
        ld bc,9
        add ix,bc
        jp .next
.finish:
        nextreg $52,10
        nextreg $53,11
        nextreg $1c,2
        nextreg $19,0
        nextreg $19,255
        nextreg $19,0
        nextreg $19,167
        nextreg $15,1
        nextreg 7,0
        ret

; HL = CPC pose list. A source zero nibble preserves earlier pieces.
cpc_compose:
        ld a,(hl)
        cp $80
        ret z
        ld c,a                  ; signed x in bytes
        inc hl
        ld a,32
        sub (hl)                ; bottom line relative to canvas top
        inc hl
        ld e,(hl)
        inc hl
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,c
        add a,16
        ld c,a
        ld b,high canvas
        add hl,bc               ; destination bottom left
        push hl
        xor a
        ld (cpc_exposed),a
        ld a,(ix+8)             ; CPC emerging descriptor, reconstructed from its master
        or a
        jr z,.descriptor
        ld a,e
        cp $a1
        jr nz,.pop
        ld e,$e4
        jr .expose
.pop:   cp $9e
        jr nz,.descriptor
        ld e,$c8
.expose: ld a,(ix+8)
        ld (cpc_exposed),a
.descriptor:
        ld d,0
        ex de,hl
        add hl,hl
        add hl,hl
        ld de,$4cc7
        add hl,de
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(cpc_exposed)
        or a
        jr z,.pixels
        ld a,b
        sub (ix+8)
        jr z,.short
        push hl
        ld l,c
        ld h,0
.seek:  add hl,de
        ex de,hl
        ld l,c
        ld h,0
        dec a
        jr nz,.seek
        pop hl
.short: ld b,(ix+8)
.pixels:pop hl
.row:   push bc
        push hl
        ld b,c
.byte:  ld a,(de)
        inc de
        push hl
        ld l,a
        ld h,high cpc_mode0
        ld a,(hl)
        pop hl
        ld c,a
        and $f0
        jr nz,.left
        ld a,(hl)
        and $f0
.left:  push af
        ld a,c
        and $0f
        jr nz,.right
        ld a,(hl)
        and $0f
.right: ld c,a
        pop af
        or c
        ld (hl),a
        inc hl
        djnz .byte
        pop hl
        ld bc,-32
        add hl,bc
        pop bc
        djnz .row
        pop hl
        jp cpc_compose

        ALIGN 256
cpc_mode0:
        DUP 256,n
        db ((n & $80)>>3) | ((n & 8)<<2) | ((n & $20)<<1) | ((n & 2)<<6) | ((n & $40)>>6) | ((n & 4)>>1) | ((n & $10)>>2) | ((n & 1)<<3)
        EDUP
cpc_inks:
        ; RGB333 words as the two consecutive NextReg $44 writes.
        db 2,0,254,0,255,1,0,0,146,0,16,0,156,0,18,0
        db 31,1,144,0,3,1,19,1,242,0,240,0,128,0,224,0
cpc_templates:
