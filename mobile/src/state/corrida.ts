import { useCallback, useMemo, useReducer, useRef } from 'react';

import { correrEnVivo, reproducirCache } from '@/api/stream';
import type { Actor, Cotizacion, Espacio, PasoTraza } from '@/types';

export interface EstadoActor {
  estado: 'inactivo' | 'activo' | 'listo' | 'omitido';
  razon?: string;
}

export type FuenteActiva = 'cache' | 'vivo';

export interface EstadoCorrida {
  espacio: Espacio | null;
  turno: number;
  actores: Record<Actor, EstadoActor>;
  pasos: PasoTraza[];
  cotizacion: Cotizacion | null;
  /** Cotizacion.aprobada_por_humano, pero decidido acá. El backend expone un
   *  solo bool para toda la cotización, no una aprobación por recorte. */
  aprobada: boolean | null;
  corriendo: boolean;
  error: string | null;
  /** 'cache' = traza congelada (modo Demo, badge visible). 'vivo' = SSE real
   *  contra api/servidor.py, determinista o agéntico. */
  fuente: FuenteActiva;
}

const ACTORES: Actor[] = [
  'supervisor',
  'cuantificador',
  'comprador',
  'negociador',
  'verificador',
  'llm',
  'sistema',
];

const inicial = (): EstadoCorrida => ({
  espacio: null,
  turno: 1,
  actores: Object.fromEntries(ACTORES.map((a) => [a, { estado: 'inactivo' }])) as Record<
    Actor,
    EstadoActor
  >,
  pasos: [],
  cotizacion: null,
  aprobada: null,
  corriendo: false,
  error: null,
  fuente: 'cache',
});

type Accion =
  | { tipo: 'reiniciar'; espacio: Espacio; fuente: FuenteActiva; conservarTurno?: boolean }
  | { tipo: 'arrancar' }
  | { tipo: 'paso'; paso: PasoTraza }
  | { tipo: 'cotizacion'; cotizacion: Cotizacion }
  | { tipo: 'aprobar'; aprobada: boolean }
  | { tipo: 'terminar' }
  | { tipo: 'fallo'; mensaje: string };

/** El estado de los actores se deriva de la traza, no de eventos aparte:
 *  el backend no anuncia "empiezo", solo emite pasos. */
function aplicarPaso(
  actores: Record<Actor, EstadoActor>,
  p: PasoTraza,
): Record<Actor, EstadoActor> {
  const sig = { ...actores };

  if (p.tipo === 'memoria_hit') {
    // La prueba de memoria: el Cuantificador no corre porque ya hay resultados.
    sig.cuantificador = { estado: 'omitido', razon: p.detalle || 'reusado de memoria' };
    sig.supervisor = { estado: 'activo' };
    return sig;
  }

  if (sig[p.actor]?.estado !== 'omitido') {
    sig[p.actor] = { estado: p.tipo === 'entrega' ? 'listo' : 'activo' };
  }
  return sig;
}

function reducer(st: EstadoCorrida, ac: Accion): EstadoCorrida {
  switch (ac.tipo) {
    case 'reiniciar': {
      const base = inicial();
      return {
        ...base,
        espacio: ac.espacio,
        fuente: ac.fuente,
        turno: ac.conservarTurno ? st.turno + 1 : 1,
      };
    }

    case 'arrancar':
      return { ...st, corriendo: true, error: null };

    case 'paso':
      return { ...st, pasos: [...st.pasos, ac.paso], actores: aplicarPaso(st.actores, ac.paso) };

    case 'cotizacion':
      return { ...st, cotizacion: ac.cotizacion };

    case 'aprobar':
      return {
        ...st,
        aprobada: ac.aprobada,
        cotizacion: st.cotizacion
          ? { ...st.cotizacion, aprobada_por_humano: ac.aprobada }
          : st.cotizacion,
      };

    case 'terminar':
      return { ...st, corriendo: false };

    case 'fallo':
      return { ...st, corriendo: false, error: ac.mensaje };

    // Sin este default, agregar una acción nueva devolvería undefined y la
    // pantalla quedaría en blanco en pleno demo.
    default:
      return st;
  }
}

