# 🔍 Scripts de Diagnóstico - Alinhamento da Grade

## Problema
O grid de detecção de bolhas está **alinhado no início** mas **desalinha no final**, com fill_ratios aumentando progressivamente.

## Scripts Criados

### 1. 📋 `diagnose_grid_alignment.py`
**O quê faz**: Análise teórica dos parâmetros
- Verifica se `line_height` está sendo ajustado (14px → 18px)
- Calcula diferença acumulada
- Mostra impacto no posicionamento Y
- Analisa raio da bolha

**Como rodar**:
```bash
python diagnose_grid_alignment.py
```

**Saída**: Relatório com análise teórica

---

### 2. 📏 `measure_real_spacing.py`
**O quê faz**: Mede o espaçamento REAL das bolhas em imagens
- Detecta bolhas automaticamente com HoughCircles
- Mede espaçamento vertical entre questões
- Mede espaçamento horizontal entre alternativas
- Compara com valores esperados

**Como rodar**:
```bash
# Auto-detectar imagens em debug_corrections/
python measure_real_spacing.py

# OU especificar manualmente
python measure_real_spacing.py debug_corrections/block_01.jpg 1
```

**Saída**:
- Lista de todas as bolhas detectadas
- Espaçamento vertical (esperado 14px ou 18px)
- Estatísticas (média, desvio padrão, min, max)
- Espaçamento horizontal das alternativas

**⚠️ Importante**: Necessita de imagens de debug (que são geradas durante a correção)

---

### 3. 🎨 `generate_grid_overlay.py`
**O quê faz**: Gera visualizações da grade esperada
- Desenha grade com line_height=14px (VERDE)
- Desenha grade com line_height=18px (VERMELHO)
- Sobrepõe na imagem real para comparação visual
- Gera imagem de comparação lado-a-lado

**Como rodar**:
```bash
# Auto-processar todas as imagens
python generate_grid_overlay.py

# OU especificar manualmente
python generate_grid_overlay.py debug_corrections/block_01.jpg 1
```

**Saída**: Imagens em `debug_corrections/grid_overlay/`
- `block_01_grid_14px.jpg` - Grade com 14px (VERDE)
- `block_01_grid_18px.jpg` - Grade com 18px (VERMELHO)
- `block_01_grid_comparison.jpg` - Ambas sobrepostas
- `00_LEGENDA.jpg` - Legenda das cores

**🎯 Como interpretar**:
- Se as bolhas alinham melhor com **VERDE** (14px) → usar 14px
- Se as bolhas alinham melhor com **VERMELHO** (18px) → usar 18px

---

### 4. 🔍 `compare_expected_vs_real.py`
**O quê faz**: Comparação e recomendações
- Carrega todas as configurações dos blocos
- Calcula valores esperados com ambos os line_heights
- Imprime tabela comparativa
- Fornece plano de ação detalhado

**Como rodar**:
```bash
python compare_expected_vs_real.py
```

**Saída**:
- Tabela com blocos analisados
- Posições esperadas para questões-chave
- Recomendações específicas
- Plano de ação com instruções

---

### 5. 🚀 `run_full_diagnostic.py`
**O quê faz**: Orquestra todos os scripts em sequência
- Executa diagnóstico → medição → visualização → comparação
- Gera relatório final com próximas etapas

**Como rodar**:
```bash
python run_full_diagnostic.py
```

---

## 📊 Fluxo de Diagnóstico Completo

```
┌─────────────────────────────────────────┐
│ 1. run_full_diagnostic.py               │
│    (Inicia diagnóstico completo)        │
└────────────┬────────────────────────────┘
             │
             ├─→ diagnose_grid_alignment.py
             │   └─→ Análise teórica dos parâmetros
             │
             ├─→ measure_real_spacing.py
             │   └─→ Detecta bolhas e mede espaçamento
             │
             ├─→ generate_grid_overlay.py
             │   └─→ Cria visualizações (VERDE 14px / VERMELHO 18px)
             │
             └─→ compare_expected_vs_real.py
                 └─→ Análise comparativa + plano de ação
```

---

## 🎯 Ordem de Execução Recomendada

### Fase 1: Entender o Problema
```bash
python diagnose_grid_alignment.py
```
→ Lê o relatório teórico

### Fase 2: Verificar Realidade
```bash
python measure_real_spacing.py
```
→ Vê o espaçamento real das bolhas

