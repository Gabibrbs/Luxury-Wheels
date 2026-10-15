"""
Testes da Fase 6 — página inicial, imagens de fundo, frota completa,
contactos, horas de levantamento/entrega, balcões e extras.

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase6_site.py -v

Balcões: 1 = Lisboa – Aeroporto, 2 = Lisboa – Centro, 3 = Porto – Aeroporto,
4 = Faro – Aeroporto. Extras: 1 = Seguro contra todos os riscos (15 €/dia),
2 = Cadeira de criança (20 €, valor fixo, só para carros).
O Mitsubishi Mirage (id 1) custa 25 €/dia; a Honda CB500 (id 7) é uma moto.
"""

import unittest
from datetime import date

from base_testes import TesteComBaseDadosTemporaria
from test_fase4_reservas import TesteComClienteAutenticado, dia, MIRAGE

import reservas

HONDA = 7
SEGURO = "1"
CADEIRA = "2"


# --- Página inicial e imagens de fundo ---------------------------------------

class TestesPaginaInicial(TesteComBaseDadosTemporaria):

    def test_pagina_inicial_abre_com_o_banner_e_a_pesquisa(self):
        pagina = self.texto(self.navegador.get("/"))
        self.assertIn("encontre o seu veículo", pagina)
        self.assertIn('action="/veiculos"', pagina)  # a pesquisa leva à lista de veículos
        self.assertIn('data-background="/assets/images/banner.jpg"', pagina)

    def test_contadores_mostram_numeros_reais(self):
        self.registar()
        pagina = self.texto(self.navegador.get("/"))
        # 16 veículos na frota, 2 indisponíveis (revisão/legalização) -> 14
        self.assertIn('<span class="counter">14</span>', pagina)
        self.assertIn('<span class="counter">1</span>', pagina)   # 1 cliente registado
        self.assertIn('<span class="counter">4</span>', pagina)   # 4 balcões

    def test_destaques_sao_os_4_veiculos_com_diaria_mais_alta(self):
        pagina = self.texto(self.navegador.get("/"))
        for nome in ["Porsche 911", "Alfa Romeo 4C", "Rolls-Royce Ghost", "Audi Q8"]:
            with self.subTest(nome=nome):
                self.assertIn(nome, pagina)
        self.assertNotIn("Mitsubishi Mirage", pagina)

    def test_lista_de_veiculos_passou_para_veiculos(self):
        resposta = self.navegador.get("/veiculos")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Porsche 911", self.texto(resposta))

    def test_imagens_de_fundo_usam_data_background(self):
        # O main.js do tema lê a imagem de fundo do atributo data-background
        pagina = self.texto(self.navegador.get("/veiculos"))
        self.assertIn('data-background="/assets/images/inner-page-bg.jpg"', pagina)
        self.assertNotIn("background-image: url(", pagina)

    def test_menu_tem_inicio_veiculos_e_contactos(self):
        pagina = self.texto(self.navegador.get("/veiculos"))
        for endereco in ['href="/">Início', 'href="/veiculos">Veículos', 'href="/contactos">Contactos']:
            with self.subTest(endereco=endereco):
                self.assertIn(endereco, pagina)


# --- Frota --------------------------------------------------------------------

class TestesFrota(TesteComBaseDadosTemporaria):

    def test_os_6_modelos_novos_estao_na_lista(self):
        pagina = self.texto(self.navegador.get("/veiculos"))
        for nome in ["Subaru Forester", "Toyota Tacoma", "Porsche 911", "Alfa Romeo 4C",
                     "Nissan Qashqai", "Mitsubishi Lancer Evolution"]:
            with self.subTest(nome=nome):
                self.assertIn(nome, pagina)

    def test_categoria_grande_passou_a_ter_um_veiculo_disponivel(self):
        pagina = self.texto(self.navegador.get("/veiculos?categoria=Grande"))
        self.assertIn("Toyota Tacoma", pagina)


# --- Contactos ------------------------------------------------------------------

