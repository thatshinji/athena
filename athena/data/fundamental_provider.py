"""Longbridge 基本面数据 Provider。

通过 FundamentalContext 获取：估值/一致预期/分析师评级/财务报表明细。
"""

import concurrent.futures
import logging
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_fund_lock = Lock()
_fund_ctx = None
_fund_available: Optional[bool] = None


def _init_fundamental():
    global _fund_ctx, _fund_available
    if _fund_available is not None:
        return
    with _fund_lock:
        if _fund_available is not None:
            return

        def _do_init():
            from longbridge.openapi import Config, FundamentalContext
            return FundamentalContext(Config.from_apikey_env())

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_init)
                _fund_ctx = future.result(timeout=5)
                _fund_available = True
                logger.info("FundamentalContext 初始化成功")
        except Exception as e:
            _fund_available = False
            logger.warning(f"FundamentalContext 不可用: {e}")


def fetch_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    _init_fundamental()
    if not _fund_available:
        return None

    s = f"{symbol}.US"
    result: Dict[str, Any] = {}

    # 估值
    try:
        v = _fund_ctx.valuation(s)
        m = v.metrics
        result["valuation"] = {
            "pe": _extract_metric(m.pe), "ps": _extract_metric(m.ps),
            "pb": _extract_metric(m.pb),
            "dvd_yld": float(m.dvd_yld) if m.dvd_yld else None,
        }
    except Exception as e:
        logger.debug(f"估值失败 {symbol}: {e}")

    # 一致预期
    try:
        c = _fund_ctx.consensus(s)
        if c.list:
            r = c.list[c.current_index]
            result["consensus"] = {
                d.key: {
                    "name": d.name, "actual": float(d.actual) if d.actual else None,
                    "estimate": float(d.estimate) if d.estimate else None,
                    "comp": d.comp, "comp_desc": d.comp_desc,
                    "comp_value": float(d.comp_value) if d.comp_value else None,
                }
                for d in r.details
            }
    except Exception as e:
        logger.debug(f"一致预期失败 {symbol}: {e}")

    # 评级
    try:
        ratings = _fund_ctx.ratings(s)
        if ratings:
            result["ratings"] = [
                {"rating": getattr(r, "rating", "N/A"),
                 "target_price": float(r.target_price) if hasattr(r, "target_price") and r.target_price else None,
                 "institution": getattr(r, "institution", "N/A")}
                for r in (ratings.list if hasattr(ratings, "list") else [ratings])
            ]
    except Exception as e:
        logger.debug(f"评级失败 {symbol}: {e}")

    # 财务报表
    try:
        result["financial_report"] = _fetch_financial_report_inner(s)
    except Exception as e:
        logger.debug(f"财报失败 {symbol}: {e}")

    return result if result else None


def _fetch_financial_report_inner(symbol_full: str) -> Dict:
    """从 IncomeStatement、BalanceSheet、CashFlow 提取关键指标。"""
    from longbridge.openapi import FinancialReportKind

    metrics = {}

    def _extract_report(kind, data_key, field_map):
        try:
            r = _fund_ctx.financial_report(symbol_full, kind)
            report_data = r.list.get(data_key, {})
            for ind in report_data.get("indicators", []):
                for acct in ind.get("accounts", []):
                    field = acct.get("field", "")
                    key = field_map.get(field)
                    if not key:
                        continue
                    values = acct.get("values", [])
                    if not values:
                        continue
                    latest = values[0]
                    prev = values[1] if len(values) > 1 else {}
                    metrics[key] = {
                        "latest_value": float(latest["value"]) if latest.get("value") else None,
                        "latest_period": latest.get("period"),
                        "latest_yoy": float(latest["yoy"]) if latest.get("yoy") else None,
                        "prev_value": float(prev["value"]) if prev.get("value") else None,
                    }
        except Exception:
            pass

    # Income Statement
    _extract_report(FinancialReportKind.IncomeStatement, "IS", {
        "EPS": "eps", "OperatingRevenue": "revenue",
        "GrossMgn": "gross_margin", "NetProfitMargin": "net_margin",
        "ROE": "roe", "OperatingIncome": "operating_income",
    })

    # Balance Sheet
    _extract_report(FinancialReportKind.BalanceSheet, "BS", {
        "CashSTInvest": "cash_and_equivalents",
        "NetDebt": "net_debt",
        "BPS": "book_value_per_share",
        "Leverage": "leverage",
    })

    # Cash Flow
    _extract_report(FinancialReportKind.CashFlow, "CF", {
        "NetFreeCashFlow": "free_cash_flow",
        "NetOperateCashFlow": "operating_cash_flow",
        "CapEx": "capex",
    })

    return metrics


def _extract_metric(m) -> Optional[Dict]:
    if m is None:
        return None
    return {
        "current": float(m.median) if hasattr(m, "median") and m.median else None,
        "high": float(m.high) if hasattr(m, "high") and m.high else None,
        "low": float(m.low) if hasattr(m, "low") and m.low else None,
        "desc": m.desc if hasattr(m, "desc") and m.desc else None,
    }
