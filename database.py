"""
Módulo de acesso à base de dados do website "Luxury Wheels".

Contém as funções para ligar à base de dados SQLite, criar as tabelas a
partir do ficheiro schema.sql e semear os dados iniciais: os 16 veículos de
exemplo, os balcões e os extras.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

# Caminho do ficheiro da base de dados, guardado na mesma pasta deste módulo
CAMINHO_BASE_DADOS = Path(__file__).parent / "luxury_wheels.db"

# Caminho do ficheiro com as instruções SQL de criação das tabelas
CAMINHO_ESQUEMA_SQL = Path(__file__).parent / "schema.sql"


def obter_ligacao():
    """
    Abre e devolve uma ligação à base de dados SQLite, tal como no
    Módulo 5, Unidade 4 do curso (sqlite3.connect).

    Quem chama esta função fica responsável por fechar a ligação no fim
    (ligacao.close()), normalmente num bloco try/finally (Módulo 4,
    Unidade 3), para garantir que é fechada mesmo que ocorra um erro:

        ligacao = database.obter_ligacao()
        try:
            cursor = ligacao.cursor()
            cursor.execute(...)
            ligacao.commit()
        finally:
            ligacao.close()

    Duas configurações extra:
    - row_factory = sqlite3.Row: cada registo devolvido pelas consultas pode
      ser lido pelo nome da coluna, como num dicionário (veiculo["marca"]),
      em vez de pela posição (veiculo[1]) — o código fica mais legível.
    - PRAGMA foreign_keys = ON: ativa a verificação das chaves estrangeiras
      (FOREIGN KEY), que no SQLite vem desligada por defeito.
    """
    ligacao = sqlite3.connect(CAMINHO_BASE_DADOS)
    ligacao.row_factory = sqlite3.Row
    ligacao.execute("PRAGMA foreign_keys = ON")
    return ligacao


def inicializar_base_dados():
    """
    Cria (ou recria) as tabelas da base de dados, a partir do ficheiro
    schema.sql, e semeia os veículos de exemplo, os balcões e os extras.
    """
    # Lê o ficheiro com as instruções SQL (como no Módulo 5, Unidade 1 — Ficheiros)
    with open(CAMINHO_ESQUEMA_SQL, "r", encoding="utf-8") as ficheiro_esquema:
        instrucoes_sql = ficheiro_esquema.read()

    ligacao = obter_ligacao()
    try:
        cursor = ligacao.cursor()
        # executescript executa várias instruções SQL de uma só vez
        cursor.executescript(instrucoes_sql)
        semear_veiculos_exemplo(cursor)
        semear_balcoes_e_extras(cursor)
        ligacao.commit()
    finally:
        ligacao.close()


def semear_veiculos_exemplo(cursor):
    """
    Insere um conjunto variado de veículos de exemplo na base de dados, para
    permitir experimentar a pesquisa, os filtros e as regras de disponibilidade.

    Os veículos cobrem propositadamente diferentes categorias, tipos,
    transmissões, quantidades de pessoas e situações de revisão/legalização
    (incluindo casos que devem ficar automaticamente indisponíveis).
    """
    hoje = date.today()

    # (marca, modelo, categoria, tipo_veiculo, transmissao, quantidade_pessoas,
    #  imagem, valor_diaria, data_ultima_revisao, data_proxima_revisao, data_ultima_legalizacao)
    veiculos_exemplo = [
        ("Mitsubishi", "Mirage", "Pequeno", "Carro", "Manual", 4,
         "cars/5.jpg", 25.0,
         hoje - timedelta(days=60), hoje + timedelta(days=120), hoje - timedelta(days=100)),
        ("Volkswagen", "Golf Variante", "Médio", "Carro", "Manual", 5,
         "cars/6.jpg", 35.0,
         hoje - timedelta(days=30), hoje + timedelta(days=150), hoje - timedelta(days=200)),
        ("Subaru", "Legacy", "Médio", "Carro", "Automático", 5,
         "cars/3.jpg", 40.0,
         hoje - timedelta(days=20), hoje + timedelta(days=200), hoje - timedelta(days=50)),
        ("Rolls-Royce", "Ghost", "Luxo", "Carro", "Automático", 4,
         "cars/7.jpg", 120.0,
         hoje - timedelta(days=10), hoje + timedelta(days=300), hoje - timedelta(days=30)),
        ("Audi", "Q8", "SUV", "Carro", "Automático", 5,
         "cars/s4.jpg", 95.0,
         hoje - timedelta(days=15), hoje + timedelta(days=180), hoje - timedelta(days=90)),
        ("Mitsubishi", "Pajero", "SUV", "Carro", "Manual", 7,
         "cars/1.jpg", 60.0,
         hoje - timedelta(days=45), hoje + timedelta(days=90), hoje - timedelta(days=250)),
        ("Honda", "CB500", "Médio", "Moto", "Manual", 2,
         "cars/moto1.jpg", 20.0,
         hoje - timedelta(days=25), hoje + timedelta(days=160), hoje - timedelta(days=40)),
        ("Yamaha", "MT-07", "Pequeno", "Moto", "Manual", 2,
         "cars/moto2.jpg", 18.0,
         hoje - timedelta(days=5), hoje + timedelta(days=170), hoje - timedelta(days=60)),
        # Veículo com a próxima revisão já ultrapassada -> deve ficar indisponível
        ("Mitsubishi", "Space Star", "Pequeno", "Carro", "Manual", 4,
         "cars/b1.jpg", 22.0,
         hoje - timedelta(days=200), hoje - timedelta(days=5), hoje - timedelta(days=100)),
        # Veículo com a legalização há mais de 1 ano -> deve ficar indisponível
        ("BMW", "Série 3", "Grande", "Carro", "Automático", 5,
         "cars/s3.jpg", 85.0,
         hoje - timedelta(days=40), hoje + timedelta(days=140), hoje - timedelta(days=400)),
        # Fase 6 — mais 6 modelos (fotografias do template que estavam por usar).
        # Ficam no fim da lista para não mudar os ids dos veículos anteriores.
        ("Subaru", "Forester", "SUV", "Carro", "Automático", 5,
         "cars/2.jpg", 55.0,
         hoje - timedelta(days=35), hoje + timedelta(days=210), hoje - timedelta(days=120)),
        ("Toyota", "Tacoma", "Grande", "Carro", "Automático", 5,
         "cars/8.jpg", 70.0,
         hoje - timedelta(days=50), hoje + timedelta(days=130), hoje - timedelta(days=150)),
        ("Porsche", "911", "Luxo", "Carro", "Automático", 4,
         "cars/9.jpg", 180.0,
         hoje - timedelta(days=12), hoje + timedelta(days=250), hoje - timedelta(days=20)),
        ("Alfa Romeo", "4C", "Luxo", "Carro", "Automático", 2,
         "cars/s1.jpg", 150.0,
         hoje - timedelta(days=28), hoje + timedelta(days=190), hoje - timedelta(days=70)),
        ("Nissan", "Qashqai", "SUV", "Carro", "Manual", 5,
         "cars/s2.jpg", 45.0,
         hoje - timedelta(days=40), hoje + timedelta(days=175), hoje - timedelta(days=180)),
        ("Mitsubishi", "Lancer Evolution", "Médio", "Carro", "Manual", 5,
         "cars/v2.jpg", 65.0,
         hoje - timedelta(days=22), hoje + timedelta(days=160), hoje - timedelta(days=90)),
    ]

    for veiculo in veiculos_exemplo:
        (marca, modelo, categoria, tipo_veiculo, transmissao, quantidade_pessoas,
         imagem, valor_diaria, data_ultima_revisao, data_proxima_revisao,
         data_ultima_legalizacao) = veiculo

        # Todos os veículos são criados com disponivel = 1 (sem bloqueio
        # manual). A regra do enunciado (legalização com mais de 1 ano ou
        # revisão já ultrapassada) NÃO é guardada aqui: é verificada sempre
        # que uma página abre, comparando as datas com o dia de hoje — ver
        # reservas.CONDICAO_VEICULO_DISPONIVEL. Assim, o Mitsubishi Space Star
        # e o BMW Série 3 da lista acima ficam indisponíveis automaticamente.
        cursor.execute(
            """
            INSERT INTO veiculos (
                marca, modelo, categoria, tipo_veiculo, transmissao,
                quantidade_pessoas, imagem, valor_diaria,
                data_ultima_revisao, data_proxima_revisao,
                data_ultima_legalizacao, disponivel
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                marca, modelo, categoria, tipo_veiculo, transmissao,
                quantidade_pessoas, imagem, valor_diaria,
                data_ultima_revisao.isoformat(), data_proxima_revisao.isoformat(),
                data_ultima_legalizacao.isoformat(),
            ),
        )



