"""
Módulo de autenticação do website "Luxury Wheels" (Fase 2).

Reúne toda a lógica de negócio ligada às contas dos clientes, separada das
rotas do Flask (que ficam no app.py):
  - validação dos dados do formulário de registo;
  - criação de contas e verificação de credenciais (login);
  - geração e validação dos links simulados de recuperação de password.

As passwords nunca são guardadas em texto simples: usa-se o Werkzeug (que vem
com o Flask) para gerar e verificar um "hash" da password — uma transformação
de sentido único, que não permite voltar à password original.
"""

import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

import database

# --- Regras de validação ---------------------------------------------------

# Comprimento mínimo e máximo do nome de utilizador
COMPRIMENTO_MINIMO_UTILIZADOR = 3
COMPRIMENTO_MAXIMO_UTILIZADOR = 20

# Caracteres especiais permitidos no nome de utilizador (além de letras e números)
CARACTERES_ESPECIAIS_UTILIZADOR = "._"

# Comprimento mínimo da password (tem também de ter pelo menos 1 letra e 1 número)
COMPRIMENTO_MINIMO_PASSWORD = 8

# Validade dos links de recuperação de password
VALIDADE_LINK_RECUPERACAO = timedelta(minutes=10)

# Caracteres possíveis no código aleatório dos links de recuperação
CARACTERES_CODIGO_RECUPERACAO = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
COMPRIMENTO_CODIGO_RECUPERACAO = 32


def utilizador_valido(utilizador):
    """
    Verifica o nome de utilizador com métodos de strings (Módulo 4, Unidade 2):
    entre 3 e 20 caracteres, só letras, números, ponto e traço inferior (_).
    Como os espaços não são nenhum destes caracteres, ficam automaticamente
    excluídos.
    """
    if len(utilizador) < COMPRIMENTO_MINIMO_UTILIZADOR or len(utilizador) > COMPRIMENTO_MAXIMO_UTILIZADOR:
        return False

    # Todos os caracteres têm de ser letras/números (isalnum) ou um dos especiais
    return all([caracter.isalnum() or caracter in CARACTERES_ESPECIAIS_UTILIZADOR
                for caracter in utilizador])


def email_valido(email):
    """
    Validação simples do formato do e-mail (texto@texto.texto), com métodos
    de strings: sem espaços, exatamente um "@", algo antes do "@" e um ponto
    no domínio (que não pode estar no início nem no fim).
    """
    if " " in email or email.count("@") != 1:
        return False

    parte_antes_arroba, dominio = email.split("@")
    return (
        len(parte_antes_arroba) > 0
        and "." in dominio
        and not dominio.startswith(".")
        and not dominio.endswith(".")
    )


def validar_password(password, confirmacao_password):
    """
    Verifica se a password cumpre as regras definidas para o projeto
    (mínimo 8 caracteres, pelo menos uma letra e um número — tal como no
    exercício ValidadorPalavraPasse do Módulo 4, Unidade 2) e se coincide
    com a confirmação. Devolve a lista de mensagens de erro (vazia se estiver
    tudo certo).
    """
    erros = []

    if len(password) < COMPRIMENTO_MINIMO_PASSWORD:
        erros.append(f"A password tem de ter pelo menos {COMPRIMENTO_MINIMO_PASSWORD} caracteres.")
    if not any([caracter.isalpha() for caracter in password]):
        erros.append("A password tem de ter pelo menos uma letra.")
    if not any([caracter.isdigit() for caracter in password]):
        erros.append("A password tem de ter pelo menos um número.")
    if password != confirmacao_password:
        erros.append("A password e a confirmação não coincidem.")

    return erros


def validar_dados_registo(nome, utilizador, email, password, confirmacao_password):
    """
    Valida todos os campos do formulário de registo, incluindo a verificação
    de que o nome de utilizador e o e-mail ainda não estão a ser usados.
    Devolve a lista de mensagens de erro (vazia se o registo for válido).
    """
    erros = []

    if not nome:
        erros.append("Indique o seu nome.")

    if not utilizador_valido(utilizador):
        erros.append(
            "O nome de utilizador tem de ter entre 3 e 20 caracteres, sem espaços "
            "(só letras, números, ponto e traço inferior (_))."
        )

    if not email_valido(email):
        erros.append("Indique um endereço de e-mail válido.")

    erros.extend(validar_password(password, confirmacao_password))

    # Só vale a pena consultar a base de dados se o formato estiver correto
    if not erros:
        ligacao = database.obter_ligacao()
        try:
            cursor = ligacao.cursor()
            cursor.execute("SELECT id_cliente FROM clientes WHERE utilizador = ?", (utilizador,))
            utilizador_existente = cursor.fetchone()
            cursor.execute("SELECT id_cliente FROM clientes WHERE email = ?", (email,))
            email_existente = cursor.fetchone()
        finally:
            ligacao.close()

        if utilizador_existente:
            erros.append("Esse nome de utilizador já está a ser usado. Escolha outro.")
        if email_existente:
            erros.append("Já existe uma conta registada com esse e-mail.")

    return erros


