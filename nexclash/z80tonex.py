#!/usr/bin/env python3
"""
z80tonex.py - convert a ZX Spectrum .z80 snapshot into a ZX Spectrum Next .nex file.

The result starts the snapshot exactly where it was saved, with the Next set up
to behave like the original machine:

  * CPU at 3.5MHz, 48K (or 128K) display timing, RAM/IO contention enabled
  * 48K BASIC ROM paged in (or the ROM selected by the snapshot for 128K)
  * 7FFD paging locked for 48K snapshots
  * DivMMC automatic paging disabled (so RST 38 / IM 1 reaches the real ROM)
  * 50Hz video forced by default (game speed depends on the frame rate)
  * every Z80 register restored, including the alternate set, IX, IY, I, R,
    the interrupt mode, interrupt enable state and the border colour

How it starts:
  The NEX loader starts a small setup stub held in a spare 16K bank (bank 10,
  mapped at C000 by the NEX "entry bank" field). The stub configures the Next,
  then copies a short "tail" routine into a few bytes of the game's memory and
  jumps to it. The tail pages the ROM and bank 0 back in, sets the machine
  timing, restores every register from a block stored with it, and jumps to
  the snapshot's PC.

  By default the tail goes into the 48K printer buffer (0x5B00) if those bytes
  are all zero in the snapshot, otherwise just below the snapshot's stack
  pointer. The tail's bytes stay in memory after the game starts, so the tail
  location must be memory the game never uses. Check this for each game, or
  choose a location with --tail.

Usage:
  python z80tonex.py game.z80 [-o game.nex] [--tail ADDR] [--allow-60hz]

48K and 128K snapshots (128K builds run on hardware: Crystal Kingdom Dizzy, Rainbow Islands,
Everyone's a Wally, Commando). The main CLI is `python nexclash.py convert` (same options).
"""

import argparse
import os
import struct
import sys

STUB_BANK = 10          # spare 16K bank for the setup stub (outside the 128K banks)
STUB_ORG = 0xC000       # entry bank is mapped at C000..FFFF by the loader
STUB_PAGE_HI = 21      # upper 8K page of the stub bank (mapped at E000 by the loader)
STUB_PAGE_LO = 20      # lower 8K page of the stub bank (mapped at C000 by the loader)
STUB_SP = 0xDFFE       # top of the stub's 8K page (C000-DFFF)


# --------------------------------------------------------------------------
# .z80 snapshot reader
# --------------------------------------------------------------------------

