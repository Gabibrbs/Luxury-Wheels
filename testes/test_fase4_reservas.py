"""
Testes da Fase 4 — efetuar aluguer, pagamento e confirmação da reserva,
e a regra automática de disponibilidade dos veículos.

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase4_reservas.py -v

Veículos de exemplo usados (ver database.semear_veiculos_exemplo):
    1 = Mitsubishi Mirage (25 €/dia; revisão daqui a 120 dias)
    5 = Audi Q8 (95 €/dia)
    6 = Mitsubishi Pajero (60 €/dia; revisão daqui a 90 dias;
        legalização válida só por mais 115 dias)
    9 = Mitsubishi Space Star (revisão já ultrapassada -> indisponível)
"""

import unittest
from datetime import date, timedelta

# base_testes tem de ser importado primeiro: é ele que torna os módulos do
# projeto (app, database, reservas) importáveis a partir desta pasta.
from base_testes import TesteComBaseDadosTemporaria

import reservas

MIRAGE = 1
AUDI = 5
PAJERO = 6
SPACE_STAR = 9


def dia(dias_a_partir_de_hoje):
    """Data (texto AAAA-MM-DD) a N dias de hoje — os testes nunca dependem do dia em que correm."""
    return (date.today() + timedelta(days=dias_a_partir_de_hoje)).isoformat()


class TesteComClienteAutenticado(TesteComBaseDadosTemporaria):
    """Base para os testes desta fase: cada teste começa com um cliente registado e com sessão."""

    def setUp(self):
        super().setUp()
        self.registar()  # o registo inicia sessão automaticamente (Fase 2)

    def escolher_datas(self, id_veiculo, data_inicio, data_fim, **campos_alterados):
        """Submete o formulário "Efetuar aluguer" (horas 10:00/18:00 e balcão 1 por defeito)."""
        dados_formulario = {
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "hora_levantamento": "10:00",
            "hora_entrega": "18:00",
            "balcao_levantamento": "1",
            "balcao_entrega": "1",
        }
        dados_formulario.update(campos_alterados)
        return self.navegador.post(
            f"/veiculos/{id_veiculo}/alugar", data=dados_formulario, follow_redirects=True
        )

    def pagar(self, id_veiculo, data_inicio, data_fim, **campos_alterados):
        """Submete o pagamento com um cartão novo válido por defeito."""
        dados_formulario = {
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "hora_levantamento": "10:00",
            "hora_entrega": "18:00",
            "balcao_levantamento": "1",
            "balcao_entrega": "1",
            "forma_pagamento": "novo",
            "numero_cartao": "1234 5678 9012 3456",
            "nome_titular": "Gabriel Barbosa",
            "codigo_seguranca": "123",
        }
        dados_formulario.update(campos_alterados)
        return self.navegador.post(
            f"/veiculos/{id_veiculo}/pagamento", data=dados_formulario, follow_redirects=True
        )

    def contar_reservas(self):
        return self.consultar("SELECT COUNT(*) FROM reservas")[0][0]

    def trocar_para_outro_cliente(self):
        self.navegador.get("/logout")
        self.registar(utilizador="maria", email="maria@exemplo.pt", nome="Maria Silva")


# --- Funções isoladas do módulo reservas ----------------------------------

class TestesFuncoesDeDatas(unittest.TestCase):

    def test_contar_dias_inclui_o_dia_de_inicio_e_o_de_fim(self):
        self.assertEqual(reservas.contar_dias(date(2026, 10, 1), date(2026, 10, 3)), 3)

    def test_inicio_e_fim_no_mesmo_dia_conta_1_dia(self):
        self.assertEqual(reservas.contar_dias(date(2026, 10, 1), date(2026, 10, 1)), 1)

    def test_texto_para_data_aceita_os_dois_formatos(self):
        self.assertEqual(reservas.texto_para_data("2026-10-01"), date(2026, 10, 1))  # interno
        self.assertEqual(reservas.texto_para_data("01/10/2026"), date(2026, 10, 1))  # português
        for texto_invalido in ["", "abc", "2026-13-01", "31/02/2026", "10/13/2026"]:
            with self.subTest(texto_invalido=texto_invalido):
                self.assertIsNone(reservas.texto_para_data(texto_invalido))

    def test_formatar_data_em_portugues(self):
        self.assertEqual(reservas.formatar_data("2026-10-01"), "01/10/2026")


