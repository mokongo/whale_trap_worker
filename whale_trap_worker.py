# whale_trap_worker.py (Telegram-triggered headless mode)
import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
import re
from flask import Flask, request, jsonify
from threading import Thread

# === TELEGRAM SETUP ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1002760191193")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# === BINANCE API KEYS ===
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")

# === SYMBOL SETUP ===
def get_perpetual_usdt_symbols():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-MBX-APIKEY": BINANCE_API_KEY
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw_symbols = [
            s["symbol"] for s in data["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
        ]
        filtered = [s for s in raw_symbols if re.fullmatch(r"[A-Z]{4,20}USDT", s)]
        return filtered or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    except Exception as e:
        print(f"❌ Error getting symbols: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

symbols = get_perpetual_usdt_symbols()

# === TELEGRAM ALERT ===
def send_telegram_alert(message):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"{TELEGRAM_API}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"❌ Telegram error: {e}")

# === FETCH KLINES ===
def fetch_klines(symbol, interval="15m", limit=100):
    retries = 3
    for attempt in range(retries):
        try:
            url = f"https://data.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-MBX-APIKEY": BINANCE_API_KEY
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Fetch failed ({response.status_code}), retrying...")
        except Exception as e:
            print(f"❌ Fetch error: {e}")
        time.sleep(2)
    print(f"❌ All attempts failed for {symbol}")
    return None

# === ANALYSIS ===
def analyze_symbol(symbol):
    print(f"📊 Analyzing {symbol} ...")
    data = fetch_klines(symbol)
    if not data:
        return f"❌ No data for {symbol}."

    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'])

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    if df.shape[0] < 30:
        return f"⚠️ Not enough data for {symbol}."

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
        return f"🚨 Whale trap detected on {symbol} at ${last_close:.2f}"
    return f"No signal for {symbol}."

# === FLASK TELEGRAM BOT HANDLER ===
app = Flask(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
def telegram_webhook():
    msg = request.get_json()
    chat_id = msg['message']['chat']['id']
    text = msg['message'].get('text', '').strip()

    if text.startswith("/trap"):
        parts = text.split()
        targets = parts[1:] if len(parts) > 1 else symbols[:5]
        targets = [s.upper().replace("/", "") for s in targets if s.upper().endswith("USDT")]
        if not targets:
            targets = symbols[:5]
        response = "🕵️ Starting trap analysis...\n"
        for s in targets:
            result = analyze_symbol(s)
            response += f"{s}: {result}\n"
        send_telegram_alert(response)
    else:
        send_telegram_alert("🤖 Available command: /trap [optional symbols]")

    return jsonify(success=True)

# === RUN BOT WITH FLASK SERVER ===
def run_bot():
    print("✅ Whale Trap Bot Webhook mode ready...")
    send_telegram_alert("🟢 Whale Trap Bot is online")
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    Thread(target=run_bot).start()
