import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getDemoQuestions, getDemoSubmissions } from "@/lib/demo-questions";
import { BarChart3, BookMarked, CheckCircle2, Clock, FilePlus2, FileText, PenLine, Plus } from "lucide-react";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [{ title: "Dashboard — AfirmePlay" }],
  }),
  component: DashboardPage,
});

function useCounts() {
  return useQuery({
    queryKey: ["question-counts"],
    queryFn: async () => {
      const questions = getDemoQuestions();
      return {
        total: questions.length,
        aprovadas: questions.filter((q) => q.status === "aprovada").length,
        revisao: questions.filter((q) => q.status === "revisao").length,
        rascunhos: questions.filter((q) => q.status === "rascunho").length,
      };
    },
  });
}

function MetricCard({
  label,
  value,
  accent,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  accent?: "brand" | "warn" | "success" | "muted";
  icon: React.ComponentType<{ className?: string }>;
}) {
  const accentClass =
    accent === "success"
      ? "border-l-emerald-500"
      : accent === "warn"
        ? "border-l-amber-500"
        : accent === "brand"
          ? "border-l-brand"
          : "border-l-border";
  return (
    <div className={`rounded-xl border border-border border-l-4 bg-card p-4 shadow-sm ${accentClass}`}>
      <div className="flex items-start justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function DashboardPage() {
  const { data, isLoading } = useCounts();
  const respostas = typeof window === "undefined" ? 0 : getDemoSubmissions().length;

  return (
    <AppShell>
      <section className="px-4 py-8 md:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-8">
          <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
            <div className="flex min-w-0 flex-col gap-1">
              <h1 className="truncate text-2xl font-semibold tracking-tight">Visão geral</h1>
              <p className="max-w-[60ch] text-sm text-muted-foreground">
                Bem‑vindo ao AfirmePlay. Acompanhe seu acervo pedagógico e crie novas avaliações
                alinhadas à Matriz de Referência do SAEB e à BNCC.
              </p>
            </div>
            <Button asChild className="shrink-0 bg-brand text-brand-foreground hover:brightness-110">
              <Link to="/questoes/nova">
                <Plus className="mr-2 h-4 w-4" /> Nova questão
              </Link>
            </Button>
          </header>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total de questões"
              value={isLoading ? "—" : data!.total}
              accent="muted"
              icon={FileText}
            />
            <MetricCard
              label="Respostas de alunos"
              value={respostas}
              accent="success"
              icon={CheckCircle2}
            />
            <MetricCard
              label="Em revisão"
              value={isLoading ? "—" : data!.revisao}
              accent="warn"
              icon={Clock}
            />
            <MetricCard
              label="Rascunhos"
              value={isLoading ? "—" : data!.rascunhos}
              accent="muted"
              icon={FilePlus2}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Link
              to="/questoes/nova"
              className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:border-brand/40 hover:shadow-md"
            >
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-light text-brand">
                <Plus className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">Criar nova questão</h3>
                <p className="text-sm text-muted-foreground">
                  Escolha entre 10 tipos interativos e defina rubrica pedagógica.
                </p>
              </div>
            </Link>
            <Link
              to="/aluno"
              className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:border-brand/40 hover:shadow-md"
            >
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-light text-brand">
                <PenLine className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">Responder como aluno</h3>
                <p className="text-sm text-muted-foreground">
                  Abra a última questão criada e simule a experiência do estudante.
                </p>
              </div>
            </Link>
            <Link
              to="/questoes"
              className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:border-brand/40 hover:shadow-md"
            >
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-light text-brand">
                <BookMarked className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">Banco de questões</h3>
                <p className="text-sm text-muted-foreground">
                  Filtre por BNCC, descritor SAEB, dificuldade e status.
                </p>
              </div>
            </Link>
            <Link
              to="/resultados"
              className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:border-brand/40 hover:shadow-md"
            >
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-light text-brand">
                <BarChart3 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">Ver resultados</h3>
                <p className="text-sm text-muted-foreground">
                  Consulte desempenho, proficiência simulada e feedback pedagógico.
                </p>
              </div>
            </Link>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
