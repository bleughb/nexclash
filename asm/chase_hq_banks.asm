; Chase H.Q. (128K): the Enhanced code that runs from Next banks 8 and 28 (mapped at 0x4000 by the hidden-ROM hooks,
; asm/chase_hq_hooks.asm). Five separately assembled units, one MODULE each so their state EQUs stay apart; each
; SAVEBIN runs before the next unit overwrites its addresses. nexclash/chase_hq.py places the blocks.
        DEVICE ZXSPECTRUMNEXT
; ---- player steering views (bank 28 + 0x0000)
        MODULE chq_steer
S_SP        EQU 0x1D30
S_R         EQU 0x1D32
S_MAP2      EQU 0x1D33
S_MAP3      EQU 0x1D34
S_MAP4      EQU 0x1D35
S_ACTIVE    EQU 0x1D36
S_ANGLE     EQU 0x1D37
S_TARGET    EQU 0x1D38
S_VALID     EQU 0x1D39
S_REQ       EQU 0x1D3A
S_BOUNCE    EQU 0x1D3B
S_PAGE      EQU 0x1D3C
S_COUNT     EQU 0x1D3D
S_INIT      EQU 0x1D3E
S_FRAME     EQU 0x1D40
S_BACKUP    EQU 0x1800
S_STACK     EQU 0x1BE0

E_INIT      EQU 0x1D81
E_BACK      EQU 0x1D80
        ORG 0x4000
        jp steering_pre
        jp steering_post
steering_pre:
        xor a
        ld (S_ACTIVE),a
        ld a,(E_INIT)
        or a
        jp z,.fallback
        ld (S_INIT),a
        ld a,(0xB5AB)        ; jumping/vertical displacement uses the old drawing
        ld b,a
        ld a,(0xA22A)
        or b
        ld b,a
        ld a,(0xA22F)        ; special crash sequence
        or b
        ld b,a
        ld a,(0xB064)        ; scripted collision/bounce sequence
        or b
        jp nz,.fallback
        ld a,(S_STACK-1)    ; original A: normal steering pose, 0..2
        cp 3
        jp nc,.fallback
        add a,a
        ld b,a
        ld a,(0xA251)
        or a
        ld a,4
        jr nz,.right
        sub b
        jr .target
.right: add a,b
.target:
        ld (S_REQ),a
        ld a,(S_STACK-3)    ; original B: normal wheel/bounce phase, 0 or 3
        ld b,a
        ld a,(0xB5B0)       ; source table's self-modified phase offset
        add a,b
        cp 9
        jr c,.mod
        sub 9
.mod:   cp 9
        jp nc,.fallback
        sub 6
        jr nc,.phase
        add a,9
.phase: or a
        ld b,0
        jr z,.phase_done
        cp 3
        ld b,1
        jr z,.phase_done
        cp 6
        jp nz,.fallback
        ld b,2
.phase_done:
        ld a,b
        ld (S_BOUNCE),a
        ld a,(S_REQ)
        ld b,a
        ld a,(S_VALID)
        or a
        jr z,.direct
        ld a,(S_TARGET)
        cp b
        jr z,.direct
        ld a,(S_ANGLE)
        add a,b
        srl a               ; one update at the halfway angle; no physics delay
        jr .chosen
.direct:ld a,b
.chosen:
        ld (S_ANGLE),a
        ld a,b
        ld (S_TARGET),a
        ld a,1
        ld (S_VALID),a
        ld (S_ACTIVE),a
        xor a
        ld (E_INIT),a       ; suppress only this car's old colour rows
        ; Preserve the 64x40 original bitmap rectangle before the original body.
        ld hl,0xF8AC        ; x=96, y=88 in the game's swizzled bitmap
        ld de,S_BACKUP
        ld a,40
        ld (S_COUNT),a
.save:  push hl
        ld bc,8
        ldir
        pop hl
        inc h
        jr nz,.save_next
        ld h,0xF0
        ld a,l
        add a,32
        ld l,a
.save_next:
        ld a,(S_COUNT)
        dec a
        ld (S_COUNT),a
        jr nz,.save
        ret
.fallback:
        xor a
        ld (S_VALID),a
        ret
steering_post:
        ld a,(S_ACTIVE)
        or a
        ret z
        ld a,(S_INIT)
        ld (E_INIT),a
        ; The original body still ran with its original registers and RAM side
        ; effects. Undo only its display pixels: the new car lives in Layer 2.
        ld hl,S_BACKUP
        ld de,0xF8AC
        ld a,40
        ld (S_COUNT),a
.restore:
        push de
        ld bc,8
        ldir
        pop de
        inc d
        jr nz,.restore_next
        ld d,0xF0
        ld a,e
        add a,32
        ld e,a
.restore_next:
        ld a,(S_COUNT)
        dec a
        ld (S_COUNT),a
        jr nz,.restore
        ld a,(S_BOUNCE)
        ld b,a
        add a,a
        add a,a
        add a,a
        add a,b             ; bounce * 9
        ld b,a
        ld a,(S_ANGLE)
        add a,b             ; frame 0..26, each occupies half an 8K page
        ld (S_FRAME),a
        srl a
        add a,58
        nextreg 0x53,a
        ld a,(S_FRAME)
        and 1
        rlca
        rlca
        rlca
        rlca
        or 0x60
        ld h,a
        ld l,0
        ld a,(E_BACK)
        add a,4             ; playfield y=88: 64 lines into its 128-line area
        ld (S_PAGE),a
        nextreg 0x54,a
        ld de,0x9860        ; y within page 24, x=96
        ld a,40
        ld (S_COUNT),a
.row:   xor a               ; palette 0 means transparent; no colour blending
        DUP 64
          ldix
        EDUP
        ld e,96
        inc d
        ld a,d
        cp 0xA0
        jr c,.samepage
        ld d,0x80
        ld a,(S_PAGE)
        inc a
        ld (S_PAGE),a
        nextreg 0x54,a
.samepage:
        ld a,(S_COUNT)
        dec a
        ld (S_COUNT),a
        jp nz,.row
        xor a
        ld (S_ACTIVE),a
        ret
steering_code_end:
        ASSERT steering_code_end < 0x6000
        SAVEBIN "banks_steering.bin",0x4000,steering_code_end-0x4000
        ENDMODULE
; ---- Enhanced row plotter over the original renderer (bank 28 + 0x0800)
        MODULE chq_row
A_MAP4      EQU 0x1D50
A_STAGE     EQU 0x1D51
A_SOURCE    EQU 0x1D52
A_DEST      EQU 0x1D54
A_FLAG      EQU 0x1D56
A_LOOKUP    EQU 0x1D57
A_CPAGE     EQU 0x1D58
A_CPTR      EQU 0x1D59
A_CACHED    EQU 0x1D5B
A_MAP5      EQU 0x1D5C
A_CMAP3     EQU 0x1D5D
A_COPYINDEX EQU 0x1D5E
A_LPTR      EQU 0x1D60
A_COUNT     EQU 0x1D62

E_DEST EQU 7430
E_SP EQU 7424
E_MASKED EQU 7433
E_MIRROR EQU 7434
E_WIDTH EQU 7432
E_SOURCE EQU 7436
E_BACK EQU 7552
ASSET_RECORD_PAGE EQU 72
ASSET_CACHE_PAGE EQU 156
        ORG 0x4800
assets_row:
        ld hl,(E_DEST)
        push hl
        pop ix
        ld a,h
        cp 0xF0
        ret c
        and 15
        ld d,a
        ld a,l
        and 224
        rrca
        or d
        ld d,a
        and 96
        rlca
        rlca
        rlca
        ld e,a
        ld a,(E_BACK)
        add a,2
        add a,e
        nextreg 0x53,a
        ld a,l
        and 31
        rlca
        rlca
        rlca
        ld e,a
        ld a,d
        and 31
        or 0x60
        ld d,a
        ld hl,(E_SP)
        ld a,(E_MASKED)
        cp 3
        jr nz,.ordinary_source
        ld hl,(E_SOURCE)
        jr .source
.ordinary_source:
        cp 1
        jr nz,.source
        inc hl
.source:ld (A_SOURCE),hl
        call .choose_cache
.byte:
        ld a,(A_CPAGE)
        or a
        jr z,.dictionary
        jr .cached_record
.dictionary:
        ld a,(E_MASKED)
        cp 2
        jr z,.constant
        ld a,(A_STAGE)
        dec a
        and 7
        rlca
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,(E_MASKED)
        cp 1
        ld a,0
        jr nz,.raw_lookup
        inc a
