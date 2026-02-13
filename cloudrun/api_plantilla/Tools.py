import io
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pandas_gbq
from google.cloud import bigquery, storage
from google.cloud.bigquery import TimePartitioningType
from tqdm import tqdm


def upload_to_bigquery(
    df: pd.DataFrame,
    project_id: str,
    dataset_id: str,
    table_id: str,
    partitioning_field: str = None,
    time_partitioning_type: str = "DAY",
    clustering_fields: list = None,
    chunk_size: int = 100000,
    if_exists: str = "append",
    location: str = "us-south1",
):
    """
    Sube un DataFrame a una tabla de BigQuery con soporte opcional para
    partición por tiempo y clustering.

    Args:
        df (pd.DataFrame): DataFrame de Pandas a subir.
        project_id (str): ID del proyecto de GCP.
        dataset_id (str): ID del dataset de BigQuery.
        table_id (str): ID de la tabla de destino.
        partitioning_field (str, opcional): Columna para particionar (DATE/TIMESTAMP/DATETIME).
        time_partitioning_type (str): Tipo de partición ('DAY', 'HOUR', 'MONTH', 'YEAR').
        clustering_fields (list, opcional): Lista de campos para clusterizar (STRING permitido).
        chunk_size (int): Cantidad de filas por lote.
        if_exists (str): 'append' o 'replace'.
        location (str): Ubicación del dataset en BigQuery.
    """
    try:
        client = bigquery.Client()
        full_table_id = f"{project_id}.{dataset_id}.{table_id}"

        # 1. Verificar y crear dataset si no existe
        dataset_ref = client.dataset(dataset_id)
        try:
            client.get_dataset(dataset_ref)
        except Exception:
            print(f"Dataset '{dataset_id}' no encontrado. Creando en '{location}'...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = location
            client.create_dataset(dataset)
            print(f"✅ Dataset '{dataset_id}' creado.")

        # 2. Validar/convertir campo de partición
        if partitioning_field:
            if partitioning_field not in df.columns:
                raise ValueError(
                    f"El campo de partición '{partitioning_field}' no existe en el DataFrame."
                )

            if df[partitioning_field].dtype == "object":  # strings
                try:
                    df[partitioning_field] = pd.to_datetime(
                        df[partitioning_field], errors="raise"
                    )
                    print(
                        f"ℹ️ Columna '{partitioning_field}' convertida automáticamente a datetime64."
                    )
                except Exception:
                    raise TypeError(
                        f"El campo '{partitioning_field}' contiene STRINGs no convertibles a fecha/tiempo. "
                        f"Ejemplos: {df[partitioning_field].dropna().unique()[:5]}"
                    )

            if not pd.api.types.is_datetime64_any_dtype(df[partitioning_field]):
                raise TypeError(
                    f"El campo '{partitioning_field}' debe ser DATE/DATETIME/TIMESTAMP, pero es {df[partitioning_field].dtype}"
                )

            # Extra: si partición es por 'DAY', convertir a DATE (sin hora)
            if time_partitioning_type.upper() == "DAY":
                df[partitioning_field] = df[partitioning_field].dt.date
                print(
                    f"ℹ️ Columna '{partitioning_field}' convertida a tipo DATE para partición diaria."
                )

        # 3. Construir esquema BigQuery
        schema = []
        for col, dtype in df.dtypes.items():
            if pd.api.types.is_integer_dtype(dtype):
                field_type = "INTEGER"
            elif pd.api.types.is_float_dtype(dtype):
                field_type = "FLOAT"
            elif pd.api.types.is_bool_dtype(dtype):
                field_type = "BOOLEAN"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                # Detectar si todos los valores son fechas sin hora -> DATE
                if all(
                    x.time() == pd.Timestamp.min.time()
                    for x in df[col].dropna().astype("datetime64[ns]")
                ):
                    field_type = "DATE"
                else:
                    field_type = "TIMESTAMP"
            elif pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(
                dtype
            ):
                field_type = "STRING"
            else:
                field_type = "STRING"  # fallback
            schema.append(bigquery.SchemaField(col, field_type))

        # 4. Definir tabla con partición/clúster
        table = bigquery.Table(full_table_id, schema=schema)

        if partitioning_field:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=getattr(TimePartitioningType, time_partitioning_type.upper()),
                field=partitioning_field,
            )

        if clustering_fields:
            table.clustering_fields = clustering_fields

        # 5. Crear tabla si no existe
        try:
            client.create_table(table)
            print(f"✅ Tabla '{table_id}' creada con esquema de partición/clúster.")
        except Exception as e:
            if "Already Exists" in str(e):
                print(f"⚠️ Tabla '{table_id}' ya existe, se usará.")
            else:
                raise e

        # 6. Subir en fragmentos
        total_rows = len(df)
        print(f"Subiendo {total_rows} registros en lotes de {chunk_size}...")

        for i in range(0, total_rows, chunk_size):
            df_chunk = df.iloc[i : i + chunk_size]

            current_if_exists = (
                "replace" if i == 0 and if_exists == "replace" else "append"
            )

            pandas_gbq.to_gbq(
                df_chunk,
                destination_table=full_table_id,
                project_id=project_id,
                if_exists=current_if_exists,
            )
            print(f"✅ {min(i + chunk_size, total_rows)}/{total_rows} filas subidas...")

        print("🚀 Carga completa a BigQuery.")

    except Exception as e:
        print(f"⚠️ Error al subir datos: {e}")


