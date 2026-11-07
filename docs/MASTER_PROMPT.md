# MASTER PROMPT — CAREGAP 360
## AI-Powered Unified Health Records, Medication Intelligence & Predictive Care Continuity Platform

### 1. YOUR ROLE

You are acting as an expert software engineering team consisting of:

- Principal Software Architect
- Senior Full-Stack Developer
- Python Backend Engineer
- AI/ML Research Engineer
- Healthcare Interoperability Specialist
- Cybersecurity Engineer
- Database Architect
- UI/UX Designer
- QA Automation Engineer
- DevOps Engineer

Your responsibility is to architect, implement, test, debug, document, and progressively harden **CareGap 360**, a real-world healthcare software platform.

This is NOT a hackathon project, academic prototype, basic CRUD application, or static UI demonstration.

The goal is a maintainable, secure, modular system that can eventually be deployed in real healthcare environments after the necessary clinical evaluation, privacy compliance, security reviews, and institutional approvals.

Use production-oriented engineering practices throughout, while clearly distinguishing implemented functionality from features requiring further validation.

Do not claim the system is clinically validated or production-certified merely because it passes software tests.

---

# 2. PROJECT VISION

**Project Name:** CareGap 360

**Full Name:** CareGap 360 — Intelligent Longitudinal Health Records and Care Continuity Platform

**Mission:**

Create a secure, patient-controlled digital healthcare ecosystem that consolidates medical records from different doctors and hospitals, extracts and organizes prescription information using AI, helps clinicians review medication histories, identifies incomplete care journeys, predicts follow-up risks, and supports personalized interventions.

**Core Problem:**

Patients frequently visit multiple healthcare providers.

Their prescriptions, diagnoses, tests, and treatment information may remain scattered across paper records, PDFs, hospital systems, and personal messages.

Consequently:
- Doctors may not have access to relevant previous medical history.
- Patients may forget which medicines were prescribed.
- Medication lists from different doctors may conflict.
- Tests and referrals may remain incomplete.
- Important follow-up appointments may be missed.
- Healthcare professionals may struggle to identify care gaps early.

CareGap 360 should address these problems through unified records, consent-based sharing, intelligent document processing, and longitudinal care coordination.

---

# 3. CORE PRODUCT REQUIREMENTS

Build a responsive web application initially, with an architecture that can support a mobile application later.

Implement three primary user roles:

**Patient**
- Register and securely authenticate.
- Maintain their own health profile.
- Upload medical documents.
- View prescriptions and consultation history.
- Track medications and upcoming follow-ups.
- Approve or deny doctor access.
- Review the history of record access.
- Request correction of incorrect information.

**Doctor / Healthcare Professional**
- Complete a verification and onboarding workflow.
- Request access to a patient's information.
- Access only records the patient has authorized and that the doctor is permitted to see.
- Review a chronological medical history.
- View original prescriptions and verified structured data.
- Review medication discrepancies.
- Create consultation notes and follow-up recommendations.
- Review care-gap alerts.
- Record follow-up outcomes.

**Platform Administrator**
- Manage verification workflows.
- Configure organization and user roles.
- Monitor system health and security events.
- Manage permissions and operational settings.
- Review audit metadata without unrestricted access to patient medical information.

Use least-privilege authorization for every role.

---

# 4. FEATURE MODULE A — UNIFIED PATIENT HEALTH RECORD

Create a longitudinal medical record for each patient.

The platform should support:

1. Patient identity and demographic information.
2. Medical visit history.
3. Doctor and hospital information.
4. Prescription records.
5. Laboratory reports.
6. Diagnoses and documented medical conditions.
7. Allergies and recorded adverse reactions.
8. Medication history.
9. Referrals and follow-up plans.
10. Document attachments.

Every medical record must retain:
- Source document or system.
- Date of creation.
- Date of upload.
- Author or healthcare provider, where available.
- Verification status.
- Patient ownership/linkage.
- Last modification information.
- Relevant audit metadata.

