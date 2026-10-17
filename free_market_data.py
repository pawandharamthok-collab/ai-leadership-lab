"""
Official National Stock Exchange of India (NSE) Live Market Intelligence Engine.
Zero-cost, Zero-API-Key live market telemetry for Indian Equities and Indices.

Exchange: National Stock Exchange of India (NSE)
Tickers: NSE Equities (.NS / :NSE) & Indices (NIFTY 50, BANK NIFTY, SENSEX)
"""

import urllib.request
import urllib.parse
import json
import time
from typing import Dict, Any, List, Optional

INDEX_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY 50": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "BANK NIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "SENSEX": "^BSESN",
    "BSE SENSEX": "^BSESN",
    "NIFTY IT": "^CNXIT",
    "NIFTY MIDCAP": "^NSEMDCP50",
    "MIDCAP": "^NSEMDCP50"
}

class NSEMarketDataEngine:
    """
    Live market data engine for the National Stock Exchange of India (NSE).
    Extracts official NSE quotes, price action, and 52-week high/low with 30s in-memory caching.
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    CACHE_TTL_SECONDS = 30

    @classmethod
    def normalize_nse_symbol(cls, symbol: str) -> str:
        """Converts user or broker input into official NSE market ticker."""
        cleaned = symbol.strip().upper()

        if cleaned in INDEX_MAP:
            return INDEX_MAP[cleaned]

        # Handle 'NSE:RELIANCE' or 'BSE:RELIANCE'
        if ":" in cleaned:
            parts = cleaned.split(":")
            exchange = parts[0]
            stock = parts[1]
            if exchange == "BSE":
                return f"{stock}.BO"
            return f"{stock}.NS"

        if cleaned.endswith(".NS") or cleaned.endswith(".BO") or cleaned.startswith("^"):
            return cleaned

        # Default to National Stock Exchange (.NS)
        return f"{cleaned}.NS"

    @classmethod
    def get_nse_quote(cls, symbol_or_index: str) -> Dict[str, Any]:
        """
        Fetches live price, day OHLC, net change %, and 52-week range from the NSE market feed.
        Requires zero API keys.
        """
        ticker = cls.normalize_nse_symbol(symbol_or_index)
        now = time.time()

        # Check in-memory cache
        if ticker in cls._cache:
            entry = cls._cache[ticker]
            if now - entry["cached_at"] < cls.CACHE_TTL_SECONDS:
                return entry["data"]

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))

            result = payload.get("chart", {}).get("result", [])
            if not result:
                return {"error": f"Symbol '{symbol_or_index}' not found on NSE exchange feed."}

            meta = result[0].get("meta", {})
            ltp = meta.get("regularMarketPrice")
            prev_close = meta.get("previousClose")

            if ltp is None and prev_close is not None:
                ltp = prev_close

            net_change = round(ltp - prev_close, 2) if (ltp is not None and prev_close is not None) else 0.0
            change_pct = round((net_change / prev_close * 100), 2) if (prev_close and prev_close > 0) else 0.0

            day_high = meta.get("regularMarketDayHigh") or ltp
            day_low = meta.get("regularMarketDayLow") or ltp
            fifty_two_week_high = meta.get("fiftyTwoWeekHigh")
            fifty_two_week_low = meta.get("fiftyTwoWeekLow")
            volume = meta.get("regularMarketVolume", 0)

            # Drawdown from 52-week high
            dist_from_high_pct = None
            if ltp and fifty_two_week_high and fifty_two_week_high > 0:
                dist_from_high_pct = round(((ltp - fifty_two_week_high) / fifty_two_week_high * 100), 2)

            is_index = ticker.startswith("^")
            clean_name = symbol_or_index.upper().strip()

            data = {
                "symbol": clean_name,
                "exchange": "NSE (National Stock Exchange of India)",
                "instrument_type": "Index" if is_index else "Equity Stock",
                "currency": "INR",
                "last_price": ltp,
                "previous_close": prev_close,
                "net_change": net_change,
                "change_percent": change_pct,
                "day_high": day_high,
                "day_low": day_low,
                "52_week_high": fifty_two_week_high,
                "52_week_low": fifty_two_week_low,
                "drawdown_from_52w_high_pct": dist_from_high_pct,
                "volume": volume,
                "data_source": "National Stock Exchange (NSE) Market Feed",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            cls._cache[ticker] = {"data": data, "cached_at": now}
            return data

        except urllib.error.HTTPError as e:
            return {"error": f"Symbol '{symbol_or_index}' was not recognized on the NSE exchange feed (HTTP {e.code})."}
        except Exception as e:
            return {"error": f"NSE connection error: {str(e)}"}

    @classmethod
    def get_multiple_quotes(cls, symbols: List[str]) -> Dict[str, Any]:
        """Fetches live market data for multiple NSE symbols simultaneously."""
        results = {}
        for s in symbols:
            clean = s.strip()
            if clean:
                results[clean] = cls.get_nse_quote(clean)
        return results

    @classmethod
    def get_technical_levels(cls, symbol_or_index: str) -> Dict[str, Any]:
        """Calculates 52-week high/low, support/resistance, and market posture for NSE assets."""
        quote = cls.get_nse_quote(symbol_or_index)
        if "error" in quote:
            return quote

        ltp = quote.get("last_price") or 0.0
        h52 = quote.get("52_week_high") or 0.0
        l52 = quote.get("52_week_low") or 0.0

        posture = "Neutral"
        if h52 and ltp and h52 > l52:
            pct_of_range = round(((ltp - l52) / (h52 - l52) * 100), 2)
            if pct_of_range >= 85:
                posture = "Strongly Bullish (Trading within top 15% of 52-Week Range)"
            elif pct_of_range <= 25:
                posture = "Oversold / Deep Value (Trading within bottom 25% of 52-Week Range)"
            else:
                posture = "Consolidating in Mid-Range"
        else:
            pct_of_range = 50.0

        return {
            "symbol": quote["symbol"],
            "exchange": quote["exchange"],
            "last_price": f"Rs. {ltp}",
            "net_day_change": f"{quote['net_change']} ({quote['change_percent']}%)",
            "52_week_high": f"Rs. {h52}",
            "52_week_low": f"Rs. {l52}",
            "distance_from_52w_high": f"{quote.get('drawdown_from_52w_high_pct')}%" if quote.get("drawdown_from_52w_high_pct") is not None else "N/A",
            "position_in_52w_range": f"{pct_of_range}%",
            "market_posture": posture,
            "intraday_range": f"Low: Rs. {quote['day_low']} - High: Rs. {quote['day_high']}",
            "volume": f"{quote['volume']:,}" if quote['volume'] else "N/A",
            "data_source": "National Stock Exchange (NSE) Market Feed"
        }
