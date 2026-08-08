type BrandMarkProps = {
  className?: string;
  size?: number;
  /** Soft watermark mode for empty/success surfaces */
  muted?: boolean;
};

/**
 * BaladiGuard cedar brand mark — use only in brand-defining contexts
 * (wordmark, auth, selected empty/success). Never as a generic UI icon.
 */
export function BrandMark({ className, size = 28, muted = false }: BrandMarkProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M16 3.5c.4 0 .7.15.95.45l2.7 3.3c.35.42.1 1.05-.45 1.15l-1.7.3 3.55 3.85c.4.43.1 1.15-.5 1.2l-2.05.15 4.1 4.2c.42.43.12 1.15-.48 1.2H10.88c-.6-.05-.9-.77-.48-1.2l4.1-4.2-2.05-.15c-.6-.05-.9-.77-.5-1.2l3.55-3.85-1.7-.3c-.55-.1-.8-.73-.45-1.15l2.7-3.3c.25-.3.55-.45.95-.45Z"
        fill={muted ? 'currentColor' : 'var(--lb-green)'}
        opacity={muted ? 0.12 : 1}
      />
      <path
        d="M14.2 20.2h3.6v6.3c0 .55-.45 1-1 1h-1.6c-.55 0-1-.45-1-1v-6.3Z"
        fill={muted ? 'currentColor' : 'var(--lb-green-dark)'}
        opacity={muted ? 0.12 : 1}
      />
    </svg>
  );
}

/** Thin red–white–red accent. Avoid green–white–red equal bands (Italy read). */
export function BrandStripe({ className }: { className?: string }) {
  return (
    <span className={className ? `brand-stripe ${className}` : 'brand-stripe'} aria-hidden="true" />
  );
}
