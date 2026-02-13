echo "Testing cloud run"
curl -X POST "https://insaite-agentesdetermistas-ubicacion-708547631996.us-central1.run.app" \
     -H "Authorization: bearer $(gcloud auth print-identity-token)" \
     -H "Content-Type: application/json" \
     -d '{"direccion": "Paseo de la Reforma 50, Ciudad de México"}'

sleep 10

echo "Testing local main"
curl -X POST http://localhost:4911/ \
     -H "Content-Type: application/json" \
     -d '{"direccion": "Paseo de la Reforma 50, Ciudad de México"}'

