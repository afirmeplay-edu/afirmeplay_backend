import {
  NIVEIS,
  NIVEL_META,
  nivelDe,
  percentualDe,
  type Aluno,
} from "@/lib/proficiencia";

export function ColunasNivel({ alunos }: { alunos: Aluno[] }) {
  return (
    <section className="grid gap-4 lg:grid-cols-4">
      {NIVEIS.map((nivel) => {
        const meta = NIVEL_META[nivel];
        const lista = alunos
          .filter((a) => nivelDe(percentualDe(a)) === nivel)
          .sort((a, b) => percentualDe(b) - percentualDe(a));
        return (
          <div key={nivel} className="panel print-plain overflow-hidden">
            <header
              className="flex items-center justify-between px-4 py-3"
              style={{ background: meta.soft }}
            >
              <div>
                <p
                  className="text-[11px] font-bold tracking-wide uppercase"
                  style={{ color: meta.token }}
                >
                  {nivel}
                </p>
                <p className="text-[11px] text-muted-foreground">{meta.faixa} de acertos</p>
              </div>
              <span
                className="rounded-lg px-2 py-1 text-sm font-bold"
                style={{ background: meta.token, color: "var(--on-level)" }}
              >
                {lista.length}
              </span>
            </header>

            <div className="space-y-2 p-3">
              {lista.length === 0 && (
                <p className="py-6 text-center text-xs text-muted-foreground">
                  Nenhum aluno neste nível
                </p>
              )}
              {lista.map((a) => (
                <article
                  key={`${a.nome}-${a.turma}`}
                  className="rounded-xl border border-border bg-surface/60 p-3"
                >
                  <p className="truncate text-sm font-semibold" title={a.nome}>
                    {a.nome}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {a.serie} · Turma {a.turma}
                  </p>
                  <div className="mt-2 flex items-end justify-between">
                    <span
                      className="text-2xl font-bold"
                      style={{ color: meta.token }}
                    >
                      {percentualDe(a).toFixed(1)}%
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {a.acertos}/{a.totalItens} · nota {a.nota.toFixed(1)}
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${percentualDe(a)}%`, background: meta.token }}
                    />
                  </div>
                </article>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