def serie_cuentaajustada(df: pd.DataFrame, columnacuenta="Cuenta"):
    """Aplica las reglas de transformación a la columna cuenta para identificar las cuentas con lo especificado en el libro azul de reglas"""
    cuentaoriginal = df[columnacuenta].copy()
    cuentaoriginal = cuentaoriginal.astype("int64").astype(str).copy()
    assert (
        cuentaoriginal.dtype == "O"
    ), f"El tipo de dato incluido en la serie {columnacuenta} no es del tipo objeto"
    esprincipal = cuentaoriginal.str[-3:] == "000"  # Bool cuenta principal
    essecundaria = (cuentaoriginal.str[-2:] == "00") & (
        esprincipal == False
    )  # Bool cuenta secundaria
    # esterciaria=cuentaoriginal.str[-1:]=='0' #Bool cuenta terciaria
    cuentaajustada = (
        cuentaoriginal.copy()
    )  # Elaboramos una copia de la original sobre la cual haremos las modificaciones
    cuentaajustada[esprincipal] = cuentaoriginal[esprincipal].apply(
        lambda x: x[1:5].rstrip("0").ljust(4, "0")
    )  # Cuenta pricipal dígitos 2-5
    cuentaajustada[essecundaria] = cuentaoriginal[essecundaria].apply(
        lambda x: x[1:5].rstrip("0") + x[-3].zfill(2)
    )  # Cuenta secundaria es digitos 2-5 y valor numérico posición -2 con formato ##
    # cuentaajustada[esprincipal]=cuentaoriginal[esprincipal].str[1:5].apply(lambda x: x.rstrip("0")) #Cuenta secundaria es digitos 2-5 y valor numérico posición -2 con formato ##
    return cuentaajustada.astype(str)


def buscarcuenta(datos_eeva: pd.DataFrame, cuenta: str):
    if len(cuenta) == 4:
        tipo = "madre"
    else:
        tipo = "padre"
    limite = 5 if tipo == "madre" else 7
    serie_filtro = datos_eeva.Cuenta.str[1:limite] == cuenta
    return datos_eeva[serie_filtro]


