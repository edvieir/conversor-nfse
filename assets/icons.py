"""
assets/icons.py — Ícones SVG inline estilo Feather Icons
Substitui todos os emojis do sistema por SVGs vetoriais escaláveis.
"""

# ── HELPER ───────────────────────────────────────────────────────────────────────

_PATHS: dict[str, str] = {
    "bar-chart":      '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    "file-text":      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
    "grid":           '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "users":          '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user":           '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "log-out":        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "upload":         '<polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>',
    "download":       '<polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>',
    "check-circle":   '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "x-circle":       '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
    "alert-triangle": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "info":           '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "plus":           '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "plus-circle":    '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>',
    "trash-2":        '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
    "folder":         '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "lock":           '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "clipboard":      '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>',
    "activity":       '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "calendar":       '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "refresh-cw":     '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "shield":         '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "settings":       '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "x":              '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "check":          '<polyline points="20 6 9 17 4 12"/>',
    "arrow-left":     '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "zap":            '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
}


def icon(name: str, size: int = 16, color: str = "currentColor", extra_style: str = "") -> str:
    """Retorna um SVG inline Feather-style para uso em st.markdown."""
    paths = _PATHS.get(name, "")
    style = f"display:inline-block;vertical-align:middle;flex-shrink:0;{extra_style}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" style="{style}">'
        f'{paths}</svg>'
    )


# ── ILUSTRAÇÃO SVG DA TELA DE LOGIN ─────────────────────────────────────────────

