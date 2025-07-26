from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

start_date = '2020-01-01' # 5년치 데이터
stock_symbol = "AAPL"


df = yf.download(stock_symbol, start=start_date, progress=False, auto_adjust=False)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.droplevel('Ticker')

df = df[df['Close'].notna()]
df = df.sort_index()

if len(df) >= 252:
    high_52_week = df['High'].tail(252).max()
else:
    high_52_week = df['High'].max()

current_price = df['Close'].iloc[-1]
print(current_price)