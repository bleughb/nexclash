; Sabre Wulf, the "QAOP + Space" toggle build: the base hooks (sabre_wulf_hooks.asm) with QAOP defined, which adds
; h_qaop (the keyboard read 0xB0FA) at 0x3C00, past the base code and its register block. The base assembles byte
; for byte as without this file. Profile: docs/profiles/sabre_wulf_qaop.json.
        DEFINE QAOP
        INCLUDE "sabre_wulf_hooks.asm"
        SAVEBIN "swq_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "swq_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "swq_qaop.bin",0x3C00,qaop_end-0x3C00
