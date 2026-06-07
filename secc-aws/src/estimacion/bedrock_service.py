import json
import os
import asyncio
import re
from json_repair import repair_json
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import boto3

CODE_INTERPRETER_ID = "aws.codeinterpreter.v1"
REGION = "us-east-1"

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5001/mcp")

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


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


SYSTEM_PROMPT = """IMPORTANTE: Responde siempre en español correcto, usando tildes, ñ y todos los caracteres especiales del idioma español. Nunca omitas tildes ni caracteres especiales. Ejemplos: años, más, región, evaluación, optimización, tamaño, justificación, configuración, recomendación, métricas, número.

Actúa como un arquitecto cloud senior experto en AWS con más de 10
años de experiencia. Tu tarea es analizar el escenario recibido,
identificar los servicios AWS necesarios, consultar sus precios oficiales
y calcular los costos con precisión.

PROCESO QUE DEBES SEGUIR:
1. Identifica los servicios AWS necesarios para el escenario.
2. Usa la tool get_aws_pricing UNA SOLA VEZ con TODOS los servicios
   identificados en una sola lista para consultar los precios oficiales
   en la región correspondiente.
3. Usa la tool execute_cost_calculation para calcular con precisión
   el costo_mensual de cada servicio. Pásale un script Python con
   las variables de precio_unitario y uso estimado según el escenario.
4. Con esos costos reales genera el informe completo en el JSON indicado.

REGLAS PARA IDENTIFICAR SERVICIOS:
- Usa códigos oficiales AWS Pricing API.
- No dupliques servicios.
- Si Expone API pública es verdadero incluye AmazonAPIGateway.
- Si Salida a internet es verdadero Y red_privada es verdadero
  incluye AmazonNatGateway. Si red_privada es falso no incluyas
  AmazonNatGateway porque Lambda accede a internet directamente
  sin VPC.
- En producción con API pública siempre incluye AWSWAF.
- Según Tipo de IA:
  * "apis_externas": incluye AWSSecretsManager.
  * "propia": incluye AmazonSageMaker o AmazonBedrock según corresponda.
  * "ninguna": no incluyas servicios de IA/ML.
- Si un servicio es necesario para la arquitectura pero su precio
  no está en get_aws_pricing inclúyelo de todas formas, calcula
  su costo con tarifas oficiales conocidas e identifícalo en
  limitaciones_estimado.

IMPORTANTE — LLAMADA AL MCP: Debes invocar get_aws_pricing UNA SOLA VEZ
con TODOS los servicios identificados en una sola lista. NUNCA llames
get_aws_pricing múltiples veces en la misma evaluación.
Ejemplo correcto: get_aws_pricing(servicios=["AmazonEC2", "AmazonRDS", "AmazonS3", "ElasticLoadBalancing", ...])
Ejemplo incorrecto: llamar get_aws_pricing("AmazonEC2"), luego get_aws_pricing("AmazonRDS"), etc.

REGLAS PARA DIMENSIONAMIENTO DE EC2:
- Selecciona el tipo de instancia EC2 según la intensidad de procesamiento
  y los usuarios concurrentes declarados:
  * Ligera + hasta 1K usuarios: t3.medium (2 vCPU, 4 GB RAM)
  * Ligera + 1K-10K usuarios: t3.large (2 vCPU, 8 GB RAM)
  * Media + hasta 1K usuarios: t3.large (2 vCPU, 8 GB RAM)
  * Media + 1K-10K usuarios: m5.large (2 vCPU, 8 GB RAM)
  * Alta + cualquier escala: m5.xlarge o superior según carga
  NUNCA uses m5.xlarge para cargas ligeras con menos de 10K usuarios.

REGLAS PARA REGIÓN:
- Selecciona la región AWS según la ubicación de los usuarios:
  * latinoamerica: sa-east-1 (São Paulo) — única región en América del Sur
  * estados_unidos: us-east-1 (N. Virginia)
  * europa: eu-west-1 (Irlanda) o eu-central-1 (Frankfurt)
  * global: us-east-1 como primaria con recomendación de CloudFront
  NUNCA recomiendes us-east-1 cuando la ubicación sea latinoamerica.

REGLAS PARA EL INFORME:
- El campo plazo_compromiso del contexto indica el modelo de
  pago a usar: sin_compromiso=On-Demand, 1_año=Reserved 1 año,
  3_años=Reserved 3 años. Usa ese modelo para calcular el
  precio de todos los servicios que lo soporten.
- Usa execute_cost_calculation para determinar el modelo óptimo
  de pricing de cada servicio según su patrón de uso.
- Usa execute_cost_calculation para calcular el ahorro_estimado_usd
  en well_architected. El resultado nunca puede ser negativo.
- En buenas_practicas el campo etiquetado_ejemplo debe tener
  TODAS las claves y valores en español con tildes y caracteres
  especiales correctos. Nunca uses claves en inglés. Ejemplos
  correctos: "Producción" no "Produccion", "Latinoamérica" no
  "Latinoamerica", "Gestión" no "Gestion", "Región" no "Region".
- Cuando el usuario ingrese un rango de volumen o transferencia
  usa siempre el valor más alto del rango para calcular costos.
- En modelo_pricing y well_architected sé consistente: si recomiendas
  Reserved Instances especifica siempre el plazo (1 año o 3 años).
  No mezcles Reserved Instances con Savings Plans en la misma
  recomendación.
- Para AmazonRDS incluye siempre todos los componentes de costo.
- Para AmazonEBS incluye siempre todos los componentes de costo.
- Para cada servicio calcula todos sus componentes de costo principales.
- El campo periodo en costo_estimado debe contener ÚNICAMENTE el
  horizonte de tiempo en una sola palabra: "mensual", "trimestral"
  o "anual". Sin texto adicional.
- En buenas_practicas el campo budgets debe explicar cómo configurar
  alertas y también cómo leer el costo acumulado vs el costo previsto
  en la consola de AWS Billing, y qué significa cuando el costo
  previsto es mayor al acumulado.
- En buenas_practicas el campo cost_explorer debe explicar cómo usar
  Cost Explorer y orientar al usuario sobre cuáles de los servicios
  propuestos generan costo por uso versus costo fijo mensual, para
  que sepa qué vigilar en su factura.
- El campo presupuesto debe usarse EXACTAMENTE como lo ingresó el
  usuario, sin redondear ni modificar. Si el usuario ingresó 500,
  usa 500. Si ingresó 5000, usa 5000.
- FORMATO DE NÚMEROS EN EL JSON: usa SIEMPRE punto decimal para
  números (ej: 2129.84). NUNCA uses comas ni puntos como separadores
  de miles dentro del JSON. Incorrecto: 2.129,84 — Correcto: 2129.84.

REGLAS DE LICENCIAMIENTO:
- Asume siempre Linux como sistema operativo y MySQL/PostgreSQL como
  motor de base de datos relacional, ya que no generan costo de licencia.
  Estos son los valores base del estimado total.
- El campo region_recomendada DEBE incluir SIEMPRE los siguientes
  campos adicionales, sin excepción:
  * motor_recomendado: string con el motor de base de datos más
    adecuado para el escenario (ej: "PostgreSQL", "MySQL", "DynamoDB").
    Si no hay base de datos en el escenario usa "N/A".
  * justificacion_motor: string con justificación técnica breve de
    por qué ese motor es el más adecuado para el escenario.
    Si no hay base de datos usa "No aplica para este escenario".
  * referencia_licenciamiento: objeto con costos adicionales mensuales
    estimados si el usuario optara por software propietario en lugar
    del open source asumido. SIEMPRE incluye los tres campos:
    - nota: "Estos costos NO están incluidos en el estimado. Son
      referencias informativas si se opta por software propietario."
    - costo_sqlserver_usd: número con el costo adicional mensual
      estimado de usar SQL Server en RDS en lugar de PostgreSQL/MySQL.
      Si no hay RDS en el escenario usa 0.
    - costo_oracle_usd: número con el costo adicional mensual estimado
      de usar Oracle en RDS. Si no hay RDS usa 0.
    - costo_windows_server_usd: número con el costo adicional mensual
      estimado de usar Windows Server en EC2 en lugar de Linux.
      Si no hay EC2 usa 0.

IMPORTANTE: Responde ÚNICAMENTE con el siguiente JSON.
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

    # Limpiar markdown antes de buscar el JSON
    texto = re.sub(r'```json\s*', '', texto)
    texto = re.sub(r'```\s*', '', texto)
    texto = texto.strip()

    # Reparar y parsear con json_repair directamente sobre el texto completo
    resultado = repair_json(texto, return_objects=True)

    if not isinstance(resultado, dict) or 'servicios' not in resultado:
        raise ValueError("No se encontró JSON válido en la respuesta del agente")

    return resultado


def generar_informe(contexto, arquitectura, horizonte, inferidos):
    import traceback
    try:
        return asyncio.run(
            _ejecutar_agente(contexto, arquitectura, horizonte, inferidos)
        )
    except Exception as e:
        traceback.print_exc()
        raise
