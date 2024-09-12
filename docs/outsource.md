## General

Storing snapshots in the source code is the main feature of inline snapshots.
This has the advantage that you can easily see changes in code reviews. But it also has some problems:

* It is problematic to snapshot a lot of data, because it takes up a lot of space in your tests.
* Binary data or images are not readable in your tests.

The `outsource()` function solves this problem and integrates itself nicely with the inline snapshot.
It stores the data in a special `external()` object that can be compared in snapshots.
The object is represented by the hash of the data.
The actual data is stored in a separate file in your project.

This allows the test to be renamed and moved around in your code without losing the connection to the stored data.

Example:

=== "original code"
    <!-- inline-snapshot: first_block outcome-passed=1 outcome-errors=1 -->
    ``` python
    from inline_snapshot import snapshot, outsource


    def test_something():
        assert outsource("long text\n" * 1000) == snapshot()
    ```

=== "--inline-snapshot=create"
    <!-- inline-snapshot: create outcome-passed=1 -->
    ``` python hl_lines="2 3 7 8 9"
    from inline_snapshot import snapshot, outsource

    from inline_snapshot import external


    def test_something():
        assert outsource("long text\n" * 1000) == snapshot(
            external("hash:f5a956460453*.txt")
        )
    ```

The `external` object can be used inside other data structures.

=== "original code"
    <!-- inline-snapshot: first_block outcome-passed=1 outcome-errors=1 -->
    ``` python
    from inline_snapshot import snapshot, outsource


    def test_something():
        assert [
            outsource("long text\n" * times) for times in [50, 100, 1000]
        ] == snapshot()
    ```

=== "--inline-snapshot=create"
    <!-- inline-snapshot: create outcome-passed=1 -->
    ``` python hl_lines="2 3 9 10 11 12 13 14 15"
    from inline_snapshot import snapshot, outsource

    from inline_snapshot import external


    def test_something():
        assert [
            outsource("long text\n" * times) for times in [50, 100, 1000]
        ] == snapshot(
            [
                external("hash:362ad8374ed6*.txt"),
                external("hash:5755afea3f8d*.txt"),
                external("hash:f5a956460453*.txt"),
            ]
        )
    ```


## API

::: inline_snapshot.outsource
    options:
      show_root_heading: true

::: inline_snapshot.external
    options:
      show_root_heading: true

## pytest options

It interacts with the following `--inline-snapshot` flags:

- `trim` removes every snapshots form the storage which is not referenced with `external(...)` in the code.
