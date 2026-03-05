# Problem Definition: Financial-Statement Document to Strict JSON

Date: 2026-03-05

## 1) Core problem statement

We are solving **document-to-structured-data extraction** for financial statements.
Input is one or more document images (or PDF pages rendered to images), and output is a **schema-valid JSON object** with fields required by downstream systems.

This is not just OCR. It is a joint problem of:

- reading text,
- interpreting layout and table structure,
- linking values to semantic keys,
- and producing constraint-satisfying structured output.

## 2) Widely accepted terms for this task

Use these as canonical terms in experiments, notes, and model cards:

- **Document AI** / **Intelligent Document Processing (IDP)**
- **Document Information Extraction (DocIE)**
- **Key Information Extraction (KIE)** for semi-structured documents
- **Table Structure Recognition (TSR)** and **Table Information Extraction**
- **Visual Document Understanding (VDU)**
- **OCR-based** vs **OCR-free** document understanding
- **Schema-constrained generation** / **Constrained decoding**
- **Structured prediction** on multimodal inputs
- **Financial statement parsing** (domain-specific subtask)

## 3) Formal task definition

Given:

- document pages `D = {p_1, ..., p_n}`,
- target JSON schema `S`,
- optional metadata `M` (language, report type, period, issuer),

learn model/system `f` such that:

- `y_hat = f(D, M)`,
- `y_hat` is valid under schema `S`,
- extracted values are faithful to source evidence,
- uncertainty or missingness is explicit (not silently hallucinated).

## 4) Operational scope

In scope:

- balance sheet, income statement, cash-flow statement, notes/tables,
- multi-page reasoning,
- numeric normalization (thousands separators, signs, currency),
- unit handling (thousands/millions, basis points, percentages),
- strict schema compliance and deterministic post-validation.

Out of scope for v1 (unless requested):

- full narrative MD&A understanding,
- forecasting/prediction,
- accounting judgment beyond explicit evidence in document.

## 5) Success criteria (engineering + scientific)

- **Field-level extraction quality**: exact match, numeric tolerance metrics.
- **Record-level quality**: all required fields correct in one statement.
- **Schema validity rate**: percent outputs passing JSON schema without repair.
- **Evidence faithfulness**: extracted values traceable to page spans/cells.
- **Calibration**: confidence correlates with correctness for human review routing.
- **Robustness**: performance across templates, scans, languages, and low-quality pages.

## 6) Suggested reframings (creative but practical)

### Framing A: "Two-stage perception + constrained reasoning"

View system as:

- stage 1: perception graph (text blocks, table cells, layout edges),
- stage 2: constrained semantic mapping into schema.

Why useful:

- easier error attribution,
- supports hybrid OCR + VLM systems,
- cleanly inserts rule-based accounting checks.

### Framing B: "Program synthesis over document evidence"

Treat each field as a latent program:

- select region,
- parse value,
- normalize unit/sign,
- map to schema key.

Why useful:

- compositional generalization across statement templates,
- reusable extraction "programs" per field family.

### Framing C: "Retrieval-augmented structured generation"

Do not let generator read all pixels/tokens at once. Instead:

- retrieve top evidence regions/cells,
- generate JSON from retrieved evidence only.

Why useful:

- lower hallucination risk,
- better long-document scalability,
- direct evidence links for auditability.

### Framing D: "Risk-sensitive extraction pipeline"

Optimize expected business loss, not only F1:

- high-importance fields (revenue, net income, EPS) weighted more,
- abstain/escalate when uncertainty high.

Why useful:

- aligns model optimization with financial operations risk.

## 7) Recommended project problem statement (concise)

"Build a robust multimodal structured extraction system that converts financial-statement document images into schema-valid JSON with auditable evidence links, high numeric fidelity, and calibrated uncertainty."

## 8) Immediate implications for next experiments

- Track schema-validity as first-class metric, not post-hoc.
- Separate extraction errors into perception, alignment, normalization, and schema-mapping buckets.
- Add evidence pointers per output field (`page`, `bbox`/cell id, text span).
- Implement abstention for uncertain mandatory fields instead of forced guesses.
