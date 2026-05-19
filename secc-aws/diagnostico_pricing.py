"""
Script de diagnóstico - ejecutar directamente con:
python diagnostico_pricing.py

Muestra los SKUs reales que devuelve AWS Pricing API para cada servicio problemático.
"""
import boto3
import json

pricing_client = boto3.client('pricing', region_name='us-east-1')

SERVICIOS_PROBLEMA = {
    "AmazonAPIGateway": [
        {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"}
    ],
    "AmazonDynamoDB": [
        {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"}
    ],
    "AmazonCloudFront": [
        {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"}
    ],
    "AWSWAF": [],  # Sin filtros para ver todo
    "AmazonCloudWatch": [
        {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"}
    ],
}

for service_code, filtros in SERVICIOS_PROBLEMA.items():
    print(f"\n{'='*60}")
    print(f"SERVICIO: {service_code}")
    print(f"{'='*60}")
    try:
        kwargs = {
            "ServiceCode": service_code,
            "MaxResults": 5
        }
        if filtros:
            kwargs["Filters"] = filtros

        response = pricing_client.get_products(**kwargs)
        items = response.get("PriceList", [])
        print(f"Total SKUs encontrados: {len(items)}")

        for i, price_item in enumerate(items):
            item = json.loads(price_item)
            producto = item.get("product", {})
            atributos = producto.get("attributes", {})
            terms = item.get("terms", {}).get("OnDemand", {})

            print(f"\n  --- SKU {i+1} ---")
            print(f"  group:       {atributos.get('group', 'N/A')}")
            print(f"  groupDescription: {atributos.get('groupDescription', 'N/A')}")
            print(f"  usagetype:   {atributos.get('usagetype', 'N/A')}")
            print(f"  operation:   {atributos.get('operation', 'N/A')}")
            print(f"  location:    {atributos.get('location', 'N/A')}")

            # Extraer precio
            for term in terms.values():
                for dim in term.get("priceDimensions", {}).values():
                    precio = dim.get("pricePerUnit", {}).get("USD", "?")
                    unidad = dim.get("unit", "?")
                    desc   = dim.get("description", "?")
                    print(f"  precio:      ${precio} / {unidad}")
                    print(f"  descripcion: {desc}")

    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n{'='*60}")
print("Diagnóstico completo")