Never silently overwrite the original clinical source.

Provide a chronological patient medical timeline with filters for consultation, medication, test, diagnosis, and referral.

Support search across authorized records.

---

# 5. FEATURE MODULE B — AI PRESCRIPTION DIGITIZATION

Allow patients or authorized doctors to upload prescriptions as:

- JPG
- PNG
- PDF
- Scanned medical documents

Create a document-processing pipeline:

**Step 1: File ingestion**

Validate file type, size, and integrity. Store the original securely.

**Step 2: OCR**

Extract text using a suitable OCR or document-understanding model.

**Step 3: Structured information extraction**

Use an LLM or other document extraction model to identify:

- Doctor's name, if present.
- Consultation date.
- Hospital or clinic.
- Medication name.
- Strength.
- Dosage instructions.
- Frequency.
- Duration.
- Route of administration.
- Follow-up instructions.
- Test recommendations.

**Step 4: Normalization**

Map extracted medication names to standardized terminology where possible.

Retain the original text and source image references.

**Step 5: Confidence and uncertainty handling**

Display:
- Extracted values.
- Confidence or uncertainty indicators.
- Missing fields.
- Ambiguous handwriting.
- Fields requiring manual review.

Do not fabricate a drug name, dosage, frequency, or diagnosis when the document is unclear.

**Step 6: Human verification**

Present an editable review screen.

Uncertain or clinically significant fields must be verified by an appropriately authorized user before entering a trusted medication record.

**Step 7: Persistence**

Save the verified information as structured database records, linked to the original source.

Implement an asynchronous processing queue with visible processing states.

---

# 6. FEATURE MODULE C — SECURE DOCTOR ACCESS

Build a patient-authorized medical-record sharing system.

A doctor must NOT be able to retrieve private medical history simply by typing a patient name.

Implement:

- Unique internal patient identifiers.
- Verified login and doctor identity.
- Doctor-initiated access requests.
- Patient consent approval.
- Optional patient QR-code sharing flow.
- Time-limited access grants.
- Record-scoped permissions.
- Access revocation for future requests.
- Complete access audit history.

A doctor should be able to request a patient's history, and the patient should see:

- Who is requesting access.
- Which organization they represent.
- Which records are requested.
- Purpose of access.
- Access duration.

Implement consent-aware API authorization.

Revocation must block future access; do not falsely imply that it removes information previously downloaded by an authorized recipient.

Explore ABDM/ABHA integration as an optional interoperability module for India.

Do not claim to have live ABDM access unless real integration, authorization, and conformance have been completed.

---

# 7. FEATURE MODULE D — MEDICATION RECONCILIATION

Create a medication reconciliation workspace.

Its purpose is to help clinicians compare medication information from different consultations.

Capabilities:

1. Aggregate recorded prescriptions across visits.
2. Display medication timelines.
3. Distinguish:
   - Prescribed medications.
   - Dispensed medications.
   - Patient-reported current use.
   - Clinician-confirmed current medications.
4. Detect possible duplicate medication entries.
5. Identify overlapping prescriptions.
6. Detect contradictory medication information.
7. Flag incomplete medication instructions.
8. Present records needing clinician verification.

Provide comparison views showing the original source documents.

Never assume that a prescription proves the patient is currently taking a medicine.

Do not autonomously start, stop, or change prescribed medicines.

---

# 8. FEATURE MODULE E — MEDICATION SAFETY ASSISTANCE

Build a clinician-facing medication review assistant.

Potential functions:

- Potential drug-drug interaction checks.
- Documented allergy conflicts.
- Duplicate therapy indicators.
- Inconsistent dosage records.
- Medication discrepancy summaries.

Use validated clinical medication knowledge sources and approved terminology mappings.

Do NOT rely on an unrestricted LLM to invent drug interactions or determine safe doses.

If an appropriate verified drug database is unavailable, implement the integration interface and a clearly marked synthetic demonstration mode.

Display evidence and source references for safety alerts.

Require clinician review.

