"""Arranque unico compartido entre la CLI (run.py) y la UI (app.py). Antes cada
entrypoint duplicaba: construir el Espacio, capturar el ValidationError del
guardrail, crear la Traza e importar el supervisor de forma diferida. Esa
duplicacion es la que se corrige aqui; nada de logica de dominio nueva."""
from __future__ import annotations
from pydantic import ValidationError

from src.schemas import Cotizacion, Espacio
from src.traza import Traza


def construir_espacio(tipo: str, largo_m: float, ancho_m: float, presupuesto_cop: int,
                      altura_enchape_m: float | None = None,
                      incluye_ducha: bool | None = None,
                      metros_lineales: float | None = None,
                      puertas: int = 1) -> tuple[Espacio | None, list[str]]:
    """Devuelve (espacio, []) si es valido, o (None, mensajes_de_error) si el
    guardrail de entrada lo rechaza. Nunca lanza: quien llama decide como
    mostrar el rechazo (CLI imprime, UI muestra un st.error)."""
    kwargs = dict(tipo=tipo, largo_m=largo_m, ancho_m=ancho_m,
                  presupuesto_cop=presupuesto_cop, puertas=puertas)
    if altura_enchape_m is not None:
        kwargs["altura_enchape_m"] = altura_enchape_m
    if incluye_ducha is not None:
        kwargs["incluye_ducha"] = incluye_ducha
    if metros_lineales is not None:
        kwargs["metros_lineales"] = metros_lineales
    try:
        return Espacio(**kwargs), []
    except ValidationError as e:
        return None, [err["msg"] for err in e.errors()]


def cotizar(espacio: Espacio, sesion: str = "cli", deterministico: bool = False,
           traza: Traza | None = None) -> tuple[Cotizacion | None, Traza]:
    """Corre el modo agentico o el deterministico. Import diferido del
    supervisor: evita el coste de import de src.llm cuando solo se quiere
    construir/validar un Espacio (p.ej. en tests)."""
    from src import supervisor
    traza = traza or Traza("ejecutar")
    if deterministico:
        return supervisor.correr_deterministico(espacio, sesion=sesion, traza=traza)
    return supervisor.correr_agentico(espacio, sesion=sesion, traza=traza)


def preguntar(pregunta: str, cotizacion: Cotizacion | None, traza: Traza) -> str:
    from src import qa
    return qa.responder(pregunta, cotizacion, traza)["respuesta"]