class Z80Snapshot:
    def __init__(self, path):
        data = open(path, 'rb').read()
        h = data[:30]
        self.a, self.f = h[0], h[1]
        self.bc = h[2] | h[3] << 8
        self.hl = h[4] | h[5] << 8
        pc = h[6] | h[7] << 8
        self.sp = h[8] | h[9] << 8
        self.i = h[10]
        flags12 = h[12] if h[12] != 255 else 1
        self.r = (h[11] & 0x7F) | ((flags12 & 1) << 7)
        self.border = (flags12 >> 1) & 7
        compressed_v1 = bool(flags12 & 0x20)
        self.de = h[13] | h[14] << 8
        self.bc_ = h[15] | h[16] << 8
        self.de_ = h[17] | h[18] << 8
        self.hl_ = h[19] | h[20] << 8
        self.a_, self.f_ = h[21], h[22]
        self.iy = h[23] | h[24] << 8
        self.ix = h[25] | h[26] << 8
        self.iff1 = 1 if h[27] else 0
        self.iff2 = 1 if h[28] else 0
        self.im = h[29] & 3
        self.issue2 = (h[29] >> 2) & 1

        self.is128 = False
        self.port7ffd = 0
        self.port1ffd = 0
        self.ay_regs = [0] * 16
        self.ay_last = 0
        self.banks = {}          # 16K bank number -> bytes

        if pc != 0:
            # version 1: 48K only, one 48K block
            self.version = 1
            self.pc = pc
            body = data[30:]
            if compressed_v1:
                if body.endswith(b'\x00\xED\xED\x00'):
                    body = body[:-4]
                ram = self._decompress(body)
            else:
                ram = body
            if len(ram) < 49152:
                raise ValueError('48K block is too short (%d bytes)' % len(ram))
            ram = ram[:49152]
            self.banks = {5: ram[0:16384], 2: ram[16384:32768], 0: ram[32768:49152]}
        else:
            ext_len = data[30] | data[31] << 8
            ext = data[32:32 + ext_len]
            self.version = 2 if ext_len == 23 else 3
            self.pc = ext[0] | ext[1] << 8
            hw = ext[2]
            if self.version == 2:
                self.is128 = hw in (3, 4)
            else:
                self.is128 = hw in (4, 5, 6, 7, 9, 12, 13)
            if hw in (7, 12, 13) and self.version == 3 and ext_len >= 55:
                self.port1ffd = ext[54]
            if self.is128:
                self.port7ffd = ext[3]
                self.ay_last = ext[6]
                self.ay_regs = list(ext[7:23])
            j = 32 + ext_len
            while j < len(data):
                blen = data[j] | data[j + 1] << 8
                page = data[j + 2]
                j += 3
                if blen == 0xFFFF:
                    block = data[j:j + 16384]
                    j += 16384
                else:
                    block = self._decompress(data[j:j + blen])
                    j += blen
                if len(block) != 16384:
                    raise ValueError('page %d decompressed to %d bytes' % (page, len(block)))
                if self.is128:
                    if 3 <= page <= 10:
                        self.banks[page - 3] = block
                else:
                    bank = {8: 5, 4: 2, 5: 0}.get(page)
                    if bank is not None:
                        self.banks[bank] = block
            needed = range(8) if self.is128 else (5, 2, 0)
            missing = [b for b in needed if b not in self.banks]
            if missing:
                raise ValueError('snapshot is missing RAM banks %s' % missing)

    @staticmethod
    def _decompress(src):
        out = bytearray()
        i = 0
        n = len(src)
        while i < n:
            if src[i] == 0xED and i + 3 < n and src[i + 1] == 0xED:
                out += bytes([src[i + 3]]) * src[i + 2]
                i += 4
            else:
                out.append(src[i])
                i += 1
        return bytes(out)

    def read(self, addr):
        """Read a byte from the 64K address space as paged at snapshot time."""
        if addr < 0x4000:
            return None
        if addr < 0x8000:
            return self.banks[5][addr - 0x4000]
        if addr < 0xC000:
            return self.banks[2][addr - 0x8000]
        top = (self.port7ffd & 7) if self.is128 else 0
        return self.banks[top][addr - 0xC000]


# --------------------------------------------------------------------------
# Minimal Z80/Z80N encoder helpers
# --------------------------------------------------------------------------

def w16(v):
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def nextreg(reg, val):              # NEXTREG reg,val
    return bytes([0xED, 0x91, reg, val & 0xFF])


def nextreg_a(reg):                 # NEXTREG reg,A
    return bytes([0xED, 0x92, reg])


def read_nextreg(reg):              # A = NextReg[reg]
    return (b'\x01' + w16(0x243B) +      # LD BC,$243B
            bytes([0x3E, reg]) +         # LD A,reg
            b'\xED\x79' +                # OUT (C),A
            b'\x04' +                    # INC B  -> BC = $253B
            b'\xED\x78')                 # IN A,(C)


def out_port(port, val):            # LD BC,port / LD A,val / OUT (C),A
    return b'\x01' + w16(port) + bytes([0x3E, val & 0xFF]) + b'\xED\x79'


# --------------------------------------------------------------------------
# Tail routine (runs from game memory, restores the CPU state)
# --------------------------------------------------------------------------