# --- Regra automática de disponibilidade ---------------------------------

class TestesDisponibilidadeAutomatica(TesteComBaseDadosTemporaria):

    def test_todos_os_veiculos_sao_criados_sem_bloqueio_manual(self):
        # A regra da revisão/legalização já não é guardada na coluna "disponivel"
        total_bloqueados = self.consultar("SELECT COUNT(*) FROM veiculos WHERE disponivel = 0")[0][0]
        self.assertEqual(total_bloqueados, 0)

    def test_veiculo_cuja_revisao_passa_desaparece_sozinho_da_lista(self):
        # Simula a passagem do tempo: a revisão do Mirage passou a ser "ontem"
        self.assertIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))
        self.executar("UPDATE veiculos SET data_proxima_revisao = ? WHERE id_veiculo = ?", (dia(-1), MIRAGE))
        self.assertNotIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_veiculo_cuja_legalizacao_faz_um_ano_desaparece_sozinho_da_lista(self):
        self.executar("UPDATE veiculos SET data_ultima_legalizacao = ? WHERE id_veiculo = ?", (dia(-366), MIRAGE))
        self.assertNotIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_legalizacao_com_exatamente_um_ano_ainda_e_valida(self):
        self.executar("UPDATE veiculos SET data_ultima_legalizacao = ? WHERE id_veiculo = ?", (dia(-365), MIRAGE))
        self.assertIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_bloqueio_manual_esconde_o_veiculo(self):
        self.executar("UPDATE veiculos SET disponivel = 0 WHERE id_veiculo = ?", (MIRAGE,))
        self.assertNotIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))


# --- Página "Efetuar Aluguer" e jornadas de navegação ----------------------

class TestesPaginaEfetuarAluguer(TesteComBaseDadosTemporaria):

    def test_lista_tem_botao_efetuar_aluguer(self):
        self.assertIn(f"/veiculos/{MIRAGE}/alugar", self.texto(self.navegador.get("/veiculos")))

    def test_jornada_1_visitante_vai_ao_login_e_volta_ao_mesmo_veiculo(self):
        resposta = self.navegador.get(f"/veiculos/{MIRAGE}/alugar")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])
        # Regista-se a partir daí e é devolvido à página do mesmo veículo
        resposta = self.registar(proximo=f"/veiculos/{MIRAGE}/alugar")
        self.assertTrue(resposta.headers["Location"].endswith(f"/veiculos/{MIRAGE}/alugar"))

    def test_jornada_2_cliente_com_sessao_entra_diretamente(self):
        self.registar()
        resposta = self.navegador.get(f"/veiculos/{MIRAGE}/alugar")
        self.assertEqual(resposta.status_code, 200)
        pagina = self.texto(resposta)
        self.assertIn("Mitsubishi Mirage", pagina)
        self.assertIn("200 km por dia", pagina)
        self.assertIn("contrato especial", pagina)

    def test_veiculo_indisponivel_nao_pode_ser_alugado(self):
        self.registar()
        resposta = self.navegador.get(f"/veiculos/{SPACE_STAR}/alugar", follow_redirects=True)
        self.assertIn("não está disponível para reserva", self.texto(resposta))

    def test_veiculo_inexistente_nao_pode_ser_alugado(self):
        self.registar()
        resposta = self.navegador.get("/veiculos/999/alugar", follow_redirects=True)
        self.assertIn("não está disponível para reserva", self.texto(resposta))


# --- Validação das datas ----------------------------------------------------

