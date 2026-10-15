"""
Luxury Wheels — Website de aluguer de veículos (Projeto Final, Proposta A)

Fases concluídas:
  - Fase 1: esqueleto da aplicação Flask ligado à base de dados SQLite.
  - Fase 2: registo, login/logout, recuperação de password (simulada) e
            proteção das páginas que exigem sessão iniciada.
  - Fase 3: pesquisa e filtros na lista de veículos (marca/modelo, categoria,
            tipo de veículo, transmissão, valor da diária e nº de pessoas).
  - Fase 4: efetuar aluguer (escolha das datas), pagamento simulado com
            cartão e página de confirmação da reserva; regra automática de
            disponibilidade (revisão/legalização calculadas com a data de hoje).
  - Fase 5: "As minhas reservas" (todas as reservas, com estado e histórico
            de pagamentos), alteração das datas (com pagamento ou reembolso
            da diferença) e cancelamento (com reembolso total); filtro de
            pessoas por faixas (1 a 4, 5 a 6, 7 ou mais).
  - Fase 6: página inicial (/) e lista de veículos em /veiculos; página de
            contactos; 16 veículos; horas de levantamento/entrega, balcões e
            extras na reserva; calendário em português (dd/mm/aaaa).

Para correr a aplicação localmente:
    python app.py
E depois abrir no browser: http://127.0.0.1:5000
"""

from datetime import date

from flask import (
    Flask, render_template, redirect, url_for, flash, request, session, abort,
)

import autenticacao
import contactos
import database
import reservas

# --- Configuração da aplicação -------------------------------------------

# static_folder="assets": reaproveita a pasta de imagens/CSS/JS já existente
# (a mesma que vinha com o template HTML fornecido), em vez de duplicar os
# ficheiros numa pasta "static" separada.
aplicacao = Flask(__name__, static_folder="assets")

# Chave secreta usada pelo Flask para assinar a sessão e as mensagens
# flash. Num projeto real nunca se deixaria uma chave fixa no código-fonte,
# mas para este projeto académico, correndo apenas localmente, é suficiente.
aplicacao.secret_key = "luxury-wheels-projeto-final-chave-secreta"

# Torna a função formatar_data utilizável nos templates como filtro:
# {{ reserva.data_inicio|data_pt }} mostra a data como DD/MM/AAAA.
aplicacao.jinja_env.filters["data_pt"] = reservas.formatar_data

# Redes sociais que aparecem como botões na página de login (apenas
# demonstrativos — ver rota "login_social").
REDES_SOCIAIS = {
    "facebook": "Facebook",
    "google": "Google",
    "x": "X",
}

# Opções dos filtros da lista de veículos (Fase 3). Correspondem exatamente
# aos valores aceites pela restrição CHECK das colunas respetivas em
# schema.sql, para que nunca seja possível escolher um valor inválido.
CATEGORIAS_VEICULOS = ["Pequeno", "Médio", "Grande", "SUV", "Luxo"]
TIPOS_VEICULOS = ["Carro", "Moto"]
TRANSMISSOES_VEICULOS = ["Automático", "Manual"]

# Faixas do filtro "quantidade de pessoas", tal como no enunciado
# ("1-4, 5-6, mais de 7"). "Mais de 7" é tratado como "7 ou mais", para que
# um veículo de 7 lugares não fique de fora de todas as faixas.
# Cada faixa: código usado no URL -> (texto mostrado, mínimo, máximo)
FAIXAS_PESSOAS = {
    "1-4": ("1 a 4", 1, 4),
    "5-6": ("5 a 6", 5, 6),
    "7+": ("7 ou mais", 7, None),  # None = sem máximo
}


# --- Funções auxiliares diversas ------------------------------------------

def texto_para_numero(texto):
    """
    Tenta converter um texto (vindo de um campo do formulário de pesquisa)
    num número. Devolve None se o texto estiver vazio ou não for um número
    válido, para que esse filtro seja simplesmente ignorado (Módulo 4,
    Unidade 3 — Exceções).
    """
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def data_para_mostrar(texto):
    """
    Devolve a data no formato DD/MM/AAAA, para aparecer assim nos campos de
    data (o calendário usa este formato). Se o texto não for uma data
    válida, devolve-o tal como está, para o cliente ver o que escreveu.
    """
    data_valor = reservas.texto_para_data(texto)
    if data_valor is None:
        return texto
    return reservas.formatar_data(data_valor)


# --- Funções auxiliares de sessão ----------------------------------------

def iniciar_sessao_cliente(cliente):
    """
    Guarda na sessão os dados do cliente autenticado.

    A sessão é limpa antes, para que nenhum dado de uma sessão anterior
    (por exemplo, de outro utilizador no mesmo browser) se misture com a nova.
    """
    session.clear()
    session["id_cliente"] = cliente["id_cliente"]
    session["nome_cliente"] = cliente["nome"]


