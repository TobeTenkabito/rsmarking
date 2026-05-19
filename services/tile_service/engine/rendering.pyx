# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True

import numpy as np
cimport numpy as np
from libc.stdint cimport uint8_t


cdef inline float _scale(float low, float high) noexcept nogil:
    if high > low:
        return 255.0 / (high - low)
    return 0.0


cdef inline uint8_t _stretch(float value, float low, float scale) noexcept nogil:
    cdef float stretched = (value - low) * scale
    if stretched <= 0.0:
        return 0
    if stretched >= 255.0:
        return 255
    return <uint8_t>stretched


def render_tile(float[:, :, :] data, float[:] mins, float[:] maxs):
    """
    Stretch the first three bands into RGB and derive alpha from all bands.
    The hot loop avoids per-pixel range calculation and fills RGBA directly.
    """
    cdef int count = data.shape[0]
    cdef int height = data.shape[1]
    cdef int width = data.shape[2]
    cdef np.ndarray[uint8_t, ndim=3] out = np.empty((height, width, 4), dtype=np.uint8)
    cdef uint8_t[:, :, :] out_view = out

    cdef int band, y, x
    cdef bint has_data
    cdef float v0, v1, v2
    cdef float low0 = 0.0
    cdef float low1 = 0.0
    cdef float low2 = 0.0
    cdef float scale0 = 0.0
    cdef float scale1 = 0.0
    cdef float scale2 = 0.0

    if count <= 0:
        out.fill(0)
        return out

    if count > 0:
        low0 = mins[0]
        scale0 = _scale(mins[0], maxs[0])
    if count > 1:
        low1 = mins[1]
        scale1 = _scale(mins[1], maxs[1])
    if count > 2:
        low2 = mins[2]
        scale2 = _scale(mins[2], maxs[2])

    with nogil:
        for y in range(height):
            for x in range(width):
                if count == 1:
                    v0 = data[0, y, x]
                    out_view[y, x, 0] = _stretch(v0, low0, scale0)
                    out_view[y, x, 1] = out_view[y, x, 0]
                    out_view[y, x, 2] = out_view[y, x, 0]
                    has_data = v0 != 0.0
                elif count == 2:
                    v0 = data[0, y, x]
                    v1 = data[1, y, x]
                    out_view[y, x, 0] = _stretch(v0, low0, scale0)
                    out_view[y, x, 1] = _stretch(v1, low1, scale1)
                    out_view[y, x, 2] = 0
                    has_data = v0 != 0.0 or v1 != 0.0
                else:
                    v0 = data[0, y, x]
                    v1 = data[1, y, x]
                    v2 = data[2, y, x]
                    out_view[y, x, 0] = _stretch(v0, low0, scale0)
                    out_view[y, x, 1] = _stretch(v1, low1, scale1)
                    out_view[y, x, 2] = _stretch(v2, low2, scale2)
                    has_data = v0 != 0.0 or v1 != 0.0 or v2 != 0.0
                    if not has_data:
                        for band in range(3, count):
                            if data[band, y, x] != 0.0:
                                has_data = 1
                                break

                if has_data:
                    out_view[y, x, 3] = 255
                else:
                    out_view[y, x, 3] = 0

    return out
