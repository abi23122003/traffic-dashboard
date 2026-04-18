# Quick Start: Google Maps Integration

## 1️⃣ Get Your API Key (2 minutes)

1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Enable APIs:
   - Maps JavaScript API
   - Directions API
4. Create an API key:
   - Credentials → Create Credentials → API Key
   - Copy the key

## 2️⃣ Add API Key to .env (1 minute)

Edit `.env` file and add your API key:

```env
GOOGLE_MAPS_API_KEY=your_copied_api_key_here
```

Save the file.

## 3️⃣ Restart Server

```bash
# Stop current server (Ctrl+C if running)
# Restart with:
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## 4️⃣ Test It

1. Navigate to http://localhost:8000/police/dashboard
2. You should see:
   - ✅ Map with streets and roads
   - ✅ Traffic layer (colored roads showing traffic)
   - ✅ Red/Orange/Blue/Green incident markers
3. Click an incident marker → See incident info with ETA
4. Click "Dispatch" on an incident → Select officer → See route line and ETA

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Map is blank/white | Check that GOOGLE_MAPS_API_KEY is set and restart server |
| No traffic colors | API key doesn't have Maps JavaScript API enabled |
| Route not drawing | Officer or incident missing GPS coordinates |
| "API unavailable" message | Restart server after adding API key |

## What's New

- 🗺️ Live traffic overlay on the map
- 📍 Color-coded incident markers by severity
- 🛣️ Route drawing when dispatching officers
- ⏱️ Real ETA calculations using Google Directions API
- 🔐 API key securely stored in .env (never in code)

## Need Help?

See `GOOGLE_MAPS_SETUP.md` for detailed documentation.
