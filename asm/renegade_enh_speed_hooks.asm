; Target Renegade hook-speed build, Enhanced colours: renegade_speed_common.asm with ENH.
        DEFINE ENH
        INCLUDE "renegade_speed_common.asm"

        SAVEBIN "tr_rom.bin",0x2200,rom_end-0x2200
        SAVEBIN "tr_setup.bin",0xD000,pal-0xD000
        SAVEBIN "tr_front.bin",0x6480,front_end-0x6480
