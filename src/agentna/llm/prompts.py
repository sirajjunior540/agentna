"""Prompt templates for LLM interactions."""

SYSTEM_PROMPT = """You are an expert code analyst. Your job is to understand codebases deeply and explain them clearly.

Key principles:
- CODE IS THE SOURCE OF TRUTH. Documentation may be outdated.
- Follow the code flow: trace imports, function calls, class hierarchies
- Be specific: include file paths and line numbers
- Use structured output: tables, bullet points, clear sections
- If you see multiple implementations, explain the primary one first
- Distinguish between: models, services, views/controllers, utilities"""

EXPLAIN_CHANGES_PROMPT = """Analyze the following code changes and provide a clear explanation.

## Changed Files
{changed_files}

## Change Details
{change_details}

## Affected Code
{affected_code}

Please provide:
1. A brief summary of what changed (1-2 sentences)
2. The purpose/intent of the changes
3. Any potential impacts on other parts of the codebase
4. Any concerns or recommendations

Keep your response concise and focused on the most important aspects."""

IMPACT_ANALYSIS_PROMPT = """Analyze the potential impact of changes to the following files/symbols.

## Changed Items
{changed_items}

## Dependency Information
{dependencies}

## Related Code
{related_code}

Please provide:
1. Summary of the change scope
2. List of directly affected components
3. List of potentially affected downstream components
4. Risk assessment (low/medium/high) with reasoning
5. Recommendations for testing or review focus areas

Be specific about which files and functions might be affected."""

ASK_CODEBASE_PROMPT = """Answer based ONLY on the code provided below.

Question: {question}

## Code Context
{context}

## Symbols
{symbols}

## Relationships
{relationships}

---

Provide a clear answer with:

1. **Summary** (2-3 sentences explaining how it works)

2. **Main Files**
   - List the key files with their purpose

3. **How It Works**
   - Step by step explanation
   - Include function names and file:line references
   - Mention important business rules

4. **Example Flow** (if applicable)
   - Show a typical execution path

Be specific. Use the actual code shown above. If info is missing, say so."""

SUMMARIZE_FILE_PROMPT = """Summarize the following code file.

## File: {file_path}

## Content
{content}

## Symbols Defined
{symbols}

## Relationships
{relationships}

Provide:
1. A brief description of the file's purpose (1-2 sentences)
2. Main components/classes/functions defined
3. Key dependencies and what they're used for
4. Notable patterns or architectural decisions

Keep the summary concise but informative."""

DETECT_PATTERNS_PROMPT = """Analyze the following code samples and identify patterns and conventions.

## Code Samples
{code_samples}

Identify:
1. Naming conventions used
2. Code organization patterns
3. Common patterns (decorators, factories, etc.)
4. Error handling approaches
5. Documentation style

For each pattern, provide:
- Description of the pattern
- Example from the code
- Confidence level (high/medium/low)"""

REVIEW_CHANGES_PROMPT = """Review the following code changes and provide feedback.

## Changed Files
{changed_files}

## Diff
{diff}

## Related Context
{context}

Provide:
1. Summary of the changes
2. Potential issues or bugs
3. Code quality observations
4. Suggestions for improvement
5. Questions for the author

Be constructive and specific in your feedback."""


def format_explain_changes(
    changed_files: list[str],
    change_details: str,
    affected_code: str,
) -> str:
    """Format the explain changes prompt."""
    return EXPLAIN_CHANGES_PROMPT.format(
        changed_files="\n".join(f"- {f}" for f in changed_files),
        change_details=change_details,
        affected_code=affected_code,
    )


def format_impact_analysis(
    changed_items: list[str],
    dependencies: str,
    related_code: str,
) -> str:
    """Format the impact analysis prompt."""
    return IMPACT_ANALYSIS_PROMPT.format(
        changed_items="\n".join(f"- {item}" for item in changed_items),
        dependencies=dependencies,
        related_code=related_code,
    )


def format_ask_codebase(
    question: str,
    context: str,
    symbols: str,
    relationships: str,
) -> str:
    """Format the ask codebase prompt."""
    return ASK_CODEBASE_PROMPT.format(
        question=question,
        context=context,
        symbols=symbols,
        relationships=relationships,
    )


def format_summarize_file(
    file_path: str,
    content: str,
    symbols: list[str],
    relationships: str,
) -> str:
    """Format the summarize file prompt."""
    return SUMMARIZE_FILE_PROMPT.format(
        file_path=file_path,
        content=content[:3000],  # Limit content size
        symbols="\n".join(f"- {s}" for s in symbols),
        relationships=relationships,
    )
