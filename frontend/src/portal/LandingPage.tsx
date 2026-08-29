import { Link, useOutletContext } from "react-router-dom";
import type { User } from "../api";
import CareCard from "./CareCard";

function careLink(user: User | null, path: string): string {
  return user ? path : `/login?next=${encodeURIComponent(path)}`;
}

export default function LandingPage() {
  const user = useOutletContext<User | null>();
  const bookPath = user?.role === "doctor" || user?.role === "assistant" ? "/app/on-behalf" : "/app/book";

  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <span className="eyebrow">Healthcare made easier</span>
            <h1>Care that fits your schedule.</h1>
            <p>
              Find an available doctor, book your consultation, and keep every visit connected in one secure place.
            </p>
            <div className="hero-actions">
              <Link className="button button-large" to={careLink(user, bookPath)}>
                Book a consultation
              </Link>
              <a className="text-link" href="#get-care">
                Explore care options <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="hero-orbit hero-orbit-one" />
            <div className="hero-orbit hero-orbit-two" />
            <div className="hero-badge">
              <img src="/logo-mark.svg" alt="" />
              <span>
                <strong>Connected care</strong>
                From booking to follow-up
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="get-care">
        <div className="section-heading">
          <span className="eyebrow">Get care</span>
          <h2>What can we help you with?</h2>
          <p>Choose a service and RecLinq will guide you to the right place.</p>
        </div>
        <div className="care-grid">
          <CareCard
            icon="＋"
            title="Book a consultation"
            description="Choose from open clinic times and reserve your visit."
            to={careLink(user, bookPath)}
          />
          <CareCard
            icon="◷"
            title="Visit history"
            description="Review upcoming consultations, queue details, and past visits."
            to={careLink(user, "/app/history")}
          />
          <CareCard
            icon="◇"
            title="Health alerts"
            description="Stay informed when a booking or visit record changes."
            to={careLink(user, "/app/alerts")}
          />
          <CareCard
            eyebrow="For clinic staff"
            icon="▦"
            title="Plot a schedule"
            description="Publish practitioner hours and clinic closures."
            to={careLink(user, "/app/schedule")}
          />
        </div>
      </section>

      <section className="trust-section">
        <div className="section">
          <div className="section-heading section-heading-light">
            <span className="eyebrow">Why RecLinq</span>
            <h2>A simpler healthcare journey</h2>
          </div>
          <div className="trust-grid">
            <article>
              <span>01</span>
              <h3>Convenient booking</h3>
              <p>See real availability and choose a time that works for you.</p>
            </article>
            <article>
              <span>02</span>
              <h3>Connected records</h3>
              <p>Keep consultation notes and supporting documents with the visit.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Timely updates</h3>
              <p>Receive alerts as your appointment and care information change.</p>
            </article>
          </div>
        </div>
      </section>
    </>
  );
}
