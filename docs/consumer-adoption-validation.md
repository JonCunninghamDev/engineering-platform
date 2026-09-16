# Consumer Adoption Validation

This validation proves the released platform adoption contract without migrating or naming a real consumer repository.

## Validated path

1. Verify the published platform release and record both its semantic tag and immutable release commit.
2. Record the pin in a consumer-owned manifest together with generic capability/profile selection.
3. Synchronize the required steering and policy files into the consumer so ordinary work does not require runtime access to the platform repository.
4. Invoke reusable consumer CI from the immutable platform pin using generic capability inputs.
5. Record upgrade compatibility impact, complete validation evidence, and an explicit rollback to the prior immutable pin and synchronized steering.
6. Confirm that loss of access to the platform repository does not prevent local steering reads, local tests, defect work, or rollback.

The executable fixture in `tests/fixtures/consumer-adoption/consumer-manifest.json` models this path using a deliberately generic repository identity. `tests/test_consumer_adoption.py` verifies the immutable pin, local failure isolation, generic reusable-CI inputs, upgrade evidence, and rollback contract.

## Boundary

This validation does not claim that a named external product repository has migrated. Product-specific migration, prerequisites, branch rules, visual gates, credentials, and exceptions remain consumer-owned work. The platform validation is complete when the generic contract is executable and the released public surfaces it references are verifiable.
