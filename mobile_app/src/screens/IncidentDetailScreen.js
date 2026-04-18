import React, { useState } from 'react';
import { Alert, Linking, SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { openMapsDeepLink, respondDispatch, updateOfficerStatus } from '../api/client';

const ACTIONS = [
  { key: 'accept', label: 'Accept Dispatch' },
  { key: 'reject', label: 'Reject Dispatch' },
  { key: 'en_route', label: 'Mark En Route' },
  { key: 'on_scene', label: 'Mark On Scene' },
  { key: 'completed', label: 'Mark Completed' },
];

export default function IncidentDetailScreen({ route, authContext }) {
  const { incident } = route.params;
  const [busy, setBusy] = useState(false);

  const act = async (action) => {
    try {
      setBusy(true);
      const payload = {
        officer_id: authContext.session.officer.id,
        incident_id: String(incident.id),
        action,
      };
      await respondDispatch(payload, authContext.session.token);

      if (action === 'en_route') {
        await updateOfficerStatus(
          {
            officer_id: authContext.session.officer.id,
            incident_id: String(incident.id),
            status: 'en_route',
          },
          authContext.session.token
        );
      }

      Alert.alert('Success', `Action recorded: ${action}`);
    } catch (error) {
      Alert.alert('Failed', error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.card}>
        <Text style={styles.title}>Incident {incident.id}</Text>
        <Text style={styles.meta}>Severity: {String(incident.severity || '').toUpperCase()}</Text>
        <Text style={styles.meta}>Instructions: Follow supervisor directives and update status promptly.</Text>
      </View>

      <MapView
        style={styles.map}
        initialRegion={{
          latitude: Number(incident.lat) || 11.0168,
          longitude: Number(incident.lng) || 76.9558,
          latitudeDelta: 0.02,
          longitudeDelta: 0.02,
        }}
      >
        <Marker
          coordinate={{ latitude: Number(incident.lat) || 11.0168, longitude: Number(incident.lng) || 76.9558 }}
          title={incident.title || 'Incident'}
        />
      </MapView>

      <TouchableOpacity style={styles.navBtn} onPress={() => Linking.openURL(openMapsDeepLink(incident.lat, incident.lng))}>
        <Text style={styles.navText}>Open Google Maps Navigation</Text>
      </TouchableOpacity>

      <View style={styles.grid}>
        {ACTIONS.map((a) => (
          <TouchableOpacity key={a.key} style={styles.actionBtn} onPress={() => act(a.key)} disabled={busy}>
            <Text style={styles.actionText}>{a.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1a26', padding: 12 },
  card: { backgroundColor: '#16283a', borderRadius: 12, padding: 12, marginBottom: 12 },
  title: { color: '#fff', fontSize: 18, fontWeight: '700' },
  meta: { color: '#9ab0c5', marginTop: 5 },
  map: { height: 230, borderRadius: 12, overflow: 'hidden' },
  navBtn: { backgroundColor: '#1f4f75', marginTop: 10, borderRadius: 10, padding: 10, alignItems: 'center' },
  navText: { color: '#fff', fontWeight: '600' },
  grid: { marginTop: 12, gap: 8 },
  actionBtn: { backgroundColor: '#24699e', borderRadius: 10, paddingVertical: 10, paddingHorizontal: 12 },
  actionText: { color: '#fff', fontWeight: '600', textAlign: 'center' },
});
