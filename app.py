from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
import time # Importar time para medir la duración

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

# Configurar CORS - permitir tu dominio de Vercel (sin la barra final)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://frontend-scraper-alquileres.vercel.app"
        ]
    }
})

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
    """
    params = _get_params_from_request(request)
    print(f"Recibida petición para /scrape-all con params: {params}")

    start_time = time.time()
    try:
        # Ejecutar el orquestador
        df = run_all_scrapers(**params)
        
        end_time = time.time()
        print(f"✅ BÚSQUEDA /scrape-all finalizada en {end_time - start_time:.2f} segundos.")
        
        # Convertir el DataFrame a JSON y devolverlo
        json_results = df.to_dict('records')
        return jsonify(json_results)

    except Exception as e:
        end_time = time.time()
        print(f"❌ Error en el endpoint /scrape-all después de {end_time - start_time:.2f}s: {e}")
        return jsonify({"error": "Error interno del servidor. Probable falta de memoria (OOMKilled)."}), 500


@app.route('/scrape/<source>', methods=['GET'])
def handle_scrape_single(source: str):
    """
    Endpoint para ejecutar UN SOLO scraper.
    """
    params = _get_params_from_request(request)
    print(f"Recibida petición para /scrape/{source} con params: {params}")
    
    # Buscar la función de scraper en el mapeo
    scraper_function = SCRAPER_MAP.get(source.lower())
    
    if not scraper_function:
        return jsonify({"error": f"Fuente '{source}' no encontrada. Fuentes válidas: {list(SCRAPER_MAP.keys())}"}), 404

    start_time = time.time()
    try:
        # Ejecutar el scraper individual
        df = scraper_function(**params)
        
        end_time = time.time()
        print(f"✅ BÚSQUEDA /scrape/{source} finalizada en {end_time - start_time:.2f} segundos.")

        # Convertir el DataFrame a JSON
        json_results = df.to_dict('records')
        return jsonify(json_results)

    except Exception as e:
        end_time = time.time()
        print(f"❌ Error en el endpoint /scrape/{source} después de {end_time - start_time:.2f}s: {e}")
        return jsonify({"error": f"Error interno del servidor en {source}. Probable falta de memoria (OOMKilled)."}), 500


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
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint para monitoreo."""
    return jsonify({"status": "ok", "message": "Backend is running"}), 200

# Esta sección se ignora en Render porque se usa Gunicorn.
if __name__ == '__main__':
    # Obtener el puerto del entorno o usar 5001 por defecto
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=os.environ.get('FLASK_ENV') != 'production', host='0.0.0.0', port=port)