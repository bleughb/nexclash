; Treasure Island Dizzy 128K v1.1. Jon Attree; based on Dean Woodyatt's TID sprites.
; Original 48K and published 128K engines remain separate. The player still uses
; Dean's pattern table and hardware plot at 0x0006; the bubble read at 0x0076.
; Every entry saves R before its own work. Original plot runs with its original
; stack and an exchanged return address, then the shared limiter repays its time.
        DEVICE ZXSPECTRUMNEXT
V_KIND          EQU 0x5B01
HLIB_V_R        EQU 0x5B02
V_SPEED         EQU 0x5B05
V_IFF           EQU 0x5B06
V_RET           EQU 0x5B07
V_FRAME         EQU 0x5B09
V_X             EQU 0x5B0A
V_Y             EQU 0x5B0B
V_TARGET        EQU 0x5B0C
HLIB_V_PACE     EQU 0x5B10
HLIB_PACE_NL    EQU 311
        DEFINE HLIB_PACE_LEAN
        DEFINE HLIB_IFF_FIXED_R
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_iff.asm"

        ORG 0x0300
hooks_start:
        INCLUDE "lib/hlib_r.asm"
core_start EQU $

        ORG 0x2200
tramp_start:
        MACRO ENTRY kind
        push af
        HLIB_IFF_DI              ; protect shared state before writing even the hook kind
        push af
        ld a,kind
        jp enter
        ENDM
e_plot: ENTRY 0
e_erase: ENTRY 1
e_wipe: ENTRY 2
e_isr: ENTRY 3
e_bub: ENTRY 4
enter:  ld (V_KIND),a
        pop af
        jp po,.off
        ld a,1
        jp .store
.off:   ld a,0
        jp .store               ; both paths have exactly the same M1 count
.store: ld (V_IFF),a
        pop af
        HLIB_R_IN
        nextreg 0x50,21
        jp dispatch
xret_off:
        nextreg 0x50,255
        ret
xret_on:
        nextreg 0x50,255
        ei
        ret
xerase:
        nextreg 0x50,255
        ld (40142),sp
        jp 40092
xwipe_off:
        nextreg 0x50,255
        ld ix,29825
        jp 44935
xwipe_on:
        nextreg 0x50,255
        ei
        ld ix,29825
        jp 44935
xisr:
        nextreg 0x50,255
        jp 0x7202
xisr_on:
        nextreg 0x50,255
        ei
        jp 0x7202
; Default-mode bubble-list drawing can overrun one music interrupt when its
; virtual-player reads are added at 3.5 MHz. Run the original list at 28 MHz,
; restore its caller clock before AY, and keep a separate nested R latch.
DB_R EQU 0x5B30
DB_SPEED EQU 0x5B33
DB_HL EQU 0x5B34
        MACRO BR_IN addr
        push af
        ld a,r
        ld (addr),a
        pop af
        ENDM
        MACRO BR_OUT addr
        ld (addr+2),a
        ld a,(addr+1)
        ld r,a
        ld a,(addr+2)
        ENDM
        MACRO BR_SET addr,delta
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
bscope_entry:
        BR_IN DB_R
        HLIB_SPEED_IN DB_SPEED
        ld (DB_HL),hl
        ld hl,bscope_return
        push hl
        ld hl,(DB_HL)
        BR_SET DB_R,-6
        BR_OUT DB_R
        ld a,(0xB10B)
        jp 0xF4FA
bscope_return:
        BR_IN DB_R
        HLIB_SPEED_OUT DB_SPEED
        BR_SET DB_R,-5
        BR_OUT DB_R
        ret

tramp_end:
        ASSERT tramp_end < 0x2400
        SAVEBIN "tid_tramp.bin",tramp_start,tramp_end-tramp_start

        ORG core_start
dispatch:
        HLIB_SPEED_IN V_SPEED
        push af
        ld a,(V_KIND)
        or a
        jp z,hplot
        dec a
        jp z,herase
        dec a
        jp z,hwipe
        dec a
        jp z,hisr
        jp hbub

hplot:  pop af
        push af
        push bc
        push de
        push hl
        ld (V_FRAME),a
        ld a,e
        ld (V_X),a
        ld a,l
        ld (V_Y),a
        ld hl,8
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_RET),de
        ld de,post_plot
        ld (hl),d
        dec hl
        ld (hl),e
        call hlib_pace_open
        ld a,(V_FRAME)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,plot_times
        add hl,de
        ld a,(V_X)
        and 1
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_TARGET),de
        ld a,106                ; entry captured at original R+21; target R+1, final LD/JP two M1
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        jp 39774

post_plot:
        HLIB_R_IN               ; original plot has now returned, including original RET M1
        push af
        push bc
        push de
        push hl
        ld a,(V_X)
        ld e,a
        ld a,(V_Y)
        ld l,a
        ld a,(V_FRAME)
        call 0x0006             ; Dean's four hardware-sprite placements
        ld hl,(V_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
        ld a,120                ; captured R+3; final LD/JP/NEXTREG/RET adds five
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,(V_RET)
        ex (sp),hl              ; original return address back in its original dead stack slot
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xret_off             ; the original plot always returns DI

herase: pop af
        push af
        xor a
        ld (0x5B00),a
        ld a,103                ; target +3 (DI, LD(nn),SP); captured +21, final path seven
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xerase

hwipe:  pop af
        push af
        xor a
        ld (0x5B00),a
wipe_hide:
        nextreg 0x15,0
        ld a,(V_IFF)
        or a
        ld a,102                ; target +2 (LD IX,nn); captured +21, off path seven
        jr z,.off
        dec a                   ; on path has EI too
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xwipe_on
.off:   call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xwipe_off

hisr:   pop af
        push af
        ld a,(0x5B00)
        or a
        jr nz,isr_shown
isr_hide:
        nextreg 0x15,0
isr_shown:
        ld a,(V_IFF)
        or a
        ld a,103                ; target +1 (CALL sound); captured +21, final five
        jr z,.off
        dec a                   ; this site is also reached outside an interrupt
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xisr_on
.off:
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xisr

hbub:   pop af
        call 0x0076             ; Dean's virtual pixel read, preserves the game's bubble collision
        push af
        ld a,(V_IFF)
        or a
        ld a,112                ; whole original CALL + pixel test = 10 M1; captured +21, final five
        jr z,.off
        dec a
        call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xret_on
.off:   call hlib_r_set
        pop af
        HLIB_SPEED_OUT V_SPEED
        HLIB_R_OUT
        jp xret_off

        INCLUDE "lib/hlib_pace.asm"
hooks_end:
        ASSERT hooks_end < 0x1000
        SAVEBIN "tid_hooks.bin",hooks_start,hooks_end-hooks_start
plot_times EQU 0x1000            ; 39 x 2 little-endian 1/16-line budgets, measured from original code
