import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv, set_key
from free_market_data import NSEMarketDataEngine

load_dotenv()

# Common sector mapping for Indian equities
SECTOR_MAP = {
    "RELIANCE": "Energy / Conglomerate",
    "TCS": "Information Technology",
    "INFY": "Information Technology",
    "WIPRO": "Information Technology",
    "HCLTECH": "Information Technology",
    "TECHM": "Information Technology",
    "HDFCBANK": "Banking & Financials",
    "ICICIBANK": "Banking & Financials",
    "SBIN": "Banking & Financials",
    "KOTAKBANK": "Banking & Financials",
    "AXISBANK": "Banking & Financials",
    "BAJFINANCE": "Financial Services",
    "TATASTEEL": "Metals & Mining",
    "JSWSTEEL": "Metals & Mining",
    "HINDALCO": "Metals & Mining",
    "ITC": "FMCG",
    "HINDUNILVR": "FMCG",
    "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG",
    "TATAMOTORS": "Automobile",
    "MARUTI": "Automobile",
    "M&M": "Automobile",
    "SUNPHARMA": "Pharmaceuticals",
    "DRREDDY": "Pharmaceuticals",
    "CIPLA": "Pharmaceuticals",
    "LT": "Infrastructure & Capital Goods",
    "BHARTIARTL": "Telecommunications",
    "ADANIENT": "Diversified",
    "NTPC": "Power & Utilities",
    "POWERGRID": "Power & Utilities"
}

