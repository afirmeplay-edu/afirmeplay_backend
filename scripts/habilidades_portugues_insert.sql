INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'CEEF01LP01', 'Identificar as múltiplas linguagens que fazem parte do cotidiano da criança.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'CEEF01LP01'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP01', 'Identificar a função social de textos que circulam em campos da vida social dos quais participa cotidianamente (a casa, a rua, a comunidade, a escola) e nas mídias impressa, de massa e digital, reconhecendo para que foram produzidos, onde circulam, quem os produziu e a quem se destinam.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP01'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP02', 'Estabelecer expectativas em relação ao texto que vai ler (pressuposições antecipadoras dos sentidos, da forma e da função social do texto), apoiando-se em seus conhecimentos prévios sobre as condições de produção e recepção desse texto, o gênero, o suporte e o universo temático, bem como sobre saliências textuais, recursos gráficos, imagens, dados da própria obra (índice, prefácio etc.), confirmando antecipações e inferências realizadas antes e durante a leitura de textos, checando a adequação das hipóteses realizadas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP02'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP03', 'Localizar informações explícitas em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP03'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP04', 'Identificar o efeito de sentido produzido pelo uso de recursos expressivos gráfico-visuais em textos multissemióticos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP04'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP05', 'Planejar, com a ajuda do professor, o texto que será produzido, considerando a situação comunicativa, os interlocutores (quem escreve/para quem escreve); a finalidade ou o propósito (escrever para quê); a circulação (onde o texto vai circular); o suporte (qual é o portador do texto); a linguagem, organização e forma do texto e seu tema, pesquisando em meios impressos ou digitais, sempre que for preciso, informações necessárias à produção do texto, organizando em tópicos os dados e as fontes pesquisadas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP05'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP06', 'Reler e revisar o texto produzido com a ajuda do professor e a colaboração dos colegas, para corrigi-lo e aprimorá- lo, fazendo cortes, acréscimos, reformulações, correções de ortografia e pontuação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP06'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP07', 'Editar a versão final do texto, em colaboração com os colegas e com a ajuda do professor, ilustrando, quando for o caso, em suporte adequado, manual ou digital.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP07'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP08', 'Utilizar software, inclusive programas de edição de texto, para editar e publicar os textos produzidos, explorando os recursos multissemióticos disponíveis.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP08'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP09', 'Expressar-se em situações de intercâmbio oral com clareza, preocupando-se em ser compreendido pelo interlocutor e usando a palavra com tom de voz audível, boa articulação e ritmo adequado.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP09'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP10', 'Escutar, com atenção, falas de professores e colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP10'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP11', 'Reconhecer características da conversação espontânea presencial, respeitando os turnos de fala, selecionando e utilizando, durante a conversação, formas de tratamento adequadas, de acordo com a situação e a posição do interlocutor.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP11'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP12', 'Atribuir significado a aspectos não linguísticos (paralinguísticos) observados na fala, como direção do olhar, riso, gestos, movimentos da cabeça (de concordância ou discordância), expressão corporal, tom de voz.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP12'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP13', 'Identificar finalidades da interação oral em diferentes contextos comunicativos (solicitar informações, apresentar opiniões, informar, relatar experiências etc.).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP13'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP14', 'Construir o sentido de histórias em quadrinhos e tirinhas, relacionando imagens e palavras e interpretando recursos gráficos (tipos de balões, de letras, onomatopeias).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP14'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP15', 'Reconhecer que os textos literários fazem parte do mundo do imaginário e apresentam uma dimensão lúdica, de encantamento, valorizando- os, em sua diversidade cultural, como patrimônio artístico da humanidade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP15'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP16', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor e, mais tarde, de maneira autônoma, textos narrativos de maior porte como contos (populares, de fadas, acumulativos, de assombração etc.) e crônicas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP16'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP17', 'Apreciar poemas visuais e concretos, observando efeitos de sentido criados pelo formato do texto na página, distribuição e diagramação das letras, pelas ilustrações e por outros efeitos visuais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP17'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP18', 'Relacionar texto com ilustrações e outros recursos gráficos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP18'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF15LP19', 'Recontar oralmente, com e sem apoio de imagem, textos literários lidos pelo professor.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF15LP19'); -- Compartilhada: 1º, 2º, 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP01', 'Ler palavras novas com precisão na decodificação, no caso de palavras de uso frequente, ler globalmente, por memorização.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP01'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP02', 'Buscar, selecionar e ler, com a mediação do professor (leitura compartilhada), textos que circulam em meios impressos ou digitais, de acordo com as necessidades e interesses.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP02'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP03', 'Copiar textos breves, mantendo suas características e voltando para o texto sempre que tiver dúvidas sobre sua distribuição gráfica, espaçamento entre as palavras, escrita das palavras e pontuação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP03'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP04', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor ou já com certa autonomia, listas, agendas, calendários, avisos, convites, receitas, instruções de montagem (digitais ou impressos), dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP04'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP05', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, (re)contagens de histórias, poemas e outros textos versificados (letras de canção, quadrinhas, cordel), poemas visuais, tiras e histórias em quadrinhos, dentre outros gêneros do campo artístico- literário, considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP05'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP06', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, recados, avisos, convites, receitas, instruções de montagem, dentre outros gêneros do campo da vida cotidiana, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP06'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP07', 'Identificar e (re)produzir, em cantiga, quadras, quadrinhas, parlendas, trava-línguas e canções, rimas, aliterações, assonâncias, o ritmo de fala relacionado ao ritmo e à melodia das músicas e seus efeitos de sentido.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP07'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP08', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, fotolegendas em notícias, manchetes e lides em notícias, álbum de fotos digital noticioso e notícias curtas para público infantil, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP08'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP09', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, slogans, anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil, dentre outros gêneros do campo publicitário, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP09'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP10', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, cartazes, avisos, folhetos, regras e regulamentos que organizam a vida na comunidade escolar, dentre outros gêneros do campo da atuação cidadã, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP10'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP11', 'Escrever, em colaboração com os colegas e com a ajuda do professor, fotolegendas em notícias, manchetes e lides em notícias, álbum de fotos digital noticioso e notícias curtas para público infantil, digitais ou impressos, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP11'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP12', 'Escrever, em colaboração com os colegas e com a ajuda do professor, slogans, anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil, dentre outros gêneros do campo publicitário, considerando a situação comunicativa e o tema/ assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP12'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP13', 'Planejar, em colaboração com os colegas e com a ajuda do professor, slogans e peça de campanha de conscientização destinada ao público infantil que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP13'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP14', 'Identificar e reproduzir, em fotolegendas de notícias, álbum de fotos digital noticioso, cartas de leitor (revista infantil), digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP14'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP15', 'Identificar a forma de composição de slogans publicitários.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP15'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP16', 'Identificar e reproduzir, em anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil (orais e escritos, digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros, inclusive o uso de imagens.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP16'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP17', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, enunciados de tarefas escolares, diagramas, curiosidades, pequenos relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, entre outros gêneros do campo investigativo, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP17'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP18', 'Apreciar poemas e outros textos versificados, observando rimas, sonoridades, jogos de palavras, reconhecendo seu pertencimento ao mundo imaginário e sua dimensão de encantamento, jogo e fruição.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP18'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF12LP19', 'Reconhecer, em textos versificados, rimas, sonoridades, jogos de palavras, palavras, expressões, comparações, relacionando-as com sensações e associações.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF12LP19'); -- Compartilhada: 1º e 2º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP01', 'Ler e compreender, silenciosamente e, em seguida, em voz alta, com autonomia e fluência, textos curtos com nível de textualidade adequado.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP01'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP02', 'Selecionar livros da biblioteca e/ou do cantinho de leitura da sala de aula e/ou disponíveis em meios digitais para leitura individual, justificando a escolha e compartilhando com os colegas sua opinião, após a leitura.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP02'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP03', 'Identificar a ideia central do texto, demonstrando compreensão global.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP03'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP04', 'Inferir informações implícitas nos textos lidos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP04'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP05', 'Inferir o sentido de palavras ou expressões desconhecidas em textos, com base no contexto da frase ou do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP05'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP06', 'Recuperar relações entre partes de um texto, identificando substituições lexicais (de substantivos por sinônimos) ou pronominais (uso de pronomes anafóricos – pessoais, possessivos, demonstrativos) que contribuem para a continuidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP06'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP07', 'Utilizar, ao produzir um texto, conhecimentos linguísticos e gramaticais, tais como ortografia, regras básicas de concordância nominal e verbal, pontuação (ponto final, ponto de exclamação, ponto de interrogação, vírgulas em enumerações) e pontuação do discurso direto, quando for o caso.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP07'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP08', 'Utilizar, ao produzir um texto, recursos de referenciação (por substituição lexical ou por pronomes pessoais, possessivos e demonstrativos), vocabulário apropriado ao gênero, recursos de coesão pronominal (pronomes anafóricos) e articuladores de relações de sentido (tempo, causa, oposição, conclusão, comparação), com nível suficiente de informatividade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP08'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP09', 'Organizar o texto em unidades de sentido, dividindo-o em parágrafos segundo as normas gráficas e de acordo com as características do gênero textual.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP09'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP10', 'Identificar gêneros do discurso oral, utilizados em diferentes situações e contextos comunicativos, e suas características linguístico- expressivas e composicionais (conversação espontânea, conversação telefônica, entrevistas pessoais, entrevistas no rádio ou na TV, debate, noticiário de rádio e TV, narração de jogos esportivos no rádio e TV, aula, debate etc.).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP10'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP11', 'Ouvir gravações, canções, textos falados em diferentes variedades linguísticas, identificando características regionais, urbanas e rurais da fala e respeitando as diversas variedades linguísticas como características do uso da língua por diferentes grupos regionais ou diferentes culturas locais, rejeitando preconceitos linguísticos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP11'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP12', 'Recorrer ao dicionário para esclarecer dúvida sobre a escrita de palavras, especialmente no caso de palavras com relações irregulares fonema-grafema.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP12'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP13', 'Memorizar a grafia de palavras de uso frequente nas quais as relações fonema-grafema são irregulares e com h inicial que não representa fonema.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP13'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP14', 'Identificar em textos e usar na produção textual pronomes pessoais, possessivos e demonstrativos, como recurso coesivo anafórico.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP14'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP15', 'Opinar e defender ponto de vista sobre tema polêmico relacionado a situações vivenciadas na escola e/ou na comunidade, utilizando registro formal e estrutura adequada à argumentação, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP15'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP16', 'Identificar e reproduzir, em notícias, manchetes, lides e corpo de notícias simples para público infantil e cartas de reclamação (revista infantil), digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP16'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP17', 'Buscar e selecionar, com o apoio do professor, informações de interesse sobre fenômenos sociais e naturais, em textos que circulam em meios impressos ou digitais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP17'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP18', 'Escutar, com atenção, apresentações de trabalhos realizadas por colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP18'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP19', 'Recuperar as ideias principais em situações formais de escuta de exposições, apresentações e palestras.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP19'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP20', 'Expor trabalhos ou pesquisas escolares, em sala de aula, com apoio de recursos multissemióticos (imagens, diagrama, tabelas etc.), orientando-se por roteiro escrito, planejando o tempo de fala e adequando a linguagem à situação comunicativa.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP20'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP21', 'Ler e compreender, de forma autônoma, textos literários de diferentes gêneros e extensões, inclusive aqueles sem ilustrações, estabelecendo preferências por gêneros, temas, autores.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP21'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP22', 'Perceber diálogos em textos narrativos, observando o efeito de sentido de verbos de enunciação e, se for o caso, o uso de variedades linguísticas no discurso direto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP22'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP23', 'Apreciar poemas e outros textos versificados, observando rimas, aliterações e diferentes modos de divisão dos versos, estrofes e refrões e seu efeito de sentido.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP23'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP24', 'Identificar funções do texto dramático (escrito para ser encenado) e sua organização por meio de diálogos entre personagens e marcadores das falas das personagens e das cenas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP24'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP25', 'Criar narrativas ficcionais, com certa autonomia, utilizando detalhes descritivos, sequências de eventos e imagens apropriadas para sustentar o sentido do texto, e marcadores de tempo, espaço e de fala de personagens.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP25'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP26', 'Ler e compreender, com certa autonomia, narrativas ficcionais que apresentem cenários e personagens, observando os elementos da estrutura narrativa: enredo, tempo, espaço, personagens, narrador e a construção do discurso indireto e discurso direto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP26'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP27', 'Ler e compreender, com certa autonomia, textos em versos, explorando rimas, sons e jogos de palavras, imagens poéticas (sentidos figurados) e recursos visuais e sonoros.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP27'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP28', 'Declamar poemas, com entonação, postura e interpretação adequadas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP28'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP29', 'Identificar, em narrativas, cenário, personagem central, conflito gerador, resolução e o ponto de vista com base no qual histórias são narradas, diferenciando narrativas em primeira e terceira pessoas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP29'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP30', 'Diferenciar discurso indireto e discurso direto, determinando o efeito de sentido de verbos de enunciação e explicando o uso de variedades linguísticas no discurso direto, quando for o caso.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP30'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF35LP31', 'Identificar, em textos versificados, efeitos de sentido decorrentes do uso de recursos rítmicos e sonoros e de metáforas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF35LP31'); -- Compartilhada: 3º, 4º e 5º Ano
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP01', 'Reconhecer que textos são lidos e escritos da esquerda para a direita e de cima para baixo da página.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP01'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP01';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP02', 'Escrever, espontaneamente ou por ditado, palavras e frases de forma alfabética – usando letras/grafemas que representem fonemas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP02'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP02';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP03', 'Observar escritas convencionais, comparando-as às suas produções escritas, percebendo semelhanças e diferenças.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP03'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP03';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP04', 'Distinguir as letras do alfabeto de outros sinais gráficos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP04'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP04';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP05', 'Reconhecer o sistema de escrita alfabética como representação dos sons da fala.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP05'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP05';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP06', 'Segmentar oralmente palavras em sílabas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP06'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP06';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP07', 'Identificar fonemas e sua representação por letras.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP07'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP07';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP08', 'Relacionar elementos sonoros (sílabas, fonemas, partes de palavras) com sua representação escrita.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP08'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP08';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP09', 'Comparar palavras, identificando semelhanças e diferenças entre sons de sílabas iniciais, mediais e finais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP09'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP09';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP10', 'Nomear as letras do alfabeto e recitá-lo na ordem das letras.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP10'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP11', 'Conhecer, diferenciar e relacionar letras em formato imprensa e cursiva, maiúsculas e minúsculas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP11'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP12', 'Reconhecer a separação das palavras, na escrita, por espaços em branco.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP12'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP13', 'Comparar palavras, identificando semelhanças e diferenças entre sons de sílabas iniciais, mediais e finais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP13'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP14', 'Identificar outros sinais no texto além das letras, como pontos finais, de interrogação e exclamação, número e seus efeitos na entonação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP14'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP15', 'Agrupar palavras pelo critério de aproximação de significado (sinonímia) e separar palavras pelo critério de oposição de significado (antonímia).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP15'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP16', 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, quadras, quadrinhas, parlendas, trava-línguas, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP16'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP16';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP17', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, listas, agendas, calendários, avisos, convites, receitas, instruções de montagem e legendas para álbuns, fotos ou ilustrações (digitais ou impressos), dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/ finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP17'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP17';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP18', 'Registrar, em colaboração com os colegas e com a ajuda do professor, cantigas, quadras, quadrinhas, parlendas, trava-línguas, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP18'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP18';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP19', 'Recitar parlendas, quadras, quadrinhas, trava-línguas, com entonação adequada e observando as rimas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP19'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP19';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP20', 'Identificar e reproduzir, em listas, agendas, calendários, regras, avisos, convites, receitas, instruções de montagem e legendas para álbuns, fotos ou ilustrações (digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP20'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP20';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP21', 'Escrever, em colaboração com os colegas e com a ajuda do professor, listas de regras e regulamentos que organizam a vida na comunidade escolar, dentre outros gêneros do campo da atuação cidadã, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP21'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP21';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP22', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, diagramas, entrevistas, curiosidades, dentre outros gêneros do campo investigativo, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP22'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP22';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP23', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, entrevistas, curiosidades, dentre outros gêneros do campo investigativo, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP23'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP23';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP24', 'Identificar e reproduzir, em enunciados de tarefas escolares, diagramas, entrevistas, curiosidades, digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP24'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP24';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP25', 'Produzir, tendo o professor como escriba, recontagens de histórias lidas pelo professor, histórias imaginadas ou baseadas em livros de imagens, observando a forma de composição de textos narrativos (personagens, enredo, tempo e espaço).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP25'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP25';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF01LP26', 'Identificar elementos de uma narrativa lida ou escutada, incluindo personagens, enredo, tempo e espaço.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF01LP26'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'EF01LP26';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D1', 'Localizar informações explícitas em um texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D1'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D3', 'Inferir o sentido de uma palavra ou expressão.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D3'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D3';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D4', 'Inferir uma informação implícita em um texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D4'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D4';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D6', 'Identificar o tema de um texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D6'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D6';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D11', 'Distinguir um fato da opinião relativa a esse fato.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D11'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D5', 'Interpretar texto com auxílio de material gráfico diverso (propagandas, quadrinhos, foto, etc.).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D5'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D5';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D9', 'Identificar a finalidade de textos de diferentes gêneros.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D9'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D9';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D15', 'Reconhecer diferentes formas de tratar uma informação na comparação de textos que tratam do mesmo tema, em função das condições em que ele foi produzido e daquelas em que será recebido.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D15'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D2', 'Estabelecer relações entre partes de um texto, identificando repetições ou substituições que contribuem para a continuidade de um texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D2'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D2';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D7', 'Identificar o conflito gerador do enredo e os elementos que constroem a narrativa.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D7'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D7';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D8', 'Estabelecer relação causa /consequência entre partes e elementos do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D8'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D8';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D12', 'Estabelecer relações lógico-discursivas presentes no texto, marcadas por conjunções, advérbios, etc.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D12'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D13', 'Identificar efeitos de ironia ou humor em textos variados.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D13'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D14', 'Identificar o efeito de sentido decorrente do uso da pontuação e de outras notações.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D14'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'D10', 'Identificar as marcas linguísticas que evidenciam o locutor e o interlocutor de um texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'D10'); -- Única: 1º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '391ed6e8-fc45-46f8-8e4c-065005d2329f' FROM public.skills WHERE code = 'D10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP01', 'Utilizar, ao produzir o texto, grafia correta de palavras conhecidas ou com estruturas silábicas já dominadas, letras maiúsculas em início de frases e em substantivos próprios, segmentação entre as palavras, ponto final, ponto de interrogação e ponto de exclamação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP01'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP01';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP02', 'Segmentar palavras em sílabas e remover e substituir sílabas iniciais, mediais ou finais para criar novas palavras.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP02'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP02';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP03', 'Ler e escrever palavras com correspondências regulares diretas entre letras e fonemas (f, v, t, d, p, b) e correspondências regulares contextuais (c e q; e e o, em posição átona em final de palavra).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP03'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP03';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP04', 'Ler e escrever corretamente palavras com sílabas CV, V, CVC, CCV, identificando que existem vogais em todas as sílabas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP04'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP04';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP05', 'Ler e escrever corretamente palavras com marcas de nasalidade (til, m, n).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP05'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP05';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP06', 'Perceber o princípio acrofônico que opera nos nomes das letras do alfabeto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP06'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP06';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP07', 'Escrever palavras, frases, textos curtos nas formas imprensa e cursiva.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP07'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP07';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP08', 'Segmentar corretamente as palavras ao escrever frases e textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP08'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP08';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP09', 'Usar adequadamente ponto final, ponto de interrogação e ponto de exclamação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP09'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP09';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP10', 'Identificar sinônimos de palavras de texto lido, determinando a diferença de sentido entre eles, e formar antônimos de palavras encontradas em texto lido pelo acréscimo do prefixo de negação in-/im-.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP10'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP11', 'Formar o aumentativo e o diminutivo de palavras com os sufixos -ão e -inho/-zinho.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP11'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP12', 'Ler e compreender com certa autonomia cantigas, letras de canção, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP12'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP13', 'Planejar e produzir bilhetes e cartas, em meio impresso e/ou digital, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP13'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP14', 'Planejar e produzir pequenos relatos de observação de processos, de fatos, de experiências pessoais, mantendo as características do gênero, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP14'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP15', 'Cantar cantigas e canções, obedecendo ao ritmo e à melodia.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP15'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP16', 'Identificar e reproduzir, em bilhetes, recados, avisos, cartas, e- mails, receitas (modo de fazer), relatos (digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP16'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP16';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP17', 'Identificar e reproduzir, em relatos de experiências pessoais, a sequência dos fatos, utilizando expressões que marquem a passagem do tempo ("antes", "depois", "ontem", "hoje", "amanhã", "outro dia", "antigamente", "há muito tempo" etc.), e o nível de informatividade necessário.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP17'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP17';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP18', 'Planejar e produzir cartazes e folhetos para divulgar eventos da escola ou da comunidade, utilizando linguagem persuasiva e elementos textuais e visuais (tamanho da letra, leiaute, imagens) adequados ao gênero, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP18'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP18';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP19', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, notícias curtas para público infantil, para compor jornal falado que possa ser repassado oralmente ou em meio digital, em áudio ou vídeo, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP19'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP19';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP20', 'Reconhecer a função de textos utilizados para apresentar informações coletadas em atividades de pesquisa (enquetes, pequenas entrevistas, registros de experimentações).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP20'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP20';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP21', 'Explorar, com a mediação do professor, textos informativos de diferentes ambientes digitais de pesquisa, conhecendo suas possibilidades.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP21'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP21';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP22', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, pequenos relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, dentre outros gêneros do campo investigativo, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP22'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP22';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP23', 'Planejar e produzir, com certa autonomia, pequenos registros de observação de resultados de pesquisa, coerentes com um tema investigado.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP23'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP23';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP24', 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, relatos de experimentos, registros de observação, entrevistas, dentre outros gêneros do campo investigativo, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/ finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP24'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP24';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP25', 'Identificar e reproduzir, em relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP25'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP25';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP26', 'Ler e compreender, com certa autonomia, textos literários, de gêneros variados, desenvolvendo o gosto pela leitura.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP26'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP26';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP27', 'Reescrever textos narrativos literários lidos pelo professor.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP27'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP27';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP28', 'Reconhecer o conflito gerador de uma narrativa ficcional e sua resolução, além de palavras, expressões e frases que caracterizam personagens e ambientes.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP28'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP28';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF02LP29', 'Observar, em poemas visuais, o formato do texto na página, as ilustrações e outros efeitos visuais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF02LP29'); -- Única: 2º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, '74821122-e632-4301-b6f5-42b92b802a55' FROM public.skills WHERE code = 'EF02LP29';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP01', 'Ler e escrever palavras com correspondências regulares contextuais entre grafemas e fonemas – c/qu; g/gu; r/rr; s/ss; o (e não u) e e (e não i) em sílaba átona em final de palavra – e com marcas de nasalidade (til, m, n).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP01'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP01';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP02', 'Ler e escrever corretamente palavras com sílabas CV, V, CVC, CCV, VC, VV, CVV, identificando que existem vogais em todas as sílabas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP02'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP02';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP03', 'Ler e escrever corretamente palavras com os dígrafos lh, nh, ch.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP03'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP03';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP04', 'Usar acento gráfico (agudo ou circunflexo) em monossílabos tônicos terminados em a, e, o e em palavras oxítonas terminadas em a, e, o, seguidas ou não de s.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP04'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP04';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP05', 'Identificar o número de sílabas de palavras, classificando-as em monossílabas, dissílabas, trissílabas e polissílabas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP05'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP05';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP06', 'Identificar a sílaba tônica em palavras, classificando-as em oxítonas, paroxítonas e proparoxítonas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP06'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP06';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP07', 'Identificar a função na leitura e usar na escrita ponto final, ponto de interrogação, ponto de exclamação e, em diálogos (discurso direto), dois- pontos e travessão.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP07'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP07';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP08', 'Identificar e diferenciar, em textos, substantivos e verbos e suas funções na oração: agente, ação, objeto da ação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP08'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP08';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP09', 'Identificar, em textos, adjetivos e sua função de atribuição de propriedades aos substantivos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP09'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP09';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP10', 'Reconhecer prefixos e sufixos produtivos na formação de palavras derivadas de substantivos, de adjetivos e de verbos, utilizando-os para compreender palavras e para formar novas palavras.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP10'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP11', 'Ler e compreender, com autonomia, textos injuntivos instrucionais (receitas, instruções de montagem etc.), com a estrutura própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e mesclando palavras, imagens e recursos gráfico- visuais, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP11'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP12', 'Ler e compreender, com autonomia, cartas pessoais e diários, com expressão de sentimentos e opiniões, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP12'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP13', 'Planejar e produzir cartas pessoais e diários, com expressão de sentimentos e opiniões, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções dos gêneros carta e diário e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP13'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP14', 'Planejar e produzir textos injuntivos instrucionais, com a estrutura própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e mesclando palavras, imagens e recursos gráfico-visuais, considerando a situação comunicativa e o tema/ assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP14'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP15', 'Assistir, em vídeo digital, a programas de culinária infantil e, a partir deles, planejar e produzir receitas em áudio ou vídeo.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP15'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP16', 'Identificar e reproduzir, em textos injuntivos instrucionais (receitas, instruções de montagem, digitais ou impressos), a formatação própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e a diagramação específica dos textos desses gêneros (lista de ingredientes ou materiais e instruções de execução – \"modo de fazer\").', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP16'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP16';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP17', 'Identificar e reproduzir, em gêneros epistolares e diários, a formatação própria desses textos (relatos de acontecimentos, expressão de vivências, emoções, opiniões ou críticas) e a diagramação específica dos textos desses gêneros (data, saudação, corpo do texto, despedida, assinatura).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP17'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP17';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP18', 'Ler e compreender, com autonomia, cartas dirigidas a veículos da mídia impressa ou digital (cartas de leitor e de reclamação a jornais, revistas) e notícias, dentre outros gêneros do campo jornalístico, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP18'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP18';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP19', 'Identificar e discutir o propósito do uso de recursos de persuasão (cores, imagens, escolha de palavras, jogo de palavras, tamanho de letras) em textos publicitários e de propaganda, como elementos de convencimento.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP19'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP19';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP20', 'Produzir cartas dirigidas a veículos da mídia impressa ou digital (cartas do leitor ou de reclamação a jornais ou revistas), dentre outros gêneros do campo político- cidadão, com opiniões e críticas, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP20'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP20';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP21', 'Produzir anúncios publicitários, textos de campanhas de conscientização destinados ao público infantil, observando os recursos de persuasão utilizados nos textos publicitários e de propaganda (cores, imagens, slogan, escolha de palavras, jogo de palavras, tamanho e tipo de letras, diagramação).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP21'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP21';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP22', 'Planejar e produzir, em colaboração com os colegas, telejornal para público infantil com algumas notícias e textos de campanhas que possam ser repassados oralmente ou em meio digital, em áudio ou vídeo, considerando a situação comunicativa, a organização específica da fala nesses gêneros e o tema/assunto/ finalidade dos textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP22'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP22';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP23', 'Analisar o uso de adjetivos em cartas dirigidas a veículos da mídia impressa ou digital (cartas do leitor ou de reclamação a jornais ou revistas), digitais ou impressas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP23'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP23';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP24', 'Ler/ouvir e compreender, com autonomia, relatos de observações e de pesquisas em fontes de informações, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP24'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP24';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP25', 'Planejar e produzir textos para apresentar resultados de observações e de pesquisas em fontes de informações, incluindo, quando pertinente, imagens, diagramas e gráficos ou tabelas simples, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP25'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP25';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP26', 'Identificar e reproduzir, em relatórios de observação e pesquisa, a formatação e diagramação específica desses gêneros (passos ou listas de itens, tabelas, ilustrações, gráficos, resumo dos resultados), inclusive em suas versões orais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP26'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP26';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF03LP27', 'Recitar cordel e cantar repentes e emboladas, observando as rimas e obedecendo ao ritmo e à melodia.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF03LP27'); -- Única: 3º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84' FROM public.skills WHERE code = 'EF03LP27';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP01', 'Grafar palavras utilizando regras de correspondência fonema--grafema regulares diretas e contextuais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP01'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP01';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP02', 'Leitura e escrita, corretamente, palavras com sílabas VV e CVV em casos nos quais a combinação VV (ditongo) é reduzida na língua oral (ai, ei, ou).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP02'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP02';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP03', 'Localizar palavras no dicionário para esclarecer significados, reconhecendo o significado mais plausível para o contexto que deu origem à consulta.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP03'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP03';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP04', 'Usar acento gráfico (agudo ou circunflexo) em paroxítonas terminadas em -i(s), -l, -r, - ão(s).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP04'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP04';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP05', 'Identificar a função na leitura e usar, adequadamente, na escrita ponto final, de interrogação, de exclamação, dois- pontos e travessão em diálogos (discurso direto), vírgula em enumerações e em separação de vocativo e de aposto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP05'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP05';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP06', 'Identificar em textos e usar na produção textual a concordância entre substantivo ou pronome pessoal e verbo (concordância verbal).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP06'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP06';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP07', 'Identificar em textos e usar na produção textual a concordância entre artigo, substantivo e adjetivo (concordância no grupo nominal).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP07'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP07';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP08', 'Reconhecer e grafar, corretamente, palavras derivadas com os sufixos -agem, -oso, -eza, - izar/-isar (regulares morfológicas).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP08'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP08';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP09', 'Ler e compreender, com autonomia, boletos, faturas e carnês, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero (campos, itens elencados, medidas de consumo, código de barras) e considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP09'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP09';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP10', 'Ler e compreender, com autonomia, cartas pessoais de reclamação, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP10'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP11', 'Planejar e produzir, com autonomia, cartas pessoais de reclamação, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e com a estrutura própria desses textos (problema, opinião, argumentos), considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP11'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP12', 'Assistir, em vídeo digital, a programa infantil com instruções de montagem, de jogos e brincadeiras e, a partir dele, planejar e produzir tutoriais em áudio ou vídeo.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP12'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP13', 'Identificar e reproduzir, em textos injuntivos instrucionais (instruções de jogos digitais ou impressos), a formatação própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e formato específico dos textos orais ou escritos desses gêneros (lista/ apresentação de materiais e instruções/passos de jogo).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP13'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP14', 'Identificar, em notícias, fatos, participantes, local e momento/tempo da ocorrência do fato noticiado.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP14'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP15', 'Distinguir fatos de opiniões/sugestões em textos (informativos, jornalísticos, publicitários etc.).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP15'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP16', 'Produzir notícias sobre fatos ocorridos no universo escolar, digitais ou impressas, para o jornal da escola, noticiando os fatos e seus atores e comentando decorrências, de acordo com as convenções do gênero notícia e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP16'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP16';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP17', 'Produzir jornais radiofônicos ou televisivos e entrevistas veiculadas em rádio, TV e na internet, orientando-se por roteiro ou texto e demonstrando conhecimento dos gêneros jornal falado/televisivo e entrevista.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP17'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP17';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP18', 'Analisar o padrão entonacional e a expressão facial e corporal de âncoras de jornais radiofônicos ou televisivos e de entrevistadores/entrevistados.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP18'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP18';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP19', 'Ler e compreender textos expositivos de divulgação científica para crianças, considerando a situação comunicativa e o tema/ assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP19'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP19';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP20', 'Reconhecer a função de gráficos, diagramas e tabelas em textos, como forma de apresentação de dados e informações.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP20'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP20';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP21', 'Planejar e produzir textos sobre temas de interesse, com base em resultados de observações e pesquisas em fontes de informações impressas ou eletrônicas, incluindo, quando pertinente, imagens e gráficos ou tabelas simples, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP21'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP21';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP22', 'Planejar e produzir, com certa autonomia, verbetes de enciclopédia infantil, digitais ou impressos, considerando a situação comunicativa e o tema/ assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP22'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP22';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP23', 'Identificar e reproduzir, em verbetes de enciclopédia infantil, digitais ou impressos, a formatação e diagramação específica desse gênero (título do verbete, definição, detalhamento, curiosidades), considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP23'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP23';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP24', 'Identificar e reproduzir, em seu formato, tabelas, diagramas e gráficos em relatórios de observação e pesquisa, como forma de apresentação de dados e informações.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP24'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP24';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP25', 'Planejar e produzir, com certa autonomia, verbetes de dicionário, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP25'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP25';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP26', 'Observar, em poemas concretos, o formato, a distribuição e a diagramação das letras do texto na página.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP26'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP26';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF04LP27', 'Identificar, em textos dramáticos, marcadores das falas das personagens e de cena.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF04LP27'); -- Única: 4º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'b8cdea4d-22fe-4647-a9f3-c575eb82c514' FROM public.skills WHERE code = 'EF04LP27';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP01', 'Grafar palavras utilizando regras de correspondência fonema-grafema regulares, contextuais e morfológicas e palavras de uso frequente com correspondências irregulares.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP01'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP01';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP02', 'Identificar o caráter polissêmico das palavras (uma mesma palavra com diferentes significados, de acordo com o contexto de uso), comparando o significado de determinados termos utilizados nas áreas científicas com esses mesmos termos utilizados na linguagem usual.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP02'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP02';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP03', 'Acentuar corretamente palavras oxítonas, paroxítonas e proparoxítonas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP03'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP03';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP04', 'Diferenciar, na leitura de textos, vírgula, ponto e vírgula, dois-pontos e reconhecer, na leitura de textos, o efeito de sentido que decorre do uso de reticências, aspas, parênteses.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP04'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP04';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP05', 'Identificar a expressão de presente, passado e futuro em tempos verbais do modo indicativo.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP05'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP05';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP06', 'Flexionar, adequadamente, na escrita e na oralidade, os verbos em concordância com pronomes pessoais/nomes sujeitos da oração.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP06'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP06';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP07', 'Identificar, em textos, o uso de conjunções e a relação que estabelecem entre partes do texto: adição, oposição, tempo, causa, condição, finalidade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP07'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP07';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP08', 'Diferenciar palavras primitivas, derivadas e compostas, e derivadas por adição de prefixo e de sufixo.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP08'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP08';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP09', 'Ler e compreender, com autonomia, textos instrucionais de regras de jogo, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP09'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP09';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP10', 'Ler e compreender, com autonomia, anedotas, piadas e cartuns, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP10'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP10';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP11', 'Registrar, com autonomia, anedotas, piadas e cartuns, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP11'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP11';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP12', 'Planejar e produzir, com autonomia, textos instrucionais de regras de jogo, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP12'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP12';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP13', 'Assistir, em vídeo digital, a postagem de vlog infantil de críticas de brinquedos e livros de literatura infantil e, a partir dele, planejar e produzir resenhas digitais em áudio ou vídeo.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP13'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP13';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP14', 'Identificar e reproduzir, em textos de resenha crítica de brinquedos ou livros de literatura infantil, a formatação própria desses textos (apresentação e avaliação do produto).', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP14'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP14';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP15', 'Ler/assistir e compreender, com autonomia, notícias, reportagens, vídeos em vlogs argumentativos, dentre outros gêneros do campo político-cidadão, de acordo com as convenções dos gêneros e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP15'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP15';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP16', 'Comparar informações sobre um mesmo fato veiculadas em diferentes mídias e concluir sobre qual é mais confiável e por quê.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP16'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP16';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP17', 'Produzir roteiro para edição de uma reportagem digital sobre temas de interesse da turma, a partir de buscas de informações, imagens, áudios e vídeos na internet, de acordo com as convenções do gênero e considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP17'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP17';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP18', 'Roteirizar, produzir e editar vídeo para vlogs argumentativos sobre produtos de mídia para público infantil (filmes, desenhos animados, HQs, games etc.), com base em conhecimentos sobre os mesmos, de acordo com as convenções do gênero e considerando a situação comunicativa e o tema/ assunto/finalidade do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP18'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP18';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP19', 'Argumentar oralmente sobre acontecimentos de interesse social, com base em conhecimentos sobre fatos divulgados em TV, rádio, mídia impressa e digital, respeitando pontos de vista diferentes.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP19'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP19';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP20', 'Analisar a validade e força de argumentos em argumentações sobre produtos de mídia para público infantil (filmes, desenhos animados, HQs, games etc.), com base em conhecimentos sobre os mesmos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP20'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP20';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP21', 'Analisar o padrão entonacional, a expressão facial e corporal e as escolhas de variedade e registro linguísticos de vloggers de vlogs opinativos ou argumentativos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP21'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP21';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP22', 'Ler e compreender verbetes de dicionário, identificando a estrutura, as informações gramaticais (significado de abreviaturas) e as informações semânticas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP22'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP22';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP23', 'Comparar informações apresentadas em gráficos ou tabelas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP23'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP23';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP24', 'Planejar e produzir texto sobre tema de interesse, organizando resultados de pesquisa em fontes de informação impressas ou digitais, incluindo imagens e gráficos ou tabelas, considerando a situação comunicativa e o tema/assunto do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP24'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP24';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP25', 'Representar cenas de textos dramáticos, reproduzindo as falas das personagens, de acordo com as rubricas de interpretação e movimento indicadas pelo autor.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP25'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP25';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP26', 'Utilizar, ao produzir o texto, conhecimentos linguísticos e gramaticais: regras sintáticas de concordância nominal e verbal, convenções de escrita de citações, pontuação (ponto final, dois-pontos, vírgulas em enumerações) e regras ortográficas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP26'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP26';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP27', 'Utilizar, ao produzir o texto, recursos de coesão pronominal (pronomes anafóricos) e articuladores de relações de sentido (tempo, causa, oposição, conclusão, comparação), com nível adequado de informatividade.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP27'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP27';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), 'EF05LP28', 'Observar, em ciberpoemas e minicontos infantis em mídia digital, os recursos multissemióticos presentes nesses textos digitais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = 'EF05LP28'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = 'EF05LP28';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.1', 'Identificar a ideia central do texto.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.2', 'Localizar informação explícita.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.2'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.2';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.3', 'Reconhecer diferentes gêneros textuais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.3'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.3';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.4', 'Identificar elementos constitutivos de textos narrativos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.4'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.4';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.5', 'Reconhecer diferentes modos de organização composicional de textos em versos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.5'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.5';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L1.6', 'Identificar as marcas de organização de textos dramáticos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L1.6'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L1.6';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.1', 'Analisar elementos constitutivos de gêneros textuais diversos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.2', 'Analisar relações de causa e consequência.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.2'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.2';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.3', 'Analisar o uso de recursos de persuasão em textos verbais e/ ou multimodais.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.3'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.3';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.4', 'Distinguir fatos de opiniões em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.4'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.4';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.5', 'Analisar informações apresentadas em gráficos, infográficos ou tabelas.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.5'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.5';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.6', 'Inferir informações implícitas em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.6'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.6';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.7', 'Inferir o sentido de palavras ou expressões em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.7'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.7';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.8', 'Analisar os efeitos de sentido de recursos multissemióticos em textos que circulam em diferentes suportes.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.8'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.8';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L2.9', 'Analisar a construção de sentidos de textos em versos com base em seus elementos constitutivos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L2.9'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L2.9';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5L3.1', 'Avaliar a fidedignidade de informações sobre um mesmo fato veiculadas em diferentes mídias.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5L3.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5L3.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A1.1', 'Reconhecer os usos da pontuação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A1.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A1.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A1.2', 'Reconhecer em textos o significado de palavras derivadas a partir de seus afixos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A1.2'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A1.2';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A1.3', 'Identificar as variedades linguísticas em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A1.3'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A1.3';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A1.4', 'Identificar os mecanismos de progressão textual.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A1.4'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A1.4';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A1.5', 'Identificar os mecanismos de referenciação lexical e pronominal.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A1.5'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A1.5';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A2.1', 'Analisar os efeitos de sentido decorrentes do uso da pontuação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A2.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A2.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A2.2', 'Analisar os efeitos de sentido de verbos de enunciação.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A2.2'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A2.2';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A2.3', 'Analisar os efeitos de sentido decorrentes do uso dos adjetivos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A2.3'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A2.3';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A2.4', 'Analisar os efeitos de sentido decorrentes do uso dos advérbios.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A2.4'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A2.4';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5A3.1', 'Julgar a eficácia de argumentos em textos.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5A3.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5A3.1';
INSERT INTO public.skills (id, code, description, subject_id)
SELECT gen_random_uuid(), '5P4.1', 'Pruduzir texto em língua portuguesa, de acordo com o gênero textual e o tema demandados.', '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'
WHERE NOT EXISTS (SELECT 1 FROM public.skills WHERE code = '5P4.1'); -- Única: 5º Ano
INSERT INTO public.skill_grade (skill_id, grade_id)
SELECT id, 'f5688bb2-9624-487f-ab1f-40b191c96b76' FROM public.skills WHERE code = '5P4.1';