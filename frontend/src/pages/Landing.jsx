// The LeadOps front page, laid out the way masal.ai's front page is: one promise, proof, how it works, the product,
// questions and one action. The property site it demonstrates lives at /demo.
import { useEffect } from "react";
import { Navigate, useLocation } from "react-router";
import { BusinessModel, Faq, FinalCall, Footer } from "../landing/Closing";
import DashboardPreview from "../landing/DashboardPreview";
import { Features, FollowUp } from "../landing/Features";
import { Hero, Signals, SiteHeader, WhyLeadOps } from "../landing/Hero";
import HowItWorks from "../landing/HowItWorks";
import LiveSort from "../landing/LiveSort";

export default function Landing() {
  const { search } = useLocation();
  useEffect(() => {
    document.title = "LeadOps: find the real buyers in your website traffic";
  }, []);

  // Tester links shared before the front page existed (/?lo_test=genuine&lo_tester=t01) belong on the property site.
  if (new URLSearchParams(search).has("lo_test")) return <Navigate to={`/demo${search}`} replace />;

  return (
    <div className="bg-night">
      <SiteHeader />
      <main>
        <Hero />
        <Signals />
        <WhyLeadOps />
        <LiveSort />
        <HowItWorks />
        <DashboardPreview />
        <Features />
        <FollowUp />
        <BusinessModel />
        <Faq />
        <FinalCall />
      </main>
      <Footer />
    </div>
  );
}
