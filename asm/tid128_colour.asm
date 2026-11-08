; Treasure Island Dizzy: source-matched room colours, separate from default mode.
; Raw colour indices retain the original replacement/XOR/OR drawing operations.
; The ULA still receives every original scenery write; 255 falls through to it.
        DEVICE ZXSPECTRUMNEXT
HLIB_V_R EQU 0x5B30
C_SPEED EQU 0x5B33
C_IFF EQU 0x5B34
C_KIND EQU 0x5B35
C_EXIT EQU 0x5B36
I_START EQU 0x5B40
I_END EQU 0x5B41
I_AF EQU 0x5B42
I_BC EQU 0x5B44
I_DE EQU 0x5B46
I_HL EQU 0x5B48
I_TARGET EQU 0x5B4A
I_TEMP EQU 0x5B4C
I_ROUT EQU 0x5B4D
G_IM EQU 0x5B5C
M_R EQU 0x5B5D
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        ORG 0
hooks_start:
        INCLUDE "lib/hlib_r.asm"
        ORG 0x0038
        jp irq_entry
core_start EQU 0x0100

        ORG 0x2400
rom_start:
        MACRO ENTRY kind
        push af
        HLIB_IFF_DI
        push af
        ld a,kind
        jp enter
        ENDM
e_row: ENTRY 0
e_hi: ENTRY 1
e_lo: ENTRY 2
e_mhi: ENTRY 3
e_mlo: ENTRY 4
e_wipe: ENTRY 5
e_text: ENTRY 6
e_scroll: ENTRY 7
e_box: ENTRY 8
e_undo: ENTRY 9
e_bubbles: ENTRY 10
e_halves: ENTRY 11
enter:
        ld (C_KIND),a
        pop af
        jp po,.off
        ld a,1
        jp .store
.off:   ld a,0
        jp .store
.store: ld (C_IFF),a
        pop af
        HLIB_R_IN
        nextreg 0x50,28
        jp dispatch

; Two exits per site: identical displaced instructions, optional EI. No altered
; branch conditions or software drawing. All original instructions still run.
        MACRO EXIT_BEGIN label,enabled
label:
        nextreg 0x50,255
        IF enabled
        ei
        ENDIF
        ENDM
        MACRO ROW_EXIT label,enabled
        EXIT_BEGIN label,enabled
        dec hl
        ld a,(0x7871)
        jp 0x7BF1
        ENDM
        MACRO HI_EXIT label,enabled,target
        EXIT_BEGIN label,enabled
        ld (hl),a
        inc hl
        ld a,1
        jp target
        ENDM
        MACRO LO_EXIT label,enabled,target,mirror
        EXIT_BEGIN label,enabled
        ld (hl),a
        IF mirror
        dec de
        ELSE
        inc de
        ENDIF
        xor a
        jp target
        ENDM
        MACRO CLEAR_EXIT label,enabled,target
        EXIT_BEGIN label,enabled
.loop:  ld (hl),0
        inc hl
        djnz .loop
        jp target
        ENDM
        MACRO SCROLL_EXIT label,enabled
        EXIT_BEGIN label,enabled
        ldir
        dec a
        jp 0x75CE
        ENDM
        MACRO BOX_EXIT label,enabled
        EXIT_BEGIN label,enabled
        ld (hl),c
        inc hl
        inc de
        jp 0xE863
        ENDM
        MACRO UNDO_EXIT label,enabled
        EXIT_BEGIN label,enabled
        ld (hl),a
        inc hl
        inc de
        jp 0xE8FE
        ENDM
        MACRO BUBBLES_EXIT label,enabled
        EXIT_BEGIN label,enabled
        ld a,(ix+2)
        jp 0xF59E
        ENDM
        ROW_EXIT x_row0,0
        ROW_EXIT x_row1,1
        HI_EXIT x_hi0,0,0x7C60
        HI_EXIT x_hi1,1,0x7C60
        LO_EXIT x_lo0,0,0x7C75,0
        LO_EXIT x_lo1,1,0x7C75,0
        HI_EXIT x_mhi0,0,0x7C97
        HI_EXIT x_mhi1,1,0x7C97
        LO_EXIT x_mlo0,0,0x7CB2,1
        LO_EXIT x_mlo1,1,0x7CB2,1
        CLEAR_EXIT x_wipe0,0,0xAF9E
        CLEAR_EXIT x_wipe1,1,0xAF9E
        CLEAR_EXIT x_text0,0,0x7716
        CLEAR_EXIT x_text1,1,0x7716
        SCROLL_EXIT x_scroll0,0
        SCROLL_EXIT x_scroll1,1
        BOX_EXIT x_box0,0
        BOX_EXIT x_box1,1
        UNDO_EXIT x_undo0,0
        UNDO_EXIT x_undo1,1
        BUBBLES_EXIT x_bubbles0,0
        BUBBLES_EXIT x_bubbles1,1
        EXIT_BEGIN x_halves0,0
        ld a,(0x7871)
        jp 0x7C32
        EXIT_BEGIN x_halves1,1
        ld a,(0x7871)
        jp 0x7C32
