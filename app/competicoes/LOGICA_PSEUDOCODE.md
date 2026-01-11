# Lógica do Módulo de Competições - Pseudo Código

## 1. CRIAÇÃO DE COMPETIÇÃO

```
FUNÇÃO criar_competicao():
    // Validações iniciais
    SE dados não fornecidos:
        RETORNAR erro 400
    
    usuario = obter_usuario_do_token()
    SE usuario não encontrado:
        RETORNAR erro 404
    
    // Validar campos obrigatórios
    SE title não existe em dados:
        RETORNAR erro 400
    
    // Processar datas
    time_limit_dt = parsear_data(dados.time_limit)
    end_time_dt = parsear_data(dados.end_time)
    
    // Criar objeto Competition
    competicao = NOVO Competition(
        title = dados.title,
        description = dados.description,
        recompensas = dados.recompensas,  // {ouro: 100, prata: 50, bronze: 25, participacao: 10}
        modo_selecao = dados.modo_selecao OU 'manual',
        status = dados.status OU 'agendada',
        time_limit = time_limit_dt,
        end_time = end_time_dt,
        duration = dados.duration,
        municipalities = dados.municipalities,
        schools = dados.schools,
        classes = dados.classes,
        max_participantes = dados.max_participantes,
        created_by = usuario.id
    )
    
    ADICIONAR competicao AO banco_de_dados
    
    // Adicionar questões se fornecidas
    SE dados.questions existe E é lista:
        PARA CADA (index, question_id) EM dados.questions:
            competition_question = NOVO CompetitionQuestion(
                competition_id = competicao.id,
                question_id = question_id,
                order = index + 1
            )
            ADICIONAR competition_question AO banco_de_dados
    
    COMMIT banco_de_dados
    
    RETORNAR sucesso COM competicao.id
FIM FUNÇÃO
```

## 2. LISTAGEM DE COMPETIÇÕES

```
FUNÇÃO listar_competicoes():
    usuario = obter_usuario_do_token()
    
    query = SELECT * FROM competitions
    
    // Aplicar filtros básicos
    SE status fornecido:
        query = query WHERE status = status
    SE subject_id fornecido:
        query = query WHERE subject = subject_id
    
    // Aplicar filtros por permissão
    SE usuario.role == 'tecadm':
        city_id = usuario.tenant_id OU usuario.city_id
        school_ids = SELECT id FROM schools WHERE city_id = city_id
        query = query WHERE schools JSON contém ALGUM school_id EM school_ids
    
    SENÃO SE usuario.role == 'diretor' OU 'coordenador':
        manager = SELECT * FROM managers WHERE user_id = usuario.id
        SE manager.school_id existe:
            query = query WHERE schools JSON contém manager.school_id
    
    SENÃO SE usuario.role == 'professor':
        teacher = SELECT * FROM teachers WHERE user_id = usuario.id
        teacher_schools = SELECT school_id FROM school_teachers WHERE teacher_id = teacher.id
        query = query WHERE schools JSON contém ALGUM school_id EM teacher_schools
    
    SENÃO SE usuario.role == 'student' OU 'aluno':
        student = SELECT * FROM students WHERE user_id = usuario.id
        SE student.class_id existe:
            query = query WHERE classes JSON contém student.class_id
        SENÃO:
            query = query WHERE FALSE  // Sem acesso
    
    competicoes = EXECUTAR query
    
    resultado = []
    PARA CADA comp EM competicoes:
        ADICIONAR {
            id: comp.id,
            title: comp.title,
            status: comp.status,
            participantes_atual: comp.participantes_atual,
            max_participantes: comp.max_participantes,
            recompensas: comp.recompensas
        } A resultado
    
    RETORNAR resultado
FIM FUNÇÃO
```

## 3. INSCRIÇÃO EM COMPETIÇÃO

