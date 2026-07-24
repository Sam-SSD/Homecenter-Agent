"""Etapa de descarga. Lanzalo y hace otra cosa mientras corre.

  python -m ingest.fetch_all --etapa 1     # 3 categorias, desbloquea al equipo
  python -m ingest.fetch_all --etapa 2     # nucleo completo + guias
  python -m ingest.fetch_all --etapa 2 --force   # refresca precios (manana 7:30)
"""
from __future__ import annotations
import argparse, sys
from bs4 import BeautifulSoup
from data.categorias import NUCLEO, EXTRA, SOLO_GUIA
from ingest.fetch import fetch, url_categoria
from ingest.parse import descubrir_facetas

ETAPA_1 = ["cat90040", "cat90041", "cat5070016"]


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--force", action="store_true", help="reignora el cache")
    a = ap.parse_args()

    if a.etapa == 1:
        cats = {k: v for k, v in NUCLEO.items() if k in ETAPA_1}
        n = descargar(cats, con_facetas=True, force=a.force)
    elif a.etapa == 2:
        n = descargar(NUCLEO, con_facetas=True, force=a.force)
        n += descargar(SOLO_GUIA, con_facetas=False, force=a.force)
    else:
        n = descargar(EXTRA, con_facetas=True, force=a.force)

    print(f"\n{n} paginas en cache. Ahora: python -m ingest.parse_all")


if __name__ == "__main__":
    sys.exit(main())
