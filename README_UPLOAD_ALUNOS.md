# Upload em Massa de Alunos

Esta funcionalidade permite fazer upload em massa de alunos através de um arquivo CSV ou Excel.

## Endpoint

```
POST /users/bulk-upload-students
```

## Formato do Arquivo

O arquivo deve conter as seguintes colunas obrigatórias:

- **nome**: Nome completo do aluno
- **email**: Email único do aluno
- **data_nascimento**: Data de nascimento (formato: DD/MM/AAAA, DD-MM-AAAA, AAAA-MM-DD)
- **matricula**: Matrícula do aluno (opcional, mas deve ser única se fornecida)
- **escola**: Nome da escola
- **endereco_escola**: Endereço completo da escola
- **estado_escola**: Sigla do estado da escola (ex: SP, RJ, MG)
- **municipio_escola**: Nome do município da escola
- **serie**: Série/ano escolar
- **turma**: Nome da turma

## Funcionalidades

- **Criação Automática de Escolas**: Se a escola não existir no sistema, ela será criada automaticamente com base nos dados fornecidos
- **Criação Automática de Cidades**: Se a cidade não existir, ela será criada automaticamente
- **Validação de Dados**: Verifica se todos os campos obrigatórios estão preenchidos
- **Verificação de Duplicatas**: Evita emails e matrículas duplicadas
- **Relatório Detalhado**: Retorna um relatório completo com sucessos e erros

## Permissões

- **Admin**: Pode criar alunos em qualquer escola
- **Tecadm**: Pode criar alunos em escolas da sua cidade
- **Diretor/Coordenador**: Pode criar alunos apenas na sua escola

## Exemplo de Uso

### Arquivo CSV de Exemplo

```csv
nome,email,data_nascimento,matricula,escola,endereco_escola,estado_escola,municipio_escola,serie,turma
João Silva,joao.silva@email.com,15/03/2008,2024001,Escola Municipal A,Rua das Flores 123,SP,São Paulo,6º Ano,Turma A
Maria Santos,maria.santos@email.com,22/07/2008,2024002,Escola Municipal A,Rua das Flores 123,SP,São Paulo,6º Ano,Turma A
```

### Requisição

```bash
curl -X POST \
  http://localhost:5000/users/bulk-upload-students \
  -H 'Authorization: Bearer <seu_token>' \
  -F 'file=@alunos.csv'
```

## Resposta

```json
{
  "mensagem": "Upload concluído! 2 alunos criados com sucesso.",
  "resumo": {
    "total_linhas": 2,
    "sucessos": 2,
    "erros": 0
  },
  "alunos_criados": [
    {
      "nome": "João Silva",
      "email": "joao.silva@email.com",
      "matricula": "2024001",
      "escola": "Escola Municipal A",
      "serie": "6º Ano",
      "turma": "Turma A"
    }
  ],
  "erros": []
}
```

## Observações Importantes

1. **Escolas são criadas automaticamente** se não existirem no sistema
2. **Cidades são criadas automaticamente** se não existirem no sistema
3. **Séries e turmas devem existir** no sistema antes do upload
4. **Senhas são geradas automaticamente** para cada aluno (serão enviadas por email)
5. **Todos os campos obrigatórios** devem estar preenchidos
6. **Emails e matrículas** devem ser únicos no sistema
