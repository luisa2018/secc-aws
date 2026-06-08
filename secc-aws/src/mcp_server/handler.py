import json
import boto3
from botocore.exceptions import ClientError
from awslabs.mcp_lambda_handler import MCPLambdaHandler

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

# Servicios que no usan filtro de location porque son globales
SIN_FILTRO_LOCATION = {
    "AmazonDynamoDB",
}

# Filtros base por servicio — solo los campos que NO cambian entre escenarios
# Los campos dinámicos (instanceType, databaseEngine, etc.) vienen en parametros
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
        {"field": "location",   "value": "Europe"},
        {"field": "usagetype",  "value": "EU-DataTransfer-Out-Bytes"},
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


def consultar_precio_servicio(service_code, location_name, parametros_dinamicos=None):
    """
    Consulta precio de un servicio AWS con filtros base + filtros dinámicos.
    parametros_dinamicos: dict con campos adicionales, ej:
        {"instanceType": "m5.large", "databaseEngine": "MySQL"}
    """
    try:
        pricing_filters = []

        # Agregar filtro de location si el servicio lo requiere
        if service_code not in SIN_FILTRO_LOCATION:
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": "location",
                "Value": location_name
            })

        # Agregar filtros base del servicio
        for f in FILTROS_BASE.get(service_code, []):
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": f["field"],
                "Value": f["value"]
            })

        # Agregar filtros dinámicos que vienen del agente
        if parametros_dinamicos:
            for field, value in parametros_dinamicos.items():
                pricing_filters.append({
                    "Type": "TERM_MATCH",
                    "Field": field,
                    "Value": str(value)
                })

        kwargs = {"ServiceCode": service_code, "MaxResults": 5}
        if pricing_filters:
            kwargs["Filters"] = pricing_filters

        response = pricing_client.get_products(**kwargs)
        price_list = response.get("PriceList", [])

        if not price_list:
            return {
                "servicio":        service_code,
                "precio_unitario": 0.0,
                "unidad":          "N/A",
                "descripcion":     "Sin precio disponible para los filtros indicados"
            }

        # Buscar el primer precio mayor a 0
        for raw in price_list:
            item = json.loads(raw)
            terms = item.get("terms", {}).get("OnDemand", {})
            for term in terms.values():
                for dimension in term.get("priceDimensions", {}).values():
                    precio_str = dimension.get("pricePerUnit", {}).get("USD", "0")
                    if float(precio_str) > 0:
                        return {
                            "servicio":        service_code,
                            "precio_unitario": float(precio_str),
                            "unidad":          dimension.get("unit", ""),
                            "descripcion":     dimension.get("description", "")
                        }

        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "N/A",
            "descripcion":     "Solo precios free tier o sin coincidencia"
        }

    except ClientError as e:
        return {
            "servicio":        service_code,
            "precio_unitario": 0.0,
            "unidad":          "ERROR",
            "descripcion":     f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
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
    Consulta el precio unitario de una lista de servicios AWS.

    Args:
        servicios: Lista de service codes AWS. Ej: ["AmazonEC2", "AmazonRDS"]
        region: Región AWS. Ej: "us-east-1", "eu-west-1", "sa-east-1"
        parametros: Filtros dinámicos por servicio para obtener precio exacto.
            Ej: {
                "AmazonEC2": {"instanceType": "m5.large"},
                "AmazonRDS": {"instanceType": "db.m5.large", "databaseEngine": "MySQL"},
                "AmazonElastiCache": {"instanceType": "cache.r6g.large"}
            }
            Campos soportados por servicio:
            - AmazonEC2: instanceType (ej: "m5.large", "t3.medium", "m5.xlarge")
            - AmazonRDS: instanceType (ej: "db.m5.large"), databaseEngine ("MySQL"/"PostgreSQL")
            - AmazonElastiCache: instanceType (ej: "cache.r6g.large")
            - AmazonSageMaker: instanceType (ej: "ml.m5.xlarge")
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

    precios = []
    for servicio in servicios:
        params_servicio = parametros.get(servicio, {})
        precio = consultar_precio_servicio(servicio, location_name, params_servicio)
        precios.append(precio)

    return {
        "precios_por_servicio": precios,
        "region":               region,
        "location":             location_name
    }


def lambda_handler(event, context):
    """Entry point para AWS Lambda"""
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
