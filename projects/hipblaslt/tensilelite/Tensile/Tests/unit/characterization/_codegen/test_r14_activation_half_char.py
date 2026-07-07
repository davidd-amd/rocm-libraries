################################################################################
# Copyright (C) 2026 Advanced Micro Devices, Inc. All rights reserved.
# SPDX-License-Identifier: MIT
################################################################################
"""R14 -- half-precision Activation getModule emit (F7 fixed).

Tensile/Activation.py's half/PK activation arms referenced names never imported
(SelectBit, UnusedBit, VMaxF16, SDWAModifiers, VOP3PModifiers) and used `coef`
before assignment in the half gelu branch, so getModule(DataType('h'), ...) raised
NameError / UnboundLocalError.

With the F7 fix (add the five missing rocisa imports and hoist the gelu `coef`
assignment), the half activations build clean Modules. This pins the now-working
behavior for clippedrelu/leakyrelu/clamp/gelu/geluscaling, covering ~+165
previously-uncovered Activation.py half-path lines (incl. the half gelu/tanh/exp
chain). See work/char-findings.md F7.

Note: archCaps must be populated (real init + setKernel) -- a bare rocIsa.init
leaves archCaps empty and gelu/geluscaling (via tanh->exp) hit a pre-existing
TransOpWait KeyError unrelated to the F7 import/coef fix.
"""

import shutil

import pytest

pytestmark = pytest.mark.unit

_FIXABLE = ["clippedrelu", "leakyrelu", "clamp", "gelu", "geluscaling"]


def _init_gfx942():
    import rocisa
    asm = shutil.which("amdclang++") or "/usr/bin/amdclang++"
    ri = rocisa.rocIsa.getInstance()
    ri.init((9, 4, 2), asm)
    ri.setKernel((9, 4, 2), 64)


def _build_half_modules():
    _init_gfx942()
    from Tensile.Activation import ActivationModule, ActivationType
    from Tensile.Common.DataType import DataType
    return {
        act: str(ActivationModule().getModule(DataType("h"), ActivationType(act), "0", "0"))
        for act in _FIXABLE
    }


def test_r14_activation_half_emits_modules():
    """Each fixable half activation builds a non-empty Module (no NameError/UnboundLocalError)."""
    mods = _build_half_modules()
    for act in _FIXABLE:
        assert mods[act] and len(mods[act]) > 0, f"{act} produced an empty module"


def test_r14_activation_half_golden(snapshot):
    """Golden: per-activation half Module emit (flips if the half codegen changes)."""
    mods = _build_half_modules()
    assert mods == snapshot
