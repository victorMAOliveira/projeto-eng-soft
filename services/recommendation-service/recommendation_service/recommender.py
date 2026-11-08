"""Hybrid, explainable and deterministic recommender (no LLM).

Pipeline for a student:

1. **Hard filters** — course, minimum period, weekly workload vs availability,
   open offer and legal workload (≤ 6 h/day, ≤ 30 h/week).
2. **Content score** — TF-IDF (unigrams + bigrams, accents stripped) of
   *skills + resume summary + course* against *requirements + title +
   description*, compared with cosine similarity.
3. **Attribute score** — Jaccard between required and declared skills.
4. **Preference score** — bonus for preferred modality and city.
5. **Final score** — ``w1·cos + w2·jaccard + w3·pref`` (weights configurable).
6. **Explanation** — skills in common, missing requirements and, for
   eliminated offers, which filter removed them.
7. **Cold start** — empty profile ⇒ ranking by recency and popularity.

The module is pure (no I/O) and reused by the offline evaluation script.
"""

import math
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_HOURS_PER_DAY = 6
MAX_HOURS_PER_WEEK = 30

PT_STOP_WORDS = sorted(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "entre",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "pela",
        "pelo",
        "por",
        "que",
        "se",
        "sem",
        "sobre",
        "um",
        "uma",
        "uns",
        "umas",
        "seu",
        "sua",
        "seus",
        "suas",
        "ser",
        "ter",
        "voce",
        "nosso",
        "nossa",
        "time",
        "equipe",
        "vaga",
        "estagio",
        "estagiario",
        "atividades",
        "experiencia",
        "conhecimento",
        "conhecimentos",
        "area",
        "empresa",
        "projetos",
        "projeto",
    }
)


@dataclass(frozen=True, slots=True)
class Weights:
    """Weights of the final score (documented defaults, configurable via env)."""

    content: float = 0.5
    attributes: float = 0.35
    preference: float = 0.15

    def normalized(self) -> "Weights":
        """Return weights scaled to sum 1 (keeps scores in 0..1)."""
        total = self.content + self.attributes + self.preference
        if total <= 0:
            raise ValueError("weights must sum to a positive value")
        return Weights(self.content / total, self.attributes / total, self.preference / total)


@dataclass(slots=True)
class StudentFeatures:
    """What the recommender knows about a student (read model)."""

    id: int
    name: str = ""
    course: str | None = None
    semester: int | None = None
    skills: list[str] = field(default_factory=list)
    summary: str = ""
    weekly_hours: int | None = None
    modality: str | None = None
    city: str | None = None


@dataclass(slots=True)
class OfferFeatures:
    """What the recommender knows about an internship offer (read model)."""

    id: int
    title: str
    description: str
    requirements: list[str]
    course: str
    min_semester: int
    hours_per_day: int
    hours_per_week: int
    modality: str
    city: str
    status: str = "open"
    company_name: str = ""
    stipend: float = 0.0
    published_at: datetime | None = None
    popularity: int = 0


@dataclass(slots=True)
class Recommendation:
    """One ranked item with the components of its score and its explanation."""

    item_id: int
    score: float
    cosine: float = 0.0
    jaccard: float = 0.0
    preference: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    eliminated_by: list[str] = field(default_factory=list)
    strategy: str = "hybrid"

    @property
    def explanation(self) -> str:
        """Human readable (pt-BR) justification."""
        return " ".join(self.eliminated_by or self.reasons)


