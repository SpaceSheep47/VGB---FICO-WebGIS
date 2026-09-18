# WebGIS Goiás — versão otimizada

Portal WebGIS local em Python/Flask + Leaflet, otimizado para carregamento rápido e navegação dentro dos limites do Estado de Goiás.

## Principais alterações

### 1. Restrição geográfica para Goiás
O mapa utiliza:
- `maxBounds` para impedir navegação fora de Goiás;
- enquadramento inicial no Estado;
- limites de zoom adequados ao território estadual.

A restrição é feita no cliente, evitando consultas geográficas pesadas de grandes áreas.

### 2. Arquitetura baseada em tiles
A aplicação não baixa uma camada vetorial nacional inteira. Os mapas são carregados conforme o usuário navega, por tiles XYZ:

- OpenStreetMap — mapa base;
- Esri World Imagery — imagem de satélite;
- Esri World Transportation — sobreposição de transporte/rodovias.

Isso reduz significativamente o volume inicial de dados.

### 3. Satélite
Foi utilizado o **Esri World Imagery** em vez de um endpoint não oficial do Google. Isso evita depender de URLs de tiles do Google não documentadas para aplicações de terceiros.

### 4. Dark mode
O portal possui um botão de tema claro/escuro. A preferência é persistida no navegador com `localStorage`.

### 5. Banco de Dados GeoPackage (.gpkg)
O WebGIS agora conta com leitura automática de banco de dados geoespacial local (`data/` ou `DATA BASE/`):
- **Eixo da Ferrovia (FICO)**: Camada linear estilizada com traçado contínuo em carmim ferroviário, cálculo automático de extensão (~363,8 km), realce em hover e popup detalhado de atributos.
- **ESTACA CHEIA (Estacas Quilométricas)**: 365 pontos georreferenciados ao longo do traçado com tooltips do piquete/estaca (`0+000`, `1+000`, etc.), realce visual e popup com coordenadas geográficas completas e altitude.
- **Controle de Camadas**: Painel dedicado na barra lateral com ativação/desativação individual, badges por tipo de feição, botão de zoom individual `⌕` e botão de recarregar banco `↻`.
- **Botão de Enquadramento Global (`🚂`)**: Na barra superior, permite enquadrar imediatamente todo o projeto ferroviário no território goiano.

### 6. Ferramentas de Desenho e Medição
- **Criação de Pontos**: Permite posicionar pontos no mapa atribuindo um nome personalizado. O nome é exibido de forma permanente diretamente sobre o ponto em um rótulo estilizado, com popup informativo com coordenadas e opções de exclusão e renomeação.
- **Criação de Polígonos**: Permite desenhar áreas e polígonos clicando nos vértices (mínimo de 3). O nome é exibido de forma permanente diretamente no centro do polígono sobreposto no mapa. Inclui cálculo geodésico de área (em m² ou hectares) e perímetro (em m ou km).
- **Medição de Distância**: Ferramenta linear para calcular distâncias entre pontos com indicação em metros ou quilômetros.
- **Identidade Visual Vertical Green**: Cores temáticas oficiais (verde institucional florestal `#063231` e verde lima `#cbff54`), logotipo SVG de alta definição e favicon da empresa.

### 7. Outros recursos
- busca de endereço/localidade;
- localização do usuário;
- controle de camadas;
- coordenadas do cursor e nível de zoom;
- tema claro e tema escuro com persistência via `localStorage`;
- interface responsiva e moderna.

## Inicialização

Execute `start.bat`.

Na primeira execução, o script:
1. cria `.venv`;
2. instala Flask;
3. inicia o servidor;
4. abre o navegador em `http://127.0.0.1:5000`.

## Fontes de tiles

OpenStreetMap:
https://tile.openstreetmap.org/{z}/{x}/{y}.png

Esri World Imagery:
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}

Esri World Transportation:
https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}

## Observação

Os limites do mapa são os limites operacionais do Estado de Goiás definidos para a interface. A camada de transporte é mundial, porém apenas tiles visíveis dentro de Goiás podem ser acessados durante a navegação devido ao `maxBounds`.

Para um WebGIS institucional de produção, recomenda-se posteriormente hospedar/cachear tiles próprios e disponibilizar um recorte oficial do limite estadual de Goiás em servidor GIS próprio.
