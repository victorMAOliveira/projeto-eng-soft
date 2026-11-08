"""Deterministic SYNTHETIC dataset shared by the seed and the offline evaluation.

Every person, company and offer is fictitious (Faker pt_BR, fixed seed).
Each student and offer has a hidden *interest track* (e.g. backend, dados,
UX). Relevance labels come from that hidden track — not from the skills the
recommender sees — so the evaluation measures how well the observable,
noisy profile reveals the student's real interest:

* relevance 2 — same track and eligible (passes the hard filters);
* relevance 1 — adjacent track (e.g. backend ↔ devops) and eligible;
* relevance 0 — anything else.

Students list 3–6 skills of their track plus, half of the time, skills from
another track of the same course (noise); some summaries are generic.
"""

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from faker import Faker

SEED = 2026
REFERENCE_TIME = datetime(2026, 11, 1, 12, tzinfo=UTC)
DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "dataset.json"

TRACKS: dict[str, dict] = {
    "backend": {
        "course": "Ciência da Computação",
        "skills": [
            "Python",
            "Java",
            "SQL",
            "PostgreSQL",
            "APIs REST",
            "FastAPI",
            "Spring Boot",
            "Docker",
            "Git",
            "Testes automatizados",
        ],
        "titles": [
            "Estágio em Desenvolvimento Backend",
            "Estágio em APIs e Microsserviços",
            "Estágio em Engenharia de Software (Backend)",
        ],
        "focus": "desenvolvimento de APIs REST, integração com bancos de dados relacionais e testes automatizados",
        "interest": "desenvolvimento backend, APIs e arquitetura de software",
    },
    "dados": {
        "course": "Ciência da Computação",
        "skills": [
            "Python",
            "SQL",
            "Pandas",
            "Power BI",
            "Estatística",
            "Machine Learning",
            "ETL",
            "Visualização de dados",
            "Scikit-learn",
            "Excel",
        ],
        "titles": ["Estágio em Ciência de Dados", "Estágio em Análise de Dados", "Estágio em BI"],
        "focus": "análise exploratória, construção de dashboards e modelos preditivos com dados reais",
        "interest": "ciência de dados, estatística e aprendizado de máquina",
    },
    "devops": {
        "course": "Ciência da Computação",
        "skills": [
            "Linux",
            "Docker",
            "Kubernetes",
            "CI/CD",
            "AWS",
            "Redes",
            "Shell script",
            "Monitoramento",
            "Git",
            "Terraform",
        ],
        "titles": ["Estágio em DevOps", "Estágio em Infraestrutura e Cloud", "Estágio em SRE"],
        "focus": "automação de deploy, pipelines de CI/CD, containers e observabilidade em nuvem",
        "interest": "infraestrutura, cloud, automação e DevOps",
    },
    "frontend": {
        "course": "Sistemas de Informação",
        "skills": [
            "JavaScript",
            "TypeScript",
            "React",
            "HTML",
            "CSS",
            "Acessibilidade",
            "Figma",
            "Git",
            "Testes de interface",
            "Next.js",
        ],
        "titles": [
            "Estágio em Desenvolvimento Frontend",
            "Estágio em Desenvolvimento Web",
            "Estágio em Interfaces React",
        ],
        "focus": "construção de interfaces web responsivas e acessíveis com React e TypeScript",
        "interest": "desenvolvimento web frontend e experiência do usuário",
    },
    "mobile": {
        "course": "Sistemas de Informação",
        "skills": [
            "Kotlin",
            "Android",
            "Flutter",
            "Dart",
            "Swift",
            "React Native",
            "Firebase",
            "APIs REST",
            "Git",
            "UI mobile",
        ],
        "titles": [
            "Estágio em Desenvolvimento Mobile",
            "Estágio em Apps Android",
            "Estágio em Flutter",
        ],
        "focus": "desenvolvimento de aplicativos móveis nativos e multiplataforma",
        "interest": "aplicativos móveis Android, iOS e Flutter",
    },
    "embarcados": {
        "course": "Engenharia de Computação",
        "skills": [
            "C",
            "C++",
            "Arduino",
            "Microcontroladores",
            "Eletrônica",
            "IoT",
            "RTOS",
            "Python",
            "Sistemas digitais",
            "Linux embarcado",
        ],
        "titles": ["Estágio em Sistemas Embarcados", "Estágio em IoT", "Estágio em Firmware"],
        "focus": "firmware para microcontroladores, sensores e dispositivos de Internet das Coisas",
        "interest": "sistemas embarcados, eletrônica e IoT",
    },
    "financas": {
        "course": "Administração",
        "skills": [
            "Excel",
            "Contabilidade",
            "Finanças corporativas",
            "Análise de custos",
            "Power BI",
            "Orçamento",
            "Matemática financeira",
            "ERP",
            "Planejamento",
            "Inglês",
        ],
        "titles": ["Estágio em Finanças", "Estágio em Controladoria", "Estágio Financeiro"],
        "focus": "controle orçamentário, análise de custos e relatórios financeiros gerenciais",
        "interest": "finanças corporativas, controladoria e análise financeira",
    },
    "marketing": {
        "course": "Administração",
        "skills": [
            "Marketing digital",
            "Redes sociais",
            "Copywriting",
            "Google Analytics",
            "SEO",
            "Canva",
            "Comunicação",
            "Pesquisa de mercado",
            "CRM",
            "Inglês",
        ],
        "titles": [
            "Estágio em Marketing Digital",
            "Estágio em Comunicação e Marketing",
            "Estágio em Growth",
        ],
        "focus": "campanhas digitais, produção de conteúdo e análise de métricas de engajamento",
        "interest": "marketing digital, comunicação e comportamento do consumidor",
    },
    "obras": {
        "course": "Engenharia Civil",
        "skills": [
            "AutoCAD",
            "Revit",
            "BIM",
            "Orçamento de obras",
            "Topografia",
            "Concreto armado",
            "MS Project",
            "Normas técnicas",
            "Excel",
            "Segurança do trabalho",
        ],
        "titles": [
            "Estágio em Obras",
            "Estágio em Projetos BIM",
            "Estágio em Planejamento de Obras",
        ],
        "focus": "acompanhamento de obras, modelagem BIM e orçamentação",
        "interest": "construção civil, projetos estruturais e BIM",
    },
    "ux": {
        "course": "Design",
        "skills": [
            "Figma",
            "UX Research",
            "Prototipação",
            "Design de interação",
            "Usabilidade",
            "Design System",
            "Adobe XD",
            "Ilustração",
            "Acessibilidade",
            "Tipografia",
        ],
        "titles": [
            "Estágio em UX/UI Design",
            "Estágio em Product Design",
            "Estágio em Design Digital",
        ],
        "focus": "pesquisa com usuários, prototipação e evolução do design system",
        "interest": "design de interfaces, pesquisa com usuários e prototipação",
    },
}

