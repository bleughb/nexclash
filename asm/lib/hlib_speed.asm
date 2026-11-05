; Shared hook library: save and restore the caller's CPU speed (card patch.restore-speed).
; NEW engines only (Dean's rule, 2026-11-04): existing engines keep their own copies until a rework.
; Unit tests and negative control: nexclash/hooklib.py (selftest.py --tools).
;
; NextREG $07 read (core zxnext.vhd 5902; JNext 1.1.104 the same): bits 5:4 = the actual speed,
; bits 1:0 = the programmed one. The latch keeps bits 1:0, the speed the caller (the stub, the game,
; the F8 key or a speed option) last wrote, and the exit writes exactly that back - never a fixed 0.
; Port 0x243B is left selecting register 7: a Spectrum game never uses 0x243B / 0x253B, and NEXTREG
; never changes the selection (docs/NEXT_REGISTERS.md). A hook whose game does use them saves 0x243B.
; Each macro takes the latch byte's address: a hook that can run inside another hook (an ISR hook)
; uses its own latch, or the inner exit restores the outer's 28 MHz into the outer's latch.
; No DI / EI, no IX / IY / alternate registers. Usable with interrupts on.

; HLIB_SPEED_IN latch: latch the incoming speed, then 28 MHz. Keeps every register and flag;
; 4 bytes of stack below SP. 97 T at the incoming clock before the NEXTREG, 40 T after it.
        MACRO HLIB_SPEED_IN latch
        push af
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (latch),a
        nextreg 0x07,3
        pop bc
        pop af
        ENDM

; HLIB_SPEED_IN_ABC latch: the same without the stack; A, F, B, C are lost.
        MACRO HLIB_SPEED_IN_ABC latch
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (latch),a
        nextreg 0x07,3
        ENDM

; HLIB_SPEED_OUT latch: back to the latched speed. Keeps every register and flag; 2 bytes of stack.
        MACRO HLIB_SPEED_OUT latch
        push af
        ld a,(latch)
        nextreg 0x07,a
        pop af
        ENDM

; HLIB_SPEED_OUT_A latch: the same without the stack; A is lost, the flags are kept.
        MACRO HLIB_SPEED_OUT_A latch
        ld a,(latch)
        nextreg 0x07,a
        ENDM
