# Plugin Development

InkSight supports extensible content modes.

## Basic Idea

- each mode defines data generation logic
- backend renders generated content into E-Ink layout
- mode registry controls discoverability and metadata

## Suggested Workflow

1. Create a new mode module
2. Register the mode in backend registry
3. Add prompt and rendering logic
4. Test via preview/config page
