"""
Script para atualizar/adicionar habilidades de Português no banco de dados.
Versão direta que evita carregar todas as rotas da aplicação.

COMPORTAMENTO:
- Se a habilidade existir (busca por code): atualiza APENAS a description
- Se não existir: cria nova habilidade com todos os campos do JSON

USO:
    python scripts/update_portuguese_skills_direct.py
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import json
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def get_db_connection():
    """Cria conexão direta com o banco de dados."""
    from app.config import Config
    
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
        sys.exit(1)
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def update_portuguese_skills():
    """
    Função principal que coordena todo o processo de atualização.
    """
    logger.info("\n" + "="*70)
    logger.info("🚀 SCRIPT DE ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS (DIRETO)")
    logger.info("="*70)
    
    # Carregar dados do JSON
    logger.info("\n📂 Carregando dados das habilidades...")
    data = load_habilidades_data()
    habilidades = data.get('habilidades', [])
    logger.info(f"✅ {len(habilidades)} habilidades carregadas do JSON")
    
    # Importar modelo apenas
    from app.models.skill import Skill
    
    # Estatísticas
    stats = {
        'updated': 0,
        'created': 0,
        'errors': 0,
        'skipped': 0
    }
    
    session = get_db_connection()
    
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
                skill = session.query(Skill).filter_by(code=code).first()
                
                if skill:
                    # EXISTE: Atualizar APENAS a description
                    skill.description = description
                    stats['updated'] += 1
                    logger.info(f"   ✏️  [{idx}/{len(habilidades)}] Atualizada: {code}")
                else:
                    # NÃO EXISTE: Criar nova
                    # Converter grade_id para UUID se não for null
                    grade_id_uuid = UUID(grade_id_str) if grade_id_str else None
                    
                    skill = Skill(
                        code=code,
                        description=description,
                        subject_id=subject_id,
                        grade_id=grade_id_uuid
                    )
                    session.add(skill)
                    stats['created'] += 1
                    
                    grade_info = f"grade={grade_id_str[:8]}..." if grade_id_str else "grade=NULL"
                    logger.info(f"   ➕ [{idx}/{len(habilidades)}] Criada: {code} ({grade_info})")
            
            except Exception as e:
                logger.error(f"   ❌ [{idx}/{len(habilidades)}] Erro ao processar {code}: {str(e)}")
                stats['errors'] += 1
        
        # Commit
        logger.info("\n💾 Salvando alterações no banco de dados...")
        session.commit()
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
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    update_portuguese_skills()
