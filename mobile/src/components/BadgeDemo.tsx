import { StyleSheet, Text, View } from 'react-native';

import { c, r, s } from '@/theme';

/**
 * Badge de MODO DEMO. Visible por defecto (p.ej. en /catalogo, que siempre lee
 * el JSON bundleado sin backend). En las pantallas de corrida (index/obra/
 * cotizacion/qa) se pasa `visible={estado.fuente === 'cache'}`: con backend
 * real conectado y fuente 'vivo', mostrar este badge sería mentir sobre datos
 * que sí vienen del agente.
 */
export function BadgeDemo({ visible = true }: { visible?: boolean }) {
  if (!visible) return null;
  return (
    <View style={e.caja}>
      <Text style={e.punto}>●</Text>
      <Text style={e.texto}>
        <Text style={e.fuerte}>MODO DEMO</Text> · traza reproducida, sin agente en vivo
      </Text>
    </View>
  );
}

const e = StyleSheet.create({
  caja: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    paddingHorizontal: s.sm,
    paddingVertical: 5,
    borderRadius: r.sm,
    backgroundColor: 'rgba(251,191,36,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.4)',
  },
  punto: { color: c.alerta, fontSize: 8 },
  texto: { color: c.alerta, fontSize: 10, fontWeight: '600' },
  fuerte: { fontWeight: '900' },
});
