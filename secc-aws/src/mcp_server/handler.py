import json
import boto3
from botocore.exceptions import ClientError

# Cliente AWS Pricing API (solo disponible en us-east-1)
pricing_client = boto3.client('pricing', region_name='us-east-1')


def lambda_handler(event, context):
    """
    MCP Server - Recibe tools/call de Servicio Estimación
    y consulta AWS Price List API
    """
    try:
        body = json.loads(event.get("body", "{}"))
        method = body.get("method", "")
        request_id = body.get("id", 1)

        if method == "tools/call":
            return tools_call(body, request_id)
        else:
            return jsonrpc_error(request_id, -32601, f"Method not supported: {method}")

    except Exception as e:
        return jsonrpc_error(1, -32700, f"Parse error: {str(e)}")


def tools_call(body, request_id):
    """
    Ejecuta get_aws_pricing y retorna pricing data
    """
    params = body.get("params", {})
    tool_name = params.get("name", "")

    if tool_name == "get_aws_pricing":
        return get_aws_pricing(params, request_id)
    else:
        return jsonrpc_error(request_id, -32602, f"Tool not found: {tool_name}")


def get_aws_pricing(params, request_id):
    """
    Consulta precios reales en AWS Price List API
    """
    try:
        service_code = params.get("service_code", "")
        region = params.get("region", "us-east-1")
        filters = params.get("filters", [])

        if not service_code:
            return jsonrpc_error(request_id, -32602, "service_code es requerido")

        # Filtro base por región
        pricing_filters = [
            {
                "Type": "TERM_MATCH",
                "Field": "location",
                "Value": get_region_name(region)
            }
        ]

        # Filtros adicionales que envía el Servicio Estimación
        for f in filters:
            pricing_filters.append({
                "Type": "TERM_MATCH",
                "Field": f.get("field"),
                "Value": f.get("value")
            })

        # Consultar AWS Price List API
        response = pricing_client.get_products(
            ServiceCode=service_code,
            Filters=pricing_filters,
            MaxResults=5
        )

        # Procesar y retornar pricing data
        productos = []
        for price_item in response.get("PriceList", []):
            item = json.loads(price_item)
            productos.append({
                "descripcion": item.get("product", {}).get("attributes", {}),
                "precio": extract_price(item)
            })

        return jsonrpc_response(request_id, {
            "service_code": service_code,
            "region": region,
            "pricing_data": productos
        })

    except ClientError as e:
        return jsonrpc_error(
            request_id, 
            -32603, 
            f"AWS Error: {e.response['Error']['Message']}"
        )
    except Exception as e:
        return jsonrpc_error(request_id, -32603, f"Error: {str(e)}")


def extract_price(item):
    """Extrae precio de la respuesta de AWS Price List API"""
    try:
        terms = item.get("terms", {}).get("OnDemand", {})
        for term in terms.values():
            for dimension in term.get("priceDimensions", {}).values():
                return {
                    "precio_usd": dimension.get("pricePerUnit", {}).get("USD", "0"),
                    "unidad": dimension.get("unit", ""),
                    "descripcion": dimension.get("description", "")
                }
    except Exception:
        return {}
    return {}


def get_region_name(region_code):
    """Convierte código de región a nombre que usa AWS Pricing API"""
    region_names = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "eu-west-1": "Europe (Ireland)",
        "eu-central-1": "Europe (Frankfurt)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-southeast-2": "Asia Pacific (Sydney)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
        "sa-east-1": "South America (Sao Paulo)"
    }
    return region_names.get(region_code, "US East (N. Virginia)")


def jsonrpc_response(request_id, result):
    """Respuesta exitosa JSON-RPC 2.0"""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        })
    }


def jsonrpc_error(request_id, code, message):
    """Error JSON-RPC 2.0"""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id
        })
    }