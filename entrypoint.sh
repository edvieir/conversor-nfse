#!/bin/sh
# Fixa a porta — impede qualquer override
export PORT=8080
export STREAMLIT_SERVER_PORT=8080

# Se o DB não existir, descomprime do seed
if [ ! -f /app/data/conversor.db ]; then
    echo "[init] Descomprimindo banco de dados..."
    gunzip -c /app/data-seed/conversor.db.gz > /app/data/conversor.db
    echo "[init] Banco pronto."
fi

echo "[init] Iniciando Streamlit na porta 8080..."
exec streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --server.fileWatcherType=none
