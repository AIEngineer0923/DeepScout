"use client";

import { LiveResearchScreen } from "@/components/screens/LiveResearchScreen";
import { MobileRunScreen } from "@/components/screens/MobileRunScreen";
import { useEffect, useState } from "react";

export default function LivePage() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 430px)");
    const update = () => setMobile(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return mobile ? <MobileRunScreen /> : <LiveResearchScreen />;
}
