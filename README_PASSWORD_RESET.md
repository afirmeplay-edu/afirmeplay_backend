# Funcionalidade de Redefinição de Senha - InnovaPlay

Este documento explica a funcionalidade de redefinição de senha implementada com SendGrid.

## 📋 Funcionalidades

- ✅ Solicitação de reset de senha por email
- ✅ Tokens seguros e temporários (1 hora)
- ✅ Templates de email responsivos
- ✅ Validação de tokens
- ✅ Alteração de senha para usuários logados
- ✅ Emails de confirmação

## 🚀 Rotas Disponíveis

### 1. Solicitar Redefinição de Senha
```http
POST /users/forgot-password
Content-Type: application/json

{
  "email": "usuario@exemplo.com"
}
```

### 2. Validar Token de Reset
```http
POST /users/validate-reset-token
Content-Type: application/json

{
  "token": "token_gerado_anteriormente"
}
```

### 3. Redefinir Senha
```http
POST /users/reset-password
Content-Type: application/json

{
  "token": "token_gerado_anteriormente",
  "new_password": "nova_senha123"
}
```

### 4. Alterar Senha (Usuário Logado)
```http
POST /users/change-password
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "current_password": "senha_atual",
  "new_password": "nova_senha123"
}
```

## 🔄 Fluxo de Funcionamento

1. **Solicitação**: Usuário informa email → Sistema gera token único → Envia email com link
2. **Validação**: Frontend valida token antes de mostrar formulário de nova senha
3. **Redefinição**: Usuário define nova senha → Sistema atualiza banco → Envia email de confirmação
4. **Limpeza**: Token é invalidado após uso ou expiração

## 🔒 Segurança

- Tokens têm validade de 1 hora
- Tokens são únicos e usados apenas uma vez
- Senhas são criptografadas com bcrypt
- Não revela se email existe ou não na base
- Validação de força da senha (mínimo 6 caracteres)

## 📧 Templates de Email

Os emails são enviados com templates HTML responsivos que incluem:

- **Email de Reset**: Link para redefinição com token único
- **Email de Confirmação**: Confirmação de alteração de senha

## 🛠️ Manutenção

### Limpeza de Tokens Expirados

Para limpar tokens expirados periodicamente, execute:

```sql
DELETE FROM users 
WHERE reset_token_expires < NOW() 
AND reset_token IS NOT NULL;
```

### Monitoramento

Verifique os logs para:
- Emails enviados com sucesso
- Erros de envio de email
- Tentativas de reset de senha

## 🐛 Troubleshooting

### Erro: "SendGrid API key não configurada"
- Verifique se `SENDGRID_API_KEY` está definida no `.env`
- Confirme se a API key é válida no painel SendGrid

### Erro: "Erro ao enviar email"
- Verifique se o email remetente está verificado no SendGrid
- Confirme se não excedeu o limite de emails gratuitos
- Verifique os logs para detalhes do erro

### Token não funciona
- Verifique se o token não expirou (1 hora)
- Confirme se o token não foi usado anteriormente
- Verifique se o token está correto no banco de dados

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs da aplicação
2. Confirme as configurações de ambiente
3. Teste com um email válido cadastrado no sistema 