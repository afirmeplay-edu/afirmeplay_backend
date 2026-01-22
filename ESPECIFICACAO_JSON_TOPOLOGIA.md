# 📋 ESPECIFICAÇÃO DO JSON DE TOPOLOGIA

**Data:** 21 de Janeiro de 2026  
**Versão:** 1.0  
**Sistema:** Pipeline OMR Robusto e Determinístico

---

## 🎯 OBJETIVO

O JSON de topologia é a **FONTE DA VERDADE** sobre a estrutura do cartão-resposta.

**PRINCÍPIO FUNDAMENTAL:**
> "A imagem não define linhas ou colunas.  
> O JSON define TUDO.  
> A imagem apenas confirma o preenchimento."

---

## 📐 ESTRUTURA BÁSICA

```json
{
  "gabarito_id": "uuid-do-gabarito",
  "test_id": "uuid-da-prova",
  "num_blocks": 4,
  "use_blocks": true,
  "questions_per_block": 12,
  "total_questions": 48,
  "topology": {
    "blocks": [
      {
        "block_id": 1,
        "block_number": 1,
        "subject_name": "Matemática",
        "questions": [
          {
            "q": 1,
            "q_global": 1,
            "alternatives": ["A", "B", "C", "D"]
          },
          {
            "q": 2,
            "q_global": 2,
            "alternatives": ["A", "B", "C", "D"]
          }
        ]
      },
      {
        "block_id": 2,
        "block_number": 2,
        "subject_name": "Português",
        "questions": [
          {
            "q": 13,
            "q_global": 13,
            "alternatives": ["A", "B", "C"]
          }
        ]
      }
    ]
  }
}
```

---

## 📖 CAMPOS OBRIGATÓRIOS

### Nível Raiz

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `gabarito_id` | String (UUID) | ✅ SIM | ID único do gabarito no banco |
| `test_id` | String (UUID) | ✅ SIM | ID da prova |
| `num_blocks` | Integer | ✅ SIM | Número total de blocos no cartão |
| `use_blocks` | Boolean | ✅ SIM | Se usa estrutura de blocos (sempre true) |
| `total_questions` | Integer | ✅ SIM | Total de questões em todos os blocos |
| `topology` | Object | ✅ SIM | Estrutura de blocos e questões |

### Nível topology.blocks[]

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `block_id` | Integer | ✅ SIM | ID do bloco (1, 2, 3, 4) |
| `block_number` | Integer | ✅ SIM | Número do bloco para exibição |
| `questions` | Array | ✅ SIM | Lista de questões do bloco |
| `subject_name` | String | ❌ NÃO | Nome da disciplina (opcional) |

### Nível topology.blocks[].questions[]

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `q` | Integer | ✅ SIM | Número da questão dentro do bloco |
| `q_global` | Integer | ❌ NÃO | Número global da questão (recomendado) |
| `alternatives` | Array[String] | ✅ SIM | Lista de alternativas (ex: ["A","B","C"]) |

---

## ⚙️ COMO O PIPELINE USA O JSON

### ETAPA 5: Detecção de Blocos
```python
# Extrai número esperado de blocos
num_blocks_expected = topology_json["num_blocks"]  # Ex: 4

# Detecta blocos na imagem
blocks = self._detect_answer_blocks(img_a4, grid_area, num_blocks_expected)

# VALIDAÇÃO RIGOROSA
if len(blocks) != num_blocks_expected:
    # ❌ REJEITAR IMAGEM
    return {"success": False, "error": "Número de blocos inválido"}
```

---

### ETAPA 6: Mapeamento JSON → Grid

**INPUT:** JSON + Dimensões do Bloco
```json
{
  "block_id": 1,
  "questions": [
    {"q": 1, "alternatives": ["A", "B", "C"]},
    {"q": 2, "alternatives": ["A", "B", "C", "D"]},
    {"q": 3, "alternatives": ["A", "B"]},
    {"q": 4, "alternatives": ["A", "B", "C", "D", "E"]}
  ]
}
```

```python
block_height = 362  # pixels
block_width = 431   # pixels
```

