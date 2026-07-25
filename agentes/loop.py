"""El loop agentico: piensa -> actua -> observa -> repite, hasta terminar.
Generico: lo usan el Supervisor y los dos sub-agentes con distinta lista de tools.

No conoce el proveedor. Habla con agentes/llm.py en formato neutro, asi que
rotar llaves de Gemini o cambiar a Anthropic no toca este archivo.
"""
from __future__ import annotations
import json

from agentes import llm


def correr(actor: str, system: str, objetivo: str, tools: list[dict],
           ejecutores: dict, traza, max_iter: int = 14) -> dict:
    """Devuelve {'entrega': ..., 'texto': ..., 'iteraciones': n}.
    Un sub-agente termina llamando su tool de entrega; el resultado se captura."""
    historial: list[dict] = [{"rol": "usuario", "texto": objetivo}]
    entrega = None

    for i in range(max_iter):
        r = llm.generar(system, historial, tools, max_tokens=4096, traza=traza)
        if r.texto:
            traza.paso(actor, "piensa", r.texto[:160])
        if i == 0:
            traza.paso(actor, "llm", f"{r.modelo} via {r.llave}")

        if not r.llamadas:
            return {"entrega": entrega, "texto": r.texto, "iteraciones": i + 1}

        historial.append({"rol": "modelo", "texto": r.texto, "llamadas": r.llamadas})
        resultados = []
        for ll in r.llamadas:
            traza.paso(actor, "tool_use",
                       f"{ll.nombre}({json.dumps(ll.args, ensure_ascii=False, default=str)[:70]})")
            try:
                fn = ejecutores.get(ll.nombre)
                if fn is None:
                    salida = {"error": f"herramienta desconocida: {ll.nombre}"}
                else:
                    salida = fn(**ll.args)
                    if ll.nombre.startswith("entregar_"):
                        entrega = salida
            except TypeError as e:
                salida = {"error": f"argumentos invalidos para {ll.nombre}: {e}"}
                traza.paso(actor, "error_tool", str(e)[:120])
            except Exception as e:  # noqa: BLE001
                salida = {"error": f"{type(e).__name__}: {e}"}
                traza.paso(actor, "error_tool", str(e)[:120])
            resultados.append({
                "nombre": ll.nombre, "id": ll.id,
                "salida": json.dumps(salida, ensure_ascii=False, default=str)[:12000],
            })
        historial.append({"rol": "usuario", "resultados": resultados})

        if entrega is not None and any(l.nombre.startswith("entregar_") for l in r.llamadas):
            return {"entrega": entrega, "texto": r.texto, "iteraciones": i + 1}

    traza.paso(actor, "limite", f"max_iter={max_iter} alcanzado")
    return {"entrega": entrega, "texto": "", "iteraciones": max_iter}
