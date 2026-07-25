"""Las herramientas, con sus schemas y sus ejecutores.

El aislamiento de informacion se implementa AQUI: cada rol recibe una lista de
tools distinta. El Cuantificador no tiene ninguna herramienta que devuelva
precios; el Comprador no tiene ninguna que devuelva cantidades de obra.
"""
from __future__ import annotations
import os, re, time
from config.categorias import CONCEPTO_A_CATEGORIA
from dominio import catalogo, reglas
from dominio.schemas import LIMITES, Espacio, Producto, Requerimiento

MODO_OFFLINE = os.environ.get("MODO_OFFLINE") == "1"
_RE_PRECIO = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+)")
_estado_live = {"fallos": 0, "deshabilitado": MODO_OFFLINE, "ultima_peticion": 0.0}


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
    # El default debe salir del tipo: LIMITES["cocina"]["presupuesto_min"] supera
    # el millon, y Espacio._coherencia rechazaria un default fijo mas bajo.
    tipo = espacio.get("tipo")
    default_presupuesto = LIMITES.get(tipo, {}).get("presupuesto_min", 1_000_000)
    e = Espacio(**{**espacio, "presupuesto_cop": espacio.get("presupuesto_cop", default_presupuesto)})
    req = reglas.calcular(regla_id, e)
    return req.model_dump()


# ---------- catalogo (sin cantidades) ----------

def _specs_recortadas(p: Producto, n: int = 5) -> dict:
    """El loop trunca cada resultado de tool a 12k: no cabe la ficha completa."""
    return dict(sorted(p.specs.items())[:n])


def buscar_catalogo(consulta: str, concepto: str | None = None,
                    precio_max: int | None = None, marca: str | None = None,
                    k: int = 8) -> dict:
    cats = CONCEPTO_A_CATEGORIA.get(concepto or consulta)
    ps = catalogo.buscar(consulta, categorias=cats, precio_max=precio_max, marca=marca, k=k)
    return {"n": len(ps), "categorias_filtradas": cats,
            "productos": [{"sku": p.sku, "nombre": p.nombre, "marca": p.marca,
                           "precio": p.precio, "unidad": p.unidad,
                           "m2_por_caja": p.m2_por_caja, "kg_por_bulto": p.kg_por_bulto,
                           "rendimiento_m2": p.rendimiento_m2,
                           "unidad_incierta": p.unidad_incierta,
                           "specs": _specs_recortadas(p), "url": p.url} for p in ps]}


def ficha_producto(sku: str) -> dict:
    """Ficha tecnica de UN producto, citada al snapshot. Sin specs indexadas lo
    dice en `nota` en vez de callarlo."""
    p = catalogo.por_sku(str(sku))
    if not p:
        return {"error": f"SKU {sku} no esta en el snapshot del catalogo"}
    return {"sku": p.sku, "nombre": p.nombre, "marca": p.marca, "modelo": p.modelo,
            "categoria": p.categoria, "precio": p.precio, "unidad": p.unidad,
            "specs": p.specs, "rating": p.rating, "total_reviews": p.total_reviews,
            "url": p.url, "capturado_en": p.capturado_en,
            "fuente": f"snapshot catalogo Homecenter {p.capturado_en}",
            "nota": "" if p.specs else "sin especificaciones tecnicas en este snapshot"}


def comparar_productos(sku_a: str, sku_b: str) -> dict:
    """El LLM redacta, Python calcula el diff. Nunca al reves."""
    a, b = catalogo.por_sku(str(sku_a)), catalogo.por_sku(str(sku_b))
    if not a or not b:
        faltante = sku_a if not a else sku_b
        return {"error": f"SKU {faltante} no esta en el snapshot del catalogo"}
    diferencias, comunes = [], []
    for clave in sorted(set(a.specs) | set(b.specs)):
        va, vb = a.specs.get(clave), b.specs.get(clave)
        if va is not None and va == vb:
            comunes.append({"clave": clave, "valor": va})
        else:
            diferencias.append({"clave": clave, "a": va, "b": vb})
    return {"a": ficha_producto(sku_a), "b": ficha_producto(sku_b),
            "diferencias": diferencias, "comunes": comunes,
            "solo_en_a": sorted(set(a.specs) - set(b.specs)),
            "solo_en_b": sorted(set(b.specs) - set(a.specs)),
            "delta_precio_cop": a.precio - b.precio,
            "fuente": [a.url, b.url]}


