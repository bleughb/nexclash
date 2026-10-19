; im2hold.asm - hardware test for BRIEFING C2 #38 (Next hardware IM2 mode holds interrupts).
; GPL-3.0-or-later, part of nexclash. Build: python tools/hwtests/build.py im2hold
;
; Questions (each answered on a real Next, then in MAME / CSpect for comparison):
;  T1 vector     hardware IM2 mode: the ULA interrupt's vector byte is $16 (I*256+$16 is read)
;  T2 held       hardware IM2 mode: an interrupt that comes during a 3-frame DI is TAKEN at EI
;  T3 pulse      control: the same in pulse mode ($C0 = 0) is LOST (count 0 expected)
;  T4 ret-ack    info: a handler ending EI;RET (no RETI) in hardware mode - interrupts per frame
;  T5 tramp      the RETI-to-handler trampoline: vector -> RETI into a game-style EI;RET handler,
;                5 frames -> 4..6 handler runs, and the interrupted code carries on
;  T6 uniform    a game-style uniform 257-byte IM2 table works unchanged in hardware mode
;  T7 recover    after T4 (a handler that never RETIs), does one dummy RETI with interrupts off
;                let interrupts come again? (uniform table, 5 frames -> 4..6 runs)
; Order: T1 T2 T3 T5 T6 T4 T7 - T4 runs late because a non-acknowledged interrupt may block the
; rest (version 1 on a board, 2026-10-20: T1-T3 green, T5 + T6 red right after T4).
; Version 2 prints each test's detail byte in hex under its block (character row 5).
;
; Results table at RESULTS ($7E00): "NXHT", version, test count, then per test 2 bytes:
;   status (0 not run, 1 pass, 2 fail, 3 info) and a detail byte (an interrupt count).
; Final screen: per test a 2x2 block on character rows 2-3 from column 2, 3 columns apart:
;   green pass, red fail, white info, black not run. Border green = no test failed, red = one did.
; MAME headless: read the table at $7E00 once the border is green or red.

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

RESULTS     equ $7E00
NTESTS      equ 7
CNT         equ $7DF0           ; interrupt counter (handlers increment it)
RIGHT       equ $7DF1           ; T1: the right handler ran
WRONG       equ $7DF2           ; T1: a wrong vector's handler ran
VTAB        equ $9000           ; T1 / T2 / T4 / T5 vector page (I = $90), 256 words + 1 byte
UTAB        equ $A000           ; T3 / T6 uniform table, 257 bytes of $A1 (I = $A0)
UHANDLER    equ $A1A1           ; where a uniform $A1 table points

        org $8000
start:
        di
        ld sp,$7DE0
        nextreg $07,3           ; 28 MHz: the raster waits below are line-exact either way
        ; results header
        ld hl,RESULTS
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'H' : inc hl : ld (hl),'T' : inc hl
        ld (hl),2 : inc hl      ; version
        ld (hl),NTESTS : inc hl
        ld b,NTESTS*2
.clr:   ld (hl),0 : inc hl : djnz .clr
        call cls
        call build_tables
        ; uniform handler copied to $A1A1
        ld hl,uh_src : ld de,UHANDLER : ld bc,uh_len : ldir

        call t1_vector
        call t2_held
        call t3_pulse
        call t5_tramp
        call t6_uniform
        call t4_retack
        call t7_recover

        ; back to the boot state: pulse mode, ULA interrupt only, IM 1
        di
        nextreg $C0,0
        nextreg $C4,1
        im 1
        ld a,$3F : ld i,a
        call show
.done:  jr .done

; ---------------------------------------------------------------- tests
; T1: every vector except $16 points at h_wrong; $16 at h_right.
t1_vector:
        call hw_mode
        xor a : ld (RIGHT),a : ld (WRONG),a
        ld hl,h_right : ld (VTAB+$16),hl
        ld a,VTAB>>8 : ld i,a
        im 2
        ei
        halt                    ; one ULA interrupt
        di
        ld hl,h_wrong : ld (VTAB+$16),hl
        ld a,(WRONG) : or a : jr nz,.f
        ld a,(RIGHT) : or a : jr z,.f
        ld a,1 : ld c,a : jr .r
.f:     ld a,(WRONG) : ld c,a : ld a,2
.r:     ld b,1 : jp result

