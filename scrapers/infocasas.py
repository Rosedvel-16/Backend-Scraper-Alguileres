import re
import os 
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

from .common import (
    slugify_zone
)

SCRAPINGBEE_API_URL = "https://api.scrapingbee.com/v1/"
API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")

def scrape_infocasas(zona: str = "", dormitorios: str = "0", banos: str = "0",
                        price_min: Optional[int] = None, price_max: Optional[int] = None,
                        palabras_clave: str = "", max_pages: int = 5): # max_scrolls cambiado a max_pages
    
    # ⚠️ VERIFICACIÓN DE CLAVE API
    if not API_KEY:
        print("❌ Error: Variable de entorno SCRAPINGBEE_API_KEY no encontrada.")
        return pd.DataFrame()

    # Mapeo específico para InfoCasas
    ZONA_MAPEO_INFOCASAS = {
        "ancón": "ancon", "ate": "ate", "barranco": "barranco", "breña": "breña", "carabayllo": "carabayllo",
        "chaclacayo": "chaclacayo", "chorrillos": "chorrillos", "cieneguilla": "cieneguilla", "comas": "comas",
        "el agustino": "el-agustino", "independencia": "independencia", "jesús maría": "jesus-maria",
        "la molina": "la-molina", "la victoria": "la-victoria", "lima": "lima-cercado", "lince": "lince",
        "los olivos": "los-olivos", "lurigancho": "lurigancho", "lurín": "lurin", "magdalena del mar": "magdalena-del-mar",
        "miraflores": "miraflores", "pachacámac": "pachacamac", "pucusana": "pucusana", "pueblo libre": "pueblo-libre",
        "puente piedra": "puente-piedra", "punta hermosa": "punta-hermosa", "punta negra": "punta-negra", "rímac": "rimac",
        "san bartolo": "san-bartolo", "san borja": "san-borja", "san isidro": "san-isidro", "san juan de lurigancho": "san-juan-de-lurigancho",
        "san juan de miraflores": "san-juan-de-miraflores", "san luis": "san-luis", "san martín de porres": "san-martin-de-porres",
        "san miguel": "san-miguel", "santa anita": "santa-anita", "santa maría del mar": "santa-maria-del-mar",
        "santa rosa": "santa-rosa", "santiago de surco": "santiago-de-surco", "surquillo": "surquillo",
        "villa el salvador": "villa-el-salvador", "villa maría del triunfo": "villa-maria-del-triunfo"
    }

    results = []
    seen_links = set()
    
    for page_num in range(1, max_pages + 1):
        
        # --- 1. Construir URL base según la zona ---
        if zona and zona.strip():
            zona_lower = zona.strip().lower()
            zone_slug = ZONA_MAPEO_INFOCASAS.get(zona_lower, slugify_zone(zona))
            base = f"https://www.infocasas.com.pe/alquiler/casas-y-departamentos/lima/{zone_slug}"
        else:
            base = "https://www.infocasas.com.pe/alquiler/casas-y-departamentos"
            
        # --- 2. Agregar filtros y paginación ---
        # InfoCasas tiene una estructura de URL compleja para filtros
        url_filters = ""
        if dormitorios and dormitorios != "0":
            url_filters += f"/{dormitorios}-dormitorio"
        if banos and banos != "0":
            url_filters += f"/{banos}-bano"
        if price_min is not None:
            url_filters += f"/desde-{price_min}"
        if price_max is not None:
            url_filters += f"/hasta-{price_max}"
        
        infocasas_url = base + url_filters
        
        query_params = []
        if price_min is not None or price_max is not None:
            query_params.append("IDmoneda=6") # Soles
            
        if palabras_clave and palabras_clave.strip():
            query_params.append(f"searchstring={requests.utils.quote(palabras_clave.strip())}")

        # Añadir la paginación como un query param (funciona para todas las estructuras)
        query_params.append(f"page={page_num}") 

        if query_params:
            infocasas_url += "?" + "&".join(query_params)
            
        print(f"URL de InfoCasas (Pág {page_num}): {infocasas_url}")

        # --- 3. Configurar y llamar a ScrapingBee ---
        payload = {
            'api_key': API_KEY,
            'url': infocasas_url,
            'render_js': 'true', # Habilitar JS rendering (necesario para la carga dinámica)
            'wait': 3000,        # Esperar 3 segundos para que carguen los elementos
            'scroll_to_bottom': 'true' # Scroll automático (útil para cargar todos los listados)
        }
        
        try:
            response = requests.get(SCRAPINGBEE_API_URL, params=payload, timeout=40)
            
            if response.status_code != 200:
                print(f"❌ Error ScrapingBee (Pág {page_num}): Código {response.status_code}")
                if page_num == 1:
                    return pd.DataFrame()
                break

            soup = BeautifulSoup(response.text, "html.parser")
            
            # --- 4. Extracción de datos ---
            nodes = soup.select("div.listingCard") or soup.select("article[data-id]")
            
            if not nodes:
                print(f"⚠️ No se encontraron anuncios en la página {page_num}. Terminando.")
                if page_num > 1:
                    break
            
            new_results_found = False

            for n in nodes:
                try:
                    a = n.select_one("a[href]")
                    if not a:
                        continue

                    href = a.get("href") if a else ""
                    if href and href.startswith("/"):
                        href = "https://www.infocasas.com.pe" + href

                    if href in seen_links:
                        continue
                    seen_links.add(href)
                    new_results_found = True

                    # Extracción de campos
                    title_elem = n.select_one("h2.lc-title") or n.select_one(".lc-title") or a
                    title = title_elem.get_text(" ", strip=True) if title_elem else n.get_text(" ", strip=True)[:250]

                    price_elem = n.select_one(".main-price") or n.select_one(".lc-price p") or n.select_one(".property-price-tag p")
                    price = price_elem.get_text(" ", strip=True) if price_elem else ""

                    desc_elem = n.select_one(".lc-description") or n.select_one("p.lc-description")
                    desc = desc_elem.get_text(" ", strip=True) if desc_elem else n.get_text(" ", strip=True)[:400]

                    # Características
                    dormitorios_text = ""
                    banos_text = ""
                    m2_text = ""
                    typology_items = n.select(".lc-typologyTag__item strong")
                    for item in typology_items:
                        text = item.get_text().strip()
                        if "Dorm" in text:
                            dorm_match = re.search(r'(\d+)', text)
                            if dorm_match:
                                dormitorios_text = dorm_match.group(1)
                        elif "Baños" in text or "Baño" in text:
                            banos_match = re.search(r'(\d+)', text)
                            if banos_match:
                                banos_text = banos_match.group(1)
                        elif "m²" in text:
                            m2_match = re.search(r'(\d+)', text)
                            if m2_match:
                                m2_text = m2_match.group(1)

                    # Imagen
                    img_url = ""
                    img_tag = n.select_one(".cardImageGallery .gallery-image img") or n.select_one(".cardImageGallery img")
                    if img_tag:
                        img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img_url and img_url.startswith("//"):
                            img_url = "https:" + img_url
                        img_url = img_url.strip()

                    results.append({
                        "titulo": title,
                        "precio": price,
                        "m2": m2_text,
                        "dormitorios": dormitorios_text,
                        "baños": banos_text,
                        "descripcion": desc,
                        "link": href,
                        "imagen_url": img_url
                    })
                except Exception:
                    continue
            
            # Si se encuentra el final de la lista o no hay nuevos resultados
            if not new_results_found and page_num > 1:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con ScrapingBee (Pág {page_num}): {e}")
            break # Salir en caso de error de red o timeout

    return pd.DataFrame(results)