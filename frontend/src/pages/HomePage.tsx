import { useOutletContext } from "react-router-dom";
import type { User } from "../api";
import CareCard from "../portal/CareCard";

export default function HomePage() {
  const user = useOutletContext<User>();
  const staff = user.role === "doctor" || user.role === "assistant";

  return (
    <section>
      <div className="page-heading">
        <span className="eyebrow">{staff ? "Clinic workspace" : "My care"}</span>
        <h1>Welcome, {user.display_name}</h1>
        <p>{staff ? "Manage today’s clinic and help patients find care." : "What would you like to do today?"}</p>
      </div>
      <div className="care-grid care-grid-compact">
        {!staff && (
          <CareCard
            icon="＋"
            title="Book a consultation"
            description="Choose an available practitioner and time."
            to="/app/book"
          />
        )}
        {staff && (
          <CareCard
            icon="▦"
            title="Plot clinic schedule"
            description="Set practitioner hours and clinic closures."
            to="/app/schedule"
          />
        )}
        {staff && (
          <CareCard
            icon="＋"
            title="Book for a patient"
            description="Reserve an available time on a patient’s behalf."
            to="/app/on-behalf"
          />
        )}
        <CareCard
          icon="◷"
          title="Visit history"
          description={staff ? "Review consultation records and the patient queue." : "See upcoming and past consultations."}
          to="/app/history"
        />
        <CareCard
          icon="◇"
          title="Alerts"
          description="Read updates about bookings and records."
          to="/app/alerts"
        />
      </div>
      <p className="signed-in-note">Signed in as {user.email}</p>
    </section>
  );
}
