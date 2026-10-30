# Manual resumido por perfil

Todos os perfis: inicie sessão com o seu nome de utilizador. No primeiro acesso tem de escolher uma
nova palavra-passe (pelo menos 12 caracteres; uma frase longa serve). Se se esquecer dela, peça um
código de recuperação ao administrador técnico.

## Técnicos / Logística

1. **Nova peça**: escreva a descrição original, escolha a categoria e, se for relevante, marca,
   modelo e referência do fabricante. Fica um rascunho.
2. **Materiais e solicitações**, abra o rascunho e preencha:
   - **Identificação**: descritivos PT-PT e EN, até 40 caracteres cada (o sistema passa a maiúsculas e
     tira o ponto final; se passar do limite, tem de o encurtar, porque o texto nunca é cortado automaticamente).
   - **Características**: use «Acrescentar campos sugeridos da categoria». Deixe o valor vazio se não
     está confirmado. Quando há valor, indique a origem (descrição, fotografia, ficha técnica ou
     introdução manual). Nunca preencha por dedução.
   - **Anexos**: fotografias (JPG, PNG, WEBP) e fichas técnicas em PDF.
   - **Logística**: pesos e dimensões da **peça**, não da embalagem.
3. **Submeter a Compras**. Se a solicitação for devolvida, leia as observações, corrija e reenvie.

## Compras

1. Em **Materiais e solicitações**, abra as solicitações em PENDENTE COMPRAS e reveja os dados técnicos.
2. No separador **Comercial**, registe um ou mais fornecedores: referência, preço, moeda, unidade de
   compra, quantidade por embalagem e validade ou referência do preço.
3. **Encaminhar para Dados Mestre** (exige pelo menos um fornecedor com preço, moeda e unidade) ou
   **Devolver para correção** (as observações são obrigatórias).

## Dados Mestre

1. Reveja a ficha completa e os descritivos PT-PT e EN.
2. No separador **SAP**, preencha tipo de material, grupo de mercadorias, unidade base, centro e
   organização de compras. A lista «Ainda falta para poder aprovar» mostra o que falta.
3. Confirme manualmente no SAP que o material não existe (a deteção automática de duplicados ainda
   não está ativa). Depois **Aprovar para SAP** ou **Devolver para correção**.
4. Crie o material no SAP e registe o código com **Concluir no SAP**. O código nunca é gerado pela
   aplicação e é único por solicitação.

## Administrador técnico

Em **Administração**: criar e desativar contas, atribuir departamento, gerar códigos de recuperação
de palavra-passe (uso único, expiram em minutos) e consultar a auditoria. O administrador técnico
**não** tem autoridade para criar, aprovar ou concluir materiais. Tem de existir sempre pelo menos um
administrador ativo.
