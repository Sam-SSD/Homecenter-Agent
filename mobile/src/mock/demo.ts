/**
 * Traza congelada y paramétrica, sobre catálogo real.
 *
 * ESTO NO ES EL AGENTE. Es una reproducción: las cantidades se calculan con
 * fórmulas equivalentes a `config/reglas_obra.yaml`, y los productos son reales
 * (parseados de `cache/html/` — ver `scripts/parse_catalogo.py`), pero ningún
 * LLM interviene, ningún precio se valida en vivo, y la selección de gama es
 * determinística por percentil, no una decisión del Comprador real. La UI
 * muestra un badge de MODO DEMO permanente para que nadie lo confunda con
 * salida del agente.
 *
 * Cuando exista un `api.py` con SSE colgado de `Traza(on_paso=...)`, este
 * archivo se borra y `reproducirCache` se reemplaza por el lector del stream.
 */

import { candidatosPorGama } from '@/data/catalogo';
import type { FuenteCorridaCache } from '@/state/corrida';
import type { Cotizacion, Espacio, Gama, ItemCotizado, PasoTraza, Producto, TipoAmbiente } from '@/types';

interface LineaReceta {
  concepto: string;
  /** clave en concepto_a_categoria (categorias.json), no el texto humano */
  claveCatalogo: string;
  regla: string;
  unidad: string;
  /** 0 = cantidad fija (1, o metros_lineales) */
  porM2: number;
  prioridad: 1 | 2 | 3;
}

const MERMA = 1.1;

/** La receta por ambiente. `claveCatalogo` tiene que existir en
 *  concepto_a_categoria — si no hay candidatos reales, el ítem se reporta en
 *  `faltantes` en vez de inventarse un producto. */
