export const clinicalGroups = {
  consultations: "Consultation notes",
  follow_ups: "Consultation follow-ups",
  diagnoses: "Diagnoses and conditions",
  allergies: "Allergies and reactions",
  labs: "Lab results",
  care_plans: "Appointments, referrals and tests",
  medications: "Medication history and reconciliation",
  interventions: "Staff interventions and outcomes",
  source_reviews: "Document transcription reviews",
} as const;
export const allClinicalResources: string[] = Object.keys(clinicalGroups);
export const resourceForKind: Record<string, string> = {
  diagnosis: "diagnoses",
  allergy: "allergies",
  lab: "labs",
  appointment: "care_plans",
  referral: "care_plans",
  test: "care_plans",
  medication_order: "medications",
  dispensing: "medications",
  confirmed_use: "medications",
  intervention: "interventions",
};
export function groupLabel(key: string) {
  return clinicalGroups[key as keyof typeof clinicalGroups] || key;
}
export function selectClinicalGroup(current: string[], key: string, checked: boolean) {
  const result = new Set(current);
  if (checked) {
    result.add(key);
    if (key === "interventions") result.add("care_plans");
  } else {
    result.delete(key);
    if (key === "care_plans") result.delete("interventions");
  }
  return allClinicalResources.filter((group) => result.has(group));
}
