"""
Script para popular o campo classes da tabela test com as classes
que foram aplicadas (existem em class_test).

Este script preenche o campo classes para avaliações que já foram aplicadas,
extraindo os class_ids da tabela class_test.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.test import Test
from app.models.classTest import ClassTest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_test_classes_field():
    """Preenche o campo classes das avaliações que foram aplicadas"""
    
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("🔄 Iniciando população do campo classes nas avaliações...")
            
            # Buscar todas as avaliações
            all_tests = Test.query.all()
            logger.info(f"📊 Total de avaliações encontradas: {len(all_tests)}")
            
            updated_count = 0
            already_filled_count = 0
            not_applied_count = 0
            
            for test in all_tests:
                # Buscar class_tests para esta avaliação
                class_tests = ClassTest.query.filter_by(test_id=test.id).all()
                
                if not class_tests:
                    # Avaliação não foi aplicada
                    not_applied_count += 1
                    logger.debug(f"  ⏭️  Teste {test.id} ({test.title}): Não aplicado, pulando...")
                    continue
                
                # Extrair os class_ids dos class_tests
                class_ids = [ct.class_id for ct in class_tests]
                
                # Verificar se o campo classes já está preenchido
                if test.classes:
                    # Verificar se já contém os mesmos IDs
                    existing_classes = test.classes if isinstance(test.classes, list) else [test.classes]
                    if set(existing_classes) == set(class_ids):
                        already_filled_count += 1
                        logger.debug(f"  ✅ Teste {test.id} ({test.title}): Campo classes já preenchido corretamente")
                        continue
                    else:
                        logger.info(f"  🔄 Teste {test.id} ({test.title}): Atualizando classes de {existing_classes} para {class_ids}")
                
                # Atualizar o campo classes
                test.classes = class_ids
                updated_count += 1
                logger.info(f"  ✏️  Teste {test.id} ({test.title}): Preenchendo classes com {len(class_ids)} classe(s): {class_ids}")
            
            # Commit de todas as alterações
            db.session.commit()
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("📊 RESUMO DA POPULAÇÃO:")
            logger.info(f"  ✅ Avaliações atualizadas: {updated_count}")
            logger.info(f"  ℹ️  Avaliações já preenchidas: {already_filled_count}")
            logger.info(f"  ⏭️  Avaliações não aplicadas: {not_applied_count}")
            logger.info(f"  📦 Total processado: {len(all_tests)}")
            logger.info("=" * 60)
            logger.info("✅ População do campo classes concluída com sucesso!")
            
            # Verificar resultado
            tests_with_classes = Test.query.filter(Test.classes.isnot(None)).count()
            logger.info(f"📊 Total de avaliações com campo classes preenchido: {tests_with_classes}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro durante a população: {str(e)}", exc_info=True)
            raise
        finally:
            db.session.close()

if __name__ == "__main__":
    populate_test_classes_field()

