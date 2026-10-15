"""
Testes da Fase 1 — base de dados e lista de veículos.

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase1_veiculos.py -v
"""

import unittest

# base_testes tem de ser importado primeiro: é ele que torna os módulos do
# projeto (app, database) importáveis a partir desta pasta.
from base_testes import TesteComBaseDadosTemporaria

import sqlite3


class TestesBaseDados(TesteComBaseDadosTemporaria):
    """Verifica a estrutura da base de dados e os veículos de exemplo."""

    def test_tabelas_minimas_do_enunciado_existem(self):
        # sqlite_master é a tabela interna do SQLite que lista todas as tabelas criadas
        registos = self.consultar("SELECT name FROM sqlite_master WHERE type = 'table'")
        nomes_tabelas = [registo["name"] for registo in registos]
        for tabela_obrigatoria in ["clientes", "veiculos", "reservas", "formas_pagamento"]:
            self.assertIn(tabela_obrigatoria, nomes_tabelas)

    def test_foram_criados_16_veiculos_de_exemplo(self):
        # 10 veículos iniciais + 6 acrescentados na Fase 6
        total_veiculos = self.consultar("SELECT COUNT(*) FROM veiculos")[0][0]
        self.assertEqual(total_veiculos, 16)

    def test_categoria_invalida_e_recusada_pela_base_de_dados(self):
        # A restrição CHECK do schema.sql só aceita Pequeno/Médio/Grande/SUV/Luxo;
        # o SQLite recusa o registo com um erro do tipo IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.executar(
                """
                INSERT INTO veiculos (marca, modelo, categoria, tipo_veiculo, transmissao,
                    quantidade_pessoas, imagem, valor_diaria, data_ultima_revisao,
                    data_proxima_revisao, data_ultima_legalizacao)
                VALUES ('Teste', 'X', 'Gigante', 'Carro', 'Manual', 4, 'x.jpg', 10,
                    '2026-01-01', '2027-01-01', '2026-01-01')
                """
            )


class TestesListaVeiculos(TesteComBaseDadosTemporaria):
    """Verifica a página pública da lista de veículos e as regras de disponibilidade."""

    def test_lista_de_veiculos_e_publica(self):
        resposta = self.navegador.get("/veiculos")
        self.assertEqual(resposta.status_code, 200)

    def test_veiculo_disponivel_aparece_na_lista(self):
        self.assertIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_veiculo_com_revisao_ultrapassada_nao_aparece(self):
        # O Mitsubishi Space Star de exemplo tem a próxima revisão no passado
        self.assertNotIn("Mitsubishi Space Star", self.texto(self.navegador.get("/veiculos")))

    def test_veiculo_com_legalizacao_ha_mais_de_um_ano_nao_aparece(self):
        # O BMW Série 3 de exemplo tem a última legalização há 400 dias
        self.assertNotIn("BMW Série 3", self.texto(self.navegador.get("/veiculos")))

    def test_ficheiros_estaticos_apontam_para_a_pasta_assets(self):
        self.assertIn("/assets/css/main.css", self.texto(self.navegador.get("/veiculos")))


if __name__ == "__main__":
    unittest.main()
