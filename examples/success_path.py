"""Run the canonical successful GSRR Slice 01 realization path."""

from gsrr_slice01.contracts import Control, Decision, Outcome, Report
from gsrr_slice01.runtime import Request, SliceRuntime


def main() -> None:
    runtime = SliceRuntime()
    initial_authority = runtime.journal.aggregate.authority_state
    request = Request()

    result = runtime.run(request)

    # Executable documentation: fail loudly if the demonstration stops matching
    # the bounded public Slice 01 contract.
    assert result.control == Control.PASS
    assert result.execution is not None
    assert result.execution.reported_status == Report.SUCCESS
    assert result.reconciliation is not None
    assert result.reconciliation.outcome == Outcome.RECONCILED_SUCCESS
    assert result.projection is not None
    assert result.projection.final_decision == Decision.PROJECT
    assert result.projection.write_outcome == "APPLIED"
    assert runtime.journal.aggregate.authority_state == "REVIEW"

    print("GSRR Slice 01 — Success Path")
    print("=" * 34)
    print(f"Realization mode      : {request.mode}")
    print(f"Requested transition  : {initial_authority} -> {request.target_state}")
    print(f"Execution report      : {result.execution.reported_status}")
    print(f"Observed state        : {runtime.provider.view.state}")
    print(f"Reconciliation        : {result.reconciliation.outcome}")
    print(f"Projection decision   : {result.projection.final_decision} / {result.projection.write_outcome}")
    print(f"Authoritative state   : {initial_authority} -> {runtime.journal.aggregate.authority_state}")
    print(f"Provider invocations  : {runtime.provider.invocation_count}")
    print()
    print("Outcome:")
    print("The realized REVIEW state was independently reconciled and then admitted")
    print("through the final PROJECT / APPLIED projection gate.")


if __name__ == "__main__":
    main()
