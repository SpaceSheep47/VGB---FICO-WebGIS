/*
 * VGB-FICO WebGIS — visualização de fotografias 360°
 *
 * O módulo é carregado como ES Module e usa Photo Sphere Viewer via jsDelivr.
 * A camada de mapa continua sendo Leaflet; o viewer é aberto em um modal
 * independente quando o usuário clica em um ponto de panorama.
 */

const PSV_CORE = 'https://cdn.jsdelivr.net/npm/@photo-sphere-viewer/core@5.15.1/index.module.js';

const panoramaState = {
  items: [],
  markers: [],
  viewer: null,
  currentIndex: -1,
  initialized: false,
};

const iconSvg = `
<svg viewBox="0 0 32 32" aria-hidden="true">
  <circle cx="16" cy="16" r="13" fill="#063231" stroke="#cbff54" stroke-width="3"/>
  <circle cx="16" cy="16" r="5" fill="#ffffff"/>
  <path d="M7 12h18M9 9h14" fill="none" stroke="#cbff54" stroke-width="2" stroke-linecap="round"/>
</svg>`;

function ensureUi() {
  if (document.getElementById('panoramaViewerModal')) return;

  const modal = document.createElement('div');
  modal.id = 'panoramaViewerModal';
  modal.className = 'panorama-modal hidden';

  modal.innerHTML = `
    <div class="panorama-modal-backdrop" data-pano-close></div>
    <section class="panorama-modal-panel" role="dialog" aria-modal="true"
             aria-labelledby="panoramaViewerTitle">
      <header class="panorama-modal-header">
        <div class="panorama-modal-heading">
          <span class="panorama-modal-icon">${iconSvg}</span>
          <div>
            <div id="panoramaViewerTitle" class="panorama-modal-title">Foto 360°</div>
            <div id="panoramaViewerMeta" class="panorama-modal-meta"></div>
          </div>
        </div>
        <div class="panorama-modal-actions">
          <button type="button" id="panoramaPrev" class="panorama-action-btn"
                  title="Panorama anterior" aria-label="Panorama anterior">‹</button>
          <button type="button" id="panoramaNext" class="panorama-action-btn"
                  title="Próximo panorama" aria-label="Próximo panorama">›</button>
          <button type="button" id="panoramaFullscreen" class="panorama-action-btn"
                  title="Tela cheia" aria-label="Tela cheia">⛶</button>
          <button type="button" id="panoramaClose" class="panorama-action-btn close"
                  title="Fechar" aria-label="Fechar">×</button>
        </div>
      </header>
      <div id="panoramaViewer" class="panorama-viewer"></div>
      <footer class="panorama-modal-footer">
        <span id="panoramaCounter"></span>
        <span>Arraste para olhar ao redor • roda do mouse para zoom</span>
      </footer>
    </section>
  </div>`;

  document.body.appendChild(modal);

  modal.querySelectorAll('[data-pano-close]').forEach(el => {
    el.addEventListener('click', closeViewer);
  });

  document.getElementById('panoramaClose').addEventListener('click', closeViewer);
  document.getElementById('panoramaPrev').addEventListener('click', () => navigate(-1));
  document.getElementById('panoramaNext').addEventListener('click', () => navigate(1));
  document.getElementById('panoramaFullscreen').addEventListener('click', toggleFullscreen);

  document.addEventListener('keydown', event => {
    const isOpen = !modal.classList.contains('hidden');
    if (!isOpen) return;

    if (event.key === 'Escape') closeViewer();
    if (event.key === 'ArrowLeft') navigate(-1);
    if (event.key === 'ArrowRight') navigate(1);
  });
}

function updateViewerMeta(item) {
  const title = document.getElementById('panoramaViewerTitle');
  const meta = document.getElementById('panoramaViewerMeta');
  const counter = document.getElementById('panoramaCounter');

  if (!item) return;

  title.textContent = item.name || item.filename || 'Foto 360°';

  const coords = `${Number(item.latitude).toFixed(6)}, ${Number(item.longitude).toFixed(6)}`;
  const dimensions = item.width && item.height ? `${item.width} × ${item.height}px` : '';
  meta.textContent = [coords, dimensions].filter(Boolean).join(' • ');

  const current = panoramaState.currentIndex + 1;
  counter.textContent = `${current} / ${panoramaState.items.length}`;
}

