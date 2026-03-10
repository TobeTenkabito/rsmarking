# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True

import numpy as np
cimport numpy as np
from libc.stdint cimport uint8_t

def render_tile(float[:, :, :] data, float[:] mins, float[:] maxs):
    """
    Highly optimized tile rendering using Cython.
    Processes stretching, clipping, and RGBA stacking in a single C-loop.
    """
    cdef int count = data.shape[0]
    cdef int height = data.shape[1]
    cdef int width = data.shape[2]

    # Output buffer: Height x Width x 4 (RGBA)
    cdef np.ndarray[uint8_t, ndim=3] out = np.zeros((height, width, 4), dtype=np.uint8)

    cdef int c, y, x
    cdef float val, low, high, rng, stretched
    cdef float max_val
    cdef uint8_t pixel_val

    # Release GIL to allow true multi-core processing
    with nogil:
        for y in range(height):
            for x in range(width):
                max_val = 0

                # Handle RGB Channels
                for c in range(count):
                    if c >= 3: break # Only process up to 3 bands for RGB

                    val = data[c, y, x]
                    low = mins[c]
                    high = maxs[c]
                    rng = high - low
                    if rng <= 0: rng = 1.0

                    # Stretch and Clip
                    stretched = (val - low) / rng * 255.0
                    if stretched < 0: stretched = 0
                    if stretched > 255: stretched = 255

                    pixel_val = <uint8_t>stretched

                    # Store in Output (RGBA order)
                    if count == 1:
                        # Grayscale to RGB
                        out[y, x, 0] = pixel_val
                        out[y, x, 1] = pixel_val
                        out[y, x, 2] = pixel_val
                    else:
                        out[y, x, c] = pixel_val

                    if val > max_val:
                        max_val = val

                # Special case: 2 bands (rare in remote sensing, usually fill B with 0)
                if count == 2:
                    out[y, x, 2] = 0

                # Alpha Channel: 255 if any band has data > 0, else 0
                if max_val > 0:
                    out[y, x, 3] = 255
                else:
                    out[y, x, 3] = 0

    return out
