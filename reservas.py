"""
Módulo com as regras de negócio das reservas do website "Luxury Wheels".

Contém:
- a regra de disponibilidade automática dos veículos (revisão/legalização);
- a validação das datas de uma reserva;
- o cálculo do resumo da reserva (dias, valor total, km incluídos);
- a validação e o registo das formas de pagamento (cartão, simulado);
- a criação e a consulta das reservas;
- a lista de reservas do cliente, a alteração das datas e o cancelamento,
  com o histórico de pagamentos e reembolsos (Fase 5);
- as horas de levantamento/entrega, os balcões e os extras (Fase 6).

As datas são tratadas com o módulo datetime (Módulo 4, Unidade 4 — Dados
temporais) e guardadas na base de dados como texto no formato ISO
(AAAA-MM-DD). Neste formato, comparar datas como texto dá o mesmo
resultado que compará-las como datas ("2026-10-01" < "2026-10-15"), por
isso as comparações podem ser feitas diretamente no SQL.
"""

from datetime import date, datetime, timedelta

import database

# --- Regras do negócio (definidas para o projeto) ------------------------------

# Duração máxima de um aluguer feito pelo website. Alugueres mais longos
# exigem um contrato especial, tratado diretamente com a empresa.
DURACAO_MAXIMA_DIAS = 30

# Quilómetros incluídos por cada dia de aluguer (informativo: a empresa
# acompanha a quilometragem dos veículos remotamente).
KM_INCLUIDOS_POR_DIA = 200

# Uma legalização é válida durante 1 ano (regra do enunciado).
DIAS_VALIDADE_LEGALIZACAO = 365


def gerar_horas_disponiveis():
    """
    Horas em que se pode levantar ou entregar um veículo (horário dos
    balcões): das 08:00 às 20:00, de 30 em 30 minutos (Fase 6).
    """
    horas = []
    for hora in range(8, 21):
        horas.append(f"{hora:02d}:00")
        if hora < 20:
            horas.append(f"{hora:02d}:30")
    return horas


HORAS_DISPONIVEIS = gerar_horas_disponiveis()
HORA_LEVANTAMENTO_POR_DEFEITO = "10:00"
HORA_ENTREGA_POR_DEFEITO = "18:00"

# Condição SQL que define se um veículo está disponível HOJE. Os quatro "?"
# recebem os valores devolvidos por limites_disponibilidade():
#  - disponivel = 1 -> o veículo não foi bloqueado manualmente (ex.: avaria);
#  - data_proxima_revisao >= hoje -> a revisão ainda não passou;
#  - data_ultima_legalizacao >= hoje - 365 dias -> legalização com menos de 1 ano;
#  - sem reserva ativa que ainda não tenha terminado -> depois de reservado,
#    o veículo deixa de estar disponível para todos os clientes (incluindo o
#    próprio), até a reserva terminar ou ser cancelada (critério técnico 4).
#    A reserva com o id indicado é ignorada: é a que o cliente está a alterar.
CONDICAO_VEICULO_DISPONIVEL = (
    "disponivel = 1 AND data_proxima_revisao >= ? AND data_ultima_legalizacao >= ? "
    "AND id_veiculo NOT IN (SELECT id_veiculo FROM reservas "
    "WHERE estado = 'ativa' AND data_fim >= ? AND id_reserva != ?)"
)


def limites_disponibilidade(id_reserva_ignorar=0):
    """
    Devolve os valores a usar nos "?" de CONDICAO_VEICULO_DISPONIVEL,
    calculados a partir da data de HOJE — é isto que torna a regra
    automática: cada vez que uma página abre, a regra é verificada de novo.

    id_reserva_ignorar: só se usa ao alterar uma reserva (a própria reserva
    não pode tornar o seu veículo indisponível). O valor 0 não corresponde
    a nenhuma reserva, por isso, por defeito, todas as reservas contam.
    """
    hoje = date.today()
    limite_legalizacao = hoje - timedelta(days=DIAS_VALIDADE_LEGALIZACAO)
    return [hoje.isoformat(), limite_legalizacao.isoformat(), hoje.isoformat(), id_reserva_ignorar]


# --- Funções auxiliares de datas -----------------------------------------

