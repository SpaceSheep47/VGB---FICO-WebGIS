import os
import sys
import glob
import hashlib
import re
from pathlib import Path
from flask import Flask, render_template, jsonify, Response, abort

# Define o diretório raiz do projeto
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

app = Flask(
    __name__,
    template_folder=os.path.join(root_dir, "templates"),
    static_folder=os.path.join(root_dir, "static"),
    static_url_path="/static"
)

# Cache de GeoJSON e registro de camadas
_cache_geojson = {}
_layer_registry = {}

def get_database_dir() -> Path:
    """Retorna o caminho absoluto do diretório do banco de dados contendo os arquivos .gpkg."""
    env_dir = os.environ.get("DATABASE_DIR")
    if env_dir and os.path.isdir(env_dir):
        return Path(env_dir).resolve()
    
    # 1. Pastas internas do repositório (ideal para GitHub e deploy em nuvem)
    for folder_name in ["data", "database", "DATA BASE"]:
        local_dir = (Path(root_dir) / folder_name).resolve()
        if local_dir.is_dir() and (list(local_dir.glob("*.gpkg")) or list(local_dir.glob("*.GPKG"))):
            return local_dir
    
    # 2. Caminho relativo irmão (..\DATA BASE)
    sibling = (Path(root_dir).parent / "DATA BASE").resolve()
    if sibling.is_dir() and (list(sibling.glob("*.gpkg")) or list(sibling.glob("*.GPKG"))):
        return sibling

    # 3. Caminho padrão local absoluto
    fixed_path = Path(r"K:\0. CURSOS\WebGIS\EXERCICIOS\DATA BASE")
    if fixed_path.is_dir():
        return fixed_path

    local_fallback = (Path(root_dir) / "data").resolve()
    local_fallback.mkdir(exist_ok=True)
    return local_fallback

def generate_layer_id(file_name: str, layer_name: str) -> str:
    """Gera um identificador seguro e determinístico para a camada."""
    raw = f"{file_name}::{layer_name}"
    md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{Path(file_name).stem}_{layer_name}")[:30].strip("_")
    return f"{slug}_{md5}"

def scan_database_layers():
    """Escaneia a pasta do banco de dados e atualiza o registro de camadas."""
    import pyogrio

    db_dir = get_database_dir()
    layers = []
    _layer_registry.clear()

    if not db_dir.is_dir():
        return layers

    # Localiza arquivos .gpkg e .GPKG
    gpkg_files = sorted(list(db_dir.glob("*.gpkg")) + [f for f in db_dir.glob("*.GPKG") if f not in db_dir.glob("*.gpkg")])

    for gpkg_path in gpkg_files:
        try:
            raw_layers = pyogrio.list_layers(str(gpkg_path))
            for raw_layer in raw_layers:
                layer_name = str(raw_layer[0])
                try:
                    info = pyogrio.read_info(str(gpkg_path), layer=layer_name)
                    geom_type = str(info.get("geometry_type", "Unknown"))
                    features_count = int(info.get("features", 0))
                    crs = str(info.get("crs", "EPSG:4326"))
                    total_bounds = info.get("total_bounds") # (minx, miny, maxx, maxy)
                    
                    bounds = None
                    if total_bounds is not None and len(total_bounds) == 4:
                        # Para Leaflet: [[min_lat, min_lon], [max_lat, max_lon]]
                        minx, miny, maxx, maxy = total_bounds
                        bounds = [
                            [float(miny), float(minx)],
                            [float(maxy), float(maxx)]
                        ]
                except Exception as e:
                    geom_type = "Unknown"
                    features_count = 0
                    crs = "Unknown"
                    bounds = None

                layer_id = generate_layer_id(gpkg_path.name, layer_name)
                
                # Registra camada internamente
                _layer_registry[layer_id] = {
                    "id": layer_id,
                    "filepath": str(gpkg_path),
                    "filename": gpkg_path.name,
                    "layer_name": layer_name,
                    "display_name": layer_name if layer_name != gpkg_path.stem else gpkg_path.stem,
                    "geometry_type": geom_type,
                    "features_count": features_count,
                    "crs": crs,
                    "bounds": bounds,
                    "mtime": gpkg_path.stat().st_mtime
                }

                layers.append({
                    "id": layer_id,
                    "filename": gpkg_path.name,
                    "layer_name": layer_name,
                    "display_name": layer_name if layer_name != gpkg_path.stem else gpkg_path.stem,
                    "geometry_type": geom_type,
                    "features_count": features_count,
                    "crs": crs,
                    "bounds": bounds
                })
        except Exception as err:
            app.logger.error(f"Erro ao ler camadas de {gpkg_path.name}: {err}")

    return layers

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "application": "WebGIS Vertical Green",
        "database_dir": str(get_database_dir())
    })

@app.route("/api/database/info")
def database_info():
    db_dir = get_database_dir()
    exists = db_dir.is_dir()
    gpkg_count = len(list(db_dir.glob("*.gpkg"))) if exists else 0
    return jsonify({
        "database_dir": str(db_dir),
        "exists": exists,
        "gpkg_count": gpkg_count
    })

@app.route("/api/database/layers")
def list_database_layers():
    """Retorna a lista de todas as camadas encontradas nos arquivos GeoPackage."""
    layers = scan_database_layers()
    return jsonify({
        "status": "ok",
        "database_dir": str(get_database_dir()),
        "count": len(layers),
        "layers": layers
    })

@app.route("/api/database/layers/<layer_id>/geojson")
def get_layer_geojson(layer_id):
    """Retorna o GeoJSON de uma camada específica com cache em memória."""
    import geopandas as gpd

    # Se não estiver no registro, faz um novo escaneamento
    if layer_id not in _layer_registry:
        scan_database_layers()

    if layer_id not in _layer_registry:
        abort(404, description=f"Camada '{layer_id}' não encontrada no banco de dados.")

    layer_meta = _layer_registry[layer_id]
    gpkg_file = Path(layer_meta["filepath"])
    layer_name = layer_meta["layer_name"]

    if not gpkg_file.exists():
        abort(404, description=f"Arquivo GeoPackage '{gpkg_file.name}' não encontrado.")

    current_mtime = gpkg_file.stat().st_mtime

    # Verifica cache
    if layer_id in _cache_geojson:
        cached = _cache_geojson[layer_id]
        if cached["mtime"] == current_mtime:
            return Response(cached["geojson"], mimetype="application/json")

    try:
        # Lê a camada do GeoPackage
        gdf = gpd.read_file(gpkg_file, layer=layer_name)

        # Garante projeção WGS84 (EPSG:4326) para o Leaflet
        if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        # Serializa para GeoJSON
        geojson_str = gdf.to_json()

        # Armazena em cache
        _cache_geojson[layer_id] = {
            "mtime": current_mtime,
            "geojson": geojson_str
        }

        return Response(geojson_str, mimetype="application/json")
    except Exception as e:
        app.logger.error(f"Erro ao converter camada {layer_id} para GeoJSON: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