const RECETAS: Record<TipoAmbiente, LineaReceta[]> = {
  bano: [
    { concepto: 'Piso cerámico', claveCatalogo: 'ceramica_piso', regla: 'piso_ceramica', unidad: 'caja', porM2: 1 / 1.44, prioridad: 1 },
    { concepto: 'Enchape de muro', claveCatalogo: 'ceramica_pared', regla: 'enchape_muro', unidad: 'caja', porM2: 2.9 / 1.5, prioridad: 1 },
    { concepto: 'Sanitario', claveCatalogo: 'sanitario', regla: 'sanitario_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Lavamanos', claveCatalogo: 'lavamanos', regla: 'lavamanos_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Grifería lavamanos', claveCatalogo: 'griferia_lavamanos', regla: 'griferia_unidad', unidad: 'Und', porM2: 0, prioridad: 2 },
    { concepto: 'Grifería ducha', claveCatalogo: 'griferia_ducha', regla: 'griferia_ducha_unidad', unidad: 'Und', porM2: 0, prioridad: 2 },
    { concepto: 'Mueble de baño', claveCatalogo: 'mueble_bano', regla: 'mueble_unidad', unidad: 'Und', porM2: 0, prioridad: 3 },
    { concepto: 'Espejo', claveCatalogo: 'espejo', regla: 'espejo_unidad', unidad: 'Und', porM2: 0, prioridad: 3 },
  ],
  cocina: [
    { concepto: 'Piso cerámico', claveCatalogo: 'ceramica_piso', regla: 'piso_ceramica', unidad: 'caja', porM2: 1 / 1.44, prioridad: 1 },
    { concepto: 'Enchape de muro', claveCatalogo: 'ceramica_pared', regla: 'enchape_muro', unidad: 'caja', porM2: 0.9 / 1.5, prioridad: 2 },
    { concepto: 'Lavaplatos', claveCatalogo: 'lavaplatos', regla: 'lavaplatos_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Mesón', claveCatalogo: 'meson_cocina', regla: 'meson_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Mueble de cocina', claveCatalogo: 'mueble_cocina', regla: 'mueble_unidad', unidad: 'Und', porM2: 0, prioridad: 2 },
    { concepto: 'Grifería cocina', claveCatalogo: 'griferia_cocina', regla: 'griferia_unidad', unidad: 'Und', porM2: 0, prioridad: 2 },
  ],
  habitacion: [
    { concepto: 'Piso cerámico', claveCatalogo: 'ceramica_piso', regla: 'piso_ceramica', unidad: 'caja', porM2: 1 / 1.44, prioridad: 1 },
    { concepto: 'Pintura muros', claveCatalogo: 'pintura', regla: 'pintura_muro', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Cama', claveCatalogo: 'cama', regla: 'cama_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Colchón', claveCatalogo: 'colchon', regla: 'colchon_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Closet', claveCatalogo: 'closet', regla: 'closet_unidad', unidad: 'Und', porM2: 0, prioridad: 3 },
  ],
  sala: [
    { concepto: 'Piso cerámico', claveCatalogo: 'ceramica_piso', regla: 'piso_ceramica', unidad: 'caja', porM2: 1 / 1.44, prioridad: 1 },
    { concepto: 'Pintura muros', claveCatalogo: 'pintura', regla: 'pintura_muro', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Sofá', claveCatalogo: 'sofa', regla: 'sofa_unidad', unidad: 'Und', porM2: 0, prioridad: 1 },
    { concepto: 'Comedor', claveCatalogo: 'comedor', regla: 'comedor_unidad', unidad: 'Und', porM2: 0, prioridad: 2 },
    { concepto: 'Iluminación', claveCatalogo: 'lampara', regla: 'luminaria_unidad', unidad: 'Und', porM2: 0, prioridad: 3 },
  ],
};

function cantidadDe(linea: LineaReceta, espacio: Espacio, area: number): number {
  if (linea.porM2 === 0) {
    if (linea.unidad === 'ml') return Math.max(1, Math.round(espacio.metros_lineales ?? espacio.largo_m));
    return 1;
  }
  return Math.max(1, Math.ceil(area * linea.porM2 * MERMA));
}

function formulaDe(linea: LineaReceta, espacio: Espacio, area: number): string {
  if (linea.porM2 === 0) return `1 por ${espacio.tipo}`;
  return `ceil(${area.toFixed(2)} m² × ${MERMA} × ${linea.porM2.toFixed(3)})`;
}

interface ItemConGamas {
  item: ItemCotizado;
  candidatos: Partial<Record<Gama, Producto>>;
  gamaActual: Gama;
}

export function generarCorrida(espacio: Espacio, turno = 1): FuenteCorridaCache {
  const area = espacio.largo_m * espacio.ancho_m;
  const receta = RECETAS[espacio.tipo];
  const tope = espacio.presupuesto_cop;

  const faltantes: string[] = [];
  const items: ItemConGamas[] = [];

  for (const linea of receta) {
    const candidatos = candidatosPorGama(linea.claveCatalogo);
    const inicial = candidatos.medio ?? candidatos.economico ?? candidatos.premium;
    if (!inicial) {
      faltantes.push(linea.concepto);
      continue;
    }
    const cantidad = cantidadDe(linea, espacio, area);
    const gamaActual: Gama = candidatos.medio ? 'medio' : inicial === candidatos.economico ? 'economico' : 'premium';

    items.push({
      candidatos,
      gamaActual,
      item: {
        concepto: linea.concepto,
        requerimiento: {
          concepto: linea.concepto,
          cantidad,
          unidad: linea.unidad,
          formula: formulaDe(linea, espacio, area),
          fuente_regla: `reglas_obra · ${linea.regla}`,
          regla_verificada: true,
          prioridad: linea.prioridad,
          regla_id: linea.regla,
        },
        producto: inicial,
        unidades_a_comprar: cantidad,
        subtotal_cop: cantidad * inicial.precio,
        justificacion: `Candidato real de la categoría "${inicial.categoria}", gama ${gamaActual}.`,
        gama: gamaActual,
        estado_precio: 'snapshot',
        precio_confirmado: null,
      },
    });
  }

  const totalDe = () => items.reduce((a, x) => a + x.item.subtotal_cop, 0);
  const recortes: string[] = [];

  // 1) Baja de gama medio→económico, empezando por la prioridad más baja
  //    (3 primero), igual que describe el Negociador real.
  const porPrioridadDesc = [...items].sort((a, b) => b.item.requerimiento.prioridad - a.item.requerimiento.prioridad);
  for (const it of porPrioridadDesc) {
    if (totalDe() <= tope) break;
    if (it.gamaActual === 'medio' && it.candidatos.economico) {
      const antes = it.item.producto.precio;
      it.item.producto = it.candidatos.economico;
      it.gamaActual = 'economico';
      it.item.gama = 'economico';
      it.item.subtotal_cop = it.item.unidades_a_comprar * it.item.producto.precio;
      it.item.justificacion = `Bajado a gama económica: mismo concepto, ${(antes - it.item.producto.precio).toLocaleString('es-CO')} COP menos por unidad.`;
      recortes.push(
        `${it.item.concepto}: gama media → económica, ahorra ${((antes - it.item.producto.precio) * it.item.unidades_a_comprar).toLocaleString('es-CO')} COP`,
      );
    }
  }

  // 2) Si sigue excedido, saca ítems desde prioridad 3 hacia abajo.
  let i = 0;
  while (totalDe() > tope && items.length > 1) {
    const idx = items.reduce(
      (peor, it, k) => (it.item.requerimiento.prioridad >= items[peor].item.requerimiento.prioridad ? k : peor),
      0,
    );
    const fuera = items.splice(idx, 1)[0];
    recortes.push(
      `${fuera.item.concepto}: se retira de esta fase (prioridad ${fuera.item.requerimiento.prioridad}), libera ${fuera.item.subtotal_cop.toLocaleString('es-CO')} COP`,
    );
    if (++i > 20) break; // guarda de seguridad, nunca debería llegar aquí
  }

  const total = totalDe();
  const holgura = Math.max(0, tope - total);

  // 3) Con holgura de sobra, sugiere subir de gama el ítem de mayor prioridad
  //    que todavía tenga premium disponible.
  const alternativas: string[] = [];
  if (holgura > 150_000) {
    const candidato = [...items]
      .sort((a, b) => a.item.requerimiento.prioridad - b.item.requerimiento.prioridad)
      .find((it) => it.gamaActual !== 'premium' && it.candidatos.premium);
    if (candidato?.candidatos.premium) {
      const delta = (candidato.candidatos.premium.precio - candidato.item.producto.precio) * candidato.item.unidades_a_comprar;
      if (delta > 0 && delta <= holgura) {
        alternativas.push(
          `Subir "${candidato.item.concepto}" a gama premium: +${delta.toLocaleString('es-CO')} COP, cabe en la holgura`,
        );
      }
    }
  }

  const finales = items.map((x) => x.item);
  const fases: Record<string, string[]> = {
    'Fase 1 — Demolición y puntos': ['Retiro de acabados', 'Puntos hidráulicos'],
    'Fase 2 — Acabados': finales.filter((i) => /piso|enchape|pintura/i.test(i.concepto)).map((i) => i.concepto),
    'Fase 3 — Aparatos y mobiliario': finales
      .filter((i) => !/piso|enchape|pintura/i.test(i.concepto))
      .map((i) => i.concepto),
  };

  const cotizacion: Cotizacion = {
    espacio,
    items: finales,
    faltantes,
    total_cop: total,
    holgura_cop: holgura,
    recortes,
    alternativas,
    fases,
    cifras_sin_fuente: [],
    generada_en: new Date().toISOString(),
    aprobada_por_humano: false,
  };

  return {
    modo: 'cache',
    pasos: turno === 2 ? pasosTurno2(espacio, total, tope) : pasosTurno1(espacio, area, finales, faltantes, recortes.length > 0),
    cotizacion,
  };
}

let reloj = 0;
const paso = (actor: PasoTraza['actor'], tipo: string, detalle: string, extra: Partial<PasoTraza> = {}): PasoTraza => {
  reloj += 0.2 + Math.random() * 0.9;
  return { i: 0, t: Math.round(reloj * 100) / 100, actor, tipo, detalle, ...extra };
};

function pasosTurno1(
  espacio: Espacio,
  area: number,
  items: ItemCotizado[],
  faltantes: string[],
  huboRecortes: boolean,
): PasoTraza[] {
  reloj = 0;
  const p: PasoTraza[] = [
    paso('supervisor', 'armado', `Objetivo: ${espacio.tipo} de ${area.toFixed(2)} m², tope ${espacio.presupuesto_cop.toLocaleString('es-CO')} COP`),
    paso('supervisor', 'tool_use', 'memoria(leer) → sesión vacía'),
    paso('cuantificador', 'piensa', 'Necesito las reglas de obra antes de cualquier cantidad'),
    paso('cuantificador', 'tool_use', 'consultar_guia("instalación y acabados")'),
  ];

  for (const it of items) {
    p.push(paso('cuantificador', 'tool_use', `obtener_regla("${it.requerimiento.regla_id}")`));
    p.push(
      paso(
        'cuantificador',
        'tool_use',
        `calcular_cantidad → ${it.requerimiento.cantidad} ${it.requerimiento.unidad} · ${it.requerimiento.formula}`,
      ),
    );
  }

  p.push(paso('cuantificador', 'divergencia', 'El LLM propuso 1 caja de más; Python manda, se conserva el cálculo determinista'));
  p.push(paso('cuantificador', 'entrega', `${items.length} requerimientos con fórmula y fuente`));

  p.push(paso('llm', 'espera', 'Cuota del modelo agotada, esperando ventana (429)'));
  p.push(paso('llm', 'fallback', 'Rota a gemini-3.5-flash-lite y reintenta'));

  for (const it of items) {
    p.push(paso('comprador', 'tool_use', `buscar_catalogo("${it.concepto.toLowerCase()}") → candidatos por gama`));
  }
  for (const f of faltantes) {
    p.push(paso('comprador', 'descartado', `Sin candidatos reales para "${f}" en el catálogo cacheado`));
  }
  p.push(paso('comprador', 'entrega', `${items.length} conceptos con candidato real y SKU verificable`));

  p.push(paso('negociador', 'armado', 'Parte de la opción media en todo'));

  if (huboRecortes) {
    p.push(paso('verificador', 'rechazo', 'TOPE_EXCEDIDO: el total supera el presupuesto'));
    p.push(paso('supervisor', 'armado', 'Recompone: baja de gama por prioridad antes de sacar ítems'));
    p.push(paso('negociador', 'armado', 'Aplica recortes sobre precios reales del catálogo'));
  }

  p.push(paso('verificador', 'aprobacion', 'Sin fallas: aritmética y fuentes cuadran'));
  p.push(paso('supervisor', 'entrega', 'Cotización lista para aprobación humana'));

  return p.map((x, i) => ({ ...x, i }));
}

function pasosTurno2(espacio: Espacio, total: number, tope: number): PasoTraza[] {
  reloj = 0;
  return [
    paso('supervisor', 'tool_use', 'memoria(leer) → sesión encontrada'),
    paso('supervisor', 'memoria_hit', 'Espacio y requerimientos reusados: no se re-cuantifica'),
    paso('negociador', 'armado', `Nuevo tope ${tope.toLocaleString('es-CO')} COP, re-optimiza sobre lo ya cuantificado`),
    paso('negociador', 'armado', `Total ${total.toLocaleString('es-CO')} COP`),
    paso('verificador', 'aprobacion', 'Sin fallas'),
    paso('supervisor', 'entrega', 'Cotización actualizada sin volver a cuantificar'),
  ].map((x, i) => ({ ...x, i }));
}
