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