.raw_lookup:
        rlca
        rlca
        rlca
        rlca
        or b
        ld (A_LOOKUP),a
        push de
        ld hl,(A_SOURCE)
        ld a,h
        rrca
        rrca
        rrca
        rrca
        and 15
        ld c,a
        ld a,(A_LOOKUP)
        or c
        ld c,a
        ld b,0
        push hl
        ld hl,asset_lookup_pages
        add hl,bc
        ld a,(hl)
        nextreg 0x54,a
        pop hl
        ld a,h
        and 15
        ld h,a
        add hl,hl
        set 7,h
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        ld a,h
        srl a
        add a,ASSET_RECORD_PAGE
        cp 88
        jr c,.record_page
        add a,4             ; banks 46/47 hold the full original-ROM images
.record_page:
        nextreg 0x54,a
        ld a,h
        and 1
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        pop de
.cached_record:
        ld b,(hl)
        ld a,l
        add a,8
        ld l,a
        jr .draw
.constant:
        nextreg 0x54,28
        ld hl,(E_SOURCE)
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ld b,0
.draw:
        ld a,(E_MIRROR)
        or a
        jr nz,.reverse
        ld a,b
        or a
        jr nz,.slow_forward
        xor a
        DUP 8
          ldix
        EDUP
        jp .advance
.reverse:
        ld a,l
        add a,7
        ld l,a
        ld a,b
        or a
        jp nz,.slow_reverse
        xor a
        DUP 8
          lddx
        EDUP
        jp .reverse_done
.slow_forward:
        ld b,(ix+0)
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward0_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward0_skip
        bit 7,b
        jr nz,.forward0_black
        cp 2
        jr z,.forward0_green
        add a,244
        jr .forward0_put
.forward0_green:
        ld a,249
        jr .forward0_put
.forward0_black:
        ld a,1
.forward0_put:
        ld (de),a
.forward0_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward1_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward1_skip
        bit 6,b
        jr nz,.forward1_black
        cp 2
        jr z,.forward1_green
        add a,244
        jr .forward1_put
.forward1_green:
        ld a,249
        jr .forward1_put
.forward1_black:
        ld a,1
.forward1_put:
        ld (de),a
.forward1_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward2_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward2_skip
        bit 5,b
        jr nz,.forward2_black
        cp 2
        jr z,.forward2_green
        add a,244
        jr .forward2_put
.forward2_green:
        ld a,249
        jr .forward2_put
.forward2_black:
        ld a,1
.forward2_put:
        ld (de),a
.forward2_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward3_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward3_skip
        bit 4,b
        jr nz,.forward3_black
        cp 2
        jr z,.forward3_green
        add a,244
        jr .forward3_put
.forward3_green:
        ld a,249
        jr .forward3_put
.forward3_black:
        ld a,1
.forward3_put:
        ld (de),a
.forward3_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward4_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward4_skip
        bit 3,b
        jr nz,.forward4_black
        cp 2
        jr z,.forward4_green
        add a,244
        jr .forward4_put
.forward4_green:
        ld a,249
        jr .forward4_put
.forward4_black:
        ld a,1
.forward4_put:
        ld (de),a
.forward4_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward5_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward5_skip
        bit 2,b
        jr nz,.forward5_black
        cp 2
        jr z,.forward5_green
        add a,244
        jr .forward5_put
.forward5_green:
        ld a,249
        jr .forward5_put
.forward5_black:
        ld a,1
.forward5_put:
        ld (de),a
.forward5_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward6_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward6_skip
        bit 1,b
        jr nz,.forward6_black
        cp 2
        jr z,.forward6_green
        add a,244
        jr .forward6_put
.forward6_green:
        ld a,249
        jr .forward6_put
.forward6_black:
        ld a,1
.forward6_put:
        ld (de),a
.forward6_skip:
        inc de
        ld a,(hl)
        inc hl
        or a
        jr nz,.forward7_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.forward7_skip
        bit 0,b
        jr nz,.forward7_black
        cp 2
        jr z,.forward7_green
        add a,244
        jr .forward7_put
.forward7_green:
        ld a,249
        jr .forward7_put
.forward7_black:
        ld a,1
.forward7_put:
        ld (de),a
.forward7_skip:
        inc de
        jp .advance
.slow_reverse:
        ld b,(ix+0)
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse0_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse0_skip
        bit 7,b
        jr nz,.reverse0_black
        cp 2
        jr z,.reverse0_green
        add a,244
        jr .reverse0_put
.reverse0_green:
        ld a,249
        jr .reverse0_put
.reverse0_black:
        ld a,1
.reverse0_put:
        ld (de),a
.reverse0_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse1_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse1_skip
        bit 6,b
        jr nz,.reverse1_black
        cp 2
        jr z,.reverse1_green
        add a,244
        jr .reverse1_put
.reverse1_green:
        ld a,249
        jr .reverse1_put
.reverse1_black:
        ld a,1
.reverse1_put:
        ld (de),a
.reverse1_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse2_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse2_skip
        bit 5,b
        jr nz,.reverse2_black
        cp 2
        jr z,.reverse2_green
        add a,244
        jr .reverse2_put
.reverse2_green:
        ld a,249
        jr .reverse2_put
.reverse2_black:
        ld a,1
.reverse2_put:
        ld (de),a
.reverse2_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse3_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse3_skip
        bit 4,b
        jr nz,.reverse3_black
        cp 2
        jr z,.reverse3_green
        add a,244
        jr .reverse3_put
.reverse3_green:
        ld a,249
        jr .reverse3_put
.reverse3_black:
        ld a,1
.reverse3_put:
        ld (de),a
.reverse3_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse4_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse4_skip
        bit 3,b
        jr nz,.reverse4_black
        cp 2
        jr z,.reverse4_green
        add a,244
        jr .reverse4_put
.reverse4_green:
        ld a,249
        jr .reverse4_put
.reverse4_black:
        ld a,1
.reverse4_put:
        ld (de),a
.reverse4_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse5_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse5_skip
        bit 2,b
        jr nz,.reverse5_black
        cp 2
        jr z,.reverse5_green
        add a,244
        jr .reverse5_put
.reverse5_green:
        ld a,249
        jr .reverse5_put
.reverse5_black:
        ld a,1
.reverse5_put:
        ld (de),a
.reverse5_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse6_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse6_skip
        bit 1,b
        jr nz,.reverse6_black
        cp 2
        jr z,.reverse6_green
        add a,244
        jr .reverse6_put
.reverse6_green:
        ld a,249
        jr .reverse6_put
.reverse6_black:
        ld a,1
.reverse6_put:
        ld (de),a
.reverse6_skip:
        inc de
        ld a,(hl)
        dec hl
        or a
        jr nz,.reverse7_put
        ld a,(de)
        sub 246
        cp 3
        jr nc,.reverse7_skip
        bit 0,b
        jr nz,.reverse7_black
        cp 2
        jr z,.reverse7_green
        add a,244
        jr .reverse7_put
.reverse7_green:
        ld a,249
        jr .reverse7_put
.reverse7_black:
        ld a,1
.reverse7_put:
        ld (de),a
.reverse7_skip:
        inc de
.reverse_done:
        ld bc,9
        add hl,bc
        ld a,e
        sub 16
        ld e,a
        dec ixl
        jr .next_count
.advance:
        inc ixl
.next_count:
        ld a,(E_WIDTH)
        dec a
        ld (E_WIDTH),a
        ret z
        ld a,(A_CPAGE)
        or a
        jr z,.uncached_next
        ld a,(E_MASKED)
        cp 1
        jr nz,.cache_next
        ld bc,16
        add hl,bc
.cache_next:
        bit 5,h
        jp z,.cached_record
        ; A_SOURCE holds the starting address of this 512-byte source chunk.
        ; Only reconstruct it when the cached colour pointer crosses a page.
        ld hl,(A_SOURCE)
        ld a,h
        and 254
        add a,2
        ld h,a
        ld a,(E_MASKED)
        cp 1
        ld a,0
        jr nz,.cross_raw
        ld a,l
        and 1
.cross_raw:
        ld l,a
        ld (A_SOURCE),hl
        call .choose_cache
        jp .byte
.uncached_next:
        ld hl,(A_SOURCE)
        inc hl
        ld a,(E_MASKED)
        cp 1
        jr nz,.next_source
        inc hl
