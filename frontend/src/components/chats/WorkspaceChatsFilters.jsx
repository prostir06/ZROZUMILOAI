export default function WorkspaceChatsFilters({
  workspaceFilter,
  onWorkspaceFilterChange,
  workspaces,
  rangeFilter,
  onRangeFilterChange,
  channelFilter,
  onChannelFilterChange,
  handoffFilter,
  onHandoffFilterChange,
  feedbackFilter,
  onFeedbackFilterChange,
  shownCount,
  total,
}) {
  return (
    <div className="form__row" style={{ marginBottom: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
      <div className="form__group">
        <label htmlFor="filter_workspace">Робочий простір</label>
        <select
          id="filter_workspace"
          className="select"
          value={workspaceFilter}
          onChange={(e) => onWorkspaceFilterChange(e.target.value)}
        >
          <option value="">Всі робочі простори</option>
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
      </div>
      <div className="form__group">
        <label htmlFor="filter_range">Період</label>
        <select
          id="filter_range"
          className="select"
          value={rangeFilter}
          onChange={(e) => onRangeFilterChange(e.target.value)}
        >
          <option value="all">Весь час</option>
          <option value="today">Сьогодні</option>
          <option value="7d">Останні 7 днів</option>
          <option value="30d">Останні 30 днів</option>
        </select>
      </div>
      <div className="form__group">
        <label htmlFor="filter_channel">Джерело</label>
        <select
          id="filter_channel"
          className="select"
          value={channelFilter}
          onChange={(e) => onChannelFilterChange(e.target.value)}
        >
          <option value="all">Усі</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
          <option value="widget">Widget</option>
        </select>
      </div>
      <div className="form__group">
        <label htmlFor="filter_handoff">Handoff</label>
        <select
          id="filter_handoff"
          className="select"
          value={handoffFilter}
          onChange={(e) => onHandoffFilterChange(e.target.value)}
        >
          <option value="all">Усі</option>
          <option value="yes">Потрібен handoff</option>
          <option value="no">Без handoff</option>
        </select>
      </div>
      <div className="form__group">
        <label htmlFor="filter_feedback">Feedback</label>
        <select
          id="filter_feedback"
          className="select"
          value={feedbackFilter}
          onChange={(e) => onFeedbackFilterChange(e.target.value)}
        >
          <option value="all">Усі</option>
          <option value="up">👍</option>
          <option value="down">👎</option>
          <option value="">Без оцінки</option>
        </select>
      </div>
      <p className="auth-card__subtitle" style={{ alignSelf: 'end' }}>
        Показано {shownCount} з {total}
      </p>
    </div>
  );
}
