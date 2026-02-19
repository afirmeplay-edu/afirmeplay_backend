"""
Gera habilidades_matematica_data.json no formato esperado pelo update script.
Execute uma vez: python scripts/build_matematica_json.py
"""
import json
import os

MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
GRADE_IDS = {
    "1º Ano": "391ed6e8-fc45-46f8-8e4c-065005d2329f",
    "2º Ano": "74821122-e632-4301-b6f5-42b92b802a55",
    "3º Ano": "ea1ed64b-c9f5-4156-93b2-497ecf9e0d84",
    "4º Ano": "b8cdea4d-22fe-4647-a9f3-c575eb82c514",
    "5º Ano": "f5688bb2-9624-487f-ab1f-40b191c96b76",
    "6º Ano": "75bea034-3427-4e98-896d-23493d36a84e",
    "7º Ano": "4128c187-5e33-4ff9-a96d-e7eb9ddbe04e",
    "8º Ano": "b6760b9b-2758-4d14-a650-c3a30c0aeb3b",
    "9º Ano": "3c68a0b5-9613-469e-8376-6fb678c60363",
}

# Bloco A: Descritores 6º ao 9º Ano (compartilhados)
DESCRITORES_6_9 = [
    {"codigo": "D1", "descricao": "Identificar a localização/movimentação de objeto, em mapas, croquis e outras representações gráficas."},
    {"codigo": "D2", "descricao": "Identificar propriedades comuns e diferenças entre figuras bidimensionais e tridimensionais, relacionando-as com suas planificações."},
    {"codigo": "D3", "descricao": "Identificar propriedades de triângulos pela comparação de medidas de lados e ângulos."},
    {"codigo": "D4", "descricao": "Identificar relação entre quadriláteros, por meio de suas propriedades."},
    {"codigo": "D5", "descricao": "Reconhecer a conservação ou modificação de medidas dos lados, do perímetro, da área em ampliação e/ou redução de figuras poligonais usando malhas quadriculadas."},
    {"codigo": "D6", "descricao": "Reconhecer ângulos como mudança de direção ou giros, identificando ângulos retos e não retos."},
    {"codigo": "D7", "descricao": "Reconhecer que as imagens de uma figura construída por uma transformação homotética são semelhantes, identificando propriedades e/ou medidas que se modificam ou não se alteram."},
    {"codigo": "D8", "descricao": "Resolver problema utilizando a propriedade dos polígonos (soma de seus ângulos internos, número de diagonais, cálculo da medida de cada ângulo interno nos polígonos regulares)."},
    {"codigo": "D9", "descricao": "Interpretar informações apresentadas por meio de coordenadas cartesianas."},
    {"codigo": "D10", "descricao": "Utilizar relações métricas do triângulo retângulo para resolver problemas significativos."},
    {"codigo": "D11", "descricao": "Reconhecer círculo/circunferência, seus elementos e algumas de suas relações."},
    {"codigo": "D12", "descricao": "Resolver problema envolvendo o cálculo de perímetro de figuras planas."},
    {"codigo": "D13", "descricao": "Resolver problema envolvendo o cálculo de área de figuras planas."},
    {"codigo": "D14", "descricao": "Resolver problema envolvendo noções de volume."},
    {"codigo": "D15", "descricao": "Resolver problema envolvendo relações entre diferentes unidades de medida."},
    {"codigo": "D16", "descricao": "Identificar a localização de números inteiros na reta numérica."},
    {"codigo": "D17", "descricao": "Identificar a localização de números racionais na reta numérica."},
    {"codigo": "D18", "descricao": "Efetuar cálculos com números inteiros envolvendo as operações (adição, subtração, multiplicação, divisão e potenciação)."},
    {"codigo": "D19", "descricao": "Resolver problema com números naturais envolvendo diferentes significados das operações (adição, subtração, multiplicação, divisão e potenciação)."},
    {"codigo": "D20", "descricao": "Resolver problema com números inteiros envolvendo as operações (adição, subtração, multiplicação, divisão e potenciação)."},
    {"codigo": "D21", "descricao": "Reconhecer as diferentes representações de um número racional."},
    {"codigo": "D22", "descricao": "Identificar fração como representação que pode estar associada a diferentes significados."},
    {"codigo": "D23", "descricao": "Identificar frações equivalentes."},
    {"codigo": "D24", "descricao": "Reconhecer as representações decimais dos números racionais como uma extensão do sistema de numeração decimal identificando a existência de \"ordens\" como décimos, centésimos e milésimos."},
    {"codigo": "D25", "descricao": "Efetuar cálculos que envolvam operações com números racionais (adição, subtração, multiplicação, divisão e potenciação)."},
    {"codigo": "D26", "descricao": "Resolver problema com números racionais que envolvam as operações (adição, subtração, multiplicação, divisão e potenciação)."},
    {"codigo": "D27", "descricao": "Efetuar cálculos simples com valores aproximados de radicais."},
    {"codigo": "D28", "descricao": "Resolver problema que envolva porcentagem."},
    {"codigo": "D29", "descricao": "Resolver problema que envolva variações proporcionais, diretas ou inversas entre grandezas."},
    {"codigo": "D30", "descricao": "Calcular o valor numérico de uma expressão algébrica."},
    {"codigo": "D31", "descricao": "Resolver problema que envolva equação de segundo grau."},
    {"codigo": "D32", "descricao": "Identificar a expressão algébrica que expressa uma regularidade observada em seqüências de números ou figuras (padrões)."},
    {"codigo": "D33", "descricao": "Identificar uma equação ou uma inequação de primeiro grau que expressa um problema."},
    {"codigo": "D34", "descricao": "Identificar um sistema de equações do primeiro grau que expressa um problema."},
    {"codigo": "D35", "descricao": "Identificar a relação entre as representações algébrica e geométrica de um sistema de equações de primeiro grau."},
    {"codigo": "D36", "descricao": "Resolver problemas envolvendo informações apresentadas em tabelas e/ou gráficos."},
    {"codigo": "D37", "descricao": "Associar informações apresentadas em listas e/ou tabelas simples aos gráficos que as representam e vice-versa."},
]

