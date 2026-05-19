from flask import Flask, request, jsonify
import json, sys, importlib.util, os, traceback

app = Flask(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(BASE, "src/estimacion"))
sys.path.insert(0, os.path.join(BASE, "src/bedrock"))

def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo

estimacion = cargar_modulo("estimacion_handler", os.path.join(BASE, "src/estimacion/handler.py"))

@app.route('/estimate', methods=['POST'])
def estimate():
    try:
        event = {'body': json.dumps(request.get_json())}
        result = estimacion.lambda_handler(event, None)
        return jsonify(json.loads(result['body'])), result['statusCode']
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)