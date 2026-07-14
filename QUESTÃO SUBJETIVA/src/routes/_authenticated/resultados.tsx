import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { getDemoQuestions, getDemoSubmissions } from "@/lib/demo-questions";
import { BarChart3, FileText, PenLine, Target, TrendingUp } from "lucide-react";

export const Route = createFileRoute("/_authenticated/resultados")({
  head: () => ({
    meta: [{ title: "Resultados — AfirmePlay" }],
  }),
  component: ResultadosPage,
});

function ResultadosPage() {
  const { questions, submissions, average, proficiency } = useMemo(() => {
    const demoQuestions = getDemoQuestions();
    const demoSubmissions = getDemoSubmissions();
    const avg = demoSubmissions.length
      ? demoSubmissions.reduce((sum, item) => sum + item.score, 0) / demoSubmissions.length
      : 0;
    return {
      questions: demoQuestions,
      submissions: demoSubmissions,
      average: avg,
      proficiency: Math.round(150 + avg * 25),
    };
  }, []);

  const latestQuestion = questions[0];

  return (
    <AppShell>
      <section className="px-4 py-8 md:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-8">
          <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Resultados da avaliação</h1>
              <p className="max-w-[62ch] text-sm text-muted-foreground">
                Painel demonstrativo com nota, padrão de desempenho e feedback pedagógico das respostas enviadas.
              </p>
            </div>
            <Button asChild className="bg-brand text-brand-foreground hover:brightness-110">
              <Link to="/aluno">
                <PenLine className="mr-2 h-4 w-4" /> Responder novamente
              </Link>
            </Button>
          </header>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Metric label="Questões criadas" value={questions.length} icon={FileText} />
            <Metric label="Respostas" value={submissions.length} icon={PenLine} />
            <Metric label="Média" value={submissions.length ? average.toFixed(1) : "—"} icon={Target} />
            <Metric label="Proficiência simulada" value={submissions.length ? proficiency : "—"} icon={TrendingUp} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm lg:col-span-7">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">Desempenho por resposta</h2>
                  <p className="text-sm text-muted-foreground">Correção demonstrativa baseada em critérios da rubrica.</p>
                </div>
                <BarChart3 className="h-5 w-5 text-muted-foreground" />
              </div>

              <div className="mt-5 space-y-3">
                {submissions.length === 0 && (
                  <div className="rounded-lg border border-dashed border-border p-8 text-center">
                    <p className="font-medium">Ainda não há respostas.</p>
                    <p className="mt-1 text-sm text-muted-foreground">Responda como aluno para popular este painel.</p>
                    <Button asChild className="mt-4 bg-brand text-brand-foreground hover:brightness-110">
                      <Link to="/aluno">Responder como aluno</Link>
                    </Button>
                  </div>
                )}
                {submissions.map((submission) => (
                  <div key={submission.id} className="rounded-lg border border-border bg-background p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{submission.studentName}</div>
                        <div className="text-xs text-muted-foreground">{latestQuestion?.title ?? "Questão demonstrativa"}</div>
                      </div>
                      <Badge className="bg-brand text-brand-foreground">{submission.level}</Badge>
                    </div>
                    <div className="mt-4 flex items-center gap-3">
                      <Progress value={submission.score * 10} className="h-2" />
                      <span className="w-12 text-right text-sm font-semibold tabular-nums">{submission.score}/10</span>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{submission.feedback}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside className="space-y-4 lg:col-span-5">
              <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <h2 className="font-semibold">Questão avaliada</h2>
                <div className="mt-4 rounded-lg bg-muted p-4">
                  <div className="text-sm font-medium">{latestQuestion?.title ?? "Nenhuma questão"}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {latestQuestion?.bncc_code && <Badge variant="outline">{latestQuestion.bncc_code}</Badge>}
                    {latestQuestion?.saeb_descriptor && <Badge variant="outline">{latestQuestion.saeb_descriptor}</Badge>}
                    {latestQuestion?.knowledge_area && <Badge variant="outline">{latestQuestion.knowledge_area}</Badge>}
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <h2 className="font-semibold">Leitura pedagógica</h2>
                <div className="mt-4 space-y-4">
                  <Insight label="Domínio do conteúdo" value={submissions.length ? Math.min(100, average * 10 + 8) : 0} />
                  <Insight label="Coerência da resposta" value={submissions.length ? Math.min(100, average * 10) : 0} />
                  <Insight label="Uso de procedimento" value={submissions.length ? Math.min(100, average * 9 + 5) : 0} />
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </AppShell>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="rounded-xl border border-border border-l-4 border-l-brand bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Insight({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{Math.round(value)}%</span>
      </div>
      <Progress value={value} />
    </div>
  );
}