.next_source:
        ld (A_SOURCE),hl
        jp .byte
.choose_cache:
        xor a
        ld (A_CPAGE),a
        ld a,(E_MASKED)
        cp 2
        ret z
        ld hl,(A_SOURCE)
        ld a,h
        srl a
        cp 46
        ret c
        cp 64
        jr c,.low_range
        cp 103
        ret c
        cp 112
        ret nc
        sub 85
        jr .cache_index
.low_range:
        sub 46
.cache_index:
        ld c,a
        ld a,(E_MASKED)
        cp 1
        ld a,c
        jr nz,.cache_raw
        add a,27
.cache_raw:
        add a,ASSET_CACHE_PAGE
        ld (A_CPAGE),a
        nextreg 0x54,a
        ld a,h
        and 1
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ld (A_CPTR),hl
        ret
; A transparent edited pixel must reveal the picture before the old figure was
; drawn. Resolve only low-priority background colours against that original byte.
; Already-painted foreground pixels retain their exact colour and priority.
.pixel:
        or a
        jr nz,.put
        ld a,(de)
        cp 246
        ret c
        cp 249
        ret nc
        bit 7,b
        jr nz,.black
        cp 248
        jr z,.green
        sub 2
        jr .put
.green: ld a,249
        jr .put
.black: ld a,1
.put:   ld (de),a
        ret
asset_lookup_pages:
        db 22,23,30,31,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131
        db 22,23,30,31,104,132,133,134,108,109,110,111,112,113,114,115,116,117,118,119,120,135,136,137,124,125,126,127,128,129,130,131
        db 22,23,30,31,104,138,139,140,108,109,110,111,112,113,114,115,116,117,118,119,120,141,142,143,124,125,126,127,128,129,130,131
        db 22,23,30,31,104,144,145,146,108,109,110,111,112,113,114,115,116,117,118,119,120,147,148,149,124,125,126,127,128,129,130,131
        db 22,23,30,31,104,150,151,152,108,109,110,111,112,113,114,115,116,117,118,119,120,153,154,155,124,125,126,127,128,129,130,131
        ASSERT $ < 0x5000
        ORG 0x5000
; Expand only the current stage. Initial cache banks are supplied by the NEX;
; subsequent stage loads rebuild them here, outside steady-state drawing.
assets_prepare:
        ld a,(A_STAGE)
        ld b,a
        ld a,(A_CACHED)
        cp b
        ret z
        ld bc,0x243B
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (A_CMAP3),a
        dec b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        ld (A_MAP4),a
        dec b
        ld a,0x55
        out (c),a
        inc b
        in a,(c)
        ld (A_MAP5),a
        xor a
        ld (A_COPYINDEX),a
.page:
        ld a,(A_COPYINDEX)
        add a,ASSET_CACHE_PAGE
        nextreg 0x55,a
        ld a,(A_COPYINDEX)
        ld b,0
        cp 27
        jr c,.raw
        sub 27
        ld b,16
.raw:   cp 18
        jr c,.low
        add a,39
.low:   add a,46
        ld c,a             ; original source page, 512 bytes per cache page
        srl a
        srl a
        srl a
        or b
        ld b,a
        ld a,(A_STAGE)
        dec a
        rlca
        rlca
        rlca
        rlca
        rlca
        or b
        push bc
        ld c,a
        ld b,0
        ld hl,asset_lookup_pages
        add hl,bc
        ld a,(hl)
        nextreg 0x53,a
        pop bc
        ld a,c
        and 7
        rlca
        rlca
        or 0x60
        ld h,a
        ld l,0
        ld (A_LPTR),hl
        ld hl,512
        ld (A_COUNT),hl
        ld de,0xA000
.record:
        push de
        ld hl,(A_LPTR)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (A_LPTR),hl
        ex de,hl
        ld a,h
        srl a
        add a,ASSET_RECORD_PAGE
        cp 88
        jr c,.mapped
        add a,4
.mapped:
        nextreg 0x54,a
        ld a,h
        and 1
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        pop de
        ld bc,16
        ldir
        ld hl,(A_COUNT)
        dec hl
        ld (A_COUNT),hl
        ld a,h
        or l
        jr nz,.record
        ld a,(A_COPYINDEX)
        inc a
        ld (A_COPYINDEX),a
        cp 54
        jp nz,.page
        ld a,(A_STAGE)
        ld (A_CACHED),a
        ld a,(A_CMAP3)
        nextreg 0x53,a
        ld a,(A_MAP4)
        nextreg 0x54,a
        ld a,(A_MAP5)
        nextreg 0x55,a
        ret
assets_row_end:
        ASSERT $ < 0x6000
        SAVEBIN "banks_row.bin",0x4800,assets_row_end-0x4800
        ENDMODULE
; ---- dashboard and horizon colours (bank 28 + 0x1400)
        MODULE chq_polish
A_MAP4      EQU 0x1D50
A_STAGE     EQU 0x1D51
A_SOURCE    EQU 0x1D52
A_DEST      EQU 0x1D54
A_FLAG      EQU 0x1D56
A_LOOKUP    EQU 0x1D57
A_CPAGE     EQU 0x1D58
A_CPTR      EQU 0x1D59
A_CACHED    EQU 0x1D5B
A_MAP5      EQU 0x1D5C
A_CMAP3     EQU 0x1D5D
A_COPYINDEX EQU 0x1D5E
A_LPTR      EQU 0x1D60
A_COUNT     EQU 0x1D62
; Source-keyed colour rows over the original renderer, in its original order.
; All writes go to an undisplayed Layer 2 buffer; commit follows the ULA copy.
E_SP        EQU 0x1D00
E_R         EQU 0x1D02
E_SPEED     EQU 0x1D03
E_MAP2      EQU 0x1D04
E_MAP3      EQU 0x1D05
E_DEST      EQU 0x1D06
E_WIDTH     EQU 0x1D08
E_MASKED    EQU 0x1D09
E_MIRROR    EQU 0x1D0A
E_PAGE      EQU 0x1D0B
E_SOURCE    EQU 0x1D0C
E_TICK      EQU 0x1D0E
E_PENDING   EQU 0x1D0F
E_FHEIGHT   EQU 0x1D10
E_FCOUNT    EQU 0x1D11
E_FDEST     EQU 0x1D12
E_FSPEED    EQU 0x1D14
E_PSRC      EQU 0x1D16
E_PDEST     EQU 0x1D18
E_PCOUNT    EQU 0x1D1A
E_SOLID     EQU 0x1D1B
E_LENGTH    EQU 0x1D1C
E_OEND      EQU 0x1D1E
E_GAP       EQU 0x1D20
E_START     EQU 0x1D21
E_END       EQU 0x1D22
E_BACK      EQU 0x1D80
E_INIT      EQU 0x1D81
E_Y         EQU 0x1D82
E_X         EQU 0x1D83
E_HORIZON   EQU 0x1D84
E_LEFT      EQU 0x1D85
E_RIGHT     EQU 0x1D86
E_VALUE     EQU 0x1D87
E_TYPE      EQU 0x1D88
E_LBYTE     EQU 0x1D89
E_RBYTE     EQU 0x1D8A
E_MAP4      EQU 0x1D8B
E_PREVH     EQU 0x1D8C
E_FORCE     EQU 0x1D8D
E_DLINE     EQU 0x1D8E
E_DMA       EQU 0x1D90
E_FILL      EQU 0x1DA8

HUD_COLOURS EQU 14
P_HEIGHT EQU 7296
P_Y EQU 7297
P_PHASE EQU 7298
P_ROW EQU 7299
P_DEST EQU 7300
P_LEFT EQU 7302
P_X EQU 7303
P_COUNT EQU 7304
P_SKYVALID EQU 7312
P_SKYEND EQU 7313
        ORG 0x5400
polish_init:
        ld a,(0x1C92)
        or a
        jr z,.load
        nextreg 0x15,9
        ret
.load:  ld a,1
        ld (0x1C92),a
        ld bc,0x243b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,hud_palette
        ld b,HUD_COLOURS
.palette:
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .palette
        nextreg 0x4b,227
        xor a
        ld bc,0x303b
        out (c),a
        nextreg 0x34,0
        ld d,218
.page:
        ld a,d
        nextreg 0x53,a
        ld hl,0x6000
        ld e,32
.pattern:
        ld bc,0x005b
        otir
        dec e
        jr nz,.pattern
        inc d
        ld a,d
        cp 220
        jr nz,.page
        ld hl,hud_attributes
        ld d,64
        xor a
        ld e,a
