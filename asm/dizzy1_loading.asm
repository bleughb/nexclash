; Dizzy 1 loading screen stub: bank 43 (pages 86, 87), entry bank, PC $C000; the original start is bank 10, page 20, at $C000.
; nexclash/dizzy1.py (loading_nex) puts the original tape's screen in bank 5's screen area of the .nex and bank 5's own
; 6,912 bytes at $C200 here, so the screen shows while bank 5 loads; this holds it until a key or about 5 s, waits for
; release, puts bank 5's bytes back and goes on to the original start with every register, slot and stack byte as
; .nexload would have left them.
; On entry .nexload has left slots 2-5 = 10,11,4,5, slots 6-7 = this bank, DI, SP = $DFFE and $C000 pushed just below SP, here.
; No byte outside this bank differs when it leaves. It ends in slot 5, on the last bytes of page 87, whose last instruction puts
; page 5 back: the next fetch is $C000 with no trampoline in RAM. The border stays as the loader set it; this never writes it.
        DEVICE  ZXSPECTRUMNEXT
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 87; below it the stub's call stack
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
; A key counts only after the keyboard has been seen clear, so one held at the start doesn't.
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
; Leave only after the keyboard has been clear for a few frames, so the game doesn't see the key.
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
        ld      bc,$243B
        ld      a,(SEL)
        out     (c),a
        nextreg $55,87
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
        ds      SCRLEN          ; bank 5's own bytes, filled in by loading_nex (no game data here)
        assert  $ <= $DF00      ; $DFxx: the loader's stack
        ds      $FFD0-$         ; REGS is written at run time; zero in the file
        disp    $-$4000
; Runs from page 87 at slot 5. The entry bank's top bytes get what the loader's stack left there.
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
        nextreg $55,5           ; falls through to $C000, the entry bank
        assert  $ == $C000
        ent
        SAVEBIN "d1load_head.bin",$C000,$C200-$C000
        SAVEBIN "d1load_tail.bin",$FFD0,$10000-$FFD0
