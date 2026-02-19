"""
Gera habilidades_portugues_anos_finais_data.json no formato esperado pelo update script.
Execute uma vez: python scripts/build_anos_finais_json.py
"""
import json
import os

PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"
GRADE_IDS = {
    "6º Ano": "75bea034-3427-4e98-896d-23493d36a84e",
    "7º Ano": "4128c187-5e33-4ff9-a96d-e7eb9ddbe04e",
    "8º Ano": "b6760b9b-2758-4d14-a650-c3a30c0aeb3b",
    "9º Ano": "3c68a0b5-9613-469e-8376-6fb678c60363",
}

# Dados fornecidos pelo usuário (bncc_lingua_portuguesa_anos_finais_completa)
RAW = {
    "habilidades_compartilhadas_todos_anos": [
        {
            "series_aplicaveis": "6º, 7º, 8º e 9º Ano",
            "categoria": "Todos os Campos de Atuação",
            "habilidades": [
                {"codigo": "EF69LP01", "descricao": "Diferenciar a liberdade de expressão de discursos de ódio, posicionando-se contrariamente a esse tipo de discurso e vislumbrando possibilidades de denúncia quando for o caso."},
                {"codigo": "EF69LP02", "descricao": "Analisar e comparar peças publicitárias variadas, de forma a perceber a articulação entre elas em campanhas, as especificidades das várias semioses e mídias, a adequação dessas peças ao público-alvo, aos objetivos do anunciante e à construção composicional e estilo dos gêneros em questão."},
                {"codigo": "EF69LP03", "descricao": "Identificar, em notícias, o fato central, suas principais circunstâncias e eventuais decorrências; em reportagens e fotorreportagens, o fato ou a temática retratada e a perspectiva de abordagem; em entrevistas, os principais temas/subtemas abordados, explicações dadas ou teses defendidas."},
                {"codigo": "EF69LP04", "descricao": "Identificar e avaliar teses/opiniões/posicionamentos explícitos e argumentos em textos argumentativos (carta de leitor, comentário, artigo de opinião, resenha crítica etc.), manifestando concordância ou discordância."},
                {"codigo": "EF69LP05", "descricao": "Inferir e justificar, em textos multissemióticos – tirinhas, charges, memes, gifs etc. –, o efeito de humor, ironia e/ou crítica pelo uso ambíguo de palavras, expressões ou imagens ambíguas, de clichês, de recursos iconográficos, de pontuação etc."},
                {"codigo": "EF69LP06", "descricao": "Produzir e publicar notícias, fotodenúncias, fotorreportagens, reportagens, reportagens multimidiáticas, infográficos, podcasts noticiosos, entrevistas, cartas de leitor, comentários, artigos de opinião de interesse local ou global, textos de apresentação e apreciação de produção cultural (resenhas e outros), vlogs noticiosos, culturais etc."},
                {"codigo": "EF69LP07", "descricao": "Produzir textos em diferentes gêneros, considerando sua adequação ao contexto de produção e circulação – os enunciadores envolvidos, os objetivos, o gênero, o suporte, a circulação –, ao modo (escrito ou oral; imagem estática ou em movimento etc.), à variedade linguística e/ou semiótica apropriada a esse contexto, à construção da textualidade relacionada às propriedades textuais e do gênero."},
                {"codigo": "EF69LP08", "descricao": "Revisar/editar o texto produzido – tendo em vista sua adequação ao contexto de produção, a mídia em questão, características do gênero, aspectos linguísticos, gramaticais, ortográficos e de pontuação – e a articulação da escrita com outras linguagens."},
                {"codigo": "EF69LP09", "descricao": "Planejar uma campanha publicitária sobre questões/problemas, temas, causas significativas para a escola e/ou comunidade, a partir de um levantamento de material sobre o tema ou evento, da definição do público-alvo, do texto ou peça a ser produzido, pelo grupo ou individualmente, dos meios de circulação, da mídia a ser utilizada e da organização da socialização dos resultados."},
                {"codigo": "EF69LP10", "descricao": "Produzir notícias para rádios, TV ou vídeos, podcasts noticiosos e de opinião, entrevistas, comentários, vlogs, booktrailers, documentários, dentre outros, com a formatação e diagramação (visual e sonora) adequada."},
                {"codigo": "EF69LP11", "descricao": "Identificar e analisar posicionamentos defendidos e refutados na escuta de interações polêmicas em entrevistas, discussões e debates (televisivo, em sala de aula, em redes sociais etc.)."},
                {"codigo": "EF69LP12", "descricao": "Desenvolver estratégias de planejamento, elaboração, revisão, edição, reescrita/redesign (esses três últimos quando não for situação ao vivo) e avaliação de textos orais, áudio e/ou vídeo, considerando sua adequação aos contextos em que foram produzidos."},
                {"codigo": "EF69LP13", "descricao": "Engajar-se e contribuir com a busca de conclusões comuns relativas a problemas, temas ou questões polêmicas de interesse da turma e/ou de relevância social."},
                {"codigo": "EF69LP14", "descricao": "Formular perguntas e decompor, com a ajuda dos colegas e dos professores, tema/questão polêmica, explicações e ou argumentos relativos ao objeto de discussão para análise mais minuciosa e buscar em fontes diversas informações ou dados que permitam analisar partes da questão e compartilhá-los com a turma."},
                {"codigo": "EF69LP15", "descricao": "Apresentar argumentos e contra-argumentos coerentes, respeitando os turnos de fala, na participação em discussões sobre temas controversos e/ou polêmicos."},
                {"codigo": "EF69LP16", "descricao": "Analisar e utilizar as formas de composição dos gêneros jornalísticos da ordem do relatar, tais como notícias e reportagens."},
                {"codigo": "EF69LP17", "descricao": "Perceber e analisar os recursos estilísticos e semióticos dos gêneros jornalísticos e publicitários."},
                {"codigo": "EF69LP18", "descricao": "Utilizar, na escrita/reescrita de textos argumentativos, recursos linguísticos que marquem as relações de sentido entre parágrafos e enunciados do texto e operadores de conexão adequados aos tipos de argumento e à forma de composição de textos argumentativos."},
                {"codigo": "EF69LP19", "descricao": "Analisar, em gêneros orais que envolvam argumentação, os efeitos de sentido de elementos típicos da modalidade falada, como a pausa, a entonação, o ritmo, a gestualidade e expressão facial, as hesitações etc."},
                {"codigo": "EF69LP20", "descricao": "Identificar, tendo em vista o contexto de produção, a forma de organização dos textos normativos e legais (lei, código, estatuto, regimento etc.), a lógica de hierarquização de seus itens e subitens e suas partes."},
                {"codigo": "EF69LP21", "descricao": "Posicionar-se em relação a conteúdos veiculados em práticas não institucionalizadas de participação social, sobretudo àquelas vinculadas a manifestações artísticas, produções culturais, intervenções urbanas e práticas próprias das culturas juvenis que pretendam denunciar, expor uma problemática ou \"sacudir\" a sensibilidade."},
                {"codigo": "EF69LP22", "descricao": "Produzir, revisar e editar textos reivindicatórios ou propositivos sobre problemas que afetam a vida escolar ou da comunidade, justificando pontos de vista, reivindicações e detalhando propostas."},
                {"codigo": "EF69LP23", "descricao": "Contribuir com a escrita de textos normativos, quando houver esse tipo de demanda na escola, utilizando conhecimentos sobre a organização e recursos linguísticos desse tipo de texto."},
                {"codigo": "EF69LP24", "descricao": "Discutir casos, reais ou simulações, submetidos a juízo, que envolvam (supostos) desrespeitos a artigos, do código de defesa do consumidor, do código nacional de trânsito, de regulamentações da escola, dentre outros."},
                {"codigo": "EF69LP25", "descricao": "Posicionar-se de forma crítica e fundamentada em relação a propostas de intervenção na escola e na comunidade."},
                {"codigo": "EF69LP26", "descricao": "Tomar nota em discussões, debates, palestras, apresentação de propostas, reuniões, como forma de documentar o evento e apoiar a própria fala."},
                {"codigo": "EF69LP27", "descricao": "Analisar, em textos argumentativos, os mecanismos de modalização, de forma a reconhecer o modo como o enunciador se posiciona diante do que é dito."},
                {"codigo": "EF69LP28", "descricao": "Observar os mecanismos de modalização adequados aos textos jurídicos, as modalidades deônticas, que se referem ao eixo da conduta (obrigatoriedade/permissibilidade) e as modalidades apreciativas."},
                {"codigo": "EF69LP29", "descricao": "Refletir sobre a relação entre os contextos de produção dos gêneros de divulgação científica e os aspectos relativos à construção composicional e às marcas linguísticas características desses gêneros."},
                {"codigo": "EF69LP30", "descricao": "Comparar, com a ajuda do professor, conteúdos, dados e informações de diferentes fontes, levando em conta seus contextos de produção e referências, identificando coincidências, complementaridades e contradições."},
                {"codigo": "EF69LP31", "descricao": "Utilizar pistas linguísticas – tais como \"em primeiro lugar\", \"por outro lado\", \"em resumo\", etc. – para compreender a hierarquização das proposições."},
                {"codigo": "EF69LP32", "descricao": "Selecionar informações e dados relevantes de fontes diversas (impressas, digitais, orais etc.), avaliando a qualidade e a utilidade dessas fontes, e organizar, esquematicamente, com ajuda do professor, as informações necessárias."},
                {"codigo": "EF69LP33", "descricao": "Articular o verbal com outras linguagens em textos multissemióticos, na organização e apresentação de informações."},
                {"codigo": "EF69LP34", "descricao": "Grifar as partes essenciais do texto, tendo em vista os objetivos de leitura, produzir marginálias, ou tomar notas em outro suporte, como estratégia de leitura."},
                {"codigo": "EF69LP35", "descricao": "Planejar textos de divulgação científica, a partir da elaboração de esquema que considere as pesquisas feitas anteriormente, de notas e sínteses de leituras ou de registros de experimentos ou de estudo de campo."},
                {"codigo": "EF69LP36", "descricao": "Produzir, revisar e editar textos voltados para a divulgação do conhecimento e de dados e resultados de pesquisas."},
                {"codigo": "EF69LP37", "descricao": "Produzir roteiros para elaboração de vídeos de diferentes tipos (vlog científico, vídeo-minuto, programa de rádio, podcasts) para divulgação de conhecimentos científicos e resultados de pesquisa."},
                {"codigo": "EF69LP38", "descricao": "Organizar os dados e informações pesquisados em apresentações orais, tendo em vista o contexto de produção e as características do gênero."},
                {"codigo": "EF69LP39", "descricao": "Engajar-se ativamente em processos de planejamento, revisão/edição e reescrita tendo em vista as restrições temáticas, composicionais e estilísticas dos textos pretendidos e as configurações da situação de produção."},
                {"codigo": "EF69LP40", "descricao": "Analisar, em textos de divulgação científica e outros gêneros, a organização e o tratamento da informação, bem como os recursos de coesão e as marcas linguísticas de impessoalização."},
                {"codigo": "EF69LP41", "descricao": "Usar adequadamente ferramentas de apoio a apresentações orais, escolhendo e usando tipos e tamanhos de fontes que permitam boa visualização, ocupando os slides de forma harmônica."},
                {"codigo": "EF69LP42", "descricao": "Analisar a construção composicional dos textos pertencentes a gêneros relacionados à divulgação de conhecimentos: título, introdução, desenvolvimento, conclusão etc."},
                {"codigo": "EF69LP43", "descricao": "Identificar e utilizar os modos de introdução de outras vozes no texto – citação literal e sua formatação e paráfrase."},
                {"codigo": "EF69LP44", "descricao": "Inferir a presença de valores sociais, culturais e humanos e de diferentes visões de mundo, em textos literários."},
                {"codigo": "EF69LP45", "descricao": "Posicionar-se criticamente em relação a textos pertencentes a gêneros como quarta-capa, programa (de teatro, dança, concerto), sinopse, resenha crítica, comentário em blog/vlog cultural etc."},
                {"codigo": "EF69LP46", "descricao": "Participar de práticas de compartilhamento de leitura/recepção de obras literárias/manifestações artísticas, como rodas de leitura, clubes de leitura, eventos de contação de histórias, de leituras dramáticas etc."},
                {"codigo": "EF69LP47", "descricao": "Analisar, em textos narrativos ficcionais, as diferentes formas de composição próprias de cada gênero, os recursos coesivos e a escolha lexical típica de cada gênero."},
                {"codigo": "EF69LP48", "descricao": "Interpretar, em poemas, efeitos produzidos pelo uso de recursos expressivos sonoros, semânticos, gráfico-espaciais e imagens poéticas."},
                {"codigo": "EF69LP49", "descricao": "Mostrar-se interessado e envolvido pela leitura de livros de literatura e por outras produções culturais do campo artístico-literário."},
                {"codigo": "EF69LP50", "descricao": "Elaborar texto teatral, a partir da adaptação de romances, contos, mitos, narrativas de enigma e de aventura, novelas, biografias romanceadas, crônicas, dentre outros."},
                {"codigo": "EF69LP51", "descricao": "Engajar-se ativamente nos processos de planejamento, textualização, revisão/edição e reescrita, tendo em vista as restrições temáticas, composicionais e estilísticas dos textos pretendidos e as configurações da situação de produção."},
                {"codigo": "EF69LP52", "descricao": "Representar cenas ou textos dramáticos, considerando, na caracterização dos personagens, os aspectos linguísticos e paralinguísticos das falas (timbre e tom de voz, pausas e hesitações, entonação e expressividade, variedades e registros linguísticos)."},
                {"codigo": "EF69LP53", "descricao": "Ler em voz alta textos literários diversos, bem como leituras orais capituladas, compartilhando com os colegas os sentidos produzidos."},
                {"codigo": "EF69LP54", "descricao": "Analisar os efeitos de sentido decorrentes da interação entre os elementos linguísticos e os recursos paralinguísticos e cinésicos."},
                {"codigo": "EF69LP55", "descricao": "Reconhecer as variedades da língua falada, o conceito de norma-padrão e o de preconceito linguístico."},
                {"codigo": "EF69LP56", "descricao": "Fazer uso consciente e reflexivo de regras e normas da norma-padrão em situações de fala e escrita nas quais ela deve ser usada."},
            ]
        }
    ],
    "habilidades_compartilhadas_ciclos": [
        {
            "series_aplicaveis": "6º e 7º Ano",
            "habilidades": [
                {"codigo": "EF67LP01", "descricao": "Analisar a estrutura e funcionamento dos hiperlinks em textos noticiosos publicados na Web e vislumbrar possibilidades de uma escrita hipertextual."},
                {"codigo": "EF67LP02", "descricao": "Explorar o espaço reservado ao leitor nos jornais, revistas, impressos e on-line, sites noticiosos etc., destacando a presença de valores sociais e culturais e o posicionamento ético."},
                {"codigo": "EF67LP03", "descricao": "Comparar informações sobre um mesmo fato veiculadas em diferentes mídias e concluir sobre qual é mais confiável e por quê."},
                {"codigo": "EF67LP04", "descricao": "Distinguir, em segmentos descontínuos de textos, fato da opinião enunciada em relação a esse fato."},
                {"codigo": "EF67LP05", "descricao": "Identificar e avaliar teses/opiniões/posicionamentos explícitos e argumentos em textos argumentativos (carta de leitor, comentário, artigo de opinião etc.)."},
                {"codigo": "EF67LP06", "descricao": "Identificar os efeitos de sentido provocados pela seleção lexical, topicalização de elementos e seleção e hierarquização de informações em textos noticiosos."},
                {"codigo": "EF67LP07", "descricao": "Identificar o uso de recursos persuasivos em textos argumentativos diversos (como a escolha lexical, o uso de adjetivos e advérbios avaliativos e construções que denotam certeza, probabilidade, dúvida etc.)."},
                {"codigo": "EF67LP08", "descricao": "Identificar os efeitos de sentido devidos à escolha de imagens estáticas, sequenciação ou sobreposição de imagens, definição de figura/fundo, ângulo, profundidade de campo, foco, tonalidade, luz, uso de cores etc."},
                {"codigo": "EF67LP09", "descricao": "Planejar notícia impressa e para circulação em outras mídias, tendo em vista as condições de produção, do texto."},
                {"codigo": "EF67LP10", "descricao": "Produzir notícia impressa tendo em vista características do gênero – título ou manchete com verbo no tempo presente, lide, progressão dada/nova, organização em parágrafos, citações de falas de entrevistados por meio de discurso direto e indireto etc."},
                {"codigo": "EF67LP11", "descricao": "Planejar, roteirizar e produzir podcasts noticiosos e de opinião, entrevistas, comentários, vlogs etc."},
                {"codigo": "EF67LP12", "descricao": "Produzir resenhas críticas, vlogs, podcasts literários, playlists comentadas de obras literárias, filmes, séries, games, dentre outros."},
                {"codigo": "EF67LP13", "descricao": "Produzir, revisar e editar textos publicitários, levando em conta o contexto de produção dado, explorando recursos multissemióticos."},
                {"codigo": "EF67LP14", "descricao": "Definir o contexto de produção da entrevista (objetivos, o que se pretende conseguir, escolha do entrevistado, mapa de roteiro etc.)."},
                {"codigo": "EF67LP15", "descricao": "Identificar a proibição de propagandas de produtos nocivos à saúde e a influência da propaganda no consumo."},
                {"codigo": "EF67LP16", "descricao": "Explorar e analisar espaços de reclamação de direitos e de envio de solicitações (ouvidorias, SAC, canais de ligue-denúncia, portais de prefeituras etc.)."},
                {"codigo": "EF67LP17", "descricao": "Analisar, a partir do contexto de produção, a forma de organização das cartas de solicitação e de reclamação."},
                {"codigo": "EF67LP18", "descricao": "Identificar o objeto da reclamação e/ou da solicitação e os argumentos e explicações utilizados para sustentá-la."},
                {"codigo": "EF67LP19", "descricao": "Realizar levantamento de questões, problemas ou demandas que afetem a vida da comunidade e posicionar-se."},
                {"codigo": "EF67LP20", "descricao": "Realizar pesquisa, a partir de recortes e questões definidos, usando fontes indicadas e abertas."},
                {"codigo": "EF67LP21", "descricao": "Divulgar resultados de pesquisas por meio de apresentações orais, verbetes de enciclopédias colaborativas, reportagens de divulgação científica, vlogs científicos, vídeos de diferentes tipos etc."},
                {"codigo": "EF67LP22", "descricao": "Produzir resumos, a partir das notas e/ou esquemas feitos, com o uso adequado de paráfrases e citações."},
                {"codigo": "EF67LP23", "descricao": "Respeitar os turnos de fala, na participação em conversações e em discussões ou atividades coletivas, na sala de aula e na escola."},
                {"codigo": "EF67LP24", "descricao": "Tomar nota de aulas, apresentações orais, entrevistas (ao vivo, áudio, TV, vídeo), identificando e hierarquizando as informações principais, tendo em vista o objetivo do registro."},
                {"codigo": "EF67LP25", "descricao": "Reconhecer e utilizar os critérios de organização topológica (do geral para o específico, do específico para o geral etc.) e de organização cronológica."},
                {"codigo": "EF67LP26", "descricao": "Reconhecer a estrutura de verbetes de enciclopédias e dicionários."},
                {"codigo": "EF67LP27", "descricao": "Analisar, entre os textos literários e entre estes e outras manifestações artísticas, referências explícitas ou implícitas a outros textos."},
                {"codigo": "EF67LP28", "descricao": "Ler, de forma autônoma, e compreender – selecionando procedimentos e estratégias de leitura adequados a diferentes objetivos – romances infanto-juvenis, contos populares, contos de terror, lendas brasileiras, indígenas e africanas, narrativas de aventuras, narrativas de enigma, mitos, crônicas, autobiografias, histórias em quadrinhos, mangás, poemas de forma livre e fixa, dentre outros."},
                {"codigo": "EF67LP29", "descricao": "Identificar, em texto dramático, personagem, ato, cena, fala e indicações cênicas e a organização do texto: enredo, conflito, ideias principais, pontos de vista, universos de referência."},
                {"codigo": "EF67LP30", "descricao": "Criar narrativas ficcionais, tais como contos populares, contos de suspense, mistério, terror, humor, narrativas de enigma, crônicas, histórias em quadrinhos, dentre outros, que explorem diferentes modos de representação."},
                {"codigo": "EF67LP31", "descricao": "Criar poemas compostos por versos livres e de forma fixa (como quadras e sonetos), utilizando recursos visuais, semânticos e sonoros, tais como cadências, ritmos e rimas."},
                {"codigo": "EF67LP32", "descricao": "Escrever palavras com correção ortográfica, obedecendo às convenções da língua escrita."},
                {"codigo": "EF67LP33", "descricao": "Pontuar textos adequadamente."},
                {"codigo": "EF67LP34", "descricao": "Formar antônimos com acréscimo de prefixos que expressam noção de negação."},
                {"codigo": "EF67LP35", "descricao": "Distinguir palavras derivadas por acréscimo de afixos e palavras compostas."},
                {"codigo": "EF67LP36", "descricao": "Utilizar, ao produzir texto, recursos de coesão referencial (léxica e pronominal) e sequencial e outros recursos expressivos adequados ao gênero textual."},
                {"codigo": "EF67LP37", "descricao": "Analisar, em diferentes textos, os efeitos de sentido decorrentes do uso de recursos linguístico-discursivos de prescrição, causalidade, sequenciação e outros."},
                {"codigo": "EF67LP38", "descricao": "Analisar os efeitos de sentido do uso de figuras de linguagem, como comparação, metáfora, metonímia, personificação, hipérbole, dentre outras."},
            ]
        },
        {
            "series_aplicaveis": "8º e 9º Ano",
            "habilidades": [
                {"codigo": "EF89LP01", "descricao": "Analisar os interesses que movem o campo jornalístico, os efeitos das novas tecnologias no campo e as condições que fazem da informação uma mercadoria, de forma a adotar atitude crítica frente aos textos jornalísticos."},
                {"codigo": "EF89LP02", "descricao": "Analisar diferentes práticas (curtir, compartilhar, comentar, curar etc.) e textos pertencentes a diferentes gêneros da cultura digital (meme, gif, comentário, charge digital etc.) envolvidos no trato com a informação e opinião."},
                {"codigo": "EF89LP03", "descricao": "Analisar textos de opinião (artigos de opinião, editoriais, cartas de leitores, comentários, posts de blog e de redes sociais, charges, memes, gifs etc.) e posicionar-se de forma crítica e fundamentada, ética e respeitosa frente a fatos e opiniões relacionados a esses textos."},
                {"codigo": "EF89LP04", "descricao": "Identificar e avaliar teses/opiniões/posicionamentos explícitos e implícitos, argumentos e contra-argumentos em textos argumentativos do campo."},
                {"codigo": "EF89LP05", "descricao": "Analisar o efeito de sentido produzido pelo uso, em textos, de recursos de persuasão (escolha lexical, construções gramaticais, modalizadores etc.)."},
                {"codigo": "EF89LP06", "descricao": "Analisar o uso de recursos persuasivos em textos argumentativos diversos (como a escolha lexical, o uso de adjetivos e advérbios avaliativos e construções que denotam certeza, probabilidade, dúvida etc.)."},
                {"codigo": "EF89LP07", "descricao": "Analisar, em notícias, reportagens e peças publicitárias, a distinção entre fato e opinião, e os efeitos de sentido do uso de formas verbais, modalizadores etc."},
                {"codigo": "EF89LP08", "descricao": "Planejar reportagem impressa e em outras mídias (rádio ou TV/vídeo, sites), tendo em vista as condições de produção do texto."},
                {"codigo": "EF89LP09", "descricao": "Produzir reportagem impressa, com título, linha fina (optativa), organização composicional (expositiva, interpretativa e/ou opinativa), progressão temática e uso de recursos linguísticos compatíveis com as escolhas feitas."},
                {"codigo": "EF89LP10", "descricao": "Planejar, produzir e editar artigos de opinião, tendo em vista o contexto de produção dado, assumindo posição diante de tema polêmico, argumentando de acordo com a estrutura própria desse tipo de texto."},
                {"codigo": "EF89LP11", "descricao": "Produzir, revisar e editar peças e campanhas publicitárias, envolvendo o uso articulado e complementar de diferentes peças publicitárias."},
                {"codigo": "EF89LP12", "descricao": "Planejar, produzir e editar textos publicitários, levando em conta o contexto de produção dado e o uso de recursos multissemióticos."},
                {"codigo": "EF89LP13", "descricao": "Analisar, em debates, entrevistas, e outros gêneros, a polidez (estratégias de atenuação e de intensificação), o uso de operadores argumentativos e de modalizadores."},
                {"codigo": "EF89LP14", "descricao": "Analisar, em textos argumentativos e propositivos, os movimentos argumentativos de sustentação, refutação e negociação e os tipos de argumentos."},
                {"codigo": "EF89LP15", "descricao": "Utilizar, nos debates, operadores argumentativos que marcam a defesa de ideia e de diálogo com a tese do outro: concordância ou discordância parcial ou total, etc."},
                {"codigo": "EF89LP16", "descricao": "Analisar a modalização realizada em textos noticiosos e argumentativos, por meio das modalidades apreciativas, viabilizadas por classes e estruturas gramaticais."},
                {"codigo": "EF89LP17", "descricao": "Relacionar textos e documentos legais e normativos de âmbito universal, nacional, local ou escolar que envolvam a definição de direitos e deveres."},
                {"codigo": "EF89LP18", "descricao": "Explorar e analisar instâncias e canais de participação disponíveis na escola, na comunidade, ou via internet."},
                {"codigo": "EF89LP19", "descricao": "Analisar, no contexto de produção, a forma de organização das cartas de solicitação e de reclamação, abaixo-assinados e das propostas, considerando as marcas linguísticas e os argumentos selecionados."},
                {"codigo": "EF89LP20", "descricao": "Comparar as propostas políticas e de solução de problemas, identificando o que se pretende fazer/implementar, por que (motivações, justificativas), para que (objetivos, benefícios) e como (ações, passos, etapas)."},
                {"codigo": "EF89LP21", "descricao": "Realizar enquetes e pesquisas de opinião, de forma a levantar prioridades, problemas a resolver ou proposições que possam contribuir para a melhoria da escola ou da comunidade."},
                {"codigo": "EF89LP22", "descricao": "Compreender e comparar as diferentes posições e interesses em jogo em uma discussão ou debate."},
                {"codigo": "EF89LP23", "descricao": "Analisar, em textos argumentativos, reivindicatórios e propositivos, os movimentos argumentativos utilizados (sustentação, refutação e negociação)."},
                {"codigo": "EF89LP24", "descricao": "Realizar pesquisa, estabelecendo o recorte das questões, usando fontes abertas e confiáveis."},
                {"codigo": "EF89LP25", "descricao": "Divulgar o resultado de pesquisas por meio de apresentações orais, verbetes de enciclopédias colaborativas, reportagens de divulgação científica, vlogs científicos, vídeos de diferentes tipos etc."},
                {"codigo": "EF89LP26", "descricao": "Produzir resenhas, vlogs, podcasts literários e aulas, verbetes de enciclopédia, dentre outros, considerando a situação comunicativa."},
                {"codigo": "EF89LP27", "descricao": "Tecer considerações e formular problematizações pertinentes, em momentos oportunos, em discussões, aulas, debates, apresentações."},
                {"codigo": "EF89LP28", "descricao": "Tomar nota de videoaulas, aulas digitais, apresentações multimídias, vídeos de divulgação científica, documentários e afins, identificando, em função dos objetivos, informações principais para apoio ao estudo."},
                {"codigo": "EF89LP29", "descricao": "Utilizar e perceber mecanismos de progressão temática, tais como retomadas anafóricas, catáforas, uso de organizadores textuais, de coesivos etc."},
                {"codigo": "EF89LP30", "descricao": "Analisar a estrutura de hipertexto e hiperlinks em textos de divulgação científica e proceder à remissão a conceitos e relações por meio de links."},
                {"codigo": "EF89LP31", "descricao": "Analisar e utilizar modalização epistêmica, isto é, modos de indicar uma avaliação sobre o valor de verdade e as condições de verdade de uma proposição."},
                {"codigo": "EF89LP32", "descricao": "Analisar os efeitos de sentido decorrentes do uso de mecanismos de intertextualidade (referências, alusões, retomadas) entre os textos literários, entre esses textos literários e outras manifestações artísticas."},
                {"codigo": "EF89LP33", "descricao": "Ler, de forma autônoma, e compreender – selecionando procedimentos e estratégias de leitura adequados a diferentes objetivos – romances, contos contemporâneos, minicontos, fábulas contemporâneas, romances juvenis, biografias romanceadas, novelas, crônicas visuais, narrativas de ficção científica, narrativas de suspense, poemas de forma livre e fixa (como haicai), poema concreto, ciberpoema, dentre outros."},
                {"codigo": "EF89LP34", "descricao": "Analisar a organização de texto dramático apresentado em teatro, televisão, cinema, identificando e caracterizando o cenário, o figurino e a encenação e reconhecendo os recursos linguísticos e semióticos envolvidos."},
                {"codigo": "EF89LP35", "descricao": "Criar contos ou crônicas (em especial, líricas), crônicas visuais, minicontos, narrativas de aventura e de ficção científica, dentre outros, com temáticas próprias ao gênero."},
                {"codigo": "EF89LP36", "descricao": "Parodiar poemas conhecidos da literatura e criar textos em versos (como haicais, poemas concretos, ciberpoemas, dentre outros)."},
                {"codigo": "EF89LP37", "descricao": "Analisar os efeitos de sentido do uso de figuras de linguagem como ironia, eufemismo, antítese, aliteração, assonância, dentre outras."},
            ]
        },
    ],
    "habilidades_unicas_por_serie": [
        {
            "serie": "6º Ano",
            "habilidades": [
                {"codigo": "EF06LP01", "descricao": "Reconhecer a impossibilidade de uma neutralidade absoluta no relato de fatos e identificar diferentes graus de parcialidade/imparcialidade dados pelo recorte feito e pelos efeitos de sentido advindos de escolhas feitas pelo autor."},
                {"codigo": "EF06LP02", "descricao": "Estabelecer relação entre os diferentes gêneros jornalísticos, compreendendo a centralidade da notícia."},
                {"codigo": "EF06LP03", "descricao": "Analisar diferenças de sentido entre palavras de uma série sinonímica."},
                {"codigo": "EF06LP04", "descricao": "Analisar a função e as flexões de substantivos e adjetivos e de verbos nos modos Indicativo, Subjuntivo e Imperativo: afirmativo e negativo."},
                {"codigo": "EF06LP05", "descricao": "Identificar os efeitos de sentido dos modos verbais, considerando o gênero textual e a intenção comunicativa."},
                {"codigo": "EF06LP06", "descricao": "Empregar, adequadamente, as regras de concordância nominal (relações entre os substantivos e seus determinantes) e as regras de concordância verbal (relações entre o verbo e o sujeito simples e composto)."},
                {"codigo": "EF06LP07", "descricao": "Identificar, em textos, períodos compostos por orações separadas por vírgula sem a utilização de conectivos, nomeando-os como orações coordenadas assindéticas."},
                {"codigo": "EF06LP08", "descricao": "Identificar, em textos, termos constitutivos da oração (sujeito e seus modificadores, verbo e seus complementos e modificadores)."},
                {"codigo": "EF06LP09", "descricao": "Classificar, em textos, a palavra \"se\" (partícula apassivadora, índice de indeterminação do sujeito, conjunção condicional, conjunção integrante)."},
                {"codigo": "EF06LP10", "descricao": "Identificar sintagmas nominais e verbais como constituintes imediatos da oração."},
                {"codigo": "EF06LP11", "descricao": "Utilizar, ao produzir texto, recursos de coesão referencial (léxica e pronominal) e sequencial e outros recursos expressivos adequados ao gênero textual."},
                {"codigo": "EF06LP12", "descricao": "Utilizar, ao produzir texto, recursos de coesão referencial (nome e pronomes), recursos de semântica (sinonímia, antonímia e homonímia) e mecanismos de representação de diferentes vozes (discurso direto e indireto)."},
            ]
        },
        {
            "serie": "7º Ano",
            "habilidades": [
                {"codigo": "EF07LP01", "descricao": "Distinguir diferentes propostas editoriais em textos de notícias e reportagens, identificando recursos de persuasão."},
                {"codigo": "EF07LP02", "descricao": "Comparar notícias e reportagens sobre um mesmo fato divulgadas em diferentes mídias, analisando a especificidade dos meios e o tratamento da informação."},
                {"codigo": "EF07LP03", "descricao": "Formular perguntas e decompor, com a ajuda dos colegas e dos professores, tema/questão polêmica, explicações e ou argumentos relativos ao objeto de discussão para análise mais minuciosa."},
                {"codigo": "EF07LP04", "descricao": "Reconhecer, em textos, o verbo como o núcleo das orações."},
                {"codigo": "EF07LP05", "descricao": "Identificar, em orações de textos lidos ou de produção própria, verbos de predicação completa e incompleta: intransitivos e transitivos."},
                {"codigo": "EF07LP06", "descricao": "Empregar as regras básicas de concordância nominal e verbal em situações comunicativas e na produção de textos."},
                {"codigo": "EF07LP07", "descricao": "Identificar, em textos, a estrutura básica da oração: sujeito, predicado, complemento (objetos direto e indireto)."},
                {"codigo": "EF07LP08", "descricao": "Identificar, em textos, o sujeito (simples, composto, oculto, indeterminado) e o predicado."},
                {"codigo": "EF07LP09", "descricao": "Identificar, em textos, os adjuntos adnominais e adverbiais, diferenciando-os dos complementos."},
                {"codigo": "EF07LP10", "descricao": "Utilizar, ao produzir texto, conhecimentos linguísticos e gramaticais: modos e tempos verbais, concordância nominal e verbal, regência nominal e verbal."},
                {"codigo": "EF07LP11", "descricao": "Identificar, em textos lidos ou de produção própria, períodos compostos por coordenação e subordinação."},
                {"codigo": "EF07LP12", "descricao": "Reconhecer recursos de coesão referencial: substituições lexicais (de substantivos por sinônimos) ou pronominais (uso de pronomes anafóricos – pessoais, possessivos, demonstrativos)."},
                {"codigo": "EF07LP13", "descricao": "Estabelecer relações entre partes do texto, identificando o antecedente de um pronome relativo ou o referente comum de uma cadeia de substituições lexicais."},
                {"codigo": "EF07LP14", "descricao": "Identificar, em textos, os efeitos de sentido do uso de estratégias de modalização e argumentatividade."},
            ]
        },
        {
            "serie": "8º Ano",
            "habilidades": [
                {"codigo": "EF08LP01", "descricao": "Identificar e comparar as várias editorias de jornais impressos e digitais e de sites noticiosos, de forma a refletir sobre os tipos de fatos que são noticiados e as escolhas editoriais."},
                {"codigo": "EF08LP02", "descricao": "Justificar diferenças ou semelhanças no tratamento dado a uma mesma informação veiculada em textos diferentes, consultando sites e serviços de checadores de fatos (curadoria)."},
                {"codigo": "EF08LP03", "descricao": "Produzir artigos de opinião, tendo em vista o contexto de produção dado, assumindo posição diante de tema polêmico, argumentando de acordo com a estrutura própria desse tipo de texto e utilizando diferentes tipos de argumentos."},
                {"codigo": "EF08LP04", "descricao": "Utilizar, ao produzir texto, conhecimentos linguísticos e gramaticais: ortografia, regências e concordâncias nominal e verbal, modos e tempos verbais, pontuação etc."},
                {"codigo": "EF08LP05", "descricao": "Analisar processos de formação de palavras por composição (aglutinação e justaposição), apropriando-se de regras básicas de uso do hífen em palavras compostas."},
                {"codigo": "EF08LP06", "descricao": "Identificar, em textos lidos ou de produção própria, os termos constitutivos da oração (sujeito e seus modificadores, verbo e seus complementos e modificadores)."},
                {"codigo": "EF08LP07", "descricao": "Diferenciar, em textos lidos ou de produção própria, complementos de adjuntos."},
                {"codigo": "EF08LP08", "descricao": "Identificar, em textos lidos ou de produção própria, verbos na voz ativa e na voz passiva, interpretando os efeitos de sentido de sujeito ativo e passivo (agente da passiva)."},
                {"codigo": "EF08LP09", "descricao": "Interpretar efeitos de sentido de modificadores (adjuntos adnominais e adverbiais) em textos."},
                {"codigo": "EF08LP10", "descricao": "Interpretar, em textos lidos ou de produção própria, efeitos de sentido de modificadores do verbo (adjuntos adverbiais – tempo, lugar, modo, causa etc.)."},
                {"codigo": "EF08LP11", "descricao": "Identificar, em textos lidos ou de produção própria, agrupamento de orações em períodos, diferenciando coordenação de subordinação."},
                {"codigo": "EF08LP12", "descricao": "Identificar, em textos lidos, orações subordinadas com conjunções de uso frequente, incorporando-as às suas próprias produções."},
                {"codigo": "EF08LP13", "descricao": "Inferir efeitos de sentido decorrentes do uso de recursos de coesão sequencial: conjunções e articuladores textuais."},
                {"codigo": "EF08LP14", "descricao": "Utilizar, ao produzir texto, recursos de coesão sequencial (articuladores) e referencial (léxica e pronominal), construções passivas e impessoais, discurso direto e indireto e outros recursos expressivos adequados ao gênero textual."},
                {"codigo": "EF08LP15", "descricao": "Estabelecer relações entre partes do texto, identificando o antecedente de um pronome relativo ou o referente comum de uma cadeia de substituições lexicais."},
                {"codigo": "EF08LP16", "descricao": "Explicar os efeitos de sentido do uso de figuras de linguagem, como ironia, eufemismo, antítese, aliteração, assonância, dentre outras."},
            ]
        },
        {
            "serie": "9º Ano",
            "habilidades": [
                {"codigo": "EF09LP01", "descricao": "Analisar o fenômeno da disseminação de notícias falsas nas redes sociais e desenvolver estratégias para reconhecê-las, como a checagem da confiabilidade das fontes, a comparação entre diferentes veículos e o uso de ferramentas de curadoria."},
                {"codigo": "EF09LP02", "descricao": "Analisar e comentar a cobertura da imprensa sobre fatos de relevância social, comparando diferentes enfoques por meio do uso de ferramentas de curadoria."},
                {"codigo": "EF09LP03", "descricao": "Produzir artigos de opinião, tendo em vista o contexto de produção dado, assumindo posição diante de tema polêmico, argumentando de acordo com a estrutura própria desse tipo de texto."},
                {"codigo": "EF09LP04", "descricao": "Escrever textos corretamente, de acordo com a norma-padrão, com estruturas sintáticas complexas no nível da oração e do período."},
                {"codigo": "EF09LP05", "descricao": "Identificar, em textos lidos e em produções próprias, orações com a estrutura sujeito-verbo de ligação-predicativo."},
                {"codigo": "EF09LP06", "descricao": "Diferenciar, em textos lidos e em produções próprias, o efeito de sentido do uso de verbos de ligação e de verbos significativos."},
                {"codigo": "EF09LP07", "descricao": "Identificar, em textos lidos e em produções próprias, a relação que conjunções (e locuções conjuntivas) coordenativas e subordinativas estabelecem entre as orações que conectam."},
                {"codigo": "EF09LP08", "descricao": "Identificar, em textos lidos e em produções próprias, a relação que as conjunções (e locuções conjuntivas) coordenativas e subordinativas estabelecem entre as orações que conectam."},
                {"codigo": "EF09LP09", "descricao": "Identificar efeitos de sentido do uso de orações adjetivas restritivas e explicativas em um período composto."},
                {"codigo": "EF09LP10", "descricao": "Comparar as regras de colocação pronominal na norma-padrão com o seu uso no português brasileiro coloquial."},
                {"codigo": "EF09LP11", "descricao": "Inferir efeitos de sentido decorrentes do uso de recursos de coesão sequencial (conjunções e articuladores textuais)."},
                {"codigo": "EF09LP12", "descricao": "Identificar estrangeirismos, caracterizando-os como empréstimos ou como marcas de identidade cultural e/ou profissional."},
            ]
        },
    ],
}


