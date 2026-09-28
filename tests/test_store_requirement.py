# -*- coding: utf-8 -*-
"""Testes do requisito de desempenho da loja."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.models  # noqa: F401

from app.store.services.requirement_service import (
    check_requirement,
    missing_reason,
    validate_requirement,
)
from app.store.services.store_service import (
    AlreadyPurchasedError,
    RequirementNotMetError,
    StoreService,
)


def _item(**kwargs):
    data = dict(
        id='item-1',
        name='Item exclusivo',
        price=15,
        category='stamp',
        reward_type='stamp',
        reward_data='highlight',
        requirement=None,
        is_active=True,
        scope_type='system',
        scope_filter=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _query(result):
    q = MagicMock()
    q.filter_by.return_value = q
    q.first.return_value = result
    return q


def _snap(**kwargs):
    data = dict(
        band='Aprendiz',
        general_grade=5.0,
        general_classification='Básico',
        medals={},
        achievement_names={},
    )
    data.update(kwargs)
    return data


class TestValidateRequirement(unittest.TestCase):
    def test_none_and_empty_are_null(self):
        self.assertIsNone(validate_requirement(None))
        self.assertIsNone(validate_requirement({}))
        self.assertIsNone(validate_requirement(''))

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            validate_requirement({'type': 'reading_level'})

    def test_accepts_supported_types(self):
        self.assertEqual(
            validate_requirement({'type': 'competition_band', 'min_band': 'Destaque'})['min_band'],
            'Destaque',
        )
        self.assertEqual(
            validate_requirement({'type': 'eval_min_grade', 'min_grade': 7})['min_grade'],
            7.0,
        )
        self.assertEqual(
            validate_requirement({'type': 'eval_classification', 'min_classification': 'Adequado'})['min_classification'],
            'Adequado',
        )
        parsed = validate_requirement({
            'type': 'achievement',
            'id': 'avaliacoes_concluidas',
            'medal': 'ouro',
        })
        self.assertEqual(parsed['id'], 'avaliacoes_concluidas')
        self.assertEqual(parsed['medal'], 'ouro')


class TestCheckRequirement(unittest.TestCase):
    def test_no_requirement_is_met(self):
        met, reason = check_requirement('st1', None)
        self.assertTrue(met)
        self.assertEqual(reason, '')

    def test_competition_band_not_met(self):
        met, reason = check_requirement(
            'st1',
            {'type': 'competition_band', 'min_band': 'Destaque'},
            snapshot=_snap(band='Aprendiz'),
        )
        self.assertFalse(met)
        self.assertIn('Destaque', reason)

    def test_competition_band_met(self):
        met, reason = check_requirement(
            'st1',
            {'type': 'competition_band', 'min_band': 'Destaque'},
            snapshot=_snap(band='Mestre do Saber'),
        )
        self.assertTrue(met)
        self.assertEqual(reason, '')

    def test_eval_min_grade(self):
        req = {'type': 'eval_min_grade', 'min_grade': 7}
        met, _ = check_requirement('st1', req, snapshot=_snap(general_grade=6.9))
        self.assertFalse(met)
        met, _ = check_requirement('st1', req, snapshot=_snap(general_grade=7.0))
        self.assertTrue(met)

    def test_eval_classification(self):
        req = {'type': 'eval_classification', 'min_classification': 'Adequado'}
        met, _ = check_requirement('st1', req, snapshot=_snap(general_classification='Básico'))
        self.assertFalse(met)
        met, _ = check_requirement('st1', req, snapshot=_snap(general_classification='Avançado'))
        self.assertTrue(met)

    def test_achievement_uses_medal_order(self):
        req = {'type': 'achievement', 'id': 'avaliacoes_concluidas', 'medal': 'ouro'}
        met, _ = check_requirement(
            'st1', req, snapshot=_snap(medals={'avaliacoes_concluidas': 'prata'})
        )
        self.assertFalse(met)
        met, _ = check_requirement(
            'st1', req, snapshot=_snap(medals={'avaliacoes_concluidas': 'platina'})
        )
        self.assertTrue(met)

    def test_missing_reason_text_comes_from_service(self):
        text = missing_reason({'type': 'competition_band', 'min_band': 'Destaque'})
        self.assertEqual(text, 'Alcance a faixa Destaque para desbloquear')


class TestPurchaseWithRequirement(unittest.TestCase):
    def _run_purchase(self, item, has_purchased, check_result=(True, '')):
        debit = MagicMock(return_value=SimpleNamespace(balance_after=10))
        purchase_row = MagicMock()
        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=has_purchased), \
             patch('app.store.services.store_service.CoinService.debit_coins', debit), \
             patch('app.store.services.store_service.StudentPurchase', return_value=purchase_row), \
             patch('app.store.services.store_service.db.session'), \
             patch(
                 'app.store.services.requirement_service.check_requirement',
                 return_value=check_result,
             ):
            StoreItemCls.query = _query(item)
            result = StoreService.purchase('st1', item.id)
        return result, debit

    def test_purchase_without_requirement_unchanged(self):
        item = _item(requirement=None)
        (purchase, _tx), debit = self._run_purchase(item, has_purchased=False)
        self.assertIsNotNone(purchase)
        debit.assert_called_once()

    def test_purchase_with_requirement_met(self):
        item = _item(requirement={'type': 'eval_min_grade', 'min_grade': 7})
        (purchase, _tx), debit = self._run_purchase(
            item, has_purchased=False, check_result=(True, '')
        )
        self.assertIsNotNone(purchase)
        debit.assert_called_once()

    def test_purchase_with_requirement_not_met(self):
        item = _item(requirement={'type': 'competition_band', 'min_band': 'Destaque'})
        debit = MagicMock()
        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=False), \
             patch('app.store.services.store_service.CoinService.debit_coins', debit), \
             patch(
                 'app.store.services.requirement_service.check_requirement',
                 return_value=(False, 'Alcance a faixa Destaque para desbloquear'),
             ):
            StoreItemCls.query = _query(item)
            with self.assertRaises(RequirementNotMetError) as ctx:
                StoreService.purchase('st1', item.id)
            self.assertIn('Destaque', str(ctx.exception))
            debit.assert_not_called()

    def test_prior_purchase_kept_when_requirement_added_later(self):
        item = _item(requirement={'type': 'eval_min_grade', 'min_grade': 9})
        debit = MagicMock()
        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=True), \
             patch('app.store.services.store_service.CoinService.debit_coins', debit), \
             patch(
                 'app.store.services.requirement_service.check_requirement',
                 return_value=(False, 'não deveria ser chamado'),
             ) as check:
            StoreItemCls.query = _query(item)
            with self.assertRaises(AlreadyPurchasedError):
                StoreService.purchase('st1', item.id)
            debit.assert_not_called()
            check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
