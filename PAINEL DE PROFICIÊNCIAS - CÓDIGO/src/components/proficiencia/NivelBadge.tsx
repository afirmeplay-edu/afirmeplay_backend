import { NIVEL_META, type Nivel } from "@/lib/proficiencia";

export function NivelBadge({ nivel, className = "" }: { nivel: Nivel; className?: string }) {
  const meta = NIVEL_META[nivel];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${className}`}
      style={{ background: meta.soft, color: meta.token }}
    >
      <span
        className="size-1.5 rounded-full"
        style={{ background: meta.token }}
        aria-hidden
      />
      {nivel}
    </span>
  );
}
