# ########################################################################
# Copyright (C) 2025 Advanced Micro Devices, Inc.
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
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ########################################################################

function(hipblaslt_target_configure_sanitizers hipblaslt_target linkage)
    if(DEFINED THEROCK_SANITIZER AND NOT THEROCK_SANITIZER STREQUAL "")
        return()
    endif()
    if(HIPBLASLT_ENABLE_ASAN)
        target_compile_options(${hipblaslt_target}
            ${linkage}
                -fsanitize=address
                -shared-libasan
        )
        target_link_options(${hipblaslt_target}
            ${linkage}
                -fsanitize=address
                -shared-libasan
                -fuse-ld=lld
        )
    elseif(HIPBLASLT_ENABLE_TSAN)
        target_compile_options(${hipblaslt_target}
            ${linkage}
                -fsanitize=thread
                -shared-libtsan
        )
        target_link_options(${hipblaslt_target}
            ${linkage}
                -fsanitize=thread
                -shared-libtsan
                -fuse-ld=lld
        )
    endif()
endfunction()

# Point every sanitized executable (hipblaslt-test, hipblaslt-bench, samples, ...)
# at libclang_rt.<stem>.so, which is a DT_NEEDED under -shared-libsan. We seed two
# rpaths from a single probe:
#   * CMAKE_BUILD_RPATH   - the absolute clang runtime dir, so binaries run from the
#                           build tree resolve the runtime during local development.
#   * CMAKE_INSTALL_RPATH - a $ORIGIN-relative entry (../lib/llvm/<resource-dir>), so
#                           the *installed/dist* binary is self-contained. The install
#                           step relinks with INSTALL_RPATH and drops BUILD_RPATH, so
#                           this (not BUILD_RPATH) is what a packaged artifact uses.
# The runtime location depends on the clang layout (flat lib/linux/libclang_rt.<stem>-
# <arch>.so vs per-target lib/<triple>/libclang_rt.<stem>.so); we ask the driver via a
# link dry-run instead of hardcoding a path, so both are correct regardless of layout.
# Call once at project scope BEFORE any target is created (the CMAKE_*_RPATH vars seed
# each target's rpath properties at creation time).
function(hipblaslt_add_sanitizer_runtime_rpath)
    set(_stem "")
    set(_flag "")
    if(DEFINED THEROCK_SANITIZER AND NOT THEROCK_SANITIZER STREQUAL "")
        if(THEROCK_SANITIZER STREQUAL "ASAN" OR THEROCK_SANITIZER STREQUAL "HOST_ASAN")
            set(_stem asan)
            set(_flag "-fsanitize=address")
        elseif(THEROCK_SANITIZER STREQUAL "TSAN" OR THEROCK_SANITIZER STREQUAL "HOST_TSAN")
            set(_stem tsan)
            set(_flag "-fsanitize=thread")
        endif()
    elseif(HIPBLASLT_ENABLE_ASAN)
        set(_stem asan)
        set(_flag "-fsanitize=address")
    elseif(HIPBLASLT_ENABLE_TSAN)
        set(_stem tsan)
        set(_flag "-fsanitize=thread")
    endif()

    if(NOT _stem OR WIN32)
        return()
    endif()

    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        message(WARNING
            "\n"
            "################################################################\n"
            "  hipBLASLt sanitizer build requested with a non-Clang compiler\n"
            "  CMAKE_CXX_COMPILER_ID=${CMAKE_CXX_COMPILER_ID}. The libclang_rt\n"
            "  runtime probe only supports Clang; the sanitizer runtime rpath\n"
            "  will NOT be added and sanitized executables (hipblaslt-test,\n"
            "  hipblaslt-bench, ...) may fail to load their runtime at run time.\n"
            "  Configure with a Clang/amdclang toolchain.\n"
            "################################################################")
        return()
    endif()

    execute_process(
        COMMAND ${CMAKE_CXX_COMPILER} ${_flag} -shared-libsan -x c /dev/null "-###"
        OUTPUT_VARIABLE _out
        ERROR_VARIABLE _err
    )
    string(REGEX MATCHALL "/[^ \t\r\n\"]*libclang_rt\\.${_stem}(-[A-Za-z0-9_]+)?\\.so" _hits "${_out}${_err}")
    if(NOT _hits)
        return()
    endif()
    list(GET _hits 0 _rt)
    if(NOT EXISTS "${_rt}")
        return()
    endif()
    get_filename_component(_rt_dir "${_rt}" DIRECTORY)

    # Build tree: absolute runtime dir (only valid on this machine, dropped at install).
    list(APPEND CMAKE_BUILD_RPATH "${_rt_dir}")
    set(CMAKE_BUILD_RPATH "${CMAKE_BUILD_RPATH}" PARENT_SCOPE)
    message(STATUS "hipBLASLt: added sanitizer runtime dir to BUILD_RPATH: ${_rt_dir}")

    # Install/dist tree: re-root the clang resource dir under the dist's lib/llvm as a
    # $ORIGIN-relative entry so the packaged binary self-resolves the runtime. Inert
    # (loader skips missing entries) in installs that do not ship lib/llvm, e.g. a
    # standalone build using an external toolchain, where the runtime is on the system.
    string(REGEX REPLACE "^.*/(lib/clang/.*)$" "\\1" _rt_tail "${_rt_dir}")
    if(_rt_tail MATCHES "^lib/clang/")
        list(APPEND CMAKE_INSTALL_RPATH "$ORIGIN/../lib/llvm/${_rt_tail}")
        set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_RPATH}" PARENT_SCOPE)
        message(STATUS "hipBLASLt: added sanitizer runtime dir to INSTALL_RPATH: $ORIGIN/../lib/llvm/${_rt_tail}")
    endif()
endfunction()
