import json
import logging
import boto3
from botocore.exceptions import ClientError
from awslabs.mcp_lambda_handler import MCPLambdaHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

mcp = MCPLambdaHandler(name="SECC-AWS MCP Server", version="1.0.0")

pricing_client = boto3.client('pricing', region_name='us-east-1')

REGION_NAMES = {
    "us-east-1":      "US East (N. Virginia)",
    "us-east-2":      "US East (Ohio)",
    "us-west-1":      "US West (N. California)",
    "us-west-2":      "US West (Oregon)",
    "eu-west-1":      "Europe (Ireland)",
    "eu-central-1":   "Europe (Frankfurt)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "sa-east-1":      "South America (Sao Paulo)"
}

# Campos dinámicos válidos por servicio — SOLO estos son aceptados desde Bedrock
CAMPOS_DINAMICOS_VALIDOS = {
    "AmazonEC2":         ["instanceType"],
    "AmazonRDS":         ["instanceType", "databaseEngine"],
    "AmazonElastiCache": ["instanceType"],
    "AmazonSageMaker":   ["instanceType"],
    "AmazonMemoryDB":    ["instanceType"],
    "AmazonDocDB":       ["instanceType"],
    "AmazonRedshift":    ["instanceType"],
    "AmazonMQ":          ["instanceType"],
    "AmazonMSK":         ["instanceType"],
}

# Servicios sin precio en la AWS Pricing API pública
# El agente usa su conocimiento propio para estos
SIN_PRECIO_EN_API = {
    "AmazonEKS",      # Solo AutoMode en la API, no cluster estándar
    "AWSBackup",      # Solo transferencia cross-region, no backup estándar
    "AmazonVPC",      # NAT Gateway no está en la API
    "AmazonRoute53",  # Hosted zones no están en la API
    "AmazonCloudWatch", # Métricas estándar no están en la API
}

