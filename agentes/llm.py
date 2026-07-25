"""Capa de LLM con pool de llaves y cadena de modelos.

Diseño: el resto del proyecto NO sabe qué proveedor hay debajo. `agentes/loop.py`
llama `generar()` y recibe una respuesta normalizada. Cambiar de proveedor o
rotar llaves no toca ni una línea de los agentes.

Config en .env:
  GEMINI_API_KEYS=llave1,llave2,llave3      # se rotan en orden ante fallo
  GEMINI_MODELOS=gemini-2.5-flash           # cadena de fallback, separada por comas
  LLM_PROVEEDOR=gemini                      # o "anthropic"
  ANTHROPIC_API_KEY=...                     # solo si LLM_PROVEEDOR=anthropic

Comandos:
  python -m agentes.llm             # ping: prueba cada llave y reporta el pool
  python -m agentes.llm --modelos   # le pregunta a tus llaves qué modelos soportan
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
# Con una sola llave, enfriarla equivale a rendirse. Si el pool entero esta
# enfriando y la mas cercana vuelve dentro de este techo, se espera en vez de
# fallar. Techo bajo a proposito: en demo, colgarse es peor que fallar claro.
ESPERA_MAX_S = int(os.environ.get("LLM_ESPERA_MAX_S", "25"))


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
    # cuota por modelo: {modelo: timestamp en que vuelve a estar libre}
    modelos_frios: dict = field(default_factory=dict)

    @property
    def disponible(self) -> bool:
        return not self.inhabilitada and time.time() >= self.libre_desde

    def enfriar(self, segundos: int, motivo: str) -> None:
        self.libre_desde = time.time() + segundos
        self.fallos += 1
        self.motivo = motivo

    def enfriar_modelo(self, modelo: str, segundos: int, motivo: str) -> None:
        """Cuota agotada de UN modelo. En el tier gratuito el limite es por
        modelo y por dia, asi que la llave sigue sirviendo para los demas de la
        cadena: enfriarla entera dejaria sin probar el resto."""
        self.modelos_frios[modelo] = time.time() + segundos
        self.fallos += 1
        self.motivo = f"{motivo} ({modelo})"

    def modelo_disponible(self, modelo: str) -> bool:
        return (not self.inhabilitada
                and time.time() >= max(self.libre_desde,
                                       self.modelos_frios.get(modelo, 0.0)))

    def matar(self, motivo: str) -> None:
        self.inhabilitada = True
        self.fallos += 1
        self.motivo = motivo


def _construir_pool() -> list[Llave]:
    """Acepta tres formas de declarar llaves, en este orden, y deduplica:

      GEMINI_API_KEYS=llave1,llave2,llave3     (lista)
      GEMINI_API_KEY=llave                     (una sola)
      GEMINI_API_KEY_1=...  GEMINI_API_KEY_2=  (numeradas, mas facil de editar)
    """
    crudas: list[str] = list(_lista("GEMINI_API_KEYS"))
    if os.environ.get("GEMINI_API_KEY"):
        crudas.append(os.environ["GEMINI_API_KEY"].strip())
    for i in range(1, 21):
        v = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
        if v:
            crudas.append(v)

    vistas, pool = set(), []
    for k in crudas:
        # ignora placeholders sin reemplazar
        if not k or k.lower().startswith(("llave", "aiza...", "tu_", "pega")):
            continue
        if k in vistas:
            continue
        vistas.add(k)
        pool.append(Llave(valor=k, etiqueta=f"key{len(pool)+1}:...{k[-4:]}"))
    return pool


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
# Peticion mal formada: la llave esta sana, el bug es nuestro. Rotar llaves no
# arregla nada y entierra el error real bajo "agotadas N llaves". Sin el numero
# 400 pelado: aparece dentro de cuerpos de error de cuota.
PETICION_MALA = ("invalid_argument", "failed_precondition")
# Caso especial de Gemini 3.x: reintentar sin las firmas si el modelo las rechaza.
FIRMA = ("thought_signature", "thought signature")


def _clasificar(e: Exception) -> str:
    t = f"{type(e).__name__} {e}".lower()
    if any(s in t for s in FIRMA):
        return "firma"
    if any(s in t for s in FATAL_LLAVE):
        return "llave_muerta"
    if any(s in t for s in CUOTA):
        return "cuota"
    if any(s in t for s in MODELO_MALO):
        return "modelo_malo"
    if any(s in t for s in PETICION_MALA):
        return "peticion_mala"
    if any(s in t for s in TRANSITORIO):
        return "transitorio"
    return "desconocido"


class PeticionMalFormada(RuntimeError):
    """El proveedor rechazo la peticion (400). Bug nuestro, no de la llave."""


def _demora_sugerida(e: Exception) -> int | None:
    """Gemini manda un RetryInfo en el 429 ('retryDelay': '7s'). Suele ser unos
    pocos segundos, no los 60 de COOLDOWN_S: conviene hacerle caso."""
    import re
    m = re.search(r"['\"]retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s?['\"]", str(e))
    if not m:
        return None
    return max(1, min(int(float(m.group(1))) + 1, COOLDOWN_S))


# ------------------------------------------------------------ respuesta normalizada

@dataclass
class Llamada:
    nombre: str
    args: dict
    id: str = ""
    # Gemini 3.x firma cada function_call y exige que la firma vuelva intacta en
    # el siguiente turno. Es opaca: no se inspecciona ni se serializa a la traza
    # (son bytes, romperian el json.dumps de loop.py). Va fuera de `args` a
    # proposito. Otros proveedores la dejan en None y la ignoran.
    firma: object = None


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
    """De la forma declarativa de agentes/tools.py a FunctionDeclaration de Gemini."""
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


def _contenidos_gemini(historial: list[dict], sin_firmas: bool = False):
    """historial neutro -> Content de Gemini.

    Cada entrada: {"rol": "usuario"|"modelo", "texto": str}
                  {"rol": "modelo", "llamadas": [Llamada]}
                  {"rol": "usuario", "resultados": [{"nombre":..., "salida": str}]}

    `sin_firmas` descarta los thought_signature: las firmas pertenecen al modelo
    que las emitio, asi que al caer a otro modelo de la cadena hay que soltarlas.
    """
    from google.genai import types
    out = []
    for m in historial:
        rol = "model" if m["rol"] == "modelo" else "user"
        partes = []
        if m.get("texto"):
            partes.append(types.Part(text=m["texto"]))
        for ll in m.get("llamadas") or []:
            fc = types.FunctionCall(name=ll.nombre, args=ll.args)
            firma = None if sin_firmas else getattr(ll, "firma", None)
            partes.append(types.Part(function_call=fc, thought_signature=firma)
                          if firma else types.Part(function_call=fc))
        for r in m.get("resultados") or []:
            partes.append(types.Part.from_function_response(
                name=r["nombre"], response={"resultado": r["salida"]}))
        if partes:
            out.append(types.Content(role=rol, parts=partes))
    return out


def _llamar_gemini(llave: Llave, modelo: str, system: str,
                   historial: list[dict], tools: list[dict], max_tokens: int,
                   sin_firmas: bool = False) -> Respuesta:
    from google.genai import types
    cliente = _cliente_gemini(llave.valor)
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        tools=_tools_gemini(tools) if tools else None,
        max_output_tokens=max_tokens,
        temperature=0.2,
    )
    r = cliente.models.generate_content(
        model=modelo, contents=_contenidos_gemini(historial, sin_firmas), config=cfg)

    textos, llamadas = [], []
    for cand in (r.candidates or []):
        for p in ((cand.content.parts if cand.content else None) or []):
            if getattr(p, "text", None):
                textos.append(p.text)
            fc = getattr(p, "function_call", None)
            if fc is not None and getattr(fc, "name", None):
                # la firma cuelga de la Part, no del FunctionCall
                llamadas.append(Llamada(nombre=fc.name, args=dict(fc.args or {}),
                                        id=fc.name,
                                        firma=getattr(p, "thought_signature", None)))
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
    al siguiente modelo. Una llave con cuota agotada se enfría lo que pida el
    proveedor; una llave inválida se inhabilita para el resto de la sesión.

    Si el pool entero quedó enfriando pero la primera en volver lo hace dentro de
    ESPERA_MAX_S, espera y reintenta: con una sola llave, rendirse ante un 429
    por minuto es peor que esperar unos segundos.
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

    esperado = 0.0
    while True:
        try:
            return _rondas(system, historial, tools, max_tokens, traza)
        except SinLlavesDisponibles:
            # nadie disponible: ¿vuelve alguna lo bastante pronto?
            vivas = [k for k in POOL if not k.inhabilitada]
            if not vivas:
                raise
            # el par (llave, modelo) que vuelve antes, no solo la llave
            falta = min(max(k.libre_desde, k.modelos_frios.get(m, 0.0))
                        for k in vivas for m in MODELOS) - time.time()
            if falta <= 0 or esperado + falta > ESPERA_MAX_S:
                raise
            esperado += falta
            if traza:
                traza.paso("llm", "espera",
                           f"pool enfriando, {falta:.0f}s (acumulado {esperado:.0f}s"
                           f"/{ESPERA_MAX_S}s)")
            else:
                print(f"  [llm] pool enfriando, esperando {falta:.0f}s...",
                      file=sys.stderr)
            time.sleep(falta)


def _rondas(system: str, historial: list[dict], tools: list[dict],
            max_tokens: int, traza) -> Respuesta:
    """Una pasada por la cadena de modelos x pool. La espera vive en generar()."""
    intentos, ultimo = 0, None
    # Una vez que un modelo rechaza las firmas, se sueltan para el resto de la
    # llamada: pertenecen al modelo que las emitio y no viajan entre modelos.
    sin_firmas = False
    for modelo in MODELOS:
        modelo_roto = False
        for llave in POOL:
            if not llave.modelo_disponible(modelo):
                continue
            intentos += 1
            try:
                llave.usos += 1
                r = _llamar_gemini(llave, modelo, system, historial, tools,
                                   max_tokens, sin_firmas)
                r.intentos = intentos
                return r
            except Exception as e:  # noqa: BLE001
                ultimo = e
                clase = _clasificar(e)
                if traza:
                    traza.paso("llm", "fallback",
                               f"{modelo} / {llave.etiqueta}: {clase} - {str(e)[:70]}")
                if clase == "firma" and not sin_firmas:
                    # reintenta ya mismo contra la misma llave, sin firmas
                    sin_firmas = True
                    intentos += 1
                    try:
                        r = _llamar_gemini(llave, modelo, system, historial, tools,
                                           max_tokens, True)
                        r.intentos = intentos
                        return r
                    except Exception as e2:  # noqa: BLE001
                        ultimo = e2
                        llave.enfriar(5, "firma")
                elif clase == "llave_muerta":
                    llave.matar(clase)
                elif clase == "cuota":
                    # solo este modelo: la llave sigue viva para el resto
                    llave.enfriar_modelo(modelo, _demora_sugerida(e) or COOLDOWN_S,
                                         clase)
                elif clase == "modelo_malo":
                    modelo_roto = True
                    break
                elif clase == "peticion_mala":
                    # rotar llaves no arregla un 400: aborta con el error crudo
                    raise PeticionMalFormada(
                        f"{modelo} rechazo la peticion (bug nuestro, no de la "
                        f"llave): {e}") from e
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
    except Exception as e:  # noqa: BLE001
        print(f"  ninguna llave sirvio: {e}")
        return 1
    if "--tools" not in sys.argv:
        print("\n(para probar el ida y vuelta con herramienta: python -m agentes.llm --tools\n"
              " cuesta 2 requests mas del primer modelo, y el cupo gratis es 20/dia)")
        return 0
    return _ping_tools()


def _ping_tools() -> int:
    """Ida y vuelta con herramienta: dos turnos, con el resultado devuelto.

    El ping de un solo turno no cubre esta ruta, y es donde vive la clase de bug
    de los thought_signature de Gemini 3.x: el 400 solo aparece en el turno 2,
    cuando el historial trae de vuelta un function_call.
    """
    print("\nprueba de ida y vuelta con herramienta (2 turnos):")
    tools = [{"name": "sumar", "description": "Suma dos enteros.",
              "input_schema": {"type": "object", "properties": {
                  "a": {"type": "integer", "description": "primer sumando"},
                  "b": {"type": "integer", "description": "segundo sumando"}},
                  "required": ["a", "b"]}}]
    hist = [{"rol": "usuario",
             "texto": "Cuanto es 2+2? Usa la herramienta sumar y luego dime el resultado."}]
    try:
        r1 = generar("Usa las herramientas disponibles.", hist, tools, 256)
        if not r1.llamadas:
            print(f"  [AVISO] el modelo no llamo la herramienta: {r1.texto[:60]!r}")
            print("          no se pudo cubrir el turno 2; revisalo con pruebas.prove --con-llm")
            return 0
        ll = r1.llamadas[0]
        firma = "con firma" if getattr(ll, "firma", None) else "sin firma"
        print(f"  turno 1: {ll.nombre}({ll.args}) [{firma}]")
        hist.append({"rol": "modelo", "texto": r1.texto, "llamadas": r1.llamadas})
        hist.append({"rol": "usuario", "resultados": [
            {"nombre": ll.nombre, "id": ll.id, "salida": '{"resultado": 4}'}]})
        r2 = generar("Usa las herramientas disponibles.", hist, tools, 256)
        print(f"  turno 2: OK -> {(r2.texto or '(sin texto)')[:60]!r}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  [FALLA] {_clasificar(e)}: {str(e)[:200]}")
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
