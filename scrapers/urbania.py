import re
import os 
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

from .common import (
    slugify_zone,
)

SCRAPINGBEE_API_URL = "https://api.scrapingbee.com/v1/"
API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")

# -------------------- Urbania --------------------
def scrape_urbania(zona: str = "", dormitorios: str = "0", banos: str = "0",
                     price_min: Optional[int] = None, price_max: Optional[int] = None,
                     palabras_clave: str = "", max_pages: int = 6, **kwargs): # Eliminamos wait_time ya que no es necesario
    
    if not API_KEY:
        print("❌ Error: Variable de entorno SCRAPINGBEE_API_KEY no encontrada.")
        return pd.DataFrame()
        
    zona = (zona or "").strip()
    kw_parts = []
    if palabras_clave and palabras_clave.strip():
        kw_parts.append(palabras_clave.strip())
    if dormitorios and str(dormitorios) != "0":
        kw_parts.append(f"{dormitorios} dormitorios")
    if banos and str(banos) != "0":
        kw_parts.append(f"{banos} banos")
    keyword_value = " ".join(kw_parts).strip()
    
    # --- Construcción de la URL de Urbania ---
    if zona:
        # Mapeo específico para Urbania
        ZONA_MAPEO_URBANIA = {
            "ancón": "ancon",
            "ate": "ate-vitarte",
            "barranco": "barranco",
            "breña": "brena",
            "carabayllo": "carabayllo",
            "chaclacayo": "chaclacayo",
            "chorrillos": "chorrillos",
            "cieneguilla": "cieneguilla",
            "comas": "comas",
            "el agustino": "el-agustino",
            "independencia": "independencia",
            "jesús maría": "jesus-maria",
            "la molina": "la-molina",
            "la victoria": "la-victoria",
            "lima": "lima-cercado",
            "lince": "lince",
            "los olivos": "los-olivos",
            "lurigancho": "lurigancho",
            "lurín": "lurin",
            "magdalena del mar": "magdalena-del-mar",
            "miraflores": "miraflores",
            "pachacámac": "pachacamac",
            "pucusana": "pucusana",
            "pueblo libre": "pueblo-libre",
            "puente piedra": "puente-piedra",
            "punta hermosa": "punta-hermosa",
            "punta negra": "punta-negra",
            "rímac": "rimac",
            "san bartolo": "san-bartolo",
            "san borja": "san-borja",
            "san isidro": "san-isidro",
            "san juan de lurigancho": "san-juan-de-lurigancho",
            "san juan de miraflores": "san-juan-de-miraflores",
            "san luis": "san-luis",
            "san martín de porres": "san-martin-de-porres",
            "san miguel": "san-miguel",
            "santa anita": "santa-anita",
            "santa maría del mar": "santa-maria-del-mar",
            "santa rosa": "santa-rosa",
            "santiago de surco": "santiago-de-surco",
            "surquillo": "surquillo",
            "villa el salvador": "villa-el-salvador",
            "villa maría del triunfo": "villa-maria-del-triunfo"
        }
        zona_lower = zona.strip().lower()
        zone_slug = ZONA_MAPEO_URBANIA.get(zona_lower, slugify_zone(zona))
        base = f"https://urbania.pe/buscar/alquiler-de-departamentos-en-{zone_slug}--lima--lima"
    else:
        base = "https://urbania.pe/buscar/alquiler-de-departamentos"
        
    params_urbania = []
    if keyword_value:
        params_urbania.append(f"keyword={requests.utils.quote(keyword_value)}")
    if price_min is not None:
        params_urbania.append(f"priceMin={price_min}")
    if price_max is not None:
        params_urbania.append(f"priceMax={price_max}")
    if dormitorios and dormitorios != "0":
        params_urbania.append(f"bedroomMin={dormitorios}")
    if banos and banos != "0":
        params_urbania.append(f"bathroomMin={banos}")
    if price_min is not None or price_max is not None:
        params_urbania.append("currencyId=6") 
        
    # Urbania soporta paginación por la URL
    all_results = []
    seen = set()
    
    for page_num in range(1, max_pages + 1):
        # 1. Construir la URL completa de Urbania con paginación
        current_params = params_urbania + [f"page={page_num}"]
        urbania_url = base + ("?" + "&".join(current_params) if current_params else "")
        print(f"URL de Urbania (Pág {page_num}): {urbania_url}")

        # 2. Configurar los parámetros de ScrapingBee
        payload = {
            'api_key': API_KEY,
            'url': urbania_url,
            'render_js': 'true', # CRUCIAL: Necesario para renderizar el contenido dinámico
            'wait': 4000 # Esperar 4 segundos (4000ms) para que todo cargue
        }
        
        # 3. Llamar a la API de ScrapingBee
        try:
            response = requests.get(SCRAPINGBEE_API_URL, params=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Error ScrapingBee (Pág {page_num}): Código {response.status_code}")
                # Si es la primera página y falla, paramos. Si es una página posterior, intentamos parar la paginación.
                if page_num == 1:
                    return pd.DataFrame()
                break # Salir del bucle de paginación
            
            # El HTML renderizado está en response.text
            soup = BeautifulSoup(response.text, "html.parser")

            # 4. Extracción de datos (tu lógica de BeautifulSoup)
            card_selectors = [
                "div[data-qa='posting PROPERTY']",
                "article",
                "div.postingCard", # Este es un selector común en su diseño
                "div[class*='postingCard']",
            ]
            cards = []
            for sel in card_selectors:
                found = soup.select(sel)
                if found:
                    cards = found
                    break
            
            if not cards:
                print(f"⚠️ No se encontraron anuncios en la página {page_num}. Terminando.")
                break # Salir si no hay tarjetas, asumiendo que es el final
            
            new_results_count = 0
            for c in cards:
                try:
                    a_tag = c.select_one("a[href]") or c.select_one("h2 a") or c.select_one("h3 a")
                    link = a_tag.get("href") if a_tag else ""
                    if link and link.startswith("/"):
                        link = "https://urbania.pe" + link
                    if not link or link in seen:
                        continue
                    
                    seen.add(link)
                    new_results_count += 1
                    
                    title = a_tag.get_text(" ", strip=True) if a_tag and a_tag.get_text(strip=True) else (c.get_text(" ", strip=True)[:140])
                    price_el = c.select_one("div.postingPrices-module__price") or c.select_one(".first-price") or c.select_one(".price")
                    price = price_el.get_text(" ", strip=True) if price_el else ""
                    
                    # Intentar buscar la descripción en un elemento más corto, si es posible
                    desc_el = c.select_one("p.postingCard-module__description") or c.select_one(".postingDescription")
                    desc = desc_el.get_text(" ", strip=True)[:400] if desc_el else c.get_text(" ", strip=True)[:400] # Fallback a todo el texto

                    img = ""
                    img_tag = c.select_one("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img and img.startswith("//"): img = "https:" + img
                        img = img.strip()
                        
                    # EXTRACCIÓN DE CARACTERÍSTICAS
                    # Búsqueda más robusta de características
                    features_list = c.select(".postingMainFeatures-module__posting-main-features-span") or c.select(".posting-features-item")

                    dormitorios_text = ""
                    banos_text = ""
                    m2_text = ""
                    
                    for feature in features_list:
                        text = feature.get_text(" ", strip=True)
                        # Dormitorios
                        if "dorm." in text.lower() or "dormitorio" in text.lower():
                            match = re.search(r'(\d+)', text)
                            if match:
                                dormitorios_text = match.group(1)
                        # Baños
                        elif "baño" in text.lower():
                            match = re.search(r'(\d+)', text)
                            if match:
                                banos_text = match.group(1)
                        # Metros Cuadrados
                        elif "m²" in text.lower():
                            match = re.search(r'(\d+)', text)
                            if match:
                                m2_text = match.group(1)
                                
                    all_results.append({
                        "titulo": title,
                        "precio": price,
                        "m2": m2_text,
                        "dormitorios": dormitorios_text,
                        "baños": banos_text,
                        "descripcion": desc,
                        "link": link,
                        "imagen_url": img
                    })
                except Exception as e:
                    # Opcional: imprimir el error para depuración
                    # print(f"Error procesando tarjeta: {e}") 
                    continue
            
            # Si no encontramos nuevos resultados en esta página, es probable que se haya acabado.
            if new_results_count == 0 and page_num > 1:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con ScrapingBee (Pág {page_num}): {e}")
            break # Salir en caso de error de red o timeout
            
    return pd.DataFrame(all_results)