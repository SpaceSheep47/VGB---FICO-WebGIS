import os
import sys
import glob
import hashlib
import re
import json
import mimetypes
import time
import urllib.request
from pathlib import Path

from flask import Flask, render_template, jsonify, Response, abort, send_file, request, redirect

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

# Cache da indexação de panoramas
_panorama_cache = {
    "signature": None,
    "items": [],
    "remote_fetched_at": 0.0
}

PANORAMA_EXTENSIONS = {".jpg", ".jpeg", ".webp", ".png"}


def get_database_dir() -> Path:
    """Retorna o caminho absoluto do diretório do banco de dados contendo os arquivos .gpkg."""
    env_dir = os.environ.get("DATABASE_DIR")
    if env_dir and os.path.isdir(env_dir):
        return Path(env_dir).resolve()

    # 1. Pastas internas do repositório
    for folder_name in ["data", "database", "DATA BASE"]:
        local_dir = (Path(root_dir) / folder_name).resolve()
        if local_dir.is_dir() and (
            list(local_dir.glob("*.gpkg")) or list(local_dir.glob("*.GPKG"))
        ):
            return local_dir

    # 2. Caminho relativo irmão (..\DATA BASE)
    sibling = (Path(root_dir).parent / "DATA BASE").resolve()
    if sibling.is_dir() and (
        list(sibling.glob("*.gpkg")) or list(sibling.glob("*.GPKG"))
    ):
        return sibling

    # 3. Caminho padrão local absoluto
    fixed_path = Path(r"K:\0. CURSOS\WebGIS\EXERCICIOS\DATA BASE")
    if fixed_path.is_dir():
        return fixed_path

    local_fallback = (Path(root_dir) / "data").resolve()
    local_fallback.mkdir(exist_ok=True)
    return local_fallback


def get_panorama_roots():
    """
    Retorna os diretórios onde o indexador procura fotografias 360°.

    Prioridade:
    1. PANORAMA_DIR (pode apontar para qualquer pasta)
    2. data/panoramas
    3. data/photos360
    4. data/fotos360
    5. data
    6. DATA BASE
    7. DATABASE_DIR
    """
    candidates = []

    env_dir = os.environ.get("PANORAMA_DIR")
    if env_dir:
        candidates.extend(
            Path(part.strip()).resolve()
            for part in env_dir.split(os.pathsep)
            if part.strip()
        )

    for rel in [
        "data/panoramas",
        "data/photos360",
        "data/fotos360",
        "data",
        "DATA BASE",
        "database",
    ]:
        candidates.append((Path(root_dir) / rel).resolve())

    candidates.append(get_database_dir().resolve())

    roots = []
    seen = set()
    for path in candidates:
        if path.is_dir() and path not in seen:
            roots.append(path)
            seen.add(path)
    return roots


def generate_layer_id(file_name: str, layer_name: str) -> str:
    """Gera um identificador seguro e determinístico para a camada."""
    raw = f"{file_name}::{layer_name}"
    md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        f"{Path(file_name).stem}_{layer_name}"
    )[:30].strip("_")
    return f"{slug}_{md5}"


def scan_database_layers():
    """Escaneia a pasta do banco de dados e atualiza o registro de camadas."""
    import pyogrio

    db_dir = get_database_dir()
    layers = []
    _layer_registry.clear()

    if not db_dir.is_dir():
        return layers

    gpkg_files = sorted(
        list(db_dir.glob("*.gpkg"))
        + [
            f for f in db_dir.glob("*.GPKG")
            if f not in db_dir.glob("*.gpkg")
        ]
    )

    for gpkg_path in gpkg_files:
        try:
            raw_layers = pyogrio.list_layers(str(gpkg_path))
            for raw_layer in raw_layers:
                layer_name = str(raw_layer[0])
                try:
                    info = pyogrio.read_info(
                        str(gpkg_path),
                        layer=layer_name
                    )
                    geom_type = str(info.get("geometry_type", "Unknown"))
                    features_count = int(info.get("features", 0))
                    crs = str(info.get("crs", "EPSG:4326"))
                    total_bounds = info.get("total_bounds")

                    bounds = None
                    if total_bounds is not None and len(total_bounds) == 4:
                        minx, miny, maxx, maxy = total_bounds
                        bounds = [
                            [float(miny), float(minx)],
                            [float(maxy), float(maxx)]
                        ]
                except Exception:
                    geom_type = "Unknown"
                    features_count = 0
                    crs = "Unknown"
                    bounds = None

                layer_id = generate_layer_id(gpkg_path.name, layer_name)

                _layer_registry[layer_id] = {
                    "id": layer_id,
                    "filepath": str(gpkg_path),
                    "filename": gpkg_path.name,
                    "layer_name": layer_name,
                    "display_name": (
                        layer_name
                        if layer_name != gpkg_path.stem
                        else gpkg_path.stem
                    ),
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
                    "display_name": (
                        layer_name
                        if layer_name != gpkg_path.stem
                        else gpkg_path.stem
                    ),
                    "geometry_type": geom_type,
                    "features_count": features_count,
                    "crs": crs,
                    "bounds": bounds
                })
        except Exception as err:
            app.logger.error(
                f"Erro ao ler camadas de {gpkg_path.name}: {err}"
            )

    return layers


