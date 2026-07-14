import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, Trash2 } from "lucide-react";
import { ImageUpload } from "@/components/image-upload";
import type { Interaction } from "@/lib/question-interactions";

type Props = {
  value: Interaction;
  onChange: (next: Interaction) => void;
};

export function InteractionEditor({ value, onChange }: Props) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Interação do aluno · {labelFor(value.type)}
      </h3>
      <div className="flex flex-col gap-4">{renderEditor(value, onChange)}</div>
      <p className="mt-4 text-[11px] text-muted-foreground">
        Este é o conteúdo que o aluno realmente vai responder. Configure-o antes de simular.
      </p>
    </div>
  );
}

function labelFor(type: string) {
  const map: Record<string, string> = {
    dissertativa: "Dissertativa",
    multipla_escolha: "Múltipla escolha",
    arrastar_soltar: "Arrastar e soltar",
    completar_lacunas: "Completar lacunas",
    ligar_colunas: "Ligar colunas",
    ordenacao: "Ordenação",
    substituicao: "Substituição",
    destacar_trechos: "Destacar trechos",
    escrita_matematica: "Escrita matemática",
    construcao_resposta: "Construção em etapas",
  };
  return map[type] ?? type;
}

function renderEditor(v: Interaction, on: (n: Interaction) => void) {
  switch (v.type) {
    case "dissertativa":
      return (
        <>
          <Label className="text-xs">Palavras-chave esperadas (separadas por vírgula)</Label>
          <Input
            value={v.keywords.join(", ")}
            onChange={(e) =>
              on({ ...v, keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
            }
          />
        </>
      );
    case "multipla_escolha":
      return (
        <>
          <div className="flex items-center gap-2">
            <Checkbox
              checked={v.multi}
              onCheckedChange={(c) => on({ ...v, multi: Boolean(c) })}
              id="mc-multi"
            />
            <Label htmlFor="mc-multi" className="text-xs">Permitir múltiplas respostas corretas</Label>
          </div>
          <div className="flex flex-col gap-3">
            {v.options.map((o, i) => (
              <div key={i} className="flex gap-3 rounded-lg border border-border bg-background p-3">
                <div className="w-32 shrink-0">
                  <ImageUpload
                    aspect="square"
                    value={o.image ?? null}
                    onChange={(url) =>
                      on({ ...v, options: v.options.map((op, idx) => (idx === i ? { ...op, image: url } : op)) })
                    }
                    label="Imagem"
                  />
                </div>
                <div className="flex flex-1 items-center gap-2">
                  <Checkbox
                    checked={o.correct}
                    onCheckedChange={(c) => {
                      const options = v.options.map((op, idx) =>
                        idx === i ? { ...op, correct: Boolean(c) } : v.multi ? op : { ...op, correct: false },
                      );
                      if (!v.multi && c) options[i].correct = true;
                      on({ ...v, options });
                    }}
                  />
                  <Input
                    value={o.text}
                    onChange={(e) =>
                      on({ ...v, options: v.options.map((op, idx) => (idx === i ? { ...op, text: e.target.value } : op)) })
                    }
                  />
                  <button
                    onClick={() => on({ ...v, options: v.options.filter((_, idx) => idx !== i) })}
                    className="grid h-8 w-8 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Remover"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, options: [...v.options, { text: "Nova alternativa", correct: false }] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Alternativa
          </Button>
        </>
      );
    case "arrastar_soltar":
      return (
        <>
          <Label className="text-xs">Instrução exibida no topo (ex.: "USE AS LETRAS DO QUADRO…")</Label>
          <Textarea
            className="min-h-[60px]"
            value={v.instruction ?? ""}
            onChange={(e) => on({ ...v, instruction: e.target.value })}
          />
          <Label className="mt-2 text-xs">Rótulo do quadro de cards (ex.: G - F - B - D - C)</Label>
          <Input
            value={v.bankLabel ?? ""}
            onChange={(e) => on({ ...v, bankLabel: e.target.value })}
          />
          <Label className="mt-2 text-xs">Cards arrastáveis (separados por vírgula)</Label>
          <Input
            value={v.bank.join(", ")}
            onChange={(e) => on({ ...v, bank: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          />
          <Label className="mt-2 text-xs">Áreas de destino (com quantas imagens quiser)</Label>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {v.slots.map((s, i) => {
              const imgs = s.images ?? (s.image ? [s.image] : []);
              const updateImages = (next: string[]) =>
                on({
                  ...v,
                  slots: v.slots.map((x, idx) =>
                    idx === i ? { ...x, images: next, image: null } : x,
                  ),
                });
              return (
                <div key={i} className="flex flex-col gap-2 rounded-lg border border-border bg-background p-3">
                  <div className="grid grid-cols-2 gap-2">
                    {imgs.map((img, k) => (
                      <ImageUpload
                        key={k}
                        aspect="wide"
                        value={img}
                        onChange={(url) => {
                          if (url) updateImages(imgs.map((x, kk) => (kk === k ? url : x)));
                          else updateImages(imgs.filter((_, kk) => kk !== k));
                        }}
                        label="Imagem"
                      />
                    ))}
                    <ImageUpload
                      aspect="wide"
                      value={null}
                      onChange={(url) => {
                        if (url) updateImages([...imgs, url]);
                      }}
                      label={imgs.length ? "+ Imagem" : "Adicionar imagem"}
                    />
                  </div>
                  <Input
                    placeholder="Rótulo (ex.: ___ALANÇO)"
                    value={s.label}
                    onChange={(e) =>
                      on({ ...v, slots: v.slots.map((x, idx) => (idx === i ? { ...x, label: e.target.value } : x)) })
                    }
                  />
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Resposta correta"
                      value={s.answer}
                      onChange={(e) =>
                        on({ ...v, slots: v.slots.map((x, idx) => (idx === i ? { ...x, answer: e.target.value } : x)) })
                      }
                    />
                    <button
                      onClick={() => on({ ...v, slots: v.slots.filter((_, idx) => idx !== i) })}
                      className="grid h-9 w-9 shrink-0 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      aria-label="Remover"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, slots: [...v.slots, { label: "Nova lacuna", answer: "", images: [] }] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Lacuna
          </Button>
        </>
      );
    case "completar_lacunas": {
      const template = v.segments.map((seg, i) => seg + (i < v.answers.length ? `{{${v.answers[i]}}}` : "")).join("");
      return (
        <>
          <Label className="text-xs">Texto com lacunas — use {"{{resposta}}"} para cada lacuna</Label>
          <Textarea
            className="min-h-[100px]"
            value={template}
            onChange={(e) => {
              const raw = e.target.value;
              const answers: string[] = [];
              const segments: string[] = [];
              let last = 0;
              const re = /\{\{([^}]*)\}\}/g;
              let m: RegExpExecArray | null;
              while ((m = re.exec(raw))) {
                segments.push(raw.slice(last, m.index));
                answers.push(m[1]);
                last = m.index + m[0].length;
              }
              segments.push(raw.slice(last));
              on({ ...v, segments, answers });
            }}
          />
          <p className="text-[11px] text-muted-foreground">Ex.: A capital do Brasil é {"{{Brasília}}"}.</p>
        </>
      );
    }
    case "ligar_colunas":
      return (
        <>
          <Label className="text-xs">Pares corretos (coluna esquerda ↔ direita) — imagem opcional em cada lado</Label>
          <div className="flex flex-col gap-3">
            {v.pairs.map((p, i) => (
              <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2 rounded-lg border border-border bg-background p-3">
                <div className="flex flex-col gap-2">
                  <ImageUpload
                    aspect="wide"
                    value={p.leftImage ?? null}
                    onChange={(url) =>
                      on({ ...v, pairs: v.pairs.map((x, idx) => (idx === i ? { ...x, leftImage: url } : x)) })
                    }
                    label="Imagem esquerda"
                  />
                  <Input
                    placeholder="Texto esquerda (opcional)"
                    value={p.left}
                    onChange={(e) =>
                      on({ ...v, pairs: v.pairs.map((x, idx) => (idx === i ? { ...x, left: e.target.value } : x)) })
                    }
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <ImageUpload
                    aspect="wide"
                    value={p.rightImage ?? null}
                    onChange={(url) =>
                      on({ ...v, pairs: v.pairs.map((x, idx) => (idx === i ? { ...x, rightImage: url } : x)) })
                    }
                    label="Imagem direita"
                  />
                  <Input
                    placeholder="Texto direita (opcional)"
                    value={p.right}
                    onChange={(e) =>
                      on({ ...v, pairs: v.pairs.map((x, idx) => (idx === i ? { ...x, right: e.target.value } : x)) })
                    }
                  />
                </div>
                <button
                  onClick={() => on({ ...v, pairs: v.pairs.filter((_, idx) => idx !== i) })}
                  className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, pairs: [...v.pairs, { left: "", right: "" }] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Par
          </Button>
        </>
      );
    case "ordenacao": {
      const imgs = v.itemImages ?? v.items.map(() => null);
      return (
        <>
          <Label className="text-xs">Itens na ORDEM correta — imagem opcional por item</Label>
          <div className="flex flex-col gap-2">
            {v.items.map((item, i) => (
              <div key={i} className="flex gap-3 rounded-lg border border-border bg-background p-3">
                <div className="w-28 shrink-0">
                  <ImageUpload
                    aspect="square"
                    value={imgs[i] ?? null}
                    onChange={(url) => {
                      const next = [...imgs];
                      next[i] = url;
                      on({ ...v, itemImages: next });
                    }}
                    label="Imagem"
                  />
                </div>
                <div className="flex flex-1 items-center gap-2">
                  <Input
                    value={item}
                    onChange={(e) => {
                      const next = [...v.items];
                      next[i] = e.target.value;
                      on({ ...v, items: next });
                    }}
                  />
                  <button
                    onClick={() => {
                      const items = v.items.filter((_, idx) => idx !== i);
                      const itemImages = imgs.filter((_, idx) => idx !== i);
                      on({ ...v, items, itemImages });
                    }}
                    className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, items: [...v.items, "Novo item"], itemImages: [...imgs, null] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Item
          </Button>
        </>
      );
    }
    case "substituicao":
      return (
        <>
          <Label className="text-xs">Frase original</Label>
          <Textarea value={v.sentence} onChange={(e) => on({ ...v, sentence: e.target.value })} />
          <Label className="mt-2 text-xs">Palavras a substituir — imagem opcional para contextualizar</Label>
          {v.targets.map((t, i) => (
            <div key={i} className="flex gap-3 rounded-lg border border-border bg-background p-3">
              <div className="w-28 shrink-0">
                <ImageUpload
                  aspect="square"
                  value={t.image ?? null}
                  onChange={(url) =>
                    on({ ...v, targets: v.targets.map((x, idx) => (idx === i ? { ...x, image: url } : x)) })
                  }
                  label="Imagem"
                />
              </div>
              <div className="grid flex-1 grid-cols-[1fr_1fr_auto] gap-2">
                <Input
                  placeholder="Original"
                  value={t.original}
                  onChange={(e) =>
                    on({ ...v, targets: v.targets.map((x, idx) => (idx === i ? { ...x, original: e.target.value } : x)) })
                  }
                />
                <Input
                  placeholder="Substituto correto"
                  value={t.replacement}
                  onChange={(e) =>
                    on({ ...v, targets: v.targets.map((x, idx) => (idx === i ? { ...x, replacement: e.target.value } : x)) })
                  }
                />
                <button
                  onClick={() => on({ ...v, targets: v.targets.filter((_, idx) => idx !== i) })}
                  className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, targets: [...v.targets, { original: "", replacement: "" }] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Substituição
          </Button>
        </>
      );
    case "destacar_trechos":
      return (
        <>
          <Label className="text-xs">Palavras / tokens (um por linha)</Label>
          <Textarea
            className="min-h-[100px]"
            value={v.tokens.join("\n")}
            onChange={(e) =>
              on({
                ...v,
                tokens: e.target.value.split("\n"),
                correctIndexes: v.correctIndexes.filter((i) => i < e.target.value.split("\n").length),
              })
            }
          />
          <Label className="mt-2 text-xs">Marque os que devem ser destacados</Label>
          <div className="flex flex-wrap gap-2">
            {v.tokens.map((tok, i) => {
              const active = v.correctIndexes.includes(i);
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() =>
                    on({
                      ...v,
                      correctIndexes: active
                        ? v.correctIndexes.filter((x) => x !== i)
                        : [...v.correctIndexes, i],
                    })
                  }
                  className={`rounded border px-2 py-1 text-xs ${active ? "border-brand bg-brand-light text-brand" : "border-border"}`}
                >
                  {tok || "∅"}
                </button>
              );
            })}
          </div>
        </>
      );
    case "escrita_matematica":
      return (
        <>
          <Label className="text-xs">Resposta esperada (número ou expressão)</Label>
          <Input value={v.expected} onChange={(e) => on({ ...v, expected: e.target.value })} />
        </>
      );
    case "construcao_resposta": {
      const imgs = v.stepImages ?? v.steps.map(() => null);
      return (
        <>
          <Label className="text-xs">Etapas — imagem opcional por etapa</Label>
          <div className="flex flex-col gap-2">
            {v.steps.map((step, i) => (
              <div key={i} className="flex gap-3 rounded-lg border border-border bg-background p-3">
                <div className="w-28 shrink-0">
                  <ImageUpload
                    aspect="square"
                    value={imgs[i] ?? null}
                    onChange={(url) => {
                      const next = [...imgs];
                      next[i] = url;
                      on({ ...v, stepImages: next });
                    }}
                    label="Imagem"
                  />
                </div>
                <div className="flex flex-1 items-center gap-2">
                  <Input
                    value={step}
                    onChange={(e) => {
                      const next = [...v.steps];
                      next[i] = e.target.value;
                      on({ ...v, steps: next });
                    }}
                  />
                  <button
                    onClick={() => {
                      const steps = v.steps.filter((_, idx) => idx !== i);
                      const stepImages = imgs.filter((_, idx) => idx !== i);
                      on({ ...v, steps, stepImages });
                    }}
                    className="grid h-9 w-9 place-items-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => on({ ...v, steps: [...v.steps, "Nova etapa"], stepImages: [...imgs, null] })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Etapa
          </Button>
        </>
      );
    }
  }
}
