import { ClipboardList, MonitorSmartphone } from "lucide-react";
import { AVALIACAO, NIVEIS, type Nivel } from "@/lib/proficiencia";

export type TipoFonte = "avaliacao" | "cartao";

function Campo({
  rotulo,
  valor,
  opcoes,
  onChange,
  disabled,
}: {
  rotulo: string;
  valor: string;
  opcoes: string[];
  onChange?: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
        {rotulo}
      </span>
      <select
        value={valor}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.value)}
        className="mt-1.5 w-full rounded-xl border border-input bg-surface px-3 py-2.5 text-sm text-foreground outline-none focus:border-ring disabled:opacity-70"
      >
        {opcoes.map((o) => (
          <option key={o} value={o} className="bg-card">
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FiltrosPainel({
  tipo,
  setTipo,
  serie,
  setSerie,
  series,
  turma,
  setTurma,
  turmas,
  turno,
  setTurno,
  nivelFiltro,
  setNivelFiltro,
}: {
  tipo: TipoFonte;
  setTipo: (t: TipoFonte) => void;
  serie: string;
  setSerie: (v: string) => void;
  series: string[];
  turma: string;
  setTurma: (v: string) => void;
  turmas: string[];
  turno: string;
  setTurno: (v: string) => void;
  nivelFiltro: "Todos" | Nivel;
  setNivelFiltro: (v: "Todos" | Nivel) => void;
}) {
  const abas: { id: TipoFonte; label: string; Icone: typeof ClipboardList }[] = [
    { id: "avaliacao", label: "Avaliação online", Icone: MonitorSmartphone },
    { id: "cartao", label: "Cartão-resposta", Icone: ClipboardList },
  ];

  return (
    <section className="panel print-plain no-print mt-5 p-5 sm:p-6">
      <div className="flex flex-wrap gap-2">
        {abas.map(({ id, label, Icone }) => {
          const ativo = tipo === id;
          return (
            <button
              key={id}
              onClick={() => setTipo(id)}
              className="inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors"
              style={
                ativo
                  ? {
                      backgroundImage: "var(--gradient-brand)",
                      borderColor: "transparent",
                      color: "var(--primary-foreground)",
                    }
                  : { borderColor: "var(--border)", color: "var(--muted-foreground)" }
              }
            >
              <Icone className="size-4" />
              {label}
            </button>
          );
        })}
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <Campo rotulo="Estado" valor="Alagoas" opcoes={["Alagoas"]} disabled />
        <Campo
          rotulo="Município"
          valor="Limoeiro de Anadia"
          opcoes={["Limoeiro de Anadia"]}
          disabled
        />
        <Campo rotulo="Período" valor="05/2026" opcoes={["05/2026"]} disabled />
        <Campo
          rotulo="Avaliação"
          valor={AVALIACAO.titulo}
          opcoes={[AVALIACAO.titulo]}
          disabled
        />
        <Campo
          rotulo="Escola"
          valor={AVALIACAO.escola}
          opcoes={[AVALIACAO.escola]}
          disabled
        />
        <Campo
          rotulo="Série"
          valor={serie}
          opcoes={series}
          onChange={(v) => {
            setSerie(v);
            setTurma("Todas");
          }}
        />
        <Campo rotulo="Turma" valor={turma} opcoes={turmas} onChange={setTurma} />
        <Campo
          rotulo="Turno"
          valor={turno}
          opcoes={["Todos", "Manhã", "Tarde"]}
          onChange={setTurno}
        />
        <Campo
          rotulo="Nível de proficiência"
          valor={nivelFiltro}
          opcoes={["Todos", ...NIVEIS]}
          onChange={(v) => setNivelFiltro(v as "Todos" | Nivel)}
        />
      </div>
    </section>
  );
}