def endereco_seguro(endereco):
    """
    Confirma que o endereço de destino (parâmetro "proximo") é uma página
    interna do próprio site — começa por "/" mas não por "//".

    Sem esta verificação, alguém poderia criar um link de login que, depois
    de o cliente se autenticar, o reencaminhasse para um site externo
    malicioso (ataque conhecido como "open redirect").
    """
    return bool(endereco) and endereco.startswith("/") and not endereco.startswith("//")


def redirecionar_apos_autenticacao(proximo):
    """Volta à página onde o cliente estava, ou à lista de veículos."""
    if endereco_seguro(proximo):
        return redirect(proximo)
    return redirect(url_for("lista_veiculos"))


def exigir_sessao_iniciada():
    """
    Protege as páginas que exigem sessão iniciada. Deve ser chamada no início
    de cada uma dessas páginas:

        redirecionamento_login = exigir_sessao_iniciada()
        if redirecionamento_login:
            return redirecionamento_login

    - Se o cliente tiver sessão iniciada, devolve None e a página continua.
    - Se não tiver, devolve um redirecionamento para o login, levando consigo
      o endereço da página que o cliente queria abrir (parâmetro "proximo");
      assim, depois de se autenticar, volta exatamente a essa página
      (Jornada 1 dos wireframes do formador).
    """
    if "id_cliente" in session:
        return None

    flash("Inicie sessão para continuar.", "erro")
    # full_path inclui os parâmetros do endereço (ex.: "/reservas?x=1");
    # o rstrip remove o "?" que o Flask acrescenta quando não há nenhum.
    pagina_pretendida = request.full_path.rstrip("?")
    return redirect(url_for("iniciar_sessao", proximo=pagina_pretendida))


# --- Validação da sessão antes de cada página ----------------------------

@aplicacao.before_request
def validar_sessao():
    """
    Corre ANTES de cada página. Se a sessão indicar um cliente que já não
    existe na base de dados (acontece se a BD for recriada enquanto o
    browser ainda tem a sessão antiga), termina essa sessão — em vez de o
    site dar erro ao tentar gravar dados de um cliente inexistente.
    Os pedidos de ficheiros estáticos (CSS, JS, imagens) são ignorados, para
    não consultar a base de dados dezenas de vezes por página.
    """
    if request.endpoint == "static":
        return None
    if "id_cliente" in session and not autenticacao.cliente_existe(session["id_cliente"]):
        session.clear()
        flash("A sua sessão já não é válida. Inicie sessão novamente.", "erro")
    return None


# --- Disponibiliza informação de sessão a todos os templates --------------

@aplicacao.context_processor
def injetar_dados_sessao():
    """
    Torna disponíveis, em todos os templates, as variáveis que indicam se o
    cliente tem sessão iniciada e qual o seu nome (usadas no menu).
    """
    return {
        "utilizador_autenticado": "id_cliente" in session,
        "nome_utilizador": session.get("nome_cliente"),
    }


# --- Página inicial (pública, Fase 6) ------------------------------------

@aplicacao.route("/")
def pagina_inicial():
    """
    Página inicial do website (baseada no index.html do template): banner
    com pesquisa rápida, apresentação da empresa, contadores com números
    reais da base de dados e os veículos em destaque.
    """
    return render_template(
        "inicio.html",
        estatisticas=reservas.obter_estatisticas(),
        destaques=reservas.obter_veiculos_destaque(4),
        categorias=CATEGORIAS_VEICULOS,
        tipos_veiculos=TIPOS_VEICULOS,
    )


# --- Lista de veículos (pública) ----------------------------------------

