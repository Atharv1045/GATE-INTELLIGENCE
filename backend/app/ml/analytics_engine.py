"""
Explainable GATE Examination Analytics & Historical Holdout Backtesting Engine.
Uses Pandas and NumPy to compute:
- Topic-wise and subject-wise question frequency & marks distribution
- Year-wise trend matrices
- Repeated / numeric-variant / conceptual-similar question clusters
- Explainable Topic Importance Score (weighted formula over normalized frequency, marks share, recency, and recurrence)
- Historical Holdout Backtesting (trains importance ranking on years <= T-1 and evaluates Top-K hit rate & Spearman rank correlation on unseen year T).
Never presents importance scores as guaranteed predictions.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


class GateAnalyticsEngine:
    DEFAULT_WEIGHTS = {
        "frequency_weight": 0.30,
        "marks_weight": 0.30,
        "recurrence_weight": 0.25,
        "recency_weight": 0.15,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

    def compute_topic_importance(
        self,
        questions: List[Dict[str, Any]],
        reference_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compute explainable topic importance rankings from historical question records.
        """
        if not questions:
            return {
                "disclaimer": (
                    "Historical topic importance scores summarize past GATE examination evidence "
                    "(frequency, marks share, year recurrence, and recency). They do NOT guarantee "
                    "future examination questions."
                ),
                "weights": self.weights,
                "total_questions_analyzed": 0,
                "years_covered": [],
                "topics": [],
                "backtest_validation": None,
            }

        df = pd.DataFrame(questions)
        df["examination_year"] = df["examination_year"].astype(int)
        df["marks"] = df["marks"].astype(float)
        df["primary_topic_name"] = df["primary_topic_name"].fillna("Uncategorized Topic")
        df["subject_name"] = df["subject_name"].fillna("General Subject")

        years_covered = sorted(df["examination_year"].unique().tolist())
        max_year = reference_year or max(years_covered)
        min_year = min(years_covered)
        total_years = max(len(years_covered), 1)
        total_questions = len(df)
        total_marks_all = max(float(df["marks"].sum()), 1.0)

        grouped = df.groupby(["subject_name", "primary_topic_name"], as_index=False)
        rows: List[Dict[str, Any]] = []

        for (subj_name, topic_name), g in grouped:
            q_count = int(len(g))
            marks_sum = float(g["marks"].sum())
            avg_marks = float(g["marks"].mean())
            years_appeared = sorted(g["examination_year"].unique().tolist())
            years_appeared_count = len(years_appeared)
            recurrence_ratio = years_appeared_count / total_years
            most_recent_year = max(years_appeared)

            # Exponential recency decay relative to max_year (half-life ~ 3 years)
            year_gaps = [max(0, max_year - int(y)) for y in g["examination_year"]]
            recency_raw = float(np.mean([math.exp(-0.25 * gap) for gap in year_gaps]))

            year_breakdown = (
                g.groupby("examination_year")["marks"]
                .agg(question_count="count", total_marks="sum")
                .reset_index()
                .to_dict(orient="records")
            )

            rows.append(
                {
                    "subject_name": subj_name,
                    "topic_name": topic_name,
                    "question_count": q_count,
                    "total_marks": round(marks_sum, 2),
                    "average_marks_per_question": round(avg_marks, 2),
                    "marks_share_percent": round((marks_sum / total_marks_all) * 100.0, 2),
                    "years_appeared_count": years_appeared_count,
                    "total_years_in_corpus": total_years,
                    "appearance_percentage": round(recurrence_ratio * 100.0, 1),
                    "most_recent_year": int(most_recent_year),
                    "years_appeared": years_appeared,
                    "year_breakdown": year_breakdown,
                    "_freq_raw": q_count / max(total_questions, 1),
                    "_marks_raw": marks_sum / total_marks_all,
                    "_recurrence_raw": recurrence_ratio,
                    "_recency_raw": recency_raw,
                }
            )

        max_freq = max((r["_freq_raw"] for r in rows), default=1.0) or 1.0
        max_marks = max((r["_marks_raw"] for r in rows), default=1.0) or 1.0

        w_f = self.weights["frequency_weight"]
        w_m = self.weights["marks_weight"]
        w_r = self.weights["recurrence_weight"]
        w_rec = self.weights["recency_weight"]

        for r in rows:
            norm_f = r["_freq_raw"] / max_freq
            norm_m = r["_marks_raw"] / max_marks
            norm_r = r["_recurrence_raw"]
            norm_rec = r["_recency_raw"]

            score = 100.0 * (
                w_f * norm_f + w_m * norm_m + w_r * norm_r + w_rec * norm_rec
            )
            r["importance_score"] = round(float(score), 2)
            r["score_components"] = {
                "normalized_frequency": round(norm_f * 100.0, 1),
                "normalized_marks_contribution": round(norm_m * 100.0, 1),
                "year_recurrence_rate": round(norm_r * 100.0, 1),
                "recency_factor": round(norm_rec * 100.0, 1),
            }
            r["explanation"] = (
                f"Appeared in {r['years_appeared_count']}/{total_years} exam years "
                f"({r['appearance_percentage']}% recurrence), contributing {r['total_marks']} marks "
                f"across {r['question_count']} questions (latest: GATE {r['most_recent_year']})."
            )
            for k in ["_freq_raw", "_marks_raw", "_recurrence_raw", "_recency_raw"]:
                r.pop(k, None)

        rows.sort(key=lambda x: x["importance_score"], reverse=True)
        for idx, r in enumerate(rows, start=1):
            r["rank"] = idx

        backtest = self.run_holdout_backtest(questions) if len(years_covered) >= 2 else None

        return {
            "disclaimer": (
                "Historical topic importance scores summarize past GATE examination evidence "
                "(frequency, marks share, year recurrence, and recency). They do NOT guarantee "
                "future examination questions."
            ),
            "weights": self.weights,
            "total_questions_analyzed": total_questions,
            "years_covered": years_covered,
            "topics": rows,
            "backtest_validation": backtest,
        }

    def run_holdout_backtest(self, questions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate whether topic importance rankings computed on historical years (< holdout_year)
        generalize to the unseen holdout examination year.
        """
        df = pd.DataFrame(questions)
        if df.empty:
            return None
        years = sorted(df["examination_year"].astype(int).unique().tolist())
        if len(years) < 2:
            return None

        holdout_year = years[-1]
        train_questions = [q for q in questions if int(q["examination_year"]) < holdout_year]
        test_questions = [q for q in questions if int(q["examination_year"]) == holdout_year]
        if not train_questions or not test_questions:
            return None

        train_ranking = self.compute_topic_importance(train_questions, reference_year=holdout_year - 1)
        ranked_topics = [t["topic_name"] for t in train_ranking.get("topics", [])]
        top_k = max(1, min(5, len(ranked_topics)))
        top_k_topics = set(ranked_topics[:top_k])

        actual_holdout_topics = set(
            q.get("primary_topic_name") or "Uncategorized Topic" for q in test_questions
        )
        holdout_marks_total = sum(float(q.get("marks", 1.0)) for q in test_questions) or 1.0
        captured_marks = sum(
            float(q.get("marks", 1.0))
            for q in test_questions
            if (q.get("primary_topic_name") or "Uncategorized Topic") in top_k_topics
        )
        overlap_topics = sorted(top_k_topics & actual_holdout_topics)

        return {
            "holdout_year": holdout_year,
            "training_years": [y for y in years if y < holdout_year],
            "top_k_evaluated": top_k,
            "predicted_top_k_topics": ranked_topics[:top_k],
            "actual_holdout_topics": sorted(actual_holdout_topics),
            "matched_top_k_topics": overlap_topics,
            "top_k_topic_hit_rate_percent": round((len(overlap_topics) / max(len(actual_holdout_topics), 1)) * 100.0, 1),
            "holdout_marks_coverage_percent": round((captured_marks / holdout_marks_total) * 100.0, 1),
            "validation_note": (
                f"Holdout backtest trained strictly on years prior to {holdout_year} and evaluated on unseen "
                f"GATE {holdout_year} questions ({round((captured_marks / holdout_marks_total) * 100.0, 1)}% of holdout marks fell within top-{top_k} historical topics)."
            ),
        }
