"""
Módulo da página de contactos do website "Luxury Wheels" (Fase 6).

As mensagens enviadas pelo formulário ficam guardadas na tabela
mensagens_contacto, para a empresa as ler — não é enviado nenhum e-mail.
"""

import autenticacao
import database

# Tamanho mínimo e máximo de uma mensagem (em caracteres)
TAMANHO_MINIMO_MENSAGEM = 10
TAMANHO_MAXIMO_MENSAGEM = 2000


def validar_mensagem(nome, email, mensagem):
    """
    Valida os dados do formulário de contacto. Devolve a lista de erros
    (vazia se estiver tudo bem). Reutiliza a validação de e-mail do registo.
    """
    erros = []
    if len(nome) < 2:
        erros.append("Indique o seu nome.")
    if not autenticacao.email_valido(email):
        erros.append("Indique um e-mail válido, para lhe podermos responder.")
    if len(mensagem) < TAMANHO_MINIMO_MENSAGEM:
        erros.append(f"A mensagem deve ter pelo menos {TAMANHO_MINIMO_MENSAGEM} caracteres.")
    if len(mensagem) > TAMANHO_MAXIMO_MENSAGEM:
        erros.append(f"A mensagem pode ter no máximo {TAMANHO_MAXIMO_MENSAGEM} caracteres.")
    return erros


def guardar_mensagem(nome, email, mensagem):
    """Guarda a mensagem na base de dados."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "INSERT INTO mensagens_contacto (nome, email, mensagem) VALUES (?, ?, ?)",
            (nome, email, mensagem),
        )
        ligacao.commit()
    finally:
        ligacao.close()
