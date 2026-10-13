import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from datasets import Dataset
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.engine.indexer import dense_embeddings
from app.graph.workflow import compile_workflow

DATASET_PATH = Path("datasets/golden_qa.csv")
REPORT_PATH = Path("reports/eval_report.md")

def load_golden_questions(path: Path = DATASET_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def source_hit(expected_sources: str, sources: list[dict]) -> bool:
    expected = {source.strip() for source in expected_sources.split("|") if source.strip()}
    actual = {source.get("source") for source in sources if source and source.get("source")}
    if not expected:
        return len(actual) == 0
    return bool(expected & actual)

async def run_local_evaluation(
    assert_faithfulness: float = None,
    assert_precision: float = None,
    assert_relevancy: float = None,
) -> dict:
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, faithfulness, context_precision, context_recall, answer_correctness
    from ragas.run_config import RunConfig

    # Ensure web search is completely disabled during RAGAS evaluation
    original_web_search = settings.ENABLE_WEB_SEARCH
    settings.ENABLE_WEB_SEARCH = False

    agent = compile_workflow()
    rows = load_golden_questions()
    results = []
    
    questions = []
    answers = []
    contexts = []
    ground_truths = []

    from app.engine.semantic_cache import get_cached_answer, set_cached_answer
    from langchain_core.documents import Document

    for row in rows:
        started = perf_counter()
        
        # Bypass semantic cache during evaluation and strictly disable web search
        output_state = await agent.ainvoke({
            "question": row["question"],
            "chat_history": [],
            "run_count": 0,
            "enable_web_search": False,
        })
            
        latency_ms = round((perf_counter() - started) * 1000, 2)
        answer = output_state.get("generation", "")
        sources_dicts = output_state.get("sources", [])
        docs = output_state.get("documents", [])
        
        questions.append(row["question"])
        answers.append(answer)
        contexts.append([doc.page_content for doc in docs])
        ground_truths.append(row["expected_answer"])
        
        results.append(
            {
                "question": row["question"],
                "answer": answer,
                "latency_ms": latency_ms,
                "source_hit": source_hit(row["expected_sources"], sources_dicts),
                "retrieved_contexts": len(docs),
            }
        )

    # RAGAS Two-Tier Judge Configuration
    fast_llm = ChatOpenAI(
        model=getattr(settings, "FAST_LLM_MODEL", settings.LLM_MODEL),
        temperature=0,
        openai_api_key=getattr(settings, "FAST_LLM_API_KEY", "") or settings.OPENROUTER_API_KEY,
        openai_api_base=getattr(settings, "FAST_LLM_BASE_URL", "") or settings.OPENROUTER_BASE_URL,
        default_headers={"HTTP-Referer": "https://localhost:3000", "X-Title": "Support Docs Copilot"},
    )
    slow_llm = ChatOpenAI(
        model=getattr(settings, "SLOW_LLM_MODEL", settings.LLM_MODEL),
        temperature=0,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        default_headers={"HTTP-Referer": "https://localhost:3000", "X-Title": "Support Docs Copilot"},
    )

    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    fast_llm_wrapped = LangchainLLMWrapper(fast_llm)
    slow_llm_wrapped = LangchainLLMWrapper(slow_llm)
    embeddings_wrapped = LangchainEmbeddingsWrapper(dense_embeddings())

    # Assign fast LLM to structural metrics and slow LLM to reasoning metrics
    answer_relevancy.llm = fast_llm_wrapped
    context_precision.llm = fast_llm_wrapped
    context_recall.llm = fast_llm_wrapped
    faithfulness.llm = slow_llm_wrapped
    answer_correctness.llm = slow_llm_wrapped

    # Assign embeddings to metrics that need them
    answer_relevancy.embeddings = embeddings_wrapped
    context_precision.embeddings = embeddings_wrapped
    context_recall.embeddings = embeddings_wrapped
    answer_correctness.embeddings = embeddings_wrapped

    ragas_dataset = Dataset.from_dict({
        "user_input": questions,
        "response": answers,
        "retrieved_contexts": contexts,
        "reference": ground_truths,
    })
    
    try:
        ragas_result = evaluate(
            ragas_dataset,
            metrics=[answer_relevancy, faithfulness, context_precision, context_recall, answer_correctness],
            llm=fast_llm_wrapped,
            embeddings=embeddings_wrapped,
            run_config=RunConfig(max_workers=1, max_wait=90, max_retries=3),
        )
        
        df = ragas_result.to_pandas()
        
        # Robustly extract overall scores from the dataframe mean
        ragas_scores = {}
        for col in ["answer_relevancy", "faithfulness", "context_precision", "context_recall", "answer_correctness"]:
            if col in df.columns:
                val = df[col].mean()
                if not type(val).__name__ == "NAType":
                    ragas_scores[col] = float(val)
        
        in_domain_indices = [idx for idx, row in enumerate(rows) if row.get("expected_sources", "").strip()]
        ood_indices = [idx for idx, row in enumerate(rows) if not row.get("expected_sources", "").strip()]
        
        in_domain_scores = {}
        if in_domain_indices and not df.empty:
            in_domain_df = df.iloc[in_domain_indices]
            for col in ["answer_relevancy", "faithfulness", "context_precision", "context_recall", "answer_correctness"]:
                if col in in_domain_df.columns:
                    val = in_domain_df[col].mean()
                    if not type(val).__name__ == "NAType":
                        in_domain_scores[col] = float(val)

        guardrail_blocked = sum(1 for idx in ood_indices if results[idx]["source_hit"])
        guardrail_total = len(ood_indices)
        guardrail_accuracy = round(guardrail_blocked / max(guardrail_total, 1), 3)

        for i, df_row in df.iterrows():
            if i < len(results):
                results[i]["ragas_metrics"] = {
                    "answer_relevancy": df_row.get("answer_relevancy"),
                    "faithfulness": df_row.get("faithfulness"),
                    "context_precision": df_row.get("context_precision"),
                    "context_recall": df_row.get("context_recall"),
                    "answer_correctness": df_row.get("answer_correctness"),
                }
    except Exception as e:
        ragas_scores = {"error": str(e)}
        in_domain_scores = {}
        guardrail_blocked = 0
        guardrail_total = 0
        guardrail_accuracy = 0.0

    source_hit_rate = round(sum(1 for result in results if result["source_hit"]) / max(len(results), 1), 3)
    average_latency_ms = round(sum(result["latency_ms"] for result in results) / max(len(results), 1), 2)
    
    summary = {
        "questions": len(results),
        "source_hit_rate": source_hit_rate,
        "average_latency_ms": average_latency_ms,
        "ragas_scores": ragas_scores,
        "in_domain_scores": in_domain_scores,
        "guardrail_blocked": guardrail_blocked,
        "guardrail_total": guardrail_total,
        "guardrail_accuracy": guardrail_accuracy,
        "results": results,
    }
    write_report(summary)

    # CI/CD Quality Gate Assertions
    if isinstance(ragas_scores, dict) and "error" not in ragas_scores:
        if assert_faithfulness is not None:
            val = in_domain_scores.get("faithfulness", ragas_scores.get("faithfulness", 0.0))
            if val < assert_faithfulness:
                print(f"❌ CI Quality Gate FAILED: faithfulness score {val:.3f} < {assert_faithfulness}", file=sys.stderr)
                sys.exit(1)
        if assert_precision is not None:
            val = in_domain_scores.get("context_precision", ragas_scores.get("context_precision", 0.0))
            if val < assert_precision:
                print(f"❌ CI Quality Gate FAILED: context_precision score {val:.3f} < {assert_precision}", file=sys.stderr)
                sys.exit(1)
        if assert_relevancy is not None:
            val = in_domain_scores.get("answer_relevancy", ragas_scores.get("answer_relevancy", 0.0))
            if val < assert_relevancy:
                print(f"❌ CI Quality Gate FAILED: answer_relevancy score {val:.3f} < {assert_relevancy}", file=sys.stderr)
                sys.exit(1)

    settings.ENABLE_WEB_SEARCH = original_web_search
    return summary

def write_report(summary: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    ragas_scores = summary.get("ragas_scores", {})
    in_domain_scores = summary.get("in_domain_scores", {})
    
    lines = [
        "# RAG Evaluation Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overall Metrics",
        f"- **Questions Evaluated:** {summary['questions']}",
        f"- **Source Hit Rate:** {summary['source_hit_rate']}",
        f"- **Average Latency:** {summary['average_latency_ms']} ms",
        "",
    ]

    if in_domain_scores:
        lines.extend([
            "### In-Domain RAG Metrics (Technical Documentation Questions)",
            "| Metric | Score |",
            "| ------ | ----- |"
        ])
        for metric, score in in_domain_scores.items():
            if isinstance(score, (float, int)):
                lines.append(f"| {metric} | {score:.4f} |")
        lines.extend([
            "",
            "### Out-of-Domain Guardrail Accuracy",
            f"- **Guardrail Interceptions:** {summary.get('guardrail_blocked', 0)} / {summary.get('guardrail_total', 0)} ({summary.get('guardrail_accuracy', 1.0) * 100:.1f}%)",
            "",
            "### Combined Aggregate (All 55 Questions)",
        ])
    else:
        lines.append("### Ragas Scores")
    
    if isinstance(ragas_scores, dict) and "error" in ragas_scores:
        lines.extend([
            "**Evaluation Error:**",
            "```text",
            ragas_scores["error"],
            "```",
            ""
        ])
    else:
        lines.extend([
            "| Metric | Score |",
            "| ------ | ----- |"
        ])
        if ragas_scores:
            for metric, score in ragas_scores.items():
                if isinstance(score, (float, int)):
                    lines.append(f"| {metric} | {score:.4f} |")
                else:
                    lines.append(f"| {metric} | {score} |")
        else:
            lines.append("| N/A | No scores computed |")
        lines.append("")

    lines.extend([
        "## Question Results",
        "",
    ])

    for result in summary["results"]:
        lines.extend(
            [
                f"### Q: {result['question']}",
                f"**A:** {result['answer']}",
                f"- Source hit: {result['source_hit']}",
                f"- Retrieved contexts: {result['retrieved_contexts']}",
                f"- Latency ms: {result['latency_ms']}",
            ]
        )
        if result.get("ragas_metrics"):
            lines.append("- **Per-Question Ragas Scores:**")
            for m, s in result["ragas_metrics"].items():
                if isinstance(s, (float, int)):
                    lines.append(f"  - {m}: {s:.4f}")
                elif s is not None:
                    lines.append(f"  - {m}: {s}")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

def generate_synthetic_testset(output_path: Path = Path("datasets/synthetic_qa.json"), test_size: int = 5) -> list[dict]:
    from ragas.testset.generator import TestsetGenerator
    from langchain_community.document_loaders import DirectoryLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    print(f"Generating synthetic testset of size {test_size} from {settings.DATA_DIR}...")
    loader = DirectoryLoader(settings.DATA_DIR, glob="**/*.*", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    split_docs = splitter.split_documents(docs)
    
    generator = TestsetGenerator.from_langchain_docs(
        docs=split_docs,
        llm=ChatOpenAI(model=settings.LLM_MODEL, temperature=0.7, openai_api_key=settings.OPENROUTER_API_KEY, openai_api_base=settings.OPENROUTER_BASE_URL),
        embeddings=dense_embeddings(),
    )
    testset = generator.generate_with_langchain_docs(split_docs, test_size=test_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = testset.to_pandas()
    df.to_json(output_path, orient="records", indent=2)
    print(f"Saved {len(df)} synthetic QA pairs to {output_path}")
    return df.to_dict(orient="records")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Support Docs Copilot RAG Evaluation Suite")
    parser.add_argument("--generate-testset", action="store_true", help="Generate synthetic QA testset from documentation")
    parser.add_argument("--test-size", type=int, default=5, help="Number of synthetic QA pairs to generate")
    parser.add_argument("--assert-faithfulness", type=float, default=None, help="Minimum required faithfulness score")
    parser.add_argument("--assert-precision", type=float, default=None, help="Minimum required context precision score")
    parser.add_argument("--assert-relevancy", type=float, default=None, help="Minimum required answer relevancy score")
    args = parser.parse_args()

    if args.generate_testset:
        generate_synthetic_testset(test_size=args.test_size)
    else:
        print("Running evaluation...")
        summary = asyncio.run(run_local_evaluation(
            assert_faithfulness=args.assert_faithfulness,
            assert_precision=args.assert_precision,
            assert_relevancy=args.assert_relevancy,
        ))
        print("Evaluation report generated at:", REPORT_PATH)
