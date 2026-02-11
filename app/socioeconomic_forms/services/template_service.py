# -*- coding: utf-8 -*-
"""
Serviço para carregar templates de questionários socioeconômicos
"""

import json
from pathlib import Path


class TemplateService:
    """Serviço para carregar templates de perguntas"""
    
    # Diretório onde os templates estão armazenados
    TEMPLATES_DIR = Path(__file__).parent.parent / 'templates'
    
    # Mapeamento de formType para arquivo de template
    TEMPLATE_FILES = {
        'aluno-jovem': 'aluno_jovem_questions.json',
        'aluno-velho': 'aluno_velho_questions.json',
        # 'professor': 'professor_questions.json',  # A ser criado
        # 'diretor': 'diretor_questions.json',  # A ser criado
        # 'secretario': 'secretario_questions.json',  # A ser criado
    }
    
    @staticmethod
    def load_template(form_type):
        """
        Carrega o template de perguntas para um tipo de formulário
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, etc.)
            
        Returns:
            dict: Dicionário com o template (title, description, questions)
            None: Se o template não existir
            
        Example:
            >>> template = TemplateService.load_template('aluno-jovem')
            >>> print(template['title'])
            'Questionário Socioeconômico - Aluno Jovem'
            >>> print(len(template['questions']))
            24
        """
        if form_type not in TemplateService.TEMPLATE_FILES:
            return None
        
        template_file = TemplateService.TEMPLATE_FILES[form_type]
        template_path = TemplateService.TEMPLATES_DIR / template_file
        
        if not template_path.exists():
            return None
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            return template
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar template {template_file}: {str(e)}")
            return None
    
    @staticmethod
    def get_questions(form_type):
        """
        Obtém apenas as perguntas do template
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, etc.)
            
        Returns:
            list: Lista de perguntas do template
            None: Se o template não existir
            
        Example:
            >>> questions = TemplateService.get_questions('aluno-jovem')
            >>> print(questions[0]['id'])
            'q1'
            >>> print(questions[0]['text'])
            'Qual é o seu curso/série atual?'
        """
        template = TemplateService.load_template(form_type)
        if template:
            return template.get('questions', [])
        return None
    
    @staticmethod
    def get_available_templates():
        """
        Lista todos os templates disponíveis
        
        Returns:
            list: Lista de tipos de formulários com templates disponíveis
            
        Example:
            >>> templates = TemplateService.get_available_templates()
            >>> print(templates)
            ['aluno-jovem']
        """
        available = []
        for form_type, template_file in TemplateService.TEMPLATE_FILES.items():
            template_path = TemplateService.TEMPLATES_DIR / template_file
            if template_path.exists():
                available.append(form_type)
        return available
    
    @staticmethod
    def create_form_with_template(form_type, title=None, description=None, **kwargs):
        """
        Cria um payload de formulário usando o template
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, etc.)
            title: Título customizado (opcional, usa o do template se não fornecido)
            description: Descrição customizada (opcional)
            **kwargs: Outros campos do formulário (targetGroups, selectedSchools, etc.)
            
        Returns:
            dict: Payload completo para criar o formulário
            None: Se o template não existir
            
        Example:
            >>> payload = TemplateService.create_form_with_template(
            ...     'aluno-jovem',
            ...     title='Questionário 2025',
            ...     targetGroups=['alunos'],
            ...     selectedSchools=['school-id-1'],
            ...     selectedGrades=['grade-id-1']
            ... )
        """
        template = TemplateService.load_template(form_type)
        if not template:
            return None
        
        payload = {
            'title': title if title else template['title'],
            'description': description if description else template['description'],
            'formType': form_type,
            'questions': template['questions'],
        }
        
        # Adicionar outros campos fornecidos
        payload.update(kwargs)
        
        return payload
