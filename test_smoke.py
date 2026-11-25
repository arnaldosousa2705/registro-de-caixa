def test_se_o_servidor_esta_de_pe(client):
    # Tenta acessar a rota de status do caixa sem token (deve dar 401)
    resposta = client.get('/daily/status')
    assert resposta.status_code == 401