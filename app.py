"""UI de demo. Sin diseno complejo a proposito: la traza en vivo del loop de
agentes vale mas puntos que el CSS.

  streamlit run app.py
"""
from __future__ import annotations
import streamlit as st

from config.categorias import CONCEPTO_A_CATEGORIA
from dominio import catalogo, memoria, negociador, verificador
from dominio.schemas import LIMITES
from dominio.traza import Traza
from agentes import qa, tools
from agentes.ejecutar import construir_espacio, cotizar


@st.cache_data(show_spinner=False)
def _opciones_swap(concepto: str, unidad: str) -> list:
    """Alternativas para el selectbox de swap manual. Cacheado: sin esto,
    cada rerun (p.ej. al abrir OTRO expander) volveria a golpear la BD para
    los 200 candidatos de este concepto."""
    cats = CONCEPTO_A_CATEGORIA.get(concepto)
    return catalogo.opciones(concepto, categorias=cats, unidad_requerida=unidad)

TITULOS = {"bano": "Baño", "cocina": "Cocina", "habitacion": "Habitación", "sala": "Sala"}

# Icono + etiqueta legible para cada tipo de paso que puede aparecer en una
# Traza. Las claves son las que emiten agentes/loop.py, supervisor.py,
# subagentes.py y llm.py (ASCII, son identificadores internos) - solo los
# VALORES son texto de presentacion.
PASO_INFO = {
    "piensa":                 ("💭", "Pensando"),
    "llm":                    ("🧠", "Consultando al modelo"),
    "tool_use":                ("🔧", "Usando una herramienta"),
    "error_tool":              ("⚠️", "Error en la herramienta, reintentando"),
    "limite":                  ("⏱️", "Límite de iteraciones alcanzado"),
    "armado":                  ("📋", "Armando la cotización"),
    "rechazo":                 ("❌", "Rechazada, corrigiendo"),
    "aprobacion":              ("✅", "Aprobada"),
    "memoria_hit":             ("💾", "Reusando resultado de la sesión"),
    "entrega":                 ("📦", "Entrega al Supervisor"),
    "descartado":              ("🗑️", "Descartado"),
    "divergencia":             ("🔀", "El modelo se desvió, corregido"),
    "sku_inventado":           ("🚫", "SKU inventado, descartado"),
    "relleno_deterministico":  ("🔩", "Completado por reglas, sin LLM"),
    "espera":                  ("⏳", "Esperando cupo de la API"),
    "fallback":                ("🔁", "Cambiando de modelo o de llave"),
}
NOMBRES_ACTOR = {
    "supervisor": "Supervisor", "cuantificador": "Cuantificador",
    "comprador": "Comprador", "negociador": "Negociador",
    "verificador": "Verificador", "ui": "Sistema", "sistema": "Sistema", "qa": "Preguntas",
}


def _esc(s) -> str:
    """Streamlit >=1.30 lee $...$ como LaTeX (KaTeX): con dos o mas '$' en un
    mismo string, todo lo que hay entre el primero y el segundo se renderiza
    como formula. Escapar SOLO aqui, en la capa de presentacion: negociador.py
    re-parsea `alternativas` con una regex sobre el '$' crudo, asi que escapar
    en origen la rompe."""
    return str(s).replace("$", "\\$")


def _fila_paso(p: dict) -> str:
    icono, etiqueta = PASO_INFO.get(p["tipo"], ("•", p["tipo"]))
    actor = NOMBRES_ACTOR.get(p["actor"], p["actor"])
    linea = f"{icono} `{p['t']:6.2f}s` **{actor}** — {etiqueta}"
    if p["detalle"]:
        linea += f"  \n&nbsp;&nbsp;&nbsp;&nbsp;_{_esc(p['detalle'][:120])}_"
    return linea


st.set_page_config(page_title="Cotizador de remodelación - Homecenter", layout="wide")
st.title("Asistente de remodelación")

s = catalogo.stats()
st.caption(f"Catálogo: {s['productos']} productos · {s['guias']} fragmentos de guía · "
           f"snapshot {s['snapshot']} · precios y disponibilidad para Medellín")

