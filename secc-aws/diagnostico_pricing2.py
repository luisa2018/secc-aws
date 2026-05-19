"""
Diagnóstico específico - ejecutar con:
python diagnostico_pricing2.py
"""
import boto3
import json

pricing_client = boto3.client('pricing', region_name='us-east-1')

# ── CloudFront sin filtro de location ──────────────────────────────────────
print("=" * 60)
print("CloudFront - buscando transferencia (sin filtro location)")
print("=" * 60)
response = pricing_client.get_products(
    ServiceCode="AmazonCloudFront",
    Filters=[
        {"Type": "TERM_MATCH", "Field": "usagetype", "Value": "DataTransfer-Out-Bytes"}
    ],
    MaxResults=3
)
for price_item in response.get("PriceList", []):
    item = json.loads(price_item)
    attrs = item.get("product", {}).get("attributes", {})
    terms = item.get("terms", {}).get("OnDemand", {})
    print(f"  usagetype: {attrs.get('usagetype')}")
    print(f"  location:  {attrs.get('location')}")
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            print(f"  precio:    ${dim.get('pricePerUnit',{}).get('USD')} / {dim.get('unit')}")
            print(f"  desc:      {dim.get('description')}")
    print()

# ── CloudWatch - logs ingesta ──────────────────────────────────────────────
print("=" * 60)
print("CloudWatch - buscando logs ingesta (PutLogEvents)")
print("=" * 60)
response = pricing_client.get_products(
    ServiceCode="AmazonCloudWatch",
    Filters=[
        {"Type": "TERM_MATCH", "Field": "location",  "Value": "US East (N. Virginia)"},
        {"Type": "TERM_MATCH", "Field": "operation", "Value": "PutLogEvents"},
    ],
    MaxResults=5
)
for price_item in response.get("PriceList", []):
    item = json.loads(price_item)
    attrs = item.get("product", {}).get("attributes", {})
    terms = item.get("terms", {}).get("OnDemand", {})
    print(f"  group:     {attrs.get('group')}")
    print(f"  usagetype: {attrs.get('usagetype')}")
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            print(f"  precio:    ${dim.get('pricePerUnit',{}).get('USD')} / {dim.get('unit')}")
            print(f"  desc:      {dim.get('description')}")
    print()

# ── AWSWAF - Web ACL us-east-1 ─────────────────────────────────────────────
print("=" * 60)
print("AWSWAF - buscando WebACL us-east-1")
print("=" * 60)
response = pricing_client.get_products(
    ServiceCode="AWSWAF",
    Filters=[
        {"Type": "TERM_MATCH", "Field": "group", "Value": "Web ACL"},
    ],
    MaxResults=5
)
for price_item in response.get("PriceList", []):
    item = json.loads(price_item)
    attrs = item.get("product", {}).get("attributes", {})
    terms = item.get("terms", {}).get("OnDemand", {})
    print(f"  usagetype: {attrs.get('usagetype')}")
    print(f"  location:  {attrs.get('location')}")
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            print(f"  precio:    ${dim.get('pricePerUnit',{}).get('USD')} / {dim.get('unit')}")
            print(f"  desc:      {dim.get('description')}")
    print()

# ── DynamoDB on-demand escritura ───────────────────────────────────────────
print("=" * 60)
print("DynamoDB - on-demand WriteRequestUnits")
print("=" * 60)
response = pricing_client.get_products(
    ServiceCode="AmazonDynamoDB",
    Filters=[
        {"Type": "TERM_MATCH", "Field": "location",  "Value": "US East (N. Virginia)"},
        {"Type": "TERM_MATCH", "Field": "operation", "Value": "PayPerRequestThroughput"},
    ],
    MaxResults=5
)
for price_item in response.get("PriceList", []):
    item = json.loads(price_item)
    attrs = item.get("product", {}).get("attributes", {})
    terms = item.get("terms", {}).get("OnDemand", {})
    print(f"  group:     {attrs.get('group')}")
    print(f"  usagetype: {attrs.get('usagetype')}")
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            print(f"  precio:    ${dim.get('pricePerUnit',{}).get('USD')} / {dim.get('unit')}")
            print(f"  desc:      {dim.get('description')}")
    print()

print("Diagnóstico completo")

# Al final del archivo, agrega esto:
print("=" * 60)
print("CloudFront - todos los usagetypes disponibles")
print("=" * 60)
response = pricing_client.get_products(
    ServiceCode="AmazonCloudFront",
    MaxResults=10
)
for price_item in response.get("PriceList", []):
    item = json.loads(price_item)
    attrs = item.get("product", {}).get("attributes", {})
    print(f"  usagetype: {attrs.get('usagetype')} | location: {attrs.get('location')}")