"""
Testes da Fase 2 — registo, login, logout, proteção de páginas e
recuperação de password.

Correr só este ficheiro (a partir da pasta do projeto):
    python testes\\test_fase2_autenticacao.py -v
"""

import re
import unittest
from datetime import datetime, timedelta

# base_testes tem de ser importado primeiro: é ele que torna os módulos do
# projeto (app, database, autenticacao) importáveis a partir desta pasta.
from base_testes import TesteComBaseDadosTemporaria

import autenticacao
import database


class TestesValidacaoPassword(unittest.TestCase):
    """
    Testes da função validar_password() isolada (não precisam de base de
    dados nem do site: chamam a função diretamente).
    """

    def test_password_valida_nao_tem_erros(self):
        self.assertEqual(autenticacao.validar_password("Segura123", "Segura123"), [])

    def test_password_com_menos_de_8_caracteres_e_recusada(self):
        self.assertTrue(autenticacao.validar_password("Ab1", "Ab1"))

    def test_password_sem_numero_e_recusada(self):
        self.assertTrue(autenticacao.validar_password("SoLetrasAqui", "SoLetrasAqui"))

    def test_password_sem_letra_e_recusada(self):
        self.assertTrue(autenticacao.validar_password("12345678", "12345678"))

    def test_confirmacao_diferente_e_recusada(self):
        self.assertTrue(autenticacao.validar_password("Segura123", "Outra1234"))


class TestesValidacaoFormatos(unittest.TestCase):
    """Testes das funções utilizador_valido() e email_valido(), isoladas."""

    def test_utilizadores_validos(self):
        for utilizador in ["gab", "gabriel", "gabriel.barbosa", "gabriel_99", "a" * 20]:
            with self.subTest(utilizador=utilizador):
                self.assertTrue(autenticacao.utilizador_valido(utilizador))

    def test_utilizadores_invalidos(self):
        for utilizador in ["ga", "a" * 21, "gabriel b", "gabriel-b", "gabriel@", ""]:
            with self.subTest(utilizador=utilizador):
                self.assertFalse(autenticacao.utilizador_valido(utilizador))

    def test_emails_validos(self):
        for email in ["gabriel@exemplo.pt", "g.barbosa@mail.exemplo.com"]:
            with self.subTest(email=email):
                self.assertTrue(autenticacao.email_valido(email))

    def test_emails_invalidos(self):
        for email in ["gabriel.exemplo.pt", "@exemplo.pt", "gabriel@exemplo", "gabriel@.pt",
                      "gabriel@exemplo.", "gab riel@exemplo.pt", "g@b@exemplo.pt", ""]:
            with self.subTest(email=email):
                self.assertFalse(autenticacao.email_valido(email))


class TestesRegisto(TesteComBaseDadosTemporaria):
    """Formulário de registo: validações e criação da conta."""

    def test_pagina_de_registo_abre(self):
        self.assertEqual(self.navegador.get("/registo").status_code, 200)

    def test_dados_invalidos_sao_recusados_sem_criar_conta(self):
        casos_invalidos = {
            "password curta": {"password": "Ab1", "confirmacao_password": "Ab1"},
            "confirmação diferente": {"confirmacao_password": "Outra1234"},
            "utilizador com espaço": {"utilizador": "gabriel b"},
            "utilizador curto": {"utilizador": "ga"},
            "utilizador longo": {"utilizador": "a" * 21},
            "e-mail inválido": {"email": "gabriel.exemplo.pt"},
            "nome vazio": {"nome": "   "},
        }
        for descricao, campos in casos_invalidos.items():
            # subTest: se um caso falhar, o relatório indica exatamente qual
            with self.subTest(caso=descricao):
                resposta = self.registar(**campos)
                self.assertIn("alert-danger", self.texto(resposta))
                self.assertEqual(self.contar_clientes(), 0)

    def test_varios_erros_sao_mostrados_de_uma_vez(self):
        resposta = self.registar(email="mau", password="curta", confirmacao_password="x")
        self.assertGreaterEqual(self.texto(resposta).count("alert-danger"), 3)

    def test_formulario_mantem_o_nome_mas_nao_a_password_apos_erro(self):
        resposta = self.registar(email="mau")
        self.assertIn('value="Gabriel Barbosa"', self.texto(resposta))
        self.assertNotIn("Segura123", self.texto(resposta))

    def test_registo_valido_cria_conta_e_inicia_sessao(self):
        resposta = self.registar()
        self.assertEqual(resposta.status_code, 302)  # 302 = redirecionamento
        self.assertEqual(self.contar_clientes(), 1)
        self.assertTrue(self.sessao_iniciada())

    def test_registo_volta_a_pagina_pretendida(self):
        resposta = self.registar(proximo="/reservas")
        self.assertTrue(resposta.headers["Location"].endswith("/reservas"))

    def test_password_e_guardada_como_hash(self):
        self.registar()
        cliente = self.consultar("SELECT password_hash FROM clientes")[0]
        self.assertNotEqual(cliente["password_hash"], "Segura123")
        self.assertTrue(cliente["password_hash"].startswith(("scrypt:", "pbkdf2:")))

    def test_escolha_da_newsletter_e_guardada(self):
        self.registar(newsletter="sim")
        self.navegador.get("/logout")
        self.registar(utilizador="sem_news", email="semnews@exemplo.pt")
        valores = dict(self.consultar("SELECT utilizador, newsletter FROM clientes"))
        self.assertEqual(valores, {"gabriel": 1, "sem_news": 0})

    def test_utilizador_repetido_e_recusado_sem_distinguir_maiusculas(self):
        self.registar()
        self.navegador.get("/logout")
        resposta = self.registar(utilizador="GABRIEL", email="outro@exemplo.pt")
        self.assertIn("já está a ser usado", self.texto(resposta))
        self.assertEqual(self.contar_clientes(), 1)

    def test_email_repetido_e_recusado_sem_distinguir_maiusculas(self):
        self.registar()
        self.navegador.get("/logout")
        resposta = self.registar(utilizador="outro", email="GABRIEL@exemplo.pt")
        self.assertIn("Já existe uma conta", self.texto(resposta))
        self.assertEqual(self.contar_clientes(), 1)