; T2: hardware mode, DI over 3 frames, then EI: the held interrupt must come at once.
t2_held:
        call hw_mode
        ld hl,h_count : ld (VTAB+$16),hl
        ld a,VTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        ld b,3 : call frames    ; interrupts off the whole time
        ei
        nop : nop : nop : nop
        di
        ld a,(CNT) : ld c,a
        or a : ld a,1 : jr nz,.r
        ld a,2
.r:     ld b,2 : jp result

; T3: control - pulse mode, uniform table (the bus vector is not defined), same DI + EI.
t3_pulse:
        call pulse_mode
        ld a,UTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        ld b,3 : call frames
        ei
        nop : nop : nop : nop
        di
        ld a,(CNT) : ld c,a
        or a : ld a,1 : jr z,.r ; lost = the expected pulse behaviour
        ld a,2
.r:     ld b,3 : jp result

; T4: info - handler ends with EI;RET only. Count handler runs over one frame.
t4_retack:
        call hw_mode
        ld hl,h_noreti : ld (VTAB+$16),hl
        ld a,VTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        call frame_start
        ei
        call wait_line_100_again ; one whole frame with interrupts on
        di
        ld hl,h_count : ld (VTAB+$16),hl
        call ack_all            ; clear whatever is still pending
        ld a,(CNT) : ld c,a
        ld a,3 : ld b,4 : jp result

; T5: trampoline - vector -> push the game handler, RETI (acknowledge) -> game handler EI;RET.
t5_tramp:
        call hw_mode
        ld hl,tramp : ld (VTAB+$16),hl
        ld a,VTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        call frame_start
        ei
        ld b,5 : call frames_ei ; 5 frames with interrupts on, foreground keeps running
        di
        ld a,(CNT) : ld c,a
        call in_4_6
        ld b,5 : jp result

; T6: game-style uniform table ($A0 page, 257 x $A1 -> handler at $A1A1) in hardware mode.
t6_uniform:
        call hw_mode
        ld a,UTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        call frame_start
        ei
        ld b,5 : call frames_ei
        di
        ld a,(CNT) : ld c,a
        call in_4_6
        ld b,6 : jp result

; T7: after T4, one dummy RETI (interrupts off), then the uniform table count again.
t7_recover:
        call hw_mode
        call do_reti            ; RETI as a plain return: the controller sees the acknowledge
        ld a,UTAB>>8 : ld i,a
        im 2
        xor a : ld (CNT),a
        call frame_start
        ei
        ld b,5 : call frames_ei
        di
        ld a,(CNT) : ld c,a
        call in_4_6
        ld b,7 : jp result
do_reti: reti

; A = 1 when C is 4..6, else 2
in_4_6: ld a,c : cp 4 : jr c,.n : cp 7 : jr nc,.n
        ld a,1 : ret
.n:     ld a,2 : ret

; ---------------------------------------------------------------- interrupt modes
; hardware IM2: vector MSBs 0, ULA interrupt only; pending status cleared with interrupts off
hw_mode:
        di
        nextreg $C4,0
        nextreg $C5,0
        nextreg $C6,0
        nextreg $C0,%00000001
        call ack_all
        nextreg $C4,%00000001   ; ULA interrupt enable
        ret
pulse_mode:
        di
        nextreg $C0,0
        nextreg $C4,1
        call ack_all
        ret
ack_all:
        nextreg $C8,$FF         ; write 1 = clear (LEARNINGS 1.4)
        nextreg $C9,$FF
        nextreg $CA,$FF
        ret

; ---------------------------------------------------------------- handlers
h_right:  push af : ld a,1 : ld (RIGHT),a : pop af : ei : reti
h_wrong:  push af : ld a,(WRONG) : inc a : ld (WRONG),a : pop af : ei : reti
h_count:  push af : ld a,(CNT) : inc a : ld (CNT),a : pop af : ei : reti
h_noreti: push af : ld a,(CNT) : inc a : ld (CNT),a
          cp 200 : jr c,.ok     ; never acknowledged -> it fires again at once: stop at 200
          nextreg $C4,0         ; ULA interrupt off, so the test cannot hang
.ok:      pop af : ei : ret
; game-style handler (EI;RET), reached through the trampoline
h_game:   push af : ld a,(CNT) : inc a : ld (CNT),a : pop af : ei : ret
; trampoline: the interrupted PC is on the stack; put h_game on top and RETI into it
tramp:    push hl
          ld hl,h_game
          ex (sp),hl            ; stack: h_game, interrupted PC; HL restored
          reti                  ; acknowledge -> h_game (interrupts still off until its EI)
