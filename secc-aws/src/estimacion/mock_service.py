from datetime import datetime

MULTIPLICADOR_TIEMPO = {
    "mensual":    1,
    "trimestral": 3,
    "anual":      12
}

def calcular_semaforo(porcentaje_uso):
    if porcentaje_uso <= 70:
        return {
            "estado": "optimo",
            "mensaje": f"Tu estimación está dentro del presupuesto. Estás usando el {porcentaje_uso}% de tu presupuesto disponible."
        }
    elif porcentaje_uso <= 100:
        return {
            "estado": "ajustado",
            "mensaje": f"Tu estimación está cerca del límite. Estás usando el {porcentaje_uso}% de tu presupuesto disponible."
        }
    else:
        return {
            "estado": "excedido",
            "mensaje": f"Tu estimación supera el presupuesto. Estás usando el {porcentaje_uso}% de tu presupuesto disponible."
        }


def generar_estimacion(contexto, region_aws, inferidos, horizonte):
    multiplicador = MULTIPLICADOR_TIEMPO.get(horizonte, 1)

    servicios_mock = [
        {
            "nombre": "Servidor de aplicación",
            "servicio_aws": "AmazonEC2",
            "justificacion": "Servicio de cómputo para alojar la aplicación",
            "costo_mensual": 50.00
        },
        {
            "nombre": "Base de datos",
            "servicio_aws": "AmazonRDS",
            "justificacion": "Base de datos relacional administrada",
            "costo_mensual": 80.00
        },
        {
            "nombre": "Almacenamiento",
            "servicio_aws": "AmazonS3",
            "justificacion": "Almacenamiento de archivos estáticos",
            "costo_mensual": 20.00
        }
    ]

    total_mensual = sum(s["costo_mensual"] for s in servicios_mock)
    valor_total = round(total_mensual * multiplicador, 2)
    presupuesto = contexto.get("presupuesto", 0)
    porcentaje_uso = round((valor_total / presupuesto * 100), 2) if presupuesto > 0 else 0
    semaforo = calcular_semaforo(porcentaje_uso)

    return {
        "metadata": {
            "estilo_arquitectura": contexto.get("estilo_arquitectura"),
            "ambiente": contexto.get("ambiente"),
            "fecha_ejecucion": datetime.utcnow().isoformat(),
            "region_aws": region_aws,
            "horizonte_tiempo": horizonte
        },
        "servicios": servicios_mock,
        "costo_estimado": {
            "valor_total": valor_total,
            "moneda": "USD",
            "periodo": horizonte
        },
        "evaluacion_presupuesto": {
            "dentro_presupuesto": valor_total <= presupuesto,
            "porcentaje_uso": porcentaje_uso,
            "estado": semaforo["estado"],
            "mensaje": semaforo["mensaje"]
        },
        "recomendaciones": [
            "MOCK: Esta es una respuesta de prueba",
            "MOCK: Las recomendaciones reales las generará Bedrock"
        ],
        "resumen": "MOCK: Resumen generado por Bedrock en implementación real"
    }