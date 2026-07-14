import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DEFAULT_RUBRIC_CRITERIA,
  DIFFICULTY_LEVELS,
  KNOWLEDGE_AREAS,
  QUESTION_TYPES,
  SCHOOL_YEARS,
} from "@/lib/question-types";
import { useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { saveDemoQuestion, updateDemoQuestion, getDemoQuestionById } from "@/lib/demo-questions";
import { defaultInteraction, type Interaction, type InteractionType } from "@/lib/question-interactions";
import { InteractionEditor } from "@/components/interaction-editor";
import { InteractionPlayer } from "@/components/interaction-player";
import { ImageUpload } from "@/components/image-upload";
import { emptyResponse } from "@/lib/question-interactions";
import { z } from "zod";

const novaSearchSchema = z.object({ id: z.string().optional() });

export const Route = createFileRoute("/_authenticated/questoes/nova")({
  validateSearch: novaSearchSchema,
  head: () => ({ meta: [{ title: "Nova questão — AfirmePlay" }] }),
  component: NovaQuestao,
});

type Criterion = { name: string; weight: number; maxScore: number; minScore: number; notes: string };

function NovaQuestao() {
  const navigate = useNavigate();
  const { id: editingId } = Route.useSearch();
  const existing = editingId ? getDemoQuestionById(editingId) : undefined;
  const isEditing = Boolean(existing);
  const [saving, setSaving] = useState(false);

  const [questionType, setQuestionType] = useState<InteractionType>(existing?.question_type ?? "arrastar_soltar");
  const [interaction, setInteraction] = useState<Interaction>(existing?.interaction ?? defaultInteraction("arrastar_soltar"));

  const [title, setTitle] = useState(existing?.title ?? "");
  const [statement, setStatement] = useState(existing?.statement ?? "");
  const [statementImages, setStatementImages] = useState<string[]>(
    existing?.statement_images ?? (existing?.statement_image ? [existing.statement_image] : []),
  );
  const [supportText, setSupportText] = useState(existing?.support_text ?? "");
  const [area, setArea] = useState(existing?.knowledge_area ?? "");
  const [year, setYear] = useState(existing?.school_year ?? "");
  const [bncc, setBncc] = useState(existing?.bncc_code ?? "");
  const [descriptor, setDescriptor] = useState(existing?.saeb_descriptor ?? "");
  const [ability, setAbility] = useState(existing?.ability ?? "");
  const [competency, setCompetency] = useState(existing?.competency ?? "");
  const [theme, setTheme] = useState(existing?.theme ?? "");
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTY_LEVELS)[number]["value"]>(
    (existing?.difficulty as (typeof DIFFICULTY_LEVELS)[number]["value"]) ?? "basico",
  );
  const [expectedTime, setExpectedTime] = useState(existing?.expected_time_min ?? 5);
  const [weight, setWeight] = useState(existing?.weight ?? 1);
  const [rubric, setRubric] = useState<Criterion[]>(existing?.rubric ?? DEFAULT_RUBRIC_CRITERIA);

  const totalWeight = rubric.reduce((s, c) => s + Number(c.weight || 0), 0);

  function pickType(next: InteractionType) {
    setQuestionType(next);
    setInteraction(defaultInteraction(next));
  }

  function updateCriterion(i: number, patch: Partial<Criterion>) {
    setRubric((r) => r.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function removeCriterion(i: number) {
    setRubric((r) => r.filter((_, idx) => idx !== i));
  }
  function addCriterion() {
    setRubric((r) => [...r, { name: "Novo critério", weight: 10, maxScore: 10, minScore: 0, notes: "" }]);
  }

  async function handleSave(status: "rascunho" | "revisao") {
    if (!title.trim()) {
      toast.error("Informe um título para a questão.");
      return;
    }
    setSaving(true);
    const payload = {
      author_id: existing?.author_id ?? "demo-professor",
      title,
      statement,
      support_text: supportText || null,
      statement_image: statementImages[0] ?? null,
      statement_images: statementImages,
      question_type: questionType,
      knowledge_area: area || null,
      school_year: year || null,
      bncc_code: bncc || null,
      saeb_descriptor: descriptor || null,
      ability: ability || null,
      competency: competency || null,
      theme: theme || null,
      difficulty,
      expected_time_min: expectedTime,
      weight,
      value: weight,
      rubric,
      interaction,
      status,
    };
    if (isEditing && editingId) {
      updateDemoQuestion(editingId, payload);
      toast.success("Questão atualizada.");
    } else {
      saveDemoQuestion(payload);
      toast.success("Questão criada. Agora responda como aluno.");
    }
    setSaving(false);
    navigate({ to: isEditing ? "/questoes" : "/aluno" });
  }

  // preview response state (not persisted)
  const [previewResp, setPreviewResp] = useState(() => emptyResponse(interaction));
  // reset preview when interaction type changes
  if (previewResp.type !== interaction.type) {
    setPreviewResp(emptyResponse(interaction));
  }

  return (
    <AppShell>
      <section className="px-4 py-6 md:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-6">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <button
                onClick={() => navigate({ to: "/questoes" })}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Voltar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <div className="min-w-0">
                <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">
                  {isEditing ? "Editar questão" : "Nova questão"}
                </h1>
                <p className="text-xs text-muted-foreground">
                  Configure a interação real que o aluno vai responder.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="outline" onClick={() => handleSave("rascunho")} disabled={saving}>
                Salvar rascunho
              </Button>
              <Button
                onClick={() => handleSave("revisao")}
                disabled={saving}
                className="bg-brand text-brand-foreground hover:brightness-110"
              >
                {isEditing ? "Salvar alterações" : "Enviar para revisão"}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="flex flex-col gap-6 lg:col-span-8">
              {/* Type picker */}
              <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Tipo de questão
                  </h3>
                  <span className="text-[10px] text-muted-foreground">
                    {QUESTION_TYPES.length} tipos
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
                  {QUESTION_TYPES.map((t) => {
                    const selected = questionType === t.value;
                    return (
                      <button
                        key={t.value}
                        type="button"
                        onClick={() => pickType(t.value)}
                        className={`flex flex-col items-start gap-2 rounded-xl border p-3 text-left transition-all ${
                          selected
                            ? "border-brand bg-brand-light ring-1 ring-brand"
                            : "border-border bg-card hover:border-brand/30"
                        }`}
                      >
                        <div
                          className={`grid h-8 w-8 place-items-center rounded-lg text-xs font-bold ${
                            selected ? "bg-brand text-brand-foreground" : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {t.label[0]}
                        </div>
                        <div className="text-[11px] font-semibold leading-tight">{t.label}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Enunciado */}
              <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="title" className="text-xs font-semibold uppercase tracking-wider">
                      Título
                    </Label>
                    <Input
                      id="title"
                      placeholder="Ex.: Complete as palavras das brincadeiras"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider">Enunciado</Label>
                    <Textarea
                      placeholder="Escreva o enunciado (comando) da questão…"
                      value={statement}
                      onChange={(e) => setStatement(e.target.value)}
                      className="min-h-[100px]"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider">
                      Imagens do enunciado (adicione quantas quiser)
                    </Label>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {statementImages.map((img, i) => (
                        <ImageUpload
                          key={i}
                          aspect="wide"
                          value={img}
                          onChange={(url) => {
                            if (url) setStatementImages(statementImages.map((x, k) => (k === i ? url : x)));
                            else setStatementImages(statementImages.filter((_, k) => k !== i));
                          }}
                          label="Imagem"
                        />
                      ))}
                      <ImageUpload
                        aspect="wide"
                        value={null}
                        onChange={(url) => {
                          if (url) setStatementImages([...statementImages, url]);
                        }}
                        label={statementImages.length ? "+ Imagem" : "Adicionar imagem"}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider">
                      Texto de apoio (opcional)
                    </Label>
                    <Textarea
                      placeholder="Contexto, tabela ou trecho de referência…"
                      value={supportText}
                      onChange={(e) => setSupportText(e.target.value)}
                      className="min-h-[70px]"
                    />
                  </div>
                </div>
              </div>

              {/* Interaction editor */}
              <InteractionEditor value={interaction} onChange={setInteraction} />

              {/* Live preview */}
              <div className="rounded-2xl border border-dashed border-brand/40 bg-brand-light/40 p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-brand">
                    Pré-visualização (como o aluno verá)
                  </h3>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setPreviewResp(emptyResponse(interaction))}
                  >
                    Limpar
                  </Button>
                </div>
                <InteractionPlayer interaction={interaction} value={previewResp} onChange={setPreviewResp} />
              </div>
            </div>

            {/* Right column: pedagogy + rubric */}
            <div className="flex flex-col gap-4 lg:col-span-4">
              <Tabs defaultValue="pedagogia" className="w-full">
                <TabsList className="w-full">
                  <TabsTrigger value="pedagogia" className="flex-1">Pedagógico</TabsTrigger>
                  <TabsTrigger value="rubrica" className="flex-1">Rubrica</TabsTrigger>
                </TabsList>

                <TabsContent value="pedagogia" className="mt-3">
                  <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                    <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Identificação pedagógica
                    </h3>
                    <div className="flex flex-col gap-3">
                      <FieldGroup label="Área de conhecimento">
                        <Select value={area} onValueChange={setArea}>
                          <SelectTrigger><SelectValue placeholder="Selecione..." /></SelectTrigger>
                          <SelectContent>
                            {KNOWLEDGE_AREAS.map((a) => (
                              <SelectItem key={a} value={a}>{a}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <FieldGroup label="Ano/Série">
                        <Select value={year} onValueChange={setYear}>
                          <SelectTrigger><SelectValue placeholder="Selecione..." /></SelectTrigger>
                          <SelectContent>
                            {SCHOOL_YEARS.map((y) => (
                              <SelectItem key={y} value={y}>{y}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <div className="grid grid-cols-2 gap-3">
                        <FieldGroup label="BNCC">
                          <Input value={bncc} onChange={(e) => setBncc(e.target.value)} placeholder="EF02LP01" />
                        </FieldGroup>
                        <FieldGroup label="Descritor SAEB">
                          <Input value={descriptor} onChange={(e) => setDescriptor(e.target.value)} placeholder="D1" />
                        </FieldGroup>
                      </div>
                      <FieldGroup label="Habilidade">
                        <Input value={ability} onChange={(e) => setAbility(e.target.value)} />
                      </FieldGroup>
                      <FieldGroup label="Competência">
                        <Input value={competency} onChange={(e) => setCompetency(e.target.value)} />
                      </FieldGroup>
                      <FieldGroup label="Tema">
                        <Input value={theme} onChange={(e) => setTheme(e.target.value)} />
                      </FieldGroup>
                      <Separator />
                      <FieldGroup label="Dificuldade">
                        <Select value={difficulty} onValueChange={(v) => setDifficulty(v as typeof difficulty)}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {DIFFICULTY_LEVELS.map((d) => (
                              <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <div className="grid grid-cols-2 gap-3">
                        <FieldGroup label="Tempo (min)">
                          <Input type="number" value={expectedTime} onChange={(e) => setExpectedTime(Number(e.target.value) || 0)} />
                        </FieldGroup>
                        <FieldGroup label="Peso / Valor">
                          <Input type="number" step="0.5" value={weight} onChange={(e) => setWeight(Number(e.target.value) || 0)} />
                        </FieldGroup>
                      </div>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="rubrica" className="mt-3">
                  <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          Rubrica de avaliação
                        </h3>
                        <p className={`mt-1 text-[10px] font-medium ${totalWeight === 100 ? "text-emerald-600" : "text-amber-600"}`}>
                          Soma dos pesos: {totalWeight}% {totalWeight === 100 ? "✓" : "(ideal 100%)"}
                        </p>
                      </div>
                      <Button size="sm" variant="outline" onClick={addCriterion}>
                        <Plus className="mr-1 h-3.5 w-3.5" /> Critério
                      </Button>
                    </div>
                    <div className="flex flex-col gap-3">
                      {rubric.map((c, i) => (
                        <div key={i} className="rounded-lg border border-border bg-background p-3">
                          <div className="flex items-start gap-2">
                            <Input value={c.name} onChange={(e) => updateCriterion(i, { name: e.target.value })} className="h-8 text-sm font-medium" />
                            <button onClick={() => removeCriterion(i)} className="grid h-8 w-8 shrink-0 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <div className="mt-2 grid grid-cols-3 gap-2">
                            <MiniField label="Peso %">
                              <Input type="number" className="h-8" value={c.weight} onChange={(e) => updateCriterion(i, { weight: Number(e.target.value) || 0 })} />
                            </MiniField>
                            <MiniField label="Máx">
                              <Input type="number" className="h-8" value={c.maxScore} onChange={(e) => updateCriterion(i, { maxScore: Number(e.target.value) || 0 })} />
                            </MiniField>
                            <MiniField label="Mín">
                              <Input type="number" className="h-8" value={c.minScore} onChange={(e) => updateCriterion(i, { minScore: Number(e.target.value) || 0 })} />
                            </MiniField>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}
function MiniField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}
