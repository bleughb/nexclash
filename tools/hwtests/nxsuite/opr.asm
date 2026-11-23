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
m_hzd:  db "It maps the DivMMC memory and",0
        db "its traps (port $E3, NextReg",0
        db "$BB). A wrong step can lock up",0
        db "the machine.",0,0
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

; HL = question: db kind (0 = Y / N, 1 = 1 / 2 / 3), the lines (plines), then the answers' words (2 or 3,
; 0-ended). -> NC, A = 0 / 1 / 2: R_st OPERATOR, v = the answer's word, extras key= / means=; or carry:
; S pressed - R_st PENDING-OPERATOR (the question stays open). The group screen is drawn again after.
ask:    ld a,(hl) : ld (askk),a : inc hl
        push hl : call cls : pop hl
        ld a,1 : call plines : ld (askw),hl
        ld a,22 : ld (crow),a : xor a : ld (ccol),a
        ld hl,m_yn : ld a,(askk) : or a : jr z,.p
        ld hl,m_123
.p:     call puts
        call keys_up
.w:     call getkey : or a : jr z,.w
        cp 'S' : jr z,.s
        ld (askc),a : ld c,a
        ld a,(askk) : or a : jr nz,.n
        ld a,c : ld b,0 : cp 'Y' : jr z,.ok
        inc b : cp 'N' : jr z,.ok
        jr .w
.n:     ld a,c : sub '1' : jr c,.w
        cp 3 : jr nc,.w
        ld b,a
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
