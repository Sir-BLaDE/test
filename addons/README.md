# Nuvio Addon: Búsqueda Prioritaria Castellano Español

Addon de Nuvio que optimiza las búsquedas priorizando contenido en castellano español (ES-ES y variantes latinas).

## 🌟 Características

- ✅ Filtrado automático por país de origen (ES-ES, ES-MX, ES-AR, etc.)
- ✅ Sistema de caché local para reducir latencia
- ✅ Búsqueda multivariante con prioridad castellano
- ✅ Normalización inteligente manteniendo ñ (diferenciador clave)
- ✅ Rate limit handling para TMDB API

## 📦 Instalación

### Método 1: Instalar desde URL (recomendado)

En la interfaz de Nuvio, usa el **instalador vía URL**:

```
https://raw.githubusercontent.com/nuvio-addons/search-es-priority/main/package.json
```

Selecciona opción: **"Instalar addon remoto"** y pega la URL anterior.

### Método 2: Instalar localmente

Si tienes acceso al sistema de archivos de Nuvio:

1. Copia `nuvio_search_es_priority.py` a tu carpeta de addons
2. Ejecuta `npm install` o usa el instalador local integrado de Nuvio

## 🔧 Configuración

El addon usa por defecto:
- TMDB API: `https://api.themoviedb.org/3`
- Caché local: `C:\Nuvio\cache` (ajustable)
- Rate limit wait: 1s exponencial backoff

Para cambiar la API key de TMDB, edita directamente el archivo Python.

## 📊 Uso

```python
from nuvio_search_es_priority import build_search_plan

# Ejemplo de uso:
plan, metadata = await build_search_plan(
    api_key="TU_API_KEY_TMDB",
    stremio_type="movie",
    raw_id="tt1234567",  # ID IMDB o TMDB
    preferred_country="ES-ES",  # Auto-detect si vacio
)

print(f"Queries generadas: {plan.total_queries}")
for query, priority in plan.queries_es_priority:
    print(f"  [{priority}] {query}")
```

## 📜 Licencia

MIT License - Usalo para contenido libre de restricciones.

---

**¡Gracias por usar Nuvio!**
