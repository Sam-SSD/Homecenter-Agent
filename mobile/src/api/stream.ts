import type { Cotizacion, Espacio, PasoTraza } from '@/types';
import { API_URL } from '@/api/config';

/**
 * Reproductor de trazas congeladas (modo Demo) y lector del stream en vivo
 * (modo Determinista/Agéntico) contra `api/servidor.py::POST /corrida`.
 */

/** Un paso que tardó 6 s en la corrida real no puede congelar el demo 6 s. */
const MIN_MS = 90;
const MAX_MS = 900;

export async function reproducirCache(
  pasos: PasoTraza[],
  onPaso: (p: PasoTraza) => void,
  velocidad = 1,
): Promise<void> {
  let anterior = pasos.length ? pasos[0].t : 0;

  for (const paso of pasos) {
    const delta = Math.max(0, paso.t - anterior) * 1000;
    anterior = paso.t;

    const espera = Math.min(MAX_MS, Math.max(MIN_MS, delta)) / velocidad;
    await new Promise((r) => setTimeout(r, espera));

    onPaso(paso);
  }
}

export interface OpcionesCorridaViva {
  sesion: string;
  deterministico: boolean;
  turno?: number;
}

export interface SeñalCancelacion {
  cancelado: boolean;
}

/**
 * Lee el SSE de POST /corrida y llama onPaso/onCotizacion a medida que llegan
 * los eventos `paso`/`cotizacion`/`fin`/`error`. Un chunk TCP puede cortar un
 * evento SSE por la mitad, así que se acumula en un buffer y solo se parsean
 * los bloques completos (separados por doble salto de línea).
 *
 * Piso de ritmo: el modo determinista corre en ~300 ms (sin LLM, sin red) y
 * sin este piso `AgentLanes` parpadearía y `BudgetBar` saltaría a lleno de
 * golpe — justo en el modo que corre por defecto. Se reutiliza el mismo
 * MIN_MS que `reproducirCache`, no se inventa un segundo clamp.
 */
export async function correrEnVivo(
  espacio: Espacio,
  opts: OpcionesCorridaViva,
  onPaso: (p: PasoTraza) => void,
  onCotizacion: (c: Cotizacion) => void,
  señal: SeñalCancelacion,
): Promise<void> {
  const resp = await fetch(`${API_URL}/corrida`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      espacio,
      sesion: opts.sesion,
      deterministico: opts.deterministico,
      turno: opts.turno ?? 1,
    }),
  });

  if (!resp.ok) {
    const detalle = await resp.text().catch(() => '');
    throw new Error(`El backend rechazó la corrida (${resp.status}): ${detalle.slice(0, 200)}`);
  }
  if (!resp.body) {
    throw new Error('Este navegador no expone response.body: no se puede leer el stream.');
  }

  const lector = resp.body.getReader();
  const decodificador = new TextDecoder();
  let buffer = '';
  let ultimoT = 0;

  const procesarBloque = async (bloque: string) => {
    let evento = 'message';
    const lineasDatos: string[] = [];
    for (const linea of bloque.split('\n')) {
      if (linea.startsWith('event:')) evento = linea.slice(6).trim();
      else if (linea.startsWith('data:')) lineasDatos.push(linea.slice(5).trim());
    }
    if (!lineasDatos.length) return;
    const datos = JSON.parse(lineasDatos.join('\n'));

    if (evento === 'paso') {
      const p = datos as PasoTraza;
      const delta = Math.max(0, p.t - ultimoT) * 1000;
      ultimoT = p.t;
      const espera = Math.min(MAX_MS, Math.max(MIN_MS, delta));
      await new Promise((r) => setTimeout(r, espera));
      if (!señal.cancelado) onPaso(p);
    } else if (evento === 'cotizacion') {
      if (!señal.cancelado) onCotizacion(datos as Cotizacion);
    } else if (evento === 'error') {
      throw new Error(datos.mensaje || 'La corrida falló en el backend');
    }
    // "fin" no lleva acción propia: la cotización ya se despachó.
  };

  try {
    while (true) {
      if (señal.cancelado) {
        await lector.cancel().catch(() => {});
        return;
      }
      const { done, value } = await lector.read();
      if (done) break;
      buffer += decodificador.decode(value, { stream: true });

      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const bloque = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        await procesarBloque(bloque);
      }
    }
    if (buffer.trim()) await procesarBloque(buffer);
  } finally {
    lector.releaseLock();
  }
}
