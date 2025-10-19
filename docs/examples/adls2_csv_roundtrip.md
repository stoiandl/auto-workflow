# ADLS2 CSV Roundtrip

End-to-end example: `examples/adls_csv_flow.py`

This flow demonstrates:
- Ensuring a container exists
- Creating a folder
- Writing a small CSV
- Reading and printing its contents
- Cleaning up the created resources

## Install

```bash
poetry install -E connectors-adls2
# or
poetry install -E connectors-all
```

## Environment (profile: ADLS_TEST)

```bash
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__CONNECTION_STRING="DefaultEndpointsProtocol=..."
# or AAD-based
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__ACCOUNT_URL="https://<acct>.dfs.core.windows.net"
export AUTO_WORKFLOW_CONNECTORS_ADLS2_ADLS_TEST__USE_DEFAULT_CREDENTIALS=true
```

## Run

```bash
poetry run python examples/adls_csv_flow.py
```

Expected output:

```
CSV rows:
['id', 'name']
['1', 'alice']
['2', 'bob']
['3', 'cathy']
Flow returned 4 rows
```
