; Match Day (Ocean, 1985, 48K) - every player, the ball and its shadow as hardware sprites.
; v2.1 speed pass (Jon Attree's opt-in rework of Dean's matchday_hooks.asm, 2026-11-05): every hook latches the
; incoming CPU speed and gives it back on exit (never a fixed 3.5 MHz); the game's own image builds (0x8DEC), XOR
; draw (0x8ECE) and ball routine (0x9FCF) still run at 28 MHz, each inside a pace window whose target is the
; original's T for that call (docs/profiles/match_day_v21_pace.json, page 27 / BDTAB); the hook time and the
; difference go to a debt (1/16 lines), paid once per match-loop pass in e_frame (w_pay). Interrupt time inside a
; window is left out: isr_w / isr_x add each interrupt's lines to ISRACC.
;
; The game draws figures by XOR straight to the screen. The build keeps every plotter running and
; turns its 42 screen / attribute writes into NOPs (matchday.SCREEN_NOPS), so registers and game
; memory stay the original's; these hooks only show the same images as hardware sprites.
;
; Code: alt ROM image 1 from ROM_ORG (read-only). State, build rings, ball row table: RAM page
; STATE_PG mapped at MMU slot 6 (0xC000) while a hook runs; the 4-bit row tables (pages NIB_PG..)
; take slot 6 one row at a time while a pattern is built. Slot 6 is the only slot the game's IM 2
; handler never touches (isr scans, both recordings; it reads the user-defined key table at 0x67xx
; in slot 3), so interrupts stay ON. Every hook runs on its own stack in the printer buffer
; 0x5BA8-0x5BFF (saved and restored by every hook: the cup team names live there; the game's match stack is only 56 bytes
; deep), at 28 MHz, and never writes IX, IY, I, the alternate registers or the game's memory.
;
; Sites (original bytes checked by matchday.py):
;   0x8DEC  E6 06 FE   AND 6 / CP 4 (image build: HL = graphics, B = rows/2, DE = buffer) -> JP e_bd
;   0x8D63  DD CB 00   BIT 5,(IX+0) (clear of the 4 rows above a 32-row image)       -> JP e_clr
;   0x8B5C  CD CE 8E   CALL 0x8ECE (the XOR draw: HL = new image's last byte, DE = its screen
;                      address, B = rows drawn)                                     -> CALL e_pl
;   0x9D15  CD CF 9F   CALL 0x9FCF (ball + shadow)                                    -> CALL e_ball
;   0x817F  CD 98 98   CALL 0x9898 (match main loop, once per pass)                   -> CALL e_frame
;   0xE62C  CD AD EF   CALL 0xEFAD (screen clear at match set-up)                     -> CALL e_cls
;   0x819D  F3 3E 00   DI / LD A,0 (match loop exit)                                  -> JP e_exit
;   0x8A20  E1 FB C9   POP HL / EI / RET (the IM 2 handler's exit)                    -> JP isr_x
;   alt ROM 0x3BFF/0x3C00 (the IM 2 vector word, FF FF = 0xFFFF)                      -> isr_w
; e_pl / e_ball replace their own return address with the post-hook (EX (SP),HL) and JP to the
; game routine, so the game routine runs at exactly the original stack depth.
; Sprites: slot order = depth (higher slot on top): ball shadow first, then players and the ball
; by their ground line (bottom y): nearer = lower on the screen = in front. Figure k (k = buffer
; pair index, (IX+0x14 - 0xB736) / 192, 0..16) builds into 256-byte pattern slot k or k+17
; (double buffered: built while the other shows, switched by e_frame); ball + shadow: 34 / 35.

        DEVICE ZXSPECTRUMNEXT

ROM_ORG   EQU 0x2300                  ; ROM 0x22CB-0x3BFE is never read (scan, both recordings)
STATE_PG  EQU 26
NIB_PG    EQU 28
GAME_P3   EQU 11
GAME_P6   EQU 0
ST        EQU 0xC000                ; the state page at slot 6 (the only slot the IM 2 handler never touches)
FIG       EQU ST                  ; 17 figures x 16 bytes, then ball / shadow records
F_VIS     EQU 0
F_X       EQU 1                   ; 16-bit screen x of the image's left pixel
F_YT      EQU 3                   ; 16-bit screen y of the image's top row
F_BANK    EQU 5
F_SLOT    EQU 6                   ; 256-byte pattern slot on show
F_N       EQU 7                   ; rows (1-32)
F_YB      EQU 8                   ; bottom row y (depth key)
F_FR      EQU 9                   ; frame IX+3 at the draw
F_CAM     EQU 10                  ; camera x at the draw
F_NEW     EQU 12                  ; pattern slot built, not yet on show (0xFF = none)
F_XS      EQU 13                  ; 16-bit x as shown (the dive's spare half: locked)
F_RING    EQU 15                  ; ring index (newest build), 0-15
NFIG      EQU 17
BALLR     EQU FIG+16*NFIG         ; ball record (F_ layout)
SHADR     EQU BALLR+16            ; shadow record
NREC      EQU NFIG+2
COMBO     EQU ST+0x680            ; 64: (strip * 8 + socks) -> bank + 1
NBANK     EQU ST+0x6C0
NSPR      EQU ST+0x6C1            ; sprites shown by the last e_frame
EMS       EQU ST+0x6C2            ; next sprite slot (e_frame)
E_X       EQU ST+0x6C4
E_Y       EQU ST+0x6C6
E_PAT     EQU ST+0x6C8
E_BANK    EQU ST+0x6C9
V_LO      EQU ST+0x6CA
V_NC      EQU ST+0x6CC
V_B0      EQU ST+0x6CD
V_R       EQU ST+0x6CE
TMP       EQU ST+0x6D0            ; e_pl entry HL, DE, BC
V_SEQB    EQU ST+0x6D6            ; best seq so far (bestrow)
V_BEST    EQU ST+0x6D8            ; best entry pointer (bestrow)
V_A       EQU ST+0x6DA            ; row address (bestrow)
V_M       EQU ST+0x6DC
SAVSP     EQU ST+0x6E0
V_K       EQU ST+0x6E2
V_FP      EQU ST+0x6E4            ; FIG + 16k
V_ADDR    EQU ST+0x6E6
V_DEST    EQU ST+0x6E8
V_SRC     EQU ST+0x6EA
V_ROWS    EQU ST+0x6EC
V_SHIFT   EQU ST+0x6ED
V_N       EQU ST+0x6EE
V_OFF     EQU ST+0x6EF
V_X       EQU ST+0x6F0
V_YB      EQU ST+0x6F2
V_SLOT    EQU ST+0x6F3
V_SORTN   EQU ST+0x6F4
V_I       EQU ST+0x6F5
V_J       EQU ST+0x6F6
V_RB      EQU ST+0x6F7
V_DEST2   EQU ST+0x6F8
V_SRC2    EQU ST+0x6FA
V_SH2     EQU ST+0x6FC
V_ADDR2   EQU ST+0x6FE
SORTB     EQU ST+0x700            ; up to 20 x (key, id)
ROWSRC    EQU ST+0x780            ; 32 words: graphics row address per image row (0 = blank)
ROWSH     EQU ST+0x7C0            ; 32 bytes: row shift - the bottom row's shift (pixels, even)
CAND      EQU ST+0x7E0            ; up to 8 candidate ring entries (pointers)
SEQ       EQU ST+0x7F0            ; global build counter
RING      EQU ST+0x800            ; 17 x 128: 16 builds x (dest, src, rows, shift, seq)
HSTACK    EQU 0x5C00              ; hook stack: printer buffer 0x5BA8-0x5BFF (saved / restored by ENTERST / LEAVEST)
HSTKLO    EQU 0x5BC0              ; v2.1: 64 bytes (hooks reach 32 at most, checked; the interrupt adds 26)
PBSAVE    EQU ST+0x1C00           ; 88 bytes: what the game keeps at 0x5BA8-0x5BFF (cup team names)
SV_HL     EQU ST+0x1C60
SV_DE     EQU ST+0x1C62
SV_BC     EQU ST+0x1C64
BALLTAB   EQU ST+0x1800           ; ball rows: (src - BALL0) * 4 -> 8 nibble bytes
LASTIMG   EQU ST+0x1100           ; 17 x 96: ROWSRC + ROWSH of the image last built per figure
V_LEFT    EQU ST+0x6DE            ; rows not yet resolved
V_HO      EQU ST+0x6DF            ; own ring cursor (entries left)
V_HP      EQU ST+0x6FF            ; previous figure's ring cursor (entries left)
V_IO      EQU ST+0x6CB            ; own ring index
V_IP      EQU ST+0x6CF            ; previous ring index
BUFBASE   EQU 0xB736
LATCH     EQU ST+0x1A00           ; incoming speed (NR 7 bits 1:0) latched by the entry hook
W_L0      EQU ST+0x1A04           ; window: line at the last w_since
W_I0      EQU ST+0x1A06           ; window: ISRACC at the last w_since
DEBT      EQU ST+0x1A08           ; signed, 1/16 lines: > 0 the build is behind the original, < 0 ahead
ISRACC    EQU ST+0x1A0A           ; lines spent in the game's interrupt handler (isr_w .. isr_x), 16-bit
ISRL0     EQU ST+0x1A0C           ; line at isr_w
TGT       EQU ST+0x1A0E           ; the open window's target: the original's time (1/16 lines) - FIXU
LASTBD    EQU ST+0x1A10           ; the last build target (T / 14), for the verifier
LASTPL    EQU ST+0x1A12           ; the last draw target (T / 14), for the verifier
WSV_DE    EQU ST+0x1A14
WSV_BC    EQU ST+0x1A16
V_IFF     EQU ST+0x1A18           ; LINEHL: ISRACC's low byte before the reads
V_RED     EQU ST+0x1A19           ; e_bd: 1 = the redirected (0xFFB8 copy) builder
W_ON      EQU ST+0x1A1E           ; 1 = a pace window is open (its first hook latched the speed)
W_OBJ     EQU ST+0x1A1F           ; 1 = inside 0x8B45 (e_obj .. e_objpost): inner hooks keep the window and 28 MHz
OUTSPD    EQU ST+0x1A20           ; the speed a hook leaves with (w_close: LATCH, or 3 inside 0x8B45)
RETOBJ    EQU ST+0x1A22           ; 0x8B45's own return address
RSAVE     EQU ST+0x1A24           ; R as the hook piece read it (R at its first instruction + 2, 3 or 4)
RVAL      EQU ST+0x1A25           ; R to set before the hook's fixed tail (RSET)
ISR_R     EQU ST+0x1A26           ; isr_w / isr_x: R as read
RETFR     EQU ST+0x1A28           ; the copier's own return address (0x8182)
LASTCR    EQU ST+0x1A2A           ; the copier target (T / 14), for the verifier
CRU_MOVE  EQU 1311                ; 18359 T: the crowd copier after a camera move
CRU_SAME  EQU 1380                ; 19316 T: the crowd copier, camera still
RETOBJS   EQU ST+0x1A2C           ; 0x81FB's own return address (0x8197)
W_ACC     EQU ST+0x1A2E           ; lines of the open window already counted (ticks inside e_objs)
LOOPU     EQU 96                  ; 1328 T + CALL 17 T: 0x81FB's own code, every figure called
LOOPU2    EQU 134                 ; about 1880 T: the 0x822C path
OBJU      EQU 31                  ; 433 T: 0x8B45 when it draws nothing
DRAWU     EQU 72                  ; 1014 T: the rest of a call that draws (its code before the first build, after the draw)
CLRU      EQU 35                  ; 493 T: the 0x8D63 clear and the code after it
V_POLL    EQU ST+0x1A1A
V_WAITS   EQU ST+0x1A1C           ; passes that waited (statistics)
BDTAB     EQU ST+0x1A40           ; build targets, 1/16 lines: 8 paths x 16 values of B, words
TAB_PG    EQU 27                  ; draw targets: base 0xC000 (1024 words), adjust 0xC800 (1024 signed words)
NLINES    EQU 312                 ; lines a frame, 48K timing at 50 Hz
FIXU      EQU 12                  ; a window's unmeasured part at 3.5 MHz (entry before 28 MHz, exit after), 1/16 lines
BALLU     EQU 139                 ; the ball routine's mean T (1950) / 14
FRAME0    EQU 0xC460
FRAMEEND  EQU 0xE048
BALL0     EQU 0xA108
BALLEND   EQU 0xA188
CAMERA    EQU 0xE60B
DIVE0     EQU 72
SPARE     EQU 16                  ; figure index of the spare object 0xB6AC (keeper's second half)
SLOT_BALL EQU 34

        ; The hook stack 0x5BA8-0x5BFF holds the cup team names (OCEAN UNITED .. WOODS ATHLETIC):
        ; never read while a hook runs (the game is stopped there; its IM 2 handler never reads it),
        ; so ENTERST saves the 88 bytes to the state page and LEAVEST puts them back. Registers and
        ; flags are kept: HL/DE/BC through the state page, AF on the game stack (2 bytes).
        ; Speed and pace (v2.1). Every entry selects NR 7 at port 0x243B and reads it (LINEHL, isr_w / isr_x select
        ; 7 again after any other register, so an interrupt between an entry's OUT and IN changes nothing).
        MACRO HOOKIN                  ; the incoming speed and R read, 28 MHz, state page in; a window opened unless
        push af                     ; one is open (W_ON: the speed was latched by the window's first hook). Every
        push bc                     ; register and flag kept; 4 bytes of the game stack. 87 T at the incoming
        ld bc,0x243B                ; speed: NR 7 selected and read (the stub's start-up leaves another register
        ld a,7                      ; selected; an interrupt between the OUT and the IN leaves 7 selected: isr_x)
        out (c),a
        inc b
        in a,(c)                    ; bits 1:0 = the speed the caller set
        nextreg 0x07,3
        ld b,a
        ld a,r                      ; RSAVE = R at the hook's first instruction + 14
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld a,b
        and 3
        ld c,a
        ld a,(W_ON)
        or a
        jp nz,.on
        ld a,c
        ld (LATCH),a
        ld (SV_HL),hl
        WOPEN
        ld hl,(SV_HL)
.on:    pop bc
        pop af
        ENDM
        MACRO WOPEN                   ; a window starts now (state page in; A, BC, HL lost)
        LINEHL
        ld (W_L0),hl
        ld hl,(ISRACC)
        ld (W_I0),hl
        ld hl,-FIXU
        ld (TGT),hl
        ld hl,0
        ld (W_ACC),hl
        ld a,1
        ld (W_ON),a
        ENDM
        MACRO ENTERNL                 ; the hook stack (state page in, speed and window as they are)
        nextreg 0x56,STATE_PG
        ld (SAVSP),sp
        ld (SV_HL),hl
        ld (SV_DE),de
        ld (SV_BC),bc
        push af
        ld hl,HSTKLO
        ld de,PBSAVE
        PBCOPY
        pop af
        ld hl,(SV_HL)
        ld de,(SV_DE)
        ld bc,(SV_BC)
        ld sp,HSTACK
        ENDM
        MACRO ENTERST
        HOOKIN
        ENTERNL
        ENDM
        MACRO ENTERRET                ; a hook a RET lands in (28 MHz, window open): RSAVE = R at entry + 3, hook stack
        push af
        ld a,r
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        pop af
        ENTERNL
        ENDM
        MACRO RSET k                  ; RVAL = RSAVE + k in bits 6:0, bit 7 kept (preserve R: the original's count at
        ld hl,RVAL                  ; the resume point); A, F, HL lost
        ld a,(RSAVE)
        and 0x80
        ld (hl),a
        ld a,(RSAVE)
        add a,(k) & 0x7F
        and 0x7F
        or (hl)
        ld (hl),a
        ENDM
        MACRO PBCOPY                  ; HSTACK - HSTKLO bytes (HL) -> (DE): unrolled LDI (2 bytes of stack)
        call pbcopy
        ENDM
        MACRO LEAVEST k               ; printer buffer back, the window closed, the latched speed again
        ld sp,(SAVSP)
        ld (SV_HL),hl
        ld (SV_DE),de
        ld (SV_BC),bc
        push af
        ld hl,PBSAVE
        ld de,HSTKLO
        PBCOPY
        call w_close
        RSET k
        ld hl,(SV_HL)
        ld de,(SV_DE)
        ld a,(RVAL)
        ld r,a                      ; 8 M1s from here to the macro's end
        ld a,(OUTSPD)
        ld bc,(SV_BC)
        nextreg 0x56,GAME_P6
        nextreg 0x07,a
        pop af
        ENDM
        MACRO LEAVEPAY k              ; LEAVEST, and the debt paid (e_frame, once per match-loop pass)
        ld sp,(SAVSP)
        ld (SV_HL),hl
        ld (SV_DE),de
        ld (SV_BC),bc
        push af
        ld hl,PBSAVE
        ld de,HSTKLO
        PBCOPY
        call w_close
        call w_pay
        RSET k
        ld hl,(SV_HL)
        ld de,(SV_DE)
        ld a,(RVAL)
        ld r,a                      ; 8 M1s from here to the macro's end
        ld a,(OUTSPD)
        ld bc,(SV_BC)
        nextreg 0x56,GAME_P6
        nextreg 0x07,a
        pop af
        ENDM
        MACRO LEAVEKEEP k             ; printer buffer back; 28 MHz and the window kept (e_bd: the build follows)
        ld sp,(SAVSP)
        ld (SV_HL),hl
        ld (SV_DE),de
        ld (SV_BC),bc
        push af
        ld hl,PBSAVE
        ld de,HSTKLO
        PBCOPY
        RSET k
        ld hl,(SV_HL)
        ld de,(SV_DE)
        ld a,(RVAL)
        ld r,a                      ; 5 M1s from here to the macro's end
        ld bc,(SV_BC)
        nextreg 0x56,GAME_P6
        pop af
        ENDM
        MACRO LINEHL                  ; HL = video line 0-311 (state page in); A, BC lost. No DI: an interrupt
.r:     ld a,(ISRACC)               ; between a select and its read (isr_w / isr_x select other registers)
        ld (V_IFF),a                ; moves ISRACC, and the read is made again
        ld bc,0x243B
        ld a,0x1F
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in a,(c)
        cp l
        jr c,.r                     ; the low byte wrapped between the reads
        dec b
        ld a,7
        out (c),a                   ; register 7 selected again
        ld a,(V_IFF)
        ld b,a
        ld a,(ISRACC)
        cp b
        jr nz,.r
        ld a,h
        and 1
        ld h,a
        ENDM

        ORG ROM_ORG
; =============================================================================================
; e_bd: image build entry 0x8DEC (A = shift source, B = rows / 2, DE = buffer, HL = graphics).
; Records (dest, src, rows, shift) as the newest entry of figure k's ring; replays AND 6 / CP 4.
; =============================================================================================
e_bd:   ENTERST
        push af
        push bc
        push de
        push hl
        ld (V_SRC),hl
        ld hl,V_RED
        ld (hl),0                   ; not the redirected builder (set below)
        ld (V_DEST),de
        and 6
        ld (V_SHIFT),a
        ld a,b
        add a,a
        ld (V_ROWS),a
        ; the shift-2 / shift-6 builders, while redirected through the 0xFFB8 copy (0x8E8A /
        ; 0x8E46, set by 0x8DD2 at match start), always build 28 rows (B forced to 14)
        ld a,(V_SHIFT)
        cp 2
        jr nz,.s6
        ld hl,(0x8DF7)
        ld de,0x8E8A
        jr .chk
.s6:    cp 6
        jr nz,.rec
        ld hl,(0x8DFA)
        ld de,0x8E46
.chk:   or a
        sbc hl,de
        jr nz,.rec
        ld a,28
        ld (V_ROWS),a
        ld a,1
        ld (V_RED),a
.rec:   call figk                   ; A = k, carry = not a figure (walk-on 2x plotter etc.)
        jp c,.out
        call setk
        call ringadd
        call bdtgt                  ; TGT += the original build's time (path, B) + the game's code from its return
        pop hl
        pop de
        pop bc
        pop af
        LEAVEKEEP -21                   ; a figure's build and the game's code to its draw at 28 MHz, in the window
        and 6
        cp 4
        jp 0x8DF0
.out:   xor a                       ; not a figure (the walk-on scene's 2x plotter): the build at the caller's speed
        ld (V_RED),a
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -24
        and 6
        cp 4
        jp 0x8DF0

; bdtgt: TGT += BDTAB[(V_SHIFT / 2 + 4 x V_RED) x 16 + B] + the game's code from the build's return to the next
; hook (by return address); LASTBD = the build's value. B = the entry B (SV_BC + 1). A, BC, DE, HL lost.
bdtgt:  ld a,(V_RED)
        add a,a
        add a,a
        ld b,a
        ld a,(V_SHIFT)
        rrca
        or b                        ; path 0-7
        add a,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(SV_BC+1)
        and 15
        or b
        ld l,a
        ld h,0
        add hl,hl
        ld de,BDTAB
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (LASTBD),de
        ld hl,(TGT)
        add hl,de
        ex de,hl                    ; DE = TGT + build
        ld hl,(SAVSP)
        ld c,(hl)
        inc hl
        ld b,(hl)                   ; BC = the build's return address
        ld hl,BETW
.b:     ld a,(hl)
        inc hl
        cp c
        jr nz,.n
        ld a,(hl)
        cp b
        jr nz,.n
        inc hl
        ld a,(hl)                   ; the code to the next hook, 1/16 lines
        add a,e
        ld e,a
        jr nc,.s
        inc d
        jr .s
.n:     inc hl
        ld a,(hl)
        inc hl
        or a
        jr nz,.b                    ; (the table ends with a zero entry)
.s:     ld (TGT),de
        xor a
        ld (V_RED),a
        ret
; the original's T from an image build's return to the next hook (pace json 'between', / 14):
; return address, 1/16 lines; the table ends with a zero entry
BETW:   dw 0x8C58
        db 14                       ; 191 T (209 when IX+0 bit 6 was set): to the draw
        dw 0x8CC5
        db 14                       ; 189 T: to the draw
        dw 0x8D1D
        db 15                       ; 211 T (229): to the draw
        dw 0x8B8A
        db 6                        ; 1181 T (1158-1190) to the second build, less 1102 T (this path's code before
                                    ; the first build is 232 T, not the 1337 T that DRAWU counts)
        dw 0x8D07
        db 18                       ; 89 + 169 T (0x8DC2): to the second build
        dw 0
        db 0

; =============================================================================================
; e_obj: 0x8B45 (the player draw routine's entry: LD A,0x1C / LD (0x93AD),A), v2.1: the whole call runs at
; 28 MHz in one pace window (W_OBJ): its own code, the builds and the draw. The call returns to e_objpost, which
; closes the window (target: the original's time for the call, built up by e_obj, e_bd, e_pl, e_clr) and gives
; the caller's speed back. 0x8B45 is entered by CALL or JP: its return address is on the stack either way.
; =============================================================================================
e_objs: push af                     ; CALL 0x81FB at 0x8194 (the 16 figures' draw calls): one window for all
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)                    ; NR 7: the incoming speed
        nextreg 0x07,3
        ld b,a
        ld a,r                      ; R at the first instruction + 14
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld a,b
        and 3
        ld c,a
        ld a,(W_ON)
        or a
        jp nz,.on
        ld a,c
        ld (LATCH),a
        ld (SV_HL),hl
        WOPEN
        ld hl,(SV_HL)
.on:    ld a,1
        ld (W_OBJ),a
        ld (SV_HL),hl
        ld bc,LOOPU                 ; the loop's own code: 1328 T (all 16 called) or about 1880 T (0x822C path:
        ld a,(0x897D)               ; CALL NZ by 0xA0BB), + the CALL
        cp 3
        jr nc,.l
        ld bc,LOOPU2
.l:     ld hl,(TGT)
        add hl,bc
        inc hl
        ld (TGT),hl
        ld hl,4
        add hl,sp                   ; the return address (0x8197), under AF and BC
        ld a,(hl)
        ld (RETOBJS),a
        ld (hl),e_objspost & 255
        inc hl
        ld a,(hl)
        ld (RETOBJS+1),a
        ld (hl),e_objspost >> 8
        RSET -20
        ld a,(RVAL)
        ld r,a                      ; 6 M1s to 0x81FB
        ld hl,(SV_HL)
        nextreg 0x56,GAME_P6
        pop bc
        pop af
        jp 0x81FB
e_objspost:
        push hl
        push af
        ld a,r                      ; R at the first instruction + 4
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld (WSV_DE),de
        ld (WSV_BC),bc
        xor a
        ld (W_OBJ),a
        call w_close
        RSET -13
        ld de,(WSV_DE)
        ld bc,(WSV_BC)
        ld a,(RVAL)
        ld r,a                      ; 9 M1s to the caller
        ld hl,(RETOBJS)
        ld a,(OUTSPD)
        nextreg 0x56,GAME_P6
        nextreg 0x07,a
        pop af
        ex (sp),hl
        ret

e_obj:  push af
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)                    ; NR 7: the incoming speed
        nextreg 0x07,3
        ld b,a
        ld a,r                      ; R at the first instruction + 14
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld a,(W_OBJ)
        or a
        jp z,.full
        ld (SV_HL),hl               ; inside e_objs' window (the usual case): only the target
        ld hl,(TGT)
        ld bc,OBJU
        add hl,bc
        ld (TGT),hl
        jp .go
.full:  ld a,b
        and 3
        ld c,a
        ld a,(W_ON)
        or a
        jp nz,.on
        ld a,c
        ld (LATCH),a
        ld (SV_HL),hl
        WOPEN
        ld hl,(SV_HL)
.on:    ld a,1
        ld (W_OBJ),a
        ld (SV_HL),hl
        ld hl,(TGT)
        ld bc,OBJU                  ; the call's code when it draws nothing (433 T); a build / draw adds more
        add hl,bc
        ld (TGT),hl
        ld hl,4
        add hl,sp                   ; the return address, under AF and BC
        ld a,(hl)
        ld (RETOBJ),a
        ld (hl),e_objpost & 255
        inc hl
        ld a,(hl)
        ld (RETOBJ+1),a
        ld (hl),e_objpost >> 8
.go:    RSET -21
        ld a,(RVAL)
        ld r,a                      ; 8 M1s to 0x8B4A
        ld hl,(SV_HL)
        nextreg 0x56,GAME_P6
        pop bc
        pop af
        ld a,0x1C                   ; the replaced LD A,0x1C / LD (0x93AD),A
        ld (0x93AD),a
        jp 0x8B4A
; e_objpost: the call's RET lands here (28 MHz): window closed, the latched speed, back to the caller
e_objpost:
        push hl
        push af
        ld a,r                      ; R at the first instruction + 4
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld (WSV_DE),de
        ld (WSV_BC),bc
        xor a
        ld (W_OBJ),a
        call w_close
        RSET -13
        ld de,(WSV_DE)
        ld bc,(WSV_BC)
        ld a,(RVAL)
        ld r,a                      ; 9 M1s to the caller
        ld hl,(RETOBJ)
        ld a,(OUTSPD)
        nextreg 0x56,GAME_P6
        nextreg 0x07,a
        pop af
        ex (sp),hl
        ret

; =============================================================================================
; e_clr: 0x8D63 (after a 32-row draw the game clears 12 bytes = the 4 rows at buffer - 0x5F):
; recorded as a blank build; replays BIT 5,(IX+0), JP 0x8D67.
; =============================================================================================
e_clr:  ENTERST
        push af
        push bc
        push de
        push hl
        call figk
        jr c,.out
        call setk
        bit 5,(ix+0)
        jr z,.b16
        ld l,(ix+0x14)
        ld h,(ix+0x15)
        jr .b
.b16:   ld l,(ix+0x16)
        ld h,(ix+0x17)
.b:     ld de,-0x5F
        add hl,de
        ld (V_DEST),hl
        ld hl,0
        ld (V_SRC),hl
        ld a,4
        ld (V_ROWS),a
        xor a
        ld (V_SHIFT),a
        call ringadd
.out:   ld hl,(TGT)                 ; + the clear and the call's code after it
        ld de,CLRU
        add hl,de
        ld (TGT),hl
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -24
        bit 5,(ix+0)
        jp 0x8D67

; V_DEST / V_SRC / V_ROWS / V_SHIFT -> the newest entry of figure V_K's ring, stamped with SEQ
ringadd:
        ld hl,(V_FP)
        ld de,F_RING
        add hl,de
        ld a,(hl)
        inc a
        and 15
        ld (hl),a
        call ringptr
        ld de,(V_DEST)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_SRC)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(V_ROWS)
        ld (hl),a
        inc hl
        ld a,(V_SHIFT)
        ld (hl),a
        inc hl
        ld de,(SEQ)
        inc de
        ld (SEQ),de
        ld (hl),e
        inc hl
        ld (hl),d
        ret

; =============================================================================================
; e_pl: CALL 0x8ECE at 0x8B5C. Notes the new image (HL / DE / B), lets 0x8ECE return straight
; into e_plp (the draw runs at the original stack depth), then sets figure k's sprite image.
; =============================================================================================
e_pl:   push bc                     ; (A and F are dead here: 0x8ECE loads A first and sets the flags)
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)                    ; NR 7: the incoming speed (28 MHz inside a window)
        nextreg 0x07,3
        ld b,a
        ld a,r                      ; R at the first instruction + 13
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld a,b
        pop bc
        ld (TMP),hl
        ld (TMP+2),de
        ld (TMP+4),bc
        and 3
        ld c,a
        ld a,(W_ON)
        or a
        jp nz,.on
        ld a,c
        ld (LATCH),a                ; given back by e_plp's LEAVEST
        WOPEN
.on:    call pltgt                  ; TGT += the original draw's time; the XOR draw (screen writes NOPs) at 28 MHz
        ld hl,e_plp
        ex (sp),hl                  ; 0x8ECE returns to e_plp instead of 0x8B5F
        RSET -21
        ld a,(RVAL)
        ld r,a                      ; 8 M1s to 0x8ECE
        ld hl,(TMP)
        ld de,(TMP+2)
        ld bc,(TMP+4)
        nextreg 0x56,GAME_P6
        jp 0x8ECE                   ; an interrupt meanwhile goes through isr_w (the handler at 3.5 MHz)
e_plp:  ENTERRET
        push af
        push bc
        push de
        push hl
        call drawfig
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -12
        jp 0x8B5F

drawfig:
        call figk
        ret c
        call setk
        ld a,(ix+2)                 ; visible byte columns after the draw
        or a
        jp z,dhide
        ld a,(TMP+5)                ; B at the draw = rows drawn (28 / 32)
        cp 33
        jr c,.b0
        ld a,32
.b0:    ld (V_B0),a
        ; rows: the newest build (by seq) wins each row; this figure's ring and the previous
        ; figure's (its 28-row builds overrun into this figure's buffers), merged newest first
        ld hl,ROWSRC                ; all 32 rows + shifts zero (rows >= B0 stay blank)
        ld b,96
        xor a
.u0:    ld (hl),a
        inc hl
        djnz .u0
        ld a,(V_B0)
        ld b,a
        ld hl,ROWSRC
.u:     ld (hl),0xFF                ; drawn rows: unassigned
        inc hl
        ld (hl),0xFF
        inc hl
        djnz .u
        xor a
        ld (V_J),a
        dec a
        ld (V_SH2),a                ; 0xFF = no base build yet
        ld a,(V_B0)
        ld (V_LEFT),a
        call walk                   ; pass 1: the base (newest build holding the bottom row)
        ld a,(V_SH2)
        inc a
        jp z,dhide                  ; nothing holds the bottom row
        ld a,(V_B0)
        ld (V_LEFT),a
        call walk                   ; pass 2: every row
        ld a,(V_B0)                 ; unresolved rows -> blank
        ld b,a
        ld hl,ROWSRC
.f:     ld a,(hl)
        inc hl
        and (hl)
        inc a
        jr nz,.f2
        xor a
        ld (hl),a
        dec hl
        ld (hl),a
        inc hl
.f2:    inc hl
        djnz .f
        ld a,(V_B0)
        ld (V_N),a
        ; position: x = 8 * (col(DE) - j) + base shift, bottom row y = y(DE)
        ld de,(TMP+2)
        ld a,e
        and 31
        ld hl,V_J
        sub (hl)
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(V_SH2)
        ld e,a
        ld d,0
        add hl,de
        ld (V_X),hl
        ld de,(TMP+2)
        call scr_y
        ld (V_YB),a
        ld c,(ix+0x0E)
        ld b,(ix+0x0F)
        call getbank
        ld hl,(V_FP)
        ld de,F_BANK
        add hl,de
        ld (hl),a
        call sameimg                ; Z = the image last built for this figure (no upload)
        jr z,.keep
        ld hl,(V_FP)                ; pattern slot: the one not on show
        ld de,F_SLOT
        add hl,de
        ld a,(V_K)
        cp (hl)
        jr nz,.sl
        add a,NFIG
.sl:    ld (V_SLOT),a
        call upload
        jr .rec
.keep:  ld hl,(V_FP)
        ld de,F_NEW
        add hl,de
        ld a,(hl)                   ; a pattern still pending stays pending
        ld (V_SLOT),a
.rec:   ld hl,(V_FP)
        ld (hl),1                   ; F_VIS
        inc hl
        ld de,(V_X)
        ld (hl),e
        inc hl
        ld (hl),d                   ; F_X
        inc hl
        push hl
        ld a,(V_YB)
        ld l,a
        ld h,0
        ld a,(V_N)
        dec a
        ld e,a
        ld d,0
        or a
        sbc hl,de                   ; top row = bottom - (n - 1), 16-bit signed
        ex de,hl
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d                   ; F_YT
        ld hl,(V_FP)
        ld de,F_N
        add hl,de
        ld a,(V_N)
        ld (hl),a                   ; F_N
        inc hl
        ld a,(V_YB)
        ld (hl),a                   ; F_YB
        inc hl
        ld a,(ix+3)
        ld (hl),a                   ; F_FR
        inc hl
        ld de,(CAMERA)
        ld (hl),e
        inc hl
        ld (hl),d                   ; F_CAM
        inc hl
        ld a,(V_SLOT)
        ld (hl),a                   ; F_NEW
        ret

; walk: the builds of figure V_K's ring and figure V_K-1's ring, newest first (merged by seq);
; pass 1 (V_SH2 = 0xFF): find the newest build holding the bottom row (TMP) -> V_J, V_SH2;
; pass 2: each build fills the drawn rows it holds that no newer build filled. Stops when all
; rows are resolved.
walk:   ld hl,(V_FP)
        ld de,F_RING
        add hl,de
        ld a,(hl)
        ld (V_IO),a
        ld a,16
        ld (V_HO),a
        xor a
        ld (V_HP),a
        ld a,(V_K)
        or a
        jr z,.go
        ld hl,(V_FP)
        ld de,F_RING-16
        add hl,de
        ld a,(hl)
        ld (V_IP),a
        ld a,16
        ld (V_HP),a
.go:    ld a,(V_LEFT)
        or a
        ret z
        ld a,(V_HO)
        ld hl,V_HP
        or (hl)
        ret z                       ; both rings done
        ; pick the newer head
        ld a,(V_HO)
        or a
        jr z,.prev
        ld a,(V_HP)
        or a
        jr z,.own
        ld a,(V_K)
        ld (V_M),a
        ld a,(V_IO)
        call ringptrk
        ld de,6
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; own seq
        push de
        ld a,(V_K)
        dec a
        ld (V_M),a
        ld a,(V_IP)
        call ringptrk
        ld de,6
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; previous ring's seq
        pop hl
        or a
        sbc hl,de
        bit 7,h
        jr nz,.prev                 ; own older (16-bit seq, wrap-safe: entries are recent)
.own:   ld a,(V_K)
        ld (V_M),a
        ld a,(V_IO)
        call ringptrk
        ld a,(V_IO)
        dec a
        and 15
        ld (V_IO),a
        ld a,(V_HO)
        dec a
        ld (V_HO),a
        jr .ent
.prev:  ld a,(V_K)
        dec a
        ld (V_M),a
        ld a,(V_IP)
        call ringptrk
        ld a,(V_IP)
        dec a
        and 15
        ld (V_IP),a
        ld a,(V_HP)
        dec a
        ld (V_HP),a
.ent:   call useent
        jp .go

; HL = ring entry: pass 1 / pass 2 work for it
useent: ld e,(hl)
        inc hl
        ld d,(hl)                   ; dest
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)                   ; src
        inc hl
        ld a,(hl)                   ; rows
        or a
        ret z
        ld (V_ROWS),a
        inc hl
        ld a,(hl)
        ld (V_SHIFT),a
        ld (V_SRC),bc
        ld hl,(TMP)
        or a
        sbc hl,de                   ; d = HL0 - dest
        ret c                       ; the build starts above the bottom row's byte
        ld a,h
        or a
        ret nz
        ld a,l
        call mod3                   ; A = d mod 3, C = d div 3 (= buffer row of the bottom drawn row)
        ld b,a
        ld a,(V_SH2)
        inc a
        jr nz,.p2
        ; pass 1: does it hold the bottom row?
        ld a,(V_ROWS)
        cp c
        ret z
        ret c                       ; row C beyond the build
        ld a,b
        ld (V_J),a
        ld a,(V_SHIFT)
        ld (V_SH2),a
        xor a
        ld (V_LEFT),a               ; ends pass 1
        ret
.p2:    ld a,(V_J)
        cp b
        ret nz                      ; rows misaligned with the drawn rows: no row from it
        ; drawn row r (from the bottom) = build row C - r, for r = max(0, C - rows + 1) .. min(B0 - 1, C)
        ld a,(V_SHIFT)
        ld hl,V_SH2
        sub (hl)
        ld (V_M),a                  ; row shift
        ld a,c
        ld (V_I),a                  ; build row of r = 0
        ld b,0                      ; r
.r:     ld a,(V_I)
        sub b
        jr c,.rd                    ; build row < 0: above the build -> done
        ld hl,V_ROWS
        cp (hl)
        jr nc,.rn                   ; below the build's last row
        ld c,a                      ; C = build row
        ld a,(V_B0)
        dec a
        sub b
        jr c,.rd                    ; r beyond the drawn rows
        ld l,a
        ld h,0
        push hl
        add hl,hl
        ld de,ROWSRC
        add hl,de                   ; ROWSRC[B0 - 1 - r]
        ld a,(hl)
        inc hl
        and (hl)
        inc a
        jr nz,.rp                   ; already filled by a newer build
        ld de,(V_SRC)
        ld a,d
        or e
        jr z,.rz
        push hl
        ld l,c
        ld h,0
        add hl,hl
        add hl,de
        ex de,hl                    ; src + 2 * build row
        pop hl
.rz:    ld (hl),d
        dec hl
        ld (hl),e
        pop hl
        push hl
        ld de,ROWSH
        add hl,de
        ld a,(V_M)
        ld (hl),a
        ld hl,V_LEFT
        dec (hl)
.rp:    pop hl
.rn:    inc b
        ld a,(V_LEFT)
        or a
        jr nz,.r
.rd:    ret

; Z if ROWSRC / ROWSH (V_N rows) equal the figure's last built image; else copies them there
sameimg:
        ld a,(V_K)
        ld l,a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,de                   ; 3k
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                   ; 96k
        ld de,LASTIMG
        add hl,de
        push hl
        ld de,ROWSRC
        ld b,64
.c:     ld a,(de)
        cp (hl)
        jr nz,.diff
        inc hl
        inc de
        djnz .c
        ld de,ROWSH
        ld b,32
.c2:    ld a,(de)
        cp (hl)
        jr nz,.diff
        inc hl
        inc de
        djnz .c2
        pop hl
        xor a                       ; Z
        ret
.diff:  pop de                      ; copy the new image
        ld hl,ROWSRC
        ld bc,64
        ldir
        ld hl,ROWSH
        ld bc,32
        ldir
        or 1                        ; NZ
        ret

dhide:  ld hl,(V_FP)
        ld (hl),0
        ret

; A (0-255) -> A = A mod 3, C = A div 3
mod3:   ld c,0
.l:     cp 3
        ret c
        sub 3
        inc c
        jr .l

; IX object -> A = k (buffer pair (IX+0x14 - BUFBASE) / 192), carry = not a figure
figk:   push hl
        push bc
        ld l,(ix+0x14)
        ld h,(ix+0x15)
        ld bc,BUFBASE
        or a
        sbc hl,bc
        jr c,.no
        ld bc,192
        xor a
.l:     or a
        sbc hl,bc
        jr c,.ok
        inc a
        cp NFIG
        jr c,.l
.no:    pop bc
        pop hl
        scf
        ret
.ok:    pop bc
        pop hl
        or a
        ret

; A = k -> V_K, V_FP = FIG + 16k
setk:   ld (V_K),a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,FIG
        add hl,de
        ld (V_FP),hl
        ret

; A = ring index -> HL = RING + 128 * V_K + 8 * A
ringptr:
        push af
        ld a,(V_K)
        ld (V_M),a
        pop af
; A = ring index, V_M = figure -> HL = RING + 128 * V_M + 8 * A
ringptrk:
        push de
        and 15
        add a,a
        add a,a
        add a,a
        ld e,a
        ld a,(V_M)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld d,0
        add hl,de
        ld de,RING
        add hl,de
        pop de
        ret

; DE = screen address -> A = pixel y
scr_y:  ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or b
        ld b,a
        ld a,d
        and 7
        or b
        ret

; C = strip, B = socks (Spectrum colours, low 3 bits) -> A = palette bank (allocated on first use)
getbank:
        ld a,c
        and 7
        add a,a
        add a,a
        add a,a
        ld e,a
        ld a,b
        and 7
        or e
        ld e,a
        ld d,0
        ld hl,COMBO
        add hl,de
        ld a,(hl)
        or a
        jr z,.new
        dec a
        ret
.new:   ld a,(NBANK)
        cp 16
        jr c,.f
        ld a,15                     ; all 16 in use (never in a match): reuse the last
        jr .w
.f:     inc a
        ld (NBANK),a
        dec a
.w:     inc a
        ld (hl),a
        dec a
        push af
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        add a,a
        add a,a
        add a,a
        add a,a
        inc a
        nextreg 0x40,a              ; index 16 * bank + 1 = STRIP, + 2 = SOCKS
        ld a,c
        call spec
        nextreg 0x41,a
        ld a,b
        call spec
        nextreg 0x41,a
        pop af
        ret
spec:   and 7
        ld e,a
        ld d,0
        ld hl,SPECCY
        add hl,de
        ld a,(hl)
        ret
SPECCY: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6

; upload: V_N rows of ROWSRC (graphics row addresses, 0 = blank) shifted by ROWSH (pixels) as the
; 32-row image in 256-byte slot V_SLOT
upload: ld a,(V_SLOT)
        ld bc,0x303B
        out (c),a
        xor a
        ld (V_I),a                  ; row
.r:     ld a,(V_I)
        ld hl,V_N
        cp (hl)
        jr nc,.zero
        ld l,a
        ld h,0
        push hl
        add hl,hl
        ld de,ROWSRC
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        push de
        ld de,ROWSH
        add hl,de
        ld a,(hl)
        sra a                       ; nibble bytes to shift (signed)
        ld (V_M),a
        pop de
        ld a,d
        or e
        jr z,.zero
        call rowptr                 ; HL = 8 nibble bytes of row DE (its page at slot 6), C: none
        jr c,.zero0
        ld a,e                      ; E = nibble shift (rowptr keeps it)
        or a
        jr nz,.sh
        ld bc,0x085B
        otir
        jr .nx
.sh:    jp p,.right
        neg                         ; left by A bytes: skip A, output 8-A, then A zeros
        ld e,a
        ld d,0
        add hl,de
        ld b,a
        ld a,8
        sub b
        ld b,a
        ld c,0x5B
        otir
        ld a,e
        jr .zz
.right: ld b,a                      ; right by A bytes: A zeros, then 8-A bytes
        ld e,a
        xor a
.rz:    out (0x5B),a
        djnz .rz
        ld a,8
        sub e
        ld b,a
        ld c,0x5B
        otir
        jr .nx
.zero0: nextreg 0x56,STATE_PG
.zero:  ld a,8
.zz:    ld b,a
        xor a
.z:     out (0x5B),a
        djnz .z
.nx:    nextreg 0x56,STATE_PG       ; state page back for the next row
        ld a,(V_I)
        inc a
        ld (V_I),a
        cp 32
        jp c,.r
        ret

; DE = graphics row address, V_M = nibble shift -> HL = its 8 nibble bytes, E = the shift
; (a frame row: its table page is now at slot 6 - the state page is out; a ball row: in the
; state page), C: no such row (state page still in)
rowptr: ld a,(V_M)
        push af
        ld hl,FRAME0
        ex de,hl
        or a
        sbc hl,de                   ; HL = src - FRAME0
        jr c,.ball
        ld de,FRAMEEND-FRAME0
        push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.none
        ld a,h
        rrca
        rrca
        rrca
        and 0x1F                    ; t >> 11
        add a,NIB_PG
        add hl,hl
        add hl,hl                   ; t * 4
        ld e,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld a,e
        nextreg 0x56,a
        pop af
        ld e,a
        or a
        ret
.ball:  add hl,de                   ; back to src
        ld de,BALL0
        or a
        sbc hl,de
        jr c,.none
        ld a,h
        or a
        jr nz,.none
        ld a,l
        cp BALLEND-BALL0
        jr nc,.none
        add hl,hl
        add hl,hl
        ld de,BALLTAB
        add hl,de
        pop af
        ld e,a
        or a
        ret
.none:  pop af
        scf
        ret

; =============================================================================================
; e_ball: CALL 0x9FCF at 0x9D15 (ball + shadow); afterwards ($A0C0) / ($A0D1) = the ball's new
; screen address (right byte, bottom row) / graphics end, ($A0C2) / ($A0D3) the shadow's;
; an address below 0x4000 = not drawn.
; =============================================================================================
e_ball: push bc                     ; (A, F, BC, DE and HL are dead here: 0x9FCF loads them before any use)
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        ld b,a
        ld a,r                      ; R at the first instruction + 13
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld a,b
        pop bc
        ld (TMP),hl
        ld (TMP+4),bc
        and 3
        ld c,a
        ld a,(W_ON)
        or a
        jp nz,.on
        ld a,c
        ld (LATCH),a
        WOPEN
.on:    ld hl,(TGT)                 ; the ball routine (screen writes NOPs) at 28 MHz and e_bpost's work:
        ld bc,BALLU                 ; target += the original routine's mean time
        add hl,bc
        ld (TGT),hl
        ld hl,e_bpost
        ex (sp),hl
        RSET -19
        ld a,(RVAL)
        ld r,a                      ; 6 M1s to 0x9FCF
        ld bc,(TMP+4)
        ld hl,(TMP)
        nextreg 0x56,GAME_P6
        jp 0x9FCF
e_bpost:
        ENTERRET
        push af
        push bc
        push de
        push hl
        ld a,(BALLR+F_SLOT)         ; the slot not on show
        cp SLOT_BALL
        ld a,SLOT_BALL
        jr nz,.s
        inc a
.s:     ld (V_SLOT),a
        ld hl,ROWSRC                ; 32 rows: ball 5 rows + 11 blank | shadow 1 row + 15 blank
        ld b,96                     ; (ROWSRC and ROWSH: no row shifts)
        xor a
.c:     ld (hl),a
        inc hl
        djnz .c
        ld hl,(0xA0D1)              ; ball graphics end: rows end-9 .. end-1 (2 bytes, top first)
        ld de,-9
        add hl,de
        ex de,hl
        ld hl,ROWSRC
        ld b,5
.br:    ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        inc de
        inc de
        djnz .br
        ld hl,(0xA0D3)
        dec hl
        ld (ROWSRC+32),hl
        ld a,32
        ld (V_N),a
        call upload
        ld a,(V_SLOT)
        ld (BALLR+F_NEW),a
        ld de,(0xA0C0)
        ld hl,BALLR
        ld c,4                      ; top row = bottom - 4
        call ballrec
        ld de,(0xA0C2)
        ld hl,SHADR
        ld c,0
        call ballrec
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -12
        jp 0x9D18

; DE = new screen address (right byte, bottom row), HL = record, C = rows - 1
ballrec:
        ld (V_ADDR),hl
        ld a,d
        cp 0x40
        jr c,.off
        cp 0x58
        jr c,.on
.off:   ld (hl),0
        ret
.on:    ld (hl),1                   ; F_VIS
        push bc
        call scr_y                  ; A = bottom row y
        pop bc
        ld (V_YB),a
        ld a,e
        and 31
        dec a                       ; left byte = col - 1
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ex de,hl                    ; DE = x
        ld hl,(V_ADDR)
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d                   ; F_X
        inc hl
        ld a,(V_YB)
        sub c
        ld e,a
        sbc a,a
        ld d,a                      ; y - (rows - 1), 16-bit signed (y < 128 when it borrows)
        ld a,(V_YB)
        cp c
        jr c,.neg
        ld d,0
.neg:   ld (hl),e
        inc hl
        ld (hl),d                   ; F_YT
        inc hl
        ld (hl),0                   ; F_BANK 0 (ball colours are fixed indices)
        ld hl,(V_ADDR)
        ld de,F_YB
        add hl,de
        ld a,(V_YB)
        ld (hl),a
        ret

; =============================================================================================
; e_frame: CALL 0x9898 at 0x817F (once per match loop pass): new patterns on show, the dive's
; spare half locked to the keeper half, sprites written in depth order; then JP 0x9898.
; =============================================================================================
e_frame:
        ENTERST
        push hl
        push af
        push de
        ld hl,(TGT)                 ; + the replaced CALL 0x9898: 17 T
        inc hl
        ld de,1                     ; + the crowd copier 0x9898 (v2.1: at 28 MHz in this window): RET when
        ld a,(0x9898)               ; nothing to copy (10 T), else 18359 T after a camera move, 19316 T without
        cp 0xC9
        jr z,.cr
        ld de,CRU_SAME
        ld a,(CAMERA)
        push hl
        ld hl,0x9A43
        cp (hl)
        pop hl
        jr z,.cr
        ld de,CRU_MOVE
.cr:    ld (LASTCR),de
        add hl,de
        ld (TGT),hl
        pop de
        pop af
        pop hl
        push af
        push bc
        push de
        push hl
        ld hl,FIG                   ; promote built patterns, F_XS = F_X
        ld b,NREC
.p:     push hl
        push bc
        ld de,F_NEW
        add hl,de
        ld a,(hl)
        cp 0xFF
        jr z,.p2
        ld (hl),0xFF
        pop bc
        pop hl
        push hl
        push bc
        ld de,F_SLOT
        add hl,de
        ld (hl),a
.p2:    pop bc
        pop hl
        push hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; F_X
        pop hl
        push hl
        push de
        ld de,F_XS
        add hl,de
        pop de
        ld (hl),e
        inc hl
        ld (hl),d
        pop hl
        ld de,16
        add hl,de
        djnz .p
        call divelock
        ; sort list: (bottom y, id) of every visible figure and the ball
        ld hl,SORTB
        ld (V_ADDR),hl
        xor a
        ld (V_SORTN),a
        ld c,0
.f:     ld a,c
        call setk
        ld hl,(V_FP)
        ld a,(hl)
        or a
        jr z,.f2
        ld de,F_YB
        add hl,de
        ld a,(hl)
        call sortadd
.f2:    inc c
        ld a,c
        cp NFIG
        jr c,.f
        ld a,(BALLR+F_VIS)
        or a
        jr z,.srt
        ld a,(SHADR+F_VIS)
        or a
        ld a,(SHADR+F_YB)
        jr nz,.bk
        ld a,(BALLR+F_YB)
.bk:    ld c,NFIG
        call sortadd
.srt:   call sort
        xor a
        ld (EMS),a
        ld a,(SHADR+F_VIS)
        or a
        jr z,.e0
        ld hl,SHADR
        ld a,(BALLR+F_SLOT)
        add a,a
        inc a
        call emit1
.e0:    ld hl,SORTB
        ld a,(V_SORTN)
        or a
        jr z,.hide
        ld b,a
.e:     push bc
        inc hl
        ld a,(hl)                   ; id
        inc hl
        push hl
        cp NFIG
        jr nz,.ef
        ld hl,BALLR
        ld a,(BALLR+F_SLOT)
        add a,a
        call emit1
        jr .en
.ef:    call setk
        ld hl,(V_FP)
        call emitfig
.en:    pop hl
        pop bc
        djnz .e
.hide:  ld a,(NSPR)                 ; hide what the last pass showed beyond this one
        ld b,a
        ld a,(EMS)
        ld (NSPR),a
.h:     cp b
        jr nc,.done
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        jr .h
.done:  ld hl,(SAVSP)               ; the copier returns to e_frpost (its own return kept in RETFR)
        ld e,(hl)
        ld (hl),e_frpost & 255
        inc hl
        ld d,(hl)
        ld (hl),e_frpost >> 8
        ld (RETFR),de
        pop hl
        pop de
        pop bc
        pop af
        LEAVEKEEP -20
        jp 0x9898
; e_frpost: the copier's RET lands here (28 MHz, window open): window closed, the debt paid, the latched speed,
; back to the match loop (0x8182)
e_frpost:
        push hl
        push af
        ld a,r                      ; R at the first instruction + 4
        nextreg 0x56,STATE_PG
        ld (RSAVE),a
        ld (WSV_DE),de
        ld (WSV_BC),bc
        call w_close
        call w_pay
        RSET -13
        ld de,(WSV_DE)
        ld bc,(WSV_BC)
        ld a,(RVAL)
        ld r,a                      ; 9 M1s to the caller
        ld hl,(RETFR)
        ld a,(OUTSPD)
        nextreg 0x56,GAME_P6
        nextreg 0x07,a
        pop af
        ex (sp),hl
        ret

; A = key, C = id -> SORTB
sortadd:
        ld hl,(V_ADDR)
        ld (hl),a
        inc hl
        ld (hl),c
        inc hl
        ld (V_ADDR),hl
        ld hl,V_SORTN
        inc (hl)
        ret

; insertion sort of SORTB by key (ascending: far first, near last = on top)
sort:   ld a,(V_SORTN)
        cp 2
        ret c
        ld c,1                      ; i
.o:     ld a,c
        ld hl,V_SORTN
        cp (hl)
        ret nc
        ld b,c                      ; j = i
.in:    ld a,b
        or a
        jr z,.ni
        add a,a
        ld e,a
        ld d,0
        ld hl,SORTB
        add hl,de                   ; HL -> entry j
        dec hl
        dec hl                      ; entry j-1
        ld a,(hl)
        inc hl
        inc hl
        cp (hl)                     ; key[j-1] - key[j]
        jr c,.ni
        jr z,.ni
        ld d,(hl)                   ; swap entries j-1, j
        inc hl
        ld e,(hl)
        dec hl
        dec hl
        dec hl
        ld a,(hl)
        ld (hl),d
        inc hl
        inc hl
        ld (hl),a
        dec hl
        ld a,(hl)
        ld (hl),e
        inc hl
        inc hl
        ld (hl),a
        dec b
        jr .in
.ni:    inc c
        jr .o

; HL = figure record: 1 or 2 sprites (rows 0-15, 16-31)
emitfig:
        push hl
        ld de,F_SLOT
        add hl,de
        ld a,(hl)
        add a,a
        pop hl
        push hl
        push af
        call emit1
        pop af
        pop hl
        push hl
        ld de,F_N
        add hl,de
        ld b,a
        ld a,(hl)
        cp 17
        ld a,b
        pop hl
        ret c
        inc a
        push af
        ld de,F_YT
        push hl
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,16
        add hl,de
        ld (E_Y),hl
        pop hl
        pop af
        jr emit2

; HL = record (F_XS, F_YT, F_BANK), A = 4-bit pattern -> one sprite in slot EMS
emit1:  push af
        push hl
        ld de,F_YT
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (E_Y),de
        pop hl
        pop af
emit2:  ld (E_PAT),a
        push hl
        ld de,F_BANK
        add hl,de
        ld a,(hl)
        ld (E_BANK),a
        pop hl
        ld de,F_XS
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,32
        add hl,de                   ; X = x + 32
        ld a,(EMS)
        cp 64
        ret nc
        nextreg 0x34,a
        inc a
        ld (EMS),a
        ld a,l
        nextreg 0x35,a
        ld a,(E_BANK)
        add a,a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,h
        and 1
        or l
        ld l,a                      ; attr 2: palette offset, X8
        ld de,(E_Y)
        ld a,e
        add a,32
        ld e,a
        ld a,d
        adc a,0
        ld d,a                      ; Y = y + 32
        ld a,e
        nextreg 0x36,a
        ld a,l
        nextreg 0x37,a
        ld a,(E_PAT)
        srl a
        or 0xC0
        nextreg 0x38,a              ; visible, 5th byte, pattern N
        ld a,(E_PAT)
        and 1
        rrca
        rrca
        or 0x80
        ld e,a
        ld a,d
        and 1
        or e
        nextreg 0x39,a              ; 4-bit, N6, Y8
        ret

; the keeper's dive: the spare half (figure SPARE) where it would be at the keeper half's camera
divelock:
        ld a,SPARE
        call setk
        ld hl,(V_FP)
        ld a,(hl)
        or a
        ret z
        ld de,F_FR
        add hl,de
        ld a,(hl)
        cp DIVE0
        ret c
        ld c,0
.l:     ld a,c
        cp SPARE
        jr z,.n
        call setk
        ld hl,(V_FP)
        ld a,(hl)
        or a
        jr z,.n
        ld de,F_FR
        add hl,de
        ld a,(hl)
        cp DIVE0
        jr nc,.got
.n:     inc c
        ld a,c
        cp NFIG
        jr c,.l
        ret
.got:   inc hl                      ; F_CAM of the keeper half
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,FIG+16*SPARE+F_CAM
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        or a
        sbc hl,de                   ; cam(spare) - cam(keeper)
        ex de,hl
        ld hl,(FIG+16*SPARE+F_X)
        add hl,de
        ld (FIG+16*SPARE+F_XS),hl
        ret

; =============================================================================================
; e_cls: CALL 0xEFAD at 0xE62C (screen clear when a match is set up); e_exit: 0x819D DI / LD A,0
; (match loop exit). Both hide every sprite and forget every figure.
; =============================================================================================
e_cls:  ENTERST
        push hl
        ld hl,(TGT)                 ; + the replaced CALL 0xEFAD
        inc hl
        ld (TGT),hl
        pop hl
        push af
        push bc
        push de
        push hl
        call hideall
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -23
        jp 0xEFAD
e_exit: ENTERST
        push hl
        ld hl,(TGT)                 ; + the replaced DI / LD A,0
        inc hl
        ld (TGT),hl
        pop hl
        push af
        push bc
        push de
        push hl
        call hideall
        pop hl
        pop de
        pop bc
        pop af
        LEAVEST -24
        di
        ld a,0
        jp 0x81A0

; =============================================================================================
; isr_w / isr_x: the game's IM 2 handler (0xFFFF -> 0xFFF4 -> 0x89F0 .. 0x8A22) plays its beeper
; sound with timed loops (0xB381..0xB3C4: OUT (0xFE) per bit), so it must run at 3.5 MHz even
; when the interrupt lands in 28 MHz code (a hook, or the game's XOR draw). The IM 2 vector (alt
; ROM word at 0x3BFF, set by matchday.py) points at isr_w: it keeps the interrupted speed in
; NextReg 0x7F (the free user register: no RAM), sets 3.5 MHz and JUMPS to 0xFFFF; the handler's
; one exit 0x8A20 POP HL / EI / RET is JP isr_x, which restores the speed. No stack depth is added
; to the handler's own (24 bytes): isr_w / isr_x use 4 bytes at its shallow ends (the match stack
; has game variables 18 bytes below its deepest point, 0x89A8; RZX scan 2026-10-20).
; =============================================================================================
isr_w:  push af
        ld a,r                      ; R after the interrupt's acceptance + 3
        push bc
        push hl
        ld h,a
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)                    ; NextReg 7: bits 1-0 = the speed set
        nextreg 0x7F,a
        nextreg 0x07,3              ; the book-keeping at 28 MHz
        dec b
        ld a,0x56
        out (c),a
        inc b
        in a,(c)                    ; the page at slot 6 (game, state or a row table)
        push af
        nextreg 0x56,STATE_PG
        ld a,h
        ld (ISR_R),a
        call isr_line
        ld (ISRL0),hl
        ld a,(ISR_R)                ; R for 0xFFFF: as the original reaches it (6 M1s after the LD R,A)
        and 0x80
        ld l,a
        ld a,(ISR_R)
        add a,(-9) & 0x7F
        and 0x7F
        or l
        ld l,a
        pop af
        nextreg 0x56,a
        ld a,l
        ld r,a
        pop hl
        pop bc
        pop af
        nextreg 0x07,0
        jp 0xFFFF
