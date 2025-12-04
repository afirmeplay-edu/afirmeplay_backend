# Plano de Implementação: Correção de Provas Institucionais com IA

## 📋 Análise do Sistema Atual

### Situação Atual
1. **Geração de Provas**: `institutional_test_weasyprint_generator.py` gera PDFs com:
   - QR Code contendo `student_id` e `test_id` (JSON)
   - Formulário de respostas com bolhas OMR (A, B, C, D)
   - Borda grossa preta ao redor dos blocos para detecção OMR

2. **Correção Atual**: `physical_test_pdf_generator.py` e `sistemaORM.py`:
   - Detectam QR Code na imagem escaneada
   - Tentam detectar bolhas marcadas usando OpenCV
   - Salvam respostas no banco (`StudentAnswer`)
   - Calculam nota e proficiência

3. **Problema Identificado**: 
   - Detecção OMR não está funcionando corretamente
   - Imagens podem ter baixa qualidade, distorção, iluminação irregular
   - Alinhamento de perspectiva pode falhar

4. **IA Existente**: `ai_analysis_service.py`:
   - Usa OpenAI/Gemini para análise de relatórios
   - Já tem infraestrutura configurada (OpenAI e Gemini)
   - Usa prompts estruturados com templates

---

## 🎯 Objetivo

Implementar correção de provas institucionais usando IA para:
1. **Detectar bolhas marcadas** quando OMR falhar
2. **Validar detecções OMR** duvidosas
3. **Processar casos especiais** (marcações parciais, rasuras, etc.)
4. **Fallback inteligente** quando detecção tradicional falhar

---

## 🏗️ Arquitetura Proposta

### Fluxo Híbrido: OMR + IA

```
┌─────────────────────────────────────────────────────────┐
│ 1. Receber Imagem Escaneada                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Detectar QR Code (OpenCV)                           │
│    - Extrair student_id e test_id                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Tentar Detecção OMR Tradicional (OpenCV)             │
│    - Alinhamento de perspectiva                        │
│    - Detecção de bolhas                                │
│    - Confiança: ALTA, MÉDIA, BAIXA                     │
└──────────────────┬──────────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
    [ALTA]              [MÉDIA/BAIXA]
    Confiança          Confiança
         │                   │
         │                   ▼
         │         ┌─────────────────────────┐
         │         │ 4. Usar IA para         │
         │         │    Validação/Correção   │
         │         └──────────┬──────────────┘
         │                    │
         └──────────┬─────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Salvar Respostas no Banco                            │
│    - StudentAnswer                                       │
│    - EvaluationResult                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Componentes a Criar

### 1. Serviço de Correção com IA
**Arquivo**: `app/services/ai_correction_service.py`

**Responsabilidades**:
- Receber imagem do formulário de respostas
- Extrair região do formulário (cortar cabeçalho, rodapé)
- Enviar para IA com prompt estruturado
- Processar resposta da IA
- Retornar respostas detectadas

**Métodos Principais**:
```python
class AICorrectionService:
    def correct_with_ai(self, image_data, test_id, student_id, questions_data) -> Dict
    def _prepare_image_for_ai(self, image) -> bytes
    def _build_correction_prompt(self, questions_data, num_questions) -> str
    def _call_ai_api(self, prompt, image_base64) -> str
    def _parse_ai_response(self, ai_response) -> Dict[int, str]  # {question_num: answer}
```

### 2. Integração no Fluxo de Correção
**Arquivo**: `app/services/physical_test_pdf_generator.py` (modificar)

**Modificações**:
- Adicionar método `_corrigir_com_ia_fallback()`
- Chamar quando OMR falhar ou tiver baixa confiança
- Comparar resultados OMR vs IA quando ambos disponíveis

### 3. Endpoint de Correção com IA
**Arquivo**: `app/routes/physical_test_routes.py` (adicionar)

**Novo Endpoint**:
```python
@bp.route('/test/<string:test_id>/process-correction-ai', methods=['POST'])
def process_correction_with_ai(test_id):
    """
    Processa correção usando IA como método principal ou fallback
    """
```

---

## 🔧 Detalhamento Técnico

### 1. Preparação da Imagem para IA

**Processo**:
1. Detectar QR Code (já funciona)
2. Extrair região do formulário de respostas:
   - Identificar borda grossa preta (5px) ao redor dos blocos
   - Cortar região interna do formulário
   - Redimensionar para tamanho padrão (ex: 2000x3000px)
   - Melhorar contraste e nitidez

**Código Base**:
```python
def _prepare_image_for_ai(self, image):
    # 1. Converter para grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2. Detectar borda grossa (5px) usando contornos
    # 3. Extrair ROI do formulário
    # 4. Aplicar pré-processamento (contraste, nitidez)
    # 5. Converter para base64
    
    return image_base64
