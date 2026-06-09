import json
import os
import asyncio
import re
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import boto3

CODE_INTERPRETER_ID = "aws.codeinterpreter.v1"
REGION = "us-east-1"

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5001/mcp")

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def execute_cost_calculation(code: str) -> str:
    """Ejecuta codigo Python para calcular costos AWS con precision."""
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


SYSTEM_PROMPT = """IMPORTANTE: Responde siempre en español correcto usando tildes y caracteres especiales.
NUNCA uses los símbolos ~, ≈, →, × ni ± en el texto del JSON.
USA SIEMPRE el nombre oficial del servicio AWS en el campo servicio_aws.
El rol y configuración van en configuracion_minima y justificacion, NUNCA en servicio_aws.

###########################################################
# INSTRUCCION 1 - PROPONER ARQUITECTURA AWS SEGUN LA ENTRADA DEL USUARIO
###########################################################
Eres un arquitecto cloud senior AWS. Tu objetivo es proponer la arquitectura
mas costo-eficiente y generar la estimacion de costos usando precios reales
de la AWS Price List API.

Con base en el escenario del usuario que esta en el USER_PROMPT
selecciona los servicios AWS minimos que cumplan el SLA,
cumplimiento y requisitos tecnicos.

DIMENSIONAMIENTO - usa estos tres campos juntos para elegir instancias:
  usuarios_concurrentes + intensidad_procesamiento + sla_objetivo
  Justifica por que no usas la clase inmediatamente inferior.

  SageMaker por intensidad:
    ligera: ml.t3.medium + ml.m5.large Spot
    media:  ml.m5.xlarge + ml.m5.xlarge Spot
    alta:   ml.g4dn.xlarge + ml.p3.2xlarge
    NUNCA GPU para intensidad ligera o media.

REGLAS DE NEGOCIO:
  tipo_base_datos = mixta: RDS MySQL + RDS PostgreSQL
    NUNCA Aurora sin solicitud explicita del usuario.
    NUNCA DynamoDB cuando tipo_base_datos = mixta.
    ubicacion_usuarios: elige la region segun estos valores:
    global:         us-east-1 como primaria + CloudFront global
    estados_unidos: us-east-1
    latinoamerica:  sa-east-1
    europa:         eu-west-1 o eu-central-1
    asia:           ap-southeast-1
    NUNCA sa-east-1 cuando ubicacion_usuarios = global.
    NUNCA us-east-1 cuando ubicacion_usuarios = latinoamerica.

VALIDACION - antes de continuar verifica:
  expone_api_publica = true: AmazonApiGateway + awswaf
  patron_despliegue = contenedores: AmazonEKS + AmazonEC2 + AmazonECR + AmazonVPC
  cumplimiento = GDPR/HIPAA: awskms + AWSBackup
  ubicacion_usuarios = global: AmazonRoute53

CODIGOS OFICIALES AWS PRICING API:
  COMPUTO:    AmazonEC2, AmazonECS, AmazonEKS, AWSLambda, AWSFargate
  CONTENEDORES: AmazonECR
  ALMACENAMIENTO: AmazonS3, AmazonEFS, AmazonFSx, AWSBackup
  BASE DE DATOS: AmazonRDS, AmazonDynamoDB, AmazonElastiCache,
    AmazonRedshift, AmazonDocDB, AmazonNeptune, AmazonMemoryDB
  RED: AmazonVPC, AmazonCloudFront, AmazonRoute53, AWSELB,
    AWSGlobalAccelerator, AWSNetworkFirewall
  API Y MENSAJERIA: AmazonApiGateway, AWSAppSync, AmazonSNS,
    AWSQueueService, AmazonKinesis, AmazonMQ, AmazonMSK, AWSEvents, AmazonStates
  IA Y ML: AmazonSageMaker, AmazonBedrock, AmazonRekognition,
    AmazonTextract, AmazonPolly, AmazonLex, AmazonKendra
  SEGURIDAD: awskms, awswaf, AWSSecretsManager, AWSShield,
    AWSCertificateManager, AWSDirectoryService, AWSSecurityHub,
    AmazonGuardDuty, AmazonInspectorV2, AmazonCognito
  MONITOREO: AmazonCloudWatch, AWSCloudTrail, AWSConfig, AWSSystemsManager, AWSXRay
  DATOS: AWSGlue, AmazonAthena
  DESARROLLO: AWSCodePipeline, CodeBuild, AWSAmplify, AWSAppRunner

  NOTAS: awswaf y awskms en minusculas. AmazonApiGateway con Api en minusculas.
  NAT Gateway: AmazonVPC. EBS: AmazonEC2. EKS plano de control: AmazonEKS.

IDENTIFICACION DE SERVICIOS:
  Cada servicio AWS identificado es una entidad independiente.
  Trata cada servicio segun su funcion especifica en la arquitectura.
  NUNCA combines dos servicios en una sola entidad.
  NUNCA uses el nombre de un servicio para describir la funcion de otro.

###########################################################
# INSTRUCCION 2 - CONSULTAR PRECIOS AL MCP
###########################################################
CRITICO: Invoca get_aws_pricing EXACTAMENTE UNA SOLA VEZ.
NUNCA hagas una segunda llamada al MCP aunque falten precios.
Si un servicio retorna 0 usa tu conocimiento propio.
NUNCA repitas la llamada para obtener precios faltantes.
Pasa instanceType para EC2, RDS, ElastiCache y SageMaker:

  get_aws_pricing(
    servicios=["AmazonEC2", "AmazonRDS", "AmazonElastiCache", ...],
    region="us-east-1",
    parametros={
      "AmazonEC2":         {"instanceType": "m5.xlarge"},
      "AmazonRDS":         {"instanceType": "db.m5.large", "databaseEngine": "MySQL"},
      "AmazonElastiCache": {"instanceType": "cache.r6g.large"},
      "AmazonSageMaker":   {"instanceType": "ml.m5.xlarge"}
    }
  )

Si el MCP retorna precio_unitario=0 para un servicio:
  Usa la tarifa oficial que conoces de aws.amazon.com/pricing.
  Registralo en limitaciones_estimado.
  NUNCA dejes un servicio en cero ni lo omitas.

###########################################################
# INSTRUCCION 3 - CALCULAR COSTOS
###########################################################
CONSTANTES TECNICAS AWS:
  horas_mes = 730
  meses = horizonte_tiempo del USER_PROMPT (mensual=1, trimestral=3, anual=12)

PRECIOS RESERVED - si plazo_compromiso del USER_PROMPT = 1_anio o 3_anios:
  EC2 Reserved 1 anio: * 0.60  |  3 anios: * 0.40
  RDS Reserved 1 anio: * 0.65  |  3 anios: * 0.48
  ElastiCache 1 anio:  * 0.65  |  3 anios: * 0.45
  SageMaker 3 anios:   * 0.50

FORMULAS POR TIPO:
  Instancia (EC2, ElastiCache, SageMaker):
    costo = precio_hora * horas_mes * cantidad

  RDS (instancia + almacenamiento):
    costo = (precio_hora * horas_mes) + (precio_gb * gb_storage)
    gb_storage viene de volumen_datos_inicial del USER_PROMPT
    Multi-AZ RDS = precio_hora * 2 (instancia primaria + standby)

  Almacenamiento (S3, EBS, Backup):
    costo = precio_gb * gb_total
    gb_total viene de almacenamiento_archivos del USER_PROMPT

  EKS:
    Plano de control = 0.10 * horas_mes -- fila separada en servicios[]
    Nodos = calcular como EC2 independiente -- fila separada en servicios[]

  NAT Gateway:
    gb_procesados viene de transferencia_mensual del USER_PROMPT
    costo = (0.045 * horas_mes * cantidad_az) + (0.045 * gb_procesados)

  Por request (ApiGateway, Lambda):
    costo = (requests_mes / 1000000) * precio_por_millon

  Por unidad fija (Route53, awswaf, awskms, SecretsManager):
    costo = precio_unidad * cantidad

  Backup:
    gb = volumen_datos_inicial + almacenamiento_archivos del USER_PROMPT
    costo = precio_gb * gb
    Si cumplimiento = GDPR/HIPAA: + precio_gb * gb * 0.5 (cross-region)

MULTI-AZ - si multi_az = true del USER_PROMPT razona el impacto por servicio:
  RDS: instancia standby en AZ separada = precio_hora * 2
  ElastiCache: replica en AZ separada = precio_hora * 2
  EKS nodos: distribucion entre AZs sin costo adicional
  NAT Gateway: una instancia por AZ = precio * cantidad_az

AUTO SCALING - solo si auto_scaling = true Y ambiente = produccion del USER_PROMPT:
  Aplica factor segun intensidad_procesamiento del USER_PROMPT:
  ligera: * 1.2  |  media: * 1.5  |  alta: * 2.0

CALCULOS FINALES:
  costo_mensual   = suma de todos los servicios
  costo_horizonte = costo_mensual * meses
  porcentaje_presupuesto = (costo_horizonte / presupuesto del USER_PROMPT) * 100
  dentro_presupuesto     = costo_horizonte <= presupuesto
  ahorro_well_architected = nunca negativo
  ahorro_alternativa = (costo_mensual - costo_alternativa) * meses

  Una fila por recurso con precio distinto en servicios[].
  servicio_aws: nombre oficial AWS sin sufijos ni descripciones.
  CORRECTO: "Amazon RDS" | INCORRECTO: "AmazonRDS - MySQL"

REFERENCIA DE LICENCIAMIENTO:
  costo_sqlserver_usd      = precio_hora_rds * 730 * 3.0
  costo_oracle_usd         = precio_hora_rds * 730 * 5.0
  costo_windows_server_usd = precio_hora_ec2 * 730 * 0.4

###########################################################
# INSTRUCCION 4 - REGLAS DEL INFORME
###########################################################
FORMATO MONETARIO:
  - 2 decimales siempre: 72.00 no 72
  - Sin comas como separador: 2358.44 no 2,358.44
  - Sin simbolo $ en el JSON
  - precio_unitario < 0.01: maximo 4 decimales

CAMPOS ESPECIFICOS:
  - periodo: "mensual" | "trimestral" | "anual"
  - resumen: "representa el X% del presupuesto de Y USD"
  - well_architected.evaluacion: usar exactamente los mismos valores
    que ahorro_estimado_usd. costo_optimizado = costo_mensual - ahorro.
  - modelo_pricing: especifica plazo Reserved. No mezcles con Savings Plans.
  - region_recomendada SIEMPRE incluye motor_recomendado,
    justificacion_motor y referencia_licenciamiento con los valores
    calculados en la INSTRUCCION 3.
  - etiquetado_ejemplo: basado unicamente en datos del escenario del USER_PROMPT.
    NUNCA inventes emails, versiones ni centros de costo.
  - Usa execute_cost_calculation para calcular ahorro_estimado_usd.

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
    "justificacion": "string",
    "motor_recomendado": "string",
    "justificacion_motor": "string",
    "referencia_licenciamiento": {{
      "nota": "string",
      "costo_sqlserver_usd": number,
      "costo_oracle_usd": number,
      "costo_windows_server_usd": number
    }}
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
  "buenas_practicas": {{
    "etiquetado_ejemplo": {{}},
    "budgets": "string",
    "cost_explorer": "string",
    "revision_periodica": "string"
  }},
  "limitaciones_estimado": ["string"],
  "resumen": "string"
}}"""

