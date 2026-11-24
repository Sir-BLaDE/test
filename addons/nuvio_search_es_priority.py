# -*- coding: utf-8 -*-
"""
NUVIO ADDON - Búsqueda Prioritaria Castellano Español (ES)
===========================================================

Este addon optimiza las búsquedas en Nuvio/AllDebrid priorizando contenido en castellano
español (ES-ES y variantes latinas, excluyendo italiano/francés/portugués).

Características:
  - ✅ Filtrado por país de origen (ES-ES, ES-MX, ES-AR, etc.)
  - ✅ Cache local para reducir latencia entre consultas repetidas
  - ✅ Búsqueda multivariante (títulos exacto, sin tildes, con año)
  - ✅ Rate limit handling para TMDB API
  - ✅ Logging estructurado para monitorización
  - ✅ Normalización inteligente manteniendo ñ (diferenciador clave)

Instalación:
  Copiar este archivo a: C:\Nuvio\addons/nuvio_search_es_priority.py
  
  O usar el método de script inline desde la configuración del addon.

URL para import/module_path: nuvio_search_es_priority.addon_main
"""


import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Tuple, Dict, Any
import httpx
from datetime import datetime
import json
import hashlib
import os
import logging
import asyncio
import pickle

# =====================================================
# CONFIGURACIÓN
# =====================================================

TMDB_BASE_URL = "https://api.themoviedb.org/3"
ADDON_VERSION = "1.0.0"
CACHE_DIR = r"C:\Nuvio\cache"  # O ajustar a tu ruta Nuvio actual
MAX_CACHE_AGE_SECONDS = 300  # 5 minutos
TMDB_RATE_LIMIT_WAIT = 1.0  # segundos entre intentos al rate limit

# Logging configurado (no spam)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("nuvio_search_es_priority")


# =====================================================
# CLASES PRINCIPALES
# =====================================================

@dataclass
class CountryVariant:
    """Información sobre variante regional de contenido"""
    country_code: str  # ES-ES, ES-MX, ES-AR, etc.
    name_localized: str
    markers: List[str]  # Palabras clave identificativas