The system is clinical decision support, not an autonomous prescribing system.

---

# 9. FEATURE MODULE F — CARE-GAP PREDICTION

Build a machine learning system for identifying patients at risk of incomplete follow-up care.

Potential inputs include:

- Historical appointment attendance.
- Referral completion history.
- Time since last appointment.
- Previously missed follow-ups.
- Patient-reported access barriers.
- Appointment scheduling characteristics.
- Appropriate clinical context with authorization.

Potential target outcomes:

- Missed scheduled appointment.
- Uncompleted referral.
- Delayed recommended follow-up.
- Missing required test completion.

Start with interpretable baseline models.

Evaluate:

- Logistic regression.
- XGBoost.
- Survival analysis.
- Gradient boosting approaches.

Add SHAP-based explainability where technically appropriate.

Evaluation must include:

- Precision.
- Recall.
- PR-AUC.
- Calibration.
- False-positive rates.
- Subgroup performance.
- Temporal validation.
- Data leakage checks.

Do not fabricate training data quality, model performance, or clinical effectiveness.

Use synthetic data for initial integration testing.

Train a clinically meaningful model only after suitable labeled, representative data and appropriate approvals are available.

Never represent synthetic-data performance as real-world clinical validation.

---

# 10. FEATURE MODULE G — CAUSAL INTERVENTION INTELLIGENCE

This is one of the proposed advanced differentiators.

Ordinary prediction systems estimate which patients might miss appointments.

CareGap 360 should eventually estimate which permitted intervention may improve an individual patient's probability of completing care.

Possible interventions:

- Appointment rescheduling.
- Multilingual reminders.
- Staff outreach.
- Transport assistance.
- Financial support referrals.
- Clarification of clinician-approved instructions.

Investigate:

- Causal inference.
- Treatment-effect estimation.
- Causal forests.
- Doubly robust learning.
- Uplift modeling.
- Contextual bandits for future, carefully governed use.

IMPORTANT:

Do not claim causal effects based purely on correlations.

First design an intervention event schema, logging framework, and evaluation plan.

Consider confounding, intervention selection bias, missing outcomes, and appropriate prospective evaluation.

Until a model has adequate data and validation, provide transparent rule-based intervention suggestions for staff review.

High-impact patient interventions require human oversight.

---

# 11. FEATURE MODULE H — SMART PATIENT AND DOCTOR DASHBOARDS

Design a modern healthcare SaaS interface.

**Patient Dashboard**
- Health overview.
- Recent consultations.
- Medical timeline.
- Prescription library.
- Medication history.
- Upcoming follow-ups.
- Pending tests and referrals.
- Doctor access requests.
- Consent management.
- Notifications.

**Doctor Dashboard**
- Authorized patient list.
- Patient medical summary.
- Original prescription viewer.
- Medication reconciliation.
- Consultation history.
- Pending follow-ups.
- Care-gap alerts.
- Risk explanations.
- Intervention review.
- Consultation notes.

**Admin Dashboard**
- User and organization management.
- Doctor verification status.
- Operational metrics.
- Audit events.
- System monitoring.

UI requirements:
- Clean, modern, professional styling.
- Responsive mobile and desktop layouts.
- Accessible colors and controls.
- Loading, empty, error, and success states.
- Consistent component library.
- Search, sorting, and filtering.
- Accessible navigation.
- No decorative or nonfunctional buttons.
- No fabricated metrics presented as real patient analytics.

Prefer a polished healthcare design, not a generic AI dashboard.

---

# 12. FEATURE MODULE I — MEDICAL HISTORY AI SUMMARY

Add an AI-assisted longitudinal history summarizer.

A doctor should be able to request an overview of authorized historical records.

The summary may organize:

- Previous consultations.
- Documented diagnoses.
- Prescribed medication history.
- Patient-reported current medicines.
- Recorded allergies.
- Important tests.
- Outstanding referrals and follow-ups.
- Medication discrepancies needing review.

Every medically significant statement must link to its source record.

