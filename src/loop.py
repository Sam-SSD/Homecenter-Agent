"""El loop agentico: piensa -> actua -> observa -> repite, hasta terminar.
Generico: lo usan el Supervisor y los dos sub-agentes con distinta lista de tools.
Que quepa en una pantalla es parte del punto."""
from __future__ import annotations
import json, os
from anthropic import Anthropic

MODELO = os.environ.get("MODELO", "claude-sonnet-5")
_cliente: Anthropic | None = None


def cliente() -> Anthropic:
    global _cliente
    if _cliente is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("falta ANTHROPIC_API_KEY (copia .env.example a .env)")
        _cliente = Anthropic()
    return _cliente


def correr(actor: str, system: str, objetivo: str, tools: list[dict],
           ejecutores: dict, traza, max_iter: int = 14) -> dict:
    """Devuelve {'entrega': ..., 'texto': ..., 'iteraciones': n}.
    Un sub-agente termina llamando su tool de entrega; el resultado se captura."""
    mensajes = [{"role": "user", "content": objetivo}]
    entrega = None

    for i in range(max_iter):
        r = cliente().messages.create(
            model=MODELO, max_tokens=4096, system=system,
            tools=tools, messages=mensajes,
        )
        texto = " ".join(b.text for b in r.content if b.type == "text").strip()
        if texto:
            traza.paso(actor, "piensa", texto[:160])

        usos = [b for b in r.content if b.type == "tool_use"]
        if not usos:
            return {"entrega": entrega, "texto": texto, "iteraciones": i + 1}

        mensajes.append({"role": "assistant", "content": r.content})
        resultados = []
        for u in usos:
            traza.paso(actor, "tool_use", f"{u.name}({json.dumps(u.input, ensure_ascii=False)[:70]})")
            try:
                salida = ejecutores[u.name](**u.input)
                if u.name.startswith("entregar_"):
                    entrega = salida
            except Exception as e:
                salida = {"error": f"{type(e).__name__}: {e}"}
                traza.paso(actor, "error_tool", str(e)[:120])
            texto_salida = json.dumps(salida, ensure_ascii=False, default=str)[:12000]
            resultados.append({"type": "tool_result", "tool_use_id": u.id,
                               "content": texto_salida})
        mensajes.append({"role": "user", "content": resultados})

        if entrega is not None and any(u.name.startswith("entregar_") for u in usos):
            return {"entrega": entrega, "texto": texto, "iteraciones": i + 1}

    traza.paso(actor, "limite", f"max_iter={max_iter} alcanzado")
    return {"entrega": entrega, "texto": "", "iteraciones": max_iter}
