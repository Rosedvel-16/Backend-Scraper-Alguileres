import re
import os
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

from .common import (
    parse_precio_con_moneda,
    normalize_text,
    _extract_int_from_text
)

SCRAPINGBEE_API_URL = "https://api.scrapingbee.com/v1/"
API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")

EXCEPCIONES = ["miraflores", "tarapoto", "la molina", "magdalena", "lambayeque", "ventanilla", "la victoria"]

def build_zona_slug_nestoria(zona_input: str) -> str:
    """Construye el slug de la zona para la URL de Nestoria."""
    if not zona_input or not zona_input.strip():
        return "lima"
    z = zona_input.strip().lower().replace(" ", "-")
    if z not in [e.lower().replace(" ", "-") for e in EXCEPCIONES]:
        return z
    else:
        return "lima_" + z

def scrape_nestoria(zona: str = "", dormitorios: str = "0", banos: str = "0",
                     price_min: Optional[int] = None, price_max: Optional[int] = None,
                     palabras_clave: str = "", max_results_per_zone: int = 200):
    
    # ⚠️ VERIFICACIÓN DE CLAVE API
    if not API_KEY:
        print("❌ Error: Variable de entorno SCRAPINGBEE_API_KEY no encontrada.")
        return pd.DataFrame()

    zona_slug = build_zona_slug_nestoria(zona)
    base_url = f"https://www.nestoria.pe/{zona_slug}/inmuebles/alquiler"
    
    # Construcción de la URL base con filtros
    if dormitorios and dormitorios != "0":
        base_url += f"/dormitorios-{dormitorios}"
        
    params = []
    if banos and banos != "0":
        params.append(f"bathrooms={banos}")
    if price_min and str(price_min) != "0":
        params.append(f"price_min={price_min}")
    if price_max and str(price_max) != "0":
        params.append(f"price_max={price_max}")
        
    if params:
        base_url += "?" + "&".join(params)
        
    print(f"URL de Nestoria: {base_url}")
    
    # --- Configuración de ScrapingBee ---
    payload = {
        'api_key': API_KEY,
        'url': base_url,
        'render_js': 'true', # Habilitar JS rendering
        'wait': 4000,        # Esperar 4 segundos (mucha información se carga con JS)
        'screenshot': 'false',
        'extract_rules': '{"items": "li.rating__new, ul#main__listing_res > li", "next_page": "a.pagination__next"}' # Esto NO funcionará en el plan gratuito, solo para referencia. Usaremos la paginación manual.
    }
    
    results = []
    seen_links = set()
    current_url = base_url
    page_count = 0
    max_pages = 5 # Límite de páginas para evitar un uso excesivo de tokens de ScrapingBee
    
    while page_count < max_pages:
        page_count += 1
        print(f"-> Scrapeando Nestoria (Página {page_count}): {current_url}")
        
        # Actualizar la URL en el payload
        payload['url'] = current_url
        
        try:
            # 1. Llamar a la API de ScrapingBee
            response = requests.get(SCRAPINGBEE_API_URL, params=payload, timeout=40)
            
            if response.status_code != 200:
                print(f"❌ Error ScrapingBee (Pág {page_count}): Código {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # --- VALIDACIÓN: Verificar si hay 0 resultados ---
            if page_count == 1:
                h1_title = soup.select_one("div.listings__title h1")
                if h1_title and re.search(r'^0\s+inmuebles', h1_title.get_text(strip=True).lower()):
                    print("Nestoria: La búsqueda devolvió 0 resultados. Saltando...")
                    return pd.DataFrame()

            # --- Extracción de datos ---
            items = soup.select("li.rating__new") or soup.select("ul#main__listing_res > li")
            
            if not items:
                print(f"⚠️ No se encontraron anuncios en la página {page_count}. Terminando.")
                break
                
            new_results_found = False
            
            for li in items:
                try:
                    # Extraer link
                    a_tag = li.select_one("a.results__link") or li.select_one("a[href]")
                    if not a_tag:
                        continue
                        
                    link = a_tag.get("data-href") or a_tag.get("href") or ""
                    if link and link.startswith("/"):
                        link = "https://www.nestoria.pe" + link
                    
                    if not link or link in seen_links:
                        continue
                        
                    seen_links.add(link)
                    new_results_found = True
                    
                    # Extraer título y precio (simplificado)
                    title_elem = li.select_one(".listing__title__text") or li.select_one(".listing__title") or a_tag
                    title = title_elem.get_text(" ", strip=True) if title_elem else a_tag.get_text(" ", strip=True)[:140]
                    
                    price_elem = li.select_one(".result__details__price span") or li.select_one(".result__details__price") or li.select_one(".price")
                    price_text = price_elem.get_text(" ", strip=True) if price_elem else ""
                    
                    # Aplicar filtro de precio (solo en Soles) - Tu lógica se mantiene
                    moneda, precio_val = parse_precio_con_moneda(price_text)
                    if (price_max is not None and moneda == "S" and precio_val is not None and precio_val > price_max) or \
                       (price_min is not None and moneda == "S" and precio_val is not None and precio_val < price_min) or \
                       (moneda == "USD" and (price_max is not None or price_min is not None)):
                        continue
                        
                    desc_elem = li.select_one(".listing__description") or li.select_one(".result__summary")
                    desc = desc_elem.get_text(" ", strip=True) if desc_elem else li.get_text(" ", strip=True)[:800]
                    
                    # Extracción de características del texto
                    text_content = li.get_text(" ", strip=True).lower()
                    dormitorios_text = re.search(r'(\d+)\s*dormitori', text_content, flags=re.I).group(1) if re.search(r'(\d+)\s*dormitori', text_content, flags=re.I) else ""
                    banos_text = re.search(r'(\d+)\s*bañ', text_content, flags=re.I).group(1) if re.search(r'(\d+)\s*bañ', text_content, flags=re.I) else ""
                    m2_text = re.search(r'(\d{1,4})\s*(m²|m2)', text_content, flags=re.I).group(1) if re.search(r'(\d{1,4})\s*(m²|m2)', text_content, flags=re.I) else ""
                    
                    # --- Extracción de Imagen ---
                    # Buscamos la imagen principal que debería estar cargada por JS
                    img_url = ""
                    img_tag = li.select_one("img.result__image") or li.select_one(".listing__image img")
                    
                    if img_tag:
                        img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img_url and img_url.startswith("//"):
                            img_url = "https:" + img_url
                        img_url = img_url.strip()
                    
                    results.append({
                        "titulo": title,
                        "precio": price_text,
                        "m2": m2_text,
                        "dormitorios": dormitorios_text,
                        "baños": banos_text,
                        "descripcion": desc,
                        "link": link,
                        "imagen_url": img_url
                    })
                except Exception:
                    continue
            
            # --- Lógica de Paginación ---
            next_page_tag = soup.select_one("a.pagination__next")
            if next_page_tag:
                # El link de la siguiente página es relativo
                next_page_href = next_page_tag.get("href")
                if next_page_href and next_page_href.startswith("/"):
                    current_url = "https://www.nestoria.pe" + next_page_href
                elif next_page_href:
                    current_url = next_page_href
                else:
                    break
            else:
                break # Si no hay botón de Siguiente, terminamos
                
            if not new_results_found:
                 break # Si no se encontraron nuevos resultados en la página, terminamos
                 
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con ScrapingBee (Pág {page_count}): {e}")
            break # Salir en caso de error de red o timeout
            
    print(f"Procesados {len(results)} anuncios válidos")
    return pd.DataFrame(results)