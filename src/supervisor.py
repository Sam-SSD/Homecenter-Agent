"""El Supervisor: loop propio que delega, lee memoria y decide si repetir.

Dos modos:
  correr_agentico()      -> el supervisor es un loop LLM (arquitectura completa)
  correr_deterministico() -> los mismos pasos en codigo (red de seguridad de demo)

El modo deterministico existe porque a las 11:50 frente al jurado la prioridad es
que funcione. Se declara en el README, no se esconde.
"""
from __future__ import annotations
import json
from src import loop, memoria, negociador, prompts, subagentes, tools, verificador
from src.schemas import Cotizacion, Espacio
from src.traza import Traza

MAX_VUELTAS = 3


def _ejecutores(espacio: Espacio, traza, sesion: str, estado: dict) -> dict:
    def delegar_cuantificacion() -> dict:
        reqs = subagentes.cuantificar(espacio, traza)
        estado["requerimientos"] = reqs
        return {"n": len(reqs), "requerimientos": [r.model_dump() for r in reqs]}

    def delegar_compra() -> dict:
        reqs = estado.get("requerimientos") or []
        if not reqs:
            return {"error": "todavia no hay requerimientos; llama delegar_cuantificacion"}
        cands = subagentes.comprar(reqs, traza)
        cands = subagentes.completar_gamas(cands, reqs, traza)
        estado["candidatos"] = cands
        return {"conceptos": list(cands),
                "sin_candidatos": [r.concepto for r in reqs if r.concepto not in cands]}

    def armar_presupuesto() -> dict:
        reqs, cands = estado.get("requerimientos"), estado.get("candidatos")
        if not reqs or not cands:
            return {"error": "faltan requerimientos o candidatos"}
        cot = negociador.armar(espacio, reqs, cands)
        estado["cotizacion"] = cot
        traza.paso("negociador", "armado",
                   f"total ${cot.total_cop:,} de tope ${espacio.presupuesto_cop:,}, "
                   f"{len(cot.recortes)} recortes")
        return {"total_cop": cot.total_cop, "holgura_cop": cot.holgura_cop,
                "items": len(cot.items), "recortes": cot.recortes[:6],
                "faltantes": cot.faltantes}

    def verificar_cotizacion() -> dict:
        cot = estado.get("cotizacion")
        if not cot:
            return {"error": "no hay cotizacion"}
        fallas = verificador.verificar(cot)
        estado["fallas"] = fallas
        estado["vueltas"] = estado.get("vueltas", 0) + 1
        if fallas:
            traza.paso("verificador", "rechazo",
                       f"{len(fallas)} fallas: {[f.codigo for f in fallas][:4]}")
        else:
            traza.paso("verificador", "aprobacion", "sin fallas")
        return {"aprobada": not fallas, "vuelta": estado["vueltas"],
                "fallas": [f.model_dump() for f in fallas]}

    return {
        "leer_memoria": lambda: {"memoria": memoria.todo(sesion)},
        "escribir_memoria": lambda clave, valor: (memoria.escribir(sesion, clave, valor),
                                                  {"ok": True})[1],
        "delegar_cuantificacion": delegar_cuantificacion,
        "delegar_compra": delegar_compra,
        "armar_presupuesto": armar_presupuesto,
        "verificar_cotizacion": verificar_cotizacion,
    }


def _tools_supervisor() -> list[dict]:
    t = tools._t
    return [
        t("leer_memoria", "Lee el estado de la sesion: espacio, requerimientos y "
          "cotizaciones anteriores. Llamala SIEMPRE primero.", {}, []),
        t("delegar_cuantificacion", "Delega en el Cuantificador, que calcula cantidades "
          "de obra sin ver el presupuesto.", {}, []),
        t("delegar_compra", "Delega en el Comprador, que busca productos reales sin ver "
          "el presupuesto.", {}, []),
        t("armar_presupuesto", "Optimiza la lista bajo el tope y devuelve los recortes "
          "aplicados en pesos.", {}, []),
        t("verificar_cotizacion", "Audita la cotizacion. Devuelve las fallas para que "
          "decidas que rehacer.", {}, []),
        t("escribir_memoria", "Guarda algo en la sesion para el proximo turno.",
          {"clave": {"type": "string"}, "valor": {"type": "string"}}, ["clave", "valor"]),
    ]


def correr_agentico(espacio: Espacio, sesion: str = "demo",
                    traza: Traza | None = None) -> tuple[Cotizacion | None, Traza]:
    traza = traza or Traza("supervisor")
    estado: dict = {}
    memoria.escribir(sesion, "espacio", espacio.model_dump())
    objetivo = (f"Cotiza este {espacio.tipo} dentro del tope.\n"
                f"Espacio: {json.dumps(espacio.model_dump(), ensure_ascii=False)}")
    loop.correr("supervisor", prompts.SUPERVISOR, objetivo,
                _tools_supervisor(), _ejecutores(espacio, traza, sesion, estado), traza)
    cot = estado.get("cotizacion")
    if cot:
        cot.recalcular()
        memoria.escribir(sesion, "ultima_cotizacion", cot.model_dump())
    return cot, traza


def correr_deterministico(espacio: Espacio, sesion: str = "demo",
                          traza: Traza | None = None,
                          reusar_requerimientos: bool = True) -> tuple[Cotizacion, Traza]:
    from evals.nucleo import candidatos_de, requerimientos_de
    traza = traza or Traza("deterministico")
    guardados = memoria.leer(sesion, "requerimientos") if reusar_requerimientos else None
    if guardados:
        from src.schemas import Requerimiento
        reqs = [Requerimiento(**r) for r in guardados]
        traza.paso("supervisor", "memoria_hit", f"{len(reqs)} requerimientos reusados")
    else:
        reqs = requerimientos_de(espacio)
        traza.paso("cuantificador", "entrega", f"{len(reqs)} requerimientos")
        memoria.escribir(sesion, "requerimientos", [r.model_dump() for r in reqs])
    cands = candidatos_de(reqs)
    traza.paso("comprador", "entrega", f"{len(cands)} conceptos con candidatos")
    cot = negociador.armar(espacio, reqs, cands)
    traza.paso("negociador", "armado", f"total ${cot.total_cop:,}, {len(cot.recortes)} recortes")
    fallas = verificador.verificar(cot)
    traza.paso("verificador", "rechazo" if fallas else "aprobacion",
               f"{len(fallas)} fallas" if fallas else "sin fallas")
    memoria.escribir(sesion, "espacio", espacio.model_dump())
    memoria.escribir(sesion, "ultima_cotizacion", cot.model_dump())
    return cot, traza
