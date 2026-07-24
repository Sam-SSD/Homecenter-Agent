"""Capa de LLM con pool de llaves y cadena de modelos.

Diseño: el resto del proyecto NO sabe qué proveedor hay debajo. `src/loop.py`
llama `generar()` y recibe una respuesta normalizada. Cambiar de proveedor o
rotar llaves no toca ni una línea de los agentes.

Config en .env:
  GEMINI_API_KEYS=llave1,llave2,llave3      # se rotan en orden ante fallo
  GEMINI_MODELOS=gemini-2.5-flash           # cadena de fallback, separada por comas
  LLM_PROVEEDOR=gemini                      # o "anthropic"
  ANTHROPIC_API_KEY=...                     # solo si LLM_PROVEEDOR=anthropic

Comandos:
  python -m src.llm             # ping: prueba cada llave y reporta el pool
  python -m src.llm --modelos   # le pregunta a tus llaves qué modelos soportan
"""
from __future__ import annotations
import os, sys, time
from dataclasses import dataclass, field

# ---------------------------------------------------------------- configuración

def _lista(nombre: str, defecto: str = "") -> list[str]:
    crudo = os.environ.get(nombre, defecto) or ""
    return [x.strip() for x in crudo.replace("\n", ",").replace(";", ",").split(",") if x.strip()]


def _cargar_env() -> None:
    """Lee .env sin dependencias externas. Idempotente."""
    import pathlib
    p = pathlib.Path(".env")
    if not p.exists():
        return
    for linea in p.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env()

PROVEEDOR = os.environ.get("LLM_PROVEEDOR", "gemini").lower()
MODELOS = _lista("GEMINI_MODELOS", "gemini-2.5-flash")
COOLDOWN_S = int(os.environ.get("LLM_COOLDOWN_S", "60"))


# ------------------------------------------------------------------- pool de llaves

@dataclass
class Llave:
    valor: str
    etiqueta: str
    usos: int = 0
    fallos: int = 0
    inhabilitada: bool = False
    motivo: str = ""
    libre_desde: float = 0.0

    @property
    def disponible(self) -> bool:
        return not self.inhabilitada and time.time() >= self.libre_desde

    def enfriar(self, segundos: int, motivo: str) -> None:
        self.libre_desde = time.time() + segundos
        self.fallos += 1
        self.motivo = motivo

    def matar(self, motivo: str) -> None:
        self.inhabilitada = True
        self.fallos += 1
        self.motivo = motivo


def _construir_pool() -> list[Llave]:
    crudas = _lista("GEMINI_API_KEYS")
    if not crudas and os.environ.get("GEMINI_API_KEY"):
        crudas = [os.environ["GEMINI_API_KEY"]]
    return [Llave(valor=k, etiqueta=f"key{i+1}:...{k[-4:]}") for i, k in enumerate(crudas)]


POOL: list[Llave] = _construir_pool()


def estado() -> dict:
    return {
        "proveedor": PROVEEDOR,
        "modelos": MODELOS,
        "llaves": len(POOL),
        "disponibles": sum(1 for k in POOL if k.disponible),
        "detalle": [{"llave": k.etiqueta, "usos": k.usos, "fallos": k.fallos,
                     "estado": "inhabilitada" if k.inhabilitada
                     else ("enfriando" if not k.disponible else "ok"),
                     "motivo": k.motivo} for k in POOL],
    }


# ------------------------------------------------------- clasificación de errores

FATAL_LLAVE = ("api key not valid", "api_key_invalid", "invalid api key",
               "permission_denied", "unauthorized", "401", "403",
               "consumer_suspended", "api key expired")
CUOTA = ("resource_exhausted", "quota", "rate limit", "429", "too many requests")
MODELO_MALO = ("not found", "404", "is not supported", "not_found", "unsupported model")
TRANSITORIO = ("500", "502", "503", "504", "internal", "unavailable", "overloaded",
               "deadline", "timeout", "connection")


def _clasificar(e: Exception) -> str:
    t = f"{type(e).__name__} {e}".lower()
    if any(s in t for s in FATAL_LLAVE):
        return "llave_muerta"
    if any(s in t for s in CUOTA):
        return "cuota"
    if any(s in t for s in MODELO_MALO):
        return "modelo_malo"
    if any(s in t for s in TRANSITORIO):
        return "transitorio"
    return "desconocido"


# ------------------------------------------------------------ respuesta normalizada

@dataclass
class Llamada:
    nombre: str
    args: dict
    id: str = ""


@dataclass
class Respuesta:
    texto: str = ""
    llamadas: list[Llamada] = field(default_factory=list)
    crudo: object = None
    modelo: str = ""
    llave: str = ""
    intentos: int = 0


# --------------------------------------------- conversion de schemas a Gemini

_TIPOS = {"string": "STRING", "integer": "INTEGER", "number": "NUMBER",
          "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT"}