Separate:
- Verified facts.
- Patient-reported information.
- AI-generated interpretations.
- Missing or uncertain information.

Do not invent diagnoses or claim a clinical conclusion without evidence.

Use retrieval over authorized documents only, with source citations.

---

# 13. FEATURE MODULE J — NOTIFICATIONS AND CARE COORDINATION

Create a follow-up scheduling and notification system.

Capabilities:

- Appointment reminders.
- Pending-test reminders.
- Referral follow-up notifications.
- Patient-requested rescheduling.
- Missed-follow-up flags.
- Staff-reviewed escalation workflows.
- Notification preferences.
- Notification delivery history.

Use an abstraction for email, SMS, and WhatsApp.

For local development, implement mock notification providers.

Do not send real healthcare information through external messaging services before consent, privacy controls, and provider integrations are properly configured.

---

# 14. RECOMMENDED TECHNOLOGY STACK

Use the following stack unless a clearly justified alternative is necessary.

**Frontend**
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Query / TanStack Query

**Backend**
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

**Database**
- PostgreSQL

**Document storage**
- S3-compatible private object storage.
- MinIO for local development.

**Background processing**
- Redis
- Celery or an equivalent reliable job-processing system.

**AI/ML**
- Python
- OCR/document understanding
- Structured LLM extraction
- scikit-learn
- XGBoost
- SHAP
- EconML / DoWhy when justified

**Security**
- Secure authentication.
- Role- and relationship-based authorization.
- Server-side consent enforcement.
- Encryption in transit and at rest.
- Audit logging.
- Secrets management.

**Interoperability**
- HL7 FHIR-aligned data models.
- Optional ABDM/ABHA integration adapters.

**Testing**
- Pytest.
- React Testing Library.
- Playwright.
- API integration tests.
- Authorization security tests.

**DevOps**
- Docker.
- Docker Compose.
- GitHub Actions.
- Environment-based configuration.

Use a modular monolith initially rather than unnecessarily splitting everything into microservices.

Make module boundaries clear so the platform can scale later.

---

# 15. DATABASE ARCHITECTURE

Design a normalized PostgreSQL schema.

Include appropriate entities for:

- Users.
- Patients.
- Doctors.
- Healthcare organizations.
- Professional verification records.
- Patient-doctor relationships.
- Consent grants.
- Access requests.
- Medical visits.
- Medical documents.
- Prescription records.
- Medication entries.
- Medication reconciliation events.
- Allergies.
- Diagnoses.
- Laboratory reports.
- Referrals.
- Follow-up tasks.
- Appointments.
- Risk assessments.
- Intervention recommendations.
- Intervention events.
- Notifications.
- Audit events.

Use appropriate foreign keys, indexes, constraints, migrations, and timestamps.

Preserve clinical data provenance and version history.

Design clear mappings to relevant HL7 FHIR resources such as Patient, Practitioner, Encounter, DocumentReference, MedicationRequest, MedicationStatement, Observation, ServiceRequest, and Consent where applicable.

Do not force incomplete mappings or confuse FHIR resources that represent different medical concepts.

---

# 16. PRIVACY, SECURITY AND MEDICAL SAFETY

CareGap 360 contains highly sensitive medical information.

Security and privacy must be foundational.

Implement:
- Strong authentication.
- Least-privilege access control.
- Patient-level authorization.
- Consent verification at API and data-access layers.
- Tenant and organization isolation.
- Encrypted communications.
- Private document storage.
- Signed or authenticated file access.
- Secure file-upload validation.
- Sensitive-data-safe application logs.
- Audit trails.
- Secure session handling.
- Rate limiting.
- Input validation.
- Protection against common web attacks.
- Backup and recovery planning.
- Data retention and deletion workflows.
- Privacy-aware error handling.

Document compliance considerations for the Indian Digital Personal Data Protection framework and relevant healthcare requirements.

Do not claim legal compliance without independent verification.

An emergency access or break-glass workflow must not bypass safeguards casually; if implemented, it requires explicit authorization, limited access, justification, and heightened auditing.

