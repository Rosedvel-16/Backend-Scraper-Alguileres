import re
import pandas as pd
from typing import Optional

# Importar las funciones de scraping de sus respectivos archivos
from scrapers.nestoria import scrape_nestoria
from scrapers.infocasas import scrape_infocasas
from scrapers.urbania import scrape_urbania
from scrapers.properati import scrape_properati
from scrapers.doomos import scrape_doomos

# Importar helpers de filtrado desde common
from scrapers.common import _parse_price_soles, _extract_int_from_text

# -------------------- Filtrado y Unificación --------------------
SCRAPERS = [
    ("nestoria", scrape_nestoria),
    ("infocasas", scrape_infocasas),
    ("urbania", scrape_urbania),
    ("properati", scrape_properati),
    ("doomos", scrape_doomos),
]

def _filter_df_strict(df, dormitorios_req, banos_req, price_min, price_max):
    if df is None or df.empty:
        return pd.DataFrame()
    dfc = df.copy().reset_index(drop=True)
    dfc["_precio_soles"] = dfc["precio"].apply(_parse_price_soles)
    dfc["_dorm_num"] = dfc["dormitorios"].apply(_extract_int_from_text)
    dfc["_banos_num"] = dfc["baños"].apply(_extract_int_from_text)
    mask = pd.Series(True, index=dfc.index)
    # only require dorm/banos if user requested them
    try:
        if dormitorios_req is not None and str(dormitorios_req).strip() != "" and str(dormitorios_req) != "0":
            dorm_req_int = int(dormitorios_req)
            mask &= (dfc["_dorm_num"].notnull()) & (dfc["_dorm_num"] == dorm_req_int)
    except:
        pass
    try:
        if banos_req is not None and str(banos_req).strip() != "" and str(banos_req) != "0":
            banos_req_int = int(banos_req)
            mask &= (dfc["_banos_num"].notnull()) & (dfc["_banos_num"] == banos_req_int)
    except:
        pass
    if (price_min is not None) or (price_max is not None):
        if price_min is None:
            price_min = -10**12
        if price_max is None:
            price_max = 10**12
        mask &= dfc["_precio_soles"].notnull()
        mask &= (dfc["_precio_soles"] >= int(price_min)) & (dfc["_precio_soles"] <= int(price_max))
    df_filtered = dfc.loc[mask].copy().reset_index(drop=True)
    df_filtered.drop(columns=["_precio_soles","_dorm_num","_banos_num"], errors="ignore", inplace=True)
    return df_filtered

def _filter_by_keywords(df, palabras_clave: str):
    if df is None or df.empty or not palabras_clave or not palabras_clave.strip():
        return df
    palabras = palabras_clave.lower().split()
    dfc = df.copy()
    dfc["texto_completo"] = (
        dfc["titulo"].astype(str) + " " +
        dfc.get("descripcion", pd.Series([""]*len(dfc))).astype(str) + " " +
        dfc.get("m2", pd.Series([""]*len(dfc))).astype(str) + " " +
        dfc.get("dormitorios", pd.Series([""]*len(dfc))).astype(str) + " " +
        dfc.get("baños", pd.Series([""]*len(dfc))).astype(str)
    ).str.lower()
    for p in palabras:
        dfc = dfc[dfc["texto_completo"].str.contains(re.escape(p), na=False, case=False)]
    dfc.drop(columns=["texto_completo"], errors="ignore", inplace=True)
    return dfc

def run_all_scrapers(zona: str = "", dormitorios: str = "0", banos: str = "0",
                     price_min: Optional[int] = None, price_max: Optional[int] = None,
                     palabras_clave: str = ""):
    frames = []
    counts_raw = {}
    counts_after = {}
    print(f"🔎 Buscando: zona='{zona}' | dorms={dormitorios} | baños={banos} | pmin={price_min} | pmax={price_max} | keywords='{palabras_clave}'")
    
    for name, func in SCRAPERS:
        print(f"-> Ejecutando scraper: {name}")
        try:
            df = func(zona=zona, dormitorios=dormitorios, banos=banos, price_min=price_min, price_max=price_max, palabras_clave=palabras_clave)
        except TypeError:
            # backward compatibility: call with fewer args
            try:
                df = func(zona=zona, dormitorios=dormitorios, banos=banos, price_min=price_min, price_max=price_max)
            except Exception as e:
                print(f" ❌ Error ejecutando {name} (fallback):", e)
                df = pd.DataFrame()
        except Exception as e:
            print(f" ❌ Error ejecutando {name}:", e)
            df = pd.DataFrame()
        
        if df is None or not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(columns=["titulo","precio","m2","dormitorios","baños","descripcion","link","imagen_url"])
        
        # ensure columns present
        for col in ["titulo","precio","m2","dormitorios","baños","descripcion","link","imagen_url"]:
            if col not in df.columns:
                df[col] = ""
        
        total_raw = len(df)
        counts_raw[name] = total_raw
        print(f"   encontrados (raw): {total_raw}")
        
        # normalize
        df = df.fillna("").astype(object)
        for col in ["titulo","precio","m2","dormitorios","baños","descripcion","link","imagen_url"]:
            df[col] = df[col].astype(str).str.strip().replace({None: "", "None": ""})
        
        # strict filters (price/dorm/banos)
        df_filtered = _filter_df_strict(df, dormitorios, banos, price_min, price_max)
        print(f"   después filtrado estricto: {len(df_filtered)}")
        
        # keywords: apply post-scrape ONLY for sources that didn't use keyword in URL
        # EXCLUDE properati because it uses 'amenities' and text may not contain the keyword
        if palabras_clave and palabras_clave.strip() and name not in ("urbania", "doomos", "properati"):
            prev = len(df_filtered)
            df_filtered = _filter_by_keywords(df_filtered, palabras_clave)
            print(f"   después filtrar por keywords: {len(df_filtered)} (eliminados {prev - len(df_filtered)})")
        
        counts_after[name] = len(df_filtered)
        if len(df_filtered) > 0:
            df_filtered = df_filtered.copy()
            df_filtered["fuente"] = name
            frames.append(df_filtered)
    
    if not frames:
        print("⚠️ Ninguna fuente devolvió anuncios tras filtrar. Conteo raw:", counts_raw)
        return pd.DataFrame()
    
    combined = pd.concat(frames, ignore_index=True, sort=False)
    
    # Eliminar filas donde el link empieza con "#" o está vacío
    combined = combined[~combined["link"].str.startswith("#")].reset_index(drop=True)
    combined = combined[combined["link"] != ""].reset_index(drop=True)
    combined = combined.drop_duplicates(subset=["link","titulo"], keep="first").reset_index(drop=True)
    
    print(f"Resultados combinados y unificados: {len(combined)}")
    
    # Devolver el DataFrame combinado
    return combined