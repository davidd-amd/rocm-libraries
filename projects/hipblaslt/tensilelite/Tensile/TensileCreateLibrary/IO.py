################################################################################
#
# Copyright (C) 2022-2025 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################

"""Disk and serialization layer for TensileCreateLibrary.

Houses the library path layout (libraryRoot/libraryDir/_baseArchs/
tensileLibraryFile), the stinky-asm ELF verification helpers, the
mem-compression helpers, the assembly/helper disk-write primitives, and the
static-file copier. Populated incrementally by the NBA-* decomposition; names
are re-imported back into Run.py so existing imports keep resolving.
"""

import os
import pickle
import zlib

from pathlib import Path
from typing import Collection, List, Union

from Tensile.Common import IsaVersion, printExit
from Tensile.Common.Architectures import isaToGfx
from Tensile.Common.GlobalParameters import globalParameters
from Tensile.verify_stinky_comment_vs_elf_text import verify_stinky_paths


def libraryRoot(outputPath: Union[str, Path]) -> Path:
    """The library/ root directory under outputPath.

    Used as the dispatch root by builders that fan kernels out into per-base
    subdirectories at write time.
    """
    return Path(outputPath) / "library"


def libraryDir(outputPath: Union[str, Path], arch: str) -> Path:
    """The per-base-arch library subdirectory: <outputPath>/library/<base>/.

    Target features (xnack+/xnack-, sramecc, etc.) are stripped from the path —
    variants of one base co-locate in one directory, disambiguated by kernel
    filename suffix. Layout matches the runtime probe in tensile_host.cpp which
    strips at the first colon before looking up the subdirectory.
    """
    return libraryRoot(outputPath) / arch.split(":")[0]


def _baseArchs(archs: Collection[str]) -> List[str]:
    """Unique base archs (xnack/sramecc stripped), sorted for determinism."""
    return sorted({a.split(":")[0] for a in archs})


def tensileLibraryFile(outputPath: Union[str, Path], arch: str, library_format: str = "msgpack") -> Path:
    """The canonical TensileLibrary path for one base arch under outputPath.

    Composes ``<outputPath>/library/<base>/TensileLibrary.<ext>`` where ``ext``
    is ``.yaml`` for the YAML format and ``.dat`` for msgpack. The base arch
    is derived from ``arch`` via the same colon-strip rule as ``libraryDir``,
    so cooked variants like ``gfx942:sramecc+:xnack+`` resolve to the same
    file as the bare ``gfx942`` arch.

    This is the file that ``writeClientConfigIni``'s ``libraryFile`` argument
    must point to under the per-base layout. Callers (BenchmarkProblems'
    cache-hit branch, ClientWriter's benchmark-parameters helper) reach for
    it from different parts of the pipeline; the helper keeps the
    "library/<base>/TensileLibrary.<ext>" naming convention in one place so
    future format/extension changes touch a single call site.
    """
    ext = ".yaml" if library_format == "yaml" else ".dat"
    return libraryDir(outputPath, arch) / f"TensileLibrary{ext}"


def _stinky_asm_verify_wanted(isa: IsaVersion) -> bool:
    """Return True if asm/.o Stinky size check should run for this kernel.

    Requires ``CheckASMCodeSize`` and gfx1250. When True, callers should avoid joblib for
    write+assemble so logs stay on one process.
    """
    return bool(globalParameters["CheckASMCodeSize"]) and isaToGfx(isa) == "gfx1250"


def _stinky_out(msg: str) -> None:
    """Emit one user-visible log line for Stinky verify.

    Writes to stderr via ``os.write(2, ...)``. Under pytest-xdist, worker stdout may be
    hidden; stderr often still appears in the terminal.
    """
    try:
        os.write(2, (msg + "\n").encode("utf-8", errors="replace"))
    except OSError:
        pass


def _verify_stinky_asm_comment_vs_elf_text(s_path: Path, o_path: Path, kernel_base: str) -> None:
    """After assembling ``s_path`` → ``o_path``, verify Stinky vs ELF ``.text``.

    Call only when ``_stinky_asm_verify_wanted(isa)`` is True. Uses ``verify_stinky_comment_vs_elf_text``
    (``readelf`` / ``llvm-readelf``; ``ROCM_PATH``, ``LLVM_BIN``, or ``PATH``). Forwards messages
    through ``_stinky_out``. Exits via ``printExit`` on mismatch (1) or tool/readelf error (2).

    Args:
        s_path: Path to the generated ``.s`` file.
        o_path: Path to the assembled ``.o`` file.
        kernel_base: Short name for messages (usually the asm stem).
    """
    _stinky_out(f"CheckASMCodeSize: running verify for {kernel_base}")
    try:
        code, out_s, err_s = verify_stinky_paths(s_path, o_path)
    except Exception as ex:
        printExit(f"CheckASMCodeSize: could not run verifier for {kernel_base}: {ex}")
    if out_s:
        for line in out_s.splitlines():
            _stinky_out(line)
    if err_s:
        for line in err_s.splitlines():
            _stinky_out(line)
    if code == 2:
        printExit(f"CheckASMCodeSize: verifier error for {kernel_base}")
    if code == 1:
        printExit(
            f"CheckASMCodeSize: STINKY_TOTAL_INST_BYTES vs ELF .text mismatch for {kernel_base}"
        )
    if code == 0:
        out = (out_s or "") + (err_s or "")
        matched = "OK STINKY" in out
        if matched:
            _stinky_out(
                f"CheckASMCodeSize: OK STINKY_TOTAL_INST_BYTES vs ELF .text match for {kernel_base}"
            )


def memCompress(obj):
    return zlib.compress(pickle.dumps(obj))

def memDecompress(byt):
    return pickle.loads(zlib.decompress(byt))