; A real interrupt can arrive while Layer 2/source pages replace game slots.
; Forward it immediately, at the incoming game speed and original mappings.
; Save only transient colour state; persistent canvas/undo writes made by the
; original ISR's own drawing hooks are retained. The original handler runs once.
        ORG 0x2800
irq_entry:
        push af
        ld a,r
        ld (I_START),a          ; after vector JP / PUSH / LD A,R: entry R + 4
        nextreg 0xC8,1          ; this ULA interrupt is now being serviced
        push bc
        push de
        push hl
        push ix
        push iy
        ld (I_BC),bc
        ld (I_DE),de
        ld (I_HL),hl
        ld hl,10
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (I_AF),de
        ld hl,0x5B30
        ld b,4
.cs:    ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        djnz .cs
        ld hl,state_start
        ld b,(state_end-state_start)/2
.vs:    ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        djnz .vs
        ld bc,0x243B
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        push af
        dec b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        push af
        ld a,(old53)
        nextreg 0x53,a
        ld a,(old54)
        nextreg 0x54,a
        ld a,(G_IM)
        cp 1
        ld hl,0x0038
        jr z,.im1
        im 2
        ld hl,(0xFEFF)
        jr .target
.im1:   im 1
.target:ld (I_TARGET),hl
        ld a,(I_START)
        sub 6
        and 0x7F
        ld b,a
        ld a,(I_START)
        and 0x80
        or b
        ld (I_ROUT),a
        ld hl,irq_return
        push hl
        ld hl,(I_TARGET)
        push hl
        ld hl,(I_AF)
        push hl
        pop af
        ld bc,(I_BC)
        ld de,(I_DE)
        ld hl,(I_HL)
        HLIB_SPEED_OUT C_SPEED
        nextreg 0x50,255
        ld (I_TEMP),a
        ld a,(I_ROUT)
        ld r,a
        ld a,(I_TEMP)
        ret                     ; original handler, with original entry R and registers
irq_return:
        di
        push af
        ld a,r
        ld (I_END),a             ; original handler's returned R + 4
        pop af
        nextreg 0x07,3
        nextreg 0x50,28
        pop af
        nextreg 0x54,a
        pop af
        nextreg 0x53,a
        ld hl,state_end-1
        ld b,(state_end-state_start)/2
.vr:    pop de
        ld (hl),d
        dec hl
        ld (hl),e
        dec hl
        djnz .vr
        ld hl,0x5B37
        ld b,4
.cr:    pop de
        ld (hl),d
        dec hl
        ld (hl),e
        dec hl
        djnz .cr
        ; Credit original ISR M1s + the hardware acknowledge to the outer R
        ; budget. Hook work itself is still removed by HLIB_R_OUT at its exit.
        ld a,(I_START)
        ld c,a
        ld a,(I_END)
        sub c
        inc a
        ld b,a
        ld a,(HLIB_V_R)
        ld c,a
        add a,b
        and 0x7F
        ld b,a
        ld a,c
        and 0x80
        or b
        ld (HLIB_V_R),a
        ld a,(I_END)
        sub 7                   ; 4 capture M1s, 3 after the final LD R,A
        and 0x7F
        ld b,a
        ld a,(I_END)
        and 0x80
        or b
        ld (I_ROUT),a
        im 1                    ; private vector only while the colour hook runs
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld (I_TEMP),a
        ld a,(I_ROUT)
        ld r,a
        ld a,(I_TEMP)
        ei
        ret

