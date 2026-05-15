from flask import Flask, request, jsonify
import json, sys
sys.path.insert(0, 'src/estimacion')
from handler import lambda_handler

app = Flask(__name__)

@app.route('/estimate', methods=['POST'])
def estimate():
    event = {'body': json.dumps(request.get_json())}
    result = lambda_handler(event, None)
    return jsonify(json.loads(result['body'])), result['statusCode']

if __name__ == '__main__':
    app.run(port=5000)