// 서버 컴포넌트 — 상호작용이 있는 승인 루프 뷰는 클라이언트 컴포넌트로 위임한다.
// (DEV_RULES F항: 서버 컴포넌트에 직접 이벤트 핸들러 금지)
import ApprovalLoopClient from "./components/ApprovalLoopClient";

export default function Page() {
  return <ApprovalLoopClient />;
}