# ---------------------------------------------------------------------------
# PANORAMAS 360°
# ---------------------------------------------------------------------------

def panorama_source_mode():
    return os.environ.get("PANORAMA_SOURCE", "local").strip().lower()

def remote_panorama_index_url():
    return os.environ.get("PANORAMA_INDEX_URL", "").strip()

def scan_remote_panoramas(force=False):
    """Carrega o índice JSON público das fotografias hospedadas na nuvem."""
    url = remote_panorama_index_url()
    if not url:
        app.logger.warning("PANORAMA_SOURCE=remote, mas PANORAMA_INDEX_URL não foi definido.")
        return []

    now = time.time()
    ttl = int(os.environ.get("PANORAMA_REMOTE_CACHE_SECONDS", "300"))
    if (
        not force
        and _panorama_cache["items"]
        and now - _panorama_cache["remote_fetched_at"] < ttl
    ):
        return _panorama_cache["items"]

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "VGB-FICO-WebGIS/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        items = payload.get("items", payload if isinstance(payload, list) else [])
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("latitude") is None or item.get("longitude") is None:
                continue
            if not item.get("url"):
                continue
            normalized.append(dict(item))

        normalized.sort(
            key=lambda item: (
                float(item.get("latitude", 0)),
                float(item.get("longitude", 0)),
                str(item.get("filename", item.get("name", ""))).lower()
            )
        )
        _panorama_cache["items"] = normalized
        _panorama_cache["remote_fetched_at"] = now
        return normalized
    except Exception as exc:
        app.logger.error("Falha ao carregar índice remoto de panoramas: %s", exc)
        return []


def _rational_to_float(value):
    try:
        return float(value)
    except Exception:
        try:
            return value.numerator / value.denominator
        except Exception:
            return float(str(value))


def _dms_to_decimal(values, ref):
    if not values or len(values) < 3:
        return None
    d = _rational_to_float(values[0])
    m = _rational_to_float(values[1])
    s = _rational_to_float(values[2])
    decimal = d + (m / 60.0) + (s / 3600.0)
    if str(ref).upper() in {"S", "W"}:
        decimal *= -1
    return decimal


def _read_exif_metadata(path: Path):
    """Lê GPS/heading básicos do EXIF sem exigir ExifTool."""
    try:
        from PIL import Image
        with Image.open(path) as image:
            exif = image.getexif()
            gps = exif.get_ifd(0x8825) if exif else {}

            lat = _dms_to_decimal(
                gps.get(2),
                gps.get(1)
            ) if gps else None
            lon = _dms_to_decimal(
                gps.get(4),
                gps.get(3)
            ) if gps else None

            altitude = None
            if gps and gps.get(6) is not None:
                altitude = _rational_to_float(gps.get(6))
                if gps.get(5) == 1:
                    altitude *= -1

            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": altitude,
                "width": image.width,
                "height": image.height
            }
    except Exception as exc:
        app.logger.warning(
            "Falha ao ler EXIF de %s: %s",
            path.name,
            exc
        )
        return {
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "width": None,
            "height": None
        }


