; Sabre Wulf, the Enhanced colour set with the "QAOP + Space" toggle: SABREMAN_BANKS (sabre_wulf_enhanced.asm) and
; QAOP (sabre_wulf_qaop.asm) both defined. Profile: docs/profiles/sabre_wulf_enhanced_qaop.json.
        DEFINE SABREMAN_BANKS
        DEFINE QAOP
        INCLUDE "sabre_wulf_hooks.asm"
        SAVEBIN "sweq_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "sweq_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "sweq_qaop.bin",0x3C00,qaop_end-0x3C00
