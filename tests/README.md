# Foundation tests

Run from the repository root after installing the locked Python environment:

```text
python -m unittest discover -s tests -v
```

Step 1 verifies application import/lifespan without opening a listener.
Persistence, configuration, authorization, migration, CRUD, isolation, and
supplier-contract tests arrive with their corresponding implementation steps.
Tests must never require production credentials, paid inference, or customer funds.
