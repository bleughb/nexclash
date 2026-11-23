; nxsuite/harness.asm - start-up, menu, run engine, result lines, screen (bank 0, $C000-). GPL-3.0-or-later.
; Code here must not run while slot 6 holds another page: every routine that maps one (txt_*, far_copy,
; the esxDOS calls) lives in bank 2 (core.asm) and puts page 0 back before it returns.

; ---------------------------------------------------------------- start
entry:  ld sp,MSTACK
        call s00_scan                       ; S00 first: the printer buffer as NEXLOAD left it
        ld e,0                              ; S01: every NextReg, before any write
.snap:  ld a,e : call rdreg
        ld l,e : ld h,NRSNAP>>8 : ld (hl),a
        inc e : jr nz,.snap
        ld a,i : ld (launch_i),a
        ld a,(NRSNAP+$07) : and 3 : ld (spd0),a
        ld bc,$1FFD : ld a,$04 : out (c),a  ; ROM 3, the 48K state the file calls are made from (spec 1.1)
        ld bc,$7FFD : ld a,$10 : out (c),a
        xor a : out ($FE),a
        call crc_init
        call cls
        ld hl,STAB                          ; results table "NXS1"
        ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'S' : inc hl : ld (hl),'1' : inc hl
        ld (hl),SUITE_VER : inc hl
        ld (hl),NTESTS & $FF : inc hl : ld (hl),NTESTS >> 8 : inc hl
        ld d,h : ld e,l : inc de : ld (hl),0 : ld bc,NTESTS*8 : ldir
        xor a : ld (DONEFLAG),a
        ld a,2 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_start : call puts
        call preamble
        ; progress record and the text file of earlier runs
        call prg_read : jr nc,.prgok
        call prg_new
.prgok: ld hl,(PRGB+4) : inc hl : ld (PRGB+4),hl : ld (runno),hl
        call txt_load : ld (fstate),a
        ld a,(PRGB+PRG_STATE) : cp 1 : jr nz,.menu
        ld a,1 : ld (resume_pending),a
.menu:  jp menu

m_start: db "nxsuite: measuring...",0

; a fresh progress record
prg_new:
        ld hl,PRGB : ld de,PRGB+1 : ld bc,63 : ld (hl),0 : ldir
        ld hl,PRGB : ld (hl),'N' : inc hl : ld (hl),'X' : inc hl : ld (hl),'P' : inc hl : ld (hl),'1'
        ld hl,PRGB+PRG_HUNG : ld b,12
.h:     ld (hl),$FF : inc hl : djnz .h
        ret

