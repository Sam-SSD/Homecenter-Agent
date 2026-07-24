"""Los dos sub-agentes. Cada uno tiene su propio loop, su propio system prompt y
su propio subconjunto de herramientas. Si fuera una sola llamada al LLM seria una
funcion, no un agente."""
from __future__ import annotations
import json
from src import catalogo, loop, prompts, tools
from src.schemas import Espacio, Producto, Requerimiento


def cuantificar(espacio: Espacio, traza) -> list[Requerimiento]:
    """AISLAMIENTO: recibe sin_presupuesto(). Si viera el tope ajustaria las
    cantidades para que quepan, y esa cotizacion en obra no alcanza."""
    payload = espacio.sin_presupuesto()
    assert "presupuesto_cop" not in payload, "fuga de presupuesto al Cuantificador"
    objetivo = ("Cuantifica los materiales para remodelar este bano.\n"
                f"Espacio: {json.dumps(payload, ensure_ascii=False)}\n"
                "Pasa este mismo objeto como argumento `espacio` de calcular_cantidad.")
    ejecutores = {
        "listar_reglas": tools.listar_reglas,
        "consultar_guia": tools.consultar_guia,
        "calcular_cantidad": lambda regla_id, espacio: tools.calcular_cantidad(regla_id, payload),
        "entregar_requerimientos": lambda requerimientos: {"ok": True, "n": len(requerimientos),
                                                           "requerimientos": requerimientos},
    }
    r = loop.correr("cuantificador", prompts.CUANTIFICADOR, objetivo,
                    tools.tools_cuantificador(), ejecutores, traza)
    entrega = (r.get("entrega") or {}).get("requerimientos") or []
    out = []
    for d in entrega:
        try:
            out.append(Requerimiento(**d))
        except Exception as e:
            traza.paso("cuantificador", "descartado", f"requerimiento invalido: {e}")
    traza.paso("cuantificador", "entrega", f"{len(out)} requerimientos")
    return out


def comprar(requerimientos: list[Requerimiento], traza) -> dict[str, dict[str, Producto]]:
    """AISLAMIENTO: recibe conceptos y unidades, no el presupuesto."""
    pedido = [{"concepto": r.concepto, "cantidad_necesaria": r.cantidad, "unidad": r.unidad}
              for r in requerimientos]
    objetivo = ("Encuentra hasta 3 opciones reales por concepto (economico, media, premium).\n"
                f"Requerimientos: {json.dumps(pedido, ensure_ascii=False)}")
    ejecutores = {
        "buscar_catalogo": tools.buscar_catalogo,
        "validar_en_vivo": tools.validar_en_vivo,
        "entregar_candidatos": lambda candidatos, justificaciones=None, sin_candidatos=None: {
            "ok": True, "candidatos": candidatos, "sin_candidatos": sin_candidatos or []},
    }
    r = loop.correr("comprador", prompts.COMPRADOR, objetivo,
                    tools.tools_comprador(), ejecutores, traza)
    crudos = (r.get("entrega") or {}).get("candidatos") or {}

    # GUARDRAIL: solo sobreviven los SKUs que existen de verdad en el catalogo.
    salida: dict[str, dict[str, Producto]] = {}
    descartados = 0
    for concepto, gamas in crudos.items():
        if not isinstance(gamas, dict):
            continue
        ok: dict[str, Producto] = {}
        for gama, sku in gamas.items():
            sku = str(sku.get("sku") if isinstance(sku, dict) else sku)
            p = catalogo.por_sku(sku)
            if p:
                ok[gama] = p
            else:
                descartados += 1
                traza.paso("comprador", "sku_inventado", f"{concepto}/{gama}: {sku} no existe")
        if ok:
            salida[concepto] = ok
    traza.paso("comprador", "entrega",
               f"{len(salida)} conceptos con candidatos, {descartados} SKUs descartados")
    return salida


def completar_gamas(candidatos: dict[str, dict[str, Producto]],
                    requerimientos: list[Requerimiento], traza) -> dict:
    """Red de seguridad determinista: si el Comprador dejo conceptos vacios, los
    llena por SQL. Queda registrado en la traza como relleno, no como hallazgo del LLM."""
    from data.categorias import CONCEPTO_A_CATEGORIA as MAPA
    for req in requerimientos:
        if candidatos.get(req.concepto):
            continue
        g = catalogo.gamas(req.concepto, MAPA.get(req.concepto), unidad_requerida=req.unidad)
        if g:
            candidatos[req.concepto] = g
            traza.paso("sistema", "relleno_deterministico", f"{req.concepto} por SQL")
    return candidatos
