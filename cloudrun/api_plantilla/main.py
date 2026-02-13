# Librerias base para clour Run
import os
from flask import jsonify
import functions_framework

## Ingresar logica de notebook

# endpoint unico de cloud run
@functions_framework.http
def functionRun(request):
    # Utilizar la logica del notebook dentro de una estructura de api
    """Función principal para ejecutar el pipeline"""

    # Salida esperada, con mensaje y datos de respuesta
    return jsonify({"message": "executed successfully", "data": None})