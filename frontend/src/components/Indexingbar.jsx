import '../styles/IndexingBar.css';

// Shows live backend progress steps while the repo is being uploaded & indexed
// steps: "cloning" -> "parsing" -> "embedding" -> "done" (or "failed")
export default function IndexingBar({ step, error, onReindex }) {
  const steps = ['Cloning', 'Parsing AST', 'Embedding', 'Ready'];
  const stepIds = ['cloning', 'parsing', 'embedding', 'done'];
  const current = stepIds.indexOf(step);
  const isFailed = step === 'failed';
  const isDone = step === 'done';

  const statusText = {
    cloning: 'Cloning repository from GitHub...',
    parsing: 'Parsing AST & extracting semantic chunks...',
    embedding: 'Generating MiniLM embeddings & storing in ChromaDB...',
    done: '✓ Repository indexed and ready',
    failed: error || 'Indexing failed. Try again.',
  };

  return (
    <div className={`indexing-bar ${isFailed ? 'failed' : ''}`}>
      {/* Spinner — shown while work is in progress */}
      {!isDone && !isFailed && <div className="indexing-spinner" />}

      {/* Status label */}
      <span className="indexing-text">{statusText[step] || 'Working...'}</span>

      {/* Step pills */}
      <div className="indexing-steps">
        {steps.map((label, i) => {
          let state = 'pending';
          if (isFailed) {
            state = 'pending';
          } else if (isDone || i < current) {
            state = 'done';
          } else if (i === current) {
            state = 'active';
          }
          return (
            <span key={label} className={`indexing-step ${state}`}>
              {state === 'done' ? '✓ ' : ''}
              {label}
            </span>
          );
        })}

        {(isDone || isFailed) && onReindex && (
          <button type="button" className="indexing-reindex-btn" onClick={onReindex}>
            {isFailed ? 'Retry Index' : 'Re-index'}
          </button>
        )}
      </div>
    </div>
  );
}
