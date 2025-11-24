import re
import time
import requests
import pandas as pd
from typing import Optional
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager 

COMMON_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# -------------------- Helpers --------------------

def create_driver(headless: bool = True):
    """
    Crea una instancia del driver de Chrome.
    Adaptado para entornos de contenedor (Railway/Docker).
    """
    options = Options()
    
    # Configuración necesaria para correr en entornos de Linux (Docker)
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={COMMON_UA}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 1. Intentar con Webdriver Manager (falla a menudo en Docker)
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("DEBUG: Usando WebDriverManager (Método 1)")
        return driver
    except Exception as e:
        print(f"DEBUG: Fallo de WebDriverManager ({e}). Intentando método 2...")

    # 2. Método de Fallback (Usando rutas esperadas de Chrome en Docker/Linux)
    try:
        options.binary_location = '/usr/bin/chromium' 
        service = Service('/usr/bin/chromedriver') 
        driver = webdriver.Chrome(service=service, options=options)
        print("DEBUG: Usando rutas de contenedor (Método 2)")
        return driver
    except Exception as e:
        print(f"ERROR FATAL: No se pudo iniciar el driver en ninguna modalidad: {e}")
        raise RuntimeError("El servicio de scraping falló al iniciar el navegador.")
    
def slugify_zone(zona: str) -> str:
    if not zona:
        return ""
    import unicodedata
    s = zona.lower().strip()
    # Reemplazar caracteres especiales y tildes
    trans = str.maketrans("áéíóúñü", "aeiounu")
    s = s.translate(trans)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s

def parse_precio_con_moneda(precio_str):
    if not precio_str:
        return (None, None)
    s = str(precio_str)
    moneda = None
    if "S/" in s or s.strip().startswith("S/"):
        moneda = "S"
    elif "$" in s:
        moneda = "USD"
    nums = re.sub(r"[^\d]", "", s)
    return (moneda, int(nums)) if nums else (moneda, None)

def _extract_m2(s):
    if s is None:
        return None
    m = re.search(r"(\d{1,4})\s*(m²|m2)", str(s), flags=re.I)
    return int(m.group(1)) if m else None

def _parse_price_soles(s):
    moneda, val = parse_precio_con_moneda(str(s))
    return val if moneda == "S" else None

def normalize_text(text):
    """Elimina acentos y pasa a minúsculas"""
    import unicodedata
    return unicodedata.normalize('NFKD', text.lower()).encode('ASCII','ignore').decode('utf-8')

def _extract_int_from_text(s):
    """Extrae el primer número entero de una cadena de texto."""
    if s is None:
        return None
    text = str(s).strip()
    text = re.sub(r'\s+', ' ', text)
    m = re.search(r'(\d+)', text)
    return int(m.group(1)) if m else None