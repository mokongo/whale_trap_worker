
import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
import os

BINANCE_BASE_URL = "https://api.binance.com"

def get_perpetual_usdt_symbols():
    url = f"{BINANCE_BASE_URL}/fapi/v1/exchangeInfo"
    response = requests.get(url)
    if response.status_code != 200:
        print("❌ Failed to fetch exchange info")
        return []
    data = response.json()
    return [
        s["symbol"]
        for s in data["symbols"]
        if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
    ]

symbols = symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def fetch_binance_klines(symbol, interval="15m", limit=100):
    url = f"{BINANCE_BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Failed to fetch {symbol} from Binance")
        return None
    return response.json()

def analyze_symbol(symbol):
    print(f"📊 Analyzing {symbol} ...")
    data = fetch_binance_klines(symbol)
    if not data:
        return

    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])

    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
    df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)

    last_rsi = df['rsi'].iloc[-1]
    prev_rsi = df['rsi'].iloc[-2]
    last_close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    last_obv = df['obv'].iloc[-1]
    prev_obv = df['obv'].iloc[-2]
    last_atr = df['atr'].iloc[-1]

    rsi_spike = last_rsi > 50 and prev_rsi < 30
    price_recovery = last_close > df['ema20'].iloc[-1]
    obv_surge = (last_obv - prev_obv) > df['volume'].mean() * 2
    atr_spike = last_atr > df['atr'].rolling(window=20).mean().iloc[-1] * 1.5

    if rsi_spike and price_recovery and obv_surge and atr_spike:
        print(f"🚨 Whale trap signal detected on {symbol} at {last_close:.5f}")
        with open("trap_log.txt", "a") as f:
            f.write(f"{df['time'].iloc[-1]} - Whale trap detected on {symbol} at {last_close:.5f}\n")
    else:
        print("⚠️ No trap signal this cycle.")

    plt.figure(figsize=(10, 6))
    plt.subplot(3, 1, 1)
    plt.plot(df['time'], df['close'], label='Close', color='blue')
    plt.plot(df['time'], df['ema20'], label='EMA 20', linestyle='--')
    plt.plot(df['time'], df['ema50'], label='EMA 50', linestyle='--')
    plt.title(f"{symbol} Price with EMAs")
    plt.legend()
    plt.grid(True)

    plt.subplot(3, 1, 2)
    plt.plot(df['time'], df['obv'], label='OBV', color='green')
    plt.title("On Balance Volume")
    plt.grid(True)

    plt.subplot(3, 1, 3)
    plt.plot(df['time'], df['atr'], label='ATR', color='red')
    plt.title("ATR Volatility")
    plt.grid(True)

    plt.tight_layout()
    chart_path = f"chart_{symbol}.png"
    plt.savefig(chart_path)
    plt.close()
    print(f"✅ Saved chart as {chart_path}")

def run_whale_trap_worker():
    print("✅ Whale Trap Worker started...")
    for symbol in symbols:
        analyze_symbol(symbol)

if __name__ == "__main__":
    run_whale_trap_worker()
