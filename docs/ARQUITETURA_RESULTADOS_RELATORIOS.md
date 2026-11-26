# Documentação Técnica — Centralização de Resultados e Relatórios do AfirmePlay

**Objetivo:** Garantir que todos os relatórios do AfirmePlay utilizem uma única fonte de dados e regras de negócio para leitura e cálculo de resultados.

**Serviço central:** `ResultadoEscopo`

**Regra fundamental:** Nenhum relatório deve implementar suas próprias regras de negócio para calcular, selecionar, filtrar, agregar ou classificar resultados quando já existir um serviço central responsável por essa funcionalidade.

---

## 1. Princípio fundamental

O AfirmePlay possui diferentes relatórios que precisam apresentar os mesmos indicadores para uma mesma avaliação e escopo.

Exemplos:

- Relatório consolidado.
- Relatório comparativo.
- Relatório de evolução.
- Rankings.
- Dashboard.
- Boletins.
- Relatórios por escola, série e turma.
- Mapa de proficiência.
- Relatórios detalhados.

Esses relatórios não podem implementar interpretações diferentes das regras de resultados.

Para isso, o projeto possui uma arquitetura centralizada, tendo o `ResultadoEscopo` como fachada de leitura dos resultados.

### Regra obrigatória

Antes de implementar qualquer funcionalidade relacionada a resultados, o desenvolvedor deve:

1. Verificar se o `ResultadoEscopo` já fornece os dados necessários.
2. Verificar se existe um serviço especializado responsável pelo cálculo desejado.
3. Reutilizar a implementação existente.
4. Caso a funcionalidade ainda não exista, avaliar se ela deve ser incorporada a um serviço especializado.
5. Somente depois disponibilizar o novo dado através do `ResultadoEscopo`.

**É proibido criar uma implementação independente dentro de um relatório para resolver uma necessidade que pertence à camada central de resultados.**

---

## 2. Arquitetura e responsabilidades

O `ResultadoEscopo` é uma fachada que coordena serviços especializados. Ele não deve concentrar toda a lógica de negócio em uma única classe.

### 2.1. ResultadoEscopo

Responsável por fornecer uma visão consistente dos resultados de uma avaliação.

Suas responsabilidades incluem:

- Resolver o contexto da avaliação.
- Identificar o universo de alunos.
- Determinar a elegibilidade dos alunos.
- Selecionar resultados válidos.
- Aplicar as regras de ADAP.
- Deduplicar resultados.
- Coordenar os cálculos individuais.
- Coordenar as agregações hierárquicas.
- Disponibilizar os indicadores de participação.
- Fornecer os dados consolidados aos relatórios.

O serviço deve reutilizar os módulos especializados existentes.

### 2.2. Serviços especializados

Os módulos abaixo possuem responsabilidades que devem ser preservadas e reutilizadas.

| Serviço | Responsabilidade |
|---|---|
| `ResultadoEscopo` | Fachada central de leitura dos resultados |
| `school_equal_weight_means.py` | Agregações hierárquicas pela Regra B |
| `participation_census.py` | Censo e cálculo de participação |
| `alunos_resultado_filtro.py` | Seleção e filtragem de alunos |
| `adap_resultado_pareado.py` | Associação e validação dos resultados ADAP |
| `evaluation_result_snapshot.py` | Preservação do contexto histórico dos resultados |
| `app/services/evaluation_calculator.py` | Cálculos individuais, proficiência, notas e classificação |

**Importante:** Se uma regra precisar de correção, corrija o serviço responsável por ela. Não reproduza a lógica em outro módulo.

---

## 3. Como um relatório deve consumir os resultados

Um relatório deve ser um consumidor dos dados centralizados, não uma segunda implementação do mecanismo de resultados.

### Responsabilidades permitidas aos relatórios

- Apresentação dos dados.
- Gráficos e indicadores visuais.
- Ordenação.
- Paginação.
- Formatação.
- Filtros de apresentação.
- Organização das informações.
- Exportação para PDF, Excel e outros formatos.

### Responsabilidades que não devem ser implementadas nos relatórios

- Reconstruir o universo de alunos.
- Determinar quais alunos são elegíveis.
- Selecionar resultados regulares ou ADAP.
- Implementar deduplicação.
- Identificar alunos faltantes.
- Calcular participação.
- Calcular proficiência.
- Calcular notas.
- Implementar cortes de classificação.
- Criar médias hierárquicas.
- Resolver transferências e histórico.
- Implementar regras alternativas de agregação.

