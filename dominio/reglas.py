"""Motor de reglas de obra. El LLM NUNCA hace aritmetica: pide la regla y llama
calcular_cantidad(); el calculo lo hace Python y queda auditable."""
from __future__ import annotations
import math, pathlib
import yaml
from dominio.schemas import Espacio, Requerimiento

RUTA = pathlib.Path("config/reglas_obra.yaml")
_SEGURO = {"min": min, "max": max, "ceil": math.ceil, "floor": math.floor,
           "round": round, "abs": abs}


def cargar() -> dict:
    return yaml.safe_load(RUTA.read_text(encoding="utf-8"))


def _aplica(regla: dict, tipo: str | None) -> bool:
    """Sin `ambientes` en la regla, se asume que aplica a todos (compatibilidad
    hacia atras). Con el, solo aplica si tipo esta en la lista."""
    ambientes = regla.get("ambientes")
    if not ambientes or tipo is None:
        return True
    return tipo in ambientes


def obtener(regla_id: str, tipo: str | None = None) -> dict | None:
    r = cargar().get(regla_id)
    if not r:
        return None
    if not _aplica(r, tipo):
        return None
    r = dict(r)
    r["id"] = regla_id
    return r


def listar(tipo: str | None = None) -> list[dict]:
    """Sin `tipo`, lista todo (uso administrativo). El Cuantificador SIEMPRE
    llama con el tipo del Espacio: sin este filtro, el Cuantificador de bano
    veria (y podria cotizar) reglas de cocina en cuanto existieran."""
    return [{"id": k, "concepto": v["concepto"], "unidad": v["unidad"],
             "prioridad": v.get("prioridad", 1), "verificada": v.get("verificada", False)}
            for k, v in cargar().items() if _aplica(v, tipo)]


def calcular(regla_id: str, espacio: Espacio) -> Requerimiento:
    r = obtener(regla_id, espacio.tipo)
    if not r:
        raise KeyError(f"regla desconocida o no aplicable a {espacio.tipo}: {regla_id}")
    variables = espacio.variables() | dict(r.get("coeficientes") or {})
    formula = r["formula"]
    try:
        cantidad = float(eval(formula, {"__builtins__": {}}, {**_SEGURO, **variables}))
    except NameError as e:
        # La formula referencia una variable que este Espacio no expone (p.ej.
        # altura_enchape_m en un tipo que no enchapa). Es el mismo caso que
        # cantidad<=0: la regla no aplica a este espacio, no un error de sistema.
        raise ValueError(f"{regla_id} no aplica a este espacio: falta {e}") from e
    cantidad = round(cantidad, 2)
    if cantidad <= 0:
        raise ValueError(f"{regla_id} no aplica a este espacio (cantidad {cantidad})")
    sustituida = formula
    for k, v in sorted(variables.items(), key=lambda kv: -len(kv[0])):
        sustituida = sustituida.replace(k, str(v))
    return Requerimiento(
        concepto=r["concepto"],
        cantidad=cantidad,
        unidad=r["unidad"],
        formula=f"{formula} = {sustituida} = {cantidad} {r['unidad']}",
        fuente_regla=r.get("fuente", ""),
        regla_verificada=bool(r.get("verificada", False)),
        prioridad=int(r.get("prioridad", 1)),
        regla_id=regla_id,
    )
