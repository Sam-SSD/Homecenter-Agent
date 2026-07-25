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


def fijar_en_candidatos(candidatos: dict[str, dict[str, Producto]],
                        swaps: dict[str, str] | None) -> list[str]:
    """Colapsa las 3 gamas de un concepto al producto que el usuario fijo a
    mano. Con las 3 gamas iguales, _mejor_downgrade nunca encuentra ahorro
    positivo para ese concepto (queda protegido de la escalera de recortes)
    y el bucle de upgrades nunca le ofrece "subir de gama" porque ya esta en
    todas. _mayor_opcional SI puede sacarlo (ver sustituir() y armar()): un
    pin es una preferencia, no una garantia de que quepa en el presupuesto.

    Recibe `candidatos` y lo muta in-place antes de llamar a armar(). Nunca
    inyecta un Producto que la UI construyo: siempre re-consulta el catalogo
    por SKU, para que un swap viejo con precio desactualizado no cause
    precio_alterado en el verificador.

    Devuelve los conceptos huerfanos: el swap ya no aplica (cambio de
    ambiente/tamaño, o el SKU salio del catalogo)."""
    from dominio import catalogo
    huerfanos = []
    for concepto, sku in (swaps or {}).items():
        prod = catalogo.por_sku(sku)
        if concepto not in candidatos or not prod:
            huerfanos.append(concepto)
            continue
        candidatos[concepto] = {g: prod for g in ORDEN_GAMA}
    return huerfanos


def sustituir(cot: Cotizacion, concepto: str, sku: str) -> tuple[bool, str]:
    """Cambio manual de producto disparado por la UI. Determinista: el LLM
    nunca llama esto (regla 2 y 4 de CLAUDE.md, ver agentes/subagentes.py).

    Reconstruye el ItemCotizado con _item(), que recalcula unidades_a_comprar
    via unidades_necesarias() y fija subtotal = unidades * precio: por eso
    'aritmetica' y 'cantidad_insuficiente' no pueden dispararse en el
    verificador para un swap valido. Re-consulta el catalogo por SKU en vez
    de confiar en el Producto que trae la UI, por la misma razon que
    fijar_en_candidatos."""
    from dominio import catalogo
    idx = next((k for k, i in enumerate(cot.items) if i.concepto == concepto), None)
    if idx is None:
        return False, f"{concepto} ya no esta en la cotizacion"
    prod = catalogo.por_sku(str(sku))
    if not prod:
        return False, f"el SKU {sku} no existe en el catalogo"
    it = cot.items[idx]
    nuevo = _item(it.requerimiento, prod, _gama_estimada(it.concepto, it.requerimiento, prod, it.gama))
    nuevo.fijado_por_usuario = True
    cot.items[idx] = nuevo
    cot.aprobada_por_humano = False  # la canasta cambio despues de aprobar
    cot.recalcular()
    return True, f"{concepto}: {prod.nombre[:50]} — ${nuevo.subtotal_cop:,}"


def _gama_estimada(concepto: str, req: Requerimiento, prod: Producto, gama_previa: str) -> str:
    """Etiqueta de display para un producto elegido a mano: la gama de las 3
    (economico/media/premium) mas cercana en precio. Nunca un cuarto valor:
    ORDEN_GAMA.index(gama) en armar() revienta con algo fuera de las 3."""
    from dominio import catalogo
    from config.categorias import CONCEPTO_A_CATEGORIA
    disponibles = catalogo.gamas(concepto, CONCEPTO_A_CATEGORIA.get(concepto),
                                 unidad_requerida=req.unidad)
    if not disponibles:
        return gama_previa
    return min(disponibles, key=lambda g: abs(disponibles[g].precio - prod.precio))


def armar(espacio: Espacio,
          requerimientos: list[Requerimiento],
          candidatos: dict[str, dict[str, Producto]],
          tope: int | None = None,
          fijados: set[str] | None = None) -> Cotizacion:
    """Estrategia, en este orden y es explicable en una frase: primero cede en la
    gama de los opcionales, luego los saca, y solo entonces toca lo esencial.

    `fijados`: conceptos que el usuario fijo a mano (via fijar_en_candidatos).
    Ya vienen protegidos de _mejor_downgrade porque sus 3 gamas son el mismo
    producto (ahorro=0 siempre), pero _mayor_opcional SI puede sacarlos -- un
    pin es una preferencia, no una garantia de que quepa. Si eso pasa, el
    recorte lo dice explicitamente en vez de borrar la eleccion en silencio."""
    tope = tope or espacio.presupuesto_cop
    fijados = fijados or set()
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
                if concepto in fijados:
                    etiqueta += ", ERA TU ELECCION"
                cot.recortes.append(
                    f"saque {concepto} ({etiqueta}) y libere ${monto:,}")
        if total() <= tope:
            break

    cot.items = [_item(r, candidatos[c][g], g) for c, (r, g) in seleccion.items()]
    cot.items.sort(key=lambda i: (i.requerimiento.prioridad, -i.subtotal_cop))
    cot.recalcular()

    if cot.total_cop > tope:
        cot.minimo_viable_cop = cot.total_cop
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
