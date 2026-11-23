; nxsuite/gv.asm - V VISUAL: the operator pass (spec section 3 V, step 4). GPL-3.0-or-later.
; Slot-7 overlay, shares page 41 with G3 (G3's tables at $F800-$FFFF stay untouched). Only by the menu key
; V: in RUN ALL every V test is PENDING-OPERATOR. Each test shows a picture or runs a stopwatch, then asks
; (ask, opr.asm): Y / N or 1 / 2 / 3 -> OPERATOR with key= / means=, S -> PENDING-OPERATOR (asked again on
; the next V pass). The tests built are those a key press can answer without a photograph; the others are
; left out with their reason in nxsuite_claims.json. NextRegs and ports put back by the harness
; (restore_all: $12 $15 $52 $69 $123B ...); sprites used here hidden again.

; A = row: "press any key when you have looked" there, then waits for a key
gv_look:
        ld (crow),a : xor a : ld (ccol),a
        ld hl,m_look : call puts
gv_key: call keys_up
.w:     call getkey : or a : jr z,.w
        jp keys_up
m_look: db "Look, then press any key.",0

; ---------------------------------------------------------------- V19 frame rate (stopwatch) and cable
; First: which cable carries the picture (1 HDMI, 2 VGA, 3 other / RGB) -> cable=. Then a stopwatch: SPACE
; starts the count and the watch together, SPACE stops both after 60 s or more; frames counted from the
; raster line (frame_sync); the seconds typed in. v = frames / seconds (Hz); keys frames, secs, r05
; (NextReg $05: bit 2 = 60 Hz), r11 (VGA timing). Operator-timed: +-0.2 s of reaction is +-0.3 % at 60 s.
@t_v19: ld hl,q_cable : call ask : ret c
        ld hl,(askp) : push hl
        ld hl,EXB : ld (wp),hl                      ; the cable answer as cable= only
        ld hl,k_cable : call ex_k : pop hl : call wstr
        call cls
        ld hl,m_sw : ld a,1 : call plines
        ld a,20 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_sw2 : call puts
        call keys_up
.w:     call getkey : cp 'S' : jp z,.pend
        cp ' ' : jr nz,.w
        ld a,4 : out ($FE),a
        ld hl,0 : ld (.n),hl
        call keys_up
.f:     call frame_sync
        ld hl,(.n) : inc hl : ld (.n),hl
        ld a,l : and 15 : jr nz,.k
        ld a,12 : ld (crow),a : xor a : ld (ccol),a : ld hl,(.n) : call sdec
.k:     ld a,$7F : in a,($FE) : rra : jr c,.f        ; SPACE (row $7F bit 0)
        ld a,1 : out ($FE),a
        ld a,12 : ld (crow),a : xor a : ld (ccol),a : ld hl,(.n) : call sdec
        ld a,14 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_secs : call puts
        call readnum : ld (.s),hl
        ld a,h : or l : jp z,.pend
        ld bc,(.n) : ld de,100 : call mul16
        ld bc,(.s) : call div32
        call res_num : ld hl,u_hz : call res_unit
        ld a,ST_OPER : ld (R_st),a
        ld de,(.n) : ld hl,k_frames : call ex_kd
        ld de,(.s) : ld hl,k_secs : call ex_kd
        ld a,$05 : call rdreg : ld hl,k_r05 : call ex_kh
        ld a,$11 : call rdreg : ld hl,k_r11 : call ex_kh
        jp gscreen
.pend:  ld a,ST_PENDOP : ld (R_st),a : call keys_up : jp gscreen
.n:     dw 0
.s:     dw 0
q_cable: db 1
        db "V19 FRAME RATE - first:",0
        db " ",0
        db "Which cable carries the picture",0
        db "to the screen now?",0
        db "1 = HDMI",0
        db "2 = VGA",0
        db "3 = other (RGB, SCART ...)",0,0
        db "hdmi",0,"vga",0,"other",0
k_cable: db "cable",0
k_frames: db "frames",0
k_secs: db "secs",0
k_r05:  db "r05",0
k_r11:  db "r11",0
u_hz:   db "Hz",0
m_sw:   db "STOPWATCH: have a watch that",0
        db "shows seconds.",0
        db "Press SPACE and start the watch",0
        db "at the same moment. The border",0
        db "turns green and frames count.",0
        db "After 60 s or more press SPACE",0
        db "and stop the watch together.",0
        db "Then type the seconds (whole),",0
        db "ENTER. (C clears.)",0,0
m_sw2:  db "SPACE = start    S = ask later",0
m_secs: db "Seconds on the watch: ",0

; ---------------------------------------------------------------- V15 the ULA reads bank 5
; A checkerboard and these words in bank 5 (slot 2 = page 10). Then page 36 is mapped into slot 2 and its
; screen area filled white (paper 7, ink 7) while the operator looks; slot 2 back (restore_all also).
; Y = the checkerboard stayed (the ULA reads bank 5: the claim), N = the screen went white.
@t_v15: call cls
        ld hl,$4800                                 ; checkerboard of 4 x 4 dots: rows 8-23
.c:     ld a,h : and 4 : ld a,$F0 : jr z,.c1
        ld a,$0F
.c1:    ld (hl),a : inc hl : ld a,h : cp $58 : jr nz,.c
        ld hl,m_v15 : ld a,1 : call plines
        nextreg $52,36
        ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),$3F : ldir
        call gv_key
        nextreg $52,$0A
        ld hl,q_v15 : jp ask