Essas operações pertencem à camada central de resultados.

### Exemplo de arquitetura desejada

```text
                 RELATÓRIO
                     |
                     v
              ResultadoEscopo
                     |
          +----------+----------+
          |          |          |
          v          v          v
       Universo   Resultados  Participação
          |          |          |
          v          v          v
      Filtros      ADAP       Censo
                     |
                     v
             EvaluationCalculator
                     |
                     v
             Agregador Regra B
                     |
                     v
              Dados consolidados
                     |
                     v
                 RELATÓRIO
```

O relatório recebe os dados calculados e apenas decide como apresentá-los.

---

## 4. Regras oficiais de negócio

Todos os relatórios devem respeitar as regras abaixo, sem criar exceções locais.

### 4.1. Universo de alunos

Uma avaliação é considerada disponibilizada para uma turma quando existe o vínculo entre avaliação e turma.

O universo considera:

- Alunos matriculados quando a avaliação foi vinculada.
- Alunos matriculados posteriormente, enquanto a avaliação estiver disponibilizada.
- Alunos que saíram posteriormente, preservando sua participação histórica.

Não entram no universo alunos que saíram da turma antes da disponibilização da avaliação.

A identidade do aluno deve ser baseada em `student_id`, nunca no nome.

**Importante:** Estar no universo não significa ter realizado a avaliação.

### 4.2. Transferências e histórico

Um resultado pertence à avaliação e à colocação escolar em que foi produzido.

Portanto:

- Transferências não deslocam resultados antigos.
- O aluno não herda resultados anteriores ao ingressar em outra turma.
- Resultados históricos permanecem associados à escola, turma e série originais.
- O resultado não pode depender exclusivamente da matrícula atual.

Snapshots históricos devem preservar, quando aplicável:

- `student_id`.
- Escola.
- Turma.
- Série.
- Matrícula.
- Nome histórico do aluno.

Resultados legados sem snapshot devem ser tratados explicitamente. Nunca devem ser associados silenciosamente à turma atual.

### 4.3. Exclusão de alunos

A exclusão comum é lógica, por meio de inativação.

Alunos inativos deixam de aparecer nas listagens de ativos e não recebem novas matrículas ou avaliações enquanto estiverem inativos.

Entretanto, resultados, respostas, sessões e históricos existentes devem ser preservados.

Não realizar exclusão física automática de registros históricos.

### 4.4. ADAP

A condição ADAP deve ser determinada exclusivamente pelo cadastro do aluno.

As categorias são mutuamente exclusivas:

- Regular: utiliza resultado regular.
- ADAP 1: utiliza resultado ADAP correspondente.
- ADAP 2: utiliza resultado ADAP correspondente.
- ADAP 3: não participa de avaliações objetivas nem de cartões-resposta.

Um aluno nunca deve possuir simultaneamente um resultado regular e ADAP para a mesma avaliação.

Regras obrigatórias:

- Não inferir ADAP pelo tipo de resultado encontrado.
- Não exigir resultado regular para aceitar um resultado ADAP.
- Não contar o mesmo aluno duas vezes.
- Não gerar nota zero para ausência de resultado.
- Validar a compatibilidade entre cadastro, nível ADAP e tipo de avaliação.
- Preservar os fluxos subjetivos existentes, especialmente para ADAP3.

Inconsistências legadas devem ser identificadas, sem exclusões ou correções destrutivas automáticas.

### 4.5. Contexto da avaliação

Cada avaliação pertence a um único curso, mesmo quando contempla várias séries.

O curso deve ser resolvido a partir da própria avaliação.

Utilizar o contexto centralizado, incluindo:

- `course_name`.
- `has_matematica`.
- Modalidade.
- Escala aplicável.

Não inferir o curso misturando os cursos cadastrados na escola.

---

## 5. Cálculo individual

O único serviço autorizado a determinar os cálculos individuais é:

`app/services/evaluation_calculator.py`

Não criar fórmulas alternativas nos relatórios.

### 5.1. Proficiência

A proficiência é calculada por:

```python
proficiencia = (acertos / total_questoes) * teto_disciplina
```

| Etapa | Matemática | Outras disciplinas |
|---|---:|---:|
| Infantil | 375 | 350 |
| Anos Iniciais | 375 | 350 |
| Especial | 375 | 350 |
| EJA | 375 | 350 |
| Anos Finais | 425 | 400 |
| Ensino Médio | 425 | 400 |

### 5.2. Nota padrão

A fórmula oficial é:

```python
nota = ((proficiencia - base) / divisor) * 10
```

