; Optional wide-palette figures and scenery, over the same original game code.
        DEFINE DZ_ENHANCED
        DEFINE DZ_NO_SAVE
        INCLUDE "dizzy1_hooks.asm"
        SAVEBIN "d1_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "d1_setup.bin",0xD000,pal-0xD000