with st.sidebar:
    st.header("El espacio")
    tipo = st.selectbox("Ambiente", ["bano", "cocina", "habitacion", "sala"],
                        format_func=lambda t: TITULOS[t])
    limites = LIMITES[tipo]
    lado_max = float(limites["lado_max"])
    largo = st.number_input("Largo (m)", 0.8, lado_max, min(2.0, lado_max), 0.1)
    ancho = st.number_input("Ancho (m)", 0.8, lado_max, min(2.0, lado_max), 0.1)

    enchape = None
    ducha = None
    metros_lineales = None
    if tipo in ("bano", "cocina"):
        enchape = st.number_input("Altura de enchape (m)", 0.5, 3.0, 2.0, 0.1)
    if tipo == "bano":
        ducha = st.checkbox("Tiene ducha", True)
    if tipo in ("cocina", "habitacion"):
        etiqueta = "Mesón de cocina (ml)" if tipo == "cocina" else "Clóset corrido (ml)"
        metros_lineales = st.number_input(etiqueta, 0.5, 15.0, 3.0, 0.5)

    # "Deshacer: subir el tope" (mas abajo) no puede escribir directo en
    # session_state["presupuesto"]: el widget con key="presupuesto" ya se
    # instancio aqui mismo, y Streamlit revienta si se asigna a la key de un
    # widget ya instanciado en el mismo run. Se deja una sugerencia en una key
    # aparte y se lee como `value=` AQUI, en el rerun siguiente.
    _sugerido = st.session_state.pop("tope_sugerido", None)
    presupuesto = st.number_input("Presupuesto (COP)", int(limites["presupuesto_min"]),
                                  200_000_000,
                                  _sugerido or max(2_000_000, int(limites["presupuesto_min"])),
                                  100_000, key="presupuesto")
    modo = st.radio("Modo", ["Con agentes IA", "Rápido (sin IA, respaldo de demo)"], index=0)
    sesion = st.text_input("Sesión", "demo")
    if st.button("Cotizar", type="primary", use_container_width=True):
        st.session_state.pop("cot", None)
        st.session_state["ejecutar"] = True
    if st.button("Olvidar sesión", use_container_width=True):
        memoria.olvidar(sesion)
        st.session_state.clear()
        st.rerun()
    from agentes import llm as _llm
    _est = _llm.estado()
    if _est["proveedor"] != "gemini":
        st.caption(f"proveedor: {_est['proveedor']}")
    elif not _est["llaves"]:
        st.warning("Sin llaves de LLM configuradas: solo funciona el modo rápido. "
                   "Pon GEMINI_API_KEYS en .env")
    else:
        st.caption(f"{_est['disponibles']}/{_est['llaves']} llaves disponibles · "
                   f"{len(_est['modelos'])} modelos en cadena")

izq, der = st.columns([3, 2])

with der:
    st.subheader("Cómo trabajan los agentes")
    progreso = st.container(height=420, border=True)
    with progreso:
        st.caption("Corre una cotización para ver el proceso en vivo.")

if st.session_state.pop("ejecutar", False):
    espacio, errores = construir_espacio(
        tipo=tipo, largo_m=largo, ancho_m=ancho, presupuesto_cop=int(presupuesto),
        altura_enchape_m=enchape, incluye_ducha=ducha, metros_lineales=metros_lineales)
    if espacio is None:
        st.error("Estos datos no son válidos:")
        for msg in errores:
            st.write("-", msg)
        st.stop()

    lineas_vistas: list[str] = []

    def _mostrar(p: dict) -> None:
        lineas_vistas.append(_fila_paso(p))
        with progreso:
            progreso.empty()
            for linea in lineas_vistas:
                st.markdown(linea)

    traza = Traza("ui", on_paso=_mostrar)
    with st.spinner("Cotizando..."):
        cot, traza = cotizar(espacio, sesion=sesion,
                             deterministico=modo.startswith("Rápido"), traza=traza)
    st.session_state["cot"] = cot
    st.session_state["traza"] = traza

cot = st.session_state.get("cot")
traza = st.session_state.get("traza")

with der:
    if traza:
        st.divider()
        st.caption(f"{len(traza.pasos)} pasos · {traza.resumen()['segundos']}s"
                   + (" · hubo auto-corrección" if traza.hubo_autocorreccion() else ""))
        with st.expander("Ver traza completa"):
            for p in traza.pasos:
                st.markdown(_fila_paso(p))

