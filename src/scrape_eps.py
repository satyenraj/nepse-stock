import requests
import pandas as pd

BASE_URL = "https://sharehubnepal.com/data/api/v1/fundamental/values"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://sharehubnepal.com/",
}


def get_fundamentals(symbol: str, compare_type: str = "yoy") -> pd.DataFrame:
    url = f"{BASE_URL}/{symbol}"

    response = requests.get(
        url,
        params={"compareType": compare_type},
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if not result["success"]:
        raise Exception(result["message"])

    records = []

    for report in result["data"]:

        # Skip reports that have no values
        if not report.get("values"):
            continue

        row = {
            "symbol": report["symbol"],
            "fiscal_year": report["fiscalYear"],
            "quarter": report["quarter"],
        }

        for item in report["values"]:
            if item["key"] in {"dps", "eps", "eps_a", "roe", "net_profit", "paidup_capital"}:
                row[item["key"]] = (
                    item["valueString"]
                    if item["valueString"] is not None
                    else item["value"]
                )

        records.append(row)

    return pd.DataFrame(records)


if __name__ == "__main__":

    symbols = [
        "AKPL",
        "CHCL",
        "CBBL",
        "DDBL",
        "EBL",
        "GBIME",
        "KBL",
        "MBL",
        "NABIL",
        "NIL",
        "NMB",
        "SAHAS",
        "SANIMA",
        "SBL",
        "SHPC",
    ]

    frames = []

    for symbol in symbols:
        try:
            df = get_fundamentals(symbol)
            frames.append(df)
            print(f"✓ {symbol}")
        except Exception as e:
            print(f"✗ {symbol}: {e}")

    all_df = pd.concat(frames, ignore_index=True)

    all_df.to_csv(
        "data/fundamentals.csv",
        index=False
    )