.attr:
        ld a,e
        nextreg 0x34,a
        ld a,(hl)
        nextreg 0x35,a
        inc hl
        ld a,(hl)
        nextreg 0x36,a
        inc hl
        ld a,(hl)
        nextreg 0x37,a
        inc hl
        ld a,e
        or 128
        nextreg 0x38,a
        inc e
        dec d
        jr nz,.attr
        nextreg 0x1c,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,63
        nextreg 0x15,9
        nextreg 0x43,0
        pop af
        nextreg 0x53,a
        ret
hud_palette:
        db 0,0,5,0,10,1,37,0,41,1,51,1,64,0,78,0,114,1,151,0,160,0,187,1,223,1,228,1
hud_attributes:
        db 32,32,0,48,32,0,64,32,0,80,32,0,96,32,0,112,32,0,128,32,0,144,32,0,160,32,0,176,32,0,192,32
        db 0,208,32,0,224,32,0,240,32,0,0,32,1,16,32,1,32,48,0,48,48,0,64,48,0,80,48,0,96,48,0,112
        db 48,0,128,48,0,144,48,0,160,48,0,176,48,0,192,48,0,208,48,0,224,48,0,240,48,0,0,48,1,16,48,1
        db 32,64,0,48,64,0,64,64,0,80,64,0,96,64,0,112,64,0,128,64,0,144,64,0,160,64,0,176,64,0,192,64
        db 0,208,64,0,224,64,0,240,64,0,0,64,1,16,64,1,32,80,0,48,80,0,64,80,0,80,80,0,96,80,0,112
        db 80,0,128,80,0,144,80,0,160,80,0,176,80,0,192,80,0,208,80,0,224,80,0,240,80,0,0,80,1,16,80,1
        ASSERT $ <= 0x5800
        ORG 0x5800
; The original supplies a repeating 80x24 horizon. Paint the same selected
; source rows and horizontal phase into the back buffer before foregrounds.
polish_sky:
        ld a,(P_SKYVALID)
        or a
        ret z
        ld a,(0xC161)
        ld b,a
        ld a,(0xC890)
        or b
        ret nz
        ld bc,0x243b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        push af
        ld a,(0xC80C)
        or a
        jp z,.done
        cp 25
        jp nc,.done
        ld (P_HEIGHT),a
        ld b,a
        ld a,(P_SKYEND)
        sub b
        ld (P_Y),a
        ; The original's 4-pixel scrolling selects a half-byte shifted tile.
        ld a,(0xC7E8)
        and 31
        add a,a
        add a,a
.mod:   cp 80
        jr c,.phase
        sub 80
        jr .mod
.phase: ld (P_PHASE),a
        ld a,0x54
        ld (E_DMA+6),a
        xor a
        ld (P_ROW),a
.row:
        ld a,(P_Y)
        cp 128
        jp nc,.next
        ld c,a
        and 96
        rlca
        rlca
        rlca
        ld b,a
        ld a,(E_BACK)
        add a,2
        add a,b
        nextreg 0x53,a
        ld a,c
        and 31
        or 0x60
        ld d,a
        ld e,8
        ld (P_DEST),de
        ld a,240
        ld (P_LEFT),a
        ld a,(P_PHASE)
        ld (P_X),a
        ld a,(A_STAGE)
        dec a
        add a,a
        ld b,a
        add a,a
        add a,b
        add a,a
        add a,a             ; stage * 24 source rows, each 512 bytes
        ld b,a
        ld a,(P_ROW)
        add a,b
        ld b,a
        srl a
        srl a
        srl a
        srl a
        add a,210
        nextreg 0x54,a
        ld a,b
        and 15
        add a,a
        or 0x80
        ld h,a
        ld a,(P_PHASE)
        ld l,a
        ld (E_DMA+2),hl
        ld bc,240
        ld (E_DMA+4),bc
        ld de,(P_DEST)
        ld (E_DMA+11),de
        ld hl,E_DMA
        ld bc,16*256+0x6b
        otir
.next:
        ld hl,P_ROW
        inc (hl)
        ld hl,P_Y
        inc (hl)
        ld hl,P_HEIGHT
        dec (hl)
        jp nz,.row
.done:
        ld a,0x64
        ld (E_DMA+6),a
        pop af
        nextreg 0x54,a
        ret
polish_end:
        SAVEBIN "banks_polish.bin",polish_init,polish_end-polish_init
        ENDMODULE
; ---- road motion and Copper list (bank 28 + 0x2000)
        MODULE chq_motion
A_MAP4      EQU 0x1D50
A_STAGE     EQU 0x1D51
A_SOURCE    EQU 0x1D52
A_DEST      EQU 0x1D54
A_FLAG      EQU 0x1D56
A_LOOKUP    EQU 0x1D57
A_CPAGE     EQU 0x1D58
A_CPTR      EQU 0x1D59
A_CACHED    EQU 0x1D5B
A_MAP5      EQU 0x1D5C
A_CMAP3     EQU 0x1D5D
A_COPYINDEX EQU 0x1D5E
A_LPTR      EQU 0x1D60
A_COUNT     EQU 0x1D62
S_SP        EQU 0x1D30
S_R         EQU 0x1D32
S_MAP2      EQU 0x1D33
S_MAP3      EQU 0x1D34
S_MAP4      EQU 0x1D35
S_ACTIVE    EQU 0x1D36
S_ANGLE     EQU 0x1D37
S_TARGET    EQU 0x1D38
S_VALID     EQU 0x1D39
S_REQ       EQU 0x1D3A
S_BOUNCE    EQU 0x1D3B
S_PAGE      EQU 0x1D3C
S_COUNT     EQU 0x1D3D
S_INIT      EQU 0x1D3E
S_FRAME     EQU 0x1D40
S_BACKUP    EQU 0x1800
S_STACK     EQU 0x1BE0

E_HORIZON EQU 0x1D84
M_CENTRES EQU 2048
M_COPPER EQU 2304
M_PHASE EQU 7328
M_SKYPHASE EQU 7329
M_STAGE EQU 7330
M_VALID EQU 7331
M_Y EQU 7332
M_DELTA EQU 7333
M_SKYDX EQU 7334
M_DY EQU 7335
M_DX EQU 7336
M_PTR EQU 7337
M_READY EQU 7339
M_LENGTH EQU 7340
M_DMA EQU 7344
M_PHASELOW EQU 7360
M_CHANGED EQU 7361
        ORG 0x6000
motion_commit:
        jp motion_reset
motion_capture:
        ld a,(0xA240)
        ld (M_PHASE),a
        ld a,(0xA23F)
        ld (M_PHASELOW),a
        ld a,(0xC7E8)
        ld (M_SKYPHASE),a
        ld a,(A_STAGE)
        ld (M_STAGE),a
        ld a,1
        ld (M_VALID),a
        xor a
        ld (M_Y),a
        ld de,M_CENTRES
.row:   push de
        call centre
        pop de
        ld (de),a
        inc de
        ld hl,M_Y
        inc (hl)
        ld a,(hl)
        cp 128
        jr nz,.row
        ret
motion_install:
        nextreg 0x62,0
        nextreg 0x61,0
        ld hl,base_copper
        ld de,base_copper_end-base_copper
        call upload
        nextreg 0x62,0xc0
        ret
motion_reset:
        ; Keep the running PC: all WAITs and register numbers are immutable.
        ; A live DMA changes only offset values. A partial-frame update can
        ; move part of the image, but cannot skip the palette split at line 64.
        nextreg 0x62,0xc0
        nextreg 0x61,0
        ld hl,base_copper
        ld de,base_copper_end-base_copper
        call upload
        ret
motion_prepare:
        xor a
        ld (M_READY),a
        ld a,(M_VALID)
        or a
        ret z
        ld a,(M_STAGE)
        ld b,a
        ld a,(A_STAGE)
        cp b
        ret nz
        ld a,(S_VALID)
        or a
        ret z
        ld a,(0xB5AB)
        ld b,a
        ld a,(0xA22A)
        or b
        ld b,a
        ld a,(0xA22F)
        or b
        ld b,a
        ld a,(0xB064)
        or b
        ret nz
        ld a,(M_PHASELOW)
        ld e,a
        ld a,(M_PHASE)
        ld d,a
        ld hl,(0xA23F)
        or a
        sbc hl,de
        ld a,h
        cp 8
        ret nc
        add hl,hl
        add hl,hl
        ld a,h
        ld (M_DELTA),a
        xor a
        ld (M_CHANGED),a
        ld a,(0xC7E8)
        ld b,a
        ld a,(M_SKYPHASE)
        sub b
        neg
        ; The 80-pixel horizon repeats every 20 four-pixel phases.
        cp 10
        jr c,.skyphase
        cp 246
        jr nc,.skyphase
        bit 7,a
        jr z,.skyminus
        add a,20
        jr .skyphase