```
FUNÇÃO inscrever_em_competicao(competition_id):
    usuario = obter_usuario_do_token()
    student = SELECT * FROM students WHERE user_id = usuario.id
    competicao = SELECT * FROM competitions WHERE id = competition_id
    
    // Validações
    SE competicao.status NÃO ESTÁ EM ['aberta', 'em_andamento']:
        RETORNAR erro "Competição não está aberta"
    
    SE competicao.max_participantes existe E competicao.participantes_atual >= competicao.max_participantes:
        RETORNAR erro "Limite de participantes atingido"
    
    SE student.class_id NÃO ESTÁ EM competicao.classes:
        RETORNAR erro "Turma não elegível"
    
    // Verificar se já está inscrito
    enrollment_existente = SELECT * FROM competition_enrollments 
                          WHERE competition_id = competition_id 
                          AND student_id = student.id
    
    SE enrollment_existente existe:
        RETORNAR sucesso COM enrollment_existente.id
    
    // Criar inscrição
    enrollment = NOVO CompetitionEnrollment(
        competition_id = competition_id,
        student_id = student.id,
        status = 'inscrito'
    )
    
    ADICIONAR enrollment AO banco_de_dados
    
    // Incrementar contador
    competicao.participantes_atual = competicao.participantes_atual + 1
    
    COMMIT banco_de_dados
    
    RETORNAR sucesso COM enrollment.id
FIM FUNÇÃO
```

## 4. INICIAR COMPETIÇÃO

```
FUNÇÃO iniciar_competicao(competition_id):
    usuario = obter_usuario_do_token()
    student = SELECT * FROM students WHERE user_id = usuario.id
    competicao = SELECT * FROM competitions WHERE id = competition_id
    
    // Verificar inscrição
    enrollment = SELECT * FROM competition_enrollments 
                 WHERE competition_id = competition_id 
                 AND student_id = student.id
    
    SE enrollment NÃO existe:
        RETORNAR erro "Aluno não inscrito"
    
    // Verificar se já tem sessão ativa
    session_existente = SELECT * FROM test_sessions 
                       WHERE student_id = student.id 
                       AND test_id = competition_id 
                       AND status = 'em_andamento'
    
    SE session_existente existe:
        RETORNAR sucesso COM session_existente.id
    
    // Verificar datas
    agora = DATA_ATUAL()
    SE competicao.time_limit existe E agora < competicao.time_limit:
        RETORNAR erro "Competição ainda não iniciou"
    
    SE competicao.end_time existe E agora > competicao.end_time:
        RETORNAR erro "Competição expirou"
    
    // Criar sessão
    session = NOVO TestSession(
        student_id = student.id,
        test_id = competition_id,
        time_limit_minutes = competicao.duration,
        ip_address = request.remote_addr,
        user_agent = request.user_agent
    )
    
    session.iniciar_sessao()  // Define started_at e status = 'em_andamento'
    
    // Atualizar status da inscrição
    enrollment.status = 'iniciado'
    
    ADICIONAR session AO banco_de_dados
    COMMIT banco_de_dados
    
    // Buscar questões ordenadas
    competition_questions = SELECT * FROM competition_questions 
                           WHERE competition_id = competition_id 
                           ORDER BY order
    
    questoes = []
    PARA CADA cq EM competition_questions:
        question = SELECT * FROM questions WHERE id = cq.question_id
        ADICIONAR {
            id: question.id,
            number: cq.order,
            text: question.text,
            alternatives: question.alternatives
        } A questoes
    
    RETORNAR sucesso COM {
        session_id: session.id,
        started_at: session.started_at,
        questions: questoes
    }
FIM FUNÇÃO
```

## 5. SUBMETER COMPETIÇÃO

