"""Servidor HTTP para el frontend Expo (mobile/). No existia ninguna capa HTTP
en el repo: este modulo es el puente entre `Traza(on_paso=...)` (dominio/traza.py,
el mismo mecanismo que usa app.py para el progreso en vivo de Streamlit) y
Server-Sent Events.

Reglas de este archivo:
- Nunca hace aritmetica ni decide cantidades/precios: delega TODO a
  agentes.ejecutar / dominio.negociador, igual que run.py y app.py.
- No importa nada de mobile/ ni conoce React: es Python puro sirviendo JSON.
- CORS abierto (allow_origins=["*"]): no hay credenciales involucradas y la
  demo corre en localhost. Sin GZipMiddleware: rompe el streaming SSE.

    uvicorn api.servidor:app --port 8000     # desde la raiz del repo
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from dominio import catalogo, memoria
from dominio.schemas import Cotizacion, Espacio
from dominio.traza import Traza
from agentes import ejecutar, llm, qa

app = FastAPI(title="homecenter-agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single-flight: una corrida a la vez. Protege la cuota del LLM (una corrida
# agentica gasta ~35 requests contra 20/dia/modelo) y evita corridas SQLite
# solapadas en pleno demo.
_LOCK_CORRIDA = threading.Lock()


# --------------------------------------------------------------------- salud

@app.get("/salud")
def salud() -> dict:
    st = catalogo.stats()
    return {
        "ok": True,
        "catalogo": {"productos": st["productos"], "categorias": len(st["categorias"])},
        "llaves": llm.estado(),
        "modos": ["deterministico", "agentico"],
        "ocupado": _LOCK_CORRIDA.locked(),
    }


# --------------------------------------------------------------------- corrida

class PeticionCorrida(BaseModel):
    espacio: dict
    sesion: str | None = None
    deterministico: bool = True
    turno: int = 1


def _sse(evento: str, datos: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False, default=str)}\n\n"


def _errores_planos(e: ValidationError) -> list[dict]:
    """e.errors() trae 'ctx': {'error': ValueError(...)} — el objeto crudo no es
    JSON-serializable y HTTPException lo intenta serializar tal cual, lo que
    revienta un 422 limpio en un 500. Solo se pasan campos ya-string."""
    return [{"tipo": err["type"], "campo": ".".join(str(x) for x in err["loc"]), "mensaje": err["msg"]}
            for err in e.errors()]


@app.post("/corrida")
def corrida(pet: PeticionCorrida):
    try:
        espacio = Espacio.model_validate(pet.espacio)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_errores_planos(e))

    if not _LOCK_CORRIDA.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Ya hay una corrida en curso")
    _LOCK_CORRIDA.release()  # solo era para probar disponibilidad sin bloquear la peticion HTTP

    sesion = pet.sesion or f"sesion-{uuid.uuid4().hex[:8]}"
    # El turno 1 arranca en limpio: sin esto, una sesion reutilizada entre
    # ensayos deja memoria vieja y el Cuantificador sale "omitido" (memoria_hit)
    # en lo que deberia verse como una corrida fresca.
    if pet.turno == 1:
        memoria.olvidar(sesion)

    def generador():
        cola: queue.Queue = queue.Queue()
        resultado: dict = {}

        def on_paso(p: dict) -> None:
            cola.put(("paso", p))

        def trabajo() -> None:
            with _LOCK_CORRIDA:
                try:
                    traza = Traza("api", on_paso=on_paso)
                    cot, traza = ejecutor(espacio, sesion, pet.deterministico, traza)
                    if cot is None:
                        cola.put(("error", {"mensaje": "El loop agentico no armo una cotizacion"}))
                    else:
                        cot.recalcular()
                        cola.put(("cotizacion", cot.model_dump()))
                        cola.put(("fin", traza.resumen()))
                except Exception as e:  # noqa: BLE001 - nunca dejar el hilo mudo
                    cola.put(("error", {"mensaje": str(e)}))
                finally:
                    cola.put(("__fin_stream__", {}))

        def ejecutor(espacio, sesion, deterministico, traza):
            return ejecutar.cotizar(espacio, sesion=sesion, deterministico=deterministico, traza=traza)

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()

        while True:
            try:
                evento, datos = cola.get(timeout=0.5)
            except queue.Empty:
                if not hilo.is_alive() and cola.empty():
                    break
                continue
            if evento == "__fin_stream__":
                break
            yield _sse(evento, datos)

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------------- qa

class PeticionQA(BaseModel):
    pregunta: str
    cotizacion: dict | None = None
    tipo_defecto: str = "bano"


@app.post("/qa")
def preguntar(pet: PeticionQA) -> dict:
    cot: Cotizacion | None = None
    if pet.cotizacion:
        try:
            cot = Cotizacion.model_validate(pet.cotizacion)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=_errores_planos(e))
    resultado = qa.responder(pet.pregunta, cot, Traza("qa"), tipo_defecto=pet.tipo_defecto)
    return {"respuesta": resultado["respuesta"], "herramientas": resultado["herramientas"]}


# --------------------------------------------------------------------- catalogo

@app.get("/catalogo")
def buscar_catalogo(q: str = "", categoria: str | None = None, limite: int = 20) -> dict:
    categorias = [categoria] if categoria else None
    productos = catalogo.buscar(q, categorias=categorias, k=min(limite, 100))
    return {"productos": [p.model_dump() for p in productos]}
