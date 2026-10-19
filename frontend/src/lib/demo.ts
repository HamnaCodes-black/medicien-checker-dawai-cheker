export type DemoCaseId =
  | "authentic"
  | "typo"
  | "expired"
  | "wrong-color";

export interface DemoCase {
  id: DemoCaseId;
  labelKey: string;
  descriptionKey: string;
  tone: "consistent" | "suspicious";
}

export const DEMO_CASES: DemoCase[] = [
  {
    id: "authentic",
    labelKey: "demo.authentic",
    descriptionKey: "demo.authenticHint",
    tone: "consistent",
  },
  {
    id: "typo",
    labelKey: "demo.typo",
    descriptionKey: "demo.typoHint",
    tone: "suspicious",
  },
  {
    id: "expired",
    labelKey: "demo.expired",
    descriptionKey: "demo.expiredHint",
    tone: "suspicious",
  },
  {
    id: "wrong-color",
    labelKey: "demo.wrongColor",
    descriptionKey: "demo.wrongColorHint",
    tone: "suspicious",
  },
];

export const DEMO_PHOTOS: Record<DemoCaseId, Record<string, string>> = {
  authentic: {
    front: "/demo/authentic-front.png",
    back: "/demo/authentic-back.png",
    batch: "/demo/authentic-batch.png",
  },
  typo: {
    front: "/demo/typo-front.png",
    back: "/demo/typo-back.png",
    batch: "/demo/typo-batch.png",
  },
  expired: {
    front: "/demo/expired-front.png",
    back: "/demo/expired-back.png",
    batch: "/demo/expired-batch.png",
  },
  "wrong-color": {
    front: "/demo/wrong-color-front.png",
    back: "/demo/wrong-color-back.png",
    batch: "/demo/wrong-color-batch.png",
  },
};