; uniform-table handler source, copied to $A1A1
uh_src:   push af : ld a,(CNT) : inc a : ld (CNT),a : pop af : ei : reti
uh_len    equ $-uh_src

; ---------------------------------------------------------------- raster helpers
; read the 9-bit line into HL until two reads agree (LEARNINGS 1.5: $1E/$1F are two reads)
line:   push bc
.again: call line1 : ld d,h : ld e,l
        call line1
        ld a,h : cp d : jr nz,.again
        ld a,l : cp e : jr nz,.again
        pop bc : ret
line1:  ld bc,$243B : ld a,$1E : out (c),a : inc b : in a,(c) : and 1 : ld h,a
        dec b : ld a,$1F : out (c),a : inc b : in a,(c) : ld l,a
        ret
; wait for line 100 (H = 0, L = 100) after first leaving it
frame_start:
wait_line_100_again:
.off:   call line : ld a,h : or a : jr nz,.on : ld a,l : cp 100 : jr z,.off
.on:    call line : ld a,h : or a : jr nz,.on : ld a,l : cp 100 : jr nz,.on
        ret
; B frames (interrupts as they are)
frames:
frames_ei:
.l:     push bc : call wait_line_100_again : pop bc : djnz .l
        ret

; ---------------------------------------------------------------- results + screen
; A = status, B = test number (1-based), C = detail
result: push af
        ld a,b : dec a : add a,a : ld e,a : ld d,0
        ld hl,RESULTS+6 : add hl,de
        pop af
        ld (hl),a : inc hl : ld (hl),c
        ret

; A in hex at DE (two characters, ROM font at $3D00)
hex2:   push af : rrca : rrca : rrca : rrca : call hex1 : pop af
hex1:   and 15 : add a,'0' : cp '9'+1 : jr c,.d : add a,7
.d:     push de
        sub 32 : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld bc,$3D00 : add hl,bc
        ld b,8
.l:     ld a,(hl) : ld (de),a : inc hl : inc d : djnz .l
        pop de : inc de
        ret

cls:    ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),0 : ldir
        xor a : out ($FE),a
        ret

build_tables:
        ld hl,VTAB : ld b,128
.v:     ld de,h_wrong : ld (hl),e : inc hl : ld (hl),d : inc hl : djnz .v
        ld (hl),h_wrong & $FF   ; byte 257
        ld hl,UTAB : ld de,UTAB+1 : ld bc,256 : ld (hl),UHANDLER & $FF : ldir
        ret

; per test: status -> paper colour, 2x2 cells at row 2, column 2 + 3*(n-1)
show:   ld ix,RESULTS+6
        ld b,NTESTS
        ld c,0                  ; fails
        ld hl,$5800+2*32+2
.t:     ld a,(ix+0)
        cp 1 : ld e,4*8+64 : jr z,.c    ; green, bright
        cp 2 : ld e,2*8+64 : jr z,.f    ; red
        cp 3 : ld e,7*8+64 : jr z,.c    ; white
        ld e,0 : jr .c
.f:     inc c
.c:     ld (hl),e : inc hl : ld (hl),e : dec hl
        push hl : ld de,32 : add hl,de : pop de : ex de,hl
        ld a,(hl) : ld (de),a : inc de : ld (de),a ; row 3 = row 2
        inc hl : inc hl : inc hl
        push bc : push hl
        ld a,(ix+1)             ; detail byte in hex at character row 5, under the block
        ld de,32*3-3 : add hl,de ; HL had moved 3 columns on: back to this block, row 2 -> row 5
        ld (hl),$47 : inc hl : ld (hl),$47 : dec hl
        ld de,$5800 : or a : sbc hl,de ; HL = 5*32 + column
        ld de,$4000 : add hl,de : ex de,hl ; DE = pixel address of row 5, line 0
        ld a,(ix+1) : call hex2
        pop hl : pop bc
        inc ix : inc ix
        djnz .t
        ld a,c : or a : ld a,4 : jr z,.b
        ld a,2
.b:     out ($FE),a
        ret

        SAVENEX OPEN "im2hold.nex", start, $7DE0
        SAVENEX CORE 3,1,0
        SAVENEX CFG 0,0,0,0
        SAVENEX AUTO
        SAVENEX CLOSE
