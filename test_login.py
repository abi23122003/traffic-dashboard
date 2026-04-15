import requests
import json

print("🔍 Testing login endpoint...")
print("=" * 60)

url = 'http://localhost:8000/api/auth/login'

print("\n1️⃣ Testing login with Admin/Admin123:")
data = {
    'username': 'Admin',
    'password': 'Admin123'
}

response = requests.post(url, data=data)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    token = response.json()['access_token']
    print(f"✅ Login successful!")
    print(f"Token preview: {token[:50]}...")
else:
    print(f"❌ Login failed!")
    print(f"Response: {response.text}")
