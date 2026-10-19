import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

export function DisclaimerBar() {
  const { t } = useTranslation();
  return (
    <aside className="disclaimer-fixed" role="note">
      <div className="disclaimer-inner">
        <ShieldAlert size={18} aria-hidden="true" />
        <p>
          <strong>{t("result.disclaimerLabel")}:</strong> {t("app.disclaimer")}
        </p>
      </div>
    </aside>
  );
}
