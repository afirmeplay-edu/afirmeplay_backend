# Rotas de Atalhos do Usuário (User Quick Links)

Este documento descreve as rotas disponíveis para gerenciar os atalhos personalizados do menu de cada usuário.

## Base URL
```
/user-quick-links
```

## Autenticação
Todas as rotas requerem autenticação JWT. Inclua o token no header:
```
Authorization: Bearer <seu_token_jwt>
```

## Rotas Disponíveis

### 1. Buscar Atalhos do Usuário
**GET** `/user-quick-links/<user_id>`

Busca os atalhos personalizados de um usuário específico.

**Resposta de Sucesso (200):**
```json
{
  "id": "uuid-do-registro",
  "user_id": "uuid-do-usuario",
  "quickLinks": [
    {
      "href": "/app/avaliacoes",
      "icon": "List",
      "label": "Avaliações"
    },
    {
      "href": "/app/estudantes",
      "icon": "Users",
      "label": "Estudantes"
    }
  ],
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00"
}
```

**Resposta quando não há atalhos (200):**
```json
{
  "quickLinks": []
}
```

### 2. Criar/Atualizar Atalhos do Usuário
**POST** `/user-quick-links/<user_id>`

Cria novos atalhos ou atualiza atalhos existentes para um usuário.

**Body da Requisição:**
```json
{
  "quickLinks": [
    {
      "href": "/app/avaliacoes",
      "icon": "List",
      "label": "Avaliações"
    },
    {
      "href": "/app/estudantes",
      "icon": "Users",
      "label": "Estudantes"
    }
  ]
}
```

**Resposta de Sucesso - Criação (201):**
```json
{
  "mensagem": "Atalhos criados com sucesso!",
  "id": "uuid-do-registro",
  "user_id": "uuid-do-usuario",
  "quickLinks": [...],
  "created_at": "2024-01-01T10:00:00"
}
```

**Resposta de Sucesso - Atualização (200):**
```json
{
  "mensagem": "Atalhos atualizados com sucesso!",
  "id": "uuid-do-registro",
  "user_id": "uuid-do-usuario",
  "quickLinks": [...],
  "updated_at": "2024-01-01T10:00:00"
}
```

### 3. Deletar Atalhos do Usuário
**DELETE** `/user-quick-links/<user_id>`

Remove todos os atalhos personalizados de um usuário.

**Resposta de Sucesso (200):**
```json
{
  "mensagem": "Atalhos deletados com sucesso!"
}
```

## Códigos de Erro

- **400**: Dados inválidos (campo 'quickLinks' obrigatório)
- **403**: Não autorizado (usuário tentando acessar atalhos de outro usuário)
- **404**: Usuário ou atalhos não encontrados
- **500**: Erro interno do servidor

## Segurança

- Cada usuário só pode acessar e modificar seus próprios atalhos
- A autenticação é obrigatória em todas as rotas
- Validação de dados é feita no servidor

## Exemplo de Uso

```javascript
// Buscar atalhos do usuário
const response = await fetch('/user-quick-links/meu-user-id', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
});

// Salvar atalhos
const response = await fetch('/user-quick-links/meu-user-id', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    quickLinks: [
      {
        href: "/app/avaliacoes",
        icon: "List",
        label: "Avaliações"
      }
    ]
  })
});
``` 