O resultado deve ser limitado ao intervalo de 0 a 10.

| Etapa | Disciplina | Base | Divisor |
|---|---|---:|---:|
| Infantil, Iniciais, Especial e EJA | Matemática | 60 | 262 |
| Infantil, Iniciais, Especial e EJA | Outras | 49 | 275 |
| Anos Finais e Ensino Médio | Todas | 100 | 300 |

### 5.3. Modo simple

O modo `simple` utiliza a proporção de acertos:

```python
nota = (acertos / total_questoes) * 10
```

O modo deve ser respeitado inclusive em avaliações multidisciplinares.

### 5.4. Classificação

Utilizar exclusivamente:

- `CLASSIFICATION_CONFIG`.
- Função oficial de classificação.

É proibido criar cortes numéricos próprios nos relatórios.

O arredondamento deve acontecer no ponto definido pelo cálculo canônico, antes da classificação.

---

## 6. Regra B: agregação hierárquica

A regra oficial de agregação do AfirmePlay é a média aritmética simples da proficiência do nível imediatamente inferior.

Hierarquia:

```text
Aluno
  |
  v
Turma
  |
  v
Série
  |
  v
Escola
  |
  v
Município
```

| Nível | Regra |
|---|---|
| Turma | Média das proficiências dos alunos com resultados válidos |
| Série | Média das proficiências das turmas |
| Escola | Média das proficiências das séries |
| Município | Média das proficiências das escolas |

Cada unidade do nível inferior possui o mesmo peso, independentemente da quantidade de alunos.

### Exemplo

Uma série possui duas turmas:

- Turma A: proficiência 200.
- Turma B: proficiência 300.

A proficiência da série será:

```python
proficiencia_serie = (200 + 300) / 2
# 250
```

Não ponderar pela quantidade de alunos.

### 6.1. Nota agregada

A nota de cada nível deve ser calculada a partir da proficiência média daquele próprio nível.

```python
nota_turma = calculate_grade(proficiencia_media_turma)

nota_serie = calculate_grade(proficiencia_media_serie)

nota_escola = calculate_grade(proficiencia_media_escola)

nota_municipio = calculate_grade(proficiencia_media_municipio)
```

É proibido:

```python
nota_serie = media(notas_das_turmas)
```

Também é proibido:

```sql
AVG(grade)
```

ou implementar agregações de proficiência diretamente em consultas SQL fora do agregador oficial.

### 6.2. GERAL multidisciplinar

A mesma regra se aplica ao indicador GERAL individual.

O cálculo correto é:

1. Obter as proficiências das disciplinas do aluno.
2. Calcular a média simples dessas proficiências.
3. Aplicar `calculate_grade()` sobre a proficiência média.

Não calcular a média das notas disciplinares.

**O serviço `school_equal_weight_means.py` é a referência para agregações hierárquicas.**

Não criar outra implementação da Regra B.

---

## 7. Participação e censo

A participação deve ser calculada exclusivamente pelo serviço:

`participation_census.py`

Fórmula oficial:

```python
participacao = (avaliados / matriculados) * 100
```

### Regras

- Faltantes entram no denominador.
- Alunos sem resultado não entram nas médias de proficiência.
- Não criar resultados com nota zero.
- Avaliação não disponibilizada possui status `não aplicada`.
- Avaliação disponibilizada com matriculados e nenhum avaliado possui participação de 0%.

Os estados devem diferenciar:

- Avaliado.
- Faltante.
- Ausente.
- Pendente.
- Inconsistente.
- Não aplicada.

### Agregações de participação

Para calcular a participação de uma série, escola ou município, somar os avaliados e matriculados antes de calcular o percentual.

Exemplo:

```python
participacao = (
    total_avaliados / total_matriculados
) * 100
```

Não utilizar a média dos percentuais das turmas ou escolas.

Os fluxos online e cartão-resposta devem utilizar a mesma regra.

---

## 8. Identidade e agrupamento das unidades

Os relatórios devem respeitar as identidades oficiais das entidades.

### Turmas

A identidade da turma deve considerar seu identificador e sua escola.

Duas turmas de escolas diferentes nunca podem ser confundidas, mesmo que possuam o mesmo nome.

### Séries

Séries equivalentes de escolas diferentes podem compor o mesmo agregado de série.

A identidade deve utilizar o identificador ou a classificação oficial da série.

Nunca utilizar apenas o nome da turma para determinar a série.

Exemplo:

