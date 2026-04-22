# Google Maps Integration Setup

This document describes the Google Maps API integration for the Police Supervisor Command Center.

## Features Implemented

### 1. **Live Traffic Layer**
   - Real-time traffic overlay on the map
   - Shows current traffic conditions for the district
   - Enabled by default when the map loads

### 2. **Incident Markers with Severity Color Coding**
   - **Red**: Critical/High severity incidents
   - **Orange**: Medium/Moderate severity incidents
   - **Blue**: Medium severity incidents
   - **Green**: Low severity incidents
   - **Gray**: Unknown severity
   - Markers automatically update as new incidents are reported

### 3. **Incident Selection & Info Windows**
   - Clicking any incident marker displays:
     - Incident title and description
     - Severity level
     - Nearest available officer
     - Real-time ETA from Directions API
     - Distance to incident
     - Current traffic duration estimate

### 4. **Dispatch Console with Route Drawing**
   - When dispatching an officer to an incident:
     - Select an available officer from the dropdown
     - The map automatically calculates the optimal route
     - A blue polyline shows the route from officer's GPS to incident
     - Real-time ETA is displayed including:
       - Duration in traffic (accounting for real traffic)
       - Distance to travel
       - Officer name and ID
   - Route is automatically cleared when modal is closed

### 5. **Directions API Integration**
   - Uses Google Directions API to calculate routes
   - Accounts for real-time traffic conditions
   - Provides accurate ETAs based on current traffic

## Configuration

### Environment Variable Setup

Add the following to your `.env` file:

```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
```

### Getting a Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - **Maps JavaScript API**
   - **Directions API**
   - **Distance Matrix API** (optional, for enhanced routing)
4. Create an API key:
   - Go to "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the key to your `.env` file
5. (Recommended) Restrict your key to:
   - **Application restrictions**: HTTP referrers
   - **API restrictions**: Select only the enabled APIs above

### Security Best Practices

✅ **What we do correctly:**
- API key is stored in `.env` (never committed to git)
- API key is passed to Jinja2 template as a variable
- JavaScript loads the Maps API using the template variable
- Key is never hardcoded in JavaScript

⚠️ **Additional security measures (recommended):**
- Restrict API key to your domain (HTTP referrers)
- Set up billing alerts in Google Cloud Console
- Monitor API usage regularly

## File Changes

### Modified Files

1. **`.env`**
   - Added `GOOGLE_MAPS_API_KEY` configuration variable

2. **`templates/police/supervisor_dashboard.html`**
   - Added route drawing variables:
     - `dispatchRoutePolyline`: Stores the route line
     - `dispatchDirectionsRenderer`: Stores directions renderer
     - `currentDispatchOfficer`: Tracks selected officer
     - `currentDispatchIncident`: Tracks target incident
   
   - Added functions:
     - `drawDispatchRoute(officer, incident)`: Calculates and draws route
     - `clearDispatchRoute()`: Removes route from map
     - `attachDispatchOfficerChangeListener()`: Listens for officer selection
   
   - Enhanced existing functions:
     - `openDispatchModal()`: Initializes map, attaches listeners, clears previous routes
     - `closeDispatchModal()`: Clears routes when modal is closed
     - `submitDispatch()`: Clears routes after successful dispatch
   
   - Updated CSS:
     - Enhanced `.dispatch-feedback` styling for better route info display

3. **`app.py`** (No changes needed)
   - Already passes `google_maps_api_key` to template context

## How to Use

### For Users

1. **Viewing the Command Center**:
   - Navigate to `/police/dashboard`
   - The map displays with traffic layer enabled
   - Active incidents appear as color-coded markers

2. **Clicking an Incident Marker**:
   - Click any incident marker on the map
   - An info window shows incident details
   - See the nearest available officer's ETA

3. **Dispatching an Officer**:
   - Click the "Dispatch" button on an incident
   - Select an available officer from the dropdown
   - **The map automatically draws the route and shows real ETA**
   - Review the calculated route and time
   - Click "Dispatch" to confirm

### For Developers

The integration uses these Google Maps APIs:

```javascript
// Map initialization
new google.maps.Map(element, options)

// Traffic layer
new google.maps.TrafficLayer()

// Route drawing
new google.maps.Polyline(options)

// Route calculation
googleDirectionsService.route(request, callback)

// Directions API libraries
drivingOptions: { trafficModel: google.maps.TrafficModel.BEST_GUESS }
```

## Testing

1. **Verify API Key is set:**
   ```bash
   echo $GOOGLE_MAPS_API_KEY  # Linux/Mac
   echo %GOOGLE_MAPS_API_KEY%  # Windows
   ```

2. **Check browser console for errors:**
   - Open DevTools (F12)
   - Look for console errors related to Google Maps
   - Check Network tab for API requests

3. **Test map functionality:**
   - Verify traffic layer loads (should see colored roads)
   - Click incident markers to see info windows
   - Select officers in dispatch modal to see route drawing

4. **Monitor API usage:**
   - Log into Google Cloud Console
   - Check API usage dashboard under "Directions API"

## Troubleshooting

### Map doesn't load
- **Issue**: White/blank map area
- **Solution**: 
  - Check that `GOOGLE_MAPS_API_KEY` is set in `.env`
  - Restart the server
  - Check browser console for API load errors

### Route not drawing when selecting officer
- **Issue**: No blue line appears when selecting officer
- **Solution**:
  - Ensure officer has GPS coordinates (`latitude`, `longitude` in database)
  - Ensure incident has coordinates
  - Check browser console for Directions API errors
  - Verify Directions API is enabled in Google Cloud Console

### "Google Maps API unavailable" message
- **Issue**: Heatmap refresh label shows this message
- **Solution**:
  - API key not set or incorrect
  - API key doesn't have Maps JavaScript API enabled
  - Check Google Cloud Console for API restrictions

### Rate limiting
- **Issue**: Many API requests failing with HTTP 429
- **Solution**:
  - Set billing quota in Google Cloud Console
  - Reduce refresh frequency in code
  - Check if multiple users are accessing simultaneously

## Performance Considerations

- **Map tile loading**: Initial load may take 2-3 seconds
- **Marker updates**: 100+ markers on map may cause slowdown
- **Route calculations**: Directions API adds ~500ms-1000ms per route
- **Traffic layer**: Updates every 2-5 minutes from Google

## Limitations

- Free tier Directions API has 25,000 requests/day limit
- Each route calculation counts as 1 request
- Traffic data updates are provided by Google (typically 2-5 min delay)
- Polylines may not be visible if zoom is too far out

## API Rate Limits (Free Tier)

- **Directions API**: 25,000 requests/day
- **Maps JavaScript API**: 25,000 requests/day (for each unique user IP)
- **Each operation counts as 1 request**:
  - Map load
  - Route calculation
  - Directions request

## Next Steps

1. Set `GOOGLE_MAPS_API_KEY` in `.env`
2. Restart the Flask server
3. Navigate to `/police/dashboard`
4. Test the map, markers, and dispatch functionality
5. Monitor API usage in Google Cloud Console

## Support

For issues or questions:
- Check the browser console for errors (F12 → Console tab)
- Verify API key and permissions in Google Cloud Console
- Review the JavaScript functions in `supervisor_dashboard.html`
