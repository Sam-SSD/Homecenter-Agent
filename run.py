#!/usr/bin/env python3
"""CLI end-to-end.

  python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2000000
  python run.py --tipo cocina --largo 3 --ancho 2.5 --presupuesto 8000000 --deterministico
  python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2500000 --sesion demo   # 2do turno
"""
from __future__ import annotations
import argparse, sys
from agentes.ejecutar import construir_espacio, cotizar, preguntar
from dominio.traza import Traza


def imprimir(cot) -> None:
    if cot is None:
        print("\nno se produjo cotizacion")
        return
    e = cot.espacio
    print(f"\n{'='*74}\nCOTIZACION  {e.tipo} {e.largo_m}x{e.ancho_m} m ({e.area_piso} m2)"
          f"  tope ${e.presupuesto_cop:,}\n{'='*74}")
    for i in cot.items:
        amarillo = "" if i.requerimiento.regla_verificada else "  (*)"
        print(f" p{i.requerimiento.prioridad} {i.concepto:24} {i.unidades_a_comprar:>3} x "
              f"${i.producto.precio:>9,} = ${i.subtotal_cop:>10,}  [{i.gama}]{amarillo}")
        print(f"      {i.producto.nombre[:64]}")
        print(f"      {i.producto.url}")
    print(f"\n TOTAL      ${cot.total_cop:>12,}")
    print(f" HOLGURA    ${cot.holgura_cop:>12,}")
    if cot.faltantes:
        print(f" SIN CANDIDATOS: {', '.join(cot.faltantes)}")
    if cot.recortes:
        print("\n NEGOCIACION:")
        for r in cot.recortes[:6]:
            print(f"   - {r}")
    if cot.alternativas:
        print("\n CON LA HOLGURA:")
        for a in cot.alternativas[:3]:
            print(f"   + {a}")
    if cot.fases:
        print("\n PLAN POR FASES:")
        for f, cs in cot.fases.items():
            print(f"   {f}: {', '.join(cs)}")
    if cot.cifras_sin_fuente:
        print(f"\n (*) cifras estimadas sin fuente verificada: {', '.join(cot.cifras_sin_fuente)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tipo", default="bano", choices=["bano", "cocina", "habitacion", "sala"])
    ap.add_argument("--largo", type=float, default=None)
    ap.add_argument("--ancho", type=float, default=None)
    ap.add_argument("--presupuesto", type=int, default=None)
    ap.add_argument("--altura-enchape", type=float, default=None,
                    help="solo aplica a bano y cocina (enchape de pared)")
    ap.add_argument("--sin-ducha", action="store_true", help="solo aplica a bano")
    ap.add_argument("--metros-lineales", type=float, default=None,
                    help="meson de cocina o closet corrido, cuando aplique")
    ap.add_argument("--sesion", default="cli")
    ap.add_argument("--deterministico", action="store_true",
                    help="salta el loop LLM del supervisor (red de seguridad de demo)")
    ap.add_argument("--preguntar", default=None, help="pregunta de seguimiento al Q&A")
    a = ap.parse_args()

    geometria = (a.largo, a.ancho, a.presupuesto)
    if all(g is None for g in geometria):
        # --preguntar solo: el Q&A de producto no necesita un espacio cotizado.
        if a.preguntar:
            print(f"PREGUNTA: {a.preguntar}")
            print("RESPUESTA:", preguntar(a.preguntar, None, Traza("run")))
            return 0
        ap.error("se requieren --largo, --ancho y --presupuesto "
                 "(o --preguntar para consultar sin cotizar)")
    if any(g is None for g in geometria):
        ap.error("--largo, --ancho y --presupuesto van juntos")

    # Los defaults por ambiente (altura_enchape_m=2.0, metros_lineales=3.0,
    # incluye_ducha=True) los aplica dominio.schemas.Espacio (DEFAULTS_POR_TIPO):
    # una sola fuente de verdad, no duplicada aqui y en app.py. Solo --sin-ducha
    # necesita forzar un valor explicito, porque es lo opuesto al default.
    incluye_ducha = False if a.sin_ducha else None

    espacio, errores = construir_espacio(
        tipo=a.tipo, largo_m=a.largo, ancho_m=a.ancho, presupuesto_cop=a.presupuesto,
        altura_enchape_m=a.altura_enchape, incluye_ducha=incluye_ducha,
        metros_lineales=a.metros_lineales)
    if espacio is None:
        print("GUARDRAIL rechazo la entrada:")
        for msg in errores:
            print("  -", msg)
        return 2

    traza = Traza("run")
    print(f"objetivo: {espacio.tipo} {espacio.area_piso} m2, tope ${espacio.presupuesto_cop:,}\n")
    cot, traza = cotizar(espacio, sesion=a.sesion, deterministico=a.deterministico, traza=traza)
    imprimir(cot)
    print("\ntraza:", traza.guardar(), "|", traza.resumen())

    if a.preguntar and cot:
        print(f"\nPREGUNTA: {a.preguntar}")
        print("RESPUESTA:", preguntar(a.preguntar, cot, traza))
    return 0


if __name__ == "__main__":
    sys.exit(main())
