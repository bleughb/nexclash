; Included for each palette edition. Only the inactive cache entries can be
; rebuilt before the beat. The attributes stay pending until the scenery blit.
        ORG 0x3000
smooth_bl:
        nextreg 7,3
        nextreg 0x54,26
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call commit                 ; installer splits commit at .upl
        ld a,8
        ld hl,0x5DA3
        sub (hl)
        jr nc,.phase
        xor a
.phase: ld (V_OFFSET),a
        ld c,a
        ld a,(V_NS)
        ld b,a
        or a
        jr z,.wait
        ld hl,SPRTAB
.shift: ld a,(hl)
        sub c
        ld (hl),a
        inc hl
        inc hl
        jr nc,.next
        ld a,(hl)
        xor 1                       ; X is nine bits, keep the palette nibble
        ld (hl),a
.next:  inc hl
        inc hl
        inc hl
        djnz .shift
.wait:  ; Stage the original blit with a mirror of the screen page. Its stack,
        ; pointer variables and in-play interrupt code also live in that page.
        nextreg 0x55,86
        ld hl,0x4000
        ld de,0xA000
        ld bc,8192
        ldir
        nextreg 0x55,5
        nextreg 0x52,86
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x54,4
        jp e_bl                     ; stage, then present at smooth_upload

smooth_upload:
        ; Return every non-screen byte, including the live game stack. The
        ; music interrupt runs on H's stack during both page transfers.
        nextreg 0x55,10
        ld hl,0x5B00
        ld de,0xBB00
        ld bc,0x500
        ldir
        nextreg 0x52,10
        nextreg 0x55,86
        call wait_beat
        ld a,(V_OFFSET)
        nextreg 0x61,cu_phase-cu_list
        nextreg 0x62,0xC0
        nextreg 0x60,a
        nextreg 0x26,a
        ld hl,packet
        ld bc,(packet_end-packet)*256+0x6B
        otir
        nextreg 0x55,5
        xor a
        ld (V_N),a
        jp commit.upl+4

packet: db 0x83,0xC3,0x7D
        dw 0xA000,6912
        db 0x14,0x10,0xAD
        dw 0x4000
        db 0x82,0xCF,0x87
packet_end:

; The original IM2 music driver runs once per interrupt. Re-enable after
; the AY routine so an asserted /INT cannot re-enter at turbo speed.
smooth_irq:
        exx
        ex af,af'
        push hl
        ld hl,TICK
        inc (hl)
        pop hl
        call 0x5F8A
        ex af,af'
        exx
        ei
        reti

wait_beat:
        ld a,(V_STARTED)
        or a
        jr nz,.scheduled
        inc a
        ld (V_STARTED),a
        nextreg 0x61,0
        nextreg 0x62,0
        ld hl,cu_list
        ld b,cu_end-cu_list
.init:  ld a,(hl)
        nextreg 0x60,a
        inc hl
        djnz .init
        nextreg 0x62,0xC0
        ; Clip to source columns 2..29 even at a seven-pixel offset.
        nextreg 0x1C,2
        nextreg 0x19,16
        nextreg 0x19,231
        nextreg 0x19,0
        nextreg 0x19,151
        call .line
        ; First presentation may follow row 191 before the copper has run
        ; its first complete field. Establish the first playfield clip now.
        nextreg 0x1C,4
        nextreg 0x1A,16
        nextreg 0x1A,231
        nextreg 0x1A,0
        nextreg 0x1A,191
        ret
.scheduled:
        ld hl,V_BEAT
        ld a,(hl)
        inc a
        cp 3
        jr c,.index
        xor a
.index: ld (hl),a
        ld b,6
        cp 1
        jr nz,.six
        dec b                       ; 5, 6, 6
.six:   ld a,(V_LAST)
        add a,b
        ld b,a
.tick:  ld a,(TICK)
        sub b
        jr z,.line
        jp p,.line                  ; resume after a pause or cutscene
        jr .tick
.line:  ld bc,0x243B
.poll:  ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        and 1
        jr z,.poll
        ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        dec b
        cp low PRESENT_LINE
        jr nz,.poll
        ld a,(TICK)
        ld (V_LAST),a
        ret

; The moves after the last playfield pixel prepare the first stationary
; panel line. Restore the playfield after the last panel pixel of each frame.
cu_list:
        db 0xC0,151, 0x26,0
        db 0x1A,0, 0x1A,255, 0x1A,0, 0x1A,191
        db 0xC0,191, 0x26
cu_phase: db 0
        db 0x1A,16, 0x1A,231, 0x1A,0, 0x1A,191
        db 0xFF,0xFF
cu_end:
; The power gauge flashes fifteen times inside a single game update. Its two
; 4000-count delay calls alone would overrun even a six-frame slot at 28 MHz.
gauge_delay:
        push bc
        ld bc,1000
        jp 0x64A4                   ; same loop exit, stack and BC as the game
; Partial paint rows used variable-length rotation loops in the 1.2 renderer.
; Resolve the eight pixels in straight-line code to bound large cache misses.
smooth_paint:
        ld a,(V_TM)
        ld b,a
        ld a,(V_G)
        ld c,a
        ld a,(V_M)
        ld h,a
        ld a,(V_INK)
        ld d,a
        ld a,(V_PAP)
        ld e,a
        ld a,(V_KIND)
        cp 1
        jp z,.reverse
        AB_PAIR 0,1,0
        AB_PAIR 2,3,2
        AB_PAIR 4,5,4
        AB_PAIR 6,7,6
        ret
.reverse:
        AB_PAIR 7,6,0
        AB_PAIR 5,4,2
        AB_PAIR 3,2,4
        AB_PAIR 1,0,6
        ret
smooth_end:
