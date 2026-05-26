import json
import boto3
from botocore.exceptions import ClientError
from fastmcp import FastMCP

from rule_engine import AWS_COST_SERVICES

mcp = FastMCP("SECC-AWS MCP Server")

pricing_client = boto3.client('pricing', region_name='us-east-1')

FILTROS_POR_SERVICIO = {
    "AmazonEC2": [
        {"field": "operatingSystem", "value": "Linux"},
        {"field": "tenancy",         "value": "Shared"},
        {"field": "capacitystatus",  "value": "Used"},
        {"field": "preInstalledSw",  "value": "NA"},
        {"field": "instanceType",    "value": "m5.xlarge"},
    ],
    "AmazonRDS": [
        {"field": "databaseEngine",  "value": "MySQL"},
        {"field": "deploymentOption","value": "Single-AZ"},
        {"field": "instanceType",    "value": "db.t3.medium"},
    ],
    "AmazonEBS": [
        {"field": "volumeApiName",   "value": "gp3"},
    ],
    "AmazonS3": [
        {"field": "storageClass",    "value": "General Purpose"},
        {"field": "volumeType",      "value": "Standard"},
    ],
    "ElasticLoadBalancing": [
        {"field": "loadBalancerType","value": "Application"},
    ],
    "AmazonCloudFront": [
        {"field": "usagetype",       "value": "CA-Requests-Tier1"},
    ],
    "AmazonDynamoDB": [
        {"field": "usagetype",       "value": "WriteRequestUnits"},
    ],
    "AWSLambda": [
        {"field": "group",           "value": "AWS-Lambda-Requests"},
    ],
    "AmazonAPIGateway": [
        {"field": "operation",       "value": "ApiGatewayHttpApi"},
        {"field": "usagetype",       "value": "USE1-ApiGatewayHttpRequest"},
    ],
    "AmazonElastiCache": [
        {"field": "cacheEngine",     "value": "Redis"},
    ],
    "AWSFargate": [
        {"field": "group",           "value": "AWS-Fargate-vCPU-Hours:perCPU"},
    ],
    "AmazonEKS": [
        {"field": "group",           "value": "AmazonEKS-Clusters"},
    ],
    "AmazonSNS": [
        {"field": "group",           "value": "SNS-Requests"},
    ],
    "AmazonSQS": [
        {"field": "group",           "value": "SQS-APIRequest"},
    ],
    "AmazonCloudWatch": [
        {"field": "usagetype",       "value": "DataProcessing-Bytes"},
    ],
    "AWSSecretsManager": [
        {"field": "group",           "value": "AWSSecretsManager-Secret"},
    ],
    "AWSBackup": [
        {"field": "group",           "value": "AWSBackup-BackupStorage"},
    ],
    "AWSWAF": [
        {"field": "usagetype",       "value": "USE1-WebACLV2"},
    ],
    "AmazonRoute53": [
        {"field": "group",           "value": "DNS-Queries"},
    ],
    "AWSKMS": [
        {"field": "group",           "value": "AWS-KMS-Keys"},
    ],
    "AmazonKinesis": [
        {"field": "group",           "value": "AmazonKinesis-ShardHour"},
    ],
    "AmazonEventBridge": [
        {"field": "group",           "value": "AmazonEventBridge-Events"},
    ],
    "AWSStepFunctions": [
        {"field": "group",           "value": "AWSStepFunctions-StateTransitions"},
    ],
    "AmazonSageMaker": [
        {"field": "group",           "value": "SageMaker-Instances"},
    ],
    "AmazonBedrock": [
        {"field": "group",           "value": "AmazonBedrock-InputTokens"},
    ],
    "AmazonNatGateway": [
        {"field": "group",           "value": "AmazonVPC-NatGateway-Hours"},
    ],
}

SIN_FILTRO_LOCATION = {
    "AmazonCloudFront", "AmazonDynamoDB",
    "AmazonCloudWatch", "AmazonAPIGateway", "AWSWAF"
}

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


def consultar_precio_servicio(service_code, location_name):
    try:
        pricing_filters = []
        if service_code not in SIN_FILTRO_LOCATION:
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": "location",
                "Value": location_name
            })
        for f in FILTROS_POR_SERVICIO.get(service_code, []):
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": f["field"],
                "Value": f["value"]
            })

        kwargs = {"ServiceCode": service_code, "MaxResults": 3}
        if pricing_filters:
            kwargs["Filters"] = pricing_filters

        response = pricing_client.get_products(**kwargs)
        price_list = response.get("PriceList", [])

        if not price_list:
            return {
                "servicio": service_code,
                "precio_unitario": 0.0,
                "unidad": "N/A",
                "descripcion": "Sin precio disponible"
            }

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
            "servicio": service_code,
            "precio_unitario": 0.0,
            "unidad": "N/A",
            "descripcion": "Solo precios free tier"
        }

    except ClientError as e:
        return {
            "servicio": service_code,
            "precio_unitario": 0.0,
            "unidad": "ERROR",
            "descripcion": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        return {
            "servicio": service_code,
            "precio_unitario": 0.0,
            "unidad": "ERROR",
            "descripcion": f"Error: {str(e)}"
        }


@mcp.tool()
def get_aws_pricing(servicios: list, region: str = "us-east-1") -> dict:
    """Consulta el precio unitario de una lista de servicios AWS en AWS Pricing API"""
    location_name = REGION_NAMES.get(region, "US East (N. Virginia)")
    precios = [consultar_precio_servicio(s, location_name) for s in servicios]
    return {
        "precios_por_servicio": precios,
        "region": region
    }


@mcp.tool()
def list_supported_services() -> dict:
    """Lista los servicios AWS soportados para consulta de precios"""
    return {"servicios_soportados": sorted(list(AWS_COST_SERVICES))}


def lambda_handler(event, context):
    """Entry point para AWS Lambda"""
    return mcp.run(transport="lambda")


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=5001)