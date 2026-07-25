"""Etapa de descarga, por ambiente. Lanzalo y hace otra cosa mientras corre.

  python -m ingest.fetch_all --ambiente bano
  python -m ingest.fetch_all --ambiente cocina
  python -m ingest.fetch_all --ambiente todos
  python -m ingest.fetch_all --ambiente cocina --force   # refresca precios
  python -m ingest.fetch_all --ambiente cocina --estimar # solo cuenta, cero red

DELAY minimo 1.8s por request (ver ingest/fetch.py). Con --estimar se imprime
cuantas categorias y facetas tocaria bajar, y el tiempo aproximado, SIN tocar
la red: util para presupuestar la noche antes de lanzar de verdad.
"""
from __future__ import annotations
import argparse, sys
from bs4 import BeautifulSoup
from data.categorias import (AMBIENTE_A_CATEGORIAS, categorias_de_ambiente,
                              guias_de_ambiente)
from ingest.fetch import DELAY, fetch, url_categoria
from ingest.parse import descubrir_facetas

AMBIENTES = list(AMBIENTE_A_CATEGORIAS.keys()) + ["todos"]


def _categorias_producto(ambiente: str) -> dict:
    if ambiente == "todos":
        cats: dict = {}
        for amb in AMBIENTE_A_CATEGORIAS:
            cats.update(categorias_de_ambiente(amb))
        return cats
    return categorias_de_ambiente(ambiente)


def _categorias_guia(ambiente: str) -> dict:
    if ambiente == "todos":
        cats: dict = {}
        for amb in AMBIENTE_A_CATEGORIAS:
            cats.update(guias_de_ambiente(amb))
        return cats
    return guias_de_ambiente(ambiente)


def descargar(cats: dict, con_facetas: bool, force: bool) -> int:
    n = 0
    for cat_id, (nombre, slug) in cats.items():
        url = url_categoria(cat_id, slug)
        print(f"-> {nombre} ({cat_id})")
        html = fetch(url, force=force)
        if not html:
            continue
        n += 1
        if not con_facetas:
            continue
        soup = BeautifulSoup(html, "lxml")
        facetas = descubrir_facetas(soup, cat_id)
        print(f"   {len(facetas)} facetas")
        for f in facetas:
            if fetch(f, force=force):
                n += 1
    return n


def estimar(ambiente: str) -> None:
    """Cuenta categorias sin tocar la red. Las facetas de paginas no cacheadas
    no se pueden contar sin descargar, asi que se estima con un techo de 8
    (el limite de descubrir_facetas) por categoria de producto."""
    productos = _categorias_producto(ambiente)
    guias = _categorias_guia(ambiente)
    max_facetas_por_cat = 8
    techo_requests = len(productos) * (1 + max_facetas_por_cat) + len(guias)
    print(f"ambiente: {ambiente}")
    print(f"  categorias de producto: {len(productos)}")
    print(f"  categorias solo-guia:   {len(guias)}")
    print(f"  techo de requests (peor caso, 8 facetas c/u): {techo_requests}")
    print(f"  tiempo aprox. (DELAY={DELAY}s):                "
          f"{techo_requests * DELAY / 60:.1f} min")
    print("  nota: las paginas ya en cache/ no generan request nuevo, asi que")
    print("  el tiempo real suele ser menor si se corre en varias tandas.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ambiente", default="bano", choices=AMBIENTES)
    ap.add_argument("--force", action="store_true", help="reignora el cache")
    ap.add_argument("--estimar", action="store_true",
                    help="solo cuenta categorias/requests, cero red")
    a = ap.parse_args()

    if a.estimar:
        estimar(a.ambiente)
        return

    n = descargar(_categorias_producto(a.ambiente), con_facetas=True, force=a.force)
    n += descargar(_categorias_guia(a.ambiente), con_facetas=False, force=a.force)

    print(f"\n{n} paginas en cache. Ahora: python -m ingest.parse_all")


if __name__ == "__main__":
    sys.exit(main())
