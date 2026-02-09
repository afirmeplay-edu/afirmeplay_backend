#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para popular cache inicial de resultados de formulários socioeconômicos.
Útil para migração de dados ou quando o cache foi limpo.

Uso:
    python scripts/populate_socioeconomic_cache.py              # Todos os formulários
    python scripts/populate_socioeconomic_cache.py --form-id abc123  # Formulário específico
"""

import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv('app/.env')

from app import create_app, db
from app.socioeconomic_forms.models import Form, FormResponse, FormResultCache
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.models import School, City
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def identify_filter_combinations(form):
    """
    Identifica combinações de filtros para gerar cache.
    Mesma lógica do results_migration_tasks.py
    """
    combinations = []
    
    # Caso 1: Form tem filters preenchido
    if form.filters and (form.filters.get('estado') or form.filters.get('municipio')):
        logger.info(f"Form {form.id} tem filters: {form.filters}")
        
        base_filters = {
            'state': form.filters.get('estado'),
            'municipio': form.filters.get('municipio')
        }
        combinations.append({k: v for k, v in base_filters.items() if v})
        
        if form.filters.get('escola'):
            school_filters = base_filters.copy()
            school_filters['escola'] = form.filters['escola']
            combinations.append({k: v for k, v in school_filters.items() if v})
            
            if form.filters.get('serie'):
                grade_filters = school_filters.copy()
                grade_filters['serie'] = form.filters['serie']
                combinations.append({k: v for k, v in grade_filters.items() if v})
    
    # Caso 2: Construir baseado em selected_*
    else:
        logger.info(f"Form {form.id} NÃO tem filters. Construindo baseado em selected_*")
        
        if form.selected_schools and len(form.selected_schools) > 0:
            first_school_id = form.selected_schools[0]
            school = School.query.get(first_school_id)
            
            if school and school.city_id:
                city = City.query.get(school.city_id)
                
                if city:
                    base_filters = {
                        'state': city.state,
                        'municipio': city.id
                    }
                    combinations.append(base_filters)
                    
                    # Adicionar por escola
                    for school_id in form.selected_schools[:5]:
                        school_filters = base_filters.copy()
                        school_filters['escola'] = school_id
                        combinations.append(school_filters)
                        
                        # Se tem séries, adicionar
                        if form.selected_grades:
                            for grade_id in form.selected_grades[:3]:
                                grade_filters = school_filters.copy()
                                grade_filters['serie'] = grade_id
                                combinations.append(grade_filters)
    
    # Remover duplicatas
    unique_combinations = []
    seen = set()
    for combo in combinations:
        key = tuple(sorted(combo.items()))
        if key not in seen:
            seen.add(key)
            unique_combinations.append(combo)
    
    return unique_combinations


def populate_cache_for_form(form_id, dry_run=False):
    """
    Popula cache para um formulário específico.
    
    Args:
        form_id: ID do formulário
        dry_run: Se True, apenas mostra o que seria feito sem executar
    
    Returns:
        Dict com estatísticas
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Processando formulário: {form_id}")
    logger.info(f"{'='*60}")
    
    form = Form.query.get(form_id)
    if not form:
        logger.error(f"Formulário {form_id} não encontrado")
        return {'success': False, 'error': 'Formulário não encontrado'}
    
    logger.info(f"Título: {form.title}")
    logger.info(f"Tipo: {form.form_type}")
    
    # Verificar respostas
    responses_count = FormResponse.query.filter_by(
        form_id=form_id,
        status='completed'
    ).count()
    
    logger.info(f"Respostas completas: {responses_count}")
    
    if responses_count == 0:
        logger.warning(f"Formulário não tem respostas completas. Pulando.")
        return {
            'success': True,
            'skipped': True,
            'reason': 'Sem respostas completas'
        }
    
    # Identificar combinações de filtros
    filter_combinations = identify_filter_combinations(form)
    logger.info(f"\nCombinações de filtros identificadas: {len(filter_combinations)}")
    
    caches_created = 0
    caches_skipped = 0
    
    for idx, filters in enumerate(filter_combinations, 1):
        logger.info(f"\n--- Combinação {idx}/{len(filter_combinations)} ---")
        logger.info(f"Filtros: {filters}")
        
        # Verificar se já existe cache
        existing_indices = ResultsCacheService.get(form_id, 'indices', filters)
        existing_profiles = ResultsCacheService.get(form_id, 'profiles', filters)
        
        if existing_indices and not existing_indices.is_dirty:
            logger.info(f"  ✓ Cache 'indices' já existe e está válido. Pulando.")
            caches_skipped += 1
        else:
            if dry_run:
                logger.info(f"  [DRY RUN] Criaria cache 'indices'")
            else:
                logger.info(f"  → Gerando cache 'indices'...")
                try:
                    result = ResultsService.calculate_general_indices(form_id, filters, page=1, limit=20)
                    ResultsCacheService.save(
                        form_id=form_id,
                        report_type='indices',
                        filters=filters,
                        result=result,
                        student_count=result.get('totalRespostas', 0),
                        commit=True
                    )
                    logger.info(f"  ✓ Cache 'indices' criado com sucesso")
                    caches_created += 1
                except Exception as e:
                    logger.error(f"  ✗ Erro ao criar cache 'indices': {str(e)}")
        
        if existing_profiles and not existing_profiles.is_dirty:
            logger.info(f"  ✓ Cache 'profiles' já existe e está válido. Pulando.")
            caches_skipped += 1
        else:
            if dry_run:
                logger.info(f"  [DRY RUN] Criaria cache 'profiles'")
            else:
                logger.info(f"  → Gerando cache 'profiles'...")
                try:
                    result = ResultsService.calculate_profiles_report(form_id, filters)
                    ResultsCacheService.save(
                        form_id=form_id,
                        report_type='profiles',
                        filters=filters,
                        result=result,
                        student_count=result.get('totalRespostas', 0),
                        commit=True
                    )
                    logger.info(f"  ✓ Cache 'profiles' criado com sucesso")
                    caches_created += 1
                except Exception as e:
                    logger.error(f"  ✗ Erro ao criar cache 'profiles': {str(e)}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Resumo para form_id={form_id}:")
    logger.info(f"  Caches criados: {caches_created}")
    logger.info(f"  Caches pulados: {caches_skipped}")
    logger.info(f"{'='*60}\n")
    
    return {
        'success': True,
        'form_id': form_id,
        'caches_created': caches_created,
        'caches_skipped': caches_skipped
    }