**PROCESSAMENTO:**
```python
num_rows = len(questions)  # 4 questões = 4 linhas
row_height = block_height / num_rows  # 362 / 4 = 90.5px por linha

for row_idx, question in enumerate(questions):
    alternatives = question["alternatives"]  # ["A", "B", "C"]
    num_cols = len(alternatives)  # 3 alternativas = 3 colunas
    
    # IMPORTANTE: col_width VARIA POR QUESTÃO
    col_width = block_width / num_cols  # 431 / 3 = 143.67px
    
    # Centro Y da linha
    cy = row_height * row_idx + row_height / 2
    
    for col_idx, alt_letter in enumerate(alternatives):
        # Centro X da coluna
        cx = col_width * col_idx + col_width / 2
        
        # Registra posição da bolha
        bubble = {
            "q_num": question["q"],
            "alternative": alt_letter,
            "cx": cx,
            "cy": cy
        }
```

**OUTPUT:** Grid Matemático
```python
{
  "num_rows": 4,
  "row_height": 90.5,
  "questions": [
    {
      "q_num": 1,
      "cy": 45.25,  # Centro da linha 1
      "num_cols": 3,
      "col_width": 143.67,
      "alternatives": [
        {"letter": "A", "cx": 71.83},
        {"letter": "B", "cx": 215.50},
        {"letter": "C", "cx": 359.17}
      ]
    },
    {
      "q_num": 2,
      "cy": 135.75,  # Centro da linha 2
      "num_cols": 4,
      "col_width": 107.75,  # ← Largura diferente!
      "alternatives": [
        {"letter": "A", "cx": 53.875},
        {"letter": "B", "cx": 161.625},
        {"letter": "C", "cx": 269.375},
        {"letter": "D", "cx": 377.125}
      ]
    },
    {
      "q_num": 3,
      "cy": 226.25,  # Centro da linha 3
      "num_cols": 2,
      "col_width": 215.5,  # ← Largura muito diferente!
      "alternatives": [
        {"letter": "A", "cx": 107.75},
        {"letter": "B", "cx": 323.25}
      ]
    },
    {
      "q_num": 4,
      "cy": 316.75,  # Centro da linha 4
      "num_cols": 5,
      "col_width": 86.2,  # ← Largura ainda diferente!
      "alternatives": [
        {"letter": "A", "cx": 43.1},
        {"letter": "B", "cx": 129.3},
        {"letter": "C", "cx": 215.5},
        {"letter": "D", "cx": 301.7},
        {"letter": "E", "cx": 387.9}
      ]
    }
  ]
}
```

---

## 🔍 EXEMPLOS PRÁTICOS

### Exemplo 1: Bloco com Alternativas Variáveis

**JSON:**
```json
{
  "block_id": 1,
  "questions": [
    {"q": 1, "alternatives": ["A", "B"]},
    {"q": 2, "alternatives": ["A", "B", "C", "D"]},
    {"q": 3, "alternatives": ["A", "B", "C"]},
    {"q": 4, "alternatives": ["A", "B", "C", "D", "E"]}
  ]
}
```

**Resultado:**
- Linha 1: 2 bolhas (A, B) - cada uma ocupa 50% da largura
- Linha 2: 4 bolhas (A, B, C, D) - cada uma ocupa 25% da largura
- Linha 3: 3 bolhas (A, B, C) - cada uma ocupa 33.33% da largura
- Linha 4: 5 bolhas (A, B, C, D, E) - cada uma ocupa 20% da largura

---

### Exemplo 2: Múltiplos Blocos com Disciplinas

