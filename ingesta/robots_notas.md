# Copia de https://www.homecenter.com.co/robots.txt revisada el 24-jul-2026,
# antes de hacer el primer request. Rutas usadas por este proyecto:
#   /homecenter-co/category/  -> PERMITIDA
#   /homecenter-co/product/   -> PERMITIDA
#   facetas f.product.*       -> PERMITIDAS explicitamente (Allow)
# Rutas evitadas por ingesta/fetch.py:PROHIBIDOS:
#   /homecenter-co/search/, */search?, /homecenter-co/browse/, /cart/,
#   /myaccount/, /CMR/, /*N-*, /*Ver-todos*/, /*staticContent, /*.aspx$,
#   */noSearchResult, */*?queryId=*, */*?bvstate=*
# El sitemap de categorias declarado ahi es la fuente de config/categorias.py.