def build_tail(snap, org, slot1=None, altrom=False):
    """Return (tail bytes, offset of the NextReg $08 value byte, offset of restore label,
    register block or None).

    slot1 = (page, regblock_addr) selects the compact tail used when a patch keeps
    its code in a RAM page mapped at 0x2000-0x3FFF (MMU slot 1): the border, I and
    interrupt mode are set by the stub instead, the register block lives in that
    page (the stub writes it), and the tail maps the page in after the legacy ROM
    paging writes (which reset slots 0-1 to ROM).
    altrom=True (with slot1): the register block is in the alt ROM (image 1, filled by the
    stub) and the tail enables it with NEXTREG $8C,$80 instead of mapping a RAM page."""
    code = bytearray()

    # Paging: select ROM and bank at C000. On the Next this also remaps MMU6/7,
    # which pages the stub bank out and the game's bank back in.
    if snap.is128:
        v7ffd = snap.port7ffd
        if snap.port1ffd:
            v1ffd = snap.port1ffd                 # +2A/+3 snapshot: use its own value
        else:
            # 128K: 7FFD bit 4 picks the 128 editor ROM (Next ROM 0) or 48 BASIC (ROM 3)
            v1ffd = 0x04 if v7ffd & 0x10 else 0x00
    else:
        v1ffd = 0x04            # ROM 3 (48K BASIC) = 1FFD bit 2 + 7FFD bit 4
        v7ffd = 0x30            # bit 4: ROM select, bit 5: lock paging, bank 0 at C000
    code += out_port(0x1FFD, v1ffd)
    code += out_port(0x7FFD, v7ffd)

    # Peripheral 3 ($08): value is computed by the stub and patched in here.
    code += b'\xED\x91\x08'
    p3_off = len(code)
    code += b'\x00'

    # Display timing, after the paging writes (VHDL 3.01.09: 48K timing does NOT stop
    # 7FFD/1FFD decoding; the 7FFD write above, bit 5, is what locks 48K paging).
    timing = 0x02 if snap.is128 else 0x01
    code += nextreg(0x03, 0x80 | (timing << 4) | 0x03)

    if slot1 is not None:
        if altrom:
            code += nextreg(0x8C, 0x80)                   # alt ROM on for reads (low nibble 0)
        else:
            code += nextreg(0x51, slot1[0])               # patch page into slot 1
    else:
        # Border (port FE bits 0-2; MIC/EAR bits left at 0)
        code += bytes([0x3E, snap.border, 0xD3, 0xFE])    # LD A,b / OUT ($FE),A
        # I register and interrupt mode
        code += bytes([0x3E, snap.i, 0xED, 0x47])         # LD A,i / LD I,A
        code += {0: b'\xED\x46', 1: b'\xED\x56', 2: b'\xED\x5E'}[snap.im]

    restore_off = len(code)
    # LD SP,regblock  (address patched below once the code length is known)
    code += b'\x31\x00\x00'
    sp_fix = len(code) - 2
    # alternate set
    code += b'\xC1\xD1\xE1'          # POP BC / POP DE / POP HL
    code += b'\xD9'                  # EXX
    code += b'\xF1'                  # POP AF
    code += b'\x08'                  # EX AF,AF'
    # index registers and main set
    code += b'\xDD\xE1\xFD\xE1'      # POP IX / POP IY
    code += b'\xC1\xD1\xE1'          # POP BC / POP DE / POP HL
    # R register: set it so it reads correctly when the game's first
    # instruction is fetched. Fetches after LD R,A: POP AF, LD SP, [EI], JP = 3 or 4
    fetches = 4 if snap.iff1 else 3
    r_set = ((snap.r - fetches) & 0x7F) | (snap.r & 0x80)
    code += bytes([0x3E, r_set, 0xED, 0x4F])     # LD A,r / LD R,A
    code += b'\xF1'                              # POP AF
    code += b'\x31' + w16(snap.sp)               # LD SP,game SP
    if snap.iff1:
        code += b'\xFB'                          # EI (takes effect after the JP)
    code += b'\xC3' + w16(snap.pc)               # JP game PC

    regblock_addr = org + len(code) if slot1 is None else slot1[1]
    code[sp_fix:sp_fix + 2] = w16(regblock_addr)

    def pair(hi, lo):
        return bytes([lo, hi])
    regs = bytearray()
    regs += w16(snap.bc_) + w16(snap.de_) + w16(snap.hl_)
    regs += pair(snap.a_, snap.f_)
    regs += w16(snap.ix) + w16(snap.iy)
    regs += w16(snap.bc) + w16(snap.de) + w16(snap.hl)
    regs += pair(snap.a, snap.f)
    if slot1 is not None:
        return bytes(code), p3_off, restore_off, bytes(regs)
    code += regs
    return bytes(code), p3_off, restore_off, None


