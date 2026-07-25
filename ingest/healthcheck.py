"""Verifica que la red permite consultar PDPs en vivo. Correr desde casa hoy y
OTRA VEZ manana 7:45 desde EAFIT: es otra IP y puede comportarse distinto.

  python -m ingest.healthcheck            # bano (default, SKUs confirmados)
  python -m ingest.healthcheck cocina     # requiere SKUS_POR_AMBIENTE poblado
"""
from __future__ import annotations
import re, sys, time
import requests
from ingest.fetch import SESSION, BASE

# SKUs reales confirmados por ambiente. Poblar cocina/habitacion/sala una vez
# hecho el primer fetch_all --ambiente de cada uno (tomar 3 de data/productos.json
# resultante). Vacio => ese ambiente no se puede healthcheckear todavia.
SKUS_POR_AMBIENTE = {
    "bano": ["3057289", "468303", "212968"],
    "cocina": [],
    "habitacion": [],
    "sala": [],
}
RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")


def main(ambiente: str = "bano") -> int:
    skus = SKUS_POR_AMBIENTE.get(ambiente) or []
    if not skus:
        print(f"sin SKUs confirmados para '{ambiente}' todavia. "
              "Corre fetch_all + parse_all para ese ambiente y puebla SKUS_POR_AMBIENTE.")
        return 1
    ok = 0
    for sku in skus:
        url = f"{BASE}/homecenter-co/product/{sku}/x/{sku}/"
        t0 = time.time()
        try:
            r = SESSION.get(url, timeout=6)
            precio = RE_PRECIO.search(r.text)
            estado = "OK" if precio else "NO PARSEA PRECIO"
            if r.status_code == 200 and precio:
                ok += 1
            print(f"  {sku}  http={r.status_code}  {time.time()-t0:4.1f}s  {estado}"
                  f"  {'$' + precio.group(1) if precio else ''}")
        except Exception as e:
            print(f"  {sku}  FALLO  {type(e).__name__}: {e}")
        time.sleep(1.5)
    print(f"\n{ok}/{len(skus)} en vivo.",
          "Validacion en vivo disponible." if ok >= 2 else
          "Corre en modo snapshot: MODO_OFFLINE=1")
    return 0 if ok >= 2 else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0] if a else "bano"))
