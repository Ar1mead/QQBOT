# Decision 0001: Single Project Repository

- **Status:** Accepted
- **Decision:** `Ar1mead/QQBOT` is the single primary repository for the complete AI individual project.
- **Scope:** Cognitive-state core, ASM, memory, personality, life engine, runtime integration, platform adapters, documentation, and tests belong in this repository.
- **Naming:** Keep the existing repository name `QQBOT` for now. The name does not limit the repository to QQ bot code.
- **Structure:** Separate modules by directory and explicit interfaces rather than creating separate repositories at this stage.
- **Rationale:** The project needs one coherent history for architecture, specifications, core state, and platform integrations while preserving replaceable module boundaries.
- **Consequences:** Repository structure may evolve as implementation clarifies module boundaries. This decision does not require every planned directory or component to be created immediately.