def texto_para_data(texto):
    """
    Converte um texto numa data. Aceita dois formatos:
    - DD/MM/AAAA — o formato português, usado pelo calendário das páginas;
    - AAAA-MM-DD — o formato usado internamente nos links entre páginas.
    Devolve None se o texto estiver vazio ou não for uma data válida
    (Módulo 4, Unidade 4 — Dados temporais; Unidade 3 — Exceções).
    """
    if not texto:
        return None
    texto = texto.strip()
    try:
        if "/" in texto:
            # strptime lê o texto segundo o formato indicado (%d dia, %m mês, %Y ano)
            return datetime.strptime(texto, "%d/%m/%Y").date()
        return date.fromisoformat(texto)
    except ValueError:
        return None


def formatar_data(data_valor):
    """
    Formata uma data (ou um texto AAAA-MM-DD vindo da base de dados) no
    formato português DD/MM/AAAA, para mostrar nas páginas. Se o texto
    trouxer também a hora ("AAAA-MM-DD HH:MM:SS"), só a data é usada.
    """
    if isinstance(data_valor, str):
        data_valor = date.fromisoformat(data_valor[:10])
    return data_valor.strftime("%d/%m/%Y")


def contar_dias(data_inicio, data_fim):
    """
    Número de dias do aluguer, contando o dia de início E o dia de fim
    (ex.: de 1 a 3 de outubro = 3 dias; início e fim no mesmo dia = 1 dia).
    """
    return (data_fim - data_inicio).days + 1


def validade_legalizacao(veiculo):
    """Último dia em que a legalização do veículo ainda é válida."""
    data_legalizacao = date.fromisoformat(veiculo["data_ultima_legalizacao"])
    return data_legalizacao + timedelta(days=DIAS_VALIDADE_LEGALIZACAO)


# --- Veículos ------------------------------------------------------------

