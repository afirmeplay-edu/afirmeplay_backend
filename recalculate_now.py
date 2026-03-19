"""
Script temporário para recalcular resultado específico
Execute com: flask shell < recalculate_now.py
"""

from app.models.evaluationResult import EvaluationResult
from app.services.evaluation_result_service import EvaluationResultService
from app import db

evaluation_result_id = 'bdda37a4-738f-4b5e-9a80-29352f21595f'

print("=" * 80)
print(f"Recalculando resultado: {evaluation_result_id}")
print("=" * 80)

# Buscar o resultado existente
evaluation_result = EvaluationResult.query.get(evaluation_result_id)

if not evaluation_result:
    print(f"❌ Resultado não encontrado: {evaluation_result_id}")
else:
    print(f"✅ Resultado encontrado:")
    print(f"   Test ID: {evaluation_result.test_id}")
    print(f"   Student ID: {evaluation_result.student_id}")
    print(f"   Session ID: {evaluation_result.session_id}")
    print(f"   Nota atual: {evaluation_result.grade}")
    print(f"   Proficiência atual: {evaluation_result.proficiency}")
    print(f"   Classificação atual: {evaluation_result.classification}")
    
    # Recalcular usando o serviço
    print("\n🔄 Recalculando resultado...")
    
    new_result = EvaluationResultService.calculate_and_save_result(
        test_id=evaluation_result.test_id,
        student_id=evaluation_result.student_id,
        session_id=evaluation_result.session_id
    )
    
    if new_result:
        print("\n✅ Resultado recalculado e salvo com sucesso!")
        print(f"   Nova nota: {new_result.get('grade', 'N/A')}")
        print(f"   Nova proficiência: {new_result.get('proficiency', 'N/A')}")
        print(f"   Nova classificação: {new_result.get('classification', 'N/A')}")
        
        # Buscar resultado atualizado para verificar subject_results
        updated_result = EvaluationResult.query.get(evaluation_result_id)
        if updated_result and updated_result.subject_results:
            print(f"\n📊 Resultados por disciplina salvos:")
            for subject_id, subject_data in updated_result.subject_results.items():
                print(f"   - {subject_data.get('subject_name', subject_id)}:")
                print(f"     Nota: {subject_data.get('grade', 'N/A')}")
                print(f"     Proficiência: {subject_data.get('proficiency', 'N/A')}")
                print(f"     Classificação: {subject_data.get('classification', 'N/A')}")
        
        print("\n" + "=" * 80)
        print("🎉 Recálculo concluído com sucesso!")
        print("=" * 80)
    else:
        print("❌ Erro ao recalcular resultado")