class TestesValidacaoDatas(TesteComClienteAutenticado):

    def test_datas_validas_seguem_para_o_pagamento(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12)))
        self.assertIn("Resumo da reserva", pagina)

    def test_datas_no_formato_do_calendario_dd_mm_aaaa_sao_aceites(self):
        data_inicio = reservas.formatar_data(dia(10))  # ex.: "08/10/2026"
        data_fim = reservas.formatar_data(dia(12))
        pagina = self.texto(self.escolher_datas(MIRAGE, data_inicio, data_fim))
        self.assertIn("Resumo da reserva", pagina)
        self.assertIn("75.00 €", pagina)

    def test_campos_de_data_usam_o_calendario_em_portugues(self):
        pagina = self.texto(self.navegador.get(f"/veiculos/{MIRAGE}/alugar"))
        self.assertIn('class="datepicker-here" data-language="pt"', pagina)
        self.assertIn("js/datepicker.pt.js", pagina)

    def test_reserva_de_um_so_dia_e_aceite(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(10)))
        self.assertIn("Resumo da reserva", pagina)

    def test_datas_invalidas_sao_recusadas(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, "abc", ""))
        self.assertIn("Indique uma data de início e uma data de fim válidas", pagina)

    def test_inicio_no_passado_e_recusado(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(-1), dia(2)))
        self.assertIn("não pode ser anterior a hoje", pagina)

    def test_fim_antes_do_inicio_e_recusado(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(8)))
        self.assertIn("não pode ser anterior à data de início", pagina)

    def test_30_dias_e_aceite_mas_31_e_recusado(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(1), dia(30)))  # 30 dias
        self.assertIn("Resumo da reserva", pagina)
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(1), dia(31)))  # 31 dias
        self.assertIn("contacte-nos para um contrato especial", pagina)

    def test_inicio_depois_da_proxima_revisao_e_recusado(self):
        # Revisão do Mirage daqui a 120 dias
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(121), dia(125)))
        self.assertIn("o aluguer tem de começar até essa data", pagina)

    def test_revisao_durante_o_aluguer_e_aceite_com_aviso(self):
        # Revisão do Pajero daqui a 90 dias; aluguer de 85 a 95
        pagina = self.texto(self.escolher_datas(PAJERO, dia(85), dia(95)))
        self.assertIn("Resumo da reserva", pagina)
        self.assertIn("A revisão terá de ser tratada pelo cliente", pagina)
        self.assertIn("todos os custos são suportados pela Luxury Wheels", pagina)

    def test_fim_depois_da_validade_da_legalizacao_e_recusado(self):
        # Legalização do Pajero válida só por mais 115 dias; aluguer de 88 a 117
        pagina = self.texto(self.escolher_datas(PAJERO, dia(88), dia(117)))
        self.assertIn("o aluguer tem de terminar até essa data", pagina)

    def test_abrir_o_pagamento_com_datas_invalidas_no_url_volta_atras(self):
        resposta = self.navegador.get(
            f"/veiculos/{MIRAGE}/pagamento?data_inicio={dia(-5)}&data_fim={dia(1)}",
            follow_redirects=True,
        )
        self.assertIn("não pode ser anterior a hoje", self.texto(resposta))
        self.assertIn("continuar para o pagamento", self.texto(resposta))  # voltou à página do pedido


# --- Veículo reservado deixa de estar disponível -------------------------------
# Critério técnico 4 do enunciado: "Após a reserva ser concluída, o veículo
# escolhido não deve ficar mais disponível para os clientes" (e, segundo o
# formador, nem para o próprio cliente).

