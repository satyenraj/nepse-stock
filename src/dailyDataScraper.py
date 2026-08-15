# import required library and required constants
import time
import requests
import pandas as pd
from io import StringIO
from pathlib import Path
from bs4 import BeautifulSoup
from utils.status import getStatus
from constants.url import dailyPriceUrl

html = requests.get(dailyPriceUrl).text
bs = BeautifulSoup(html, "lxml")

# today date in yyyy-mm-dd format
today = bs.find("span", {"class": "text-org"}).text

# get html tables
tables = pd.read_html(StringIO(html))

# select the first table i.e. the stock price table
dataTable = tables[0]

# Select and rename columns
selected_columns = {
    "Symbol": "symbol",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Diff %": "change_percent",
    "Vol": "volume",
    "Turnover": "traded_amount"
}

dataTable = dataTable[list(selected_columns.keys())].rename(columns=selected_columns)

# Write selected columns to CSV
dataTable.to_csv("data/today_prices.csv", mode="w", index=False)


fileDir = Path(__file__).parent.parent / "data" / "company"
for file in fileDir.glob("*.csv"):
    # first check if data already exist for this date
    existingDf = pd.read_csv(file)
    lastRow = existingDf.iloc[-1]
    lastDate = lastRow["date"]
    if str(lastDate) != str(today):
        symbol = file.stem
        data = dataTable.loc[dataTable["Symbol"] == symbol]
        if len(data) == 1:
            status = getStatus(float(data["Open"].iloc[0]), float(data["Close"].iloc[0]))
            dataRow = [
                [
                    today,
                    float(data["Open"].iloc[0]),
                    float(data["High"].iloc[0]),
                    float(data["Low"].iloc[0]),
                    float(data["Close"].iloc[0]),
                    float(data["Diff %"].iloc[0]),
                    float(data["Vol"].iloc[0]),
                    float(data["Turnover"].iloc[0]),
                    status,
                ]
            ]
            dataframe = pd.DataFrame(dataRow)
            dataframe.to_csv(file, mode="a", header=False, index=False)

