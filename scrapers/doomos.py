import re
import time
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

# Imports locales desde el módulo 'common'
from .common import (
    create_driver
)

# -------------------- Doomos --------------------
def scrape_doomos(zona: str = "", dormitorios: str = "0", banos: str = "0",
                    price_min: Optional[int] = None, price_max: Optional[int] = None,
                    palabras_clave: str = ""):
    driver = create_driver(headless=True)
    results = []
    try:
        # Mapeo ACTUALIZADO de zonas a sus IDs específicos para Doomos
        ZONA_IDS_CORRECTOS = {
            "ancón": "-336912",
            "ate": "-337679",
            "breña": "65645345",
            "carabayllo": "-339907",
            "chaclacayo": "-341190",
            "chorrillos": "-342811",
            "cieneguilla": "-343329",
            "comas": "-343903",
            "el agustino": "-345552",
            "jesús maría": "348294",
            "la molina": "-351740",
            "la victoria": "-352442",
            "lima": "45343445",  # Cercado de Lima
            "lince": "-352696",
            "los olivos": "191126",
            "lurigancho": "-353648",
            "lurín": "-353652",
            "magdalena del mar": "326245",
            "miraflores": "-354864",
            "pachacámac": "-356636",
            "pucusana": "-359672",
            "pueblo libre": "-359690",
            "puente piedra": "-359759",
            "punta hermosa": "-360186",
            "punta negra": "-360189",
            "rímac": "-361308",
            "san bartolo": "-362154",
            "san borja": "-362170",
            "san isidro": "-362425",
            "san luis": "-362738",
            "san miguel": "-362804",
            "santiago de surco": "-364705",
            "surquillo": "-364723"
        }

        # Construir URL base CORRECTA para Doomos
        base_url = "http://www.doomos.com.pe/search/"

        # Parámetros base
        params = {
            "clase": "1",  # Departamentos
            "stipo": "16",  # Alquiler
            "pagina": "1",
            "sort": "primeasc"
        }

        # Si NO se especifica zona, usar LIMA por defecto con el ID CORRECTO
        if not zona or not zona.strip():
            params["loc_name"] = "Lima (Región de Lima)"
            params["loc_id"] = "-352647"  # ← ¡¡¡ESTA ES LA LÍNEA CORREGIDA!!!
        else:
            zona_lower = zona.strip().lower()
            loc_id = ZONA_IDS_CORRECTOS.get(zona_lower, "")
            zona_formateada = f"{zona.strip()} (Región de Lima)"
            params["loc_name"] = zona_formateada
            if loc_id:
                params["loc_id"] = loc_id

        # Agregar filtros opcionales
        if dormitorios and dormitorios != "0":
            params["piezas"] = dormitorios
        if banos and banos != "0":
            params["banos"] = banos
        if price_min is not None:
            params["preciomin"] = str(price_min)
        if price_max is not None:
            params["preciomax"] = str(price_max)
        if palabras_clave and palabras_clave.strip():
            params["keyword"] = palabras_clave.strip()

        # Construir URL completa
        url = base_url + "?" + "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        print(f"URL de Doomos: {url}")

        driver.get(url)
        time.sleep(3)

        # Scroll para cargar más resultados
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select(".content_result")

        if not cards:
            print("No se encontraron cards en Doomos")
            return pd.DataFrame()

        print(f"Se encontraron {len(cards)} cards en Doomos")

        for card in cards:
            try:
                # Extraer link y título
                a_tag = card.select_one(".content_result_titulo a")
                if not a_tag:
                    continue

                title = a_tag.get_text(" ", strip=True)
                href = a_tag.get("href") or ""

                # Construir URL completa si es relativa
                if href and href.startswith("/"):
                    href = "http://www.doomos.com.pe" + href

                # Extraer precio (TEXTO COMPLETO)
                price_elem = card.select_one(".content_result_precio")
                price_full_text = price_elem.get_text(" ", strip=True) if price_elem else ""

                # EXTRAER DORMITORIOS, BAÑOS Y M2 DEL TEXTO DEL PRECIO
                dormitorios_text = ""
                banos_text = ""
                m2_text = ""

                price_text_content = price_full_text.lower() if price_full_text else ""

                # 🔥 CORRECCIÓN CLAVE: Buscar "hab." además de "dormitorio"
                dorm_match = re.search(r'(\d+)\s*(?:dormitorio|hab)', price_text_content)
                if dorm_match:
                    dormitorios_text = dorm_match.group(1)

                banos_match = re.search(r'(\d+)\s*baño', price_text_content)
                if banos_match:
                    banos_text = banos_match.group(1)

                m2_match = re.search(r'(\d+)\s*m2', price_text_content)
                if m2_match:
                    m2_text = m2_match.group(1)

                # LIMPIAR EL CAMPO "precio" PARA QUE SOLO CONTENGA EL VALOR MONETARIO
                # Buscar el patrón: "S/ 1.680" o "US$ 480"
                precio_limpio = ""
                match_precio = re.search(r'(S/|US\$)\s*[\d\.,]+', price_full_text)
                if match_precio:
                    precio_limpio = match_precio.group(0).strip()
                else:
                    # Si no coincide el patrón, dejar el texto original como fallback
                    precio_limpio = price_full_text

                # Extraer descripción
                desc_elem = card.select_one(".content_result_descripcion")
                desc = desc_elem.get_text(" ", strip=True) if desc_elem else card.get_text(" ", strip=True)[:400]

                # EXTRAER IMAGEN DIRECTAMENTE DEL LISTADO (NO ENTRAR AL DETALLE)
                img_url = ""
                img_tag = card.select_one("img.content_result_image")
                if img_tag:
                    img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                    if img_url and img_url.startswith("//"):
                        img_url = "https:" + img_url
                    img_url = img_url.strip()

                results.append({
                    "titulo": title,
                    "precio": precio_limpio,  # ← ¡CAMBIO CLAVE AQUÍ!
                    "m2": m2_text,
                    "dormitorios": dormitorios_text,
                    "baños": banos_text,
                    "descripcion": desc,
                    "link": href,
                    "imagen_url": img_url
                })

            except Exception as e:
                print(f"Error procesando card en Doomos: {e}")
                continue

    except Exception as e:
        print(f"Error en Doomos scraper: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

    return pd.DataFrame(results)