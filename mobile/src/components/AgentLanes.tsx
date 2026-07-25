import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated, { LinearTransition } from 'react-native-reanimated';

import type { EstadoActor } from '@/state/corrida';
import { ACTORES_VISIBLES, c, carril, nombreActor, r, s } from '@/theme';
import type { Actor } from '@/types';

/** Negociador y Verificador son código puro (dominio/negociador.py,
 *  dominio/verificador.py), no un LLM — no deben leerse "pensando" cuando
 *  se activan, por eso no reciben el glow de fondo que sí tienen los otros
 *  tres actores. */
const DETERMINISTAS: Actor[] = ['negociador', 'verificador'];

/**
 * La tira de agentes. Su trabajo real es hacer visible el turno 2: cuando llega
 * un paso `memoria_hit`, el Cuantificador queda tachado y el juez VE que no se
 * re-cuantificó. Ese salto es la prueba de memoria de la rúbrica.
 */
export function AgentLanes({ actores }: { actores: Record<Actor, EstadoActor> }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={e.tira}
      style={{ flexGrow: 0 }}
    >
      {ACTORES_VISIBLES.map((id) => {
        const a = actores[id];
        const color = carril[id];
        const activo = a.estado === 'activo';
        const omitido = a.estado === 'omitido';
        const determinista = DETERMINISTAS.includes(id);

        return (
          <Animated.View
            key={id}
            layout={LinearTransition.springify()}
            style={[
              e.pastilla,
              activo &&
                (determinista
                  ? { borderColor: color }
                  : { borderColor: color, backgroundColor: color + '1F' }),
              omitido && e.omitido,
            ]}
          >
            <View style={e.filaPastilla}>
              <View
                style={[
                  determinista ? e.puntoCuadrado : e.punto,
                  { backgroundColor: omitido ? c.textoTenue : color },
                  a.estado === 'inactivo' && { opacity: 0.3 },
                ]}
              />
              <Text
                style={[
                  e.nombre,
                  { color: activo ? color : c.textoSuave },
                  omitido && { color: c.textoTenue, textDecorationLine: 'line-through' },
                ]}
              >
                {nombreActor[id]}
              </Text>
            </View>
            {determinista && !omitido && (
              <Text style={e.detTag} numberOfLines={1}>
                código, sin LLM
              </Text>
            )}
            {omitido && (
              <Text style={e.razon} numberOfLines={1}>
                {a.razon ?? 'reusado de memoria'}
              </Text>
            )}
          </Animated.View>
        );
      })}
    </ScrollView>
  );
}

const e = StyleSheet.create({
  tira: { paddingHorizontal: s.md, gap: s.sm, paddingVertical: s.sm },
  pastilla: {
    paddingHorizontal: s.md,
    paddingVertical: s.sm,
    borderRadius: r.sm,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
  },
  omitido: { borderStyle: 'dashed', opacity: 0.85 },
  filaPastilla: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  punto: { width: 7, height: 7, borderRadius: 4 },
  puntoCuadrado: { width: 7, height: 7, borderRadius: 2 },
  nombre: { fontSize: 12, fontWeight: '700' },
  razon: { color: c.alerta, fontSize: 9, marginTop: 2, maxWidth: 160 },
  detTag: { color: c.textoTenue, fontSize: 8, marginTop: 2, letterSpacing: 0.3 },
});
