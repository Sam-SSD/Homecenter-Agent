"""Verifica que la red permite consultar PDPs en vivo. Correr desde casa hoy y
OTRA VEZ manana 7:45 desde EAFIT: es otra IP y puede comportarse distinto."""
from __future__ import annotations
import re, sys, time
import requests
from ingest.fetch import SESSION, BASE

SKUS = ["3057289", "468303", "212968"]  # SKUs reales confirmados en cat90040
RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")


def main() -> int:
    ok = 0
    for sku in SKUS:
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
    print(f"\n{ok}/{len(SKUS)} en vivo.",
          "Validacion en vivo disponible." if ok >= 2 else
          "Corre en modo snapshot: MODO_OFFLINE=1")
    return 0 if ok >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
