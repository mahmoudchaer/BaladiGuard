import { useId } from 'react';

type BrandMarkProps = {
  className?: string;
  size?: number | string;
};

/**
 * BaladiGuard brand mark: Lebanese cedar on a shield with a map pin.
 * Use for brand surfaces (nav, footer, hero, empty states, list glyphs).
 */
export function BrandMark({ className, size = 40 }: BrandMarkProps) {
  const gradientId = useId().replace(/:/g, '');

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse cx="100" cy="178" rx="42" ry="8" fill="var(--brand)" opacity="0.08" />
      <path
        d="M100 16c32 12 54 17 68 19.5V92c0 38-28 66-68 94-40-28-68-56-68-94V35.5C46 33 68 28 100 16Z"
        fill={`url(#${gradientId})`}
      />
      <path
        d="M100 16c32 12 54 17 68 19.5V92c0 38-28 66-68 94-40-28-68-56-68-94V35.5C46 33 68 28 100 16Z"
        stroke="var(--brand-dark)"
        strokeOpacity="0.18"
        strokeWidth="1.25"
      />
      <path
        d="M100 36c24 9 40.5 12.8 50 14.5V90c0 27-21 48-50 70-29-22-50-43-50-70V50.5C59.5 48.8 76 45 100 36Z"
        fill="#fff"
      />
      <g transform="translate(100 72)">
        <path
          d="M0-22c.7 0 1.25.28 1.65.8l7.2 9.55c.6.8.16 1.95-.8 2.1l-3.55.55 6.55 7.25c.65.72.16 1.95-.85 2.05l-4.05.3 8.1 8.45c.7.72.2 2-.85 2.05H-13.5c-1.05-.05-1.55-1.33-.85-2.05l8.1-8.45-4.05-.3c-1.01-.1-1.5-1.33-.85-2.05l6.55-7.25-3.55-.55c-.96-.15-1.4-1.3-.8-2.1L-1.65-21.2C-1.25-21.72-.7-22 0-22Z"
          fill="var(--brand)"
        />
        <path
          d="M-3.4 12.5h6.8V26c0 1.1-.9 2-2 2h-2.8c-1.1 0-2-.9-2-2V12.5Z"
          fill="var(--brand-dark)"
        />
      </g>
      <g transform="translate(128 98)">
        <path
          d="M14 2c6.63 0 12 5.15 12 11.5C26 22.2 14 34 14 34S2 22.2 2 13.5C2 7.15 7.37 2 14 2Z"
          fill="var(--accent)"
        />
        <circle cx="14" cy="13.2" r="4.4" fill="#fff" />
      </g>
      <defs>
        <linearGradient
          id={gradientId}
          x1="52"
          y1="20"
          x2="148"
          y2="180"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#1a9a55" />
          <stop offset="0.55" stopColor="var(--brand)" />
          <stop offset="1" stopColor="var(--brand-dark)" />
        </linearGradient>
      </defs>
    </svg>
  );
}