def semear_balcoes_e_extras(cursor):
    """
    Insere os balcões de levantamento/entrega e os extras que podem ser
    acrescentados às reservas (Fase 6).
    """
    balcoes = [
        ("Lisboa – Aeroporto", "Aeroporto de Lisboa, Terminal 1 (zona de chegadas), Lisboa"),
        ("Lisboa – Centro", "Avenida da Liberdade, 100, 1250-146 Lisboa"),
        ("Porto – Aeroporto", "Aeroporto do Porto (zona de chegadas), Maia"),
        ("Faro – Aeroporto", "Aeroporto de Faro (zona de chegadas), Faro"),
    ]
    cursor.executemany("INSERT INTO balcoes (nome, morada) VALUES (?, ?)", balcoes)

    # (nome, preço, tipo de preço, só para carros: 1 = sim)
    extras = [
        ("Seguro contra todos os riscos", 15.0, "por_dia", 0),
        ("Cadeira de criança", 20.0, "fixo", 1),
    ]
    cursor.executemany(
        "INSERT INTO extras (nome, preco, tipo_preco, so_carros) VALUES (?, ?, ?, ?)", extras
    )


if __name__ == "__main__":
    # Permite recriar a base de dados diretamente, correndo:
    #   python database.py
    inicializar_base_dados()
    print(f"Base de dados criada/recriada em: {CAMINHO_BASE_DADOS}")
