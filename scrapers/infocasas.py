import re
import time
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

# Imports locales desde el módulo 'common'
from .common import (
    create_driver,
    slugify_zone
)

# -------------------- Infocasas --------------------
def scrape_infocasas(zona: str = "", dormitorios: str = "0", banos: str = "0",
                       price_min: Optional[int] = None, price_max: Optional[int] = None,
                       palabras_clave: str = "", max_scrolls: int = 8):
    # Mapeo específico para InfoCasas
    ZONA_MAPEO_INFOCASAS = {
        "ancón": "ancon",
        "ate": "ate",
        "barranco": "barranco",
        "breña": "breña",
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
    # Construir URL base según la zona
    if zona and zona.strip():
        zona_lower = zona.strip().lower()
        zone_slug = ZONA_MAPEO_INFOCASAS.get(zona_lower, slugify_zone(zona))
        base = f"https://www.infocasas.com.pe/alquiler/casas-y-departamentos/lima/{zone_slug}"
    else:
        base = "https://www.infocasas.com.pe/alquiler/casas-y-departamentos"
    # Agregar filtros si están especificados
    if dormitorios and dormitorios != "0" and banos and banos != "0" and price_min is not None and price_max is not None:
        base += f"/{dormitorios}-dormitorio/{banos}-bano/desde-{price_min}/hasta-{price_max}?&IDmoneda=6"
    elif dormitorios and dormitorios != "0" and banos and banos != "0":
        base += f"/{dormitorios}-dormitorio/{banos}-bano"
    elif dormitorios and dormitorios != "0":
        base += f"/{dormitorios}-dormitorio"
    elif banos and banos != "0":
        base += f"/{banos}-bano"
    # Agregar parámetros de búsqueda si existen
    if palabras_clave and palabras_clave.strip():
        if "?" in base:
            base += f"&searchstring={requests.utils.quote(palabras_clave.strip())}"
        else:
            base += f"?searchstring={requests.utils.quote(palabras_clave.strip())}"
    print(f"URL de InfoCasas: {base}")  # Mostrar URL usada
    driver = create_driver(headless=True)
    results = []
    try:
        driver.get(base)
        time.sleep(2)  # Esperar a que cargue la página
        # Hacer scroll para cargar más resultados
        for _ in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.6)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Buscar los contenedores de anuncios específicos de InfoCasas
        nodes = soup.select("div.listingCard") or soup.select("article")
        for n in nodes:
            try:
                # Verificar que el elemento tiene el atributo href
                a = n.select_one("a[href]")
                if not a:
                    continue
                href = a.get("href") if a else ""
                # Construir URL completa
                if href and href.startswith("/"):
                    href = "https://www.infocasas.com.pe" + href
                # Extraer título
                title_elem = n.select_one("h2.lc-title") or n.select_one(".lc-title") or a
                title = title_elem.get_text(" ", strip=True) if title_elem else n.get_text(" ", strip=True)[:250]
                # Extraer precio
                price = ""
                price_elem = n.select_one(".main-price") or n.select_one(".lc-price p") or n.select_one(".property-price-tag p")
                if price_elem:
                    price = price_elem.get_text(" ", strip=True)
                # Extraer ubicación
                location_elem = n.select_one(".lc-location") or n.select_one("strong")
                location = location_elem.get_text(" ", strip=True) if location_elem else ""
                # Extraer dormitorios, baños y m² de los tags
                dormitorios_text = ""
                banos_text = ""
                m2_text = ""
                # Buscar en los elementos con clase lc-typologyTag__item
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
                # Extraer descripción
                desc_elem = n.select_one(".lc-description") or n.select_one("p")
                desc = desc_elem.get_text(" ", strip=True) if desc_elem else n.get_text(" ", strip=True)[:400]
                # EXTRAER IMAGEN DIRECTAMENTE DEL LISTADO (NO ENTRAR AL DETALLE)
                img_url = ""
                img_tag = n.select_one(".cardImageGallery .gallery-image img")
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
                    "link": href or "",
                    "imagen_url": img_url
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error en InfoCasas scraper: {e}")
        pass
    finally:
        try:
            driver.quit()
        except:
            pass
    return pd.DataFrame(results)