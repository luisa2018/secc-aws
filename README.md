# SECC-AWS — Backend

> Sistema de Evaluación de Costos en Cloud (SECC-AWS)  
> Backend serverless desplegado en AWS con SAM

---

## Descripción

SECC-AWS es un prototipo académico que estima costos de arquitecturas cloud en AWS a partir de parámetros de entrada definidos por el usuario. El backend orquesta un agente de inteligencia artificial (Amazon Bedrock + Strands Agents) que consulta precios oficiales de AWS mediante el protocolo Model Context Protocol (MCP) y calcula los costos con precisión matemática a través del Amazon Bedrock AgentCore Code Interpreter.

---

## Arquitectura

El backend se implementa como una arquitectura serverless sobre AWS, compuesta por tres funciones Lambda expuestas mediante Amazon API Gateway:

| Función | Descripción |
|---|---|
| `estimacion` | Orquesta el agente Strands y genera la estimación de costos |
| `mcp_server` | Expone herramientas MCP para consultar la AWS Price List API |
| `reporte` | Genera el informe en formato PDF en memoria |

---

## Estructura del proyecto

```
/ (raíz del repositorio)
├── .github/
│   └── workflows/          # CI/CD con GitHub Actions
└── secc-aws/
    ├── src/
    │   ├── estimacion/
    │   │   ├── handler.py          # Entry point Lambda
    │   │   ├── bedrock_service.py  # Integración con Strands Agent y Bedrock
    │   │   ├── rule_engine.py      # Inferencia de parámetros por arquitectura
    │   │   └── requirements.txt
    │   ├── mcp_server/
    │   │   ├── handler.py          # Entry point Lambda MCP Server
    │   │   ├── rule_engine.py      # Lógica de consulta AWS Price List API
    │   │   └── requirements.txt
    │   └── reporte/
    │       ├── handler.py          # Entry point Lambda generación PDF
    │       └── requirements.txt
    ├── template.yaml       # Definición infraestructura AWS SAM
    ├── samconfig.toml      # Configuración de despliegue SAM
    └── local_server.py     # Servidor MCP local para desarrollo
```

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Orquestación de agente | Strands Agents |
| Modelo de lenguaje | Amazon Bedrock (Claude Sonnet) |
| Consulta de precios | AWS Price List API vía MCP |
| Cálculo de costos | Amazon Bedrock AgentCore Code Interpreter |
| Protocolo de herramientas | Model Context Protocol (MCP) + FastMCP |
| Infraestructura | AWS Lambda + Amazon API Gateway |
| Despliegue | AWS SAM |
| CI/CD | GitHub Actions |

---

## Endpoints

### `POST /estimate`
Recibe los parámetros del escenario y retorna la estimación de costos en JSON.

### `POST /report`
Recibe la estimación generada y retorna el informe en formato PDF.

---

## Ejecución local

### Requisitos previos
- Python 3.12
- AWS CLI configurado con credenciales válidas
- AWS SAM CLI instalado

### Instalar dependencias

```bash
cd secc-aws/src/estimacion
pip install -r requirements.txt

cd ../mcp_server
pip install -r requirements.txt

cd ../reporte
pip install -r requirements.txt
```

### Levantar el servidor MCP local

```bash
cd secc-aws
python local_server.py
```

### Levantar el backend localmente con SAM

```bash
cd secc-aws
sam local start-api
```

---

## Despliegue en AWS

El despliegue se realiza automáticamente mediante GitHub Actions al hacer push a la rama `main`. También puede realizarse manualmente:

```bash
cd secc-aws
sam build
sam deploy
```

La configuración del despliegue se encuentra en `samconfig.toml`.

---

## Variables de entorno

| Variable | Descripción |
|---|---|
| `MCP_URL` | URL del MCP Server (por defecto `http://127.0.0.1:5001/mcp` en local) |

---

## Autor

**luisa2018** — Proyecto de grado 2026
