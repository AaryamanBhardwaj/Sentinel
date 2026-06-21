import { useState } from "react";

interface Props {
  onSubmit: (input: string) => void;
  isLoading: boolean;
}

const PLACEHOLDER = `Paste a stack trace, error log, or error message...

Example:
Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
    at com.example.DataProcessor.loadAll(DataProcessor.java:142)
    at com.example.Main.main(Main.java:28)`;

export function InputPanel({ onSubmit, isLoading }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (trimmed.length >= 10) {
      onSubmit(trimmed);
    }
  };

  return (
    <div className="input-panel">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={PLACEHOLDER}
        rows={10}
        disabled={isLoading}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            handleSubmit();
          }
        }}
      />
      <div className="input-actions">
        <span className="char-count">
          {input.length} / 10,000
        </span>
        <button
          onClick={handleSubmit}
          disabled={isLoading || input.trim().length < 10}
        >
          {isLoading ? "Analyzing..." : "Analyze"}
        </button>
      </div>
    </div>
  );
}