class TestesLoginLogout(TesteComBaseDadosTemporaria):
    """Login, logout e menu."""

    def setUp(self):
        super().setUp()
        self.registar()
        self.navegador.get("/logout")

    def test_login_correto_inicia_sessao(self):
        resposta = self.iniciar_sessao()
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(self.sessao_iniciada())

    def test_login_aceita_utilizador_com_maiusculas(self):
        self.iniciar_sessao(utilizador="Gabriel")
        self.assertTrue(self.sessao_iniciada())

    def test_password_errada_e_utilizador_inexistente_dao_a_mesma_mensagem(self):
        mensagem = "Nome de utilizador ou password incorretos."
        self.assertIn(mensagem, self.texto(self.iniciar_sessao(password="Errada123")))
        self.assertIn(mensagem, self.texto(self.iniciar_sessao(utilizador="naoexiste")))
        self.assertFalse(self.sessao_iniciada())

    def test_logout_termina_a_sessao(self):
        self.iniciar_sessao()
        self.navegador.get("/logout")
        self.assertFalse(self.sessao_iniciada())

    def test_menu_muda_com_e_sem_sessao(self):
        pagina_sem_sessao = self.texto(self.navegador.get("/"))
        self.assertIn("Iniciar sessão", pagina_sem_sessao)

        self.iniciar_sessao()
        pagina_com_sessao = self.texto(self.navegador.get("/"))
        self.assertIn("Terminar sessão (Gabriel Barbosa)", pagina_com_sessao)
        self.assertNotIn("Registar-se", pagina_com_sessao)

    def test_com_sessao_iniciada_a_pagina_de_login_redireciona(self):
        self.iniciar_sessao()
        self.assertEqual(self.navegador.get("/login").status_code, 302)


class TestesProtecaoPaginas(TesteComBaseDadosTemporaria):
    """Páginas que exigem sessão iniciada (Jornada 1 da arquitetura)."""

    def setUp(self):
        super().setUp()
        self.registar()
        self.navegador.get("/logout")

    def test_sem_sessao_reservas_redireciona_para_o_login(self):
        resposta = self.navegador.get("/reservas")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login?proximo=/reservas", resposta.headers["Location"])

    def test_depois_do_login_volta_a_pagina_pretendida(self):
        resposta = self.iniciar_sessao(proximo="/reservas")
        self.assertTrue(resposta.headers["Location"].endswith("/reservas"))
        self.assertEqual(self.navegador.get("/reservas").status_code, 200)

    def test_endereco_externo_em_proximo_e_ignorado(self):
        resposta = self.iniciar_sessao(proximo="//site-malicioso.com")
        self.assertNotIn("malicioso", resposta.headers["Location"])


class TestesBotoesSociais(TesteComBaseDadosTemporaria):
    """Botões Facebook, Google e X (apenas demonstrativos)."""

    def test_paginas_das_redes_sociais_abrem(self):
        for rede, nome_rede in [("facebook", "Facebook"), ("google", "Google"), ("x", "X")]:
            with self.subTest(rede=nome_rede):
                resposta = self.navegador.get(f"/login-social/{rede}")
                self.assertEqual(resposta.status_code, 200)
                self.assertIn(f"Iniciar sessão com {nome_rede}", self.texto(resposta))

    def test_rede_social_desconhecida_devolve_erro_404(self):
        self.assertEqual(self.navegador.get("/login-social/myspace").status_code, 404)