```text
Escola X
  - 1º Ano A

Escola Y
  - 1º Ano A

Escola Z
  - 1º Ano B
```

São três turmas distintas, mas podem compor o mesmo agregado de 1º Ano.

---

## 9. Cache e invalidação

Os caches devem preservar a consistência dos resultados.

Especial atenção ao `ReportAggregateService`.

A chave de cache deve considerar os fatores que alteram os resultados:

- Avaliação.
- Escopo.
- Modalidade.
- Filtro de alunos.
- Versão do universo/roster.
- Contexto do curso.
- Filtros que alterem os resultados.

A invalidação deve ocorrer quando houver:

- Matrícula.
- Transferência.
- Mudança de turma.
- Vinculação ou remoção de avaliação.
- Alteração do nível ADAP.
- Alteração de educação especial.
- Inclusão ou correção de resultado.
- Exclusão lógica de resultado.
- Alteração de respostas que exija recálculo.

Não introduzir mecanismos complexos de cache antes de garantir a correção dos dados sem cache.

---

## 10. Regras para novos relatórios

Todo novo relatório deve seguir obrigatoriamente este fluxo:

1. Identificar a avaliação e o escopo solicitado.
2. Consultar o `ResultadoEscopo`.
3. Obter o universo e os resultados válidos.
4. Consumir os indicadores individuais e agregados disponibilizados.
5. Utilizar os dados de participação fornecidos pelo serviço central.
6. Aplicar apenas filtros de apresentação e organização visual.
7. Apresentar os resultados sem recalcular regras de negócio.

### Checklist obrigatório antes de implementar

- [ ] Verifiquei se o `ResultadoEscopo` já fornece os dados necessários.
- [ ] Verifiquei os serviços especializados existentes.
- [ ] Não implementei uma nova seleção de alunos.
- [ ] Não implementei uma nova deduplicação de resultados.
- [ ] Não implementei cálculos próprios de proficiência.
- [ ] Não implementei cálculos próprios de notas.
- [ ] Não implementei classificações próprias.
- [ ] Não implementei médias alternativas.
- [ ] Não implementei cálculo próprio de participação.
- [ ] Não criei regras paralelas para ADAP.
- [ ] Não utilizei a matrícula atual para reconstruir resultados históricos.
- [ ] Não consultei resultados paralelamente para reconstruir indicadores já fornecidos pelo serviço central.
- [ ] Verifiquei a compatibilidade dos filtros com o universo centralizado.
- [ ] Criei testes para a funcionalidade implementada.

Se algum item não puder ser atendido, a necessidade deve ser avaliada na camada central antes de prosseguir.

---

## 11. Como agir quando faltar um indicador

Se um relatório precisar de um indicador que ainda não esteja disponível no `ResultadoEscopo`, não implemente o cálculo diretamente no relatório.

Procedimento:

1. Identificar qual serviço especializado é responsável pela informação.
2. Verificar se o serviço já possui os dados necessários.
3. Se necessário, ampliar o serviço preservando sua responsabilidade.
4. Adicionar o novo indicador ao contrato do `ResultadoEscopo`.
5. Criar testes para a nova funcionalidade.
6. Atualizar a documentação.
7. Consumir o indicador no relatório.

Exemplo:

Um relatório precisa apresentar a quantidade de alunos faltantes.

**Incorreto:**

```python
# Dentro do report_routes.py

faltantes = matriculados - resultados.count()
```

Esse cálculo pode ignorar regras de elegibilidade, ADAP, deduplicação e histórico.

**Correto:**

```python
# Dentro do relatório

escopo = resultado_escopo.obter(...)

faltantes = escopo.participacao.faltantes
```

Os nomes são ilustrativos: utilizar a API efetivamente implementada no projeto.

---

## 12. Migração dos relatórios existentes

Os relatórios existentes devem ser migrados gradualmente para utilizar o `ResultadoEscopo`.

Pontos de atenção:

- `/avaliacoes`.
- Linhas de escola e turma na listagem de avaliações.
- `report_routes.py`.
- Relatório consolidado.
- Relatório comparativo.
- Relatório de evolução.
- Rankings.
- Dashboard.
- Listagem e geração de cartão-resposta.
- Comparação de cartão-resposta.
- Boletins.
- Mapa de proficiência, quando aplicável.
- GET de avaliação/alunos.
- Relatórios detalhados.

O `report_routes.py` exige atenção especial devido à quantidade de regras próprias existentes.

A migração não deve alterar desnecessariamente o layout dos relatórios.

