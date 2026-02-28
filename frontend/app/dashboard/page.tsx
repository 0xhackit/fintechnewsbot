import DashboardForm from "@/components/DashboardForm";

export const metadata = {
  title: "Manual Post Dashboard — Fintech Onchain",
};

export default function DashboardPage() {
  return (
    <main className="dashboard-page">
      <div className="dashboard-header">
        <h2 className="page-title">Manual Post Dashboard</h2>
        <p className="page-subtitle">
          Paste an article URL to scrape, preview, and post to X &amp; Telegram.
        </p>
      </div>
      <DashboardForm />
    </main>
  );
}
