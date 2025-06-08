# whale_trap_worker.py
# Background worker version – auto-runs every hour with real-time technical data from Binance (12h–48h filter)

import pandas as pd
import requests
import os
import time
from io import BytesIO
import ta
import numpy as np
import matplotlib.pyplot as plt

# ------------------------------
# TRAP DETECTION LOGIC
# ------------------------------
def detect_whale_traps(data):
    df = pd.DataFrame(data)

    def trap_score(row):
        score = 0
        score += 1 if row['Max Potential Gain %'] >= 10 else 0
        score += 1 if -3 < row['Price Change % 24 hours'] < 5 else 0
        score += 1 if 40 < row['Relative Strength Index (14) 1 day'] < 65 else 0
        score += 1 if 10 < row['Commodity Channel Index (20) 1 day'] < 100 else 0
        score += 1 if row['OBV Trend (12h delta)'] > 0 else 0
        score += 1 if row['Volatility Spike (ATR%)'] > 3 else 0
        score += 1 if abs(row.get('BTC Correlation', 0)) < 0.3 else 0
        score += 1 if row.get('Volume Surge Ratio', 0) > 1.5 else 0
        score += 1 if row.get('EMA 20') > row.get('EMA 50') else 0
        return score

    df['trap_score'] = df.apply(trap_score, axis=1)
    top_traps = df[df['trap_score'] >= 4].sort_values(by='trap_score', ascending=False).head(10)
    return df, top_traps

# ------------------------------
# CHART GENERATOR
# ------------------------------
def generate_chart(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=48"
    res = requests.get(url).json()
    df = pd.DataFrame(res, columns=[
        'time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'count',
        'buy_base_volume', 'buy_quote_volume', 'ignore']
    )
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['time'] = pd.to_datetime(df['time'], unit='ms')

    obv = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    atr = ta.volatility.AverageTrueRange(df['high'].astype(float), df['low'].astype(float), df['close'], window=14).average_true_range()
    ema9 = ta.trend.ema_indicator(df['close'], window=9)
    ema20 = ta.trend.ema_indicator(df['close'], window=20)
    ema50 = ta.trend.ema_indicator(df['close'], window=50)

    plt.figure(figsize=(8, 6))
    plt.subplot(3, 1, 1)
    plt.plot(df['time'], df['close'], label='Price', color='blue')
    plt.plot(df['time'], ema9, label='EMA 9', color='orange', linestyle='--')
    plt.plot(df['time'], ema20, label='EMA 20', color='green', linestyle='--')
    plt.plot(df['time'], ema50, label='EMA 50', color='red', linestyle='--')
    plt.title(f"{symbol} 15m Price + MAs")
    plt.legend()
    plt.grid(True)

    plt.subplot(3, 1, 2)
    plt.plot(df['time'], obv, label='OBV', color='green')
    plt.title("On-Balance Volume")
    plt.grid(True)

    plt.subplot(3, 1, 3)
    plt.plot(df['time'], atr, label='ATR', color='red')
    plt.title("ATR (Volatility)")
    plt.tight_layout()
    plt.grid(True)

    chart_path = f"{symbol}_chart.png"
    plt.savefig(chart_path)
    plt.close()
    return chart_path
    
    def run_whale_trap_worker():
    # All your worker logic goes here
    # for example: fetch data, calculate indicators, send alerts
    pass
    def run_whale_trap_worker():
    print("🚀 Worker environment is running successfully!")




# The rest of the script remains unchanged and will use these new indicators where needed.
