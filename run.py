#!/usr/bin/env python3
"""CLI end-to-end.

  python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2000000
  python run.py --tipo cocina --largo 3 --ancho 2.5 --presupuesto 8000000 --deterministico
  python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2500000 --sesion demo   # 2do turno
"""
from __future__ import annotations
import argparse, sys
from src.ejecutar import construir_espacio, cotizar, preguntar
from src.traza import Traza


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
    ap.add_argument("--largo", type=float, required=True)
    ap.add_argument("--ancho", type=float, required=True)
    ap.add_argument("--presupuesto", type=int, required=True)
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

    altura_enchape = a.altura_enchape
    if altura_enchape is None and a.tipo in ("bano", "cocina"):
        altura_enchape = 2.0
    incluye_ducha = (not a.sin_ducha) if a.tipo == "bano" else None
    metros_lineales = a.metros_lineales
    if metros_lineales is None and a.tipo in ("cocina", "habitacion"):
        # sin esto, meson_cocina/closet no tienen su variable y la regla no
        # aplica: el mesón o el closet desaparecen de la cotizacion sin aviso,
        # y el verificador solo lo atrapa si el concepto es esencial (cocina).
        metros_lineales = 3.0

    espacio, errores = construir_espacio(
        tipo=a.tipo, largo_m=a.largo, ancho_m=a.ancho, presupuesto_cop=a.presupuesto,
        altura_enchape_m=altura_enchape, incluye_ducha=incluye_ducha,
        metros_lineales=metros_lineales)
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
