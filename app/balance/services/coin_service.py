# -*- coding: utf-8 -*-
"""
Serviço de moedas do aluno: saldo, crédito, débito e histórico.
"""
from app import db
from app.balance.models import StudentCoins, CoinTransaction


class InsufficientBalanceError(Exception):
    """Erro lançado quando saldo é insuficiente."""

    pass


class CoinService:
    @staticmethod
    def get_balance(student_id: str) -> int:
        """
        Retorna saldo de moedas do aluno.
        Retorna 0 se o aluno ainda não tem registro.
        """
        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        return coins.balance if coins else 0

    @staticmethod
    def credit_coins(student_id: str, amount: int, reason: str, **kwargs) -> CoinTransaction:
        """
        Credita moedas para o aluno.

        Args:
            student_id: ID do aluno
            amount: Quantidade de moedas (deve ser positivo)
            reason: Motivo (competition_participation, competition_rank_1, etc.)
            **kwargs: Campos opcionais (competition_id, test_session_id, description)

        Returns:
            CoinTransaction criada
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        if not coins:
            coins = StudentCoins(student_id=student_id, balance=0)
            db.session.add(coins)

        balance_before = coins.balance
        coins.balance += amount
        balance_after = coins.balance

        transaction = CoinTransaction(
            student_id=student_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reason=reason,
            competition_id=kwargs.get('competition_id'),
            test_session_id=kwargs.get('test_session_id'),
            description=kwargs.get('description'),
        )
        db.session.add(transaction)
        db.session.commit()

        return transaction

    @staticmethod
    def debit_coins(student_id: str, amount: int, reason: str, **kwargs) -> CoinTransaction:
        """
        Debita moedas do aluno (para loja futura).

        Raises:
            InsufficientBalanceError: Se saldo insuficiente
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        if not coins or coins.balance < amount:
            raise InsufficientBalanceError(
                f"Saldo insuficiente. Disponível: {coins.balance if coins else 0}, Requerido: {amount}"
            )

        balance_before = coins.balance
        coins.balance -= amount
        balance_after = coins.balance

        transaction = CoinTransaction(
            student_id=student_id,
            amount=-amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reason=reason,
            competition_id=kwargs.get('competition_id'),
            test_session_id=kwargs.get('test_session_id'),
            description=kwargs.get('description'),
        )
        db.session.add(transaction)
        db.session.commit()

        return transaction

    @staticmethod
    def get_transaction_history(student_id: str, limit: int = 50, offset: int = 0):
        """
        Lista histórico de transações do aluno (mais recentes primeiro).

        Returns:
            Lista de CoinTransaction
        """
        return (
            CoinTransaction.query.filter_by(student_id=student_id)
            .order_by(CoinTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