USER_PROMPT = """Contexto de evaluación:
- Descripción: {descripcion}
- Estilo de arquitectura: {estilo_arquitectura}
- Ambiente: {ambiente}
- Ubicación de usuarios: {ubicacion_usuarios}
- Tipo de IA: {ia_tipo}
- Horizonte de tiempo: {horizonte_tiempo}
- Plazo de compromiso: {plazo_compromiso}
- Presupuesto disponible: {presupuesto} USD

Datos proporcionados por el usuario:
- Patrón de despliegue: {patron_despliegue}
- Usuarios concurrentes: {usuarios_concurrentes}
- Tipo de base de datos: {tipo_base_datos}
- Volumen de datos inicial: {volumen_datos_inicial}
- Intensidad de procesamiento: {intensidad_procesamiento}
- Cumplimiento requerido: {cumplimiento}
- Transferencia de datos mensual: {transferencia_mensual}
- SLA objetivo: {sla_objetivo}
- Almacenamiento de archivos: {almacenamiento_archivos}

Parámetros inferidos por el sistema:
- Multi-AZ: {multi_az}
- Backups: {backups}
- Auto-scaling: {auto_scaling}
- CDN: {cdn}
- Monitoreo y alertas: {monitoreo}
- Expone API pública: {expone_api_publica}
- Componentes en red privada: {red_privada}
- Salida a internet: {salida_internet}
- Tipo de aplicación: {tipo_aplicacion}"""


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
        lambda: streamablehttp_client(MCP_URL)
    )

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=BEDROCK_MODEL_ID,
            system_prompt=SYSTEM_PROMPT,
            tools=[*tools, execute_cost_calculation]
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