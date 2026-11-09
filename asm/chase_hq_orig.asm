; Chase H.Q.: the "Orig. pace" colour set: Enhanced colours, the pace target following the original's time for each update (asm/chase_hq_hooks.asm, CHQ_SET 2).
        DEFINE CHQ_SET 2
        DEFINE CHQ_WRAPPED
        INCLUDE "chase_hq_hooks.asm"
        SAVEBIN "chase_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "hud_aux.bin",hud_aux,hud_aux_end-hud_aux