def _read_xmp(path: Path):
    """
    Extrai campos GPano diretamente do JPEG/WEBP/PNG quando o arquivo
    contém metadados XMP. Não depende do ExifTool.
    """
    try:
        data = path.read_bytes()
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return {}

    def get_number(name):
        pattern = (
            r'(?:GPano:|GImage:|xmp:)?'
            + re.escape(name)
            + r'\s*=\s*["\']([^"\']+)["\']'
        )
        match = re.search(pattern, text, flags=re.I)
        if not match:
            return None
        try:
            return float(match.group(1))
        except Exception:
            return None

    # Procura também o namespace explicitamente para reduzir falsos positivos.
    has_gpano = bool(
        re.search(r'http://ns\.google\.com/photos/1\.0/panorama/', text)
        or re.search(r'GPano:', text, flags=re.I)
    )

    fields = {
        "full_pano_width": get_number("FullPanoWidthPixels"),
        "full_pano_height": get_number("FullPanoHeightPixels"),
        "cropped_area_width": get_number("CroppedAreaImageWidthPixels"),
        "cropped_area_height": get_number("CroppedAreaImageHeightPixels"),
        "cropped_area_left": get_number("CroppedAreaLeftPixels"),
        "cropped_area_top": get_number("CroppedAreaTopPixels"),
        "pose_heading": get_number("PoseHeadingDegrees"),
        "pose_pitch": get_number("PosePitchDegrees"),
        "pose_roll": get_number("PoseRollDegrees"),
    }

    fields["has_gpano"] = has_gpano
    return fields


def _is_probable_panorama(width, height, xmp):
    """
    Identificação conservadora:
    - GPano/XMP explícito => 360°;
    - caso contrário, proporção próxima de 2:1 e resolução horizontal >= 2000.
    """
    if xmp.get("has_gpano"):
        return True, "GPano/XMP"

    if not width or not height or height <= 0:
        return False, "indeterminado"

    ratio = width / height
    if width >= 2000 and 1.80 <= ratio <= 2.20:
        return True, "proporção 2:1"

    return False, "não identificado"