def _schema_gemini(prop: dict):
    """Convierte un JSON Schema simple al Schema de Gemini.

    Gemini rechaza OBJECT sin properties y propiedades sin type, que es
    justamente lo que usan las tools de forma libre (candidatos, requerimientos).
    Esos casos se degradan a STRING y el ejecutor parsea el JSON.
    """
    from google.genai import types
    t = (prop or {}).get("type")
    desc = (prop or {}).get("description", "")
    if t == "object":
        props = prop.get("properties") or {}
        if not props:
            return types.Schema(type="STRING",
                                description=(desc + " (pasar como JSON en texto)").strip())
        return types.Schema(type="OBJECT", description=desc,
                            properties={k: _schema_gemini(v) for k, v in props.items()},
                            required=prop.get("required") or None)
    if t == "array":
        items = prop.get("items") or {}
        if not items or (items.get("type") == "object" and not items.get("properties")):
            return types.Schema(type="STRING",
                                description=(desc + " (lista JSON en texto)").strip())
        return types.Schema(type="ARRAY", description=desc, items=_schema_gemini(items))
    if t in _TIPOS:
        return types.Schema(type=_TIPOS[t], description=desc)
    return types.Schema(type="STRING", description=desc)


def _tools_gemini(tools: list[dict]):
    """De la forma declarativa de src/tools.py a FunctionDeclaration de Gemini."""
    from google.genai import types
    decls = []
    for t in tools:
        esquema = t.get("input_schema") or {}
        props = esquema.get("properties") or {}
        parametros = None
        if props:
            parametros = types.Schema(
                type="OBJECT",
                properties={k: _schema_gemini(v) for k, v in props.items()},
                required=esquema.get("required") or None,
            )
        decls.append(types.FunctionDeclaration(
            name=t["name"], description=t.get("description", ""), parameters=parametros))
    return [types.Tool(function_declarations=decls)]


# --------------------------------------------------------------- adaptador Gemini

_clientes: dict[str, object] = {}


def _cliente_gemini(llave: str):
    if llave not in _clientes:
        from google import genai
        _clientes[llave] = genai.Client(api_key=llave)
    return _clientes[llave]


def _contenidos_gemini(historial: list[dict]):
    """historial neutro -> Content de Gemini.

    Cada entrada: {"rol": "usuario"|"modelo", "texto": str}
                  {"rol": "modelo", "llamadas": [Llamada]}
                  {"rol": "usuario", "resultados": [{"nombre":..., "salida": str}]}
    """
    from google.genai import types
    out = []
    for m in historial:
        rol = "model" if m["rol"] == "modelo" else "user"
        partes = []
        if m.get("texto"):
            partes.append(types.Part(text=m["texto"]))
        for ll in m.get("llamadas") or []:
            partes.append(types.Part(function_call=types.FunctionCall(
                name=ll.nombre, args=ll.args)))
        for r in m.get("resultados") or []:
            partes.append(types.Part.from_function_response(
                name=r["nombre"], response={"resultado": r["salida"]}))
        if partes:
            out.append(types.Content(role=rol, parts=partes))
    return out


def _llamar_gemini(llave: Llave, modelo: str, system: str,
                   historial: list[dict], tools: list[dict], max_tokens: int) -> Respuesta:
    from google.genai import types
    cliente = _cliente_gemini(llave.valor)
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        tools=_tools_gemini(tools) if tools else None,
        max_output_tokens=max_tokens,
        temperature=0.2,
    )
    r = cliente.models.generate_content(
        model=modelo, contents=_contenidos_gemini(historial), config=cfg)

    textos, llamadas = [], []
    for cand in (r.candidates or []):
        for p in ((cand.content.parts if cand.content else None) or []):
            if getattr(p, "text", None):
                textos.append(p.text)
            fc = getattr(p, "function_call", None)
            if fc is not None and getattr(fc, "name", None):
                llamadas.append(Llamada(nombre=fc.name, args=dict(fc.args or {}),
                                        id=fc.name))
    return Respuesta(texto="\n".join(textos).strip(), llamadas=llamadas, crudo=r,
                     modelo=modelo, llave=llave.etiqueta)


# ------------------------------------------------------------ adaptador Anthropic

def _llamar_anthropic(modelo: str, system: str, historial: list[dict],
                      tools: list[dict], max_tokens: int) -> Respuesta:
    from anthropic import Anthropic
    cliente = Anthropic()
    mensajes = []
    for m in historial:
        if m["rol"] == "modelo":
            bloques = []
            if m.get("texto"):
                bloques.append({"type": "text", "text": m["texto"]})
            for ll in m.get("llamadas") or []:
                bloques.append({"type": "tool_use", "id": ll.id or ll.nombre,
                                "name": ll.nombre, "input": ll.args})
            mensajes.append({"role": "assistant", "content": bloques})
        elif m.get("resultados"):
            mensajes.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": r.get("id") or r["nombre"],
                 "content": r["salida"]} for r in m["resultados"]]})
        else:
            mensajes.append({"role": "user", "content": m.get("texto", "")})
    r = cliente.messages.create(model=modelo, max_tokens=max_tokens, system=system,
                                tools=tools, messages=mensajes)
    textos = [b.text for b in r.content if b.type == "text"]
    llamadas = [Llamada(nombre=b.name, args=dict(b.input), id=b.id)
                for b in r.content if b.type == "tool_use"]
    return Respuesta(texto="\n".join(textos).strip(), llamadas=llamadas, crudo=r,
                     modelo=modelo, llave="anthropic")


