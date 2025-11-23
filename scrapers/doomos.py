import re
import os # Necesario para obtener la clave API
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

SCRAPINGBEE_API_URL = "https://api.scrapingbee.com/v1/"
API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")

# -------------------- Doomos (CON API DE SCRAPINGBEE) --------------------
def scrape_doomos(zona: str = "", dormitorios: str = "0", banos: str = "0",
                     price_min: Optional[int] = None, price_max: Optional[int] = None,
                     palabras_clave: str = ""):
    
    # ⚠️ VERIFICACIÓN DE CLAVE API
    if not API_KEY:
        print("❌ Error: Variable de entorno SCRAPINGBEE_API_KEY no encontrada.")
        return pd.DataFrame()

    results = []
    
    try:
        # Mapeo ACTUALIZADO de zonas a sus IDs específicos para Doomos
        ZONA_IDS_CORRECTOS = {
            "ancón": "-336912", "ate": "-337679", "breña": "65645345", "carabayllo": "-339907",
            "chaclacayo": "-341190", "chorrillos": "-342811", "cieneguilla": "-343329",
            "comas": "-343903", "el agustino": "-345552", "jesús maría": "348294",
            "la molina": "-351740", "la victoria": "-352442", "lima": "45343445", 
            "lince": "-352696", "los olivos": "191126", "lurigancho": "-353648", 
            "lurín": "-353652", "magdalena del mar": "326245", "miraflores": "-354864", 
            "pachacámac": "-356636", "pucusana": "-359672", "pueblo libre": "-359690",
            "puente piedra": "-359759", "punta hermosa": "-360186", "punta negra": "-360189",
            "rímac": "-361308", "san bartolo": "-362154", "san borja": "-362170", 
            "san isidro": "-362425", "san luis": "-362738", "san miguel": "-362804",
            "santiago de surco": "-364705", "surquillo": "-364723"
        }

        base_url = "http://www.doomos.com.pe/search/"

        # Parámetros base
        params_doomos = {
            "clase": "1",    # Departamentos
            "stipo": "16",   # Alquiler
            "pagina": "1",
            "sort": "primeasc"
        }

        # Manejo de la Zona y ID
        if not zona or not zona.strip():
            params_doomos["loc_name"] = "Lima (Región de Lima)"
            params_doomos["loc_id"] = "-352647" 
        else:
            zona_lower = zona.strip().lower()
            loc_id = ZONA_IDS_CORRECTOS.get(zona_lower, "")
            params_doomos["loc_name"] = f"{zona.strip()} (Región de Lima)"
            if loc_id:
                params_doomos["loc_id"] = loc_id

        # Agregar filtros opcionales
        if dormitorios and dormitorios != "0":
            params_doomos["piezas"] = dormitorios
        if banos and banos != "0":
            params_doomos["banos"] = banos
        if price_min is not None:
            params_doomos["preciomin"] = str(price_min)
        if price_max is not None:
            params_doomos["preciomax"] = str(price_max)
        if palabras_clave and palabras_clave.strip():
            params_doomos["keyword"] = palabras_clave.strip()

        # Construir URL completa
        url = base_url + "?" + "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params_doomos.items())
        print(f"URL de Doomos: {url}")
        
        # --- Configuración y Llamada a ScrapingBee ---
        
        # ⚠️ Nota: Doomos tiene paginación simple por URL con el parámetro 'pagina'.
        # Hacemos 3 peticiones (Pág 1, 2, 3) para simular el scroll y obtener más resultados.
        
        for page_num in range(1, 4): 
            
            current_params = params_doomos.copy()
            current_params["pagina"] = str(page_num)
            
            current_url = base_url + "?" + "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in current_params.items())
            
            payload = {
                'api_key': API_KEY,
                'url': current_url,
                'render_js': 'true', # Habilitar JS rendering (necesario para la carga dinámica)
                'wait': 3000,        # Esperar 3 segundos para la carga
                'scroll_to_bottom': 'true' # Simula el scroll que hacías
            }
            
            print(f"-> Scrapeando Doomos (Pág {page_num}): {current_url}")
            response = requests.get(SCRAPINGBEE_API_URL, params=payload, timeout=40)

            if response.status_code != 200:
                print(f"❌ Error ScrapingBee (Pág {page_num}): Código {response.status_code}")
                if page_num == 1:
                    return pd.DataFrame()
                break # Salir de la paginación si hay error

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select(".content_result")

            if not cards:
                print(f"⚠️ No se encontraron más cards en la página {page_num}.")
                break
            
            for card in cards:
                try:
                    # Extraer link y título
                    a_tag = card.select_one(".content_result_titulo a")
                    if not a_tag:
                        continue

                    title = a_tag.get_text(" ", strip=True)
                    href = a_tag.get("href") or ""

                    if href and href.startswith("/"):
                        href = "http://www.doomos.com.pe" + href

                    # Extraer precio y características (tu lógica de REGEX)
                    price_elem = card.select_one(".content_result_precio")
                    price_full_text = price_elem.get_text(" ", strip=True) if price_elem else ""

                    price_text_content = price_full_text.lower() if price_full_text else ""
                    
                    # Características: buscar en el texto completo del precio
                    dormitorios_text = re.search(r'(\d+)\s*(?:dormitorio|hab)', price_text_content).group(1) if re.search(r'(\d+)\s*(?:dormitorio|hab)', price_text_content) else ""
                    banos_text = re.search(r'(\d+)\s*baño', price_text_content).group(1) if re.search(r'(\d+)\s*baño', price_text_content) else ""
                    m2_text = re.search(r'(\d+)\s*m2', price_text_content).group(1) if re.search(r'(\d+)\s*m2', price_text_content) else ""

                    # Limpiar Precio Monetario (S/ 1.680 o US$ 480)
                    precio_limpio = ""
                    match_precio = re.search(r'(S/|US\$)\s*[\d\.,]+', price_full_text)
                    if match_precio:
                        precio_limpio = match_precio.group(0).strip()
                    else:
                        precio_limpio = price_full_text
                        
                    # Extraer descripción
                    desc_elem = card.select_one(".content_result_descripcion")
                    desc = desc_elem.get_text(" ", strip=True) if desc_elem else card.get_text(" ", strip=True)[:400]

                    # EXTRAER IMAGEN
                    img_url = ""
                    img_tag = card.select_one("img.content_result_image")
                    if img_tag:
                        img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img_url and img_url.startswith("//"):
                            img_url = "https:" + img_url
                        img_url = img_url.strip()

                    results.append({
                        "titulo": title,
                        "precio": precio_limpio,
                        "m2": m2_text,
                        "dormitorios": dormitorios_text,
                        "baños": banos_text,
                        "descripcion": desc,
                        "link": href,
                        "imagen_url": img_url
                    })

                except Exception as e:
                    # print(f"Error procesando card en Doomos: {e}")
                    continue

    except Exception as e:
        print(f"Error en Doomos scraper (conexión/base): {e}")

    return pd.DataFrame(results)