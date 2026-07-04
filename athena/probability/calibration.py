"""概率引擎权重校准 — 逻辑回归拟合。

用历史回测数据拟合最优信号权重，替代手动打分。
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from athena.validation import CaseRecord

logger = logging.getLogger(__name__)

# 默认手动权重（作为先验）
DEFAULT_WEIGHTS = {
    "alignment_strong_bullish": 2.0,
    "alignment_bullish": 1.0,
    "alignment_bearish": -2.0,
    "alignment_below_ma200": -2.0,
    "rsi_overbought": -1.0,
    "rsi_oversold": 1.0,
    "atr_stop_bad": -1.0,
    "atr_stop_good": 1.0,
    "near_52w_high": -1.0,
    "near_52w_low": 1.0,
    "eps_beat_strong": 2.0,
    "eps_miss": -2.0,
    "rev_beat_strong": 1.0,
    "rev_miss": -1.0,
    "fwd_pe_high": -2.0,
    "fwd_pe_low": 2.0,
}


def fit_logistic_weights(cases: List[CaseRecord]) -> Tuple[Dict[str, float], float]:
    """用逻辑回归从案例中拟合最优权重。

    Args:
        cases: 已结案例列表

    Returns:
        (weights_dict, accuracy)
    """
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        logger.warning("scikit-learn 未安装，使用默认权重")
        return DEFAULT_WEIGHTS, 0.0

    if len(cases) < 30:
        logger.warning(f"案例不足 ({len(cases)}), 需要 ≥30")
        return DEFAULT_WEIGHTS, 0.0

    # 从每个案例的 evidence_summary 中提取特征
    X, y = [], []
    feature_names = list(DEFAULT_WEIGHTS.keys())

    for case in cases:
        # 简化特征提取：使用 status_at_time 作为主要预测特征
        # 真实版本需要从原始信号中提取，此处用 status 做为基础
        row = [0.0] * len(feature_names)

        # 用 status 推断方向
        status = case.status_at_time
        if status == "Candidate":
            row[0] = 1.0  # alignment_strong_bullish
            row[1] = 1.0  # alignment_bullish
            row[6] = 1.0  # atr_stop_good
            row[10] = 1.0  # eps_beat_strong
        elif status == "Risk Alert":
            row[2] = 1.0  # alignment_bearish
            row[12] = 1.0  # rev_miss
            row[14] = 1.0  # fwd_pe_high
        elif status == "Reject":
            row[3] = 1.0  # alignment_below_ma200
            row[11] = 1.0  # eps_miss
            row[14] = 1.0  # fwd_pe_high

        X.append(row)
        # 标签：是否先涨 +20%
        outcome = case.to_dict().get("outcome", "Neither")
        y.append(1 if outcome == "UpsideFirst" else 0)

    X = np.array(X)
    y = np.array(y)

    # 训练逻辑回归
    model = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=5000, tol=1e-4)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, y)

    # 提取权重
    fitted = dict(zip(feature_names, model.coef_[0]))
    accuracy = float(model.score(X, y))

    logger.info(f"逻辑回归完成: accuracy={accuracy:.2%}, "
                f"samples={len(cases)}, positive_class={sum(y)}")

    return fitted, accuracy


def apply_fitted_weights(signals: Dict, fitted_weights: Dict = None) -> Dict:
    """用拟合权重替代手动权重计算概率。

    如果未提供 fitted_weights，回退到默认值。
    """
    w = fitted_weights or DEFAULT_WEIGHTS
    bullish = 0.0
    bearish = 0.0

    tech = signals.get("technical", {})
    fund = signals.get("fundamental", {})
    val = signals.get("valuation", {})

    # 技术面
    alignment = tech.get("price", {}).get("alignment", {})
    align_type = alignment.get("type", "")
    if align_type == "strong_bullish":
        bullish += w["alignment_strong_bullish"]
        bearish -= min(0, w["alignment_strong_bullish"])
    elif align_type == "bullish":
        bullish += w["alignment_bullish"]
    elif align_type == "bearish":
        bearish += abs(w["alignment_bearish"])
    elif align_type == "below_ma200":
        bearish += abs(w["alignment_below_ma200"])

    rsi = tech.get("momentum", {}).get("rsi14")
    if rsi and rsi > 70:
        bearish += abs(w["rsi_overbought"])
    elif rsi and rsi < 30:
        bullish += w["rsi_oversold"]

    atr_stop = tech.get("volatility", {}).get("atr_stop_assessment", {})
    if atr_stop.get("stop_loss_feasible") is False:
        bearish += abs(w["atr_stop_bad"])
    elif atr_stop.get("stop_loss_feasible") is True:
        bullish += w["atr_stop_good"]

    pct_h = tech.get("support_resistance", {}).get("pct_from_high")
    if pct_h and pct_h > -5:
        bearish += abs(w["near_52w_high"])

    # 基本面
    if fund.get("available"):
        eps_b = fund.get("eps", {}).get("beat_pct", 0) or 0
        if eps_b > 3:
            bullish += w["eps_beat_strong"]
        elif eps_b < 0:
            bearish += abs(w["eps_miss"])

        rev_b = fund.get("revenue", {}).get("beat_pct", 0) or 0
        if rev_b > 3:
            bullish += w["rev_beat_strong"]
        elif rev_b < 0:
            bearish += abs(w["rev_miss"])

    # 估值
    if val.get("available"):
        fwd_pe = val.get("forward_pe", {}).get("value")
        if fwd_pe and fwd_pe > 40:
            bearish += abs(w["fwd_pe_high"])
        elif fwd_pe and fwd_pe < 15:
            bullish += w["fwd_pe_low"]

    return {"bullish": max(0, bullish), "bearish": max(0, bearish), "weights_used": "fitted" if fitted_weights else "default"}
