import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="page page-narrow py-12 text-center">
      <div className="empty-visual">
        <Compass size={32} aria-hidden="true" />
      </div>
      <h1 className="display-page font-display mt-5">
        {t("errors.notFoundTitle")}
      </h1>
      <p className="lead mx-auto mt-2 max-w-md">{t("errors.notFoundBody")}</p>
      <Link to="/" className="btn btn-primary mt-6">
        {t("nav.home")}
      </Link>
    </div>
  );
}
