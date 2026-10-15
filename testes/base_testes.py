"""
Base comum dos testes automáticos do website Luxury Wheels.

Como correr TODOS os testes (a partir da pasta do projeto, na Anaconda Prompt):
    python -m unittest discover testes -v

Cada teste corre com uma base de dados TEMPORÁRIA, criada do zero antes do
teste e apagada no fim — a base de dados real (luxury_wheels.db) nunca é
tocada.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Permite importar os módulos do projeto (app, database, autenticacao), que
# estão na pasta acima desta, mesmo que os testes sejam corridos de outro sítio.
PASTA_PROJETO = Path(__file__).resolve().parent.parent
if str(PASTA_PROJETO) not in sys.path:
    sys.path.insert(0, str(PASTA_PROJETO))

import database  # noqa: E402  (tem de vir depois de ajustar o sys.path)
from app import aplicacao  # noqa: E402


class TesteComBaseDadosTemporaria(unittest.TestCase):
    """
    Classe-base: todas as classes de testes herdam desta.

    - setUp() corre ANTES de cada teste: cria uma pasta temporária, aponta a
      aplicação para uma base de dados nova dentro dela e cria o "navegador
      de testes" do Flask (test_client), que simula um cliente a usar o site.
    - tearDown() corre DEPOIS de cada teste: repõe o caminho original da base
      de dados e apaga a pasta temporária.
    Assim, cada teste começa sempre do mesmo estado e não depende dos outros.
    """

    def setUp(self):
        self.caminho_original_bd = database.CAMINHO_BASE_DADOS
        self.pasta_temporaria = tempfile.mkdtemp(prefix="luxury_wheels_testes_")
        database.CAMINHO_BASE_DADOS = Path(self.pasta_temporaria) / "teste.db"
        database.inicializar_base_dados()

        aplicacao.config["TESTING"] = True
        self.navegador = aplicacao.test_client()

    def tearDown(self):
        database.CAMINHO_BASE_DADOS = self.caminho_original_bd
        shutil.rmtree(self.pasta_temporaria, ignore_errors=True)

    # --- Funções auxiliares usadas por vários testes ---------------------

    def registar(self, **campos_alterados):
        """
        Submete o formulário de registo com dados válidos por defeito;
        qualquer campo pode ser alterado (ex.: registar(password="curta")).
        """
        dados_formulario = {
            "nome": "Gabriel Barbosa",
            "utilizador": "gabriel",
            "email": "gabriel@exemplo.pt",
            "password": "Segura123",
            "confirmacao_password": "Segura123",
        }
        dados_formulario.update(campos_alterados)
        return self.navegador.post("/registo", data=dados_formulario)

    def iniciar_sessao(self, utilizador="gabriel", password="Segura123", proximo=""):
        """Submete o formulário de login."""
        return self.navegador.post(
            "/login",
            data={"utilizador": utilizador, "password": password, "proximo": proximo},
        )

    def texto(self, resposta):
        """Devolve o HTML de uma resposta, como texto."""
        return resposta.get_data(as_text=True)

    def consultar(self, instrucao_sql, parametros=()):
        """Executa uma consulta (SELECT) na base de dados de teste e devolve todos os registos."""
        ligacao = database.obter_ligacao()
        try:
            cursor = ligacao.cursor()
            cursor.execute(instrucao_sql, parametros)
            return cursor.fetchall()
        finally:
            ligacao.close()

    def executar(self, instrucao_sql, parametros=()):
        """Executa uma alteração (INSERT/UPDATE/DELETE) na base de dados de teste."""
        ligacao = database.obter_ligacao()
        try:
            cursor = ligacao.cursor()
            cursor.execute(instrucao_sql, parametros)
            ligacao.commit()
        finally:
            ligacao.close()

    def contar_clientes(self):
        return self.consultar("SELECT COUNT(*) FROM clientes")[0][0]

    def sessao_iniciada(self):
        """Indica se o navegador de testes tem, neste momento, sessão iniciada."""
        with self.navegador.session_transaction() as sessao:
            return "id_cliente" in sessao
