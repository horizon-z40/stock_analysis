import requests

def test_eastmoney(secid):
    url = 'https://push2.eastmoney.com/api/qt/stock/get'
    params = {
        'secid': secid,
        'fields': 'f43,f57,f58,f59,f116,f162,f163,f167'
    }
    print(f"Testing Eastmoney for {secid}...")
    try:
        resp = requests.get(url, params=params, timeout=8)
        print(f"Response for {secid}:")
        print(resp.json())
    except Exception as e:
        print(f"Error for {secid}: {e}")

if __name__ == "__main__":
    test_eastmoney("116.01211") # BYD HK
    test_eastmoney("105.AAPL")   # Apple US