class TestesContactos(TesteComBaseDadosTemporaria):

    def mensagens(self):
        return self.consultar("SELECT * FROM mensagens_contacto")

    def test_pagina_mostra_os_balcoes(self):
        pagina = self.texto(self.navegador.get("/contactos"))
        for balcao in ["Lisboa – Aeroporto", "Lisboa – Centro", "Porto – Aeroporto", "Faro – Aeroporto"]:
            with self.subTest(balcao=balcao):
                self.assertIn(balcao, pagina)

    def test_mensagem_valida_fica_guardada(self):
        resposta = self.navegador.post("/contactos", data={
            "nome": "Ana Costa", "email": "ana@exemplo.pt",
            "mensagem": "Gostava de alugar uma carrinha durante 2 meses.",
        }, follow_redirects=True)
        self.assertIn("Mensagem enviada", self.texto(resposta))
        self.assertEqual(len(self.mensagens()), 1)
        self.assertEqual(self.mensagens()[0]["email"], "ana@exemplo.pt")

    def test_dados_invalidos_nao_guardam_a_mensagem(self):
        resposta = self.navegador.post("/contactos", data={
            "nome": "A", "email": "sem-arroba", "mensagem": "curta",
        }, follow_redirects=True)
        pagina = self.texto(resposta)
        self.assertIn("Indique o seu nome", pagina)
        self.assertIn("e-mail válido", pagina)
        self.assertIn("pelo menos 10 caracteres", pagina)
        self.assertEqual(len(self.mensagens()), 0)

    def test_com_sessao_o_nome_aparece_preenchido(self):
        self.registar()
        self.assertIn('value="Gabriel Barbosa"', self.texto(self.navegador.get("/contactos")))

    def test_mensagem_do_contrato_especial_tem_link_para_contactos(self):
        self.registar()
        pagina = self.texto(self.navegador.get(f"/veiculos/{MIRAGE}/alugar"))
        self.assertIn('<a href="/contactos">contacte-nos</a> para um contrato especial', pagina)


# --- Horas de levantamento e entrega -----------------------------------------------

class TestesValidarHoras(unittest.TestCase):

    def test_horario_dos_balcoes(self):
        self.assertEqual(reservas.HORAS_DISPONIVEIS[0], "08:00")
        self.assertEqual(reservas.HORAS_DISPONIVEIS[-1], "20:00")
        self.assertEqual(len(reservas.HORAS_DISPONIVEIS), 25)  # de 30 em 30 minutos

    def test_hora_fora_do_horario_e_recusada(self):
        amanha = date.fromisoformat(dia(1))
        erros = reservas.validar_horas(amanha, amanha, "07:00", "21:00")
        self.assertEqual(len(erros), 2)

    def test_no_mesmo_dia_a_entrega_tem_de_ser_depois_do_levantamento(self):
        amanha = date.fromisoformat(dia(1))
        self.assertTrue(reservas.validar_horas(amanha, amanha, "18:00", "10:00"))
        self.assertTrue(reservas.validar_horas(amanha, amanha, "10:00", "10:00"))
        self.assertEqual(reservas.validar_horas(amanha, amanha, "10:00", "18:00"), [])

    def test_em_dias_diferentes_qualquer_hora_serve(self):
        self.assertEqual(
            reservas.validar_horas(date.fromisoformat(dia(1)), date.fromisoformat(dia(2)), "18:00", "08:00"), []
        )

    def test_levantamento_hoje_numa_hora_que_ja_passou_e_recusado(self):
        hoje = date.today()
        amanha = date.fromisoformat(dia(1))
        # "agora" fixo, para o teste não depender da hora a que é corrido
        self.assertTrue(reservas.validar_horas(hoje, amanha, "10:00", "10:00", agora="15:00"))
        self.assertEqual(reservas.validar_horas(hoje, amanha, "16:00", "10:00", agora="15:00"), [])


# --- Reserva com horas, balcões e extras -------------------------------------------

