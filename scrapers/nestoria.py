import re
import time
from typing import Optional
import pandas as pd
from bs4 import BeautifulSoup

# Imports locales desde el módulo 'common'
from .common import (
    create_driver,
    parse_precio_con_moneda,
    normalize_text,
    _extract_int_from_text
)

# -------------------- Nestoria (VERSÓN CORREGIDA Y FUNCIONAL CON IMÁGENES) --------------------
EXCEPCIONES = ["miraflores", "tarapoto", "la molina", "magdalena", "lambayeque", "ventanilla", "la victoria"]

def build_zona_slug_nestoria(zona_input: str) -> str:
    if not zona_input or not zona_input.strip():
        return "lima"  # ← ¡ESTO ES LO ÚNICO QUE CAMBIA!
    z = zona_input.strip().lower().replace(" ", "-")
    if z not in [e.lower() for e in EXCEPCIONES]:
        return z
    else:
        return "lima_" + z

def scrape_nestoria(zona: str = "", dormitorios: str = "0", banos: str = "0",
                      price_min: Optional[int] = None, price_max: Optional[int] = None,
                      palabras_clave: str = "", max_results_per_zone: int = 200):
    """
    Scraper FINAL para Nestoria. Usa Selenium.
    Extrae la imagen DEL DETALLE de cada anuncio.
    Solo entra al detalle para obtener la imagen, no para extraer más datos.
    VALIDA si la búsqueda devolvió 0 resultados y en ese caso devuelve DataFrame vacío.
    """
    zona_slug = build_zona_slug_nestoria(zona)
    base_url = f"https://www.nestoria.pe/{zona_slug}/inmuebles/alquiler"
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
    driver = create_driver(headless=True)
    results = []
    try:
        driver.get(base_url)
        time.sleep(3)

        # --- NUEVA VALIDACIÓN: Verificar si hay 0 resultados ---
        soup_check = BeautifulSoup(driver.page_source, "html.parser")
        h1_title = soup_check.select_one("div.listings__title h1")
        if h1_title:
            title_text = h1_title.get_text(strip=True).lower()
            # Buscar el patrón: "{número} inmuebles en ..."
            match = re.search(r'^(\d+)\s+inmuebles', title_text)
            if match:
                result_count = int(match.group(1))
                if result_count == 0:
                    print("Nestoria: La búsqueda devolvió 0 resultados. Saltando...")
                    return pd.DataFrame()  # Devolver vacío si son 0 resultados
            else:
                print("Advertencia: No se pudo extraer el número de resultados de la página.")
        else:
            print("Advertencia: No se encontró el título con el conteo de resultados.")

        # Scroll para cargar más resultados
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Seleccionar los contenedores de anuncios
        items = soup.select("li.rating__new") or soup.select("ul#main__listing_res > li")
        if not items:
            items = [li for li in soup.find_all("li") if li.select_one(".result__details__price")]
        if not items:
            items = soup.find_all(["li", "div", "article"], class_=lambda x: x and any(cls in x for cls in ["listing", "result", "property", "item"]))
        seen_links = set()
        for i, li in enumerate(items):
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
                # Extraer título
                title_elem = li.select_one(".listing__title__text") or li.select_one(".listing__title") or a_tag
                title = title_elem.get_text(" ", strip=True) if title_elem else a_tag.get_text(" ", strip=True)[:140]
                # Extraer precio
                price_elem = li.select_one(".result__details__price span") or li.select_one(".result__details__price") or li.select_one(".price")
                price_text = price_elem.get_text(" ", strip=True) if price_elem else ""
                # Aplicar filtro de precio aquí mismo
                moneda, precio_val = parse_precio_con_moneda(price_text)
                if price_max is not None and moneda == "S" and precio_val is not None and precio_val > price_max:
                    continue
                if price_min is not None and moneda == "S" and precio_val is not None and precio_val < price_min:
                    continue
                if moneda == "USD" and (price_max is not None or price_min is not None):
                    continue
                # Extraer descripción
                desc_elem = li.select_one(".listing__description") or li.select_one(".result__summary") or None
                desc = desc_elem.get_text(" ", strip=True) if desc_elem else li.get_text(" ", strip=True)[:800]
                # Extraer dormitorios, baños y m2 del texto
                text_content = li.get_text(" ", strip=True).lower()
                dormitorios_text = ""
                dorm_match = re.search(r'(\d+)\s*dormitori', text_content, flags=re.I)
                if dorm_match:
                    dormitorios_text = dorm_match.group(1)
                banos_text = ""
                banos_match = re.search(r'(\d+)\s*bañ', text_content, flags=re.I)
                if banos_match:
                    banos_text = banos_match.group(1)
                m2_text = ""
                m2_match = re.search(r'(\d{1,4})\s*(m²|m2)', text_content, flags=re.I)
                if m2_match:
                    m2_text = m2_match.group(1)
                # AHORA: Entrar al detalle para obtener la imagen principal (MÉTODO ROBUSTO)
                img_url = ""
                try:
                    driver.get(link)
                    time.sleep(1)  # Esperar a que cargue la imagen
                    detail_soup = BeautifulSoup(driver.page_source, "html.parser")

                    # Método 1: Buscar por el selector original (data-element)
                    main_img = detail_soup.select_one("img[data-element='main-swiper-slide']")
                    if main_img:
                        img_url = main_img.get("src") or main_img.get("data-src") or ""

                    # Método 2: Si falla, buscar por ID 'd_a_c_photo'
                    if not img_url:
                        img_by_id = detail_soup.select_one("img#d_a_c_photo")
                        if img_by_id:
                            img_url = img_by_id.get("src") or img_by_id.get("data-src") or ""

                    # Método 3: Si aún no se encuentra, buscar en la etiqueta meta con itemprop="image"
                    if not img_url:
                        meta_img = detail_soup.select_one("meta[itemprop='image']")
                        if meta_img:
                            img_url = meta_img.get("content") or ""

                    # Limpiar y formatear la URL
                    if img_url:
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url
                        img_url = img_url.strip()
                    else:
                        img_url = ""  # Asegurarse de que sea cadena vacía si no se encontró nada

                except Exception as e:
                    print(f"Error al obtener imagen de detalle en Nestoria para {link}: {e}")
                    pass

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
                seen_links.add(link)
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error en Nestoria scraper: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
    print(f"Procesados {len(results)} anuncios válidos")
    return pd.DataFrame(results)