```
FUNÇÃO submeter_competicao():
    dados = request.get_json()
    session_id = dados.session_id
    
    session = SELECT * FROM test_sessions WHERE id = session_id
    competicao = SELECT * FROM competitions WHERE id = session.test_id
    
    // Salvar respostas
    PARA CADA resposta EM dados.answers:
        question_id = resposta.question_id
        answer = resposta.answer
        
        existing_answer = SELECT * FROM student_answers 
                         WHERE student_id = session.student_id 
                         AND test_id = session.test_id 
                         AND question_id = question_id
        
        SE existing_answer existe:
            existing_answer.answer = answer
            existing_answer.answered_at = DATA_ATUAL()
        SENÃO:
            student_answer = NOVO StudentAnswer(
                student_id = session.student_id,
                test_id = session.test_id,
                question_id = question_id,
                answer = answer
            )
            ADICIONAR student_answer AO banco_de_dados
    
    // Buscar questões e respostas
    competition_questions = SELECT * FROM competition_questions 
                          WHERE competition_id = competicao.id
    questoes = [cq.question PARA CADA cq EM competition_questions]
    
    student_answers = SELECT * FROM student_answers 
                     WHERE student_id = session.student_id 
                     AND test_id = competicao.id
    
    // Calcular resultado usando serviço existente
    resultado = EvaluationResultService.calcular_resultado(
        test_id = competicao.id,
        student_id = session.student_id,
        session_id = session_id,
        questions = questoes,
        answers = student_answers
    )
    
    // Calcular métricas adicionais
    total_questions = TAMANHO(questoes)
    total_answered = TAMANHO(student_answers)
    em_branco = total_questions - total_answered
    erros = total_answered - resultado.correct_answers
    
    // Calcular tempo gasto
    tempo_gasto = (DATA_ATUAL() - session.started_at).total_seconds()
    
    // Criar CompetitionResult
    competition_result = NOVO CompetitionResult(
        competition_id = competicao.id,
        student_id = session.student_id,
        session_id = session_id,
        correct_answers = resultado.correct_answers,
        total_questions = total_questions,
        score_percentage = resultado.score_percentage,
        grade = resultado.grade,
        proficiency = resultado.proficiency,
        classification = resultado.classification,
        acertos = resultado.correct_answers,
        erros = erros,
        em_branco = em_branco,
        tempo_gasto = tempo_gasto
    )
    
    ADICIONAR competition_result AO banco_de_dados
    
    // Finalizar sessão
    session.finalizar_sessao(
        correct_answers = resultado.correct_answers,
        total_questions = resultado.total_questions
    )
    
    // Atualizar status da inscrição
    enrollment = SELECT * FROM competition_enrollments 
                 WHERE competition_id = competicao.id 
                 AND student_id = session.student_id
    enrollment.status = 'finalizado'
    
    COMMIT banco_de_dados
    
    RETORNAR sucesso COM {
        result_id: competition_result.id,
        grade: competition_result.grade,
        proficiency: competition_result.proficiency
    }
FIM FUNÇÃO
```

## 6. CÁLCULO DE RANKINGS

```
FUNÇÃO calcular_rankings_competicao(competition_id):
    // Buscar todos os resultados ordenados
    results = SELECT * FROM competition_results 
             WHERE competition_id = competition_id 
             ORDER BY grade DESC, tempo_gasto ASC
    
    competicao = SELECT * FROM competitions WHERE id = competition_id
    recompensas = competicao.recompensas
    
    // Atualizar posições e moedas
    PARA CADA (index, result) EM enumerate(results):
        posicao = index + 1
        result.posicao = posicao
        result.moedas_ganhas = calcular_moedas_ganhas(posicao, recompensas)
    
    COMMIT banco_de_dados
FIM FUNÇÃO

FUNÇÃO calcular_moedas_ganhas(posicao, recompensas):
    SE recompensas NÃO existe:
        RETORNAR 0
    
    participacao = recompensas.get('participacao', 0)
    
    SE posicao == 1:
        RETORNAR recompensas.get('ouro', 0) + participacao
    SENÃO SE posicao == 2:
        RETORNAR recompensas.get('prata', 0) + participacao
    SENÃO SE posicao == 3:
        RETORNAR recompensas.get('bronze', 0) + participacao
    SENÃO:
        RETORNAR participacao
FIM FUNÇÃO
```