@aplicacao.route("/veiculos")
def lista_veiculos():
    """
    Lista de veículos: lista, pesquisa e filtra os veículos disponíveis para
    aluguer (Fase 3). É uma página pública, tal como definido na arquitetura
    do projeto (não exige sessão iniciada).

    Os filtros vêm do URL (método GET, ?pesquisa=...&categoria=...), para que
    a pesquisa possa ser partilhada por link ou reaberta com o botão "Voltar"
    do browser. Quando o cliente preenche mais do que um filtro, TODOS têm de
    ser cumpridos ao mesmo tempo (lógica E), e a pesquisa por marca/modelo é
    parcial (não é preciso escrever o nome todo).
    """
    # Valores escolhidos pelo cliente nos filtros; texto vazio = sem filtro
    texto_pesquisado = request.args.get("pesquisa", "").strip()
    categoria_escolhida = request.args.get("categoria", "")
    tipo_escolhido = request.args.get("tipo_veiculo", "")
    transmissao_escolhida = request.args.get("transmissao", "")
    valor_minimo = texto_para_numero(request.args.get("valor_min", ""))
    valor_maximo = texto_para_numero(request.args.get("valor_max", ""))
    faixa_pessoas = request.args.get("pessoas", "")

    # Lista de condições da consulta SQL e respetivos parâmetros. Começa
    # sempre por só considerar veículos disponíveis HOJE (regra automática
    # de revisão/legalização — ver reservas.CONDICAO_VEICULO_DISPONIVEL).
    condicoes = [reservas.CONDICAO_VEICULO_DISPONIVEL]
    parametros = reservas.limites_disponibilidade()

    if texto_pesquisado:
        # LIKE com "%" dos dois lados -> pesquisa parcial na marca OU no modelo
        texto_como_padrao = "%" + texto_pesquisado + "%"
        condicoes.append("(marca LIKE ? OR modelo LIKE ?)")
        parametros.append(texto_como_padrao)
        parametros.append(texto_como_padrao)

    if categoria_escolhida in CATEGORIAS_VEICULOS:
        condicoes.append("categoria = ?")
        parametros.append(categoria_escolhida)

    if tipo_escolhido in TIPOS_VEICULOS:
        condicoes.append("tipo_veiculo = ?")
        parametros.append(tipo_escolhido)

    if transmissao_escolhida in TRANSMISSOES_VEICULOS:
        condicoes.append("transmissao = ?")
        parametros.append(transmissao_escolhida)

    if valor_minimo is not None:
        condicoes.append("valor_diaria >= ?")
        parametros.append(valor_minimo)

    if valor_maximo is not None:
        condicoes.append("valor_diaria <= ?")
        parametros.append(valor_maximo)

    if faixa_pessoas in FAIXAS_PESSOAS:
        texto_faixa, pessoas_minimo, pessoas_maximo = FAIXAS_PESSOAS[faixa_pessoas]
        condicoes.append("quantidade_pessoas >= ?")
        parametros.append(pessoas_minimo)
        if pessoas_maximo is not None:
            condicoes.append("quantidade_pessoas <= ?")
            parametros.append(pessoas_maximo)

    # Junta todas as condições com "AND": um veículo só aparece na lista se
    # cumprir TODOS os filtros escolhidos. Os veículos são ordenados pelo
    # valor da diária, do mais barato ao mais caro.
    instrucao_sql = (
        "SELECT * FROM veiculos WHERE " + " AND ".join(condicoes)
        + " ORDER BY valor_diaria ASC"
    )

    ligacao = database.obter_ligacao()
    try:
        cursor = ligacao.cursor()
        cursor.execute(instrucao_sql, parametros)
        veiculos_encontrados = cursor.fetchall()
    finally:
        ligacao.close()

    # Dicionário com os filtros escolhidos, para o template conseguir voltar
    # a mostrá-los preenchidos no formulário depois da pesquisa.
    filtros = {
        "pesquisa": texto_pesquisado,
        "categoria": categoria_escolhida,
        "tipo_veiculo": tipo_escolhido,
        "transmissao": transmissao_escolhida,
        "valor_min": request.args.get("valor_min", ""),
        "valor_max": request.args.get("valor_max", ""),
        "pessoas": faixa_pessoas,
    }

    return render_template(
        "lista_veiculos.html",
        veiculos=veiculos_encontrados,
        filtros=filtros,
        categorias=CATEGORIAS_VEICULOS,
        tipos_veiculos=TIPOS_VEICULOS,
        transmissoes=TRANSMISSOES_VEICULOS,
        faixas_pessoas=FAIXAS_PESSOAS,
    )


# --- Registo, login e logout (Fase 2) ------------------------------------