Never use real patient data in AI coding prompts, tests, or external development services.

All generated demonstration data must be clearly synthetic.

---

# 17. AI SAFETY AND QUALITY REQUIREMENTS

AI must never silently invent or modify a patient's clinical history.

For each extracted or summarized clinical value:

- Preserve source provenance.
- Report extraction uncertainty.
- Support human correction.
- Track verification status.
- Distinguish model output from clinician-confirmed information.

Do not autonomously diagnose illness, prescribe medication, change dosages, or make emergency triage decisions.

Clinical decision-support features must display limitations and require qualified human review.

Include tests for:
- Unclear handwriting.
- Missing medication strength.
- Similar drug names.
- Duplicate prescriptions.
- Incorrect patient association.
- Conflicting dates.
- Missing source records.
- Unauthorized access.
- Incomplete clinical documents.

---

# 18. PROJECT STRUCTURE

Create a maintainable monorepo with clearly organized directories for:

- Frontend application.
- Backend application.
- Domain modules.
- Database models and migrations.
- API schemas.
- Authentication and authorization.
- Document-processing workers.
- AI/ML pipelines.
- FHIR mapping adapters.
- Unit tests.
- Integration tests.
- End-to-end tests.
- Infrastructure.
- Developer documentation.

Choose sensible naming conventions and enforce consistent formatting, typing, and linting.

Maintain README documentation, setup instructions, architecture decisions, and API documentation.

---

# 19. DEVELOPMENT ROADMAP

Implement the system in independently testable milestones.

### PHASE 1 — FOUNDATION

Build:
- Repository structure.
- Docker development environment.
- Database connection and migrations.
- Authentication.
- Patient, doctor, and admin roles.
- Role-aware application navigation.
- Initial dashboard layouts.
- Synthetic seed data.
- Automated test framework.

Acceptance: The application starts locally, users can authenticate, access is correctly restricted, and the first automated tests pass.

### PHASE 2 — MEDICAL RECORDS

Build:
- Patient profiles.
- Secure document uploads.
- Medical history timeline.
- Prescription document library.
- Consultation record management.
- Private file storage.
- Provenance tracking.

Acceptance: A synthetic patient can upload and retrieve their records, while unauthorized users cannot access them.

### PHASE 3 — AI PRESCRIPTION EXTRACTION

Build:
- OCR pipeline.
- Structured extraction.
- Review interface.
- Medication normalization.
- Verification workflow.
- Background processing.
- Original-document linkage.

Acceptance: Sample prescriptions can be processed and reviewed without silently accepting uncertain drug information.

### PHASE 4 — DOCTOR ACCESS AND CONSENT

Build:
- Doctor verification workflow.
- Patient access requests.
- Consent approval.
- Scoped record sharing.
- Access expiration.
- Audit logging.

Acceptance: Doctor access is denied by default and works only with the required verified permissions.

### PHASE 5 — MEDICATION INTELLIGENCE

Build:
- Medication history comparison.
- Reconciliation interface.
- Duplicate-entry detection.
- Verified knowledge-base integration interface.
- Clinician review queue.

Acceptance: The system reliably identifies tested record discrepancies and does not fabricate clinical safety conclusions.

### PHASE 6 — CARE-GAP ANALYTICS

Build:
- Follow-up event tracking.
- Risk-model training pipeline.
- Baseline prediction model.
- Risk explanations.
- Model evaluation reports.
- Doctor dashboard integration.

Acceptance: The pipeline is reproducible, evaluates against held-out data, and clearly labels synthetic-data results.

### PHASE 7 — INTERVENTION INTELLIGENCE

Build:
- Intervention event logging.
- Rule-based recommendations.
- Outcome tracking.
- Causal evaluation framework.
- Research-ready experiment infrastructure.

Acceptance: The system can measure and compare interventions using appropriately collected outcome data, without unsupported causal claims.

### PHASE 8 — ADVANCED INTEGRATION

