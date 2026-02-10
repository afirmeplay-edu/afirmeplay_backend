# Script de Ajuste de Alinhamento do Grid Virtual

Este script permite ajustar manualmente a posição do grid virtual para alinhar corretamente com as bolhas reais detectadas nos blocos.

## Funcionalidade

O script ajusta os seguintes parâmetros do grid virtual:

- **LEFT_MARGIN_RATIO**: Distância do início do bloco até a primeira bolha (A)
- **TOP_PADDING_RATIO**: Padding superior do bloco (onde começa a primeira questão)
- **BUBBLE_SPACING_RATIO**: Espaçamento entre centros das bolhas (A, B, C, D)
- **LINE_HEIGHT**: Altura de linha entre questões (em pixels)

## Uso

### Modo Interativo

```bash
# Ajustar grid do bloco 1 visualmente
python scripts/adjust_grid_alignment.py --block 1 --real-filename 20260119_182714_166_04_block_01_real_only
```

### Modo Manual (via linha de comando)

```bash
# Ajustar ratios e salvar (line-height será calculado automaticamente)
python scripts/adjust_grid_alignment.py --block 1 --real-filename <nome> --left-margin 0.27 --top-padding 0.02 --bubble-spacing 0.14 --save

# Ajustar apenas top-padding (útil para corrigir alinhamento vertical)
python scripts/adjust_grid_alignment.py --block 3 --real-filename <nome> --load-config --top-padding 0.01 --save

# Especificar line-height manualmente se necessário
python scripts/adjust_grid_alignment.py --block 1 --real-filename <nome> --line-height 19 --top-padding 0.02 --save
```

### Carregar configuração existente e ajustar

```bash
python scripts/adjust_grid_alignment.py --block 1 --real-filename <nome> --load-config --left-margin 0.21 --save
```

## Controles (Modo Interativo)

- **a/d**: Ajustar LEFT_MARGIN_RATIO (-0.001 / +0.001)
- **A/D**: Ajustar LEFT_MARGIN_RATIO (-0.01 / +0.01) [Shift]
- **w/x**: Ajustar TOP_PADDING_RATIO (-0.001 / +0.001)
- **W/X**: Ajustar TOP_PADDING_RATIO (-0.01 / +0.01) [Shift]
- **e/r**: Ajustar BUBBLE_SPACING_RATIO (-0.001 / +0.001)
- **E/R**: Ajustar BUBBLE_SPACING_RATIO (-0.01 / +0.01) [Shift]
- **i/k**: Ajustar LINE_HEIGHT (-1 / +1)
- **Espaço**: Alternar exibição do grid
- **S**: Salvar configuração
- **Q**: Sair sem salvar

## Arquivo de Configuração

O script salva a configuração em:
```
app/services/cartao_resposta/block_XX_grid_alignment.json
```

Formato do arquivo:
```json
{
  "block_num": 1,
  "left_margin_ratio": 0.20,
  "top_padding_ratio": 0.06,
  "bubble_spacing_ratio": 0.15,
  "line_height": 19,
  "block_width_ref": 163,
  "block_height_ref": 507,
  "img_real_path": "..."
}
```

## Integração com o Sistema de Correção

O sistema de correção (`correction_n.py`) carrega automaticamente esses ratios quando disponíveis:

1. Busca o arquivo `block_XX_grid_alignment.json`
2. Usa os ratios salvos ao invés dos padrões
3. Aplica os valores para gerar o grid virtual

Isso permite que o grid seja ajustado uma vez e depois usado automaticamente em todas as correções.

## Exemplo de Uso Completo

1. Executar uma correção para gerar imagens de debug:
   ```bash
   # Isso gera imagens em debug_corrections/
   ```

2. Ajustar o grid do bloco 1 (line-height será calculado automaticamente):
   ```bash
   python scripts/adjust_grid_alignment.py --block 1 --real-filename 20260119_182714_166_04_block_01_real_only --left-margin 0.27 --top-padding 0.02 --bubble-spacing 0.14 --save
   ```

3. Se o eixo Y ficar muito alto ou baixo, ajustar apenas o top-padding:
   ```bash
   # Para subir o grid (valores negativos ou menores)
   python scripts/adjust_grid_alignment.py --block 3 --real-filename <nome> --load-config --top-padding -0.01 --save
   
   # Para descer o grid (valores positivos maiores)
   python scripts/adjust_grid_alignment.py --block 3 --real-filename <nome> --load-config --top-padding 0.03 --save
   ```

4. Repetir para blocos 2, 3 e 4 com os mesmos valores (ou ajustar individualmente)

5. Próximas correções usarão automaticamente os ratios ajustados

## Dica Importante

- O `line-height` é calculado automaticamente baseado nas bolhas detectadas
- Se precisar ajustar manualmente o `top-padding`, use valores pequenos (ex: -0.01, 0.01, 0.02)
- Valores negativos de `top-padding` movem o grid para cima
- Valores positivos maiores movem o grid para baixo
