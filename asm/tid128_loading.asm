; Treasure Island Dizzy loading screen stub: bank 44 (pages 88, 89), entry bank, PC $C000; the original start is bank 10, page 20, at $C000.
; nexclash/tid128_v11.py (loading_nex) puts the original tape's screen in bank 5's screen area of the .nex and bank 5's own
; 6,912 bytes at $C200 here, so the screen shows while bank 5 loads; this holds it until a key or about 5 s, waits for
; release, puts bank 5's bytes back and goes on to the original start with every register, slot and stack byte as
; .nexload would have left them.
; On entry .nexload has left slots 2-5 = 10,11,4,5, slots 6-7 = this bank, DI, SP = $DFFE and $C000 pushed just below SP, here.
; No byte outside this bank differs when it leaves. It ends in slot 5, on the last bytes of page 89, whose last instruction puts
; page 5 back: the next fetch is $C000 with no trampoline in RAM. The border stays as the loader set it; this never writes it.
LOAD_PAGE equ     89              ; the stub bank's upper page
        INCLUDE "lib/loading_stub.inc"
        SAVEBIN "tidload_head.bin",$C000,$C200-$C000
        SAVEBIN "tidload_tail.bin",$FFD0,$10000-$FFD0
