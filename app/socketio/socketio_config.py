# -*- coding: utf-8 -*-
"""
Configuração SocketIO para ranking em tempo real de competições.
"""
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import logging

from .auth import get_user_from_token, get_token_from_request
from app.competitions.models import Competition
from app.services.competition_ranking_service import CompetitionRankingService
from app.models.student import Student

logger = logging.getLogger(__name__)

# Inicializar SocketIO (será inicializado com app em app/__init__.py)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)


@socketio.on('connect')
def on_connect():
    """Evento de conexão - validar autenticação."""
    token = get_token_from_request()
    if not token:
        logger.warning("Conexão WebSocket sem token")
        return False
    
    user_payload = get_user_from_token(token)
    if not user_payload:
        logger.warning("Token inválido na conexão WebSocket")
        return False
    
    user_id = user_payload.get('sub')
    logger.info(f"Cliente WebSocket conectado: user_id={user_id}")
    return True


@socketio.on('disconnect')
def on_disconnect():
    """Evento de desconexão."""
    logger.info("Cliente WebSocket desconectado")


@socketio.on('join_competition_ranking')
def on_join_ranking(data):
    """
    Aluno entra na "sala" da competição para receber atualizações de ranking.
    
    Data esperada:
    {
        "competition_id": "...",
        "token": "..." (opcional, se não veio na query)
    }
    """
    try:
        competition_id = data.get('competition_id')
        if not competition_id:
            emit('error', {'message': 'competition_id é obrigatório'})
            return
        
        # Validar token
        token = data.get('token') or get_token_from_request()
        if not token:
            emit('error', {'message': 'Token de autenticação necessário'})
            return
        
        user_payload = get_user_from_token(token)
        if not user_payload:
            emit('error', {'message': 'Token inválido'})
            return
        
        user_id = user_payload.get('sub')
        
        # Verificar se competição existe e está acessível
        competition = Competition.query.get(competition_id)
        if not competition:
            emit('error', {'message': 'Competição não encontrada'})
            return
        
        # Verificar se ranking está visível
        visibility = (competition.ranking_visibility or 'final').strip().lower()
        if visibility == 'final' and competition.status != 'encerrada':
            emit('error', {'message': 'Ranking só é exibido após o encerramento da competição'})
            return
        
        # Entrar na room da competição
        room = f"competition_{competition_id}"
        join_room(room)
        logger.info(f"Usuário {user_id} entrou na room {room}")
        
        # Enviar ranking atual imediatamente
        try:
            ranking = CompetitionRankingService.get_ranking(competition_id, limit=100, enriquecer=True)
            emit('ranking_updated', {
                'competition_id': competition_id,
                'ranking': ranking
            }, room=room)
        except Exception as e:
            logger.error(f"Erro ao buscar ranking inicial: {e}", exc_info=True)
            emit('error', {'message': 'Erro ao buscar ranking'})
    
    except Exception as e:
        logger.exception(f"Erro no evento join_competition_ranking: {e}")
        emit('error', {'message': 'Erro ao entrar na sala de ranking'})


@socketio.on('leave_competition_ranking')
def on_leave_ranking(data):
    """
    Aluno sai da "sala" da competição.
    
    Data esperada:
    {
        "competition_id": "..."
    }
    """
    try:
        competition_id = data.get('competition_id')
        if not competition_id:
            return
        
        room = f"competition_{competition_id}"
        leave_room(room)
        logger.info(f"Cliente saiu da room {room}")
    
    except Exception as e:
        logger.exception(f"Erro no evento leave_competition_ranking: {e}")


def notify_ranking_updated(competition_id: str):
    """
    Notifica todos os clientes na room da competição que o ranking foi atualizado.
    Deve ser chamado após alguém entregar a prova.
    """
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            logger.warning(f"Competição {competition_id} não encontrada para notificar ranking")
            return
        
        # Verificar se ranking está visível
        visibility = (competition.ranking_visibility or 'final').strip().lower()
        if visibility == 'final' and competition.status != 'encerrada':
            # Ranking não visível ainda, não notificar
            return
        
        # Buscar ranking atualizado
        ranking = CompetitionRankingService.get_ranking(competition_id, limit=100, enriquecer=True)
        
        # Emitir para a room da competição
        room = f"competition_{competition_id}"
        socketio.emit('ranking_updated', {
            'competition_id': competition_id,
            'ranking': ranking
        }, room=room)
        
        logger.info(f"Ranking atualizado notificado para competição {competition_id}")
    
    except Exception as e:
        logger.exception(f"Erro ao notificar ranking atualizado: {e}")