; Keep the original room rendering routine at the fast clock.
; Every original opcode still runs, including clipping and self-modification.
; The game's IRQ wrapper temporarily restores the caller's clock for music.
        ORG 0x2C00
S_R EQU 0x5B50
S_OUT EQU 0x5B51
S_TEMP EQU 0x5B52
S_SPEED EQU 0x5B53
S_ACTIVE EQU 0x5B54
S_IFF EQU 0x5B55
S_HL EQU 0x5B56
Q_R EQU 0x5B58
Q_OUT EQU 0x5B59
Q_TEMP EQU 0x5B5A
Q_SPEED EQU 0x5B5B
        MACRO SR_IN addr
        push af
        ld a,r
        ld (addr),a
        pop af
        ENDM
        MACRO SR_OUT addr
        ld (addr+2),a
        ld a,(addr+1)
        ld r,a
        ld a,(addr+2)
        ENDM
        MACRO SR_SET addr,delta
        push af
        push bc
        ld a,(addr)
        ld b,a
        add a,delta
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld (addr+1),a
        pop bc
        pop af
        ENDM
scope_entry:
        push af
        HLIB_IFF_DI
        jp po,.off
        ld a,1
        jp .save
.off:   ld a,0
        jp .save
.save:  ld (S_IFF),a
        pop af
        SR_IN S_R
        HLIB_SPEED_IN S_SPEED
        push af
        ld a,1
        ld (S_ACTIVE),a
        pop af
        ld (S_HL),hl
        ld hl,scope_return
        push hl
        ld hl,(S_HL)
        SR_SET S_R,-19
        push af
        ld a,(S_IFF)
        or a
        jr z,.offout
        pop af
        SR_OUT S_R
        ei
        call 0xF4E2
        jp 0xAFE2
.offout:pop af
        SR_SET S_R,-18
        SR_OUT S_R
        call 0xF4E2
        jp 0xAFE2
scope_return:
        push af
        HLIB_IFF_DI
        jp po,.off
        ld a,1
        jp .save
.off:   ld a,0
        jp .save
.save:  ld (S_IFF),a
        pop af
        SR_IN S_R
        push af
        xor a
        ld (S_ACTIVE),a
        pop af
        HLIB_SPEED_OUT S_SPEED
        SR_SET S_R,-18
        push af
        ld a,(S_IFF)
        or a
        jr z,.offout
        pop af
        SR_OUT S_R
        ei
        ret
.offout:pop af
        SR_SET S_R,-17
        SR_OUT S_R
        ret

; IM2 game IRQ entry/exit: only change speed inside a scenery scope. It starts
; with DI already; colour hooks called from the handler keep their own latch.
game_irq_entry:
        di
        SR_IN Q_R
        push af
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (Q_SPEED),a
        ld a,(S_ACTIVE)
        or a
        jr z,.same
        ld a,(S_SPEED)
        nextreg 7,a
.same:  nextreg 0xC8,1
        pop bc
        pop af
        SR_SET Q_R,-6
        SR_OUT Q_R
        push af
        push bc
        jp 0xEF9E

game_irq_exit:
        SR_IN Q_R
        HLIB_SPEED_OUT Q_SPEED
        SR_SET Q_R,-6
        SR_OUT Q_R
        pop hl
        pop de
        pop bc
        jp 0xEFBC

mode2:
        SR_IN M_R
        push af
        ld a,2
        ld (G_IM),a
        pop af
        SR_SET M_R,-6
        SR_OUT M_R
        im 2
        ld a,195
        jp 0xEF7F
mode1:
        SR_IN M_R
        push af
        ld a,1
        ld (G_IM),a
        pop af
        SR_SET M_R,-6
        SR_OUT M_R
        im 1
        ei
        jp 0xEF9A