async function loadCore() {
  if (panoramaState.core) return panoramaState.core;
  panoramaState.core = await import(PSV_CORE);
  return panoramaState.core;
}

async function createViewer(item) {
  ensureUi();

  const { Viewer } = await loadCore();

  if (panoramaState.viewer) {
    try {
      panoramaState.viewer.destroy();
    } catch (_) {}
    panoramaState.viewer = null;
  }

  const container = document.getElementById('panoramaViewer');

  panoramaState.viewer = new Viewer({
    container,
    panorama: item.url,
    navbar: [
      'zoom',
      'move',
      'download',
      'caption',
      'fullscreen',
    ],
    defaultZoomLvl: 0,
    touchmoveTwoFingers: false,
    mousemove: true,
    loadingImg: undefined,
    caption: item.name || item.filename || 'Foto 360°',
  });

  // Usa a orientação registrada pela câmera quando disponível.
  if (Number.isFinite(Number(item.heading))) {
    try {
      await panoramaState.viewer.rotate({
        yaw: (Number(item.heading) * Math.PI) / 180,
        pitch: Number.isFinite(Number(item.pitch))
          ? (Number(item.pitch) * Math.PI) / 180
          : 0,
      });
    } catch (_) {
      // Algumas versões/câmeras não fornecem uma orientação compatível.
    }
  }

  updateViewerMeta(item);
}

async function openViewer(index) {
  ensureUi();

  if (!panoramaState.items.length) {
    alert('Nenhuma fotografia 360° georreferenciada foi encontrada.');
    return;
  }

  panoramaState.currentIndex =
    (index + panoramaState.items.length) % panoramaState.items.length;

  const item = panoramaState.items[panoramaState.currentIndex];
  const modal = document.getElementById('panoramaViewerModal');

  modal.classList.remove('hidden');
  document.body.classList.add('panorama-open');

  updateNavigationButtons();

  try {
    await createViewer(item);
  } catch (error) {
    console.error('Erro ao abrir panorama:', error);
    document.getElementById('panoramaViewer').innerHTML = `
      <div class="panorama-error">
        <strong>Não foi possível abrir esta fotografia.</strong>
        <small>${escapeHtml(error?.message || 'Erro desconhecido')}</small>
      </div>`;
  }
}

function closeViewer() {
  const modal = document.getElementById('panoramaViewerModal');
  if (!modal) return;

  modal.classList.add('hidden');
  document.body.classList.remove('panorama-open');

  if (panoramaState.viewer) {
    try {
      panoramaState.viewer.destroy();
    } catch (_) {}
    panoramaState.viewer = null;
  }
}

function navigate(delta) {
  if (!panoramaState.items.length) return;

  panoramaState.currentIndex =
    (panoramaState.currentIndex + delta + panoramaState.items.length)
    % panoramaState.items.length;

  openViewer(panoramaState.currentIndex);
}

function updateNavigationButtons() {
  const prev = document.getElementById('panoramaPrev');
  const next = document.getElementById('panoramaNext');

  if (!prev || !next) return;

  const enabled = panoramaState.items.length > 1;
  prev.disabled = !enabled;
  next.disabled = !enabled;
}

