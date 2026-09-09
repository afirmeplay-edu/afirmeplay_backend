import { NIVEIS, NIVEL_META } from "@/lib/proficiencia";

export function EscalaProficiencia({
  distribuicao,
  total,
}: {
  distribuicao: Record<string, number>;
  total: number;
}) {
  return (
    <section className="panel print-plain p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">Escala de proficiência</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Percentual de acertos por aluno na avaliação de {" "}
            {String(total)} estudantes com cartão corrigido.
          </p>
        </div>
        <div className="flex gap-3 text-[11px] text-muted-foreground">
          <span>0%</span>
          <span>30%</span>
          <span>60%</span>
          <span>80%</span>
          <span>100%</span>
        </div>
      </div>

      <div className="mt-4 h-3 w-full overflow-hidden rounded-full scale-bar" />

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {NIVEIS.map((nivel) => {
          const qtd = distribuicao[nivel] ?? 0;
          const pct = total ? (qtd / total) * 100 : 0;
          const meta = NIVEL_META[nivel];
          return (
            <div
              key={nivel}
              className="rounded-xl border p-4"
              style={{ background: meta.soft, borderColor: meta.token }}
            >
              <div className="flex items-center justify-between text-[11px] font-semibold tracking-wide uppercase" style={{ color: meta.token }}>
                <span>{nivel}</span>
                <span>{meta.faixa}</span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-bold" style={{ color: meta.token }}>
                  {qtd}
                </span>
                <span className="text-sm text-muted-foreground">
                  alunos · {pct.toFixed(1)}%
                </span>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, background: meta.token }}
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">{meta.descricao}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
