"""API HTTP del cotizador. Paquete nuevo: no toca dominio/ ni agentes/, asi que
pruebas/prove.py sigue siendo la fuente de verdad del nucleo determinista.

Arrancar SIEMPRE desde la raiz del repo (datos/catalogo.db, config/reglas_obra.yaml
y datos/memoria.db son rutas relativas):

    uvicorn api.servidor:app --port 8000
"""
