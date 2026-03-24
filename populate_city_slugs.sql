# Script SQL: Popular Slugs das Cidades
# ========================================
# 
# Este script deve ser executado após a migration
# para popular os slugs das cidades existentes.
#
# Uso:
#   psql -d afirmeplay_dev -f populate_city_slugs.sql
#
# Ou via Python:
#   flask shell < populate_city_slugs.sql

-- ========================================
-- VERIFICAR CIDADES EXISTENTES
-- ========================================

SELECT 
    id,
    name,
    state,
    slug,
    created_at
FROM public.city
ORDER BY name;

-- ========================================
-- POPULAR SLUGS AUTOMATICAMENTE
-- ========================================

-- A migration já tenta popular automaticamente,
-- mas este script permite ajustes manuais

-- Opção 1: Popular com base no nome (remover acentos e espaços)
UPDATE public.city
SET slug = LOWER(
    REGEXP_REPLACE(
        TRANSLATE(
            name,
            'ÁÀÂÃÄÅáàâãäåÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇçÑñ',
            'AAAAAAaaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCcNn'
        ),
        '[^a-zA-Z0-9]',
        '',
        'g'
    )
)
WHERE slug IS NULL OR slug = '';

-- ========================================
-- AJUSTES MANUAIS (EXEMPLOS)
-- ========================================

-- Ajustar slugs manualmente para garantir URLs amigáveis
-- Descomente e ajuste conforme suas cidades:

-- UPDATE public.city SET slug = 'jiparana' WHERE name = 'Ji-Paraná';
-- UPDATE public.city SET slug = 'portovelho' WHERE name = 'Porto Velho';
-- UPDATE public.city SET slug = 'ariquemes' WHERE name = 'Ariquemes';
-- UPDATE public.city SET slug = 'cacoal' WHERE name = 'Cacoal';
-- UPDATE public.city SET slug = 'vilhena' WHERE name = 'Vilhena';
-- UPDATE public.city SET slug = 'jaru' WHERE name = 'Jaru';
-- UPDATE public.city SET slug = 'guajaramirim' WHERE name = 'Guajará-Mirim';
-- UPDATE public.city SET slug = 'rolimmoura' WHERE name = 'Rolim de Moura';

-- ========================================
-- VERIFICAR DUPLICATAS
-- ========================================

-- Encontrar slugs duplicados
SELECT 
    slug,
    COUNT(*) as quantidade,
    STRING_AGG(name, ', ') as cidades
FROM public.city
GROUP BY slug
HAVING COUNT(*) > 1;

-- Se houver duplicatas, ajustar manualmente:
-- UPDATE public.city SET slug = 'slug-unico' WHERE id = 'uuid-da-cidade';

-- ========================================
-- VERIFICAR SLUGS INVÁLIDOS
-- ========================================

-- Encontrar slugs que não seguem o padrão (apenas a-z, 0-9, -)
SELECT 
    id,
    name,
    slug
FROM public.city
WHERE slug IS NOT NULL
  AND slug !~ '^[a-z0-9-]+$';

-- ========================================
-- VERIFICAR RESULTADO FINAL
-- ========================================

SELECT 
    id,
    name,
    slug,
    'https://' || slug || '.afirmeplay.com.br' as url_subdominio
FROM public.city
WHERE slug IS NOT NULL
ORDER BY name;

-- ========================================
-- TESTE DE LOOKUP
-- ========================================

-- Testar busca por slug (simular resolução do middleware)
SELECT 
    id,
    name,
    slug,
    state
FROM public.city
WHERE slug = 'jiparana';  -- Ajustar conforme seu caso

-- ========================================
-- ESTATÍSTICAS
-- ========================================

SELECT 
    COUNT(*) as total_cidades,
    COUNT(slug) as cidades_com_slug,
    COUNT(*) - COUNT(slug) as cidades_sem_slug
FROM public.city;
