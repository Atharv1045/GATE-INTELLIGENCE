"""
Authoritative GATE Paper & Syllabus Taxonomy Loader.
Supports all 30 GATE disciplines with year-aware syllabus resolution and marking scheme lookup.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class GateTaxonomyLoader:
    """Loads and queries GATE paper registries, marking schemes, and year-versioned syllabi."""

    def __init__(self, exam_root: Optional[Path] = None) -> None:
        if exam_root is None:
            # Resolve relative to repository root
            candidate = Path(__file__).resolve().parent
            self.exam_root = candidate
        else:
            self.exam_root = Path(exam_root)

        self.papers_path = self.exam_root / "papers.json"
        self.syllabus_dir = self.exam_root / "syllabus"
        self.marking_dir = self.exam_root / "marking_schemes"
        self._papers_cache: Optional[Dict[str, Any]] = None
        self._syllabus_cache: Dict[str, Dict[str, Any]] = {}

    def load_papers_registry(self) -> Dict[str, Any]:
        if self._papers_cache is None:
            with open(self.papers_path, "r", encoding="utf-8") as f:
                self._papers_cache = json.load(f)
        return self._papers_cache

    def list_papers(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        registry = self.load_papers_registry()
        papers = registry.get("papers", [])
        if year is None:
            return papers
        filtered = []
        for p in papers:
            active_from = p.get("active_from") or 1984
            active_to = p.get("active_to")
            if year >= active_from and (active_to is None or year <= active_to):
                filtered.append(p)
        return filtered

    def get_paper_info(self, paper_code: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        code_upper = paper_code.strip().upper()
        for p in self.list_papers(year=year):
            if p["code"] == code_upper:
                return p
        return None

    def load_marking_scheme(self, scheme_id: str = "standard_gate") -> Dict[str, Any]:
        path = self.marking_dir / f"{scheme_id}.json"
        if not path.exists():
            path = self.marking_dir / "standard_gate.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_syllabus(self, paper_code: str, year: int = 2026) -> Dict[str, Any]:
        code_upper = paper_code.strip().upper()
        cache_key = f"{code_upper}:{year}"
        if cache_key in self._syllabus_cache:
            return self._syllabus_cache[cache_key]

        paper_dir = self.syllabus_dir / code_upper
        if paper_dir.exists():
            # Try exact year first, then latest available JSON in that discipline folder
            exact_file = paper_dir / f"{year}.json"
            if exact_file.exists():
                with open(exact_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._syllabus_cache[cache_key] = data
                    return data
            json_files = sorted(paper_dir.glob("*.json"), reverse=True)
            if json_files:
                with open(json_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._syllabus_cache[cache_key] = data
                    return data

        # Fallback dynamic structure for papers without a detailed local file yet
        paper_info = self.get_paper_info(code_upper) or {
            "code": code_upper,
            "name": f"GATE {code_upper}",
            "ga_marks": 15,
            "eng_math_marks": 13,
            "subject_marks": 72,
        }
        fallback = {
            "paper_code": code_upper,
            "paper_name": paper_info.get("name", f"GATE {code_upper}"),
            "syllabus_version": f"{year}.fallback",
            "valid_years": [year],
            "source_url": "https://gate2026.iitg.ac.in/exam-papers-and-syllabus.html",
            "subjects": [
                {
                    "code": "GA",
                    "name": "General Aptitude",
                    "weightage_estimate": 0.15,
                    "topics": [
                        {
                            "name": "Verbal, Quantitative & Analytical Aptitude",
                            "subtopics": ["Verbal Aptitude", "Quantitative Aptitude", "Analytical Aptitude", "Spatial Aptitude"],
                            "keywords": ["aptitude", "probability", "ratio", "grammar", "comprehension"]
                        }
                    ]
                },
                {
                    "code": f"{code_upper}-CORE",
                    "name": f"{paper_info.get('name', code_upper)} Core Syllabus",
                    "weightage_estimate": 0.85,
                    "topics": [
                        {
                            "name": "Core Discipline Topics",
                            "subtopics": ["Section 1: Mathematical Foundations", "Section 2: Core Engineering / Science Concepts"],
                            "keywords": [code_upper.lower()]
                        }
                    ]
                }
            ]
        }
        self._syllabus_cache[cache_key] = fallback
        return fallback

    def flatten_topics(self, paper_code: str, year: int = 2026) -> List[Dict[str, Any]]:
        """Returns flat list of {paper_code, subject_code, subject_name, topic_name, subtopics, keywords}."""
        syllabus = self.load_syllabus(paper_code, year)
        flat: List[Dict[str, Any]] = []
        for subj in syllabus.get("subjects", []):
            for topic in subj.get("topics", []):
                flat.append({
                    "paper_code": syllabus["paper_code"],
                    "syllabus_version": syllabus.get("syllabus_version", "2026.1"),
                    "subject_code": subj["code"],
                    "subject_name": subj["name"],
                    "weightage_estimate": subj.get("weightage_estimate", 0.1),
                    "topic_name": topic["name"],
                    "subtopics": topic.get("subtopics", []),
                    "keywords": topic.get("keywords", []),
                })
        return flat