# Bloco B: Descritores 1º ao 5º Ano (compartilhados) - com prefixo EF15_
DESCRITORES_1_5 = [
    {"codigo": "D1", "descricao": "Identificar a localização /movimentação de objeto em mapas, croquis e outras representações gráficas."},
    {"codigo": "D2", "descricao": "Identificar propriedades comuns e diferenças entre poliedros e corpos redondos, relacionando figuras tridimensionais com suas planificações."},
    {"codigo": "D3", "descricao": "Identificar propriedades comuns e diferenças entre figuras bidimensionais pelo número de lados, pelos tipos de ângulos."},
    {"codigo": "D4", "descricao": "Identificar quadriláteros observando as relações entre seus lados (paralelos, congruentes, perpendiculares)."},
    {"codigo": "D5", "descricao": "Reconhecer a conservação ou modificação de medidas dos lados, do perímetro, da área em ampliação e /ou redução de figuras poligonais usando malhas quadriculadas."},
    {"codigo": "D13", "descricao": "Reconhecer e utilizar características do sistema de numeração decimal, tais como agrupamentos e trocas na base 10 e princípio do valor posicional."},
    {"codigo": "D14", "descricao": "Identificar a localização de números naturais na reta numérica."},
    {"codigo": "D15", "descricao": "Reconhecer a decomposição de números naturais nas suas diversas ordens."},
    {"codigo": "D16", "descricao": "Reconhecer a composição e a decomposição de números naturais em sua forma polinomial."},
    {"codigo": "D17", "descricao": "Calcular o resultado de uma adição ou subtração de números naturais."},
    {"codigo": "D18", "descricao": "Calcular o resultado de uma multiplicação ou divisão de números naturais."},
    {"codigo": "D19", "descricao": "Resolver problema com números naturais, envolvendo diferentes significados da adição ou subtração: juntar, alteração de um estado inicial (positiva ou negativa), comparação e mais de uma transformação (positiva ou negativa)."},
    {"codigo": "D20", "descricao": "Resolver problema com números naturais, envolvendo diferentes significados da multiplicação ou divisão: multiplicação comparativa, idéia de proporcionalidade, configuração retangular e combinatória."},
    {"codigo": "D21", "descricao": "Identificar diferentes representações de um mesmo número racional."},
    {"codigo": "D22", "descricao": "Identificar a localização de números racionais representados na forma decimal na reta numérica."},
    {"codigo": "D23", "descricao": "Resolver problema utilizando a escrita decimal de cédulas e moedas do sistema monetário brasileiro."},
    {"codigo": "D24", "descricao": "Identificar fração como representação que pode estar associada a diferentes significados."},
    {"codigo": "D25", "descricao": "Resolver problema com números racionais expressos na forma decimal envolvendo diferentes significados da adição ou subtração."},
    {"codigo": "D26", "descricao": "Resolver problema envolvendo noções de porcentagem (25%, 50%, 100%)."},
    {"codigo": "D27", "descricao": "Ler informações e dados apresentados em tabelas."},
    {"codigo": "D28", "descricao": "Ler informações e dados apresentados em gráficos (particularmente em gráficos de colunas)."},
]

