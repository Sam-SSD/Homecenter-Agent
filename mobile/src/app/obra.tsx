import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useEffect, useRef } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated, {
  FadeIn,
  FadeInDown,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { AgentLanes } from '@/components/AgentLanes';
import { BadgeDemo } from '@/components/BadgeDemo';
import { BudgetBar } from '@/components/BudgetBar';
import { PasoCard } from '@/components/PasoCard';
import { useEsEscritorio } from '@/lib/responsive';
import { useCorridaCtx } from '@/state/CorridaProvider';
import { c, r, s } from '@/theme';

/** Dos hápticos seguidos a 90 ms se sienten como un zumbido, no como un latido. */
const MS_ENTRE_HAPTICOS = 220;

export default function Obra() {
  const { estado, señales } = useCorridaCtx();
  const escritorio = useEsEscritorio();
  const scroll = useRef<ScrollView>(null);
  const cercaDelFondo = useRef(true);
  const ultimoHaptico = useRef(0);
  const vistos = useRef(0);

  useEffect(() => {
    if (estado.pasos.length <= vistos.current) return;
    vistos.current = estado.pasos.length;

    const ahora = Date.now();
    if (ahora - ultimoHaptico.current > MS_ENTRE_HAPTICOS) {
      ultimoHaptico.current = ahora;
      Haptics.selectionAsync();
    }

    // Solo seguimos al fondo si el juez no se fue a leer hacia arriba.
    if (cercaDelFondo.current) scroll.current?.scrollToEnd({ animated: true });
  }, [estado.pasos.length]);

  const cot = estado.cotizacion;
  const terminada = !estado.corriendo && estado.pasos.length > 0;

  const traza = (
    <>
      <AgentLanes actores={estado.actores} />
      <ScrollView
        ref={scroll}
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingTop: s.sm, paddingBottom: s.xxl }}
        scrollEventThrottle={120}
        onScroll={(ev) => {
          const { layoutMeasurement, contentOffset, contentSize } = ev.nativeEvent;
          cercaDelFondo.current =
            layoutMeasurement.height + contentOffset.y >= contentSize.height - 90;
        }}
      >
        {estado.pasos.map((p) => (
          <PasoCard key={p.i} paso={p} />
        ))}

        {estado.pasos.length === 0 && (
          <Animated.Text entering={FadeIn.delay(300)} style={e.vacio}>
            Esperando al Supervisor…
          </Animated.Text>
        )}

        {estado.error && <Text style={e.error}>{estado.error}</Text>}

        {señales.skusInventados > 0 && (
          <Text style={e.nota}>
            {señales.skusInventados} SKU inventado por el LLM fue atrapado y descartado.
          </Text>
        )}
      </ScrollView>
    </>
  );

  const resumenYAcciones = (
    <>
      <View style={e.barra}>
        <BudgetBar total={cot?.total_cop ?? 0} tope={estado.espacio?.presupuesto_cop ?? 0} />
      </View>

      {señales.huboAutocorreccion && <TarjetaRechazo detalle={señales.rechazos[0].detalle} />}

      {terminada && <ResumenCorrida pasos={estado.pasos.length} señales={señales} />}

      {cot && (
        <Animated.View entering={FadeInDown.springify()} style={e.pieCta}>
          <Pressable style={e.cta} onPress={() => router.push('/cotizacion')}>
            <Text style={e.ctaTexto}>Ver los {cot.items.length} productos de la cotización →</Text>
          </Pressable>
          <Text style={e.pieNota}>
            Todavía puedes revisar cada producto antes de decidir sobre los recortes.
          </Text>
        </Animated.View>
      )}
    </>
  );

  return (
    <View style={{ flex: 1 }}>
      <View style={e.encabezado}>
        <BadgeDemo visible={estado.fuente === 'cache'} />
      </View>

      {escritorio ? (
        <View style={e.filaEscritorio}>
          <View style={e.colIzquierda}>{resumenYAcciones}</View>
          <View style={e.colDerecha}>{traza}</View>
        </View>
      ) : (
        <View style={{ flex: 1 }}>
          {traza}
          {resumenYAcciones}
        </View>
      )}
    </View>
  );
}

