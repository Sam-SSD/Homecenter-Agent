import * as Haptics from 'expo-haptics';
import { StyleSheet, Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  FadeInDown,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';
import { runOnJS } from 'react-native-worklets';

import { c, pesos, r, s } from '@/theme';

const UMBRAL = 84;

/**
 * Human-in-the-loop.
 *
 * El backend modela `recortes` como `list[str]` y la aprobación como un solo
 * `aprobada_por_humano: bool` sobre toda la cotización. Así que la compuerta es
 * una, no una por recorte: se listan los recortes tal como llegan y se aprueba
 * o rechaza el conjunto. El gesto se mantiene porque nadie aprueba recortes de
 * verdad sin sentirlo — el háptico dispara al cruzar el umbral, no al soltar.
 */
export function AprobacionHumana({
  recortes,
  alternativas,
  holgura,
  onDecidir,
}: {
  recortes: string[];
  alternativas: string[];
  holgura: number;
  onDecidir: (aprobada: boolean) => void;
}) {
  const x = useSharedValue(0);
  const armado = useSharedValue(false);

  const vibrar = () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  const confirmar = (ok: boolean) => {
    Haptics.notificationAsync(
      ok ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Warning,
    );
    onDecidir(ok);
  };

  const pan = Gesture.Pan()
    .activeOffsetX([-12, 12])
    .onUpdate((ev) => {
      x.value = ev.translationX;
      const pasa = Math.abs(ev.translationX) > UMBRAL;
      if (pasa !== armado.value) {
        armado.value = pasa;
        if (pasa) runOnJS(vibrar)();
      }
    })
    .onEnd((ev) => {
      if (Math.abs(ev.translationX) > UMBRAL) {
        runOnJS(confirmar)(ev.translationX > 0);
      }
      x.value = withSpring(0, { damping: 20 });
      armado.value = false;
    });

  const tarjeta = useAnimatedStyle(() => ({
    transform: [
      { translateX: x.value },
      { rotateZ: `${interpolate(x.value, [-200, 0, 200], [-3, 0, 3])}deg` },
    ],
  }));

  const fondo = useAnimatedStyle(() => ({
    backgroundColor: x.value > 0 ? c.ok : c.falla,
    opacity: interpolate(Math.abs(x.value), [0, UMBRAL], [0, 0.3], 'clamp'),
  }));

  return (
    <Animated.View entering={FadeInDown.springify().damping(18)} style={e.envoltura}>
      <Animated.View style={[StyleSheet.absoluteFill, e.fondo, fondo]} />

      <GestureDetector gesture={pan}>
        <Animated.View style={[e.tarjeta, tarjeta]}>
          <Text style={e.titulo}>Aprobación humana</Text>

          {recortes.length > 0 ? (
            <>
              <Text style={e.subtitulo}>
                El Negociador recortó {recortes.length}{' '}
                {recortes.length === 1 ? 'cosa' : 'cosas'} para entrar bajo el tope:
              </Text>
              {recortes.map((rec, i) => (
                <View key={i} style={e.item}>
                  <Text style={e.bala}>−</Text>
                  <Text style={e.recorte}>{rec}</Text>
                </View>
              ))}
            </>
          ) : (
            <Text style={e.subtitulo}>No hizo falta recortar nada.</Text>
          )}

          {alternativas.length > 0 && (
            <>
              <Text style={e.seccion}>Con la holgura de {pesos(holgura)} propone:</Text>
              {alternativas.map((alt, i) => (
                <View key={i} style={e.item}>
                  <Text style={[e.bala, { color: c.ok }]}>+</Text>
                  <Text style={e.recorte}>{alt}</Text>
                </View>
              ))}
            </>
          )}

          <Text style={e.pista}>← rechazar · deslizar · aprobar →</Text>
        </Animated.View>
      </GestureDetector>
    </Animated.View>
  );
}

const e = StyleSheet.create({
  envoltura: { borderRadius: r.md, overflow: 'hidden' },
  fondo: { borderRadius: r.md },
  tarjeta: {
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.acento,
  },
  titulo: { color: c.texto, fontSize: 16, fontWeight: '800' },
  subtitulo: { color: c.textoSuave, fontSize: 12, marginTop: 4, lineHeight: 17 },
  seccion: { color: c.textoTenue, fontSize: 10, fontWeight: '800', letterSpacing: 1, marginTop: s.md },
  item: { flexDirection: 'row', gap: s.sm, marginTop: s.sm },
  bala: { color: c.falla, fontSize: 13, fontWeight: '900', width: 10 },
  recorte: { color: c.texto, fontSize: 13, flex: 1, lineHeight: 18 },
  pista: { color: c.textoTenue, fontSize: 10, marginTop: s.md, textAlign: 'center' },
});
