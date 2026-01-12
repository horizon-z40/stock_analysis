
import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime

def load_stock_data(stock_code):
    data_dir = 'data'
    years = ['2021', '2022', '2023']
    dfs = []
    for year in years:
        file_path = os.path.join(data_dir, f"{year}_by_day", f"{stock_code}.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            dfs.append(df)
    
    if not dfs:
        return None
    
    df = pd.concat(dfs, ignore_index=True)
    df['trade_time'] = pd.to_datetime(df['trade_time'])
    df = df.sort_values('trade_time')
    return df

def backtest_strategy(df, buy_rule, sell_rule, initial_capital=1000000):
    buy_start = pd.to_datetime('2021-01-01')
    buy_end = pd.to_datetime('2022-12-31')
    sell_start = pd.to_datetime('2023-01-01')
    sell_end = pd.to_datetime('2023-12-31')
    
    # Calculate indicators
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    
    # RSI calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Buy signals in 2021-2022
    buy_mask = (df['trade_time'] >= buy_start) & (df['trade_time'] <= buy_end)
    buy_signals = df[buy_mask & buy_rule(df)]
    
    if buy_signals.empty:
        return 0, None, None
    
    # Take the first buy signal
    buy_signal = buy_signals.iloc[0]
    buy_price = buy_signal['close']
    buy_date = buy_signal['trade_time']
    
    # Sell signals in 2023
    sell_mask = (df['trade_time'] >= sell_start) & (df['trade_time'] <= sell_end)
    sell_signals = df[sell_mask & sell_rule(df)]
    
    if sell_signals.empty:
        # If no sell signal, sell at the end of 2023
        sell_signals = df[sell_mask]
        if sell_signals.empty:
            return 0, buy_date, None
        sell_signal = sell_signals.iloc[-1]
    else:
        # Take the first sell signal
        sell_signal = sell_signals.iloc[0]
        
    sell_price = sell_signal['close']
    sell_date = sell_signal['trade_time']
    
    return (sell_price - buy_price) / buy_price * 100, buy_date, sell_date

# Define some rules
rules = [
    {
        'name': 'RSI极度超跌策略',
        'buy': lambda df: df['rsi'] < 20,
        'sell': lambda df: df['rsi'] > 60,
        'desc': '买入：RSI < 20（极度超跌）；卖出：2023年内 RSI > 60（回暖）。'
    },
    {
        'name': '双底超跌策略',
        'buy': lambda df: (df['close'] < df['close'].shift(20) * 0.8) & (df['close'] < df['ma60'] * 0.9),
        'sell': lambda df: df['close'] > df['ma60'],
        'desc': '买入：20日内跌幅超过20%且低于60日均线10%；卖出：2023年内回到60日均线。'
    },
    {
        'name': '价值回归策略',
        'buy': lambda df: (df['close'] < df['ma60'] * 0.8) & (df['rsi'] < 30),
        'sell': lambda df: (df['close'] > df['ma60']) | (df['rsi'] > 70),
        'desc': '买入：价格低于60日线20%且RSI < 30；卖出：2023年内回归60日线或RSI > 70。'
    }
]

stocks_to_test = ['000001.SZ', '000002.SZ', '000725.SZ', '600036.SH', '600519.SH']
# Filter stocks that actually exist in the data
existing_stocks = []
for s in stocks_to_test:
    if os.path.exists(os.path.join('data', '2021_by_day', f"{s}.csv")):
        existing_stocks.append(s)

results = []
for rule in rules:
    stock_returns = []
    for stock in existing_stocks:
        df = load_stock_data(stock)
        if df is not None:
            ret, bd, sd = backtest_strategy(df, rule['buy'], rule['sell'])
            if bd is not None:
                stock_returns.append(ret)
    
    avg_return = np.mean(stock_returns) if stock_returns else -100
    results.append({
        'name': rule['name'],
        'avg_return': avg_return,
        'desc': rule['desc']
    })

results.sort(key=lambda x: x['avg_return'], reverse=True)

print("Backtest Results:")
for r in results:
    print(f"Strategy: {r['name']}, Avg Return: {r['avg_return']:.2f}%, Desc: {r['desc']}")
