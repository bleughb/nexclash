; Pyjamarama (Mikro-Gen 1984, 48K) - every moving figure as a hardware sprite.
; Hooks + state in RAM page PAGE at 0x2000-0x3FFF (MMU slot 1) for the whole game; the game's own ROM use
; (IM 1 handler, keyboard scan) is all below 0x2000.
;
; Method (games/pyjamarama.md): a pure XOR plotter 43758 (A = graphic, (43755) x, (43756) y; 16 x 16, 1 bit)
; draws every figure on the screen, and a second identical call rubs it out. All logic runs unchanged. For a
; figure the hook turns the plotter's three screen writes into NOPs and toggles (A, x, y) in a list: found =
; rubbed out, not found = drawn. The list becomes sprite attributes at the game's delay routine 44092, which
; every animation loop calls once per step. Patterns are uploaded when first needed, from pages PAT..,
; since the 164 figure graphics are more than the 128 slots.
; The player's own attribute block (44801 paints 70 over 2-3 x 4-5 cells): the three LD (HL),70 write back
; the value just read instead, so the saved block is the same as the original's and the scenery keeps its colours.
;
; Sites (original bytes checked by pyjamarama.py):
;   43758 F3 F5 E5      DI / PUSH AF / PUSH HL       -> JP e_plot
;   44092 C5 F5 01      PUSH BC / PUSH AF / LD BC,nn -> JP e_wait (the operand stays, read at run time)
;   57896 E5 C5 D5      PUSH HL / PUSH BC / PUSH DE  -> JP e_wipe (room change: clears the play area)
;   44969 21 00 40      LD HL,16384                  -> JP e_clr  (whole screen clear)
;   44902, 44908, 44920 36 46  LD (HL),70            -> 77 00  LD (HL),A / NOP
; Written at run time: 43840, 43844, 43848 (LD (HL),A = 77, or NOP = 00).

        DEVICE ZXSPECTRUMNEXT

NMAX    EQU 32          ; figures at once (the recordings reach 10)
XPOS    EQU 43755
YPOS    EQU 43756
YMIN    EQU 40          ; above this: the HUD, stays on the ULA
PATPAGE EQU 26          ; patterns, 64 per 8K page
HOME3   EQU 11          ; what slot 3 normally holds

        INCLUDE "lib/hlib_speed.asm"
HLIB_V_R EQU rstate
        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"
; ---- 43758 ----
e_plot: di
        ld (t_sp),sp
        ld sp,stk
        push af
        HLIB_R_IN
        HLIB_SPEED_IN speed
        push bc
        push de
        push hl
        push af
        ld a,-21
        call hlib_r_set
        pop af
        ld c,a
        ld h,high pidx
        ld l,a
        ld a,(hl)
        inc a
        jr z,.ula               ; 0xFF: an item or an icon, stays on the ULA
        ld a,(YPOS)
        cp YMIN
        jr c,.ula
        call toggle
        xor a                   ; NOP
        jr .set
.ula:   ld a,0x77               ; LD (HL),A
.set:   ld (43840),a
        ld (43844),a
        ld (43848),a
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        HLIB_SPEED_OUT speed
        ld sp,(t_sp)
        push af
        push hl
        jp 43761

; C = graphic. Found in the list: remove it. Else add it.
toggle: ld de,(XPOS)            ; E = x, D = y
        ld a,1
        ld (dirty),a
        ld a,(nl)
        ld b,a
        ld hl,lst
        or a
        jr z,.add
.s:     ld a,(hl)
        cp c
        jr nz,.nx
        inc l
        ld a,(hl)
        dec l
        cp e
        jr nz,.nx
        inc l
        inc l
        ld a,(hl)
        dec l
        dec l
        cp d
        jr z,.del
.nx:    ld a,l
        add a,4
        ld l,a
        djnz .s
.add:   ld a,(nl)
        cp NMAX
        ret nc                  ; full: not shown (the verifier counts it; the recordings reach 10)
        inc a
        ld (nl),a
        ld (hl),c
        inc l
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld (hl),0xFF            ; no slot yet: the search below must not see an old one
        push hl
        call slotfor
        pop hl
        ld (hl),a
        ret
.del:   ld a,(nl)               ; the last entry moves into the gap
        dec a
        ld (nl),a
        add a,a
        add a,a
        ld e,a
        ld d,high lst
        ld b,4
.m:     ld a,(de)
        ld (hl),a
        inc e
        inc l
        djnz .m
        ret

; C = graphic -> A = its pattern slot, uploaded if need be. Never takes a slot on show.
slotfor:
        ld h,high slotof
        ld l,c
        ld a,(hl)
        cp 0xFF
        ret nz
.next:  ld a,(rr)
        inc a
        and 127
        ld (rr),a
        ld e,a
        ld a,(nl)
        ld b,a
        ld hl,lst+3
