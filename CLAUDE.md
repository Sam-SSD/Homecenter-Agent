# CLAUDE.md â€” contexto para Claude Code

## QuÃ© es
Cotizador de remodelaciÃ³n con productos reales de Homecenter Colombia. Cubre 4
ambientes: baÃ±o, cocina, habitaciÃ³n y sala.
Hackathon AgentSprint by ReshapeX, EAFIT MedellÃ­n, 25-jul-2026, 8:00â€“12:00.

Frase del pitch: **no es un buscador de productos, es un cuantificador de obra que
negocia con tu presupuesto y te dice que no.**

## Reglas del proyecto â€” no las rompas

1. **El LLM nunca hace aritmÃ©tica.** Llama `calcular_cantidad`; Python evalÃºa la
   fÃ³rmula de `config/reglas_obra.yaml` y devuelve la fÃ³rmula sustituida.
2. **El LLM nunca inventa un SKU.** Todo producto sale de `buscar_catalogo`.
   `agentes/subagentes.py:comprar` descarta cualquier SKU que no exista y lo registra.
3. **Aislamiento de informaciÃ³n.** El Cuantificador NO ve el presupuesto
   (`Espacio.sin_presupuesto()`) ni tiene herramientas de precio. El Comprador NO
   ve cantidades. Si lo rompes, el sistema ajusta las cantidades para que quepan y
   la cotizaciÃ³n en obra no alcanza. `pruebas/prove.py` lo verifica.
4. **El presupuestador es determinista.** `dominio/negociador.py` es optimizaciÃ³n, no
   un LLM. Un LLM complace y alucina totales.
5. **Toda cifra declara fuente.** Regla sin fuente verificada â†’ `regla_verificada:
   false` â†’ amarillo en la UI. No la marques `true` sin una guÃ­a real en
   `datos/guias.json`.
6. **Respeta robots.txt.** `ingesta/fetch.py:permitido()` bloquea las rutas
   prohibidas. No uses `/search`, no rotes el User-Agent, no evadas Cloudflare.
   Usa la `Session` (conserva la cookie `__cf_bm`). DELAY mÃ­nimo 1.8 s.
7. **Descarga y parseo separados.** El parser se itera contra `cache/`, sin red.

8. **El proveedor de LLM vive solo en `agentes/llm.py`.** Los agentes usan `generar()`
   en formato neutro. Si necesitas cambiar de modelo o de proveedor, se toca ese
   archivo o `.env`, nunca `supervisor.py` ni `subagentes.py`. Pool de llaves con
   rotacion ante 429/503/llave invalida, y cadena de modelos ante 404.

## Arquitectura
```
Objetivo â†’ Supervisor (loop) â”€â”¬â†’ Cuantificador (loop, sin precios)
                              â””â†’ Comprador (loop, sin cantidades)
                                 â†’ Negociador (cÃ³digo) â†’ Verificador (cÃ³digo)
                                 â†’ si rechaza, vuelve al Supervisor como
                                   resultado de herramienta
```
El Q&A (`agentes/qa.py`) es la Ãºnica puerta de salida de texto: sin fuente responde
"No tengo informaciÃ³n verificada sobre eso."

## Estructura de carpetas
```
dominio/    modelos, reglas de obra, catalogo (SQL+FTS5), negociador, verificador,
            memoria, traza, y el pipeline determinista (nucleo.py). Codigo puro, sin LLM.
agentes/    los 3 loops LLM (supervisor, subagentes, qa), el proveedor aislado
            (llm.py), prompts, tools y el arranque unificado (ejecutar.py).
config/     fuente versionada: categorias de Homecenter (categorias.py) y las
            reglas de obra (reglas_obra.yaml).
datos/      artefactos generados y gitignored: catalogo.db, productos.json,
            guias.json, memoria.db. Se regeneran del pipeline de ingesta.
ingesta/    scraping y parseo (fetch, parse, build_index, sanity, estado, healthcheck).
pruebas/    prove.py (163 chequeos), cases.yaml, fixtures.
run.py, app.py   entrypoints, en la raiz (streamlit y python ponen el directorio
                 del script en sys.path, asi que no pueden vivir en una subcarpeta).
```