# --------------------------------------------------------------------------
# Setup stub (runs from the entry bank at C000)
# --------------------------------------------------------------------------

def altrom_fill(org, page, lo, hi, extra=()):
    """Stub code (assembled for address org in the stub page at C000) that fills alt ROM image 1:
    ROM3 (48K BASIC) copied 0x0000-0x3FFF in write mode ($8C bits 7+6), then bytes lo..hi-1 of
    RAM page `page` (the patch image of 0x2000-0x3FFF) written over it, then each (addr, off, n) of
    `extra` (patch.altrom0: n bytes at page offset off -> addr, e.g. a JP into the hooks at a ROM
    address below 0x2000; the page offset is one the lo..hi copy does not use); $8C is left at 0 (the tail
    enables reads). The legacy 1FFD/7FFD writes that select ROM3 remap MMU slots 6/7 (where the
    stub runs), so the routine runs from an alias of the stub page in slot 4, with the patch page
    in slot 5 as the copy source, restores slots 6/7 and jumps back; no stack use in between."""
    c = bytearray()
    c += nextreg(0x54, STUB_PAGE_LO) + nextreg(0x55, page)
    c += b'\xC3' + w16(org + len(c) + 3 - 0x4000)               # JP into the slot-4 alias
    c += read_nextreg(0x08) + b'\xF6\x80' + nextreg_a(0x08)     # OR $80: unlock 7FFD paging
    c += out_port(0x1FFD, 0x04) + out_port(0x7FFD, 0x10)         # ROM3 (alt image 1)
    c += nextreg(0x8C, 0xC0)                                     # alt ROM write mode
    c += b'\x21\x00\x00\x11\x00\x00\x01\x00\x40\xED\xB0'       # LD HL,0 / LD DE,0 / LD BC,$4000 / LDIR
    c += b'\x21' + w16(0xA000 + lo - 0x2000) + b'\x11' + w16(lo) + b'\x01' + w16(hi - lo) + b'\xED\xB0'
    for addr, off, n in extra:
        c += b'\x21' + w16(0xA000 + off) + b'\x11' + w16(addr) + b'\x01' + w16(n) + b'\xED\xB0'
    c += nextreg(0x8C, 0x00)
    c += nextreg(0x56, STUB_PAGE_LO) + nextreg(0x57, STUB_PAGE_HI)
    c += b'\xC3' + w16(org + len(c) + 3)                          # JP back to C000 space
    c += nextreg(0x54, 4) + nextreg(0x55, 5)                      # bank 2 back in slots 4/5
    return bytes(c)


