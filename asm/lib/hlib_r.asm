; Shared hook library: leave R as the original code would (card patch.preserve-r). After Nightshade's
; hooks (pilot runs/nightshade, asm/nightshade_hooks.asm mkT). NEW engines only (Dean's rule).
; Unit tests and negative control: nexclash/hooklib.py (selftest.py --tools).
;
; Games that take random numbers from R (Atic Atac: 9 reads) meet other enemies when a hook changes
; the instruction count. R counts M1 cycles (bits 6:0; bit 7 only changes by LD R,A), so:
;   O = M1s the original runs from the site to the return point (mod 128; hooklib.r_span measures it),
;   E = M1s the hook runs from the site through HLIB_R_IN (the macro itself: 3),
;   N = M1s the hook runs after the LD R,A of HLIB_R_OUT up to the return point (the macro: 1),
;   delta = O - E - N (hooklib.r_delta); HLIB_R_IN, then A = delta, CALL hlib_r_set; for a run-time O
;   (a loop of B steps: Nightshade's colour box) add the variable part with CALL hlib_r_add.
; The verifier compares R (register index 15; hooklib.CMP_R) after every hook; hooklib.r_check says
; how many to add when it differs.
;
; The engine defines, before the INCLUDE:
;   HLIB_V_R  EQU <3 bytes of hook RAM>   +0 R at entry, +1 R to set, +2 A saved at the exit
; One hook level: a hook that can run inside another keeps its own copy (or saves HLIB_V_R).

; HLIB_R_IN: HLIB_V_R+0 = R. Keeps every register and flag; 2 bytes of stack. 3 M1 (push af, ld a,r).
        MACRO HLIB_R_IN
        push af
        ld a,r
        ld (HLIB_V_R),a
        pop af
        ENDM

; HLIB_R_OUT: R = HLIB_V_R+1. Keeps every register and flag; no stack. 1 M1 after the LD R,A.
        MACRO HLIB_R_OUT
        ld (HLIB_V_R + 2),a
        ld a,(HLIB_V_R + 1)
        ld r,a
        ld a,(HLIB_V_R + 2)
        ENDM

; hlib_r_set: A = delta (mod 128) -> HLIB_V_R+1 = bit 7 of the entry R, (entry R + A) in bits 6:0.
; AF lost; BC, DE, HL kept. Runs at any speed (R counts instructions, not time).
hlib_r_set:
        push bc
        ld c,a
        ld a,(HLIB_V_R)
        jr hlib_r_add.c

; hlib_r_add: A = more M1s -> HLIB_V_R+1 advanced by A in bits 6:0, bit 7 kept. AF lost.
hlib_r_add:
        push bc
        ld c,a
        ld a,(HLIB_V_R + 1)
.c:     ld b,a
        add a,c
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld (HLIB_V_R + 1),a
        pop bc
        ret
