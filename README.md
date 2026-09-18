# 🖥️ Monitor de Sites com aviso no celular

Verifica de tempos em tempos se seus sites estão no ar, guarda o histórico
(quando caiu, quanto tempo ficou fora, uptime), vigia o vencimento do SSL e
manda um relatório no seu celular — tudo rodando de graça no GitHub Actions,
sem precisar deixar o computador ligado.

## O que ele verifica

| Checagem | Como | O que pega |
| --- | --- | --- |
| **Site responde?** | HTTP `GET` com 2 tentativas e timeout de 15s | Servidor fora, DNS quebrado, erro 4xx/5xx, timeout |
| **Página é a certa?** | Procura um texto (a marca) no HTML | "Falsos 200": página de manutenção, domínio estacionado, erro do CMS |
| **SSL vai vencer?** | Lê a validade do certificado | Avisa 14 dias antes — certificado vencido derruba o site "sem cair" |
| **Está lento?** | Tempo de resposta > 5s ganha um 🐢 | Servidor sobrecarregado, problema chegando |
| **Caiu / voltou?** | Compara com a execução anterior (`status.json`) | Avisa a mudança e quanto tempo ficou fora |

Exemplo da mensagem que chega:

```
🖥️ Monitor de Sites — 18/09/2026 16:03 (Brasília)

🟢 VOLTOU: Toca do Aranha — ficou fora por 2h13min
⚠️ SSL de RB Run Club vence em 6 dia(s) (24/09) — renove!

✅ RB Run Club — 200, 487ms · uptime 100%
✅ Toca do Aranha — 200, 503ms · uptime 98,9%
✅ Conexão Freelance — 200, 230ms · uptime 100%

🟢 Tudo normal! 3 site(s) online.
🕓 Último incidente: Toca do Aranha, 18/09 13:50, fora por 2h13min
```

## Arquivos

| Arquivo | Para quê |
| --- | --- |
| `sites.txt` | **Sua lista de sites** — o único arquivo que você precisa editar |
| `monitor.py` | O script (Python + `requests`) |
| `.github/workflows/monitor.yml` | O agendamento no GitHub Actions |
| `status.json` | Histórico — **criado e atualizado pelo próprio robô**, não edite |
| `requirements.txt` | Dependências |

### Formato do `sites.txt`

```
Nome do site | https://endereco.com | texto que deve aparecer na página
```

O 3º campo é opcional, mas recomendado: use algo estável como o **nome da
marca**. Se a página responder 200 mas não tiver esse texto, conta como fora.
Linhas começando com `#` são ignoradas.

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
4. Copie do painel: **idInstance**, **apiTokenInstance** e a **apiUrl**.
5. Os secrets serão: `WHATSAPP_FONE` (seu número, ex: `+5514999999999`),
   `GREEN_API_INSTANCE`, `GREEN_API_TOKEN` e `GREEN_API_URL`.

> ⚠️ A Green API usa o protocolo do WhatsApp Web (não oficial). Para pouco
> volume, mandando só para você mesmo, funciona bem — mas evite usar seu número
> comercial principal se quiser risco zero.

**Opção C — WhatsApp via CallMeBot (quando reabrir cadastros):**

