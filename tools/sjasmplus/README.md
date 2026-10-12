# sjasmplus - the pinned assembler

Hook sources (asm/*.asm) are assembled with exactly one sjasmplus version, pinned in
`pin.json` (now 1.24.0, tag v1.24.0, commit d379eeac). Builds never need it: the profiles in
docs/profiles keep the assembled hex. You need it only to change or add hook code.

## Use
    python tools/asm2profile.py <engine>          reassemble asm/<engine>_hooks.asm -> profile hex
    python tools/asm2profile.py --check --all     every profile = what the pinned version makes
    python tools/sjasmplus/sjasm.py               path of the pinned sjasmplus

`sjasm.py` uses `sjasmplus-1.24.0-linux-x86_64` here (static, checked by SHA-256 and
--version). Elsewhere (macOS, Windows, ARM) or if it will not run, it builds the pinned tag
from source into ~/.cache/nexclash/ (~15 s; needs git, make, a C++ compiler). Any other
version is refused. Both paths give byte-identical output (checked 2026-10-12, all four hook
engines).

Dizzy V (`asm/dizzy5_hooks.asm`) has no hooks section: dizzy5.py emits the bytes itself and
`python selftest.py --tools` checks the pinned assembler's output equals them.

## New engine convention
- `SAVEBIN "<prefix>_<key>.bin",...` for each block: the tool stores it as hooks[<key>].
- The profile's hooks section names the source: `"source": "asm/<engine>_hooks.asm"`.
- hooks.syms lists the symbols the engine reads; add one with `--add-sym NAME`.

## Upgrading sjasmplus (maintainers, on a branch)
1. Build the new tag: `git clone --depth 1 --branch vX.Y.Z https://github.com/z00m128/sjasmplus`
   then `make USE_LUA=0 LDFLAGS="-static -s"`.
2. Point a copy of pin.json at it (version, tag, commit, binary name, sha256) and run
   `python tools/asm2profile.py --check --all`.
3. IDENTICAL for every engine: commit the new binary + pin.json, delete the old binary, and
   `python tools/asm2profile.py --all` (updates assembled_with). Note it in docs/VERIFICATION.md.
4. Any DIFFERS: the assembler changed meaning. Keep the old pin, or regenerate the affected
   profiles - that changes those games' .nex MD5s: full selftest, re-baseline, hardware retest.

Licence: sjasmplus is BSD-3-Clause (LICENSE-sjasmplus.md); redistributed unmodified.
