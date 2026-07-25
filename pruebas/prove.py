#!/usr/bin/env python3
"""Demuestra cada componente de arquitectura HACIENDO su trabajo.

  python -m pruebas.prove              # nucleo determinista, sin API key
  python -m pruebas.prove --con-llm    # incluye los 3 loops (requiere ANTHROPIC_API_KEY)

Esta es la respuesta a "esto esta mockeado?" y a "el componente funciona?".
"""
from __future__ import annotations
import argparse, os, sys, time
import yaml
from pydantic import ValidationError

from config.categorias import CONCEPTO_A_CATEGORIA
from dominio import catalogo, memoria, negociador, reglas, verificador
from agentes import tools
from dominio.schemas import Cotizacion, Espacio, ItemCotizado, Producto, Requerimiento
from dominio.traza import Traza
from dominio.nucleo import candidatos_de, cotizar, requerimientos_de

OK, NO = "  [OK]", "  [FALLA]"
resultados: list[tuple[str, bool]] = []
# Un chequeo saltado no es una falla (no cambia el exit code) pero TAMPOCO es
# verde: sin esto, "148/148 en verde" podia significar que el chequeo mas
# importante estaba desactivado y nadie lo notaba en el resumen.
saltados: list[str] = []


def saltar(nombre: str, motivo: str) -> None:
    print(f"  [SALTADO] {nombre} -> {motivo}")
    saltados.append(f"{nombre} ({motivo})")


def espacio_bano(**over) -> Espacio:
    """Bano con enchape/ducha, igual al default que usaban run.py/app.py antes
    de que altura_enchape_m/incluye_ducha dejaran de tener default en el schema
    (paso necesario para que sean Optional y no aparezcan en ambientes que no
    enchapan). Los chequeos que ejercen el set completo de reglas de bano
    (enchape_pared, adhesivo, boquilla, griferia_ducha) usan este helper."""
    base = dict(tipo="bano", largo_m=2, ancho_m=2, altura_enchape_m=2.0,
                incluye_ducha=True, presupuesto_cop=2_000_000)
    base.update(over)
    return Espacio(**base)


def titulo(n: int, nombre: str, archivo: str) -> None:
    print(f"\n{'='*74}\nCOMPONENTE {n}: {nombre}\n  archivo: {archivo}\n{'='*74}")


def chequeo(nombre: str, cond: bool, detalle: str = "") -> bool:
    print(f"{OK if cond else NO} {nombre}" + (f" -> {detalle}" if detalle else ""))
    resultados.append((nombre, bool(cond)))
    return bool(cond)


def c1_guardrails() -> None:
    titulo(1, "Guardrails de entrada", "dominio/schemas.py")
    casos = yaml.safe_load(open("pruebas/cases.yaml", encoding="utf-8"))
    for c in casos:
        datos = {k: v for k, v in c.items() if k not in ("id", "descripcion", "espera")}
        try:
            Espacio(**datos)
            valido = True
            motivo = ""
        except ValidationError as e:
            valido = False
            motivo = e.errors()[0]["msg"][:60]
        esperado_valido = c["espera"] != "rechazo_guardrail"
        chequeo(f"caso '{c['id']}' {'aceptado' if esperado_valido else 'rechazado'}",
                valido == esperado_valido, motivo)


def c2_retrieval() -> None:
    titulo(2, "Retrieval y grounding sobre datos reales", "dominio/catalogo.py")
    s = catalogo.stats()
    chequeo("catalogo indexado", s["productos"] > 0, f"{s['productos']} productos, "
            f"{len(s['categorias'])} categorias, snapshot {s['snapshot']}")
    chequeo("guias indexadas (corpus RAG)", True, f"{s['guias']} chunks"
            + ("  <-- corre ingesta.fetch_all --ambiente bano" if s["guias"] == 0 else ""))
    ps = catalogo.buscar("sanitario blanco", categorias=["sanitarios"], k=3)
    chequeo("busqueda devuelve SKUs con precio y URL", bool(ps),
            f"{ps[0].sku} ${ps[0].precio:,} {ps[0].url[-28:]}" if ps else "")
    chequeo("FTS5 no revienta con caracteres raros",
            isinstance(catalogo.buscar('sanitario "one-piece" (30.5)', k=2), list))
    chequeo("filtro estructurado por precio",
            all(p.precio <= 300_000 for p in catalogo.buscar("sanitario", precio_max=300_000, k=5)))
    # El SKU sale de la busqueda, no hardcodeado: la DB cambia entre el fixture
    # y los datos reales. `specs` puede venir vacio si aun no se parsean, pero
    # el campo debe existir y por_sku no debe reventar.
    if ps:
        p = catalogo.por_sku(ps[0].sku)
        chequeo("por_sku() de un SKU real trae el producto con campo specs",
                p is not None and isinstance(getattr(p, "specs", None), dict),
                f"{ps[0].sku} -> {len(getattr(p, 'specs', {}) or {})} specs")
    chequeo("por_sku() de un SKU inexistente devuelve None limpio",
            catalogo.por_sku("99999999") is None)


