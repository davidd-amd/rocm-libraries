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

# Append the clang sanitizer runtime directory to CMAKE_BUILD_RPATH so that every
# executable (hipblaslt-test, hipblaslt-bench, samples, ...) can dlopen
# libclang_rt.<stem>.so from the build tree. Under a sanitizer, the runtime is a
# DT_NEEDED on all sanitized binaries, but its on-disk location depends on the
# clang runtime layout (flat lib/linux/libclang_rt.<stem>-<arch>.so vs per-target
# lib/<triple>/libclang_rt.<stem>.so). We ask the driver via a link dry-run
# instead of hardcoding a path, so the rpath is correct regardless of layout.
# Call once at project scope BEFORE any target is created (CMAKE_BUILD_RPATH seeds
# each target's BUILD_RPATH at creation time).
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
    if(_hits)
        list(GET _hits 0 _rt)
        if(EXISTS "${_rt}")
            get_filename_component(_rt_dir "${_rt}" DIRECTORY)
            list(APPEND CMAKE_BUILD_RPATH "${_rt_dir}")
            set(CMAKE_BUILD_RPATH "${CMAKE_BUILD_RPATH}" PARENT_SCOPE)
            message(STATUS "hipBLASLt: added sanitizer runtime dir to BUILD_RPATH: ${_rt_dir}")
        endif()
    endif()
endfunction()
