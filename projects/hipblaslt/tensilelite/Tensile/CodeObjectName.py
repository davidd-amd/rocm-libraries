################################################################################
#
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
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

from Tensile.Properties import Predicate
from Tensile.Contractions import ProblemType
from Tensile.Common.Architectures import supportsChipIdPredicate


def codeObjectFileBaseName(d: dict, useLazyLibraryLoading: bool = True):
    """Compute the code-object (lazy placeholder) library base name from raw
    logic-file metadata, WITHOUT materializing solution objects.

    This is the cheap, YAML-only twin of the placeholder-name assembled across
    ``SolutionLibrary.MasterSolutionLibrary.FromOriginalState`` (the ``selection``,
    ``predicates``, ``performanceMetric``, ``operationIdentifier`` and
    ``hardware`` levels). It MUST stay byte-for-byte in sync with that assembly:
    the fused build pipeline groups logic files by this name to decide which land
    in the same code object. Kept reconciled with the branch naming (compute-input
    A/B split, MX blocks, sparse metadata layout, chip-id hardware suffix).

    Args:
        d: metadata with keys ``ProblemType``, ``PerfMetric``, ``ArchitectureName``,
           ``CUCount`` and optionally ``DeviceNames``.
        useLazyLibraryLoading: emit the lazy naming convention (the only mode used
           by the pipeline).

    Returns:
        The placeholder library base name string.
    """
    placeholderName = "TensileLibrary"
    problemType = ProblemType.FromOriginalState(d["ProblemType"])
    if useLazyLibraryLoading:
        # --- selection(): datatypes + problem features (SolutionLibrary @492-539)
        computeInputTypeStr = str(problemType.computeInputTypeA)
        if problemType.computeInputTypeA != problemType.computeInputTypeB:
            computeInputTypeStr = str(problemType.computeInputTypeA) + str(problemType.computeInputTypeB)
        placeholderName += '_' + str(problemType.aType) + str(problemType.bType)
        placeholderName += '_' + str(problemType.cType) + computeInputTypeStr
        if problemType.activationType != 'none':
            if str(problemType.activationType).upper() == 'ALL':
                placeholderName += "_A"
            elif str(problemType.activationType).upper() == 'HIPBLASLT_ALL':
                placeholderName += "_HA"
            else:
                placeholderName += "_%s" % str(problemType.activationType).upper()

        if problemType.mxBlockA:
            placeholderName += ('_MXA' + str(problemType.mxTypeA) + 'B' + str(problemType.mxBlockA))
        if problemType.mxBlockB:
            placeholderName += ('_MXB' + str(problemType.mxTypeB) + 'B' + str(problemType.mxBlockB))

        if problemType.swizzleTensorA:
            placeholderName += '_STA'
        if problemType.swizzleTensorB:
            placeholderName += '_STB'

        if problemType.useBias:
            placeholderName += '_Bias'
        if problemType.useE:
            placeholderName += '_Grad' if problemType.useGradient else '_Aux'
        if problemType.groupedGemm:
            placeholderName += "_GG"
        else:
            placeholderName += "" if problemType.stridedBatched else "_GB"  # legacy
        if problemType.useScaleAB == "Scalar":
            placeholderName += '_SAB'
        elif problemType.useScaleAB == "Vector":
            placeholderName += '_SABV'
        if problemType.useScaleCD:
            placeholderName += '_SCD'
        if problemType.useScaleAlphaVec:
            placeholderName += '_SAV'
        if problemType.sparse:
            placeholderName += '_SPB' if problemType.sparse == 2 else '_SPA'
            placeholderName += "ML" + str(problemType.metadataLayout)
        if not problemType.f32XdlMathOp.isSingle() and problemType.computeInputTypeA.isSingle() and problemType.computeInputTypeB.isSingle():
            placeholderName += '_M' + str(problemType.f32XdlMathOp)
        if problemType.supportDeviceUserArguments:
            placeholderName += '_UA'

        # --- predicates(): batch/type discriminators (SolutionLibrary @451)
        placeholderName += problemType.placeholderStr(includeBatch=True, includeType=True)

        # --- performanceMetric() (SolutionLibrary @431-439)
        # Match parseLibraryLogicList truthiness: an absent PerfMetric arrives as
        # None (getCoFileNames reads a fixed index), which parseLibraryLogicList
        # treats as "no PerfMetric" (it sets the key only `if len(data) > 10 and
        # data[10]`). Coalesce None/falsy to the DeviceEfficiency default so the
        # name matches SolutionLibrary rather than emitting a spurious "_None".
        perfMetric = d.get("PerfMetric") or "DeviceEfficiency"
        if perfMetric != "DeviceEfficiency":
            predicate = Predicate(tag=perfMetric)
        else:
            predicate = Predicate(tag="TruePred")
        if predicate.tag != "TruePred":
            placeholderName += "_" + predicate.tag

        # --- operationIdentifier() (SolutionLibrary @426)
        operationID = problemType.operationIdentifier
        placeholderName += "_" + operationID

        # --- hardware(): CU count, optional chip-id, device (SolutionLibrary @363-379)
        devicePart = d["ArchitectureName"]
        cuCount = d["CUCount"]
        pciChipId = d.get("DeviceNames", None)
        if cuCount:
            placeholderName += "_CU" + str(cuCount)
        if pciChipId and supportsChipIdPredicate(devicePart):
            if isinstance(pciChipId, list):
                chipIdStr = '-'.join([str(x).replace('Device ', '').strip() for x in pciChipId])
            else:
                chipIdStr = str(pciChipId).replace('Device ', '').strip()
            placeholderName += "_ID" + chipIdStr
        placeholderName += "_" + str(devicePart)

    return placeholderName
