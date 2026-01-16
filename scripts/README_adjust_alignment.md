# Script de Ajuste Manual de Alinhamento

Este script permite ajustar manualmente os offsets X e Y para alinhar corretamente as bolhas entre a imagem de referência e a imagem real escaneada.

## Como Funciona

1. **Ajuste Visual**: O script mostra uma visualização interativa onde você pode ajustar os offsets
2. **Salvar Configuração**: Salva os offsets em um arquivo JSON (`block_NN_alignment.json`)
3. **Uso Automático**: O código de correção carrega automaticamente esses offsets e os aplica

## Uso

### Modo 1: Interativo (com janelas OpenCV)

**Requisito**: OpenCV com suporte a GUI instalado.

```bash
# Buscar automaticamente imagens do bloco 1
python scripts/adjust_block_alignment.py --block 1 --auto

# Ou especificar imagens manualmente
python scripts/adjust_block_alignment.py \
  --reference debug_corrections/08_block_01_reference.jpg \
  --real debug_corrections/04_block_01_original.jpg \
  --block 1
```

**Controles (modo interativo):**
- **← →** : Ajustar offset X (-1 / +1 pixel)
- **↑ ↓** : Ajustar offset Y (-1 / +1 pixel)
- **Espaço** : Alternar entre overlay (sobreposição) e lado a lado
- **+/-** : Ajustar transparência do overlay
- **S** : Salvar configuração
- **Q** : Sair (sem salvar)

### Modo 2: Não-Interativo (sem janelas - recomendado se OpenCV não tem GUI)

Se você receber erro sobre OpenCV sem suporte a GUI, use este modo:

```bash
# 1. Gerar imagens de visualização com offsets atuais
python scripts/adjust_block_alignment.py --block 1 --auto --no-interactive

# 2. Ajustar offsets via linha de comando e visualizar
python scripts/adjust_block_alignment.py --block 1 --auto --offset-x -30 --offset-y 20 --no-interactive

# 3. Quando estiver satisfeito, salvar
python scripts/adjust_block_alignment.py --block 1 --auto --offset-x -30 --offset-y 20 --save
```

O modo não-interativo:
- Salva imagens `block_NN_alignment_overlay.jpg` e `block_NN_alignment_side_by_side.jpg`
- Permite ajustar offsets via parâmetros `--offset-x` e `--offset-y`
- Use `--save` para salvar a configuração quando estiver satisfeito

### Passo 3: Verificar o Resultado

Após salvar, o arquivo `block_01_alignment.json` será criado com o formato:

```json
{
  "block_num": 1,
  "offset_x": -32,
  "offset_y": 20,
  "img_ref_path": "debug_corrections/...",
  "img_real_path": "debug_corrections/..."
}
```

### Passo 4: Usar na Correção

O código de correção (`correction_n.py`) **automaticamente** carrega esses offsets quando processar o bloco correspondente. Não é necessário fazer nada adicional!

## Exemplo Completo

### Modo Interativo:
```bash
# 1. Ajustar bloco 1
python scripts/adjust_block_alignment.py --block 1 --auto

# 2. Na interface:
#    - Use as setas para alinhar as bolhas
#    - Pressione S para salvar
#    - Pressione Q para sair

# 3. Executar correção (os offsets serão aplicados automaticamente)
```

### Modo Não-Interativo:
```bash
# 1. Gerar imagens iniciais
python scripts/adjust_block_alignment.py --block 1 --auto --no-interactive

# 2. Abrir as imagens geradas e verificar alinhamento
#    - block_01_alignment_overlay.jpg
#    - block_01_alignment_side_by_side.jpg

# 3. Ajustar offsets e gerar novas imagens
python scripts/adjust_block_alignment.py --block 1 --auto --offset-x -30 --offset-y 20 --no-interactive

# 4. Repetir passo 3 até alinhar corretamente

# 5. Salvar configuração final
python scripts/adjust_block_alignment.py --block 1 --auto --offset-x -30 --offset-y 20 --save

# 6. Executar correção (os offsets serão aplicados automaticamente)
```

## Interpretação dos Offsets

- **Offset X negativo**: Bolhas reais estão mais à esquerda que o esperado
- **Offset X positivo**: Bolhas reais estão mais à direita que o esperado
- **Offset Y negativo**: Bolhas reais estão mais acima que o esperado
- **Offset Y positivo**: Bolhas reais estão mais abaixo que o esperado

## Dicas

1. **Use o modo overlay** (Espaço) para ver melhor o alinhamento
2. **Ajuste a transparência** (+/-) para ver melhor as duas imagens
3. **Comece com ajustes grandes** (use múltiplas teclas) e depois refine
4. **Salve frequentemente** (S) para não perder o progresso

## Arquivos Gerados

- `block_01_alignment.json` - Configuração do bloco 1
- `block_02_alignment.json` - Configuração do bloco 2
- etc.

Esses arquivos devem estar na raiz do projeto (mesmo diretório onde você executa o script).
