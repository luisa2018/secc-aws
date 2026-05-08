import json

def lambda_handler(event, context):
    """
    MCP Server - Implementación JSON-RPC 2.0
    """
    try:
        body = json.loads(event.get("body", "{}"))
        method = body.get("method", "")
        request_id = body.get("id", 1)

        # Router de métodos
        if method == "tools/list":
            return tools_list(request_id)
        elif method == "tools/call":
            return tools_call(body, request_id)
        else:
            return jsonrpc_error(request_id, -32601, "Method not found")

    except Exception as e:
        return jsonrpc_error(1, -32700, f"Parse error: {str(e)}")


def tools_list(request_id):
    """Retorna lista de herramientas disponibles"""
    tools = [
        {
            "name": "calcular_precio_ec2",
            "description": "Calcula el precio de una instancia EC2"
        },
        {
            "name": "calcular_precio_s3",
            "description": "Calcula el precio de almacenamiento en S3"
        }
    ]
    return jsonrpc_response(request_id, {"tools": tools})


def tools_call(body, request_id):
    """Ejecuta una herramienta específica"""
    params = body.get("params", {})
    tool_name = params.get("name", "")

    if tool_name == "calcular_precio_ec2":
        return jsonrpc_response(request_id, {"precio": "pendiente de implementar"})
    elif tool_name == "calcular_precio_s3":
        return jsonrpc_response(request_id, {"precio": "pendiente de implementar"})
    else:
        return jsonrpc_error(request_id, -32602, f"Tool not found: {tool_name}")


def jsonrpc_response(request_id, result):
    """Formato estándar JSON-RPC 2.0 para respuestas exitosas"""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        })
    }


def jsonrpc_error(request_id, code, message):
    """Formato estándar JSON-RPC 2.0 para errores"""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id
        })
    }