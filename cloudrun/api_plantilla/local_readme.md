# Guía para Desplegar Procesos de Datos a Cloud Run

## 📋 Introducción

Esta guía te ayudará a convertir tus notebooks de Jupyter (`.ipynb`) en servicios de Cloud Run de Google Cloud Platform (GCP). Cloud Run permite ejecutar tus procesos de datos de forma automatizada y escalable sin necesidad de mantener servidores.

### ¿Qué es Cloud Run?
Cloud Run es un servicio de GCP que ejecuta código Python como una API web. Cuando alguien hace una petición HTTP (POST), tu código se ejecuta y devuelve una respuesta en formato JSON.

### ¿Por qué usar Cloud Run?
- ✅ **Automatización**: Puedes programar ejecuciones automáticas
- ✅ **Escalabilidad**: Se adapta automáticamente a la carga de trabajo
- ✅ **Sin servidores**: No necesitas mantener infraestructura
- ✅ **Integración**: Se integra fácilmente con otros servicios de GCP

---

## 📁 Estructura de Archivos

Antes de comenzar, es importante entender qué hace cada archivo en la plantilla:

```
api_plantilla/
├── main.py              # Código principal que se ejecuta en Cloud Run
├── local_main.py         # Versión local para pruebas (usa Flask)
├── requirements.txt      # Librerías de Python necesarias
├── Tools.py              # Funciones auxiliares (BigQuery, Storage, etc.)
├── local_env.yaml        # Variables de entorno para pruebas locales
├── local_test.sh         # Script para probar el servicio localmente
└── local_readme.md       # Esta guía
```

### Descripción de Archivos

- **`main.py`**: Contiene la lógica principal de tu proceso. Es el archivo que Cloud Run ejecutará.
- **`local_main.py`**: Permite ejecutar y probar tu código localmente antes de desplegar.
- **`requirements.txt`**: Lista todas las librerías de Python que necesita tu código (pandas, numpy, etc.).
- **`Tools.py`**: Funciones reutilizables para trabajar con BigQuery, Cloud Storage y otras herramientas de GCP.
- **`local_env.yaml`**: Variables de configuración (rutas de archivos, IDs de proyectos, etc.).
- **`local_test.sh`**: Script para hacer pruebas HTTP al servicio local.

---

## 🚀 Proceso Paso a Paso

### Paso 0: Preparación

#### Requisitos Previos
- ✅ Notebook de Jupyter con la lógica del proceso funcionando
- ✅ Ubuntu como sistema operativo (o WSL en Windows, tambien puede ser vertex notebook o collab)
- ✅ Python 3.12 instalado
- ✅ Acceso a GCP con permisos para Cloud Run
- ✅ `gcloud` CLI instalado y configurado

#### Crear una Nueva Carpeta para tu Servicio

1. Copia la carpeta `api_plantilla` y renómbrala con el nombre de tu servicio:
   ```bash
   cp -r api_plantilla api_mi_proceso
   cd api_mi_proceso
   ```

2. El nombre debe ser descriptivo y seguir el formato `api_nombre_proceso` (ej: `api_carga_presupuesto`, `api_procesamiento_datos`)

---

### Paso 1: Convertir la Lógica del Notebook a `main.py`

#### 1.1 Entender la Estructura

El archivo `main.py` tiene una estructura básica:

```python
import os
from flask import jsonify
import functions_framework

@functions_framework.http
def functionRun(request):
    """Función principal para ejecutar el pipeline"""
    
    # TODO: Aquí va tu lógica del notebook
    
    return jsonify({"message": "executed successfully", "data": None})
```

#### 1.2 Pasos para Migrar tu Notebook

1. **Abre tu notebook** y revisa las celdas principales
2. **Identifica las funciones principales** que realizan el trabajo
3. **Copia el código relevante** al archivo `main.py`
4. **Elimina código de visualización** (matplotlib, print de debugging, etc.)
5. **Mantén solo la lógica de procesamiento**

#### 1.3 Ejemplo de Migración

**Notebook Original:**
```python
# Celda 1: Cargar datos
import pandas as pd
df = pd.read_excel("archivo.xlsx")

# Celda 2: Procesar
df['nueva_columna'] = df['columna1'] * 2

# Celda 3: Guardar
df.to_csv("resultado.csv")
print("Proceso completado")
```