Build:
- Source-grounded medical summaries.
- Multilingual interfaces.
- FHIR export/import adapters.
- Optional ABDM integration preparation.
- Notification provider adapters.
- Operational monitoring.

### PHASE 9 — HARDENING AND DEPLOYMENT

Build:
- Security testing.
- End-to-end regression suite.
- Accessibility improvements.
- Performance testing.
- CI/CD pipeline.
- Staging environment.
- Backup and recovery procedures.
- Deployment documentation.

A real patient-facing deployment requires additional clinical, legal, security, and operational review.

---

# 20. AGENT EXECUTION RULES

You are not merely producing design recommendations.

You must actively implement a functioning application, incrementally.

Follow these rules:

1. Inspect the repository before making changes.
2. Create an architecture document and implementation roadmap.
3. Use planning mode for major architectural decisions.
4. Break complex work into manageable, testable tasks.
5. Implement actual frontend, backend, database, and API functionality.
6. Do not create fake API responses disguised as working integrations.
7. Use clearly labeled mocks only where external services or real clinical data are unavailable.
8. Run relevant tests after each feature.
9. Investigate and fix errors introduced by your changes.
10. Review generated code for authorization and security flaws.
11. Keep database migrations consistent.
12. Avoid unnecessary dependencies and excessive abstractions.
13. Preserve working code when adding features.
14. Use Git checkpoints before substantial refactoring.
15. Do not commit secrets, credentials, or patient information.
16. Request approval before destructive operations, external deployments, account connections, or security-sensitive changes.
17. Maintain a progress document showing completed, partial, blocked, and unimplemented features.
18. Never claim that a feature works unless it has been implemented and tested.
19. If a test fails, report the failure and attempt a targeted correction.
20. Clearly explain any limitations that remain.

Use browser automation, when available, to verify important frontend flows.

Use the terminal to execute tests and inspect runtime failures.

Do not bypass failing tests by deleting assertions or weakening expected behavior.

---

# 21. FINAL PRODUCT QUALITY EXPECTATIONS

The application should eventually include:

- A professional patient dashboard.
- A functional doctor dashboard.
- Secure authentication and authorization.
- Patient-controlled medical-record sharing.
- Working medical document storage.
- AI-assisted prescription extraction.
- Source-linked medical history.
- Medication reconciliation.
- Clinician-supervised safety checks.
- Follow-up tracking.
- Interpretable care-gap risk estimates.
- Research-ready intervention evaluation.
- Complete API documentation.
- Automated testing.
- Dockerized development setup.
- Security and operational documentation.

The product should be designed for extension and long-term maintenance.

Avoid placeholder pages, dead navigation links, hardcoded production credentials, and invented clinical data.

---

# 22. BEGIN IMPLEMENTATION

Start by performing the following tasks:

**Task 1:** Inspect the current workspace and identify any existing files.

**Task 2:** Produce a concise but complete technical architecture with a diagram, module responsibilities, and major engineering decisions.

**Task 3:** Create an implementation roadmap with dependencies and measurable acceptance criteria.

**Task 4:** Design the initial PostgreSQL database schema and authorization model.

**Task 5:** Scaffold the actual Next.js frontend, FastAPI backend, PostgreSQL database, and Docker Compose development environment.

**Task 6:** Implement the first working vertical slice:

Patient registration/login → protected patient dashboard → medical-document upload → secure database/file persistence → authorized document retrieval.

**Task 7:** Add and run automated tests for this first vertical slice, including unauthorized-access tests.

**Task 8:** Start the application, verify the workflow, identify any failures, and fix them.

**Task 9:** Report:
- Files created and modified.
- Features implemented.
- Tests executed and results.
- How to run the application.
- Any blockers.
- The next recommended milestone.

Do not attempt to implement all advanced AI modules at once.

Continue milestone by milestone, preserving a functioning application.

**PRIMARY OBJECTIVE: Build CareGap 360 into a real, secure, technically advanced, independently maintainable healthcare software platform—not merely generate code that looks complete.**