class TestesReservaCompleta(TesteComClienteAutenticado):

    def reserva(self):
        return self.consultar("SELECT * FROM reservas")[0]

    def test_horas_e_balcoes_ficam_guardados_e_aparecem_na_confirmacao(self):
        pagina = self.texto(self.pagar(
            MIRAGE, dia(10), dia(12), hora_levantamento="09:30", hora_entrega="17:00",
            balcao_levantamento="2", balcao_entrega="3",
        ))
        reserva = self.reserva()
        self.assertEqual((reserva["hora_levantamento"], reserva["hora_entrega"]), ("09:30", "17:00"))
        self.assertEqual((reserva["id_balcao_levantamento"], reserva["id_balcao_entrega"]), (2, 3))
        self.assertIn("Lisboa – Centro", pagina)
        self.assertIn("Porto – Aeroporto", pagina)
        self.assertIn("09:30", pagina)

    def test_entregar_noutro_balcao_nao_tem_custo(self):
        self.pagar(MIRAGE, dia(10), dia(12), balcao_levantamento="1", balcao_entrega="4")
        self.assertEqual(self.reserva()["valor_total"], 75.0)

    def test_balcao_invalido_e_recusado(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12), balcao_levantamento="99"))
        self.assertIn("Escolha o balcão de levantamento", pagina)

    def test_hora_invalida_e_recusada(self):
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12), hora_entrega="21:00"))
        self.assertIn("hora de entrega entre as 08:00 e as 20:00", pagina)

    def test_resumo_mostra_os_extras_antes_de_pagar(self):
        # 3 dias: diárias 75 €; seguro 15 € x 3 = 45 €; cadeira 20 € -> total 140 €
        pagina = self.texto(self.escolher_datas(MIRAGE, dia(10), dia(12), extras=[SEGURO, CADEIRA]))
        self.assertIn("Seguro contra todos os riscos", pagina)
        self.assertIn("45.00 €", pagina)
        self.assertIn("valor fixo = 20.00 €", pagina)
        self.assertIn("140.00 €", pagina)
        self.assertIn('name="extras" value="1"', pagina)  # os extras seguem escondidos no formulário

    def test_extras_ficam_guardados_e_entram_no_total(self):
        self.pagar(MIRAGE, dia(10), dia(12), extras=[SEGURO, CADEIRA])
        self.assertEqual(self.reserva()["valor_total"], 140.0)
        ids_extras = [registo[0] for registo in self.consultar("SELECT id_extra FROM reserva_extras ORDER BY id_extra")]
        self.assertEqual(ids_extras, [1, 2])

    def test_cadeira_de_crianca_nao_aparece_nas_motos(self):
        pagina = self.texto(self.navegador.get(f"/veiculos/{HONDA}/alugar"))
        self.assertIn("Seguro contra todos os riscos", pagina)
        self.assertNotIn("Cadeira de criança", pagina)

    def test_cadeira_de_crianca_numa_moto_e_recusada(self):
        pagina = self.texto(self.escolher_datas(HONDA, dia(10), dia(12), extras=[CADEIRA]))
        self.assertIn("não está disponível para este veículo", pagina)


# --- Alteração com horas e extras ----------------------------------------------------

class TestesAlteracaoComExtras(TesteComClienteAutenticado):

    def test_so_mudar_as_horas_nao_tem_custo(self):
        self.pagar(MIRAGE, dia(10), dia(12))
        pagina = self.texto(self.navegador.post("/reservas/1/alterar", data={
            "data_inicio": dia(10), "data_fim": dia(12),
            "hora_levantamento": "08:00", "hora_entrega": "20:00",
        }, follow_redirects=True))
        self.assertIn("Sem diferença de valor", pagina)
        self.navegador.post("/reservas/1/confirmar-alteracao", data={
            "data_inicio": dia(10), "data_fim": dia(12),
            "hora_levantamento": "08:00", "hora_entrega": "20:00",
        })
        reserva = self.consultar("SELECT * FROM reservas")[0]
        self.assertEqual((reserva["hora_levantamento"], reserva["hora_entrega"]), ("08:00", "20:00"))

    def test_encurtar_recalcula_o_seguro_e_mantem_a_cadeira(self):
        # 3 dias com seguro e cadeira = 140 €; 1 dia = 25 + 15 + 20 = 60 € -> reembolso de 80 €
        self.pagar(MIRAGE, dia(10), dia(12), extras=[SEGURO, CADEIRA])
        pagina = self.texto(self.navegador.post(
            "/reservas/1/confirmar-alteracao",
            data={"data_inicio": dia(10), "data_fim": dia(10)},
            follow_redirects=True,
        ))
        self.assertIn("80.00 €", pagina)
        reserva = self.consultar("SELECT * FROM reservas")[0]
        self.assertEqual(reserva["valor_total"], 60.0)
        # Balcões e extras não mudam com a alteração
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM reserva_extras")[0][0], 2)

    def test_alteracao_mantem_as_horas_se_nao_forem_indicadas(self):
        self.pagar(MIRAGE, dia(10), dia(12), hora_levantamento="09:00", hora_entrega="19:00")
        self.navegador.post("/reservas/1/confirmar-alteracao", data={"data_inicio": dia(11), "data_fim": dia(13)})
        reserva = self.consultar("SELECT * FROM reservas")[0]
        self.assertEqual((reserva["hora_levantamento"], reserva["hora_entrega"]), ("09:00", "19:00"))


if __name__ == "__main__":
    unittest.main()