class TestesVeiculoReservadoFicaIndisponivel(TesteComClienteAutenticado):

    def setUp(self):
        super().setUp()
        self.pagar(MIRAGE, dia(10), dia(12))  # reserva ativa do Mirage

    def test_veiculo_reservado_sai_da_lista(self):
        lista = self.texto(self.navegador.get("/veiculos"))
        self.assertNotIn("Mitsubishi Mirage", lista)
        self.assertIn("Audi Q8", lista)  # os outros continuam disponíveis

    def test_veiculo_reservado_sai_da_lista_para_outro_cliente(self):
        self.trocar_para_outro_cliente()
        lista = self.texto(self.navegador.get("/veiculos"))
        self.assertNotIn("Mitsubishi Mirage", lista)

    def test_outro_cliente_nao_consegue_abrir_o_aluguer_do_veiculo(self):
        self.trocar_para_outro_cliente()
        pagina = self.texto(self.navegador.get(f"/veiculos/{MIRAGE}/alugar", follow_redirects=True))
        self.assertIn("não está disponível para reserva", pagina)

    def test_o_proprio_cliente_nao_pode_reservar_o_mesmo_veiculo_outra_vez(self):
        # Nem nas mesmas datas, nem noutras: enquanto a reserva estiver ativa
        for datas in [(dia(10), dia(12)), (dia(30), dia(32))]:
            with self.subTest(datas=datas):
                pagina = self.texto(self.escolher_datas(MIRAGE, *datas))
                self.assertIn("não está disponível para reserva", pagina)
        self.assertEqual(self.contar_reservas(), 1)

    def test_outro_veiculo_nas_mesmas_datas_e_aceite(self):
        pagina = self.texto(self.escolher_datas(AUDI, dia(10), dia(12)))
        self.assertIn("Resumo da reserva", pagina)

    def test_pagar_veiculo_que_entretanto_foi_reservado_e_recusado(self):
        # Simula dois clientes com a página de pagamento aberta ao mesmo tempo:
        # a disponibilidade é verificada outra vez no momento de pagar
        self.trocar_para_outro_cliente()
        pagina = self.texto(self.pagar(MIRAGE, dia(20), dia(21)))
        self.assertIn("não está disponível para reserva", pagina)
        self.assertEqual(self.contar_reservas(), 1)

    def test_reserva_cancelada_devolve_o_veiculo_a_lista(self):
        self.navegador.post("/reservas/1/cancelar")
        self.assertIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_reserva_terminada_devolve_o_veiculo_a_lista(self):
        # Simula a passagem do tempo: a reserva acabou ontem
        self.executar("UPDATE reservas SET data_inicio = ?, data_fim = ?", (dia(-3), dia(-1)))
        self.assertIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))

    def test_reserva_que_acaba_hoje_ainda_mantem_o_veiculo_indisponivel(self):
        self.executar("UPDATE reservas SET data_inicio = ?, data_fim = ?", (dia(-2), dia(0)))
        self.assertNotIn("Mitsubishi Mirage", self.texto(self.navegador.get("/veiculos")))


# --- Pagamento ----------------------------------------------------------------

