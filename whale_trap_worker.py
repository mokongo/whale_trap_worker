# whale_trap_worker.py (Updated with retry + safety checks)
import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
from binance.client import Client

# === TELEGRAM SETUP ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1002760191193")  # Updated to full channel ID format

# === BINANCE API SETUP ===
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

def send_telegram_alert(message):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        try:
            response = requests.post(url, json=payload)
            print(f"📤 Telegram response: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")

def get_perpetual_usdt_symbols():
    try:
        exchange_info = client.futures_exchange_info()
        return [
            s["symbol"] for s in exchange_info["symbols"]
            if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT"
        ]
    except Exception as e:
        print(f"❌ Error getting symbols: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

symbols = get_perpetual_usdt_symbols()

def fetch_klines(symbol, interval="15m", limit=100):
    retries = 3
    for attempt in range(retries):
        try:
            klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            if klines and len(klines) >= 30:
                return klines
        except Exception as e:
            print(f"❌ Attempt {attempt+1}: Kline fetch error for {symbol}: {e}")
            time.sleep(2)
    print(f"🚫 All attempts failed for {symbol}")
    return None

def analyze_symbol(symbol):
    print(f"📊 Analyzing {symbol} ...")
    data = fetch_klines(symbol)
    if not data:
        return

    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    if df.shape[0] < 30:
        print(f"⚠️ Not enough data to analyze {symbol}")
        return

    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
    df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)

    last_rsi, prev_rsi = df['rsi'].iloc[-1], df['rsi'].iloc[-2]
    last_close = df['close'].iloc[-1]
    last_obv, prev_obv = df['obv'].iloc[-1], df['obv'].iloc[-2]
    last_atr = df['atr'].iloc[-1]
    atr_mean = df['atr'].rolling(window=20).mean().iloc[-1]

    rsi_spike = last_rsi > 50 and prev_rsi < 30
    price_recovery = last_close > df['ema20'].iloc[-1]
    obv_surge = (last_obv - prev_obv) > df['volume'].mean() * 2
    atr_spike = last_atr > atr_mean * 1.5

    if rsi_spike and price_recovery and obv_surge and atr_spike:
        signal = f"🚨 Whale trap signal detected on {symbol} at {last_close:.2f}"
        print(signal)
        send_telegram_alert(signal)
    else:
        print("⚠️ No signal.")

def run_whale_trap_worker():
    print("✅ Whale Trap Worker started (Binance Client mode)...")
    send_telegram_alert("✅ Whale Trap Worker started (Binance Client mode)")
    while True:
        for symbol in symbols:
            analyze_symbol(symbol)
            time.sleep(29)
        print("🔁 Cycle complete. Sleeping 10 minutes...")
        time.sleep(20)

if __name__ == "__main__":
    run_whale_trap_worker()
