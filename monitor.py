# -*- coding: utf-8 -*-
"""
Monitor de Sites — verifica se os sites estão no ar, guarda o histórico
(caiu / voltou / uptime), vigia o vencimento do SSL e avisa no Telegram
e/ou WhatsApp.

Feito para rodar no GitHub Actions, mas também funciona localmente:
    pip install -r requirements.txt
    python monitor.py

sites.txt — um site por linha:
    Nome | https://endereco | texto que deve existir na página (opcional)
O 3º campo pega os "falsos 200": página de manutenção, domínio estacionado,
erro do CMS que responde 200 etc.

status.json — criado e atualizado pelo próprio script. Guarda desde quando
cada site está no estado atual, as últimas checagens (uptime) e o último
incidente. No GitHub Actions ele é commitado de volta no repositório.

Canais de aviso (configure um ou mais — o script usa os que existirem):

  Telegram (recomendado — grátis e estável):
    TELEGRAM_TOKEN    -> token do bot criado no @BotFather
    TELEGRAM_CHAT_ID  -> seu ID de usuário (pegue no @userinfobot)

  WhatsApp via Green API (green-api.com — você conecta seu próprio WhatsApp):
    WHATSAPP_FONE      -> seu número com código do país, ex: +5514999999999
    GREEN_API_INSTANCE -> idInstance do painel da Green API
    GREEN_API_TOKEN    -> apiTokenInstance do painel
    GREEN_API_URL      -> opcional; a "apiUrl" que o painel mostrar

  WhatsApp via CallMeBot (quando o bot voltar a aceitar cadastros):
    WHATSAPP_FONE     -> seu número com código do país
    CALLMEBOT_APIKEY  -> a chave que o CallMeBot te manda

Quando enviar (variável MODO):
    completo (padrão) -> relatório completo a toda execução
    diario            -> só quando algo muda (caiu, voltou, SSL vencendo,
                         site ainda fora) + um resumo por dia a partir da
                         RESUMO_HORA (padrão 8h de Brasília)
    alertas           -> só quando algo muda
"""

import html
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests

# O terminal do Windows às vezes não sabe imprimir emoji (cp1252) — evita quebrar por isso
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- configurações

TIMEOUT_SEGUNDOS = 15        # tempo máximo esperando cada site responder
TENTATIVAS = 2               # tenta de novo antes de declarar que o site caiu
PAUSA_ENTRE_TENTATIVAS = 5   # segundos
LENTO_MS = 5000              # acima disso o site ganha um 🐢 no relatório
SSL_AVISO_DIAS = 14          # avisa quando o certificado vence em N dias ou menos
HISTORICO_MAXIMO = 180       # checagens guardadas por site (~30 dias a 6/dia)

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_SITES = os.path.join(PASTA, "sites.txt")
ARQUIVO_STATUS = os.path.join(PASTA, "status.json")

# Alguns servidores bloqueiam robôs sem User-Agent; fingimos ser um navegador comum
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

# O Brasil não tem mais horário de verão desde 2019, então o -3 fixo é correto
FUSO_BRASILIA = timezone(timedelta(hours=-3))


# ------------------------------------------------------------------ utilidades

def agora_utc():
    return datetime.now(timezone.utc)


def formatar_duracao(segundos):
    """1234 -> '20min', 8000 -> '2h13min', 200000 -> '2d 7h'"""
    segundos = int(segundos)
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return f"{dias}d {horas}h"
    if horas:
        return f"{horas}h{minutos:02d}min"
    if minutos:
        return f"{minutos}min"
    return f"{segundos}s"


