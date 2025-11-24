import re
import time
import requests
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

# Imports locales desde el módulo 'common'
from .common import (
    create_driver,
    slugify_zone,
    WebDriverWait,
    By,
    EC
)

# -------------------- Urbania --------------------
def scrape_urbania(zona: str = "", dormitorios: str = "0", banos: str = "0",
                     price_min: Optional[int] = None, price_max: Optional[int] = None,
                     palabras_clave: str = "", max_pages: int = 6, wait_time: float = 1.5):
    zona = (zona or "").strip()
    # construir keyword combinando filtros (si el usuario solo pone keyword, la usamos)
    kw_parts = []
    if palabras_clave and palabras_clave.strip():
        kw_parts.append(palabras_clave.strip())
    if dormitorios and str(dormitorios) != "0":
        kw_parts.append(f"{dormitorios} dormitorios")
    if banos and str(banos) != "0":
        kw_parts.append(f"{banos} banos")
    keyword_value = " ".join(kw_parts).strip()
    # CAMBIO CLAVE: Siempre usar la zona si está especificada, independientemente de las keywords
    if zona:
        # Mapeo específico para Urbania
        ZONA_MAPEO_URBANIA = {
            "ancón": "ancon",
            "ate": "ate-vitarte",  # Usar ate-vitarte como fallback
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
    params = []
    if keyword_value:
        params.append(f"keyword={requests.utils.quote(keyword_value)}")
    if price_min is not None:
        params.append(f"priceMin={price_min}")
    if price_max is not None:
        params.append(f"priceMax={price_max}")
    if dormitorios and dormitorios != "0":
        params.append(f"bedroomMin={dormitorios}")
    if banos and banos != "0":
        params.append(f"bathroomMin={banos}")
    if price_min is not None or price_max is not None:
        params.append("currencyId=6")  # Soles
    url = base + ("?" + "&".join(params) if params else "")
    print(f"URL de Urbania: {url}")  # Mostrar URL usada
    driver = create_driver(headless=True)
    results = []
    seen = set()
    try:
        driver.get(url)
        # esperar unos segundos por elementos representativos (no bloquear si timeout)
        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, div[data-qa='posting PROPERTY'], div.postingCard"))
            )
        except:
            pass
        page_count = 0
        while page_count < max_pages:
            page_count += 1
            last_h = driver.execute_script("return document.body.scrollHeight")
            for _ in range(8):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(wait_time)
                new_h = driver.execute_script("return document.body.scrollHeight")
                if new_h == last_h:
                    break
                last_h = new_h
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # intentar varios selectores
            card_selectors = [
                "div[data-qa='posting PROPERTY']",
                "article",
                "div.postingCard-module__posting",
                "div.postingCard",
                "div.posting-card",
                "div[class*='postingCard']",
            ]
            cards = []
            for sel in card_selectors:
                found = soup.select(sel)
                if found and len(found) > 0:
                    cards = found
                    break
            if not cards:
                cards = soup.select("a[href]")[:0]  # vacío
            prev_len = len(results)
            for c in cards:
                try:
                    a_tag = c.select_one("a[href]") or c.select_one("h2 a") or c.select_one("h3 a")
                    link = a_tag.get("href") if a_tag else ""
                    if link and link.startswith("/"):
                        link = "https://urbania.pe" + link
                    if not link:
                        continue
                    if link in seen:
                        continue
                    seen.add(link)
                    title = a_tag.get_text(" ", strip=True) if a_tag and a_tag.get_text(strip=True) else (c.get_text(" ", strip=True)[:140])
                    price_el = c.select_one("div.postingPrices-module__price") or c.select_one(".first-price") or c.select_one(".price")
                    price = price_el.get_text(" ", strip=True) if price_el else ""
                    desc = c.get_text(" ", strip=True)[:400]
                    img = ""
                    img_tag = c.select_one("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img and img.startswith("//"): img = "https:" + img
                        # Limpiar espacios al final
                        img = img.strip()
                    # EXTRAER DORMITORIOS
                    dormitorios_text = ""
                    dorm_elem = c.select_one(".postingMainFeatures-module__posting-main-features-span:contains('dorm.')")
                    if dorm_elem:
                        dorm_text = dorm_elem.get_text(" ", strip=True)
                        dorm_match = re.search(r'(\d+)', dorm_text)
                        if dorm_match:
                            dormitorios_text = dorm_match.group(1)
                    # EXTRAER BAÑOS
                    banos_text = ""
                    banos_elem = c.select_one(".postingMainFeatures-module__posting-main-features-span:contains('baño')")
                    if banos_elem:
                        banos_text_full = banos_elem.get_text(" ", strip=True)
                        banos_match = re.search(r'(\d+)', banos_text_full)
                        if banos_match:
                            banos_text = banos_match.group(1)
                    # EXTRAER METROS CUADRADOS
                    m2_text = ""
                    m2_elem = c.select_one(".postingMainFeatures-module__posting-main-features-span:contains('m²')")
                    if m2_elem:
                        m2_text_full = m2_elem.get_text(" ", strip=True)
                        m2_match = re.search(r'(\d+)', m2_text_full)
                        if m2_match:
                            m2_text = m2_match.group(1)
                    # AHORA INCLUIMOS LOS VALORES EXTRAÍDOS
                    results.append({
                        "titulo": title,
                        "precio": price,
                        "m2": m2_text,
                        "dormitorios": dormitorios_text,
                        "baños": banos_text,
                        "descripcion": desc,
                        "link": link,
                        "imagen_url": img
                    })
                except Exception:
                    continue
            # si no hay nuevos resultados intentar paginar/click "cargar más"
            if len(results) == prev_len:
                clicked = False
                try:
                    # probar varios selectores para "cargar más" / siguiente
                    next_selectors = [
                        "a[rel='next']", "a[aria-label='Siguiente']", "a[data-qa='pagination-next']",
                        "button[data-qa='pagination-next']", "a.pagination__next", "a.next", "button.load-more", "a.load-more"
                    ]
                    for sel in next_selectors:
                        elems = driver.find_elements(By.CSS_SELECTOR, sel)
                        for e in elems:
                            try:
                                if e.is_displayed():
                                    driver.execute_script("arguments[0].scrollIntoView(true);", e)
                                    time.sleep(0.2)
                                    e.click()
                                    time.sleep(wait_time + 0.5)
                                    clicked = True
                                    break
                            except:
                                continue
                        if clicked:
                            break
                except:
                    clicked = False
                if not clicked:
                    # intentar incrementar page= en URL
                    cur = driver.current_url
                    m = re.search(r"([?&]page=)(\d+)", cur)
                    if m:
                        cur_page = int(m.group(2))
                        next_page = cur_page + 1
                        new_url = re.sub(r"([?&]page=)\d+", r"\1{}".format(next_page), cur)
                        try:
                            driver.get(new_url)
                            time.sleep(wait_time + 0.8)
                            clicked = True
                        except:
                            clicked = False
                if not clicked:
                    break
            time.sleep(0.4)
        return pd.DataFrame(results)
    except Exception:
        return pd.DataFrame()
    finally:
        try:
            driver.quit()
        except:
            pass