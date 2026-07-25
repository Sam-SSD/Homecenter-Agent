"""UI de demo. Sin diseno complejo a proposito: la traza en vivo del loop de
agentes vale mas puntos que el CSS.

  streamlit run app.py
"""
from __future__ import annotations
import streamlit as st

from dominio import catalogo, memoria, verificador
from dominio.schemas import LIMITES
from dominio.traza import Traza
from agentes import qa, tools
from agentes.ejecutar import construir_espacio, cotizar

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
    "verificador": "Verificador", "ui": "Sistema", "qa": "Preguntas",
}


def _fila_paso(p: dict) -> str:
    icono, etiqueta = PASO_INFO.get(p["tipo"], ("•", p["tipo"]))
    actor = NOMBRES_ACTOR.get(p["actor"], p["actor"])
    linea = f"{icono} `{p['t']:6.2f}s` **{actor}** — {etiqueta}"
    if p["detalle"]:
        linea += f"  \n&nbsp;&nbsp;&nbsp;&nbsp;_{p['detalle'][:120]}_"
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

    presupuesto = st.number_input("Presupuesto (COP)", int(limites["presupuesto_min"]),
                                  200_000_000, max(2_000_000, int(limites["presupuesto_min"])),
                                  100_000)
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
            st.write(f"- `{f.codigo}` {f.concepto}: {f.mensaje}")
    else:
        st.success("Verificador: cotización aprobada")

    st.subheader("Lista de compra")
    for i in cot.items:
        fuente = ("fuente verificada" if i.requerimiento.regla_verificada
                  else "estimación sin fuente verificada")
        marca = "" if i.requerimiento.regla_verificada else " :warning:"
        with st.expander(
                f"{i.concepto} — {i.unidades_a_comprar} x ${i.producto.precio:,} "
                f"= ${i.subtotal_cop:,}  [{i.gama}]{marca}", expanded=False):
            st.write(f"**{i.producto.nombre}**  \nSKU {i.producto.sku} · {i.producto.marca}")
            st.write(f"[Abrir en Homecenter]({i.producto.url})")
            st.caption(f"Obra: {i.requerimiento.cantidad} {i.requerimiento.unidad} · "
                       f"{i.requerimiento.formula}")
            st.caption(f"{fuente}: {i.requerimiento.fuente_regla}")
            if i.estado_precio != "snapshot":
                st.caption(f"precio {i.estado_precio}: ${i.precio_confirmado:,}")

    if cot.faltantes:
        st.warning(f"Sin candidatos en el catálogo: {', '.join(cot.faltantes)}")

    if cot.recortes:
        st.subheader("Negociación (requiere tu aprobación)")
        for r in cot.recortes[:8]:
            st.write("-", r)
        col1, col2 = st.columns(2)
        if col1.button("Aprobar los recortes", type="primary"):
            cot.aprobada_por_humano = True
            memoria.escribir(sesion, "recortes_aprobados", cot.recortes)
            st.success("Recortes aprobados. Cotización lista.")
        if col2.button("Rechazar y subir el presupuesto"):
            st.info("Sube el tope en la barra lateral y vuelve a cotizar: "
                    "el agente recuerda las cantidades y no las recalcula.")

    if cot.alternativas:
        st.subheader("Con la holgura podrías")
        for al in cot.alternativas[:4]:
            st.write("+", al)

    if cot.fases:
        st.subheader("Plan por fases")
        for f, cs in cot.fases.items():
            st.write(f"**{f}**: {', '.join(cs)}")

    st.subheader("Validación en vivo")
    if st.button("Confirmar precios contra homecenter.com.co"):
        barra = st.progress(0.0)
        for n, i in enumerate(cot.items, 1):
            r = tools.validar_en_vivo(i.producto.sku)
            i.estado_precio = r.get("estado", "snapshot")
            i.precio_confirmado = r.get("precio")
            barra.progress(n / len(cot.items))
            st.write(f"- {i.concepto}: {r.get('estado')} "
                     f"${(r.get('precio') or 0):,}"
                     + ("" if r.get("en_vivo") else f"  ({r.get('motivo', 'snapshot')})"))
        st.rerun()

    st.subheader("Pregunta lo que quieras")
    q = st.text_input("Escribe tu pregunta sobre la cotización")
    if q:
        with st.spinner("Consultando fuentes..."):
            r = qa.responder(q, cot, traza or Traza("qa"))
        st.write(r["respuesta"])
        st.caption("Herramientas usadas: " + ", ".join(r["herramientas"][-4:]))
