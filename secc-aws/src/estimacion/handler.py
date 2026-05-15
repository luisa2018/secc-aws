import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../bedrock'))
from bedrock_service import proponer_arquitectura
from rule_engine import validar_servicios

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


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        errores = validar_entrada(body)
        if errores:
            return response(400, {"error": "Datos de entrada inválidos", "detalle": errores})

        contexto = body.get("contexto_evaluacion", {})
        arquitectura = body.get("arquitectura", {})

        estilo = contexto.get("estilo_arquitectura", "")
        ubicacion = contexto.get("ubicacion_usuarios", "")
        horizonte = contexto.get("horizonte_tiempo", "mensual")
        region_aws = REGION_MAP.get(ubicacion, "us-east-1")
        inferidos = INFERIDOS_POR_ESCENARIO.get(estilo, {})

        # Paso 1: LLM - proponer arquitectura
        servicios_llm = proponer_arquitectura(contexto, arquitectura, region_aws, horizonte, inferidos)
        print("Servicios LLM:", servicios_llm)

        # Paso 2: Validar servicios
        servicios_validos, decision_log = validar_servicios(servicios_llm, contexto, arquitectura, inferidos)
        print("Servicios validados:", servicios_validos)
        print("Decision log:", decision_log)

        # TODO EST-03: consultar AWS Pricing
        # TODO EST-04: Prompt 2 - justificaciones
        # TODO EST-05: response final

        return response(202, {"mensaje": "Estimación en proceso - flujo incompleto"})

    except Exception as e:
        return response(500, {"error": f"Error interno: {str(e)}"})


def validar_entrada(body):
    errores = []
    contexto = body.get("contexto_evaluacion", {})
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


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }