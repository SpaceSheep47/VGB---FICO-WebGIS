# VGB-FICO WebGIS — armazenamento de panoramas 360° na nuvem

A integração mantém o WebGIS e suas camadas no GitHub/Vercel e coloca as fotografias 360° no Cloudflare R2.

## Estrutura

```text
VGB-FICO-WebGIS/
├── api/index.py
├── static/
├── scripts/
│   └── sync_panoramas_r2.py
├── data/
│   └── panoramas/          # somente pasta local de origem, opcional
├── .env.r2.example
└── docs/
    └── PANORAMAS-CLOUD-R2.md
```

No R2:

```text
panoramas/
├── foto_001.jpg
├── foto_002.jpg
├── foto_003.jpg
└── index.json
```

O WebGIS lê somente `index.json`. As imagens são carregadas diretamente da URL pública do R2.