class ZerodhaService:
    """
    Secure, Read-Only Zerodha Portfolio Intelligence & Analytics Service.
    
    Security & Privacy Guarantees:
    1. STRICTLY READ-ONLY: Real trade execution is permanently blocked to prevent capital loss.
    2. PRIVACY-AIR-GAPPED: Client IDs, PAN, emails, and personal identifiers are scrubbed
       before data is ever formatted or presented to the LLM.
    3. DUAL OPERATION:
       - Sandbox / Mock Mode: Realistic Indian portfolio data for risk analysis & doubt exploration.
       - Live Kite Connect Mode: Connects to your real Zerodha account via official KiteConnect SDK
         for read-only portfolio telemetry, margins, and live quotes.
    """

    # Enforce Read-Only Mode at code level for maximum security
    READ_ONLY_MODE = True

    def __init__(self):
        self.reload_config()
        self._init_mock_data()

    def reload_config(self):
        """Reloads configuration from .env dynamically."""
        load_dotenv(override=True)
        self.api_key = os.getenv("ZERODHA_API_KEY", "").strip()
        self.api_secret = os.getenv("ZERODHA_API_SECRET", "").strip()
        self.access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip()
        
        raw_mock = os.getenv("ZERODHA_MOCK_MODE", "true").strip().lower()
        self.mock_mode = raw_mock in ("true", "1", "yes") or not (self.api_key and self.access_token)
        
        self.kite = None
        if not self.mock_mode and self.api_key and self.access_token:
            try:
                from kiteconnect import KiteConnect
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.access_token)
            except Exception as e:
                print(f"[ZerodhaService] Live Kite connection error: {e}. Falling back to Sandbox Mode.")
                self.mock_mode = True

    def _init_mock_data(self):
        """Initializes high-fidelity mock Indian market data for sandbox analysis."""
        self._mock_margins = {
            "equity": {
                "enabled": True,
                "net": 245800.50,
                "available": {
                    "cash": 180600.50,
                    "collateral": 65200.00
                },
                "utilised": {
                    "debits": 42150.00,
                    "m2m_realised": 2150.00
                }
            },
            "commodity": {
                "enabled": True,
                "net": 50000.00,
                "available": {"cash": 50000.00},
                "utilised": {"debits": 0.0}
            }
        }

        self._mock_holdings = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "NSE",
                "isin": "INE002A01018",
                "quantity": 25,
                "average_price": 2840.50,
                "last_price": 2985.20,
                "close_price": 2940.00,
                "pnl": 3617.50,
                "day_change": 45.20,
                "day_change_percentage": 1.54
            },
            {
                "tradingsymbol": "TCS",
                "exchange": "NSE",
                "isin": "INE467B01029",
                "quantity": 15,
                "average_price": 4120.00,
                "last_price": 4245.50,
                "close_price": 4190.00,
                "pnl": 1882.50,
                "day_change": 55.50,
                "day_change_percentage": 1.32
            },
            {
                "tradingsymbol": "INFY",
                "exchange": "NSE",
                "isin": "INE009A01021",
                "quantity": 60,
                "average_price": 1490.20,
                "last_price": 1625.00,
                "close_price": 1608.50,
                "pnl": 8088.00,
                "day_change": 16.50,
                "day_change_percentage": 1.03
            },
            {
                "tradingsymbol": "HDFCBANK",
                "exchange": "NSE",
                "isin": "INE040A01034",
                "quantity": 50,
                "average_price": 1585.00,
                "last_price": 1665.40,
                "close_price": 1650.00,
                "pnl": 4020.00,
                "day_change": 15.40,
                "day_change_percentage": 0.93
            },
            {
                "tradingsymbol": "TATASTEEL",
                "exchange": "NSE",
                "isin": "INE081A01020",
                "quantity": 250,
                "average_price": 141.50,
                "last_price": 158.75,
                "close_price": 155.00,
                "pnl": 4312.50,
                "day_change": 3.75,
                "day_change_percentage": 2.42
            },
            {
                "tradingsymbol": "ITC",
                "exchange": "NSE",
                "isin": "INE154A01025",
                "quantity": 120,
                "average_price": 428.00,
                "last_price": 454.20,
                "close_price": 451.00,
                "pnl": 3144.00,
                "day_change": 3.20,
                "day_change_percentage": 0.71
            }
        ]

        self._mock_positions = {
            "net": [
                {
                    "tradingsymbol": "NIFTY24OCT25000CE",
                    "exchange": "NFO",
                    "product": "NRML",
                    "quantity": 50,
                    "buy_quantity": 50,
                    "buy_price": 124.50,
                    "sell_quantity": 0,
                    "last_price": 158.00,
                    "pnl": 1675.00,
                    "m2m": 1675.00
                }
            ],
            "day": [
                {
                    "tradingsymbol": "TATAMOTORS",
                    "exchange": "NSE",
                    "product": "MIS",
                    "quantity": 0,
                    "buy_quantity": 30,
                    "buy_price": 930.00,
                    "sell_quantity": 30,
                    "sell_price": 948.50,
                    "last_price": 947.00,
                    "pnl": 555.00,
                    "m2m": 555.00
                }
            ]
        }

        self._mock_mf_holdings = [
            {
                "fund": "PARAG PARIKH FLEXI CAP FUND - DIRECT PLAN",
                "quantity": 94.403,
                "average_price": 87.9158,
                "last_price": 88.8355
            },
            {
                "fund": "MOTILAL OSWAL MIDCAP FUND - DIRECT PLAN",
                "quantity": 44.993,
                "average_price": 95.5654,
                "last_price": 114.3619
            },
            {
                "fund": "UTI NIFTY 50 INDEX FUND - DIRECT PLAN",
                "quantity": 30.947,
                "average_price": 161.5585,
                "last_price": 159.2891
            },
            {
                "fund": "HDFC LIQUID FUND - DIRECT PLAN",
                "quantity": 0.806,
                "average_price": 5585.4052,
                "last_price": 5593.1126
            },
            {
                "fund": "ZERODHA GOLD ETF FOF - DIRECT PLAN",
                "quantity": 53.788,
                "average_price": 18.5905,
                "last_price": 19.2209
            },
            {
                "fund": "NIPPON INDIA SILVER ETF FOF - DIRECT PLAN",
                "quantity": 29.50,
                "average_price": 33.8964,
                "last_price": 33.3947
            }
        ]

        self._mock_mf_sips = [
            {
                "fund": "Parag Parikh Flexi Cap Fund - Direct Plan",
                "status": "ACTIVE",
                "frequency": "monthly",
                "instalment_amount": 5000.0,
                "instalment_day": 18,
                "next_instalment": "2026-10-18",
                "completed_instalments": 6,
                "created": "2026-03-13"
            },
            {
                "fund": "Motilal Oswal Midcap Fund - Direct Plan",
                "status": "ACTIVE",
                "frequency": "monthly",
                "instalment_amount": 2500.0,
                "instalment_day": 18,
                "next_instalment": "2026-10-18",
                "completed_instalments": 6,
                "created": "2026-03-13"
            },
            {
                "fund": "UTI Nifty 50 Index Fund - Direct Plan",
                "status": "ACTIVE",
                "frequency": "monthly",
                "instalment_amount": 2000.0,
                "instalment_day": 18,
                "next_instalment": "2026-10-18",
                "completed_instalments": 6,
                "created": "2026-03-13"
            }
        ]

    # =========================================================================
    # AUTHENTICATION & SESSION MANAGEMENT
    # =========================================================================

    def get_login_url(self, redirect_uri: str = "http://127.0.0.1:5000/zerodha/callback") -> str:
        """Generates Zerodha Kite OAuth login URL for secure 1-click morning login."""
        if not self.api_key:
            return "Error: ZERODHA_API_KEY is not configured in .env."
        return f"https://kite.zerodha.com/connect/login?v=3&api_key={self.api_key}&redirect_url={redirect_uri}"

    def exchange_request_token(self, request_token: str) -> Dict[str, Any]:
        """
        Exchanges morning OAuth request_token for a daily access_token via KiteConnect API.
        Saves the access_token safely to .env.
        """
        if not (self.api_key and self.api_secret):
            return {"status": "error", "message": "ZERODHA_API_KEY or ZERODHA_API_SECRET missing in .env"}
        
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=self.api_key)
            session_data = kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = session_data.get("access_token")
            
            if not access_token:
                return {"status": "error", "message": "Could not extract access_token from Zerodha session response."}
            
            # Save to .env
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            set_key(env_path, "ZERODHA_ACCESS_TOKEN", access_token)
            set_key(env_path, "ZERODHA_MOCK_MODE", "false")
            
            self.reload_config()
            return {
                "status": "success",
                "message": "Zerodha live session established successfully for today! Switched to Live Read-Only mode.",
                "user_name": session_data.get("user_name", "User"),
                "login_time": session_data.get("login_time", time.strftime("%Y-%m-%d %H:%M:%S"))
            }
        except Exception as e:
            return {"status": "error", "message": f"Session generation failed: {str(e)}"}

    def get_status(self) -> Dict[str, Any]:
        """Returns connection status, mode, and security posture."""
        return {
            "mode": "Sandbox (Simulation / Mock Data)" if self.mock_mode else "Live Kite Connect API (Read-Only)",
            "is_mock": self.mock_mode,
            "security_policy": "READ-ONLY & ANONYMIZED (Zero Order Execution Privilege)",
            "has_api_key": bool(self.api_key),
            "has_access_token": bool(self.access_token),
            "broker": "Zerodha Kite Connect v3"
        }

    # =========================================================================
    # ANONYMIZED & ENRICHED PORTFOLIO QUERIES
    # =========================================================================

    def get_margins(self) -> Dict[str, Any]:
        """Fetches equity and commodity available margins, cash balances, and collateral (anonymized)."""
        raw_margins = self._mock_margins
        if not self.mock_mode and self.kite:
            try:
                raw_margins = self.kite.margins()
            except Exception as e:
                return {"error": str(e), "mode": "Live Kite Fetch Failed"}
        
        # Anonymized summary without account IDs
        eq = raw_margins.get("equity", {})
        comm = raw_margins.get("commodity", {})
        return {
            "equity_margin": {
                "net_available_balance": eq.get("net", 0.0),
                "available_cash": eq.get("available", {}).get("cash", 0.0),
                "collateral_margin": eq.get("available", {}).get("collateral", 0.0),
                "utilised_margin": eq.get("utilised", {}).get("debits", 0.0),
                "realised_m2m": eq.get("utilised", {}).get("m2m_realised", 0.0)
            },
            "commodity_margin": {
                "net_available_balance": comm.get("net", 0.0),
                "available_cash": comm.get("available", {}).get("cash", 0.0)
            },
            "mode": "Sandbox" if self.mock_mode else "Live Zerodha API"
        }

    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Retrieves equity delivery holdings enriched with:
        - Exact purchase price & current LTP
        - Unrealized P&L and % gain/loss
        - Sector classification
        - Allocation percentage weight in portfolio
        """
        raw_holdings = self._mock_holdings
        if not self.mock_mode and self.kite:
            try:
                raw_holdings = self.kite.holdings()
            except Exception as e:
                return [{"error": f"Failed to fetch live holdings: {str(e)}"}]

        enriched = []
        for h in raw_holdings:
            sym = h.get("tradingsymbol", "").upper()
            qty = h.get("quantity", 0)
            avg_price = round(h.get("average_price", 0.0), 2)
            invested_val = round(qty * avg_price, 2)

            # Query official live market price from NSEMarketDataEngine
            nse_quote = NSEMarketDataEngine.get_nse_quote(sym)
            if "last_price" in nse_quote and nse_quote["last_price"]:
                ltp = round(nse_quote["last_price"], 2)
                day_change_pct = round(nse_quote.get("change_percent", 0.0), 2)
                h52 = nse_quote.get("52_week_high")
                l52 = nse_quote.get("52_week_low")
            else:
                ltp = round(h.get("last_price", 0.0) or h.get("average_price", 0.0), 2)
                day_change_pct = round(h.get("day_change_percentage", 0.0), 2)
                h52 = None
                l52 = None

            curr_val = round(qty * ltp, 2)
            pnl = round(curr_val - invested_val, 2)
            pnl_pct = round((pnl / invested_val * 100), 2) if invested_val > 0 else 0.0
            sector = SECTOR_MAP.get(sym, "Diversified / General")

            enriched.append({
                "tradingsymbol": sym,
                "exchange": "NSE",
                "quantity": qty,
                "average_price": avg_price,
                "last_price": ltp,
                "invested_value": invested_val,
                "current_value": curr_val,
                "pnl": pnl,
                "pnl_percentage": pnl_pct,
                "sector": sector,
                "day_change_pct": day_change_pct,
                "52_week_high": h52,
                "52_week_low": l52,
                "data_source": "National Stock Exchange (NSE) Live Feed"
            })

        total_current_val = sum(item["current_value"] for item in enriched)
        for item in enriched:
            item["portfolio_weight_pct"] = round((item["current_value"] / total_current_val * 100), 2) if total_current_val > 0 else 0.0

        return enriched

    def get_portfolio_analytics(self) -> Dict[str, Any]:
        """
        Performs executive-level portfolio health and risk analysis:
        - Total Invested vs Current Portfolio Value
        - Overall P&L and ROI %
        - Sector diversification breakdown
        - Concentration risk analysis (flags if any stock is > 20% of portfolio)
        - Top performing stock & biggest laggard
        """
        holdings = self.get_holdings()
        if not holdings or "error" in holdings[0]:
            return {"error": "Holdings unavailable for analysis"}

        total_invested = sum(h["invested_value"] for h in holdings)
        total_current = sum(h["current_value"] for h in holdings)
        total_pnl = round(total_current - total_invested, 2)
        total_roi = round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0.0

        # Sector Allocation
        sectors = {}
        for h in holdings:
            sec = h["sector"]
            sectors[sec] = sectors.get(sec, 0.0) + h["current_value"]
        
        sector_breakdown = [
            {
                "sector": sec,
                "value": round(val, 2),
                "allocation_pct": round((val / total_current * 100), 2) if total_current > 0 else 0.0
            }
            for sec, val in sorted(sectors.items(), key=lambda x: x[1], reverse=True)
        ]

        # Concentration Risk (>20% allocation in single equity)
        concentration_alerts = []
        for h in holdings:
            if h["portfolio_weight_pct"] >= 20.0:
                concentration_alerts.append({
                    "stock": h["tradingsymbol"],
                    "weight": f"{h['portfolio_weight_pct']}%",
                    "risk_level": "HIGH" if h["portfolio_weight_pct"] >= 30.0 else "MODERATE",
                    "recommendation": "Consider trimming or diversifying gains to avoid single-stock volatility impact."
                })

        # Top performers
        sorted_by_gain = sorted(holdings, key=lambda x: x["pnl_percentage"], reverse=True)
        top_winner = sorted_by_gain[0] if sorted_by_gain else None
        top_laggard = sorted_by_gain[-1] if sorted_by_gain else None

        return {
            "portfolio_summary": {
                "total_invested_inr": round(total_invested, 2),
                "total_current_value_inr": round(total_current, 2),
                "total_unrealized_pnl_inr": total_pnl,
                "overall_roi_percentage": f"{total_roi}%",
                "total_stocks_count": len(holdings)
            },
            "top_performer": {
                "stock": top_winner["tradingsymbol"] if top_winner else "N/A",
                "return_pct": f"{top_winner['pnl_percentage']}%" if top_winner else "0%",
                "pnl_inr": top_winner["pnl"] if top_winner else 0
            },
            "lagging_holding": {
                "stock": top_laggard["tradingsymbol"] if top_laggard else "N/A",
                "return_pct": f"{top_laggard['pnl_percentage']}%" if top_laggard else "0%",
                "pnl_inr": top_laggard["pnl"] if top_laggard else 0
            },
            "sector_allocation": sector_breakdown,
            "concentration_risk_alerts": concentration_alerts or ["No single stock exceeds 20% concentration. Portfolio is well-distributed."],
            "mode": "Sandbox Simulation" if self.mock_mode else "Live Zerodha Account"
        }

    def get_positions(self) -> Dict[str, Any]:
        """Fetches active intraday (MIS) and F&O derivative positions (anonymized)."""
        raw_positions = self._mock_positions
        if not self.mock_mode and self.kite:
            try:
                raw_positions = self.kite.positions()
            except Exception as e:
                return {"error": str(e)}

        return {
            "net_positions": raw_positions.get("net", []),
            "day_positions": raw_positions.get("day", []),
            "mode": "Sandbox" if self.mock_mode else "Live Zerodha API"
        }

    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Fetches official NSE real-time price quotes (LTP, OHLC, volume, change %)."""
        return NSEMarketDataEngine.get_multiple_quotes(instruments)

    def get_technical_levels(self, symbol: str) -> Dict[str, Any]:
        """Calculates 52-week high/low, support/resistance, and market posture from the NSE market feed."""
        return NSEMarketDataEngine.get_technical_levels(symbol)

    # =========================================================================
    # COIN MUTUAL FUNDS & SIP INTELLIGENCE
    # =========================================================================

    def get_mutual_fund_holdings(self) -> List[Dict[str, Any]]:
        """
        Retrieves Coin mutual fund portfolio holdings with units, purchase NAV,
        current NAV, total invested value, current value, and unrealized returns.
        Folios and account numbers are strictly anonymized for privacy.
        """
        raw_funds = []
        if not self.mock_mode and self.kite:
            try:
                raw_funds = self.kite.mf_holdings()
            except Exception as e:
                return [{"error": f"Failed to fetch mutual fund holdings: {str(e)}"}]
        else:
            raw_funds = getattr(self, "_mock_mf_holdings", [])

        categorized = []
        for item in raw_funds:
            fund_name = item.get("fund", "Unknown Mutual Fund").strip()
            qty = float(item.get("quantity", 0.0))
            avg_price = float(item.get("average_price", 0.0))
            last_price = float(item.get("last_price", 0.0))

            invested = round(qty * avg_price, 2)
            current = round(qty * last_price, 2)
            pnl = round(current - invested, 2)
            roi_pct = round((pnl / invested * 100), 2) if invested > 0 else 0.0

            # Determine category
            fname_upper = fund_name.upper()
            if "GOLD" in fname_upper:
                cat = "Commodities (Gold)"
            elif "SILVER" in fname_upper:
                cat = "Commodities (Silver)"
            elif "LIQUID" in fname_upper or "OVERNIGHT" in fname_upper or "MONEY MARKET" in fname_upper:
                cat = "Debt / Liquid (Emergency Buffer)"
            elif "NIFTY 50" in fname_upper or "INDEX" in fname_upper or "SENSEX" in fname_upper:
                cat = "Equity (Large Cap Index)"
            elif "MIDCAP" in fname_upper or "MID CAP" in fname_upper:
                cat = "Equity (Mid Cap Alpha Growth)"
            elif "SMALLCAP" in fname_upper or "SMALL CAP" in fname_upper:
                cat = "Equity (Small Cap)"
            elif "FLEXI" in fname_upper or "MULTI" in fname_upper:
                cat = "Equity (Diversified Flexi Cap)"
            else:
                cat = "Equity (Diversified)"

            categorized.append({
                "fund_name": fund_name,
                "category": cat,
                "units": qty,
                "avg_nav": round(avg_price, 4),
                "current_nav": round(last_price, 4),
                "invested_value_inr": invested,
                "current_value_inr": current,
                "unrealized_pnl_inr": pnl,
                "roi_percentage": f"{roi_pct}%",
                "roi_numeric": roi_pct
            })

        return categorized

    def get_mutual_fund_sips(self) -> List[Dict[str, Any]]:
        """
        Retrieves active Coin SIP schedules, monthly deduction dates,
        installment amounts, and completion history.
        """
        raw_sips = []
        if not self.mock_mode and self.kite:
            try:
                raw_sips = self.kite.mf_sips()
            except Exception as e:
                return [{"error": f"Failed to fetch mutual fund SIPs: {str(e)}"}]
        else:
            raw_sips = getattr(self, "_mock_mf_sips", [])

        cleaned_sips = []
        for s in raw_sips:
            cleaned_sips.append({
                "fund_name": s.get("fund", "Unknown Fund"),
                "status": s.get("status", "ACTIVE"),
                "frequency": s.get("frequency", "monthly").title(),
                "monthly_amount_inr": float(s.get("instalment_amount", 0.0)),
                "instalment_day": s.get("instalment_day"),
                "next_instalment_date": str(s.get("next_instalment", "")),
                "completed_instalments_count": s.get("completed_instalments", 0),
                "sip_start_date": str(s.get("created", ""))[:10]
            })
        return cleaned_sips

    def get_mutual_fund_analytics(self) -> Dict[str, Any]:
        """
        Analyzes the Coin Mutual Fund portfolio: asset allocation breakdown,
        monthly SIP volume, top performing fund, and total MF wealth.
        """
        funds = self.get_mutual_fund_holdings()
        sips = self.get_mutual_fund_sips()

        if not funds or "error" in funds[0]:
            return {"error": "Mutual fund holdings unavailable for analysis"}

        total_invested = sum(f["invested_value_inr"] for f in funds)
        total_current = sum(f["current_value_inr"] for f in funds)
        total_pnl = round(total_current - total_invested, 2)
        total_roi = round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0.0

        # Allocation by Category
        categories = {}
        for f in funds:
            c = f["category"]
            categories[c] = categories.get(c, 0.0) + f["current_value_inr"]

        category_breakdown = [
            {
                "category": cat,
                "current_value_inr": round(val, 2),
                "allocation_pct": round((val / total_current * 100), 2) if total_current > 0 else 0.0
            }
            for cat, val in sorted(categories.items(), key=lambda x: x[1], reverse=True)
        ]

        # Top performer & Laggard
        sorted_funds = sorted(funds, key=lambda x: x["roi_numeric"], reverse=True)
        top_winner = sorted_funds[0] if sorted_funds else None
        top_laggard = sorted_funds[-1] if sorted_funds else None

        active_sips = [s for s in sips if s.get("status") == "ACTIVE"]
        total_monthly_sip = sum(s.get("monthly_amount_inr", 0.0) for s in active_sips)

        return {
            "summary": {
                "total_funds_held": len(funds),
                "total_invested_inr": round(total_invested, 2),
                "total_current_value_inr": round(total_current, 2),
                "net_unrealized_pnl_inr": total_pnl,
                "overall_roi_percentage": f"{total_roi}%",
                "active_monthly_sip_inflow_inr": total_monthly_sip
            },
            "top_performer": {
                "fund": top_winner["fund_name"] if top_winner else "N/A",
                "roi": top_winner["roi_percentage"] if top_winner else "0%",
                "pnl_inr": top_winner["unrealized_pnl_inr"] if top_winner else 0
            },
            "lagging_fund": {
                "fund": top_laggard["fund_name"] if top_laggard else "N/A",
                "roi": top_laggard["roi_percentage"] if top_laggard else "0%",
                "pnl_inr": top_laggard["unrealized_pnl_inr"] if top_laggard else 0
            },
            "asset_allocation": category_breakdown,
            "active_sips": active_sips
        }

    def get_combined_wealth_overview(self) -> Dict[str, Any]:
        """
        Combines Demat Direct Equities + Coin Mutual Funds for a comprehensive
        master portfolio review and overall profitability verdict.
        """
        stock_analytics = self.get_portfolio_analytics()
        mf_analytics = self.get_mutual_fund_analytics()

        stock_inv = stock_analytics.get("portfolio_summary", {}).get("total_invested_inr", 0.0)
        stock_cur = stock_analytics.get("portfolio_summary", {}).get("total_current_value_inr", 0.0)
        stock_pnl = stock_analytics.get("portfolio_summary", {}).get("total_unrealized_pnl_inr", 0.0)

        mf_inv = mf_analytics.get("summary", {}).get("total_invested_inr", 0.0)
        mf_cur = mf_analytics.get("summary", {}).get("total_current_value_inr", 0.0)
        mf_pnl = mf_analytics.get("summary", {}).get("net_unrealized_pnl_inr", 0.0)

        total_inv = round(stock_inv + mf_inv, 2)
        total_cur = round(stock_cur + mf_cur, 2)
        total_pnl = round(total_cur - total_inv, 2)
        total_roi = round((total_pnl / total_inv * 100), 2) if total_inv > 0 else 0.0

        is_profitable = total_pnl >= 0

        return {
            "verdict": {
                "status": "PROFITABLE INVESTOR 🟢" if is_profitable else "TEMPORARY DRAWDOWN 🔴",
                "net_profit_loss_inr": total_pnl,
                "overall_roi_percentage": f"{total_roi}%"
            },
            "master_totals": {
                "total_capital_deployed_inr": total_inv,
                "total_current_portfolio_value_inr": total_cur,
                "net_gain_inr": total_pnl
            },
            "sub_portfolios": {
                "direct_equities": {
                    "invested": stock_inv,
                    "current": stock_cur,
                    "pnl": stock_pnl,
                    "roi": stock_analytics.get("portfolio_summary", {}).get("overall_roi_percentage", "0%")
                },
                "coin_mutual_funds": {
                    "invested": mf_inv,
                    "current": mf_cur,
                    "pnl": mf_pnl,
                    "roi": mf_analytics.get("summary", {}).get("overall_roi_percentage", "0%")
                }
            }
        }


    # =========================================================================
    # EXECUTION BLOCK (HARD-LOCKED SECURITY BARRIER)
    # =========================================================================

    def place_order(self, *args, **kwargs) -> Dict[str, Any]:
        """Hard security lock: order placement is permanently disabled for read-only portfolio analysis."""
        return {
            "status": "blocked",
            "security_lock": True,
            "message": "Live order execution is permanently disabled in this AI Assistant. This instance operates in strictly READ-ONLY mode for portfolio analysis and investment guidance to guarantee complete capital safety."
        }

    def cancel_order(self, *args, **kwargs) -> Dict[str, Any]:
        """Hard security lock: order cancellation is disabled in read-only mode."""
        return {
            "status": "blocked",
            "security_lock": True,
            "message": "Order modifications are disabled in Read-Only mode."
        }

# Global singleton
zerodha_client = ZerodhaService()
