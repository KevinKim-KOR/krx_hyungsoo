// 서버 컴포넌트 — 상호작용 뷰는 클라이언트 컴포넌트 MainPanel 로 위임.
// (DEV_RULES F항: 서버 컴포넌트에 직접 이벤트 핸들러 금지)
import MainPanel from "./components/MainPanel";

export default function Page() {
  return <MainPanel />;
}