def obter_veiculo_disponivel(id_veiculo, id_reserva_ignorar=0):
    """
    Devolve o veículo com o id indicado, mas só se estiver disponível hoje
    (bloqueio manual, revisão, legalização e reservas ativas); caso contrário
    devolve None. id_reserva_ignorar: ver limites_disponibilidade().
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "SELECT * FROM veiculos WHERE id_veiculo = ? AND " + CONDICAO_VEICULO_DISPONIVEL,
            [id_veiculo] + limites_disponibilidade(id_reserva_ignorar),
        )
        return cursor.fetchone()
    finally:
        ligacao.close()


def validar_datas_reserva(veiculo, texto_inicio, texto_fim):
    """
    Valida as datas escolhidas para alugar o veículo.

    Devolve um tuplo (erros, data_inicio, data_fim): "erros" é uma lista de
    mensagens (vazia se estiver tudo bem) e as datas já vêm convertidas.

    Regras:
    1. As duas datas têm de ser válidas.
    2. O início não pode ser antes de hoje; o fim não pode ser antes do início.
    3. Máximo de 30 dias (mais do que isso = contrato especial).
    4. O início tem de ser até à data da próxima revisão (se a revisão calhar
       DURANTE o aluguer, é aceite, mas o cliente é avisado de que terá de
       tratar dela — ver calcular_resumo_reserva).
    5. Todo o aluguer tem de estar dentro da validade da legalização (um
       veículo com a legalização expirada não pode circular).

    Não é preciso verificar se as datas se sobrepõem a outra reserva: um
    veículo com uma reserva ativa nem chega a estar disponível (ver
    CONDICAO_VEICULO_DISPONIVEL). As mesmas regras aplicam-se ao alterar as
    datas de uma reserva (Fase 5).
    """
    erros = []
    data_inicio = texto_para_data(texto_inicio)
    data_fim = texto_para_data(texto_fim)

    # Regra 1 — sem datas válidas não faz sentido verificar mais nada
    if data_inicio is None or data_fim is None:
        erros.append("Indique uma data de início e uma data de fim válidas.")
        return erros, data_inicio, data_fim

    # Regra 2
    if data_inicio < date.today():
        erros.append("A data de início não pode ser anterior a hoje.")
    if data_fim < data_inicio:
        erros.append("A data de fim não pode ser anterior à data de início.")
        return erros, data_inicio, data_fim

    # Regra 3
    if contar_dias(data_inicio, data_fim) > DURACAO_MAXIMA_DIAS:
        erros.append(
            f"O aluguer pelo website tem um máximo de {DURACAO_MAXIMA_DIAS} dias. "
            "Para alugueres mais longos, contacte-nos para um contrato especial."
        )

    # Regra 4
    data_proxima_revisao = date.fromisoformat(veiculo["data_proxima_revisao"])
    if data_inicio > data_proxima_revisao:
        erros.append(
            "Este veículo tem uma revisão agendada para "
            f"{formatar_data(data_proxima_revisao)}; o aluguer tem de começar até essa data."
        )

    # Regra 5
    data_validade_legalizacao = validade_legalizacao(veiculo)
    if data_fim > data_validade_legalizacao:
        erros.append(
            "A legalização deste veículo só é válida até "
            f"{formatar_data(data_validade_legalizacao)}; o aluguer tem de terminar até essa data."
        )

    return erros, data_inicio, data_fim


def calcular_resumo_reserva(veiculo, data_inicio, data_fim, extras=()):
    """
    Calcula o resumo mostrado ao cliente ANTES de pagar (requisito do
    enunciado): número de dias, valor das diárias, valor de cada extra
    escolhido (Fase 6), valor total, km incluídos e se a próxima revisão
    calha durante o aluguer.

    Extras "por_dia" são multiplicados pelo número de dias; extras "fixo"
    são pagos uma só vez.
    """
    numero_dias = contar_dias(data_inicio, data_fim)
    data_proxima_revisao = date.fromisoformat(veiculo["data_proxima_revisao"])
    valor_diarias = round(veiculo["valor_diaria"] * numero_dias, 2)

    linhas_extras = []
    valor_extras = 0
    for extra in extras:
        if extra["tipo_preco"] == "por_dia":
            subtotal = round(extra["preco"] * numero_dias, 2)
            descricao = f"{extra['preco']:.2f} € × {numero_dias} dia(s)"
        else:
            subtotal = extra["preco"]
            descricao = "valor fixo"
        linhas_extras.append({"nome": extra["nome"], "descricao": descricao, "subtotal": subtotal})
        valor_extras += subtotal

    return {
        "numero_dias": numero_dias,
        "valor_diarias": valor_diarias,
        "linhas_extras": linhas_extras,
        "valor_extras": round(valor_extras, 2),
        "valor_total": round(valor_diarias + valor_extras, 2),
        "km_incluidos": numero_dias * KM_INCLUIDOS_POR_DIA,
        "revisao_durante_aluguer": data_inicio <= data_proxima_revisao <= data_fim,
        "data_proxima_revisao": data_proxima_revisao,
    }


# --- Horas, balcões e extras (Fase 6) --------------------------------------

def validar_horas(data_inicio, data_fim, hora_levantamento, hora_entrega, agora=None):
    """
    Valida as horas de levantamento e de entrega. Devolve a lista de erros.
    - As horas têm de ser do horário dos balcões (HORAS_DISPONIVEIS).
    - No mesmo dia, a entrega tem de ser depois do levantamento.
    - Se o levantamento for hoje, a hora ainda não pode ter passado.
    O parâmetro opcional "agora" (HH:MM) é, por defeito, a hora atual.
    Nota: as horas no formato HH:MM comparam-se bem como texto ("09:30" < "10:00").
    """
    erros = []
    if hora_levantamento not in HORAS_DISPONIVEIS:
        erros.append("Escolha uma hora de levantamento entre as 08:00 e as 20:00.")
    if hora_entrega not in HORAS_DISPONIVEIS:
        erros.append("Escolha uma hora de entrega entre as 08:00 e as 20:00.")
    if erros or data_inicio is None or data_fim is None:
        return erros

    if data_inicio == data_fim and hora_entrega <= hora_levantamento:
        erros.append("Num aluguer de um só dia, a hora de entrega tem de ser depois da hora de levantamento.")

    if agora is None:
        agora = datetime.now().strftime("%H:%M")
    if data_inicio == date.today() and hora_levantamento <= agora:
        erros.append("Para levantar hoje, escolha uma hora de levantamento que ainda não tenha passado.")
    return erros


def obter_balcoes():
    """Todos os balcões, por ordem de id (para as listas de escolha)."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT * FROM balcoes ORDER BY id_balcao")
        return cursor.fetchall()
    finally:
        ligacao.close()


