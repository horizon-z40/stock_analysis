import akshare as ak
import pandas as pd

def test_hk_pe(symbol):
    print(f"Testing HK PE for {symbol}...")
    try:
        df = ak.stock_hk_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period="全部")
        print(f"HK PE for {symbol}:")
        print(df.head())
    except Exception as e:
        print(f"Error testing HK PE for {symbol}: {e}")

def test_us_pe(symbol):
    print(f"Testing US PE for {symbol}...")
    try:
        df = ak.stock_us_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period="全部")
        print(f"US PE for {symbol}:")
        print(df.head())
    except Exception as e:
        print(f"Error testing US PE for {symbol}: {e}")

if __name__ == "__main__":
    test_hk_pe("01211") # BYD
    test_us_pe("AAPL")  # Apple
