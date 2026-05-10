import json
from datetime import datetime

# Campos inferidos según estilo de arquitectura
INFERIDOS_POR_ESCENARIO = {
    "monolitica":    {"multi_az": False, "backups": True,  "auto_scaling": False, "cdn": False, "monitoreo": True},
    "microservicios":{"multi_az": True,  "backups": True,  "auto_scaling": True,  "cdn": True,  "monitoreo": True},
    "serverless":    {"multi_az": False, "backups": False, "auto_scaling": False, "cdn": True,  "monitoreo": True},
    "event_driven":  {"multi_az": True,  "backups": True,  "auto_scaling": True,  "cdn": False, "monitoreo": True},
    "hibrida":       {"multi_az": True,  "backups": True,  "auto_scaling": True,  "cdn": True,  "monitoreo": True}
}

# Traducción de ubicación a región AWS
REGION_MAP = {
    "latinoamerica":   "sa-east-1",
    "estados_unidos":  "us-east-1",
    "europa":          "eu-west-1",
    "global":          "us-east-1"
}

# Multiplicador según horizonte de tiempo
MULTIPLICADOR_TIEMPO = {
    "mensual":    1,
    "trimestral": 3,
    "anual":      12
}


def lambda_handler(event, context):
    """
    Servicio de Estimación - Orquestador principal
    Recibe POST /estimate y devuelve estimación de costos
    """
    try:
        # Parsear body
        body = json.loads(event.get("body", "{}"))

        # Validar entrada
        errores = validar_entrada(body)
        if errores:
            return response(400, {"error": "Datos de entrada inválidos", "detalle": errores})

        # Extraer datos del usuario
        contexto = body.get("contexto_evaluacion", {})
        arquitectura = body.get("arquitectura", {})

        # Calcular campos del sistema
        estilo = contexto.get("estilo_arquitectura", "")
        ubicacion = contexto.get("ubicacion_usuarios", "")
        horizonte = contexto.get("horizonte_tiempo", "mensual")

        region_aws = REGION_MAP.get(ubicacion, "us-east-1")
        inferidos = INFERIDOS_POR_ESCENARIO.get(estilo, {})

        # TODO EST-02: reemplazar mock por llamada real a Bedrock
        resultado = mock_response(contexto, region_aws, inferidos, horizonte)

        return response(200, resultado)

    except Exception as e:
        return response(500, {"error": f"Error interno: {str(e)}"})


def validar_entrada(body):
    """Valida que la entrada tenga los campos requeridos"""
    errores = []

    contexto = body.get("contexto_evaluacion", {})
    arquitectura = body.get("arquitectura", {})

    # Validar contexto_evaluacion
    if not contexto.get("estilo_arquitectura"):
        errores.append("estilo_arquitectura es requerido")
    elif contexto.get("estilo_arquitectura") not in INFERIDOS_POR_ESCENARIO:
        errores.append(f"estilo_arquitectura debe ser: {list(INFERIDOS_POR_ESCENARIO.keys())}")

    if not contexto.get("horizonte_tiempo"):
        errores.append("horizonte_tiempo es requerido")
    elif contexto.get("horizonte_tiempo") not in MULTIPLICADOR_TIEMPO:
        errores.append("horizonte_tiempo debe ser: mensual | trimestral | anual")

    if not contexto.get("presupuesto"):
        errores.append("presupuesto es requerido")

    if not contexto.get("ambiente"):
        errores.append("ambiente es requerido")

    if not contexto.get("ubicacion_usuarios"):
        errores.append("ubicacion_usuarios es requerido")

    # Validar arquitectura
    campos_arquitectura = [
        "patron_despliegue", "numero_servicios", "usuarios_concurrentes",
        "tipo_base_datos", "volumen_datos_inicial", "intensidad_procesamiento",
        "cumplimiento", "transferencia_mensual", "sla_objetivo",
        "ia_ml", "almacenamiento_archivos"
    ]
    for campo in campos_arquitectura:
        if not arquitectura.get(campo):
            errores.append(f"{campo} es requerido")

    return errores


def mock_response(contexto, region_aws, inferidos, horizonte):
    """
    Respuesta mock con estructura correcta del contrato de salida
    TODO EST-02: reemplazar por respuesta real de Bedrock
    """
    multiplicador = MULTIPLICADOR_TIEMPO.get(horizonte, 1)

    servicios_mock = [
        {
            "nombre": "Servidor de aplicación",
            "servicio_aws": "AmazonEC2",
            "justificacion": "Servicio de cómputo para alojar la aplicación",
            "costo_mensual": 50.00
        },
        {
            "nombre": "Base de datos",
            "servicio_aws": "AmazonRDS",
            "justificacion": "Base de datos relacional administrada",
            "costo_mensual": 80.00
        },
        {
            "nombre": "Almacenamiento",
            "servicio_aws": "AmazonS3",
            "justificacion": "Almacenamiento de archivos estáticos",
            "costo_mensual": 20.00
        }
    ]

    total_mensual = sum(s["costo_mensual"] for s in servicios_mock)
    valor_total = total_mensual * multiplicador
    presupuesto = contexto.get("presupuesto", 0)
    porcentaje_uso = round((valor_total / presupuesto * 100), 2) if presupuesto > 0 else 0

    return {
        "metadata": {
            "estilo_arquitectura": contexto.get("estilo_arquitectura"),
            "ambiente": contexto.get("ambiente"),
            "fecha_ejecucion": datetime.utcnow().isoformat(),
            "region_aws": region_aws,
            "horizonte_tiempo": horizonte
        },
        "servicios": servicios_mock,
        "costo_estimado": {
            "valor_total": round(valor_total, 2),
            "moneda": "USD",
            "periodo": horizonte
        },
        "evaluacion_presupuesto": {
            "dentro_presupuesto": valor_total <= presupuesto,
            "porcentaje_uso": porcentaje_uso
        },
        "recomendaciones": [
            "MOCK: Esta es una respuesta de prueba",
            "MOCK: Las recomendaciones reales las generará Bedrock"
        ],
        "resumen": "MOCK: Resumen generado por Bedrock en implementación real"
    }


def response(status_code, body):
    """Formato de respuesta HTTP"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }