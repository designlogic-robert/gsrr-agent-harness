"""Demonstrate why a provider SUCCESS report is not authoritative realization."""

from gsrr_slice01.contracts import Decision, Outcome, Report
from gsrr_slice01.fixture import FixtureFaults
from gsrr_slice01.runtime import Request, SliceRuntime


def main() -> None:
    # The provider is invoked and reports SUCCESS, but this deterministic fault
    # performs no state-changing action. Independent observation remains DRAFT.
    runtime = SliceRuntime(faults=FixtureFaults(actions=()))
    initial_authority = runtime.journal.aggregate.authority_state
    request = Request()

    result = runtime.run(request)

    # Executable documentation: these assertions define the public demonstration.
    assert result.execution is not None
    assert result.execution.reported_status == Report.SUCCESS
    assert runtime.provider.view.state == "DRAFT"
    assert result.reconciliation is not None
    assert result.reconciliation.outcome == Outcome.RECONCILIATION_FAILED
    assert result.projection is not None
    assert result.projection.final_decision == Decision.DO_NOT_PROJECT
    assert result.projection.authoritative_state_changed is False
    assert runtime.journal.aggregate.authority_state == "DRAFT"

    print("GSRR Slice 01 — False-Success Path")
    print("=" * 40)
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
    print("The provider reported SUCCESS, but the required REVIEW effect was not observed.")
    print("Reconciliation therefore failed and REVIEW was not projected as authoritative.")
    print()
    print("provider success != realized authoritative state")


if __name__ == "__main__":
    main()