def populate_all_forms(dry_run=False):
    """
    Popula cache para todos os formulários que têm respostas.
    
    Args:
        dry_run: Se True, apenas mostra o que seria feito
    """
    logger.info("\n" + "="*60)
    logger.info("POPULAÇÃO DE CACHE DE TODOS OS FORMULÁRIOS")
    logger.info("="*60 + "\n")
    
    # Buscar formulários com respostas
    forms_with_responses = db.session.query(
        Form.id, 
        Form.title,
        db.func.count(FormResponse.id).label('response_count')
    ).join(
        FormResponse, Form.id == FormResponse.form_id
    ).filter(
        FormResponse.status == 'completed'
    ).group_by(
        Form.id, Form.title
    ).having(
        db.func.count(FormResponse.id) > 0
    ).all()
    
    total_forms = len(forms_with_responses)
    logger.info(f"Total de formulários com respostas: {total_forms}\n")
    
    if total_forms == 0:
        logger.warning("Nenhum formulário com respostas encontrado.")
        return
    
    # Processar cada formulário
    total_created = 0
    total_skipped = 0
    
    for idx, (form_id, form_title, response_count) in enumerate(forms_with_responses, 1):
        logger.info(f"\n{'#'*60}")
        logger.info(f"Formulário {idx}/{total_forms}")
        logger.info(f"ID: {form_id}")
        logger.info(f"Título: {form_title}")
        logger.info(f"Respostas: {response_count}")
        logger.info(f"{'#'*60}")
        
        result = populate_cache_for_form(form_id, dry_run=dry_run)
        
        if result.get('success'):
            total_created += result.get('caches_created', 0)
            total_skipped += result.get('caches_skipped', 0)
    
    # Resumo final
    logger.info("\n" + "="*60)
    logger.info("RESUMO FINAL")
    logger.info("="*60)
    logger.info(f"Total de formulários processados: {total_forms}")
    logger.info(f"Total de caches criados: {total_created}")
    logger.info(f"Total de caches pulados: {total_skipped}")
    logger.info("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Popula cache inicial de resultados de formulários socioeconômicos'
    )
    parser.add_argument(
        '--form-id',
        type=str,
        help='ID de um formulário específico (opcional)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra o que seria feito sem executar'
    )
    
    args = parser.parse_args()
    
    # Criar app Flask
    app = create_app()
    
    with app.app_context():
        if args.form_id:
            # Processar formulário específico
            logger.info(f"Modo: Formulário específico (ID: {args.form_id})")
            if args.dry_run:
                logger.info("⚠️ DRY RUN - Nenhuma alteração será feita\n")
            
            populate_cache_for_form(args.form_id, dry_run=args.dry_run)
        else:
            # Processar todos os formulários
            logger.info("Modo: Todos os formulários")
            if args.dry_run:
                logger.info("⚠️ DRY RUN - Nenhuma alteração será feita\n")
            
            populate_all_forms(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
