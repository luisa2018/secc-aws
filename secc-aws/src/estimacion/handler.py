import json
import sys
import os
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../bedrock'))
from bedrock_service import generar_informe

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
REGION_MAP = {
    "latinoamerica": "us-east-1",
    "estados_unidos": "us-east-1",
    "europa":         "eu-west-1",
    "global":         "us-east-1"
}

INFERIDOS_POR_ESCENARIO = {
    "monolitica": {
        "multi_az": False, "backups": True, "auto_scaling": False,
        "cdn": False, "monitoreo": True, "expone_api_publica": False,
        "red_privada": False, "salida_internet": False, "tipo_aplicacion": "web"
    },
    "microservicios": {
        "multi_az": True, "backups": True, "auto_scaling": True,
        "cdn": True, "monitoreo": True, "expone_api_publica": True,
        "red_privada": True, "salida_internet": True, "tipo_aplicacion": "api_web"
    },
    "serverless": {
        "multi_az": False, "backups": False, "auto_scaling": True,
        "cdn": True, "monitoreo": True, "expone_api_publica": True,
        "red_privada": False, "salida_internet": True, "tipo_aplicacion": "api"
    },
    "event_driven": {
        "multi_az": True, "backups": True, "auto_scaling": True,
        "cdn": False, "monitoreo": True, "expone_api_publica": False,
        "red_privada": True, "salida_internet": True, "tipo_aplicacion": "backend"
    },
    "hibrida": {
        "multi_az": True, "backups": True, "auto_scaling": True,
        "cdn": True, "monitoreo": True, "expone_api_publica": True,
        "red_privada": True, "salida_internet": True, "tipo_aplicacion": "web_api_backend"
    }
}

MULTIPLICADOR_TIEMPO = {
    "mensual":    1,
    "trimestral": 3,
    "anual":      12
}

MCP_URL = os.environ.get("MCP_URL", "http://localhost:5000/mcp")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        errores = validar_entrada(body)
        if errores:
            return response(400, {"error": "Datos de entrada inválidos", "detalle": errores})

        contexto     = body.get("contexto_evaluacion", {})
        arquitectura = body.get("arquitectura", {})

        estilo    = contexto.get("estilo_arquitectura", "")
        horizonte = contexto.get("horizonte_tiempo", "mensual")
        inferidos = INFERIDOS_POR_ESCENARIO.get(estilo, {})

        # Strands Agent ejecuta ciclo completo de razonamiento
        informe = generar_informe(
            contexto, arquitectura, horizonte, inferidos
        )

        return response(200, {
            "metadata": {
                "escenario":       estilo,
                "fecha_ejecucion": datetime.datetime.utcnow().isoformat()
            },
            **informe
        })

    except Exception as e:
        return response(500, {"error": f"Error interno: {str(e)}"})

# ---------------------------------------------------------------------------
# Validación de entrada
# ---------------------------------------------------------------------------
def validar_entrada(body):
    errores = []
    contexto     = body.get("contexto_evaluacion", {})
    arquitectura = body.get("arquitectura", {})

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

    if not contexto.get("ia_tipo"):
        errores.append("ia_tipo es requerido")

    campos_arquitectura = [
        "patron_despliegue", "usuarios_concurrentes",
        "tipo_base_datos", "volumen_datos_inicial", "intensidad_procesamiento",
        "cumplimiento", "transferencia_mensual", "sla_objetivo",
        "almacenamiento_archivos"
    ]
    for campo in campos_arquitectura:
        if not arquitectura.get(campo):
            errores.append(f"{campo} es requerido")

    return errores


# ---------------------------------------------------------------------------
# Helper response
# ---------------------------------------------------------------------------
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }