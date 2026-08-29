import { Link } from "react-router-dom";

type Props = {
  eyebrow?: string;
  title: string;
  description: string;
  to: string;
  icon: string;
};

export default function CareCard({ eyebrow, title, description, to, icon }: Props) {
  return (
    <Link className="care-card" to={to}>
      <span className="care-card-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="care-card-copy">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <strong>{title}</strong>
        <span>{description}</span>
      </span>
      <span className="care-card-arrow" aria-hidden="true">
        →
      </span>
    </Link>
  );
}