.skyminus:
        sub 20
.skyphase:
        add a,a
        ld (M_SKYDX),a
        xor a
        ld (M_Y),a
        ld hl,M_COPPER
        ld (hl),0x43
        inc hl
        ld (hl),0
        inc hl
        ld (hl),0x80
        inc hl
        ld (hl),64
        inc hl
        ld (hl),0x43
        inc hl
        ld (hl),2
        inc hl
.row:
        ld (M_PTR),hl
        ld a,(M_Y)
        ld b,a
        ld a,(0xE314)
        add a,32
        ld c,a
        ld a,b
        sub c
        jr c,.sky
        ld l,a
        ld a,(M_DELTA)
        srl a
        jr nc,.even
        set 7,l
.even:  add a,0x70
        ld h,a
        ld a,(hl)
        and 254            ; preserve the original checkerboard parity
        ld b,a
        xor a
        sub b
        jr z,.dy
        add a,192
.dy:    ld (M_DY),a
        call centre
        ld b,a
        ld a,(M_Y)
        ld l,a
        ld h,high M_CENTRES
        ld a,(hl)
        sub b
        cp 17
        jr c,.smallturn
        cp 240
        jr nc,.smallturn
        xor a
.smallturn:
        sra a
        and 254
        ld (M_DX),a
        jr .emit
.sky:   xor a
        ld (M_DY),a
        ld a,(M_SKYDX)
        ld (M_DX),a
.emit:  ld a,(M_DX)
        ld b,a
        ld a,(M_DY)
        or b
        jr z,.unchanged
        ld a,1
        ld (M_CHANGED),a
.unchanged:
        ld hl,(M_PTR)
        ld a,0x80
        call wait_row
        ld a,(M_Y)
        cp 112
        jr c,.normal
        call fixed
        ld a,0x8e       ; restore road movement after the three turbo symbols
        call wait_row
.normal:
        call offsets
        ld a,(M_Y)
        cp 88
        jr c,.next
        ld a,0x94       ; keep the independent 64x40 player-car rectangle steady
        call wait_row
        call fixed
        ld a,0xaa
        call wait_row
        call offsets
.next:  ld a,(M_Y)
        inc a
        ld (M_Y),a
        cp 128
        jp nz,.row
        ld a,(M_CHANGED)
        or a
        ret z
        ld de,end_copper
        ld b,end_copper_end-end_copper
.end:   ld a,(de)
        ld (hl),a
        inc de
        inc hl
        djnz .end
        ld de,M_COPPER
        or a
        sbc hl,de
        ld (M_LENGTH),hl
        ld a,1
        ld (M_READY),a
        ret
motion_show:
        ld a,(0xC161)
        ld b,a
        ld a,(0xC890)
        or b
        ret nz
        ld a,(M_READY)
        or a
        ret z
        xor a
        ld (M_READY),a
        ld de,(M_LENGTH)
        ld hl,M_COPPER
        nextreg 0x62,0xc0
        nextreg 0x61,0
        call upload
        ret
wait_row:
        ld (hl),a
        inc hl
        ld a,(M_Y)
        add a,64
        ld (hl),a
        inc hl
        ret
fixed:  ld b,0
        ld c,0
        jr emit_l2
; Only L2 is held steady in the car rectangle: the original car bitmap was
; restored by the existing steering hook, so the ULA road keeps moving below it.
offsets:
        ld a,(M_DX)
        ld b,a
        ld a,(M_DY)
        ld c,a
        ld (hl),0x26
        inc hl
        ld (hl),b
        inc hl
        ld (hl),0x27
        inc hl
        ld (hl),c
        inc hl
emit_l2:
        ld (hl),0x16
        inc hl
        ld (hl),b
        inc hl
        ld (hl),0x17
        inc hl
        ld (hl),c
        inc hl
        ret
centre:
        ld a,(M_Y)
        add a,a
        ld l,a
        ld h,0xe8
        call clamp
        ld b,a
        ld h,0xec
        call clamp
        add a,b
        rra
        ret
clamp:
        inc l
        ld a,(hl)
        dec l
        bit 7,a
        jr nz,.zero
        or a
        jr nz,.max
        ld a,(hl)
        ret
.zero:  xor a
        ret
.max:   ld a,255
        ret
upload:
        push hl
        push de
        ld hl,port_dma
        ld de,M_DMA
        ld bc,16
        ldir
        pop de
        pop hl
        ld (M_DMA+2),hl
        ld (M_DMA+4),de
        ld bc,0x243b
        ld a,0x60
        out (c),a
        ld hl,M_DMA
        ld bc,16*256+0x6b
        otir
        ret
port_dma:
        db 0x83,0x7d
        dw 0,0
        db 0x54,2,0x68,2,0xad
        dw 0x253b
        db 0x82,0xcf,0x87
end_copper:
        db 0x80,192, 0x43,0, 0x16,0, 0x17,0, 0x26,0, 0x27,0, 0xff,0xff
end_copper_end:
        ASSERT $ <= 0x6600
        ORG 0x6600
