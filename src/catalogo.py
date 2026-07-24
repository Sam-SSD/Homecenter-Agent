"""Acceso al catalogo: SQL + FTS5. NO es una base vectorial y es a proposito.
Un embedding no responde "el mas barato bajo $400.000 en porcelana blanca";
un WHERE + bm25 si, y es auditable linea por linea."""
from __future__ import annotations
import re, sqlite3
from src.schemas import Producto

DB = "data/catalogo.db"
_RE_TOKEN = re.compile(r"[0-9a-zA-ZaeiouAEIOUnN]+")


def _con() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def consulta_fts(texto: str) -> str:
    """FTS5 revienta con comillas, guiones y parentesis. Tokeniza y une con OR."""
    tokens = [t for t in _RE_TOKEN.findall(texto or "") if len(t) > 2][:8]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


def _fila_a_producto(r: sqlite3.Row) -> Producto:
    return Producto(**{k: r[k] for k in r.keys() if k != "unidad_incierta"} |
                    {"unidad_incierta": bool(r["unidad_incierta"])})


def buscar(consulta: str, categorias: list[str] | None = None,
           precio_max: int | None = None, precio_min: int | None = None,
           k: int = 8) -> list[Producto]:
    q = consulta_fts(consulta)
    where, params = [], []
    if categorias:
        where.append(f"p.categoria IN ({','.join('?' * len(categorias))})")
        params += list(categorias)
    if precio_max:
        where.append("p.precio <= ?")
        params.append(int(precio_max))
    if precio_min:
        where.append("p.precio >= ?")
        params.append(int(precio_min))
    filtro = (" AND " + " AND ".join(where)) if where else ""

    with _con() as c:
        if q:
            sql = (f"SELECT p.* FROM productos_fts f JOIN productos p ON p.sku = f.sku "
                   f"WHERE productos_fts MATCH ?{filtro} "
                   f"ORDER BY bm25(productos_fts), p.precio LIMIT ?")
            filas = c.execute(sql, [q, *params, k]).fetchall()
            if filas:
                return [_fila_a_producto(r) for r in filas]
        # sin match textual: cae al filtro estructurado, ordenado por precio
        sql = f"SELECT p.* FROM productos p WHERE 1=1{filtro} ORDER BY p.precio LIMIT ?"
        return [_fila_a_producto(r) for r in c.execute(sql, [*params, k]).fetchall()]


def por_sku(sku: str) -> Producto | None:
    with _con() as c:
        r = c.execute("SELECT * FROM productos WHERE sku=?", (str(sku),)).fetchone()
    return _fila_a_producto(r) if r else None


def skus_conocidos() -> set[str]:
    with _con() as c:
        return {r[0] for r in c.execute("SELECT sku FROM productos")}


def _normalizar(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def filtrar_por_concepto(ps: list[Producto], concepto: str) -> list[Producto]:
    """Descarta accesorios y repuestos que viven en la misma categoria.
    Si el filtro deja la lista vacia, devuelve la original: mejor un candidato
    imperfecto que ningun candidato."""
    from data.categorias import CONCEPTO_FILTROS
    f = CONCEPTO_FILTROS.get(concepto)
    if not f or not ps:
        return ps
    debe = [_normalizar(x) for x in f.get("debe", [])]
    no = [_normalizar(x) for x in f.get("no", [])]
    ok = []
    for p in ps:
        n = _normalizar(p.nombre)
        if no and any(x in n for x in no):
            continue
        if debe and not any(x in n for x in debe):
            continue
        ok.append(p)
    return ok or ps


def gamas(consulta: str, categorias: list[str] | None = None,
          unidad_requerida: str | None = None) -> dict[str, Producto]:
    """Tres opciones por concepto. Es lo que le permite al Negociador recortar.

    Filtra accesorios por nombre y, cuando la obra se mide en m2/kg/galon,
    prefiere productos que declaren su contenido de venta: si no lo declaran no
    se puede calcular cuantas cajas comprar."""
    ps = buscar(consulta, categorias=categorias, k=200)
    ps = filtrar_por_concepto(ps, consulta)
    if unidad_requerida in ("m2", "kg"):  # galon: la regla ya entrega galones
        con_unidad = [p for p in ps if p.contenido_por_unidad()]
        if con_unidad:
            ps = con_unidad
    if not ps:
        return {}
    ps = sorted(ps, key=lambda p: p.precio)
    # Percentiles en vez de min/max: los extremos absolutos suelen ser un
    # accesorio suelto o un producto industrial fuera de contexto.
    def en(frac: float) -> Producto:
        return ps[min(int(len(ps) * frac), len(ps) - 1)]
    return {"economico": en(0.10), "media": en(0.45), "premium": en(0.85)}


def buscar_guias(consulta: str, k: int = 3) -> list[dict]:
    q = consulta_fts(consulta)
    if not q:
        return []
    with _con() as c:
        try:
            filas = c.execute(
                "SELECT g.id, g.titulo, g.texto, g.url, g.categoria "
                "FROM guias_fts f JOIN guias g ON g.id = f.id "
                "WHERE guias_fts MATCH ? ORDER BY bm25(guias_fts) LIMIT ?",
                (q, k)).fetchall()
        except sqlite3.OperationalError:
            return []
    return [{"id": r["id"], "titulo": r["titulo"], "url": r["url"],
             "categoria": r["categoria"], "texto": r["texto"][:900]} for r in filas]


def stats() -> dict:
    with _con() as c:
        n = c.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        g = c.execute("SELECT COUNT(*) FROM guias").fetchone()[0]
        cats = [r[0] for r in c.execute("SELECT DISTINCT categoria FROM productos ORDER BY 1")]
        fecha = c.execute("SELECT MAX(capturado_en) FROM productos").fetchone()[0]
    return {"productos": n, "guias": g, "categorias": cats, "snapshot": fecha}
