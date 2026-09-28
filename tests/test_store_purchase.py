# -*- coding: utf-8 -*-
"""Testes dos bugs de compra única e persistência de moldura."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.models  # noqa: F401

from app.store.services.store_service import (
    AlreadyPurchasedError,
    StoreService,
)


def _item(**kwargs):
    data = dict(
        id='item-1',
        name='Moldura ouro',
        price=10,
        category='frame',
        reward_type='frame',
        reward_data='gold',
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
    q.order_by.return_value = q
    q.limit.return_value = q
    q.offset.return_value = q
    q.first.return_value = result
    q.all.return_value = result if isinstance(result, list) else ([result] if result else [])
    return q


class TestStorePurchaseUnique(unittest.TestCase):
    def test_repurchase_is_rejected_without_debit(self):
        item = _item()
        debit = MagicMock()
        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=True), \
             patch('app.store.services.store_service.CoinService.debit_coins', debit):
            StoreItemCls.query = _query(item)
            with self.assertRaises(AlreadyPurchasedError) as ctx:
                StoreService.purchase('st1', item.id)
            self.assertIn('já comprou', str(ctx.exception).lower())
            debit.assert_not_called()

    def test_first_purchase_without_requirement_debits_and_records(self):
        item = _item(reward_type='stamp', reward_data='highlight')
        purchase_row = MagicMock()
        debit_tx = SimpleNamespace(balance_after=90)
        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=False), \
             patch('app.store.services.store_service.CoinService.debit_coins', return_value=debit_tx), \
             patch('app.store.services.store_service.StudentPurchase', return_value=purchase_row), \
             patch('app.store.services.store_service.db.session') as session:
            StoreItemCls.query = _query(item)
            purchase, tx = StoreService.purchase('st1', item.id)
        self.assertIs(purchase, purchase_row)
        self.assertEqual(tx.balance_after, 90)
        session.add.assert_called()
        session.commit.assert_called()


class TestStoreFramePersistence(unittest.TestCase):
    def test_purchased_frame_is_owned_on_fresh_server_query(self):
        """Simula reload: posse vem de student_purchases + user_settings, sem estado do cliente."""
        item = _item()
        purchase_row = MagicMock()
        debit_tx = SimpleNamespace(balance_after=40)
        settings = SimpleNamespace(user_id='user-1', frame_id=None)
        settings_query = _query(settings)

        with patch('app.store.services.store_service.StoreItem') as StoreItemCls, \
             patch.object(StoreService, 'has_purchased', return_value=False), \
             patch('app.store.services.store_service.CoinService.debit_coins', return_value=debit_tx), \
             patch('app.store.services.store_service.StudentPurchase', return_value=purchase_row), \
             patch('app.store.services.store_service.db.session'), \
             patch('app.models.user_settings.UserSettings') as UserSettingsCls:
            StoreItemCls.query = _query(item)
            UserSettingsCls.query = settings_query
            StoreService.purchase('st1', item.id, user_id='user-1')

        self.assertEqual(settings.frame_id, 'gold')

        owned_query = _query(purchase_row)
        with patch('app.store.services.store_service.StudentPurchase') as PurchaseCls:
            PurchaseCls.query = owned_query
            self.assertTrue(StoreService.has_purchased('st1', item.id))
            purchases = StoreService.get_student_purchases('st1')
        self.assertEqual(purchases, [purchase_row])


if __name__ == '__main__':
    unittest.main()
