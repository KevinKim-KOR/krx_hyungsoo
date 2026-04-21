import { PageFrame } from "./components/PageFrame";
import { DashboardManager } from "./dashboard/DashboardManager";

export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <PageFrame title="홈">
      <DashboardManager />
    </PageFrame>
  );
}