# --- Contas de clientes ----------------------------------------------------

def criar_cliente(nome, utilizador, email, password, quer_newsletter):
    """
    Insere um novo cliente na base de dados (com a password em forma de hash)
    e devolve o registo completo do cliente criado.
    """
    password_hash = generate_password_hash(password)

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            INSERT INTO clientes (nome, utilizador, email, password_hash, newsletter)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nome, utilizador, email, password_hash, 1 if quer_newsletter else 0),
        )
        ligacao.commit()

        # lastrowid: o id que a base de dados atribuiu ao registo acabado de inserir
        cursor.execute("SELECT * FROM clientes WHERE id_cliente = ?", (cursor.lastrowid,))
        novo_cliente = cursor.fetchone()
    finally:
        ligacao.close()

    return novo_cliente


def autenticar_cliente(utilizador, password):
    """
    Verifica as credenciais de login. Devolve o registo do cliente se o nome
    de utilizador existir e a password estiver correta; caso contrário, None.

    A mensagem de erro mostrada ao cliente é propositadamente a mesma nos
    dois casos (utilizador inexistente ou password errada), para não revelar
    que nomes de utilizador existem no sistema.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT * FROM clientes WHERE utilizador = ?", (utilizador,))
        cliente = cursor.fetchone()
    finally:
        ligacao.close()

    # check_password_hash calcula o hash da password escrita e compara-o com o guardado
    if cliente and check_password_hash(cliente["password_hash"], password):
        return cliente
    return None


def cliente_existe(id_cliente):
    """
    Indica se ainda existe um cliente com este id. Usado para validar a
    sessão: o cookie da sessão fica guardado no browser e pode sobreviver à
    base de dados ser recriada (python database.py), apontando então para
    um cliente que já não existe.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE id_cliente = ?", (id_cliente,))
        total_clientes = cursor.fetchone()[0]
    finally:
        ligacao.close()
    return total_clientes > 0


# --- Recuperação de password (versão simulada) -----------------------------

def gerar_codigo_recuperacao():
    """
    Gera o código aleatório que faz parte do link de recuperação: 32
    caracteres escolhidos ao acaso (com o módulo random) entre letras e
    números.
    """
    caracteres_escolhidos = [random.choice(CARACTERES_CODIGO_RECUPERACAO)
                             for posicao in range(COMPRIMENTO_CODIGO_RECUPERACAO)]
    return "".join(caracteres_escolhidos)


def criar_pedido_recuperacao(email):
    """
    Gera um link de recuperação para a conta com este e-mail e guarda-o na
    base de dados, com validade de 10 minutos.
    Devolve o código do link, ou None se não existir conta com esse e-mail.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT id_cliente FROM clientes WHERE email = ?", (email,))
        cliente = cursor.fetchone()

        if cliente is None:
            return None

        codigo = gerar_codigo_recuperacao()
        data_expiracao = datetime.now() + VALIDADE_LINK_RECUPERACAO

        cursor.execute(
            """
            INSERT INTO recuperacoes_password (id_cliente, codigo, data_expiracao)
            VALUES (?, ?, ?)
            """,
            (cliente["id_cliente"], codigo, data_expiracao.isoformat()),
        )
        ligacao.commit()
    finally:
        # O finally corre sempre, mesmo quando se sai pelo "return None" acima
        ligacao.close()

    return codigo


def obter_recuperacao_valida(codigo):
    """
    Procura o pedido de recuperação com este código e devolve-o apenas se
    ainda for válido (não usado e dentro dos 10 minutos).
    Caso contrário, devolve None.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT * FROM recuperacoes_password WHERE codigo = ?", (codigo,))
        recuperacao = cursor.fetchone()
    finally:
        ligacao.close()

    if recuperacao is None or recuperacao["utilizado"]:
        return None

    # As datas estão guardadas como texto (formato ISO); fromisoformat converte-as
    # de volta para datetime, para poderem ser comparadas (Módulo 4, Unidade 4)
    data_expiracao = datetime.fromisoformat(recuperacao["data_expiracao"])
    if datetime.now() > data_expiracao:
        return None

    return recuperacao


def redefinir_password(recuperacao, nova_password):
    """
    Grava a nova password do cliente e marca como usados todos os links de
    recuperação desse cliente (o link só serve uma vez, e quaisquer outros
    links pedidos anteriormente deixam também de funcionar).
    """
    novo_hash = generate_password_hash(nova_password)

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "UPDATE clientes SET password_hash = ? WHERE id_cliente = ?",
            (novo_hash, recuperacao["id_cliente"]),
        )
        cursor.execute(
            "UPDATE recuperacoes_password SET utilizado = 1 WHERE id_cliente = ?",
            (recuperacao["id_cliente"],),
        )
        ligacao.commit()
    finally:
        ligacao.close()
