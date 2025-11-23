from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd

# Importar el orquestador principal
from orchestrator import run_all_scrapers

# Importar también los scrapers individuales por si quieres llamarlos por separado
from scrapers.nestoria import scrape_nestoria
from scrapers.infocasas import scrape_infocasas
from scrapers.urbania import scrape_urbania
from scrapers.properati import scrape_properati
from scrapers.doomos import scrape_doomos

# --- Inicialización de Flask ---
app = Flask(__name__)
CORS(app)  # Permite que React (desde otro puerto) llame a esta API

# Mapeo de strings a funciones de scraper
SCRAPER_MAP = {
    "nestoria": scrape_nestoria,
    "infocasas": scrape_infocasas,
    "urbania": scrape_urbania,
    "properati": scrape_properati,
    "doomos": scrape_doomos,
}

def _get_params_from_request(req):
    """Función auxiliar para extraer parámetros de la URL."""
    zona = req.args.get('zona', '')
    dormitorios = req.args.get('dormitorios', '0')
    banos = req.args.get('banos', '0')
    palabras_clave = req.args.get('palabras_clave', '')
    
    price_min_str = req.args.get('price_min')
    price_max_str = req.args.get('price_max')
    
    price_min = int(price_min_str) if price_min_str and price_min_str.isdigit() else None
    price_max = int(price_max_str) if price_max_str and price_max_str.isdigit() else None
    
    return {
        "zona": zona,
        "dormitorios": dormitorios,
        "banos": banos,
        "palabras_clave": palabras_clave,
        "price_min": price_min,
        "price_max": price_max
    }

# -------------------- API Endpoints --------------------

@app.route('/scrape-all', methods=['GET'])
def handle_scrape_all():
    """
    Endpoint para ejecutar TODOS los scrapers, combinarlos y filtrarlos.
    Ej: GET http://127.0.0.1:5001/scrape-all?zona=miraflores&dormitorios=2
    """
    params = _get_params_from_request(request)
    print(f"Recibida petición para /scrape-all con params: {params}")

    try:
        # Ejecutar el orquestador
        df = run_all_scrapers(**params)
        
        # Convertir el DataFrame a JSON
        json_results = df.to_dict('records')
        return jsonify(json_results)

    except Exception as e:
        print(f"Error en el endpoint /scrape-all: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/scrape/<source>', methods=['GET'])
def handle_scrape_single(source: str):
    """
    Endpoint para ejecutar UN SOLO scraper.
    Ej: GET http://127.0.0.1:5001/scrape/doomos?zona=surquillo
    Ej: GET http://127.0.0.1:5001/scrape/nestoria?zona=lima
    """
    params = _get_params_from_request(request)
    print(f"Recibida petición para /scrape/{source} con params: {params}")
    
    # Buscar la función de scraper en el mapeo
    scraper_function = SCRAPER_MAP.get(source.lower())
    
    if not scraper_function:
        return jsonify({"error": f"Fuente '{source}' no encontrada. Fuentes válidas: {list(SCRAPER_MAP.keys())}"}), 404

    try:
        # Ejecutar el scraper individual
        df = scraper_function(**params)
        
        # Convertir el DataFrame a JSON
        json_results = df.to_dict('records')
        return jsonify(json_results)

    except Exception as e:
        print(f"Error en el endpoint /scrape/{source}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Endpoint de bienvenida para saber que la API está funcionando."""
    return jsonify({
        "message": "API de Scrapers está en funcionamiento.",
        "endpoints": {
            "/scrape-all": "Ejecuta todos los scrapers y combina resultados.",
            "/scrape/<fuente>": "Ejecuta un scraper individual. Fuentes: [nestoria, infocasas, urbania, properati, doomos]"
        },
        "query_params_opcionales": "?zona=...&dormitorios=...&banos=...&price_min=...&price_max=...&palabras_clave=..."
    })

# --- Iniciar el servidor ---
if __name__ == '__main__':
    # Usamos el puerto 5001 para el backend
    app.run(debug=True, port=5001)