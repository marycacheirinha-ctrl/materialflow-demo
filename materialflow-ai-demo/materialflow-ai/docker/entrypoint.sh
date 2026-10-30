#!/bin/sh
set -eu
echo "A aplicar as migracoes da base de dados..."
alembic upgrade head
echo "A garantir os dados de referencia..."
python -m scripts.bootstrap
echo "A iniciar a aplicacao..."
exec streamlit run app/ui/main.py --server.port=8501 --server.address=0.0.0.0
