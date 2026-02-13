from flask import Flask, request, jsonify 
from main import functionRun
import os
from yaml import load, Loader

#Usa archivos locales para las variables de entorno
with open('local_env.yaml', 'r') as file:
    env = load(file, Loader=Loader)
    for key, value in env.items():
        os.environ[key] = value

app = Flask(__name__)

@app.route('/', methods=['POST'])
@app.route('/endpoint', methods=['POST']) 

def endpoint():
    """Simulador local del main"""
    return functionRun(request)

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4911)) 
    print(f"Running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)