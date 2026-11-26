; nxsuite/gq.asm - in the string page (62) after the strings, assembled for slot 7: the operator's
; questionnaire at the first start, its H line in the file, and the paged summary when the results could not
; be saved. GPL-3.0-or-later. Reached through ovcall (nxsuite.asm), which maps page 62 into slot 7 and puts
; the caller's page back. qmodels (the machine list) is in the same page at its slot-6 address: far_copy.

; ---------------------------------------------------------------- questionnaire (once per NXSUITE.PRG)
; Machine (a two-key code from qmodels: nxsuite_claims.json "platforms"), display connection, display kind,
; RAM believed fitted, accelerator / Pi, a machine label. One key each; S skips; 20 s with no key skips the
; rest (an unattended start goes on by itself). The answers go to the progress record (PRG_Q, PRG_FLAGS
; bit 2 = asked) and from there into every session's "H operator" line. Nothing is measured here.
q_ask:  ld a,(PRGB+PRG_FLAGS) : bit 2,a : ret nz
        ld hl,PRGB+PRG_Q : ld b,12
.z:     ld (hl),0 : inc hl : djnz .z
.m:     call cls
        ld hl,q_m0 : xor a : call q_txt
        ld hl,qmodels : ld a,3 : ld (crow),a
.l:     ld de,WORK : call far_copy : inc hl
        ld a,(WORK) : or a : jr z,.le
        push hl : xor a : ld (ccol),a : ld hl,WORK : call puts : pop hl
        ld a,(crow) : inc a : ld (crow),a : jr .l
.le:    ld hl,q_m1 : ld a,21 : call q_txt
        call q_key : jp c,.done : cp 'S' : jp z,.done : ld (.k),a
        call q_key : jp c,.done : ld (.k+1),a
        ld hl,qmodels
.f:     ld de,WORK : call far_copy : inc hl
        ld a,(WORK) : or a : jr z,.m                ; not in the list: asked again
        ld de,(.k) : ld a,(WORK) : cp e : jr nz,.f
        ld a,(WORK+1) : cp d : jr nz,.f
        ld (PRGB+PRG_Q),de
        ld hl,q_c : call q_one : ld (.k),a
        ld hl,q_d : call q_one : call .hi : ld (PRGB+PRG_Q+2),a
        ld hl,q_r : call q_one : ld (.k),a
        ld hl,q_p : call q_one : call .hi : ld (PRGB+PRG_Q+3),a
        ld hl,q_l : call q_one0
        xor a : ld (.k),a                           ; label length (q_key uses BC / DE / HL)
.t:     call q_key : jr c,.done : cp 13 : jr z,.done
        cp '0' : jr c,.t                            ; letters and digits only
        ld c,a : ld a,(.k) : cp 8 : jr nc,.t
        ld e,a : ld d,0 : ld hl,PRGB+PRG_Q+4 : add hl,de : ld (hl),c
        inc a : ld (.k),a
        add a,10 : ld (ccol),a : ld a,7 : ld (crow),a : ld a,c : call putc
        jr .t
.done:  ld hl,PRGB+PRG_FLAGS : set 2,(hl)
        jp prg_write
.hi:    rlca : rlca : rlca : rlca : ld hl,.k : or (hl) : ret
.k:     dw 0

; HL = question (lines, then 0) -> A = 1-4 (the key), 0 = S / no key in 20 s
q_one:  call q_one0
.k:     call q_key : jr c,.z
        cp 'S' : jr z,.z
        sub '1' : cp 4 : jr nc,.k
        inc a : ret
.z:     xor a : ret
q_one0: push hl : call cls : pop hl : xor a
; V19's monitor-rate screen text (gv.asm calls it through ovcall: page 41 has no room for it)
q_v19m: ld hl,q_mon : ld a,1 : jp q_txt
q_mon:  db "V19 RATE THE DISPLAY SHOWS",0
        db "If its info / OSD menu shows the",0
        db "refresh rate, type it (49.36,",0
        db "50.0 ...), ENTER. Point = M.",0
        db "C clears. S = it shows none.",0,0
; HL = lines (each 0-ended, a 0 after the last), A = first row -> printed from column 0
q_txt:  ld (crow),a
.l:     ld a,(hl) : or a : ret z
        xor a : ld (ccol),a : call puts : inc hl
        ld a,(crow) : inc a : ld (crow),a : jr .l
; -> A = a key (after every key is up), carry = none in 20 s (1000 frames). The keyboard is polled all the
; time (a short press is not missed); a frame is counted when the raster line's bit 8 ($1E) falls.
q_key:  call keys_up
        ld de,1000
.w:     push de : call getkey : pop de : or a : ret nz
        ld bc,$243B : ld a,$1E : out (c),a : inc b : in a,(c) : and 1
        ld hl,.lm : cp (hl) : ld (hl),a : jr nc,.w
        dec de : ld a,d : or e : jr nz,.w
        scf : ret
.lm:    db 0

q_m0:   db "ABOUT THIS MACHINE (optional)",0
        db "Type its 2-key code, e.g. K1.",0
        db "S = skip all questions.",0,0
