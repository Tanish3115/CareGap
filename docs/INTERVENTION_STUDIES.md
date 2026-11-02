# Offline intervention study evaluation

The application records clinician-reviewed intervention events and outcome histories, and continues to use transparent rules for staff review. It never chooses a patient intervention from an unvalidated effect model. The offline evaluator adds executable study design, timing, missingness and assigned-arm analysis to the existing protocol. It does not allocate patients or read the application database.

From the root:

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate_interventions.py
backend/.venv/Scripts/python.exe scripts/evaluate_interventions.py --output .tools/research/new-synthetic-report.json
```

The default generates 2,000 artificial units with fixed-seed assignments and a stated artificial outcome process. The shipped aggregate artifact is reproducible from this generator. The authenticated **Registered synthetic intervention study** dashboard displays this artificial report separately from actual recorded patient outcomes. No patient was assigned an intervention to produce it.

For a separately approved, deidentified research dataset, supply `--protocol`, `--dataset` and a new private `--output` path. Never place the inputs in application source/data directories or source packages. The tool refuses to overwrite an output file. Approved-data mode requires hashed unit identifiers; synthetic mode requires synthetic identifiers. Extra fields such as patient names, clinical UUIDs or email addresses are rejected. Approval references and reported allocation remain operator assertions requiring independent verification.

The strict protocol specifies study ID, synthetic/approved-deidentified mode, registered allocation design, registration and analysis-cutoff times, fixed assignment probability, outcome window, outcome definition, approval reference and explicit research authorization. Participants contain one assignment per unit, baseline measurement/assignment dates, assigned and received treatment, reported assignment probability, documented binary outcome and observation timestamps, and bounded pre-assignment barrier/attendance features. See `backend/app/schemas/research_study.py` for the complete input contract.

Validation rejects repeated units, baseline measurements at/after assignment, unregistered or future-to-cutoff outcomes, mismatched randomization probabilities, missing comparison arms, completion outside the registered window, and a negative outcome recorded before full follow-up. Pending or unobserved outcomes are never converted into failed care.

Reports include protocol/dataset checksums, assigned-arm counts, receipt/nonreceipt/missingness, baseline balance, observed-case rates and worst/best binary-outcome difference bounds. Fully observed registered randomized fixtures also report an assigned-arm difference. A labelled normal-approximation interval is available only when each arm has at least 20 units and at least five observations of each outcome. These restrictions do not establish statistical adequacy for a clinical study; they are safeguards for this limited demonstration.

No effect estimate is returned for missing outcomes or observational allocation. Observational rate differences remain unadjusted associations. The tool does not estimate individual treatment effects, adjust unmeasured confounding, select policies, or provide prospective clinical validation. Registered causal forests, doubly robust learning, uplift models and contextual bandits require a justified study design, suitable approved data and separate validation before any clinical use. The current alternative permitted by the master prompt remains rules plus human oversight.

Reporting separates assignment, receipt and missing outcomes, consistent with the considerations discussed in the [CONSORT 2025 explanation and elaboration](https://pmc.ncbi.nlm.nih.gov/articles/PMC11995452/). This software is not a certified trial platform or an endorsement by the guideline authors. Independent research, privacy, clinical and statistical review must precede real studies.
