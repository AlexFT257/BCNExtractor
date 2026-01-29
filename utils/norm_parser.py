import xml.etree.ElementTree as ET
from typing import Optional, List
from datetime import date
from utils.norm_types import Norm


class BCNXMLParser:
    """
    Parser para convertir XML de normas BCN a Markdown.
    
    Uso:
        parser = BCNXMLParser()
        markdown, metadata = parser.parse_from_file('norma.xml')
        # O desde string:
        markdown, metadata = parser.parse_from_string(xml_string)
    """
    
    def __init__(self, namespace: str = "http://www.leychile.cl/esquemas"):
        self.ns = {'bcn': namespace}
    
    def parse_from_file(self, filepath: str) -> tuple[str, Norm]:
        """Parsea un archivo XML y retorna Markdown y metadatos"""
        tree = ET.parse(filepath)
        root = tree.getroot()
        return self._parse_norma(root)
    
    def parse_from_string(self, xml_string: str) -> tuple[str, Norm]:
        """Parsea un string XML y retorna Markdown y metadatos"""
        root = ET.fromstring(xml_string)
        return self._parse_norma(root)
    
    def _parse_norma(self, root: ET.Element) -> tuple[str, Norm]:
        """Procesa el elemento raíz Norma"""
        md_parts = []
        
        # Extraer metadatos
        metadata = self._extract_metadata(root)
        
        # Título principal
        md_parts.append(f"# {metadata.titulo}\n")
        
        # Información básica
        md_parts.append(self._format_info_basica(metadata))
        
        # Encabezado
        encabezado = root.find('bcn:Encabezado', self.ns)
        if encabezado is not None:
            md_parts.append(self._parse_encabezado(encabezado))
        
        # Estructuras Funcionales (Articulado)
        estructuras = root.find('bcn:EstructurasFuncionales', self.ns)
        if estructuras is not None:
            md_parts.append(self._parse_estructuras(estructuras))
        
        # Promulgación
        promulgacion = root.find('bcn:Promulgacion', self.ns)
        if promulgacion is not None:
            md_parts.append(self._parse_promulgacion(promulgacion))
        
        # Anexos
        anexos = root.find('bcn:Anexos', self.ns)
        if anexos is not None:
            md_parts.append(self._parse_anexos(anexos))
        
        return '\n'.join(md_parts), metadata
    
    def _extract_metadata(self, root: ET.Element) -> Norm:
        """Extrae metadatos de la norma"""
        identificador = root.find('bcn:Identificador', self.ns)
        metadatos = root.find('bcn:Metadatos', self.ns)
        
        # Tipo y número
        tipo_numero = identificador.find('.//bcn:TipoNumero', self.ns)
        tipo = tipo_numero.find('bcn:Tipo', self.ns).text
        numero = tipo_numero.find('bcn:Numero', self.ns).text
        
        # Organismos
        organismos = [
            org.text for org in identificador.findall('.//bcn:Organismo', self.ns)
        ]
        
        # Fechas
        fecha_pub = identificador.get('fechaPublicacion')
        fecha_prom = identificador.get('fechaPromulgacion')
        
        # Título
        titulo = metadatos.find('bcn:TituloNorma', self.ns).text
        
        # Materias
        materias = [
            mat.text for mat in metadatos.findall('.//bcn:Materia', self.ns)
        ]
        
        return Norm(
            norma_id=int(root.get('normaId')),
            tipo=tipo,
            numero=numero,
            titulo=titulo,
            fecha_publicacion=self._parse_date(fecha_pub),
            fecha_promulgacion=self._parse_date(fecha_prom),
            organismos=organismos,
            derogado=root.get('derogado') == 'derogado',
            es_tratado=root.get('esTratado') == 'tratado',
            materias=materias
        )
    
    def _format_info_basica(self, metadata: Norm) -> str:
        """Formatea la información básica como Markdown"""
        lines = ["\n## Información Básica\n"]
        
        lines.append(f"**Tipo:** {metadata.tipo}  ")
        lines.append(f"**Número:** {metadata.numero}  ")
        
        if metadata.fecha_publicacion:
            lines.append(f"**Fecha de Publicación:** {metadata.fecha_publicacion}  ")
        
        if metadata.fecha_promulgacion:
            lines.append(f"**Fecha de Promulgación:** {metadata.fecha_promulgacion}  ")
        
        if metadata.organismos:
            lines.append(f"**Organismo(s):** {', '.join(metadata.organismos)}  ")
        
        if metadata.derogado:
            lines.append("**Estado:** DEROGADO  ")
        
        if metadata.materias:
            lines.append(f"\n**Materias:** {', '.join(metadata.materias)}")
        
        return '\n'.join(lines) + '\n'
    
    def _parse_encabezado(self, encabezado: ET.Element) -> str:
        """Parsea el encabezado de la norma"""
        texto = encabezado.find('bcn:Texto', self.ns)
        if texto is not None and texto.text:
            return f"\n## Encabezado\n\n{self._clean_text(texto.text)}\n"
        return ""
    
    def _parse_estructuras(self, estructuras: ET.Element, level: int = 2) -> str:
        """Parsea las estructuras funcionales (articulado) recursivamente"""
        md_parts = []
        
        for estructura in estructuras.findall('bcn:EstructuraFuncional', self.ns):
            md_parts.append(self._parse_estructura(estructura, level))
        
        return '\n'.join(md_parts)
    
    def _parse_estructura(self, estructura: ET.Element, level: int) -> str:
        """Parsea una estructura funcional individual"""
        md_parts = []
        
        tipo_parte = estructura.get('tipoParte')
        metadatos = estructura.find('bcn:Metadatos', self.ns)
        
        # Título de la parte
        if metadatos is not None:
            nombre = metadatos.find('bcn:NombreParte', self.ns)
            titulo = metadatos.find('bcn:TituloParte', self.ns)
            
            if nombre is not None and nombre.get('presente') == 'si':
                md_parts.append(f"\n{'#' * level} {nombre.text}")
            
            if titulo is not None and titulo.get('presente') == 'si':
                if nombre is None or nombre.get('presente') == 'no':
                    md_parts.append(f"\n{'#' * level} {titulo.text}")
                else:
                    md_parts.append(f"**{titulo.text}**")
        
        # Texto de la estructura
        texto = estructura.find('bcn:Texto', self.ns)
        if texto is not None and texto.text:
            md_parts.append(f"\n{self._clean_text(texto.text)}")
        
        # Estado
        if estructura.get('derogado') == 'derogado':
            md_parts.append("\n*[DEROGADO]*")
        
        if estructura.get('transitorio') == 'transitorio':
            md_parts.append("\n*[TRANSITORIO]*")
        
        # Sub-estructuras (recursivo)
        sub_estructuras = estructura.find('bcn:EstructurasFuncionales', self.ns)
        if sub_estructuras is not None:
            md_parts.append(self._parse_estructuras(sub_estructuras, level + 1))
        
        return '\n'.join(md_parts)
    
    def _parse_promulgacion(self, promulgacion: ET.Element) -> str:
        """Parsea la sección de promulgación"""
        texto = promulgacion.find('bcn:Texto', self.ns)
        if texto is not None and texto.text:
            return f"\n## Promulgación\n\n{self._clean_text(texto.text)}\n"
        return ""
    
    def _parse_anexos(self, anexos_elem: ET.Element) -> str:
        """Parsea los anexos de la norma"""
        md_parts = ["\n## Anexos\n"]
        
        for anexo in anexos_elem.findall('bcn:Anexo', self.ns):
            metadatos = anexo.find('bcn:Metadatos', self.ns)
            titulo = metadatos.find('bcn:Titulo', self.ns).text
            
            md_parts.append(f"\n### {titulo}\n")
            
            texto = anexo.find('bcn:Texto', self.ns)
            if texto is not None and texto.text:
                md_parts.append(self._clean_text(texto.text))
        
        return '\n'.join(md_parts)
    
    def _clean_text(self, text: str) -> str:
        """Limpia y formatea el texto"""
        if not text:
            return ""
        
        # Eliminar espacios extras y normalizar saltos de línea
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        
        return '\n'.join(lines)
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Convierte string de fecha a objeto date"""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except:
            return None


# Ejemplo de uso
if __name__ == "__main__":
    parser = BCNXMLParser()
    markdown, metadata = parser.parse_from_file("./data/sample/norma_completa.xml")
    
    print("MARKDOWN GENERADO:")
    print("=" * 80)
    print(markdown)
    print("\n" + "=" * 80)
    print("\nMETADATOS:")
    print(metadata)