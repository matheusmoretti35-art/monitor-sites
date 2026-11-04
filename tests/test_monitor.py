"""Testes das funções puras do monitor (sem rede)."""

from datetime import datetime, timedelta, timezone

import pytest

import monitor


@pytest.mark.parametrize(
    ("segundos", "esperado"),
    [(45, "45s"), (1234, "20min"), (8000, "2h13min"), (200000, "2d 7h")],
)
def test_formatar_duracao(segundos, esperado):
    assert monitor.formatar_duracao(segundos) == esperado


def test_carregar_sites_ignora_comentarios_e_campo_opcional(tmp_path, monkeypatch):
    arquivo = tmp_path / "sites.txt"
    arquivo.write_text(
        "# comentário\n"
        "\n"
        "Loja | https://loja.com | Minha Loja\n"
        "Blog | https://blog.com\n"
        "https://so-url.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor, "ARQUIVO_SITES", str(arquivo))

    assert monitor.carregar_sites() == [
        {"nome": "Loja", "url": "https://loja.com", "texto": "Minha Loja"},
        {"nome": "Blog", "url": "https://blog.com", "texto": ""},
        {"nome": "https://so-url.com", "url": "https://so-url.com", "texto": ""},
    ]


def test_uptime():
    assert monitor.uptime({}) is None
    assert monitor.uptime({"historico": "1111"}) == "100%"
    assert monitor.uptime({"historico": "1110"}) == "75,0%"


def test_atualizar_status_detecta_queda_e_retorno():
    site = {"nome": "Loja", "url": "https://loja.com", "texto": ""}
    status = {"sites": {}}
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert monitor.atualizar_status(status, site, {"online": True, "detalhe": "200"}, t0) is None

    caiu = monitor.atualizar_status(
        status, site, {"online": False, "detalhe": "HTTP 500"}, t0 + timedelta(hours=1)
    )
    assert caiu == {"tipo": "caiu", "motivo": "HTTP 500"}

    voltou = monitor.atualizar_status(
        status, site, {"online": True, "detalhe": "200"}, t0 + timedelta(hours=3)
    )
    assert voltou == {"tipo": "voltou", "duracao_s": 7200}

    registro = status["sites"]["https://loja.com"]
    assert registro["historico"] == "101"
    assert registro["ultimo_incidente"]["motivo"] == "HTTP 500"


def test_decidir_envio_modo_alertas_so_envia_com_novidade():
    agora = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
    assert monitor.decidir_envio("alertas", [], [], [], {}, agora, 8) == (False, False)
    assert monitor.decidir_envio("alertas", [{"tipo": "caiu"}], [], [], {}, agora, 8) == (True, False)


def test_decidir_envio_modo_diario_manda_um_resumo_por_dia():
    agora = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)  # 12h em Brasília
    assert monitor.decidir_envio("diario", [], [], [], {}, agora, 8) == (True, True)
    status = {"ultimo_resumo": "2026-01-01"}
    assert monitor.decidir_envio("diario", [], [], [], status, agora, 8) == (False, False)


def test_para_html_telegram_escapa_e_converte_negrito():
    assert monitor.para_html_telegram("*Oi* <b>") == "<b>Oi</b> &lt;b&gt;"
