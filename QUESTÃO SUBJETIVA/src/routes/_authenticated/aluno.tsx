import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { getLatestDemoQuestion, saveDemoSubmission, type DemoSubmission } from "@/lib/demo-questions";
import { emptyResponse, type Response } from "@/lib/question-interactions";
import { DIFFICULTY_LEVELS, QUESTION_TYPES } from "@/lib/question-types";
import { InteractionPlayer } from "@/components/interaction-player";
import { ArrowLeft, BarChart3, Clock, RefreshCcw, SendHorizontal } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/_authenticated/aluno")({
  head: () => ({ meta: [{ title: "Responder como aluno — AfirmePlay" }] }),
  component: AlunoPage,
});

function AlunoPage() {
  const question = useMemo(() => getLatestDemoQuestion(), []);
  const [studentName, setStudentName] = useState("Aluno demonstrativo");
  const [response, setResponse] = useState<Response>(() => emptyResponse(question.interaction));
  const [submission, setSubmission] = useState<DemoSubmission | null>(null);

  const typeLabel = QUESTION_TYPES.find((item) => item.value === question.question_type)?.label ?? question.question_type;
  const difficulty = DIFFICULTY_LEVELS.find((item) => item.value === question.difficulty)?.label ?? "Médio";

  function handleSubmit() {
    const result = saveDemoSubmission({ question, studentName, response });
    setSubmission(result);
    toast.success("Resposta enviada e resultado gerado.");
  }
  function handleReset() {
    setResponse(emptyResponse(question.interaction));
    setSubmission(null);
  }

  return (
    <AppShell>
      <section className="px-4 py-8 md:px-8">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-8">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">Experiência do aluno</h1>
                <p className="text-sm text-muted-foreground">Responda a última questão criada.</p>
              </div>
              <Button asChild variant="outline">
                <Link to="/questoes/nova">
                  <ArrowLeft className="mr-2 h-4 w-4" /> Criar outra
                </Link>
              </Button>
            </div>

            <article className="rounded-xl border border-border bg-card shadow-sm">
              <header className="border-b border-border p-5">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{typeLabel}</Badge>
                  {question.knowledge_area && <Badge variant="outline">{question.knowledge_area}</Badge>}
                  {question.school_year && <Badge variant="outline">{question.school_year}</Badge>}
                  <Badge variant="outline">{difficulty}</Badge>
                </div>
                <h2 className="mt-4 text-xl font-semibold leading-snug">{question.title}</h2>
              </header>
              <div className="space-y-5 p-5">
                {question.support_text && (
                  <div className="rounded-lg border border-border bg-muted/50 p-4 text-sm leading-relaxed">
                    {question.support_text}
                  </div>
                )}
                <p className="text-base leading-relaxed text-foreground">{question.statement}</p>
                {(() => {
                  const imgs =
                    question.statement_images && question.statement_images.length
                      ? question.statement_images
                      : question.statement_image
                        ? [question.statement_image]
                        : [];
                  if (!imgs.length) return null;
                  return (
                    <div className={`grid gap-3 ${imgs.length > 1 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-1"}`}>
                      {imgs.map((img, i) => (
                        <img
                          key={i}
                          src={img}
                          alt=""
                          className="max-h-80 w-full rounded-lg border border-border object-contain"
                        />
                      ))}
                    </div>
                  );
                })()}

                <div className="rounded-lg border border-border bg-background p-4">
                  <InteractionPlayer
                    interaction={question.interaction}
                    value={response}
                    onChange={setResponse}
                    disabled={!!submission}
                  />
                </div>

                <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
                  <div className="grid gap-1.5">
                    <Label htmlFor="student-name">Nome do aluno</Label>
                    <input
                      id="student-name"
                      value={studentName}
                      onChange={(event) => setStudentName(event.target.value)}
                      className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>
                  <Button variant="outline" onClick={handleReset}>
                    <RefreshCcw className="mr-2 h-4 w-4" /> Refazer
                  </Button>
                  <Button
                    onClick={handleSubmit}
                    disabled={!!submission}
                    className="bg-brand text-brand-foreground hover:brightness-110"
                  >
                    <SendHorizontal className="mr-2 h-4 w-4" /> Enviar resposta
                  </Button>
                </div>
              </div>
            </article>
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Matriz SAEB/BNCC</h3>
              <div className="mt-4 space-y-3 text-sm">
                <InfoRow label="BNCC" value={question.bncc_code ?? "—"} />
                <InfoRow label="Descritor" value={question.saeb_descriptor ?? "—"} />
                <InfoRow label="Habilidade" value={question.ability ?? "—"} />
                <InfoRow label="Tempo" value={`${question.expected_time_min} min`} />
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Resultado da simulação
              </h3>
              {!submission ? (
                <div className="mt-4 flex items-start gap-3 rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                  <Clock className="mt-0.5 h-4 w-4 shrink-0" />
                  Envie uma resposta para gerar a nota e o feedback pedagógico.
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Nota simulada</span>
                    <span className="text-2xl font-semibold tabular-nums">{submission.score}/10</span>
                  </div>
                  <Progress value={submission.score * 10} />
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Acertos</span>
                    <span className="font-semibold">{submission.correct}/{submission.total}</span>
                  </div>
                  <Badge className="bg-brand text-brand-foreground">{submission.level}</Badge>
                  <p className="text-sm leading-relaxed text-muted-foreground">{submission.feedback}</p>
                  <Button asChild variant="outline" className="w-full">
                    <Link to="/resultados">
                      <BarChart3 className="mr-2 h-4 w-4" /> Ver painel de resultados
                    </Link>
                  </Button>
                </div>
              )}
            </div>
          </aside>
        </div>
      </section>
    </AppShell>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium leading-snug">{value}</div>
    </div>
  );
}
