import re
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

# Imports locales desde el módulo 'common'
from .common import (
    COMMON_UA,
    slugify_zone
)

# -------------------- Properati --------------------
def scrape_properati(zona: str = "", dormitorios: str = "0", banos: str = "0",
                       price_min: Optional[int] = None, price_max: Optional[int] = None,
                       palabras_clave: str = ""):
    if zona and zona.strip():
        # Mapeo específico para Properati
        ZONA_MAPEO_PROPERATI = {
            "ancón": "ancon",
            "ate": "ate",
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
            "lima": "lima",
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
            "villa maría del triunfo": "villa-maria-del-triunfo",
            # Nuevas entradas para manejar "cercado de lima"
            "cercado de lima": "lima-cercado",
            "cercado lima": "lima-cercado",
            "lima cercado": "lima-cercado",
        }
        zona_lower = zona.strip().lower()
        zone_slug = ZONA_MAPEO_PROPERATI.get(zona_lower, slugify_zone(zona))
        base = f"https://www.properati.com.pe/s/{zone_slug}/alquiler?propertyType=apartment%2Chouse"
    else:
        base = "https://www.properati.com.pe/s/alquiler?propertyType=apartment%2Chouse"
    # Agregar parámetros de filtros
    params = []
    if dormitorios and dormitorios != "0":
        params.append(f"bedrooms={dormitorios}")
    if banos and banos != "0":
        params.append(f"bathrooms={banos}")
    if price_min is not None:
        params.append(f"minPrice={price_min}")
    if price_max is not None:
        params.append(f"maxPrice={price_max}")
    # Procesar palabras clave: convertir "piscina" → amenities=swimming_pool, "jardin" → amenities=garden
    if palabras_clave and palabras_clave.strip():
        palabras = palabras_clave.lower().split()
        amenities = []
        other_keywords = []
        for p in palabras:
            if p == "piscina":
                amenities.append("swimming_pool")
            elif p == "jardin":
                amenities.append("garden")
            else:
                other_keywords.append(p)
        # Si hay amenities, usarlas como parámetro separado
        if amenities:
            base += "&amenities=" + ",".join(amenities)
        # Si quedan otras palabras clave, agregarlas como keyword
        if other_keywords:
            base += "&keyword=" + requests.utils.quote(" ".join(other_keywords))
    # Construir URL final
    if params:
        base += "&" + "&".join(params)
    print(f"URL de Properati: {base}")  # Mostrar URL usada
    try:
        r = requests.get(base, headers={"User-Agent": COMMON_UA}, timeout=15)
        r.raise_for_status()
    except:
        return pd.DataFrame()
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("article") or soup.select("div.posting-card") or soup.select("a[href]")
    results = []
    for c in cards:
        try:
            a = c.select_one("a[href]") or c.select_one("a.title")
            href = a.get("href") if a else ""
            if href and href.startswith("/"):
                href = "https://www.properati.com.pe" + href
            title = a.get_text(" ", strip=True) if a else c.get_text(" ", strip=True)[:140]
            price = ""
            price_elem = c.select_one(".price")
            if price_elem:
                price = price_elem.get_text(" ", strip=True)
            # EXTRAER DORMITORIOS
            dormitorios_text = ""
            dorm_elem = c.select_one(".properties__bedrooms")
            if dorm_elem:
                dorm_text = dorm_elem.get_text(" ", strip=True)
                dorm_match = re.search(r'(\d+)', dorm_text)
                if dorm_match:
                    dormitorios_text = dorm_match.group(1)
            # EXTRAER BAÑOS
            banos_text = ""
            banos_elem = c.select_one(".properties__bathrooms")
            if banos_elem:
                banos_text_full = banos_elem.get_text(" ", strip=True)
                banos_match = re.search(r'(\d+)', banos_text_full)
                if banos_match:
                    banos_text = banos_match.group(1)
            # EXTRAER METROS CUADRADOS
            m2_text = ""
            m2_elem = c.select_one(".properties__area")
            if m2_elem:
                m2_text_full = m2_elem.get_text(" ", strip=True)
                m2_match = re.search(r'(\d+)', m2_text_full)
                if m2_match:
                    m2_text = m2_match.group(1)
            img = ""
            img_tag = c.select_one("img")
            if img_tag:
                img = img_tag.get("src") or img_tag.get("data-src") or ""
                # Filtrar imágenes no deseadas: solo aceptar las que comienzan con https://img (no con https://images.proppit)
                if img and img.startswith("https://img"):
                    img = img.strip()
                elif img and img.startswith("//"):
                    img_full = "https:" + img
                    if img_full.startswith("https://img"):
                        img = img_full.strip()
                    else:
                        img = ""  # Rechazar otras fuentes
                else:
                    img = ""  # Rechazar si no cumple con el criterio
            # AHORA INCLUIMOS LOS VALORES EXTRAÍDOS
            results.append({
                "titulo": title,
                "precio": price,
                "m2": m2_text,
                "dormitorios": dormitorios_text,
                "baños": banos_text,
                "descripcion": title,
                "link": href or "",
                "imagen_url": img
            })
        except Exception as e:
            print(f"Error en Properati al procesar un anuncio: {e}")
            continue
    return pd.DataFrame(results)