FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Guarda o DB comprimido como seed para volumes vazios
RUN mkdir -p /app/data-seed && cp /app/data/conversor.db.gz /app/data-seed/conversor.db.gz

RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
