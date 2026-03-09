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
<<<<<<< HEAD



r"""
\documentclass[11pt, a4paper]{article}

% --- 通用预处理块 ---
\usepackage[a4paper, top=2.5cm, bottom=2.5cm, left=2cm, right=2cm]{geometry}
\usepackage{fontspec}
\usepackage[english]{babel}
\usepackage{amsmath, amssymb, amsthm}
\usepackage{algorithm}
\usepackage{algorithmic}
\usepackage{bm}
\usepackage{booktabs}

% 设置默认字体为 Noto Sans
\babelfont{rm}{Noto Sans}

\title{GeoAdaptive 算法：高维空间特征提取与现场自学习水体分类数学规格说明}
\author{GeoAdaptive Engine 核心开发组}
\date{\today}

\begin{document}

\maketitle

\section{算法概述}
GeoAdaptive 算法是一种混合遥感分类架构。其核心数学逻辑在于将物理先验知识（光谱指数）作为启发式引导，通过构建高维时空特征金字塔，利用梯度提升决策树（HGBC）在局部区域执行实时非线性拟合。

\section{数学定义与过程}

\subsection{第一阶段：启发式采样与引导索引}
设波段集合 $\mathcal{B} = \{B_1, \dots, B_6\}$。首先计算融合引导索引 $\mathcal{I}$：
\begin{equation}
    MNDWI = \frac{B_{green} - B_{swir1}}{B_{green} + B_{swir1} + \epsilon}
\end{equation}
\begin{equation}
    AWEI = 4(B_{green} - B_{nir}) - (0.25 B_{swir1} + 2.75 B_{swir2})
\end{equation}
\begin{equation}
    \mathcal{I} = 0.7 \cdot AWEI + 0.3 \cdot MNDWI
\end{equation}

样本集 $\mathcal{S}$ 的构建遵循逻辑：
\begin{itemize}
    \item \textbf{正样本} $\mathcal{S}^+ = \{p \mid \mathcal{I}(p) > \tau + 0.45\}$
    \item \textbf{负样本} $\mathcal{S}^- = \{p \mid \mathcal{I}(p) < \tau - 0.45\}$
    \item \textbf{权重函数} $w(p) = \text{clip}(|\mathcal{I}(p) - \tau|, 0.1, 5.0)$
\end{itemize}

\subsection{第二阶段：高维特征空间映射}
定义算子 $\Phi$ 将单一波段 $B$ 映射为 5 维局部特征向量：
\begin{equation}
    \Phi(B)_p = \begin{bmatrix}
        B(p) \\
        (B * K_{u3})(p) \\
        (B * G_{\sigma=1.2})(p) \\
        (B * L)(p) \\
        \sqrt{(B^2 * K_{u5})(p) - ((B * K_{u5})(p))^2}
    \end{bmatrix}
\end{equation}
总特征维度 $d = |\mathcal{B}| \times 5 = 30$。

\section{算法伪代码}

\begin{algorithm}
\caption{GeoAdaptive 高性能分类流程}
\begin{algorithmic}[1]
\REQUIRE 波段集 $\mathcal{B}$，阈值 $\tau$
\ENSURE 优化后的二值掩膜 $M_{final}$

\STATE \COMMENT{// 第一阶段：生成引导索引}
\STATE $\mathcal{I} \leftarrow 0.7 \cdot AWEI(\mathcal{B}) + 0.3 \cdot MNDWI(\mathcal{B})$ 

\STATE \COMMENT{// 第二阶段：启发式样本筛选}
\STATE $\mathcal{S} \leftarrow \{ \text{Select } p \text{ based on } \mathcal{I} \text{ and } \tau \}$
\STATE 计算样本权重 $\mathbf{W}_{\mathcal{S}}$ 基于偏差 $|\mathcal{I} - \tau|$

\STATE \COMMENT{// 第三阶段：高维特征构建与标准化}
\FOR{每一个波段 $B \in \mathcal{B}$}
    \STATE $\mathbf{X}_{B} \leftarrow \Phi(B)$ \COMMENT{执行卷积与统计计算}
\ENDFOR
\STATE $\mathbf{X} \leftarrow \bigoplus \mathbf{X}_{B} \in \mathbb{R}^{30}$
\STATE $\mathbf{z}_{\mathcal{S}} \leftarrow \text{RobustScaler}(\mathbf{X}_{\mathcal{S}})$ \COMMENT{使用 IQR 进行鲁棒缩放}

\STATE \COMMENT{// 第四阶段：现场训练与分块预测}
\STATE $H \leftarrow \text{Train HGBC on } (\mathbf{z}_{\mathcal{S}}, y_{\mathcal{S}}) \text{ with weights } \mathbf{W}_{\mathcal{S}}$
\FOR{每一个像素块 $\text{chunk } \in \text{Image}$}
    \STATE $P_{chunk} \leftarrow H.\text{predict\_proba}(\text{RobustScaler}(\mathbf{X}_{chunk}))$
\ENDFOR

\STATE \COMMENT{// 第五阶段：几何与拓扑优化}
\STATE $M_0 \leftarrow \{p \mid P(p) > 0.5\}$
\STATE $M_1 \leftarrow \text{Filter components where Area} < 20$
\STATE $M_{final} \leftarrow \text{BinaryFillHoles}(\text{BinaryClosing}(M_1))$

\RETURN $M_{final}$
\end{algorithmic}
\end{algorithm}

\end{document}
"""
=======
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
