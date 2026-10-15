# Luxury Wheels

**Português** | [English](#english)

Website de aluguer de veículos (carros e motos), feito em **Python + Flask** com base de dados **SQLite**.
Projeto final do curso de Programação Python (Tokio School, 400 h) — autor: Gabriel Barbosa.

## Funcionalidades

- Pesquisa de veículos com filtros (categoria, tipo, transmissão, valor da diária, quantidade de pessoas).
- Registo, início de sessão e recuperação de password (simulada); passwords guardadas como *hash*.
- Reservas com datas e horas, balcões e extras; pagamento simulado com valor discriminado antes de pagar.
- Alterar e cancelar reservas, com pagamento da diferença ou reembolso.
- Regras de negócio: disponibilidade do veículo (revisão e legalização), máximo de 30 dias, dia de início e de fim contam ambos.
- **173 testes automáticos** (`unittest`), cada um com uma base de dados temporária.

## Como correr

Requisitos: Python 3.10 ou superior.

```
pip install -r requirements.txt
python app.py
```

Abrir no browser: http://127.0.0.1:5000 (a base de dados é criada na primeira execução).

Testes:

```
python -m unittest discover testes -v
```

## Estrutura

```
app.py            rotas Flask
autenticacao.py   registo, início de sessão, recuperação de password
reservas.py       disponibilidade, datas, horas, extras, pagamentos
contactos.py      formulário de contactos
database.py       ligação à base de dados e dados iniciais
schema.sql        tabelas
templates/        páginas HTML (Jinja2)
assets/           CSS, JavaScript e imagens
testes/           testes automáticos (unittest)
```

## Reconhecimentos

O aspeto visual (HTML, CSS, JavaScript, imagens e ícones da pasta `assets/`) vem do template
fornecido pelo curso, adaptado para este projeto. Bibliotecas: Flask (com Jinja2 e Werkzeug)
e a biblioteca padrão do Python.

Pagamentos, reembolsos e e-mails são simulados: nenhum valor é cobrado e nenhum e-mail é enviado.

---

## English

Car and motorbike rental website built with **Python + Flask** and a **SQLite** database.
Final project of the Python Programming course (Tokio School, 400 h) — author: Gabriel Barbosa.

### Features

- Vehicle search with filters (category, type, transmission, daily price, number of passengers).
- Sign-up, login and password recovery (simulated); passwords stored as hashes.
- Bookings with dates and times, pick-up points and extras; simulated payment with the full price shown before paying.
- Change and cancel bookings, with payment of the difference or a refund.
- Business rules: vehicle availability (inspection and legalisation dates), 30-day maximum, both start and end days counted.
- **173 automated tests** (`unittest`), each using a temporary database.

### How to run

Requirements: Python 3.10 or higher.

```
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser (the database is created on the first run).

Tests:

```
python -m unittest discover testes -v
```

### Credits

The visual design (HTML, CSS, JavaScript, images and icons in `assets/`) comes from the template
provided by the course, adapted for this project. Libraries: Flask (with Jinja2 and Werkzeug)
and the Python standard library.

Payments, refunds and emails are simulated: nothing is charged and no email is sent.