def run():
    out = {"habilidades": []}

    for group in RAW["habilidades_compartilhadas_todos_anos"]:
        series = group.get("series_aplicaveis", "")
        for h in group.get("habilidades", []):
            out["habilidades"].append({
                "code": h["codigo"],
                "description": h["descricao"],
                "subject_id": PORTUGUES_ID,
                "grade_id": None,
                "comment": f"Compartilhada: {series}",
            })

    for group in RAW["habilidades_compartilhadas_ciclos"]:
        series = group.get("series_aplicaveis", "")
        for h in group.get("habilidades", []):
            out["habilidades"].append({
                "code": h["codigo"],
                "description": h["descricao"],
                "subject_id": PORTUGUES_ID,
                "grade_id": None,
                "comment": f"Compartilhada: {series}",
            })

    for grade_data in RAW["habilidades_unicas_por_serie"]:
        serie = grade_data.get("serie", "")
        grade_id = GRADE_IDS.get(serie)
        if not grade_id:
            raise ValueError(f"Série não mapeada: {serie}")
        for h in grade_data.get("habilidades", []):
            out["habilidades"].append({
                "code": h["codigo"],
                "description": h["descricao"],
                "subject_id": PORTUGUES_ID,
                "grade_id": grade_id,
                "comment": f"Única: {serie}",
            })

    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "habilidades_portugues_anos_finais_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ Gerado: {path} ({len(out['habilidades'])} habilidades)")


if __name__ == "__main__":
    run()
