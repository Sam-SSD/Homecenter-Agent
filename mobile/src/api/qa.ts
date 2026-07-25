import type { Cotizacion } from '@/types';
import { API_URL } from '@/api/config';

/**
 * Q&A sobre la cotización generada.
 *
 * Espeja el contrato real de `agentes/qa.py::responder(pregunta, cotizacion,
 * traza) -> {"respuesta": str, "herramientas": list[str]}`, servido por
 * `api/servidor.py::POST /qa`. Es de un solo turno por llamada (sin historial
 * en el propio backend); el historial de la conversación vive en el cliente,
 * en `state/qa.ts`.
 *
 * `mockPreguntar` (abajo) se conserva como fallback para el modo Demo (traza
 * congelada, sin backend real): solo referencia SKUs/fuentes que YA existen
 * en la `cotizacion` recibida, nunca inventa un producto o una fuente nueva.
 */

export interface RespuestaQA {
  respuesta: string;
  herramientas: string[];
}

const SIN_FUENTE = 'No tengo información verificada sobre eso.';

export async function preguntar(
  pregunta: string,
  cotizacion: Cotizacion | null,
): Promise<RespuestaQA> {
  const resp = await fetch(`${API_URL}/qa`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pregunta,
      cotizacion,
      tipo_defecto: cotizacion?.espacio.tipo ?? 'bano',
    }),
  });
  if (!resp.ok) {
    throw new Error(`El backend rechazó la pregunta (${resp.status})`);
  }
  return (await resp.json()) as RespuestaQA;
}

const MIN_MS = 500;
const MAX_MS = 1100;

function esperar(): Promise<void> {
  const ms = MIN_MS + Math.random() * (MAX_MS - MIN_MS);
  return new Promise((r) => setTimeout(r, ms));
}

/** Fallback del modo Demo: no hay backend real detrás de la traza congelada. */
export async function mockPreguntar(
  pregunta: string,
  cotizacion: Cotizacion | null,
): Promise<RespuestaQA> {
  await esperar();

  if (!cotizacion) {
    return { respuesta: SIN_FUENTE, herramientas: [] };
  }

  const texto = pregunta.toLowerCase();

  const item = cotizacion.items.find((it) =>
    texto.includes(it.concepto.toLowerCase()) || it.concepto.toLowerCase().includes(texto.trim()),
  );
  if (item) {
    const req = item.requerimiento;
    const fuente = req.regla_verificada ? `fuente verificada: ${req.fuente_regla}` : 'estimación sin fuente verificada';
    return {
      respuesta:
        `Para ${item.concepto} se calculó ${req.cantidad} ${req.unidad} (${req.formula}). ` +
        `Se compró ${item.unidades_a_comprar} ${item.producto.unidad} de ${item.producto.nombre} ` +
        `(SKU ${item.producto.sku}) por ${item.subtotal_cop.toLocaleString('es-CO')} COP. ${fuente}.`,
      herramientas: ['consultar_guia', 'buscar_catalogo'],
    };
  }

  if (texto.includes('total') || texto.includes('presupuesto') || texto.includes('holgura')) {
    return {
      respuesta:
        `El total de la cotización es ${cotizacion.total_cop.toLocaleString('es-CO')} COP ` +
        `contra un tope de ${cotizacion.espacio.presupuesto_cop.toLocaleString('es-CO')} COP ` +
        `(holgura de ${cotizacion.holgura_cop.toLocaleString('es-CO')} COP).`,
      herramientas: [],
    };
  }

  if (texto.includes('recorte') || texto.includes('negocia')) {
    if (cotizacion.recortes.length === 0) {
      return { respuesta: 'Esta cotización no necesitó ningún recorte para caber en el presupuesto.', herramientas: [] };
    }
    return {
      respuesta: `Se hicieron ${cotizacion.recortes.length} recortes: ${cotizacion.recortes.join('; ')}.`,
      herramientas: [],
    };
  }

  return { respuesta: SIN_FUENTE, herramientas: [] };
}
