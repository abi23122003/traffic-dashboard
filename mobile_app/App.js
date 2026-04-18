import React, { useEffect, useMemo, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import LoginScreen from './src/screens/LoginScreen';
import IncidentListScreen from './src/screens/IncidentListScreen';
import IncidentDetailScreen from './src/screens/IncidentDetailScreen';
import ChatScreen from './src/screens/ChatScreen';
import { getStoredSession } from './src/storage/auth';

const Stack = createNativeStackNavigator();

export default function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    (async () => {
      const saved = await getStoredSession();
      setSession(saved);
    })();
  }, []);

  const authContext = useMemo(
    () => ({ session, setSession }),
    [session]
  );

  return (
    <NavigationContainer>
      <Stack.Navigator>
        {!session ? (
          <Stack.Screen name="Login" options={{ headerShown: false }}>
            {(props) => <LoginScreen {...props} authContext={authContext} />}
          </Stack.Screen>
        ) : (
          <>
            <Stack.Screen name="Incidents" options={{ title: 'Live Dispatch' }}>
              {(props) => <IncidentListScreen {...props} authContext={authContext} />}
            </Stack.Screen>
            <Stack.Screen name="IncidentDetail" options={{ title: 'Incident Detail' }}>
              {(props) => <IncidentDetailScreen {...props} authContext={authContext} />}
            </Stack.Screen>
            <Stack.Screen name="Chat" options={{ title: 'Supervisor Chat' }}>
              {(props) => <ChatScreen {...props} authContext={authContext} />}
            </Stack.Screen>
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
