import os
import sys

# Define o diretório raiz do projeto
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from flask import Flask, render_template, jsonify

app = Flask(
    __name__,
    template_folder=os.path.join(root_dir, "templates"),
    static_folder=os.path.join(root_dir, "static"),
    static_url_path="/static"
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "application": "WebGIS Vertical Green"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
