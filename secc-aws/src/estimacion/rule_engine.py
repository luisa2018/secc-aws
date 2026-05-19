AWS_COST_SERVICES = {
    "AmazonEC2", "AmazonEBS", "AmazonRDS", "AmazonS3",
    "AmazonNatGateway", "ElasticLoadBalancing", "AmazonCloudFront",
    "AmazonRoute53", "AmazonCloudWatch", "AWSBackup", "AWSWAF",
    "AmazonECS", "AmazonEKS", "AWSLambda", "AmazonAPIGateway",
    "AmazonDynamoDB", "AmazonElastiCache", "AmazonSNS", "AmazonSQS",
    "AmazonKinesis", "AWSSecretsManager", "AmazonCognito",
    "AmazonSageMaker", "AmazonBedrock", "AmazonMSK", "AmazonECR",
    "AWSKMS", "AWSCloudTrail", "AmazonGuardDuty", "AWSXRAY",
    "AWSConfig", "AWSShield", "AWSSecurityHub",
    "AmazonEventBridge", "AWSStepFunctions",
    "AWSFargate", "AWSGlue", "AmazonEMR", "AmazonKinesisFirehose",
    "AmazonAthena", "AmazonRedshift", "AWSDirectConnect",
    "AmazonMacie"
}

CORRECCIONES_CODIGOS = {
    "awswaf":              "AWSWAF",
    "AWSWaf":              "AWSWAF",
    "AWSWAFv2":            "AWSWAF",
    "AWSELBv2":            "ElasticLoadBalancing",
    "AmazonELB":           "ElasticLoadBalancing",
    "AmazonNATGateway":    "AmazonNatGateway",
    "AmazonNAT":           "AmazonNatGateway",
    "AWSSecretManager":    "AWSSecretsManager",
    "AmazonApiGatewayV2":  "AmazonAPIGateway",
    "AmazonApiGateway":    "AmazonAPIGateway",
    "AmazonKinesisStreams": "AmazonKinesis",
    "AmazonKinesisFirehose":"AmazonKinesisFirehose",
    "AWSSNS":              "AmazonSNS",
    "AWSSQS":              "AmazonSQS",
    # Nombres incorrectos frecuentes que Bedrock puede generar
    "CloudFront":          "AmazonCloudFront",
    "CloudWatch":          "AmazonCloudWatch",
    "NatGateway":          "AmazonNatGateway",
    "APIGateway":          "AmazonAPIGateway",
    "DynamoDB":            "AmazonDynamoDB",
    "Lambda":              "AWSLambda",
    "S3":                  "AmazonS3",
    "EC2":                 "AmazonEC2",
    "RDS":                 "AmazonRDS",
}

PROHIBIDOS_POR_ESTILO = {
    "monolitica":     {"AmazonEKS", "AmazonECS", "AWSLambda"},
    "serverless":     {"AmazonEC2", "AmazonECS", "AmazonEKS"},
    "event_driven":   {"AmazonEC2"},
    "microservicios": set(),
    "hibrida":        set()
}


def validar_servicios(servicios, contexto, arquitectura, inferidos):
    vistos = set()
    servicios_validos = []
    decision_log = []

    estilo    = contexto.get("estilo_arquitectura", "")
    tipo_db   = arquitectura.get("tipo_base_datos", "")
    ia_tipo   = contexto.get("ia_tipo", "ninguna")
    prohibidos = PROHIBIDOS_POR_ESTILO.get(estilo, set())

    # ── Guardar atributos de servicios eliminados por nombre incorrecto ──
    # Si Bedrock propone "CloudFront" en vez de "AmazonCloudFront", el código
    # se normaliza correctamente pero si ya existe en vistos se descarta.
    # Guardamos los atributos para usarlos cuando se agrega el servicio inferido.
    atributos_rescatados = {}

    for servicio in servicios:
        codigo_original = servicio.get("servicio_aws", "").strip()
        codigo = normalizar_codigo(codigo_original)

        if codigo not in AWS_COST_SERVICES:
            decision_log.append(f"Eliminado: {codigo} no está en catálogo AWS")
            continue

        if codigo in prohibidos:
            decision_log.append(f"Eliminado: {codigo} prohibido para estilo {estilo}")
            continue

        if codigo in vistos:
            decision_log.append(f"Eliminado: {codigo} duplicado")
            continue

        vistos.add(codigo)
        servicio["servicio_aws"] = codigo
        servicios_validos.append(servicio)

        # Guardar atributos por si fueron normalizados desde nombre incorrecto
        atributos = servicio.get("atributos", {})
        if atributos:
            atributos_rescatados[codigo] = atributos

    codigos = {s["servicio_aws"] for s in servicios_validos}

    # ── Agregar servicios inferidos con atributos rescatados si existen ──

    if tipo_db == "relacional" and "AmazonRDS" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonRDS",
            "atributos": atributos_rescatados.get("AmazonRDS", {})
        })
        decision_log.append("RDS agregado: tipo_base_datos=relacional")

    if tipo_db == "nosql" and "AmazonDynamoDB" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonDynamoDB",
            "atributos": atributos_rescatados.get("AmazonDynamoDB", {})
        })
        decision_log.append("DynamoDB agregado: tipo_base_datos=nosql")

    if ia_tipo == "apis_externas" and inferidos.get("expone_api_publica") and "AmazonAPIGateway" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonAPIGateway",
            "atributos": atributos_rescatados.get("AmazonAPIGateway", {})
        })
        decision_log.append("APIGateway agregado: ia_tipo=apis_externas + expone_api_publica=True")

    if inferidos.get("cdn") and "AmazonCloudFront" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonCloudFront",
            "atributos": atributos_rescatados.get("AmazonCloudFront", {})
        })
        decision_log.append("CloudFront agregado: cdn=True")

    if inferidos.get("red_privada") and "AmazonNatGateway" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonNatGateway",
            "atributos": atributos_rescatados.get("AmazonNatGateway", {})
        })
        decision_log.append("NatGateway agregado: red_privada=True")

    if "AmazonCloudWatch" not in codigos:
        servicios_validos.append({
            "servicio_aws": "AmazonCloudWatch",
            "atributos": atributos_rescatados.get("AmazonCloudWatch", {})
        })
        decision_log.append("CloudWatch agregado: monitoreo siempre requerido")

    return servicios_validos, decision_log


def normalizar_codigo(codigo):
    return CORRECCIONES_CODIGOS.get(codigo, codigo)