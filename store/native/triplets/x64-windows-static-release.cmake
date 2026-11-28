set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE static)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_BUILD_TYPE release)

# The optional ScrollView debugger launches a separate Java process.
# File OCR and its PDF and hOCR output do not use the debugger.
if(PORT STREQUAL "tesseract")
    list(APPEND VCPKG_CMAKE_CONFIGURE_OPTIONS "-DGRAPHICS_DISABLED=ON")
endif()
