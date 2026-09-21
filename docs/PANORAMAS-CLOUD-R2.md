# Fotografias 360° na nuvem — Cloudflare R2

Esta implementação separa as fotografias panorâmicas do código do WebGIS.

```text
GitHub / Vercel
├── código Flask
├── Leaflet / Photo Sphere Viewer
└── metadados da aplicação

Cloudflare R2
└── panoramas/
    ├── 0001.jpg
    ├── 0002.jpg
    ├── 0003.jpg
    └── index.json
```

## 1. Criar o bucket

No Cloudflare, crie um bucket R2, por exemplo `vgb-fico`.

Configure uma URL pública para o bucket. Para produção, prefira um domínio próprio. O domínio público deve permitir que o navegador carregue os JPGs e o `index.json`.

## 2. Criar as credenciais S3 do R2

Crie uma API Token do R2 com permissão de leitura e escrita no bucket. Nunca coloque `R2_ACCESS_KEY_ID` ou `R2_SECRET_ACCESS_KEY` dentro do JavaScript, HTML ou repositório público.

## 3. Configurar o ambiente do script de sincronização

Copie `.env.r2.example` para um arquivo local de configuração e preencha:

- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`
- `R2_PUBLIC_BASE_URL`

As credenciais são usadas somente pelo script de sincronização. O navegador não recebe essas credenciais.

## 4. Instalar dependências

```bash
pip install -r requirements.txt
```

## 5. Enviar as fotografias

Coloque as imagens em:

```text
data/panoramas/
```

Depois execute:

```bash
python scripts/sync_panoramas_r2.py --source data/panoramas
```

O script:

1. encontra JPG/JPEG/WEBP/PNG;
2. verifica se parecem panoramas 360°;
3. lê GPS e metadados GPano/XMP;
4. ignora imagens sem coordenadas;
5. envia as imagens ao R2;
6. gera `panoramas/index.json`;
7. atualiza o índice usado pelo WebGIS.

Para remover do R2 os arquivos que não existem mais localmente:

```bash
python scripts/sync_panoramas_r2.py --source data/panoramas --delete
```

Use `--delete` com cuidado.

## 6. Configurar o WebGIS

No ambiente de produção (por exemplo, variáveis do Vercel), configure:

```text
PANORAMA_SOURCE=remote
PANORAMA_INDEX_URL=https://SEU_DOMINIO_PUBLICO/panoramas/index.json
PANORAMA_REMOTE_CACHE_SECONDS=300
```

O endpoint existente:

```text
GET /api/panoramas
```

passará a devolver os panoramas do índice remoto, mantendo o mesmo formato usado pelo Photo Sphere Viewer.

O frontend não precisa conhecer as credenciais do R2.

## 7. Resultado

Ao abrir o WebGIS:

```text
WebGIS
  ↓
/api/panoramas
  ↓
index.json no R2
  ↓
marcadores no mapa
  ↓
clique no marcador
  ↓
Photo Sphere Viewer
  ↓
JPG diretamente do R2
```

O servidor Flask não precisa fazer proxy da fotografia. Isso reduz consumo de CPU, RAM e banda da aplicação.

## 8. Recomendações de segurança

- Não faça commit das credenciais do R2.
- Use variáveis de ambiente no Vercel/servidor.
- Mantenha o bucket de imagens público somente para leitura.
- Mantenha a API token do R2 privada.
- Se as fotografias forem privadas, a arquitetura deve ser alterada para URLs assinadas (presigned URLs).

## 9. Próxima evolução: panoramas tiled

Para panoramas muito grandes, a próxima etapa recomendada é gerar versões multi-resolution/tiled. Nesse modelo o Photo Sphere Viewer baixa somente os tiles necessários, em vez de baixar o panorama inteiro.
