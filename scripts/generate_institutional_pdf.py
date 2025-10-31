import os
import sys
from datetime import datetime

# Garantir que a raiz do projeto esteja no PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app


def main():
    """Gera PDFs institucionais para um teste específico sem frontend/autenticação."""
    # Ler test_id via argumento de linha de comando ou usar padrão
    test_id = None
    if len(sys.argv) > 1:
        test_id = sys.argv[1]
    else:
        # ID padrão fornecido pelo usuário
        test_id = "ec3535d2-3812-4567-a237-e3c5c007b284"

    output_dir = os.path.abspath(os.path.join(os.getcwd(), "generated_pdfs"))
    os.makedirs(output_dir, exist_ok=True)

    app = create_app()

    # Importações internas que precisam do contexto
    from app.services.physical_test_form_service import PhysicalTestFormService

    with app.app_context():
        service = PhysicalTestFormService()
        result = service.generate_physical_forms(test_id=test_id, output_dir=output_dir)

        # Exibir resumo no console
        print("=== Resultado da Geração de Provas Físicas ===")
        if result.get("success"):
            print(f"Mensagem: {result.get('message', 'Sucesso')} ")
            print(f"Prova: {result.get('test_title', '-')}")
            print(f"Total de questões: {result.get('total_questions', 0)}")
            print(f"Total de alunos: {result.get('total_students', 0)}")
            print(f"Formulários gerados: {result.get('generated_forms', 0)}")

            forms = result.get("forms", [])
            if forms:
                print(f"Primeiros 3 formulários:")
                for form in forms[:3]:
                    sid = form.get("student_id") or form.get("aluno_id") or "-"
                    sname = form.get("student_name") or form.get("aluno_nome") or "-"
                    url = form.get("pdf_url") or form.get("file_url") or "(salvo no banco/armazenamento)"
                    print(f" - Aluno: {sname} ({sid}) | PDF: {url}")
        else:
            print("Falha ao gerar formulários.")
            print(f"Erro: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
