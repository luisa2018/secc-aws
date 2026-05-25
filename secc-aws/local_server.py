from flask import Flask, request, jsonify, Response
import json, sys, importlib.util, os, traceback, base64

app = Flask(__name__)
from flask_cors import CORS
CORS(app)

BASE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(BASE, "src/estimacion"))
sys.path.insert(0, os.path.join(BASE, "src/bedrock"))
sys.path.insert(0, os.path.join(BASE, "src/reporte"))

def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo

estimacion = cargar_modulo(
    "estimacion_handler",
    os.path.join(BASE, "src/estimacion/handler.py")
)
reporte = cargar_modulo(
    "reporte_handler",
    os.path.join(BASE, "src/reporte/handler.py")
)

@app.route('/estimate', methods=['POST'])
def estimate():
    try:
        event = {'body': json.dumps(request.get_json())}
        result = estimacion.lambda_handler(event, None)
        return jsonify(json.loads(result['body'])), result['statusCode']
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/report', methods=['POST'])
def report():
    try:
        event = {'body': json.dumps(request.get_json())}
        result = reporte.lambda_handler(event, None)

        if result.get('isBase64Encoded'):
            pdf_bytes = base64.b64decode(result['body'])
            return Response(
                pdf_bytes,
                status=result['statusCode'],
                headers={
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': 'attachment; filename="informe_secc_aws.pdf"',
                    'Access-Control-Allow-Origin': '*',
                }
            )
        return jsonify(json.loads(result['body'])), result['statusCode']
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)