Relatórios subjetivos devem preservar seu comportamento atual nesta etapa, incluindo os fluxos existentes de ADAP3.

Código legado só deve ser removido depois de comprovar que nenhum consumidor depende dele.

---

## 13. Testes e consistência entre relatórios

Qualquer alteração na camada central deve possuir testes automatizados compatíveis com a regra alterada.

Os testes devem cobrir:

- Universo de alunos.
- Transferências e histórico.
- Exclusão lógica.
- ADAP.
- Proficiência.
- Nota padrão.
- Modo simple.
- Classificação.
- GERAL multidisciplinar.
- Regra B.
- Participação.
- Modalidades online e cartão-resposta.
- Cache e invalidação.

### Critério de consistência

Para uma mesma avaliação e escopo, diferentes relatórios devem apresentar os mesmos valores centrais:

| Indicador | Fonte |
|---|---|
| Universo | `ResultadoEscopo` |
| Avaliados | `participation_census.py` |
| Faltantes | `participation_census.py` |
| Participação | `participation_census.py` |
| Proficiência individual | `EvaluationCalculator` |
| Nota individual | `EvaluationCalculator` |
| Classificação | Função oficial de classificação |
| Médias hierárquicas | `school_equal_weight_means.py` |
| Resultados ADAP | `adap_resultado_pareado.py` |
| Contexto histórico | `evaluation_result_snapshot.py` |

Criar testes de regressão para verificar se relatórios diferentes apresentam os mesmos indicadores para a mesma avaliação.

---

## 14. Restrições de arquitetura

As seguintes práticas são proibidas:

1. Criar funções de cálculo de proficiência dentro de relatórios.
2. Criar funções locais de cálculo de nota.
3. Criar classificações com cortes numéricos próprios.
4. Criar médias hierárquicas fora do agregador oficial.
5. Calcular participação independentemente do censo.
6. Reconstruir o universo de alunos em cada endpoint.
7. Criar filtros ADAP independentes.
8. Criar consultas paralelas para substituir dados já fornecidos pelo `ResultadoEscopo`.
9. Utilizar a matrícula atual como substituta do histórico.
10. Criar serviços duplicados para funcionalidades já existentes.
11. Alterar regras oficiais apenas para atender a um relatório específico.

Uma necessidade específica de um relatório não justifica a criação de uma nova regra de negócio.

---

## 15. Instrução obrigatória para ferramentas de desenvolvimento com IA

Ao utilizar Cursor, agentes de IA ou outras ferramentas para implementar novos relatórios, incluir a seguinte orientação:

> Antes de implementar qualquer funcionalidade relacionada a resultados no AfirmePlay, consulte esta documentação e audite a arquitetura existente.
>
> O `ResultadoEscopo` é a fachada central obrigatória para leitura dos resultados.
>
> Não crie funções, serviços, consultas ou cálculos independentes para universo de alunos, elegibilidade, seleção de resultados, deduplicação, ADAP, proficiência, notas, classificação, participação ou agregações hierárquicas.
>
> Reutilize os serviços especializados existentes, especialmente `school_equal_weight_means.py`, `participation_census.py`, `alunos_resultado_filtro.py`, `adap_resultado_pareado.py`, `evaluation_result_snapshot.py` e `app/services/evaluation_calculator.py`.
>
> Se um indicador necessário ainda não estiver disponível, identifique o serviço responsável e amplie a implementação centralizada. Não implemente uma solução local no relatório.
>
> O relatório deve consumir os dados calculados e ficar responsável apenas pela apresentação, organização e formatação.
>
> Não altere regras oficiais, não duplique responsabilidades e não remova código legado sem verificar seus consumidores.
>
> Antes de concluir, execute os testes pertinentes e verifique se os indicadores permanecem consistentes com os demais relatórios.

---

## 16. Princípio final

A arquitetura do AfirmePlay deve garantir que exista uma única interpretação dos resultados, independentemente de onde eles sejam apresentados.

O mesmo aluno, na mesma avaliação, deve possuir o mesmo resultado, a mesma proficiência, a mesma nota e a mesma classificação em todos os relatórios.

A mesma avaliação deve possuir o mesmo universo, a mesma quantidade de avaliados, a mesma quantidade de faltantes e o mesmo percentual de participação.

**O relatório não define as regras. O relatório consome as regras.**

O `ResultadoEscopo` é a referência central de leitura, coordenando os serviços especializados responsáveis por cada regra de negócio.

Qualquer funcionalidade nova deve ampliar essa arquitetura, nunca criar uma implementação paralela.