def recomendar_por_specs(consulta: str, specs: dict | None = None,
                         precio_max: int | None = None, k: int = 5) -> dict:
    """FTS recupera, PYTHON ordena. Si ordenara el LLM el criterio no seria auditable."""
    candidatos = catalogo.buscar_por_specs(consulta, precio_max=precio_max, k=30)
    if not candidatos:
        return {"n": 0, "productos": [], "criterios": specs or {},
                "fuente": "sin coincidencias en specs indexadas"}
    criterios = {str(c): str(v) for c, v in (specs or {}).items()}

    def puntaje(p: Producto) -> int:
        return sum(1 for c, v in criterios.items()
                   if c in p.specs and v.lower() in p.specs[c].lower())

    ordenados = sorted(candidatos, key=lambda p: (-puntaje(p), p.precio))[:k]
    return {"n": len(ordenados), "criterios": criterios,
            "productos": [{"sku": p.sku, "nombre": p.nombre, "marca": p.marca,
                           "precio": p.precio, "specs": _specs_recortadas(p),
                           "puntaje": puntaje(p), "url": p.url} for p in ordenados],
            "fuente": "productos_specs_fts sobre snapshot Homecenter"}


def validar_en_vivo(sku: str) -> dict:
    """GET al PDP real. Circuit breaker: tras 2 fallos se degrada al snapshot y
    la UI lo dice explicitamente. Respeta robots.txt (permitido()) y el DELAY
    minimo de 1.8s entre requests (regla 6 de CLAUDE.md): se gatea con un
    timestamp de ultima peticion a nivel de modulo, en vez de dormir siempre,
    para no penalizar la primera llamada de cada corrida."""
    base = catalogo.por_sku(str(sku))
    if not base:
        return {"sku": sku, "error": "SKU no esta en el snapshot"}
    if _estado_live["deshabilitado"]:
        return {"sku": sku, "estado": "snapshot", "precio": base.precio,
                "capturado_en": base.capturado_en, "en_vivo": False}
    try:
        from ingesta.fetch import BASE, DELAY, SESSION, permitido
        url = f"{BASE}/homecenter-co/product/{sku}/x/{sku}/"
        if not permitido(url):
            raise RuntimeError("bloqueado por robots.txt")
        espera = DELAY - (time.time() - _estado_live["ultima_peticion"])
        if espera > 0:
            time.sleep(espera)
        t0 = time.time()
        r = SESSION.get(url, timeout=5)
        _estado_live["ultima_peticion"] = time.time()
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
     "precio_max": {"type": "integer"},
     "marca": {"type": "string", "description": "filtra por marca del producto"},
     "k": {"type": "integer", "default": 8}}, ["consulta"])

T_FICHA = _t("ficha_producto",
    "Ficha tecnica completa de UN producto por SKU: specs, marca, modelo, precio, "
    "rating y URL citable. Usala antes de afirmar cualquier caracteristica.",
    {"sku": {"type": "string"}}, ["sku"])

T_COMPARAR = _t("comparar_productos",
    "Compara dos SKUs y devuelve las diferencias de specs calculadas por Python, "
    "mas el delta de precio. Usala para responder en que se diferencian dos productos.",
    {"sku_a": {"type": "string"}, "sku_b": {"type": "string"}}, ["sku_a", "sku_b"])

T_RECOMENDAR = _t("recomendar_por_specs",
    "Busca productos por caracteristicas tecnicas y los ordena por cuantos criterios "
    "cumplen y luego por precio. El orden lo calcula Python, no tu.",
    {"consulta": {"type": "string"},
     "specs": {"type": "object", "description": "caracteristicas deseadas, {clave: valor}"},
     "precio_max": {"type": "integer"}, "k": {"type": "integer", "default": 5}}, ["consulta"])

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
    """SIN acceso a precios. Verificado en pruebas/prove.py."""
    return [T_LISTAR_REGLAS, T_CONSULTAR_GUIA, T_CALCULAR, T_ENTREGAR_REQS]


def tools_comprador() -> list[dict]:
    """SIN acceso a cantidades ni al presupuesto."""
    return [T_BUSCAR, T_FICHA, T_COMPARAR, T_RECOMENDAR, T_VALIDAR, T_ENTREGAR_CANDS]


def tools_qa() -> list[dict]:
    return [T_CONSULTAR_GUIA, T_BUSCAR, T_FICHA, T_COMPARAR, T_RECOMENDAR]
