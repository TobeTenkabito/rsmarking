import numpy as np
cimport numpy as cnp

def fast_stretch_and_stack(
        cnp.ndarray[cnp.float32_t, ndim=3] data,
        cnp.ndarray[cnp.float32_t, ndim=1] mins,
        cnp.ndarray[cnp.float32_t, ndim=1] maxs):
    cdef int bands = data.shape[0]
    cdef int rows = data.shape[1]
    cdef int cols = data.shape[2]
    cdef cnp.ndarray[cnp.uint8_t, ndim=3] output = np.zeros((rows, cols, 4), dtype=np.uint8)
    cdef int b, i, j
    cdef float val, b_min, b_max, scale
    cdef float max_val_all_bands
    for b in range(bands):
        if b >= 3: break
        b_min = mins[b]
        b_max = maxs[b]
        scale = 255.0 / (b_max - b_min) if b_max > b_min else 0
        for i in range(rows):
            for j in range(cols):
                val = (data[b, i, j] - b_min) * scale
                if val > 255:
                    val = 255
                elif val < 0:
                    val = 0
                output[i, j, b] = <cnp.uint8_t> val
    for i in range(rows):
        for j in range(cols):
            max_val_all_bands = 0
            for b in range(bands):
                if data[b, i, j] > max_val_all_bands:
                    max_val_all_bands = data[b, i, j]
            if max_val_all_bands > 0:
                output[i, j, 3] = 255
            else:
                output[i, j, 3] = 0
    if bands == 1:
        for i in range(rows):
            for j in range(cols):
                output[i, j, 1] = output[i, j, 0]
                output[i, j, 2] = output[i, j, 0]

    return output
