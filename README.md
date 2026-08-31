# 🖥️ Monitor de Sites com aviso no celular

Verifica de tempos em tempos se seus sites estão no ar e manda um relatório no
seu celular — tudo rodando de graça no GitHub Actions, sem precisar deixar o
computador ligado.

- ✅ **Python** + `requests` (código simples, fácil de mexer)
- ✅ **GitHub Actions** com agendamento (padrão: a cada 4 horas)
- ✅ Três canais de aviso — o script envia por **todos os que você configurar**
  nos secrets:
  - **Telegram** (recomendado — grátis, ilimitado, 5 min de setup)
  - **WhatsApp via Green API** (grátis — seu próprio número vira o "bot")
  - **WhatsApp via CallMeBot** (grátis, mas em ago/2026 está sem aceitar
    novos cadastros; quando reabrir, é só adicionar os secrets)

Exemplo da mensagem que chega:

```
🖥️ Monitor de Sites — 31/08/2026 14:00 (Brasília)

✅ Spider Store — online (200, 340ms)
🔴 API do Backend — FORA DO AR (HTTP 500)

⚠️ Atenção: 1 site(s) com problema!
```

---

## Passo a passo completo

### Passo 1 — Criar o canal de aviso

**Opção A — Telegram (recomendada, 5 minutos):**

1. No Telegram, procure por **@BotFather** (o oficial, com selo de verificado)
   e envie `/newbot`. Dê um nome (ex: `Monitor dos Meus Sites`) e um username
   terminando em `bot` (ex: `moretti_monitor_bot`).
2. O BotFather responde com o **token** do bot — algo como
   `7412345678:AAHxYz...`. **Guarde-o** (é o secret `TELEGRAM_TOKEN`).
3. Descubra o seu **chat ID**: procure por **@userinfobot**, aperte
   **Start** e ele responde com o seu `Id` (um número tipo `987654321`).
   **Guarde-o** (é o secret `TELEGRAM_CHAT_ID`).
4. **Importante:** abra o chat do bot que você acabou de criar e aperte
   **Start** nele também — sem isso, o Telegram não deixa o bot te enviar
   mensagens.

**Opção B — WhatsApp via Green API (~10 minutos):**

Aqui é o **seu próprio WhatsApp virando o "bot"**: você conecta seu número via
QR code (igual WhatsApp Web) e a Green API te dá uma API para enviar mensagens.
O plano gratuito (Developer) permite 1 número e poucas conversas — suficiente
para mandar avisos para você mesmo.

1. Crie uma conta gratuita em https://green-api.com (só e-mail).
2. No painel, crie uma **instância** no plano gratuito (Developer).
3. Abra a instância e escaneie o **QR code** com o WhatsApp do celular
   (WhatsApp → Configurações → **Dispositivos conectados** → Conectar).
4. Copie do painel: **idInstance** (ex: `7103123456`), **apiTokenInstance**
   (uma chave longa) e a **apiUrl** mostrada (ex: `https://7103.api.greenapi.com`).
5. Os secrets serão: `WHATSAPP_FONE` (seu número, ex: `+5514999999999`),
   `GREEN_API_INSTANCE`, `GREEN_API_TOKEN` e `GREEN_API_URL` (essa apiUrl).

> ⚠️ A Green API usa o protocolo do WhatsApp Web (não oficial). Para pouco
> volume, mandando só para você mesmo, funciona bem — mas evite usar seu número
> comercial principal se quiser risco zero. Se a instância desconectar um dia,
> é só escanear o QR de novo.

**Opção C — WhatsApp via CallMeBot (quando reabrir cadastros):**

