# Notes & Assumptions

## Decisions Made

1. **Slug generation:** Person IDs (slugs) are derived from the person's name. If no name is provided, the last path segment of the LinkedIn or Instagram URL is used. Duplicates get a numeric suffix.

2. **People template:** The `people.html` template handles both Pydantic model objects and plain dicts to support both live runs and loaded demo data.

3. **TF-IDF fallback:** If `sentence-transformers` is too heavy to install, the shortlister automatically falls back to TF-IDF with scikit-learn's `TfidfVectorizer`. No code change needed.

4. **LLM model IDs:** Using `openai/gpt-oss-120b` for analysis and `openai/gpt-oss-20b` for dates as specified. These should be verified in the Groq console before running.

5. **Date turn structure:** Turn 1 is always Agent A. Odd turns = A, even turns = B. On A's very first turn, a system prompt instructs them to open the date.

6. **Score clamping:** Final scores are clamped to [0, 100] per the formula in Section 10.

7. **Apify adapters:** Both LinkedIn and Instagram adapters try multiple possible field names in the raw actor output to be resilient to actor output format changes.

8. **SSE events:** The progress stream uses `sse-starlette` with a 30s keepalive ping to prevent timeouts.

9. **Pipeline runs sequentially for analysis** (one LLM call per person, to stay well within rate limits) but concurrently for dates (semaphore-controlled).
