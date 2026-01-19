import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.sessions import Request
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BCNClient:
    """Cliente para la API de BCN."""

    # URLs base de los servicios
    BASE_URL = "https://www.leychile.cl"

    # Endpoints específicos
    ENDPOINTS = {
        "metadatos": "/Consulta/obtxml?opt=4546&idNorma={}",  # Metadatos + encabezado
        "norma_completa": "/Consulta/obtxml?opt=7&idNorma={}",  # XML completo
        "normas_institucion": "/Consulta/obtxml?opt=6&idCategoria={}&down=True",  # Por institución
    }

    def __init__(
        self,
        cache_dir: str = "data/cache",
        rate_limit_delay: float = 0.5,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0

        self.session = self._create_session(max_retries)

        logger.info(f"BCN Client inicializado (cache={self.cache_dir})")

    def _create_session(self, max_retries: int) -> requests.Session:
        session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/xml, text/xml, */*",
                "Accept-Language": "es-CL,es;q=0.9",
            }
        )

        return session

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _get_cache_path(self, cache_key: str) -> Path:
        hash_key = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.xml"

    def _read_cache(self, cache_key: str) -> Optional[str]:
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            logger.debug(f"Cache HIT: {cache_key}")
            return cache_path.read_text(encoding="utf-8")

        return None

    def _write_cache(self, cache_key: str, content: str):
        cache_path = self._get_cache_path(cache_key)
        cache_path.write_text(content, encoding="utf-8")
        logger.debug(f"Cache WRITE: {cache_key}")

    def _make_request(
        self, url: str, use_cache: bool = True, cache_key: Optional[str] = None
    ) -> Optional[str]:
        cache_key = cache_key or url

        if use_cache:
            cached = self._read_cache(cache_key)
            if cached:
                return cached

        self._rate_limit()

        try:
            logger.info(f"Request: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            content = response.text

            if use_cache:
                self._write_cache(cache_key, content)

            return content

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code}: {url}")
            return None

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out: {url}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request fallo: {url} - {e}")
            return None

        except Exception as e:
            logger.error(f"Error inesperado: {url} - {e}")
            return None

    def get_normas_por_institucion(
        self, id_institucion: int, use_cache: bool = True
    ) -> Optional[List[Dict]]:
        url = self.BASE_URL + self.ENDPOINTS["normas_institucion"].format(
            id_institucion
        )

        xml_content = self._make_request(url, use_cache=use_cache)

        if not xml_content:
            return None

        try:
            root = ET.fromstring(xml_content)
            normas = []

            # El XML tiene estructura: <NORMAS_CONVENIO><NORMA>...</NORMA></NORMAS_CONVENIO>
            for norma_elem in root.findall(".//NORMA"):
                # Extraer ID de la norma desde la URL
                url_norma = norma_elem.findtext("URL", "")
                id_norma = None

                # Extraer idNorma del URL (formato: ...?idNorma=12345)
                import re

                match = re.search(r"idNorma=(\d+)", url_norma)
                if match:
                    id_norma = int(match.group(1))

                # Extraer tipo y número desde TIPOS_NUMEROS
                tipo_numero_elem = norma_elem.find(".//TIPO_NUMERO")
                numero = None
                abreviatura = None
                tipo_norma = None
                id_tipo_norma = None  # Codigo de la bcn

                if tipo_numero_elem is not None:
                    numero = tipo_numero_elem.findtext("NUMERO")
                    abreviatura = tipo_numero_elem.findtext("ABREVIACION")
                    tipo_norma = tipo_numero_elem.findtext("DESCRIPCION")
                    id_tipo_norma = tipo_numero_elem.findtext("TIPO")
                    # remover formato (ej:XX13->13) si existe
                    if id_tipo_norma:
                        id_tipo_norma = int(id_tipo_norma.strip("X"))

                # Extraer organismos
                organismos = []
                for org in norma_elem.findall(".//ORGANISMO"):
                    if org.text:
                        organismos.append(org.text.strip())

                norma = {
                    "id": id_norma,
                    "tipo": tipo_norma,
                    "id_tipo": id_tipo_norma,  # Desde TIPO_NUMEROS -> TIPO aka id tipo
                    "numero": numero,  # Numero de la norma (ej: Decreto 179, Ley 21517)
                    "abreviatura": abreviatura,
                    "titulo": norma_elem.findtext("TITULO", "").strip(),
                    "materia": norma_elem.findtext("MATERIA", "").strip(),
                    "fecha_promulgacion": norma_elem.findtext("FECHA_PROMULGACION"),
                    "fecha_publicacion": norma_elem.findtext("FECHA_PUBLICACION"),
                    "organismos": organismos,
                    "url": url_norma,
                }

                # Solo agregar si tiene ID válido
                if norma["id"]:
                    normas.append(norma)
                else:
                    logger.warning(f"Norma sin ID válido: {norma['titulo'][:50]}")

            logger.info(
                f"Institución {id_institucion}: {len(normas)} normas encontradas"
            )
            return normas

        except ET.ParseError as e:
            logger.error(f"Error parseando XML: {e}")
            return None

    def get_norma_metadatos(
        self, id_norma: int, use_cache: bool = True
    ) -> Optional[str]:
        url = self.BASE_URL + self.ENDPOINTS["metadatos"].format(id_norma)
        return self._make_request(url, use_cache=use_cache)

    def get_norma_completa(
        self, id_norma: int, use_cache: bool = True
    ) -> Optional[str]:
        url = self.BASE_URL + self.ENDPOINTS["norma_completa"].format(id_norma)
        return self._make_request(url, use_cache=use_cache)
        
    def download_normas_institucion(
        self,
        id_institucion: int,
        download_full: bool = True,
        limit: Optional[int] = None,
        callback=None
    ) -> Dict:
        
        stats = {
            'total': 0,
            'exitosas': 0,
            'fallidas': 0,
            'omitidas': 0,
            'inicio': datetime.now(),
            'fin': None
        }
        
        logger.info(f"Iniciando descarga de normas - Institución: {id_institucion}")
        
        # Obtener lista de normas
        normas = self.get_normas_por_institucion(id_institucion)
        if not normas:
            logger.error("No se pudo obtener lista de normas")
            return stats
        
        stats['total'] = len(normas)
        
        # Aplicar límite si se especifica
        if limit:
            normas = normas[:limit]
            logger.info(f"Limitando descarga a {limit} normas")
        
        # Descargar cada norma
        for i, norma_info in enumerate(normas, 1):
            id_norma = int(norma_info['id_norma'])
            
            logger.info(f"[{i}/{len(normas)}] Descargando norma {id_norma}: {norma_info['titulo'][:50]}...")
            
            try:
                # Descargar XML (completo o solo metadatos)
                if download_full:
                    xml_content = self.get_norma_completa(id_norma)
                else:
                    xml_content = self.get_norma_metadatos(id_norma)
                
                if xml_content:
                    stats['exitosas'] += 1
                    
                    # Llamar callback si se proporciona
                    if callback:
                        try:
                            callback(norma_info, xml_content)
                        except Exception as e:
                            logger.error(f"Error en callback para norma {id_norma}: {e}")
                else:
                    stats['fallidas'] += 1
                    
            except Exception as e:
                logger.error(f"Error descargando norma {id_norma}: {e}")
                stats['fallidas'] += 1
        
        stats['fin'] = datetime.now()
        duracion = (stats['fin'] - stats['inicio']).total_seconds()
        
        logger.info('-'*50)
        logger.info("DESCARGA COMPLETADA")
        logger.info(f"\tTotal:     {stats['total']}")
        logger.info(f"\tExitosas:  {stats['exitosas']}")
        logger.info(f"\tFallidas:  {stats['fallidas']}")
        logger.info(f"\tDuración:  {duracion:.1f}s")
        logger.info('-'*50)
        
        return stats

    def get_cache_stats(self) -> Dict:
        cache_files = list(self.cache_dir.glob("*.xml"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "total_archivos": len(cache_files),
            "tamano_total_mb": total_size / (1024 * 1024),
            "directorio": str(self.cache_dir),
        }

    def clear_cache(self):
        cache_files = list(self.cache_dir.glob("*.xml"))
        for f in cache_files:
            f.unlink()
        logger.info(f"Caché limpiado: {len(cache_files)} archivos eliminados")

    def close(self):
        self.session.close()
        logger.info("BCN Client cerrado")
