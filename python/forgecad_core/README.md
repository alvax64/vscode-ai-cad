# forgecad_core

This package is reserved for reusable Python geometry code.

It should contain logic that can be used by the service, tests, scripts, and
future command-line tools without importing the service server.

## Candidate Modules

- CAD object normalization.
- OCP/CadQuery/build123d type adapters.
- Tessellation helpers.
- Shape path and ID helpers.
- Metadata extraction.
- Measurement helpers.
- STL export helpers.

The first implementation should migrate behavior from the current
`ocp_vscode` modules with focused tests.
