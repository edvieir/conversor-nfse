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
<div style="margin-bottom:1.6rem;">
<svg viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;border-radius:12px;display:block;">
  <defs>
    <linearGradient id="bg1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   style="stop-color:#0A192F"/>
      <stop offset="100%" style="stop-color:#112240"/>
    </linearGradient>
    <linearGradient id="ga" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   style="stop-color:#00CED1"/>
      <stop offset="100%" style="stop-color:#20B2AA"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" rx="12" fill="url(#bg1)"/>
  <!-- nós -->
  <circle cx="80"  cy="60" r="22" fill="none" stroke="#2F6FEB" stroke-width="2.5"/>
  <circle cx="200" cy="60" r="30" fill="none" stroke="url(#ga)" stroke-width="3.5"/>
  <circle cx="320" cy="60" r="22" fill="none" stroke="#2F6FEB" stroke-width="2.5"/>
  <!-- linhas tracejadas -->
  <path d="M102 60 L170 60" stroke="#2A3A50" stroke-width="1.5" stroke-dasharray="4,4"/>
  <path d="M230 60 L298 60" stroke="#2A3A50" stroke-width="1.5" stroke-dasharray="4,4"/>
  <!-- ícone XML (doc) -->
  <rect x="71" y="50" width="18" height="22" rx="2" fill="#2F6FEB" opacity="0.85"/>
  <line x1="75" y1="57" x2="85" y2="57" stroke="#fff" stroke-width="1.3"/>
  <line x1="75" y1="61" x2="85" y2="61" stroke="#fff" stroke-width="1.3"/>
  <line x1="75" y1="65" x2="82" y2="65" stroke="#fff" stroke-width="1.3"/>
  <!-- seta central (conversor) -->
  <polygon points="188,51 210,60 188,69" fill="#00CED1"/>
  <!-- ícone TXT/XLSX (tabela) -->
  <rect x="310" y="50" width="20" height="20" rx="2" fill="#2F6FEB" opacity="0.85"/>
  <line x1="315" y1="55" x2="325" y2="55" stroke="#fff" stroke-width="1.3"/>
  <line x1="315" y1="60" x2="325" y2="60" stroke="#fff" stroke-width="1.3"/>
  <line x1="315" y1="65" x2="325" y2="65" stroke="#fff" stroke-width="1.3"/>
  <line x1="320" y1="50" x2="320" y2="70" stroke="#fff" stroke-width="0.7" opacity="0.5"/>
  <!-- labels -->
  <text x="80"  y="96" text-anchor="middle" fill="#3A4455"
        font-size="9" font-family="Inter,sans-serif">XML</text>
  <text x="200" y="103" text-anchor="middle" fill="#00CED1"
        font-size="9" font-family="Inter,sans-serif" font-weight="600">CONVERSOR</text>
  <text x="320" y="96" text-anchor="middle" fill="#3A4455"
        font-size="9" font-family="Inter,sans-serif">TXT / XLSX</text>
</svg>
</div>
"""
