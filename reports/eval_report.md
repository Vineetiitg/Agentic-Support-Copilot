# RAG Evaluation Report

Generated: 2026-10-24T04:14:45.337539+00:00

## Overall Metrics
- **Questions Evaluated:** 5
- **Source Hit Rate:** 1.0
- **Average Latency:** 12968.74 ms

### In-Domain RAG Metrics (Technical Documentation Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8996 |
| faithfulness | 0.8262 |
| context_precision | 0.6000 |
| context_recall | 1.0000 |
| answer_correctness | 0.6928 |

### Out-of-Domain Guardrail Accuracy
- **Guardrail Interceptions:** 0 / 0 (100.0%)

### Combined Aggregate (All 55 Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8996 |
| faithfulness | 0.8262 |
| context_precision | 0.6000 |
| context_recall | 1.0000 |
| answer_correctness | 0.6928 |

## Question Results

### Q: How do I reset my password?
**A:** To reset your password, click on the 'Forgot Password' link on the login page and follow the instructions sent to your email. [auth_guide.txt]
- Source hit: True
- Retrieved contexts: 3
- Latency ms: 14529.8
- **Per-Question Ragas Scores:**
  - answer_relevancy: 1.0000
  - faithfulness: 1.0000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 0.9850

### Q: cant login bro
**A:** I understand you're having trouble logging in. Here's what the documentation says:

You can reset your password by clicking on the 'Forgot Password' link on the login page and following the instructions sent to your email. [auth_guide.txt]

If you continue to experience issues, you can contact support by emailing support@example.com or calling 1-800-555-0199. [contact_info.html]
- Source hit: True
- Retrieved contexts: 5
- Latency ms: 21590.93
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.7754
  - faithfulness: 0.7143
  - context_precision: 0.5000
  - context_recall: 1.0000
  - answer_correctness: 0.3661

### Q: How do I upload MP4 videos?
**A:** The documentation specifies that the supported file formats for upload are PDF, DOCX, TXT, HTML, and Markdown. MP4 video uploads are not mentioned as a supported format. [api_docs.md]
- Source hit: True
- Retrieved contexts: 2
- Latency ms: 7043.0
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.7555
  - faithfulness: 1.0000
  - context_precision: 0.5000
  - context_recall: 1.0000
  - answer_correctness: 0.5282

### Q: Does the system use RabbitMQ for background tasks?
**A:** The system uses Redis-backed ARQ workers for async task processing, including ingestion and evaluation. RabbitMQ is not mentioned in the documentation for background tasks. [doc_id]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 8096.48
- **Per-Question Ragas Scores:**
  - answer_relevancy: 1.0000
  - faithfulness: 0.6667
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 0.5976

### Q: If I upload a file, what formats are supported and how does the system process it in the background?
**A:** The supported file formats for upload are PDF, DOCX, TXT, HTML, and Markdown [api_docs.md]. In the background, the system processes uploaded files using Redis-backed ARQ workers for asynchronous task processing, which includes ingestion and evaluation [redis_worker_architecture.md].
- Source hit: True
- Retrieved contexts: 2
- Latency ms: 13583.48
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.9670
  - faithfulness: 0.7500
  - context_precision: 0.0000
  - context_recall: 1.0000
  - answer_correctness: 0.9869