base_copper:
 db 67,0,128,64,67,2,128,64,38,0,39,0,22,0,23,0,128,65,38,0,39,0,22,0,23,0,128,66,38,0,39,0
 db 22,0,23,0,128,67,38,0,39,0,22,0,23,0,128,68,38,0,39,0,22,0,23,0,128,69,38,0,39,0,22,0
 db 23,0,128,70,38,0,39,0,22,0,23,0,128,71,38,0,39,0,22,0,23,0,128,72,38,0,39,0,22,0,23,0
 db 128,73,38,0,39,0,22,0,23,0,128,74,38,0,39,0,22,0,23,0,128,75,38,0,39,0,22,0,23,0,128,76
 db 38,0,39,0,22,0,23,0,128,77,38,0,39,0,22,0,23,0,128,78,38,0,39,0,22,0,23,0,128,79,38,0
 db 39,0,22,0,23,0,128,80,38,0,39,0,22,0,23,0,128,81,38,0,39,0,22,0,23,0,128,82,38,0,39,0
 db 22,0,23,0,128,83,38,0,39,0,22,0,23,0,128,84,38,0,39,0,22,0,23,0,128,85,38,0,39,0,22,0
 db 23,0,128,86,38,0,39,0,22,0,23,0,128,87,38,0,39,0,22,0,23,0,128,88,38,0,39,0,22,0,23,0
 db 128,89,38,0,39,0,22,0,23,0,128,90,38,0,39,0,22,0,23,0,128,91,38,0,39,0,22,0,23,0,128,92
 db 38,0,39,0,22,0,23,0,128,93,38,0,39,0,22,0,23,0,128,94,38,0,39,0,22,0,23,0,128,95,38,0
 db 39,0,22,0,23,0,128,96,38,0,39,0,22,0,23,0,128,97,38,0,39,0,22,0,23,0,128,98,38,0,39,0
 db 22,0,23,0,128,99,38,0,39,0,22,0,23,0,128,100,38,0,39,0,22,0,23,0,128,101,38,0,39,0,22,0
 db 23,0,128,102,38,0,39,0,22,0,23,0,128,103,38,0,39,0,22,0,23,0,128,104,38,0,39,0,22,0,23,0
 db 128,105,38,0,39,0,22,0,23,0,128,106,38,0,39,0,22,0,23,0,128,107,38,0,39,0,22,0,23,0,128,108
 db 38,0,39,0,22,0,23,0,128,109,38,0,39,0,22,0,23,0,128,110,38,0,39,0,22,0,23,0,128,111,38,0
 db 39,0,22,0,23,0,128,112,38,0,39,0,22,0,23,0,128,113,38,0,39,0,22,0,23,0,128,114,38,0,39,0
 db 22,0,23,0,128,115,38,0,39,0,22,0,23,0,128,116,38,0,39,0,22,0,23,0,128,117,38,0,39,0,22,0
 db 23,0,128,118,38,0,39,0,22,0,23,0,128,119,38,0,39,0,22,0,23,0,128,120,38,0,39,0,22,0,23,0
 db 128,121,38,0,39,0,22,0,23,0,128,122,38,0,39,0,22,0,23,0,128,123,38,0,39,0,22,0,23,0,128,124
 db 38,0,39,0,22,0,23,0,128,125,38,0,39,0,22,0,23,0,128,126,38,0,39,0,22,0,23,0,128,127,38,0
 db 39,0,22,0,23,0,128,128,38,0,39,0,22,0,23,0,128,129,38,0,39,0,22,0,23,0,128,130,38,0,39,0
 db 22,0,23,0,128,131,38,0,39,0,22,0,23,0,128,132,38,0,39,0,22,0,23,0,128,133,38,0,39,0,22,0
 db 23,0,128,134,38,0,39,0,22,0,23,0,128,135,38,0,39,0,22,0,23,0,128,136,38,0,39,0,22,0,23,0
 db 128,137,38,0,39,0,22,0,23,0,128,138,38,0,39,0,22,0,23,0,128,139,38,0,39,0,22,0,23,0,128,140
 db 38,0,39,0,22,0,23,0,128,141,38,0,39,0,22,0,23,0,128,142,38,0,39,0,22,0,23,0,128,143,38,0
 db 39,0,22,0,23,0,128,144,38,0,39,0,22,0,23,0,128,145,38,0,39,0,22,0,23,0,128,146,38,0,39,0
 db 22,0,23,0,128,147,38,0,39,0,22,0,23,0,128,148,38,0,39,0,22,0,23,0,128,149,38,0,39,0,22,0
 db 23,0,128,150,38,0,39,0,22,0,23,0,128,151,38,0,39,0,22,0,23,0,128,152,38,0,39,0,22,0,23,0
 db 148,152,22,0,23,0,170,152,38,0,39,0,22,0,23,0,128,153,38,0,39,0,22,0,23,0,148,153,22,0,23,0
 db 170,153,38,0,39,0,22,0,23,0,128,154,38,0,39,0,22,0,23,0,148,154,22,0,23,0,170,154,38,0,39,0
 db 22,0,23,0,128,155,38,0,39,0,22,0,23,0,148,155,22,0,23,0,170,155,38,0,39,0,22,0,23,0,128,156
 db 38,0,39,0,22,0,23,0,148,156,22,0,23,0,170,156,38,0,39,0,22,0,23,0,128,157,38,0,39,0,22,0
 db 23,0,148,157,22,0,23,0,170,157,38,0,39,0,22,0,23,0,128,158,38,0,39,0,22,0,23,0,148,158,22,0
 db 23,0,170,158,38,0,39,0,22,0,23,0,128,159,38,0,39,0,22,0,23,0,148,159,22,0,23,0,170,159,38,0
 db 39,0,22,0,23,0,128,160,38,0,39,0,22,0,23,0,148,160,22,0,23,0,170,160,38,0,39,0,22,0,23,0
 db 128,161,38,0,39,0,22,0,23,0,148,161,22,0,23,0,170,161,38,0,39,0,22,0,23,0,128,162,38,0,39,0
 db 22,0,23,0,148,162,22,0,23,0,170,162,38,0,39,0,22,0,23,0,128,163,38,0,39,0,22,0,23,0,148,163
 db 22,0,23,0,170,163,38,0,39,0,22,0,23,0,128,164,38,0,39,0,22,0,23,0,148,164,22,0,23,0,170,164
 db 38,0,39,0,22,0,23,0,128,165,38,0,39,0,22,0,23,0,148,165,22,0,23,0,170,165,38,0,39,0,22,0
 db 23,0,128,166,38,0,39,0,22,0,23,0,148,166,22,0,23,0,170,166,38,0,39,0,22,0,23,0,128,167,38,0
 db 39,0,22,0,23,0,148,167,22,0,23,0,170,167,38,0,39,0,22,0,23,0,128,168,38,0,39,0,22,0,23,0
 db 148,168,22,0,23,0,170,168,38,0,39,0,22,0,23,0,128,169,38,0,39,0,22,0,23,0,148,169,22,0,23,0
 db 170,169,38,0,39,0,22,0,23,0,128,170,38,0,39,0,22,0,23,0,148,170,22,0,23,0,170,170,38,0,39,0
 db 22,0,23,0,128,171,38,0,39,0,22,0,23,0,148,171,22,0,23,0,170,171,38,0,39,0,22,0,23,0,128,172
 db 38,0,39,0,22,0,23,0,148,172,22,0,23,0,170,172,38,0,39,0,22,0,23,0,128,173,38,0,39,0,22,0
 db 23,0,148,173,22,0,23,0,170,173,38,0,39,0,22,0,23,0,128,174,38,0,39,0,22,0,23,0,148,174,22,0
 db 23,0,170,174,38,0,39,0,22,0,23,0,128,175,38,0,39,0,22,0,23,0,148,175,22,0,23,0,170,175,38,0
 db 39,0,22,0,23,0,128,176,22,0,23,0,142,176,38,0,39,0,22,0,23,0,148,176,22,0,23,0,170,176,38,0
 db 39,0,22,0,23,0,128,177,22,0,23,0,142,177,38,0,39,0,22,0,23,0,148,177,22,0,23,0,170,177,38,0
 db 39,0,22,0,23,0,128,178,22,0,23,0,142,178,38,0,39,0,22,0,23,0,148,178,22,0,23,0,170,178,38,0
 db 39,0,22,0,23,0,128,179,22,0,23,0,142,179,38,0,39,0,22,0,23,0,148,179,22,0,23,0,170,179,38,0
 db 39,0,22,0,23,0,128,180,22,0,23,0,142,180,38,0,39,0,22,0,23,0,148,180,22,0,23,0,170,180,38,0
 db 39,0,22,0,23,0,128,181,22,0,23,0,142,181,38,0,39,0,22,0,23,0,148,181,22,0,23,0,170,181,38,0
 db 39,0,22,0,23,0,128,182,22,0,23,0,142,182,38,0,39,0,22,0,23,0,148,182,22,0,23,0,170,182,38,0
 db 39,0,22,0,23,0,128,183,22,0,23,0,142,183,38,0,39,0,22,0,23,0,148,183,22,0,23,0,170,183,38,0
 db 39,0,22,0,23,0,128,184,22,0,23,0,142,184,38,0,39,0,22,0,23,0,148,184,22,0,23,0,170,184,38,0
 db 39,0,22,0,23,0,128,185,22,0,23,0,142,185,38,0,39,0,22,0,23,0,148,185,22,0,23,0,170,185,38,0
 db 39,0,22,0,23,0,128,186,22,0,23,0,142,186,38,0,39,0,22,0,23,0,148,186,22,0,23,0,170,186,38,0
 db 39,0,22,0,23,0,128,187,22,0,23,0,142,187,38,0,39,0,22,0,23,0,148,187,22,0,23,0,170,187,38,0
 db 39,0,22,0,23,0,128,188,22,0,23,0,142,188,38,0,39,0,22,0,23,0,148,188,22,0,23,0,170,188,38,0
 db 39,0,22,0,23,0,128,189,22,0,23,0,142,189,38,0,39,0,22,0,23,0,148,189,22,0,23,0,170,189,38,0
 db 39,0,22,0,23,0,128,190,22,0,23,0,142,190,38,0,39,0,22,0,23,0,148,190,22,0,23,0,170,190,38,0
 db 39,0,22,0,23,0,128,191,22,0,23,0,142,191,38,0,39,0,22,0,23,0,148,191,22,0,23,0,170,191,38,0
 db 39,0,22,0,23,0,128,192,67,0,22,0,23,0,38,0,39,0,255,255
base_copper_end:
        ASSERT $ < 0x7000
        ORG 0x7000
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2
 db 2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2
 db 2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3
 db 3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3
 db 3,4,4,4,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2
 db 2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4
 db 4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2
 db 2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2
 db 2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2
 db 3,3,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3
 db 3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3
 db 3,3,3,3,3,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3
 db 3,3,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3
 db 4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,4,4
 db 4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,4,4,4,4
 db 4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4
 db 4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,1,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,1,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,2,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,1,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 1,2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1
 db 2,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,2
 db 2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,2
 db 2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,2,2
 db 2,2,2,2,2,2,2,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,2,2
 db 2,2,2,2,2,2,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2
 db 2,2,2,2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,2,2,2
 db 2,2,2,2,2,3,3,3,3,3,3,3,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2
 db 2,2,2,2,3,3,3,3,3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
 db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
