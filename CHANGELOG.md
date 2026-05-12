# Changelog

## [0.12.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.11.0...v0.12.0) (2026-05-12)


### Features

* **mcp:** upgrade to protocol 2025-06-18 with richer metadata, pagination, and correct error codes ([b150b71](https://github.com/ValueArchitectsAI/sop-mcp/commit/b150b71de24302642a22a7e1c2538521d8b79573))
* **templates:** expose packaged SOP scaffolds under template:// ([e676f1b](https://github.com/ValueArchitectsAI/sop-mcp/commit/e676f1b1b24ac4d2e3daaa2029c7b30d1038233f))


### Bug Fixes

* replace datetime.UTC with timezone.utc for Python 3.10 compat ([56a770e](https://github.com/ValueArchitectsAI/sop-mcp/commit/56a770eac6d8a6deb6ff4ac9c1f9545e66f1f75d))

## [0.11.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.10.1...v0.11.0) (2026-05-12)


### Features

* **lint,mcp:** Enforce parameter schema with SOP109 and surface params in resource descriptions ([2443652](https://github.com/ValueArchitectsAI/sop-mcp/commit/244365265280b96b350aae2cf6e45d5a3f9d76ec))
* **lint:** Add sop-lint rule engine and CLI ([5b37b79](https://github.com/ValueArchitectsAI/sop-mcp/commit/5b37b793671be11e5dbf351ee17c4675085064c1))
* **mcp:** Wire sop-lint into publish_sop and update step-heading parser ([43e0f3a](https://github.com/ValueArchitectsAI/sop-mcp/commit/43e0f3a181804272409570de232afd23cb165f22))
* **sops:** Migrate bundled example SOPs to Agent SOP spec format ([64e580b](https://github.com/ValueArchitectsAI/sop-mcp/commit/64e580ba80b6577a5f172496ea0470e38732f609))

## [0.10.1](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.10.0...v0.10.1) (2026-05-11)


### Bug Fixes

* **sop:** Add optional References section to SOP template ([c30127e](https://github.com/ValueArchitectsAI/sop-mcp/commit/c30127e6913e47939356e2661c7f3b9cd2cc5a47))
* **sop:** Add optional References section to SOP template ([#88](https://github.com/ValueArchitectsAI/sop-mcp/issues/88)) ([18a841d](https://github.com/ValueArchitectsAI/sop-mcp/commit/18a841df554b059ce2a1bcd260f6c3e762c25af2))

## [0.10.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.9.4...v0.10.0) (2026-05-05)


### Features

* add list_resources to llms.txt tool reference ([#83](https://github.com/ValueArchitectsAI/sop-mcp/issues/83)) ([a3b15ed](https://github.com/ValueArchitectsAI/sop-mcp/commit/a3b15edd4cfdfe37d3aa6888c2e78f4e1067dda1))
* flat SOP layout with YAML frontmatter and integer versions ([#82](https://github.com/ValueArchitectsAI/sop-mcp/issues/82)) ([f001022](https://github.com/ValueArchitectsAI/sop-mcp/commit/f001022))
* cap step_output at 50 KB to bound input size ([c917da1](https://github.com/ValueArchitectsAI/sop-mcp/commit/c917da1))
* improve adoption with stable storage default, catalog, and publish mismatch warnings ([ee56ea5](https://github.com/ValueArchitectsAI/sop-mcp/commit/ee56ea5))
* add server instructions, parameter descriptions, and doc generator ([907f63b](https://github.com/ValueArchitectsAI/sop-mcp/commit/907f63b))
* expose SOP attachments via sop://{name}/{relative_path} ([3d9deb8](https://github.com/ValueArchitectsAI/sop-mcp/commit/3d9deb8))
* support resources/subscribe and per-resource updated notifications ([7352df7](https://github.com/ValueArchitectsAI/sop-mcp/commit/7352df7))
* require stage parameter on publish_sop and overwrite frontmatter on write ([7b63ba6](https://github.com/ValueArchitectsAI/sop-mcp/commit/7b63ba6))


### Bug Fixes

* seed full SOP folders so attachments travel with their SOP ([9349d8a](https://github.com/ValueArchitectsAI/sop-mcp/commit/9349d8a))
* route stdio tool calls through call_tool so hooks fire ([6d84851](https://github.com/ValueArchitectsAI/sop-mcp/commit/6d84851))
* resolve validator warnings in sop_creation_guide and add validate_sop.py ([c8f5d28](https://github.com/ValueArchitectsAI/sop-mcp/commit/c8f5d28))
* remove version argument from SOP instantiation in resolve_sop ([d81f262](https://github.com/ValueArchitectsAI/sop-mcp/commit/d81f262))
* remove unreachable code block left in _extract_steps ([3e8e937](https://github.com/ValueArchitectsAI/sop-mcp/commit/3e8e937))

## [0.9.4](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.9.3...v0.9.4) (2026-04-12)


### Bug Fixes

* Add missing resources tools([#68](https://github.com/ValueArchitectsAI/sop-mcp/issues/68)) ([6a5b0dc](https://github.com/ValueArchitectsAI/sop-mcp/commit/6a5b0dcfda3743d256ea00599123f9a55bf8f9dc))

## [0.9.3](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.9.2...v0.9.3) (2026-04-12)


### Bug Fixes

* replace fastmcp with StdioMCP — zero C-dependencies ([#66](https://github.com/ValueArchitectsAI/sop-mcp/issues/66)) ([42c4dd1](https://github.com/ValueArchitectsAI/sop-mcp/commit/42c4dd1227ba5ba36fac79c88d1ad7f0d71ec34b))

## [0.9.2](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.9.1...v0.9.2) (2026-04-06)


### Bug Fixes

* rename src/mcp to src/sop_mcp to resolve Python namespace collision ([#60](https://github.com/ValueArchitectsAI/sop-mcp/issues/60)) ([cab0762](https://github.com/ValueArchitectsAI/sop-mcp/commit/cab07626a5016fa55e89558e0d57b01938b836b3))

## [0.9.1](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.9.0...v0.9.1) (2026-03-18)


### Bug Fixes

* add YAML support for hook configuration ([#50](https://github.com/ValueArchitectsAI/sop-mcp/issues/50)) ([022b502](https://github.com/ValueArchitectsAI/sop-mcp/commit/022b502ca4bfed55e851170fdb027ee1255dd6cd))

## [0.9.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.8.0...v0.9.0) (2026-03-18)


### Features

* **hooks:** Add FastMCP middleware hook system with e2e tests ([#47](https://github.com/ValueArchitectsAI/sop-mcp/issues/47)) ([2557fc7](https://github.com/ValueArchitectsAI/sop-mcp/commit/2557fc7ec2be615d1bbf09d2a68dc45443896d6d))

## [0.8.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.7.1...v0.8.0) (2026-03-03)


### Features

* add S3 storage backend for SOP persistence ([#38](https://github.com/ValueArchitectsAI/sop-mcp/issues/38)) ([3fa9730](https://github.com/ValueArchitectsAI/sop-mcp/commit/3fa973080ea340c89b236944fe47adcd054b73eb))

## [0.7.1](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.7.0...v0.7.1) (2026-02-20)


### Bug Fixes

* **publish_sop:** Improve tool description and upgrade fastmcp to 3.0.0 ([#26](https://github.com/ValueArchitectsAI/sop-mcp/issues/26)) ([e4fdb81](https://github.com/ValueArchitectsAI/sop-mcp/commit/e4fdb81d34d68594d9bfae90ed77ba40117d34ce))

## [0.7.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.6.0...v0.7.0) (2026-02-18)


### Features

* **resources:** Expose SOPs as MCP resources with text/markdown ([8188e2d](https://github.com/ValueArchitectsAI/sop-mcp/commit/8188e2d5e8e4833616608f35a5f0dc00ef94a6e1))
* Unify SOP tools into single run_sop with conditional step_output ([25a0562](https://github.com/ValueArchitectsAI/sop-mcp/commit/25a05628ef2c556ab6e337158e4cd13d0333d0b6))
* Upgrade from mcp SDK to FastMCP 3.0 ([07b46f3](https://github.com/ValueArchitectsAI/sop-mcp/commit/07b46f399bc435bd25dff1a192faba35d9bab939))

## [0.6.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.5.0...v0.6.0) (2026-02-16)


### Features

* Add optinal previous_outputs accumulation for multi-step SOP execution ([#19](https://github.com/ValueArchitectsAI/sop-mcp/issues/19)) ([eef2bd1](https://github.com/ValueArchitectsAI/sop-mcp/commit/eef2bd195e9c83266144bb438d1ee7043c8bcba5))

## [0.5.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.4.0...v0.5.0) (2026-02-15)


### Features

* Improve LLM output quality and slim handler response ([#16](https://github.com/ValueArchitectsAI/sop-mcp/issues/16)) ([03621b4](https://github.com/ValueArchitectsAI/sop-mcp/commit/03621b4baff197bfdd515181d5ad0f476567b558))

## [0.4.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.3.0...v0.4.0) (2026-02-14)


### Features

* Add MCP server prerequisites support to SOP system ([#11](https://github.com/ValueArchitectsAI/sop-mcp/issues/11)) ([d99ae9f](https://github.com/ValueArchitectsAI/sop-mcp/commit/d99ae9f5579b86464ee06e6bfcae57efdada3922))


### Bug Fixes

* Set dependabot package-ecosystem to uv and github-actions ([6a768da](https://github.com/ValueArchitectsAI/sop-mcp/commit/6a768da47a227619c19e1af31de794077b5c2f25))

## [0.3.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.2.0...v0.3.0) (2026-02-13)


### Features

* add E2E MCP tests over stdio and gitignore feedback.md ([58d7d6d](https://github.com/ValueArchitectsAI/sop-mcp/commit/58d7d6d113d5c8978cb876a8bea4f2320ddeedb7))
* Add PyPI badges, one-click install links, and fix CI workflows ([#6](https://github.com/ValueArchitectsAI/sop-mcp/issues/6)) ([bcd58fc](https://github.com/ValueArchitectsAI/sop-mcp/commit/bcd58fc89646600c67701e8e543c0675f46d0c3b))
* add SOP storage abstraction layer ([d402f49](https://github.com/ValueArchitectsAI/sop-mcp/commit/d402f49910e4b272f36c27475944b154ecd910d5))
* add time estimate warning on publish, update README and steering ([98946a8](https://github.com/ValueArchitectsAI/sop-mcp/commit/98946a88707fb2ff2fbd65b1ead5f68df0e57ea0))
* support Python 3.10-3.13, add tox-uv for multi-version testing ([c301643](https://github.com/ValueArchitectsAI/sop-mcp/commit/c301643a03bac6dcfcc51823d77c4b7840973022))


### Bug Fixes

* add contents:read permission to publish jobs ([362b835](https://github.com/ValueArchitectsAI/sop-mcp/commit/362b835659331082effa95cd03f5bef82ab574cb))
* cap hypothesis &lt;6.150 to fix Python 3.12 CI failure ([0b6109f](https://github.com/ValueArchitectsAI/sop-mcp/commit/0b6109f108e13e443f092cf7e84304b5edc4bd46))
* resolve ruff linting and formatting issues across src/ and tests/ ([315e30e](https://github.com/ValueArchitectsAI/sop-mcp/commit/315e30eae3f82108090847384e1f995543b0b54a))
* sort imports in test_storage_backend, add lint+test pre-commit hook ([0980da9](https://github.com/ValueArchitectsAI/sop-mcp/commit/0980da94c04c5cf9f53e5e999279ef686c3d75e8))
* use uv sync --frozen in CI to respect lockfile ([0ca6121](https://github.com/ValueArchitectsAI/sop-mcp/commit/0ca6121f83adc25b8843872c1050806937e58584))


### Documentation

* add AGENT.md, remove .kiro steering, untrack .vscode and .DS_Store ([4ee71a9](https://github.com/ValueArchitectsAI/sop-mcp/commit/4ee71a93437ddf85313d70171b1067de1ceefc60))

## [0.2.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.1.0...v0.2.0) (2026-02-13)


### Features

* Add PyPI badges, one-click install links, and fix CI workflows ([#6](https://github.com/ValueArchitectsAI/sop-mcp/issues/6)) ([bcd58fc](https://github.com/ValueArchitectsAI/sop-mcp/commit/bcd58fc89646600c67701e8e543c0675f46d0c3b))
