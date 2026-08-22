"""Curated Italian catalog metadata for public demos."""

# ruff: noqa: E501

from __future__ import annotations

CATALOG_IT: dict[str, dict[str, str]] = {
    "multi-hop-research": {
        "title": "Ricerca istituzionale UE multi-hop",
        "summary": "Dipendenza semantica tra attività di identificazione e di ricerca normativa.",
        "why_interesting": "Mostra il DAG del planner con archi depends_on.",
        "goal": (
            "Identifica chi ricopre attualmente la carica di Presidente della Commissione europea, "
            "quindi determina su quali obblighi concreti relativi ai modelli di IA per finalità generali "
            "la Commissione europea ha pubblicato linee guida destinate ai fornitori per il 2026. "
            "La seconda attività deve dipendere dalla corretta identificazione del titolare della carica "
            "nella prima attività. Utilizza esclusivamente fonti istituzionali ufficiali dell'UE."
        ),
    },
    "rag-architecture-2026": {
        "title": "Hybrid RAG vs GraphRAG vs long-context (2026)",
        "summary": "Compromessi architetturali per assistenti di conoscenza in produzione.",
        "why_interesting": "Sintesi tecnica da documentazione primaria e paper.",
        "goal": (
            "Confronta architetture Hybrid RAG, GraphRAG e long-context per un assistente di conoscenza "
            "in produzione nel 2026. Valuta qualità del retrieval, provenienza, costo di aggiornamento, "
            "complessità operativa, latenza, sicurezza, strategia di valutazione e i carichi di lavoro "
            "per cui ciascuna architettura è più adatta. Preferisci paper originali e documentazione "
            "ufficiale di framework o vendor."
        ),
    },
    "ev-battery-evidence": {
        "title": "Evidenze LFP vs NMC per veicoli passeggeri",
        "summary": "Confronto basato su evidenze tra chimiche di batteria.",
        "why_interesting": "Fonti scientifiche con provenienza e citazioni.",
        "goal": (
            "Confronta le evidenze attuali sulle chimiche LFP e NMC ad alto contenuto di nichel per veicoli "
            "passeggeri elettrici, concentrandoti su ciclo di vita, densità energetica, sicurezza termica, "
            "driver di costo e su come l'ingegneria a livello di pacco modifichi il compromesso pratico. "
            "Preferisci lavori peer-reviewed, report DOE o di laboratori nazionali e dati ingegneristici "
            "credibili dei produttori."
        ),
    },
    "eu-ai-act-gpai-2026": {
        "title": "Obblighi GPAI del EU AI Act (2026)",
        "summary": "Sintesi normativa da fonti ufficiali UE.",
        "why_interesting": "Ricerca istituzionale attuale con provenienza.",
        "goal": (
            "Spiega gli obblighi che il Regolamento UE sull'IA impone nel 2026 ai fornitori di modelli di "
            "IA per finalità generali, distinguendo gli obblighi già applicabili da quelli successivi, "
            "e individua le fonti autorevoli della Commissione o dell'UE a supporto di ogni conclusione. "
            "Dai priorità a EUR-Lex, Commissione europea e pubblicazioni dell'EU AI Office."
        ),
    },
    "ev-lifecycle-evidence": {
        "title": "Evidenze sul ciclo di vita GHG dei veicoli elettrici",
        "summary": "Differenze metodologiche tra studi di ciclo di vita autorevoli.",
        "why_interesting": "Incertezza e contraddizione senza conclusioni forzate.",
        "goal": (
            "Confronta stime credibili dell'impatto sul ciclo di vita dei gas serra di veicoli elettrici "
            "a batteria rispetto a veicoli a combustione comparabili in Europa, e spiega perché studi "
            "autorevoli producono stime di break-even diverse. Preferisci ICCT, IEA, ricerca peer-reviewed "
            "e fonti istituzionali europee."
        ),
    },
}
