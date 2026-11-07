GEMINI_MODEL_BASES = frozenset({
    'gemini-2.0-flash',
    'gemini-2.5-flash-lite',
    'gemini-1.5-flash',
})


def rewrite_llm_fields(provider, model_names):
    """Повернути (provider, model_names) без Gemini."""
    cleaned = []
    for name in model_names or []:
        base = str(name).split(':', 1)[0].strip()
        if base not in GEMINI_MODEL_BASES:
            cleaned.append(name)
    if provider == 'gemini':
        provider = 'ollama'
    return provider or 'ollama', cleaned
