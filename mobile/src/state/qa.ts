import { useCallback, useState } from 'react';

import { mockPreguntar, preguntar } from '@/api/qa';
import type { FuenteActiva } from '@/state/corrida';
import type { Cotizacion } from '@/types';

export interface MensajeQA {
  id: string;
  rol: 'usuario' | 'agente';
  texto: string;
  herramientas?: string[];
}

/**
 * Historial de Q&A, local a la pantalla `/qa`. Solo LEE `cotizacion` (viene
 * de `useCorridaCtx()` en el componente que llama a este hook) — no muta el
 * estado de la corrida, por eso vive aparte de `state/corrida.ts` y no
 * dentro de `CorridaProvider`. El backend no tiene sesión de Q&A (solo de
 * cantidades, vía `dominio/memoria.py`), así que perder el hilo al cerrar la
 * pantalla es honesto, no un bug.
 *
 * `fuente` decide si se pregunta al backend real (`POST /qa`) o al mock local
 * — la traza congelada del modo Demo no tiene un backend detrás que pueda
 * responder de verdad.
 */
export function useQA(cotizacion: Cotizacion | null, fuente: FuenteActiva = 'vivo') {
  const [mensajes, setMensajes] = useState<MensajeQA[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enviar = useCallback(
    async (pregunta: string) => {
      const texto = pregunta.trim();
      if (!texto || enviando) return;

      const idUsuario = `u-${mensajes.length}`;
      setMensajes((m) => [...m, { id: idUsuario, rol: 'usuario', texto }]);
      setEnviando(true);
      setError(null);

      try {
        const r = fuente === 'cache' ? await mockPreguntar(texto, cotizacion) : await preguntar(texto, cotizacion);
        setMensajes((m) => [
          ...m,
          { id: `a-${m.length}`, rol: 'agente', texto: r.respuesta, herramientas: r.herramientas },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setEnviando(false);
      }
    },
    [cotizacion, enviando, mensajes.length, fuente],
  );

  return { mensajes, enviando, error, enviar };
}