motion_end:
        SAVEBIN "banks_motion.bin",0x6000,motion_end-0x6000
        ENDMODULE
; ---- radio portraits, message pane, briefing plotters (bank 8 + 0x0000)
        MODULE chq_hud
PORTRAIT_COUNT EQU 5
H_SOURCE EQU 0x1C60
H_VISIBLE EQU 0x1C62
H_VALID EQU 0x1C63
H_OFFSET EQU 0x1C64
H_PTR EQU 0x1C66
H_Y EQU 0x1C68
H_BASE EQU 0x1C69
H_COUNT EQU 0x1C6A
H_ROW EQU 0x1C6B
H_FILL EQU 0x1C6C
H_READY EQU 0x1C6E
H_DMA EQU 0x1C70
H_CACHE EQU 0x1E00
        ORG 0x4000
        jp hud_init
        jp hud_show
        jp hud_hide
        jp hud_message
        jp hud_rows
; Table is resolved after the hidden-ROM labels have been assembled.
; Restore original plotters during briefing; install colour plotters for play.
hud_rows:
        nextreg 0x54,4
        ld hl,0x5000
        ld b,(hl)
        inc hl
.record:
        push bc
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,0
        ld a,(0x1C96)
        or a
        jr nz,.original
        add hl,bc
        ldir
        jr .next
.original:
        push bc
        ldir
        pop bc
        add hl,bc
.next:
        pop bc
        djnz .record
        ret
hud_init:
        ld a,(H_READY)
        or a
        ret nz
        ld a,1
        ld (H_READY),a
        xor a
        ld (H_VISIBLE),a
        ld (H_VALID),a
        ld (H_FILL),a
        ld hl,fill_dma
        ld de,H_DMA
        ld bc,16
        ldir
        ld d,32
.clear:
        ld a,d
        nextreg 0x53,a
        push de
        ld hl,H_DMA
        ld bc,0x106B
        otir
        pop de
        inc d
        ld a,d
        cp 34
        jr nz,.second
        ld d,38
.second:
        cp 40
        jr c,.clear
        ret
hud_show:
        ld hl,portraits
        ld b,PORTRAIT_COUNT
.find:
        ld a,(hl)
        inc hl
        or a
        jr z,.stage
        ld c,a
        ld a,(0x1D51)
        cp c
        jr nz,.skip
.stage:
        ld a,(H_SOURCE)
        cp (hl)
        jr nz,.skip
        inc hl
        ld a,(H_SOURCE+1)
        cp (hl)
        dec hl
        jr z,.found
.skip:
        ld de,4
        add hl,de
        djnz .find
        jp hud_hide
.found:
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (H_OFFSET),de
        ld a,1
        ld (H_VISIBLE),a
        ld a,32
        call portrait_buffer
        ld a,38
        jp portrait_buffer
portrait_buffer:
        ld (H_BASE),a
        ld hl,(H_OFFSET)
        ld (H_PTR),hl
        ld a,8
        ld (H_Y),a
.row:
        ld a,(H_Y)
        rrca
        rrca
        rrca
        rrca
        rrca
        and 1
        ld b,a
        ld a,(H_BASE)
        add a,b
        nextreg 0x53,a
        ld a,(H_Y)
        and 31
        or 0x60
        ld d,a
        ld e,176
        ld a,(H_VISIBLE)
        or a
        jr z,.empty
        ld hl,(H_PTR)
        ld a,h
        rrca
        rrca
        rrca
        rrca
        rrca
        and 1
        add a,18
        nextreg 0x54,a
        ld a,h
        and 31
        or 0x80
        ld h,a
        ld bc,32
        ldir
        ld hl,(H_PTR)
        ld bc,32
        add hl,bc
        ld (H_PTR),hl
        jr .next
.empty:
        xor a
        ld b,32
.zero:
        ld (de),a
        inc e
        djnz .zero
.next:
        ld hl,H_Y
        inc (hl)
        ld a,(hl)
        cp 48
        jr c,.row
        ret
hud_hide:
        ld a,(H_VISIBLE)
        or a
        ret z
        xor a
        ld (H_VISIBLE),a
        ld a,32
        call portrait_buffer
        ld a,38
        jp portrait_buffer
hud_message:
        nextreg 0x54,10     ; original bank 5 screen, read through slot 4
        ld hl,0x85C1
        ld ix,H_CACHE
        ld a,0x75
        ld (H_Y),a
        ld a,6
        ld (H_ROW),a
.row:
        push hl
        ld b,30
        ld c,8
.byte:
        ld a,(hl)
        ld d,a
        ld a,(H_VALID)
        or a
        ld a,d
        jr z,.changed
        cp (ix+0)
        jr z,.next
.changed:
        ld (ix+0),a
        push bc
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,c
        ld (0x1C6D),a
        ld bc,message_lut
        add hl,bc
        push hl
        nextreg 0x53,33
        call .eight
        pop hl
        nextreg 0x53,39
        call .eight
        pop hl
        pop bc
.next:
        inc hl
        inc ix
        ld a,c
        add a,8
        ld c,a
        djnz .byte
        pop hl
        call screen_next
        ld a,(H_Y)
        inc a
        ld (H_Y),a
        ld a,(H_ROW)
        dec a
        ld (H_ROW),a
        jr nz,.row
        ld a,1
        ld (H_VALID),a
        ret
.eight:
        ld a,(H_Y)
        ld d,a
        ld a,(0x1C6D)
        ld e,a
        ld bc,8
        ldir
        ret
screen_next:
        inc h
        ld a,h
        and 7
        ret nz
        ld a,l
        add a,32
        ld l,a
        ret c
        ld a,h
        sub 8
        ld h,a
        ret
fill_dma:
        db 0x83,0x7D
        dw H_FILL,8192
        db 0x64,2,0x50,2,0xAD
        dw 0x6000
        db 0x82,0xCF,0x87
portraits:
        db 2
        dw 27738,0
        db 4
        dw 27445,1280
        db 0
        dw 31721,2560
        db 0
        dw 31901,3840
        db 0
        dw 32081,5120
