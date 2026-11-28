; One source for the common hooks. The published build assembles without ENHANCED.
        DEFINE ENHANCED
        INCLUDE "dynamite_dan_hooks.asm"
        SAVEBIN "dd_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "dd_setup.bin",0xD000,setup_end-0xD000
