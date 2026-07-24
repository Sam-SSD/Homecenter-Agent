"""Parseo offline del HTML cacheado. Cero red."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE = "https://www.homecenter.com.co"

RE_PDP = re.compile(r"/product/(\d+)/([^/?]+)/(\d+)")
# Los precios de producto terminan en .900 / .000 con 3 grupos. El regex global
# sobre la pagina tambien captura los rangos del filtro lateral ($150.000 -
# $300.000), por eso el precio SIEMPRE se ancla al contenedor de la tarjeta.
RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")

RE_M2_CAJA = re.compile(r"(\d+[.,]\d+)\s*m2", re.I)
RE_KG = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg", re.I)
RE_RENDIM = re.compile(r"(\d+)\s*m2\s*(?:/|por\s*)?\s*(gal|galon|lt|litro)", re.I)
RE_GALON = re.compile(r"\bgal(?:on|\.)?\b", re.I)
RE_M2_ANY = re.compile(r"(\d+(?:[.,]\d+)?)\s*m2", re.I)


def _precio_int(txt: str) -> int | None:
    m = RE_PRECIO.search(txt)
    return int(m.group(1).replace(".", "")) if m else None


def enriquecer(p: dict) -> dict:
    """Infiere unidad de venta desde el nombre. Lo que no se pueda inferir queda
    con unidad_incierta=True y el verificador lo marca."""
    n = p["nombre"]
    if m := RE_M2_CAJA.search(n):
        p["m2_por_caja"] = float(m.group(1).replace(",", "."))
        p["unidad"] = "m2"
    elif m := RE_RENDIM.search(n):
        p["rendimiento_m2"] = float(m.group(1))
        p["unidad"] = "galon"
    elif m := RE_KG.search(n):
        p["kg_por_bulto"] = float(m.group(1).replace(",", "."))
        p["unidad"] = "kg"
    elif RE_GALON.search(n):
        p["unidad"] = "galon"
        # "Galon 30 m2" (orden invertido respecto a RE_RENDIM)
        if m := RE_M2_ANY.search(n):
            p["rendimiento_m2"] = float(m.group(1).replace(",", "."))
        else:
            p["unidad_incierta"] = True
    else:
        p["unidad"] = "Und"
        cat = p.get("categoria", "")
        if any(k in cat for k in ("ceramic", "piso", "pared", "adhesivo", "boquilla", "pintura")):
            p["unidad_incierta"] = True
    return p


def parse_categoria(soup: BeautifulSoup, cat_id: str, categoria: str) -> list[dict]:
    """Un producto por SKU (primer id de la URL). Los ids siguientes son variantes
    de color: cat90040 muestra 44 productos y ~55 ids."""
    productos, vistos = [], set()
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for a in soup.select('a[href*="/product/"]'):
        m = RE_PDP.search(a.get("href", ""))
        if not m:
            continue
        sku, slug, variante = m.groups()
        if sku in vistos:
            continue
        contenedor = a.find_parent(
            lambda t: t.name in ("div", "li", "article", "section") and "$" in t.get_text()
        )
        if contenedor is None:
            continue
        texto = contenedor.get_text(" ", strip=True)
        crudos = [int(x.replace(".", "")) for x in RE_PRECIO.findall(texto)]
        crudos = sorted({c for c in crudos if 1000 <= c <= 30_000_000})
        if not crudos:
            continue
        nombre = a.get_text(" ", strip=True) or slug.replace("-", " ").title()
        nombre = re.sub(r"^(BANK_PROMOTION|EVENT\w*)\s*", "", nombre).strip()
        if len(nombre) < 5:
            nombre = slug.replace("-", " ").title()
        marca = ""
        for b in contenedor.select('a[href*="/brand/"], b, strong'):
            t = b.get_text(strip=True)
            if 2 < len(t) < 30 and "$" not in t:
                marca = t
                break
        vistos.add(sku)
        productos.append(enriquecer({
            "sku": sku,
            "nombre": nombre[:200],
            "marca": marca,
            "categoria": categoria,
            "cat_id": cat_id,
            "precio": crudos[0],
            "precio_antes": crudos[-1] if len(crudos) > 1 else None,
            "url": a["href"] if a["href"].startswith("http") else BASE + a["href"],
            "imagen_url": f"https://media.falabella.com/sodimacCO/{variante}/w=800,h=800,f=webp",
            "capturado_en": ahora,
        }))
    return productos


def parse_guias(soup: BeautifulSoup, cat_id: str, categoria: str) -> list[dict]:
    """Bloques SEO y FAQ al final de la categoria, escritos por Homecenter.
    Este es el corpus RAG: texto no estructurado con fuente citable."""
    chunks = []
    for h in soup.find_all(["h2", "h3", "h4", "h5"]):
        titulo = h.get_text(" ", strip=True)
        if not titulo or len(titulo) > 160:
            continue
        cuerpo = []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3", "h4", "h5"):
                break
            t = sib.get_text(" ", strip=True)
            if t:
                cuerpo.append(t)
            if sum(len(c) for c in cuerpo) > 2500:
                break
        texto = " ".join(cuerpo).strip()
        if len(texto) < 140:
            continue
        chunks.append({
            "id": f"guia:{cat_id}:{len(chunks)}",
            "categoria": categoria,
            "titulo": titulo,
            "texto": texto[:2200],
            "url": f"{BASE}/homecenter-co/category/{cat_id}/",
        })
    return chunks


def descubrir_facetas(soup: BeautifulSoup, cat_id: str, limite: int = 8) -> list[str]:
    """Las facetas permitidas en robots.txt reemplazan la paginacion: los links
    ya vienen en el HTML, no hay que adivinar el parametro de pagina."""
    from ingest.fetch import FACETAS_OK, permitido
    urls = set()
    for a in soup.select(f'a[href*="{cat_id}"]'):
        href = a.get("href", "")
        if any(f in href for f in FACETAS_OK) and permitido(href):
            urls.add(href if href.startswith("http") else BASE + href)
    return sorted(urls)[:limite]
