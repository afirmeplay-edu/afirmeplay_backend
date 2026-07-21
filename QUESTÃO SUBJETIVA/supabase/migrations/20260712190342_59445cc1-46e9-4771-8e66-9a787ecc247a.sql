
-- 1) Roles enum + user_roles
CREATE TYPE public.app_role AS ENUM ('admin','secretario','tecnico','diretor','coordenador','professor','aluno');

CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL DEFAULT '',
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profiles read own" ON public.profiles FOR SELECT TO authenticated USING (auth.uid() = id);
CREATE POLICY "profiles update own" ON public.profiles FOR UPDATE TO authenticated USING (auth.uid() = id);
CREATE POLICY "profiles insert own" ON public.profiles FOR INSERT TO authenticated WITH CHECK (auth.uid() = id);

CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_roles read own" ON public.user_roles FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role public.app_role)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role) $$;

CREATE OR REPLACE FUNCTION public.has_any_role(_user_id UUID, _roles public.app_role[])
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = ANY(_roles)) $$;

-- 2) Auto-create profile + default 'professor' role on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, title)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'title', 'Professor')
  );
  INSERT INTO public.user_roles (user_id, role) VALUES (NEW.id, 'professor');
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 3) Questions bank
CREATE TYPE public.question_type AS ENUM (
  'dissertativa','arrastar_soltar','ligar_colunas','ordenacao','completar_lacunas',
  'substituicao','destacar_trechos','multipla_escolha','escrita_matematica','construcao_resposta'
);
CREATE TYPE public.question_status AS ENUM ('rascunho','revisao','aprovada','arquivada');
CREATE TYPE public.difficulty_level AS ENUM ('facil','medio','dificil','muito_dificil');

CREATE TABLE public.questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Content
  title TEXT NOT NULL,
  statement TEXT NOT NULL DEFAULT '',
  support_text TEXT,
  question_type public.question_type NOT NULL DEFAULT 'dissertativa',

  -- Pedagogical identification
  knowledge_area TEXT,
  curricular_component TEXT,
  school_year TEXT,
  school_stage TEXT,
  bncc_code TEXT,
  saeb_descriptor TEXT,
  ability TEXT,
  competency TEXT,
  knowledge_object TEXT,
  theme TEXT,
  subtheme TEXT,
  difficulty public.difficulty_level NOT NULL DEFAULT 'medio',
  expected_time_min INT DEFAULT 5,
  weight NUMERIC(6,2) NOT NULL DEFAULT 1,
  value NUMERIC(6,2) NOT NULL DEFAULT 1,
  complexity TEXT,

  -- Interactive payload + rubric (JSON)
  interactions JSONB NOT NULL DEFAULT '{}'::jsonb,
  rubric JSONB NOT NULL DEFAULT '[]'::jsonb,

  -- Workflow
  status public.question_status NOT NULL DEFAULT 'rascunho',
  version INT NOT NULL DEFAULT 1,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.questions TO authenticated;
GRANT ALL ON public.questions TO service_role;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;

-- Authors manage their own questions
CREATE POLICY "questions select own" ON public.questions FOR SELECT TO authenticated
  USING (author_id = auth.uid());
CREATE POLICY "questions insert own" ON public.questions FOR INSERT TO authenticated
  WITH CHECK (author_id = auth.uid());
CREATE POLICY "questions update own" ON public.questions FOR UPDATE TO authenticated
  USING (author_id = auth.uid());
CREATE POLICY "questions delete own" ON public.questions FOR DELETE TO authenticated
  USING (author_id = auth.uid());

-- Coordinators, directors, admins can view all
CREATE POLICY "questions select by staff" ON public.questions FOR SELECT TO authenticated
  USING (public.has_any_role(auth.uid(), ARRAY['coordenador','diretor','admin']::public.app_role[]));

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER trg_questions_updated
  BEFORE UPDATE ON public.questions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_profiles_updated
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX idx_questions_author ON public.questions(author_id);
CREATE INDEX idx_questions_status ON public.questions(status);
CREATE INDEX idx_questions_saeb ON public.questions(saeb_descriptor);
