import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  BarChart3,
  GraduationCap,
  Printer,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  ALUNOS,
  AVALIACAO,
  HABILIDADES,
  NIVEIS,
  NIVEL_META,
  nivelDe,
  percentualDe,
  type Nivel,
} from "@/lib/proficiencia";
import { EscalaProficiencia } from "@/components/proficiencia/EscalaProficiencia";
import { ColunasNivel } from "@/components/proficiencia/ColunasNivel";
import { RelatorioTurmas } from "@/components/proficiencia/RelatorioTurmas";
import { TurmasHomogeneas } from "@/components/proficiencia/TurmasHomogeneas";
import {
  FiltrosPainel,
  type TipoFonte,
} from "@/components/proficiencia/FiltrosPainel";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      {
        title: "Painel de Proficiência | Afirme Play",
      },
      {
        name: "description",
        content:
          "Painel e relatório de níveis de proficiência — Abaixo do Básico, Básico, Adequado e Avançado — por série e turma.",
      },
      { property: "og:title", content: "Painel de Proficiência | Afirme Play" },
      {
        property: "og:description",
        content:
          "Resultados por nível de proficiência, separados por série e turma, com relatório imprimível.",
      },
    ],
  }),
  component: Painel,
});

function Painel() {
  const [tipo, setTipo] = useState<TipoFonte>("avaliacao");
  const [turno, setTurno] = useState("Todos");
  const [serie, setSerie] = useState("Todas");
  const [turma, setTurma] = useState("Todas");
  const [nivelFiltro, setNivelFiltro] = useState<"Todos" | Nivel>("Todos");

  const series = ["Todas", ...new Set(ALUNOS.map((a) => a.serie))];
  const turmas = [
    "Todas",
    ...new Set(
      ALUNOS.filter((a) => serie === "Todas" || a.serie === serie).map(
        (a) => a.turma,
      ),
    ),
  ];

  const filtrados = useMemo(
    () =>
      ALUNOS.filter(
        (a) =>
          (serie === "Todas" || a.serie === serie) &&
          (turma === "Todas" || a.turma === turma) &&
          (nivelFiltro === "Todos" || nivelDe(percentualDe(a)) === nivelFiltro),
      ),
    [serie, turma, nivelFiltro],
  );

  const distribuicao = useMemo(() => {
    const base = {} as Record<Nivel, number>;
    for (const n of NIVEIS) base[n] = 0;
    for (const a of filtrados) base[nivelDe(percentualDe(a))] += 1;
    return base;
  }, [filtrados]);

  const media = filtrados.length
    ? filtrados.reduce((s, a) => s + percentualDe(a), 0) / filtrados.length
    : 0;
  const proficienciaMedia = filtrados.length
    ? filtrados.reduce((s, a) => s + a.proficiencia, 0) / filtrados.length
    : 0;
  const adequadoOuMais = distribuicao["Adequado"] + distribuicao["Avançado"];
  const criticos = distribuicao["Abaixo do Básico"];

  const habilidades = HABILIDADES.filter(
    (h) => serie === "Todas" || h.serie === serie,
  ).sort((a, b) => a.percentual - b.percentual);

  const indicadores = [
    {
      rotulo: "Alunos avaliados",
      valor: String(filtrados.length),
      detalhe: `${new Set(filtrados.map((a) => `${a.serie}${a.turma}`)).size} turmas`,
      Icone: Users,
    },
    {
      rotulo: "Média de acertos",
      valor: `${media.toFixed(1)}%`,
      detalhe: `${AVALIACAO.itens} itens na prova`,
      Icone: BarChart3,
    },
    {
      rotulo: "Proficiência média",
      valor: proficienciaMedia.toFixed(1),
      detalhe: "Escala Afirme Play",
      Icone: TrendingUp,
    },
    {
      rotulo: "Adequado + Avançado",
      valor: filtrados.length
        ? `${((adequadoOuMais / filtrados.length) * 100).toFixed(0)}%`
        : "0%",
      detalhe: `${adequadoOuMais} alunos no nível esperado`,
      Icone: Target,
    },
    {
      rotulo: "Atenção prioritária",
      valor: String(criticos),
      detalhe: "Abaixo do Básico",
      Icone: GraduationCap,
    },
  ];

  return (
    <main className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
      <header className="panel print-plain relative overflow-hidden p-6 sm:p-8">
        <div className="brand-bar absolute inset-x-0 top-0 h-1" />
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-2xl">
            <p className="text-[11px] font-semibold tracking-[0.2em] text-accent uppercase">
              Afirme Play · Aprendizagem e Resultado
            </p>
            <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
              Painel de Níveis de Proficiência
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              {AVALIACAO.titulo} · {AVALIACAO.municipio}
            </p>
            <p className="text-sm text-muted-foreground">
              {AVALIACAO.escola} · Aplicada em {AVALIACAO.data}
            </p>
          </div>
          <button
            onClick={() => window.print()}
            className="no-print inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            style={{ backgroundImage: "var(--gradient-brand)" }}
          >
            <Printer className="size-4" />
            Imprimir relatório
          </button>
        </div>

      </header>

      <FiltrosPainel
        tipo={tipo}
        setTipo={setTipo}
        serie={serie}
        setSerie={setSerie}
        series={series}
        turma={turma}
        setTurma={setTurma}
        turmas={turmas}
        turno={turno}
        setTurno={setTurno}
        nivelFiltro={nivelFiltro}
        setNivelFiltro={setNivelFiltro}
      />

      <section className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {indicadores.map(({ rotulo, valor, detalhe, Icone }) => (
          <div key={rotulo} className="panel print-plain p-5">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                {rotulo}
              </p>
              <Icone className="size-4 text-accent" />
            </div>
            <p className="mt-3 text-3xl font-bold">{valor}</p>
            <p className="mt-1 text-xs text-muted-foreground">{detalhe}</p>
          </div>
        ))}
      </section>

      <div className="mt-5">
        <EscalaProficiencia distribuicao={distribuicao} total={filtrados.length} />
      </div>

      <h2 className="mt-8 mb-3 text-lg font-semibold">
        Alunos por nível de proficiência
      </h2>
      <ColunasNivel alunos={filtrados} />

      <h2 className="mt-8 mb-3 text-lg font-semibold">
        Relatório detalhado por série e turma
      </h2>
      <RelatorioTurmas alunos={filtrados} />

      <h2 className="mt-8 mb-3 text-lg font-semibold">
        Formação de turmas homogêneas
      </h2>
      <TurmasHomogeneas alunos={filtrados} />

      <h2 className="mt-8 mb-3 text-lg font-semibold">

        Habilidades por nível de domínio
      </h2>
      <section className="panel print-plain p-5 sm:p-6">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {habilidades.map((h) => {
            const nivel = nivelDe(h.percentual);
            const meta = NIVEL_META[nivel];
            return (
              <div
                key={`${h.serie}-${h.codigo}`}
                className="rounded-xl border p-4"
                style={{ background: meta.soft, borderColor: meta.token }}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-bold">{h.codigo}</p>
                  <span className="text-[11px] text-muted-foreground">
                    {h.serie}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{h.componente}</p>
                <p
                  className="mt-2 text-2xl font-bold"
                  style={{ color: meta.token }}
                >
                  {h.percentual.toFixed(1)}%
                </p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${h.percentual}%`, background: meta.token }}
                  />
                </div>
                <p className="mt-2 text-[11px] font-semibold" style={{ color: meta.token }}>
                  {nivel}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <footer className="mt-10 border-t border-border pt-5 pb-4 text-center text-xs text-muted-foreground">
        © 2026 Afirme Play — {AVALIACAO.rede} de {AVALIACAO.municipio}
      </footer>
    </main>
  );
}
