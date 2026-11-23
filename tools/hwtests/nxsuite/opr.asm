; nxsuite/opr.asm - the person at the machine: menu keys of the operator / opt-in groups, the opt-in
; hazard screen, questions (Y / N, 1 / 2 / 3, S = later) and typed numbers. Bank 2 (bank 0 is full).
; GPL-3.0-or-later.

; ---------------------------------------------------------------- menu
; A = a menu key other than A / R / U: 0-9 = that group; else the group from 10 on whose key it is
; (V visual, T / D / H opt-in), if it has a built (or left-out) test
menu_key:
        cp '0' : jr c,.o
        cp '9'+1 : jr nc,.o
        sub '0' : jp do_group
.o:     ld c,a : ld b,10
.l:     ld a,b : cp NGROUPS : jp nc,menu_again
        push bc : call gent : pop bc
        ld a,(ix+3) : cp c : jr z,.g
        inc b : jr .l
.g:     ld a,(ix+2) : or a : jp z,menu_again
        ld a,b : jp do_group

; ---------------------------------------------------------------- opt-in
; The screen before an opt-in test ((cure) = its ttab entry): what it changes, what to do if the machine
; does not come back; Y runs it, N skips it (-> carry, HL kept). Never reached in RUN ALL.
hazard: push hl
        call cls
        xor a : ld (crow),a : ld (ccol),a
        ld hl,m_hz0 : call puts
        ld ix,(cure) : ld a,1 : ld (wsink),a : call wtid : xor a : ld (wsink),a
        ld a,' ' : call putc
        ld ix,(cure) : ld l,(ix+10) : ld h,(ix+11) : ld de,WORK : call far_copy
        ld hl,WORK : call puts
        ld ix,(cure) : ld a,(ix+4)
        ld hl,m_hzt : cp 11 : jr z,.t
        ld hl,m_hzd : cp 12 : jr z,.t
        ld hl,m_hzh
.t:     ld a,2 : call plines
        ld hl,m_hzc : ld a,(crow) : inc a : call plines
        ld a,22 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_hzk : call puts
        call keys_up
.w:     call getkey : cp 'Y' : jr z,.y
        cp 'N' : jr nz,.w
        call keys_up : call gscreen : pop hl : scf : ret
.y:     call keys_up : call gscreen : pop hl : or a : ret
m_hz0:  db "OPT-IN ",0
m_hzt:  db "It changes the machine timing",0
        db "(NextReg $03) and puts it back.",0
        db "The picture may roll or go blank",0
        db "for a moment.",0,0
m_hzd:  db "It maps DivMMC memory (alt ROM,",0
        db "NextReg $BB). If it locks up:",0
        db "power off/on, start again.",0,0
m_hzh:  db "It starts a DMA that may keep",0
        db "the bus (the machine can freeze)",0
        db "or leave the DMA deaf until a",0
        db "reset (XH2: the screen after it",0
        db "says what to do).",0,0
m_hzc:  db "Nothing is saved to the machine.",0
        db "If the picture or the border does",0
        db "not come back within 10 seconds:",0
        db "reset (or power off and on),",0
        db "start nxsuite.nex again from the",0
        db "same folder: it resumes by itself",0
        db "and marks this test HANG-GUARD.",0,0
m_hzk:  db "Y = run it    N = skip it",0

; ---------------------------------------------------------------- questions
; A = first row, HL = lines (each 0-ended, an empty one ends them) -> printed from column 0; HL after them
plines: ld (crow),a
.l:     ld a,(hl) : or a : jr z,.e
        xor a : ld (ccol),a : call puts : inc hl
        ld a,(crow) : inc a : ld (crow),a : jr .l
.e:     inc hl : ret

; HL = question: db kind (0 = Y / N, k = 1-3: keys 1 to k + 2), the lines (plines), then the answers' words
; (2 for Y / N, else k + 2; 0-ended). -> NC, A = the answer's index: R_st OPERATOR, v = the answer's word, extras key= / means=; or carry:
; S pressed - R_st PENDING-OPERATOR (the question stays open). The group screen is drawn again after.
ask:    ld a,(hl) : ld (askk),a : inc hl
        push hl : call cls : pop hl
        ld a,1 : call plines : ld (askw),hl
        ld a,22 : ld (crow),a : xor a : ld (ccol),a
        call askprm                                 ; the prompt line (nxsuite.asm, bank 2)
        call keys_up
.w:     call getkey : or a : jr z,.w
        cp 'S' : jr z,.s
        ld (askc),a : ld c,a
        ld a,(askk) : or a : jr nz,.n
        ld a,c : ld b,0 : cp 'Y' : jr z,.ok
        inc b : cp 'N' : jr z,.ok
        jr .w
.n:     ld a,c : sub '1' : jr c,.w
        ld b,a : ld a,(askk) : inc a : cp b : jr c,.w  ; keys 1 to askk + 2
