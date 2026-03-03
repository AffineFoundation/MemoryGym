# MemoryBench — Design Lessons

What didn't work, and why. Documenting these to prevent repeating mistakes.

## v1: Needle-in-Haystack Collapse

**Problem**: Classifier accuracy dropped from 100% to 36% only after switching to WikiText backgrounds. The original parameterized filler text was trivially distinguishable from fact-bearing sentences.

**Root cause**: 5 fixed templates with structured formatting (`Name: X, Salary: Y`) made needles 100% classifiable. An agent could skip reading documents entirely and just pattern-match for facts.

**Lesson**: If your "haystack" is stylistically different from your "needles", the task becomes needle detection, not memory management.

## v1: Small Entity Pool = Memorizable

**Problem**: With only 50 entities and fixed attribute sets, the total question-answer space was small enough to enumerate.

**Root cause**: `50 entities x 6 attributes x 10 question types = ~3,000 possible Q&A pairs`. A model could plausibly memorize all of them from evaluation data leakage.

**Lesson**: Fixed question pool + fixed answers = memorizable. Need either dynamic data, large combinatorial spaces, or both.

## v2: WikiText Perplexity Uncontrollable

**Problem**: WikiText-2 paragraphs had wildly varying complexity. Some were simple lists, others were dense academic text. This introduced uncontrolled difficulty variance unrelated to memory ability.

**Root cause**: Using real-world text as filler means you inherit its distribution. No filtering could fully normalize difficulty.

**Lesson**: Document difficulty should be controlled by the benchmark designer, not inherited from a corpus.

## v2: Fixed 6-Competency Matrix Too Rigid

**Problem**: The 6 competency categories (retrieval, update, conflict, abstention, cross-session, selective) created artificial boundaries. Some questions tested multiple competencies, others fit none cleanly.

**Root cause**: Trying to map continuous memory behavior onto discrete categories. The categories were designed top-down from theory rather than bottom-up from observed agent behavior.

**Lesson**: Score dimensions should measure observable outcomes (accuracy, efficiency, adaptability), not hypothetical cognitive categories.

## General: Phrasing Attacks

**Problem**: Models could distinguish question types from wording alone. Abstention questions used hedging language ("Do you happen to know...") while retrieval questions were direct ("What is X's salary?").

**Root cause**: Different question types had different linguistic signatures. An agent could learn "hedging = abstain" without reading any documents.

**Fix in v3**: Unified phrasing across all question types. Added "trick retrieval" questions that use abstention-like phrasing but have real answers.

## General: Read-Then-Answer is RAG, Not Memory

**Problem**: v1/v2's "read all documents, then answer all questions" format meant the task primarily tested retrieval quality — the same thing RAG benchmarks already measure.

**Root cause**: Separating the reading phase from the questioning phase removed the strategic decision-making element. The agent had no reason to be selective about what to store.

**Fix in v3**: Streaming architecture — each task simultaneously presents new information and asks questions. The agent must decide what to store *while also answering questions*, creating genuine resource management pressure.