; Bubble list erase/redraw is called from the original ISR with IFF off.
; Run its original drawing loop at 28 MHz, then return before the AY routine.
B_R EQU 0x5B60
B_SPEED EQU 0x5B63
B_HL EQU 0x5B64
bubble_scope:
        SR_IN B_R
        HLIB_SPEED_IN B_SPEED
        ld (B_HL),hl
        ld hl,bubble_return
        push hl
        ld hl,(B_HL)
        SR_SET B_R,-6
        SR_OUT B_R
        ld a,(0xB10B)
        jp 0xF4FA
bubble_return:
        SR_IN B_R
        HLIB_SPEED_OUT B_SPEED
        SR_SET B_R,-5
        SR_OUT B_R
        ret

rom_end:
        ASSERT rom_end < 0x3000
        SAVEBIN "tidc_rom.bin",rom_start,rom_end-rom_start

        ORG core_start
dispatch:
        HLIB_SPEED_IN C_SPEED
        push af
        push bc
        push de
        push hl
        push ix
        ld (src),de
        ld (dst),hl
        ld (ixsrc),ix
        ld a,b
        ld (count),a
        ld (scroll_n),bc
        ld a,(0x7741)
        ld (mode),a
        ld a,(0x7BF3)
        cp 0xCD
        ld a,0
        jr nz,.mirror_set
        inc a
.mirror_set:
        ld (mirror),a
        ld a,(0x7871)
        ld (width),a
        ld bc,0x243B
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (old53),a
        dec b
        ld a,0x54
        out (c),a
        inc b
        in a,(c)
        ld (old54),a
        ld a,(C_IFF)
        or a
        jr z,.no_irq
        im 1
        ei
.no_irq:
        ld a,(C_KIND)
        ld l,a
        ld h,0
        add hl,hl
        ld de,handlers
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        jp (hl)
handlers:
        dw row,hi,lo,mhi,mlo,clear,clear,scroll,box,undo,bubbles,halves
exits:
        dw x_row0,x_row1,x_hi0,x_hi1,x_lo0,x_lo1,x_mhi0,x_mhi1
        dw x_mlo0,x_mlo1,x_wipe0,x_wipe1,x_text0,x_text1
        dw x_scroll0,x_scroll1,x_box0,x_box1,x_undo0,x_undo1
        dw x_bubbles0,x_bubbles1
        dw x_halves0,x_halves1

; HL = Spectrum screen-byte address. Page is 32..37, mapped into slot 3.
; BC = its first pixel in 0x6000..0x7FFF, A = page. Every byte stays in one page.
pixelptr:
        ld a,h
        and 0x18
        rrca
        rrca
        ld b,a
        ld a,l
        rlca
        ld a,b
        adc a,32
        nextreg 0x53,a
        ld a,l
        and 0x60
        rrca
        rrca
        ld b,a
        ld a,h
        and 7
        or b
        or 0x60
        ld b,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld c,a
        ret

; Source graphic at (src), eight source-owned indices into pix. The importer
; validates graphic identities; only expanded colour planes enter these banks.
fetch:
        ld hl,(src)
        ld a,h
        sub 0x40
        srl a
        srl a
        add a,40
        nextreg 0x54,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ld de,pix
        DUP 8
        ldi
        EDUP
        ret
reverse:
        ld hl,pix
        ld de,pix+7
        ld b,4
.loop:  ld c,(hl)
        ld a,(de)
        ld (hl),a
        ld a,c
        ld (de),a
        inc hl
        dec de
        djnz .loop
        ret

row:
        ld a,(width)
        add a,a
        ld (count),a
        ld a,1
        ld (half),a           ; full byte starts at destination bit zero
        ld a,0
        ld (source_offset),a
        jr bulk_start

mhi:    call fetch
        call reverse
        jr half_hi
hi:     call fetch
half_hi:
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        inc l
        inc l
        inc l
        inc l
        ld de,pix
        ld b,4
        call paint
        jp done
halves:
        ld a,(0x7872)
        ld (half),a
        add a,a
        add a,a
        ld (source_offset),a
        ld a,(width)
        ld (count),a
