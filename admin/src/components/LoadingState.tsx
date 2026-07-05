import './LoadingState.css';

type LoadingStateProps = {
  message?: string;
};

export function LoadingState({ message = 'Loading tickets…' }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="loading-state__spinner" aria-hidden="true" />
      <p className="loading-state__message">{message}</p>
    </div>
  );
}
