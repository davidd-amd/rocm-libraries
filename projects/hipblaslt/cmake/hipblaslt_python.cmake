# Copyright Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier:  MIT

include("${CMAKE_CURRENT_LIST_DIR}/hipblaslt_codegen.cmake")

macro(hipblaslt_find_python python_dev_component)
    find_package(Python3 3.8 COMPONENTS Interpreter ${python_dev_component} REQUIRED)
    set(Python_EXECUTABLE "${Python3_EXECUTABLE}")
    find_package(Python 3.8 COMPONENTS Interpreter ${python_dev_component} REQUIRED)
    if(NOT "${Python_EXECUTABLE}" STREQUAL "${Python3_EXECUTABLE}")
        message(WARNING "FindPython and FindPython3 found different executables. You may need to pin -DPython_EXECUTABLE and -DPython3_EXECUTABLE (${Python_EXECUTABLE} vs ${Python3_EXECUTABLE})")
    endif()
endmacro()

# Sets the HIPBLASLT_PYTHON_COMMAND variable in the parent scope such that it
# can invoke the Python interpreter valid for the build parameters. Because
# this may involve a multi token list, it must be used without quotes in
# COMMAND lists.
function(hipblaslt_configure_bundled_python_command python_binary_dir)
    set(_sanitizer_flags "")
    if(HIPBLASLT_ENABLE_DEVICE)
        if(HIPBLASLT_ENABLE_ASAN OR THEROCK_SANITIZER STREQUAL "ASAN" OR THEROCK_SANITIZER STREQUAL "HOST_ASAN")
            set(_sanitizer_flags ASAN)
        elseif(HIPBLASLT_ENABLE_TSAN OR THEROCK_SANITIZER STREQUAL "TSAN")
            set(_sanitizer_flags TSAN)
        endif()
    endif()
    hipblaslt_detect_sanitizer_runtime(_asan_options _runtime_lib_dirs ${_sanitizer_flags})
    hipblaslt_make_python_command(_python_command
        PYTHONPATH_DIRS ${python_binary_dir} "${hipblaslt_SOURCE_DIR}/tensilelite"
        RUNTIME_LIB_DIRS ${_runtime_lib_dirs}
        ENV_ASSIGNMENTS ${_asan_options}
    )
    message(VERBOSE "Python command: ${_python_command}")
    set(HIPBLASLT_PYTHON_COMMAND "${_python_command}" PARENT_SCOPE)
endfunction()