class TestesPagamento(TesteComClienteAutenticado):

    def test_resumo_mostra_dias_valor_total_e_km_antes_de_pagar(self):
        # Mirage: 25 €/dia x 3 dias = 75 €; 3 x 200 km = 600 km
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12)))
        self.assertIn("75.00 €", pagina)
        self.assertIn("600 km", pagina)

    def test_pagamento_valido_cria_a_reserva_e_mostra_a_confirmacao(self):
        pagina = self.texto(self.pagar(MIRAGE, dia(10), dia(12)))
        self.assertIn("Reserva concluída", pagina)
        self.assertIn("Cartão terminado em 3456", pagina)
        reserva = self.consultar("SELECT * FROM reservas")[0]
        self.assertEqual(reserva["estado"], "ativa")
        self.assertEqual(reserva["valor_total"], 75.0)
        self.assertEqual(reserva["data_inicio"], dia(10))
        self.assertEqual(reserva["data_fim"], dia(12))

    def test_valor_total_e_calculado_no_servidor(self):
        # Mesmo que alguém acrescente um "valor_total" ao formulário, é ignorado
        self.pagar(MIRAGE, dia(10), dia(12), valor_total="1")
        self.assertEqual(self.consultar("SELECT valor_total FROM reservas")[0][0], 75.0)

    def test_so_os_ultimos_4_algarismos_sao_guardados_e_nunca_o_cvv(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        cartao = self.consultar("SELECT * FROM formas_pagamento")[0]
        self.assertEqual(cartao["ultimos_digitos"], "3456")
        self.assertNotIn("codigo_seguranca", cartao.keys())
        # O número completo não aparece em nenhuma coluna da tabela
        for valor in tuple(cartao):
            self.assertNotIn("1234567890123456", str(valor))

    def test_dados_de_cartao_invalidos_sao_recusados_sem_criar_reserva(self):
        casos_invalidos = [
            {"numero_cartao": "1234 5678 9012 345"},   # só 15 algarismos
            {"numero_cartao": "1234 5678 9012 34AB"},  # letras
            {"codigo_seguranca": "12"},                # CVV curto
            {"nome_titular": ""},                      # sem nome
        ]
        for campos in casos_invalidos:
            with self.subTest(campos=campos):
                pagina = self.texto(self.pagar(MIRAGE, dia(10), dia(12), **campos))
                self.assertIn("Forma de pagamento", pagina)  # continua na página de pagamento
                self.assertEqual(self.contar_reservas(), 0)

    def test_cartao_guardado_aparece_para_reutilizar(self):
        self.pagar(MIRAGE, dia(10), dia(12), guardar_cartao="sim")
        pagina = self.texto(self.escolher_datas(AUDI, dia(20), dia(21)))
        self.assertIn("Cartão terminado em 3456", pagina)

    def test_cartao_nao_guardado_por_defeito_nao_aparece_mas_fica_no_historico(self):
        self.pagar(MIRAGE, dia(10), dia(12))  # sem marcar "Guardar este cartão"
        pagina = self.texto(self.escolher_datas(AUDI, dia(20), dia(21)))
        self.assertNotIn("Cartão terminado em 3456", pagina)
        cartao = self.consultar("SELECT * FROM formas_pagamento")[0]
        self.assertEqual(cartao["guardado"], 0)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pagamentos")[0][0], 1)

    def test_caixa_guardar_cartao_aparece_desmarcada(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12)))
        self.assertIn('name="guardar_cartao" type="checkbox" value="sim" />', pagina)
        self.assertIn('class="mt-3 dados-cartao-novo"', pagina)

    def test_nao_e_possivel_escolher_um_cartao_nao_guardado(self):
        self.pagar(MIRAGE, dia(10), dia(12))  # cartão não guardado
        id_cartao = self.consultar("SELECT id_forma_pagamento FROM formas_pagamento")[0][0]
        pagina = self.texto(self.pagar(AUDI, dia(20), dia(21), forma_pagamento=str(id_cartao)))
        self.assertIn("Escolha uma forma de pagamento válida", pagina)
        self.assertEqual(self.contar_reservas(), 1)

    def test_guardar_depois_um_cartao_ja_usado_passa_a_guarda_lo(self):
        self.pagar(MIRAGE, dia(10), dia(12))                           # não guardado
        self.pagar(AUDI, dia(20), dia(21), guardar_cartao="sim")      # mesmo cartão, agora guardado
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM formas_pagamento")[0][0], 1)
        self.assertEqual(self.consultar("SELECT guardado FROM formas_pagamento")[0][0], 1)

    def test_reutilizar_cartao_guardado_nao_cria_cartao_novo(self):
        self.pagar(MIRAGE, dia(10), dia(12), guardar_cartao="sim")
        id_cartao = self.consultar("SELECT id_forma_pagamento FROM formas_pagamento")[0][0]
        self.pagar(AUDI, dia(20), dia(21), forma_pagamento=str(id_cartao))
        self.assertEqual(self.contar_reservas(), 2)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM formas_pagamento")[0][0], 1)

    def test_escrever_de_novo_o_mesmo_cartao_nao_o_duplica(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        self.pagar(AUDI, dia(20), dia(21))
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM formas_pagamento")[0][0], 1)

    def test_nao_e_possivel_usar_o_cartao_de_outro_cliente(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        id_cartao_gabriel = self.consultar("SELECT id_forma_pagamento FROM formas_pagamento")[0][0]
        self.trocar_para_outro_cliente()
        pagina = self.texto(self.pagar(AUDI, dia(20), dia(21), forma_pagamento=str(id_cartao_gabriel)))
        self.assertIn("Escolha uma forma de pagamento válida", pagina)
        self.assertEqual(self.contar_reservas(), 1)


# --- Página de confirmação -------------------------------------------------

class TestesConfirmacao(TesteComClienteAutenticado):

    def test_outro_cliente_nao_ve_a_confirmacao(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        id_reserva = self.consultar("SELECT id_reserva FROM reservas")[0][0]
        self.trocar_para_outro_cliente()
        resposta = self.navegador.get(f"/reservas/{id_reserva}/confirmacao")
        self.assertEqual(resposta.status_code, 404)

    def test_sem_sessao_a_confirmacao_pede_login(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        self.navegador.get("/logout")
        resposta = self.navegador.get("/reservas/1/confirmacao")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])


if __name__ == "__main__":
    unittest.main()