def read_gcs_files_to_dataframes_aserta(
    bucket_name: str,
    prefix: str,
    file_type: str = ".xlsx",
    file_prefix: Optional[str] = None,
    delimiter: bool = False,
    read_log_file: bool = True,
    **kwargs: Dict[str, Any],
) -> pd.DataFrame:
    """
    Lee archivos de un bucket de Google Cloud Storage, los concatena y añade una columna con el nombre del archivo.
    Añade un control de registro (file_already_read.txt) para omitir archivos ya procesados.

    Args:
        bucket_name (str): El nombre del bucket de GCS.
        prefix (str): El prefijo o la "carpeta" donde buscar los archivos.
        file_type (str): La extensión de archivo a buscar (por ejemplo, ".xlsx", ".csv").
        file_prefix (str, opcional): Prefijo con el que debe iniciar el nombre del archivo (ej. 'data_').
        delimiter (bool): Si es True, ignora las subcarpetas dentro del prefijo (comportamiento de ls).
        read_log_file (bool): Si es True, usa el archivo de registro para omitir archivos ya leídos
                              y lo actualiza al finalizar.
        **kwargs: Argumentos adicionales que se pasarán a la función
                  correspondiente de pandas (ej. sheet_name, skiprows, encoding, sep).

    Returns:
        pd.DataFrame: Un único DataFrame con los datos de todos los archivos encontrados,
                      o un DataFrame vacío si no se encuentra ninguno o si todos ya fueron procesados.
    """
    all_dataframes: List[pd.DataFrame] = []
    # Nombre del archivo de registro
    log_filename = "file_already_read.txt"
    files_already_read: List[str] = []
    log_blob = None
    log_gcs_path = ""

    try:
        # 1. Conexión a GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # --- 2. Lectura del Archivo de Registro (Log) ---
        if read_log_file:
            # Construye el nombre completo del blob del log (ej: 'carpeta/subcarpeta/file_already_read.txt')
            log_blob_name = os.path.join(prefix, log_filename).replace("\\", "/")
            log_blob = bucket.blob(log_blob_name)

            # **Define la ubicación GCS del archivo de registro**
            log_gcs_path = f"gs://{bucket_name}/{log_blob_name}"
            print(f"Buscando/Creando archivo de registro en: {log_gcs_path}")

            if log_blob.exists():
                log_content = log_blob.download_as_text()
                files_already_read = [
                    f.strip() for f in log_content.split("\n") if f.strip()
                ]
                print(
                    f"Archivo de registro '{log_filename}' encontrado. {len(files_already_read)} archivos previamente procesados."
                )
            else:
                print(
                    f"Archivo de registro '{log_filename}' no encontrado. Se procesarán todos los archivos elegibles."
                )

        # --- 3. Listado y Filtrado de Blobs ---
        blobs = bucket.list_blobs(prefix=prefix, delimiter="/" if delimiter else None)

        candidate_files = [
            blob
            for blob in blobs
            if blob.name.endswith(file_type)
            and (
                file_prefix is None or blob.name.split("/")[-1].startswith(file_prefix)
            )
            and blob.name.split("/")[-1] != log_filename
        ]

        if not candidate_files:
            print("No se encontraron archivos de datos que cumplan los criterios.")
            return pd.DataFrame()

        # --- 4. Filtrado por Archivos Ya Leídos (Log) ---
        files_to_read = []
        files_to_update_log = []

        for blob in candidate_files:
            file_name = blob.name.split("/")[-1]
            if read_log_file and file_name in files_already_read:
                print(f"Skipping: {file_name} (ya listado en el registro)")
            else:
                files_to_read.append(blob)
                files_to_update_log.append(file_name)

        if not files_to_read:
            print(
                f"Se encontraron {len(candidate_files)} archivos elegibles, pero todos ya han sido procesados según el registro."
            )
            return pd.DataFrame()

        print(f"Se procesarán {len(files_to_read)} archivos nuevos o no registrados.")

        # --- 5. Lectura y Concatenación de Datos ---
        for blob in tqdm(files_to_read, desc="Procesando archivos"):
            file_name = blob.name.split("/")[-1]
            try:
                file_bytes = blob.download_as_bytes()

                if file_type == ".xlsx":
                    df = pd.read_excel(io.BytesIO(file_bytes), **kwargs)
                elif file_type == ".csv":
                    df = pd.read_csv(io.BytesIO(file_bytes), **kwargs)
                else:
                    print(f"Tipo de archivo no soportado: {file_type}")
                    continue

                df["file"] = file_name
                all_dataframes.append(df)
            except Exception as e:
                print(f"\nError al leer el archivo {file_name}: {e}")
                if file_name in files_to_update_log:
                    files_to_update_log.remove(file_name)

        # --- 6. Finalización y Actualización del Log ---
        if all_dataframes:
            final_df = pd.concat(all_dataframes, ignore_index=True)
            print(
                "\n✅ ¡Proceso completado! Todos los DataFrames han sido concatenados."
            )

            # **Bloque de creación/escritura del TXT en GCS**
            if read_log_file and files_to_update_log and log_blob:
                try:
                    updated_log_list = files_already_read + files_to_update_log
                    updated_log_content = "\n".join(updated_log_list)

                    # Esta operación CREA el blob si no existe, o lo SOBREESCRIBE si existe.
                    log_blob.upload_from_string(updated_log_content)
                    print(
                        f"Archivo de registro '{log_filename}' actualizado con {len(files_to_update_log)} nuevo(s) archivo(s)."
                    )

                    # **CONFIRMACIÓN DE UBICACIÓN**
                    print(
                        f"💾 El archivo de registro fue guardado/actualizado en: {log_gcs_path}"
                    )
                except Exception as e:
                    print(
                        f"❌ ERROR: Falló la actualización del archivo de registro '{log_filename}'."
                    )
                    print(
                        f"Asegúrate de tener el permiso de escritura (storage.objects.create) en el bucket '{bucket_name}'."
                    )
                    print(f"Detalle del error: {e}")

            return final_df
        else:
            print("Ningún archivo pudo ser procesado exitosamente.")
            return pd.DataFrame()

    except Exception as e:
        print(f"\nOcurrió un error general en la función: {e}")
        return pd.DataFrame()


