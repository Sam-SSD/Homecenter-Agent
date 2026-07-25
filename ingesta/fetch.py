"""Descarga con cache en disco. Separa red de parseo: se descarga una vez y
se parsea veinte. Reanudable: si el run se corta, solo baja lo que falta.

Respeta robots.txt de homecenter.com.co (revisado 24-jul-2026, copia real en
ingesta/robots_homecenter_2026-07-24.txt; ingesta/robots_notas.md es el resumen
manual). PROHIBIDOS refleja los Disallow que aplican a user-agent: *.
"""
from __future__ import annotations
import hashlib, json, pathlib, time
import requests

BASE = "https://www.homecenter.com.co"
CACHE = pathlib.Path("cache/html")
MANIFEST = pathlib.Path("cache/manifest.jsonl")
DELAY = 1.8

PROHIBIDOS = ("N-", "/search", "/browse/", "/cart/", "/myaccount/", "/CMR/",
              "Ver-todos", "staticContent", ".aspx", "queryId=", "bvstate=")

FACETAS_OK = ("f.product.brandName=", "f.product.attribute.Tipo=",
              "f.product.attribute.Material=", "f.product.attribute.Color=",
              "f.product.attribute.Capacidad=", "f.product.attribute.Forma=")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "AgentSprint-EAFIT-hackathon/1.0 (demo academica)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-CO,es;q=0.9",
})


def permitido(url: str) -> bool:
    return not any(p in url for p in PROHIBIDOS)


def clave(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def cat_id_de(url: str) -> str | None:
    for parte in url.replace("?", "/").split("/"):
        if parte.startswith("cat") and parte[3:4].isdigit():
            return parte
    return None


def url_categoria(cat_id: str, slug: str) -> str:
    return f"{BASE}/homecenter-co/category/{cat_id}/{slug}/"


def fetch(url: str, force: bool = False) -> str | None:
    """Devuelve el HTML. Usa cache salvo force=True. None si robots lo prohibe o falla.

    REANUDABLE: si el archivo ya esta en cache NO se hace ningun request. Volver a
    lanzar fetch_all solo baja lo que falta; nunca borra ni reempieza.
    El unico modo que re-descarga es force=True (o sea --force).
    """
    if not permitido(url):
        print(f"  omitido por robots: {url}")
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    archivo = CACHE / f"{clave(url)}.html"
    if archivo.exists() and not force:
        # Se re-registra por si el proceso murio entre escribir y registrar en
        # una corrida anterior: _registrar es idempotente y evita huerfanos.
        _registrar(url)
        return archivo.read_text(encoding="utf-8")
    try:
        r = SESSION.get(url, timeout=25)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  fallo {url}: {e}")
        return None
    finally:
        time.sleep(DELAY)
    # Escribir primero a .tmp y renombrar: un Ctrl+C a mitad no deja un HTML
    # truncado que el parser leeria como pagina valida.
    tmp = archivo.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(archivo)
    _registrar(url)
    return html


def _registrar(url: str) -> None:
    entrada = {"hash": clave(url), "url": url, "cat_id": cat_id_de(url), "ts": time.time()}
    vistos = {json.loads(l)["hash"] for l in MANIFEST.read_text(encoding="utf-8").splitlines()} \
        if MANIFEST.exists() else set()
    if entrada["hash"] in vistos:
        return
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
