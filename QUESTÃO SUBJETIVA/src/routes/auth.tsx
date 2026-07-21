import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { GraduationCap } from "lucide-react";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [{ title: "Entrar — AfirmePlay" }],
  }),
  beforeLoad: async () => {
    if (typeof window === "undefined") return;
    const { data } = await supabase.auth.getSession();
    if (data.session) throw redirect({ to: "/dashboard" });
  },
  component: AuthPage,
});

function AuthPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [title, setTitle] = useState("Professor");

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({
      email: signInEmail,
      password: signInPassword,
    });
    setLoading(false);
    if (error) {
      toast.error("Não foi possível entrar. Verifique e‑mail e senha.");
      return;
    }
    navigate({ to: "/dashboard" });
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("A senha deve ter ao menos 6 caracteres.");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin,
        data: { full_name: name, title },
      },
    });
    setLoading(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success("Conta criada. Você já pode entrar.");
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      {/* Left: brand panel */}
      <div className="relative hidden overflow-hidden bg-brand p-12 text-brand-foreground lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-brand-foreground/15">
            <GraduationCap className="h-5 w-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">AfirmePlay</span>
        </div>
        <div className="flex flex-col gap-4">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-balance">
            Avaliação inteligente, alinhada ao SAEB e à BNCC.
          </h1>
          <p className="max-w-md text-sm text-brand-foreground/80 text-pretty">
            Construa questões interativas, aplique rubricas pedagógicas e acompanhe o desempenho da
            sua rede com clareza institucional.
          </p>
        </div>
        <div className="text-[11px] uppercase tracking-widest text-brand-foreground/60">
          Plataforma para professores, coordenadores, diretores e administradores.
        </div>
        <div
          aria-hidden
          className="pointer-events-none absolute -right-40 -top-40 h-96 w-96 rounded-full bg-brand-foreground/10 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -left-16 h-72 w-72 rounded-full bg-brand-foreground/5 blur-3xl"
        />
      </div>

      {/* Right: forms */}
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-brand text-brand-foreground">
              <GraduationCap className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold tracking-tight text-brand">AfirmePlay</span>
          </div>

          <div className="mb-5 rounded-xl border border-brand/20 bg-brand-light p-4">
            <p className="text-sm font-medium text-brand">Quer só testar na prática?</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Entre no modo demonstração para criar uma questão, responder como aluno e ver os
              resultados sem cadastro.
            </p>
            <Button
              type="button"
              onClick={() => navigate({ to: "/dashboard" })}
              className="mt-3 w-full bg-brand text-brand-foreground hover:brightness-110"
            >
              Acessar demonstração
            </Button>
          </div>

          <Tabs defaultValue="signin">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="signin">Entrar</TabsTrigger>
              <TabsTrigger value="signup">Criar conta</TabsTrigger>
            </TabsList>

            <TabsContent value="signin" className="mt-6">
              <form onSubmit={handleSignIn} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="signin-email">E‑mail institucional</Label>
                  <Input
                    id="signin-email"
                    type="email"
                    required
                    autoComplete="email"
                    value={signInEmail}
                    onChange={(e) => setSignInEmail(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="signin-password">Senha</Label>
                  <Input
                    id="signin-password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={signInPassword}
                    onChange={(e) => setSignInPassword(e.target.value)}
                  />
                </div>
                <Button
                  type="submit"
                  disabled={loading}
                  className="bg-brand text-brand-foreground hover:brightness-110"
                >
                  {loading ? "Entrando…" : "Entrar"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="signup" className="mt-6">
              <form onSubmit={handleSignUp} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="name">Nome completo</Label>
                  <Input
                    id="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="title">Cargo</Label>
                  <Input
                    id="title"
                    placeholder="Ex: Professor de Matemática"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="email">E‑mail institucional</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="password">Senha</Label>
                  <Input
                    id="password"
                    type="password"
                    minLength={6}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <p className="text-[11px] text-muted-foreground">Mínimo de 6 caracteres.</p>
                </div>
                <Button
                  type="submit"
                  disabled={loading}
                  className="bg-brand text-brand-foreground hover:brightness-110"
                >
                  {loading ? "Criando…" : "Criar conta"}
                </Button>
                <p className="text-center text-[11px] text-muted-foreground">
                  Ao criar sua conta você recebe o papel de <b>Professor</b>. Papéis adicionais
                  (Coordenador, Diretor, Administrador) são atribuídos pela gestão da rede.
                </p>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
