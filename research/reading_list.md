# Research Reading List

Last updated: 2026-03-05

## Project framing

- [Problem Definition](/Users/delmedigo/Dev/ppi/research/notes/problem_definition.md)

## Priority themes for literature search

- Document information extraction for financial reports
- OCR-free document understanding models
- Table structure recognition and cell-level parsing
- Layout-aware multimodal encoders
- Constrained decoding for strict JSON/schema outputs
- Hallucination reduction and faithfulness in VLM extraction
- Confidence calibration and abstention for extraction systems
- Evaluation protocols for document extraction and structured generation

## Search keywords (starter set)

- "financial statement document information extraction"
- "OCR-free document understanding table extraction"
- "layout-aware vision language model document parsing"
- "schema-constrained decoding JSON generation"
- "document extraction calibration abstention"
- "multimodal key information extraction benchmark"

## Paper note format

For each paper, add a file under `research/papers/` using:

- [Paper Template](/Users/delmedigo/Dev/ppi/research/papers/TEMPLATE.md)

## Candidate benchmark families to prioritize

- Document VQA-style benchmarks (for grounded field extraction)
- KIE benchmarks (for key-value extraction under layout variation)
- Table extraction benchmarks (for structure + cell content)
- Financial-report-specific datasets/benchmarks when available

## Open research questions

- Which architecture gives best quality/cost on multi-page statements: OCR-based, OCR-free, or hybrid?
- How much does constrained decoding improve validity without harming recall?
- What is the best representation for evidence attribution per JSON field?
- Which evaluation metric best predicts downstream analyst trust?
