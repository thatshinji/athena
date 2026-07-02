"""测试基本面 + 估值 + 风险信号"""

from athena.signals.fundamentals import compute_fundamental_signals
from athena.signals.valuation import compute_valuation_signals
from athena.signals.risk import compute_risk_signals


def test_fundamental_no_data():
    result = compute_fundamental_signals(None)
    assert result["signals"]["available"] is False


def test_fundamental_empty():
    result = compute_fundamental_signals({})
    assert result["signals"]["available"] is False


def test_valuation_no_data():
    result = compute_valuation_signals(None, 100.0)
    assert result["signals"]["available"] is False


def test_valuation_with_mock_pe():
    fund_data = {
        "valuation": {
            "pe": {"current": 25.0, "high": 40.0, "low": 15.0, "desc": "cheaper than 50%"},
            "ps": None, "pb": None, "dvd_yld": None,
        },
        "consensus": {},
    }
    result = compute_valuation_signals(fund_data, 200.0)
    assert result["signals"]["available"]
    assert result["signals"]["trailing_pe"]["current"] == 25.0
    assert result["signals"]["trailing_pe"]["percentile"] == 50.0
    ri = result["research_inputs"]
    assert "VL-001" in ri


def test_risk_empty():
    tech = {"price": {"alignment": {}}, "momentum": {}, "volatility": {}}
    result = compute_risk_signals(tech, {}, {})
    assert result["signals"]["available"]


def test_risk_high_valuation():
    tech = {"price": {"alignment": {"type": "mixed"}}, "momentum": {"rsi14": 50},
            "volatility": {"atr_stop_assessment": {"stop_loss_feasible": True}}}
    fund = {"available": True, "eps": {"beat_pct": 2}, "revenue": {"beat_pct": 3}}
    val = {"available": True, "forward_pe": {"value": 45}, "trailing_pe": {"current": 30}}
    result = compute_risk_signals(tech, fund, val)
    assert result["signals"]["risk_score"] >= 3  # Forward PE > 40 triggers