```

### 2. Prompt para IA

**Estrutura do Prompt**:
```
Você é um especialista em correção de provas escolares usando formulários de múltipla escolha.

TAREFA:
Analise a imagem do formulário de respostas e identifique quais bolhas foram marcadas pelo aluno.

INSTRUÇÕES:
1. O formulário contém {num_questions} questões
2. Cada questão tem 4 alternativas: A, B, C, D
3. As bolhas estão organizadas em blocos de 12 questões cada
4. Identifique APENAS bolhas completamente preenchidas (não aceite marcações parciais ou rasuras)

FORMATO DE RESPOSTA:
Retorne um JSON com o seguinte formato:
{
  "answers": {
    "1": "A",  // ou "B", "C", "D", ou null se não marcada
    "2": "B",
    ...
  },
  "confidence": {
    "1": 0.95,  // nível de confiança (0-1)
    "2": 0.87,
    ...
  },
  "notes": {
    "1": "Marcação clara e completa",
    "2": "Marcação parcial, mas aceita",
    ...
  }
}

IMPORTANTE:
- Se uma questão não tiver marcação clara, retorne null
- Se houver múltiplas marcações na mesma questão, retorne a mais provável
- Se houver rasura, considere a marcação mais recente/visível
```

### 3. Integração com OpenAI/Gemini Vision

**Gemini** (preferencial - suporta visão):
```python
from app.openai_config.openai_config import get_gemini_client

def _call_ai_api(self, prompt, image_base64):
    gemini = get_gemini_client()
    
    # Gemini suporta imagens diretamente
    response = gemini.generate_content([
        prompt,
        {
            "mime_type": "image/jpeg",
            "data": image_base64
        }
    ])
    
    return response.text
```

**OpenAI** (fallback - também suporta visão):
```python
from app.openai_config.openai_config import get_openai_client

def _call_ai_api(self, prompt, image_base64):
    client = get_openai_client()
    
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",  # ou gpt-4o
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000
    )
    
    return response.choices[0].message.content
```

### 4. Processamento da Resposta da IA

**Validação e Parsing**:
```python
def _parse_ai_response(self, ai_response):
    import json
    import re
    
    # Tentar extrair JSON da resposta
    # A IA pode retornar JSON puro ou texto com JSON
    
    # Método 1: Buscar JSON entre ```json ... ```
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Método 2: Buscar JSON direto
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("JSON não encontrado na resposta da IA")
    
    # Parsear JSON
    result = json.loads(json_str)
    
    # Validar estrutura
    if 'answers' not in result:
        raise ValueError("Resposta da IA não contém 'answers'")
    
    # Converter para formato esperado: {question_num: answer}
    answers = {}
    for q_num_str, answer in result['answers'].items():
        q_num = int(q_num_str)
        if answer and answer.upper() in ['A', 'B', 'C', 'D']:
            answers[q_num] = answer.upper()
        else:
            answers[q_num] = None  # Não marcada ou inválida
    
    return answers
```

---

## 🔄 Fluxo de Integração

### Opção 1: IA como Fallback (Recomendado)
```
1. Tentar OMR tradicional
2. Se OMR falhar OU confiança < 0.7:
   → Usar IA
3. Se ambos disponíveis:
   → Comparar resultados
   → Usar IA se diferença significativa
```

### Opção 2: IA como Validador
```
1. Executar OMR tradicional
2. Executar IA em paralelo
3. Comparar resultados:
   - Se concordam: usar resultado
   - Se discordam: usar IA (mais confiável)
   - Se IA não detectou: usar OMR
```

### Opção 3: IA como Método Principal
```
1. Usar IA diretamente
2. OMR apenas para debug/validação
```

**Recomendação**: Começar com **Opção 1** (Fallback), depois evoluir para **Opção 2** (Validador).

---

## 📝 Estrutura de Arquivos

```
app/
├── services/
│   ├── ai_correction_service.py          # NOVO: Serviço de correção com IA
│   ├── physical_test_pdf_generator.py    # MODIFICAR: Adicionar fallback IA
│   └── ai_analysis_service.py            # EXISTENTE: Reutilizar configuração
│
├── routes/
│   └── physical_test_routes.py           # MODIFICAR: Adicionar endpoint IA
│
└── openai_config/
    └── openai_config.py                  # EXISTENTE: Já tem Gemini/OpenAI
