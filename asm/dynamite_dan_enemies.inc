; The 48 room pages plus the menu start at MMU page 32. Each page holds
; record-to-group offsets, eight plot descriptors per group, and 8-bit tiles.
; Slot 2 is normally ULA bank 5 (page 10). No game stack or enemy records
; are in this window. Restore it before executing the displaced instruction.
        MACRO enemy_entry
        push af
        ld a,r
        push af
        push bc
        push de
        push hl
        ld bc,$243b
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 7,3
        ld a,iyh
        cp $ca                  ; menu records CA3D, CA43, CA4B
        ld a,48
        jr z,$+5
        ld a,(ROOM)
        add a,32
        nextreg $52,a
        ENDM
        MACRO enemy_exit
        nextreg $52,10
        pop af
        nextreg 7,a
        pop hl
        pop de
        pop bc
        pop af
        RSET D_DAN
        pop af
        ENDM

; Upload once on entering a room. The game runs its complete ULA setup next.
e_room: enemy_entry
        ld a,27
        ld bc,$303b
        out (c),a
        ld hl,$4400
        ld a,($4000)
        or a
        jr z,.done
        ld d,a
        ld c,$5b
.tile:  ld b,0
        otir
        dec d
        jr nz,.tile
.done:  enemy_exit
        ld a,(iy+0)
        jp $e550

; IY records have an eight-byte stride. Return L = record number, C = first slot.
record_slot:
        ld a,($4001)
        ld b,a
        ld a,iyl
        sub b
        rrca
        rrca
        rrca
        ld l,a
        add a,a
        add a,a
        add a,11
        ld c,a
        ret

e_enemy: enemy_entry
        call record_slot
        bit 6,(iy+4)
        jr nz,.done             ; killed: ULA plotter suppresses its writes
        ld h,$40
        inc l
        inc l
        ld b,(hl)               ; group * 8
        ld a,(iy+4)
        and 7
        add a,b
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,$41
        ld h,a
        ld b,(hl)               ; descriptor: count, X mirror, then dx,dy,pattern
        inc hl
        ld a,(hl)
        push ix
        ld ixl,a
        inc hl
        ld a,d
        add a,a
        add a,a
        add a,a
        ld d,a
        ld a,e
        add a,a
        add a,a
        add a,a
        ld e,a
.tile:  ld a,c
        nextreg $34,a
        ld a,d
        add a,(hl)              ; dx includes the 32px border
        nextreg $35,a
        ld a,ixl
        adc a,0
        nextreg $37,a
        inc hl
        ld a,e
        add a,(hl)
        nextreg $36,a
        inc hl
        ld a,(hl)
        nextreg $38,a           ; 4-byte attributes, 8-bit anchor
        inc hl
        inc c
        djnz .tile
        pop ix
.done:  enemy_exit
        push bc
        bit 6,(iy+4)
        jp $e970

; The collision handler erases the enemy's box immediately, before next tick.
e_erase: enemy_entry
        call record_slot
        ld b,4
.hide:  ld a,c
        nextreg $34,a
        nextreg $38,0
        inc c
        djnz .hide
        enemy_exit
        set 6,(iy+4)
        jp $d2eb

; A global sprite clip would also cut enemies below Dan. Only on sinking,
; mask the partial 16-row tile in slot 26 and hide the tile below it.
clip_dan:
        ld a,(DAN_ROWS)
        cp 13
        ret nc
        add a,a
        sub 2                   ; Dan's first pattern starts at plot row 2
        ld b,a
        ld a,(DAN_FR)
        add a,a
        ld h,a
        xor a
        nextreg $34,1
        ld a,b
        sub 16
        jr c,.top
        inc h
        jr .partial
.top:   nextreg $38,0
        nextreg $34,0
        ld a,b
.partial:
        or a
        jr nz,.copy
        nextreg $38,0
        ret
.copy:  swapnib                 ; 16 bytes per row
        ld b,a
        ld a,h
        add a,$40
        ld h,a
        ld l,0
        nextreg $52,22
        push bc
        ld bc,$303b
        ld a,26
        out (c),a
        pop bc
        ld a,b
        neg
        ld c,$5b
        otir
        ld b,a
        ld a,$e3
.fill:  out (c),a
        djnz .fill
        nextreg $52,10
        ; The pattern-select port also selects attribute slot 26.
        ld a,(DAN_ROWS)
        cp 9
        ld a,0
        jr c,$+3
        inc a
        nextreg $34,a
        nextreg $38,$da
        ret

; Repay the plot hooks out of the tick's counted idle loop. Blocks of 32
; iterations have 128 M1 fetches, so the original R is still reached. BC is
; supplied by the game (0400 or 03FF with define keys). No-enemies skips
; repayment because its RET at E592 also skips all the game-time plot hooks.
e_delay:
        push af
        ld a,r
        push af
        ld a,($e592)
        cp $c9
        jr z,.go
        ld a,(ROOM)
        add a,32
        nextreg $52,a
        ld a,($400c)            ; room repayment, zero in an empty room
        nextreg $52,10
        push de
        ld e,a
        ld a,c
        sub e
        ld c,a
        ld a,b
        sbc a,0
        ld b,a
        pop de
.go:    pop af
        RSET D_DAN
        pop af
        call $d4af
        jp $c83a
