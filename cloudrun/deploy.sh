SERVICE_ROOT_DIR=$1 # ej. inegi_localizacion
FUNCTION_NAME=$2    # ej. inegi_localizacion

# --- Configuración ---
RUNTIME="python312" 
MEMORY="8GB"
TIMEOUT="600s"
MIN_INSTANCES="1"
MAX_INSTANCES="20"
ENTRY_POINT="functionRun"

PROJECT_ID=$(grep "PROJECT_ID" .env | cut -d '=' -f 2)
REGION=$(grep "REGION" .env | cut -d '=' -f 2)
GCS_PATH=$(grep "GCS_PATH" .env | cut -d '=' -f 2)

echo ""
echo "================================================"
echo "INICIANDO DESPLIEGUE DE FUNCION"
echo "================================================"

# Validación de parámetros
if [ -z "$SERVICE_ROOT_DIR" ] || [ -z "$FUNCTION_NAME" ]; then
    echo "Uso: $0 <directorio_raiz_servicio> <nombreFuncion_cloudRun>"
    echo "Ejemplo: $0 ./path_ejemplo cloudrun_ejemplo"
    exit 1
fi

if [ ! -d "$SERVICE_ROOT_DIR" ]; then
    echo "Error: Directorio $SERVICE_ROOT_DIR no encontrado."
    exit 1
fi

ZIP_FILE_NAME="${FUNCTION_NAME}.zip"
ZIP_FILE_PATH="$(pwd)/${ZIP_FILE_NAME}"  
GCS_ZIP_PATH="${GCS_PATH}/${ZIP_FILE_NAME}"
ENV_FILE_PATH="${SERVICE_ROOT_DIR}/local_env.yaml"

echo ""
echo "================================================"
echo "Carga a cloud storage"
echo "================================================"
echo ""
echo "Creando ZIP para $FUNCTION_NAME desde $SERVICE_ROOT_DIR..."
(cd "$SERVICE_ROOT_DIR" && zip -j "$ZIP_FILE_PATH" * 2>/dev/null || zip -j "$ZIP_FILE_PATH" ./*)

# Eliminar archivos locales del ZIP si existen
if [ -f "$ZIP_FILE_PATH" ]; then
    echo "Eliminando archivos locales del ZIP..."
    zip -d "$ZIP_FILE_PATH" "local*" 2>/dev/null || true
fi


echo "Subiendo $ZIP_FILE_PATH a $GCS_ZIP_PATH..."
gsutil cp "$ZIP_FILE_PATH" "$GCS_ZIP_PATH"

echo ""
echo "================================================"
echo "Carga a cloud storage"
echo "================================================"
echo ""

echo "Desplegando función $FUNCTION_NAME..."
gcloud functions deploy "$FUNCTION_NAME" \
    --entry-point=$ENTRY_POINT \
    --runtime "$RUNTIME" \
    --trigger-http \
    --region "$REGION" \
    --source="$GCS_ZIP_PATH" \
    --gen2 \
    --memory="$MEMORY" \
    --timeout="$TIMEOUT" \
    --min-instances="$MIN_INSTANCES" \
    --max-instances="$MAX_INSTANCES" \
    --env-vars-file="$ENV_FILE_PATH"

#    --no-allow-unauthenticated \


echo ""
echo "================================================"
echo "Limpiando archivo ZIP local..."
echo "================================================"
echo ""
rm "$ZIP_FILE_PATH"

echo ""
echo "================================================"
echo "Despliegue de $FUNCTION_NAME finalizado"
echo "================================================"
echo ""