m_v15:  db "V15: the program now fills the",0
        db "screen white through ANOTHER",0
        db "page mapped at $4000.",0
        db "Look, then press any key.",0,0
q_v15:  db 0
        db "V15 ULA READS BANK 5",0
        db " ",0
        db "While you looked, did the",0
        db "checkerboard and the words stay?",0
        db "Y = they stayed",0
        db "N = the screen went white",0,0
        db "stays",0,"white",0

; ---------------------------------------------------------------- V16 port $FF (Timex modes)
; A ULA picture (stripes and words); any key: OUT ($FF),2 (Timex high colour) for 150 frames, then
; OUT ($FF),0; $69 put back by the harness. 1 = the picture changed during the 3 s (the claim), 2 = it
; stayed the same, 3 = other (blank, did not come back).
@t_v16: call cls
        ld hl,$4000 : ld de,$4001 : ld bc,$07FF : ld (hl),$F0 : ldir     ; stripes: the top third
        ld hl,m_v16 : ld a,10 : call plines
        call gv_key
        ld a,2 : out ($FF),a
        ld b,150
.f:     push bc : call frame_sync : pop bc : djnz .f
        xor a : out ($FF),a
        ld hl,q_v16 : jp ask
m_v16:  db "V16: press a key and watch: for",0
        db "3 s the program writes port $FF",0
        db "= 2, then $FF = 0 again.",0,0
q_v16:  db 1
        db "V16 PORT $FF (TIMEX)",0
        db " ",0
        db "During the 3 seconds:",0
        db "1 = the picture changed",0
        db "2 = it stayed the same",0
        db "3 = something else (blank ...)",0,0
        db "changed",0,"same",0,"other",0

; ---------------------------------------------------------------- V10 Layer 2 flip is not synced
; Layer 2 256 x 192 on top ($15 order LSU). Pages 44-47 red ($E0), 48-53 blue ($03). $12 = 22 shows pages
; 44-49 (red rows 0-127, blue 128-191); $12 = 24 shows 48-53 (all blue). The CPU polls the raster: $12 =
; 24 at line 96, $12 = 22 at line 200, every frame until a key. Not synced (the claim): still, red top
; half, blue bottom half. Taken at the frame start: still, red two thirds, blue one third. 1 / 2 / 3 other.
@t_v10: call cls
        ld hl,m_v10 : ld a,1 : call plines
        call gv_key
        ld a,44
.p:     push af : nextreg $53,a                     ; slot 3 ($6000; the harness data there is not used)
        ld e,$E0 : cp 48 : jr c,.p1
        ld e,$03
