# -*- coding: utf-8 -*-
"""Generate scripts/organizacao_matematica_novo.json from build_matematica_json data."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_matematica_json import (
    HABILIDADES_POR_SERIE,
    DESCRITORES_1_5,
)

# User-specified D6-D12 for Group 1 (1º-5º)
D6_D12_USER = [
    {"codigo": "D6", "descricao": "Estimar a medida de grandezas utilizando unidades de medida convencionais ou não."},
    {"codigo": "D7", "descricao": "Resolver problemas significativos utilizando unidades de medida padronizadas como km/m/cm/mm, kg/g/mg, l/ml."},
    {"codigo": "D8", "descricao": "Estabelecer relações entre unidades de medida de tempo."},
    {"codigo": "D9", "descricao": "Estabelecer relações entre o horário de início e término e /ou o intervalo da duração de um evento ou acontecimento."},
    {"codigo": "D10", "descricao": "Num problema, estabelecer trocas entre cédulas e moedas do sistema monetário brasileiro, em função de seus valores."},
    {"codigo": "D11", "descricao": "Resolver problema envolvendo o cálculo do perímetro de figuras planas, desenhadas em malhas quadriculadas."},
    {"codigo": "D12", "descricao": "Resolver problema envolvendo o cálculo ou estimativa de áreas de figuras planas, desenhadas em malhas quadriculadas."},
]

# Build D1-D28 for Group 1: D1-D5, D6-D12 (user), D13-D28 from DESCRITORES_1_5
def build_d1_d28():
    out = []
    for d in DESCRITORES_1_5:
        if d["codigo"] in ("D1", "D2", "D3", "D4", "D5"):
            out.append(d)
    out.extend(D6_D12_USER)
    for d in DESCRITORES_1_5:
        if d["codigo"] in ("D13", "D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27", "D28"):
            out.append(d)
    return out

# EF01MA06 user: "adição e subtração"
EF01MA_GROUP1 = list(HABILIDADES_POR_SERIE["1º Ano"])
for i, h in enumerate(EF01MA_GROUP1):
    if h["codigo"] == "EF01MA06":
        EF01MA_GROUP1[i] = {"codigo": "EF01MA06", "descricao": "Construir fatos básicos da adição e subtração e utilizá-los em procedimentos de cálculo para resolver problemas."}
        break

# 2º Ano extras (2N1.1, 2N1.2, ... 2E2.1) - proper Portuguese
EXTRAS_2ANO = [
    {"codigo": "2N1.1", "descricao": "Reconhecer o que os números naturais indicam em diferentes situações: quantidade, ordem, medida ou código de identificação."},
    {"codigo": "2N1.2", "descricao": "Identificar a posição ordinal de um objeto ou termo em uma sequência (1º, 2º etc.)."},
    {"codigo": "2N1.3", "descricao": "Escrever números naturais de até 3 ordens em sua representação por algarismos ou em língua materna OU associar o registro numérico de números naturais de até 3 ordens ao registro em língua materna."},
    {"codigo": "2N1.4", "descricao": "Comparar OU ordenar quantidades de objetos (até 2 ordens)."},
    {"codigo": "2N1.5", "descricao": "Comparar OU ordenar números naturais de até 3 ordens com ou sem suporte da reta numérica."},
    {"codigo": "2N1.6", "descricao": "Identificar a ordem ocupada por um algarismo OU seu valor posicional (ou valor relativo) em um número natural de até 3 ordens."},
    {"codigo": "2N1.7", "descricao": "Calcular o resultado de adições ou subtrações, envolvendo números naturais de até 3 ordens."},
    {"codigo": "2N1.8", "descricao": "Compor OU decompor números naturais de até 3 ordens por meio de diferentes adições."},
    {"codigo": "2N2.1", "descricao": "Resolver problemas de adição ou de subtração, envolvendo números naturais de até 3 ordens, com os significados de juntar, acrescentar, separar ou retirar."},
    {"codigo": "2N2.2", "descricao": "Resolver problemas de multiplicação ou de divisão (por 2, 3, 4 ou 5), envolvendo números naturais, com os significados de formação de grupos iguais ou proporcionalidade (incluindo dobro, metade, triplo ou terça parte)."},
    {"codigo": "2N2.3", "descricao": "Analisar argumentações sobre a resolução de problemas de adição, subtração, multiplicação ou divisão envolvendo números naturais."},
    {"codigo": "2A1.1", "descricao": "Identificar a classificação OU classificar objetos ou representações por figuras, por meio de atributos, tais como cor, forma e medida."},
    {"codigo": "2A1.2", "descricao": "Inferir OU descrever atributos ou propriedades comuns que os elementos que constituem uma sequência de números naturais apresentam."},
    {"codigo": "2A1.3", "descricao": "Inferir o padrão ou a regularidade de uma sequência de números naturais ordenados, de objetos ou de figuras."},
    {"codigo": "2A1.4", "descricao": "Inferir os elementos ausentes em uma sequência de números naturais ordenados, de objetos ou de figuras."},
    {"codigo": "2G1.1", "descricao": "Identificar a localização OU a descrição/esboço do deslocamento de pessoas e/ou de objetos em representações bidimensionais (mapas, croquis, etc.)."},
    {"codigo": "2G1.2", "descricao": "Reconhecer/nomear figuras geométricas espaciais (cubo, bloco retangular, pirâmide, cone, cilindro e esfera), relacionando-as com objetos do mundo físico."},
    {"codigo": "2G1.3", "descricao": "Reconhecer/nomear figuras geométricas planas (círculo, quadrado, retângulo e triângulo)."},
    {"codigo": "2G2.1", "descricao": "Descrever OU esboçar o deslocamento de pessoas e/ou objetos em representações bidimensionais (mapas, croquis etc.) ou plantas de ambientes, de acordo com condições dadas."},
    {"codigo": "2M1.1", "descricao": "Comparar comprimentos, capacidades ou massas OU ordenar imagens de objetos com base na comparação visual de seus comprimentos, capacidades ou massas."},
    {"codigo": "2M1.2", "descricao": "Estimar/inferir medida de comprimento, capacidade ou massa de objetos, utilizando unidades de medida convencionais ou não OU medir comprimento, capacidade ou massa de objetos."},
    {"codigo": "2M1.3", "descricao": "Identificar a medida do comprimento, da capacidade ou da massa de objetos, dada a imagem de um instrumento de medida."},
    {"codigo": "2M1.4", "descricao": "Reconhecer unidades de medida e/ou instrumentos utilizados para medir comprimento, tempo, massa ou capacidade."},
    {"codigo": "2M1.5", "descricao": "Identificar sequência de acontecimentos relativos a um dia."},
    {"codigo": "2M1.6", "descricao": "Identificar datas, dias da semana ou meses do ano em calendário OU escrever uma data, apresentando o dia, o mês e o ano."},
    {"codigo": "2M1.7", "descricao": "Relacionar valores de moedas e/ou cédulas do sistema monetário brasileiro, com base nas imagens desses objetos."},
    {"codigo": "2M2.1", "descricao": "Determinar a data de início, a data de término ou a duração de um acontecimento entre duas datas."},
    {"codigo": "2M2.2", "descricao": "Determinar o horário de início, o horário de término ou a duração de um acontecimento."},
    {"codigo": "2M2.3", "descricao": "Resolver problemas que envolvam moedas e/ou cédulas do sistema monetário brasileiro."},
    {"codigo": "2E1.1", "descricao": "Classificar resultados de eventos cotidianos aleatórios como \"pouco prováveis\", \"muito prováveis\", \"certos\" ou \"impossíveis\"."},
    {"codigo": "2E1.2", "descricao": "Ler/identificar OU comparar dados estatísticos ou informações expressas em tabelas (simples ou de dupla entrada)."},
    {"codigo": "2E1.3", "descricao": "Ler/identificar OU comparar dados estatísticos expressos em gráficos (barras simples, colunas simples ou pictóricos)."},
    {"codigo": "2E2.1", "descricao": "Representar os dados de uma pesquisa estatística ou de um levantamento em listas, tabelas (simples ou de dupla entrada) ou gráficos (barras simples, colunas simples ou pictóricos)."},
]

# 5º Ano extras (5N, 5G, 5M, 5E)
EXTRAS_5ANO = [
    {"codigo": "5N1.1", "descricao": "Identificar número racional (naturais até 6 ordens, representação fracionária ou decimal finita até 6 ordens dos milésimos) em sua representação por algarismos ou em língua materna OU associar o registro numérico ao registro em língua materna."},
    {"codigo": "5N1.2", "descricao": "Identificar a ordem ocupada por um algarismo OU seu valor posicional (valor relativo) em um número natural até 6 ordens."},
    {"codigo": "5N1.3", "descricao": "Comparar OU ordenar número racional (naturais até 6 ordens, representação fracionária ou decimal finita até 6 ordens dos milésimos) com ou sem suporte da reta numérica."},
    {"codigo": "5N1.4", "descricao": "Compor OU decompor número natural de até 6 ordens na forma aditiva, ou aditiva/multiplicativa, ou com adições e multiplicações."},
    {"codigo": "5N1.5", "descricao": "Calcular o resultado de adições ou subtrações de números naturais de até 6 ordens."},
    {"codigo": "5N1.6", "descricao": "Calcular o resultado de multiplicações ou divisões envolvendo números naturais de até 6 ordens."},
    {"codigo": "5N1.7", "descricao": "Associar o quociente de uma divisão com resto zero de um número natural de até 6 ordens por 2, 3, 4, 5 ou 10 à ideia de metade, terça, quarta, quinta e décima partes."},
    {"codigo": "5N1.8", "descricao": "Representar frações menores ou maiores do que a unidade (por meio de representações pictóricas) OU associar frações a representações pictóricas."},
    {"codigo": "5N1.9", "descricao": "Identificar frações equivalentes."},
    {"codigo": "5N2.1", "descricao": "Resolver problemas de adição ou de subtração, envolvendo números naturais de até 6 ordens, com os significados de juntar, acrescentar, separar, retirar, comparar ou completar."},
    {"codigo": "5N2.2", "descricao": "Resolver problemas de multiplicação ou de divisão, envolvendo números naturais de até 6 ordens, com os significados de adição de parcelas iguais, configuração retangular e medida."},
    {"codigo": "5N2.3", "descricao": "Resolver problemas de adição ou de subtração, envolvendo números racionais representados na sua representação decimal finita até 6 ordens dos milésimos, com os significados de juntar, acrescentar, separar, retirar, comparar ou completar."},
    {"codigo": "5N2.4", "descricao": "Resolver problemas de multiplicação ou de divisão, envolvendo números racionais apenas na sua representação decimal finita até 6 ordens dos milésimos com os significados de formação de grupos (incluindo repartição equitativa de medida), proporcionalidade ou disposição retangular."},
    {"codigo": "5N2.5", "descricao": "Resolver problemas que envolvam fração como resultado de uma divisão (quociente)."},
    {"codigo": "5N2.6", "descricao": "Resolver problemas simples de contagem (combinatória)."},
    {"codigo": "5N2.7", "descricao": "Resolver problemas que envolvam 10%, 25%, 50% ou 100%, associando essas representações, respectivamente, à décima parte, quarta parte, metade, três quartos e um inteiro."},
    {"codigo": "5N2.8", "descricao": "Inferir OU descrever atributos ou propriedades comuns que os elementos que constituem uma sequência recursiva de números naturais apresentam."},
    {"codigo": "5N2.9", "descricao": "Inferir o padrão ou regularidade de uma sequência numérica de números ordinais, objetos ou figuras."},
    {"codigo": "5G1.1", "descricao": "Identificar localização e movimentação (deslocamento) de objetos em relação a diferentes representações bidimensionais (mapas, croquis etc.)."},
    {"codigo": "5G1.2", "descricao": "Interpretar OU descrever localização e movimentação de objetos e figuras geométricas no plano cartesiano (1º quadrante), indicando mudanças de direção, sentido ou giros."},
    {"codigo": "5G1.3", "descricao": "Reconhecer/nomear figuras geométricas planas (triângulos, quadriláteros, círculos) e espaciais (prismas, pirâmides, cilindros, cones, esferas)."},
    {"codigo": "5G1.4", "descricao": "Reconhecer/nomear, contar OU comparar elementos de figuras geométricas espaciais (vértice, aresta, face, base de prismas, pirâmides, cilindros, cones ou esferas)."},
    {"codigo": "5G1.5", "descricao": "Relacionar figuras geométricas espaciais (prismas retos, pirâmides retas, cilindros retos ou cones retos) e suas planificações."},
    {"codigo": "5G1.6", "descricao": "Reconhecer/nomear figuras geométricas planas (polígonos, circunferência e círculos)."},
    {"codigo": "5G1.7", "descricao": "Reconhecer/nomear, contar OU comparar elementos de figuras geométricas planas (vértice, lado, diagonal, base)."},
    {"codigo": "5G1.8", "descricao": "Reconhecer figuras geométricas congruentes ou identificar simetria de reflexão em figuras ou em pares de figuras geométricas planas."},
    {"codigo": "5G2.1", "descricao": "Resolver OU descrever o deslocamento de pessoas e/ou de objetos em representações bidimensionais (mapas, croquis etc.) em situações de ampliação ou de redução em malhas quadriculadas."},
    {"codigo": "5G2.2", "descricao": "Descrever o deslocamento de pessoas e/ou de objetos em representações bidimensionais (mapas, croquis etc.) ou plantas de ambientes, de acordo com condições dadas."},
    {"codigo": "5G2.3", "descricao": "Construir/desenhar figuras geométricas planas ou espaciais que satisfaçam condições dadas."},
    {"codigo": "5M1.1", "descricao": "Reconhecer a unidade de medida ou o instrumento mais apropriado para medições de comprimento, área, massa, tempo, capacidade ou temperatura."},
    {"codigo": "5M1.2", "descricao": "Estimar/Inferir medida de comprimento, capacidade ou massa de objetos, utilizando unidades de medida convencionais ou não OU medir comprimento, capacidade ou massa de objetos."},
    {"codigo": "5M1.3", "descricao": "Medir OU comparar perímetro ou área de figuras planas desenhadas em malha quadriculada."},
    {"codigo": "5M1.4", "descricao": "Identificar volume ou capacidade de sólidos em diferentes níveis ou o instrumento de medição de comprimento de cubos."},
    {"codigo": "5M1.5", "descricao": "Identificar medidas relativas a dinheiro com uso de gráficos, outros formatos e dígitos."},
    {"codigo": "5M1.6", "descricao": "Relacionar valores de medidas do sistema monetário brasileiro, com base nas imagens desses objetos."},
    {"codigo": "5M1.7", "descricao": "Explicar que o resultado de uma medida depende da unidade de medida utilizada."},
    {"codigo": "5M2.1", "descricao": "Resolver problemas que envolvam medidas de grandezas (comprimento, massa, tempo e capacidade) em que haja conversões entre as unidades mais usuais."},
    {"codigo": "5M2.2", "descricao": "Resolver problemas que envolvam perímetro de figuras planas."},
    {"codigo": "5M2.3", "descricao": "Resolver problemas que envolvam área de figuras planas."},
    {"codigo": "5M2.4", "descricao": "Determinar a hora de início, a hora de término ou a duração de um acontecimento."},
    {"codigo": "5M2.5", "descricao": "Resolver problemas que envolvam o sistema monetário brasileiro."},
    {"codigo": "5E1.1", "descricao": "Identificar, entre eventos aleatórios, aqueles que têm menores, maiores ou iguais chances de ocorrência, sem utilizar frações."},
    {"codigo": "5E1.2", "descricao": "Ler/Identificar OU comparar dados estatísticos expressos em tabelas (simples ou de dupla entrada)."},
    {"codigo": "5E1.3", "descricao": "Ler/Identificar OU comparar dados estatísticos expressos em gráficos (barras simples ou agrupadas, colunas simples ou agrupadas, pictóricos ou de linhas)."},
    {"codigo": "5E1.4", "descricao": "Identificar os indivíduos (universo ou população-alvo da pesquisa), as variáveis ou os tipos de variáveis (quantitativas ou categóricas) em um conjunto de dados."},
    {"codigo": "5E1.5", "descricao": "Representar OU associar os dados de uma pesquisa ou de um levantamento em listas, tabelas (simples ou de dupla entrada) ou gráficos (barras simples ou agrupadas, colunas simples ou agrupadas, pictóricos ou de linhas)."},
    {"codigo": "5E1.6", "descricao": "Inferir a tendência/variação de uma pesquisa ou de um levantamento em listas, tabelas (simples ou de dupla entrada) ou gráficos (barras simples ou agrupadas, colunas simples ou agrupadas, pictóricos ou de linhas) com os dados dessa pesquisa."},
    {"codigo": "5E2.1", "descricao": "Resolver problemas que envolvam dados apresentados em tabelas (simples ou de dupla entrada) ou gráficos (barras simples ou agrupadas, colunas simples ou agrupadas, pictóricos ou de linhas)."},
    {"codigo": "5E2.2", "descricao": "Argumentar OU analisar argumentações/conclusões com base nos dados apresentados em tabelas (simples ou de dupla entrada) ou gráficos (barras simples ou agrupadas, colunas simples ou agrupadas, pictóricos ou de linhas)."},
    {"codigo": "5E2.3", "descricao": "Determinar a probabilidade de ocorrência de um resultado em eventos aleatórios, quando todos os resultados possíveis têm a mesma chance de ocorrer (equiprováveis)."},
]

def main():
    grupo1_habilidades = EF01MA_GROUP1 + build_d1_d28()

    grupo2_habilidades = list(HABILIDADES_POR_SERIE["2º Ano"]) + EXTRAS_2ANO

    grupo3_habilidades = list(HABILIDADES_POR_SERIE["3º Ano"])

    grupo4_habilidades = list(HABILIDADES_POR_SERIE["4º Ano"])

    # EF04MA07 and EF04MA24 user descriptions
    for i, h in enumerate(grupo4_habilidades):
        if h["codigo"] == "EF04MA07":
            grupo4_habilidades[i] = {"codigo": "EF04MA07", "descricao": "Resolver e elaborar problemas de divisão cujo divisor tenha no máximo dois algarismos, envolvendo os significados de repartição equitativa e de medida, utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos."}
        elif h["codigo"] == "EF04MA24":
            grupo4_habilidades[i] = {"codigo": "EF04MA24", "descricao": "Registrar as temperaturas máxima e mínima diárias, em locais do seu cotidiano, e elaborar gráficos de colunas com as variações diárias da temperatura, utilizando, inclusive, planilhas eletrônicas."}

    habilidades_5ano = list(HABILIDADES_POR_SERIE["5º Ano"]) + EXTRAS_5ANO

    out = {
        "organizacao_habilidades_matematica": {
            "habilidades_compartilhadas": [
                {
                    "series_aplicaveis": "1º, 2º, 3º, 4º e 5º Ano",
                    "habilidades": grupo1_habilidades
                },
                {
                    "series_aplicaveis": "2º, 3º, 4º e 5º Ano",
                    "habilidades": grupo2_habilidades
                },
                {
                    "series_aplicaveis": "3º, 4º e 5º Ano",
                    "habilidades": grupo3_habilidades
                },
                {
                    "series_aplicaveis": "4º e 5º Ano",
                    "habilidades": grupo4_habilidades
                }
            ],
            "habilidades_unicas_por_serie": [
                {
                    "serie": "5º Ano",
                    "habilidades": habilidades_5ano
                }
            ]
        }
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "organizacao_matematica_novo.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("OK:", path)


if __name__ == "__main__":
    main()
