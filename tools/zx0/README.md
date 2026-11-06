# ZX0 - the compressor the .nxc packager runs

`nexclash/nxc.py make` (the vendored .nxc packager) compresses every block with Einar Saukas's
ZX0 compressor, format version 2. The sources here are upstream's, unmodified, from commit
ecde3a2 (pin.json; BSD-3-Clause, LICENSE-zx0). Applying or listing a .nxc never needs it.
No binary is kept in Git (owner's decision, 2026-11-05): nexclash builds one, or you supply one.

## How nexclash finds it (nexclash/nxcout.py `zx0_dir`)
1. `$NXC_ZX0_DIR`, if it holds a `zx0`.
2. A zx0 built or copied earlier into `~/.cache/nexclash/zx0-ecde3a2/`.
3. Windows: `tools/zx0/zx0.exe`, if you downloaded it (below; checked by SHA-256, Git ignores it).
4. These sources built once with a C compiler (`$CC`, `cc`, `gcc` or `clang`, ~1 s) into that folder.
Every binary must give pin.json's golden output before it is used. With none of these, the build
keeps its .nex files and the report says why.

## Building it yourself
    cc -O2 -o zx0 zx0.c optimize.c compress.c memory.c      (in tools/zx0; gcc or clang the same)
then set `NXC_ZX0_DIR` to the folder that holds `zx0`. nexclash does this itself on first use.

## Windows without a C compiler
Download upstream's own build from the pinned commit,
https://github.com/einar-saukas/ZX0/raw/ecde3a2ae05061fe06469ed46df81a33b7de7d86/win/zx0.exe
(repository: https://github.com/einar-saukas/ZX0), and save it as `tools/zx0/zx0.exe`. Its SHA-256 must
be pin.json's `windows_binary_sha256`.