```

---

## 🧪 Casos de Teste

### 1. Imagem de Alta Qualidade
- **Entrada**: Imagem nítida, bem iluminada, sem distorção
- **Esperado**: IA detecta todas as respostas corretamente
- **Confiança**: > 0.9

### 2. Imagem de Baixa Qualidade
- **Entrada**: Imagem borrada, baixa resolução, iluminação irregular
- **Esperado**: IA detecta respostas com confiança média
- **Confiança**: 0.7 - 0.9

### 3. Marcações Parciais
- **Entrada**: Bolhas parcialmente preenchidas
- **Esperado**: IA identifica se é marcação válida ou não
- **Nota**: Incluir observação sobre marcação parcial

### 4. Múltiplas Marcações
- **Entrada**: Questão com 2 bolhas marcadas (rasura)
- **Esperado**: IA identifica a marcação mais provável
- **Nota**: Incluir observação sobre rasura

### 5. Questões Não Marcadas
- **Entrada**: Questão sem marcação
- **Esperado**: IA retorna null/None
- **Confiança**: Baixa (0.3 - 0.5)

---

## ⚙️ Configurações

### Variáveis de Ambiente
```python
# app/openai_config/openai_config.py

# Adicionar configurações específicas para correção
AI_CORRECTION_MODEL = "gemini-2.0-flash-exp"  # Modelo com visão
AI_CORRECTION_TEMPERATURE = 0.1  # Baixa temperatura para precisão
AI_CORRECTION_MAX_TOKENS = 2000
AI_CORRECTION_CONFIDENCE_THRESHOLD = 0.7  # Confiança mínima para aceitar
```

### Flags de Controle
```python
# Permitir escolher método de correção
USE_AI_CORRECTION = True  # Habilitar correção com IA
AI_CORRECTION_MODE = "fallback"  # "fallback", "validator", "primary"
FORCE_AI_CORRECTION = False  # Forçar IA mesmo se OMR funcionar
```

---

## 📊 Métricas e Monitoramento

### Logs a Registrar
1. **Método usado**: OMR, IA, ou ambos
2. **Confiança média**: Nível de confiança das detecções
3. **Tempo de processamento**: Tempo total de correção
4. **Taxa de sucesso**: % de questões detectadas corretamente
5. **Custos**: Tokens/requisições da API de IA

### Dashboard de Monitoramento
- Taxa de uso de IA vs OMR
- Confiança média por método
- Tempo médio de processamento
- Custos acumulados de API

---

## 🚀 Fases de Implementação

### Fase 1: MVP (Mínimo Viável)
- [ ] Criar `ai_correction_service.py` básico
- [ ] Implementar detecção com Gemini Vision
- [ ] Integrar como fallback quando OMR falhar
- [ ] Testar com 10-20 imagens reais

### Fase 2: Melhorias
- [ ] Adicionar validação cruzada (OMR + IA)
- [ ] Melhorar pré-processamento de imagem
- [ ] Adicionar tratamento de casos especiais
- [ ] Otimizar custos (cache, batch processing)

### Fase 3: Produção
- [ ] Monitoramento e métricas
- [ ] Tratamento de erros robusto
- [ ] Documentação completa
- [ ] Treinamento de usuários

---

## 💰 Estimativa de Custos

### Gemini 2.0 Flash (Recomendado)
- **Custo**: ~$0.075 por 1M tokens de entrada, ~$0.30 por 1M tokens de saída
- **Imagem**: ~500 tokens por imagem (base64)
- **Prompt**: ~500 tokens
- **Resposta**: ~200 tokens (JSON)
- **Total por correção**: ~1.200 tokens = **$0.0001 por correção**

### OpenAI GPT-4 Vision
- **Custo**: ~$0.01 por imagem + tokens
- **Total por correção**: **~$0.01 por correção**

**Recomendação**: Usar Gemini para custos menores.

---

## 🔒 Considerações de Segurança

1. **Dados Sensíveis**: Imagens contêm informações de alunos
   - Não armazenar imagens processadas por IA
   - Limpar cache após processamento
   - Logs não devem conter dados pessoais

2. **Rate Limiting**: Limitar requisições à API
   - Máximo de correções simultâneas
   - Queue para processamento em lote

3. **Validação**: Sempre validar respostas da IA
   - Verificar formato JSON
   - Validar range de questões
   - Verificar alternativas válidas (A, B, C, D)

---

## 📚 Referências

- **Gemini Vision API**: https://ai.google.dev/docs
- **OpenAI Vision API**: https://platform.openai.com/docs/guides/vision
- **OpenCV OMR**: Código existente em `physical_test_pdf_generator.py`
- **IA de Análise**: Código existente em `ai_analysis_service.py`

---

## ✅ Próximos Passos

1. **Revisar este plano** com a equipe
2. **Aprovar arquitetura** proposta
3. **Criar branch** para desenvolvimento
4. **Implementar Fase 1** (MVP)
5. **Testar** com imagens reais
6. **Iterar** baseado em feedback

---

**Data de Criação**: 2025-01-XX
**Autor**: Sistema de Planejamento
**Status**: Aguardando Aprovação

