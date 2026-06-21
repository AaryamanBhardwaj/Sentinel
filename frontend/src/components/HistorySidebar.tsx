import type { HistoryEntry } from "../hooks/useHistory";

interface Props {
  entries: HistoryEntry[];
  onSelect: (entry: HistoryEntry) => void;
  onClear: () => void;
}

export function HistorySidebar({ entries, onSelect, onClear }: Props) {
  if (entries.length === 0) {
    return (
      <aside className="history-sidebar">
        <h2>History</h2>
        <p className="history-empty">No analyses yet.</p>
      </aside>
    );
  }

  return (
    <aside className="history-sidebar">
      <div className="history-header">
        <h2>History</h2>
        <button className="clear-btn" onClick={onClear}>Clear</button>
      </div>
      <ul className="history-list">
        {entries.map((entry) => (
          <li key={entry.id} onClick={() => onSelect(entry)}>
            <div className="history-item">
              <span className="history-category">{entry.diagnosis.category}</span>
              <span className="history-confidence">{entry.diagnosis.confidence}</span>
            </div>
            <p className="history-preview">
              {entry.input.slice(0, 80)}
              {entry.input.length > 80 ? "..." : ""}
            </p>
            <time className="history-time">
              {new Date(entry.timestamp).toLocaleString()}
            </time>
          </li>
        ))}
      </ul>
    </aside>
  );
}