/** Traza congelada: `pasos`/`cotizacion` ya existen de antemano. */
export interface FuenteCorridaCache {
  modo: 'cache';
  pasos: PasoTraza[];
  cotizacion: Cotizacion;
}

/** Corrida real contra api/servidor.py: los pasos llegan por SSE, la
 *  cotización se conoce solo al final del stream. */
export interface FuenteCorridaViva {
  modo: 'vivo';
  deterministico: boolean;
  sesion: string;
}

export type FuenteCorrida = FuenteCorridaCache | FuenteCorridaViva;

/** ID de sesión estable para toda la vida de la app — es lo que le permite al
 *  backend distinguir "primera cotización" (limpia memoria) de "turno 2, y si
 *  le subo a X" (memoria_hit deliberado). No es criptográfico, es solo una
 *  clave de partición en datos/memoria.db. */
const SESION_APP = `app-${Math.random().toString(36).slice(2, 10)}`;

export function useCorrida() {
  const [estado, dispatch] = useReducer(reducer, undefined, inicial);
  const abortar = useRef<{ cancelado: boolean } | null>(null);

  const correr = useCallback(
    async (espacio: Espacio, fuente: FuenteCorrida, opts: { conservarTurno?: boolean } = {}) => {
      if (abortar.current) abortar.current.cancelado = true;
      const señal = { cancelado: false };
      abortar.current = señal;

      dispatch({ tipo: 'reiniciar', espacio, fuente: fuente.modo, conservarTurno: opts.conservarTurno });
      dispatch({ tipo: 'arrancar' });

      try {
        if (fuente.modo === 'cache') {
          await reproducirCache(fuente.pasos, (p) => {
            if (señal.cancelado) return;
            dispatch({ tipo: 'paso', paso: p });
          });
          if (señal.cancelado) return;
          dispatch({ tipo: 'cotizacion', cotizacion: fuente.cotizacion });
        } else {
          const turno = opts.conservarTurno ? 2 : 1;
          await correrEnVivo(
            espacio,
            { sesion: fuente.sesion, deterministico: fuente.deterministico, turno },
            (p) => dispatch({ tipo: 'paso', paso: p }),
            (c) => dispatch({ tipo: 'cotizacion', cotizacion: c }),
            señal,
          );
        }
        if (señal.cancelado) return;
        dispatch({ tipo: 'terminar' });
      } catch (err) {
        if (señal.cancelado) return;
        dispatch({ tipo: 'fallo', mensaje: err instanceof Error ? err.message : String(err) });
      }
    },
    [],
  );

  /** Arranca una corrida en vivo con la sesión estable de la app — es el
   *  atajo que usan las pantallas en vez de construir FuenteCorridaViva a mano. */
  const correrVivo = useCallback(
    (espacio: Espacio, deterministico: boolean, opts: { conservarTurno?: boolean } = {}) =>
      correr(espacio, { modo: 'vivo', deterministico, sesion: SESION_APP }, opts),
    [correr],
  );

  const aprobar = useCallback(
    (ok: boolean) => dispatch({ tipo: 'aprobar', aprobada: ok }),
    [],
  );

  const cancelar = useCallback(() => {
    if (abortar.current) abortar.current.cancelado = true;
  }, []);

  /** Señales que el pitch necesita resaltar, derivadas una sola vez. */
  const señales = useMemo(() => {
    const rechazos = estado.pasos.filter((p) => p.tipo === 'rechazo');
    return {
      rechazos,
      huboAutocorreccion: rechazos.length > 0,
      memoriaHit: estado.pasos.some((p) => p.tipo === 'memoria_hit'),
      skusInventados: estado.pasos.filter((p) => p.tipo === 'sku_inventado').length,
      fallbacksLlm: estado.pasos.filter((p) => p.tipo === 'fallback' || p.tipo === 'espera').length,
      segundos: estado.pasos.length ? estado.pasos[estado.pasos.length - 1].t : 0,
    };
  }, [estado.pasos]);

  return { estado, correr, correrVivo, cancelar, aprobar, señales };
}
