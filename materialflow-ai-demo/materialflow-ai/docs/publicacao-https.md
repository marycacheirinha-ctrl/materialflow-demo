# Publicação num servidor com HTTPS

A aplicação não termina HTTPS sozinha. Em produção, coloque um proxy inverso com certificado à frente.
O `docker-compose.yml` publica a aplicação apenas em `127.0.0.1:8501` para que só o proxy lhe aceda.

## 1. Preparar

- Servidor Linux com Docker e Docker Compose, e um nome DNS a apontar para ele (ex.: `materiais.exemplo.pt`).
- Portas 80 e 443 abertas. A 8501 **não** deve estar acessível de fora.
- No `.env`: `APP_ENV=production`, `APP_BASE_URL=https://materiais.exemplo.pt` e uma `POSTGRES_PASSWORD` forte.
  Os segredos ficam em variáveis de ambiente ou num gestor de segredos, nunca no repositório.

## 2. Proxy com certificado automático (Caddy)

Os ficheiros `deploy/docker-compose.https.yml` e `deploy/Caddyfile` são um exemplo. Edite o domínio
no `Caddyfile` e arranque:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.https.yml up -d --build
docker compose exec app python -m scripts.create_admin
```

O Caddy obtém e renova o certificado (Let's Encrypt) e já suporta os WebSockets que o Streamlit usa.
Pode usar nginx ou o proxy da sua empresa: tem de reencaminhar também os WebSockets para a porta 8501.

## 3. Verificar

- `https://materiais.exemplo.pt` abre com cadeado e `http://` redireciona para `https://`.
- A porta 8501 não responde a partir de outra máquina.
- O login funciona e a auditoria regista os acessos.

## Backups (a implementar pela infraestrutura)

A aplicação ainda não faz backups nem aplica retenção por si. Até lá, agende no servidor, por exemplo:

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > /backups/materialflow-$(date +%F).sql.gz
```

e copie também o volume `storage` (fotografias e fichas técnicas). Defina a retenção removendo
cópias antigas (`find /backups -mtime +30 -delete`) e **teste uma restauração** antes de depender
dela. A retenção de dados da aplicação (auditoria e anexos) será configurável numa fase posterior.

## IA e dados da empresa (fase 2)

Quando o motor de IA for ligado, a chave da OpenAI ficará só no servidor (variável de ambiente) e os
documentos só serão enviados com autorização expressa da empresa.
