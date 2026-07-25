"""Parsea todo el cache. Cero red. Corre en segundos: aqui es donde se itera
cuando un selector esta mal."""
from __future__ import annotations
import json, pathlib
from bs4 import BeautifulSoup
from config.categorias import CAT_A_NOMBRE, SOLO_GUIA
from ingesta.fetch import CACHE, manifest
from ingesta.parse import parse_categoria, parse_guias, specs_de_next_data


def main() -> None:
    entradas = manifest()
    if not entradas:
        print("cache vacio. Corre primero: python -m ingesta.fetch_all --ambiente bano")
        return
    productos, guias, vistos, ids_guia = [], [], set(), set()
    # Un SKU repetido entre facetas puede traer highlights vacios en una pagina y
    # completos en otra: se acumula sobre todo el cache y se mezcla al final.
    specs_por_sku: dict[str, dict] = {}
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
            for sku, extra in specs_de_next_data(soup).items():
                previo = specs_por_sku.get(sku)
                if previo is None:
                    specs_por_sku[sku] = extra
                    continue
                for k, v in extra.items():
                    if not previo.get(k) and v:
                        previo[k] = v

        if "?" not in e["url"]:
            for g in parse_guias(soup, cat_id, nombre):
                clave = (g["titulo"], g["texto"][:80])
                if clave not in ids_guia:
                    ids_guia.add(clave)
                    g["id"] = f"guia:{cat_id}:{len(guias)}"
                    guias.append(g)

    enriquecidos = 0
    for p in productos:
        extra = specs_por_sku.get(p["sku"])
        if not extra:
            continue
        if extra["specs"]:
            p["specs"] = extra["specs"]
            enriquecidos += 1
        if not p.get("marca") and extra["marca"]:
            p["marca"] = extra["marca"]
        if extra["rating"] is not None:
            p["rating"] = extra["rating"]
        if extra["total_reviews"] is not None:
            p["total_reviews"] = extra["total_reviews"]
        if extra["modelo"]:
            p["modelo"] = extra["modelo"]

    pathlib.Path("datos").mkdir(exist_ok=True)
    json.dump(productos, open("datos/productos.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(guias, open("datos/guias.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(productos)} productos ({enriquecidos} con specs) - {len(guias)} chunks de guia")
    print("Ahora: python -m ingesta.build_index && python -m ingesta.sanity")


if __name__ == "__main__":
    main()