class TestesRecuperacaoPassword(TesteComBaseDadosTemporaria):
    """Recuperação de password (versão simulada)."""

    def setUp(self):
        super().setUp()
        self.registar()
        self.navegador.get("/logout")

    def pedir_link(self, email="gabriel@exemplo.pt"):
        """Pede um link de recuperação e devolve o endereço mostrado no ecrã."""
        resposta = self.navegador.post("/recuperar-password", data={"email": email})
        correspondencia = re.search(r'href="http://localhost(/redefinir-password/[^"]+)"', self.texto(resposta))
        return correspondencia.group(1) if correspondencia else None

    def test_email_inexistente_mostra_erro(self):
        resposta = self.navegador.post("/recuperar-password", data={"email": "ninguem@exemplo.pt"})
        self.assertIn("Não existe nenhuma conta", self.texto(resposta))

    def test_email_valido_mostra_link_que_expira_em_10_minutos(self):
        link = self.pedir_link()
        self.assertIsNotNone(link)
        recuperacao = self.consultar("SELECT * FROM recuperacoes_password")[0]
        tempo_restante = datetime.fromisoformat(recuperacao["data_expiracao"]) - datetime.now()
        self.assertTrue(timedelta(minutes=9) < tempo_restante <= timedelta(minutes=10))

    def test_codigo_do_link_tem_32_letras_e_numeros_e_fica_guardado(self):
        codigo_link = self.pedir_link().rsplit("/", 1)[1]
        self.assertEqual(len(codigo_link), 32)
        self.assertTrue(codigo_link.isalnum())
        recuperacao = self.consultar("SELECT codigo FROM recuperacoes_password")[0]
        self.assertEqual(recuperacao["codigo"], codigo_link)

    def test_cada_pedido_gera_um_codigo_diferente(self):
        primeiro_codigo = autenticacao.criar_pedido_recuperacao("gabriel@exemplo.pt")
        segundo_codigo = autenticacao.criar_pedido_recuperacao("gabriel@exemplo.pt")
        self.assertNotEqual(primeiro_codigo, segundo_codigo)

    def test_nova_password_fraca_e_recusada(self):
        resposta = self.navegador.post(self.pedir_link(), data={"password": "fraca", "confirmacao_password": "fraca"})
        self.assertIn("alert-danger", self.texto(resposta))

    def test_nova_password_substitui_a_antiga(self):
        self.navegador.post(self.pedir_link(), data={"password": "NovaPass456", "confirmacao_password": "NovaPass456"})
        self.assertIsNone(autenticacao.autenticar_cliente("gabriel", "Segura123"))
        self.assertIsNotNone(autenticacao.autenticar_cliente("gabriel", "NovaPass456"))

    def test_link_so_pode_ser_usado_uma_vez(self):
        link = self.pedir_link()
        self.navegador.post(link, data={"password": "NovaPass456", "confirmacao_password": "NovaPass456"})
        resposta = self.navegador.get(link)
        self.assertIn("/recuperar-password", resposta.headers["Location"])

    def test_link_expirado_deixa_de_funcionar(self):
        codigo_link = autenticacao.criar_pedido_recuperacao("gabriel@exemplo.pt")
        uma_hora_atras = (datetime.now() - timedelta(hours=1)).isoformat()
        self.executar("UPDATE recuperacoes_password SET data_expiracao = ?", (uma_hora_atras,))
        resposta = self.navegador.get(f"/redefinir-password/{codigo_link}")
        self.assertEqual(resposta.status_code, 302)

    def test_link_inventado_nao_funciona(self):
        self.assertEqual(self.navegador.get("/redefinir-password/inventado123").status_code, 302)


class TestesSessaoInvalida(TesteComBaseDadosTemporaria):
    """
    Erro encontrado ao testar a Fase 5: depois de recriar a base de
    dados, o browser ainda tinha a sessão de um cliente que já não existia,
    e o pagamento dava erro (FOREIGN KEY constraint failed).
    """

    def test_sessao_de_cliente_que_ja_nao_existe_e_terminada(self):
        self.registar()
        self.assertTrue(self.sessao_iniciada())
        database.inicializar_base_dados()  # recria a BD: o cliente deixa de existir
        resposta = self.navegador.get("/reservas", follow_redirects=True)
        self.assertIn("A sua sessão já não é válida", self.texto(resposta))
        self.assertFalse(self.sessao_iniciada())

    def test_pagamento_com_sessao_antiga_nao_da_erro(self):
        self.registar()
        database.inicializar_base_dados()
        resposta = self.navegador.post(
            "/veiculos/1/pagamento",
            data={"data_inicio": (datetime.now() + timedelta(days=10)).date().isoformat(),
                  "data_fim": (datetime.now() + timedelta(days=11)).date().isoformat(),
                  "forma_pagamento": "novo",
                  "numero_cartao": "1234567890123456", "nome_titular": "Gabriel", "codigo_seguranca": "123"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM formas_pagamento")[0][0], 0)


if __name__ == "__main__":
    unittest.main()
