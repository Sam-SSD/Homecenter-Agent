"""El loop agentico: piensa -> actua -> observa -> repite, hasta terminar.
Generico: lo usan el Supervisor y los dos sub-agentes con distinta lista de tools.

No conoce el proveedor. Habla con agentes/llm.py en formato neutro, asi que
rotar llaves de Gemini o cambiar a Anthropic no toca este archivo.
"""
from __future__ import annotations
import inspect
import json

from agentes import llm


def _filtrar_args(fn, args: dict) -> tuple[dict, list[str]]:
    """Descarta los kwargs que el ejecutor no acepta, conservando los validos.

    Los modelos debiles inventan argumentos para tools que no los declaran
    (p.ej. delegar_cuantificacion(espacio=...)): sin este filtro cada invento
    revienta en TypeError, quema una iteracion del loop y con el antiguo
    max_iter=14 el supervisor moria sin llamar armar_presupuesto (visto en demo con
    gemini-3.5-flash-lite: 11 iteraciones seguidas perdidas en variaciones del
    mismo invento). Descartar es seguro: el dato que el modelo 'aporta' ya vive
    en el closure del ejecutor. Si la funcion acepta **kwargs, pasa todo tal
    cual; los argumentos REQUERIDOS que falten siguen fallando con TypeError,
    que es el error correcto para que el modelo se corrija."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):  # builtins sin firma introspectable
        return args, []
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return args, []
    return ({k: v for k, v in args.items() if k in params},
            [k for k in args if k not in params])


def correr(actor: str, system: str, objetivo: str, tools: list[dict],
           ejecutores: dict, traza, max_iter: int = 30) -> dict:
    """Devuelve {'entrega': ..., 'texto': ..., 'iteraciones': n}.
    Un sub-agente termina llamando su tool de entrega; el resultado se captura.

    max_iter es un freno anti-loop-infinito, no control de gasto: una corrida
    sana termina sola (entrega o respuesta sin llamadas) mucho antes del techo,
    y morir en el limite desperdicia TODOS los requests ya gastados. Con 14 el
    comprador (12 conceptos de a una busqueda por turno en modelos lite) no
    tenia margen."""
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
                    args, ignorados = _filtrar_args(fn, ll.args)
                    if ignorados:
                        traza.paso(actor, "descartado",
                                   f"{ll.nombre}: args inventados ignorados: "
                                   f"{', '.join(ignorados)}"[:120])
                    salida = fn(**args)
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
