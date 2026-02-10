# 🐳 Docker Compose - InnovaPlay Backend

Este arquivo contém a configuração completa do Docker Compose para rodar o projeto localmente.

## 📋 Serviços Incluídos

1. **PostgreSQL** - Banco de dados principal
2. **Redis** - Broker e backend para Celery, além de cache
3. **MinIO** - Object storage (S3-compatible)
4. **API Flask** - Aplicação principal
5. **Celery Worker** - Processamento assíncrono de tarefas
6. **MinIO Init** - Script de inicialização dos buckets do MinIO

## 🚀 Como Usar

### 1. Configurar Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` e configure as variáveis:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações, especialmente:
- `JWT_SECRET_KEY` - Use uma chave segura em produção
- `REDIS_PASSWORD` - Senha do Redis
- `MINIO_ROOT_USER` e `MINIO_ROOT_PASSWORD` - Credenciais do MinIO
- `SENDGRID_API_KEY` - Se usar envio de emails
- `TELEGRAM_BOT_TOKEN` - Se usar alertas do Telegram

### 2. Iniciar os Serviços

```bash
docker-compose up -d
```

Isso irá:
- Construir a imagem da API (se necessário)
- Iniciar todos os serviços
- Criar a rede `local`
- Criar volumes para persistência de dados
- Executar o script de inicialização do MinIO

### 3. Verificar Logs

```bash
# Todos os serviços
docker-compose logs -f

# Serviço específico
docker-compose logs -f api
docker-compose logs -f celery
docker-compose logs -f postgres
```

### 4. Parar os Serviços

```bash
docker-compose down
```

Para remover também os volumes (⚠️ apaga dados):

```bash
docker-compose down -v
```

## 🔧 Configurações

### Portas Expostas

- **API**: `http://localhost:5000`
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **MinIO API**: `http://localhost:9000`
- **MinIO Console**: `http://localhost:9001`

### Credenciais Padrão

#### PostgreSQL
- User: `postgres_user`
- Password: `postgres_password`
- Database: `postgres_db`

#### Redis
- Password: `redis_password` (configurável via `.env`)

#### MinIO
- Root User: `minioadmin` (configurável via `.env`)
- Root Password: `minioadmin123` (configurável via `.env`)
- Console: `http://localhost:9001`

### Volumes

Os seguintes volumes são criados para persistência:
- `postgres_data` - Dados do PostgreSQL
- `redis_data` - Dados do Redis
- `minio_data` - Arquivos do MinIO

## 📦 Buckets do MinIO

O script de inicialização cria automaticamente os seguintes buckets:

- `answer-sheets` - Cartões de resposta (download público)
- `physical-tests` - Provas físicas (download público)
- `municipality-logos` - Logos de municípios (público)
- `school-logos` - Logos de escolas (público)
- `question-images` - Imagens de questões
- `user-uploads` - Uploads de usuários

## 🔍 Troubleshooting

### API não conecta ao banco

Verifique se o PostgreSQL está saudável:
```bash
docker-compose ps
docker-compose logs postgres
```

### Celery não processa tarefas

Verifique se o Redis está rodando e acessível:
```bash
docker-compose logs redis
docker-compose exec redis redis-cli -a redis_password ping
```

### MinIO buckets não foram criados

O container `minio-init` executa apenas uma vez. Para recriar os buckets:

```bash
docker-compose run --rm minio-init
```

Ou manualmente via console do MinIO em `http://localhost:9001`

### Rebuild da imagem

Se você alterou o Dockerfile ou requirements.txt:

```bash
docker-compose build --no-cache api celery
docker-compose up -d
```

## 🔄 Comandos Úteis

```bash
# Reiniciar um serviço específico
docker-compose restart api

# Ver status dos serviços
docker-compose ps

# Executar comandos dentro de um container
docker-compose exec api bash
docker-compose exec postgres psql -U postgres_user -d postgres_db

# Ver uso de recursos
docker stats

# Limpar tudo (containers, volumes, networks)
docker-compose down -v
docker system prune -a
```

## 📝 Notas

- A API usa Gunicorn com 4 workers por padrão
- O Celery Worker usa 4 processos de concorrência
- Todos os serviços estão na mesma rede Docker (`local`)
- O MinIO init executa apenas uma vez (restart: "no")
- Os volumes persistem dados mesmo após `docker-compose down`
