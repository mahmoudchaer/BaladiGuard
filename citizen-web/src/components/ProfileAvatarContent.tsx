export function ProfileAvatarContent({ fullName }: { fullName?: string | null }) {
  const initial = fullName?.trim().charAt(0).toLocaleUpperCase();

  if (initial) return <span aria-hidden>{initial}</span>;

  return (
    <svg className="profile-avatar-icon" viewBox="0 0 24 24" aria-hidden>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 20c.4-4 2.6-6 6.5-6s6.1 2 6.5 6" />
    </svg>
  );
}
