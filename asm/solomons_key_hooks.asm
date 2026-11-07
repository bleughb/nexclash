; Solomon's Key (U.S. Gold / Probe 1987, 48K) - every figure as a hardware sprite. Facts and design:
; games/solomons_key.md. Interrupts are off all game (isr: 0 accepted).
;
; Method: back-buffer composer. Clean scenery at 0x5B00, compose buffer at 0x7300; the masked plotter 38093
; draws into the compose buffer and 38569 copies dirty 3 x 16 blocks to the screen. The plotter runs unchanged,
; so all game memory stays identical. The blit's source becomes the clean copy (two operand bytes, 0x73 -> 0x5B),
; so the ULA has no figures. Each compose plot is logged; after the blit the log becomes sprite attributes.
;
; 2026-11-05 rework (refactor phase 7 import):
; - the hooks live in alt ROM image 1 at 0x386E, the whole image Sinclair's ROM + these bytes (card
;   patch.whole-altrom-image): the game's delay LDIR (39203) reads ROM 0x0000-0x01F3, Sinclair's as on a 48K.
;   Their state is in RAM page SPAGE, mapped at slot 6 only inside a hook (no game code runs while it is; the
;   game's stack is at the top of memory, so not slot 7).
; - e_plot, post and e_cls run at 28 MHz and restore the caller's speed at exit (card patch.restore-speed);
;   e_pad runs at the caller's speed, as its delay must.
; - R as the original's at every hook (card patch.preserve-r; the game reads R at 53434).
; - the caller's speed: latched at entry (NR 7 read through 0x243B), restored at exit; e_pad never changes it.
; - pace ORIGINAL (card patch.pace-limiter, its debt idea at the game's own clock): every hook runs at the
;   game's clock and adds its own time to a debt, in LDIR steps of 21 T (8.8 fixed point); the game pads each
;   pass with up to 10 calls of its delay 39194 (38032: LDIR of BC = 500), and e_pad runs that delay up to 499
;   steps shorter to repay it. Every path's time is a constant here (K_*, measured on the verifier), so a padded
;   pass takes the original's time to the T-state; a pass with no padding (10 figures or more) carries the debt.
;
; Sites (original bytes checked by solomons_key.py):
;   38093 F5 C5 D5   PUSH AF / PUSH BC / PUSH DE  -> JP e_plot
;   37970 97 96      CALL 38551 (operand)         -> CALL e_cp
;   39097 21 FF 5A   LD HL,23295 (screen clear)   -> JP e_cls
;   38584 73, 38656 73  LD B,115 (blit source)    -> LD B,91
;   38047 1A 99      CALL 39194 (operand, the pad) -> CALL e_pad

        DEVICE ZXSPECTRUMNEXT

NMAX    EQU 64          ; figures per pass (the recordings reach 17)
PLOTD   EQU 38146       ; operand of LD D,115: 91 while the game stamps scenery into the clean copy
FLIP    EQU 43300       ; 43209 mirrors frames 48-58 in place; bit 0 = they are mirrored from the snapshot
DELAY   EQU 39194       ; the game's delay: LDIR of BC bytes, ROM 0 onto itself
SPAGE   EQU 24          ; the state page (bank 12, first half), at slot 6 inside a hook

; state page (0xC000-; slot 6: the game's stack is at the top of memory)
lpos    EQU 0xC000      ; the log's end (3 bytes a figure)
shown   EQU 0xC001      ; sprites shown by the last commit
t_a     EQU 0xC002
vr      EQU 0xC003      ; R at a hook's entry
debt    EQU 0xC004      ; 4 bytes: 1/256 step, then steps (21 T) owed (24 bits)
acc3    EQU 0xC008      ; post: the dirty blocks' sum, its third byte
vspd    EQU 0xC009      ; the incoming speed (NR 7 bits 1:0): e_plot, post and e_cls run at 28 MHz
CAP     EQU 2048        ; e_pad: steps carried at most after a pad (about a quarter of a pass); more is let go
lbuf    EQU 0xC100      ; NMAX * 3
MTAB    EQU 0xC200      ; frame -> 0x80 for the player's mirrored frames 48-58, else 0 (solomons_key.py fills it)
LOWT    EQU 0xC300      ; dirty block's D -> its debt (16 bits, low then high page): the block loop's own time plus
                        ; the blit's extra contention in the build (solomons_key.py low_table)
DIRTY   EQU 38390       ; the game's dirty block list: (E, D) pairs, 255 ends it
ROMB    EQU 0x52        ; Sinclair's ROM at 0x01F3: the last byte the original's delay (BC = 500) moves

; Time each path adds (8.8 steps of 21 T), and R (bits 6:0) from the entry's LD A,R to the exit's LD R,A.
; Measured on the verifier (solomons_key.time_check); the K_ values do not change any path's time.
K_SCEN  EQU 2126           ; e_plot, a scenery plot (not logged)
K_LOG   EQU 2428           ; e_plot, a figure logged
K_FULL  EQU 2149           ; e_plot, the log full
K_POST  EQU 3179      ; post: fixed part
K_SPR   EQU 736      ; post: each sprite shown
K_HIDE  EQU 366      ; post: each sprite hidden
K_CLS   EQU 2274      ; e_cls: fixed part (its hides: K_HIDE each)
K_PADN  EQU 9496           ; e_pad's own time by its path: owed less than 499 steps
K_PADC  EQU 9898           ;   499 or more, under CAP left
K_PADX  EQU 9801           ;   more than CAP left: CAP kept
K_PADB  EQU 9106           ;   65536 steps or more
D_PLOT  EQU 0x7F & -23 
D_POST  EQU 0x7F & -28
D_CLS  EQU 0x7F & -24
D_PAD  EQU 0x7F & -22

        ORG 0x386E
; ---- 38093: A = frame, E = x, D = y. No register or flag changes; nothing written but the state page and dead stack.
e_plot: push af
        push bc
        ld bc,0x243B            ; the caller's speed (card patch.restore-speed), then 28 MHz
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld b,a
        ld a,r
        nextreg 0x56,SPAGE
        ld (vr),a
        ld a,b
        ld (vspd),a
        pop bc
        pop af
        ld (t_a),a
        push af
        push hl
        ld a,(PLOTD)
        cp 115
        jr nz,.scen             ; scenery: stays on the ULA
        ld a,(lpos)
        cp NMAX*3
        jr nc,.full             ; full: not shown (the verifier counts it)
        ld l,a
        ld h,high lbuf
        add a,3
        ld (lpos),a
        ld a,(FLIP)             ; the game mirrors the player's frames in place and keeps this flag
        rrca
        and 0x80
        ld (hl),a
        ld a,(t_a)              ; bit 7: X mirror, as drawn at this plot, for frames 48-58 (the same time for all)
        push hl
        ld l,a
        ld h,high MTAB
        ld a,(hl)
        pop hl
        and (hl)
        ld (hl),a
        ld a,(t_a)
        or (hl)
        ld (hl),a
        inc l
        ld (hl),e
        inc l
        ld (hl),d
        ld hl,K_LOG
        jr .o
.scen:  ld hl,K_SCEN
        jr .o
.full:  ld hl,K_FULL
.o:     call dadd
        ld a,(vr)
        ld h,a
        add a,D_PLOT
        and 0x7F
        ld l,a
        ld a,h
        and 0x80
        or l
        pop hl
        ld r,a
        ld a,(vspd)
        nextreg 0x56,0
        nextreg 0x07,a
        pop af
        push af
        push bc
        push de
        jp 38096

; dadd: debt += HL (8.8 steps). A, F, HL lost. Same time whatever the carry.
dadd:   push de
        ld de,(debt)
        add hl,de
        ld (debt),hl
        ld a,(debt+2)
        adc a,0
        ld (debt+2),a
        ld a,(debt+3)
        adc a,0
        ld (debt+3),a
        pop de
        ret

; ---- CALL 38551 replaced: the blit, then the log as sprites.
e_cp:   call 38551
post:   push af
        push bc
        push de
        push hl
        ld bc,0x243B            ; the caller's speed (card patch.restore-speed), then 28 MHz
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld b,a
        ld a,r
        nextreg 0x56,SPAGE
        ld (vr),a
        ld a,b
        ld (vspd),a
        ld hl,K_POST
        call dadd
        ld hl,lbuf
        ld c,0                  ; sprite slot
.n:     ld a,(lpos)
        cp l
        jr z,.hide
        ld a,c
        nextreg 0x34,a
        ld b,(hl)               ; frame
        inc l
        ld a,(hl)               ; x
        inc l
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,a                 ; x bit 8
        ld e,a
        ld a,(hl)               ; y
        inc l
        add a,32
        nextreg 0x36,a
        ld a,b
        and 0x80
        rrca
        rrca
        rrca
        rrca                    ; X mirror
        or e
        nextreg 0x37,a
        res 7,b
        ld a,b
        srl a                   ; 128-byte units: bit 0 = N6
        or 0xC0                 ; visible, attribute 4 follows
        nextreg 0x38,a
        ld a,b
        and 1
        rrca
        rrca                    ; bit 6
        or 0x80                 ; 4-bit
        nextreg 0x39,a
        push hl
        ld hl,K_SPR
        call dadd
        pop hl
        inc c
        jr .n
.hide:  call hide
        ld hl,DIRTY             ; the blit read its source rows 104-191 from the clean copy, contended memory, where the
        ld bc,0                 ; original's compose buffer is not: per dirty block LOWT holds that time (an average a
        xor a                   ; byte, measured in JNext) and this loop's own; summed in acc3:B:C
        ld (acc3),a
.b:     ld a,(hl)
        cp 255
        jr z,.bd
        inc hl
        ld e,(hl)
        inc hl
        ld d,high LOWT
        ld a,(de)
        add a,c
        ld c,a
        inc d
        ld a,(de)
        adc a,b
        ld b,a
        ld a,(acc3)
        adc a,0
        ld (acc3),a
        jr .b
.bd:    ld hl,(debt)            ; debt += acc3:B:C
        add hl,bc
        ld (debt),hl
        ld a,(acc3)
        ld b,a
        ld a,(debt+2)
        adc a,b
        ld (debt+2),a
        ld a,(debt+3)
        adc a,0
        ld (debt+3),a
        ld a,(vr)
        ld h,a
        add a,D_POST
        and 0x7F
        ld l,a
        ld a,h
        and 0x80
        or l
        ld r,a
        ld a,(vspd)
        nextreg 0x56,0
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ret

; C = sprites now on show: hide the rest of last time's, empty the log. Keeps nothing but SP.
hide:   ld a,(shown)
        ld b,a
        ld a,c
        ld (shown),a
.h:     ld a,c
        cp b
        jr nc,.d
        nextreg 0x34,a
        xor a
        nextreg 0x38,a
        ld hl,K_HIDE
        call dadd
        inc c
        jr .h
.d:     xor a
        ld (lpos),a
        ret

; ---- 39097: the screen clear (level build, title, game over, high scores): no figures on these screens.
e_cls:  push af
        push bc
        ld bc,0x243B            ; the caller's speed (card patch.restore-speed), then 28 MHz
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        and 3
        ld b,a
        ld a,r
        nextreg 0x56,SPAGE
        ld (vr),a
        ld a,b
        ld (vspd),a
        push hl
        ld hl,K_CLS
        call dadd
        ld c,0
        call hide
        ld a,(vr)
        ld h,a
        add a,D_CLS
        and 0x7F
        ld l,a
        ld a,h
        and 0x80
        or l
        pop hl
        ld r,a
        ld a,(vspd)
        nextreg 0x56,0
        nextreg 0x07,a
        pop bc
        pop af
        ld hl,23295
        jp 39100

; ---- CALL 39194 in the pad loop (38046), BC = 500: the delay, up to 499 steps shorter by the debt.
; Leaves every register as the original's: BC = 500, A, and F as the original's LDIR leaves it (S, Z, C kept;
; H, N, P/V clear; bits 3 and 5 from A + its last byte, ROMB). Its own time (K_PADx, by its path) goes into the
; debt after the repayment, so the next pad repays it. Past CAP steps left the debt is let go: a long stretch of
; unpadded passes is as slow as its hooks (the verifier counts what is let go).
e_pad:  push af
        ld a,r
        nextreg 0x56,SPAGE
        ld (vr),a
        push hl
        push de
        ld hl,(debt+1)          ; steps owed, 24 bits
        ld a,(debt+3)
        or a
        jr nz,.big
        ld de,499
        sbc hl,de
        jr nc,.cap              ; 499 or more: repay 499, HL = what is left
        add hl,de               ; less: repay it all
        ex de,hl                ; DE = k
        ld hl,K_PADN
        push hl
        ld hl,0
        jr .k
.big:   ld hl,K_PADB            ; 65536 steps or more: repay 499, keep CAP
        push hl
        ld hl,CAP
        ld de,499
        jr .k
.cap:   ld de,CAP
        sbc hl,de
        jr nc,.over
        add hl,de               ; left < CAP: kept
        ld de,K_PADC
        push de
        ld de,499
        jr .k
.over:  ld hl,K_PADX            ; left over CAP: CAP kept
        push hl
        ld hl,CAP
        ld de,499
.k:     ld a,l
        ld (debt+1),a
        ld a,h
        ld (debt+2),a
        xor a
        ld (debt+3),a
        pop hl
        call dadd               ; this pad's own time, by its path
        push bc                 ; 500
        ld h,b
        ld l,c
        or a
        sbc hl,de
        ld b,h
        ld c,l                  ; BC = 500 - k, 1 at least
        nextreg 0x56,0
        call DELAY
        pop bc
        nextreg 0x56,SPAGE
        ld hl,5                 ; the stack: DE, HL, then the entry's F and A
        add hl,sp
        ld a,(hl)
        add a,ROMB
        ld d,a                  ; n = A + the last byte moved
        dec hl
        ld a,(hl)
        and 0xC1
        ld e,a
        ld a,d
        and 0x08
        or e
        ld e,a
        ld a,d
        rlca
        rlca
        rlca
        rlca
        and 0x20
        or e
        ld (hl),a               ; F out
        ld a,(vr)
        ld h,a
        add a,D_PAD
        and 0x7F
        ld l,a
        ld a,h
        and 0x80
        or l
        pop de
        pop hl
        ld r,a
        nextreg 0x56,0
        pop af
        ret

rom_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, hide all, clip, sprites on ---
        ORG 0xD000
setup:  ld bc,0x303B
        xor a
        out (c),a
        ld a,22
.p:     nextreg 0x57,a
        ld hl,0xE000
        ld d,0x20
        ld bc,0x005B
.o:     otir
        dec d
        jr nz,.o
        inc a
        cp 24
        jr nz,.p
        nextreg 0x57,21
        nextreg 0x4B,0
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
        nextreg 0x19,8
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
; 0 transparent, 1 bright white (the figures' default), 2 black (solid body), then the Spectrum's others
pal:    db 0x00,0xFF,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFC
setup_end:

        SAVEBIN "sk_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sk_setup.bin",0xD000,setup_end-0xD000

; ---------------------------------------------------------------------------------------------------
; Loading screen hold, copied unchanged from asm/lunar_jetman_hooks.asm (2026-11-05; the tape's SCREEN$ is a
; standard 6,912-byte block): the build puts bank 5's own screen at loading.picture (solomons_key.loading_nex). The .nex's bank 5 screen area
; holds the tape's loading screen; this is bank 34 (pages 68, 69), the entry bank, PC $C000: it shows
; the picture until a key or 5 s, waits for the key to go, puts bank 5's screen back and falls through
; to $C000, page 20 (the converter's own stub). Assembled after the hook SAVEBINs (device 0xC000-0xFFFF).
        MODULE loading
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 69; below it the stub's call stack
SEL     equ     $FE02           ; port $243B as found
TIMEOUT equ     250             ; frames: 5 s at 50 Hz
CAP     equ     250             ; most frames to wait for a held key to go
CLEAR   equ     3               ; frames with no key before leaving
LINE    equ     192             ; first line below the picture

        org     $C000
start:  di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,$243B
        in      a,(c)
        ld      (SEL),a
        xor     a
        out     ($fe),a
; Show: a key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the menu doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,picture
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        xor     a
        out     ($fe),a
        ld      bc,$243B
        ld      a,(SEL)
        out     (c),a
        nextreg $55,69
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,$243B
        ld      a,$1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,($fe)
        cpl
        and     $1f
        or      e
        ld      e,a
        ld      a,d
        ret

        ds      $C200-$
picture:
        ds      6912            ; bank 5's own screen, put in by the build (the file has the loading screen there)
        assert  $ <= $DF00      ; $DFxx: the loader's stack
        ds      $FFD0-$         ; REGS is written at run time; zero in the file
        disp    $-$4000
; Runs from page 69 at slot 5. Bank 10's top bytes get what the loader's stack left there.
final:  nextreg $56,20
        nextreg $57,21
        ld      hl,$C000
        ld      ($DFFC),hl
        ld      sp,REGS-$4000-12
        pop     iy
        pop     ix
        ld      hl,($BFFF)      ; MEMPTR = $C000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,$DFFE
        ds      $BFFC-$
        nextreg $55,5           ; falls through to $C000, page 20
        assert  $ == $C000
        ent
        ENDMODULE
        SAVEBIN "sk_loading.bin",0xC000,0x0200          ; code before loading.picture
        SAVEBIN "sk_loadend.bin",0xFFD0,0x0030          ; loading.final (the rest of the bank is zero)
