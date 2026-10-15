"""
Testes da Fase 5 — "As minhas reservas", alteração das datas (com pagamento
ou reembolso da diferença) e cancelamento (com reembolso total).

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase5_reservas.py -v

Cartões usados nos testes:
    cartão A = 1234 5678 9012 3456 (termina em 3456) — usado por defeito
    cartão B = 1111 2222 3333 4444 (termina em 4444)
O Mitsubishi Mirage custa 25 €/dia: 3 dias = 75 €, 5 dias = 125 €, 1 dia = 25 €.
"""

import unittest

# base_testes tem de ser importado primeiro (torna o projeto importável);
# as funções auxiliares da Fase 4 são reaproveitadas.
import base_testes  # noqa: F401
import reservas
from test_fase4_reservas import TesteComClienteAutenticado, dia, MIRAGE, AUDI, PAJERO

CARTAO_B = "1111 2222 3333 4444"


class TesteReservas(TesteComClienteAutenticado):
    """Funções auxiliares comuns aos testes desta fase."""

    def reserva(self, id_reserva=1):
        return self.consultar("SELECT * FROM reservas WHERE id_reserva = ?", (id_reserva,))[0]

    def movimentos(self, id_reserva=1):
        """Lista de (tipo, valor, últimos 4 algarismos do cartão), pela ordem em que aconteceram."""
        registos = self.consultar(
            """
            SELECT pagamentos.tipo, pagamentos.valor, formas_pagamento.ultimos_digitos
            FROM pagamentos JOIN formas_pagamento
                 ON formas_pagamento.id_forma_pagamento = pagamentos.id_forma_pagamento
            WHERE id_reserva = ? ORDER BY id_pagamento
            """,
            (id_reserva,),
        )
        return [(registo[0], registo[1], registo[2]) for registo in registos]

    def mudar_datas_na_bd(self, data_inicio, data_fim, id_reserva=1):
        """Simula a passagem do tempo, pondo a reserva no passado ou a decorrer."""
        self.executar(
            "UPDATE reservas SET data_inicio = ?, data_fim = ? WHERE id_reserva = ?",
            (data_inicio, data_fim, id_reserva),
        )

    def pedir_alteracao(self, data_inicio, data_fim, id_reserva=1):
        return self.navegador.post(
            f"/reservas/{id_reserva}/alterar",
            data={"data_inicio": data_inicio, "data_fim": data_fim},
            follow_redirects=True,
        )

    def confirmar_alteracao(self, data_inicio, data_fim, id_reserva=1, **campos):
        dados_formulario = {"data_inicio": data_inicio, "data_fim": data_fim}
        dados_formulario.update(campos)
        return self.navegador.post(
            f"/reservas/{id_reserva}/confirmar-alteracao",
            data=dados_formulario,
            follow_redirects=True,
        )

    def pagar_diferenca_com_cartao_b(self, data_inicio, data_fim, id_reserva=1):
        return self.confirmar_alteracao(
            data_inicio, data_fim, id_reserva,
            forma_pagamento="novo", numero_cartao=CARTAO_B,
            nome_titular="Gabriel Barbosa", codigo_seguranca="999",
        )


# --- "As minhas reservas" ---------------------------------------------------

