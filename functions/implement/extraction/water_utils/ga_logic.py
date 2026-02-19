import numpy as np
import logging
import multiprocessing
from typing import List
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import RobustScaler
from scipy import ndimage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GeoAdaptive-Exact")


class GeoAdaptive:
    def __init__(self, chunk_size: int = 20000, n_jobs: int = -1):
        self.chunk_size = chunk_size
        self.n_jobs = n_jobs if n_jobs > 0 else multiprocessing.cpu_count()
        self.clf = HistGradientBoostingClassifier(
            loss='log_loss',
            max_iter=300,
            max_depth=12,
            learning_rate=0.04,
            l2_regularization=15.0,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=25
        )
        self.scaler = RobustScaler()

    def _sanitize_array(self, arr: np.ndarray) -> np.ndarray:
        mask = np.isfinite(arr)
        if not np.all(mask):
            mean_val = np.nanmean(arr) if np.any(mask) else 0.0
            arr = np.nan_to_num(arr, nan=mean_val, posinf=mean_val, neginf=mean_val)
        return arr

    def _generate_feature_pyramid_fast(self, bands: List[np.ndarray]) -> np.ndarray:
        h, w = bands[0].shape
        n_bands = len(bands)
        pyramid = np.empty((h * w, n_bands * 5), dtype=np.float32)

        for i in range(n_bands):
            b: np.ndarray = bands[i]
            b_norm = self._sanitize_array(b)
            start_col = i * 5

            pyramid[:, start_col] = b_norm.ravel()
            pyramid[:, start_col + 1] = ndimage.uniform_filter(b_norm, size=3).ravel()
            pyramid[:, start_col + 2] = ndimage.gaussian_filter(b_norm, sigma=1.2).ravel()
            pyramid[:, start_col + 3] = ndimage.laplace(b_norm).ravel()

            mean = ndimage.uniform_filter(b_norm, size=5)
            sq_mean = ndimage.uniform_filter(b_norm ** 2, size=5)
            std = np.sqrt(np.maximum(sq_mean - mean ** 2, 0))
            pyramid[:, start_col + 4] = std.ravel()

        return pyramid

    def process(self, bands: List[np.ndarray], threshold: float = 0.0) -> np.ndarray:
        h, w = bands[0].shape

        green: np.ndarray = bands[1]
        nir: np.ndarray = bands[3]
        swir1: np.ndarray = bands[4]
        swir2: np.ndarray = bands[5]

        awei = 4.0 * (green - nir) - (0.25 * swir1 + 2.75 * swir2)
        mndwi = (green - swir1) / (green + swir1 + 1e-7)
        guide_index = awei * 0.7 + mndwi * 0.3

        flat_index = guide_index.ravel()
        w_mask = flat_index > (threshold + 0.45)
        l_mask = flat_index < (threshold - 0.45)

        w_seeds = np.flatnonzero(w_mask)
        l_seeds = np.flatnonzero(l_mask)

        n_base = min(len(w_seeds), len(l_seeds), 12000)
        if n_base < 100:
            return (guide_index > threshold).astype('uint8')

        w_idx = np.random.choice(w_seeds, n_base, replace=False)
        l_idx = np.random.choice(l_seeds, n_base, replace=False)

        w_hard_mask = (flat_index > threshold) & (flat_index <= threshold + 0.45)
        l_hard_mask = (flat_index < threshold) & (flat_index >= threshold - 0.45)
        w_hard = np.flatnonzero(w_hard_mask)
        l_hard = np.flatnonzero(l_hard_mask)

        n_hard = min(len(w_hard), len(l_hard), 2000)
        if n_hard > 10:
            w_idx = np.concatenate([w_idx, np.random.choice(w_hard, n_hard)])
            l_idx = np.concatenate([l_idx, np.random.choice(l_hard, n_hard)])

        train_indices = np.concatenate([w_idx, l_idx])
        y = np.concatenate([np.ones(len(w_idx)), np.zeros(len(l_idx))])
        weights = np.clip(np.abs(flat_index[train_indices] - threshold), 0.1, 5.0)

        X_flat = self._generate_feature_pyramid_fast(bands)
        X_train = self.scaler.fit_transform(X_flat[train_indices])
        self.clf.fit(X_train, y, sample_weight=weights)

        probs = np.empty(h * w, dtype=np.float32)
        for i in range(0, h * w, self.chunk_size):
            end = i + self.chunk_size
            chunk = self.scaler.transform(X_flat[i:end])
            probs[i:end] = self.clf.predict_proba(chunk)[:, 1]

        raw_mask = (probs.reshape(h, w) > 0.5)
        labeled, num_features = ndimage.label(raw_mask)
        size = np.bincount(labeled.ravel())
        mask_cleaned = size[labeled] > 20

        mask_closed = ndimage.binary_closing(mask_cleaned, structure=np.ones((3, 3)))
        return ndimage.binary_fill_holes(mask_closed).astype('uint8')