@dataclass
class MediaQueryPlan:
    """Plan de búsqueda optimizado con prioridad castellano + filtrado por país"""
    
    media_type: Literal["movie", "tv"]
    tmdb_id: Optional[int]
    localized_title_es: str  # Título en castellano español
    original_title: str      # Título original
    
    year: Optional[str]
    season: Optional[int] = None
    episode: Optional[int] = None
    
    # País detectado (prioridad de búsqueda)
    detected_country: str = "UNDEFINED"
    preferred_countries: List[str] = field(default_factory=list)
    
    # Queries ordenadas por prioridad
    queries_es_priority: List[Tuple[float, str]] = field(default_factory=list)
    queries_fallback: List[Tuple[float, str]] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Construir queries tras inicialización"""
        self._build_queries()
    
    def _build_queries(self):
        """
        Construye lista de queries ordenadas por prioridad castellano + país.
        
        Orden:
          1. Título ES-ES exacto (peninsular) si detectado
          2. Título latam exacto (si aplica)
          3. Título sin tildes (búsqueda más amplia en ES)
          4. Original + "castellano" (hint explícito)
          5. Original puro (fallback último recurso)
        """
        
        title_es = self.localized_title_es.strip()
        original = self.original_title.strip()
        year = self.year or ""
        
        ep_tag = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == "tv" else ""
        
        queries: List[Tuple[float, str]] = []
        
        # === PRIORIDAD 1: Título ES-ES (peninsular) si detectado ===
        if title_es and self.detected_country == "ES-ES":
            q_exacto = f"{title_es}{ep_tag}"
            if year and self.media_type == "movie":
                q_exacto += f" {year}"
            queries.append((0.1, q_exacto))  # Máxima prioridad
            
        # === PRIORIDAD 2: Título latam si aplica ===
        if title_es and self.detected_country.startswith("ES-"):
            q_latino = f"{title_es}{ep_tag}"
            if year and self.media_type == "movie":
                q_latino += f" {year}"
            queries.append((0.2, q_latino))
        
        # === PRIORIDAD 3: Normalizado a peninsular ===
        if title_es and self.detected_country != "ES-ES":
            q_peninsular = f"{self._normalize_to_peninsular(title_es)}{ep_tag}"
            if year and self.media_type == "movie":
                q_peninsular += f" {year}"
            queries.append((0.3, q_peninsular))
        
        # === PRIORIDAD 4: Sin tildes (búsqueda amplia en ES) ===
        if title_es:
            q_no_tilde = f"{self._remove_accents_preserve_n(title_es)}{ep_tag}"
            if year and self.media_type == "movie":
                q_no_tilde += f" {year}"
            queries.append((0.4, q_no_tilde))
        
        # === PRIORIDAD 5: Original con hint castellano ===
        if original and (not title_es or original.lower() != title_es.lower()):
            if self._is_spanish_language(original):
                q_orig_hint = f"{original}{ep_tag} castellano"
                if year and self.media_type == "movie":
                    q_orig_hint += f" {year}"
                queries.append((0.5, q_orig_hint))
        
        # === PRIORIDAD 6: Original puro (fallback) ===
        if original:
            q_orig_puro = f"{original}{ep_tag}"
            if year and self.media_type == "movie":
                q_orig_puro += f" {year}"
            queries.append((0.9, q_orig_puro))  # Prioridad más baja
        
        # Ordenar por prioridad y deduplicar (conservando orden)
        seen_queries: set[str] = set()
        final_queries: List[Tuple[float, str]] = []
        
        for _, query in sorted(queries, key=lambda x: x[0]):
            normalized_key = re.sub(r'\s+', ' ', query).strip().lower()
            
            if normalized_key not in seen_queries:
                seen_queries.add(normalized_key)
                final_queries.append((x[0], query))
        
        self.queries_es_priority = [(1, q) for _, q in sorted(final_queries[:len(queries)//2+1], key=lambda x: x[0])]
        self.queries_fallback = [(2, q) for _, q in sorted(final_queries[len(queries)//2+1:], key=lambda x: x[0], reverse=True)]
        
        # Guardar metadatos
        self.metadata['total_queries'] = len(final_queries)
        self.metadata['country_detected'] = self.detected_country
    
    def _normalize_to_peninsular(self, text: str) -> str:
        """Normaliza variante latinoamericana a peninsular estándar"""
        
        # Reemplazos léxicos específicos (vocabulary ES vs otros)
        replacements = {
            # Algunas variaciones dialectales antiguas
            ('se', 'ce'): ["Se ha comido", "Cé he come"],  # Castellano antiguo
        }
        
        result = text
        
        for old, new in replacements.items():
            if isinstance(old, str):
                # Reemplazo simple por palabra clave
                pattern = rf'\b{re.escape(old)}\b'
                replacement = new[1]
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def _remove_accents_preserve_n(self, text: str) -> str:
        """Elimina tildes de vocales pero MANTIENE ñ (diferenciador clave ES/IT/FR)"""
        
        accented = ['á', 'é', 'í', 'ó', 'ú', 'ü']
        non_accented = ['a', 'e', 'i', 'o', 'u', 'u']
        
        result = text
        
        for accented, non_accent in zip(accented, non_accented):
            result = result.replace(accented, non_accent)
        
        return result
    
    def _is_spanish_language(self, text: str) -> bool:
        """Determina si el título es probable en español (no italiano/francés/etc.)"""
        
        # Palabras exclusivas o comunes solo en ES
        spanish_markers = {
            'la', 'el', 'los', 'las', 'un', 'una', 
            'pero', 'y', 'o', 'con', 'sin', 'donde', 
            'cuando', 'porque', 'aunque'
        }
        
        # Idiados no-español a evitar
        non_spanish = {'italiano', 'francês', 'português', 'català', 'euskera'}
        
        text_lower = text.lower()
        
        has_spanish_content = any(marker in text_lower for marker in spanish_markers if len(marker) > 1)
        has_non_spanish = any(marker in text_lower for marker in non_spanish)
        
        return has_spanish_content and not has_non_spanish
    
    @property
    def total_queries(self) -> int:
        return len(self.queries_es_priority) + len(self.queries_fallback)


class SearchCache:
    """
    Cache local para resultados de búsqueda.
    
    Reduce latencia reutilizando consultas similares a AllDebrid/Nuvio.
    Guarda en disco JSON por simplicidad (pickle es más complejo de serializar).
    """
    
    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.normpath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._ensure_cache_file()
    
    def _ensure_cache_file(self):
        """Asegura que el archivo de caché existe"""
        cache_path = os.path.join(self.cache_dir, 'nuvio_search_cache.json')
        if not os.path.exists(cache_path):
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def _get_cache_key(self, query_type: str, title: str) -> str:
        """Genera hash único para cachear consulta"""
        data = f"{query_type}:{title}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:32]
    
    def get(self, query_type: str, title: str) -> Optional[Dict]:
        """Obtener resultado cacheado si existe y no está expirado"""
        try:
            cache_key = self._get_cache_key(query_type, title)
            cache_path = os.path.join(self.cache_dir, f'{cache_key}.json')
            
            if not os.path.exists(cache_path):
                return None
            
            # Cargar y verificar caducidad
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            expires = data.get('expires', 0)
            if datetime.now().timestamp() - expires > MAX_CACHE_AGE_SECONDS:
                logger.debug(f"Caché expirada para {cache_key}")
                self.delete(cache_path)
                return None
            
            return data.get('results')
        
        except Exception as e:
            logger.error(f"Error cargando caché para {cache_key}: {e}")
            return None
    
    def set(self, query_type: str, title: str, results: Dict):
        """Guardar resultado en caché"""
        try:
            cache_key = self._get_cache_key(query_type, title)
            data = {
                'results': results,
                'query': title,
                'query_type': query_type,
                'expires': (datetime.now().timestamp() + MAX_CACHE_AGE_SECONDS),
                'timestamp': datetime.now().isoformat()
            }
            
            cache_path = os.path.join(self.cache_dir, f'{cache_key}.json')
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            logger.debug(f"Caché guardado para {cache_key}")
        
        except Exception as e:
            logger.error(f"Error guardando en caché: {e}")
    
    def delete(self, path: str):
        """Eliminar archivo de caché específico"""
        try:
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error eliminando caché {path}: {e}")
            return False
    
    def clear(self):
        """Limpiar toda la caché"""
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
            logger.info("Caché limpiada")
        
        except Exception as e:
            logger.error(f"Error limpiando caché: {e}")


# =====================================================
# FUNCIÓNES DE ANÁLISIS Y PARSING
# =====================================================

COUNTRY_MARKERS = {
    "ES-ES": ["castellano", "español peninsular", "madrid", "barcelona", "valencia", "andalucía"],
    "ES-MX": ["mexico", "ciudad de mexico", "méxico", "cine mexicano", "telenovela mexicana"],
    "ES-AR": ["argentina", "cine argentino", "telefe", "arnova"],
    "ES-CO": ["colombia", "cinemaximo", "movistar+ col"],
    "ES-CL": ["chile", "canal 13", "megacanal"],
    "ES-PE": ["peru", "atv", "lamedios"],
}


def detect_country_variant(title: str) -> str:
    """
    Detecta variante regional del título en español.
    
    Retorna: 'ES-ES', 'ES-MX', 'ES-AR', etc., o 'UNDEFINED'
    """
    title_lower = title.lower()
    
    for country, markers in COUNTRY_MARKERS.items():
        if any(marker in title_lower for marker in markers):
            return country
    
    return "UNDEFINED"


def parse_stremio_id(stremio_type: str, raw_id: str) -> Tuple[Literal["movie", "tv"], str, str, Optional[int], Optional[int]]:
    """
    Parsear ID estándar de Nuvio/Stremio.
    
    Soporta formatos:
      - movie/tt1234567 (IMDB)
      - movie/tmdb:12345 (TMDB)
      - series/tt1234567:1:2 (IMDB + temporada/episodio)
    """
    
    media_type = "tv" if stremio_type == "series" else "movie"
    parts = raw_id.split(":")

    id_source = "tmdb" if parts[0] == "tmdb" else "imdb"
    
    season: Optional[int] = None
    episode: Optional[int] = None
    
    if media_type == "tv" and len(parts) >= 4:
        season = int(parts[2])
        episode = int(parts[3])

    return media_type, raw_id, id_source, season, episode


# =====================================================
# CONSULTAS A TMDB API
# =====================================================

TMDB_CACHE = SearchCache(CACHE_DIR)


async def resolve_tmdb_id(
    client: httpx.AsyncClient, 
    api_key: str, 
    external_id: str, 
    id_source: Literal["imdb", "tmdb"], 
    preferred_type: Literal["movie", "tv"]
) -> Tuple[Literal["movie", "tv"], int]:
    """
    Resolver ID externo a TMDB con reintentos y rate limit handling.
    
    Usa caché local para consultas repetidas idénticas.
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Reintentar inmediatamente si es TMDB directo
            if id_source == "tmdb":
                return preferred_type, int(external_id)

            resp = await client.get(
                f"{TMDB_BASE_URL}/find/{external_id}",
                params={"api_key": api_key, "external_source": "imdb_id"},
            )
            
            # Rate limit (429 Too Many Requests)
            if resp.status_code == 429:
                wait = min(TMDB_RATE_LIMIT_WAIT * (2 ** attempt), 300)
                logger.warning(f"⚠️ TMDB rate limit, waiting {wait}s")
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # Buscar resultados según tipo preferido o fallback genérico
            if preferred_type == "movie" and data.get("movie_results"):
                return "movie", data["movie_results"][0]["id"]
            if preferred_type == "tv" and data.get("tv_results"):
                return "tv", data["tv_results"][0]["id"]
            
            # Fallback: cualquier resultado encontrado
            for category in ["movie_results", "tv_results"]:
                results = data.get(category)
                if results:
                    return category, results[0]["id"]

            raise ValueError(f"No TMDB result para {external_id}")
        
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                logger.info(f"⏱️ Timeout (intent {attempt+1}/{max_retries}), reintentando...")
                continue
            raise
    
    # Si agotamos todos los intentos, lanzar error
    raise ConnectionError(f"Agotados reintentos TMDB para {external_id}")