def build_stub(snap, tail, tail_addr, p3_off, force50, setup_call=None, slot1=None, regs=None, altrom=None,
               printer=None, altrom0=()):
    code = bytearray()
    code += b'\xF3'                          # DI
    code += b'\x31' + w16(STUB_SP)           # LD SP,$FFFE
    code += nextreg(0x07, 0x00)              # CPU 3.5MHz

    # Peripheral 2 ($06): clear bit 4 (DivMMC automatic paging)
    code += read_nextreg(0x06) + b'\xE6\xEF' + nextreg_a(0x06)       # AND $EF
    # Unmap DivMMC memory: OUT ($E3),0
    code += b'\xAF\xD3\xE3'                                           # XOR A / OUT ($E3),A

    if force50:
        # Peripheral 1 ($05): clear bit 2 -> 50Hz
        code += read_nextreg(0x05) + b'\xE6\xFB' + nextreg_a(0x05)   # AND $FB

    # Sprites, Layer 2 and hardware IM2 off (normally already off after NEXLOAD)
    code += nextreg(0x15, 0x00)
    code += out_port(0x123B, 0x00)
    code += nextreg(0xC0, 0x00)

    # 128K: restore AY registers now (the ports are always available)
    if snap.is128:
        for reg, val in enumerate(snap.ay_regs):
            code += out_port(0xFFFD, reg)
            code += out_port(0xBFFD, val)
        code += out_port(0xFFFD, snap.ay_last)

    # optional patch setup routine (e.g. sprite pattern upload), in the stub bank
    if setup_call is not None:
        code += b'\xCD' + w16(setup_call)       # CALL setup

    if slot1 is not None:
        # compact tail: border, I and interrupt mode are set here, and the register
        # block is written into the slot-1 patch page (mapped at E000 for the copy)
        code += bytes([0x3E, snap.border, 0xD3, 0xFE])          # LD A,b / OUT ($FE),A
        code += bytes([0x3E, snap.i, 0xED, 0x47])               # LD A,i / LD I,A
        code += {0: b'\xED\x46', 1: b'\xED\x56', 2: b'\xED\x5E'}[snap.im]
        code += nextreg(0x57, slot1[0])
        regs_src_fix = len(code) + 1
        code += b'\x21\x00\x00'                                # LD HL,regs (patched)
        code += b'\x11' + w16(0xE000 + slot1[1] - 0x2000)       # LD DE,page copy
        code += b'\x01' + w16(len(regs))                        # LD BC,len
        code += b'\xED\xB0'                                     # LDIR
        code += nextreg(0x57, STUB_PAGE_HI)
        if altrom is not None:                  # (lo, hi): patch bytes of the page for the alt ROM
            code += altrom_fill(STUB_ORG + len(code), slot1[0], altrom[0], altrom[1], altrom0)

    # Peripheral 3 ($08) value for the tail:
    #   keep bit 5 (AY stereo) and bit 4 (internal speaker) from the current setting,
    #   bit 7: 1 = clear the 7FFD lock (128K unless snapshot locked it) / 0 = no change
    #          (48K stays locked by the tail's 7FFD write, bit 5; VHDL 3.01.09)
    #   bit 6: 0 = contention enabled
    #   bits 3-1: 0 (DACs, port FF read, TurboSound off)
    #   bit 0: issue 2 keyboard from the snapshot
    extra = snap.issue2
    if snap.is128 and not (snap.port7ffd & 0x20):
        extra |= 0x80
    code += read_nextreg(0x08) + b'\xE6\x30' + bytes([0xF6, extra])   # AND $30 / OR extra

    # printer (opt-in, 48K): put the snapshot's printer buffer 0x5B00-0x5BFF back. NextZXOS keeps
    # its paging routines and system variables there (SWAP 0x5B00.., BANKM 0x5B5C, BANK678 0x5B67,
    # OLDSP / TSTACK) and the .nex loader writes them AFTER loading bank 5, so a 48K game that keeps
    # data there (Match Day: icons, team names) starts with it overwritten (hardware 2026-10-20).
    prn_fix = None
    if printer is not None:
        prn_fix = len(code) + 1
        code += b'\x21\x00\x00'                  # LD HL,copy (patched)
        code += b'\x11' + w16(0x5B00)             # LD DE,0x5B00
        code += b'\x01' + w16(len(printer))       # LD BC,256
        code += b'\xED\xB0'                      # LDIR

    # copy tail into place, then patch the $08 value
    src_label_fix = len(code) + 1
    code += b'\x21\x00\x00'                      # LD HL,tail source (patched)
    code += b'\x11' + w16(tail_addr)             # LD DE,tail address
    code += b'\x01' + w16(len(tail))             # LD BC,length
    # A holds the $08 value; LDIR does not change A
    code += b'\xED\xB0'                          # LDIR
    code += b'\x32' + w16(tail_addr + p3_off)    # LD (tail+p3),A
    code += b'\xC3' + w16(tail_addr)             # JP tail
    src = STUB_ORG + len(code)
    code[src_label_fix:src_label_fix + 2] = w16(src)
    code += tail
    if slot1 is not None:
        code[regs_src_fix:regs_src_fix + 2] = w16(STUB_ORG + len(code))
        code += regs
    if printer is not None:
        code[prn_fix:prn_fix + 2] = w16(STUB_ORG + len(code))
        code += printer
    return bytes(code)


