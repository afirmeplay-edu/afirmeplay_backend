# ✅ **CHECKLIST: Implementação MinIO Storage**

## 📋 **Status da Implementação**

### **✅ 1. INFRAESTRUTURA**

#### **GitLab CI (.gitlab-ci.yml)**
- [x] Adicionado stage `mock_storage`
- [x] Criado job `minio_setup` que:
  - [x] Cria container MinIO
  - [x] Aguarda health check
  - [x] Cria 6 buckets automáticos
  - [x] Define políticas de acesso
- [x] Variáveis MinIO adicionadas ao `image_build`

#### **Variáveis de Ambiente (GitLab CI/CD > Settings > Variables)**

**⚠️ IMPORTANTE: Configure estas variáveis no GitLab antes do deploy!**

```bash
# Copie e cole no GitLab CI/CD Variables:

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=SenhaSuperForte123!
MINIO_ENDPOINT=minio-server:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=SenhaSuperForte123!
MINIO_SECURE=false

# Opcional (se usar proxy/nginx):
# MINIO_ENDPOINT_PUBLIC=https://storage.seudominio.com
```

---

### **✅ 2. BACKEND**

#### **Serviço MinIO**
- [x] `app/services/storage/__init__.py` - Package init
- [x] `app/services/storage/minio_service.py` - Serviço completo:
  - [x] Upload genérico de arquivos
  - [x] URLs pré-assinadas (1 hora)
  - [x] Download de arquivos
  - [x] Métodos específicos:
    - [x] `upload_answer_sheet_zip()`
    - [x] `upload_physical_test_zip()`
    - [x] `upload_municipality_logo()`
    - [x] `upload_school_logo()`
    - [x] `upload_question_image()`

#### **Dependências**
- [x] `requirements.txt` - Adicionado `minio==7.2.3`

#### **Banco de Dados**
- [x] `migrations/versions/add_minio_storage_fields.py` - Migração criada:
  - [x] `AnswerSheetGabarito`: 4 novos campos
  - [x] `PhysicalTestForm`: 3 novos campos

**⚠️ AÇÃO NECESSÁRIA:**
```bash
# Atualizar down_revision na migração:
# Edite: migrations/versions/add_minio_storage_fields.py
# Linha 16: down_revision = None
# Substitua por: down_revision = 'ID_DA_ULTIMA_MIGRACAO'
```

#### **Tasks Celery**
- [x] `app/services/celery_tasks/answer_sheet_tasks.py`:
  - [x] Cria ZIP temporário
  - [x] Upload para MinIO
  - [x] Atualiza gabarito com URL
  - [x] Limpa arquivos temporários
  - [x] Retorna `minio_url` e `download_size_bytes`

- [x] `app/services/celery_tasks/physical_test_tasks.py`:
  - [x] Busca PDFs do banco
  - [x] Cria ZIP temporário
  - [x] Upload para MinIO
  - [x] Atualiza gabarito com URL
  - [x] Limpa arquivos temporários
  - [x] Retorna `minio_url` e `download_size_bytes`

#### **Rotas da API**
- [x] `app/routes/answer_sheet_routes.py`:
  - [x] `GET /gabarito/<id>/download` - Retorna URL pré-assinada
  - [x] Valida se ZIP foi gerado
  - [x] Retorna metadados completos

- [x] `app/routes/physical_test_routes.py`:
  - [x] `GET /test/<id>/download-all` - Retorna URL pré-assinada
  - [x] Valida se ZIP foi gerado
  - [x] Retorna metadados completos

---

### **✅ 3. DOCUMENTAÇÃO**

- [x] `GUIA_MINIO_STORAGE.md` - Guia completo:
  - [x] Arquitetura
  - [x] Estrutura de buckets
  - [x] Fluxos (diagramas)
  - [x] Endpoints da API
  - [x] Exemplos frontend (React/Vue)
  - [x] Variáveis de ambiente
  - [x] Troubleshooting
  - [x] Exemplos de uso futuro

- [x] `IMPLEMENTACAO_MINIO_CHECKLIST.md` - Este arquivo

---

## 🚀 **PASSOS PARA DEPLOY**

### **1. Configurar GitLab CI/CD Variables**

Vá em: **Settings > CI/CD > Variables** e adicione:

| Key | Value | Protected | Masked |
|-----|-------|-----------|--------|
| `MINIO_ROOT_USER` | `minioadmin` | ✅ | ✅ |
| `MINIO_ROOT_PASSWORD` | `SenhaSuperForte123!` | ✅ | ✅ |
| `MINIO_ENDPOINT` | `minio-server:9000` | ❌ | ❌ |
| `MINIO_ACCESS_KEY` | `minioadmin` | ✅ | ✅ |
| `MINIO_SECRET_KEY` | `SenhaSuperForte123!` | ✅ | ✅ |
| `MINIO_SECURE` | `false` | ❌ | ❌ |

### **2. Atualizar Down Revision da Migração**

