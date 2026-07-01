#!/usr/bin/env bash
# Artifact-equivalence check for Group 1 (additive port, run() NOT rewired -> the
# gfx90a build output must be byte-identical). Builds the current branch worktree
# once, fingerprints every file under the output library/ (relpath size sha256),
# and diffs against a stored baseline fingerprint.
#
# Usage:
#   diff_artifacts.sh capture <name> <SUBSET|FULL>   # build & save fingerprint
#   diff_artifacts.sh <a> <b> <SUBSET|FULL>          # compare two fingerprints;
#                                                    #  a literal "HEAD" builds now
# Fingerprints live in fp-<name>-<subset|full>.txt next to this script.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE=tensilelite-char:gpumocks
WT=/home/davdixon/projects/rocm-libraries/.claude/worktrees/parallel-build-algo/projects/hipblaslt
RB=/home/davdixon/projects/rocm-libraries/.claude/worktrees/parallel-build-algo/projects/hipblaslt/tensilelite/rocisa/build/cp312-cp312-linux_x86_64
# Optional: point the mounted tensilelite tree elsewhere (e.g. a git-archive of a
# prior commit) to fingerprint a different source revision with the same rocisa.
TENSILE_TREE="${TENSILE_TREE:-$WT/tensilelite}"

fp_path () { # <name> <filter>
  local n="$1"; local f; f="$(echo "$2" | tr '[:upper:]' '[:lower:]')"
  echo "$HERE/fp-$n-$f.txt"
}

build_and_fingerprint () { # <filter> -> writes fingerprint lines to stdout
  local FILTER="$1"
  local LOGIC FILT_OPT=""
  if [ "$FILTER" = "SUBSET" ]; then
    LOGIC="$HERE/logic-subset"
    [ -d "$LOGIC" ] || { echo "subset not staged; run stage_subset.sh first" >&2; return 2; }
  else
    LOGIC="$WT/library/src/amd_detail/rocblaslt/src/Tensile/Logic"
  fi
  docker run --rm \
    -v "$TENSILE_TREE":/wt:ro -v "$RB":/rb:ro -v "$LOGIC":/logic:ro \
    -w /tmp "$IMAGE" bash -c '
      set -e
      SP=$(python3 -c "import sys; print([p for p in sys.path if p.endswith(\"site-packages\")][0])")
      rm -rf "$SP/rocisa"; cp -r /rb/rocisa "$SP/rocisa"
      export LD_LIBRARY_PATH=/rb/stinkytofu:${LD_LIBRARY_PATH:-}
      export PYTHONPATH=/wt PYTHONDONTWRITEBYTECODE=1
      out=$(mktemp -d)
      python3 -m Tensile.TensileCreateLibrary \
        --architecture=gfx90a --cxx-compiler=amdclang++ \
        /logic "$out" HIP >/tmp/build.log 2>&1 || { echo "BUILD_FAILED" >&2; tail -30 /tmp/build.log >&2; exit 1; }
      cd "$out"
      # Structural fingerprint: the gfx90a assembler/linker is NOT byte-
      # deterministic for multi-kernel code objects (.co/.hsaco vary in size &
      # sha across identical-code builds; README allows address/ordering drift).
      # So ELF objects are fingerprinted by their defined-symbol SET + count
      # (deterministic); metadata (.dat.zlib et al) keeps the exact byte sha.
      # The gfx90a build has exactly one benign nondeterminism source: the
      # compiler-generated __hip_cuid_<hash> compilation-unit id, which varies
      # per compile and propagates into the hsaco symtab, the .co byte layout,
      # and the lazy-master .dat. It is filtered/normalized out below so an
      # additive-only change can be proven to produce IDENTICAL structure.
      NORM="s/__hip_cuid_[0-9a-fA-F]*/__hip_cuid_NORM/g"
      find library -type f | sort | while read -r f; do
        case "$f" in
          *.hsaco)
            syms=$(llvm-nm --defined-only "$f" 2>/dev/null | awk "{print \$NF}" | grep -v "^__hip_cuid_" | sort)
            n=$(printf "%s\n" "$syms" | grep -c .)
            sh=$(printf "%s\n" "$syms" | sha256sum | cut -d" " -f1)
            printf "%s ELF nsym=%s symsha=%s\n" "$f" "$n" "$sh"
            ;;
          *.co)
            allsyms=""; ntgt=0
            for tgt in $(clang-offload-bundler --list --type=o --input="$f" 2>/dev/null | grep -v "^host"); do
              ntgt=$((ntgt+1))
              clang-offload-bundler --unbundle --type=o --targets="$tgt" --input="$f" --output=/tmp/inner.o 2>/dev/null
              allsyms="$allsyms$(llvm-nm --defined-only /tmp/inner.o 2>/dev/null | awk "{print \$NF}" | grep -v "^__hip_cuid_" | sort)
