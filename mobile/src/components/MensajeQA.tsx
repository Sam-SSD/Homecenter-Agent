import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { c, r, s } from '@/theme';
import type { MensajeQA as TMensajeQA } from '@/state/qa';

export function MensajeQA({ mensaje }: { mensaje: TMensajeQA }) {
  const esUsuario = mensaje.rol === 'usuario';

  return (
    <Animated.View
      entering={FadeInDown.springify().damping(16)}
      style={[e.fila, esUsuario && e.filaUsuario]}
    >
      <View style={[e.burbuja, esUsuario ? e.burbujaUsuario : e.burbujaAgente]}>
        <Text style={[e.texto, esUsuario && { color: '#100804' }]}>{mensaje.texto}</Text>
      </View>
      {!esUsuario && !!mensaje.herramientas?.length && (
        <Text style={e.herramientas}>Herramientas: {mensaje.herramientas.join(', ')}</Text>
      )}
    </Animated.View>
  );
}

const e = StyleSheet.create({
  fila: { marginBottom: s.md, alignItems: 'flex-start' },
  filaUsuario: { alignItems: 'flex-end' },
  burbuja: { maxWidth: '82%', padding: s.md, borderRadius: r.lg },
  burbujaAgente: {
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
    borderTopLeftRadius: 4,
  },
  burbujaUsuario: { backgroundColor: c.acento, borderTopRightRadius: 4 },
  texto: { color: c.texto, fontSize: 14, lineHeight: 20 },
  herramientas: { color: c.textoTenue, fontSize: 10, marginTop: 4, fontStyle: 'italic' },
});