# Filtros base verificados contra AWS Pricing API real
FILTROS_BASE = {
    # CÓMPUTO
    "AmazonEC2": [
        {"field": "operatingSystem", "value": "Linux"},
        {"field": "tenancy",         "value": "Shared"},
        {"field": "capacitystatus",  "value": "Used"},
        {"field": "preInstalledSw",  "value": "NA"},
    ],
    "AmazonECS": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSLambda": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSFargate": [
        {"field": "locationType", "value": "AWS Region"},
    ],

    # CONTENEDORES
    "AmazonECR": [
        {"field": "usagetype", "value": "TimedStorage-ByteHrs"},
    ],

    # ALMACENAMIENTO
    "AmazonS3": [
        {"field": "storageClass", "value": "General Purpose"},
        {"field": "volumeType",   "value": "Standard"},
    ],
    "AmazonEFS": [
        {"field": "storageClass", "value": "General Purpose"},
    ],
    "AmazonFSx": [
        {"field": "fileSystemType",   "value": "Windows"},
        {"field": "deploymentOption", "value": "Single-AZ"},
        {"field": "storageType",      "value": "SSD"},
    ],

    # BASE DE DATOS
    "AmazonRDS": [
        {"field": "deploymentOption", "value": "Single-AZ"},
    ],
    "AmazonDynamoDB": [
        {"field": "group", "value": "DDB-WriteUnits"},
    ],
    # ElastiCache — filtro por usagetype para evitar ExtendedSupport
    "AmazonElastiCache": [
        {"field": "cacheEngine", "value": "Redis"},
        {"field": "usagetype",   "value": "NodeUsage:cache.r6g.large"},
    ],
    "AmazonRedshift": [
        {"field": "usageFamily", "value": "RA3"},
    ],
    "AmazonDocDB": [
        {"field": "databaseEngine", "value": "Amazon DocumentDB"},
    ],
    "AmazonNeptune": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AmazonMemoryDB": [
        {"field": "engine", "value": "Redis"},
    ],

    # RED Y ENTREGA
    # AmazonVPC — NAT Gateway no está en la API, el agente usa conocimiento propio
    # AmazonCloudFront — sin filtro de location, solo transferType
    "AmazonCloudFront": [
        {"field": "transferType", "value": "CloudFront to Internet"},
    ],
    # AmazonRoute53 — hosted zones no están en la API, el agente usa conocimiento propio
    "AWSELB": [
        {"field": "group", "value": "ELB:Balancing"},
    ],
    "AWSGlobalAccelerator": [
        {"field": "trafficDirection", "value": "In"},
    ],
    "AWSNetworkFirewall": [
        {"field": "subcategory", "value": "Endpoint"},
    ],

    # API Y MENSAJERÍA
    # AmazonApiGateway — usagetype correcto para REST API calls
    "AmazonApiGateway": [
        {"field": "usagetype", "value": "USE1-ApiGatewayRequest"},
    ],
    "AmazonAPIGateway": [  # alias mayúsculas
        {"field": "usagetype", "value": "USE1-ApiGatewayRequest"},
    ],
    "AWSAppSync": [
        {"field": "graphqloperation", "value": "Invocation"},
    ],
    "AmazonSNS": [
        {"field": "group", "value": "SNS-Requests"},
    ],
    "AWSQueueService": [
        {"field": "group", "value": "SQS-APIRequest-Tier1"},
    ],
    "AmazonKinesis": [
        {"field": "group", "value": "AmazonKinesis-ShardHour"},
    ],
    "AmazonMQ": [
        {"field": "brokerEngine",     "value": "ActiveMQ"},
        {"field": "deploymentOption", "value": "Single-AZ"},
    ],
    "AmazonMSK": [
        {"field": "group", "value": "Broker"},
    ],
    "AWSEvents": [
        {"field": "eventType", "value": "Custom Event"},
    ],
    "AmazonStates": [
        {"field": "group", "value": "SFN-StateTransitions"},
    ],

    # IA Y ML
    # AmazonSageMaker — instanceType debe incluir sufijo -Hosting
    "AmazonSageMaker": [
        {"field": "component", "value": "Hosting"},
    ],
    "AmazonBedrock": [
        {"field": "inferenceType", "value": "Input tokens"},
    ],
    "AmazonRekognition": [
        {"field": "group", "value": "Rekognition Image API Requests"},
    ],
    "AmazonTextract": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AmazonPolly": [
        {"field": "engine", "value": "Standard"},
    ],
    "AmazonLex": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AmazonKendra": [
        {"field": "group", "value": "Kendra-Enterprise-Additional-Capacity"},
    ],

    # SEGURIDAD
    "awskms": [
        {"field": "group", "value": "awskms-APIRequest-All"},
    ],
    "AWSKMS": [  # alias
        {"field": "group", "value": "awskms-APIRequest-All"},
    ],
    # awswaf — group correcto para WebACL
    "awswaf": [
        {"field": "group", "value": "Web ACL (Shield Protected)"},
    ],
    "AWSWAF": [  # alias
        {"field": "group", "value": "Web ACL (Shield Protected)"},
    ],
    "AWSSecretsManager": [
        {"field": "group", "value": "AWSSecretsManager-Secret"},
    ],
    "AWSShield": [
        {"field": "resourceType", "value": "LoadBalancing"},
    ],
    "AWSCertificateManager": [
        {"field": "type", "value": "Private"},
    ],
    "AWSDirectoryService": [
        {"field": "directorySize", "value": "Standard"},
        {"field": "directoryType", "value": "Shared Microsoft AD"},
    ],
    "AWSSecurityHub": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AmazonGuardDuty": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AmazonInspectorV2": [
        {"field": "scanType", "value": "Automated re-scan"},
    ],
    "AmazonCognito": [
        {"field": "locationType", "value": "AWS Region"},
    ],

    # MONITOREO
    # AmazonCloudWatch — métricas estándar no están en la API
    "AWSCloudTrail": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSConfig": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSSystemsManager": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSXRay": [
        {"field": "group", "value": "Traces Scanned"},
    ],

    # DATOS
    "AWSGlue": [
        {"field": "group", "value": "Data catalog requests"},
    ],
    "AmazonAthena": [
        {"field": "locationType", "value": "AWS Region"},
    ],

    # DESARROLLO
    "AWSCodePipeline": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "CodeBuild": [
        {"field": "operatingSystem", "value": "Linux"},
    ],
    "AWSAmplify": [
        {"field": "locationType", "value": "AWS Region"},
    ],
    "AWSAppRunner": [
        {"field": "type", "value": "vCPU-hours"},
    ],
}

# Servicios sin filtro de location porque son globales
SIN_FILTRO_LOCATION = {
    "AmazonCloudFront",
    "AWSGlobalAccelerator",
    "AWSShield",
    "AmazonDynamoDB",
}


