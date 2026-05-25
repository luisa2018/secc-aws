import json
import os
import asyncio
import re
from strands import Agent
from strands.tools.mcp import MCPClient
import boto3

CODE_INTERPRETER_ID = "aws.codeinterpreter.v1"
REGION = "us-east-1"

def execute_cost_calculation(code: str) -> str:
    """Ejecuta código Python para calcular costos AWS con precisión."""
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    
    session = client.start_code_interpreter_session(
        codeInterpreterIdentifier=CODE_INTERPRETER_ID,
        name="cost-calc"
    )
    session_id = session['sessionId']
    
    response = client.invoke_code_interpreter(
        codeInterpreterIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
        name="executeCode",
        arguments={"code": code, "language": "python"}
    )
    
    result = response['response'].read()
    result_data = json.loads(result)
    
    client.stop_code_interpreter_session(
        codeInterpreterIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id
    )
    
    return json.dumps(result_data)

from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5001/mcp")

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

SYSTEM_PROMPT = """Actua como un arquitecto cloud senior experto en AWS con mas de 10
anos de experiencia. Tu tarea es analizar el escenario recibido,
identificar los servicios AWS necesarios, consultar sus precios oficiales
y calcular los costos con precision.

PROCESO QUE DEBES SEGUIR:
1. Identifica los servicios AWS necesarios para el escenario.
2. Usa la tool get_aws_pricing para consultar los precios oficiales
   de TODOS los servicios identificados en la region correspondiente.
3. Usa la tool execute_cost_calculation para calcular con precision
   el costo_mensual de cada servicio. Pasale un script Python con
   las variables de precio_unitario y uso estimado segun el escenario.
4. Con esos costos reales genera el informe completo en el JSON indicado.

REGLAS PARA IDENTIFICAR SERVICIOS:
- Usa codigos oficiales AWS Pricing API.
- No dupliques servicios.
- Si Expone API publica es verdadero incluye AmazonAPIGateway.
- Si Salida a internet es verdadero Y red_privada es verdadero
  incluye AmazonNatGateway. Si red_privada es falso no incluyas
  AmazonNatGateway porque Lambda accede a internet directamente
  sin VPC.
- En produccion con API publica siempre incluye AWSWAF.
- Segun Tipo de IA:
  * "apis_externas": incluye AWSSecretsManager.
  * "propia": incluye AmazonSageMaker o AmazonBedrock segun corresponda.
  * "ninguna": no incluyas servicios de IA/ML.
- Si un servicio es necesario para la arquitectura pero su precio
  no esta en get_aws_pricing incluyelo de todas formas, calcula
  su costo con tarifas oficiales conocidas e identificalo en
  limitaciones_estimado.

REGLAS PARA EL INFORME:
- El campo plazo_compromiso del contexto indica el modelo de
  pago a usar: sin_compromiso=On-Demand, 1_año=Reserved 1 año,
  3_años=Reserved 3 años. Usa ese modelo para calcular el
  precio de todos los servicios que lo soporten.
- Usa execute_cost_calculation para determinar el modelo optimo
  de pricing de cada servicio segun su patron de uso.
- Usa execute_cost_calculation para calcular el ahorro_estimado_usd
  en well_architected. El resultado nunca puede ser negativo.
- En buenas_practicas el campo etiquetado_ejemplo debe tener
  TODAS las claves y valores en español. Ejemplo: "proyecto",
  "entorno", "propietario", "centro-de-costos". Nunca uses
  claves en ingles.
- Cuando el usuario ingrese un rango de volumen o transferencia
  usa siempre el valor mas alto del rango para calcular costos.
- En modelo_pricing y well_architected se consistente: si recomiendas
  Reserved Instances especifica siempre el plazo (1 año o 3 años).
  No mezcles Reserved Instances con Savings Plans en la misma
  recomendacion. Elige el modelo que mejor se ajuste al patron
  de uso y justifica el plazo recomendado.
- Para AmazonRDS incluye siempre todos los componentes de costo:
  instancia, almacenamiento, backup storage y proxy si aplica.
  No calcules solo el precio por hora de la instancia.
- Para AmazonEBS incluye siempre todos los componentes de costo:
  almacenamiento, IOPS y throughput segun el tipo de volumen.
- Para cada servicio calcula todos sus componentes de costo
  principales: horas de uso, almacenamiento, transferencia de
  datos, requests y unidades de capacidad segun aplique.

IMPORTANTE: Responde UNICAMENTE con el siguiente JSON.
Sin explicaciones, sin markdown, sin texto adicional. Solo el JSON:

{{
  "servicios": [
    {{
      "servicio_aws": "string",
      "configuracion_minima": "string",
      "justificacion": "string",
      "precio_unitario": number,
      "unidad": "string",
      "costo_mensual": number
    }}
  ],
  "costo_estimado": {{
    "costo_mensual": number,
    "costo_horizonte": number,
    "moneda": "USD",
    "periodo": "string"
  }},
  "evaluacion_presupuesto": {{
    "dentro_presupuesto": boolean,
    "porcentaje_del_presupuesto": number,
    "estado": "string",
    "mensaje": "string"
  }},
  "top_3_servicios": [
    {{
      "servicio_aws": "string",
      "configuracion_minima": "string",
      "costo_mensual": number,
      "porcentaje_del_total": number
    }}
  ],
  "nivel_riesgo": {{
    "clasificacion": "Bajo | Medio | Alto",
    "justificacion": "string"
  }},
  "modelo_pricing": [
    {{
      "servicio_aws": "string",
      "modelo_recomendado": "On-Demand | Reserved | Spot | Savings-Plan",
      "justificacion": "string"
    }}
  ],
  "region_recomendada": {{
    "region": "string",
    "justificacion": "string"
  }},
  "well_architected": {{
    "evaluacion": "string con costo actual y proyectado en USD",
    "ahorro_estimado_usd": number,
    "recomendacion": "string"
  }},
  "alternativa_menor_costo": {{
    "aplica": boolean,
    "descripcion": "string",
    "ahorro_estimado": number
  }},
  "analisis_migracion": {{
    "aplica": boolean,
    "costo_actual_estimado_usd": number,
    "ahorro_mensual_estimado_usd": number,
    "periodo_retorno_inversion": "string"
  }},
  "buenas_practicas": {{
    "etiquetado_ejemplo": {{}},
    "budgets": "string",
    "cost_explorer": "string",
    "revision_periodica": "string"
  }},
  "limitaciones_estimado": ["string"],
  "resumen": "string"
}}"""