**JSON:**
```json
{
  "num_blocks": 4,
  "total_questions": 48,
  "topology": {
    "blocks": [
      {
        "block_id": 1,
        "block_number": 1,
        "subject_name": "Matemática",
        "questions": [
          {"q": 1, "q_global": 1, "alternatives": ["A","B","C","D"]},
          {"q": 2, "q_global": 2, "alternatives": ["A","B","C","D"]},
          {"q": 3, "q_global": 3, "alternatives": ["A","B","C","D"]},
          {"q": 4, "q_global": 4, "alternatives": ["A","B","C","D"]},
          {"q": 5, "q_global": 5, "alternatives": ["A","B","C","D"]},
          {"q": 6, "q_global": 6, "alternatives": ["A","B","C","D"]},
          {"q": 7, "q_global": 7, "alternatives": ["A","B","C","D"]},
          {"q": 8, "q_global": 8, "alternatives": ["A","B","C","D"]},
          {"q": 9, "q_global": 9, "alternatives": ["A","B","C","D"]},
          {"q": 10, "q_global": 10, "alternatives": ["A","B","C","D"]},
          {"q": 11, "q_global": 11, "alternatives": ["A","B","C","D"]},
          {"q": 12, "q_global": 12, "alternatives": ["A","B","C","D"]}
        ]
      },
      {
        "block_id": 2,
        "block_number": 2,
        "subject_name": "Português",
        "questions": [
          {"q": 13, "q_global": 13, "alternatives": ["A","B","C","D"]},
          {"q": 14, "q_global": 14, "alternatives": ["A","B","C","D"]},
          {"q": 15, "q_global": 15, "alternatives": ["A","B","C","D"]},
          {"q": 16, "q_global": 16, "alternatives": ["A","B","C","D"]},
          {"q": 17, "q_global": 17, "alternatives": ["A","B","C","D"]},
          {"q": 18, "q_global": 18, "alternatives": ["A","B","C","D"]},
          {"q": 19, "q_global": 19, "alternatives": ["A","B","C","D"]},
          {"q": 20, "q_global": 20, "alternatives": ["A","B","C","D"]},
          {"q": 21, "q_global": 21, "alternatives": ["A","B","C","D"]},
          {"q": 22, "q_global": 22, "alternatives": ["A","B","C","D"]},
          {"q": 23, "q_global": 23, "alternatives": ["A","B","C","D"]},
          {"q": 24, "q_global": 24, "alternatives": ["A","B","C","D"]}
        ]
      },
      {
        "block_id": 3,
        "block_number": 3,
        "subject_name": "Ciências",
        "questions": [
          {"q": 25, "q_global": 25, "alternatives": ["A","B","C","D"]},
          {"q": 26, "q_global": 26, "alternatives": ["A","B","C","D"]},
          {"q": 27, "q_global": 27, "alternatives": ["A","B","C","D"]},
          {"q": 28, "q_global": 28, "alternatives": ["A","B","C","D"]},
          {"q": 29, "q_global": 29, "alternatives": ["A","B","C","D"]},
          {"q": 30, "q_global": 30, "alternatives": ["A","B","C","D"]},
          {"q": 31, "q_global": 31, "alternatives": ["A","B","C","D"]},
          {"q": 32, "q_global": 32, "alternatives": ["A","B","C","D"]},
          {"q": 33, "q_global": 33, "alternatives": ["A","B","C","D"]},
          {"q": 34, "q_global": 34, "alternatives": ["A","B","C","D"]},
          {"q": 35, "q_global": 35, "alternatives": ["A","B","C","D"]},
          {"q": 36, "q_global": 36, "alternatives": ["A","B","C","D"]}
        ]
      },
      {
        "block_id": 4,
        "block_number": 4,
        "subject_name": "História",
        "questions": [
          {"q": 37, "q_global": 37, "alternatives": ["A","B","C","D"]},
          {"q": 38, "q_global": 38, "alternatives": ["A","B","C","D"]},
          {"q": 39, "q_global": 39, "alternatives": ["A","B","C","D"]},
          {"q": 40, "q_global": 40, "alternatives": ["A","B","C","D"]},
          {"q": 41, "q_global": 41, "alternatives": ["A","B","C","D"]},
          {"q": 42, "q_global": 42, "alternatives": ["A","B","C","D"]},
          {"q": 43, "q_global": 43, "alternatives": ["A","B","C","D"]},
          {"q": 44, "q_global": 44, "alternatives": ["A","B","C","D"]},
          {"q": 45, "q_global": 45, "alternatives": ["A","B","C","D"]},
          {"q": 46, "q_global": 46, "alternatives": ["A","B","C","D"]},
          {"q": 47, "q_global": 47, "alternatives": ["A","B","C","D"]},
          {"q": 48, "q_global": 48, "alternatives": ["A","B","C","D"]}
        ]
      }
    ]
  }
}
```