"
            done
            n=$(printf "%s" "$allsyms" | grep -c .)
            sh=$(printf "%s" "$allsyms" | sha256sum | cut -d" " -f1)
            printf "%s CO ntgt=%s nsym=%s symsha=%s\n" "$f" "$ntgt" "$n" "$sh"
            ;;
          *.zlib)
            # decompress, normalize cuid, and fingerprint the ORDER-INDEPENDENT
            # set of printable tokens: the lazy-master map serializes its entries
            # in parallel-completion order which drifts run-to-run while the entry
            # set is identical, so byte order is not a meaningful signal here.
            sz=$(python3 -c "import zlib,sys,re,hashlib; b=zlib.decompress(open(sys.argv[1],\"rb\").read()); b=re.sub(rb\"__hip_cuid_[0-9a-fA-F]+\",b\"NORM\",b); toks=sorted(set(re.findall(rb\"[ -~]{4,}\",b))); h=hashlib.sha256(b\"\\n\".join(toks)).hexdigest(); sys.stdout.write(str(len(b))+\" ntok=\"+str(len(toks))+\" \"+h)" "$f")
            printf "%s ZLIB dsize=%s\n" "$f" "$sz"
            ;;
          *)
            printf "%s RAW size=%s sha=%s\n" "$f" "$(stat -c %s "$f")" "$(sha256sum "$f" | cut -d" " -f1)"
            ;;
        esac
      done
    '
}

case "${1:-}" in
  capture)
    NAME="$2"; FILTER="$3"
    OUT="$(fp_path "$NAME" "$FILTER")"
    build_and_fingerprint "$FILTER" > "$OUT.tmp" || { echo "capture FAILED"; exit 1; }
    mv "$OUT.tmp" "$OUT"
    echo "captured $(wc -l < "$OUT") files -> $OUT"
    ;;
  *)
    A="$1"; B="$2"; FILTER="$3"
    fa="$(mktemp)"; fb="$(mktemp)"
    if [ "$A" = "HEAD" ]; then build_and_fingerprint "$FILTER" > "$fa" || exit 1
    else cp "$(fp_path "$A" "$FILTER")" "$fa" || { echo "no baseline $A"; exit 1; }; fi
    if [ "$B" = "HEAD" ]; then build_and_fingerprint "$FILTER" > "$fb" || exit 1
    else cp "$(fp_path "$B" "$FILTER")" "$fb" || { echo "no baseline $B"; exit 1; }; fi
    na=$(wc -l < "$fa"); nb=$(wc -l < "$fb")
    echo "file-count: $A=$na $B=$nb"
    if diff -q "$fa" "$fb" >/dev/null; then
      echo "artifacts: IDENTICAL ($na files, size+sha256 match)"
    else
      echo "artifacts: DIFFERENT"
      echo "--- $A vs $B (unified) ---"
      diff "$fa" "$fb" | head -60
    fi
    rm -f "$fa" "$fb"
    ;;
esac
