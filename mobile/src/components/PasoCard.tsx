import { memo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown, LinearTransition } from 'react-native-reanimated';

import { c, carril, nombreActor, r, s } from '@/theme';
import type { PasoTraza } from '@/types';

/** Cada `tipo` que emite el backend, con el peso visual que merece en el pitch.
 *  Sin iconos: el color de carril + el énfasis (borde) ya distinguen el paso,
 *  el texto de la etiqueta no necesita un glifo decorativo al lado. */
const ESTILO: Record<string, { etiqueta: string; enfasis?: 'malo' | 'alerta' | 'bueno' }> = {
  tool_use: { etiqueta: 'herramienta' },
  piensa: { etiqueta: 'razona' },
  llm: { etiqueta: 'consultando al modelo' },
  error_tool: { etiqueta: 'error en herramienta, reintenta', enfasis: 'alerta' },
  limite: { etiqueta: 'límite de iteraciones', enfasis: 'alerta' },
  entrega: { etiqueta: 'entrega', enfasis: 'bueno' },
  armado: { etiqueta: 'arma' },
  memoria_hit: { etiqueta: 'memoria', enfasis: 'bueno' },
  rechazo: { etiqueta: 'rechazo', enfasis: 'malo' },
  aprobacion: { etiqueta: 'aprobado', enfasis: 'bueno' },
  descartado: { etiqueta: 'descarta' },
  divergencia: { etiqueta: 'divergencia', enfasis: 'alerta' },
  sku_inventado: { etiqueta: 'SKU inventado', enfasis: 'malo' },
  espera: { etiqueta: 'espera cuota' },
  fallback: { etiqueta: 'cambia de modelo', enfasis: 'alerta' },
  relleno_deterministico: { etiqueta: 'relleno determinista' },
};

export const PasoCard = memo(function PasoCard({ paso }: { paso: PasoTraza }) {
  const color = carril[paso.actor] ?? c.textoSuave;
  const est = ESTILO[paso.tipo] ?? { etiqueta: paso.tipo };

  const borde =
    est.enfasis === 'malo' ? c.falla : est.enfasis === 'alerta' ? c.alerta : undefined;

  return (
    <Animated.View
      entering={FadeInDown.springify().damping(16).mass(0.5)}
      layout={LinearTransition.springify().damping(18)}
      style={e.fila}
    >
      <View style={e.canal}>
        <View style={[e.punto, { backgroundColor: borde ?? color }]} />
        <View style={[e.linea, { backgroundColor: (borde ?? color) + '33' }]} />
      </View>

      <View
        style={[
          e.tarjeta,
          { borderLeftColor: borde ?? color },
          borde && { borderWidth: 1, borderColor: borde },
        ]}
      >
        <View style={e.cabecera}>
          <Text style={[e.actor, { color: borde ?? color }]}>
            {nombreActor[paso.actor] ?? paso.actor}
          </Text>
          <Text style={e.t}>{paso.t.toFixed(2)}s</Text>
        </View>

        <Text style={[e.tipo, borde ? { color: borde } : undefined]}>{est.etiqueta}</Text>

        {!!paso.detalle && (
          <Text style={e.detalle} numberOfLines={4}>
            {paso.detalle}
          </Text>
        )}

        {!!paso.sku && <Text style={e.sku}>SKU {paso.sku}</Text>}
      </View>
    </Animated.View>
  );
});

const e = StyleSheet.create({
  fila: { flexDirection: 'row', paddingHorizontal: s.md },
  canal: { width: 20, alignItems: 'center' },
  punto: { width: 9, height: 9, borderRadius: 5, marginTop: 16 },
  linea: { width: 2, flex: 1, marginTop: 4, borderRadius: 1 },
  tarjeta: {
    flex: 1,
    marginBottom: s.sm,
    padding: s.md,
    borderRadius: r.md,
    borderLeftWidth: 3,
    backgroundColor: c.surface,
  },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  actor: { fontSize: 10, fontWeight: '800', letterSpacing: 0.9, textTransform: 'uppercase' },
  t: { fontSize: 10, color: c.textoTenue, fontVariant: ['tabular-nums'] },
  tipo: { color: c.texto, fontSize: 14, fontWeight: '700', marginTop: 3 },
  detalle: { color: c.textoSuave, fontSize: 12, marginTop: s.xs, lineHeight: 17 },
  sku: { color: c.textoTenue, fontSize: 11, marginTop: s.xs, fontVariant: ['tabular-nums'] },
});
