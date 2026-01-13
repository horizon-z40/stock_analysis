import akshare as ak
import pandas as pd

def test_us_pe(symbol):
    print(f"Testing US PE for {symbol}...")
    try:
        df = ak.stock_us_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period="全部")
        print(f"US PE for {symbol}:")
        if df is not None:
            print(df.head())
        else:
            print("Result is None")
    except Exception as e:
        print(f"Error testing US PE for {symbol}: {e}")

if __name__ == "__main__":
    test_us_pe("105.AAPL")
    test_us_pe("AAPL")