def normalize(term: str) -> str:
    """Lower-case, strip accents and collapse spaces (``"Análise  de Dados"`` → ``"analise de dados"``)."""
    decomposed = unicodedata.normalize("NFKD", term)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.lower().split())


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard index of two skill sets (normalised terms)."""
    set_a, set_b = {normalize(x) for x in a if x}, {normalize(x) for x in b if x}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def is_cold_start(student: StudentFeatures) -> bool:
    """No skills and no summary: content-based scoring has nothing to work with."""
    return not student.skills and not (student.summary or "").strip()


def hard_filter_reasons(student: StudentFeatures, offer: OfferFeatures) -> list[str]:
    """Reasons that eliminate ``offer`` for ``student`` (empty list = eligible)."""
    reasons = []
    if offer.status != "open":
        reasons.append("A vaga está encerrada.")
    if student.course and normalize(student.course) != normalize(offer.course):
        reasons.append(f"Curso incompatível: a vaga é para {offer.course}.")
    if student.semester is not None and student.semester < offer.min_semester:
        reasons.append(f"Período mínimo {offer.min_semester}º (você está no {student.semester}º).")
    if student.weekly_hours is not None and offer.hours_per_week > student.weekly_hours:
        reasons.append(
            f"Carga de {offer.hours_per_week} h/semana acima da sua disponibilidade "
            f"({student.weekly_hours} h)."
        )
    if offer.hours_per_day > MAX_HOURS_PER_DAY or offer.hours_per_week > MAX_HOURS_PER_WEEK:
        reasons.append("Jornada acima do limite da Lei 11.788/2008.")
    return reasons


def student_document(student: StudentFeatures) -> str:
    """Text representing the student (skills weighted twice)."""
    skills = " ".join(student.skills)
    return f"{skills} {skills} {student.summary or ''} {student.course or ''}"


def offer_document(offer: OfferFeatures) -> str:
    """Text representing the offer (requirements weighted twice)."""
    requirements = " ".join(offer.requirements)
    return f"{requirements} {requirements} {offer.title} {offer.description}"


def content_scores(query: str, documents: Sequence[str]) -> list[float]:
    """Cosine similarity between ``query`` and each document in a shared TF-IDF space."""
    if not documents or not query.strip():
        return [0.0] * len(documents)
    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        stop_words=PT_STOP_WORDS,
    )
    try:
        matrix = vectorizer.fit_transform([query, *documents])
    except ValueError:  # empty vocabulary (only stop words)
        return [0.0] * len(documents)
    return [float(x) for x in cosine_similarity(matrix[0:1], matrix[1:]).ravel()]


def preference_score(student: StudentFeatures, offer: OfferFeatures) -> tuple[float, list[str]]:
    """Bonus (0..1) for preferred modality and city, with the matching reasons."""
    score, reasons = 0.0, []
    if student.modality:
        if student.modality == offer.modality:
            score += 0.6
            reasons.append("Modalidade compatível com sua preferência.")
        elif "hybrid" in (student.modality, offer.modality):
            score += 0.3
    if offer.modality == "remote":
        score += 0.4
        reasons.append("Vaga remota (sem deslocamento).")
    elif student.city and normalize(student.city) == normalize(offer.city):
        score += 0.4
        reasons.append(f"Na sua cidade ({offer.city}).")
    return min(score, 1.0), reasons


def _explain(rec: Recommendation, required: Sequence[str]) -> None:
    total = len(required)
    if rec.matched_skills:
        rec.reasons.insert(
            0,
            f"Você tem {len(rec.matched_skills)} de {total} habilidades exigidas "
            f"({', '.join(rec.matched_skills)}).",
        )
    else:
        rec.reasons.insert(0, f"Nenhuma das {total} habilidades exigidas aparece no seu perfil.")
    if rec.missing_skills:
        rec.reasons.insert(1, f"Faltam: {', '.join(rec.missing_skills)}.")
    if rec.cosine >= 0.15:
        rec.reasons.append(f"Seu perfil é {rec.cosine:.0%} similar ao texto da vaga (TF-IDF).")


def recommend_for_student(
    student: StudentFeatures,
    offers: Sequence[OfferFeatures],
    *,
    k: int = 10,
    weights: Weights = Weights(),
    exclude_ids: Iterable[int] = (),
    now: datetime | None = None,
) -> tuple[list[Recommendation], list[Recommendation]]:
    """Rank offers for ``student``.

    Returns ``(recommended, filtered)``: the top-``k`` eligible offers and the
    offers removed by hard filters (each with ``eliminated_by`` reasons).
    """
    excluded = set(exclude_ids)
    eligible, filtered = [], []
    for offer in offers:
        if offer.id in excluded:
            continue
        reasons = hard_filter_reasons(student, offer)
        if reasons:
            filtered.append(
                Recommendation(offer.id, 0.0, eliminated_by=reasons, strategy="filtered")
            )
        else:
            eligible.append(offer)

    if is_cold_start(student):
        return cold_start(eligible, k=k, now=now), filtered

    w = weights.normalized()
    cosines = content_scores(student_document(student), [offer_document(o) for o in eligible])
    student_skills = {normalize(s): s for s in student.skills}
    ranked = []
    for offer, cos in zip(eligible, cosines, strict=True):
        required = list(offer.requirements)
        matched = [r for r in required if normalize(r) in student_skills]
        missing = [r for r in required if normalize(r) not in student_skills]
        jac = jaccard(student.skills, required)
        pref, pref_reasons = preference_score(student, offer)
        score = w.content * cos + w.attributes * jac + w.preference * pref
        rec = Recommendation(
            offer.id,
            round(score, 4),
            cosine=round(cos, 4),
            jaccard=round(jac, 4),
            preference=round(pref, 4),
            matched_skills=matched,
            missing_skills=missing,
            reasons=pref_reasons,
        )
        _explain(rec, required)
        ranked.append(rec)
    # Deterministic: ties broken by offer id.
    ranked.sort(key=lambda r: (-r.score, r.item_id))
    return ranked[:k], filtered


def cold_start(
    offers: Sequence[OfferFeatures], *, k: int = 10, now: datetime | None = None
) -> list[Recommendation]:
    """Fallback without profile: 60% recency (half-life 14 days) + 40% popularity."""
    now = now or datetime.now(UTC)
    max_pop = max((o.popularity for o in offers), default=0) or 1
    ranked = []
    for offer in offers:
        published = offer.published_at or now
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        age_days = max((now - published).total_seconds() / 86400, 0.0)
        recency = math.exp(-math.log(2) * age_days / 14)
        popularity = offer.popularity / max_pop
        score = round(0.6 * recency + 0.4 * popularity, 4)
        ranked.append(
            Recommendation(
                offer.id,
                score,
                reasons=[
                    "Perfil ainda vazio: mostrando vagas recentes e populares "
                    f"({offer.popularity} candidatura(s)). Complete seu perfil para "
                    "recomendações personalizadas."
                ],
                strategy="cold_start",
            )
        )
    ranked.sort(key=lambda r: (-r.score, r.item_id))
    return ranked[:k]


def rank_candidates(
    offer: OfferFeatures,
    students: Sequence[StudentFeatures],
    *,
    k: int = 10,
    weights: Weights = Weights(),
) -> list[Recommendation]:
    """Rank students for an offer with the same scoring (``item_id`` = student id).

    Students failing a hard filter are kept at the end with their reasons, so
    the company sees why an applicant does not fit.
    """
    w = weights.normalized()
    cosines = content_scores(offer_document(offer), [student_document(s) for s in students])
    ranked = []
    for student, cos in zip(students, cosines, strict=True):
        skills = {normalize(s) for s in student.skills}
        matched = [r for r in offer.requirements if normalize(r) in skills]
        missing = [r for r in offer.requirements if normalize(r) not in skills]
        jac = jaccard(student.skills, offer.requirements)
        pref, _ = preference_score(student, offer)
        eliminated = [r for r in hard_filter_reasons(student, offer) if "encerrada" not in r]
        score = (
            0.0
            if eliminated
            else round(w.content * cos + w.attributes * jac + w.preference * pref, 4)
        )
        rec = Recommendation(
            student.id,
            score,
            cosine=round(cos, 4),
            jaccard=round(jac, 4),
            preference=round(pref, 4),
            matched_skills=matched,
            missing_skills=missing,
            eliminated_by=eliminated,
        )
        rec.reasons = [
            f"Atende {len(matched)} de {len(offer.requirements)} requisitos"
            + (f" ({', '.join(matched)})." if matched else "."),
        ]
        if missing:
            rec.reasons.append(f"Não informa: {', '.join(missing)}.")
        if cos >= 0.15:
            rec.reasons.append(f"Perfil {cos:.0%} similar à descrição da vaga.")
        ranked.append(rec)
    ranked.sort(key=lambda r: (bool(r.eliminated_by), -r.score, r.item_id))
    return ranked[:k]