def obter_balcao(texto_id_balcao):
    """Devolve o balcão com o id indicado (texto vindo do formulário), ou None."""
    if not texto_id_balcao or not str(texto_id_balcao).isdigit():
        return None
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute("SELECT * FROM balcoes WHERE id_balcao = ?", (int(texto_id_balcao),))
        return cursor.fetchone()
    finally:
        ligacao.close()


def obter_extras_para_veiculo(veiculo):
    """
    Extras que podem ser escolhidos para este veículo: nas motos não
    aparecem os extras só para carros (ex.: cadeira de criança).
    """
    instrucao_sql = "SELECT * FROM extras"
    if veiculo["tipo_veiculo"] == "Moto":
        instrucao_sql += " WHERE so_carros = 0"
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(instrucao_sql + " ORDER BY id_extra")
        return cursor.fetchall()
    finally:
        ligacao.close()


def obter_extras_reserva(id_reserva):
    """Extras escolhidos numa reserva (com o preço e o tipo de preço)."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT extras.* FROM reserva_extras
            JOIN extras ON extras.id_extra = reserva_extras.id_extra
            WHERE reserva_extras.id_reserva = ?
            ORDER BY extras.id_extra
            """,
            (id_reserva,),
        )
        return cursor.fetchall()
    finally:
        ligacao.close()


def validar_pedido_reserva(veiculo, dados):
    """
    Valida um pedido de reserva completo, vindo do formulário (textos):
    datas, horas, balcões e extras. "dados" é um dicionário com as chaves
    data_inicio, data_fim, hora_levantamento, hora_entrega,
    balcao_levantamento, balcao_entrega e extras (lista de ids em texto).

    Devolve um tuplo (erros, pedido): "pedido" é um dicionário com os
    valores já convertidos (datas, registos dos balcões e dos extras).
    """
    erros, data_inicio, data_fim = validar_datas_reserva(veiculo, dados["data_inicio"], dados["data_fim"])
    erros += validar_horas(data_inicio, data_fim, dados["hora_levantamento"], dados["hora_entrega"])

    balcao_levantamento = obter_balcao(dados["balcao_levantamento"])
    balcao_entrega = obter_balcao(dados["balcao_entrega"])
    if balcao_levantamento is None:
        erros.append("Escolha o balcão de levantamento.")
    if balcao_entrega is None:
        erros.append("Escolha o balcão de entrega.")

    # Só são aceites extras que existam e que se apliquem a este veículo
    extras_possiveis = obter_extras_para_veiculo(veiculo)
    extras_escolhidos = []
    for extra in extras_possiveis:
        if str(extra["id_extra"]) in dados["extras"]:
            extras_escolhidos.append(extra)
    ids_validos = [str(extra["id_extra"]) for extra in extras_possiveis]
    for texto_id_extra in dados["extras"]:
        if texto_id_extra not in ids_validos:
            erros.append("Um dos extras escolhidos não está disponível para este veículo.")
            break

    pedido = {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "hora_levantamento": dados["hora_levantamento"],
        "hora_entrega": dados["hora_entrega"],
        "balcao_levantamento": balcao_levantamento,
        "balcao_entrega": balcao_entrega,
        "extras": extras_escolhidos,
    }
    return erros, pedido


# --- Formas de pagamento (cartão, simulado) ------------------------------

def validar_cartao(numero_cartao, nome_titular, codigo_seguranca):
    """
    Valida os dados de um cartão novo (validação simples — o pagamento é
    simulado). Devolve a lista de erros (vazia se estiver tudo bem).

    Os espaços no número são aceites (ex.: "1234 5678 9012 3456") e removidos.
    """
    erros = []
    numero_sem_espacos = numero_cartao.replace(" ", "")

    if len(numero_sem_espacos) != 16 or not numero_sem_espacos.isdigit():
        erros.append("O número do cartão deve ter 16 algarismos.")

    nome_sem_espacos = nome_titular.replace(" ", "")
    if len(nome_sem_espacos) < 3 or not nome_sem_espacos.isalpha():
        erros.append("Indique o nome do titular, tal como aparece no cartão (só letras).")

    if len(codigo_seguranca) != 3 or not codigo_seguranca.isdigit():
        erros.append("O código de segurança (CVV) deve ter 3 algarismos.")

    return erros