1. Adicione o número do bot aos contatos (veja o número atual em
   https://www.callmebot.com/blog/free-api-whatsapp-messages/).
2. Envie pelo WhatsApp: `I allow callmebot to send me messages`
3. Ele responde com a sua **API key** — são os secrets `WHATSAPP_FONE` e
   `CALLMEBOT_APIKEY`.

> Pode configurar mais de uma opção: o script envia por todos os canais cujos
> secrets existirem.

### Passo 2 — Criar o repositório no GitHub

1. Acesse https://github.com/new
2. Nome: `monitor-sites` (ou o que preferir)
3. Deixe **Public** (público): minutos de Actions ilimitados. Os secrets
   continuam criptografados e invisíveis mesmo com o repositório público.
   (Se preferir privado, são 2.000 min/mês grátis — a cada 4h gasta ~90.)
4. Clique em **Create repository**.

### Passo 3 — Subir os arquivos

**Opção A — pelo site (sem instalar nada):**

1. No repositório novo, clique em **uploading an existing file**
2. Arraste `monitor.py`, `sites.txt` e `requirements.txt` e confirme o commit.
3. O site **não deixa arrastar pastas ocultas**, então crie o workflow assim:
   `Add file > Create new file` → no nome digite
   `.github/workflows/monitor.yml` → cole o conteúdo do arquivo `monitor.yml`
   deste projeto → **Commit changes**.

**Opção B — pelo git:**

```bash
cd monitor-sites
git init -b main
git add .
git commit -m "Monitor de sites"
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

Edite o `sites.txt` (pode ser pelo lápis no próprio GitHub):

```
Spider Store | https://www.seusite.com.br | Spider Store
Portfólio | https://portfolio.seusite.com.br | Moretti Design
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

O agendamento no `monitor.yml` roda **a cada 4 horas**. Cada execução também
salva o `status.json` no repositório (é o commit "status: ..." do
`monitor-bot`) — é assim que ele lembra o que aconteceu na execução anterior.

---

## Escolher quando receber mensagem (`MODO`)

No `monitor.yml`, a variável `MODO` controla isso:

| `MODO`     | Você recebe                                                                 |
| ---------- | --------------------------------------------------------------------------- |
| `completo` | O relatório completo a **toda execução** (padrão — ~6 mensagens/dia)         |
| `diario`   | Só quando **algo muda** (caiu, voltou, SSL vencendo, site ainda fora) **+ 1 resumo por dia** a partir da `RESUMO_HORA` (padrão 8h) |
| `alertas`  | Só quando algo muda — silêncio total enquanto está tudo bem                  |

Recomendação: `diario`. Você sabe que o robô está vivo (1 resumo de manhã) e
só é incomodado quando importa.

## ⚠️ Por que este monitor NÃO serve como alarme urgente

O evento `schedule` do GitHub Actions é **"melhor esforço"**: a própria
documentação do GitHub avisa que agendamentos atrasam em períodos de carga.
Medido neste repositório com o cron de 4h: atrasos de 30 min a 2 horas, e
cerca de **metade dos horários simplesmente pulados**. Com cron de 15 min,
ficou mais de 1 hora sem disparar nenhuma vez.

Por isso a divisão de tarefas:

| Ferramenta | Papel | Frequência |
| ---------- | ----- | ---------- |
| **HetrixTools** (hetrixtools.com) | Alarme urgente — avisa no Telegram no minuto em que um site cai | 1 minuto |
| **Este repositório** | Relatório completo, histórico, uptime, SSL | ~4 horas |

O plano gratuito do HetrixTools inclui 15 monitores, checagem de 1 minuto e
notificação via Telegram (só exige login no painel a cada 90 dias).
Obs.: no UptimeRobot a integração com Telegram é **paga** (planos Solo/Team/
Enterprise), por isso não foi usado.

## Coisas boas de saber

- **O horário do cron é UTC** (Brasília = UTC−3). O relatório já converte
  para o horário de Brasília.
- **Repositório parado 60 dias:** o GitHub pausa agendamentos de repositórios
  sem commits há 60 dias. Como o robô commita o `status.json` a cada
  execução, isso **não acontece mais** com este projeto.
- **Quando um site cai, a execução fica ❌ de propósito** — assim o GitHub te
  manda um e-mail de "workflow failed", servindo como segundo alerta gratuito.
- **Se o envio falhar** (Telegram fora, token errado), o `status.json` não é
  atualizado — a próxima execução enxerga a mudança de novo e reavisa.
- **Rodar no seu PC para testar:**
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
| Meta WhatsApp Cloud API | Oficial | Setup complexo (app Business, token de sistema) e fora da janela de 24h só envia mensagens-template pré-aprovadas — ruim p/ relatórios |
| Twilio Sandbox | Confiável | Sandbox expira a cada 72h (precisa reativar sempre) |
| Bot caseiro (Baileys / whatsapp-web.js) | Controle total | Precisa de servidor ligado 24/7, protocolo não oficial (risco de banir o número) e quebra a cada atualização do WhatsApp |
