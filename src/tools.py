"""Las herramientas, con sus schemas y sus ejecutores.

El aislamiento de informacion se implementa AQUI: cada rol recibe una lista de
tools distinta. El Cuantificador no tiene ninguna herramienta que devuelva
precios; el Comprador no tiene ninguna que devuelva cantidades de obra.
"""
from __future__ import annotations
import os, re, time
from data.categorias import CONCEPTO_A_CATEGORIA
from src import catalogo, reglas
from src.schemas import Espacio, Producto, Requerimiento

MODO_OFFLINE = os.environ.get("MODO_OFFLINE") == "1"
_RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")
_estado_live = {"fallos": 0, "deshabilitado": MODO_OFFLINE}


# ---------- conocimiento (sin precios) ----------

def consultar_guia(consulta: str, k: int = 3) -> dict:
    r = catalogo.buscar_guias(consulta, k=k)
    if not r:
        return {"resultados": [], "nota": "sin fuente verificada para esa consulta"}
    return {"resultados": r}


def listar_reglas(tipo: str | None = None) -> dict:
    return {"reglas": reglas.listar(tipo)}


def calcular_cantidad(regla_id: str, espacio: dict) -> dict:
    """El LLM no hace aritmetica: pasa la regla y el espacio, Python calcula."""
    e = Espacio(**{**espacio, "presupuesto_cop": espacio.get("presupuesto_cop", 1_000_000)})
    req = reglas.calcular(regla_id, e)
    return req.model_dump()


# ---------- catalogo (sin cantidades) ----------

def buscar_catalogo(consulta: str, concepto: str | None = None,
                    precio_max: int | None = None, k: int = 8) -> dict:
    cats = CONCEPTO_A_CATEGORIA.get(concepto or consulta)
    ps = catalogo.buscar(consulta, categorias=cats, precio_max=precio_max, k=k)
    return {"n": len(ps), "categorias_filtradas": cats,
            "productos": [{"sku": p.sku, "nombre": p.nombre, "marca": p.marca,
                           "precio": p.precio, "unidad": p.unidad,
                           "m2_por_caja": p.m2_por_caja, "kg_por_bulto": p.kg_por_bulto,
                           "rendimiento_m2": p.rendimiento_m2,
                           "unidad_incierta": p.unidad_incierta, "url": p.url} for p in ps]}


def validar_en_vivo(sku: str) -> dict:
    """GET al PDP real. Circuit breaker: tras 2 fallos se degrada al snapshot y
    la UI lo dice explicitamente."""
    base = catalogo.por_sku(str(sku))
    if not base:
        return {"sku": sku, "error": "SKU no esta en el snapshot"}
    if _estado_live["deshabilitado"]:
        return {"sku": sku, "estado": "snapshot", "precio": base.precio,
                "capturado_en": base.capturado_en, "en_vivo": False}
    try:
        from ingest.fetch import SESSION, BASE
        t0 = time.time()
        r = SESSION.get(f"{BASE}/homecenter-co/product/{sku}/x/{sku}/", timeout=5)
        m = _RE_PRECIO.search(r.text)
        if r.status_code != 200 or not m:
            raise RuntimeError(f"http={r.status_code} precio={'no' if not m else 'si'}")
        actual = int(m.group(1).replace(".", ""))
        _estado_live["fallos"] = 0
        return {"sku": sku, "estado": "en_vivo" if actual == base.precio else "cambio",
                "precio": actual, "precio_snapshot": base.precio,
                "coincide": actual == base.precio, "en_vivo": True,
                "latencia_s": round(time.time() - t0, 2)}
    except Exception as e:
        _estado_live["fallos"] += 1
        if _estado_live["fallos"] >= 2:
            _estado_live["deshabilitado"] = True
        return {"sku": sku, "estado": "snapshot", "precio": base.precio,
                "capturado_en": base.capturado_en, "en_vivo": False, "motivo": str(e)[:80]}


# ---------- schemas para la API ----------

def _t(nombre, desc, props, req):
    return {"name": nombre, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": req}}


T_CONSULTAR_GUIA = _t("consultar_guia",
    "Busca en las guias tecnicas y FAQ publicados por Homecenter. Unica fuente valida "
    "para restricciones de instalacion. Devuelve titulo, texto y URL citable.",
    {"consulta": {"type": "string"}, "k": {"type": "integer", "default": 3}}, ["consulta"])

T_LISTAR_REGLAS = _t("listar_reglas",
    "Lista las reglas de cuantificacion disponibles con su concepto, unidad y prioridad.",
    {}, [])

T_CALCULAR = _t("calcular_cantidad",
    "Ejecuta una regla de cuantificacion sobre el espacio y devuelve la cantidad con "
    "su formula sustituida. El calculo lo hace Python, no tu.",
    {"regla_id": {"type": "string"},
    },
    ["regla_id"])

T_BUSCAR = _t("buscar_catalogo",
    "Busca productos reales en el snapshot del catalogo de Homecenter. Devuelve sku, "
    "nombre, precio, unidad de venta y URL. Solo puedes proponer SKUs que salgan de aqui.",
    {"consulta": {"type": "string"},
     "concepto": {"type": "string", "description": "concepto de obra para filtrar categorias"},
     "precio_max": {"type": "integer"}, "k": {"type": "integer", "default": 8}}, ["consulta"])

T_VALIDAR = _t("validar_en_vivo",
    "Consulta la pagina de producto real y confirma el precio actual. Si la red falla, "
    "degrada al snapshot y lo informa.",
    {"sku": {"type": "string"}}, ["sku"])

T_ENTREGAR_REQS = _t("entregar_requerimientos",
    "Entrega la lista final de requerimientos de obra y termina tu trabajo.",
    {"requerimientos": {"type": "array", "items": {"type": "object"}}}, ["requerimientos"])

T_ENTREGAR_CANDS = _t("entregar_candidatos",
    "Entrega los candidatos por concepto y termina tu trabajo. Formato: "
    "{concepto: {economico: sku, media: sku, premium: sku}}.",
    {"candidatos": {"type": "object"},
     "justificaciones": {"type": "object", "description": "{sku: una linea}"},
     "sin_candidatos": {"type": "array", "items": {"type": "string"}}}, ["candidatos"])


def tools_cuantificador() -> list[dict]:
    """SIN acceso a precios. Verificado en evals/prove.py."""
    return [T_LISTAR_REGLAS, T_CONSULTAR_GUIA, T_CALCULAR, T_ENTREGAR_REQS]


def tools_comprador() -> list[dict]:
    """SIN acceso a cantidades ni al presupuesto."""
    return [T_BUSCAR, T_VALIDAR, T_ENTREGAR_CANDS]


def tools_qa() -> list[dict]:
    return [T_CONSULTAR_GUIA, T_BUSCAR]
