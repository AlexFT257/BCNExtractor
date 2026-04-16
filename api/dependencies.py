from functools import lru_cache

from bcn_client import BCNClient
from managers.downloads import DownloadManager
from managers.institutions import InstitutionManager
from managers.norms import NormsManager
from managers.norms_types import TiposNormasManager
from managers.metadata import MetadataManager
from utils.norm_parser import BCNXMLParser


@lru_cache
def get_client() -> BCNClient:
    return BCNClient()


@lru_cache
def get_parser() -> BCNXMLParser:
    return BCNXMLParser()


@lru_cache
def get_norm_manager() -> NormsManager:
    return NormsManager()


@lru_cache
def get_institution_manager() -> InstitutionManager:
    return InstitutionManager()


@lru_cache
def get_tipos_manager() -> TiposNormasManager:
    return TiposNormasManager()


@lru_cache
def get_download_logger() -> DownloadManager:
    return DownloadManager()
    
@lru_cache
def get_metadata_manager() -> MetadataManager:
    return MetadataManager()