.ok:    ld a,b : ld (aski),a
        ld hl,(askw) : or a : jr z,.f
.sk:    ld a,(hl) : inc hl : or a : jr nz,.sk
        djnz .sk
.f:     ld (askp),hl
        call res_word
        ld a,ST_OPER : ld (R_st),a
        ld hl,k_key : call ex_k : ld a,(askc) : call wchr
        ld hl,k_means : call ex_k : ld hl,(askp) : call wstr
        call keys_up : call gscreen
        ld a,(aski) : or a : ret
.s:     ld a,ST_PENDOP : ld (R_st),a
        call keys_up : call gscreen : scf : ret
askk:   db 0
askc:   db 0
aski:   db 0
askw:   dw 0
askp:   dw 0
m_yn:   db "Y = yes  N = no  S = ask later",0
m_123:  db "1, 2 or 3      S = ask later",0
k_key:  db "key",0
k_means: db "means",0

; -> HL = a number typed at crow / ccol (digits, at most 4; C clears; ENTER ends)
readnum:
        ld a,(ccol) : ld (.c0),a
.st:    ld hl,0 : ld (.v),hl : xor a : ld (.d),a
.w:     call keys_up
.k:     call getkey : or a : jr z,.k
        cp 13 : jr z,.en
        cp 'C' : jr z,.cl
        cp '0' : jr c,.w
        cp '9'+1 : jr nc,.w
        ld c,a : ld a,(.d) : cp 4 : jr nc,.w
        inc a : ld (.d),a
        ld a,c : call putc
        ld a,c : sub '0' : ld e,a : ld d,0
        ld hl,(.v) : add hl,hl : push hl : add hl,hl : add hl,hl : pop bc : add hl,bc : add hl,de : ld (.v),hl
        jr .w
.cl:    ld a,(.c0) : ld (ccol),a : ld b,4
.c2:    ld a,' ' : call putc : djnz .c2
        ld a,(.c0) : ld (ccol),a : jr .st
.en:    ld a,(.d) : or a : jr z,.w
        call keys_up
        ld hl,(.v) : ret
.c0:    db 0
.d:     db 0
.v:     dw 0

; ---------------------------------------------------------------- NEXT STEP (moved from bank 0: full)
; the NEXT STEP lines -> (ns1), (ns2)
next_step:
        ld a,(resume_pending) : or a : jr z,.n1
        ld hl,ns_res1 : ld (ns1),hl : ld hl,ns_res2 : ld (ns2),hl : ret
.n1:    ld b,0                              ; any automatic group with built tests not run?
.l:     ld a,b : cp 10 : jr nc,.n2
        push bc : call gent : pop bc
        ld a,(ix+2) : or a : jr z,.nx
        ld hl,PRGB+PRG_GST : ld a,l : add a,b : ld l,a
        ld a,(hl) : or a : jr z,.auto
        cp GS_RUN : jr z,.auto
.nx:    inc b : jr .l
.auto:  ld hl,ns_all1 : ld (ns1),hl : ld hl,ns_all2 : ld (ns2),hl : ret
.n2:    ld hl,PRGB+PRG_HUNG : ld b,6                 ; a hung test listed: U
.h:     ld a,(hl) : inc hl : and (hl) : inc hl : inc a : jr nz,.hu
        djnz .h
        ld a,(PRGB+PRG_GST+10) : cp GS_DONE : jr z,.v  ; the visual pass answered
        cp GS_FAILS : jr z,.v
        ld hl,ns_v1 : ld de,ns_v2 : jr .set
.v:     ld b,11                                     ; opt-in groups not run: optional
.o:     ld hl,PRGB+PRG_GST : ld a,l : add a,b : ld l,a
        ld a,(hl) : or a : jr z,.opt
        inc b : ld a,b : cp 14 : jr c,.o
        ld hl,ns_done1 : ld de,ns_done2 : jr .set
.opt:   ld hl,ns_opt1 : ld de,ns_opt2 : jr .set
.hu:    ld hl,ns_hu1 : ld de,ns_hu2
.set:   ld (ns1),hl : ld (ns2),de : ret
ns1:    dw 0
ns2:    dw 0
ns_res1: db "Last run stopped. R or wait 5 s:",0
ns_res2: db "resume, the test is marked hung",0
ns_all1: db "Press A: all automatic tests,",0
ns_all2: db "about 5 min. Leave it alone.",0
ns_done1: db "NOTHING OUTSTANDING. Copy",0
ns_done2: db "NXSUITE.TXT to the PC.",0
ns_v1:  db "Press V: the visual pass (you",0
ns_v2:  db "answer what you see), ~5 min.",0
ns_hu1: db "A test hung: U retries it, or",0
ns_hu2: db "copy NXSUITE.TXT to the PC.",0
ns_opt1: db "NOTHING OUTSTANDING (T D H are",0
ns_opt2: db "optional). Copy NXSUITE.TXT.",0
