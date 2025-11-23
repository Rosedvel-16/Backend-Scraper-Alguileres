import re
import pandas as pd
from typing import Optional
from bs4 import BeautifulSoup
import unicodedata


def slugify_zone(zona: str) -> str:
    """Convierte una cadena a un formato de URL amigable (slug) sin tildes."""
    if not zona:
        return ""
    s = zona.lower().strip()
    trans = str.maketrans("áéíóúñü", "aeiounu")
    s = s.translate(trans)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s

def parse_precio_con_moneda(precio_str):
    """Extrae el tipo de moneda (S/USD) y el valor numérico de una cadena de precio."""
    if not precio_str:
        return (None, None)
    s = str(precio_str)
    moneda = None
    if "S/" in s or s.strip().startswith("S/"):
        moneda = "S"
    elif "$" in s:
        moneda = "USD"
    
    s_cleaned = re.sub(r"[^\d\.\,]", "", s)
    s_nums = re.sub(r"[^\d]", "", s_cleaned) 
    
    return (moneda, int(s_nums)) if s_nums else (moneda, None)

def _extract_m2(s):
    """Extrae la cantidad de metros cuadrados de una cadena."""
    if s is None:
        return None
    m = re.search(r"(\d{1,4})\s*(m²|m2)", str(s), flags=re.I)
    return int(m.group(1)) if m else None

def _parse_price_soles(s):
    """Devuelve el valor numérico solo si la moneda es Soles (S)."""
    moneda, val = parse_precio_con_moneda(str(s))
    return val if moneda == "S" else None

def normalize_text(text):
    """Elimina acentos y pasa a minúsculas."""
    return unicodedata.normalize('NFKD', text.lower()).encode('ASCII','ignore').decode('utf-8')

def _extract_int_from_text(s):
    """Extrae el primer número entero de una cadena de texto de forma robusta."""
    if s is None:
        return None
    text = str(s).strip()
    text = re.sub(r'\s+', ' ', text)
    m = re.search(r'(\d+)', text)
    return int(m.group(1)) if m else None