import json
import boto3

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

PROMPT_TEMPLATE = """Actúa como un arquitecto cloud senior experto en AWS con más de 10 años de experiencia. Estás en una kata de arquitectura donde debes analizar los siguientes parámetros de entrada, identificar los servicios AWS necesarios con sus atributos técnicos mínimos para consultar sus precios en AWS Pricing API, proponiendo la solución más adecuada y costo-eficiente sin omitir ningún componente crítico.

Contexto de evaluación:
- Descripción: {descripcion}
- Estilo de arquitectura: {estilo_arquitectura}
- Ambiente: {ambiente}
- Ubicación de usuarios: {ubicacion_usuarios}
- Tipo de IA: {ia_tipo}

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

Parámetros inferidos según el estilo de arquitectura:
- Multi-AZ: {multi_az}
- Backups: {backups}
- Auto-scaling: {auto_scaling}
- CDN: {cdn}
- Monitoreo y alertas: {monitoreo}
- Expone API pública: {expone_api_publica}
- Componentes en red privada: {red_privada}
- Salida a internet: {salida_internet}
- Tipo de aplicación: {tipo_aplicacion}

Instrucciones:
- Devuelve únicamente servicios AWS necesarios para materializar esta arquitectura.
- No dupliques servicios.
- Usa códigos oficiales AWS Pricing API.
- Incluye solo atributos relevantes para pricing.
- Si Tipo de IA es "apis_externas", incluye AmazonAPIGateway.
- Si Tipo de IA es "ninguna", no incluyas servicios de IA/ML.
- Para volúmenes de almacenamiento en bloque usa AmazonEBS, nunca AmazonEC2.
- Para transferencia de datos usa el atributo transferencia_gb del servicio que la genera, nunca AWSDataTransfer como servicio separado.
- Si Tipo de IA es "propia", incluye AmazonSageMaker o AmazonBedrock según corresponda.
- AmazonNatGateway debe ser un servicio separado, nunca un atributo de AmazonVPC.
- En producción con API pública siempre incluye AWSWAF con sus atributos de configuración.
- Si Tipo de IA es "apis_externas" siempre incluye AWSSecretsManager para gestionar las credenciales.
- Para arquitecturas monolíticas que consumen APIs externas NO incluyas AmazonAPIGateway. API Gateway es para exponer tus propias APIs, no para consumir APIs de terceros.
- Si no faltan servicios devuelve: {{"servicios":[]}}

Responde únicamente JSON válido:
{{
  "servicios": [
    {{
      "servicio_aws": "código oficial AWS Pricing API",
      "atributos": {{}}
    }}
  ]
}}"""


def proponer_arquitectura(contexto, arquitectura, region_aws, horizonte, inferidos):

    prompt = PROMPT_TEMPLATE.format(
        descripcion=contexto.get("descripcion", "No especificada"),
        estilo_arquitectura=contexto.get("estilo_arquitectura"),
        horizonte_tiempo=horizonte,
        ambiente=contexto.get("ambiente"),
        presupuesto=contexto.get("presupuesto"),
        ubicacion_usuarios=contexto.get("ubicacion_usuarios"),
        ia_tipo=contexto.get("ia_tipo", "ninguna"),
        region=region_aws,
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

    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

    response_bedrock = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        })
    )

    response_body = json.loads(response_bedrock["body"].read())
    texto = response_body["content"][0]["text"]
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    return json.loads(texto)["servicios"]