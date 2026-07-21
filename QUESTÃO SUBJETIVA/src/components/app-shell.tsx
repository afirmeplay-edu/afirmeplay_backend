import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import {
  BookMarked,
  BarChart3,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  PenLine,
  Search,
  Settings,
  Sparkles,
  Users2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useQueryClient } from "@tanstack/react-query";

type NavItem = {
  title: string;
  url: string;
  icon: typeof LayoutDashboard;
  disabled?: boolean;
};

const navItems: NavItem[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Banco de Questões", url: "/questoes", icon: BookMarked },
  { title: "Responder como aluno", url: "/aluno", icon: PenLine },
  { title: "Resultados", url: "/resultados", icon: BarChart3 },
  { title: "Avaliações", url: "/avaliacoes", icon: ClipboardList, disabled: true },
  { title: "Turmas", url: "/turmas", icon: Users2, disabled: true },
  { title: "IA Pedagógica", url: "/ia", icon: Sparkles, disabled: true },
];

function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <Sidebar collapsible="icon" className="border-r border-border">
      <SidebarHeader className="px-4 py-4">
        <Link to="/dashboard" className="flex items-center gap-2">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-brand text-brand-foreground">
            <GraduationCap className="h-4 w-4" />
          </div>
          <span className="text-base font-semibold tracking-tight text-brand group-data-[collapsible=icon]:hidden">
            AfirmePlay
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const active =
                  pathname === item.url || pathname.startsWith(item.url + "/");
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild={!item.disabled}
                      isActive={active}
                      disabled={item.disabled}
                      tooltip={item.title}
                      className={
                        active
                          ? "bg-brand-light text-brand ring-1 ring-brand/10 hover:bg-brand-light"
                          : ""
                      }
                    >
                      {item.disabled ? (
                        <span className="flex items-center gap-3 opacity-50 cursor-not-allowed">
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                          <span className="ml-auto text-[9px] font-semibold uppercase tracking-wider text-muted-foreground group-data-[collapsible=icon]:hidden">
                            em breve
                          </span>
                        </span>
                      ) : (
                        <Link to={item.url} className="flex items-center gap-3">
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                        </Link>
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Configurações" disabled>
              <Settings className="h-4 w-4" />
              <span>Configurações</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

function TopBar() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [profile, setProfile] = useState<{ name: string; role: string } | null>(null);

  useEffect(() => {
    (async () => {
      const { data: userData } = await supabase.auth.getUser();
      if (!userData.user) {
        setProfile({ name: "Professor Demo", role: "Modo demonstração" });
        return;
      }
      const [{ data: p }, { data: r }] = await Promise.all([
        supabase.from("profiles").select("full_name, title").eq("id", userData.user.id).maybeSingle(),
        supabase.from("user_roles").select("role").eq("user_id", userData.user.id).limit(1).maybeSingle(),
      ]);
      setProfile({
        name: p?.full_name || userData.user.email || "Usuário",
        role: (r?.role as string) || p?.title || "Professor",
      });
    })();
  }, []);

  async function handleSignOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    navigate({ to: "/dashboard", replace: true });
  }

  const initials = profile?.name
    ? profile.name
        .split(" ")
        .slice(0, 2)
        .map((n) => n[0])
        .join("")
        .toUpperCase()
    : "";

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between gap-4 border-b border-border bg-background/80 px-4 backdrop-blur-md md:px-6">
      <div className="flex items-center gap-3">
        <SidebarTrigger className="h-8 w-8" />
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar questões ou descritores..."
            className="h-9 w-80 border-0 bg-muted pl-9 ring-1 ring-border focus-visible:ring-brand"
          />
        </div>
      </div>
      <div className="flex items-center gap-3">
        {profile && (
          <div className="hidden text-right md:block">
            <div className="text-sm font-medium leading-tight">{profile.name}</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {profile.role}
            </div>
          </div>
        )}
        <Avatar className="h-9 w-9 ring-1 ring-border">
          <AvatarFallback className="bg-brand-light text-xs font-semibold text-brand">
            {initials || "AP"}
          </AvatarFallback>
        </Avatar>
        <button
          onClick={handleSignOut}
          title="Reiniciar sessão"
          className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