## Comandos
```bash
Copy-Item .env.example .env      # poner GEMINI_API_KEYS=llave1,llave2,llave3
python -m agentes.llm                # verifica cada llave (barato)
python -m agentes.llm --tools        # + ida y vuelta con herramienta (2 requests, una vez)
python -m agentes.llm --modelos      # que modelos soporta tu llave (gratis)

# datos (requiere red; hacerlo la noche anterior)
python -m ingesta.fetch_all --ambiente bano            # o cocina | habitacion | sala | todos
python -m ingesta.fetch_all --ambiente cocina --estimar  # cuenta requests, cero red
python -m ingesta.parse_all                            # offline, itera aquÃ­
python -m ingesta.build_index
python -m ingesta.sanity                               # QA: abre los 3 links que imprime
python -m ingesta.healthcheck                          # correr otra vez 7:45 desde EAFIT

# sin red / sin API key
python -m ingesta.build_index --fuente pruebas/fixture_productos.json
python -m pruebas.prove                                 # 163 chequeos, 13 componentes
python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico

# completo
python -m pruebas.prove --con-llm
python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2000000
streamlit run app.py
```

## Estado actual
- NÃºcleo determinista: **funcionando**, 163/163 en `prove.py` contra datos reales,
  para los 4 ambientes (baÃ±o, cocina, habitaciÃ³n, sala).
- Loops LLM: **probados con llave real** en baÃ±o. `--con-llm` se mantiene solo
  en baÃ±o por cuota (ver abajo); cocina/habitaciÃ³n/sala se cubren de forma
  determinista, incluidos dos chequeos que verifican que cada regla del YAML
  tiene formula bien formada y resuelve a producto real en su ambiente.
- Cuota Gemini del tier gratuito: **20 requests por dÃ­a y POR MODELO**. Una
  corrida `--con-llm` gasta ~35, asÃ­ que `GEMINI_MODELOS` lleva 4 modelos: el
  fallback por modelo es lo que sostiene el dÃ­a de demo. MÃ¡s llaves = mÃ¡s cupo.
- `datos/catalogo.db` estÃ¡ construido desde datos reales: 2827 productos en 37
  categorÃ­as, 231 chunks de guÃ­a, cubriendo los 4 ambientes. El esquema SQL no
  cambiÃ³ al agregar ambientes (`categoria`/`cat_id` son strings libres): el
  contrato es la base de datos. `pruebas/fixture_productos.json` (sintÃ©tico, 4
  ambientes) sigue disponible para evals sin red vÃ­a `--fuente`.
- `datos/guias.json` tiene 231 chunks reales de las 4 categorÃ­as padre de guÃ­as.
  Sin fuente verificada en `datos/guias.json`, una regla queda `verificada: false`
  (amarillo en la UI) â€” eso es lo esperado para todo lo que no sea baÃ±o hasta
  que se scrapeen mÃ¡s guÃ­as de cocina/habitaciÃ³n/sala.

## Orden de trabajo maÃ±ana
- 8:00â€“8:20 congelar `dominio/schemas.py`, repartir archivos sin solaparse
- 8:20â€“9:20 `python -m pruebas.prove --con-llm` en verde (los 3 loops corriendo)
- 9:20â€“10:10 corpus de guÃ­as real + citaciones + Q&A
- 10:10â€“10:30 revisar `prove.py`, agregar chequeos que falten
- 10:30 punto de decisiÃ³n: si el agÃ©ntico estÃ¡ frÃ¡gil, se presenta el determinista
- 10:30â€“11:20 UI, memoria, aprobaciÃ³n humana
- 11:20 congelar. `git tag demo`. Dos ensayos con cronÃ³metro.

## Verificar antes del evento
- Los modelos en `.env` (`GEMINI_MODELOS`): ya verificados el 24-jul-2026 contra
  la llave real (3.6-flash, 3.5-flash-lite, 3.1-flash-lite, 3-flash-preview).
  2.0 y 2.5 estan apagados. Si cambia la llave, corre `python -m agentes.llm --modelos`.
- `python -m agentes.llm --tools` hace una ida y vuelta con herramienta: si eso pasa,
  los loops corren (el ping de un solo turno no cubria el bug de las firmas).
  **Cuesta 2 requests del primer modelo, de 20 que hay al dia: corrolo UNA vez.**
- **Conseguir mas llaves.** Con una sola, una corrida `--con-llm` casi agota el
  dia. Cada llave del equipo multiplica el cupo (20/dia x modelo x llave).
- El parÃ¡metro de paginaciÃ³n de las categorÃ­as: **no confirmado**. Por eso
  `ingesta/fetch.py` usa facetas (permitidas en robots.txt) en vez de paginar.



