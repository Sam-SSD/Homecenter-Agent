import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { AprobacionHumana } from '@/components/AprobacionHumana';
import { BadgeDemo } from '@/components/BadgeDemo';
import { MiniaturaProducto } from '@/components/ProductoPreview';
import { SourceChip } from '@/components/SourceChip';
import { productosDeCategoria } from '@/data/catalogo';
import { useEsEscritorio } from '@/lib/responsive';
import { generarCorrida } from '@/mock/demo';
import { useCorridaCtx } from '@/state/CorridaProvider';
import { c, pesos, r, s } from '@/theme';
import type { ItemCotizado, Producto } from '@/types';

/**
 * Orden intencional: primero los productos reales (para que el usuario vea
 * QUÉ está comprando), después la negociación que pide su aprobación. Antes
 * la aprobación vivía como compuerta en /obra, bloqueando la vista de
 * productos — eso se movió acá para que "ver antes de aprobar" sea literal.
 */
export default function CotizacionPantalla() {
  const { estado, correr, correrVivo, aprobar } = useCorridaCtx();
  const escritorio = useEsEscritorio();
  const cot = estado.cotizacion;
  const [subiendo, setSubiendo] = useState(false);

  if (!cot) return <Text style={e.vacio}>Todavía no hay cotización.</Text>;

  /**
   * El turno 2 del pitch. Reusa el mismo espacio con un tope mayor. En modo
   * Demo, la traza arranca con `memoria_hit` porque el guion la trae armada;
   * en modo Vivo, es el backend real el que lee `datos/memoria.db` y por eso
   * el Cuantificador sale tachado: el jurado VE que no se re-cuantificó.
   */
  const subirTope = async () => {
    if (!estado.espacio) return;
    setSubiendo(true);
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);

    const espacio = {
      ...estado.espacio,
      presupuesto_cop: Math.round(estado.espacio.presupuesto_cop * 1.25),
    };
    router.push('/obra');
    if (estado.fuente === 'cache') {
      await correr(espacio, generarCorrida(espacio, 2), { conservarTurno: true });
    } else {
      await correrVivo(espacio, true, { conservarTurno: true });
    }
    setSubiendo(false);
  };

  const nuevoTope = Math.round(cot.espacio.presupuesto_cop * 1.25);
  const necesitaDecision = cot.recortes.length > 0 || cot.alternativas.length > 0;

  const hero = (
    <Animated.View entering={FadeInDown.springify()} style={e.hero}>
      <Text style={e.etiqueta}>TOTAL</Text>
      <Text style={e.total}>{pesos(cot.total_cop)}</Text>
      <Text style={e.bajoTope}>
        bajo un tope de {pesos(cot.espacio.presupuesto_cop)} · holgura {pesos(cot.holgura_cop)}
      </Text>
      {estado.aprobada !== null ? (
        <View style={[e.sello, estado.aprobada ? e.selloOk : e.selloNo]}>
          <Text style={[e.selloTexto, { color: estado.aprobada ? c.ok : c.falla }]}>
            {estado.aprobada ? '✓ Aprobada por humano' : '✕ Recortes rechazados'}
          </Text>
        </View>
      ) : necesitaDecision ? (
        <View style={e.selloPendiente}>
          <Text style={e.selloPendienteTexto}>Revisa los productos y decide abajo</Text>
        </View>
      ) : null}
    </Animated.View>
  );

  const items = (
    <Seccion titulo={`PRODUCTOS (${cot.items.length})`}>
      {cot.items.map((it, i) => (
        <Item key={`${it.concepto}-${i}`} item={it} idx={i} />
      ))}
      {cot.faltantes.length > 0 && (
        <View style={e.faltantesBox}>
          <Text style={e.faltantesTitulo}>Sin candidatos en el catálogo</Text>
          {cot.faltantes.map((f) => (
            <Text key={f} style={e.faltante}>
              · {f}
            </Text>
          ))}
        </View>
      )}
    </Seccion>
  );

  const negociacion = necesitaDecision && (
    <Seccion titulo="NEGOCIACIÓN">
      {estado.aprobada === null ? (
        <AprobacionHumana
          recortes={cot.recortes}
          alternativas={cot.alternativas}
          holgura={cot.holgura_cop}
          onDecidir={aprobar}
        />
      ) : (
        <View style={e.negociacionDecidida}>
          {cot.recortes.map((rec, i) => (
            <View key={i} style={e.recorte}>
              <Text style={e.recorteTexto}>− {rec}</Text>
            </View>
          ))}
          {cot.alternativas.map((alt, i) => (
            <View key={i} style={e.alternativa}>
              <Text style={e.alternativaTexto}>+ {alt}</Text>
            </View>
          ))}
        </View>
      )}
    </Seccion>
  );

  const fases = Object.keys(cot.fases).length > 0 && (
    <Seccion titulo="PLAN POR FASES">
      {Object.entries(cot.fases).map(([nombre, conceptos], i) => (
        <View key={nombre} style={e.fase}>
          <View style={e.faseNum}>
            <Text style={e.faseNumTexto}>{i + 1}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={e.faseNombre}>{nombre}</Text>
            <Text style={e.faseConceptos}>{conceptos.length ? conceptos.join(' · ') : '—'}</Text>
          </View>
        </View>
      ))}
    </Seccion>
  );

  const acciones = (
    <>
      <Pressable onPress={subirTope} disabled={subiendo} style={e.cta}>
        <Text style={e.ctaTexto}>
          {subiendo ? 'Recordando…' : `¿Y si le subo a ${pesos(nuevoTope)}?`}
        </Text>
      </Pressable>
      <Text style={e.notaMemoria}>
        No vuelve a cuantificar: lee memoria de sesión y solo re-corre Negociador y Verificador.
      </Text>

      <Pressable onPress={() => router.push('/qa')} style={e.ctaQA}>
        <Text style={e.ctaQATexto}>Preguntarle al agente sobre esta cotización</Text>
      </Pressable>

      <Text style={e.limites}>
        Límites conocidos: los precios son un snapshot, no hay stock por bodega, y la merma no está
        verificada contra guía oficial.
        {estado.fuente === 'cache' &&
          ' Además, esta corrida es una traza reproducida — el agente real vive en el repo del equipo y corre sobre Streamlit.'}
      </Text>
    </>
  );

  return (
    <ScrollView contentContainerStyle={[e.cuerpo, escritorio && e.cuerpoEscritorio]}>
      <BadgeDemo visible={estado.fuente === 'cache'} />

      {escritorio ? (
        <View style={e.filaEscritorio}>
          <View style={e.colPrincipal}>
            {hero}
            {items}
          </View>
          <View style={e.colLateral}>
            {negociacion}
            {fases}
            {acciones}
          </View>
        </View>
      ) : (
        <>
          {hero}
          {items}
          {negociacion}
          {fases}
          {acciones}
        </>
      )}
    </ScrollView>
  );
}

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <View style={{ marginTop: s.lg }}>
      <Text style={e.tituloSeccion}>{titulo}</Text>
      {children}
    </View>
  );
}

