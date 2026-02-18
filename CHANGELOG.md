# Changelog

## [0.7.0](https://github.com/ValueArchitectsAI/sop-mcp/compare/v0.6.0...v0.7.0) (2026-02-18)


### Features

* **resources:** Expose SOPs as MCP resources with text/markdown ([8188e2d](https://github.com/ValueArchitectsAI/sop-mcp/commit/8188e2d5e8e4833616608f35a5f0dc00ef94a6e1))
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