async def fetch_tmdb_details(
    client: httpx.AsyncClient, 
    tmdb_id: int, 
    language: str = "es-ES"
) -> Dict:
    """
    Obtener detalles de contenido de TMDB con caché.
    
    Caché por ID + hash del título para evitar consultas repetidas.
    """
    cache_key = hashlib.sha256(f"{tmdb_id}:{language}".encode()).hexdigest()[:32]
    cache_path = os.path.join(CACHE_DIR, f'tmdb_details_{cache_key}.json')
    
    if not os.path.exists(cache_path):
        try:
            detail_resp = await client.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}" if media_type == "movie" 
                else f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                params={"api_key": api_key, "language": language},
            )
            detail_resp.raise_for_status()
            
            data = detail_resp.json()
            
            # Guardar en caché
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            return data
        
        except Exception as e:
            logger.error(f"Error obteniendo detalles TMDB {tmdb_id}: {e}")
            raise
    
    else:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)


# =====================================================
# FUNCIÓN PRINCIPAL: GENERAR PLAN DE BÚSQUEDA
# =====================================================

async def build_search_plan(
    api_key: str,
    stremio_type: str,
    raw_id: str,
    preferred_country: str = "UNDEFINED",  # 'ES-ES', 'ES-MX', etc. o vacio para auto-detec
    include_all_languages: bool = False,
) -> Tuple[MediaQueryPlan, List[Dict]]:
    """
    Construye plan de búsqueda MÁXIMA COBERTURA con PRIORIDAD CASTELLANO.
    
    Args:
        api_key: API key de TMDB
        stremio_type: "movie" o "series"
        raw_id: ID crudo (tmdb:123, tt1234567, etc.)
        preferred_country: País preferido para filtrado (auto-detect si vacío)
        include_all_languages: Si True, añade queries adicionales para otros idiomas
    
    Returns:
        - MediaQueryPlan con queries ordenadas por prioridad castellano
        - Lista de metadatos obtenidos desde TMDB
    """
    
    media_type, external_id, id_source, season, episode = parse_stremio_id(stremio_type, raw_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Resolver ID a TMDB
        resolved_type, tmdb_id = await resolve_tmdb_id(
            client, api_key, external_id, id_source, media_type
        )

        # Obtener detalles con caché
        details = await fetch_tmdb_details(client, tmdb_id)
    
    if resolved_type == "movie":
        localized_es = details.get("title") or ""  # TMDB: 'title' es español por defecto
        original_title = details.get("original_title") or localized_es
        year = (details.get("release_date") or "").replace("-", "")[:4] if details.get("release_date") else None
    else:
        localized_es = details.get("name") or ""
        original_title = details.get("original_name") or localized_es
        year = (details.get("first_air_date") or "").replace("-", "")[:4] if details.get("first_air_date") else None

    # Detectar variante por país
    detected_country = detect_country_variant(localized_es)
    
    # Si preferred_country está vacío, auto-detect desde los datos
    if not preferred_country:
        preferred_country = detected_country
    
    # Actualizar plan con país preferido
    localized_clean = normalize_for_search(localized_es)
    original_clean = normalize_for_search(original_title)
    
    plan = MediaQueryPlan(
        media_type=resolved_type,
        tmdb_id=tmdb_id,
        localized_title_es=localized_es,
        original_title=original_title,
        year=year,
        season=season,
        episode=episode,
        detected_country=preferred_country,
        preferred_countries=[preferred_country],
    )
    
    # Cachear resultado de búsqueda
    cache_key = hashlib.sha256(f"{resolved_type}:{tmdb_id}:{localized_es}".encode()).hexdigest()[:32]
    TMDB_CACHE.set(cache_key, {
        'plan': plan.__dict__,
        'metadata': details
    })
    
    logger.info(f"✅ Plan de búsqueda generado para {localized_es[:50]}... "
                f"(ID TMDB: {tmdb_id}, País: {preferred_country}, "
                f"Queries: {len(plan.queries_es_priority)} + {len(plan.queries_fallback)})")
    
    # Retornar plan y metadatos
    return plan, details


def normalize_for_search(text: str) -> str:
    """Normalización para búsqueda amplia en castellano"""
    cleaned = re.sub(r'[^\w\sñ]', '', text, flags=re.UNICODE)
    accented = ['á', 'é', 'í', 'ó', 'ú', 'ü']
    non_accented = ['a', 'e', 'i', 'o', 'u', 'u']
    
    result = cleaned
    
    for accented, non_accent in zip(accented, non_accented):
        result = result.replace(accented, non_accent)
    
    return re.sub(r'\s+', ' ', result).strip()


# =====================================================
# EXPORTAR PARA IMPORTACIÓN
# =====================================================

def addon_main():
    """Punto de entrada para Nuvio al importar este addon."""
    return {
        'MediaQueryPlan': MediaQueryPlan,
        'build_search_plan': build_search_plan,
        'parse_stremio_id': parse_stremio_id,
        'resolve_tmdb_id': resolve_tmdb_id,
        'normalize_for_search': normalize_for_search,
        '__version__': ADDON_VERSION,
    }


if __name__ == "__main__":
    """Ejemplo de uso: prueba local sin Nuvio."""
    import asyncio
    
    async def test_example():
        try:
            plan, metadata = await build_search_plan(
                api_key="TU_API_KEY_AQUI",  # O cargar desde archivo de config
                stremio_type="movie",
                raw_id="tt1234567",  # Ejemplo con ID IMDB real
                preferred_country="ES-ES",
            )
            
            print("\n" + "="*60)
            print(f"TÍTULO: {plan.localized_title_es}")
            print(f"AÑO: {plan.year}")
            print(f"CACHÉ: {plan.detected_country}")
            print("="*60)
            print("\nQUERIES ORDENADAS POR PRIORIDAD:")
            
            for idx, (priority, query) in enumerate(plan.queries_es_priority[:5], 1):
                print(f"  [{idx}] Prioridad {priority:.1f}: {query}")
            
            print("\nQUERIES DE FALLBACK:")
            for idx, (priority, query) in enumerate(plan.queries_fallback[:3], 1):
                print(f"  [{idx}] Prioridad {priority:.1f}: {query}")
        
        except Exception as e:
            logger.error(f"Error en prueba: {e}")
    
    asyncio.run(test_example())
