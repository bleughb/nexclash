# ZX0 - the compressor the .nxc packager runs

`nexclash/nxc.py make` (the vendored .nxc packager) compresses every block with Einar Saukas's
ZX0 compressor, format version 2. The sources here are upstream's, unmodified, from commit
ecde3a2 (pin.json; BSD-3-Clause, LICENSE-zx0). Applying or listing a .nxc never needs it.

## How nexclash finds it (nexclash/nxcout.py `zx0_dir`)
1. `$NXC_ZX0_DIR`, if it holds a `zx0`.
2. Windows: `zx0.exe` here (upstream's own build from that commit, checked by SHA-256).
3. Elsewhere: these sources built once with the system C compiler (`cc`, `gcc` or `clang`, ~1 s)
   into `~/.cache/nexclash/zx0-ecde3a2/`.
Every binary must give pin.json's golden output before it is used. With none of these, the build
keeps its .nex files and the report says why no .nxc was made.

`zx0.exe` stays in Git for now (2026-11-05), as the pinned assembler does (tools/sjasmplus): source, BSD notice,
SHA-256 and the golden output are checked before use (selftest --tools). Shipping it only in the release zip
instead is Dean's call; until he decides, keep the pin and the golden check.
