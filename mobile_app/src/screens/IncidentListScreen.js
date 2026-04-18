import React, { useCallback, useEffect, useState } from 'react';
import { Linking, SafeAreaView, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { clearSession } from '../storage/auth';
import { getMobileIncidents, getWsUrls, openMapsDeepLink } from '../api/client';
import useLiveSocket from '../hooks/useLiveSocket';

export default function IncidentListScreen({ navigation, authContext }) {
  const [incidents, setIncidents] = useState([]);

  const loadIncidents = useCallback(async () => {
    const data = await getMobileIncidents(authContext.session.token);
    setIncidents(Array.isArray(data) ? data : []);
  }, [authContext.session.token]);

  useEffect(() => {
    loadIncidents().catch((err) => console.log(err.message));
  }, [loadIncidents]);

  useLiveSocket(getWsUrls('live').incidentWs, (payload) => {
    if (payload.type === 'incident_update') {
      setIncidents((prev) => {
        const idx = prev.findIndex((i) => String(i.id) === String(payload.data.id));
        if (idx >= 0) {
          const cloned = [...prev];
          cloned[idx] = payload.data;
          return cloned;
        }
        return [payload.data, ...prev];
      });
    }
  });

  const logout = async () => {
    await clearSession();
    authContext.setSession(null);
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.title}>Assigned Incidents</Text>
        <TouchableOpacity onPress={logout}><Text style={styles.logout}>Logout</Text></TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={styles.list}>
        {incidents.map((incident) => (
          <TouchableOpacity
            key={String(incident.id)}
            style={styles.card}
            onPress={() => navigation.navigate('IncidentDetail', { incident })}
          >
            <Text style={styles.cardTitle}>{incident.title || 'Incident'}</Text>
            <Text style={styles.meta}>Severity: {String(incident.severity || '').toUpperCase()}</Text>
            <Text style={styles.meta}>Location: {incident.lat}, {incident.lng}</Text>
            <View style={styles.actions}>
              <TouchableOpacity
                style={styles.btn}
                onPress={() => navigation.navigate('Chat', { incidentId: String(incident.id) })}
              >
                <Text style={styles.btnText}>Open Chat</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.btn}
                onPress={() => Linking.openURL(openMapsDeepLink(incident.lat, incident.lng))}
              >
                <Text style={styles.btnText}>Navigate</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1a26' },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: { color: '#fff', fontSize: 20, fontWeight: '700' },
  logout: { color: '#ff8d8d', fontWeight: '600' },
  list: { padding: 14 },
  card: {
    backgroundColor: '#16283a',
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
  },
  cardTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  meta: { color: '#9ab0c5', marginTop: 3 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 10 },
  btn: { backgroundColor: '#1f4f75', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 10 },
  btnText: { color: '#fff', fontSize: 12, fontWeight: '600' },
});