isr_x:  pop hl                      ; (the replaced POP HL)
        push af
        ld a,r                      ; R at isr_x + 4
        push bc
        push de
        push hl
        ld e,a
        nextreg 0x07,3
        ld bc,0x243B
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        push af
        nextreg 0x56,STATE_PG
        ld a,e
        ld (ISR_R),a
        call isr_line
        ld de,(ISRL0)
        or a
        sbc hl,de
        jr nc,.p
        ld de,NLINES
        add hl,de
.p:     ld de,(ISRACC)
        add hl,de
        ld (ISRACC),hl
        ld a,(ISR_R)                ; R after the RET: as the original's (6 M1s after the LD R,A)
        and 0x80
        ld e,a
        ld a,(ISR_R)
        add a,(-8) & 0x7F
        and 0x7F
        or e
        ld e,a
        pop af
        nextreg 0x56,a
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        and 3
        ld l,a
        dec b
        ld a,7
        out (c),a                   ; register 7 selected again
        ld a,l
        nextreg 0x07,a
        ld a,e
        ld r,a
        pop hl
        pop de
        pop bc
        pop af
        ei
        ret
; isr_line: HL = video line (interrupts are off in the handler); A, BC lost
isr_line:
.r:     ld bc,0x243B
        ld a,0x1E
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        xor h
        and 1
        jr nz,.r
        ld a,h
        and 1
        ld h,a
        ret

