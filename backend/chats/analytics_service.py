"""Workspace analytics aggregation service."""
from datetime import timedelta
from typing import Any, Dict

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from chats.models import WorkspaceChatLog


def get_workspace_analytics(
    workspace,
    date_range: str = '30d',
) -> Dict[str, Any]:
    """
    Compute educational KPIs and knowledge gaps for a given workspace.

    Args:
        workspace: Workspace instance to aggregate analytics for.
        date_range: 'today', '7d', '30d', or 'all'. Defaults to '30d'.

    Returns:
        Dictionary with KPIs, knowledge gaps list, and timeline data.
    """
    now = timezone.now()
    qs = WorkspaceChatLog.objects.filter(workspace=workspace)

    if date_range == 'today':
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(created_at__gte=start_of_day)
    elif date_range == '7d':
        qs = qs.filter(created_at__gte=now - timedelta(days=7))
    elif date_range == '30d':
        qs = qs.filter(created_at__gte=now - timedelta(days=30))
    elif date_range == 'all':
        pass
    else:
        # Default fallback to 30d if unknown
        qs = qs.filter(created_at__gte=now - timedelta(days=30))

    total_queries = qs.count()
    unique_users = qs.values('sent_by').distinct().count()
    handoff_count = qs.filter(needs_handoff=True).count()
    handoff_rate = (
        round(handoff_count / total_queries * 100, 1)
        if total_queries > 0
        else 0.0
    )

    feedback_up = qs.filter(feedback='up').count()
    feedback_down = qs.filter(feedback='down').count()
    rated_count = feedback_up + feedback_down
    csat_score = (
        round(feedback_up / rated_count * 100, 1)
        if rated_count > 0
        else 0.0
    )

    gaps_qs = qs.filter(
        Q(needs_handoff=True) | Q(feedback='down')
    ).order_by('-created_at')[:50]

    knowledge_gaps = [
        {
            'id': log.id,
            'created_at': log.created_at.isoformat() if log.created_at else '',
            'prompt': log.prompt,
            'response_snippet': (log.response or '')[:160],
            'needs_handoff': log.needs_handoff,
            'feedback': log.feedback,
            'reason': (
                'low_confidence'
                if log.needs_handoff
                else 'negative_feedback'
            ),
        }
        for log in gaps_qs
    ]

    timeline_qs = (
        qs.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(
            total_queries=Count('id'),
            handoffs=Count('id', filter=Q(needs_handoff=True)),
        )
        .order_by('date')
    )

    timeline = [
        {
            'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
            'total_queries': item['total_queries'],
            'handoffs': item['handoffs'],
        }
        for item in timeline_qs
    ]

    return {
        'range': date_range,
        'total_queries': total_queries,
        'unique_users': unique_users,
        'handoff_count': handoff_count,
        'handoff_rate': handoff_rate,
        'feedback_up': feedback_up,
        'feedback_down': feedback_down,
        'csat_score': csat_score,
        'knowledge_gaps': knowledge_gaps,
        'timeline': timeline,
    }