/** Comportamiento esperado por la skill agent-trace-ui: al terminar, un
 *  resumen de pasos/segundos/autocorrección, no solo la traza cruda. */
function ResumenCorrida({
  pasos,
  señales,
}: {
  pasos: number;
  señales: { segundos: number; huboAutocorreccion: boolean; skusInventados: number };
}) {
  const partes = [`${pasos} pasos`, `${señales.segundos.toFixed(2)}s`];
  if (señales.huboAutocorreccion) partes.push('hubo auto-corrección');
  if (señales.skusInventados > 0) partes.push(`${señales.skusInventados} SKU inventado`);

  return (
    <Animated.View entering={FadeIn} style={e.resumen}>
      <Text style={e.resumenTexto}>{partes.join(' · ')}</Text>
    </Animated.View>
  );
}

/** El rechazo del Verificador entra como observación, no como excepción. Se ve. */
function TarjetaRechazo({ detalle }: { detalle: string }) {
  const sacudir = useSharedValue(0);

  useEffect(() => {
    sacudir.value = withSequence(
      withTiming(-6, { duration: 55 }),
      withTiming(6, { duration: 55 }),
      withTiming(-4, { duration: 55 }),
      withTiming(0, { duration: 55 }),
    );
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  }, [detalle, sacudir]);

  const est = useAnimatedStyle(() => ({ transform: [{ translateX: sacudir.value }] }));

  return (
    <Animated.View style={[e.rechazo, est]}>
      <Text style={e.rechazoTitulo}>✕ El Verificador rechazó</Text>
      <Text style={e.falla}>{detalle}</Text>
      <Text style={e.recompone}>El Supervisor recompone…</Text>
    </Animated.View>
  );
}

const e = StyleSheet.create({
  encabezado: { paddingHorizontal: s.md, paddingTop: s.sm },
  barra: { paddingHorizontal: s.md, paddingBottom: s.sm },

  // Escritorio: columna izquierda (estado/decisión) + columna derecha fija
  // para la traza (referencia: panel de ~420px de la demo Streamlit).
  filaEscritorio: { flex: 1, flexDirection: 'row', maxWidth: 1100, alignSelf: 'center', width: '100%' },
  colIzquierda: { flex: 1, paddingHorizontal: s.md },
  colDerecha: { width: 400, borderLeftWidth: 1, borderColor: c.borde },

  resumen: {
    marginHorizontal: s.md,
    marginTop: s.sm,
    paddingVertical: s.sm,
    paddingHorizontal: s.md,
    borderRadius: r.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
  },
  resumenTexto: { color: c.textoSuave, fontSize: 12, fontWeight: '600', textAlign: 'center' },

  vacio: { color: c.textoTenue, textAlign: 'center', marginTop: s.xxl, fontSize: 13 },
  error: { color: c.falla, textAlign: 'center', margin: s.lg, fontSize: 13 },
  nota: {
    color: c.alerta,
    fontSize: 12,
    textAlign: 'center',
    marginHorizontal: s.lg,
    marginTop: s.md,
    lineHeight: 17,
  },

  rechazo: {
    marginHorizontal: s.md,
    marginBottom: s.sm,
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: 'rgba(244,63,94,0.12)',
    borderWidth: 1,
    borderColor: c.falla,
  },
  rechazoTitulo: { color: c.falla, fontWeight: '800', fontSize: 13 },
  falla: { color: c.textoSuave, fontSize: 11, marginTop: 3 },
  recompone: { color: c.alerta, fontSize: 11, marginTop: s.sm, fontStyle: 'italic' },

  pieCta: { padding: s.md, borderTopWidth: 1, borderColor: c.borde, backgroundColor: c.bg },
  cta: { paddingVertical: 16, borderRadius: r.lg, backgroundColor: c.acento, alignItems: 'center' },
  ctaTexto: { color: '#100804', fontSize: 15, fontWeight: '900' },
  pieNota: { color: c.textoTenue, fontSize: 11, textAlign: 'center', marginTop: s.sm },
});
