"""Q&A fundamentado. Esta es la puerta unica de salida de texto al usuario:
si las herramientas no traen fuente, la respuesta es "no tengo informacion
verificada". Ese "no se" es lo que demuestra el nivel 4."""
from __future__ import annotations
import json
from src import loop, prompts, tools
from src.schemas import Cotizacion


def responder(pregunta: str, cotizacion: Cotizacion | None, traza) -> dict:
    contexto = ""
    if cotizacion:
        contexto = "Cotizacion vigente (usala como fuente, cita el SKU):\n" + json.dumps(
            {"total_cop": cotizacion.total_cop,
             "tope": cotizacion.espacio.presupuesto_cop,
             "recortes": cotizacion.recortes,
             "items": [{"concepto": i.concepto, "sku": i.producto.sku,
                        "nombre": i.producto.nombre, "precio": i.producto.precio,
                        "unidades": i.unidades_a_comprar, "url": i.producto.url,
                        "cantidad_obra": i.requerimiento.cantidad,
                        "unidad": i.requerimiento.unidad,
                        "formula": i.requerimiento.formula,
                        "fuente": i.requerimiento.fuente_regla,
                        "verificada": i.requerimiento.regla_verificada}
                       for i in cotizacion.items]}, ensure_ascii=False)
    objetivo = f"{contexto}\n\nPregunta: {pregunta}"
    ejecutores = {"consultar_guia": tools.consultar_guia,
                  "buscar_catalogo": tools.buscar_catalogo}
    r = loop.correr("qa", prompts.QA, objetivo, tools.tools_qa(), ejecutores, traza, max_iter=6)
    return {"respuesta": r["texto"] or "No tengo informacion verificada sobre eso.",
            "herramientas": traza.herramientas_usadas()}