def _panorama_signature(roots):
    entries = []
    for root in roots:
        try:
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in PANORAMA_EXTENSIONS:
                    try:
                        stat = path.stat()
                        entries.append(
                            (
                                str(path.resolve()),
                                stat.st_mtime_ns,
                                stat.st_size
                            )
                        )
                    except OSError:
                        pass
        except OSError:
            pass
    entries.sort()
    return hashlib.sha1(
        json.dumps(entries, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def scan_panoramas(force=False):
    """Indexa fotografias 360° e retorna apenas as que possuem GPS."""
    roots = get_panorama_roots()
    signature = _panorama_signature(roots)

    if (
        not force
        and _panorama_cache["signature"] == signature
    ):
        return _panorama_cache["items"]

    items = []

    for root in roots:
        try:
            files = root.rglob("*")
        except OSError:
            continue

        for path in files:
            if (
                not path.is_file()
                or path.suffix.lower() not in PANORAMA_EXTENSIONS
            ):
                continue

            try:
                exif = _read_exif_metadata(path)
                xmp = _read_xmp(path)
                is_pano, detection = _is_probable_panorama(
                    exif["width"],
                    exif["height"],
                    xmp
                )

                if not is_pano:
                    continue

                if (
                    exif["latitude"] is None
                    or exif["longitude"] is None
                ):
                    # Sem GPS a foto pode ser aberta por URL, mas não pode
                    # ser posicionada automaticamente no mapa.
                    continue

                rel_path = path.relative_to(root).as_posix()

                items.append({
                    "id": hashlib.sha1(
                        str(path.resolve()).encode("utf-8")
                    ).hexdigest()[:16],
                    "name": path.stem,
                    "filename": path.name,
                    "path": rel_path,
                    "url": "/api/panoramas/file/"
                          + hashlib.sha1(
                              str(path.resolve()).encode("utf-8")
                          ).hexdigest()[:16],
                    "latitude": exif["latitude"],
                    "longitude": exif["longitude"],
                    "altitude": exif["altitude"],
                    "heading": xmp.get("pose_heading"),
                    "pitch": xmp.get("pose_pitch"),
                    "roll": xmp.get("pose_roll"),
                    "width": exif["width"],
                    "height": exif["height"],
                    "detection": detection,
                    "source_root": str(root)
                })

            except Exception as exc:
                app.logger.warning(
                    "Falha ao indexar panorama %s: %s",
                    path,
                    exc
                )

    # Ordenação geográfica/alfabética previsível.
    items.sort(
        key=lambda item: (
            item["latitude"],
            item["longitude"],
            item["filename"].lower()
        )
    )

    _panorama_cache["signature"] = signature
    _panorama_cache["items"] = items
    return items


def _find_panorama_by_id(panorama_id):
    for item in scan_panoramas():
        if item["id"] == panorama_id:
            return item
    return None


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

    if layer_id not in _layer_registry:
        scan_database_layers()

    if layer_id not in _layer_registry:
        abort(
            404,
            description=f"Camada '{layer_id}' não encontrada no banco de dados."
        )

    layer_meta = _layer_registry[layer_id]
    gpkg_file = Path(layer_meta["filepath"])
    layer_name = layer_meta["layer_name"]

    if not gpkg_file.exists():
        abort(
            404,
            description=f"Arquivo GeoPackage '{gpkg_file.name}' não encontrado."
        )

    current_mtime = gpkg_file.stat().st_mtime

    if layer_id in _cache_geojson:
        cached = _cache_geojson[layer_id]
        if cached["mtime"] == current_mtime:
            return Response(
                cached["geojson"],
                mimetype="application/json"
            )

    try:
        gdf = gpd.read_file(
            gpkg_file,
            layer=layer_name
        )

        if (
            gdf.crs is not None
            and str(gdf.crs).upper() != "EPSG:4326"
        ):
            gdf = gdf.to_crs("EPSG:4326")

        geojson_str = gdf.to_json()

        _cache_geojson[layer_id] = {
            "mtime": current_mtime,
            "geojson": geojson_str
        }

        return Response(
            geojson_str,
            mimetype="application/json"
        )
    except Exception as e:
        app.logger.error(
            f"Erro ao converter camada {layer_id} para GeoJSON: {e}"
        )
        return jsonify({"error": str(e)}), 500


@app.route("/api/panoramas")
def list_panoramas():
    """Retorna as fotografias 360° locais ou hospedadas na nuvem."""
    force = request_bool("refresh")
    if panorama_source_mode() in {"remote", "cloud", "r2"}:
        items = scan_remote_panoramas(force=force)
        source = "remote"
    else:
        items = scan_panoramas(force=force)
        source = "local"

    public_items = []
    for item in items:
        public_item = dict(item)
        public_item.pop("source_root", None)
        public_items.append(public_item)

    return jsonify({
        "status": "ok",
        "source": source,
        "count": len(public_items),
        "items": public_items
    })


@app.route("/api/panoramas/file/<panorama_id>")
def panorama_file(panorama_id):
    """Entrega/encaminha uma fotografia 360° já indexada."""
    if panorama_source_mode() in {"remote", "cloud", "r2"}:
        item = next(
            (x for x in scan_remote_panoramas() if x.get("id") == panorama_id),
            None
        )
        if item is None or not item.get("url"):
            abort(404, description="Panorama não encontrado.")
        return redirect(item["url"], code=302)

    item = _find_panorama_by_id(panorama_id)

    if item is None:
        abort(404, description="Panorama não encontrado.")

    path = None
    for root in get_panorama_roots():
        candidate = (root / item["path"]).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            path = candidate
            break

    if path is None:
        abort(404, description="Arquivo do panorama não encontrado.")

    mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return send_file(
        path,
        mimetype=mimetype,
        conditional=True,
        max_age=86400
    )


def request_bool(name):
    value = str(request.args.get(name, "")).lower()
    return value in {"1", "true", "yes", "on"}


@app.after_request
def inject_panorama_assets(response):
    """
    Mantém o template index.html intacto: os assets do viewer são injetados
    automaticamente apenas nas respostas HTML da aplicação.
    """
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return response

    try:
        html = response.get_data(as_text=True)
        head_marker = "</head>"
        head_injection = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@photo-sphere-viewer/core@5.15.1/index.min.css">
<link rel="stylesheet" href="/static/panorama-viewer.css">
"""
        # O mapa original é criado em um <script> inline no final do template.
        # O bootstrap abaixo é inserido imediatamente antes desse script para
        # capturar a instância Leaflet antes de L.map() ser chamado.
        script_marker = "<script>\n(function () {"
        bootstrap = """
<script>
(function () {
  if (!window.L || window.__vgPanoramaMapHooked) return;
  window.__vgPanoramaMapHooked = true;

  const originalMapFactory = window.L.map;
  window.L.map = function (...args) {
    const map = originalMapFactory.apply(this, args);
    window.__vgMap = map;

    // Carrega a integração 360° depois que o mapa foi criado.
    import('/static/panorama-viewer.js')
      .then(() => {
        if (window.__vgPanoramaInit) window.__vgPanoramaInit();
      })
      .catch(err => console.error('Falha ao carregar módulo 360°:', err));

    return map;
  };
})();
</script>
"""
        if head_marker in html and "/static/panorama-viewer.css" not in html:
            html = html.replace(head_marker, head_injection + head_marker, 1)

        if script_marker in html and "/static/panorama-viewer.js" not in html:
            html = html.replace(script_marker, bootstrap + "\n" + script_marker, 1)

        response.set_data(html)
    except Exception as exc:
        app.logger.warning("Falha ao injetar assets 360°: %s", exc)

    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
