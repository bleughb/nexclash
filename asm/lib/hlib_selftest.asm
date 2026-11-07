; Test harness for the shared hook library (asm/lib/hlib_*.asm), assembled and run on a simulator by
; nexclash/hooklib.py selfcheck (selftest.py --tools). Not a game: each t_ / h_ entry is a hook, each o_
; entry the original code it displaces. Also the smallest example of a new engine using the library.
; Negative controls are assembled from this file with a define (-DNEG_...), or patched at a library
; label (hooklib.NEGATIVES).

        DEVICE ZXSPECTRUMNEXT

V_SPD   EQU 0xC000              ; speed latch (one per hook level)
V_SPD2  EQU 0xC001
HLIB_V_R EQU 0xC004             ; 3 bytes
V_BURN  EQU 0xC008              ; h_plot's extra work, in 256-step loops
V_N     EQU 0xC009
V_I     EQU 0xC00A
V_SL    EQU 0xC00B
V_FP    EQU 0xC00C              ; 2
V_AP    EQU 0xC00E              ; 2
HLIB_V_PACE EQU 0xC010          ; 14
HLIB_PACE_NL EQU 312            ; 48K timing in the tests
HLIB_V_DB EQU 0xC020            ; 2
HLIB_DB_HALF EQU 32
HLIB_DB_SPR0 EQU 0
HLIB_PCACHE EQU 0xC100          ; 128, 256-aligned
ATAB    EQU 0xC200              ; the frame's attribute table, 5 x 64
FRAME   EQU 0xB000              ; n, then n x (key 2, source 2, x, y), written by the test
BLITN   EQU 2048                ; o_blit: 2048 bytes by LDIR
T_BLIT  EQU 30 + 21 * (BLITN - 1) + 16 + 10    ; its T at 3.5 MHz, CALL excluded
    IFDEF PACE_SLOWWAIT
T_FIX   EQU 97 + 10 + 600       ; h_blit's 3.5 MHz part outside the polling: HLIB_SPEED_IN, RET, the wait's tail
                                ; from its last line reading (about 600 T at 3.5 MHz)
    ELSE
T_FIX   EQU 97 + 10             ; h_blit's 3.5 MHz part outside the window (HLIB_SPEED_IN, RET)
    ENDIF
TGT16   EQU ((T_BLIT - T_FIX) * 16 + 112) / 224 ; hooklib.lines16(T_BLIT - T_FIX)
DPLOT   EQU 12                  ; h_plot's unmeasured time less o_plot's: HLIB_SPEED_IN's 97 T, RET, the work outside
                                ; the two line readings (about 90 T at 28 MHz), 1/16 lines

        ORG 0x8000
        INCLUDE "hlib_speed.asm"        ; macros only
        INCLUDE "hlib_r.asm"            ; macros + hlib_r_set / hlib_r_add
        INCLUDE "hlib_iff.asm"          ; macros only
        INCLUDE "hlib_pace.asm"
        INCLUDE "hlib_pcache.asm"
        INCLUDE "hlib_commit.asm"

; ---- speed: work at 28 MHz, the caller's speed back ---------------------------------------------
t_speed:
        HLIB_SPEED_IN V_SPD
        ld a,b
        add a,c
        ld d,a
    IFDEF NEG_FORCED35
        nextreg 0x07,0          ; the old convention: a fixed 3.5 MHz exit
    ELSE
        HLIB_SPEED_OUT V_SPD
    ENDIF
        ret

t_speed2:                       ; the no-stack forms: A, F, B, C lost
        HLIB_SPEED_IN_ABC V_SPD2
        ld a,d
        xor e
        ld h,a
        HLIB_SPEED_OUT_A V_SPD2
        ret

; ---- R: the original sums B + 1 bytes (B = 0: 257); the hook does the same work with more code ------
o_r:    ld a,(hl)               ; O = 1 + 3B + 1 (RET) M1s
.l:     add a,(hl)
        inc hl
        djnz .l
        ret