**Resultado:**
- 4 blocos detectados
- Cada bloco com 12 questões
- Total: 48 questões
- Todas com 4 alternativas (A, B, C, D)

---

### Exemplo 3: Prova com Número Variável de Questões por Bloco

**JSON:**
```json
{
  "num_blocks": 3,
  "total_questions": 30,
  "topology": {
    "blocks": [
      {
        "block_id": 1,
        "questions": [
          {"q": 1, "alternatives": ["A","B","C","D"]},
          {"q": 2, "alternatives": ["A","B","C","D"]},
          {"q": 3, "alternatives": ["A","B","C","D"]},
          {"q": 4, "alternatives": ["A","B","C","D"]},
          {"q": 5, "alternatives": ["A","B","C","D"]},
          {"q": 6, "alternatives": ["A","B","C","D"]},
          {"q": 7, "alternatives": ["A","B","C","D"]},
          {"q": 8, "alternatives": ["A","B","C","D"]},
          {"q": 9, "alternatives": ["A","B","C","D"]},
          {"q": 10, "alternatives": ["A","B","C","D"]}
        ]
      },
      {
        "block_id": 2,
        "questions": [
          {"q": 11, "alternatives": ["A","B","C","D"]},
          {"q": 12, "alternatives": ["A","B","C","D"]},
          {"q": 13, "alternatives": ["A","B","C","D"]},
          {"q": 14, "alternatives": ["A","B","C","D"]},
          {"q": 15, "alternatives": ["A","B","C","D"]},
          {"q": 16, "alternatives": ["A","B","C","D"]},
          {"q": 17, "alternatives": ["A","B","C","D"]},
          {"q": 18, "alternatives": ["A","B","C","D"]},
          {"q": 19, "alternatives": ["A","B","C","D"]},
          {"q": 20, "alternatives": ["A","B","C","D"]},
          {"q": 21, "alternatives": ["A","B","C","D"]},
          {"q": 22, "alternatives": ["A","B","C","D"]},
          {"q": 23, "alternatives": ["A","B","C","D"]},
          {"q": 24, "alternatives": ["A","B","C","D"]},
          {"q": 25, "alternatives": ["A","B","C","D"]}
        ]
      },
      {
        "block_id": 3,
        "questions": [
          {"q": 26, "alternatives": ["A","B","C","D"]},
          {"q": 27, "alternatives": ["A","B","C","D"]},
          {"q": 28, "alternatives": ["A","B","C","D"]},
          {"q": 29, "alternatives": ["A","B","C","D"]},
          {"q": 30, "alternatives": ["A","B","C","D"]}
        ]
      }
    ]
  }
}
```

**Resultado:**
- Bloco 1: 10 questões (altura da linha = block_height / 10)
- Bloco 2: 15 questões (altura da linha = block_height / 15)
- Bloco 3: 5 questões (altura da linha = block_height / 5)

**IMPORTANTE:** Cada bloco tem altura de linha diferente!

---

## ⚠️ ERROS COMUNS E COMO EVITAR

### ❌ ERRO 1: Assumir Número Fixo de Alternativas

**Errado:**
```python
# ❌ NUNCA FAÇA ISSO
num_cols = 4  # Assumindo sempre 4 alternativas
col_width = block_width / 4
```

**Correto:**
```python
# ✅ SEMPRE FAÇA ISSO
alternatives = question["alternatives"]  # Ler do JSON
num_cols = len(alternatives)  # Pode ser 2, 3, 4, 5, etc
col_width = block_width / num_cols
```

---

### ❌ ERRO 2: Assumir Número Fixo de Questões

**Errado:**
```python
# ❌ NUNCA FAÇA ISSO
num_rows = 12  # Assumindo sempre 12 questões por bloco
row_height = block_height / 12
```

