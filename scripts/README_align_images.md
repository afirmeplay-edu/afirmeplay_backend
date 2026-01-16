# Script de Alinhamento de Imagens de Blocos

Este script permite alinhar e comparar visualmente as imagens de referência (geradas pelo sistema) com as imagens reais dos blocos escaneados, facilitando a análise de alinhamento e posicionamento das bolhas.

## Funcionalidades

- ✅ Alinha automaticamente as imagens usando a borda do bloco como referência
- ✅ Detecta bolhas em ambas as imagens usando HoughCircles
- ✅ Cria visualização lado a lado mostrando onde estão as bolhas
- ✅ Cria versão sobreposta (overlay) para comparação direta
- ✅ Calcula offsets médios entre bolhas correspondentes
- ✅ Busca automática de imagens no diretório `debug_corrections`

## Uso

### Opção 1: Busca Automática (Recomendado)

```bash
# Buscar automaticamente imagens do bloco 1
python scripts/align_block_images.py --block 1 --auto

# Buscar automaticamente qualquer bloco (pega as mais recentes)
python scripts/align_block_images.py --auto
```

### Opção 2: Especificar Imagens Manualmente

```bash
# Especificar caminhos completos
python scripts/align_block_images.py \
  --reference debug_corrections/20260116_115907_08_block_01_reference.jpg \
  --real debug_corrections/20260116_115907_05_block_01_roi.jpg \
  --output aligned_block_01.jpg
```

### Opção 3: Com Parâmetros Personalizados

```bash
# Ajustar raio esperado das bolhas
python scripts/align_block_images.py --block 1 --auto --bubble-radius 12

# Especificar diretório de debug diferente
python scripts/align_block_images.py --block 1 --auto --debug-dir meu_debug_dir
```

## Parâmetros

- `--reference, -r`: Caminho para imagem de referência (gerada pelo sistema)
- `--real, -i`: Caminho para imagem real do bloco escaneado
- `--auto, -a`: Buscar automaticamente imagens no diretório de debug
- `--block, -b`: Número do bloco para busca automática (1, 2, etc.)
- `--output, -o`: Caminho de saída (padrão: `aligned_comparison.jpg`)
- `--bubble-radius`: Raio esperado das bolhas em pixels (padrão: 10)
- `--debug-dir`: Diretório de debug (padrão: `debug_corrections`)

## Saída

O script gera duas imagens:

1. **`aligned_comparison.jpg`**: Imagem lado a lado mostrando:
   - Lado esquerdo: Imagem de referência com bolhas em **verde**
   - Lado direito: Imagem real com bolhas em **azul**
   - Contadores de bolhas detectadas

2. **`aligned_comparison_overlay.jpg`**: Imagem sobreposta (50% transparência) mostrando:
   - Imagem de referência e real sobrepostas
   - Bolhas da referência em **verde**
   - Bolhas da real em **azul**

## Exemplo de Saída no Console

```
============================================================
Script de Alinhamento de Imagens de Blocos
============================================================

🔍 Buscando imagens automaticamente no diretório 'debug_corrections'...
   ✅ Referência encontrada: debug_corrections/20260116_115907_08_block_01_reference.jpg
   ✅ Real encontrada: debug_corrections/20260116_115907_05_block_01_roi.jpg

📂 Carregando imagem de referência: ...
   Referência: (175, 287, 3)
   Real: (175, 312, 3)

🔧 Alinhando imagens...
   Borda ref: 287x175
   Borda real: 312x175
   Área interna ref: (171, 283)
   Área interna real: (171, 308)

🔍 Detectando bolhas (raio esperado: 10px)...
   Bolhas na referência: 9
   Bolhas na real: 9

📊 Analisando offsets...
   Bolha ref (45, 33) -> real (13, 53): offset=(-32, +20)
   ...

   📌 Offset médio: X=-32.0px, Y=+20.0px

🎨 Criando visualização...
✅ Imagem lado a lado salva: aligned_comparison.jpg
✅ Imagem sobreposta salva: aligned_comparison_overlay.jpg

✅ Concluído! Imagens salvas:
   - aligned_comparison.jpg
   - aligned_comparison_overlay.jpg
```

## Interpretação dos Resultados

- **Offset negativo em X**: Bolhas reais estão mais à esquerda que o esperado
- **Offset positivo em X**: Bolhas reais estão mais à direita que o esperado
- **Offset negativo em Y**: Bolhas reais estão mais acima que o esperado
- **Offset positivo em Y**: Bolhas reais estão mais abaixo que o esperado

Use esses offsets para ajustar o código de correção se necessário.