h_r:    HLIB_R_IN               ; E = 3
        HLIB_SPEED_IN V_SPD
        ld a,b
        add a,a
        add a,b                 ; 3B
    IFDEF NEG_ROFF
        add a,(2 - 3 - 2 + 1) & 0xFF    ; one count off
    ELSE
        add a,(2 - 3 - 2) & 0xFF        ; delta = O - E - N, N = 2 (HLIB_R_OUT's last load, RET)
    ENDIF
        call hlib_r_set
        ld a,(hl)
.l:     add a,(hl)
        inc hl
        djnz .l
        HLIB_SPEED_OUT V_SPD
        HLIB_R_OUT
        ret

; ---- pace: the original blit at 3.5 MHz; the hook does it at 28 MHz and waits out the rest ---------
o_blit: ld hl,0xD000
        ld de,0xD800
        ld bc,BLITN
        ldir
        ret

h_blit: HLIB_SPEED_IN V_SPD
        push af
        push bc
        push de
        push hl
        call hlib_pace_open
        pop hl
        pop de
        pop bc
        pop af
        ld hl,0xD000
        ld de,0xD800
        ld bc,BLITN
        ldir
        push af
        push bc
        push de
        push hl
    IFDEF PACE_SLOWWAIT
        HLIB_SPEED_OUT V_SPD    ; interrupts on at the site: wait at the caller's clock
    ENDIF
        ld a,(V_SPD)
        ld hl,TGT16
        call hlib_pace_wait
        pop hl
        pop de
        pop bc
        pop af
        HLIB_SPEED_OUT V_SPD
        ret

; an outside hook that adds time (its original copies one byte); the next window repays it
o_plot: ld a,(hl)
        ld (de),a
        ret

h_plot: HLIB_SPEED_IN V_SPD
        push af
        push bc
        push de
        push hl
        call hlib_debt_open
        ld a,(V_BURN)
        or a
        jr z,.n
        ld c,a
        ld b,0
.w:     djnz .w                 ; the hook's own work (1.9 lines a step at 28 MHz)
        push bc
        call hlib_debt_tick     ; at least once a frame
        pop bc
        dec c
        jr nz,.w
.n:     ld a,DPLOT
        call hlib_debt_close
        pop hl
        pop de
        pop bc
        pop af
        ld a,(hl)
        ld (de),a
        HLIB_SPEED_OUT V_SPD
        ret

; ---- content cache ------------------------------------------------------------------------------
t_up:   HLIB_SPEED_IN V_SPD     ; A = slot, DE = key, HL = source
        call hlib_pc_upload
        HLIB_SPEED_OUT V_SPD
        ret

t_inval:
        HLIB_SPEED_IN V_SPD
        call hlib_pc_inval
        HLIB_SPEED_OUT V_SPD
        ret

t_reset:
        HLIB_SPEED_IN V_SPD
        call hlib_pc_reset
        HLIB_SPEED_OUT V_SPD
        ret

; ---- one frame: each figure's image into the back half (through the cache), then one burst --------
t_frame:
        HLIB_SPEED_IN V_SPD
        ld hl,FRAME
        ld a,(hl)
        ld (V_N),a
        inc hl
        ld (V_FP),hl
        ld hl,ATAB
        ld (V_AP),hl
        xor a
        ld (V_I),a
.f:     ld a,(V_I)
        ld hl,V_N
        cp (hl)
        jr z,.done
        ld hl,(V_FP)
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = key
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = source
        inc hl
        push bc
        ld bc,(V_AP)
        ld a,(hl)               ; X
        ld (bc),a
        inc bc
        inc hl
        ld a,(hl)               ; Y
        ld (bc),a
        inc bc
        inc hl
        ld (V_FP),hl
        xor a
        ld (bc),a               ; attribute 2
        inc bc
        call hlib_db_back
        ld hl,V_I
        add a,(hl)
        ld (V_SL),a
        or 0xC0                 ; visible, the 5-byte form, pattern = the slot
        ld (bc),a
        inc bc
        xor a
        ld (bc),a               ; attribute 4: 8-bit pattern
        inc bc
        ld (V_AP),bc
        pop hl
        ld a,(V_SL)
        call hlib_pc_upload
    IFDEF NEG_SPLIT
        ld a,(V_I)              ; this sprite's attributes at once, between the uploads
        add a,HLIB_DB_SPR0
        ld bc,0x303B
        out (c),a
        ld hl,(V_AP)
        ld de,-5
        add hl,de
        ld bc,0x0557
        otir
    ENDIF
        ld hl,V_I
        inc (hl)
        jr .f
.done:
    IFDEF NEG_SPLIT
        ld a,(HLIB_V_DB)
        xor HLIB_DB_HALF
        ld (HLIB_V_DB),a
    ELSE
        ld hl,ATAB
        ld a,(V_N)
        call hlib_commit
    ENDIF
        HLIB_SPEED_OUT V_SPD
        ret

; ---- interrupt state: the caller's IFF back after a hook that holds interrupts off -----------------
t_iff:
    IFDEF NEG_IFF1
        ld a,i                  ; the old form: one read, trusted
        di
    ELSE
        HLIB_IFF_DI
    ENDIF
        push af
        ld a,b                  ; the hook's work with interrupts off
        add a,c
        ld d,a
        pop af
        HLIB_IFF_EI
        ret

t_line_di:                      ; a video line read with the shortest DI window
        call hlib_line_di
        ret

code_end:

        SAVEBIN "hlib_code.bin",0x8000,code_end-0x8000