def validación_archivos_actualizados(balanzaeeva: pd.DataFrame):
    """Realiza la sumatoria YTD del resutado del  periodos y valida su coincidencia vs los periodos. Si no coinciden, existe un error. Únicamente para las cuentas 15 y 16"""
    balanzaeeva = balanzaeeva[balanzaeeva.Cuenta.str[0:2].isin(["15", "16"])].astype(
        {"Saldo_Anterior": "float64", "Saldo_Nuevo": "float64"}
    )  # Filtrmaos cuenta 15 y 16 que son las que se reinician a cero en cada periodo anual y cambiamos a tipo float64 las columans aplicablels
    sumdatos_eeva = balanzaeeva.groupby(
        ["empresa", "Cuenta", pd.Grouper(key="fecha", freq="ME")],
        as_index=False,
        dropna=False,
    ).sum(
        numeric_only=True
    )  # Sumamos para obtener el total por cuenta sin separar por ramo
    sumdatos_eeva["periodoytd"] = sumdatos_eeva.groupby(
        ["empresa", "Cuenta", sumdatos_eeva.fecha.dt.year], dropna=False
    )[
        "Periodo"
    ].cumsum()  # Obtemeos Periodo acumulado YTD
    sumdatos_eeva["dif_abs_saldos"] = (
        sumdatos_eeva["periodoytd"] - sumdatos_eeva["Saldo_Nuevo"]
    ).abs()  # Calculamos la diferencia absoluta entre saldo nuevo calculado por sumatoria de periodo y saldo nuevo de sistema
    sumdatos_eeva["validación"] = (
        sumdatos_eeva["dif_abs_saldos"] < 1
    ) == False  # Identificamos aquellos en los que la diferencia no sea significativa (menor a 1)
    estadisticas_diagnostico = sumdatos_eeva.groupby(["empresa", "fecha"])[
        "validación"
    ].sum()  # Contamos los que no cumlen con la regla de validacion
    detalle_errores = sumdatos_eeva[
        sumdatos_eeva.validación
    ]  # Filtramos los registros en los que no se cumple la validación

    if sumdatos_eeva["validación"].sum() > 0:
        return True
    else:
        print(
            f'Existen {sumdatos_eeva["validación"].sum()} combinaciones de empresa, cuenta, fecha donde el acumulado ytd no coincide con el saldo'
        )
        return False


def extraer_excel_gcs(bucket_name, file_path, **kwargs):
    """
    Descarga un archivo Excel desde un bucket de GCS y lo carga en un DataFrame de pandas.

    Args:
        bucket_name (str): Nombre del bucket.
        file_path (str): Ruta completa del archivo dentro del bucket.
        **kwargs: Argumentos adicionales para pd.read_excel.

    Returns:
        pd.DataFrame: DataFrame con el contenido del archivo Excel.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    file_bytes = blob.download_as_bytes()
    df = pd.read_excel(io.BytesIO(file_bytes), **kwargs)
    return df


def test():
    print("Función de prueba ejecutada correctamente.")

def query_to_dataframe(query: str, project_id: str = "otbi-gcp-project"):
    """
    Ejecuta una consulta SQL y devuelve el resultado como un DataFrame de pandas.
    """
    client = bigquery.Client(project=project_id)
    query_job = client.query(query)
    return query_job.to_dataframe()