## 7. LISTAR COMPETIÇÕES DISPONÍVEIS

```
FUNÇÃO listar_competicoes_disponiveis():
    usuario = obter_usuario_do_token()
    student = SELECT * FROM students WHERE user_id = usuario.id
    
    agora = DATA_ATUAL()
    
    query = SELECT * FROM competitions 
           WHERE status IN ['aberta', 'em_andamento']
           AND (time_limit IS NULL OU time_limit <= agora)
           AND (end_time IS NULL OU end_time >= agora)
    
    // Filtrar por turma do aluno
    SE student.class_id existe:
        query = query WHERE classes JSON contém student.class_id
    SENÃO:
        query = query WHERE FALSE
    
    // Filtrar por limite de participantes
    query = query WHERE (max_participantes IS NULL 
                        OU participantes_atual < max_participantes)
    
    competicoes = EXECUTAR query
    
    resultado = []
    PARA CADA comp EM competicoes:
        enrollment = SELECT * FROM competition_enrollments 
                    WHERE competition_id = comp.id 
                    AND student_id = student.id
        
        ADICIONAR {
            id: comp.id,
            title: comp.title,
            status: comp.status,
            inscrito: enrollment != NULL,
            enrollment_status: enrollment.status SE enrollment existe
        } A resultado
    
    RETORNAR resultado
FIM FUNÇÃO
```

## 8. GERAR TABELA DETALHADA DE RESULTADOS