async function toggleFullscreen() {
  const panel = document.querySelector('.panorama-modal-panel');
  if (!panel) return;

  if (!document.fullscreenElement) {
    await panel.requestFullscreen?.();
  } else {
    await document.exitFullscreen?.();
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function panoramaIcon() {
  return L.divIcon({
    className: 'panorama-marker-wrapper',
    html: '<div class="panorama-marker" title="Fotografia 360°">' + iconSvg + '</div>',
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -17],
  });
}

function bindMapMarkers(map) {
  panoramaState.markers.forEach(marker => {
    try {
      map.removeLayer(marker);
    } catch (_) {}
  });
  panoramaState.markers = [];

  panoramaState.items.forEach((item, index) => {
    const marker = L.marker([item.latitude, item.longitude], {
      icon: panoramaIcon(),
      keyboard: true,
      title: `Foto 360°: ${item.name || item.filename}`,
      riseOnHover: true,
    });

    marker.bindTooltip(
      `<b>Foto 360°</b><br>${escapeHtml(item.name || item.filename)}`,
      {
        direction: 'top',
        offset: [0, -15],
        className: 'panorama-tooltip',
      }
    );

    marker.on('click', () => openViewer(index));
    marker.addTo(map);
    panoramaState.markers.push(marker);
  });
}

function addSidebarPanel() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar || document.getElementById('panoramaPanel')) return;

  const panel = document.createElement('section');
  panel.id = 'panoramaPanel';
  panel.className = 'panel panorama-sidebar-panel';

  panel.innerHTML = `
    <div class="panel-header-row">
      <div class="panel-title">FOTOGRAFIAS 360°</div>
      <button id="btnReloadPanoramas" class="action-mini-btn"
              title="Reindexar fotografias 360°">↻</button>
    </div>
    <div class="db-status-bar panorama-status-bar">
      <span id="panoramaIndicator" class="db-indicator loading">●</span>
      <span id="panoramaStatusText">Procurando fotografias...</span>
    </div>
    <label class="layer-item panorama-layer-toggle">
      <input id="panoramaToggle" type="checkbox" checked>
      <span class="panorama-legend-dot"></span>
      <span>Exibir pontos 360°</span>
    </label>
    <button id="btnFitPanoramas" class="tool-btn panorama-fit-btn">
      ◉ Enquadrar fotografias 360°
    </button>
  `;

  const dbPanel = sidebar.querySelector('.panel:nth-of-type(2)');
  if (dbPanel) {
    dbPanel.insertAdjacentElement('afterend', panel);
  } else {
    sidebar.insertBefore(panel, sidebar.firstChild);
  }

  document.getElementById('btnReloadPanoramas').addEventListener(
    'click',
    () => loadPanoramas(true)
  );

  document.getElementById('panoramaToggle').addEventListener('change', event => {
    const visible = event.target.checked;
    panoramaState.markers.forEach(marker => {
      if (visible) marker.addTo(window.__vgMap);
      else window.__vgMap.removeLayer(marker);
    });
  });

  document.getElementById('btnFitPanoramas').addEventListener('click', () => {
    if (!panoramaState.items.length) return;

    const bounds = L.latLngBounds(
      panoramaState.items.map(item => [item.latitude, item.longitude])
    );

    window.__vgMap.fitBounds(bounds, {
      padding: [60, 60],
      maxZoom: 15,
    });
  });
}

function updateSidebarStatus() {
  const text = document.getElementById('panoramaStatusText');
  const indicator = document.getElementById('panoramaIndicator');
  if (!text || !indicator) return;

  if (!panoramaState.items.length) {
    text.textContent = 'Nenhuma foto 360° georreferenciada';
    indicator.className = 'db-indicator offline';
    return;
  }

  text.textContent =
    `${panoramaState.items.length} foto${panoramaState.items.length !== 1 ? 's' : ''} 360°`;
  indicator.className = 'db-indicator';
}

async function loadPanoramas(refresh = false) {
  try {
    const url = refresh ? '/api/panoramas?refresh=1' : '/api/panoramas';
    const response = await fetch(url, { cache: 'no-store' });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    panoramaState.items = Array.isArray(data.items) ? data.items : [];

    updateSidebarStatus();
    bindMapMarkers(window.__vgMap);
    updateNavigationButtons();
  } catch (error) {
    console.error('Erro ao carregar fotografias 360°:', error);

    const text = document.getElementById('panoramaStatusText');
    const indicator = document.getElementById('panoramaIndicator');

    if (text) text.textContent = 'Erro ao indexar fotografias';
    if (indicator) indicator.className = 'db-indicator offline';
  }
}

function initPanoramaFeature() {
  if (panoramaState.initialized) return;

  if (!window.L || !window.__vgMap) {
    setTimeout(initPanoramaFeature, 100);
    return;
  }

  panoramaState.initialized = true;
  ensureUi();
  addSidebarPanel();
  loadPanoramas(false);
}


window.__vgPanoramaInit = initPanoramaFeature;
window.__vgPanoramaLoad = loadPanoramas;
window.__vgPanoramaOpen = openViewer;
window.__vgPanoramaState = panoramaState;