1. Adicione o número do bot aos contatos (veja o número atual em
   https://www.callmebot.com/blog/free-api-whatsapp-messages/).
2. Envie pelo WhatsApp: `I allow callmebot to send me messages`
3. Ele responde com a sua **API key** (ex: `123456`) — são os secrets
   `WHATSAPP_FONE` (seu número) e `CALLMEBOT_APIKEY`.

> Pode configurar mais de uma opção: o script envia por todos os canais cujos
> secrets existirem.

### Passo 2 — Criar o repositório no GitHub

1. Acesse https://github.com/new
2. Nome: `monitor-sites` (ou o que preferir)
3. Pode marcar como **Private** (privado) — os 2.000 minutos/mês gratuitos de
   Actions são mais que suficientes (este monitor gasta ~90 min/mês).
   Se for **Public**, os minutos são ilimitados.
4. Clique em **Create repository**.

### Passo 3 — Subir os arquivos

**Opção A — pelo site (sem instalar nada):**

1. No repositório novo, clique em **uploading an existing file** (ou `Add file > Upload files`)
2. Arraste `monitor.py`, `sites.txt` e `requirements.txt` e confirme o commit.
3. O site **não deixa arrastar pastas ocultas**, então crie o workflow assim:
   `Add file > Create new file` → no nome digite
   `.github/workflows/monitor.yml` → cole o conteúdo do arquivo `monitor.yml`
   deste projeto → **Commit changes**.

**Opção B — pelo git (se já usa):**

```bash
cd monitor-sites
git init
git add .
git commit -m "Monitor de sites com aviso no WhatsApp"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/monitor-sites.git
git push -u origin main
```

### Passo 4 — Configurar os segredos (secrets)

No repositório, vá em:

**Settings → Secrets and variables → Actions → New repository secret**

Crie os secrets do canal que você escolheu no Passo 1 (nomes exatamente assim,
em maiúsculas):

| Nome                 | Valor                                               | Canal               |
| -------------------- | --------------------------------------------------- | ------------------- |
| `TELEGRAM_TOKEN`     | Token do BotFather, ex: `7412345678:AAHxYz...`      | Telegram            |
| `TELEGRAM_CHAT_ID`   | Seu ID do @userinfobot, ex: `987654321`             | Telegram            |
| `WHATSAPP_FONE`      | Seu número com código do país, ex: `+5514999999999` | Green API/CallMeBot |
| `GREEN_API_INSTANCE` | idInstance do painel, ex: `7103123456`              | Green API           |
| `GREEN_API_TOKEN`    | apiTokenInstance do painel                          | Green API           |
| `GREEN_API_URL`      | apiUrl do painel, ex: `https://7103.api.greenapi.com` | Green API         |
| `CALLMEBOT_APIKEY`   | A chave que o CallMeBot te mandou, ex: `123456`     | CallMeBot           |

> Secrets ficam criptografados — nem quem vê o repositório consegue lê-los.

### Passo 5 — Cadastrar os seus sites

Edite o arquivo `sites.txt` (pode editar direto no site do GitHub, no ícone de
lápis) e coloque seus sites reais, um por linha:

```
Spider Store | https://www.seusite.com.br
Portfólio | https://portfolio.seusite.com.br
```

### Passo 6 — Testar agora (sem esperar 4 horas)

1. Vá na aba **Actions** do repositório
2. Se aparecer um aviso pedindo para habilitar workflows, clique em habilitar
3. Clique no workflow **Monitor de Sites** (menu da esquerda)
4. Botão **Run workflow → Run workflow**
5. Em ~1 minuto a execução termina e a mensagem chega no seu celular 🎉

Se der erro, clique na execução vermelha e leia o log do passo
"Verificar sites e enviar avisos" — o script imprime o motivo.

### Passo 7 — Pronto! Roda sozinho

O agendamento já está configurado no `monitor.yml` para rodar **a cada 4 horas**.
Para mudar a frequência, edite a linha do `cron`:

| Frequência      | Linha no monitor.yml       |
| --------------- | -------------------------- |
| A cada 2 horas  | `- cron: "0 */2 * * *"`    |
| A cada 4 horas  | `- cron: "0 */4 * * *"`    |
| A cada 6 horas  | `- cron: "0 */6 * * *"`    |
| 1x por dia às 8h de Brasília | `- cron: "0 11 * * *"` (11 UTC = 8h BRT) |

---

## Ajustes opcionais

- **Receber mensagem só quando um site cair** (em vez do relatório sempre):
  no `monitor.yml`, troque `SO_ALERTAS: "false"` por `SO_ALERTAS: "true"`.
- **E-mail de reforço:** quando um site cai, o workflow termina com ❌ de
  propósito — o GitHub te manda um e-mail de "workflow failed", servindo como
  segundo alerta gratuito.

## Coisas boas de saber

- **O horário do cron é UTC** (Brasília = UTC−3) e o GitHub pode atrasar alguns
  minutos em horários de pico. Para monitoramento, isso não faz diferença.
- **Repositório parado 60 dias:** o GitHub pausa agendamentos de repositórios
  sem nenhum commit há 60 dias e te avisa por e-mail. Basta clicar para
  reativar — ou fazer qualquer commit (editar o `sites.txt`, por exemplo) que o
  prazo zera.
- **Limites do CallMeBot:** é gratuito para uso pessoal e aguenta tranquilo
  algumas mensagens por dia. Rodando a cada 4h são só 6 mensagens/dia.
- **Rodar no seu PC para testar (com Telegram):**
  ```bash
  pip install -r requirements.txt
  set TELEGRAM_TOKEN=7412345678:AAHxYz...
  set TELEGRAM_CHAT_ID=987654321
  python monitor.py
  ```

## Comparativo dos canais de aviso

| Opção | Prós | Contras |
| ----- | ---- | ------- |
| **Telegram Bot** (recomendada) | Grátis, ilimitado, super estável, oficial | Não é WhatsApp 🙂 |
| **Green API** (WhatsApp) | Grátis p/ uso pessoal, seu próprio número vira o bot | Não oficial (WhatsApp Web); QR pode pedir reconexão de vez em quando |
| **CallMeBot** (WhatsApp) | Grátis, 2 min de setup | Só manda p/ seu próprio número; às vezes lota e fecha cadastros |
| Meta WhatsApp Cloud API | Oficial ("fazer o bot" do jeito certo) | Setup complexo (app Business, token de sistema) e fora da janela de 24h só envia mensagens-template pré-aprovadas — ruim p/ relatórios |
| Twilio Sandbox | Confiável | Sandbox expira a cada 72h (precisa reativar sempre) |
| Bot caseiro (Baileys / whatsapp-web.js) | Controle total | Precisa de servidor ligado 24/7, protocolo não oficial (risco de banir o número) e quebra a cada atualização do WhatsApp |
