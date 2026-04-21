import type { ReactNode } from "react";

type AppModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  size?: "md" | "xl";
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
};

export function AppModal({
  open,
  title,
  subtitle,
  size = "md",
  onClose,
  footer,
  children,
}: AppModalProps) {
  if (!open) {
    return null;
  }

  const dialogClassName =
    size === "xl" ? "modal-dialog modal-xl modal-dialog-centered" : "modal-dialog modal-dialog-centered";

  return (
    <>
      <div className="modal modal-blur fade show d-block" role="dialog" aria-modal="true">
        <div className={dialogClassName}>
          <div className="modal-content">
            <div className="modal-header">
              <div>
                <h5 className="modal-title">{title}</h5>
                {subtitle ? <div className="tableMuted">{subtitle}</div> : null}
              </div>
              <button type="button" className="btn-close" aria-label="닫기" onClick={onClose} />
            </div>
            <div className="modal-body">{children}</div>
            {footer ? <div className="modal-footer">{footer}</div> : null}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" onClick={onClose} />
    </>
  );
}