SVG_LOGIN_GRAPHIC = """
<div style="margin-bottom:1.8rem;">
<svg viewBox="0 0 520 168" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;border-radius:16px;display:block;">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1" gradientUnits="objectBoundingBox">
      <stop offset="0%"   stop-color="#0D1117"/>
      <stop offset="100%" stop-color="#091420"/>
    </linearGradient>
    <linearGradient id="tealG" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#00CED1"/>
      <stop offset="100%" stop-color="#007A80"/>
    </linearGradient>
    <linearGradient id="cardL" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   stop-color="#131C28"/>
      <stop offset="100%" stop-color="#0D1520"/>
    </linearGradient>
    <linearGradient id="cardC" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   stop-color="#071E22"/>
      <stop offset="100%" stop-color="#041318"/>
    </linearGradient>
    <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="9" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="g4" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Fundo -->
  <rect width="520" height="168" rx="16" fill="url(#bg)"/>

  <!-- Grade de pontos sutil -->
  <g opacity="0.22">
    <rect x="0" y="0" width="520" height="168" rx="16" fill="none"/>
    <!-- linha de pontos horizontal -->
    <circle cx="40"  cy="28"  r="1" fill="#1E3040"/>
    <circle cx="80"  cy="28"  r="1" fill="#1E3040"/>
    <circle cx="440" cy="28"  r="1" fill="#1E3040"/>
    <circle cx="480" cy="28"  r="1" fill="#1E3040"/>
    <circle cx="40"  cy="140" r="1" fill="#1E3040"/>
    <circle cx="80"  cy="140" r="1" fill="#1E3040"/>
    <circle cx="440" cy="140" r="1" fill="#1E3040"/>
    <circle cx="480" cy="140" r="1" fill="#1E3040"/>
  </g>

  <!-- Brilho teal difuso atrás do card central -->
  <rect x="170" y="18" width="180" height="132" rx="24"
        fill="#00CED1" opacity="0.07" filter="url(#glow)"/>

  <!-- ══ CARD ESQUERDO — XML ══ -->
  <rect x="28" y="28" width="128" height="112" rx="14"
        fill="url(#cardL)" stroke="#1C3044" stroke-width="1.4"/>

  <!-- Ícone: documento com dobra no canto -->
  <g transform="translate(64, 46)" fill="none"
     stroke="#3E7090" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6">
    <path d="M4 0 L32 0 L32 4 L36 4 L36 44 L4 44 Z"/>
    <path d="M32 0 L32 8 L40 8"/>
    <path d="M0 4 L32 4 L32 8 L40 8 L40 48 L0 48 Z"
          fill="#0E1E2E" stroke="#2A5070" stroke-width="1.4"/>
    <line x1="8"  y1="20" x2="32" y2="20" stroke-width="1.3"/>
    <line x1="8"  y1="27" x2="32" y2="27" stroke-width="1.3"/>
    <line x1="8"  y1="34" x2="22" y2="34" stroke-width="1.3"/>
  </g>

  <!-- Badge XML -->
  <rect x="44" y="104" width="40" height="16" rx="5"
        fill="#0E1E30" stroke="#1C3850" stroke-width="1"/>
  <text x="64" y="115.5" text-anchor="middle"
        fill="#3E7090" font-size="8" font-family="'Courier New',monospace"
        font-weight="700">&lt;/&gt;</text>

  <!-- Label -->
  <text x="92" y="152" text-anchor="middle"
        fill="#3A5570" font-size="10" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="2">XML</text>

  <!-- ══ SETA ESQUERDA ══ -->
  <line x1="160" y1="84" x2="196" y2="84"
        stroke="#1C3A44" stroke-width="1.5" stroke-dasharray="4,4" stroke-linecap="round"/>
  <path d="M193,79 L203,84 L193,89"
        fill="none" stroke="#265060" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round"/>

  <!-- ══ CARD CENTRAL — CONVERSOR ══ -->
  <!-- Borda brilhante externa -->
  <rect x="204" y="16" width="112" height="104" rx="18"
        fill="none" stroke="#00CED1" stroke-width="2.5" opacity="0.9"
        filter="url(#glow)"/>
  <!-- Card principal -->
  <rect x="204" y="16" width="112" height="104" rx="18"
        fill="url(#cardC)" stroke="#00CED1" stroke-width="2"/>
  <!-- Anel interno -->
  <rect x="216" y="28" width="88" height="80" rx="12"
        fill="none" stroke="#00CED1" stroke-width="0.5" opacity="0.18"/>

  <!-- Ícone raio (zap) — grande, centralizado -->
  <g transform="translate(234, 34)" filter="url(#g4)">
    <polygon points="22,0 8,28 20,28 14,52 42,20 26,20 34,0"
             fill="url(#tealG)"/>
  </g>

  <!-- Label -->
  <text x="260" y="138" text-anchor="middle"
        fill="#00CED1" font-size="10" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="2">CONVERSOR</text>

  <!-- ══ SETA DIREITA ══ -->
  <line x1="320" y1="84" x2="356" y2="84"
        stroke="#1C3A44" stroke-width="1.5" stroke-dasharray="4,4" stroke-linecap="round"/>
  <path d="M353,79 L363,84 L353,89"
        fill="none" stroke="#265060" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round"/>

  <!-- ══ CARD DIREITO — TXT / XLSX ══ -->
  <rect x="364" y="28" width="128" height="112" rx="14"
        fill="url(#cardL)" stroke="#1C3044" stroke-width="1.4"/>

  <!-- Ícone: planilha/tabela -->
  <g transform="translate(380, 46)" fill="none"
     stroke="#3E7090" stroke-linecap="round" stroke-linejoin="round">
    <rect x="0" y="0" width="56" height="48" rx="5" stroke-width="1.6"/>
    <!-- Header -->
    <rect x="0" y="0" width="56" height="14" rx="5" fill="#162838" stroke="none"/>
    <rect x="1" y="1" width="54" height="12" rx="4" fill="#162838" stroke="none"/>
    <line x1="0"  y1="14" x2="56" y2="14" stroke-width="1"/>
    <line x1="0"  y1="28" x2="56" y2="28" stroke-width="1"/>
    <line x1="0"  y1="38" x2="56" y2="38" stroke-width="1"/>
    <line x1="18" y1="14" x2="18" y2="48" stroke-width="1"/>
    <line x1="37" y1="14" x2="37" y2="48" stroke-width="1"/>
    <!-- Dados simulados nas células -->
    <rect x="4"  y="17" width="10" height="7" rx="1" fill="#1A3040" stroke="none"/>
    <rect x="21" y="17" width="12" height="7" rx="1" fill="#142830" stroke="none"/>
    <rect x="40" y="17" width="12" height="7" rx="1" fill="#1A3040" stroke="none"/>
  </g>

  <!-- Label -->
  <text x="428" y="152" text-anchor="middle"
        fill="#3A5570" font-size="10" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="2">TXT / XLSX</text>
</svg>
</div>
"""
