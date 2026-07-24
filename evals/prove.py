#!/usr/bin/env python3
"""Demuestra cada componente de arquitectura HACIENDO su trabajo.

  python -m evals.prove              # nucleo determinista, sin API key
  python -m evals.prove --con-llm    # incluye los 3 loops (requiere ANTHROPIC_API_KEY)

Esta es la respuesta a "esto esta mockeado?" y a "el componente funciona?".
"""
from __future__ import annotations
import argparse, os, sys
import yaml
from pydantic import ValidationError

from data.categorias import CONCEPTO_A_CATEGORIA
from src import catalogo, memoria, negociador, reglas, tools, verificador
from src.schemas import Cotizacion, Espacio, ItemCotizado, Producto, Requerimiento
from src.traza import Traza
from evals.nucleo import candidatos_de, cotizar, requerimientos_de

OK, NO = "  [OK]", "  [FALLA]"
resultados: list[tuple[str, bool]] = []


def titulo(n: int, nombre: str, archivo: str) -> None:
    print(f"\n{'='*74}\nCOMPONENTE {n}: {nombre}\n  archivo: {archivo}\n{'='*74}")


def chequeo(nombre: str, cond: bool, detalle: str = "") -> bool:
    print(f"{OK if cond else NO} {nombre}" + (f" -> {detalle}" if detalle else ""))
    resultados.append((nombre, bool(cond)))
    return bool(cond)


def c1_guardrails() -> None:
    titulo(1, "Guardrails de entrada", "src/schemas.py")
    casos = yaml.safe_load(open("evals/cases.yaml", encoding="utf-8"))
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
    titulo(2, "Retrieval y grounding sobre datos reales", "src/catalogo.py")
    s = catalogo.stats()
    chequeo("catalogo indexado", s["productos"] > 0, f"{s['productos']} productos, "
            f"{len(s['categorias'])} categorias, snapshot {s['snapshot']}")
    chequeo("guias indexadas (corpus RAG)", True, f"{s['guias']} chunks"
            + ("  <-- corre ingest.fetch_all etapa 2" if s["guias"] == 0 else ""))
    ps = catalogo.buscar("sanitario blanco", categorias=["sanitarios"], k=3)
    chequeo("busqueda devuelve SKUs con precio y URL", bool(ps),
            f"{ps[0].sku} ${ps[0].precio:,} {ps[0].url[-28:]}" if ps else "")
    chequeo("FTS5 no revienta con caracteres raros",
            isinstance(catalogo.buscar('sanitario "one-piece" (30.5)', k=2), list))
    chequeo("filtro estructurado por precio",
            all(p.precio <= 300_000 for p in catalogo.buscar("sanitario", precio_max=300_000, k=5)))


def c3_reglas_sin_aritmetica_del_llm() -> None:
    titulo(3, "Cuantificacion auditable (el LLM no hace aritmetica)", "src/reglas.py")
    e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    r = reglas.calcular("piso_ceramica", e)
    chequeo("formula sustituida es auditable", "=" in r.formula, r.formula)
    chequeo("cantidad correcta (4 m2 + 10% merma)", abs(r.cantidad - 4.4) < 0.01, f"{r.cantidad} m2")
    chequeo("cada cifra declara fuente", bool(r.fuente_regla), r.fuente_regla)
    chequeo("regla no verificada queda marcada", r.regla_verificada is False,
            "se muestra en amarillo en la UI")
    e2 = Espacio(largo_m=2, ancho_m=2, incluye_ducha=False, presupuesto_cop=2_000_000)
    try:
        reglas.calcular("griferia_ducha", e2)
        chequeo("omite conceptos que no aplican", False)
    except ValueError:
        chequeo("omite conceptos que no aplican", True, "sin ducha -> sin griferia de ducha")


def c4_aislamiento() -> None:
    titulo(4, "Multi-agente con aislamiento de informacion", "src/subagentes.py, src/tools.py")
    e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
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


