# Methodology and controls

`perfaud` compares two reported-data snapshots without redesigning the accounting
system that produced them. It identifies changed portfolio returns and security
returns, connects those changes to available source evidence, and separates explained
effects from residuals requiring review.

The workflow is:

1. validate the configuration, source contracts, and financially material policy;
2. load both snapshots through explicit Axys/APX column mappings;
3. compare portfolio, security, holding, transaction, and reference evidence;
4. reconstruct returns where configured and estimate only supported impacts;
5. enforce conservation, lineage, financial-integrity, and explanation-reconciliation
   invariants; and
6. publish the complete validated report set atomically.

The system does not guess transaction meaning or causal attribution. Ambiguous or
incomplete evidence remains visible for review. Suppression changes presentation, not
the underlying audit trail.

Artifact schemas, signs, rounding, finding classifications, and explanation semantics
are stable product contracts. Detailed design material is available in
[`reference/comparison.md`](reference/comparison.md),
[`reference/safety_invariants.md`](reference/safety_invariants.md), and
[`reference/transaction_policy.md`](reference/transaction_policy.md).
