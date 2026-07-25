/**
 * Catálogo real de Homecenter, parseado de `cache/html/` (331 páginas
 * scrapeadas, ver `scripts/parse_catalogo.py`). 2885 productos con SKU, precio
 * y URL reales. Bundleado como JSON estático: no hay red ni backend detrás.
 *
 * `marca` viene vacía en todo el dataset — el sitio no expone la marca por
 * producto en la tarjeta (los links `/brand/` que existen son filtros de
 * categoría, no atributos de producto). Se documenta en vez de inventarla.
 */
import categoriasData from './categorias.json';
import productosData from './productos.json';

import type { Gama, Producto, TipoAmbiente } from '@/types';

export const PRODUCTOS = productosData as Producto[];

interface CategoriasJson {
  categorias: Record<string, [string, TipoAmbiente[]]>;
  concepto_a_categoria: Record<string, string[]>;
  filtros: Record<string, { debe: string[]; no: string[] }>;
}

const { categorias: CATEGORIAS, concepto_a_categoria: CONCEPTO_A_CATEGORIA, filtros: FILTROS } =
  categoriasData as unknown as CategoriasJson;

const POR_CATEGORIA: Record<string, Producto[]> = {};
for (const p of PRODUCTOS) {
  (POR_CATEGORIA[p.categoria] ??= []).push(p);
}

/** Los `concepto` que tienen candidatos reales — para no ofrecer un concepto
 *  de obra que no tiene con qué materializarse. */
export const CONCEPTOS_DISPONIBLES = Object.keys(CONCEPTO_A_CATEGORIA).filter((c) =>
  (CONCEPTO_A_CATEGORIA[c] ?? []).some((cat) => (POR_CATEGORIA[cat]?.length ?? 0) > 0),
);

export function categoriasDeAmbiente(ambiente: TipoAmbiente): string[] {
  return Object.entries(CATEGORIAS)
    .filter(([, [, ambientes]]) => ambientes.includes(ambiente))
    .map(([, [nombre]]) => nombre);
}

function pasaFiltro(nombre: string, concepto: string): boolean {
  const f = FILTROS[concepto];
  if (!f) return true;
  const n = nombre.toLowerCase();
  const tieneAlguno = f.debe.some((k) => n.includes(k));
  const tieneExcluido = f.no.some((k) => n.includes(k));
  return tieneAlguno && !tieneExcluido;
}

/** Todos los candidatos de un concepto de obra, ya filtrados por nombre. */
export function productosDeConcepto(concepto: string, maxPrecio?: number): Producto[] {
  const categorias = CONCEPTO_A_CATEGORIA[concepto] ?? [];
  const vistos = new Set<string>();
  const out: Producto[] = [];
  for (const cat of categorias) {
    for (const p of POR_CATEGORIA[cat] ?? []) {
      if (vistos.has(p.sku)) continue;
      if (!pasaFiltro(p.nombre, concepto)) continue;
      if (maxPrecio !== undefined && p.precio > maxPrecio) continue;
      vistos.add(p.sku);
      out.push(p);
    }
  }
  return out.sort((a, b) => a.precio - b.precio);
}

/**
 * Tres candidatos por gama, como el Comprador real: económico, medio y
 * premium por percentil de precio dentro del concepto, no los 3 más baratos.
 */
export function candidatosPorGama(
  concepto: string,
  maxPrecio?: number,
): Partial<Record<Gama, Producto>> {
  const todos = productosDeConcepto(concepto, maxPrecio);
  if (todos.length === 0) return {};
  if (todos.length < 3) {
    return { medio: todos[Math.floor(todos.length / 2)] };
  }
  const p25 = todos[Math.floor(todos.length * 0.2)];
  const p50 = todos[Math.floor(todos.length * 0.5)];
  const p80 = todos[Math.floor(todos.length * 0.8)];
  return { economico: p25, medio: p50, premium: p80 };
}

/** Búsqueda de texto libre, para la pantalla de explorar catálogo. */
export function buscarTexto(consulta: string, limite = 40): Producto[] {
  const q = consulta.trim().toLowerCase();
  if (q.length < 2) return [];
  const terminos = q.split(/\s+/);
  return PRODUCTOS.filter((p) => {
    const n = p.nombre.toLowerCase();
    return terminos.every((t) => n.includes(t));
  }).slice(0, limite);
}

export function productosDeCategoria(categoria: string): Producto[] {
  return POR_CATEGORIA[categoria] ?? [];
}

export const CATEGORIAS_CON_PRODUCTOS = Object.keys(POR_CATEGORIA).sort(
  (a, b) => POR_CATEGORIA[b].length - POR_CATEGORIA[a].length,
);

export function nombreCategoria(id: string): string {
  return id.replace(/_/g, ' ');
}
