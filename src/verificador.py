"""Guardrail de salida y motor de auto-correccion. Codigo puro: no audita un LLM
con otro LLM. Sus fallas se devuelven al loop COMO RESULTADO DE HERRAMIENTA,
para que el agente las lea y decida. Eso es 'look at the result, repeat'.
"""
from __future__ import annotations
from math import ceil
from src import catalogo
from src.schemas import Cotizacion, Falla, unidades_necesarias


def verificar(cot: Cotizacion) -> list[Falla]:
    fallas: list[Falla] = []
    conocidos = catalogo.skus_conocidos()

    for it in cot.items:
        c = it.concepto
        if it.producto.sku not in conocidos:
            fallas.append(Falla(codigo="sku_inexistente", concepto=c,
                                mensaje=f"el SKU {it.producto.sku} no existe en el catalogo"))
        real = catalogo.por_sku(it.producto.sku)
        if real and real.precio != it.producto.precio:
            fallas.append(Falla(codigo="precio_alterado", concepto=c,
                                mensaje=f"precio citado ${it.producto.precio:,} != catalogo ${real.precio:,}"))
        if it.subtotal_cop != it.producto.precio * it.unidades_a_comprar:
            fallas.append(Falla(codigo="aritmetica", concepto=c,
                                mensaje=f"subtotal {it.subtotal_cop} != {it.producto.precio} x {it.unidades_a_comprar}"))
        minimo = unidades_necesarias(it.requerimiento, it.producto)
        if it.unidades_a_comprar < minimo:
            fallas.append(Falla(codigo="cantidad_insuficiente", concepto=c,
                                mensaje=f"{it.unidades_a_comprar} unidades no cubren "
                                        f"{it.requerimiento.cantidad} {it.requerimiento.unidad} (min {minimo})"))
        if not it.requerimiento.fuente_regla:
            fallas.append(Falla(codigo="cifra_sin_fuente", concepto=c,
                                mensaje="la cantidad no declara fuente"))
        if it.producto.unidad_incierta:
            fallas.append(Falla(codigo="unidad_incierta", concepto=c,
                                mensaje=f"no se pudo inferir la unidad de venta de {it.producto.sku}"))

    if cot.total_cop != sum(i.subtotal_cop for i in cot.items):
        fallas.append(Falla(codigo="total_no_cuadra", mensaje="el total no es la suma de los subtotales"))
    if cot.total_cop > cot.espacio.presupuesto_cop:
        fallas.append(Falla(codigo="excede_presupuesto",
                            mensaje=f"total ${cot.total_cop:,} excede el tope "
                                    f"${cot.espacio.presupuesto_cop:,}"))

    esenciales = {"sanitario", "ceramica de piso", "pegante para ceramica"}
    presentes = {i.concepto for i in cot.items}
    for e in esenciales - presentes:
        fallas.append(Falla(codigo="falta_esencial", concepto=e,
                            mensaje=f"una remodelacion de bano no puede omitir: {e}"))
    return fallas


def a_texto(fallas: list[Falla]) -> str:
    if not fallas:
        return "APROBADA: sin fallas."
    return "RECHAZADA. Fallas:\n" + "\n".join(
        f"- [{f.codigo}] {f.concepto or 'general'}: {f.mensaje}" for f in fallas)
