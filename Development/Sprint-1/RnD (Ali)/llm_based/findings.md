# LLM-Based Schema Mapping — Findings & Conclusion

I evaluated an LLM-based mapping approach where the model is prompted to map uploaded CSV headers to our canonical sales schema. The system returns a JSON mapping (canonical → CSV column) which the user then verifies via a simple UI.

## What I tested
- Prompting the LLM with canonical column names and the CSV header list.
- Parsing a variety of response formats and normalizing them into canonical→CSV mappings.
- Presenting the LLM's suggestions in a human-in-the-loop Streamlit interface for correction.

## Pros
- **Semantic flexibility:** LLMs can interpret abbreviations, multilingual labels, and unusual conventions without hand-coded rules.
- **Minimal maintenance:** No large alias lists to curate; the model generalizes to unseen variants.
- **Human-in-the-loop safety:** The UI allows users to review and correct mappings, preventing many automated errors from propagating downstream.
- **Fast iteration:** Prompt improvements can quickly address systematic mapping mistakes across datasets.

## Cons / Limitations
- **Occasional misses or hallucinations:** LLMs sometimes omit mappings or output unexpected shapes; robust parsing and UI safeguards are required.
- **Privacy tradeoff:** Sending column sample values (recommended to improve accuracy) would expose user data to the LLM provider. For sensitive datasets this may be unacceptable.
- **Non-determinism:** Model outputs can vary slightly between runs unless prompts and model parameters are tightly controlled.
- **Cost and availability:** LLM API usage incurs cost and depends on service availability; consider fallbacks for offline cases.
- **No hard guarantees:** An LLM cannot provide a formal correctness guarantee; human verification remains necessary.

## Practical improvement: include sample rows
Including a few sample values per column in the prompt substantially improves mapping accuracy (e.g., `GB`/`UK` signals country; `2025-01-05` signals a date field). However, that requires sending data samples to the LLM—introducing privacy and compliance concerns.

## Conclusion
LLM + human-in-the-loop is the **best approach so far**. It handles messy, multilingual, and terse column names much better than strict dictionaries or fuzzy-only methods. The human verification step mitigates many of the LLM's occasional errors.

However, it is not perfect for our production needs because:
- the LLM can still miss mappings,
- improved accuracy requires sending sample rows (privacy concern),
- occasional nondeterministic outputs complicate automation.

Final position: **adopt LLM-assisted mapping with human verification as the primary mapping strategy**, but augment it with strict local fallbacks and careful privacy controls (e.g., do not send raw sample values for sensitive datasets; instead use local heuristics or anonymized samples). This hybrid approach gives us the best balance of accuracy, auditability, and user safety.
