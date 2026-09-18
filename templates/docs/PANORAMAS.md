# Fotografias 360° no VGB-FICO WebGIS

Esta alteração adiciona um índice automático de fotografias panorâmicas e um
visualizador 360° baseado em **Photo Sphere Viewer**.

## Como funciona

1. O backend Flask procura imagens em:
   - `data/panoramas/`
   - `data/photos360/`
   - `data/fotos360/`
   - `data/`
   - `DATA BASE/`
   - `database/`
   - ou no diretório definido pela variável `PANORAMA_DIR`.

2. O indexador considera como panorama:
   - imagens com metadados Google GPano/XMP; ou
   - imagens com proporção aproximadamente 2:1 e largura mínima de 2000 px.

3. Para aparecer no mapa, a fotografia também precisa possuir latitude e
   longitude no EXIF.

4. O endpoint `/api/panoramas` retorna os panoramas georreferenciados.

5. O endpoint `/api/panoramas/file/<id>` entrega a imagem somente depois que
   ela foi indexada, evitando expor caminhos arbitrários do servidor.

6. O frontend cria marcadores específicos para as fotos 360°. Ao clicar em
   um marcador, abre um modal com o Photo Sphere Viewer.

## Estrutura recomendada

```text
data/
└── panoramas/
    ├── FICO_0001.jpg
    ├── FICO_0002.jpg
    └── FICO_0003.jpg
```

Não é necessário cadastrar manualmente cada fotografia.

## Metadados recomendados

O ideal é que as fotografias contenham:

- GPS Latitude;
- GPS Longitude;
- altitude, se disponível;
- `GPano` / XMP;
- `PoseHeadingDegrees`, quando a câmera registrar orientação.

O heading é utilizado para tentar abrir o panorama já apontando na direção
registrada pela câmera.

## Variável PANORAMA_DIR

Para manter as fotografias fora do repositório:

### Windows

```bat
set PANORAMA_DIR=K:\Projeto\Fotos360
```

Para múltiplas pastas, use `;`:

```bat
set PANORAMA_DIR=K:\Projeto\Fotos360;D:\Fotos360
```

### Linux

```bash
export PANORAMA_DIR=/srv/fico/panoramas
```

## Desempenho

A implementação inicial trabalha com a imagem equiretangular original.
Para fotografias muito grandes, recomenda-se posteriormente gerar panoramas
em tiles multirresolução e utilizar o `EquirectangularTilesAdapter` do Photo
Sphere Viewer.

O Photo Sphere Viewer oferece suporte oficial a panoramas equiretangulares,
tiles e plugins, incluindo navegação entre panoramas. Consulte:

https://photo-sphere-viewer.js.org/

## CDN

O viewer é carregado pelo frontend via jsDelivr. Isso evita adicionar uma
árvore `node_modules` ao repositório atual, que é uma aplicação Flask/Leaflet.

Versão utilizada nesta implementação: `@photo-sphere-viewer/core@5.15.1`.

## Teste rápido

Coloque uma foto 360° georreferenciada em:

```text
data/panoramas/teste.jpg
```

Execute:

```bat
start.bat
```

Abra o WebGIS e procure o marcador circular de fotografia 360°.

## Observação sobre GitHub/Vercel

As fotografias 360° normalmente são arquivos grandes e não devem ser
incluídas no Git sem necessidade. Para produção, prefira armazenamento de
objetos/CDN ou um diretório de dados montado no servidor.

O backend aceita `PANORAMA_DIR`, permitindo separar o código das imagens.

## Integração com a interface existente

O template `templates/index.html` permanece sem alterações. O backend injeta o CSS e um pequeno bootstrap antes do script que cria o mapa Leaflet, captura a instância do mapa e então carrega o módulo 360°. Isso mantém o PR concentrado nos arquivos da funcionalidade.
