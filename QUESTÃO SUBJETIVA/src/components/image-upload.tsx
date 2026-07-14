import { useRef } from "react";
import { ImagePlus, X } from "lucide-react";

type Props = {
  value?: string | null;
  onChange: (dataUrl: string | null) => void;
  label?: string;
  aspect?: "square" | "wide" | "auto";
  className?: string;
};

export function ImageUpload({ value, onChange, label = "Adicionar imagem", aspect = "auto", className }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
      alert("Imagem muito grande (máx 4MB).");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => onChange(String(reader.result));
    reader.readAsDataURL(file);
  }

  const box =
    aspect === "square"
      ? "aspect-square"
      : aspect === "wide"
        ? "aspect-[16/9]"
        : "min-h-[80px]";

  if (value) {
    return (
      <div className={`relative overflow-hidden rounded-lg border border-border bg-muted/40 ${box} ${className ?? ""}`}>
        <img src={value} alt="" className="h-full w-full object-contain" />
        <button
          type="button"
          onClick={() => onChange(null)}
          className="absolute right-1 top-1 grid h-6 w-6 place-items-center rounded-full bg-black/60 text-white hover:bg-black/80"
          aria-label="Remover imagem"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => inputRef.current?.click()}
      className={`flex ${box} w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground hover:border-brand/40 hover:bg-brand-light/40 hover:text-brand ${className ?? ""}`}
    >
      <ImagePlus className="h-5 w-5" />
      <span>{label}</span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
    </button>
  );
}
