import requests

print("🔍 Testing flexible login (username OR email)...")
print("=" * 60)

url = 'http://localhost:8000/api/auth/login'

# Test 1: Login with username
print("\n1️⃣ Login with username 'Admin':")
response = requests.post(url, data={'username': 'Admin', 'password': 'Admin123'})
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ SUCCESS with username")
else:
    print(f"❌ FAILED: {response.json()}")

# Test 2: Login with email
print("\n2️⃣ Login with email 'admin@trafficdashboard.com':")
response = requests.post(url, data={'username': 'admin@trafficdashboard.com', 'password': 'Admin123'})
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ SUCCESS with email")
else:
    print(f"❌ FAILED: {response.json()}")

# Test 3: Wrong password
print("\n3️⃣ Wrong password test:")
response = requests.post(url, data={'username': 'Admin', 'password': 'WrongPassword'})
print(f"Status: {response.status_code}")
if response.status_code == 401:
    print("✅ Correctly rejected wrong password")
else:
    print(f"❌ FAILED: {response.json()}")