; ---------------------------------------------------------------- what every session measures first
; core version, CPU speed, calibration (2048 x LD A,(IX+0) at 3.5 MHz), lines per frame, CTC ticks per
; line, RAM size choice (test S03's method), ROM 3 CRCs (S04).
preamble:
        nextreg $07,0
        xor a : ld (mshift),a : ld (msline),a
        ld hl,zini : ld (mini),hl
        ld ix,$8000
        ld hl,cal_body : ld (mk_body),hl : ld a,3 : ld (mk_bodyl),a
        ld hl,256 : ld (mk_n),hl
        xor a : ld (mk_prol),a : ld (mk_epil),a
        call mkrow
        ld hl,TBUF : ld a,8 : call measure : push hl
        ld hl,TBUF2 : ld a,8 : call measure
        ex de,hl : pop hl : or a : sbc hl,de : ld (cal),hl
        nextreg $07,3
        call frame_lines : ld (flines),hl           ; G4 F01 method, 3 frames
        call ctc_line : ld (ctcpl),hl : ld (ctcpl+2),de   ; G4 F02 method: ticks per line x 100
        nextreg $07,0
        call s03_ram : ld (ramchoice),a
        call set_core303
        call s04_crc
        ld a,(spd0) : nextreg $07,a
        call restore_all
        ret
cal_body: ld a,(ix+0)
spd0:   db 0
flines: dw 0
ctcpl:  ds 4
ramchoice: db 0
runno:  dw 0
fstate: db 0                                ; 0 no file, 1 earlier results loaded, 2 file not right (new)
resume_pending: db 0
sess_done: db 0                             ; session header written
mode:   db 0                                ; 0 RUN ALL, 1 + g one group, $80 + mode = resumed
justhung: dw $FFFF                          ; the test the last run stopped in (HANG-GUARD now)

; ---------------------------------------------------------------- menu
menu:   ld sp,MSTACK
        call restore_all
        ld a,(spd0) : nextreg $07,a
        xor a : out ($FE),a
        call cls
        xor a : ld (crow),a : ld (ccol),a
        ld hl,m_title : call puts : call pcore
        ld a,1 : ld (crow),a : xor a : ld (ccol),a
        ld hl,m_run : call puts : ld hl,(runno) : call sdec
        ld hl,m_file0 : ld a,(fstate) : or a : jr z,.f
        ld hl,m_file1 : cp 1 : jr z,.f
        ld hl,m_file2
.f:     call puts
        ; groups
        ld b,0
.g:     ld a,b : cp NGROUPS : jr nc,.gd
        push bc
        add a,3 : ld (crow),a : xor a : ld (ccol),a
        ld a,b : call gent                  ; IX = group entry
        ld a,(ix+3) : call putc : ld a,' ' : call putc
        ld l,(ix+5) : ld h,(ix+6) : ld de,WORK : call far_copy
        ld hl,WORK : call puts
        ld a,12 : ld (ccol),a
        pop bc : push bc
        call gstate_text : call puts
        pop bc : inc b : jr .g
.gd:    ; the next step
        call next_step
        ld a,18 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_next : call puts
        ld a,19 : ld (crow),a : xor a : ld (ccol),a : ld hl,(ns1) : call puts
        ld a,20 : ld (crow),a : xor a : ld (ccol),a : ld hl,(ns2) : call puts
        ld a,22 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_keys : call puts
        ld a,23 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_keys2 : call puts
        call keys_up
        ; resume after 5 s unless a key
        ld a,(resume_pending) : or a : jr z,.wait
        ld b,250
.rw:    push bc : call getkey : pop bc : or a : jr nz,.key
        push bc : call frame_sync : pop bc
        djnz .rw
        jp do_resume
.wait:  call getkey : or a : jr z,.wait
.key:   cp 'A' : jp z,do_all
        cp 'R' : jr nz,.k1
        ld a,(resume_pending) : or a : jp nz,do_resume
        jr menu_again
.k1:    cp 'U' : jp z,do_hung
        cp '0' : jr c,menu_again
        cp '9'+1 : jr nc,menu_again
        sub '0' : jp do_group
menu_again:
        xor a : ld (resume_pending),a
        jp menu

m_title: db "NXSUITE 1.0  core ",0
m_run:  db "run ",0
m_file0: db "  file: new",0
m_file1: db "  file: earlier results kept",0
m_file2: db "  file: unreadable, new",0
m_next: db "NEXT STEP:",0
m_keys: db "A all  0-9 group  R resume",0
m_keys2: db "U retry hung tests",0

; A = group -> IX = its gtab entry (8 bytes)
gent:   ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,gtab : add hl,de : push hl : pop ix
        ret

; B = group -> HL = its state text
gstate_text:
        ld a,b : call gent
        ld a,(ix+2) : or a : ld hl,g_nb : ret z
        ld a,b : ld hl,PRGB+PRG_GST : add a,l : ld l,a : jr nc,.n
        inc h
.n:     ld a,(hl) : add a,a : ld l,a : ld h,0 : ld de,gst_txt : add hl,de
        ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        ret
g_nb:   db "not built yet",0
gst_txt: dw g_s0,g_s1,g_s2,g_s3,g_s4,g_s5
g_s0:   db "not run",0
g_s1:   db "done",0
g_s2:   db "done, FAIL in it",0
g_s3:   db "questions open",0
g_s4:   db "hung (see file)",0
g_s5:   db "stopped",0

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
.n2:    ld hl,ns_done1 : ld (ns1),hl : ld hl,ns_done2 : ld (ns2),hl : ret
ns1:    dw 0
ns2:    dw 0
ns_res1: db "Last run stopped. R or wait 5 s:",0
ns_res2: db "resume, the test is marked hung",0
ns_all1: db "Press A: all automatic tests,",0
ns_all2: db "about 5 min. Leave it alone.",0
ns_done1: db "ALL DONE (this version). Copy",0
ns_done2: db "NXSUITE.TXT to the PC.",0

; ---------------------------------------------------------------- running
do_all: xor a : ld (mode),a
        ld b,0
        jp run_from
do_resume:
        xor a : ld (resume_pending),a
        ld hl,(PRGB+PRG_TIDX) : ld (justhung),hl
        ld a,h : and l : inc a : jr z,.nt          ; $FFFF: stopped between tests
        call hung_add
        ld a,(PRGB+PRG_GROUP) : ld b,a
        push bc
        ld hl,PRGB+PRG_GST : ld a,l : add a,b : ld l,a : ld (hl),GS_HUNG
        pop bc
        ld a,(PRGB+PRG_MODE) : or $80 : ld (mode),a
        and $7F : jp z,run_from                     ; RUN ALL: on from the group it stopped in
        dec a : ld b,a
        call run_group
        jp run_end
.nt:    ; stopped between tests (no risky test was running): the group is marked, the run goes on after it
        ld a,(PRGB+PRG_GROUP) : ld b,a : ld (curg),a
        ld hl,PRGB+PRG_GST : ld a,l : add a,b : ld l,a : ld (hl),GS_HUNG
        ld a,(PRGB+PRG_MODE) : or $80 : ld (mode),a
        call sess_header
        call w_lb : ld hl,s_stopg : call wstr : call wgid : ld hl,s_stopg2 : call wstr
        call w_len : call txt_append
        ld a,(mode) : and $7F : jp nz,run_end
        ld a,(curg) : inc a : ld b,a : jp run_from
do_group:
        ld b,a : inc a : ld (mode),a
        call run_group
        jp run_end
do_hung:                                            ; the hung tests one by one, each PRG-marked
        ld a,$7F : ld (mode),a
        call sess_header
        ld hl,PRGB+PRG_HUNG : ld b,6
.l:     push bc : push hl
        ld e,(hl) : inc hl : ld d,(hl)
        ld a,d : and e : inc a : jr z,.n
        ld a,e : ld (retry),a : ld a,1 : ld (retrying),a
        ld a,e : call run_test_marked
        xor a : ld (retrying),a
.n:     pop hl : pop bc : inc hl : inc hl : djnz .l
        jp run_end
retry:  db 0
s_stopg: db "# the last run stopped between tests in group ",0
s_stopg2: db " (no marked test was running); the run goes on after that group",10,0
retrying: db 0

; B = first group of a RUN ALL
run_from:
.g:     ld a,b : cp NGROUPS : jr nc,run_end
        push bc : call run_group : pop bc
        inc b : jr .g
run_end:
        ld a,2 : ld (PRGB+PRG_STATE),a
        ld hl,$FFFF : ld (PRGB+PRG_TIDX),hl
        call prg_write
        call txt_flush : ld (flushfail),a
        ld a,$A5 : ld (DONEFLAG),a
        call cls
        xor a : ld (crow),a : ld (ccol),a
        ld hl,m_done : call puts
        ld a,1 : ld (crow),a : xor a : ld (ccol),a
        ld hl,m_done2 : call puts
        ld a,(flushfail) : or a : jr z,.k
        ld a,3 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_wfail : call puts
.k:     ld a,5 : ld (crow),a : xor a : ld (ccol),a : ld hl,m_any : call puts
        call keys_up
.w:     call getkey : or a : jr z,.w
        jp menu
flushfail: db 0
m_done: db "DONE - you may reset.",0
m_done2: db "Results: NXSUITE.TXT",0
m_wfail: db "FILE WRITE FAILED - photograph",0
m_any:  db "Any key: menu",0

; B = group: G line, its tests, G end line, file written, group state
run_group:
        ld a,b : ld (curg),a
        call sess_header
        ld a,(curg) : call gent
        ld a,(ix+4) : cp 1 : jr nz,.nv              ; the operator group in an unattended run
        ld a,(mode) : and $7F : jr nz,.nv
        ld a,1 : ld (unatt),a : jr .s
.nv:    xor a : ld (unatt),a
.s:     ; progress: running, between tests, this group
        ld a,1 : ld (PRGB+PRG_STATE),a
        ld a,(curg) : ld (PRGB+PRG_GROUP),a
        ld a,(mode) : and $7F : ld (PRGB+PRG_MODE),a
        ld hl,PRGB+PRG_GST : ld a,(curg) : add a,l : ld l,a : ld (hl),GS_RUN
        ld hl,$FFFF : call prg_mark
        ld a,(curg) : call gent
        ld a,(ix+0) : ld (gfirst),a
        ld a,(ix+1) : ld (gcount),a
        call gscreen
        ld a,1 : out ($FE),a                        ; blue while running
        ; G line
        call w_lb : ld hl,s_gid : call wstr : call wgid
        ld hl,s_gname : call wstr
        ld a,(curg) : call gent : ld l,(ix+5) : ld h,(ix+6) : ld de,WORK : call far_copy
        ld hl,WORK : call wstr
        ld hl,s_gstart : call wstr
        ld a,(mode) : bit 7,a : jr z,.nr
        ld hl,s_resumed : call wstr
.nr:    ld a,10 : call wchr : call w_len : call txt_append
        xor a : ld (gfails),a : ld (ginfo),a
        ld a,(gcount) : ld b,a : ld a,(gfirst) : ld c,a
.t:     push bc
        ld a,c : call run_test_marked
        pop bc : inc c : djnz .t
        ; G end
        call w_lb : ld hl,s_gid : call wstr : call wgid
        ld hl,s_gend : call wstr
        ld a,(gfails) : ld l,a : ld h,0 : call wdec
        ld a,10 : call wchr : call w_len : call txt_append
        ; state
        ld e,GS_DONE : ld a,(gfails) : or a : jr z,.st
        ld e,GS_FAILS
.st:    ld a,(unatt) : or a : jr z,.st2
        push de : ld a,(curg) : call gent : pop de : ld a,(ix+2) : or a : jr z,.st2
        ld e,GS_PENDOP
.st2:   ld hl,PRGB+PRG_GST : ld a,(curg) : add a,l : ld l,a : ld (hl),e
        ld hl,$FFFF : call prg_mark
        call txt_flush
        ; border: green no FAIL, yellow INFO only, red a FAIL
        ld a,4 : ld e,a : ld a,(ginfo) : or a : jr z,.b1
        ld e,6
.b1:    ld a,(gfails) : or a : jr z,.b2
        ld e,2
.b2:    ld a,e : out ($FE),a
        ret
curg:   db 0
gfirst: db 0
gcount: db 0
gfails: db 0
ginfo:  db 0
unatt:  db 0
s_gid:  db "G id=",0
s_gname: db " name=",0
s_gstart: db " start",0
s_resumed: db " resumed",0
s_gend: db " end fails=",0

; the group id ("G3", "V", "XT") of (curg)
wgid:   ld a,(curg) : cp 10 : jr nc,.o
        ld a,'G' : call wchr : ld a,(curg) : add a,'0' : jp wchr
.o:     sub 10 : add a,a : ld l,a : ld h,0 : ld de,gids : add hl,de
        ld a,(hl) : call wchr : inc hl : ld a,(hl) : cp ' ' : ret z
        jp wchr
gids:   db "V XTXDXH"

; HL = test index or $FFFF -> progress record state 1, written
prg_mark:
        ld (PRGB+PRG_TIDX),hl
        ld a,h : and l : inc a : jr nz,.id
        ld hl,PRGB+PRG_TID : ld b,8
.c:     ld (hl),' ' : inc hl : djnz .c
        jr .w
.id:    ld a,l : call tent
        push ix : pop hl : ld de,PRGB+PRG_TID : ld bc,4 : ldir
        ld a,' ' : ld b,4
.p:     ld (de),a : inc de : djnz .p
.w:     ld a,1 : ld (PRGB+PRG_STATE),a
        jp prg_write

; A = test index -> IX = its ttab entry (12 bytes)
tent:   ld l,a : ld h,0 : ld d,h : ld e,l : add hl,hl : add hl,de : add hl,hl : add hl,hl   ; * 12
        ld de,ttab : add hl,de : push hl : pop ix
        ret

; A = test index -> carry if in the hung list
hung_is:
        ld hl,PRGB+PRG_HUNG : ld b,6
.l:     cp (hl) : jr nz,.n
        inc hl : ld c,a : ld a,(hl) : dec hl : or a : ld a,c : scf : ret z
.n:     inc hl : inc hl : djnz .l
        or a : ret
; HL = test index -> added to the hung list (first free word; when full the oldest is replaced)
hung_add:
        ex de,hl
        ld hl,PRGB+PRG_HUNG : ld b,6
.l:     ld a,(hl) : inc hl : and (hl) : inc a : jr z,.f
        inc hl : djnz .l
        ld hl,PRGB+PRG_HUNG+1
.f:     ld (hl),d : dec hl : ld (hl),e
        ret

; ---------------------------------------------------------------- one test
; A = test index: decides run / skip, marks the progress record before a risky test, runs it, writes
; the T line, the results table and the screen.
run_test_marked:
        ld (curt),a
        call tent : ld (cure),ix
        ; clear the result
        ld hl,R_st : ld de,R_st+1 : ld bc,R_end-R_st-1 : ld (hl),0 : ldir
        ld a,ST_INFO : ld (R_st),a
        ld hl,1 : ld (R_n),hl
        ld hl,EXB : ld (wp),hl : ld (hl),0 : xor a : ld (wsink),a
        call scr_mark                               ; '>' on the screen
        ld ix,(cure)
        ld l,(ix+6) : ld h,(ix+7) : ld a,h : or l : jr nz,.b
        ld hl,why_nb : jr .skip
.b:     ld a,(curt) : ld hl,(justhung) : cp l : jr nz,.nj
        ld a,h : or a : jr nz,.nj
        ld a,ST_HANG : ld (R_st),a
        ld hl,$FFFF : ld (justhung),hl
        jp .emit
.nj:    ld a,(retrying) : or a : jr nz,.go
        ld a,(curt) : call hung_is : jr nc,.nh
        ld hl,why_hung : jr .skip
.nh:    ld ix,(cure) : bit 2,(ix+5) : jr z,.ni      ; opt-in: never in RUN ALL
        ld a,(mode) : and $7F : jr nz,.ni
        ld hl,why_ns : jr .skip
.ni:    bit 1,(ix+5) : jr z,.go                     ; operator test, unattended: pending
        ld a,(unatt) : or a : jr z,.go
        ld a,ST_PENDOP : ld (R_st),a : jr .emit
.skip:  ld (R_why),hl : ld a,ST_SKIP : ld (R_st),a : jr .emit
.go:    ld ix,(cure) : bit 0,(ix+5) : jr z,.nm
        ld a,(curt) : ld l,a : ld h,0 : call prg_mark
.nm:    ld (tsp),sp
        ld ix,(cure) : ld l,(ix+6) : ld h,(ix+7)
        ld a,(spd0) : nextreg $07,a
        call .jp
        di
        ld sp,(tsp)
        call restore_all
        ld a,(spd0) : nextreg $07,a
        ld ix,(cure) : bit 0,(ix+5) : jr z,.emit
        ld hl,$FFFF : call prg_mark                 ; between tests again
.emit:  ld hl,(wp) : ld (hl),0                      ; extras end
        call emit_t
        call stab_put
        call scr_status
        ld a,(R_st) : cp ST_FAIL : jr nz,.i
        ld hl,gfails : inc (hl)
.i:     cp ST_INFO : ret c
        ld hl,ginfo : inc (hl)
        ret
.jp:    jp (hl)
curt:   db 0
cure:   dw 0
tsp:    dw 0
why_nb: db "not-built",0
why_hung: db "hung-last-run",0
why_ns: db "not-selected",0

; the result of the test being run (tests set these; harness writes the line)
R_st:   db 0
R_vk:   db 0
R_v:    ds 4
R_min:  ds 4
R_max:  ds 4
R_n:    dw 0
R_unit: dw 0
R_why:  dw 0
R_end:

; ---------------------------------------------------------------- helpers for tests
; DEHL = value x 100 -> single-shot number (n = 1, min = max = v)
res_num:
        ld (R_v),hl : ld (R_v+2),de
        ld (R_min),hl : ld (R_min+2),de
        ld (R_max),hl : ld (R_max+2),de
        ld a,VK_NUM : ld (R_vk),a
        ld hl,1 : ld (R_n),hl
        ret
; HL = unsigned integer -> res_num
res_int:
        call x100 : jr res_num
; A = byte -> "$hh"
res_hex:
        ld (R_v),a : ld a,VK_HEX : ld (R_vk),a : ret
; HL = 16-bit raw -> "$hhhh"
res_hex16:
        ld (R_v),hl : ld a,VK_HEX16 : ld (R_vk),a : ret
; HL = choice word
res_word:
        ld (R_v),hl : ld a,VK_WORD : ld (R_vk),a : ret
; the five-run result of trow -> v = mean, min, max, n = 5
res_trow:
        ld hl,tr_mean : ld de,R_v : ld bc,4 : ldir
        ld hl,tr_min : ld de,R_min : ld bc,4 : ldir
        ld hl,tr_max : ld de,R_max : ld bc,4 : ldir
        ld hl,5 : ld (R_n),hl
        ld a,VK_NUM : ld (R_vk),a
        ret
; HL = unit string
res_unit:
        ld (R_unit),hl : ret
; HL = key -> " key=" into the extras
ex_k:   ld a,' ' : call wchr : call wstr : ld a,'=' : jp wchr
; HL = key, A = byte -> " key=$hh"
ex_kh:  push af : call ex_k : pop af : jp wdhex2
; HL = key, DE = value -> " key=<decimal>"
ex_kd:  push de : call ex_k : pop hl : jp wdec
; HL = key, (tr_mean) -> " key=<mean>"
ex_kmean:
        call ex_k : ld hl,(tr_mean) : ld de,(tr_mean+2) : jp wfix

; a sub-test line now: HL = id string; R_* and the extras written so far as for a test line; afterwards
; the extras are empty again and the status INFO (the main line is written by the harness at the end)
sub_emit:
        ld (subid),hl
        ld hl,(wp) : ld (hl),0
        call emit_t
        ld hl,0 : ld (subid),hl
        ld hl,EXB : ld (wp),hl : ld (hl),0
        xor a : ld (wsink),a
        ld a,ST_INFO : ld (R_st),a
        ret

; ---------------------------------------------------------------- the T line
emit_t: call w_lb
        ld hl,s_tid : call wstr
        ld hl,(subid) : ld a,h : or l : jr z,.mid
        call wstr : jr .sid
.mid:   ld ix,(cure) : call wtid
.sid:
        ld hl,s_st : call wstr
        ld a,(R_st) : add a,a : ld l,a : ld h,0 : ld de,stnames : add hl,de
        ld a,(hl) : inc hl : ld h,(hl) : ld l,a : call wstr
        ld hl,s_c : call wstr
        ld ix,(cure) : ld l,(ix+8) : ld h,(ix+9) : ld de,WORK : call far_copy
        ld hl,WORK : call wstr
        ld hl,s_v : call wstr : ld hl,R_v : call wval
        ld hl,s_u : call wstr : ld hl,(R_unit) : ld a,h : or l : jr nz,.u
        ld hl,s_dash
.u:     call wstr
        ld hl,s_n : call wstr : ld hl,(R_n) : ld a,(R_vk) : or a : jr nz,.n
        ld hl,0
.n:     call wdec
        ld hl,s_min : call wstr : ld hl,R_min : call wval_mm
        ld hl,s_max : call wstr : ld hl,R_max : call wval_mm
        ld hl,(R_why) : ld a,h : or l : jr z,.x
        push hl : ld hl,s_why : call wstr : pop hl : call wstr
.x:     ld hl,EXB : call wstr
        ld a,10 : call wchr
        call w_len : jp txt_append
s_tid:  db "T id=",0
subid:  dw 0                    ; non-zero: a sub-test id string (e.g. "ih.t1") written instead of the test id
s_st:   db " st=",0
s_c:    db " c=",0
s_v:    db " v=",0
s_u:    db " u=",0
s_n:    db " n=",0
s_min:  db " min=",0
s_max:  db " max=",0
s_why:  db " why=",0
s_dash: db "-",0
stnames: dw s_dash,st1,st2,st3,st4,st5,st6,st7,st8,st9
st1:    db "PASS",0
st2:    db "FAIL",0
st3:    db "INFO",0
st4:    db "SKIP",0
st5:    db "HANG-GUARD",0
st6:    db "VISUAL",0
st7:    db "VISUAL-SHOWN",0
st8:    db "OPERATOR",0
st9:    db "PENDING-OPERATOR",0
; IX = test entry -> its id, spaces dropped
wtid:   ld b,4
.l:     ld a,(ix+0) : inc ix : cp ' ' : call nz,wchr : djnz .l
        ret
; HL = value field (R_v layout), by R_vk
wval:   ld a,(R_vk)
        cp VK_NUM : jr z,.num
        cp VK_HEX : jr z,.hex
        cp VK_HEX16 : jr z,.h16
        cp VK_WORD : jr z,.w
        ld hl,s_dash : jp wstr
.num:   ld e,(hl) : inc hl : ld d,(hl) : inc hl : ld a,(hl) : inc hl : ld h,(hl) : ld l,a
        ex de,hl : jp wfix
.hex:   ld a,(hl) : jp wdhex2
.h16:   ld a,'$' : call wchr : ld a,(hl) : inc hl : ld h,(hl) : ld l,a : jp whex4
.w:     ld a,(hl) : inc hl : ld h,(hl) : ld l,a : jp wstr
; min / max: the number's own, else the value again
wval_mm:
        ld a,(R_vk) : cp VK_NUM : jr z,wval
        ld hl,R_v : jr wval

; results table entry: status, group, value dword x 100 (numbers; a byte value x 100), n
stab_put:
        ld a,(R_vk) : cp VK_NUM : jr nz,.h
        ld hl,(R_v) : ld de,(R_v+2) : jr .s
.h:     ld hl,0 : ld de,0 : cp VK_HEX : jr nz,.s
        ld a,(R_v) : ld l,a : call x100
.s:     ld (.t),hl : ld (.t+2),de
        ld a,(curt) : ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,STAB+7 : add hl,de
        ld a,(R_st) : ld (hl),a : inc hl
        ld a,(curg) : ld (hl),a : inc hl
        ex de,hl : ld hl,.t : ld bc,4 : ldir : ex de,hl
        ld a,(R_n) : ld (hl),a
        ret
.t:     ds 4

; ---------------------------------------------------------------- session header (spec section 2)
sess_header:
        ld a,(sess_done) : or a : ret nz
        inc a : ld (sess_done),a
        ld a,(fstate) : cp 1 : jr z,.h
        ld hl,0 : ld (txtlen),hl : ld (txtlines),hl : ld hl,$FFFF : ld (crc),hl
        call w_lb : ld hl,s_magic : call wstr : call w_len : call txt_append
        ld a,(fstate) : cp 2 : jr nz,.h
        call w_lb : ld hl,s_unread : call wstr : call w_len : call txt_append
.h:     ; H suite
        call w_lb : ld hl,h_suite : call wstr
        ld hl,srcstr : call wstr : ld hl,h_built : call wstr : ld hl,datestr : call wstr
        ld hl,h_run : call wstr : ld hl,(runno) : call wdec
        ld hl,h_mode : call wstr
        ld a,(mode) : bit 7,a : jr z,.m1
        ld hl,h_resume : call wstr : jr .m3
.m1:    and $7F : jr nz,.m2
        ld hl,h_all : call wstr : jr .m3
.m2:    cp $7F : jr nz,.m2b
        ld hl,h_hung : call wstr : jr .m3
.m2b:   push af : ld hl,h_group : call wstr : pop af : dec a : ld (curg),a : call wgid
.m3:    ld hl,h_rf : call wstr
        ld hl,(PRGB+PRG_TIDX) : ld a,(mode) : bit 7,a : jr z,.nr
        ld a,h : and l : inc a : jr z,.nr
        ld a,l : call tent : call wtid : jr .rr
.nr:    ld a,'-' : call wchr
.rr:    call hend
        ; H core
        call w_lb : ld hl,h_core : call wstr : call wcore
        ld hl,h_nr01 : call wstr : ld a,(NRSNAP+$01) : call wdhex2
        ld hl,h_nr0e : call wstr : ld a,(NRSNAP+$0E) : call wdhex2
        ld hl,h_mach : call wstr : ld a,(NRSNAP+$00) : call wdhex2
        ld hl,h_board : call wstr : ld a,(NRSNAP+$0F) : call wdhex2
        ld hl,h_ram : call wstr : ld a,(ramchoice) : call wram
        call hend
        ; H video
        call w_lb : ld hl,h_video : call wstr
        ld a,(NRSNAP+$11) : and 7 : cp 7 : ld hl,h_hdmi : jr z,.v
        ld hl,h_vga
.v:     call wstr
        ld hl,h_nr11 : call wstr : ld a,(NRSNAP+$11) : call wdhex2
        ld hl,h_timing : call wstr : ld a,(NRSNAP+$03) : call wdhex2
        ld hl,h_hz : call wstr : ld a,(NRSNAP+$05) : and 4 : ld hl,h_50 : jr z,.z
        ld hl,h_60
.z:     call wstr
        ld hl,h_nr05 : call wstr : ld a,(NRSNAP+$05) : call wdhex2
        ld hl,h_lines : call wstr : ld hl,(flines) : inc hl : call wdec
        ld hl,h_linet : call wstr : call wlinet_ctc
        call hend
        ; H speed
        call w_lb : ld hl,h_speed : call wstr : ld a,(NRSNAP+$07) : call wdhex2
        ld hl,h_cal : call wstr : ld hl,(cal) : call wdec
        ld hl,h_calctc : call wstr : ld hl,(ctcpl) : ld de,(ctcpl+2) : call wfix
        ld hl,h_tpl : call wstr : call wtpl
        call hend
        ; H divmmc
        call w_lb : ld hl,h_div : call wstr
        ld hl,h_nr0a : call wstr : ld a,(NRSNAP+$0A) : call wdhex2
        ld hl,h_nrb8 : call wstr : ld a,(NRSNAP+$B8) : call wdhex2
        ld hl,h_nrb9 : call wstr : ld a,(NRSNAP+$B9) : call wdhex2
        ld hl,h_nrba : call wstr : ld a,(NRSNAP+$BA) : call wdhex2
        ld hl,h_nrbb : call wstr : ld a,(NRSNAP+$BB) : call wdhex2
        call hend
        ; R lines, only in a new file
        ld a,(fstate) : cp 1 : ret z
        ld e,0
.r:     push de
        call w_lb : ld hl,h_r : call wstr : pop de : push de : ld a,e : call wdhex2
        ld hl,h_rv : call wstr : pop de : push de : ld l,e : ld h,NRSNAP>>8 : ld a,(hl) : call wdhex2
        call hend
        pop de : inc e : jr nz,.r
        ret
hend:   ld a,10 : call wchr : call w_len : jp txt_append
s_unread: db "# the NXSUITE.TXT found was not complete; a new file was started",10,0
h_suite: db "H suite=1.0 src=",0
h_built: db " built=",0
h_run:  db " run=",0
h_mode: db " mode=",0
h_resume: db "RESUME",0
h_all:  db "ALL",0
h_hung: db "RETRY-HUNG",0
h_group: db "GROUP:",0
h_rf:   db " resumed_from=",0
h_core: db "H core=",0
h_nr01: db " nr01=",0
h_nr0e: db " nr0e=",0
h_mach: db " machine=nr00:",0
h_board: db " board=nr0f:",0
h_ram:  db " ram=",0
h_video: db "H video=",0
h_hdmi: db "HDMI",0
h_vga:  db "VGA",0
h_nr11: db " nr11=",0
h_timing: db " timing=nr03:",0
h_hz:   db " hz=",0
h_50:   db "50",0
h_60:   db "60",0
h_nr05: db " nr05=",0
h_lines: db " lines=",0
h_linet: db " line_t=",0
h_speed: db "H speed_start=nr07:",0
h_cal:  db " cal35=",0
h_calctc: db " cal_ctc=",0
h_tpl:  db " t_per_line=",0
h_div:  db "H divmmc",0
h_nr0a: db " nr0a=",0
h_nrb8: db " nrb8=",0
h_nrb9: db " nrb9=",0
h_nrba: db " nrba=",0
h_nrbb: db " nrbb=",0
h_r:    db "R nr=",0
h_rv:   db " v=",0

; core version a.b.cc from NextRegs $01 / $0E
wcore:  ld a,(NRSNAP+$01) : rrca : rrca : rrca : rrca : and 15 : add a,'0' : call wchr
        ld a,'.' : call wchr
        ld a,(NRSNAP+$01) : and 15 : call .two
        ld a,'.' : call wchr
        ld a,(NRSNAP+$0E)
.two:   ld b,0
.t:     cp 10 : jr c,.u
        sub 10 : inc b : jr .t
.u:     push af : ld a,b : add a,'0' : call wchr : pop af : add a,'0' : jp wchr
; A = RAM choice 0 wrap / 1 alias0 / 2 distinct
wram:   add a,a : ld l,a : ld h,0 : ld de,ramw : add hl,de
        ld a,(hl) : inc hl : ld h,(hl) : ld l,a : jp wstr
ramw:   dw rw0,rw1,rw2
rw0:    db "wrap",0
rw1:    db "alias0",0
rw2:    db "distinct",0
; T per line from the calibration: 4 x 38912 / cal, x 100
wtpl:   ld hl,$8000 : ld de,$00ED                   ; 15,564,800 = 4 x 38912 x 100
        ld bc,(cal) : ld a,b : or c : jr nz,.d
        inc bc
.d:     call div32 : jp wfix
; T per line from the CTC: ticks per line x 2 (one tick = 16 clocks of 28 MHz = 2 T at 3.5 MHz)
wlinet_ctc:
        ld hl,(ctcpl) : ld de,(ctcpl+2)
        add hl,hl : rl e : rl d
        jp wfix
; screen: core version at the cursor
pcore:  ld a,1 : ld (wsink),a
        call wcore
        xor a : ld (wsink),a
        ret

; ---------------------------------------------------------------- group screen
gscreen:
        call cls
        xor a : ld (crow),a : ld (ccol),a
        ld a,1 : ld (wsink),a
        call wgid
        ld a,' ' : call putc
        ld a,(curg) : call gent : ld l,(ix+5) : ld h,(ix+6) : ld de,WORK : call far_copy
        ld hl,WORK : call puts
        ld hl,m_running : call puts
        xor a : ld (wsink),a
        ld a,(curg) : call gent
        ld a,(ix+1) : ld b,a : ld a,(ix+0) : ld c,a
.t:     push bc
        ld a,c : call tpos
        ld a,c : call tent
        ld a,1 : ld (wsink),a : call wtid : xor a : ld (wsink),a
        ld a,(ccol) : and $F0 : add a,5 : ld (ccol),a
        ld l,(ix+10) : ld h,(ix+11) : ld de,WORK : call far_copy
        ld hl,WORK : ld b,9
.c:     ld a,(hl) : or a : jr z,.cd
        call putc : inc hl : djnz .c
.cd:    pop bc : inc c : djnz .t
        ret
m_running: db " - running",0
; A = test index -> crow / ccol of its line on the group screen (rows 2-23, two columns)
tpos:   ld hl,gfirst : sub (hl)
        cp 22 : jr nc,.r
        add a,2 : ld (crow),a : xor a : ld (ccol),a : ret
.r:     sub 20 : ld (crow),a : ld a,16 : ld (ccol),a : ret
; '>' at the status column of the test being run
scr_mark:
        ld a,(curt) : call tpos
        ld a,(ccol) : add a,15 : ld (ccol),a
        ld a,'>' : jp putc
; status letter + colour
scr_status:
        ld a,(curt) : call tpos
        ld a,(ccol) : add a,15 : ld (ccol),a
        ld a,(R_st) : ld l,a : ld h,0 : ld de,stlet : add hl,de : ld a,(hl)
        push af : call putc : pop af
        ld a,(R_st) : ld l,a : ld h,0 : ld de,stcol : add hl,de : ld e,(hl)
        ld a,(ccol) : dec a : ld (ccol),a : jp paint1
stlet:  db " PFISHVVOQ"
stcol:  db $38,$60,$50,$78,$38,$58,$68,$68,$68,$68

; ---------------------------------------------------------------- screen primitives (ROM font at $3D00)
cls:    ld hl,$4000 : ld de,$4001 : ld bc,6143 : ld (hl),0 : ldir
        ld hl,$5800 : ld de,$5801 : ld bc,767 : ld (hl),$38 : ldir
        ret
; E = attribute for the cell at crow, ccol
paint1: ld a,(crow) : ld l,a : ld h,0
        add hl,hl : add hl,hl : add hl,hl : add hl,hl : add hl,hl
        ld a,(ccol) : add a,l : ld l,a
        ld bc,$5800 : add hl,bc
        ld (hl),e
        ret
putc:   push hl : push de : push bc
        ld c,a : ld a,(ccol) : cp 32 : jr nc,.x
        ld a,(crow) : cp 24 : jr nc,.x
        ld a,c : sub 32 : jr c,.x
        ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,$3D00 : add hl,de
        ld a,(crow) : and $18 : or $40 : ld d,a
        ld a,(crow) : and 7 : rrca : rrca : rrca : ld e,a
        ld a,(ccol) : or e : ld e,a
        ld b,8
.l:     ld a,(hl) : ld (de),a : inc hl : inc d : djnz .l
.x:     ld a,(ccol) : inc a : ld (ccol),a
        pop bc : pop de : pop hl
        ret
puts:   ld a,(hl) : or a : ret z
        call putc : inc hl : jr puts
; HL = number on the screen
sdec:   ld a,1 : ld (wsink),a : call wdec : xor a : ld (wsink),a : ret
crow:   db 0
ccol:   db 0

; ---------------------------------------------------------------- keyboard
; -> A = the key pressed (ASCII capitals, digits, 13 = ENTER, ' ' = SPACE), 0 = none
getkey: ld hl,keymap : ld bc,$FEFE
.r:     in a,(c) : cpl : and $1F : ld e,5
.k:     rra : jr c,.got
        inc hl : dec e : jr nz,.k
        rlc b : jr c,.r
        xor a : ret
.got:   ld a,(hl) : ret
keymap: db 0,"ZXCV","ASDFG","QWERT","12345","09876","POIUY",13,"LKJH"," ",0,"MNB"
keys_up:
.w:     xor a : in a,($FE) : cpl : and $1F : jr nz,.w
        ret
