import json
import os
import asyncio
import re
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5001/mcp")

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# ─────────────────────────────────────────────
# SYSTEM PROMPT — fijo, se cachea en Bedrock
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Actua como un arquitecto cloud senior experto en AWS con mas de 10
anos de experiencia. Tu tarea es analizar el escenario recibido,
identificar los servicios AWS necesarios para materializar la
arquitectura cloud correspondiente, consultar sus precios oficiales
usando la tool get_aws_pricing, y generar un informe ejecutivo
completo previo al despliegue.

PROCESO QUE DEBES SEGUIR:
1. Identifica los servicios AWS necesarios para el escenario.
2. Usa la tool get_aws_pricing para consultar los precios oficiales
   de TODOS los servicios identificados en la region correspondiente.
3. Para cada servicio calcula el costo_mensual multiplicando el
   precio_unitario real obtenido del MCP por la cantidad estimada
   segun la configuracion_minima del escenario.
4. Con esos costos reales genera el informe completo en el JSON indicado.

REGLAS PARA IDENTIFICAR SERVICIOS:
- Usa codigos oficiales AWS Pricing API.
- No dupliques servicios.
- Si Expone API publica es verdadero incluye AmazonAPIGateway.
- Si Salida a internet es verdadero incluye AmazonNatGateway.
- En produccion con API publica siempre incluye AWSWAF.
- Segun Tipo de IA:
  * "apis_externas": incluye AWSSecretsManager.
  * "propia": incluye AmazonSageMaker o AmazonBedrock segun corresponda.
  * "ninguna": no incluyas servicios de IA/ML.

REGLAS PARA EL INFORME:
- El campo precio_unitario de cada servicio debe ser exactamente
  el valor retornado por get_aws_pricing, no una estimacion.
- El campo costo_mensual debe calcularse con ese precio real
  multiplicado por el uso estimado segun la configuracion_minima.
- El costo total debe calcularse segun el horizonte de tiempo ingresado.
- Compara el costo total con el presupuesto disponible.
- El nivel de riesgo considera el SLA objetivo, el ambiente y la
  relacion entre el costo estimado y el presupuesto.
- La alternativa de menor costo es obligatoria si se supera el
  presupuesto: describe brevemente que cambiaria y el ahorro estimado.
- Evalua unicamente el pilar Well-Architected de Optimizacion de
  Costos. El campo "evaluacion" debe indicar el costo actual y el
  costo proyectado despues de aplicar las recomendaciones en USD.
  El campo "recomendacion" debe incluir el ahorro estimado en USD
  si se implementa, referenciando principios de rightsizing,
  modelo de consumo y managed services.
- Si la descripcion indica una migracion, incluye en
  "analisis_migracion" una estimacion del costo actual
  on-premise o nube anterior, el ahorro mensual estimado
  y el periodo aproximado de retorno de inversion.
  Si no es migracion, "aplica" debe ser false y los
  demas campos en 0.
- Justifica la region recomendada en terminos de latencia vs costo.

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


# ─────────────────────────────────────────────
# USER PROMPT — variable, datos del escenario
# ─────────────────────────────────────────────
USER_PROMPT = """Contexto de evaluacion:
- Descripcion: {descripcion}
- Estilo de arquitectura: {estilo_arquitectura}
- Ambiente: {ambiente}
- Ubicacion de usuarios: {ubicacion_usuarios}
- Tipo de IA: {ia_tipo}
- Horizonte de tiempo: {horizonte_tiempo}
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
        tools=[mcp_client]
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