message_lut:
        db 17,17,17,17,17,17,17,17,17,17,17,17,17,17,17,255,17,17,17,17,17,17,255,17,17,17,17,17,17,17,255,255
        db 17,17,17,17,17,255,17,17,17,17,17,17,17,255,17,255,17,17,17,17,17,255,255,17,17,17,17,17,17,255,255,255
        db 17,17,17,17,255,17,17,17,17,17,17,17,255,17,17,255,17,17,17,17,255,17,255,17,17,17,17,17,255,17,255,255
        db 17,17,17,17,255,255,17,17,17,17,17,17,255,255,17,255,17,17,17,17,255,255,255,17,17,17,17,17,255,255,255,255
        db 17,17,17,255,17,17,17,17,17,17,17,255,17,17,17,255,17,17,17,255,17,17,255,17,17,17,17,255,17,17,255,255
        db 17,17,17,255,17,255,17,17,17,17,17,255,17,255,17,255,17,17,17,255,17,255,255,17,17,17,17,255,17,255,255,255
        db 17,17,17,255,255,17,17,17,17,17,17,255,255,17,17,255,17,17,17,255,255,17,255,17,17,17,17,255,255,17,255,255
        db 17,17,17,255,255,255,17,17,17,17,17,255,255,255,17,255,17,17,17,255,255,255,255,17,17,17,17,255,255,255,255,255
        db 17,17,255,17,17,17,17,17,17,17,255,17,17,17,17,255,17,17,255,17,17,17,255,17,17,17,255,17,17,17,255,255
        db 17,17,255,17,17,255,17,17,17,17,255,17,17,255,17,255,17,17,255,17,17,255,255,17,17,17,255,17,17,255,255,255
        db 17,17,255,17,255,17,17,17,17,17,255,17,255,17,17,255,17,17,255,17,255,17,255,17,17,17,255,17,255,17,255,255
        db 17,17,255,17,255,255,17,17,17,17,255,17,255,255,17,255,17,17,255,17,255,255,255,17,17,17,255,17,255,255,255,255
        db 17,17,255,255,17,17,17,17,17,17,255,255,17,17,17,255,17,17,255,255,17,17,255,17,17,17,255,255,17,17,255,255
        db 17,17,255,255,17,255,17,17,17,17,255,255,17,255,17,255,17,17,255,255,17,255,255,17,17,17,255,255,17,255,255,255
        db 17,17,255,255,255,17,17,17,17,17,255,255,255,17,17,255,17,17,255,255,255,17,255,17,17,17,255,255,255,17,255,255
        db 17,17,255,255,255,255,17,17,17,17,255,255,255,255,17,255,17,17,255,255,255,255,255,17,17,17,255,255,255,255,255,255
        db 17,255,17,17,17,17,17,17,17,255,17,17,17,17,17,255,17,255,17,17,17,17,255,17,17,255,17,17,17,17,255,255
        db 17,255,17,17,17,255,17,17,17,255,17,17,17,255,17,255,17,255,17,17,17,255,255,17,17,255,17,17,17,255,255,255
        db 17,255,17,17,255,17,17,17,17,255,17,17,255,17,17,255,17,255,17,17,255,17,255,17,17,255,17,17,255,17,255,255
        db 17,255,17,17,255,255,17,17,17,255,17,17,255,255,17,255,17,255,17,17,255,255,255,17,17,255,17,17,255,255,255,255
        db 17,255,17,255,17,17,17,17,17,255,17,255,17,17,17,255,17,255,17,255,17,17,255,17,17,255,17,255,17,17,255,255
        db 17,255,17,255,17,255,17,17,17,255,17,255,17,255,17,255,17,255,17,255,17,255,255,17,17,255,17,255,17,255,255,255
        db 17,255,17,255,255,17,17,17,17,255,17,255,255,17,17,255,17,255,17,255,255,17,255,17,17,255,17,255,255,17,255,255
        db 17,255,17,255,255,255,17,17,17,255,17,255,255,255,17,255,17,255,17,255,255,255,255,17,17,255,17,255,255,255,255,255
        db 17,255,255,17,17,17,17,17,17,255,255,17,17,17,17,255,17,255,255,17,17,17,255,17,17,255,255,17,17,17,255,255
        db 17,255,255,17,17,255,17,17,17,255,255,17,17,255,17,255,17,255,255,17,17,255,255,17,17,255,255,17,17,255,255,255
        db 17,255,255,17,255,17,17,17,17,255,255,17,255,17,17,255,17,255,255,17,255,17,255,17,17,255,255,17,255,17,255,255
        db 17,255,255,17,255,255,17,17,17,255,255,17,255,255,17,255,17,255,255,17,255,255,255,17,17,255,255,17,255,255,255,255
        db 17,255,255,255,17,17,17,17,17,255,255,255,17,17,17,255,17,255,255,255,17,17,255,17,17,255,255,255,17,17,255,255
        db 17,255,255,255,17,255,17,17,17,255,255,255,17,255,17,255,17,255,255,255,17,255,255,17,17,255,255,255,17,255,255,255
        db 17,255,255,255,255,17,17,17,17,255,255,255,255,17,17,255,17,255,255,255,255,17,255,17,17,255,255,255,255,17,255,255
        db 17,255,255,255,255,255,17,17,17,255,255,255,255,255,17,255,17,255,255,255,255,255,255,17,17,255,255,255,255,255,255,255
        db 255,17,17,17,17,17,17,17,255,17,17,17,17,17,17,255,255,17,17,17,17,17,255,17,255,17,17,17,17,17,255,255
        db 255,17,17,17,17,255,17,17,255,17,17,17,17,255,17,255,255,17,17,17,17,255,255,17,255,17,17,17,17,255,255,255
        db 255,17,17,17,255,17,17,17,255,17,17,17,255,17,17,255,255,17,17,17,255,17,255,17,255,17,17,17,255,17,255,255
        db 255,17,17,17,255,255,17,17,255,17,17,17,255,255,17,255,255,17,17,17,255,255,255,17,255,17,17,17,255,255,255,255
        db 255,17,17,255,17,17,17,17,255,17,17,255,17,17,17,255,255,17,17,255,17,17,255,17,255,17,17,255,17,17,255,255
        db 255,17,17,255,17,255,17,17,255,17,17,255,17,255,17,255,255,17,17,255,17,255,255,17,255,17,17,255,17,255,255,255
        db 255,17,17,255,255,17,17,17,255,17,17,255,255,17,17,255,255,17,17,255,255,17,255,17,255,17,17,255,255,17,255,255
        db 255,17,17,255,255,255,17,17,255,17,17,255,255,255,17,255,255,17,17,255,255,255,255,17,255,17,17,255,255,255,255,255
        db 255,17,255,17,17,17,17,17,255,17,255,17,17,17,17,255,255,17,255,17,17,17,255,17,255,17,255,17,17,17,255,255
        db 255,17,255,17,17,255,17,17,255,17,255,17,17,255,17,255,255,17,255,17,17,255,255,17,255,17,255,17,17,255,255,255
        db 255,17,255,17,255,17,17,17,255,17,255,17,255,17,17,255,255,17,255,17,255,17,255,17,255,17,255,17,255,17,255,255
        db 255,17,255,17,255,255,17,17,255,17,255,17,255,255,17,255,255,17,255,17,255,255,255,17,255,17,255,17,255,255,255,255
        db 255,17,255,255,17,17,17,17,255,17,255,255,17,17,17,255,255,17,255,255,17,17,255,17,255,17,255,255,17,17,255,255
        db 255,17,255,255,17,255,17,17,255,17,255,255,17,255,17,255,255,17,255,255,17,255,255,17,255,17,255,255,17,255,255,255
        db 255,17,255,255,255,17,17,17,255,17,255,255,255,17,17,255,255,17,255,255,255,17,255,17,255,17,255,255,255,17,255,255
        db 255,17,255,255,255,255,17,17,255,17,255,255,255,255,17,255,255,17,255,255,255,255,255,17,255,17,255,255,255,255,255,255
        db 255,255,17,17,17,17,17,17,255,255,17,17,17,17,17,255,255,255,17,17,17,17,255,17,255,255,17,17,17,17,255,255
        db 255,255,17,17,17,255,17,17,255,255,17,17,17,255,17,255,255,255,17,17,17,255,255,17,255,255,17,17,17,255,255,255
        db 255,255,17,17,255,17,17,17,255,255,17,17,255,17,17,255,255,255,17,17,255,17,255,17,255,255,17,17,255,17,255,255
        db 255,255,17,17,255,255,17,17,255,255,17,17,255,255,17,255,255,255,17,17,255,255,255,17,255,255,17,17,255,255,255,255
        db 255,255,17,255,17,17,17,17,255,255,17,255,17,17,17,255,255,255,17,255,17,17,255,17,255,255,17,255,17,17,255,255
        db 255,255,17,255,17,255,17,17,255,255,17,255,17,255,17,255,255,255,17,255,17,255,255,17,255,255,17,255,17,255,255,255
        db 255,255,17,255,255,17,17,17,255,255,17,255,255,17,17,255,255,255,17,255,255,17,255,17,255,255,17,255,255,17,255,255
        db 255,255,17,255,255,255,17,17,255,255,17,255,255,255,17,255,255,255,17,255,255,255,255,17,255,255,17,255,255,255,255,255
        db 255,255,255,17,17,17,17,17,255,255,255,17,17,17,17,255,255,255,255,17,17,17,255,17,255,255,255,17,17,17,255,255
        db 255,255,255,17,17,255,17,17,255,255,255,17,17,255,17,255,255,255,255,17,17,255,255,17,255,255,255,17,17,255,255,255
        db 255,255,255,17,255,17,17,17,255,255,255,17,255,17,17,255,255,255,255,17,255,17,255,17,255,255,255,17,255,17,255,255
        db 255,255,255,17,255,255,17,17,255,255,255,17,255,255,17,255,255,255,255,17,255,255,255,17,255,255,255,17,255,255,255,255
        db 255,255,255,255,17,17,17,17,255,255,255,255,17,17,17,255,255,255,255,255,17,17,255,17,255,255,255,255,17,17,255,255
        db 255,255,255,255,17,255,17,17,255,255,255,255,17,255,17,255,255,255,255,255,17,255,255,17,255,255,255,255,17,255,255,255
        db 255,255,255,255,255,17,17,17,255,255,255,255,255,17,17,255,255,255,255,255,255,17,255,17,255,255,255,255,255,17,255,255
        db 255,255,255,255,255,255,17,17,255,255,255,255,255,255,17,255,255,255,255,255,255,255,255,17,255,255,255,255,255,255,255,255
hud_code_end:
        ASSERT $ <= 0x6000
        SAVEBIN "banks_hud.bin",0x4000,hud_code_end-0x4000
        ENDMODULE
