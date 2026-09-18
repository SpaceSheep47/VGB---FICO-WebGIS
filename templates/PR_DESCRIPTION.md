# Pull Request — Visualização de fotografias 360°

## O que foi implementado

- Indexação automática de fotografias 360°.
- Leitura de GPS do EXIF.
- Detecção de metadados GPano/XMP.
- Endpoint `/api/panoramas`.
- Endpoint seguro para servir as fotografias indexadas.
- Marcadores 360° no mapa Leaflet.
- Modal de visualização com Photo Sphere Viewer.
- Leitura de heading/pitch/roll quando disponíveis.
- Navegação anterior/próxima entre fotografias indexadas.
- Botão para enquadrar todas as fotografias.
- Controle de visibilidade da camada 360°.
- Suporte a `PANORAMA_DIR` para manter as fotos fora do repositório.
- Documentação em `docs/PANORAMAS.md`.

## Arquivos

- `api/index.py` — backend e indexação.
- `static/panorama-viewer.js` — integração Leaflet + Photo Sphere Viewer.
- `static/panorama-viewer.css` — interface dos marcadores e viewer.
- `requirements.txt` — adiciona Pillow.
- `docs/PANORAMAS.md` — documentação.

## Observação

O `templates/index.html` não precisa ser substituído. O backend injeta os
assets do viewer nas respostas HTML, reduzindo o tamanho do diff e mantendo
a interface existente.
