#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para recalcular um resultado específico de avaliação

Uso:
    python scripts/recalculate_specific_evaluation_result.py <evaluation_result_id>
    
Exemplo:
    python scripts/recalculate_specific_evaluation_result.py bdda37a4-738f-4b5e-9a80-29352f21595f
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.evaluationResult import EvaluationResult
from app.services.evaluation_result_service import EvaluationResultService
from app.utils.tenant_middleware import set_search_path
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def recalculate_evaluation_result(evaluation_result_id):
    """
    Recalcula um resultado específico de avaliação
    
    Args:
        evaluation_result_id: ID do resultado a recalcular
    """
    try:
        # Buscar o resultado existente
        evaluation_result = EvaluationResult.query.get(evaluation_result_id)
        
        if not evaluation_result:
            logger.error(f"❌ Resultado não encontrado: {evaluation_result_id}")
            return False
        
        logger.info(f"✅ Resultado encontrado:")
        logger.info(f"   Test ID: {evaluation_result.test_id}")
        logger.info(f"   Student ID: {evaluation_result.student_id}")
        logger.info(f"   Session ID: {evaluation_result.session_id}")
        logger.info(f"   Nota atual: {evaluation_result.grade}")
        logger.info(f"   Proficiência atual: {evaluation_result.proficiency}")
        logger.info(f"   Classificação atual: {evaluation_result.classification}")
        
        # Recalcular usando o serviço
        logger.info("\n🔄 Recalculando resultado...")
        
        new_result = EvaluationResultService.calculate_and_save_result(
            test_id=evaluation_result.test_id,
            student_id=evaluation_result.student_id,
            session_id=evaluation_result.session_id
        )
        
        if new_result:
            logger.info("\n✅ Resultado recalculado e salvo com sucesso!")
            logger.info(f"   Nova nota: {new_result.get('grade', 'N/A')}")
            logger.info(f"   Nova proficiência: {new_result.get('proficiency', 'N/A')}")
            logger.info(f"   Nova classificação: {new_result.get('classification', 'N/A')}")
            
            # Buscar resultado atualizado para verificar subject_results
            updated_result = EvaluationResult.query.get(evaluation_result_id)
            if updated_result and updated_result.subject_results:
                logger.info(f"\n📊 Resultados por disciplina salvos:")
                for subject_id, subject_data in updated_result.subject_results.items():
                    logger.info(f"   - {subject_data.get('subject_name', subject_id)}:")
                    logger.info(f"     Nota: {subject_data.get('grade', 'N/A')}")
                    logger.info(f"     Proficiência: {subject_data.get('proficiency', 'N/A')}")
                    logger.info(f"     Classificação: {subject_data.get('classification', 'N/A')}")
            
            return True
        else:
            logger.error("❌ Erro ao recalcular resultado")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao recalcular: {str(e)}", exc_info=True)
        return False


def main():
    """
    Função principal do script
    """
    if len(sys.argv) < 2:
        logger.error("❌ Uso: python scripts/recalculate_specific_evaluation_result.py <evaluation_result_id>")
        sys.exit(1)
    
    evaluation_result_id = sys.argv[1]
    
    logger.info("=" * 80)
    logger.info(f"Recalculando resultado: {evaluation_result_id}")
    logger.info("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        success = recalculate_evaluation_result(evaluation_result_id)
        
        if success:
            logger.info("\n" + "=" * 80)
            logger.info("🎉 Recálculo concluído com sucesso!")
            logger.info("=" * 80)
            sys.exit(0)
        else:
            logger.error("\n" + "=" * 80)
            logger.error("❌ Falha ao recalcular resultado")
            logger.error("=" * 80)
            sys.exit(1)


if __name__ == '__main__':
    main()
