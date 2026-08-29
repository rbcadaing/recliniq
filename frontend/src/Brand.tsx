import { Link } from "react-router-dom";

type Props = { size?: "sm" | "lg"; to?: string };

export default function Brand({ size = "sm", to }: Props) {
  const content = (
    <>
      <img src="/logo-mark.svg" alt="" className="brand-mark" />
      <span className="brand-name">
        Rec<span>Linq</span>
      </span>
    </>
  );
  const className = `brand${size === "lg" ? " brand-lg" : ""}`;

  if (to) {
    return (
      <Link to={to} className={className} aria-label="RecLinq home">
        {content}
      </Link>
    );
  }
  return <span className={className}>{content}</span>;
}