.p1:    ld hl,$6000 : ld (hl),e : ld de,$6001 : ld bc,$1FFF : ldir
        pop af : inc a : cp 54 : jr nz,.p
        nextreg $53,$0B
        di
        ld a,(NRSNAP+$15) : and %11100011 : or %00000100 : nextreg $15,a   ; LSU
        nextreg $12,22
        ld bc,$123B : ld a,2 : out (c),a
.fr:    call line : ld a,h : or a : jr nz,.fr       ; wait for a line below 96
        ld a,l : cp 96 : jr nc,.fr
.a:     call line : ld a,l : cp 96 : jr c,.a
        nextreg $12,24
.b:     call line : ld a,h : or a : jr nz,.c
        ld a,l : cp 200 : jr c,.b
.c:     nextreg $12,22
        call getkey : or a : jr z,.fr
        ld bc,$123B : xor a : out (c),a
        call keys_up
        ld hl,q_v10 : jp ask
m_v10:  db "V10: Layer 2 picture next, red",0
        db "and blue. Watch it, then press",0
        db "any key. Press a key now.",0,0
q_v10:  db 1
        db "V10 LAYER 2 FLIP AT LINE 96",0
        db " ",0
        db "1 = still: red top HALF,",0
        db "    blue bottom half",0
        db "2 = still: red top TWO THIRDS,",0
        db "    blue bottom third",0
        db "3 = something else (flicker ...)",0,0
        db "split-96",0,"frame-start",0,"other",0

; ---------------------------------------------------------------- V02 sprite order ($15 bit 6)
; Sprite 1 red ($E0) at X 128 Y 112, sprite 2 green ($1C) at X 136 Y 120 (16 x 16, they overlap 8 x 8),
; patterns 0 / 1. Shown with $15 bit 6 = 0, then = 1; each time: which colour is on top. b0 / b1 = the
; answers (green = the higher number on top, red = sprite 0's end on top); means=<b0>-<b1>, the claim:
; green-red. v = the second answer. Sprites hidden again, patterns 0 / 1 left written (G8 writes its own).
@t_v02: di
        ld bc,$303B : xor a : out (c),a
        ld bc,$005B : ld a,$E0
.p0:    out (c),a : djnz .p0
        ld a,$1C
.p1:    out (c),a : djnz .p1
        nextreg $34,1 : nextreg $35,128 : nextreg $36,112 : nextreg $37,0 : nextreg $38,$80
        nextreg $34,2 : nextreg $35,136 : nextreg $36,120 : nextreg $37,0 : nextreg $38,$81
        ld a,(NRSNAP+$15) : and %00011100 : or 1 : ld (.r15),a
        nextreg $15,a
        ld hl,(wp) : ld (.wp),hl
        call .one : jr c,.x
        ld hl,(askp) : ld (.w0),hl
        ld hl,(.wp) : ld (wp),hl : ld hl,k_b0 : call ex_k : ld hl,(askp) : call wstr
        ld hl,(wp) : ld (.wp),hl
        ld a,(.r15) : or $40 : nextreg $15,a
        call .one : jr c,.x
        ld hl,(.wp) : ld (wp),hl : ld hl,k_b1 : call ex_k : ld hl,(askp) : call wstr
        ld hl,k_means : call ex_k : ld hl,(.w0) : call wstr     ; means=<b0>-<b1> (the claim: green-red)
        ld a,'-' : call wchr : ld hl,(askp) : call wstr
.x:     nextreg $34,1 : nextreg $38,0 : nextreg $34,2 : nextreg $38,0
        ret
.one:   call cls
        ld hl,m_v02 : ld a,1 : call plines
        ld a,20 : call gv_look
        ld hl,q_v02 : jp ask
.r15:   db 0
.wp:    dw 0
.w0:    dw 0
k_b0:   db "b0",0
k_b1:   db "b1",0
m_v02:  db "V02: two squares, red and green,",0
        db "overlap in the middle.",0,0
q_v02:  db 0
        db "V02 SPRITE ORDER",0
        db " ",0
        db "Where the squares overlapped:",0
        db "Y = GREEN was on top",0
        db "N = RED was on top",0,0
        db "green",0,"red",0