# Fuera de `with izq:` y ANTES del st.stop() de abajo: preguntar por specs o
# comparar dos SKU es una capacidad independiente de la cotizacion. El
# st.form evita que un rerun de Streamlit (cualquier otro widget) vuelva a
# disparar qa.responder() y queme cuota de LLM sin pregunta nueva.
with izq:
    st.subheader("Pregunta lo que quieras")
    st.caption("Funciona sin cotizar: puedes preguntar por specs de un SKU o "
               "comparar dos productos.")
    with st.form("form_qa"):
        q = st.text_input("Escribe tu pregunta sobre la cotización o sobre un producto")
        enviado = st.form_submit_button("Preguntar")
    if enviado and q:
        with st.spinner("Consultando fuentes..."):
            # Traza propia: la de la cotizacion mezclaria tools del
            # supervisor/comprador en "Herramientas usadas" de esta pregunta.
            st.session_state["respuesta_qa"] = qa.responder(q, cot, Traza("qa"), tipo_defecto=tipo)
    r = st.session_state.get("respuesta_qa")
    if r:
        st.write(_esc(r["respuesta"]))
        st.caption("Herramientas usadas: " + ", ".join(r["herramientas"][-4:]))
    st.divider()

with izq:
    if not cot:
        st.info("Define el espacio y el presupuesto en la barra lateral.")
        st.stop()

    a, b, c = st.columns(3)
    a.metric("Total", f"${cot.total_cop:,}")
    b.metric("Tope", f"${cot.espacio.presupuesto_cop:,}")
    c.metric("Holgura", f"${cot.holgura_cop:,}")

    fallas = verificador.verificar(cot)
    if fallas:
        st.error(f"El verificador encontró {len(fallas)} fallas")
        for f in fallas[:6]:
            st.write(f"- `{f.codigo}` {f.concepto}: {_esc(f.mensaje)}")
    else:
        st.success("Verificador: cotización aprobada")

    # Conceptos que ya aparecen en cot.recortes: los upgrades de esos mismos
    # conceptos en cot.alternativas serian "deshacer el corte que acabo de
    # hacer" presentado como si fuera algo nuevo. Se fusionan en una sola
    # narrativa mas abajo en vez de mostrarse como dos secciones que se
    # contradicen.
    # Fragil a proposito: parsea los strings de negociador.py, no un campo
    # estructurado. Se apoya en que ningun concepto de config/categorias.py
    # contiene " a " ni ":" en su nombre (verificado). Si eso cambia, la
    # unica consecuencia es que un upgrade quede sin fusionar y aparezca
    # tambien en "Con la holgura podrias" -- no revienta, solo se duplica.
    _recortados = {r.split(":")[0].removeprefix("saque ").split(" (")[0].strip()
                   for r in cot.recortes if not r.startswith("NO ALCANZA")}

    st.subheader("Lista de compra")
    for i in cot.items:
        fuente = ("fuente verificada" if i.requerimiento.regla_verificada
                  else "estimación sin fuente verificada")
        marca = "" if i.requerimiento.regla_verificada else " :warning:"
        pin = " 📌" if i.fijado_por_usuario else ""
        with st.expander(
                _esc(f"{i.concepto} — {i.unidades_a_comprar} x ${i.producto.precio:,} "
                     f"= ${i.subtotal_cop:,}  [{i.gama}]{marca}{pin}"), expanded=False):
            st.write(f"**{i.producto.nombre}**  \nSKU {i.producto.sku} · {i.producto.marca}")
            st.write(f"[Abrir en Homecenter]({i.producto.url})")
            st.caption(f"Obra: {i.requerimiento.cantidad} {i.requerimiento.unidad} · "
                       f"{i.requerimiento.formula}")
            st.caption(f"{fuente}: {i.requerimiento.fuente_regla}")
            if i.estado_precio != "snapshot":
                st.caption(_esc(f"precio {i.estado_precio}: ${i.precio_confirmado:,}"))
            if i.fijado_por_usuario:
                st.caption("📌 lo elegiste tú; el negociador no le baja la gama por su cuenta")

            if st.toggle("Cambiar producto", key=f"tg_{i.concepto}"):
                opts = _opciones_swap(i.concepto, i.requerimiento.unidad)
                if not opts:
                    st.caption("No hay alternativas para este concepto en el catálogo.")
                else:
                    with st.form(f"swap_{i.concepto}"):
                        idx_actual = next((k for k, p in enumerate(opts)
                                          if p.sku == i.producto.sku), 0)
                        elegido = st.selectbox(
                            "Alternativas", opts,
                            format_func=lambda p: f"${p.precio:,} · {p.nombre[:55]}",
                            index=idx_actual, key=f"sel_{i.concepto}")
                        if st.form_submit_button("Cambiar"):
                            ok, msg = negociador.sustituir(cot, i.concepto, elegido.sku)
                            if ok:
                                swaps = memoria.leer(sesion, "swaps") or {}
                                swaps[i.concepto] = elegido.sku
                                memoria.escribir(sesion, "swaps", swaps)
                                st.session_state["cot"] = cot
                                st.rerun()
                            else:
                                st.error(_esc(msg))

    if cot.faltantes:
        st.warning(f"Sin candidatos en el catálogo: {', '.join(cot.faltantes)}")

    if cot.recortes:
        st.subheader("Para que cupiera en tu presupuesto, hice estos ajustes")
        st.caption("El total de arriba ya los incluye. Puedes confirmarlos o deshacerlos "
                   "subiendo el tope.")
        for r in cot.recortes[:8]:
            st.write("-", _esc(r))
        # Upgrades que revertirian un recorte recien hecho se muestran junto al
        # recorte, no como una seccion aparte que se contradice con la de arriba.
        reversibles = [al for al in cot.alternativas
                      if any(al.split(" a ")[0].endswith(c) for c in _recortados)]
        if reversibles:
            st.caption("Con la holgura que queda, podrías revertir alguno de estos:")
            for al in reversibles[:4]:
                st.write("↩", _esc(al))
        col1, col2 = st.columns(2)
        if col1.button("Confirmar y seguir", type="primary"):
            cot.aprobada_por_humano = True
            memoria.escribir(sesion, "recortes_aprobados", cot.recortes)
            st.success("Ajustes confirmados. Cotización lista.")
        # Solo tiene sentido cuando de verdad no alcanzo ni con todos los
        # recortes (minimo_viable_cop > 0); si la cotizacion ya cupo, "subir
        # el tope" no tiene a que numero subir.
        if cot.minimo_viable_cop and col2.button("Deshacer: subir el tope al mínimo viable"):
            st.session_state["tope_sugerido"] = min(int(cot.minimo_viable_cop), 200_000_000)
            st.session_state["ejecutar"] = True
            st.rerun()

    _otras_alternativas = [al for al in cot.alternativas
                           if not any(al.split(" a ")[0].endswith(c) for c in _recortados)]
    if _otras_alternativas:
        st.subheader("Con la holgura podrías")
        for al in _otras_alternativas[:4]:
            st.write("+", _esc(al))

    if cot.fases:
        st.subheader("Plan por fases")
        for f, cs in cot.fases.items():
            st.write(f"**{f}**: {', '.join(cs)}")

    st.subheader("Validación en vivo")
    st.caption("Confirma el precio de los 3 ítems más caros contra homecenter.com.co "
               "(no mueve el total: solo muestra la diferencia).")
    if not cot.items:
        st.caption("Nada que validar todavía.")
    elif st.button("Confirmar precios contra homecenter.com.co"):
        objetivo = sorted(cot.items, key=lambda i: -i.subtotal_cop)[:3]
        barra = st.progress(0.0)
        filas = []
        for n, i in enumerate(objetivo, 1):
            r = tools.validar_en_vivo(i.producto.sku)
            filas.append({"concepto": i.concepto, "subtotal_snapshot": i.subtotal_cop,
                         "unidades": i.unidades_a_comprar, **r})
            barra.progress(n / len(objetivo))
        st.session_state["validacion"] = filas

    val = st.session_state.get("validacion")
    if val:
        total_snapshot = sum(f["subtotal_snapshot"] for f in val)
        total_vivo = sum((f.get("precio") or (f["subtotal_snapshot"] // max(f["unidades"], 1)))
                         * f["unidades"] for f in val)
        diff = total_vivo - total_snapshot
        d1, d2, d3 = st.columns(3)
        d1.metric("Total snapshot (estos ítems)", f"${total_snapshot:,}")
        d2.metric("Total en vivo", f"${total_vivo:,}")
        d3.metric("Diferencia", f"${diff:,}", delta=f"${diff:,}" if diff else None)
        for f in val:
            estado = f.get("estado", "snapshot")
            icono = {"en_vivo": "✅", "cambio": "⚠️", "snapshot": "○"}.get(estado, "○")
            linea = f"{icono} {f['concepto']}: {estado} ${(f.get('precio') or 0):,}"
            if not f.get("en_vivo"):
                linea += f"  ({_esc(f.get('motivo', f.get('error', 'snapshot')))})"
            st.write(linea)