def carregar_sites():
    """Lê o sites.txt. Formato: Nome | https://endereco | texto esperado (opcional)"""
    sites = []
    with open(ARQUIVO_SITES, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue  # ignora linhas vazias e comentários
            partes = [parte.strip() for parte in linha.split("|")]
            if len(partes) == 1:
                partes = [partes[0], partes[0]]
            nome, url = partes[0], partes[1]
            texto = partes[2] if len(partes) > 2 else ""
            sites.append({"nome": nome, "url": url, "texto": texto})
    return sites


def carregar_status():
    try:
        with open(ARQUIVO_STATUS, encoding="utf-8") as arquivo:
            status = json.load(arquivo)
    except (FileNotFoundError, json.JSONDecodeError):
        status = {}
    status.setdefault("sites", {})
    return status


def salvar_status(status):
    with open(ARQUIVO_STATUS, "w", encoding="utf-8") as arquivo:
        json.dump(status, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")


# ---------------------------------------------------------------- verificações

def verificar_site(site):
    """Retorna dict com online (bool), detalhe (str) e ms (int ou None)."""
    detalhe_erro = "erro desconhecido"
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            inicio = time.time()
            resposta = requests.get(site["url"], timeout=TIMEOUT_SEGUNDOS,
                                    headers=HEADERS, allow_redirects=True)
            ms = int((time.time() - inicio) * 1000)
            if resposta.status_code >= 400:
                detalhe_erro = f"HTTP {resposta.status_code}"
            elif site["texto"] and site["texto"].lower() not in resposta.text.lower():
                detalhe_erro = (f"HTTP {resposta.status_code}, mas a página não tem "
                                f"\"{site['texto']}\"")
            else:
                return {"online": True, "detalhe": f"{resposta.status_code}, {ms}ms", "ms": ms}
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

    return {"online": False, "detalhe": detalhe_erro, "ms": None}


def dias_para_vencer_ssl(url):
    """Quantos dias faltam para o certificado vencer. None se não for https ou der erro."""
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https" or not partes.hostname:
        return None
    try:
        contexto = ssl.create_default_context()
        with socket.create_connection((partes.hostname, partes.port or 443), timeout=10) as sock, \
             contexto.wrap_socket(sock, server_hostname=partes.hostname) as conexao:
            certificado = conexao.getpeercert()
        validade = datetime.strptime(certificado["notAfter"], "%b %d %H:%M:%S %Y %Z")
        validade = validade.replace(tzinfo=timezone.utc)
        return (validade - agora_utc()).days
    except (OSError, ssl.SSLError, ValueError, KeyError):
        return None


def atualizar_status(status, site, resultado, agora):
    """Atualiza o registro do site no status e devolve o evento ('caiu'/'voltou'), se houve."""
    registro = status["sites"].get(site["url"])
    evento = None

    if registro is None:
        registro = {"online": resultado["online"], "desde": agora.isoformat(),
                    "historico": "", "ultimo_incidente": None}
        status["sites"][site["url"]] = registro
    elif registro["online"] and not resultado["online"]:
        evento = {"tipo": "caiu", "motivo": resultado["detalhe"]}
        registro.update(online=False, desde=agora.isoformat(), motivo=resultado["detalhe"])
    elif not registro["online"] and resultado["online"]:
        inicio = datetime.fromisoformat(registro["desde"])
        duracao = int((agora - inicio).total_seconds())
        registro["ultimo_incidente"] = {"inicio": registro["desde"], "fim": agora.isoformat(),
                                        "duracao_s": duracao,
                                        "motivo": registro.get("motivo", "")}
        evento = {"tipo": "voltou", "duracao_s": duracao}
        registro.update(online=True, desde=agora.isoformat())
        registro.pop("motivo", None)

    registro["nome"] = site["nome"]
    registro["ultima_checagem"] = agora.isoformat()
    marca = "1" if resultado["online"] else "0"
    registro["historico"] = (registro.get("historico", "") + marca)[-HISTORICO_MAXIMO:]
    return evento


def uptime(registro):
    """'100%' ou '99,4%' com base nas últimas checagens; None se ainda não há histórico."""
    historico = registro.get("historico", "")
    if not historico:
        return None
    pct = 100 * historico.count("1") / len(historico)
    return "100%" if pct >= 99.95 else f"{pct:.1f}%".replace(".", ",")


# ------------------------------------------------------------------ relatório

def montar_relatorio(resultados, eventos, avisos_ssl, agora):
    """Monta o texto usando *negrito* (formato do WhatsApp; vira <b> no Telegram)."""
    agora_brt = agora.astimezone(FUSO_BRASILIA)
    linhas = [f"🖥️ *Monitor de Sites* — {agora_brt:%d/%m/%Y %H:%M} (Brasília)", ""]

    for ev in eventos:
        if ev["tipo"] == "caiu":
            linhas.append(f"🔴 *CAIU:* {ev['nome']} — {ev['motivo']}")
        else:
            linhas.append(f"🟢 *VOLTOU:* {ev['nome']} — ficou fora por {formatar_duracao(ev['duracao_s'])}")
    for nome, dias in avisos_ssl:
        if dias < 0:
            quando = f"VENCEU há {-dias} dia(s)"
        elif dias == 0:
            quando = "vence HOJE"
        else:
            data = (agora + timedelta(days=dias)).astimezone(FUSO_BRASILIA)
            quando = f"vence em {dias} dia(s) ({data:%d/%m})"
        linhas.append(f"⚠️ *SSL* de {nome} {quando} — renove!")
    if eventos or avisos_ssl:
        linhas.append("")

    for r in resultados:
        registro = r["registro"]
        up = uptime(registro)
        sufixo_uptime = f" · uptime {up}" if up else ""
        if r["online"]:
            lento = " 🐢" if r["ms"] and r["ms"] > LENTO_MS else ""
            linhas.append(f"✅ {r['nome']} — {r['detalhe']}{lento}{sufixo_uptime}")
        else:
            fora_ha = (agora - datetime.fromisoformat(registro["desde"])).total_seconds()
            ha = "agora" if fora_ha < 60 else f"há {formatar_duracao(fora_ha)}"
            linhas.append(f"🔴 {r['nome']} — *FORA DO AR* ({r['detalhe']}) · {ha}{sufixo_uptime}")

    linhas.append("")
    caidos = [r for r in resultados if not r["online"]]
    if caidos:
        linhas.append(f"⚠️ *{len(caidos)} site(s) com problema!*")
    else:
        linhas.append(f"🟢 *Tudo normal!* {len(resultados)} site(s) online.")

    incidentes = [(r["nome"], r["registro"]["ultimo_incidente"])
                  for r in resultados if r["registro"].get("ultimo_incidente")]
    if incidentes:
        nome, inc = max(incidentes, key=lambda item: item[1]["fim"])
        fim = datetime.fromisoformat(inc["fim"]).astimezone(FUSO_BRASILIA)
        linhas.append(f"🕓 Último incidente: {nome}, {fim:%d/%m %H:%M}, "
                      f"fora por {formatar_duracao(inc['duracao_s'])}")

    return "\n".join(linhas)


def decidir_envio(modo, eventos, avisos_ssl, caidos, status, agora, resumo_hora):
    """Retorna (enviar, eh_resumo_diario)."""
    if modo == "completo":
        return True, False

    hoje = agora.astimezone(FUSO_BRASILIA).strftime("%Y-%m-%d")
    # aviso de SSL só conta como novidade uma vez por dia, para não repetir 6x/dia
    ssl_novo = bool(avisos_ssl) and status.get("ultimo_aviso_ssl") != hoje
    novidade = bool(eventos or caidos or ssl_novo)

    if modo == "diario":
        hora_brt = agora.astimezone(FUSO_BRASILIA).hour
        if status.get("ultimo_resumo") != hoje and hora_brt >= resumo_hora:
            return True, True
    return novidade, False


# --------------------------------------------------------------------- envio

def para_html_telegram(texto):
    """Escapa o texto e converte *negrito* em <b>negrito</b>."""
    escapado = html.escape(texto, quote=False)
    return re.sub(r"\*(.+?)\*", r"<b>\1</b>", escapado)


def enviar_telegram(texto):
    """Retorna True se enviou, False se falhou, None se não está configurado."""
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    dados = {"chat_id": chat_id, "text": para_html_telegram(texto), "parse_mode": "HTML",
             "disable_web_page_preview": True}
    resposta = requests.post(url, data=dados, timeout=30)
    if resposta.status_code == 400:
        # Algum caractere quebrou a formatação — reenvia como texto puro
        dados.update(text=texto)
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
    resposta = requests.post(url, json={"chatId": f"{numero_limpo}@c.us", "message": texto},
                             timeout=60)
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

    url = ("https://api.callmebot.com/whatsapp.php"
           f"?phone={urllib.parse.quote(fone)}"
           f"&apikey={urllib.parse.quote(apikey)}"
           f"&text={urllib.parse.quote(texto)}")
    resposta = requests.get(url, timeout=60)
    if resposta.status_code >= 400:
        print(f"ERRO ao enviar WhatsApp: HTTP {resposta.status_code}")
        print(resposta.text[:300])
        return False
    print("Mensagem enviada no WhatsApp com sucesso.")
    return True


def enviar_avisos(texto):
    """Dispara em todos os canais configurados. Retorna True se pelo menos um funcionou."""
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
        return False
    if not any(configurados.values()):
        print("ERRO: todos os canais configurados falharam ao enviar.")
        return False
    return True


# -------------------------------------------------------------------- execução

def main():
    sites = carregar_sites()
    if not sites:
        print("Nenhum site cadastrado no sites.txt — nada a fazer.")
        return

    modo = os.environ.get("MODO", "completo").strip().lower()
    resumo_hora = int(os.environ.get("RESUMO_HORA", "8"))
    status = carregar_status()
    agora = agora_utc()

    # esquece sites que saíram do sites.txt
    urls_atuais = {site["url"] for site in sites}
    status["sites"] = {url: reg for url, reg in status["sites"].items() if url in urls_atuais}

    print(f"Verificando {len(sites)} site(s)... (modo: {modo})\n")
    resultados, eventos, avisos_ssl = [], [], []
    for site in sites:
        resultado = verificar_site(site)
        evento = atualizar_status(status, site, resultado, agora)
        if evento:
            evento["nome"] = site["nome"]
            eventos.append(evento)

        dias_ssl = dias_para_vencer_ssl(site["url"])
        if dias_ssl is not None and dias_ssl <= SSL_AVISO_DIAS:
            avisos_ssl.append((site["nome"], dias_ssl))

        situacao = "ONLINE" if resultado["online"] else "FORA DO AR"
        extra_ssl = f" | SSL vence em {dias_ssl} dias" if dias_ssl is not None else ""
        print(f"  [{situacao}] {site['nome']} ({site['url']}) — {resultado['detalhe']}{extra_ssl}")
        resultados.append({**site, **resultado, "registro": status["sites"][site["url"]]})

    caidos = [r for r in resultados if not r["online"]]
    relatorio = montar_relatorio(resultados, eventos, avisos_ssl, agora)
    print("\n----- relatório -----\n" + relatorio + "\n---------------------\n")

    enviar, eh_resumo = decidir_envio(modo, eventos, avisos_ssl, caidos, status, agora, resumo_hora)
    enviado_ok = True
    if enviar:
        enviado_ok = enviar_avisos(relatorio)
        if enviado_ok:
            hoje = agora.astimezone(FUSO_BRASILIA).strftime("%Y-%m-%d")
            if eh_resumo:
                status["ultimo_resumo"] = hoje
            if avisos_ssl:
                status["ultimo_aviso_ssl"] = hoje
    else:
        print(f"Nada de novo — não vou mandar mensagem (MODO={modo}).")

    if enviado_ok:
        salvar_status(status)
    else:
        # Não grava o status: assim a próxima execução enxerga a mudança de novo e reavisa
        print("AVISO: envio falhou — status.json não foi atualizado, para reavisar na próxima.")

    # Sai com erro se algum site caiu ou o aviso falhou: o GitHub Actions fica com ❌
    # e ainda te manda um e-mail — um segundo canal de alerta, de graça.
    if caidos or not enviado_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