def filtrar_parametros_validos(service_code, parametros_raw):
    """Solo acepta campos dinámicos válidos. Ignora cualquier campo inventado por Bedrock."""
    campos_validos = CAMPOS_DINAMICOS_VALIDOS.get(service_code, [])
    return {k: v for k, v in parametros_raw.items() if k in campos_validos}


def ajustar_instancetype_sagemaker(service_code, parametros_limpios):
    """
    SageMaker requiere instanceType con sufijo -Hosting.
    Ej: ml.m5.xlarge → ml.m5.xlarge-Hosting
    """
    if service_code == "AmazonSageMaker" and "instanceType" in parametros_limpios:
        instance = parametros_limpios["instanceType"]
        if not instance.endswith("-Hosting"):
            parametros_limpios["instanceType"] = f"{instance}-Hosting"
    return parametros_limpios


def ajustar_usagetype_elasticache(service_code, parametros_limpios, filtros_base):
    """
    ElastiCache requiere usagetype específico para evitar ExtendedSupport.
    Reemplaza el usagetype del filtro base con el instanceType correcto.
    """
    if service_code == "AmazonElastiCache" and "instanceType" in parametros_limpios:
        instance = parametros_limpios.pop("instanceType")
        # Actualizar el filtro base de usagetype con la instancia correcta
        for f in filtros_base:
            if f["Field"] == "usagetype":
                f["Value"] = f"NodeUsage:{instance}"
    return filtros_base, parametros_limpios


def consultar_precio_servicio(service_code, location_name, parametros_dinamicos=None):
    # Servicios sin precio en la API — retornar 0 para que el agente use conocimiento propio
    if service_code in SIN_PRECIO_EN_API:
        logger.info(f"[MCP] {service_code} | sin precio en API — el agente usa conocimiento propio")
        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "N/A",
            "descripcion":     "Precio no disponible en AWS Price List API. Usar tarifa oficial conocida."
        }

    try:
        pricing_filters = []

        if service_code not in SIN_FILTRO_LOCATION:
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": "location",
                "Value": location_name
            })

        for f in FILTROS_BASE.get(service_code, []):
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": f["field"],
                "Value": f["value"]
            })

        if parametros_dinamicos:
            parametros_limpios = filtrar_parametros_validos(service_code, parametros_dinamicos)
            parametros_limpios = ajustar_instancetype_sagemaker(service_code, parametros_limpios)

            # Ajuste especial ElastiCache
            if service_code == "AmazonElastiCache":
                pricing_filters, parametros_limpios = ajustar_usagetype_elasticache(
                    service_code, parametros_limpios, pricing_filters
                )

            for field, value in parametros_limpios.items():
                pricing_filters.append({
                    "Type": "TERM_MATCH",
                    "Field": field,
                    "Value": str(value)
                })

        logger.info(f"[MCP] {service_code} | filtros={json.dumps(pricing_filters)}")

        kwargs = {"ServiceCode": service_code, "MaxResults": 5}
        if pricing_filters:
            kwargs["Filters"] = pricing_filters

        response = pricing_client.get_products(**kwargs)
        price_list = response.get("PriceList", [])

        logger.info(f"[MCP] {service_code} | resultados={len(price_list)}")

        if not price_list:
            logger.warning(f"[MCP] {service_code} | SIN RESULTADOS")
            return {
                "servicio":        service_code,
                "precio_unitario": 0.0,
                "unidad":          "N/A",
                "descripcion":     "Sin precio disponible para los filtros indicados"
            }

        for raw in price_list:
            item = json.loads(raw)
            terms = item.get("terms", {}).get("OnDemand", {})
            for term in terms.values():
                for dimension in term.get("priceDimensions", {}).values():
                    precio_str = dimension.get("pricePerUnit", {}).get("USD", "0")
                    if float(precio_str) > 0:
                        logger.info(f"[MCP] {service_code} | precio={precio_str} | unidad={dimension.get('unit')} | desc={dimension.get('description','')[:80]}")
                        return {
                            "servicio":        service_code,
                            "precio_unitario": float(precio_str),
                            "unidad":          dimension.get("unit", ""),
                            "descripcion":     dimension.get("description", "")
                        }

        logger.warning(f"[MCP] {service_code} | solo precios en 0 o free tier")
        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "N/A",
            "descripcion":     "Solo precios free tier o sin coincidencia"
        }

    except ClientError as e:
        logger.error(f"[MCP] {service_code} | AWS Error: {e.response['Error']['Message']}")
        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "ERROR",
            "descripcion":     f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"[MCP] {service_code} | Error: {str(e)}")
        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "ERROR",
            "descripcion":     f"Error: {str(e)}"
        }


