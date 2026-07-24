"""Parseo offline del HTML cacheado. Cero red."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE = "https://www.homecenter.com.co"

RE_PDP = re.compile(r"/product/(\d+)/([^/?]+)/(\d+)")
# Los precios de producto terminan en .900 / .000 con 3 grupos. El regex global
# sobre la pagina tambien captura los rangos del filtro lateral ($150.000 -
# $300.000), por eso el precio SIEMPRE se ancla a la tarjeta del producto.
RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")
RE_RUIDO = re.compile(r"^(BANK_PROMOTION|EVENT\w*|Comparar|Agregar al carro)\s*", re.I)

RE_M2_CAJA = re.compile(r"(\d+[.,]\d+)\s*m2", re.I)
RE_KG = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg", re.I)
RE_RENDIM = re.compile(r"(\d+)\s*m2\s*(?:/|por\s*)?\s*(gal|galon|lt|litro)", re.I)
RE_GALON = re.compile(r"\bgal(?:on|\.)?\b", re.I)
RE_M2_ANY = re.compile(r"(\d+(?:[.,]\d+)?)\s*m2", re.I)


def leer_html(ruta: str) -> str:
    """El cache se escribe en utf-8, pero un archivo bajado con otra herramienta
    puede venir en cp1252. Probar los dos evita perder la pagina entera."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(ruta, encoding="utf-8", errors="replace") as f:
        return f.read()


def _precios_de(texto: str) -> list[int]:
    crudos = {int(x.replace(".", "")) for x in RE_PRECIO.findall(texto)}
    return sorted(c for c in crudos if 1000 <= c <= 30_000_000)


def _tarjeta(a, max_subida: int = 7, max_chars: int = 1800):
    """Sube por los ancestros y devuelve el mas pequeno que contenga un precio.
    El limite de caracteres evita agarrar la grilla completa y con ella los
    rangos del filtro lateral."""
    nodo = a
    for _ in range(max_subida):
        nodo = nodo.parent
        if nodo is None or nodo.name in ("body", "html", "[document]"):
            return None
        texto = nodo.get_text(" ", strip=True)
        if RE_PRECIO.search(texto) and len(texto) <= max_chars:
            return nodo
    return None


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
    de color: cat90040 muestra 44 productos y ~55 ids.

    Agrupa TODAS las anclas de cada SKU antes de decidir, porque la primera suele
    ser la imagen (texto vacio o 'BANK_PROMOTION') y la buena viene despues.
    """
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    por_sku: dict[str, dict] = {}
    for a in soup.select('a[href*="/product/"]'):
        m = RE_PDP.search(a.get("href", ""))
        if not m:
            continue
        sku, slug, variante = m.groups()
        e = por_sku.setdefault(sku, {"slug": slug, "variante": variante,
                                     "href": a["href"], "anclas": []})
        e["anclas"].append(a)

    productos = []
    for sku, info in por_sku.items():
        tarjeta = None
        for a in info["anclas"]:
            tarjeta = _tarjeta(a)
            if tarjeta is not None:
                break
        if tarjeta is None:
            continue
        precios = _precios_de(tarjeta.get_text(" ", strip=True))
        if not precios:
            continue

        nombres = []
        for a in info["anclas"]:
            t = RE_RUIDO.sub("", a.get_text(" ", strip=True)).strip()
            if len(t) > 8 and "$" not in t:
                nombres.append(t)
        nombre = max(nombres, key=len) if nombres else info["slug"].replace("-", " ").title()

        marca = ""
        for b in tarjeta.select('a[href*="/brand/"]'):
            t = b.get_text(strip=True)
            if 2 < len(t) < 30:
                marca = t
                break
        if not marca:
            for a in info["anclas"]:
                t = a.get_text(" ", strip=True)
                if 2 < len(t) < 22 and "$" not in t and t.lower() in nombre.lower():
                    marca = t
                    break

        href = info["href"]
        productos.append(enriquecer({
            "sku": sku,
            "nombre": nombre[:200],
            "marca": marca,
            "categoria": categoria,
            "cat_id": cat_id,
            "precio": precios[0],
            "precio_antes": precios[-1] if len(precios) > 1 else None,
            "url": href if href.startswith("http") else BASE + href,
            "imagen_url": f"https://media.falabella.com/sodimacCO/{info['variante']}/w=800,h=800,f=webp",
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
