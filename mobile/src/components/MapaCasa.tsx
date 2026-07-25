import type { ReactElement } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { c, r, s } from '@/theme';
import { AMBIENTES, type TipoAmbiente } from '@/types';

/**
 * Selector de ambiente como plano de casa: 4 regiones reales (Pressable, no
 * zonas clicables dentro de un solo SVG) dispuestas en 2×2 dentro de un marco
 * de casa decorativo. Sigue cotizando UN ambiente por corrida — esto es solo
 * el picker, no compone varios Espacio en una obra.
 */
const ICONOS: Record<TipoAmbiente, (activo: boolean) => ReactElement> = {
  bano: (activo) => (
    <Svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 10h14M6 10v7a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-7"
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <Path
        d="M8 10V6a2 2 0 0 1 3.2-1.6"
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <Circle cx={16} cy={5} r={1.2} fill={activo ? c.seleccion : c.textoSuave} />
    </Svg>
  ),
  cocina: (activo) => (
    <Svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <Rect
        x={4}
        y={5}
        width={16}
        height={14}
        rx={1.5}
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
      />
      <Circle cx={8.5} cy={9.5} r={1.4} stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.4} />
      <Circle cx={15.5} cy={9.5} r={1.4} stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.4} />
      <Line x1={6} y1={15} x2={18} y2={15} stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.4} />
    </Svg>
  ),
  habitacion: (activo) => (
    <Svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 18v-6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6"
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <Path d="M4 14h16" stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.6} />
      <Path d="M4 18v2M20 18v2" stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.6} strokeLinecap="round" />
    </Svg>
  ),
  sala: (activo) => (
    <Svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 12v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <Path
        d="M4 12a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2"
        stroke={activo ? c.seleccion : c.textoSuave}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      <Path d="M6 18v1.5M18 18v1.5" stroke={activo ? c.seleccion : c.textoSuave} strokeWidth={1.6} strokeLinecap="round" />
    </Svg>
  ),
};

export function MapaCasa({
  seleccion,
  onSeleccionar,
}: {
  seleccion: TipoAmbiente;
  onSeleccionar: (t: TipoAmbiente) => void;
}) {
  return (
    <View style={e.marco} accessibilityRole="radiogroup" accessibilityLabel="Ambiente a remodelar">
      {/* Techo decorativo de la casa: solo estética, no es un objetivo táctil. */}
      <Svg
        width="100%"
        height={26}
        viewBox="0 0 200 26"
        style={{ position: 'absolute', top: 0, left: 0, right: 0 }}
        pointerEvents="none"
      >
        <Path d="M6 26 L100 4 L194 26" stroke={c.borde} strokeWidth={2} fill="none" strokeLinecap="round" />
      </Svg>

      <View style={e.techoEspaciador} />

      <View style={e.grid}>
        {AMBIENTES.map((a) => {
          const activo = seleccion === a.id;
          return (
            <Pressable
              key={a.id}
              onPress={() => onSeleccionar(a.id)}
              accessibilityRole="radio"
              accessibilityLabel={a.nombre}
              accessibilityState={{ selected: activo }}
              hitSlop={4}
              style={[e.cuarto, activo && e.cuartoOn]}
            >
              {ICONOS[a.id](activo)}
              <Text style={[e.nombre, activo && { color: c.seleccion }]}>{a.nombre}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const e = StyleSheet.create({
  marco: {
    borderWidth: 1,
    borderColor: c.borde,
    borderRadius: r.lg,
    backgroundColor: c.surfaceAlto,
    overflow: 'hidden',
  },
  techoEspaciador: { height: 26 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: s.sm,
    gap: s.sm,
  },
  cuarto: {
    flexBasis: '47%',
    flexGrow: 1,
    minHeight: 76,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: s.sm,
    borderRadius: r.md,
    borderWidth: 1,
    borderColor: 'transparent',
    backgroundColor: c.surface,
  },
  cuartoOn: { borderColor: c.seleccion, backgroundColor: 'rgba(59,130,246,0.12)' },
  nombre: { color: c.textoSuave, fontSize: 12, fontWeight: '700' },
});
