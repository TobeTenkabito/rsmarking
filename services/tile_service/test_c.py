import numpy as np
from engine import translator

data = np.random.rand(3, 256, 256).astype(np.float32)
mins = np.zeros(3, dtype=np.float32)
maxs = np.ones(3, dtype=np.float32)

rgba = translator.fast_stretch_and_stack(data, mins, maxs)
print(rgba.shape)  # output (256, 256, 4)
print(rgba.dtype)  # output uint8
