# TileEngine Performance Analysis

## Overview

This document describes the theoretical time complexity, architectural evolution,
and performance comparison of different TileEngine implementations.

Tile size: 256 × 256  
Let:

- T = tile pixel count (256 × 256)
- B = band count
- N = B × T

Since B ≤ 3 in most visualization cases:

Time Complexity ≈ O(T)

------------------------------------------------------------

# 1. Version Comparison

| Version              | Core Implementation      | Time Complexity | Pixel Traversals | Performance Level |
|----------------------|--------------------------|-----------------|------------------|-------------------|
| V1 NumPy             | Vectorized NumPy         | O(N)            | Multiple         | ★★☆☆☆            |
| V2 translator.pyx    | Cython loop optimization | O(N)            | 1~2              | ★★★★☆            |
| V3 rendering.pyx     | Cython fused loop        | O(N)            | 1                | ★★★★★            |

------------------------------------------------------------

# 2. Complexity Breakdown

| Stage                | Time Complexity |
|----------------------|----------------|
| Coordinate Transform | O(1)           |
| Window Calculation   | O(1)           |
| Raster Read          | O(N)           |
| Percentile Estimate  | O(T)           |
| Stretch Computation  | O(N)           |
| Alpha Generation     | O(N)           |
| RGB Composition      | O(N)           |

Overall:

Time  = O(N)  
Space = O(N)

------------------------------------------------------------

# 3. Optimization Evolution

| Optimization Item       | NumPy | translator.pyx | rendering.pyx |
|--------------------------|-------|----------------|---------------|
| Transformer reuse        | ❌    | ✅             | ✅            |
| File handle reuse        | ❌    | ✅             | ✅            |
| Statistics caching       | ❌    | ✅             | ✅            |
| Percentile sampling      | ❌    | ✅             | ✅            |
| Single-pass pixel loop   | ❌    | ⚠️ Partial     | ✅            |
| Compiler optimization    | ❌    | -O3            | -O3 -march    |

------------------------------------------------------------

# 4. Estimated Relative Performance

(3 bands, 256x256 tile)

NumPy baseline            = 1.0x  
translator.pyx            = 2x ~ 3x  
rendering.pyx (current)   = 3x ~ 5x  

------------------------------------------------------------

# 5. Current Architecture

FastAPI  
   ↓  
TileEngine (stateless)  
   ↓  
COG  
   ↓  
LRU Tile Cache  

Execution priority:

rendering.pyx  
   ↓  
translator.pyx  
   ↓  
NumPy fallback  

------------------------------------------------------------

# 6. Current Version Characteristics

- Time Complexity: O(N)
- Space Complexity: O(N)
- Pixel Traversal Count: 1
- Minimal Python-level overhead
- Performance close to native C implementation

------------------------------------------------------------

# Conclusion

The current rendering.pyx implementation achieves:

- Optimal asymptotic complexity O(N)
- Minimal constant factor
- Single-pass pixel computation
- Near-native execution efficiency

This version represents a production-grade tile rendering engine.