"""Q&A fundamentado. Esta es la puerta unica de salida de texto al usuario:
si las herramientas no traen fuente, la respuesta es "no tengo informacion
verificada". Ese "no se" es lo que demuestra el nivel 4."""
from __future__ import annotations
import json
from agentes import llm, loop, prompts, tools
from dominio.schemas import Cotizacion

MAX_ITER = 6


def responder(pregunta: str, cotizacion: Cotizacion | None, traza,
             tipo_defecto: str = "bano") -> dict:
    """Nunca deja subir una excepcion hasta la UI: SinLlavesDisponibles y
    PeticionMalFormada (agentes/llm.py) suben desde loop.correr sin capturar,
    y antes rompian el render de Streamlit a medio pintar. Aqui se distinguen
    tres desenlaces, todos con `herramientas` propias de ESTA pregunta (traza
    nueva, no la de la cotizacion: esa mezclaba tools del supervisor/comprador
    con las del Q&A)."""
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
                  "buscar_catalogo": tools.buscar_catalogo,
                  "ficha_producto": tools.ficha_producto,
                  "comparar_productos": tools.comparar_productos,
                  "recomendar_por_specs": tools.recomendar_por_specs}
    tipo = cotizacion.espacio.tipo if cotizacion else tipo_defecto
    try:
        r = loop.correr("qa", prompts.qa(tipo), objetivo, tools.tools_qa(),
                        ejecutores, traza, max_iter=MAX_ITER)
    except llm.SinLlavesDisponibles as e:
        return {"respuesta": f"Sin cupo del modelo ahora mismo: {e}",
                "herramientas": [], "error": "sin_llaves"}
    except llm.PeticionMalFormada as e:
        return {"respuesta": f"El proveedor rechazo la peticion: {e}",
                "herramientas": [], "error": "peticion_malformada"}

    if not r["texto"] and r["iteraciones"] >= MAX_ITER:
        respuesta = ("Me quede sin pasos para responder con fuentes verificadas. "
                    "Intenta con una pregunta mas puntual (un SKU o dos productos a comparar).")
    else:
        respuesta = r["texto"] or "No tengo informacion verificada sobre eso."
    return {"respuesta": respuesta, "herramientas": traza.herramientas_usadas()}