**Versión en `main.py`:**
```python
import os
from flask import jsonify
import pandas as pd
import functions_framework
from Tools import upload_to_bigquery  # Función auxiliar

@functions_framework.http
def functionRun(request):
    """Función principal para ejecutar el pipeline"""
    try:
        # 1. Cargar datos
        archivo = os.getenv('ARCHIVO_EXCEL')
        df = pd.read_excel(archivo)
        
        # 2. Procesar
        df['nueva_columna'] = df['columna1'] * 2
        
        # 3. Guardar en BigQuery
        upload_to_bigquery(
            df,
            project_id="aserta-mx-prd-warehousing",
            dataset_id="mi_dataset",
            table_id="mi_tabla",
            if_exists="replace"
        )
        
        # 4. Retornar respuesta
        return jsonify({
            "message": "Proceso completado exitosamente",
            "data": df.head(10).to_dict(orient='records')  # Primeras 10 filas
        })
    except Exception as e:
        return jsonify({
            "message": f"Error: {str(e)}",
            "data": None
        }), 500
```

#### 1.4 Buenas Prácticas

- ✅ **Manejo de errores**: Usa `try/except` para capturar errores
- ✅ **Logging**: Usa `print()` para mensajes de depuración (aparecerán en los logs de Cloud Run)
- ✅ **Respuestas claras**: Devuelve mensajes descriptivos en el JSON
- ✅ **Datos de muestra**: Incluye una muestra de los datos procesados en la respuesta

---

### Paso 2: Configurar Variables de Entorno (`local_env.yaml`)

#### 2.1 ¿Qué son las Variables de Entorno?

Son valores de configuración que pueden cambiar entre entornos (local vs producción). Ejemplos:
- Rutas de archivos en Cloud Storage
- IDs de proyectos de GCP
- Nombres de tablas de BigQuery
- Versiones de APIs

#### 2.2 Configurar `local_env.yaml`

Edita el archivo `local_env.yaml` con tus variables:

```yaml
# Ejemplo de configuración
ARCHIVO_EXCEL: gs://mi-bucket/datos/archivo.xlsx
PROJECT_ID: aserta-mx-prd-warehousing
DATASET_ID: mi_dataset
TABLA_DESTINO: mi_tabla
VERSION: 1.0.0
```

#### 2.3 Usar Variables en el Código

En `main.py`, accede a las variables así:

```python
archivo = os.getenv('ARCHIVO_EXCEL')
project_id = os.getenv('PROJECT_ID', 'default_project')  # Con valor por defecto
```

> **Nota**: Si tu servicio no necesita variables de entorno, puedes dejar `local_env.yaml` vacío o con solo `VERSION: 1.0.0`

---

### Paso 3: Configurar Dependencias (`requirements.txt`)

#### 3.1 ¿Qué es `requirements.txt`?

Este archivo lista todas las librerías de Python que necesita tu código. Cloud Run las instalará automáticamente.

#### 3.2 Agregar Librerías

El archivo base ya incluye las librerías más comunes. Agrega las que falten:

```txt
functions-framework==3.*
Flask
requests
gunicorn
openpyxl
pandas
numpy
google-cloud-storage
google-cloud-bigquery
tqdm
ipykernel
gcsfs
pandas-gbq
pyarrow
fastapi
uvicorn
pydantic
tabulate
looker-sdk

# Agrega aquí tus librerías adicionales
# Ejemplo:
# scikit-learn==1.3.0
# matplotlib==3.7.0
```

#### 3.3 Verificar Librerías del Notebook

1. Revisa las celdas `import` de tu notebook
2. Compara con `requirements.txt`
3. Agrega las que falten

> **Importante**: El archivo debe llamarse exactamente `requirements.txt` (no `requeriments.txt` ni otro nombre)

---

### Paso 4: Actualizar `Tools.py` (si es necesario)

#### 4.1 ¿Cuándo actualizar `Tools.py`?

Solo si:
- Tu notebook usa funciones personalizadas que no están en `Tools.py`
- Necesitas agregar nuevas funciones auxiliares
- Hay cambios en las funciones existentes

#### 4.2 Funciones Disponibles en `Tools.py`

- `upload_to_bigquery()`: Subir DataFrames a BigQuery
- `query_to_dataframe()`: Ejecutar queries SQL y obtener DataFrames
- `download_from_storage()`: Descargar archivos de Cloud Storage
- `upload_to_storage()`: Subir archivos a Cloud Storage

