"""
Script para atualizar/adicionar habilidades de Português no banco de dados.

COMPORTAMENTO:
- Se a habilidade existir (busca por code): atualiza APENAS a description
- Se não existir: cria nova habilidade com todos os campos do JSON

IMPORTANTE: Coloque todas as habilidades no arquivo habilidades_portugues_data.json
com o formato:
{
  "habilidades": [
    {
      "code": "EF01LP01",
      "description": "...",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": "391ed6e8-fc45-46f8-8e4c-065005d2329f"  ou null
    },
    ...
  ]
}

USO:
    python scripts/update_portuguese_skills.py
    python scripts/update_portuguese_skills.py 9A1.1 9A2.1 9A2.2   # processa só esses códigos
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import json
from uuid import UUID

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def load_habilidades_data():
    """Carrega dados das habilidades do arquivo JSON."""
    json_path = os.path.join(os.path.dirname(__file__), 'habilidades_portugues_data.json')
    
    if not os.path.exists(json_path):
        logger.error(f"❌ Arquivo não encontrado: {json_path}")
        logger.error("   Por favor, crie o arquivo com os dados das habilidades.")
        sys.exit(1)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_portuguese_skills():
    """
    Função principal que coordena todo o processo de atualização.
    """
    logger.info("\n" + "="*70)
    logger.info("🚀 SCRIPT DE ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS")
    logger.info("="*70)
    
    # Carregar dados do JSON
    logger.info("\n📂 Carregando dados das habilidades...")
    data = load_habilidades_data()
    habilidades = data.get('habilidades', [])
    # Filtrar por códigos se passados na linha de comando
    only_codes = [c.strip() for c in sys.argv[1:] if c.strip()]
    if only_codes:
        habilidades = [h for h in habilidades if h.get('code') in only_codes]
        logger.info(f"✅ Filtrado: {len(habilidades)} habilidades (códigos: {', '.join(only_codes)})")
    else:
        logger.info(f"✅ {len(habilidades)} habilidades carregadas do JSON")
    if not habilidades:
        logger.warning("Nenhuma habilidade para processar.")
        return
    # Importações do app
    from app import create_app, db
    from app.models.skill import Skill
    from app.models.grades import Grade
    
    # Estatísticas
    stats = {
        'updated': 0,
        'created': 0,
        'errors': 0,
        'skipped': 0
    }
    
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("\n" + "="*70)
            logger.info("📦 PROCESSANDO HABILIDADES")
            logger.info("="*70 + "\n")
            
            for idx, hab in enumerate(habilidades, 1):
                code = hab.get('code')
                description = hab.get('description')
                subject_id = hab.get('subject_id')
                grade_id_str = hab.get('grade_id')
                
                if not code or not description:
                    logger.warning(f"   ⚠️  Item {idx}: Faltando code ou description, pulando...")
                    stats['skipped'] += 1
                    continue
                
                try:
                    # Buscar habilidade existente por code
                    skill = Skill.query.filter_by(code=code).first()
                    
                    if skill:
                        # EXISTE: Atualizar description, subject_id e garantir vínculo com a série
                        skill.description = description
                        if subject_id is not None:
                            skill.subject_id = subject_id
                        if grade_id_str:
                            grade_id_uuid = UUID(grade_id_str)
                            grade = Grade.query.get(grade_id_uuid)
                            if grade and grade not in (skill.grades or []):
                                skill.grades.append(grade)
                        stats['updated'] += 1
                        logger.info(f"   ✏️  [{idx}/{len(habilidades)}] Atualizada: {code}")
                    else:
                        # NÃO EXISTE: Criar nova (modelo usa skill_grade N:N, não grade_id)
                        skill = Skill(
                            code=code,
                            description=description,
                            subject_id=subject_id,
                        )
                        db.session.add(skill)
                        db.session.flush()
                        if grade_id_str:
                            grade_id_uuid = UUID(grade_id_str)
                            grade = Grade.query.get(grade_id_uuid)
                            if grade:
                                skill.grades.append(grade)
                        stats['created'] += 1
                        grade_info = f"grade={grade_id_str[:8]}..." if grade_id_str else "grade=NULL"
                        logger.info(f"   ➕ [{idx}/{len(habilidades)}] Criada: {code} ({grade_info})")
                
                except Exception as e:
                    logger.error(f"   ❌ [{idx}/{len(habilidades)}] Erro ao processar {code}: {str(e)}")
                    stats['errors'] += 1
            
            # Commit
            logger.info("\n💾 Salvando alterações no banco de dados...")
            db.session.commit()
            logger.info("✅ Commit realizado com sucesso!")
            
            # Relatório final
            logger.info("\n" + "="*70)
            logger.info("📊 RELATÓRIO FINAL")
            logger.info("="*70)
            logger.info(f"\n  📝 Total de habilidades no JSON: {len(habilidades)}")
            logger.info(f"  ✏️  Habilidades atualizadas: {stats['updated']}")
            logger.info(f"  ➕ Habilidades criadas: {stats['created']}")
            logger.info(f"  ⏭️  Habilidades puladas: {stats['skipped']}")
            logger.info(f"  ❌ Erros: {stats['errors']}")
            logger.info("\n" + "="*70)
            logger.info("✅ SCRIPT CONCLUÍDO COM SUCESSO!")
            logger.info("="*70 + "\n")
            
        except Exception as e:
            logger.error(f"\n❌ ERRO CRÍTICO: {str(e)}")
            logger.error("🔄 Fazendo rollback...")
            db.session.rollback()
            raise
        finally:
            db.session.close()


if __name__ == "__main__":
    update_portuguese_skills()