**Correto:**
```python
# ✅ SEMPRE FAÇA ISSO
questions = block_config["questions"]  # Ler do JSON
num_rows = len(questions)  # Pode ser 5, 10, 12, 15, etc
row_height = block_height / num_rows
```

---

### ❌ ERRO 3: Usar col_width Global

**Errado:**
```python
# ❌ NUNCA FAÇA ISSO
# Calcular col_width uma vez para todo o bloco
col_width = block_width / 4

for question in questions:
    for col_idx in range(4):  # ← Assumindo 4 colunas sempre
        cx = col_width * col_idx + col_width / 2
```

**Correto:**
```python
# ✅ SEMPRE FAÇA ISSO
# Calcular col_width POR QUESTÃO
for question in questions:
    alternatives = question["alternatives"]
    num_cols = len(alternatives)  # ← Pode variar!
    col_width = block_width / num_cols  # ← Recalcular a cada questão
    
    for col_idx, alt_letter in enumerate(alternatives):
        cx = col_width * col_idx + col_width / 2
```

---

### ❌ ERRO 4: Hardcoded Letters

**Errado:**
```python
# ❌ NUNCA FAÇA ISSO
alternatives = ["A", "B", "C", "D"]  # Hardcoded
```

**Correto:**
```python
# ✅ SEMPRE FAÇA ISSO
alternatives = question["alternatives"]  # Do JSON
# Pode ser ["A","B"], ["A","B","C"], ["A","B","C","D"], etc
```

---

## 📚 ESTRUTURA NO BANCO DE DADOS

### Tabela: answer_sheet_gabaritos

```sql
CREATE TABLE answer_sheet_gabaritos (
    id UUID PRIMARY KEY,
    test_id UUID NOT NULL,
    topology_json JSONB NOT NULL,  -- ← JSON completo aqui
    correct_answers JSONB NOT NULL, -- ← Gabarito {1: "A", 2: "C", ...}
    num_blocks INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Exemplo de Consulta

```python
def _load_topology(self, gabarito_id: str) -> Optional[Dict]:
    """Carrega JSON de topologia do banco"""
    
    gabarito = AnswerSheetGabarito.query.filter_by(id=gabarito_id).first()
    
    if not gabarito:
        self.logger.error(f"Gabarito {gabarito_id} não encontrado")
        return None
    
    # topology_json é um campo JSONB
    topology = gabarito.topology_json
    
    # Validar estrutura
    if not topology or "topology" not in topology:
        self.logger.error("JSON de topologia inválido")
        return None
    
    return topology
```

---

## ✅ VALIDAÇÃO DO JSON

### Função de Validação

```python
def validate_topology_json(topology_json: Dict) -> Tuple[bool, Optional[str]]:
    """
    Valida estrutura do JSON de topologia
    
    Retorna:
        (True, None) se válido
        (False, "mensagem de erro") se inválido
    """
    
    # Validar campos raiz
    required_root_fields = ["num_blocks", "use_blocks", "topology"]
    for field in required_root_fields:
        if field not in topology_json:
            return False, f"Campo obrigatório ausente: {field}"
    
    # Validar topology.blocks
    if "blocks" not in topology_json["topology"]:
        return False, "Campo 'topology.blocks' ausente"
    
    blocks = topology_json["topology"]["blocks"]
    
    if not isinstance(blocks, list):
        return False, "'topology.blocks' deve ser uma lista"
    
    if len(blocks) != topology_json["num_blocks"]:
        return False, (
            f"Número de blocos no JSON ({len(blocks)}) difere "
            f"de 'num_blocks' ({topology_json['num_blocks']})"
        )
    
    # Validar cada bloco
    for idx, block in enumerate(blocks):
        block_num = idx + 1
        
        # Validar campos do bloco
        required_block_fields = ["block_id", "questions"]
        for field in required_block_fields:
            if field not in block:
                return False, f"Bloco {block_num}: campo '{field}' ausente"
        
        questions = block["questions"]
        
        if not isinstance(questions, list):
            return False, f"Bloco {block_num}: 'questions' deve ser uma lista"
        
        if len(questions) == 0:
            return False, f"Bloco {block_num}: deve ter pelo menos 1 questão"
        
        # Validar cada questão
        for q_idx, question in enumerate(questions):
            q_num = q_idx + 1
            
            # Validar campos da questão
            required_question_fields = ["q", "alternatives"]
            for field in required_question_fields:
                if field not in question:
                    return False, (
                        f"Bloco {block_num}, Questão {q_num}: "
                        f"campo '{field}' ausente"
                    )
            
            alternatives = question["alternatives"]
            
            if not isinstance(alternatives, list):
                return False, (
                    f"Bloco {block_num}, Questão {q_num}: "
                    f"'alternatives' deve ser uma lista"
                )
            
            if len(alternatives) == 0:
                return False, (
                    f"Bloco {block_num}, Questão {q_num}: "
                    f"deve ter pelo menos 1 alternativa"
                )
            
            # Validar que alternativas são strings
            for alt in alternatives:
                if not isinstance(alt, str):
                    return False, (
                        f"Bloco {block_num}, Questão {q_num}: "
                        f"alternativas devem ser strings"
                    )
    
    return True, None
