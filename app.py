from flask import Flask, render_template, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "application": "WebGIS Vertical Green"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