# --------------------------------------------------------------------------
# Tail placement
# --------------------------------------------------------------------------

def choose_tail_addr(snap, length, requested, avoid_printer_buffer=False):
    """48K and 128K: the tail must end below 0xC000. The stub copies it while its own bank 10 is at
    C000, and the tail's first 7FFD write remaps slots 6/7, so a tail at 0xC000-0xFFFF vanishes from
    under the PC (48K too: El Capitan Trueno, tail at 0xFF97). Refused even with --tail; never chosen
    by default (boot simulation confirmed the failure)."""
    if requested is not None:
        if requested + length > 0xC000:
            raise ValueError('--tail 0x%04X: the start-up tail must end below 0xC000 (the top 16K '
                             'is swapped out by the tail\'s own 7FFD write); %s' % (requested, _TAIL_HINT))
        return requested, 'requested with --tail'
    if not avoid_printer_buffer and (not snap.is128 or 0x5B00 + length <= 0x5C00):
        if all(snap.read(a) == 0 for a in range(0x5B00, 0x5B00 + length)):
            return 0x5B00, 'printer buffer (0x5B00), all zero in the snapshot'
    addr = snap.sp - length - 16
    if addr >= 0x4000 + 6912 and addr + length <= 0xC000:
        return addr, 'below the stack pointer (0x%04X)' % snap.sp
    if snap.sp >= 0xC000:
        raise ValueError('snapshot with SP=0x%04X in the paged top 16K: no automatic place for the '
                         'start-up tail; %s' % (snap.sp, _TAIL_HINT))
    raise ValueError('could not find a place for the start-up tail; use --tail ADDR')


_TAIL_HINT = ('use --tail ADDR in 0x5B00-0xBFFF on memory the game never reads before writing '
              '(access scan: e.g. a zeroed printer buffer, dead stack, or a back buffer the game '
              'redraws; Rainbow Islands: 0x9F00)')


# --------------------------------------------------------------------------
# NEX writer
# --------------------------------------------------------------------------

BANK_FILE_ORDER = [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112))


def write_nex(path, snap, banks):
    header = bytearray(512)
    header[0:4] = b'Next'
    header[4:8] = b'V1.2'
    header[8] = 0                       # RAM required: 768K
    header[9] = len(banks)              # number of 16K banks
    header[10] = 0                      # no loading screen
    header[11] = snap.border
    header[12:14] = w16(STUB_SP)
    header[14:16] = w16(STUB_ORG)       # PC: start of the stub in the entry bank
    for b in banks:
        header[18 + b] = 1
    header[134] = 0                     # reset NextRegs to defaults before starting
    header[135:138] = bytes([3, 0, 0])  # minimum core version 3.00.00
    header[139] = STUB_BANK             # entry bank, mapped at C000
    out = bytearray(header)
    for b in BANK_FILE_ORDER:
        if b in banks:
            data = banks[b]
            out += data + bytes(16384 - len(data))
    open(path, 'wb').write(out)
    return len(out)


ALLOW_60HZ = False          # set by `nexclash.py ... --allow-60hz`: no build forces 50 Hz then


