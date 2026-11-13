# -*- coding: utf-8 -*-
"""Importa AnswerSheetCorrectionNewGrid sem Flask/DB/weasyprint."""
import importlib.util
import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_omr_class():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    if "app" not in sys.modules:
        app_mod = types.ModuleType("app")
        app_mod.__path__ = [os.path.join(ROOT, "app")]
        app_mod.db = types.SimpleNamespace()
        sys.modules["app"] = app_mod

    for name in ["app.services", "app.services.cartao_resposta"]:
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [os.path.join(ROOT, *name.split("."))]
            sys.modules[name] = m

    mod_name = "app.services.cartao_resposta.correction_new_grid"
    if mod_name in sys.modules and hasattr(sys.modules[mod_name], "AnswerSheetCorrectionNewGrid"):
        return sys.modules[mod_name].AnswerSheetCorrectionNewGrid

    path = os.path.join(ROOT, "app", "services", "cartao_resposta", "correction_new_grid.py")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.AnswerSheetCorrectionNewGrid


def default_topology(n_blocks: int = 4, q_per_block: int = 11):
    """Topologia padrão 4×11, alternativas A–D, questões 1..44."""
    blocks = []
    q = 1
    for b in range(1, n_blocks + 1):
        qs = []
        for _ in range(q_per_block):
            qs.append({"q": q, "alternatives": ["A", "B", "C", "D"]})
            q += 1
        blocks.append({"block_id": b, "questions": qs})
    return {
        "num_blocks": n_blocks,
        "use_blocks": True,
        "total_questions": n_blocks * q_per_block,
        "topology": {"blocks": blocks},
    }
