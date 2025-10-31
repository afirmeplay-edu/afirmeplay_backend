# Configuração de Alertas via Telegram

Este documento explica como configurar os alertas via Telegram para monitoramento de erros do backend.

## 📋 Pré-requisitos

1. Ter uma conta no Telegram
2. Criar um Bot do Telegram
3. Obter o ID do grupo/canal onde os alertas serão enviados

## 🤖 Passo 1: Criar um Bot no Telegram

1. Abra o Telegram e procure por `@BotFather`
2. Inicie uma conversa e envie o comando `/newbot`
3. Siga as instruções para:
    - Definir um nome para o bot (ex: "InnovaPlay Alert Bot")
    - Definir um username para o bot (deve terminar com "bot", ex: "innovaplay_alert_bot")
4. **Guarde o token** fornecido pelo BotFather (algo como: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## 👥 Passo 2: Criar um Grupo e Adicionar o Bot

1. Crie um grupo no Telegram (ou use um existente)
2. Adicione o bot que você criou ao grupo
3. Dê permissão de administrador ao bot (opcional, mas recomendado)

## 🔍 Passo 3: Obter o ID do Grupo

Existem várias formas de obter o ID do grupo:

### Método 1: Usar um bot auxiliar

1. Adicione `@userinfobot` ao grupo
2. O bot mostrará o ID do grupo na mensagem

### Método 2: Usar a API do Telegram diretamente

1. Envie uma mensagem no grupo
2. Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
3. Procure por `"chat":{"id":-123456789}` - o número negativo é o ID do grupo

### Método 3: Converter para Supergrupo

1. Transforme o grupo em supergrupo (configurações do grupo)
2. O ID do supergrupo aparece na URL: `https://web.telegram.org/k/#-123456789`

**Nota:** IDs de grupos começam com `-` (são negativos)

## ⚙️ Passo 4: Configurar Variáveis de Ambiente

Adicione as seguintes variáveis ao arquivo `.env` (localizado em `app/.env`):

```env
# Telegram Alert Configuration
TELEGRAM_BOT_TOKEN=seu_token_do_botfather_aqui
TELEGRAM_GROUP_ID=-123456789
TELEGRAM_ALERT_ENABLED=true
```

### Explicação das variáveis:

-   **TELEGRAM_BOT_TOKEN**: Token fornecido pelo BotFather ao criar o bot
-   **TELEGRAM_GROUP_ID**: ID do grupo onde os alertas serão enviados (começa com `-` para grupos)
-   **TELEGRAM_ALERT_ENABLED**: `true` para habilitar alertas, `false` para desabilitar (útil para desenvolvimento)

## 🧪 Passo 5: Testar a Configuração

1. Reinicie o servidor Flask após adicionar as variáveis de ambiente
2. Gere um erro intencional (por exemplo, acesse uma rota que não existe)
3. Verifique se a mensagem aparece no grupo do Telegram

## 📨 Formato dos Alertas

Os alertas enviados incluem:

-   🚨 Emoji de alerta
-   ⏰ Timestamp do erro
-   📍 Rota e método HTTP onde ocorreu o erro
-   👤 ID e email do usuário (se autenticado)
-   ❌ Mensagem de erro
-   📋 Stack trace completo (truncado se muito longo)
-   ℹ️ Informações adicionais (URL, IP, User-Agent, Body JSON)

## 🔒 Segurança

-   **NÃO** compartilhe o token do bot publicamente
-   **NÃO** faça commit do arquivo `.env` no Git
-   O `.env` já deve estar no `.gitignore`

## ⚠️ Troubleshooting

### Alertas não estão sendo enviados

1. Verifique se `TELEGRAM_ALERT_ENABLED=true` no `.env`
2. Verifique se o token do bot está correto
3. Verifique se o ID do grupo está correto (deve começar com `-`)
4. Verifique se o bot foi adicionado ao grupo
5. Verifique os logs do servidor para erros relacionados ao Telegram

### Erro: "chat not found"

-   Certifique-se de que o bot está no grupo
-   Certifique-se de que o ID do grupo está correto
-   Para grupos privados, o bot precisa ter sido adicionado manualmente

### Rate Limiting

Os alertas têm um sistema de rate limiting embutido:

-   Máximo de 1 alerta por minuto por rota
-   Isso evita spam em caso de erros repetidos

## 📝 Exemplo de Mensagem de Alerta

```
🚨 *ALERTA DE ERRO - Backend*

*⏰ Timestamp:* 2025-01-15 14:30:45

*📍 Rota:* `DELETE /classes/abc123`

*👤 Usuário:* `admin@example.com`

*❌ Erro:*
```

IntegrityError: foreign key constraint failed

```

*📋 Stack Trace:*
```

Traceback (most recent call last):
File "...", line 123, in delete_class
db.session.commit()
...

```

*ℹ️ Informações Adicionais:*
• *URL Completa:* `http://localhost:5000/classes/abc123`
• *IP:* `192.168.1.100`
• *User-Agent:* `Mozilla/5.0...`
```

## 🔧 Desabilitar Alertas Temporariamente

Para desabilitar alertas sem remover a configuração:

```env
TELEGRAM_ALERT_ENABLED=false
```

Os erros ainda serão logados em `logs/app.log`, mas não serão enviados para o Telegram.
