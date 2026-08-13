export function PrivacyPage() {
  return (
    <div className="page">
      <h1>Privacy</h1>
      <div className="panel stack">
        <p style={{ margin: 0, lineHeight: 1.55 }}>
          Public browsing shows only the citizen-safe projection: ticket number, status, category,
          description, public address text, map coordinates approved for publication, department
          name when assigned, attribution display name, and approved public photo URLs.
        </p>
        <p style={{ margin: 0, lineHeight: 1.55 }}>
          Internal ticket IDs, tracking codes from browse responses, contact details, private
          location precision, staff history, and private image keys are never shown on public
          surfaces.
        </p>
        <p style={{ margin: 0, lineHeight: 1.55 }}>
          Possession-based tracking requires your 6-character code and returns only the status
          timeline for that report.
        </p>
      </div>
    </div>
  );
}