# ------------------------------------------------------------- punto de entrada

class SinLlavesDisponibles(RuntimeError):
    pass


def generar(system: str, historial: list[dict], tools: list[dict] | None = None,
            max_tokens: int = 4096, traza=None) -> Respuesta:
    """Intenta cada modelo de la cadena con cada llave disponible del pool.

    Orden: modelo1 x llave1, modelo1 x llave2, ... y si el modelo no existe pasa
    al siguiente modelo. Una llave con cuota agotada se enfría COOLDOWN_S segundos;
    una llave inválida se inhabilita para el resto de la sesión.
    """
    tools = tools or []
    if PROVEEDOR == "anthropic":
        modelo = os.environ.get("MODELO", "claude-sonnet-5")
        r = _llamar_anthropic(modelo, system, historial, tools, max_tokens)
        r.intentos = 1
        return r

    if not POOL:
        raise SinLlavesDisponibles(
            "no hay llaves. Pon GEMINI_API_KEYS=llave1,llave2 en .env")

    intentos, ultimo = 0, None
    for modelo in MODELOS:
        modelo_roto = False
        for llave in POOL:
            if not llave.disponible:
                continue
            intentos += 1
            try:
                llave.usos += 1
                r = _llamar_gemini(llave, modelo, system, historial, tools, max_tokens)
                r.intentos = intentos
                return r
            except Exception as e:  # noqa: BLE001
                ultimo = e
                clase = _clasificar(e)
                if traza:
                    traza.paso("llm", "fallback",
                               f"{modelo} / {llave.etiqueta}: {clase} - {str(e)[:70]}")
                if clase == "llave_muerta":
                    llave.matar(clase)
                elif clase == "cuota":
                    llave.enfriar(COOLDOWN_S, clase)
                elif clase == "modelo_malo":
                    modelo_roto = True
                    break
                else:
                    llave.enfriar(5, clase)
        if modelo_roto:
            continue
    raise SinLlavesDisponibles(
        f"agotadas {len(POOL)} llaves y {len(MODELOS)} modelos tras {intentos} "
        f"intentos. Ultimo error: {ultimo}")


def como_dict(x) -> dict:
    """Las tools de forma libre viajan como JSON en texto cuando el proveedor no
    soporta objetos sin esquema. Esto acepta ambas formas."""
    import json
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            v = json.loads(x)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


def como_lista(x) -> list:
    import json
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            v = json.loads(x)
            return v if isinstance(v, list) else ([v] if v else [])
        except Exception:
            return []
    return []


# ------------------------------------------------------------------------- CLI

def _ping() -> int:
    print(f"proveedor: {PROVEEDOR}")
    print(f"modelos:   {MODELOS}")
    print(f"llaves:    {len(POOL)}")
    if not POOL and PROVEEDOR == "gemini":
        print("\nFALTA configurar .env:\n  GEMINI_API_KEYS=llave1,llave2,llave3")
        return 1
    hist = [{"rol": "usuario", "texto": "Responde exactamente: OK"}]
    for llave in POOL:
        t0 = time.time()
        try:
            r = _llamar_gemini(llave, MODELOS[0], "", hist, [], 32)
            print(f"  [OK]    {llave.etiqueta}  {time.time()-t0:.1f}s  "
                  f"{MODELOS[0]}  -> {r.texto[:30]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  [FALLA] {llave.etiqueta}  {_clasificar(e)}  {str(e)[:90]}")
    print("\nprueba de fallback completa (usa generar()):")
    try:
        r = generar("", hist, [], 32)
        print(f"  respondio {r.llave} con {r.modelo} en {r.intentos} intento(s): {r.texto[:40]!r}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  ninguna llave sirvio: {e}")
        return 1


def _listar_modelos() -> int:
    if not POOL:
        print("sin llaves en .env")
        return 1
    for llave in POOL:
        print(f"\n{llave.etiqueta}")
        try:
            cliente = _cliente_gemini(llave.valor)
            nombres = []
            for m in cliente.models.list():
                n = (m.name or "").replace("models/", "")
                acciones = getattr(m, "supported_actions", None) or \
                    getattr(m, "supported_generation_methods", None) or []
                if not acciones or "generateContent" in acciones:
                    nombres.append(n)
            for n in sorted(n for n in nombres if "gemini" in n and "embedding" not in n):
                print("   ", n)
        except Exception as e:  # noqa: BLE001
            print("    error:", str(e)[:120])
    print("\nPon los que quieras en .env:  GEMINI_MODELOS=modelo_preferido,modelo_respaldo")
    return 0


if __name__ == "__main__":
    sys.exit(_listar_modelos() if "--modelos" in sys.argv else _ping())