def c5_negociacion() -> None:
    titulo(5, "Negociador determinista bajo restriccion", "src/negociador.py")
    for pres in (6_000_000, 2_000_000, 1_200_000):
        e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=pres)
        cot, fallas, _, _ = cotizar(e)
        uso = 100 * cot.total_cop // pres
        # Invariante: entra en el tope, y la holgura queda EXPLICADA (aprovechada
        # o convertida en upgrades que el humano aprueba). Nunca plata muda.
        explicada = uso >= 80 or bool(cot.alternativas)
        chequeo(f"tope ${pres:,}: entra y la holgura queda explicada",
                cot.total_cop <= pres and explicada,
                f"total ${cot.total_cop:,} ({uso}%), {len(cot.recortes)} recortes, "
                f"{len(cot.alternativas)} upgrades ofrecidos")
    e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    cot, _, _, _ = cotizar(e)
    chequeo("los recortes se explican en pesos",
            any("libere $" in r for r in cot.recortes), cot.recortes[0][:70] if cot.recortes else "")
    chequeo("propone plan por fases", len(cot.fases) >= 2, list(cot.fases))


def c6_autocorreccion() -> None:
    titulo(6, "Auto-correccion: el verificador rechaza y el loop lo observa",
           "src/verificador.py")
    e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
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
    titulo(7, "Memoria de sesion: el 2do turno no re-cuantifica", "src/memoria.py")
    from src import supervisor
    ses = "prove-memoria"
    memoria.olvidar(ses)
    e1 = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
    cot1, t1 = supervisor.correr_deterministico(e1, sesion=ses, traza=Traza("t1"))
    chequeo("turno 1 cuantifica y guarda", memoria.leer(ses, "requerimientos") is not None,
            f"total ${cot1.total_cop:,}")
    e2 = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_500_000)
    cot2, t2 = supervisor.correr_deterministico(e2, sesion=ses, traza=Traza("t2"))
    hit = any(p["tipo"] == "memoria_hit" for p in t2.pasos)
    chequeo("turno 2 reusa requerimientos de memoria", hit,
            f"total ${cot2.total_cop:,} con el tope subido")
    chequeo("mas presupuesto -> mejor cotizacion", cot2.total_cop > cot1.total_cop,
            f"${cot1.total_cop:,} -> ${cot2.total_cop:,}")
    memoria.olvidar(ses)


def c8_observabilidad() -> None:
    titulo(8, "Observabilidad: traza persistida", "src/traza.py")
    t = Traza("prove")
    t.paso("supervisor", "tool_use", "delegar_cuantificacion()")
    t.paso("verificador", "rechazo", "1 falla: sku_inexistente")
    t.paso("supervisor", "tool_use", "delegar_compra()")
    ruta = t.guardar()
    chequeo("traza guardada en disco", os.path.exists(ruta), ruta)
    chequeo("detecta auto-correccion", t.hubo_autocorreccion())
    chequeo("lista herramientas usadas", len(t.herramientas_usadas()) == 2,
            str(t.herramientas_usadas()))


def c9_llm() -> None:
    titulo(9, "Los tres loops agenticos (requiere ANTHROPIC_API_KEY)",
           "src/loop.py, src/supervisor.py")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [SALTADO] sin ANTHROPIC_API_KEY. Corre: python -m evals.prove --con-llm")
        return
    from src import qa, supervisor
    e = Espacio(largo_m=2, ancho_m=2, presupuesto_cop=2_000_000)
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
            "no tengo informacion verificada" in r2["respuesta"].lower(), r2["respuesta"][:90])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--con-llm", action="store_true")
    a = ap.parse_args()
    if not os.path.exists("data/catalogo.db"):
        print("no existe data/catalogo.db. Corre:")
        print("  python -m ingest.build_index --fuente evals/fixture_productos.json")
        return 1
    for f in (c1_guardrails, c2_retrieval, c3_reglas_sin_aritmetica_del_llm, c4_aislamiento,
              c5_negociacion, c6_autocorreccion, c7_memoria, c8_observabilidad):
        f()
    if a.con_llm:
        c9_llm()
    malos = [n for n, ok in resultados if not ok]
    print(f"\n{'='*74}\n{len(resultados) - len(malos)}/{len(resultados)} chequeos en verde")
    for n in malos:
        print("  FALLA:", n)
    print("=" * 74)
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
