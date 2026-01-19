import re
from bs4 import BeautifulSoup
import csv
import json

def extraer_instituciones(archivo_html):
    """
    Extrae instituciones y sus IDs de un archivo HTML de LeyChile
    
    Args:
        archivo_html: ruta al archivo HTML
    
    Returns:
        lista de diccionarios con 'institucion' e 'id'
    """
    # Leer el archivo HTML
    with open(archivo_html, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    # Parsear con BeautifulSoup
    soup = BeautifulSoup(contenido, 'html.parser')
    
    instituciones = []
    instituciones_vistas = set()  # Para evitar duplicados
    
    # Buscar el contenedor principal
    container = soup.find('div', class_='d-flex flex-wrap mt-3 row')
    
    if not container:
        print("No se encontró el contenedor principal")
        return instituciones
    
    # Buscar solo los divs hijos directos que contienen las cards
    # Evitamos las cards anidadas buscando solo en el primer nivel
    for child_div in container.find_all('div', recursive=False):
        card = child_div.find('div', class_='card card-body', recursive=False)
        
        if not card:
            continue
            
        try:
            # Extraer el nombre de la institución del enlace en h4
            h4 = card.find('h4', class_='card-title', recursive=False)
            if not h4:
                continue
            
            # Buscar el primer enlace (el que no está anidado)
            link = h4.find('a', recursive=False)
            if not link:
                continue
                
            institucion = link.get_text(strip=True)
            
            # Extraer el ID del parámetro agr en el href
            href = link.get('href', '')
            id_match = re.search(r'agr=(\d+)', href)
            
            if not id_match:
                continue
                
            id_institucion = id_match.group(1)
            
            # Verificar que no sea duplicado
            clave = f"{institucion}_{id_institucion}"
            if clave in instituciones_vistas:
                continue
                
            instituciones_vistas.add(clave)
            
            instituciones.append({
                'institucion': institucion,
                'id': id_institucion
            })
            
        except Exception as e:
            print(f"Error procesando una card: {e}")
            continue
    
    return instituciones


def guardar_csv(datos, archivo_salida='instituciones.csv'):
    """Guarda los datos en formato CSV"""
    with open(archivo_salida, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['institucion', 'id'])
        writer.writeheader()
        writer.writerows(datos)
    print(f"Datos guardados en {archivo_salida}")


def guardar_json(datos, archivo_salida='instituciones.json'):
    """Guarda los datos en formato JSON"""
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"Datos guardados en {archivo_salida}")


def main():
    # Nombre del archivo HTML a procesar
    archivo_html = 'instituciones.html' 
    
    print("Extrayendo datos...")
    instituciones = extraer_instituciones(archivo_html)
    
    print(f"\nTotal de instituciones encontradas: {len(instituciones)}")
    
    # Mostrar las primeras 5 como muestra
    print("\nPrimeras 5 instituciones:")
    for inst in instituciones[:5]:
        print(f"  - {inst['institucion']} (ID: {inst['id']})")
    
    # Guardar en ambos formatos
    guardar_csv(instituciones)
    guardar_json(instituciones)
    
    # Retornar los datos para uso posterior
    return instituciones


if __name__ == "__main__":
    datos = main()