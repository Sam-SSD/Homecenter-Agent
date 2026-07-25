"""Estado del pipeline de datos. Cero red: solo mira que hay en disco.

  python -m ingest.estado

Contesta: que falta por descargar, hay huerfanos en el cache, y con que datos
esta trabajando el agente ahora mismo.
"""
from __future__ import annotations
import json, pathlib, sqlite3, sys
from bs4 import BeautifulSoup

from data.categorias import AMBIENTE_A_CATEGORIAS, PRODUCTOS, SOLO_GUIA
from ingest.fetch import CACHE, MANIFEST, clave, manifest, url_categoria
from ingest.parse import descubrir_facetas, leer_html


def _cacheada(url: str) -> bool:
    return (CACHE / f"{clave(url)}.html").exists()


def main() -> int:
    print("=" * 70)
    print("1. CACHE  (HTML crudo, reanudable, nunca se borra solo)")
    print("=" * 70)
    htmls = sorted(CACHE.glob("*.html")) if CACHE.exists() else []
    tmps = sorted(CACHE.glob("*.tmp")) if CACHE.exists() else []
    entradas = manifest()
    hashes_manifest = {e["hash"] for e in entradas}
    huerfanos = [h for h in htmls if h.stem not in hashes_manifest]
    peso = sum(h.stat().st_size for h in htmls) / 1_048_576
    print(f"  cache/html:           {len(htmls):>4} paginas  ({peso:.1f} MB)")
    print(f"  cache/manifest.jsonl: {len(entradas):>4} entradas")
    print(f"  huerfanos (html sin entrada): {len(huerfanos)}"
          + ("  -> se re-registran solos al volver a correr fetch_all" if huerfanos else ""))
    if tmps:
        print(f"  descargas truncadas (.tmp): {len(tmps)}  -> se pueden borrar")

    print()
    print("=" * 70)
    print("2. PENDIENTE POR DESCARGAR  (por categoria)")
    print("=" * 70)
    pendientes = 0
    for etiqueta, cats, con_facetas in (("productos", PRODUCTOS, True),
                                        ("guias", SOLO_GUIA, False)):
        for cat_id, (nombre, slug) in cats.items():
            base = url_categoria(cat_id, slug)
            if not _cacheada(base):
                print(f"  [ ] {nombre:22} {etiqueta:6} base sin descargar")
                pendientes += 1
                continue
            if not con_facetas:
                print(f"  [x] {nombre:22} {etiqueta:6} base ok (solo guias)")
                continue
            soup = BeautifulSoup(leer_html(str(CACHE / f"{clave(base)}.html")), "lxml")
            facetas = descubrir_facetas(soup, cat_id)
            faltan = [f for f in facetas if not _cacheada(f)]
            pendientes += len(faltan)
            marca = "x" if not faltan else " "
            print(f"  [{marca}] {nombre:22} {etiqueta:6} "
                  f"{len(facetas) - len(faltan)}/{len(facetas)} facetas")
    print(f"\n  URLs pendientes: {pendientes}"
          + ("  -> corre: python -m ingest.fetch_all --ambiente <bano|cocina|habitacion|sala|todos>"
             if pendientes else "  -> nada que bajar"))
    print(f"\n  ambientes configurados: {', '.join(AMBIENTE_A_CATEGORIAS.keys())}")

    print()
    print("=" * 70)
    print("3. DATOS DERIVADOS  (se regeneran del cache, es seguro reconstruirlos)")
    print("=" * 70)
    for ruta, desc, comando in (
            ("data/productos.json", "productos parseados", "python -m ingest.parse_all"),
            ("data/guias.json", "corpus RAG", "python -m ingest.parse_all")):
        p = pathlib.Path(ruta)
        if p.exists():
            try:
                n = len(json.load(open(p, encoding="utf-8")))
            except Exception:
                n = "?"
            print(f"  {ruta:24} {n:>6} registros   ({desc})")
        else:
            print(f"  {ruta:24}  FALTA  -> {comando}")

    print()
    print("=" * 70)
    print("4. LO QUE EL AGENTE ESTA LEYENDO AHORA")
    print("=" * 70)
    db = pathlib.Path("data/catalogo.db")
    if not db.exists():
        print("  data/catalogo.db FALTA -> python -m ingest.build_index")
        return 1
    con = sqlite3.connect(db)
    n_p = con.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    n_g = con.execute("SELECT COUNT(*) FROM guias").fetchone()[0]
    cats = con.execute("SELECT COUNT(DISTINCT categoria) FROM productos").fetchone()[0]
    fecha = con.execute("SELECT MAX(capturado_en) FROM productos").fetchone()[0]
    fixture = con.execute("SELECT COUNT(*) FROM productos WHERE cat_id='catFIXTURE'").fetchone()[0]
    con.close()
    print(f"  data/catalogo.db: {n_p} productos en {cats} categorias, {n_g} chunks de guia")
    print(f"  snapshot: {fecha}")
    if fixture:
        print(f"  OJO: {fixture} de esos productos son del FIXTURE sintetico.")
        print("       Corre: python -m ingest.build_index   (sin --fuente)")
    if n_g == 0:
        print("  OJO: 0 chunks de guia -> consultar_guia no tiene fuente y NO se")
        print("       alcanza el nivel 4 de la rubrica. Revisa data/guias.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
