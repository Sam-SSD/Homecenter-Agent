"""Prueba del nucleo determinista: reglas -> catalogo -> negociador -> verificador.
Corre sin LLM y sin red. Es la base de evals/prove.py.

La lista de reglas para el modo deterministico se deriva de reglas.listar(tipo),
la misma fuente que usa el camino agentico (via listar_reglas). Antes existia
una lista fija REGLAS_BANO con los 12 ids de bano: eso hacia que agregar una
regla al YAML cambiara el camino agentico pero no este, dejando la red de
seguridad de la demo ciega a todo lo nuevo. Derivarla del YAML cierra esa
asimetria."""
from __future__ import annotations
from data.categorias import CONCEPTO_A_CATEGORIA as MAPA
from src import catalogo, negociador, reglas, verificador
from src.schemas import Espacio


def requerimientos_de(espacio: Espacio):
    out = []
    for r in reglas.listar(espacio.tipo):
        try:
            out.append(reglas.calcular(r["id"], espacio))
        except ValueError:
            pass
    return out


def candidatos_de(reqs):
    c = {}
    for r in reqs:
        g = catalogo.gamas(r.concepto, MAPA.get(r.concepto), unidad_requerida=r.unidad)
        if g:
            c[r.concepto] = g
    return c


def cotizar(espacio: Espacio):
    reqs = requerimientos_de(espacio)
    cands = candidatos_de(reqs)
    cot = negociador.armar(espacio, reqs, cands)
    return cot, verificador.verificar(cot), reqs, cands
