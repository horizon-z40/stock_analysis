import requests
import json

BASE_URL = "http://127.0.0.1:8080"

def test_api(endpoint):
    url = f"{BASE_URL}{endpoint}"
    print(f"Testing {url}...")
    try:
        resp = requests.get(url, timeout=20)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        if data.get('success'):
            if 'data' in data:
                print(f"Data count: {len(data['data'])}")
                if len(data['data']) > 0:
                    print(f"Sample data: {data['data'][0]}")
            else:
                print(f"Result: {data}")
        else:
            print(f"Error: {data.get('error')}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Test HK Stock
    print("\n--- Testing HK Stock (01211.HK) ---")
    test_api("/api/stock_info/01211.HK")
    test_api("/api/stock_pe/01211.HK")
    
    # Test US Stock
    print("\n--- Testing US Stock (AAPL.US) ---")
    test_api("/api/stock_info/105.AAPL.US")
    test_api("/api/stock_pe/105.AAPL.US")
