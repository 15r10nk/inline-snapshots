<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
<!--
### Added

- A bullet item for the Added category.

-->
### Changed

- inline-snapshot uses now `--inline-snapshot=disable` during CI runs by default.
    This improves performance because `snapshot()` is then equal to:
    ```python
    def snapshot(x):
        return x
    ```




<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
<!--
### Fixed

- A bullet item for the Fixed category.

-->
<!--
### Security

- A bullet item for the Security category.

-->