```bash
# Localmente, descubra a última migração:
flask db heads

# Edite o arquivo:
# migrations/versions/add_minio_storage_fields.py

# Linha 16:
down_revision = 'COLE_O_ID_AQUI'  # Ex: '79caf408ad15'
```

### **3. Commit e Push**

```bash
git add .
git commit -m "feat: implementar MinIO storage para PDFs e arquivos"
git push origin artur
```

### **4. Aguardar Pipeline**

O pipeline vai:
1. ✅ Validar
2. ✅ Build da imagem
3. ✅ Criar network
4. ✅ **[NOVO] Criar MinIO container e buckets**
5. ✅ Deploy da API
6. ✅ Deploy do Celery Worker

### **5. Executar Migração**

```bash
# SSH no servidor:
ssh usuario@seu-servidor

# Entrar no container:
docker exec -it innovplay_api bash

# Executar migração:
flask db upgrade

# Verificar:
flask db current
```

### **6. Testar MinIO**

```bash
# Verificar se container está rodando:
docker ps | grep minio

# Acessar console web:
# http://seu-servidor:9001
# User: minioadmin
# Pass: SenhaSuperForte123!

# Verificar buckets:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc ls myminio"
```

### **7. Testar Geração e Download**

```bash
# 1. Gerar cartões (via frontend ou Postman)
POST /answer-sheets/generate
# Aguardar task completar (polling)

# 2. Solicitar download
GET /answer-sheets/gabarito/{id}/download
# Deve retornar URL pré-assinada

# 3. Testar download
# Abrir URL no navegador
```

---

## 🔍 **Troubleshooting**

### **Problema: MinIO não inicia**

```bash
# Logs:
docker logs minio-server

# Possíveis causas:
# - Porta 9000/9001 já em uso
# - Permissões do volume
# - Variáveis não configuradas
```

**Solução:**
```bash
# Parar container conflitante:
docker stop $(docker ps -q --filter "publish=9000")

# Remover e recriar:
docker rm minio-server
# Re-executar job minio_setup no GitLab
```

### **Problema: Buckets não criados**

```bash
# Verificar buckets manualmente:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc mb myminio/answer-sheets --ignore-existing"
```

### **Problema: Upload falha nas tasks**

```bash
# Verificar logs do Celery:
docker logs innovplay_api-celery

# Erros comuns:
# - MinIO não acessível: verificar network
# - Credenciais erradas: verificar .env
# - Bucket não existe: criar manualmente
```

### **Problema: URL pré-assinada não funciona**

```bash
# Verificar se arquivo existe:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc ls myminio/answer-sheets/gabaritos/{gabarito_id}/"

# Verificar se URL não expirou (1 hora)
# Solicitar nova URL
```

---

## 📊 **Monitoramento**

### **Uso de Espaço**

```bash
# Total usado:
docker exec minio-server du -sh /data

# Por bucket:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc du myminio/answer-sheets"
```

### **Arquivos no Bucket**

```bash
# Listar cartões:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc ls -r myminio/answer-sheets"

# Listar provas:
docker run --rm --network prod \
  minio/mc:latest \
  sh -c "mc alias set myminio http://minio-server:9000 minioadmin SenhaSuperForte123! && mc ls -r myminio/physical-tests"
```

---

## 🎯 **Próximos Passos (Futuro)**

- [ ] Lifecycle policies (auto-delete após 30 dias)
- [ ] Replicação para backup
- [ ] CDN na frente do MinIO (CloudFlare)
- [ ] Compressão de PDFs antes do upload
- [ ] Upload de logos de municípios/escolas
- [ ] Upload de imagens de questões

---

## 📚 **Arquivos Modificados**

### **Novos:**
```
app/services/storage/__init__.py
app/services/storage/minio_service.py
migrations/versions/add_minio_storage_fields.py
GUIA_MINIO_STORAGE.md
IMPLEMENTACAO_MINIO_CHECKLIST.md
```

### **Modificados:**
```
.gitlab-ci.yml
requirements.txt
app/services/celery_tasks/answer_sheet_tasks.py
app/services/celery_tasks/physical_test_tasks.py
app/routes/answer_sheet_routes.py
app/routes/physical_test_routes.py
```

---

## ✅ **Checklist Final**

Antes de considerar concluído:

- [ ] Variáveis configuradas no GitLab
- [ ] Down revision atualizada na migração
- [ ] Commit e push realizados
- [ ] Pipeline executada com sucesso
- [ ] MinIO container rodando
- [ ] Buckets criados
- [ ] Migração executada no servidor
- [ ] Teste de geração + upload funcionando
- [ ] Teste de download funcionando
- [ ] Console web MinIO acessível
- [ ] Documentação lida pelo time de frontend
- [ ] Frontend atualizado para usar URLs pré-assinadas

---

**Implementado em**: 2026-01-23  
**Versão**: 1.0.0  
**Status**: ✅ **COMPLETO - Pronto para deploy**
