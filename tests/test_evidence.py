"""测试 Evidence 模型和存储"""

import json
from athena.data.market_provider import LongbridgeMarketProvider
from athena.signals.technical import compute_technical_signals
from athena.evidence.models import Evidence, build_price_evidence
from athena.evidence.store import EvidenceStore


class TestEvidenceModel:
    def test_evidence_creation(self):
        e = Evidence(symbol="NVDA", as_of="2024-02-22T21:00:00Z",
                     source="longbridge", source_type="market_data",
                     evidence_type="technical", claim="NVDA is in strong uptrend")
        assert e.symbol == "NVDA"
        assert e.confidence == "High"
        assert e.evidence_id == "NVDA_LB_TEC_2024-02-22"

    def test_evidence_to_dict(self):
        e = Evidence(symbol="AAPL", as_of="2024-01-01T00:00:00Z",
                     source="fixture", source_type="market_data",
                     evidence_type="technical", claim="test", metrics={"close": 100.0})
        d = e.to_dict()
        assert d["evidence_id"] == "AAPL_FX_TEC_2024-01-01"
        assert d["metrics"]["close"] == 100.0


class TestEvidenceStore:
    def test_add_and_count(self):
        store = EvidenceStore()
        e = Evidence(symbol="NVDA", as_of="2024-01-01T00:00:00Z",
                     source="test", source_type="test", evidence_type="test", claim="test")
        store.add(e)
        assert len(store) == 1

    def test_to_json(self):
        store = EvidenceStore()
        e = Evidence(symbol="NVDA", as_of="2024-01-01T00:00:00Z",
                     source="test", source_type="test", evidence_type="test", claim="test claim")
        store.add(e)
        j = store.to_json()
        parsed = json.loads(j)
        assert len(parsed) == 1
        assert parsed[0]["claim"] == "test claim"


class TestBuildPriceEvidence:
    def test_build_nvda(self):
        p = LongbridgeMarketProvider()
        df = p.fetch_history("NVDA", 250)
        tech = compute_technical_signals(df)
        evidence_list = build_price_evidence("NVDA", tech, source=p.data_source)
        assert len(evidence_list) == 5
        for e in evidence_list:
            assert e.symbol == "NVDA"
            assert e.evidence_type == "technical"
            assert e.confidence in ("High", "Medium", "Low")

    def test_build_aapl(self):
        p = LongbridgeMarketProvider()
        df = p.fetch_history("AAPL", 250)
        tech = compute_technical_signals(df)
        evidence_list = build_price_evidence("AAPL", tech, source=p.data_source)
        assert len(evidence_list) == 5
