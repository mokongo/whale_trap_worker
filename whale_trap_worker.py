
# whale_trap_worker.py (Updated with Binance client version fallback and tighter filters)
import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
import re

# === TELEGRAM SETUP ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1002760191193")

# === SYMBOL SETUP ===
def get_perpetual_usdt_symbols():
    try:
        url = "https://data.binance.com/fapi/v1/exchangeInfo"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw_symbols = [
            s["symbol"] for s in data["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
        ]
        filtered = [s for s in raw_symbols if re.fullmatch(r"[A-Z]{4,20}USDT", s)]
        if not filtered:
            print("⚠️ No valid symbols found, using fallback list.")
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        return filtered
    except Exception as e:
        print(f"❌ Error getting symbols: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

symbols = get_perpetual_usdt_symbols()

# === TELEGRAM ALERT ===
def send_telegram_alert(message):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        try:
            response = requests.post(url, json=payload)
            print(f"📤 Telegram response: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")

# === FETCH KLINES ===
def fetch_klines(symbol, interval="15m", limit=100):
    retries = 3
    for attempt in range(retries):
        try:
            url = f"https://data.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            print(f"⚠️ Fetch failed ({response.status_code}), retrying...")
        except Exception as e:
            print(f"❌ Attempt {attempt+1} error for {symbol}: {e}")
        time.sleep(2)
    print(f"🚫 All attempts failed for {symbol}")
    return None

# === ANALYSIS ===
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

# === MAIN WORKER ===
def run_whale_trap_worker():
    print("✅ Whale Trap Worker started (Public Endpoint Mode)...")
    send_telegram_alert("✅ Whale Trap Worker started (Public Endpoint Mode)")
    while True:
        for symbol in symbols:
            analyze_symbol(symbol)
            time.sleep(30)
        print("🔁 Cycle complete. Sleeping 10 minutes...")
        time.sleep(600)

if __name__ == "__main__":
    run_whale_trap_worker()