Revisa el archivo `Tools.py` para ver todas las funciones disponibles.

---

### Paso 5: Probar Localmente

#### 5.1 Activar el Entorno Virtual

```bash
# Desde la raíz del proyecto
source .venv/bin/activate
```

#### 5.2 Instalar Dependencias Localmente

```bash
cd api_mi_proceso
pip install -r requirements.txt
```

#### 5.3 Ejecutar el Servicio Local

```bash
python local_main.py
```

Deberías ver un mensaje como:
```
Running on http://localhost:4911
```

> **Nota**: Asegúrate de estar en el directorio del servicio (`api_mi_proceso`)

#### 5.4 Probar el Servicio

En una **nueva terminal** (sin cerrar la anterior):

```bash
cd api_mi_proceso
source ./local_test.sh
```

O manualmente:
```bash
curl -X POST http://localhost:4911/ \
     -H "Content-Type: application/json" \
     -d '{}'
```

#### 5.5 Personalizar `local_test.sh`

Si tu servicio necesita parámetros, edita `local_test.sh`:

```bash
echo "Testing local main"
curl -X POST http://localhost:4911/ \
     -H "Content-Type: application/json" \
     -d '{"parametro1": "valor1", "parametro2": "valor2"}'
```

#### 5.6 Verificar la Respuesta

Deberías recibir un JSON como:
```json
{
  "message": "executed successfully",
  "data": [...]
}
```

Si hay errores, revísalos en la terminal donde ejecutaste `local_main.py`.

---

### Paso 6: Desplegar a Cloud Run

#### 6.1 Preparación

1. Asegúrate de estar en el directorio `src`:
   ```bash
   cd ~/Aserta/aserta-dwh/src
   ```

2. Verifica que tu servicio esté listo:
   - ✅ `main.py` funciona localmente
   - ✅ `requirements.txt` tiene todas las dependencias
   - ✅ `local_env.yaml` está configurado

#### 6.2 Ejecutar el Despliegue

```bash
source ./deploy.sh ./api_mi_proceso nombre_funcion_cloudrun
```

**Parámetros:**
- `./api_mi_proceso`: Ruta relativa a tu carpeta del servicio
- `nombre_funcion_cloudrun`: Nombre que tendrá tu función en GCP (ej: `carga_presupuesto_bq`)

**Ejemplo completo:**
```bash
source ./deploy.sh ./api_carga_presupuesto carga_presupuesto_bq
```

#### 6.3 ¿Qué hace el Script de Despliegue?

1. ✅ Valida que exista el directorio del servicio
2. ✅ Crea un archivo ZIP con todos los archivos necesarios
3. ✅ Sube el ZIP a Cloud Storage
4. ✅ Despliega la función en Cloud Run
5. ✅ Configura las variables de entorno desde `local_env.yaml`
6. ✅ Limpia archivos temporales

#### 6.4 Verificar el Despliegue

Después del despliegue, verás un mensaje con la URL de tu función:
```
https://us-east4-aserta-dev-dwh.cloudfunctions.net/nombre_funcion_cloudrun
```

Puedes probarla con:
```bash
curl -X POST https://us-east4-aserta-dev-dwh.cloudfunctions.net/nombre_funcion_cloudrun \
     -H "Content-Type: application/json" \
     -d '{}'
```

---

## 🔧 Troubleshooting (Solución de Problemas)

### Error: "ModuleNotFoundError: No module named 'pandas'"

**Causa**: La librería no está en `requirements.txt` o el archivo tiene un nombre incorrecto.

**Solución**:
1. Verifica que el archivo se llame exactamente `requirements.txt`
2. Agrega la librería faltante al archivo
3. Vuelve a desplegar

### Error: "FileNotFoundError: No such file or directory"

**Causa**: Ruta de archivo incorrecta o archivo no existe en Cloud Storage.

**Solución**:
1. Verifica que la ruta en `local_env.yaml` sea correcta
2. Asegúrate de que el archivo exista en Cloud Storage
3. Verifica permisos de acceso

### Error: "Permission denied" o "403 Forbidden"

**Causa**: Falta de permisos en GCP.

**Solución**:
1. Verifica que tengas permisos de Cloud Run Admin
2. Verifica permisos de Cloud Storage y BigQuery
3. Contacta al administrador de GCP

### El servicio funciona localmente pero falla en Cloud Run

