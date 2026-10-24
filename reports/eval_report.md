# RAG Evaluation Report

Generated: 2026-10-24T06:47:42.283650+00:00

## Overall Metrics
- **Questions Evaluated:** 5
- **Source Hit Rate:** 1.0
- **Average Latency:** 13270.41 ms

### In-Domain RAG Metrics (Technical Documentation Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8704 |
| faithfulness | 0.8000 |
| context_precision | 0.8000 |
| context_recall | 1.0000 |
| answer_correctness | 0.8531 |

### Out-of-Domain Guardrail Accuracy
- **Guardrail Interceptions:** 0 / 0 (100.0%)

### Combined Aggregate (All 55 Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8704 |
| faithfulness | 0.8000 |
| context_precision | 0.8000 |
| context_recall | 1.0000 |
| answer_correctness | 0.8531 |

## Question Results

### Q: How do I reset my password?
**A:** You can reset your password by clicking on the 'Forgot Password' link on the login page and following the instructions sent to your email. [doc_id: auth_guide.txt]
- Source hit: True
- Retrieved contexts: 2
- Latency ms: 14412.88
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.9935
  - faithfulness: 1.0000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 1.0000

### Q: cant login bro
**A:** Click the 'Forgot Password' link on the login page and follow the instructions sent to your email to reset your password. [doc_id: auth_guide.txt]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 18609.63
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.7073
  - faithfulness: 1.0000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 0.6076

### Q: How do I upload MP4 videos?
**A:** The system does not support MP4 video uploads. Supported formats are PDF, DOCX, TXT, HTML, and Markdown. [doc_id: api_docs.md]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 17271.49
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.8121
  - faithfulness: 0.5000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 1.0000

### Q: Does the system use RabbitMQ for background tasks?
**A:** No, the system uses Redis-backed ARQ workers for async task processing, not RabbitMQ. [doc_id: redis_worker_architecture.md]
- Source hit: True
- Retrieved contexts: 3
- Latency ms: 10102.5
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.9027
  - faithfulness: 0.5000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 1.0000

### Q: If I upload a file, what formats are supported and how does the system process it in the background?
**A:** The system supports PDF, DOCX, TXT, HTML, and Markdown file formats. [doc_id: api_docs.md] The /admin/upload endpoint accepts multiple files in a single request. [doc_id: rest_endpoints_guide.md] In the background, the system uses Redis-backed ARQ workers for async task processing including ingestion and evaluation. [doc_id: redis_worker_architecture.md]
- Source hit: True
- Retrieved contexts: 3
- Latency ms: 5955.56
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.9366
  - faithfulness: 1.0000
  - context_precision: 0.0000
  - context_recall: 1.0000
  - answer_correctness: 0.6577
