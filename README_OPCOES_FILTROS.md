# 📋 Rotas para Opções de Filtros - Evaluation Results

Este documento descreve as novas rotas criadas para obter as opções disponíveis nos filtros de avaliações, permitindo popular os selects do frontend de forma dinâmica.

## 🎯 **Objetivo**

Fornecer endpoints que retornem as opções disponíveis para cada filtro, baseado nos filtros já aplicados, permitindo um afunilamento progressivo das opções.

## 📡 **Rotas Disponíveis**

### 1. **GET /evaluation-results/opcoes-filtros**
**Rota principal que retorna todas as opções disponíveis**

**Query Parameters:**
- `estado` (obrigatório): Estado selecionado
- `municipio` (opcional): Município selecionado
- `escola` (opcional): Escola selecionada
- `serie` (opcional): Série selecionada
- `turma` (opcional): Turma selecionada

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c
```

**Exemplo de retorno:**
```json
{
  "opcoes": {
    "estados": [
      {"id": "ALAGOAS", "nome": "ALAGOAS"},
      {"id": "SÃO PAULO", "nome": "SÃO PAULO"}
    ],
    "municipios": [
      {"id": "618f56d1-2167-439e-bf0b-d3d2be54271c", "nome": "SÃO MIGUEL DOS CAMPOS"},
      {"id": "abc123-def456", "nome": "MACEIÓ"}
    ],
    "escolas": [
      {"id": "123e4567-e89b-12d3-a456-426614174000", "nome": "Escola Municipal Campo Alegre"},
      {"id": "987fcdeb-51a2-43d1-b789-123456789abc", "nome": "Escola Estadual São João"}
    ],
    "series": [
      {"id": "456e7890-f12g-34h5-i678-901234567890", "nome": "9º Ano"},
      {"id": "789f0123-g45h-67i8-j901-234567890123", "nome": "8º Ano"}
    ],
    "turmas": [
      {"id": "abc123-def456-ghi789", "nome": "Turma A"},
      {"id": "def456-ghi789-jkl012", "nome": "Turma B"}
    ],
    "avaliacoes": [
      {"id": "test-123e4567-e89b-12d3-a456-426614174000", "titulo": "Avaliação de Matemática - 9º Ano"},
      {"id": "test-987fcdeb-51a2-43d1-b789-123456789abc", "titulo": "Avaliação de Português - 8º Ano"}
    ]
  },
  "filtros_aplicados": {
    "estado": "ALAGOAS",
    "municipio": "618f56d1-2167-439e-bf0b-d3d2be54271c",
    "escola": null,
    "serie": null,
    "turma": null
  }
}
```

---

### 2. **GET /evaluation-results/opcoes-filtros/estados**
**Retorna todos os estados disponíveis**

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/estados
```

**Exemplo de retorno:**
```json
{
  "estados": [
    {"id": "ALAGOAS", "nome": "ALAGOAS"},
    {"id": "SÃO PAULO", "nome": "SÃO PAULO"},
    {"id": "RIO DE JANEIRO", "nome": "RIO DE JANEIRO"}
  ],
  "total": 3
}
```

---

### 3. **GET /evaluation-results/opcoes-filtros/municipios/{estado}**
**Retorna municípios de um estado específico**

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/municipios/ALAGOAS
```

**Exemplo de retorno:**
```json
{
  "municipios": [
    {"id": "618f56d1-2167-439e-bf0b-d3d2be54271c", "nome": "SÃO MIGUEL DOS CAMPOS"},
    {"id": "abc123-def456-ghi789", "nome": "MACEIÓ"},
    {"id": "def456-ghi789-jkl012", "nome": "ARAPIRACA"}
  ],
  "estado": "ALAGOAS",
  "total": 3
}
```

---

### 4. **GET /evaluation-results/opcoes-filtros/escolas/{municipio_id}**
**Retorna escolas de um município específico**

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/escolas/618f56d1-2167-439e-bf0b-d3d2be54271c
```

**Exemplo de retorno:**
```json
{
  "escolas": [
    {"id": "123e4567-e89b-12d3-a456-426614174000", "nome": "Escola Municipal Campo Alegre"},
    {"id": "987fcdeb-51a2-43d1-b789-123456789abc", "nome": "Escola Estadual São João"},
    {"id": "456e7890-f12g-34h5-i678-901234567890", "nome": "Escola Municipal Santa Maria"}
  ],
  "municipio_id": "618f56d1-2167-439e-bf0b-d3d2be54271c",
  "total": 3
}
```

---

### 5. **GET /evaluation-results/opcoes-filtros/series**
**Retorna séries disponíveis baseado nos filtros aplicados**

