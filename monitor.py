# -*- coding: utf-8 -*-
"""
Monitor de Sites — verifica se os sites estão no ar e envia relatório no WhatsApp.

Feito para rodar no GitHub Actions, mas também funciona localmente:
    pip install -r requirements.txt
    python monitor.py

Canais de aviso (configure UM ou os DOIS — o script usa os que existirem):

  Telegram (recomendado — grátis e estável):
    TELEGRAM_TOKEN    -> token do bot criado no @BotFather
    TELEGRAM_CHAT_ID  -> seu ID de usuário (pegue no @userinfobot)

  WhatsApp via Green API (green-api.com — você conecta seu próprio WhatsApp):
    WHATSAPP_FONE      -> seu número com código do país, ex: +5514999999999
    GREEN_API_INSTANCE -> idInstance do painel da Green API, ex: 7103123456
    GREEN_API_TOKEN    -> apiTokenInstance do painel
    GREEN_API_URL      -> opcional; a URL "apiUrl" que o painel mostrar
                          (padrão: https://api.green-api.com)

  WhatsApp via CallMeBot (quando o bot voltar a aceitar cadastros):
    WHATSAPP_FONE     -> seu número com código do país, ex: +5514999999999
    CALLMEBOT_APIKEY  -> a chave que o CallMeBot te manda no WhatsApp

  Opcional:
    SO_ALERTAS        -> "true" = só manda mensagem se algum site cair.
                         Qualquer outro valor = manda o relatório sempre.
"""

import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests

# ---------------------------------------------------------------- configurações

TIMEOUT_SEGUNDOS = 15   # tempo máximo esperando cada site responder
TENTATIVAS = 2          # tenta de novo antes de declarar que o site caiu
PAUSA_ENTRE_TENTATIVAS = 5  # segundos

ARQUIVO_SITES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites.txt")

# Alguns servidores bloqueiam robôs sem User-Agent; fingimos ser um navegador comum
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

FUSO_BRASILIA = timezone(timedelta(hours=-3))


# ------------------------------------------------------------------- funções

def carregar_sites():
    """Lê o sites.txt. Formato de cada linha: Nome do site | https://endereco"""
    sites = []
    with open(ARQUIVO_SITES, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue  # ignora linhas vazias e comentários
            if "|" in linha:
                nome, url = [parte.strip() for parte in linha.split("|", 1)]
            else:
                nome, url = linha, linha
            sites.append((nome, url))
    return sites


def verificar_site(nome, url):
    """Retorna (esta_online, detalhe)."""
    detalhe_erro = "erro desconhecido"
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            inicio = time.time()
            resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS,
                                    headers=HEADERS, allow_redirects=True)
            milissegundos = int((time.time() - inicio) * 1000)
            if resposta.status_code < 400:
                return True, f"{resposta.status_code}, {milissegundos}ms"
            detalhe_erro = f"HTTP {resposta.status_code}"
        except requests.exceptions.Timeout:
            detalhe_erro = f"sem resposta em {TIMEOUT_SEGUNDOS}s"
        except requests.exceptions.SSLError:
            detalhe_erro = "certificado SSL com problema"
        except requests.exceptions.ConnectionError:
            detalhe_erro = "conexão recusada / DNS falhou"
        except requests.exceptions.RequestException as erro:
            detalhe_erro = type(erro).__name__

        if tentativa < TENTATIVAS:
            time.sleep(PAUSA_ENTRE_TENTATIVAS)

    return False, detalhe_erro


def montar_relatorio(resultados):
    agora = datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")
    caidos = [r for r in resultados if not r["online"]]

    linhas = [f"🖥️ *Monitor de Sites* — {agora} (Brasília)", ""]
    for r in resultados:
        if r["online"]:
            linhas.append(f"✅ {r['nome']} — online ({r['detalhe']})")
        else:
            linhas.append(f"🔴 {r['nome']} — *FORA DO AR* ({r['detalhe']})")

    linhas.append("")
    if caidos:
        linhas.append(f"⚠️ *Atenção: {len(caidos)} site(s) com problema!*")
    else:
        linhas.append(f"🟢 Tudo normal! {len(resultados)} site(s) online.")

    return "\n".join(linhas), caidos


