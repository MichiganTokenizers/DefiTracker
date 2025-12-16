#!/usr/bin/env python3
"""Test FlareScan API to get contract ABIs"""
import requests
import json
import sys

# Test contracts
contracts = {
    "Lens": "0x553e7b78812D69fA30242E7380417781125C7AC7",
    "Comptroller": "0x35aFf580e53d9834a3a0e21a50f97b942Aba8866",
    "Unitroller": "0x15F69897E6aEBE0463401345543C26d1Fd994abB",
    "ISO FXRP": "0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3"
}

def test_api(contract_address: str, api_key: str = None):
    """Test FlareScan API endpoint"""
    url = f"https://api.flarescan.com/api?module=contract&action=getabi&address={contract_address}"
    if api_key:
        url += f"&apikey={api_key}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }
    
    print(f"\nTesting: {contract_address}")
    print(f"URL: {url[:100]}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)[:300]}")
                
                if data.get('status') == '1' and data.get('result'):
                    abi = json.loads(data['result'])
                    functions = [item for item in abi if item.get('type') == 'function']
                    print(f"✓ SUCCESS! Found {len(functions)} functions")
                    return abi
                else:
                    print(f"✗ Status: {data.get('status')}, Message: {data.get('message', 'N/A')}")
            except json.JSONDecodeError as e:
                print(f"✗ Invalid JSON: {e}")
                print(f"Response text: {response.text[:200]}")
        else:
            print(f"✗ HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    return None

if __name__ == "__main__":
    print("=" * 60)
    print("FlareScan API Test")
    print("=" * 60)
    print("\nNote: If you get 403/202 errors, you may need an API key.")
    print("Get one free at: https://flarescan.com/myapikey")
    print("\nTo use with API key:")
    print("  python test_flarescan_api.py YOUR_API_KEY")
    print("=" * 60)
    
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    if api_key:
        print(f"\nUsing API key: {api_key[:10]}...")
    else:
        print("\nNo API key provided - testing without one")
    
    results = {}
    for name, address in contracts.items():
        abi = test_api(address, api_key)
        results[name] = abi is not None
    
    print("\n" + "=" * 60)
    print("Summary:")
    for name, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {name}")
    
    if not any(results.values()):
        print("\n⚠ No ABIs retrieved. Possible reasons:")
        print("  1. API key required (get free key at flarescan.com/myapikey)")
        print("  2. Contracts not verified on FlareScan")
        print("  3. Rate limiting or API issues")

