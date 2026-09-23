"""In-memory capture of bounded runtime records used by the Slice 01 tests."""
import pytest

from gsrr_slice01.contracts import plain


TRACES = {}


@pytest.fixture
def capture(request):
    """Retain the current test's runtime trace in memory without writing repo files."""
    def retain(runtime, label="main"):
        TRACES.setdefault(request.node.nodeid, {})[label] = {
            "result": plain(runtime.result()),
            "authority_state": runtime.journal.aggregate.authority_state,
            "authority_version": runtime.journal.aggregate.authority_version,
            "observed_effect_state": plain(runtime.provider.view),
            "provider_reads": runtime.provider.read_count,
            "invocations": runtime.provider.invocation_count,
            "external_planner_calls": runtime.planner.calls,
            "provider_internal_planning_calls": runtime.capability.internal_planning_calls,
            "attempts": plain(runtime.supervisor.attempts),
            "scope": plain(runtime.supervisor.ledger),
            "records": {
                key: plain(value)
                for key, value in runtime.journal.aggregate.records
            },
            "events": plain(runtime.journal.aggregate.events),
        }

    return retain
