from flask import Flask, send_from_directory
from flask_cors import CORS  # Import CORS

app = Flask(__name__, static_folder='static')

# Enable CORS for all routes
CORS(app, resources={r"/subtitle/*": {"origins": "http://localhost:5000"}})

@app.route('/')
def home():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/video/<path:filename>')
def serve_video(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/subtitle/<path:filename>')
def serve_subtitle(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