/**
 * Aprobar/cambiar es una decisión de exploración por producto: "cambiar"
 * trae otra opción REAL de la misma categoría del catálogo (nunca inventa un
 * SKU). El subtotal mostrado se recalcula con el precio del reemplazo, pero
 * no se propaga a `cot.total_cop` (ese lo calcula el Negociador) — por eso
 * queda marcado explícitamente como "cambio local, no en el total".
 */
function Item({ item, idx }: { item: ItemCotizado; idx: number }) {
  const req = item.requerimiento;
  const [actual, setActual] = useState<Producto>(item.producto);
  const [decision, setDecision] = useState<'pendiente' | 'aprobado'>('pendiente');
  const [vistos, setVistos] = useState<string[]>([item.producto.sku]);
  const cambiado = actual.sku !== item.producto.sku;
  const subtotalActual = item.unidades_a_comprar * actual.precio;

  const cambiarOpcion = () => {
    const opciones = productosDeCategoria(item.producto.categoria).filter(
      (op) => !vistos.includes(op.sku),
    );
    if (opciones.length === 0) return;
    const siguiente = opciones[0];
    setActual(siguiente);
    setVistos((v) => [...v, siguiente.sku]);
    setDecision('pendiente');
  };

  return (
    <Animated.View entering={FadeInDown.delay(idx * 45).springify()} style={e.item}>
      <View style={e.itemCabecera}>
        <MiniaturaProducto producto={actual} />
        <View style={{ flex: 1 }}>
          <View style={e.itemTitulo}>
            <Text style={e.concepto}>{item.concepto}</Text>
            <Text style={e.subtotal}>{pesos(subtotalActual)}</Text>
          </View>
          <Text style={e.producto} numberOfLines={2}>
            {actual.nombre}
          </Text>
        </View>
      </View>

      <Text style={e.detalle}>
        {item.unidades_a_comprar} {actual.unidad} × {pesos(actual.precio)} · SKU {actual.sku} · gama{' '}
        {item.gama}
      </Text>

      <Text style={e.formula}>
        {req.cantidad} {req.unidad} ← {req.formula}
      </Text>
      <Text style={e.justificacion}>{item.justificacion}</Text>

      {cambiado && (
        <Text style={e.aviso}>
          Cambiaste esta opción — cambio local, no se recalculó el total de la cotización.
        </Text>
      )}
      {item.estado_precio === 'cambio' && (
        <Text style={e.aviso}>
          El precio en vivo cambió a {pesos(item.precio_confirmado ?? actual.precio)}
        </Text>
      )}
      {item.estado_precio === 'snapshot' && (
        <Text style={e.snapshot}>Precio de snapshot, sin confirmar en vivo</Text>
      )}

      <View style={e.chips}>
        <SourceChip
          fuente={{ source_id: `sku:${actual.sku}`, titulo: 'Ver en Homecenter', url: actual.url }}
        />
        <SourceChip
          fuente={{
            source_id: req.regla_id,
            titulo: req.regla_verificada ? 'Regla verificada' : 'Regla sin verificar',
          }}
        />
      </View>

      <View style={e.decisionFila}>
        <Pressable
          onPress={() => setDecision('aprobado')}
          style={[e.decisionBtn, decision === 'aprobado' && e.decisionBtnOk]}
        >
          <Text style={[e.decisionTexto, decision === 'aprobado' && { color: c.ok }]}>
            {decision === 'aprobado' ? '✓ Aprobado' : 'Aprobar este producto'}
          </Text>
        </Pressable>
        <Pressable onPress={cambiarOpcion} style={e.decisionBtn}>
          <Text style={e.decisionTexto}>Ver otra opción</Text>
        </Pressable>
      </View>
    </Animated.View>
  );
}

