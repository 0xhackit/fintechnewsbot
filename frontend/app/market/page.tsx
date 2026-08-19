import MarketReport from "@/components/MarketReport";

export const metadata = {
  title: "Market profile — shadow preview",
};

export default function MarketPage() {
  return (
    <main className="feed" style={{ maxWidth: "none" }}>
      <MarketReport />
    </main>
  );
}
