# Real-Time Traffic Congestion Analysis Dashboard

A comprehensive web application for real-time traffic route analysis with ML-powered congestion predictions, cost optimization, and interactive visualization.

## Overview

This project provides a full-stack solution for analyzing traffic routes using:
- **TomTom API** for real-time routing and geocoding
- **FastAPI** backend with REST endpoints
- **Machine Learning** (RandomForest) for congestion prediction
- **Interactive Frontend** with Leaflet maps
- **SQLite Database** for persistence
- **Power BI Integration** (optional) for streaming dashboards

## Features

- 🔍 **Autocomplete Search**: Real-time place suggestions using TomTom Search API
- 🗺️ **Route Analysis**: Compare multiple route alternatives with detailed metrics
- 💰 **Cost Calculation**: Deterministic algorithm considering time, delay, and distance
- 🤖 **ML Predictions**: RandomForest model predicts congestion levels
- 📊 **Interactive Maps**: Visualize routes on Leaflet maps with polylines
- 💾 **Data Persistence**: SQLite database stores all analysis results
- 📈 **Power BI Integration**: Optional streaming to Power BI dashboards

## Project Structure

```
TrafficDashboard/
├── app.py                 # FastAPI backend with endpoints
├── utils.py               # Unified TomTom API helpers and utilities
├── db.py                  # SQLAlchemy database models and persistence
├── model_train.py         # ML model training script
├── push_to_powerbi.py     # Optional Power BI push helper
├── test_utils.py          # Unit tests for utility functions
├── test_cost.py           # Cost calculation examples
├── templates/
│   └── index.html         # Frontend HTML with Leaflet map
├── static/
│   └── app.js             # Frontend JavaScript
├── requirements.txt       # Python dependencies
├── demo_run.sh            # Demo script (Linux/Mac)
├── demo_run.bat           # Demo script (Windows)
├── README.md              # This file
└── SECOND_REVIEW.md       # Review checklist and documentation
```

## Setup & Installation

### 1. Prerequisites

