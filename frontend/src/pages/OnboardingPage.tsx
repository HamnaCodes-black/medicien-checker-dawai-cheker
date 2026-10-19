import { useState } from "react";
import { Camera, ScanLine, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { LanguageToggle } from "../components/Controls";

const ONBOARDING_KEY = "dawaiicheck_onboarded";

interface Slide {
  icon: typeof ScanLine;
  titleKey: string;
  bodyKey: string;
  noteKey?: string;
}

const SLIDES: Slide[] = [
  {
    icon: ScanLine,
    titleKey: "onboarding.slide1Title",
    bodyKey: "onboarding.slide1Body",
    noteKey: "onboarding.slide1Note",
  },
  {
    icon: Camera,
    titleKey: "onboarding.slide2Title",
    bodyKey: "onboarding.slide2Body",
  },
  {
    icon: ShieldAlert,
    titleKey: "onboarding.slide3Title",
    bodyKey: "onboarding.slide3Body",
  },
];

export function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const slide = SLIDES[step];
  const Icon = slide.icon;
  const last = step === SLIDES.length - 1;

  const complete = (destination: string) => {
    try {
      window.localStorage.setItem(ONBOARDING_KEY, "1");
      navigate(destination, { replace: true });
    } catch {
      navigate(destination, { replace: true });
    }
  };

  return (
    <div className="page page-narrow py-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <span className="chip chip-brand">{t("app.tagline")}</span>
        <LanguageToggle />
      </div>

      <section className="hero-card surface-pad reveal" aria-live="polite">
        <div className="feature-icon" aria-hidden="true">
          <Icon size={22} />
        </div>
        <div className="mt-5">
          <p className="eyebrow">
            {t("onboarding.step", {
              current: step + 1,
              total: SLIDES.length,
            })}
          </p>
          <h1 className="display-hero font-display mt-2">
            {t(slide.titleKey)}
          </h1>
          <p className="lead mt-3">{t(slide.bodyKey)}</p>
          {slide.noteKey ? (
            <div className="notice mt-4" data-tone="warn">
              <ShieldAlert size={18} aria-hidden="true" />
              <span>{t(slide.noteKey)}</span>
            </div>
          ) : null}
        </div>

        <div className="step-pips mt-6" aria-hidden="true">
          {SLIDES.map((item, index) => (
            <span
              key={item.titleKey}
              className="step-pip"
              data-state={
                index === step ? "active" : index < step ? "done" : "pending"
              }
            />
          ))}
        </div>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
          <button
            type="button"
            className="btn btn-primary flex-1"
            onClick={() => (last ? complete("/scan") : setStep(step + 1))}
          >
            {last ? t("onboarding.start") : t("onboarding.next")}
          </button>
          <button
            type="button"
            className="btn btn-secondary flex-1"
            onClick={() => complete("/")}
          >
            {t("onboarding.skip")}
          </button>
        </div>
      </section>

      <div className="surface surface-pad mt-4">
        <p className="hint">{t("onboarding.privacyNote")}</p>
        <p className="hint mt-2">{t("onboarding.languageHint")}</p>
      </div>
    </div>
  );
}