```

### Uso da Validação

```python
# Ao criar gabarito
topology_json = {
    "num_blocks": 4,
    "topology": {...}
}

is_valid, error_msg = validate_topology_json(topology_json)

if not is_valid:
    raise ValueError(f"JSON de topologia inválido: {error_msg}")

# Salvar no banco
gabarito = AnswerSheetGabarito(
    id=uuid.uuid4(),
    test_id=test_id,
    topology_json=topology_json,
    correct_answers={...},
    num_blocks=topology_json["num_blocks"],
    total_questions=calculate_total_questions(topology_json)
)
```

---

## 🔄 MIGRAÇÃO DE DADOS ANTIGOS

Se você tem dados antigos sem topology_json, precisa gerá-lo:

```python
def generate_topology_from_legacy(num_blocks: int, questions_per_block: int,
                                  num_alternatives: int = 4) -> Dict:
    """
    Gera JSON de topologia a partir de estrutura legada
    
    Args:
        num_blocks: Número de blocos (ex: 4)
        questions_per_block: Questões por bloco (ex: 12)
        num_alternatives: Alternativas por questão (ex: 4)
    
    Retorna:
        JSON de topologia completo
    """
    
    # Gerar letras de alternativas
    letters = ["A", "B", "C", "D", "E", "F", "G", "H"][:num_alternatives]
    
    blocks = []
    q_global = 1
    
    for block_num in range(1, num_blocks + 1):
        questions = []
        
        for q_local in range(1, questions_per_block + 1):
            questions.append({
                "q": q_global,
                "q_global": q_global,
                "alternatives": letters.copy()
            })
            q_global += 1
        
        blocks.append({
            "block_id": block_num,
            "block_number": block_num,
            "questions": questions
        })
    
    total_questions = num_blocks * questions_per_block
    
    return {
        "num_blocks": num_blocks,
        "use_blocks": True,
        "questions_per_block": questions_per_block,
        "total_questions": total_questions,
        "topology": {
            "blocks": blocks
        }
    }