```
FUNÇÃO gerar_tabela_detalhada_competicao(competition_id):
    competicao = SELECT * FROM competitions WHERE id = competition_id
    
    // Organizar questões por disciplina
    questoes_por_disciplina = {}
    competition_questions = SELECT * FROM competition_questions 
                           WHERE competition_id = competition_id 
                           ORDER BY order
    
    PARA CADA cq EM competition_questions:
        question = cq.question
        subject_id = question.subject_id OU 'sem_disciplina'
        
        SE subject_id NÃO ESTÁ EM questoes_por_disciplina:
            questoes_por_disciplina[subject_id] = {
                id: subject_id,
                nome: question.subject.name,
                questoes: [],
                alunos: []
            }
        
        ADICIONAR {
            numero: cq.order,
            habilidade: question.skill.description,
            question_id: question.id
        } A questoes_por_disciplina[subject_id].questoes
    
    // Buscar alunos inscritos
    enrollments = SELECT * FROM competition_enrollments 
                 WHERE competition_id = competition_id
    student_ids = [e.student_id PARA CADA e EM enrollments]
    students = SELECT * FROM students WHERE id IN student_ids
    
    // Buscar resultados
    competition_results = SELECT * FROM competition_results 
                        WHERE competition_id = competition_id
    results_dict = MAPA {r.student_id: r PARA CADA r EM competition_results}
    
    // Buscar respostas
    student_answers = SELECT * FROM student_answers 
                     WHERE test_id = competition_id 
                     AND student_id IN student_ids
    respostas_por_aluno = AGRUPAR student_answers POR student_id E question_id
    
    // Processar cada disciplina
    PARA CADA (subject_id, disciplina_data) EM questoes_por_disciplina:
        alunos_disciplina = []
        
        PARA CADA student EM students:
            competition_result = results_dict.get(student.id)
            
            respostas_por_questao = []
            total_acertos = 0
            total_erros = 0
            total_respondidas = 0
            
            PARA CADA questao_info EM disciplina_data.questoes:
                question = SELECT * FROM questions WHERE id = questao_info.question_id
                resposta_aluno = respostas_por_aluno.get(student.id, {}).get(question.id)
                
                SE resposta_aluno existe:
                    total_respondidas = total_respondidas + 1
                    acertou = verificar_resposta(resposta_aluno.answer, question.correct_answer)
                    
                    SE acertou:
                        total_acertos = total_acertos + 1
                    SENÃO:
                        total_erros = total_erros + 1
                    
                    ADICIONAR {
                        questao: questao_info.numero,
                        acertou: acertou,
                        respondeu: TRUE,
                        resposta: resposta_aluno.answer
                    } A respostas_por_questao
                SENÃO:
                    ADICIONAR {
                        questao: questao_info.numero,
                        acertou: FALSE,
                        respondeu: FALSE,
                        resposta: NULL
                    } A respostas_por_questao
            
            // Calcular nota e proficiência
            SE total_respondidas > 0:
                resultado = EvaluationCalculator.calcular_avaliacao(
                    correct_answers = total_acertos,
                    total_questions = total_respondidas,
                    course_name = competicao.course,
                    subject_name = disciplina_data.nome
                )
                nota = resultado.grade
                proficiencia = resultado.proficiency
                classificacao = resultado.classification
            SENÃO:
                nota = 0
                proficiencia = 0
                classificacao = NULL
            
            // Obter posição e moedas
            posicao = competition_result.posicao SE competition_result existe
            moedas_ganhas = competition_result.moedas_ganhas SE competition_result existe
            tempo_gasto = competition_result.tempo_gasto SE competition_result existe
            
            ADICIONAR {
                id: student.id,
                nome: student.name,
                respostas_por_questao: respostas_por_questao,
                total_acertos: total_acertos,
                total_erros: total_erros,
                nota: nota,
                proficiencia: proficiencia,
                nivel_proficiencia: classificacao,
                posicao: posicao,
                moedas_ganhas: moedas_ganhas,
                tempo_gasto: tempo_gasto
            } A alunos_disciplina
        
        disciplina_data.alunos = alunos_disciplina
    
    // Calcular dados gerais (média de todas as disciplinas)
    dados_gerais = calcular_dados_gerais_competicao(questoes_por_disciplina, competition_id)
    
    RETORNAR {
        disciplinas: VALORES(questoes_por_disciplina),
        geral: dados_gerais
    }
FIM FUNÇÃO

FUNÇÃO calcular_dados_gerais_competicao(questoes_por_disciplina, competition_id):
    dados_alunos = {}
    
    // Agregar dados de todas as disciplinas por aluno
    PARA CADA (subject_id, disciplina_data) EM questoes_por_disciplina:
        PARA CADA aluno_data EM disciplina_data.alunos:
            aluno_id = aluno_data.id
            
            SE aluno_id NÃO ESTÁ EM dados_alunos:
                dados_alunos[aluno_id] = {
                    id: aluno_id,
                    nome: aluno_data.nome,
                    notas_disciplinas: [],
                    proficiencias_disciplinas: [],
                    total_acertos_geral: 0,
                    total_questoes_geral: 0,
                    posicao: aluno_data.posicao,
                    moedas_ganhas: aluno_data.moedas_ganhas
                }
            
            ADICIONAR aluno_data.nota A dados_alunos[aluno_id].notas_disciplinas
            ADICIONAR aluno_data.proficiencia A dados_alunos[aluno_id].proficiencias_disciplinas
            dados_alunos[aluno_id].total_acertos_geral += aluno_data.total_acertos
            dados_alunos[aluno_id].total_questoes_geral += aluno_data.total_questoes_disciplina
    
    // Calcular médias
    alunos_gerais = []
    PARA CADA (aluno_id, dados) EM dados_alunos:
        SE dados.notas_disciplinas NÃO está vazio:
            nota_geral = MEDIA(dados.notas_disciplinas)
            proficiencia_geral = MEDIA(dados.proficiencias_disciplinas)
        SENÃO:
            nota_geral = 0
            proficiencia_geral = 0
        
        percentual_acertos = (dados.total_acertos_geral / dados.total_questoes_geral) * 100
        nivel_proficiencia_geral = calcular_classificacao(proficiencia_geral, course_name)
        
        ADICIONAR {
            id: dados.id,
            nome: dados.nome,
            nota_geral: nota_geral,
            proficiencia_geral: proficiencia_geral,
            nivel_proficiencia_geral: nivel_proficiencia_geral,
            total_acertos_geral: dados.total_acertos_geral,
            percentual_acertos_geral: percentual_acertos_geral,
            posicao: dados.posicao,
            moedas_ganhas: dados.moedas_ganhas
        } A alunos_gerais
    
    // Ordenar por posição (ranking)
    ORDENAR alunos_gerais POR posicao ASC
    
    RETORNAR {alunos: alunos_gerais}
FIM FUNÇÃO
```

