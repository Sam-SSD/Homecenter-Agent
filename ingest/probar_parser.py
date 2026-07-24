"""Prueba el parser contra un HTML guardado. Cero red: aqui se itera cuando un
selector esta mal.

  python -m ingest.probar_parser ingest/muestra_cat90040.html cat90040 sanitarios

Hallazgo del 24-jul-2026: la pagina de categoria trae ~27 de los 40 productos en
el HTML del servidor; el resto se hidrata con JavaScript. Por eso el scraper NO
pagina: recorre las facetas permitidas en robots.txt y deduplica por SKU global.
"""
from __future__ import annotations
import sys
from bs4 import BeautifulSoup
from ingest.parse import leer_html, parse_categoria, parse_guias


def main(ruta: str, cat_id: str = "cat90040", categoria: str = "sanitarios") -> int:
    soup = BeautifulSoup(leer_html(ruta), "lxml")
    ps = parse_categoria(soup, cat_id, categoria)
    gs = parse_guias(soup, cat_id, categoria)
    print(f"productos: {len(ps)} | guias: {len(gs)}")
    for x in ps[:8]:
        print(f"  {x['sku']:>8} ${x['precio']:>9,} {x['unidad']:6} {x['marca'][:14]:14} {x['nombre'][:44]}")
    raros = [x for x in ps if x["precio"] < 20_000 or x["precio"] > 20_000_000]
    inciertas = [x for x in ps if x.get("unidad_incierta")]
    print(f"precios sospechosos: {len(raros)} | unidad incierta: {len(inciertas)}"
          f" | sin marca: {sum(1 for x in ps if not x['marca'])}")
    for g in gs[:3]:
        print(f"  guia: {g['titulo'][:64]} ({len(g['texto'])} chars)")
    return 0 if ps else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0] if a else "ingest/muestra_cat90040.html", *a[1:]))
