import type { Actor } from './types';

/**
 * Oscuro por defecto: el celular del juez está en una sala iluminada y el
 * contraste alto es lo que hace que la traza se lea a 40 cm de distancia.
 */
export const c = {
  bg: '#0B0D10',
  surface: '#14181D',
  surfaceAlto: '#1C222A',
  borde: '#252C36',
  texto: '#E8EDF3',
  textoSuave: '#8A94A3',
  textoTenue: '#5A6472',

  acento: '#FF5A1F',
  ok: '#22C55E',
  alerta: '#FBBF24',
  falla: '#F43F5E',

  /** Selección neutra (ej. mapa de casa): `acento` queda reservado a CTA
   *  primario/holgura positiva, no se diluye en un selector. */
  seleccion: '#3B82F6',
} as const;

/** Un color por actor. La traza se lee por carril, no leyendo texto. */
export const carril: Record<Actor, string> = {
  supervisor: '#FF5A1F',
  cuantificador: '#22D3EE',
  comprador: '#A78BFA',
  negociador: '#FBBF24',
  verificador: '#F43F5E',
  llm: '#64748B',
  sistema: '#64748B',
};

export const nombreActor: Record<Actor, string> = {
  supervisor: 'Supervisor',
  cuantificador: 'Cuantificador',
  comprador: 'Comprador',
  negociador: 'Negociador',
  verificador: 'Verificador',
  llm: 'LLM',
  sistema: 'Sistema',
};

/** Los que se muestran en la tira de arriba. `llm` y `sistema` son
 *  infraestructura, no agentes del pitch. */
export const ACTORES_VISIBLES: Actor[] = [
  'supervisor',
  'cuantificador',
  'comprador',
  'negociador',
  'verificador',
];

export const r = { sm: 8, md: 14, lg: 20, xl: 28 } as const;
export const s = { xs: 4, sm: 8, md: 12, lg: 18, xl: 26, xxl: 36 } as const;

export const pesos = (n: number) =>
  '$' + Math.round(n).toLocaleString('es-CO', { maximumFractionDigits: 0 });
