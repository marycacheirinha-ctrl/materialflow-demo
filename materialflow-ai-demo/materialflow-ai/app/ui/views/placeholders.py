"""Áreas previstas no projeto cujo desenvolvimento é a fase seguinte. Não simulam funcionalidade."""

import streamlit as st


def batch_import() -> None:
    st.header("Importação em lote")
    st.info(
        "Esta área ainda não está disponível. A importação de ficheiros Excel com várias peças "
        "será implementada na fase seguinte do projeto, depois do motor de IA."
    )


def dictionary() -> None:
    st.header("Dicionário técnico")
    st.info(
        "Esta área ainda não está disponível. O dicionário de termos técnicos aprovados será "
        "implementado na fase seguinte, juntamente com o motor de IA que o consulta."
    )
