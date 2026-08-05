#!/bin/sh
# Se o DB não existir, descomprime do seed
if [ ! -f /app/data/conversor.db ]; then
    echo "[init] Descomprimindo banco de dados..."
    gunzip -k /app/data-seed/conversor.db.gz -c > /app/data/conversor.db
    echo "[init] Banco pronto ($(du -h /app/data/conversor.db | cut -f1))"
fi
exec streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --server.fileWatcherType=none
