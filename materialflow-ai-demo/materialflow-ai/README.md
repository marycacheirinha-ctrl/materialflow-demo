# MaterialFlow AI

Aplicação web para criar, normalizar, validar e gerir fichas de materiais destinadas ao SAP,
com o fluxo obrigatório **Técnicos / Logística, Compras, Dados Mestre**. A aprovação final, a
exportação e o registo do código SAP são exclusivos de Dados Mestre.

Stack: Python 3.12+, Streamlit, PostgreSQL, SQLAlchemy, Alembic, Argon2id, Pandas, Docker.

## Estado do projeto

Este é o resultado da **fase 1** (estrutura, base de dados, autenticação e fluxo de criação).

| Área | Estado |
| --- | --- |
| Estrutura modular (interface, domínio, serviços, dados, segurança) | Feito |
| Base de dados e migração inicial (PostgreSQL) | Feito |
| Contas individuais, Argon2id, sessões com expiração, bloqueio por tentativas, recuperação de palavra-passe | Feito |
| Permissões por departamento verificadas no servidor | Feito |
| Criação de solicitações, características dinâmicas com origem, fotografias e PDF, informação comercial e logística | Feito |
| Workflow completo com histórico (quem, quando, estado anterior e novo, observações, alterações) | Feito |
| Descritivos PT-PT e EN: limite de 40 caracteres, maiúsculas, sem ponto final, sem cortes automáticos | Feito (escritos manualmente) |
| Registo de auditoria | Feito |
| Motor de IA (OpenAI), sugestão de campos e descritivos | **Por fazer** (fase 2) |
| Dicionário técnico | **Por fazer** (fase 2) |
| Importação de Excel em lote | **Por fazer** (fase 2) |
| Exportações (descritivos, fichas, template SAP configurável) | **Por fazer** (fase 3) |
| Deteção de duplicados | **Por fazer** (fase 3) |
| Backups automáticos e política de retenção | **Por fazer**: ver «Backups» em `docs/publicacao-https.md` |
| Envio de email na recuperação de palavra-passe | Não existe: o administrador entrega um código de uso único |

As áreas «Importação em lote» e «Dicionário técnico» aparecem na interface com um aviso claro de
que ainda não estão disponíveis. Nada é simulado como se estivesse integrado.

Os campos SAP obrigatórios para aprovar estão em `REQUIRED_SAP_FIELDS`
(`app/services/requests.py`). Serão ligados ao template real de Dados Mestre quando o tivermos.

## Execução local com Docker

```bash
cp .env.example .env
# Edite .env e defina POSTGRES_PASSWORD (uma palavra-passe forte e única)
docker compose up --build
```

Noutro terminal, crie o administrador técnico (a palavra-passe é pedida no terminal):

```bash
docker compose exec app python -m scripts.create_admin
```

Abra http://localhost:8501. O administrador cria as contas de cada departamento na área
**Administração**.

Dados de demonstração fictícios (só para testes, recusado em produção):

```bash
docker compose exec app python -m scripts.seed_demo
```

As palavras-passe das contas de demonstração são geradas ao acaso e mostradas uma única vez.

## Demonstração online (só dados fictícios)

Para mostrar o fluxo a colegas com um simples link, sem instalar nada e sem tocar na infraestrutura da
empresa, veja `docs/demo-online.md` (Streamlit Community Cloud, modo `DEMO_MODE`).

## Execução sem Docker

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL="postgresql+psycopg://utilizador:palavra-passe@localhost:5432/materialflow"
alembic upgrade head
python -m scripts.bootstrap
python -m scripts.create_admin
streamlit run app/ui/main.py
```

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

- `tests/unit`: regras de domínio puras (40 caracteres, permissões, workflow, números, uploads, logs).
- `tests/integration`: autenticação, bloqueio, sessões, recuperação, workflow completo, persistência
  e **verificação de que a migração coincide com os modelos**. Usam SQLite temporário.

## Estrutura

```
app/
  domain/      regras puras: permissões, workflow, descritivos, números (sem base de dados)
  security/    Argon2id, tokens, validação de ficheiros, política de palavras-passe
  db/          modelos SQLAlchemy, sessões
  services/    lógica de negócio e verificação de permissões (autenticação, solicitações, contas)
  ui/          interface Streamlit (só apresentação)
alembic/       migrações
scripts/       bootstrap, create_admin, seed_demo
tests/         unitários e de integração
docs/          manual por perfil e publicação
```

A interface nunca acede diretamente à base de dados nem decide permissões: chama os serviços, que
verificam sempre o departamento e o estado da solicitação.

## Segurança: o que está e o que falta

Feito: palavras-passe com Argon2id; tokens de sessão e de recuperação guardados só como hash;
mensagens de erro de login iguais para utilizador inexistente e palavra-passe errada; bloqueio por
tentativas repetidas (também para nomes inexistentes); validação de ficheiros pelo conteúdo real,
tamanho e extensão; ficheiros guardados fora da web com nome aleatório; consultas parametrizadas
(SQLAlchemy); logs com mascaramento de segredos; sem credenciais no código.

Limitações conhecidas: a sessão do browser perde-se ao recarregar a página (é preciso iniciar sessão
de novo); HTTPS tem de ser fornecido por um proxy à frente (ver `docs/publicacao-https.md`).
