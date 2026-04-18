import Constants from 'expo-constants';

const API_BASE_URL =
  Constants.expoConfig?.extra?.API_BASE_URL ||
  Constants.manifest2?.extra?.expoClient?.extra?.API_BASE_URL ||
  'http://127.0.0.1:5000';

async function request(path, options = {}, token) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const text = await res.text();
  let json;
  try {
    json = text ? JSON.parse(text) : {};
  } catch {
    json = { raw: text };
  }

  if (!res.ok) {
    throw new Error(json.detail || `Request failed: ${res.status}`);
  }

  return json;
}

export function loginOfficer(officerId) {
  return request('/api/mobile/login', {
    method: 'POST',
    body: JSON.stringify({ officer_id: Number(officerId) }),
  });
}

export function registerDeviceToken(officerId, deviceToken, token) {
  return request(
    '/api/mobile/device-token',
    {
      method: 'POST',
      body: JSON.stringify({ officer_id: Number(officerId), device_token: deviceToken }),
    },
    token
  );
}

export function getMobileIncidents(token) {
  return request('/api/mobile/incidents', { method: 'GET' }, token);
}

export function updateOfficerStatus(payload, token) {
  return request('/api/mobile/officer/status', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, token);
}

export function respondDispatch(payload, token) {
  return request('/api/mobile/dispatch/respond', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, token);
}

export function getWsUrls(incidentId) {
  return {
    incidentWs: `ws://${API_BASE_URL.replace(/^https?:\/\//, '')}/ws/incidents`,
    chatWs: `ws://${API_BASE_URL.replace(/^https?:\/\//, '')}/ws/chat/${incidentId}`,
  };
}

export function openMapsDeepLink(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
}