# Bloco C: Habilidades por série (1º a 5º Ano)
HABILIDADES_POR_SERIE = {
    "1º Ano": [
        {"codigo": "EF01MA01", "descricao": "Utilizar números naturais como indicador de quantidade ou de ordem em diferentes situações cotidianas e reconhecer situações em que os números não indicam contagem nem ordem, mas sim código de identificação."},
        {"codigo": "EF01MA02", "descricao": "Contar de maneira exata ou aproximada, utilizando diferentes estratégias como o pareamento e outros agrupamentos."},
        {"codigo": "EF01MA03", "descricao": "Estimar e comparar quantidades de objetos de dois conjuntos (em torno de 20 elementos), por estimativa e/ou por correspondência (um a um, dois a dois) para indicar \"tem mais\", \"tem menos\" ou \"tem a mesma quantidade\"."},
        {"codigo": "EF01MA04", "descricao": "Contar a quantidade de objetos de coleções até 100 unidades e apresentar o resultado por registros verbais e simbólicos, em situações de seu interesse, como jogos, brincadeiras, materiais da sala de aula, entre outros."},
        {"codigo": "EF01MA05", "descricao": "Comparar números naturais de até duas ordens em situações cotidianas, com e sem suporte da reta numérica."},
        {"codigo": "EF01MA06", "descricao": "Construir fatos básicos da adição e utilizá-los em procedimentos de cálculo para resolver problemas."},
        {"codigo": "EF01MA07", "descricao": "Compor e decompor número de até duas ordens, por meio de diferentes adições, com o suporte de material manipulável, contribuindo para a compreensão de características do sistema de numeração decimal e o desenvolvimento de estratégias de cálculo."},
        {"codigo": "EF01MA08", "descricao": "Resolver e elaborar problemas de adição e de subtração, envolvendo números de até dois algarismos, com os significados de juntar, acrescentar, separar e retirar, com o suporte de imagens e/ou material manipulável, utilizando estratégias e formas de registro pessoais."},
        {"codigo": "EF01MA09", "descricao": "Organizar e ordenar objetos familiares ou representações por figuras, por meio de atributos, tais como cor, forma e medida."},
        {"codigo": "EF01MA10", "descricao": "Descrever, após o reconhecimento e a explicitação de um padrão (ou regularidade), os elementos ausentes em sequências recursivas de números naturais, objetos ou figuras."},
        {"codigo": "EF01MA11", "descricao": "Descrever a localização de pessoas e de objetos no espaço em relação à sua própria posição, utilizando termos como à direita, à esquerda, em frente, atrás."},
        {"codigo": "EF01MA12", "descricao": "Descrever a localização de pessoas e de objetos no espaço segundo um dado ponto de referência, compreendendo que, para a utilização de termos que se referem à posição, como direita, esquerda, em cima, em baixo, é necessário explicitar-se o referencial."},
        {"codigo": "EF01MA13", "descricao": "Relacionar figuras geométricas espaciais (cones, cilindros, esferas e blocos retangulares) a objetos familiares do mundo físico."},
        {"codigo": "EF01MA14", "descricao": "Identificar e nomear figuras planas (círculo, quadrado, retângulo e triângulo) em desenhos, jogos e em diferentes representações artísticas e desenhos apresentados em diferentes disposições ou em sólidos geométricos."},
        {"codigo": "EF01MA15", "descricao": "Comparar comprimentos, capacidades ou massas, utilizando termos como mais alto, mais baixo, mais comprido, mais curto, mais grosso, mais fino, mais largo, mais pesado, mais leve, cabe mais, cabe menos, entre outros, para ordenar objetos de uso cotidiano."},
        {"codigo": "EF01MA16", "descricao": "Relatar em linguagem verbal ou não verbal sequência de acontecimentos relativos a um dia, utilizando, quando possível, os horários dos eventos."},
        {"codigo": "EF01MA17", "descricao": "Reconhecer e relacionar períodos do dia, dias da semana e meses do ano, utilizando calendário, quando necessário."},
        {"codigo": "EF01MA18", "descricao": "Produzir a escrita de uma data, apresentando o dia, o mês e o ano, e indicar o dia da semana de uma data, consultando calendários."},
        {"codigo": "EF01MA19", "descricao": "Reconhecer e relacionar valores de moedas e cédulas do sistema monetário brasileiro para resolver situações simples do cotidiano do estudante."},
        {"codigo": "EF01MA20", "descricao": "Classificar eventos envolvendo o acaso, tais como \"acontecerá com certeza\", \"talvez aconteça\" e \"é impossível acontecer\", em situações do cotidiano."},
        {"codigo": "EF01MA21", "descricao": "Ler dados expressos em tabelas e em gráficos de colunas simples."},
        {"codigo": "EF01MA22", "descricao": "Realizar pesquisa, envolvendo até duas variáveis categóricas de seu interesse e universo de até 30 elementos, e organizar dados por meio de representações pessoais."},
    ],
    "2º Ano": [
        {"codigo": "EF02MA01", "descricao": "Comparar e ordenar números naturais (até a ordem de centenas) pela compreensão de características do sistema de numeração decimal (valor posicional e função do zero)."},
        {"codigo": "EF02MA02", "descricao": "Fazer estimativas por meio de estratégias diversas a respeito da quantidade de objetos de coleções e registrar o resultado da contagem desses objetos (até 1000 unidades)."},
        {"codigo": "EF02MA03", "descricao": "Comparar quantidades de objetos de dois conjuntos, por estimativa e/ou por correspondência (um a um, dois a dois, entre outros), para indicar \"tem mais\", \"tem menos\" ou \"tem a mesma quantidade\", indicando, quando for o caso, quantos a mais e quantos a menos."},
        {"codigo": "EF02MA04", "descricao": "Compor e decompor números naturais de até três ordens, com suporte de material manipulável, por meio de diferentes adições."},
        {"codigo": "EF02MA05", "descricao": "Construir fatos básicos da adição e subtração e utilizá-los no cálculo mental ou escrito."},
        {"codigo": "EF02MA06", "descricao": "Resolver e elaborar problemas de adição e de subtração, envolvendo números de até três ordens, com os significados de juntar, acrescentar, separar, retirar, utilizando estratégias pessoais ou convencionais."},
        {"codigo": "EF02MA07", "descricao": "Resolver e elaborar problemas de multiplicação (por 2, 3, 4 e 5) com a ideia de adição de parcelas iguais por meio de estratégias e formas de registro pessoais, utilizando ou não suporte de imagens e/ou material manipulável."},
        {"codigo": "EF02MA08", "descricao": "Resolver e elaborar problemas envolvendo dobro, metade, triplo e terça parte, com o suporte de imagens ou material manipulável, utilizando estratégias pessoais."},
        {"codigo": "EF02MA09", "descricao": "Construir sequências de números naturais em ordem crescente ou decrescente a partir de um número qualquer, utilizando uma regularidade estabelecida."},
        {"codigo": "EF02MA10", "descricao": "Descrever um padrão (ou regularidade) de sequências repetitivas e de sequências recursivas, por meio de palavras, símbolos ou desenhos."},
        {"codigo": "EF02MA11", "descricao": "Descrever os elementos ausentes em sequências repetitivas e em sequências recursivas de números naturais, objetos ou figuras."},
        {"codigo": "EF02MA12", "descricao": "Identificar e registrar, em linguagem verbal ou não verbal, a localização e os deslocamentos de pessoas e de objetos no espaço, considerando mais de um ponto de referência, e indicar as mudanças de direção e de sentido."},
        {"codigo": "EF02MA13", "descricao": "Esboçar roteiros a ser seguidos ou plantas de espaços familiares, considerando relações de direção e de sentido, e de tamanho."},
        {"codigo": "EF02MA14", "descricao": "Reconhecer, nomear e comparar figuras geométricas espaciais (cubo, bloco retangular, pirâmide, cone, cilindro e esfera), relacionando-as com objetos do mundo físico."},
        {"codigo": "EF02MA15", "descricao": "Reconhecer, comparar e nomear figuras planas (círculo, quadrado, retângulo e triângulo), por meio de características comuns, em desenhos, objetos do mundo físico e em sólidos geométricos."},
        {"codigo": "EF02MA16", "descricao": "Estimativas, medir e comparar comprimentos de lados de salas (incluindo contorno) e de polígonos, utilizando unidades de medida não padronizadas e padronizadas (metro, centímetro e milímetro) e instrumentos adequados."},
        {"codigo": "EF02MA17", "descricao": "Estimar, medir e comparar capacidades e massas, utilizando estratégias pessoais e unidades de medida não padronizadas ou padronizadas (litro, mililitro, grama e quilograma)."},
        {"codigo": "EF02MA18", "descricao": "Indicar a duração de intervalos de tempo entre duas datas, como dias da semana e meses do ano, utilizando calendário, para planejamentos e organização de agenda."},
        {"codigo": "EF02MA19", "descricao": "Medir a duração de um intervalo de tempo por meio de relógio digital e registrar o horário do início e do fim do intervalo."},
        {"codigo": "EF02MA20", "descricao": "Estabelecer a equivalência de valores entre moedas e cédulas do sistema monetário brasileiro para resolver situações cotidianas."},
        {"codigo": "EF02MA21", "descricao": "Classificar resultados de eventos cotidianos aleatórios como \"pouco prováveis\", \"muito prováveis\", \"improváveis\" e \"impossíveis\"."},
        {"codigo": "EF02MA22", "descricao": "Comparar informações de pesquisas apresentadas por meio de tabelas de dupla entrada e em gráficos de colunas simples ou barras, para melhor compreender aspectos da realidade próxima."},
        {"codigo": "EF02MA23", "descricao": "Realizar pesquisa em universo de até 30 elementos, escolhendo até três variáveis categóricas de seu interesse, organizando os dados coletados em listas, tabelas e gráficos de colunas simples."},
    ],
    "3º Ano": [
        {"codigo": "EF03MA01", "descricao": "Ler, escrever e comparar números naturais de até a ordem de unidade de milhar, estabelecendo relações entre os registros numéricos e em língua materna."},
        {"codigo": "EF03MA02", "descricao": "Identificar características do sistema de numeração decimal, utilizando a composição e a decomposição de número natural de até quatro ordens."},
        {"codigo": "EF03MA03", "descricao": "Construir e utilizar fatos básicos da adição e da multiplicação para o cálculo mental ou escrito."},
        {"codigo": "EF03MA04", "descricao": "Estabelecer a relação entre números naturais e a reta numérica para ordená-los."},
        {"codigo": "EF03MA05", "descricao": "Utilizar diferentes procedimentos de cálculo mental e escrito para resolver problemas significativos envolvendo adição e subtração com números naturais."},
        {"codigo": "EF03MA06", "descricao": "Resolver e elaborar problemas de adição e subtração com os significados de juntar, acrescentar, separar, retirar, comparar e completar quantidades, utilizando diferentes estratégias de cálculo exato ou aproximado, incluindo cálculo mental."},
        {"codigo": "EF03MA07", "descricao": "Resolver e elaborar problemas de multiplicação (por 2, 3, 4, 5 e 10) com os significados de adição de parcelas iguais e elementos apresentados em disposição retangular, utilizando diferentes estratégias de cálculo e registros."},
        {"codigo": "EF03MA08", "descricao": "Resolver e elaborar problemas de divisão de um número natural por outro (até 10), com resto zero e com resto diferente de zero, com os significados de repartição equitativa e de medida, por meio de estratégias e registros pessoais."},
        {"codigo": "EF03MA09", "descricao": "Associar o quociente de uma divisão com resto zero de um número natural por 2, 3, 4, 5 e 10 às ideias de metade, terça, quarta, quinta e décima partes."},
        {"codigo": "EF03MA10", "descricao": "Identificar regularidades em sequências ordenadas de números naturais, resultantes da realização de adições ou subtrações sucessivas, por um mesmo número, descrever uma regra de formação da sequência e determinar elementos faltantes ou seguintes."},
        {"codigo": "EF03MA11", "descricao": "Compreender a ideia de igualdade para escrever diferentes sentenças de adições ou de subtrações de dois números naturais que resultem na mesma soma ou diferença."},
        {"codigo": "EF03MA12", "descricao": "Descrever e representar, por meio de esboços de trajetos ou utilizando croquis e maquetes, a movimentação de pessoas ou de objetos no espaço, incluindo mudanças de direção e sentido, com base em diferentes pontos de referência."},
        {"codigo": "EF03MA13", "descricao": "Associar figuras geométricas espaciais (cubo, bloco retangular, pirâmide, cone, cilindro e esfera) a objetos do mundo físico e nomear essas figuras."},
        {"codigo": "EF03MA14", "descricao": "Descrever características de algumas figuras geométricas espaciais (prismas retos, pirâmides, cilindros, cones), relacionando-as com suas planificações."},
        {"codigo": "EF03MA15", "descricao": "Classificar figuras planas em polígonos e não polígonos, considerando lados e vértices, e nomear triângulos, quadriláteros e pentágonos."},
        {"codigo": "EF03MA16", "descricao": "Reconhecer figuras congruentes, usando sobreposição e desenhos em malhas quadriculadas ou triangulares, incluindo o uso de tecnologias digitais."},
        {"codigo": "EF03MA17", "descricao": "Reconhecer que o resultado de uma medida depende da unidade de medida utilizada."},
        {"codigo": "EF03MA18", "descricao": "Escolher a unidade de medida e o instrumento mais apropriado para medições de comprimento, tempo e capacidade."},
        {"codigo": "EF03MA19", "descricao": "Estimar, medir e comparar comprimentos, utilizando unidades de medida não padronizadas e padronizadas mais usuais (metro, centímetro e milímetro) e diversos instrumentos de medida."},
        {"codigo": "EF03MA20", "descricao": "Estimar e medir capacidade e massa, utilizando unidades de medida não padronizadas e padronizadas mais usuais (litro, mililitro, quilograma, grama e miligrama), reconhecendo-as em leitura de rótulos e embalagens, entre outros."},
        {"codigo": "EF03MA21", "descricao": "Comparar, visualmente ou por superposição, áreas de faces de objetos, de figuras planas ou de desenhos."},
        {"codigo": "EF03MA22", "descricao": "Ler e registrar medidas e intervalos de tempo, utilizando relógios (analógico e digital) para informar os horários de início e término de realização de uma atividade e sua duração."},
        {"codigo": "EF03MA23", "descricao": "Ler horas em relógios digitais e em relógios analógicos e reconhecer a relação entre hora e minutos e entre minuto e segundos."},
        {"codigo": "EF03MA24", "descricao": "Resolver e elaborar problemas que envolvam a comparação e a equivalência de valores monetários do sistema brasileiro em situações de compra, venda e troca."},
        {"codigo": "EF03MA25", "descricao": "Identificar, em eventos familiares aleatórios, todos os resultados possíveis, estimando os que têm maiores ou menores chances de ocorrência."},
        {"codigo": "EF03MA26", "descricao": "Resolver problemas cujos dados estão apresentados em tabelas de dupla entrada, gráficos de barras ou de colunas."},
        {"codigo": "EF03MA27", "descricao": "Ler, interpretar e comparar dados apresentados em tabelas de dupla entrada, gráficos de barras ou de colunas, envolvendo resultados de pesquisas significativas, utilizando termos como maior e menor frequência, apropriando-se desse tipo de linguagem para compreender aspectos da realidade sociocultural significativos."},
        {"codigo": "EF03MA28", "descricao": "Realizar pesquisa envolvendo variáveis categóricas em um universo de até 50 elementos, organizar os dados coletados utilizando listas, tabelas simples ou de dupla entrada e representá-los em gráficos de colunas simples, com e sem uso de tecnologias digitais."},
    ],
    "4º Ano": [
        {"codigo": "EF04MA01", "descricao": "Ler, escrever e ordenar números naturais até a ordem de dezenas de milhar."},
        {"codigo": "EF04MA02", "descricao": "Mostrar, por decomposição e composição, que todo número natural pode ser escrito por meio de adições e multiplicações por potências de dez, para compreender o sistema de numeração decimal e desenvolver estratégias de cálculo."},
        {"codigo": "EF04MA03", "descricao": "Resolver e elaborar problemas com números naturais envolvendo adição e subtração, utilizando estratégias diversas, como cálculo, cálculo mental e algoritmos, além de fazer estimativas do resultado."},
        {"codigo": "EF04MA04", "descricao": "Utilizar as relações entre adição e subtração, bem como entre multiplicação e divisão, para ampliar as estratégias de cálculo."},
        {"codigo": "EF04MA05", "descricao": "Utilizar as propriedades das operações para desenvolver estratégias de cálculo."},
        {"codigo": "EF04MA06", "descricao": "Resolver e elaborar problemas envolvendo diferentes significados da multiplicação (adição de parcelas iguais, organização retangular e proporcionalidade), utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos."},
        {"codigo": "EF04MA07", "descricao": "Resolver e elaborar problemas de divisão cujo divisor tenha no máximo dois algarismos, envolvendo os significados de resultado de uma medida e de partição equitativa, utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos."},
        {"codigo": "EF04MA08", "descricao": "Resolver, com o suporte de imagem e/ou material manipulável, problemas simples de contagem, como a determinação do número de agrupamentos possíveis ao se combinar cada elemento de uma coleção com todos os elementos de outra, utilizando estratégias e formas de registro pessoais."},
        {"codigo": "EF04MA09", "descricao": "Reconhecer as frações unitárias mais usuais (1/2, 1/3, 1/4, 1/5, 1/10 e 1/100) como unidades de medida menores do que uma unidade, utilizando a reta numérica como recurso."},
        {"codigo": "EF04MA10", "descricao": "Reconhecer que as regras do sistema de numeração decimal podem ser estendidas para a representação decimal de um número racional e relacionar décimos e centésimos com a representação do sistema monetário brasileiro."},
        {"codigo": "EF04MA11", "descricao": "Identificar regularidades em sequências numéricas compostas por múltiplos de um número natural."},
        {"codigo": "EF04MA12", "descricao": "Reconhecer, por meio de investigações, que há grupos de números naturais para os quais as divisões por um determinado número resultam em restos iguais, identificando regularidades."},
        {"codigo": "EF04MA13", "descricao": "Reconhecer, por meio de investigações, utilizando a calculadora quando necessário, as relações inversas entre as operações de adição e de subtração e de multiplicação e de divisão, para aplicá-las na resolução de problemas."},
        {"codigo": "EF04MA14", "descricao": "Reconhecer e mostrar, por meio de exemplos, que a relação de igualdade existente entre dois termos permanece quando se adiciona ou se subtrai um mesmo número a cada um desses termos."},
        {"codigo": "EF04MA15", "descricao": "Determinar o número desconhecido que torna verdadeira uma igualdade que envolve as operações fundamentais com números naturais."},
        {"codigo": "EF04MA16", "descricao": "Descrever deslocamentos e localização de pessoas e de objetos no espaço, por meio de malhas quadriculadas e representações como desenhos, mapas, planta baixa e croquis, empregando termos como direita e esquerda, mudanças de direção e sentido, intersecção, transversais, paralelas e perpendiculares."},
        {"codigo": "EF04MA17", "descricao": "Associar prismas e pirâmides a suas planificações e analisar, nomear e comparar seus atributos, estabelecendo relações entre as representações planas e espaciais."},
        {"codigo": "EF04MA18", "descricao": "Reconhecer ângulos retos e não retos em figuras poligonais com o uso de dobraduras, esquadros ou softwares de geometria."},
        {"codigo": "EF04MA19", "descricao": "Reconhecer simetria de reflexão em figuras e em pares de figuras geométricas planas e utilizá-la na construção de figuras congruentes, com o uso de malhas quadriculadas e de softwares de geometria."},
        {"codigo": "EF04MA20", "descricao": "Medir e estimar comprimentos (incluindo perímetros), massas e capacidades, utilizando unidades de medida padronizadas mais usuais, valorizando e respeitando a cultura local."},
        {"codigo": "EF04MA21", "descricao": "Medir, comparar e estimar área de figuras planas desenhadas em malha quadriculada, pela contagem dos quadradinhos ou de metades de quadradinho, reconhecendo que duas figuras com formatos diferentes podem ter a mesma área."},
        {"codigo": "EF04MA22", "descricao": "Ler e registrar medidas e intervalos de tempo em horas, minutos e segundos em situações relacionadas ao seu cotidiano, como informar os horários de início e término de realização de uma tarefa e sua duração."},
        {"codigo": "EF04MA23", "descricao": "Reconhecer temperatura como grandeza e o grau Celsius como unidade de medida a ela associada e utilizá-lo em comparações de temperaturas em diferentes regiões do Brasil ou no exterior ou, ainda, em discussões sobre o aquecimento global."},
        {"codigo": "EF04MA24", "descricao": "Registrar as temperaturas máxima e mínima diárias, em locais do seu cotidiano, e elaborar gráficos de colunas com as variações diárias e mensais das temperaturas."},
        {"codigo": "EF04MA25", "descricao": "Resolver e elaborar problemas que envolvam situações de compra e venda e formas de pagamento, utilizando termos como troco e desconto, enfatizando o consumo ético, consciente e responsável."},
        {"codigo": "EF04MA26", "descricao": "Identificar, entre eventos aleatórios cotidianos, aqueles que têm maior chance de ocorrência, reconhecendo características de resultados mais prováveis, sem utilizar frações."},
        {"codigo": "EF04MA27", "descricao": "Analisar dados apresentados em tabelas simples ou de dupla entrada e em gráficos de colunas ou pictóricos, com base em informações das diferentes áreas do conhecimento, e produzir texto com a síntese de sua análise."},
        {"codigo": "EF04MA28", "descricao": "Realizar pesquisa envolvendo variáveis categóricas e numéricas e organizar dados coletados por meio de tabelas e gráficos de colunas simples ou agrupadas, com e sem uso de tecnologias digitais."},
    ],
    "5º Ano": [
        {"codigo": "EF05MA01", "descricao": "Ler, escrever e ordenar números naturais até a ordem das centenas de milhar com compreensão das principais características do sistema de numeração decimal."},
        {"codigo": "EF05MA02", "descricao": "Ler, escrever e ordenar números racionais na forma decimal com compreensão das principais características do sistema de numeração decimal, utilizando, como recursos, a composição e decomposição e a reta numérica."},
        {"codigo": "EF05MA03", "descricao": "Identificar e representar frações (menores e maiores que a unidade), associando-as ao resultado de uma divisão ou à ideia de parte de um todo, utilizando a reta numérica como recurso."},
        {"codigo": "EF05MA04", "descricao": "Identificar frações equivalentes."},
        {"codigo": "EF05MA05", "descricao": "Comparar e ordenar números racionais positivos (representações fracionária e decimal), relacionando-os a pontos na reta numérica."},
        {"codigo": "EF05MA06", "descricao": "Associar as representações 10%, 25%, 50%, 75% e 100% respectivamente à décima parte, quarta parte, metade, três quartos e um inteiro, para calcular porcentagens, utilizando estratégias pessoais, cálculo mental e calculadora, em contextos de educação financeira, entre outros."},
        {"codigo": "EF05MA07", "descricao": "Resolver e elaborar problemas de adição e subtração com números naturais e com números racionais, cuja representação decimal seja finita, utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos."},
        {"codigo": "EF05MA08", "descricao": "Resolver e elaborar problemas de multiplicação e divisão com números naturais e com números racionais cuja representação decimal é finita (com multiplicador natural e divisor natural e diferente de zero), utilizando estratégias diversas, como cálculo por estimativa, cálculo mental e algoritmos."},
        {"codigo": "EF05MA09", "descricao": "Resolver e elaborar problemas simples de contagem envolvendo o princípio multiplicativo, como a determinação do número de agrupamentos possíveis ao se combinar cada elemento de uma coleção com todos os elementos de outra coleção, por meio de diagramas de árvore ou de tabelas."},
        {"codigo": "EF05MA10", "descricao": "Concluir, por meio de investigações, que a relação de igualdade existente entre dois membros permanece ao adicionar, subtrair, multiplicar ou dividir cada um desses membros por um mesmo número, para construir a noção de equivalência."},
        {"codigo": "EF05MA11", "descricao": "Resolver e elaborar problemas cuja conversão em sentença matemática seja uma igualdade com uma operação em que um dos termos é desconhecido."},
        {"codigo": "EF05MA12", "descricao": "Resolver problemas que envolvam variação de proporcionalidade direta entre duas grandezas, para associar a quantidade de um produto ao valor a pagar, alterar as quantidades de ingredientes de receitas, ampliar ou reduzir escalas em mapas, entre outros."},
        {"codigo": "EF05MA13", "descricao": "Resolver problemas envolvendo a partilha de uma quantidade em duas partes desiguais, tais como dividir uma quantidade em duas partes, de modo que uma seja o dobro da outra, com compreensão da ideia de razão entre as partes e delas com o todo."},
        {"codigo": "EF05MA14", "descricao": "Utilizar e compreender diferentes representações para a localização de objetos no plano, como mapas, células em planilhas eletrônicas e coordenadas geográficas, a fim de desenvolver as primeiras noções de coordenadas cartesianas."},
        {"codigo": "EF05MA15", "descricao": "Interpretar, descrever e representar a localização ou movimentação de objetos no plano cartesiano (1º quadrante), utilizando coordenadas cartesianas, indicando mudanças de direção e de sentido e giros."},
        {"codigo": "EF05MA16", "descricao": "Associar figuras espaciais a suas planificações (prismas, pirâmides, cilindros e cones) e analisar, nomear e comparar seus atributos."},
        {"codigo": "EF05MA17", "descricao": "Reconhecer, nomear e comparar polígonos, considerando lados, vértices e ângulos, e desenhá-los, utilizando material de desenho ou tecnologias digitais."},
        {"codigo": "EF05MA18", "descricao": "Reconhecer a congruência dos ângulos e a proporcionalidade entre os lados correspondentes de figuras poligonais em situações de ampliação e de redução em malhas quadriculadas e usando tecnologias digitais."},
        {"codigo": "EF05MA19", "descricao": "Resolver e elaborar problemas envolvendo medidas das grandezas comprimento, área, massa, tempo, temperatura e capacidade, recorrendo a transformações entre as unidades mais usuais em contextos socioculturais."},
        {"codigo": "EF05MA20", "descricao": "Concluir, por meio de investigações, que figuras de perímetros iguais podem ter áreas diferentes e que, também, figuras que têm a mesma área podem ter perímetros diferentes."},
        {"codigo": "EF05MA21", "descricao": "Reconhecer volume como grandeza associada a sólidos geométricos e medir volumes por meio de empilhamento de cubos, utilizando, preferencialmente, objetos concretos."},
        {"codigo": "EF05MA22", "descricao": "Apresentar todos os possíveis resultados de um experimento aleatório, estimando se esses resultados são igualmente prováveis ou não."},
        {"codigo": "EF05MA23", "descricao": "Determinar a probabilidade de ocorrência de um resultado em eventos aleatórios, quando todos os resultados possíveis têm a mesma chance de ocorrer (equiprováveis)."},
        {"codigo": "EF05MA24", "descricao": "Interpretar dados estatísticos apresentados em textos, tabelas e gráficos (colunas ou linhas), referentes a outras áreas do conhecimento ou a outros contextos, como saúde e trânsito, e produzir textos com o objetivo de sintetizar conclusões."},
        {"codigo": "EF05MA25", "descricao": "Realizar pesquisa envolvendo variáveis categóricas e numéricas, organizar dados coletados por meio de tabelas, gráficos de colunas, pictóricos e de linhas, com e sem uso de tecnologias digitais, e apresentar texto escrito sobre a finalidade da pesquisa e a síntese dos resultados."},
    ],
}


