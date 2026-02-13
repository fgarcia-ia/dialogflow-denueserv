echo "Testing local main"
curl -X POST http://localhost:4911/ \
     -H "Content-Type: application/json" \
     -d '{"servicio": "mascotas", "latitud": 19.432607, "longitud": -99.133209, "metros": 1000}'