# Exemplo de uso
topology_json = generate_topology_from_legacy(
    num_blocks=4,
    questions_per_block=12,
    num_alternatives=4
)
```

---

## 📝 GERAÇÃO DO JSON AO CRIAR PROVA

Ao criar uma prova no sistema, gerar o JSON automaticamente:

```python
def create_test_with_topology(test_data: Dict) -> str:
    """
    Cria prova e gera JSON de topologia
    
    Args:
        test_data: {
            "title": str,
            "num_blocks": int,
            "questions": [
                {
                    "question_number": int,
                    "subject": str,
                    "alternatives": ["A", "B", "C", "D"],
                    "correct_answer": "A"
                },
                ...
            ]
        }
    
    Retorna:
        gabarito_id (UUID)
    """
    
    # 1. Criar prova no banco
    test = Test(...)
    db.session.add(test)
    db.session.flush()
    
    # 2. Agrupar questões por bloco
    questions_per_block = len(test_data["questions"]) // test_data["num_blocks"]
    
    blocks = []
    correct_answers = {}
    
    for block_num in range(1, test_data["num_blocks"] + 1):
        start_idx = (block_num - 1) * questions_per_block
        end_idx = start_idx + questions_per_block
        
        block_questions = test_data["questions"][start_idx:end_idx]
        
        questions = []
        for q_data in block_questions:
            q_num = q_data["question_number"]
            
            questions.append({
                "q": q_num,
                "q_global": q_num,
                "alternatives": q_data["alternatives"]
            })
            
            correct_answers[q_num] = q_data["correct_answer"]
        
        blocks.append({
            "block_id": block_num,
            "block_number": block_num,
            "subject_name": block_questions[0].get("subject"),
            "questions": questions
        })
    
    # 3. Montar JSON de topologia
    topology_json = {
        "gabarito_id": str(uuid.uuid4()),
        "test_id": str(test.id),
        "num_blocks": test_data["num_blocks"],
        "use_blocks": True,
        "total_questions": len(test_data["questions"]),
        "topology": {
            "blocks": blocks
        }
    }
    
    # 4. Validar JSON
    is_valid, error_msg = validate_topology_json(topology_json)
    if not is_valid:
        raise ValueError(f"JSON inválido: {error_msg}")
    
    # 5. Criar gabarito
    gabarito = AnswerSheetGabarito(
        id=topology_json["gabarito_id"],
        test_id=test.id,
        topology_json=topology_json,
        correct_answers=correct_answers,
        num_blocks=test_data["num_blocks"],
        total_questions=len(test_data["questions"])
    )
    
    db.session.add(gabarito)
    db.session.commit()
    
    return gabarito.id
```

---

## 🎯 RESUMO EXECUTIVO

### O QUE É
O JSON de topologia é um documento que define a estrutura COMPLETA do cartão-resposta.

### O QUE CONTÉM
- Número de blocos
- Para cada bloco:
  - Número de questões
  - Para cada questão:
    - Número da questão
    - Lista de alternativas (VARIÁVEL)

### COMO É USADO
1. Pipeline detecta blocos na imagem
2. Pipeline valida que número de blocos == JSON.num_blocks
3. Para cada bloco:
   - Pipeline lê block_config do JSON
   - Calcula num_rows = len(questions)
   - Calcula row_height = block_height / num_rows
   - Para cada questão:
     - Calcula num_cols = len(alternatives)
     - Calcula col_width = block_width / num_cols (VARIA!)
     - Calcula posições das bolhas matematicamente
4. Pipeline mede preenchimento das bolhas
5. Pipeline retorna respostas detectadas

### POR QUE É IMPORTANTE
- **Elimina hardcoded values:** Nenhum número fixo no código
- **Suporta estruturas variáveis:** 2-5 alternativas, 5-26 questões
- **É determinístico:** Mesma entrada = mesma saída
- **É testável:** Pode validar JSON antes de usar
- **É escalável:** Funciona com qualquer estrutura válida

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Ao Criar Sistema
- [ ] Criar campo `topology_json` (JSONB) na tabela de gabaritos
- [ ] Implementar função `validate_topology_json()`
- [ ] Implementar função `generate_topology_from_legacy()`
- [ ] Migrar dados antigos se necessário

### Ao Criar Prova
- [ ] Gerar JSON de topologia automaticamente
- [ ] Validar JSON antes de salvar
- [ ] Salvar no campo `topology_json`
- [ ] Testar com estruturas variáveis

### Ao Processar Cartão
- [ ] Carregar topology_json do banco
- [ ] Validar JSON antes de usar
- [ ] Passar JSON para `_execute_omr_pipeline()`
- [ ] Usar JSON em `_map_topology_to_grid()`

---

**Autor:** Sistema de Análise OMR  
**Versão:** 1.0  
**Status:** 🟢 ESPECIFICAÇÃO COMPLETA E APROVADA
