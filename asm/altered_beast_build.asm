; Assemble both editions from the same source. The unbanked binary is the published default.
        INCLUDE altered_beast_hooks.asm
        SAVEBIN "ab_rom.bin",0x2400,rom_end-0x2400
        SAVEBIN "ab_setup.bin",0xD000,pal-0xD000

        DEFINE AB_BANKED
        MODULE enhanced
        INCLUDE altered_beast_hooks.asm
        ENDMODULE
        SAVEBIN "ab_banked_rom.bin",0x2400,enhanced.rom_end-0x2400
        SAVEBIN "ab_banked_setup.bin",0xD000,enhanced.pal-0xD000