def obter_formas_pagamento(id_cliente):
    """
    Devolve os cartões que o cliente escolheu guardar (para os poder
    reutilizar). Os cartões não guardados ficam só no histórico.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT * FROM formas_pagamento
            WHERE id_cliente = ? AND guardado = 1
            ORDER BY id_forma_pagamento
            """,
            (id_cliente,),
        )
        return cursor.fetchall()
    finally:
        ligacao.close()


def obter_forma_pagamento_cliente(id_forma_pagamento, id_cliente):
    """
    Devolve a forma de pagamento indicada, mas só se pertencer ao cliente e
    estiver guardada (impede que alguém altere o formulário para usar o
    cartão de outro cliente, ou um cartão que o cliente não quis guardar).
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT * FROM formas_pagamento
            WHERE id_forma_pagamento = ? AND id_cliente = ? AND guardado = 1
            """,
            (id_forma_pagamento, id_cliente),
        )
        return cursor.fetchone()
    finally:
        ligacao.close()


def registar_cartao(id_cliente, numero_cartao, nome_titular, guardar=False):
    """
    Regista um cartão novo e devolve o seu id. Por segurança, guarda APENAS
    os últimos 4 algarismos — nunca o número completo nem o CVV.

    - guardar=True: o cliente escolheu guardar o cartão para próximas
      reservas (aparece na lista de cartões).
    - guardar=False: o cartão fica só no histórico de pagamentos (é preciso
      saber que cartão pagou, para os reembolsos), mas não aparece na lista.
    Se o cliente já tiver o mesmo cartão registado, reutiliza-o (sem duplicar)
    e, se agora o quiser guardar, passa a ficar guardado.
    """
    ultimos_digitos = numero_cartao.replace(" ", "")[-4:]
    nome_titular = nome_titular.strip().upper()

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT id_forma_pagamento FROM formas_pagamento
            WHERE id_cliente = ? AND ultimos_digitos = ? AND nome_titular = ?
            """,
            (id_cliente, ultimos_digitos, nome_titular),
        )
        cartao_existente = cursor.fetchone()
        if cartao_existente:
            if guardar:
                cursor.execute(
                    "UPDATE formas_pagamento SET guardado = 1 WHERE id_forma_pagamento = ?",
                    (cartao_existente["id_forma_pagamento"],),
                )
                ligacao.commit()
            return cartao_existente["id_forma_pagamento"]

        cursor.execute(
            """
            INSERT INTO formas_pagamento (id_cliente, tipo, nome_titular, ultimos_digitos, guardado)
            VALUES (?, 'Cartão', ?, ?, ?)
            """,
            (id_cliente, nome_titular, ultimos_digitos, 1 if guardar else 0),
        )
        ligacao.commit()
        return cursor.lastrowid
    finally:
        ligacao.close()


# --- Reservas -------------------------------------------------------------

def criar_reserva(id_cliente, veiculo, pedido, id_forma_pagamento):
    """
    Cria a reserva (estado "ativa") a partir de um pedido já validado
    (datas, horas, balcões e extras — ver validar_pedido_reserva), grava os
    extras escolhidos, regista o pagamento inicial na tabela de movimentos e
    devolve o id da reserva.

    O valor total é SEMPRE calculado aqui, no servidor, a partir dos preços
    guardados na base de dados — nunca é lido do formulário, para que o
    cliente não o consiga alterar.
    """
    resumo = calcular_resumo_reserva(veiculo, pedido["data_inicio"], pedido["data_fim"], pedido["extras"])

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            INSERT INTO reservas (id_cliente, id_veiculo, data_inicio, data_fim,
                                  hora_levantamento, hora_entrega,
                                  id_balcao_levantamento, id_balcao_entrega,
                                  valor_total, id_forma_pagamento, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ativa')
            """,
            (
                id_cliente, veiculo["id_veiculo"],
                pedido["data_inicio"].isoformat(), pedido["data_fim"].isoformat(),
                pedido["hora_levantamento"], pedido["hora_entrega"],
                pedido["balcao_levantamento"]["id_balcao"], pedido["balcao_entrega"]["id_balcao"],
                resumo["valor_total"], id_forma_pagamento,
            ),
        )
        id_reserva = cursor.lastrowid
        for extra in pedido["extras"]:
            cursor.execute(
                "INSERT INTO reserva_extras (id_reserva, id_extra) VALUES (?, ?)",
                (id_reserva, extra["id_extra"]),
            )
        cursor.execute(
            """
            INSERT INTO pagamentos (id_reserva, id_forma_pagamento, tipo, valor)
            VALUES (?, ?, 'pagamento', ?)
            """,
            (id_reserva, id_forma_pagamento, resumo["valor_total"]),
        )
        # Um só commit para todas as instruções: ou fica tudo gravado, ou nada
        ligacao.commit()
        return id_reserva
    finally:
        ligacao.close()


