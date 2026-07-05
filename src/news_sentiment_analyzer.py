"""
Nepal Stock News — Impact Analyzer using Ollama Python Client
-------------------------------------------------------------
Uses the official `ollama` Python package to call Ollama Cloud API.

Install : pip install ollama
API Key : export OLLAMA_API_KEY="your-key-here"  (from ollama.com/settings/keys)

Input   : nepal_stock_news.csv
Output  : nepal_stock_impact.csv
"""

import csv
import json
import os
import time
from datetime import datetime
from ollama import Client

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
INPUT_CSV  = "data/nepal_stock_news.csv"
OUTPUT_CSV = "data/nepal_stock_analysis.csv"

OLLAMA_API_KEY = "11e34a1bb3b74e4b905e4a4b2c484175.83q_wBSMvjzPn7u-y8aNywqF" # os.environ.get("OLLAMA_API_KEY", "")
MODEL          = "gpt-oss:120b-cloud"   # or "gpt-oss:20b-cloud" for faster/cheaper
DELAY_SECONDS  = 1.0

# Ollama Cloud client — same pattern as the example
client = Client(
    host="https://ollama.com",
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

# ─────────────────────────────────────────────
# NEPSE REFERENCE DATA
# ─────────────────────────────────────────────
NEPSE_SECTORS = [
    "Banking", "Development Bank", "Finance", "Microfinance",
    "Insurance", "Life Insurance", "Non-Life Insurance",
    "Hydropower", "Manufacturing and Processing",
    "Hotels and Tourism", "Trading", "Investment", "Mutual Fund", "Others",
]

NEPSE_TICKERS = """
Banking       : NABIL, EBL, NICA, SBI, KBL, MBL, CBL, GBIME, HBL, NMB, PCBL, PRVU, SANIMA, SCB, SRBL
Development   : CORBL, EDBL, GBBL, JBBL, KBBL, LBBL, MLBL, MNBBL, MRBL, MWBL, NABBC, NESDO, NGBBL, ODBL, SADBL
Finance       : BFC, CFCL, GFCL, ICFC, JFL, MFIL, MPFL, NFS, PROFL, RLFL, SFCL, SIFC
Microfinance  : CBBL, CYCL, DDBL, FOWAD, GMFIL, HLBSL, KLBSL, LLBS, MERO, MGBL, NUBL, RMDC, SKBBL, SMFBS, WOMI
Insurance     : ALICL, GILC, HGI, LICN, NLIC, NLG, NLICL, PLI, PMLI, PRIC, RBCL, SALICL, SGIC, SIC, SLICL
Hydropower    : AHPC, API, BARUN, BPCL, CHCL, DHPL, GVL, HURJA, KBPL, MHNL, NHPC, NWCL, PHPL, RADHI, RHPL, UPPER
Hotels        : OHL, SHL, TRH, TRHM, YETI
Manufacturing : BNL, BNT, GCIL, HDL, KDL, NBBL, NBTM, SHIVM, UALT
"""

# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a NEPSE (Nepal Stock Exchange) market analyst.
Analyze Nepal financial news and identify impacted sectors and stocks.
Always respond with valid JSON only — no explanation, no markdown, no code fences."""


def build_prompt(title: str, content: str) -> str:
    text = content.strip() if content.strip() else title
    return f"""Analyze this Nepal financial news and return a JSON object with:

- "relevant"        : true or false
- "market_impact"   : "bullish", "bearish", or "neutral"
- "overall_score"   : float -1.0 (very bearish) to +1.0 (very bullish)
- "impacted_sectors": list of objects with "sector", "score", "reason"
- "impacted_tickers": list of objects with "ticker", "score", "reason"
- "reason"          : one sentence summarizing the overall market impact

Score guide:
  +1.0 = extremely bullish  (massive dividend, acquisition)
  +0.5 = moderately bullish (good earnings, rate cut)
   0.0 = neutral
  -0.5 = moderately bearish (rate hike, tightening)
  -1.0 = extremely bearish  (fraud, bankruptcy, crisis)

NEPSE sectors : {", ".join(NEPSE_SECTORS)}
NEPSE tickers : {NEPSE_TICKERS}

News Title   : {title}
News Content : {text[:3000]}

Respond ONLY with valid JSON."""


# ─────────────────────────────────────────────
# CSV HELPERS
# ─────────────────────────────────────────────
OUTPUT_COLUMNS = [
    "id", "source", "title", "date",
    "relevant", "market_impact", "overall_score",
    "impacted_sectors", "impacted_tickers",
    "reason", "analyzed_at",
]


def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_analyzed_urls(path: str) -> set[str]:
    return {r["url"] for r in load_csv(path) if r.get("url")}


def append_csv(rows: list[dict], path: str) -> None:
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in OUTPUT_COLUMNS})


# ─────────────────────────────────────────────
# OLLAMA CALL  (same pattern as the example)
# ─────────────────────────────────────────────
def analyze(title: str, content: str) -> dict:
    """Stream response from Ollama Cloud, collect chunks, parse JSON."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_prompt(title, content)},
    ]

    # Stream and print each chunk as it arrives
    raw_text = ""
    for part in client.chat(MODEL, messages=messages, stream=True):
        chunk = part["message"]["content"]
        raw_text += chunk
        print(chunk, end="", flush=True)

    print()  # newline after stream ends

    # Strip markdown fences if model adds them despite instructions
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return format_result(json.loads(text))
    except json.JSONDecodeError as e:
        print(f"    [ERROR] Failed to parse JSON: {e}")
        return default_result()


