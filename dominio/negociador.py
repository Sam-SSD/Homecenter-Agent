"""Optimizacion bajo restriccion. NO es un LLM y es a proposito: ajustar N items
a un tope es optimizacion, y un LLM complace al usuario y alucina totales.
El LLM decide QUE recortar proponiendo gamas; la aritmetica la hace esto.
"""
from __future__ import annotations
import re
from dominio import reglas
from dominio.schemas import (Cotizacion, Espacio, ItemCotizado, Producto,
                             Requerimiento, unidades_necesarias)

FASES_NOMBRE = {
    "obra_gris": "Semana 1 - demolicion y obra gris",
    "enchape": "Semana 2 - enchape",
    "acabados": "Semana 3 - acabados",
}

ORDEN_GAMA = ["premium", "media", "economico"]


def _item(req: Requerimiento, prod: Producto, gama: str) -> ItemCotizado:
    n = unidades_necesarias(req, prod)
    return ItemCotizado(
        concepto=req.concepto, requerimiento=req, producto=prod,
        unidades_a_comprar=n, subtotal_cop=n * prod.precio, gama=gama,
        justificacion=f"{n} x {prod.unidad} de {prod.nombre[:60]}",
    )


def _subtotal(candidatos, concepto, req, gama) -> int:
    return _item(req, candidatos[concepto][gama], gama).subtotal_cop


def _mejor_downgrade(seleccion, candidatos, solo_prioridad=None):
    """Un paso de gama hacia abajo, el que mas ahorra. None si no hay."""
    mejor = None
    for concepto, (req, gama) in seleccion.items():
        if solo_prioridad and req.prioridad not in solo_prioridad:
            continue
        i = ORDEN_GAMA.index(gama)
        if i + 1 >= len(ORDEN_GAMA):
            continue
        siguiente = ORDEN_GAMA[i + 1]
        prod = candidatos[concepto].get(siguiente)
        if not prod:
            continue
        ahorro = _subtotal(candidatos, concepto, req, gama) - _item(req, prod, siguiente).subtotal_cop
        if ahorro > 0 and (mejor is None or ahorro > mejor[0]):
            mejor = (ahorro, concepto, siguiente, prod)
    return mejor


def _mayor_opcional(seleccion, candidatos, prioridades):
    cands = [(_subtotal(candidatos, c, r, g), c) for c, (r, g) in seleccion.items()
             if r.prioridad in prioridades]
    return max(cands) if cands else None


def armar(espacio: Espacio,
          requerimientos: list[Requerimiento],
          candidatos: dict[str, dict[str, Producto]],
          tope: int | None = None) -> Cotizacion:
    """Estrategia, en este orden y es explicable en una frase: primero cede en la
    gama de los opcionales, luego los saca, y solo entonces toca lo esencial."""
    tope = tope or espacio.presupuesto_cop
    cot = Cotizacion(espacio=espacio)

    seleccion: dict[str, tuple[Requerimiento, str]] = {}
    for req in requerimientos:
        opciones = candidatos.get(req.concepto) or {}
        if not opciones:
            cot.faltantes.append(req.concepto)
            continue
        gama = "media" if "media" in opciones else next(iter(opciones))
        seleccion[req.concepto] = (req, gama)

    def total() -> int:
        return sum(_subtotal(candidatos, c, r, g) for c, (r, g) in seleccion.items())

    fases_recorte = [
        ("downgrade", {3}),      # 1. baja gama de opcionales
        ("sacar", {3}),          # 2. saca opcionales
        ("downgrade", {1, 2}),   # 3. baja gama de lo importante y lo esencial
        ("sacar", {2}),          # 4. ultimo recurso: saca importantes
    ]

    for accion, prioridades in fases_recorte:
        guardas = 0
        while total() > tope and guardas < 40:
            guardas += 1
            if accion == "downgrade":
                m = _mejor_downgrade(seleccion, candidatos, prioridades)
                if not m:
                    break
                ahorro, concepto, gama_nueva, prod = m
                req, _ = seleccion[concepto]
                seleccion[concepto] = (req, gama_nueva)
                cot.recortes.append(
                    f"{concepto}: baje a {prod.nombre[:52]} y libere ${ahorro:,}")
            else:
                m = _mayor_opcional(seleccion, candidatos, prioridades)
                if not m:
                    break
                monto, concepto = m
                seleccion.pop(concepto)
                etiqueta = "opcional" if prioridades == {3} else "no esencial"
                cot.recortes.append(
                    f"saque {concepto} ({etiqueta}) y libere ${monto:,}")
        if total() <= tope:
            break

    cot.items = [_item(r, candidatos[c][g], g) for c, (r, g) in seleccion.items()]
    cot.items.sort(key=lambda i: (i.requerimiento.prioridad, -i.subtotal_cop))
    cot.recalcular()

    if cot.total_cop > tope:
        cot.recortes.append(
            f"NO ALCANZA: ni con todos los recortes baja de ${tope:,}. "
            f"Minimo viable ${cot.total_cop:,} (faltan ${cot.total_cop - tope:,})")

    for concepto, (req, gama) in list(seleccion.items()):
        i = ORDEN_GAMA.index(gama)
        if i == 0:
            continue
        arriba = ORDEN_GAMA[i - 1]
        prod = candidatos[concepto].get(arriba)
        if not prod:
            continue
        delta = _item(req, prod, arriba).subtotal_cop - _subtotal(candidatos, concepto, req, gama)
        if 0 < delta <= cot.holgura_cop:
            cot.alternativas.append(
                f"con ${cot.holgura_cop:,} de holgura podrias subir {concepto} "
                f"a {prod.nombre[:48]} (+${delta:,})")

    cot.alternativas.sort(key=lambda s: -int(re.search(r"\+\$([\d,]+)", s).group(1).replace(",", "")))
    cot.fases = _fases(cot)
    return cot


def _fases(cot: Cotizacion) -> dict[str, list[str]]:
    """Agrupa por el campo `fase` de la regla en config/reglas_obra.yaml, no por
    keywords en el nombre del concepto: eso hacia que todo concepto de un
    ambiente nuevo (sin 'pegante'/'boquilla'/'ceramica' en el nombre) cayera
    siempre en 'acabados', y se extiende gratis a ambientes nuevos.

    Carga el YAML UNA vez (no por item): reglas.obtener() dentro del loop haria
    un read_text + yaml.safe_load por cada item de la cotizacion."""
    todas = reglas.cargar()
    f: dict[str, list[str]] = {v: [] for v in FASES_NOMBRE.values()}
    for i in cot.items:
        regla = todas.get(i.requerimiento.regla_id) or {}
        clave_fase = regla.get("fase", "acabados")
        nombre_fase = FASES_NOMBRE.get(clave_fase, FASES_NOMBRE["acabados"])
        f[nombre_fase].append(i.concepto)
    return {k: v for k, v in f.items() if v}