def obter_reserva_cliente(id_reserva, id_cliente):
    """
    Devolve a reserva com os dados do veículo e do cartão usados, mas só se
    pertencer ao cliente indicado (um cliente nunca vê reservas de outro).
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT reservas.*, veiculos.marca, veiculos.modelo,
                   veiculos.valor_diaria, veiculos.data_proxima_revisao,
                   formas_pagamento.nome_titular, formas_pagamento.ultimos_digitos,
                   balcao_levantamento.nome AS nome_balcao_levantamento,
                   balcao_entrega.nome AS nome_balcao_entrega
            FROM reservas
            JOIN veiculos ON veiculos.id_veiculo = reservas.id_veiculo
            JOIN formas_pagamento
                 ON formas_pagamento.id_forma_pagamento = reservas.id_forma_pagamento
            -- A tabela balcoes entra duas vezes (levantamento e entrega), por
            -- isso cada uma recebe um nome próprio (AS balcao_levantamento / AS balcao_entrega)
            JOIN balcoes AS balcao_levantamento ON balcao_levantamento.id_balcao = reservas.id_balcao_levantamento
            JOIN balcoes AS balcao_entrega ON balcao_entrega.id_balcao = reservas.id_balcao_entrega
            WHERE reservas.id_reserva = ? AND reservas.id_cliente = ?
            """,
            (id_reserva, id_cliente),
        )
        return cursor.fetchone()
    finally:
        ligacao.close()


# --- Fase 5 — lista de reservas, alteração de datas e cancelamento --------

# Ordem pela qual os estados aparecem em "As minhas reservas" (futuras primeiro)
ORDEM_ESTADOS = {"Futura": 0, "A decorrer": 1, "Terminada": 2, "Cancelada": 3}

# Texto mostrado ao cliente para cada tipo de movimento da tabela pagamentos
NOMES_MOVIMENTOS = {
    "pagamento": "Pagamento",
    "diferenca": "Diferença paga",
    "reembolso": "Reembolso",
}


def estado_da_reserva(reserva):
    """
    Estado mostrado ao cliente, calculado a partir das datas e da data de
    hoje: "Futura", "A decorrer", "Terminada" ou "Cancelada". Na base de
    dados só se guarda "ativa" ou "cancelada" — o resto depende do dia de hoje.
    """
    if reserva["estado"] == "cancelada":
        return "Cancelada"
    hoje = date.today().isoformat()
    if reserva["data_inicio"] > hoje:
        return "Futura"
    if reserva["data_fim"] < hoje:
        return "Terminada"
    return "A decorrer"


def pode_alterar_ou_cancelar(reserva):
    """Uma reserva só pode ser alterada ou cancelada antes de começar."""
    return estado_da_reserva(reserva) == "Futura"


def obter_movimentos(id_reserva):
    """Histórico de pagamentos e reembolsos da reserva, do mais antigo para o mais recente."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT pagamentos.*, formas_pagamento.ultimos_digitos, formas_pagamento.nome_titular
            FROM pagamentos
            JOIN formas_pagamento
                 ON formas_pagamento.id_forma_pagamento = pagamentos.id_forma_pagamento
            WHERE pagamentos.id_reserva = ?
            ORDER BY pagamentos.id_pagamento
            """,
            (id_reserva,),
        )
        return cursor.fetchall()
    finally:
        ligacao.close()


