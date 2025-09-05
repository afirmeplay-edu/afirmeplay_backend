# Sistema de Formulários Físicos de Provas

Este sistema permite gerar e corrigir provas físicas integrado com o banco de dados existente.

## Arquivos Criados

### Modelos de Dados
- `app/models/physicalTestForm.py` - Modelo para formulários físicos
- `app/models/physicalTestAnswer.py` - Modelo para respostas físicas

### Serviços
- `app/services/physical_test_pdf_generator.py` - Geração de PDFs com provas e formulários
- `app/services/physical_test_correction.py` - Correção automática usando OpenCV
- `app/services/physical_test_form_service.py` - Serviço principal de coordenação

### Rotas
- `app/routes/physical_test_routes.py` - Endpoints da API

## Fluxo de Funcionamento

### 1. Geração de Formulários Físicos

**Endpoint:** `POST /physical-tests/test/{test_id}/generate-forms`

**Pré-requisitos:**
- A prova deve existir
- A prova deve ter sido aplicada (class_test.status != 'agendada')
- A prova deve ter questões associadas

**Processo:**
1. Verifica se a prova foi aplicada
2. Busca questões da prova ordenadas
3. Busca alunos das turmas onde a prova foi aplicada
4. Gera PDF individual para cada aluno contendo:
   - Cabeçalho com dados do aluno e da prova
   - Todas as questões com alternativas
   - Formulário de resposta com QR Code único
   - Gabarito com respostas corretas
5. Salva informações no banco de dados

**Resposta:**
```json
{
  "message": "Formulários gerados com sucesso",
  "generated_forms": 25,
  "test_title": "Prova de Matemática",
  "total_questions": 20,
  "total_students": 25,
  "forms": [
    {
      "id": "form_id",
      "student_id": "student_id",
      "student_name": "Nome do Aluno",
      "pdf_url": "/path/to/pdf",
      "qr_code_data": "test_id_student_id"
    }
  ]
}
```

### 2. Processamento de Correção

**Endpoint:** `POST /physical-tests/test/{test_id}/process-correction`

**Body:**
- `image`: Imagem do gabarito preenchido (base64 ou file upload)
- `correction_image_url` (opcional): URL para salvar imagem corrigida

**Processo:**
1. Recebe imagem do gabarito preenchido
2. Detecta QR Code para identificar o aluno
3. Processa imagem com OpenCV para detectar marcações
4. Compara respostas com gabarito correto
5. Calcula proficiência, nota e classificação usando sistema existente
6. Salva resultados na tabela `evaluation_results`
7. Retorna imagem corrigida com marcações coloridas

**Resposta:**
```json
{
  "message": "Correção processada com sucesso",
  "student_id": "student_id",
  "correction_results": {
    "correct_answers": 18,
    "incorrect_answers": 2,
    "unanswered": 0,
    "total_questions": 20,
    "detailed_results": [...]
  },
  "physical_form_id": "form_id",
  "corrected_image": "data:image/jpeg;base64,..."
}
```

## Endpoints Disponíveis

### 1. Gerar Formulários
```
POST /physical-tests/test/{test_id}/generate-forms
```

### 2. Processar Correção
```
POST /physical-tests/test/{test_id}/process-correction
```

### 3. Listar Formulários
```
GET /physical-tests/test/{test_id}/forms
GET /physical-tests/test/{test_id}/forms?student_id={student_id}
```

### 4. Download de Formulário
```
GET /physical-tests/test/{test_id}/download/{form_id}
```

### 5. Verificar Status
```
GET /physical-tests/test/{test_id}/status
```

## Integração com Sistema Existente

### Reutilização de Código
- **EvaluationCalculator**: Para calcular proficiência, nota e classificação
- **EvaluationResultService**: Para salvar resultados na tabela `evaluation_results`
- **Sistema de QR Code**: Adaptado do `formularios.py` original
- **Processamento de imagem**: Adaptado do `projeto.py` original

### Validações
- Verifica se `class_test.status != 'agendada'` antes de gerar formulários
- Valida permissões do professor (só pode gerar para suas próprias provas)
- Verifica se aluno pertence à turma onde a prova foi aplicada

### Fluxo de Dados
```
1. Professor aplica prova → class_test.status = 'em_andamento'
2. Professor gera formulários físicos → PDFs com QR Codes
3. Alunos preenchem gabaritos físicos
4. Professor faz upload do gabarito preenchido
5. Sistema processa correção → evaluation_results
6. Resultados ficam disponíveis para relatórios
```

## Estrutura do PDF Gerado

### Página 1: Prova
- Cabeçalho com nome da escola, aluno e data
- Instruções da prova
- Questões numeradas com:
  - Título da questão
  - Texto formatado
  - Alternativas (A, B, C, D, E)

### Página 2: Formulário de Resposta
- QR Code único do aluno
- Nome do aluno
- Formulário com círculos para marcar respostas
- Layout de 2 colunas para questões 11-20

### Página 3: Gabarito
- Respostas corretas de todas as questões
- Para referência do professor

## Configurações

### Parâmetros de Layout
- Tamanho do formulário: 720x320 pixels
- QR Code: 100x100 pixels
- Círculos de resposta: 18x18 pixels
- Coordenadas fixas para detecção de marcações

### Detecção de Marcações
- Threshold adaptativo: 70% de pixels brancos
- Máscara circular para cada alternativa
- Confiança mínima: 70%

## Dependências Necessárias

```bash
pip install opencv-python
pip install qrcode[pil]
pip install reportlab
pip install pillow
```

## Próximos Passos

1. **Registrar rotas** no `app/__init__.py`
2. **Criar migrações** para os novos modelos
3. **Testar integração** com sistema existente
4. **Implementar storage** para imagens corrigidas
5. **Adicionar validações** adicionais se necessário

## Vantagens

- **Integração completa** com sistema existente
- **Reutilização** de toda lógica de cálculo
- **Consistência** nos resultados
- **Flexibilidade** para qualquer número de questões
- **Validação** de aplicação da prova
- **Permissões** baseadas em roles
