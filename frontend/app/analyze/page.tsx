import AnalyzeForm from "@/components/AnalyzeForm";

export const metadata = {
  title: "AI Trade Analysis — Fintech Onchain",
  description:
    "Paste any fintech or crypto news article and get an instant AI-powered trade recommendation with live prices.",
};

export default function AnalyzePage() {
  return (
    <main className="analyze-page">
      <div className="analyze-header">
        <h2 className="page-title">AI Trade Analysis</h2>
        <p className="page-subtitle">
          Paste a news article URL for an instant AI-powered trade recommendation
        </p>
      </div>
      <AnalyzeForm />
    </main>
  );
}