class TestesListaReservas(TesteReservas):

    def test_sem_reservas_mostra_mensagem(self):
        pagina = self.texto(self.navegador.get("/reservas"))
        self.assertIn("Ainda não fez nenhuma reserva", pagina)

    def test_reserva_aparece_com_estado_historico_e_acoes(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        pagina = self.texto(self.navegador.get("/reservas"))
        self.assertIn("Mitsubishi Mirage", pagina)
        self.assertIn("Futura", pagina)
        self.assertIn("Pagamento:", pagina)
        self.assertIn("75.00 €", pagina)
        self.assertIn("cartão terminado em 3456", pagina)
        self.assertIn("/reservas/1/alterar", pagina)
        self.assertIn("/reservas/1/cancelar", pagina)

    def test_estados_e_ordem_futuras_primeiro(self):
        self.pagar(MIRAGE, dia(10), dia(12))    # 1 -> vai ficar Terminada
        self.pagar(AUDI, dia(10), dia(12))   # 2 -> vai ficar A decorrer
        self.pagar(PAJERO, dia(20), dia(22))    # 3 -> Futura (um veículo reservado não volta a ser reservável)
        self.mudar_datas_na_bd(dia(-5), dia(-3), id_reserva=1)
        self.mudar_datas_na_bd(dia(-1), dia(1), id_reserva=2)
        pagina = self.texto(self.navegador.get("/reservas"))
        posicao_futura = pagina.find("Reserva n.º 3")
        posicao_a_decorrer = pagina.find("Reserva n.º 2")
        posicao_terminada = pagina.find("Reserva n.º 1")
        self.assertLess(posicao_futura, posicao_a_decorrer)
        self.assertLess(posicao_a_decorrer, posicao_terminada)
        self.assertIn("A decorrer", pagina)
        self.assertIn("Terminada", pagina)
        # Só a reserva futura tem os botões de alterar/cancelar
        self.assertIn("/reservas/3/alterar", pagina)
        self.assertNotIn("/reservas/1/alterar", pagina)
        self.assertNotIn("/reservas/2/alterar", pagina)

    def test_cliente_nao_ve_reservas_de_outro_cliente(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        self.trocar_para_outro_cliente()
        pagina = self.texto(self.navegador.get("/reservas"))
        self.assertIn("Ainda não fez nenhuma reserva", pagina)


# --- Prazo e privacidade -------------------------------------------------------

class TestesPrazoEPrivacidade(TesteReservas):

    def setUp(self):
        super().setUp()
        self.pagar(MIRAGE, dia(10), dia(12))

    def test_reserva_a_decorrer_nao_pode_ser_alterada_nem_cancelada(self):
        self.mudar_datas_na_bd(dia(-1), dia(1))
        for endereco in ["/reservas/1/alterar", "/reservas/1/cancelar"]:
            with self.subTest(endereco=endereco):
                pagina = self.texto(self.navegador.get(endereco, follow_redirects=True))
                self.assertIn("já não pode ser alterada nem cancelada", pagina)
        # Mesmo enviando o formulário diretamente, nada muda
        self.navegador.post("/reservas/1/cancelar")
        self.assertEqual(self.reserva()["estado"], "ativa")

    def test_reserva_cancelada_nao_pode_ser_cancelada_outra_vez(self):
        self.navegador.post("/reservas/1/cancelar")
        self.navegador.post("/reservas/1/cancelar")
        self.assertEqual([m[0] for m in self.movimentos()].count("reembolso"), 1)
        pagina = self.texto(self.navegador.get("/reservas/1/alterar", follow_redirects=True))
        self.assertIn("Esta reserva já foi cancelada", pagina)

    def test_outro_cliente_recebe_404(self):
        self.trocar_para_outro_cliente()
        for endereco in ["/reservas/1/alterar", "/reservas/1/confirmar-alteracao", "/reservas/1/cancelar"]:
            with self.subTest(endereco=endereco):
                self.assertEqual(self.navegador.get(endereco).status_code, 404)
        self.assertEqual(self.navegador.post("/reservas/1/cancelar").status_code, 404)
        self.assertEqual(self.reserva()["estado"], "ativa")

    def test_sem_sessao_pede_login(self):
        self.navegador.get("/logout")
        resposta = self.navegador.get("/reservas/1/alterar")
        self.assertIn("/login", resposta.headers["Location"])


# --- Alteração das datas -------------------------------------------------------

class TestesAlterarDatas(TesteReservas):

    def setUp(self):
        super().setUp()
        self.pagar(MIRAGE, dia(10), dia(12))  # 3 dias = 75 € no cartão A

    def test_formulario_mostra_as_datas_atuais(self):
        pagina = self.texto(self.navegador.get("/reservas/1/alterar"))
        # As datas aparecem no formato do calendário (DD/MM/AAAA)
        self.assertIn(f'value="{reservas.formatar_data(dia(10))}"', pagina)
        self.assertIn(f'value="{reservas.formatar_data(dia(12))}"', pagina)

    def test_datas_iguais_as_atuais_sao_recusadas(self):
        pagina = self.texto(self.pedir_alteracao(dia(10), dia(12)))
        self.assertIn("iguais às atuais", pagina)

    def test_mais_cara_pede_pagamento_da_diferenca(self):
        pagina = self.texto(self.pedir_alteracao(dia(10), dia(14)))  # 5 dias = 125 €
        self.assertIn("Diferença a pagar", pagina)
        self.assertIn("50.00 €", pagina)
        self.assertIn("Usar um cartão novo", pagina)
        # Ainda nada mudou: só muda depois de pagar
        self.assertEqual(self.reserva()["data_fim"], dia(12))

    def test_pagar_a_diferenca_altera_a_reserva(self):
        pagina = self.texto(self.pagar_diferenca_com_cartao_b(dia(10), dia(14)))
        self.assertIn("Foi paga a diferença de 50.00 €", pagina)
        reserva = self.reserva()
        self.assertEqual(reserva["data_fim"], dia(14))
        self.assertEqual(reserva["valor_total"], 125.0)
        self.assertEqual(reserva["id_veiculo"], MIRAGE)
        self.assertEqual(self.movimentos(), [("pagamento", 75.0, "3456"), ("diferenca", 50.0, "4444")])

    def test_pagar_a_diferenca_com_cartao_guardado(self):
        # Outra reserva com o mesmo cartão A, desta vez marcando "Guardar este cartão"
        self.pagar(AUDI, dia(30), dia(31), guardar_cartao="sim")
        id_cartao_a = self.consultar("SELECT id_forma_pagamento FROM formas_pagamento")[0][0]
        self.confirmar_alteracao(dia(10), dia(14), forma_pagamento=str(id_cartao_a))
        self.assertEqual(self.movimentos()[-1], ("diferenca", 50.0, "3456"))

    def test_cartao_invalido_nao_altera_nada(self):
        self.confirmar_alteracao(
            dia(10), dia(14), forma_pagamento="novo",
            numero_cartao="123", nome_titular="Gabriel", codigo_seguranca="1",
        )
        self.assertEqual(self.reserva()["data_fim"], dia(12))
        self.assertEqual(len(self.movimentos()), 1)

    def test_mais_barata_reembolsa_a_diferenca(self):
        pagina = self.texto(self.pedir_alteracao(dia(10), dia(10)))  # 1 dia = 25 €
        self.assertIn("Diferença a reembolsar", pagina)
        pagina = self.texto(self.confirmar_alteracao(dia(10), dia(10)))
        self.assertIn("Foi reembolsado: 50.00 € para o cartão terminado em 3456", pagina)
        self.assertEqual(self.reserva()["valor_total"], 25.0)
        self.assertEqual(self.movimentos()[-1], ("reembolso", 50.0, "3456"))

    def test_mesmo_valor_so_confirma(self):
        pagina = self.texto(self.pedir_alteracao(dia(20), dia(22)))  # continua a ser 3 dias
        self.assertIn("Sem diferença de valor", pagina)
        self.confirmar_alteracao(dia(20), dia(22))
        self.assertEqual(self.reserva()["data_inicio"], dia(20))
        self.assertEqual(len(self.movimentos()), 1)  # nenhum movimento novo

    def test_a_propria_reserva_nao_torna_o_seu_veiculo_indisponivel(self):
        # O veículo está reservado (por esta mesma reserva), mas a alteração
        # das datas tem de continuar a funcionar; 11-13 até se sobrepõe às atuais.
        pagina = self.texto(self.pedir_alteracao(dia(11), dia(13)))
        self.assertIn("Resumo da alteração", pagina)

    def test_regras_da_fase_4_aplicam_se_as_novas_datas(self):
        pagina = self.texto(self.pedir_alteracao(dia(1), dia(31)))
        self.assertIn("contrato especial", pagina)
        pagina = self.texto(self.pedir_alteracao(dia(-1), dia(3)))
        self.assertIn("não pode ser anterior a hoje", pagina)

    def test_datas_invalidas_no_url_da_confirmacao_voltam_atras(self):
        resposta = self.navegador.get(
            f"/reservas/1/confirmar-alteracao?data_inicio={dia(-3)}&data_fim={dia(2)}",
            follow_redirects=True,
        )
        pagina = self.texto(resposta)
        self.assertIn("não pode ser anterior a hoje", pagina)
        self.assertIn("Nova data de início", pagina)

    def test_valor_e_veiculo_nao_podem_ser_mudados_pelo_formulario(self):
        self.confirmar_alteracao(dia(10), dia(10), valor_total="1", id_veiculo=str(AUDI))
        reserva = self.reserva()
        self.assertEqual(reserva["valor_total"], 25.0)
        self.assertEqual(reserva["id_veiculo"], MIRAGE)


# --- Reembolsos repartidos por vários cartões ------------------------------

class TestesReembolsosPorCartao(TesteReservas):

    def setUp(self):
        super().setUp()
        self.pagar(MIRAGE, dia(10), dia(12))                  # 75 € no cartão A
        self.pagar_diferenca_com_cartao_b(dia(10), dia(14))  # +50 € no cartão B (total 125 €)

    def test_encurtar_reembolsa_primeiro_o_ultimo_cartao_usado(self):
        # 10-11 = 2 dias = 50 € -> reembolso de 75 €: 50 € ao B (tudo o que pagou) e 25 € ao A
        pagina = self.texto(self.confirmar_alteracao(dia(10), dia(11)))
        self.assertIn(
            "50.00 € para o cartão terminado em 4444 e 25.00 € para o cartão terminado em 3456",
            pagina,
        )
        self.assertEqual(
            self.movimentos()[-2:], [("reembolso", 50.0, "4444"), ("reembolso", 25.0, "3456")]
        )

    def test_cancelar_devolve_a_cada_cartao_o_que_pagou(self):
        self.navegador.post("/reservas/1/cancelar")
        self.assertEqual(
            self.movimentos()[-2:], [("reembolso", 50.0, "4444"), ("reembolso", 75.0, "3456")]
        )

    def test_total_reembolsado_nunca_passa_do_total_pago(self):
        self.confirmar_alteracao(dia(10), dia(11))   # reembolso de 75 €
        self.navegador.post("/reservas/1/cancelar")  # reembolso dos 50 € restantes
        pago = sum(valor for tipo, valor, cartao in self.movimentos() if tipo != "reembolso")
        reembolsado = sum(valor for tipo, valor, cartao in self.movimentos() if tipo == "reembolso")
        self.assertEqual(pago, 125.0)
        self.assertEqual(reembolsado, 125.0)


# --- Cancelamento ------------------------------------------------------------

class TestesCancelar(TesteReservas):

    def setUp(self):
        super().setUp()
        self.pagar(MIRAGE, dia(10), dia(12))

    def test_abrir_a_pagina_pede_confirmacao_e_nao_cancela(self):
        pagina = self.texto(self.navegador.get("/reservas/1/cancelar"))
        self.assertIn("Tem a certeza", pagina)
        self.assertIn("75.00 € para o cartão terminado em 3456", pagina)
        self.assertEqual(self.reserva()["estado"], "ativa")

    def test_confirmar_cancela_e_reembolsa_tudo(self):
        pagina = self.texto(self.navegador.post("/reservas/1/cancelar", follow_redirects=True))
        self.assertIn("foi cancelada", pagina)
        self.assertIn("75.00 € para o cartão terminado em 3456", pagina)
        self.assertEqual(self.reserva()["estado"], "cancelada")
        self.assertEqual(self.movimentos()[-1], ("reembolso", 75.0, "3456"))
        self.assertIn("Cancelada", pagina)
        self.assertIn("(reembolsado)", pagina)

    def test_depois_de_cancelar_o_veiculo_fica_livre_para_outros_clientes(self):
        self.navegador.post("/reservas/1/cancelar")
        self.trocar_para_outro_cliente()
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12)))
        self.assertIn("Resumo da reserva", pagina)


if __name__ == "__main__":
    unittest.main()