q_m1:   db "No key for 20 s: skipped.",0
        db "ZXnano/MSXnano/A800nano: not a",0
        db "Next core; the suite needs one.",0,0
q_c:    db "DISPLAY CONNECTION",0," ",0,"1 HDMI",0,"2 VGA",0,"3 RGB / SCART",0,"4 don't know",0," ",0
        db "S = skip",0,0
q_d:    db "DISPLAY KIND",0," ",0,"1 monitor",0,"2 TV",0,"3 capture device",0,"4 don't know",0," ",0
        db "S = skip",0,0
q_r:    db "RAM YOU BELIEVE IS FITTED",0," ",0,"1 1 MB",0,"2 2 MB",0,"3 other",0,"4 don't know",0," ",0
        db "S = skip",0,0
q_p:    db "ACCELERATOR / Pi FITTED?",0," ",0,"1 yes",0,"2 no",0,"3 don't know",0," ",0,"S = skip",0,0
q_l:    db "MACHINE LABEL (optional)",0," ",0
        db "A NICKNAME FOR THE MACHINE, NOT",0
        db "A PERSON'S NAME. Up to 8 letters",0
        db "or digits, ENTER to finish.",0," ",0," ",0
        db "    label:",0,0

; "H operator model=K1 conn=1 disp=2 ramq=1 pi=2 label=BENCH1" (- = not given) after the session's H divmmc line
q_wline:
        call w_lb : ld hl,q_h0 : call wstr
        ld hl,(PRGB+PRG_Q) : ld a,l : or a : jr z,.m0
        call wchr : ld a,h : call wchr : jr .m1
.m0:    call .dash
.m1:    ld hl,q_h1 : call wstr : ld a,(PRGB+PRG_Q+2) : call .nb
        ld hl,q_h2 : call wstr : ld a,(PRGB+PRG_Q+2) : call .hn
        ld hl,q_h3 : call wstr : ld a,(PRGB+PRG_Q+3) : call .nb
        ld hl,q_h4 : call wstr : ld a,(PRGB+PRG_Q+3) : call .hn
        ld hl,q_h5 : call wstr
        ld hl,PRGB+PRG_Q+4 : ld a,(hl) : or a : jr nz,.lb
        call .dash : jr .e
.lb:    ld b,8
.lc:    ld a,(hl) : or a : jr z,.e
        call wchr : inc hl : djnz .lc
.e:     ld a,10 : call wchr : call w_len : jp txt_append
.hn:    rrca : rrca : rrca : rrca
.nb:    and 15 : jr z,.dash
        add a,'0' : jp wchr
.dash:  ld a,'-' : jp wchr
q_h0:   db "H operator model=",0
q_h1:   db " conn=",0
q_h2:   db " disp=",0
q_h3:   db " ramq=",0
q_h4:   db " pi=",0
q_h5:   db " label=",0

; ---------------------------------------------------------------- results not saved: a paged summary
; At DONE when the last write of NXSUITE.TXT failed (flushfail): every test run this session (results table
; STAB: status, value x 100), 20 a page, for the operator to photograph. Any key: next page.
ps_show:
        ld a,(flushfail) : or a : ret z
        xor a : ld (.t),a
.pg:    call cls
        ld a,2 : out ($FE),a
        ld hl,ps_m0 : xor a : call q_txt
        ld a,3 : ld (crow),a
.e:     ld a,(.t) : cp NTESTS : jr nc,.end
        ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl : ld de,STAB+7 : add hl,de
        ld a,(hl) : or a : jr z,.nx
        push hl
        xor a : ld (ccol),a : inc a : ld (wsink),a
        ld a,(.t) : call tent : call wtid
        ld a,5 : ld (ccol),a                       ; column 6: the status
        pop hl : push hl : ld a,(hl) : add a,a : ld e,a : ld d,0 : ld hl,stnames : add hl,de
        ld a,(hl) : inc hl : ld h,(hl) : ld l,a : call wstr
        ld a,(ccol) : inc a : ld (ccol),a
        pop hl : inc hl : inc hl
        ld c,(hl) : inc hl : ld b,(hl) : inc hl : ld e,(hl) : inc hl : ld d,(hl)
        ld h,b : ld l,c : ld a,h : or l : or d : or e : call nz,wfix
        xor a : ld (wsink),a
        ld a,(crow) : inc a : ld (crow),a : cp 23 : jr c,.nx
        ld hl,.t : inc (hl) : call .key : jp .pg
.nx:    ld hl,.t : inc (hl) : jr .e
.end:   ld a,23 : ld (crow),a : xor a : ld (ccol),a : ld hl,ps_m1 : call puts
.key:   call keys_up
.k:     call getkey : or a : jr z,.k
        ret
.t:     db 0
ps_m0:  db "RESULTS COULD NOT BE SAVED -",0
        db "photograph these pages. Any key:",0
        db "the next page.",0,0
ps_m1:  db "END of the list. Any key.",0
        ASSERT NTESTS < 256