ADJACENT = {
    frozenset(p)
    for p in (
        ("backend", "devops"),
        ("backend", "dados"),
        ("frontend", "mobile"),
        ("financas", "marketing"),
        ("frontend", "ux"),
    )
}
SOFT_SKILLS = ["Comunicação", "Trabalho em equipe", "Inglês", "Proatividade", "Organização"]
CITIES = ["Maceió"] * 7 + ["Arapiraca", "Rio Largo", "Recife"]


@dataclass
class SyntheticStudent:
    """A fictitious student; ``track`` is the hidden interest used for labels."""

    key: str
    name: str
    email: str
    track: str
    course: str
    semester: int
    skills: list[str]
    resume_summary: str
    weekly_availability_hours: int
    preferred_modality: str | None
    city: str
    is_pcd: bool = False


@dataclass
class SyntheticInternship:
    """A fictitious offer with its hidden ``track``."""

    key: str
    company_key: str
    track: str
    title: str
    description: str
    requirements: list[str]
    course: str
    min_semester: int
    hours_per_day: int
    hours_per_week: int
    modality: str
    city: str
    stipend: float
    published_at: str


@dataclass
class SyntheticCompany:
    """A fictitious host company."""

    key: str
    name: str
    email: str
    sector: str
    city: str
    description: str


@dataclass
class Dataset:
    """Everything the seed loads and the evaluation scores."""

    meta: dict
    companies: list[SyntheticCompany] = field(default_factory=list)
    internships: list[SyntheticInternship] = field(default_factory=list)
    students: list[SyntheticStudent] = field(default_factory=list)
    labels: list[dict] = field(default_factory=list)


def eligible(student: SyntheticStudent, offer: SyntheticInternship) -> bool:
    """Same hard filters as the recommender (course, period, availability)."""
    return (
        student.course == offer.course
        and student.semester >= offer.min_semester
        and offer.hours_per_week <= student.weekly_availability_hours
    )


def relevance(student: SyntheticStudent, offer: SyntheticInternship) -> int:
    """Graded ground truth from the hidden tracks (see module docstring)."""
    if not eligible(student, offer):
        return 0
    if student.track == offer.track:
        return 2
    return 1 if frozenset((student.track, offer.track)) in ADJACENT else 0