def format_result(raw: dict) -> dict:
    """Flatten nested sector/ticker lists into readable CSV strings."""
    sectors = raw.get("impacted_sectors", [])
    sector_str = ", ".join(
        f"{s['sector']} ({'+' if s['score'] >= 0 else ''}{s['score']:.2f})"
        for s in sectors if isinstance(s, dict) and s.get("sector")
    )

    tickers = raw.get("impacted_tickers", [])
    ticker_str = ", ".join(
        f"{t['ticker']} ({'+' if t['score'] >= 0 else ''}{t['score']:.2f})"
        for t in tickers if isinstance(t, dict) and t.get("ticker")
    )

    return {
        "relevant":         str(raw.get("relevant", False)).lower(),
        "market_impact":    raw.get("market_impact", "neutral"),
        "overall_score":    round(float(raw.get("overall_score", 0.0)), 2),
        "impacted_sectors": sector_str,
        "impacted_tickers": ticker_str,
        "reason":           raw.get("reason", ""),
    }


def default_result() -> dict:
    return {
        "relevant": "false", "market_impact": "neutral",
        "overall_score": 0.0, "impacted_sectors": "",
        "impacted_tickers": "", "reason": "Analysis failed",
    }

# ─────────────────────────────────────────────
# analyze and save to csv file
# ─────────────────────────────────────────────
def analyze_n_save(news: list[dict]):
    if not OLLAMA_API_KEY:
        print("[ERROR] OLLAMA_API_KEY not set.\nRun: export OLLAMA_API_KEY='your-key'")
        return

    print(f"\n{'='*60}")
    print("  Nepal Stock News — Impact Analyzer (Ollama Cloud)")
    print(f"  Model   : {MODEL}")
    print(f"  Input   : {INPUT_CSV}")
    print(f"  Output  : {OUTPUT_CSV}")
    print(f"{'='*60}\n")

    all_news      = news #load_csv(INPUT_CSV)
    analyzed_urls = load_analyzed_urls(OUTPUT_CSV)
    pending       = [r for r in all_news if r.get("url") not in analyzed_urls]

    print(f"  Total in CSV     : {len(all_news)}")
    print(f"  Already analyzed : {len(analyzed_urls)}")
    print(f"  Pending          : {len(pending)}\n")

    if not pending:
        print("  ✅ All articles already analyzed.")
        return

    scored = []
    for i, row in enumerate(pending, 1):
        title   = row.get("title", "")
        content = row.get("content", "")

        print(f"  [{i:>3}/{len(pending)}] {title[:65]}")
        print(f"  {'─'*58}")

        result = analyze(title, content)

        scored_row = {
            "id": row.get("id", ""),
            "source":      row.get("source", ""),
            "title":       title,
            "date":        row.get("date", ""),
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **result,
        }
        scored.append(scored_row)

        icon = "📈" if result["market_impact"] == "bullish" else \
               "📉" if result["market_impact"] == "bearish" else "➖"
        print(f"\n  {icon} {result['market_impact'].upper()} | score: {result['overall_score']:+.2f}")
        if result["impacted_sectors"]:
            print(f"  Sectors : {result['impacted_sectors']}")
        if result["impacted_tickers"]:
            print(f"  Tickers : {result['impacted_tickers']}")
        print()

        # Save every 5 articles in case of interruption
        if i % 5 == 0:
            append_csv(scored, OUTPUT_CSV)
            print(f"  💾 Progress saved ({i} articles).\n")
            scored = []

        time.sleep(DELAY_SECONDS)

    if scored:
        append_csv(scored, OUTPUT_CSV)

    # Final summary
    all_done = load_csv(OUTPUT_CSV)
    bullish  = sum(1 for r in all_done if r.get("market_impact") == "bullish")
    bearish  = sum(1 for r in all_done if r.get("market_impact") == "bearish")
    relevant = sum(1 for r in all_done if r.get("relevant") == "true")

    print(f"\n{'='*60}")
    print(f"  ✅ Done! Results saved to: {OUTPUT_CSV}")
    print(f"  Total: {len(all_done)} | Relevant: {relevant} | 📈 {bullish} | 📉 {bearish}")
    print(f"{'='*60}\n")