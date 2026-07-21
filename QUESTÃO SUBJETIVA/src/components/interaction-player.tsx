import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { Interaction, Response } from "@/lib/question-interactions";

type Props = {
  interaction: Interaction;
  value: Response;
  onChange: (next: Response) => void;
  disabled?: boolean;
};

export function InteractionPlayer({ interaction, value, onChange, disabled }: Props) {
  switch (interaction.type) {
    case "dissertativa":
      return (
        <Textarea
          disabled={disabled}
          value={(value as any).text}
          onChange={(e) => onChange({ type: "dissertativa", text: e.target.value })}
          placeholder="Escreva sua resposta..."
          className="min-h-[170px]"
        />
      );
    case "multipla_escolha": {
      const sel = new Set(((value as any).selected as number[]) ?? []);
      return (
        <div className="flex flex-col gap-2">
          {interaction.options.map((o, i) => {
            const active = sel.has(i);
            return (
              <button
                key={i}
                type="button"
                disabled={disabled}
                onClick={() => {
                  let next: number[];
                  if (interaction.multi) {
                    next = active ? [...sel].filter((x) => x !== i) : [...sel, i];
                  } else {
                    next = [i];
                  }
                  onChange({ type: "multipla_escolha", selected: next });
                }}
                className={`flex items-center gap-3 rounded-lg border p-3 text-left text-sm transition ${
                  active ? "border-brand bg-brand-light" : "border-border hover:bg-muted/50"
                }`}
              >
                <span
                  className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs font-bold ${
                    active ? "border-brand bg-brand text-brand-foreground" : "border-border"
                  }`}
                >
                  {String.fromCharCode(65 + i)}
                </span>
                {o.image && (
                  <img src={o.image} alt="" className="h-16 w-16 shrink-0 rounded border border-border object-contain" />
                )}
                <span className="flex-1">{o.text}</span>
              </button>
            );
          })}
        </div>
      );
    }
    case "arrastar_soltar":
      return <ArrastarSoltar interaction={interaction} value={value as any} onChange={onChange} disabled={disabled} />;
    case "completar_lacunas": {
      const vals = ((value as any).values as string[]) ?? interaction.answers.map(() => "");
      return (
        <p className="text-base leading-loose">
          {interaction.segments.map((seg, i) => (
            <span key={i}>
              {seg}
              {i < interaction.answers.length && (
                <input
                  disabled={disabled}
                  value={vals[i] ?? ""}
                  onChange={(e) => {
                    const nv = [...vals];
                    nv[i] = e.target.value;
                    onChange({ type: "completar_lacunas", values: nv });
                  }}
                  className="mx-1 inline-block w-32 border-b-2 border-brand bg-transparent px-1 text-center font-medium outline-none focus:border-brand"
                />
              )}
            </span>
          ))}
        </p>
      );
    }
    case "ligar_colunas":
      return <LigarColunas interaction={interaction} value={value as any} onChange={onChange} disabled={disabled} />;
    case "ordenacao":
      return <Ordenacao interaction={interaction} value={value as any} onChange={onChange} disabled={disabled} />;
    case "substituicao": {
      const vals = ((value as any).values as string[]) ?? interaction.targets.map(() => "");
      return (
        <div className="flex flex-col gap-3">
          <p className="rounded-lg border border-border bg-muted/40 p-3 text-sm">{interaction.sentence}</p>
          {interaction.targets.map((t, i) => (
            <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
              {t.image && (
                <img src={t.image} alt="" className="h-20 w-20 shrink-0 rounded border border-border object-contain" />
              )}
              <div className="grid flex-1 grid-cols-[140px_1fr] items-center gap-2">
                <span className="text-sm font-medium">Substituir "{t.original}":</span>
                <Input
                  disabled={disabled}
                  value={vals[i] ?? ""}
                  onChange={(e) => {
                    const nv = [...vals];
                    nv[i] = e.target.value;
                    onChange({ type: "substituicao", values: nv });
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      );
    }
    case "destacar_trechos": {
      const sel = new Set(((value as any).selected as number[]) ?? []);
      return (
        <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-background p-4 text-base leading-relaxed">
          {interaction.tokens.map((tok, i) => {
            const active = sel.has(i);
            return (
              <button
                key={i}
                type="button"
                disabled={disabled}
                onClick={() => {
                  const next = active ? [...sel].filter((x) => x !== i) : [...sel, i];
                  onChange({ type: "destacar_trechos", selected: next });
                }}
                className={`rounded px-1.5 py-0.5 transition ${
                  active ? "bg-amber-200 font-semibold text-amber-900" : "hover:bg-muted"
                }`}
              >
                {tok}
              </button>
            );
          })}
        </div>
      );
    }
    case "escrita_matematica":
      return (
        <Input
          disabled={disabled}
          value={(value as any).text ?? ""}
          onChange={(e) => onChange({ type: "escrita_matematica", text: e.target.value })}
          placeholder="Digite o resultado..."
          className="font-mono text-lg"
        />
      );
    case "construcao_resposta": {
      const steps = ((value as any).steps as string[]) ?? interaction.steps.map(() => "");
      const stepImgs = interaction.stepImages ?? [];
      return (
        <div className="flex flex-col gap-3">
          {interaction.steps.map((label, i) => (
            <div key={i} className="rounded-lg border border-border bg-background p-3">
              <div className="mb-2 flex items-center gap-3">
                {stepImgs[i] && (
                  <img src={stepImgs[i] ?? ""} alt="" className="h-16 w-16 shrink-0 rounded border border-border object-contain" />
                )}
                <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Etapa {i + 1} · {label}
                </div>
              </div>
              <Textarea
                disabled={disabled}
                value={steps[i] ?? ""}
                onChange={(e) => {
                  const nv = [...steps];
                  nv[i] = e.target.value;
                  onChange({ type: "construcao_resposta", steps: nv });
                }}
                className="min-h-[70px]"
              />
            </div>
          ))}
        </div>
      );
    }
  }
}

// ---------- Drag & Drop ----------
function ArrastarSoltar({
  interaction,
  value,
  onChange,
  disabled,
}: {
  interaction: Extract<Interaction, { type: "arrastar_soltar" }>;
  value: Extract<Response, { type: "arrastar_soltar" }>;
  onChange: (r: Response) => void;
  disabled?: boolean;
}) {
  const slotValues = value.slotValues ?? interaction.slots.map(() => null);
  const used = new Set(slotValues.filter(Boolean) as string[]);

  function drop(slotIdx: number, card: string) {
    const nv = [...slotValues];
    // remove card from other slots
    for (let i = 0; i < nv.length; i++) if (nv[i] === card) nv[i] = null;
    nv[slotIdx] = card;
    onChange({ type: "arrastar_soltar", slotValues: nv });
  }
  function clear(slotIdx: number) {
    const nv = [...slotValues];
    nv[slotIdx] = null;
    onChange({ type: "arrastar_soltar", slotValues: nv });
  }

  return (
    <div className="flex flex-col gap-5">
      {interaction.instruction && (
        <p className="rounded-lg border border-border bg-muted/40 p-3 text-sm font-medium uppercase leading-snug tracking-wide">
          {interaction.instruction}
        </p>
      )}
      <div>
        {interaction.bankLabel && (
          <div className="mb-2 rounded-lg border-2 border-foreground/70 bg-background px-4 py-2 text-center text-lg font-bold tracking-widest">
            {interaction.bankLabel}
          </div>
        )}
        <div className="flex flex-wrap justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/40 p-3">
          {interaction.bank.map((card, i) => {
            const isUsed = used.has(card);
            return (
              <div
                key={i}
                draggable={!disabled && !isUsed}
                onDragStart={(e) => e.dataTransfer.setData("text/plain", card)}
                className={`cursor-grab select-none rounded-lg border px-4 py-2 text-base font-bold shadow-sm transition ${
                  isUsed
                    ? "cursor-not-allowed border-dashed border-border bg-muted text-muted-foreground opacity-40"
                    : "border-brand bg-brand-light text-brand hover:brightness-110 active:cursor-grabbing"
                }`}
              >
                {card}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {interaction.slots.map((s, i) => {
          const current = slotValues[i];
          return (
            <div
              key={i}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const card = e.dataTransfer.getData("text/plain");
                if (card) drop(i, card);
              }}
              className="flex flex-col gap-2 rounded-xl border-2 border-border bg-card p-3"
            >
              {(() => {
                const imgs = s.images ?? (s.image ? [s.image] : []);
                if (imgs.length === 0) {
                  return (
                    <div className="grid aspect-[16/10] w-full place-items-center rounded-lg border-2 border-dashed border-border bg-muted/30 text-xs text-muted-foreground">
                      (sem imagem)
                    </div>
                  );
                }
                return (
                  <div className={`grid gap-2 ${imgs.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                    {imgs.map((img, k) => (
                      <div key={k} className="aspect-[16/10] w-full overflow-hidden rounded-lg border border-border bg-muted/40">
                        <img src={img} alt="" className="h-full w-full object-contain" />
                      </div>
                    ))}
                  </div>
                );
              })()}
              <div className="flex items-center justify-center gap-1 rounded-lg border-2 border-foreground/70 bg-background px-3 py-2">
                <div
                  onClick={() => current && !disabled && clear(i)}
                  className={`grid h-9 w-12 shrink-0 place-items-center rounded border text-lg font-bold ${
                    current
                      ? "cursor-pointer border-brand bg-brand text-brand-foreground"
                      : "border-dashed border-border bg-muted/60 text-muted-foreground"
                  }`}
                >
                  {current ?? "?"}
                </div>
                <span className="text-xl font-bold tracking-wide">{s.label}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Ligar Colunas ----------
function LigarColunas({
  interaction,
  value,
  onChange,
  disabled,
}: {
  interaction: Extract<Interaction, { type: "ligar_colunas" }>;
  value: Extract<Response, { type: "ligar_colunas" }>;
  onChange: (r: Response) => void;
  disabled?: boolean;
}) {
  const mapping = value.mapping ?? {};
  // right column is shown in shuffled order (stable per mount)
  const rightOrder = useMemo(
    () => interaction.pairs.map((_, i) => i).sort(() => Math.random() - 0.5),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [interaction.pairs.length],
  );
  const [selectedLeft, setSelectedLeft] = useState<number | null>(null);

  function pickRight(rightIdx: number) {
    if (selectedLeft === null) return;
    const next = { ...mapping, [selectedLeft]: rightIdx };
    onChange({ type: "ligar_colunas", mapping: next });
    setSelectedLeft(null);
  }

  const rightAssignedTo: Record<number, number> = {};
  Object.entries(mapping).forEach(([l, r]) => (rightAssignedTo[r] = Number(l)));

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-2">
        <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Coluna A</div>
        {interaction.pairs.map((p, i) => {
          const assigned = mapping[i];
          const active = selectedLeft === i;
          return (
            <button
              key={i}
              type="button"
              disabled={disabled}
              onClick={() => setSelectedLeft(active ? null : i)}
              className={`flex items-center gap-3 rounded-lg border p-3 text-left text-sm transition ${
                active ? "border-brand ring-2 ring-brand" : assigned !== undefined ? "border-emerald-300 bg-emerald-50" : "border-border hover:bg-muted/50"
              }`}
            >
              {p.leftImage && (
                <img src={p.leftImage} alt="" className="h-16 w-16 shrink-0 rounded border border-border object-contain" />
              )}
              <span className="flex-1">{p.left}</span>
              {assigned !== undefined && (
                <span className="text-xs font-semibold text-emerald-700">
                  → {interaction.pairs[assigned]?.right || "✓"}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="flex flex-col gap-2">
        <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Coluna B</div>
        {rightOrder.map((rightIdx) => {
          const leftAssigned = rightAssignedTo[rightIdx];
          const disabledBtn = disabled || selectedLeft === null;
          const pair = interaction.pairs[rightIdx];
          return (
            <button
              key={rightIdx}
              type="button"
              disabled={disabledBtn}
              onClick={() => pickRight(rightIdx)}
              className={`flex items-center gap-3 rounded-lg border p-3 text-left text-sm transition ${
                leftAssigned !== undefined ? "border-emerald-300 bg-emerald-50" : "border-border hover:bg-muted/50"
              } ${disabledBtn && leftAssigned === undefined ? "opacity-60" : ""}`}
            >
              {pair.rightImage && (
                <img src={pair.rightImage} alt="" className="h-16 w-16 shrink-0 rounded border border-border object-contain" />
              )}
              <div className="flex-1">
                <div>{pair.right}</div>
                {leftAssigned !== undefined && (
                  <div className="mt-1 text-xs text-emerald-700">↔ {interaction.pairs[leftAssigned].left || "conectado"}</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <div className="col-span-2 text-[11px] text-muted-foreground">
        Clique em um item da Coluna A e depois no par correspondente na Coluna B.
      </div>
    </div>
  );
}

// ---------- Ordenacao (drag reorder) ----------
function Ordenacao({
  interaction,
  value,
  onChange,
  disabled,
}: {
  interaction: Extract<Interaction, { type: "ordenacao" }>;
  value: Extract<Response, { type: "ordenacao" }>;
  onChange: (r: Response) => void;
  disabled?: boolean;
}) {
  // start in a scrambled order; we track indexes into interaction.items
  const initial = useMemo(
    () => (value.order?.length ? value.order : interaction.items.map((_, i) => i).sort(() => Math.random() - 0.5)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [interaction.items.length],
  );
  const order = value.order?.length ? value.order : initial;

  function move(from: number, to: number) {
    if (to < 0 || to >= order.length) return;
    const nv = [...order];
    const [x] = nv.splice(from, 1);
    nv.splice(to, 0, x);
    onChange({ type: "ordenacao", order: nv });
  }

  const itemImgs = interaction.itemImages ?? [];
  return (
    <ol className="flex flex-col gap-2">
      {order.map((itemIdx, pos) => (
        <li
          key={itemIdx}
          className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
        >
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand text-sm font-bold text-brand-foreground">
            {pos + 1}
          </span>
          {itemImgs[itemIdx] && (
            <img src={itemImgs[itemIdx] ?? ""} alt="" className="h-16 w-16 shrink-0 rounded border border-border object-contain" />
          )}
          <span className="flex-1 text-sm">{interaction.items[itemIdx]}</span>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" disabled={disabled || pos === 0} onClick={() => move(pos, pos - 1)}>
              ↑
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={disabled || pos === order.length - 1}
              onClick={() => move(pos, pos + 1)}
            >
              ↓
            </Button>
          </div>
        </li>
      ))}
    </ol>
  );
}
