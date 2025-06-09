
# whale_trap_worker.py
import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
import os
import time
import random

BINANCE_BASE_URL = os.getenv("BINANCE_HOST", "https://api.binance.com")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

# === TELEGRAM SETUP ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(message):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                print(f"❌ Failed to send Telegram alert: {response.text}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")

def test_binance_connection():
    test_url = f"{BINANCE_BASE_URL}/api/v3/time"
    try:
        r = requests.get(test_url, headers=HEADERS)
        if r.status_code == 200:
            print("✅ Binance API connection successful")
        else:
            print(f"⚠️ Binance API responded with status code {r.status_code}")
    except Exception as e:
        print(f"❌ Binance API connection error: {e}")

# Temporarily hardcode a few high-liquidity symbols for stability
def get_perpetual_usdt_symbols():
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

symbols = get_perpetual_usdt_symbols()

def fetch_binance_klines(symbol, interval="15m", limit=100):
    url = f"{BINANCE_BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Failed to fetch {symbol} from Binance. Status: {response.status_code} - {response.text}")
        return None
    print(f"✅ Data retrieved for {symbol}")
    return response.json()

def safe_fetch_klines(symbol):
    retries = 3
    for attempt in range(retries):
        data = fetch_binance_klines(symbol)
        if data:
            return data
        print(f"🔁 Retrying {symbol} in 5s... (Attempt {attempt+1})")
        time.sleep(5 + random.uniform(1, 3))
    return None

def analyze_symbol(symbol):
    print(f"📊 Analyzing {symbol} ...")
    data = safe_fetch_klines(symbol)
    if not data:
        return

    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])

    df['open'] = df['open'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')

    # OHLC features
    df['body'] = abs(df['close'] - df['open'])
    df['wick'] = df['high'] - df[['close', 'open']].max(axis=1)
    df['tail'] = df[['close', 'open']].min(axis=1) - df['low']

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

    # --- TEST MODE TO FORCE ALERT ---
    if True:
        signal = f"🚨 TEST SIGNAL on {symbol}"
        print(signal)
        with open("trap_log.txt", "a") as f:
           # f.write(f"{df['time'].iloc[-1]} - {signal}")
             f.write(f"{df['time'].iloc[-1]} - {signal}\n")
        send_telegram_alert(signal)
        return

    rsi_spike = last_rsi > 50 and prev_rsi < 30
    price_recovery = last_close > df['ema20'].iloc[-1]
    obv_surge = (last_obv - prev_obv) > df['volume'].mean() * 2
    atr_spike = last_atr > df['atr'].rolling(window=20).mean().iloc[-1] * 1.5

    if rsi_spike and price_recovery and obv_surge and atr_spike:
        signal = f"🚨 Whale trap signal detected on {symbol} at {last_close:.5f}"
        print(signal)
        with open("trap_log.txt", "a") as f:
            f.write(f"{df['time'].iloc[-1]} - {signal}\n")
        send_telegram_alert(signal)
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
    test_binance_connection()
    while True:
        for symbol in symbols:
            analyze_symbol(symbol)
            time.sleep(29)  # Delay to avoid throttling
        print("🔁 Cycle complete. Sleeping 10 minutes before next scan...")
        time.sleep(60)

if __name__ == "__main__":
    run_whale_trap_worker()