.chk:   ld a,(hl)
        cp e
        jr z,.next              ; on show: try the next
        ld a,l
        add a,4
        ld l,a
        djnz .chk
        ld h,high owner         ; E = free slot
        ld l,e
        ld a,(hl)
        ld (hl),c
        cp 0xFF
        jr z,.fresh
        ld l,a
        ld h,high slotof
        ld (hl),0xFF            ; the old graphic loses it
.fresh: ld h,high slotof
        ld l,c
        ld (hl),e
        ld a,e                  ; port 0x303B: bits 5-0 the 256-byte slot, bit 7 the 128-byte half
        srl a
        jr nc,.ev
        or 0x80
.ev:    push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld h,high pidx
        ld l,c
        ld a,(hl)               ; pattern number
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl               ; H = 64-pattern page; L bits 7-2
        ld a,h
        add a,PATPAGE
        nextreg 0x53,a
        ld a,l
        ld l,0                  ; address = 0x6000 + (n & 63) * 128
        ld h,a                  ; n bits 5-0 in H bits 7-2
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        ld a,h
        or 0x60
        ld h,a
        ld bc,0x805B            ; 128 bytes
        otir
        nextreg 0x53,HOME3
        ld a,e
        ret

; ---- 44092: the list becomes sprites, then the routine as usual ----
e_wait: ld (t_sp),sp
        ld sp,stk
        push af
        HLIB_R_IN
        HLIB_SPEED_IN speed
        ld a,-19
        call hlib_r_set
        ld a,(dirty)
        or a
        call nz,commit
        HLIB_R_OUT
        pop af
        HLIB_SPEED_OUT speed
        ld sp,(t_sp)
        push bc
        push af
        ld bc,(44095)
        jp 44097

; No register kept but SP and PC: callers save what they need.
commit: push bc
        push de
        push hl
        xor a
        ld (dirty),a
        ld hl,lst
        ld c,a
        ld a,(nl)
        ld b,a
        or a
        jr z,.hide
.n:     ld a,c
        nextreg 0x34,a
        inc l                   ; the graphic: not needed here
        ld a,(hl)
        inc l
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,a                 ; x bit 8
        ld e,a
        ld a,(hl)
        inc l
        add a,32
        nextreg 0x36,a
        ld a,e
        nextreg 0x37,a
        ld a,(hl)
        inc l
        srl a                   ; carry = the 128-byte half
        ld d,a
        ld a,0
        rra
        rra
        or 0x80                 ; 4-bit; bit 6 = N6
        ld e,a
        ld a,d
        or 0xC0                 ; visible, attribute 4 follows
        nextreg 0x38,a
        ld a,e
        nextreg 0x39,a
        inc c
        djnz .n
.hide:  ld a,(shown)
        ld b,a
        ld a,c
        ld (shown),a
.h:     ld a,c
        cp b
        jr nc,.d
        nextreg 0x34,a
        xor a
        nextreg 0x38,a
        inc c
        jr .h
.d:     pop hl
        pop de
        pop bc
        ret

; ---- room change and whole screen clear: nothing is drawn any more ----
e_wipe: ld (t_ret),sp
        ld sp,stk2
        push af
        HLIB_R_IN
        HLIB_SPEED_IN speed
        ld a,-18
        call hlib_r_set
        call wipe2
        HLIB_R_OUT
        pop af
        HLIB_SPEED_OUT speed
        ld sp,(t_ret)
        push hl
        push bc
        push de
        jp 57899

e_clr:  ld (t_ret),sp
        ld sp,stk2
        push af
        HLIB_R_IN
        HLIB_SPEED_IN speed
        ld a,-18
        call hlib_r_set
        call wipe2
        HLIB_R_OUT
        pop af
        HLIB_SPEED_OUT speed
        ld sp,(t_ret)
        ld hl,16384
        jp 44972

wipe2:  push af
        xor a
        ld (nl),a
        call commit
        pop af
        ret

code_end:
        ds 32
stk2:
t_sp:   dw 0
t_ret:  dw 0
nl:     db 0            ; figures in the list
shown:  db 0            ; sprites on show
rstate: ds 3
speed:  db 0
dirty:  db 0
rr:     db 127          ; last slot handed out
regs:   ds 20           ; register block for the start-up tail
        ds 40
stk:
        ALIGN 256
lst:    ds 256          ; NMAX x (graphic, x, y, slot)
pidx:   ds 256          ; graphic -> pattern number, 0xFF = stays on the ULA (filled by the build)
slotof: ds 256          ; graphic -> slot, 0xFF = none (filled by the build)
owner:  ds 128          ; slot -> graphic, 0xFF = none (filled by the build)
page_end:

; --- setup routine (stub bank, 0xD000): palette, hide all, clip, sprites on ---
        ORG 0xD000
setup:  nextreg 0x4B,0
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.c:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .c
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
; 0 transparent, then the Spectrum's colours (nexclash colour slots, recolour's 1-15)
pal:    db 0x00,0xFF,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFC
setup_end:

        SAVEBIN "pj_page.bin",0x2000,page_end-0x2000
        SAVEBIN "pj_setup.bin",0xD000,setup_end-0xD000