def enviar_telegram(texto):
    """Retorna True se enviou, False se falhou, None se não está configurado."""
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    dados = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    resposta = requests.post(url, data=dados, timeout=30)
    if resposta.status_code == 400:
        # Algum caractere quebrou o Markdown — reenvia como texto puro
        dados.pop("parse_mode")
        resposta = requests.post(url, data=dados, timeout=30)
    if resposta.status_code >= 400:
        print(f"ERRO ao enviar Telegram: HTTP {resposta.status_code}")
        print(resposta.text[:300])
        return False
    print("Mensagem enviada no Telegram com sucesso.")
    return True


def enviar_greenapi(texto):
    """Retorna True se enviou, False se falhou, None se não está configurado."""
    instancia = os.environ.get("GREEN_API_INSTANCE", "").strip()
    token = os.environ.get("GREEN_API_TOKEN", "").strip()
    fone = os.environ.get("WHATSAPP_FONE", "").strip()
    base = os.environ.get("GREEN_API_URL", "https://api.green-api.com").strip().rstrip("/")
    if not instancia or not token or not fone:
        return None

    # A Green API identifica o destinatário como 5514999999999@c.us (sem o "+")
    numero_limpo = fone.lstrip("+").replace(" ", "").replace("-", "")
    url = f"{base}/waInstance{instancia}/sendMessage/{token}"
    resposta = requests.post(
        url,
        json={"chatId": f"{numero_limpo}@c.us", "message": texto},
        timeout=60,
    )
    if resposta.status_code >= 400:
        print(f"ERRO ao enviar via Green API: HTTP {resposta.status_code}")
        print(resposta.text[:300])
        return False
    print("Mensagem enviada no WhatsApp (Green API) com sucesso.")
    return True


def enviar_callmebot(texto):
    """Retorna True se enviou, False se falhou, None se não está configurado."""
    fone = os.environ.get("WHATSAPP_FONE", "").strip()
    apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    if not fone or not apikey:
        return None

    url = (
        "https://api.callmebot.com/whatsapp.php"
        f"?phone={urllib.parse.quote(fone)}"
        f"&apikey={urllib.parse.quote(apikey)}"
        f"&text={urllib.parse.quote(texto)}"
    )
    resposta = requests.get(url, timeout=60)
    if resposta.status_code >= 400:
        print(f"ERRO ao enviar WhatsApp: HTTP {resposta.status_code}")
        print(resposta.text[:300])
        return False
    print("Mensagem enviada no WhatsApp com sucesso.")
    return True


def enviar_avisos(texto):
    """Dispara em todos os canais configurados. Encerra com erro se nenhum funcionar."""
    resultados = {
        "Telegram": enviar_telegram(texto),
        "WhatsApp (Green API)": enviar_greenapi(texto),
        "WhatsApp (CallMeBot)": enviar_callmebot(texto),
    }
    configurados = {canal: ok for canal, ok in resultados.items() if ok is not None}

    if not configurados:
        print("ERRO: nenhum canal de aviso configurado.")
        print("Configure no GitHub os secrets de pelo menos um canal:")
        print("  Telegram:  TELEGRAM_TOKEN + TELEGRAM_CHAT_ID")
        print("  Green API: WHATSAPP_FONE + GREEN_API_INSTANCE + GREEN_API_TOKEN")
        print("  CallMeBot: WHATSAPP_FONE + CALLMEBOT_APIKEY")
        sys.exit(1)

    if not any(configurados.values()):
        print("ERRO: todos os canais configurados falharam ao enviar.")
        sys.exit(1)


# -------------------------------------------------------------------- execução

def main():
    sites = carregar_sites()
    if not sites:
        print("Nenhum site cadastrado no sites.txt — nada a fazer.")
        return

    print(f"Verificando {len(sites)} site(s)...\n")
    resultados = []
    for nome, url in sites:
        online, detalhe = verificar_site(nome, url)
        situacao = "ONLINE" if online else "FORA DO AR"
        print(f"  [{situacao}] {nome} ({url}) — {detalhe}")
        resultados.append({"nome": nome, "url": url,
                           "online": online, "detalhe": detalhe})

    relatorio, caidos = montar_relatorio(resultados)
    print("\n----- relatório -----\n" + relatorio + "\n---------------------\n")

    so_alertas = os.environ.get("SO_ALERTAS", "false").strip().lower() == "true"
    if so_alertas and not caidos:
        print("Tudo online e SO_ALERTAS=true — não vou mandar mensagem.")
    else:
        enviar_avisos(relatorio)

    # Se algum site caiu, encerra com erro: o GitHub Actions fica com ❌ e ainda
    # te manda um e-mail de aviso — um segundo canal de alerta, de graça.
    if caidos:
        sys.exit(1)


if __name__ == "__main__":
    main()