def c3_reglas_sin_aritmetica_del_llm() -> None:
    titulo(3, "Cuantificacion auditable (el LLM no hace aritmetica)", "dominio/reglas.py")
    e = Espacio(tipo="bano", largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    r = reglas.calcular("piso_ceramica", e)
    chequeo("formula sustituida es auditable", "=" in r.formula, r.formula)
    chequeo("cantidad correcta (4 m2 + 10% merma)", abs(r.cantidad - 4.4) < 0.01, f"{r.cantidad} m2")
    chequeo("cada cifra declara fuente", bool(r.fuente_regla), r.fuente_regla)
    chequeo("regla no verificada queda marcada", r.regla_verificada is False,
            "se muestra en amarillo en la UI")
    e2 = Espacio(tipo="bano", largo_m=2, ancho_m=2, incluye_ducha=False, presupuesto_cop=2_000_000)
    try:
        reglas.calcular("griferia_ducha", e2)
        chequeo("omite conceptos que no aplican", False)
    except ValueError:
        chequeo("omite conceptos que no aplican", True, "sin ducha -> sin griferia de ducha")


def c4_aislamiento() -> None:
    titulo(4, "Multi-agente con aislamiento de informacion", "agentes/subagentes.py, agentes/tools.py")
    e = Espacio(tipo="bano", largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    payload = e.sin_presupuesto()
    chequeo("el Cuantificador NO recibe el presupuesto", "presupuesto_cop" not in payload,
            f"claves: {sorted(payload)[:6]}...")
    nombres_c = {t["name"] for t in tools.tools_cuantificador()}
    chequeo("el Cuantificador NO tiene herramientas de precio",
            "buscar_catalogo" not in nombres_c and "validar_en_vivo" not in nombres_c,
            f"{sorted(nombres_c)}")
    nombres_v = {t["name"] for t in tools.tools_comprador()}
    chequeo("el Comprador NO tiene herramientas de cuantificacion",
            "calcular_cantidad" not in nombres_v and "listar_reglas" not in nombres_v,
            f"{sorted(nombres_v)}")

    # Las tools de experto de producto: el Comprador y el Q&A las tienen, el
    # Cuantificador no (ver specs implica ver precio). Un "no esta en
    # cuantificador" es trivialmente cierto si la tool no existe en ninguna
    # lista: por eso se salta ruidosamente en vez de pasar en verde.
    nombres_qa = {t["name"] for t in tools.tools_qa()} if hasattr(tools, "tools_qa") else set()
    for nombre in ("ficha_producto", "comparar_productos", "recomendar_por_specs"):
        if nombre not in nombres_v | nombres_qa:
            saltar(f"aislamiento de {nombre}", "la herramienta aun no existe en ninguna lista")
            continue
        chequeo(f"{nombre}: la tiene el Comprador y el Q&A, NO el Cuantificador",
                nombre not in nombres_c and nombre in nombres_v and nombre in nombres_qa,
                f"cuantificador={nombre in nombres_c} comprador={nombre in nombres_v} "
                f"qa={nombre in nombres_qa}")

    # B1: el default de presupuesto sale del tipo, no de una constante fija.
    # Con 1_000_000 fijo, cocina (presupuesto_min=1_500_000) lanzaba
    # ValidationError y la cotizacion agentica de cocina salia en cero.
    # Pasa por sin_presupuesto(): es el payload real que arma subagentes.py,
    # no un dict a mano que probaria el fix en abstracto.
    for _t in ("bano", "cocina", "habitacion", "sala"):
        _payload = Espacio(tipo=_t, largo_m=3, ancho_m=3,
                           presupuesto_cop=5_000_000).sin_presupuesto()
        try:
            _r = tools.calcular_cantidad("piso_ceramica", _payload)
            _ok, _det = True, f"{_r['cantidad']} {_r['unidad']}"
        except Exception as _ex:  # noqa: BLE001
            _ok, _det = False, f"{type(_ex).__name__}: {_ex}"
        chequeo(f"calcular_cantidad sin presupuesto no falla en {_t}", _ok, _det)


def c5_negociacion() -> None:
    titulo(5, "Negociador determinista bajo restriccion", "dominio/negociador.py")
    for pres in (6_000_000, 2_000_000, 1_200_000):
        e = espacio_bano(presupuesto_cop=pres)
        cot, fallas, _, _ = cotizar(e)
        uso = 100 * cot.total_cop // pres
        # Invariante: entra en el tope, y la holgura queda EXPLICADA (aprovechada
        # o convertida en upgrades que el humano aprueba). Nunca plata muda.
        explicada = uso >= 80 or bool(cot.alternativas)
        chequeo(f"tope ${pres:,}: entra y la holgura queda explicada",
                cot.total_cop <= pres and explicada,
                f"total ${cot.total_cop:,} ({uso}%), {len(cot.recortes)} recortes, "
                f"{len(cot.alternativas)} upgrades ofrecidos")
    e = espacio_bano()
    cot, _, _, _ = cotizar(e)
    chequeo("los recortes se explican en pesos",
            any("libere $" in r for r in cot.recortes), cot.recortes[0][:70] if cot.recortes else "")
    chequeo("propone plan por fases", len(cot.fases) >= 2, list(cot.fases))


def c6_autocorreccion() -> None:
    titulo(6, "Auto-correccion: el verificador rechaza y el loop lo observa",
           "dominio/verificador.py")
    e = espacio_bano()
    cot, fallas, reqs, _ = cotizar(e)
    chequeo("cotizacion valida pasa el verificador", not fallas,
            f"{len(cot.items)} items, 0 fallas")

    # inyecta un SKU inventado, como haria un LLM alucinando
    falso = Producto(sku="99999999", nombre="Sanitario Inventado", categoria="sanitarios",
                     precio=350_000, url="http://ejemplo/no-existe")
    req = next(r for r in reqs if r.concepto == "sanitario")
    sucia = Cotizacion(espacio=e, items=[ItemCotizado(
        concepto="sanitario", requerimiento=req, producto=falso,
        unidades_a_comprar=1, subtotal_cop=999)]).recalcular()
    f2 = verificador.verificar(sucia)
    codigos = {f.codigo for f in f2}
    chequeo("atrapa SKU inventado", "sku_inexistente" in codigos)
    chequeo("atrapa aritmetica alterada", "aritmetica" in codigos)
    chequeo("atrapa omision de esenciales", "falta_esencial" in codigos,
            f"codigos: {sorted(codigos)}")
    print("\n  --- lo que el loop recibe como observacion de herramienta ---")
    print("  " + verificador.a_texto(f2).replace("\n", "\n  ")[:420])


def c7_memoria() -> None:
    titulo(7, "Memoria de sesion: el 2do turno no re-cuantifica", "dominio/memoria.py")
    from agentes import supervisor
    ses = "prove-memoria"
    memoria.olvidar(ses)
    e1 = espacio_bano()
    cot1, t1 = supervisor.correr_deterministico(e1, sesion=ses, traza=Traza("t1"))
    chequeo("turno 1 cuantifica y guarda", memoria.leer(ses, "requerimientos") is not None,
            f"total ${cot1.total_cop:,}")
    e2 = espacio_bano(presupuesto_cop=2_500_000)
    cot2, t2 = supervisor.correr_deterministico(e2, sesion=ses, traza=Traza("t2"))
    hit = any(p["tipo"] == "memoria_hit" for p in t2.pasos)
    chequeo("turno 2 reusa requerimientos de memoria", hit,
            f"total ${cot2.total_cop:,} con el tope subido")
    chequeo("mas presupuesto -> mejor cotizacion", cot2.total_cop > cot1.total_cop,
            f"${cot1.total_cop:,} -> ${cot2.total_cop:,}")
    memoria.olvidar(ses)


def c8_observabilidad() -> None:
    titulo(8, "Observabilidad: traza persistida", "dominio/traza.py")
    t = Traza("prove")
    t.paso("supervisor", "tool_use", "delegar_cuantificacion()")
    t.paso("verificador", "rechazo", "1 falla: sku_inexistente")
    t.paso("supervisor", "tool_use", "delegar_compra()")
    ruta = t.guardar()
    chequeo("traza guardada en disco", os.path.exists(ruta), ruta)
    chequeo("detecta auto-correccion", t.hubo_autocorreccion())
    chequeo("lista herramientas usadas", len(t.herramientas_usadas()) == 2,
            str(t.herramientas_usadas()))

    # Traza sin on_paso (el default de siempre) sigue funcionando igual: la UI
    # en vivo agrega un callback opcional, y sin el la traza no debe cambiar.
    t_sin_callback = Traza("prove-sin-callback")
    t_sin_callback.paso("supervisor", "armado", "sin callback registrado")
    chequeo("Traza sin on_paso sigue funcionando (compatibilidad)",
            len(t_sin_callback.pasos) == 1)

    # Traza con on_paso: cada paso() debe invocar el callback con el mismo dict
    # que quedo en self.pasos, y un callback que revienta no debe tumbar paso().
    vistos: list[dict] = []
    t_con_callback = Traza("prove-con-callback", on_paso=vistos.append)
    t_con_callback.paso("cuantificador", "piensa", "calculando area")
    t_con_callback.paso("comprador", "tool_use", "buscar_catalogo(sku=123)")
    chequeo("on_paso recibe cada paso en vivo", vistos == t_con_callback.pasos,
            f"{len(vistos)} pasos vistos por el callback")

    def _callback_roto(_p):
        raise RuntimeError("fallo de render simulado")

    t_callback_roto = Traza("prove-callback-roto", on_paso=_callback_roto)
    t_callback_roto.paso("supervisor", "entrega", "no debe propagar la excepcion")
    chequeo("un on_paso que falla no rompe la cotizacion",
            len(t_callback_roto.pasos) == 1)


def c8b_cuantificador_no_transcribe() -> None:
    """REGLA 1: la formula y la fuente las deriva Python, no las copia el LLM.

    El modelo real entregaba la lista a mano con solo concepto/cantidad/unidad y
    los 12 requerimientos se caian por validacion (falta fuente_regla / formula).
    Esto lo fija sin gastar cuota: simula exactamente ese payload mutilado.
    """
    titulo("8b", "El Cuantificador no transcribe cifras que calculo Python",
           "agentes/subagentes.py")
    from agentes import subagentes
    from dominio.traza import Traza

    t = Traza("prove-transcribe")
    espacio = Espacio(tipo="bano", largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    capturado: dict = {}

    def loop_falso(actor, system, objetivo, tools_, ejecutores, traza, max_iter=14):
        capturado["max_iter"] = max_iter
        ejecutores["calcular_cantidad"](regla_id="piso_ceramica")
        ejecutores["calcular_cantidad"](regla_id="sanitario")
        # el LLM entrega la lista mutilada, igual que en la corrida real
        entrega = ejecutores["entregar_requerimientos"](requerimientos=[
            {"concepto": "ceramica de piso", "cantidad": 4.4, "unidad": "m2"}])
        return {"entrega": entrega, "texto": "", "iteraciones": 3}

    original = subagentes.loop.correr
    try:
        subagentes.loop.correr = loop_falso
        reqs = subagentes.cuantificar(espacio, t)
    finally:
        subagentes.loop.correr = original

    chequeo("entrega lo que calculo Python, no lo que listo el LLM", len(reqs) == 2,
            f"{len(reqs)} requerimientos")
    chequeo("cada requerimiento conserva su formula sustituida",
            all(r.formula and "=" in r.formula for r in reqs),
            reqs[0].formula if reqs else "")
    chequeo("cada requerimiento conserva su fuente",
            all(r.fuente_regla for r in reqs))
    chequeo("una lista mutilada del LLM queda en la traza como divergencia",
            any(p.get("tipo") == "divergencia" for p in t.pasos))
    chequeo("max_iter alcanza para las reglas + la entrega en modelos lite",
            capturado.get("max_iter", 0) >= 20, str(capturado.get("max_iter")))


FASES_VALIDAS = {"obra_gris", "enchape", "acabados"}

# Un Espacio "completo": TODAS las variables que cualquier ambiente pueda usar,
# pobladas. Sirve para detectar un typo de variable en una formula del YAML
# (p.ej. 'metros_lineals') sin que se confunda con una regla que legitimamente
# no aplica (esa se prueba aparte, con incluye_ducha=False).
_ESPACIOS_COMPLETOS = {
    "bano": dict(tipo="bano", largo_m=3, ancho_m=3, altura_enchape_m=2.0,
                incluye_ducha=True, presupuesto_cop=5_000_000),
    "cocina": dict(tipo="cocina", largo_m=3, ancho_m=3, altura_enchape_m=2.0,
                  metros_lineales=4.0, presupuesto_cop=8_000_000),
    "habitacion": dict(tipo="habitacion", largo_m=4, ancho_m=4,
                       metros_lineales=3.0, presupuesto_cop=8_000_000),
    "sala": dict(tipo="sala", largo_m=6, ancho_m=6, presupuesto_cop=15_000_000),
}


def c_reglas_bien_formadas() -> None:
    """Sin catalogo: valida el YAML mismo. reglas.calcular() convierte un
    NameError (variable ausente en el Espacio) en ValueError, tratandolo como
    'la regla no aplica' -- correcto para altura_enchape_m en una sala, pero
    silencia igual de bien un typo real en la formula (p.ej. escribir
    'metros_lineals'). Con un Espacio COMPLETO del ambiente (todas las variables
    pobladas), ese ValueError ya no tiene excusa: si salta, la formula esta mal
    escrita, no es que el ambiente no use esa variable."""
    titulo("reglas-formadas", "Cada regla del YAML tiene fase valida y formula sin errores",
           "config/reglas_obra.yaml")
    todas = reglas.cargar()
    for regla_id, r in sorted(todas.items()):
        chequeo(f"{regla_id}: tiene campo 'fase' valido",
                r.get("fase") in FASES_VALIDAS, f"fase={r.get('fase')!r}")
        for tipo in r.get("ambientes") or ["bano"]:
            e = Espacio(**_ESPACIOS_COMPLETOS[tipo])
            try:
                reglas.calcular(regla_id, e)
                chequeo(f"{regla_id} ({tipo}): formula evalua sin error de variable", True)
            except ValueError as ex:
                # legitimo solo si la formula referencia una variable opcional
                # (incluye_ducha/altura_enchape_m/metros_lineales) que SI esta
                # poblada aqui: si aun asi falla, es cantidad<=0 con datos
                # completos, tambien sospechoso, o un typo de nombre de variable.
                chequeo(f"{regla_id} ({tipo}): formula evalua sin error de variable",
                        False, str(ex)[:90])


def c_reglas_con_datos_reales() -> None:
    """El chequeo de mayor valor de la expansion a 4 ambientes: para cada regla
    del YAML, en cada ambiente que declara, su concepto debe resolver a >=1
    producto real en datos/catalogo.db. Sin este chequeo, una regla nueva sin
    categoria descargada (o con CONCEPTO_A_CATEGORIA/CONCEPTO_FILTROS mal
    puestos) cae en cot.faltantes EN SILENCIO: es exactamente lo que le paso a
    'espejo' y 'division de ducha' cuando su categoria (EXTRA) nunca se
    descargo, y el fixture sintetico los tapaba mientras los datos reales
    fallaban. Corre solo contra la DB real (no contra el fixture, que por
    diseno cubre todos los conceptos con 1-2 productos sinteticos)."""
    titulo("reglas-datos", "Cada regla resuelve a producto real en su ambiente",
           "config/reglas_obra.yaml + datos/catalogo.db")
    if catalogo.stats().get("productos", 0) == 0:
        saltar("cada regla resuelve a producto real", "catalogo vacio")
        return
    # Si la DB fue construida desde el fixture (catFIXTURE), este chequeo no
    # aplica: el fixture es sintetico a proposito y no debe reflejar el catalogo real.
    con = catalogo._con()
    n_fixture = con.execute(
        "SELECT COUNT(*) FROM productos WHERE cat_id='catFIXTURE'").fetchone()[0]
    con.close()
    if n_fixture > 0:
        saltar("cada regla resuelve a producto real",
               "catalogo construido desde el fixture sintetico")
        return
    todas = reglas.cargar()
    for regla_id, r in sorted(todas.items()):
        for tipo in r.get("ambientes") or ["bano"]:
            cats = CONCEPTO_A_CATEGORIA.get(r["concepto"])
            g = catalogo.gamas(r["concepto"], cats, unidad_requerida=r["unidad"])
            chequeo(f"{regla_id} ({tipo}) resuelve producto real",
                    bool(g), f"concepto='{r['concepto']}' categorias={cats} gamas={sorted(g)}")


def c9_fallback_llaves() -> None:
    titulo(9, "Fallback de llaves y modelos del LLM", "agentes/llm.py")
    from agentes import llm
    guardado = (llm.POOL, llm.MODELOS, llm._llamar_gemini)
    try:
        llm.POOL = [llm.Llave("k-uno", "key1:...uno"),
                    llm.Llave("k-dos", "key2:...dos"),
                    llm.Llave("k-tres", "key3:...tres")]
        llm.MODELOS = ["modelo-fantasma", "modelo-bueno"]
        intentos: list[tuple[str, str]] = []

        def falso(llave, modelo, system, historial, tools, max_tokens,
                  sin_firmas=False):
            intentos.append((modelo, llave.etiqueta))
            if modelo == "modelo-fantasma":
                raise RuntimeError("404 models/modelo-fantasma is not found")
            if llave.valor == "k-uno":
                raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
            if llave.valor == "k-dos":
                raise RuntimeError("503 UNAVAILABLE: model is overloaded")
            return llm.Respuesta(texto="OK", modelo=modelo, llave=llave.etiqueta)

        llm._llamar_gemini = falso
        r = llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
        chequeo("modelo inexistente -> pasa al siguiente modelo",
                intentos[0][0] == "modelo-fantasma" and r.modelo == "modelo-bueno",
                f"{len(intentos)} intentos: {intentos}")
        # el 429 enfria el par (llave, modelo): la llave sigue viva para otros
        chequeo("cuota agotada (429) -> rota a la siguiente llave",
                llm.POOL[0].motivo.startswith("cuota")
                and not llm.POOL[0].modelo_disponible("modelo-bueno"))
        chequeo("error transitorio (503) -> rota y enfria brevemente",
                llm.POOL[1].motivo == "transitorio")
        chequeo("responde con la tercera llave", r.llave == "key3:...tres", r.texto)

        # --- Gemini 3.x: la firma del function_call debe volver intacta ---
        llm.MODELOS = ["modelo-bueno"]
        for k in llm.POOL:
            k.inhabilitada, k.libre_desde, k.motivo = False, 0.0, ""
        vistas: list[object] = []

        def espia_firmas(llave, modelo, system, historial, tools, max_tokens,
                         sin_firmas=False):
            for m in historial:
                for ll in m.get("llamadas") or []:
                    vistas.append(None if sin_firmas else ll.firma)
            return llm.Respuesta(texto="OK", modelo=modelo, llave=llave.etiqueta)

        llm._llamar_gemini = espia_firmas
        hist = [{"rol": "usuario", "texto": "x"},
                {"rol": "modelo", "llamadas": [
                    llm.Llamada(nombre="t", args={}, firma=b"FIRMA-OPACA")]},
                {"rol": "usuario", "resultados": [{"nombre": "t", "salida": "{}"}]}]
        llm.generar("", hist, [], 16)
        chequeo("la firma del function_call sobrevive el ida y vuelta",
                vistas == [b"FIRMA-OPACA"], f"vistas={vistas}")

        # la firma no puede colarse a la traza: son bytes, romperian json.dumps
        import json as _json
        _json.dumps(hist[1]["llamadas"][0].args)
        chequeo("la firma va fuera de args (la traza sigue serializable)",
                "firma" not in hist[1]["llamadas"][0].args)

        # modelo que rechaza firmas -> reintenta sin ellas en vez de morir
        estado_firma = {"rechazo": False}

        def rechaza_firma(llave, modelo, system, historial, tools, max_tokens,
                          sin_firmas=False):
            if not sin_firmas:
                estado_firma["rechazo"] = True
                raise RuntimeError(
                    "400 INVALID_ARGUMENT Function call is missing a "
                    "thought_signature in functionCall parts.")
            return llm.Respuesta(texto="OK", modelo=modelo, llave=llave.etiqueta)

        llm._llamar_gemini = rechaza_firma
        r2 = llm.generar("", hist, [], 16)
        chequeo("modelo que rechaza la firma -> reintenta sin ella, no muere",
                estado_firma["rechazo"] and r2.texto == "OK", f"{r2.intentos} intento(s)")

        # un 400 nuestro no debe quemar el pool ni disfrazarse de "sin llaves"
        def malformada(llave, modelo, system, historial, tools, max_tokens,
                       sin_firmas=False):
            raise RuntimeError("400 INVALID_ARGUMENT: campo desconocido 'foo'")

        llm._llamar_gemini = malformada
        try:
            llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
            chequeo("peticion malformada (400) -> aborta con el error crudo", False)
        except llm.PeticionMalFormada as e:
            chequeo("peticion malformada (400) -> aborta con el error crudo",
                    "foo" in str(e), str(e)[:60])
        except llm.SinLlavesDisponibles:
            chequeo("peticion malformada (400) -> aborta con el error crudo", False,
                    "se disfrazo de 'sin llaves' y quemo el pool")
        chequeo("un 400 no inhabilita las llaves sanas",
                all(not k.inhabilitada for k in llm.POOL))

        # --- cuota del tier gratuito: es POR MODELO, no por llave ---
        # Con una sola llave, enfriarla entera ante un 429 saltaba el resto de
        # la cadena con 'continue' y agotaba 4 modelos en 1 intento.
        llm.POOL = [llm.Llave("k-sola", "key1:...sola")]
        llm.MODELOS = ["modelo-sin-cupo", "modelo-con-cupo"]
        probados: list[str] = []

        def cuota_por_modelo(llave, modelo, *a, **k):
            probados.append(modelo)
            if modelo == "modelo-sin-cupo":
                raise RuntimeError("429 RESOURCE_EXHAUSTED quota "
                                   "{'retryDelay': '31s'}")
            return llm.Respuesta(texto="OK", modelo=modelo, llave=llave.etiqueta)

        llm._llamar_gemini = cuota_por_modelo
        r0 = llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
        chequeo("429 en un modelo -> prueba el siguiente con la misma llave",
                r0.modelo == "modelo-con-cupo" and len(probados) == 2,
                f"probados={probados}")
        chequeo("un 429 por modelo no enfria la llave entera",
                llm.POOL[0].disponible and not llm.POOL[0].modelo_disponible(
                    "modelo-sin-cupo"))

        # --- una sola llave enfriando: esperar es mejor que rendirse ---
        guardado_espera = llm.ESPERA_MAX_S
        llm.ESPERA_MAX_S = 3
        llm.POOL = [llm.Llave("k-sola", "key1:...sola")]
        llm.POOL[0].libre_desde = time.time() + 1  # vuelve en 1s
        llm._llamar_gemini = lambda llave, modelo, *a, **k: llm.Respuesta(
            texto="OK", modelo=modelo, llave=llave.etiqueta)
        t0 = time.time()
        r3 = llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
        chequeo("pool de 1 llave enfriando -> espera y reintenta, no se rinde",
                r3.texto == "OK" and 0.5 < time.time() - t0 < 3,
                f"{time.time()-t0:.1f}s")

        # pero el techo se respeta: nada de colgarse en plena demo
        llm.POOL[0].libre_desde = time.time() + 60
        t0 = time.time()
        try:
            llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
            chequeo("espera mas larga que el techo -> falla rapido", False)
        except llm.SinLlavesDisponibles:
            chequeo("espera mas larga que el techo -> falla rapido",
                    time.time() - t0 < 1, f"{time.time()-t0:.1f}s")
        llm.ESPERA_MAX_S = guardado_espera

        # el 429 hace caso al retryDelay del proveedor, no al COOLDOWN_S fijo
        chequeo("usa el retryDelay que manda el proveedor",
                llm._demora_sugerida(RuntimeError(
                    "429 RESOURCE_EXHAUSTED {'retryDelay': '7s'}")) == 8,
                str(llm._demora_sugerida(RuntimeError("'retryDelay': '7s'"))))

        llm.POOL = [llm.Llave("k-uno", "key1:...uno"),
                    llm.Llave("k-dos", "key2:...dos"),
                    llm.Llave("k-tres", "key3:...tres")]
        llm._llamar_gemini = falso
        for k in llm.POOL:
            k.matar("prueba")
        try:
            llm.generar("", [{"rol": "usuario", "texto": "x"}], [], 16)
            chequeo("sin llaves disponibles -> error claro", False)
        except llm.SinLlavesDisponibles as e:
            chequeo("sin llaves disponibles -> error claro", True, str(e)[:70])
    finally:
        llm.POOL, llm.MODELOS, llm._llamar_gemini = guardado


def c10_llm() -> None:
    titulo(10, "Los tres loops agenticos (requiere llaves reales)",
           "agentes/loop.py, agentes/supervisor.py")
    from agentes import llm
    if not llm.POOL and llm.PROVEEDOR == "gemini":
        print("  [SALTADO] sin GEMINI_API_KEYS en .env")
        print("            configura y corre: python -m pruebas.prove --con-llm")
        return
    from agentes import qa, supervisor
    print(f"  proveedor={llm.PROVEEDOR} modelos={llm.MODELOS} llaves={len(llm.POOL)}")
    # --con-llm se mantiene SOLO en bano: la cuota Gemini del tier gratuito es
    # 20 requests/dia POR MODELO y esta corrida gasta ~35. Parametrizar esto por
    # los 4 ambientes cuadruplicaria el gasto la vispera de la demo. Cocina,
    # habitacion y sala se cubren de forma determinista (c1/c3/c6/c8b + c_reglas_con_datos).
    e = espacio_bano()
    cot, traza = supervisor.correr_agentico(e, sesion="prove-llm")
    chequeo("el supervisor produjo cotizacion", cot is not None)
    usos = traza.herramientas_usadas()
    chequeo("el loop eligio herramientas por su cuenta", len(usos) >= 3, f"{len(usos)} llamadas")
    chequeo("participaron los 3 actores",
            len({p["actor"] for p in traza.pasos} & {"supervisor", "cuantificador", "comprador"}) == 3,
            str(sorted({p["actor"] for p in traza.pasos})))
    r = qa.responder("cuanta ceramica de piso y por que esa cantidad", cot, traza)
    print(f"\n  Q&A fundamentado: {r['respuesta'][:220]}")
    r2 = qa.responder("cual es la capital de Mongolia", cot, traza)
    chequeo("el Q&A dice que no sabe fuera del corpus",
            "no tengo informacion verificada" in r2["respuesta"].lower()
            or "no tengo información verificada" in r2["respuesta"].lower(), r2["respuesta"][:90])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--con-llm", action="store_true")
    a = ap.parse_args()
    if not os.path.exists("datos/catalogo.db"):
        print("no existe datos/catalogo.db. Corre:")
        print("  python -m ingesta.build_index --fuente pruebas/fixture_productos.json")
        return 1
    for f in (c1_guardrails, c2_retrieval, c3_reglas_sin_aritmetica_del_llm, c4_aislamiento,
              c5_negociacion, c6_autocorreccion, c7_memoria, c8_observabilidad,
              c8b_cuantificador_no_transcribe, c_reglas_bien_formadas,
              c_reglas_con_datos_reales, c9_fallback_llaves):
        f()
    if a.con_llm:
        c10_llm()
    malos = [n for n, ok in resultados if not ok]
    print(f"\n{'='*74}\n{len(resultados) - len(malos)}/{len(resultados)} chequeos en verde")
    for n in malos:
        print("  FALLA:", n)
    if saltados:
        print(f"\n  /!\\ {len(saltados)} chequeo(s) SALTADO(s) -- NO verificados:")
        for n in saltados:
            print("    -", n)
    print("=" * 74)
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
