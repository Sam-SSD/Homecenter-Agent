"""Semilla committeada: 2 productos por categoria. data/muestra.json SI va al
repo (los evals corren en cualquier maquina). data/productos.json NO va al repo."""
from __future__ import annotations
import json, pathlib

def main() -> None:
    ruta = pathlib.Path("data/productos.json")
    if not ruta.exists():
        print("no existe data/productos.json")
        return
    ps = json.load(open(ruta, encoding="utf-8"))
    por_cat: dict[str, list] = {}
    for p in ps:
        por_cat.setdefault(p["categoria"], []).append(p)
    semilla = []
    for v in por_cat.values():
        v = sorted(v, key=lambda x: x.get("precio") or 0)
        semilla.append(v[len(v) // 2])
        if len(v) > 1:
            semilla.append(v[0])
    json.dump(semilla, open("data/muestra.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"data/muestra.json: {len(semilla)} productos de {len(por_cat)} categorias")

if __name__ == "__main__":
    main()
