# RAG Evaluation Report

Generated: 2026-10-24T05:26:32.805785+00:00

## Overall Metrics
- **Questions Evaluated:** 5
- **Source Hit Rate:** 1.0
- **Average Latency:** 12179.81 ms

### In-Domain RAG Metrics (Technical Documentation Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8444 |
| faithfulness | 0.8000 |
| context_precision | 0.8000 |
| context_recall | 1.0000 |
| answer_correctness | 0.8859 |

### Out-of-Domain Guardrail Accuracy
- **Guardrail Interceptions:** 0 / 0 (100.0%)

### Combined Aggregate (All 55 Questions)
| Metric | Score |
| ------ | ----- |
| answer_relevancy | 0.8444 |
| faithfulness | 0.8000 |
| context_precision | 0.8000 |
| context_recall | 1.0000 |
| answer_correctness | 0.8859 |

## Question Results

### Q: How do I reset my password?
**A:** To reset your password, click the 'Forgot Password' link on the login page and follow the instructions sent to your email. [auth_guide.txt]
- Source hit: True
- Retrieved contexts: 3
- Latency ms: 14730.31
- **Per-Question Ragas Scores:**
  - answer_relevancy: 1.0000
  - faithfulness: 1.0000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 0.9959

### Q: cant login bro
**A:** To reset your password, click the 'Forgot Password' link on the login page and follow the instructions sent to your email. [auth_guide.txt]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 19119.0
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.7010
  - faithfulness: 1.0000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 0.6080

### Q: How do I upload MP4 videos?
**A:** The system does not support MP4 video uploads. Supported formats are PDF, DOCX, TXT, HTML, and Markdown. [api_docs.md]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 9303.94
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.8121
  - faithfulness: 0.5000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 1.0000

### Q: Does the system use RabbitMQ for background tasks?
**A:** No, the system uses Redis-backed ARQ workers for async task processing, not RabbitMQ. [redis_worker_architecture.md]
- Source hit: True
- Retrieved contexts: 1
- Latency ms: 10947.75
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.9027
  - faithfulness: 0.5000
  - context_precision: 1.0000
  - context_recall: 1.0000
  - answer_correctness: 1.0000

### Q: If I upload a file, what formats are supported and how does the system process it in the background?
**A:** The system supports PDF, DOCX, TXT, HTML, and Markdown file formats. [api_docs.md] In the background, the system uses Redis-backed ARQ workers for async task processing, including ingestion and evaluation. [redis_worker_architecture.md]
- Source hit: True
- Retrieved contexts: 2
- Latency ms: 6798.04
- **Per-Question Ragas Scores:**
  - answer_relevancy: 0.8060
  - faithfulness: 1.0000
  - context_precision: 0.0000
  - context_recall: 1.0000
  - answer_correctness: 0.8256
