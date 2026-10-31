# tests

Test suite for ClaimGuard end-to-end data and ML pipeline.

## Running Tests

```bash
pip install pytest

# Run offline unit and schema tests
pytest tests/test_pipeline.py -v -k "not Integration"

# Run integration tests against a live API instance
API_URL=http://localhost:8000 pytest tests/test_pipeline.py -v -k "Integration"
```
