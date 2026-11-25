def test_abrir_caixa_com_sucesso(client, auth_headers):
    # 1. Arrange (Já temos o cabeçalho com token via auth_headers)
    
    # 2. Act: Chama a rota de abrir caixa
    resposta = client.post('/daily/open', headers=auth_headers)
    
    # 3. Assert: Verifica se deu certo
    assert resposta.status_code == 201
    dados = resposta.get_json()
    assert dados["status"] == "aberto"
    assert "id" in dados
    assert dados["adopted_sales"] == 0 # Nenhuma venda pendente ainda

def test_nao_pode_abrir_dois_caixas_no_mesmo_dia(client, auth_headers):
    # 1. Arrange: Abre o primeiro caixa
    client.post('/daily/open', headers=auth_headers)
    
    # 2. Act: Tenta abrir o segundo caixa no mesmo dia
    resposta = client.post('/daily/open', headers=auth_headers)
    
    # 3. Assert: O sistema deve barrar (erro 400)
    assert resposta.status_code == 400
    assert "Já existe um caixa aberto" in resposta.get_json()["error"]

def test_adocao_de_vendas_pendentes(client, auth_headers):
    # 1. Arrange: 
    # Cria uma venda SEM abrir o caixa (vai ficar pendente, daily_register_id = None)
    client.post('/sales', headers=auth_headers, json={
        "amount": 50.0,
        "payment_method": "pix"
    })
    
    # 2. Act: Abre o caixa
    resposta_abertura = client.post('/daily/open', headers=auth_headers)
    
    # 3. Assert: 
    # O caixa deve dizer que adotou 1 venda
    dados_abertura = resposta_abertura.get_json()
    assert dados_abertura["adopted_sales"] == 1
    
    # Busca as vendas do caixa recém-aberto
    caixa_id = dados_abertura["id"]
    resposta_vendas = client.get(f'/sales?daily_register_id={caixa_id}', headers=auth_headers)
    
    # A venda deve estar lá
    assert len(resposta_vendas.get_json()["sales"]) == 1
    assert resposta_vendas.get_json()["sales"][0]["amount"] == 50.0

def test_fechar_caixa_com_calculo_de_lucro(client, auth_headers):
    # 1. Arrange (Prepara o dia)
    client.post('/daily/open', headers=auth_headers)
    
    # Cria uma venda de 100
    client.post('/sales', headers=auth_headers, json={
        "amount": 100.0,
        "payment_method": "dinheiro"
    })
    
    # Cria uma retirada de 30
    client.post('/withdrawals', headers=auth_headers, json={
        "amount": 30.0,
        "reason": "Compra de água"
    })

    # 2. Act (Fecha o caixa)
    resposta = client.post('/daily/close', headers=auth_headers)
    
    # 3. Assert (Verifica as contas)
    assert resposta.status_code == 200
    dados = resposta.get_json()
    
    assert dados["status"] == "fechado"
    assert dados["total_sales"] == 100.0
    assert dados["total_withdrawals"] == 30.0
    assert dados["net_total"] == 70.0 # A conta tem que ser 100 - 30 = 70

def test_nao_pode_registrar_venda_com_valor_negativo(client, auth_headers):
    # 1. Arrange
    client.post('/daily/open', headers=auth_headers)
    
    # 2. Act (Tenta registrar uma venda inválida)
    resposta = client.post('/sales', headers=auth_headers, json={
        "amount": -50.0,
        "payment_method": "pix"
    })
    
    # 3. Assert
    assert resposta.status_code == 400
    assert "Valor inválido" in resposta.get_json()["error"]    

from datetime import date, datetime
from extensions import db
from models.daily_register import DailyRegister
from models.sale import Sale
from models.withdrawal import Withdrawal

def test_relatorio_mensal_e_anual(client, auth_headers, app):
    # 1. Arrange: Insere dados "no passado" direto no banco
    with app.app_context():
        # Cria um caixa falso de Janeiro de 2025
        caixa_passado = DailyRegister(date=date(2025, 1, 15), status='fechado')
        db.session.add(caixa_passado)
        db.session.flush() # Pega o ID do caixa sem comitar ainda

        # Cria uma venda de 500 e uma retirada de 100 nesse caixa
        db.session.add(Sale(date=datetime(2025, 1, 15, 10, 0), amount=500.0, payment_method="pix", daily_register_id=caixa_passado.id))
        db.session.add(Withdrawal(date=datetime(2025, 1, 15, 11, 0), amount=100.0, reason="Troco", daily_register_id=caixa_passado.id))
        db.session.commit()

    # 2. Act: Pede o relatório de Janeiro de 2025
    resposta_mensal = client.get('/reports/monthly?year=2025&month=1', headers=auth_headers)
    
    # 3. Assert: Verifica se a matemática do mês está certa
    assert resposta_mensal.status_code == 200
    dados_mensal = resposta_mensal.get_json()
    assert dados_mensal["total_sales"] == 500.0
    assert dados_mensal["total_withdrawals"] == 100.0
    assert dados_mensal["net_total"] == 400.0

    # 4. Act: Pede o relatório do ano de 2025
    resposta_anual = client.get('/reports/yearly?year=2025', headers=auth_headers)
    
    # 5. Assert: O valor do ano deve ser igual ao do mês (já que só tem 1 mês com dados)
    assert resposta_anual.status_code == 200
    dados_anual = resposta_anual.get_json()
    assert dados_anual["total_sales"] == 500.0
    assert dados_anual["net_total"] == 400.0