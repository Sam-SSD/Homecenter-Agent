"""Indice SQLite + FTS5. Tabla FTS autonoma (sin content=) para no depender de
triggers ni de 'rebuild': mas simple y mas dificil de romper a las 11 AM.

Acepta --fuente para construir desde la muestra committeada o desde un fixture.
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3

DB = "datos/catalogo.db"

ESQUEMA = """
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS productos_fts;
DROP TABLE IF EXISTS guias;
DROP TABLE IF EXISTS guias_fts;

CREATE TABLE productos (
  sku TEXT PRIMARY KEY, nombre TEXT, marca TEXT, categoria TEXT, cat_id TEXT,
  precio INTEGER, precio_antes INTEGER, unidad TEXT,
  m2_por_caja REAL, kg_por_bulto REAL, rendimiento_m2 REAL,
  unidad_incierta INTEGER DEFAULT 0,
  url TEXT, imagen_url TEXT, capturado_en TEXT
);
CREATE INDEX idx_prod_cat ON productos(categoria);
CREATE INDEX idx_prod_precio ON productos(precio);

CREATE VIRTUAL TABLE productos_fts USING fts5(
  sku UNINDEXED, nombre, marca, categoria,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE guias (
  id TEXT PRIMARY KEY, categoria TEXT, titulo TEXT, texto TEXT, url TEXT
);
CREATE VIRTUAL TABLE guias_fts USING fts5(
  id UNINDEXED, titulo, texto,
  tokenize='unicode61 remove_diacritics 2'
);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", default="datos/productos.json")
    ap.add_argument("--guias", default="datos/guias.json")
    a = ap.parse_args()

    ruta = pathlib.Path(a.fuente)
    if not ruta.exists():
        print(f"no existe {ruta}. Opciones:")
        print("  python -m ingesta.fetch_all --ambiente bano && python -m ingesta.parse_all")
        print("  python -m ingesta.build_index --fuente pruebas/fixture_productos.json")
        return
    productos = json.load(open(ruta, encoding="utf-8"))
    guias = json.load(open(a.guias, encoding="utf-8")) if pathlib.Path(a.guias).exists() else []

    db = sqlite3.connect(DB)
    db.executescript(ESQUEMA)
    for p in productos:
        db.execute(
            """INSERT OR REPLACE INTO productos VALUES
               (:sku,:nombre,:marca,:categoria,:cat_id,:precio,:precio_antes,:unidad,
                :m2_por_caja,:kg_por_bulto,:rendimiento_m2,:unidad_incierta,
                :url,:imagen_url,:capturado_en)""",
            {k: p.get(k) for k in
             ("sku", "nombre", "marca", "categoria", "cat_id", "precio", "precio_antes",
              "unidad", "m2_por_caja", "kg_por_bulto", "rendimiento_m2", "url",
              "imagen_url", "capturado_en")} | {"unidad_incierta": int(p.get("unidad_incierta", False))},
        )
        db.execute("INSERT INTO productos_fts (sku,nombre,marca,categoria) VALUES (?,?,?,?)",
                   (p["sku"], p.get("nombre", ""), p.get("marca", ""), p.get("categoria", "")))
    for g in guias:
        db.execute("INSERT OR REPLACE INTO guias VALUES (:id,:categoria,:titulo,:texto,:url)", g)
        db.execute("INSERT INTO guias_fts (id,titulo,texto) VALUES (?,?,?)",
                   (g["id"], g.get("titulo", ""), g.get("texto", "")))
    db.commit()
    n_p = db.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    n_g = db.execute("SELECT COUNT(*) FROM guias").fetchone()[0]
    db.close()
    print(f"{DB}: {n_p} productos, {n_g} guias")


if __name__ == "__main__":
    main()
