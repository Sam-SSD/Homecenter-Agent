import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CorridaProvider } from '@/state/CorridaProvider';
import { c } from '@/theme';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: c.bg }}>
      <SafeAreaProvider>
        <CorridaProvider>
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: c.bg },
              headerTintColor: c.texto,
              headerTitleStyle: { fontWeight: '800' },
              headerTitleAlign: 'center',
              contentStyle: { backgroundColor: c.bg },
              headerShadowVisible: false,
            }}
          >
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="obra" options={{ title: 'Traza en vivo' }} />
            <Stack.Screen name="cotizacion" options={{ title: 'Cotización' }} />
            <Stack.Screen name="qa" options={{ title: 'Preguntas' }} />
            <Stack.Screen name="catalogo" options={{ title: 'Catálogo real' }} />
          </Stack>
        </CorridaProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