; pbcopy: the printer buffer bytes the hook stack uses, HL -> DE (unrolled LDI: 16 T a byte, LDIR's 21)
pbcopy: DUP HSTACK-HSTKLO
        ldi
        EDUP
        ret
; ---- pace windows (state page in; no pushes; LINEHL once per routine) ----
; w_close: the open window ends: DEBT += 16 x (lines since it opened, less the interrupt handler's) - TGT, clamped
; to -16128 .. 9984. A, BC, DE, HL lost.
w_close:
        ld a,(W_OBJ)
        or a
        jr z,.c
        ld a,3                      ; inside e_objs / e_obj: the window stays open, the game's code goes on at
        ld (OUTSPD),a               ; 28 MHz; its lines so far go to W_ACC (a long window: no unseen wrap)
        ld a,(W_ON)
        or a
        ret z
        call w_since
        ld de,(W_ACC)
        add hl,de
        ld (W_ACC),hl
        ret
.c:     ld a,(LATCH)
        ld (OUTSPD),a
        ld a,(W_ON)
        or a
        ret z
        xor a
        ld (W_ON),a
        LINEHL
        ld de,(W_L0)
        or a
        sbc hl,de
        jr nc,.p
        ld de,NLINES
        add hl,de
.p:     ld de,(W_ACC)
        add hl,de
        ex de,hl
        ld hl,(ISRACC)
        ld bc,(W_I0)
        or a
        sbc hl,bc
        ex de,hl
        or a
        sbc hl,de
        jr nc,.q
        ld hl,0
.q:     add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(TGT)
        or a
        sbc hl,de
        ld de,(DEBT)
        add hl,de
        bit 7,h
        jr nz,.neg
        ld a,h
        cp 0x50
        jr c,.st
        ld hl,0x5000                ; at most 1280 lines (about 4 frames) behind carried
        jr .st
.neg:   ld a,h
        cp 0xC1
        jr nc,.st
        ld hl,0xC100
.st:    ld (DEBT),hl
        ret
; w_since: HL = lines since W_L0, less ISRACC - W_I0 (>= 0); W_L0 / W_I0 = now. A, BC, DE, HL lost.
w_since:
        LINEHL
        ld de,(W_L0)
        ld (W_L0),hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,NLINES
        add hl,de
.p:     ex de,hl
        ld hl,(ISRACC)
        ld bc,(W_I0)
        ld (W_I0),hl
        or a
        sbc hl,bc
        ex de,hl
        or a
        sbc hl,de
        ret nc
        ld hl,0
        ret
; w_pay: while the build is ahead of the original (DEBT < 0), wait on the video line (interrupt time does not pay)
w_pay:  ld hl,(DEBT)
        bit 7,h
        ret z
        ld hl,(V_WAITS)
        inc hl
        ld (V_WAITS),hl
        call w_since                ; the base = now
        ld hl,0
        ld (V_POLL),hl
.l:     call w_since
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(DEBT)
        add hl,de
        ld (DEBT),hl
        bit 7,h
        ret z
        ld hl,(V_POLL)
        dec hl
        ld (V_POLL),hl
        ld a,h
        or l
        jr nz,.l
        ld hl,0                     ; no line counter (an emulator without NR 0x1E / 0x1F): give up
        ld (DEBT),hl
        ret
; pltgt: TGT = draw_base[key] + draw_adj[key2] - FIXU (tables in page TAB_PG), LASTPL = their sum, from the draw's
; entry state (TMP = HL, DE, BC; 0x93A2 / 0x93A4 / 0x93A7-A / 0x93AC; IX+0x19). Keys as matchday_v21.draw_keys.
; A, BC, DE, HL lost; no pushes.
pltgt:  ld a,(0x93AC)
        and 7
        ld c,a                      ; base key bits 0-2: the dispatch value
        ld a,(TMP+5)
        cp 32
        jr nz,.b1
        set 3,c                     ; bit 3: 32 rows
.b1:    ld hl,(0x93A9)
        ld de,(TMP+2)
        or a
        sbc hl,de
        ld a,0
        jr nz,.b2
        set 4,c                     ; bit 4: drawn at the old address
        inc a
.b2:    ld (WSV_BC),a
        ld a,(0x93A2)
        or a
        jr z,.b3
        set 5,c                     ; bit 5: 0x93A2 set
.b3:    bit 7,(ix+0x19)
        jr z,.b4
        set 6,c                     ; bit 6: IX+0x19 bit 7
.b4:    ld a,(0x93A7)               ; bit 7: the same attribute address (low bytes, high bits 4-3)
        ld hl,0x93A9
        cp (hl)
        jr nz,.b5
        ld a,(0x93AA)
        ld hl,0x93A8
        xor (hl)
        and 0x18
        jr nz,.b5
        set 7,c
.b5:    ld a,(0x93A4)
        and 3
        ld h,a                      ; bits 8-9: 0x93A4
        ld l,c
        add hl,hl
        ld a,h
        or 0xC0
        ld h,a
        ld (WSV_DE),hl              ; the base entry's address
        ld a,(0x93AA)               ; key2 = AC | same << 3 | new row phase << 4 | old row phase << 7
        and 7
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(TMP+3)
        and 7
        or l
        ld l,a
        add hl,hl
        ld a,(WSV_BC)
        or l
        ld l,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(0x93AC)
        and 7
        or l
        ld l,a
        add hl,hl
        ld a,h
        or 0xC8
        ld h,a                      ; HL = the adjust entry's address
        ld bc,(WSV_DE)
        nextreg 0x56,TAB_PG
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(bc)
        ld l,a
        inc bc
        ld a,(bc)
        ld h,a
        add hl,de
        nextreg 0x56,STATE_PG
        ld (LASTPL),hl
        ld de,DRAWU
        add hl,de
        ld de,(TGT)
        add hl,de
        ld (TGT),hl
        ret
hideall:
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 64
        jr c,.h
        xor a
        ld (NSPR),a
        ld (NBANK),a
        ld hl,FIG
        ld b,NREC
.f:     ld (hl),0                   ; F_VIS
        push hl
        ld de,F_NEW
        add hl,de
        ld (hl),0xFF
        pop hl
        ld de,16
        add hl,de
        djnz .f
        ld hl,COMBO
        ld b,64
        xor a
.c:     ld (hl),a
        inc hl
        djnz .c
        ret

rom_end:

; --- setup (stub bank, 0xD000): sprite palette (16 banks: 0 transparent, 1 STRIP, 2 SOCKS,
; 3-15 the fixed colours), every sprite hidden, sprites on (over the ULA, clipped to the screen)
        ORG 0xD000
setup:  ld bc,0x243B                ; NextReg 7 selected (the hooks read the incoming speed with one IN)
        ld a,7
        out (c),a
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld c,16
.b:     ld hl,PALROW
        ld b,16
.i:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .i
        dec c
        jr nz,.b
        nextreg 0x4B,0              ; sprite transparency index 0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
PALROW: db 0xE3,0xB6,0xB6,0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0x1C,0xFC,0xFF   ; fill = 13 (bright green 0x1C, the pitch paper: attr 0x67)
setup_end:

        SAVEBIN "md21_rom.bin",ROM_ORG,rom_end-ROM_ORG
        SAVEBIN "md21_setup.bin",0xD000,setup_end-0xD000
