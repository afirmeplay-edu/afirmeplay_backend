import { useMemo, useState } from "react";
import { Users2 } from "lucide-react";
import {
  NIVEIS,
  NIVEL_META,
  nivelDe,
  percentualDe,
  type Aluno,
  type Nivel,
} from "@/lib/proficiencia";

interface Sugestao {
  rotulo: string;
  serie: string;
  nivel: Nivel;
  alunos: Aluno[];
  origens: string[];
  media: number;
}

const LETRAS = "ABCDEFGH";

function gerar(alunos: Aluno[], tamanhoMax: number): Sugestao[] {
  const porSerie = new Map<string, Aluno[]>();
  for (const a of alunos) {
    porSerie.set(a.serie, [...(porSerie.get(a.serie) ?? []), a]);
  }

  const out: Sugestao[] = [];
  for (const [serie, lista] of [...porSerie.entries()].sort()) {
    for (const nivel of NIVEIS) {
      const doNivel = lista
        .filter((a) => nivelDe(percentualDe(a)) === nivel)
        .sort((a, b) => percentualDe(b) - percentualDe(a));
      if (doNivel.length === 0) continue;
      const blocos = Math.ceil(doNivel.length / tamanhoMax);
      for (let i = 0; i < blocos; i++) {
        const grupo = doNivel.slice(i * tamanhoMax, (i + 1) * tamanhoMax);
        out.push({
          rotulo: `${serie} · Turma ${nivel}${blocos > 1 ? ` ${LETRAS[i]}` : ""}`,
          serie,
          nivel,
          alunos: grupo,
          origens: [...new Set(grupo.map((a) => `${a.serie} ${a.turma}`))].sort(),
          media:
            grupo.reduce((s, a) => s + percentualDe(a), 0) / (grupo.length || 1),
        });
      }
    }
  }
  return out;
}

export function TurmasHomogeneas({ alunos }: { alunos: Aluno[] }) {
  const [tamanhoMax, setTamanhoMax] = useState(12);
  const [aberta, setAberta] = useState<string | null>(null);
  const sugestoes = useMemo(() => gerar(alunos, tamanhoMax), [alunos, tamanhoMax]);

  return (
    <section className="panel print-plain p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-semibold">
            <Users2 className="size-4 text-accent" />
            Turmas homogêneas sugeridas
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Reagrupamento de alunos da mesma série e escola por nível de
            proficiência, unindo turmas de origem (ex.: 5º Ano A + 5º Ano B).
          </p>
        </div>
        <label className="no-print block">
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            Alunos por turma
          </span>
          <select
            value={tamanhoMax}
            onChange={(e) => setTamanhoMax(Number(e.target.value))}
            className="mt-1.5 w-full rounded-xl border border-input bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-ring"
          >
            {[8, 10, 12, 15, 20, 25].map((n) => (
              <option key={n} value={n} className="bg-card">
                até {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {sugestoes.length === 0 ? (
        <p className="mt-5 text-sm text-muted-foreground">
          Nenhum aluno nos filtros atuais para sugerir turmas.
        </p>
      ) : (
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sugestoes.map((s) => {
            const meta = NIVEL_META[s.nivel];
            const expandida = aberta === s.rotulo;
            return (
              <article
                key={s.rotulo}
                className="rounded-xl border p-4"
                style={{ background: meta.soft, borderColor: meta.token }}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-bold">{s.rotulo}</p>
                  <span
                    className="rounded-lg px-2 py-0.5 text-[11px] font-semibold"
                    style={{ background: meta.token, color: "#fff" }}
                  >
                    {s.alunos.length} alunos
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  Média do grupo:{" "}
                  <strong style={{ color: meta.token }}>
                    {s.media.toFixed(1)}%
                  </strong>{" "}
                  de acertos
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Origem: {s.origens.join(" + ")}
                </p>
                <button
                  onClick={() => setAberta(expandida ? null : s.rotulo)}
                  className="no-print mt-3 text-[11px] font-semibold underline"
                  style={{ color: meta.token }}
                >
                  {expandida ? "Ocultar alunos" : "Ver alunos"}
                </button>
                <ul
                  className={`mt-2 space-y-1 text-xs text-muted-foreground ${expandida ? "" : "hidden print:block"}`}
                >
                  {s.alunos.map((a) => (
                    <li key={a.nome} className="flex justify-between gap-2">
                      <span>{a.nome}</span>
                      <span style={{ color: meta.token }}>
                        {percentualDe(a).toFixed(0)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
