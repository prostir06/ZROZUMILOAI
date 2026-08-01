"""
Reciprocal Rank Fusion для hybrid RAG.

RRF об'єднує ранги з різних джерел (cosine vs Meili), не змішуючи сирі scores.
Оригінальний score зберігається окремо для порогів handoff / RAG_MIN_SCORE.
"""

# Стандартна константа RRF з літератури (Cormack et al.).
RRF_K = 60


def reciprocal_rank_fusion(result_lists, top_k, k=RRF_K):
    """
    Об'єднати кілька ранжованих списків через Reciprocal Rank Fusion.

    Ранжування — за rrf_score; поле score лишає оригінальний cosine/Meili
    (max при злитті), щоб RAG_MIN_SCORE / handoff не порівнювали з ~1/(k+rank).

    :param result_lists: iterable списків dict з ключами document_name, content, score
    :param top_k: максимальна кількість результатів на виході
    :param k: константа згладжування RRF
    :return: список dict з додатковими rrf_score / relevance_score
    """
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 0
    if top_k <= 0:
        return []

    try:
        k = float(k)
    except (TypeError, ValueError):
        k = float(RRF_K)
    if k <= 0:
        k = float(RRF_K)

    rrf_scores = {}
    relevance = {}
    payloads = {}

    for results in result_lists or []:
        if not results:
            continue
        for rank, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                continue
            key = (
                item.get('document_name', ''),
                (item.get('content') or '')[:120],
            )
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            try:
                original = float(item.get('score') or 0)
            except (TypeError, ValueError):
                original = 0.0
            relevance[key] = max(relevance.get(key, 0.0), original)
            if key not in payloads:
                payloads[key] = dict(item)

    merged = []
    for key, rrf_score in rrf_scores.items():
        entry = dict(payloads[key])
        entry['rrf_score'] = rrf_score
        entry['score'] = relevance[key]
        entry['relevance_score'] = relevance[key]
        merged.append(entry)

    merged.sort(key=lambda item: item.get('rrf_score', 0), reverse=True)
    return merged[:top_k]
