; Chase H.Q.: the "Speed" colour set: Enhanced colours at the Speed targets (asm/chase_hq_hooks.asm, CHQ_SET 1).
        DEFINE CHQ_SET 1
        DEFINE CHQ_WRAPPED
        INCLUDE "chase_hq_hooks.asm"
        SAVEBIN "chase_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "hud_aux.bin",hud_aux,hud_aux_end-hud_aux