@mcp.tool()
def get_aws_pricing(
    servicios: list,
    region: str = "us-east-1",
    parametros: dict = {}
) -> dict:
    """
    Consulta el precio unitario oficial de servicios AWS desde la AWS Price List API.

    Args:
        servicios: Lista de service codes AWS oficiales.
            Usa EXACTAMENTE estos códigos:
            CÓMPUTO: AmazonEC2, AmazonECS, AmazonEKS, AWSLambda, AWSFargate
            CONTENEDORES: AmazonECR
            ALMACENAMIENTO: AmazonS3, AmazonEFS, AmazonFSx, AWSBackup
            BASE DE DATOS: AmazonRDS, AmazonDynamoDB, AmazonElastiCache,
              AmazonRedshift, AmazonDocDB, AmazonNeptune, AmazonMemoryDB
            RED: AmazonVPC, AmazonCloudFront, AmazonRoute53, AWSELB,
              AWSGlobalAccelerator, AWSNetworkFirewall
            API Y MENSAJERÍA: AmazonApiGateway, AWSAppSync, AmazonSNS,
              AWSQueueService, AmazonKinesis, AmazonMQ, AmazonMSK,
              AWSEvents, AmazonStates
            IA Y ML: AmazonSageMaker, AmazonBedrock, AmazonRekognition,
              AmazonTextract, AmazonPolly, AmazonLex, AmazonKendra
            SEGURIDAD: awskms, awswaf, AWSSecretsManager, AWSShield,
              AWSCertificateManager, AWSDirectoryService, AWSSecurityHub,
              AmazonGuardDuty, AmazonInspectorV2, AmazonCognito
            MONITOREO: AmazonCloudWatch, AWSCloudTrail, AWSConfig,
              AWSSystemsManager, AWSXRay
            DATOS: AWSGlue, AmazonAthena
            DESARROLLO: AWSCodePipeline, CodeBuild, AWSAmplify, AWSAppRunner
            NOTA: awswaf y awskms van en minúsculas obligatoriamente.

        region: Código de región AWS.
            Valores válidos: "us-east-1", "us-west-2", "eu-west-1",
            "eu-central-1", "ap-southeast-1", "sa-east-1"

        parametros: Filtros adicionales SOLO para servicios con instancias.
            Campos válidos por servicio:
            - AmazonEC2: instanceType (ej: "m5.large", "m5.xlarge")
            - AmazonRDS: instanceType (ej: "db.m5.large"), databaseEngine ("MySQL" o "PostgreSQL")
            - AmazonElastiCache: instanceType (ej: "cache.r6g.large")
            - AmazonSageMaker: instanceType (ej: "ml.m5.xlarge")
            Para todos los demás servicios NO pases parametros adicionales.

        NOTA: Los siguientes servicios no tienen precio en la AWS Price List API
        y retornarán precio_unitario=0. El agente debe usar su conocimiento de
        las tarifas oficiales de aws.amazon.com/pricing para calcular su costo:
        AmazonEKS, AWSBackup, AmazonVPC, AmazonRoute53, AmazonCloudWatch.

    Returns:
        dict con lista de precios por servicio, región y location name.
    """
    if isinstance(servicios, str):
        try:
            servicios = json.loads(servicios)
        except Exception:
            servicios = [s.strip() for s in servicios.split(',') if s.strip()]

    if isinstance(parametros, str):
        try:
            parametros = json.loads(parametros)
        except Exception:
            parametros = {}

    location_name = REGION_NAMES.get(region, "US East (N. Virginia)")

    logger.info(f"[MCP] get_aws_pricing | region={region} | servicios={servicios}")

    precios = []
    for servicio in servicios:
        params_raw = parametros.get(servicio, {})
        precio = consultar_precio_servicio(servicio, location_name, params_raw)
        precios.append(precio)

    return {
        "precios_por_servicio": precios,
        "region":               region,
        "location":             location_name
    }


def lambda_handler(event, context):
    http_method = (
        event.get('requestContext', {}).get('http', {}).get('method', '')
        or event.get('httpMethod', '')
    )

    if http_method in ('GET', 'OPTIONS') or 'body' not in event or event.get('body') is None:
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                'Access-Control-Allow-Headers': '*'
            },
            'body': json.dumps({'status': 'ok'})
        }

    return mcp.handle_request(event, context)