bulk_start:
        ld hl,(src)
        ld a,h
        sub 0x40
        srl a
        srl a
        add a,40
        ld (source_page),a
        nextreg 0x54,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        set 7,h
        ld a,(source_offset)
        ld e,a
        ld d,0
        ld a,(mirror)
        or a
        jr z,.source
        ld a,e
        xor 7
        ld e,a
.source:add hl,de
        ld (src),hl
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        ld a,(half)
        or a
        jr nz,.destination
        inc hl
        inc hl
        inc hl
        inc hl
.destination:
        ld de,(src)
.loop:  ld a,(mirror)
        or a
        jr nz,.reverse
        ld a,(mode)
        cp 1
        jr z,.xor
        cp 2
        jr z,.or
        DUP 4
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        EDUP
        jr .forward_step
.xor:   DUP 4
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
        jr .forward_step
.or:    DUP 4
        ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
.forward_step:
        ld a,d
        cp 0xA0
        jr nz,.next
        ld d,0x80
        ld a,(source_page)
        inc a
        jr .page
.reverse:
        ld a,(mode)
        cp 1
        jr z,.rxor
        cp 2
        jr z,.ror
        DUP 4
        ld a,(de)
        ld (hl),a
        dec de
        inc hl
        EDUP
        jr .back_step
.rxor:  DUP 4
        ld a,(de)
        xor (hl)
        ld (hl),a
        dec de
        inc hl
        EDUP
        jr .back_step
.ror:   DUP 4
        ld a,(de)
        or (hl)
        ld (hl),a
        dec de
        inc hl
        EDUP
.back_step:
        ld a,d
        cp 0x7F
        jr nz,.next
        ld d,0x9F
        ld a,(source_page)
        dec a
.page:  ld (source_page),a
        nextreg 0x54,a
.next:  ld a,(count)
        dec a
        ld (count),a
        jp nz,.loop
        jp done

mlo:    call fetch
        call reverse
        jr half_lo
lo:     call fetch
half_lo:
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        ld de,pix+4
        ld b,4
        call paint
        jp done
paint:
        ld a,(mode)
        cp 1
        jr z,.xor
        cp 2
        jr z,.or
.replace:
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        djnz .replace
        ret
.xor:   ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        djnz .xor
        ret
.or:    ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        inc hl
        djnz .or
        ret
clear:
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        ld a,(count)
        ld c,a
        ld b,0
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        ld d,h
        ld e,l
        inc de
        ld (hl),0
        dec bc
        ldir
        jp done
scroll:
        ; The game copies 20 bytes per row. Source/destination can span pages.
        ld hl,(dst)
        ld de,(src)
        ld (src),hl
        ld (dst),de
.loop:  ld hl,(src)
        call pixelptr
        ld h,b
        ld l,c
        ld de,pix
        DUP 8
        ldi
        EDUP
        ld hl,(dst)
        call pixelptr
        ld d,b
        ld e,c
        ld hl,pix
        DUP 8
        ldi
        EDUP
        ld hl,(src)
        inc hl
        ld (src),hl
        ld hl,(dst)
        inc hl
        ld (dst),hl
        ld hl,(scroll_n)
        dec hl
        ld (scroll_n),hl
        ld a,h
        or l
        jr nz,.loop
        jp done
box:
        ld hl,(src)
        call undoptr
        ld (undo_at),hl
        ld hl,(ixsrc)
        ld (src),hl
        call fetch
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        ld de,pix
        ld ix,(undo_at)
        ld b,8
.loop:  ld a,(de)
        xor (hl)
        ld (ix+0),a
        ld a,(de)
        ld (hl),a
        inc hl
        inc de
        inc ix
        djnz .loop
        jp done
undoptr:
        ; The original box undo addresses are 0x72BB..0x7324. Keep 256 bytes
        ; of indices (2 KB) in the private hook page; never borrow game RAM.
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,colour_undo
        add hl,de
        ret
undo:
        ld hl,(src)
        call undoptr
        ex de,hl
        jp xor8
