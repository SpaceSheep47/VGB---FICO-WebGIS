#!/usr/bin/env python3
"""Envia panoramas para Cloudflare R2 e gera um índice JSON consumido pelo WebGIS.

Variáveis de ambiente obrigatórias:
  R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID=...
  R2_SECRET_ACCESS_KEY=...
  R2_BUCKET=vgb-fico
  R2_PUBLIC_BASE_URL=https://<dominio-publico>

Exemplo:
  python scripts/sync_panoramas_r2.py --source data/panoramas
"""
import argparse
import hashlib
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from PIL import Image

EXTENSIONS = {".jpg", ".jpeg", ".webp", ".png"}


def rational(v):
    try:
        return float(v)
    except Exception:
        try:
            return v.numerator / v.denominator
        except Exception:
            return float(str(v))


def dms(values, ref):
    if not values or len(values) < 3:
        return None
    out = rational(values[0]) + rational(values[1]) / 60 + rational(values[2]) / 3600
    if str(ref).upper() in {"S", "W"}:
        out *= -1
    return out


def read_metadata(path: Path):
    with Image.open(path) as image:
        exif = image.getexif()
        gps = exif.get_ifd(0x8825) if exif else {}
        lat = dms(gps.get(2), gps.get(1)) if gps else None
        lon = dms(gps.get(4), gps.get(3)) if gps else None
        altitude = rational(gps.get(6)) if gps and gps.get(6) is not None else None
        if gps and gps.get(5) == 1 and altitude is not None:
            altitude *= -1
        width, height = image.width, image.height

    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")

    def num(name):
        m = re.search(r'(?:GPano:|GImage:|xmp:)?' + re.escape(name) + r'\s*=\s*["\']([^"\']+)["\']', text, re.I)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    has_gpano = bool(re.search(r'GPano:', text, re.I) or re.search(r'http://ns\.google\.com/photos/1\.0/panorama/', text))
    probable = has_gpano or (width >= 2000 and height > 0 and 1.80 <= width / height <= 2.20)
    if not probable or lat is None or lon is None:
        return None

    return {
        "latitude": lat,
        "longitude": lon,
        "altitude": altitude,
        "heading": num("PoseHeadingDegrees"),
        "pitch": num("PosePitchDegrees"),
        "roll": num("PoseRollDegrees"),
        "width": width,
        "height": height,
        "detection": "GPano/XMP" if has_gpano else "proporção 2:1",
    }


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Variável obrigatória ausente: {name}")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/panoramas", help="Pasta local com as fotografias 360°")
    parser.add_argument("--prefix", default="panoramas", help="Prefixo dentro do bucket R2")
    parser.add_argument("--delete", action="store_true", help="Remove do R2 objetos de panorama que não existem mais localmente")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_dir():
        raise SystemExit(f"Pasta não encontrada: {source}")

    endpoint = env("R2_ENDPOINT_URL")
    access_key = env("R2_ACCESS_KEY_ID")
    secret_key = env("R2_SECRET_ACCESS_KEY")
    bucket = env("R2_BUCKET")
    public_base = env("R2_PUBLIC_BASE_URL").rstrip("/")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )

    items = []
    local_keys = set()
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)

    for path in files:
        try:
            meta = read_metadata(path)
        except Exception as exc:
            print(f"[AVISO] Não foi possível ler {path.name}: {exc}")
            continue
        if meta is None:
            print(f"[IGNORADO] Não parece ser panorama 360° georreferenciado: {path.name}")
            continue

        rel = path.relative_to(source).as_posix()
        key = f"{args.prefix.strip('/')}/{rel}"
        local_keys.add(key)
        object_url = f"{public_base}/{key}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        metadata = {k: str(v) for k, v in meta.items() if v is not None}
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "public,max-age=31536000,immutable",
                "Metadata": metadata,
            },
        )
        print(f"[OK] {rel} -> {object_url}")

        items.append({
            "id": digest,
            "name": path.stem,
            "filename": path.name,
            "path": rel,
            "url": object_url,
            **meta,
        })

    items.sort(key=lambda x: (x["latitude"], x["longitude"], x["filename"].lower()))
    manifest = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "cloudflare-r2",
        "count": len(items),
        "items": items,
    }

    manifest_key = f"{args.prefix.strip('/')}/index.json"
    body = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public,max-age=60",
    )
    print(f"[OK] Índice: {public_base}/{manifest_key}")

    if args.delete:
        paginator = s3.get_paginator("list_objects_v2")
        prefix = args.prefix.strip("/") + "/"
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key == manifest_key or key not in local_keys:
                    s3.delete_object(Bucket=bucket, Key=key)
                    print(f"[REMOVIDO] {key}")


if __name__ == "__main__":
    main()
