# Librerias base para clour Run
import os
from flask import jsonify
import functions_framework
import requests
import urllib.parse

## Ingresar logica de notebook
TOKEN = os.getenv('INEGI_TOKEN')

# endpoint unico de cloud run
@functions_framework.http
def functionRun(request):
    """
    HTTP Cloud Function para consultar la API del DENUE (INEGI).
    Recibe un JSON con: servicio, latitud, longitud, token, metros (opcional).
    """
    
    # 1. Manejo de CORS (Opcional pero recomendado para llamadas desde web)
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # 2. Obtener datos del request (JSON)
    request_json = request.get_json(silent=True)
    
    if not request_json:
        return ({"error": "El cuerpo de la solicitud debe ser un JSON válido"}, 400, headers)

    # 3. Extraer variables
    servicio = request_json.get('servicio')
    latitud = request_json.get('latitud')
    longitud = request_json.get('longitud')
    metros = request_json.get('metros', 250) # Por defecto 250 metros si no se envía

    # 4. Validar que existan los datos obligatorios
    if not all([servicio, latitud, longitud]):
        missing = [k for k, v in {"servicio": servicio, "latitud": latitud, "longitud": longitud}.items() if not v]
        return ({"error": f"Faltan parámetros obligatorios: {', '.join(missing)}"}, 400, headers)

    try:
        # 5. Codificar el servicio para URL (ej. "tacos de asada" -> "tacos,de,asada")
        servicio_encoded = str(servicio).replace(' ', ',')

        # 6. Construir la URL de INEGI
        # Estructura: .../Buscar/{condicion}/{lat},{lon}/{metros}/{token}
        url_inegi = (
            f"https://www.inegi.org.mx/app/api/denue/v1/consulta/Buscar/"
            f"{servicio_encoded}/{latitud},{longitud}/{metros}/{TOKEN}"
        )

        # 7. Hacer la petición a INEGI
        print(f"Consultando INEGI: {servicio} en {latitud}, {longitud}") # Log para Cloud Logging
        print(f"URL: {url_inegi}")
        response = requests.get(url_inegi)
        
        # Verificar si la respuesta de INEGI fue exitosa
        response.raise_for_status()
        
        # 8. Devolver los datos al cliente
        return (response.json(), 200, headers)

    except requests.exceptions.HTTPError as err:
        return ({"error": "Error en la API de INEGI", "detalle": str(err)}, 502, headers)
    except Exception as e:
        return ({"error": "Error interno del servidor", "detalle": str(e)}, 500, headers)