import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';

import { c, pesos, r, s } from '@/theme';

/**
 * El momento de negociación hecho físico: la barra se pasa del tope en rojo y,
 * a medida que el Negociador recorta, se retrae con resorte hasta ponerse verde.
 * El jurado ve el ahorro, no lo lee.
 */
export function BudgetBar({ total, tope }: { total: number; tope: number }) {
  const p = useSharedValue(0);

  useEffect(() => {
    if (!tope) return;
    p.value = withSpring(total / tope, { damping: 15, stiffness: 90 });
  }, [total, tope, p]);

  const excede = tope > 0 && total > tope;

  const barra = useAnimatedStyle(() => ({
    width: `${Math.min(p.value, 1) * 100}%`,
    backgroundColor: interpolateColor(
      Math.min(p.value, 1.0001),
      [0, 0.9, 1.0001],
      [c.ok, c.alerta, c.falla],
    ),
  }));

  // Lo que se sale del tope se pinta encima, no se recorta: el exceso tiene que verse.
  const desborde = useAnimatedStyle(() => ({
    width: `${Math.min(Math.max(p.value - 1, 0), 0.6) * 100}%`,
    opacity: p.value > 1 ? 1 : 0,
  }));

  return (
    <View style={e.caja}>
      <View style={e.cabecera}>
        <Text style={e.etiqueta}>PRESUPUESTO</Text>
        <Text style={[e.total, { color: excede ? c.falla : c.ok }]}>
          {pesos(total)} <Text style={e.tope}>/ {pesos(tope)}</Text>
        </Text>
      </View>

      <View style={e.riel}>
        <Animated.View style={[e.relleno, barra]} />
        <Animated.View style={[e.desborde, desborde]} />
        <View style={e.marcaTope} />
      </View>

      {excede && (
        <Text style={e.aviso}>Excede por {pesos(total - tope)} — negociando recortes</Text>
      )}
      {!excede && tope > 0 && total > 0 && (
        <Text style={[e.aviso, { color: c.ok }]}>
          Holgura de {pesos(tope - total)} ({100 - Math.round((total / tope) * 100)} %)
        </Text>
      )}
    </View>
  );
}

const e = StyleSheet.create({
  caja: {
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
  },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  etiqueta: { color: c.textoTenue, fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  total: { fontSize: 16, fontWeight: '800', fontVariant: ['tabular-nums'] },
  tope: { color: c.textoTenue, fontSize: 12, fontWeight: '600' },
  riel: {
    height: 10,
    borderRadius: 5,
    backgroundColor: c.surfaceAlto,
    marginTop: s.sm,
    overflow: 'hidden',
    flexDirection: 'row',
  },
  relleno: { height: '100%', borderRadius: 5 },
  desborde: { height: '100%', backgroundColor: c.falla, opacity: 0.55 },
  marcaTope: { position: 'absolute', right: 0, width: 2, height: '100%', backgroundColor: c.texto },
  aviso: { marginTop: s.sm, color: c.falla, fontSize: 11, fontWeight: '700' },
});
