# Jogos Educativos - Wordwall

Este módulo permite gerenciar jogos educativos do Wordwall no sistema InnovaPlay.

## Model Game

A model `Game` armazena informações sobre jogos educativos com os seguintes campos:

- **id**: Identificador único (UUID)
- **url**: URL do jogo no Wordwall (obrigatório)
- **title**: Título do jogo (obrigatório)
- **iframeHtml**: HTML do embed do jogo (obrigatório)
- **thumbnail**: URL da thumbnail do jogo (opcional)
- **author**: Nome do autor do jogo no Wordwall (opcional)
- **provider**: Provedor do jogo (fixo: 'wordwall')
- **subject**: Disciplina do jogo (obrigatório)
- **userId**: ID do usuário que criou o jogo (obrigatório)
- **createdAt**: Data/hora de criação
- **updatedAt**: Data/hora de atualização

## Rotas Disponíveis

### POST /games
Cria um novo jogo educativo.

**Autenticação**: JWT Token obrigatório
**Permissões**: admin, professor, coordenador, diretor, tecadm

**Body**:
```json
{
  "url": "https://wordwall.net/pt/resource/94433702/roleta",
  "title": "Roleta",
  "iframeHtml": "<iframe src='https://wordwall.net/pt/embed/94433702' width='500' height='380'></iframe>",
  "thumbnail": "https://example.com/thumbnail.jpg",
  "author": "Nome do Autor",
  "subject": "Matemática"
}
```

**Resposta**:
```json
{
  "mensagem": "Jogo criado com sucesso!",
  "jogo": {
    "id": "uuid-do-jogo",
    "url": "https://wordwall.net/pt/resource/94433702/roleta",
    "title": "Roleta",
    "iframeHtml": "<iframe...>",
    "thumbnail": "https://example.com/thumbnail.jpg",
    "author": "Nome do Autor",
    "provider": "wordwall",
    "subject": "Matemática",
    "userId": "uuid-do-usuario",
    "createdAt": "2024-01-01T10:00:00",
    "updatedAt": "2024-01-01T10:00:00"
  }
}
```

### GET /games
Lista todos os jogos cadastrados.

**Autenticação**: JWT Token obrigatório
**Permissões**: admin, professor, coordenador, diretor, tecadm, aluno

**Resposta**:
```json
{
  "jogos": [
    {
      "id": "uuid-do-jogo",
      "url": "https://wordwall.net/pt/resource/94433702/roleta",
      "title": "Roleta",
      "iframeHtml": "<iframe...>",
      "thumbnail": "https://example.com/thumbnail.jpg",
      "author": "Nome do Autor",
      "provider": "wordwall",
      "subject": "Matemática",
      "userId": "uuid-do-usuario",
      "createdAt": "2024-01-01T10:00:00",
      "updatedAt": "2024-01-01T10:00:00"
    }
  ]
}
```

### GET /games/:id
Retorna os dados de um jogo específico.

**Autenticação**: JWT Token obrigatório
**Permissões**: admin, professor, coordenador, diretor, tecadm, aluno

**Resposta**:
```json
{
  "id": "uuid-do-jogo",
  "url": "https://wordwall.net/pt/resource/94433702/roleta",
  "title": "Roleta",
  "iframeHtml": "<iframe...>",
  "thumbnail": "https://example.com/thumbnail.jpg",
  "author": "Nome do Autor",
  "provider": "wordwall",
  "subject": "Matemática",
  "userId": "uuid-do-usuario",
  "createdAt": "2024-01-01T10:00:00",
  "updatedAt": "2024-01-01T10:00:00"
}
```

### PUT /games/:id
Atualiza os dados de um jogo.

**Autenticação**: JWT Token obrigatório
**Permissões**: admin, professor, coordenador, diretor, tecadm (apenas criador ou admin)

**Body** (campos opcionais):
```json
{
  "url": "https://wordwall.net/pt/resource/94433702/roleta-nova",
  "title": "Roleta Atualizada",
  "iframeHtml": "<iframe src='https://wordwall.net/pt/embed/94433702' width='600' height='480'></iframe>",
  "thumbnail": "https://example.com/new-thumbnail.jpg",
  "author": "Novo Autor",
  "subject": "Português"
}
```

### DELETE /games/:id
Remove um jogo.

**Autenticação**: JWT Token obrigatório
**Permissões**: admin, professor, coordenador, diretor, tecadm (apenas criador ou admin)

**Resposta**:
```json
{
  "mensagem": "Jogo excluído com sucesso!"
}
```

## Validações

### Disciplinas Válidas
O campo `subject` deve corresponder a uma disciplina existente no sistema. As disciplinas válidas são obtidas através da rota `/subjects`.

### Permissões
- **Criação**: Apenas usuários autenticados com roles apropriados
- **Edição/Exclusão**: Apenas o criador do jogo ou administradores
- **Visualização**: Todos os usuários autenticados

### Campo Provider
O campo `provider` é automaticamente definido como "wordwall" e não pode ser alterado.

### Campo UserId
O campo `userId` é automaticamente preenchido com o ID do usuário autenticado.

## Migração

Para criar a tabela `games` no banco de dados, execute:

```bash
python apply_games_migration.py
```

Ou execute diretamente o SQL:

```sql
-- Ver arquivo migration_create_games_table.sql
```

## Exemplo de Uso

### Criar um jogo
```bash
curl -X POST http://localhost:5000/games \
  -H "Authorization: Bearer SEU_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://wordwall.net/pt/resource/94433702/roleta",
    "title": "Roleta de Matemática",
    "iframeHtml": "<iframe src=\"https://wordwall.net/pt/embed/94433702\" width=\"500\" height=\"380\"></iframe>",
    "thumbnail": "https://example.com/thumbnail.jpg",
    "author": "Professor Silva",
    "subject": "Matemática"
  }'
```

### Listar jogos
```bash
curl -X GET http://localhost:5000/games \
  -H "Authorization: Bearer SEU_JWT_TOKEN"
```

### Buscar jogo específico
```bash
curl -X GET http://localhost:5000/games/UUID_DO_JOGO \
  -H "Authorization: Bearer SEU_JWT_TOKEN"
```

### Atualizar jogo
```bash
curl -X PUT http://localhost:5000/games/UUID_DO_JOGO \
  -H "Authorization: Bearer SEU_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Roleta Atualizada",
    "subject": "Português"
  }'
```

### Excluir jogo
```bash
curl -X DELETE http://localhost:5000/games/UUID_DO_JOGO \
  -H "Authorization: Bearer SEU_JWT_TOKEN"
``` 