### Fase 3: Visualizar
```bash
python generate_grid_overlay.py
```
→ Abre as imagens em `debug_corrections/grid_overlay/`
→ Compara visualmente com grade VERDE (14px) e VERMELHA (18px)

### Fase 4: Decisão
```bash
python compare_expected_vs_real.py
```
→ Segue o plano de ação

---

## 🔧 Interpretando os Resultados

### Cenário A: Bolhas alinham com VERDE (14px)
```
✅ CONCLUSÃO: line_height deveria ser 14px

📋 AÇÃO:
   1. Abrir: app/services/cartao_resposta/correction_n.py
   2. Ir para: linha ~2595
   3. COMENTAR o ajuste dinâmico:
      
      # ⚠️ DESABILITAR AJUSTE DINÂMICO
      # if abs(line_height - ideal_line_height) > 0.5:
      #     adjusted_line_height = round(ideal_line_height)
      #     use_line_height = adjusted_line_height
      
      use_line_height = line_height  # Sempre usar JSON
```

### Cenário B: Bolhas alinham com VERMELHO (18px)
```
✅ CONCLUSÃO: line_height deveria ser 18px

📋 AÇÃO:
   1. Atualizar JSONs:
      - block_01_coordinates_adjustment.json
      - block_02_coordinates_adjustment.json
      - block_03_coordinates_adjustment.json
      - block_04_coordinates_adjustment.json
      
      Mudar "line_height": 14 → "line_height": 18
   
   2. Desabilitar ajuste dinâmico (mesmo assim)
```

---

## 📝 Notas Importantes

### Quando não há imagens de debug
Se os scripts de medição/visualização retornarem erro, é porque:
- As imagens de debug ainda não foram geradas
- Isso ocorre na primeira vez que você roda `python run.py` com um cartão

**Solução**: 
1. Rodar `python run.py` com um cartão de teste
2. Isso vai gerar `debug_corrections/`
3. Aí rodar os scripts de medição/visualização

### Interpretação de Statistics
```
Espaçamento médio: 14.2px
Desvio padrão:     0.5px
```
- Se média ≈ 14px: usar 14px
- Se média ≈ 18px: usar 18px
- Se desvio padrão > 1px: há distorção na imagem

---

## ✅ Checklist de Diagnóstico

- [ ] Rodar `diagnose_grid_alignment.py` e ler análise teórica
- [ ] Gerar imagens de teste (rodar `python run.py` uma vez)
- [ ] Rodar `measure_real_spacing.py` e analisar estatísticas
- [ ] Rodar `generate_grid_overlay.py` e visualizar
- [ ] Decidir: 14px ou 18px baseado nas visualizações
- [ ] Rodar `compare_expected_vs_real.py` e seguir plano de ação
- [ ] Implementar solução em `correction_n.py`
- [ ] Testar com imagem real
- [ ] Verificar se fill_ratios ficaram consistentes

---

## 🆘 Troubleshooting

### "Nenhuma bolha detectada"
- Imagem muito escura ou clara
- Bolhas não marcadas no cartão
- Algoritmo HoughCircles não reconheceu como círculos

**Solução**: Ajustar parâmetros de HoughCircles em `measure_real_spacing.py`

### "Arquivo não encontrado"
- Ainda não há imagens em `debug_corrections/`
- Caminho incorreto

**Solução**: Rodar `python run.py` primeiro para gerar imagens

### Visualizações em branco
- Imagem muito pequena ou muito grande
- Valores de overlay incorretos

**Solução**: Verificar dimensões da imagem, ajustar escala em `generate_grid_overlay.py`

---

## 📊 Saída Esperada

Após completar o diagnóstico, você deve ter:

```
✅ Relatório teórico (analyze_grid_alignment.py)
✅ Espaçamento real medido (measure_real_spacing.py)
✅ Visualizações em cores (generate_grid_overlay.py)
✅ Plano de ação (compare_expected_vs_real.py)
✅ Recomendação clara (use 14px ou 18px)
```

---

## 🎓 O que cada número significa

- **14px**: Valor no arquivo JSON (original calibrado)
- **18px**: Valor calculado dinamicamente pelo código (17.58px → 18px)
- **fill_ratio**: Percentual de preenchimento de uma bolha (0.0 = vazia, 1.0 = cheia)
- **line_height**: Espaçamento vertical entre questões em pixels

---

Criado em: 2026-01-21
Versão: 1.0