def obter_reservas_cliente(id_cliente):
    """
    Devolve TODAS as reservas do cliente (para "As minhas reservas"), cada
    uma como dicionário com os dados do veículo, o estado mostrado, se pode
    ser alterada/cancelada, o número de dias e o histórico de movimentos.
    Ordem: futuras primeiro, depois a decorrer, terminadas e canceladas; em
    cada grupo, pela data de início.
    """
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            SELECT reservas.*, veiculos.marca, veiculos.modelo, veiculos.imagem,
                   balcao_levantamento.nome AS nome_balcao_levantamento,
                   balcao_entrega.nome AS nome_balcao_entrega
            FROM reservas
            JOIN veiculos ON veiculos.id_veiculo = reservas.id_veiculo
            JOIN balcoes AS balcao_levantamento ON balcao_levantamento.id_balcao = reservas.id_balcao_levantamento
            JOIN balcoes AS balcao_entrega ON balcao_entrega.id_balcao = reservas.id_balcao_entrega
            WHERE reservas.id_cliente = ?
            """,
            (id_cliente,),
        )
        registos = cursor.fetchall()
    finally:
        ligacao.close()

    lista_reservas = []
    for registo in registos:
        reserva = dict(registo)  # dicionário, para poder acrescentar informação
        reserva["estado_mostrado"] = estado_da_reserva(registo)
        reserva["pode_alterar"] = pode_alterar_ou_cancelar(registo)
        reserva["numero_dias"] = contar_dias(
            date.fromisoformat(reserva["data_inicio"]), date.fromisoformat(reserva["data_fim"])
        )
        reserva["movimentos"] = obter_movimentos(reserva["id_reserva"])
        reserva["extras"] = obter_extras_reserva(reserva["id_reserva"])
        lista_reservas.append(reserva)

    lista_reservas.sort(
        key=lambda reserva: (ORDEM_ESTADOS[reserva["estado_mostrado"]], reserva["data_inicio"])
    )
    return lista_reservas


def saldo_por_cartao(id_reserva):
    """
    Quanto cada cartão pagou, em termos líquidos, por esta reserva:
    pagamentos e diferenças somam, reembolsos subtraem.

    Devolve uma lista de dicionários (id_forma_pagamento, ultimos_digitos,
    saldo), começando pelo ÚLTIMO cartão usado para pagar — é por esta
    ordem que os reembolsos são feitos. Cartões com saldo 0 não aparecem.
    """
    saldos = {}  # id_forma_pagamento -> dados e saldo desse cartão
    for ordem_movimento, movimento in enumerate(obter_movimentos(id_reserva)):
        id_forma_pagamento = movimento["id_forma_pagamento"]
        if id_forma_pagamento not in saldos:
            saldos[id_forma_pagamento] = {
                "id_forma_pagamento": id_forma_pagamento,
                "ultimos_digitos": movimento["ultimos_digitos"],
                "saldo": 0.0,
                "ultima_utilizacao": 0,
            }
        cartao = saldos[id_forma_pagamento]
        if movimento["tipo"] == "reembolso":
            cartao["saldo"] -= movimento["valor"]
        else:
            cartao["saldo"] += movimento["valor"]
            cartao["ultima_utilizacao"] = ordem_movimento

    cartoes_com_saldo = [cartao for cartao in saldos.values() if round(cartao["saldo"], 2) > 0]
    cartoes_com_saldo.sort(key=lambda cartao: cartao["ultima_utilizacao"], reverse=True)
    return cartoes_com_saldo


def planear_reembolso(id_reserva, valor_a_reembolsar):
    """
    Reparte um reembolso pelos cartões que pagaram a reserva: começa pelo
    último cartão usado e nunca devolve a um cartão mais do que ele pagou.
    Ex.: 75 € no cartão A + 50 € no cartão B; reembolso de 60 € -> 50 € para
    o B e 10 € para o A. Devolve a lista (id_forma_pagamento, ultimos_digitos, valor).
    """
    reembolsos = []
    valor_em_falta = round(valor_a_reembolsar, 2)
    for cartao in saldo_por_cartao(id_reserva):
        if valor_em_falta <= 0:
            break
        valor_deste_cartao = round(min(cartao["saldo"], valor_em_falta), 2)
        reembolsos.append({
            "id_forma_pagamento": cartao["id_forma_pagamento"],
            "ultimos_digitos": cartao["ultimos_digitos"],
            "valor": valor_deste_cartao,
        })
        valor_em_falta = round(valor_em_falta - valor_deste_cartao, 2)
    return reembolsos


def calcular_alteracao(reserva, veiculo, nova_data_inicio, nova_data_fim):
    """
    Resumo de uma alteração de datas: o novo resumo (dias, total, km…), o
    valor já pago, a diferença (positiva = a pagar; negativa = a reembolsar)
    e, se houver reembolso, como fica repartido pelos cartões.
    """
    # Os extras da reserva não mudam, mas o seguro (por dia) é recalculado para os novos dias
    extras = obter_extras_reserva(reserva["id_reserva"])
    resumo = calcular_resumo_reserva(veiculo, nova_data_inicio, nova_data_fim, extras)
    diferenca = round(resumo["valor_total"] - reserva["valor_total"], 2)
    resumo["valor_pago"] = reserva["valor_total"]
    resumo["diferenca"] = diferenca
    if diferenca < 0:
        resumo["reembolsos"] = planear_reembolso(reserva["id_reserva"], -diferenca)
    else:
        resumo["reembolsos"] = []
    return resumo


def registar_reembolsos(cursor, id_reserva, reembolsos):
    """Grava na tabela pagamentos um movimento de reembolso por cada cartão."""
    for reembolso in reembolsos:
        cursor.execute(
            """
            INSERT INTO pagamentos (id_reserva, id_forma_pagamento, tipo, valor)
            VALUES (?, ?, 'reembolso', ?)
            """,
            (id_reserva, reembolso["id_forma_pagamento"], reembolso["valor"]),
        )


def alterar_datas_reserva(reserva, veiculo, nova_data_inicio, nova_data_fim,
                          nova_hora_levantamento, nova_hora_entrega, id_forma_pagamento=None):
    """
    Altera as datas e as horas da reserva e acerta o valor (tudo calculado
    aqui, no servidor): se ficar mais cara, regista a diferença paga com o
    cartão indicado; se ficar mais barata, regista os reembolsos. O veículo,
    os balcões e os extras nunca mudam. Devolve o resumo da alteração.
    """
    alteracao = calcular_alteracao(reserva, veiculo, nova_data_inicio, nova_data_fim)

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            """
            UPDATE reservas
            SET data_inicio = ?, data_fim = ?, hora_levantamento = ?, hora_entrega = ?, valor_total = ?
            WHERE id_reserva = ?
            """,
            (
                nova_data_inicio.isoformat(), nova_data_fim.isoformat(),
                nova_hora_levantamento, nova_hora_entrega,
                alteracao["valor_total"], reserva["id_reserva"],
            ),
        )
        if alteracao["diferenca"] > 0:
            cursor.execute(
                """
                INSERT INTO pagamentos (id_reserva, id_forma_pagamento, tipo, valor)
                VALUES (?, ?, 'diferenca', ?)
                """,
                (reserva["id_reserva"], id_forma_pagamento, alteracao["diferenca"]),
            )
        registar_reembolsos(cursor, reserva["id_reserva"], alteracao["reembolsos"])
        ligacao.commit()
    finally:
        ligacao.close()
    return alteracao


def cancelar_reserva(reserva):
    """
    Cancela a reserva (as datas ficam livres para outros clientes) e
    reembolsa o valor total: cada cartão recebe o que pagou. Devolve a
    lista de reembolsos feitos.
    """
    reembolsos = planear_reembolso(reserva["id_reserva"], reserva["valor_total"])

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "UPDATE reservas SET estado = 'cancelada' WHERE id_reserva = ?",
            (reserva["id_reserva"],),
        )
        registar_reembolsos(cursor, reserva["id_reserva"], reembolsos)
        ligacao.commit()
    finally:
        ligacao.close()
    return reembolsos


# --- Página inicial (Fase 6) -----------------------------------------------

def obter_estatisticas():
    """Números reais mostrados nos contadores da página inicial."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM veiculos WHERE " + CONDICAO_VEICULO_DISPONIVEL,
            limites_disponibilidade(),
        )
        total_veiculos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clientes")
        total_clientes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reservas")
        total_reservas = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM balcoes")
        total_balcoes = cursor.fetchone()[0]
    finally:
        ligacao.close()
    return {
        "veiculos": total_veiculos,
        "clientes": total_clientes,
        "reservas": total_reservas,
        "balcoes": total_balcoes,
    }


def obter_veiculos_destaque(quantidade=4):
    """Os veículos disponíveis com a diária mais alta (destaques da página inicial)."""
    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(
            "SELECT * FROM veiculos WHERE " + CONDICAO_VEICULO_DISPONIVEL
            + " ORDER BY valor_diaria DESC LIMIT ?",
            limites_disponibilidade() + [quantidade],
        )
        return cursor.fetchall()
    finally:
        ligacao.close()

