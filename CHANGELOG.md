# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-08-28

### Fixed

- Anonymous models -- those generated for object schemas written inline rather than
  under `$defs` -- are now rebuilt against the completed namespace. Previously only
  models reachable from `$defs` were rebuilt, so an inline object containing a `$ref`
  kept the reference as an unresolved forward reference and stayed incomplete
  (`__pydantic_complete__ == False`) while the root model reported complete. This
  broke consumers that copy field annotations into a new `create_model` in a
  different module. Extends the `$defs`-only fix from 0.3.1.

## [0.4.0] - 2026-03-23

### Changed

- **Breaking**: Objects without defined properties now return a Pydantic model instead of `Dict[str, Any]`. This ensures consistent handling of `additionalProperties` regardless of whether properties are defined.

### Added

- Support for `additionalProperties` as a schema: when `additionalProperties` is a schema object (dict), it is now properly converted and used as the type for additional properties.

### Fixed

- Fixed inconsistent behavior in `_convert_object` when properties are present vs. absent. Objects are now always created through the same code path, ensuring uniform handling of configuration options like `additionalProperties`.

## [0.3.1] - Previous

_See git history for earlier releases._
