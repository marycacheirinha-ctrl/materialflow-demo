# Demonstração online com um link (Streamlit Community Cloud)

Serve para mostrar o fluxo a colegas. Não usa nada da empresa. É gratuito, mas **só para dados
fictícios**: o serviço é externo e os dados apagam-se quando a aplicação reinicia (por exemplo,
depois de alguns dias sem uso). Para trabalho real, use a instalação normal do README.

## 1. Contas (gratuitas)

- GitHub: https://github.com (é onde o código fica guardado).
- Streamlit Community Cloud: https://share.streamlit.io, entrando com a conta GitHub.

## 2. Colocar o código no GitHub

1. No GitHub, crie um repositório novo (botão «New»). Nome à escolha, por exemplo `materialflow-demo`.
   Pode ser privado: o código não contém credenciais.
2. Extraia o zip. Na página do repositório, escolha «Add file», depois «Upload files», e arraste o
   **conteúdo** da pasta `materialflow-ai` (não a pasta em si). Confirme com «Commit changes».
3. Confirme que na raiz do repositório aparecem `requirements.txt` e as pastas `app` e `alembic`.

## 3. Publicar

1. Em https://share.streamlit.io, clique em «Create app» e escolha o repositório que criou.
2. **Main file path:** `app/ui/main.py`
3. Abra «Advanced settings» e:
   - em **Python version**, escolha **3.12** (o código precisa de 3.11 ou superior);
   - em **Secrets**, cole as duas linhas abaixo, trocando a palavra-passe por uma frase sua com pelo
     menos 12 caracteres:
     ```
     DEMO_MODE = "true"
     DEMO_PASSWORD = "uma frase longa e unica"
     ```
4. Clique em «Deploy». A primeira vez demora alguns minutos.

Os nomes dos botões podem variar um pouco, mas o caminho é este.

## 4. Partilhar

Envie o endereço (`algo.streamlit.app`) aos colegas e a palavra-passe **por outro canal**. Os
utilizadores são `demo.tecnico`, `demo.compras`, `demo.dadosmestre` e `demo.admin`, todos com a
mesma palavra-passe. Já vêm três peças fictícias em estados diferentes.

Sugestão de visita: entrar como `demo.tecnico` e submeter o rascunho, depois `demo.compras` para
encaminhar, e por fim `demo.dadosmestre` para aprovar e registar um código SAP inventado.

## Cuidados

- Quem tiver o endereço e a palavra-passe entra. Escolha uma palavra-passe que não use noutro sítio.
- Não escreva peças, preços ou fornecedores reais.
- Para apagar tudo, elimine a aplicação em Streamlit (menu da aplicação) ou o repositório no GitHub.
- A IA, o dicionário e a importação de Excel ainda não existem nesta versão.
