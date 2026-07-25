/**
 * Espejo de `dominio/schemas.py` del repo Homecenter-Agent.
 *
 * Regla dura: los nombres de campo son los del backend, sin traducir y sin
 * "mejorar". Si aquí dice `total_cop` es porque allá dice `total_cop`. El día
 * que alguien conecte un endpoint real, el JSON tiene que caer directo.
 */

export type TipoAmbiente = 'bano' | 'cocina' | 'habitacion' | 'sala';

export const AMBIENTES: { id: TipoAmbiente; nombre: string }[] = [
  { id: 'bano', nombre: 'Baño' },
  { id: 'cocina', nombre: 'Cocina' },
  { id: 'habitacion', nombre: 'Habitación' },
  { id: 'sala', nombre: 'Sala' },
];

/** Los rangos son los de los Field(...) de Pydantic. Si la UI valida distinto,
 *  el backend rechaza y el usuario ve un 422 en vez de un mensaje útil. */
export const LIMITES = {
  lado_m: { min: 0.6, max: 14, exclusivo: true },
  altura_m: { min: 1.8, max: 4.5, exclusivo: true },
  altura_enchape_m: { min: 0.3, max: 4.5 },
  metros_lineales: { min: 0, max: 20 },
  puertas: { min: 0, max: 3 },
} as const;

/** Límites por ambiente de `dominio/schemas.py::LIMITES` — el guardrail real
 *  rechaza un Espacio coherente con `LIMITES` genérico pero incoherente con
 *  esto (ej. una sala de 45 m² pasa `lado_m`/`altura_m` pero viola
 *  `area_max` de sala=60... y un baño de 30 m² viola `area_max` de baño=25
 *  aunque cumpla `lado_m`). Validar ambos, no solo el genérico. */
export const LIMITES_AMBIENTE: Record<
  TipoAmbiente,
  { area_max: number; lado_max: number; presupuesto_min: number }
> = {
  bano: { area_max: 25, lado_max: 8, presupuesto_min: 500_000 },
  cocina: { area_max: 40, lado_max: 10, presupuesto_min: 1_500_000 },
  habitacion: { area_max: 45, lado_max: 12, presupuesto_min: 800_000 },
  sala: { area_max: 60, lado_max: 14, presupuesto_min: 1_000_000 },
};

/** Espeja `DEFAULTS_POR_TIPO` de `dominio/schemas.py`: si el campo no se
 *  pide explícito, el backend usa esto. La UI debe mostrar el valor real
 *  antes de que el usuario lo toque, no un input vacío. */
export const DEFAULTS_POR_TIPO: Record<
  TipoAmbiente,
  { altura_enchape_m?: number; incluye_ducha?: boolean; metros_lineales?: number }
> = {
  bano: { altura_enchape_m: 2.0, incluye_ducha: true },
  cocina: { altura_enchape_m: 2.0, metros_lineales: 3.0 },
  habitacion: { metros_lineales: 3.0 },
  sala: {},
};

export interface Espacio {
  tipo: TipoAmbiente;
  largo_m: number;
  ancho_m: number;
  altura_m: number;
  altura_enchape_m?: number | null;
  incluye_ducha?: boolean | null;
  puertas: number;
  metros_lineales?: number | null;
  /** El presupuesto vive DENTRO de Espacio, no como parámetro aparte. */
  presupuesto_cop: number;
}

export interface Producto {
  sku: string;
  nombre: string;
  marca: string;
  categoria: string;
  cat_id: string;
  precio: number;
  precio_antes?: number | null;
  unidad: string;
  kg_por_bulto?: number | null;
  unidad_incierta: boolean;
  url: string;
  imagen_url?: string | null;
  capturado_en: string;
  /** Specs tecnicas del PDP, cuando el scraper las capturo. */
  specs?: Record<string, string>;
  rating?: number | null;
  total_reviews?: number | null;
  modelo?: string;
}

export interface Requerimiento {
  concepto: string;
  cantidad: number;
  unidad: string;
  formula: string;
  fuente_regla: string;
  regla_verificada: boolean;
  prioridad: number;
  regla_id: string;
}

/** El backend distingue precio de snapshot, precio confirmado en vivo, y
 *  precio que cambió entre uno y otro. Esa distinción es el grounding. */
export type EstadoPrecio = 'snapshot' | 'en_vivo' | 'cambio';

/** El backend modela `ItemCotizado.gama` como string libre (default "media").
 *  Este union es solo para la selección local de candidatos por percentil de
 *  precio en `data/catalogo.ts` — no es parte del contrato del backend. */
export type Gama = 'economico' | 'medio' | 'premium';

export interface ItemCotizado {
  concepto: string;
  requerimiento: Requerimiento;
  producto: Producto;
  unidades_a_comprar: number;
  subtotal_cop: number;
  justificacion: string;
  gama: string;
  estado_precio: EstadoPrecio;
  precio_confirmado?: number | null;
  /** true si un swap manual del usuario fijo este producto (no lo toca el
   *  negociador al re-optimizar). */
  fijado_por_usuario?: boolean;
}

export interface Falla {
  codigo: string;
  mensaje: string;
  concepto: string;
}

export interface Cotizacion {
  espacio: Espacio;
  items: ItemCotizado[];
  faltantes: string[];
  total_cop: number;
  holgura_cop: number;
  /** OJO: son strings, no objetos. El backend no modela el recorte con
   *  ahorro/impacto, así que la UI no puede inventarse esos números. */
  recortes: string[];
  alternativas: string[];
  /** { "Fase 1 — Demolición": ["concepto", ...] } */
  fases: Record<string, string[]>;
  cifras_sin_fuente: string[];
  generada_en: string;
  aprobada_por_humano: boolean;
  /** Piso de gasto que el negociador no puede recortar mas. 0 si no aplica. */
  minimo_viable_cop?: number;
}

/* ------------------------------------------------------------------ */
/* La traza. Espeja `Traza.paso()` de dominio/traza.py:14             */
/*   {"i", "t", "actor", "tipo", "detalle", **extra}                   */
/* ------------------------------------------------------------------ */

export type Actor =
  | 'supervisor'
  | 'cuantificador'
  | 'comprador'
  | 'negociador'
  | 'verificador'
  | 'llm'
  | 'sistema';

/** Los `tipo` que realmente emite el backend hoy. Se sacaron grepeando
 *  `.paso(` en `agentes/loop.py`, `agentes/llm.py`, `agentes/supervisor.py`
 *  y `agentes/subagentes.py` del repo Homecenter-Agent, no de la imaginación. */
export type TipoPaso =
  | 'tool_use'
  | 'piensa'
  | 'llm'
  | 'error_tool'
  | 'limite'
  | 'entrega'
  | 'armado'
  | 'memoria_hit'
  | 'rechazo'
  | 'aprobacion'
  | 'descartado'
  | 'divergencia'
  | 'sku_inventado'
  | 'espera'
  | 'fallback'
  | 'relleno_deterministico';

export interface PasoTraza {
  /** índice incremental */
  i: number;
  /** segundos desde el arranque de la corrida */
  t: number;
  actor: Actor;
  tipo: TipoPaso | string;
  detalle: string;
  /** extras que el backend adjunta con **kwargs (sku=, max_iter=) */
  sku?: string;
  max_iter?: number;
  [extra: string]: unknown;
}

/** No lo emite el backend: lo sintetiza la app al terminar la corrida offline. */
export interface CorridaTerminada {
  cotizacion: Cotizacion;
}
