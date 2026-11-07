; Atic Atac, the "QAOP + Space" toggle build: the base hooks (atic_atac_v14_hooks.asm) with QAOP defined,
; which adds h_qaop (the keyboard read 0x93CD) and h_pause (the pause check 0x948A) after the base
; code. The base assembles byte for byte as without this file. Profile: docs/profiles/atic_atac_v14_qaop.json.
        DEFINE QAOP
        INCLUDE "atic_atac_v14_hooks.asm"
        SAVEBIN "aq_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "aq_setup.bin",0xD000,ops-0xD000