bubbles:
        ; All sixteen bubble source bytes share one expanded colour page.
        ; Read it directly while XORing each scanline; no staging copy.
        ld ix,(ixsrc)
        ld a,(ix+0)
        and 1
        ld (mirror),a
        ld a,(ix+0)
        srl a
        ld (width),a
        ld a,(ix+2)
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x9160
        add hl,de
        ld (src),hl
        ld l,(ix+1)
        ld h,0
        add hl,hl
        ld de,29729
        add hl,de
        ld (ixsrc),hl
        nextreg 0x54,85
        ld a,4
        ld (count),a
.loop:  ld a,(old53)
        nextreg 0x53,a
        ld ix,(ixsrc)
        ld l,(ix+0)
        ld h,(ix+1)
        ld a,(width)
        ld e,a
        ld d,0
        add hl,de
        call pixelptr
        ld h,b
        ld l,c
        ld de,(src)
        ld a,(mirror)
        or a
        jr nz,.rotated
        DUP 8
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
        jr .next
.rotated:
        push de
        inc e
        inc e
        inc e
        inc e
        DUP 4
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
        pop de
        DUP 4
        ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        EDUP
.next:  ld hl,(src)
        ld de,8
        add hl,de
        ld (src),hl
        ld hl,(ixsrc)
        inc hl
        inc hl
        ld (ixsrc),hl
        ld a,(count)
        dec a
        ld (count),a
        jp nz,.loop
        jp done

xor8:
        ld hl,(dst)
        call pixelptr
        ld h,b
        ld l,c
        ld b,8
.loop:  ld a,(de)
        xor (hl)
        ld (hl),a
        inc de
        inc hl
        djnz .loop
done:
        di
        ld a,(C_IFF)
        or a
        jr z,.irq_done
        ld a,(G_IM)
        cp 2
        jr nz,.irq_done          ; initial ROM IM1 startup has no game ISR latch
        ld bc,0x243B
        ld a,0xC8
        out (c),a
        inc b
        in a,(c)
        and 1
        jr z,.irq_done
        ; A pulse during entry/exit's short DI window is latched by INT status.
        ; RST contributes the acknowledge M1; the same forwarding path services
        ; it once. The game ISR clears the latch on normal hardware entry too.
        rst 0x38
        di
.irq_done:
        ld a,(G_IM)
        cp 1
        jr z,.im1
        im 2
        jr .im_done
.im1:   im 1
.im_done:
        ld a,(old53)
        nextreg 0x53,a
        ld a,(old54)
        nextreg 0x54,a
        ld a,(C_KIND)
        add a,a
        ld l,a
        ld a,(C_IFF)
        add a,l
        ld l,a
        ld h,0
        add hl,hl
        ld de,exits
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (C_EXIT),de
        ld a,(C_IFF)
        ld b,a
        ld a,102
        sub b                   ; E=21, exit=5 plus EI, displaced instructions cancel
        call hlib_r_set
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,(C_EXIT)
        ex (sp),hl
        HLIB_SPEED_OUT C_SPEED
        HLIB_R_OUT
        ret
state_start:
src:    dw 0
dst:    dw 0
ixsrc:  dw 0
undo_at: dw 0
scroll_n: dw 0
mode:   db 0
mirror: db 0
width:  db 0
count:  db 0
old53:  db 0
old54:  db 0
pix:    ds 8
half:   db 0,0
source_page: db 0
source_offset: db 0
state_end:
hooks_end:
        ASSERT hooks_end < 0x1000
colour_undo EQU 0x1000
        SAVEBIN "tidc_hooks.bin",hooks_start,hooks_end-hooks_start

        ORG 0x1100
isr_clear:
        nextreg 0xC8,1
        jp 0                   ; builder relocates to the default hlib ISR entry
        SAVEBIN "tidc_irqclear.bin",isr_clear,$-isr_clear

        ORG 0xD200
setup_start:
        nextreg 0xC8,1
        nextreg 0x12,16
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,palette
        ld b,0
.pal:   ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pal
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld b,16
.spr:   ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .spr
        nextreg 0x43,0
        ld bc,0x123B
        ld a,2
        out (c),a
        ret
palette:
        SAVEBIN "tidc_setup.bin",setup_start,palette-setup_start
