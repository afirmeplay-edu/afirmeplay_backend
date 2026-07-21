import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getDemoQuestions } from "@/lib/demo-questions";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DIFFICULTY_LEVELS, QUESTION_TYPES, STATUS_META } from "@/lib/question-types";
import { useNavigate } from "@tanstack/react-router";
import { MoreHorizontal, Plus, Search } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/_authenticated/questoes/")({
  head: () => ({
    meta: [{ title: "Banco de Questões — AfirmePlay" }],
  }),
  component: BancoQuestoes,
});

const questionTypeLabel = Object.fromEntries(
  QUESTION_TYPES.map((t) => [t.value, t.label]),
) as Record<string, string>;

function BancoQuestoes() {
  const [statusFilter, setStatusFilter] = useState<string>("todos");
  const [areaFilter, setAreaFilter] = useState<string>("todas");
  const [difficultyFilter, setDifficultyFilter] = useState<string>("todas");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const { data: questions, isLoading } = useQuery({
    queryKey: ["questions", { statusFilter, areaFilter, difficultyFilter, search }],
    queryFn: async () => {
      const normalizedSearch = search.trim().toLowerCase();
      return getDemoQuestions()
        .filter((q) => statusFilter === "todos" || q.status === statusFilter)
        .filter((q) => areaFilter === "todas" || q.knowledge_area === areaFilter)
        .filter((q) => difficultyFilter === "todas" || q.difficulty === difficultyFilter)
        .filter((q) => !normalizedSearch || q.title.toLowerCase().includes(normalizedSearch))
        .slice(0, 50);
    },
  });

  const clearFilters = () => {
    setStatusFilter("todos");
    setAreaFilter("todas");
    setDifficultyFilter("todas");
    setSearch("");
  };

  return (
    <AppShell>
      <section className="px-4 py-8 md:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-8">
          <header className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
            <div className="flex min-w-0 flex-col gap-1">
              <h1 className="truncate text-2xl font-semibold tracking-tight">Banco de Questões</h1>
              <p className="max-w-[60ch] text-sm text-muted-foreground">
                Gerencie o acervo de itens avaliativos alinhados à Matriz de Referência do SAEB e à
                BNCC.
              </p>
            </div>
            <Button asChild className="shrink-0 bg-brand text-brand-foreground hover:brightness-110">
              <Link to="/questoes/nova">
                <Plus className="mr-2 h-4 w-4" /> Nova questão
              </Link>
            </Button>
          </header>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted p-2 ring-1 ring-border">
            <div className="relative min-w-[220px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Buscar por título..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 border-0 bg-background pl-9 ring-1 ring-border"
              />
            </div>
            <Select value={areaFilter} onValueChange={setAreaFilter}>
              <SelectTrigger className="h-9 w-[200px] border-0 bg-background ring-1 ring-border">
                <SelectValue placeholder="Área" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todas">Todas as áreas</SelectItem>
                <SelectItem value="Matemática">Matemática</SelectItem>
                <SelectItem value="Linguagens">Linguagens</SelectItem>
                <SelectItem value="Ciências da Natureza">Ciências da Natureza</SelectItem>
                <SelectItem value="Ciências Humanas">Ciências Humanas</SelectItem>
              </SelectContent>
            </Select>
            <Select value={difficultyFilter} onValueChange={setDifficultyFilter}>
              <SelectTrigger className="h-9 w-[180px] border-0 bg-background ring-1 ring-border">
                <SelectValue placeholder="Dificuldade" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todas">Todas dificuldades</SelectItem>
                {DIFFICULTY_LEVELS.map((d) => (
                  <SelectItem key={d.value} value={d.value}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-9 w-[160px] border-0 bg-background ring-1 ring-border">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos status</SelectItem>
                <SelectItem value="rascunho">Rascunho</SelectItem>
                <SelectItem value="revisao">Em revisão</SelectItem>
                <SelectItem value="aprovada">Aprovada</SelectItem>
                <SelectItem value="arquivada">Arquivada</SelectItem>
              </SelectContent>
            </Select>
            <button
              onClick={clearFilters}
              className="ml-auto px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Limpar filtros
            </button>
          </div>

          {/* Table */}
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Enunciado
                    </th>
                    <th className="px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Pedagógico
                    </th>
                    <th className="px-6 py-3 text-center text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Dificuldade
                    </th>
                    <th className="px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Status
                    </th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {isLoading && (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-sm text-muted-foreground">
                        Carregando...
                      </td>
                    </tr>
                  )}
                  {!isLoading && questions && questions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-6 py-16 text-center">
                        <div className="mx-auto flex max-w-md flex-col items-center gap-3">
                          <div className="grid h-12 w-12 place-items-center rounded-full bg-brand-light text-brand">
                            <Plus className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="font-medium">Seu banco está vazio</p>
                            <p className="text-sm text-muted-foreground">
                              Comece criando sua primeira questão alinhada ao SAEB/BNCC.
                            </p>
                          </div>
                          <Button
                            asChild
                            className="bg-brand text-brand-foreground hover:brightness-110"
                          >
                            <Link to="/questoes/nova">Nova questão</Link>
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )}
                  {questions?.map((q) => {
                    const status = STATUS_META[q.status as keyof typeof STATUS_META];
                    const diff = DIFFICULTY_LEVELS.find((d) => d.value === q.difficulty);
                    return (
                      <tr
                        key={q.id}
                        onClick={() => navigate({ to: "/questoes/nova", search: { id: q.id } })}
                        className="group cursor-pointer transition-colors hover:bg-muted/40"
                      >
                        <td className="px-6 py-4">
                          <div className="flex min-w-0 flex-col gap-1">
                            <span className="max-w-[420px] truncate text-sm font-medium">
                              {q.title || "(sem título)"}
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="rounded bg-brand-light px-1.5 py-0.5 text-[10px] font-medium text-brand">
                                {questionTypeLabel[q.question_type] ?? q.question_type}
                              </span>
                              {q.knowledge_area && (
                                <span className="text-[10px] font-medium text-muted-foreground">
                                  {q.knowledge_area}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex flex-wrap gap-1.5">
                            {q.saeb_descriptor && (
                              <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-[10px] font-semibold text-zinc-700">
                                {q.saeb_descriptor}
                              </span>
                            )}
                            {q.bncc_code && (
                              <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-semibold text-brand">
                                {q.bncc_code}
                              </span>
                            )}
                            {!q.saeb_descriptor && !q.bncc_code && (
                              <span className="text-[10px] text-muted-foreground">—</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex justify-center gap-0.5">
                            {[1, 2, 3, 4].map((n) => (
                              <div
                                key={n}
                                className={`h-1.5 w-1.5 rounded-full ${
                                  diff && n <= diff.dots ? "bg-brand" : "bg-border"
                                }`}
                              />
                            ))}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${status?.className ?? ""}`}
                          >
                            {status?.label ?? q.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate({ to: "/questoes/nova", search: { id: q.id } });
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground opacity-0 transition-all hover:bg-muted hover:text-foreground group-hover:opacity-100"
                          >
                            <MoreHorizontal className="h-3.5 w-3.5" /> Editar
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
