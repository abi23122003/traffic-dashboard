import React, { useState } from 'react';
import { Alert, SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import * as Notifications from 'expo-notifications';
import { loginOfficer, registerDeviceToken } from '../api/client';
import { saveSession } from '../storage/auth';

export default function LoginScreen({ authContext }) {
  const [officerId, setOfficerId] = useState('1');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    try {
      setLoading(true);
      const response = await loginOfficer(officerId);
      const session = {
        token: response.access_token,
        officer: response.officer,
      };

      try {
        const perm = await Notifications.requestPermissionsAsync();
        if (perm.status === 'granted') {
          let tokenValue = null;
          try {
            const deviceToken = await Notifications.getDevicePushTokenAsync();
            tokenValue = deviceToken?.data || null;
          } catch (_) {
            // Fallback to Expo token when native device token is unavailable.
          }

          if (!tokenValue) {
            const expoToken = await Notifications.getExpoPushTokenAsync();
            tokenValue = expoToken?.data || null;
          }

          if (tokenValue) {
            await registerDeviceToken(response.officer.id, tokenValue, response.access_token);
          }
        }
      } catch (err) {
        console.log('Push token registration skipped:', err?.message || err);
      }

      await saveSession(session);
      authContext.setSession(session);
    } catch (error) {
      Alert.alert('Login failed', error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.card}>
        <Text style={styles.title}>Officer Login</Text>
        <Text style={styles.subtitle}>Sign in with your officer ID</Text>

        <TextInput
          value={officerId}
          onChangeText={setOfficerId}
          placeholder="Officer ID"
          keyboardType="numeric"
          style={styles.input}
          placeholderTextColor="#9aaec2"
        />

        <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? 'Signing in...' : 'Login'}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#0e1a26',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: '#16283a',
    borderRadius: 14,
    padding: 18,
  },
  title: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  subtitle: {
    color: '#9aaec2',
    marginTop: 6,
    marginBottom: 14,
  },
  input: {
    backgroundColor: '#21384f',
    color: '#fff',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
  },
  button: {
    backgroundColor: '#1988d7',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600',
  },
});