USER_PROMPT = """Contexto de evaluacion:
- Descripcion: {descripcion}
- Estilo de arquitectura: {estilo_arquitectura}
- Ambiente: {ambiente}
- Ubicacion de usuarios: {ubicacion_usuarios}
- Tipo de IA: {ia_tipo}
- Horizonte de tiempo: {horizonte_tiempo}
- Plazo de compromiso: {plazo_compromiso}
- Presupuesto disponible: {presupuesto} USD

Datos proporcionados por el usuario:
- Patron de despliegue: {patron_despliegue}
- Usuarios concurrentes: {usuarios_concurrentes}
- Tipo de base de datos: {tipo_base_datos}
- Volumen de datos inicial: {volumen_datos_inicial}
- Intensidad de procesamiento: {intensidad_procesamiento}
- Cumplimiento requerido: {cumplimiento}
- Transferencia de datos mensual: {transferencia_mensual}
- SLA objetivo: {sla_objetivo}
- Almacenamiento de archivos: {almacenamiento_archivos}

Parametros inferidos por el sistema:
- Multi-AZ: {multi_az}
- Backups: {backups}
- Auto-scaling: {auto_scaling}
- CDN: {cdn}
- Monitoreo y alertas: {monitoreo}
- Expone API publica: {expone_api_publica}
- Componentes en red privada: {red_privada}
- Salida a internet: {salida_internet}
- Tipo de aplicacion: {tipo_aplicacion}"""


def construir_user_prompt(contexto, arquitectura, horizonte, inferidos):
    return USER_PROMPT.format(
        descripcion=contexto.get("descripcion", "No especificada"),
        estilo_arquitectura=contexto.get("estilo_arquitectura"),
        ambiente=contexto.get("ambiente"),
        ubicacion_usuarios=contexto.get("ubicacion_usuarios"),
        ia_tipo=contexto.get("ia_tipo", "ninguna"),
        horizonte_tiempo=horizonte,
        plazo_compromiso=contexto.get("plazo_compromiso", "sin_compromiso"),
        presupuesto=contexto.get("presupuesto"),
        patron_despliegue=arquitectura.get("patron_despliegue"),
        usuarios_concurrentes=arquitectura.get("usuarios_concurrentes"),
        tipo_base_datos=arquitectura.get("tipo_base_datos"),
        volumen_datos_inicial=arquitectura.get("volumen_datos_inicial"),
        intensidad_procesamiento=arquitectura.get("intensidad_procesamiento"),
        cumplimiento=arquitectura.get("cumplimiento"),
        transferencia_mensual=arquitectura.get("transferencia_mensual"),
        sla_objetivo=arquitectura.get("sla_objetivo"),
        almacenamiento_archivos=arquitectura.get("almacenamiento_archivos"),
        multi_az=inferidos.get("multi_az", False),
        backups=inferidos.get("backups", False),
        auto_scaling=inferidos.get("auto_scaling", False),
        cdn=inferidos.get("cdn", False),
        monitoreo=inferidos.get("monitoreo", False),
        expone_api_publica=inferidos.get("expone_api_publica", False),
        red_privada=inferidos.get("red_privada", False),
        salida_internet=inferidos.get("salida_internet", False),
        tipo_aplicacion=inferidos.get("tipo_aplicacion", "web")
    )


async def _ejecutar_agente(contexto, arquitectura, horizonte, inferidos):
    prompt_usuario = construir_user_prompt(
        contexto, arquitectura, horizonte, inferidos
    )

    mcp_client = MCPClient(
        lambda: streamable_http_client(MCP_URL)
    )

    agent = Agent(
        model=BEDROCK_MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[mcp_client, execute_cost_calculation]
    )

    respuesta = await agent.invoke_async(prompt_usuario)
    texto = str(respuesta).strip()

    match = re.search(r'\{[\s\S]*"servicios"[\s\S]*\}', texto)
    if match:
        return json.loads(match.group())
    else:
        raise ValueError("No se encontro JSON valido en la respuesta del agente")


def generar_informe(contexto, arquitectura, horizonte, inferidos):
    import traceback
    try:
        return asyncio.run(
            _ejecutar_agente(contexto, arquitectura, horizonte, inferidos)
        )
    except Exception as e:
        traceback.print_exc()
        raise