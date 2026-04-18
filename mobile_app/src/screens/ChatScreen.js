import React, { useEffect, useMemo, useState } from 'react';
import { SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { getWsUrls } from '../api/client';

export default function ChatScreen({ route, authContext }) {
  const { incidentId } = route.params;
  const wsUrl = useMemo(() => getWsUrls(incidentId).chatWs, [incidentId]);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === 'receive_message') {
          setMessages((prev) => [...prev, payload.data]);
        }
      } catch {
        setMessages((prev) => [...prev, { sender: 'system', text: event.data }]);
      }
    };
    setSocket(ws);
    return () => ws.close();
  }, [wsUrl]);

  const send = () => {
    if (!socket || !text.trim()) return;
    socket.send(
      JSON.stringify({
        event: 'send_message',
        incident_id: incidentId,
        sender: authContext.session.officer.name,
        text: text.trim(),
      })
    );
    setText('');
  };

  return (
    <SafeAreaView style={styles.root}>
      <Text style={styles.title}>Incident Chat: {incidentId}</Text>
      <View style={styles.stream}>
        {messages.map((msg, idx) => (
          <Text key={`${idx}-${msg.text || ''}`} style={styles.msg}>
            {msg.sender || 'unknown'}: {msg.text || ''}
          </Text>
        ))}
      </View>
      <View style={styles.composer}>
        <TextInput style={styles.input} value={text} onChangeText={setText} placeholder="Type message" placeholderTextColor="#8aa3bb" />
        <TouchableOpacity style={styles.send} onPress={send}><Text style={styles.sendText}>Send</Text></TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1a26', padding: 12 },
  title: { color: '#fff', fontWeight: '700', fontSize: 18, marginBottom: 10 },
  stream: { flex: 1, backgroundColor: '#16283a', borderRadius: 12, padding: 10 },
  msg: { color: '#d7e8f8', marginBottom: 6 },
  composer: { flexDirection: 'row', marginTop: 10, gap: 8 },
  input: { flex: 1, backgroundColor: '#1b3550', color: '#fff', borderRadius: 10, paddingHorizontal: 12 },
  send: { backgroundColor: '#1988d7', paddingHorizontal: 14, justifyContent: 'center', borderRadius: 10 },
  sendText: { color: '#fff', fontWeight: '700' },
});