## 9. OBTER RESULTADOS DA COMPETIÇÃO

```
FUNÇÃO obter_resultados(competition_id):
    competicao = SELECT * FROM competitions WHERE id = competition_id
    
    // Calcular rankings se necessário
    calcular_rankings_competicao(competition_id)
    
    // Gerar tabela detalhada
    tabela_detalhada = gerar_tabela_detalhada_competicao(competition_id)
    
    RETORNAR tabela_detalhada
FIM FUNÇÃO
```

## 10. VERIFICAR SE PODE INICIAR

```
FUNÇÃO pode_iniciar_competicao(competition_id):
    usuario = obter_usuario_do_token()
    student = SELECT * FROM students WHERE user_id = usuario.id
    competicao = SELECT * FROM competitions WHERE id = competition_id
    
    // Verificar inscrição
    enrollment = SELECT * FROM competition_enrollments 
                 WHERE competition_id = competition_id 
                 AND student_id = student.id
    
    SE enrollment NÃO existe:
        RETORNAR {pode_iniciar: FALSE, motivo: "Não inscrito"}
    
    SE enrollment.status == 'finalizado':
        RETORNAR {pode_iniciar: FALSE, motivo: "Já finalizado"}
    
    // Verificar datas
    agora = DATA_ATUAL()
    SE competicao.time_limit existe E agora < competicao.time_limit:
        RETORNAR {pode_iniciar: FALSE, motivo: "Ainda não iniciou"}
    
    SE competicao.end_time existe E agora > competicao.end_time:
        RETORNAR {pode_iniciar: FALSE, motivo: "Já expirou"}
    
    RETORNAR {pode_iniciar: TRUE}
FIM FUNÇÃO
```

## RESUMO DO FLUXO COMPLETO

```
1. ADMIN/PROFESSOR cria competição
   └─> Define questões, escopo, recompensas, datas

2. COMPETIÇÃO fica com status 'agendada' ou 'aberta'

3. ALUNO visualiza competições disponíveis
   └─> Filtradas por sua turma, status, datas, limite de participantes

4. ALUNO se inscreve na competição
   └─> Cria CompetitionEnrollment
   └─> Incrementa participantes_atual

5. ALUNO inicia a competição
   └─> Cria TestSession
   └─> Atualiza enrollment.status = 'iniciado'
   └─> Retorna questões ordenadas

6. ALUNO responde questões
   └─> Salva respostas em StudentAnswer

7. ALUNO submete a competição
   └─> Calcula resultado usando EvaluationResultService
   └─> Cria CompetitionResult com métricas
   └─> Finaliza TestSession
   └─> Atualiza enrollment.status = 'finalizado'

8. SISTEMA calcula rankings
   └─> Ordena por grade DESC, tempo_gasto ASC
   └─> Atribui posições
   └─> Calcula moedas ganhas por posição

9. ADMIN/PROFESSOR visualiza resultados
   └─> Tabela detalhada por disciplina
   └─> Dados gerais com ranking
   └─> Posições e moedas ganhas
```