def convert(src, dst, tail_req=None, force50=True, quiet=False, patch=None, keep_printer_buffer=False):
    """patch (optional) is an object with:
         apply(snap)         modify snap.banks (pokes) before conversion
         stub_extra          bytes placed in the stub bank at STUB_ORG+0x1000 (setup routine)
         setup_call          address to CALL from the stub (or None)
         hook_page_data      bytes for the stub bank's upper 8K page (or b'')
         extra_banks         {bank: bytes}
         uses_printer_buffer True if the tail must not go at 0x5B00
         keep_printer_buffer (optional) True: the stub restores the snapshot's 0x5B00-0x5BFF after
                             NEXLOAD (48K games that keep data there; build_stub `printer`)
    """
    force50 = force50 and not ALLOW_60HZ
    snap = Z80Snapshot(src)
    if patch is not None:
        patch.apply(snap)
    avoid = bool(patch is not None and patch.uses_printer_buffer) or keep_printer_buffer
    slot1 = getattr(patch, 'slot1', None) if patch is not None else None
    altrom = getattr(patch, 'altrom', None) if patch is not None else None
    probe = build_tail(snap, 0x8000, slot1, altrom is not None)[0]
    if tail_req is None and patch is not None and getattr(patch, 'tail_addr', None) is not None:
        tail_req = patch.tail_addr
    tail_addr, why = choose_tail_addr(snap, len(probe), tail_req, avoid)
    max_tail = getattr(patch, 'max_tail', None) if patch is not None else None
    if max_tail is not None and len(probe) > max_tail:
        raise ValueError('start-up tail is %d bytes but only %d are free' % (len(probe), max_tail))
    tail, p3_off, restore_off, regs = build_tail(snap, tail_addr, slot1, altrom is not None)
    printer = None
    if keep_printer_buffer or getattr(patch, 'keep_printer_buffer', False):
        if snap.is128:
            raise ValueError('keep_printer_buffer is for 48K snapshots')
        printer = bytes(snap.banks[5][0x1B00:0x1C00])
    stub = build_stub(snap, tail, tail_addr, p3_off, force50,
                      patch.setup_call if patch is not None else None, slot1, regs, altrom, printer,
                      tuple(getattr(patch, 'altrom0', ())) if patch is not None else ())
    if len(stub) > 0x1000:
        raise ValueError('stub too long')

    banks = dict(snap.banks)
    bank10 = bytearray(16384)
    bank10[0:len(stub)] = stub
    if patch is not None:
        bank10[0x1000:0x1000 + len(patch.stub_extra)] = patch.stub_extra
        bank10[0x2000:0x2000 + len(patch.hook_page_data)] = patch.hook_page_data
        banks.update(patch.extra_banks)
    banks[STUB_BANK] = bytes(bank10)
    size = write_nex(dst, snap, banks)

    if not quiet:
        kind = '128K' if snap.is128 else '48K'
        print('Snapshot : %s (version %d, %s)' % (os.path.basename(src), snap.version, kind))
        print('  PC=%04X SP=%04X  IM %d  interrupts %s  border %d' % (
            snap.pc, snap.sp, snap.im, 'enabled' if snap.iff1 else 'disabled', snap.border))
        if snap.iff1 != snap.iff2:
            print('  note: IFF1 and IFF2 differ in the snapshot; both are set to IFF1')
        print('Tail     : %d bytes at 0x%04X-0x%04X - %s' % (
            len(tail), tail_addr, tail_addr + len(tail) - 1, why))
        print('           these bytes stay in memory; the game must not use them')
        print('Stub     : %d bytes in bank %d' % (len(stub), STUB_BANK))
        if patch is not None:
            print('Patch    : %s' % getattr(patch, 'name', 'applied'))
        print('Video    : %s' % ('50Hz forced' if force50 else 'left as configured'))
        print('Wrote    : %s (%d bytes, %d banks)' % (dst, size, len(banks)))
    return snap, tail_addr, tail, restore_off


def main():
    ap = argparse.ArgumentParser(description='Convert a .z80 snapshot to a ZX Spectrum Next .nex file.')
    ap.add_argument('z80', help='input .z80 snapshot')
    ap.add_argument('-o', '--output', help='output .nex file (default: same name with .nex)')
    ap.add_argument('--tail', type=lambda s: int(s, 0), default=None,
                    help='address for the start-up tail (e.g. 0x5B00); must be unused by the game; '
                         '128K: must end below 0xC000')
    ap.add_argument('--allow-60hz', action='store_true',
                    help='do not force 50Hz video (the game will run faster at 60Hz)')
    args = ap.parse_args()
    dst = args.output or os.path.splitext(args.z80)[0] + '.nex'
    try:
        convert(args.z80, dst, args.tail, not args.allow_60hz)
    except (ValueError, OSError) as e:
        sys.exit('Error: %s' % e)


if __name__ == '__main__':
    main()
