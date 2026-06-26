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

"""Logic-file discovery and solution derivation for TensileCreateLibrary.

Houses the per-arch fallback-placeholder rename helpers, the unique-kernel
object derivation, and the logic-load + per-arch merge + reindex core
(generateLogicDataAndSolutions). Populated incrementally by the NBA-*
decomposition; names are re-imported back into Run.py so existing imports keep
resolving.
"""

import copy

from Tensile.SolutionLibrary import PlaceholderLibrary


def _renameFallbackPlaceholders(node, arch: str) -> None:
    """Walk a library tree, appending "_<arch>" to fallback PlaceholderLibrary names.

    Mutates `filenamePrefix` on every PlaceholderLibrary leaf whose existing
    prefix already encodes a fallback (i.e. came from the merged-in fallback
    master library and therefore ends with "_fallback") and which has not yet
    been arch-suffixed. Idempotent: a prefix already ending in "_<arch>"
    is left alone so a second pass cannot double-suffix.
    """
    if node is None:
        return
    if isinstance(node, PlaceholderLibrary):
        if "_fallback" in node.filenamePrefix and not node.filenamePrefix.endswith("_" + arch):
            node.filenamePrefix = node.filenamePrefix + "_" + arch
        return
    rows = getattr(node, "rows", None)
    if rows:
        for row in rows:
            _renameFallbackPlaceholders(row.get("library"), arch)
    mapping = getattr(node, "mapping", None)
    if mapping:
        for child in mapping.values():
            _renameFallbackPlaceholders(child, arch)


def renameFallbacksPerArch(masterLibraries) -> None:
    """Make merged-in fallback lazy-library filenames arch-specific.

    `MasterSolutionLibrary.merge` aliases the same fallback lazy library across
    every per-arch master that absorbs it (keys collide on the un-suffixed
    "_fallback" name). That alias means the per-arch *_fallback.dat files are
    written with overlapping filenames carrying different solution-index spaces,
    and the per-arch Mapping write loop's `name.endswith("_<arch>")` filter drops
    every fallback entry — runtime then can't resolve fallback-served dtypes.

    Per-arch deep-copy here splits the alias and arch-suffixes both the
    `lazyLibraries` dict keys and the matching PlaceholderLibrary nodes inside
    the master library tree, so:
      - on-disk filenames diverge (no overlay collision),
      - the per-arch Mapping filter matches "_fallback_<arch>" naturally, and
      - each arch keeps its own re-indexed copy of the fallback solutions.
    """
    for arch in list(masterLibraries.keys()):
        master = copy.deepcopy(masterLibraries[arch])
        masterLibraries[arch] = master
        renamed = {}
        for name, lib in master.lazyLibraries.items():
            if "_fallback" in name and not name.endswith("_" + arch):
                renamed[name + "_" + arch] = lib
            else:
                renamed[name] = lib
        master.lazyLibraries = renamed
        _renameFallbackPlaceholders(master.library, arch)
