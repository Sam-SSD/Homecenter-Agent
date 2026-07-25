"""Los dos sub-agentes. Cada uno tiene su propio loop, su propio system prompt y
su propio subconjunto de herramientas. Si fuera una sola llamada al LLM seria una
funcion, no un agente."""
from __future__ import annotations
import json
from agentes import llm, loop, prompts, tools
from dominio import catalogo
from dominio.schemas import Espacio, Producto, Requerimiento


def cuantificar(espacio: Espacio, traza) -> list[Requerimiento]:
    """AISLAMIENTO: recibe sin_presupuesto(). Si viera el tope ajustaria las
    cantidades para que quepan, y esa cotizacion en obra no alcanza."""
    payload = espacio.sin_presupuesto()
    assert "presupuesto_cop" not in payload, "fuga de presupuesto al Cuantificador"
    objetivo = (f"Cuantifica los materiales para remodelar este {espacio.tipo}.\n"
                f"Espacio: {json.dumps(payload, ensure_ascii=False)}\n"
                "Pasa este mismo objeto como argumento `espacio` de calcular_cantidad.")
    # REGLA 1: calcular_cantidad ya devuelve el Requerimiento completo, con la
    # formula sustituida y la fuente que derivo Python. Se acumula aqui y ESO es
    # lo que se entrega. Si se dejara armar la lista al LLM, el modelo copia
    # concepto/cantidad/unidad y pierde formula y fuente_regla: cifras sin fuente
    # y aritmetica transcrita a mano, justo lo que la regla prohibe.
    calculados: dict[str, Requerimiento] = {}

    def _calcular(regla_id, **_):
        salida = tools.calcular_cantidad(regla_id, payload)
        if isinstance(salida, dict) and not salida.get("error"):
            try:  # el ultimo gana: cubre el reintento tras un regla_id errado
                calculados[regla_id] = Requerimiento(**salida)
            except Exception as e:  # noqa: BLE001
                traza.paso("cuantificador", "descartado", f"regla {regla_id}: {e}")
        return salida

    ejecutores = {
        # el tipo lo inyecta Python, igual que el espacio en calcular_cantidad:
        # el Cuantificador de un ambiente no debe poder pedir reglas de otro.
        "listar_reglas": lambda **_: tools.listar_reglas(espacio.tipo),
        "consultar_guia": tools.consultar_guia,
        "calcular_cantidad": _calcular,
        # el payload del LLM se ignora como fuente de cifras: solo dice "ya termine"
        "entregar_requerimientos": lambda requerimientos=None, **_: {
            "ok": True, "listados": len(llm.como_lista(requerimientos)),
            "requerimientos": [r.model_dump() for r in calculados.values()]},
    }
    r = loop.correr("cuantificador", prompts.cuantificador(espacio.tipo), objetivo,
                    tools.tools_cuantificador(), ejecutores, traza,
                    # los modelos lite llaman calcular_cantidad de a una por turno:
                    # 1 listar + 1 consultar + 12 reglas + la entrega no caben en 14
                    max_iter=24)
    out = list(calculados.values())
    listados = (r.get("entrega") or {}).get("listados")
    if listados is not None and listados != len(out):
        traza.paso("cuantificador", "divergencia",
                   f"el LLM listo {listados}, Python calculo {len(out)}: se entregan los calculados")
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
        "entregar_candidatos": lambda candidatos=None, justificaciones=None, sin_candidatos=None, **_: {
            "ok": True, "candidatos": llm.como_dict(candidatos),
            "sin_candidatos": llm.como_lista(sin_candidatos)},
    }
    r = loop.correr("comprador", prompts.COMPRADOR, objetivo,
                    tools.tools_comprador(), ejecutores, traza)
    crudos = llm.como_dict((r.get("entrega") or {}).get("candidatos"))

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
    from config.categorias import CONCEPTO_A_CATEGORIA as MAPA
    for req in requerimientos:
        if candidatos.get(req.concepto):
            continue
        g = catalogo.gamas(req.concepto, MAPA.get(req.concepto), unidad_requerida=req.unidad)
        if g:
            candidatos[req.concepto] = g
            traza.paso("sistema", "relleno_deterministico", f"{req.concepto} por SQL")
    return candidatos
