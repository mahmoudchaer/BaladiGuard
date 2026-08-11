import { Link } from 'react-router-dom';

type StubPageProps = {
  title: string;
  message: string;
};

export function StubPage({ title, message }: StubPageProps) {
  return (
    <div className="page">
      <h1>{title}</h1>
      <div className="panel stack">
        <p style={{ margin: 0, lineHeight: 1.55 }}>{message}</p>
        <Link className="button button-secondary" to="/">
          Browse public reports
        </Link>
        <Link to="/track">Track by code instead</Link>
      </div>
    </div>
  );
}