- Python 3.11 or higher
- TomTom API key ([Get one here](https://developer.tomtom.com/))

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```env
# Required
TOMTOM_KEY=your_tomtom_api_key_here

# Optional
DB_PATH=traffic_analysis.db
MODEL_PATH=rf_model.pkl
OUTPUT_CSV=traffic_results.csv

# Power BI (optional)
POWERBI_PUSH_ENABLED=false
POWERBI_PUSH_URL=https://api.powerbi.com/beta/...
```

### 4. Initialize Database

```bash
python -c "from db import init_db; init_db()"
```

### 5. Train ML Model (Optional)

If you have historical data in `traffic_results.csv`:

```bash
python model_train.py
```

The model requires at least 24 samples. It will be saved to `rf_model.pkl` and automatically loaded by the API.

## Running the Application

### Quick Start (Demo Script)

**Windows:**
```bash
demo_run.bat
```

**Linux/Mac:**
```bash
chmod +x demo_run.sh
./demo_run.sh
```

### Manual Start

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Then open: http://localhost:8000

## API Endpoints

### GET `/`
Serves the frontend HTML page.

### GET `/health`
Health check endpoint. Returns server status and ML model loading state.

### GET `/autocomplete?q={query}`
Get autocomplete suggestions for place names.

**Example:**
```bash
curl "http://localhost:8000/autocomplete?q=Chennai"
```

**Response:**
```json
{
  "suggestions": [
    {
      "text": "Chennai, Tamil Nadu, India",
      "address": {...},
      "position": {"lat": 13.0827, "lon": 80.2707}
    }
  ]
}
```

### POST `/analyze-route`
Analyze route alternatives with cost calculation and ML predictions.

**Request Body:**
```json
{
  "origin": "Guindy, Chennai",
  "destination": "Velachery, Chennai",
  "maxAlternatives": 3,
  "alpha": 1.0,
  "beta": 0.5,
  "gamma": 0.001
}
```

**Or with coordinates:**
```json
{
  "origin": {"lat": 13.0106, "lon": 80.2128},
  "destination": {"lat": 12.9857, "lon": 80.2209},
  "maxAlternatives": 3
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/analyze-route \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Guindy, Chennai",
    "destination": "Velachery, Chennai"
  }'
```

**Response:**
```json
{
  "origin": {"name": "Guindy, Chennai", "lat": 13.0106, "lon": 80.2128},
  "destination": {"name": "Velachery, Chennai", "lat": 12.9857, "lon": 80.2209},
  "analyzed_routes": [
    {
      "route_index": 0,
      "travel_time_s": 1200,
      "no_traffic_s": 900,
      "delay_s": 300,
      "length_m": 8500,
      "congestion_ratio": 1.33,
      "calculated_cost": 25.5,
      "ml_predicted_congestion": 1.28,
      "geometry": [[lat, lon], ...]
    }
  ],
  "best_route_index": 0,
  "best_route": {...},
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## Cost Calculation Algorithm

The deterministic cost function is:

```
cost = α × (travel_time_s / 60) + β × (delay_s / 60) + γ × (distance_m / 1000)
```

Where:
- **α (alpha)**: Weight for travel time (default: 1.0)
- **β (beta)**: Weight for delay/congestion (default: 0.5)
- **γ (gamma)**: Weight for distance (default: 0.001)

**Example Calculation:**
- Travel time: 1200s (20 min)
- Delay: 300s (5 min)
- Distance: 8500m (8.5 km)
- Cost = 1.0 × 20 + 0.5 × 5 + 0.001 × 8.5 = **22.5085**

Test the cost function:
```bash
python test_cost.py
```

## ML Model Training

### Features Used

- `hour`: Hour of day (0-23)
- `weekday`: Day of week (0-6)
- `is_weekend`: Binary weekend indicator
- `distance_km`: Route distance in kilometers
- `route_index`: Route alternative index
- `travel_time_s`: Travel time in seconds
- `no_traffic_s`: No-traffic travel time
- `delay_s`: Traffic delay
- `rolling_mean_congestion`: Rolling average (if enough data)
- `rolling_std_congestion`: Rolling standard deviation (if enough data)

### Training

```bash
python model_train.py
```

The script will:
1. Load data from `traffic_results.csv`
2. Engineer features
3. Train RandomForestRegressor
4. Evaluate with MAE and R² metrics
5. Save model to `rf_model.pkl`

### Model Evaluation

The training script outputs:
- **MAE (Mean Absolute Error)**: Average prediction error
- **R² Score**: Coefficient of determination (1.0 = perfect)
- **Feature Importances**: Which features matter most

## Testing

Run unit tests:
```bash
python test_utils.py
```

Test cost calculation examples:
```bash
python test_cost.py
```

## Power BI Integration (Optional)

### Setup

1. Create a streaming dataset in Power BI
2. Get the Push URL from dataset settings
3. Add to `.env`:
   ```env
   POWERBI_PUSH_ENABLED=true
   POWERBI_PUSH_URL=https://api.powerbi.com/beta/...
   ```

### Usage

The `push_to_powerbi.py` helper can be imported and used:

```python
from push_to_powerbi import push_analysis_result

result = push_analysis_result({
    "timestamp": "2025-01-15T10:30:00Z",
    "route_id": "Guindy→Velachery",
    "travel_time_s": 1200,
    "no_traffic_s": 900,
    "delay_s": 300,
    "length_m": 8500,
    "calculated_cost": 25.5,
    "ml_predicted": 1.28
})
```

## Database Schema

The `analysis_results` table stores:

- `id`: Primary key
- `timestamp`: Analysis timestamp (UTC)
- `route_id`: Route identifier
- `origin`: Origin location (JSON string)
- `destination`: Destination location (JSON string)
- `travel_time_s`: Travel time in seconds
- `no_traffic_s`: No-traffic time in seconds
- `delay_s`: Traffic delay in seconds
- `length_m`: Route length in meters
- `calculated_cost`: Computed cost value
- `ml_predicted`: ML-predicted congestion (nullable)
- `raw_json`: Full route JSON (nullable)

## Development

### Code Structure

- **utils.py**: Reusable TomTom API functions with retry logic
- **db.py**: SQLAlchemy models and database operations
- **app.py**: FastAPI routes and business logic
- **model_train.py**: ML training pipeline
- **Frontend**: Vanilla JavaScript with Leaflet for maps

### Adding New Features

1. **New API endpoint**: Add route in `app.py`
2. **New utility function**: Add to `utils.py`
3. **Database changes**: Update `db.py` models and run migrations
4. **Frontend changes**: Modify `templates/index.html` and `static/app.js`

## Troubleshooting

### "TOMTOM_KEY not set"
- Ensure `.env` file exists with `TOMTOM_KEY=your_key`

### "No routes found"
- Check origin/destination coordinates are valid
- Verify TomTom API key has routing permissions

### "Model not loaded"
- Train model first: `python model_train.py`
- Ensure `rf_model.pkl` exists in project root

### Frontend not loading
- Check `templates/index.html` exists
- Verify static files are served correctly
- Check browser console for errors

## License

This project is for educational/academic purposes.

## Author

Sanjaykumar S | Reg No: 67223200109  
Guide: Mrs. Arockia Xaiver Annie  
Anna University – Center for Distance Education, Chennai
#   t r a f f i c - d a s h b o a r d  
 