@aplicacao.route("/registo", methods=["GET", "POST"])
def registar():
    """
    GET: mostra o formulário de registo.
    POST: valida os dados, cria a conta e inicia logo a sessão do novo
    cliente, devolvendo-o à página onde estava (se aplicável).
    """
    if "id_cliente" in session:
        return redirect(url_for("lista_veiculos"))

    proximo = request.values.get("proximo", "")

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        utilizador = request.form.get("utilizador", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirmacao_password = request.form.get("confirmacao_password", "")
        quer_newsletter = request.form.get("newsletter") == "sim"

        erros = autenticacao.validar_dados_registo(
            nome, utilizador, email, password, confirmacao_password
        )

        if erros:
            for mensagem_erro in erros:
                flash(mensagem_erro, "erro")
            # Volta a mostrar o formulário, mantendo o que o cliente já
            # escreveu (exceto as passwords, por segurança).
            return render_template(
                "registo.html",
                proximo=proximo,
                nome=nome,
                utilizador=utilizador,
                email=email,
                quer_newsletter=quer_newsletter,
            )

        novo_cliente = autenticacao.criar_cliente(
            nome, utilizador, email, password, quer_newsletter
        )
        iniciar_sessao_cliente(novo_cliente)
        flash(f"Conta criada com sucesso. Bem-vindo(a), {novo_cliente['nome']}!", "sucesso")
        return redirecionar_apos_autenticacao(proximo)

    return render_template("registo.html", proximo=proximo)


@aplicacao.route("/login", methods=["GET", "POST"])
def iniciar_sessao():
    """
    GET: mostra o formulário de login.
    POST: verifica o nome de utilizador e a password; se estiverem certos,
    inicia a sessão e volta à página onde o cliente estava.
    """
    if "id_cliente" in session:
        return redirect(url_for("lista_veiculos"))

    proximo = request.values.get("proximo", "")

    if request.method == "POST":
        utilizador = request.form.get("utilizador", "").strip()
        password = request.form.get("password", "")

        cliente = autenticacao.autenticar_cliente(utilizador, password)

        if cliente is None:
            flash("Nome de utilizador ou password incorretos.", "erro")
            return render_template("login.html", proximo=proximo, utilizador=utilizador)

        iniciar_sessao_cliente(cliente)
        flash(f"Sessão iniciada. Olá, {cliente['nome']}!", "sucesso")
        return redirecionar_apos_autenticacao(proximo)

    return render_template("login.html", proximo=proximo)


@aplicacao.route("/logout")
def terminar_sessao():
    """Termina a sessão do cliente, apagando todos os dados guardados nela."""
    session.clear()
    flash("Sessão terminada.", "sucesso")
    return redirect(url_for("lista_veiculos"))


@aplicacao.route("/login-social/<rede>")
def login_social(rede):
    """
    Página demonstrativa dos botões de login com redes sociais.

    Os botões existem no template original; foram mantidos para mostrar o que
    seria possível fazer, mas esta funcionalidade não faz parte dos requisitos
    do projeto e não está implementada.
    """
    nome_rede = REDES_SOCIAIS.get(rede)
    if nome_rede is None:
        abort(404)

    proximo = request.args.get("proximo", "")
    return render_template("login_social.html", nome_rede=nome_rede, proximo=proximo)


# --- Recuperação de password (versão simulada) ---------------------------

@aplicacao.route("/recuperar-password", methods=["GET", "POST"])
def recuperar_password():
    """
    GET: mostra o formulário onde o cliente indica o seu e-mail.
    POST: gera um link de recuperação válido durante 10 minutos.

    Versão simulada: num site real, o link seria enviado por e-mail; aqui é
    mostrado diretamente no ecrã, porque o projeto não tem servidor de e-mail.
    """
    link_recuperacao = None
    email = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        codigo = autenticacao.criar_pedido_recuperacao(email)

        if codigo is None:
            flash("Não existe nenhuma conta registada com esse e-mail.", "erro")
        else:
            link_recuperacao = url_for("redefinir_password", codigo=codigo, _external=True)

    return render_template(
        "recuperar_password.html",
        link_recuperacao=link_recuperacao,
        email=email,
        minutos_validade=int(autenticacao.VALIDADE_LINK_RECUPERACAO.total_seconds() // 60),
    )


@aplicacao.route("/redefinir-password/<codigo>", methods=["GET", "POST"])
def redefinir_password(codigo):
    """
    GET: mostra o formulário para escolher a nova password (se o link for válido).
    POST: valida a nova password, grava-a e inutiliza o link.
    """
    recuperacao = autenticacao.obter_recuperacao_valida(codigo)

    if recuperacao is None:
        flash("Este link de recuperação é inválido, já foi usado ou expirou. Peça um novo.", "erro")
        return redirect(url_for("recuperar_password"))

    if request.method == "POST":
        nova_password = request.form.get("password", "")
        confirmacao_password = request.form.get("confirmacao_password", "")

        erros = autenticacao.validar_password(nova_password, confirmacao_password)
        if erros:
            for mensagem_erro in erros:
                flash(mensagem_erro, "erro")
            return render_template("redefinir_password.html", codigo=codigo)

        autenticacao.redefinir_password(recuperacao, nova_password)
        flash("Password alterada com sucesso. Já pode iniciar sessão.", "sucesso")
        return redirect(url_for("iniciar_sessao"))

    return render_template("redefinir_password.html", codigo=codigo)


# --- Escolha da forma de pagamento (usada nas Fases 4, 5 e 6) ------------

def escolha_pagamento_por_defeito(formas_pagamento):
    """Por defeito fica escolhido o cartão guardado mais recente (ou "novo", se não houver nenhum)."""
    if formas_pagamento:
        return str(formas_pagamento[-1]["id_forma_pagamento"])
    return "novo"


def obter_forma_pagamento_escolhida(id_cliente):
    """
    Lê do formulário a forma de pagamento escolhida (um cartão guardado ou
    um cartão novo) e devolve um tuplo (id_forma_pagamento, erros).

    - Cartão novo: valida os dados e, se estiverem certos, regista-o (só os
      últimos 4 algarismos) — guardado para próximas reservas apenas se o
      cliente marcar essa opção (desmarcada por defeito).
    - Cartão guardado: confirma que existe e que pertence a este cliente
      (impede o uso do cartão de outra pessoa alterando o formulário).
    """
    escolha_pagamento = request.form.get("forma_pagamento", "")

    if escolha_pagamento == "novo":
        numero_cartao = request.form.get("numero_cartao", "").strip()
        nome_titular = request.form.get("nome_titular", "").strip()
        codigo_seguranca = request.form.get("codigo_seguranca", "").strip()
        # A caixa "Guardar este cartão" só é enviada pelo browser se estiver marcada
        guardar_cartao = request.form.get("guardar_cartao") == "sim"
        erros = reservas.validar_cartao(numero_cartao, nome_titular, codigo_seguranca)
        if erros:
            return None, erros
        return reservas.registar_cartao(id_cliente, numero_cartao, nome_titular, guardar_cartao), []

    forma_escolhida = None
    if escolha_pagamento.isdigit():
        forma_escolhida = reservas.obter_forma_pagamento_cliente(int(escolha_pagamento), id_cliente)
    if forma_escolhida is None:
        return None, ["Escolha uma forma de pagamento válida."]
    return forma_escolhida["id_forma_pagamento"], []


# --- Reserva e pagamento (Fases 4 e 6) — exigem sessão iniciada ----------

def ler_dados_pedido():
    """
    Lê do formulário (ou do URL) os dados de um pedido de reserva, tal como
    vêm do browser (texto): datas, horas, balcões e extras escolhidos.
    request.values junta os dados do URL (GET) e do formulário (POST);
    getlist() devolve todos os valores de um campo que pode repetir-se
    (uma caixa de extra marcada = um valor "extras").
    """
    return {
        "data_inicio": request.values.get("data_inicio", ""),
        "data_fim": request.values.get("data_fim", ""),
        "hora_levantamento": request.values.get(
            "hora_levantamento", reservas.HORA_LEVANTAMENTO_POR_DEFEITO
        ),
        "hora_entrega": request.values.get("hora_entrega", reservas.HORA_ENTREGA_POR_DEFEITO),
        "balcao_levantamento": request.values.get("balcao_levantamento", ""),
        "balcao_entrega": request.values.get("balcao_entrega", ""),
        "extras": request.values.getlist("extras"),
    }


def parametros_pedido(pedido):
    """
    Converte um pedido já validado nos parâmetros que seguem no URL (e nos
    campos escondidos do formulário) para o passo seguinte. As datas vão no
    formato interno AAAA-MM-DD.
    """
    return {
        "data_inicio": pedido["data_inicio"].isoformat(),
        "data_fim": pedido["data_fim"].isoformat(),
        "hora_levantamento": pedido["hora_levantamento"],
        "hora_entrega": pedido["hora_entrega"],
        "balcao_levantamento": pedido["balcao_levantamento"]["id_balcao"],
        "balcao_entrega": pedido["balcao_entrega"]["id_balcao"],
        "extras": [extra["id_extra"] for extra in pedido["extras"]],
    }


@aplicacao.route("/veiculos/<int:id_veiculo>/alugar", methods=["GET", "POST"])
def efetuar_aluguer(id_veiculo):
    """
    Página "Efetuar Aluguer": mostra o veículo escolhido e o formulário do
    pedido: datas e horas de levantamento e de entrega, balcões e extras (Fase 6).

    Exige sessão iniciada. Um visitante que clique em "Efetuar aluguer" na
    lista é enviado para o login e, depois de entrar, volta a esta página
    com o mesmo veículo (Jornada 1 dos wireframes do formador).
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    veiculo = reservas.obter_veiculo_disponivel(id_veiculo)
    if veiculo is None:
        flash("Este veículo não está disponível para reserva.", "erro")
        return redirect(url_for("lista_veiculos"))

    dados = ler_dados_pedido()

    if request.method == "POST":
        erros, pedido = reservas.validar_pedido_reserva(veiculo, dados)
        if not erros:
            # Pedido válido: segue para o pagamento, levando as escolhas no URL.
            # "**" passa cada par chave/valor do dicionário como um argumento.
            return redirect(url_for("pagamento", id_veiculo=id_veiculo, **parametros_pedido(pedido)))
        for erro in erros:
            flash(erro, "erro")

    return render_template(
        "efetuar_aluguer.html",
        veiculo=veiculo,
        validade_legalizacao=reservas.validade_legalizacao(veiculo),
        dados=dados,
        data_inicio=data_para_mostrar(dados["data_inicio"]),
        data_fim=data_para_mostrar(dados["data_fim"]),
        horas=reservas.HORAS_DISPONIVEIS,
        balcoes=reservas.obter_balcoes(),
        extras=reservas.obter_extras_para_veiculo(veiculo),
        duracao_maxima=reservas.DURACAO_MAXIMA_DIAS,
        km_por_dia=reservas.KM_INCLUIDOS_POR_DIA,
    )


@aplicacao.route("/veiculos/<int:id_veiculo>/pagamento", methods=["GET", "POST"])
def pagamento(id_veiculo):
    """
    Página de Pagamento: mostra o resumo da reserva (datas, horas, balcões,
    diárias, extras e valor total — requisito do enunciado: o total aparece
    ANTES de pagar) e pede a forma de pagamento (cartão guardado ou novo).

    O pedido é validado outra vez, tanto ao abrir a página como ao pagar:
    entre a escolha das datas e o pagamento, outro cliente pode ter
    reservado o mesmo veículo para essas datas.
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    veiculo = reservas.obter_veiculo_disponivel(id_veiculo)
    if veiculo is None:
        flash("Este veículo não está disponível para reserva.", "erro")
        return redirect(url_for("lista_veiculos"))

    dados = ler_dados_pedido()
    erros_pedido, pedido = reservas.validar_pedido_reserva(veiculo, dados)
    if erros_pedido:
        for erro in erros_pedido:
            flash(erro, "erro")
        return redirect(url_for("efetuar_aluguer", id_veiculo=id_veiculo, **dados))

    id_cliente = session["id_cliente"]
    formas_pagamento = reservas.obter_formas_pagamento(id_cliente)

    escolha_pagamento = request.form.get(
        "forma_pagamento", escolha_pagamento_por_defeito(formas_pagamento)
    )
    nome_titular = request.form.get("nome_titular", "").strip()

    if request.method == "POST":
        id_forma_pagamento, erros_pagamento = obter_forma_pagamento_escolhida(id_cliente)

        if not erros_pagamento:
            id_reserva = reservas.criar_reserva(id_cliente, veiculo, pedido, id_forma_pagamento)
            flash("Pagamento concluído. A sua reserva está confirmada!", "sucesso")
            return redirect(url_for("confirmacao_reserva", id_reserva=id_reserva))

        for erro in erros_pagamento:
            flash(erro, "erro")

    return render_template(
        "pagamento.html",
        veiculo=veiculo,
        pedido=pedido,
        parametros=parametros_pedido(pedido),
        resumo=reservas.calcular_resumo_reserva(
            veiculo, pedido["data_inicio"], pedido["data_fim"], pedido["extras"]
        ),
        formas_pagamento=formas_pagamento,
        escolha_pagamento=escolha_pagamento,
        nome_titular=nome_titular,
        guardar_cartao=request.form.get("guardar_cartao") == "sim",
        km_por_dia=reservas.KM_INCLUIDOS_POR_DIA,
    )


@aplicacao.route("/reservas/<int:id_reserva>/confirmacao")
def confirmacao_reserva(id_reserva):
    """
    Página "Reserva concluída", mostrada depois do pagamento. Só o cliente
    que fez a reserva a pode ver (para outro cliente, a página "não existe").
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    reserva = reservas.obter_reserva_cliente(id_reserva, session["id_cliente"])
    if reserva is None:
        abort(404)

    resumo = reservas.calcular_resumo_reserva(
        reserva,
        date.fromisoformat(reserva["data_inicio"]),
        date.fromisoformat(reserva["data_fim"]),
        reservas.obter_extras_reserva(id_reserva),
    )
    return render_template("confirmacao_reserva.html", reserva=reserva, resumo=resumo)


# --- As minhas reservas: lista, alteração e cancelamento (Fase 5) --------

def obter_reserva_alteravel(id_reserva):
    """
    Devolve um tuplo (reserva, redirecionamento) para as páginas de alterar
    e cancelar:
    - a reserva tem de pertencer ao cliente com sessão (senão: 404);
    - só pode ser alterada/cancelada antes de começar (senão: volta à lista
      com uma mensagem de erro, no "redirecionamento").
    """
    reserva = reservas.obter_reserva_cliente(id_reserva, session["id_cliente"])
    if reserva is None:
        abort(404)
    if reserva["estado"] == "cancelada":
        flash("Esta reserva já foi cancelada.", "erro")
        return reserva, redirect(url_for("lista_reservas"))
    if not reservas.pode_alterar_ou_cancelar(reserva):
        flash(
            "Esta reserva já não pode ser alterada nem cancelada: "
            "só é possível antes da data de início.",
            "erro",
        )
        return reserva, redirect(url_for("lista_reservas"))
    return reserva, None


def obter_veiculo_da_reserva(reserva):
    """
    Devolve o veículo da reserva, se continuar disponível. As novas datas de
    uma alteração cumprem as mesmas regras de uma reserva nova (Fase 4),
    incluindo a disponibilidade do veículo.
    """
    # A própria reserva não conta: senão o veículo estaria sempre "reservado".
    veiculo = reservas.obter_veiculo_disponivel(
        reserva["id_veiculo"], id_reserva_ignorar=reserva["id_reserva"]
    )
    if veiculo is None:
        flash(
            "O veículo desta reserva está temporariamente indisponível, por isso as datas "
            "não podem ser alteradas. Pode cancelar a reserva, com reembolso total.",
            "erro",
        )
    return veiculo


def texto_reembolsos(reembolsos):
    """Ex.: "50.00 € para o cartão terminado em 1111 e 10.00 € para o cartão terminado em 3456"."""
    partes = []
    for reembolso in reembolsos:
        partes.append(
            f"{reembolso['valor']:.2f} € para o cartão terminado em {reembolso['ultimos_digitos']}"
        )
    return " e ".join(partes)


@aplicacao.route("/reservas")
def lista_reservas():
    """
    "As minhas reservas": todas as reservas do cliente (futuras, a decorrer,
    terminadas e canceladas), com o histórico de pagamentos e reembolsos.
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    return render_template(
        "lista_reservas.html",
        reservas_cliente=reservas.obter_reservas_cliente(session["id_cliente"]),
        nomes_movimentos=reservas.NOMES_MOVIMENTOS,
    )


@aplicacao.route("/reservas/<int:id_reserva>/alterar", methods=["GET", "POST"])
def alterar_reserva(id_reserva):
    """
    Alteração da Reserva: o cliente escolhe novas datas e horas (o veículo,
    os balcões e os extras nunca mudam — regra do enunciado e decisão da
    Fase 6). Se forem válidas, segue para a confirmação, onde vê a diferença
    a pagar ou a reembolsar.
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    reserva, redirecionamento = obter_reserva_alteravel(id_reserva)
    if redirecionamento:
        return redirecionamento
    veiculo = obter_veiculo_da_reserva(reserva)
    if veiculo is None:
        return redirect(url_for("lista_reservas"))

    # Por defeito, o formulário mostra as datas e as horas atuais da reserva
    texto_inicio = request.values.get("data_inicio", reserva["data_inicio"])
    texto_fim = request.values.get("data_fim", reserva["data_fim"])
    hora_levantamento = request.values.get("hora_levantamento", reserva["hora_levantamento"])
    hora_entrega = request.values.get("hora_entrega", reserva["hora_entrega"])

    if request.method == "POST":
        erros, data_inicio, data_fim = reservas.validar_datas_reserva(
            veiculo, texto_inicio, texto_fim
        )
        erros += reservas.validar_horas(data_inicio, data_fim, hora_levantamento, hora_entrega)
        if (not erros and data_inicio.isoformat() == reserva["data_inicio"]
                and data_fim.isoformat() == reserva["data_fim"]
                and hora_levantamento == reserva["hora_levantamento"]
                and hora_entrega == reserva["hora_entrega"]):
            erros = ["As datas e as horas escolhidas são iguais às atuais."]
        if not erros:
            return redirect(url_for(
                "confirmar_alteracao", id_reserva=id_reserva,
                data_inicio=data_inicio.isoformat(), data_fim=data_fim.isoformat(),
                hora_levantamento=hora_levantamento, hora_entrega=hora_entrega,
            ))
        for erro in erros:
            flash(erro, "erro")

    return render_template(
        "alterar_reserva.html",
        reserva=reserva,
        veiculo=veiculo,
        validade_legalizacao=reservas.validade_legalizacao(veiculo),
        data_inicio=data_para_mostrar(texto_inicio),
        data_fim=data_para_mostrar(texto_fim),
        hora_levantamento=hora_levantamento,
        hora_entrega=hora_entrega,
        horas=reservas.HORAS_DISPONIVEIS,
        duracao_maxima=reservas.DURACAO_MAXIMA_DIAS,
    )


@aplicacao.route("/reservas/<int:id_reserva>/confirmar-alteracao", methods=["GET", "POST"])
def confirmar_alteracao(id_reserva):
    """
    Confirmação da alteração das datas, com o acerto do valor:
    - mais cara  -> novo passo de pagamento da diferença (cartão guardado ou novo);
    - mais barata -> reembolso da diferença, repartido pelos cartões que pagaram;
    - igual       -> só confirma.
    Tudo é validado e calculado outra vez no servidor no momento de confirmar.
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    reserva, redirecionamento = obter_reserva_alteravel(id_reserva)
    if redirecionamento:
        return redirecionamento
    veiculo = obter_veiculo_da_reserva(reserva)
    if veiculo is None:
        return redirect(url_for("lista_reservas"))

    texto_inicio = request.values.get("data_inicio", "")
    texto_fim = request.values.get("data_fim", "")
    # Se as horas não vierem no pedido, mantêm-se as atuais da reserva
    hora_levantamento = request.values.get("hora_levantamento", reserva["hora_levantamento"])
    hora_entrega = request.values.get("hora_entrega", reserva["hora_entrega"])
    erros_datas, data_inicio, data_fim = reservas.validar_datas_reserva(
        veiculo, texto_inicio, texto_fim
    )
    erros_datas += reservas.validar_horas(data_inicio, data_fim, hora_levantamento, hora_entrega)
    if erros_datas:
        for erro in erros_datas:
            flash(erro, "erro")
        return redirect(url_for(
            "alterar_reserva", id_reserva=id_reserva,
            data_inicio=texto_inicio, data_fim=texto_fim,
            hora_levantamento=hora_levantamento, hora_entrega=hora_entrega,
        ))

    alteracao = reservas.calcular_alteracao(reserva, veiculo, data_inicio, data_fim)
    id_cliente = session["id_cliente"]
    formas_pagamento = reservas.obter_formas_pagamento(id_cliente)
    escolha_pagamento = request.form.get(
        "forma_pagamento", escolha_pagamento_por_defeito(formas_pagamento)
    )
    nome_titular = request.form.get("nome_titular", "").strip()

    if request.method == "POST":
        id_forma_pagamento = None
        erros_pagamento = []
        if alteracao["diferenca"] > 0:
            id_forma_pagamento, erros_pagamento = obter_forma_pagamento_escolhida(id_cliente)

        if not erros_pagamento:
            alteracao = reservas.alterar_datas_reserva(
                reserva, veiculo, data_inicio, data_fim,
                hora_levantamento, hora_entrega, id_forma_pagamento,
            )
            mensagem = (
                f"A reserva n.º {id_reserva} foi alterada para "
                f"{reservas.formatar_data(data_inicio)} às {hora_levantamento} a "
                f"{reservas.formatar_data(data_fim)} às {hora_entrega}."
            )
            if alteracao["diferenca"] > 0:
                mensagem += f" Foi paga a diferença de {alteracao['diferenca']:.2f} €."
            elif alteracao["diferenca"] < 0:
                mensagem += f" Foi reembolsado: {texto_reembolsos(alteracao['reembolsos'])}."
            flash(mensagem, "sucesso")
            return redirect(url_for("lista_reservas"))

        for erro in erros_pagamento:
            flash(erro, "erro")

    return render_template(
        "confirmar_alteracao.html",
        reserva=reserva,
        veiculo=veiculo,
        alteracao=alteracao,
        data_inicio=data_inicio,
        data_fim=data_fim,
        hora_levantamento=hora_levantamento,
        hora_entrega=hora_entrega,
        formas_pagamento=formas_pagamento,
        escolha_pagamento=escolha_pagamento,
        nome_titular=nome_titular,
        guardar_cartao=request.form.get("guardar_cartao") == "sim",
    )


@aplicacao.route("/reservas/<int:id_reserva>/cancelar", methods=["GET", "POST"])
def cancelar_reserva(id_reserva):
    """
    Cancelamento da reserva. Ao abrir (GET), mostra a página "Tem a
    certeza?" com o resumo e o valor a reembolsar; só ao confirmar (POST) a
    reserva é cancelada, com reembolso total para os cartões que pagaram.
    """
    redirecionamento_login = exigir_sessao_iniciada()
    if redirecionamento_login:
        return redirecionamento_login

    reserva, redirecionamento = obter_reserva_alteravel(id_reserva)
    if redirecionamento:
        return redirecionamento

    if request.method == "POST":
        reembolsos = reservas.cancelar_reserva(reserva)
        flash(
            f"A reserva n.º {id_reserva} foi cancelada. "
            f"Foi reembolsado: {texto_reembolsos(reembolsos)}.",
            "sucesso",
        )
        return redirect(url_for("lista_reservas"))

    return render_template(
        "cancelar_reserva.html",
        reserva=reserva,
        numero_dias=reservas.contar_dias(
            date.fromisoformat(reserva["data_inicio"]), date.fromisoformat(reserva["data_fim"])
        ),
        reembolsos=reservas.planear_reembolso(id_reserva, reserva["valor_total"]),
        extras=reservas.obter_extras_reserva(id_reserva),
    )


# --- Contactos (pública, Fase 6) -----------------------------------------

@aplicacao.route("/contactos", methods=["GET", "POST"])
def pagina_contactos():
    """
    Página de contactos (baseada no contact.html do template): moradas dos
    balcões, telefone, e-mail e formulário. A mensagem fica guardada na base
    de dados (não é enviado nenhum e-mail). Se o cliente tiver sessão
    iniciada, o nome aparece já preenchido.
    """
    nome = request.form.get("nome", session.get("nome_cliente", "")).strip()
    email = request.form.get("email", "").strip()
    mensagem = request.form.get("mensagem", "").strip()

    if request.method == "POST":
        erros = contactos.validar_mensagem(nome, email, mensagem)
        if not erros:
            contactos.guardar_mensagem(nome, email, mensagem)
            flash("Mensagem enviada. Obrigado! Responderemos para o e-mail indicado.", "sucesso")
            return redirect(url_for("pagina_contactos"))
        for erro in erros:
            flash(erro, "erro")

    return render_template(
        "contactos.html",
        balcoes=reservas.obter_balcoes(),
        duracao_maxima=reservas.DURACAO_MAXIMA_DIAS,
        nome=nome,
        email=email,
        mensagem=mensagem,
    )


if __name__ == "__main__":
    # Garante que a base de dados existe antes de arrancar o servidor.
    if not database.CAMINHO_BASE_DADOS.exists():
        database.inicializar_base_dados()

    aplicacao.run(debug=True)
