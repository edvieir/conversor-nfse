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
<svg viewBox="0 0 480 155" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;border-radius:14px;display:block;">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#0D1117"/>
      <stop offset="50%"  stop-color="#0A1828"/>
      <stop offset="100%" stop-color="#0D1117"/>
    </linearGradient>
    <linearGradient id="teal" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#00CED1"/>
      <stop offset="100%" stop-color="#008C8C"/>
    </linearGradient>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="softglow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Fundo -->
  <rect width="480" height="155" rx="14" fill="url(#bg)"/>

  <!-- Brilho difuso atrás do nó central -->
  <circle cx="240" cy="77" r="60" fill="#00CED1" opacity="0.05"/>
  <circle cx="240" cy="77" r="42" fill="#00CED1" opacity="0.05"/>

  <!-- ── Linhas de conexão ── -->
  <!-- Esquerda → Centro -->
  <line x1="129" y1="77" x2="193" y2="77"
        stroke="#1C3A44" stroke-width="1.5" stroke-dasharray="5,5"
        stroke-linecap="round"/>
  <polygon points="191,72 202,77 191,82" fill="#1C4050"/>
  <!-- Centro → Direita -->
  <line x1="283" y1="77" x2="345" y2="77"
        stroke="#1C3A44" stroke-width="1.5" stroke-dasharray="5,5"
        stroke-linecap="round"/>
  <polygon points="343,72 354,77 343,82" fill="#1C4050"/>

  <!-- ── NÓ ESQUERDO — XML ── -->
  <circle cx="96" cy="77" r="33" fill="#0A1520" stroke="#1E3D54" stroke-width="1.8"/>
  <!-- Ícone documento -->
  <g transform="translate(83,62)"
     fill="none" stroke="#3A7090" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 0 L15 0 L22 7 L22 26 L2 26 Z" stroke-width="1.5"/>
    <path d="M15 0 L15 7 L22 7"               stroke-width="1.5"/>
    <line x1="6" y1="13" x2="18" y2="13"      stroke-width="1.3"/>
    <line x1="6" y1="17" x2="18" y2="17"      stroke-width="1.3"/>
    <line x1="6" y1="21" x2="14" y2="21"      stroke-width="1.3"/>
  </g>
  <text x="96" y="123" text-anchor="middle"
        fill="#3A5570" font-size="9" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="1.5">XML</text>

  <!-- ── NÓ CENTRAL — CONVERSOR ── -->
  <circle cx="240" cy="77" r="42" fill="#071E22"
          stroke="url(#teal)" stroke-width="2.5" filter="url(#glow)"/>
  <!-- Anel interno sutil -->
  <circle cx="240" cy="77" r="33" fill="none"
          stroke="#00CED1" stroke-width="0.6" opacity="0.2"/>
  <!-- Seta play (mais refinada) -->
  <polygon points="229,63 256,77 229,91"
           fill="url(#teal)" filter="url(#softglow)"/>
  <text x="240" y="135" text-anchor="middle"
        fill="#00CED1" font-size="9" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="1.5">CONVERSOR</text>

  <!-- ── NÓ DIREITO — TXT / XLSX ── -->
  <circle cx="384" cy="77" r="33" fill="#0A1520" stroke="#1E3D54" stroke-width="1.8"/>
  <!-- Ícone planilha -->
  <g transform="translate(370,63)"
     fill="none" stroke="#3A7090" stroke-linecap="round" stroke-linejoin="round">
    <rect x="0" y="0" width="28" height="24" rx="2" stroke-width="1.5"/>
    <path d="M0 0 L28 0 L28 8 L0 8 Z" fill="#193040" opacity="0.7" stroke="none"/>
    <line x1="0"  y1="8"  x2="28" y2="8"  stroke-width="0.9"/>
    <line x1="0"  y1="16" x2="28" y2="16" stroke-width="0.9"/>
    <line x1="9"  y1="8"  x2="9"  y2="24" stroke-width="0.9"/>
    <line x1="19" y1="8"  x2="19" y2="24" stroke-width="0.9"/>
  </g>
  <text x="384" y="123" text-anchor="middle"
        fill="#3A5570" font-size="9" font-family="Inter,sans-serif"
        font-weight="700" letter-spacing="1.5">TXT / XLSX</text>
</svg>
</div>
"""
