"""Prueba del nucleo determinista: reglas -> catalogo -> negociador -> verificador.
Corre sin LLM y sin red. Es la base de evals/prove.py."""
from __future__ import annotations
from data.categorias import CONCEPTO_A_CATEGORIA as MAPA
from src import catalogo, negociador, reglas, verificador
from src.schemas import Espacio

REGLAS_BANO = ["sanitario", "lavamanos", "piso_ceramica", "enchape_pared", "adhesivo",
               "boquilla", "pintura_cielo", "griferia_lavamanos", "griferia_ducha",
               "mueble_bano", "espejo", "division_ducha"]


def requerimientos_de(espacio: Espacio):
    out = []
    for rid in REGLAS_BANO:
        try:
            out.append(reglas.calcular(rid, espacio))
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
