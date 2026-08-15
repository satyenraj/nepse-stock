import requests
import pandas as pd
from constants.companyIdMap import companyIdMap

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


def get_fundamentals(symbol: str, compare_type: str = "quarterly") -> pd.DataFrame:
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

def get_latest_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    # Extract quarter number (q1 -> 1, q2 -> 2, etc.) for proper sorting
    df["quarter_num"] = df["quarter"].str.extract(r"(\d+)").astype(int)

    # fiscal_year like "082/083" sorts correctly as a string in most cases,
    # but to be safe, extract the starting year as an integer for sorting
    df["fy_start"] = df["fiscal_year"].str.split("/").str[0].astype(int)

    # Sort by symbol, then by fiscal year and quarter descending
    df_sorted = df.sort_values(
        by=["symbol", "fy_start", "quarter_num"],
        ascending=[True, False, False]
    )

    # Take the first row per symbol after sorting (i.e., the latest record)
    latest_df = df_sorted.groupby("symbol", as_index=False).first()

    # Drop helper columns if you don't need them
    latest_df = latest_df.drop(columns=["quarter_num", "fy_start"])

    return latest_df

if __name__ == "__main__":

    symbols = list(companyIdMap.keys())
    df_today_prices = pd.read_csv("data/today_prices.csv")
    print(df_today_prices)

    frames = []
    latest_frames = []

    for symbol in symbols:
        try:
            df = get_fundamentals(symbol)
            frames.append(df)

            if not df.empty:

                df_latest = get_latest_fundamentals(df)
                #print(df_latest)

                today_price = df_today_prices[df_today_prices["symbol"] == symbol]
                today_price = today_price.reset_index(drop=True)
                #print(today_price)

                df_latest["pde"] = 0.00
                df_latest["pe"] = 0.00

                if not today_price.empty:
                    if "eps" in df.columns:
                        #print(today_price["close"]/df_latest["eps"])
                        df_latest["pe"] = round(today_price["close"]/df_latest["eps"], 2)

                    if "dps" in df.columns:
                        #print(today_price["close"]/df_latest["dps"])
                        df_latest["pde"] = round(today_price["close"]/df_latest["dps"], 2)

                    df_latest["price"] = round(today_price["close"], 2)

                latest_frames.append(df_latest) 

            print(f"✓ {symbol}")
        except Exception as e:
            print(f"✗ {symbol}: {e}")
            exit(1)

    all_df = pd.concat(frames, ignore_index=True)
    latest_all_df = pd.concat(latest_frames, ignore_index=True)

    all_df.to_csv(
        "data/quarterly_fundamentals.csv",
        index=False
    )

    latest_all_df.to_csv(
        "data/fundamentals.csv",
        index=False
    )