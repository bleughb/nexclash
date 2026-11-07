; Shared hook library: read and restore the caller's interrupt state safely (card patch.iff-safe-read).
; Unit tests and negative control: nexclash/hooklib.py (selftest.py --tools); the static check of every
; LD A,I / LD A,R in asm/ is hooklib.iff_audit.
;
; LD A,I / LD A,R copy IFF2 into P/V. On the NMOS Z80 - and in JNext (Quazatron, 2026-11-06: 31 interrupts
; missed in 1,400 frames; whether the Next's own core does it is untested, the double read is right either
; way) - an interrupt ACCEPTED at the end of that instruction leaves P/V = 0 although interrupts were on:
; the handler runs, returns with EI, and a hook that then trusts P/V (JP PO / RET PO past its EI) leaves
; interrupts off until the game's next EI, and every interrupt in between is lost. A second read cannot
; be hit the same way: the handler has already run, and an interrupt line still held after its EI / RET
; is taken at the end of that RET, before the second read. So: read once; on PO read again; then DI.
;
; Long DI windows lose interrupts too: the Next's /INT lasts about 32 T at 3.5 MHz (9 us); interrupts
; off across that moment lose the frame's interrupt. Keep every DI window short (a line read, an MMU
; switch: well under 9 us at 28 MHz) and open interrupts between polls (hlib_pace.asm hlib_line_di); a hook that must
; hold them off for longer defers the handler instead (card patch.isr-deferral).
; Macros only (no code): INCLUDE it before hlib_pace.asm. No IX / IY / alternate registers. Any speed.

; HLIB_IFF_DI: P/V = the caller's IFF (PE = on), then DI. A = I; the other flags lost; nothing else changed.
; Push AF after it to keep the state across the hook. 2 or 4 M1 + 1 (DI).
        MACRO HLIB_IFF_DI
        ld a,i
        jp pe,$+5               ; on: no second read (JP 3 bytes + LD A,I 2 bytes)
        ld a,i                  ; off, or an interrupt was accepted at the end of the first read
        di
        ENDM

; HLIB_IFF_EI: F's P/V from HLIB_IFF_DI (PE = were on) -> EI when they were. Keeps every register and flag.
        MACRO HLIB_IFF_EI
        jp po,$+4               ; JP 3 bytes + EI 1 byte
        ei
        ENDM
