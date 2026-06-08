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
# Cualquier otro campo enviado por Bedrock es ignorado
CAMPOS_DINAMICOS_VALIDOS = {
    "AmazonEC2":         ["instanceType"],
    "AmazonRDS":         ["instanceType", "databaseEngine"],
    "AmazonElastiCache": ["instanceType"],
    "AmazonSageMaker":   ["instanceType"],
}

# Filtros base internos por servicio — el MCP los maneja sin depender de Bedrock
FILTROS_BASE = {
    "AmazonEC2": [
        {"field": "operatingSystem", "value": "Linux"},
        {"field": "tenancy",         "value": "Shared"},
        {"field": "capacitystatus",  "value": "Used"},
        {"field": "preInstalledSw",  "value": "NA"},
    ],
    "AmazonRDS": [
        {"field": "deploymentOption", "value": "Single-AZ"},
    ],
    "AmazonEBS": [
        {"field": "volumeApiName", "value": "gp3"},
    ],
    "AmazonS3": [
        {"field": "storageClass", "value": "General Purpose"},
        {"field": "volumeType",   "value": "Standard"},
    ],
    "ElasticLoadBalancing": [
        {"field": "loadBalancerType", "value": "Application"},
    ],
    "AmazonCloudFront": [
        {"field": "usagetype", "value": "US-DataTransfer-Out-Bytes"},
    ],
    "AmazonDynamoDB": [
        {"field": "usagetype", "value": "WriteRequestUnits"},
    ],
    "AWSLambda": [
        {"field": "group", "value": "AWS-Lambda-Requests"},
    ],
    "AmazonAPIGateway": [
        {"field": "usagetype", "value": "USE1-ApiGatewayHttpRequest"},
    ],
    "AmazonElastiCache": [
        {"field": "cacheEngine", "value": "Redis"},
    ],
    "AWSFargate": [
        {"field": "group", "value": "AWS-Fargate-vCPU-Hours:perCPU"},
    ],
    "AmazonEKS": [
        {"field": "group", "value": "AmazonEKS-Clusters"},
    ],
    "AmazonSNS": [
        {"field": "group", "value": "SNS-Requests"},
    ],
    "AmazonSQS": [
        {"field": "group", "value": "SQS-APIRequest"},
    ],
    "AmazonCloudWatch": [
        {"field": "group", "value": "MetricStorage:StdResolution"},
    ],
    "AWSSecretsManager": [
        {"field": "group", "value": "AWSSecretsManager-Secret"},
    ],
    "AWSBackup": [
        {"field": "group", "value": "AWSBackup-BackupStorage"},
    ],
    "AWSWAF": [
        {"field": "group", "value": "AWS-WAF-WebACL"},
    ],
    "AmazonRoute53": [
        {"field": "group", "value": "DNS-Queries"},
    ],
    "AWSKMS": [
        {"field": "group", "value": "AWS-KMS-Keys"},
    ],
    "AmazonECR": [
        {"field": "group", "value": "AmazonECR-TimedStorage-ByteHrs"},
    ],
    "AmazonKinesis": [
        {"field": "group", "value": "AmazonKinesis-ShardHour"},
    ],
    "AmazonEventBridge": [
        {"field": "group", "value": "AmazonEventBridge-Events"},
    ],
    "AWSStepFunctions": [
        {"field": "group", "value": "AWSStepFunctions-StateTransitions"},
    ],
    "AmazonSageMaker": [
        {"field": "group", "value": "SageMaker-Instances"},
    ],
    "AmazonBedrock": [
        {"field": "group", "value": "AmazonBedrock-InputTokens"},
    ],
    "AmazonVPC": [
        {"field": "group", "value": "AmazonVPC-NatGateway-Hours"},
    ],
}

# Servicios que no usan filtro de location
SIN_FILTRO_LOCATION = {"AmazonDynamoDB"}


def filtrar_parametros_validos(service_code, parametros_raw):
    """
    Solo acepta los campos dinámicos válidos para cada servicio.
    Ignora cualquier campo inventado por Bedrock.
    """
    campos_validos = CAMPOS_DINAMICOS_VALIDOS.get(service_code, [])
    return {k: v for k, v in parametros_raw.items() if k in campos_validos}


def consultar_precio_servicio(service_code, location_name, parametros_dinamicos=None):
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

        # Solo agregar parámetros dinámicos válidos
        if parametros_dinamicos:
            parametros_limpios = filtrar_parametros_validos(service_code, parametros_dinamicos)
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
            Ejemplos: ["AmazonEC2", "AmazonRDS", "AmazonS3", "AmazonEKS",
                       "AmazonElastiCache", "AmazonSageMaker", "AmazonVPC",
                       "AWSBackup", "AWSKMS", "AWSSecretsManager", "AWSWAF",
                       "AmazonCloudFront", "AmazonAPIGateway", "AmazonCloudWatch",
                       "AmazonRoute53", "AmazonECR", "AmazonEBS"]

        region: Código de región AWS.
            Valores válidos: "us-east-1", "us-west-2", "eu-west-1",
            "eu-central-1", "ap-southeast-1", "sa-east-1"

        parametros: Filtros adicionales SOLO para servicios con instancias.
            IMPORTANTE: Solo usa los campos exactos listados abajo.
            Cualquier otro campo es ignorado.

            Campos válidos por servicio:
            - AmazonEC2:
                instanceType: tipo de instancia EC2
                Ejemplos: "t3.medium", "t3.large", "m5.large", "m5.xlarge"

            - AmazonRDS:
                instanceType: tipo de instancia RDS
                Ejemplos: "db.t3.medium", "db.m5.large", "db.m5.xlarge"
                databaseEngine: motor de base de datos
                Valores válidos: "MySQL", "PostgreSQL", "MariaDB"

            - AmazonElastiCache:
                instanceType: tipo de instancia ElastiCache
                Ejemplos: "cache.t3.medium", "cache.r6g.large"

            - AmazonSageMaker:
                instanceType: tipo de instancia SageMaker
                Ejemplos: "ml.t3.medium", "ml.m5.large", "ml.m5.xlarge"

            Ejemplo de uso correcto:
            parametros={
                "AmazonEC2": {"instanceType": "m5.large"},
                "AmazonRDS": {"instanceType": "db.m5.large", "databaseEngine": "MySQL"},
                "AmazonElastiCache": {"instanceType": "cache.r6g.large"},
                "AmazonSageMaker": {"instanceType": "ml.m5.xlarge"}
            }

            Para todos los demás servicios NO pases parametros adicionales.
            El MCP los maneja internamente con los filtros correctos.

    Returns:
        dict con lista de precios por servicio, región consultada y location name.
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