def generate(seed: int = SEED, n_students: int = 50, n_companies: int = 8) -> Dataset:
    """Build the dataset deterministically (same seed ⇒ same output)."""
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    fake.seed_instance(seed)
    track_names = list(TRACKS)

    sectors = [
        "Tecnologia",
        "Consultoria",
        "Indústria",
        "Varejo",
        "Construção",
        "Saúde",
        "Educação",
        "Finanças",
    ]
    companies = []
    for i in range(n_companies):
        name = f"{fake.last_name()} {rng.choice(['Tecnologia', 'Soluções', 'Engenharia', 'Consultoria', 'Digital'])} Ltda (fictícia)"
        companies.append(
            SyntheticCompany(
                key=f"c{i + 1}",
                name=name,
                email="rh@techsolucoes.test" if i == 0 else f"empresa{i + 1}@empresas.test",
                sector=sectors[i % len(sectors)],
                city="Maceió",
                description=f"Empresa fictícia do setor de {sectors[i % len(sectors)].lower()} criada para a demonstração.",
            )
        )

    internships = []
    for i in range(30):
        track = track_names[i % len(track_names)]
        spec = TRACKS[track]
        requirements = rng.sample(spec["skills"], rng.randint(3, 5))
        hours_per_day = rng.choice([4, 5, 6])
        published = REFERENCE_TIME - timedelta(days=rng.randint(0, 45), hours=rng.randint(0, 23))
        internships.append(
            SyntheticInternship(
                key=f"v{i + 1}",
                company_key=companies[i % n_companies].key,
                track=track,
                title=rng.choice(spec["titles"]),
                description=(
                    f"Atuar com {spec['focus']}. O(a) estagiário(a) terá mentoria semanal e "
                    f"participará de rituais ágeis. Desejável: {', '.join(requirements[:2])}."
                ),
                requirements=requirements,
                course=spec["course"],
                min_semester=rng.randint(2, 6),
                hours_per_day=hours_per_day,
                hours_per_week=hours_per_day * 5,
                modality=rng.choice(["onsite", "remote", "hybrid"]),
                city=rng.choice(CITIES),
                stipend=float(rng.choice([800, 1000, 1200, 1400, 1600, 1800])),
                published_at=published.isoformat(),
            )
        )

    students = []
    for i in range(n_students):
        track = track_names[i % len(track_names)]
        spec = TRACKS[track]
        skills = rng.sample(spec["skills"], rng.randint(3, 6))
        siblings = [t for t in track_names if t != track and TRACKS[t]["course"] == spec["course"]]
        if siblings and rng.random() < 0.5:
            skills += rng.sample(TRACKS[rng.choice(siblings)]["skills"], rng.randint(1, 2))
        if rng.random() < 0.6:
            skills.append(rng.choice(SOFT_SKILLS))
        skills = list(dict.fromkeys(skills))
        summary = (
            f"Estudante de {spec['course']} interessado(a) em {spec['interest']}."
            if rng.random() < 0.75
            else f"Estudante de {spec['course']} buscando a primeira experiência profissional."
        )
        name = fake.name()
        if i == 0:  # fixed, coherent profile for the live demo account
            email, name = "estudante@ufal.test", "Ana Beatriz Souza"
            skills = ["Python", "SQL", "FastAPI", "Docker", "Git", "APIs REST", "Inglês"]
            summary = (
                "Estudante de Ciência da Computação interessada em desenvolvimento backend, "
                "APIs e arquitetura de software; monitora de Programação 2."
            )
        else:
            email = f"estudante{i + 1:02d}@ufal.test"
        students.append(
            SyntheticStudent(
                key=f"s{i + 1}",
                name=name,
                email=email,
                track=track,
                course=spec["course"],
                semester=rng.randint(3, 9) if i else 6,
                skills=skills,
                resume_summary=summary,
                weekly_availability_hours=rng.choice([25, 30, 30]) if i else 30,
                preferred_modality=rng.choice(["onsite", "remote", "hybrid", None]),
                city=rng.choice(CITIES),
                is_pcd=(i % 17 == 5),
            )
        )

    labels = [
        {"student": s.key, "internship": v.key, "relevance": rel}
        for s in students
        for v in internships
        if (rel := relevance(s, v)) > 0
    ]
    meta = {
        "synthetic": True,
        "description": "Conjunto SINTÉTICO e fictício gerado por scripts/synthetic_data.py (Faker pt_BR).",
        "seed": seed,
        "reference_time": REFERENCE_TIME.isoformat(),
        "tracks": track_names,
        "label_rule": "2 = mesma trilha latente e elegível; 1 = trilha adjacente e elegível; 0 = demais",
    }
    return Dataset(meta, companies, internships, students, labels)


def to_json(dataset: Dataset) -> str:
    """Stable JSON (sorted keys) so regenerating does not change the file."""
    payload = {
        "meta": dataset.meta,
        "companies": [asdict(c) for c in dataset.companies],
        "internships": [asdict(v) for v in dataset.internships],
        "students": [asdict(s) for s in dataset.students],
        "labels": dataset.labels,
    }
    return json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load(path: Path = DATASET_PATH) -> Dataset:
    """Load the dataset written by the seed (or regenerate it if absent)."""
    if not path.exists():
        return generate()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Dataset(
        raw["meta"],
        [SyntheticCompany(**c) for c in raw["companies"]],
        [SyntheticInternship(**v) for v in raw["internships"]],
        [SyntheticStudent(**s) for s in raw["students"]],
        raw["labels"],
    )


def save(dataset: Dataset, path: Path = DATASET_PATH) -> Path:
    """Write the dataset JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(dataset), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(save(generate()))
