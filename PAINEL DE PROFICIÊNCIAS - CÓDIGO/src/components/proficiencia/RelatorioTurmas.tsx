import {
  NIVEIS,
  NIVEL_META,
  nivelDe,
  percentualDe,
  type Aluno,
} from "@/lib/proficiencia";
import { NivelBadge } from "./NivelBadge";

function agrupar(alunos: Aluno[]) {
  const mapa = new Map<string, Aluno[]>();
  for (const a of alunos) {
    const chave = `${a.serie}|${a.turma}`;
    mapa.set(chave, [...(mapa.get(chave) ?? []), a]);
  }
  return [...mapa.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

export function RelatorioTurmas({ alunos }: { alunos: Aluno[] }) {
  const grupos = agrupar(alunos);

  return (
    <section className="space-y-5">
      {grupos.map(([chave, lista]) => {
        const [serie, turma] = chave.split("|");
        const media =
          lista.reduce((s, a) => s + percentualDe(a), 0) / (lista.length || 1);
        const ordenados = [...lista].sort(
          (a, b) => percentualDe(b) - percentualDe(a),
        );
        const contagem = NIVEIS.map((n) => ({
          nivel: n,
          qtd: lista.filter((a) => nivelDe(percentualDe(a)) === n).length,
        }));

        return (
          <article key={chave} className="panel print-plain overflow-hidden">
            <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
              <div>
                <h3 className="text-base font-semibold">
                  {serie} — Turma {turma}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {lista.length} alunos · média da turma {media.toFixed(1)}% de acertos
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {contagem.map(({ nivel, qtd }) => (
                  <span
                    key={nivel}
                    className="rounded-lg px-2.5 py-1 text-[11px] font-semibold"
                    style={{
                      background: NIVEL_META[nivel].soft,
                      color: NIVEL_META[nivel].token,
                    }}
                  >
                    {nivel}: {qtd}
                  </span>
                ))}
              </div>
            </header>

            <div className="mb-4 flex h-2 w-full overflow-hidden">
              {contagem.map(({ nivel, qtd }) => (
                <div
                  key={nivel}
                  style={{
                    width: `${(qtd / lista.length) * 100}%`,
                    background: NIVEL_META[nivel].token,
                  }}
                />
              ))}
            </div>

            <div className="overflow-x-auto px-2 pb-4">
              <table className="w-full min-w-[640px] border-separate border-spacing-y-1 text-sm">
                <thead>
                  <tr className="text-left text-[11px] tracking-wide text-muted-foreground uppercase">
                    <th className="px-3 py-2 font-semibold">#</th>
                    <th className="px-3 py-2 font-semibold">Aluno</th>
                    <th className="px-3 py-2 text-center font-semibold">Acertos</th>
                    <th className="px-3 py-2 text-center font-semibold">% Acertos</th>
                    <th className="px-3 py-2 text-center font-semibold">Nota</th>
                    <th className="px-3 py-2 text-center font-semibold">Proficiência</th>
                    <th className="px-3 py-2 font-semibold">Nível</th>
                  </tr>
                </thead>
                <tbody>
                  {ordenados.map((a, i) => {
                    const pct = percentualDe(a);
                    const nivel = nivelDe(pct);
                    return (
                      <tr key={a.nome} className="bg-surface/50">
                        <td className="rounded-l-lg px-3 py-2 text-muted-foreground">
                          {i + 1}
                        </td>
                        <td className="px-3 py-2 font-medium">{a.nome}</td>
                        <td className="px-3 py-2 text-center text-muted-foreground">
                          {a.acertos}/{a.totalItens}
                        </td>
                        <td
                          className="px-3 py-2 text-center font-semibold"
                          style={{ color: NIVEL_META[nivel].token }}
                        >
                          {pct.toFixed(1)}%
                        </td>
                        <td className="px-3 py-2 text-center">{a.nota.toFixed(1)}</td>
                        <td className="px-3 py-2 text-center text-muted-foreground">
                          {a.proficiencia.toFixed(1)}
                        </td>
                        <td className="rounded-r-lg px-3 py-2">
                          <NivelBadge nivel={nivel} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </article>
        );
      })}
    </section>
  );
}
