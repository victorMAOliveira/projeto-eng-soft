from datetime import UTC, datetime, timedelta

import pytest
from recommendation_service.recommender import (
    OfferFeatures,
    StudentFeatures,
    Weights,
    cold_start,
    content_scores,
    hard_filter_reasons,
    jaccard,
    normalize,
    preference_score,
    rank_candidates,
    recommend_for_student,
)

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def offer(id_: int, **kw) -> OfferFeatures:
    base = dict(
        id=id_,
        title="Estágio",
        description="Desenvolvimento de software",
        requirements=["Python"],
        course="Ciência da Computação",
        min_semester=3,
        hours_per_day=6,
        hours_per_week=30,
        modality="onsite",
        city="Maceió",
        published_at=NOW,
    )
    base.update(kw)
    return OfferFeatures(**base)


ANA = StudentFeatures(
    id=1,
    name="Ana",
    course="Ciência da Computação",
    semester=5,
    skills=["Python", "SQL", "FastAPI", "Docker"],
    summary="Desenvolvo APIs REST em Python com FastAPI e bancos SQL.",
    weekly_hours=30,
    modality="hybrid",
    city="Maceió",
)

BACKEND = offer(
    10,
    title="Estágio Backend Python",
    description="APIs REST com FastAPI, PostgreSQL e Docker.",
    requirements=["Python", "SQL", "Docker", "Git"],
    modality="hybrid",
)
FRONTEND = offer(
    11,
    title="Estágio Frontend",
    description="Interfaces com React, TypeScript e CSS.",
    requirements=["React", "TypeScript", "CSS"],
    modality="remote",
)
DATA = offer(
    12,
    title="Estágio em Dados",
    description="Pipelines de dados em Python e SQL, dashboards.",
    requirements=["Python", "SQL", "Pandas"],
)


def test_normalize_and_jaccard():
    assert normalize("  Análise  de Dados ") == "analise de dados"
    assert jaccard(["Python", "SQL"], ["python", "Git"]) == pytest.approx(1 / 3)
    assert jaccard([], ["x"]) == 0.0


def test_hard_filters_explain_each_elimination():
    student = StudentFeatures(id=1, course="Design", semester=2, weekly_hours=20)
    reasons = hard_filter_reasons(
        student, offer(1, status="closed", min_semester=4, hours_per_week=30, hours_per_day=7)
    )
    assert len(reasons) == 5
    assert any("Curso incompatível" in r for r in reasons)
    assert any("Período mínimo" in r for r in reasons)
    assert any("disponibilidade" in r for r in reasons)
    assert any("encerrada" in r for r in reasons)
    assert any("Lei 11.788" in r for r in reasons)
    assert hard_filter_reasons(ANA, BACKEND) == []


def test_hybrid_ranking_is_explainable_and_deterministic():
    offers = [FRONTEND, DATA, BACKEND, offer(13, course="Design")]
    first, filtered = recommend_for_student(ANA, offers, k=3, now=NOW)
    second, _ = recommend_for_student(ANA, offers, k=3, now=NOW)
    assert [r.item_id for r in first] == [r.item_id for r in second]
    assert first[0].item_id == 10  # backend matches 3 of 4 skills
    top = first[0]
    assert top.matched_skills == ["Python", "SQL", "Docker"]
    assert top.missing_skills == ["Git"]
    assert "3 de 4" in top.explanation and "Faltam: Git" in top.explanation
    assert 0 < top.score <= 1
    assert top.score > first[-1].score
    assert [r.item_id for r in filtered] == [13]
    assert "Curso incompatível" in filtered[0].explanation


def test_excluded_ids_and_k():
    ranked, _ = recommend_for_student(ANA, [BACKEND, DATA, FRONTEND], k=1, exclude_ids=[10])
    assert [r.item_id for r in ranked] == [12]


def test_cold_start_uses_recency_and_popularity():
    empty = StudentFeatures(id=2, course="Ciência da Computação", semester=5, weekly_hours=30)
    old_popular = offer(1, published_at=NOW - timedelta(days=60), popularity=10)
    new_unpopular = offer(2, published_at=NOW, popularity=0)
    new_popular = offer(3, published_at=NOW - timedelta(days=1), popularity=8)
    ranked, _ = recommend_for_student(empty, [old_popular, new_unpopular, new_popular], now=NOW)
    assert [r.item_id for r in ranked] == [3, 2, 1]
    assert all(r.strategy == "cold_start" for r in ranked)
    assert "Perfil ainda vazio" in ranked[0].explanation
    naive = cold_start([offer(4, published_at=datetime(2026, 11, 1))], now=NOW)
    assert naive[0].score > 0


def test_preference_score():
    pref, reasons = preference_score(ANA, BACKEND)
    assert pref == pytest.approx(1.0)
    assert len(reasons) == 2
    pref_remote, reasons_remote = preference_score(ANA, FRONTEND)
    assert pref_remote == pytest.approx(0.7)
    assert any("remota" in r for r in reasons_remote)
    nothing, _ = preference_score(StudentFeatures(id=9), offer(1, modality="onsite", city="Recife"))
    assert nothing == 0


def test_weights_normalisation():
    assert Weights(2, 1, 1).normalized().content == pytest.approx(0.5)
    with pytest.raises(ValueError):
        Weights(0, 0, 0).normalized()
    content_only, _ = recommend_for_student(
        ANA, [FRONTEND, DATA], weights=Weights(1, 0, 0), now=NOW
    )
    assert content_only[0].score == content_only[0].cosine


def test_content_scores_edge_cases():
    assert content_scores("", ["a"]) == [0.0]
    assert content_scores("python", []) == []
    assert content_scores("de da do", ["e o a"]) == [0.0]  # only stop words
    scores = content_scores("python fastapi", ["python fastapi apis", "react css"])
    assert scores[0] > scores[1]


def test_rank_candidates_keeps_ineligible_last():
    bob = StudentFeatures(
        id=2,
        name="Bob",
        course="Ciência da Computação",
        semester=6,
        skills=["Python", "Git"],
        weekly_hours=30,
    )
    carla = StudentFeatures(
        id=3, name="Carla", course="Design", semester=6, skills=["Python", "SQL", "Docker", "Git"]
    )
    ranked = rank_candidates(BACKEND, [carla, bob, ANA])
    assert [r.item_id for r in ranked] == [1, 2, 3]
    assert ranked[-1].eliminated_by and ranked[-1].score == 0
    assert "Atende 3 de 4" in ranked[0].explanation or ranked[0].reasons[0].startswith(
        "Atende 3 de 4"
    )
    assert "Não informa: Git" in " ".join(ranked[0].reasons)