**Causa**: Variables de entorno no configuradas o rutas incorrectas.

**Solución**:
1. Verifica que `local_env.yaml` tenga todas las variables necesarias
2. Revisa los logs de Cloud Run en la consola de GCP
3. Asegúrate de que las rutas usen rutas de GCS (gs://) y no rutas locales

### Error: "Timeout" en Cloud Run

**Causa**: El proceso tarda más de 10 minutos (600 segundos).

**Solución**:
1. Optimiza tu código para que sea más rápido
2. Si es necesario, contacta al equipo para aumentar el timeout
3. Considera dividir el proceso en pasos más pequeños

---

## 📝 Checklist de Despliegue

Antes de desplegar, verifica:

- [ ] El código funciona correctamente en el notebook
- [ ] `main.py` contiene toda la lógica necesaria
- [ ] `requirements.txt` tiene todas las librerías
- [ ] `local_env.yaml` está configurado correctamente
- [ ] El servicio funciona localmente (`python local_main.py`)
- [ ] Las pruebas locales pasan (`source ./local_test.sh`)
- [ ] No hay archivos de prueba o temporales en la carpeta
- [ ] El nombre del servicio es descriptivo y claro

---

## 💡 Mejores Prácticas

### Código

1. **Manejo de errores**: Siempre usa `try/except` para capturar errores
2. **Logging**: Usa `print()` para mensajes importantes (aparecen en logs de Cloud Run)
3. **Validación**: Valida datos de entrada antes de procesarlos
4. **Respuestas claras**: Devuelve mensajes descriptivos en caso de error

### Variables de Entorno

1. **No hardcodear valores**: Usa variables de entorno para configuración
2. **Valores por defecto**: Proporciona valores por defecto cuando sea posible
3. **Documentación**: Documenta qué hace cada variable

### Despliegue

1. **Probar localmente primero**: Siempre prueba localmente antes de desplegar
2. **Versiones**: Usa versiones específicas en `requirements.txt` cuando sea posible
3. **Nombres descriptivos**: Usa nombres claros para tus servicios

---

## 📚 Recursos Adicionales

### Documentación Oficial

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Functions Framework for Python](https://github.com/GoogleCloudPlatform/functions-framework-python)
- [BigQuery Python Client](https://cloud.google.com/bigquery/docs/reference/libraries)

### Soporte

Si tienes dudas o problemas:
1. Revisa los logs de Cloud Run en la consola de GCP
2. Consulta con el equipo de datos
3. Revisa ejemplos de otros servicios desplegados

---

## 🎯 Ejemplo Completo

### Caso: Cargar datos de Excel a BigQuery

**1. Notebook Original:**
```python
import pandas as pd
df = pd.read_excel("datos.xlsx")
df.to_gbq("mi_dataset.mi_tabla", project_id="mi_proyecto")
```

**2. `main.py`:**
```python
import os
from flask import jsonify
import pandas as pd
import functions_framework
from Tools import upload_to_bigquery

@functions_framework.http
def functionRun(request):
    try:
        archivo = os.getenv('ARCHIVO_EXCEL')
        df = pd.read_excel(archivo)
        
        upload_to_bigquery(
            df,
            project_id=os.getenv('PROJECT_ID'),
            dataset_id=os.getenv('DATASET_ID'),
            table_id=os.getenv('TABLA_DESTINO'),
            if_exists="replace"
        )
        
        return jsonify({
            "message": f"Cargados {len(df)} registros exitosamente",
            "data": df.head(5).to_dict(orient='records')
        })
    except Exception as e:
        return jsonify({
            "message": f"Error: {str(e)}",
            "data": None
        }), 500
```

**3. `local_env.yaml`:**
```yaml
ARCHIVO_EXCEL: gs://mi-bucket/datos.xlsx
PROJECT_ID: aserta-mx-prd-warehousing
DATASET_ID: mi_dataset
TABLA_DESTINO: mi_tabla
VERSION: 1.0.0
```

**4. Desplegar:**
```bash
cd ~/Insaite/aserta-dwh/src
source ./deploy.sh ./api_carga_excel carga_excel_bq
```

---

## ✅ ¡Listo!

Con esta guía deberías poder convertir cualquier notebook en un servicio de Cloud Run. Recuerda: **siempre prueba localmente primero** antes de desplegar.

¡Éxito con tu despliegue! 🚀
