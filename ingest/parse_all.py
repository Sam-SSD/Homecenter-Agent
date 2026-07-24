"""Parsea todo el cache. Cero red. Corre en segundos: aqui es donde se itera
cuando un selector esta mal."""
from __future__ import annotations
import json, pathlib
from bs4 import BeautifulSoup
from data.categorias import CAT_A_NOMBRE, SOLO_GUIA
from ingest.fetch import CACHE, manifest
from ingest.parse import parse_categoria, parse_guias


def main() -> None:
    entradas = manifest()
    if not entradas:
        print("cache vacio. Corre primero: python -m ingest.fetch_all --etapa 1")
        return
    productos, guias, vistos, ids_guia = [], [], set(), set()
    for e in entradas:
        archivo = CACHE / f"{e['hash']}.html"
        if not archivo.exists():
            continue
        cat_id = e.get("cat_id") or ""
        nombre = CAT_A_NOMBRE.get(cat_id, "otros")
        soup = BeautifulSoup(archivo.read_text(encoding="utf-8"), "lxml")

        if cat_id not in SOLO_GUIA:
            for p in parse_categoria(soup, cat_id, nombre):
                if p["sku"] not in vistos:
                    vistos.add(p["sku"])
                    productos.append(p)

        if "?" not in e["url"]:
            for g in parse_guias(soup, cat_id, nombre):
                clave = (g["titulo"], g["texto"][:80])
                if clave not in ids_guia:
                    ids_guia.add(clave)
                    g["id"] = f"guia:{cat_id}:{len(guias)}"
                    guias.append(g)

    pathlib.Path("data").mkdir(exist_ok=True)
    json.dump(productos, open("data/productos.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(guias, open("data/guias.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(productos)} productos - {len(guias)} chunks de guia")
    print("Ahora: python -m ingest.build_index && python -m ingest.sanity")


if __name__ == "__main__":
    main()
