"""
Testes da Fase 3 — pesquisa e filtros na lista de veículos.

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase3_pesquisa.py -v
"""

import unittest

# base_testes tem de ser importado primeiro: é ele que torna os módulos do
# projeto (app, database) importáveis a partir desta pasta.
from base_testes import TesteComBaseDadosTemporaria


class TestesPesquisaPorTexto(TesteComBaseDadosTemporaria):
    """Verifica a pesquisa por marca/modelo (parcial, sem distinguir maiúsculas)."""

    def test_pesquisa_parcial_encontra_pela_marca(self):
        resposta = self.texto(self.navegador.get("/veiculos?pesquisa=subaru"))
        self.assertIn("Subaru Legacy", resposta)

    def test_pesquisa_parcial_encontra_pelo_modelo(self):
        resposta = self.texto(self.navegador.get("/veiculos?pesquisa=mirage"))
        self.assertIn("Mitsubishi Mirage", resposta)

    def test_pesquisa_sem_resultados_mostra_mensagem(self):
        resposta = self.texto(self.navegador.get("/veiculos?pesquisa=NaoExiste123"))
        self.assertIn("Não foi encontrado nenhum veículo", resposta)

    def test_pesquisa_nao_devolve_veiculos_indisponiveis(self):
        # O Mitsubishi Space Star está indisponível (revisão ultrapassada); mesmo que
        # o texto pesquisado corresponda, não deve aparecer na lista.
        resposta = self.texto(self.navegador.get("/veiculos?pesquisa=space"))
        self.assertNotIn("Mitsubishi Space Star", resposta)


class TestesFiltrosPorCampo(TesteComBaseDadosTemporaria):
    """Verifica cada filtro isoladamente."""

    def test_filtro_categoria(self):
        resposta = self.texto(self.navegador.get("/veiculos?categoria=Luxo"))
        self.assertIn("Rolls-Royce Ghost", resposta)
        self.assertNotIn("Mitsubishi Mirage", resposta)

    def test_filtro_tipo_veiculo(self):
        resposta = self.texto(self.navegador.get("/veiculos?tipo_veiculo=Moto"))
        self.assertIn("Honda CB500", resposta)
        self.assertIn("Yamaha MT-07", resposta)
        self.assertNotIn("Mitsubishi Mirage", resposta)

    def test_filtro_transmissao(self):
        resposta = self.texto(self.navegador.get("/veiculos?transmissao=Automático"))
        self.assertIn("Subaru Legacy", resposta)
        self.assertNotIn("Mitsubishi Mirage", resposta)

    def test_filtro_valor_minimo(self):
        resposta = self.texto(self.navegador.get("/veiculos?valor_min=90"))
        self.assertIn("Audi Q8", resposta)  # 95€/dia
        self.assertNotIn("Mitsubishi Mirage", resposta)  # 25€/dia

    def test_filtro_valor_maximo(self):
        resposta = self.texto(self.navegador.get("/veiculos?valor_max=20"))
        self.assertIn("Yamaha MT-07", resposta)  # 18€/dia
        self.assertNotIn("Rolls-Royce Ghost", resposta)  # 120€/dia

    # Filtro de pessoas por faixas, como no enunciado (alterado na Fase 5)
    def test_faixa_1_a_4_pessoas(self):
        resposta = self.texto(self.navegador.get("/veiculos?pessoas=1-4"))
        self.assertIn("Mitsubishi Mirage", resposta)  # 4 pessoas
        self.assertIn("Yamaha MT-07", resposta)  # 2 pessoas
        self.assertNotIn("Subaru Legacy", resposta)  # 5 pessoas

    def test_faixa_5_a_6_pessoas(self):
        resposta = self.texto(self.navegador.get("/veiculos?pessoas=5-6"))
        self.assertIn("Subaru Legacy", resposta)  # 5 pessoas
        self.assertIn("Audi Q8", resposta)  # 5 pessoas
        self.assertNotIn("Mitsubishi Mirage", resposta)  # 4 pessoas
        self.assertNotIn("Mitsubishi Pajero", resposta)  # 7 pessoas

    def test_faixa_7_ou_mais_pessoas(self):
        resposta = self.texto(self.navegador.get("/veiculos?pessoas=7%2B"))  # %2B = "+" no URL
        self.assertIn("Mitsubishi Pajero", resposta)  # 7 pessoas
        self.assertNotIn("Audi Q8", resposta)  # 5 pessoas

    def test_faixa_desconhecida_e_ignorada(self):
        resposta = self.texto(self.navegador.get("/veiculos?pessoas=abc"))
        self.assertIn("Mitsubishi Mirage", resposta)
        self.assertIn("Mitsubishi Pajero", resposta)

    def test_categoria_desconhecida_e_ignorada(self):
        # Um valor de categoria que não existe não deve provocar erro nem
        # filtrar tudo — o filtro é simplesmente ignorado.
        resposta = self.navegador.get("/veiculos?categoria=NaoExiste")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Mitsubishi Mirage", self.texto(resposta))

    def test_valor_nao_numerico_e_ignorado(self):
        # Texto inválido num campo numérico não deve causar erro 500.
        resposta = self.navegador.get("/veiculos?valor_min=abc")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Mitsubishi Mirage", self.texto(resposta))


class TestesCombinacaoDeFiltros(TesteComBaseDadosTemporaria):
    """Verifica que vários filtros aplicados ao mesmo tempo se combinam com E (AND)."""

    def test_dois_filtros_que_o_mesmo_veiculo_cumpre(self):
        resposta = self.texto(self.navegador.get("/veiculos?categoria=SUV&tipo_veiculo=Carro"))
        self.assertIn("Audi Q8", resposta)

    def test_dois_filtros_que_nenhum_veiculo_cumpre_ao_mesmo_tempo(self):
        # Existem motos (Honda, Yamaha) e existem veículos de Luxo (Porsche,
        # Rolls-Royce...), mas nenhuma moto é da categoria Luxo: combinando
        # os dois filtros não deve haver resultados.
        resposta = self.texto(self.navegador.get("/veiculos?categoria=Luxo&tipo_veiculo=Moto"))
        self.assertIn("Não foi encontrado nenhum veículo", resposta)


class TestesOrdenacao(TesteComBaseDadosTemporaria):
    """Verifica que a lista aparece sempre ordenada pelo valor da diária, crescente."""

    def test_lista_completa_esta_ordenada_por_preco_crescente(self):
        resposta = self.texto(self.navegador.get("/veiculos"))
        posicao_barato = resposta.find("Yamaha MT-07")  # 18€/dia (o mais barato)
        posicao_caro = resposta.find("Rolls-Royce Ghost")  # 120€/dia (o mais caro)
        self.assertNotEqual(posicao_barato, -1)
        self.assertNotEqual(posicao_caro, -1)
        self.assertLess(posicao_barato, posicao_caro)


class TestesFormularioMantemEscolhas(TesteComBaseDadosTemporaria):
    """Verifica que o formulário reaparece preenchido com os filtros escolhidos."""

    def test_campos_do_formulario_mantem_os_valores_pesquisados(self):
        resposta = self.texto(self.navegador.get(
            "/veiculos?pesquisa=Golf&categoria=M%C3%A9dio&valor_min=30"
        ))
        self.assertIn('value="Golf"', resposta)
        self.assertIn('value="30"', resposta)
        self.assertIn('selected', resposta)


if __name__ == "__main__":
    unittest.main()
