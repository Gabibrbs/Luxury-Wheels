-- Esquema da base de dados do website "Luxury Wheels" (Proposta A - Projeto Final)
-- Entidades mínimas exigidas pelo enunciado: Clientes, Veículos, Reservas, Formas de Pagamento.

-- Apagar as tabelas se já existirem, para permitir recriar a base de dados do zero
-- (a ordem importa: primeiro as tabelas que dependem de outras)
DROP TABLE IF EXISTS mensagens_contacto;
DROP TABLE IF EXISTS reserva_extras;
DROP TABLE IF EXISTS pagamentos;
DROP TABLE IF EXISTS recuperacoes_password;
DROP TABLE IF EXISTS reservas;
DROP TABLE IF EXISTS formas_pagamento;
DROP TABLE IF EXISTS veiculos;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS extras;
DROP TABLE IF EXISTS balcoes;

-- Tabela dos clientes que se registam no website
-- COLLATE NOCASE: "Gabriel" e "gabriel" são tratados como o mesmo valor, tanto
-- na verificação de unicidade como nas pesquisas (login, recuperação).
CREATE TABLE clientes (
    id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    utilizador TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    newsletter INTEGER NOT NULL DEFAULT 0,  -- 1 = quer receber a newsletter, 0 = não
    data_registo TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Tabela dos pedidos de recuperação de password (versão simulada: o link é
-- mostrado no ecrã em vez de ser enviado por e-mail). Cada pedido tem um
-- código aleatório (que faz parte do link), uma data de expiração e a
-- indicação de se já foi usado.
CREATE TABLE recuperacoes_password (
    id_recuperacao INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    data_expiracao TEXT NOT NULL,
    utilizado INTEGER NOT NULL DEFAULT 0,  -- 1 = link já usado (só serve uma vez)
    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente)
);

-- Tabela dos veículos da frota (incluindo os que estejam indisponíveis)
CREATE TABLE veiculos (
    id_veiculo INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    categoria TEXT NOT NULL CHECK (categoria IN ('Pequeno', 'Médio', 'Grande', 'SUV', 'Luxo')),
    tipo_veiculo TEXT NOT NULL CHECK (tipo_veiculo IN ('Carro', 'Moto')),
    transmissao TEXT NOT NULL CHECK (transmissao IN ('Automático', 'Manual')),
    quantidade_pessoas INTEGER NOT NULL,
    imagem TEXT NOT NULL,
    valor_diaria REAL NOT NULL,
    data_ultima_revisao TEXT NOT NULL,
    data_proxima_revisao TEXT NOT NULL,
    data_ultima_legalizacao TEXT NOT NULL,
    -- Bloqueio manual (ex.: avaria): 1 = pode ser alugado, 0 = bloqueado.
    -- A regra automática da revisão/legalização é verificada à parte,
    -- com a data de hoje, sempre que uma página abre (ver reservas.py).
    disponivel INTEGER NOT NULL DEFAULT 1
);

-- Tabela das formas de pagamento associadas a cada cliente
-- Nota de segurança: nunca se guarda o número completo do cartão nem o código
-- verificador (CVV); apenas os últimos 4 dígitos, suficientes para identificar
-- a forma de pagamento escolhida numa reserva.
CREATE TABLE formas_pagamento (
    id_forma_pagamento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    nome_titular TEXT NOT NULL,
    ultimos_digitos TEXT NOT NULL,
    -- 1 = o cliente escolheu guardar o cartão (aparece para reutilizar);
    -- 0 = não guardado: fica só no histórico de pagamentos e reembolsos
    guardado INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente)
);

-- Balcões onde os veículos são levantados e entregues (Fase 6). Qualquer
-- veículo pode ser levantado e entregue em qualquer balcão (sem custo extra).
CREATE TABLE balcoes (
    id_balcao INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    morada TEXT NOT NULL
);

-- Extras que o cliente pode acrescentar à reserva (Fase 6).
--   tipo_preco 'por_dia' -> o preço é multiplicado pelo número de dias;
--   tipo_preco 'fixo'    -> o preço é pago uma só vez, qualquer que seja a duração.
--   so_carros = 1        -> só aparece para carros (não para motos).
CREATE TABLE extras (
    id_extra INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    preco REAL NOT NULL CHECK (preco >= 0),
    tipo_preco TEXT NOT NULL CHECK (tipo_preco IN ('por_dia', 'fixo')),
    so_carros INTEGER NOT NULL DEFAULT 0
);

-- Tabela das reservas efetuadas pelos clientes
CREATE TABLE reservas (
    id_reserva INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    id_veiculo INTEGER NOT NULL,
    data_inicio TEXT NOT NULL,
    data_fim TEXT NOT NULL,
    hora_levantamento TEXT NOT NULL,  -- HH:MM (Fase 6)
    hora_entrega TEXT NOT NULL,       -- HH:MM (Fase 6)
    id_balcao_levantamento INTEGER NOT NULL,
    id_balcao_entrega INTEGER NOT NULL,
    valor_total REAL NOT NULL,
    id_forma_pagamento INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'ativa' CHECK (estado IN ('ativa', 'cancelada')),
    data_criacao TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente),
    FOREIGN KEY (id_veiculo) REFERENCES veiculos (id_veiculo),
    FOREIGN KEY (id_balcao_levantamento) REFERENCES balcoes (id_balcao),
    FOREIGN KEY (id_balcao_entrega) REFERENCES balcoes (id_balcao),
    FOREIGN KEY (id_forma_pagamento) REFERENCES formas_pagamento (id_forma_pagamento)
);

-- Extras escolhidos em cada reserva (uma linha por extra escolhido).
-- A chave primária composta impede que o mesmo extra seja escolhido duas vezes.
CREATE TABLE reserva_extras (
    id_reserva INTEGER NOT NULL,
    id_extra INTEGER NOT NULL,
    PRIMARY KEY (id_reserva, id_extra),
    FOREIGN KEY (id_reserva) REFERENCES reservas (id_reserva),
    FOREIGN KEY (id_extra) REFERENCES extras (id_extra)
);

-- Tabela dos movimentos de pagamento de cada reserva (Fase 5) — tabela extra,
-- permitida pelo enunciado. Guarda o histórico de tudo o que foi pago ou
-- devolvido, e com que cartão:
--   'pagamento' -> pagamento inicial da reserva;
--   'diferenca' -> diferença paga ao alterar as datas para um período mais caro;
--   'reembolso' -> valor devolvido (ao encurtar as datas ou ao cancelar).
-- O valor é sempre positivo; o tipo indica se o dinheiro entrou ou saiu.
CREATE TABLE pagamentos (
    id_pagamento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_reserva INTEGER NOT NULL,
    id_forma_pagamento INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('pagamento', 'diferenca', 'reembolso')),
    valor REAL NOT NULL CHECK (valor > 0),
    data_movimento TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (id_reserva) REFERENCES reservas (id_reserva),
    FOREIGN KEY (id_forma_pagamento) REFERENCES formas_pagamento (id_forma_pagamento)
);

-- Mensagens enviadas pelo formulário da página de contactos (Fase 6).
-- Ficam guardadas para a empresa as ler (não é enviado nenhum e-mail).
CREATE TABLE mensagens_contacto (
    id_mensagem INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    data_envio TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
