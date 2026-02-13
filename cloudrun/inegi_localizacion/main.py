# Librerias base para clour Run
import os
from flask import jsonify
import functions_framework

import time
from geopy.geocoders import Photon

# Photon no requiere user_agent obligatorio, pero es buena práctica ponerlo.
def get_location(direccion: str) -> tuple[float, float] | bool:
    """
    Obtiene la latitud y longitud de una dirección
    Args:
        direccion: str - La dirección a buscar
    Returns:
        tuple: (latitude, longitude) si la dirección es encontrada, False en caso contrario
    """
    geolocator = Photon(user_agent="inegi_test_location")

    try:
        location = geolocator.geocode(direccion)
        
        if location:
            print(f"Dirección encontrada: {location.address}")
            print(f"Latitud: {location.latitude}, Longitud: {location.longitude}")
            return location.latitude, location.longitude
        else:
            print("No se encontró la dirección.")
            return False
    except Exception as e:
        print(f"Ocurrió un error: {e}")

# Si vas a buscar muchas direcciones en un ciclo, respeta a Nominatim:
# time.sleep(1) # Espera 1 segundo entre peticiones

# endpoint unico de cloud run
@functions_framework.http
def functionRun(request):
    """
    Función principal para ejecutar el pipeline
    Args:
        request: request - La solicitud HTTP
    Returns:
        json: (message, data) si la dirección es encontrada, (message, None) en caso contrario
    """
    try:
        direccion = request.json.get('direccion')
    except Exception as e:
        print(f"Ocurrió un error al obtener payload: {e}")
        return jsonify({"message": f"Error: {str(e)}", "data": None}), 500

    if not direccion:
        return jsonify({"message": "direccion is required", "data": None}), 400
    latitude_longitude = get_location(direccion)

    if latitude_longitude:
        return jsonify({"message": "direccion found", "data": latitude_longitude}), 200
    else:
        return jsonify({"message": "direccion not found", "data": None}), 404
