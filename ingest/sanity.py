"""QA del snapshot. No confies en el conteo: corre esto antes de dar los datos
por buenos, y abre a mano los 3 links que imprime al final."""
from __future__ import annotations
import json, pathlib, statistics as st, sys


def main(ruta: str = "data/productos.json") -> int:
    p = pathlib.Path(ruta)
    if not p.exists():
        print(f"no existe {ruta}")
        return 1
    ps = json.load(open(p, encoding="utf-8"))
    if not ps:
        print("archivo vacio")
        return 1

    print(f"total {len(ps)} - SKUs unicos {len({x['sku'] for x in ps})}\n")
    cats = sorted({x["categoria"] for x in ps})
    for cat in cats:
        sub = [x for x in ps if x["categoria"] == cat]
        pr = [x["precio"] for x in sub if x.get("precio")]
        if not pr:
            print(f"  {cat:22} n={len(sub):4}  SIN PRECIOS")
            continue
        print(f"  {cat:22} n={len(sub):4}  min=${min(pr):>10,}  "
              f"med=${int(st.median(pr)):>10,}  max=${max(pr):>10,}")

    raros = [x for x in ps if not x.get("precio") or x["precio"] < 1000 or x["precio"] > 20_000_000]
    print(f"\nprecios sospechosos: {len(raros)}")
    for x in raros[:5]:
        print(f"   {x.get('precio')} {x['nombre'][:58]}")

    inciertas = [x for x in ps if x.get("unidad_incierta")]
    pct = 100 * len(inciertas) // len(ps)
    print(f"unidad incierta: {len(inciertas)} ({pct}%)"
          f"{'  <-- revisar los PDP de estos' if pct > 30 else ''}")

    faltan = [c for c in ("pisos_bano", "paredes_ceramicas", "sanitarios", "lavamanos",
                          "griferia_lavamanos", "adhesivo_ceramica", "pintura_antihongos")
              if c not in cats]
    if faltan:
        print(f"\nOJO faltan categorias clave: {faltan}")

    print("\nabre estos 3 a mano y compara el precio:")
    paso = max(len(ps) // 3, 1)
    for x in ps[::paso][:3]:
        print(f"   ${x['precio']:,}  {x['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
