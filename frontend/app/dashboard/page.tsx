import AdminPanel from "@/components/AdminPanel";

export const metadata = {
  title: "Admin — Fintech Onchain",
};

export default function DashboardPage() {
  return (
    <main className="dashboard-page">
      <div className="dashboard-header">
        <h2 className="page-title">Admin</h2>
        <p className="page-subtitle">
          Review queue (kept / review / killed) and manual posting.
        </p>
      </div>
      <AdminPanel />
    </main>
  );
}