const e = StyleSheet.create({
  cuerpo: { padding: s.md, paddingBottom: s.xxl },
  cuerpoEscritorio: { maxWidth: 1180, alignSelf: 'center', width: '100%' },
  vacio: { color: c.textoTenue, textAlign: 'center', marginTop: s.xxl },

  filaEscritorio: { flexDirection: 'row', gap: s.xl, alignItems: 'flex-start' },
  colPrincipal: { flex: 1.6, minWidth: 0 },
  colLateral: { flex: 1, minWidth: 320 },

  hero: {
    padding: s.lg,
    borderRadius: r.lg,
    backgroundColor: c.surface,
    alignItems: 'center',
    marginTop: s.md,
  },
  etiqueta: { color: c.textoTenue, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  total: {
    color: c.texto,
    fontSize: 37,
    fontWeight: '900',
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
  bajoTope: { color: c.textoSuave, fontSize: 12, marginTop: 4, textAlign: 'center' },
  sello: { marginTop: s.md, paddingHorizontal: s.md, paddingVertical: 5, borderRadius: r.sm },
  selloOk: { backgroundColor: 'rgba(34,197,94,0.12)' },
  selloNo: { backgroundColor: 'rgba(244,63,94,0.12)' },
  selloTexto: { fontSize: 12, fontWeight: '800' },
  selloPendiente: {
    marginTop: s.md,
    paddingHorizontal: s.md,
    paddingVertical: 5,
    borderRadius: r.sm,
    backgroundColor: 'rgba(251,191,36,0.12)',
  },
  selloPendienteTexto: { color: c.alerta, fontSize: 12, fontWeight: '800' },

  tituloSeccion: {
    color: c.textoTenue,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
    marginBottom: s.sm,
    textAlign: 'center',
  },

  negociacionDecidida: { gap: s.sm },
  recorte: {
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: 'rgba(244,63,94,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(244,63,94,0.25)',
  },
  recorteTexto: { color: c.texto, fontSize: 13, lineHeight: 18 },
  alternativa: {
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: 'rgba(34,197,94,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
  },
  alternativaTexto: { color: c.texto, fontSize: 13, lineHeight: 18 },

  item: {
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
    marginBottom: s.sm,
  },
  itemCabecera: { flexDirection: 'row', gap: s.sm },
  itemTitulo: { flexDirection: 'row', justifyContent: 'space-between', gap: s.sm },
  concepto: {
    color: c.acento,
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
    flex: 1,
  },
  subtotal: { color: c.texto, fontSize: 14, fontWeight: '800', fontVariant: ['tabular-nums'] },
  producto: { color: c.texto, fontSize: 13, fontWeight: '600', marginTop: 3, lineHeight: 18 },
  detalle: { color: c.textoTenue, fontSize: 11, marginTop: s.sm },
  formula: { color: c.textoSuave, fontSize: 11, marginTop: s.xs, fontStyle: 'italic' },
  justificacion: { color: c.textoSuave, fontSize: 12, marginTop: s.xs, lineHeight: 17 },
  aviso: { color: c.alerta, fontSize: 11, marginTop: s.xs, fontWeight: '700' },
  snapshot: { color: c.textoTenue, fontSize: 10, marginTop: s.xs },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: s.sm, marginTop: s.sm },

  decisionFila: { flexDirection: 'row', gap: s.sm, marginTop: s.md },
  decisionBtn: {
    flex: 1,
    paddingVertical: s.sm,
    borderRadius: r.sm,
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: c.borde,
    alignItems: 'center',
  },
  decisionBtnOk: { borderColor: c.ok, backgroundColor: 'rgba(34,197,94,0.1)' },
  decisionTexto: { color: c.textoSuave, fontSize: 11, fontWeight: '700' },

  faltantesBox: { marginTop: s.sm },
  faltantesTitulo: { color: c.alerta, fontSize: 11, fontWeight: '800', marginBottom: 4 },
  faltante: { color: c.alerta, fontSize: 12, marginBottom: 4 },

  fase: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: s.sm,
    padding: s.md,
    borderRadius: r.md,
    backgroundColor: c.surface,
    marginBottom: s.sm,
  },
  faseNum: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: c.surfaceAlto,
    alignItems: 'center',
    justifyContent: 'center',
  },
  faseNumTexto: { color: c.acento, fontWeight: '900', fontSize: 12 },
  faseNombre: { color: c.texto, fontSize: 13, fontWeight: '700' },
  faseConceptos: { color: c.textoTenue, fontSize: 11, marginTop: 2 },

  cta: {
    marginTop: s.xl,
    paddingVertical: 17,
    borderRadius: r.lg,
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: c.acento,
    alignItems: 'center',
  },
  ctaTexto: { color: c.acento, fontSize: 15, fontWeight: '800' },
  notaMemoria: {
    color: c.textoTenue,
    fontSize: 11,
    textAlign: 'center',
    marginTop: s.sm,
    lineHeight: 16,
  },
  ctaQA: {
    marginTop: s.md,
    paddingVertical: 14,
    borderRadius: r.lg,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
    alignItems: 'center',
  },
  ctaQATexto: { color: c.textoSuave, fontSize: 13, fontWeight: '700' },
  limites: { color: c.textoTenue, fontSize: 11, marginTop: s.xl, lineHeight: 17, fontStyle: 'italic' },
});
