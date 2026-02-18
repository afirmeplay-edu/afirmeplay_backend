"""
Script para gerar SQL de atualização de habilidades de Português.

Lê o arquivo habilidades_portugues_data.json e gera um arquivo SQL
completo e pronto para executar no PostgreSQL.

USO:
    python scripts/generate_portuguese_skills_sql.py

SAÍDA:
    scripts/update_portuguese_skills_generated.sql
"""

import json
import os
from datetime import datetime

def escape_sql_string(s):
    """Escapa aspas simples para uso em SQL."""
    if s is None:
        return 'NULL'
    return s.replace("'", "''")

def generate_sql():
    """Gera o arquivo SQL com todas as habilidades."""
    
    # Carregar JSON
    json_path = os.path.join(os.path.dirname(__file__), 'habilidades_portugues_data.json')
    
    if not os.path.exists(json_path):
        print(f"❌ Arquivo não encontrado: {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    habilidades = data.get('habilidades', [])
    
    # Nome do arquivo de saída
    output_path = os.path.join(os.path.dirname(__file__), 'update_portuguese_skills_generated.sql')
    
    print("\n" + "="*70)
    print("🚀 GERADOR DE SQL PARA HABILIDADES DE PORTUGUÊS")
    print("="*70)
    print(f"\n📂 Lendo: {json_path}")
    print(f"📝 Habilidades encontradas: {len(habilidades)}")
    print(f"💾 Gerando: {output_path}\n")
    
    # Gerar SQL
    with open(output_path, 'w', encoding='utf-8') as f:
        # Cabeçalho
        f.write("-- " + "="*76 + "\n")
        f.write("-- SCRIPT DE ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS\n")
        f.write("-- " + "="*76 + "\n")
        f.write("--\n")
        f.write(f"-- Gerado automaticamente em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"-- Total de habilidades: {len(habilidades)}\n")
        f.write("--\n")
        f.write("-- COMPORTAMENTO:\n")
        f.write("-- - Se a habilidade existir (busca por code): atualiza APENAS description\n")
        f.write("-- - Se não existir: cria nova habilidade\n")
        f.write("--\n")
        f.write("-- EXECUÇÃO:\n")
        f.write("--   psql -U postgres -d afirmeplay_dev -f update_portuguese_skills_generated.sql\n")
        f.write("--\n")
        f.write("-- OU (Docker):\n")
        f.write("--   docker exec -i postgres psql -U postgres -d afirmeplay_dev < update_portuguese_skills_generated.sql\n")
        f.write("--\n")
        f.write("-- " + "="*76 + "\n\n")
        
        # Bloco DO
        f.write("DO $$\n")
        f.write("DECLARE\n")
        f.write("    v_count_updated integer := 0;\n")
        f.write("    v_count_created integer := 0;\n")
        f.write("    v_count_errors integer := 0;\n")
        f.write("    v_exists boolean;\n")
        f.write("BEGIN\n")
        f.write("    RAISE NOTICE '';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '🚀 ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '';\n")
        f.write(f"    RAISE NOTICE '📂 Total de habilidades: {len(habilidades)}';\n")
        f.write("    RAISE NOTICE '';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '📦 PROCESSANDO HABILIDADES';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '';\n\n")
        
        # Processar cada habilidade
        for idx, hab in enumerate(habilidades, 1):
            code = hab.get('code')
            description = escape_sql_string(hab.get('description'))
            subject_id = hab.get('subject_id')
            grade_id = hab.get('grade_id')
            
            if not code or not description:
                continue
            
            f.write(f"    -- [{idx}/{len(habilidades)}] {code}\n")
            f.write("    BEGIN\n")
            f.write(f"        -- Verificar se existe\n")
            f.write(f"        SELECT EXISTS(SELECT 1 FROM public.skill WHERE code = '{code}') INTO v_exists;\n\n")
            f.write(f"        -- INSERT com ON CONFLICT\n")
            f.write(f"        INSERT INTO public.skill (code, description, subject_id, grade_id)\n")
            f.write(f"        VALUES (\n")
            f.write(f"            '{code}',\n")
            f.write(f"            '{description}',\n")
            f.write(f"            '{subject_id}'::uuid,\n")
            
            if grade_id:
                f.write(f"            '{grade_id}'::uuid\n")
            else:
                f.write(f"            NULL\n")
            
            f.write(f"        )\n")
            f.write(f"        ON CONFLICT (code)\n")
            f.write(f"        DO UPDATE SET\n")
            f.write(f"            description = EXCLUDED.description,\n")
            f.write(f"            updated_at = NOW()\n")
            f.write(f"        ;\n\n")
            f.write(f"        IF v_exists THEN\n")
            f.write(f"            v_count_updated := v_count_updated + 1;\n")
            f.write(f"            RAISE NOTICE '   ✏️  [{idx}/{len(habilidades)}] Atualizada: {code}';\n")
            f.write(f"        ELSE\n")
            f.write(f"            v_count_created := v_count_created + 1;\n")
            
            if grade_id:
                grade_short = grade_id[:8]
                f.write(f"            RAISE NOTICE '   ➕ [{idx}/{len(habilidades)}] Criada: {code} (grade={grade_short}...)';\n")
            else:
                f.write(f"            RAISE NOTICE '   ➕ [{idx}/{len(habilidades)}] Criada: {code} (grade=NULL)';\n")
            
            f.write(f"        END IF;\n\n")
            f.write(f"    EXCEPTION WHEN OTHERS THEN\n")
            f.write(f"        v_count_errors := v_count_errors + 1;\n")
            f.write(f"        RAISE WARNING '   ❌ [{idx}/{len(habilidades)}] Erro ao processar {code}: %', SQLERRM;\n")
            f.write(f"    END;\n\n")
        
        # Relatório final
        f.write("    -- Relatório final\n")
        f.write("    RAISE NOTICE '';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '📊 RELATÓRIO FINAL';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '';\n")
        f.write(f"    RAISE NOTICE '  📝 Total de habilidades: {len(habilidades)}';\n")
        f.write("    RAISE NOTICE '  ✏️  Habilidades atualizadas: %', v_count_updated;\n")
        f.write("    RAISE NOTICE '  ➕ Habilidades criadas: %', v_count_created;\n")
        f.write("    RAISE NOTICE '  ❌ Erros: %', v_count_errors;\n")
        f.write("    RAISE NOTICE '';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '✅ SCRIPT CONCLUÍDO COM SUCESSO!';\n")
        f.write("    RAISE NOTICE '======================================================================';\n")
        f.write("    RAISE NOTICE '';\n")
        f.write("END $$;\n\n")
        
        # Queries de validação
        f.write("-- " + "="*76 + "\n")
        f.write("-- VALIDAÇÃO (descomente para executar)\n")
        f.write("-- " + "="*76 + "\n\n")
        f.write("-- Ver habilidades atualizadas recentemente\n")
        f.write("-- SELECT code, LEFT(description, 60) as description, updated_at\n")
        f.write("-- FROM public.skill\n")
        f.write("-- WHERE code LIKE 'EF%' OR code LIKE 'CEEF%'\n")
        f.write("-- ORDER BY updated_at DESC\n")
        f.write("-- LIMIT 20;\n\n")
        f.write("-- Contar total de habilidades por code prefix\n")
        f.write("-- SELECT \n")
        f.write("--     SUBSTRING(code FROM '^[A-Z]+') as prefix,\n")
        f.write("--     COUNT(*) as total\n")
        f.write("-- FROM public.skill\n")
        f.write("-- GROUP BY prefix\n")
        f.write("-- ORDER BY prefix;\n")
    
    print("="*70)
    print("✅ SQL GERADO COM SUCESSO!")
    print("="*70)
    print(f"\n📄 Arquivo: {output_path}")
    print(f"📊 Habilidades processadas: {len(habilidades)}")
    print("\n💡 Para executar:")
    print(f"   psql -U postgres -d afirmeplay_dev -f {os.path.basename(output_path)}")
    print("\n   OU (Docker):")
    print(f"   docker exec -i postgres psql -U postgres -d afirmeplay_dev < {os.path.basename(output_path)}")
    print("")

if __name__ == "__main__":
    generate_sql()
