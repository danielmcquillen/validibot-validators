# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-02-13

### Security

- Run containers as non-root `validibot` user in both EnergyPlus and FMI Dockerfiles

## [0.2.0] - 2026-02-05

### Added

- Support for `resource_files` in EnergyPlus runner, enabling weather data to be
  provided via `resource_files` (type `energyplus_weather`) in addition to the
  legacy `input_files` (role `weather`) approach
- CODEOWNERS file to require owner review on all changes
- Third-party acknowledgments in README

### Changed

- Updated GitHub URLs to use `danielmcquillen` org

### Fixed

- License mismatch between LICENSE file and pyproject.toml

## [0.1.0] - 2025-12-05

### Added

- Initial release with EnergyPlus and FMI validator containers
- Core validator framework with shared utilities
- EnergyPlus error message extraction from `.err` files
- Justfile for building, testing, and deploying validators
- Cloud Run Jobs deployment support
- Docker multi-stage builds for EnergyPlus (with build-time EnergyPlus installation)

[Unreleased]: https://github.com/danielmcquillen/validibot-validators/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/danielmcquillen/validibot-validators/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/danielmcquillen/validibot-validators/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/danielmcquillen/validibot-validators/releases/tag/v0.1.0
