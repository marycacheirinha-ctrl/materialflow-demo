"""Textos em português de Portugal para apresentar os valores do domínio."""

from app.domain.enums import AttachmentKind, CharacteristicSource, Department, RequestStatus

DEPARTMENT_LABELS = {
    Department.TECNICOS_LOGISTICA: "Técnicos / Logística",
    Department.COMPRAS: "Compras",
    Department.DADOS_MESTRE: "Dados Mestre",
}

STATUS_LABELS = {
    RequestStatus.RASCUNHO: "RASCUNHO",
    RequestStatus.PENDENTE_COMPRAS: "PENDENTE COMPRAS",
    RequestStatus.PENDENTE_DADOS_MESTRE: "PENDENTE DADOS MESTRE",
    RequestStatus.DEVOLVIDO_PARA_CORRECAO: "DEVOLVIDO PARA CORREÇÃO",
    RequestStatus.APROVADO_PARA_SAP: "APROVADO PARA SAP",
    RequestStatus.CONCLUIDO_NO_SAP: "CONCLUÍDO NO SAP",
}

SOURCE_LABELS = {
    CharacteristicSource.DESCRICAO_ORIGINAL: "Descrição original",
    CharacteristicSource.FOTOGRAFIA: "Fotografia",
    CharacteristicSource.FICHA_TECNICA: "Ficha técnica",
    CharacteristicSource.INTRODUCAO_MANUAL: "Introdução manual",
}

ATTACHMENT_KIND_LABELS = {
    AttachmentKind.FOTOGRAFIA: "Fotografia",
    AttachmentKind.FICHA_TECNICA: "Ficha técnica",
}
