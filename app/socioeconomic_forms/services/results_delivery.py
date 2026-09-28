# -*- coding: utf-8 -*-
"""Decisão de entrega do relatório socioeconômico (cache, fila ou cálculo na requisição)."""

STALE_AFTER_SECONDS = 20.0


def decide_report_delivery(cache_ready, workers_alive, inflight_age, stale_after=STALE_AFTER_SECONDS):
    """
    Escolhe como responder GET .../results/*.

    ready: cache válido → 200.
    compute_sync: sem worker, fila sem consumidor, ou job antigo que não gravou
        cache → calcular nesta requisição e devolver 200 (ou 4xx/5xx se falhar).
    enqueue: há worker e ainda não há job deste filtro → enfileirar uma vez e 202.
    wait: job já enfileirado e ainda dentro do prazo → 202 sem novo enqueue.
    """
    if cache_ready:
        return "ready"
    if not workers_alive:
        return "compute_sync"
    if inflight_age is None:
        return "enqueue"
    if inflight_age >= stale_after:
        return "compute_sync"
    return "wait"
