from verified_transition_loop import EvidenceLedger


def test_ledger_isolated_from_caller_payload_mutation():
    ledger = EvidenceLedger()
    payload = {"decision": {"verdict": "AUTHORIZE"}}
    returned = ledger.append("decision", payload)

    payload["decision"]["verdict"] = "BLOCK"
    returned.payload["decision"]["verdict"] = "HOLD"

    records = ledger.records
    assert records[0].payload == {"decision": {"verdict": "AUTHORIZE"}}
    assert EvidenceLedger.verify(records)


def test_ledger_records_property_returns_defensive_copies():
    ledger = EvidenceLedger()
    ledger.append("decision", {"verdict": "AUTHORIZE"})

    exposed = ledger.records
    exposed[0].payload["verdict"] = "BLOCK"

    fresh = ledger.records
    assert fresh[0].payload == {"verdict": "AUTHORIZE"}
    assert EvidenceLedger.verify(fresh)
