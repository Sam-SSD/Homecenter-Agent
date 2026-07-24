"""UI de demo. Sin diseno a proposito: la traza vale mas puntos que el CSS.

  streamlit run app.py
"""
from __future__ import annotations
import os
import streamlit as st
from pydantic import ValidationError

from src import catalogo, memoria, qa, supervisor, tools, verificador
from src.schemas import Espacio
from src.traza import Traza

st.set_page_config(page_title="Cotizador de bano - Homecenter", layout="wide")
st.title("Asistente de remodelacion de bano")

s = catalogo.stats()
st.caption(f"Catalogo: {s['productos']} productos - {s['guias']} chunks de guia - "
           f"snapshot {s['snapshot']} - precios y disponibilidad para Medellin")

with st.sidebar:
    st.header("El espacio")
    largo = st.number_input("Largo (m)", 0.8, 6.0, 2.0, 0.1)
    ancho = st.number_input("Ancho (m)", 0.8, 6.0, 2.0, 0.1)
    enchape = st.number_input("Altura de enchape (m)", 0.5, 3.0, 2.0, 0.1)
    ducha = st.checkbox("Tiene ducha", True)
    presupuesto = st.number_input("Presupuesto (COP)", 500_000, 50_000_000, 2_000_000, 100_000)
    modo = st.radio("Modo", ["Agentico (3 loops)", "Determinista (respaldo de demo)"], index=0)
    sesion = st.text_input("Sesion", "demo")
    if st.button("Cotizar", type="primary", use_container_width=True):
        st.session_state.pop("cot", None)
        st.session_state["ejecutar"] = True
    if st.button("Olvidar sesion", use_container_width=True):
        memoria.olvidar(sesion)
        st.session_state.clear()
        st.rerun()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("Sin ANTHROPIC_API_KEY: solo funciona el modo determinista.")

if st.session_state.pop("ejecutar", False):
    try:
        espacio = Espacio(largo_m=largo, ancho_m=ancho, altura_enchape_m=enchape,
                          incluye_ducha=ducha, presupuesto_cop=int(presupuesto))
    except ValidationError as e:
        st.error("El guardrail de entrada rechazo estos datos:")
        for err in e.errors():
            st.write("-", err["msg"])
        st.stop()
    traza = Traza("ui")
    with st.spinner("El agente esta trabajando..."):
        if modo.startswith("Determinista"):
            cot, traza = supervisor.correr_deterministico(espacio, sesion=sesion, traza=traza)
        else:
            cot, traza = supervisor.correr_agentico(espacio, sesion=sesion, traza=traza)
    st.session_state["cot"] = cot
    st.session_state["traza"] = traza

cot = st.session_state.get("cot")
traza = st.session_state.get("traza")

izq, der = st.columns([3, 2])

with der:
    st.subheader("Traza del agente")
    if traza:
        st.caption(f"{len(traza.pasos)} pasos - {traza.resumen()['segundos']}s"
                   + (" - hubo auto-correccion" if traza.hubo_autocorreccion() else ""))
        for p in traza.pasos:
            icono = {"rechazo": "[X]", "aprobacion": "[OK]", "tool_use": "[>]",
                     "piensa": "[~]", "sku_inventado": "[!]"}.get(p["tipo"], "[.]")
            st.text(f"{icono} {p['t']:6.2f}s {p['actor']:13} {p['tipo']}")
            if p["detalle"]:
                st.caption(f"      {p['detalle'][:120]}")
    else:
        st.info("Corre una cotizacion para ver el loop.")

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
        st.error(f"El verificador encontro {len(fallas)} fallas")
        for f in fallas[:6]:
            st.write(f"- `{f.codigo}` {f.concepto}: {f.mensaje}")
    else:
        st.success("Verificador: aprobada")

    st.subheader("Lista de compra")
    for i in cot.items:
        fuente = ("fuente verificada" if i.requerimiento.regla_verificada
                  else "estimacion sin fuente verificada")
        marca = "" if i.requerimiento.regla_verificada else " :warning:"
        with st.expander(
                f"{i.concepto} - {i.unidades_a_comprar} x ${i.producto.precio:,} "
                f"= ${i.subtotal_cop:,}  [{i.gama}]{marca}", expanded=False):
            st.write(f"**{i.producto.nombre}**  \nSKU {i.producto.sku} - {i.producto.marca}")
            st.write(f"[Abrir en Homecenter]({i.producto.url})")
            st.caption(f"Obra: {i.requerimiento.cantidad} {i.requerimiento.unidad} - "
                       f"{i.requerimiento.formula}")
            st.caption(f"{fuente}: {i.requerimiento.fuente_regla}")
            if i.estado_precio != "snapshot":
                st.caption(f"precio {i.estado_precio}: ${i.precio_confirmado:,}")

    if cot.faltantes:
        st.warning(f"Sin candidatos en el catalogo: {', '.join(cot.faltantes)}")

    if cot.recortes:
        st.subheader("Negociacion (requiere tu aprobacion)")
        for r in cot.recortes[:8]:
            st.write("-", r)
        col1, col2 = st.columns(2)
        if col1.button("Aprobar los recortes", type="primary"):
            cot.aprobada_por_humano = True
            memoria.escribir(sesion, "recortes_aprobados", cot.recortes)
            st.success("Recortes aprobados. Cotizacion lista.")
        if col2.button("Rechazar y subir el presupuesto"):
            st.info("Sube el tope en la barra lateral y vuelve a cotizar: "
                    "el agente recuerda las cantidades y no las recalcula.")

    if cot.alternativas:
        st.subheader("Con la holgura podrias")
        for al in cot.alternativas[:4]:
            st.write("+", al)

    if cot.fases:
        st.subheader("Plan por fases")
        for f, cs in cot.fases.items():
            st.write(f"**{f}**: {', '.join(cs)}")

    st.subheader("Validacion en vivo")
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
    q = st.text_input("Toda respuesta sale de una herramienta, o dice que no sabe")
    if q:
        with st.spinner("Consultando fuentes..."):
            r = qa.responder(q, cot, traza or Traza("qa"))
        st.write(r["respuesta"])
        st.caption("herramientas usadas: " + ", ".join(r["herramientas"][-4:]))
