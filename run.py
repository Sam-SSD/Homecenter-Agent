#!/usr/bin/env python3
"""CLI end-to-end.

  python run.py --largo 2 --ancho 2 --presupuesto 2000000
  python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico
  python run.py --largo 2 --ancho 2 --presupuesto 2500000 --sesion demo   # 2do turno
"""
from __future__ import annotations
import argparse, sys
from pydantic import ValidationError
from src.schemas import Espacio
from src.traza import Traza


def imprimir(cot) -> None:
    if cot is None:
        print("\nno se produjo cotizacion")
        return
    e = cot.espacio
    print(f"\n{'='*74}\nCOTIZACION  bano {e.largo_m}x{e.ancho_m} m ({e.area_piso} m2)"
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
    ap.add_argument("--largo", type=float, required=True)
    ap.add_argument("--ancho", type=float, required=True)
    ap.add_argument("--presupuesto", type=int, required=True)
    ap.add_argument("--altura-enchape", type=float, default=2.0)
    ap.add_argument("--sin-ducha", action="store_true")
    ap.add_argument("--sesion", default="cli")
    ap.add_argument("--deterministico", action="store_true",
                    help="salta el loop LLM del supervisor (red de seguridad de demo)")
    ap.add_argument("--preguntar", default=None, help="pregunta de seguimiento al Q&A")
    a = ap.parse_args()

    try:
        espacio = Espacio(largo_m=a.largo, ancho_m=a.ancho,
                          altura_enchape_m=a.altura_enchape,
                          incluye_ducha=not a.sin_ducha,
                          presupuesto_cop=a.presupuesto)
    except ValidationError as e:
        print("GUARDRAIL rechazo la entrada:")
        for err in e.errors():
            print("  -", err["msg"])
        return 2

    from src import supervisor
    traza = Traza("run")
    print(f"objetivo: bano {espacio.area_piso} m2, tope ${espacio.presupuesto_cop:,}\n")
    if a.deterministico:
        cot, traza = supervisor.correr_deterministico(espacio, sesion=a.sesion, traza=traza)
    else:
        cot, traza = supervisor.correr_agentico(espacio, sesion=a.sesion, traza=traza)
    imprimir(cot)
    print("\ntraza:", traza.guardar(), "|", traza.resumen())

    if a.preguntar and cot:
        from src import qa
        print(f"\nPREGUNTA: {a.preguntar}")
        print("RESPUESTA:", qa.responder(a.preguntar, cot, traza)["respuesta"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