def run():
    out = {"habilidades": []}
    
    # Bloco A: Descritores 6º-9º (compartilhados)
    for item in DESCRITORES_6_9:
        out["habilidades"].append({
            "code": item["codigo"],
            "description": item["descricao"],
            "subject_id": MATEMATICA_ID,
            "grade_id": None,
            "comment": "Compartilhada: 6º ao 9º Ano",
        })
    
    # Bloco B: Descritores 1º-5º (compartilhados) com prefixo EF15_
    for item in DESCRITORES_1_5:
        out["habilidades"].append({
            "code": f"EF15_{item['codigo']}",
            "description": item["descricao"],
            "subject_id": MATEMATICA_ID,
            "grade_id": None,
            "comment": "Compartilhada: 1º ao 5º Ano",
        })
    
    # Bloco C: Habilidades por série
    for serie, habilidades in HABILIDADES_POR_SERIE.items():
        grade_id = GRADE_IDS.get(serie)
        if not grade_id:
            raise ValueError(f"Série não mapeada: {serie}")
        for h in habilidades:
            out["habilidades"].append({
                "code": h["codigo"],
                "description": h["descricao"],
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
                "comment": f"Única: {serie}",
            })
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "habilidades_matematica_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    
    total = len(out["habilidades"])
    d69 = len(DESCRITORES_6_9)
    d15 = len(DESCRITORES_1_5)
    hserie = sum(len(h) for h in HABILIDADES_POR_SERIE.values())
    
    print(f"✅ Gerado: {path}")
    print(f"   Total: {total} habilidades")
    print(f"   - Descritores 6º-9º: {d69}")
    print(f"   - Descritores 1º-5º (EF15_): {d15}")
    print(f"   - Habilidades por série: {hserie}")


if __name__ == "__main__":
    run()
