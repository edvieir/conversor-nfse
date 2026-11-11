// background.js — abre o painel lateral ao clicar no ícone.
// O painel fica aberto enquanto o usuário trabalha na página, o que um popup
// não permite: ele fecharia a cada clique no portal.

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
    .catch((e) => console.error('sidePanel:', e));
});