**Query Parameters:**
- `estado` (obrigatório): Estado selecionado
- `municipio` (opcional): Município selecionado
- `escola` (opcional): Escola selecionada

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/series?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c
```

**Exemplo de retorno:**
```json
{
  "series": [
    {"id": "456e7890-f12g-34h5-i678-901234567890", "nome": "9º Ano"},
    {"id": "789f0123-g45h-67i8-j901-234567890123", "nome": "8º Ano"},
    {"id": "abc123-def456-ghi789", "nome": "7º Ano"}
  ],
  "total": 3
}
```

---

### 6. **GET /evaluation-results/opcoes-filtros/turmas**
**Retorna turmas disponíveis baseado nos filtros aplicados**

**Query Parameters:**
- `estado` (obrigatório): Estado selecionado
- `municipio` (opcional): Município selecionado
- `escola` (opcional): Escola selecionada
- `serie` (opcional): Série selecionada

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/turmas?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c&serie=456e7890-f12g-34h5-i678-901234567890
```

**Exemplo de retorno:**
```json
{
  "turmas": [
    {"id": "abc123-def456-ghi789", "nome": "Turma A"},
    {"id": "def456-ghi789-jkl012", "nome": "Turma B"},
    {"id": "ghi789-jkl012-mno345", "nome": "Turma C"}
  ],
  "total": 3
}
```

---

### 7. **GET /evaluation-results/opcoes-filtros/avaliacoes**
**Retorna avaliações disponíveis baseado nos filtros aplicados**

**Query Parameters:**
- `estado` (obrigatório): Estado selecionado
- `municipio` (opcional): Município selecionado
- `escola` (opcional): Escola selecionada
- `serie` (opcional): Série selecionada
- `turma` (opcional): Turma selecionada

**Exemplo de uso:**
```bash
GET /evaluation-results/opcoes-filtros/avaliacoes?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c&serie=456e7890-f12g-34h5-i678-901234567890
```

**Exemplo de retorno:**
```json
{
  "avaliacoes": [
    {"id": "test-123e4567-e89b-12d3-a456-426614174000", "titulo": "Avaliação de Matemática - 9º Ano"},
    {"id": "test-987fcdeb-51a2-43d1-b789-123456789abc", "titulo": "Avaliação de Português - 8º Ano"},
    {"id": "test-456e7890-f12g-34h5-i678-901234567890", "titulo": "Simulado SAEB - 5º Ano"}
  ],
  "total": 3
}
```

## 🔄 **Fluxo de Uso no Frontend**

### **Passo 1: Carregar Estados**
```javascript
// Carregar estados disponíveis
const response = await fetch('/evaluation-results/opcoes-filtros/estados');
const { estados } = await response.json();
// Popular select de estados
```

### **Passo 2: Usuário seleciona Estado**
```javascript
// Quando usuário seleciona um estado
const estadoSelecionado = "ALAGOAS";
const response = await fetch(`/evaluation-results/opcoes-filtros/municipios/${estadoSelecionado}`);
const { municipios } = await response.json();
// Popular select de municípios
```

### **Passo 3: Usuário seleciona Município**
```javascript
// Quando usuário seleciona um município
const municipioSelecionado = "618f56d1-2167-439e-bf0b-d3d2be54271c";
const response = await fetch(`/evaluation-results/opcoes-filtros/escolas/${municipioSelecionado}`);
const { escolas } = await response.json();
// Popular select de escolas
```

### **Passo 4: Usuário seleciona Escola**
```javascript
// Quando usuário seleciona uma escola
const response = await fetch(`/evaluation-results/opcoes-filtros/series?estado=${estado}&municipio=${municipio}&escola=${escola}`);
const { series } = await response.json();
// Popular select de séries
```

### **Passo 5: Usuário seleciona Série**
```javascript
// Quando usuário seleciona uma série
const response = await fetch(`/evaluation-results/opcoes-filtros/turmas?estado=${estado}&municipio=${municipio}&escola=${escola}&serie=${serie}`);
const { turmas } = await response.json();
// Popular select de turmas
```

### **Passo 6: Usuário seleciona Turma**
```javascript
// Quando usuário seleciona uma turma
const response = await fetch(`/evaluation-results/opcoes-filtros/avaliacoes?estado=${estado}&municipio=${municipio}&escola=${escola}&serie=${serie}&turma=${turma}`);
const { avaliacoes } = await response.json();
// Popular select de avaliações
```

## 🔐 **Controle de Acesso**

- **Admin**: Vê todas as opções de todos os estados
- **Professor**: Vê apenas opções relacionadas às suas avaliações
- **Coordenador/Diretor**: Vê opções baseadas em suas permissões

## ⚠️ **Observações Importantes**

1. **Parâmetro obrigatório**: `estado` é sempre obrigatório em todas as rotas
2. **Afunilamento progressivo**: As opções são filtradas baseadas nos filtros já aplicados
3. **Autenticação**: Todas as rotas requerem JWT válido
4. **Autorização**: Baseada no papel do usuário (admin, professor, coordenador, diretor)
5. **Performance**: As consultas são otimizadas com joins e filtros apropriados

## 🚀 **Como Testar**

1. **Faça login** e obtenha um token JWT
2. **Teste a rota principal** com diferentes combinações de filtros
3. **Teste as rotas individuais** para cada tipo de opção
4. **Verifique o afunilamento** aplicando filtros progressivamente

```bash
# Exemplo de teste
curl -H "Authorization: Bearer SEU_TOKEN_JWT" \
     "http://localhost:5000/evaluation-results/opcoes-filtros?estado=ALAGOAS"
``` 