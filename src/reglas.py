"""Motor de reglas de obra. El LLM NUNCA hace aritmetica: pide la regla y llama
calcular_cantidad(); el calculo lo hace Python y queda auditable."""
from __future__ import annotations
import math, pathlib
import yaml
from src.schemas import Espacio, Requerimiento

RUTA = pathlib.Path("data/reglas_obra.yaml")
_SEGURO = {"min": min, "max": max, "ceil": math.ceil, "floor": math.floor,
           "round": round, "abs": abs}


def cargar() -> dict:
    return yaml.safe_load(RUTA.read_text(encoding="utf-8"))


def obtener(regla_id: str) -> dict | None:
    r = cargar().get(regla_id)
    if r:
        r = dict(r)
        r["id"] = regla_id
    return r


def listar() -> list[dict]:
    return [{"id": k, "concepto": v["concepto"], "unidad": v["unidad"],
             "prioridad": v.get("prioridad", 1), "verificada": v.get("verificada", False)}
            for k, v in cargar().items()]


def calcular(regla_id: str, espacio: Espacio) -> Requerimiento:
    r = obtener(regla_id)
    if not r:
        raise KeyError(f"regla desconocida: {regla_id}")
    variables = espacio.variables() | dict(r.get("coeficientes") or {})
    formula = r["formula"]
    cantidad = float(eval(formula, {"__builtins__": {}}, {**_SEGURO, **variables}))
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
